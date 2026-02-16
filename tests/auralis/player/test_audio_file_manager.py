#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AudioFileManager Unit Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive test suite for AudioFileManager covering:
- File loading (target and reference)
- Audio chunk extraction with boundary conditions
- Mono-to-stereo conversion
- Padding behavior
- State management and clearing

Issue: #2289
"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from auralis.player.audio_file_manager import AudioFileManager


class TestAudioFileManagerInitialization:
    """Test AudioFileManager initialization and default state."""

    def test_default_initialization(self):
        """Test default initialization with 44100 Hz sample rate."""
        manager = AudioFileManager()

        assert manager.sample_rate == 44100
        assert manager.audio_data is None
        assert manager.current_file is None
        assert manager.reference_data is None
        assert manager.reference_file is None
        assert not manager.is_loaded()
        assert not manager.has_reference()

    def test_custom_sample_rate(self):
        """Test initialization with custom sample rate."""
        manager = AudioFileManager(sample_rate=48000)

        assert manager.sample_rate == 48000
        assert manager.audio_data is None

    def test_initial_state_methods(self):
        """Test state query methods on uninitialized manager."""
        manager = AudioFileManager()

        assert manager.get_duration() == 0.0
        assert manager.get_total_samples() == 0
        assert manager.get_channel_count() == 0


class TestAudioFileLoading:
    """Test audio file loading functionality."""

    @pytest.fixture
    def audio_files(self, tmp_path):
        """Create test audio files with various characteristics."""
        sample_rate = 44100
        duration = 2.0
        samples = int(sample_rate * duration)

        files = {}

        # Stereo file
        t = np.linspace(0, duration, samples)
        stereo_audio = np.column_stack([
            0.3 * np.sin(2 * np.pi * 440 * t),  # Left: A4
            0.3 * np.sin(2 * np.pi * 523.25 * t)  # Right: C5
        ])
        stereo_path = tmp_path / "stereo.wav"
        sf.write(stereo_path, stereo_audio, sample_rate)
        files['stereo'] = str(stereo_path)

        # Mono file
        mono_audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        mono_path = tmp_path / "mono.wav"
        sf.write(mono_path, mono_audio, sample_rate)
        files['mono'] = str(mono_path)

        # Short file (0.5 seconds)
        short_samples = int(sample_rate * 0.5)
        short_t = np.linspace(0, 0.5, short_samples)
        short_audio = 0.3 * np.sin(2 * np.pi * 440 * short_t)
        short_path = tmp_path / "short.wav"
        sf.write(short_path, short_audio, sample_rate)
        files['short'] = str(short_path)

        # Different sample rate (48000 Hz)
        hires_sr = 48000
        hires_duration = 1.0
        hires_samples = int(hires_sr * hires_duration)
        hires_t = np.linspace(0, hires_duration, hires_samples)
        hires_audio = 0.3 * np.sin(2 * np.pi * 440 * hires_t)
        hires_path = tmp_path / "hires.wav"
        sf.write(hires_path, hires_audio, hires_sr)
        files['hires'] = str(hires_path)

        # Corrupt file (text file with .wav extension)
        corrupt_path = tmp_path / "corrupt.wav"
        corrupt_path.write_text("This is not an audio file")
        files['corrupt'] = str(corrupt_path)

        return files

    def test_load_valid_stereo_file(self, audio_files):
        """Test loading a valid stereo audio file."""
        manager = AudioFileManager()

        success = manager.load_file(audio_files['stereo'])

        assert success is True
        assert manager.is_loaded()
        assert manager.current_file == audio_files['stereo']
        assert manager.audio_data is not None
        assert manager.sample_rate == 44100
        assert manager.get_channel_count() == 2
        assert manager.get_duration() > 1.9  # ~2 seconds
        assert manager.get_total_samples() > 88000  # ~2s * 44100

    def test_load_valid_mono_file(self, audio_files):
        """Test loading a valid mono audio file.

        Note: Auralis loader automatically converts mono to stereo,
        so channel count will be 2 even for mono source files.
        """
        manager = AudioFileManager()

        success = manager.load_file(audio_files['mono'])

        assert success is True
        assert manager.is_loaded()
        assert manager.audio_data is not None
        # Auralis loader converts mono to stereo
        assert manager.get_channel_count() == 2

    def test_load_different_sample_rate(self, audio_files):
        """Test loading file with different sample rate updates manager state."""
        manager = AudioFileManager(sample_rate=44100)

        success = manager.load_file(audio_files['hires'])

        assert success is True
        # Sample rate should update to match loaded file
        assert manager.sample_rate == 48000
        assert manager.get_duration() > 0.9  # ~1 second

    def test_load_missing_file(self):
        """Test loading a non-existent file fails gracefully."""
        manager = AudioFileManager()

        success = manager.load_file("/nonexistent/path/to/audio.wav")

        assert success is False
        assert not manager.is_loaded()
        assert manager.audio_data is None
        assert manager.current_file is None

    def test_load_corrupt_file(self, audio_files):
        """Test loading a corrupt file fails gracefully."""
        manager = AudioFileManager()

        success = manager.load_file(audio_files['corrupt'])

        assert success is False
        assert not manager.is_loaded()
        assert manager.audio_data is None

    def test_load_file_updates_previous_state(self, audio_files):
        """Test loading a new file overwrites previous audio data."""
        manager = AudioFileManager()

        # Load first file
        manager.load_file(audio_files['stereo'])
        first_duration = manager.get_duration()

        # Load second file
        manager.load_file(audio_files['short'])
        second_duration = manager.get_duration()

        assert manager.current_file == audio_files['short']
        assert second_duration < first_duration


