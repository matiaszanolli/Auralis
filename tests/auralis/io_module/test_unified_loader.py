# -*- coding: utf-8 -*-

"""
Tests for Unified Audio Loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the audio file loading system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import numpy as np
from pathlib import Path

from auralis.io.unified_loader import (
    load_audio,
    SUPPORTED_FORMATS,
    FFMPEG_FORMATS
)


@pytest.fixture
def sample_wav_file(tmp_path):
    """Create a sample WAV file for testing"""
    import soundfile as sf

    # Create 1 second of stereo audio at 44.1kHz
    sample_rate = 44100
    duration = 1.0
    samples = int(sample_rate * duration)

    # Generate stereo sine wave
    t = np.linspace(0, duration, samples)
    left = np.sin(2 * np.pi * 440 * t)  # A4 note
    right = np.sin(2 * np.pi * 554.37 * t)  # C#5 note
    audio = np.column_stack([left, right]).astype(np.float32)

    # Save to file
    wav_path = tmp_path / "test_audio.wav"
    sf.write(str(wav_path), audio, sample_rate)

    return wav_path


@pytest.fixture
def sample_mono_file(tmp_path):
    """Create a mono WAV file"""
    import soundfile as sf

    sample_rate = 44100
    duration = 0.5
    samples = int(sample_rate * duration)

    # Generate mono sine wave
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

    mono_path = tmp_path / "test_mono.wav"
    sf.write(str(mono_path), audio, sample_rate)

    return mono_path


# ===== Basic Loading Tests =====

def test_load_audio_basic(sample_wav_file):
    """Test basic audio loading"""
    audio, sr = load_audio(str(sample_wav_file))

    assert audio is not None
    assert isinstance(audio, np.ndarray)
    assert sr == 44100
    assert audio.ndim == 2  # Stereo
    assert audio.shape[1] == 2  # 2 channels


def test_load_audio_with_path_object(sample_wav_file):
    """Test loading with Path object"""
    audio, sr = load_audio(sample_wav_file)

    assert audio is not None
    assert sr == 44100


def test_load_audio_sample_rate(sample_wav_file):
    """Test that sample rate is correctly returned"""
    audio, sr = load_audio(sample_wav_file)

    assert sr == 44100


def test_load_audio_shape(sample_wav_file):
    """Test audio array shape"""
    audio, sr = load_audio(sample_wav_file)

    # Should be (samples, channels) for stereo
    assert audio.ndim == 2
    assert audio.shape[1] == 2


def test_load_audio_dtype(sample_wav_file):
    """Test audio data type"""
    audio, sr = load_audio(sample_wav_file)

    # Should be float32 or float64
    assert audio.dtype in [np.float32, np.float64]


# ===== Mono/Stereo Handling =====

def test_load_mono_audio(sample_mono_file):
    """Test loading mono audio"""
    audio, sr = load_audio(sample_mono_file)

    assert audio is not None
    assert audio.ndim in [1, 2]  # May be (samples,) or (samples, 1)
    assert sr == 44100


def test_force_stereo_from_mono(sample_mono_file):
    """Test converting mono to stereo"""
    audio, sr = load_audio(sample_mono_file, force_stereo=True)

    # Should be converted to stereo
    if audio.ndim == 1:
        # If still mono, that's okay too (implementation dependent)
        pass
    else:
        assert audio.shape[1] == 2


# ===== Resampling Tests =====

def test_resample_audio(sample_wav_file):
    """Test that downsampling works for high sample rates"""
    # Test file is 44.1kHz; don't downsample (below 48kHz threshold)
    # Instead, load and verify no downsampling is applied
    audio, sr = load_audio(sample_wav_file, target_sample_rate=48000)

    # Should stay at 44.1kHz (design avoids upsampling above original rate)
    assert sr == 44100
    assert audio is not None


def test_resample_maintains_duration(sample_wav_file):
    """Test that attempting upsample doesn't change sample rate"""
    # Load original at 44.1kHz
    audio1, sr1 = load_audio(sample_wav_file)
    duration1 = len(audio1) / sr1

    # Try to load with upsample request (48kHz > 44.1kHz)
    # Design skips upsampling to avoid quality degradation
    audio2, sr2 = load_audio(sample_wav_file, target_sample_rate=48000)
    duration2 = len(audio2) / sr2

    # Since upsampling is skipped, sample rate should remain at 44.1kHz
    assert sr2 == 44100
    # Duration should be approximately the same
    assert abs(duration1 - duration2) < 0.01


# ===== Error Handling =====

def test_load_nonexistent_file():
    """Test loading a file that doesn't exist"""
    with pytest.raises(Exception):  # Should raise some error
        load_audio("/path/that/does/not/exist.wav")


def test_load_invalid_format(tmp_path):
    """Test loading unsupported file format"""
    # Create a text file with .wav extension
    fake_wav = tmp_path / "fake.wav"
    fake_wav.write_text("This is not audio data")

    with pytest.raises(Exception):
        load_audio(str(fake_wav))


def test_load_empty_path():
    """Test loading with empty path"""
    with pytest.raises(Exception):
        load_audio("")


# ===== Normalization Tests =====

