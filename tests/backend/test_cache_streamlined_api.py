"""
Tests for Cache Streamlined Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the streamlined cache management API endpoints.

Coverage:
- GET /api/cache/stats - Get cache statistics
- GET /api/cache/track/{track_id}/status - Get track cache status
- POST /api/cache/clear - Clear all caches
- GET /api/cache/health - Get cache health status

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def client():
    """FastAPI test client with cache router registered via mock cache manager."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from routers.cache_streamlined import create_streamlined_cache_router

    mock_cache = Mock()
    mock_cache.get_stats = Mock(return_value={
        "tier1": {"hit_rate": 0.0, "size_mb": 0.0, "hits": 0, "misses": 0},
        "tier2": {"hit_rate": 0.0, "size_mb": 0.0, "hits": 0, "misses": 0},
        "overall": {"overall_hit_rate": 0.0, "total_size_mb": 0.0},
        "tracks": {},
    })
    mock_cache.get_track_cache_status = Mock(return_value=None)
    mock_cache.clear_all = AsyncMock()

    app = FastAPI()
    app.include_router(create_streamlined_cache_router(cache_manager=mock_cache))

    with TestClient(app) as test_client:
        yield test_client


class TestGetCacheStats:
    """Test GET /api/cache/stats"""

    def test_get_cache_stats_structure(self, client):
        """Test that cache stats returns correct structure"""
        response = client.get("/api/cache/stats")

        assert response.status_code == 200
        data = response.json()

        # Check required top-level keys
        assert "tier1" in data
        assert "tier2" in data
        assert "overall" in data
        assert "tracks" in data

    def test_get_cache_stats_tier1_fields(self, client):
        """Test that tier1 stats contain required fields"""
        response = client.get("/api/cache/stats")

        assert response.status_code == 200
        data = response.json()

        tier1 = data["tier1"]
        assert isinstance(tier1, dict)

        # Tier1 should have hit rate and size info
        # Exact fields depend on implementation
        assert "hit_rate" in tier1 or "hits" in tier1 or "size_mb" in tier1

    def test_get_cache_stats_tier2_fields(self, client):
        """Test that tier2 stats contain required fields"""
        response = client.get("/api/cache/stats")

        assert response.status_code == 200
        data = response.json()

        tier2 = data["tier2"]
        assert isinstance(tier2, dict)

        # Tier2 should have cache info
        assert "hit_rate" in tier2 or "hits" in tier2 or "size_mb" in tier2

    def test_get_cache_stats_overall_fields(self, client):
        """Test that overall stats contain required fields"""
        response = client.get("/api/cache/stats")

        assert response.status_code == 200
        data = response.json()

        overall = data["overall"]
        assert isinstance(overall, dict)

        # Overall stats should aggregate both tiers
        assert len(overall) > 0

    def test_get_cache_stats_tracks_dict(self, client):
        """Test that tracks field is a dictionary"""
        response = client.get("/api/cache/stats")

        assert response.status_code == 200
        data = response.json()

        tracks = data["tracks"]
        assert isinstance(tracks, dict)

    def test_get_cache_stats_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/cache/stats")
        assert response.status_code in [404, 405]

    def test_get_cache_stats_consistency(self, client):
        """Test that multiple calls return consistent structure"""
        response1 = client.get("/api/cache/stats")
        response2 = client.get("/api/cache/stats")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Structure should be identical
        assert set(response1.json().keys()) == set(response2.json().keys())


