"""
WebSocket Message Validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Frame-level validation for inbound WebSocket messages (size, JSON depth,
schema) and the standardized error reply.

Fixes #2156: Unvalidated WebSocket message content and size

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import logging
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from config.limits import WS_MAX_MESSAGE_SIZE
from config.log_throttle import warn_throttled
from schemas import WebSocketErrorResponse, WebSocketMessageBase

logger = logging.getLogger(__name__)

# The size and rate limits live in config/limits.py (#3902) with their
# rationale; only the JSON nesting bound is local to this module.
MAX_JSON_DEPTH = 32


def _json_nesting_exceeds(data: str, max_depth: int) -> bool:
    """Detect excessive object/array nesting without recursively parsing JSON."""
    depth = 0
    in_string = False
    escaped = False
    for char in data:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > max_depth:
                return True
        elif char in "]}":
            depth -= 1
    return False


async def _reject(
    websocket: WebSocket, code: str, message: str, may_reply: Callable[[], bool] | None
) -> None:
    """Answer a rejected frame with an error frame, unless the sender's budget is spent."""
    if may_reply is None or may_reply():
        await send_error_response(websocket, code, message)


async def validate_and_parse_message(
    data: str,
    websocket: WebSocket,
    max_size: int = WS_MAX_MESSAGE_SIZE,
    may_reply: Callable[[], bool] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Validate and parse a WebSocket message.

    Security checks:
    - Message size limit (64KB default)
    - JSON parsing safety
    - Schema validation
    - Message type whitelist

    Args:
        data: Raw message data (text)
        websocket: WebSocket connection (for error responses)
        max_size: Maximum allowed message size in bytes
        may_reply: Called once per rejected frame; it charges that frame to the
            caller's rate limiter and returns False when the budget is spent,
            in which case the rejection is not answered with an error frame (#5915)

    Returns:
        Tuple of (parsed_message: dict | None, error: str | None)
    """
    # Check message size (security: prevent memory exhaustion)
    message_size = len(data.encode('utf-8'))
    if message_size > max_size:
        error_msg = f"Message size {message_size} bytes exceeds maximum {max_size} bytes"
        warn_throttled(logger, "ws.oversized", f"Rejected oversized WebSocket message: {error_msg}")
        await _reject(websocket, "message_too_large", error_msg, may_reply)
        return None, error_msg

    if _json_nesting_exceeds(data, MAX_JSON_DEPTH):
        error_msg = f"JSON nesting exceeds maximum depth {MAX_JSON_DEPTH}"
        warn_throttled(logger, "ws.nested", "Rejected deeply nested WebSocket message")
        await _reject(websocket, "message_too_complex", error_msg, may_reply)
        return None, error_msg

    # Parse JSON (security: catch malformed JSON)
    try:
        message = json.loads(data)
    except (json.JSONDecodeError, RecursionError) as e:
        error_msg = f"Invalid JSON: {e}"
        warn_throttled(logger, "ws.invalid_json", f"Failed to parse WebSocket message: {error_msg}")
        await _reject(websocket, "invalid_json", "Message must be valid JSON", may_reply)
        return None, error_msg

    # Validate message structure (security: enforce schema)
    try:
        validated = WebSocketMessageBase.model_validate(message)
        return validated.model_dump(), None
    except ValidationError as e:
        error_msg = f"Schema validation failed: {e}"
        warn_throttled(logger, "ws.invalid_schema", f"WebSocket message validation failed: {error_msg}")
        await _reject(
            websocket, "validation_error", "Invalid message format or unknown message type", may_reply
        )
        return None, error_msg


async def receive_text_frame(websocket: WebSocket, may_reply: Callable[[], bool]) -> str | None:
    """Receive one frame and return its text, or ``None`` for a binary frame.

    A binary frame arrives as ``{"type": "websocket.receive", "bytes": ...}``
    with no ``"text"`` key, so ``receive_text()`` raises a bare KeyError that
    tears the connection down with no error frame (#4741). It is answered with
    ``unsupported_frame_type`` instead, subject to ``may_reply`` (#5915).

    Raises:
        WebSocketDisconnect: The peer closed the connection.
    """
    frame = await websocket.receive()
    if frame["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(frame.get("code", 1000), frame.get("reason"))
    if "text" not in frame:
        await _reject(
            websocket,
            "unsupported_frame_type",
            "Binary WebSocket frames are not supported; send JSON text frames",
            may_reply,
        )
        return None
    return str(frame["text"])


async def send_error_response(
    websocket: WebSocket,
    error_code: str,
    message: str,
    command: str | None = None,
) -> None:
    """
    Send a standardized error response to the WebSocket client.

    Args:
        websocket: WebSocket connection
        error_code: Error code (e.g., "validation_error", "rate_limit_exceeded")
        message: Human-readable error message
        command: Type of the client message being rejected, when known (#5885)
    """
    try:
        error_response = WebSocketErrorResponse(
            error=error_code,
            message=message,
            command=command,
        )
        await websocket.send_text(error_response.model_dump_json())
    except Exception as e:
        logger.error(f"Failed to send error response to WebSocket: {e}")
