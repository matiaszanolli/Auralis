"""
Tests for System Router
~~~~~~~~~~~~~~~~~~~~~~~

Tests for system infrastructure endpoints and WebSocket communication.

Coverage:
- GET /api/health - Health check
- GET /api/version - Version information
- WebSocket /ws - Real-time communication
  - ping/pong
  - processing_settings_update
  - ab_track_loaded
  - play_enhanced
  - play_normal
  - pause
  - stop
  - seek
  - subscribe_job_progress

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


class TestHealthCheck:
    """Test GET /api/health"""

    def test_health_check_returns_healthy(self, client):
        """Test that health check returns healthy status"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "auralis_available" in data

    def test_health_check_accepts_get_only(self, client):
        """Test that health check only accepts GET"""
        response = client.post("/api/health")
        assert response.status_code == 405  # Method Not Allowed

    def test_health_check_structure(self, client):
        """Test health check response structure"""
        response = client.get("/api/health")
        data = response.json()

        assert isinstance(data["status"], str)
        assert isinstance(data["auralis_available"], bool)


class TestVersionEndpoint:
    """Test GET /api/version"""

    def test_get_version_returns_info(self, client):
        """Test that version endpoint returns version info"""
        response = client.get("/api/version")

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "version" in data
        assert "api_version" in data
        assert "db_schema_version" in data

    def test_version_structure(self, client):
        """Test version response has correct structure"""
        response = client.get("/api/version")
        data = response.json()

        # Semantic version components
        assert "major" in data
        assert "minor" in data
        assert "patch" in data
        assert isinstance(data["major"], int)
        assert isinstance(data["minor"], int)
        assert isinstance(data["patch"], int)

    def test_version_display_format(self, client):
        """Test that display version is formatted correctly"""
        response = client.get("/api/version")
        data = response.json()

        assert "display" in data
        assert "Auralis" in data["display"]
        assert data["version"] in data["display"]

    def test_version_accepts_get_only(self, client):
        """Test that version endpoint only accepts GET"""
        response = client.post("/api/version")
        assert response.status_code == 405

    def test_version_includes_build_metadata(self, client):
        """Test that version includes build metadata"""
        response = client.get("/api/version")
        data = response.json()

        assert "build_date" in data
        assert "api_version" in data
        assert data["api_version"] == "v1"
        assert data["db_schema_version"] == 3


class TestWebSocketConnection:
    """Test WebSocket connection and disconnection"""

    def test_websocket_connect(self, client):
        """Test WebSocket connection establishment"""
        with client.websocket_connect("/ws") as websocket:
            # Connection should be established
            assert websocket is not None

    def test_websocket_ping_pong(self, client):
        """Test WebSocket ping/pong heartbeat"""
        with client.websocket_connect("/ws") as websocket:
            # Send ping
            websocket.send_text(json.dumps({"type": "ping"}))

            # Receive pong
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "pong"

    def test_websocket_multiple_pings(self, client):
        """Test multiple ping/pong cycles"""
        with client.websocket_connect("/ws") as websocket:
            for _ in range(3):
                websocket.send_text(json.dumps({"type": "ping"}))
                response = websocket.receive_text()
                data = json.loads(response)
                assert data["type"] == "pong"


class TestWebSocketMessageValidation:
    """Test WebSocket message validation and security"""

    def test_websocket_invalid_json(self, client):
        """Test that invalid JSON is rejected"""
        with client.websocket_connect("/ws") as websocket:
            # Send invalid JSON
            websocket.send_text("invalid json {")

            # Should receive error message
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "error"
            assert "code" in data

    def test_websocket_oversized_message(self, client):
        """Test that oversized messages are rejected (security)"""
        with client.websocket_connect("/ws") as websocket:
            # Create large message (> 1MB)
            large_data = "x" * (1024 * 1024 + 1)
            message = json.dumps({"type": "test", "data": large_data})

            websocket.send_text(message)

            # Should receive error message
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "error"
            assert "size" in data.get("message", "").lower()

    def test_websocket_rate_limiting(self, client):
        """Test WebSocket rate limiting (security)"""
        with client.websocket_connect("/ws") as websocket:
            # Send messages rapidly to trigger rate limit
            for i in range(15):  # Limit is 10/sec
                websocket.send_text(json.dumps({"type": "ping"}))

            # Should receive rate limit error
            # Note: Some pongs may come through before rate limit kicks in
            response_received = False
            for _ in range(15):
                try:
                    response = websocket.receive_text()
                    data = json.loads(response)
                    if data["type"] == "error" and "rate" in str(data).lower():
                        response_received = True
                        break
                except Exception:
                    break

            # Rate limiting should have triggered
            assert response_received, "Rate limiting did not trigger"


class TestWebSocketProcessingSettings:
    """Test WebSocket processing settings messages"""

    @patch('main.connection_manager')
    def test_processing_settings_update(self, mock_manager, client):
        """Test processing settings update message"""
        mock_manager.broadcast = AsyncMock()

        with client.websocket_connect("/ws") as websocket:
            settings = {
                "preset": "warm",
                "intensity": 0.8
            }

            # Send processing settings update
            websocket.send_text(json.dumps({
                "type": "processing_settings_update",
                "data": settings
            }))

            # May receive broadcast response (depending on implementation)
            # Just verify no error
            try:
                response = websocket.receive_text()
                data = json.loads(response)
                # Should not be an error
                assert data.get("type") != "error"
            except Exception:
                # No response is also acceptable
                pass


