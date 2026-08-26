"""
Integration test: a repository-backed router under SQLite lock contention (#4773)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

No test anywhere in the suite exercised a genuinely locked/busy SQLite database
("database is locked" / OperationalError / SQLITE_BUSY) despite it being a
documented, recurring operational failure (CLAUDE.md's troubleshooting table).
`routers/errors.py::handle_query_error` already maps `OperationalError` to a
503 — this test drives a real lock contention scenario end-to-end to verify
that mapping actually fires, rather than trusting it by inspection.

Approach: a second, independent SQLite connection to the SAME file holds a
`BEGIN EXCLUSIVE` transaction open while a repository-backed router (the
track-favorite endpoints) attempts a write through the real connection pool —
forcing a genuine `sqlite3.OperationalError: database is locked`, not a
mocked one.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.database import LibraryDatabase  # noqa: E402
from routers.tracks import create_tracks_router  # noqa: E402


def _make_app(db: LibraryDatabase) -> FastAPI:
    app = FastAPI()
    app.include_router(create_tracks_router(get_repository_factory=lambda: db))
    return app


@pytest.fixture
def locked_db_env(tmp_path):
    """A real LibraryDatabase with one track, plus a short per-connection
    busy_timeout so a genuine lock-contention test doesn't hang for the
    production default of 60s (database.py:165) before the OperationalError
    this test asserts on ever surfaces."""
    db_path = tmp_path / "library.db"
    db = LibraryDatabase(database_path=str(db_path))

    @event.listens_for(db.engine, "checkout")
    def _short_busy_timeout(dbapi_connection, connection_record, connection_proxy):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout=200")
        cursor.close()

    track = db.tracks.add({
        "filepath": str(tmp_path / "track.wav"),
        "title": "Test Track",
    })
    assert track is not None

    yield db, str(db_path), track.id


def _hold_exclusive_lock(db_path: str) -> sqlite3.Connection:
    """Open an independent connection and hold BEGIN EXCLUSIVE — the
    strongest SQLite lock, blocking every other connection's reads and
    writes alike until released."""
    blocker = sqlite3.connect(db_path, timeout=0, isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    return blocker


def test_write_under_sqlite_lock_contention_maps_to_503(locked_db_env):
    db, db_path, track_id = locked_db_env
    client = TestClient(_make_app(db))

    blocker = _hold_exclusive_lock(db_path)
    try:
        response = client.post(f"/api/library/tracks/{track_id}/favorite")
    finally:
        blocker.rollback()
        blocker.close()

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"].lower()


def test_connection_is_returned_to_pool_after_contended_request(locked_db_env):
    """The contended request's connection must not leak or break the pool —
    a follow-up request, after the lock is released, must succeed normally."""
    db, db_path, track_id = locked_db_env
    client = TestClient(_make_app(db))

    blocker = _hold_exclusive_lock(db_path)
    try:
        first = client.post(f"/api/library/tracks/{track_id}/favorite")
    finally:
        blocker.rollback()
        blocker.close()
    assert first.status_code == 503

    second = client.post(f"/api/library/tracks/{track_id}/favorite")
    assert second.status_code == 200
    assert second.json()["favorite"] is True


def test_uncontended_write_succeeds(locked_db_env):
    """Control: without a competing lock, the same endpoint succeeds — proves
    the 503 above is specifically the lock-contention path, not some other
    fixture misconfiguration."""
    db, _db_path, track_id = locked_db_env
    client = TestClient(_make_app(db))

    response = client.post(f"/api/library/tracks/{track_id}/favorite")

    assert response.status_code == 200
    assert response.json()["favorite"] is True
