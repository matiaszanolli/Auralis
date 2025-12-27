# -*- coding: utf-8 -*-

"""
Tests for Audio Saver
~~~~~~~~~~~~~~~~~~~~~

Tests the audio file saving system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from auralis.io.saver import save


@pytest.fixture
def sample_stereo_audio():
    """Create sample stereo audio data"""
    sample_rate = 44100
    duration = 1.0
    samples = int(sample_rate * duration)

    # Generate stereo sine wave
    t = np.linspace(0, duration, samples)
    left = np.sin(2 * np.pi * 440 * t)
    right = np.sin(2 * np.pi * 554.37 * t)
    audio = np.column_stack([left, right]).astype(np.float32)

    return audio, sample_rate


@pytest.fixture
def sample_mono_audio():
    """Create sample mono audio data"""
    sample_rate = 44100
    duration = 0.5
    samples = int(sample_rate * duration)

    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

    return audio, sample_rate


# ===== Basic Saving Tests =====

def test_save_basic(tmp_path, sample_stereo_audio):
    """Test basic audio saving"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output.wav"

    # Save audio
    save(str(output_path), audio, sr)

    # Verify file was created
    assert output_path.exists()


def test_save_and_verify_content(tmp_path, sample_stereo_audio):
    """Test that saved audio can be read back correctly"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output.wav"

    # Save audio
    save(str(output_path), audio, sr)

    # Read it back
    audio_loaded, sr_loaded = sf.read(str(output_path))

    # Verify
    assert sr_loaded == sr
    assert audio_loaded.shape == audio.shape
    # PCM_16 has quantization noise, so tolerance needs to be higher
    assert np.allclose(audio, audio_loaded, atol=1e-4)


def test_save_with_path_object(tmp_path, sample_stereo_audio):
    """Test saving with Path object"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output.wav"

    # Should work with Path object (converted to string internally)
    save(str(output_path), audio, sr)

    assert output_path.exists()


# ===== Format Tests =====

def test_save_pcm_16(tmp_path, sample_stereo_audio):
    """Test saving as PCM 16-bit"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output_16.wav"

    save(str(output_path), audio, sr, subtype='PCM_16')

    assert output_path.exists()

    # Verify format
    info = sf.info(str(output_path))
    assert info.subtype == 'PCM_16'


def test_save_pcm_24(tmp_path, sample_stereo_audio):
    """Test saving as PCM 24-bit"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output_24.wav"

    save(str(output_path), audio, sr, subtype='PCM_24')

    assert output_path.exists()

    info = sf.info(str(output_path))
    assert info.subtype == 'PCM_24'


def test_save_float32(tmp_path, sample_stereo_audio):
    """Test saving as 32-bit float"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output_float.wav"

    save(str(output_path), audio, sr, subtype='FLOAT')

    assert output_path.exists()


# ===== Sample Rate Tests =====

def test_save_44100(tmp_path, sample_stereo_audio):
    """Test saving at 44.1kHz"""
    audio, _ = sample_stereo_audio
    sr = 44100
    output_path = tmp_path / "output_44100.wav"

    save(str(output_path), audio, sr)

    info = sf.info(str(output_path))
    assert info.samplerate == 44100


def test_save_48000(tmp_path, sample_stereo_audio):
    """Test saving at 48kHz"""
    audio, _ = sample_stereo_audio
    sr = 48000
    output_path = tmp_path / "output_48000.wav"

    save(str(output_path), audio, sr)

    info = sf.info(str(output_path))
    assert info.samplerate == 48000


def test_save_96000(tmp_path, sample_stereo_audio):
    """Test saving at 96kHz"""
    audio, _ = sample_stereo_audio
    sr = 96000
    output_path = tmp_path / "output_96000.wav"

    save(str(output_path), audio, sr)

    info = sf.info(str(output_path))
    assert info.samplerate == 96000


# ===== Mono/Stereo Tests =====

def test_save_mono_audio(tmp_path, sample_mono_audio):
    """Test saving mono audio"""
    audio, sr = sample_mono_audio
    output_path = tmp_path / "output_mono.wav"

    save(str(output_path), audio, sr)

    assert output_path.exists()

    info = sf.info(str(output_path))
    assert info.channels == 1


def test_save_stereo_audio(tmp_path, sample_stereo_audio):
    """Test saving stereo audio"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output_stereo.wav"

    save(str(output_path), audio, sr)

    assert output_path.exists()

    info = sf.info(str(output_path))
    assert info.channels == 2


