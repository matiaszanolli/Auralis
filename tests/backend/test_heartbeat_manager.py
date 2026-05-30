"""
Tests for HeartbeatManager (auralis-web/backend/websocket/websocket_protocol.py)

This file supersedes test_websocket_protocol_b3.py (#3858 / BE-TC-3).  The
original 514-LOC file contained 5 dead test classes (TestWSMessage,
TestConnectionInfo, TestRateLimiter, TestWebSocketProtocol, TestMessageTypes)
referencing B.3 protocol classes that were never merged into the codebase;
those are removed here, leaving only the valid HeartbeatManager tests.

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


# ---------------------------------------------------------------------------
# Regression: mark_alive must not clear pending_pongs (#3866 / BE-WS-5)
# ---------------------------------------------------------------------------

class TestMarkAlive:
    """mark_alive records liveness but must not mask an outstanding ping."""

    def test_mark_alive_updates_last_heartbeat(self):
        """mark_alive must update last_heartbeat so is_alive() returns True."""
        hb = HeartbeatManager(interval_seconds=30)
        conn_id = "test-alive"

        hb.mark_alive(conn_id)

        assert hb.is_alive(conn_id) is True

    def test_mark_alive_does_not_clear_pending_pongs(self):
        """
        mark_alive on a keepalive frame must NOT clear pending_pongs.

        Before this fix, the heartbeat handler called mark_pong(), which
        deleted the pending_pongs entry armed by mark_ping().  This masked
        dead connections until the next ping cycle (fixes #3866).
        """
        hb = HeartbeatManager(timeout_seconds=5)
        conn_id = "test-alive-no-clear"

        # Arm a ping (simulating the heartbeat task sending a server-side ping)
        hb.mark_ping(conn_id)
        assert conn_id in hb.pending_pongs, "pending_pongs must be set after mark_ping"

        # A keepalive frame arrives — must NOT clear the pending pong entry
        hb.mark_alive(conn_id)
        assert conn_id in hb.pending_pongs, (
            "mark_alive must not clear pending_pongs (#3866 — "
            "calling mark_pong on heartbeat masked dead connections)"
        )

    def test_mark_pong_still_clears_pending_pongs(self):
        """An actual pong response (not heartbeat) must still clear pending_pongs."""
        hb = HeartbeatManager(timeout_seconds=5)
        conn_id = "test-pong-clears"

        hb.mark_ping(conn_id)
        assert conn_id in hb.pending_pongs

        result = hb.mark_pong(conn_id)

        assert result is True
        assert conn_id not in hb.pending_pongs

    def test_is_stale_not_masked_by_mark_alive(self):
        """
        After mark_ping + mark_alive (timeout elapses), is_stale() must return
        True — the keepalive must not reset the stale-detection clock.
        """
        hb = HeartbeatManager(timeout_seconds=0.1)
        conn_id = "test-stale-not-masked"

        hb.mark_ping(conn_id)
        hb.mark_alive(conn_id)  # keepalive arrives — must not clear pending_pongs
        time.sleep(0.15)        # timeout elapses

        assert hb.is_stale(conn_id) is True, (
            "is_stale must still trigger after mark_alive — pending_pong untouched"
        )
