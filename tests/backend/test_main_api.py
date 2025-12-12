"""
Tests for Main FastAPI Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for the main FastAPI backend.

NOTE: Multiple API endpoints return 404/503 due to incomplete implementation.
This file is marked as skipped. See test_api_endpoint_integration.py for
documented endpoint status and commit 38be81c for details.
"""

import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def client():
    """Create test client for main app"""
    # Import after adding to path
    from main import app
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """Test health check returns OK"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "auralis_available" in data
        assert data["status"] == "healthy"

    def test_health_check_fields(self, client):
        """Test health check includes all expected fields"""
        response = client.get("/api/health")
        data = response.json()

        assert "status" in data
        assert "auralis_available" in data
        assert "library_manager" in data


class TestLibraryEndpoints:
    """Test library management endpoints"""

    def test_get_library_stats(self, client):
        """Test getting library statistics"""
        response = client.get("/api/library/stats")

        # May return 503 if library not initialized, or 200 with stats
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            # Stats should be a dictionary
            assert isinstance(data, dict)

    def test_get_library_stats_with_mock(self, client):
        """Test library stats with mocked library manager"""
        with patch('main.library_manager') as mock_library:
            mock_library.get_library_stats.return_value = {
                "total_tracks": 100,
                "total_artists": 20,
                "total_albums": 15
            }

            response = client.get("/api/library/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_tracks"] == 100
            assert data["total_artists"] == 20

    def test_get_library_stats_error(self, client):
        """Test library stats error handling"""
        with patch('main.library_manager') as mock_library:
            mock_library.get_library_stats.side_effect = Exception("Database error")

            response = client.get("/api/library/stats")

            assert response.status_code == 500

    def test_get_tracks(self, client):
        """Test getting tracks from library"""
        response = client.get("/api/library/tracks?limit=10&offset=0")

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "tracks" in data
            assert "total" in data
            assert "offset" in data
            assert "limit" in data

    def test_get_tracks_with_mock(self, client):
        """Test getting tracks with mocked data"""
        with patch('main.library_manager') as mock_library:
            # Create a mock track with proper attribute values to avoid serialization issues
            mock_track = Mock()
            mock_track.id = 1
            mock_track.title = "Test Song"
            mock_track.filepath = "/path/to/song.mp3"
            mock_track.duration = 180
            mock_track.format = "mp3"
            # get_all_tracks returns (tracks, total) tuple
            mock_library.get_all_tracks.return_value = ([mock_track], 1)

            response = client.get("/api/library/tracks?limit=10")

            assert response.status_code == 200
            data = response.json()
            assert len(data["tracks"]) == 1
            assert data["tracks"][0]["title"] == "Test Song"

    def test_get_tracks_with_search(self, client):
        """Test searching tracks"""
        response = client.get("/api/library/tracks?search=test")

        assert response.status_code in [200, 503]

    def test_get_tracks_with_search_mock(self, client):
        """Test track search with mocked data"""
        with patch('main.library_manager') as mock_library:
            # Create a mock track with proper attribute values to avoid serialization issues
            mock_track = Mock()
            mock_track.id = 2
            mock_track.title = "Test Result"
            mock_track.filepath = "/path/to/result.wav"
            mock_track.duration = 0  # Default from DEFAULT_TRACK_FIELDS
            mock_track.format = "Unknown"  # Default from DEFAULT_TRACK_FIELDS
            mock_library.search_tracks.return_value = [mock_track]

            response = client.get("/api/library/tracks?search=test&limit=5")

            assert response.status_code == 200
            data = response.json()
            assert len(data["tracks"]) == 1
            # API now includes offset parameter
            mock_library.search_tracks.assert_called_once_with("test", limit=5, offset=0)

    def test_get_tracks_pagination(self, client):
        """Test track pagination"""
        with patch('main.library_manager') as mock_library:
            # get_all_tracks returns (tracks, total) tuple
            mock_library.get_all_tracks.return_value = ([], 100)

            response = client.get("/api/library/tracks?limit=25&offset=50")

            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == 25
            assert data["offset"] == 50

    def test_get_artists(self, client):
        """Test getting artists list"""
        response = client.get("/api/library/artists")

        assert response.status_code in [200, 503]

    def test_scan_directory(self, client):
        """Test directory scanning"""
        with patch('main.library_manager') as mock_library, \
             patch('main.LibraryScanner') as mock_scanner_class:

            mock_scanner = Mock()
            mock_scanner_class.return_value = mock_scanner

            response = client.post("/api/library/scan", json={"directory": "/test/path"})

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "scanning" in data["status"]

    def test_scan_directory_no_library(self, client):
        """Test scan when library manager not available"""
        with patch('main.library_manager', None):
            response = client.post("/api/library/scan", json={"directory": "/test/path"})

            assert response.status_code == 503


class TestAudioFormats:
    """Test audio format endpoints"""

    def test_get_supported_formats(self, client):
        """Test getting supported audio formats"""
        response = client.get("/api/audio/formats")

        assert response.status_code == 200
        data = response.json()

        assert "input_formats" in data
        assert "output_formats" in data
        assert "sample_rates" in data
        assert "bit_depths" in data

        # Check specific formats
        assert ".wav" in data["input_formats"]
        assert ".mp3" in data["input_formats"]
        assert ".flac" in data["input_formats"]

    def test_supported_output_formats(self, client):
        """Test output formats include common types"""
        response = client.get("/api/audio/formats")
        data = response.json()

        output_formats = data["output_formats"]
        assert ".wav" in output_formats
        assert ".flac" in output_formats
        assert ".mp3" in output_formats

    def test_supported_sample_rates(self, client):
        """Test sample rates include standard values"""
        response = client.get("/api/audio/formats")
        data = response.json()

        sample_rates = data["sample_rates"]
        assert 44100 in sample_rates
        assert 48000 in sample_rates

    def test_supported_bit_depths(self, client):
        """Test bit depths include standard values"""
        response = client.get("/api/audio/formats")
        data = response.json()

        bit_depths = data["bit_depths"]
        assert 16 in bit_depths
        assert 24 in bit_depths


class TestFileUpload:
    """Test file upload endpoints"""

    def test_upload_single_wav_file(self, client, tmp_path):
        """Test uploading a single WAV file"""
        # Create a temporary WAV file
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)  # Minimal WAV header

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/files/upload",
                files={"files": ("test.wav", f, "audio/wav")}
            )

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["filename"] == "test.wav"
        assert data["results"][0]["status"] == "success"

    def test_upload_multiple_files(self, client, tmp_path):
        """Test uploading multiple files"""
        # Create test files
        files = []
        for name in ["test1.wav", "test2.mp3", "test3.flac"]:
            test_file = tmp_path / name
            test_file.write_bytes(b"test content")
            files.append(("files", (name, open(test_file, "rb"), "audio/wav")))

        response = client.post("/api/files/upload", files=files)

        # Close file handles
        for _, (_, f, _) in files:
            f.close()

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert len(data["results"]) == 3

    def test_upload_unsupported_file_type(self, client, tmp_path):
        """Test uploading unsupported file type"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("not audio")

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/files/upload",
                files={"files": ("test.txt", f, "text/plain")}
            )

        assert response.status_code == 200
        data = response.json()

        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "error"
        assert "Unsupported file type" in data["results"][0]["message"]

    def test_upload_mixed_valid_invalid_files(self, client, tmp_path):
        """Test uploading mix of valid and invalid files"""
        wav_file = tmp_path / "good.wav"
        wav_file.write_bytes(b"audio")

        txt_file = tmp_path / "bad.txt"
        txt_file.write_text("text")

        files = [
            ("files", ("good.wav", open(wav_file, "rb"), "audio/wav")),
            ("files", ("bad.txt", open(txt_file, "rb"), "text/plain"))
        ]

        response = client.post("/api/files/upload", files=files)

        # Close file handles
        for _, (_, f, _) in files:
            f.close()

        assert response.status_code == 200
        data = response.json()

        assert len(data["results"]) == 2
        assert data["results"][0]["status"] == "success"
        assert data["results"][1]["status"] == "error"

    def test_upload_all_supported_formats(self, client, tmp_path):
        """Test uploading all supported audio formats"""
        formats = [".mp3", ".wav", ".flac", ".ogg", ".m4a"]
        files = []

        for fmt in formats:
            test_file = tmp_path / f"test{fmt}"
            test_file.write_bytes(b"audio data")
            files.append(("files", (f"test{fmt}", open(test_file, "rb"), "audio/*")))

        response = client.post("/api/files/upload", files=files)

        # Close file handles
        for _, (_, f, _) in files:
            f.close()

        assert response.status_code == 200
        data = response.json()

        assert len(data["results"]) == 5
        for result in data["results"]:
            assert result["status"] == "success"

    def test_upload_no_files(self, client):
        """Test upload endpoint with no files"""
        response = client.post("/api/files/upload", files=[])

        assert response.status_code == 422  # Validation error


