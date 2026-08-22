"""
Chunk Operations Utility
~~~~~~~~~~~~~~~~~~~~~~~~~

Unified chunk extraction and boundary calculation operations.

Consolidates duplicate logic from:
- chunked_processor.load_chunk()
- chunked_processor._extract_chunk_segment()

This utility eliminates ~300 lines of duplicate chunk handling code.

Crossfade math lives solely in ``chunk_crossfade.apply_crossfade_between_chunks``
(#4245) — an `apply_crossfade` staticmethod used to be duplicated here too, but
it was dead code (no caller anywhere in the tree) that had drifted into its own
copy of the same sin²/cos² math; removed rather than reconciled, since nothing
depended on it (#4245 CONSISTENCY check).

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging

import numpy as np

from core.chunk_boundaries import (
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    CONTEXT_DURATION,
    OVERLAP_DURATION,
    ChunkBoundaryManager,
)

logger = logging.getLogger(__name__)


class ChunkOperations:
    """
    Unified chunk operations utility.

    Provides static methods for:
    - Loading audio chunks from files
    - Extracting segments with overlap handling

    Crossfade math lives in chunk_crossfade.apply_crossfade_between_chunks
    (#4245), not here.

    This class follows the Utilities Pattern (Phase 7.2) - all methods are
    static, no instance state.
    """

    @staticmethod
    def load_chunk_from_file(
        filepath: str,
        chunk_index: int,
        sample_rate: int,
        chunk_duration: float = CHUNK_DURATION,
        chunk_interval: float = CHUNK_INTERVAL,
        overlap_duration: float = OVERLAP_DURATION,
        with_context: bool = True,
        total_duration: float | None = None
    ) -> tuple[np.ndarray, float, float]:
        """
        Load a single chunk from audio file with optional context.

        Consolidates logic from:
        - chunked_processor.load_chunk()

        Chunks after the first include OVERLAP_DURATION at the start for crossfading.
        This ensures no audio is lost during crossfade concatenation.

        Args:
            filepath: Path to audio file
            chunk_index: Index of chunk to load (0-based)
            sample_rate: Sample rate of audio
            chunk_duration: Duration of each chunk in seconds (actual chunk length).
                Only used when total_duration is None — see below.
            chunk_interval: Interval between chunk starts (for overlap model).
                Only used when total_duration is None — see below.
            overlap_duration: Overlap duration for crossfading. Unused directly;
                kept for call-site symmetry with extract_chunk_segment().
            with_context: Include context before/after for better processing
            total_duration: Total duration of audio, if known. When provided,
                boundaries are derived from ChunkBoundaryManager — the same
                authority trim_context() uses — instead of being re-derived
                here, so the load and trim halves of the pipeline cannot
                structurally desync (the #3807 failure mode; fixes #5055).
                ChunkBoundaryManager always uses chunk_boundaries.py's
                module-level CHUNK_DURATION/CHUNK_INTERVAL/CONTEXT_DURATION,
                so chunk_duration/chunk_interval above are ignored in this
                case — true of every current caller, which already pass
                those same constants through. When None (duration not yet
                known), falls back to the original unbounded derivation
                using chunk_duration/chunk_interval directly.

        Returns:
            Tuple of (audio_chunk, chunk_start_time, chunk_end_time)
        """
        if total_duration is not None:
            boundary_manager = ChunkBoundaryManager(
                total_duration=total_duration, sample_rate=sample_rate
            )
            load_start, load_end, chunk_start, chunk_end = boundary_manager.get_chunk_boundaries(
                chunk_index, with_context=with_context
            )
        else:
            # No known total_duration (e.g. probing before metadata is
            # loaded) — ChunkBoundaryManager requires one, so fall back to
            # the original, unbounded derivation. chunk_end/load_end are NOT
            # capped here; test_fallback_start_beyond_eof_returns_float32
            # deliberately exercises this uncapped path.
            if chunk_index == 0:
                chunk_start = 0.0
                chunk_end = chunk_start + chunk_duration
            else:
                chunk_start = chunk_index * chunk_interval
                chunk_end = chunk_start + chunk_duration
            context_duration = CONTEXT_DURATION if with_context else 0.0
            load_start = max(0.0, chunk_start - context_duration)
            load_end = chunk_end + context_duration

        # An out-of-range chunk_index (beyond total_duration) collapses this
        # window to empty or inverted once chunk_end is capped above. Bail out
        # here instead of letting the soundfile read fail and fall through to
        # the full-file-decode fallback below — that fallback is a small-
        # request -> large-work amplifier for an out-of-bounds index (#4342).
        if load_start >= load_end:
            logger.warning(
                f"Chunk {chunk_index} window is empty/inverted "
                f"(start={load_start:.1f}s, end={load_end:.1f}s) — out of range, returning silence"
            )
            silence = np.zeros((int(0.1 * sample_rate), 2), dtype=np.float32)
            return silence, chunk_start, chunk_end

        # Load audio segment
        try:
            import soundfile as sf

            start_frame = int(round(load_start * sample_rate))
            frames_to_read = int(round((load_end - load_start) * sample_rate))

            with sf.SoundFile(filepath) as f:
                f.seek(start_frame)
                # dtype defaults to float64 with no dtype= arg (#4794) — every
                # other read/fallback in this pipeline (load_audio below,
                # stream_normal.py, the silence fallbacks) is float32, so an
                # unspecified dtype here silently double-precisions the DSP
                # working set on the primary (non-fallback) load path.
                # always_2d=True replaces the manual ndim fix-up below.
                audio = f.read(frames_to_read, dtype='float32', always_2d=True)

        except Exception as e:
            logger.warning(f"Soundfile loading failed, using fallback: {e}")
            # Fallback: load entire audio and slice
            from auralis.io.unified_loader import load_audio

            full_audio, _ = load_audio(filepath, target_sample_rate=sample_rate)

            start_sample = int(round(load_start * sample_rate))
            end_sample = int(round(load_end * sample_rate))

            # Ensure we don't try to read beyond the file
            end_sample = min(end_sample, len(full_audio))

            if start_sample >= len(full_audio):
                logger.error(
                    f"Chunk {chunk_index} start ({start_sample}) beyond file length ({len(full_audio)})"
                )
                num_ch = full_audio.shape[1] if full_audio.ndim > 1 else 1
                audio = np.zeros((1, num_ch), dtype=np.float32)
            else:
                audio = full_audio[start_sample:end_sample]

        # Validate that we loaded something
        if len(audio) == 0:
            logger.error(
                f"Chunk {chunk_index} resulted in empty audio "
                f"(start={load_start:.1f}s, end={load_end:.1f}s)"
            )
            # Return minimal silence instead of empty array
            num_channels = audio.shape[1] if audio.ndim > 1 else 1
            audio = np.zeros((int(0.1 * sample_rate), num_channels), dtype=np.float32)
            logger.warning(f"Returning 100ms of silence for chunk {chunk_index}")

        return audio, chunk_start, chunk_end

    @staticmethod
    def extract_chunk_segment(
        processed_chunk: np.ndarray,
        chunk_index: int,
        sample_rate: int,
        chunk_duration: float = CHUNK_DURATION,
        chunk_interval: float = CHUNK_INTERVAL,
        overlap_duration: float = OVERLAP_DURATION,
        total_chunks: int | None = None,
        total_duration: float | None = None
    ) -> np.ndarray:
        """
        Extract the correct segment from a context-trimmed chunk based on its position.

        After ``ChunkBoundaryManager.trim_context()``, the buffer for chunk N
        (N > 0) spans source time ``[N*interval, N*interval + chunk_duration]``.
        The preceding chunk already emitted up to ``(N-1)*interval + chunk_duration``
        = ``N*interval + overlap_duration``, so the new content starts
        ``overlap_duration`` into the trimmed buffer:

        - Chunk 0: ``[:chunk_duration]`` — first chunk has no predecessor overlap
        - Middle:  ``[overlap:overlap+interval]`` — skip already-emitted overlap
        - Last:    ``[overlap:overlap+remaining]`` — remaining new content only

        Args:
            processed_chunk: Processed chunk (context already trimmed)
            chunk_index: Index of this chunk
            sample_rate: Sample rate
            chunk_duration: Duration of each chunk in seconds
            chunk_interval: Interval between chunk starts
            overlap_duration: Overlap between consecutive chunks (= chunk_duration - chunk_interval)
            total_chunks: Total number of chunks (for last chunk detection)
            total_duration: Total duration (for last chunk calculation)

        Returns:
            Extracted segment ready for encoding
        """
        if chunk_index < 0:
            raise ValueError(f"chunk_index {chunk_index} out of range")
        if total_chunks is not None and chunk_index >= total_chunks:
            raise ValueError(
                f"chunk_index {chunk_index} out of range "
                f"(valid: 0..{total_chunks - 1})"
            )

        is_last = (total_chunks is not None) and (chunk_index == total_chunks - 1)
        overlap_samples = int(round(overlap_duration * sample_rate))

        if chunk_index == 0:
            # First chunk: extract CHUNK_DURATION (or total_duration if shorter, e.g. single-chunk file)
            max_duration = chunk_duration
            if is_last and total_duration is not None:
                max_duration = min(chunk_duration, total_duration)
            expected_samples = int(round(max_duration * sample_rate))
            extracted = processed_chunk[:expected_samples]
            logger.debug(
                f"✅ Chunk 0: extracted [0:{expected_samples}] samples "
                f"({expected_samples/sample_rate:.2f}s)"
            )

        elif is_last:
            # Last chunk: skip overlap already emitted by the previous chunk,
            # then extract only the truly new remaining content. This offset
            # assumes trim_context() performed the full CONTEXT_DURATION trim —
            # true unconditionally as of #3807 (the old max_trim_fraction cap
            # used to under-trim short tracks' final chunk here, desyncing this
            # offset and dropping the track's final seconds).
            assert total_duration is not None
            chunk_start_time = chunk_index * chunk_interval
            remaining_duration = max(0, total_duration - (chunk_start_time + overlap_duration))
            expected_samples = int(round(remaining_duration * sample_rate))

            extracted = processed_chunk[overlap_samples:overlap_samples + expected_samples]
            logger.debug(
                f"✅ Chunk {chunk_index} (last): starts {chunk_start_time + overlap_duration:.1f}s, "
                f"remaining {remaining_duration:.1f}s, {expected_samples} samples"
            )

        else:
            # Regular chunk: skip overlap already emitted by the previous chunk,
            # then extract exactly CHUNK_INTERVAL of new content.
            expected_samples = int(round(chunk_interval * sample_rate))
            extracted = processed_chunk[overlap_samples:overlap_samples + expected_samples]
            logger.debug(
                f"✅ Chunk {chunk_index}: extracted {expected_samples} samples "
                f"({expected_samples/sample_rate:.2f}s) after {overlap_duration:.1f}s overlap skip"
            )

        # Verify and pad/trim if needed (edge case handling)
        current_samples = len(extracted)

        # Normalize mono to 2-D (N,1) up front so every validation branch below
        # (pad / trim / pass-through) returns the same rank (#4132) — previously
        # only the pad path promoted mono to 2-D, the others stayed 1-D.
        if extracted.ndim not in (1, 2):
            raise ValueError(
                f"Chunk {chunk_index}: expected 1-D or 2-D audio array, got shape {extracted.shape}"
            )
        if extracted.ndim == 1:
            extracted = extracted[:, np.newaxis]

        if chunk_index == 0:
            max_dur = chunk_duration
            if is_last and total_duration is not None:
                max_dur = min(chunk_duration, total_duration)
            expected_for_validation = int(round(max_dur * sample_rate))
        elif is_last:
            assert total_duration is not None
            chunk_start_time = chunk_index * chunk_interval
            remaining_duration = max(0, total_duration - (chunk_start_time + overlap_duration))
            expected_for_validation = int(round(remaining_duration * sample_rate))
        else:
            expected_for_validation = int(round(chunk_interval * sample_rate))

        if current_samples < expected_for_validation:
            # Pad with silence if too short. extracted is guaranteed 2-D here.
            padding_needed = expected_for_validation - current_samples
            num_channels = extracted.shape[1]
            # Match the buffer's dtype instead of hardcoding float32 (#4134,
            # same dtype-hygiene fix as #4125) so padding never forces a cast.
            padding = np.zeros((padding_needed, num_channels), dtype=extracted.dtype)
            extracted = np.vstack([extracted, padding])
            logger.warning(
                f"⚠️ Chunk {chunk_index} was {padding_needed} samples short, padded with silence"
            )

        elif current_samples > expected_for_validation:
            # Trim if too long
            extracted = extracted[:expected_for_validation]
            logger.warning(
                f"⚠️ Chunk {chunk_index} was {current_samples - expected_for_validation} "
                f"samples too long, trimmed"
            )

        return extracted
