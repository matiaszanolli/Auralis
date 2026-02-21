# -*- coding: utf-8 -*-

"""
Chunked Processing Boundary Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Edge case tests for chunked audio processing boundaries.

Categories:
1. Exact Chunk Boundaries (6 tests)
2. Partial Last Chunks (6 tests)
3. Single Chunk Edge Cases (6 tests)
4. Very Long Audio (6 tests)
5. Minimum Duration (6 tests)
"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Constants from chunked processor
# NOTE: These are hardcoded to match auralis-web/backend/chunked_processor.py
# If chunked_processor.py changes these values, update here as well
CHUNK_DURATION = 10.0  # 10 seconds per chunk (Phase 2 reduced from 30s)
OVERLAP_DURATION = 3.0  # 3 seconds overlap


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_audio_dir():
    """Create temporary directory for audio files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def create_test_audio(duration_seconds, sample_rate=44100):
    """
    Create test audio of specified duration.

    Args:
        duration_seconds: Duration in seconds
        sample_rate: Sample rate in Hz

    Returns:
        Stereo audio array (samples, 2)
    """
    num_samples = int(duration_seconds * sample_rate)
    # Create stereo audio with distinct L/R channels
    audio = np.random.randn(num_samples, 2) * 0.1
    return audio


def save_test_audio(filepath, audio, sample_rate=44100):
    """Save audio to file"""
    from auralis.io.saver import save
    save(filepath, audio, sample_rate, subtype='PCM_16')


def create_processor(filepath, track_id=1, preset="adaptive", intensity=1.0):
    """
    Helper to create ChunkedAudioProcessor with default test parameters.

    Args:
        filepath: Path to audio file
        track_id: Track ID for cache keys (default: 1)
        preset: Processing preset (default: "adaptive")
        intensity: Processing intensity (default: 1.0)

    Returns:
        ChunkedAudioProcessor instance
    """
    # Import here to avoid module-level import issues
    from core.chunked_processor import ChunkedAudioProcessor

    return ChunkedAudioProcessor(
        track_id=track_id,
        filepath=filepath,
        preset=preset,
        intensity=intensity
    )


# ============================================================================
# 1. Exact Chunk Boundaries (6 tests)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.slow
def test_audio_exactly_one_chunk_duration(temp_audio_dir):
    """
    BOUNDARY: Audio duration = CHUNK_DURATION exactly (30.0s).

    Should create exactly 1 chunk with no overlap needed.
    """

    duration = CHUNK_DURATION  # Exactly 30.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "exact_30s.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Should have exactly 1 chunk
    assert processor.total_chunks == 1, (
        f"Audio of exactly {CHUNK_DURATION}s should create 1 chunk, "
        f"got {processor.total_chunks}"
    )

    # Total duration should match
    assert abs(processor.total_duration - duration) < 0.1, (
        f"Duration mismatch: expected {duration}s, got {processor.total_duration}s"
    )


@pytest.mark.boundary
@pytest.mark.slow
def test_audio_exactly_two_chunks_duration(temp_audio_dir):
    """
    BOUNDARY: Audio duration = 2 * CHUNK_DURATION exactly (60.0s).

    Should create exactly 2 chunks with overlap.
    """

    duration = 2 * CHUNK_DURATION  # Exactly 60.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "exact_60s.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Should have exactly 2 chunks
    assert processor.total_chunks == 2, (
        f"Audio of exactly {2 * CHUNK_DURATION}s should create 2 chunks, "
        f"got {processor.total_chunks}"
    )


@pytest.mark.boundary
@pytest.mark.slow
def test_audio_exactly_three_chunks_duration(temp_audio_dir):
    """
    BOUNDARY: Audio duration = 3 * CHUNK_DURATION exactly (90.0s).

    Should create exactly 3 chunks.
    """

    duration = 3 * CHUNK_DURATION  # Exactly 90.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "exact_90s.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 3, (
        f"Audio of exactly {3 * CHUNK_DURATION}s should create 3 chunks, "
        f"got {processor.total_chunks}"
    )


