"""
Chunk Operations Utility
~~~~~~~~~~~~~~~~~~~~~~~~~

Unified chunk extraction, boundary calculation, and crossfading operations.

Consolidates duplicate logic from:
- chunked_processor.load_chunk()
- chunked_processor._extract_chunk_segment()
- chunked_processor.apply_crossfade_between_chunks()
- webm_streaming._get_original_wav_chunk()

This utility eliminates ~300 lines of duplicate chunk handling code.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class ChunkOperations:
    """
    Unified chunk operations utility.

    Provides static methods for:
    - Loading audio chunks from files
    - Extracting segments with overlap handling
    - Applying crossfades between chunks
    - Calculating chunk boundaries

    This class follows the Utilities Pattern (Phase 7.2) - all methods are
    static, no instance state.
    """

    @staticmethod
    def load_chunk_from_file(
        filepath: str,
        chunk_index: int,
        sample_rate: int,
        chunk_duration: int = 15,
        chunk_interval: int = 10,
        overlap_duration: int = 5,
        with_context: bool = True,
        total_duration: float | None = None
    ) -> tuple[np.ndarray, float, float]:
        """
        Load a single chunk from audio file with optional context.

        Consolidates logic from:
        - chunked_processor.load_chunk()
        - webm_streaming._get_original_wav_chunk()

        Chunks after the first include OVERLAP_DURATION at the start for crossfading.
        This ensures no audio is lost during crossfade concatenation.

        Args:
            filepath: Path to audio file
            chunk_index: Index of chunk to load (0-based)
            sample_rate: Sample rate of audio
            chunk_duration: Duration of each chunk in seconds (actual chunk length)
            chunk_interval: Interval between chunk starts (for overlap model)
            overlap_duration: Overlap duration for crossfading
            with_context: Include context before/after for better processing
            total_duration: Total duration of audio (optional, for validation)

        Returns:
            Tuple of (audio_chunk, chunk_start_time, chunk_end_time)
        """
        # Calculate chunk boundaries
        if chunk_index == 0:
            # First chunk: starts at 0
            chunk_start = 0.0
            chunk_end = chunk_start + chunk_duration
        else:
            # Subsequent chunks: use interval for start position
            chunk_start = chunk_index * chunk_interval
            chunk_end = chunk_start + chunk_duration

        # Cap end time at total_duration if provided (last chunk shouldn't exceed file length)
        if total_duration is not None:
            chunk_end = min(chunk_end, total_duration)

        # Add context if requested
        context_duration = 5.0 if with_context else 0.0
        load_start = max(0.0, chunk_start - context_duration)
        load_end = chunk_end + context_duration

        # Load audio segment
        try:
            import soundfile as sf

            start_frame = int(round(load_start * sample_rate))
            frames_to_read = int(round((load_end - load_start) * sample_rate))

            with sf.SoundFile(filepath) as f:
                f.seek(start_frame)
                audio = f.read(frames_to_read)

                # Ensure 2D array (samples, channels)
                if audio.ndim == 1:
                    audio = audio[:, np.newaxis]

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
                # Return silence instead of crashing
                audio = np.zeros((1, full_audio.shape[1] if full_audio.ndim > 1 else 1))
            else:
                audio = full_audio[start_sample:end_sample]

        # Validate that we loaded something
        if len(audio) == 0:
            logger.error(
                f"Chunk {chunk_index} resulted in empty audio "
                f"(start={load_start:.1f}s, end={load_end:.1f}s)"
            )
            # Return minimal silence instead of empty array
            num_channels = 2  # Default to stereo
            audio = np.zeros((int(0.1 * sample_rate), num_channels))
            logger.warning(f"Returning 100ms of silence for chunk {chunk_index}")

        return audio, chunk_start, chunk_end

    @staticmethod
    def extract_chunk_segment(
        processed_chunk: np.ndarray,
        chunk_index: int,
        sample_rate: int,
        chunk_duration: int = 15,
        chunk_interval: int = 10,
        overlap_duration: int = 5,
        total_chunks: int | None = None,
        total_duration: float | None = None
    ) -> np.ndarray:
        """
        Extract the correct segment from a processed chunk based on its position.

        Consolidates logic from chunked_processor._extract_chunk_segment().

        Handles first chunk, last chunk, and middle chunks differently to ensure:
        - No duplicate audio at boundaries
        - Proper handling of overlap regions
        - Correct duration for the final segment

        Args:
            processed_chunk: Full processed chunk (may include overlap/context)
            chunk_index: Index of this chunk
            sample_rate: Sample rate
            chunk_duration: Duration of each chunk in seconds
            chunk_interval: Interval between chunk starts
            overlap_duration: Overlap duration for crossfading
            total_chunks: Total number of chunks (for last chunk detection)
            total_duration: Total duration (for last chunk calculation)

        Returns:
            Extracted segment ready for encoding
        """
        is_last = (total_chunks is not None) and (chunk_index == total_chunks - 1)
        overlap_samples = int(round(overlap_duration * sample_rate))

        if chunk_index == 0:
            # First chunk: extract exactly CHUNK_DURATION seconds (or full duration if shorter)
            expected_samples = int(round(chunk_duration * sample_rate))
            extracted = processed_chunk[:expected_samples]
            logger.debug(
                f"✅ Chunk 0: extracted [0:{expected_samples}] samples "
                f"({expected_samples/sample_rate:.2f}s)"
            )

        elif is_last:
            # Last chunk: skip the overlap, extract remaining duration
            assert total_duration is not None
            chunk_start_time = chunk_index * chunk_interval
            remaining_duration = max(0, total_duration - chunk_start_time)
            expected_samples = int(round(remaining_duration * sample_rate))

            # Skip the overlap region to avoid duplicate audio
            extracted = processed_chunk[overlap_samples : overlap_samples + expected_samples]
            logger.debug(
                f"✅ Chunk {chunk_index} (last): starts {chunk_start_time:.1f}s, "
                f"remaining {remaining_duration:.1f}s, {expected_samples} samples"
            )

        else:
            # Regular chunk: skip the overlap, extract exactly CHUNK_DURATION seconds
            expected_samples = int(round(chunk_duration * sample_rate))
            # Skip the overlap region to avoid duplicate audio
            extracted = processed_chunk[overlap_samples : overlap_samples + expected_samples]
            logger.debug(
                f"✅ Chunk {chunk_index}: skipped {overlap_samples} overlap, "
                f"extracted {expected_samples} samples ({expected_samples/sample_rate:.2f}s)"
            )

        # Verify and pad/trim if needed (edge case handling)
        current_samples = len(extracted)

        if is_last:
            assert total_duration is not None
            chunk_start_time = chunk_index * chunk_interval
            remaining_duration = max(0, total_duration - chunk_start_time)
            expected_for_validation = int(round(remaining_duration * sample_rate))
        else:
            expected_for_validation = int(round(chunk_duration * sample_rate))

        if current_samples < expected_for_validation:
            # Pad with silence if too short
            padding_needed = expected_for_validation - current_samples
            num_channels = extracted.shape[1] if extracted.ndim > 1 else 1
            padding = np.zeros((padding_needed, num_channels), dtype=np.float32)

            if extracted.ndim == 1:
                extracted = extracted[:, np.newaxis]
                padding = padding.reshape(-1, num_channels)

            extracted = (
                np.vstack([extracted, padding])
                if extracted.ndim > 1
                else np.concatenate([extracted, padding])
            )
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

    @staticmethod
    def apply_crossfade(
        chunk1: np.ndarray,
        chunk2: np.ndarray,
        overlap_samples: int
    ) -> np.ndarray:
        """
        Apply crossfade between two audio chunks and return concatenated result.

        Consolidates logic from chunked_processor.apply_crossfade_between_chunks().

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
            result: np.ndarray = np.concatenate([chunk1, chunk2], axis=0)
            return result

        # Get overlap regions
        chunk1_tail = chunk1[-actual_overlap:]
        chunk2_head = chunk2[:actual_overlap]

        # Create equal-power fade curves (sin²/cos²) to avoid ~3 dB energy dip
        # at crossfade midpoint — consistent with chunked_processor.py (#2578).
        t = np.linspace(0.0, np.pi / 2, actual_overlap)
        fade_out = np.cos(t) ** 2
        fade_in = np.sin(t) ** 2

        # Handle stereo
        if chunk1_tail.ndim == 2:
            fade_out = fade_out[:, np.newaxis]
            fade_in = fade_in[:, np.newaxis]

        # Apply fades and mix the overlap region
        crossfade = chunk1_tail * fade_out + chunk2_head * fade_in

        # IMPORTANT: Don't lose audio!
        # Result = full chunk1 (except last overlap) + crossfaded overlap + rest of chunk2
        result = np.concatenate(
            [
                chunk1[:-actual_overlap],  # Chunk1 without the tail that will be mixed
                crossfade,  # The mixed overlap region
                chunk2[actual_overlap:],  # Chunk2 without the head that was mixed
            ],
            axis=0,
        )

        return result

    @staticmethod
    def calculate_total_chunks(
        total_duration: float,
        chunk_interval: int = 10
    ) -> int:
        """
        Calculate total number of chunks for a given duration.

        Args:
            total_duration: Total audio duration in seconds
            chunk_interval: Interval between chunk starts

        Returns:
            Total number of chunks
        """
        import math
        return int(math.ceil(total_duration / chunk_interval))

    @staticmethod
    def get_chunk_time_range(
        chunk_index: int,
        chunk_duration: int = 15,
        chunk_interval: int = 10
    ) -> tuple[float, float]:
        """
        Get time range for a chunk (without context).

        Args:
            chunk_index: Chunk index (0-based)
            chunk_duration: Duration of each chunk
            chunk_interval: Interval between chunk starts

        Returns:
            Tuple of (start_time, end_time) in seconds
        """
        if chunk_index == 0:
            start_time = 0.0
        else:
            start_time = chunk_index * chunk_interval

        end_time = start_time + chunk_duration
        return start_time, end_time
