"""
Boundary Tests for Chunked Audio Processor

Tests edge cases and boundary conditions for chunked audio processing.

Philosophy:
- Test minimum/maximum values
- Test exact boundaries (0s, 10s, 20s chunks)
- Test off-by-one scenarios
- Test empty/single/extreme inputs

These tests complement the invariant tests by focusing on edge cases
where bugs commonly occur.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil
import sys

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from chunked_processor import (
    ChunkedAudioProcessor,
    CHUNK_DURATION,
    OVERLAP_DURATION,
)
from auralis.io.saver import save as save_audio


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_audio_dir():
    """Create a temporary directory for test audio files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def create_test_audio(duration_seconds: float, sample_rate: int = 44100) -> np.ndarray:
    """Create test audio of specified duration."""
    num_samples = int(duration_seconds * sample_rate)
    # Create stereo audio with sine wave
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
    audio_stereo = np.column_stack([audio, audio])  # Stereo
    return audio_stereo


@pytest.fixture
def processor_factory(temp_audio_dir):
    """Factory to create processors with different audio durations."""
    def _create_processor(duration_seconds: float, sample_rate: int = 44100):
        # Create test audio file
        audio = create_test_audio(duration_seconds, sample_rate)
        filepath = temp_audio_dir / f"test_audio_{duration_seconds}s.wav"
        save_audio(str(filepath), audio, sample_rate, subtype='PCM_16')

        # Create processor
        processor = ChunkedAudioProcessor(
            audio_file=str(filepath),
            preset="adaptive",
            sample_rate=sample_rate
        )
        return processor

    return _create_processor


# ============================================================================
# Boundary Tests - Minimum Duration
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_very_short_audio_less_than_one_second(processor_factory):
    """
    BOUNDARY: Audio shorter than 1 second.

    Edge case: Very short audio files (e.g., 0.5s) should still process correctly.
    """
    processor = processor_factory(duration_seconds=0.5)

    assert processor.total_chunks == 1, \
        f"Very short audio should have 1 chunk, got {processor.total_chunks}"

    # Should be able to load the chunk
    chunk, start, end = processor.load_chunk(0, with_context=False)

    assert chunk is not None, "Failed to load chunk from very short audio"
    assert len(chunk) > 0, "Chunk from very short audio is empty"

    # Duration should match original
    expected_duration = 0.5
    actual_duration = len(chunk) / processor.sample_rate
    tolerance = 0.01  # 10ms tolerance

    assert abs(actual_duration - expected_duration) < tolerance, \
        f"Duration mismatch for very short audio: expected {expected_duration}s, got {actual_duration}s"


@pytest.mark.boundary
@pytest.mark.audio
def test_minimum_viable_audio_100ms(processor_factory):
    """
    BOUNDARY: Minimum viable audio duration (100ms).

    Tests the absolute minimum audio that should be processable.
    """
    processor = processor_factory(duration_seconds=0.1)

    assert processor.total_chunks == 1

    chunk, start, end = processor.load_chunk(0, with_context=False)

    assert chunk is not None
    assert len(chunk) > 0
    assert len(chunk) == int(0.1 * processor.sample_rate * 2)  # 2 channels


@pytest.mark.boundary
@pytest.mark.audio
def test_audio_exactly_chunk_duration(processor_factory):
    """
    BOUNDARY: Audio exactly CHUNK_DURATION (10s).

    Edge case: When audio length exactly matches chunk duration.
    """
    processor = processor_factory(duration_seconds=CHUNK_DURATION)

    assert processor.total_chunks == 1, \
        f"Audio of exactly {CHUNK_DURATION}s should have 1 chunk, got {processor.total_chunks}"

    chunk, start, end = processor.load_chunk(0, with_context=False)

    # Should extract exactly the full duration
    expected_samples = int(CHUNK_DURATION * processor.sample_rate * 2)  # Stereo

    assert len(chunk) == expected_samples, \
        f"Chunk sample count mismatch: expected {expected_samples}, got {len(chunk)}"


