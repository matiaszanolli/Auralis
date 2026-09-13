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
    by_path = {track.filepath: track for track in tracks.values()}
    repo.get_by_paths = MagicMock(
        side_effect=lambda paths: {path: by_path[path] for path in paths if path in by_path}
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
async def test_queue_changed_hydrates_a_filepath_only_queue_with_one_repository_call():
    """#5455: POST /api/player/queue hands the engine bare filepaths (no id).
    The old id-keyed hydration missed every entry and broadcast the raw
    `{'filepath': ...}` rows, leaking paths (#3205) and blanking Redux."""
    service, queue, repo = _build_service([1, 2])
    queue.set_queue(
        [
            '/music/track_1.flac',
            '/music/track_2.flac',
            '/music/missing.flac',
            '/music/track_1.flac',
        ],
        start_index=3,
    )

    await service._broadcast_queue_changed(action='reordered')

    repo.get_by_paths.assert_called_once_with(
        ['/music/track_1.flac', '/music/track_2.flac', '/music/missing.flac']
    )
    repo.get_by_id.assert_not_called()
    payload = service.connection_manager.broadcast.await_args.args[0]['data']
    assert [track['id'] for track in payload['tracks']] == [1, 2, 1]
    assert all(track['title'] for track in payload['tracks'])
    assert not any('filepath' in track for track in payload['tracks'])
    # Engine index 3 re-based past the dropped entry before it.
    assert payload['current_index'] == 2


@pytest.mark.regression
@pytest.mark.asyncio
async def test_queue_changed_reports_no_current_track_when_it_resolves_to_nothing():
    service, queue, _ = _build_service([1])
    queue.set_queue(['/music/track_1.flac', '/music/missing.flac'], start_index=1)

    await service._broadcast_queue_changed(action='removed')

    payload = service.connection_manager.broadcast.await_args.args[0]['data']
    assert [track['id'] for track in payload['tracks']] == [1]
    assert payload['current_index'] == -1


@pytest.mark.regression
@pytest.mark.asyncio
async def test_queue_changed_omits_tracks_when_hydration_fails():
    """Clients keep their last good queue rather than receiving raw rows."""
    service, queue, repo = _build_service([1])
    repo.get_by_paths.side_effect = RuntimeError("database unavailable")
    queue.set_queue(['/music/track_1.flac'], start_index=0)

    await service._broadcast_queue_changed(action='added')

    payload = service.connection_manager.broadcast.await_args.args[0]['data']
    assert 'tracks' not in payload
    assert payload['current_index'] == 0
