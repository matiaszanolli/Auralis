"""
Tests for System Router
~~~~~~~~~~~~~~~~~~~~~~~

Tests for system infrastructure endpoints and WebSocket communication.

Coverage:
- GET /api/health - Health check
- GET /api/version - Version information
- WebSocket /ws - Real-time communication
  - ping/pong
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

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


def _recv_until_type(websocket, target: str, max_reads: int = 10) -> dict:
    """Drain frames until one matches ``target`` type and return it.

    Every `/ws` connection is immediately sent unsolicited sync frames
    (`enhancement_settings_changed`, `player_state` — see
    ws_handlers/connection.py:setup_connection, #2507/#2606) before any
    client-initiated message gets a response, so tests must drain past them
    rather than asserting on the first frame received. (#4781: tests that
    skipped this drain asserted directly on the first frame, which was
    reliably one of these sync frames instead of the expected response, and
    left the extra unread frames sitting in the connection's receive queue
    past test teardown.)
    """
    for _ in range(max_reads):
        data = json.loads(websocket.receive_text())
        if data.get("type") == target:
            return data
    raise AssertionError(f"No {target!r} frame received within {max_reads} reads")


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
        """HealthResponse is registered in the generated OpenAPI schema (#3863)."""
        import main

        # Production intentionally disables the HTTP OpenAPI route (#4375).
        # Inspect the generated schema directly so this tests response-model
        # registration without contradicting that security contract.
        schema = main.app.openapi()
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
        from auralis.version import DB_SCHEMA_VERSION

        assert data["db_schema_version"] == DB_SCHEMA_VERSION

    def test_version_pydantic_schema_exported(self, client):
        """VersionInfoResponse is registered in the generated OpenAPI schema (#3863)."""
        import main

        from auralis.version import __version__

        schema = main.app.openapi()
        assert schema["info"]["version"] == __version__
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

            # Should receive error message (after the connect-handshake frames)
            data = _recv_until_type(websocket, "error")
            assert data["error"] == "invalid_json"

    def test_websocket_oversized_message(self, client):
        """Test that oversized messages are rejected (security)"""
        with client.websocket_connect("/ws") as websocket:
            # Create large message (> 1MB)
            large_data = "x" * (1024 * 1024 + 1)
            message = json.dumps({"type": "test", "data": large_data})

            websocket.send_text(message)

            # Should receive error message (after the connect-handshake frames)
            data = _recv_until_type(websocket, "error")
            assert "size" in data.get("message", "").lower()

    def test_websocket_rate_limiting(self, client):
        """Test WebSocket rate limiting (security)

        Uses "buffer_full" rather than "ping" (#4786: ping/pong/heartbeat are
        protocol-critical control frames exempt from the rate limiter, so a
        burst of pings would never trigger it — see
        TestWebSocketRateLimitExemptsControlFrames below for that guarantee).
        """
        with client.websocket_connect("/ws") as websocket:
            # Send messages rapidly to trigger rate limit
            for i in range(15):  # Limit is 10/sec
                websocket.send_text(json.dumps({"type": "buffer_full"}))

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


class TestWebSocketRateLimitExemptsControlFrames:
    """#4786: ping/pong/heartbeat must never be dropped by the rate limiter,
    regardless of how many other messages preceded them in the same window.
    A dropped pong never reaches heartbeat.mark_pong(), so the connection
    gets force-closed by the next heartbeat tick as if it had gone stale."""

    @pytest.fixture(autouse=True)
    def _reset_rate_limiter(self):
        """_rate_limiter is a module-level singleton shared by every
        connection in the process (routers/system.py), and its per-IP
        bucket deliberately survives across connections/reconnects (#3811).
        Each burst test here intentionally exhausts the per-connection limit
        (10/s), which also charges ~10 messages against the shared per-IP
        bucket (30/s) — three such tests in quick succession would exhaust
        that shared bucket and spuriously rate-limit whatever test happens
        to run next. Reset before and after so this class neither inherits
        pollution from other rate-limit tests nor leaves any behind."""
        import routers.system as system_module

        def _clear():
            system_module._rate_limiter.message_log.clear()
            system_module._rate_limiter.ip_message_log.clear()

        _clear()
        yield
        _clear()

    def test_ping_survives_a_rate_limit_exceeding_burst(self, client):
        """A burst that exhausts the rate limit (proven by
        test_websocket_rate_limiting above) must not also swallow a ping
        sent immediately after — a real pong reply must still arrive.

        The burst itself legitimately produces real rate_limit_exceeded
        errors (for the non-exempt buffer_full messages) queued ahead of the
        pong — those are drained, not asserted against; only the pong's
        eventual arrival is the assertion.
        """
        with client.websocket_connect("/ws") as websocket:
            # Exhaust the per-connection rate limit (10 msg/s) — same burst
            # shape proven to trigger it in test_websocket_rate_limiting.
            for _ in range(15):
                websocket.send_text(json.dumps({"type": "buffer_full"}))

            # ping is exempt: must still get a real pong, even though the
            # limiter is exhausted from the burst above.
            websocket.send_text(json.dumps({"type": "ping"}))

            for _ in range(30):
                data = json.loads(websocket.receive_text())
                if data.get("type") == "pong":
                    break
            else:
                raise AssertionError(
                    "No pong received after the rate-limited burst — ping was "
                    "likely dropped by the rate limiter (#4786)"
                )

    def test_pong_survives_a_rate_limit_exceeding_burst_and_keeps_connection_alive(
        self, client
    ):
        """A pong sent inside a rate-limit-exceeding burst must still reach
        the heartbeat handler — proven indirectly here by the connection
        staying responsive to a ping sent right after (a dropped pong alone
        produces no observable symptom until the next heartbeat tick, which
        this test cannot wait 30s for — see the integration-level
        assertion in TestWebSocketFlowControl for the direct handling
        check)."""
        with client.websocket_connect("/ws") as websocket:
            for _ in range(15):
                websocket.send_text(json.dumps({"type": "buffer_full"}))
            websocket.send_text(json.dumps({"type": "pong"}))  # exempt, no reply
            websocket.send_text(json.dumps({"type": "ping"}))

            for _ in range(30):
                data = json.loads(websocket.receive_text())
                if data.get("type") == "pong":
                    break
            else:
                raise AssertionError(
                    "No pong received after the rate-limited burst — pong/ping "
                    "were likely dropped by the rate limiter (#4786)"
                )

    @pytest.mark.asyncio
    async def test_handle_ping_marks_heartbeat_alive(self):
        """SIBLING gap fixed alongside #4786: handle_ping replied pong but
        never recorded liveness, so a client-initiated ping did not count
        towards the connection's is_alive() state (unlike handle_heartbeat,
        which already called mark_alive)."""
        from ws_handlers.messages import handle_ping
        from websocket.websocket_protocol import HeartbeatManager

        heartbeat = HeartbeatManager()
        connection_id = "test-conn-1"
        ws = AsyncMock()
        # handle_ping now sends via safe_send_text (#4771), which checks
        # is_websocket_connected(ws) — client_state.name must read
        # "CONNECTED" for the send to go through (established pattern, e.g.
        # test_audio_stream_crossfade.py).
        ws.client_state = Mock()
        ws.client_state.name = "CONNECTED"

        assert connection_id not in heartbeat.last_heartbeat
        await handle_ping(ws, heartbeat, connection_id)

        assert connection_id in heartbeat.last_heartbeat
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "pong"


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

            # Should receive error about invalid preset (after the
            # connect-handshake frames: enhancement_settings_changed, player_state)
            handshake_types = {"enhancement_settings_changed", "player_state"}
            for _ in range(10):
                data = json.loads(websocket.receive_text())
                if data.get("type") not in handshake_types:
                    break
            else:
                raise AssertionError("No response received within 10 frames")

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

            # Should receive pause acknowledgment (after connect-handshake frames)
            data = _recv_until_type(websocket, "playback_paused")

            assert data["data"]["state"] == "paused"

    def test_stop_playback(self, client):
        """Test stop message"""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "stop"}))

            # Should receive stop acknowledgment (after connect-handshake frames)
            data = _recv_until_type(websocket, "playback_stopped")

            assert data["data"]["state"] == "stopped"

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

            # Should receive seek acknowledgment (after connect-handshake frames)
            data = _recv_until_type(websocket, "seek_started")

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

    def test_play_enhanced_releases_lock_before_awaiting_old_task(self, client):
        """Regression test for #3828 / BE-WS-2.

        play_enhanced used to `await old_task` from INSIDE
        _active_streaming_tasks_lock. stream_audio's own finally block also
        acquires this same (non-reentrant) lock for idempotent self-cleanup
        — with the lock still held by the outer await, that acquire() could
        never succeed until the awaiting task itself completed, which it
        can't do until the awaited task finishes: a real deadlock waiting to
        happen the moment any future change added lock-guarded cleanup work
        to the streaming task's finally block.

        The mock below explicitly re-acquires the SAME lock inside its
        CancelledError handler (modeling that real finally-block behavior)
        and signals a threading.Event on success — proving the lock was
        released before the second play_enhanced awaited the first task.
        threading.Event (not asyncio.Event) because the ASGI app runs its
        event loop on a different thread than this test.
        """
        import threading

        import asyncio

        import routers.system as system_module

        lock_reacquired = threading.Event()

        async def slow_stream_audio(
            websocket, get_repository_factory, get_enhancement_settings,
            get_cache_manager, *, track_id, preset, intensity, force,
            start_position, ws_id,
        ):
            try:
                await asyncio.sleep(1000)
            except asyncio.CancelledError:
                # Models stream_audio's real finally block, which also
                # acquires _active_streaming_tasks_lock (fixes #2425/#2430's
                # idempotent self-cleanup).
                async with system_module._active_streaming_tasks_lock:
                    lock_reacquired.set()
                raise

        def _recv_until_type(ws, target: str, max_reads: int = 10) -> dict:
            for _ in range(max_reads):
                data = json.loads(ws.receive_text())
                if data.get("type") == target:
                    return data
            raise AssertionError(f"No {target!r} frame received within {max_reads} reads")

        with patch.object(system_module, "stream_audio", slow_stream_audio):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_text(json.dumps({
                    "type": "play_enhanced",
                    "data": {"track_id": 1, "preset": "adaptive", "intensity": 1.0},
                }))
                # Let the first task actually start before cancelling it.
                import time as time_module
                time_module.sleep(0.05)

                websocket.send_text(json.dumps({
                    "type": "play_enhanced",
                    "data": {"track_id": 2, "preset": "adaptive", "intensity": 1.0},
                }))
                websocket.send_text(json.dumps({"type": "ping"}))
                _recv_until_type(websocket, "pong")

        assert lock_reacquired.wait(timeout=2.0), (
            "stream_audio's finally-block self-cleanup never acquired "
            "_active_streaming_tasks_lock — the outer handler is still "
            "holding it during await old_task (#3828 not fixed)"
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
    """Test WebSocket job progress subscription.

    NOTE: the original version of this test patched 'main.processing_engine',
    an attribute that no longer exists after the globals_dict refactor — it
    failed at collection time (AttributeError) rather than actually
    exercising the handler. Rewritten to patch main.globals_dict, matching
    the pattern used by every other processing_engine-dependent test in this
    file, and to send job_id nested under "data" (the shape
    subscribe_job_progress actually reads — the original top-level
    "job_id": ... was never read by the handler either).
    """

    @staticmethod
    def _recv_until_type(websocket, target: str, max_reads: int = 10) -> dict:
        for _ in range(max_reads):
            data = json.loads(websocket.receive_text())
            if data.get("type") == target:
                return data
        raise AssertionError(f"No {target!r} message received within {max_reads} reads")

    def test_subscribe_job_progress_registers_callback(self, client):
        """A valid job_id registers a progress callback with the engine."""
        mock_engine = Mock()
        mock_engine.register_progress_callback = AsyncMock()

        import main as main_module
        with patch.dict(main_module.globals_dict, {'processing_engine': mock_engine}):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_text(json.dumps({
                    "type": "subscribe_job_progress",
                    "data": {"job_id": "test-job-123"}
                }))
                websocket.send_text(json.dumps({"type": "ping"}))
                data = self._recv_until_type(websocket, "pong")
                assert data["type"] == "pong"

        mock_engine.register_progress_callback.assert_awaited_once()
        called_job_id = mock_engine.register_progress_callback.await_args[0][0]
        assert called_job_id == "test-job-123"

    def test_progress_callback_self_unregisters_after_disconnect(self, client):
        """Fixes #3826 / BE-RH-9.

        The registered progress_callback closure must not attempt
        websocket.send_text() once the socket has disconnected — it must
        check client_state and self-unregister from the engine instead.
        Without the fix, invoking the closure after disconnect raises
        (send on a closed connection); the engine's own catch-all in
        _notify_progress only removes the callback AFTER it raises once,
        so there's a real window where a dead-socket send is attempted.
        """
        mock_engine = Mock()
        mock_engine.register_progress_callback = AsyncMock()
        mock_engine.unregister_progress_callback = AsyncMock()

        import main as main_module
        with patch.dict(main_module.globals_dict, {'processing_engine': mock_engine}):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_text(json.dumps({
                    "type": "subscribe_job_progress",
                    "data": {"job_id": "test-job-456"}
                }))
                websocket.send_text(json.dumps({"type": "ping"}))
                self._recv_until_type(websocket, "pong")
            # `with` block exited — the websocket is now disconnected.

        assert mock_engine.register_progress_callback.await_args is not None
        progress_callback = mock_engine.register_progress_callback.await_args[0][1]
        # The server's own disconnect-cleanup loop already unregistered this
        # job_id once by the time the `with` block above exits — reset the
        # mock so the assertion below is specifically about the closure's
        # own self-unregister behavior, not the pre-existing cleanup path.
        mock_engine.unregister_progress_callback.reset_mock()

        # Invoking the closure post-disconnect must not raise, and must
        # self-unregister rather than attempt a send on the dead socket.
        import asyncio
        asyncio.run(progress_callback("test-job-456", 50.0, "halfway"))

        mock_engine.unregister_progress_callback.assert_awaited_once_with("test-job-456")


class TestWebSocketCleanup:
    """Test WebSocket cleanup on disconnect"""

    def test_websocket_disconnect_cleanup(self, client):
        """Test that resources are cleaned up on disconnect"""
        # Connect and disconnect
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "ping"}))
            _recv_until_type(websocket, "pong")

        # Reconnect should work (no resource leaks)
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "ping"}))
            _recv_until_type(websocket, "pong")

    def test_multiple_concurrent_connections(self, client):
        """Test multiple WebSocket connections simultaneously"""
        # Note: TestClient may not support true concurrent connections
        # This tests sequential connections
        connections = []

        try:
            for i in range(3):
                ws = client.websocket_connect("/ws")
                ws.__enter__()
                connections.append(ws)

            # All connections should be active
            for ws in connections:
                ws.send_text(json.dumps({"type": "ping"}))
                _recv_until_type(ws, "pong")
        finally:
            # Cleanup — must run even on assertion failure, or an unread
            # frame left in a connection's queue wedges the next test (#4781).
            for ws in connections:
                ws.__exit__(None, None, None)