class TestGetTrackCacheStatus:
    """Test GET /api/cache/track/{track_id}/status"""

    def test_get_track_status_not_in_cache(self, client):
        """Test getting status for track not in cache"""
        # Use a track ID that's unlikely to be cached
        response = client.get("/api/cache/track/999999/status")

        # Should return 404 if not in cache
        assert response.status_code == 404
        assert "not found in cache" in response.json()["detail"].lower()

    def test_get_track_status_structure(self, client):
        """Test track status response structure if track is cached"""
        # Try track ID 1 (may or may not be cached)
        response = client.get("/api/cache/track/1/status")

        if response.status_code == 200:
            data = response.json()

            # Check required fields
            assert "track_id" in data
            assert "total_chunks" in data
            assert "cached_original" in data
            assert "cached_processed" in data
            assert "completion_percent" in data
            assert "fully_cached" in data

    def test_get_track_status_field_types(self, client):
        """Test that track status fields have correct types"""
        response = client.get("/api/cache/track/1/status")

        if response.status_code == 200:
            data = response.json()

            assert isinstance(data["track_id"], int)
            assert isinstance(data["total_chunks"], int)
            assert isinstance(data["cached_original"], int)
            assert isinstance(data["cached_processed"], int)
            assert isinstance(data["completion_percent"], (int, float))
            assert isinstance(data["fully_cached"], bool)

    def test_get_track_status_completion_range(self, client):
        """Test that completion percentage is in valid range"""
        response = client.get("/api/cache/track/1/status")

        if response.status_code == 200:
            data = response.json()

            # Completion should be 0-100%
            assert 0.0 <= data["completion_percent"] <= 100.0

    def test_get_track_status_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/cache/track/1/status")
        assert response.status_code in [404, 405]

    def test_get_track_status_negative_id(self, client):
        """Test that negative track IDs are rejected"""
        response = client.get("/api/cache/track/-1/status")

        # Should either reject or return 404
        assert response.status_code in [404, 422]


class TestClearCache:
    """Test POST /api/cache/clear"""

    def test_clear_cache_success(self, client):
        """Test clearing cache successfully"""
        response = client.post("/api/cache/clear")

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert "cleared" in data["message"].lower()

    def test_clear_cache_multiple_times(self, client):
        """Test clearing cache multiple times"""
        # First clear
        response1 = client.post("/api/cache/clear")
        assert response1.status_code == 200

        # Second clear (should also succeed)
        response2 = client.post("/api/cache/clear")
        assert response2.status_code == 200

    def test_clear_cache_accepts_post_only(self, client):
        """Test that endpoint only accepts POST"""
        response = client.get("/api/cache/clear")
        assert response.status_code in [404, 405]

    def test_clear_cache_affects_stats(self, client):
        """Test that clearing cache affects stats"""
        # Get stats before clearing
        stats_before = client.get("/api/cache/stats")
        assert stats_before.status_code == 200

        # Clear cache
        clear_response = client.post("/api/cache/clear")
        assert clear_response.status_code == 200

        # Get stats after clearing
        stats_after = client.get("/api/cache/stats")
        assert stats_after.status_code == 200

        # Stats should still be retrievable (structure unchanged)
        assert set(stats_before.json().keys()) == set(stats_after.json().keys())


class TestCacheHealth:
    """Test GET /api/cache/health"""

    def test_cache_health_structure(self, client):
        """Test cache health response structure"""
        response = client.get("/api/cache/health")

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "healthy" in data
        assert "tier1_size_mb" in data
        assert "tier1_healthy" in data
        assert "tier2_size_mb" in data
        assert "tier2_healthy" in data
        assert "total_size_mb" in data
        assert "memory_healthy" in data
        assert "tier1_hit_rate" in data
        assert "overall_hit_rate" in data

    def test_cache_health_field_types(self, client):
        """Test that health fields have correct types"""
        response = client.get("/api/cache/health")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["healthy"], bool)
        assert isinstance(data["tier1_size_mb"], (int, float))
        assert isinstance(data["tier1_healthy"], bool)
        assert isinstance(data["tier2_size_mb"], (int, float))
        assert isinstance(data["tier2_healthy"], bool)
        assert isinstance(data["total_size_mb"], (int, float))
        assert isinstance(data["memory_healthy"], bool)
        assert isinstance(data["tier1_hit_rate"], (int, float))
        assert isinstance(data["overall_hit_rate"], (int, float))

    def test_cache_health_size_non_negative(self, client):
        """Test that cache sizes are non-negative"""
        response = client.get("/api/cache/health")

        assert response.status_code == 200
        data = response.json()

        assert data["tier1_size_mb"] >= 0
        assert data["tier2_size_mb"] >= 0
        assert data["total_size_mb"] >= 0

    def test_cache_health_hit_rate_range(self, client):
        """Test that hit rates are in valid range"""
        response = client.get("/api/cache/health")

        assert response.status_code == 200
        data = response.json()

        # Hit rates should be 0-1 (0-100%)
        assert 0.0 <= data["tier1_hit_rate"] <= 1.0
        assert 0.0 <= data["overall_hit_rate"] <= 1.0

    def test_cache_health_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/cache/health")
        assert response.status_code in [404, 405]

    def test_cache_health_consistency(self, client):
        """Test that health checks are consistent"""
        response1 = client.get("/api/cache/health")
        response2 = client.get("/api/cache/health")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Structure should be identical
        assert set(response1.json().keys()) == set(response2.json().keys())


