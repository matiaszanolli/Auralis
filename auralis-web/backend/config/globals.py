"""
Global State Management

Centralized global variable declarations and shared utilities like ConnectionManager.
These are initialized during application startup and used throughout the backend.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.

    Tracks active connections and broadcasts messages to all connected clients.
    """

    def __init__(self) -> None:
        """Initialize connection manager with empty connections list."""
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection.

        Args:
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            websocket: WebSocket connection to unregister
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
        else:
            logger.debug("WebSocket disconnect called but connection not in list (already removed)")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast message to all connected clients.

        Automatically removes stale connections that fail to receive messages.

        Args:
            message: Dictionary message to broadcast (will be JSON encoded)
        """
        stale_connections: list[WebSocket] = []
        message_json = json.dumps(message)

        for connection in list(self.active_connections):  # snapshot: disconnect() may modify during await
            try:
                await connection.send_text(message_json)
            except Exception as e:
                # Connection is stale, mark for removal
                stale_connections.append(connection)
                logger.debug(f"Marking stale connection for removal: {e}")

        # Remove stale connections
        for stale in stale_connections:
            if stale in self.active_connections:
                self.active_connections.remove(stale)

        if stale_connections:
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
        'processing_cache': {},  # Cache for processed audio files
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