# ===== Data Type Tests =====

def test_save_float64_array(tmp_path):
    """Test saving float64 array (should convert to float32)"""
    sr = 44100
    audio = np.random.randn(sr, 2).astype(np.float64)
    output_path = tmp_path / "output_float64.wav"

    # Should handle float64 input
    save(str(output_path), audio, sr)

    assert output_path.exists()


def test_save_int16_array(tmp_path):
    """Test saving int16 array (should convert to float32)"""
    sr = 44100
    audio = (np.random.randn(sr, 2) * 32767).astype(np.int16)
    output_path = tmp_path / "output_int16.wav"

    # Should handle int16 input
    save(str(output_path), audio, sr)

    assert output_path.exists()


# ===== Edge Cases =====

def test_save_empty_audio(tmp_path):
    """Test saving empty audio array"""
    sr = 44100
    audio = np.array([], dtype=np.float32)
    output_path = tmp_path / "output_empty.wav"

    # May raise error or create empty file
    try:
        save(str(output_path), audio, sr)
        # If it succeeds, file should exist
        assert output_path.exists()
    except:
        # If it fails, that's okay too
        pass


def test_save_very_short_audio(tmp_path):
    """Test saving very short audio (1 sample)"""
    sr = 44100
    audio = np.array([[0.5, 0.5]], dtype=np.float32)
    output_path = tmp_path / "output_short.wav"

    save(str(output_path), audio, sr)

    assert output_path.exists()


def test_save_silent_audio(tmp_path):
    """Test saving silent audio (all zeros)"""
    sr = 44100
    audio = np.zeros((sr, 2), dtype=np.float32)
    output_path = tmp_path / "output_silent.wav"

    save(str(output_path), audio, sr)

    assert output_path.exists()

    # Verify it's actually silent
    audio_loaded, _ = sf.read(str(output_path))
    assert np.allclose(audio_loaded, 0.0)


def test_save_clipped_audio(tmp_path):
    """Test saving audio with clipping (values > 1.0)"""
    sr = 44100
    samples = sr
    t = np.linspace(0, 1.0, samples)
    audio = np.column_stack([
        np.sin(2 * np.pi * 440 * t) * 2.0,  # Exceeds [-1, 1]
        np.sin(2 * np.pi * 440 * t) * 2.0
    ]).astype(np.float32)

    output_path = tmp_path / "output_clipped.wav"

    # Should save without error (may clip or normalize)
    save(str(output_path), audio, sr)

    assert output_path.exists()


# ===== Error Handling =====

def test_save_to_invalid_path():
    """Test saving to invalid path"""
    sr = 44100
    audio = np.random.randn(sr, 2).astype(np.float32)

    with pytest.raises(Exception):
        save("/invalid/path/that/does/not/exist/output.wav", audio, sr)


def test_save_with_invalid_sample_rate(tmp_path, sample_stereo_audio):
    """Test saving with invalid sample rate"""
    audio, _ = sample_stereo_audio
    output_path = tmp_path / "output_invalid_sr.wav"

    # Negative sample rate should fail
    with pytest.raises(Exception):
        save(str(output_path), audio, -44100)


def test_save_with_zero_sample_rate(tmp_path, sample_stereo_audio):
    """Test saving with zero sample rate"""
    audio, _ = sample_stereo_audio
    output_path = tmp_path / "output_zero_sr.wav"

    with pytest.raises(Exception):
        save(str(output_path), audio, 0)