class TestPlayerEndpoints:
    """Test audio player endpoints"""

    def test_get_player_status(self, client):
        """Test getting player status"""
        response = client.get("/api/player/status")

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "state" in data
            assert "volume" in data

    def test_get_player_status_with_mock(self, client):
        """Test player status with mocked player"""
        from player_state import PlayerState, PlaybackState

        with patch('main.player_state_manager') as mock_state_manager:
            # Create mock PlayerState
            mock_state = PlayerState(
                state=PlaybackState.STOPPED,
                volume=80,
                current_track=None,
                queue=[]
            )
            mock_state_manager.get_state.return_value = mock_state

            response = client.get("/api/player/status")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "stopped"
            assert data["volume"] == 80

    def test_load_track(self, client):
        """Test loading a track"""
        with patch('main.audio_player') as mock_player:
            mock_player.add_to_queue = Mock()
            mock_player.load_current_track.return_value = True

            response = client.post("/api/player/load?track_path=/test/song.mp3")

            assert response.status_code == 200
            mock_player.add_to_queue.assert_called_once()

    def test_play_audio(self, client):
        """Test starting playback"""
        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager') as mock_state_manager:
            mock_player.play = Mock()
            mock_state_manager.set_playing = AsyncMock()

            response = client.post("/api/player/play")

            assert response.status_code == 200
            mock_player.play.assert_called_once()

    def test_pause_audio(self, client):
        """Test pausing playback"""
        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager') as mock_state_manager:
            mock_player.pause = Mock()
            mock_state_manager.set_playing = AsyncMock()

            response = client.post("/api/player/pause")

            assert response.status_code == 200
            mock_player.pause.assert_called_once()

    def test_stop_audio(self, client):
        """Test stopping playback"""
        with patch('main.audio_player') as mock_player:
            mock_player.stop = Mock()

            response = client.post("/api/player/stop")

            assert response.status_code == 200
            mock_player.stop.assert_called_once()

    def test_seek_audio(self, client):
        """Test seeking to position"""
        with patch('main.audio_player') as mock_player:
            mock_player.seek_to_position = Mock()

            response = client.post("/api/player/seek?position=60.0")

            assert response.status_code == 200
            mock_player.seek_to_position.assert_called_once()

    def test_set_volume(self, client):
        """Test setting volume"""
        with patch('main.audio_player') as mock_player:
            mock_player.set_volume = Mock()

            response = client.post("/api/player/volume?volume=0.75")

            assert response.status_code == 200
            mock_player.set_volume.assert_called_once()

    def test_next_track(self, client):
        """Test skipping to next track"""
        with patch('main.audio_player') as mock_player:
            mock_player.next_track = Mock(return_value=True)

            response = client.post("/api/player/next")

            assert response.status_code == 200
            mock_player.next_track.assert_called_once()

    def test_previous_track(self, client):
        """Test going to previous track"""
        with patch('main.audio_player') as mock_player:
            mock_player.previous_track = Mock(return_value=True)

            response = client.post("/api/player/previous")

            assert response.status_code == 200
            mock_player.previous_track.assert_called_once()

    def test_get_queue(self, client):
        """Test getting playback queue"""
        response = client.get("/api/player/queue")

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "tracks" in data or "current_index" in data

    def test_add_to_queue(self, client):
        """Test adding track to queue"""
        with patch('main.audio_player') as mock_player:
            mock_player.add_to_queue = Mock()

            response = client.post("/api/player/queue/add?track_path=/new/song.mp3")

            assert response.status_code == 200
            mock_player.add_to_queue.assert_called_once()


