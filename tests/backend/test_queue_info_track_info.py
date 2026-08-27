"""Contract tests for QueueService.get_queue_info TrackInfo enrichment (#4374).

The GET /api/player/queue response is typed `tracks: list[TrackInfo]`, but the
engine queue stores only filepath dicts. get_queue_info enriches those into
full TrackInfo using the player state manager's TrackInfo queue as a filepath
map, with a batched library fallback for filepaths it does not cover.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from player_state import TrackInfo, create_track_info  # noqa: E402
from services.queue_service import QueueService  # noqa: E402


def _track_info(track_id: int) -> TrackInfo:
    return TrackInfo(
        id=track_id,
        title=f"Track {track_id}",
        artist="Artist",
        album="Album",
        duration=180.0,
        filepath=f"/music/track_{track_id}.flac",
    )


def _build_service(*, state_queue: list[TrackInfo], engine_info: dict) -> QueueService:
    audio_player = MagicMock()
    audio_player.queue.get_queue_info = MagicMock(return_value=engine_info)

    state_manager = MagicMock()
    state_manager.get_state = MagicMock(
        return_value=SimpleNamespace(queue=state_queue)
    )

    library_database = MagicMock()
    library_database.tracks = MagicMock()

    return QueueService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        library_database=library_database,
        connection_manager=MagicMock(),
        create_track_info_fn=create_track_info,
    )


@pytest.mark.asyncio
async def test_enriches_filepath_dicts_from_state_manager():
    """Engine filepath dicts become full TrackInfo via the state-manager map."""
    tracks = [_track_info(1), _track_info(2)]
    engine_info = {
        "tracks": [{"filepath": t.filepath} for t in tracks],
        "current_index": 1,
        "current_track": {"filepath": tracks[1].filepath},
        "track_count": 2,
    }
    service = _build_service(state_queue=tracks, engine_info=engine_info)

    info = await service.get_queue_info()

    assert all(isinstance(t, TrackInfo) for t in info["tracks"])
    assert [t.id for t in info["tracks"]] == [1, 2]
    assert isinstance(info["current_track"], TrackInfo)
    assert info["current_track"].id == 2
    # The library fallback must not have been needed.
    service.library_database.tracks.get_by_paths.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_library_for_uncovered_filepath():
    """A filepath absent from the state map is resolved via get_by_paths."""
    covered = _track_info(1)
    # track 2 was added via add-track after the last set_queue → not in state.
    engine_info = {
        "tracks": [{"filepath": covered.filepath}, {"filepath": "/music/track_2.flac"}],
        "current_index": 0,
        "current_track": {"filepath": covered.filepath},
        "track_count": 2,
    }
    service = _build_service(state_queue=[covered], engine_info=engine_info)
    db_track = SimpleNamespace(
        id=2, title="Track 2", filepath="/music/track_2.flac",
        artists=[SimpleNamespace(name="Artist")],
        album=SimpleNamespace(title="Album", id=9), duration=200.0,
    )
    service.library_database.tracks.get_by_paths = MagicMock(
        return_value={db_track.filepath: db_track}
    )

    info = await service.get_queue_info()

    assert [t.id for t in info["tracks"]] == [1, 2]
    assert all(isinstance(t, TrackInfo) for t in info["tracks"])
    service.library_database.tracks.get_by_paths.assert_called_once_with(
        ["/music/track_2.flac"]
    )
    service.library_database.tracks.get_by_path.assert_not_called()


@pytest.mark.asyncio
async def test_drops_unresolvable_entries_instead_of_leaking_partial_dicts():
    """A filepath in neither the state map nor the library is dropped."""
    covered = _track_info(1)
    engine_info = {
        "tracks": [{"filepath": covered.filepath}, {"filepath": "/gone.flac"}],
        "current_index": 0,
        "current_track": {"filepath": covered.filepath},
        "track_count": 2,
    }
    service = _build_service(state_queue=[covered], engine_info=engine_info)
    service.library_database.tracks.get_by_paths = MagicMock(return_value={})

    info = await service.get_queue_info()

    assert [t.id for t in info["tracks"]] == [1]
    assert all(isinstance(t, TrackInfo) for t in info["tracks"])


@pytest.mark.asyncio
async def test_batches_multiple_missing_filepaths_and_preserves_engine_order():
    covered = _track_info(1)
    second = SimpleNamespace(
        id=2, title="Track 2", filepath="/music/track_2.flac",
        artists=[SimpleNamespace(name="Artist")], album=None, duration=200.0,
    )
    fourth = SimpleNamespace(
        id=4, title="Track 4", filepath="/music/track_4.flac",
        artists=[SimpleNamespace(name="Artist")], album=None, duration=220.0,
    )
    engine_info = {
        "tracks": [
            {"filepath": second.filepath},
            {"filepath": covered.filepath},
            {"filepath": "/music/missing.flac"},
            {"filepath": fourth.filepath},
        ],
        "current_index": 1,
        "current_track": {"filepath": covered.filepath},
        "track_count": 4,
    }
    service = _build_service(state_queue=[covered], engine_info=engine_info)
    service.library_database.tracks.get_by_paths = MagicMock(
        return_value={second.filepath: second, fourth.filepath: fourth}
    )

    info = await service.get_queue_info()

    assert [track.id for track in info["tracks"]] == [2, 1, 4]
    service.library_database.tracks.get_by_paths.assert_called_once_with(
        [second.filepath, "/music/missing.flac", fourth.filepath]
    )


@pytest.mark.asyncio
async def test_empty_queue_returns_empty_list():
    engine_info = {"tracks": [], "current_index": 0, "track_count": 0}
    service = _build_service(state_queue=[], engine_info=engine_info)

    info = await service.get_queue_info()

    assert info["tracks"] == []
    assert info["current_track"] is None
