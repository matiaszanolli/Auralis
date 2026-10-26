"""
Proactive Buffering

Buffers the first 3 chunks (45 seconds) of the one remaining preset when a
track loads, so the first playback and any toggle back to enhanced start from a
warm cache.
"""

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import numpy as np

from core.chunk_stream_state import fast_start_for

logger = logging.getLogger(__name__)

# The preset to buffer. Mirrors schemas.DEFAULT_PRESET -- not imported directly
# to avoid this streaming-core module depending on the REST schemas module.
# Narrowed to a single preset (#4861 follow-up), so there is no per-preset loop.
BUFFER_PRESET = "adaptive"
PRELOAD_CHUNKS = 3  # Buffer first 45 seconds (3 x 15s chunks)


async def _buffer_chunk(
    processor: Any, preset: str, chunk_idx: int, chunks_to_buffer: int, cancelled: Callable[[], bool]
) -> bool:
    """Render one chunk, or serve it from the cache; False means the stream was cancelled."""
    try:
        logger.info(f"🔄 Buffering: {preset} chunk {chunk_idx}/{chunks_to_buffer-1}")
        # Always through process_chunk_safe, never an .exists() shortcut: it serves a
        # cache hit from disk AND records that chunk's level (#4669), so chunk N+1 is
        # smoothed against its real neighbour instead of a cold baseline. The live
        # stream may have written this chunk first; fast_start follows the same rule as
        # the live stream, so the durable bytes do not depend on who won (#6090).
        chunk_path, audio_array = cast(
            tuple[Path, np.ndarray],
            await processor.process_chunk_safe(chunk_idx, fast_start=fast_start_for(chunk_idx)),
        )
        logger.info(f"✅ Buffered: {preset} chunk {chunk_idx}")

        # Small delay to avoid CPU saturation
        await asyncio.sleep(0.1)

    except Exception as chunk_error:
        # A chunk abandoned mid-DSP because the stream was cancelled is not a
        # failure -- #4815 raises ChunkCancelledError out of process_chunk_safe
        # for exactly this, and logging it at ERROR would turn a routine seek
        # into a scary log line (#5378).
        if cancelled():
            logger.debug(
                f"Proactive buffering of {preset} chunk {chunk_idx} abandoned: stream cancelled"
            )
            return False
        logger.error(f"Failed to buffer {preset} chunk {chunk_idx}: {chunk_error}")
    return True


async def _buffer_one_preset(
    preset: str,
    track_id: int,
    filepath: str,
    intensity: float,
    chunks_to_buffer: int,
    cancel_event: threading.Event | None,
    cancelled: Callable[[], bool],
) -> bool:
    """Buffer the first chunks of one preset; False means the stream was cancelled."""
    # Import here to avoid circular dependency
    from core.chunked_processor import ChunkedAudioProcessor
    from core.processor_registry import PROACTIVE_BUFFER_CONSUMER, get_processor_factory

    if cancelled():
        logger.debug(f"Proactive buffering abandoned before {preset}: stream cancelled")
        return False
    processor = None
    try:
        # Create the processor on a worker thread -- the constructor does a sync
        # SoundFile open + fingerprint load + HybridProcessor init (~200-500 ms).
        # Constructing it directly here would stall the event loop (#3853).
        # Mirrors the streaming path at audio_stream_controller.py:597.
        processor = await asyncio.to_thread(
            ChunkedAudioProcessor,
            track_id=track_id,
            filepath=filepath,
            preset=preset,
            intensity=intensity,
            cancel_event=cancel_event,
            # Its own processors, not the live stream's: this runs alongside
            # that stream on the same track (#5311).
            processor_factory=get_processor_factory(PROACTIVE_BUFFER_CONSUMER),
        )

        # Buffer first N chunks
        for chunk_idx in range(chunks_to_buffer):
            # #5378: bail out between chunks once the owning stream is gone.
            if cancelled():
                logger.debug(
                    f"Proactive buffering stopped at {preset} chunk {chunk_idx}: stream cancelled"
                )
                return False
            if not await _buffer_chunk(processor, preset, chunk_idx, chunks_to_buffer, cancelled):
                return False
        return True

    except Exception as preset_error:
        logger.error(f"Failed to initialize processor for {preset}: {preset_error}")
        return True
    finally:
        # Release processor resources (#2567)
        if processor is not None and hasattr(processor, "close"):
            try:
                processor.close()
            except Exception:
                # Best-effort release (#4368 -- was a bare pass, hiding genuine
                # resource-release failures from debugging).
                logger.debug(f"Processor close failed for {preset}", exc_info=True)


async def buffer_presets_for_track(
    track_id: int,
    filepath: str,
    intensity: float = 1.0,
    total_chunks: int | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    """
    Proactively buffer the first 3 chunks of the buffered preset in the background.

    This runs as a background task after streaming starts.

    Args:
        track_id: Track ID
        filepath: Path to audio file
        intensity: Processing intensity (0.0-1.0)
        total_chunks: Total number of chunks (if known, to avoid over-buffering)
        cancel_event: the owning stream's cooperative-cancel signal (#5378).
            Set by stop/seek/disconnect teardown before the stream task is
            cancelled; checked between chunks here and, via the processor,
            inside the DSP itself (#4815), so buffering stops with the stream
            instead of running on against its successor. ``None`` (the
            default) keeps every check a no-op for callers without a stream.
    """
    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    try:
        # Determine how many chunks to buffer (don't exceed total chunks)
        chunks_to_buffer = PRELOAD_CHUNKS
        if total_chunks is not None:
            chunks_to_buffer = min(PRELOAD_CHUNKS, total_chunks)

        logger.info(
            f"🚀 Starting proactive buffering: track={track_id}, "
            f"chunks={chunks_to_buffer}, preset={BUFFER_PRESET}"
        )

        completed = await _buffer_one_preset(
            BUFFER_PRESET, track_id, filepath, intensity, chunks_to_buffer, cancel_event, _cancelled
        )
        if not completed:
            return

        logger.info(
            f"🎉 Proactive buffering complete: track={track_id}, "
            f"{chunks_to_buffer} chunks × 1 preset buffered"
        )

    except Exception as e:
        logger.error(f"Proactive buffering failed for track {track_id}: {e}", exc_info=True)
