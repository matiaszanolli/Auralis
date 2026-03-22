"""
WebSocket Heartbeat Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Heartbeat manager for WebSocket connection health monitoring.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HeartbeatManager:
    """Manages heartbeat for WebSocket connections."""

    def __init__(self, interval_seconds: int = 30, timeout_seconds: int = 10):
        """
        Initialize heartbeat manager.

        Args:
            interval_seconds: Heartbeat interval in seconds (default 30s)
            timeout_seconds: Timeout before considering connection dead (default 10s)
        """
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self.last_heartbeat: dict[str, datetime] = {}
        self.pending_pongs: dict[str, datetime] = {}

    def mark_ping(self, connection_id: str) -> None:
        """Mark when ping was sent."""
        self.last_heartbeat[connection_id] = datetime.now(timezone.utc)
        self.pending_pongs[connection_id] = datetime.now(timezone.utc)

    def mark_pong(self, connection_id: str) -> bool:
        """
        Mark pong response received.

        Returns:
            True if pong was within timeout, False if it was late
        """
        if connection_id not in self.pending_pongs:
            return False

        elapsed = (datetime.now(timezone.utc) - self.pending_pongs[connection_id]).total_seconds()
        del self.pending_pongs[connection_id]

        return elapsed < self.timeout_seconds

    def is_alive(self, connection_id: str) -> bool:
        """Check if connection is alive (has recent activity)."""
        if connection_id not in self.last_heartbeat:
            return False

        elapsed = (datetime.now(timezone.utc) - self.last_heartbeat[connection_id]).total_seconds()
        return elapsed < (self.interval_seconds * 2)  # Allow 2 intervals before timeout

    def is_stale(self, connection_id: str) -> bool:
        """Check if connection has pending pong for too long."""
        if connection_id not in self.pending_pongs:
            return False

        elapsed = (datetime.now(timezone.utc) - self.pending_pongs[connection_id]).total_seconds()
        return elapsed > self.timeout_seconds
