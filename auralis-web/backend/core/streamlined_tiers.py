"""
Streamlined Cache Worker Tier Scheduling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tier-priority scheduling for ``StreamlinedCacheWorker``, split out of
``core/streamlined_worker.py`` (#5037) so scheduling-policy work and the
processor cache/lock bookkeeping (``core/streamlined_processor_cache.py``) stop
sharing one module.

Every function here takes the worker as its first argument and is bound into
the ``StreamlinedCacheWorker`` class body under its original name, so call
sites, method signatures and per-instance monkeypatching are unchanged by the
split.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from core.file_signature import FileSignatureService
from core.streamlined_processor_cache import prune_processors_for_track


logger = logging.getLogger(__name__)


async def process_priorities(worker: Any) -> None:
    """
    Process caching priorities:
    1. Next chunk (Tier 1 - critical)
    2. Full track cache (Tier 2 - background)
    3. Previous track (Tier 2 - nice to have)
    """
    # #4546: one snapshot under the cache manager's lock instead of four
    # separate unsynchronised reads. Previously a track or preset change
    # landing between any two of them produced a mismatched tuple — e.g.
    # track A's id with track B's position, giving a chunk index past A's
    # end — and the `to_thread` DB round-trip below widened that window
    # from "between two attribute reads" to a full query.
    snapshot = await worker.cache_manager.get_playback_snapshot()
    if snapshot is None:
        return  # No track playing

    track_id = snapshot.track_id
    current_chunk = snapshot.chunk_idx
    preset = snapshot.preset
    intensity = snapshot.intensity

    # Get track from library (sync DB call — offload to thread)
    track = await asyncio.to_thread(worker.library_manager.tracks.get_by_id, track_id)
    if not track:
        logger.warning(f"Track {track_id} not found in library")
        return

    # Re-validate after the await: if playback moved to another track while
    # the query was in flight, abandon this tick rather than caching chunks
    # under the previous track's key. The next tick picks up the new track.
    if worker.cache_manager.current_track_id != track_id:
        logger.debug(
            f"Track changed during priority processing "
            f"({track_id} -> {worker.cache_manager.current_track_id}); skipping tick"
        )
        return

    status = worker.cache_manager.get_track_cache_status(track_id)
    if status is None:
        logger.debug(f"Track {track_id} cache status is not initialized; skipping tick")
        return

    # Priority 1: Ensure next chunk is cached (Tier 1)
    next_chunk_idx = current_chunk + 1
    if 0 <= next_chunk_idx < status.total_chunks:
        await worker._ensure_tier1_chunk(
            track, track_id, next_chunk_idx, preset, intensity
        )
    else:
        logger.debug(
            f"Track {track_id} has no chunk after {current_chunk} "
            f"({status.total_chunks} total); skipping Tier 1 prefetch"
        )

    # Priority 2: Build full track cache in background (Tier 2)
    if not worker.cache_manager.is_track_fully_cached(track_id):
        await worker._build_tier2_cache(track, track_id, current_chunk, preset, intensity)


async def ensure_tier1_chunk(
    worker: Any,
    track: Any,
    track_id: int,
    chunk_idx: int,
    preset: str,
    intensity: float
) -> None:
    """
    Ensure a chunk is cached in Tier 1 (both original and processed).

    This method proactively loads chunks into Tier 1 cache to ensure instant
    playback continuity and fast preset switching.

    Args:
        track: Track object from library
        track_id: Track ID
        chunk_idx: Chunk index to cache
        preset: Current preset
        intensity: Processing intensity
    """
    # Collect chunk paths to warm Tier 1 after processing
    tier1_chunks_to_warm: list[tuple[int, Path, str | None]] = []

    # #5251: this tier is consulted before the signature-aware disk lookup,
    # so a lookup without the current file signature would keep hitting a
    # stale in-memory entry after the source file changes on disk.
    file_signature = FileSignatureService.generate(track.filepath)

    # Check if original chunk is cached
    original_path, tier = await worker.cache_manager.get_chunk(
        track_id, chunk_idx, preset=None, intensity=intensity, file_signature=file_signature
    )

    if original_path is None:
        # Process original chunk
        original_path = await worker._process_chunk(
            track, track_id, chunk_idx, preset=None, intensity=intensity, tier="tier1"
        )

    # Add to warming list if we have the path
    if original_path:
        from pathlib import Path
        tier1_chunks_to_warm.append((chunk_idx, Path(original_path), None))

    # Check if processed chunk is cached (only if auto-mastering enabled)
    if worker.cache_manager.auto_mastering_enabled:
        processed_path, tier = await worker.cache_manager.get_chunk(
            track_id, chunk_idx, preset=preset, intensity=intensity, file_signature=file_signature
        )

        if processed_path is None:
            # Process with current preset
            processed_path = await worker._process_chunk(
                track, track_id, chunk_idx, preset=preset, intensity=intensity, tier="tier1"
            )

        # Add to warming list if we have the path
        if processed_path:
            from pathlib import Path
            tier1_chunks_to_warm.append((chunk_idx, Path(processed_path), preset))

    # Immediately warm Tier 1 with these chunks
    if tier1_chunks_to_warm:
        await worker.cache_manager.warm_tier1_immediately(
            track_id=track_id,
            chunk_paths=tier1_chunks_to_warm,
            intensity=intensity,
            file_signature=file_signature
        )


async def build_tier2_cache(
    worker: Any,
    track: Any,
    track_id: int,
    current_chunk: int,
    preset: str,
    intensity: float
) -> None:
    """
    Build full track cache (Tier 2) in background.

    Strategy:
    - Process chunks sequentially from start to end
    - Skip chunks already in Tier 1 or Tier 2
    - Process one chunk per iteration (avoid blocking)

    Args:
        track: Track object from library
        track_id: Track ID
        current_chunk: Current playback position chunk
        preset: Current preset
        intensity: Processing intensity
    """
    # Get track cache status
    status = worker.cache_manager.get_track_cache_status(track_id)
    if not status:
        return  # Track not initialized yet

    # Reset building state if track changed
    if worker._building_track_id != track_id:
        worker._building_track_id = track_id
        worker._building_chunk_idx = 0
        # Close and drop the previous track's processors (#5062) — see
        # prune_processors_for_track for why this early release sits on top of
        # the LRU cap rather than replacing it.
        worker._processor_cache, worker._processor_build_locks = prune_processors_for_track(
            worker._processor_cache,
            worker._processor_build_locks,
            worker._build_waiters,
            track_id,
        )
        logger.info(f"Building Tier 2 cache for track {track_id} ({status.total_chunks} chunks)")

    # Find next uncached chunk
    for chunk_idx in range(worker._building_chunk_idx, status.total_chunks):
        # Check if original chunk is cached
        if chunk_idx not in status.cached_chunks_original:
            await worker._process_chunk(
                track, track_id, chunk_idx, preset=None, intensity=intensity, tier="tier2"
            )
            worker._building_chunk_idx = chunk_idx + 1
            return  # Process one chunk per iteration

        # Check if processed chunk is cached (only if auto-mastering enabled)
        if worker.cache_manager.auto_mastering_enabled:
            if chunk_idx not in status.cached_chunks_processed:
                await worker._process_chunk(
                    track, track_id, chunk_idx, preset=preset, intensity=intensity, tier="tier2"
                )
                worker._building_chunk_idx = chunk_idx + 1
                return  # Process one chunk per iteration

    # All chunks processed
    if not worker.cache_manager.is_track_fully_cached(track_id):
        logger.info(f"Tier 2 cache complete for track {track_id}")


async def trigger_immediate_processing(
    worker: Any,
    track_id: int,
    chunk_idx: int,
    preset: str | None,
    intensity: float
) -> bool:
    """
    Trigger immediate processing of a specific chunk (for cache misses).

    Used when user seeks or switches tracks and chunk is not cached.

    Args:
        track_id: Track ID
        chunk_idx: Chunk index
        preset: Preset (None for original)
        intensity: Processing intensity

    Returns:
        True if processing succeeded
    """
    status = worker.cache_manager.get_track_cache_status(track_id)
    if status is None:
        logger.warning(
            f"Cannot process chunk {chunk_idx} for track {track_id}: "
            "cache status is not initialized"
        )
        return False
    if chunk_idx < 0 or chunk_idx >= status.total_chunks:
        logger.warning(
            f"Cannot process chunk {chunk_idx} for track {track_id}: "
            f"valid range is 0..{status.total_chunks - 1}"
        )
        return False

    track = await asyncio.to_thread(worker.library_manager.tracks.get_by_id, track_id)
    if not track:
        return False

    try:
        preset_str = "original" if preset is None else preset
        logger.info(f"⚡ IMMEDIATE: Processing chunk {chunk_idx} ({preset_str})")

        chunk_path = await worker._process_chunk(
            track, track_id, chunk_idx, preset, intensity, tier="tier1"
        )

        # _process_chunk swallows its own failures (timeout, missing/
        # unreadable file, any other exception) and returns None rather
        # than raising, so "no exception here" doesn't mean "chunk built"
        # — only a non-None path does (#5063).
        return chunk_path is not None

    except Exception as e:
        logger.error(f"Immediate processing failed: {e}")
        return False
