"""set_playing() starts or stops the position ticker from the state, not its argument (#6549).

set_playing(False) mutated the state, awaited its broadcast, and only then
stopped the ticker because its argument was False. A set_playing(True) landing
in that await found the old ticker alive and started nothing; the first call
then cancelled it, leaving the state PLAYING with no ticker and the UI position
frozen. Both calls now reconcile the ticker to ``state.is_playing``.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.state_manager import PlayerStateManager  # noqa: E402

pytestmark = pytest.mark.asyncio


def _ticking(manager: PlayerStateManager) -> bool:
    task = manager._position_update_task
    return task is not None and not task.done()


async def test_a_play_during_a_pause_broadcast_keeps_its_ticker():
    ws = MagicMock()
    ws.broadcast = AsyncMock()
    manager = PlayerStateManager(ws)
    await manager.set_playing(True, broadcast=False)
    assert _ticking(manager)

    in_broadcast, release = asyncio.Event(), asyncio.Event()

    async def slow_broadcast(_state):
        in_broadcast.set()
        await release.wait()

    manager.broadcast_state = slow_broadcast  # only the pause broadcasts
    pausing = asyncio.create_task(manager.set_playing(False))
    await in_broadcast.wait()
    await manager.set_playing(True, broadcast=False)  # e.g. PlaybackService.play()
    release.set()
    await pausing

    assert manager.get_state().is_playing
    assert _ticking(manager), "state is PLAYING but the position ticker was stopped"
    await manager._stop_position_updates()


async def test_a_plain_pause_still_stops_the_ticker():
    ws = MagicMock()
    ws.broadcast = AsyncMock()
    manager = PlayerStateManager(ws)
    await manager.set_playing(True, broadcast=False)

    await manager.set_playing(False, broadcast=False)

    assert not manager.get_state().is_playing
    assert not _ticking(manager)
