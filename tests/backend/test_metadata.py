"""
Tests for metadata editing endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the metadata router endpoints for editing track metadata.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import os
import sys
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def mock_track():
    """Create a mock track object"""
    track = Mock()
    track.id = 1
    track.filepath = "/path/to/test.mp3"
    track.format = "mp3"
    track.title = "Test Track"
    track.artist = "Test Artist"
    track.album = "Test Album"
    track.year = 2024
    track.genre = "Rock"
    track.track = 1
    track.disc = 1
    return track


@pytest.fixture(autouse=True)
def patch_track_repository(mock_track):
    """Auto-patch TrackRepository for all tests in this module"""
    with patch('auralis.library.repositories.TrackRepository') as MockTrackRepo:
        repo_instance = Mock()
        repo_instance.get_by_id.return_value = mock_track
        MockTrackRepo.return_value = repo_instance
        yield MockTrackRepo


@pytest.fixture
def mock_library_manager():
    """Create a mock library manager"""
    manager = Mock()
    manager.session = Mock()
    manager.session.commit = Mock()
    manager.session.rollback = Mock()
    return manager


@pytest.fixture
def mock_broadcast_manager():
    """Create a mock broadcast manager"""
    manager = AsyncMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture(scope="function")
def mock_metadata_editor():
    """Create a fresh mock metadata editor for each test"""
    # Create a completely fresh mock for each test
    mock_editor = MagicMock()

    # Set default return values (not side_effects)
    mock_editor.get_editable_fields.return_value = [
        'title', 'artist', 'album', 'year', 'genre', 'track', 'disc'
    ]
    mock_editor.read_metadata.return_value = {
        'title': 'Test Track',
        'artist': 'Test Artist',
        'album': 'Test Album',
        'year': 2024,
        'genre': 'Rock',
        'track': 1,
        'disc': 1
    }
    mock_editor.write_metadata.return_value = True
    mock_editor.batch_update.return_value = {
        'total': 2,
        'successful': 2,
        'failed': 0,
        'results': [
            {'track_id': 1, 'success': True, 'updates': {'title': 'New Title'}},
            {'track_id': 2, 'success': True, 'updates': {'artist': 'New Artist'}}
        ]
    }

    # Clear any side_effects to ensure clean state
    mock_editor.get_editable_fields.side_effect = None
    mock_editor.read_metadata.side_effect = None
    mock_editor.write_metadata.side_effect = None
    mock_editor.batch_update.side_effect = None

    return mock_editor


@pytest.fixture(scope="function", autouse=False)
def client(mock_library_manager, mock_broadcast_manager, mock_metadata_editor):
    """Create test client with mocked dependencies

    IMPORTANT: This fixture creates a NEW router for EACH test.
    This ensures that mock modifications in one test don't affect others.
    """
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from routers.metadata import create_metadata_router

    # Create a fresh app and router for this test
    app = FastAPI()
    router = create_metadata_router(
        get_library_manager=lambda: mock_library_manager,
        broadcast_manager=mock_broadcast_manager,
        metadata_editor=mock_metadata_editor  # Fresh mock for each test
    )
    app.include_router(router)

    client = TestClient(app)
    # Return tuple for unpacking in tests
    return client, mock_broadcast_manager, mock_metadata_editor


class TestGetEditableFields:
    """Tests for GET /api/metadata/tracks/{track_id}/fields"""

    def test_get_editable_fields_success(self, client):
        """Test successfully getting editable fields for a track"""
        test_client, _, mock_editor = client

        response = test_client.get("/api/metadata/tracks/1/fields")

        assert response.status_code == 200
        data = response.json()
        assert data["track_id"] == 1
        assert data["filepath"] == "/path/to/test.mp3"
        assert data["format"] == "mp3"
        assert "title" in data["editable_fields"]
        assert "artist" in data["editable_fields"]
        assert "current_metadata" in data
        assert data["current_metadata"]["title"] == "Test Track"

    def test_get_editable_fields_track_not_found(self, client):
        """Test getting fields for non-existent track"""
        test_client, _, mock_editor = client

        with patch('auralis.library.repositories.TrackRepository') as MockTrackRepo:
            repo_instance = MockTrackRepo.return_value
            repo_instance.get_by_id.return_value = None

            response = test_client.get("/api/metadata/tracks/999/fields")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_editable_fields_file_not_found(self, client):
        """Test getting fields when audio file doesn't exist"""
        test_client, _, mock_editor = client

        mock_editor.get_editable_fields.side_effect = FileNotFoundError("File not found")

        response = test_client.get("/api/metadata/tracks/1/fields")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetTrackMetadata:
    """Tests for GET /api/metadata/tracks/{track_id}"""

    
    def test_get_metadata_success(self, client):
        """Test successfully getting track metadata"""
        test_client, _, mock_editor = client

        response = test_client.get("/api/metadata/tracks/1")

        assert response.status_code == 200
        data = response.json()
        assert data["track_id"] == 1
        assert data["filepath"] == "/path/to/test.mp3"
        assert data["format"] == "mp3"
        assert data["metadata"]["title"] == "Test Track"
        assert data["metadata"]["artist"] == "Test Artist"

    
    def test_get_metadata_track_not_found(self, client):
        """Test getting metadata for non-existent track"""
        test_client, _, mock_editor = client

        with patch('auralis.library.repositories.TrackRepository') as MockTrackRepo:
            repo_instance = MockTrackRepo.return_value
            repo_instance.get_by_id.return_value = None

            response = test_client.get("/api/metadata/tracks/999")

            assert response.status_code == 404


