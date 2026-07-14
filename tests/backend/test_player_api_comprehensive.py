"""
Tests for Player Router (Comprehensive)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for all player control and queue management endpoints.

Coverage (14 active routes):
- GET /api/player/status - Get player status
- POST /api/player/load - Load track
- POST /api/player/seek - Seek to position
- GET /api/player/queue - Get playback queue
- POST /api/player/queue - Set entire queue
- POST /api/player/queue/add-track - Add track to queue (with position support)
- DELETE /api/player/queue/{index} - Remove track from queue
- PUT /api/player/queue/reorder - Reorder queue
- POST /api/player/queue/clear - Clear queue
- POST /api/player/queue/add-track (regression: legacy /queue/add removed #2725)
- PUT /api/player/queue/move - Move track in queue
- POST /api/player/queue/shuffle - Shuffle queue
- POST /api/player/next - Play next track
- POST /api/player/previous - Play previous track

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


class TestPlayerStatus:
    """Test GET /api/player/status"""

    def test_get_player_status_structure(self, client):
        """Test player status response structure"""
        response = client.get("/api/player/status")

        assert response.status_code == 200
        data = response.json()

        # Should have player state information
        assert isinstance(data, dict)

    def test_get_player_status_accepts_get_only(self, client):
        """Test that status endpoint only accepts GET"""
        response = client.post("/api/player/status")
        assert response.status_code in [404, 405]

    def test_get_player_status_consistency(self, client):
        """Test that multiple status requests are consistent"""
        response1 = client.get("/api/player/status")
        response2 = client.get("/api/player/status")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Structure should be identical
        assert set(response1.json().keys()) == set(response2.json().keys())


class TestLoadTrack:
    """Test POST /api/player/load"""

    def test_load_track_missing_track_id(self, client):
        """Test loading without track_id parameter"""
        response = client.post("/api/player/load", json={})

        # Should require track_id
        assert response.status_code in [400, 422]

    def test_load_track_invalid_track_id(self, client):
        """Test loading with invalid track ID"""
        response = client.post("/api/player/load", json={"track_id": "invalid"})

        assert response.status_code == 422

    def test_load_track_nonexistent(self, client):
        """Test loading non-existent track"""
        response = client.post("/api/player/load", json={"track_id": 999999})

        # Should return 404 or 500
        assert response.status_code in [404, 500]

    def test_load_track_accepts_post_only(self, client):
        """Test that load only accepts POST"""
        response = client.get("/api/player/load")
        assert response.status_code in [404, 405]

    def test_load_track_broadcasts_track_id_not_track_path(self, client):
        """Regression test for #3809.

        #2479 replaced the track_loaded broadcast's `track_path` field with
        `track_id` to stop leaking the server filesystem path — but
        WEBSOCKET_API.md and the frontend TrackLoadedMessage type weren't
        updated to match at the time. This asserts the actual wire payload:
        `track_id` present, `track_path` absent.
        """
        mock_player = Mock()
        mock_player.add_to_queue = Mock()
        mock_player.load_track_from_library.return_value = True

        mock_track = Mock()
        mock_track.id = 1
        mock_track.filepath = "/test/song.mp3"

        mock_library = Mock()
        mock_library.tracks.get_by_id.return_value = mock_track

        # connection_manager is bound into the player router's closures at
        # router-registration time (config/routes.py: connection_manager=manager),
        # so patching the module attribute `main.manager` post-hoc wouldn't
        # affect the already-closed-over reference — patch the .broadcast
        # method on the actual instance instead.
        import main as main_module

        with patch.dict('main.globals_dict', {'audio_player': mock_player, 'library_manager': mock_library}), \
             patch.object(main_module.manager, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            response = client.post("/api/player/load", json={"track_id": 1})

            assert response.status_code == 200
            track_loaded_calls = [
                call for call in mock_broadcast.call_args_list
                if call.args[0].get("type") == "track_loaded"
            ]
            assert len(track_loaded_calls) == 1, (
                f"expected exactly one track_loaded broadcast, got "
                f"{len(track_loaded_calls)}: {mock_broadcast.call_args_list}"
            )
            payload = track_loaded_calls[0].args[0]["data"]
            assert payload == {"track_id": 1}
            assert "track_path" not in payload, (
                "track_loaded broadcast must not leak the server filesystem "
                "path (#2479) — track_path must never reappear in this payload"
            )

    def test_load_track_does_not_block_event_loop_during_add_to_queue(self, client):
        """Regression test for #3815.

        audio_player.add_to_queue() can synchronously load a file (SoundFile
        open, 50-500ms typical) when nothing is loaded yet — e.g. the very
        first track played this session. If that call runs directly on the
        event loop instead of via asyncio.to_thread, it stalls every other
        in-flight request for its duration. Proves the fix by running a slow
        add_to_queue concurrently with a lightweight GET and asserting the
        GET isn't held up.
        """
        import threading
        import time

        mock_player = Mock()

        def slow_add_to_queue(track_info):
            time.sleep(0.3)

        mock_player.add_to_queue = Mock(side_effect=slow_add_to_queue)
        mock_player.load_track_from_library.return_value = True

        mock_track = Mock()
        mock_track.id = 1
        mock_track.filepath = "/test/song.mp3"

        mock_library = Mock()
        mock_library.tracks.get_by_id.return_value = mock_track

        with patch.dict('main.globals_dict', {'audio_player': mock_player, 'library_manager': mock_library}):
            results = {}

            def do_load():
                start = time.monotonic()
                resp = client.post("/api/player/load", json={"track_id": 1})
                results['load_status'] = resp.status_code
                results['load_elapsed'] = time.monotonic() - start

            load_thread = threading.Thread(target=do_load)
            load_thread.start()
            time.sleep(0.05)  # let the load request actually enter add_to_queue's sleep

            health_start = time.monotonic()
            health_resp = client.get("/api/health")
            health_elapsed = time.monotonic() - health_start

            load_thread.join(timeout=5)

            assert results.get('load_status') == 200
            assert results['load_elapsed'] >= 0.3, "sanity check: the slow mock actually ran"
            assert health_resp.status_code == 200
            assert health_elapsed < 0.25, (
                f"GET /api/health took {health_elapsed:.3f}s while a slow "
                "add_to_queue was in flight — the event loop was blocked "
                "(add_to_queue must run via asyncio.to_thread, not directly)"
            )

    def test_load_track_does_not_block_event_loop_during_get_by_id(self, client):
        """Regression test for #3822.

        library_manager.tracks.get_by_id() does a synchronous DB query.
        Under lock contention or a cold mtime-cache, this can take hundreds
        of ms. If it runs directly on the event loop instead of via
        asyncio.to_thread, it stalls every other in-flight request for that
        duration. Proves the fix (already applied — get_by_id is wrapped in
        asyncio.to_thread) by running a slow get_by_id concurrently with a
        lightweight GET and asserting the GET isn't held up.
        """
        import threading
        import time

        mock_player = Mock()
        mock_player.add_to_queue = Mock()
        mock_player.load_track_from_library.return_value = True

        mock_track = Mock()
        mock_track.id = 1
        mock_track.filepath = "/test/song.mp3"

        def slow_get_by_id(track_id):
            time.sleep(0.3)
            return mock_track

        mock_library = Mock()
        mock_library.tracks.get_by_id = Mock(side_effect=slow_get_by_id)

        with patch.dict('main.globals_dict', {'audio_player': mock_player, 'library_manager': mock_library}):
            results = {}

            def do_load():
                start = time.monotonic()
                resp = client.post("/api/player/load", json={"track_id": 1})
                results['load_status'] = resp.status_code
                results['load_elapsed'] = time.monotonic() - start

            load_thread = threading.Thread(target=do_load)
            load_thread.start()
            time.sleep(0.05)  # let the load request actually enter get_by_id's sleep

            health_start = time.monotonic()
            health_resp = client.get("/api/health")
            health_elapsed = time.monotonic() - health_start

            load_thread.join(timeout=5)

            assert results.get('load_status') == 200
            assert results['load_elapsed'] >= 0.3, "sanity check: the slow mock actually ran"
            assert health_resp.status_code == 200
            assert health_elapsed < 0.25, (
                f"GET /api/health took {health_elapsed:.3f}s while a slow "
                "get_by_id was in flight — the event loop was blocked "
                "(get_by_id must run via asyncio.to_thread, not directly)"
            )


class TestSeekPosition:
    """Test POST /api/player/seek"""

    def test_seek_missing_position(self, client):
        """Test seeking without position parameter"""
        response = client.post("/api/player/seek", json={})

        assert response.status_code in [400, 422]

    def test_seek_negative_position(self, client):
        """Test seeking to negative position"""
        response = client.post("/api/player/seek", json={"position": -10})

        # Should reject or clamp to 0
        assert response.status_code in [200, 400, 422]

    def test_seek_valid_position(self, client):
        """Test seeking to valid position"""
        response = client.post("/api/player/seek", json={"position": 30.5})

        # May fail if no track loaded, but validates parameter
        assert response.status_code in [200, 400, 500]

    def test_seek_accepts_post_only(self, client):
        """Test that seek only accepts POST"""
        response = client.get("/api/player/seek")
        assert response.status_code in [404, 405]


class TestGetQueue:
    """Test GET /api/player/queue"""

    def test_get_queue_structure(self, client):
        """Test queue response structure"""
        response = client.get("/api/player/queue")

        assert response.status_code == 200
        data = response.json()

        # Should return queue array or object
        assert isinstance(data, (list, dict))

    def test_get_queue_accepts_get_only(self, client):
        """Test that queue GET only accepts GET"""
        response = client.post("/api/player/queue", json={"tracks": []})
        # Note: POST /api/player/queue is a different endpoint (set queue)
        # This tests that the GET endpoint doesn't accept POST
        # But POST is valid for setting queue, so may return 200 or 400 (empty tracks)
        assert response.status_code in [200, 400, 404, 405]


class TestSetQueue:
    """Test POST /api/player/queue (set entire queue)"""

    def test_set_queue_empty(self, client):
        """Test setting queue to empty array"""
        response = client.post("/api/player/queue", json={"tracks": []})

        # Should accept empty queue
        assert response.status_code in [200, 400]

    def test_set_queue_with_tracks(self, client):
        """Test setting queue with track IDs"""
        response = client.post("/api/player/queue", json={"tracks": [1, 2, 3]})

        # May fail if tracks don't exist
        assert response.status_code in [200, 404, 500]

    def test_set_queue_invalid_format(self, client):
        """Test setting queue with invalid format"""
        response = client.post("/api/player/queue", json={"tracks": "invalid"})

        assert response.status_code == 422


class TestLegacyQueueAddRemoved:
    """Regression: legacy POST /api/player/queue/add removed (#2725)"""

    def test_legacy_queue_add_returns_404_or_405(self, client):
        """Legacy /api/player/queue/add no longer exists."""
        response = client.post("/api/player/queue/add", json={"track_id": 1})
        assert response.status_code in [404, 405]


class TestRemoveFromQueue:
    """Test DELETE /api/player/queue/{index}"""

    def test_remove_from_queue_invalid_index(self, client):
        """Test removing with invalid index"""
        response = client.delete("/api/player/queue/999")

        # Should return 404 or 400 (index out of range)
        assert response.status_code in [200, 400, 404]

    def test_remove_from_queue_negative_index(self, client):
        """Test removing with negative index"""
        response = client.delete("/api/player/queue/-1")

        assert response.status_code in [400, 404, 422]

    def test_remove_from_queue_accepts_delete_only(self, client):
        """Test that queue remove only accepts DELETE"""
        response = client.get("/api/player/queue/0")
        # Note: GET /api/player/queue is valid, so this might return 200
        # We're testing DELETE specifically
        assert response.status_code in [200, 404, 405]


class TestReorderQueue:
    """Test PUT /api/player/queue/reorder"""

    def test_reorder_queue_missing_parameters(self, client):
        """Test reordering without parameters"""
        response = client.put("/api/player/queue/reorder", json={})

        assert response.status_code in [400, 422]

    def test_reorder_queue_valid(self, client):
        """Test reordering with valid indices"""
        response = client.put(
            "/api/player/queue/reorder",
            json={"from_index": 0, "to_index": 2}
        )

        # May fail if queue is empty, or 422 if schema expects different fields
        assert response.status_code in [200, 400, 422, 500]

    def test_reorder_queue_accepts_put_only(self, client):
        """Test that reorder only accepts PUT"""
        response = client.post("/api/player/queue/reorder")
        assert response.status_code in [404, 405]


class TestClearQueue:
    """Test POST /api/player/queue/clear"""

    def test_clear_queue_success(self, client):
        """Test clearing the queue"""
        response = client.post("/api/player/queue/clear")

        # Should always succeed
        assert response.status_code == 200

    def test_clear_queue_idempotent(self, client):
        """Test that clearing multiple times is safe"""
        # First clear
        response1 = client.post("/api/player/queue/clear")
        assert response1.status_code == 200

        # Second clear (should also succeed)
        response2 = client.post("/api/player/queue/clear")
        assert response2.status_code == 200

    def test_clear_queue_accepts_post_only(self, client):
        """Test that clear only accepts POST"""
        response = client.get("/api/player/queue/clear")
        assert response.status_code in [404, 405]


class TestAddTrackToQueue:
    """Test POST /api/player/queue/add-track (alternate add endpoint)"""

    def test_add_track_missing_track_id(self, client):
        """Test adding track without track_id"""
        response = client.post("/api/player/queue/add-track", json={})

        assert response.status_code in [400, 422]

    def test_add_track_valid(self, client):
        """Test adding valid track"""
        response = client.post("/api/player/queue/add-track", json={"track_id": 1})

        assert response.status_code in [200, 404, 500]

    def test_add_track_accepts_post_only(self, client):
        """Test that add-track only accepts POST"""
        response = client.get("/api/player/queue/add-track")
        assert response.status_code in [404, 405]


class TestMoveQueueItem:
    """Test PUT /api/player/queue/move"""

    def test_move_queue_item_missing_parameters(self, client):
        """Test moving without parameters"""
        response = client.put("/api/player/queue/move", json={})

        assert response.status_code in [400, 422]

    def test_move_queue_item_valid(self, client):
        """Test moving with valid indices"""
        response = client.put(
            "/api/player/queue/move",
            json={"from_index": 0, "to_index": 1}
        )

        # May fail if queue is empty
        assert response.status_code in [200, 400, 500]

    def test_move_queue_item_accepts_put_only(self, client):
        """Test that move only accepts PUT"""
        response = client.post("/api/player/queue/move")
        assert response.status_code in [404, 405]


class TestShuffleQueue:
    """Test POST /api/player/queue/shuffle"""

    def test_shuffle_queue_success(self, client):
        """Test shuffling the queue"""
        response = client.post("/api/player/queue/shuffle")

        # 200 if player available, 500/503 if no player in test environment
        assert response.status_code in [200, 500, 503]

    def test_shuffle_queue_multiple_times(self, client):
        """Test shuffling multiple times"""
        for _ in range(3):
            response = client.post("/api/player/queue/shuffle")
            assert response.status_code in [200, 500, 503]

    def test_shuffle_queue_accepts_post_only(self, client):
        """Test that shuffle only accepts POST"""
        response = client.get("/api/player/queue/shuffle")
        assert response.status_code in [404, 405]


class TestPlayNext:
    """Test POST /api/player/next"""

    def test_play_next_success(self, client):
        """Test playing next track"""
        response = client.post("/api/player/next")

        # May fail if no next track
        assert response.status_code in [200, 400, 500]

    def test_play_next_accepts_post_only(self, client):
        """Test that next only accepts POST"""
        response = client.get("/api/player/next")
        assert response.status_code in [404, 405]


class TestPlayPrevious:
    """Test POST /api/player/previous"""

    def test_play_previous_success(self, client):
        """Test playing previous track"""
        response = client.post("/api/player/previous")

        # May fail if no previous track
        assert response.status_code in [200, 400, 500]

    def test_play_previous_accepts_post_only(self, client):
        """Test that previous only accepts POST"""
        response = client.get("/api/player/previous")
        assert response.status_code in [404, 405]


class TestPlayerIntegration:
    """Integration tests for player workflow"""

    def test_workflow_load_then_status(self, client):
        """Test workflow: load track → get status"""
        # 1. Load a track (may fail if track doesn't exist)
        load_response = client.post("/api/player/load", json={"track_id": 1})

        if load_response.status_code == 200:
            # 2. Get status
            status_response = client.get("/api/player/status")
            assert status_response.status_code == 200

    def test_workflow_queue_operations(self, client):
        """Test workflow: clear → add → shuffle → get queue"""
        # 1. Clear queue
        clear_response = client.post("/api/player/queue/clear")
        assert clear_response.status_code == 200

        # 2. Add tracks to queue
        for track_id in [1, 2, 3]:
            add_response = client.post(
                "/api/player/queue/add-track",
                json={"track_id": track_id}
            )
            # May fail if tracks don't exist
            if add_response.status_code != 200:
                break

        # 3. Shuffle queue (may fail in test env without audio player)
        shuffle_response = client.post("/api/player/queue/shuffle")
        assert shuffle_response.status_code in [200, 500, 503]

        # 4. Get queue
        queue_response = client.get("/api/player/queue")
        assert queue_response.status_code == 200

    def test_workflow_navigation(self, client):
        """Test workflow: add to queue → next → previous"""
        # 1. Clear and add tracks
        client.post("/api/player/queue/clear")
        client.post("/api/player/queue/add-track", json={"track_id": 1})
        client.post("/api/player/queue/add-track", json={"track_id": 2})

        # 2. Play next
        next_response = client.post("/api/player/next")
        assert next_response.status_code in [200, 400, 500]

        # 3. Play previous
        prev_response = client.post("/api/player/previous")
        assert prev_response.status_code in [200, 400, 500]

    def test_workflow_reorder_queue(self, client):
        """Test workflow: set queue → reorder → get queue"""
        # 1. Set queue with tracks
        set_response = client.post(
            "/api/player/queue",
            json={"tracks": [1, 2, 3]}
        )

        if set_response.status_code == 200:
            # 2. Reorder queue
            reorder_response = client.put(
                "/api/player/queue/reorder",
                json={"from_index": 0, "to_index": 2}
            )

            # 3. Get updated queue
            queue_response = client.get("/api/player/queue")
            assert queue_response.status_code == 200


class TestPlayerSecurityValidation:
    """Security-focused tests for player endpoints"""

    def test_load_track_sql_injection(self, client):
        """Test that track_id doesn't allow SQL injection"""
        response = client.post(
            "/api/player/load",
            json={"track_id": "1; DROP TABLE tracks; --"}
        )

        # Should reject malformed input
        assert response.status_code == 422

    def test_seek_overflow_protection(self, client):
        """Test seek position with extremely large value"""
        response = client.post(
            "/api/player/seek",
            json={"position": 999999999.0}
        )

        # Should handle gracefully (may clamp or reject)
        assert response.status_code in [200, 400, 500]

    def test_queue_operations_race_conditions(self, client):
        """Test rapid queue operations"""
        # Rapid adds
        for _ in range(10):
            client.post("/api/player/queue/add-track", json={"track_id": 1})

        # Queue should remain consistent
        queue_response = client.get("/api/player/queue")
        assert queue_response.status_code == 200

    def test_reorder_invalid_indices(self, client):
        """Test reordering with malicious indices"""
        response = client.put(
            "/api/player/queue/reorder",
            json={"from_index": -999, "to_index": 999999}
        )

        # Should reject or handle gracefully
        assert response.status_code in [200, 400, 422]


class TestRepeatMode:
    """Test POST /api/player/queue/repeat"""

    def test_set_repeat_all(self, client):
        """Test enabling repeat-all mode"""
        response = client.post(
            "/api/player/queue/repeat",
            json={"mode": "all"}
        )
        assert response.status_code == 200
        assert "message" in response.json()

    def test_set_repeat_one(self, client):
        """Test enabling repeat-one mode"""
        response = client.post(
            "/api/player/queue/repeat",
            json={"mode": "one"}
        )
        assert response.status_code == 200

    def test_set_repeat_off(self, client):
        """Test disabling repeat mode"""
        response = client.post(
            "/api/player/queue/repeat",
            json={"mode": "off"}
        )
        assert response.status_code == 200

    def test_set_repeat_invalid_mode(self, client):
        """Test that invalid repeat mode is rejected"""
        response = client.post(
            "/api/player/queue/repeat",
            json={"mode": "invalid"}
        )
        assert response.status_code == 422

    def test_set_repeat_missing_mode(self, client):
        """Test that missing mode field is rejected"""
        response = client.post(
            "/api/player/queue/repeat",
            json={}
        )
        assert response.status_code == 422


class TestQueueHistory:
    """Test GET/POST/DELETE /api/player/queue/history and POST /api/player/queue/undo.

    Regression coverage for #3805 — these 4 routes previously did not exist
    at all (404 on every call from the frontend's useQueueHistory hook).
    """

    @staticmethod
    def _snapshot(track_ids=None, current_index=0, is_shuffled=False, repeat_mode="off"):
        return {
            "track_ids": track_ids if track_ids is not None else [1, 2, 3],
            "current_index": current_index,
            "is_shuffled": is_shuffled,
            "repeat_mode": repeat_mode,
        }

    def test_get_history_empty_by_default(self, client):
        """A fresh (or already-cleared) history returns an empty list, not 404."""
        client.delete("/api/player/queue/history")  # ensure clean slate
        response = client.get("/api/player/queue/history")

        assert response.status_code == 200
        data = response.json()
        assert data["history"] == []
        assert data["count"] == 0

    def test_record_operation_then_appears_in_history(self, client):
        client.delete("/api/player/queue/history")

        record_response = client.post(
            "/api/player/queue/history",
            json={
                "operation": "add",
                "state_snapshot": self._snapshot(track_ids=[1, 2, 3]),
                "operation_metadata": {"track_id": 5},
            },
        )
        assert record_response.status_code == 200
        entry = record_response.json()
        assert entry["operation"] == "add"
        assert entry["state_snapshot"]["track_ids"] == [1, 2, 3]
        assert entry["operation_metadata"] == {"track_id": 5}
        assert "id" in entry
        assert "created_at" in entry

        history_response = client.get("/api/player/queue/history")
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert history_data["count"] >= 1
        assert any(e["id"] == entry["id"] for e in history_data["history"])

    def test_record_operation_rejects_invalid_operation_type(self, client):
        response = client.post(
            "/api/player/queue/history",
            json={
                "operation": "not_a_real_operation",
                "state_snapshot": self._snapshot(),
            },
        )
        assert response.status_code == 422

    def test_record_operation_rejects_missing_state_snapshot(self, client):
        response = client.post(
            "/api/player/queue/history",
            json={"operation": "add"},
        )
        assert response.status_code == 422

    def test_undo_with_no_history_returns_404(self, client):
        client.delete("/api/player/queue/history")

        response = client.post("/api/player/queue/undo")

        assert response.status_code == 404

    def test_undo_after_record_restores_and_removes_entry(self, client):
        client.delete("/api/player/queue/history")
        client.post(
            "/api/player/queue/history",
            json={
                "operation": "clear",
                "state_snapshot": self._snapshot(track_ids=[7, 8, 9], current_index=1),
            },
        )
        before_count = client.get("/api/player/queue/history").json()["count"]

        undo_response = client.post("/api/player/queue/undo")

        assert undo_response.status_code == 200
        data = undo_response.json()
        assert data["queue_state"]["track_ids"] == [7, 8, 9]
        assert data["queue_state"]["current_index"] == 1

        after_count = client.get("/api/player/queue/history").json()["count"]
        assert after_count == before_count - 1, (
            "undo must consume (delete) the history entry it restores from"
        )

    def test_undo_broadcasts_queue_changed_not_queue_updated(self, client):
        """#4420: the undo straggler must emit the canonical `queue_changed`
        (the #3492 rename), never the unsubscribed `queue_updated`."""
        from config.globals import ConnectionManager

        client.delete("/api/player/queue/history")
        client.post(
            "/api/player/queue/history",
            json={
                "operation": "clear",
                "state_snapshot": self._snapshot(track_ids=[7, 8, 9], current_index=1),
            },
        )

        # Patch at the class level so whichever ConnectionManager instance the
        # router captured is covered.
        with patch.object(ConnectionManager, "broadcast", new=AsyncMock()) as mock_bcast:
            response = client.post("/api/player/queue/undo")
            assert response.status_code == 200

        broadcast_types = [
            call.args[0].get("type")
            for call in mock_bcast.call_args_list
            if call.args and isinstance(call.args[0], dict)
        ]
        assert "queue_changed" in broadcast_types
        assert "queue_updated" not in broadcast_types

    def test_clear_history_empties_it(self, client):
        client.post(
            "/api/player/queue/history",
            json={"operation": "add", "state_snapshot": self._snapshot()},
        )
        assert client.get("/api/player/queue/history").json()["count"] >= 1

        clear_response = client.delete("/api/player/queue/history")
        assert clear_response.status_code == 200

        assert client.get("/api/player/queue/history").json()["count"] == 0
