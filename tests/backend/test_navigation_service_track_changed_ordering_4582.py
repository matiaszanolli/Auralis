"""
Regression tests for #4582: `track_changed` broadcasts carry a monotonic
`seq` and can no longer interleave out of order under a rapid skip burst.

Root cause: NavigationService is re-instantiated per HTTP request (routers/
player.py wires it via FastAPI `Depends()`), so a lock or counter on `self`
would never contend with another request's instance — three concurrent
"Next" clicks hit three separate NavigationService objects, and nothing
serialized their engine-mutate-then-broadcast steps. `_TrackChangeSequencer`
is a module-level singleton for exactly this reason; these tests would be
unable to detect the bug at all against an instance-level lock/counter,
since MagicMock-based unit tests exercise one NavigationService per test but
must still prove the *module-level* state is what's actually shared.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.navigation_service import NavigationService  # noqa: E402


def _make_service(index_counter: dict) -> NavigationService:
    """A NavigationService whose engine mutation deterministically advances
    a shared index counter by 1 each call -- standing in for the real
    engine's queue.current_index, which every concurrent call also mutates.
    """
    audio_player = MagicMock()

    def _next_track():
        index_counter["value"] += 1
        audio_player.queue.current_index = index_counter["value"]
        return True

    audio_player.next_track = MagicMock(side_effect=_next_track)
    audio_player.queue = MagicMock()
    audio_player.queue.current_index = index_counter["value"]

    state_manager = MagicMock()
    state_manager.set_playing = AsyncMock()

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    return NavigationService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        connection_manager=connection_manager,
        create_track_info_fn=MagicMock(),
    )


@pytest.mark.asyncio
async def test_concurrent_next_track_calls_get_unique_monotonic_seq():
    """N concurrent next_track() calls (a rapid skip burst) must each get a
    distinct seq, and sorting the broadcasts by seq must recover the exact
    order the engine's index actually advanced in -- proving the lock
    prevented the mutate-and-tag step from interleaving, even though the
    broadcasts themselves are sent outside the lock and may arrive at the
    wire in a different order.
    """
    index_counter = {"value": -1}
    service = _make_service(index_counter)

    await asyncio.gather(*(service.next_track() for _ in range(10)))

    broadcasts = [c.args[0] for c in service.connection_manager.broadcast.await_args_list]
    seqs = [b["data"]["seq"] for b in broadcasts]
    indices = [b["data"]["track_index"] for b in broadcasts]

    # No two concurrent calls ever raced onto the same seq value.
    assert len(set(seqs)) == len(seqs) == 10

    # Sorting by seq must recover the true mutation order (0..9) -- if the
    # lock did not serialize mutate+tag, a call whose engine mutation landed
    # early could still get a later seq (or vice versa), breaking this.
    by_seq = sorted(zip(seqs, indices))
    assert [idx for _, idx in by_seq] == list(range(10))


@pytest.mark.asyncio
async def test_next_and_jump_share_one_sequence_and_never_collide():
    """next_track() and jump_to_track() must draw from the SAME counter
    (module-level _sequencer), not independent per-method counters -- a Jump
    racing a Next burst still needs one shared ordering to guard against.
    """
    index_counter = {"value": -1}
    service = _make_service(index_counter)
    service.audio_player.queue.get_queue_size = MagicMock(return_value=100)
    service.audio_player.queue.set_current_index = MagicMock()
    service.audio_player.play = MagicMock()

    await asyncio.gather(
        service.next_track(),
        service.jump_to_track(42),
        service.next_track(),
    )

    broadcasts = [c.args[0] for c in service.connection_manager.broadcast.await_args_list]
    seqs = [b["data"]["seq"] for b in broadcasts]
    assert len(set(seqs)) == len(seqs) == 3
