"""
Regression tests for:
  #3855 — AudioStreamController cache_manager is accepted and not silently
           replaced with a fresh SimpleChunkCache per request.
  #3856 — PlaylistRepository.add_tracks() inserts all tracks in a single
           transaction (batch), assigning correct sequential positions.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.models import Album, Artist, Base, Track
from auralis.library.models.base import track_playlist
from auralis.library.models import Playlist
from auralis.library.repositories.playlist_repository import PlaylistRepository


# ---------------------------------------------------------------------------
# Helpers — in-memory SQLite DB
# ---------------------------------------------------------------------------

def _make_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _make_playlist_repo():
    return PlaylistRepository(_make_session_factory())


def _insert_playlist_and_tracks(repo: PlaylistRepository, n_tracks: int = 5):
    """Populate the DB with 1 playlist and n tracks; return (playlist_id, track_ids)."""
    session = repo.get_session()
    try:
        playlist = Playlist(name="Test Playlist", description="")
        session.add(playlist)
        session.flush()

        tracks = []
        for i in range(n_tracks):
            t = Track(
                title=f"Track {i}",
                filepath=f"/music/track_{i}.mp3",
                duration=180.0,
            )
            session.add(t)
            tracks.append(t)
        session.flush()
        track_ids = [t.id for t in tracks]
        playlist_id = playlist.id
        session.commit()
        return playlist_id, track_ids
    finally:
        session.close()


# ---------------------------------------------------------------------------
# #3856: PlaylistRepository.add_tracks() batch insert
# ---------------------------------------------------------------------------

class TestAddTracksBatch:
    """add_tracks() must insert all tracks in one transaction with correct positions."""

    def test_add_tracks_returns_correct_count(self):
        repo = _make_playlist_repo()
        playlist_id, track_ids = _insert_playlist_and_tracks(repo, n_tracks=5)

        added = repo.add_tracks(playlist_id, track_ids)
        assert added == 5

    def test_add_tracks_assigns_sequential_positions(self):
        """Positions must be 0, 1, 2, … N-1 after a single batch call."""
        repo = _make_playlist_repo()
        playlist_id, track_ids = _insert_playlist_and_tracks(repo, n_tracks=4)

        repo.add_tracks(playlist_id, track_ids)

        session = repo.get_session()
        try:
            rows = session.execute(
                track_playlist.select()
                .where(track_playlist.c.playlist_id == playlist_id)
                .order_by(track_playlist.c.position)
            ).fetchall()
        finally:
            session.close()

        positions = [r.position for r in rows]
        assert positions == list(range(len(track_ids))), (
            f"Expected sequential positions 0..{len(track_ids)-1}, got {positions}"
        )

    def test_add_tracks_skips_duplicates_idempotently(self):
        """Re-adding tracks that are already in the playlist counts as 0 new inserts."""
        repo = _make_playlist_repo()
        playlist_id, track_ids = _insert_playlist_and_tracks(repo, n_tracks=3)

        first = repo.add_tracks(playlist_id, track_ids)
        assert first == 3

        second = repo.add_tracks(playlist_id, track_ids)
        assert second == 0, "No rows should be inserted for tracks already present"

    def test_add_tracks_empty_list_returns_zero(self):
        repo = _make_playlist_repo()
        playlist_id, _ = _insert_playlist_and_tracks(repo, n_tracks=2)
        assert repo.add_tracks(playlist_id, []) == 0

    def test_add_tracks_nonexistent_playlist_returns_zero(self):
        repo = _make_playlist_repo()
        assert repo.add_tracks(99999, [1, 2, 3]) == 0

    def test_add_tracks_appends_after_existing_rows(self):
        """add_tracks starts counting positions AFTER existing entries."""
        repo = _make_playlist_repo()
        playlist_id, track_ids = _insert_playlist_and_tracks(repo, n_tracks=4)

        # Insert first 2 individually
        repo.add_track(playlist_id, track_ids[0])  # position 0
        repo.add_track(playlist_id, track_ids[1])  # position 1

        # Batch-add the remaining 2
        added = repo.add_tracks(playlist_id, track_ids[2:])
        assert added == 2

        session = repo.get_session()
        try:
            rows = session.execute(
                track_playlist.select()
                .where(track_playlist.c.playlist_id == playlist_id)
                .order_by(track_playlist.c.position)
            ).fetchall()
        finally:
            session.close()

        positions = [r.position for r in rows]
        assert positions == [0, 1, 2, 3], (
            f"Expected positions [0,1,2,3] after mixing add_track + add_tracks, got {positions}"
        )


# ---------------------------------------------------------------------------
# #3855: AudioStreamController accepts shared cache_manager
# ---------------------------------------------------------------------------

class TestAudioStreamControllerCacheSharing:
    """AudioStreamController must store the provided cache_manager, not replace it."""

    def test_provided_cache_manager_is_stored(self):
        """When a cache_manager is passed, the controller stores it as-is."""
        from core.audio_stream_controller import AudioStreamController

        shared_cache = MagicMock()
        ctrl = AudioStreamController(
            chunked_processor_class=None,
            get_repository_factory=None,
            cache_manager=shared_cache,
        )
        assert ctrl.cache_manager is shared_cache, (
            "AudioStreamController must use the provided cache_manager, "
            "not create a fresh SimpleChunkCache (#3855)"
        )

    def test_no_cache_manager_falls_back_to_simple_cache(self):
        """Without a cache_manager, the controller falls back to SimpleChunkCache."""
        from core.audio_stream_controller import AudioStreamController, SimpleChunkCache

        ctrl = AudioStreamController(
            chunked_processor_class=None,
            get_repository_factory=None,
        )
        assert isinstance(ctrl.cache_manager, SimpleChunkCache)
