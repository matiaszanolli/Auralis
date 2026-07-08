"""
System Router - WebSocket
~~~~~~~~~~~~~~~~~~~~~~~~~

WebSocket endpoint for real-time communication.
Health and version endpoints have been moved to routers/health.py.
"""

import asyncio
import json
import logging
import math
from typing import Any
from collections.abc import Callable

from core.audio_stream_controller import AudioStreamController, ws_id as _ws_id
from core.processing_engine import _safe_error_message
from helpers import spawn_background_task
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from websocket.websocket_protocol import HeartbeatManager
from websocket.websocket_security import (
    WebSocketRateLimiter,
    validate_and_parse_message,
    send_error_response,
)

logger = logging.getLogger(__name__)

# Track active streaming tasks per WebSocket to allow cancellation
_active_streaming_tasks: dict[str, asyncio.Task] = {}
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

        Handles heartbeat, enhancement settings sync, player state sync,
        and streaming commands (play_enhanced, play_normal, seek, stop, pause/resume).
        """
        # Origin check is delegated entirely to ConnectionManager.connect
        # (config/globals.py) — see #3524 / BE-NEW-66. Single authoritative
        # origin policy lives in config/globals.py.
        await manager.connect(websocket)
        connection_id = _ws_id(websocket)
        heartbeat = HeartbeatManager(interval_seconds=30, timeout_seconds=10)

        async def _heartbeat_loop() -> None:
            """Send pings and evict stale connections."""
            while True:
                await asyncio.sleep(heartbeat.interval_seconds)
                if heartbeat.is_stale(connection_id):
                    logger.warning(f"WebSocket {connection_id} stale — closing")
                    await websocket.close(code=1001, reason="Heartbeat timeout")
                    return
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    heartbeat.mark_ping(connection_id)
                except Exception:
                    return  # Connection already dead

        heartbeat_task = spawn_background_task(_heartbeat_loop(), name=f"ws_heartbeat_{connection_id}")

        # Immediately send current enhancement settings so a reconnecting
        # frontend syncs its Redux store without waiting for the next broadcast
        # (fixes #2507).
        if get_enhancement_settings is not None:
            try:
                _settings = get_enhancement_settings()
                await websocket.send_text(json.dumps({
                    "type": "enhancement_settings_changed",
                    "data": {
                        "enabled": _settings.get("enabled", True),
                        "preset": _settings.get("preset", "adaptive"),
                        "intensity": _settings.get("intensity", 1.0),
                    }
                }))
            except Exception:
                pass  # Connection rejected or already closed

        # Push full player state on connect so reconnecting clients sync
        # their Redux store immediately (fixes #2606).
        if get_state_manager is not None:
            try:
                _state_mgr = get_state_manager()
                if _state_mgr is not None:
                    _state = _state_mgr.get_state()
                    await websocket.send_text(json.dumps({
                        "type": "player_state",
                        "data": _state.model_dump(),
                    }))
            except Exception:
                pass  # Best-effort: don't fail the connection

        # Track job IDs this WS subscribed to, for cleanup on disconnect (#3325)
        _subscribed_job_ids: set[str] = set()

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

                msg_type = message.get("type")

                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

                elif msg_type == "pong":
                    heartbeat.mark_pong(connection_id)

                elif msg_type == "heartbeat":
                    # Keepalive from RealTimeAnalysisStream — use mark_alive (not
                    # mark_pong) so an outstanding ping is not masked (#3866 / BE-WS-5).
                    heartbeat.mark_alive(connection_id)

                elif msg_type == "processing_settings_update":
                    settings = message.get("data", {})
                    logger.info(f"Processing settings updated: {settings}")
                    await manager.broadcast({"type": "processing_settings_applied", "data": settings})

                elif msg_type == "ab_track_loaded":
                    track_data = message.get("data", {})
                    logger.info(f"A/B track loaded: {track_data}")
                    await manager.broadcast({"type": "ab_track_ready", "data": track_data})

                elif msg_type == "play_enhanced":
                    data = message.get("data", {})
                    track_id = data.get("track_id")

                    # Validate track_id before launching any background task (#2393)
                    if not isinstance(track_id, int) or track_id <= 0:
                        logger.warning(f"Invalid track_id in play_enhanced: {track_id!r}")
                        await send_error_response(websocket, "invalid_track_id", "track_id must be a positive integer")
                        continue

                    VALID_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]
                    # Explicit client opt-out of the stored-`enabled` gate (#3773).
                    force = bool(data.get("force", False))

                    raw_preset = data.get("preset", "")
                    raw_intensity = data.get("intensity")
                    preset = raw_preset.lower() if (raw_preset and isinstance(raw_preset, str) and raw_preset.lower() in VALID_PRESETS) else None
                    intensity = float(raw_intensity) if (isinstance(raw_intensity, (int, float)) and 0.0 <= raw_intensity <= 1.0) else None

                    enhancement_enabled = True
                    if get_enhancement_settings is not None:
                        settings = get_enhancement_settings()
                        enhancement_enabled = settings.get("enabled", True)
                        if preset is None:
                            preset = settings.get("preset", "adaptive")
                        if intensity is None:
                            intensity = settings.get("intensity", 1.0)
                        logger.info(f"Using enhancement settings (frontend+stored): enabled={enhancement_enabled}, preset={preset}, intensity={intensity}")
                    else:
                        if preset is None:
                            await send_error_response(websocket, "invalid_preset", f"Invalid preset. Must be one of: {', '.join(VALID_PRESETS)}")
                            continue
                        if intensity is None:
                            intensity = 1.0
                        logger.warning("Enhancement settings not available, using validated message data")

                    start_position = float(data.get("start_position", 0.0) or 0.0)
                    if not math.isfinite(start_position):
                        start_position = 0.0

                    logger.info(
                        f"Received play_enhanced: track_id={track_id}, preset={preset}, intensity={intensity}"
                        + (f", resume_at={start_position:.1f}s" if start_position > 0 else "")
                    )

                    if not enhancement_enabled and not force:
                        logger.warning(f"Enhancement disabled, rejecting play_enhanced request for track {track_id}")
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "audio_stream_error",
                                "data": {
                                    "track_id": track_id,
                                    "error": "Auto-mastering is currently disabled. Enable it in the enhancement panel to use this feature.",
                                    "code": "ENHANCEMENT_DISABLED",
                                    "stream_type": "enhanced",
                                }
                            }))
                        except Exception as e:
                            logger.error(f"Failed to send enhancement disabled error: {e}")
                        continue

                    ws_id = _ws_id(websocket)

                    # Deduplicate: if the same track is already streaming, skip
                    async with _active_streaming_tasks_lock:
                        existing_track = _active_streaming_track_ids.get(ws_id)
                        existing_task = _active_streaming_tasks.get(ws_id)
                        if (existing_track == track_id and existing_task is not None and not existing_task.done()):
                            logger.info(f"Ignoring duplicate play_enhanced for track {track_id} (already streaming on ws {ws_id})")
                            continue

                    # Atomically: clean up done tasks, cancel prior stream, register new task (fixes #2425, #2430)
                    async with _active_streaming_tasks_lock:
                        for k in [k for k, v in _active_streaming_tasks.items() if v.done()]:
                            _active_streaming_tasks.pop(k, None)
                        old_task = _active_streaming_tasks.pop(ws_id, None)
                        if old_task and not old_task.done():
                            logger.info(f"Cancelling existing streaming task for ws {ws_id}")
                            old_task.cancel()
                            # Await cancellation so the old task releases pause/flow events (#3219)
                            try:
                                await old_task
                            except (asyncio.CancelledError, Exception):
                                pass
                        # Clear stale events before creating fresh ones (#3219)
                        _stream_pause_events.pop(ws_id, None)
                        _stream_flow_events.pop(ws_id, None)
                        # Create pause event for this stream — set = running (#2106)
                        pause_event = asyncio.Event()
                        pause_event.set()
                        _stream_pause_events[ws_id] = pause_event
                        # Create flow control event — set = flowing (not throttled)
                        flow_event = asyncio.Event()
                        flow_event.set()
                        _stream_flow_events[ws_id] = flow_event
                        task = asyncio.create_task(stream_audio(
                            websocket,
                            get_repository_factory,
                            get_enhancement_settings,
                            get_cache_manager,
                            track_id=track_id,
                            preset=preset,
                            intensity=intensity,
                            force=force,
                            start_position=start_position,
                            ws_id=ws_id,
                        ))
                        _active_streaming_tasks[ws_id] = task
                        _active_streaming_track_ids[ws_id] = track_id
                    logger.info(f"Started background streaming task for track {track_id}")

                elif msg_type == "play_normal":
                    data = message.get("data", {})
                    track_id = data.get("track_id")

                    # Validate track_id before launching any background task (#2393)
                    if not isinstance(track_id, int) or track_id <= 0:
                        logger.warning(f"Invalid track_id in play_normal: {track_id!r}")
                        await send_error_response(websocket, "invalid_track_id", "track_id must be a positive integer")
                        continue

                    start_position = float(data.get("start_position", 0.0) or 0.0)
                    if not math.isfinite(start_position):
                        start_position = 0.0

                    logger.info(
                        f"Received play_normal: track_id={track_id}"
                        + (f", resume_at={start_position:.1f}s" if start_position > 0 else "")
                    )

                    ws_id = _ws_id(websocket)

                    # Atomically: clean up done tasks, cancel prior stream, register new task (fixes #2425, #2430)
                    async with _active_streaming_tasks_lock:
                        for k in [k for k, v in _active_streaming_tasks.items() if v.done()]:
                            _active_streaming_tasks.pop(k, None)
                        old_task = _active_streaming_tasks.pop(ws_id, None)
                        if old_task and not old_task.done():
                            logger.info(f"Cancelling existing streaming task for ws {ws_id}")
                            old_task.cancel()
                            # Await cancellation so the old task releases pause/flow events (#3219)
                            try:
                                await old_task
                            except (asyncio.CancelledError, Exception):
                                pass
                        # Clear stale events before creating fresh ones (#3219)
                        _stream_pause_events.pop(ws_id, None)
                        _stream_flow_events.pop(ws_id, None)
                        # Create pause event for this stream — set = running (#2106)
                        pause_event = asyncio.Event()
                        pause_event.set()
                        _stream_pause_events[ws_id] = pause_event
                        # Create flow control event — set = flowing (not throttled)
                        flow_event = asyncio.Event()
                        flow_event.set()
                        _stream_flow_events[ws_id] = flow_event
                        task = asyncio.create_task(stream_normal(
                            websocket,
                            get_repository_factory,
                            get_cache_manager,
                            track_id=track_id,
                            start_position=start_position,
                            ws_id=ws_id,
                        ))
                        _active_streaming_tasks[ws_id] = task
                        # Track which track is streaming so subsequent play_enhanced
                        # dedup checks see the truth (#3509 / BE-NEW-51).
                        _active_streaming_track_ids[ws_id] = track_id
                    logger.info(f"Started background normal streaming task for track {track_id}")

                elif msg_type == "pause":
                    logger.info("Received pause command via WebSocket")
                    ws_id = _ws_id(websocket)
                    pause_evt = _stream_pause_events.get(ws_id)
                    if pause_evt is not None:
                        pause_evt.clear()
                        logger.info("Paused streaming task (event cleared)")
                    # Use {state} shape the frontend type expects (#3503 / BE-NEW-45).
                    await websocket.send_text(json.dumps({"type": "playback_paused", "data": {"state": "paused"}}))

                elif msg_type == "resume":
                    logger.info("Received resume command via WebSocket")
                    ws_id = _ws_id(websocket)
                    pause_evt = _stream_pause_events.get(ws_id)
                    if pause_evt is not None:
                        pause_evt.set()
                        logger.info("Resumed streaming task (event set)")
                    await websocket.send_text(json.dumps({"type": "playback_resumed", "data": {"state": "playing"}}))

                elif msg_type == "buffer_full":
                    ws_id = _ws_id(websocket)
                    flow_evt = _stream_flow_events.get(ws_id)
                    if flow_evt is not None:
                        flow_evt.clear()
                        logger.debug("Flow control: paused (buffer_full)")

                elif msg_type == "buffer_ready":
                    ws_id = _ws_id(websocket)
                    flow_evt = _stream_flow_events.get(ws_id)
                    if flow_evt is not None:
                        flow_evt.set()
                        logger.debug("Flow control: resumed (buffer_ready)")

                elif msg_type == "stop":
                    logger.info("Received stop command via WebSocket")
                    ws_id = _ws_id(websocket)
                    async with _active_streaming_tasks_lock:
                        task = _active_streaming_tasks.pop(ws_id, None)
                    if task and not task.done():
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass
                        logger.info("Cancelled active streaming task")
                    await websocket.send_text(json.dumps({"type": "playback_stopped", "data": {"state": "stopped"}}))

                elif msg_type == "seek":
                    data = message.get("data", {})
                    track_id = data.get("track_id")
                    position = data.get("position", 0)

                    # Validate before launching any background task (#2393)
                    if not isinstance(track_id, int) or track_id <= 0:
                        logger.warning(f"Invalid track_id in seek: {track_id!r}")
                        await send_error_response(websocket, "invalid_track_id", "track_id must be a positive integer")
                        continue

                    if not isinstance(position, (int, float)) or not math.isfinite(position) or position < 0:
                        logger.warning(f"Invalid seek position: {position!r}")
                        await send_error_response(websocket, "invalid_seek_position", "position must be a non-negative number")
                        continue

                    # Use WS message values as initial fallback (fixes #2381),
                    # then let server-side settings override (fixes #2103).
                    preset = data.get("preset", "adaptive")
                    intensity = data.get("intensity", 1.0)
                    if get_enhancement_settings is not None:
                        settings = get_enhancement_settings()
                        preset = settings.get("preset", preset)
                        intensity = settings.get("intensity", intensity)

                    logger.info(f"Received seek: track_id={track_id}, position={position}s, preset={preset}")

                    # Pop prior task under lock; cancel and await outside lock to avoid deadlock (fixes #2425, #2430)
                    ws_id = _ws_id(websocket)
                    async with _active_streaming_tasks_lock:
                        for k in [k for k, v in _active_streaming_tasks.items() if v.done()]:
                            _active_streaming_tasks.pop(k, None)
                        old_task = _active_streaming_tasks.pop(ws_id, None)
                    if old_task and not old_task.done():
                        logger.info("Cancelling existing streaming task for seek")
                        old_task.cancel()
                        # Await unconditionally (fixes #3806) — the prior 100ms
                        # wait_for/shield let the old task's DSP work (200ms-2s
                        # inside asyncio.to_thread) outlive the timeout, so it
                        # resumed and sent its own chunk over the same websocket
                        # concurrently with the new seek task, interleaving
                        # frames. play_enhanced/play_normal already await
                        # unconditionally (see above); seek was the outlier. No
                        # deadlock risk: the lock was released above this block.
                        try:
                            await old_task
                        except (asyncio.CancelledError, Exception):
                            pass

                    await websocket.send_text(json.dumps({
                        "type": "seek_started",
                        "data": {"track_id": track_id, "position": position},
                    }))

                    enhancement_enabled = True
                    if get_enhancement_settings is not None:
                        enhancement_enabled = get_enhancement_settings().get("enabled", True)

                    # Reset pause/flow-control events AND register the new seek task
                    # atomically — fixes #3522 / BE-NEW-64 (prior code did the event
                    # replacement outside the lock, leaving a torn-state window).
                    async with _active_streaming_tasks_lock:
                        pause_event = asyncio.Event()
                        pause_event.set()
                        _stream_pause_events[ws_id] = pause_event
                        flow_event = asyncio.Event()
                        flow_event.set()
                        _stream_flow_events[ws_id] = flow_event
                        task = asyncio.create_task(stream_from_position(
                            websocket,
                            get_repository_factory,
                            get_enhancement_settings,
                            get_cache_manager,
                            track_id=track_id,
                            preset=preset,
                            intensity=intensity,
                            position=position,
                            enhancement_enabled=enhancement_enabled,
                            ws_id=ws_id,
                        ))
                        _active_streaming_tasks[ws_id] = task
                        _active_streaming_track_ids[ws_id] = track_id
                    logger.info(f"Started seek streaming task for track {track_id} at {position}s")

                elif msg_type == "subscribe_job_progress":
                    data = message.get("data", {})
                    job_id = data.get("job_id")
                    # Validate job_id — prior code accepted any value, opening a slow
                    # per-session leak and non-string payloads to other WS subscribers
                    # (#3520 / BE-NEW-62).
                    if not isinstance(job_id, str) or not job_id or len(job_id) > 64:
                        await send_error_response(websocket, "invalid_job_id", "Invalid job_id (must be non-empty string, ≤64 chars)")
                        continue
                    processing_engine = get_processing_engine()
                    if processing_engine:
                        async def progress_callback(job_id: str, progress: float, message: str) -> None:
                            # Skip (and self-unregister) once the socket is no longer
                            # connected — closing this window matters because the
                            # engine's own catch-all in _notify_progress only removes
                            # a callback AFTER it raises, so without this guard every
                            # progress tick between disconnect and cleanup still
                            # attempts a send on a dead socket (fixes #3826 / BE-RH-9).
                            if websocket.client_state != WebSocketState.CONNECTED:
                                await processing_engine.unregister_progress_callback(job_id)
                                return
                            await websocket.send_text(json.dumps({
                                "type": "job_progress",
                                "data": {"job_id": job_id, "progress": progress, "message": message}
                            }))

                        # Track subscription intent BEFORE registering with the engine
                        # (not after) so the disconnect-cleanup loop below always knows
                        # to unregister this job_id even if this task is cancelled
                        # mid-await inside register_progress_callback.
                        _subscribed_job_ids.add(job_id)
                        await processing_engine.register_progress_callback(job_id, progress_callback)

                else:
                    # Unknown message type (fixes #2417); sanitize before reflecting to client
                    raw_type = message.get("type", "unknown")
                    safe_type = str(raw_type)[:32] if isinstance(raw_type, str) else "non-string"
                    logger.warning(f"Unknown WebSocket message type: {raw_type!r}")
                    await send_error_response(websocket, "unknown_message_type", f"Unknown message type: {safe_type}")

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected normally")
        except RuntimeError as e:
            logger.warning(f"WebSocket runtime error: {e}")
        except Exception as e:
            logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
        finally:
            # Always clean up on disconnect. Each step is independently
            # try/except-guarded so a failure mid-sequence cannot skip
            # later steps (manager.disconnect in particular) and leave the
            # WS in ConnectionManager.active_connections — fixes #3521 / BE-NEW-63.
            try:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            except Exception:
                logger.warning("Heartbeat cleanup failed", exc_info=True)
            ws_id = _ws_id(websocket)

            # Cancel any active streaming task — idempotent pop under lock (fixes #2425).
            # Also await the cancellation so the streaming task fully releases its
            # semaphore + chunk cache before we proceed.
            try:
                async with _active_streaming_tasks_lock:
                    task = _active_streaming_tasks.pop(ws_id, None)
                    _active_streaming_track_ids.pop(ws_id, None)
                if task and not task.done():
                    logger.info(f"Cancelling streaming task on disconnect for ws {ws_id}")
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
            except Exception:
                logger.warning("Streaming-task cleanup failed", exc_info=True)

            # Clean up pause event (#2106) and flow control event
            try:
                _stream_pause_events.pop(ws_id, None)
                _stream_flow_events.pop(ws_id, None)
            except Exception:
                logger.warning("Stream-event cleanup failed", exc_info=True)

            # Clean up rate limiter (fixes #2156)
            try:
                _rate_limiter.cleanup(websocket)
            except Exception:
                logger.warning("Rate-limiter cleanup failed", exc_info=True)

            # Remove stale progress callbacks on WS disconnect (#3325).
            # Wrap each unregister so one failure doesn't skip the rest.
            if _subscribed_job_ids:
                processing_engine = get_processing_engine()
                if processing_engine:
                    for jid in list(_subscribed_job_ids):
                        try:
                            await processing_engine.unregister_progress_callback(jid)
                        except Exception:
                            logger.warning(f"Failed to unregister progress callback for {jid}", exc_info=True)

            # Remove from connection manager
            try:
                await manager.disconnect(websocket)
            except Exception:
                logger.warning("manager.disconnect failed", exc_info=True)

    return router
