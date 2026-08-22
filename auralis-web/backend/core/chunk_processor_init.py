#!/usr/bin/env python3

"""
ChunkedAudioProcessor Construction Helpers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two pieces of ``ChunkedAudioProcessor.__init__`` extracted verbatim (#4245):

- ``build_collaborators()`` constructs the boundary/level/encoding/cache
  collaborators that depend only on already-known metadata (sample rate,
  duration, chunk dir) and the cache identity (track/signature/preset/
  intensity) — no track-specific fingerprint work.
- ``init_fingerprint_and_processor()`` performs the 3-tier fingerprint load
  (via ``MasteringTargetService``) and creates (or skips, for
  ``preset=None``) the shared ``HybridProcessor`` instance for this track.

Neither is a chunk-streaming concern; both are one-time per-track setup.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, NamedTuple

from core.chunk_boundaries import ChunkBoundaryManager
from core.chunk_cache_manager import ChunkCacheManager
from core.chunk_path_cache import ChunkPathCache
from core.encoding import WAVEncoder
from core.level_manager import LevelManager

logger = logging.getLogger("core.chunked_processor")


class Collaborators(NamedTuple):
    """Bundle returned by :func:`build_collaborators`."""

    boundary_manager: ChunkBoundaryManager
    level_manager: LevelManager
    wav_encoder: WAVEncoder
    cache_manager: ChunkCacheManager
    path_cache: ChunkPathCache


def build_collaborators(
    total_duration: float,
    sample_rate: int,
    chunk_dir: Path,
    chunk_cache: dict[str, Any],
    track_id: int,
    file_signature: str,
    preset: str | None,
    intensity: float,
) -> Collaborators:
    """Construct the boundary/level/encoding/cache collaborators for one processor.

    ``LevelManager`` takes no ``max_level_change_db`` argument: its own
    default IS ``MAX_LEVEL_CHANGE_DB``, so passing it back in was a no-op
    (#4284) — tuning one without the other would have left this and
    LevelManager silently disagreeing on level-change tolerance across chunk
    boundaries (the #4124 failure mode).
    """
    boundary_manager = ChunkBoundaryManager(total_duration, sample_rate)
    level_manager = LevelManager()
    wav_encoder = WAVEncoder(chunk_dir=chunk_dir, default_subtype='PCM_16')
    cache_manager = ChunkCacheManager(chunk_cache)
    path_cache = ChunkPathCache(
        track_id=track_id,
        file_signature=file_signature,
        preset=preset,
        intensity=intensity,
        wav_encoder=wav_encoder,
        cache_manager=cache_manager,
    )
    return Collaborators(boundary_manager, level_manager, wav_encoder, cache_manager, path_cache)


def init_fingerprint_and_processor(
    mastering_target_service: Any,
    processor_factory: Any,
    track_id: int,
    filepath: str,
    preset: str | None,
    intensity: float,
) -> tuple[Any | None, Any | None, Any | None]:
    """Load the track's fingerprint/targets and create its shared HybridProcessor.

    3-tier fingerprint loading: Database (fastest) -> .25d file -> extract
    from audio (deferred: ``extract_if_missing=False`` here, only on first
    chunk playback) — delegated to ``MasteringTargetService``.

    If ``preset`` is None the caller wants unprocessed/original audio: no
    fingerprint load and no processor (the third element is ``None``).

    CRITICAL: a single shared processor instance is created (not per-chunk)
    to maintain state — envelope followers, gain reduction tracking — across
    chunks; recreating it per chunk causes audible artifacts at boundaries.

    Returns (fingerprint, mastering_targets, processor).
    """
    fingerprint = None
    mastering_targets = None

    if preset is not None:
        result = mastering_target_service.load_fingerprint(
            track_id=track_id,
            filepath=filepath,
            extract_if_missing=False,  # Don't extract on init, only on first chunk playback
            save_extracted=True,
        )
        if result is not None:
            fingerprint, mastering_targets = result
            logger.info(f"✅ Loaded fingerprint/targets via MasteringTargetService for track {track_id}")

    if preset is not None:
        processor = processor_factory.get_or_create(
            track_id=track_id,
            preset=preset,  # narrowed to str by the guard (#4028)
            intensity=intensity,
            mastering_targets=mastering_targets,
        )
        logger.info(f"🎯 Processor initialized via ProcessorFactory for track {track_id}")
    else:
        processor = None  # No processing for original audio (preset is None)

    return fingerprint, mastering_targets, processor
