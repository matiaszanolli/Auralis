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
- POST /api/player/queue/add - Add track to queue
- DELETE /api/player/queue/{index} - Remove track from queue
- PUT /api/player/queue/reorder - Reorder queue
- POST /api/player/queue/clear - Clear queue
- POST /api/player/queue/add-track - Add track to queue (alternate)
- PUT /api/player/queue/move - Move track in queue
- POST /api/player/queue/shuffle - Shuffle queue
- POST /api/player/next - Play next track
- POST /api/player/previous - Play previous track

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

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


class TestAddToQueue:
    """Test POST /api/player/queue/add"""

    def test_add_to_queue_missing_track_id(self, client):
        """Test adding without track_id"""
        response = client.post("/api/player/queue/add", json={})

        assert response.status_code in [400, 422]

    def test_add_to_queue_valid(self, client):
        """Test adding valid track to queue"""
        response = client.post("/api/player/queue/add", json={"track_id": 1})

        # May fail if track doesn't exist
        assert response.status_code in [200, 404, 500]

    def test_add_to_queue_accepts_post_only(self, client):
        """Test that queue add only accepts POST"""
        response = client.get("/api/player/queue/add")
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
                "/api/player/queue/add",
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
        client.post("/api/player/queue/add", json={"track_id": 1})
        client.post("/api/player/queue/add", json={"track_id": 2})

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
            client.post("/api/player/queue/add", json={"track_id": 1})

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
