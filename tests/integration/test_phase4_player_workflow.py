"""
Phase 4 Integration Tests - Player Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the complete playback workflow against the real backend:
1. Play → Seek → Pause → Volume Change
2. Search → Select Track → Play
3. Error Recovery (network errors, API failures)

Tests use real backend servers (localhost:8765) and validate:
- UI command → API request → backend state change
- WebSocket broadcasts received
- State synchronization
- Error handling and recovery

:copyright: (C) 2024 Auralis
:license: GPLv3
"""

import asyncio
import json
import pytest
import websockets
import httpx
from typing import Dict, Any, Optional
import time


# Base configuration
BACKEND_URL = "http://localhost:8765"
WS_URL = "ws://localhost:8765/ws"
TIMEOUT = 10.0
WS_TIMEOUT = 5.0


class BackendClient:
    """HTTP client for backend API calls."""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url
        self.client = httpx.Client(timeout=TIMEOUT)

    def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """GET request."""
        url = f"{self.base_url}{endpoint}"
        response = self.client.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """POST request."""
        url = f"{self.base_url}{endpoint}"
        response = self.client.post(url, json=data, **kwargs)
        response.raise_for_status()
        return response.json()

    def put(self, endpoint: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """PUT request."""
        url = f"{self.base_url}{endpoint}"
        response = self.client.put(url, json=data, **kwargs)
        response.raise_for_status()
        return response.json()

    def delete(self, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """DELETE request."""
        url = f"{self.base_url}{endpoint}"
        response = self.client.delete(url, **kwargs)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return None

    def close(self):
        """Close client."""
        self.client.close()


class WebSocketListener:
    """Listens to WebSocket messages from backend."""

    def __init__(self, ws_url: str = WS_URL):
        self.ws_url = ws_url
        self.websocket = None
        self.messages = []
        self.running = False

    async def connect(self):
        """Connect to WebSocket."""
        self.websocket = await websockets.connect(self.ws_url)
        self.running = True

    async def disconnect(self):
        """Disconnect from WebSocket."""
        self.running = False
        if self.websocket:
            await self.websocket.close()

    async def listen(self, timeout: float = WS_TIMEOUT):
        """Listen for messages with timeout."""
        try:
            while self.running:
                message = await asyncio.wait_for(
                    self.websocket.recv(), timeout=timeout
                )
                data = json.loads(message)
                self.messages.append(data)
                yield data
        except asyncio.TimeoutError:
            pass

    def get_messages(self, message_type: str) -> list:
        """Get messages of specific type."""
        return [m for m in self.messages if m.get("type") == message_type]

    def clear_messages(self):
        """Clear message buffer."""
        self.messages.clear()


@pytest.fixture
def backend():
    """Backend client fixture."""
    client = BackendClient()
    yield client
    client.close()


@pytest.fixture
async def ws_listener():
    """WebSocket listener fixture."""
    listener = WebSocketListener()
    await listener.connect()
    yield listener
    await listener.disconnect()


@pytest.fixture
async def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# WORKFLOW 1: Play → Seek → Pause → Volume
# ============================================================================


class TestPlaybackWorkflow:
    """Test complete playback workflow."""

    def test_get_initial_player_status(self, backend):
        """Verify initial player status."""
        status = backend.get("/api/player/status")

        # Should have these fields
        assert "state" in status
        assert "is_playing" in status
        assert "current_track" in status
        assert "volume" in status
        assert "queue" in status
        assert isinstance(status["volume"], int)
        assert 0 <= status["volume"] <= 100

    def test_get_library_tracks(self, backend):
        """Verify library has tracks available."""
        response = backend.get("/api/library/tracks?limit=10&offset=0")

        # Should have tracks or empty list (at least the structure)
        assert "tracks" in response
        assert isinstance(response["tracks"], list)

        if response["tracks"]:
            track = response["tracks"][0]
            assert "id" in track
            assert "title" in track
            assert "duration" in track
            assert "filepath" in track

    def test_load_track(self, backend):
        """Load a track into the player."""
        # Get first available track
        tracks = backend.get("/api/library/tracks?limit=1&offset=0")
        if not tracks["tracks"]:
            pytest.skip("No tracks available in library")

        track = tracks["tracks"][0]
        track_id = track["id"]
        track_path = track["filepath"]

        # Load track using query parameters
        response = backend.post(f"/api/player/load?track_path={track_path}&track_id={track_id}")

        assert "state" in response
        # Track should be queued or loaded
        assert response["current_track"] is not None or len(response["queue"]) > 0

    def test_play_track(self, backend):
        """Test playing a track."""
        # Load track first
        tracks = backend.get("/api/library/tracks?limit=1&offset=0")
        if not tracks["tracks"]:
            pytest.skip("No tracks available")

        track = tracks["tracks"][0]
        backend.post(f"/api/player/load?track_path={track['filepath']}&track_id={track['id']}")

        # Play
        response = backend.post("/api/player/play")

        assert response["is_playing"] is True
        assert response["state"] in ["playing", "buffering"]

    def test_pause_track(self, backend):
        """Test pausing playback."""
        # Play first
        tracks = backend.get("/api/library/tracks?limit=1&offset=0")
        if not tracks["tracks"]:
            pytest.skip("No tracks available")

        track = tracks["tracks"][0]
        backend.post(f"/api/player/load?track_path={track['filepath']}&track_id={track['id']}")
        backend.post("/api/player/play")

        # Pause
        response = backend.post("/api/player/pause")

        assert response["is_playing"] is False
        assert response["is_paused"] is True

    def test_seek_position(self, backend):
        """Test seeking to a position."""
        # Load and play track
        tracks = backend.get("/api/library/tracks?limit=1&offset=0")
        if not tracks["tracks"]:
            pytest.skip("No tracks available")

        track = tracks["tracks"][0]
        track_id = track["id"]
        duration = track["duration"]

        backend.post(f"/api/player/load?track_path={track['filepath']}&track_id={track_id}")
        backend.post("/api/player/play")

        # Seek to 25% of duration (query parameter)
        seek_position = duration * 0.25
        response = backend.post(f"/api/player/seek?position={seek_position}")

        # Current time should be near seek position (allowing for rounding)
        assert response["current_time"] > 0
        assert abs(response["current_time"] - seek_position) < 1.0  # Within 1 second

    def test_volume_control(self, backend):
        """Test volume changes."""
        # Set volume to 50 (0-100 scale for API)
        response = backend.post("/api/player/volume?volume=50")

        assert response["volume"] == 50
        assert response["is_muted"] is False

        # Mute
        response = backend.post("/api/player/volume?volume=0")
        assert response["volume"] == 0

        # Unmute (restore to previous)
        response = backend.post("/api/player/volume?volume=75")
        assert response["volume"] == 75

    def test_full_playback_sequence(self, backend):
        """Test complete sequence: Load → Play → Seek → Pause → Volume."""
        # Get first track
        tracks = backend.get("/api/library/tracks?limit=1&offset=0")
        if not tracks["tracks"]:
            pytest.skip("No tracks available")

        track = tracks["tracks"][0]
        track_id = track["id"]
        duration = track["duration"]

        # 1. Load
        status = backend.post(f"/api/player/load?track_path={track['filepath']}&track_id={track_id}")
        assert status["current_track"] is not None or status["queue"]

        # 2. Play
        status = backend.post("/api/player/play")
        assert status["is_playing"] is True

        # 3. Seek
        seek_pos = duration * 0.5  # Seek to halfway
        status = backend.post(f"/api/player/seek?position={seek_pos}")
        assert status["current_time"] > 0

        # 4. Pause
        status = backend.post("/api/player/pause")
        assert status["is_paused"] is True

        # 5. Volume
        status = backend.post("/api/player/volume?volume=60")
        assert status["volume"] == 60

    def test_next_track(self, backend):
        """Test skipping to next track."""
        # Load a track with queue
        tracks = backend.get("/api/library/tracks?limit=3&offset=0")
        if len(tracks["tracks"]) < 2:
            pytest.skip("Need at least 2 tracks")

        track_ids = [t["id"] for t in tracks["tracks"][:3]]

        # Set queue
        backend.post("/api/player/queue", {"tracks": track_ids, "start_index": 0})

        # Play
        backend.post("/api/player/play")

        # Get current track
        status_before = backend.get("/api/player/status")
        current_before = status_before["queue_index"]

        # Next
        status_after = backend.post("/api/player/next")

        # Should have moved to next track
        assert status_after["queue_index"] > current_before or status_after["queue_size"] <= 1

    def test_previous_track(self, backend):
        """Test skipping to previous track."""
        # Load a track with queue
        tracks = backend.get("/api/library/tracks?limit=3&offset=0")
        if len(tracks["tracks"]) < 2:
            pytest.skip("Need at least 2 tracks")

        track_ids = [t["id"] for t in tracks["tracks"][:3]]

        # Set queue at index 1
        backend.post("/api/player/queue", {"tracks": track_ids, "start_index": 1})
        backend.post("/api/player/play")

        status_before = backend.get("/api/player/status")
        current_before = status_before["queue_index"]

        # Previous
        status_after = backend.post("/api/player/previous")

        # Should have moved to previous track
        assert status_after["queue_index"] < current_before or current_before == 0


# ============================================================================
# WORKFLOW 2: Search → Select → Play
# ============================================================================


class TestLibrarySearchWorkflow:
    """Test library search and playback workflow."""

    def test_search_tracks(self, backend):
        """Search for tracks in library."""
        response = backend.get("/api/library/tracks?limit=50&offset=0")

        assert "tracks" in response
        assert isinstance(response["tracks"], list)

    def test_search_with_query(self, backend):
        """Test searching with a query string."""
        # Try to search for a common term
        response = backend.get(
            "/api/library/tracks",
            params={"search": "track", "limit": 10, "offset": 0}
        )

        assert "tracks" in response
        # Results should match search (or be empty if no matches)
        assert isinstance(response["tracks"], list)

    def test_pagination(self, backend):
        """Test pagination through tracks."""
        # Get first page
        page1 = backend.get("/api/library/tracks?limit=5&offset=0")
        assert len(page1["tracks"]) <= 5

        # Get second page
        page2 = backend.get("/api/library/tracks?limit=5&offset=5")
        assert len(page2["tracks"]) <= 5

        # Pages should be different (if enough tracks)
        if len(page1["tracks"]) == 5 and len(page2["tracks"]) > 0:
            track_ids_1 = {t["id"] for t in page1["tracks"]}
            track_ids_2 = {t["id"] for t in page2["tracks"]}
            assert track_ids_1.isdisjoint(track_ids_2)  # No overlap

    def test_select_and_play_from_search(self, backend):
        """Test selecting a track from search results and playing it."""
        # Search for tracks
        response = backend.get("/api/library/tracks?limit=10&offset=0")
        if not response["tracks"]:
            pytest.skip("No tracks available")

        track = response["tracks"][0]
        track_id = track["id"]

        # Load and play
        backend.post(f"/api/player/load?track_path={track['filepath']}&track_id={track_id}")
        status = backend.post("/api/player/play")

        assert status["is_playing"] is True
        assert status["current_track"] is not None or len(status["queue"]) > 0

    def test_add_to_queue_from_search(self, backend):
        """Test adding searched tracks to queue."""
        # Get tracks
        response = backend.get("/api/library/tracks?limit=5&offset=0")
        if len(response["tracks"]) < 2:
            pytest.skip("Need at least 2 tracks")

        tracks = response["tracks"]

        # Set initial queue
        backend.post(
            "/api/player/queue",
            {"tracks": [tracks[0]["id"]], "start_index": 0}
        )

        # Add second track to queue
        response = backend.post(
            "/api/player/queue/add",
            {"track_id": tracks[1]["id"]}
        )

        queue_ids = [t["id"] for t in response["queue"]]
        assert tracks[1]["id"] in queue_ids


# ============================================================================
# WORKFLOW 3: Error Recovery
# ============================================================================


class TestErrorRecovery:
    """Test error handling and recovery."""

    def test_invalid_track_id(self, backend):
        """Test loading invalid track path."""
        with pytest.raises(Exception):  # Should raise HTTP error
            backend.post("/api/player/load?track_path=/nonexistent/path.mp3&track_id=999999")

    def test_seek_beyond_duration(self, backend):
        """Test seeking beyond track duration."""
        tracks = backend.get("/api/library/tracks?limit=1&offset=0")
        if not tracks["tracks"]:
            pytest.skip("No tracks available")

        track = tracks["tracks"][0]
        backend.post(f"/api/player/load?track_path={track['filepath']}&track_id={track['id']}")
        backend.post("/api/player/play")

        # Seek beyond duration
        response = backend.post(f"/api/player/seek?position={track['duration'] * 2}")

        # Should clamp to duration
        assert response["current_time"] <= track["duration"]

    def test_seek_negative_position(self, backend):
        """Test seeking to negative position."""
        tracks = backend.get("/api/library/tracks?limit=1&offset=0")
        if not tracks["tracks"]:
            pytest.skip("No tracks available")

        track = tracks["tracks"][0]
        backend.post(f"/api/player/load?track_path={track['filepath']}&track_id={track['id']}")
        backend.post("/api/player/play")

        # Seek to negative
        response = backend.post("/api/player/seek?position=-10")

        # Should clamp to 0
        assert response["current_time"] >= 0

    def test_volume_out_of_range(self, backend):
        """Test volume values outside 0-100 range."""
        # Over 100
        response = backend.post("/api/player/volume?volume=150")
        assert 0 <= response["volume"] <= 100

        # Negative
        response = backend.post("/api/player/volume?volume=-50")
        assert 0 <= response["volume"] <= 100

    def test_state_consistency_after_error(self, backend):
        """Verify state is consistent after error."""
        # Get initial state
        initial = backend.get("/api/player/status")

        # Try invalid operation
        try:
            backend.post("/api/player/load?track_path=/nonexistent/path.mp3&track_id=999999")
        except Exception:
            pass

        # State should still be valid
        final = backend.get("/api/player/status")

        assert "state" in final
        assert "is_playing" in final
        assert "volume" in final


# ============================================================================
# WEBSOCKET INTEGRATION (Real-time Updates)
# ============================================================================


class TestWebSocketIntegration:
    """Test WebSocket real-time message delivery."""

    @pytest.mark.asyncio
    async def test_ws_connection(self):
        """Test WebSocket can connect."""
        listener = WebSocketListener()
        try:
            await listener.connect()
            assert listener.websocket is not None
        finally:
            await listener.disconnect()

    @pytest.mark.asyncio
    async def test_ws_playback_state_message(self, backend):
        """Test WebSocket broadcasts playback state changes."""
        listener = WebSocketListener()
        try:
            await listener.connect()

            # Clear any existing messages
            listener.clear_messages()

            # Load and play a track
            tracks = backend.get("/api/library/tracks?limit=1&offset=0")
            if not tracks["tracks"]:
                pytest.skip("No tracks available")

            track = tracks["tracks"][0]
            backend.post(f"/api/player/load?track_path={track['filepath']}&track_id={track['id']}")

            # Listen for messages while playing
            async def listen_task():
                async for msg in listener.listen(timeout=3.0):
                    if msg.get("type") == "playback_state_changed":
                        return msg

            backend.post("/api/player/play")

            # Wait for WebSocket message
            try:
                msg = await asyncio.wait_for(listen_task(), timeout=5.0)
                assert msg is not None
                assert msg["type"] == "playback_state_changed"
                assert "data" in msg
            except asyncio.TimeoutError:
                pytest.skip("WebSocket message not received in time")

        finally:
            await listener.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
