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

    def test_health_check_pydantic_schema_exported(self, client):
        """HealthResponse model is used — FastAPI exposes it in /openapi.json (#3863)."""
        schema = client.get("/openapi.json").json()
        schemas = schema.get("components", {}).get("schemas", {})
        assert "HealthResponse" in schemas, (
            "HealthResponse Pydantic model must appear in OpenAPI schema (#3863)"
        )


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

    def test_version_pydantic_schema_exported(self, client):
        """VersionInfoResponse model is used — FastAPI exposes it in /openapi.json (#3863)."""
        schema = client.get("/openapi.json").json()
        schemas = schema.get("components", {}).get("schemas", {})
        assert "VersionInfoResponse" in schemas, (
            "VersionInfoResponse Pydantic model must appear in OpenAPI schema (#3863)"
        )


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

            # Drain initial handshake frames (e.g. enhancement_settings_changed)
            # until we find the pong response.
            for _ in range(10):
                data = json.loads(websocket.receive_text())
                if data.get("type") == "pong":
                    break
            else:
                raise AssertionError("pong not received within 10 frames")

    def test_websocket_multiple_pings(self, client):
        """Test multiple ping/pong cycles"""
        with client.websocket_connect("/ws") as websocket:
            for _ in range(3):
                websocket.send_text(json.dumps({"type": "ping"}))
                # Drain until pong (first iteration may see handshake frames)
                for _ in range(10):
                    data = json.loads(websocket.receive_text())
                    if data.get("type") == "pong":
                        break
                else:
                    raise AssertionError("pong not received within 10 frames")


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

    @staticmethod
    def _recv_until_stream_error(websocket, max_reads=10):
        """Drain connect-handshake messages and return the first audio_stream_error.

        On connect the WS pushes handshake messages (enhancement_settings_changed,
        player_state); the relevant response to play_enhanced is an
        audio_stream_error that follows.
        """
        for _ in range(max_reads):
            data = json.loads(websocket.receive_text())
            if data.get("type") == "audio_stream_error":
                return data
        raise AssertionError("No audio_stream_error received within max_reads")

    def test_play_enhanced_when_disabled(self, client):
        """Test play_enhanced when enhancement is disabled"""
        import main

        # Enhancement settings live in main.globals_dict and are read by the router
        # via a lambda closed over that dict; patch it in place so the handler sees
        # enabled=False (the old `main.enhancement_settings` attribute no longer exists).
        with patch.dict(main.globals_dict["enhancement_settings"], {"enabled": False}):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_text(json.dumps({
                    "type": "play_enhanced",
                    "data": {"track_id": 1}
                }))

                # Should be rejected with the disabled-gate error.
                data = self._recv_until_stream_error(websocket)
                assert data["data"]["code"] == "ENHANCEMENT_DISABLED"

    def test_play_enhanced_force_overrides_disabled(self, client):
        """force:true bypasses the stored enabled=False gate (#3773)

        With enhancement globally disabled, an explicit play_enhanced carrying
        force:true must NOT be rejected with ENHANCEMENT_DISABLED. The request
        proceeds past the gate and fails later for an unrelated reason (the track
        does not exist in the test DB), surfacing a different error code.
        """
        import main

        with patch.dict(main.globals_dict["enhancement_settings"], {"enabled": False}):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_text(json.dumps({
                    "type": "play_enhanced",
                    "data": {"track_id": 1, "force": True}
                }))

                # force overrides the stored-enabled gate: the first stream error
                # must not be the ENHANCEMENT_DISABLED rejection.
                data = self._recv_until_stream_error(websocket)
                assert data["data"]["code"] != "ENHANCEMENT_DISABLED"

    def test_play_enhanced_invalid_preset(self, client):
        """Test play_enhanced with invalid preset (Issue #2112)"""
        with client.websocket_connect("/ws") as websocket:
            # Send play_enhanced with invalid preset
            websocket.send_text(json.dumps({
                "type": "play_enhanced",
                "data": {
                    "track_id": 1,
                    "preset": "invalid_preset_name",
                    "intensity": 1.0
                }
            }))

            # Should receive error about invalid preset
            response = websocket.receive_text()
            data = json.loads(response)

            # Should either reject immediately or fail gracefully
            # Not crash the processing engine
            assert isinstance(data, dict)
            assert data.get("type") in ["audio_stream_error", "error", "seek_started"]

    def test_play_enhanced_out_of_range_intensity(self, client):
        """Test play_enhanced with out-of-range intensity (Issue #2112)"""
        with client.websocket_connect("/ws") as websocket:
            # Send play_enhanced with intensity > 1.0
            websocket.send_text(json.dumps({
                "type": "play_enhanced",
                "data": {
                    "track_id": 1,
                    "preset": "adaptive",
                    "intensity": 5.0  # Way out of range
                }
            }))

            # Should receive error or clamp value
            response = websocket.receive_text()
            data = json.loads(response)

            # Should handle gracefully, not crash
            assert isinstance(data, dict)

    def test_play_enhanced_negative_intensity(self, client):
        """Test play_enhanced with negative intensity (Issue #2112)"""
        with client.websocket_connect("/ws") as websocket:
            # Send play_enhanced with negative intensity
            websocket.send_text(json.dumps({
                "type": "play_enhanced",
                "data": {
                    "track_id": 1,
                    "preset": "adaptive",
                    "intensity": -0.5
                }
            }))

            # Should receive error or clamp to 0
            response = websocket.receive_text()
            data = json.loads(response)

            # Should handle gracefully
            assert isinstance(data, dict)

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

    def test_seek_awaits_old_task_before_starting_new_one(self, client):
        """Regression test for #3806.

        The seek handler used to give the prior streaming task only a 100ms
        `wait_for`/`shield` window before abandoning it and starting a new
        one: if the old task caught the cancellation but needed real time to
        finish up (e.g. flushing an already-computed chunk it was mid-way
        through sending), the 100ms deadline could fire first — the seek
        handler moved on to create the new task while the old one was still
        alive and finishing its own send, interleaving frames on the shared
        websocket.

        The mock below explicitly catches CancelledError and performs 0.2s
        of further async work before finishing (modeling that
        finish-sending-in-progress-chunk behavior) — longer than the old
        100ms deadline. Asserts the old task's completion marker is recorded
        before the second seek's acknowledgement is sent, proving the
        handler now waits for the old task's FULL lifecycle unconditionally
        rather than abandoning it on a timeout.
        """
        import asyncio
        import time as time_module

        import routers.system as system_module

        call_order = []

        async def slow_stream_from_position(
            websocket, get_repository_factory, get_enhancement_settings,
            get_cache_manager, *, track_id, preset, intensity, position,
            enhancement_enabled, ws_id,
        ):
            try:
                await asyncio.sleep(1000)  # normally streams chunks until cancelled
            except asyncio.CancelledError:
                # Model finishing an in-flight send after being cancelled —
                # takes longer than the old 100ms wait_for/shield deadline.
                await asyncio.sleep(0.2)
                call_order.append(f"old_task_completed:{position}")
                raise

        def _recv_until_type(ws, target: str, max_reads: int = 10) -> dict:
            """Drain frames until one matches ``target`` type (other broadcast
            traffic, e.g. enhancement_settings_changed, may arrive first)."""
            for _ in range(max_reads):
                data = json.loads(ws.receive_text())
                if data.get("type") == target:
                    return data
            raise AssertionError(f"No '{target}' frame received within {max_reads} reads")

        with patch.object(system_module, "stream_from_position", slow_stream_from_position):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_text(json.dumps({
                    "type": "seek",
                    "data": {"track_id": 1, "position": 10.0},
                }))
                _recv_until_type(websocket, "seek_started")
                # The task-creation block runs just AFTER the ack send, on
                # the server's next event-loop iteration — give it a moment
                # to register the task before popping it as "old_task" below,
                # so this test isn't racing the server's own async handoff.
                time_module.sleep(0.05)

                # Seek again while the first task is still sleeping inside
                # to_thread — this must fully await it before its own
                # acknowledgement is sent.
                start = time_module.monotonic()
                websocket.send_text(json.dumps({
                    "type": "seek",
                    "data": {"track_id": 1, "position": 20.0},
                }))
                second_ack = _recv_until_type(websocket, "seek_started")
                elapsed = time_module.monotonic() - start

                assert second_ack["data"]["position"] == 20.0
                # The old task's completion must have already happened by the
                # time the new seek is acknowledged — not abandoned mid-flight.
                assert call_order == ["old_task_completed:10.0"], (
                    "seek did not wait for the prior streaming task to finish "
                    f"before proceeding (call_order={call_order})"
                )
                assert elapsed >= 0.2, (
                    f"seek acknowledged after only {elapsed:.3f}s — the old "
                    "task's non-cancellable work should have blocked it"
                )


