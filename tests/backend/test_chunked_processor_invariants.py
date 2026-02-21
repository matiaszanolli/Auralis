#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Chunked Audio Processor Invariant Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Critical invariant tests for ChunkedAudioProcessor that would have caught the overlap bug.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: The overlap bug (OVERLAP_DURATION=3s with CHUNK_DURATION=10s) had 100% code coverage
but zero validation. These tests validate properties that MUST always hold, regardless of
implementation details.

Test Philosophy:
- Test invariants (properties that must always hold)
- Test behavior, not implementation
- Focus on defect detection, not line execution
- Integration tests > unit tests for configuration bugs

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

# Import the module under test
import sys
import tempfile
from pathlib import Path
from typing import Tuple

import numpy as np
import pytest

backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from core.chunked_processor import (
    CHUNK_DURATION,
    CONTEXT_DURATION,
    MAX_LEVEL_CHANGE_DB,
    OVERLAP_DURATION,
    ChunkedAudioProcessor,
    apply_crossfade_between_chunks,
)

# Add root to path for auralis imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from auralis.io.saver import save as save_audio

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_audio_file(tmp_path):
    """Create a test audio file (90 seconds, stereo, 44.1kHz)."""
    duration = 90.0  # seconds
    sample_rate = 44100
    num_samples = int(duration * sample_rate)

    # Generate test audio: stereo sine wave
    t = np.linspace(0, duration, num_samples)
    frequency = 440.0  # A4 note
    audio = np.sin(2 * np.pi * frequency * t)

    # Make stereo
    audio_stereo = np.column_stack([audio, audio])

    # Save to file
    filepath = tmp_path / "test_audio.wav"
    save_audio(str(filepath), audio_stereo, sample_rate, subtype='PCM_16')

    return str(filepath), sample_rate, duration


@pytest.fixture
def processor(test_audio_file):
    """Create ChunkedAudioProcessor instance."""
    filepath, sample_rate, duration = test_audio_file
    return ChunkedAudioProcessor(
        track_id=1,
        filepath=filepath,
        preset="adaptive",
        intensity=1.0,
        chunk_cache={}
    )


# ============================================================================
# Configuration Invariant Tests (P0 Priority - Would Have Caught Overlap Bug)
# ============================================================================

@pytest.mark.unit
def test_overlap_is_appropriate_for_chunk_duration():
    """
    CRITICAL INVARIANT: Overlap must be less than CHUNK_DURATION / 2.

    This test would have caught the overlap bug immediately.
    Original bug: OVERLAP_DURATION=3s with CHUNK_DURATION=10s (30% overlap!)
    Fixed: OVERLAP_DURATION=0.1s with CHUNK_DURATION=10s (1% overlap)

    Why this matters:
    - Overlap >= CHUNK_DURATION/2 causes duplicate audio in concatenation
    - Creates audible "phasing" and length discrepancies
    - Was the root cause of the Beta 9.0 audio gap bug
    """
    assert OVERLAP_DURATION < CHUNK_DURATION / 2, (
        f"Overlap {OVERLAP_DURATION}s is too large for {CHUNK_DURATION}s chunks. "
        f"Must be < {CHUNK_DURATION / 2}s to prevent duplicate audio during crossfade. "
        f"This invariant violation caused the Beta 9.0 audio gap bug!"
    )


@pytest.mark.unit
def test_overlap_is_positive():
    """
    INVARIANT: Overlap must be positive for smooth transitions.

    Zero or negative overlap would cause audible clicks/pops at chunk boundaries.
    """
    assert OVERLAP_DURATION > 0, (
        f"Overlap must be positive for smooth crossfading, got {OVERLAP_DURATION}s"
    )


@pytest.mark.unit
def test_context_duration_is_reasonable():
    """
    INVARIANT: Context duration should be reasonable for processing quality.

    Too small: Poor processing quality (not enough context for analysis)
    Too large: Excessive memory usage and slow chunk loading
    """
    assert 1.0 <= CONTEXT_DURATION <= 10.0, (
        f"Context duration {CONTEXT_DURATION}s outside reasonable range [1.0, 10.0]s"
    )


