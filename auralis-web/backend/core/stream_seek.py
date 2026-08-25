#!/usr/bin/env python3

"""
Enhanced Audio Streaming From Position (Seek)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The stream_enhanced_audio_from_position entry point: like stream_enhanced,
but starts from an arbitrary mid-track position with precise sample-level
trim of the first chunk.

Extracted from audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import threading
from pathlib import Path  # noqa: F401 — kept for module-attribute patching in tests (core.stream_seek.Path)
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

import numpy as np
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc
from .chunk_boundaries import (
    SEEK_MIN_CHUNK_REMAINDER,
    chunk_for_position,
    emitted_chunk_start,
)
from .stream_track_resolution import resolve_and_validate_track
from security.path_security import validate_file_path

if TYPE_CHECKING:
    from .chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger(__name__)


async def stream_enhanced_audio_from_position(
    controller: '_asc.AudioStreamController',
    track_id: int,
    preset: str,
    intensity: float,
    websocket: WebSocket,
    start_position: float,
    on_progress: Callable[[int, float, str], Any] | None = None
) -> None:
    """
    Stream enhanced audio chunks starting from a specific position (seek).

    This method is used for seeking - it starts streaming from the chunk
    containing the target position, with an offset applied for precise seeking.

    Args:
        controller: AudioStreamController instance
        track_id: Track ID to process and stream
        preset: Processing preset (adaptive, gentle, warm, etc.)
        intensity: Processing intensity (0.0-1.0)
        websocket: WebSocket connection to client
        start_position: Position in seconds to start streaming from
        on_progress: Optional callback for progress updates

    Raises:
        ValueError: If track not found or processor unavailable
        Exception: If processing or streaming fails
    """
    _asc._stream_type_var.set("enhanced")  # per-task; safe for concurrent coroutines (fixes #2493)

    if not controller.chunked_processor_class:
        raise ValueError("ChunkedProcessor not available")

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
    lookahead_task: asyncio.Task[tuple[np.ndarray, int]] | None = None
    # Same unbound-var hazard as lookahead_task above, for the same reason:
    # the outer `finally:` below must be able to release this processor's
    # temp WAV (SeekableSource, #4737) even when construction itself timed
    # out or an earlier step raised before `processor` was ever assigned
    # (#5253 — a leaked temp WAV per seek of a non-natively-seekable format,
    # since nothing here used to call .close() at all).
    processor: 'ChunkedAudioProcessor | None' = None

    # Cooperative-cancel signal for in-flight chunk DSP (#4815) — same
    # mechanism as stream_enhanced.py, see its comment for the full
    # rationale. Registered before track lookup/processor construction so
    # _cancel_prior_task can find and set() it for this task's whole
    # lifetime.
    from routers.system import _stream_chunk_cancel_events
    chunk_cancel_event = threading.Event()
    _stream_chunk_cancel_events[_asc.ws_id(websocket)] = chunk_cancel_event

    # Same early-exit accounting as the non-seek path (#4659): a stream stopped
    # by a mid-stream enhancement toggle must not report the full track length.
    stopped_early: bool = False
    delivered_samples: int = 0
    # Chunk indices skipped via the #3190 continue-and-keep-going recovery
    # path (#4790) — see stream_enhanced.py's identical field for the full
    # rationale: the loop can run to its natural end with gaps in the
    # delivered audio without stopped_early ever being set.
    failed_chunks: list[int] = []

    # A single try/finally from here guards the semaphore permit acquired above:
    # it is released exactly once in the finally at the end. The track lookup
    # lives INSIDE this try so a task cancellation (CancelledError — a
    # BaseException that `except Exception` does not catch) during the awaited
    # get_by_id cannot escape before the permit is released, which would leak a
    # permit permanently for the process lifetime (#4329).
    try:
        # Get track from library and validate its filepath (#5032: shared
        # with stream_normal.py/stream_enhanced.py — see stream_track_resolution.py).
        resolved = await resolve_and_validate_track(
            controller, track_id, websocket, validate_file_path=validate_file_path
        )
        if resolved is None:
            return
        _track, validated_filepath = resolved

        # Create processor for this track with timeout (#2125)
        try:
            processor = await asyncio.wait_for(
                asyncio.to_thread(
                    controller.chunked_processor_class,
                    track_id=track_id,
                    filepath=validated_filepath,
                    preset=preset,
                    intensity=intensity,
                    cancel_event=chunk_cancel_event,
                ),
                timeout=_asc.CHUNK_PROCESS_TIMEOUT,
            )
        except TimeoutError:
            error_msg = "Audio processor initialization timed out during seek. File may be corrupt or on slow storage."
            logger.error(f"Processor instantiation timed out for track {track_id} during seek (30s)")
            await controller._send_error(websocket, track_id, error_msg, error_code="SEEK_ERROR")
            return

        # Ensure processor has loaded metadata (raise instead of assert
        # so guards work under python -O / PyInstaller, fixes #2735)
        for _attr in ('total_chunks', 'sample_rate', 'channels', 'duration'):
            if getattr(processor, _attr) is None:
                raise ValueError(f"Processor metadata missing: {_attr} is None")


        # Map the requested position onto the chunk that actually EMITS it
        # (#4557). This used to be `int(start_position / chunk_interval)` with
        # `seek_offset = start_position - idx * chunk_interval`, which maps onto
        # the chunk *core* timeline — but the buffer the offset is trimmed from
        # has already had OVERLAP_DURATION skipped by
        # ChunkOperations.extract_chunk_segment, so every seek to >= 10s landed
        # exactly 5s past the requested point and the transport read 5s ahead of
        # the audio for the rest of the stream.
        #
        # chunk_for_position derives both values from the same constants the
        # extraction uses, and may advance to the next chunk when the requested
        # point falls within a sliver of its chunk's end — hence
        # effective_position, which is what the client must be told.
        start_chunk_idx, seek_offset, effective_position = chunk_for_position(
            start_position, processor.total_chunks
        )

        if effective_position != start_position:
            logger.info(
                f"Seek: requested {start_position:.2f}s falls within "
                f"{SEEK_MIN_CHUNK_REMAINDER}s of chunk {start_chunk_idx - 1}'s end; "
                f"advancing to chunk {start_chunk_idx} at {effective_position:.2f}s"
            )

        logger.info(
            f"Seek: position={effective_position}s → chunk {start_chunk_idx}/{processor.total_chunks}, "
            f"offset={seek_offset:.2f}s"
        )

        # Check if WebSocket disconnected
        if not controller._is_websocket_connected(websocket):
            logger.info(f"WebSocket disconnected, aborting seek stream")
            return

        # Send stream start message with seek info
        if not await controller._send_stream_start(
            websocket,
            track_id=track_id,
            preset=preset,
            intensity=intensity,
            sample_rate=processor.sample_rate,
            channels=processor.channels,
            total_chunks=processor.total_chunks,
            chunk_duration=processor.chunk_duration,
            total_duration=processor.duration,
            start_chunk=start_chunk_idx,
            # #4557: the source time of the first sample we will actually
            # deliver, which is what the client sets its position counter from
            # (useEnhancedStreamStart.ts). Reporting the raw request here is
            # what let the readout drift away from the audio.
            seek_position=effective_position,
            seek_offset=seek_offset,
        ):
            logger.info(f"WebSocket disconnected, cannot start seek stream")
            return

        # Process and stream chunks with look-ahead (same pattern as
        # normal streaming): process chunk N+1 while streaming chunk N
        # to eliminate inter-chunk gaps on slow storage.
        # (`lookahead_task` is declared at function scope so the outer
        # `finally:` can drain it on every exit path — fixes #3493.)

        for chunk_idx in range(start_chunk_idx, processor.total_chunks):
            # Stop streaming if enhancement was toggled off mid-stream (fixes #2866).
            if controller._get_enhancement_enabled and not controller._get_enhancement_enabled():
                logger.info(
                    f"Enhancement disabled mid-stream, stopping seek stream for track {track_id}"
                )
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                stopped_early = True
                break

            # Honour pause/resume and flow control events (fixes missing
            # pause check in seek path — pre-existing bug).
            from routers.system import _stream_pause_events, _stream_flow_events
            pause_evt = _stream_pause_events.get(_asc.ws_id(websocket))
            if pause_evt is not None:
                await pause_evt.wait()
            flow_evt = _stream_flow_events.get(_asc.ws_id(websocket))
            if flow_evt is not None:
                await flow_evt.wait()

            if not controller._is_websocket_connected(websocket):
                logger.info(f"WebSocket disconnected, stopping seek stream")
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                stopped_early = True
                break

            try:
                # Get processed chunk: from look-ahead task or process now
                if lookahead_task is not None:
                    try:
                        pcm_samples, _sr = await lookahead_task
                    except ConnectionError:
                        stopped_early = True
                        break
                    lookahead_task = None
                else:
                    pcm_samples, _sr = await controller._process_chunk_only(chunk_idx, processor, websocket)

                # Trim the first chunk to the exact seek position
                if chunk_idx == start_chunk_idx and seek_offset > 0:
                    trim_samples = round(seek_offset * processor.sample_rate)
                    pcm_samples = pcm_samples[trim_samples:]
                    logger.debug(
                        f"Seek trim: removed {trim_samples} samples "
                        f"({seek_offset:.2f}s) from chunk {chunk_idx}"
                    )

                # Start look-ahead: process next chunk while we stream current one
                if chunk_idx + 1 < processor.total_chunks:
                    lookahead_task = asyncio.create_task(
                        controller._process_chunk_only(chunk_idx + 1, processor, websocket)
                    )

                # Stream current chunk
                delivered = await controller._stream_processed_chunk(
                    pcm_samples, chunk_idx, processor, websocket
                )
                if not delivered:
                    await controller._drain_cancelled_task(lookahead_task)
                    lookahead_task = None
                    recovery_position = (
                        effective_position
                        if chunk_idx == start_chunk_idx
                        else emitted_chunk_start(chunk_idx)
                    )
                    await controller._send_error(
                        websocket,
                        track_id,
                        f"Failed to send audio chunk {chunk_idx}",
                        recovery_position=recovery_position,
                    )
                    stopped_early = True
                    break
                delivered_samples += int(pcm_samples.shape[0])

                # Progress update
                if on_progress:
                    chunks_remaining = processor.total_chunks - start_chunk_idx
                    chunks_done = chunk_idx - start_chunk_idx + 1
                    progress = (chunks_done / chunks_remaining) * 100
                    await on_progress(track_id, progress, f"Processed chunk {chunk_idx + 1}")

            except ConnectionError:
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                stopped_early = True
                break

            except TimeoutError:
                # #4999/#5074: a chunk DSP timeout (stream_chunk_ops.CHUNK_PROCESS_TIMEOUT)
                # means asyncio.wait_for gave up on the wrapper future, but the
                # underlying OS thread may still be running inside
                # processor.process_chunk_safe() — holding `processor`'s
                # threading.RLock (_processor_lock) for however long the hung
                # DSP call takes, unbounded. Unlike a plain processing error
                # (#3190's skip-and-continue), the #3190 recovery path is unsafe
                # here: the NEXT chunk's process_chunk_safe() call would block
                # trying to acquire that same still-held lock, itself time out
                # 30s later, and so on — cascading every remaining chunk into a
                # serial pileup of timeouts instead of one clean failure.
                # `processor` (this stream's ChunkedAudioProcessor, analogous to
                # #4727's pooled HybridProcessor) must never be touched again —
                # end the stream rather than continuing to reuse it. Lifted from
                # stream_enhanced.py's #4999 fix, which never reached this
                # structurally identical seek-path loop (#5074).
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                logger.error(
                    f"Chunk {chunk_idx} DSP timed out for track {track_id}; "
                    f"ending seek stream rather than reusing a processor an "
                    f"orphaned thread may still be running inside"
                )
                recovery_position = (
                    effective_position
                    if chunk_idx == start_chunk_idx
                    else emitted_chunk_start(chunk_idx)
                )
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Audio processing timed out on chunk {chunk_idx}; stream stopped",
                    recovery_position=recovery_position,
                )
                stopped_early = True
                break

            except Exception as chunk_error:
                # Drain the cancelled look-ahead (#3493) so the next
                # iteration doesn't trip on its CancelledError.
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                logger.error(
                    f"Failed to process chunk {chunk_idx}: {chunk_error}",
                    exc_info=True
                )
                # Seek-path recovery preserves the user's exact target
                # for the first chunk; chunk-start otherwise (#3493 / BE-NEW-67).
                # #4557: "chunk start" is the EMITTED start, not
                # chunk_idx * chunk_interval — resuming at the core start would
                # replay OVERLAP_DURATION of already-delivered audio.
                if chunk_idx == start_chunk_idx:
                    recovery_position = effective_position
                else:
                    recovery_position = emitted_chunk_start(chunk_idx)
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Failed to process audio chunk {chunk_idx}",
                    recovery_position=recovery_position,
                )
                # Skip failed chunk and continue (#3190). Recorded so the
                # terminal message doesn't claim reason="completed" over a
                # stream with gaps (#4790).
                failed_chunks.append(chunk_idx)
                continue

        # Stream finished — distinguish a truncated seek stream from a
        # completed one and report what was actually delivered (#4659). A
        # stream that ran to the end but skipped one or more failed chunks
        # (#3190) is neither: it didn't stop early, but it also didn't
        # deliver the whole seek range, so reason="completed" with the full
        # track's sample count would be a lie (#4790).
        if stopped_early:
            _sample_rate = processor.sample_rate or 0
            _delivered_duration = delivered_samples / _sample_rate if _sample_rate else 0.0
            logger.info(
                f"Seek stream stopped early: track={track_id}, "
                f"delivered={_delivered_duration:.2f}s"
            )
            await controller._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=delivered_samples,
                duration=_delivered_duration,
                reason="stopped",
            )
        elif failed_chunks:
            _sample_rate = processor.sample_rate or 0
            _delivered_duration = delivered_samples / _sample_rate if _sample_rate else 0.0
            logger.info(
                f"Seek stream degraded: track={track_id}, "
                f"{len(failed_chunks)} chunk(s) failed ({failed_chunks}), "
                f"delivered={_delivered_duration:.2f}s"
            )
            await controller._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=delivered_samples,
                duration=_delivered_duration,
                reason="errored",
            )
        else:
            logger.info(f"Seek stream complete: track={track_id}")
            await controller._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=int(processor.duration * processor.sample_rate),
                duration=processor.duration,
                reason="completed",
            )

    except WebSocketDisconnect:
        # Client closed the WebSocket — normal exit (#3511 / BE-NEW-53).
        logger.info(f"Seek streaming stopped: client disconnected")
    except Exception as e:
        logger.error(f"Seek streaming failed: {e}", exc_info=True)
        if controller._is_websocket_connected(websocket):
            await controller._send_error(websocket, track_id, "Audio streaming failed")
    finally:
        # Drain any in-flight look-ahead (fixes #3493).
        await controller._drain_cancelled_task(lookahead_task)
        controller._stream_semaphore.release()
        # #5253: release the temp WAV this processor may own (SeekableSource,
        # #4737) — a non-natively-seekable format (m4a/aac/wma) converts once
        # per ChunkedAudioProcessor instance, and since a new instance is
        # constructed per seek, nothing ever reclaimed it before this fix.
        # Never self.processor — that's the *shared* HybridProcessor owned by
        # ProcessorFactory's own lifecycle (see ChunkedAudioProcessor.close()).
        if processor is not None:
            await asyncio.to_thread(processor.close)
        # #4815: only remove OUR OWN registration — a reissued stream on the
        # same ws_id may already have registered its own event by the time
        # this (cancelled) task's finally runs.
        _ws_id_key = _asc.ws_id(websocket)
        if _stream_chunk_cancel_events.get(_ws_id_key) is chunk_cancel_event:
            _stream_chunk_cancel_events.pop(_ws_id_key, None)
