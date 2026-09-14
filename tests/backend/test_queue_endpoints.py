"""
Test Queue Management API Endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for queue manipulation endpoints:
- DELETE /api/player/queue/:index - Remove track
- PUT /api/player/queue/reorder - Reorder queue
- POST /api/player/queue/clear - Clear queue
- POST /api/player/queue/shuffle - Shuffle queue

Phase 5C: Dual-Mode Backend Testing
This file demonstrates Phase 5C patterns:
1. Using mock fixtures from conftest.py
2. Parametrized dual-mode testing (LibraryManager + RepositoryFactory)
3. Queue-specific interface validation
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from auralis.player.components.queue_manager import QueueManager

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def client():
    """Create test client for main app.

    Shadows the shared conftest `client` fixture deliberately: this one skips
    the lifespan, which would run real startup against the developer's actual
    ~/.auralis/library.db. It must therefore repeat the conftest fixture's
    #5089 Origin header itself -- OriginCheckMiddleware rejects every
    state-changing /api request carrying an empty Origin from TestClient's
    non-loopback 'testclient' host, which silently turned 13 queue assertions
    into 403 checks. Port 8765 is allowlisted in both dev and prod (#4781).
    """
    from main import app
    return TestClient(app, headers={"origin": "http://localhost:8765"})


@pytest.fixture
def queue_manager():
    """Create the real queue component consumed by QueueService (#5175)."""
    manager = QueueManager()
    manager.tracks = [
        {"id": 1, "title": "Track 1", "filepath": "/path/1.wav"},
        {"id": 2, "title": "Track 2", "filepath": "/path/2.wav"},
        {"id": 3, "title": "Track 3", "filepath": "/path/3.wav"},
        {"id": 4, "title": "Track 4", "filepath": "/path/4.wav"},
        {"id": 5, "title": "Track 5", "filepath": "/path/5.wav"},
    ]
    manager.current_index = 0
    return manager


class TestRemoveFromQueue:
    """Test DELETE /api/player/queue/:index endpoint"""

    def test_remove_track_success(self, client, queue_manager):
        """Test removing a track from the queue"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }), patch('main.manager', mock_ws):

            response = client.delete("/api/player/queue/2")
            assert response.status_code == 200

            data = response.json()
            assert data['message'] == "Track removed from queue"
            assert data['index'] == 2
            assert queue_manager.get_queue_size() == 4
            assert [track["id"] for track in queue_manager.get_queue()] == [1, 2, 4, 5]

    def test_remove_invalid_index(self, client, queue_manager):
        """Test removing track with invalid index"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }):
            # Index 999 is out of range
            response = client.delete("/api/player/queue/999")
            assert response.status_code == 400
            assert "Invalid index" in response.json()['detail']

    def test_remove_negative_index(self, client, queue_manager):
        """A negative index is rejected at the path-validation boundary
        (Path(..., ge=0), #3893) rather than reaching the handler's own
        out-of-range check — 422, not the handler's 400."""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }):
            response = client.delete("/api/player/queue/-1")
            assert response.status_code == 422

    def test_remove_no_player(self, client):
        """Test removing when player is not available"""
        with patch.dict('main.globals_dict', {'audio_player': None}):
            response = client.delete("/api/player/queue/0")
            assert response.status_code == 503

    def test_remove_uses_the_atomic_check_not_a_separate_read_and_remove(self, client, queue_manager):
        """#5360 WIRING: remove_track_from_queue must call
        remove_if_index_matches_current(), not a separate current_index
        read followed by a plain remove_track() call — the two-step version
        has a TOCTOU gap a concurrent advance/next/previous could land in."""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        real_atomic = queue_manager.remove_if_index_matches_current
        calls: list[int] = []

        def _spy(index):
            calls.append(index)
            return real_atomic(index)

        queue_manager.remove_if_index_matches_current = _spy
        queue_manager.remove_track = Mock(side_effect=AssertionError(
            "remove_track_from_queue must not call remove_track() directly "
            "— it bypasses the atomic was_current check (#5360)"
        ))

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }), patch('main.manager', mock_ws):
            # Index 0 == queue_manager.current_index (fixture default) — the
            # was_current=True path, which is the one this issue is about.
            response = client.delete("/api/player/queue/0")

        assert response.status_code == 200
        assert calls == [0]
        assert queue_manager.remove_track.call_count == 0


class TestReorderQueue:
    """Test PUT /api/player/queue/reorder endpoint"""

    def test_reorder_queue_success(self, client, queue_manager):
        """Test reordering the queue"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }), patch('main.manager', mock_ws):

            new_order = [4, 3, 2, 1, 0]  # Reverse order
            response = client.put("/api/player/queue/reorder", json={
                "new_order": new_order
            })

            assert response.status_code == 200
            data = response.json()
            assert data['message'] == "Queue reordered successfully"
            assert [track["id"] for track in queue_manager.get_queue()] == [5, 4, 3, 2, 1]

    def test_reorder_invalid_length(self, client, queue_manager):
        """Test reordering with wrong number of indices"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }):
            response = client.put("/api/player/queue/reorder", json={
                "new_order": [0, 1, 2]  # Too few
            })
            assert response.status_code == 400
            assert "must match queue size" in response.json()['detail']

    def test_reorder_duplicate_indices(self, client, queue_manager):
        """Test reordering with duplicate indices"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }):
            response = client.put("/api/player/queue/reorder", json={
                "new_order": [0, 0, 0, 0, 0]  # All duplicates
            })
            assert response.status_code == 400
            assert "exactly once" in response.json()['detail']

    def test_reorder_invalid_indices(self, client, queue_manager):
        """Test reordering with out-of-range indices"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }):
            response = client.put("/api/player/queue/reorder", json={
                "new_order": [0, 1, 2, 3, 999]  # 999 is invalid
            })
            assert response.status_code == 400


