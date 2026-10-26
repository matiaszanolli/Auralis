"""
Navigation Service

Manages track navigation: next track, previous track, jump to track.
Coordinates with AudioPlayer and PlayerStateManager for state synchronization.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from core.state_manager import PlayerStateManager
from websocket.outbound_messages import broadcast_typed

from auralis import AudioPlayer

from .errors import require_collaborators
from .loop_bound_lock import LoopBoundLock
from .queue_enrichment import entry_filepath

if TYPE_CHECKING:
    from player_state import PlayerState
    from websocket.outbound_messages import BroadcastManager

logger = logging.getLogger(__name__)


class _TrackChangeSequencer:
    """Cross-request serialization for `track_changed` broadcasts (#4582).

    routers/player.py wires NavigationService via FastAPI `Depends()`, which
    builds a fresh instance per request — so a lock or counter on `self`
    would never actually contend with another request's instance and would
    silently serialize nothing. A rapid skip burst (three "Next" clicks) then
    hits three concurrent next_track() calls whose engine mutation
    (`asyncio.to_thread`) and `track_changed` broadcast could interleave,
    letting an older index land after a newer one. This module-level
    singleton is the one thing genuinely shared across those instances: the
    lock serializes the mutate-and-tag step (broadcast itself stays outside
    it, matching PlaybackService's #4581 pattern, so one slow WS client can't
    stall the next command), and the counter gives the frontend a monotonic
    `seq` to drop a stale delivery by — same mechanism as `player_state.seq`
    (#3732), but a separate counter: NavigationService mutates the engine's
    own queue, not PlayerStateManager.state, so there is no shared generation
    to reuse (see the "Queue dataflow split" architecture note).
    """

    def __init__(self) -> None:
        self._lock = LoopBoundLock()
        self._seq = 0

    @property
    def lock(self) -> asyncio.Lock:
        """The process-wide lock, rebound to the current running loop."""
        return self._lock.get()

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq


_sequencer = _TrackChangeSequencer()


class NavigationService:
    """
    Service for managing track navigation in playback queue.

    Handles next/previous track operations and track jumping.
    Coordinates state synchronization and WebSocket broadcasting.
    """

    def __init__(
        self,
        audio_player: AudioPlayer,
        player_state_manager: PlayerStateManager,
        connection_manager: BroadcastManager,
        create_track_info_fn: Callable[[Any], Any],
    ) -> None:
        """
        Initialize NavigationService.

        Args:
            audio_player: AudioPlayer instance
            player_state_manager: PlayerStateManager instance
            connection_manager: WebSocket connection manager for broadcasts
            create_track_info_fn: Function to convert DB track to TrackInfo

        Raises:
            ValueError: If any required component is not available
        """
        self.audio_player: AudioPlayer = audio_player
        self.player_state_manager: PlayerStateManager = player_state_manager
        self.connection_manager: BroadcastManager = connection_manager
        self.create_track_info_fn: Callable[[Any], Any] = create_track_info_fn

    async def _follow_engine(self, track_index: int) -> PlayerState | None:
        """Sync PlayerStateManager to the track the engine just moved to (#5456).

        The state manager no longer advances "now playing" on its own
        wall-clock estimate, so every engine navigation must tell it. Called
        inside the sequencer lock with the broadcast deferred to the caller.
        Best-effort: a failed sync is logged, never fails the navigation the
        engine has already performed.
        """
        try:
            queue = self.audio_player.queue
            current = None
            if hasattr(queue, 'get_current_track'):
                current = await asyncio.to_thread(queue.get_current_track)
            filepath = entry_filepath(current) if current is not None else None
            return await self.player_state_manager.follow_navigation(
                track_index, filepath, broadcast=False
            )
        except Exception as e:
            logger.warning(f"Could not sync player state to track {track_index}: {e}")
            return None

    async def next_track(self) -> dict[str, Any]:
        """
        Skip to next track in queue.

        Returns:
            dict: Success message and track info if available

        Raises:
            ServiceUnavailable: If the audio player is not available (#5338)
            Exception: If operation fails
        """
        return await self._navigate("next")

    async def previous_track(self) -> dict[str, Any]:
        """
        Skip to previous track in queue.

        Returns:
            dict: Success message and track info if available

        Raises:
            ServiceUnavailable: If the audio player is not available (#5338)
            Exception: If operation fails
        """
        return await self._navigate("previous")

    async def _navigate(self, action: Literal["next", "previous"]) -> dict[str, Any]:
        """Shared body of next_track / previous_track.

        The two commands share one sequencer so they cannot interleave against
        each other either (#4582).
        """
        require_collaborators(audio_player=self.audio_player)
        method_name = f"{action}_track"
        emoji = "⏭️ " if action == "next" else "⏮️ "

        try:
            # Check if the player has the engine method
            if not hasattr(self.audio_player, method_name):
                message = f"{action.capitalize()} track function not available"
                logger.warning(message)
                return {"message": message}

            # Serialize the engine mutation + index read + seq assignment
            # (#4582) — see _TrackChangeSequencer. Broadcast stays outside
            # the lock so one slow WS client can't stall the next command.
            async with _sequencer.lock:
                success = await asyncio.to_thread(getattr(self.audio_player, method_name))
                track_index = None
                seq = None
                state_snapshot = None
                if (
                    success
                    and self.player_state_manager
                    and hasattr(self.audio_player, 'queue')
                    and hasattr(self.audio_player.queue, 'current_index')
                ):
                    track_index = self.audio_player.queue.current_index
                    state_snapshot = await self._follow_engine(track_index)
                    seq = _sequencer.next_seq()

            if not success:
                message = f"No {action} track available"
                logger.info(f"ℹ️  {message}")
                return {"message": message}

            if state_snapshot is not None:
                await self.player_state_manager.broadcast_state(state_snapshot)
            if track_index is not None:
                assert seq is not None
                # Include the new index so clients can sync
                # currentTrack/currentIndex immediately instead of
                # waiting for the next player_state snapshot (#4144).
                await broadcast_typed(
                    self.connection_manager,
                    "track_changed",
                    {
                        "action": action,
                        "track_index": track_index,
                        "seq": seq,
                    },
                )

            message = f"Skipped to {action} track"
            logger.info(f"{emoji} {message}")
            return {"message": message}

        except Exception as e:
            logger.error(f"Failed to skip to {action} track: {e}")
            raise
