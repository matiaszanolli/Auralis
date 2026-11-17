"""
Chunk render (cache miss)
~~~~~~~~~~~~~~~~~~~~~~~~~

The DSP-and-persist step of ``chunk_streaming.process_chunk``: what the single-flight
leader does for a chunk no cache tier holds (#5258). Split out of chunk_streaming.py.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .chunk_stream_state import (
    ChunkCancelledError,
    _invalidate_after_post_dsp_failure,
    _raise_if_cancelled,
)

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


def render_chunk(
    processor: "ChunkedAudioProcessor", chunk_index: int
) -> tuple[str, np.ndarray]:
    """Run the DSP for a cache miss and persist the raw segment (the single-flight leader's work)."""
    # #4815: bail out before the expensive DSP call if the owning stream was
    # already cancelled (seek/track-change/disconnect) — cheap to check, and
    # avoids running 200ms-2s of DSP work (and holding the shared
    # HybridProcessor's _process_lock, blocking any NEW stream reusing the
    # same pooled processor) for a chunk nothing will ever consume.
    _raise_if_cancelled(processor, chunk_index)

    logger.info(f"Processing chunk {chunk_index}/{processor.total_chunks} (preset: {processor.preset})")

    # Skip synchronous fingerprint extraction during chunk processing.
    # Loading the full audio file to compute a fingerprint blocks the first
    # chunk for 5-30s (depending on file size/format), causing the frontend
    # to time out and re-send play requests.  The background fingerprint
    # queue handles extraction asynchronously; subsequent plays will use
    # the cached result.  HybridProcessor analyzes per-chunk as fallback.
    if processor.fingerprint is None and chunk_index == 0:
        logger.info(f"ℹ️  No cached fingerprint for track {processor.track_id} — using per-chunk adaptive processing")

    processor._dsp_state_advanced = False
    try:
        # Process chunk using shared core logic
        # Already the emitted, non-overlapping segment: the core extracts it
        # before smoothing so the gain ramp is audible (#5051).
        extracted_chunk = processor._process_chunk_core(chunk_index)
        assert processor.sample_rate is not None

        # #5328: a seek can land while this DSP is in flight - look-ahead
        # renders are mid-DSP for most of the pump loop - and the check above
        # has long passed. Never persist a render its stream abandoned.
        _raise_if_cancelled(processor, chunk_index)

        # Saved for durability/caching; the array avoids an immediate readback.
        # #4666: targets_hash completes the on-disk identity — the write must
        # land at exactly the path ChunkPathCache.lookup_cached() will check.
        chunk_path = processor._wav_encoder.encode_and_save_from_path(
            audio=extracted_chunk,
            sample_rate=processor.sample_rate,
            track_id=processor.track_id,
            file_signature=processor.file_signature,
            preset=processor.preset,
            intensity=processor.intensity,
            chunk_index=chunk_index,
            subtype='PCM_16',
            targets_hash=processor.targets_hash,
        )
        processor._path_cache.store(chunk_index, chunk_path)
    except ChunkCancelledError:
        # Not a failed retry (#5274): nothing re-requests this chunk from the
        # cancelled stream, and the seek that cancelled it already breaks
        # processor continuity, exactly as when the look-ahead finished first.
        processor._dsp_state_advanced = False
        raise
    except Exception:
        _invalidate_after_post_dsp_failure(processor, chunk_index)
        raise
    processor._dsp_state_advanced = False

    logger.info(f"Chunk {chunk_index} processed and saved to {Path(chunk_path).name}")
    # The durable file holds the raw segment, so it is the same whichever chunk
    # this processor rendered before it. What this stream hears is that segment
    # smoothed against the chunk it just heard (#5948) - a separate array.
    return (str(chunk_path), processor._smooth_level_transition(extracted_chunk, chunk_index))
