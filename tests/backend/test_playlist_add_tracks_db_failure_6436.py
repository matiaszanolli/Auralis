"""
A failed database write in add_tracks is an error, not "Added 0 track(s)" (#6436)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``PlaylistRepository.add_tracks`` was the one playlist mutator still inside ``_guarded``,
whose ``__exit__`` swallows every Exception and falls through to ``return 0``. The router
documents 0 as "all-duplicate" and answered 200 ``added_count: 0``, so SQLite contention, an
IntegrityError at commit or a vanished FK looked like the idempotent no-op: a success toast
and nothing written. 0 now means only a missing playlist or nothing new to add (#5264 did the
same for add_track/update/reorder/clear).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.models import Base, Playlist, Track  # noqa: E402
from auralis.library.repositories.playlist_repository import PlaylistRepository  # noqa: E402
from routers.playlists import add_tracks_to_playlist  # noqa: E402
from routers.playlists_models import AddTracksRequest  # noqa: E402


def _repo_with_playlist_and_tracks(n_tracks: int = 2):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    repo = PlaylistRepository(sessionmaker(bind=engine))
    session = repo.get_session()
    try:
        playlist = Playlist(name="P", description="")
        session.add(playlist)
        tracks = [Track(title=f"T{i}", filepath=f"/m/{i}.mp3", duration=1.0) for i in range(n_tracks)]
        session.add_all(tracks)
        session.commit()
        return repo, playlist.id, [t.id for t in tracks]
    finally:
        session.close()


def test_a_commit_failure_propagates_instead_of_returning_zero():
    repo, playlist_id, track_ids = _repo_with_playlist_and_tracks()
    boom = OperationalError("COMMIT", {}, Exception("database is locked"))

    with patch("sqlalchemy.orm.Session.commit", side_effect=boom):
        with pytest.raises(OperationalError, match="database is locked"):
            repo.add_tracks(playlist_id, track_ids)

    # Rolled back by the scope: nothing was written.
    assert repo.add_tracks(playlist_id, track_ids) == len(track_ids)


def test_zero_still_means_missing_playlist_or_all_duplicate():
    repo, playlist_id, track_ids = _repo_with_playlist_and_tracks()

    assert repo.add_tracks(9999, track_ids) == 0  # missing playlist
    assert repo.add_tracks(playlist_id, track_ids) == len(track_ids)
    assert repo.add_tracks(playlist_id, track_ids) == 0  # all duplicates
    assert repo.add_tracks(playlist_id, []) == 0


@pytest.mark.asyncio
async def test_the_route_fails_and_does_not_broadcast_when_the_repository_raises():
    repos = MagicMock()
    repos.playlists.get_by_id.return_value = MagicMock()
    repos.playlists.add_tracks.side_effect = OperationalError("COMMIT", {}, Exception("database is locked"))
    manager = MagicMock()
    manager.broadcast = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await add_tracks_to_playlist(5, AddTracksRequest(track_ids=[1]), repos=repos, connection_manager=manager)

    assert exc.value.status_code >= 500
    manager.broadcast.assert_not_awaited()
