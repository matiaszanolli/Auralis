"""
Navigation Service

Manages track navigation: next track, previous track, jump to track.
Coordinates with AudioPlayer and PlayerStateManager for state synchronization.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import Any
from collections.abc import Callable

from config.globals import ConnectionManager
from state_manager import PlayerStateManager

from auralis import EnhancedAudioPlayer

logger = logging.getLogger(__name__)


class NavigationService:
    """
    Service for managing track navigation in playback queue.

    Handles next/previous track operations and track jumping.
    Coordinates state synchronization and WebSocket broadcasting.
    """

    def __init__(
        self,
        audio_player: EnhancedAudioPlayer,
        player_state_manager: PlayerStateManager,
        connection_manager: ConnectionManager,
        create_track_info_fn: Callable[[Any], Any],
    ) -> None:
        """
        Initialize NavigationService.

        Args:
            audio_player: EnhancedAudioPlayer instance
            player_state_manager: PlayerStateManager instance
            connection_manager: WebSocket connection manager for broadcasts
            create_track_info_fn: Function to convert DB track to TrackInfo

        Raises:
            ValueError: If any required component is not available
        """
        self.audio_player: EnhancedAudioPlayer = audio_player
        self.player_state_manager: PlayerStateManager = player_state_manager
        self.connection_manager: ConnectionManager = connection_manager
        self.create_track_info_fn: Callable[[Any], Any] = create_track_info_fn

    async def next_track(self) -> dict[str, Any]:
        """
        Skip to next track in queue.

        Returns:
            dict: Success message and track info if available

        Raises:
            Exception: If operation fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")

        try:
            # Check if player has next_track method
            if hasattr(self.audio_player, 'next_track'):
                success = self.audio_player.next_track()

                if success:
                    # Update state if available
                    if self.player_state_manager and hasattr(self.audio_player, 'queue'):
                        self.player_state_manager.get_state()
                        if hasattr(self.audio_player.queue, 'current_index'):
                            # Broadcast track change
                            await self.connection_manager.broadcast({
                                "type": "track_changed",
                                "data": {"action": "next"}
                            })

                    logger.info("⏭️  Skipped to next track")
                    return {"message": "Skipped to next track"}
                else:
                    logger.info("ℹ️  No next track available")
                    return {"message": "No next track available"}
            else:
                logger.warning("Next track function not available")
                return {"message": "Next track function not available"}

        except Exception as e:
            logger.error(f"Failed to skip to next track: {e}")
            raise

    async def previous_track(self) -> dict[str, Any]:
        """
        Skip to previous track in queue.

        Returns:
            dict: Success message and track info if available

        Raises:
            Exception: If operation fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")

        try:
            # Check if player has previous_track method
            if hasattr(self.audio_player, 'previous_track'):
                success = self.audio_player.previous_track()

                if success:
                    # Update state if available
                    if self.player_state_manager and hasattr(self.audio_player, 'queue'):
                        self.player_state_manager.get_state()
                        if hasattr(self.audio_player.queue, 'current_index'):
                            # Broadcast track change
                            await self.connection_manager.broadcast({
                                "type": "track_changed",
                                "data": {"action": "previous"}
                            })

                    logger.info("⏮️  Skipped to previous track")
                    return {"message": "Skipped to previous track"}
                else:
                    logger.info("ℹ️  No previous track available")
                    return {"message": "No previous track available"}
            else:
                logger.warning("Previous track function not available")
                return {"message": "Previous track function not available"}

        except Exception as e:
            logger.error(f"Failed to skip to previous track: {e}")
            raise

    async def jump_to_track(self, track_index: int) -> dict[str, Any]:
        """
        Jump to specific track in queue.

        Args:
            track_index: Index of track to jump to

        Returns:
            dict: Success message and track info

        Raises:
            Exception: If index invalid or operation fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")
        if not self.player_state_manager:
            raise ValueError("Player state manager not available")

        try:
            # Get current queue
            if not hasattr(self.audio_player, 'queue'):
                raise ValueError("Queue not available")

            queue_manager = self.audio_player.queue
            queue_size = queue_manager.get_queue_size()

            # Validate index
            if track_index < 0 or track_index >= queue_size:
                raise ValueError(f"Invalid track index: {track_index}")

            # Set queue position
            if hasattr(queue_manager, 'set_current_index'):
                queue_manager.set_current_index(track_index)
            else:
                # Fallback: manually get queue and load track
                queue = queue_manager.get_queue()
                if track_index < len(queue):
                    track_path = queue[track_index]
                    if hasattr(self.audio_player, 'load_file'):
                        self.audio_player.load_file(track_path)  # type: ignore[arg-type]

            # Start playback
            if hasattr(self.audio_player, 'play'):
                self.audio_player.play()

            # Update state
            await self.player_state_manager.set_playing(True)

            # Broadcast track change
            await self.connection_manager.broadcast({
                "type": "track_changed",
                "data": {
                    "action": "jumped",
                    "track_index": track_index
                }
            })

            logger.info(f"Jumped to track {track_index}")
            return {
                "message": "Jumped to track successfully",
                "track_index": track_index
            }

        except Exception as e:
            logger.error(f"Failed to jump to track {track_index}: {e}")
            raise
