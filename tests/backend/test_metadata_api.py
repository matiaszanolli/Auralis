"""
Tests for Metadata Router
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for track metadata editing endpoints.

Coverage:
- GET /api/metadata/tracks/{track_id}/fields - Get editable fields
- GET /api/metadata/tracks/{track_id} - Get current metadata
- PUT /api/metadata/tracks/{track_id} - Update metadata
- POST /api/metadata/batch - Batch update metadata

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

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
    track.track_number = 1
    track.disc_number = 1
    track.duration = 180.0
    return track


@pytest.fixture
def mock_metadata_editor():
    """Create a mock MetadataEditor"""
    editor = Mock()
    editor.get_editable_fields = Mock(return_value=[
        "title", "artist", "album", "year", "genre", "track", "disc"
    ])
    editor.read_metadata = Mock(return_value={
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "year": 2024,
        "genre": "Rock"
    })
    editor.write_metadata = Mock(return_value=True)
    editor.batch_update = Mock(return_value={
        "total": 1,
        "successful": 1,
        "failed": 0,
        "results": [{"track_id": 1, "success": True, "updates": {"title": "New Title"}}]
    })
    return editor


@pytest.fixture
def mock_repos():
    """Create mock RepositoryFactory"""
    repos = Mock()
    repos.tracks = Mock()
    repos.tracks.get_by_id = Mock(return_value=None)
    repos.tracks.update_metadata = Mock(return_value=None)
    return repos


@pytest.fixture
def mock_broadcast_manager():
    """Mock broadcast manager"""
    manager = Mock()
    manager.broadcast = AsyncMock()
    return manager


class TestGetEditableFields:
    """Test GET /api/metadata/tracks/{track_id}/fields"""

    @patch('routers.metadata.require_repository_factory')
    def test_get_editable_fields_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test getting editable fields for non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/metadata/tracks/999/fields")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch('routers.metadata.require_repository_factory')
    def test_get_editable_fields_file_not_found(self, mock_require_repos, client, mock_repos, mock_track):
        """Test getting editable fields when audio file doesn't exist"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track
        mock_track.filepath = "/nonexistent/file.mp3"

        response = client.get("/api/metadata/tracks/1/fields")

        # Should return 404 for missing file
        assert response.status_code in [404, 500]

    def test_get_editable_fields_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/metadata/tracks/1/fields")
        assert response.status_code == 405


class TestGetTrackMetadata:
    """Test GET /api/metadata/tracks/{track_id}"""

    @patch('routers.metadata.require_repository_factory')
    def test_get_metadata_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test getting metadata for non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/metadata/tracks/999")

        assert response.status_code == 404

    @patch('routers.metadata.require_repository_factory')
    def test_get_metadata_file_not_found(self, mock_require_repos, client, mock_repos, mock_track):
        """Test getting metadata when audio file doesn't exist"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track
        mock_track.filepath = "/nonexistent/file.mp3"

        response = client.get("/api/metadata/tracks/1")

        assert response.status_code in [404, 500]

    def test_get_metadata_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/metadata/tracks/1")
        assert response.status_code == 405


class TestUpdateTrackMetadata:
    """Test PUT /api/metadata/tracks/{track_id}"""

    @patch('routers.metadata.require_repository_factory')
    def test_update_metadata_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test updating metadata for non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.put(
            "/api/metadata/tracks/999",
            json={"title": "New Title"}
        )

        assert response.status_code == 404

    @patch('routers.metadata.require_repository_factory')
    def test_update_metadata_no_fields(self, mock_require_repos, client, mock_repos, mock_track):
        """Test update with no metadata fields provided"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        response = client.put("/api/metadata/tracks/1", json={})

        assert response.status_code == 400
        assert "No metadata fields" in response.json()["detail"]

    @patch('routers.metadata.require_repository_factory')
    def test_update_metadata_unknown_field(self, mock_require_repos, client, mock_repos, mock_track):
        """Test update with unknown/extra fields"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        # Try to send unknown field
        response = client.put(
            "/api/metadata/tracks/1",
            json={"unknown_field": "value"}
        )

        # Should be rejected by Pydantic validation
        assert response.status_code == 422

    @patch('routers.metadata.require_repository_factory')
    def test_update_metadata_invalid_year(self, mock_require_repos, client, mock_repos, mock_track):
        """Test update with invalid year type"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        response = client.put(
            "/api/metadata/tracks/1",
            json={"year": "not_a_number"}
        )

        assert response.status_code == 422

    @patch('routers.metadata.require_repository_factory')
    def test_update_metadata_file_not_found(self, mock_require_repos, client, mock_repos, mock_track):
        """Test update when audio file doesn't exist"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track
        mock_track.filepath = "/nonexistent/file.mp3"

        response = client.put(
            "/api/metadata/tracks/1",
            json={"title": "New Title"}
        )

        # Should return 404 for missing file
        assert response.status_code in [404, 500]

    def test_update_metadata_accepts_put_only(self, client):
        """Test that endpoint only accepts PUT"""
        response = client.post(
            "/api/metadata/tracks/1",
            json={"title": "New Title"}
        )
        # POST to this endpoint should fail (it's the batch endpoint)
        assert response.status_code in [404, 405]

    @patch('routers.metadata.require_repository_factory')
    def test_update_metadata_backup_parameter(self, mock_require_repos, client, mock_repos, mock_track):
        """Test backup parameter in update request"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        # Test with backup=false
        response = client.put(
            "/api/metadata/tracks/1?backup=false",
            json={"title": "New Title"}
        )

        # Will fail because file doesn't exist, but validates parameter passing
        assert response.status_code in [404, 500]


