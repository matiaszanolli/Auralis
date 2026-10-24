#!/usr/bin/env python3

"""
Position Ticker
~~~~~~~~~~~~~~~~

The once-per-second position loop of ``PlayerStateManager``, split out as a
mixin (#6269): it is independent of the state mutators and only needs the
host's ``state``, ``_lock``, ``_position_update_task`` and
``_broadcast_state``. Drift-corrected ticking (#2171); a pure ticker that
holds at duration rather than advancing the queue (#5456).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
from typing import TYPE_CHECKING, Any

from helpers import spawn_background_task
from websocket.outbound_messages import broadcast_typed

if TYPE_CHECKING:
    from player_state import PlayerState


class PositionTickerMixin:
    """Hosts provide ``state``, ``_lock``, ``ws_manager``,
    ``_position_update_task`` and ``async _broadcast_state(state)`` —
    ``PlayerStateManager`` declares all of them."""

    _position_update_task: asyncio.Task[Any] | None
    _lock: asyncio.Lock
    ws_manager: Any
    _update_seq: int

    if TYPE_CHECKING:
        from player_state import PlayerState as _PlayerState

        state: _PlayerState

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
