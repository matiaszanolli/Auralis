"""In-process integration coverage for the player workflow.

The original Phase 4 suite connected to ``localhost:8765`` with httpx and
websockets. That made the tests depend on a separately managed development
server and guaranteed failure in hermetic CI. These tests mount the real
library/player routers and playback-control WebSocket handlers in a FastAPI
``TestClient`` instead. Deterministic boundary fakes replace only the audio
device and database, which are outside the HTTP/WebSocket contract under test.
"""

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import player_state
import pytest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from routers import player as player_router
from routers.player import create_player_router
from routers.tracks import create_tracks_router
from ws_handlers.context import StreamState
from ws_handlers.playback_control import (
    handle_pause,
    handle_resume,
    handle_stop,
)


@dataclass
class FakeAlbum:
    title: str


@dataclass
class FakeTrack:
    id: int
    title: str
    artist: str
    album: FakeAlbum
    duration: float
    filepath: str
    format: str = "flac"
    artwork_url: str | None = None
    genre: str | None = "Test"
    year: int | None = 2026
    bitrate: int | None = 1411
    sample_rate: int | None = 44100
    bit_depth: int | None = 16
    loudness: float | None = -14.0
    date_added: str | None = None
    date_modified: str | None = None
    album_id: int | None = None
    track_number: int | None = None
    disc_number: int | None = None
    favorite: bool = False


class FakeTrackRepository:
    def __init__(self, tracks: list[FakeTrack]) -> None:
        self._tracks = tracks

    def get_all(
        self, *, limit: int, offset: int, order_by: str
    ) -> tuple[list[FakeTrack], int]:
        del order_by
        return self._tracks[offset : offset + limit], len(self._tracks)

    def search(
        self, query: str, *, limit: int, offset: int, order_by: str
    ) -> tuple[list[FakeTrack], int]:
        del order_by
        query = query.casefold()
        matches = [
            track
            for track in self._tracks
            if query in track.title.casefold() or query in track.artist.casefold()
        ]
        return matches[offset : offset + limit], len(matches)

    def get_by_id(self, track_id: int) -> FakeTrack | None:
        return next((track for track in self._tracks if track.id == track_id), None)


class InProcessConnectionManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for websocket in list(self.connections):
            await websocket.send_json(message)


class InProcessStateManager:
    def __init__(self, manager: InProcessConnectionManager) -> None:
        self.state = player_state.PlayerState()
        self.manager = manager

    def get_state(self) -> player_state.PlayerState:
        return self.state.model_copy(deep=True)

    async def update_state(self, **changes: Any) -> None:
        for key, value in changes.items():
            setattr(self.state, key, value)
        self.state.is_playing = self.state.state == player_state.PlaybackState.PLAYING
        self.state.is_paused = self.state.state == player_state.PlaybackState.PAUSED
        self.state.seq += 1
        await self.manager.broadcast(
            {"type": "player_state", "data": self.state.model_dump(mode="json")}
        )


class InProcessPlayer:
    def __init__(
        self, tracks: FakeTrackRepository, state: InProcessStateManager
    ) -> None:
        self.tracks = tracks
        self.state_manager = state
        self.queue_ids: list[int] = []
        self.current_index = 0
        self.seek_position = 0.0

    def add_to_queue(self, track_info: dict[str, Any]) -> None:
        track_id = int(track_info["id"])
        if track_id not in self.queue_ids:
            self.queue_ids.append(track_id)

    def load_track_from_library(self, track_id: int) -> bool:
        track = self.tracks.get_by_id(track_id)
        if track is None:
            return False
        self.add_to_queue({"id": track_id})
        self.current_index = self.queue_ids.index(track_id)
        info = player_state.create_track_info(track)
        self.state_manager.state.current_track = info
        self.state_manager.state.current_time = 0.0
        self.state_manager.state.duration = track.duration
        self.state_manager.state.state = player_state.PlaybackState.LOADING
        self.state_manager.state.queue = [
            info
            for queued_id in self.queue_ids
            if (
                info := player_state.create_track_info(self.tracks.get_by_id(queued_id))
            )
            is not None
        ]
        self.state_manager.state.queue_size = len(self.queue_ids)
        self.state_manager.state.queue_index = self.current_index
        self.state_manager.state.seq += 1
        return True


