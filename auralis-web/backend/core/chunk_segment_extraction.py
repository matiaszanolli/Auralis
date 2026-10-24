#!/usr/bin/env python3

"""
Chunk Segment Extraction
~~~~~~~~~~~~~~~~~~~~~~~~

``extract_chunk_segment`` split out of ``ChunkOperations`` (#6270): trimming
a processed chunk (context included) to its non-overlapping CHUNK_INTERVAL
segment — the tiling half of the #4642 no-crossfade contract.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""



import logging

import numpy as np

from core.chunk_boundary_manager import ChunkBoundaryManager
from core.chunk_boundaries import (
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    CONTEXT_DURATION,
    OVERLAP_DURATION,
)

logger = logging.getLogger(__name__)



def extract_chunk_segment(
    processed_chunk: np.ndarray,
    chunk_index: int,
    sample_rate: int,
    chunk_duration: float = CHUNK_DURATION,
    chunk_interval: float = CHUNK_INTERVAL,
    overlap_duration: float = OVERLAP_DURATION,
    total_chunks: int | None = None,
    total_duration: float | None = None
) -> np.ndarray:
    """
    Extract the correct segment from a context-trimmed chunk based on its position.

    After ``ChunkBoundaryManager.trim_context()``, the buffer for chunk N
    (N > 0) spans source time ``[N*interval, N*interval + chunk_duration]``.
    The preceding chunk already emitted up to ``(N-1)*interval + chunk_duration``
    = ``N*interval + overlap_duration``, so the new content starts
    ``overlap_duration`` into the trimmed buffer:

    - Chunk 0: ``[:chunk_duration]`` — first chunk has no predecessor overlap
    - Middle:  ``[overlap:overlap+interval]`` — skip already-emitted overlap
    - Last:    ``[overlap:overlap+remaining]`` — remaining new content only

    Args:
        processed_chunk: Processed chunk (context already trimmed)
        chunk_index: Index of this chunk
        sample_rate: Sample rate
        chunk_duration: Duration of each chunk in seconds
        chunk_interval: Interval between chunk starts
        overlap_duration: Overlap between consecutive chunks (= chunk_duration - chunk_interval)
        total_chunks: Total number of chunks (for last chunk detection)
        total_duration: Total duration (for last chunk calculation)

    Returns:
        Extracted segment ready for encoding
    """
    if chunk_index < 0:
        raise ValueError(f"chunk_index {chunk_index} out of range")
    if total_chunks is not None and chunk_index >= total_chunks:
        raise ValueError(
            f"chunk_index {chunk_index} out of range "
            f"(valid: 0..{total_chunks - 1})"
        )

    is_last = (total_chunks is not None) and (chunk_index == total_chunks - 1)
    overlap_samples = int(round(overlap_duration * sample_rate))

    if chunk_index == 0:
        # First chunk: extract CHUNK_DURATION (or total_duration if shorter, e.g. single-chunk file)
        max_duration = chunk_duration
        if is_last and total_duration is not None:
            max_duration = min(chunk_duration, total_duration)
        expected_samples = int(round(max_duration * sample_rate))
        extracted = processed_chunk[:expected_samples]
        logger.debug(
            f"✅ Chunk 0: extracted [0:{expected_samples}] samples "
            f"({expected_samples/sample_rate:.2f}s)"
        )

    elif is_last:
        # Last chunk: skip overlap already emitted by the previous chunk,
        # then extract only the truly new remaining content. This offset
        # assumes trim_context() performed the full CONTEXT_DURATION trim —
        # true unconditionally as of #3807 (the old max_trim_fraction cap
        # used to under-trim short tracks' final chunk here, desyncing this
        # offset and dropping the track's final seconds).
        assert total_duration is not None
        chunk_start_time = chunk_index * chunk_interval
        remaining_duration = max(0, total_duration - (chunk_start_time + overlap_duration))
        expected_samples = int(round(remaining_duration * sample_rate))

        extracted = processed_chunk[overlap_samples:overlap_samples + expected_samples]
        logger.debug(
            f"✅ Chunk {chunk_index} (last): starts {chunk_start_time + overlap_duration:.1f}s, "
            f"remaining {remaining_duration:.1f}s, {expected_samples} samples"
        )

    else:
        # Regular chunk: skip overlap already emitted by the previous chunk,
        # then extract exactly CHUNK_INTERVAL of new content.
        expected_samples = int(round(chunk_interval * sample_rate))
        extracted = processed_chunk[overlap_samples:overlap_samples + expected_samples]
        logger.debug(
            f"✅ Chunk {chunk_index}: extracted {expected_samples} samples "
            f"({expected_samples/sample_rate:.2f}s) after {overlap_duration:.1f}s overlap skip"
        )

    # Verify and pad/trim if needed (edge case handling)
    current_samples = len(extracted)

    # Normalize mono to 2-D (N,1) up front so every validation branch below
    # (pad / trim / pass-through) returns the same rank (#4132) — previously
    # only the pad path promoted mono to 2-D, the others stayed 1-D.
    if extracted.ndim not in (1, 2):
        raise ValueError(
            f"Chunk {chunk_index}: expected 1-D or 2-D audio array, got shape {extracted.shape}"
        )
    if extracted.ndim == 1:
        extracted = extracted[:, np.newaxis]

    if chunk_index == 0:
        max_dur = chunk_duration
        if is_last and total_duration is not None:
            max_dur = min(chunk_duration, total_duration)
        expected_for_validation = int(round(max_dur * sample_rate))
    elif is_last:
        assert total_duration is not None
        chunk_start_time = chunk_index * chunk_interval
        remaining_duration = max(0, total_duration - (chunk_start_time + overlap_duration))
        expected_for_validation = int(round(remaining_duration * sample_rate))
    else:
        expected_for_validation = int(round(chunk_interval * sample_rate))

    if current_samples < expected_for_validation:
        # Pad with silence if too short. extracted is guaranteed 2-D here.
        padding_needed = expected_for_validation - current_samples
        num_channels = extracted.shape[1]
        # Match the buffer's dtype instead of hardcoding float32 (#4134,
        # same dtype-hygiene fix as #4125) so padding never forces a cast.
        padding = np.zeros((padding_needed, num_channels), dtype=extracted.dtype)
        extracted = np.vstack([extracted, padding])
        logger.warning(
            f"⚠️ Chunk {chunk_index} was {padding_needed} samples short, padded with silence"
        )

    elif current_samples > expected_for_validation:
        # Trim if too long
        extracted = extracted[:expected_for_validation]
        logger.warning(
            f"⚠️ Chunk {chunk_index} was {current_samples - expected_for_validation} "
            f"samples too long, trimmed"
        )

    return extracted