class TestProcessingControlEndpoints:
    """Test processing control endpoints"""

    def test_get_audio_analysis(self, client):
        """Test getting audio analysis"""
        response = client.get("/api/processing/analysis")

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            # Should contain analysis metrics
            assert isinstance(data, dict)

    def test_enable_level_matching(self, client):
        """Test enabling level matching"""
        with patch('main.audio_player') as mock_player:
            mock_player.config.enable_level_matching = False

            response = client.post("/api/processing/enable_matching?enabled=true")

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True

    def test_disable_level_matching(self, client):
        """Test disabling level matching"""
        with patch('main.audio_player') as mock_player:
            mock_player.config.enable_level_matching = True

            response = client.post("/api/processing/enable_matching?enabled=false")

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False

    def test_load_reference_track(self, client):
        """Test loading reference track"""
        with patch('main.audio_player') as mock_player:
            mock_player.load_reference.return_value = True

            response = client.post("/api/processing/load_reference?reference_path=/ref.wav")

            assert response.status_code == 200
            data = response.json()
            assert "reference_path" in data
            mock_player.load_reference.assert_called_once()

    def test_load_reference_track_failure(self, client):
        """Test reference track loading failure"""
        with patch('main.audio_player') as mock_player:
            mock_player.load_reference.side_effect = Exception("Failed to load")

            response = client.post("/api/processing/load_reference?reference_path=/bad.wav")

            assert response.status_code == 500

    def test_apply_processing_preset(self, client):
        """Test applying processing preset"""
        with patch('main.audio_player') as mock_player:
            settings = {"mode": "adaptive", "target_loudness": -14}

            response = client.post(
                "/api/processing/apply_preset",
                params={"preset_name": "warm"},
                json={"settings": settings}
            )

            assert response.status_code == 200
            data = response.json()
            assert "warm" in data["message"]

    def test_apply_preset_not_available(self, client):
        """Test applying preset when player not available"""
        with patch('main.audio_player', None):
            response = client.post(
                "/api/processing/apply_preset",
                params={"preset_name": "warm"},
                json={"settings": {}}
            )

            assert response.status_code == 503


