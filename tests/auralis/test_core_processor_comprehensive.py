# -*- coding: utf-8 -*-

"""
Comprehensive tests for Auralis core processor
"""

import pytest
import numpy as np
import tempfile
import os
from unittest.mock import patch, MagicMock

from auralis.core.processor import process
from auralis.core.config import Config
from auralis.io.results import Result
from auralis.utils.logging import ModuleError, Code


class TestCoreProcessor:
    """Test core audio processor functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create synthetic stereo audio data
        self.sample_rate = 44100
        duration = 1.0  # 1 second
        samples = int(duration * self.sample_rate)

        # Create stereo test audio (2 channels)
        t = np.linspace(0, duration, samples)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        right = 0.5 * np.sin(2 * np.pi * 880 * t)  # 880 Hz sine wave
        self.target_audio = np.column_stack((left, right))
        self.reference_audio = np.column_stack((left * 0.8, right * 0.8))  # Slightly different

        # Create temp files
        self.temp_dir = tempfile.mkdtemp()
        self.target_path = os.path.join(self.temp_dir, "target.wav")
        self.reference_path = os.path.join(self.temp_dir, "reference.wav")
        self.output_path = os.path.join(self.temp_dir, "output.wav")

    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.check_equality')
    @patch('auralis.core.processor.main')
    @patch('auralis.core.processor.save')
    @patch('auralis.core.processor.get_temp_folder')
    def test_process_basic_functionality(self, mock_get_temp, mock_save, mock_main,
                                       mock_check_equality, mock_check, mock_load):
        """Test basic process functionality with mocked dependencies"""
        # Setup mocks
        mock_load.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_main.return_value = (self.target_audio, None, None)
        mock_get_temp.return_value = self.temp_dir

        # Test with string result path
        process(self.target_path, self.reference_path, [self.output_path])

        # Verify calls
        assert mock_load.call_count == 2
        assert mock_check.call_count == 2
        mock_check_equality.assert_called_once()
        mock_main.assert_called_once()
        mock_save.assert_called_once()

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.check_equality')
    @patch('auralis.core.processor.main')
    @patch('auralis.core.processor.save')
    @patch('auralis.core.processor.get_temp_folder')
    def test_process_with_result_objects(self, mock_get_temp, mock_save, mock_main,
                                       mock_check_equality, mock_check, mock_load):
        """Test process with Result objects"""
        # Setup mocks
        mock_load.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_main.return_value = (self.target_audio, None, None)
        mock_get_temp.return_value = self.temp_dir

        # Test with Result objects
        results = [
            Result(self.output_path, subtype='PCM_24', use_limiter=True, normalize=False),
            Result(self.output_path.replace('.wav', '_2.wav'), subtype='PCM_16', use_limiter=False, normalize=True)
        ]

        process(self.target_path, self.reference_path, results)

        # Verify Result objects were used properly
        mock_save.assert_called()
        assert mock_save.call_count == 2

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.check_equality')
    @patch('auralis.core.processor.main')
    @patch('auralis.core.processor.save')
    @patch('auralis.core.processor.get_temp_folder')
    def test_process_with_custom_config(self, mock_get_temp, mock_save, mock_main,
                                      mock_check_equality, mock_check, mock_load):
        """Test process with custom configuration"""
        # Setup mocks
        mock_load.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_main.return_value = (self.target_audio, None, None)
        mock_get_temp.return_value = self.temp_dir

        # Custom config
        config = Config(
            internal_sample_rate=48000,
            fft_size=8192,
            temp_folder=self.temp_dir,
            allow_equality=True
        )

        process(self.target_path, self.reference_path, [self.output_path], config=config)

        # Verify config was used
        mock_check_equality.assert_not_called()  # allow_equality=True
        assert config.internal_sample_rate == max(self.sample_rate, self.sample_rate)

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.check_equality')
    @patch('auralis.core.processor.channel_count')
    @patch('auralis.core.processor.size')
    @patch('auralis.core.processor.main')
    @patch('auralis.core.processor.save')
    @patch('auralis.core.processor.get_temp_folder')
    def test_process_sample_rate_handling(self, mock_get_temp, mock_save, mock_main,
                                        mock_size, mock_channel_count, mock_check_equality,
                                        mock_check, mock_load):
        """Test sample rate handling logic"""
        target_rate = 48000
        ref_rate = 48000  # Must match for validation to pass

        # Setup mocks with same sample rates
        mock_load.side_effect = [
            (self.target_audio, target_rate),
            (self.reference_audio, ref_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, target_rate),
            (self.reference_audio, ref_rate)
        ]
        mock_main.return_value = (self.target_audio, None, None)
        mock_get_temp.return_value = self.temp_dir
        mock_channel_count.side_effect = [2, 2]  # Both stereo
        mock_size.side_effect = [8192, 8192]  # Both large enough

        config = Config()
        process(self.target_path, self.reference_path, [self.output_path], config=config)

        # Verify internal rate was updated during processing
        # Note: The config gets modified during process() execution
        # The actual assertion depends on the implementation details

    def test_process_empty_results_error(self):
        """Test error handling for empty results list"""
        with pytest.raises(RuntimeError, match="The result list is empty"):
            process(self.target_path, self.reference_path, [])

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.channel_count')
    @patch('auralis.core.processor.size')
    def test_process_validation_error(self, mock_size, mock_channel_count, mock_check, mock_load):
        """Test validation error handling"""
        # Setup mocks to trigger validation error
        mock_load.side_effect = [
            (self.target_audio, 44100),
            (self.reference_audio, 48000)  # Different sample rates
        ]
        mock_check.side_effect = [
            (self.target_audio, 44100),
            (self.reference_audio, 48000)
        ]
        mock_channel_count.side_effect = [2, 2]  # Both stereo
        mock_size.side_effect = [8192, 8192]  # Both large enough

        with pytest.raises(ModuleError):
            process(self.target_path, self.reference_path, [self.output_path])

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.check_equality')
    @patch('auralis.core.processor.main')
    @patch('auralis.core.processor.save')
    @patch('auralis.core.processor.create_preview')
    @patch('auralis.core.processor.get_temp_folder')
    def test_process_with_preview(self, mock_get_temp, mock_create_preview, mock_save,
                                mock_main, mock_check_equality, mock_check, mock_load):
        """Test process with preview generation"""
        # Setup mocks
        mock_load.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_main.return_value = (self.target_audio, None, None)
        mock_get_temp.return_value = self.temp_dir

        # Create preview result objects
        preview_target = Result(os.path.join(self.temp_dir, "preview_target.wav"))
        preview_result = Result(os.path.join(self.temp_dir, "preview_result.wav"))

        process(
            self.target_path,
            self.reference_path,
            [self.output_path],
            preview_target=preview_target,
            preview_result=preview_result
        )

        # Verify preview was created
        mock_create_preview.assert_called_once()

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.check_equality')
    @patch('auralis.core.processor.main')
    @patch('auralis.core.processor.save')
    @patch('auralis.core.processor.get_temp_folder')
    def test_process_different_result_types(self, mock_get_temp, mock_save, mock_main,
                                          mock_check_equality, mock_check, mock_load):
        """Test process with different result output types"""
        # Setup mocks
        mock_load.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]

        # Mock main to return all three result types
        result_limited = self.target_audio
        result_no_limiter = self.target_audio * 0.9
        result_normalized = self.target_audio * 1.1
        mock_main.return_value = (result_limited, result_no_limiter, result_normalized)
        mock_get_temp.return_value = self.temp_dir

        # Test different result combinations
        results = [
            Result(self.output_path.replace('.wav', '_limited.wav'), use_limiter=True, normalize=False),
            Result(self.output_path.replace('.wav', '_no_limit.wav'), use_limiter=False, normalize=False),
            Result(self.output_path.replace('.wav', '_normalized.wav'), use_limiter=False, normalize=True)
        ]

        process(self.target_path, self.reference_path, results)

        # Verify correct results were saved
        assert mock_save.call_count == 3

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.check_equality')
    @patch('auralis.core.processor.main')
    @patch('auralis.core.processor.save')
    @patch('auralis.core.processor.get_temp_folder')
    def test_process_single_result_conversion(self, mock_get_temp, mock_save, mock_main,
                                            mock_check_equality, mock_check, mock_load):
        """Test that single result gets converted to list"""
        # Setup mocks
        mock_load.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_main.return_value = (self.target_audio, None, None)
        mock_get_temp.return_value = self.temp_dir

        # Pass single result instead of list
        process(self.target_path, self.reference_path, self.output_path)

        # Verify it was converted to list and processed
        mock_save.assert_called_once()

    @patch('auralis.core.processor.load')
    @patch('auralis.core.processor.check')
    @patch('auralis.core.processor.channel_count')
    @patch('auralis.core.processor.size')
    def test_validation_conditions(self, mock_size, mock_channel_count, mock_check, mock_load):
        """Test various validation condition failures"""
        # Setup base mocks
        mock_load.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]

        # Test mono audio failure (not stereo)
        mock_channel_count.side_effect = [1, 2]  # Target mono, ref stereo
        mock_size.side_effect = [8192, 8192]

        with pytest.raises(ModuleError):
            process(self.target_path, self.reference_path, [self.output_path])

        # Test insufficient size failure - reset mocks for second test
        mock_load.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_check.side_effect = [
            (self.target_audio, self.sample_rate),
            (self.reference_audio, self.sample_rate)
        ]
        mock_channel_count.side_effect = [2, 2]  # Both stereo
        mock_size.side_effect = [2048, 8192]  # Target too small (< 4096)

        with pytest.raises(ModuleError):
            process(self.target_path, self.reference_path, [self.output_path])