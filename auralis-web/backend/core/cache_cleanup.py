"""Unified lifecycle boundary for every backend cache tier (#5257)."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from config.limits import chunk_cache_dir

from core.encoding.wav_encoder import delete_chunk_files
from core.mastering_target_service import clear_global_mastering_target_cache
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
    chunk_files_removed: int = 0


async def clear_all_caches(
    cache_manager: ClearableChunkCache | None,
    artwork_dir: Path,
    *,
    clear_source_artwork: bool = False,
    chunk_dir: Path | None = None,
) -> CacheClearResult:
    """Clear chunk, thumbnail, and track-analysis caches.

    ``cache_manager`` may be absent during a library reset when the streamlined
    cache feature is disabled; the filesystem and analysis tiers are still
    cleared. The analysis tier is MasteringTargetService's per-track
    fingerprint/target cache (#5085); ``analysis_cache_cleared`` is False only
    when that service was never created in this process. Source artwork is
    retained by default because live album rows point at those files; a
    destructive library reset passes ``clear_source_artwork=True`` after
    deleting those rows. Blocking directory work runs off the event loop.

    The on-disk chunk directory (``chunk_dir``, default the shared chunk cache)
    is swept whether or not ``cache_manager`` exists (#5340): the manager's
    tiers only record the streamlined worker's chunks, while live playback
    writes its own files there, found later by name alone.
    """
    if cache_manager is not None:
        await cache_manager.clear_all()
    chunk_files_removed = await asyncio.to_thread(
        delete_chunk_files, chunk_dir if chunk_dir is not None else chunk_cache_dir()
    )

    cleanup_root = artwork_dir if clear_source_artwork else artwork_dir / "thumbnails"
    files_removed, bytes_reclaimed = await asyncio.to_thread(clear_artwork_cache, cleanup_root)
    return CacheClearResult(
        artwork_files_removed=files_removed,
        artwork_bytes_reclaimed=bytes_reclaimed,
        analysis_cache_cleared=clear_global_mastering_target_cache(),
        chunk_files_removed=chunk_files_removed,
    )