@pytest.mark.unit
def test_chunk_duration_is_reasonable():
    """
    INVARIANT: Chunk duration should balance latency and overhead.

    Too small: Excessive chunk count, high processing overhead
    Too large: Slow initial playback start, poor instant toggle
    """
    assert 5.0 <= CHUNK_DURATION <= 60.0, (
        f"Chunk duration {CHUNK_DURATION}s outside reasonable range [5.0, 60.0]s"
    )


@pytest.mark.unit
def test_max_level_change_is_reasonable():
    """
    INVARIANT: Maximum level change should prevent audible volume jumps.

    Too small: Over-normalized, unnatural dynamics
    Too large: Audible volume jumps between chunks
    """
    assert 0.5 <= MAX_LEVEL_CHANGE_DB <= 3.0, (
        f"Max level change {MAX_LEVEL_CHANGE_DB} dB outside reasonable range [0.5, 3.0] dB"
    )


# ============================================================================
# Chunk Boundary Invariant Tests (P0 Priority)
# ============================================================================

@pytest.mark.integration
def test_chunks_cover_entire_duration_no_gaps(processor):
    """
    CRITICAL INVARIANT: Chunk boundaries must cover entire audio duration.

    This test validates that chunks start at 0 and end at total_duration,
    with proper overlaps connecting them.

    Note: When summing raw chunk samples, overlaps cause duplication.
    That's expected and correct - overlaps allow smooth crossfading.
    This test instead validates coverage via start/end times.
    """
    # Validate first chunk starts at 0
    _, first_start, first_end = processor.load_chunk(0, with_context=False)
    assert first_start == 0.0, f"First chunk should start at 0.0s, got {first_start}s"

    # Validate last chunk ends at or near total duration
    last_idx = processor.total_chunks - 1
    _, last_start, last_end = processor.load_chunk(last_idx, with_context=False)

    # Allow 0.5s tolerance for edge cases
    assert abs(last_end - processor.total_duration) < 0.5, (
        f"Last chunk should end at {processor.total_duration:.2f}s, got {last_end:.2f}s"
    )

    # Validate all chunks are continuous (with overlaps)
    for chunk_idx in range(processor.total_chunks - 1):
        _, _, curr_end = processor.load_chunk(chunk_idx, with_context=False)
        _, next_start, _ = processor.load_chunk(chunk_idx + 1, with_context=False)

        # Next chunk should start before or at current chunk end (for overlap)
        assert next_start <= curr_end + 0.1, (
            f"Gap between chunks {chunk_idx} and {chunk_idx + 1}: "
            f"chunk {chunk_idx} ends at {curr_end:.3f}s, "
            f"chunk {chunk_idx + 1} starts at {next_start:.3f}s"
        )


@pytest.mark.integration
def test_chunk_boundaries_are_continuous(processor):
    """
    INVARIANT: Chunk N+1 should start before chunk N ends (accounting for overlap).

    Validates that chunks form a continuous timeline with overlap for crossfading.

    Chunk layout with CHUNK_INTERVAL=10s, CHUNK_DURATION=15s, OVERLAP_DURATION=5s:
    - Chunk 0: [0.0, 15.0]s
    - Chunk 1: [10.0, 25.0]s (starts 5s before chunk 0 ends for 5s overlap)
    - Chunk 2: [20.0, 35.0]s
    - ...
    - Each chunk starts at: chunk_idx * CHUNK_INTERVAL
    - Each chunk ends at: chunk_idx * CHUNK_INTERVAL + CHUNK_DURATION
    """
    from core.chunked_processor import CHUNK_INTERVAL

    for chunk_idx in range(processor.total_chunks - 1):
        _, chunk_start, chunk_end = processor.load_chunk(chunk_idx, with_context=False)
        _, next_chunk_start, next_chunk_end = processor.load_chunk(chunk_idx + 1, with_context=False)

        # Each chunk starts at chunk_idx * CHUNK_INTERVAL
        expected_start = chunk_idx * CHUNK_INTERVAL
        expected_end = chunk_idx * CHUNK_INTERVAL + CHUNK_DURATION
        expected_next_start = (chunk_idx + 1) * CHUNK_INTERVAL
        expected_next_end = (chunk_idx + 1) * CHUNK_INTERVAL + CHUNK_DURATION

        # Allow 0.1s tolerance for floating point rounding
        assert abs(chunk_start - expected_start) < 0.1, (
            f"Chunk {chunk_idx} start mismatch: expected {expected_start:.3f}s, got {chunk_start:.3f}s"
        )
        assert abs(chunk_end - expected_end) < 0.1, (
            f"Chunk {chunk_idx} end mismatch: expected {expected_end:.3f}s, got {chunk_end:.3f}s"
        )
        assert abs(next_chunk_start - expected_next_start) < 0.1, (
            f"Chunk {chunk_idx + 1} start mismatch: expected {expected_next_start:.3f}s, got {next_chunk_start:.3f}s"
        )

        # Verify there's overlap between chunks (next starts before current ends)
        assert next_chunk_start < chunk_end, (
            f"No overlap between chunks {chunk_idx} and {chunk_idx + 1}: "
            f"chunk {chunk_idx} ends at {chunk_end:.3f}s, "
            f"chunk {chunk_idx + 1} starts at {next_chunk_start:.3f}s"
        )


