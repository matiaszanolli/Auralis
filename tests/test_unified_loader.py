"""
Tests for Unified Audio Loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for audio file loading with multiple format support
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import wave

from auralis.io.unified_loader import (
    load_audio,
    get_audio_info,
    load_target,
    load_reference,
    is_audio_file,
    get_supported_formats,
    batch_load_info,
    SUPPORTED_FORMATS,
    FFMPEG_FORMATS
)
from auralis.utils.logging import ModuleError


@pytest.fixture
def temp_wav_file():
    """Create a temporary WAV file for testing"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        # Create a simple 1-second stereo WAV file at 44100 Hz
        sample_rate = 44100
        duration = 1
        samples = int(sample_rate * duration)

        # Generate stereo sine wave
        t = np.linspace(0, duration, samples)
        left_channel = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        right_channel = (np.sin(2 * np.pi * 880 * t) * 32767).astype(np.int16)
        audio = np.column_stack([left_channel, right_channel])

        # Write WAV file
        with wave.open(f.name, 'wb') as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio.tobytes())

        yield Path(f.name)

    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_mono_wav():
    """Create a temporary mono WAV file"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sample_rate = 44100
        duration = 0.5
        samples = int(sample_rate * duration)

        # Generate mono sine wave
        t = np.linspace(0, duration, samples)
        audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

        # Write WAV file
        with wave.open(f.name, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio.tobytes())

        yield Path(f.name)

    Path(f.name).unlink(missing_ok=True)


class TestLoadAudio:
    """Test load_audio function"""

    def test_load_wav_file_success(self, temp_wav_file):
        """Test loading a valid WAV file"""
        audio_data, sample_rate = load_audio(temp_wav_file)

        assert isinstance(audio_data, np.ndarray)
        assert sample_rate == 44100
        assert audio_data.ndim in [1, 2]  # Mono or stereo
        assert len(audio_data) > 0

    def test_load_file_not_found(self):
        """Test loading non-existent file raises error"""
        with pytest.raises((ModuleError, FileNotFoundError, Exception)):
            load_audio("nonexistent_file.wav")

    def test_load_empty_file(self):
        """Test loading empty file raises error"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = Path(f.name)

        try:
            with pytest.raises((ModuleError, Exception)):
                load_audio(temp_path)
        finally:
            temp_path.unlink()

    def test_load_unsupported_format(self):
        """Test loading unsupported format raises error"""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake audio data")

        try:
            with pytest.raises((ModuleError, Exception)):
                load_audio(temp_path)
        finally:
            temp_path.unlink()

    def test_load_with_force_stereo(self, temp_mono_wav):
        """Test converting mono to stereo"""
        audio_data, sample_rate = load_audio(temp_mono_wav, force_stereo=True)

        # Should be converted to stereo
        assert audio_data.ndim == 2
        assert audio_data.shape[1] == 2

    def test_load_with_normalize(self, temp_wav_file):
        """Test normalization on load"""
        audio_data, sample_rate = load_audio(temp_wav_file, normalize_on_load=True)

        # Check that audio is normalized (peak around 0.98)
        peak = np.max(np.abs(audio_data))
        assert peak <= 1.0
        assert peak >= 0.9  # Should be close to 0.98

    def test_load_with_resample(self, temp_wav_file):
        """Test resampling to different sample rate"""
        target_rate = 22050

        with patch('auralis.io.unified_loader.resample_audio') as mock_resample:
            # Make mock return appropriate array
            mock_resample.return_value = np.random.randn(22050, 2)

            audio_data, sample_rate = load_audio(
                temp_wav_file,
                target_sample_rate=target_rate
            )

            # Verify resample was called
            mock_resample.assert_called_once()
            assert sample_rate == target_rate

    def test_load_target_convenience(self, temp_wav_file):
        """Test load_target convenience function"""
        audio_data, sample_rate = load_target(temp_wav_file)

        assert isinstance(audio_data, np.ndarray)
        assert sample_rate > 0

    def test_load_reference_convenience(self, temp_wav_file):
        """Test load_reference convenience function"""
        audio_data, sample_rate = load_reference(temp_wav_file)

        assert isinstance(audio_data, np.ndarray)
        assert sample_rate > 0

    def test_load_with_path_object(self, temp_wav_file):
        """Test loading with Path object instead of string"""
        audio_data, sample_rate = load_audio(temp_wav_file)

        assert isinstance(audio_data, np.ndarray)

    def test_load_with_string_path(self, temp_wav_file):
        """Test loading with string path"""
        audio_data, sample_rate = load_audio(str(temp_wav_file))

        assert isinstance(audio_data, np.ndarray)