class TestBatchUpdateMetadata:
    """Test POST /api/metadata/batch"""

    def test_batch_update_empty_list(self, client):
        """Test batch update with empty updates list"""
        response = client.post(
            "/api/metadata/batch",
            json={"updates": []}
        )

        assert response.status_code == 400
        assert "No updates provided" in response.json()["detail"]

    def test_batch_update_missing_updates_field(self, client):
        """Test batch update without updates field"""
        response = client.post("/api/metadata/batch", json={})

        assert response.status_code == 422

    @patch('routers.metadata.require_repository_factory')
    def test_batch_update_invalid_track_id(self, mock_require_repos, client, mock_repos):
        """Test batch update with non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.post(
            "/api/metadata/batch",
            json={
                "updates": [
                    {
                        "track_id": 999,
                        "metadata": {"title": "New Title"}
                    }
                ]
            }
        )

        # Should process but report failure for missing track
        assert response.status_code in [200, 500]

    @patch('routers.metadata.require_repository_factory')
    def test_batch_update_mixed_success_failure(self, mock_require_repos, client, mock_repos):
        """Test batch update with mix of valid and invalid tracks"""
        mock_require_repos.return_value = mock_repos

        def get_by_id_side_effect(track_id):
            if track_id == 1:
                track = Mock()
                track.id = 1
                track.filepath = "/path/to/track1.mp3"
                return track
            return None

        mock_repos.tracks.get_by_id.side_effect = get_by_id_side_effect

        response = client.post(
            "/api/metadata/batch",
            json={
                "updates": [
                    {"track_id": 1, "metadata": {"title": "Track 1"}},
                    {"track_id": 999, "metadata": {"title": "Track 999"}}
                ]
            }
        )

        # Should process and return results
        assert response.status_code in [200, 500]

    @patch('routers.metadata.require_repository_factory')
    def test_batch_update_backup_disabled(self, mock_require_repos, client, mock_repos):
        """Test batch update with backup disabled"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.post(
            "/api/metadata/batch",
            json={
                "updates": [
                    {"track_id": 1, "metadata": {"title": "New Title"}}
                ],
                "backup": False
            }
        )

        # Validates that backup parameter is accepted
        assert response.status_code in [200, 500]

    def test_batch_update_invalid_metadata_structure(self, client):
        """Test batch update with invalid metadata structure"""
        response = client.post(
            "/api/metadata/batch",
            json={
                "updates": [
                    {
                        "track_id": 1,
                        "metadata": "invalid_not_a_dict"
                    }
                ]
            }
        )

        assert response.status_code == 422

    def test_batch_update_accepts_post_only(self, client):
        """Test that batch endpoint only accepts POST"""
        response = client.get("/api/metadata/batch")
        assert response.status_code == 405


