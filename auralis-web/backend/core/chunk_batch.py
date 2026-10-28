#!/usr/bin/env python3

"""
Whole-Track Chunk Batch Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The whole-track operation extracted from ``ChunkedAudioProcessor`` (#4245):
``get_full_processed_audio_path`` (concatenate every chunk into one full-track
WAV), iterating ``processor.process_chunk_safe`` rather than the per-chunk
streaming hot path directly.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from core.chunk_stream_state import fast_start_for
from core.encoding.atomic_io import atomic_save_audio, is_wav_complete
from auralis.io.saver import save as save_audio

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


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

    # Process all chunks sequentially (fixes #2318) and keep what each returns:
    # the cached files hold the raw segments, and the level smoothing that makes
    # the concatenation seamless is applied to the returned audio, in order
    # (#5948). Calling process_chunk_safe() directly avoids the nested-event-loop
    # antipattern that process_chunk_synchronized() created via asyncio.run().
    all_chunks: list[np.ndarray] = []
    for chunk_idx in range(processor.total_chunks):
        _path, chunk_audio = await processor.process_chunk_safe(
            chunk_idx, fast_start=fast_start_for(chunk_idx)
        )
        all_chunks.append(chunk_audio)

    # Concatenate contiguous, non-overlapping chunks without crossfading.
    logger.info("Concatenating all processed chunks")

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
