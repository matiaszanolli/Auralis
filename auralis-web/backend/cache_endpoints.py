"""
Cache-Aware Endpoint Helpers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for creating cache-aware endpoints with automatic timing and hit tracking.

Phase B.2: Cache Integration and Monitoring

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import time
from typing import Callable, Any, Optional, Awaitable, TypeVar, Dict
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheAwareEndpoint:
    """
    Wrapper for creating cache-aware endpoints with automatic metrics.

    Tracks:
    - Cache hit/miss
    - Processing time
    - Response source (tier1, tier2, miss)
    """

    def __init__(self, cache_manager, monitor=None):
        """
        Initialize cache-aware endpoint wrapper.

        Args:
            cache_manager: StreamlinedCacheManager instance
            monitor: Optional CacheMonitor instance for tracking
        """
        self.cache_manager = cache_manager
        self.monitor = monitor

    def track_request(
        self,
        handler: Callable[..., Awaitable[tuple[Any, str]]],
    ) -> Callable:
        """
        Decorator to track endpoint request metrics.

        Expected handler signature: async def handler(...) -> (data, cache_source)

        Args:
            handler: Async handler function

        Returns:
            Wrapped handler with metrics tracking
        """
        @wraps(handler)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                data, cache_source = await handler(*args, **kwargs)
                processing_time_ms = (time.time() - start_time) * 1000

                # Update monitor if available
                if self.monitor:
                    self.monitor.update_metrics()

                return {
                    "data": data,
                    "cache_source": cache_source,
                    "cache_hit": cache_source != "miss",
                    "processing_time_ms": round(processing_time_ms, 2)
                }
            except Exception as e:
                processing_time_ms = (time.time() - start_time) * 1000
                logger.error(f"Endpoint error: {e}")

                raise

        return wrapper


class CacheQueryBuilder:
    """
    Helper for building cache-aware queries.

    Supports:
    - Tier 1 (hot) cache checks
    - Tier 2 (warm) cache checks
    - Fallback to database on miss
    """

    def __init__(self, cache_manager, db_handler: Callable):
        """
        Initialize cache query builder.

        Args:
            cache_manager: StreamlinedCacheManager instance
            db_handler: Function to call on cache miss
        """
        self.cache_manager = cache_manager
        self.db_handler = db_handler

    async def get_with_cache(
        self,
        cache_key: str,
        track_id: int,
        chunk_idx: int,
        preset: Optional[str] = None,
        intensity: float = 1.0
    ) -> tuple[Any, str]:
        """
        Get data with automatic cache checking.

        Args:
            cache_key: Unique cache key
            track_id: Track ID for cache lookup
            chunk_idx: Chunk index for cache lookup
            preset: Processing preset (None for original)
            intensity: Processing intensity

        Returns:
            (data, cache_source) tuple
        """
        # Check cache
        chunk_path, source = await self.cache_manager.get_chunk(
            track_id=track_id,
            chunk_idx=chunk_idx,
            preset=preset,
            intensity=intensity
        )

        if source != "miss":
            logger.debug(f"Cache hit from {source}: {cache_key}")
            return (chunk_path, source)

        # Cache miss - load from database
        logger.debug(f"Cache miss: {cache_key}, loading from database")
        data = await self.db_handler(cache_key, track_id, chunk_idx)

        return (data, "miss")


class EndpointMetrics:
    """
    Collect and analyze endpoint performance metrics.
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics collector.

        Args:
            max_history: Maximum metrics to keep in history
        """
        self.max_history = max_history
        self.metrics: list = []
        self.summary = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_time_ms": 0.0,
            "tier1_hits": 0,
            "tier2_hits": 0
        }

    def record(
        self,
        endpoint: str,
        cache_source: str,
        processing_time_ms: float,
        success: bool = True
    ) -> None:
        """
        Record an endpoint request metric.

        Args:
            endpoint: Endpoint path
            cache_source: Cache tier (tier1, tier2, miss)
            processing_time_ms: Processing time in milliseconds
            success: Whether request succeeded
        """
        metric = {
            "endpoint": endpoint,
            "cache_source": cache_source,
            "processing_time_ms": processing_time_ms,
            "success": success,
            "timestamp": time.time()
        }

        self.metrics.append(metric)

        # Trim history
        if len(self.metrics) > self.max_history:
            self.metrics.pop(0)

        # Update summary
        self._update_summary()

    def _update_summary(self) -> None:
        """Update summary statistics."""
        if not self.metrics:
            return

        self.summary["total_requests"] = len(self.metrics)
        self.summary["cache_hits"] = sum(
            1 for m in self.metrics if m["cache_source"] != "miss"
        )
        self.summary["cache_misses"] = sum(
            1 for m in self.metrics if m["cache_source"] == "miss"
        )
        self.summary["tier1_hits"] = sum(
            1 for m in self.metrics if m["cache_source"] == "tier1"
        )
        self.summary["tier2_hits"] = sum(
            1 for m in self.metrics if m["cache_source"] == "tier2"
        )

        # Average processing time
        total_time = sum(m["processing_time_ms"] for m in self.metrics)
        self.summary["avg_time_ms"] = round(total_time / len(self.metrics), 2)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        return self.summary.copy()

    def get_tier_stats(self) -> Dict[str, Any]:
        """Get cache tier statistics."""
        if not self.metrics:
            return {
                "tier1_percent": 0.0,
                "tier2_percent": 0.0,
                "miss_percent": 0.0
            }

        total = len(self.metrics)

        return {
            "tier1_percent": round(self.summary["tier1_hits"] / total * 100, 1),
            "tier2_percent": round(self.summary["tier2_hits"] / total * 100, 1),
            "miss_percent": round(self.summary["cache_misses"] / total * 100, 1),
            "hit_rate": round(self.summary["cache_hits"] / total, 3)
        }

    def get_performance_trends(self, window: int = 10) -> Dict[str, Any]:
        """
        Get performance trends over recent requests.

        Args:
            window: Number of recent requests to analyze

        Returns:
            Dictionary with performance trends
        """
        recent = self.metrics[-window:] if len(self.metrics) >= window else self.metrics

        if not recent:
            return {"avg_time_ms": 0.0, "trend": "none"}

        recent_time = sum(m["processing_time_ms"] for m in recent) / len(recent)
        overall_time = self.summary["avg_time_ms"]

        if recent_time > overall_time * 1.1:
            trend = "degrading"
        elif recent_time < overall_time * 0.9:
            trend = "improving"
        else:
            trend = "stable"

        return {
            "avg_time_ms": round(recent_time, 2),
            "overall_avg_ms": overall_time,
            "trend": trend,
            "window": len(recent)
        }

    def clear(self) -> None:
        """Clear all metrics."""
        self.metrics.clear()
        self.summary = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_time_ms": 0.0,
            "tier1_hits": 0,
            "tier2_hits": 0
        }


def create_cache_aware_handler(
    cache_manager,
    handler: Callable[..., Awaitable[tuple[Any, str]]],
    metrics: Optional[EndpointMetrics] = None
) -> Callable:
    """
    Create a cache-aware handler with automatic metrics.

    Args:
        cache_manager: StreamlinedCacheManager instance
        handler: Original async handler
        metrics: Optional EndpointMetrics for tracking

    Returns:
        Wrapped handler with caching and metrics
    """
    @wraps(handler)
    async def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            data, cache_source = await handler(*args, **kwargs)
            processing_time_ms = (time.time() - start_time) * 1000

            # Record metrics if available
            if metrics:
                endpoint = getattr(handler, '__name__', 'unknown')
                metrics.record(endpoint, cache_source, processing_time_ms)

            return {
                "data": data,
                "cache_source": cache_source,
                "cache_hit": cache_source != "miss",
                "processing_time_ms": round(processing_time_ms, 2)
            }

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000

            # Record failure
            if metrics:
                endpoint = getattr(handler, '__name__', 'unknown')
                metrics.record(endpoint, "error", processing_time_ms, success=False)

            raise

    return wrapper
