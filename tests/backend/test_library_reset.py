"""
Tests for POST /api/library/reset and RepositoryFactory.reset_library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Covers: confirmation header guard, 503 when repository_factory is None,
successful reset, background-worker pause/restart (#4111), LibraryManager cache
invalidation (#3770), failure handling, and the repository-layer bulk delete
(dependency order, commit/rollback/close).

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
_library_manager_box: list = [None]


def _get_factory():
    return _factory_box[0]


def _resolve_worker(key):
    return _workers_box.get(key)


def _get_library_manager():
    return _library_manager_box[0]


_app = FastAPI()
_router = create_library_router(
    get_repository_factory=_get_factory,
    resolve_worker=_resolve_worker,
    get_library_manager=_get_library_manager,
)
_app.include_router(_router)
_client = TestClient(_app)

CONFIRM_HEADERS = {"X-Confirm-Reset": "RESET"}


@pytest.fixture(autouse=True)
def _reset_boxes():
    _factory_box[0] = None
    _workers_box.clear()
    _library_manager_box[0] = None
    yield
    _factory_box[0] = None
    _workers_box.clear()
    _library_manager_box[0] = None


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
            worker.stop = AsyncMock(side_effect=lambda k=key: order.append(f"stop:{k}"))
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

    def test_cache_invalidated_after_reset(self):
        """LibraryManager query cache is cleared after the reset (#3770)."""
        _factory_box[0] = _mock_repos()
        lm = MagicMock()
        _library_manager_box[0] = lm

        response = _client.post("/api/library/reset", headers=CONFIRM_HEADERS)

        assert response.status_code == 200
        lm.clear_cache.assert_called_once()

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
        # _workers_box empty, _library_manager_box None

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