@pytest.mark.boundary
@pytest.mark.audio
def test_audio_just_over_chunk_duration(processor_factory):
    """
    BOUNDARY: Audio just slightly longer than CHUNK_DURATION (10.1s).

    Edge case: Should create 2 chunks even though we're only 100ms over.
    """
    duration = CHUNK_DURATION + 0.1
    processor = processor_factory(duration_seconds=duration)

    assert processor.total_chunks == 2, \
        f"Audio of {duration}s should have 2 chunks, got {processor.total_chunks}"

    # First chunk should be full CHUNK_DURATION
    chunk1, start1, end1 = processor.load_chunk(0, with_context=False)
    duration1 = len(chunk1) / processor.sample_rate / 2  # Stereo

    assert abs(duration1 - CHUNK_DURATION) < 0.01, \
        f"First chunk should be {CHUNK_DURATION}s, got {duration1}s"

    # Second chunk should be ~0.1s
    chunk2, start2, end2 = processor.load_chunk(1, with_context=False)
    duration2 = len(chunk2) / processor.sample_rate / 2  # Stereo

    assert duration2 < 1.0, \
        f"Second chunk should be very short (~0.1s), got {duration2}s"


# ============================================================================
# Boundary Tests - Chunk Boundaries
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_chunk_boundary_at_exact_10_second_mark(processor_factory):
    """
    BOUNDARY: Chunk boundary falls exactly at 10.0 seconds.

    Tests that chunk boundaries are calculated correctly at exact CHUNK_DURATION intervals.
    """
    processor = processor_factory(duration_seconds=20.0)

    assert processor.total_chunks == 2

    # First chunk: 0.0 - 10.0s
    chunk1, start1, end1 = processor.load_chunk(0, with_context=False)

    assert start1 == 0.0
    assert abs(end1 - 10.0) < 0.001, f"First chunk should end at 10.0s, got {end1}s"

    # Second chunk: 10.0 - 20.0s
    chunk2, start2, end2 = processor.load_chunk(1, with_context=False)

    assert abs(start2 - 10.0) < 0.001, f"Second chunk should start at 10.0s, got {start2}s"
    assert abs(end2 - 20.0) < 0.001, f"Second chunk should end at 20.0s, got {end2}s"


@pytest.mark.boundary
@pytest.mark.audio
def test_chunk_boundary_at_30_seconds(processor_factory):
    """
    BOUNDARY: Chunk boundaries at 10s, 20s, 30s.

    Tests multiple exact chunk boundaries.
    """
    processor = processor_factory(duration_seconds=30.0)

    assert processor.total_chunks == 3

    expected_boundaries = [
        (0.0, 10.0),
        (10.0, 20.0),
        (20.0, 30.0)
    ]

    for chunk_idx, (expected_start, expected_end) in enumerate(expected_boundaries):
        chunk, start, end = processor.load_chunk(chunk_idx, with_context=False)

        assert abs(start - expected_start) < 0.001, \
            f"Chunk {chunk_idx} start: expected {expected_start}s, got {start}s"
        assert abs(end - expected_end) < 0.001, \
            f"Chunk {chunk_idx} end: expected {expected_end}s, got {end}s"


@pytest.mark.boundary
@pytest.mark.audio
def test_last_chunk_exactly_chunk_duration(processor_factory):
    """
    BOUNDARY: Last chunk is exactly CHUNK_DURATION (rare case).

    Tests the case where the last chunk perfectly fills CHUNK_DURATION.
    """
    # Create audio that's exactly 3 * CHUNK_DURATION
    total_duration = 3 * CHUNK_DURATION  # 30s
    processor = processor_factory(duration_seconds=total_duration)

    assert processor.total_chunks == 3

    # Last chunk should be full duration
    last_chunk, start, end = processor.load_chunk(2, with_context=False)
    chunk_duration = len(last_chunk) / processor.sample_rate / 2  # Stereo

    assert abs(chunk_duration - CHUNK_DURATION) < 0.01, \
        f"Last chunk should be {CHUNK_DURATION}s, got {chunk_duration}s"


# ============================================================================
# Boundary Tests - Maximum Duration
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
@pytest.mark.slow
def test_very_long_audio_one_hour(processor_factory):
    """
    BOUNDARY: Very long audio (1 hour = 3600s).

    Tests that the processor can handle very long audio files.
    """
    duration = 3600.0  # 1 hour
    processor = processor_factory(duration_seconds=duration)

    # Should have 360 chunks (3600s / 10s)
    expected_chunks = int(duration / CHUNK_DURATION)

    assert processor.total_chunks == expected_chunks, \
        f"1 hour audio should have {expected_chunks} chunks, got {processor.total_chunks}"

    # Test first chunk
    chunk1, start1, end1 = processor.load_chunk(0, with_context=False)
    assert chunk1 is not None
    assert start1 == 0.0

    # Test last chunk
    last_idx = processor.total_chunks - 1
    chunk_last, start_last, end_last = processor.load_chunk(last_idx, with_context=False)
    assert chunk_last is not None
    assert end_last == duration


