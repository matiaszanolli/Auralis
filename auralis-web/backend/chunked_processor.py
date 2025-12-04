#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Chunked Audio Processor
~~~~~~~~~~~~~~~~~~~~~~~

Processes audio in 10-second chunks for fast streaming start and instant toggle.
Applies crossfade between chunks to avoid audible jumps.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
import logging
from pathlib import Path
from typing import Optional, Tuple
import tempfile
import asyncio

# Auralis imports
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio
from auralis.io.saver import save as save_audio
from auralis.analysis.mastering_fingerprint import MasteringFingerprint
from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine

logger = logging.getLogger(__name__)

# Global cache for last content profiles (used by visualizer API)
# Maps preset name -> last_content_profile dict
_last_content_profiles = {}

# Chunk configuration
# NEW (Beta 12.1): 15s chunks with 10s intervals = 5s overlap for natural crossfades
# Benefits:
# - 5-second overlap provides excellent crossfade material
# - More natural transitions between chunks
# - Better audio quality with proper blending
# - Still fast enough for responsive preset switching
CHUNK_DURATION = 15  # seconds - actual chunk length
CHUNK_INTERVAL = 10  # seconds - playback interval (CHUNK_DURATION - OVERLAP_DURATION)
OVERLAP_DURATION = 5  # seconds - overlap for natural crossfades (was 0.1s)
CONTEXT_DURATION = 5  # seconds of context for better processing quality
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
        preset: str = "adaptive",
        intensity: float = 1.0,
        chunk_cache: Optional[dict] = None
    ):
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

        # Generate file signature for cache integrity
        self.file_signature = self._generate_file_signature()

        # Load audio metadata
        self.sample_rate = None
        self.total_duration = None
        self.total_chunks = None
        self._load_metadata()

        # Temp directory for chunks
        self.chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
        self.chunk_dir.mkdir(exist_ok=True)

        # CRITICAL: Async lock for processor thread-safety
        # Prevents concurrent calls to processor.process() from corrupting state
        # (envelope followers, gain reduction tracking, etc.)
        self._processor_lock = asyncio.Lock()

        # NEW (Beta.9): Load cached fingerprint from .25d file
        # This enables fast processing by skipping per-chunk analysis
        self.fingerprint = None
        self.mastering_targets = None

        # NEW (Priority 4): Weighted profile recommendation caching
        # Stores mastering profile analysis for real-time UI display
        self.mastering_recommendation = None
        self.adaptive_mastering_engine = None

        if self.preset is not None:
            from auralis.analysis.fingerprint import FingerprintStorage

            # Try to load from .25d file
            cached_data = FingerprintStorage.load(Path(filepath))
            if cached_data:
                self.fingerprint, self.mastering_targets = cached_data
                logger.info(f"✅ Loaded fingerprint from .25d file for track {track_id}")
            else:
                logger.info(f"⏳ No .25d file found for track {track_id}, will extract on first chunk")

        # CRITICAL FIX: Create single shared processor instance to maintain state
        # across chunks. This prevents audio artifacts from resetting compressor
        # envelope followers at chunk boundaries.
        # NOTE: If preset is None, we're serving original/unprocessed audio (no processor needed)
        if self.preset is not None:
            config = UnifiedConfig()
            config.set_processing_mode("adaptive")
            config.mastering_profile = self.preset.lower()
            self.processor = HybridProcessor(config)

            # NEW (Beta.9): If we loaded mastering targets from .25d file, set them
            # This enables fixed-target processing (8x faster, instant toggle)
            if self.mastering_targets is not None:
                self.processor.set_fixed_mastering_targets(self.mastering_targets)
                logger.info(f"🎯 Fixed mastering targets applied to processor for track {track_id}")
        else:
            self.processor = None  # No processing for original audio

        # Processing state tracking for smooth transitions
        self.chunk_rms_history = []  # Track RMS levels of processed chunks
        self.chunk_gain_history = []  # Track gain adjustments applied
        self.previous_chunk_tail = None  # Last samples of previous chunk for analysis

        logger.info(
            f"ChunkedAudioProcessor initialized: track_id={track_id}, "
            f"duration={self.total_duration:.1f}s, chunks={self.total_chunks}, "
            f"preset={preset}, intensity={intensity}"
        )

    def _generate_file_signature(self) -> str:
        """
        Generate a unique signature for the audio file based on metadata.

        This ensures cached chunks are invalidated if the file changes.
        Uses modification time and file size for fast computation.

        Returns:
            Hex string signature (first 8 chars of hash)
        """
        import os
        import hashlib

        try:
            stat = os.stat(self.filepath)
            # Combine mtime and size for unique signature
            signature_input = f"{stat.st_mtime}_{stat.st_size}_{self.filepath}"
            signature = hashlib.md5(signature_input.encode()).hexdigest()[:8]
            return signature
        except Exception as e:
            logger.warning(f"Failed to generate file signature: {e}, using fallback")
            # Fallback: use filepath hash only
            return hashlib.md5(self.filepath.encode()).hexdigest()[:8]

    def _load_metadata(self):
        """Load audio file metadata without loading full audio"""
        try:
            import soundfile as sf
            with sf.SoundFile(self.filepath) as f:
                self.sample_rate = f.samplerate
                self.total_duration = len(f) / f.samplerate
                # Calculate chunks based on CHUNK_INTERVAL (not CHUNK_DURATION)
                # This accounts for the 5s overlap between chunks
                self.total_chunks = int(np.ceil(self.total_duration / CHUNK_INTERVAL))
        except Exception as e:
            logger.error(f"Failed to load audio metadata: {e}")
            # Fallback: load entire audio with optional downsampling (slower)
            audio, sr = load_audio(
                self.filepath,
                target_sample_rate=self.config.processing_sample_rate
            )
            self.sample_rate = sr
            self.total_duration = len(audio) / sr
            # Calculate chunks based on CHUNK_INTERVAL (not CHUNK_DURATION)
            self.total_chunks = int(np.ceil(self.total_duration / CHUNK_INTERVAL))

    def _get_cache_key(self, chunk_index: int) -> str:
        """
        Generate cache key for chunk with file signature.

        Includes track_id, file_signature, preset, intensity, and chunk_index.
        This ensures chunks cannot be misassigned to different tracks or file versions.
        """
        return f"{self.track_id}_{self.file_signature}_{self.preset}_{self.intensity}_chunk_{chunk_index}"

    def _get_chunk_path(self, chunk_index: int) -> Path:
        """
        Get file path for chunk with file signature.

        Includes file signature in filename to prevent serving wrong audio
        if track file is modified or replaced.
        """
        return self.chunk_dir / f"track_{self.track_id}_{self.file_signature}_{self.preset}_{self.intensity}_chunk_{chunk_index}.wav"

    def _get_wav_chunk_path(self, chunk_index: int) -> Path:
        """
        Get file path for WAV chunk.

        This is the primary output format for the unified architecture
        (replaced WebM/Opus for Web Audio API compatibility).
        """
        return self.chunk_dir / f"track_{self.track_id}_{self.file_signature}_{self.preset}_{self.intensity}_chunk_{chunk_index}.wav"

    def load_chunk(self, chunk_index: int, with_context: bool = True) -> Tuple[np.ndarray, float, float]:
        """
        Load a single chunk from audio file with optional context.

        Chunks after the first include OVERLAP_DURATION at the start for crossfading.
        This ensures no audio is lost during crossfade concatenation.

        Args:
            chunk_index: Index of chunk to load (0-based)
            with_context: Include context before/after for better processing

        Returns:
            Tuple of (audio_chunk, chunk_start_time, chunk_end_time)
        """
        # Calculate chunk boundaries with 15s/10s model
        # Chunk 0: 0s-15s (15s duration)
        # Chunk 1: 10s-25s (15s duration, 5s overlap with chunk 0)
        # Chunk 2: 20s-35s (15s duration, 5s overlap with chunk 1)
        # Each chunk is CHUNK_DURATION (15s) long
        # Each chunk starts CHUNK_INTERVAL (10s) after the previous
        chunk_start = chunk_index * CHUNK_INTERVAL
        chunk_end = min(chunk_start + CHUNK_DURATION, self.total_duration)

        # Add context for processing (but trim later)
        if with_context:
            load_start = max(0, chunk_start - CONTEXT_DURATION)
            load_end = min(self.total_duration, chunk_end + CONTEXT_DURATION)
        else:
            load_start = chunk_start
            load_end = chunk_end

        # Load audio segment
        try:
            import soundfile as sf
            start_frame = int(load_start * self.sample_rate)
            frames_to_read = int((load_end - load_start) * self.sample_rate)

            with sf.SoundFile(self.filepath) as f:
                f.seek(start_frame)
                audio = f.read(frames_to_read)

                # Ensure 2D array (samples, channels)
                if audio.ndim == 1:
                    audio = audio[:, np.newaxis]

        except Exception as e:
            logger.warning(f"Soundfile loading failed, using fallback: {e}")
            # Fallback: load entire audio and slice with optional downsampling
            full_audio, _ = load_audio(
                self.filepath,
                target_sample_rate=self.config.processing_sample_rate
            )
            start_sample = int(load_start * self.sample_rate)
            end_sample = int(load_end * self.sample_rate)

            # Ensure we don't try to read beyond the file
            end_sample = min(end_sample, len(full_audio))

            if start_sample >= len(full_audio):
                logger.error(f"Chunk {chunk_index} start ({start_sample}) beyond file length ({len(full_audio)})")
                # Return silence instead of crashing
                audio = np.zeros((1, full_audio.shape[1] if full_audio.ndim > 1 else 1))
            else:
                audio = full_audio[start_sample:end_sample]

        # Validate that we loaded something
        if len(audio) == 0:
            logger.error(f"Chunk {chunk_index} resulted in empty audio (start={load_start:.1f}s, end={load_end:.1f}s, duration={self.total_duration:.1f}s)")
            # Return minimal silence instead of empty array to prevent downstream crashes
            num_channels = 2  # Default to stereo
            audio = np.zeros((int(0.1 * self.sample_rate), num_channels))  # 100ms of silence
            logger.warning(f"Returning 100ms of silence for chunk {chunk_index} to prevent crash")

        return audio, chunk_start, chunk_end

    def _calculate_rms(self, audio: np.ndarray) -> float:
        """Calculate RMS level of audio in dB."""
        rms = np.sqrt(np.mean(audio ** 2))
        return 20 * np.log10(rms + 1e-10)  # Add epsilon to avoid log(0)

    def _smooth_level_transition(
        self,
        chunk: np.ndarray,
        chunk_index: int
    ) -> np.ndarray:
        """
        Smooth level transitions between chunks by limiting maximum level changes.

        This prevents volume jumps by ensuring the current chunk's RMS doesn't differ
        too much from the previous chunk's RMS.

        Args:
            chunk: Processed audio chunk
            chunk_index: Index of this chunk

        Returns:
            Level-smoothed chunk
        """
        # First chunk OR no history (processor was just created) - establish baseline
        if chunk_index == 0 or len(self.chunk_rms_history) == 0:
            chunk_rms = self._calculate_rms(chunk)
            self.chunk_rms_history.append(chunk_rms)
            self.chunk_gain_history.append(0.0)  # No adjustment for first chunk
            return chunk

        # Calculate current and previous RMS
        current_rms = self._calculate_rms(chunk)
        previous_rms = self.chunk_rms_history[-1]

        # Calculate level difference
        level_diff_db = current_rms - previous_rms

        # Limit the level change
        if abs(level_diff_db) > MAX_LEVEL_CHANGE_DB:
            # Calculate required gain adjustment to stay within limits
            target_diff = MAX_LEVEL_CHANGE_DB if level_diff_db > 0 else -MAX_LEVEL_CHANGE_DB
            required_adjustment_db = target_diff - level_diff_db

            # Convert dB to linear gain
            gain_adjustment = 10 ** (required_adjustment_db / 20)

            # Apply gain adjustment
            chunk_adjusted = chunk * gain_adjustment

            # Log the adjustment
            adjusted_rms = self._calculate_rms(chunk_adjusted)
            logger.info(
                f"Chunk {chunk_index}: Smoothed level transition "
                f"(original RMS: {current_rms:.1f} dB, "
                f"adjusted RMS: {adjusted_rms:.1f} dB, "
                f"diff from previous: {level_diff_db:.1f} dB -> {target_diff:.1f} dB)"
            )

            # Store adjusted values
            self.chunk_rms_history.append(adjusted_rms)
            self.chunk_gain_history.append(required_adjustment_db)

            return chunk_adjusted
        else:
            # Level change is acceptable, no adjustment needed
            logger.info(
                f"Chunk {chunk_index}: Level transition OK "
                f"(RMS: {current_rms:.1f} dB, diff: {level_diff_db:.1f} dB)"
            )
            self.chunk_rms_history.append(current_rms)
            self.chunk_gain_history.append(0.0)
            return chunk

    def _trim_context(self, audio_chunk: np.ndarray, chunk_index: int) -> np.ndarray:
        """
        Trim context from audio chunk to keep only the actual chunk content.

        This method consolidates the duplicate context trimming logic that was
        previously implemented in two places (process_chunk and process_chunk_synchronized).

        Args:
            audio_chunk: Audio chunk with context (potentially padded)
            chunk_index: Index of the chunk being processed

        Returns:
            Audio chunk with context trimmed
        """
        context_samples = int(CONTEXT_DURATION * self.sample_rate)
        actual_start = chunk_index * CHUNK_INTERVAL  # Use interval, not duration
        is_last = chunk_index == self.total_chunks - 1

        # Safety: Ensure we have enough samples to trim
        chunk_length = len(audio_chunk)

        # For the last chunk, be more conservative with trimming
        # since the audio is much shorter than expected
        max_trim_samples = chunk_length // 4  # Never trim more than 1/4 of the chunk

        if actual_start > 0:  # Not first chunk, trim start context
            trim_start = min(context_samples, max_trim_samples)
            if chunk_length > trim_start:
                audio_chunk = audio_chunk[trim_start:]
                logger.debug(f"Chunk {chunk_index}: trimmed {trim_start/self.sample_rate:.2f}s from start")
            else:
                logger.warning(f"Chunk {chunk_index} too short to trim start context ({chunk_length} < {trim_start}). Keeping as-is.")

        # Don't trim end context for last chunk
        if not is_last:
            chunk_length = len(audio_chunk)  # Update after potential start trim
            trim_end = min(context_samples, max_trim_samples)
            if chunk_length > trim_end:
                audio_chunk = audio_chunk[:-trim_end]
                logger.debug(f"Chunk {chunk_index}: trimmed {trim_end/self.sample_rate:.2f}s from end")
            else:
                logger.warning(f"Chunk {chunk_index} too short to trim end context ({chunk_length} < {trim_end}). Keeping as-is.")

        return audio_chunk

    def apply_crossfade(
        self,
        chunk: np.ndarray,
        chunk_index: int,
        is_last: bool = False
    ) -> np.ndarray:
        """
        No longer applies individual fades - chunks are crossfaded during concatenation.

        This method is kept for compatibility but now just returns the chunk unmodified.
        Crossfading happens in get_full_processed_audio_path() via apply_crossfade_between_chunks().

        Args:
            chunk: Audio chunk to process
            chunk_index: Index of this chunk
            is_last: Whether this is the last chunk

        Returns:
            Unmodified chunk (crossfading happens during concatenation)
        """
        # Crossfading is now handled during concatenation for better quality
        # No individual fades needed
        return chunk

    def process_chunk(self, chunk_index: int, fast_start: bool = False) -> str:
        """
        Process a single chunk with Auralis HybridProcessor.

        Args:
            chunk_index: Index of chunk to process
            fast_start: If True, skip expensive fingerprint analysis for faster initial buffering

        Returns:
            Path to processed chunk file
        """
        # Check cache first
        cache_key = self._get_cache_key(chunk_index)
        cached_path = self.chunk_cache.get(cache_key)

        if cached_path and Path(cached_path).exists():
            logger.info(f"Serving cached chunk {chunk_index}/{self.total_chunks}")
            return cached_path

        logger.info(f"Processing chunk {chunk_index}/{self.total_chunks} (preset: {self.preset}, fast_start: {fast_start})")

        # NEW (Beta.9): Extract fingerprint on first chunk if not cached
        # This creates the .25d file for future fast processing
        if self.fingerprint is None and chunk_index == 0 and self.preset is not None:
            logger.info(f"🔍 Extracting fingerprint for track {self.track_id} (first playback)...")

            try:
                # Load full audio for fingerprint extraction
                from auralis.io.unified_loader import load_audio
                full_audio, sr = load_audio(self.filepath)

                # Extract complete 25D fingerprint
                from auralis.analysis.fingerprint import AudioFingerprintAnalyzer
                analyzer = AudioFingerprintAnalyzer()

                # Add metadata for .25d file
                from mutagen import File as MutagenFile
                audio_file = MutagenFile(self.filepath)
                duration = audio_file.info.length if audio_file else self.total_duration

                self.fingerprint = analyzer.analyze(full_audio, sr)
                # Add metadata (will be stripped before saving)
                self.fingerprint['_metadata'] = {
                    'duration': duration,
                    'sample_rate': sr
                }

                # Generate mastering targets from fingerprint
                self.mastering_targets = self._generate_targets_from_fingerprint(self.fingerprint)

                # Set targets on processor for fixed-target mode
                if self.processor is not None:
                    self.processor.set_fixed_mastering_targets(self.mastering_targets)
                    logger.info(f"🎯 Applied newly extracted mastering targets to processor")

                # Save to .25d file for future use
                from auralis.analysis.fingerprint import FingerprintStorage
                FingerprintStorage.save(Path(self.filepath), self.fingerprint, self.mastering_targets)
                logger.info(f"💾 Saved fingerprint to .25d file for track {self.track_id}")

            except Exception as e:
                logger.error(f"Fingerprint extraction failed: {e}, using default processing")
                # Continue with normal processing (HybridProcessor will analyze per-chunk)
                self.fingerprint = None
                self.mastering_targets = None

        # Load chunk with context
        audio_chunk, chunk_start, chunk_end = self.load_chunk(chunk_index, with_context=True)

        # SPECIAL CASE: If preset is None, we're serving original/unprocessed audio
        # Just trim context and encode without any processing
        if self.processor is None:
            logger.info(f"Serving original audio for chunk {chunk_index} (no processing)")
            processed_chunk = audio_chunk
        else:
            # NEW (Beta.9): Use fixed targets if available (from .25d file)
            # This bypasses expensive per-chunk analysis and enables instant toggle
            if self.mastering_targets is not None:
                logger.info(f"⚡ Processing chunk {chunk_index} with fixed targets from fingerprint")

                # Disable per-chunk fingerprint analysis (we already have the targets)
                original_fingerprint_setting = self.processor.content_analyzer.use_fingerprint_analysis
                self.processor.content_analyzer.use_fingerprint_analysis = False

                try:
                    # Process with fixed targets (no per-chunk analysis)
                    # The processor will use the pre-computed mastering targets
                    processed_chunk = self.processor.process(audio_chunk)
                finally:
                    # Restore fingerprint analysis setting
                    self.processor.content_analyzer.use_fingerprint_analysis = original_fingerprint_setting

            elif fast_start and chunk_index == 0:
                # FAST-PATH OPTIMIZATION: Skip fingerprint analysis for first chunk
                # This reduces initial buffering from ~30s to <5s by avoiding slow librosa.beat.tempo call
                # Fingerprint can be extracted later in background for subsequent chunks
                # Temporarily disable fingerprint analysis
                original_fingerprint_setting = self.processor.content_analyzer.use_fingerprint_analysis
                self.processor.content_analyzer.use_fingerprint_analysis = False
                logger.info("⚡ Fast-start: Skipping fingerprint analysis for first chunk")

                try:
                    # Process with shared HybridProcessor instance
                    # This maintains compressor state (envelope followers, gain reduction)
                    # across chunk boundaries, preventing audio artifacts
                    processed_chunk = self.processor.process(audio_chunk)
                finally:
                    # Restore fingerprint analysis for subsequent chunks
                    self.processor.content_analyzer.use_fingerprint_analysis = original_fingerprint_setting
            else:
                # Normal processing with fingerprint analysis
                processed_chunk = self.processor.process(audio_chunk)

        # Trim context (keep only the actual chunk)
        processed_chunk = self._trim_context(processed_chunk, chunk_index)

        # Apply intensity blending
        if self.intensity < 1.0:
            # Load the exact same chunk with context that we processed
            original_chunk_with_context, _, _ = self.load_chunk(chunk_index, with_context=True)

            # Trim context from original to match processed chunk dimensions
            original_chunk_with_context = self._trim_context(original_chunk_with_context, chunk_index)

            # Now both chunks should have the same length
            min_len = min(len(original_chunk_with_context), len(processed_chunk))
            processed_chunk = (
                original_chunk_with_context[:min_len] * (1.0 - self.intensity) +
                processed_chunk[:min_len] * self.intensity
            )

        # Validate chunk is not empty before smooth transitions
        if len(processed_chunk) == 0:
            logger.error(f"Chunk {chunk_index} is empty after context trimming. Returning silence.")
            num_channels = audio_chunk.shape[1] if audio_chunk.ndim > 1 else 2
            processed_chunk = np.zeros((self.sample_rate // 10, num_channels))  # 100ms silence

        # CRITICAL FIX: Smooth level transitions between chunks
        # This prevents volume jumps by limiting maximum RMS changes
        processed_chunk = self._smooth_level_transition(processed_chunk, chunk_index)

        # Determine if this is the last chunk
        is_last = chunk_index == self.total_chunks - 1

        # Apply crossfade
        processed_chunk = self.apply_crossfade(processed_chunk, chunk_index, is_last)

        # Save chunk
        chunk_path = self._get_chunk_path(chunk_index)
        save_audio(str(chunk_path), processed_chunk, self.sample_rate, subtype='PCM_16')

        # Cache the path
        self.chunk_cache[cache_key] = str(chunk_path)

        logger.info(f"Chunk {chunk_index} processed and saved to {chunk_path}")
        return str(chunk_path)

    async def process_chunk_safe(self, chunk_index: int, fast_start: bool = False) -> str:
        """
        Process a single chunk with thread-safe locking (async version).

        This async method wraps processor.process() calls with an asyncio lock to prevent
        concurrent access from corrupting the shared processor state (envelope followers,
        gain reduction tracking, etc.).

        Args:
            chunk_index: Index of chunk to process
            fast_start: If True, skip expensive fingerprint analysis for faster initial buffering

        Returns:
            Path to processed chunk file
        """
        async with self._processor_lock:
            # All processor.process() calls are now serialized
            return self.process_chunk(chunk_index, fast_start)

    def process_chunk_synchronized(self, chunk_index: int, fast_start: bool = False) -> str:
        """
        Process a single chunk with thread-safe locking (synchronous wrapper).

        This method is for use in synchronous contexts (e.g., get_full_processed_audio_path).
        It ensures that processor.process() calls are protected by the lock, but since
        asyncio.Lock cannot be used in synchronous context, we run the async version
        in a new event loop.

        Args:
            chunk_index: Index of chunk to process
            fast_start: If True, skip expensive fingerprint analysis for faster initial buffering

        Returns:
            Path to processed chunk file
        """
        # For synchronous calls, we need to run the async lock in an event loop
        # This is less ideal but necessary for backward compatibility with sync methods
        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()
            # If we're already in an async context, schedule the coroutine
            return asyncio.create_task(self.process_chunk_safe(chunk_index, fast_start))
        except RuntimeError:
            # No event loop running, create a new one
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.process_chunk_safe(chunk_index, fast_start))
            finally:
                loop.close()

    def _get_track_fingerprint_cache_key(self) -> str:
        """
        Get cache key for track-level fingerprint.

        Fingerprints are track-specific, not chunk-specific, so we cache them
        once per track to avoid expensive recomputation for every chunk.
        """
        return f"fingerprint_{self.track_id}_{self.file_signature}"

    def get_cached_fingerprint(self) -> Optional[dict]:
        """
        Get cached track-level fingerprint if available.

        Returns:
            dict: Cached fingerprint or None if not cached
        """
        cache_key = self._get_track_fingerprint_cache_key()
        return self.chunk_cache.get(cache_key)

    def cache_fingerprint(self, fingerprint: dict):
        """
        Cache track-level fingerprint for reuse across all chunks.

        This avoids expensive fingerprint analysis (especially librosa tempo detection)
        for every chunk, reducing processing time by ~0.5-1s per chunk.

        Args:
            fingerprint: Complete 25D fingerprint dictionary
        """
        cache_key = self._get_track_fingerprint_cache_key()
        self.chunk_cache[cache_key] = fingerprint
        logger.info(f"Cached track-level fingerprint for track {self.track_id}")

    def get_mastering_recommendation(self, confidence_threshold: float = 0.4):
        """
        Get weighted mastering profile recommendation for this track (Priority 4).

        Lazily initializes the adaptive mastering engine and caches the recommendation.
        Uses the track's fingerprint if available, otherwise analyzes from audio.

        Args:
            confidence_threshold: Threshold for blending (default 0.4)

        Returns:
            MasteringRecommendation with weighted_profiles populated if hybrid, or None if unable to analyze
        """
        # Return cached recommendation if available
        if self.mastering_recommendation is not None:
            return self.mastering_recommendation

        try:
            # Initialize engine on first use
            if self.adaptive_mastering_engine is None:
                self.adaptive_mastering_engine = AdaptiveMasteringEngine()

            # Get or extract fingerprint
            if self.fingerprint is None:
                logger.info(f"📊 Extracting mastering fingerprint for recommendation analysis...")
                try:
                    self.fingerprint = MasteringFingerprint.from_audio_file(self.filepath)
                except Exception as e:
                    logger.warning(f"Failed to extract fingerprint for recommendations: {e}")
                    return None

            # Get weighted recommendation
            if self.fingerprint:
                self.mastering_recommendation = self.adaptive_mastering_engine.recommend_weighted(
                    self.fingerprint,
                    confidence_threshold=confidence_threshold
                )
                logger.info(
                    f"🎯 Mastering recommendation generated: "
                    f"profile={self.mastering_recommendation.primary_profile.name}, "
                    f"confidence={self.mastering_recommendation.confidence_score:.0%}, "
                    f"blended={'yes' if self.mastering_recommendation.weighted_profiles else 'no'}"
                )
                return self.mastering_recommendation

        except Exception as e:
            logger.error(f"Failed to generate mastering recommendation: {e}")
            return None

        return None

    def _generate_targets_from_fingerprint(self, fingerprint: dict) -> dict:
        """
        Generate mastering targets from 25D fingerprint.

        This converts acoustic characteristics into processing parameters.
        Targets remain fixed for the entire track, enabling fast processing.

        Args:
            fingerprint: 25D fingerprint dictionary

        Returns:
            Dictionary of mastering targets
        """
        freq = fingerprint.get('frequency', {})
        dynamics = fingerprint.get('dynamics', {})

        # Target loudness based on current LUFS
        current_lufs = dynamics.get('lufs', -14.0)
        target_lufs = -14.0  # Standard streaming loudness

        # Target crest factor (preserve dynamic range character)
        current_crest = dynamics.get('crest_db', 12.0)
        target_crest = max(10.0, current_crest * 0.85)  # Slight reduction

        # EQ adjustments based on frequency balance
        eq_adjustments = {
            'sub_bass': self._calculate_eq_adjustment(freq.get('sub_bass_pct', 5.0), ideal=5.0),
            'bass': self._calculate_eq_adjustment(freq.get('bass_pct', 15.0), ideal=15.0),
            'low_mid': self._calculate_eq_adjustment(freq.get('low_mid_pct', 18.0), ideal=18.0),
            'mid': self._calculate_eq_adjustment(freq.get('mid_pct', 22.0), ideal=22.0),
            'upper_mid': self._calculate_eq_adjustment(freq.get('upper_mid_pct', 20.0), ideal=20.0),
            'presence': self._calculate_eq_adjustment(freq.get('presence_pct', 13.0), ideal=13.0),
            'air': self._calculate_eq_adjustment(freq.get('air_pct', 7.0), ideal=7.0),
        }

        return {
            'target_lufs': target_lufs,
            'target_crest_db': target_crest,
            'eq_adjustments_db': eq_adjustments,
            'compression': {
                'ratio': 2.5,
                'amount': 0.6
            }
        }

    def _calculate_eq_adjustment(self, current_pct: float, ideal: float) -> float:
        """
        Calculate EQ adjustment in dB to reach ideal percentage.

        Args:
            current_pct: Current frequency percentage
            ideal: Ideal frequency percentage

        Returns:
            EQ adjustment in dB (clamped to ±6 dB)
        """
        # Simple proportional adjustment
        diff = ideal - current_pct
        # ±1% difference = ±0.5 dB adjustment (gentle)
        adjustment = diff * 0.5
        # Clamp to reasonable range
        return max(-6.0, min(6.0, adjustment))

    async def process_all_chunks_async(self):
        """
        Background task to process all remaining chunks.

        Processes chunks sequentially to avoid overwhelming the system.
        Uses thread-safe locking to prevent concurrent processor state corruption.
        """
        logger.info(f"Starting background processing of {self.total_chunks - 1} remaining chunks")

        for chunk_idx in range(1, self.total_chunks):
            try:
                # Check if already cached
                cache_key = self._get_cache_key(chunk_idx)
                if cache_key in self.chunk_cache:
                    continue

                # Process chunk with thread-safe locking
                await self.process_chunk_safe(chunk_idx)

                # Small delay to avoid CPU saturation
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to process chunk {chunk_idx}: {e}")

        logger.info("Background chunk processing complete")

    def get_full_processed_audio_path(self) -> str:
        """
        Concatenate all processed chunks into a single file.

        Returns:
            Path to full concatenated audio file
        """
        full_path = self.chunk_dir / f"track_{self.track_id}_{self.file_signature}_{self.preset}_{self.intensity}_full.wav"

        # Check if already exists
        if full_path.exists():
            return str(full_path)

        # Ensure all chunks are processed with thread-safe locking
        # Use fast-start for first chunk to reduce initial buffering time
        for chunk_idx in range(self.total_chunks):
            self.process_chunk_synchronized(chunk_idx, fast_start=(chunk_idx == 0))

        # Concatenate chunks with proper crossfading
        logger.info("Concatenating all processed chunks with crossfading")
        all_chunks = []

        for chunk_idx in range(self.total_chunks):
            chunk_path = self._get_chunk_path(chunk_idx)
            chunk_audio, _ = load_audio(str(chunk_path))
            all_chunks.append(chunk_audio)

        # Apply crossfade between consecutive chunks
        overlap_samples = int(OVERLAP_DURATION * self.sample_rate)

        if len(all_chunks) == 1:
            # Single chunk, no crossfading needed
            full_audio = all_chunks[0]
        else:
            # Start with first chunk
            result = all_chunks[0]

            for i in range(1, len(all_chunks)):
                # Crossfade current result with next chunk
                result = apply_crossfade_between_chunks(result, all_chunks[i], overlap_samples)

            full_audio = result

        # Save full file
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
        # Check cache first
        cache_key = f"{self.track_id}_{self.file_signature}_{self.preset}_{self.intensity}_wav_{chunk_index}"
        if cache_key in self.chunk_cache:
            cached_path = Path(self.chunk_cache[cache_key])
            if cached_path.exists():
                logger.info(f"Serving cached WAV chunk {chunk_index}")
                return str(cached_path)

        # Get WAV output path
        wav_chunk_path = self._get_wav_chunk_path(chunk_index)

        # Check if already exists on disk
        if wav_chunk_path.exists():
            logger.info(f"WAV chunk {chunk_index} already exists on disk")
            self.chunk_cache[cache_key] = str(wav_chunk_path)
            return str(wav_chunk_path)

        # Process audio chunk
        logger.info(f"Processing chunk {chunk_index} directly to WAV")

        # Load chunk with context
        audio_chunk, chunk_start, chunk_end = self.load_chunk(chunk_index, with_context=True)

        # SPECIAL CASE: If preset is None, we're serving original/unprocessed audio
        # Just trim context and encode without any processing
        if self.processor is None:
            logger.info(f"Serving original audio for chunk {chunk_index} (no processing)")
            processed_chunk = audio_chunk
        else:
            # FAST-PATH OPTIMIZATION: Skip fingerprint analysis for first chunk
            # This reduces initial buffering from ~30s to <5s
            if chunk_index == 0:
                # Temporarily disable fingerprint analysis
                original_fingerprint_setting = self.processor.content_analyzer.use_fingerprint_analysis
                self.processor.content_analyzer.use_fingerprint_analysis = False
                logger.info("⚡ Fast-start: Skipping fingerprint analysis for first chunk")

                try:
                    # Process with shared HybridProcessor instance
                    processed_chunk = self.processor.process(audio_chunk)
                finally:
                    # Restore fingerprint analysis for subsequent chunks
                    self.processor.content_analyzer.use_fingerprint_analysis = original_fingerprint_setting
            else:
                # Normal processing with fingerprint analysis
                processed_chunk = self.processor.process(audio_chunk)

        # Trim context (keep only the actual chunk)
        processed_chunk = self._trim_context(processed_chunk, chunk_index)

        # Apply intensity blending
        if self.intensity < 1.0:
            # Load the exact same chunk with context that we processed
            original_chunk_with_context, _, _ = self.load_chunk(chunk_index, with_context=True)

            # Trim context from original to match processed chunk dimensions
            original_chunk_with_context = self._trim_context(original_chunk_with_context, chunk_index)

            # Now both chunks should have the same length
            min_len = min(len(original_chunk_with_context), len(processed_chunk))
            processed_chunk = (
                original_chunk_with_context[:min_len] * (1.0 - self.intensity) +
                processed_chunk[:min_len] * self.intensity
            )

        # Extract the correct segment for this chunk
        # NO windowing - perfectly continuous audio segments
        is_last = chunk_index == self.total_chunks - 1
        overlap_samples = int(OVERLAP_DURATION * self.sample_rate)

        if chunk_index == 0:
            # First chunk: extract exactly 30 seconds (or full duration if shorter)
            expected_samples = int(CHUNK_DURATION * self.sample_rate)
            processed_chunk = processed_chunk[:expected_samples]
            logger.debug(f"✅ Chunk 0: extracted [0:{expected_samples}] samples ({expected_samples/self.sample_rate:.2f}s)")

        elif is_last:
            # Last chunk: skip the overlap, extract remaining duration
            # Use CHUNK_INTERVAL (10s) for chunk position, not CHUNK_DURATION (15s)
            chunk_start_time = chunk_index * CHUNK_INTERVAL
            remaining_duration = max(0, self.total_duration - chunk_start_time)
            expected_samples = int(remaining_duration * self.sample_rate)
            # Skip the overlap region to avoid duplicate audio
            processed_chunk = processed_chunk[overlap_samples:overlap_samples + expected_samples]
            logger.debug(f"✅ Chunk {chunk_index} (last): chunk starts at {chunk_start_time:.1f}s, remaining {remaining_duration:.1f}s, extracted {expected_samples} samples")

        else:
            # Regular chunk: skip the 3s overlap, extract exactly 30 seconds
            expected_samples = int(CHUNK_DURATION * self.sample_rate)
            # Skip the overlap region to avoid duplicate audio
            processed_chunk = processed_chunk[overlap_samples:overlap_samples + expected_samples]
            logger.debug(f"✅ Chunk {chunk_index}: skipped {overlap_samples} overlap, extracted {expected_samples} samples ({expected_samples/self.sample_rate:.2f}s)")

        # CRITICAL FIX: Smooth level transitions between chunks
        # This must come AFTER extraction to ensure consistent boundaries
        processed_chunk = self._smooth_level_transition(processed_chunk, chunk_index)

        # Verify final length (should never need padding with this logic)
        current_samples = len(processed_chunk)
        if current_samples < expected_samples:
            # Pad with silence if too short (edge case, shouldn't happen)
            padding_needed = expected_samples - current_samples
            padding = np.zeros((padding_needed, processed_chunk.shape[1] if processed_chunk.ndim > 1 else 1))
            if processed_chunk.ndim == 1:
                padding = padding.flatten()
            processed_chunk = np.concatenate([processed_chunk, padding])
            logger.warning(f"⚠️ Chunk {chunk_index} was {padding_needed} samples short, padded with silence")
        elif current_samples > expected_samples:
            # This shouldn't happen with the new logic, but trim just in case
            processed_chunk = processed_chunk[:expected_samples]
            logger.warning(f"⚠️ Chunk {chunk_index} was {current_samples - expected_samples} samples too long, trimmed")

        # Encode directly to WAV (Web Audio API compatible)
        try:
            from encoding.wav_encoder import encode_to_wav, WAVEncoderError

            wav_bytes = encode_to_wav(processed_chunk, self.sample_rate)

            # Write WAV file
            wav_chunk_path.write_bytes(wav_bytes)
            logger.info(f"Chunk {chunk_index} encoded to WAV: {len(wav_bytes)} bytes")

        except WAVEncoderError as e:
            logger.error(f"WAV encoding failed for chunk {chunk_index}: {e}")
            raise RuntimeError(f"Failed to encode chunk to WAV: {e}")

        # Cache the path
        self.chunk_cache[cache_key] = str(wav_chunk_path)

        # Store last_content_profile globally for visualizer API access
        # This allows the /api/processing/parameters endpoint to show real processing data
        global _last_content_profiles
        if hasattr(self.processor, 'last_content_profile') and self.processor.last_content_profile:
            _last_content_profiles[self.preset.lower()] = self.processor.last_content_profile
            logger.debug(f"📊 Stored processing profile for preset '{self.preset}'")

        return str(wav_chunk_path)


def _convert_to_webm_opus(input_wav: str, output_webm: str, bitrate: str = "128k") -> None:
    """
    Convert WAV audio to WebM/Opus format using ffmpeg.

    Args:
        input_wav: Path to input WAV file
        output_webm: Path to output WebM file
        bitrate: Opus bitrate (default: 128k for good quality)
    """
    import subprocess

    try:
        subprocess.run([
            'ffmpeg',
            '-i', input_wav,
            '-c:a', 'libopus',
            '-b:a', bitrate,
            '-vbr', 'on',  # Variable bitrate for better quality
            '-compression_level', '10',  # Maximum compression
            '-y',  # Overwrite output file
            output_webm
        ], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion failed: {e.stderr}")
        raise RuntimeError(f"Failed to convert WAV to WebM/Opus: {e.stderr}")


def apply_crossfade_between_chunks(chunk1: np.ndarray, chunk2: np.ndarray, overlap_samples: int) -> np.ndarray:
    """
    Apply crossfade between two audio chunks and return concatenated result.

    Uses overlap-add: the last N samples of chunk1 are mixed with the first N samples
    of chunk2, then we keep all of chunk1 + the non-overlapping part of chunk2.
    This preserves total duration without losing audio.

    Args:
        chunk1: First audio chunk
        chunk2: Second audio chunk
        overlap_samples: Number of samples to crossfade

    Returns:
        Concatenated audio with crossfade applied at boundary (no audio lost)
    """
    # Ensure we don't try to overlap more than available
    actual_overlap = min(overlap_samples, len(chunk1), len(chunk2))

    if actual_overlap <= 0:
        # No overlap possible, just concatenate
        return np.concatenate([chunk1, chunk2], axis=0)

    # Get overlap regions
    chunk1_tail = chunk1[-actual_overlap:]
    chunk2_head = chunk2[:actual_overlap]

    # Create fade curves
    fade_out = np.linspace(1.0, 0.0, actual_overlap)
    fade_in = np.linspace(0.0, 1.0, actual_overlap)

    # Handle stereo
    if chunk1_tail.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]

    # Apply fades and mix the overlap region
    crossfade = chunk1_tail * fade_out + chunk2_head * fade_in

    # IMPORTANT: Don't lose audio!
    # Result = full chunk1 (except last overlap) + crossfaded overlap + rest of chunk2
    result = np.concatenate([
        chunk1[:-actual_overlap],  # Chunk1 without the tail that will be mixed
        crossfade,                  # The mixed overlap region
        chunk2[actual_overlap:]     # Chunk2 without the head that was mixed
    ], axis=0)

    return result


def get_last_content_profile(preset: str):
    """
    Get the last content profile for a given preset.
    Used by /api/processing/parameters endpoint to show real processing data.

    Args:
        preset: Preset name (e.g., "adaptive", "gentle", "warm", etc.)

    Returns:
        Last content profile dict or None if not available
    """
    global _last_content_profiles
    return _last_content_profiles.get(preset.lower())
