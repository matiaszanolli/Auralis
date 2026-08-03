"""Regression coverage for sequenced, deferred player-state broadcasts."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.state_manager import PlayerStateManager
from player_state import PlaybackState, TrackInfo


@pytest.mark.regression
@pytest.mark.asyncio
async def test_set_playing_can_defer_broadcast_without_deferring_mutation():
    websocket_manager = AsyncMock()
    manager = PlayerStateManager(websocket_manager)

    snapshot = await manager.set_playing(True, broadcast=False)

    assert manager.get_state().state == PlaybackState.PLAYING
    assert snapshot.state == PlaybackState.PLAYING
    assert snapshot.seq == 1
    websocket_manager.broadcast.assert_not_awaited()

    await manager.broadcast_state(snapshot)

    websocket_manager.broadcast.assert_awaited_once()
    await manager.set_playing(False, broadcast=False)


@pytest.mark.regression
@pytest.mark.asyncio
async def test_deferred_queue_snapshots_keep_seq_when_broadcast_out_of_order():
    websocket_manager = AsyncMock()
    manager = PlayerStateManager(websocket_manager)
    first_track = TrackInfo(
        id=1, title="First", artist="Artist", album="Album",
        duration=180.0, filepath="/music/first.flac",
    )
    second_track = TrackInfo(
        id=2, title="Second", artist="Artist", album="Album",
        duration=200.0, filepath="/music/second.flac",
    )

    first = await manager.set_queue([first_track], broadcast=False)
    second = await manager.set_queue([second_track], broadcast=False)
    await manager.broadcast_state(second)
    await manager.broadcast_state(first)

    payloads = [call.args[0]["data"] for call in websocket_manager.broadcast.await_args_list]
    assert [payload["seq"] for payload in payloads] == [2, 1]
    assert manager.get_state().current_track == second_track
    assert manager.get_state().seq == 2
