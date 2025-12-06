"""
Shared dependency injection and validation utilities for routers.

This module consolidates common dependency checks that appear across multiple routers,
reducing boilerplate and improving consistency.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import HTTPException
import logging
from typing import Callable, Any
from auralis import EnhancedAudioPlayer
from auralis.library import LibraryManager

logger = logging.getLogger(__name__)


def require_library_manager(get_library_manager: Callable[[], Any]) -> LibraryManager:
    """
    Validate that library manager is available.

    Args:
        get_library_manager: Callable that returns LibraryManager instance

    Returns:
        LibraryManager: The library manager instance

    Raises:
        HTTPException: 503 if library manager is not available
    """
    library_manager = get_library_manager()
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")
    return library_manager


def require_audio_player(get_audio_player: Callable[[], Any]) -> EnhancedAudioPlayer:
    """
    Validate that audio player is available.

    Args:
        get_audio_player: Callable that returns EnhancedAudioPlayer instance

    Returns:
        EnhancedAudioPlayer: The audio player instance

    Raises:
        HTTPException: 503 if audio player is not available
    """
    audio_player = get_audio_player()
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")
    return audio_player


def require_player_state_manager(get_player_state_manager: Callable[[], Any]) -> Any:
    """
    Validate that player state manager is available.

    Args:
        get_player_state_manager: Callable that returns PlayerStateManager instance

    Returns:
        PlayerStateManager: The player state manager instance

    Raises:
        HTTPException: 503 if player state manager is not available
    """
    state_manager = get_player_state_manager()
    if not state_manager:
        raise HTTPException(status_code=503, detail="Player state manager not available")
    return state_manager


def require_connection_manager(connection_manager: Any) -> Any:
    """
    Validate that WebSocket connection manager is available.

    Args:
        connection_manager: WebSocket connection manager instance

    Returns:
        ConnectionManager: The connection manager instance

    Raises:
        HTTPException: 503 if connection manager is not available
    """
    if not connection_manager:
        raise HTTPException(status_code=503, detail="Connection manager not available")
    return connection_manager