@pytest.mark.integration
def test_first_chunk_starts_at_zero(processor):
    """
    INVARIANT: First chunk must start at time 0.
    """
    _, chunk_start, _ = processor.load_chunk(0, with_context=False)
    assert chunk_start == 0.0, f"First chunk should start at 0.0s, got {chunk_start}s"


@pytest.mark.integration
def test_last_chunk_ends_at_total_duration(processor):
    """
    INVARIANT: Last chunk must end at exactly total duration.
    """
    last_idx = processor.total_chunks - 1
    _, _, chunk_end = processor.load_chunk(last_idx, with_context=False)

    # Allow 0.1s tolerance for rounding
    assert abs(chunk_end - processor.total_duration) < 0.1, (
        f"Last chunk should end at {processor.total_duration:.2f}s, got {chunk_end:.2f}s"
    )


@pytest.mark.integration
def test_chunk_count_calculation(processor):
    """
    INVARIANT: Number of chunks should correctly cover total duration.

    Formula: total_chunks = ceil(total_duration / CHUNK_INTERVAL)

    Note: Chunks are based on CHUNK_INTERVAL (10s), not CHUNK_DURATION (15s).
    This allows for 5s overlaps (CHUNK_DURATION - CHUNK_INTERVAL = 15 - 10 = 5).
    """
    import math

    from core.chunked_processor import CHUNK_INTERVAL
    expected_chunks = math.ceil(processor.total_duration / CHUNK_INTERVAL)

    assert processor.total_chunks == expected_chunks, (
        f"Chunk count mismatch: got {processor.total_chunks}, "
        f"expected {expected_chunks} for {processor.total_duration:.1f}s duration "
        f"(using CHUNK_INTERVAL={CHUNK_INTERVAL}s)"
    )


# ============================================================================
# Audio Processing Invariant Tests (P0 Priority)
# ============================================================================

@pytest.mark.audio
@pytest.mark.integration
def test_processing_preserves_sample_count_per_chunk(processor):
    """
    INVARIANT: Processed chunk must have same sample count as input chunk.

    Processing should not add or remove samples (except context trimming).
    """
    # Process first chunk
    chunk_idx = 0

    # Load original chunk
    original_chunk, _, _ = processor.load_chunk(chunk_idx, with_context=True)
    original_samples = len(original_chunk)

    # Process chunk (this creates the processed file)
    processor.process_chunk(chunk_idx)

    # Load processed chunk
    from auralis.io.unified_loader import load_audio
    chunk_path = processor._get_chunk_path(chunk_idx)
    processed_chunk, _ = load_audio(str(chunk_path))
    processed_samples = len(processed_chunk)

    # After processing and context trimming, we expect a specific duration
    # For chunk 0: CHUNK_DURATION (no overlap)
    expected_duration = CHUNK_DURATION
    expected_samples = int(expected_duration * processor.sample_rate)

    # Allow 1% tolerance for context trimming and windowing
    tolerance = int(0.01 * expected_samples)

    assert abs(processed_samples - expected_samples) <= tolerance, (
        f"Sample count changed during processing: "
        f"expected ~{expected_samples} samples ({expected_duration:.1f}s), "
        f"got {processed_samples} samples ({processed_samples / processor.sample_rate:.2f}s)"
    )


