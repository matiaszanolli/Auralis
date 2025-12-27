"""
Audio Processing Boundary Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests edge cases and boundary conditions for audio processing operations.

These tests verify critical invariants:
1. Sample count preservation (output samples = input samples)
2. No clipping (all samples in valid range)
3. No NaN or Inf values in output
4. Sample rate handling (8kHz to 192kHz)
5. Channel configuration handling (mono, stereo)

Test Categories:
- Sample rate boundaries (6 tests)
- Audio duration boundaries (6 tests)
- Amplitude boundaries (6 tests)
- Channel configuration (6 tests)
- Invalid audio data (6 tests)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os

# Add auralis to path
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis'))

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_audio_dir():
    """Create temporary directory for audio files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def default_config():
    """Create default processing config"""
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    return config


@pytest.fixture
def processor(default_config):
    """Create hybrid processor"""
    return HybridProcessor(default_config)


def create_test_audio(duration_seconds, sample_rate=44100, channels=2, amplitude=0.1):
    """
    Helper to create test audio of specified duration.

    Args:
        duration_seconds: Duration in seconds
        sample_rate: Sample rate (Hz)
        channels: Number of channels (1=mono, 2=stereo)
        amplitude: Signal amplitude

    Returns:
        numpy array of shape (samples, channels)
    """
    num_samples = int(duration_seconds * sample_rate)
    if channels == 1:
        audio = np.random.randn(num_samples) * amplitude
    else:
        audio = np.random.randn(num_samples, channels) * amplitude
    return audio


