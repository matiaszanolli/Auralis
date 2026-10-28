"""
System Router - WebSocket
~~~~~~~~~~~~~~~~~~~~~~~~~

WebSocket endpoint for real-time communication.
Health and version endpoints have been moved to routers/health.py.
"""

import asyncio
import logging
from typing import Any
from collections.abc import Callable

from config.globals import WebSocketOriginRejected
from config.limits import WS_MAX_MESSAGES_PER_SECOND
from core.audio_stream_controller import ws_id as _ws_id
from core.stream_gates import stream_chunk_cancel_events, stream_flow_events, stream_pause_events
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from websocket.websocket_security import (
    WebSocketRateLimiter,
    receive_text_frame,
    send_error_response,
    validate_and_parse_message,
)
from ws_handlers import connection as ws_connection
from ws_handlers.context import StreamState, WSDeps

from .system_deps import _SystemDeps, _deps, _get_deps  # noqa: F401
from .system_streams import (  # noqa: F401
    _active_streaming_tasks,
    _active_streaming_tasks_lock,
    _active_streaming_track_ids,
    stream_audio,
    stream_from_position,
    stream_normal,
)

logger = logging.getLogger(__name__)

# Global rate limiter for all WebSocket connections (fixes #2156)
_rate_limiter = WebSocketRateLimiter(max_messages_per_second=WS_MAX_MESSAGES_PER_SECOND)

# Protocol-critical control frames, exempt from rate limiting (#4786). They
# are small, fixed-size, and a dropped one has an outsized effect: a
# rate-limited pong never reaches heartbeat.mark_pong(), so the connection
# gets force-closed by the next heartbeat tick as if it had gone stale.
# buffer_full/buffer_ready are exempt (#5863): they are the flow-control
# pair that gates audio delivery itself — a dropped resume signal parks
# the stream (the client sends them at most a few times per track).
_RATE_LIMIT_EXEMPT_TYPES = frozenset({"ping", "pong", "heartbeat", "buffer_full", "buffer_ready"})


# ============================================================================
# WebSocket endpoint
# ============================================================================

