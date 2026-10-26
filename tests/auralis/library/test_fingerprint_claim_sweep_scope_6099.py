"""
Regression tests: only the backend sweeps fingerprint claims (#6099).

``cleanup_incomplete_fingerprints`` releases EVERY claim in the table (it is
crash recovery). ``LibraryDatabase.__init__`` used to run it, so any second
process opening the same library.db (``fetch_artwork``, a script) deleted the
running backend's live claims and workers re-extracted tracks another worker
was still processing.
"""

import pytest
from sqlalchemy import select

from auralis.library import LibraryDatabase
from auralis.library.models import Track, TrackFingerprint
from auralis.library.repositories.fingerprint_shared import PLACEHOLDER_LUFS_SENTINEL


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "library.db")


def _claim_one_track(db: LibraryDatabase) -> int:
    with db.SessionLocal() as session:
        track = Track(title="in-flight", filepath="/music/in-flight.flac")
        session.add(track)
        session.commit()
        track_id = int(track.id)
    claimed = db.repositories.fingerprint_scheduler.claim_next_unfingerprinted_track()
    assert claimed is not None and claimed.id == track_id
    return track_id


def _placeholder_lufs(db: LibraryDatabase, track_id: int) -> float | None:
    with db.SessionLocal() as session:
        row = session.execute(
            select(TrackFingerprint).where(TrackFingerprint.track_id == track_id)
        ).scalars().first()
        return None if row is None else float(row.lufs)


def test_second_library_database_leaves_live_claims_intact(db_path):
    backend = LibraryDatabase(database_path=db_path)
    track_id = _claim_one_track(backend)
    assert _placeholder_lufs(backend, track_id) == PLACEHOLDER_LUFS_SENTINEL

    other_process = LibraryDatabase(database_path=db_path)
    try:
        assert _placeholder_lufs(other_process, track_id) == PLACEHOLDER_LUFS_SENTINEL
    finally:
        other_process.shutdown()
        backend.shutdown()


def test_backend_startup_sweep_still_releases_a_crashed_sessions_claims(db_path):
    crashed = LibraryDatabase(database_path=db_path)
    track_id = _claim_one_track(crashed)
    crashed.shutdown()

    restarted = LibraryDatabase(database_path=db_path)
    try:
        assert _placeholder_lufs(restarted, track_id) == PLACEHOLDER_LUFS_SENTINEL
        restarted.cleanup_incomplete_fingerprints()
        assert _placeholder_lufs(restarted, track_id) is None
    finally:
        restarted.shutdown()


def test_backend_component_init_runs_the_sweep(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[3] / "auralis-web" / "backend"))
    from config.startup import components

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    calls: list[str] = []

    class _FakeDatabase:
        database_path = str(tmp_path / "library.db")
        repositories = object()

        def cleanup_incomplete_fingerprints(self) -> None:
            calls.append("sweep")

    monkeypatch.setattr("auralis.library.LibraryDatabase", _FakeDatabase)
    state: dict = {}
    components._init_library_database(state)

    assert calls == ["sweep"]
    assert isinstance(state["library_database"], _FakeDatabase)
