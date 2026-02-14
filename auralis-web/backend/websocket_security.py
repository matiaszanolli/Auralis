"""
WebSocket Security Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rate limiting and validation utilities for WebSocket connections.

Fixes #2156: Unvalidated WebSocket message content and size

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import logging
import time
from typing import Any

from fastapi import WebSocket
from pydantic import ValidationError
from schemas import WebSocketErrorResponse, WebSocketMessageBase

logger = logging.getLogger(__name__)

# Security limits
MAX_MESSAGE_SIZE = 64 * 1024  # 64KB max message size
MAX_MESSAGES_PER_SECOND = 10  # 10 messages per second per connection
MESSAGE_WINDOW_SECONDS = 1.0  # Time window for rate limiting


class WebSocketRateLimiter:
    """
    Per-connection rate limiter for WebSocket messages.

    Tracks message timestamps per connection and enforces rate limits.
    """

    def __init__(
        self,
        max_messages_per_second: int = MAX_MESSAGES_PER_SECOND,
        window_seconds: float = MESSAGE_WINDOW_SECONDS
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            max_messages_per_second: Maximum messages allowed per second
            window_seconds: Time window for rate limiting
        """
        self.max_messages_per_second = max_messages_per_second
        self.window_seconds = window_seconds
        # Track message timestamps per WebSocket ID
        self.message_log: dict[int, list[float]] = {}

    def check_rate_limit(self, websocket: WebSocket) -> tuple[bool, str | None]:
        """
        Check if a message should be allowed based on rate limit.

        Args:
            websocket: WebSocket connection

        Returns:
            Tuple of (allowed: bool, error_message: str | None)
        """
        ws_id = id(websocket)
        now = time.time()
        cutoff = now - self.window_seconds

        # Initialize log for this connection if needed
        if ws_id not in self.message_log:
            self.message_log[ws_id] = []

        # Remove old timestamps outside the window
        self.message_log[ws_id] = [
            ts for ts in self.message_log[ws_id]
            if ts > cutoff
        ]

        # Check if rate limit exceeded
        if len(self.message_log[ws_id]) >= self.max_messages_per_second:
            return False, (
                f"Rate limit exceeded: maximum {self.max_messages_per_second} "
                f"messages per {self.window_seconds}s"
            )

        # Record this message timestamp
        self.message_log[ws_id].append(now)
        return True, None

    def cleanup(self, websocket: WebSocket) -> None:
        """
        Clean up rate limit tracking for a disconnected WebSocket.

        Args:
            websocket: WebSocket connection
        """
        ws_id = id(websocket)
        if ws_id in self.message_log:
            del self.message_log[ws_id]
            logger.debug(f"Cleaned up rate limiter for WebSocket {ws_id}")


async def validate_and_parse_message(
    data: str,
    websocket: WebSocket,
    max_size: int = MAX_MESSAGE_SIZE
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

    Returns:
        Tuple of (parsed_message: dict | None, error: str | None)
    """
    # Check message size (security: prevent memory exhaustion)
    message_size = len(data.encode('utf-8'))
    if message_size > max_size:
        error_msg = f"Message size {message_size} bytes exceeds maximum {max_size} bytes"
        logger.warning(f"Rejected oversized WebSocket message: {error_msg}")
        await send_error_response(
            websocket,
            "message_too_large",
            error_msg
        )
        return None, error_msg

    # Parse JSON (security: catch malformed JSON)
    try:
        message = json.loads(data)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON: {e}"
        logger.warning(f"Failed to parse WebSocket message: {error_msg}")
        await send_error_response(
            websocket,
            "invalid_json",
            "Message must be valid JSON"
        )
        return None, error_msg

    # Validate message structure (security: enforce schema)
    try:
        validated = WebSocketMessageBase.model_validate(message)
        return validated.model_dump(), None
    except ValidationError as e:
        error_msg = f"Schema validation failed: {e}"
        logger.warning(f"WebSocket message validation failed: {error_msg}")
        await send_error_response(
            websocket,
            "validation_error",
            "Invalid message format or unknown message type"
        )
        return None, error_msg


async def send_error_response(
    websocket: WebSocket,
    error_code: str,
    message: str
) -> None:
    """
    Send a standardized error response to the WebSocket client.

    Args:
        websocket: WebSocket connection
        error_code: Error code (e.g., "validation_error", "rate_limit_exceeded")
        message: Human-readable error message
    """
    try:
        error_response = WebSocketErrorResponse(
            error=error_code,
            message=message
        )
        await websocket.send_text(error_response.model_dump_json())
    except Exception as e:
        logger.error(f"Failed to send error response to WebSocket: {e}")
