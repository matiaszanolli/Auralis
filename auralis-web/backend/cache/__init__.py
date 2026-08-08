"""
Auralis Cache System
~~~~~~~~~~~~~~~~~~~~

Unified cache management system with two-tier caching strategy:
- Tier 1 (Hot): Current + next chunk for instant playback (12 MB)
- Tier 2 (Warm): Full track cache for instant seeking (60-120 MB)

Also includes monitoring utilities for cache-aware operations. The real
cache HTTP surface lives in routers/cache_streamlined.py; endpoints.py
(a second, never-wired "cache-aware endpoint" helper layer built for the
retired REST/MSE chunk-streaming surface, #4435) was deleted as dead code
with zero production importers (#4738).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

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
    # Monitoring exports
    "CacheMonitor",
    "CacheMetrics",
    "CacheAlert",
    "HealthStatus",
]