class TestClearQueue:
    """Test POST /api/player/queue/clear endpoint"""

    def test_clear_queue_success(self, client, queue_manager):
        """Test clearing the queue"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_player.stop = Mock()
        mock_state = Mock()
        mock_state.set_playing = AsyncMock()
        mock_state.set_track = AsyncMock()
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }), patch('main.manager', mock_ws):

            response = client.post("/api/player/queue/clear")
            assert response.status_code == 200

            data = response.json()
            assert data['message'] == "Queue cleared successfully"
            assert queue_manager.get_queue() == []

    def test_clear_no_player(self, client):
        """Test clearing when player is not available"""
        with patch.dict('main.globals_dict', {'audio_player': None}):
            response = client.post("/api/player/queue/clear")
            assert response.status_code == 503


class TestShuffleQueue:
    """Test POST /api/player/queue/shuffle endpoint"""

    def test_shuffle_queue_success(self, client, queue_manager):
        """Test shuffling the queue"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_state = Mock()
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        with patch.object(
            queue_manager, 'shuffle', wraps=queue_manager.shuffle
        ) as shuffle_spy, patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }), patch('main.manager', mock_ws):

            response = client.post("/api/player/queue/shuffle", json={"enabled": True})
            assert response.status_code == 200

            data = response.json()
            assert data['message'] == "Queue shuffled successfully"
            assert data['queue_size'] == 5
            shuffle_spy.assert_called_once_with()
            assert sorted(track["id"] for track in queue_manager.get_queue()) == [1, 2, 3, 4, 5]

    def test_shuffle_no_player(self, client):
        """Test shuffling when player is not available"""
        with patch.dict('main.globals_dict', {'audio_player': None}):
            response = client.post("/api/player/queue/shuffle", json={"enabled": True})
            assert response.status_code == 503


class TestQueueIntegration:
    """Integration tests for queue manipulation"""

    def test_all_queue_operations_available(self, client):
        """Test that all queue endpoints are registered"""
        # Just verify endpoints exist (they may return 503 if player not initialized)
        # But they should not return 404 (not found)

        response = client.delete("/api/player/queue/0")
        assert response.status_code != 404  # Endpoint exists

        response = client.put("/api/player/queue/reorder", json={"new_order": []})
        assert response.status_code != 404

        response = client.post("/api/player/queue/clear")
        assert response.status_code != 404

        response = client.post("/api/player/queue/shuffle", json={"enabled": True})
        assert response.status_code != 404

    def test_queue_workflow_with_queue_manager(self, client, queue_manager):
        """Test a complete queue manipulation workflow"""
        mock_player = Mock()
        mock_player.queue = queue_manager
        mock_player.stop = Mock()
        mock_state = Mock()
        mock_state.set_playing = AsyncMock()
        mock_state.set_track = AsyncMock()
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state
        }), patch('main.manager', mock_ws):

            # 1. Remove a track
            response = client.delete("/api/player/queue/1")
            assert response.status_code == 200

            # 2. Reorder queue
            response = client.put("/api/player/queue/reorder", json={
                "new_order": [3, 2, 1, 0]
            })
            assert response.status_code == 200

            # 3. Shuffle queue
            response = client.post("/api/player/queue/shuffle", json={"enabled": True})
            assert response.status_code == 200

            # 4. Clear queue
            response = client.post("/api/player/queue/clear")
            assert response.status_code == 200
            assert queue_manager.get_queue() == []


# ============================================================
# Phase 5C: Dual-Mode Backend Testing Patterns
# ============================================================
# The following tests demonstrate how to use Phase 5C fixtures
# from conftest.py for dual-mode parametrized testing with
# queue-specific repository interfaces.

@pytest.mark.phase5c
class TestQueueAPIDualModeParametrized:
    """Phase 5C.3: Parametrized dual-mode tests for queue operations.

    These tests automatically run with both LibraryManager and RepositoryFactory
    via the parametrized mock_data_source fixture. The queue-specific
    repository (queue_history) is validated with both patterns; the caller-less
    QueueRepository and its interface test were deleted in #5358.
    """

    def test_queue_history_repository_interface(self, mock_data_source):
        """
        Parametrized test: Validate queue_history repository for RepositoryFactory mode.

        RepositoryFactory has queue_history; LibraryManager may not.
        Both should have basic repository interface.
        """
        mode, source = mock_data_source

        if mode == "repository_factory":
            assert hasattr(source, 'queue_history'), f"{mode} missing queue_history"
            assert hasattr(source.queue_history, 'get_all'), "queue_history missing get_all"