class InProcessPlaybackService:
    def __init__(
        self,
        player: InProcessPlayer,
        state: InProcessStateManager,
        manager: InProcessConnectionManager,
    ) -> None:
        self.player = player
        self.state_manager = state
        self.manager = manager

    async def get_status(self) -> dict[str, Any]:
        state = self.state_manager.get_state()
        payload = state.model_dump()

        def response_track(track: player_state.TrackInfo) -> dict[str, Any]:
            data = track.model_dump()
            # FastAPI validates the internal response against TrackInfo before
            # applying Field(exclude=True) to the public payload.
            data["filepath"] = track.filepath
            return data

        if state.current_track is not None:
            payload["current_track"] = response_track(state.current_track)
        payload["queue"] = [response_track(track) for track in state.queue]
        return payload

    async def seek(self, position: float) -> dict[str, Any]:
        self.player.seek_position = position
        self.state_manager.state.current_time = position
        return {"message": "Seek successful", "position": position}

    async def set_volume(self, volume: float) -> dict[str, Any]:
        volume_100 = round(volume * 100)
        self.state_manager.state.volume = volume_100
        self.state_manager.state.is_muted = volume_100 == 0
        await self.manager.broadcast(
            {"type": "volume_changed", "data": {"volume": volume_100, "seq": 1}}
        )
        return {"message": "Volume set", "volume": volume_100}


class InProcessQueueService:
    def __init__(
        self,
        player: InProcessPlayer,
        tracks: FakeTrackRepository,
        state: InProcessStateManager,
    ) -> None:
        self.player = player
        self.tracks = tracks
        self.state_manager = state

    def _track_infos(self) -> list[player_state.TrackInfo]:
        return [
            info
            for track_id in self.player.queue_ids
            if (info := player_state.create_track_info(self.tracks.get_by_id(track_id)))
            is not None
        ]

    async def get_queue_info(self) -> dict[str, Any]:
        tracks = self._track_infos()
        current = tracks[self.player.current_index] if tracks else None
        return {
            "tracks": tracks,
            "current_index": self.player.current_index,
            "track_count": len(tracks),
            "current_track": current,
            "has_next": self.player.current_index < len(tracks) - 1,
            "has_previous": self.player.current_index > 0,
            "shuffle_enabled": False,
            "repeat_mode": "off",
        }

    async def set_queue(
        self, track_ids: list[int], start_index: int = 0
    ) -> dict[str, Any]:
        valid_ids = [
            track_id for track_id in track_ids if self.tracks.get_by_id(track_id)
        ]
        if not valid_ids:
            raise ValueError("No valid tracks found")
        self.player.queue_ids = valid_ids
        self.player.current_index = min(start_index, len(valid_ids) - 1)
        infos = self._track_infos()
        self.state_manager.state.queue = infos
        self.state_manager.state.queue_size = len(infos)
        self.state_manager.state.queue_index = self.player.current_index
        self.state_manager.state.current_track = infos[self.player.current_index]
        self.state_manager.state.duration = infos[self.player.current_index].duration
        self.state_manager.state.state = player_state.PlaybackState.PLAYING
        self.state_manager.state.is_playing = True
        return {
            "message": "Queue set successfully",
            "track_count": len(infos),
            "start_index": self.player.current_index,
        }

    async def add_track_to_queue(
        self, track_id: int, position: int | None = None
    ) -> dict[str, Any]:
        if self.tracks.get_by_id(track_id) is None:
            raise ValueError(f"Track {track_id} not found")
        if position is None:
            self.player.queue_ids.append(track_id)
        else:
            position = min(position, len(self.player.queue_ids))
            self.player.queue_ids.insert(position, track_id)
        self.state_manager.state.queue = self._track_infos()
        self.state_manager.state.queue_size = len(self.player.queue_ids)
        return {
            "message": "Track added to queue",
            "track_id": track_id,
            "position": position,
            "queue_size": len(self.player.queue_ids),
        }


