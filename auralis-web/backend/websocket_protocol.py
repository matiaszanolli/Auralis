"""
WebSocket Message Protocol
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Standardized message protocol for WebSocket communication with connection management,
heartbeat, rate limiting, and automatic reconnection support.

Phase B.3: WebSocket Enhancement

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import uuid
import time
import asyncio
from typing import Dict, List, Optional, Callable, Any, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    # Connection management
    PING = "ping"
    PONG = "pong"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    ERROR = "error"

    # Player messages
    PLAY = "play"
    PAUSE = "pause"
    STOP = "stop"
    SEEK = "seek"
    NEXT = "next"
    PREVIOUS = "previous"

    # Queue messages
    QUEUE_ADD = "queue_add"
    QUEUE_REMOVE = "queue_remove"
    QUEUE_CLEAR = "queue_clear"
    QUEUE_REORDER = "queue_reorder"

    # Library messages
    LIBRARY_SYNC = "library_sync"
    LIBRARY_SEARCH = "library_search"

    # Cache messages
    CACHE_STATUS = "cache_status"
    CACHE_STATS = "cache_stats"

    # Notification messages
    NOTIFICATION = "notification"

    # Status messages
    STATUS_UPDATE = "status_update"
    HEALTH_CHECK = "health_check"


class MessagePriority(str, Enum):
    """Message priority levels for rate limiting."""
    CRITICAL = "critical"  # Heartbeat, disconnect
    HIGH = "high"           # Play, pause, seek
    NORMAL = "normal"       # Queue operations, library sync
    LOW = "low"             # Status updates, notifications


@dataclass
class WSMessage:
    """WebSocket message envelope."""
    type: MessageType
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: MessagePriority = MessagePriority.NORMAL
    payload: Optional[Dict[str, Any]] = None
    response_required: bool = False
    timeout_seconds: float = 30.0
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "payload": self.payload or {},
            "response_required": self.response_required,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WSMessage":
        """Create message from dictionary."""
        return cls(
            type=MessageType(data["type"]),
            correlation_id=data.get("correlation_id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
            priority=MessagePriority(data.get("priority", "normal")),
            payload=data.get("payload", {}),
            response_required=data.get("response_required", False),
            timeout_seconds=data.get("timeout_seconds", 30.0),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3)
        )


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    connection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    message_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    state: str = "connected"
    client_version: Optional[str] = None
    subscriptions: List[str] = field(default_factory=list)

    def is_active(self, timeout_seconds: int = 120) -> bool:
        """Check if connection is active (within timeout)."""
        elapsed = datetime.utcnow() - self.last_activity
        return elapsed < timedelta(seconds=timeout_seconds)

    def mark_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()


class RateLimiter:
    """Rate limiter for WebSocket messages."""

    def __init__(self, messages_per_minute: int = 100):
        """
        Initialize rate limiter.

        Args:
            messages_per_minute: Maximum messages per minute per priority level
        """
        self.messages_per_minute = messages_per_minute
        self.request_log: Dict[str, List[float]] = {}

        # Different limits for different priorities
        self.priority_multipliers = {
            MessagePriority.CRITICAL: 10.0,  # 10x limit
            MessagePriority.HIGH: 2.0,        # 2x limit
            MessagePriority.NORMAL: 1.0,      # Standard limit
            MessagePriority.LOW: 0.5           # Half limit
        }

    def is_allowed(self, connection_id: str, priority: MessagePriority = MessagePriority.NORMAL) -> bool:
        """
        Check if message is allowed under rate limit.

        Args:
            connection_id: Connection identifier
            priority: Message priority level

        Returns:
            True if message is allowed, False if rate limited
        """
        now = time.time()
        minute_ago = now - 60

        # Initialize if new connection
        if connection_id not in self.request_log:
            self.request_log[connection_id] = []

        # Remove old entries
        self.request_log[connection_id] = [
            ts for ts in self.request_log[connection_id]
            if ts > minute_ago
        ]

        # Check limit based on priority
        multiplier = self.priority_multipliers.get(priority, 1.0)
        limit = int(self.messages_per_minute * multiplier)

        if len(self.request_log[connection_id]) >= limit:
            logger.warning(f"Rate limit exceeded for {connection_id}: {priority.value}")
            return False

        # Record this request
        self.request_log[connection_id].append(now)
        return True

    def get_stats(self, connection_id: str) -> Dict[str, Any]:
        """Get rate limiter statistics for a connection."""
        now = time.time()
        minute_ago = now - 60

        if connection_id not in self.request_log:
            return {
                "requests_this_minute": 0,
                "limit": self.messages_per_minute,
                "utilization_percent": 0.0
            }

        # Clean old entries
        recent = [ts for ts in self.request_log[connection_id] if ts > minute_ago]

        return {
            "requests_this_minute": len(recent),
            "limit": self.messages_per_minute,
            "utilization_percent": round(len(recent) / self.messages_per_minute * 100, 1)
        }


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
        self.last_heartbeat: Dict[str, datetime] = {}
        self.pending_pongs: Dict[str, datetime] = {}

    def mark_ping(self, connection_id: str) -> None:
        """Mark when ping was sent."""
        self.last_heartbeat[connection_id] = datetime.utcnow()
        self.pending_pongs[connection_id] = datetime.utcnow()

    def mark_pong(self, connection_id: str) -> bool:
        """
        Mark pong response received.

        Returns:
            True if pong was within timeout, False if it was late
        """
        if connection_id not in self.pending_pongs:
            return False

        elapsed = (datetime.utcnow() - self.pending_pongs[connection_id]).total_seconds()
        del self.pending_pongs[connection_id]

        return elapsed < self.timeout_seconds

    def is_alive(self, connection_id: str) -> bool:
        """Check if connection is alive (has recent activity)."""
        if connection_id not in self.last_heartbeat:
            return False

        elapsed = (datetime.utcnow() - self.last_heartbeat[connection_id]).total_seconds()
        return elapsed < (self.interval_seconds * 2)  # Allow 2 intervals before timeout

    def is_stale(self, connection_id: str) -> bool:
        """Check if connection has pending pong for too long."""
        if connection_id not in self.pending_pongs:
            return False

        elapsed = (datetime.utcnow() - self.pending_pongs[connection_id]).total_seconds()
        return elapsed > self.timeout_seconds


class WebSocketProtocol:
    """
    High-level WebSocket protocol handler with message queuing,
    correlation tracking, and automatic reconnection support.
    """

    def __init__(
        self,
        max_message_queue: int = 1000,
        rate_limit_per_minute: int = 100,
        heartbeat_interval: int = 30,
        heartbeat_timeout: int = 10
    ):
        """
        Initialize WebSocket protocol handler.

        Args:
            max_message_queue: Maximum pending messages per connection
            rate_limit_per_minute: Rate limit threshold
            heartbeat_interval: Heartbeat interval in seconds
            heartbeat_timeout: Heartbeat timeout in seconds
        """
        self.connections: Dict[str, ConnectionInfo] = {}
        self.message_queue: Dict[str, List[WSMessage]] = {}
        self.pending_responses: Dict[str, Dict[str, Any]] = {}
        self.message_handlers: Dict[MessageType, List[Callable]] = {}
        self.max_message_queue = max_message_queue

        self.rate_limiter = RateLimiter(rate_limit_per_minute)
        self.heartbeat = HeartbeatManager(heartbeat_interval, heartbeat_timeout)

        logger.info("WebSocketProtocol initialized")

    def register_handler(self, message_type: MessageType, handler: Callable) -> None:
        """
        Register a message handler for a specific message type.

        Args:
            message_type: Type of message to handle
            handler: Async handler function
        """
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []

        self.message_handlers[message_type].append(handler)
        logger.debug(f"Registered handler for {message_type.value}")

    async def handle_message(self, message: WSMessage) -> Optional[WSMessage]:
        """
        Handle an incoming message.

        Args:
            message: The message to handle

        Returns:
            Response message if response_required, else None
        """
        # Get handlers for this message type
        handlers = self.message_handlers.get(message.type, [])

        if not handlers:
            logger.warning(f"No handlers registered for {message.type.value}")
            return None

        # Execute all handlers
        for handler in handlers:
            try:
                result = await handler(message)

                if message.response_required and result:
                    return WSMessage(
                        type=message.type,
                        correlation_id=message.correlation_id,
                        payload=result
                    )

            except Exception as e:
                logger.error(f"Error in message handler: {e}")
                return WSMessage(
                    type=MessageType.ERROR,
                    correlation_id=message.correlation_id,
                    payload={"error": str(e)}
                )

        return None

    def get_connection_info(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Get information about a connection."""
        return self.connections.get(connection_id)

    def get_all_connections(self) -> List[ConnectionInfo]:
        """Get all active connections."""
        return list(self.connections.values())

    def get_connection_stats(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed statistics for a connection."""
        conn = self.connections.get(connection_id)
        if not conn:
            return None

        return {
            "connection_id": conn.connection_id,
            "connected_at": conn.connected_at.isoformat(),
            "last_activity": conn.last_activity.isoformat(),
            "message_count": conn.message_count,
            "bytes_sent": conn.bytes_sent,
            "bytes_received": conn.bytes_received,
            "state": conn.state,
            "is_active": conn.is_active(),
            "uptime_seconds": (datetime.utcnow() - conn.connected_at).total_seconds(),
            "rate_limiter": self.rate_limiter.get_stats(connection_id),
            "subscriptions": conn.subscriptions
        }
