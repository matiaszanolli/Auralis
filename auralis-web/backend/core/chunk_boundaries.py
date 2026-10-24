"""
Chunk Boundary Manager
~~~~~~~~~~~~~~~~~~~~~~

Manages chunk boundaries and context windows for audio processing.
Centralizes chunk calculation logic to prevent duplication and ensure consistency.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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
    which is what ``get_chunk_boundaries`` returns. The former ChunkOperations module
    (split in #6270 into chunk_file_loading / chunk_segment_extraction).
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

    A position at or past the end is clamped back to
    ``duration - SEEK_MIN_CHUNK_REMAINDER`` (#5409) — the normal-path twin of
    the #5254 fix in ``chunk_for_position``. Unclamped, the seek sample lands
    past ``total_frames`` where ``sf.SoundFile.seek()`` raises and the stream
    ends in an ``audio_stream_error`` frame instead of on the last audible
    instant (a saved playback position at the very end of a track hits this
    on every resume).
    """
    chunk_duration = float(CHUNK_DURATION)
    chunk_samples = int(chunk_duration * sample_rate)
    interval_samples = chunk_samples  # No overlap for the normal path.

    total_chunks = max(1, int(np.ceil(total_frames / interval_samples)))
    duration = total_frames / sample_rate

    pos = min(max(0.0, float(start_position)), max(0.0, duration - SEEK_MIN_CHUNK_REMAINDER))

    # #5446: round(), not int() — the module's #2327 sample-boundary
    # convention, matching the enhanced path's seek trim
    # (stream_enhanced_chunks.py). One rounded index feeds BOTH the chunk index
    # and the trim: computing the chunk from a truncated index while the trim
    # rounded would let the trim spill one sample past start_chunk's
    # interval, sending the first read one sample into the next chunk.
    start_chunk = 0
    first_chunk_trim_samples = 0
    start_sample = round(pos * sample_rate)
    if start_sample > 0:
        start_chunk = min(start_sample // interval_samples, total_chunks - 1)
        first_chunk_trim_samples = start_sample - (start_chunk * interval_samples)

    seek_offset = pos - (start_chunk * chunk_duration)

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
