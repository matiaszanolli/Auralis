"""Player-state snapshots are shallow copies: O(1) in the queue length (#5960).

get_state() and every update_state() deep-copied the whole state, queue included (~2.3 ms per
1000 tracks, so ~45 ms on a 20 000-track "play the library" queue). The manager never mutates the
queue in place, it replaces it, so a shallow copy is isolated enough.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.state_manager import PlayerStateManager  # noqa: E402
from player_state import TrackInfo  # noqa: E402


def _manager() -> PlayerStateManager:
    ws = MagicMock()
    ws.broadcast = AsyncMock()
    return PlayerStateManager(ws)


def _tracks(n: int) -> list[TrackInfo]:
    return [TrackInfo(id=i, title=f"t{i}", artist="a", album="b", duration=1.0, filepath=f"/m/{i}.flac") for i in range(n)]


def test_snapshot_shares_the_queue_instead_of_copying_it():
    manager = _manager()
    manager.state.queue = _tracks(20_000)

    assert manager.get_state().queue is manager.state.queue  # no per-call O(queue) copy


def test_a_snapshot_keeps_its_own_scalars_when_state_moves_on():
    manager = _manager()
    asyncio.run(manager.update_state(volume=30, current_time=5.0))
    snapshot = manager.get_state()

    asyncio.run(manager.update_state(volume=90, current_time=9.0))

    assert (snapshot.volume, snapshot.current_time) == (30, 5.0)
    assert (manager.state.volume, manager.state.current_time) == (90, 9.0)


def test_replacing_the_queue_leaves_earlier_snapshots_with_the_old_one():
    manager = _manager()
    asyncio.run(manager.update_state(queue=_tracks(3), queue_size=3))
    snapshot = manager.get_state()

    asyncio.run(manager.update_state(queue=_tracks(5), queue_size=5))

    assert len(snapshot.queue) == 3
    assert len(manager.state.queue) == 5
