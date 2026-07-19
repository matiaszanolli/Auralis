#!/usr/bin/env python3

"""
Enhanced Audio Streaming
~~~~~~~~~~~~~~~~~~~~~~~~

The stream_enhanced_audio entry point: streams DSP-processed (mastered)
audio chunks to a client via WebSocket, with look-ahead processing,
chunk-boundary crossfading, and per-chunk error recovery.

Extracted from audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from pathlib import Path  # noqa: F401 — kept for module-attribute patching in tests (core.stream_enhanced.Path)
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

import numpy as np
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc
from .chunk_cache import SimpleChunkCache
from security.path_security import PathValidationError, validate_file_path

if TYPE_CHECKING:
    from .chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger(__name__)


async def stream_enhanced_audio(
    controller: '_asc.AudioStreamController',
    track_id: int,
    preset: str,
    intensity: float,
    websocket: WebSocket,
    on_progress: Callable[[int, float, str], Any] | None = None
) -> None:
    """
    Stream enhanced audio chunks to client via WebSocket.

    Args:
        controller: AudioStreamController instance
        track_id: Track ID to process and stream
        preset: Processing preset (adaptive, gentle, warm, etc.)
        intensity: Processing intensity (0.0-1.0)
        websocket: WebSocket connection to client
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
        await asyncio.wait_for(controller._stream_semaphore.acquire(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning(
            f"Stream limit ({_asc.MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
        )
        await controller._send_error(websocket, track_id, "Server busy - too many active streams")
        return

    # Declare look-ahead task early so the outer `finally:` can drain it
    # even if an exception fires before the streaming loop initialises it
    # (fixes #3493 unbound-var hazard).
    lookahead_task: asyncio.Task[tuple[np.ndarray, int]] | None = None

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
                    await asyncio.to_thread(validate_file_path, str(track.filepath))
                )
            except PathValidationError as e:
                logger.warning(f"Track {track_id} filepath failed validation: {e}")
                await controller._send_error(
                    websocket, track_id, "Audio file not found"
                )
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}", exc_info=True)
            await controller._send_error(websocket, track_id, "Failed to load track")
            return

        # Create processor for this track with timeout (#2125)
        try:
            processor: 'ChunkedAudioProcessor' = await asyncio.wait_for(
                asyncio.to_thread(
                    controller.chunked_processor_class,
                    track_id=track_id,
                    filepath=validated_filepath,
                    preset=preset,
                    intensity=intensity,
                ),
                timeout=_asc.CHUNK_PROCESS_TIMEOUT,
            )
        except TimeoutError:
            error_msg = "Audio processor initialization timed out. File may be corrupt or on slow storage."
            logger.error(f"Processor instantiation timed out for track {track_id} (30s)")
            await controller._send_error(websocket, track_id, error_msg)
            return

        # Ensure processor has loaded metadata (raise instead of assert
        # so guards work under python -O / PyInstaller, fixes #2735)
        for _attr in ('total_chunks', 'sample_rate', 'channels', 'duration'):
            if getattr(processor, _attr) is None:
                raise ValueError(f"Processor metadata missing: {_attr} is None")


        # Phase 7.5: Non-blocking fingerprint check
        # Check if fingerprint exists in cache - if not, queue for background generation
        # Don't wait for generation - start streaming immediately with standard mastering
        fingerprint_available = await controller._check_or_queue_fingerprint(
            track_id=track_id,
            filepath=str(track.filepath),
            websocket=websocket
        )
        if fingerprint_available:
            logger.info(f"🎯 Adaptive mastering will use fingerprint-optimized parameters (cached)")
        else:
            logger.info(f"📊 Streaming with standard adaptive mastering (fingerprint queued for background generation)")

        logger.info(
            f"Starting audio stream: track={track_id}, preset={preset}, "
            f"intensity={intensity}, chunks={processor.total_chunks}"
        )

        # Send stream start message with metadata
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
        ):
            logger.info(f"WebSocket disconnected, cannot start stream")
            return

        # Process and stream chunks with look-ahead: start processing
        # chunk N+1 while streaming chunk N to eliminate inter-chunk gaps.
        # (`lookahead_task` is declared earlier so the outer `finally:`
        # can drain it even on early-exit paths.)

        for chunk_idx in range(processor.total_chunks):
            # Stop streaming if enhancement was toggled off mid-stream (fixes #2866).
            if controller._get_enhancement_enabled and not controller._get_enhancement_enabled():
                logger.info(
                    f"Enhancement disabled mid-stream, stopping enhanced stream for track {track_id}"
                )
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                break

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
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                break

            try:
                # Get processed chunk: from look-ahead task or process now
                if lookahead_task is not None:
                    try:
                        pcm_samples, _sr = await lookahead_task
                    except ConnectionError:
                        # Client disconnected during look-ahead processing
                        break
                    lookahead_task = None
                else:
                    pcm_samples, _sr = await controller._process_chunk_only(chunk_idx, processor, websocket)

                # Start look-ahead: process next chunk while we stream current one
                if chunk_idx + 1 < processor.total_chunks:
                    lookahead_task = asyncio.create_task(
                        controller._process_chunk_only(chunk_idx + 1, processor, websocket)
                    )

                # Stream current chunk (crossfade + send)
                await controller._stream_processed_chunk(pcm_samples, chunk_idx, processor, websocket)

                # Progress update
                progress = ((chunk_idx + 1) / processor.total_chunks) * 100
                if on_progress:
                    await on_progress(track_id, progress, f"Processed chunk {chunk_idx + 1}")

                # Pre-fetch was disabled in #3513 / BE-NEW-55: it populated a
                # per-stream cache (system.py creates one fresh per
                # play_enhanced) that nothing else reads. Re-enable once the
                # cache manager is hoisted to a process-wide singleton.

            except ConnectionError:
                # Client disconnected — clean exit
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                break

            except Exception as chunk_error:
                # Cancel look-ahead task on error AND drain it so the
                # CancelledError that would otherwise be raised by the
                # next iteration's `await lookahead_task` doesn't escape
                # `except Exception` and kill the stream (fixes #3493 /
                # the #3190 recovery loop).
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                logger.error(
                    f"Failed to process chunk {chunk_idx}: {chunk_error}",
                    exc_info=True
                )
                # Compute recovery position: start of the failed chunk (issue #2085)
                recovery_position: float = chunk_idx * processor.chunk_interval
                # Evict any stale cache entry for the failed chunk so a retry
                # processes it fresh rather than replaying corrupt data (issue #2085)
                if isinstance(controller.cache_manager, SimpleChunkCache):
                    controller.cache_manager.invalidate_chunk(
                        track_id=track_id,
                        chunk_idx=chunk_idx,
                        preset=preset,
                        intensity=intensity,
                        file_signature=processor.file_signature,  # #4358
                    )
                # Proactively remove crossfade tail so the next chunk
                # starts clean (lock-protected per #3527).
                await controller._drop_chunk_tail(track_id)
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Failed to process audio chunk {chunk_idx}",
                    recovery_position=recovery_position,
                )
                # Skip failed chunk and continue with remaining chunks (#3190)
                continue

        # Stream complete
        logger.info(f"Audio stream complete: track={track_id}")
        # Both are guaranteed non-None due to assertions above
        await controller._send_stream_end(
            websocket,
            track_id=track_id,
            total_samples=int(processor.duration * processor.sample_rate),
            duration=processor.duration,
        )

    except WebSocketDisconnect:
        # Client closed the WebSocket — normal exit (#3511 / BE-NEW-53;
        # prior code matched on \"close message\" inside the exception
        # string which depended on Starlette internals).
        logger.info(f"Audio streaming stopped: client disconnected")
    except Exception as e:
        logger.error(f"Audio streaming failed: {e}", exc_info=True)
        # Only try to send error if WebSocket is still connected
        if controller._is_websocket_connected(websocket):
            await controller._send_error(websocket, track_id, "Audio streaming failed")
    finally:
        # Clean up chunk tail storage for this track (under lock, #3527)
        await controller._drop_chunk_tail(track_id)
        # Drain any in-flight look-ahead task that survived the loop —
        # otherwise the orphan keeps running and holds a HybridProcessor
        # reference past stream teardown (fixes #3493).
        await controller._drain_cancelled_task(lookahead_task)
        controller._stream_semaphore.release()