class TestUpdateTrackMetadata:
    """Tests for PUT /api/metadata/tracks/{track_id}"""

    
    def test_update_metadata_success(self, client, mock_library_manager):
        """Test successfully updating track metadata"""
        test_client, broadcast_manager, mock_editor = client

        update_data = {
            "title": "New Title",
            "artist": "New Artist"
        }

        response = test_client.put("/api/metadata/tracks/1", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["track_id"] == 1
        assert "title" in data["updated_fields"]
        assert "artist" in data["updated_fields"]

        # Verify metadata editor was called
        mock_editor.write_metadata.assert_called_once()

        # Verify database commit
        mock_library_manager.session.commit.assert_called_once()

        # Verify WebSocket broadcast
        broadcast_manager.broadcast.assert_called_once()
        broadcast_call = broadcast_manager.broadcast.call_args[0][0]
        assert broadcast_call["type"] == "metadata_updated"
        assert broadcast_call["data"]["track_id"] == 1

    
    def test_update_metadata_with_backup(self, client):
        """Test updating metadata with backup enabled"""
        test_client, _, mock_editor = client

        update_data = {"title": "New Title"}

        response = test_client.put("/api/metadata/tracks/1?backup=true", json=update_data)

        assert response.status_code == 200

        # Verify backup parameter was passed
        call_args = mock_editor.write_metadata.call_args
        assert call_args[1]['backup'] is True

    
    def test_update_metadata_without_backup(self, client):
        """Test updating metadata with backup disabled"""
        test_client, _, mock_editor = client

        update_data = {"title": "New Title"}

        response = test_client.put("/api/metadata/tracks/1?backup=false", json=update_data)

        assert response.status_code == 200

        # Verify backup parameter was passed
        call_args = mock_editor.write_metadata.call_args
        assert call_args[1]['backup'] is False

    
    def test_update_metadata_empty_fields(self, client):
        """Test updating with no fields provided"""
        test_client, _, mock_editor = client

        response = test_client.put("/api/metadata/tracks/1", json={})

        assert response.status_code == 400
        assert "no metadata fields" in response.json()["detail"].lower()

    
    def test_update_metadata_write_failure(self, client, mock_library_manager):
        """Test handling write failure"""
        test_client, _, mock_editor = client

        mock_editor.write_metadata.return_value = False

        update_data = {"title": "New Title"}
        response = test_client.put("/api/metadata/tracks/1", json=update_data)

        assert response.status_code == 500
        assert "failed to write" in response.json()["detail"].lower()

        # Verify rollback was called
        mock_library_manager.session.rollback.assert_called_once()

    
    def test_update_metadata_track_not_found(self, client):
        """Test updating non-existent track"""
        test_client, _, mock_editor = client

        with patch('auralis.library.repositories.TrackRepository') as MockTrackRepo:
            repo_instance = MockTrackRepo.return_value
            repo_instance.get_by_id.return_value = None

            response = test_client.put("/api/metadata/tracks/999", json={"title": "New"})

            assert response.status_code == 404


class TestBatchUpdateMetadata:
    """Tests for POST /api/metadata/batch"""

    
    def test_batch_update_success(self, client, mock_library_manager):
        """Test successful batch update"""
        test_client, broadcast_manager, mock_editor = client

        # Create mock tracks
        track1 = Mock(id=1, filepath="/path/to/test1.mp3", title="Track 1")
        track2 = Mock(id=2, filepath="/path/to/test2.mp3", title="Track 2")

        with patch('auralis.library.repositories.TrackRepository') as MockTrackRepo:
            repo_instance = MockTrackRepo.return_value
            repo_instance.get_by_id.side_effect = lambda track_id: track1 if track_id == 1 else track2

            batch_request = {
                "updates": [
                    {"track_id": 1, "metadata": {"title": "New Title 1"}},
                    {"track_id": 2, "metadata": {"artist": "New Artist 2"}}
                ],
                "backup": True
            }

            response = test_client.post("/api/metadata/batch", json=batch_request)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["total"] == 2
            assert data["successful"] == 2
            assert data["failed"] == 0

            # Verify batch update was called
            mock_editor.batch_update.assert_called_once()

            # Verify database commit
            mock_library_manager.session.commit.assert_called_once()

            # Verify WebSocket broadcast
            broadcast_manager.broadcast.assert_called_once()
            broadcast_call = broadcast_manager.broadcast.call_args[0][0]
            assert broadcast_call["type"] == "metadata_batch_updated"
            assert len(broadcast_call["data"]["track_ids"]) == 2

    
    def test_batch_update_empty_list(self, client):
        """Test batch update with empty list"""
        test_client, _, mock_editor = client

        batch_request = {
            "updates": [],
            "backup": True
        }

        response = test_client.post("/api/metadata/batch", json=batch_request)

        assert response.status_code == 400
        assert "no updates" in response.json()["detail"].lower()

    
    def test_batch_update_partial_success(self, client):
        """Test batch update with some failures"""
        test_client, _, mock_editor = client

        # Mock batch_update to return partial success
        mock_editor.batch_update.return_value = {
            'total': 2,
            'successful': 1,
            'failed': 1,
            'results': [
                {'track_id': 1, 'success': True, 'updates': {'title': 'New Title'}},
                {'track_id': 2, 'success': False, 'error': 'File not found'}
            ]
        }

        track1 = Mock(id=1, filepath="/path/to/test1.mp3")

        with patch('auralis.library.repositories.TrackRepository') as MockTrackRepo:
            repo_instance = MockTrackRepo.return_value
            repo_instance.get_by_id.side_effect = lambda track_id: track1 if track_id == 1 else None

            batch_request = {
                "updates": [
                    {"track_id": 1, "metadata": {"title": "New Title"}},
                    {"track_id": 2, "metadata": {"title": "New Title"}}
                ]
            }

            response = test_client.post("/api/metadata/batch", json=batch_request)

            assert response.status_code == 200
            data = response.json()
            assert data["successful"] == 1
            assert data["failed"] == 1

    
    def test_batch_update_exception_handling(self, client, mock_library_manager):
        """Test batch update error handling"""
        test_client, _, mock_editor = client

        mock_editor.batch_update.side_effect = Exception("Batch update failed")

        batch_request = {
            "updates": [
                {"track_id": 1, "metadata": {"title": "New"}}
            ]
        }

        response = test_client.post("/api/metadata/batch", json=batch_request)

        assert response.status_code == 500
        assert "batch update failed" in response.json()["detail"].lower()

        # Verify rollback was called
        mock_library_manager.session.rollback.assert_called_once()


class TestMetadataValidation:
    """Tests for metadata validation"""

    
    def test_invalid_field_name(self, client):
        """Test updating with invalid field name"""
        test_client, _, mock_editor = client

        # Extra fields should be rejected by Pydantic with extra="forbid"
        update_data = {
            "title": "Valid",
            "invalid_field": "Should be rejected"
        }

        response = test_client.put("/api/metadata/tracks/1", json=update_data)

        # Pydantic should reject this with 422 Unprocessable Entity
        assert response.status_code == 422

    
    def test_year_type_validation(self, client):
        """Test year field type validation"""
        test_client, _, mock_editor = client

        update_data = {
            "year": "not a number"  # Should fail validation
        }

        response = test_client.put("/api/metadata/tracks/1", json=update_data)

        # Pydantic should reject this
        assert response.status_code == 422

    
    def test_multiple_fields_update(self, client):
        """Test updating multiple fields at once"""
        test_client, _, mock_editor = client

        update_data = {
            "title": "New Title",
            "artist": "New Artist",
            "album": "New Album",
            "year": 2024,
            "genre": "Pop"
        }

        response = test_client.put("/api/metadata/tracks/1", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert len(data["updated_fields"]) == 5


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
        assert hasattr(mock_library_manager, 'tracks')
        assert hasattr(mock_library_manager.tracks, 'get_all')
        assert hasattr(mock_library_manager.tracks, 'get_by_id')

    def test_mock_repository_factory_fixture_interface(self, mock_repository_factory):
        """Test that mock_repository_factory has required interface."""
        assert hasattr(mock_repository_factory, 'tracks')
        assert hasattr(mock_repository_factory.tracks, 'get_all')
        assert hasattr(mock_repository_factory.tracks, 'get_by_id')

    def test_dual_mode_interface_equivalence(self, mock_library_manager, mock_repository_factory):
        """Test that both mocks implement equivalent interfaces."""
        from unittest.mock import Mock
        
        # Create test data
        item = Mock()
        item.id = 1
        item.name = "Test"

        # Test LibraryManager pattern
        mock_library_manager.tracks.get_by_id = Mock(return_value=item)
        lib_result = mock_library_manager.tracks.get_by_id(1)
        assert lib_result.id == 1

        # Test RepositoryFactory pattern
        mock_repository_factory.tracks.get_by_id = Mock(return_value=item)
        repo_result = mock_repository_factory.tracks.get_by_id(1)
        assert repo_result.id == 1

        # Both should return same result
        assert lib_result.name == repo_result.name