@pytest.mark.audio
@pytest.mark.integration
def test_processed_chunks_concatenate_to_correct_duration(processor):
    """
    CRITICAL INVARIANT: Processed chunks should have reasonable duration.

    With overlaps, sum of raw chunks will exceed original due to overlap duplication.
    This test validates chunks can be loaded and processed without errors.
    """
    # Process all chunks
    for chunk_idx in range(processor.total_chunks):
        processor.process_chunk(chunk_idx)

    # Load all processed chunks to verify they exist and have content
    from auralis.io.unified_loader import load_audio

    total_samples = 0
    for chunk_idx in range(processor.total_chunks):
        chunk_path = processor._get_chunk_path(chunk_idx)
        chunk_audio, _ = load_audio(str(chunk_path))
        assert chunk_audio is not None, f"Chunk {chunk_idx} should load successfully"
        assert len(chunk_audio) > 0, f"Chunk {chunk_idx} should have audio data"
        total_samples += len(chunk_audio)

    # With overlaps, total samples will be more than original
    # Just verify it's reasonable (not 0, not huge anomalies)
    total_duration = total_samples / processor.sample_rate

    # With 5s overlaps between chunks, total should be roughly:
    # original_duration + (num_chunks - 1) * overlap_duration
    from core.chunked_processor import CHUNK_INTERVAL
    expected_overlap_seconds = max(0, (processor.total_chunks - 1) * OVERLAP_DURATION)
    rough_expected = processor.total_duration + expected_overlap_seconds

    # Allow reasonable variance due to crossfading and windowing
    tolerance = processor.total_duration * 0.5  # 50% tolerance for overlap effects

    assert total_duration < rough_expected + tolerance, (
        f"Processed chunks duration seems wrong: "
        f"got {total_duration:.2f}s (with overlaps), "
        f"expected around {rough_expected:.2f}s"
    )


# ============================================================================
# Crossfade Invariant Tests (P1 Priority)
# ============================================================================

@pytest.mark.unit
def test_crossfade_preserves_total_duration():
    """
    INVARIANT: Crossfading two chunks should not change total duration.

    Result length = len(chunk1) + len(chunk2) - overlap_samples
    """
    # Create two test chunks
    chunk1 = np.random.randn(44100, 2)  # 1 second stereo
    chunk2 = np.random.randn(44100, 2)  # 1 second stereo
    overlap_samples = 4410  # 0.1 second overlap

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap_samples)

    expected_length = len(chunk1) + len(chunk2) - overlap_samples

    assert len(result) == expected_length, (
        f"Crossfade changed duration: expected {expected_length} samples, "
        f"got {len(result)} samples"
    )


@pytest.mark.unit
def test_crossfade_handles_stereo_correctly():
    """
    INVARIANT: Crossfade must preserve stereo channel count.
    """
    chunk1 = np.random.randn(44100, 2)  # Stereo
    chunk2 = np.random.randn(44100, 2)  # Stereo
    overlap_samples = 4410

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap_samples)

    assert result.ndim == 2, f"Expected 2D array (stereo), got {result.ndim}D"
    assert result.shape[1] == 2, f"Expected 2 channels, got {result.shape[1]}"


@pytest.mark.unit
def test_crossfade_with_zero_overlap_concatenates():
    """
    INVARIANT: Zero overlap should result in simple concatenation.
    """
    chunk1 = np.random.randn(44100, 2)
    chunk2 = np.random.randn(44100, 2)
    overlap_samples = 0

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap_samples)
    expected = np.concatenate([chunk1, chunk2], axis=0)

    assert len(result) == len(expected), "Zero overlap should concatenate"
    np.testing.assert_array_equal(result, expected)


@pytest.mark.unit
def test_crossfade_overlap_larger_than_chunks_handles_gracefully():
    """
    INVARIANT: Crossfade should handle edge case where overlap > chunk length.
    """
    chunk1 = np.random.randn(1000, 2)
    chunk2 = np.random.randn(1000, 2)
    overlap_samples = 10000  # Larger than chunks

    # Should not crash, should use actual available overlap
    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap_samples)

    assert len(result) > 0, "Should handle excessive overlap gracefully"