class TestWebSocketConnection:
    """Test WebSocket endpoints"""

    def test_websocket_connection(self, client):
        """Test WebSocket connection and basic communication"""
        with client.websocket_connect("/ws") as websocket:
            # Test ping/pong
            websocket.send_json({"type": "ping"})
            response = websocket.receive_json()

            assert response["type"] == "pong"

    def test_websocket_processing_settings_update(self, client):
        """Test processing settings update via WebSocket"""
        with client.websocket_connect("/ws") as websocket:
            # Send processing settings update
            settings = {"mode": "adaptive", "target_loudness": -14}
            websocket.send_json({
                "type": "processing_settings_update",
                "data": settings
            })

            # Should receive broadcast confirmation
            response = websocket.receive_json()
            assert response["type"] == "processing_settings_applied"
            assert response["data"] == settings

    def test_websocket_ab_track_loaded(self, client):
        """Test A/B track loading via WebSocket"""
        with client.websocket_connect("/ws") as websocket:
            # Send A/B track loaded message
            track_data = {"track_id": "123", "name": "test.wav"}
            websocket.send_json({
                "type": "ab_track_loaded",
                "data": track_data
            })

            # Should receive broadcast confirmation
            response = websocket.receive_json()
            assert response["type"] == "ab_track_ready"
            assert response["data"] == track_data

    def test_websocket_subscribe_job_progress(self, client):
        """Test subscribing to job progress updates"""
        with client.websocket_connect("/ws") as websocket:
            # Subscribe to job progress - WebSocket should accept the message without error
            # (actual processing engine integration is tested elsewhere)
            websocket.send_json({
                "type": "subscribe_job_progress",
                "job_id": "test-job-123"
            })

            # Test passes if no exception is raised
            # The WebSocket remains open and functional

    def test_websocket_multiple_connections(self, client):
        """Test multiple simultaneous WebSocket connections"""
        with client.websocket_connect("/ws") as ws1, \
             client.websocket_connect("/ws") as ws2:

            # Send from first connection
            ws1.send_json({"type": "ping"})
            response1 = ws1.receive_json()
            assert response1["type"] == "pong"

            # Send from second connection
            ws2.send_json({"type": "ping"})
            response2 = ws2.receive_json()
            assert response2["type"] == "pong"

    def test_websocket_broadcast(self, client):
        """Test that messages are broadcast to all connections"""
        with client.websocket_connect("/ws") as ws1, \
             client.websocket_connect("/ws") as ws2:

            # Send processing settings from first connection
            settings = {"mode": "adaptive"}
            ws1.send_json({
                "type": "processing_settings_update",
                "data": settings
            })

            # Both connections should receive broadcast
            response1 = ws1.receive_json()
            assert response1["type"] == "processing_settings_applied"

            response2 = ws2.receive_json()
            assert response2["type"] == "processing_settings_applied"


class TestCORS:
    """Test CORS middleware"""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present"""
        response = client.options("/api/health")

        # CORS should allow cross-origin requests
        # TestClient may not fully simulate CORS, but we can check basic setup
        assert response.status_code in [200, 405]


class TestErrorHandling:
    """Test error handling"""

    def test_404_on_invalid_endpoint(self, client):
        """Test 404 on invalid endpoint"""
        response = client.get("/api/invalid/endpoint")

        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test 405 on wrong HTTP method"""
        response = client.post("/api/health")

        assert response.status_code == 405


class TestAPIDocumentation:
    """Test API documentation endpoints"""

    def test_openapi_schema(self, client):
        """Test OpenAPI schema is available"""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_api_docs_accessible(self, client):
        """Test API docs endpoint"""
        response = client.get("/api/docs")

        assert response.status_code == 200

    def test_redoc_accessible(self, client):
        """Test ReDoc endpoint"""
        response = client.get("/api/redoc")

        assert response.status_code == 200


class TestStaticFileServing:
    """Test static file serving"""

    def test_root_endpoint(self, client):
        """Test root endpoint serves frontend or info"""
        response = client.get("/")

        # Should serve frontend or show backend info
        assert response.status_code == 200


class TestIntegrationFlows:
    """Test integration workflows"""

    def test_health_to_formats_flow(self, client):
        """Test typical API flow: health check then get formats"""
        # Check health
        health_response = client.get("/api/health")
        assert health_response.status_code == 200

        # Get formats
        formats_response = client.get("/api/audio/formats")
        assert formats_response.status_code == 200

    def test_processing_workflow_endpoints_exist(self, client):
        """Test that processing workflow endpoints exist"""
        # These should all be registered, even if they return 503 without setup

        # Get presets
        response = client.get("/api/processing/presets")
        assert response.status_code in [200, 503]

        # Get queue status
        response = client.get("/api/processing/queue/status")
        assert response.status_code in [200, 503]


