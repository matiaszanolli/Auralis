"""
Playlist Pagination Regression Tests (#4554)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``PlaylistRepository.get_all()`` used to take no arguments and unconditionally
``selectinload`` every playlist's full ``tracks`` collection, while the router
called it with no bound and reported ``total: len(playlists)``. "List playlists"
was therefore an unbounded read of the entire playlist-to-track association
table whose cost scaled in both playlist count *and* tracks-per-playlist, with
no server-side or client-side bound expressible anywhere in the chain.

These tests pin the three properties the fix has to hold:

1. ``get_all`` honours limit/offset and reports a real total.
2. ``track_count`` / ``total_duration`` come from SQL aggregates, so they stay
   correct even though the tracks collection is never loaded.
3. Serialization of a paginated playlist does not touch ``.tracks`` (which
   would raise ``DetachedInstanceError`` on the expunged instance).
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.models import Base, Playlist, Track
from auralis.library.repositories.playlist_repository import PlaylistRepository


def _make_repo() -> PlaylistRepository:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return PlaylistRepository(sessionmaker(bind=engine))


def _seed(repo: PlaylistRepository, playlist_count: int, tracks_each: int) -> None:
    """Create `playlist_count` playlists, each holding `tracks_each` tracks."""
    session = repo.get_session()
    try:
        tracks = [
            Track(title=f"T{i}", filepath=f"/music/t{i}.mp3", duration=60.0)
            for i in range(tracks_each)
        ]
        session.add_all(tracks)
        session.flush()

        for p in range(playlist_count):
            # Zero-padded so alphabetical ordering matches creation order.
            playlist = Playlist(name=f"Playlist {p:03d}")
            playlist.tracks = list(tracks)
            session.add(playlist)
        session.commit()
    finally:
        session.close()


class TestPlaylistPagination:
    """get_all() must be bounded and report a real total (#4554)."""

    def test_limit_bounds_the_page(self):
        repo = _make_repo()
        _seed(repo, playlist_count=10, tracks_each=2)

        playlists, total = repo.get_all(limit=3, offset=0)

        assert len(playlists) == 3, "limit must bound the number of rows returned"
        assert total == 10, "total must be a COUNT over the table, not the page length"

    def test_offset_walks_the_collection(self):
        repo = _make_repo()
        _seed(repo, playlist_count=10, tracks_each=1)

        first, _ = repo.get_all(limit=4, offset=0)
        second, _ = repo.get_all(limit=4, offset=4)

        assert [p.name for p in first] == [f"Playlist {i:03d}" for i in range(4)]
        assert [p.name for p in second] == [f"Playlist {i:03d}" for i in range(4, 8)]

    def test_offset_past_the_end_is_empty_but_total_stands(self):
        repo = _make_repo()
        _seed(repo, playlist_count=3, tracks_each=1)

        playlists, total = repo.get_all(limit=50, offset=100)

        assert playlists == []
        assert total == 3

    def test_empty_table(self):
        repo = _make_repo()
        playlists, total = repo.get_all()
        assert playlists == []
        assert total == 0


class TestSqlAggregates:
    """Counts must come from SQL, not from a loaded tracks collection (#4554)."""

    def test_track_count_and_duration_without_loading_tracks(self):
        repo = _make_repo()
        _seed(repo, playlist_count=2, tracks_each=5)

        playlists, _ = repo.get_all(limit=10)

        for playlist in playlists:
            assert playlist.track_count_expr == 5
            assert playlist.total_duration_expr == pytest.approx(300.0)

    def test_to_dict_uses_the_sql_aggregates(self):
        repo = _make_repo()
        _seed(repo, playlist_count=1, tracks_each=4)

        playlists, _ = repo.get_all(limit=10)
        data = playlists[0].to_dict()

        assert data["track_count"] == 4
        assert data["total_duration"] == pytest.approx(240.0)

    def test_empty_playlist_reports_zero_not_null(self):
        """SUM over zero rows is NULL in SQL — it must be coalesced to 0."""
        repo = _make_repo()
        session = repo.get_session()
        try:
            session.add(Playlist(name="Empty"))
            session.commit()
        finally:
            session.close()

        playlists, _ = repo.get_all(limit=10)
        data = playlists[0].to_dict()

        assert data["track_count"] == 0
        assert data["total_duration"] == 0

    def test_serialization_never_touches_the_tracks_collection(self):
        """The returned playlists are expunged and tracks were never loaded, so
        any read of `.tracks` would raise rather than degrade."""
        from routers.serializers import serialize_playlists

        repo = _make_repo()
        _seed(repo, playlist_count=3, tracks_each=6)

        playlists, total = repo.get_all(limit=10)
        serialized = serialize_playlists(playlists)

        assert len(serialized) == 3
        assert total == 3
        for entry in serialized:
            assert entry["track_count"] == 6
            assert entry["total_duration"] == pytest.approx(360.0)

    def test_to_dict_still_falls_back_to_tracks_when_not_paginated(self):
        """get_by_id() does not supply the aggregates — the walk must remain."""
        repo = _make_repo()
        _seed(repo, playlist_count=1, tracks_each=3)

        playlists, _ = repo.get_all(limit=1)
        playlist = repo.get_by_id(playlists[0].id)
        assert playlist is not None

        data = playlist.to_dict()
        assert data["track_count"] == 3
        assert data["total_duration"] == pytest.approx(180.0)
