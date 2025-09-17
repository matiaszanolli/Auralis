# -*- coding: utf-8 -*-

"""
Additional comprehensive tests for enhanced audio player components
"""

import pytest
import numpy as np
import tempfile
import os
from unittest.mock import patch, MagicMock

from auralis.player.enhanced_audio_player import (
    EnhancedAudioPlayer, QueueManager, PlaybackState
)
from auralis.player.config import PlayerConfig


class TestEnhancedPlayerExtended:
    """Extended tests for enhanced audio player functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create synthetic stereo audio data
        self.sample_rate = 44100
        duration = 0.3  # 0.3 seconds
        samples = int(duration * self.sample_rate)

        # Create stereo test audio (2 channels)
        t = np.linspace(0, duration, samples)
        left = 0.2 * np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        right = 0.2 * np.sin(2 * np.pi * 880 * t)  # 880 Hz sine wave
        self.test_audio = np.column_stack((left, right)).astype(np.float32)

        # Create temp files
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = []
        for i in range(3):
            file_path = os.path.join(self.temp_dir, f"test_{i}.wav")
            self.test_files.append(file_path)

    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_enhanced_player_advanced_queue_operations(self):
        """Test advanced queue operations"""
        config = PlayerConfig(queue_size=10)
        player = EnhancedAudioPlayer(config)

        # Test adding multiple tracks
        for file_path in self.test_files:
            player.add_to_queue(file_path)

        assert len(player.queue_manager.queue) == 3

        # Test queue manipulation methods
        assert player.queue_manager.get_queue_size() == 3
        assert player.queue_manager.get_current_position() == 0

        # Test getting queue state
        queue_info = player.queue_manager.get_queue_info()
        assert 'total_tracks' in queue_info
        assert 'current_index' in queue_info
        assert 'tracks' in queue_info

    def test_enhanced_player_crossfade_functionality(self):
        """Test crossfade functionality"""
        config = PlayerConfig(
            enable_crossfade=True,
            crossfade_duration=2.0
        )
        player = EnhancedAudioPlayer(config)

        # Add tracks to queue
        for file_path in self.test_files:
            player.add_to_queue(file_path)

        # Test crossfade settings
        assert player.config.enable_crossfade is True
        assert player.config.crossfade_duration == 2.0

        # Test crossfade state management
        player.enable_crossfade(True)
        player.set_crossfade_duration(3.0)
        assert player.config.crossfade_duration == 3.0

    @patch('auralis.io.loader.load')
    def test_enhanced_player_gapless_playback(self, mock_load):
        """Test gapless playback functionality"""
        mock_load.return_value = (self.test_audio, self.sample_rate)

        config = PlayerConfig(enable_gapless=True)
        player = EnhancedAudioPlayer(config)

        # Add multiple tracks
        for file_path in self.test_files:
            player.add_to_queue(file_path)

        # Load and prepare first track
        player.load_current_track()
        player.play()

        assert player.state == PlaybackState.PLAYING
        assert player.config.enable_gapless is True

    def test_enhanced_player_repeat_modes(self):
        """Test different repeat modes"""
        player = EnhancedAudioPlayer()

        # Add tracks to queue
        for file_path in self.test_files:
            player.add_to_queue(file_path)

        # Test repeat modes
        player.set_repeat_mode('none')
        assert player.repeat_mode == 'none'

        player.set_repeat_mode('track')
        assert player.repeat_mode == 'track'

        player.set_repeat_mode('queue')
        assert player.repeat_mode == 'queue'

        # Test invalid repeat mode
        with pytest.raises(ValueError):
            player.set_repeat_mode('invalid')

    def test_enhanced_player_shuffle_functionality(self):
        """Test shuffle functionality"""
        player = EnhancedAudioPlayer()

        # Add tracks to queue
        for file_path in self.test_files:
            player.add_to_queue(file_path)

        original_queue = player.queue_manager.queue.copy()

        # Enable shuffle
        player.enable_shuffle(True)
        assert player.shuffle_enabled is True

        # Disable shuffle
        player.enable_shuffle(False)
        assert player.shuffle_enabled is False

    @patch('auralis.io.loader.load')
    def test_enhanced_player_track_navigation(self, mock_load):
        """Test track navigation methods"""
        mock_load.return_value = (self.test_audio, self.sample_rate)

        player = EnhancedAudioPlayer()

        # Add tracks to queue
        for file_path in self.test_files:
            player.add_to_queue(file_path)

        # Test navigation
        assert player.queue_manager.current_index == 0

        # Test next track
        player.next_track()
        assert player.queue_manager.current_index == 1

        # Test previous track
        player.previous_track()
        assert player.queue_manager.current_index == 0

        # Test jumping to specific track
        player.jump_to_track(2)
        assert player.queue_manager.current_index == 2

    def test_enhanced_player_volume_control(self):
        """Test volume control functionality"""
        player = EnhancedAudioPlayer()

        # Test initial volume
        assert player.volume == 1.0

        # Test setting volume
        player.set_volume(0.5)
        assert player.volume == 0.5

        # Test volume bounds
        player.set_volume(1.5)  # Should be clamped to 1.0
        assert player.volume == 1.0

        player.set_volume(-0.1)  # Should be clamped to 0.0
        assert player.volume == 0.0

    def test_enhanced_player_equalizer_integration(self):
        """Test equalizer integration"""
        config = PlayerConfig(enable_equalizer=True)
        player = EnhancedAudioPlayer(config)

        # Test equalizer enabled
        assert player.config.enable_equalizer is True

        # Test equalizer band adjustment
        eq_settings = {
            'low': 1.2,
            'mid': 0.8,
            'high': 1.1
        }
        player.set_equalizer_settings(eq_settings)
        assert player.equalizer_settings == eq_settings

    @patch('auralis.io.loader.load')
    def test_enhanced_player_seek_functionality(self, mock_load):
        """Test seek functionality"""
        mock_load.return_value = (self.test_audio, self.sample_rate)

        player = EnhancedAudioPlayer()
        player.add_to_queue(self.test_files[0])
        player.load_current_track()

        # Test seeking to position
        seek_position = 5.0  # 5 seconds
        player.seek_to_position(seek_position)

        # Position should be updated
        assert abs(player.get_position() - seek_position) < 0.1

        # Test seeking with bounds checking
        player.seek_to_position(-1.0)  # Should clamp to 0
        assert player.get_position() >= 0

        duration = player.get_duration()
        player.seek_to_position(duration + 10)  # Should clamp to duration
        assert player.get_position() <= duration

    @patch('auralis.io.loader.load')
    def test_enhanced_player_real_time_analysis(self, mock_load):
        """Test real-time audio analysis"""
        mock_load.return_value = (self.test_audio, self.sample_rate)

        config = PlayerConfig(enable_analysis=True)
        player = EnhancedAudioPlayer(config)
        player.add_to_queue(self.test_files[0])
        player.load_current_track()

        # Test getting real-time analysis
        analysis = player.get_real_time_analysis()

        assert 'peak_level' in analysis
        assert 'rms_level' in analysis
        assert 'frequency_spectrum' in analysis

    def test_enhanced_player_error_handling(self):
        """Test error handling in various scenarios"""
        player = EnhancedAudioPlayer()

        # Test operations on empty queue
        assert player.next_track() is False
        assert player.previous_track() is False
        assert player.get_current_track() is None

        # Test invalid file operations
        player.add_to_queue("nonexistent_file.wav")
        assert not player.load_current_track()

    def test_enhanced_player_state_persistence(self):
        """Test state persistence functionality"""
        player = EnhancedAudioPlayer()

        # Add tracks and modify state
        for file_path in self.test_files:
            player.add_to_queue(file_path)

        player.set_volume(0.7)
        player.enable_shuffle(True)
        player.set_repeat_mode('queue')

        # Test getting complete state
        state = player.get_player_state()

        assert 'volume' in state
        assert 'shuffle_enabled' in state
        assert 'repeat_mode' in state
        assert 'queue' in state
        assert 'current_index' in state

        assert state['volume'] == 0.7
        assert state['shuffle_enabled'] is True
        assert state['repeat_mode'] == 'queue'

    def test_enhanced_player_playback_statistics(self):
        """Test playback statistics collection"""
        player = EnhancedAudioPlayer()

        # Add tracks to queue
        for file_path in self.test_files:
            player.add_to_queue(file_path)

        # Test getting statistics
        stats = player.get_playback_statistics()

        assert 'total_tracks_played' in stats
        assert 'total_playtime' in stats
        assert 'queue_completion_rate' in stats

    @patch('auralis.io.loader.load')
    def test_enhanced_player_batch_operations(self, mock_load):
        """Test batch operations on queue"""
        mock_load.return_value = (self.test_audio, self.sample_rate)

        player = EnhancedAudioPlayer()

        # Test batch adding tracks
        player.add_tracks_batch(self.test_files)
        assert len(player.queue_manager.queue) == 3

        # Test clearing queue
        player.clear_queue()
        assert len(player.queue_manager.queue) == 0

        # Test batch removing tracks
        player.add_tracks_batch(self.test_files)
        player.remove_tracks_batch([0, 2])  # Remove first and third tracks
        assert len(player.queue_manager.queue) == 1

    def test_enhanced_player_advanced_configuration(self):
        """Test advanced configuration options"""
        config = PlayerConfig(
            buffer_size=4096,
            sample_rate=48000,
            enable_level_matching=True,
            enable_crossfade=True,
            crossfade_duration=3.0,
            enable_gapless=True,
            enable_equalizer=True,
            enable_analysis=True,
            queue_size=50
        )

        player = EnhancedAudioPlayer(config)

        # Verify all configuration settings
        assert player.config.buffer_size == 4096
        assert player.config.sample_rate == 48000
        assert player.config.enable_level_matching is True
        assert player.config.enable_crossfade is True
        assert player.config.crossfade_duration == 3.0
        assert player.config.enable_gapless is True
        assert player.config.enable_equalizer is True
        assert player.config.enable_analysis is True
        assert player.config.queue_size == 50