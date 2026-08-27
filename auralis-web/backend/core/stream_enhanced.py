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
import threading
from pathlib import Path  # noqa: F401 — kept for module-attribute patching in tests (core.stream_enhanced.Path)
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc
from .stream_enhanced_chunks import pump_enhanced_chunks
from .proactive_buffer import buffer_presets_for_track
from .stream_track_resolution import resolve_and_validate_track
from helpers import spawn_background_task
from security.path_security import validate_file_path

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

    # The look-ahead task moved into pump_enhanced_chunks with the loop that
    # owns it (#5032); #3493's drain now lives in that function's own finally.
    #
    # `processor` still needs the unbound-var guard here, for the same reason
    # lookahead_task used to:
    # the outer `finally:` below must be able to release this processor's
    # temp WAV (SeekableSource, #4737) even when construction itself timed
    # out or an earlier step raised before `processor` was ever assigned
    # (#5253 — a leaked temp WAV per seek/play of a non-natively-seekable
    # format, since nothing here used to call .close() at all).
    processor: 'ChunkedAudioProcessor | None' = None

    # Cooperative-cancel signal for in-flight chunk DSP (#4815). Registered
    # as early as possible — before track lookup/processor construction —
    # so _cancel_prior_task can find and set() it for the whole lifetime of
    # this task, not just once the streaming loop starts. Set() by
    # playback_commands._cancel_prior_task / playback_control.handle_stop
    # before they call task.cancel(); checked by
    # chunk_streaming.process_chunk before starting DSP.
    from routers.system import _stream_chunk_cancel_events
    chunk_cancel_event = threading.Event()
    _stream_chunk_cancel_events[_asc.ws_id(websocket)] = chunk_cancel_event

    # Whether the chunk loop exited before delivering the whole track, and how
    # much audio actually reached the client. Without these the terminal message
    # reported the FULL track length on a truncated stream, so a client could not
    # tell a stopped stream from a finished one (#4659).
    stopped_early: bool = False
    delivered_samples: int = 0
    # Chunk indices that failed processing and were skipped via the #3190
    # continue-and-keep-going recovery path. #4659 only tracked the break-driven
    # early exits (disconnect, timeout, enhancement toggled off) — a chunk that
    # fails and is skipped doesn't set stopped_early, so the loop can still run
    # to its natural end with gaps in the delivered audio and still report
    # reason="completed" with the full track's sample count (#4790).
    failed_chunks: list[int] = []

    # A single try/finally from here guards the semaphore permit acquired above:
    # it is released exactly once in the finally at the end. The track lookup
    # lives INSIDE this try so a task cancellation (CancelledError — a
    # BaseException that `except Exception` does not catch) during the awaited
    # get_by_id cannot escape before the permit is released, which would leak a
    # permit permanently for the process lifetime (#4329).
    try:
        # Get track from library and validate its filepath (#5032: shared
        # with stream_normal.py/stream_seek.py — see stream_track_resolution.py).
        resolved = await resolve_and_validate_track(
            controller, track_id, websocket, validate_file_path=validate_file_path
        )
        if resolved is None:
            return
        track, validated_filepath = resolved

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
            error_msg = "Audio processor initialization timed out. File may be corrupt or on slow storage."
            logger.error(f"Processor instantiation timed out for track {track_id} (30s)")
            await controller._send_error(websocket, track_id, error_msg)
            return

        # Ensure processor has loaded metadata (raise instead of assert
        # so guards work under python -O / PyInstaller, fixes #2735)
        for _attr in ('total_chunks', 'sample_rate', 'channels', 'duration'):
            if getattr(processor, _attr) is None:
                raise ValueError(f"Processor metadata missing: {_attr} is None")

        # Proactively buffer the first few chunks across every preset so a
        # preset switch early in playback doesn't wait the full DSP window
        # (#3884). Fire-and-forget: buffer_presets_for_track caches each
        # chunk to the same on-disk WAV cache process_chunk_safe() checks
        # (ChunkPathCache, keyed on track_id/file_signature/preset/intensity/
        # chunk_index), so a later real chunk request hits the pre-rendered
        # file instead of redoing DSP. It is a no-op per chunk that's already
        # cached, so re-issuing the same track (preset switch, WS reconnect)
        # is safe to call again. spawn_background_task logs instead of
        # silently dropping the rare exception that reaches it (the
        # function's own try/except already handles per-preset/per-chunk
        # failures internally).
        spawn_background_task(
            buffer_presets_for_track(
                track_id, validated_filepath, intensity, processor.total_chunks
            ),
            name=f"proactive_buffer:{track_id}",
        )

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

        # The process/send loop lives in stream_enhanced_chunks (#5032); what
        # stays here is the semaphore/cancel/finally skeleton around it.
        pump = await pump_enhanced_chunks(
            controller,
            websocket,
            track_id=track_id,
            processor=processor,
            preset=preset,
            intensity=intensity,
            on_progress=on_progress,
        )
        stopped_early = pump.stopped_early
        failed_chunks = pump.failed_chunks
        delivered_samples = pump.delivered_samples

        # Report whether the loop ran to the end and how much audio actually
        # reached the client — shared with stream_normal.py/stream_seek.py
        # (#5032), see stream_messages.send_stream_completion for the
        # reason= rules (#4659/#4790).
        await controller._send_stream_completion(
            websocket,
            track_id=track_id,
            label="Audio stream",
            stopped_early=stopped_early,
            failed_chunks=failed_chunks,
            delivered_samples=delivered_samples,
            sample_rate=processor.sample_rate,
            # Both guaranteed non-None due to the metadata assertions above.
            full_duration=processor.duration,
            log_full_duration_on_partial=True,
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
        # The look-ahead drain that used to sit here moved into
        # pump_enhanced_chunks' own finally (#3493 still holds — the task
        # cannot outlive that function).
        controller._stream_semaphore.release()
        # #5253: release the temp WAV this processor may own (SeekableSource,
        # #4737) — a non-natively-seekable format (m4a/aac/wma) converts once
        # per ChunkedAudioProcessor instance, and since a new instance is
        # constructed per stream, nothing ever reclaimed it before this fix.
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
