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
from core.stream_protocol import safe_send_text
from helpers import spawn_background_task
from websocket.websocket_protocol import HeartbeatManager
from websocket.websocket_security import WebSocketRateLimiter

from . import messages as msg_handlers
from . import playback_commands, playback_control
from .context import StreamState, WSDeps

logger = logging.getLogger(__name__)


async def run_heartbeat_loop(
    websocket: WebSocket,
    heartbeat: HeartbeatManager,
    connection_id: str,
) -> None:
    """Send pings and evict stale connections.

    Two independent cadences, deliberately decoupled (#4843): pings go out
    every ``interval_seconds``, but staleness is checked at the ``pending
    pong + timeout_seconds`` deadline. The loop previously slept one full
    interval and then checked, so ``elapsed`` at check time was always
    ≈ ``interval_seconds`` — ``30 > 10`` was unconditionally true and
    ``timeout_seconds`` could not influence detection latency at all.
    Tuning it down bought nothing unless ``interval_seconds`` came down too.

    Sleeping to whichever deadline comes first (rather than polling on a
    fixed short tick) keeps an idle connection at exactly one wake-up per
    interval, so accuracy costs no extra wake-ups in the common case.
    """
    loop = asyncio.get_running_loop()
    next_ping_at = loop.time() + heartbeat.interval_seconds
    # is_stale() compares with a strict `>`, so waking exactly ON the
    # deadline can read as not-yet-stale and cost an extra zero-delay pass.
    # Wake a hair after it instead.
    DEADLINE_EPSILON = 0.01

    while True:
        until_stale = heartbeat.seconds_until_stale(connection_id)
        delay = next_ping_at - loop.time()
        if until_stale is not None:
            delay = min(delay, until_stale + DEADLINE_EPSILON)
        # Never busy-spin: a deadline already in the past yields 0, and the
        # check below runs immediately.
        await asyncio.sleep(max(0.0, delay))

        if heartbeat.is_stale(connection_id):
            logger.warning(f"WebSocket {connection_id} stale — closing")
            await websocket.close(code=1001, reason="Heartbeat timeout")
            return

        # Woke for the timeout deadline, not the ping deadline — the pong
        # is still outstanding but not yet late. Re-evaluate rather than
        # sending an extra ping ahead of schedule.
        if loop.time() < next_ping_at:
            continue
        # safe_send_text pre-checks the connection state and classifies
        # failures (#3870): a bare send_text() on a just-disconnected
        # socket raises RuntimeError("Cannot call 'send' once a close
        # message has been sent."), and the old blanket `except Exception:
        # return` swallowed that indistinguishably from a genuine encoder
        # or payload error. safe_send_text logs a real close at debug and
        # anything else at warning, so genuine bugs stay visible.
        if not await safe_send_text(websocket, {"type": "ping"}):
            return  # Connection already dead, or the send genuinely failed
        heartbeat.mark_ping(connection_id)
        # Fixed cadence from the scheduled time, not from now, so a slow
        # send does not let the ping interval drift outward over a long
        # session.
        next_ping_at += heartbeat.interval_seconds


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

    heartbeat_task = spawn_background_task(
        run_heartbeat_loop(websocket, heartbeat, connection_id),
        name=f"ws_heartbeat_{connection_id}",
    )

    # Everything below is best-effort (each push is already independently
    # guarded) and should never actually raise — but if it ever does, don't
    # leak heartbeat_task: the caller has no access to it once this function
    # raises, so it can never be cancelled from outside (#4771).
    try:
        # Immediately send current enhancement settings so a reconnecting
        # frontend syncs its Redux store without waiting for the next
        # broadcast (fixes #2507).
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
                # Best-effort: don't fail the connection (#4368 — was a bare
                # pass, hiding genuine send failures from debugging).
                logger.debug("Initial enhancement-settings push failed", exc_info=True)

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
                # Best-effort: don't fail the connection (#4368 — was a bare
                # pass, hiding genuine send failures from debugging).
                logger.debug("Initial player-state push failed", exc_info=True)
    except Exception:
        heartbeat_task.cancel()
        raise

    return connection_id, heartbeat, heartbeat_task


async def dispatch_message(
    websocket: WebSocket,
    message: dict[str, Any],
    state: StreamState,
    deps: WSDeps,
    heartbeat: HeartbeatManager,
    connection_id: str,
    job_subscriptions: dict[str, Callable[..., Any]],
) -> None:
    """Route one parsed WS message to its handler by `type`."""
    msg_type = message.get("type")

    if msg_type == "ping":
        await msg_handlers.handle_ping(websocket, heartbeat, connection_id)
    elif msg_type == "pong":
        msg_handlers.handle_pong(heartbeat, connection_id)
    elif msg_type == "heartbeat":
        msg_handlers.handle_heartbeat(heartbeat, connection_id)
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
        await msg_handlers.handle_subscribe_job_progress(websocket, message, deps, job_subscriptions)
    else:
        await msg_handlers.handle_unknown(websocket, message)


async def teardown_connection(
    websocket: WebSocket,
    heartbeat_task: asyncio.Task[None],
    state: StreamState,
    get_processing_engine: Callable[..., Any],
    job_subscriptions: dict[str, Callable[..., Any]],
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
    #
    # #4704: this is deliberately a lock-split variant of the teardown that
    # playback_commands._cancel_prior_task expresses in one block. It runs at
    # DISCONNECT, not mid-stream, so the registries it clears below can be
    # cleared outside `active_tasks_lock` — no successor stream is about to
    # register into them, which is the race the mid-stream helper guards
    # against. Each half is independently try/except'd so one failing cleanup
    # cannot skip the rest of a disconnect.
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
        state.active_stream_settings.pop(ws_id, None)  # #4742
    except Exception:
        logger.warning("Stream-event cleanup failed", exc_info=True)

    # Clean up rate limiter (fixes #2156)
    try:
        rate_limiter.cleanup(websocket)
    except Exception:
        logger.warning("Rate-limiter cleanup failed", exc_info=True)
        # Best-effort second pass keyed on the ws_id we already derived above,
        # so the bucket doesn't leak forever if cleanup() keeps failing
        # (fixes #3906 / BE-MW-17).
        try:
            rate_limiter.force_cleanup(ws_id)
        except Exception:
            logger.warning("Rate-limiter fallback cleanup also failed", exc_info=True)

    # Remove stale progress callbacks on WS disconnect (#3325).
    # Wrap each unregister so one failure doesn't skip the rest.
    #
    # Unregisters THIS connection's own callback per job, not the job_id
    # wholesale (#3868) — other connections may still be subscribed to the
    # same job, and evicting them here would silently stop their
    # `job_progress` events with no error on either side.
    if job_subscriptions:
        processing_engine = get_processing_engine()
        if processing_engine:
            for jid, callback in list(job_subscriptions.items()):
                try:
                    await processing_engine.unregister_progress_callback(jid, callback)
                except Exception:
                    logger.warning(f"Failed to unregister progress callback for {jid}", exc_info=True)

    # Remove from connection manager
    try:
        await manager.disconnect(websocket)
    except Exception:
        logger.warning("manager.disconnect failed", exc_info=True)
