"""
Tests for Enhancement Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the enhancement settings API endpoints.

Coverage:
- POST /api/player/enhancement/toggle - Enable/disable enhancement
- POST /api/player/enhancement/preset - Change preset
- POST /api/player/enhancement/intensity - Adjust intensity
- GET /api/player/enhancement/status - Get current settings
- GET /api/player/mastering/recommendation/{track_id} - Get mastering recommendation
- GET /api/processing/parameters - Get processing parameters
- POST /api/player/enhancement/cache/clear - Clear cache

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


class TestToggleEnhancement:
    """Test POST /api/player/enhancement/toggle"""

    def test_toggle_enhancement_enable(self, client):
        """Test enabling enhancement"""
        response = client.post("/api/player/enhancement/toggle?enabled=true")

        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert data["settings"]["enabled"] is True
        assert "message" in data

    def test_toggle_enhancement_disable(self, client):
        """Test disabling enhancement"""
        response = client.post("/api/player/enhancement/toggle?enabled=false")

        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["enabled"] is False

    def test_toggle_enhancement_missing_parameter(self, client):
        """Test toggle without enabled parameter"""
        response = client.post("/api/player/enhancement/toggle")

        # Should return 422 (validation error)
        assert response.status_code == 422

    def test_toggle_enhancement_invalid_type(self, client):
        """Test toggle with invalid boolean value"""
        response = client.post("/api/player/enhancement/toggle?enabled=invalid")

        assert response.status_code == 422


class TestSetEnhancementPreset:
    """Test POST /api/player/enhancement/preset"""

    def test_set_preset_valid(self, client):
        """Test setting valid preset"""
        for preset in ["adaptive", "gentle", "warm", "bright", "punchy"]:
            response = client.post(f"/api/player/enhancement/preset?preset={preset}")

            assert response.status_code == 200
            data = response.json()
            assert data["settings"]["preset"] == preset

    def test_set_preset_case_insensitive(self, client):
        """Test that preset names are case-insensitive"""
        response = client.post("/api/player/enhancement/preset?preset=WARM")

        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["preset"] == "warm"

    def test_set_preset_invalid(self, client):
        """Test setting invalid preset"""
        response = client.post("/api/player/enhancement/preset?preset=invalid_preset")

        assert response.status_code == 400
        assert "Invalid preset" in response.json()["detail"]

    def test_set_preset_missing_parameter(self, client):
        """Test preset change without preset parameter"""
        response = client.post("/api/player/enhancement/preset")

        assert response.status_code == 422


class TestSetEnhancementIntensity:
    """Test POST /api/player/enhancement/intensity"""

    def test_set_intensity_valid(self, client):
        """Test setting valid intensity values"""
        for intensity in [0.0, 0.5, 1.0]:
            response = client.post(f"/api/player/enhancement/intensity?intensity={intensity}")

            assert response.status_code == 200
            data = response.json()
            assert data["settings"]["intensity"] == intensity

    def test_set_intensity_boundary_values(self, client):
        """Test intensity at exact boundaries"""
        # Test minimum
        response = client.post("/api/player/enhancement/intensity?intensity=0.0")
        assert response.status_code == 200

        # Test maximum
        response = client.post("/api/player/enhancement/intensity?intensity=1.0")
        assert response.status_code == 200

    def test_set_intensity_below_minimum(self, client):
        """Test intensity below 0.0"""
        response = client.post("/api/player/enhancement/intensity?intensity=-0.1")

        assert response.status_code == 400
        assert "between 0.0 and 1.0" in response.json()["detail"]

    def test_set_intensity_above_maximum(self, client):
        """Test intensity above 1.0"""
        response = client.post("/api/player/enhancement/intensity?intensity=1.1")

        assert response.status_code == 400
        assert "between 0.0 and 1.0" in response.json()["detail"]

    def test_set_intensity_missing_parameter(self, client):
        """Test intensity change without parameter"""
        response = client.post("/api/player/enhancement/intensity")

        assert response.status_code == 422

    def test_set_intensity_invalid_type(self, client):
        """Test intensity with non-numeric value"""
        response = client.post("/api/player/enhancement/intensity?intensity=invalid")

        assert response.status_code == 422


class TestGetEnhancementStatus:
    """Test GET /api/player/enhancement/status"""

    def test_get_enhancement_status(self, client):
        """Test getting current enhancement status"""
        response = client.get("/api/player/enhancement/status")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "preset" in data
        assert "intensity" in data
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["preset"], str)
        assert isinstance(data["intensity"], (int, float))

    def test_get_enhancement_status_accepts_get_only(self, client):
        """Test that status endpoint only accepts GET"""
        response = client.post("/api/player/enhancement/status")
        assert response.status_code == 405  # Method Not Allowed


class TestGetMasteringRecommendation:
    """Test GET /api/player/mastering/recommendation/{track_id}"""

    def test_get_mastering_recommendation_missing_filepath(self, client):
        """Test recommendation without filepath parameter"""
        response = client.get("/api/player/mastering/recommendation/1")

        assert response.status_code == 400
        assert "filepath parameter required" in response.json()["detail"]

    def test_get_mastering_recommendation_absolute_path(self, client):
        """Test that absolute paths are rejected (security)"""
        response = client.get("/api/player/mastering/recommendation/1?filepath=/etc/passwd")

        assert response.status_code == 400
        assert "Absolute paths are not allowed" in response.json()["detail"]

    def test_get_mastering_recommendation_path_traversal(self, client):
        """Test that path traversal is rejected (security)"""
        response = client.get("/api/player/mastering/recommendation/1?filepath=../../etc/passwd")

        assert response.status_code == 400
        assert "Path traversal" in response.json()["detail"]

    def test_get_mastering_recommendation_custom_threshold(self, client):
        """Test custom confidence threshold parameter"""
        # This will fail because file doesn't exist, but validates parameter passing
        response = client.get(
            "/api/player/mastering/recommendation/1"
            "?filepath=test.mp3&confidence_threshold=0.6"
        )

        # Should accept the parameter (even if processing fails)
        assert response.status_code in [400, 500]  # Not a validation error


class TestGetProcessingParameters:
    """Test GET /api/processing/parameters"""

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

        # All values should be numeric
        for key, value in data.items():
            assert isinstance(value, (int, float)), f"{key} should be numeric"

    def test_processing_parameters_value_ranges(self, client):
        """Test that coordinate values are in valid range"""
        response = client.get("/api/processing/parameters")
        data = response.json()

        # Coordinates should be 0-1
        assert 0.0 <= data["spectral_balance"] <= 1.0
        assert 0.0 <= data["dynamic_range"] <= 1.0
        assert 0.0 <= data["energy_level"] <= 1.0

    def test_processing_parameters_accepts_get_only(self, client):
        """Test that endpoint only accepts GET requests"""
        response = client.post("/api/processing/parameters")
        assert response.status_code == 405  # Method Not Allowed


class TestClearProcessingCache:
    """Test POST /api/player/enhancement/cache/clear"""

    def test_clear_cache_success(self, client):
        """Test clearing cache successfully"""
        response = client.post("/api/player/enhancement/cache/clear")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "items_cleared" in data
        assert isinstance(data["items_cleared"], int)

    def test_clear_cache_accepts_post_only(self, client):
        """Test that cache clear only accepts POST"""
        response = client.get("/api/player/enhancement/cache/clear")
        # Should be 405 (Method Not Allowed) or 404 (Not Found if GET route doesn't exist)
        assert response.status_code in [404, 405]


class TestEnhancementIntegration:
    """Integration tests for enhancement endpoints"""

    def test_workflow_enable_change_preset_adjust_intensity(self, client):
        """Test complete workflow: enable → change preset → adjust intensity"""
        # 1. Enable enhancement
        response = client.post("/api/player/enhancement/toggle?enabled=true")
        assert response.status_code == 200

        # 2. Change preset
        response = client.post("/api/player/enhancement/preset?preset=warm")
        assert response.status_code == 200

        # 3. Adjust intensity
        response = client.post("/api/player/enhancement/intensity?intensity=0.7")
        assert response.status_code == 200

        # 4. Verify final state
        response = client.get("/api/player/enhancement/status")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["preset"] == "warm"
        assert data["intensity"] == 0.7

    def test_multiple_preset_changes(self, client):
        """Test changing presets multiple times"""
        presets = ["gentle", "warm", "bright", "punchy", "adaptive"]

        for preset in presets:
            response = client.post(f"/api/player/enhancement/preset?preset={preset}")
            assert response.status_code == 200
            assert response.json()["settings"]["preset"] == preset