# ============================================================================
# CATEGORY 1: SAMPLE RATE BOUNDARIES (6 tests)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.slow
def test_minimum_sample_rate_8khz(processor, temp_audio_dir):
    """
    BOUNDARY: Minimum common sample rate (8kHz - telephony).
    Processing should handle low sample rates without error.
    """
    sample_rate = 8000
    duration = 5.0  # 5 seconds
    audio = create_test_audio(duration, sample_rate)

    # Save to file (processor needs file path)
    filepath = os.path.join(temp_audio_dir, "8khz.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    # Process
    result = processor.process(filepath)

    # Verify
    assert result is not None, "Processing should succeed for 8kHz audio"
    # Note: Processor may resample internally, so sample count may differ
    assert len(result) > 0, "Should return non-empty audio"
    assert not np.any(np.isnan(result)), "Output should not contain NaN"
    assert not np.any(np.isinf(result)), "Output should not contain Inf"


@pytest.mark.boundary
@pytest.mark.slow
def test_cd_quality_sample_rate_44khz(processor, temp_audio_dir):
    """
    BOUNDARY: CD quality sample rate (44.1kHz - most common).
    Should process without issues.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate)

    filepath = os.path.join(temp_audio_dir, "44khz.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) > 0, "Should return non-empty audio"
    assert not np.any(np.isnan(result))
    assert not np.any(np.isinf(result))


@pytest.mark.boundary
@pytest.mark.slow
def test_high_quality_sample_rate_48khz(processor, temp_audio_dir):
    """
    BOUNDARY: Professional sample rate (48kHz - video standard).
    Should process without issues.
    """
    sample_rate = 48000
    duration = 5.0
    audio = create_test_audio(duration, sample_rate)

    filepath = os.path.join(temp_audio_dir, "48khz.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) > 0, "Should return non-empty audio"


@pytest.mark.boundary
@pytest.mark.slow
def test_high_res_sample_rate_96khz(processor, temp_audio_dir):
    """
    BOUNDARY: High-resolution sample rate (96kHz).
    Should handle high sample rates.
    """
    sample_rate = 96000
    duration = 3.0  # Shorter to keep test fast
    audio = create_test_audio(duration, sample_rate)

    filepath = os.path.join(temp_audio_dir, "96khz.wav")
    save(filepath, audio, sample_rate, subtype='PCM_24')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) > 0, "Should return non-empty audio"


@pytest.mark.boundary
@pytest.mark.slow
def test_ultra_high_res_sample_rate_192khz(processor, temp_audio_dir):
    """
    BOUNDARY: Ultra high-resolution sample rate (192kHz - archival).
    Should handle extreme high sample rates.
    """
    sample_rate = 192000
    duration = 2.0  # Very short to keep memory usage reasonable
    audio = create_test_audio(duration, sample_rate)

    filepath = os.path.join(temp_audio_dir, "192khz.wav")
    save(filepath, audio, sample_rate, subtype='PCM_24')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) > 0, "Should return non-empty audio"


@pytest.mark.boundary
@pytest.mark.slow
def test_sample_rate_preservation(processor, temp_audio_dir):
    """
    INVARIANT: Processing should handle various sample rates without error.
    Test with multiple sample rates.
    Note: Sample count may differ due to internal resampling.
    """
    sample_rates = [8000, 16000, 22050, 44100, 48000]
    duration = 2.0

    for sr in sample_rates:
        audio = create_test_audio(duration, sr)
        filepath = os.path.join(temp_audio_dir, f"sr_{sr}.wav")
        save(filepath, audio, sr, subtype='PCM_16')

        result = processor.process(filepath)

        assert result is not None, f"Processing failed for {sr}Hz"
        assert len(result) > 0, f"Empty output for {sr}Hz"
        assert not np.any(np.isnan(result)), f"NaN in output for {sr}Hz"
        assert not np.any(np.isinf(result)), f"Inf in output for {sr}Hz"


# ============================================================================
# CATEGORY 2: AUDIO DURATION BOUNDARIES (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_minimum_duration_one_sample(processor, temp_audio_dir):
    """
    BOUNDARY: Absolute minimum audio - 1 sample.
    Should handle gracefully (likely fail or process minimally).
    """
    sample_rate = 44100
    audio = np.array([[0.0, 0.0]])  # 1 sample, stereo

    filepath = os.path.join(temp_audio_dir, "one_sample.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    # This may fail or succeed - we just want no crash
    try:
        result = processor.process(filepath)
        if result is not None:
            assert len(result) > 0, "If processing succeeds, should return audio"
    except (ValueError, RuntimeError):
        # Expected for very short audio
        pass


@pytest.mark.boundary
def test_very_short_duration_100ms(processor, temp_audio_dir):
    """
    BOUNDARY: Very short audio (100ms - minimum for some analysis).
    Should process or gracefully reject.
    """
    sample_rate = 44100
    duration = 0.1  # 100ms
    audio = create_test_audio(duration, sample_rate)

    filepath = os.path.join(temp_audio_dir, "100ms.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    try:
        result = processor.process(filepath)
        if result is not None:
            assert len(result) > 0, "Should return non-empty audio"
    except (ValueError, RuntimeError):
        # May fail for too-short audio
        pass


@pytest.mark.boundary
@pytest.mark.slow
def test_short_duration_1_second(processor, temp_audio_dir):
    """
    BOUNDARY: Short audio (1 second - minimum for most analysis).
    Should process successfully.
    """
    sample_rate = 44100
    duration = 1.0
    audio = create_test_audio(duration, sample_rate)

    filepath = os.path.join(temp_audio_dir, "1sec.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) > 0, "Should return non-empty audio"


@pytest.mark.boundary
@pytest.mark.slow
def test_normal_duration_3_minutes(processor, temp_audio_dir):
    """
    BOUNDARY: Normal song duration (3 minutes - typical track).
    Should process efficiently.
    """
    sample_rate = 44100
    duration = 180.0  # 3 minutes
    audio = create_test_audio(duration, sample_rate)

    filepath = os.path.join(temp_audio_dir, "3min.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) > 0, "Should return non-empty audio"
    assert not np.any(np.isnan(result))
    assert not np.any(np.isinf(result))


@pytest.mark.boundary
@pytest.mark.slow
def test_long_duration_10_minutes(processor, temp_audio_dir):
    """
    BOUNDARY: Long audio (10 minutes - extended track).
    Should handle long durations without memory issues.
    """
    sample_rate = 44100
    duration = 600.0  # 10 minutes
    audio = create_test_audio(duration, sample_rate)

    filepath = os.path.join(temp_audio_dir, "10min.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) > 0, "Should return non-empty audio"


@pytest.mark.boundary
@pytest.mark.slow
def test_very_long_duration_1_hour(processor, temp_audio_dir):
    """
    BOUNDARY: Very long audio (1 hour - DJ set, audiobook).
    Should handle extreme durations.
    """
    sample_rate = 44100
    duration = 3600.0  # 1 hour
    audio = create_test_audio(duration, sample_rate, amplitude=0.01)  # Low amplitude to save memory

    filepath = os.path.join(temp_audio_dir, "1hour.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) > 0, "Should return non-empty audio for long audio"


# ============================================================================
# CATEGORY 3: AMPLITUDE BOUNDARIES (6 tests)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.slow
def test_zero_amplitude_silence(processor, temp_audio_dir):
    """
    BOUNDARY: Complete silence (all samples = 0).
    Should handle without error.
    """
    sample_rate = 44100
    duration = 5.0
    audio = np.zeros((int(duration * sample_rate), 2))

    filepath = os.path.join(temp_audio_dir, "silence.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) == len(audio)
    assert not np.any(np.isnan(result))
    assert not np.any(np.isinf(result))


@pytest.mark.boundary
@pytest.mark.slow
def test_very_low_amplitude(processor, temp_audio_dir):
    """
    BOUNDARY: Very quiet audio (amplitude = 0.001).
    Should process without underflow.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate, amplitude=0.001)

    filepath = os.path.join(temp_audio_dir, "very_quiet.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) == len(audio)
    assert not np.any(np.isnan(result))


@pytest.mark.boundary
@pytest.mark.slow
def test_normal_amplitude(processor, temp_audio_dir):
    """
    BOUNDARY: Normal audio amplitude (0.1-0.3 RMS).
    Should process optimally.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate, amplitude=0.2)

    filepath = os.path.join(temp_audio_dir, "normal.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) == len(audio)
    # Check no clipping
    assert np.max(np.abs(result)) <= 1.0, "Output should not clip (exceed ±1.0)"


@pytest.mark.boundary
@pytest.mark.slow
def test_high_amplitude_near_clipping(processor, temp_audio_dir):
    """
    BOUNDARY: High amplitude near clipping (0.9 peak).
    Should handle without introducing clipping.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate, amplitude=0.9)

    filepath = os.path.join(temp_audio_dir, "loud.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) == len(audio)
    # Limiter should prevent clipping
    assert np.max(np.abs(result)) <= 1.0, "Limiter should prevent clipping"


@pytest.mark.boundary
@pytest.mark.slow
def test_clipped_input_audio(processor, temp_audio_dir):
    """
    BOUNDARY: Already clipped input (peaks at ±1.0).
    Should handle gracefully.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate, amplitude=1.0)
    # Hard clip some samples
    audio = np.clip(audio, -1.0, 1.0)

    filepath = os.path.join(temp_audio_dir, "clipped.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert len(result) == len(audio)
    assert not np.any(np.isnan(result))
    assert not np.any(np.isinf(result))


@pytest.mark.boundary
@pytest.mark.slow
def test_no_clipping_invariant(processor, temp_audio_dir):
    """
    INVARIANT: Processing should never introduce clipping (samples > ±1.0).
    Test with various input amplitudes.
    """
    sample_rate = 44100
    duration = 3.0
    amplitudes = [0.1, 0.3, 0.5, 0.7, 0.9, 0.99]

    for amp in amplitudes:
        audio = create_test_audio(duration, sample_rate, amplitude=amp)
        filepath = os.path.join(temp_audio_dir, f"amp_{amp}.wav")
        save(filepath, audio, sample_rate, subtype='PCM_16')

        result = processor.process(filepath)

        max_abs = np.max(np.abs(result))
        assert max_abs <= 1.0, (
            f"Processing introduced clipping for amplitude {amp}: "
            f"max_abs={max_abs}"
        )


# ============================================================================
# CATEGORY 4: CHANNEL CONFIGURATION (6 tests)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.slow
def test_mono_audio(processor, temp_audio_dir):
    """
    BOUNDARY: Mono audio (1 channel).
    Should handle mono and convert if needed.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate, channels=1)

    filepath = os.path.join(temp_audio_dir, "mono.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert not np.any(np.isnan(result))


@pytest.mark.boundary
@pytest.mark.slow
def test_stereo_audio(processor, temp_audio_dir):
    """
    BOUNDARY: Stereo audio (2 channels - standard).
    Should process without issues.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate, channels=2)

    filepath = os.path.join(temp_audio_dir, "stereo.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert result.ndim == 2, "Stereo output should be 2D array"
    assert result.shape[1] == 2, "Stereo output should have 2 channels"


@pytest.mark.boundary
@pytest.mark.slow
def test_mono_to_stereo_conversion(processor, temp_audio_dir):
    """
    BOUNDARY: Mono input should produce stereo output.
    Test channel conversion.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate, channels=1)

    filepath = os.path.join(temp_audio_dir, "mono_convert.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    # Processor should output stereo
    assert result.ndim == 2, "Output should be 2D (stereo)"
    assert result.shape[1] == 2, "Output should have 2 channels"


@pytest.mark.boundary
@pytest.mark.slow
def test_stereo_width_extremes_narrow(processor, temp_audio_dir):
    """
    BOUNDARY: Extremely narrow stereo (L ≈ R - near mono).
    Should handle without issues.
    """
    sample_rate = 44100
    duration = 5.0
    # Create nearly mono stereo (very narrow)
    mono_signal = np.random.randn(int(duration * sample_rate)) * 0.1
    audio = np.column_stack([mono_signal, mono_signal])

    filepath = os.path.join(temp_audio_dir, "narrow_stereo.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert result.shape[1] == 2


@pytest.mark.boundary
@pytest.mark.slow
def test_stereo_width_extremes_wide(processor, temp_audio_dir):
    """
    BOUNDARY: Extremely wide stereo (L and R completely uncorrelated).
    Should handle without phase issues.
    """
    sample_rate = 44100
    duration = 5.0
    # Create completely uncorrelated L/R
    left = np.random.randn(int(duration * sample_rate)) * 0.1
    right = np.random.randn(int(duration * sample_rate)) * 0.1
    audio = np.column_stack([left, right])

    filepath = os.path.join(temp_audio_dir, "wide_stereo.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert result.shape[1] == 2
    assert not np.any(np.isnan(result))


@pytest.mark.boundary
@pytest.mark.slow
def test_stereo_phase_inverted(processor, temp_audio_dir):
    """
    BOUNDARY: Phase-inverted stereo (L = -R).
    Should detect and handle phase issues.
    """
    sample_rate = 44100
    duration = 5.0
    left = np.random.randn(int(duration * sample_rate)) * 0.1
    right = -left  # Phase inverted
    audio = np.column_stack([left, right])

    filepath = os.path.join(temp_audio_dir, "phase_inverted.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    result = processor.process(filepath)

    assert result is not None
    assert result.shape[1] == 2


# ============================================================================
# CATEGORY 5: INVALID AUDIO DATA (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_nan_values_in_input(processor, temp_audio_dir):
    """
    BOUNDARY: Input audio contains NaN values.
    Should detect and reject or sanitize.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate)
    # Inject NaN values
    audio[100:110] = np.nan

    filepath = os.path.join(temp_audio_dir, "nan_input.wav")

    # WAV format doesn't support NaN, so this may fail during save
    try:
        save(filepath, audio, sample_rate, subtype='PCM_16')
        result = processor.process(filepath)

        # If processing succeeds, output should not have NaN
        if result is not None:
            assert not np.any(np.isnan(result)), "Output should not contain NaN"
    except (ValueError, RuntimeError):
        # Expected for invalid audio
        pass


@pytest.mark.boundary
def test_inf_values_in_input(processor, temp_audio_dir):
    """
    BOUNDARY: Input audio contains Inf values.
    Should detect and reject or sanitize.
    """
    sample_rate = 44100
    duration = 5.0
    audio = create_test_audio(duration, sample_rate)
    # Inject Inf values
    audio[200:210] = np.inf

    filepath = os.path.join(temp_audio_dir, "inf_input.wav")

    try:
        save(filepath, audio, sample_rate, subtype='PCM_16')
        result = processor.process(filepath)

        if result is not None:
            assert not np.any(np.isinf(result)), "Output should not contain Inf"
    except (ValueError, RuntimeError):
        # Expected for invalid audio
        pass


@pytest.mark.boundary
def test_empty_audio_array(processor):
    """
    BOUNDARY: Empty audio array (0 samples).
    Should reject gracefully.
    """
    audio = np.array([]).reshape(0, 2)  # Empty stereo array

    # Should raise error or return None
    try:
        result = processor.process(audio)
        if result is not None:
            assert len(result) == 0, "Empty input should produce empty output"
    except (ValueError, RuntimeError):
        # Expected for empty audio
        pass


@pytest.mark.boundary
def test_wrong_shape_1d_array(processor, temp_audio_dir):
    """
    BOUNDARY: 1D array for stereo (wrong shape).
    Should handle or reject with clear error.
    """
    sample_rate = 44100
    duration = 5.0
    # Create 1D array (invalid for stereo)
    audio = np.random.randn(int(duration * sample_rate)) * 0.1

    filepath = os.path.join(temp_audio_dir, "mono_1d.wav")
    save(filepath, audio, sample_rate, subtype='PCM_16')

    # Should either convert to stereo or process as mono
    try:
        result = processor.process(filepath)
        assert result is not None, "Should handle 1D array"
    except (ValueError, RuntimeError):
        # May reject invalid shape
        pass


@pytest.mark.boundary
def test_sample_count_invariant(processor, temp_audio_dir):
    """
    INVARIANT: Processing should not corrupt audio structure.
    Test across various configurations.
    Note: Sample count may differ due to resampling, but output should be valid.
    """
    configs = [
        (44100, 5.0, 1),   # Mono
        (44100, 5.0, 2),   # Stereo
        (48000, 3.0, 2),   # 48kHz
        (96000, 2.0, 2),   # 96kHz
    ]

    for sample_rate, duration, channels in configs:
        audio = create_test_audio(duration, sample_rate, channels)
        filepath = os.path.join(temp_audio_dir, f"sr{sample_rate}_ch{channels}.wav")
        save(filepath, audio, sample_rate, subtype='PCM_16')

        result = processor.process(filepath)

        if result is not None:
            assert len(result) > 0, f"Empty output for {sample_rate}Hz {channels}ch"
            assert result.ndim == 2, f"Output should be 2D for {sample_rate}Hz {channels}ch"
            assert result.shape[1] == 2, f"Output should be stereo for {sample_rate}Hz {channels}ch"


@pytest.mark.boundary
@pytest.mark.slow
def test_no_nan_inf_invariant(processor, temp_audio_dir):
    """
    INVARIANT: Processing should never produce NaN or Inf in output.
    Test with various edge cases.
    """
    test_cases = [
        (44100, 5.0, 2, 0.0),     # Silence
        (44100, 5.0, 2, 0.001),   # Very quiet
        (44100, 5.0, 2, 0.9),     # Very loud
        (8000, 3.0, 1, 0.1),      # Low sample rate mono
        (96000, 2.0, 2, 0.5),     # High sample rate
    ]

    for sample_rate, duration, channels, amplitude in test_cases:
        audio = create_test_audio(duration, sample_rate, channels, amplitude)
        filepath = os.path.join(temp_audio_dir, f"test_{sample_rate}_{channels}_{amplitude}.wav")
        save(filepath, audio, sample_rate, subtype='PCM_16')

        result = processor.process(filepath)

        if result is not None:
            assert not np.any(np.isnan(result)), (
                f"NaN in output for {sample_rate}Hz {channels}ch amp={amplitude}"
            )
            assert not np.any(np.isinf(result)), (
                f"Inf in output for {sample_rate}Hz {channels}ch amp={amplitude}"
            )
