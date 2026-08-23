#!/usr/bin/env python3

"""
Chunk Streaming Entry Points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The three per-chunk retrieval entry points extracted from
``ChunkedAudioProcessor`` (#4245): ``process_chunk`` (sync, cache-aware),
``process_chunk_safe`` (async, thread-pool-offloaded), and
``get_wav_chunk_path`` (sync, writes straight to the on-disk WAV cache — the
primary path for the unified streaming architecture).

Each function takes the owning ``ChunkedAudioProcessor`` as its first
argument and reads/updates its state directly (see ``chunk_render.py`` for
the shared rationale on why sibling-method calls go through
``processor.<method>`` rather than a direct module-to-module call).

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION
from core.chunk_content_profile import store_content_profile
from core.chunk_operations import ChunkOperations
from core.encoding import WAVEncoderError

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


class ChunkCancelledError(Exception):
    """Raised when a chunk's owning stream was cancelled before/during DSP
    (#4815). Distinguishes a deliberately-abandoned chunk from a genuine
    processing failure — callers must not log/retry it as one. In practice
    the coroutine that would have awaited this chunk has almost always
    already unwound via CancelledError by the time this is raised (asyncio
    cancellation doesn't wait for the underlying executor thread), so this
    exists mainly to cut the wasted DSP work short rather than to be
    observed by a live caller."""


def process_chunk(
    processor: "ChunkedAudioProcessor", chunk_index: int, fast_start: bool = False, locked: bool = False
) -> tuple[str, np.ndarray]:
    """
    Process a single chunk with Auralis HybridProcessor and save to WAV.

    Returns both the path (for caching) and the numpy array (for streaming).
    This avoids the disk round-trip of saving then immediately reading back.

    Args:
        locked: If True, hold _processor_lock (threading.Lock) for the whole
            chunk so concurrent calls serialise. Used by process_chunk_safe,
            which runs this in a thread pool (#2388). Default False keeps the
            direct sync call (and tests) lock-free (#4245: collapses the old
            process_chunk / _process_chunk_locked pair).

    Returns:
        Tuple of (path_to_chunk_file, processed_audio_array)
    """
    if locked:
        with processor._processor_lock:
            return processor.process_chunk(chunk_index, fast_start, locked=False)

    # Keep the range check below every public processing entry point. This
    # must happen before cache lookup so a stale out-of-range cache file can
    # never bypass the authoritative processor bound (#4733).
    processor._validate_chunk_index(chunk_index)

    # Check cache first — in-memory, then on-disk WAV (#4792: this used to
    # check only the in-memory dict, so a fresh in-memory cache (every new
    # stream) always re-ran the full DSP pipeline even when a byte-identical
    # WAV from a previous stream of this track/preset/intensity was already
    # on disk).
    cached_path = processor._lookup_cached_chunk(chunk_index)

    if cached_path is not None:
        assert processor.total_chunks is not None
        logger.info(f"Serving cached chunk {chunk_index}/{processor.total_chunks}")
        # Load from disk only if cached (for subsequent requests)
        # For initial streaming, audio array is already in memory cache
        from auralis.io.unified_loader import load_audio
        audio, _ = load_audio(str(cached_path))
        return (str(cached_path), audio)

    # #4815: bail out before the expensive DSP call if the owning stream was
    # already cancelled (seek/track-change/disconnect) — cheap to check, and
    # avoids running 200ms-2s of DSP work (and holding the shared
    # HybridProcessor's _process_lock, blocking any NEW stream reusing the
    # same pooled processor) for a chunk nothing will ever consume.
    cancel_event = getattr(processor, "_cancel_event", None)
    if cancel_event is not None and cancel_event.is_set():
        raise ChunkCancelledError(
            f"Chunk {chunk_index} abandoned: owning stream was cancelled"
        )

    logger.info(f"Processing chunk {chunk_index}/{processor.total_chunks} (preset: {processor.preset}, fast_start: {fast_start})")

    # Skip synchronous fingerprint extraction during chunk processing.
    # Loading the full audio file to compute a fingerprint blocks the first
    # chunk for 5-30s (depending on file size/format), causing the frontend
    # to time out and re-send play requests.  The background fingerprint
    # queue handles extraction asynchronously; subsequent plays will use
    # the cached result.  HybridProcessor analyzes per-chunk as fallback.
    if processor.fingerprint is None and chunk_index == 0:
        logger.info(f"ℹ️  No cached fingerprint for track {processor.track_id} — using per-chunk adaptive processing")

    # Process chunk using shared core logic
    processed_chunk = processor._process_chunk_core(chunk_index, fast_start)

    # CRITICAL: Extract the correct segment for this chunk to handle overlaps (Phase 5.1: Using ChunkOperations)
    # - Chunk 0: full CHUNK_DURATION (15s)
    # - Regular chunks: skip overlap (5s), extract CHUNK_INTERVAL (10s)
    # Without this, chunks would overlap and cause audio jumps during playback
    assert processor.sample_rate is not None and processor.total_chunks is not None and processor.total_duration is not None
    extracted_chunk = ChunkOperations.extract_chunk_segment(
        processed_chunk=processed_chunk,
        chunk_index=chunk_index,
        sample_rate=processor.sample_rate,
        chunk_duration=CHUNK_DURATION,
        chunk_interval=CHUNK_INTERVAL,
        overlap_duration=OVERLAP_DURATION,
        total_chunks=processor.total_chunks,
        total_duration=processor.total_duration
    )

    # Save chunk using WAVEncoder (Phase 3.5 refactoring)
    # NOTE: Saved for durability/caching, but we return the array directly to avoid disk I/O
    chunk_path = processor._wav_encoder.encode_and_save_from_path(
        audio=extracted_chunk,
        sample_rate=processor.sample_rate,
        track_id=processor.track_id,
        file_signature=processor.file_signature,
        preset=processor.preset,
        intensity=processor.intensity,
        chunk_index=chunk_index,
        subtype='PCM_16'
    )

    # Cache the path
    processor._path_cache.store(chunk_index, chunk_path)

    logger.info(f"Chunk {chunk_index} processed and saved to {Path(chunk_path).name}")
    # Return both path (for caching) and audio array (for immediate streaming)
    return (str(chunk_path), extracted_chunk)


async def process_chunk_safe(
    processor: "ChunkedAudioProcessor", chunk_index: int, fast_start: bool = False
) -> tuple[str, np.ndarray]:
    """
    Process a single chunk with thread-safe locking (async version).

    Offloads the CPU-intensive DSP work (HPSS, EQ, loudness normalization) to a
    thread-pool worker via asyncio.to_thread(), keeping the event loop free to handle
    WebSocket heartbeats, pause/seek commands, and other coroutines during the
    5-30 second processing window (issue #2388).

    Serialisation is provided by _processor_lock (threading.Lock): concurrent
    calls block in the thread pool rather than on the event loop.

    Returns:
        Tuple of (path_to_chunk_file, processed_audio_array)
        - path: for caching/durability
        - audio: numpy array for immediate streaming (avoids disk round-trip)
    """
    # Dedicated streaming pool, not the shared default executor (#5086):
    # this is the per-chunk hot path, and queueing behind an unrelated
    # repository call or the library scan makes CHUNK_PROCESS_TIMEOUT
    # (#3852) fire on queueing delay rather than a genuine DSP hang.
    from .executors import run_in_stream_executor

    return await run_in_stream_executor(processor.process_chunk, chunk_index, fast_start, True)


def get_wav_chunk_path(processor: "ChunkedAudioProcessor", chunk_index: int) -> str:
    """
    Get WAV chunk for unified streaming architecture.

    This is the PRIMARY output method for the unified architecture.
    Process audio and encode directly to WAV in a single pass.
    WAV format is required for Web Audio API compatibility.

    Returns:
        Path to WAV chunk file
    """
    assert processor.sample_rate is not None and processor.total_chunks is not None and processor.total_duration is not None
    # Validate before cache/disk lookup. The shared validator is also used
    # by process_chunk and _process_chunk_core so worker-driven processing
    # cannot bypass the ceiling (#4342, #4733).
    processor._validate_chunk_index(chunk_index)
    # _sync_cache_lock serialises the full check→process→cache cycle so that
    # two concurrent thread-pool calls for the same chunk cannot both miss the
    # cache, both process the chunk, and produce conflicting results.
    with processor._sync_cache_lock:
        # Check cache — in-memory, then on-disk WAV (#4792: shared with
        # process_chunk() via _lookup_cached_chunk, since both write the
        # exact same on-disk file under what used to be two different
        # cache keys — a hit recorded by one was invisible to the other).
        cached_path = processor._lookup_cached_chunk(chunk_index)
        if cached_path is not None:
            logger.info(f"Serving cached WAV chunk {chunk_index}")
            return str(cached_path)

        # Get WAV output path
        wav_chunk_path = processor._get_wav_chunk_path(chunk_index)

        logger.info(f"Processing chunk {chunk_index} directly to WAV")

        # Use shared core processing logic (eliminates duplicate code)
        processed_chunk = processor._process_chunk_core(chunk_index, fast_start=False)

        # Extract the correct segment for this chunk (Phase 5.1: Using ChunkOperations)
        extracted_chunk = ChunkOperations.extract_chunk_segment(
            processed_chunk=processed_chunk,
            chunk_index=chunk_index,
            sample_rate=processor.sample_rate,
            chunk_duration=CHUNK_DURATION,
            chunk_interval=CHUNK_INTERVAL,
            overlap_duration=OVERLAP_DURATION,
            total_chunks=processor.total_chunks,
            total_duration=processor.total_duration
        )

        # Encode directly to WAV (Web Audio API compatible). Routed through
        # the same WAVEncoder.encode_and_save() primitive process_chunk()
        # uses (#4895) — this applies the isfinite/empty-array guard the
        # standalone encode_to_wav() lacked, and its own stage+os.replace
        # atomic write (#4576) replaces the manual encode_to_wav() +
        # atomic_write_bytes() pair, leaving exactly one atomic-write
        # implementation (atomic_save_audio) for this pipeline.
        try:
            processor._wav_encoder.encode_and_save(
                audio=extracted_chunk,
                sample_rate=processor.sample_rate,
                chunk_path=wav_chunk_path,
                subtype='PCM_16'
            )
            logger.info(f"Chunk {chunk_index} encoded to WAV: {wav_chunk_path.name}")

        except WAVEncoderError as e:
            logger.error(f"WAV encoding failed for chunk {chunk_index}: {e}")
            raise RuntimeError(f"Failed to encode chunk to WAV: {e}")

        # Cache the path under the same collapsed key process_chunk() uses
        # (#4792), so this write is visible to both callers.
        processor._path_cache.store(chunk_index, wav_chunk_path)

    # Store last_content_profile globally for visualizer API access
    # This allows the /api/processing/parameters endpoint to show real processing data.
    # Runs across concurrent asyncio.to_thread workers (#4341) — guarded by
    # chunk_content_profile's dedicated lock so a write here can't interleave
    # with a read in get_last_content_profile() from the event-loop thread.
    if processor.processor is not None:
        processor_profile = getattr(processor.processor, 'last_content_profile', None)
        if processor_profile and processor.preset is not None:
            store_content_profile(processor.preset, processor_profile)
            logger.debug(f"📊 Stored processing profile for preset '{processor.preset}'")

    return str(wav_chunk_path)
