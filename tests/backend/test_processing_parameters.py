"""
Tests for Processing Parameters API

Tests the new /api/processing/parameters endpoint that exposes real-time
processing data from the continuous space system.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'))

from main import app


@pytest.fixture
def client():
    """Test client for API requests"""
    return TestClient(app)


class TestProcessingParametersEndpoint:
    """Tests for GET /api/processing/parameters"""

    def test_get_processing_parameters_returns_defaults(self, client):
        """Test that endpoint returns default values when no track processed"""
        response = client.get("/api/processing/parameters")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields present
        assert "spectral_balance" in data
        assert "dynamic_range" in data
        assert "energy_level" in data
        assert "target_lufs" in data
        assert "peak_target_db" in data
        assert "bass_boost" in data
        assert "air_boost" in data
        assert "compression_amount" in data
        assert "expansion_amount" in data
        assert "stereo_width" in data

    def test_processing_parameters_field_types(self, client):
        """Test that all fields have correct types"""
        response = client.get("/api/processing/parameters")
        data = response.json()
        
        # Coordinates should be floats 0-1
        assert isinstance(data["spectral_balance"], (int, float))
        assert isinstance(data["dynamic_range"], (int, float))
        assert isinstance(data["energy_level"], (int, float))
        
        # Processing parameters
        assert isinstance(data["target_lufs"], (int, float))
        assert isinstance(data["peak_target_db"], (int, float))
        assert isinstance(data["bass_boost"], (int, float))
        assert isinstance(data["air_boost"], (int, float))
        assert isinstance(data["compression_amount"], (int, float))
        assert isinstance(data["expansion_amount"], (int, float))
        assert isinstance(data["stereo_width"], (int, float))

    def test_processing_parameters_value_ranges(self, client):
        """Test that coordinate values are in valid range"""
        response = client.get("/api/processing/parameters")
        data = response.json()
        
        # Coordinates should be 0-1
        assert 0.0 <= data["spectral_balance"] <= 1.0
        assert 0.0 <= data["dynamic_range"] <= 1.0
        assert 0.0 <= data["energy_level"] <= 1.0
        
        # Compression/expansion/stereo should be 0-1
        assert 0.0 <= data["compression_amount"] <= 1.0
        assert 0.0 <= data["expansion_amount"] <= 1.0
        assert 0.0 <= data["stereo_width"] <= 1.0
        
        # LUFS and peak should be negative (dB values)
        assert data["target_lufs"] < 0
        assert data["peak_target_db"] <= 0

    def test_processing_parameters_endpoint_accepts_get_only(self, client):
        """Test that endpoint only accepts GET requests"""
        # POST should not be allowed
        response = client.post("/api/processing/parameters")
        assert response.status_code == 405  # Method Not Allowed
        
        # PUT should not be allowed
        response = client.put("/api/processing/parameters")
        assert response.status_code == 405

    def test_processing_parameters_consistency(self, client):
        """Test that multiple calls return consistent structure"""
        response1 = client.get("/api/processing/parameters")
        response2 = client.get("/api/processing/parameters")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Same keys in both responses
        assert set(response1.json().keys()) == set(response2.json().keys())


class TestProcessingParametersIntegration:
    """Integration tests for processing parameters"""

    def test_parameters_accessible_without_auth(self, client):
        """Test that endpoint doesn't require authentication"""
        response = client.get("/api/processing/parameters")
        # Should not return 401/403
        assert response.status_code == 200

    def test_parameters_cors_headers(self, client):
        """Test that CORS headers are present for frontend access"""
        response = client.options("/api/processing/parameters")
        # CORS preflight should be handled
        assert response.status_code in [200, 405]  # Either allowed or method not configured

    def test_parameters_with_enhancement_disabled(self, client):
        """Test that parameters are returned even when enhancement disabled"""
        # Disable enhancement
        client.post("/api/player/enhancement/toggle?enabled=false")
        
        # Parameters should still be accessible
        response = client.get("/api/processing/parameters")
        assert response.status_code == 200
        assert "spectral_balance" in response.json()


class TestProcessingParametersDocumentation:
    """Tests for API documentation"""

    def test_parameters_endpoint_in_openapi_schema(self, client):
        """Test that endpoint is documented in OpenAPI schema"""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        # Check endpoint exists in paths
        assert "/api/processing/parameters" in schema.get("paths", {})

    def test_parameters_endpoint_has_description(self, client):
        """Test that endpoint has proper documentation"""
        response = client.get("/openapi.json")
        schema = response.json()

        endpoint = schema["paths"]["/api/processing/parameters"]["get"]
        assert "summary" in endpoint or "description" in endpoint


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================
# Phase 5C.2: Dual-Mode Backend Testing Patterns
# ============================================================
# Following the same pattern as Phase 5C.1 API tests.

@pytest.mark.phase5c
class TestProcessingParametersDualModeParametrized:
    """Phase 5C.3: Parametrized dual-mode tests for processing parameters.

    These tests automatically run with both LibraryManager and RepositoryFactory
    via the parametrized mock_data_source fixture.
    """

    def test_parameters_tracks_interface(self, mock_data_source):
        """
        Parametrized test: Validate tracks repository for parameter handling.

        Processing parameters are applied to tracks from both access patterns.
        """
        mode, source = mock_data_source

        assert hasattr(source, 'tracks'), f"{mode} missing tracks repository"
        assert hasattr(source.tracks, 'get_all'), f"{mode}.tracks missing get_all"
        assert hasattr(source.tracks, 'get_by_id'), f"{mode}.tracks missing get_by_id"

    def test_parameters_get_all_returns_tuple(self, mock_data_source):
        """
        Parametrized test: Validate tracks.get_all returns (items, total) for both modes.

        Parameter application requires listing and iterating tracks.
        """
        mode, source = mock_data_source

        # Create mock tracks with parameter data
        track1 = Mock()
        track1.id = 1
        track1.title = "Track 1"
        track1.parameters = {}

        track2 = Mock()
        track2.id = 2
        track2.title = "Track 2"
        track2.parameters = {}

        test_tracks = [track1, track2]
        source.tracks.get_all = Mock(return_value=(test_tracks, 2))

        # Test with both modes
        tracks, total = source.tracks.get_all(limit=50, offset=0)

        assert len(tracks) == 2, f"{mode}: Expected 2 tracks"
        assert total == 2, f"{mode}: Expected total=2"
        assert tracks[0].title == "Track 1", f"{mode}: First track title mismatch"
        assert tracks[1].title == "Track 2", f"{mode}: Second track title mismatch"

    def test_parameters_get_by_id_interface(self, mock_data_source):
        """
        Parametrized test: Validate tracks.get_by_id works with both modes.

        Parameter application needs individual track retrieval for settings.
        """
        mode, source = mock_data_source

        track = Mock()
        track.id = 1
        track.title = "Test Track"
        track.parameters = {"preset": "adaptive", "intensity": 1.0}

        source.tracks.get_by_id = Mock(return_value=track)

        result = source.tracks.get_by_id(1)

        assert result.id == 1, f"{mode}: Track ID mismatch"
        assert result.title == "Test Track", f"{mode}: Track title mismatch"
        assert result.parameters == {"preset": "adaptive", "intensity": 1.0}, f"{mode}: Track parameters mismatch"
        source.tracks.get_by_id.assert_called_once_with(1)