class TestLyricsEndpoint:
    """Test lyrics endpoint"""

    def test_get_lyrics_no_library(self, client):
        """Test getting lyrics when library not available"""
        with patch('main.library_manager', None):
            response = client.get("/api/library/tracks/1/lyrics")
            assert response.status_code == 503

    def test_get_lyrics_track_not_found(self, client):
        """Test getting lyrics for non-existent track"""
        with patch('main.library_manager') as mock_library:
            mock_library.tracks.get_by_id.return_value = None

            response = client.get("/api/library/tracks/999/lyrics")
            assert response.status_code == 404

    def test_get_lyrics_from_database(self, client):
        """Test getting cached lyrics from database"""
        with patch('main.library_manager') as mock_library:
            # Mock track with lyrics already in database
            mock_track = Mock()
            mock_track.lyrics = "[00:00.00]Test lyrics line 1\n[00:05.00]Test lyrics line 2"
            mock_track.filepath = "/path/to/track.mp3"
            mock_library.tracks.get_by_id.return_value = mock_track

            response = client.get("/api/library/tracks/1/lyrics")

            assert response.status_code == 200
            data = response.json()
            assert data["track_id"] == 1
            assert data["lyrics"] is not None
            assert data["format"] == "lrc"

    def test_get_lyrics_plain_text(self, client):
        """Test getting plain text lyrics"""
        with patch('main.library_manager') as mock_library:
            mock_track = Mock()
            mock_track.lyrics = "Plain text lyrics without timestamps"
            mock_track.filepath = "/path/to/track.mp3"
            mock_library.tracks.get_by_id.return_value = mock_track

            response = client.get("/api/library/tracks/1/lyrics")

            assert response.status_code == 200
            data = response.json()
            assert data["format"] == "plain"

    def test_get_lyrics_no_lyrics_available(self, client):
        """Test track with no lyrics"""
        with patch('main.library_manager') as mock_library:
            mock_track = Mock()
            mock_track.lyrics = None
            mock_track.filepath = "/path/to/track.mp3"
            mock_library.tracks.get_by_id.return_value = mock_track

            response = client.get("/api/library/tracks/1/lyrics")

            assert response.status_code == 200
            data = response.json()
            assert data["lyrics"] is None
            assert data["format"] is None


class TestFavoritesEndpoints:
    """Test favorites management endpoints"""

    def test_get_favorites_no_library(self, client):
        """Test getting favorites when library not available"""
        with patch('main.library_manager', None):
            response = client.get("/api/library/tracks/favorites")
            assert response.status_code == 503

    def test_get_favorites_success(self, client):
        """Test getting favorite tracks"""
        with patch('main.library_manager') as mock_library:
            # Create mock tracks with proper attribute values to avoid serialization issues
            mock_track1 = Mock()
            mock_track1.id = 1
            mock_track1.title = "Track 1"
            mock_track1.filepath = "/path/to/track1.wav"
            mock_track1.duration = 180
            mock_track1.format = "Unknown"

            mock_track2 = Mock()
            mock_track2.id = 2
            mock_track2.title = "Track 2"
            mock_track2.filepath = "/path/to/track2.wav"
            mock_track2.duration = 200
            mock_track2.format = "Unknown"

            # Endpoint calls get_favorite_tracks() not tracks.get_favorites()
            mock_library.get_favorite_tracks.return_value = [mock_track1, mock_track2]

            response = client.get("/api/library/tracks/favorites")

            assert response.status_code == 200
            data = response.json()
            assert "tracks" in data
            assert len(data["tracks"]) == 2

    def test_add_favorite_success(self, client):
        """Test adding track to favorites"""
        with patch('main.library_manager') as mock_library:
            mock_library.tracks.set_favorite.return_value = None

            response = client.post("/api/library/tracks/1/favorite")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Track marked as favorite"
            assert data["track_id"] == 1
            assert data["favorite"] is True

    def test_add_favorite_track_not_found(self, client):
        """Test adding non-existent track to favorites"""
        with patch('main.library_manager') as mock_library:
            mock_library.tracks.set_favorite.side_effect = Exception("Track not found")

            response = client.post("/api/library/tracks/999/favorite")
            assert response.status_code == 500

    def test_remove_favorite_success(self, client):
        """Test removing track from favorites"""
        with patch('main.library_manager') as mock_library:
            mock_library.tracks.set_favorite.return_value = None

            response = client.delete("/api/library/tracks/1/favorite")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Track removed from favorites"
            assert data["track_id"] == 1
            assert data["favorite"] is False