class InProcessNavigationService:
    def __init__(self, player: InProcessPlayer, state: InProcessStateManager) -> None:
        self.player = player
        self.state_manager = state

    def _sync_current(self) -> None:
        self.state_manager.state.queue_index = self.player.current_index
        self.state_manager.state.current_track = self.state_manager.state.queue[
            self.player.current_index
        ]

    async def next_track(self) -> dict[str, str]:
        if self.player.current_index < len(self.player.queue_ids) - 1:
            self.player.current_index += 1
            self._sync_current()
            return {"message": "Skipped to next track"}
        return {"message": "No next track available"}

    async def previous_track(self) -> dict[str, str]:
        if self.player.current_index > 0:
            self.player.current_index -= 1
            self._sync_current()
            return {"message": "Skipped to previous track"}
        return {"message": "No previous track available"}


class NoOpRecommendationService:
    async def generate_and_broadcast_recommendation(self, **kwargs: Any) -> None:
        del kwargs


class BackendClient:
    """Small JSON wrapper around FastAPI's in-process client."""

    def __init__(self, client: TestClient, player: InProcessPlayer) -> None:
        self.client = client
        self.player = player

    def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        response = self.client.get(endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    def post(
        self, endpoint: str, data: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        response = self.client.post(endpoint, json=data, **kwargs)
        response.raise_for_status()
        return response.json()


def _make_tracks() -> list[FakeTrack]:
    return [
        FakeTrack(
            id=index,
            title=f"Test Track {index}",
            artist="Integration Artist",
            album=FakeAlbum("Integration Album"),
            duration=120.0 + index,
            filepath=f"/server-only/music/track-{index}.flac",
            track_number=index,
        )
        for index in range(1, 9)
    ]


@pytest.fixture
def backend() -> BackendClient:
    tracks = FakeTrackRepository(_make_tracks())
    repositories = SimpleNamespace(tracks=tracks)
    library = SimpleNamespace(tracks=tracks)
    manager = InProcessConnectionManager()
    state = InProcessStateManager(manager)
    audio_player = InProcessPlayer(tracks, state)
    playback_service = InProcessPlaybackService(audio_player, state, manager)
    queue_service = InProcessQueueService(audio_player, tracks, state)
    navigation_service = InProcessNavigationService(audio_player, state)

    app = FastAPI()
    app.include_router(create_tracks_router(lambda: repositories))
    app.include_router(
        create_player_router(
            lambda: library,
            lambda: audio_player,
            lambda: state,
            manager,
            None,
            player_state.create_track_info,
        )
    )
    app.dependency_overrides[player_router._get_playback_service] = lambda: (
        playback_service
    )
    app.dependency_overrides[player_router._get_queue_service] = lambda: queue_service
    app.dependency_overrides[player_router._get_navigation_service] = lambda: (
        navigation_service
    )
    app.dependency_overrides[player_router._get_recommendation_service] = lambda: (
        NoOpRecommendationService()
    )

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        stream_state = StreamState({}, asyncio.Lock(), {}, {}, {})
        await manager.connect(websocket)
        await websocket.send_json(
            {"type": "player_state", "data": state.get_state().model_dump(mode="json")}
        )
        try:
            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")
                if message_type == "pause":
                    state.state.state = player_state.PlaybackState.PAUSED
                    state.state.is_playing = False
                    state.state.is_paused = True
                    await handle_pause(websocket, stream_state)
                elif message_type == "resume":
                    state.state.state = player_state.PlaybackState.PLAYING
                    state.state.is_playing = True
                    state.state.is_paused = False
                    await handle_resume(websocket, stream_state)
                elif message_type == "stop":
                    state.state.state = player_state.PlaybackState.STOPPED
                    state.state.is_playing = False
                    state.state.is_paused = False
                    state.state.current_time = 0.0
                    await handle_stop(websocket, stream_state)
                else:
                    await websocket.send_json(
                        {"type": "error", "data": {"message": "Unknown command"}}
                    )
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    with TestClient(app) as client:
        yield BackendClient(client, audio_player)


def _first_track(backend: BackendClient) -> dict[str, Any]:
    return backend.get("/api/library/tracks?limit=1&offset=0")["tracks"][0]


def _load_first_track(backend: BackendClient) -> dict[str, Any]:
    track = _first_track(backend)
    backend.post("/api/player/load", {"track_id": track["id"]})
    return track


class TestPlaybackWorkflow:
    def test_get_initial_player_status(self, backend: BackendClient) -> None:
        status = backend.get("/api/player/status")
        assert status["state"] == "stopped"
        assert status["is_playing"] is False
        assert status["current_track"] is None
        assert 0 <= status["volume"] <= 100
        assert status["queue"] == []

    def test_get_library_tracks(self, backend: BackendClient) -> None:
        response = backend.get("/api/library/tracks?limit=10&offset=0")
        assert response["total"] == 8
        assert len(response["tracks"]) == 8
        assert {"id", "title", "duration"} <= response["tracks"][0].keys()
        assert "filepath" not in response["tracks"][0]

    def test_load_track(self, backend: BackendClient) -> None:
        track = _first_track(backend)
        response = backend.post("/api/player/load", {"track_id": track["id"]})
        status = backend.get("/api/player/status")
        assert response == {
            "message": "Track loaded successfully",
            "track_id": track["id"],
        }
        assert status["current_track"]["id"] == track["id"]
        assert status["queue_size"] == 1

    def test_play_track(self, backend: BackendClient) -> None:
        _load_first_track(backend)
        with backend.client.websocket_connect("/ws") as websocket:
            assert websocket.receive_json()["type"] == "player_state"
            websocket.send_json({"type": "resume"})
            assert websocket.receive_json()["type"] == "playback_resumed"
        assert backend.get("/api/player/status")["is_playing"] is True

    def test_pause_track(self, backend: BackendClient) -> None:
        _load_first_track(backend)
        with backend.client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "resume"})
            websocket.receive_json()
            websocket.send_json({"type": "pause"})
            message = websocket.receive_json()
        assert message["type"] == "playback_paused"
        assert backend.get("/api/player/status")["is_paused"] is True

    def test_seek_position(self, backend: BackendClient) -> None:
        track = _load_first_track(backend)
        position = track["duration"] * 0.25
        response = backend.post("/api/player/seek", {"position": position})
        assert response["position"] == position
        assert backend.player.seek_position == position

    def test_volume_control(self, backend: BackendClient) -> None:
        assert backend.post("/api/player/volume", {"volume": 50})["volume"] == 50
        assert backend.post("/api/player/volume", {"volume": 0})["volume"] == 0
        assert backend.post("/api/player/volume", {"volume": 75})["volume"] == 75
        assert backend.get("/api/player/status")["volume"] == 75

    def test_full_playback_sequence(self, backend: BackendClient) -> None:
        track = _load_first_track(backend)
        with backend.client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "resume"})
            assert websocket.receive_json()["data"]["state"] == "playing"
            assert (
                backend.post("/api/player/seek", {"position": track["duration"] / 2})[
                    "position"
                ]
                == track["duration"] / 2
            )
            websocket.send_json({"type": "pause"})
            assert websocket.receive_json()["data"]["state"] == "paused"
            backend.post("/api/player/volume", {"volume": 60})
            assert websocket.receive_json()["data"]["volume"] == 60
        status = backend.get("/api/player/status")
        assert status["is_paused"] is True
        assert status["volume"] == 60

    def test_next_track(self, backend: BackendClient) -> None:
        tracks = backend.get("/api/library/tracks?limit=3&offset=0")["tracks"]
        backend.post("/api/player/queue", {"tracks": [t["id"] for t in tracks]})
        response = backend.post("/api/player/next")
        assert response["message"] == "Skipped to next track"
        assert backend.get("/api/player/status")["queue_index"] == 1

    def test_previous_track(self, backend: BackendClient) -> None:
        tracks = backend.get("/api/library/tracks?limit=3&offset=0")["tracks"]
        backend.post(
            "/api/player/queue",
            {"tracks": [t["id"] for t in tracks], "start_index": 1},
        )
        response = backend.post("/api/player/previous")
        assert response["message"] == "Skipped to previous track"
        assert backend.get("/api/player/status")["queue_index"] == 0


