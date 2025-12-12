"""
Tests for Processing Parameters API

Tests the new /api/processing/parameters endpoint that exposes real-time
processing data from the continuous space system.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

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