class TestSettingsEndpoints:
    """Test settings management endpoints"""

    def test_get_settings_no_repository(self, client):
        """Test getting settings when repository not available"""
        with patch('main.settings_repository', None):
            response = client.get("/api/settings")
            assert response.status_code == 503

    def test_get_settings_success(self, client):
        """Test getting application settings"""
        with patch('main.settings_repository') as mock_repo:
            mock_settings = Mock()
            mock_settings.to_dict.return_value = {
                "theme": "dark",
                "volume": 80,
                "gapless_enabled": True,
                "crossfade_enabled": False
            }
            mock_repo.get_settings.return_value = mock_settings

            response = client.get("/api/settings")

            assert response.status_code == 200
            data = response.json()
            assert "theme" in data
            assert "volume" in data

    def test_update_settings_success(self, client):
        """Test updating application settings"""
        with patch('main.settings_repository') as mock_repo:
            mock_settings = Mock()
            mock_settings.to_dict.return_value = {"theme": "light", "volume": 90}
            mock_repo.update_settings.return_value = mock_settings

            new_settings = {
                "theme": "light",
                "volume": 90
            }

            response = client.put("/api/settings", json=new_settings)

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert data["message"] == "Settings updated successfully"

    def test_reset_settings_success(self, client):
        """Test resetting settings to defaults"""
        with patch('main.settings_repository') as mock_repo:
            mock_settings = Mock()
            mock_settings.to_dict.return_value = {}
            mock_repo.reset_settings.return_value = mock_settings

            response = client.post("/api/settings/reset")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    def test_add_scan_folder_success(self, client):
        """Test adding scan folder"""
        with patch('main.settings_repository') as mock_repo:
            mock_settings = Mock()
            mock_settings.scan_folders = ["/existing/folder"]
            mock_settings.to_dict.return_value = {"scan_folders": ["/existing/folder", "/new/folder"]}
            mock_repo.get_settings.return_value = mock_settings
            mock_repo.add_scan_folder.return_value = mock_settings

            response = client.post("/api/settings/scan-folders", json={"folder": "/new/folder"})

            assert response.status_code == 200

    def test_remove_scan_folder_success(self, client):
        """Test removing scan folder"""
        with patch('main.settings_repository') as mock_repo:
            mock_settings = Mock()
            mock_settings.scan_folders = ["/folder1", "/folder2"]
            mock_settings.to_dict.return_value = {"scan_folders": ["/folder2"]}
            mock_repo.get_settings.return_value = mock_settings
            mock_repo.remove_scan_folder.return_value = mock_settings

            # Use request.request for DELETE with body
            response = client.request(
                "DELETE",
                "/api/settings/scan-folders",
                json={"folder": "/folder1"}
            )

            assert response.status_code == 200


class TestAlbumArtistEndpoints:
    """Test album and artist detail endpoints"""

    def test_get_artist_detail_success(self, client):
        """Test getting artist details"""
        with patch('main.library_manager') as mock_library:
            # Create mock artist with proper attribute values to avoid serialization issues
            # Important: explicitly set albums and tracks to empty lists to prevent Mock from
            # creating infinite recursion when serializer uses hasattr() and len()
            mock_artist = Mock()
            mock_artist.id = 1
            mock_artist.name = "Test Artist"
            mock_artist.track_count = 10
            mock_artist.album_count = 2
            mock_artist.albums = []  # Prevent Mock infinite recursion
            mock_artist.tracks = []  # Prevent Mock infinite recursion
            mock_library.artists.get_by_id.return_value = mock_artist

            response = client.get("/api/library/artists/1")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test Artist"

    def test_get_artist_not_found(self, client):
        """Test getting non-existent artist"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = None

            response = client.get("/api/library/artists/999")
            assert response.status_code == 404

    def test_get_album_detail_success(self, client):
        """Test getting album details"""
        with patch('main.library_manager') as mock_library:
            # Create mock album with spec to prevent infinite Mock recursion
            # Use a dict-like object instead of Mock to avoid JSON serialization issues
            album_data = {
                'id': 1,
                'title': 'Test Album',
                'artist': 'Test Artist',
                'year': 2024,
                'artwork_path': None,
                'tracks': []
            }
            # Convert dict to object-like mock with attributes
            from types import SimpleNamespace
            mock_album = SimpleNamespace(**album_data)
            mock_library.albums.get_by_id.return_value = mock_album

            response = client.get("/api/library/albums/1")

            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Test Album"

    def test_get_album_not_found(self, client):
        """Test getting non-existent album"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.return_value = None

            response = client.get("/api/library/albums/999")
            assert response.status_code == 404

    def test_get_albums_list(self, client):
        """Test getting albums list"""
        with patch('main.library_manager') as mock_library:
            # Use SimpleNamespace instead of Mock to avoid JSON serialization recursion issues
            from types import SimpleNamespace

            mock_album1 = SimpleNamespace(
                id=1,
                title="Album 1",
                artist="Artist 1",
                year=2023,
                artwork_path=None,
                tracks=[]
            )

            mock_album2 = SimpleNamespace(
                id=2,
                title="Album 2",
                artist="Artist 2",
                year=2024,
                artwork_path=None,
                tracks=[]
            )

            mock_library.albums.get_all.return_value = [mock_album1, mock_album2]

            response = client.get("/api/library/albums")

            assert response.status_code == 200
            data = response.json()
            assert "albums" in data
            assert len(data["albums"]) == 2


