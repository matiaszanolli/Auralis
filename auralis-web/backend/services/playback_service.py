"""
Playback Service

Manages audio playback control operations: play, pause, stop, seek, volume.
Coordinates with PlayerStateManager to keep single source of truth.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import logging
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)


class AudioPlayer(Protocol):
    """Protocol for audio player interface."""

    def play(self) -> None:
        """Start playback."""
        ...

    def pause(self) -> None:
        """Pause playback."""
        ...

    def stop(self) -> None:
        """Stop playback."""
        ...

    def seek(self, position: float) -> None:
        """Seek to position in seconds."""
        ...

    # #3722: deliberately NO set_volume method. Volume is applied
    # client-side via Web Audio API GainNode; the /api/player/volume
    # route exists only to broadcast volume state for cross-client
    # mirroring. The engine never mixes audio for playback.


class PlayerStateManager(Protocol):
    """Protocol for player state manager interface."""

    async def set_playing(self, playing: bool) -> None:
        """Update playing state."""
        ...

    async def set_track(self, track: Any, library_manager: Any) -> None:
        """Set current track."""
        ...

    def get_state(self) -> Any:
        """Get current state."""
        ...


class ConnectionManager(Protocol):
    """Protocol for connection manager interface."""

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to connected clients."""
        ...


class PlaybackService:
    """
    Service for managing audio playback control.

    Encapsulates play/pause/stop/seek/volume logic and state synchronization.
    Acts as coordinator between audio player and state manager.
    """

    def __init__(
        self,
        audio_player: AudioPlayer,
        player_state_manager: PlayerStateManager,
        connection_manager: ConnectionManager,
    ) -> None:
        """
        Initialize PlaybackService.

        Args:
            audio_player: EnhancedAudioPlayer instance implementing AudioPlayer protocol
            player_state_manager: PlayerStateManager instance implementing PlayerStateManager protocol
            connection_manager: WebSocket connection manager implementing ConnectionManager protocol

        Raises:
            ValueError: If any required component is not available
        """
        self.audio_player: AudioPlayer = audio_player
        self.player_state_manager: PlayerStateManager = player_state_manager
        self.connection_manager: ConnectionManager = connection_manager

        # #3734: serialise play/pause/stop/seek through one service-level
        # lock so two concurrent requests can't interleave their
        # `set_playing` + broadcast steps and leave the UI showing a
        # stale transport state. Matches the QueueService.set_queue
        # pattern from #3721. set_volume is broadcast-only and stays
        # outside the lock.
        self._playback_lock: asyncio.Lock = asyncio.Lock()

    async def get_status(self) -> dict[str, Any]:
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
            return cast(dict[str, Any], state.model_dump())
        except Exception as e:
            logger.error(f"Failed to get player status: {e}")
            raise

    async def play(self) -> dict[str, Any]:
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
            async with self._playback_lock:  # #3734
                # #3716: offload the sync engine call. play() acquires
                # PlaybackController._lock; cheap in isolation but the wrap
                # is identical to QueueService's pattern and guards against
                # any future heavy work landing inside the engine method.
                await asyncio.to_thread(self.audio_player.play)

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

    async def pause(self) -> dict[str, Any]:
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
            async with self._playback_lock:  # #3734
                # #3716: offload the sync engine call.
                await asyncio.to_thread(self.audio_player.pause)

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

    async def stop(self) -> dict[str, Any]:
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
            async with self._playback_lock:  # #3734
                # #3716: offload the sync engine call.
                await asyncio.to_thread(self.audio_player.stop)

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

    async def seek(self, position: float) -> dict[str, Any]:
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
            async with self._playback_lock:  # #3734
                # #3716: offload the sync engine call. seek() is the
                # load-bearing case — it acquires `file_manager._audio_lock`,
                # which a concurrent `load_file()` can hold for hundreds of
                # ms to seconds while decoding a large file. Running this
                # synchronously on the event loop froze the FastAPI worker
                # and stalled every other in-flight HTTP request.
                if hasattr(self.audio_player, 'seek'):
                    await asyncio.to_thread(self.audio_player.seek, position)

                # #3777: removed the `{"type": "seek"}` broadcast — no
                # frontend subscriber consumes it (grep over
                # auralis-web/frontend/src/ returns zero subscribe()
                # calls for "seek"). The outbound `play_enhanced` /
                # `play_normal` streams already carry `start_position`
                # via the WS path; the legacy REST seek endpoint only
                # mutates the EnhancedAudioPlayer state and doesn't
                # need an extra cross-client broadcast.

            logger.info(f"⏩ Seeked to {position:.1f}s")
            return {
                "message": "Seek successful",
                "position": position
            }

        except Exception as e:
            logger.error(f"Failed to seek: {e}")
            raise

    async def set_volume(self, volume: float) -> dict[str, Any]:
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
            # #3722: volume is a CLIENT-SIDE concern. The backend never
            # mixes audio for playback — bytes leave the engine and go
            # straight to the WebSocket; the frontend AudioPlaybackEngine
            # (services/audio/AudioPlaybackEngine.ts) applies gain via a
            # Web Audio API GainNode before the destination. The previous
            # `if hasattr(self.audio_player, 'set_volume'):` guard was a
            # silent no-op (the engine method has never existed) which
            # hid this design from manual QA — clients saw the slider
            # move thanks to the broadcast echo and assumed the level
            # changed. This route exists only to broadcast volume state
            # so other connected clients can mirror the slider position;
            # the actual audio gain change happens on the originating
            # client and on every other client that receives the
            # broadcast.

            # Broadcast volume change (0-100 scale matching PlayerState)
            volume_100 = round(volume * 100)
            await self.connection_manager.broadcast({
                "type": "volume_changed",
                "data": {"volume": volume_100}
            })

            logger.info(f"🔊 Volume set to {volume:.0%} (broadcast only — applied client-side)")
            return {
                "message": "Volume set",
                "volume": volume_100
            }

        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            raise