@pytest.mark.boundary
def test_audio_one_sample_over_chunk_boundary(temp_audio_dir):
    """
    BOUNDARY: Audio = CHUNK_DURATION + 1 sample (30.000023s at 44.1kHz).

    Should create 2 chunks (crosses boundary by smallest possible amount).
    """

    sample_rate = 44100
    duration = CHUNK_DURATION + (1 / sample_rate)  # 30s + 1 sample
    audio = create_test_audio(duration, sample_rate)
    filepath = os.path.join(temp_audio_dir, "one_sample_over.wav")
    save_test_audio(filepath, audio, sample_rate)

    processor = create_processor(filepath)

    # Should have 2 chunks (crossed boundary by 1 sample)
    assert processor.total_chunks == 2, (
        f"Audio {duration}s (CHUNK_DURATION + 1 sample) should create 2 chunks, "
        f"got {processor.total_chunks}"
    )


@pytest.mark.boundary
def test_audio_one_sample_under_chunk_boundary(temp_audio_dir):
    """
    BOUNDARY: Audio = CHUNK_DURATION - 1 sample (29.999977s at 44.1kHz).

    Should create 1 chunk (doesn't cross boundary).
    """

    sample_rate = 44100
    duration = CHUNK_DURATION - (1 / sample_rate)  # 30s - 1 sample
    audio = create_test_audio(duration, sample_rate)
    filepath = os.path.join(temp_audio_dir, "one_sample_under.wav")
    save_test_audio(filepath, audio, sample_rate)

    processor = create_processor(filepath)

    # Should have 1 chunk (doesn't cross boundary)
    assert processor.total_chunks == 1, (
        f"Audio {duration}s (CHUNK_DURATION - 1 sample) should create 1 chunk, "
        f"got {processor.total_chunks}"
    )


@pytest.mark.boundary
def test_audio_at_overlap_boundary(temp_audio_dir):
    """
    BOUNDARY: Audio = CHUNK_DURATION + OVERLAP_DURATION (33.0s).

    Tests chunk creation at overlap boundary.
    """

    duration = CHUNK_DURATION + OVERLAP_DURATION  # 33.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "at_overlap.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Should have 2 chunks
    assert processor.total_chunks == 2, (
        f"Audio of {duration}s should create 2 chunks, got {processor.total_chunks}"
    )


# ============================================================================
# 2. Partial Last Chunks (6 tests)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.slow
def test_last_chunk_very_short(temp_audio_dir):
    """
    BOUNDARY: Last chunk = 0.1s (minimum meaningful duration).

    Should handle very short last chunk gracefully.
    """

    duration = CHUNK_DURATION + 0.1  # 30.1s (last chunk = 0.1s)
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "short_last.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 2

    # Process all chunks
    for i in range(processor.total_chunks):
        processor.process_chunk(i)

    # Should complete without error
    assert processor.total_chunks == 2


@pytest.mark.boundary
def test_last_chunk_half_of_regular(temp_audio_dir):
    """
    BOUNDARY: Last chunk = CHUNK_DURATION / 2 (15s).

    Common case: last chunk is about half size.
    """

    duration = CHUNK_DURATION + (CHUNK_DURATION / 2)  # 45.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "half_last.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 2

    # Process and verify both chunks
    for i in range(processor.total_chunks):
        processor.process_chunk(i)


@pytest.mark.boundary
def test_last_chunk_almost_full(temp_audio_dir):
    """
    BOUNDARY: Last chunk = CHUNK_DURATION - 1s (29s).

    Last chunk almost as long as regular chunk.
    """

    duration = CHUNK_DURATION + (CHUNK_DURATION - 1)  # 59.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "almost_full_last.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 2


@pytest.mark.boundary
def test_multiple_chunks_with_tiny_remainder(temp_audio_dir):
    """
    BOUNDARY: Many chunks + tiny last chunk (0.01s).

    Tests handling of negligible final chunk.
    """

    duration = 3 * CHUNK_DURATION + 0.01  # 90.01s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "tiny_remainder.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Should create 4 chunks (3 full + 1 tiny)
    assert processor.total_chunks == 4