class TestReferenceFileLoading:
    """Test reference file loading functionality."""

    @pytest.fixture
    def reference_files(self, tmp_path):
        """Create test reference audio files."""
        sample_rate = 44100
        duration = 3.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        files = {}

        # Valid reference
        ref_audio = np.column_stack([
            0.5 * np.sin(2 * np.pi * 880 * t),  # A5
            0.5 * np.sin(2 * np.pi * 987.77 * t)  # B5
        ])
        ref_path = tmp_path / "reference.wav"
        sf.write(ref_path, ref_audio, sample_rate)
        files['valid'] = str(ref_path)

        # Corrupt reference
        corrupt_path = tmp_path / "corrupt_ref.wav"
        corrupt_path.write_text("Not audio")
        files['corrupt'] = str(corrupt_path)

        return files

    def test_load_valid_reference(self, reference_files):
        """Test loading a valid reference file."""
        manager = AudioFileManager()

        success = manager.load_reference(reference_files['valid'])

        assert success is True
        assert manager.has_reference()
        assert manager.reference_file == reference_files['valid']
        assert manager.reference_data is not None

    def test_load_missing_reference(self):
        """Test loading a non-existent reference file fails gracefully."""
        manager = AudioFileManager()

        success = manager.load_reference("/nonexistent/reference.wav")

        assert success is False
        assert not manager.has_reference()
        assert manager.reference_data is None
        assert manager.reference_file is None

    def test_load_corrupt_reference(self, reference_files):
        """Test loading a corrupt reference file fails gracefully."""
        manager = AudioFileManager()

        success = manager.load_reference(reference_files['corrupt'])

        assert success is False
        assert not manager.has_reference()

    def test_reference_independent_from_target(self, tmp_path):
        """Test that reference and target audio are managed independently."""
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        # Create target
        target_audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        target_path = tmp_path / "target.wav"
        sf.write(target_path, target_audio, sample_rate)

        # Create reference
        ref_audio = 0.5 * np.sin(2 * np.pi * 880 * t)
        ref_path = tmp_path / "reference.wav"
        sf.write(ref_path, ref_audio, sample_rate)

        manager = AudioFileManager()

        # Load both
        manager.load_file(str(target_path))
        manager.load_reference(str(ref_path))

        assert manager.is_loaded()
        assert manager.has_reference()
        assert manager.current_file == str(target_path)
        assert manager.reference_file == str(ref_path)
        # They should be different data
        assert not np.array_equal(manager.audio_data, manager.reference_data)


