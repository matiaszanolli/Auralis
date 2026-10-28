"""HTTP coverage for the four routes no test called (#6000).

POST /api/playlists/{id}/tracks/add and PUT .../tracks/reorder (#4658), POST
/api/player/queue/add-tracks (#5651) and DELETE /api/cache/track/{id} were covered only by
registration assertions, so their status mapping and effect were never run. The playlist routes
run against a real SQLite library; the queue route against a stub service so the ValueError ->
status mapping is exercised.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library import LibraryDatabase  # noqa: E402
from services.errors import InvalidRequest, ResourceNotFound  # noqa: E402


@pytest.fixture
def client(client):
    """The shared client with a trusted Origin on state-changing calls (OriginCheckMiddleware)."""
    for method in ("put", "post", "delete", "patch"):
        original = getattr(client, method)

        def _with_origin(url, *, _original=original, **kwargs):
            headers = dict(kwargs.pop("headers", {}) or {})
            headers.setdefault("origin", "http://localhost:8765")
            return _original(url, headers=headers, **kwargs)

        setattr(client, method, _with_origin)
    return client


@pytest.fixture
def library(tmp_path):
    """A real library with one playlist holding tracks A, B, C in that order."""
    db = LibraryDatabase(database_path=str(tmp_path / "library.db"))
    track_ids = []
    for name in ("A", "B", "C", "D"):
        path = tmp_path / f"{name}.wav"
        sf.write(str(path), np.zeros((4410, 2), dtype="float32"), 44100)
        track = db.tracks.add({"filepath": str(path), "title": name, "artists": ["X"], "album": "Al"})
        track_ids.append(track.id)
    playlist = db.playlists.create("List")
    for track_id in track_ids[:3]:
        db.playlists.add_track(playlist.id, track_id)
    yield db, playlist.id, track_ids


def _titles(db, playlist_id):
    return [track.title for track in db.playlists.get_by_id(playlist_id).tracks]


class TestPlaylistAddAtPosition:
    def test_inserts_at_the_requested_position(self, client, library):
        db, playlist_id, ids = library

        with patch.dict("main.globals_dict", {"repository_factory": db.repositories}):
            response = client.post(
                f"/api/playlists/{playlist_id}/tracks/add", json={"track_id": ids[3], "position": 1}
            )

        assert response.status_code == 200
        assert _titles(db, playlist_id) == ["A", "D", "B", "C"]

    def test_re_adding_a_member_moves_it_instead_of_duplicating_it(self, client, library):
        db, playlist_id, ids = library

        with patch.dict("main.globals_dict", {"repository_factory": db.repositories}):
            response = client.post(
                f"/api/playlists/{playlist_id}/tracks/add", json={"track_id": ids[0], "position": 2}
            )

        assert response.status_code == 200
        assert _titles(db, playlist_id) == ["B", "C", "A"]

    def test_an_unknown_track_is_a_400_and_changes_nothing(self, client, library):
        db, playlist_id, _ = library

        with patch.dict("main.globals_dict", {"repository_factory": db.repositories}):
            response = client.post(f"/api/playlists/{playlist_id}/tracks/add", json={"track_id": 999_999})

        assert response.status_code == 400
        assert _titles(db, playlist_id) == ["A", "B", "C"]


class TestPlaylistReorder:
    def test_moves_a_track_rather_than_duplicating_it(self, client, library):
        db, playlist_id, _ = library

        with patch.dict("main.globals_dict", {"repository_factory": db.repositories}):
            response = client.put(
                f"/api/playlists/{playlist_id}/tracks/reorder", json={"from_index": 0, "to_index": 2}
            )

        assert response.status_code == 200
        assert _titles(db, playlist_id) == ["B", "C", "A"]

    def test_an_index_past_the_end_is_a_400_and_changes_nothing(self, client, library):
        db, playlist_id, _ = library

        with patch.dict("main.globals_dict", {"repository_factory": db.repositories}):
            response = client.put(
                f"/api/playlists/{playlist_id}/tracks/reorder", json={"from_index": 0, "to_index": 9}
            )

        assert response.status_code == 400
        assert _titles(db, playlist_id) == ["A", "B", "C"]


ADDED = {"message": "Added 3 tracks", "added_count": 3, "requested_count": 3, "queue_size": 8}


class TestQueueAddTracks:
    @staticmethod
    def _use_service(client, service):
        from routers.player_deps import _get_queue_service

        client.app.dependency_overrides[_get_queue_service] = lambda: service

    def test_hands_the_ids_to_the_service_in_order(self, client):
        service = Mock()
        service.add_tracks_to_queue = AsyncMock(return_value=ADDED)
        self._use_service(client, service)
        try:
            response = client.post("/api/player/queue/add-tracks", json={"track_ids": [5, 2, 9]})
        finally:
            client.app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == ADDED
        service.add_tracks_to_queue.assert_awaited_once_with([5, 2, 9])

    @pytest.mark.parametrize("error,status", [(ResourceNotFound("track 5"), 404), (InvalidRequest("bad"), 400)])
    def test_service_errors_map_to_their_status(self, client, error, status):
        service = Mock()
        service.add_tracks_to_queue = AsyncMock(side_effect=error)
        self._use_service(client, service)
        try:
            response = client.post("/api/player/queue/add-tracks", json={"track_ids": [5]})
        finally:
            client.app.dependency_overrides.clear()

        assert response.status_code == status


class TestClearTrackCache:
    def test_clears_the_one_track_and_reports_what_was_removed(self, client):
        from routers.cache_streamlined import _get_cache_manager

        cache = Mock()
        cache.clear_track = AsyncMock(return_value=3)
        client.app.dependency_overrides[_get_cache_manager] = lambda: cache
        try:
            response = client.delete("/api/cache/track/7")
        finally:
            client.app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == {"message": "Cleared cache for track 7", "removed": 3}
        cache.clear_track.assert_awaited_once_with(7)
