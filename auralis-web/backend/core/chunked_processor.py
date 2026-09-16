#!/usr/bin/env python3

"""
Chunked Audio Processor
~~~~~~~~~~~~~~~~~~~~~~~

Renders 15 s windows (CHUNK_DURATION) with 5 s context each side and emits them
as 10 s non-overlapping segments (CHUNK_INTERVAL), with no boundary crossfade
(#2750/#3514/#4642). `core/chunk_boundaries.py` owns the geometry constants.

A coordinator (#4245): logic lives in sibling ``chunk_*`` modules that take this
instance as their first argument; every method stays a thin delegator so
``patch.object(processor, ...)`` works, and those modules log as
``"core.chunked_processor"``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import math
import sys
import threading
from pathlib import Path
from typing import Any

import numpy as np

# Ensure both project root and backend are in path
backend_path = str(Path(__file__).parent.parent)   # core/ → backend/
project_root = str(Path(__file__).parent.parent.parent.parent)  # → auralis-web/ → project root
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.limits import chunk_cache_dir, create_secure_temp_dir

# Chunk geometry and MAX_LEVEL_CHANGE_DB are re-exported, not redeclared (#4024/#4284).
from core.chunk_boundaries import (  # noqa: F401 — CONTEXT_DURATION/OVERLAP_DURATION re-exported for callers
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    OVERLAP_DURATION,
    CONTEXT_DURATION,
)
from core import chunk_batch, chunk_render, chunk_streaming
# The `noqa: F401` names below are re-exported so pre-#4245 test patch targets
# (`patch("core.chunked_processor.X")`, class-attribute patches) and
# `import core.chunked_processor as cp; cp.X` reads keep resolving.
from core.audio_processing_pipeline import AudioProcessingPipeline  # noqa: F401
from core.chunk_content_profile import (  # noqa: F401
    _last_content_profiles,
    _last_content_profiles_lock,
    get_last_content_profile,
)
from core.chunk_fingerprint_registry import (  # noqa: F401
    _default_get_fingerprints_repository,
    _reset_registry_miss_warning,
)
from core.chunk_metadata import load_audio_metadata
from core.chunk_operations import ChunkOperations  # noqa: F401
from core.chunk_mastering import compute_mastering_recommendation
from core.chunk_processor_init import build_collaborators, init_fingerprint_and_processor
from core.targets_hash import get_targets_hash
from core.seekable_source import SeekableSource
from core.file_signature import FileSignatureService  # Phase 5.1: File signature generation
from core.level_manager import MAX_LEVEL_CHANGE_DB  # noqa: F401
from core.mastering_target_service import get_mastering_target_service  # Singleton (#4749)
from core.processor_factory import get_processor_factory  # Singleton (injected, not constructed here)

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine, MasteringRecommendation

logger = logging.getLogger(__name__)


class ChunkedAudioProcessor:
    """
    Process audio in chunks for fast streaming: fast-starting first chunk,
    background processing of the rest, and smart caching of processed chunks.
    """

    def __init__(
        self,
        track_id: int,
        filepath: str,
        preset: str | None = "adaptive",
        intensity: float = 1.0,
        chunk_cache: dict[str, Any] | None = None,
        cancel_event: threading.Event | None = None,
        processor_factory: Any | None = None,
    ) -> None:
        """preset=None serves original audio; chunk_cache is shared across processors.

        processor_factory: None means the live-stream factory; background builders
        pass their own so they never advance a live stream's state (#5311).
        cancel_event: set when the owning stream is torn down so chunk_streaming
        skips DSP for an abandoned chunk (#4815); None disables the check.
        """
        self.track_id = track_id
        self.filepath = filepath
        self.preset = preset
        self.intensity = intensity
        self.chunk_cache = chunk_cache if chunk_cache is not None else {}
        self._cancel_event = cancel_event

        # Resolves `filepath` to a seekable path lazily, at most once per track
        # (#4737), so get_mastering_recommendation() alone never decodes. Owns a
        # temp dir only after a conversion — see close().
        self._source = SeekableSource(filepath)
        self.file_signature = FileSignatureService.generate(filepath)  # cache integrity

        self.sample_rate: int | None = None
        self.total_duration: float | None = None
        self.total_chunks: int | None = None
        self.channels: int | None = None
        self._load_metadata()

        # Expose canonical chunk interval so consumers don't need getattr fallbacks (#2848)
        self.chunk_interval: float = float(CHUNK_INTERVAL)

        self.chunk_dir = chunk_cache_dir()
        create_secure_temp_dir(self.chunk_dir)

        self._processor_factory: Any = (
            processor_factory if processor_factory is not None else get_processor_factory()
        )
        self._mastering_target_service: Any = get_mastering_target_service()

        # Fingerprint/targets (DB -> .25d file -> extract-on-first-play) and the
        # shared HybridProcessor, whose state persists across chunks.
        # #4666: MUST precede build_collaborators() — the chunk cache identity
        # (memory key and WAV filename) hashes these targets.
        # `or 44100` only narrows `int | None`; metadata is already loaded.
        sample_rate_valid: int = self.sample_rate or 44100
        (
            self.fingerprint,
            self.mastering_targets,
            self.processor,
            # #5306: every later factory lookup for this track (chunk_render,
            # chunk_streaming's #5274 invalidate) MUST pass this same config, or
            # it hashes to a different, 44.1 kHz-assuming cache entry.
            self.processor_config,
        ) = init_fingerprint_and_processor(
            self._mastering_target_service,
            self._processor_factory,
            track_id,
            filepath,
            self.preset,
            intensity,
            sample_rate_valid,
        )
        # Same helper ProcessorFactory keys its cache on (#3720/#4666).
        self.targets_hash: str = get_targets_hash(self.mastering_targets)

        # Collaborators (#4245: see chunk_processor_init.build_collaborators).
        total_duration_valid: float = self.total_duration or 0.0
        (
            self._boundary_manager,
            self._level_manager,
            self._wav_encoder,
            self._cache_manager,
            self._path_cache,
        ) = build_collaborators(
            total_duration=total_duration_valid,
            sample_rate=sample_rate_valid,
            chunk_dir=self.chunk_dir,
            chunk_cache=self.chunk_cache,
            track_id=track_id,
            file_signature=self.file_signature,
            preset=preset,
            intensity=intensity,
            targets_hash=self.targets_hash,
        )

        # RLock, not asyncio.Lock: taken in asyncio.to_thread() workers (#2388)
        # and re-entered by process_chunk(locked=True) (#3808). Serialises
        # processor.process() so shared DSP state is never corrupted.
        self._processor_lock = threading.RLock()
        # Set right after the stateful DSP call; chunk_streaming clears it on
        # durable success or invalidates the pooled processor (#5274).
        self._dsp_state_advanced = False
        # Serialises get_wav_chunk_path()'s check→process→cache cycle per chunk.
        self._sync_cache_lock = threading.Lock()

        # Weighted mastering-profile recommendation cache (real-time UI display).
        self.mastering_recommendation: MasteringRecommendation | None = None
        self.adaptive_mastering_engine: AdaptiveMasteringEngine | None = None

        # Processing state tracking for smooth transitions
        self.chunk_rms_history: list[float] = []
        self.chunk_gain_history: list[float] = []
        self.previous_chunk_tail: np.ndarray | None = None  # Last samples of previous chunk

        logger.info(
            f"ChunkedAudioProcessor initialized: track_id={track_id}, "
            f"duration={self.total_duration:.1f}s, chunks={self.total_chunks}, "
            f"preset={preset}, intensity={intensity}"
        )

    @property
    def duration(self) -> float | None:
        """Get total duration (alias for total_duration for AudioStreamController compatibility)"""
        return self.total_duration

    @property
    def chunk_duration(self) -> float:
        """Get chunk duration in seconds for crossfade calculations"""
        return CHUNK_DURATION

    def _validate_chunk_index(self, chunk_index: int) -> None:
        """Reject indices outside this track's content-carrying chunks."""
        if self.total_chunks is None:
            raise RuntimeError("Processor metadata missing: total_chunks is None")
        if chunk_index < 0 or chunk_index >= self.total_chunks:
            raise ValueError(
                f"chunk_index {chunk_index} out of range "
                f"(valid: 0..{self.total_chunks - 1})"
            )

    def _load_metadata(self) -> None:
        """Load audio file metadata without decoding it. Delegates to chunk_metadata (#4245)."""
        meta = load_audio_metadata(self.filepath)
        if not math.isfinite(meta.total_duration) or meta.total_duration <= 0:
            raise ValueError(
                f"Cannot process unplayable audio with duration "
                f"{meta.total_duration!r}s: {self.filepath}"
            )
        self.sample_rate = meta.sample_rate
        self.channels = meta.channels
        self.total_duration = meta.total_duration
        self.total_chunks = meta.total_chunks

    def _get_chunk_path(self, chunk_index: int) -> Path:
        """Chunk's on-disk WAV path. Delegates to ChunkPathCache (#4245)."""
        return self._path_cache.get_chunk_path(chunk_index)

    def _get_wav_chunk_path(self, chunk_index: int) -> Path:
        """Alias of _get_chunk_path (unified architecture's primary output format)."""
        return self._get_chunk_path(chunk_index)

    def _lookup_cached_chunk(self, chunk_index: int) -> Path | None:
        """In-memory, then on-disk WAV cache lookup. Delegates to ChunkPathCache (#4245, #4792)."""
        return self._path_cache.lookup_cached(chunk_index)

    def load_chunk(self, chunk_index: int, with_context: bool = True) -> tuple[np.ndarray, float, float]:
        """Load a chunk with optional context. Delegates to chunk_render (#4245)."""
        return chunk_render.load_chunk(self, chunk_index, with_context)

    def _calculate_rms(self, audio: np.ndarray) -> float:
        """RMS level in dB. Delegates to chunk_render / LevelManager (#4245)."""
        return chunk_render.calculate_rms(self, audio)

    def _smooth_level_transition(self, chunk: np.ndarray, chunk_index: int) -> np.ndarray:
        """Smooth level transitions across chunks. Delegates to chunk_render (#4245)."""
        return chunk_render.smooth_level_transition(self, chunk, chunk_index)

    def note_cached_chunk_level(
        self, chunk: np.ndarray | None, chunk_index: int, gain_db: float = 0.0, rms_db: float | None = None
    ) -> None:
        """Record a cache-hit chunk's level (#3832); a known ``rms_db`` lets ``chunk`` be None (#4669)."""
        chunk_render.note_cached_chunk_level(self, chunk, chunk_index, gain_db, rms_db)

    def _process_chunk_core(self, chunk_index: int, fast_start: bool = False) -> np.ndarray:
        """Shared core of process_chunk/get_wav_chunk_path. Delegates to chunk_render (#4245)."""
        return chunk_render.process_chunk_core(self, chunk_index, fast_start)

    def process_chunk(
        self, chunk_index: int, fast_start: bool = False, locked: bool = False
    ) -> tuple[str, np.ndarray]:
        """Process a chunk to WAV, returning (path, audio); ``locked`` holds _processor_lock (#2388)."""
        return chunk_streaming.process_chunk(self, chunk_index, fast_start, locked)

    async def process_chunk_safe(self, chunk_index: int, fast_start: bool = False) -> tuple[str, np.ndarray]:
        """Thread-pool-offloaded process_chunk (#2388). Delegates to chunk_streaming (#4245)."""
        return await chunk_streaming.process_chunk_safe(self, chunk_index, fast_start)

    def close(self) -> None:
        """Release the seekable-source temp WAV (#4737), never the shared ``self.processor``. Idempotent."""
        self._source.close()

    def get_mastering_recommendation(self, confidence_threshold: float = 0.4) -> Any | None:
        """Weighted mastering profile recommendation. Delegates to chunk_mastering (#4245)."""
        return compute_mastering_recommendation(self, confidence_threshold)

    async def process_all_chunks_async(self) -> None:
        """Background-process all remaining chunks. Delegates to chunk_batch (#4245)."""
        await chunk_batch.process_all_chunks_async(self)

    async def get_full_processed_audio_path(self) -> str:
        """Concatenate all processed chunks into one file. Delegates to chunk_batch (#4245)."""
        return await chunk_batch.get_full_processed_audio_path(self)

    def get_wav_chunk_path(self, chunk_index: int) -> str:
        """PRIMARY output method: process a chunk directly to WAV. Delegates to chunk_streaming (#4245)."""
        return chunk_streaming.get_wav_chunk_path(self, chunk_index)