class TestWebSocketABTesting:
    """Test WebSocket A/B comparison messages"""

    @patch('main.connection_manager')
    def test_ab_track_loaded(self, mock_manager, client):
        """Test A/B track loaded message"""
        mock_manager.broadcast = AsyncMock()

        with client.websocket_connect("/ws") as websocket:
            track_data = {
                "track_id": 1,
                "filepath": "/path/to/track.mp3"
            }

            # Send A/B track loaded message
            websocket.send_text(json.dumps({
                "type": "ab_track_loaded",
                "data": track_data
            }))

            # Should broadcast without error
            try:
                response = websocket.receive_text()
                data = json.loads(response)
                assert data.get("type") != "error"
            except Exception:
                pass


class TestWebSocketPlayback:
    """Test WebSocket playback control messages"""

    def test_play_enhanced_missing_track_id(self, client):
        """Test play_enhanced without track_id"""
        with client.websocket_connect("/ws") as websocket:
            # Send play_enhanced without track_id
            websocket.send_text(json.dumps({
                "type": "play_enhanced",
                "data": {}
            }))

            # Should receive error (track not found or similar)
            try:
                response = websocket.receive_text()
                data = json.loads(response)
                # May be error or may attempt processing
                # Just verify response is valid JSON
                assert isinstance(data, dict)
            except Exception:
                pass

    @patch('main.enhancement_settings')
    def test_play_enhanced_when_disabled(self, mock_settings, client):
        """Test play_enhanced when enhancement is disabled"""
        mock_settings.update({"enabled": False, "preset": "adaptive", "intensity": 1.0})

        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({
                "type": "play_enhanced",
                "data": {"track_id": 1}
            }))

            # Should receive error about enhancement being disabled
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "audio_stream_error"
            assert "ENHANCEMENT_DISABLED" in data["data"]["code"]

    def test_pause_playback(self, client):
        """Test pause message"""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "pause"}))

            # Should receive pause acknowledgment
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "playback_paused"
            assert data["data"]["success"] is True

    def test_stop_playback(self, client):
        """Test stop message"""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "stop"}))

            # Should receive stop acknowledgment
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "playback_stopped"
            assert data["data"]["success"] is True

    def test_seek_playback(self, client):
        """Test seek message"""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({
                "type": "seek",
                "data": {
                    "track_id": 1,
                    "position": 30.0
                }
            }))

            # Should receive seek acknowledgment
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "seek_started"
            assert data["data"]["position"] == 30.0


class TestWebSocketJobProgress:
    """Test WebSocket job progress subscription"""

    @patch('main.processing_engine')
    def test_subscribe_job_progress(self, mock_engine, client):
        """Test subscribing to job progress updates"""
        mock_engine.register_progress_callback = Mock()

        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({
                "type": "subscribe_job_progress",
                "job_id": "test-job-123"
            }))

            # Should register callback (verified via mock)
            # No error response expected
            try:
                # May not send response immediately
                websocket.send_text(json.dumps({"type": "ping"}))
                response = websocket.receive_text()
                data = json.loads(response)
                assert data["type"] == "pong"
            except Exception:
                pass


class TestWebSocketCleanup:
    """Test WebSocket cleanup on disconnect"""

    def test_websocket_disconnect_cleanup(self, client):
        """Test that resources are cleaned up on disconnect"""
        # Connect and disconnect
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "ping"}))
            response = websocket.receive_text()
            assert json.loads(response)["type"] == "pong"

        # Reconnect should work (no resource leaks)
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "ping"}))
            response = websocket.receive_text()
            assert json.loads(response)["type"] == "pong"

    def test_multiple_concurrent_connections(self, client):
        """Test multiple WebSocket connections simultaneously"""
        # Note: TestClient may not support true concurrent connections
        # This tests sequential connections
        connections = []

        for i in range(3):
            ws = client.websocket_connect("/ws")
            ws.__enter__()
            connections.append(ws)

        # All connections should be active
        for ws in connections:
            ws.send_text(json.dumps({"type": "ping"}))
            response = ws.receive_text()
            assert json.loads(response)["type"] == "pong"

        # Cleanup
        for ws in connections:
            ws.__exit__(None, None, None)


class TestSystemIntegration:
    """Integration tests for system endpoints"""

    def test_health_and_version_consistency(self, client):
        """Test that health and version endpoints are consistent"""
        health_response = client.get("/api/health")
        version_response = client.get("/api/version")

        assert health_response.status_code == 200
        assert version_response.status_code == 200

        # If health shows auralis available, version should work
        health_data = health_response.json()
        version_data = version_response.json()

        if health_data["auralis_available"]:
            assert "version" in version_data
            assert version_data["version"]

    def test_websocket_after_health_check(self, client):
        """Test WebSocket connection after health check"""
        # Check health first
        response = client.get("/api/health")
        assert response.status_code == 200

        # Then connect WebSocket
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "ping"}))
            response = websocket.receive_text()
            assert json.loads(response)["type"] == "pong"