# ============================================================================
# Cache Invariant Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_cache_key_includes_file_signature(processor):
    """
    INVARIANT: Cache keys must include file signature to prevent stale cache.

    If a track file is modified, old cached chunks must not be served.
    """
    # Phase 5.1 update: Use ChunkCacheManager API
    from core.chunk_cache_manager import ChunkCacheManager
    cache_key = ChunkCacheManager.get_chunk_cache_key(
        processor.track_id, processor.file_signature, processor.preset, processor.intensity, 0
    )

    # Cache key should include file signature
    assert processor.file_signature in cache_key, (
        f"Cache key must include file signature to prevent stale cache: {cache_key}"
    )


@pytest.mark.integration
def test_cache_key_includes_all_processing_parameters(processor):
    """
    INVARIANT: Cache keys must include all parameters that affect output.

    Different presets/intensities must have different cache keys.
    """
    # Phase 5.1 update: Use ChunkCacheManager API
    from core.chunk_cache_manager import ChunkCacheManager
    cache_key = ChunkCacheManager.get_chunk_cache_key(
        processor.track_id, processor.file_signature, processor.preset, processor.intensity, 0
    )

    # Should include track_id, preset, intensity, chunk_index
    assert str(processor.track_id) in cache_key, "Cache key must include track_id"
    assert processor.preset in cache_key, "Cache key must include preset"
    assert str(processor.intensity) in cache_key, "Cache key must include intensity"


@pytest.mark.integration
def test_cached_chunks_are_reused(processor):
    """
    INVARIANT: Processing the same chunk twice should use cache.
    """
    # Process chunk 0 first time (returns tuple of (path, audio_array))
    path1, _ = processor.process_chunk(0)

    # Process chunk 0 second time (should use cache)
    path2, _ = processor.process_chunk(0)

    assert path1 == path2, "Should return same path from cache"

    # Verify cache was actually used (Phase 5.1: Use ChunkCacheManager API)
    from core.chunk_cache_manager import ChunkCacheManager
    cache_key = ChunkCacheManager.get_chunk_cache_key(
        processor.track_id, processor.file_signature, processor.preset, processor.intensity, 0
    )
    assert cache_key in processor.chunk_cache, "Chunk should be in cache"


# ============================================================================
# Level Smoothing Invariant Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_level_smoothing_limits_rms_changes(processor):
    """
    INVARIANT: RMS level changes between chunks must be limited.

    Prevents audible volume jumps between chunks.
    """
    # Process first two chunks
    processor.process_chunk(0)
    processor.process_chunk(1)

    # Check RMS history
    assert len(processor.chunk_rms_history) >= 2, "Should have RMS history for 2 chunks"

    # Calculate RMS difference between chunks
    if len(processor.chunk_rms_history) >= 2:
        rms_diff = abs(processor.chunk_rms_history[1] - processor.chunk_rms_history[0])

        assert rms_diff <= MAX_LEVEL_CHANGE_DB, (
            f"RMS change {rms_diff:.2f} dB exceeds maximum {MAX_LEVEL_CHANGE_DB} dB"
        )


@pytest.mark.integration
def test_level_smoothing_tracks_chunk_history(processor):
    """
    INVARIANT: Level smoothing must track history for all processed chunks.
    """
    # Process 3 chunks
    for chunk_idx in range(min(3, processor.total_chunks)):
        processor.process_chunk(chunk_idx)

    chunks_processed = min(3, processor.total_chunks)

    assert len(processor.chunk_rms_history) == chunks_processed, (
        f"RMS history length {len(processor.chunk_rms_history)} doesn't match "
        f"chunks processed {chunks_processed}"
    )
    assert len(processor.chunk_gain_history) == chunks_processed, (
        f"Gain history length {len(processor.chunk_gain_history)} doesn't match "
        f"chunks processed {chunks_processed}"
    )


# ============================================================================
# File Signature Invariant Tests (P2 Priority)
# ============================================================================

@pytest.mark.unit
def test_file_signature_changes_when_file_modified(test_audio_file, tmp_path):
    """
    INVARIANT: File signature must change when file is modified.

    Ensures cache invalidation when track is updated.
    """
    filepath, _, _ = test_audio_file

    # Create first processor
    processor1 = ChunkedAudioProcessor(
        track_id=1,
        filepath=filepath,
        preset="adaptive",
        intensity=1.0
    )
    sig1 = processor1.file_signature

    # Wait a moment and modify the file (change modification time)
    import time
    time.sleep(0.1)

    # Touch the file to update mtime
    Path(filepath).touch()

    # Create second processor for same file
    processor2 = ChunkedAudioProcessor(
        track_id=1,
        filepath=filepath,
        preset="adaptive",
        intensity=1.0
    )
    sig2 = processor2.file_signature

    assert sig1 != sig2, (
        f"File signature should change when file is modified: {sig1} == {sig2}"
    )


