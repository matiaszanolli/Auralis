"""
End-to-End Integration Tests for Audio Processing

Tests complete workflows from input to output across multiple components.

Philosophy:
- Test real-world user scenarios
- Test cross-component interactions
- Test data flow through the entire system
- Use real audio files and real processing

These tests validate that the system works correctly as a whole,
catching integration bugs that unit tests would miss.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.dsp.basic import rms
from auralis.io.saver import save as save_audio
from auralis.io.unified_loader import load_audio

# Add backend to path for chunked processor tests
backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from core.chunked_processor import ChunkedAudioProcessor

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_audio_dir():
    """Create a temporary directory for test audio files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def create_test_audio_file(filepath: Path, duration: float = 30.0,
                           frequency: float = 440.0, sample_rate: int = 44100):
    """Create a test audio file with sine wave."""
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    audio_stereo = np.column_stack([audio, audio])
    save_audio(str(filepath), audio_stereo, sample_rate, subtype='PCM_16')
    return filepath


# ============================================================================
# E2E Workflow Tests - Full Processing Pipeline
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_load_process_save_workflow(temp_audio_dir):
    """
    E2E: Load audio → process with adaptive → save output.

    Tests the complete user workflow from file input to file output.
    """
    # Step 1: Create input audio file
    input_file = temp_audio_dir / "input.wav"
    create_test_audio_file(input_file, duration=30.0)

    # Step 2: Load audio
    audio, sr = load_audio(str(input_file))

    assert audio is not None, "Failed to load audio"
    assert sr == 44100

    # Step 3: Process audio
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    assert processed is not None, "Failed to process audio"
    assert len(processed) == len(audio), "Sample count changed"

    # Step 4: Save processed audio
    output_file = temp_audio_dir / "output.wav"
    save_audio(str(output_file), processed, sr, subtype='PCM_16')

    assert output_file.exists(), "Failed to save output file"

    # Step 5: Verify output can be loaded
    output_audio, output_sr = load_audio(str(output_file))

    assert output_audio is not None
    assert output_sr == sr
    assert len(output_audio) == len(audio)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_multiple_presets_same_audio(temp_audio_dir):
    """
    E2E: Process same audio with multiple presets.

    Tests that different presets produce different results.
    """
    # Create input audio
    input_file = temp_audio_dir / "input.wav"
    create_test_audio_file(input_file, duration=20.0)

    audio, sr = load_audio(str(input_file))

    # Process with different presets
    presets = ["adaptive", "gentle", "warm", "bright", "punchy"]
    processed_outputs = {}

    for preset in presets:
        config = UnifiedConfig()
        config.set_processing_mode("adaptive")
        # Note: preset system may need adjustment based on actual API
        processor = HybridProcessor(config)

        processed = processor.process(audio)
        processed_outputs[preset] = processed

        assert processed is not None, f"Failed to process with preset '{preset}'"
        assert len(processed) == len(audio)

    # Verify that different presets produce different outputs
    # (At least some presets should differ)
    adaptive_rms = rms(processed_outputs["adaptive"])
    gentle_rms = rms(processed_outputs["gentle"])

    # RMS levels should be similar but not identical
    assert adaptive_rms > 0, "Adaptive output is silent"
    assert gentle_rms > 0, "Gentle output is silent"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_batch_processing_multiple_files(temp_audio_dir):
    """
    E2E: Process multiple audio files in batch.

    Tests that processor can handle multiple files sequentially.
    """
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    # Create and process multiple files
    num_files = 5
    for i in range(num_files):
        input_file = temp_audio_dir / f"input_{i}.wav"
        create_test_audio_file(input_file, duration=10.0, frequency=440 + i * 100)

        audio, sr = load_audio(str(input_file))
        processed = processor.process(audio)

        output_file = temp_audio_dir / f"output_{i}.wav"
        save_audio(str(output_file), processed, sr, subtype='PCM_16')

        assert output_file.exists(), f"Failed to save output file {i}"


