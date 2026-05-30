"""
Tests for HeartbeatManager (auralis-web/backend/websocket/websocket_protocol.py)

This file supersedes test_websocket_protocol_b3.py (#3858 / BE-TC-3).  The
original 514-LOC file contained 5 dead test classes (TestWSMessage,
TestConnectionInfo, TestRateLimiter, TestWebSocketProtocol, TestMessageTypes)
referencing B.3 protocol classes that were never merged into the codebase;
those are removed here, leaving only the 8 valid HeartbeatManager tests.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from websocket.websocket_protocol import HeartbeatManager


class TestHeartbeatManager:
    """Test heartbeat management."""

    def test_heartbeat_creation(self):
        """Test creating heartbeat manager."""
        hb = HeartbeatManager(interval_seconds=30, timeout_seconds=10)

        assert hb.interval_seconds == 30
        assert hb.timeout_seconds == 10

    def test_heartbeat_mark_ping(self):
        """Test marking ping sent."""
        hb = HeartbeatManager()
        conn_id = "test-conn"

        hb.mark_ping(conn_id)

        assert conn_id in hb.last_heartbeat
        assert conn_id in hb.pending_pongs

    def test_heartbeat_mark_pong_success(self):
        """Test marking successful pong response."""
        hb = HeartbeatManager(timeout_seconds=10)
        conn_id = "test-conn"

        hb.mark_ping(conn_id)
        result = hb.mark_pong(conn_id)

        assert result is True
        assert conn_id not in hb.pending_pongs

    def test_heartbeat_mark_pong_no_pending(self):
        """Test marking pong when no ping was sent."""
        hb = HeartbeatManager()
        conn_id = "test-conn"

        result = hb.mark_pong(conn_id)

        assert result is False

    def test_heartbeat_is_alive(self):
        """Test checking if connection is alive."""
        hb = HeartbeatManager(interval_seconds=30)
        conn_id = "test-conn"

        hb.mark_ping(conn_id)
        hb.mark_pong(conn_id)

        assert hb.is_alive(conn_id) is True

    def test_heartbeat_is_stale(self):
        """Test detecting stale heartbeat."""
        hb = HeartbeatManager(timeout_seconds=1)
        conn_id = "test-conn"

        hb.mark_ping(conn_id)
        # Don't send pong, wait for timeout

        # Immediately after ping, not stale
        assert hb.is_stale(conn_id) is False

    def test_heartbeat_no_response(self):
        """Test detecting missing pong response."""
        hb = HeartbeatManager(timeout_seconds=0.1)
        conn_id = "test-conn"

        hb.mark_ping(conn_id)
        # Wait for timeout
        time.sleep(0.15)

        # Should be marked as stale
        assert hb.is_stale(conn_id) is True