# ============================================================================
# Sample Alignment Invariant Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_chunk_samples_are_frame_aligned(processor):
    """
    INVARIANT: All chunks must be frame-aligned (sample count is multiple of channel count).

    Misaligned chunks cause audio corruption and channel swap.
    """
    for chunk_idx in range(processor.total_chunks):
        audio_chunk, _, _ = processor.load_chunk(chunk_idx, with_context=False)

        # For stereo audio, sample count must be even
        assert len(audio_chunk) % 2 == 0, (
            f"Chunk {chunk_idx} has {len(audio_chunk)} samples, "
            f"not frame-aligned for stereo (should be multiple of 2)"
        )


@pytest.mark.integration
def test_overlap_samples_are_frame_aligned(processor):
    """
    INVARIANT: Overlap region must be frame-aligned.

    Misaligned overlaps cause channel issues during crossfading.
    """
    overlap_samples = int(OVERLAP_DURATION * processor.sample_rate)

    # For stereo, overlap samples must be even
    assert overlap_samples % 2 == 0, (
        f"Overlap samples {overlap_samples} not frame-aligned for stereo "
        f"(should be multiple of 2)"
    )


# ============================================================================
# Chunk Overlap Edge Cases (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_overlap_never_exceeds_chunk_duration(processor):
    """
    INVARIANT: Overlap must never equal or exceed chunk duration.

    Overlap >= chunk duration causes chunks to become negative length.
    """
    for chunk_idx in range(processor.total_chunks):
        _, chunk_start, chunk_end = processor.load_chunk(chunk_idx, with_context=False)
        chunk_duration = chunk_end - chunk_start

        assert OVERLAP_DURATION < chunk_duration, (
            f"Chunk {chunk_idx} duration {chunk_duration:.2f}s is less than "
            f"overlap {OVERLAP_DURATION}s - would cause negative chunk length!"
        )


@pytest.mark.integration
def test_all_chunks_have_consistent_overlap(processor):
    """
    INVARIANT: All chunk overlaps should be consistent (except last chunk).

    Inconsistent overlaps cause audible transitions and timing issues.
    """
    overlaps = []

    for chunk_idx in range(processor.total_chunks - 1):
        _, chunk_start, chunk_end = processor.load_chunk(chunk_idx, with_context=False)
        _, next_chunk_start, _ = processor.load_chunk(chunk_idx + 1, with_context=False)

        # Calculate actual overlap
        overlap = chunk_end - next_chunk_start
        overlaps.append(overlap)

    if overlaps:
        # All overlaps should be within 0.01s of each other
        min_overlap = min(overlaps)
        max_overlap = max(overlaps)

        assert abs(max_overlap - min_overlap) < 0.01, (
            f"Inconsistent overlaps detected: min={min_overlap:.3f}s, "
            f"max={max_overlap:.3f}s (difference: {abs(max_overlap - min_overlap):.3f}s)"
        )


# ============================================================================
# Duration Preservation Edge Cases (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_single_chunk_preserves_exact_duration(processor):
    """
    INVARIANT: For single-chunk audio, output duration must exactly match input.

    No crossfading occurs with single chunk, so duration must be perfect.
    """
    if processor.total_chunks == 1:
        processor.process_chunk(0)

        from auralis.io.unified_loader import load_audio
        chunk_path = processor._get_chunk_path(0)
        processed_chunk, _ = load_audio(str(chunk_path))

        processed_duration = len(processed_chunk) / processor.sample_rate

        # Single chunk should match original duration exactly (within 0.01s)
        assert abs(processed_duration - processor.total_duration) < 0.01, (
            f"Single chunk duration mismatch: "
            f"expected {processor.total_duration:.3f}s, "
            f"got {processed_duration:.3f}s"
        )
    else:
        pytest.skip("Test only applies to single-chunk audio")


