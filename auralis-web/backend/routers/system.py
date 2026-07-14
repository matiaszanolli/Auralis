"""
System Router - WebSocket
~~~~~~~~~~~~~~~~~~~~~~~~~

WebSocket endpoint for real-time communication.
Health and version endpoints have been moved to routers/health.py.
"""

import asyncio
import json
import logging
from typing import Any
from collections.abc import Callable

from core.audio_stream_controller import AudioStreamController, ws_id as _ws_id
from core.processing_engine import _safe_error_message
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket.websocket_security import (
    WebSocketRateLimiter,
    validate_and_parse_message,
    send_error_response,
)
from ws_handlers import connection as ws_connection
from ws_handlers.context import StreamState, WSDeps

logger = logging.getLogger(__name__)

# Track active streaming tasks per WebSocket to allow cancellation
_active_streaming_tasks: dict[str, asyncio.Task[None]] = {}
_active_streaming_tasks_lock = asyncio.Lock()  # Protects all _active_streaming_tasks access (fixes #2425)
# Track which track ID is currently streaming per WS (for deduplication)
_active_streaming_track_ids: dict[str, int] = {}

# Per-WebSocket pause events: when clear, streaming loops sleep; when set, they proceed.
# This avoids destroying the streaming task on pause (#2106).
_stream_pause_events: dict[str, asyncio.Event] = {}

# Per-WebSocket flow control events: when clear, backend stops sending chunks
# (frontend buffer is full); when set, backend continues streaming.
# Separate from pause events — pause is user-initiated, flow is buffer-driven.
_stream_flow_events: dict[str, asyncio.Event] = {}


# Global rate limiter for all WebSocket connections (fixes #2156)
_rate_limiter = WebSocketRateLimiter(max_messages_per_second=10)

router = APIRouter(tags=["system"])

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
    get_cache_manager: Callable[[], Any] | None,
    *,
    track_id: int = 0,
    preset: str = "adaptive",
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
            # Reuse the process-wide chunk cache so scrub/replay
            # hits cache instead of rebuilding DSP from scratch
            # (fixes #3855 — per-stream SimpleChunkCache prevented
            # cross-request sharing).
            cache_manager=get_cache_manager() if get_cache_manager else None,
        )

        if controller.fingerprint_generator:
            logger.info("✅ FingerprintGenerator available - on-demand fingerprint generation enabled")
        else:
            logger.warning("⚠️  FingerprintGenerator not available - using database/cached fingerprints only")

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
        except Exception:
            pass  # WebSocket may be closed
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
        except Exception:
            pass  # WebSocket may be closed
    finally:
        # Idempotent self-cleanup under lock (fixes #2425)
        async with _active_streaming_tasks_lock:
            if _active_streaming_tasks.get(ws_id) is my_task:
                _active_streaming_tasks.pop(ws_id, None)
                _active_streaming_track_ids.pop(ws_id, None)


async def stream_normal(
    websocket: WebSocket,
    get_repository_factory: Callable[..., Any] | None,
    get_cache_manager: Callable[[], Any] | None,
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
            cache_manager=get_cache_manager() if get_cache_manager else None,
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
        except Exception:
            pass  # WebSocket may be closed
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
    get_cache_manager: Callable[[], Any] | None,
    *,
    track_id: int = 0,
    preset: str = "adaptive",
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
            cache_manager=get_cache_manager() if get_cache_manager else None,
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
        except Exception:
            pass
    finally:
        # Idempotent self-cleanup under lock (fixes #2425)
        async with _active_streaming_tasks_lock:
            if _active_streaming_tasks.get(ws_id) is my_task:
                _active_streaming_tasks.pop(ws_id, None)
                _active_streaming_track_ids.pop(ws_id, None)


# ============================================================================
# Router factory
# ============================================================================

def create_system_router(
    manager: Any,
    get_processing_engine: Callable[..., Any],
    HAS_AURALIS: bool,
    get_repository_factory: Callable[..., Any] | None = None,
    get_state_manager: Callable[..., Any] | None = None,
    get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
    get_cache_manager: Callable[[], Any] | None = None,
) -> APIRouter:
    """Create system router (WebSocket endpoint only).

    Health and version routes are registered separately via create_health_router().
    """

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time communication.

        Handles heartbeat, enhancement settings sync, player state sync, and
        streaming commands (play_enhanced, play_normal, seek, stop,
        pause/resume). Connection lifecycle and per-message-type dispatch
        live in ws_handlers/ (#4074); this function wires them together for
        one connection.
        """
        connection_id, heartbeat, heartbeat_task = await ws_connection.setup_connection(
            websocket, manager, get_enhancement_settings, get_state_manager
        )
        state = StreamState(
            active_tasks=_active_streaming_tasks,
            active_tasks_lock=_active_streaming_tasks_lock,
            active_track_ids=_active_streaming_track_ids,
            pause_events=_stream_pause_events,
            flow_events=_stream_flow_events,
        )
        deps = WSDeps(
            get_repository_factory=get_repository_factory,
            get_enhancement_settings=get_enhancement_settings,
            get_cache_manager=get_cache_manager,
            get_processing_engine=get_processing_engine,
            stream_audio=stream_audio,
            stream_normal=stream_normal,
            stream_from_position=stream_from_position,
        )
        # Track job IDs this WS subscribed to, for cleanup on disconnect (#3325)
        subscribed_job_ids: set[str] = set()

        try:
            while True:
                # Named raw_data to avoid shadowing the inner payload dicts
                # extracted per-message below (fixes #2312).
                raw_data = await websocket.receive_text()

                # Security: Check rate limit (fixes #2156)
                allowed, error_msg = _rate_limiter.check_rate_limit(websocket)
                if not allowed:
                    logger.warning(f"Rate limit exceeded for WebSocket {_ws_id(websocket)}: {error_msg}")
                    await send_error_response(websocket, "rate_limit_exceeded", error_msg)
                    continue

                # Security: Validate message size and structure (fixes #2156)
                message, error = await validate_and_parse_message(raw_data, websocket)
                if error or not message:
                    continue

                await ws_connection.dispatch_message(
                    websocket, message, state, deps, heartbeat, connection_id, subscribed_job_ids
                )

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected normally")
        except RuntimeError as e:
            logger.warning(f"WebSocket runtime error: {e}")
        except Exception as e:
            logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
        finally:
            await ws_connection.teardown_connection(
                websocket, heartbeat_task, state, get_processing_engine,
                subscribed_job_ids, manager, _rate_limiter,
            )

    return router

