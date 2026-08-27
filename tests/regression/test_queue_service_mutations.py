"""Regression coverage for atomic QueueService mutations and hydration."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from player_state import TrackInfo
from services.queue_service import QueueService

from auralis.player.queue_controller import QueueController


def _db_track(track_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=track_id,
        title=f"Track {track_id}",
        filepath=f"/music/track_{track_id}.flac",
        artists=[SimpleNamespace(name="Artist")],
        album=SimpleNamespace(title="Album", id=1),
        duration=180.0,
    )


def _track_info(track: SimpleNamespace) -> TrackInfo:
    return TrackInfo(
        id=track.id,
        title=track.title,
        artist="Artist",
        album="Album",
        duration=track.duration,
        filepath=track.filepath,
    )


def _build_service(track_ids: list[int]) -> tuple[QueueService, QueueController, MagicMock]:
    tracks = {track_id: _db_track(track_id) for track_id in track_ids}
    repo = MagicMock()
    repo.get_by_id = MagicMock(side_effect=tracks.get)
    repo.get_by_ids = MagicMock(
        side_effect=lambda ids: {track_id: tracks[track_id] for track_id in ids if track_id in tracks}
    )
    library_database = SimpleNamespace(tracks=repo)

    controller = QueueController(lambda: None)
    audio_player = SimpleNamespace(queue=controller)
    state_manager = MagicMock()
    state_manager.get_state.return_value = SimpleNamespace(queue=[])
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    service = QueueService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        library_database=library_database,
        connection_manager=connection_manager,
        create_track_info_fn=_track_info,
    )
    return service, controller, repo


@pytest.mark.regression
@pytest.mark.asyncio
async def test_default_add_appends_through_queue_controller():
    service, queue, _ = _build_service([1, 2, 99])
    queue.set_queue([_db_track(1).__dict__, _db_track(2).__dict__], start_index=1)

    result = await service.add_track_to_queue(99)

    assert [track['id'] for track in queue.get_queue()] == [1, 2, 99]
    assert queue.get_current_track()['id'] == 2
    assert queue.current_index == 1
    assert result['position'] is None


@pytest.mark.regression
@pytest.mark.asyncio
async def test_positional_add_before_current_preserves_playing_track():
    service, queue, _ = _build_service([1, 2, 99])
    queue.set_queue([_db_track(1).__dict__, _db_track(2).__dict__], start_index=1)

    result = await service.add_track_to_queue(99, position=0)

    assert [track['id'] for track in queue.get_queue()] == [99, 1, 2]
    assert queue.get_current_track()['id'] == 2
    assert queue.current_index == 2
    assert result['position'] == 0


@pytest.mark.regression
@pytest.mark.asyncio
async def test_move_before_current_preserves_playing_track():
    service, queue, _ = _build_service([1, 2, 3])
    queue.set_queue(
        [_db_track(1).__dict__, _db_track(2).__dict__, _db_track(3).__dict__],
        start_index=1,
    )

    await service.move_track_in_queue(2, 0)

    assert [track['id'] for track in queue.get_queue()] == [3, 1, 2]
    assert queue.get_current_track()['id'] == 2
    assert queue.current_index == 2


@pytest.mark.regression
@pytest.mark.asyncio
async def test_queue_changed_hydrates_ids_with_one_repository_call():
    service, queue, repo = _build_service([1, 2])
    queue.set_queue(
        [
            {'id': 1, 'filepath': '/music/track_1.flac'},
            {'track_id': 2, 'filepath': '/music/track_2.flac'},
            {'id': 404, 'filepath': '/music/missing.flac'},
            {'id': 1, 'filepath': '/music/track_1.flac'},
        ],
        start_index=0,
    )

    await service._broadcast_queue_changed(action='test')

    repo.get_by_ids.assert_called_once_with([1, 2, 404])
    repo.get_by_id.assert_not_called()
    payload = service.connection_manager.broadcast.await_args.args[0]['data']
    assert [track.get('id') for track in payload['tracks']] == [1, 2, 404, 1]
    assert payload['tracks'][2] == {'id': 404, 'filepath': '/music/missing.flac'}
