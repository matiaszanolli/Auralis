#!/usr/bin/env python3

"""
Whole-Track Chunk Batch Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two whole-track operations extracted from ``ChunkedAudioProcessor`` (#4245):
``process_all_chunks_async`` (background pre-processing of every remaining
chunk) and ``get_full_processed_audio_path`` (concatenate every chunk into
one full-track WAV). Both iterate ``processor.process_chunk_safe`` rather
than the per-chunk streaming hot path directly.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from core.encoding.atomic_io import atomic_save_audio, is_wav_complete
from auralis.io.saver import save as save_audio
from auralis.io.unified_loader import load_audio

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


async def process_all_chunks_async(processor: "ChunkedAudioProcessor") -> None:
    """
    Background task to process all remaining chunks.

    Processes chunks sequentially to avoid overwhelming the system.
    Uses thread-safe locking to prevent concurrent processor state corruption.
    """
    assert processor.total_chunks is not None
    logger.info(f"Starting background processing of {processor.total_chunks - 1} remaining chunks")

    for chunk_idx in range(1, processor.total_chunks):
        try:
            # Check if already cached — in-memory tier only (not the on-disk
            # fallback _lookup_cached_chunk also checks), matching the
            # pre-#4245 behaviour of this loop exactly.
            cache_key = processor._path_cache.cache_key(chunk_idx)
            if processor._cache_manager.get_cached_chunk_path(cache_key) is not None:
                continue

            # Process chunk with thread-safe locking
            await processor.process_chunk_safe(chunk_idx)

            # Small delay to avoid CPU saturation
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Failed to process chunk {chunk_idx}: {e}")

    logger.info("Background chunk processing complete")


async def get_full_processed_audio_path(processor: "ChunkedAudioProcessor") -> str:
    """
    Concatenate all processed chunks into a single file.

    Returns:
        Path to full concatenated audio file
    """
    assert processor.sample_rate is not None and processor.total_chunks is not None
    full_path = (
        processor.chunk_dir
        / f"track_{processor.track_id}_{processor.file_signature}_{processor.preset}_{processor.intensity}_full.wav"
    )

    # Check if a complete file already exists (#4576 — a bare exists()
    # check would serve a truncated concatenation forever).
    if full_path.exists():
        if is_wav_complete(full_path):
            return str(full_path)
        logger.warning(
            f"Discarding truncated full-audio WAV {full_path.name}; regenerating"
        )

    # Ensure all chunks are processed sequentially (fixes #2318).
    # Calling process_chunk_safe() directly avoids the nested-event-loop
    # antipattern that process_chunk_synchronized() created via asyncio.run().
    for chunk_idx in range(processor.total_chunks):
        await processor.process_chunk_safe(chunk_idx, fast_start=(chunk_idx == 0))

    # Concatenate chunks with proper crossfading
    logger.info("Concatenating all processed chunks")
    all_chunks: list[np.ndarray] = []

    for chunk_idx in range(processor.total_chunks):
        chunk_path = processor._get_chunk_path(chunk_idx)
        chunk_audio, _ = load_audio(str(chunk_path))
        all_chunks.append(chunk_audio)

    # Chunks are stored as contiguous, non-overlapping segments — simple
    # concatenation preserves correct duration (#2750).  The previous
    # crossfade incorrectly blended unrelated audio at boundaries and
    # shortened output by (N-1) × 5s.
    full_audio = np.concatenate(all_chunks, axis=0)

    # Save full file atomically (#4576)
    assert processor.sample_rate is not None
    _sr = processor.sample_rate
    atomic_save_audio(
        full_path,
        lambda staged: save_audio(staged, full_audio, _sr, subtype='PCM_16'),
    )
    logger.info(f"Full audio saved to {Path(full_path).name}")

    return str(full_path)
