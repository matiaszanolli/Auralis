"""
Cache Management API Router (Streamlined - Beta.9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

API endpoints for streamlined two-tier cache management and statistics.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path as FilePath
from typing import Annotated, Any

from cache import StreamlinedCacheManager
from cache.models import CHUNK_SIZE_MB, TIER1_MAX_SIZE_MB, TIER2_MAX_SIZE_MB
from config.limits import chunk_cache_dir
from core.chunk_disk_prune import chunk_directory_stats
from core.cache_cleanup import clear_all_caches, clear_track_caches
from core.thumbnail_cache import artwork_cache_root
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

# The typed contracts (#3548, #4755); get_stats()'s shape matches them except tier_name, filled in below.
from schemas import CacheHealthResponse, CacheStatsResponse, TrackCacheStatusResponse
from websocket.outbound_messages import broadcast_typed

from .errors import NotFoundError, ServiceUnavailableError
from .dependencies import RouterDeps, with_error_handling

logger = logging.getLogger(__name__)


class ClearTrackCacheResponse(BaseModel):
    """Result of clearing one track."""
    message: str = Field(description="Human-readable confirmation")
    removed: int = Field(description="Number of on-disk chunk files removed")


class ClearCacheResponse(BaseModel):
    """Result of clearing every cache tier."""
    message: str = Field(description="Human-readable confirmation")


def _require_cache(
    get_cache_manager: Callable[[], StreamlinedCacheManager | None],
) -> StreamlinedCacheManager:
    """Return the cache manager or raise 503 if not yet initialised."""
    mgr = get_cache_manager()
    if mgr is None:
        raise ServiceUnavailableError("Cache manager is not yet initialised")
    return mgr


class _CacheDeps:
    def __init__(
        self,
        get_cache_manager: Callable[[], StreamlinedCacheManager | None] = lambda: None,
        broadcast_manager: Any | None = None,
        get_artwork_cache_dir: Callable[[], FilePath] = artwork_cache_root,
    ) -> None:
        self.get_cache_manager = get_cache_manager
        self.broadcast_manager = broadcast_manager
        self.get_artwork_cache_dir = get_artwork_cache_dir


_deps = RouterDeps("cache_streamlined", _CacheDeps())


def _get_deps() -> _CacheDeps:
    return _deps.current()


def _get_cache_manager(deps: _CacheDeps = Depends(_get_deps)) -> StreamlinedCacheManager:
    """The cache manager for this request, or 503 before lifespan set it up."""
    return _require_cache(deps.get_cache_manager)


def _get_optional_cache_manager(deps: _CacheDeps = Depends(_get_deps)) -> StreamlinedCacheManager | None:
    """The manager if up; clearing sweeps the chunk directory without it."""
    return deps.get_cache_manager()


@with_error_handling("get cache stats")
async def get_cache_stats(cache_manager: StreamlinedCacheManager = Depends(_get_cache_manager)) -> CacheStatsResponse:
    """
    Get comprehensive cache statistics.

    Returns detailed statistics for both cache tiers including:
    - Tier 1 (Hot): Current + next chunk stats
    - Tier 2 (Warm): Full track cache stats
    - Overall hit rates and memory usage
    - Per-track cache completion status
    """
    # On the loop, not a thread: no I/O, and it iterates dicts the loop mutates (#6003).
    stats = cache_manager.get_stats()
    # CacheTierStats requires tier_name, which get_stats() cannot derive; fill it in here.
    stats["tier1"]["tier_name"] = "tier1"
    stats["tier2"]["tier_name"] = "tier2"
    # The tiers only record the worker's chunks; this directory is what serves (#6002).
    stats["chunk_directory"] = await asyncio.to_thread(chunk_directory_stats, chunk_cache_dir())
    return CacheStatsResponse(**stats)


@with_error_handling("get track cache status")
async def get_track_cache_status(
    track_id: Annotated[int, Path(ge=1)],
    cache_manager: StreamlinedCacheManager = Depends(_get_cache_manager),
) -> TrackCacheStatusResponse:
    """
    Get cache status for a specific track.

    Args:
        track_id: Track ID

    Returns:
        Cache status including completion percentage and chunk counts
    """
    try:
        status = cache_manager.get_track_cache_status(track_id)  # on the loop with the state it reads (#6003)

        if status is None:
            raise NotFoundError("Track", detail=f"Track {track_id} not found in cache")

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


@with_error_handling("clear track cache")
async def clear_track_cache(
    track_id: Annotated[int, Path(ge=1)],
    cache_manager: StreamlinedCacheManager | None = Depends(_get_optional_cache_manager),
) -> dict[str, Any]:
    """Clear cached data for a single track; reports the on-disk chunk files deleted."""
    removed = await clear_track_caches(cache_manager, track_id)
    return {"message": f"Cleared cache for track {track_id}", "removed": removed}


@with_error_handling("clear cache")
async def clear_cache(
    cache_manager: StreamlinedCacheManager | None = Depends(_get_optional_cache_manager),
    deps: _CacheDeps = Depends(_get_deps),
) -> dict[str, str]:
    """
    Clear chunk, derived-thumbnail, and analysis caches.

    Use with caution - this will force re-processing of all chunks.
    """
    await clear_all_caches(cache_manager, deps.get_artwork_cache_dir())

    # Broadcast cache cleared event using the canonical {type, data}
    # envelope (#3545 / BE-NEW-87). Wrap the message in `data` so
    # the frontend dispatcher does not classify it as unknown.
    if deps.broadcast_manager:
        await broadcast_typed(
            deps.broadcast_manager,
            "cache_cleared",
            {"message": "All caches cleared"},
        )

    return {"message": "All caches cleared successfully"}


@with_error_handling("check cache health")
async def cache_health(cache_manager: StreamlinedCacheManager = Depends(_get_cache_manager)) -> CacheHealthResponse:
    """Get cache system health: memory usage against the tier budgets."""
    stats = cache_manager.get_stats()  # on the loop, see get_cache_stats (#6003)

    overall = stats["overall"]
    tier1 = stats["tier1"]
    tier2 = stats["tier2"]

    # The cache's own budgets (#5971) plus one chunk, resident until eviction runs.
    tier1_healthy = tier1["size_mb"] <= TIER1_MAX_SIZE_MB + CHUNK_SIZE_MB
    tier2_healthy = tier2["size_mb"] <= TIER2_MAX_SIZE_MB + CHUNK_SIZE_MB
    memory_healthy = overall["total_size_mb"] <= TIER1_MAX_SIZE_MB + TIER2_MAX_SIZE_MB + CHUNK_SIZE_MB

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


def create_streamlined_cache_router(
    get_cache_manager: Callable[[], StreamlinedCacheManager | None],
    broadcast_manager: Any | None = None,
    get_artwork_cache_dir: Callable[[], FilePath] = artwork_cache_root,
) -> APIRouter:
    """
    Create streamlined cache management router.

    Args:
        get_cache_manager: Callable that returns the StreamlinedCacheManager
            (or None before lifespan has initialised it).
        broadcast_manager: Optional broadcast manager for notifications
        get_artwork_cache_dir: Returns the source-artwork cache root. Injectable
            so tests and alternate deployments never clear a real user cache.

    Returns:
        FastAPI router with cache endpoints
    """
    deps = _CacheDeps(get_cache_manager, broadcast_manager, get_artwork_cache_dir)
    router = APIRouter(
        prefix="/api/cache", tags=["cache"], dependencies=[Depends(_deps.bind(deps))]
    )
    router.add_api_route("/stats", get_cache_stats, methods=["GET"], response_model=CacheStatsResponse)
    router.add_api_route("/track/{track_id}/status", get_track_cache_status, methods=["GET"], response_model=TrackCacheStatusResponse)
    router.add_api_route("/track/{track_id}", clear_track_cache, methods=["DELETE"], response_model=ClearTrackCacheResponse)
    router.add_api_route("/clear", clear_cache, methods=["POST"], response_model=ClearCacheResponse)
    router.add_api_route("/health", cache_health, methods=["GET"], response_model=CacheHealthResponse)
    return router
