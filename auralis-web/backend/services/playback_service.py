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

from websocket.outbound_messages import broadcast_typed

from services.playback_event_sequencer import playback_event_sequencer

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

    async def set_playing(
        self, playing: bool, *, broadcast: bool = True
    ) -> Any:
        """Update playing state."""
        ...

    async def broadcast_state(self, state: Any) -> None:
        """Broadcast a previously sequenced state snapshot."""
        ...

    async def set_track(self, track: Any, library_database: Any) -> None:
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
            audio_player: AudioPlayer instance implementing AudioPlayer protocol
            player_state_manager: PlayerStateManager instance implementing PlayerStateManager protocol
            connection_manager: WebSocket connection manager implementing ConnectionManager protocol

        Raises:
            ValueError: If any required component is not available
        """
        self.audio_player: AudioPlayer = audio_player
        self.player_state_manager: PlayerStateManager = player_state_manager
        self.connection_manager: ConnectionManager = connection_manager

        # #3734/#5294: play/pause/stop/seek use one process-wide lock so
        # separate per-request service instances cannot interleave their
        # `set_playing` + broadcast steps and leave the UI showing a
        # stale transport state. WebSocket-native pause/resume/stop handlers
        # draw from the same sequencer. set_volume is broadcast-only and uses
        # a separate sequence domain, so it stays outside the transport lock.
        #
        # #4581: the explicit `connection_manager.broadcast()` calls now run
        # OUTSIDE this lock — the transition is committed before them, so the
        # lock guarded nothing they read.
        #
        # #4751: state mutation and seq assignment stay INSIDE this lock so
        # their order still matches the engine transitions. The resulting
        # snapshot is broadcast after release, and clients use seq to discard
        # a late older snapshot.

    @property
    def _playback_lock(self) -> asyncio.Lock:
        """Compatibility name for the process-wide transition lock.

        A setter-backed override preserves the lightweight ``__new__`` test
        seam used by the broadcast-timeout regression suite. Normal service
        construction never sets it and always resolves the shared lock.
        """
        override = getattr(self, "_playback_lock_override", None)
        if override is not None:
            return override
        return playback_event_sequencer.transition_lock

    @_playback_lock.setter
    def _playback_lock(self, lock: asyncio.Lock) -> None:
        self._playback_lock_override = lock

    async def _broadcast_state_snapshot(self, snapshot: Any) -> None:
        """Send a deferred state snapshot when the collaborator returned one."""
        if snapshot is not None:
            await self.player_state_manager.broadcast_state(snapshot)

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

                # Mutate state and assign seq under the transition lock, but
                # defer the potentially slow WebSocket send (#4751).
                state_snapshot = await self.player_state_manager.set_playing(
                    True, broadcast=False
                )
                event_seq = playback_event_sequencer.next_transport_seq()

            await self._broadcast_state_snapshot(state_snapshot)

            # #4581: broadcast OUTSIDE the lock. The transition is already
            # committed by this point, so the lock protects nothing the
            # broadcast reads — but holding it across a per-client send meant
            # one stalled WebSocket client froze play/pause/stop for everyone.
            await broadcast_typed(
                self.connection_manager,
                "playback_started",
                {"state": "playing", "seq": event_seq},
            )

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

                state_snapshot = await self.player_state_manager.set_playing(
                    False, broadcast=False
                )
                event_seq = playback_event_sequencer.next_transport_seq()

            await self._broadcast_state_snapshot(state_snapshot)

            # Broadcast outside the lock (#4581) — see play().
            await broadcast_typed(
                self.connection_manager,
                "playback_paused",
                {"state": "paused", "seq": event_seq},
            )

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
            state_snapshot: Any = None
            async with self._playback_lock:  # #3734
                # #3716: offload the sync engine call.
                await asyncio.to_thread(self.audio_player.stop)

                # Update state to stopped and clear
                if self.player_state_manager:
                    state_snapshot = await self.player_state_manager.set_playing(
                        False, broadcast=False
                    )
                event_seq = playback_event_sequencer.next_transport_seq()

            await self._broadcast_state_snapshot(state_snapshot)

            # Broadcast outside the lock (#4581) — see play().
            await broadcast_typed(
                self.connection_manager,
                "playback_stopped",
                {"state": "stopped", "seq": event_seq},
            )

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
            event_seq = playback_event_sequencer.next_volume_seq()
            await broadcast_typed(
                self.connection_manager,
                "volume_changed",
                {"volume": volume_100, "seq": event_seq},
            )

            logger.info(f"🔊 Volume set to {volume:.0%} (broadcast only — applied client-side)")
            return {
                "message": "Volume set",
                "volume": volume_100
            }

        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            raise
