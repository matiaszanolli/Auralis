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
from auralis.dsp.constants import DEFAULT_SAMPLE_RATE

# Ensure both project root and backend are in path
backend_path = str(Path(__file__).parent.parent)   # core/ → backend/
project_root = str(Path(__file__).parent.parent.parent.parent)  # → auralis-web/ → project root
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.limits import chunk_cache_dir, create_secure_temp_dir

# Chunk geometry lives in chunk_boundaries and is imported, never redeclared
# (#4024); tests import constants and helpers from where they are defined (#5775).
from core.chunk_boundaries import CHUNK_DURATION
from core import chunk_render, chunk_streaming
from core.chunk_metadata import load_audio_metadata
from core.chunk_mastering import compute_mastering_recommendation
from core.chunk_processor_init import build_collaborators, init_fingerprint_and_processor
from core.chunk_processor_lease import StreamProcessorLeaseMixin
from core.intensity_key import intensity_cache_key
from core.targets_hash import get_targets_hash
from core.seekable_source import SeekableSource
from core.file_signature import FileSignatureService  # Phase 5.1: File signature generation
from core.mastering_target_service import get_mastering_target_service  # Singleton (#4749)
from core.processor_registry import get_processor_factory  # Singleton (injected, not constructed here)

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine
from auralis.core.config.preset_profiles import DEFAULT_PRESET_NAME
from auralis.analysis.mastering_recommendation import MasteringRecommendation

logger = logging.getLogger(__name__)


class ChunkedAudioProcessor(StreamProcessorLeaseMixin):
    """
    Process audio in chunks for fast streaming: fast-starting first chunk,
    background processing of the rest, and smart caching of processed chunks.
    """

    def __init__(
        self,
        track_id: int,
        filepath: str,
        preset: str | None = DEFAULT_PRESET_NAME,
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
        # Quantised once, before anything reads it: the DSP blends with the same
        # value every cache key carries, so a bucket never holds other audio (#5909).
        intensity = intensity_cache_key(intensity)
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

        # #5056: `self.chunk_interval` is deliberately not exposed — no production reader
        # (position math: chunk_boundaries.emitted_chunk_start(); loaders default it from CHUNK_INTERVAL).

        self.chunk_dir = chunk_cache_dir()
        create_secure_temp_dir(self.chunk_dir)

        self._processor_factory: Any = (
            processor_factory if processor_factory is not None else get_processor_factory()
        )
        self._mastering_target_service: Any = get_mastering_target_service()

        # Fingerprint/targets (DB -> .25d file -> extract-on-first-play) and this
        # stream's leased HybridProcessor (#6091), whose state persists across chunks.
        # #4666: MUST precede build_collaborators() — the chunk cache identity
        # (memory key and WAV filename) hashes these targets.
        # `or 44100` only narrows `int | None`; metadata is already loaded.
        sample_rate_valid: int = self.sample_rate or DEFAULT_SAMPLE_RATE
        (
            self.fingerprint,
            self.mastering_targets,
            self.processor,
            # #5306: every later lease (hybrid_processor(), release_lease) MUST pass
            # this same config or it keys a different, 44.1 kHz-assuming entry.
            self.processor_config,
        ) = init_fingerprint_and_processor(
            self._mastering_target_service,
            self._processor_factory,
            track_id,
            filepath,
            self.preset,
            intensity,
            sample_rate_valid,
            file_signature=self.file_signature, cancel_event=self._cancel_event,
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
        self._dsp_fallback: str | None = None  # why the last render is a DSP fallback, not a mastered chunk (#6444)
        # Serialises get_wav_chunk_path()'s check→process→cache cycle per chunk.
        self._sync_cache_lock = threading.Lock()

        # Weighted mastering-profile recommendation cache (real-time UI display).
        self.mastering_recommendation: MasteringRecommendation | None = None
        self.adaptive_mastering_engine: AdaptiveMasteringEngine | None = None

        logger.info(
            f"ChunkedAudioProcessor initialized: track_id={track_id}, "
            f"duration={self.total_duration:.1f}s, chunks={self.total_chunks}, "
            f"preset={preset}, intensity={intensity}"
        )

    @property
    def chunk_rms_history(self) -> list[float]:
        """RMS levels of the chunks processed so far (owned by the LevelManager)."""
        return list(self._level_manager.history)

    @property
    def chunk_gain_history(self) -> list[float]:
        """Gain adjustments applied to the chunks so far (owned by the LevelManager)."""
        return list(self._level_manager.gain_adjustments)

    @property
    def duration(self) -> float | None:
        """Total duration in seconds; the stream entry points read it under this name."""
        return self.total_duration

    @property
    def chunk_duration(self) -> float:
        """Chunk duration in seconds (the render window; emitted segments do not overlap)."""
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
        meta = load_audio_metadata(self.filepath, self._source)
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

    def _lookup_cached_chunk(self, chunk_index: int) -> Path | None:
        """In-memory, then on-disk WAV cache lookup. Delegates to ChunkPathCache (#4245, #4792)."""
        return self._path_cache.lookup_cached(chunk_index)

    def load_chunk(self, chunk_index: int, with_context: bool = True) -> tuple[np.ndarray, float, float]:
        """Load a chunk with optional context. Delegates to chunk_render (#4245)."""
        return chunk_render.load_chunk(self, chunk_index, with_context)

    def _smooth_level_transition(self, chunk: np.ndarray, chunk_index: int) -> np.ndarray:
        """Smooth level transitions across chunks. Delegates to chunk_render (#4245)."""
        return chunk_render.smooth_level_transition(self, chunk, chunk_index)

    def _process_chunk_core(self, chunk_index: int) -> np.ndarray:
        """Shared core of process_chunk/get_wav_chunk_path. Delegates to chunk_render (#4245)."""
        return chunk_render.process_chunk_core(self, chunk_index)

    def process_chunk(
        self, chunk_index: int, locked: bool = False
    ) -> tuple[str, np.ndarray]:
        """Process a chunk to WAV, returning (path, audio); ``locked`` holds _processor_lock (#2388)."""
        return chunk_streaming.process_chunk(self, chunk_index, locked)

    async def process_chunk_safe(self, chunk_index: int) -> tuple[str, np.ndarray]:
        """Thread-pool-offloaded process_chunk (#2388). Delegates to chunk_streaming (#4245)."""
        return await chunk_streaming.process_chunk_safe(self, chunk_index)

    def close(self) -> None:
        """Return the leased HybridProcessor (#6091); release the temp WAV (#4737)."""
        self._close_lease()
        self._source.close()

    def get_mastering_recommendation(self, confidence_threshold: float = 0.4) -> Any | None:
        """Weighted mastering profile recommendation. Delegates to chunk_mastering (#4245)."""
        return compute_mastering_recommendation(self, confidence_threshold)

    def get_wav_chunk_path(self, chunk_index: int) -> str:
        """PRIMARY output method: process a chunk directly to WAV. Delegates to chunk_streaming (#4245)."""
        return chunk_streaming.get_wav_chunk_path(self, chunk_index)