class TestAudioChunkExtraction:
    """Test get_audio_chunk() with various boundary conditions."""

    @pytest.fixture
    def manager_with_stereo_audio(self, tmp_path):
        """Create manager with loaded stereo audio."""
        sample_rate = 44100
        duration = 2.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = np.column_stack([
            0.3 * np.sin(2 * np.pi * 440 * t),
            0.3 * np.sin(2 * np.pi * 523.25 * t)
        ])

        path = tmp_path / "test.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        manager.load_file(str(path))
        return manager

    @pytest.fixture
    def manager_with_mono_audio(self, tmp_path):
        """Create manager with loaded mono audio."""
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)

        path = tmp_path / "mono.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        manager.load_file(str(path))
        return manager

    def test_get_chunk_no_audio_loaded(self):
        """Test getting chunk when no audio is loaded returns zeros."""
        manager = AudioFileManager()

        chunk = manager.get_audio_chunk(start_position=0, chunk_size=1024)

        assert chunk.shape == (1024, 2)
        assert chunk.dtype == np.float32
        assert np.allclose(chunk, 0.0)

    def test_get_normal_chunk(self, manager_with_stereo_audio):
        """Test extracting a normal chunk from middle of audio."""
        chunk_size = 1024
        start_pos = 10000

        chunk = manager_with_stereo_audio.get_audio_chunk(start_pos, chunk_size)

        assert chunk.shape == (chunk_size, 2)
        assert chunk.dtype == np.float32
        # Should not be all zeros
        assert not np.allclose(chunk, 0.0)

    def test_get_chunk_at_start(self, manager_with_stereo_audio):
        """Test extracting chunk from the start of audio."""
        chunk_size = 512

        chunk = manager_with_stereo_audio.get_audio_chunk(0, chunk_size)

        assert chunk.shape == (chunk_size, 2)
        assert chunk.dtype == np.float32

    def test_get_chunk_at_end_with_padding(self, manager_with_stereo_audio):
        """Test extracting chunk that extends beyond audio end (requires padding)."""
        total_samples = manager_with_stereo_audio.get_total_samples()
        chunk_size = 2048
        # Start near the end so chunk extends beyond
        start_pos = total_samples - 1000

        chunk = manager_with_stereo_audio.get_audio_chunk(start_pos, chunk_size)

        # Should still return full chunk size
        assert chunk.shape == (chunk_size, 2)
        # First part should have signal, last part should be zeros (padding)
        assert not np.allclose(chunk[:1000], 0.0)  # Has signal
        assert np.allclose(chunk[1000:], 0.0)  # Padded with zeros

    def test_get_chunk_beyond_audio_end(self, manager_with_stereo_audio):
        """Test extracting chunk starting beyond audio end returns all zeros."""
        total_samples = manager_with_stereo_audio.get_total_samples()
        chunk_size = 1024

        chunk = manager_with_stereo_audio.get_audio_chunk(total_samples + 1000, chunk_size)

        assert chunk.shape == (chunk_size, 2)
        assert np.allclose(chunk, 0.0)

    def test_mono_to_stereo_conversion(self, manager_with_mono_audio):
        """Test that mono audio is converted to stereo in chunk extraction."""
        chunk_size = 1024

        chunk = manager_with_mono_audio.get_audio_chunk(0, chunk_size)

        # Should return stereo even though source is mono
        assert chunk.shape == (chunk_size, 2)
        # Both channels should be identical (duplicated mono)
        assert np.allclose(chunk[:, 0], chunk[:, 1])

    def test_single_channel_stereo_conversion(self, tmp_path):
        """Test conversion of shape (n, 1) audio to stereo."""
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        # Create audio with shape (n, 1)
        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        audio = audio.reshape(-1, 1)  # Force (n, 1) shape

        path = tmp_path / "single_channel.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        manager.load_file(str(path))

        chunk = manager.get_audio_chunk(0, 1024)

        # Should return stereo
        assert chunk.shape == (1024, 2)
        # Both channels should be identical
        assert np.allclose(chunk[:, 0], chunk[:, 1])

    def test_chunk_is_copy_not_view(self, manager_with_stereo_audio):
        """Test that returned chunk is a copy, not a view of original data."""
        chunk = manager_with_stereo_audio.get_audio_chunk(0, 1024)
        original_chunk = chunk.copy()

        # Modify chunk
        chunk[:] = 0.0

        # Get same chunk again
        chunk2 = manager_with_stereo_audio.get_audio_chunk(0, 1024)

        # Should match original, not modified version
        assert np.allclose(chunk2, original_chunk)
        assert not np.allclose(chunk2, chunk)

    def test_large_chunk_extraction(self, manager_with_stereo_audio):
        """Test extracting a very large chunk."""
        total_samples = manager_with_stereo_audio.get_total_samples()
        chunk_size = total_samples * 2  # Request twice the audio length

        chunk = manager_with_stereo_audio.get_audio_chunk(0, chunk_size)

        # Should return full requested size with padding
        assert chunk.shape == (chunk_size, 2)
        # First half should have signal
        assert not np.allclose(chunk[:total_samples], 0.0)
        # Second half should be zeros
        assert np.allclose(chunk[total_samples:], 0.0)


