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
from typing import TYPE_CHECKING, Any

from core.state_manager import PlayerStateManager
from websocket.outbound_messages import broadcast_typed

from auralis import AudioPlayer

from .errors import InvalidRequest, ServiceUnavailable
from .queue_enrichment import entry_filepath

if TYPE_CHECKING:
    from config.globals import ConnectionManager
    from player_state import PlayerState

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
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self._seq = 0

    @property
    def lock(self) -> asyncio.Lock:
        """Lazily (re)bind the lock to the current running loop.

        `asyncio.Lock` binds to whatever loop is running at its first
        `acquire()`, not at construction — reusing it from a *different*
        loop later raises "bound to a different event loop". This module-
        level singleton is created at import time, before any loop
        necessarily exists, and outlives any one loop in test contexts
        (each pytest-asyncio test gets a fresh loop). A long-running server
        process has exactly one loop for its whole lifetime, so this only
        ever (re)creates the lock once there in practice.
        """
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

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
        connection_manager: ConnectionManager,
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
        self.connection_manager: ConnectionManager = connection_manager
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
        if not self.audio_player:
            raise ServiceUnavailable("Audio player not available")

        try:
            # Check if player has next_track method
            if hasattr(self.audio_player, 'next_track'):
                # Serialize the engine mutation + index read + seq assignment
                # (#4582) — see _TrackChangeSequencer. Broadcast stays outside
                # the lock so one slow WS client can't stall the next command.
                async with _sequencer.lock:
                    success = await asyncio.to_thread(self.audio_player.next_track)
                    track_index = None
                    seq = None
                    state_snapshot = None
                    if success and self.player_state_manager and hasattr(self.audio_player, 'queue'):
                        if hasattr(self.audio_player.queue, 'current_index'):
                            track_index = self.audio_player.queue.current_index
                            state_snapshot = await self._follow_engine(track_index)
                            seq = _sequencer.next_seq()

                if success:
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
                                "action": "next",
                                "track_index": track_index,
                                "seq": seq,
                            },
                        )

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
            ServiceUnavailable: If the audio player is not available (#5338)
            Exception: If operation fails
        """
        if not self.audio_player:
            raise ServiceUnavailable("Audio player not available")

        try:
            # Check if player has previous_track method
            if hasattr(self.audio_player, 'previous_track'):
                # Serialize the engine mutation + index read + seq assignment
                # (#4582) — see _TrackChangeSequencer, shared with next_track
                # so the two can't interleave against each other either.
                async with _sequencer.lock:
                    success = await asyncio.to_thread(self.audio_player.previous_track)
                    track_index = None
                    seq = None
                    state_snapshot = None
                    if success and self.player_state_manager and hasattr(self.audio_player, 'queue'):
                        if hasattr(self.audio_player.queue, 'current_index'):
                            track_index = self.audio_player.queue.current_index
                            state_snapshot = await self._follow_engine(track_index)
                            seq = _sequencer.next_seq()

                if success:
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
                                "action": "previous",
                                "track_index": track_index,
                                "seq": seq,
                            },
                        )

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
            ServiceUnavailable: If the audio player, player state manager, or
                queue is not available (#5338)
            InvalidRequest: If track_index is out of range (#5338)
            Exception: If operation fails
        """
        if not self.audio_player:
            raise ServiceUnavailable("Audio player not available")
        if not self.player_state_manager:
            raise ServiceUnavailable("Player state manager not available")

        try:
            # Get current queue
            if not hasattr(self.audio_player, 'queue'):
                raise ServiceUnavailable("Queue not available")

            queue_manager = self.audio_player.queue
            queue_size = await asyncio.to_thread(queue_manager.get_queue_size)

            # Validate index
            if track_index < 0 or track_index >= queue_size:
                raise InvalidRequest(f"Invalid track index: {track_index}")

            # Serialize the same mutate-and-tag step as next/previous (#4582)
            # — see _TrackChangeSequencer — so a Jump racing a rapid Next/
            # Previous burst can't broadcast track_changed out of order.
            async with _sequencer.lock:
                # Set queue position
                if hasattr(queue_manager, 'set_current_index'):
                    await asyncio.to_thread(queue_manager.set_current_index, track_index)
                else:
                    # Fallback: manually get queue and load track
                    queue = await asyncio.to_thread(queue_manager.get_queue)
                    if track_index < len(queue):
                        track_path = queue[track_index]
                        if hasattr(self.audio_player, 'load_file'):
                            await asyncio.to_thread(self.audio_player.load_file, track_path)  # type: ignore[arg-type]

                # Start playback
                if hasattr(self.audio_player, 'play'):
                    await asyncio.to_thread(self.audio_player.play)

                # Update state — the jumped-to track first (#5456), so the
                # set_playing broadcast (deferred below, #5324) already
                # carries it.
                await self._follow_engine(track_index)
                # #5324: broadcast=False — next_track/previous_track already
                # broadcast only after releasing _sequencer.lock; jump_to_track
                # was the one outlier still awaiting a broadcast (bounded by
                # BROADCAST_SEND_TIMEOUT per client) while holding it, which
                # could stall every other next/previous/jump behind one slow
                # WS client. Snapshot captured here, broadcast after release.
                state_snapshot = await self.player_state_manager.set_playing(True, broadcast=False)
                seq = _sequencer.next_seq()

            # Broadcast state and track change — both outside _sequencer.lock.
            await self.player_state_manager.broadcast_state(state_snapshot)
            await broadcast_typed(
                self.connection_manager,
                "track_changed",
                {
                    "action": "jumped",
                    "track_index": track_index,
                    "seq": seq,
                },
            )

            logger.info(f"Jumped to track {track_index}")
            return {
                "message": "Jumped to track successfully",
                "track_index": track_index
            }

        except Exception as e:
            logger.error(f"Failed to jump to track {track_index}: {e}")
            raise