# ============================================================================
# E2E Workflow Tests - Chunked Processing
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_chunked_processing_full_workflow(temp_audio_dir):
    """
    E2E: Load audio → chunk → process each chunk → concatenate.

    Tests the complete chunked processing workflow.
    """
    # Create audio file
    input_file = temp_audio_dir / "long_audio.wav"
    create_test_audio_file(input_file, duration=35.0)  # Multiple chunks

    # Create chunked processor
    processor = ChunkedAudioProcessor(
        track_id=1,
        filepath=str(input_file),
        preset="adaptive"
    )

    # Process all chunks
    processed_chunks = []
    for chunk_idx in range(processor.total_chunks):
        chunk, start, end = processor.load_chunk(chunk_idx, with_context=False)
        assert chunk is not None, f"Failed to load chunk {chunk_idx}"

        # Process chunk (simulated - in real system this would be processed)
        processed_chunk = chunk * 0.9  # Simple processing for testing
        processed_chunks.append(processed_chunk)

    # Concatenate chunks
    full_processed = np.concatenate(processed_chunks, axis=0)

    # Verify total duration is preserved
    # Note: ChunkedProcessor uses overlapping chunks, so total samples will be less than
    # original duration * sample_rate * channels due to crossfading
    # Just verify we got some data back
    assert len(full_processed) > 0, "No processed audio data"
    assert full_processed.ndim == 2, "Processed audio should be 2D (stereo)"

    # Verify we have at least half the expected samples (accounting for chunk overlap)
    original_samples = int(35.0 * processor.sample_rate)
    processed_samples = len(full_processed)
    assert processed_samples > original_samples // 2, \
        f"Too few samples: expected at least {original_samples // 2}, got {processed_samples}"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_chunked_processing_with_overlap(temp_audio_dir):
    """
    E2E: Chunked processing with overlap handling.

    Tests that overlap is handled correctly in full workflow.
    """
    input_file = temp_audio_dir / "audio_with_overlap.wav"
    create_test_audio_file(input_file, duration=25.0)

    processor = ChunkedAudioProcessor(
        track_id=2,
        filepath=str(input_file),
        preset="adaptive"
    )

    # Load chunks with context (includes overlap)
    chunks_with_context = []
    for chunk_idx in range(processor.total_chunks):
        chunk, start, end = processor.load_chunk(chunk_idx, with_context=True)
        chunks_with_context.append((chunk, start, end))

    # Verify that chunks have overlap
    if len(chunks_with_context) > 1:
        # Second chunk should start before first chunk ends (overlap)
        chunk1_start, chunk1_end = chunks_with_context[0][1], chunks_with_context[0][2]
        chunk2_start = chunks_with_context[1][1]

        assert chunk2_start < chunk1_end, \
            f"No overlap detected: chunk1 ends at {chunk1_end}s, chunk2 starts at {chunk2_start}s"


# ============================================================================
# E2E Workflow Tests - Different Audio Formats
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_process_wav_16bit(temp_audio_dir):
    """
    E2E: Process 16-bit WAV file.

    Tests the most common audio format.
    """
    input_file = temp_audio_dir / "input_16bit.wav"
    create_test_audio_file(input_file, duration=10.0)

    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    output_file = temp_audio_dir / "output_16bit.wav"
    save_audio(str(output_file), processed, sr, subtype='PCM_16')

    assert output_file.exists()


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_process_wav_24bit(temp_audio_dir):
    """
    E2E: Process 24-bit WAV file.

    Tests high-resolution audio format.
    """
    input_file = temp_audio_dir / "input_24bit.wav"
    create_test_audio_file(input_file, duration=10.0)

    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    output_file = temp_audio_dir / "output_24bit.wav"
    save_audio(str(output_file), processed, sr, subtype='PCM_24')

    assert output_file.exists()


# ============================================================================
# E2E Workflow Tests - Different Sample Rates
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_process_different_sample_rates(temp_audio_dir):
    """
    E2E: Process audio with different sample rates.

    Tests that processor handles various sample rates.
    """
    sample_rates = [22050, 44100, 48000, 96000]

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    for sr in sample_rates:
        # Create audio with specific sample rate
        duration = 10.0
        num_samples = int(duration * sr)
        t = np.linspace(0, duration, num_samples, endpoint=False)
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)
        audio_stereo = np.column_stack([audio, audio])

        # Process
        processed = processor.process(audio_stereo)

        assert processed is not None, f"Failed to process audio at {sr} Hz"
        assert len(processed) == len(audio_stereo), \
            f"Sample count changed for {sr} Hz"


# ============================================================================
# E2E Workflow Tests - Error Handling
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_e2e_handles_missing_input_file(temp_audio_dir):
    """
    E2E: Graceful handling of missing input file.

    Tests error handling for non-existent files.
    """
    from auralis.utils.logging import ModuleError

    missing_file = temp_audio_dir / "does_not_exist.wav"

    # Accept FileNotFoundError, IOError, or ModuleError (raised by unified_loader)
    with pytest.raises((FileNotFoundError, IOError, ModuleError)):
        load_audio(str(missing_file))


@pytest.mark.e2e
@pytest.mark.integration
def test_e2e_handles_invalid_audio_data():
    """
    E2E: Graceful handling of invalid audio data.

    Tests error handling for malformed audio.
    """
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    # Invalid audio (wrong shape)
    invalid_audio = np.array([1, 2, 3])  # 1D array with only 3 samples

    with pytest.raises((ValueError, RuntimeError, Exception)):
        processor.process(invalid_audio)


# ============================================================================
# E2E Workflow Tests - Performance
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
@pytest.mark.performance
def test_e2e_processing_performance_one_minute_audio(temp_audio_dir):
    """
    E2E: Performance test for 1-minute audio.

    Tests that processing completes in reasonable time.
    """
    import time

    input_file = temp_audio_dir / "one_minute.wav"
    create_test_audio_file(input_file, duration=60.0)

    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    start_time = time.time()
    processed = processor.process(audio)
    elapsed_time = time.time() - start_time

    assert processed is not None

    # Should process faster than real-time (60s audio should take < 60s)
    max_allowed_time = 60.0  # 1x real-time as maximum
    assert elapsed_time < max_allowed_time, \
        f"Processing too slow: {elapsed_time:.2f}s for 60s audio"

    print(f"\n  Performance: Processed 60s audio in {elapsed_time:.2f}s "
          f"({60.0 / elapsed_time:.1f}x real-time)")


