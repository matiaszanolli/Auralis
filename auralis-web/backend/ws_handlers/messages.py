"""
WebSocket Misc Message Handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handlers for message types that don't touch streaming-task state: ping,
pong, heartbeat, and the unknown-type fallback. Extracted verbatim from the
websocket_endpoint dispatch loop in routers/system.py (#4074). There is
deliberately no subscribe_job_progress handler: no frontend sends the frame
or consumes `job_progress` (#5525) — do not re-add a per-connection
subscription surface without a consumer.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

from fastapi import WebSocket

from core.stream_protocol import safe_send_text
from websocket.websocket_protocol import HeartbeatManager
from websocket.websocket_security import send_error_response

logger = logging.getLogger(__name__)


async def handle_ping(websocket: WebSocket, heartbeat: HeartbeatManager, connection_id: str) -> None:
    # A client-initiated ping proves liveness — use mark_alive (not
    # mark_pong) since it is not a response to a server-issued ping and must
    # not clear an outstanding pending_pongs slot (#3866 / BE-WS-5, same
    # rationale as handle_heartbeat below). Sibling gap fixed alongside
    # #4786: client pings previously did not count as liveness at all.
    heartbeat.mark_alive(connection_id)
    await safe_send_text(websocket, {"type": "pong"})


def handle_pong(heartbeat: HeartbeatManager, connection_id: str) -> None:
    heartbeat.mark_pong(connection_id)


def handle_heartbeat(heartbeat: HeartbeatManager, connection_id: str) -> None:
    # Keepalive from RealTimeAnalysisStream — use mark_alive (not
    # mark_pong) so an outstanding ping is not masked (#3866 / BE-WS-5).
    heartbeat.mark_alive(connection_id)


async def handle_unknown(websocket: WebSocket, message: dict[str, Any]) -> None:
    # Unknown message type (fixes #2417). The raw value is logged server-side
    # for forensics only — never reflected to the client, which would let a
    # caller-controlled string reach frontend log rendering (fixes #3910 /
    # BE-EH-12, sibling of the caller-controlled reflection closed in #3332).
    raw_type = message.get("type", "unknown")
    logger.warning(f"Unknown WebSocket message type: {raw_type!r}")
    await send_error_response(websocket, "unknown_message_type", "Unrecognised message type")
