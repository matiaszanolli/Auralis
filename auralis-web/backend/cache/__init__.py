"""
Auralis Cache System
~~~~~~~~~~~~~~~~~~~~

Unified cache management system with two-tier caching strategy:
- Tier 1 (Hot): Current + next chunk for instant playback (12 MB)
- Tier 2 (Warm): Full track cache for instant seeking (60-120 MB)

The real cache HTTP surface lives in routers/cache_streamlined.py; endpoints.py
(a second, never-wired "cache-aware endpoint" helper layer built for the
retired REST/MSE chunk-streaming surface, #4435) was deleted as dead code
with zero production importers (#4738).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .manager import StreamlinedCacheManager, streamlined_cache_manager

__all__ = [
    "StreamlinedCacheManager",
    "streamlined_cache_manager",
]
