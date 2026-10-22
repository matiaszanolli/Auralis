"""
Tests for Phase B.2 Cache Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for cache layer integration with standardized API endpoints.

Test Coverage:
- Cache-aware response schemas and validation
- Cache statistics and analytics
- Integration with endpoint handlers
- Performance impact of caching

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from schemas import (
    CacheHealthResponse,
    CacheStatsResponse,
    CacheTierStats,
    OverallCacheStats,
    TrackCacheStatusResponse,
)

# ============================================================================
# Schema Tests
# ============================================================================

class TestCacheSchemas:
    """Test cache integration schemas."""

    def test_track_cache_status_response(self):
        """Test track cache status response."""
        status = TrackCacheStatusResponse(
            track_id=123,
            total_chunks=50,
            cached_original=50,
            cached_processed=35,
            completion_percent=70.0,
            fully_cached=False,
            estimated_cache_time_seconds=15.5
        )
        assert status.track_id == 123
        assert status.completion_percent == 70.0
        assert status.fully_cached is False

    def test_cache_tier_stats(self):
        """Test cache tier statistics."""
        stats = CacheTierStats(
            tier_name="tier1",
            chunks=4,
            size_mb=6.0,
            hits=150,
            misses=10,
            hit_rate=0.938
        )
        assert stats.tier_name == "tier1"
        assert stats.hit_rate == 0.938

    def test_overall_cache_stats(self):
        """Test overall cache statistics."""
        stats = OverallCacheStats(
            total_chunks=150,
            total_size_mb=225.0,
            total_hits=1500,
            total_misses=100,
            overall_hit_rate=0.938,
            tracks_cached=5
        )
        assert stats.total_chunks == 150
        assert stats.overall_hit_rate == 0.938

    def test_cache_health_response(self):
        """Test cache health response."""
        health = CacheHealthResponse(
            healthy=True,
            tier1_size_mb=6.0,
            tier1_healthy=True,
            tier2_size_mb=200.0,
            tier2_healthy=True,
            total_size_mb=206.0,
            memory_healthy=True,
            tier1_hit_rate=0.95,
            overall_hit_rate=0.938
        )
        assert health.healthy is True
        assert health.memory_healthy is True



# ============================================================================
# Cache Integration Tests
# ============================================================================

class TestCacheIntegration:
    """Integration tests for cache system."""

    def test_cache_stats_response_structure(self):
        """Test complete cache stats response structure."""
        stats = {
            "tier1": {
                "tier_name": "tier1",
                "chunks": 4,
                "size_mb": 6.0,
                "hits": 150,
                "misses": 10,
                "hit_rate": 0.938
            },
            "tier2": {
                "tier_name": "tier2",
                "chunks": 146,
                "size_mb": 219.0,
                "hits": 1350,
                "misses": 90,
                "hit_rate": 0.937,
                "tracks_cached": 5
            },
            "overall": {
                "total_chunks": 150,
                "total_size_mb": 225.0,
                "total_hits": 1500,
                "total_misses": 100,
                "overall_hit_rate": 0.938,
                "tracks_cached": 5
            },
            "tracks": {}
        }

        # Should validate successfully
        response = CacheStatsResponse(**stats)
        assert response.tier1.hit_rate == 0.938
        assert response.tier2.chunks == 146
        assert response.overall.total_hits == 1500


    def test_cache_health_response_all_good(self):
        """Test health response when all metrics are healthy."""
        health = CacheHealthResponse(
            healthy=True,
            tier1_size_mb=6.0,
            tier1_healthy=True,
            tier2_size_mb=200.0,
            tier2_healthy=True,
            total_size_mb=206.0,
            memory_healthy=True,
            tier1_hit_rate=0.95,
            overall_hit_rate=0.938
        )

        assert health.healthy is True
        assert health.tier1_healthy is True
        assert health.tier2_healthy is True
        assert health.memory_healthy is True

    def test_cache_health_response_memory_warning(self):
        """Test health response with memory warning."""
        health = CacheHealthResponse(
            healthy=False,
            tier1_size_mb=20.0,
            tier1_healthy=False,
            tier2_size_mb=240.0,
            tier2_healthy=True,
            total_size_mb=260.0,
            memory_healthy=False,
            tier1_hit_rate=0.95,
            overall_hit_rate=0.938
        )

        assert health.healthy is False
        assert health.tier1_healthy is False
        assert health.memory_healthy is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
