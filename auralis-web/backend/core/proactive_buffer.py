"""
Proactive Buffering for Instant Preset Switching

Buffers first 3 chunks (45 seconds) for all presets when track loads.
This enables instant preset switching with zero wait time.
"""

import asyncio
import logging
import threading
from pathlib import Path
from typing import cast

import numpy as np

logger = logging.getLogger(__name__)

# Available presets for buffering. Mirrors schemas.VALID_PRESETS -- not
# imported directly to avoid this streaming-core module depending on the
# REST schemas module. Narrowed to a single preset (#4861 follow-up); with
# only one preset, "instant switching" degenerates to warming that one
# preset's cache a little earlier, which is still worth doing.
AVAILABLE_PRESETS = ["adaptive"]
PRELOAD_CHUNKS = 3  # Buffer first 45 seconds (3 x 15s chunks)


async def buffer_presets_for_track(
    track_id: int,
    filepath: str,
    intensity: float = 1.0,
    total_chunks: int | None = None,
    cancel_event: threading.Event | None = None,
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
        # Import here to avoid circular dependency
        from core.chunked_processor import ChunkedAudioProcessor
        from core.processor_factory import PROACTIVE_BUFFER_CONSUMER, get_processor_factory

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
            if _cancelled():
                logger.debug(
                    f"Proactive buffering abandoned before {preset}: stream cancelled"
                )
                return
            processor = None
            try:
                # Create processor for this preset on a worker thread — the
                # constructor does a sync SoundFile open + fingerprint load +
                # HybridProcessor init (~200-500 ms each). Constructing it
                # directly here would stall the event loop for up to ~2.5 s
                # across the 5 presets before the first await (#3853). Mirrors
                # the streaming path at audio_stream_controller.py:597.
                processor = await asyncio.to_thread(
                    ChunkedAudioProcessor,
                    track_id=track_id,
                    filepath=filepath,
                    preset=preset,
                    intensity=intensity,
                    cancel_event=cancel_event,
                    # Its own processors, not the live stream's: this runs
                    # alongside that stream on the same track (#5311).
                    processor_factory=get_processor_factory(PROACTIVE_BUFFER_CONSUMER),
                )

                # Buffer first N chunks
                for chunk_idx in range(chunks_to_buffer):
                    # #5378: bail out between chunks once the owning stream is
                    # gone. `return`, not `break` — every preset shares the one
                    # event, so there is nothing left to buffer for any of them.
                    if _cancelled():
                        logger.debug(
                            f"Proactive buffering stopped at {preset} chunk "
                            f"{chunk_idx}: stream cancelled"
                        )
                        return
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
                        # A chunk abandoned mid-DSP because the stream was
                        # cancelled is not a failure — #4815 raises
                        # ChunkCancelledError out of process_chunk_safe for
                        # exactly this, and logging it at ERROR would turn a
                        # routine seek into a scary log line (#5378).
                        if _cancelled():
                            logger.debug(
                                f"Proactive buffering of {preset} chunk {chunk_idx} "
                                f"abandoned: stream cancelled"
                            )
                            return
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
                        # Best-effort release (#4368 — was a bare pass, hiding
                        # genuine resource-release failures from debugging).
                        logger.debug(f"Processor close failed for {preset}", exc_info=True)

        logger.info(
            f"🎉 Proactive buffering complete: track={track_id}, "
            f"{chunks_to_buffer} chunks × {len(AVAILABLE_PRESETS)} presets buffered"
        )

    except Exception as e:
        logger.error(f"Proactive buffering failed for track {track_id}: {e}", exc_info=True)
