"""
Tests for Phase B.2 Cache Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for cache layer integration with standardized API endpoints.

Test Coverage:
- Cache-aware response schemas and validation
- Cache monitoring and health tracking
- Cache statistics and analytics
- Integration with endpoint handlers
- Performance impact of caching

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from schemas import (
    CacheSource,
    ChunkCacheMetadata,
    TrackCacheStatusResponse,
    CacheTierStats,
    OverallCacheStats,
    CacheStatsResponse,
    CacheHealthResponse,
    CacheAwareResponse
)
from helpers import (
    calculate_cache_hit_probability,
    format_cache_stats,
    estimate_cache_completion_time,
    create_cache_aware_response
)
from cache_monitoring import (
    CacheMonitor,
    CacheMetrics,
    CacheAlert,
    HealthStatus
)


# ============================================================================
# Schema Tests
# ============================================================================

class TestCacheSchemas:
    """Test cache integration schemas."""

    def test_cache_source_enum(self):
        """Test CacheSource enum values."""
        assert CacheSource.TIER1.value == "tier1"
        assert CacheSource.TIER2.value == "tier2"
        assert CacheSource.MISS.value == "miss"

    def test_chunk_cache_metadata_creation(self):
        """Test creating chunk cache metadata."""
        metadata = ChunkCacheMetadata(
            track_id=123,
            chunk_index=0,
            preset="adaptive",
            intensity=1.0,
            source=CacheSource.TIER1,
            timestamp=datetime.utcnow(),
            access_count=5
        )
        assert metadata.track_id == 123
        assert metadata.preset == "adaptive"
        assert metadata.source == CacheSource.TIER1
        assert metadata.access_count == 5

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

    def test_cache_aware_response(self):
        """Test cache-aware response wrapper."""
        response = CacheAwareResponse(
            status="success",
            data={"test": "data"},
            cache_source=CacheSource.TIER1,
            cache_hit=True,
            processing_time_ms=2.5
        )
        assert response.cache_hit is True
        assert response.cache_source == CacheSource.TIER1
        assert response.processing_time_ms == 2.5


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestCacheHelpers:
    """Test cache integration helper functions."""

    def test_calculate_cache_hit_probability_sufficient_requests(self):
        """Test hit rate calculation with sufficient requests."""
        hit_rate = calculate_cache_hit_probability(
            total_hits=150,
            total_misses=10,
            minimum_requests=10
        )
        assert hit_rate == pytest.approx(0.938, rel=0.01)

    def test_calculate_cache_hit_probability_insufficient_requests(self):
        """Test hit rate with insufficient data."""
        hit_rate = calculate_cache_hit_probability(
            total_hits=5,
            total_misses=2,
            minimum_requests=10
        )
        assert hit_rate == 0.0

    def test_calculate_cache_hit_probability_no_hits(self):
        """Test hit rate with all misses."""
        hit_rate = calculate_cache_hit_probability(
            total_hits=0,
            total_misses=100,
            minimum_requests=10
        )
        assert hit_rate == 0.0

    def test_calculate_cache_hit_probability_all_hits(self):
        """Test hit rate with perfect hits."""
        hit_rate = calculate_cache_hit_probability(
            total_hits=100,
            total_misses=0,
            minimum_requests=10
        )
        assert hit_rate == 1.0

    def test_format_cache_stats(self):
        """Test cache stats formatting."""
        stats = {
            "tier1": {
                "chunks": 4,
                "size_mb": 6.0,
                "hits": 150,
                "misses": 10,
                "hit_rate": 0.938
            },
            "tier2": {
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
                "overall_hit_rate": 0.938
            },
            "tracks": {}
        }

        formatted = format_cache_stats(stats)

        assert formatted["tier1"]["chunks"] == 4
        assert formatted["tier1"]["hit_rate"] == 0.938
        assert formatted["overall"]["tracks_cached"] == 5
        assert formatted["overall"]["total_chunks"] == 150

    def test_estimate_cache_completion_time_partially_cached(self):
        """Test cache completion time estimation."""
        time_estimate = estimate_cache_completion_time(
            cached_chunks=35,
            total_chunks=50,
            avg_processing_time_per_chunk=0.3
        )
        assert time_estimate == pytest.approx(4.5, rel=0.01)  # 15 remaining * 0.3s

    def test_estimate_cache_completion_time_fully_cached(self):
        """Test completion time when fully cached."""
        time_estimate = estimate_cache_completion_time(
            cached_chunks=50,
            total_chunks=50
        )
        assert time_estimate is None

    def test_estimate_cache_completion_time_over_cached(self):
        """Test completion time with more cached than total."""
        time_estimate = estimate_cache_completion_time(
            cached_chunks=60,
            total_chunks=50
        )
        assert time_estimate is None

    def test_create_cache_aware_response_cache_hit(self):
        """Test creating cache-aware response with hit."""
        response = create_cache_aware_response(
            data={"key": "value"},
            cache_source="tier1",
            processing_time_ms=2.5,
            message="Retrieved from cache"
        )
        assert response["status"] == "success"
        assert response["cache_hit"] is True
        assert response["cache_source"] == "tier1"
        assert response["processing_time_ms"] == 2.5

    def test_create_cache_aware_response_cache_miss(self):
        """Test creating cache-aware response with miss."""
        response = create_cache_aware_response(
            data={"key": "value"},
            cache_source="miss",
            processing_time_ms=50.0
        )
        assert response["cache_hit"] is False
        assert response["cache_source"] == "miss"
        assert response["processing_time_ms"] == 50.0


# ============================================================================
# Cache Monitoring Tests
# ============================================================================

class MockCacheManager:
    """Mock cache manager for testing monitoring."""

    def __init__(self):
        self.hit_count = 0
        self.miss_count = 0
        self.tier1_size = 0.0
        self.tier2_size = 0.0

    def get_stats(self):
        """Return mock stats."""
        return {
            "tier1": {
                "hit_rate": self.hit_count / max(1, self.hit_count + self.miss_count),
                "size_mb": self.tier1_size,
                "chunks": int(self.tier1_size / 1.5) if self.tier1_size > 0 else 0
            },
            "tier2": {
                "hit_rate": self.hit_count / max(1, self.hit_count + self.miss_count),
                "size_mb": self.tier2_size,
                "chunks": int(self.tier2_size / 1.5) if self.tier2_size > 0 else 0,
                "tracks_cached": 2
            },
            "overall": {
                "overall_hit_rate": self.hit_count / max(1, self.hit_count + self.miss_count),
                "total_size_mb": self.tier1_size + self.tier2_size,
                "total_hits": self.hit_count,
                "total_misses": self.miss_count
            }
        }


class TestCacheMonitor:
    """Test cache monitoring system."""

    def test_cache_monitor_initialization(self):
        """Test monitor initialization."""
        mock_cache = MockCacheManager()
        monitor = CacheMonitor(mock_cache)

        assert monitor.tier1_size_limit_mb == 15
        assert monitor.tier2_size_limit_mb == 250
        assert monitor.total_size_limit_mb == 260

    def test_update_metrics(self):
        """Test metrics update."""
        mock_cache = MockCacheManager()
        mock_cache.hit_count = 150
        mock_cache.miss_count = 10
        mock_cache.tier1_size = 6.0
        mock_cache.tier2_size = 200.0

        monitor = CacheMonitor(mock_cache)
        metrics = monitor.update_metrics()

        assert metrics.tier1_size_mb == 6.0
        assert metrics.tier2_size_mb == 200.0
        assert metrics.total_requests == 160

    def test_metrics_history_limited(self):
        """Test metrics history size limit."""
        mock_cache = MockCacheManager()
        monitor = CacheMonitor(mock_cache)

        # Add more than max_history measurements
        for i in range(150):
            monitor.update_metrics()

        assert len(monitor.metrics_history) == 100

    def test_alert_tier1_size_exceeded(self):
        """Test alert for Tier 1 size exceeded."""
        mock_cache = MockCacheManager()
        mock_cache.tier1_size = 20.0  # Exceeds limit of 15

        monitor = CacheMonitor(mock_cache)
        metrics = monitor.update_metrics()

        health_status, alerts = monitor.get_health_status()
        assert health_status == HealthStatus.CRITICAL
        assert len(alerts) > 0
        assert any("Tier 1" in alert.title for alert in alerts)

    def test_alert_hit_rate_warning(self):
        """Test alert for low hit rate."""
        mock_cache = MockCacheManager()
        mock_cache.hit_count = 60  # 60 hits out of 100 = 60% rate
        mock_cache.miss_count = 40

        monitor = CacheMonitor(mock_cache)
        monitor.min_hit_rate_warning = 0.70

        metrics = monitor.update_metrics()

        health_status, alerts = monitor.get_health_status()
        assert health_status == HealthStatus.WARNING

    def test_alert_hit_rate_critical(self):
        """Test alert for very low hit rate."""
        mock_cache = MockCacheManager()
        mock_cache.hit_count = 40  # 40% hit rate
        mock_cache.miss_count = 60

        monitor = CacheMonitor(mock_cache)
        monitor.min_hit_rate_critical = 0.50

        metrics = monitor.update_metrics()

        health_status, alerts = monitor.get_health_status()
        assert health_status == HealthStatus.CRITICAL

    def test_get_trend_increasing(self):
        """Test trend detection for increasing metric."""
        mock_cache = MockCacheManager()
        monitor = CacheMonitor(mock_cache)

        # Simulate increasing cache size
        for i in range(5):
            mock_cache.tier1_size = i * 2.0
            monitor.update_metrics()

        trend = monitor.get_trend("tier1_size_mb")
        assert trend["trend"] == "up"

    def test_get_trend_decreasing(self):
        """Test trend detection for decreasing metric."""
        mock_cache = MockCacheManager()
        monitor = CacheMonitor(mock_cache)

        # Simulate decreasing cache size
        for i in range(5, 0, -1):
            mock_cache.tier1_size = i * 2.0
            monitor.update_metrics()

        trend = monitor.get_trend("tier1_size_mb")
        assert trend["trend"] == "down"

    def test_get_trend_stable(self):
        """Test trend detection for stable metric."""
        mock_cache = MockCacheManager()
        monitor = CacheMonitor(mock_cache)

        mock_cache.tier1_size = 5.0

        for _ in range(5):
            monitor.update_metrics()

        trend = monitor.get_trend("tier1_size_mb")
        assert trend["trend"] == "stable"

    def test_get_summary(self):
        """Test getting comprehensive summary."""
        mock_cache = MockCacheManager()
        mock_cache.hit_count = 150
        mock_cache.miss_count = 10
        mock_cache.tier1_size = 6.0
        mock_cache.tier2_size = 200.0

        monitor = CacheMonitor(mock_cache)
        monitor.update_metrics()

        summary = monitor.get_summary()

        assert "health_status" in summary
        assert "tier1" in summary
        assert "tier2" in summary
        assert "overall" in summary
        assert summary["tier1"]["size_mb"] == 6.0
        assert summary["tier2"]["size_mb"] == 200.0


# ============================================================================
# Integration Tests
# ============================================================================

class TestCacheIntegration:
    """Integration tests for cache system."""

    def test_cache_stats_response_structure(self):
        """Test complete cache stats response structure."""
        mock_cache = MockCacheManager()
        mock_cache.hit_count = 1500
        mock_cache.miss_count = 100
        mock_cache.tier1_size = 6.0
        mock_cache.tier2_size = 219.0

        monitor = CacheMonitor(mock_cache)
        monitor.update_metrics()

        stats = {
            "tier1": {
                "chunks": 4,
                "size_mb": 6.0,
                "hits": 150,
                "misses": 10,
                "hit_rate": 0.938
            },
            "tier2": {
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
                "overall_hit_rate": 0.938
            },
            "tracks": {}
        }

        # Should validate successfully
        response = CacheStatsResponse(**format_cache_stats(stats))
        assert response.tier1.hit_rate == 0.938
        assert response.tier2.chunks == 146
        assert response.overall.total_hits == 1500

    def test_cache_aware_response_with_data(self):
        """Test cache-aware response with typed data."""
        response = CacheAwareResponse[Dict[str, Any]](
            status="success",
            data={"track_id": 123, "title": "Test Track"},
            cache_source=CacheSource.TIER2,
            cache_hit=True,
            processing_time_ms=5.2,
            message="Retrieved from warm cache"
        )

        assert response.data["track_id"] == 123
        assert response.cache_hit is True

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
