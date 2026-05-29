"""
Cache Management API Router (Streamlined - Beta.9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

API endpoints for streamlined two-tier cache management and statistics.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Annotated, Any
from collections.abc import Callable

from cache import StreamlinedCacheManager
from fastapi import Path, APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics.

    NOTE: schemas.CacheStatsResponse / CacheTierStats / OverallCacheStats
    expose properly-typed nested fields (#3548 / BE-NEW-90). This local
    copy uses dict[str, Any] to absorb the StreamlinedCacheManager.get_stats()
    return shape verbatim. Migrating to the schemas.py version is a
    follow-up that needs to verify the get_stats() dict matches the
    typed model field-for-field.
    """
    tier1: dict[str, Any]
    tier2: dict[str, Any]
    overall: dict[str, Any]
    tracks: dict[int, dict[str, Any]]


class TrackCacheStatus(BaseModel):
    """Model for track cache status (see schemas.TrackCacheStatusResponse
    for the canonical fully-typed version, #3548 / BE-NEW-90)."""
    track_id: int
    total_chunks: int
    cached_original: int
    cached_processed: int
    completion_percent: float
    fully_cached: bool


def _require_cache(
    get_cache_manager: Callable[[], StreamlinedCacheManager | None],
) -> StreamlinedCacheManager:
    """Return the cache manager or raise 503 if not yet initialised."""
    mgr = get_cache_manager()
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="Cache manager is not yet initialised",
        )
    return mgr


def create_streamlined_cache_router(
    get_cache_manager: Callable[[], StreamlinedCacheManager | None],
    broadcast_manager: Any | None = None
) -> APIRouter:
    """
    Create streamlined cache management router.

    Args:
        get_cache_manager: Callable that returns the StreamlinedCacheManager
            (or None before lifespan has initialised it).
        broadcast_manager: Optional broadcast manager for notifications

    Returns:
        FastAPI router with cache endpoints
    """
    router = APIRouter(prefix="/api/cache", tags=["cache"])

    @router.get("/stats", response_model=CacheStatsResponse)
    async def get_cache_stats() -> CacheStatsResponse:
        """
        Get comprehensive cache statistics.

        Returns detailed statistics for both cache tiers including:
        - Tier 1 (Hot): Current + next chunk stats
        - Tier 2 (Warm): Full track cache stats
        - Overall hit rates and memory usage
        - Per-track cache completion status
        """
        cache_manager = _require_cache(get_cache_manager)
        try:
            stats = await asyncio.to_thread(cache_manager.get_stats)
            return CacheStatsResponse(**stats)
        except Exception:
            # Don't leak DB / filesystem details to the client (#3500 / BE-27).
            logger.exception("Error getting cache stats")
            raise HTTPException(status_code=500, detail="Failed to get cache stats")

    @router.get("/track/{track_id}/status", response_model=TrackCacheStatus)
    async def get_track_cache_status(track_id: int) -> TrackCacheStatus:
        """
        Get cache status for a specific track.

        Args:
            track_id: Track ID

        Returns:
            Cache status including completion percentage and chunk counts
        """
        cache_manager = _require_cache(get_cache_manager)
        try:
            status = await asyncio.to_thread(cache_manager.get_track_cache_status, track_id)

            if status is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Track {track_id} not found in cache"
                )

            return TrackCacheStatus(
                track_id=status.track_id,
                total_chunks=status.total_chunks,
                cached_original=len(status.cached_chunks_original),
                cached_processed=len(status.cached_chunks_processed),
                completion_percent=status.get_completion_percent(),
                fully_cached=status.is_fully_cached()
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception(f"Error getting track cache status (track {track_id})")
            raise HTTPException(status_code=500, detail="Failed to get track cache status")

    @router.delete("/track/{track_id}")
    async def clear_track_cache(track_id: int) -> dict[str, Any]:
        """Clear cached data for a single track."""
        cache_manager = _require_cache(get_cache_manager)
        try:
            removed = await cache_manager.clear_track(track_id)
            return {"message": f"Cleared cache for track {track_id}", "removed": removed}
        except Exception:
            logger.exception(f"Error clearing cache for track {track_id}")
            raise HTTPException(status_code=500, detail="Failed to clear track cache")

    @router.post("/clear")
    async def clear_cache() -> dict[str, str]:
        """
        Clear all caches (Tier 1 and Tier 2).

        Use with caution - this will force re-processing of all chunks.
        """
        cache_manager = _require_cache(get_cache_manager)
        try:
            await cache_manager.clear_all()

            # Broadcast cache cleared event using the canonical {type, data}
            # envelope (#3545 / BE-NEW-87). Wrap the message in `data` so
            # the frontend dispatcher does not classify it as unknown.
            if broadcast_manager:
                await broadcast_manager.broadcast({
                    "type": "cache_cleared",
                    "data": {"message": "All caches cleared"},
                })

            return {"message": "All caches cleared successfully"}
        except Exception:
            logger.exception("Error clearing cache")
            raise HTTPException(status_code=500, detail="Failed to clear cache")

    @router.get("/health")
    async def cache_health() -> dict[str, Any]:
        """
        Get cache system health status.

        Returns:
            Health information including memory usage and worker status
        """
        cache_manager = _require_cache(get_cache_manager)
        try:
            stats = await asyncio.to_thread(cache_manager.get_stats)

            overall = stats["overall"]
            tier1 = stats["tier1"]
            tier2 = stats["tier2"]

            # Calculate health metrics
            tier1_healthy = tier1["size_mb"] <= 15  # Should be ~12 MB
            tier2_healthy = tier2["size_mb"] <= 250  # Max 240 MB
            memory_healthy = overall["total_size_mb"] <= 260

            return {
                "healthy": tier1_healthy and tier2_healthy and memory_healthy,
                "tier1_size_mb": tier1["size_mb"],
                "tier1_healthy": tier1_healthy,
                "tier2_size_mb": tier2["size_mb"],
                "tier2_healthy": tier2_healthy,
                "total_size_mb": overall["total_size_mb"],
                "memory_healthy": memory_healthy,
                "tier1_hit_rate": tier1["hit_rate"],
                "overall_hit_rate": overall["overall_hit_rate"]
            }
        except Exception:
            logger.exception("Error checking cache health")
            raise HTTPException(status_code=500, detail="Failed to check cache health")

    return router
