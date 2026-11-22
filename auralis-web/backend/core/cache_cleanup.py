"""Unified lifecycle boundary for every backend cache tier (#5257)."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from config.limits import chunk_cache_dir

from auralis.analysis.fingerprint.fingerprint_store_maintenance import clear_all_entries, sweep_orphans

from core.encoding.atomic_io import is_partial_path
from core.mastering_target_service import (
    clear_global_mastering_target_cache,
    clear_global_mastering_target_entry,
)
from core.thumbnail_cache import clear_artwork_cache

logger = logging.getLogger(__name__)


class ClearableChunkCache(Protocol):
    """Minimum chunk-cache contract needed by the global cleanup boundary."""

    async def clear_all(self) -> None: ...

    async def clear_track(self, track_id: int) -> int: ...


@dataclass(frozen=True)
class CacheClearResult:
    """Observable cleanup totals for tests, logs, and future API expansion."""

    artwork_files_removed: int
    artwork_bytes_reclaimed: int
    analysis_cache_cleared: bool
    chunk_files_removed: int = 0
    fingerprint_files_removed: int = 0


def delete_chunk_files(
    chunk_dir: Path,
    track_id: int | None = None,
    file_signature: str | None = None,
) -> int:
    """Delete published chunk WAVs from *chunk_dir* (#5340).

    The on-disk chunk cache is found by name alone (``get_chunk_path`` +
    ``Path.exists()``), whoever wrote the file — live playback, the streamlined
    worker or pre-warm — so clearing it means sweeping the directory, not just
    the paths a cache tier recorded. Scoped to one track (optionally one file
    signature) or, with ``track_id`` None, every chunk.

    In-progress staged writes (#4576) are left alone: deleting one would make
    its writer's ``os.replace()`` fail mid-stream. A missing directory is
    simply nothing to delete.

    Returns:
        Number of files deleted
    """
    if track_id is None:
        patterns = ["*.wav"]
    else:
        # The trailing "_" keeps track 1 from matching track 12's files.
        signature = f"{file_signature}_" if file_signature is not None else ""
        patterns = [
            f"track_{track_id}_{signature}*.wav",  # Pre-versioning format
            f"v*_track_{track_id}_{signature}*.wav",  # Versioned format
        ]
    files = {
        f
        for pattern in patterns
        for f in chunk_dir.glob(pattern)
        if not is_partial_path(f)
    }

    deleted_count = 0
    for f in files:
        try:
            f.unlink()
            deleted_count += 1
        except FileNotFoundError:
            pass  # Removed concurrently (another clear, or the size pruner)
        except OSError as e:
            logger.warning(f"Failed to delete chunk file {f}: {e}")

    if deleted_count > 0:
        scope = "all tracks" if track_id is None else f"track {track_id}"
        logger.info(f"Cleaned up {deleted_count} chunk file(s) for {scope}")

    return deleted_count


async def clear_track_caches(
    cache_manager: ClearableChunkCache | None,
    track_id: int,
    *,
    chunk_dir: Path | None = None,
) -> int:
    """Clear one track's chunk files and analysis entry; returns the chunk files deleted.

    Like clear_all_caches, the on-disk sweep runs whether or not the streamlined manager
    exists, so the "clear and retry" lever survives the worker dying (#6002).
    """
    if cache_manager is not None:
        removed = await cache_manager.clear_track(track_id)
    else:
        removed = await asyncio.to_thread(
            delete_chunk_files, chunk_dir if chunk_dir is not None else chunk_cache_dir(), track_id
        )
    clear_global_mastering_target_entry(track_id)
    return removed


async def clear_all_caches(
    cache_manager: ClearableChunkCache | None,
    artwork_dir: Path,
    *,
    clear_source_artwork: bool = False,
    chunk_dir: Path | None = None,
    clear_fingerprint_store: bool = False,
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

    The central ``.25d`` fingerprint store (#6004) only ever has its dead entries swept here - a
    Clear Cache click must not throw away live, expensive analysis - unless
    ``clear_fingerprint_store`` is set, which a library reset does: every track it described is gone.
    """
    if cache_manager is not None:
        await cache_manager.clear_all()
    chunk_files_removed = await asyncio.to_thread(
        delete_chunk_files, chunk_dir if chunk_dir is not None else chunk_cache_dir()
    )

    cleanup_root = artwork_dir if clear_source_artwork else artwork_dir / "thumbnails"
    files_removed, bytes_reclaimed = await asyncio.to_thread(clear_artwork_cache, cleanup_root)
    fingerprint_files_removed = await asyncio.to_thread(
        clear_all_entries if clear_fingerprint_store else sweep_orphans
    )
    return CacheClearResult(
        artwork_files_removed=files_removed,
        artwork_bytes_reclaimed=bytes_reclaimed,
        analysis_cache_cleared=clear_global_mastering_target_cache(),
        chunk_files_removed=chunk_files_removed,
        fingerprint_files_removed=fingerprint_files_removed,
    )