@pytest.mark.boundary
@pytest.mark.audio
def test_two_hour_audio_chunk_count(processor_factory):
    """
    BOUNDARY: Very long audio (2 hours = 7200s).

    Tests chunk count calculation for extremely long audio.
    """
    duration = 7200.0  # 2 hours
    processor = processor_factory(duration_seconds=duration)

    expected_chunks = int(duration / CHUNK_DURATION)  # 720 chunks

    assert processor.total_chunks == expected_chunks, \
        f"2 hour audio should have {expected_chunks} chunks, got {processor.total_chunks}"


# ============================================================================
# Boundary Tests - Sample Rates
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_different_sample_rate_48000(processor_factory):
    """
    BOUNDARY: Different sample rate (48000 Hz).

    Tests that chunking works correctly with non-standard sample rates.
    """
    processor = processor_factory(duration_seconds=20.0, sample_rate=48000)

    assert processor.sample_rate == 48000
    assert processor.total_chunks == 2

    # Verify chunk sample counts match sample rate
    chunk, start, end = processor.load_chunk(0, with_context=False)
    expected_samples = int(CHUNK_DURATION * 48000 * 2)  # Stereo

    assert len(chunk) == expected_samples, \
        f"Chunk sample count mismatch for 48kHz: expected {expected_samples}, got {len(chunk)}"


@pytest.mark.boundary
@pytest.mark.audio
def test_high_sample_rate_96000(processor_factory):
    """
    BOUNDARY: High sample rate (96000 Hz).

    Tests that chunking works correctly with high sample rates.
    """
    processor = processor_factory(duration_seconds=10.0, sample_rate=96000)

    assert processor.sample_rate == 96000
    assert processor.total_chunks == 1

    chunk, start, end = processor.load_chunk(0, with_context=False)
    expected_samples = int(10.0 * 96000 * 2)  # Stereo

    assert len(chunk) == expected_samples


# ============================================================================
# Boundary Tests - Chunk Index
# ============================================================================

@pytest.mark.boundary
@pytest.mark.unit
def test_load_chunk_at_index_zero(processor_factory):
    """
    BOUNDARY: Load chunk at index 0 (first chunk).

    Tests the minimum valid chunk index.
    """
    processor = processor_factory(duration_seconds=30.0)

    chunk, start, end = processor.load_chunk(0, with_context=False)

    assert chunk is not None
    assert start == 0.0
    assert len(chunk) > 0


@pytest.mark.boundary
@pytest.mark.unit
def test_load_chunk_at_last_index(processor_factory):
    """
    BOUNDARY: Load chunk at last valid index.

    Tests the maximum valid chunk index.
    """
    processor = processor_factory(duration_seconds=30.0)

    last_idx = processor.total_chunks - 1
    chunk, start, end = processor.load_chunk(last_idx, with_context=False)

    assert chunk is not None
    assert end == processor.total_duration
    assert len(chunk) > 0


@pytest.mark.boundary
@pytest.mark.unit
def test_load_chunk_beyond_last_index_raises_error(processor_factory):
    """
    BOUNDARY: Load chunk beyond last valid index (should fail gracefully).

    Tests off-by-one error handling.
    """
    processor = processor_factory(duration_seconds=30.0)

    invalid_idx = processor.total_chunks  # One past the last valid index

    with pytest.raises((IndexError, ValueError)):
        processor.load_chunk(invalid_idx, with_context=False)


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about boundary tests."""
    print("\n" + "=" * 70)
    print("CHUNKED PROCESSOR BOUNDARY TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total boundary tests: 15")
    print(f"\nTest categories:")
    print(f"  - Minimum duration tests: 3")
    print(f"  - Chunk boundary tests: 3")
    print(f"  - Maximum duration tests: 2")
    print(f"  - Sample rate tests: 2")
    print(f"  - Chunk index tests: 3")
    print(f"  - Summary stats: 1")
    print("=" * 70)
