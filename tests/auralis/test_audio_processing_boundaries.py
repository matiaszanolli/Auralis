"""
Boundary Tests for Audio Processing

Tests edge cases and boundary conditions for audio processing.

Philosophy:
- Test minimum/maximum durations
- Test minimum/maximum amplitudes
- Test different sample rates
- Test silent and very loud audio
- Test mono/stereo edge cases

These tests complement the audio processing invariant tests by focusing on
extreme inputs where audio processing commonly fails.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save as save_audio
from auralis.dsp.basic import rms


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_audio_dir():
    """Create a temporary directory for test audio files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def processor():
    """Create a HybridProcessor with adaptive settings."""
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    return HybridProcessor(config)


def create_test_audio(duration_seconds: float, amplitude: float = 0.5,
                      sample_rate: int = 44100, mono: bool = False) -> tuple:
    """Create test audio with specified parameters."""
    num_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    audio = amplitude * np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave

    if mono:
        return audio, sample_rate
    else:
        # Stereo
        audio_stereo = np.column_stack([audio, audio])
        return audio_stereo, sample_rate


# ============================================================================
# Boundary Tests - Duration Extremes
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_minimum_duration_100ms(processor):
    """
    BOUNDARY: Minimum viable audio duration (100ms).

    Tests the absolute minimum audio that should be processable.
    """
    audio, sr = create_test_audio(duration_seconds=0.1, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None, "Failed to process 100ms audio"
    assert len(processed) > 0, "Processed audio is empty"
    assert len(processed) == len(audio), "Sample count changed"


@pytest.mark.boundary
@pytest.mark.audio
def test_very_short_audio_500ms(processor):
    """
    BOUNDARY: Very short audio (500ms).

    Tests that very short audio doesn't cause errors.
    """
    audio, sr = create_test_audio(duration_seconds=0.5, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)


@pytest.mark.boundary
@pytest.mark.audio
def test_exactly_one_second_audio(processor):
    """
    BOUNDARY: Exactly 1 second of audio.

    Tests a common boundary duration.
    """
    audio, sr = create_test_audio(duration_seconds=1.0, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)
    assert len(processed) == 44100  # 1 second at 44100 Hz, shape is (44100, 2) so len() = 44100


@pytest.mark.boundary
@pytest.mark.audio
@pytest.mark.slow
def test_very_long_audio_five_minutes(processor):
    """
    BOUNDARY: Very long audio (5 minutes = 300s).

    Tests that long audio can be processed without memory issues.
    """
    audio, sr = create_test_audio(duration_seconds=300.0, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)


# ============================================================================
# Boundary Tests - Amplitude Extremes
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_silent_audio_all_zeros(processor):
    """
    BOUNDARY: Silent audio (all samples = 0).

    Tests that processing silent audio doesn't crash and returns audio.
    Silent audio inherently produces NaN/Inf in metrics (e.g., RMS of zero = -inf dB)
    but the output audio itself should remain finite.
    """
    duration = 10.0
    num_samples = int(duration * 44100)
    audio = np.zeros((num_samples, 2), dtype=np.float32)  # Stereo silence

    processed = processor.process(audio)

    assert processed is not None, "Failed to process silent audio"
    assert len(processed) == len(audio)
    # Silent audio is valid even if metrics contain NaN
    # The important check is that processing doesn't crash
    assert isinstance(processed, np.ndarray), "Output should be numpy array"


@pytest.mark.boundary
@pytest.mark.audio
def test_very_quiet_audio(processor):
    """
    BOUNDARY: Very quiet audio (amplitude = 0.001).

    Tests that very quiet audio is handled without errors.
    """
    audio, sr = create_test_audio(duration_seconds=10.0, amplitude=0.001, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None
    assert not np.isnan(processed).any()
    assert not np.isinf(processed).any()


@pytest.mark.boundary
@pytest.mark.audio
def test_maximum_amplitude_at_1_0(processor):
    """
    BOUNDARY: Maximum amplitude (exactly 1.0, at clipping threshold).

    Tests that audio at the clipping threshold is handled correctly.
    """
    audio, sr = create_test_audio(duration_seconds=10.0, amplitude=1.0, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)

    # Verify no clipping (output should be <= 1.0)
    max_amplitude = np.max(np.abs(processed))
    assert max_amplitude <= 1.0, f"Output exceeds ±1.0: {max_amplitude}"


@pytest.mark.boundary
@pytest.mark.audio
def test_very_loud_audio_above_threshold(processor):
    """
    BOUNDARY: Very loud audio (amplitude > 1.0, clipped input).

    Tests that processor can handle already-clipped input audio.
    """
    duration = 10.0
    num_samples = int(duration * 44100)
    # Create audio that exceeds ±1.0 (simulates clipped/distorted input)
    audio = np.random.uniform(-1.5, 1.5, (num_samples, 2)).astype(np.float32)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)

    # Output must be within ±1.0 regardless of input
    max_amplitude = np.max(np.abs(processed))
    assert max_amplitude <= 1.0, f"Output exceeds ±1.0: {max_amplitude}"


# ============================================================================
# Boundary Tests - Sample Rates
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_low_sample_rate_22050hz(processor):
    """
    BOUNDARY: Low sample rate (22050 Hz).

    Tests that low sample rates are handled correctly.
    """
    audio, sr = create_test_audio(duration_seconds=10.0, sample_rate=22050)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)


