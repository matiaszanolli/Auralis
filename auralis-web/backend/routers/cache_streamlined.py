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
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

# The canonical, fully-typed contracts (#3548 / BE-NEW-90, #4755): this router
# used to declare its own same-named CacheStatsResponse/TrackCacheStatus with
# dict[str, Any] fields, absorbing StreamlinedCacheManager.get_stats()'s shape
# verbatim without ever validating it against the typed schema — two classes
# with the same name existed in the process, and the typed one was never what
# actually went on the wire. get_stats()'s shape has been verified
# field-for-field against these models: the one gap (CacheTierStats.tier_name,
# which get_stats() doesn't produce) is filled in below before validation.
from schemas import CacheHealthResponse, CacheStatsResponse, TrackCacheStatusResponse

from .dependencies import with_error_handling

logger = logging.getLogger(__name__)


class ClearTrackCacheResponse(BaseModel):
    """Result of clearing one track's cached chunks."""
    message: str = Field(description="Human-readable confirmation")
    removed: int = Field(description="Number of cached chunks removed")


class ClearCacheResponse(BaseModel):
    """Result of clearing every cache tier."""
    message: str = Field(description="Human-readable confirmation")


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
    @with_error_handling("get cache stats")
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
        stats = await asyncio.to_thread(cache_manager.get_stats)
        # get_stats()'s tier1/tier2 dicts don't carry a tier_name field
        # (there's nothing to derive it from once the two dicts are
        # separate) — CacheTierStats requires it, so fill it in here at
        # the one place that knows which dict is which.
        stats["tier1"]["tier_name"] = "tier1"
        stats["tier2"]["tier_name"] = "tier2"
        return CacheStatsResponse(**stats)

    @router.get("/track/{track_id}/status", response_model=TrackCacheStatusResponse)
    @with_error_handling("get track cache status")
    async def get_track_cache_status(track_id: Annotated[int, Path(ge=1)]) -> TrackCacheStatusResponse:
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

            return TrackCacheStatusResponse(
                track_id=status.track_id,
                total_chunks=status.total_chunks,
                cached_original=len(status.cached_chunks_original),
                cached_processed=len(status.cached_chunks_processed),
                completion_percent=status.get_completion_percent(),
                fully_cached=status.is_fully_cached()
            )
        except HTTPException:
            raise

    @router.delete("/track/{track_id}", response_model=ClearTrackCacheResponse)
    @with_error_handling("clear track cache")
    async def clear_track_cache(track_id: Annotated[int, Path(ge=1)]) -> dict[str, Any]:
        """Clear cached data for a single track."""
        cache_manager = _require_cache(get_cache_manager)
        removed = await cache_manager.clear_track(track_id)
        return {"message": f"Cleared cache for track {track_id}", "removed": removed}

    @router.post("/clear", response_model=ClearCacheResponse)
    @with_error_handling("clear cache")
    async def clear_cache() -> dict[str, str]:
        """
        Clear all caches (Tier 1 and Tier 2).

        Use with caution - this will force re-processing of all chunks.
        """
        cache_manager = _require_cache(get_cache_manager)
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

    @router.get("/health", response_model=CacheHealthResponse)
    @with_error_handling("check cache health")
    async def cache_health() -> CacheHealthResponse:
        """
        Get cache system health status.

        Returns:
            Health information including memory usage and worker status
        """
        cache_manager = _require_cache(get_cache_manager)
        stats = await asyncio.to_thread(cache_manager.get_stats)

        overall = stats["overall"]
        tier1 = stats["tier1"]
        tier2 = stats["tier2"]

        # Calculate health metrics
        tier1_healthy = tier1["size_mb"] <= 15  # Should be ~12 MB
        tier2_healthy = tier2["size_mb"] <= 250  # Max 240 MB
        memory_healthy = overall["total_size_mb"] <= 260

        return CacheHealthResponse(
            healthy=tier1_healthy and tier2_healthy and memory_healthy,
            tier1_size_mb=tier1["size_mb"],
            tier1_healthy=tier1_healthy,
            tier2_size_mb=tier2["size_mb"],
            tier2_healthy=tier2_healthy,
            total_size_mb=overall["total_size_mb"],
            memory_healthy=memory_healthy,
            tier1_hit_rate=tier1["hit_rate"],
            overall_hit_rate=overall["overall_hit_rate"],
        )

    return router
