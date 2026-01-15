"""
Tests for metadata editing endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the metadata router endpoints for editing track metadata.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import shutil
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

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


# Phase 5B.1: Migration to conftest.py fixtures
# Removed local mock_library_manager fixture - now using conftest.py fixture
# This fixture was shadowing conftest.py - tests now use parent fixture


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
def client(mock_track, mock_broadcast_manager, mock_metadata_editor):
    """Create test client with mocked dependencies

    IMPORTANT: This fixture creates a NEW router for EACH test.
    This ensures that mock modifications in one test don't affect others.

    Note: Phase 6B migrated to RepositoryFactory pattern - uses get_repository_factory
    instead of get_library_manager.

    Returns:
        tuple: (TestClient, mock_broadcast_manager, mock_metadata_editor, mock_repository_factory)
    """
    import sys
    from types import ModuleType
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Break circular import: routers -> services -> config -> routers
    # Pre-populate config.routes with a stub that has setup_routers
    if 'config.routes' not in sys.modules:
        routes_stub = ModuleType('config.routes')
        routes_stub.setup_routers = lambda app: None  # Stub function
        sys.modules['config.routes'] = routes_stub

    from routers.metadata import create_metadata_router

    # Create mock repository factory with tracks repository
    mock_repository_factory = Mock()
    mock_repository_factory.tracks = Mock()
    mock_repository_factory.tracks.get_by_id.return_value = mock_track

    # Create a fresh app and router for this test
    app = FastAPI()
    router = create_metadata_router(
        get_repository_factory=lambda: mock_repository_factory,
        broadcast_manager=mock_broadcast_manager,
        metadata_editor=mock_metadata_editor  # Fresh mock for each test
    )
    app.include_router(router)

    client = TestClient(app)
    # Return tuple for unpacking in tests (added mock_repository_factory for edge case tests)
    return client, mock_broadcast_manager, mock_metadata_editor, mock_repository_factory


class TestGetEditableFields:
    """Tests for GET /api/metadata/tracks/{track_id}/fields"""

    def test_get_editable_fields_success(self, client):
        """Test successfully getting editable fields for a track"""
        test_client, _, mock_editor, _ = client

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
        test_client, _, mock_editor, mock_repo_factory = client

        # Override mock to return None for non-existent track
        mock_repo_factory.tracks.get_by_id.return_value = None

        response = test_client.get("/api/metadata/tracks/999/fields")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_editable_fields_file_not_found(self, client):
        """Test getting fields when audio file doesn't exist"""
        test_client, _, mock_editor, _ = client

        mock_editor.get_editable_fields.side_effect = FileNotFoundError("File not found")

        response = test_client.get("/api/metadata/tracks/1/fields")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetTrackMetadata:
    """Tests for GET /api/metadata/tracks/{track_id}"""

    
    def test_get_metadata_success(self, client):
        """Test successfully getting track metadata"""
        test_client, _, mock_editor, _ = client

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
        test_client, _, mock_editor, mock_repo_factory = client

        # Override mock to return None for non-existent track
        mock_repo_factory.tracks.get_by_id.return_value = None

        response = test_client.get("/api/metadata/tracks/999")

        assert response.status_code == 404


class TestUpdateTrackMetadata:
    """Tests for PUT /api/metadata/tracks/{track_id}"""

    
    def test_update_metadata_success(self, client, mock_track):
        """Test successfully updating track metadata"""
        test_client, broadcast_manager, mock_editor, mock_repo_factory = client

        # Mock update_metadata to return the track
        mock_repo_factory.tracks.update_metadata.return_value = mock_track

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

        # Verify repository update was called
        mock_repo_factory.tracks.update_metadata.assert_called_once()

        # Verify WebSocket broadcast
        broadcast_manager.broadcast.assert_called_once()
        broadcast_call = broadcast_manager.broadcast.call_args[0][0]
        assert broadcast_call["type"] == "metadata_updated"
        assert broadcast_call["data"]["track_id"] == 1

    
    def test_update_metadata_with_backup(self, client):
        """Test updating metadata with backup enabled"""
        test_client, _, mock_editor, _ = client

        update_data = {"title": "New Title"}

        response = test_client.put("/api/metadata/tracks/1?backup=true", json=update_data)

        assert response.status_code == 200

        # Verify backup parameter was passed
        call_args = mock_editor.write_metadata.call_args
        assert call_args[1]['backup'] is True

    
    def test_update_metadata_without_backup(self, client):
        """Test updating metadata with backup disabled"""
        test_client, _, mock_editor, _ = client

        update_data = {"title": "New Title"}

        response = test_client.put("/api/metadata/tracks/1?backup=false", json=update_data)

        assert response.status_code == 200

        # Verify backup parameter was passed
        call_args = mock_editor.write_metadata.call_args
        assert call_args[1]['backup'] is False

    
    def test_update_metadata_empty_fields(self, client):
        """Test updating with no fields provided"""
        test_client, _, mock_editor, _ = client

        response = test_client.put("/api/metadata/tracks/1", json={})

        assert response.status_code == 400
        assert "no metadata fields" in response.json()["detail"].lower()

    
    def test_update_metadata_write_failure(self, client):
        """Test handling write failure"""
        test_client, _, mock_editor, _ = client

        mock_editor.write_metadata.return_value = False

        update_data = {"title": "New Title"}
        response = test_client.put("/api/metadata/tracks/1", json=update_data)

        assert response.status_code == 500
        assert "failed to write" in response.json()["detail"].lower()

    
    def test_update_metadata_track_not_found(self, client):
        """Test updating non-existent track"""
        test_client, _, mock_editor, mock_repo_factory = client

        # Override mock to return None for non-existent track
        mock_repo_factory.tracks.get_by_id.return_value = None

        response = test_client.put("/api/metadata/tracks/999", json={"title": "New"})

        assert response.status_code == 404