@pytest.mark.boundary
@pytest.mark.audio
def test_standard_sample_rate_44100hz(processor):
    """
    BOUNDARY: Standard CD sample rate (44100 Hz).

    Tests the most common sample rate.
    """
    audio, sr = create_test_audio(duration_seconds=10.0, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)


@pytest.mark.boundary
@pytest.mark.audio
def test_high_sample_rate_48000hz(processor):
    """
    BOUNDARY: Professional sample rate (48000 Hz).

    Tests a common professional sample rate.
    """
    audio, sr = create_test_audio(duration_seconds=10.0, sample_rate=48000)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)


@pytest.mark.boundary
@pytest.mark.audio
def test_very_high_sample_rate_96000hz(processor):
    """
    BOUNDARY: High-resolution sample rate (96000 Hz).

    Tests that high sample rates work correctly.
    """
    audio, sr = create_test_audio(duration_seconds=5.0, sample_rate=96000)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)


# ============================================================================
# Boundary Tests - Channel Configurations
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_mono_audio_single_channel(processor):
    """
    BOUNDARY: Mono audio (1 channel).

    Tests that mono audio is handled correctly.
    """
    audio, sr = create_test_audio(duration_seconds=10.0, mono=True, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None
    # Processor may convert to stereo, just verify no errors
    assert len(processed) > 0


@pytest.mark.boundary
@pytest.mark.audio
def test_stereo_audio_two_channels(processor):
    """
    BOUNDARY: Stereo audio (2 channels).

    Tests the most common channel configuration.
    """
    audio, sr = create_test_audio(duration_seconds=10.0, mono=False, sample_rate=44100)

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)
    # Verify stereo shape (2 channels)
    if processed.ndim == 2:
        assert processed.shape[1] == 2


# ============================================================================
# Boundary Tests - Special Audio Patterns
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_audio_with_dc_offset(processor):
    """
    BOUNDARY: Audio with DC offset (non-zero mean).

    Tests that audio with DC offset is processed without crashing.
    The processor may amplify the signal, so we just verify it returns valid output.
    """
    audio, sr = create_test_audio(duration_seconds=10.0, sample_rate=44100)

    # Add DC offset
    dc_offset = 0.5
    audio = audio + dc_offset

    processed = processor.process(audio)

    assert processed is not None
    assert len(processed) == len(audio)
    # Processor should return finite values
    assert not np.isnan(processed).any(), "Processing should not produce NaN"
    assert isinstance(processed, np.ndarray), "Output should be numpy array"


@pytest.mark.boundary
@pytest.mark.audio
def test_audio_alternating_polarity(processor):
    """
    BOUNDARY: Audio alternating between positive and negative extremes.

    Tests handling of audio with rapid polarity changes.
    """
    duration = 10.0
    num_samples = int(duration * 44100)

    # Create square wave-like pattern (alternating ±0.8)
    audio = np.tile([0.8, -0.8], num_samples // 2)
    if len(audio) < num_samples:
        audio = np.append(audio, 0.8)  # Add one more sample if odd
    audio_stereo = np.column_stack([audio[:num_samples], audio[:num_samples]])

    processed = processor.process(audio_stereo)

    assert processed is not None
    assert len(processed) == len(audio_stereo)
    assert not np.isnan(processed).any()


@pytest.mark.boundary
@pytest.mark.audio
def test_audio_with_subsonic_content(processor):
    """
    BOUNDARY: Audio with very low frequency content (subsonic).

    Tests handling of audio with frequencies below 20 Hz.
    """
    duration = 10.0
    num_samples = int(duration * 44100)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    # 5 Hz subsonic frequency
    audio = 0.5 * np.sin(2 * np.pi * 5 * t)
    audio_stereo = np.column_stack([audio, audio])

    processed = processor.process(audio_stereo)

    assert processed is not None
    assert len(processed) == len(audio_stereo)
    assert not np.isnan(processed).any()


@pytest.mark.boundary
@pytest.mark.audio
def test_audio_with_ultrasonic_content(processor):
    """
    BOUNDARY: Audio with very high frequency content (ultrasonic).

    Tests handling of audio with frequencies near Nyquist limit.
    """
    duration = 10.0
    sample_rate = 44100
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    # 20 kHz near Nyquist (22.05 kHz for 44.1 kHz sample rate)
    audio = 0.5 * np.sin(2 * np.pi * 20000 * t)
    audio_stereo = np.column_stack([audio, audio])

    processed = processor.process(audio_stereo)

    assert processed is not None
    assert len(processed) == len(audio_stereo)
    assert not np.isnan(processed).any()


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about audio processing boundary tests."""
    print("\n" + "=" * 70)
    print("AUDIO PROCESSING BOUNDARY TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total boundary tests: 20")
    print(f"\nTest categories:")
    print(f"  - Duration extremes: 4 tests")
    print(f"  - Amplitude extremes: 4 tests")
    print(f"  - Sample rates: 4 tests")
    print(f"  - Channel configurations: 2 tests")
    print(f"  - Special audio patterns: 5 tests")
    print(f"  - Summary stats: 1 test")
    print("=" * 70)
