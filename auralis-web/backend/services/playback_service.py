"""
Playback Service

Manages audio playback control operations: play, pause, stop, seek, volume.
Coordinates with PlayerStateManager to keep single source of truth.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PlaybackService:
    """
    Service for managing audio playback control.

    Encapsulates play/pause/stop/seek/volume logic and state synchronization.
    Acts as coordinator between audio player and state manager.
    """

    def __init__(self, audio_player, player_state_manager, connection_manager):
        """
        Initialize PlaybackService.

        Args:
            audio_player: EnhancedAudioPlayer instance
            player_state_manager: PlayerStateManager instance
            connection_manager: WebSocket connection manager for broadcasts
        """
        self.audio_player = audio_player
        self.player_state_manager = player_state_manager
        self.connection_manager = connection_manager

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current player status.

        Returns:
            dict: Player state with track info, playback status, queue

        Raises:
            Exception: If unable to retrieve status
        """
        if not self.player_state_manager:
            raise ValueError("Player state manager not available")

        try:
            state = self.player_state_manager.get_state()
            return state.model_dump()
        except Exception as e:
            logger.error(f"Failed to get player status: {e}")
            raise

    async def play(self) -> Dict[str, Any]:
        """
        Start playback (updates single source of truth).

        Returns:
            dict: Success message and playback state

        Raises:
            Exception: If playback start fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")
        if not self.player_state_manager:
            raise ValueError("Player state manager not available")

        try:
            self.audio_player.play()

            # Update state (broadcasts automatically)
            await self.player_state_manager.set_playing(True)

            # Broadcast playback_started event
            await self.connection_manager.broadcast({
                "type": "playback_started",
                "data": {"state": "playing"}
            })

            logger.info("▶️  Playback started")
            return {"message": "Playback started", "state": "playing"}

        except Exception as e:
            logger.error(f"Failed to start playback: {e}")
            raise

    async def pause(self) -> Dict[str, Any]:
        """
        Pause playback (updates single source of truth).

        Returns:
            dict: Success message and playback state

        Raises:
            Exception: If pause fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")
        if not self.player_state_manager:
            raise ValueError("Player state manager not available")

        try:
            self.audio_player.pause()

            # Update state (broadcasts automatically)
            await self.player_state_manager.set_playing(False)

            # Broadcast playback_paused event
            await self.connection_manager.broadcast({
                "type": "playback_paused",
                "data": {"state": "paused"}
            })

            logger.info("⏸️  Playback paused")
            return {"message": "Playback paused", "state": "paused"}

        except Exception as e:
            logger.error(f"Failed to pause playback: {e}")
            raise

    async def stop(self) -> Dict[str, Any]:
        """
        Stop playback and clear queue.

        Returns:
            dict: Success message

        Raises:
            Exception: If stop fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")

        try:
            self.audio_player.stop()

            # Update state to stopped and clear
            if self.player_state_manager:
                await self.player_state_manager.set_playing(False)

            # Broadcast playback_stopped event
            await self.connection_manager.broadcast({
                "type": "playback_stopped",
                "data": {"state": "stopped"}
            })

            logger.info("⏹️  Playback stopped")
            return {"message": "Playback stopped", "state": "stopped"}

        except Exception as e:
            logger.error(f"Failed to stop playback: {e}")
            raise

    async def seek(self, position: float) -> Dict[str, Any]:
        """
        Seek to specific playback position.

        Args:
            position: Position in seconds

        Returns:
            dict: Success message and new position

        Raises:
            Exception: If seek fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")

        if position < 0:
            raise ValueError("Position must be non-negative")

        try:
            # Call audio player seek method if available
            if hasattr(self.audio_player, 'seek'):
                self.audio_player.seek(position)

            # Broadcast seek event
            await self.connection_manager.broadcast({
                "type": "seek",
                "data": {"position": position}
            })

            logger.info(f"⏩ Seeked to {position:.1f}s")
            return {
                "message": "Seek successful",
                "position": position
            }

        except Exception as e:
            logger.error(f"Failed to seek: {e}")
            raise

    async def set_volume(self, volume: float) -> Dict[str, Any]:
        """
        Set playback volume.

        Args:
            volume: Volume level (0.0-1.0)

        Returns:
            dict: Success message and new volume

        Raises:
            ValueError: If volume out of range
            Exception: If setting volume fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")

        if not (0.0 <= volume <= 1.0):
            raise ValueError("Volume must be between 0.0 and 1.0")

        try:
            # Set volume if method available
            if hasattr(self.audio_player, 'set_volume'):
                self.audio_player.set_volume(volume)

            # Broadcast volume change
            await self.connection_manager.broadcast({
                "type": "volume_changed",
                "data": {"volume": volume}
            })

            logger.info(f"🔊 Volume set to {volume:.0%}")
            return {
                "message": "Volume set",
                "volume": volume
            }

        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            raise