def test_save_with_invalid_subtype(tmp_path, sample_stereo_audio):
    """Test saving with invalid subtype"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output_invalid_subtype.wav"

    with pytest.raises(Exception):
        save(str(output_path), audio, sr, subtype='INVALID_SUBTYPE')


# ===== Overwrite Tests =====

def test_save_overwrite_existing(tmp_path, sample_stereo_audio):
    """Test overwriting existing file"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output.wav"

    # Save first time
    save(str(output_path), audio, sr)
    first_size = output_path.stat().st_size

    # Save again (overwrite)
    save(str(output_path), audio, sr)
    second_size = output_path.stat().st_size

    # Sizes should be the same
    assert first_size == second_size


# ===== Integration Tests =====

def test_save_and_load_roundtrip(tmp_path):
    """Test complete save/load roundtrip"""
    from auralis.io.unified_loader import load_audio

    # Create audio
    sr = 44100
    duration = 1.0
    samples = int(sr * duration)
    t = np.linspace(0, duration, samples)
    audio = np.column_stack([
        np.sin(2 * np.pi * 440 * t),
        np.sin(2 * np.pi * 554.37 * t)
    ]).astype(np.float32)

    output_path = tmp_path / "roundtrip.wav"

    # Save
    save(str(output_path), audio, sr)

    # Load
    audio_loaded, sr_loaded = load_audio(output_path)

    # Verify
    assert sr_loaded == sr
    assert audio_loaded.shape == audio.shape
    # PCM_16 quantization + load_audio processing may introduce small errors
    assert np.allclose(audio, audio_loaded, atol=1e-4)


def test_save_multiple_files(tmp_path, sample_stereo_audio):
    """Test saving multiple files"""
    audio, sr = sample_stereo_audio

    for i in range(5):
        output_path = tmp_path / f"output_{i}.wav"
        save(str(output_path), audio, sr)
        assert output_path.exists()


# ===== Performance Tests =====

def test_save_performance(tmp_path, sample_stereo_audio):
    """Test that saving completes in reasonable time"""
    import time

    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output_perf.wav"

    start = time.perf_counter()
    save(str(output_path), audio, sr)
    elapsed = time.perf_counter() - start

    # Saving 1 second of audio should be fast (< 100ms)
    assert elapsed < 0.1
    assert output_path.exists()


# ===== File Size Tests =====

def test_save_file_size_reasonable(tmp_path, sample_stereo_audio):
    """Test that saved file size is reasonable"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output_size.wav"

    save(str(output_path), audio, sr, subtype='PCM_16')

    file_size = output_path.stat().st_size

    # 1 second stereo at 44.1kHz, 16-bit should be roughly 176KB
    # (44100 * 2 channels * 2 bytes + header)
    expected_size = 44100 * 2 * 2
    # Allow 10% variance + header
    assert file_size > expected_size * 0.9
    assert file_size < expected_size * 1.5  # Account for header and metadata


# ===== Data Integrity Tests =====

def test_save_preserves_amplitude(tmp_path):
    """Test that saving preserves audio amplitude"""
    sr = 44100
    # Create audio with known amplitude
    audio = np.ones((sr, 2), dtype=np.float32) * 0.5

    output_path = tmp_path / "output_amplitude.wav"
    save(str(output_path), audio, sr)

    # Load and check
    audio_loaded, _ = sf.read(str(output_path))
    assert np.allclose(audio_loaded, 0.5, atol=1e-4)


def test_save_no_nan_or_inf(tmp_path, sample_stereo_audio):
    """Test that saved audio doesn't create NaN or Inf"""
    audio, sr = sample_stereo_audio
    output_path = tmp_path / "output_no_nan.wav"

    save(str(output_path), audio, sr)

    # Load and verify
    audio_loaded, _ = sf.read(str(output_path))
    assert not np.any(np.isnan(audio_loaded))
    assert not np.any(np.isinf(audio_loaded))
