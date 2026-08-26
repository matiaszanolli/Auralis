"""
Chunk Boundary Manager
~~~~~~~~~~~~~~~~~~~~~~

Manages chunk boundaries and context windows for audio processing.
Centralizes chunk calculation logic to prevent duplication and ensure consistency.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import NamedTuple

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


# Minimum amount of new audio the first chunk of a seek must still carry.
# Below this, the seek advances to the next chunk instead: an immediate
# buffer underrun is worse than starting a fraction of a second late.
SEEK_MIN_CHUNK_REMAINDER = 0.5


def emitted_chunk_start(chunk_index: int) -> float:
    """Source time of the FIRST sample chunk ``chunk_index`` actually emits.

    Not the same as the chunk's *core* start (``chunk_index * CHUNK_INTERVAL``),
    which is what ``get_chunk_boundaries`` returns. ``ChunkOperations.
    extract_chunk_segment`` skips ``OVERLAP_DURATION`` from the head of every
    chunk ``>= 1`` because the previous chunk already emitted that audio, so:

        chunk 0 emits [0, 15)      — CHUNK_DURATION, nothing skipped
        chunk 1 emits [15, 25)     — 1*10 + 5
        chunk 2 emits [25, 35)     — 2*10 + 5

    Contiguous with no gaps, but offset by OVERLAP_DURATION from the core
    timeline for every chunk after the first. Confusing the two is #4557.
    """
    if chunk_index <= 0:
        return 0.0
    return chunk_index * CHUNK_INTERVAL + OVERLAP_DURATION


def emitted_chunk_length(chunk_index: int) -> float:
    """Seconds of NEW audio chunk ``chunk_index`` emits (ignoring the last-chunk
    short case, which is bounded by total duration)."""
    return CHUNK_DURATION if chunk_index <= 0 else CHUNK_INTERVAL


def chunk_for_position(
    position: float,
    total_chunks: int,
    min_remainder: float = SEEK_MIN_CHUNK_REMAINDER,
    *,
    total_duration: float | None = None,
) -> tuple[int, float, float]:
    """Map a source-time position onto the chunk that actually emits it (#4557).

    Returns ``(chunk_index, offset_into_emitted_audio, effective_position)``.

    The seek path used to compute ``int(position / CHUNK_INTERVAL)`` and trim
    ``position - index * CHUNK_INTERVAL`` off the front of the delivered
    buffer. That maps onto the *core* timeline while the buffer it trims has
    already had ``OVERLAP_DURATION`` removed, so every seek to >= 10s landed
    exactly OVERLAP_DURATION past the requested point.

    ``effective_position`` is normally ``position``, but differs when the
    requested point falls within ``min_remainder`` of the end of its chunk:
    trimming that chunk down to a sliver produces an immediate underrun, so the
    seek advances to the start of the next chunk instead. Callers must report
    ``effective_position`` as the stream's seek position, not the request, or
    the client's counter drifts by exactly the amount skipped.

    Args:
        position: Requested source time in seconds.
        total_chunks: Number of chunks the processor will emit.
        min_remainder: Minimum seconds of audio the first chunk must retain.
        total_duration: Actual track duration. When supplied, positions at or
            beyond the end are clamped far enough back to retain audible audio
            instead of producing an empty first buffer (#5254).
    """
    pos = max(0.0, float(position))
    total_chunks = max(1, int(total_chunks))
    if total_duration is not None:
        duration = max(0.0, float(total_duration))
        pos = min(pos, max(0.0, duration - min_remainder))

    # Chunk 0 emits a full CHUNK_DURATION, so anything inside it maps there;
    # after that the emitted timeline is offset by OVERLAP_DURATION.
    if pos < CHUNK_DURATION:
        index = 0
    else:
        index = int((pos - OVERLAP_DURATION) // CHUNK_INTERVAL)
    index = max(0, min(index, total_chunks - 1))

    offset = max(0.0, pos - emitted_chunk_start(index))

    # Avoid delivering a sliver as the first chunk of the stream.
    if (
        index < total_chunks - 1
        and emitted_chunk_length(index) - offset < min_remainder
    ):
        index += 1
        offset = 0.0
        pos = emitted_chunk_start(index)

    return index, offset, pos


class NormalStreamPlan(NamedTuple):
    """No-overlap chunk plan for stream_normal.py (#5032).

    Distinct from the overlap-aware CHUNK_INTERVAL/OVERLAP_DURATION model the
    rest of this module describes: normal streaming sends raw chunks with no
    server-side crossfade, so ``interval_samples == chunk_samples`` here —
    everything else in this module (``emitted_chunk_start``, ``CHUNK_INTERVAL``,
    ``chunk_for_position``...) is about the enhanced/seek path instead.
    """
    duration: float
    chunk_duration: float
    chunk_samples: int
    interval_samples: int
    total_chunks: int
    start_chunk: int
    seek_offset: float
    first_chunk_trim_samples: int


def normal_stream_plan(
    total_frames: int, sample_rate: int, start_position: float = 0.0
) -> NormalStreamPlan:
    """Compute the no-overlap chunk plan for normal (unprocessed) streaming.

    Pulled out of stream_normal.py's inline math (#5032) so it is unit-testable
    without any file I/O; behaviour is unchanged.

    ``first_chunk_trim_samples`` is the number of samples to skip off the
    front of ``start_chunk``'s read so playback lands exactly on
    ``start_position`` — the server-side trim #4560 made authoritative
    (``seek_offset`` is informational only; no client ever consumed it).
    """
    chunk_duration = float(CHUNK_DURATION)
    chunk_samples = int(chunk_duration * sample_rate)
    interval_samples = chunk_samples  # No overlap for the normal path.

    total_chunks = max(1, int(np.ceil(total_frames / interval_samples)))

    start_chunk = 0
    if start_position > 0:
        start_sample = int(start_position * sample_rate)
        start_chunk = min(start_sample // interval_samples, total_chunks - 1)

    seek_offset = start_position - (start_chunk * chunk_duration)
    first_chunk_trim_samples = (
        int(start_position * sample_rate) - (start_chunk * interval_samples)
        if start_position > 0
        else 0
    )

    return NormalStreamPlan(
        duration=total_frames / sample_rate,
        chunk_duration=chunk_duration,
        chunk_samples=chunk_samples,
        interval_samples=interval_samples,
        total_chunks=total_chunks,
        start_chunk=start_chunk,
        seek_offset=seek_offset,
        first_chunk_trim_samples=first_chunk_trim_samples,
    )


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
