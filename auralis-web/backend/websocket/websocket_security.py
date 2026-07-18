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
import threading
import time
from typing import Any

from fastapi import WebSocket
from pydantic import ValidationError
from core.audio_stream_controller import ws_id as _stable_ws_id
from schemas import WebSocketErrorResponse, WebSocketMessageBase

logger = logging.getLogger(__name__)

# Security limits
MAX_MESSAGE_SIZE = 64 * 1024  # 64KB max message size
MAX_MESSAGES_PER_SECOND = 10  # 10 messages per second per connection
MESSAGE_WINDOW_SECONDS = 1.0  # Time window for rate limiting


class WebSocketRateLimiter:
    """
    Per-connection rate limiter for WebSocket messages.

    Tracks message timestamps per connection and enforces rate limits. Also
    maintains a per-client-IP fallback bucket (fixes #3811): the
    per-connection bucket alone is trivially bypassed by closing and
    reopening the WebSocket, since a fresh connection gets a fresh (empty)
    bucket keyed on its own connection id. The IP bucket persists across
    reconnects — only `cleanup()`'s per-connection bucket is cleared on
    disconnect — so a client can't outrun the limit by cycling connections.
    """

    def __init__(
        self,
        max_messages_per_second: int = MAX_MESSAGES_PER_SECOND,
        window_seconds: float = MESSAGE_WINDOW_SECONDS,
        max_messages_per_second_per_ip: int | None = None,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            max_messages_per_second: Maximum messages allowed per second per connection
            window_seconds: Time window for rate limiting
            max_messages_per_second_per_ip: Aggregate ceiling across all current and
                recent connections from the same client IP, surviving reconnects
                (fixes #3811). Defaults to 3x the per-connection limit, allowing
                headroom for a few legitimate simultaneous connections (e.g. multiple
                tabs) from the same client without permitting an unbounded
                reconnect-loop bypass.
        """
        self.max_messages_per_second = max_messages_per_second
        self.window_seconds = window_seconds
        self.max_messages_per_second_per_ip = (
            max_messages_per_second_per_ip
            if max_messages_per_second_per_ip is not None
            else max_messages_per_second * 3
        )
        # Track message timestamps per WebSocket ID
        self.message_log: dict[str, list[float]] = {}
        # Track message timestamps per client IP — NOT cleared per-connection
        # cleanup, so it persists across a close/reopen cycle (#3811).
        self.ip_message_log: dict[str, list[float]] = {}
        # Lock to protect message_log during concurrent access (#2442)
        self._lock = threading.Lock()

    @staticmethod
    def _client_ip(websocket: WebSocket) -> str:
        # getattr-based, not a direct .client access: test doubles and other
        # minimal WebSocket-like objects may not define `.client` at all
        # (unlike a real Starlette WebSocket, where it's always present but
        # may be None).
        client = getattr(websocket, "client", None)
        return client.host if client else "unknown"

    def check_rate_limit(self, websocket: WebSocket) -> tuple[bool, str | None]:
        """
        Check if a message should be allowed based on rate limit.

        Args:
            websocket: WebSocket connection

        Returns:
            Tuple of (allowed: bool, error_message: str | None)
        """
        with self._lock:  # Thread-safe access to message_log (#2442)
            ws_id = _stable_ws_id(websocket)
            client_ip = self._client_ip(websocket)
            now = time.time()
            cutoff = now - self.window_seconds

            # Initialize logs for this connection/IP if needed
            if ws_id not in self.message_log:
                self.message_log[ws_id] = []
            if client_ip not in self.ip_message_log:
                self.ip_message_log[client_ip] = []

            # Remove old timestamps outside the window
            self.message_log[ws_id] = [
                ts for ts in self.message_log[ws_id]
                if ts > cutoff
            ]
            self.ip_message_log[client_ip] = [
                ts for ts in self.ip_message_log[client_ip]
                if ts > cutoff
            ]

            # Check per-connection limit
            if len(self.message_log[ws_id]) >= self.max_messages_per_second:
                return False, (
                    f"Rate limit exceeded: maximum {self.max_messages_per_second} "
                    f"messages per {self.window_seconds}s"
                )

            # Check per-IP limit (fixes #3811 — survives reconnects)
            if len(self.ip_message_log[client_ip]) >= self.max_messages_per_second_per_ip:
                return False, (
                    f"Rate limit exceeded: maximum {self.max_messages_per_second_per_ip} "
                    f"messages per {self.window_seconds}s from this client"
                )

            # Record this message timestamp in both buckets
            self.message_log[ws_id].append(now)
            self.ip_message_log[client_ip].append(now)
            return True, None

    def cleanup(self, websocket: WebSocket) -> None:
        """
        Clean up rate limit tracking for a disconnected WebSocket.

        Only clears the per-connection bucket — the per-IP bucket
        deliberately survives so a reconnect doesn't reset it (#3811).

        Args:
            websocket: WebSocket connection
        """
        self.force_cleanup(_stable_ws_id(websocket))

    def force_cleanup(self, ws_id: str) -> None:
        """
        Clear a connection's rate-limit bucket by its already-known ws_id.

        Used as a fallback when cleanup() itself raises (fixes #3906 /
        BE-MW-17): callers that already computed ws_id elsewhere (e.g. the
        WS teardown sequence) can retry the removal directly without
        re-deriving it from the websocket object, so the bucket doesn't leak
        forever if whatever made cleanup() fail is still failing.

        Args:
            ws_id: Stable connection id, as returned by ws_id(websocket)
        """
        with self._lock:  # Thread-safe access to message_log (#2442)
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
