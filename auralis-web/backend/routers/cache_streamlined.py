"""
Cache Management API Router (Streamlined - Beta.9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

API endpoints for streamlined two-tier cache management and statistics.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any

from cache import StreamlinedCacheManager
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics."""
    tier1: dict[str, Any]
    tier2: dict[str, Any]
    overall: dict[str, Any]
    tracks: dict[int, dict[str, Any]]


class TrackCacheStatus(BaseModel):
    """Model for track cache status."""
    track_id: int
    total_chunks: int
    cached_original: int
    cached_processed: int
    completion_percent: float
    fully_cached: bool


def create_streamlined_cache_router(
    cache_manager: StreamlinedCacheManager,
    broadcast_manager: Any | None = None
) -> APIRouter:
    """
    Create streamlined cache management router.

    Args:
        cache_manager: StreamlinedCacheManager instance
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
        try:
            stats = cache_manager.get_stats()
            return CacheStatsResponse(**stats)
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/track/{track_id}/status", response_model=TrackCacheStatus)
    async def get_track_cache_status(track_id: int) -> TrackCacheStatus:
        """
        Get cache status for a specific track.

        Args:
            track_id: Track ID

        Returns:
            Cache status including completion percentage and chunk counts
        """
        try:
            status = cache_manager.get_track_cache_status(track_id)

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
        except Exception as e:
            logger.error(f"Error getting track cache status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/clear")
    async def clear_cache() -> dict[str, str]:
        """
        Clear all caches (Tier 1 and Tier 2).

        Use with caution - this will force re-processing of all chunks.
        """
        try:
            await cache_manager.clear_all()

            # Broadcast cache cleared event
            if broadcast_manager:
                await broadcast_manager.broadcast({
                    "type": "cache_cleared",
                    "message": "All caches cleared"
                })

            return {"message": "All caches cleared successfully"}
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/health")
    async def cache_health() -> dict[str, Any]:
        """
        Get cache system health status.

        Returns:
            Health information including memory usage and worker status
        """
        try:
            stats = cache_manager.get_stats()

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
        except Exception as e:
            logger.error(f"Error checking cache health: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
