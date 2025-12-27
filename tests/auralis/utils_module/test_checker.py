# -*- coding: utf-8 -*-

"""
Tests for Audio Checker
~~~~~~~~~~~~~~~~~~~~~~~~

Tests the audio validation and checking utilities

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from auralis.utils.checker import (
    check,
    check_equality,
    check_file_permissions,
    is_audio_file,
)
from auralis.utils.logging import Code, ModuleError


@pytest.fixture
def sample_audio():
    """Create sample audio data"""
    sample_rate = 44100
    duration = 1.0
    samples = int(sample_rate * duration)

    t = np.linspace(0, duration, samples)
    audio = np.column_stack([
        np.sin(2 * np.pi * 440 * t),
        np.sin(2 * np.pi * 554.37 * t)
    ]).astype(np.float32)

    return audio, sample_rate


@pytest.fixture
def mock_config():
    """Create a mock configuration object"""
    class MockConfig:
        internal_sample_rate = 44100
    return MockConfig()


# ===== check() Function Tests =====

def test_check_basic(sample_audio, mock_config):
    """Test basic audio checking"""
    audio, sr = sample_audio

    result_audio, result_sr = check(audio, sr, mock_config)

    assert result_sr == sr
    assert result_audio.shape == audio.shape
    assert np.array_equal(result_audio, audio)


def test_check_mono_audio(mock_config):
    """Test checking mono audio"""
    sr = 44100
    audio = np.random.randn(sr).astype(np.float32)

    result_audio, result_sr = check(audio, sr, mock_config)

    assert result_sr == sr
    assert result_audio.shape == audio.shape


def test_check_different_sample_rates(sample_audio, mock_config):
    """Test checking audio with different sample rates"""
    audio, _ = sample_audio

    for sr in [22050, 44100, 48000, 96000]:
        result_audio, result_sr = check(audio, sr, mock_config)
        assert result_sr == sr


def test_check_custom_file_type(sample_audio, mock_config):
    """Test checking with custom file type"""
    audio, sr = sample_audio

    # Should accept custom file_type parameter
    result_audio, result_sr = check(audio, sr, mock_config, file_type="target")

    assert result_sr == sr
    assert np.array_equal(result_audio, audio)


# ===== check_equality() Function Tests =====

def test_check_equality_different_arrays():
    """Test equality check with different arrays"""
    target = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    reference = np.array([1.1, 2.1, 3.1], dtype=np.float32)

    # Should not raise exception
    check_equality(target, reference)


def test_check_equality_identical_arrays():
    """Test equality check with identical arrays"""
    audio = np.array([1.0, 2.0, 3.0], dtype=np.float32)

    with pytest.raises(ModuleError) as exc_info:
        check_equality(audio, audio)

    assert exc_info.value.code == Code.ERROR_VALIDATION


def test_check_equality_similar_not_identical():
    """Test equality check with similar but not identical arrays"""
    target = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    reference = np.array([1.0, 2.0, 3.001], dtype=np.float32)

    # Should not raise (not exactly equal)
    check_equality(target, reference)


def test_check_equality_different_shapes():
    """Test equality check with different shapes"""
    target = np.array([[1.0, 2.0]], dtype=np.float32)
    reference = np.array([1.0, 2.0], dtype=np.float32)

    # Should not raise (different shapes)
    check_equality(target, reference)


# ===== is_audio_file() Function Tests =====

def test_is_audio_file_wav():
    """Test WAV file detection"""
    assert is_audio_file("test.wav") is True
    assert is_audio_file("TEST.WAV") is True
    assert is_audio_file("/path/to/file.wav") is True


def test_is_audio_file_flac():
    """Test FLAC file detection"""
    assert is_audio_file("test.flac") is True
    assert is_audio_file("test.FLAC") is True


def test_is_audio_file_mp3():
    """Test MP3 file detection"""
    assert is_audio_file("test.mp3") is True
    assert is_audio_file("test.MP3") is True


def test_is_audio_file_various_formats():
    """Test detection of various audio formats"""
    audio_files = [
        "test.aiff", "test.aif", "test.m4a", "test.ogg",
        "test.wma", "test.opus", "test.ac3", "test.dts"
    ]

    for filename in audio_files:
        assert is_audio_file(filename) is True


def test_is_audio_file_non_audio():
    """Test non-audio file detection"""
    non_audio_files = [
        "test.txt", "test.pdf", "test.jpg", "test.png",
        "test.doc", "test.exe", "test.zip"
    ]

    for filename in non_audio_files:
        assert is_audio_file(filename) is False


def test_is_audio_file_no_extension():
    """Test file with no extension"""
    assert is_audio_file("testfile") is False


def test_is_audio_file_empty_string():
    """Test empty filename"""
    assert is_audio_file("") is False


def test_is_audio_file_case_insensitive():
    """Test case insensitive extension matching"""
    assert is_audio_file("test.WaV") is True
    assert is_audio_file("test.FlAc") is True
    assert is_audio_file("test.Mp3") is True


# ===== check_file_permissions() Function Tests =====

def test_check_file_permissions_readable_file(tmp_path):
    """Test checking permissions on readable file"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    assert check_file_permissions(str(test_file)) is True