class TestVersionEndpoint:
    """Test version endpoint"""

    def test_get_version(self, client):
        """Test getting API version"""
        response = client.get("/api/version")

        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        assert "db_schema_version" in data


class TestPlaylistEndpoints:
    """Test playlist management endpoints"""

    def test_get_playlists_no_library(self, client):
        """Test getting playlists when library not available"""
        with patch('main.library_manager', None):
            response = client.get("/api/playlists")
            assert response.status_code == 503

    def test_get_playlists_success(self, client):
        """Test getting all playlists"""
        with patch('main.library_manager') as mock_library:
            mock_playlist1 = Mock()
            mock_playlist1.to_dict.return_value = {"id": 1, "name": "Playlist 1"}
            mock_playlist2 = Mock()
            mock_playlist2.to_dict.return_value = {"id": 2, "name": "Playlist 2"}

            mock_library.playlists.get_all.return_value = [mock_playlist1, mock_playlist2]

            response = client.get("/api/playlists")

            assert response.status_code == 200
            data = response.json()
            assert "playlists" in data
            assert len(data["playlists"]) == 2

    def test_get_playlist_by_id_success(self, client):
        """Test getting playlist by ID"""
        with patch('main.library_manager') as mock_library:
            mock_playlist = Mock()
            mock_playlist.to_dict.return_value = {"id": 1, "name": "My Playlist"}
            mock_playlist.tracks = []  # Empty tracks list
            mock_library.playlists.get_by_id.return_value = mock_playlist

            response = client.get("/api/playlists/1")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "My Playlist"

    def test_get_playlist_not_found(self, client):
        """Test getting non-existent playlist"""
        with patch('main.library_manager') as mock_library:
            mock_library.playlists.get_by_id.return_value = None

            response = client.get("/api/playlists/999")
            assert response.status_code == 404

    def test_create_playlist_success(self, client):
        """Test creating a new playlist"""
        with patch('main.library_manager') as mock_library:
            with patch('main.manager') as mock_ws_manager:
                mock_ws_manager.broadcast = AsyncMock()

                mock_playlist = Mock()
                mock_playlist.id = 1
                mock_playlist.name = "New Playlist"
                mock_playlist.to_dict.return_value = {"id": 1, "name": "New Playlist"}
                mock_library.playlists.create.return_value = mock_playlist

                response = client.post("/api/playlists", json={"name": "New Playlist"})

                assert response.status_code == 200
                data = response.json()
                assert "playlist" in data
                assert data["playlist"]["id"] == 1

    def test_update_playlist_success(self, client):
        """Test updating playlist"""
        with patch('main.library_manager') as mock_library:
            with patch('main.manager') as mock_ws_manager:
                mock_ws_manager.broadcast = AsyncMock()

                mock_library.playlists.update.return_value = True

                response = client.put("/api/playlists/1", json={"name": "Updated Playlist"})

                assert response.status_code == 200
                data = response.json()
                assert "message" in data
                assert data["message"] == "Playlist updated successfully"

    def test_delete_playlist_success(self, client):
        """Test deleting playlist"""
        with patch('main.library_manager') as mock_library:
            mock_library.playlists.delete.return_value = True

            response = client.delete("/api/playlists/1")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    def test_add_track_to_playlist_success(self, client):
        """Test adding track to playlist"""
        with patch('main.library_manager') as mock_library:
            with patch('main.manager') as mock_ws_manager:
                mock_ws_manager.broadcast = AsyncMock()

                mock_library.playlists.add_track.return_value = True

                response = client.post("/api/playlists/1/tracks", json={"track_ids": [5]})

                assert response.status_code == 200
                data = response.json()
                assert "added_count" in data
                assert data["added_count"] == 1

    def test_remove_track_from_playlist_success(self, client):
        """Test removing track from playlist"""
        with patch('main.library_manager') as mock_library:
            response = client.delete("/api/playlists/1/tracks/5")

            assert response.status_code == 200

    def test_clear_playlist_success(self, client):
        """Test clearing all tracks from playlist"""
        with patch('main.library_manager') as mock_library:
            response = client.delete("/api/playlists/1/tracks")

            assert response.status_code == 200


