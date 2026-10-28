"""A failed playlist write is reported as a failure, not as success (#5940).

PlaylistRepository mutators catch every exception and return a sentinel. DELETE
playlist and DELETE track discarded it, then broadcast and answered 200; create
answered a write failure with 400 "Failed to create playlist" (the client's fault).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def api():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from routers.playlists import create_playlists_router

    repos = Mock()
    repos.playlists = Mock()
    repos.playlists.get_by_id = Mock(return_value=Mock(id=1))
    connection_manager = Mock()
    connection_manager.broadcast = AsyncMock()

    app = FastAPI()
    app.include_router(create_playlists_router(lambda: repos, connection_manager))
    return TestClient(app), repos, connection_manager


def test_delete_that_failed_to_write_is_a_500_and_broadcasts_nothing(api):
    client, repos, manager = api
    repos.playlists.delete = Mock(return_value=False)  # locked database; the playlist is still there

    response = client.delete("/api/playlists/1")

    assert response.status_code == 500
    manager.broadcast.assert_not_called()


def test_delete_that_lost_a_race_is_still_a_success(api):
    client, repos, manager = api
    repos.playlists.delete = Mock(return_value=False)
    repos.playlists.get_by_id = Mock(side_effect=[Mock(id=1), None])  # exists, then gone

    response = client.delete("/api/playlists/1")

    assert response.status_code == 200


def test_remove_track_that_failed_to_write_is_a_500_and_broadcasts_nothing(api):
    client, repos, manager = api
    repos.playlists.remove_track = Mock(return_value=False)

    response = client.delete("/api/playlists/1/tracks/9")

    assert response.status_code == 500
    manager.broadcast.assert_not_called()


def test_remove_track_success_still_broadcasts(api):
    client, repos, manager = api
    repos.playlists.remove_track = Mock(return_value=True)

    response = client.delete("/api/playlists/1/tracks/9")

    assert response.status_code == 200
    manager.broadcast.assert_called()


def test_create_that_failed_to_write_is_a_500_not_a_400(api):
    client, repos, _manager = api
    repos.playlists.create = Mock(return_value=None)

    response = client.post("/api/playlists", json={"name": "Mix"})

    assert response.status_code == 500
