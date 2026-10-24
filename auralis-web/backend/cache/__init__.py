"""
Auralis Cache System
~~~~~~~~~~~~~~~~~~~~

Unified cache management system with two-tier caching strategy:
- Tier 1 (Hot): Current + next chunk for instant playback (12 MB)
- Tier 2 (Warm): Full track cache for instant seeking (60-120 MB)

The real cache HTTP surface lives in routers/cache_streamlined.py — do
not add a second helper layer ahead of the endpoints that would use it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .manager import StreamlinedCacheManager, streamlined_cache_manager

__all__ = [
    "StreamlinedCacheManager",
    "streamlined_cache_manager",
]
