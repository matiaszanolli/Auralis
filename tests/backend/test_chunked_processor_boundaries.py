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

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from core.chunked_processor import (
    CHUNK_DURATION,
    OVERLAP_DURATION,
    ChunkedAudioProcessor,
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
            track_id=1,  # Use track_id parameter
            filepath=str(filepath),  # Use filepath parameter
            preset="adaptive",
            intensity=1.0  # Use intensity parameter
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
    # len(chunk) returns number of samples (rows in (samples, channels) array)
    assert len(chunk) == int(0.1 * processor.sample_rate)


@pytest.mark.boundary
@pytest.mark.audio
def test_audio_exactly_chunk_duration(processor_factory):
    """
    BOUNDARY: Audio exactly CHUNK_DURATION (15s).

    Edge case: When audio length exactly matches chunk duration.
    Note: Chunks are calculated based on CHUNK_INTERVAL (10s), not CHUNK_DURATION (15s)
    So 15s audio = ceil(15/10) = 2 chunks
    """
    processor = processor_factory(duration_seconds=CHUNK_DURATION)

    # 15s / 10s interval = ceil(1.5) = 2 chunks
    assert processor.total_chunks == 2, \
        f"Audio of exactly {CHUNK_DURATION}s should have 2 chunks, got {processor.total_chunks}"

    # First chunk spans 0-10s
    chunk1, start1, end1 = processor.load_chunk(0, with_context=False)
    assert chunk1 is not None
    assert len(chunk1) > 0

    # Second chunk spans 10-15s
    chunk2, start2, end2 = processor.load_chunk(1, with_context=False)
    assert chunk2 is not None
    assert len(chunk2) > 0


@pytest.mark.boundary
@pytest.mark.audio
def test_audio_just_over_chunk_duration(processor_factory):
    """
    BOUNDARY: Audio just slightly longer than CHUNK_DURATION (15.1s).

    Edge case: Should create 2 chunks based on CHUNK_INTERVAL (10s).
    Note: 15.1s / 10s interval = ceil(1.51) = 2 chunks
    """
    duration = CHUNK_DURATION + 0.1
    processor = processor_factory(duration_seconds=duration)

    assert processor.total_chunks == 2, \
        f"Audio of {duration}s should have 2 chunks, got {processor.total_chunks}"

    # First chunk spans 0-10s
    chunk1, start1, end1 = processor.load_chunk(0, with_context=False)
    assert chunk1 is not None
    assert len(chunk1) > 0

    # Second chunk spans 10-15.1s
    chunk2, start2, end2 = processor.load_chunk(1, with_context=False)
    assert chunk2 is not None
    assert len(chunk2) > 0


# ============================================================================
# Boundary Tests - Chunk Boundaries
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_chunk_boundary_at_exact_multiples_of_interval(processor_factory):
    """
    BOUNDARY: Chunk boundaries at exact multiples of CHUNK_INTERVAL (10s).

    Tests that chunk boundaries are calculated correctly.
    Note: CHUNK_DURATION=15s, CHUNK_INTERVAL=10s (used for chunk calculation)
    30s / 10s = 3 chunks at 0-10s, 10-20s, 20-30s
    """
    processor = processor_factory(duration_seconds=30.0)

    assert processor.total_chunks == 3, f"30s audio should have 3 chunks, got {processor.total_chunks}"

    # Chunks should exist and be loadable
    for chunk_idx in range(3):
        chunk, start, end = processor.load_chunk(chunk_idx, with_context=False)
        assert chunk is not None, f"Chunk {chunk_idx} should load successfully"
        assert len(chunk) > 0, f"Chunk {chunk_idx} should have audio data"


@pytest.mark.boundary
@pytest.mark.audio
def test_chunk_boundary_at_45_seconds(processor_factory):
    """
    BOUNDARY: Multiple chunk boundaries with longer audio.

    Tests chunks at 45 seconds.
    Note: 45s / 10s CHUNK_INTERVAL = ceil(4.5) = 5 chunks
    """
    processor = processor_factory(duration_seconds=45.0)

    # 45s / 10s interval = ceil(4.5) = 5 chunks
    expected_chunks = 5
    assert processor.total_chunks == expected_chunks, \
        f"45s audio should have {expected_chunks} chunks, got {processor.total_chunks}"

    # All chunks should load successfully
    for chunk_idx in range(expected_chunks):
        chunk, start, end = processor.load_chunk(chunk_idx, with_context=False)
        assert chunk is not None, f"Chunk {chunk_idx} should load successfully"
        assert len(chunk) > 0, f"Chunk {chunk_idx} should have audio data"


@pytest.mark.boundary
@pytest.mark.audio
def test_last_chunk_at_boundary(processor_factory):
    """
    BOUNDARY: Last chunk at audio boundary.

    Tests that the last chunk loads correctly and ends at total duration.
    Note: Chunk calculation is ceil(duration / CHUNK_INTERVAL)
    """
    # Create audio that results in clean chunk boundaries
    total_duration = 40.0  # 40s / 10s = 4 chunks exactly
    processor = processor_factory(duration_seconds=total_duration)

    expected_chunks = int(np.ceil(total_duration / OVERLAP_DURATION))  # Using CHUNK_INTERVAL instead
    # Actually, let me recalculate: 40 / 10 = 4
    assert processor.total_chunks == 4, \
        f"40s audio should have 4 chunks, got {processor.total_chunks}"

    # Last chunk should load successfully
    last_chunk, start, end = processor.load_chunk(3, with_context=False)
    assert last_chunk is not None
    assert len(last_chunk) > 0
    # Total duration should match
    assert abs(processor.total_duration - total_duration) < 0.01


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
    Note: Chunks are calculated as ceil(duration / CHUNK_INTERVAL)
    1 hour = 3600s / 10s CHUNK_INTERVAL = 360 chunks
    """
    duration = 3600.0  # 1 hour
    processor = processor_factory(duration_seconds=duration)

    # Should have 360 chunks (3600s / 10s CHUNK_INTERVAL)
    from core.chunked_processor import CHUNK_INTERVAL
    expected_chunks = int(np.ceil(duration / CHUNK_INTERVAL))

    assert processor.total_chunks == expected_chunks, \
        f"1 hour audio should have {expected_chunks} chunks, got {processor.total_chunks}"

    # Test first chunk
    chunk1, start1, end1 = processor.load_chunk(0, with_context=False)
    assert chunk1 is not None
    assert len(chunk1) > 0

    # Test last chunk
    last_idx = processor.total_chunks - 1
    chunk_last, start_last, end_last = processor.load_chunk(last_idx, with_context=False)
    assert chunk_last is not None
    assert len(chunk_last) > 0


@pytest.mark.boundary
@pytest.mark.audio
def test_two_hour_audio_chunk_count(processor_factory):
    """
    BOUNDARY: Very long audio (2 hours = 7200s).

    Tests chunk count calculation for extremely long audio.
    Note: 7200s / 10s CHUNK_INTERVAL = 720 chunks
    """
    duration = 7200.0  # 2 hours
    processor = processor_factory(duration_seconds=duration)

    from core.chunked_processor import CHUNK_INTERVAL
    expected_chunks = int(np.ceil(duration / CHUNK_INTERVAL))  # 720 chunks

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
    expected_samples = int(CHUNK_DURATION * 48000)

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
    expected_samples = int(10.0 * 96000)

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
def test_load_chunk_beyond_last_index(processor_factory):
    """
    BOUNDARY: Load chunk beyond last valid index (processor behavior).

    Tests what happens when loading beyond valid chunk range.
    Note: The processor gracefully handles out-of-bounds requests by
    attempting to load audio beyond the file duration.
    """
    processor = processor_factory(duration_seconds=30.0)

    invalid_idx = processor.total_chunks  # One past the last valid index

    # The processor may return various things:
    # - A tuple with audio data (possibly zeros/silence)
    # - Or raise an error
    # Just verify it doesn't crash unexpectedly
    try:
        result = processor.load_chunk(invalid_idx, with_context=False)
        # If it returns, result should be a tuple or None
        assert result is None or isinstance(result, tuple), \
            f"Expected None or tuple, got {type(result)}"
    except (IndexError, ValueError, RuntimeError):
        # Raising an error is also acceptable behavior
        pass


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