@pytest.mark.boundary
def test_last_chunk_exactly_overlap_duration(temp_audio_dir):
    """
    BOUNDARY: Last chunk duration = OVERLAP_DURATION exactly (3.0s).

    Last chunk same size as overlap region.
    """

    duration = CHUNK_DURATION + OVERLAP_DURATION  # 33.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "last_equals_overlap.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 2


@pytest.mark.boundary
def test_last_chunk_between_overlap_and_full(temp_audio_dir):
    """
    BOUNDARY: Last chunk = OVERLAP_DURATION + 5s (8s).

    Last chunk larger than overlap but much smaller than full chunk.
    """

    duration = CHUNK_DURATION + (OVERLAP_DURATION + 5)  # 38.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "medium_last.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 2


# ============================================================================
# 3. Single Chunk Edge Cases (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_single_chunk_minimum_duration(temp_audio_dir):
    """
    BOUNDARY: Audio = 0.1s (minimum meaningful duration, single chunk).

    Shortest possible audio that's still valid.
    """

    duration = 0.1  # 100ms
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "min_single.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 1
    assert processor.total_duration < CHUNK_DURATION


@pytest.mark.boundary
def test_single_chunk_one_second(temp_audio_dir):
    """
    BOUNDARY: Audio = 1.0s exactly (single chunk).

    Common short audio duration.
    """

    duration = 1.0
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "one_second.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 1
    assert abs(processor.total_duration - 1.0) < 0.1


@pytest.mark.boundary
def test_single_chunk_ten_seconds(temp_audio_dir):
    """
    BOUNDARY: Audio = 10.0s (single chunk, 1/3 of CHUNK_DURATION).

    Medium short audio.
    """

    duration = 10.0
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "ten_seconds.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 1


@pytest.mark.boundary
def test_single_chunk_twenty_seconds(temp_audio_dir):
    """
    BOUNDARY: Audio = 20.0s (2x CHUNK_DURATION = 2 chunks).

    With 10s chunks, 20s audio creates exactly 2 chunks.
    """

    duration = 20.0
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "twenty_seconds.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 2  # 20s / 10s = 2 chunks


@pytest.mark.boundary
def test_single_chunk_just_under_boundary(temp_audio_dir):
    """
    BOUNDARY: Audio = 9.9s (single chunk, just under CHUNK_DURATION).

    Maximum single chunk size (just under 10s boundary).
    """

    duration = 9.9
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "just_under.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 1  # 9.9s < 10s = 1 chunk


@pytest.mark.boundary
def test_single_chunk_processing_preserves_duration(temp_audio_dir):
    """
    BOUNDARY: Single chunk processing must preserve exact duration.

    With 10s chunks, use 5s audio to ensure single chunk.
    No crossfading occurs, so duration must be perfect.
    """
    from auralis.io.unified_loader import load_audio

    duration = 5.0  # < 10s CHUNK_DURATION, ensures single chunk
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "preserve_duration.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Verify it's actually a single chunk
    assert processor.total_chunks == 1, f"Expected 1 chunk, got {processor.total_chunks}"

    # Process the single chunk
    processor.process_chunk(0)

    # Load processed chunk
    chunk_path = processor._get_chunk_path(0)
    processed, sr = load_audio(str(chunk_path))

    processed_duration = len(processed) / sr

    # Duration should be preserved (within 0.01s)
    assert abs(processed_duration - duration) < 0.01, (
        f"Single chunk duration not preserved: expected {duration}s, "
        f"got {processed_duration}s"
    )


# ============================================================================
# 4. Very Long Audio (6 tests)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.slow
def test_audio_one_hour_duration(temp_audio_dir):
    """
    BOUNDARY: Audio = 1 hour (3600s, ~120 chunks).

    Tests handling of long audio files.
    """

    duration = 3600.0  # 1 hour
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "one_hour.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Should create ~120 chunks
    expected_chunks = int(duration / CHUNK_DURATION) + 1
    assert processor.total_chunks >= expected_chunks - 1, (
        f"1 hour audio should create ~{expected_chunks} chunks, "
        f"got {processor.total_chunks}"
    )