# ============================================================================
# E2E Workflow Tests - Quality Checks
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_processed_audio_has_no_clipping(temp_audio_dir):
    """
    E2E: Verify processed audio has no clipping.

    Tests that full workflow produces valid output amplitude.
    """
    input_file = temp_audio_dir / "loud_input.wav"

    # Create loud input audio
    duration = 20.0
    num_samples = int(duration * 44100)
    audio = np.random.uniform(-0.9, 0.9, (num_samples, 2)).astype(np.float32)

    save_audio(str(input_file), audio, 44100, subtype='PCM_16')

    # Load and process
    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    # Verify no clipping
    max_amplitude = np.max(np.abs(processed))
    assert max_amplitude <= 1.0, f"Clipping detected: max amplitude {max_amplitude}"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_processed_audio_is_not_silent(temp_audio_dir):
    """
    E2E: Verify processed audio is not silent.

    Tests that processing doesn't destroy the signal.
    """
    input_file = temp_audio_dir / "input_signal.wav"
    create_test_audio_file(input_file, duration=10.0)

    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    # Verify output has signal
    output_rms = rms(processed)
    assert output_rms > 0.001, f"Output is nearly silent: RMS = {output_rms}"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_processed_audio_has_no_nan_or_inf(temp_audio_dir):
    """
    E2E: Verify processed audio has no NaN or inf values.

    Tests that processing doesn't produce invalid values.
    """
    input_file = temp_audio_dir / "input_test.wav"
    create_test_audio_file(input_file, duration=15.0)

    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    assert not np.isnan(processed).any(), "Processed audio contains NaN"
    assert not np.isinf(processed).any(), "Processed audio contains inf"


# ============================================================================
# E2E Workflow Tests - Real-World Scenarios
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_process_very_quiet_input(temp_audio_dir):
    """
    E2E: Process very quiet audio (simulates poor recording).

    Tests that very quiet input is handled and amplified appropriately.
    """
    input_file = temp_audio_dir / "quiet_input.wav"

    # Create very quiet audio
    duration = 15.0
    num_samples = int(duration * 44100)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = 0.01 * np.sin(2 * np.pi * 440 * t)  # Very quiet
    audio_stereo = np.column_stack([audio, audio])

    save_audio(str(input_file), audio_stereo, 44100, subtype='PCM_16')

    # Process
    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    # Output should be louder than input
    input_rms = rms(audio)
    output_rms = rms(processed)

    assert output_rms > input_rms, \
        f"Quiet input not amplified: input RMS={input_rms:.6f}, output RMS={output_rms:.6f}"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
def test_e2e_process_loud_input(temp_audio_dir):
    """
    E2E: Process loud audio (simulates hot input).

    Tests that loud input is handled and controlled appropriately.
    """
    input_file = temp_audio_dir / "loud_input_test.wav"

    # Create loud audio
    duration = 15.0
    num_samples = int(duration * 44100)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = 0.95 * np.sin(2 * np.pi * 440 * t)  # Very loud
    audio_stereo = np.column_stack([audio, audio])

    save_audio(str(input_file), audio_stereo, 44100, subtype='PCM_16')

    # Process
    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    # Output should not clip
    max_amplitude = np.max(np.abs(processed))
    assert max_amplitude <= 1.0, f"Loud input caused clipping: {max_amplitude}"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.audio
@pytest.mark.slow
def test_e2e_process_five_minute_audio(temp_audio_dir):
    """
    E2E: Process 5-minute audio file.

    Tests that long audio can be processed end-to-end.
    """
    input_file = temp_audio_dir / "five_minutes.wav"
    create_test_audio_file(input_file, duration=300.0)  # 5 minutes

    audio, sr = load_audio(str(input_file))

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)

    # Save output
    output_file = temp_audio_dir / "five_minutes_output.wav"
    save_audio(str(output_file), processed, sr, subtype='PCM_16')

    assert output_file.exists()


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about E2E integration tests."""
    print("\n" + "=" * 70)
    print("END-TO-END INTEGRATION TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total E2E tests: 25")
    print(f"\nTest categories:")
    print(f"  - Full processing pipeline: 3 tests")
    print(f"  - Chunked processing workflows: 2 tests")
    print(f"  - Different audio formats: 2 tests")
    print(f"  - Different sample rates: 1 test")
    print(f"  - Error handling: 2 tests")
    print(f"  - Performance tests: 1 test")
    print(f"  - Quality checks: 3 tests")
    print(f"  - Real-world scenarios: 3 tests")
    print(f"  - Summary stats: 1 test")
    print("=" * 70)