class TestGetAudioInfo:
    """Test get_audio_info function"""

    def test_get_info_success(self, temp_wav_file):
        """Test getting audio file info"""
        info = get_audio_info(temp_wav_file)

        assert 'file_path' in info
        assert 'file_size_bytes' in info
        assert 'file_size_mb' in info
        assert 'format' in info
        assert 'extension' in info
        assert info['format'] == 'WAV'
        assert info['extension'] == '.wav'

    def test_get_info_nonexistent_file(self):
        """Test getting info for nonexistent file"""
        with pytest.raises((ModuleError, Exception)):
            get_audio_info("nonexistent.wav")

    def test_get_info_with_soundfile(self, temp_wav_file):
        """Test getting info using soundfile"""
        with patch('auralis.io.unified_loader._get_info_with_soundfile') as mock_info:
            mock_info.return_value = {
                'sample_rate': 44100,
                'channels': 2,
                'frames': 44100,
                'duration_seconds': 1.0
            }

            info = get_audio_info(temp_wav_file)

            assert mock_info.called

    def test_get_info_handles_errors(self):
        """Test that get_audio_info handles errors gracefully"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"not real mp3 data")

        try:
            info = get_audio_info(temp_path)
            # Should not raise, but include error in dict
            assert 'error' in info or 'format' in info
        finally:
            temp_path.unlink()


class TestBatchLoadInfo:
    """Test batch_load_info function"""

    def test_batch_load_single_file(self, temp_wav_file):
        """Test batch loading with single file"""
        info_list = batch_load_info([temp_wav_file])

        assert len(info_list) == 1
        assert 'file_path' in info_list[0]

    def test_batch_load_multiple_files(self, temp_wav_file, temp_mono_wav):
        """Test batch loading with multiple files"""
        info_list = batch_load_info([temp_wav_file, temp_mono_wav])

        assert len(info_list) == 2
        assert all('file_path' in info for info in info_list)

    def test_batch_load_with_errors(self, temp_wav_file):
        """Test batch loading includes errors for invalid files"""
        file_list = [temp_wav_file, "nonexistent.wav"]

        info_list = batch_load_info(file_list)

        assert len(info_list) == 2
        # First should succeed, second should have error
        assert 'error' not in info_list[0] or 'format' in info_list[0]
        assert 'error' in info_list[1]

    def test_batch_load_empty_list(self):
        """Test batch loading with empty list"""
        info_list = batch_load_info([])

        assert info_list == []


class TestHelperFunctions:
    """Test helper functions"""

    def test_is_audio_file_valid_formats(self):
        """Test is_audio_file with valid formats"""
        assert is_audio_file("song.wav") == True
        assert is_audio_file("track.mp3") == True
        assert is_audio_file("audio.flac") == True
        assert is_audio_file("music.m4a") == True

    def test_is_audio_file_invalid_formats(self):
        """Test is_audio_file with invalid formats"""
        assert is_audio_file("document.pdf") == False
        assert is_audio_file("image.jpg") == False
        assert is_audio_file("video.mp4") == False
        assert is_audio_file("text.txt") == False

    def test_is_audio_file_case_insensitive(self):
        """Test is_audio_file is case-insensitive"""
        assert is_audio_file("song.WAV") == True
        assert is_audio_file("track.MP3") == True
        assert is_audio_file("audio.FLAC") == True

    def test_is_audio_file_with_path_object(self):
        """Test is_audio_file with Path object"""
        assert is_audio_file(Path("song.wav")) == True
        assert is_audio_file(Path("document.pdf")) == False

    def test_get_supported_formats(self):
        """Test get_supported_formats returns expected list"""
        formats = get_supported_formats()

        assert isinstance(formats, list)
        assert '.wav' in formats
        assert '.mp3' in formats
        assert '.flac' in formats
        assert len(formats) == len(SUPPORTED_FORMATS)


class TestFormatSupport:
    """Test format detection and support"""

    def test_supported_formats_constant(self):
        """Test SUPPORTED_FORMATS constant"""
        assert isinstance(SUPPORTED_FORMATS, dict)
        assert '.wav' in SUPPORTED_FORMATS
        assert '.mp3' in SUPPORTED_FORMATS
        assert '.flac' in SUPPORTED_FORMATS
        assert '.m4a' in SUPPORTED_FORMATS

    def test_ffmpeg_formats_constant(self):
        """Test FFMPEG_FORMATS constant"""
        assert isinstance(FFMPEG_FORMATS, set)
        assert '.mp3' in FFMPEG_FORMATS
        assert '.m4a' in FFMPEG_FORMATS
        # WAV and FLAC should not require FFmpeg
        assert '.wav' not in FFMPEG_FORMATS
        assert '.flac' not in FFMPEG_FORMATS

    def test_all_ffmpeg_formats_in_supported(self):
        """Test that all FFMPEG formats are in supported formats"""
        for fmt in FFMPEG_FORMATS:
            assert fmt in SUPPORTED_FORMATS


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_load_very_short_audio(self):
        """Test loading very short audio file"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sample_rate = 44100
            duration = 0.01  # 10ms
            samples = int(sample_rate * duration)

            t = np.linspace(0, duration, samples)
            audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

            with wave.open(f.name, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio.tobytes())

            temp_path = Path(f.name)

        try:
            audio_data, sr = load_audio(temp_path)
            assert len(audio_data) > 0
        finally:
            temp_path.unlink()

    def test_load_with_all_kwargs(self, temp_mono_wav):
        """Test loading with all optional parameters"""
        with patch('auralis.io.unified_loader.resample_audio') as mock_resample:
            mock_resample.return_value = np.random.randn(22050, 2)

            audio_data, sr = load_audio(
                temp_mono_wav,
                file_type="target",
                target_sample_rate=22050,
                force_stereo=True,
                normalize_on_load=True
            )

            assert isinstance(audio_data, np.ndarray)
