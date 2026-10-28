"""GET /api/albums/fingerprints answers a page of album tiles in one request (#5873).

The album grid issued one /api/albums/{id}/fingerprint per loaded album, each
hydrating the full album detail, so scrolling a large library sent thousands
of requests that competed with audio streaming.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA  # noqa: E402
from routers.albums import create_albums_router  # noqa: E402


def _fp(lufs: float) -> SimpleNamespace:
    return SimpleNamespace(**({name: 0.5 for name in DIMENSION_SCHEMA} | {"lufs": lufs}))


@pytest.fixture
def repos():
    return MagicMock()


@pytest.fixture
def client(repos):
    app = FastAPI()
    app.include_router(create_albums_router(lambda: repos))
    return TestClient(app)


def test_one_request_returns_each_fingerprinted_album_once(client, repos):
    repos.fingerprints.get_by_album_ids.return_value = {3: [_fp(-10.0), _fp(-14.0), _fp(-12.0)]}

    response = client.get("/api/albums/fingerprints", params=[("ids", 3), ("ids", 4), ("ids", 3)])

    assert response.status_code == 200
    # Deduplicated, and read through the one-join repository call.
    repos.fingerprints.get_by_album_ids.assert_called_once_with([3, 4])
    [entry] = response.json()["albums"]  # album 4 has no fingerprint: absent, not a 404
    assert entry["album_id"] == 3
    assert entry["fingerprinted_track_count"] == 3
    assert entry["fingerprint"]["lufs"] == -12.0
    repos.albums.get_by_id.assert_not_called()


def test_the_literal_route_is_not_swallowed_by_the_album_id_route(client, repos):
    repos.fingerprints.get_by_album_ids.return_value = {}

    response = client.get("/api/albums/fingerprints?ids=1")

    # Registered after /api/albums/{album_id} it would 422 on "fingerprints".
    assert response.status_code == 200
    assert response.json() == {"albums": []}


@pytest.mark.parametrize("query", ["", "?ids=" + "&ids=".join(str(i) for i in range(1, 202))])
def test_the_id_list_is_required_and_bounded(client, repos, query):
    assert client.get(f"/api/albums/fingerprints{query}").status_code == 422
    repos.fingerprints.get_by_album_ids.assert_not_called()


def test_the_single_album_route_reads_the_summary_not_the_detail(client, repos):
    repos.albums.get_summary.return_value = SimpleNamespace(title="B", track_count_expr=5)
    repos.fingerprints.get_by_album_ids.return_value = {7: [_fp(-9.0)]}

    response = client.get("/api/albums/7/fingerprint")

    assert response.status_code == 200
    assert response.json()["track_count"] == 5
    repos.albums.get_by_id.assert_not_called()
