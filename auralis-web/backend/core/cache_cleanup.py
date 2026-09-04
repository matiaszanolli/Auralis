"""Unified lifecycle boundary for every backend cache tier (#5257)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from analysis.track_analysis_cache import clear_global_track_analysis_cache
from core.thumbnail_cache import clear_artwork_cache


class ClearableChunkCache(Protocol):
    """Minimum chunk-cache contract needed by the global cleanup boundary."""

    async def clear_all(self) -> None: ...


@dataclass(frozen=True)
class CacheClearResult:
    """Observable cleanup totals for tests, logs, and future API expansion."""

    artwork_files_removed: int
    artwork_bytes_reclaimed: int
    analysis_cache_cleared: bool


async def clear_all_caches(
    cache_manager: ClearableChunkCache | None,
    artwork_dir: Path,
    *,
    clear_source_artwork: bool = False,
) -> CacheClearResult:
    """Clear chunk, thumbnail, and optional analysis caches.

    ``cache_manager`` may be absent during a library reset when the streamlined
    cache feature is disabled; the filesystem and analysis tiers are still
    cleared. Source artwork is retained by default because live album rows
    point at those files; a destructive library reset passes
    ``clear_source_artwork=True`` after deleting those rows. Blocking directory
    work runs off the event loop.
    """
    if cache_manager is not None:
        await cache_manager.clear_all()

    cleanup_root = artwork_dir if clear_source_artwork else artwork_dir / "thumbnails"
    files_removed, bytes_reclaimed = await asyncio.to_thread(clear_artwork_cache, cleanup_root)
    return CacheClearResult(
        artwork_files_removed=files_removed,
        artwork_bytes_reclaimed=bytes_reclaimed,
        analysis_cache_cleared=clear_global_track_analysis_cache(),
    )
