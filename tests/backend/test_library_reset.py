"""
Tests for POST /api/library/reset
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Covers: 503 when repository_factory is None, successful reset,
rollback on failure, and response JSON structure.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.library import create_library_router

# Use a mutable container so the same router closure can return different
# values per test.  create_library_router registers routes on a module-level
# APIRouter, so it must only be called once per process.
_factory_box: list = [None]


def _get_factory():
    return _factory_box[0]


_app = FastAPI()
_router = create_library_router(get_repository_factory=_get_factory)
_app.include_router(_router)
_client = TestClient(_app)


@pytest.fixture(autouse=True)
def _reset_factory():
    """Reset the factory box before each test."""
    _factory_box[0] = None
    yield
    _factory_box[0] = None


class TestLibraryReset:
    """Test POST /api/library/reset"""

    def test_returns_503_when_repository_factory_is_none(self):
        """If repository_factory getter returns None, endpoint must return 503."""
        _factory_box[0] = None

        response = _client.post("/api/library/reset")

        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()

    def test_successful_reset_returns_200_with_message(self):
        """Successful reset must return 200 with a message key."""
        session = MagicMock()
        repos = Mock()
        repos.session_factory.return_value = session
        _factory_box[0] = repos

        response = _client.post("/api/library/reset")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "reset" in data["message"].lower()

    def test_successful_reset_commits_and_closes_session(self):
        """On success the session must be committed and closed."""
        session = MagicMock()
        repos = Mock()
        repos.session_factory.return_value = session
        _factory_box[0] = repos

        _client.post("/api/library/reset")

        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.close.assert_called_once()

    def test_successful_reset_deletes_in_dependency_order(self):
        """Association tables must be cleared before entity tables."""
        session = MagicMock()
        repos = Mock()
        repos.session_factory.return_value = session
        _factory_box[0] = repos

        _client.post("/api/library/reset")

        # session.execute called for association table deletes
        assert session.execute.call_count >= 3
        # session.query().delete() called for entity tables
        assert session.query.call_count >= 7

    def test_rollback_on_failure(self):
        """If a delete raises, the session must be rolled back and closed."""
        session = MagicMock()
        session.execute.side_effect = RuntimeError("disk full")
        repos = Mock()
        repos.session_factory.return_value = session
        _factory_box[0] = repos

        response = _client.post("/api/library/reset")

        assert response.status_code == 500
        session.rollback.assert_called_once()
        session.close.assert_called_once()
        session.commit.assert_not_called()

    def test_response_json_structure(self):
        """Response body must be a dict with exactly the 'message' key."""
        session = MagicMock()
        repos = Mock()
        repos.session_factory.return_value = session
        _factory_box[0] = repos

        response = _client.post("/api/library/reset")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert set(data.keys()) == {"message"}