def test_check_file_permissions_nonexistent_file():
    """Test checking permissions on nonexistent file"""
    assert check_file_permissions("/nonexistent/path/file.txt") is False


def test_check_file_permissions_directory(tmp_path):
    """Test checking permissions on directory (not a file)"""
    assert check_file_permissions(str(tmp_path)) is False


def test_check_file_permissions_empty_path():
    """Test checking permissions on empty path"""
    assert check_file_permissions("") is False


# ===== Integration Tests =====

def test_full_validation_workflow(sample_audio, mock_config):
    """Test complete validation workflow"""
    audio, sr = sample_audio

    # Check audio
    checked_audio, checked_sr = check(audio, sr, mock_config)

    # Verify it's not equal to a different array
    different_audio = audio * 0.5
    check_equality(checked_audio, different_audio)

    # Verify checks passed
    assert checked_sr == sr
    assert checked_audio.shape == audio.shape


def test_file_validation_workflow(tmp_path):
    """Test file validation workflow"""
    # Create test file
    test_file = tmp_path / "test.wav"
    test_file.write_text("fake audio data")

    filepath = str(test_file)

    # Check if it's an audio file (by extension)
    assert is_audio_file(filepath) is True

    # Check if it's readable
    assert check_file_permissions(filepath) is True


# ===== Edge Cases =====

def test_check_empty_audio(mock_config):
    """Test checking empty audio array"""
    audio = np.array([], dtype=np.float32)
    sr = 44100

    # Should handle empty array
    result_audio, result_sr = check(audio, sr, mock_config)
    assert result_sr == sr


def test_check_very_large_audio(mock_config):
    """Test checking very large audio"""
    sr = 44100
    duration = 600  # 10 minutes
    samples = int(sr * duration)
    audio = np.random.randn(samples, 2).astype(np.float32)

    result_audio, result_sr = check(audio, sr, mock_config)
    assert result_sr == sr
    assert result_audio.shape == audio.shape


def test_check_equality_empty_arrays():
    """Test equality check with empty arrays"""
    target = np.array([], dtype=np.float32)
    reference = np.array([], dtype=np.float32)

    # Empty arrays are equal, should raise
    with pytest.raises(ModuleError):
        check_equality(target, reference)


def test_is_audio_file_multiple_dots():
    """Test filename with multiple dots"""
    assert is_audio_file("my.song.name.wav") is True
    assert is_audio_file("backup.2024.mp3") is True


def test_is_audio_file_hidden_files():
    """Test hidden files (Unix-style)"""
    assert is_audio_file(".hidden.wav") is True
    assert is_audio_file(".config") is False