class TestStateManagement:
    """Test state query and management methods."""

    def test_get_duration_no_audio(self):
        """Test get_duration returns 0 when no audio loaded."""
        manager = AudioFileManager()
        assert manager.get_duration() == 0.0

    def test_get_duration_with_audio(self, tmp_path):
        """Test get_duration calculates correct duration."""
        sample_rate = 44100
        duration = 2.5
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        path = tmp_path / "test.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        manager.load_file(str(path))

        calculated_duration = manager.get_duration()
        assert abs(calculated_duration - duration) < 0.01  # Within 10ms

    def test_get_total_samples_no_audio(self):
        """Test get_total_samples returns 0 when no audio loaded."""
        manager = AudioFileManager()
        assert manager.get_total_samples() == 0

    def test_get_total_samples_with_audio(self, tmp_path):
        """Test get_total_samples returns correct count."""
        sample_rate = 44100
        duration = 1.0
        expected_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, expected_samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        path = tmp_path / "test.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        manager.load_file(str(path))

        assert manager.get_total_samples() == expected_samples

    def test_get_channel_count_variations(self, tmp_path):
        """Test get_channel_count for mono and stereo.

        Note: Auralis loader automatically converts all audio to stereo,
        so both mono and stereo source files result in channel_count=2.
        """
        sample_rate = 44100
        duration = 0.5
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        # Mono
        mono_audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        mono_path = tmp_path / "mono.wav"
        sf.write(mono_path, mono_audio, sample_rate)

        # Stereo
        stereo_audio = np.column_stack([
            0.3 * np.sin(2 * np.pi * 440 * t),
            0.3 * np.sin(2 * np.pi * 523.25 * t)
        ])
        stereo_path = tmp_path / "stereo.wav"
        sf.write(stereo_path, stereo_audio, sample_rate)

        manager = AudioFileManager()

        # Test no audio
        assert manager.get_channel_count() == 0

        # Test mono (Auralis loader converts to stereo)
        manager.load_file(str(mono_path))
        assert manager.get_channel_count() == 2

        # Test stereo
        manager.load_file(str(stereo_path))
        assert manager.get_channel_count() == 2

    def test_is_loaded_state_transitions(self, tmp_path):
        """Test is_loaded() state transitions."""
        sample_rate = 44100
        duration = 0.5
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        path = tmp_path / "test.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()

        # Initially not loaded
        assert not manager.is_loaded()

        # After loading
        manager.load_file(str(path))
        assert manager.is_loaded()

        # After clearing
        manager.clear_audio()
        assert not manager.is_loaded()

    def test_has_reference_state_transitions(self, tmp_path):
        """Test has_reference() state transitions."""
        sample_rate = 44100
        duration = 0.5
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        path = tmp_path / "ref.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()

        # Initially no reference
        assert not manager.has_reference()

        # After loading reference
        manager.load_reference(str(path))
        assert manager.has_reference()

        # After clearing
        manager.clear_reference()
        assert not manager.has_reference()


