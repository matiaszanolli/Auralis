"""
Chunk Boundary Manager
~~~~~~~~~~~~~~~~~~~~~~

Manages chunk boundaries and context windows for audio processing.
Centralizes chunk calculation logic to prevent duplication and ensure consistency.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Chunk configuration - SINGLE SOURCE OF TRUTH
CHUNK_DURATION = 15.0  # seconds - actual chunk length
CHUNK_INTERVAL = 10.0  # seconds - playback interval (CHUNK_DURATION - OVERLAP_DURATION)
OVERLAP_DURATION = 5.0  # seconds - overlap for natural crossfades
CONTEXT_DURATION = 5.0  # seconds of context for better processing quality


class ChunkBoundaryManager:
    """
    Manages chunk boundaries and context windows.

    Provides methods to calculate chunk boundaries, context windows,
    and segment extraction for audio processing.

    **Chunk Model**:
    - Chunk 0: 0s-15s (15s duration, no overlap before)
    - Chunk 1: 10s-25s (15s duration, 5s overlap with chunk 0)
    - Chunk 2: 20s-35s (15s duration, 5s overlap with chunk 1)

    Each chunk is CHUNK_DURATION (15s) long and starts CHUNK_INTERVAL (10s)
    after the previous chunk, creating a 5s overlap region.
    """

    def __init__(self, total_duration: float, sample_rate: int):
        """
        Initialize ChunkBoundaryManager.

        Args:
            total_duration: Total duration of audio in seconds
            sample_rate: Sample rate of audio in Hz
        """
        self.total_duration = total_duration
        self.sample_rate = sample_rate
        self._total_chunks = int(__import__('numpy').ceil(total_duration / CHUNK_INTERVAL))

    @property
    def total_chunks(self) -> int:
        """Get total number of chunks needed for track."""
        return self._total_chunks

    def get_chunk_boundaries(
        self,
        chunk_index: int,
        with_context: bool = True
    ) -> Tuple[float, float, float, float]:
        """
        Get chunk boundaries in seconds.

        Returns (load_start, load_end, trim_start, trim_end) as times in seconds.

        Args:
            chunk_index: Index of chunk (0-based)
            with_context: Whether to include context for processing

        Returns:
            Tuple of (load_start, load_end, trim_start, trim_end) in seconds
        """
        # Calculate chunk core boundaries
        chunk_start = chunk_index * CHUNK_INTERVAL
        chunk_end = min(chunk_start + CHUNK_DURATION, self.total_duration)

        # Add context for processing
        if with_context:
            load_start = max(0, chunk_start - CONTEXT_DURATION)
            load_end = min(self.total_duration, chunk_end + CONTEXT_DURATION)
        else:
            load_start = chunk_start
            load_end = chunk_end

        return load_start, load_end, chunk_start, chunk_end

    def get_chunk_boundaries_samples(
        self,
        chunk_index: int,
        with_context: bool = True
    ) -> Tuple[int, int, int, int]:
        """
        Get chunk boundaries in samples.

        Returns (load_start, load_end, trim_start, trim_end) as sample indices.

        Args:
            chunk_index: Index of chunk (0-based)
            with_context: Whether to include context for processing

        Returns:
            Tuple of (load_start, load_end, trim_start, trim_end) in samples
        """
        load_start, load_end, trim_start, trim_end = self.get_chunk_boundaries(
            chunk_index,
            with_context=with_context
        )

        return (
            int(load_start * self.sample_rate),
            int(load_end * self.sample_rate),
            int(trim_start * self.sample_rate),
            int(trim_end * self.sample_rate)
        )

    def calculate_context_trim_samples(self, chunk_index: int) -> Tuple[int, int]:
        """
        Calculate samples to trim from context at start and end.

        Args:
            chunk_index: Index of chunk (0-based)

        Returns:
            Tuple of (trim_start_samples, trim_end_samples)
        """
        context_samples = int(CONTEXT_DURATION * self.sample_rate)
        is_last = chunk_index == self.total_chunks - 1

        trim_start = context_samples if chunk_index > 0 else 0
        trim_end = 0 if is_last else context_samples

        return trim_start, trim_end

    def is_last_chunk(self, chunk_index: int) -> bool:
        """Check if this is the last chunk."""
        return chunk_index == self.total_chunks - 1

    def get_overlap_samples(self) -> int:
        """Get the number of overlap samples between adjacent chunks."""
        return int(OVERLAP_DURATION * self.sample_rate)

    def get_segment_boundaries(
        self,
        chunk_index: int,
        full_processed_samples: int
    ) -> Tuple[int, int]:
        """
        Calculate segment boundaries for extracting final output from processed chunk.

        The processed chunk includes context, so we need to extract the right segment
        for final output (WAV file or streaming).

        Args:
            chunk_index: Index of chunk
            full_processed_samples: Total samples in processed chunk (with context)

        Returns:
            Tuple of (segment_start, segment_end) in samples
        """
        is_last = self.is_last_chunk(chunk_index)
        overlap_samples = self.get_overlap_samples()
        context_samples = int(CONTEXT_DURATION * self.sample_rate)

        # Start point in processed chunk (skip leading context)
        if chunk_index == 0:
            segment_start = 0  # First chunk: use from start
        else:
            segment_start = context_samples  # Skip leading context

        # End point in processed chunk
        chunk_duration_samples = int(CHUNK_DURATION * self.sample_rate)
        if is_last:
            # Last chunk: calculate from remaining duration
            chunk_start_time = chunk_index * CHUNK_INTERVAL
            remaining_duration = max(0, self.total_duration - chunk_start_time)
            remaining_samples = int(remaining_duration * self.sample_rate)
            segment_end = segment_start + remaining_samples
        else:
            # Regular chunk: extract CHUNK_DURATION
            segment_end = segment_start + chunk_duration_samples

        # Ensure bounds
        segment_end = min(segment_end, full_processed_samples)
        segment_start = min(segment_start, full_processed_samples)

        return segment_start, segment_end

    def log_chunk_info(self, chunk_index: int) -> None:
        """Log information about chunk boundaries for debugging."""
        load_start, load_end, chunk_start, chunk_end = self.get_chunk_boundaries(chunk_index)
        is_last = self.is_last_chunk(chunk_index)

        logger.debug(
            f"Chunk {chunk_index}/{self.total_chunks}: "
            f"load [{load_start:.1f}s-{load_end:.1f}s], "
            f"core [{chunk_start:.1f}s-{chunk_end:.1f}s], "
            f"duration={chunk_end - chunk_start:.1f}s{'  (LAST)' if is_last else ''}"
        )
