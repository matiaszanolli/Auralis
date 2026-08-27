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

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc
from .chunk_boundaries import (
    SEEK_MIN_CHUNK_REMAINDER,
    chunk_for_position,
)
from .stream_seek_chunks import pump_seek_chunks
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
    # The look-ahead task moved into pump_seek_chunks with the loop that owns
    # it (#5032); #3493's drain now lives in that function's own finally.
    #
    # `processor` still needs the unbound-var guard here, for the same reason
    # lookahead_task used to:
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
        if processor is None:
            raise ValueError("Audio processor initialization returned None")
        if processor.total_chunks is None:
            raise ValueError("Processor metadata missing: total_chunks is None")
        if processor.sample_rate is None:
            raise ValueError("Processor metadata missing: sample_rate is None")
        if processor.channels is None:
            raise ValueError("Processor metadata missing: channels is None")
        if processor.duration is None:
            raise ValueError("Processor metadata missing: duration is None")


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
            start_position,
            processor.total_chunks,
            total_duration=processor.duration,
        )

        if start_position >= processor.duration:
            logger.info(
                f"Seek: requested {start_position:.2f}s is at/past the "
                f"{processor.duration:.2f}s track end; clamping to "
                f"{effective_position:.2f}s so audible audio is delivered"
            )
        elif effective_position != start_position:
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

        # The process/send loop lives in stream_seek_chunks (#5032); what stays
        # here is the semaphore/cancel/finally skeleton around it.
        pump = await pump_seek_chunks(
            controller,
            websocket,
            track_id=track_id,
            processor=processor,
            start_chunk_idx=start_chunk_idx,
            seek_offset=seek_offset,
            effective_position=effective_position,
            on_progress=on_progress,
        )
        stopped_early = pump.stopped_early
        failed_chunks = pump.failed_chunks
        delivered_samples = pump.delivered_samples

        # Distinguish a truncated seek stream from a completed one and report
        # what was actually delivered — shared with stream_normal.py/
        # stream_enhanced.py (#5032), see stream_messages.send_stream_completion
        # for the reason= rules (#4659/#4790).
        await controller._send_stream_completion(
            websocket,
            track_id=track_id,
            label="Seek stream",
            stopped_early=stopped_early,
            failed_chunks=failed_chunks,
            delivered_samples=delivered_samples,
            sample_rate=processor.sample_rate,
            full_duration=processor.duration,
        )

    except WebSocketDisconnect:
        # Client closed the WebSocket — normal exit (#3511 / BE-NEW-53).
        logger.info(f"Seek streaming stopped: client disconnected")
    except Exception as e:
        logger.error(f"Seek streaming failed: {e}", exc_info=True)
        if controller._is_websocket_connected(websocket):
            await controller._send_error(
                websocket, track_id, "Audio streaming failed", error_code="SEEK_ERROR"
            )
    finally:
        # The look-ahead drain that used to sit here moved into
        # pump_seek_chunks' own finally (#3493 still holds — the task cannot
        # outlive that function).
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
