#!/usr/bin/env python3

"""
Enhanced / Seek Stream Lifecycle
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The skeleton `stream_enhanced_audio` and `stream_enhanced_audio_from_position` share (#6214): the
stream-slot semaphore, the cooperative-cancel registration, track resolution, processor construction
with a timeout, the error replies, and the teardown (semaphore, temp WAV, cancel-event registry, the
proactive-buffer task). Each entry point keeps only what differs: its start message, how it picks the
first chunk, and its logging. Written once because the two copies drifted (#4329, #4815, #5253, #5378).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc
from .job_error_mapping import _safe_error_message
from .stream_gates import stream_chunk_cancel_events
from .stream_track_resolution import resolve_and_validate_track

if TYPE_CHECKING:
    from .chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger(__name__)


@dataclass
class EnhancedStream:
    """What a running enhanced/seek stream owns, for its body and for the teardown."""

    chunk_cancel_event: threading.Event = field(default_factory=threading.Event)
    # Set once constructed; None while construction runs, so the finally can tell.
    processor: 'ChunkedAudioProcessor | None' = None
    # The proactive-buffer task (#5378): scoped to this stream's life, or it keeps rendering after a stop.
    buffer_task: 'asyncio.Task[Any] | None' = None


@dataclass(frozen=True)
class StreamFlavour:
    """The wording and error code that differ between a play-from-start stream and a seek."""

    stopped_log: str
    failed_log: str
    init_timeout_log_suffix: str = ""
    init_timeout_message: str = (
        "Audio processor initialization timed out. File may be corrupt or on slow storage."
    )
    error_code: str | None = None


async def run_enhanced_stream(
    controller: '_asc.AudioStreamController',
    track_id: int,
    preset: str,
    intensity: float,
    websocket: WebSocket,
    *,
    flavour: StreamFlavour,
    validate_file_path: Callable[..., Any],
    body: Callable[[EnhancedStream, str], Awaitable[None]],
) -> None:
    """Run ``body(stream, validated_filepath)`` inside the shared enhanced-stream lifecycle."""
    _asc._stream_type_var.set("enhanced")  # per-task; safe for concurrent coroutines (#2493)

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
    except TimeoutError:
        logger.warning(
            f"Stream limit ({_asc.MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
        )
        await controller._send_error(websocket, track_id, "Server busy - too many active streams")
        return

    # Registered before track lookup and processor construction so _cancel_prior_task can set() it
    # for this task's whole life, not just once the chunk loop runs (#4815).
    stream = EnhancedStream()
    stream_chunk_cancel_events[_asc.ws_id(websocket)] = stream.chunk_cancel_event
    error_kwargs: dict[str, Any] = {"error_code": flavour.error_code} if flavour.error_code else {}

    # One try/finally guards the semaphore permit acquired above. The track lookup lives INSIDE it so a
    # CancelledError (a BaseException) during the awaited lookup cannot leak the permit (#4329).
    try:
        resolved = await resolve_and_validate_track(
            controller, track_id, websocket, validate_file_path=validate_file_path
        )
        if resolved is None:
            return
        _track, validated_filepath = resolved

        try:
            stream.processor = await asyncio.wait_for(
                asyncio.to_thread(
                    controller.chunked_processor_class,
                    track_id=track_id,
                    filepath=validated_filepath,
                    preset=preset,
                    intensity=intensity,
                    cancel_event=stream.chunk_cancel_event,
                ),
                timeout=_asc.PROCESSOR_INIT_TIMEOUT,
            )
        except TimeoutError:
            stream.chunk_cancel_event.set()  # the abandoned init thread drops its analysis wait (#6336)
            logger.error(
                f"Processor instantiation timed out for track {track_id}{flavour.init_timeout_log_suffix} "
                f"({_asc.PROCESSOR_INIT_TIMEOUT:.0f}s)"
            )
            await controller._send_error(websocket, track_id, flavour.init_timeout_message, **error_kwargs)
            return

        await body(stream, validated_filepath)

    except WebSocketDisconnect:
        # Client closed the WebSocket: a normal exit (#3511).
        logger.info(flavour.stopped_log)
    except Exception as e:
        logger.error(f"{flavour.failed_log}: {e}", exc_info=True)
        if controller._is_websocket_connected(websocket):
            # #5488: surface the specific category, not a blanket string.
            await controller._send_error(
                websocket, track_id, _safe_error_message(e, default="Audio streaming failed"), **error_kwargs
            )
    finally:
        # Signal the proactive buffer at once; the awaited drain is last, because a cancellation aimed at
        # THIS task re-raises out of the drain (#5083) and would skip everything after it (#5378).
        if stream.buffer_task is not None and not stream.buffer_task.done():
            stream.buffer_task.cancel()
        controller._stream_semaphore.release()
        # Release the temp WAV a non-natively-seekable format converts per processor (#5253) and return
        # this stream's leased HybridProcessor to the factory (#6091).
        if stream.processor is not None:
            await asyncio.to_thread(stream.processor.close)
        # Remove only OUR registration: a reissued stream on the same ws_id may own the slot now (#4815).
        ws_key = _asc.ws_id(websocket)
        if stream_chunk_cancel_events.get(ws_key) is stream.chunk_cancel_event:
            stream_chunk_cancel_events.pop(ws_key, None)
        await controller._drain_cancelled_task(stream.buffer_task)