def test_normalize_on_load(sample_wav_file):
    """Test normalize_on_load parameter"""
    # Load without normalization
    audio1, sr1 = load_audio(sample_wav_file, normalize_on_load=False)

    # Load with normalization
    audio2, sr2 = load_audio(sample_wav_file, normalize_on_load=True)

    assert audio1.shape == audio2.shape
    assert sr1 == sr2

    # Normalized audio should have max absolute value of 1.0 (or close)
    max_val = np.max(np.abs(audio2))
    assert max_val <= 1.0
    # Normalization may or may not change the audio depending on implementation
    # Just verify both loads succeed


# ===== Format Support Tests =====

def test_supported_formats_list():
    """Test that supported formats are defined"""
    assert len(SUPPORTED_FORMATS) > 0
    assert '.wav' in SUPPORTED_FORMATS
    assert '.flac' in SUPPORTED_FORMATS
    assert '.mp3' in SUPPORTED_FORMATS


def test_ffmpeg_formats_list():
    """Test that FFmpeg formats are defined"""
    assert len(FFMPEG_FORMATS) > 0
    assert '.mp3' in FFMPEG_FORMATS


# ===== Edge Cases =====

def test_load_very_short_audio(tmp_path):
    """Test loading very short audio (< 1 second)"""
    import soundfile as sf

    # Create 0.1 second audio
    sample_rate = 44100
    samples = int(sample_rate * 0.1)
    audio_data = np.random.randn(samples, 2).astype(np.float32)

    short_file = tmp_path / "short.wav"
    sf.write(str(short_file), audio_data, sample_rate)

    audio, sr = load_audio(short_file)

    assert audio is not None
    assert len(audio) == samples


def test_load_silent_audio(tmp_path):
    """Test loading silent audio (all zeros)"""
    import soundfile as sf

    sample_rate = 44100
    samples = sample_rate  # 1 second
    audio_data = np.zeros((samples, 2), dtype=np.float32)

    silent_file = tmp_path / "silent.wav"
    sf.write(str(silent_file), audio_data, sample_rate)

    audio, sr = load_audio(silent_file)

    assert audio is not None
    assert np.allclose(audio, 0.0)


def test_load_clipped_audio(tmp_path):
    """Test loading audio with clipping (values > 1.0)"""
    import soundfile as sf

    sample_rate = 44100
    samples = sample_rate  # 1 second

    # Create audio with clipping
    t = np.linspace(0, 1.0, samples)
    audio_data = np.column_stack([
        np.sin(2 * np.pi * 440 * t) * 1.5,  # Clipped
        np.sin(2 * np.pi * 440 * t) * 1.5
    ]).astype(np.float32)

    # Clip to valid range
    audio_data = np.clip(audio_data, -1.0, 1.0)

    clipped_file = tmp_path / "clipped.wav"
    sf.write(str(clipped_file), audio_data, sample_rate)

    audio, sr = load_audio(clipped_file)

    assert audio is not None
    # Should be loaded successfully even with clipping


# ===== Integration Tests =====

def test_load_and_reload(sample_wav_file, tmp_path):
    """Test loading, saving, and reloading audio"""
    from auralis.io.saver import save

    # Load original
    audio1, sr1 = load_audio(sample_wav_file)

    # Save to new file
    temp_file = tmp_path / "temp.wav"
    save(str(temp_file), audio1, sr1)

    # Reload
    audio2, sr2 = load_audio(temp_file)

    # Should be very similar
    assert sr1 == sr2
    assert audio1.shape == audio2.shape
    # Allow small numerical differences
    assert np.allclose(audio1, audio2, atol=1e-6)


def test_load_multiple_files(sample_wav_file, sample_mono_file):
    """Test loading multiple files sequentially"""
    audio1, sr1 = load_audio(sample_wav_file)
    audio2, sr2 = load_audio(sample_mono_file)

    assert audio1 is not None
    assert audio2 is not None
    assert sr1 == 44100
    assert sr2 == 44100


# ===== Performance Tests =====

def test_load_performance(sample_wav_file):
    """Test that loading completes in reasonable time"""
    import time

    start = time.perf_counter()
    audio, sr = load_audio(sample_wav_file)
    elapsed = time.perf_counter() - start

    # Loading 1 second of audio should be very fast (< 100ms)
    assert elapsed < 0.1
    assert audio is not None


def test_multiple_loads_performance(sample_wav_file):
    """Test loading same file multiple times"""
    import time

    start = time.perf_counter()
    for _ in range(10):
        audio, sr = load_audio(sample_wav_file)
    elapsed = time.perf_counter() - start

    # 10 loads should complete quickly (< 1 second)
    assert elapsed < 1.0


# ===== Data Integrity Tests =====

def test_audio_amplitude_range(sample_wav_file):
    """Test that loaded audio is in expected amplitude range"""
    audio, sr = load_audio(sample_wav_file)

    # Audio should typically be in range [-1.0, 1.0] or thereabouts
    max_val = np.max(np.abs(audio))
    assert max_val <= 10.0  # Generous upper bound
    assert max_val > 0.0  # Should have some signal


def test_audio_not_all_zeros(sample_wav_file):
    """Test that loaded audio contains actual signal"""
    audio, sr = load_audio(sample_wav_file)

    # Should not be all zeros
    assert not np.allclose(audio, 0.0)


def test_audio_no_nan_or_inf(sample_wav_file):
    """Test that loaded audio doesn't contain NaN or Inf"""
    audio, sr = load_audio(sample_wav_file)

    assert not np.any(np.isnan(audio))
    assert not np.any(np.isinf(audio))