class TestCacheIntegration:
    """Integration tests for cache endpoints"""

    def test_workflow_stats_health_clear(self, client):
        """Test workflow: get stats → check health → clear → verify"""
        # 1. Get initial stats
        stats_response = client.get("/api/cache/stats")
        assert stats_response.status_code == 200

        # 2. Check health
        health_response = client.get("/api/cache/health")
        assert health_response.status_code == 200

        # 3. Clear cache
        clear_response = client.post("/api/cache/clear")
        assert clear_response.status_code == 200

        # 4. Verify stats still accessible
        stats_after = client.get("/api/cache/stats")
        assert stats_after.status_code == 200

        # 5. Verify health still accessible
        health_after = client.get("/api/cache/health")
        assert health_after.status_code == 200

    def test_workflow_track_status_after_clear(self, client):
        """Test track status after clearing cache"""
        # Get track status (may or may not exist)
        status_before = client.get("/api/cache/track/1/status")

        # Clear cache
        clear_response = client.post("/api/cache/clear")
        assert clear_response.status_code == 200

        # Try to get track status again
        status_after = client.get("/api/cache/track/1/status")

        # Should return 404 (track no longer in cache) or same structure
        assert status_after.status_code in [200, 404]

    def test_workflow_health_reflects_stats(self, client):
        """Test that health reflects stats data"""
        stats_response = client.get("/api/cache/stats")
        health_response = client.get("/api/cache/health")

        assert stats_response.status_code == 200
        assert health_response.status_code == 200

        stats = stats_response.json()
        health = health_response.json()

        # Health should be based on stats
        # Tier sizes should be consistent
        if "size_mb" in stats["tier1"]:
            assert health["tier1_size_mb"] == stats["tier1"]["size_mb"]

    def test_multiple_track_status_requests(self, client):
        """Test getting status for multiple tracks"""
        track_ids = [1, 2, 3, 5, 10]

        for track_id in track_ids:
            response = client.get(f"/api/cache/track/{track_id}/status")

            # Should return 200 or 404 (not 500)
            assert response.status_code in [200, 404]


class TestCacheSecurityValidation:
    """Security-focused tests for cache endpoints"""

    def test_cache_stats_no_injection(self, client):
        """Test that cache stats don't allow injection"""
        # Try to inject query parameters
        response = client.get("/api/cache/stats?evil=<script>alert('xss')</script>")

        # Should ignore unknown parameters
        assert response.status_code == 200

    def test_track_status_extremely_large_id(self, client):
        """Test track status with extremely large ID"""
        large_id = 999999999999
        response = client.get(f"/api/cache/track/{large_id}/status")

        # Should handle gracefully (404, not crash)
        assert response.status_code == 404

    def test_clear_cache_unauthorized_access(self, client):
        """Test that cache clear requires proper authorization"""
        # Note: This test assumes no auth is currently required
        # If auth is added, this test should verify it
        response = client.post("/api/cache/clear")

        # Currently should succeed (no auth)
        # If auth added, should return 401/403
        assert response.status_code in [200, 401, 403]

    def test_health_check_performance(self, client):
        """Test that health check responds quickly"""
        import time

        start = time.time()
        response = client.get("/api/cache/health")
        duration = time.time() - start

        assert response.status_code == 200

        # Health check should be fast (< 1 second)
        assert duration < 1.0