class TestClearMethods:
    """Test audio data clearing functionality."""

    @pytest.fixture
    def loaded_manager(self, tmp_path):
        """Create manager with both target and reference loaded."""
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        # Target audio
        target_audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        target_path = tmp_path / "target.wav"
        sf.write(target_path, target_audio, sample_rate)

        # Reference audio
        ref_audio = 0.5 * np.sin(2 * np.pi * 880 * t)
        ref_path = tmp_path / "reference.wav"
        sf.write(ref_path, ref_audio, sample_rate)

        manager = AudioFileManager()
        manager.load_file(str(target_path))
        manager.load_reference(str(ref_path))

        return manager

    def test_clear_audio(self, loaded_manager):
        """Test clear_audio() clears only target audio."""
        loaded_manager.clear_audio()

        # Target should be cleared
        assert loaded_manager.audio_data is None
        assert loaded_manager.current_file is None
        assert not loaded_manager.is_loaded()

        # Reference should remain
        assert loaded_manager.reference_data is not None
        assert loaded_manager.reference_file is not None
        assert loaded_manager.has_reference()

    def test_clear_reference(self, loaded_manager):
        """Test clear_reference() clears only reference audio."""
        loaded_manager.clear_reference()

        # Reference should be cleared
        assert loaded_manager.reference_data is None
        assert loaded_manager.reference_file is None
        assert not loaded_manager.has_reference()

        # Target should remain
        assert loaded_manager.audio_data is not None
        assert loaded_manager.current_file is not None
        assert loaded_manager.is_loaded()

    def test_clear_all(self, loaded_manager):
        """Test clear_all() clears both target and reference."""
        loaded_manager.clear_all()

        # Both should be cleared
        assert loaded_manager.audio_data is None
        assert loaded_manager.current_file is None
        assert not loaded_manager.is_loaded()

        assert loaded_manager.reference_data is None
        assert loaded_manager.reference_file is None
        assert not loaded_manager.has_reference()

    def test_clear_when_already_empty(self):
        """Test clearing when nothing is loaded doesn't error."""
        manager = AudioFileManager()

        # Should not raise
        manager.clear_audio()
        manager.clear_reference()
        manager.clear_all()

        assert not manager.is_loaded()
        assert not manager.has_reference()

    def test_state_after_clear_audio(self, loaded_manager):
        """Test that helper methods return correct values after clearing."""
        loaded_manager.clear_audio()

        assert loaded_manager.get_duration() == 0.0
        assert loaded_manager.get_total_samples() == 0
        assert loaded_manager.get_channel_count() == 0

        # get_audio_chunk should return zeros
        chunk = loaded_manager.get_audio_chunk(0, 1024)
        assert chunk.shape == (1024, 2)
        assert np.allclose(chunk, 0.0)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_chunk_size(self, tmp_path):
        """Test requesting chunk with size 0."""
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        path = tmp_path / "test.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        manager.load_file(str(path))

        chunk = manager.get_audio_chunk(0, 0)

        assert chunk.shape == (0, 2)

    def test_negative_start_position(self, tmp_path):
        """Test behavior with negative start position."""
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        path = tmp_path / "test.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        manager.load_file(str(path))

        # NumPy slicing with negative indices should work
        # -1000:chunk_size would give unexpected results but shouldn't crash
        chunk = manager.get_audio_chunk(-1000, 1024)

        # Should return some chunk (exact behavior depends on numpy slicing)
        assert chunk.shape[1] == 2

    def test_very_short_audio_file(self, tmp_path):
        """Test with extremely short audio (< 1 second)."""
        sample_rate = 44100
        duration = 0.01  # 10 milliseconds
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        path = tmp_path / "very_short.wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        success = manager.load_file(str(path))

        assert success is True
        assert manager.get_total_samples() == samples
        assert manager.get_duration() > 0.0

        # Request chunk larger than file
        chunk = manager.get_audio_chunk(0, 44100)  # Request 1 second
        assert chunk.shape == (44100, 2)
        # Should be mostly padding
        assert np.allclose(chunk[samples:], 0.0)

    def test_file_path_with_special_characters(self, tmp_path):
        """Test loading file with special characters in path."""
        sample_rate = 44100
        duration = 0.5
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        # Path with spaces and special chars
        special_dir = tmp_path / "test dir (special)"
        special_dir.mkdir()
        path = special_dir / "audio file [test].wav"
        sf.write(path, audio, sample_rate)

        manager = AudioFileManager()
        success = manager.load_file(str(path))

        assert success is True
        assert manager.is_loaded()
        assert manager.current_file == str(path)
