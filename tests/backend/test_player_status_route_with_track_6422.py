"""
Regression tests: GET /api/player/status survives a loaded track (#6422)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``TrackInfo.filepath`` is ``Field(exclude=True)`` yet required. The service used
to hand the route ``state.model_dump()`` (no ``filepath``), and the route's
``response_model=PlayerState`` then failed re-validation with a 500 whenever
the state held a ``TrackInfo``. A no-track smoke test passed, which is why it
went unnoticed. These tests drive the real router with a real
``PlayerStateManager`` in every non-empty state.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(BACKEND))

from core.state_manager import PlayerStateManager
from player_state import TrackInfo
from routers.player import create_player_router

SECRET_PATH = "/srv/private/music/song.flac"


def _track(track_id: int = 1) -> TrackInfo:
    return TrackInfo(
        id=track_id, title="T", artist="A", album="B", duration=60.0,
        filepath=SECRET_PATH, format="flac",
    )


@pytest.fixture
def manager() -> PlayerStateManager:
    return PlayerStateManager(MagicMock())


@pytest.fixture
def client(manager: PlayerStateManager) -> TestClient:
    router = create_player_router(
        get_library_database=lambda: MagicMock(),
        get_audio_player=lambda: MagicMock(),
        get_player_state_manager=lambda: manager,
        connection_manager=MagicMock(),
        create_track_info_fn=lambda t: t,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _status(client: TestClient) -> dict:
    response = client.get("/api/player/status")
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_state_returns_200(client: TestClient) -> None:
    assert _status(client)["current_track"] is None


def test_loaded_track_returns_200_without_filepath(client: TestClient, manager: PlayerStateManager) -> None:
    manager.state.current_track = _track()
    body = _status(client)
    assert body["current_track"]["id"] == 1
    assert "filepath" not in body["current_track"]
    assert SECRET_PATH not in client.get("/api/player/status").text


def test_queue_only_state_returns_200(client: TestClient, manager: PlayerStateManager) -> None:
    manager.state.queue = [_track(1), _track(2)]
    manager.state.queue_size = 2
    body = _status(client)
    assert [t["id"] for t in body["queue"]] == [1, 2]
    assert all("filepath" not in t for t in body["queue"])


def test_openapi_does_not_require_filepath(client: TestClient) -> None:
    schemas = client.app.openapi()["components"]["schemas"]
    assert "filepath" not in schemas["TrackInfo"].get("required", [])
