"""
Player State Manager
~~~~~~~~~~~~~~~~~~~

Centralized state management and broadcasting for Auralis player.
Single source of truth that broadcasts state changes via WebSocket.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any, cast

from helpers import spawn_background_task
from player_state import PlaybackState, PlayerState, TrackInfo, create_track_info
from websocket.outbound_messages import PlayerStatePayload, broadcast_typed

logger = logging.getLogger(__name__)


class PlayerStateManager:
    """
    Centralized player state manager.

    Maintains the single source of truth for player state and broadcasts
    changes to all connected clients via WebSocket.
    """

    def __init__(self, websocket_manager: Any) -> None:
        """
        Initialize state manager

        Args:
            websocket_manager: WebSocket connection manager for broadcasting
        """
        self.state: PlayerState = PlayerState()
        self.ws_manager: Any = websocket_manager
        self._lock: asyncio.Lock = asyncio.Lock()
        self._position_update_task: asyncio.Task[Any] | None = None
        self._update_seq: int = 0

    def get_state(self) -> PlayerState:
        """Get current player state snapshot"""
        return self.state.model_copy(deep=True)

    async def _mutate_state(self, **kwargs: Any) -> PlayerState:
        """Apply a state mutation and return its sequenced snapshot."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)

            self.state.is_playing = (self.state.state == PlaybackState.PLAYING)
            self.state.is_paused = (self.state.state == PlaybackState.PAUSED)

            if self.state.current_track:
                self.state.duration = self.state.current_track.duration

            self._update_seq += 1
            self.state.seq = self._update_seq
            return self.state.model_copy(deep=True)

    async def broadcast_state(self, state: PlayerState) -> None:
        """Broadcast a snapshot previously returned by a deferred mutation."""
        await self._broadcast_state(state)

    async def update_state(self, **kwargs: Any) -> None:
        """
        Update player state and broadcast changes.

        #3723 held the broadcast inside `_lock` so concurrent update_state()
        calls could not reorder their outgoing WebSocket messages — but that
        meant a single slow WS client (full TCP receive buffer, backgrounded
        Electron client) stalled every other update_state() call for the
        duration of its send (#3732). Fixed via a monotonic `seq` counter
        instead: mutation + snapshot happen under the lock, the lock is
        released, and the broadcast (which can now race with other
        broadcasts) runs outside it. The frontend
        (usePlayerStateSync.ts) drops any snapshot with `seq` less than the
        highest it has already applied, so out-of-order delivery can no
        longer regress observers to a stale state.

        Args:
            **kwargs: Fields to update in PlayerState
        """
        state_snapshot = await self._mutate_state(**kwargs)

        # Broadcast outside the lock (#3732) — a slow/stalled WS client no
        # longer blocks concurrent update_state() callers.
        await self.broadcast_state(state_snapshot)

    async def set_track(
        self, track: Any, library_database: Any, *, broadcast: bool = True
    ) -> PlayerState:
        """
        Set current track and broadcast

        Args:
            track: Track object from database
            library_database: Library manager to fetch track details
        """
        if track is None:
            state_snapshot = await self._mutate_state(
                current_track=None,
                current_time=0.0,
                duration=0.0,
                state=PlaybackState.STOPPED
            )
        else:
            track_info = create_track_info(track)
            state_snapshot = await self._mutate_state(
                current_track=track_info,
                current_time=0.0,
                duration=track_info.duration if track_info else 0.0,
                state=PlaybackState.LOADING
            )

        if broadcast:
            await self.broadcast_state(state_snapshot)
        return state_snapshot

    async def set_playing(
        self, playing: bool, *, broadcast: bool = True
    ) -> PlayerState:
        """Set playing state, optionally deferring its sequenced broadcast."""
        new_state = PlaybackState.PLAYING if playing else PlaybackState.PAUSED
        state_snapshot = await self._mutate_state(state=new_state)

        if broadcast:
            await self.broadcast_state(state_snapshot)

        # Start/stop position updates
        if playing:
            self._start_position_updates()
        else:
            await self._stop_position_updates()
        return state_snapshot

    async def set_position(self, position: float) -> None:
        """Set playback position"""
        await self.update_state(current_time=position)

    async def set_volume(self, volume: int) -> None:
        """Set volume level"""
        await self.update_state(
            volume=max(0, min(100, volume)),
            is_muted=(volume == 0)
        )

    async def set_queue(
        self,
        tracks: list[TrackInfo],
        start_index: int = 0,
        *,
        broadcast: bool = True,
    ) -> PlayerState:
        """Set playback queue, optionally deferring its sequenced broadcast."""
        current_track = tracks[start_index] if tracks and 0 <= start_index < len(tracks) else None
        state_snapshot = await self._mutate_state(
            queue=tracks,
            queue_size=len(tracks),
            queue_index=start_index,
            current_track=current_track
        )
        if broadcast:
            await self.broadcast_state(state_snapshot)
        return state_snapshot

    async def follow_navigation(
        self, queue_index: int, filepath: str | None, *, broadcast: bool = True
    ) -> PlayerState | None:
        """Make the track the engine just moved to the new "now playing" (#5456).

        This manager used to own a second notion of "what plays next": it
        re-indexed its own queue whenever its wall-clock position estimate
        reached the track's duration, independently of the engine and of the
        frontend's completion-driven advance (which goes through
        NavigationService). It no longer advances on its own — NavigationService
        calls this after the engine has moved, so one path decides.

        The track is matched by ``filepath``: this manager's queue copy can be
        stale after queue edits, so its index may name a different track. The
        index is used alone only when the engine reported no filepath. Returns
        None, changing nothing, when neither identifies a track.
        """
        async with self._lock:
            if filepath is not None:
                match = next(
                    (t for t in self.state.queue if t.filepath == filepath), None
                )
            elif 0 <= queue_index < len(self.state.queue):
                match = self.state.queue[queue_index]
            else:
                match = None
        if match is None:
            return None

        state_snapshot = await self._mutate_state(
            queue_index=queue_index, current_track=match, current_time=0.0
        )
        if broadcast:
            await self.broadcast_state(state_snapshot)
        return state_snapshot

    async def _broadcast_state(self, state: PlayerState) -> None:
        """Broadcast state to all WebSocket clients"""
        payload = cast(PlayerStatePayload, state.model_dump())
        await broadcast_typed(self.ws_manager, "player_state", payload)

    async def shutdown(self) -> None:
        """Stop this manager's background work (#4747).

        The 1 Hz position loop was previously only reachable from
        ``set_playing(False)``, so the app lifespan — which tears down every
        other long-lived component explicitly — left it running when the
        process shut down mid-playback. The loop kept broadcasting
        ``position_changed`` against closing WebSockets until the event loop
        went away, producing "Task was destroyed but it is pending" at
        teardown.

        Public and idempotent: ``_shutdown_components`` calls it without
        knowing whether playback was ever started, and calling it twice (or
        after a pause already stopped the loop) is a no-op.
        """
        await self._stop_position_updates()

    def _start_position_updates(self) -> None:
        """Start periodic position updates (called when playback starts)"""
        if self._position_update_task is None or self._position_update_task.done():
            self._position_update_task = spawn_background_task(self._position_update_loop(), name="state_manager._position_update_loop")

    async def _stop_position_updates(self) -> None:
        """Stop position updates (called when playback pauses).

        Awaits the cancelled task rather than firing and forgetting (#4543
        SIBLING). Without the await, set_playing(False) could return while the
        loop was still unwinding, letting one more position_changed tick land
        after the pause — and leaving a task in flight at teardown. The loop
        catches CancelledError and returns immediately, so this is prompt.
        """
        task = self._position_update_task
        self._position_update_task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _position_update_loop(self) -> None:
        """Update position every second while playing, corrected for event-loop drift.

        asyncio.sleep(1.0) can fire slightly late when the loop is busy.
        Recording the wall-clock timestamp of the previous tick and using the
        actual elapsed time prevents the 10-20ms/tick drift that accumulates
        into visible position lag over a 3-minute track (fixes #2171).

        A pure position ticker (#5456): at the track's duration it holds there
        and stays alive rather than advancing the queue, so the next track is
        chosen only by navigation (follow_navigation), which resets the
        position the loop then keeps ticking.
        """
        loop = asyncio.get_running_loop()
        last_tick = loop.time()
        try:
            while True:
                await asyncio.sleep(1.0)
                now = loop.time()
                elapsed = now - last_tick
                last_tick = now

                new_time: float | None = None
                tick_seq: int = 0

                async with self._lock:
                    if self.state.is_playing and self.state.current_track:
                        # Advance by actual elapsed wall-clock time, not a fixed 1.0s
                        previous_time = self.state.current_time
                        new_time = min(
                            previous_time + elapsed,
                            self.state.duration
                        )
                        self.state.current_time = new_time

                        # Read the CURRENT generation without bumping it (#4544).
                        # This tick is a refinement of the last state, not a new
                        # generation, so it must not advance _update_seq — but it
                        # must carry a stamp so the frontend can drop it if a
                        # newer player_state has already been applied. Read here,
                        # inside the same lock that computed new_time, so the
                        # stamp always describes the value it travels with.
                        tick_seq = self._update_seq

                        # Held at the track end (#5456): nothing new to report
                        # until navigation moves to another track. The loop
                        # stays alive (#4545) so that track keeps ticking.
                        if new_time == previous_time:
                            new_time = None

                # Broadcast lightweight position update (fixes #2570) — avoids
                # serialising the full queue + track info every second.
                if new_time is not None:
                    await broadcast_typed(
                        self.ws_manager,
                        "position_changed",
                        {"position": new_time, "seq": tick_seq},
                    )
        except asyncio.CancelledError:
            pass  # Normal cancellation
