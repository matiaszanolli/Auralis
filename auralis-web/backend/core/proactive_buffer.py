"""
Proactive Buffering for Instant Preset Switching

Buffers first 3 chunks (45 seconds) for all presets when track loads.
This enables instant preset switching with zero wait time.
"""

import asyncio
import logging
from pathlib import Path
from typing import cast

import numpy as np

logger = logging.getLogger(__name__)

# Available presets for buffering
AVAILABLE_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]
PRELOAD_CHUNKS = 3  # Buffer first 45 seconds (3 x 15s chunks)


async def buffer_presets_for_track(
    track_id: int,
    filepath: str,
    intensity: float = 1.0,
    total_chunks: int | None = None
) -> None:
    """
    Proactively buffer first 3 chunks for all presets in background.

    This runs as a background task after streaming starts, enabling instant
    preset switching within the first 90 seconds of playback.

    Args:
        track_id: Track ID
        filepath: Path to audio file
        intensity: Processing intensity (0.0-1.0)
        total_chunks: Total number of chunks (if known, to avoid over-buffering)
    """
    try:
        # Import here to avoid circular dependency
        from core.chunked_processor import ChunkedAudioProcessor

        # Determine how many chunks to buffer (don't exceed total chunks)
        chunks_to_buffer = PRELOAD_CHUNKS
        if total_chunks is not None:
            chunks_to_buffer = min(PRELOAD_CHUNKS, total_chunks)

        logger.info(
            f"🚀 Starting proactive buffering: track={track_id}, "
            f"chunks={chunks_to_buffer}, presets={len(AVAILABLE_PRESETS)}"
        )

        # Process each preset
        for preset in AVAILABLE_PRESETS:
            processor = None
            try:
                # Create processor for this preset
                processor = ChunkedAudioProcessor(
                    track_id=track_id,
                    filepath=filepath,
                    preset=preset,
                    intensity=intensity
                )

                # Buffer first N chunks
                for chunk_idx in range(chunks_to_buffer):
                    try:
                        # Check if already cached
                        chunk_path = processor._get_chunk_path(chunk_idx)

                        if chunk_path.exists():
                            logger.debug(f"✓ Already cached: {preset} chunk {chunk_idx}")
                            continue

                        # Process chunk with thread-safe locking
                        logger.info(f"🔄 Buffering: {preset} chunk {chunk_idx}/{chunks_to_buffer-1}")
                        # process_chunk_safe now returns (path, audio_array) tuple
                        chunk_path, audio_array = cast(tuple[Path, np.ndarray], await processor.process_chunk_safe(chunk_idx))
                        logger.info(f"✅ Buffered: {preset} chunk {chunk_idx}")

                        # Small delay to avoid CPU saturation
                        await asyncio.sleep(0.1)

                    except Exception as chunk_error:
                        logger.error(f"Failed to buffer {preset} chunk {chunk_idx}: {chunk_error}")
                        continue

            except Exception as preset_error:
                logger.error(f"Failed to initialize processor for {preset}: {preset_error}")
            finally:
                # Release processor resources (#2567)
                if processor is not None and hasattr(processor, "close"):
                    try:
                        processor.close()
                    except Exception:
                        pass

        logger.info(
            f"🎉 Proactive buffering complete: track={track_id}, "
            f"{chunks_to_buffer} chunks × {len(AVAILABLE_PRESETS)} presets buffered"
        )

    except Exception as e:
        logger.error(f"Proactive buffering failed for track {track_id}: {e}", exc_info=True)


# Removed: get_buffer_status() (#3526 / BE-NEW-68).
# It globbed for `track_{id}_{preset}_{intensity}_chunk_*.wav` but the
# actual on-disk filename (WAVEncoder.get_chunk_path at
# encoding/wav_encoder.py:96-99) is
# `v{CACHE_VERSION}_track_{id}_{file_signature}_{preset}_{intensity}_chunk_{idx}.wav`,
# so the glob matched zero files and the function always returned set().
# A grep across auralis-web/ + tests/ confirmed zero callers — pure dead
# code. If a buffer-status query is needed, expose it through
# ChunkCacheManager.get_statistics() which operates on the canonical
# in-memory cache state.
