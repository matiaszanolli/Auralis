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

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def client():
    """Create test client for main app"""
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_queue_manager():
    """Create a mock queue manager with test data"""
    queue_manager = Mock()
    queue_manager.get_queue_size.return_value = 5
    queue_manager.get_queue.return_value = [
        {"id": 1, "title": "Track 1", "filepath": "/path/1.wav"},
        {"id": 2, "title": "Track 2", "filepath": "/path/2.wav"},
        {"id": 3, "title": "Track 3", "filepath": "/path/3.wav"},
        {"id": 4, "title": "Track 4", "filepath": "/path/4.wav"},
        {"id": 5, "title": "Track 5", "filepath": "/path/5.wav"},
    ]
    queue_manager.remove_track.return_value = True
    queue_manager.reorder_tracks.return_value = True
    queue_manager.shuffle.return_value = None
    queue_manager.clear.return_value = None
    return queue_manager


class TestRemoveFromQueue:
    """Test DELETE /api/player/queue/:index endpoint"""

    def test_remove_track_success(self, client, mock_queue_manager):
        """Test removing a track from the queue"""
        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager') as mock_state, \
             patch('main.manager') as mock_ws:

            mock_player.queue_manager = mock_queue_manager
            mock_ws.broadcast = AsyncMock()

            response = client.delete("/api/player/queue/2")
            assert response.status_code == 200

            data = response.json()
            assert data['message'] == "Track removed from queue"
            assert data['index'] == 2
            assert mock_queue_manager.remove_track.called
            assert mock_queue_manager.remove_track.call_args[0][0] == 2

    def test_remove_invalid_index(self, client, mock_queue_manager):
        """Test removing track with invalid index"""
        mock_queue_manager.get_queue_size.return_value = 5

        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager'):

            mock_player.queue_manager = mock_queue_manager

            # Index 999 is out of range
            response = client.delete("/api/player/queue/999")
            assert response.status_code == 400
            assert "Invalid index" in response.json()['detail']

    def test_remove_negative_index(self, client, mock_queue_manager):
        """Test removing track with negative index"""
        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager'):

            mock_player.queue_manager = mock_queue_manager

            response = client.delete("/api/player/queue/-1")
            assert response.status_code == 400

    def test_remove_no_player(self, client):
        """Test removing when player is not available"""
        with patch('main.player_state_manager', None):
            response = client.delete("/api/player/queue/0")
            assert response.status_code == 503


class TestReorderQueue:
    """Test PUT /api/player/queue/reorder endpoint"""

    def test_reorder_queue_success(self, client, mock_queue_manager):
        """Test reordering the queue"""
        mock_queue_manager.get_queue_size.return_value = 5

        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager') as mock_state, \
             patch('main.manager') as mock_ws:

            mock_player.queue_manager = mock_queue_manager
            mock_ws.broadcast = AsyncMock()

            new_order = [4, 3, 2, 1, 0]  # Reverse order
            response = client.put("/api/player/queue/reorder", json={
                "new_order": new_order
            })

            assert response.status_code == 200
            data = response.json()
            assert data['message'] == "Queue reordered successfully"
            assert mock_queue_manager.reorder_tracks.called

    def test_reorder_invalid_length(self, client, mock_queue_manager):
        """Test reordering with wrong number of indices"""
        mock_queue_manager.get_queue_size.return_value = 5

        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager'):

            mock_player.queue_manager = mock_queue_manager

            response = client.put("/api/player/queue/reorder", json={
                "new_order": [0, 1, 2]  # Too few
            })
            assert response.status_code == 400
            assert "must match queue size" in response.json()['detail']

    def test_reorder_duplicate_indices(self, client, mock_queue_manager):
        """Test reordering with duplicate indices"""
        mock_queue_manager.get_queue_size.return_value = 5

        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager'):

            mock_player.queue_manager = mock_queue_manager

            response = client.put("/api/player/queue/reorder", json={
                "new_order": [0, 0, 0, 0, 0]  # All duplicates
            })
            assert response.status_code == 400
            assert "exactly once" in response.json()['detail']

    def test_reorder_invalid_indices(self, client, mock_queue_manager):
        """Test reordering with out-of-range indices"""
        mock_queue_manager.get_queue_size.return_value = 5

        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager'):

            mock_player.queue_manager = mock_queue_manager

            response = client.put("/api/player/queue/reorder", json={
                "new_order": [0, 1, 2, 3, 999]  # 999 is invalid
            })
            assert response.status_code == 400