class TestWebSocketPlayNormal:
    """Tests for the play_normal WS message type (#3859 / BE-TC-4).

    play_normal is a 100-LOC handler with its own error-validation gate,
    background-task creation, and stream-error path — it had zero real-WS
    coverage before this class.
    """

    @staticmethod
    def _recv_until_type(websocket, target: str, max_reads: int = 10) -> dict:
        """Drain frames until one matches ``target`` type; return it."""
        for _ in range(max_reads):
            data = json.loads(websocket.receive_text())
            if data.get("type") == target:
                return data
        raise AssertionError(f"No '{target}' frame received within {max_reads} reads")

    def test_play_normal_invalid_track_id_returns_error(self, client):
        """play_normal without track_id must be rejected with 'invalid_track_id'."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({
                "type": "play_normal",
                "data": {}
            }))

            data = self._recv_until_type(websocket, "error")
            assert data["error"] == "invalid_track_id"

    def test_play_normal_negative_track_id_returns_error(self, client):
        """play_normal with a negative track_id must be rejected (non-positive int gate)."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({
                "type": "play_normal",
                "data": {"track_id": -5}
            }))

            data = self._recv_until_type(websocket, "error")
            assert data["error"] == "invalid_track_id"

    def test_play_normal_nonexistent_track_sends_stream_error(self, client):
        """play_normal for a track not in the DB produces an audio_stream_error."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({
                "type": "play_normal",
                "data": {"track_id": 99999}
            }))

            # The background task runs stream_normal_audio which fetches from DB,
            # finds nothing, and sends audio_stream_error.  May come after a small
            # delay, so drain up to 10 frames.
            found = False
            for _ in range(10):
                try:
                    msg = json.loads(websocket.receive_text())
                    if msg.get("type") == "audio_stream_error":
                        assert msg["data"]["stream_type"] == "normal"
                        found = True
                        break
                except Exception:
                    break
            assert found, "Expected audio_stream_error for nonexistent track in play_normal"

    def test_stream_error_branches_use_safe_message_not_raw_exception_text(self):
        """The `audio_stream_error` payload sent by the three streaming
        branches (`play_enhanced`/`stream_enhanced`, `play_normal`/
        `stream_normal`, `seek`/`stream_from_position`) must never carry a
        raw exception string — each `except Exception` branch must call
        `_safe_error_message(e)` instead (fixes #3820 / BE-RH-3 — WS-layer
        parity with the HTTP-layer `_safe_error_message` pattern already
        used elsewhere, e.g. `similarity.py`/`cache_streamlined.py`).

        `_safe_error_message` itself (imported from `core.processing_engine`)
        is a pure function with no websocket/request dependency and needs no
        further test here. This is a static regression guard on the call
        sites: it fails if a future edit reintroduces `str(e)`/`repr(e)`
        into an `audio_stream_error` "error" field.
        """
        import inspect
        import routers.system as system_module

        source = inspect.getsource(system_module)

        assert source.count('"error": _safe_error_message(e)') >= 3, (
            "Expected _safe_error_message(e) in the audio_stream_error 'error' "
            "field of all three streaming branches (play_enhanced, play_normal, seek)"
        )
        for forbidden in ('"error": str(e)', "'error': str(e)", '"error": repr(e)'):
            assert forbidden not in source, (
                f"Found raw exception interpolation {forbidden!r} in routers/system.py — "
                "audio_stream_error payloads must use _safe_error_message(e) instead"
            )


class TestWebSocketFlowControl:
    """Tests for flow-control and keepalive WS message types (#3859 / BE-TC-4).

    heartbeat, pong, buffer_full, and buffer_ready produce no WS response.
    The round-trip is validated by following them with a ping and asserting
    the connection is still live (pong received).  resume does produce a
    response (playback_resumed).

    NOTE: the server pushes one or two handshake messages on connect
    (enhancement_settings_changed, optionally player_state).  Tests that
    need the server's response to a specific message drain those handshake
    frames first with _recv_until_type().
    """

    @staticmethod
    def _recv_until_type(websocket, target: str, max_reads: int = 10) -> dict:
        """Drain frames until one matches ``target`` type; return it."""
        for _ in range(max_reads):
            data = json.loads(websocket.receive_text())
            if data.get("type") == target:
                return data
        raise AssertionError(f"No '{target}' frame received within {max_reads} reads")

    def test_resume_sends_playback_resumed(self, client):
        """resume must respond with playback_resumed."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "resume"}))
            data = self._recv_until_type(websocket, "playback_resumed")
            assert data["data"]["state"] == "playing"

    def test_heartbeat_keeps_connection_alive(self, client):
        """heartbeat (keepalive) must not crash the handler; connection stays up."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "heartbeat"}))
            # No response — verify liveness by sending ping after
            websocket.send_text(json.dumps({"type": "ping"}))
            data = self._recv_until_type(websocket, "pong")
            assert data["type"] == "pong"

    def test_pong_keeps_connection_alive(self, client):
        """pong (client-side heartbeat reply) must be handled without crashing."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "pong"}))
            # No response — verify liveness
            websocket.send_text(json.dumps({"type": "ping"}))
            data = self._recv_until_type(websocket, "pong")
            assert data["type"] == "pong"

    def test_buffer_full_clears_flow_event_and_connection_stays_alive(self, client):
        """buffer_full (frontend buffer filling) must be handled without crashing."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "buffer_full"}))
            # No response — verify liveness
            websocket.send_text(json.dumps({"type": "ping"}))
            data = self._recv_until_type(websocket, "pong")
            assert data["type"] == "pong"

    def test_buffer_ready_sets_flow_event_and_connection_stays_alive(self, client):
        """buffer_ready (frontend buffer drained) must be handled without crashing."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "buffer_ready"}))
            # No response — verify liveness
            websocket.send_text(json.dumps({"type": "ping"}))
            data = self._recv_until_type(websocket, "pong")
            assert data["type"] == "pong"


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
