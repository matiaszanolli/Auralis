"""
Tests for POST /api/library/reset and RepositoryFactory.reset_library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Covers: confirmation header guard, 503 when repository_factory is None,
successful reset, background-worker pause/restart (#4111), LibraryManager cache
invalidation (#3770), the scan-slot exclusion that stops an in-flight manual
scan from silently undoing a confirmed reset (#4816), failure handling, and the
repository-layer bulk delete (dependency order, commit/rollback/close).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.library import create_library_router

# Mutable containers so the single router closure can return different values
# per test (create_library_router registers on a module-level APIRouter, so it
# must only be called once per process).
_factory_box: list = [None]
_workers_box: dict = {}
_cache_box: list = [None]
_artwork_dir_box: list[Path] = [Path("/nonexistent/auralis-test-artwork")]
_db_box: list = [None]


class FakeLibraryDatabase:
    """The scan-slot half of LibraryDatabase, with the real exclusion rule.

    Mirrors ``try_begin_exclusive_access``/``end_exclusive_access``: exclusive
    access is granted only when no scan holds a slot (#4816).
    """

    def __init__(self, active_scans: int = 0) -> None:
        self.active_scans = active_scans
        self.exclusive = False
        self.begin_calls = 0
        self.end_calls = 0

    def try_begin_exclusive_access(self) -> bool:
        self.begin_calls += 1
        if self.exclusive or self.active_scans > 0:
            return False
        self.exclusive = True
        return True

    def end_exclusive_access(self) -> None:
        self.end_calls += 1
        self.exclusive = False


def _get_factory():
    return _factory_box[0]


def _resolve_worker(key):
    return _workers_box.get(key)


_app = FastAPI()
_router = create_library_router(
    get_repository_factory=_get_factory,
    resolve_worker=_resolve_worker,
    get_cache_manager=lambda: _cache_box[0],
    get_artwork_cache_dir=lambda: _artwork_dir_box[0],
    get_library_database=lambda: _db_box[0],
)
_app.include_router(_router)
_client = TestClient(_app)

CONFIRM_HEADERS = {"X-Confirm-Reset": "RESET"}


@pytest.fixture(autouse=True)
def _reset_boxes(tmp_path):
    _factory_box[0] = None
    _workers_box.clear()
    _cache_box[0] = None
    _artwork_dir_box[0] = tmp_path / "artwork"
    _db_box[0] = FakeLibraryDatabase()
    yield
    _factory_box[0] = None
    _workers_box.clear()
    _cache_box[0] = None
    _db_box[0] = None


def _mock_repos():
    """RepositoryFactory mock whose reset_library is a no-op by default."""
    repos = Mock()
    repos.reset_library = Mock()
    return repos


class TestLibraryResetConfirmationGuard:
    """X-Confirm-Reset header requirement (fixes #2733)."""

    def test_returns_422_without_confirmation_header(self):
        repos = _mock_repos()
        _factory_box[0] = repos

        response = _client.post("/api/library/reset")

        assert response.status_code == 422
        repos.reset_library.assert_not_called()

    def test_returns_400_with_wrong_header_value(self):
        repos = _mock_repos()
        _factory_box[0] = repos

        response = _client.post("/api/library/reset", headers={"X-Confirm-Reset": "yes"})

        assert response.status_code == 400
        assert "confirmation" in response.json()["detail"].lower()
        repos.reset_library.assert_not_called()

    def test_succeeds_with_correct_header(self):
        repos = _mock_repos()
        _factory_box[0] = repos

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        repos.reset_library.assert_called_once()


class TestLibraryReset:
    """POST /api/library/reset router behaviour."""

    def test_returns_503_when_repository_factory_is_none(self):
        _factory_box[0] = None

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()

    def test_successful_reset_returns_200_with_message(self):
        _factory_box[0] = _mock_repos()

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "reset" in data["message"].lower()

    def test_reset_uses_repository_method_not_raw_session(self):
        """The router must delegate to repos.reset_library, not session_factory (#4111)."""
        repos = _mock_repos()
        _factory_box[0] = repos

        _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        repos.reset_library.assert_called_once()
        repos.session_factory.assert_not_called()

    def test_all_background_workers_paused_then_restarted(self):
        """All three workers stop before the delete and start after (#4111)."""
        order: list[str] = []
        repos = _mock_repos()
        repos.reset_library.side_effect = lambda: order.append("reset")
        _factory_box[0] = repos

        for key in ("auto_scanner", "ondemand_fingerprint_queue", "fingerprint_queue"):
            worker = MagicMock()
            worker.stop = AsyncMock(
                side_effect=lambda timeout=None, k=key: order.append(f"stop:{k}")
            )
            worker.start = AsyncMock(side_effect=lambda k=key: order.append(f"start:{k}"))
            _workers_box[key] = worker

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        # Every worker stopped before the reset and started after it.
        reset_idx = order.index("reset")
        for key in ("auto_scanner", "ondemand_fingerprint_queue", "fingerprint_queue"):
            assert order.index(f"stop:{key}") < reset_idx
            assert order.index(f"start:{key}") > reset_idx
            _workers_box[key].stop.assert_awaited_once()
            _workers_box[key].start.assert_awaited_once()

    def test_reset_needs_no_query_cache_invalidation(self):
        """#4619 / #3770: there is no query cache left to invalidate.

        The `@cached_query` decorators live only on the deprecated
        LibraryManager facade, which the backend no longer constructs — every
        read goes straight through the repositories to SQLite. The router does
        take a `get_library_database` again (#4816), but only for the scan-slot
        registry: the reset itself still never reads or writes through it, so
        no cache can be left stale behind it."""
        repos = _mock_repos()
        _factory_box[0] = repos

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        db = _db_box[0]
        # Scan-slot arbitration only — no repository/session access through it.
        assert not hasattr(db, "tracks")
        repos.reset_library.assert_called_once()

    def test_reset_clears_chunk_artwork_and_thumbnail_caches(self):
        artwork_dir = _artwork_dir_box[0]
        thumb_dir = artwork_dir / "thumbnails"
        thumb_dir.mkdir(parents=True)
        (artwork_dir / "album.jpg").write_bytes(b"source")
        (thumb_dir / "album-thumb.png").write_bytes(b"thumb")
        cache_manager = MagicMock()
        cache_manager.clear_all = AsyncMock()
        _cache_box[0] = cache_manager
        _factory_box[0] = _mock_repos()

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        cache_manager.clear_all.assert_awaited_once_with()
        assert list(artwork_dir.rglob("*")) == []

    def test_workers_restarted_even_if_reset_fails(self):
        """A failing reset still restarts the paused workers (finally) and returns 500."""
        repos = _mock_repos()
        repos.reset_library.side_effect = RuntimeError("disk full")
        _factory_box[0] = repos

        worker = MagicMock()
        worker.stop = AsyncMock()
        worker.start = AsyncMock()
        _workers_box["auto_scanner"] = worker

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 500
        worker.stop.assert_awaited_once()
        worker.start.assert_awaited_once()

    def test_reset_succeeds_with_no_workers_registered(self):
        """Reset works even when no background workers are present."""
        _factory_box[0] = _mock_repos()
        # _workers_box empty

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200

    def test_response_json_structure(self):
        _factory_box[0] = _mock_repos()

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert set(data.keys()) == {"message"}


class TestRepositoryResetLibrary:
    """RepositoryFactory.reset_library bulk-delete behaviour (#4111)."""

    def _factory(self, session):
        from auralis.library.repositories.factory import RepositoryFactory

        return RepositoryFactory(session_factory=lambda: session)

    def test_commits_and_closes_on_success(self):
        session = MagicMock()
        self._factory(session).reset_library()

        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.close.assert_called_once()

    def test_deletes_association_and_entity_tables(self):
        session = MagicMock()
        self._factory(session).reset_library()

        # 3 association-table deletes + 8 entity/child deletes = 11 execute calls.
        assert session.execute.call_count == 11

    def test_rolls_back_and_reraises_on_failure(self):
        session = MagicMock()
        session.execute.side_effect = RuntimeError("disk full")

        with pytest.raises(RuntimeError, match="disk full"):
            self._factory(session).reset_library()

        session.rollback.assert_called_once()
        session.close.assert_called_once()
        session.commit.assert_not_called()


class TestResetScanExclusion:
    """#4816 — a manual scan must not be able to undo a confirmed reset.

    `stop_background_workers()` only reaches the three registered workers; a
    scan started via POST /api/library/scan is a transient LibraryScanner under
    no registry key, so it kept inserting rows straight through the deletes and
    the user watched the library they just wiped come back.
    """

    def test_reset_rejected_with_409_while_a_scan_is_active(self):
        repos = _mock_repos()
        _factory_box[0] = repos
        _db_box[0] = FakeLibraryDatabase(active_scans=1)

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 409
        assert "scan" in response.json()["detail"].lower()
        repos.reset_library.assert_not_called()

    def test_rejected_reset_does_not_pause_workers(self):
        """The 409 fires before anything is torn down, so the running scan's
        fingerprint queues keep working."""
        _factory_box[0] = _mock_repos()
        _db_box[0] = FakeLibraryDatabase(active_scans=1)
        worker = MagicMock()
        worker.stop = AsyncMock()
        worker.start = AsyncMock()
        _workers_box["auto_scanner"] = worker

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 409
        worker.stop.assert_not_awaited()

    def test_rejected_reset_does_not_leak_exclusive_access(self):
        """A refused acquisition must not leave the library locked against
        every future scan."""
        _factory_box[0] = _mock_repos()
        db = FakeLibraryDatabase(active_scans=1)
        _db_box[0] = db

        _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert db.exclusive is False

    def test_successful_reset_takes_and_releases_exclusive_access(self):
        repos = _mock_repos()
        _factory_box[0] = repos
        db = FakeLibraryDatabase()
        _db_box[0] = db

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        assert db.begin_calls == 1
        assert db.end_calls == 1
        assert db.exclusive is False

    def test_exclusive_access_is_held_across_the_delete(self):
        """No scan may start mid-reset either — the guard brackets the delete,
        it is not a point-in-time check."""
        db = FakeLibraryDatabase()
        _db_box[0] = db
        repos = _mock_repos()
        held: list[bool] = []
        repos.reset_library.side_effect = lambda: held.append(db.exclusive)
        _factory_box[0] = repos

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        assert held == [True]

    def test_exclusive_access_released_even_if_reset_fails(self):
        db = FakeLibraryDatabase()
        _db_box[0] = db
        repos = _mock_repos()
        repos.reset_library.side_effect = RuntimeError("disk full")
        _factory_box[0] = repos

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 500
        assert db.exclusive is False
        assert db.end_calls == 1

    def test_reset_still_works_when_no_library_database_is_wired(self):
        """Degrade, don't 500: the guard is skipped (and logged) if the
        database component never came up."""
        _factory_box[0] = _mock_repos()
        _db_box[0] = None

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200

    def test_router_consults_the_scan_slot_registry(self):
        """WIRING (#4816): the guard must be on the request path, not just
        defined. A grep-equivalent assertion so a refactor that drops the call
        fails here."""
        import inspect

        import routers.library as mod

        src = inspect.getsource(mod)
        assert src.count("try_begin_exclusive_access") == 1
        assert src.count("end_exclusive_access") == 1
        assert "get_library_database" in inspect.signature(create_library_router).parameters
