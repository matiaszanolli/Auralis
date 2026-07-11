"""
WebSocket Connection Lifecycle & Dispatch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Connection setup/teardown and per-message-type dispatch for the `/ws`
endpoint, extracted from routers/system.py so `websocket_endpoint` stays a
thin wrapper (#4074).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import logging
from typing import Any
from collections.abc import Callable

from fastapi import WebSocket

from core.audio_stream_controller import ws_id as _ws_id
from helpers import spawn_background_task
from websocket.websocket_protocol import HeartbeatManager
from websocket.websocket_security import WebSocketRateLimiter

from . import messages as msg_handlers
from . import playback_commands, playback_control
from .context import StreamState, WSDeps

logger = logging.getLogger(__name__)


async def setup_connection(
    websocket: WebSocket,
    manager: Any,
    get_enhancement_settings: Callable[[], dict[str, Any]] | None,
    get_state_manager: Callable[..., Any] | None,
) -> tuple[str, HeartbeatManager, asyncio.Task[None]]:
    """Accept the connection, start the heartbeat loop, and push initial
    sync frames (enhancement settings, player state) to the client."""
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

    return connection_id, heartbeat, heartbeat_task


async def dispatch_message(
    websocket: WebSocket,
    message: dict[str, Any],
    state: StreamState,
    deps: WSDeps,
    manager: Any,
    heartbeat: HeartbeatManager,
    connection_id: str,
    subscribed_job_ids: set[str],
) -> None:
    """Route one parsed WS message to its handler by `type`."""
    msg_type = message.get("type")

    if msg_type == "ping":
        await msg_handlers.handle_ping(websocket)
    elif msg_type == "pong":
        msg_handlers.handle_pong(heartbeat, connection_id)
    elif msg_type == "heartbeat":
        msg_handlers.handle_heartbeat(heartbeat, connection_id)
    elif msg_type == "processing_settings_update":
        await msg_handlers.handle_processing_settings_update(message, manager)
    elif msg_type == "ab_track_loaded":
        await msg_handlers.handle_ab_track_loaded(message, manager)
    elif msg_type == "play_enhanced":
        await playback_commands.handle_play_enhanced(websocket, message, state, deps)
    elif msg_type == "play_normal":
        await playback_commands.handle_play_normal(websocket, message, state, deps)
    elif msg_type == "pause":
        await playback_control.handle_pause(websocket, state)
    elif msg_type == "resume":
        await playback_control.handle_resume(websocket, state)
    elif msg_type == "buffer_full":
        await playback_control.handle_buffer_full(websocket, state)
    elif msg_type == "buffer_ready":
        await playback_control.handle_buffer_ready(websocket, state)
    elif msg_type == "stop":
        await playback_control.handle_stop(websocket, state)
    elif msg_type == "seek":
        await playback_commands.handle_seek(websocket, message, state, deps)
    elif msg_type == "subscribe_job_progress":
        await msg_handlers.handle_subscribe_job_progress(websocket, message, deps, subscribed_job_ids)
    else:
        await msg_handlers.handle_unknown(websocket, message)


async def teardown_connection(
    websocket: WebSocket,
    heartbeat_task: asyncio.Task[None],
    state: StreamState,
    get_processing_engine: Callable[..., Any],
    subscribed_job_ids: set[str],
    manager: Any,
    rate_limiter: WebSocketRateLimiter,
) -> None:
    """Always clean up on disconnect. Each step is independently
    try/except-guarded so a failure mid-sequence cannot skip later steps
    (manager.disconnect in particular) and leave the WS in
    ConnectionManager.active_connections — fixes #3521 / BE-NEW-63."""
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
        async with state.active_tasks_lock:
            task = state.active_tasks.pop(ws_id, None)
            state.active_track_ids.pop(ws_id, None)
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
        state.pause_events.pop(ws_id, None)
        state.flow_events.pop(ws_id, None)
    except Exception:
        logger.warning("Stream-event cleanup failed", exc_info=True)

    # Clean up rate limiter (fixes #2156)
    try:
        rate_limiter.cleanup(websocket)
    except Exception:
        logger.warning("Rate-limiter cleanup failed", exc_info=True)

    # Remove stale progress callbacks on WS disconnect (#3325).
    # Wrap each unregister so one failure doesn't skip the rest.
    if subscribed_job_ids:
        processing_engine = get_processing_engine()
        if processing_engine:
            for jid in list(subscribed_job_ids):
                try:
                    await processing_engine.unregister_progress_callback(jid)
                except Exception:
                    logger.warning(f"Failed to unregister progress callback for {jid}", exc_info=True)

    # Remove from connection manager
    try:
        await manager.disconnect(websocket)
    except Exception:
        logger.warning("manager.disconnect failed", exc_info=True)
