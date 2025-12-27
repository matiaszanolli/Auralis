"""
Auralis Cache System
~~~~~~~~~~~~~~~~~~~~

Unified cache management system with two-tier caching strategy:
- Tier 1 (Hot): Current + next chunk for instant playback (12 MB)
- Tier 2 (Warm): Full track cache for instant seeking (60-120 MB)

Also includes monitoring and endpoint utilities for cache-aware operations.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .adapter import StreamlinedCacheAdapter
from .endpoints import (
    CacheAwareEndpoint,
    CacheQueryBuilder,
    EndpointMetrics,
    create_cache_aware_handler,
)
from .manager import (
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    CHUNK_SIZE_MB,
    TIER1_MAX_CHUNKS,
    TIER1_MAX_SIZE_MB,
    TIER2_MAX_SIZE_MB,
    TIER2_MAX_TRACKS,
    CachedChunk,
    StreamlinedCacheManager,
    TrackCacheStatus,
    streamlined_cache_manager,
)
from .monitoring import (
    CacheAlert,
    CacheMetrics,
    CacheMonitor,
    HealthStatus,
)

__all__ = [
    # Manager exports
    "StreamlinedCacheManager",
    "streamlined_cache_manager",
    "CachedChunk",
    "TrackCacheStatus",
    "CHUNK_DURATION",
    "CHUNK_INTERVAL",
    "CHUNK_SIZE_MB",
    "TIER1_MAX_CHUNKS",
    "TIER1_MAX_SIZE_MB",
    "TIER2_MAX_TRACKS",
    "TIER2_MAX_SIZE_MB",
    # Adapter exports
    "StreamlinedCacheAdapter",
    # Monitoring exports
    "CacheMonitor",
    "CacheMetrics",
    "CacheAlert",
    "HealthStatus",
    # Endpoints exports
    "CacheAwareEndpoint",
    "CacheQueryBuilder",
    "EndpointMetrics",
    "create_cache_aware_handler",
]
