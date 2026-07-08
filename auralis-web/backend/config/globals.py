"""
Global State Management

Centralized global variable declarations and shared utilities like ConnectionManager.
These are initialized during application startup and used throughout the backend.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Allowed origins for WebSocket connections — single authoritative allowlist
# (fixes #2413: cross-origin hijacking, and #3524 / BE-NEW-66: prior
# system.py prefix-based pre-check disagreed with this strict allowlist on
# e.g. `file://` Electron origins). Browser clients send the Origin header;
# non-browser clients (native apps, tests) may not.
#
# Generated programmatically over the same host x port matrix as CORS
# (see config/middleware.py), plus `file://` for packaged Electron builds
# whose renderer Origin header is `file://`.
_DEV_PORTS = list(range(3000, 3007)) + [8765]
ALLOWED_WS_ORIGINS = frozenset(
    {
        f"{scheme}://{host}:{port}"
        for scheme in ("http", "https", "ws", "wss")
        for host in ("localhost", "127.0.0.1")
        for port in _DEV_PORTS
    }
    | {"file://"}
)

# Hosts considered loopback — empty-Origin connections are allowed only from
# these addresses so non-browser local processes on non-loopback interfaces
# cannot bypass the origin check (fixes #3845).
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.

    Tracks active connections and broadcasts messages to all connected clients.
    """

    def __init__(self) -> None:
        """Initialize connection manager with empty connections list."""
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection.

        Validates the Origin header to prevent cross-origin hijacking attacks.
        Rejects connections from untrusted origins (fixes #2413).

        Args:
            websocket: WebSocket connection to register
        """
        # Check Origin header for security (CORS does not apply to WebSocket upgrades).
        origin = websocket.headers.get("origin", "").lower()
        if origin:
            # Non-empty Origin: must be in the allowlist (fixes #2413).
            if origin not in ALLOWED_WS_ORIGINS:
                logger.warning(f"WebSocket connection rejected: untrusted origin {origin!r}")
                await websocket.close(code=1008)  # Policy Violation
                return
        else:
            # Empty Origin: allow only from loopback so non-browser processes
            # on non-loopback interfaces cannot bypass the check (fixes #3845).
            client_host = (websocket.client.host if websocket.client else "").lower()
            if client_host not in _LOOPBACK_HOSTS:
                logger.warning(
                    f"WebSocket connection rejected: empty Origin from non-loopback host {client_host!r}"
                )
                await websocket.close(code=1008)  # Policy Violation
                return

        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        client = websocket.client
        client_id = f"{client.host}:{client.port}" if client else "unknown"
        logger.info(f"WebSocket connected from {client_id}. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            websocket: WebSocket connection to unregister
        """
        client = websocket.client
        client_id = f"{client.host}:{client.port}" if client else "unknown"
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                logger.info(f"WebSocket disconnected from {client_id}. Total connections: {len(self.active_connections)}")
            else:
                logger.debug(f"WebSocket disconnect called for {client_id} but connection not in list (already removed)")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast message to all connected clients.

        Automatically removes stale connections that fail to receive messages.

        Args:
            message: Dictionary message to broadcast (will be JSON encoded)
        """
        stale_connections: list[WebSocket] = []

        async with self._lock:
            connections_snapshot = list(self.active_connections)

        message_json = json.dumps(message)

        for connection in connections_snapshot:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                stale_connections.append(connection)
                logger.debug(f"Marking stale connection for removal: {e}")

        if stale_connections:
            async with self._lock:
                for stale in stale_connections:
                    if stale in self.active_connections:
                        self.active_connections.remove(stale)
            logger.info(f"Removed {len(stale_connections)} stale connection(s). Active: {len(self.active_connections)}")


def create_globals_dict() -> dict[str, Any]:
    """
    Create and initialize the global state dictionary.

    Returns:
        Dictionary with initialized global variables
    """
    return {
        # Core components (initialized during startup)
        'library_manager': None,
        'settings_repository': None,
        'audio_player': None,
        'player_state_manager': None,

        # Processing and caching
        'processing_engine': None,
        'streamlined_cache': None,
        'streamlined_worker': None,

        # Analysis and similarity
        'similarity_system': None,
        'graph_builder': None,

        # Configuration
        'enhancement_settings': {
            "enabled": True,
            "preset": "adaptive",
            "intensity": 1.0
        },

        # WebSocket management
        'manager': ConnectionManager(),
    }


# Default global state (will be populated during startup)
globals_dict = create_globals_dict()