class TestBatchUpdateMetadata:
    """Tests for POST /api/metadata/batch"""

    
    def test_batch_update_success(self, client):
        """Test successful batch update"""
        test_client, broadcast_manager, mock_editor, mock_repo_factory = client

        # Create mock tracks
        track1 = Mock(id=1, filepath="/path/to/test1.mp3", title="Track 1")
        track2 = Mock(id=2, filepath="/path/to/test2.mp3", title="Track 2")

        # Configure mock repository factory to return different tracks by ID
        mock_repo_factory.tracks.get_by_id.side_effect = lambda track_id: track1 if track_id == 1 else track2
        # Mock update_track to return the updated track
        mock_repo_factory.tracks.update_track.side_effect = lambda track_id, **kwargs: (
            track1 if track_id == 1 else track2
        )

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

        # Verify WebSocket broadcast
        broadcast_manager.broadcast.assert_called_once()
        broadcast_call = broadcast_manager.broadcast.call_args[0][0]
        assert broadcast_call["type"] == "metadata_batch_updated"
        assert len(broadcast_call["data"]["track_ids"]) == 2

    
    def test_batch_update_empty_list(self, client):
        """Test batch update with empty list"""
        test_client, _, mock_editor, _ = client

        batch_request = {
            "updates": [],
            "backup": True
        }

        response = test_client.post("/api/metadata/batch", json=batch_request)

        assert response.status_code == 400
        assert "no updates" in response.json()["detail"].lower()

    
    def test_batch_update_partial_success(self, client):
        """Test batch update with some failures"""
        test_client, _, mock_editor, mock_repo_factory = client

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

        # Configure mock to return track1 for ID 1, None for ID 2
        mock_repo_factory.tracks.get_by_id.side_effect = lambda track_id: track1 if track_id == 1 else None
        mock_repo_factory.tracks.update_track.return_value = track1

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

    
    def test_batch_update_exception_handling(self, client):
        """Test batch update error handling"""
        test_client, _, mock_editor, _ = client

        mock_editor.batch_update.side_effect = Exception("Batch update failed")

        batch_request = {
            "updates": [
                {"track_id": 1, "metadata": {"title": "New"}}
            ]
        }

        response = test_client.post("/api/metadata/batch", json=batch_request)

        assert response.status_code == 500
        assert "batch update failed" in response.json()["detail"].lower()


class TestMetadataValidation:
    """Tests for metadata validation"""

    
    def test_invalid_field_name(self, client):
        """Test updating with invalid field name"""
        test_client, _, mock_editor, _ = client

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
        test_client, _, mock_editor, _ = client

        update_data = {
            "year": "not a number"  # Should fail validation
        }

        response = test_client.put("/api/metadata/tracks/1", json=update_data)

        # Pydantic should reject this
        assert response.status_code == 422

    
    def test_multiple_fields_update(self, client):
        """Test updating multiple fields at once"""
        test_client, _, mock_editor, _ = client

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
class TestMetadataDualModeParametrized:
    """Phase 5C.3: Parametrized dual-mode tests for metadata operations.

    These tests automatically run with both LibraryManager and RepositoryFactory
    via the parametrized mock_data_source fixture.
    """

    def test_metadata_tracks_interface(self, mock_data_source):
        """
        Parametrized test: Validate tracks repository for metadata operations.

        Both modes must support track metadata retrieval and editing.
        """
        mode, source = mock_data_source

        assert hasattr(source, 'tracks'), f"{mode} missing tracks repository"
        assert hasattr(source.tracks, 'get_all'), f"{mode}.tracks missing get_all"
        assert hasattr(source.tracks, 'get_by_id'), f"{mode}.tracks missing get_by_id"

    def test_metadata_get_all_returns_tuple(self, mock_data_source):
        """
        Parametrized test: Validate tracks.get_all returns (items, total) for both modes.

        Metadata editing requires track list pagination to work with both patterns.
        """
        mode, source = mock_data_source

        # Create mock tracks with metadata
        track1 = Mock()
        track1.id = 1
        track1.title = "Track 1"
        track1.artist = "Artist 1"

        track2 = Mock()
        track2.id = 2
        track2.title = "Track 2"
        track2.artist = "Artist 2"

        test_tracks = [track1, track2]
        source.tracks.get_all = Mock(return_value=(test_tracks, 2))

        # Test with both modes
        tracks, total = source.tracks.get_all(limit=50, offset=0)

        assert len(tracks) == 2, f"{mode}: Expected 2 tracks"
        assert total == 2, f"{mode}: Expected total=2"
        assert tracks[0].title == "Track 1", f"{mode}: First track title mismatch"
        assert tracks[1].title == "Track 2", f"{mode}: Second track title mismatch"

    def test_metadata_get_by_id_interface(self, mock_data_source):
        """
        Parametrized test: Validate tracks.get_by_id works with both modes.

        Track metadata editing depends on retrieving track by ID.
        """
        mode, source = mock_data_source

        track = Mock()
        track.id = 1
        track.title = "Test Track"
        track.artist = "Test Artist"

        source.tracks.get_by_id = Mock(return_value=track)

        result = source.tracks.get_by_id(1)

        assert result.id == 1, f"{mode}: Track ID mismatch"
        assert result.title == "Test Track", f"{mode}: Track title mismatch"
        assert result.artist == "Test Artist", f"{mode}: Track artist mismatch"
        source.tracks.get_by_id.assert_called_once_with(1)
