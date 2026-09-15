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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

# Import each name from the module that defines it. cache.manager only
# re-imports the chunk geometry and the tier/record types, and under the strict
# mypy override for cache.* (#5437) a pass-through import is not an export.
from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL

from .manager import StreamlinedCacheManager, streamlined_cache_manager
from .models import (
    CHUNK_SIZE_MB,
    TIER1_MAX_CHUNKS,
    TIER1_MAX_SIZE_MB,
    TIER2_MAX_SIZE_MB,
    TIER2_MAX_TRACKS,
    CachedChunk,
    TrackCacheStatus,
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