class TestPlayerEnhancementEndpoints:
    """Test player enhancement endpoints"""

    def test_toggle_enhancement_on(self, client):
        """Test enabling enhancement"""
        with patch('main.manager') as mock_ws_manager:
            mock_ws_manager.broadcast = AsyncMock()

            response = client.post("/api/player/enhancement/toggle?enabled=true")

            assert response.status_code == 200
            data = response.json()
            assert "settings" in data

    def test_toggle_enhancement_off(self, client):
        """Test disabling enhancement"""
        with patch('main.manager') as mock_ws_manager:
            mock_ws_manager.broadcast = AsyncMock()

            response = client.post("/api/player/enhancement/toggle?enabled=false")

            assert response.status_code == 200
            data = response.json()
            assert "settings" in data

    def test_set_enhancement_preset(self, client):
        """Test setting enhancement preset"""
        with patch('main.manager') as mock_ws_manager:
            mock_ws_manager.broadcast = AsyncMock()

            response = client.post("/api/player/enhancement/preset?preset=warm")

            assert response.status_code == 200
            data = response.json()
            assert "settings" in data

    def test_set_enhancement_intensity(self, client):
        """Test setting enhancement intensity"""
        with patch('main.manager') as mock_ws_manager:
            mock_ws_manager.broadcast = AsyncMock()

            response = client.post("/api/player/enhancement/intensity?intensity=0.7")

            assert response.status_code == 200
            data = response.json()
            assert "settings" in data

    def test_get_enhancement_status(self, client):
        """Test getting enhancement status"""
        response = client.get("/api/player/enhancement/status")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data


class TestAlbumArtworkEndpoints:
    """Test album artwork endpoints"""

    def test_get_artwork_no_library(self, client):
        """Test getting artwork when library not available"""
        with patch('main.library_manager', None):
            response = client.get("/api/albums/1/artwork")
            assert response.status_code == 503

    def test_get_artwork_album_not_found(self, client):
        """Test getting artwork for non-existent album"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.return_value = None

            response = client.get("/api/albums/999/artwork")
            assert response.status_code == 404

    def test_get_artwork_no_artwork(self, client):
        """Test getting artwork when album has no artwork"""
        with patch('main.library_manager') as mock_library:
            mock_album = Mock()
            mock_album.artwork_path = None
            mock_library.albums.get_by_id.return_value = mock_album

            response = client.get("/api/albums/1/artwork")
            assert response.status_code == 404

    def test_extract_artwork_success(self, client):
        """Test extracting artwork from audio file"""
        with patch('main.library_manager') as mock_library:
            mock_album = Mock()
            mock_album.id = 1
            mock_library.albums.get_by_id.return_value = mock_album
            mock_library.albums.extract_and_save_artwork.return_value = "/path/to/artwork.jpg"

            response = client.post("/api/albums/1/artwork/extract")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    def test_delete_artwork_success(self, client):
        """Test deleting album artwork"""
        with patch('main.library_manager') as mock_library:
            mock_album = Mock()
            mock_album.artwork_path = "/path/to/artwork.jpg"
            mock_library.albums.get_by_id.return_value = mock_album

            response = client.delete("/api/albums/1/artwork")

            assert response.status_code == 200


class TestPlayerStreamEndpoint:
    """Test audio streaming endpoint"""

    def test_stream_track_no_library(self, client):
        """Test streaming when library not available"""
        with patch('main.library_manager', None):
            response = client.get("/api/player/stream/1")
            assert response.status_code == 503

    def test_stream_track_not_found(self, client):
        """Test streaming non-existent track"""
        with patch('main.library_manager') as mock_library:
            mock_library.tracks.get_by_id.return_value = None

            response = client.get("/api/player/stream/999")
            assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# ============================================================
# Phase 5C.2: Dual-Mode Backend Testing Patterns
# ============================================================
# Following the same pattern as Phase 5C.1 API tests.

@pytest.mark.phase5c
class TestAPIEndpointDualMode:
    """Phase 5C.2: Dual-mode tests using mock fixtures from conftest.py"""

    def test_mock_library_manager_fixture_interface(self, mock_library_manager):
        """Test that mock_library_manager has required interface."""
        assert hasattr(mock_library_manager, 'library')
        assert hasattr(mock_library_manager.library, 'get_all')
        assert hasattr(mock_library_manager.library, 'get_by_id')

    def test_mock_repository_factory_fixture_interface(self, mock_repository_factory):
        """Test that mock_repository_factory has required interface."""
        assert hasattr(mock_repository_factory, 'library')
        assert hasattr(mock_repository_factory.library, 'get_all')
        assert hasattr(mock_repository_factory.library, 'get_by_id')

    def test_dual_mode_interface_equivalence(self, mock_library_manager, mock_repository_factory):
        """Test that both mocks implement equivalent interfaces."""
        from unittest.mock import Mock
        
        # Create test data
        item = Mock()
        item.id = 1
        item.name = "Test"

        # Test LibraryManager pattern
        mock_library_manager.library.get_by_id = Mock(return_value=item)
        lib_result = mock_library_manager.library.get_by_id(1)
        assert lib_result.id == 1

        # Test RepositoryFactory pattern
        mock_repository_factory.library.get_by_id = Mock(return_value=item)
        repo_result = mock_repository_factory.library.get_by_id(1)
        assert repo_result.id == 1

        # Both should return same result
        assert lib_result.name == repo_result.name
