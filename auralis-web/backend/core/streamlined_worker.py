"""
Streamlined Cache Worker for Auralis Beta.9
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simple background worker that builds two-tier caches:
- Priority 1: Next chunk (Tier 1) - critical for smooth playback
- Priority 2: Full track cache (Tier 2) - enables instant seeking
- Priority 3: Previous track - enables instant back button

Replaces complex multi-tier worker (373 lines) with simple predictive logic (~150 lines).

This module is the public facade (#5037): it owns the worker lifecycle and the
per-chunk processing entry point, and composes two siblings —
``core/streamlined_processor_cache.py`` (LRU processor cache + build-lock
bookkeeping) and ``core/streamlined_tiers.py`` (tier-priority scheduling).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any
from helpers import spawn_background_task

from core import streamlined_tiers
from core.streamlined_processor_cache import (
    _PROCESSOR_CACHE_MAX,
    ProcessorCacheKey,
    close_dropped_processor,
    get_or_build_processor,
    remember_processor,
)
from core.streamlined_processor_cache import intensity_key as _intensity_key


logger = logging.getLogger(__name__)

class StreamlinedCacheWorker:
    """
    Simple background worker for building two-tier caches.

    Strategy:
    1. Always buffer next chunk (both original + processed)
    2. Build full track cache in background
    3. Keep previous track cached for instant back button
    """

    def __init__(self, cache_manager: Any, library_manager: Any) -> None:
        """
        Initialize streamlined cache worker.

        Args:
            cache_manager: StreamlinedCacheManager instance
            library_manager: LibraryDatabase used to get track information
        """
        self.cache_manager = cache_manager
        self.library_manager = library_manager
        self.running = False
        self._worker_task: asyncio.Task[None] | None = None

        # Track what we're currently building
        self._building_track_id: int | None = None
        self._building_chunk_idx: int = 0

        # Processor cache: reuse the same ChunkedAudioProcessor across chunks
        # for a given (track_id, preset, intensity) so DSP state (compressor
        # envelope, EQ history) is preserved at chunk boundaries (fixes #2737).
        # LRU-ordered and bounded (#4521); per-key build locks (#4369) with a
        # live waiter count so a lock is only dropped when nobody is queued on
        # it. The worker owns this state; the bookkeeping over it lives in
        # core/streamlined_processor_cache.py.
        self._processor_cache: OrderedDict[ProcessorCacheKey, Any] = OrderedDict()
        self._processor_build_locks: dict[ProcessorCacheKey, asyncio.Lock] = {}
        self._build_waiters: dict[ProcessorCacheKey, int] = {}

    def _remember_processor(
        self,
        cache_key: ProcessorCacheKey,
        processor: Any,
    ) -> None:
        """Insert a processor as most-recently-used and evict past the cap (#4521).

        Thin facade over ``streamlined_processor_cache.remember_processor``; the
        cap is read here, at call time, so ``_PROCESSOR_CACHE_MAX`` stays
        overridable on this module.
        """
        remember_processor(
            self._processor_cache,
            self._processor_build_locks,
            cache_key,
            processor,
            max_size=_PROCESSOR_CACHE_MAX,
        )

    def _close_dropped_processor(
        self,
        cache_key: ProcessorCacheKey,
        processor: Any,
    ) -> None:
        """Release a dropped processor's temp WAV, if it made one (#4737).

        Thin facade over ``streamlined_processor_cache.close_dropped_processor``,
        which every removal path from ``_processor_cache`` goes through.
        """
        close_dropped_processor(cache_key, processor)

    async def start(self) -> None:
        """Start the background worker."""
        if not self.running:
            self.running = True
            self._worker_task = spawn_background_task(self._worker_loop(), name="streamlined_worker._worker_loop")
            logger.info("🚀 Streamlined cache worker started")

    async def stop(self) -> None:
        """Stop the background worker."""
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            # Drop the finished task (#4577) — leaving it in place lets a
            # health probe landing between stop() and the next start() read a
            # done task, or a plain truthiness check report a stopped worker
            # as running.
            self._worker_task = None
        logger.info("🛑 Streamlined cache worker stopped")

    @property
    def worker_task(self) -> asyncio.Task[None] | None:
        """The live background task, or None when not running (#4577).

        Public accessor so lifecycle watchers (``config/startup.py``) don't
        reach into the private attribute.
        """
        return self._worker_task

    @property
    def is_running(self) -> bool:
        """True only while the background loop is actually alive (#4577).

        False in all three dead states: never started, stopped, and crashed
        (task done with an exception) — the last being the stale-truthiness
        case #3898 is about.
        """
        return (
            self.running
            and self._worker_task is not None
            and not self._worker_task.done()
        )

    async def _worker_loop(self) -> None:
        """
        Main worker loop - runs continuously.

        Checks every 1 second for needed chunks and processes them.
        """
        try:
            while self.running:
                await asyncio.sleep(1.0)  # Check every second

                try:
                    await self._process_priorities()
                except Exception as e:
                    logger.error(f"Error in cache worker loop: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Cache worker loop cancelled")
            raise

    # Tier-priority scheduling lives in core/streamlined_tiers.py (#5037).
    # Bound here under the original names — each function takes the worker as
    # its first parameter, so these are ordinary methods with unchanged
    # signatures, and `inspect.getsource` still reaches the real body.
    _process_priorities = streamlined_tiers.process_priorities
    _ensure_tier1_chunk = streamlined_tiers.ensure_tier1_chunk
    _build_tier2_cache = streamlined_tiers.build_tier2_cache
    trigger_immediate_processing = streamlined_tiers.trigger_immediate_processing

    async def _process_chunk(
        self,
        track: Any,
        track_id: int,
        chunk_idx: int,
        preset: str | None,
        intensity: float,
        tier: str
    ) -> str | None:
        """
        Process a single chunk and add to cache.

        Args:
            track: Track object from library
            track_id: Track ID
            chunk_idx: Chunk index
            preset: Processing preset (None for original)
            intensity: Processing intensity
            tier: Target tier ("tier1" or "tier2")

        Returns:
            Path to processed chunk file, or None if processing failed
        """
        try:
            preset_str = "original" if preset is None else preset
            logger.debug(f"[{tier}] Processing chunk {chunk_idx} ({preset_str})")

            # Check if file exists
            if not Path(track.filepath).exists():
                logger.error(f"File not found: {track.filepath}")
                return None

            # Reuse processor across chunks so DSP state (compressor envelope,
            # EQ history) carries over at chunk boundaries (fixes #2737). The
            # get-or-build dance (LRU recency, per-key build lock, waiter
            # accounting) lives in core/streamlined_processor_cache.py.
            cache_key = (track_id, preset, _intensity_key(intensity))
            processor = await get_or_build_processor(self, cache_key, track.filepath)

            # Process chunk with timeout (using thread-safe async method)
            timeout_seconds = 20 if tier == "tier1" else 60  # Tier 1 is urgent

            try:
                # process_chunk_safe now returns (path, audio_array) tuple
                chunk_path, audio_array = await asyncio.wait_for(
                    processor.process_chunk_safe(chunk_idx),
                    timeout=timeout_seconds
                )
            except TimeoutError:
                logger.error(
                    f"[{tier}] Timeout processing chunk {chunk_idx} "
                    f"(exceeded {timeout_seconds}s limit)"
                )
                return None
            except FileNotFoundError as e:
                logger.error(f"[{tier}] File not found: {e}")
                return None
            except PermissionError as e:
                logger.error(f"[{tier}] Permission denied: {e}")
                return None

            # Add to cache
            if chunk_path:
                success = await self.cache_manager.add_chunk(
                    track_id=track_id,
                    chunk_idx=chunk_idx,
                    chunk_path=Path(chunk_path),
                    preset=preset,
                    intensity=intensity,
                    tier=tier
                )

                if success:
                    logger.info(
                        f"✅ [{tier}] Cached chunk {chunk_idx} ({preset_str}) "
                        f"for track {track_id}"
                    )
                else:
                    logger.warning(f"[{tier}] Failed to cache chunk {chunk_idx}")

            # Small delay to avoid CPU saturation
            await asyncio.sleep(0.05)

            return chunk_path

        except Exception as e:
            logger.error(f"[{tier}] Failed to process chunk {chunk_idx}: {e}", exc_info=True)
            return None


# Global instance (initialized in main.py)
streamlined_worker: StreamlinedCacheWorker | None = None
