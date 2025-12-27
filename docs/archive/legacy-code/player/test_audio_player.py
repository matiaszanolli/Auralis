# -*- coding: utf-8 -*-

"""
Comprehensive tests for Auralis audio player
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import EnhancedAudioPlayer


class TestAudioPlayer:
    """Test EnhancedAudioPlayer class functionality (migrated from AudioPlayer)"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create synthetic stereo audio data
        self.sample_rate = 44100
        duration = 0.5  # 0.5 seconds
        samples = int(duration * self.sample_rate)

        # Create stereo test audio (2 channels)
        t = np.linspace(0, duration, samples)
        left = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        right = 0.3 * np.sin(2 * np.pi * 880 * t)  # 880 Hz sine wave
        self.test_audio = np.column_stack((left, right)).astype(np.float32)

        # Reference audio with different characteristics
        self.reference_audio = np.column_stack((left * 0.8, right * 0.8)).astype(np.float32)

        # Create temp files
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.wav")
        self.reference_file = os.path.join(self.temp_dir, "reference.wav")

    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization_default_config(self):
        """Test EnhancedAudioPlayer initialization with default config"""
        player = EnhancedAudioPlayer()

        assert isinstance(player.config, PlayerConfig)
        assert player.is_playing is False
        assert player.current_file is None
        assert player.reference_file is None
        assert player.audio_data is None
        assert player.reference_data is None
        assert player.position == 0

    def test_initialization_custom_config(self):
        """Test EnhancedAudioPlayer initialization with custom config"""
        config = PlayerConfig(
            sample_rate=48000,
            buffer_size=2048,
            enable_level_matching=False
        )
        player = EnhancedAudioPlayer(config)

        assert player.config is config
        assert player.config.sample_rate == 48000
        assert player.config.buffer_size == 2048
        assert player.config.enable_level_matching is False

    @patch('auralis.io.loader.load')
    def test_load_file_success(self, mock_load):
        """Test successful file loading"""
        mock_load.return_value = (self.test_audio, self.sample_rate)

        player = EnhancedAudioPlayer()
        result = player.load_file(self.test_file)

        assert result is True
        assert player.current_file == self.test_file
        assert np.array_equal(player.audio_data, self.test_audio)
        assert player.position == 0
        mock_load.assert_called_once_with(self.test_file, "target")

    @patch('auralis.io.loader.load')
    def test_load_file_failure(self, mock_load):
        """Test file loading failure"""
        mock_load.side_effect = Exception("Load failed")

        player = EnhancedAudioPlayer()
        result = player.load_file(self.test_file)

        assert result is False
        assert player.current_file is None
        assert player.audio_data is None

    @patch('auralis.io.loader.load')
    def test_load_reference_success(self, mock_load):
        """Test successful reference loading"""
        mock_load.return_value = (self.reference_audio, self.sample_rate)

        player = EnhancedAudioPlayer()
        result = player.load_reference(self.reference_file)

        assert result is True
        assert player.reference_file == self.reference_file
        assert np.array_equal(player.reference_data, self.reference_audio)
        mock_load.assert_called_once_with(self.reference_file, "reference")

    @patch('auralis.io.loader.load')
    def test_load_reference_failure(self, mock_load):
        """Test reference loading failure"""
        mock_load.side_effect = Exception("Load failed")

        player = EnhancedAudioPlayer()
        result = player.load_reference(self.reference_file)

        assert result is False
        assert player.reference_file is None
        assert player.reference_data is None

    def test_play_control_methods(self):
        """Test play, pause, and stop methods"""
        player = EnhancedAudioPlayer()
        player.audio_data = self.test_audio

        # Initial state
        assert player.is_playing is False

        # Test play
        player.play()
        assert player.is_playing is True

        # Test pause
        player.pause()
        assert player.is_playing is False

        # Test stop
        player.position = 1000  # Set some position
        player.stop()
        assert player.is_playing is False
        assert player.position == 0

    def test_play_without_audio_data(self):
        """Test play method without loaded audio"""
        player = EnhancedAudioPlayer()
        player.play()  # Should not crash even without audio data
        # Should not start playing without audio data (based on the actual implementation)
        assert player.is_playing is False

    def test_get_audio_chunk_no_audio(self):
        """Test getting audio chunk when no audio is loaded"""
        player = EnhancedAudioPlayer()
        chunk = player.get_audio_chunk(1024)

        assert chunk.shape == (1024, 2)
        assert np.all(chunk == 0)  # Should be silence

    def test_get_audio_chunk_not_playing(self):
        """Test getting audio chunk when not playing"""
        player = EnhancedAudioPlayer()
        player.audio_data = self.test_audio
        player.is_playing = False

        chunk = player.get_audio_chunk(1024)

        assert chunk.shape == (1024, 2)
        assert np.all(chunk == 0)  # Should be silence

    def test_get_audio_chunk_basic_playback(self):
        """Test basic audio chunk retrieval during playback"""
        player = EnhancedAudioPlayer()
        player.audio_data = self.test_audio
        player.is_playing = True

        chunk_size = 1024
        chunk = player.get_audio_chunk(chunk_size)

        assert chunk.shape == (chunk_size, 2)
        assert not np.all(chunk == 0)  # Should contain audio data
        assert player.position == chunk_size

    def test_get_audio_chunk_end_of_track(self):
        """Test audio chunk retrieval at end of track"""
        player = EnhancedAudioPlayer()
        player.audio_data = self.test_audio
        player.is_playing = True
        player.position = len(self.test_audio) - 100  # Near end

        chunk = player.get_audio_chunk(1024)

        assert chunk.shape == (1024, 2)
        assert player.is_playing is False  # Should stop at end
        assert player.position == len(self.test_audio)

    def test_get_audio_chunk_with_padding(self):
        """Test audio chunk with padding when reaching end"""
        player = EnhancedAudioPlayer()
        player.audio_data = self.test_audio
        player.is_playing = True
        player.position = len(self.test_audio) - 100  # 100 samples left

        chunk = player.get_audio_chunk(1024)

        assert chunk.shape == (1024, 2)
        # First 100 samples should be audio, rest should be zeros
        assert not np.all(chunk[:100] == 0)
        assert np.all(chunk[100:] == 0)

    def test_get_audio_chunk_default_size(self):
        """Test audio chunk with default buffer size"""
        config = PlayerConfig(buffer_size=512)
        player = AudioPlayer(config)
        player.audio_data = self.test_audio
        player.is_playing = True

        chunk = player.get_audio_chunk()  # No size specified

        assert chunk.shape == (512, 2)  # Should use config buffer size

    @patch('auralis.dsp.basic.rms')
    @patch('auralis.dsp.basic.amplify')
    def test_real_time_mastering_enabled(self, mock_amplify, mock_rms):
        """Test real-time mastering when enabled"""
        mock_rms.side_effect = [0.2, 0.4]  # chunk_rms, ref_rms
        mock_amplify.return_value = self.test_audio[:1024]

        config = PlayerConfig(enable_level_matching=True)
        player = AudioPlayer(config)
        player.audio_data = self.test_audio
        player.reference_data = self.reference_audio
        player.is_playing = True

        chunk = player.get_audio_chunk(1024)

        # Should call RMS and amplify functions
        assert mock_rms.call_count == 2
        mock_amplify.assert_called_once()

    def test_real_time_mastering_disabled(self):
        """Test real-time mastering when disabled"""
        config = PlayerConfig(enable_level_matching=False)
        player = AudioPlayer(config)
        player.audio_data = self.test_audio
        player.reference_data = self.reference_audio
        player.is_playing = True

        chunk = player.get_audio_chunk(1024)

        # Should return unprocessed audio
        expected = self.test_audio[:1024]
        np.testing.assert_array_equal(chunk, expected)

    def test_real_time_mastering_no_reference(self):
        """Test behavior when no reference is loaded"""
        config = PlayerConfig(enable_level_matching=True)
        player = AudioPlayer(config)
        player.audio_data = self.test_audio
        player.reference_data = None  # No reference
        player.is_playing = True

        chunk = player.get_audio_chunk(1024)

        # Should return unprocessed audio
        expected = self.test_audio[:1024]
        np.testing.assert_array_equal(chunk, expected)

    @patch('auralis.dsp.basic.rms')
    @patch('auralis.dsp.basic.amplify')
    def test_real_time_mastering_zero_rms(self, mock_amplify, mock_rms):
        """Test real-time mastering with zero chunk RMS"""
        mock_rms.side_effect = [0.0, 0.4]  # zero chunk_rms, ref_rms

        config = PlayerConfig(enable_level_matching=True)
        player = AudioPlayer(config)
        player.audio_data = self.test_audio
        player.reference_data = self.reference_audio
        player.is_playing = True

        chunk = player.get_audio_chunk(1024)

        # Should not call amplify when chunk RMS is zero
        mock_amplify.assert_not_called()

    @patch('auralis.dsp.basic.rms')
    @patch('auralis.dsp.basic.amplify')
    def test_real_time_mastering_gain_limiting(self, mock_amplify, mock_rms):
        """Test gain limiting in real-time mastering"""
        mock_rms.side_effect = [0.1, 1.0]  # Would result in large gain
        mock_amplify.return_value = self.test_audio[:1024]

        config = PlayerConfig(enable_level_matching=True)
        player = AudioPlayer(config)
        player.audio_data = self.test_audio
        player.reference_data = self.reference_audio
        player.is_playing = True

        chunk = player.get_audio_chunk(1024)

        # Check that gain was limited to ±6dB
        call_args = mock_amplify.call_args[0]
        gain_db = call_args[1]
        assert -6 <= gain_db <= 6

    def test_get_playback_info_no_audio(self):
        """Test playback info when no audio is loaded"""
        player = EnhancedAudioPlayer()

        info = player.get_playback_info()

        assert info['is_playing'] is False
        assert info['position'] == 0
        assert info['total_samples'] == 0
        assert info['current_file'] is None
        assert info['reference_file'] is None
        assert 'duration_seconds' not in info
        assert 'position_seconds' not in info

    def test_get_playback_info_with_audio(self):
        """Test playback info when audio is loaded"""
        config = PlayerConfig(sample_rate=44100)
        player = AudioPlayer(config)
        player.audio_data = self.test_audio
        player.current_file = self.test_file
        player.reference_file = self.reference_file
        player.position = 1000
        player.is_playing = True

        info = player.get_playback_info()

        assert info['is_playing'] is True
        assert info['position'] == 1000
        assert info['total_samples'] == len(self.test_audio)
        assert info['current_file'] == self.test_file
        assert info['reference_file'] == self.reference_file
        assert 'duration_seconds' in info
        assert 'position_seconds' in info
        assert info['duration_seconds'] == len(self.test_audio) / 44100
        assert info['position_seconds'] == 1000 / 44100

    def test_sequential_chunk_playback(self):
        """Test sequential chunk retrieval"""
        player = EnhancedAudioPlayer()
        player.audio_data = self.test_audio
        player.is_playing = True

        chunk_size = 1000
        chunk1 = player.get_audio_chunk(chunk_size)
        chunk2 = player.get_audio_chunk(chunk_size)

        assert chunk1.shape == (chunk_size, 2)
        assert chunk2.shape == (chunk_size, 2)
        assert player.position == 2000

        # Chunks should be different (sequential parts of audio)
        assert not np.array_equal(chunk1, chunk2)

    @patch('auralis.io.loader.load')
    def test_audio_player_full_workflow(self, mock_load):
        """Test complete workflow: load, play, get chunks"""
        mock_load.return_value = (self.test_audio, self.sample_rate)

        player = EnhancedAudioPlayer()

        # Load files
        assert player.load_file(self.test_file) is True
        assert player.load_reference(self.reference_file) is True

        # Start playback
        player.play()
        assert player.is_playing is True

        # Get some chunks
        chunk1 = player.get_audio_chunk(1024)
        chunk2 = player.get_audio_chunk(1024)

        assert chunk1.shape == (1024, 2)
        assert chunk2.shape == (1024, 2)
        assert player.position == 2048

        # Stop playback
        player.stop()
        assert player.is_playing is False
        assert player.position == 0