async def websocket_endpoint(
    websocket: WebSocket,
    deps: _SystemDeps = Depends(_get_deps),
) -> None:
    """WebSocket endpoint for real-time communication.

    Handles heartbeat, enhancement settings sync, player state sync, and
    streaming commands (play_enhanced, play_normal, seek, stop,
    pause/resume). Connection lifecycle and per-message-type dispatch
    live in ws_handlers/ (#4074); this function wires them together for
    one connection.
    """
    # Populated once setup_connection() returns; guards the finally
    # block below so a setup failure (before state/deps exist) doesn't
    # attempt a teardown that needs them (#4771).
    heartbeat_task: asyncio.Task[None] | None = None
    state: StreamState | None = None

    try:
        # setup_connection() now runs INSIDE the try (was previously
        # before it): if manager.connect() or the initial sync pushes
        # ever raised after accept(), teardown_connection would never
        # run and the spawned heartbeat_task would leak for the process
        # lifetime. setup_connection() also self-guards by cancelling
        # its own heartbeat_task on internal failure (#4771).
        connection_id, heartbeat, heartbeat_task = await ws_connection.setup_connection(
            websocket, deps.manager, deps.get_enhancement_settings, deps.get_state_manager
        )
        state = StreamState(
            active_tasks=_active_streaming_tasks,
            active_tasks_lock=_active_streaming_tasks_lock,
            active_track_ids=_active_streaming_track_ids,
            pause_events=stream_pause_events,
            flow_events=stream_flow_events,
            chunk_cancel_events=stream_chunk_cancel_events,
        )
        ws_deps = WSDeps(
            get_repository_factory=deps.get_repository_factory,
            get_enhancement_settings=deps.get_enhancement_settings,
            get_processing_engine=deps.get_processing_engine,
            stream_audio=stream_audio,
            stream_normal=stream_normal,
            stream_from_position=stream_from_position,
            # #4542: the play handlers broadcast mastering_recommendation, which
            # goes to every client rather than just this socket.
            broadcast_manager=deps.manager,
        )

        # A frame that fails validation is charged to the rate limiter and, once
        # it is exhausted, dropped without a reply: an unmetered error response
        # per bad frame was a free request/response loop (#5915).
        def _may_reply() -> bool:
            return _rate_limiter.check_rate_limit(websocket)[0]

        while True:
            # receive_text() KeyErrors on a binary frame and tears the whole
            # connection down (#4741); receive_text_frame answers it instead.
            raw_data = await receive_text_frame(websocket, _may_reply)
            if raw_data is None:
                continue

            # Security: Validate message size and structure (fixes #2156).
            # Parsed BEFORE rate-limiting (#4786) so the type is known:
            # ping/pong/heartbeat are protocol-critical and exempt from
            # the rate limit below. Rate-limiting on the raw text used to
            # run first and applied uniformly to every message type,
            # including replies to the server's own heartbeat ping — a
            # burst of unrelated messages (e.g. buffer_full/buffer_ready
            # during a seek-bar drag) could silently drop the client's
            # pong, and since heartbeat.mark_pong() then never ran, the
            # next heartbeat tick force-closed the connection as if it
            # had gone stale.
            message, error = await validate_and_parse_message(raw_data, websocket, may_reply=_may_reply)
            if error or not message:
                continue

            # Security: Check rate limit (fixes #2156), except for
            # protocol-critical control frames (#4786).
            if message.get("type") not in _RATE_LIMIT_EXEMPT_TYPES:
                allowed, error_msg = _rate_limiter.check_rate_limit(websocket)
                if not allowed:
                    logger.warning(f"Rate limit exceeded for WebSocket {_ws_id(websocket)}: {error_msg}")
                    # check_rate_limit types its reason as `str | None`; it
                    # is always set when allowed is False, but fall back so
                    # the client still gets a message either way.
                    await send_error_response(
                        websocket, "rate_limit_exceeded", error_msg or "Rate limit exceeded",
                        command=message.get("type"),
                    )
                    continue

            try:
                await ws_connection.dispatch_message(
                    websocket, message, state, ws_deps, heartbeat, connection_id
                )
            except (WebSocketDisconnect, RuntimeError):
                # Genuinely fatal transport errors — let the outer
                # handler's dedicated branches deal with them.
                raise
            except Exception as e:
                # #4771: a single handler's exception (e.g. handle_seek) used to
                # unwind into teardown_connection and silently kill the whole
                # connection, which the client misread as a network drop.
                # Report it, naming the command (#5885), and keep the connection.
                logger.error(
                    f"WebSocket handler error for message type "
                    f"{message.get('type')!r}: {e}", exc_info=True
                )
                await send_error_response(
                    websocket, "internal_error", "Command failed", command=message.get("type"),
                )
                continue

    except WebSocketOriginRejected as e:
        # #4703: the handshake was refused inside setup_connection before
        # the heartbeat task was spawned, so there is
        # nothing to tear down — both `finally` branches below are already
        # guarded by their None checks. Caught explicitly (and ahead of the
        # generic handlers) so a policy rejection is not logged as an
        # "Unexpected WebSocket error" with a stack trace; connect() has
        # already logged the specific reason at warning level.
        logger.debug(f"WebSocket handshake rejected: {e}")
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except RuntimeError as e:
        logger.warning(f"WebSocket runtime error: {e}")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
    finally:
        if state is not None and heartbeat_task is not None:
            await ws_connection.teardown_connection(
                websocket, heartbeat_task, state, deps.manager, _rate_limiter,
            )
        elif heartbeat_task is not None:
            # setup_connection() returned a heartbeat_task but raised
            # before state could be constructed — nothing else to tear
            # down, but the task must not leak (#4771).
            heartbeat_task.cancel()



# ============================================================================
# Router factory
# ============================================================================

def create_system_router(
    manager: Any,
    get_processing_engine: Callable[..., Any],
    get_repository_factory: Callable[..., Any] | None = None,
    get_state_manager: Callable[..., Any] | None = None,
    get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    """Create system router (WebSocket endpoint only).

    Health and version routes are registered separately via create_health_router().
    """
    # Fresh router per factory call (#4361); the handler reaches this call's
    # collaborators through RouterDeps rather than closure capture (#5832).
    deps = _SystemDeps(
        manager,
        get_processing_engine,
        get_repository_factory,
        get_state_manager,
        get_enhancement_settings,
    )
    router = APIRouter(tags=["system"], dependencies=[Depends(_deps.bind(deps))])
    router.add_api_websocket_route("/ws", websocket_endpoint)
    return router
