"""
System router WebSocket streaming tasks and their registries (split from
system.py, #5832).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import json
import logging
import threading
from typing import Any
from collections.abc import Callable

from core.audio_stream_controller import AudioStreamController
from core.processing_engine import _safe_error_message
from fastapi import WebSocket
from schemas import DEFAULT_PRESET

logger = logging.getLogger(__name__)

# Track active streaming tasks per WebSocket to allow cancellation
_active_streaming_tasks: dict[str, asyncio.Task[None]] = {}
_active_streaming_tasks_lock = asyncio.Lock()  # Protects all _active_streaming_tasks access (fixes #2425)
# Track which track ID is currently streaming per WS (for deduplication)
_active_streaming_track_ids: dict[str, int] = {}

# Per-WebSocket cooperative-cancel signal for in-flight chunk DSP (#4815).
# stream_enhanced.py/stream_seek.py create one threading.Event per active
# stream and set()/pop() it in this dict; _cancel_prior_task/handle_stop
# set() it before cancelling so an already-abandoned chunk's executor
# thread can bail out early instead of running to completion unreferenced.
_stream_chunk_cancel_events: dict[str, threading.Event] = {}


# ============================================================================
# Streaming task coroutines — module-level so they are independently testable.
# The per-message locals (track_id, preset, …) are snapshotted as keyword-only
# default args so each task owns immutable copies: a later receive-loop message
# reassigning those names cannot leak into an in-flight task's except/finally
# paths and misattribute an error to the wrong track (#3829).
# ============================================================================

async def stream_audio(
    websocket: WebSocket,
    get_repository_factory: Callable[..., Any] | None,
    get_enhancement_settings: Callable[[], dict[str, Any]] | None,
    *,
    track_id: int = 0,
    preset: str = DEFAULT_PRESET,
    intensity: float = 1.0,
    force: bool = False,
    start_position: float = 0.0,
    ws_id: str = "",
) -> None:
    """Stream enhanced audio for a play_enhanced request."""
    # Capture task identity to prevent orphaned task race (fixes #2164)
    my_task = asyncio.current_task()
    try:
        from core.chunked_processor import ChunkedAudioProcessor

        controller = AudioStreamController(
            chunked_processor_class=ChunkedAudioProcessor,
            get_repository_factory=get_repository_factory,
            # When the client forced enhanced playback (#3773),
            # bypass the mid-stream "enhancement disabled" gate
            # (#2866) too — otherwise a stored enabled=false would
            # stop the forced stream on its first chunk.
            get_enhancement_enabled=(
                (lambda: get_enhancement_settings().get("enabled", True))
                if (get_enhancement_settings is not None and not force)
                else None
            ),
        )

        if start_position > 0:
            # Resume from position (WS reconnect, #3185)
            await controller.stream_enhanced_audio_from_position(
                track_id=track_id,
                preset=preset,
                intensity=intensity,
                websocket=websocket,
                start_position=start_position,
            )
        else:
            await controller.stream_enhanced_audio(
                track_id=track_id,
                preset=preset,
                intensity=intensity,
                websocket=websocket,
            )
    except asyncio.CancelledError:
        logger.info(f"Streaming task cancelled for track {track_id}")
    except ImportError as e:
        logger.error(f"ChunkedAudioProcessor not available: {e}")
        try:
            await websocket.send_text(
                json.dumps({
                    "type": "audio_stream_error",
                    "data": {
                        "track_id": track_id,
                        "error": "Audio processing not available",
                        "code": "PROCESSOR_UNAVAILABLE",
                        "stream_type": "enhanced",
                    }
                })
            )
        except Exception as e:
            # WebSocket may be closed — but also catches a send-side bug
            # (e.g. a json.dumps failure), so log it (#4809).
            logger.debug(f"Failed to send PROCESSOR_UNAVAILABLE error frame: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error in streaming task: {e}", exc_info=True)
        try:
            await websocket.send_text(
                json.dumps({
                    "type": "audio_stream_error",
                    "data": {
                        "track_id": track_id,
                        "error": _safe_error_message(e),
                        "code": "STREAMING_ERROR",
                        "stream_type": "enhanced",
                    }
                })
            )
        except Exception as e:
            # WebSocket may be closed — but also catches a send-side bug
            # (e.g. a json.dumps failure), so log it (#4809).
            logger.debug(f"Failed to send STREAMING_ERROR (enhanced) error frame: {e}", exc_info=True)
    finally:
        # Idempotent self-cleanup under lock (fixes #2425)
        async with _active_streaming_tasks_lock:
            if _active_streaming_tasks.get(ws_id) is my_task:
                _active_streaming_tasks.pop(ws_id, None)
                _active_streaming_track_ids.pop(ws_id, None)


async def stream_normal(
    websocket: WebSocket,
    get_repository_factory: Callable[..., Any] | None,
    *,
    track_id: int = 0,
    start_position: float = 0.0,
    ws_id: str = "",
) -> None:
    """Stream original (unprocessed) audio for a play_normal request."""
    # Capture task identity to prevent orphaned task race (fixes #2164)
    my_task = asyncio.current_task()
    try:
        controller = AudioStreamController(
            chunked_processor_class=None,
            get_repository_factory=get_repository_factory,
        )
        await controller.stream_normal_audio(
            track_id=track_id,
            websocket=websocket,
            start_position=start_position,
        )
    except asyncio.CancelledError:
        logger.info(f"Normal streaming task cancelled for track {track_id}")
    except Exception as e:
        logger.error(f"Error in normal streaming task: {e}", exc_info=True)
        try:
            await websocket.send_text(
                json.dumps({
                    "type": "audio_stream_error",
                    "data": {
                        "track_id": track_id,
                        "error": _safe_error_message(e),
                        "code": "STREAMING_ERROR",
                        "stream_type": "normal",
                    }
                })
            )
        except Exception as e:
            # WebSocket may be closed — but also catches a send-side bug
            # (e.g. a json.dumps failure), so log it (#4809).
            logger.debug(f"Failed to send STREAMING_ERROR (normal) error frame: {e}", exc_info=True)
    finally:
        # Idempotent self-cleanup under lock (fixes #2425)
        async with _active_streaming_tasks_lock:
            if _active_streaming_tasks.get(ws_id) is my_task:
                _active_streaming_tasks.pop(ws_id, None)
                _active_streaming_track_ids.pop(ws_id, None)


async def stream_from_position(
    websocket: WebSocket,
    get_repository_factory: Callable[..., Any] | None,
    get_enhancement_settings: Callable[[], dict[str, Any]] | None,
    *,
    track_id: int = 0,
    preset: str = DEFAULT_PRESET,
    intensity: float = 1.0,
    position: float = 0.0,
    enhancement_enabled: bool = True,
    ws_id: str = "",
) -> None:
    """Stream audio from a seek position for a seek request."""
    # Capture task identity to prevent orphaned task race (fixes #2164)
    my_task = asyncio.current_task()
    stream_type = "enhanced" if enhancement_enabled else "normal"
    try:
        from core.chunked_processor import ChunkedAudioProcessor

        controller = AudioStreamController(
            chunked_processor_class=ChunkedAudioProcessor,
            get_repository_factory=get_repository_factory,
            get_enhancement_enabled=(
                (lambda: get_enhancement_settings().get("enabled", True))
                if get_enhancement_settings is not None
                else None
            ),
        )

        if enhancement_enabled:
            await controller.stream_enhanced_audio_from_position(
                track_id=track_id,
                preset=preset,
                intensity=intensity,
                websocket=websocket,
                start_position=position,
            )
        else:
            # Route to normal streaming with seek offset (#3187)
            await controller.stream_normal_audio(
                track_id=track_id,
                websocket=websocket,
                start_position=position,
            )
    except asyncio.CancelledError:
        logger.info(f"Seek streaming task cancelled for track {track_id}")
    except Exception as e:
        logger.error(f"Error in seek streaming task: {e}", exc_info=True)
        try:
            await websocket.send_text(
                json.dumps({
                    "type": "audio_stream_error",
                    "data": {
                        "track_id": track_id,
                        "error": _safe_error_message(e),
                        "code": "SEEK_ERROR",
                        "stream_type": stream_type,
                    }
                })
            )
        except Exception as e:
            # WebSocket may be closed — but also catches a send-side bug
            # (e.g. a json.dumps failure), so log it (#4809).
            logger.debug(f"Failed to send SEEK_ERROR error frame: {e}", exc_info=True)
    finally:
        # Idempotent self-cleanup under lock (fixes #2425)
        async with _active_streaming_tasks_lock:
            if _active_streaming_tasks.get(ws_id) is my_task:
                _active_streaming_tasks.pop(ws_id, None)
                _active_streaming_track_ids.pop(ws_id, None)
