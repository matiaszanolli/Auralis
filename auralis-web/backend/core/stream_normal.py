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
import logging
import shutil
from pathlib import Path
from typing import Any
from collections.abc import Callable

import soundfile as sf
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc
from .stream_normal_chunks import pump_normal_chunks
from .stream_track_resolution import resolve_and_validate_track
from security.path_security import validate_file_path

logger = logging.getLogger(__name__)

# Re-exported from stream_normal_chunks, which owns the read loop it bounds
# (#5032/#5082).
from .stream_normal_chunks import MAX_CONSECUTIVE_READ_TIMEOUTS  # noqa: E402,F401


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

    # stopped_early / failed_chunks / delivered_samples now come back from
    # pump_normal_chunks (#5032); the look-ahead task and the consecutive-read-
    # timeout counter moved with the loop that owns them.

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
        # Get track from library and validate its filepath (#5032: shared
        # with stream_enhanced.py/stream_seek.py — see stream_track_resolution.py).
        resolved = await resolve_and_validate_track(
            controller, track_id, websocket, validate_file_path=validate_file_path
        )
        if resolved is None:
            return
        _track, validated_filepath = resolved

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

        # Calculate chunks (NO overlap for normal streaming - no crossfade
        # applied). #3775: pulls CHUNK_DURATION from chunk_boundaries instead
        # of re-declaring it. #5032: the plan math itself (chunk sizing, seek
        # chunk/offset/trim) is shared via normal_stream_plan() so it is
        # unit-testable without file I/O.
        from .chunk_boundaries import normal_stream_plan
        plan = normal_stream_plan(total_frames, sample_rate, start_position)
        duration = plan.duration
        chunk_duration = plan.chunk_duration
        chunk_samples = plan.chunk_samples
        interval_samples = plan.interval_samples
        total_chunks = plan.total_chunks
        start_chunk = plan.start_chunk

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
        seek_offset = plan.seek_offset
        first_chunk_trim_samples = plan.first_chunk_trim_samples
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
            # #4431: full track duration, not duration remaining from the
            # seek point — matches stream_enhanced.py/stream_seek.py's
            # `total_duration=processor.duration` convention (and this same
            # function's own `total_chunks`, which is already the full,
            # seek-stable count per #3768 immediately above). The FE only
            # ever read this field inside a DEBUG console.log, never stored
            # it, so this was latent drift rather than an observed bug.
            total_duration=duration,
            **seek_kwargs,
        ):
            logger.info(f"WebSocket disconnected, cannot start stream")
            return

        # The read/send loop lives in stream_normal_chunks (#5032); what stays
        # here is the semaphore/cancel/finally skeleton that supervises it.
        pump = await pump_normal_chunks(
            controller,
            websocket,
            track_id=track_id,
            streaming_filepath=streaming_filepath,
            start_chunk=start_chunk,
            total_chunks=total_chunks,
            interval_samples=interval_samples,
            chunk_samples=chunk_samples,
            first_chunk_trim_samples=first_chunk_trim_samples,
            chunk_duration=chunk_duration,
            start_position=start_position,
            on_progress=on_progress,
        )
        stopped_early = pump.stopped_early
        failed_chunks = pump.failed_chunks
        delivered_samples = pump.delivered_samples

        # Report whether the loop ran to completion and what was actually
        # delivered — shared with stream_enhanced.py/stream_seek.py (#5032),
        # see stream_messages.send_stream_completion for the reason= rules.
        await controller._send_stream_completion(
            websocket,
            track_id=track_id,
            label="Normal audio stream",
            stopped_early=stopped_early,
            failed_chunks=failed_chunks,
            delivered_samples=delivered_samples,
            sample_rate=sample_rate,
            full_duration=duration,
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
        # The look-ahead drain that used to sit here moved into
        # pump_normal_chunks' own finally (#3493 still holds — the task cannot
        # outlive that function).
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
