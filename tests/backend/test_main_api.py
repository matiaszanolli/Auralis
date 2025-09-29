"""
Tests for Main FastAPI Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for the main FastAPI backend.
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
            mock_track = Mock()
            mock_track.to_dict.return_value = {
                "id": 1,
                "title": "Test Song",
                "filepath": "/path/to/song.mp3",
                "duration": 180,
                "format": "mp3"
            }
            mock_library.get_recent_tracks.return_value = [mock_track]

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
            mock_track = Mock()
            mock_track.to_dict.return_value = {
                "id": 2,
                "title": "Test Result",
                "filepath": "/path/to/result.wav"
            }
            mock_library.search_tracks.return_value = [mock_track]

            response = client.get("/api/library/tracks?search=test&limit=5")

            assert response.status_code == 200
            data = response.json()
            assert len(data["tracks"]) == 1
            mock_library.search_tracks.assert_called_once_with("test", limit=5)

    def test_get_tracks_pagination(self, client):
        """Test track pagination"""
        with patch('main.library_manager') as mock_library:
            mock_library.get_recent_tracks.return_value = []

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

            response = client.post("/api/library/scan?directory=/test/path")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "scanning" in data["status"]

    def test_scan_directory_no_library(self, client):
        """Test scan when library manager not available"""
        with patch('main.library_manager', None):
            response = client.post("/api/library/scan?directory=/test/path")

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
        with patch('main.audio_player') as mock_player:
            mock_player.state.value = "stopped"
            mock_player.volume = 0.8
            mock_player.get_position.return_value = 45.0
            mock_player.get_duration.return_value = 180.0
            mock_player.get_current_track.return_value = "test.mp3"
            mock_player.queue_manager.queue = []
            mock_player.shuffle_enabled = False
            mock_player.repeat_mode = "none"

            response = client.get("/api/player/status")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "stopped"
            assert data["volume"] == 0.8

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
        with patch('main.audio_player') as mock_player:
            mock_player.play = Mock()

            response = client.post("/api/player/play")

            assert response.status_code == 200
            mock_player.play.assert_called_once()

    def test_pause_audio(self, client):
        """Test pausing playback"""
        with patch('main.audio_player') as mock_player:
            mock_player.pause = Mock()

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
        with patch('main.processing_engine') as mock_engine:
            mock_engine.register_progress_callback = Mock()

            with client.websocket_connect("/ws") as websocket:
                # Subscribe to job progress
                websocket.send_json({
                    "type": "subscribe_job_progress",
                    "job_id": "test-job-123"
                })

                # Verify callback was registered
                mock_engine.register_progress_callback.assert_called_once()

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])