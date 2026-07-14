"""
WebSocket Misc Message Handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handlers for message types that don't touch streaming-task state: ping,
pong, heartbeat, subscribe_job_progress, and the unknown-type fallback.
Extracted verbatim from the websocket_endpoint dispatch loop in
routers/system.py (#4074).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import logging
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from websocket.websocket_protocol import HeartbeatManager
from websocket.websocket_security import send_error_response

from .context import WSDeps

logger = logging.getLogger(__name__)


async def handle_ping(websocket: WebSocket) -> None:
    await websocket.send_text(json.dumps({"type": "pong"}))


def handle_pong(heartbeat: HeartbeatManager, connection_id: str) -> None:
    heartbeat.mark_pong(connection_id)


def handle_heartbeat(heartbeat: HeartbeatManager, connection_id: str) -> None:
    # Keepalive from RealTimeAnalysisStream — use mark_alive (not
    # mark_pong) so an outstanding ping is not masked (#3866 / BE-WS-5).
    heartbeat.mark_alive(connection_id)


async def handle_subscribe_job_progress(
    websocket: WebSocket, message: dict[str, Any], deps: WSDeps, subscribed_job_ids: set[str]
) -> None:
    data = message.get("data", {})
    job_id = data.get("job_id")
    # Validate job_id — prior code accepted any value, opening a slow
    # per-session leak and non-string payloads to other WS subscribers
    # (#3520 / BE-NEW-62).
    if not isinstance(job_id, str) or not job_id or len(job_id) > 64:
        await send_error_response(websocket, "invalid_job_id", "Invalid job_id (must be non-empty string, ≤64 chars)")
        return
    processing_engine = deps.get_processing_engine()
    if not processing_engine:
        return

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
    subscribed_job_ids.add(job_id)
    await processing_engine.register_progress_callback(job_id, progress_callback)


async def handle_unknown(websocket: WebSocket, message: dict[str, Any]) -> None:
    # Unknown message type (fixes #2417); sanitize before reflecting to client
    raw_type = message.get("type", "unknown")
    safe_type = str(raw_type)[:32] if isinstance(raw_type, str) else "non-string"
    logger.warning(f"Unknown WebSocket message type: {raw_type!r}")
    await send_error_response(websocket, "unknown_message_type", f"Unknown message type: {safe_type}")