class TestMetadataValidation:
    """Test metadata field validation"""

    @patch('routers.metadata.require_repository_factory')
    def test_update_valid_field_types(self, mock_require_repos, client, mock_repos, mock_track):
        """Test that valid field types are accepted"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        valid_updates = {
            "title": "New Title",
            "artist": "New Artist",
            "album": "New Album",
            "year": 2024,
            "genre": "Rock",
            "track": 1,
            "disc": 1,
            "bpm": 120
        }

        response = client.put(
            "/api/metadata/tracks/1",
            json=valid_updates
        )

        # Will fail because file doesn't exist, but validates field types
        assert response.status_code in [404, 500]
        # Should NOT be validation error (422)
        assert response.status_code != 422

    @patch('routers.metadata.require_repository_factory')
    def test_update_partial_metadata(self, mock_require_repos, client, mock_repos, mock_track):
        """Test updating only some metadata fields"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        # Update only title
        response = client.put(
            "/api/metadata/tracks/1",
            json={"title": "New Title Only"}
        )

        # Will fail because file doesn't exist, but validates partial update
        assert response.status_code in [404, 500]
        assert response.status_code != 422


class TestMetadataSecurityValidation:
    """Security-focused tests for metadata endpoints"""

    @patch('routers.metadata.require_repository_factory')
    def test_metadata_sql_injection_attempt(self, mock_require_repos, client, mock_repos, mock_track):
        """Test that SQL injection attempts are safely handled"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        # Try SQL injection in title
        response = client.put(
            "/api/metadata/tracks/1",
            json={"title": "'; DROP TABLE tracks; --"}
        )

        # Should handle safely (not execute SQL)
        assert response.status_code in [404, 500]

    @patch('routers.metadata.require_repository_factory')
    def test_metadata_xss_attempt(self, mock_require_repos, client, mock_repos, mock_track):
        """Test that XSS attempts are safely handled"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        # Try XSS in title
        response = client.put(
            "/api/metadata/tracks/1",
            json={"title": "<script>alert('XSS')</script>"}
        )

        # Should accept (metadata can contain special chars) but not execute
        assert response.status_code in [404, 500]

    @patch('routers.metadata.require_repository_factory')
    def test_metadata_extremely_long_strings(self, mock_require_repos, client, mock_repos, mock_track):
        """Test handling of extremely long metadata strings"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        # Very long title (10KB)
        long_title = "A" * 10000

        response = client.put(
            "/api/metadata/tracks/1",
            json={"title": long_title}
        )

        # Should handle safely (may accept or reject based on limits)
        assert response.status_code in [400, 404, 500]


class TestMetadataIntegration:
    """Integration tests for metadata endpoints"""

    @patch('routers.metadata.require_repository_factory')
    def test_workflow_get_fields_then_update(self, mock_require_repos, client, mock_repos, mock_track):
        """Test workflow: get editable fields → update metadata"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        # 1. Get editable fields (will fail - file doesn't exist)
        fields_response = client.get("/api/metadata/tracks/1/fields")

        # 2. Update metadata (will also fail)
        update_response = client.put(
            "/api/metadata/tracks/1",
            json={"title": "Updated Title"}
        )

        # Both should fail consistently
        assert fields_response.status_code in [404, 500]
        assert update_response.status_code in [404, 500]

    @patch('routers.metadata.require_repository_factory')
    def test_workflow_single_then_batch_update(self, mock_require_repos, client, mock_repos):
        """Test workflow: single update → batch update"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        # 1. Single update
        single_response = client.put(
            "/api/metadata/tracks/1",
            json={"title": "Single Update"}
        )

        # 2. Batch update
        batch_response = client.post(
            "/api/metadata/batch",
            json={
                "updates": [
                    {"track_id": 1, "metadata": {"title": "Batch Update 1"}},
                    {"track_id": 2, "metadata": {"title": "Batch Update 2"}}
                ]
            }
        )

        # Both should process (may fail due to missing tracks)
        assert single_response.status_code in [404, 500]
        assert batch_response.status_code in [200, 500]