class TestLibrarySearchWorkflow:
    def test_search_tracks(self, backend: BackendClient) -> None:
        response = backend.get("/api/library/tracks?limit=50&offset=0")
        assert response["total"] == 8
        assert isinstance(response["tracks"], list)

    def test_search_with_query(self, backend: BackendClient) -> None:
        response = backend.get(
            "/api/library/tracks", params={"search": "track 2", "limit": 10}
        )
        assert [track["title"] for track in response["tracks"]] == ["Test Track 2"]

    def test_pagination(self, backend: BackendClient) -> None:
        page1 = backend.get("/api/library/tracks?limit=5&offset=0")
        page2 = backend.get("/api/library/tracks?limit=5&offset=5")
        assert len(page1["tracks"]) == 5
        assert len(page2["tracks"]) == 3
        assert {t["id"] for t in page1["tracks"]}.isdisjoint(
            {t["id"] for t in page2["tracks"]}
        )

    def test_select_and_play_from_search(self, backend: BackendClient) -> None:
        track = backend.get(
            "/api/library/tracks", params={"search": "track 3", "limit": 10}
        )["tracks"][0]
        backend.post("/api/player/load", {"track_id": track["id"]})
        with backend.client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "resume"})
            websocket.receive_json()
        status = backend.get("/api/player/status")
        assert status["is_playing"] is True
        assert status["current_track"]["id"] == track["id"]

    def test_add_to_queue_from_search(self, backend: BackendClient) -> None:
        tracks = backend.get("/api/library/tracks?limit=2&offset=0")["tracks"]
        backend.post("/api/player/queue", {"tracks": [tracks[0]["id"]]})
        response = backend.post(
            "/api/player/queue/add-track", {"track_id": tracks[1]["id"]}
        )
        queue = backend.get("/api/player/queue")
        assert response["queue_size"] == 2
        assert [track["id"] for track in queue["tracks"]] == [1, 2]