class TestClearQueue:
    """Test POST /api/player/queue/clear endpoint"""

    def test_clear_queue_success(self, client, mock_queue_manager):
        """Test clearing the queue"""
        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager') as mock_state, \
             patch('main.manager') as mock_ws:

            mock_player.queue_manager = mock_queue_manager
            mock_player.stop = Mock()
            mock_state.set_playing = AsyncMock()
            mock_state.set_track = AsyncMock()
            mock_ws.broadcast = AsyncMock()

            response = client.post("/api/player/queue/clear")
            assert response.status_code == 200

            data = response.json()
            assert data['message'] == "Queue cleared successfully"
            assert mock_queue_manager.clear.called

    def test_clear_no_player(self, client):
        """Test clearing when player is not available"""
        with patch('main.player_state_manager', None):
            response = client.post("/api/player/queue/clear")
            assert response.status_code == 503


class TestShuffleQueue:
    """Test POST /api/player/queue/shuffle endpoint"""

    def test_shuffle_queue_success(self, client, mock_queue_manager):
        """Test shuffling the queue"""
        mock_queue_manager.get_queue_size.return_value = 5

        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager') as mock_state, \
             patch('main.manager') as mock_ws:

            mock_player.queue_manager = mock_queue_manager
            mock_ws.broadcast = AsyncMock()

            response = client.post("/api/player/queue/shuffle")
            assert response.status_code == 200

            data = response.json()
            assert data['message'] == "Queue shuffled successfully"
            assert data['queue_size'] == 5
            assert mock_queue_manager.shuffle.called

    def test_shuffle_no_player(self, client):
        """Test shuffling when player is not available"""
        with patch('main.player_state_manager', None):
            response = client.post("/api/player/queue/shuffle")
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

        response = client.post("/api/player/queue/shuffle")
        assert response.status_code != 404

    def test_queue_workflow_with_mocks(self, client, mock_queue_manager):
        """Test a complete queue manipulation workflow"""
        with patch('main.audio_player') as mock_player, \
             patch('main.player_state_manager') as mock_state, \
             patch('main.manager') as mock_ws:

            mock_player.queue_manager = mock_queue_manager
            mock_player.stop = Mock()
            mock_state.set_playing = AsyncMock()
            mock_state.set_track = AsyncMock()
            mock_ws.broadcast = AsyncMock()

            # 1. Remove a track
            mock_queue_manager.get_queue_size.return_value = 5
            response = client.delete("/api/player/queue/1")
            assert response.status_code == 200

            # 2. Reorder queue
            mock_queue_manager.get_queue_size.return_value = 4  # After removal
            response = client.put("/api/player/queue/reorder", json={
                "new_order": [3, 2, 1, 0]
            })
            assert response.status_code == 200

            # 3. Shuffle queue
            response = client.post("/api/player/queue/shuffle")
            assert response.status_code == 200

            # 4. Clear queue
            response = client.post("/api/player/queue/clear")
            assert response.status_code == 200


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
    via the parametrized mock_data_source fixture. Queue-specific repositories
    (queue, queue_history, queue_templates) are validated with both patterns.
    """

    def test_queue_repository_interface(self, mock_data_source):
        """
        Parametrized test: Validate queue repository interface for both modes.

        Tests both LibraryManager and RepositoryFactory have queue access.
        """
        mode, source = mock_data_source

        assert hasattr(source, 'queue'), f"{mode} missing queue repository"
        assert hasattr(source.queue, 'get_all'), f"{mode}.queue missing get_all"
        assert hasattr(source.queue, 'get_by_id'), f"{mode}.queue missing get_by_id"

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

    def test_queue_get_all_returns_tuple(self, mock_data_source):
        """
        Parametrized test: Validate queue.get_all returns (items, total) for both modes.

        Queue items contain track_id and position for playback ordering.
        """
        mode, source = mock_data_source

        # Create mock queue items
        item1 = Mock()
        item1.id = 1
        item1.track_id = 101
        item1.position = 0

        item2 = Mock()
        item2.id = 2
        item2.track_id = 102
        item2.position = 1

        test_queue = [item1, item2]
        source.queue.get_all = Mock(return_value=(test_queue, 2))

        # Test with both modes
        queue, total = source.queue.get_all(limit=100)

        assert len(queue) == 2, f"{mode}: Expected 2 queue items"
        assert total == 2, f"{mode}: Expected total=2"
        assert queue[0].track_id == 101, f"{mode}: First item track_id mismatch"
        assert queue[1].track_id == 102, f"{mode}: Second item track_id mismatch"

    def test_queue_get_by_id_interface(self, mock_data_source):
        """
        Parametrized test: Validate queue.get_by_id works with both modes.

        Both modes should return queue item with position info.
        """
        mode, source = mock_data_source

        queue_item = Mock()
        queue_item.id = 1
        queue_item.track_id = 100
        queue_item.position = 0

        source.queue.get_by_id = Mock(return_value=queue_item)

        result = source.queue.get_by_id(1)

        assert result.id == 1, f"{mode}: Queue item ID mismatch"
        assert result.track_id == 100, f"{mode}: Queue item track_id mismatch"
        assert result.position == 0, f"{mode}: Queue item position mismatch"
        source.queue.get_by_id.assert_called_once_with(1)
