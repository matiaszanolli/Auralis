"""A track id above SQLite's INTEGER range is a 404 on the similarity-family routes (#6583).

#6162 mapped the driver's ``OverflowError`` to a 404 in ``handle_query_error``, but these routes use
their own ``_with_similarity_error_handling``, which sent it to the 500 + traceback path. Real
SQLite behind the repositories: the overflow is raised by the driver binding the id, not by a mock.
"""

import logging
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from routers.fingerprint_queue import create_fingerprint_queue_router  # noqa: E402
from routers.similarity import create_similarity_router  # noqa: E402

from auralis.library.repositories.factory import RepositoryFactory  # noqa: E402

HUGE = "99999999999999999999"  # > 2**63 - 1


@pytest.fixture
def client(session_factory):
    repos = RepositoryFactory(session_factory)
    similarity = Mock()
    similarity.is_fitted.return_value = True
    app = FastAPI()
    app.include_router(create_similarity_router(lambda: similarity, lambda: None, lambda: repos))
    app.include_router(create_fingerprint_queue_router(lambda: repos))
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", f"/api/similarity/tracks/{HUGE}/similar"),
        ("get", f"/api/similarity/tracks/{HUGE}/compare/1"),
        ("get", f"/api/similarity/tracks/{HUGE}/explain/1"),
        ("post", f"/api/similarity/fingerprint-queue/enqueue/{HUGE}"),
    ],
)
def test_an_out_of_range_id_is_a_404_without_an_error_traceback(client, caplog, method, path):
    with caplog.at_level(logging.WARNING):
        response = getattr(client, method)(path)

    assert response.status_code == 404
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