class TestErrorRecovery:
    def test_invalid_track_id(self, backend: BackendClient) -> None:
        response = backend.client.post("/api/player/load", json={"track_id": 999999})
        assert response.status_code == 404

    def test_seek_beyond_duration(self, backend: BackendClient) -> None:
        track = _load_first_track(backend)
        response = backend.client.post(
            "/api/player/seek", json={"position": track["duration"] * 2}
        )
        assert response.status_code == 400

    def test_seek_negative_position(self, backend: BackendClient) -> None:
        _load_first_track(backend)
        response = backend.client.post("/api/player/seek", json={"position": -10})
        assert response.status_code == 422

    def test_volume_out_of_range(self, backend: BackendClient) -> None:
        assert backend.post("/api/player/volume", {"volume": 150})["volume"] == 100
        assert backend.post("/api/player/volume", {"volume": -50})["volume"] == 0

    def test_state_consistency_after_error(self, backend: BackendClient) -> None:
        initial = backend.get("/api/player/status")
        response = backend.client.post("/api/player/load", json={"track_id": 999999})
        assert response.status_code == 404
        final = backend.get("/api/player/status")
        assert final == initial


class TestWebSocketIntegration:
    def test_ws_connection(self, backend: BackendClient) -> None:
        with backend.client.websocket_connect("/ws") as websocket:
            message = websocket.receive_json()
        assert message["type"] == "player_state"
        assert message["data"]["state"] == "stopped"

    def test_ws_playback_state_message(self, backend: BackendClient) -> None:
        _load_first_track(backend)
        with backend.client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "resume"})
            resumed = websocket.receive_json()
            websocket.send_json({"type": "stop"})
            stopped = websocket.receive_json()
        assert resumed["type"] == "playback_resumed"
        assert stopped["type"] == "playback_stopped"
        assert resumed["data"]["seq"] < stopped["data"]["seq"]
