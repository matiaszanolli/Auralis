#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified Loader Coverage Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for the unified loader to improve coverage
"""

import numpy as np
import tempfile
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

from auralis.io.unified_loader import UnifiedAudioLoader, AudioInfo, LoaderError
import soundfile as sf

class TestUnifiedAudioLoader:
    """Test the UnifiedAudioLoader class"""

    def setUp(self):
        """Set up test fixtures"""
        self.loader = UnifiedAudioLoader()
        self.sample_rate = 44100
        self.duration = 2.0
        self.samples = int(self.sample_rate * self.duration)

        # Create test audio
        t = np.linspace(0, self.duration, self.samples)
        self.test_audio = 0.5 * np.sin(2 * np.pi * 440 * t)
        self.test_stereo_audio = np.column_stack([self.test_audio, self.test_audio * 0.8])

    def test_loader_initialization(self):
        """Test loader initialization"""
        loader = UnifiedAudioLoader()
        assert loader is not None
        assert hasattr(loader, 'load')
        assert hasattr(loader, 'get_info')
        assert hasattr(loader, 'load_segment')

    def test_load_wav_file(self):
        """Test loading WAV file"""
        self.setUp()

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, self.test_stereo_audio, self.sample_rate)
            temp_path = f.name

        try:
            audio, info = self.loader.load(temp_path)

            assert audio is not None
            assert info is not None
            assert info.sample_rate == self.sample_rate
            assert info.channels == 2
            assert info.duration > 0
            assert info.format.lower() == 'wav'

        finally:
            os.unlink(temp_path)

    def test_load_flac_file(self):
        """Test loading FLAC file"""
        self.setUp()

        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as f:
            sf.write(f.name, self.test_stereo_audio, self.sample_rate)
            temp_path = f.name

        try:
            audio, info = self.loader.load(temp_path)

            assert audio is not None
            assert info.sample_rate == self.sample_rate
            assert info.channels == 2
            assert info.format.lower() == 'flac'

        finally:
            os.unlink(temp_path)

    def test_get_info_only(self):
        """Test getting file info without loading audio"""
        self.setUp()

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, self.test_stereo_audio, self.sample_rate)
            temp_path = f.name

        try:
            info = self.loader.get_info(temp_path)

            assert info is not None
            assert info.sample_rate == self.sample_rate
            assert info.channels == 2
            assert info.duration > 0

        finally:
            os.unlink(temp_path)

    def test_load_segment(self):
        """Test loading specific segment of file"""
        self.setUp()

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, self.test_stereo_audio, self.sample_rate)
            temp_path = f.name

        try:
            # Load first half second
            audio, info = self.loader.load_segment(temp_path, start=0.0, duration=0.5)

            expected_samples = int(0.5 * self.sample_rate)
            assert audio.shape[0] == expected_samples
            assert info.duration == 0.5

        finally:
            os.unlink(temp_path)

    def test_load_mono_file(self):
        """Test loading mono file"""
        self.setUp()

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, self.test_audio, self.sample_rate)
            temp_path = f.name

        try:
            audio, info = self.loader.load(temp_path)

            assert audio is not None
            assert info.channels == 1
            assert len(audio.shape) == 1

        finally:
            os.unlink(temp_path)

    def test_load_nonexistent_file(self):
        """Test loading non-existent file"""
        try:
            self.loader.load('nonexistent_file.wav')
            assert False, "Should have raised exception"
        except (LoaderError, FileNotFoundError):
            pass  # Expected

    def test_load_invalid_format(self):
        """Test loading invalid format"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'not audio data')
            temp_path = f.name

        try:
            self.loader.load(temp_path)
            assert False, "Should have raised exception"
        except (LoaderError, Exception):
            pass  # Expected
        finally:
            os.unlink(temp_path)

    def test_resample_during_load(self):
        """Test resampling during load"""
        self.setUp()

        # Create file with different sample rate
        original_rate = 48000
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, self.test_stereo_audio, original_rate)
            temp_path = f.name

        try:
            # Load with target sample rate
            target_rate = 44100
            audio, info = self.loader.load(temp_path, target_sample_rate=target_rate)

            assert info.sample_rate == target_rate

        finally:
            os.unlink(temp_path)

    def test_audio_info_class(self):
        """Test AudioInfo class functionality"""
        info = AudioInfo(
            sample_rate=44100,
            channels=2,
            duration=3.5,
            format='WAV',
            file_size=123456
        )

        assert info.sample_rate == 44100
        assert info.channels == 2
        assert info.duration == 3.5
        assert info.format == 'WAV'
        assert info.file_size == 123456

    def test_normalize_during_load(self):
        """Test normalization during load"""
        self.setUp()

        # Create loud audio
        loud_audio = self.test_stereo_audio * 2.0

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, loud_audio, self.sample_rate)
            temp_path = f.name

        try:
            audio, info = self.loader.load(temp_path, normalize=True)

            # Check if normalized
            max_val = np.max(np.abs(audio))
            assert max_val <= 1.0

        finally:
            os.unlink(temp_path)

    def test_load_with_different_bit_depths(self):
        """Test loading files with different bit depths"""
        self.setUp()

        for subtype in ['PCM_16', 'PCM_24']:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                sf.write(f.name, self.test_stereo_audio, self.sample_rate, subtype=subtype)
                temp_path = f.name

            try:
                audio, info = self.loader.load(temp_path)

                assert audio is not None
                assert info.sample_rate == self.sample_rate

            finally:
                os.unlink(temp_path)

if __name__ == '__main__':
    import pytest
    pytest.main([__file__])