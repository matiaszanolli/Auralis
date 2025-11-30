"""
Tests for Cache-Aware Endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for endpoint helpers with cache integration and metrics.

Test Coverage:
- Cache-aware endpoint wrapper
- Cache query builder
- Endpoint metrics collection
- Performance trend detection

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, MagicMock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from cache.endpoints import (
    CacheAwareEndpoint,
    CacheQueryBuilder,
    EndpointMetrics,
    create_cache_aware_handler
)


# ============================================================================
# Cache-Aware Endpoint Tests
# ============================================================================

class TestCacheAwareEndpoint:
    """Test cache-aware endpoint wrapper."""

    @pytest.mark.asyncio
    async def test_cache_aware_endpoint_cache_hit(self):
        """Test endpoint wrapper with cache hit."""
        # Setup
        mock_cache = AsyncMock()
        endpoint = CacheAwareEndpoint(mock_cache)

        # Create handler that returns cache hit
        async def handler():
            return {"data": "test"}, "tier1"

        wrapped = endpoint.track_request(handler)
        result = await wrapped()

        assert result["data"] == {"data": "test"}
        assert result["cache_source"] == "tier1"
        assert result["cache_hit"] is True
        assert result["processing_time_ms"] >= 0  # Can be very fast

    @pytest.mark.asyncio
    async def test_cache_aware_endpoint_cache_miss(self):
        """Test endpoint wrapper with cache miss."""
        mock_cache = AsyncMock()
        endpoint = CacheAwareEndpoint(mock_cache)

        async def handler():
            return {"data": "fresh"}, "miss"

        wrapped = endpoint.track_request(handler)
        result = await wrapped()

        assert result["cache_source"] == "miss"
        assert result["cache_hit"] is False

    @pytest.mark.asyncio
    async def test_cache_aware_endpoint_with_monitor(self):
        """Test endpoint with metrics monitor."""
        mock_cache = AsyncMock()
        mock_monitor = AsyncMock()
        mock_monitor.update_metrics = AsyncMock()

        endpoint = CacheAwareEndpoint(mock_cache, monitor=mock_monitor)

        async def handler():
            return {"data": "test"}, "tier2"

        wrapped = endpoint.track_request(handler)
        result = await wrapped()

        assert result["cache_source"] == "tier2"
        mock_monitor.update_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_aware_endpoint_error_handling(self):
        """Test endpoint error handling."""
        mock_cache = AsyncMock()
        endpoint = CacheAwareEndpoint(mock_cache)

        async def handler():
            raise ValueError("Test error")

        wrapped = endpoint.track_request(handler)

        with pytest.raises(ValueError, match="Test error"):
            await wrapped()


# ============================================================================
# Cache Query Builder Tests
# ============================================================================

class TestCacheQueryBuilder:
    """Test cache query builder."""

    @pytest.mark.asyncio
    async def test_cache_query_tier1_hit(self):
        """Test query builder with Tier 1 cache hit."""
        mock_cache = AsyncMock()
        mock_cache.get_chunk = AsyncMock(return_value=("/path/to/chunk", "tier1"))

        db_handler = AsyncMock()
        builder = CacheQueryBuilder(mock_cache, db_handler)

        result = await builder.get_with_cache(
            cache_key="test_key",
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0
        )

        assert result == ("/path/to/chunk", "tier1")
        db_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_query_tier2_hit(self):
        """Test query builder with Tier 2 cache hit."""
        mock_cache = AsyncMock()
        mock_cache.get_chunk = AsyncMock(return_value=("/path/to/chunk", "tier2"))

        db_handler = AsyncMock()
        builder = CacheQueryBuilder(mock_cache, db_handler)

        result = await builder.get_with_cache(
            cache_key="test_key",
            track_id=1,
            chunk_idx=5,
            preset=None,
            intensity=1.0
        )

        assert result == ("/path/to/chunk", "tier2")
        db_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_query_miss_falls_back_to_db(self):
        """Test query builder falls back to database on cache miss."""
        mock_cache = AsyncMock()
        mock_cache.get_chunk = AsyncMock(return_value=(None, "miss"))

        db_data = {"processed": True}
        db_handler = AsyncMock(return_value=db_data)

        builder = CacheQueryBuilder(mock_cache, db_handler)

        result = await builder.get_with_cache(
            cache_key="test_key",
            track_id=1,
            chunk_idx=10,
            preset="bright",
            intensity=0.8
        )

        assert result == (db_data, "miss")
        db_handler.assert_called_once_with("test_key", 1, 10)

    @pytest.mark.asyncio
    async def test_cache_query_with_original_preset(self):
        """Test query with original preset."""
        mock_cache = AsyncMock()
        mock_cache.get_chunk = AsyncMock(return_value=("/path/original", "tier1"))

        db_handler = AsyncMock()
        builder = CacheQueryBuilder(mock_cache, db_handler)

        result = await builder.get_with_cache(
            cache_key="original_key",
            track_id=2,
            chunk_idx=0,
            preset=None,  # Original
            intensity=1.0
        )

        assert result[1] == "tier1"
        mock_cache.get_chunk.assert_called_once_with(
            track_id=2,
            chunk_idx=0,
            preset=None,
            intensity=1.0
        )


# ============================================================================
# Endpoint Metrics Tests
# ============================================================================

class TestEndpointMetrics:
    """Test endpoint metrics collection."""

    def test_metrics_initialization(self):
        """Test metrics collector initialization."""
        metrics = EndpointMetrics()

        assert metrics.summary["total_requests"] == 0
        assert metrics.summary["cache_hits"] == 0
        assert metrics.summary["cache_misses"] == 0
        assert len(metrics.metrics) == 0

    def test_record_cache_hit(self):
        """Test recording cache hit."""
        metrics = EndpointMetrics()

        metrics.record("/api/chunk", "tier1", 2.5)

        assert metrics.summary["total_requests"] == 1
        assert metrics.summary["cache_hits"] == 1
        assert metrics.summary["tier1_hits"] == 1

    def test_record_tier2_hit(self):
        """Test recording Tier 2 hit."""
        metrics = EndpointMetrics()

        metrics.record("/api/chunk", "tier2", 5.0)

        assert metrics.summary["cache_hits"] == 1
        assert metrics.summary["tier2_hits"] == 1

    def test_record_cache_miss(self):
        """Test recording cache miss."""
        metrics = EndpointMetrics()

        metrics.record("/api/chunk", "miss", 50.0)

        assert metrics.summary["total_requests"] == 1
        assert metrics.summary["cache_misses"] == 1
        assert metrics.summary["cache_hits"] == 0

    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        metrics = EndpointMetrics()

        metrics.record("/api/chunk", "tier1", 2.5)
        metrics.record("/api/chunk", "tier2", 5.0)
        metrics.record("/api/chunk", "miss", 50.0)
        metrics.record("/api/chunk", "tier1", 2.8)

        assert metrics.summary["total_requests"] == 4
        assert metrics.summary["cache_hits"] == 3
        assert metrics.summary["cache_misses"] == 1
        assert metrics.summary["tier1_hits"] == 2
        assert metrics.summary["tier2_hits"] == 1

    def test_average_processing_time(self):
        """Test average processing time calculation."""
        metrics = EndpointMetrics()

        metrics.record("/api/chunk", "tier1", 2.0)
        metrics.record("/api/chunk", "tier1", 4.0)
        metrics.record("/api/chunk", "tier1", 6.0)

        # (2 + 4 + 6) / 3 = 4
        assert metrics.summary["avg_time_ms"] == 4.0

    def test_metrics_history_limit(self):
        """Test metrics history is limited."""
        metrics = EndpointMetrics(max_history=100)

        # Record 150 metrics
        for i in range(150):
            metrics.record(f"/api/chunk", "tier1", 2.5)

        # Should only keep last 100
        assert len(metrics.metrics) == 100

    def test_get_summary(self):
        """Test getting summary statistics."""
        metrics = EndpointMetrics()

        metrics.record("/api/chunk", "tier1", 2.5)
        metrics.record("/api/chunk", "miss", 50.0)

        summary = metrics.get_summary()

        assert summary["total_requests"] == 2
        assert summary["cache_hits"] == 1
        assert summary["cache_misses"] == 1

    def test_get_tier_stats(self):
        """Test getting tier statistics."""
        metrics = EndpointMetrics()

        metrics.record("/api/chunk", "tier1", 2.5)
        metrics.record("/api/chunk", "tier2", 5.0)
        metrics.record("/api/chunk", "miss", 50.0)

        tier_stats = metrics.get_tier_stats()

        assert tier_stats["tier1_percent"] == pytest.approx(33.3, rel=0.1)
        assert tier_stats["tier2_percent"] == pytest.approx(33.3, rel=0.1)
        assert tier_stats["miss_percent"] == pytest.approx(33.3, rel=0.1)
        assert tier_stats["hit_rate"] == pytest.approx(0.667, rel=0.01)

    def test_get_performance_trends_improving(self):
        """Test performance trend detection - improving."""
        metrics = EndpointMetrics()

        # Baseline: slow requests
        for _ in range(10):
            metrics.record("/api/chunk", "miss", 50.0)

        # Recent: fast requests
        for _ in range(5):
            metrics.record("/api/chunk", "tier1", 2.0)

        trends = metrics.get_performance_trends(window=5)

        assert trends["trend"] == "improving"

    def test_get_performance_trends_degrading(self):
        """Test performance trend detection - degrading."""
        metrics = EndpointMetrics()

        # Baseline: fast requests
        for _ in range(10):
            metrics.record("/api/chunk", "tier1", 2.0)

        # Recent: slow requests
        for _ in range(5):
            metrics.record("/api/chunk", "miss", 50.0)

        trends = metrics.get_performance_trends(window=5)

        assert trends["trend"] == "degrading"

    def test_get_performance_trends_stable(self):
        """Test performance trend detection - stable."""
        metrics = EndpointMetrics()

        # Consistent performance
        for _ in range(15):
            metrics.record("/api/chunk", "tier1", 2.5)

        trends = metrics.get_performance_trends(window=5)

        assert trends["trend"] == "stable"

    def test_clear_metrics(self):
        """Test clearing metrics."""
        metrics = EndpointMetrics()

        metrics.record("/api/chunk", "tier1", 2.5)
        assert metrics.summary["total_requests"] == 1

        metrics.clear()

        assert metrics.summary["total_requests"] == 0
        assert len(metrics.metrics) == 0


# ============================================================================
# Cache-Aware Handler Tests
# ============================================================================

class TestCacheAwareHandler:
    """Test cache-aware handler wrapper."""

    @pytest.mark.asyncio
    async def test_create_cache_aware_handler_success(self):
        """Test cache-aware handler creation with success."""
        mock_cache = AsyncMock()

        async def handler():
            return {"result": "success"}, "tier1"

        wrapped = create_cache_aware_handler(mock_cache, handler)
        result = await wrapped()

        assert result["data"] == {"result": "success"}
        assert result["cache_source"] == "tier1"
        assert result["cache_hit"] is True

    @pytest.mark.asyncio
    async def test_create_cache_aware_handler_with_metrics(self):
        """Test handler with metrics tracking."""
        mock_cache = AsyncMock()
        metrics = EndpointMetrics()

        async def handler():
            return {"data": "test"}, "tier2"

        wrapped = create_cache_aware_handler(mock_cache, handler, metrics)
        result = await wrapped()

        assert metrics.summary["total_requests"] == 1
        assert metrics.summary["tier2_hits"] == 1

    @pytest.mark.asyncio
    async def test_cache_aware_handler_error_with_metrics(self):
        """Test handler error recording in metrics."""
        mock_cache = AsyncMock()
        metrics = EndpointMetrics()

        async def handler():
            raise ValueError("Test error")

        wrapped = create_cache_aware_handler(mock_cache, handler, metrics)

        with pytest.raises(ValueError):
            await wrapped()

        # Error should be recorded
        assert metrics.summary["total_requests"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