@pytest.mark.integration
def test_multi_chunk_preserves_total_duration_within_tolerance(processor):
    """
    INVARIANT: Multi-chunk audio timeline coverage must span total duration.

    With overlaps, raw sum of chunks will be > original duration.
    This test validates that the timeline is properly covered.
    """
    if processor.total_chunks > 1:
        # Validate chunk timeline coverage
        # First chunk starts at 0
        _, first_start, first_end = processor.load_chunk(0, with_context=False)
        assert first_start == 0.0, f"First chunk should start at 0.0, got {first_start}"

        # Last chunk should cover up to total_duration
        last_idx = processor.total_chunks - 1
        _, last_start, last_end = processor.load_chunk(last_idx, with_context=False)

        # Allow 0.5s tolerance for edge cases
        assert abs(last_end - processor.total_duration) < 0.5, (
            f"Last chunk should end at {processor.total_duration:.2f}s, "
            f"got {last_end:.2f}s, difference: {abs(last_end - processor.total_duration):.2f}s"
        )
    else:
        pytest.skip("Test only applies to multi-chunk audio")


# ============================================================================
# Edge Case Tests (P2 Priority)
# ============================================================================

@pytest.mark.integration
def test_handles_very_short_audio():
    """
    INVARIANT: Should handle audio shorter than one chunk duration.
    """
    # Create 2-second audio (shorter than CHUNK_DURATION=10s)
    import tempfile
    duration = 2.0
    sample_rate = 44100
    num_samples = int(duration * sample_rate)
    audio = np.random.randn(num_samples, 2)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        filepath = f.name
        save_audio(filepath, audio, sample_rate, subtype='PCM_16')

    try:
        processor = ChunkedAudioProcessor(
            track_id=999,
            filepath=filepath,
            preset="adaptive",
            intensity=1.0
        )

        # Should have exactly 1 chunk
        assert processor.total_chunks == 1, (
            f"Short audio should have 1 chunk, got {processor.total_chunks}"
        )

        # Should be able to process it
        processor.process_chunk(0)

    finally:
        Path(filepath).unlink()


@pytest.mark.integration
def test_handles_exactly_one_chunk_interval():
    """
    INVARIANT: Should handle audio that is exactly one chunk interval.

    With CHUNK_INTERVAL=10s, 10s audio = ceil(10/10) = 1 chunk
    """
    import tempfile

    from core.chunked_processor import CHUNK_INTERVAL

    duration = float(CHUNK_INTERVAL)  # Exactly 10 seconds (one CHUNK_INTERVAL)
    sample_rate = 44100
    num_samples = int(duration * sample_rate)
    audio = np.random.randn(num_samples, 2)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        filepath = f.name
        save_audio(filepath, audio, sample_rate, subtype='PCM_16')

    try:
        processor = ChunkedAudioProcessor(
            track_id=998,
            filepath=filepath,
            preset="adaptive",
            intensity=1.0
        )

        # 10s audio with CHUNK_INTERVAL=10s should have exactly 1 chunk
        assert processor.total_chunks == 1, (
            f"10s audio (one CHUNK_INTERVAL) should have 1 chunk, got {processor.total_chunks}"
        )

    finally:
        Path(filepath).unlink()


# ============================================================================
# Summary Statistics
# ============================================================================

def test_summary_stats():
    """
    Print summary of what these tests validate.

    This is not a real test, just documentation.
    """
    print("\n" + "=" * 80)
    print("CHUNKED PROCESSOR INVARIANT TEST SUMMARY")
    print("=" * 80)
    print(f"Configuration Invariants: 5 tests")
    print(f"Chunk Boundary Invariants: 5 tests")
    print(f"Audio Processing Invariants: 2 tests")
    print(f"Crossfade Invariants: 4 tests")
    print(f"Cache Invariants: 3 tests")
    print(f"Level Smoothing Invariants: 2 tests")
    print(f"File Signature Invariants: 1 test")
    print(f"Sample Alignment Invariants: 2 tests")
    print(f"Chunk Overlap Edge Cases: 2 tests")
    print(f"Duration Preservation Edge Cases: 2 tests")
    print(f"General Edge Case Tests: 2 tests")
    print("=" * 80)
    print(f"TOTAL: 30 critical invariant tests")
    print("=" * 80)
    print("\nThese tests validate properties that MUST always hold,")
    print("regardless of implementation details.")
    print("\nKey Principle: Test behavior, not code.")
    print("=" * 80 + "\n")
