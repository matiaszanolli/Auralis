#!/usr/bin/env python3

"""
Chunked Audio Processor
~~~~~~~~~~~~~~~~~~~~~~~

Processes audio in 10-second chunks for fast streaming start and instant toggle.
Applies crossfade between chunks to avoid audible jumps.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import logging
import threading

# Auralis imports
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import numpy as np

# Ensure both project root and backend are in path
backend_path = str(Path(__file__).parent.parent)   # core/ → backend/
project_root = str(Path(__file__).parent.parent.parent.parent)  # core/ → backend/ → auralis-web/ → project root
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.audio_processing_pipeline import AudioProcessingPipeline

# Core modules (new modular architecture)
from core.chunk_boundaries import (  # noqa: F401 — CONTEXT_DURATION re-exported for callers
    ChunkBoundaryManager,
    content_chunk_count,
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    OVERLAP_DURATION,
    CONTEXT_DURATION,
)
from core.chunk_cache_manager import ChunkCacheManager  # Phase 5.1: Cache management
from core.chunk_operations import ChunkOperations  # Phase 3: Unified chunk operations
# Crossfade math + mastering recommendation extracted to their own modules (#4245).
# apply_crossfade_between_chunks is re-exported so existing imports keep working.
from core.chunk_crossfade import apply_crossfade_between_chunks
from core.chunk_mastering import compute_mastering_recommendation
from core.encoding import WAVEncoder
from core.file_signature import FileSignatureService  # Phase 5.1: File signature generation
from core.level_manager import LevelManager
from core.mastering_target_service import (
    MasteringTargetService,  # Phase 4: Unified fingerprint/target management
)
from core.processor_factory import (
    get_processor_factory,  # Singleton accessor (ProcessorFactory is injected, not constructed here)
)

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine, MasteringRecommendation
from auralis.io.saver import save as save_audio
from auralis.io.unified_loader import get_audio_info, load_audio

# Phase 2 (Analysis caching) modules created but not yet integrated
# To be integrated after resolving import structure issues

logger = logging.getLogger(__name__)


def _default_get_fingerprints_repository() -> Any | None:
    """Return the global FingerprintRepository for Tier-1 (DB) fingerprint lookup.

    ChunkedAudioProcessor is constructed from many call sites (streaming controller,
    recommendation service, cache warmer, enhancement route). Rather than thread the
    repository factory through every one, the DB-tier accessor defaults to the global
    ``repository_factory`` registered in ``config.globals.globals_dict`` at startup.
    Returns ``None`` (Tier-1 silently skipped, as before) when globals aren't
    initialised yet — e.g. in unit tests — so this never raises (#3836 / BE-PE-3).
    """
    try:
        from config.globals import globals_dict
        factory = globals_dict.get("repository_factory")
        if factory is None:
            return None
        return factory.fingerprints
    except Exception:  # pragma: no cover - defensive: never break processor init
        return None


# Global cache for last content profiles (used by visualizer API)
# Maps preset name -> last_content_profile dict
_last_content_profiles: dict[str, Any] = {}

# Chunk geometry (CHUNK_DURATION/CHUNK_INTERVAL/OVERLAP_DURATION/CONTEXT_DURATION)
# comes from chunk_boundaries — the single source of truth (#4024) — re-exported
# via the import above so existing `from core.chunked_processor import …` call
# sites keep working.
MAX_LEVEL_CHANGE_DB = 1.5  # maximum allowed level change between chunks in dB


class ChunkedAudioProcessor:
    """
    Process audio in chunks for fast streaming.

    Features:
    - Process first chunk quickly for fast playback start
    - Background processing of remaining chunks
    - Crossfade between chunks to avoid audible gaps
    - Smart caching of processed chunks
    """

    def __init__(
        self,
        track_id: int,
        filepath: str,
        preset: str | None = "adaptive",
        intensity: float = 1.0,
        chunk_cache: dict[str, Any] | None = None
    ) -> None:
        """
        Initialize chunked audio processor.

        Args:
            track_id: Track ID for cache keys
            filepath: Path to source audio file
            preset: Processing preset (adaptive, gentle, warm, bright, punchy)
            intensity: Processing intensity (0.0 - 1.0)
            chunk_cache: Shared cache dictionary for chunk paths
        """
        self.track_id = track_id
        self.filepath = filepath
        self.preset = preset
        self.intensity = intensity
        self.chunk_cache = chunk_cache if chunk_cache is not None else {}

        # Generate file signature for cache integrity (Phase 5.1: Using FileSignatureService)
        self.file_signature = FileSignatureService.generate(filepath)

        # Load audio metadata
        self.sample_rate: int | None = None
        self.total_duration: float | None = None
        self.total_chunks: int | None = None
        self.channels: int | None = None
        self._load_metadata()

        # Expose canonical chunk interval so consumers don't need getattr fallbacks (#2848)
        self.chunk_interval: float = float(CHUNK_INTERVAL)

        # Temp directory for chunks
        self.chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
        self.chunk_dir.mkdir(exist_ok=True)

        # Initialize new modular architecture (Phase 3.5, updated Phase 2, Phase 5.1)
        # These dependencies replace monolithic logic in process_chunk()
        # Type: ignore for untyped core modules (ChunkBoundaryManager, LevelManager, WAVEncoder, ProcessorFactory)
        # Metadata was loaded in _load_metadata(), so both should be non-None by this point
        total_duration_valid: float = self.total_duration or 0.0  # Fallback to 0 if somehow None
        sample_rate_valid: int = self.sample_rate or 44100  # Fallback to standard sample rate
        self._boundary_manager: Any = ChunkBoundaryManager(total_duration_valid, sample_rate_valid)
        self._level_manager: Any = LevelManager(max_level_change_db=MAX_LEVEL_CHANGE_DB)
        self._wav_encoder: Any = WAVEncoder(chunk_dir=self.chunk_dir, default_subtype='PCM_16')
        self._processor_factory: Any = get_processor_factory()  # Phase 2: Use singleton
        self._mastering_target_service: Any = MasteringTargetService(
            get_fingerprints_repository=_default_get_fingerprints_repository,
        )  # Phase 4: Unified fingerprint/target management; Tier-1 DB lookup wired (#3836)
        self._cache_manager: Any = ChunkCacheManager(self.chunk_cache)  # Phase 5.1: Cache management
        # CRITICAL: Threading lock for processor thread-safety
        # Prevents concurrent calls to processor.process() from corrupting state
        # (envelope followers, gain reduction tracking, etc.)
        # Must be a threading.RLock (not asyncio.Lock) so it can be acquired
        # inside asyncio.to_thread() worker threads (issue #2388) and re-entered
        # from process_chunk(locked=True) (fixes #3808 / shared flag race — the
        # use_fingerprint_analysis toggle itself is serialised in
        # AudioProcessingPipeline.apply_enhancement via the shared
        # processor's own _process_lock, see #4354).
        self._processor_lock = threading.RLock()
        # Sync lock for get_wav_chunk_path() which runs in thread-pool context.
        # Serialises the cache-check → process → cache-write cycle so that two
        # concurrent requests for the same chunk never both miss and process it.
        self._sync_cache_lock = threading.Lock()

        # NEW (Beta.9): Load cached fingerprint from .25d file
        # This enables fast processing by skipping per-chunk analysis
        self.fingerprint = None
        self.mastering_targets = None

        # NEW (Priority 4): Weighted profile recommendation caching
        # Stores mastering profile analysis for real-time UI display
        self.mastering_recommendation: MasteringRecommendation | None = None
        self.adaptive_mastering_engine: AdaptiveMasteringEngine | None = None

        # NEW (Phase 7.3, updated Phase 4): Enhanced fingerprint loading via MasteringTargetService
        # 3-tier loading: Database (fastest) → .25d file → Extract from audio (if needed)
        if self.preset is not None:
            # DELEGATE TO MASTERING TARGET SERVICE (Phase 4 refactoring)
            # This replaces duplicate 3-tier loading logic with single service call
            result = self._mastering_target_service.load_fingerprint(
                track_id=track_id,
                filepath=filepath,
                extract_if_missing=False,  # Don't extract on init, only on first chunk playback
                save_extracted=True
            )

            if result is not None:
                self.fingerprint, self.mastering_targets = result
                logger.info(f"✅ Loaded fingerprint/targets via MasteringTargetService for track {track_id}")

        # CRITICAL FIX: Create single shared processor instance to maintain state
        # across chunks. This prevents audio artifacts from resetting compressor
        # envelope followers at chunk boundaries.
        # NOTE: If preset is None, we're serving original/unprocessed audio (no processor needed)
        if self.preset is not None:
            self.processor = self._processor_factory.get_or_create(
                track_id=track_id,
                preset=self.preset,  # narrowed to str by the guard (#4028)
                intensity=intensity,
                mastering_targets=self.mastering_targets
            )
            logger.info(f"🎯 Processor initialized via ProcessorFactory for track {track_id}")
        else:
            self.processor = None  # No processing for original audio (preset is None)

        # Processing state tracking for smooth transitions
        self.chunk_rms_history: list[float] = []  # Track RMS levels of processed chunks
        self.chunk_gain_history: list[float] = []  # Track gain adjustments applied
        self.previous_chunk_tail: np.ndarray | None = None  # Last samples of previous chunk for analysis

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



    def _load_metadata(self) -> None:
        """Load audio file metadata without loading full audio.

        Routes by extension via ``unified_loader.get_audio_info()``: a
        millisecond ``ffprobe`` for FFmpeg-only formats (mp3/m4a/aac/ogg/wma/
        opus) and ``sf.info()`` for natively-decodable ones. The previous
        implementation opened ``sf.SoundFile()`` directly, which libsndfile
        cannot do for FFmpeg-only formats — the open raised and the ``except``
        fell back to a full-file decode (temp-WAV + full float32 read) just to
        read duration/sample-rate/channels, defeating the bounded-decode
        architecture for the dominant library format (#4497).
        """
        try:
            meta = get_audio_info(self.filepath)
            if meta.get('error') or 'sample_rate' not in meta:
                raise RuntimeError(meta.get('error', 'incomplete audio metadata'))
            self.sample_rate = int(meta['sample_rate'])
            self.channels = int(meta['channels'])
            self.total_duration = float(meta['duration_seconds'])
            # Count only content-carrying chunks under the overlap model
            # (#4124) — see core.chunk_boundaries.content_chunk_count.
            self.total_chunks = content_chunk_count(self.total_duration)
        except Exception as e:
            # Last-resort fallback for a genuine probe failure: full decode.
            logger.error(f"Metadata probe failed, falling back to full decode: {e}")
            audio, sr = load_audio(self.filepath)
            self.sample_rate = sr
            # load_audio() returns mono as a 1-D (frames,) array and
            # multi-channel as (frames, channels) — samples-first — so channels
            # is shape[1] and frame count is always shape[0]. The old chained
            # ternary keyed on `shape[0] <= 2`, mislabelling very short stereo
            # clips as mono (#3881).
            self.channels = 1 if audio.ndim == 1 else audio.shape[1]
            self.total_duration = audio.shape[0] / sr
            # Count only content-carrying chunks under the overlap model
            # (#4124) — see core.chunk_boundaries.content_chunk_count.
            self.total_chunks = content_chunk_count(self.total_duration)


    def _get_chunk_path(self, chunk_index: int) -> Path:
        """
        Get file path for chunk with file signature.

        Delegates to WAVEncoder for consistent path generation.
        """
        path = self._wav_encoder.get_chunk_path(
            track_id=self.track_id,
            file_signature=self.file_signature,
            preset=self.preset,
            intensity=self.intensity,
            chunk_index=chunk_index
        )
        return Path(path)

    def _get_wav_chunk_path(self, chunk_index: int) -> Path:
        """
        Get file path for WAV chunk.

        This is the primary output format for the unified architecture
        (replaced WebM/Opus for Web Audio API compatibility).
        Delegates to WAVEncoder.
        """
        return self._get_chunk_path(chunk_index)  # Uses WAVEncoder via _get_chunk_path()

    def load_chunk(self, chunk_index: int, with_context: bool = True) -> tuple[np.ndarray, float, float]:
        """
        Load a single chunk from audio file with optional context.

        NOW DELEGATED TO: ChunkOperations.load_chunk_from_file() (Phase 3 refactoring)

        Args:
            chunk_index: Index of chunk to load (0-based)
            with_context: Include context before/after for better processing

        Returns:
            Tuple of (audio_chunk, chunk_start_time, chunk_end_time)
        """
        assert self.sample_rate is not None

        # DELEGATE TO CHUNK OPERATIONS (Phase 3 refactoring)
        return ChunkOperations.load_chunk_from_file(
            filepath=self.filepath,
            chunk_index=chunk_index,
            sample_rate=self.sample_rate,
            chunk_duration=CHUNK_DURATION,
            chunk_interval=CHUNK_INTERVAL,
            overlap_duration=OVERLAP_DURATION,
            with_context=with_context,
            total_duration=self.total_duration
        )

    def _calculate_rms(self, audio: np.ndarray) -> float:
        """
        Calculate RMS level of audio in dB.

        Delegates to LevelManager (Phase 3.5 refactoring).
        """
        rms_value = self._level_manager.calculate_rms(audio)
        return float(rms_value)

    def _smooth_level_transition(
        self,
        chunk: np.ndarray,
        chunk_index: int
    ) -> np.ndarray:
        """
        Smooth level transitions between chunks by limiting maximum level changes.

        Delegates to LevelManager (Phase 3.5 refactoring).
        This prevents volume jumps by ensuring the current chunk's RMS doesn't differ
        too much from the previous chunk's RMS.

        Args:
            chunk: Processed audio chunk
            chunk_index: Index of this chunk

        Returns:
            Level-smoothed chunk
        """
        # Use LevelManager to smooth transitions. Pass the sample rate so the
        # gain-ramp window is sized correctly (#3831).
        result_tuple = self._level_manager.smooth_transition(
            chunk=chunk,
            chunk_index=chunk_index,
            apply_adjustment=True,
            sample_rate=self.sample_rate or 44100,
        )
        chunk_adjusted, gain_db, was_adjusted = result_tuple

        # Log the adjustment for debugging
        if was_adjusted:
            current_rms = self._level_manager.current_rms
            adjusted_rms = self._calculate_rms(chunk_adjusted)
            logger.info(
                f"Chunk {chunk_index}: Smoothed level transition "
                f"(original RMS: {current_rms:.1f} dB, "
                f"adjusted RMS: {adjusted_rms:.1f} dB, "
                f"gain adjustment: {gain_db:.2f} dB)"
            )
        else:
            current_rms = self._level_manager.current_rms
            logger.info(
                f"Chunk {chunk_index}: Level transition OK "
                f"(RMS: {current_rms:.1f} dB)"
            )

        # Update legacy history tracking for backward compatibility
        history = self._level_manager.history
        gain_adjustments = self._level_manager.gain_adjustments
        self.chunk_rms_history = list(history) if hasattr(history, '__iter__') else []
        self.chunk_gain_history = list(gain_adjustments) if hasattr(gain_adjustments, '__iter__') else []

        return cast(np.ndarray, chunk_adjusted)

    def note_cached_chunk_level(self, chunk: np.ndarray, chunk_index: int) -> None:
        """Record a cache-hit chunk's level into the LevelManager (#3832).

        A cached chunk is returned without going through _process_chunk_core, so
        the LevelManager would otherwise never see it — leaving rms_history out
        of chronological sync, so a later cache-MISS chunk smooths against the
        wrong previous RMS. We RECORD the cached chunk's RMS (apply_adjustment=
        False) without re-adjusting the already-smoothed audio, under the same
        _processor_lock the processing path uses so the history deque is never
        touched concurrently.
        """
        with self._processor_lock:
            self._level_manager.smooth_transition(
                chunk=chunk,
                chunk_index=chunk_index,
                apply_adjustment=False,
                sample_rate=self.sample_rate or 44100,
            )
            # Keep the legacy history mirrors in sync (matches _smooth_level_transition).
            history = self._level_manager.history
            gain_adjustments = self._level_manager.gain_adjustments
            self.chunk_rms_history = list(history) if hasattr(history, '__iter__') else []
            self.chunk_gain_history = list(gain_adjustments) if hasattr(gain_adjustments, '__iter__') else []


    def _process_chunk_core(self, chunk_index: int, fast_start: bool = False) -> np.ndarray:
        """
        Core chunk processing logic (shared by process_chunk and get_wav_chunk_path).

        NOW DELEGATED TO: AudioProcessingPipeline.process_audio() (Phase 1 refactoring)
        This method is now a thin wrapper that:
        1. Loads chunk with context
        2. Delegates to unified pipeline for processing
        3. Trims context and smooths levels

        Args:
            chunk_index: Index of chunk to process
            fast_start: If True, skip fingerprint analysis for faster buffering

        Returns:
            Processed audio chunk (context trimmed, intensity blended, levels smoothed)
        """
        assert self.sample_rate is not None
        # Load chunk with context
        audio_chunk, chunk_start, chunk_end = self.load_chunk(chunk_index, with_context=True)

        # DELEGATE TO UNIFIED PIPELINE (Phase 1 refactoring, updated Phase 2)
        # This replaces ~80 lines of duplicate processing logic with single call
        processed_chunk = AudioProcessingPipeline.process_audio(
            audio=audio_chunk,
            preset=self.preset,
            intensity=self.intensity,
            processor_factory=self._processor_factory,  # Phase 2: Use ProcessorFactory
            track_id=self.track_id,
            targets=self.mastering_targets,
            fast_start=fast_start,
            chunk_index=chunk_index,
            allow_empty=False  # Don't allow empty chunks
        )

        # Trim context (keep only the actual chunk) (Phase 5.1: Using ChunkBoundaryManager)
        processed_chunk = self._boundary_manager.trim_context(cast(np.ndarray, processed_chunk), chunk_index)

        # Validate chunk is not empty before smooth transitions
        if len(processed_chunk) == 0:
            logger.error(f"Chunk {chunk_index} is empty after context trimming. Returning silence.")
            num_channels = audio_chunk.shape[1] if audio_chunk.ndim > 1 else 2
            assert self.sample_rate is not None
            # Preserve the input dtype rather than hardcoding float32 (#3831
            # sibling) so the fallback matches a float64 pipeline if present.
            processed_chunk = np.zeros((self.sample_rate // 10, num_channels), dtype=audio_chunk.dtype)  # 100ms silence

        # CRITICAL FIX: Smooth level transitions between chunks
        # This prevents volume jumps by limiting maximum RMS changes
        processed_chunk = self._smooth_level_transition(processed_chunk, chunk_index)

        return processed_chunk

    def process_chunk(
        self, chunk_index: int, fast_start: bool = False, locked: bool = False
    ) -> tuple[str, np.ndarray]:
        """
        Process a single chunk with Auralis HybridProcessor and save to WAV.

        Returns both the path (for caching) and the numpy array (for streaming).
        This avoids the disk round-trip of saving then immediately reading back.

        Args:
            chunk_index: Index of chunk to process
            fast_start: If True, skip expensive fingerprint analysis for faster initial buffering
            locked: If True, hold _processor_lock (threading.Lock) for the whole
                chunk so concurrent calls serialise. Used by process_chunk_safe,
                which runs this in a thread pool (#2388). Default False keeps the
                direct sync call (and tests) lock-free (#4245: collapses the old
                process_chunk / _process_chunk_locked pair).

        Returns:
            Tuple of (path_to_chunk_file, processed_audio_array)
        """
        if locked:
            with self._processor_lock:
                return self.process_chunk(chunk_index, fast_start, locked=False)

        # Check cache first (Phase 5.1: Using ChunkCacheManager)
        cache_key = ChunkCacheManager.get_chunk_cache_key(
            self.track_id, self.file_signature, self.preset, self.intensity, chunk_index
        )
        cached_path = self._cache_manager.get_cached_chunk_path(cache_key)

        if cached_path is not None:
            assert self.total_chunks is not None
            logger.info(f"Serving cached chunk {chunk_index}/{self.total_chunks}")
            # Load from disk only if cached (for subsequent requests)
            # For initial streaming, audio array is already in memory cache
            from auralis.io.unified_loader import load_audio
            audio, _ = load_audio(str(cached_path))
            return (str(cached_path), audio)

        logger.info(f"Processing chunk {chunk_index}/{self.total_chunks} (preset: {self.preset}, fast_start: {fast_start})")

        # Skip synchronous fingerprint extraction during chunk processing.
        # Loading the full audio file to compute a fingerprint blocks the first
        # chunk for 5-30s (depending on file size/format), causing the frontend
        # to time out and re-send play requests.  The background fingerprint
        # queue handles extraction asynchronously; subsequent plays will use
        # the cached result.  HybridProcessor analyzes per-chunk as fallback.
        if self.fingerprint is None and chunk_index == 0:
            logger.info(f"ℹ️  No cached fingerprint for track {self.track_id} — using per-chunk adaptive processing")

        # Process chunk using shared core logic
        processed_chunk = self._process_chunk_core(chunk_index, fast_start)

        # CRITICAL: Extract the correct segment for this chunk to handle overlaps (Phase 5.1: Using ChunkOperations)
        # - Chunk 0: full CHUNK_DURATION (15s)
        # - Regular chunks: skip overlap (5s), extract CHUNK_INTERVAL (10s)
        # Without this, chunks would overlap and cause audio jumps during playback
        assert self.sample_rate is not None and self.total_chunks is not None and self.total_duration is not None
        extracted_chunk = ChunkOperations.extract_chunk_segment(
            processed_chunk=processed_chunk,
            chunk_index=chunk_index,
            sample_rate=self.sample_rate,
            chunk_duration=CHUNK_DURATION,
            chunk_interval=CHUNK_INTERVAL,
            overlap_duration=OVERLAP_DURATION,
            total_chunks=self.total_chunks,
            total_duration=self.total_duration
        )

        # Save chunk using WAVEncoder (Phase 3.5 refactoring)
        # NOTE: Saved for durability/caching, but we return the array directly to avoid disk I/O
        chunk_path = self._wav_encoder.encode_and_save_from_path(
            audio=extracted_chunk,
            sample_rate=self.sample_rate,
            track_id=self.track_id,
            file_signature=self.file_signature,
            preset=self.preset,
            intensity=self.intensity,
            chunk_index=chunk_index,
            subtype='PCM_16'
        )

        # Cache the path (Phase 5.1: Using ChunkCacheManager)
        self._cache_manager.cache_chunk_path(cache_key, chunk_path)

        logger.info(f"Chunk {chunk_index} processed and saved to {chunk_path}")
        # Return both path (for caching) and audio array (for immediate streaming)
        return (str(chunk_path), extracted_chunk)

    async def process_chunk_safe(self, chunk_index: int, fast_start: bool = False) -> tuple[str, np.ndarray]:
        """
        Process a single chunk with thread-safe locking (async version).

        Offloads the CPU-intensive DSP work (HPSS, EQ, loudness normalization) to a
        thread-pool worker via asyncio.to_thread(), keeping the event loop free to handle
        WebSocket heartbeats, pause/seek commands, and other coroutines during the
        5-30 second processing window (issue #2388).

        Serialisation is provided by _processor_lock (threading.Lock): concurrent
        calls block in the thread pool rather than on the event loop.

        Args:
            chunk_index: Index of chunk to process
            fast_start: If True, skip expensive fingerprint analysis for faster initial buffering

        Returns:
            Tuple of (path_to_chunk_file, processed_audio_array)
            - path: for caching/durability
            - audio: numpy array for immediate streaming (avoids disk round-trip)
        """
        return await asyncio.to_thread(self.process_chunk, chunk_index, fast_start, True)




    def get_mastering_recommendation(self, confidence_threshold: float = 0.4) -> Any | None:
        """Get a weighted mastering profile recommendation for this track.

        Delegates to core.chunk_mastering (#4245) — this is not a chunk-streaming
        concern. State (adaptive_mastering_engine / fingerprint /
        mastering_recommendation) is read and cached on this processor.
        """
        return compute_mastering_recommendation(self, confidence_threshold)



    async def process_all_chunks_async(self) -> None:
        """
        Background task to process all remaining chunks.

        Processes chunks sequentially to avoid overwhelming the system.
        Uses thread-safe locking to prevent concurrent processor state corruption.
        """
        assert self.total_chunks is not None
        logger.info(f"Starting background processing of {self.total_chunks - 1} remaining chunks")

        for chunk_idx in range(1, self.total_chunks):
            try:
                # Check if already cached (Phase 5.1: Using ChunkCacheManager)
                cache_key = ChunkCacheManager.get_chunk_cache_key(
                    self.track_id, self.file_signature, self.preset, self.intensity, chunk_idx
                )
                if self._cache_manager.get_cached_chunk_path(cache_key) is not None:
                    continue

                # Process chunk with thread-safe locking
                await self.process_chunk_safe(chunk_idx)

                # Small delay to avoid CPU saturation
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to process chunk {chunk_idx}: {e}")

        logger.info("Background chunk processing complete")

    async def get_full_processed_audio_path(self) -> str:
        """
        Concatenate all processed chunks into a single file.

        Returns:
            Path to full concatenated audio file
        """
        assert self.sample_rate is not None and self.total_chunks is not None
        full_path = self.chunk_dir / f"track_{self.track_id}_{self.file_signature}_{self.preset}_{self.intensity}_full.wav"

        # Check if already exists
        if full_path.exists():
            return str(full_path)

        # Ensure all chunks are processed sequentially (fixes #2318).
        # Calling process_chunk_safe() directly avoids the nested-event-loop
        # antipattern that process_chunk_synchronized() created via asyncio.run().
        for chunk_idx in range(self.total_chunks):
            await self.process_chunk_safe(chunk_idx, fast_start=(chunk_idx == 0))

        # Concatenate chunks with proper crossfading
        logger.info("Concatenating all processed chunks")
        all_chunks: list[np.ndarray] = []

        for chunk_idx in range(self.total_chunks):
            chunk_path = self._get_chunk_path(chunk_idx)
            chunk_audio, _ = load_audio(str(chunk_path))
            all_chunks.append(chunk_audio)

        # Chunks are stored as contiguous, non-overlapping segments — simple
        # concatenation preserves correct duration (#2750).  The previous
        # crossfade incorrectly blended unrelated audio at boundaries and
        # shortened output by (N-1) × 5s.
        full_audio = np.concatenate(all_chunks, axis=0)

        # Save full file
        assert self.sample_rate is not None
        save_audio(str(full_path), full_audio, self.sample_rate, subtype='PCM_16')
        logger.info(f"Full audio saved to {full_path}")

        return str(full_path)


    def get_wav_chunk_path(self, chunk_index: int) -> str:
        """
        Get WAV chunk for unified streaming architecture.

        This is the PRIMARY output method for the unified architecture.
        Process audio and encode directly to WAV in a single pass.
        WAV format is required for Web Audio API compatibility.

        Args:
            chunk_index: Index of chunk to retrieve

        Returns:
            Path to WAV chunk file
        """
        assert self.sample_rate is not None and self.total_chunks is not None and self.total_duration is not None
        # _sync_cache_lock serialises the full check→process→cache cycle so that
        # two concurrent thread-pool calls for the same chunk cannot both miss the
        # cache, both process the chunk, and produce conflicting results.
        with self._sync_cache_lock:
            # Check cache first (Phase 5.1: Using ChunkCacheManager)
            cache_key = ChunkCacheManager.get_wav_cache_key(
                self.track_id, self.file_signature, self.preset, self.intensity, chunk_index
            )
            cached_path = self._cache_manager.get_cached_chunk_path(cache_key)
            if cached_path is not None:
                logger.info(f"Serving cached WAV chunk {chunk_index}")
                return str(cached_path)

            # Get WAV output path
            wav_chunk_path = self._get_wav_chunk_path(chunk_index)

            # Check if already exists on disk
            if wav_chunk_path.exists():
                logger.info(f"WAV chunk {chunk_index} already exists on disk")
                self._cache_manager.cache_chunk_path(cache_key, wav_chunk_path)
                return str(wav_chunk_path)

            logger.info(f"Processing chunk {chunk_index} directly to WAV")

            # Use shared core processing logic (eliminates duplicate code)
            processed_chunk = self._process_chunk_core(chunk_index, fast_start=False)

            # Extract the correct segment for this chunk (Phase 5.1: Using ChunkOperations)
            extracted_chunk = ChunkOperations.extract_chunk_segment(
                processed_chunk=processed_chunk,
                chunk_index=chunk_index,
                sample_rate=self.sample_rate,
                chunk_duration=CHUNK_DURATION,
                chunk_interval=CHUNK_INTERVAL,
                overlap_duration=OVERLAP_DURATION,
                total_chunks=self.total_chunks,
                total_duration=self.total_duration
            )

            # Encode directly to WAV (Web Audio API compatible)
            try:
                from encoding.wav_encoder import WAVEncoderError, encode_to_wav

                wav_bytes = encode_to_wav(extracted_chunk, self.sample_rate)

                # Write WAV file
                wav_chunk_path.write_bytes(wav_bytes)
                logger.info(f"Chunk {chunk_index} encoded to WAV: {len(wav_bytes)} bytes")

            except WAVEncoderError as e:
                logger.error(f"WAV encoding failed for chunk {chunk_index}: {e}")
                raise RuntimeError(f"Failed to encode chunk to WAV: {e}")

            # Cache the path (Phase 5.1: Using ChunkCacheManager)
            self._cache_manager.cache_chunk_path(cache_key, wav_chunk_path)

        # Store last_content_profile globally for visualizer API access
        # This allows the /api/processing/parameters endpoint to show real processing data
        if self.processor is not None:
            processor_profile = getattr(self.processor, 'last_content_profile', None)
            if processor_profile and self.preset is not None:
                _last_content_profiles[self.preset.lower()] = processor_profile
                logger.debug(f"📊 Stored processing profile for preset '{self.preset}'")

        return str(wav_chunk_path)


def get_last_content_profile(preset: str) -> dict[str, Any] | None:
    """
    Get the last content profile for a given preset.
    Used by /api/processing/parameters endpoint to show real processing data.

    Args:
        preset: Preset name (e.g., "adaptive", "gentle", "warm", etc.)

    Returns:
        Last content profile dict or None if not available
    """
    value = _last_content_profiles.get(preset.lower())
    if isinstance(value, dict):
        return value
    return None