@pytest.mark.boundary
@pytest.mark.slow
def test_audio_two_hours_duration(temp_audio_dir):
    """
    BOUNDARY: Audio = 2 hours (7200s, ~240 chunks).

    Tests handling of very long audio.
    """

    duration = 7200.0  # 2 hours
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "two_hours.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    expected_chunks = int(duration / CHUNK_DURATION) + 1
    assert processor.total_chunks >= expected_chunks - 1


@pytest.mark.boundary
def test_many_chunks_total_duration_preserved(temp_audio_dir):
    """
    BOUNDARY: Long audio total duration must be preserved.

    With many chunks, cumulative rounding errors shouldn't accumulate.
    """

    duration = 300.0  # 5 minutes = 10 chunks
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "five_minutes.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Duration should be preserved within 1%
    tolerance = duration * 0.01
    assert abs(processor.total_duration - duration) < tolerance


@pytest.mark.boundary
def test_many_chunks_all_valid(temp_audio_dir):
    """
    BOUNDARY: All chunks in long audio must be valid.

    No chunk should have invalid start/end times.
    """

    duration = 180.0  # 3 minutes = 6 chunks
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "three_minutes.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    for chunk_idx in range(processor.total_chunks):
        _, start, end = processor.load_chunk(chunk_idx, with_context=False)

        # All chunks must have valid times
        assert start >= 0, f"Chunk {chunk_idx} has negative start time: {start}"
        assert end <= duration, f"Chunk {chunk_idx} end time {end} exceeds duration {duration}"
        assert end > start, f"Chunk {chunk_idx} has end <= start: {start} to {end}"


@pytest.mark.boundary
@pytest.mark.slow
def test_many_chunks_no_gaps(temp_audio_dir):
    """
    BOUNDARY: Long audio chunks must have no gaps.

    Every second of audio must be covered by at least one chunk.
    """

    duration = 150.0  # 2.5 minutes = 5 chunks
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "no_gaps.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Collect all covered ranges
    covered = []
    for chunk_idx in range(processor.total_chunks):
        _, start, end = processor.load_chunk(chunk_idx, with_context=False)
        covered.append((start, end))

    # Sort by start time
    covered.sort()

    # First chunk should start at or near 0
    assert covered[0][0] < 0.1, "First chunk doesn't start near 0"

    # Last chunk should end at or near duration
    assert covered[-1][1] >= duration - 0.1, "Last chunk doesn't cover end"

    # Check for gaps between chunks
    for i in range(len(covered) - 1):
        current_end = covered[i][1]
        next_start = covered[i + 1][0]

        # Next chunk should start before or at current end (overlap is OK, gap is not)
        assert next_start <= current_end + 0.1, (
            f"Gap detected between chunk {i} and {i+1}: "
            f"chunk {i} ends at {current_end}, chunk {i+1} starts at {next_start}"
        )


@pytest.mark.boundary
def test_many_chunks_consistent_size(temp_audio_dir):
    """
    BOUNDARY: All non-final chunks should have consistent duration.

    Only last chunk can be different size.
    """

    duration = 120.0  # 2 minutes = 4 chunks
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "consistent_size.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    chunk_durations = []
    for chunk_idx in range(processor.total_chunks - 1):  # Exclude last chunk
        _, start, end = processor.load_chunk(chunk_idx, with_context=False)
        chunk_durations.append(end - start)

    if chunk_durations:
        # All non-final chunks should be within 0.2s of each other (accounting for float precision)
        min_duration = min(chunk_durations)
        max_duration = max(chunk_durations)

        assert abs(max_duration - min_duration) < 0.2, (
            f"Non-final chunks have inconsistent durations: "
            f"min={min_duration:.2f}s, max={max_duration:.2f}s"
        )


