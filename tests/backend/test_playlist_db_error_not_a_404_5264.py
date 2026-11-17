"""
A database failure in a playlist write is a 5xx, not a "not found" (#5264)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The routes read a repository's ``False`` as "no such playlist / out of range" and answer 404/400. That
was only safe if ``False`` can mean nothing else. The repositories used to return it from a blanket
``except Exception`` too, so lock contention read as a permanent client error. They no longer
swallow: ``_session_scope`` rolls back and re-raises, ``False`` is reserved for the genuine miss.
These run the REAL repositories against a real database and inject a failure at commit.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.playlists import create_playlists_router

from auralis.library.database import LibraryDatabase
from auralis.library.models import Track


@pytest.fixture
def api(tmp_path):
    db = LibraryDatabase(database_path=str(tmp_path / "library.db"))
    repos = db.repositories
    manager = Mock()
    manager.broadcast = AsyncMock()
    app = FastAPI()
    app.include_router(create_playlists_router(lambda: repos, manager))
    playlist = repos.playlists.create("Mix")
    session = db.get_session()
    try:
        tracks = [Track(title=f"T{i}", filepath=f"/m/{i}.flac", filepath_key=f"/m/{i}.flac") for i in range(3)]
        session.add_all(tracks)
        session.commit()
        track_ids = [t.id for t in tracks]
    finally:
        session.close()
    for track_id in track_ids[:2]:  # the third stays free for the add_track case
        repos.playlists.add_track(playlist.id, track_id)
    yield TestClient(app, raise_server_exceptions=False), playlist.id, track_ids
    db.engine.dispose()


def _locked(*_args, **_kwargs):
    raise OperationalError("COMMIT", {}, Exception("database is locked"))


ROUTES = [
    ("put", "/api/playlists/{pid}", {"name": "Renamed"}),
    ("post", "/api/playlists/{pid}/tracks/add", {"track_id": "{t0}"}),
    ("put", "/api/playlists/{pid}/tracks/reorder", {"from_index": 0, "to_index": 1}),
    ("delete", "/api/playlists/{pid}/tracks", None),
]


def _call(client, method, path, body, pid, track_ids):
    path = path.format(pid=pid)
    kwargs = {}
    if body is not None:
        kwargs["json"] = {k: (track_ids[2] if v == "{t0}" else v) for k, v in body.items()}
    return getattr(client, method)(path, **kwargs)


@pytest.mark.parametrize("method,path,body", ROUTES, ids=["update", "add_track", "reorder", "clear"])
def test_a_commit_failure_is_a_500_not_a_404_or_400(api, method, path, body):
    client, pid, track_ids = api
    with patch.object(Session, "commit", _locked):
        response = _call(client, method, path, body, pid, track_ids)

    assert response.status_code >= 500, (response.status_code, response.text)


def test_genuinely_missing_playlists_keep_their_not_found_answers(api):
    client, _pid, track_ids = api
    missing = 99999

    assert _call(client, "put", "/api/playlists/{pid}", {"name": "x"}, missing, track_ids).status_code == 404
    assert _call(client, "delete", "/api/playlists/{pid}/tracks", None, missing, track_ids).status_code == 404


def test_an_out_of_range_reorder_is_still_a_400(api):
    client, pid, track_ids = api

    response = _call(client, "put", "/api/playlists/{pid}/tracks/reorder", {"from_index": 0, "to_index": 50}, pid, track_ids)

    assert response.status_code == 400
