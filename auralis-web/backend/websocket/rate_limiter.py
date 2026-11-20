"""
WebSocket Rate Limiter
~~~~~~~~~~~~~~~~~~~~~~

Per-connection and per-client-IP message rate limiting for WebSocket
connections.

Fixes #2156: Unvalidated WebSocket message content and size

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
import time

from fastapi import WebSocket
from config.limits import WS_MAX_MESSAGES_PER_SECOND, WS_MESSAGE_WINDOW_SECONDS
from core.audio_stream_controller import ws_id as _stable_ws_id

logger = logging.getLogger(__name__)

#: Every this many checks, per-IP buckets with no message inside the window are dropped.
IP_LOG_SWEEP_INTERVAL = 256


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
        max_messages_per_second: int = WS_MAX_MESSAGES_PER_SECOND,
        window_seconds: float = WS_MESSAGE_WINDOW_SECONDS,
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
        self._checks = 0
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

            # An IP key outlives its connections on purpose (#3811) but must not outlive its
            # window: sweep the idle ones so distinct client addresses cannot accumulate (#6171).
            self._checks += 1
            if self._checks % IP_LOG_SWEEP_INTERVAL == 0:
                for ip in [ip for ip, log in self.ip_message_log.items() if not log or log[-1] <= cutoff]:
                    del self.ip_message_log[ip]

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
