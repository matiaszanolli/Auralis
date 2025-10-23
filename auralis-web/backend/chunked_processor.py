#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Chunked Audio Processor
~~~~~~~~~~~~~~~~~~~~~~~

Processes audio in 30-second chunks for fast streaming start.
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

logger = logging.getLogger(__name__)

# Chunk configuration
CHUNK_DURATION = 30  # seconds
OVERLAP_DURATION = 1  # seconds for crossfade
CONTEXT_DURATION = 5  # seconds of context for better processing quality


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
                self.total_chunks = int(np.ceil(self.total_duration / CHUNK_DURATION))
        except Exception as e:
            logger.error(f"Failed to load audio metadata: {e}")
            # Fallback: load entire audio (slower)
            audio, sr = load_audio(self.filepath)
            self.sample_rate = sr
            self.total_duration = len(audio) / sr
            self.total_chunks = int(np.ceil(self.total_duration / CHUNK_DURATION))

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
        # Calculate chunk boundaries
        # First chunk: 0-30s
        # Second chunk: 29-60s (includes 1s overlap)
        # Third chunk: 59-90s (includes 1s overlap)
        if chunk_index == 0:
            chunk_start = 0
        else:
            # Start 1 second earlier to create overlap
            chunk_start = chunk_index * CHUNK_DURATION - OVERLAP_DURATION

        chunk_end = min(chunk_start + CHUNK_DURATION + (OVERLAP_DURATION if chunk_index > 0 else 0),
                       self.total_duration)

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
            # Fallback: load entire audio and slice
            full_audio, _ = load_audio(self.filepath)
            start_sample = int(load_start * self.sample_rate)
            end_sample = int(load_end * self.sample_rate)
            audio = full_audio[start_sample:end_sample]

        return audio, chunk_start, chunk_end

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

    def process_chunk(self, chunk_index: int) -> str:
        """
        Process a single chunk with Auralis HybridProcessor.

        Args:
            chunk_index: Index of chunk to process

        Returns:
            Path to processed chunk file
        """
        # Check cache first
        cache_key = self._get_cache_key(chunk_index)
        cached_path = self.chunk_cache.get(cache_key)

        if cached_path and Path(cached_path).exists():
            logger.info(f"Serving cached chunk {chunk_index}/{self.total_chunks}")
            return cached_path

        logger.info(f"Processing chunk {chunk_index}/{self.total_chunks} (preset: {self.preset})")

        # Load chunk with context
        audio_chunk, chunk_start, chunk_end = self.load_chunk(chunk_index, with_context=True)

        # Configure processor
        config = UnifiedConfig()
        config.set_processing_mode("adaptive")
        config.mastering_profile = self.preset.lower()

        # Process with HybridProcessor
        processor = HybridProcessor(config)
        processed_chunk = processor.process(audio_chunk)

        # Trim context (keep only the actual chunk)
        context_samples = int(CONTEXT_DURATION * self.sample_rate)
        actual_start = chunk_index * CHUNK_DURATION

        if actual_start > 0:  # Not first chunk, trim start context
            processed_chunk = processed_chunk[context_samples:]

        # Don't trim end context for last chunk
        is_last = chunk_index == self.total_chunks - 1
        if not is_last:
            processed_chunk = processed_chunk[:-context_samples]

        # Apply intensity blending
        if self.intensity < 1.0:
            # Get original chunk without context for blending
            original_chunk, _, _ = self.load_chunk(chunk_index, with_context=False)
            # Ensure same length
            min_len = min(len(original_chunk), len(processed_chunk))
            processed_chunk = (
                original_chunk[:min_len] * (1.0 - self.intensity) +
                processed_chunk[:min_len] * self.intensity
            )

        # Apply crossfade
        processed_chunk = self.apply_crossfade(processed_chunk, chunk_index, is_last)

        # Save chunk
        chunk_path = self._get_chunk_path(chunk_index)
        save_audio(str(chunk_path), processed_chunk, self.sample_rate, subtype='PCM_16')

        # Cache the path
        self.chunk_cache[cache_key] = str(chunk_path)

        logger.info(f"Chunk {chunk_index} processed and saved to {chunk_path}")
        return str(chunk_path)

    async def process_all_chunks_async(self):
        """
        Background task to process all remaining chunks.

        Processes chunks sequentially to avoid overwhelming the system.
        """
        logger.info(f"Starting background processing of {self.total_chunks - 1} remaining chunks")

        for chunk_idx in range(1, self.total_chunks):
            try:
                # Check if already cached
                cache_key = self._get_cache_key(chunk_idx)
                if cache_key in self.chunk_cache:
                    continue

                # Process chunk
                self.process_chunk(chunk_idx)

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

        # Ensure all chunks are processed
        for chunk_idx in range(self.total_chunks):
            self.process_chunk(chunk_idx)

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
