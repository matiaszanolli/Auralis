#!/usr/bin/env python3

"""
Normal (Unprocessed) Audio Streaming
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The stream_normal_audio entry point: streams original, unprocessed audio
chunks to a client via WebSocket for A/B comparison against the enhanced
path. No DSP or crossfade is applied — chunks are read straight from disk
(or a temp WAV for compressed formats) with look-ahead I/O.

Extracted from audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import functools
import logging
import shutil
from pathlib import Path
from typing import Any
from collections.abc import Callable

import numpy as np
import soundfile as sf
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc
from .executors import run_in_stream_executor
from security.path_security import PathValidationError, validate_file_path

logger = logging.getLogger(__name__)

# How many consecutive per-chunk disk-read timeouts end the stream (#5082).
# Bounding each read with wait_for stops the stream hanging forever, but it
# does NOT stop the blocking sf.SoundFile read underneath: wait_for bounds the
# *coroutine*, and the worker thread it abandons keeps running in the default
# executor — the orphaned-thread caveat #4815/#4727 record. This fix does not
# eliminate that leak. So on storage that is genuinely gone, retrying every
# chunk would strand one executor thread per chunk and hold the stream permit
# for total_chunks x CHUNK_PROCESS_TIMEOUT. Two in a row is enough evidence
# that the backing file is unreachable rather than one chunk being slow.
MAX_CONSECUTIVE_READ_TIMEOUTS: int = 2


async def stream_normal_audio(
    controller: '_asc.AudioStreamController',
    track_id: int,
    websocket: WebSocket,
    start_position: float = 0.0,
    on_progress: Callable[[int, float, str], Any] | None = None
) -> None:
    """
    Stream original (unprocessed) audio chunks to client via WebSocket.

    Used for comparing original vs enhanced audio. Same chunking format as enhanced,
    but with no DSP processing applied.

    Args:
        controller: AudioStreamController instance
        track_id: Track ID to stream
        websocket: WebSocket connection to client
        on_progress: Optional callback for progress updates

    Raises:
        ValueError: If track not found or file unavailable
        Exception: If loading or streaming fails
    """
    _asc._stream_type_var.set("normal")  # per-task; safe for concurrent coroutines (fixes #2493)

    if not controller._get_repository_factory:
        raise ValueError("RepositoryFactory not available")

    # Limit concurrent streams to prevent unbounded memory growth (#2185)
    try:
        await asyncio.wait_for(
            controller._stream_semaphore.acquire(),
            timeout=_asc.STREAM_ACQUIRE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"Stream limit ({_asc.MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
        )
        await controller._send_error(websocket, track_id, "Server busy - too many active streams")
        return

    # Declare look-ahead task early so the outer `finally:` can drain it
    # even on early-exit paths (fixes #3493 unbound-var hazard).
    lookahead_read: asyncio.Task[np.ndarray] | None = None

    # Track whether the client received the whole stream. A failed binary
    # frame must not be reported as a completed track (#4732).
    stopped_early: bool = False
    delivered_samples: int = 0
    # Chunk indices skipped via the #3190 continue-and-keep-going recovery
    # path below (#4790): the loop can run to its natural end with gaps in
    # the delivered audio without stopped_early ever being set, so this loop
    # DOES have an early-break-with-partial-content case after all — via
    # `continue`, not `break`.
    failed_chunks: list[int] = []
    # Consecutive per-chunk disk-read timeouts — see
    # MAX_CONSECUTIVE_READ_TIMEOUTS at module scope for why the run is bounded
    # (#5082).
    read_timeouts: int = 0

    # temp_dir is declared before the guard so the finally cleanup can see it
    # regardless of where control leaves the try below. It is the *directory*
    # we remove, never the WAV path — the #4365 rule.
    #
    # That rule now holds in two places. convert_to_temp_wav() (#4737) creates
    # its directory before decoding and rmtree's it itself if the decode or the
    # write raises, so a failed conversion leaves temp_dir None here and there
    # is nothing left to clean. On success it hands the directory back and this
    # finally owns it for the rest of the stream. The separate temp_wav_path
    # variable that used to exist alongside this one is gone: it was only ever
    # written, never read.
    #
    # For compressed formats (MP3, M4A, etc.), convert to temp WAV first
    # since sf.SoundFile only supports PCM formats (#3225).
    temp_dir: str | None = None

    # A single try/finally from here guards the semaphore permit acquired above:
    # it is released exactly once in the finally at the end. The track lookup
    # lives INSIDE this try so a task cancellation (CancelledError — a
    # BaseException that `except Exception` does not catch) during the awaited
    # get_by_id cannot escape before the permit is released, which would leak a
    # permit permanently for the process lifetime (#4329).
    try:
        # Get track from library
        try:
            factory = controller._get_repository_factory()
            track = await asyncio.to_thread(factory.tracks.get_by_id, track_id)
            if not track:
                await controller._send_error(websocket, track_id, "Track not found")
                return

            # Validate the DB-retrieved filepath before any file I/O — mirrors
            # metadata.py's guard (fixes #2302), extended here to streaming's
            # highest-traffic consumer of track.filepath (#4345).
            try:
                validated_filepath = str(
                    await asyncio.to_thread(
                        functools.partial(
                            validate_file_path,
                            str(track.filepath),
                            context=f"track {track_id}",
                        )
                    )
                )
            except PathValidationError:
                # No logger call here: validate_file_path logs the rejection
                # itself with the context above, exactly once (#4925).
                await controller._send_error(
                    websocket, track_id, "Audio file not found"
                )
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}", exc_info=True)
            await controller._send_error(websocket, track_id, "Failed to load track")
            return

        streaming_filepath = validated_filepath

        from auralis.io.unified_loader import FFMPEG_FORMATS
        file_ext = Path(validated_filepath).suffix.lower()
        if file_ext in FFMPEG_FORMATS:
            # Shares the decode-once-to-temp-WAV mechanics with the enhanced
            # chunk path (#4737) instead of a second inline copy. The *trigger*
            # stays extension-based here on purpose: the enhanced path converts
            # only when libsndfile genuinely cannot open the file, but this path
            # has always converted every FFMPEG_FORMATS entry — including .mp3
            # and .ogg, which libsndfile can in fact seek — and narrowing that
            # would change normal-streaming seek behaviour for the most common
            # library format. Left alone deliberately; see the issue notes.
            from config.limits import stream_temp_prefix
            from core.seekable_source import convert_to_temp_wav

            # PID-tagged so the startup sweep can tell a live instance's temp
            # WAV from a genuinely orphaned one (#4713).
            converted_dir, converted_wav = await asyncio.to_thread(
                convert_to_temp_wav, validated_filepath, prefix=stream_temp_prefix()
            )
            temp_dir = converted_dir
            streaming_filepath = converted_wav
            logger.info(f"Converted {file_ext} to temp WAV for normal streaming")

        # Read file metadata only — do NOT load audio data yet (#2121).
        # sf.read() would allocate ~200 MB for a 10-min stereo track; instead
        # we open the SoundFile, record its shape, and close it immediately.
        def _get_audio_info(filepath: str) -> tuple[int, int, int]:
            with sf.SoundFile(filepath) as audio_file:
                return audio_file.samplerate, audio_file.channels, len(audio_file)

        sample_rate, channels, total_frames = await asyncio.to_thread(
            _get_audio_info, streaming_filepath
        )

        duration = total_frames / sample_rate

        # Calculate chunks (NO overlap for normal streaming - no crossfade applied)
        # #3775: pull the constant from chunk_boundaries instead of
        # re-declaring it (third declaration removed; chunked_processor
        # CHUNK_DURATION already mirrors chunk_boundaries.CHUNK_DURATION).
        from .chunk_boundaries import CHUNK_DURATION
        chunk_duration = float(CHUNK_DURATION)
        chunk_samples = int(chunk_duration * sample_rate)

        # For normal path: chunk_interval = chunk_duration (no overlap)
        # Unlike enhanced path which uses ChunkedProcessor with server-side crossfade,
        # normal path sends chunks without processing, so overlap would cause duplication
        interval_samples = chunk_samples  # No overlap

        total_chunks = max(1, int(np.ceil(total_frames / interval_samples)))

        # Calculate start chunk for seek (#3187)
        start_chunk = 0
        if start_position > 0:
            start_sample = int(start_position * sample_rate)
            start_chunk = min(start_sample // interval_samples, total_chunks - 1)

        logger.info(
            f"Starting normal audio stream: track={track_id}, "
            f"duration={duration:.1f}s, chunks={total_chunks}, sr={sample_rate}Hz"
            + (f", seek={start_position:.1f}s (chunk {start_chunk})" if start_chunk > 0 else "")
        )

        # When resuming mid-track (start_position > 0), emit is_seek=true so
        # the client preserves its AudioContext + PCMStreamBuffer instead of
        # tearing them down (click-free WS reconnect resume, fixes #3755;
        # mirrors the enhanced path since #3185). chunk_interval ==
        # chunk_duration here (no overlap), so seek_offset is the
        # within-chunk offset of start_position.
        #
        # #4560: seek_offset is INFORMATIONAL. This path used to locate the
        # containing chunk correctly and then stream it from its start,
        # delegating the trim to the client by advertising seek_offset — but no
        # client ever consumed that field, so up to CHUNK_DURATION (15 s) of
        # already-heard audio was replayed on every normal-mode seek and every
        # WS reconnect-resume, while the UI jumped to the requested position.
        # The server is now authoritative and trims the first chunk itself,
        # matching the enhanced path (stream_seek.py). Only one side may trim:
        # adding a client-side trim on top of this would double-skip.
        seek_offset = start_position - (start_chunk * chunk_duration)
        first_chunk_trim_samples = (
            int(start_position * sample_rate) - (start_chunk * interval_samples)
            if start_position > 0
            else 0
        )
        seek_kwargs: dict[str, Any] = {}
        if start_position > 0:
            seek_kwargs = {
                "start_chunk": start_chunk,
                "seek_position": start_position,
                "seek_offset": seek_offset,
            }
        if not await controller._send_stream_start(
            websocket,
            track_id=track_id,
            preset="none",  # No processing
            intensity=1.0,   # Full intensity (original)
            sample_rate=sample_rate,
            channels=channels,
            # #3768: emit the FULL track's chunk count as a stable
            # denominator across seeks; start_chunk (via seek_kwargs)
            # lets the client offset the numerator (matches enhanced
            # path convention since #3185).
            total_chunks=total_chunks,
            chunk_duration=chunk_duration,
            total_duration=duration - (start_chunk * chunk_duration),
            **seek_kwargs,
        ):
            logger.info(f"WebSocket disconnected, cannot start stream")
            return

        # Helper: open → seek → read → close for a single chunk (#2121).
        # Uses streaming_filepath (temp WAV for compressed formats, original for PCM).
        def _read_audio_chunk(filepath: str, start: int, frames: int) -> np.ndarray:
            with sf.SoundFile(filepath) as audio_file:
                audio_file.seek(start)
                # always_2d=True: mono returned as (N, 1) matching stereo shape
                # Do NOT use fill_value: send the last chunk at its actual
                # length to avoid appending silence (#2124).
                return audio_file.read(
                    frames=frames, dtype='float32', always_2d=True
                )

        # Look-ahead variant: short-circuits the disk read if the client
        # vanished during the previous chunk's send (#3874). Runs in a
        # worker thread concurrently with send_pcm_chunk; mirrors the
        # enhanced-path ConnectionError guard in process_chunk_only.
        def _read_audio_chunk_lookahead(filepath: str, start: int, frames: int) -> np.ndarray:
            if not controller._is_websocket_connected(websocket):
                raise ConnectionError("WebSocket disconnected before look-ahead read")
            return _read_audio_chunk(filepath, start, frames)

        # Stream chunks with look-ahead: read chunk N+1 from disk while
        # streaming chunk N to eliminate I/O gaps.
        for chunk_idx in range(start_chunk, total_chunks):
            # Honour pause/resume events from the WebSocket handler (#2106).
            from routers.system import _stream_pause_events, _stream_flow_events
            pause_evt = _stream_pause_events.get(_asc.ws_id(websocket))
            if pause_evt is not None:
                await pause_evt.wait()
            # Honour flow control: wait if frontend buffer is full.
            flow_evt = _stream_flow_events.get(_asc.ws_id(websocket))
            if flow_evt is not None:
                await flow_evt.wait()

            if not controller._is_websocket_connected(websocket):
                logger.info(f"WebSocket disconnected, stopping stream")
                await controller._drain_cancelled_task(lookahead_read)
                lookahead_read = None
                stopped_early = True
                break

            try:
                # Get chunk audio: from look-ahead task or read now
                if lookahead_read is not None:
                    try:
                        # Bounded like every sibling path's chunk producer
                        # (#5082) — see the inline read below for why.
                        # Timed here rather than at create_task() time: the
                        # pause/flow-control waits above sit between the two,
                        # so a legitimately long client pause would otherwise
                        # burn the budget and time out a healthy read.
                        chunk_audio = await asyncio.wait_for(
                            lookahead_read, timeout=_asc.CHUNK_PROCESS_TIMEOUT
                        )
                    except ConnectionError:
                        # Client disconnected during the look-ahead read (#3874).
                        # Clean exit — not a chunk failure, so don't log it as one.
                        stopped_early = True
                        break
                    except TimeoutError:
                        logger.error(
                            f"Look-ahead read for chunk {chunk_idx} timed out after "
                            f"{_asc.CHUNK_PROCESS_TIMEOUT}s (track {track_id})"
                        )
                        read_timeouts += 1
                        raise
                    finally:
                        # wait_for already cancelled the task on timeout, and
                        # the recovery branch drains it; either way this slot
                        # must not be re-awaited next iteration.
                        lookahead_read = None
                else:
                    # #4560: on the first chunk of a seek, start the read at the
                    # requested position rather than at the chunk boundary, and
                    # shorten it to match so the NEXT chunk still begins on its
                    # boundary. Only this branch needs it — the look-ahead below
                    # always reads a full chunk at a boundary, and it is only
                    # ever primed after this first read.
                    trim = first_chunk_trim_samples if chunk_idx == start_chunk else 0
                    start_sample = chunk_idx * interval_samples + trim
                    # Bound the disk read the same way every sibling chunk
                    # producer bounds its worker-thread call (#5082;
                    # stream_chunk_ops/stream_enhanced/stream_seek all use
                    # CHUNK_PROCESS_TIMEOUT). sf.SoundFile open/seek/read on a
                    # stalled network mount or a yanked external drive neither
                    # returns nor raises, so without this the stream hangs
                    # forever holding a MAX_CONCURRENT_STREAMS permit.
                    # TimeoutError is an Exception subclass, so it falls into
                    # the skip-failed-chunk recovery branch below.
                    try:
                        chunk_audio = await asyncio.wait_for(
                            run_in_stream_executor(
                                _read_audio_chunk,
                                streaming_filepath,
                                start_sample,
                                chunk_samples - trim,
                            ),
                            timeout=_asc.CHUNK_PROCESS_TIMEOUT,
                        )
                    except TimeoutError:
                        logger.error(
                            f"Disk read for chunk {chunk_idx} timed out after "
                            f"{_asc.CHUNK_PROCESS_TIMEOUT}s (track {track_id})"
                        )
                        read_timeouts += 1
                        raise

                # Start look-ahead: read next chunk while we stream current one
                if chunk_idx + 1 < total_chunks:
                    next_start = (chunk_idx + 1) * interval_samples
                    lookahead_read = asyncio.create_task(
                        run_in_stream_executor(
                            _read_audio_chunk_lookahead, streaming_filepath, next_start, chunk_samples
                        )
                    )

                # Stream the chunk
                delivered = await controller._send_pcm_chunk(
                    websocket,
                    pcm_samples=chunk_audio,
                    chunk_index=chunk_idx,
                    total_chunks=total_chunks,
                )
                if not delivered:
                    await controller._drain_cancelled_task(lookahead_read)
                    lookahead_read = None
                    await controller._send_error(
                        websocket,
                        track_id,
                        f"Failed to send audio chunk {chunk_idx}",
                        recovery_position=(
                            start_position
                            if chunk_idx == start_chunk
                            else float(chunk_idx * chunk_duration)
                        ),
                    )
                    stopped_early = True
                    break
                delivered_samples += int(chunk_audio.shape[0])
                # A chunk got through, so the storage is responding — only a
                # *run* of timeouts means the backing file is unreachable (#5082).
                read_timeouts = 0

                # Progress update
                if on_progress:
                    progress = ((chunk_idx + 1) / total_chunks) * 100
                    await on_progress(track_id, progress, f"Streamed chunk {chunk_idx + 1}")

            except Exception as chunk_error:
                # Drain the cancelled look-ahead so the next iteration
                # doesn't trip on its CancelledError (#3493).
                await controller._drain_cancelled_task(lookahead_read)
                lookahead_read = None
                logger.error(f"Failed to stream chunk {chunk_idx}: {chunk_error}", exc_info=True)
                # Recovery position: start of the failed chunk (issue #2085)
                normal_recovery_position: float = chunk_idx * chunk_duration
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Failed to stream audio chunk {chunk_idx}",
                    recovery_position=normal_recovery_position,
                )
                # Skip failed chunk and continue with remaining chunks (#3190).
                # Recorded so the terminal message doesn't claim
                # reason="completed" over a stream with gaps (#4790).
                failed_chunks.append(chunk_idx)
                # ...unless the storage itself is gone (#5082): continuing then
                # just strands another executor thread per chunk and delays the
                # permit release by CHUNK_PROCESS_TIMEOUT each time. Stop and
                # let the client retry.
                if read_timeouts >= MAX_CONSECUTIVE_READ_TIMEOUTS:
                    logger.error(
                        f"Normal audio stream aborting: {read_timeouts} consecutive disk-read "
                        f"timeouts (track {track_id}, chunk {chunk_idx}) — backing file "
                        f"{streaming_filepath} appears unreachable"
                    )
                    # Deliberately NOT stopped_early: that reports
                    # reason="stopped", which #4790 reserves for a clean
                    # client-driven exit. failed_chunks is non-empty here, so
                    # falling out of the loop lands on the reason="errored"
                    # branch — the accurate one for a server-side abort.
                    break
                continue

        if stopped_early:
            delivered_duration = delivered_samples / sample_rate
            logger.info(
                f"Normal audio stream stopped early: track={track_id}, "
                f"delivered={delivered_duration:.2f}s"
            )
            await controller._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=delivered_samples,
                duration=delivered_duration,
                reason="stopped",
            )
        elif failed_chunks:
            delivered_duration = delivered_samples / sample_rate
            logger.info(
                f"Normal audio stream degraded: track={track_id}, "
                f"{len(failed_chunks)} chunk(s) failed ({failed_chunks}), "
                f"delivered={delivered_duration:.2f}s"
            )
            await controller._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=delivered_samples,
                duration=delivered_duration,
                reason="errored",
            )
        else:
            logger.info(f"Normal audio stream complete: track={track_id}")
            await controller._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=total_frames,
                duration=duration,
                reason="completed",
            )

    except WebSocketDisconnect:
        # Client closed the WebSocket — normal exit (#3511 / BE-NEW-53).
        logger.info(f"Normal audio streaming stopped: client disconnected")
    except Exception as e:
        logger.error(f"Normal audio streaming failed: {e}", exc_info=True)
        # Only try to send error if WebSocket is still connected
        if controller._is_websocket_connected(websocket):
            await controller._send_error(websocket, track_id, "Audio streaming failed")
    finally:
        # Drain any in-flight look-ahead read task (fixes #3493).
        await controller._drain_cancelled_task(lookahead_read)
        controller._stream_semaphore.release()
        # Clean up temp WAV created for compressed format streaming (#3225).
        # Clean up the directory, not the WAV path (#4365). convert_to_temp_wav
        # removes its own directory if the decode/write fails, so reaching here
        # with temp_dir set means the conversion succeeded and this is the only
        # owner left (#4737).
        # Log on failure instead of swallowing it (#3877): an EBUSY/EACCES
        # holdout is swept and counted at next startup (config/startup.py).
        if temp_dir:
            # Offloaded via asyncio.to_thread (#4754) — temp_dir holds a
            # full decoded WAV (can be hundreds of MB), and this ran
            # directly on the event loop for every compressed-format
            # normal stream.
            try:
                await asyncio.to_thread(
                    shutil.rmtree,
                    temp_dir,
                    onexc=lambda _func, path, exc: logger.warning(
                        f"Failed to remove temp stream file {path}: {exc}"
                    ),
                )
            except Exception as cleanup_error:
                logger.warning(
                    f"Temp stream cleanup failed for {temp_dir}: {cleanup_error}"
                )
