"""PlayerState follows the engine after queue replacements and removals (#6592, #6594, #6595).

Real QueueController and real PlayerStateManager; only the library, the decoder and the socket
are stand-ins.

* #6592: set_queue / clear_queue reset the engine's shuffle flag (QueueManager.clear, #5728), but
  PlayerState and the clients kept showing shuffle on.
* #6594: removing the playing item stops the engine, but PlayerState kept PLAYING, the old
  position and a running position ticker.
* #6595: unshuffle's "No shuffle to undo" path broadcast player_state while holding the engine lock.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.state_manager import PlayerStateManager  # noqa: E402
from player_state import PlaybackState, create_track_info  # noqa: E402
from services.queue_service import QueueService  # noqa: E402

from auralis.player.queue_controller import QueueController  # noqa: E402

pytestmark = pytest.mark.asyncio


def _track(track_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=track_id, title=f"T{track_id}", filepath=f"/m/{track_id}.flac", duration=200.0,
        artists=[], album=None, album_id=None, format="flac",
    )


class _Sockets:
    """Connection manager that records every frame and whether the engine lock was held."""

    def __init__(self):
        self.frames: list[dict] = []
        self.service: QueueService | None = None
        self.sent_under_engine_lock: list[str] = []

    async def broadcast(self, message):
        self.frames.append(message)
        if self.service is not None and self.service._set_queue_engine_lock.locked():
            self.sent_under_engine_lock.append(message.get("type"))

    def shuffled_flags(self) -> list[bool]:
        return [f["data"]["is_shuffled"] for f in self.frames if f.get("type") == "queue_shuffled"]


@pytest.fixture
async def world():
    tracks = {i: _track(i) for i in range(1, 6)}
    by_path = {t.filepath: t for t in tracks.values()}
    repo = MagicMock()
    repo.get_by_ids = MagicMock(side_effect=lambda ids: {i: tracks[i] for i in ids if i in tracks})
    repo.get_by_paths = MagicMock(side_effect=lambda paths: {p: by_path[p] for p in paths if p in by_path})

    controller = QueueController(lambda: None)
    audio_player = SimpleNamespace(
        queue=controller,
        load_file=MagicMock(return_value=True),
        play=MagicMock(),
        stop=MagicMock(),
        playback=SimpleNamespace(stop=MagicMock()),
    )
    sockets = _Sockets()
    state = PlayerStateManager(sockets)
    service = QueueService(
        audio_player=audio_player,
        player_state_manager=state,
        library_database=SimpleNamespace(tracks=repo),
        connection_manager=sockets,
        create_track_info_fn=create_track_info,
    )
    sockets.service = service
    yield SimpleNamespace(service=service, state=state, sockets=sockets, controller=controller, player=audio_player)
    await state.shutdown()


async def _shuffled(world, track_ids=(1, 2, 3, 4)):
    await world.service.set_queue(list(track_ids), 0)
    await world.service.shuffle_queue()
    assert world.state.get_state().shuffle_enabled is True
    world.sockets.frames.clear()


async def test_set_queue_turns_shuffle_off_everywhere_6592(world):
    await _shuffled(world)

    await world.service.set_queue([3, 4, 5], 0)

    assert world.controller.shuffle_enabled is False
    assert world.state.get_state().shuffle_enabled is False
    assert world.sockets.shuffled_flags() == [False]


async def test_clear_queue_turns_shuffle_off_everywhere_6592(world):
    await _shuffled(world)

    await world.service.clear_queue()

    assert world.controller.shuffle_enabled is False
    assert world.state.get_state().shuffle_enabled is False
    assert world.sockets.shuffled_flags() == [False]


async def test_an_unshuffled_set_queue_sends_no_shuffle_frame_6592(world):
    await world.service.set_queue([1, 2], 0)
    world.sockets.frames.clear()

    await world.service.set_queue([3, 4], 0)

    assert world.sockets.shuffled_flags() == []


async def test_unshuffle_says_so_once_6592(world):
    await _shuffled(world)

    await world.service.unshuffle_queue()

    assert world.state.get_state().shuffle_enabled is False
    assert world.sockets.shuffled_flags() == [False]


async def test_no_shuffle_to_undo_broadcasts_outside_the_engine_lock_6595(world):
    await _shuffled(world)
    await world.service.add_track_to_queue(5)  # any edit drops the pre-shuffle snapshot
    world.sockets.sent_under_engine_lock.clear()

    result = await world.service.unshuffle_queue()

    assert result["message"] == "No shuffle to undo"
    assert world.state.get_state().shuffle_enabled is False
    assert world.sockets.sent_under_engine_lock == []


async def test_removing_the_playing_track_records_the_stopped_engine_6594(world):
    await world.service.set_queue([1, 2, 3], 0)
    await world.state.update_state(current_time=42.0)
    assert world.state.get_state().is_playing is True

    await world.service.remove_track_from_queue(0)

    state = world.state.get_state()
    world.player.load_file.assert_called_with("/m/2.flac")  # the engine is stopped on the successor
    assert state.current_track is not None and state.current_track.id == 2
    assert state.state == PlaybackState.STOPPED
    assert state.is_playing is False
    assert state.current_time == 0.0
    assert world.state._position_update_task is None


async def test_removing_the_last_track_records_a_stopped_empty_player_6594(world):
    await world.service.set_queue([1], 0)

    await world.service.remove_track_from_queue(0)

    state = world.state.get_state()
    world.player.playback.stop.assert_called_once()
    assert state.current_track is None
    assert state.state == PlaybackState.STOPPED
    assert state.is_playing is False


async def test_removing_another_track_leaves_playback_alone_6594(world):
    await world.service.set_queue([1, 2, 3], 0)

    await world.service.remove_track_from_queue(2)

    assert world.state.get_state().state == PlaybackState.PLAYING
