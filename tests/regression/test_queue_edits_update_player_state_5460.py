"""Queue edits update PlayerStateManager's copy of the queue (#5460).

Only set_queue used to write PlayerStateManager.state.queue. Every other edit
(add, remove, move, reorder, shuffle, unshuffle, clear) changed the engine and
broadcast queue_changed, so the next unrelated player_state (a volume change, a
pause, a navigation) carried the PRE-edit queue and the frontend applied it,
undoing the edit on screen. Built on a real PlayerStateManager so the stale copy
is what the assertions read.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.state_manager import PlayerStateManager
from player_state import TrackInfo
from services.queue_service import QueueService

from auralis.player.queue_controller import QueueController

IDS = [1, 2, 3, 4]


def _db_track(track_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=track_id, title=f"Track {track_id}", filepath=f"/music/track_{track_id}.flac",
        artists=[SimpleNamespace(name="Artist")], album=SimpleNamespace(title="Album", id=1),
        duration=180.0,
    )


def _track_info(track: SimpleNamespace) -> TrackInfo:
    return TrackInfo(id=track.id, title=track.title, artist="Artist", album="Album",
                     duration=track.duration, filepath=track.filepath)


async def _service(current: int = 1) -> tuple[QueueService, QueueController, PlayerStateManager, MagicMock]:
    tracks = {i: _db_track(i) for i in IDS + [9]}
    by_path = {t.filepath: t for t in tracks.values()}
    repo = MagicMock()
    repo.get_by_id = MagicMock(side_effect=tracks.get)
    repo.get_by_ids = MagicMock(side_effect=lambda ids: {i: tracks[i] for i in ids if i in tracks})
    repo.get_by_paths = MagicMock(side_effect=lambda paths: {p: by_path[p] for p in paths if p in by_path})

    ws = MagicMock()
    ws.broadcast = AsyncMock()
    state = PlayerStateManager(ws)
    controller = QueueController(lambda: None)
    controller.set_queue([tracks[i].__dict__ for i in IDS], start_index=current)
    await state.set_queue([_track_info(tracks[i]) for i in IDS], current, broadcast=False)

    service = QueueService(
        audio_player=SimpleNamespace(queue=controller, load_file=lambda _p: True, stop=lambda: None),
        player_state_manager=state,
        library_database=SimpleNamespace(tracks=repo),
        connection_manager=ws,
        create_track_info_fn=_track_info,
    )
    return service, controller, state, ws


def _state_ids(state: PlayerStateManager) -> list[int]:
    return [t.id for t in state.get_state().queue]


def _engine_ids(controller: QueueController) -> list[int]:
    return [t["id"] for t in controller.get_queue()]


@pytest.mark.regression
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "edit",
    [
        lambda s: s.add_track_to_queue(9),
        lambda s: s.add_track_to_queue(9, position=0),
        lambda s: s.remove_track_from_queue(3),
        lambda s: s.move_track_in_queue(3, 0),
        lambda s: s.reorder_queue([3, 2, 1, 0]),
        lambda s: s.shuffle_queue(),
    ],
    ids=["add", "insert", "remove", "move", "reorder", "shuffle"],
)
async def test_every_edit_leaves_player_state_holding_the_edited_queue(edit):
    service, controller, state, _ = await _service()

    await edit(service)

    assert _state_ids(state) == _engine_ids(controller)
    assert state.get_state().queue_size == len(controller.get_queue())


@pytest.mark.regression
@pytest.mark.asyncio
async def test_unshuffle_restores_player_state_too():
    service, controller, state, _ = await _service()
    await service.shuffle_queue()
    await service.unshuffle_queue()
    assert _state_ids(state) == _engine_ids(controller) == IDS


@pytest.mark.regression
@pytest.mark.asyncio
async def test_removing_the_playing_track_makes_its_successor_current():
    service, _, state, _ = await _service(current=1)  # track 2 playing

    await service.remove_track_from_queue(1)

    assert _state_ids(state) == [1, 3, 4]
    assert state.get_state().current_track.id == 3


@pytest.mark.regression
@pytest.mark.asyncio
async def test_clear_empties_player_state_queue():
    service, _, state, _ = await _service()
    await service.clear_queue()
    assert state.get_state().queue == []
    assert state.get_state().current_track is None


@pytest.mark.regression
@pytest.mark.asyncio
async def test_an_unrelated_broadcast_after_an_edit_carries_the_edited_queue():
    """The issue's integration case: edit, then a volume change broadcasts player_state."""
    service, controller, state, ws = await _service()
    await service.add_track_to_queue(9)
    ws.broadcast.reset_mock()

    await state.set_volume(40)

    player_states = [c.args[0] for c in ws.broadcast.call_args_list if c.args[0].get("type") == "player_state"]
    assert player_states, "set_volume must broadcast a player_state"
    queue = player_states[-1]["data"]["queue"]
    assert [t["id"] for t in queue] == _engine_ids(controller) == IDS + [9]