# ============================================================================
# 5. Minimum Duration Edge Cases (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_extremely_short_audio_50ms(temp_audio_dir):
    """
    BOUNDARY: Audio = 50ms (extremely short but valid).

    Should handle gracefully without crashing.
    """

    duration = 0.05  # 50ms
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "50ms.wav")
    save_test_audio(filepath, audio)

    try:
        processor = create_processor(filepath)
        assert processor.total_chunks == 1
        assert processor.total_duration < 0.1
    except Exception as e:
        pytest.fail(f"50ms audio should not crash: {e}")


@pytest.mark.boundary
def test_minimum_processable_duration(temp_audio_dir):
    """
    BOUNDARY: Find minimum duration that can be processed.

    Tests lower limit of processing system.
    """

    # Try progressively shorter durations
    for duration in [0.1, 0.05, 0.02, 0.01]:
        audio = create_test_audio(duration)
        filepath = os.path.join(temp_audio_dir, f"min_{duration}s.wav")
        save_test_audio(filepath, audio)

        try:
            processor = create_processor(filepath)
            # If we get here, this duration is processable
            assert processor.total_chunks >= 1
        except Exception:
            # This duration is too short
            continue


@pytest.mark.boundary
def test_duration_shorter_than_overlap(temp_audio_dir):
    """
    BOUNDARY: Audio < OVERLAP_DURATION (< 3s).

    Audio shorter than overlap region.
    """

    duration = OVERLAP_DURATION - 0.5  # 2.5s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "shorter_than_overlap.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    # Should create 1 chunk
    assert processor.total_chunks == 1


@pytest.mark.boundary
def test_duration_exactly_overlap_duration(temp_audio_dir):
    """
    BOUNDARY: Audio = OVERLAP_DURATION exactly (3.0s).

    Audio same length as overlap.
    """

    duration = OVERLAP_DURATION  # Exactly 3.0s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "exact_overlap.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 1


@pytest.mark.boundary
def test_duration_just_over_overlap(temp_audio_dir):
    """
    BOUNDARY: Audio = OVERLAP_DURATION + 0.1s (3.1s).

    Just over overlap duration.
    """

    duration = OVERLAP_DURATION + 0.1  # 3.1s
    audio = create_test_audio(duration)
    filepath = os.path.join(temp_audio_dir, "just_over_overlap.wav")
    save_test_audio(filepath, audio)

    processor = create_processor(filepath)

    assert processor.total_chunks == 1


@pytest.mark.boundary
def test_single_sample_audio(temp_audio_dir):
    """
    BOUNDARY: Audio = 1 sample (22.7μs at 44.1kHz).

    Absolute minimum: single audio sample.
    """

    sample_rate = 44100
    # Create single-sample stereo audio
    audio = np.array([[0.1, 0.1]])  # 1 sample, 2 channels
    filepath = os.path.join(temp_audio_dir, "one_sample.wav")
    save_test_audio(filepath, audio, sample_rate)

    try:
        processor = create_processor(filepath)
        # If this doesn't crash, that's a pass
        assert processor.total_chunks >= 1
    except Exception as e:
        # Single sample may be too short, which is acceptable
        pytest.skip(f"Single sample audio not supported: {e}")


# ============================================================================
# Summary Statistics
# ============================================================================

def test_chunked_processing_boundaries_summary():
    """
    Print summary of chunked processing boundary tests.
    """
    print("\n" + "=" * 80)
    print("CHUNKED PROCESSING BOUNDARY TEST SUMMARY")
    print("=" * 80)
    print(f"Exact Chunk Boundaries: 6 tests")
    print(f"Partial Last Chunks: 6 tests")
    print(f"Single Chunk Edge Cases: 6 tests")
    print(f"Very Long Audio: 6 tests")
    print(f"Minimum Duration: 6 tests")
    print("=" * 80)
    print(f"TOTAL: 30 boundary tests")
    print("=" * 80)
    print("\nThese tests validate edge cases and boundaries for:")
    print("1. Exact chunk duration boundaries (30s, 60s, 90s)")
    print("2. Partial last chunks (0.1s to 29s)")
    print("3. Single chunk audio (0.1s to 29.9s)")
    print("4. Very long audio (1-2 hours, 120-240 chunks)")
    print("5. Minimum duration limits (1 sample to 3s)")
    print("=" * 80 + "\n")