class TestWebSocketHandlerExceptionResilience:
    """#4771: an unhandled exception inside a single WS message handler used
    to unwind past dispatch_message() to the outer except in
    routers/system.py, which falls into `finally: teardown_connection` and
    silently kills the whole connection — no error frame, the client's
    reconnect path misdiagnoses it as a network drop. dispatch_message() is
    now wrapped in its own try/except that reports 'internal_error' and
    keeps the loop (and connection) alive."""

    def test_handler_exception_sends_internal_error_and_keeps_connection_alive(self, client):
        # A generic bug in a handler (e.g. a KeyError from malformed internal
        # state) — NOT RuntimeError/WebSocketDisconnect, which the outer
        # handler still treats as genuinely fatal transport errors and tears
        # the connection down for (unchanged, pre-existing behavior).
        with patch(
            "ws_handlers.playback_control.handle_pause",
            side_effect=KeyError("boom — some internal detail"),
        ):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_text(json.dumps({"type": "pause"}))

                data = _recv_until_type(websocket, "error")
                assert data["error"] == "internal_error"
                # Never leak the raw exception text to the client (#3825-style
                # guarantee — same rationale as _safe_error_message).
                assert "boom" not in data.get("message", "")

                # The connection must still be alive and processing OTHER
                # message types afterward — not silently torn down. Matches
                # the acceptance criteria's integration test: "a subsequent
                # ping on the same connection still gets a pong".
                websocket.send_text(json.dumps({"type": "ping"}))
                pong = _recv_until_type(websocket, "pong")
                assert pong["type"] == "pong"

    def test_transport_errors_still_reraise_to_outer_handler(self):
        """Static regression guard: WebSocketDisconnect/RuntimeError raised
        inside a handler must still be re-raised out of the per-message
        try/except (not swallowed as an 'internal_error') so the outer
        handler's dedicated branches — disconnect logging, runtime-error
        logging, and (for RuntimeError specifically) still tearing the
        connection down — keep running exactly as before #4771.

        Not exercised live over a real TestClient socket: WebSocketDisconnect
        is only ever raised by Starlette when reading from an
        already-disconnected transport, so a handler-side raise (the only
        way to simulate "a handler raises it" in a unit test) leaves the
        server with no actual close frame to send back — the client-side
        receive_text() then blocks forever waiting for one that will never
        arrive, which is a TestClient artifact, not a real code path.
        """
        import inspect
        import routers.system as system_module

        source = inspect.getsource(system_module.create_system_router)
        assert "except (WebSocketDisconnect, RuntimeError):" in source, (
            "dispatch_message's per-message try/except must re-raise "
            "WebSocketDisconnect/RuntimeError rather than swallow them"
        )
        assert '"internal_error"' in source, (
            "Expected an internal_error frame sent for other, non-transport "
            "handler exceptions"
        )


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
            _recv_until_type(websocket, "pong")
