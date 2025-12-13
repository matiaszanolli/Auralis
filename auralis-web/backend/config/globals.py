"""
Global State Management

Centralized global variable declarations and shared utilities like ConnectionManager.
These are initialized during application startup and used throughout the backend.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.

    Tracks active connections and broadcasts messages to all connected clients.
    """

    def __init__(self) -> None:
        """Initialize connection manager with empty connections list."""
        self.active_connections: List[WebSocket] = []

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
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast message to all connected clients.

        Args:
            message: Dictionary message to broadcast (will be JSON encoded)
        """
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")


def create_globals_dict() -> Dict[str, Any]:
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
