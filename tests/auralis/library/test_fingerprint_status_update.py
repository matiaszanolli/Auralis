"""
FingerprintStatsRepository.update_status — real-DB behaviour (#4108)

update_status used a raw text() UPDATE against track_fingerprints, a table that
has none of the fingerprint_status / fingerprint_computed_at columns — those
live on the tracks table (Track model). The UPDATE therefore failed and the
method silently never updated anything. It is now an ORM update() against Track,
and the facade FingerprintRepository delegates to it.

These tests run against a real SQLite DB to prove the status is actually written.
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auralis.library.models import Base, Track
from auralis.library.repositories.fingerprint_repository import FingerprintRepository


@pytest.fixture
def repo_and_factory():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    seed = SessionLocal()
    seed.add(Track(id=1, title="Song", filepath="/music/song.mp3"))
    seed.commit()
    seed.close()

    repo = FingerprintRepository(SessionLocal)
    try:
        yield repo, SessionLocal
    finally:
        engine.dispose()
        os.unlink(path)


def test_completed_writes_status_and_timestamp_to_tracks(repo_and_factory):
    repo, SessionLocal = repo_and_factory
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()

    assert repo.update_status(1, "completed", ts) is True

    s = SessionLocal()
    track = s.get(Track, 1)
    assert track.fingerprint_status == "completed"
    assert track.fingerprint_computed_at is not None  # ISO string -> DateTime
    s.close()


def test_failed_writes_status_to_tracks(repo_and_factory):
    repo, SessionLocal = repo_and_factory

    assert repo.update_status(1, "failed") is True

    s = SessionLocal()
    track = s.get(Track, 1)
    assert track.fingerprint_status == "failed"
    s.close()


def test_facade_delegates_update_status(repo_and_factory):
    """The facade (what production/extractor holds) must expose update_status."""
    repo, _ = repo_and_factory
    assert callable(repo.update_status)
    assert callable(repo.get_fingerprint_stats)
