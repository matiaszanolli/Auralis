"""
Tests for WebSocket Protocol (Phase B.3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for WebSocket message protocol, connection management,
heartbeat, and rate limiting.

Test Coverage:
- Message envelope and serialization
- Connection management and info tracking
- Rate limiting by priority
- Heartbeat management
- Protocol handler and message routing
- Error handling and recovery

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from websocket.websocket_protocol import (
    ConnectionInfo,
    HeartbeatManager,
    MessagePriority,
    MessageType,
    RateLimiter,
    WebSocketProtocol,
    WSMessage,
)

# ============================================================================
# Message Tests
# ============================================================================

class TestWSMessage:
    """Test WebSocket message envelope."""

    def test_message_creation_minimal(self):
        """Test creating message with minimal fields."""
        msg = WSMessage(type=MessageType.PING)

        assert msg.type == MessageType.PING
        assert msg.priority == MessagePriority.NORMAL
        assert msg.correlation_id is not None
        assert msg.timestamp is not None

    def test_message_creation_full(self):
        """Test creating message with all fields."""
        msg = WSMessage(
            type=MessageType.PLAY,
            correlation_id="test-123",
            priority=MessagePriority.HIGH,
            payload={"track_id": 456},
            response_required=True,
            retry_count=1,
            max_retries=3
        )

        assert msg.type == MessageType.PLAY
        assert msg.correlation_id == "test-123"
        assert msg.priority == MessagePriority.HIGH
        assert msg.payload == {"track_id": 456}
        assert msg.response_required is True
        assert msg.retry_count == 1

    def test_message_to_dict(self):
        """Test serializing message to dictionary."""
        msg = WSMessage(
            type=MessageType.SEEK,
            payload={"position": 120.5},
            priority=MessagePriority.HIGH
        )

        data = msg.to_dict()

        assert data["type"] == "seek"
        assert data["priority"] == "high"
        assert data["payload"] == {"position": 120.5}
        assert "correlation_id" in data
        assert "timestamp" in data

    def test_message_from_dict(self):
        """Test deserializing message from dictionary."""
        data = {
            "type": "play",
            "correlation_id": "test-456",
            "priority": "high",
            "payload": {"track_id": 789},
            "response_required": True,
            "timestamp": datetime.utcnow().isoformat()
        }

        msg = WSMessage.from_dict(data)

        assert msg.type == MessageType.PLAY
        assert msg.correlation_id == "test-456"
        assert msg.priority == MessagePriority.HIGH
        assert msg.payload == {"track_id": 789}

    def test_message_round_trip(self):
        """Test message serialization round-trip."""
        original = WSMessage(
            type=MessageType.QUEUE_ADD,
            payload={"track_ids": [1, 2, 3]},
            priority=MessagePriority.NORMAL,
            response_required=True
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = WSMessage.from_dict(data)

        assert restored.type == original.type
        assert restored.correlation_id == original.correlation_id
        assert restored.payload == original.payload
        assert restored.priority == original.priority


# ============================================================================
# Connection Management Tests
# ============================================================================

class TestConnectionInfo:
    """Test connection information tracking."""

    def test_connection_creation(self):
        """Test creating connection info."""
        conn = ConnectionInfo()

        assert conn.connection_id is not None
        assert conn.connected_at is not None
        assert conn.message_count == 0
        assert conn.state == "connected"

    def test_connection_is_active(self):
        """Test checking if connection is active."""
        conn = ConnectionInfo()
        conn.last_activity = datetime.utcnow()

        assert conn.is_active(timeout_seconds=120) is True

    def test_connection_is_stale(self):
        """Test detecting stale connection."""
        conn = ConnectionInfo()
        conn.last_activity = datetime.utcnow() - timedelta(seconds=150)

        assert conn.is_active(timeout_seconds=120) is False

    def test_connection_mark_activity(self):
        """Test updating activity timestamp."""
        conn = ConnectionInfo()
        old_time = conn.last_activity

        # Wait a tiny bit and update
        conn.mark_activity()

        assert conn.last_activity > old_time

    def test_connection_with_subscriptions(self):
        """Test connection with subscriptions."""
        conn = ConnectionInfo()
        conn.subscriptions = ["cache_stats", "player_state"]

        assert len(conn.subscriptions) == 2
        assert "cache_stats" in conn.subscriptions


# ============================================================================
# Rate Limiter Tests
# ============================================================================

class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_creation(self):
        """Test creating rate limiter."""
        limiter = RateLimiter(messages_per_minute=100)

        assert limiter.messages_per_minute == 100

    def test_rate_limiter_allows_normal_requests(self):
        """Test that normal requests are allowed."""
        limiter = RateLimiter(messages_per_minute=100)
        conn_id = "test-conn"

        # Should allow requests up to limit
        for _ in range(50):
            assert limiter.is_allowed(conn_id, MessagePriority.NORMAL) is True

    def test_rate_limiter_blocks_excess_requests(self):
        """Test that excess requests are blocked."""
        limiter = RateLimiter(messages_per_minute=5)
        conn_id = "test-conn"

        # Fill up the limit
        for _ in range(5):
            assert limiter.is_allowed(conn_id, MessagePriority.NORMAL) is True

        # This should be blocked
        assert limiter.is_allowed(conn_id, MessagePriority.NORMAL) is False

    def test_rate_limiter_critical_priority(self):
        """Test that critical messages have higher limit."""
        limiter = RateLimiter(messages_per_minute=10)
        conn_id = "test-conn"

        # Critical gets 10x multiplier, so 100 allowed
        for _ in range(100):
            assert limiter.is_allowed(conn_id, MessagePriority.CRITICAL) is True

        # 101st should be blocked
        assert limiter.is_allowed(conn_id, MessagePriority.CRITICAL) is False

    def test_rate_limiter_low_priority(self):
        """Test that low priority messages have lower limit."""
        limiter = RateLimiter(messages_per_minute=100)
        conn_id = "test-conn"

        # Low gets 0.5x multiplier, so 50 allowed
        for _ in range(50):
            assert limiter.is_allowed(conn_id, MessagePriority.LOW) is True

        # 51st should be blocked
        assert limiter.is_allowed(conn_id, MessagePriority.LOW) is False

    def test_rate_limiter_stats(self):
        """Test getting rate limiter statistics."""
        limiter = RateLimiter(messages_per_minute=100)
        conn_id = "test-conn"

        # Send some requests
        for _ in range(25):
            limiter.is_allowed(conn_id, MessagePriority.NORMAL)

        stats = limiter.get_stats(conn_id)

        assert stats["requests_this_minute"] == 25
        assert stats["limit"] == 100
        assert stats["utilization_percent"] == 25.0


# ============================================================================
# Heartbeat Manager Tests
# ============================================================================

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


# ============================================================================
# WebSocket Protocol Tests
# ============================================================================

class TestWebSocketProtocol:
    """Test WebSocket protocol handler."""

    def test_protocol_creation(self):
        """Test creating protocol handler."""
        protocol = WebSocketProtocol(
            max_message_queue=1000,
            rate_limit_per_minute=100,
            heartbeat_interval=30
        )

        assert protocol.max_message_queue == 1000
        assert len(protocol.connections) == 0

    @pytest.mark.asyncio
    async def test_register_handler(self):
        """Test registering message handler."""
        protocol = WebSocketProtocol()

        async def play_handler(msg):
            return {"status": "playing"}

        protocol.register_handler(MessageType.PLAY, play_handler)

        assert MessageType.PLAY in protocol.message_handlers
        assert len(protocol.message_handlers[MessageType.PLAY]) == 1

    @pytest.mark.asyncio
    async def test_handle_message_success(self):
        """Test handling message successfully."""
        protocol = WebSocketProtocol()

        async def play_handler(msg):
            return {"status": "playing", "track_id": msg.payload.get("track_id")}

        protocol.register_handler(MessageType.PLAY, play_handler)

        msg = WSMessage(
            type=MessageType.PLAY,
            payload={"track_id": 123},
            response_required=True
        )

        response = await protocol.handle_message(msg)

        assert response is not None
        assert response.payload["status"] == "playing"
        assert response.payload["track_id"] == 123

    @pytest.mark.asyncio
    async def test_handle_message_no_handler(self):
        """Test handling message with no registered handler."""
        protocol = WebSocketProtocol()

        msg = WSMessage(type=MessageType.PLAY)
        response = await protocol.handle_message(msg)

        assert response is None

    @pytest.mark.asyncio
    async def test_handle_message_handler_error(self):
        """Test handling message when handler raises error."""
        protocol = WebSocketProtocol()

        async def bad_handler(msg):
            raise ValueError("Test error")

        protocol.register_handler(MessageType.PLAY, bad_handler)

        msg = WSMessage(
            type=MessageType.PLAY,
            payload={"track_id": 123},
            response_required=True
        )

        response = await protocol.handle_message(msg)

        assert response is not None
        assert response.type == MessageType.ERROR
        assert "Test error" in response.payload["error"]

    def test_get_connection_info(self):
        """Test getting connection information."""
        protocol = WebSocketProtocol()
        conn = ConnectionInfo()

        protocol.connections[conn.connection_id] = conn

        retrieved = protocol.get_connection_info(conn.connection_id)

        assert retrieved == conn

    def test_get_all_connections(self):
        """Test getting all connections."""
        protocol = WebSocketProtocol()

        for _ in range(5):
            conn = ConnectionInfo()
            protocol.connections[conn.connection_id] = conn

        all_conns = protocol.get_all_connections()

        assert len(all_conns) == 5

    def test_get_connection_stats(self):
        """Test getting detailed connection statistics."""
        protocol = WebSocketProtocol()
        conn = ConnectionInfo()
        conn.message_count = 42
        conn.bytes_sent = 1024

        protocol.connections[conn.connection_id] = conn

        stats = protocol.get_connection_stats(conn.connection_id)

        assert stats is not None
        assert stats["message_count"] == 42
        assert stats["bytes_sent"] == 1024
        assert "connection_id" in stats
        assert "uptime_seconds" in stats


# ============================================================================
# Message Type Tests
# ============================================================================

class TestMessageTypes:
    """Test message type enumeration."""

    def test_all_message_types(self):
        """Test that all message types are defined."""
        # Connection management
        assert MessageType.PING in MessageType
        assert MessageType.PONG in MessageType
        assert MessageType.CONNECT in MessageType
        assert MessageType.DISCONNECT in MessageType

        # Player messages
        assert MessageType.PLAY in MessageType
        assert MessageType.PAUSE in MessageType
        assert MessageType.SEEK in MessageType

        # Queue messages
        assert MessageType.QUEUE_ADD in MessageType
        assert MessageType.QUEUE_REMOVE in MessageType

        # Cache messages
        assert MessageType.CACHE_STATUS in MessageType
        assert MessageType.CACHE_STATS in MessageType

    def test_message_priority_levels(self):
        """Test message priority levels."""
        assert MessagePriority.CRITICAL in MessagePriority
        assert MessagePriority.HIGH in MessagePriority
        assert MessagePriority.NORMAL in MessagePriority
        assert MessagePriority.LOW in MessagePriority


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
