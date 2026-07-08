"""
Chunk Boundary Manager
~~~~~~~~~~~~~~~~~~~~~~

Manages chunk boundaries and context windows for audio processing.
Centralizes chunk calculation logic to prevent duplication and ensure consistency.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Chunk configuration - SINGLE SOURCE OF TRUTH
CHUNK_DURATION = 15.0  # seconds - actual chunk length
CHUNK_INTERVAL = 10.0  # seconds - playback interval (CHUNK_DURATION - OVERLAP_DURATION)
OVERLAP_DURATION = 5.0  # seconds - overlap for natural crossfades
CONTEXT_DURATION = 5.0  # seconds of context for better processing quality


def content_chunk_count(total_duration: float) -> int:
    """Number of chunks that actually carry new audio content (#4124).

    Under the overlap model, chunk 0 emits CHUNK_DURATION seconds and every
    later chunk emits CHUNK_INTERVAL seconds of *new* content. The naive
    ``ceil(total_duration / CHUNK_INTERVAL)`` over-allocated a trailing chunk
    for any duration in ``(n*INTERVAL, n*INTERVAL + OVERLAP)``: that extra
    chunk emits 0 new samples, so the real penultimate chunk falls into the
    regular branch (which expects a full interval), comes up short, and gets
    padded with silence — while a 0-sample WAV is cached for the spurious
    chunk. Counting only content-carrying chunks fixes all three.
    """
    return max(1, int(np.ceil((total_duration - OVERLAP_DURATION) / CHUNK_INTERVAL)))


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
        self._total_chunks = content_chunk_count(total_duration)

    @property
    def total_chunks(self) -> int:
        """Get total number of chunks needed for track."""
        return self._total_chunks

    def get_chunk_boundaries(
        self,
        chunk_index: int,
        with_context: bool = True
    ) -> tuple[float, float, float, float]:
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
    ) -> tuple[int, int, int, int]:
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

        # round() instead of int() prevents systematic truncation drift at
        # non-44100 sample rates (e.g. 48 kHz, 96 kHz) where float arithmetic
        # gives results like 719999.999… that int() would truncate by one
        # sample per boundary (fixes #2327).
        return (
            round(load_start * self.sample_rate),
            round(load_end * self.sample_rate),
            round(trim_start * self.sample_rate),
            round(trim_end * self.sample_rate)
        )

    def calculate_context_trim_samples(self, chunk_index: int) -> tuple[int, int]:
        """
        Calculate samples to trim from context at start and end.

        Derived directly from the actual load/core geometry (``load_start``,
        ``chunk_start``, ``chunk_end``, ``load_end``) rather than assuming a
        fixed ``CONTEXT_DURATION`` on both sides. ``get_chunk_boundaries()``
        clamps ``load_start`` to 0 and ``load_end`` to ``total_duration``, so a
        chunk near either edge of the track may have less context actually
        loaded than the nominal amount — trimming the nominal amount
        regardless would eat into real chunk content instead of just context
        (see #3807: this under/over-trim happened both on a short track's
        final chunk's start-context and its *penultimate* chunk's
        end-context, since the latter's context-lookahead is equally capped
        by ``total_duration``). Using the actual interval differences is
        correct by construction for every chunk position, first/last or not.

        Args:
            chunk_index: Index of chunk (0-based)

        Returns:
            Tuple of (trim_start_samples, trim_end_samples)
        """
        load_start, load_end, chunk_start, chunk_end = self.get_chunk_boundaries_samples(chunk_index)

        trim_start = chunk_start - load_start
        trim_end = load_end - chunk_end

        return trim_start, trim_end

    def is_last_chunk(self, chunk_index: int) -> bool:
        """Check if this is the last chunk."""
        return chunk_index == self.total_chunks - 1

    def get_overlap_samples(self) -> int:
        """Get the number of overlap samples between adjacent chunks."""
        return round(OVERLAP_DURATION * self.sample_rate)

    def get_segment_boundaries(
        self,
        chunk_index: int,
        full_processed_samples: int
    ) -> tuple[int, int]:
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
        self.get_overlap_samples()
        context_samples = round(CONTEXT_DURATION * self.sample_rate)

        # Start point in processed chunk (skip leading context)
        if chunk_index == 0:
            segment_start = 0  # First chunk: use from start
        else:
            segment_start = context_samples  # Skip leading context

        # End point in processed chunk
        chunk_duration_samples = round(CHUNK_DURATION * self.sample_rate)
        if is_last:
            # Last chunk: calculate from remaining duration
            chunk_start_time = chunk_index * CHUNK_INTERVAL
            remaining_duration = max(0, self.total_duration - chunk_start_time)
            remaining_samples = round(remaining_duration * self.sample_rate)
            segment_end = segment_start + remaining_samples
        else:
            # Regular chunk: extract CHUNK_DURATION
            segment_end = segment_start + chunk_duration_samples

        # Ensure bounds
        segment_end = min(segment_end, full_processed_samples)
        segment_start = min(segment_start, full_processed_samples)

        return segment_start, segment_end

    def trim_context(
        self,
        audio_chunk: np.ndarray,
        chunk_index: int,
    ) -> np.ndarray:
        """
        Trim context padding from processed audio chunk.

        Uses calculate_context_trim_samples() to get trim amounts, then trims
        start/end, clamping only to avoid producing a negative-length slice.

        The requested trim amounts (CONTEXT_DURATION, a fixed 5s) are
        mathematically guaranteed to fit: get_chunk_boundaries() derives
        load_start/load_end so the loaded (pre-DSP) buffer for chunk_index > 0
        is always longer than the requested start-trim alone, and likewise for
        the end-trim on non-last chunks — see the boundary-derivation proof in
        #3807. An earlier `max_trim_fraction` heuristic capped trims to 25% of
        the chunk's own length, which silently under-trimmed short tracks'
        final chunk (whose loaded buffer is itself short) and desynced
        ChunkOperations.extract_chunk_segment's overlap-skip offset —
        corrupting or dropping the track's final seconds. That heuristic is
        gone; the only remaining clamp is the hard "never go negative" case,
        which only matters if a DSP stage unexpectedly shrank the buffer (a
        separate, `len(output) == len(input)` invariant violation).

        Args:
            audio_chunk: Audio chunk with context padding (processed)
            chunk_index: Index of the chunk being processed

        Returns:
            Audio chunk with context trimmed to actual content

        Examples:
            >>> import numpy as np
            >>> manager = ChunkBoundaryManager(total_duration=60.0, sample_rate=44100)
            >>> # Chunk with 5s context on each side (15s chunk + 10s context = 25s)
            >>> audio = np.zeros((25 * 44100, 2))
            >>> trimmed = manager.trim_context(audio, chunk_index=1)
            >>> len(trimmed)  # Should be ~15s worth of samples
            661500
        """
        # Get trim amounts from boundary calculation
        trim_start_samples, trim_end_samples = self.calculate_context_trim_samples(chunk_index)

        # Trim start context if not first chunk
        if trim_start_samples > 0:
            chunk_length = len(audio_chunk)
            # Hard safety net only — clamp to avoid an empty/negative result if
            # a DSP stage shrank the buffer; does not bind in normal operation.
            actual_trim_start = min(trim_start_samples, max(0, chunk_length - 1))
            if actual_trim_start < trim_start_samples:
                logger.warning(
                    f"Chunk {chunk_index}: start trim clamped to avoid emptying the buffer "
                    f"(requested {trim_start_samples} samples, buffer only had {chunk_length}; "
                    f"clamped to {actual_trim_start}) — DSP may have shrunk the chunk unexpectedly"
                )
            audio_chunk = audio_chunk[actual_trim_start:]
            logger.debug(
                f"Chunk {chunk_index}: trimmed {actual_trim_start/self.sample_rate:.2f}s "
                f"from start"
            )

        # Trim end context if not last chunk
        if trim_end_samples > 0:
            chunk_length = len(audio_chunk)  # Update after potential start trim
            actual_trim_end = min(trim_end_samples, max(0, chunk_length - 1))
            if actual_trim_end < trim_end_samples:
                logger.warning(
                    f"Chunk {chunk_index}: end trim clamped to avoid emptying the buffer "
                    f"(requested {trim_end_samples} samples, buffer only had {chunk_length}; "
                    f"clamped to {actual_trim_end}) — DSP may have shrunk the chunk unexpectedly"
                )
            if actual_trim_end > 0:
                audio_chunk = audio_chunk[:-actual_trim_end]
            logger.debug(
                f"Chunk {chunk_index}: trimmed {actual_trim_end/self.sample_rate:.2f}s "
                f"from end"
            )

        return audio_chunk

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
