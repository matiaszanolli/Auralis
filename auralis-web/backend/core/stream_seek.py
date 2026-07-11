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
from pathlib import Path
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

import numpy as np
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc

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
        await asyncio.wait_for(controller._stream_semaphore.acquire(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning(
            f"Stream limit ({_asc.MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
        )
        await controller._send_error(websocket, track_id, "Server busy - too many active streams")
        return
    # Declare look-ahead task early so the outer `finally:` can drain it
    # even on early-exit paths (fixes #3493 unbound-var hazard).
    lookahead_task: asyncio.Task[tuple[np.ndarray, int]] | None = None

    # Get track from library
    try:
        factory = controller._get_repository_factory()
        track = await asyncio.to_thread(factory.tracks.get_by_id, track_id)
        if not track:
            await controller._send_error(websocket, track_id, "Track not found")
            controller._stream_semaphore.release()
            return

        if not Path(track.filepath).exists():
            await controller._send_error(
                websocket, track_id, "Audio file not found"
            )
            controller._stream_semaphore.release()
            return
    except Exception as e:
        logger.error(f"Failed to load track {track_id}: {e}", exc_info=True)
        await controller._send_error(websocket, track_id, "Failed to load track")
        controller._stream_semaphore.release()
        return

    try:
        # Create processor for this track with timeout (#2125)
        try:
            processor: 'ChunkedAudioProcessor' = await asyncio.wait_for(
                asyncio.to_thread(
                    controller.chunked_processor_class,
                    track_id=track_id,
                    filepath=str(track.filepath),
                    preset=preset,
                    intensity=intensity,
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

        # Register active stream so cleanup can always find it (fixes #2076, #3182)
        async with controller._active_streams_lock:
            controller.active_streams[_asc.ws_id(websocket)] = asyncio.current_task()

        # Calculate which chunk to start from based on position
        # Chunks overlap, so we need to find the chunk that contains this position
        chunk_interval = processor.chunk_interval
        start_chunk_idx = int(start_position / chunk_interval)
        start_chunk_idx = max(0, min(start_chunk_idx, processor.total_chunks - 1))

        # Calculate the offset within the chunk (for precise seeking)
        chunk_start_time = start_chunk_idx * chunk_interval
        seek_offset = start_position - chunk_start_time

        logger.info(
            f"Seek: position={start_position}s → chunk {start_chunk_idx}/{processor.total_chunks}, "
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
            seek_position=start_position,
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
                break

            try:
                # Get processed chunk: from look-ahead task or process now
                if lookahead_task is not None:
                    try:
                        pcm_samples, _sr = await lookahead_task
                    except ConnectionError:
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

                # Stream current chunk (crossfade + send)
                await controller._stream_processed_chunk(pcm_samples, chunk_idx, processor, websocket)

                # Progress update
                if on_progress:
                    chunks_remaining = processor.total_chunks - start_chunk_idx
                    chunks_done = chunk_idx - start_chunk_idx + 1
                    progress = (chunks_done / chunks_remaining) * 100
                    await on_progress(track_id, progress, f"Processed chunk {chunk_idx + 1}")

            except ConnectionError:
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
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
                if chunk_idx == start_chunk_idx:
                    recovery_position = start_position
                else:
                    recovery_position = chunk_idx * chunk_interval
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Failed to process audio chunk {chunk_idx}",
                    recovery_position=recovery_position,
                )
                # Skip failed chunk and continue (#3190)
                continue

        # Stream complete
        logger.info(f"Seek stream complete: track={track_id}")
        await controller._send_stream_end(
            websocket,
            track_id=track_id,
            total_samples=int(processor.duration * processor.sample_rate),
            duration=processor.duration,
        )

    except WebSocketDisconnect:
        # Client closed the WebSocket — normal exit (#3511 / BE-NEW-53).
        logger.info(f"Seek streaming stopped: client disconnected")
    except Exception as e:
        logger.error(f"Seek streaming failed: {e}", exc_info=True)
        if controller._is_websocket_connected(websocket):
            await controller._send_error(websocket, track_id, "Audio streaming failed")
    finally:
        await controller._drop_chunk_tail(track_id)  # under lock, #3527
        # Drain any in-flight look-ahead (fixes #3493).
        await controller._drain_cancelled_task(lookahead_task)
        async with controller._active_streams_lock:  # fixes #2076, #3182
            controller.active_streams.pop(_asc.ws_id(websocket), None)
        controller._stream_semaphore.release()
