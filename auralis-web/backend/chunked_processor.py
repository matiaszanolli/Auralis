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
        """Generate cache key for chunk"""
        return f"{self.track_id}_{self.preset}_{self.intensity}_chunk_{chunk_index}"

    def _get_chunk_path(self, chunk_index: int) -> Path:
        """Get file path for chunk"""
        return self.chunk_dir / f"track_{self.track_id}_{self.preset}_{self.intensity}_chunk_{chunk_index}.wav"

    def load_chunk(self, chunk_index: int, with_context: bool = True) -> Tuple[np.ndarray, float, float]:
        """
        Load a single chunk from audio file with optional context.

        Args:
            chunk_index: Index of chunk to load (0-based)
            with_context: Include context before/after for better processing

        Returns:
            Tuple of (audio_chunk, chunk_start_time, chunk_end_time)
        """
        # Calculate chunk boundaries
        chunk_start = chunk_index * CHUNK_DURATION
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
        Apply crossfade at chunk boundaries.

        Args:
            chunk: Audio chunk to process
            chunk_index: Index of this chunk
            is_last: Whether this is the last chunk

        Returns:
            Chunk with fade in/out applied
        """
        overlap_samples = int(OVERLAP_DURATION * self.sample_rate)

        # Apply fade-in at start (except first chunk)
        if chunk_index > 0 and len(chunk) > overlap_samples:
            fade_in = np.linspace(0.0, 1.0, overlap_samples)
            if chunk.ndim == 2:
                fade_in = fade_in[:, np.newaxis]
            chunk[:overlap_samples] *= fade_in

        # Apply fade-out at end (except last chunk)
        if not is_last and len(chunk) > overlap_samples:
            fade_out = np.linspace(1.0, 0.0, overlap_samples)
            if chunk.ndim == 2:
                fade_out = fade_out[:, np.newaxis]
            chunk[-overlap_samples:] *= fade_out

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
        full_path = self.chunk_dir / f"track_{self.track_id}_{self.preset}_{self.intensity}_full.wav"

        # Check if already exists
        if full_path.exists():
            return str(full_path)

        # Ensure all chunks are processed
        for chunk_idx in range(self.total_chunks):
            self.process_chunk(chunk_idx)

        # Concatenate chunks
        logger.info("Concatenating all processed chunks")
        all_chunks = []

        for chunk_idx in range(self.total_chunks):
            chunk_path = self._get_chunk_path(chunk_idx)
            chunk_audio, _ = load_audio(str(chunk_path))
            all_chunks.append(chunk_audio)

        # Concatenate
        full_audio = np.concatenate(all_chunks, axis=0)

        # Save full file
        save_audio(str(full_path), full_audio, self.sample_rate, subtype='PCM_16')
        logger.info(f"Full audio saved to {full_path}")

        return str(full_path)


def apply_crossfade_between_chunks(chunk1: np.ndarray, chunk2: np.ndarray, overlap_samples: int) -> np.ndarray:
    """
    Apply crossfade between two audio chunks.

    Args:
        chunk1: First audio chunk
        chunk2: Second audio chunk
        overlap_samples: Number of samples to crossfade

    Returns:
        Crossfaded audio segment
    """
    # Get overlap regions
    chunk1_tail = chunk1[-overlap_samples:]
    chunk2_head = chunk2[:overlap_samples]

    # Create fade curves
    fade_out = np.linspace(1.0, 0.0, overlap_samples)
    fade_in = np.linspace(0.0, 1.0, overlap_samples)

    # Handle stereo
    if chunk1_tail.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]

    # Apply fades and mix
    crossfade = chunk1_tail * fade_out + chunk2_head * fade_in

    return crossfade
