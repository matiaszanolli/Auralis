"""
Regression tests for TrackRepository.update_metadata_batch() (#3857 / BE-PF-8)

Verifies that batch_update_metadata endpoint uses a single WHERE-IN prefetch
(get_by_ids) and a single transaction (update_metadata_batch) instead of N
individual DB round-trips.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.models import Base, Track
from auralis.library.repositories.track_repository import TrackRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo() -> TrackRepository:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return TrackRepository(sessionmaker(bind=engine))


def _insert_tracks(repo: TrackRepository, n: int) -> list[int]:
    session = repo.get_session()
    try:
        tracks = [
            Track(title=f"Track {i}", filepath=f"/music/track_{i}.mp3", duration=180.0)
            for i in range(n)
        ]
        session.add_all(tracks)
        session.flush()
        ids = [t.id for t in tracks]
        session.commit()
        return ids
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Tests: update_metadata_batch
# ---------------------------------------------------------------------------

class TestUpdateMetadataBatch:
    """update_metadata_batch() must update all tracks in one transaction."""

    def test_batch_updates_all_tracks(self):
        """All tracks in the batch receive the new field values."""
        repo = _make_repo()
        ids = _insert_tracks(repo, 3)

        updates = [(ids[0], {"title": "New Title A"}),
                   (ids[1], {"title": "New Title B"}),
                   (ids[2], {"title": "New Title C"})]
        updated_ids = repo.update_metadata_batch(updates)

        assert set(updated_ids) == set(ids)

        session = repo.get_session()
        try:
            for i, tid in enumerate(ids):
                track = session.execute(
                    select(Track).where(Track.id == tid)
                ).scalars().first()
                assert track.title == f"New Title {chr(65 + i)}"
        finally:
            session.close()

    def test_batch_returns_only_found_ids(self):
        """Tracks not in the DB are silently skipped and not returned."""
        repo = _make_repo()
        ids = _insert_tracks(repo, 2)

        updates = [(ids[0], {"title": "A"}),
                   (99999, {"title": "Ghost"})]  # nonexistent
        result = repo.update_metadata_batch(updates)

        assert result == [ids[0]]

    def test_batch_empty_list_returns_empty(self):
        repo = _make_repo()
        assert repo.update_metadata_batch([]) == []

    def test_batch_skips_none_values(self):
        """Fields with None values are not applied (same as update_metadata)."""
        repo = _make_repo()
        (tid,) = _insert_tracks(repo, 1)

        original_title = "Original"
        repo.update_metadata_batch([(tid, {"title": original_title})])
        repo.update_metadata_batch([(tid, {"title": None})])  # should not overwrite

        session = repo.get_session()
        try:
            track = session.execute(
                select(Track).where(Track.id == tid)
            ).scalars().first()
            assert track.title == original_title
        finally:
            session.close()

    def test_batch_all_applied_in_one_commit(self, monkeypatch):
        """session.commit() is called exactly once regardless of batch size."""
        repo = _make_repo()
        ids = _insert_tracks(repo, 5)

        commit_calls = []
        original_get_session = repo.get_session

        class _TrackingSession:
            def __init__(self, real_session):
                self._s = real_session

            def __getattr__(self, name):
                if name == "commit":
                    def _commit():
                        commit_calls.append(1)
                        return self._s.commit()
                    return _commit
                return getattr(self._s, name)

        monkeypatch.setattr(
            repo, "get_session",
            lambda: _TrackingSession(original_get_session())
        )

        updates = [(tid, {"title": f"T{i}"}) for i, tid in enumerate(ids)]
        repo.update_metadata_batch(updates)

        assert len(commit_calls) == 1, (
            f"update_metadata_batch must commit once, got {len(commit_calls)} commits"
        )
