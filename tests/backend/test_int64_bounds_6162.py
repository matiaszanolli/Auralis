"""Integers above SQLite's 2**63-1 are refused at the boundary (#6162).

The SQLite binding raises OverflowError for them, which used to reach the client
as a 500 plus a logged traceback per request.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from routers.pagination import PaginationParams, offset_query
from schemas.request_bounds import MAX_SQLITE_INT, QueueIndex, TrackId


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()

    @app.get("/items")
    def items(offset: int = offset_query()) -> dict:
        return {"offset": offset}

    return TestClient(app)


def test_offset_above_int64_is_a_422(client):
    assert client.get("/items", params={"offset": 10**30}).status_code == 422
    assert client.get("/items", params={"offset": MAX_SQLITE_INT + 1}).status_code == 422


def test_offset_at_the_limit_is_accepted(client):
    resp = client.get("/items", params={"offset": PaginationParams.MAX_OFFSET})
    assert resp.status_code == 200
    assert resp.json() == {"offset": MAX_SQLITE_INT}


@pytest.mark.parametrize("alias", [TrackId, QueueIndex])
def test_body_ids_above_int64_are_rejected(alias):
    adapter = TypeAdapter(alias)
    assert adapter.validate_python(MAX_SQLITE_INT) == MAX_SQLITE_INT
    with pytest.raises(ValidationError):
        adapter.validate_python(MAX_SQLITE_INT + 1)
