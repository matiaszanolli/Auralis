#!/usr/bin/env python3

"""
Chunked Audio Processor
~~~~~~~~~~~~~~~~~~~~~~~

Processes audio in 15-second render windows (CHUNK_DURATION) with 5 seconds
of context on each side (CONTEXT_DURATION), for fast streaming start and
instant toggle. Each rendered chunk is trimmed and emitted as a 10-second
non-overlapping segment (CHUNK_INTERVAL) — chunks tile the timeline exactly,
with no boundary crossfade anywhere in the emitted path (crossfade removed in
#2750/#3514/#4642). `core/chunk_boundaries.py` is the single source of truth
for these geometry constants; never hardcode them here.

``ChunkedAudioProcessor`` is a coordinator (#4245): construction and the
public API stay here; logic is delegated to focused sibling modules —
``chunk_fingerprint_registry``, ``chunk_metadata``, ``chunk_processor_init``,
``chunk_path_cache``, ``chunk_content_profile``, ``chunk_render``,
``chunk_streaming``, ``chunk_batch``, plus the pre-existing ``chunk_crossfade``
/ ``chunk_mastering`` — each taking this instance as its first argument and
reading/writing its state directly, so per-instance test patching
(``patch.object(processor, "_method", ...)``) keeps working unchanged. Their
module loggers are all named ``"core.chunked_processor"`` (not ``__name__``)
so log-capture assertions are unaffected by where the code physically lives.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
import sys
import tempfile
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

from config.limits import CHUNK_TEMP_DIRNAME

# Core modules (new modular architecture)
from core.chunk_boundaries import (  # noqa: F401 — CONTEXT_DURATION/OVERLAP_DURATION re-exported for callers
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    OVERLAP_DURATION,
    CONTEXT_DURATION,
)
from core import chunk_batch, chunk_render, chunk_streaming
# The names below are all re-exported (not used directly in this module) so
# that pre-#4245 test patch targets — both plain `patch("core.chunked_processor.
# X", ...)` and class-attribute patches like `...ChunkOperations.extract_chunk_
# segment` (which mutate the class itself, so any import path resolves the same
# object) — and `import core.chunked_processor as cp; cp.X` module-global reads
# keep working unchanged after the logic that used to live here moved out.
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
from core.chunk_crossfade import apply_crossfade_between_chunks  # noqa: F401
from core.chunk_mastering import compute_mastering_recommendation
from core.chunk_processor_init import build_collaborators, init_fingerprint_and_processor
from core.seekable_source import SeekableSource
from core.file_signature import FileSignatureService  # Phase 5.1: File signature generation
from core.level_manager import MAX_LEVEL_CHANGE_DB  # noqa: F401 (re-exported, see below)
from core.mastering_target_service import get_mastering_target_service  # Singleton (#4749)
from core.processor_factory import get_processor_factory  # Singleton (injected, not constructed here)

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine, MasteringRecommendation

logger = logging.getLogger(__name__)

# Chunk geometry / MAX_LEVEL_CHANGE_DB: re-exported, not redeclared (#4024/#4284).


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
    ) -> None:
        """track_id/filepath identify the track; preset=None serves original audio
        unprocessed; chunk_cache is a shared dict of chunk paths across processors.

        cancel_event: optional cooperative-cancel signal (#4815). The caller
        sets it when this processor's owning stream is torn down (seek,
        track change, disconnect); chunk_streaming.process_chunk checks it
        before starting DSP so an already-abandoned chunk bails out instead
        of running to completion unreferenced. None (the default) means "no
        cancellation signal available" — every check degrades to a no-op,
        so callers that don't have a per-stream event (e.g. the prefetch
        path) keep working unchanged.
        """
        self.track_id = track_id
        self.filepath = filepath
        self.preset = preset
        self.intensity = intensity
        self.chunk_cache = chunk_cache if chunk_cache is not None else {}
        self._cancel_event = cancel_event

        # Resolves `filepath` to a seekable path on first chunk load, at most
        # once per track (#4737); lazy so a caller wanting only
        # get_mastering_recommendation() never triggers a decode. Owns a temp
        # dir only after a conversion — see close().
        self._source = SeekableSource(filepath)

        # Generate file signature for cache integrity
        self.file_signature = FileSignatureService.generate(filepath)

        self.sample_rate: int | None = None
        self.total_duration: float | None = None
        self.total_chunks: int | None = None
        self.channels: int | None = None
        self._load_metadata()

        # Expose canonical chunk interval so consumers don't need getattr fallbacks (#2848)
        self.chunk_interval: float = float(CHUNK_INTERVAL)

        # Temp directory for chunks
        self.chunk_dir = Path(tempfile.gettempdir()) / CHUNK_TEMP_DIRNAME
        self.chunk_dir.mkdir(exist_ok=True)

        # Collaborators (#4245: see chunk_processor_init.build_collaborators).
        # Metadata was loaded above, so both fallbacks below are never hit in practice.
        total_duration_valid: float = self.total_duration or 0.0
        sample_rate_valid: int = self.sample_rate or 44100
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
        )
        self._processor_factory: Any = get_processor_factory()  # Phase 2: Use singleton
        self._mastering_target_service: Any = get_mastering_target_service()

        # threading.RLock (not asyncio.Lock): acquired inside asyncio.to_thread()
        # workers (#2388) and re-entered from process_chunk(locked=True) (#3808).
        # Prevents concurrent processor.process() calls from corrupting shared
        # DSP state (envelope followers, gain reduction tracking).
        self._processor_lock = threading.RLock()
        # Serialises get_wav_chunk_path()'s check→process→cache cycle so two
        # concurrent thread-pool calls for the same chunk can't both miss+process it.
        self._sync_cache_lock = threading.Lock()

        # Weighted mastering-profile recommendation cache (real-time UI display).
        self.mastering_recommendation: MasteringRecommendation | None = None
        self.adaptive_mastering_engine: AdaptiveMasteringEngine | None = None

        # Fingerprint/targets (3-tier: DB -> .25d file -> extract-on-first-play)
        # and the shared HybridProcessor instance (state persists across chunks
        # to avoid compressor-envelope artifacts at chunk boundaries).
        self.fingerprint, self.mastering_targets, self.processor = init_fingerprint_and_processor(
            self._mastering_target_service, self._processor_factory, track_id, filepath, self.preset, intensity
        )

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
        """Check the in-memory cache, then the on-disk WAV cache, for chunk_index.

        Delegates to ChunkPathCache (#4245; on-disk-vs-memory rationale: #4792).
        """
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

    def note_cached_chunk_level(self, chunk: np.ndarray, chunk_index: int, gain_db: float = 0.0) -> None:
        """Record a cache-hit chunk's level into LevelManager (#3832). Delegates to chunk_render (#4245)."""
        chunk_render.note_cached_chunk_level(self, chunk, chunk_index, gain_db)

    def _process_chunk_core(self, chunk_index: int, fast_start: bool = False) -> np.ndarray:
        """Shared core of process_chunk/get_wav_chunk_path. Delegates to chunk_render (#4245)."""
        return chunk_render.process_chunk_core(self, chunk_index, fast_start)

    def process_chunk(
        self, chunk_index: int, fast_start: bool = False, locked: bool = False
    ) -> tuple[str, np.ndarray]:
        """Process a chunk and save to WAV; returns (path, audio). Delegates to chunk_streaming (#4245).

        Args:
            locked: If True, hold _processor_lock for the whole chunk so
                concurrent calls serialise (used by process_chunk_safe via a
                thread pool — #2388).
        """
        return chunk_streaming.process_chunk(self, chunk_index, fast_start, locked)

    async def process_chunk_safe(self, chunk_index: int, fast_start: bool = False) -> tuple[str, np.ndarray]:
        """Thread-pool-offloaded process_chunk (keeps the event loop free — #2388).

        Delegates to chunk_streaming (#4245).
        """
        return await chunk_streaming.process_chunk_safe(self, chunk_index, fast_start)

    def close(self) -> None:
        """Release the temp WAV this processor may own (#4737).

        Only the seekable-source temp dir — never ``self.processor``, a
        *shared* HybridProcessor owned by the ProcessorFactory singleton with
        its own lifecycle. Idempotent; a no-op when no conversion happened.
        """
        self._source.close()

    def get_mastering_recommendation(self, confidence_threshold: float = 0.4) -> Any | None:
        """Weighted mastering profile recommendation for this track.

        Delegates to chunk_mastering (#4245) — not a chunk-streaming concern.
        """
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
