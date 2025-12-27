# -*- coding: utf-8 -*-

"""
Comprehensive tests for Auralis DSP stages
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from auralis.core.config import Config
from auralis.dsp.stages import main


class TestDSPStages:
    """Test DSP processing stages"""

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
        self.target_audio = np.column_stack((left, right))

        # Reference with different RMS level
        self.reference_audio = np.column_stack((left * 0.8, right * 0.8))

        self.config = Config()

    def test_main_pipeline_basic(self):
        """Test basic main processing pipeline"""
        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            self.reference_audio,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # All results should be returned
        assert result is not None
        assert result_no_limiter is not None
        assert result_normalized is not None

        # Results should have same shape as input
        assert result.shape == self.target_audio.shape
        assert result_no_limiter.shape == self.target_audio.shape
        assert result_normalized.shape == self.target_audio.shape

    def test_main_pipeline_selective_outputs(self):
        """Test main pipeline with selective outputs"""
        # Only request default result
        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            self.reference_audio,
            self.config,
            need_default=True,
            need_no_limiter=False,
            need_no_limiter_normalized=False
        )

        assert result is not None
        assert result_no_limiter is None
        assert result_normalized is None

        # Only request no-limiter result
        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            self.reference_audio,
            self.config,
            need_default=False,
            need_no_limiter=True,
            need_no_limiter_normalized=False
        )

        assert result is None
        assert result_no_limiter is not None
        assert result_normalized is None

        # Only request normalized result
        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            self.reference_audio,
            self.config,
            need_default=False,
            need_no_limiter=False,
            need_no_limiter_normalized=True
        )

        assert result is None
        assert result_no_limiter is None
        assert result_normalized is not None

    def test_main_pipeline_gain_adjustment(self):
        """Test that gain adjustment occurs correctly"""
        # Create target with lower RMS than reference
        quiet_target = self.target_audio * 0.1
        loud_reference = self.reference_audio * 2.0

        result, result_no_limiter, result_normalized = main(
            quiet_target,
            loud_reference,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Result should be louder than original quiet target
        target_peak = np.max(np.abs(quiet_target))
        result_peak = np.max(np.abs(result_no_limiter))
        assert result_peak > target_peak

    def test_main_pipeline_peak_limiting(self):
        """Test peak limiting in default result"""
        # Create target that will exceed 0.99 after gain adjustment
        loud_target = self.target_audio * 2.0
        quiet_reference = self.reference_audio * 0.1

        result, result_no_limiter, result_normalized = main(
            loud_target,
            quiet_reference,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Default result should be limited to <= 0.99
        result_peak = np.max(np.abs(result))
        assert result_peak <= 0.99

        # No-limiter result may exceed 0.99
        no_limiter_peak = np.max(np.abs(result_no_limiter))
        # (May or may not exceed depending on gain calculation)

    def test_main_pipeline_zero_target_rms(self):
        """Test handling of zero target RMS"""
        # Create silent target
        silent_target = np.zeros_like(self.target_audio)

        result, result_no_limiter, result_normalized = main(
            silent_target,
            self.reference_audio,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Results should still be silent or very quiet
        assert np.max(np.abs(result)) < 0.01
        assert np.max(np.abs(result_no_limiter)) < 0.01

    def test_main_pipeline_mono_audio(self):
        """Test main pipeline with mono audio"""
        # Create mono audio (1D array)
        mono_target = self.target_audio[:, 0]  # Just left channel
        mono_reference = self.reference_audio[:, 0]

        result, result_no_limiter, result_normalized = main(
            mono_target,
            mono_reference,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Results should have same shape as mono input
        assert result.shape == mono_target.shape
        assert result_no_limiter.shape == mono_target.shape
        assert result_normalized.shape == mono_target.shape

    def test_main_pipeline_edge_case_very_loud_reference(self):
        """Test with very loud reference"""
        very_loud_reference = self.reference_audio * 100.0

        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            very_loud_reference,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Should still produce valid results
        assert np.isfinite(result).all()
        assert np.isfinite(result_no_limiter).all()
        assert np.isfinite(result_normalized).all()

    def test_main_pipeline_edge_case_very_quiet_reference(self):
        """Test with very quiet reference"""
        very_quiet_reference = self.reference_audio * 0.001

        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            very_quiet_reference,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Should still produce valid results
        assert np.isfinite(result).all()
        assert np.isfinite(result_no_limiter).all()
        assert np.isfinite(result_normalized).all()

    def test_main_pipeline_identical_target_reference(self):
        """Test with identical target and reference"""
        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            self.target_audio,  # Same as target
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Results should be very similar to input (minimal gain change)
        np.testing.assert_allclose(result_no_limiter, self.target_audio, rtol=0.1)

    @patch('auralis.dsp.stages.rms')
    def test_main_pipeline_with_mocked_rms(self, mock_rms):
        """Test main pipeline with mocked RMS calculation"""
        # Mock RMS to return specific values
        mock_rms.side_effect = [0.2, 0.4]  # target_rms, reference_rms

        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            self.reference_audio,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Verify RMS was called twice
        assert mock_rms.call_count == 2

        # Results should be valid
        assert result is not None
        assert result_no_limiter is not None
        assert result_normalized is not None

    @patch('auralis.dsp.stages.amplify')
    @patch('auralis.dsp.stages.normalize')
    def test_main_pipeline_function_calls(self, mock_normalize, mock_amplify):
        """Test that expected functions are called"""
        # Setup mocks to return input unchanged
        mock_amplify.return_value = self.target_audio
        mock_normalize.return_value = self.target_audio

        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            self.reference_audio,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Verify amplify was called for gain adjustment
        mock_amplify.assert_called_once()

        # Verify normalize was called for normalized result
        mock_normalize.assert_called_once()

    def test_main_pipeline_no_outputs_requested(self):
        """Test when no outputs are requested"""
        result, result_no_limiter, result_normalized = main(
            self.target_audio,
            self.reference_audio,
            self.config,
            need_default=False,
            need_no_limiter=False,
            need_no_limiter_normalized=False
        )

        # All results should be None
        assert result is None
        assert result_no_limiter is None
        assert result_normalized is None

    def test_main_pipeline_complex_audio(self):
        """Test with more complex audio signal"""
        # Create complex signal with multiple frequencies
        duration = 0.2
        samples = int(duration * self.sample_rate)
        t = np.linspace(0, duration, samples)

        # Complex stereo signal
        left = (0.1 * np.sin(2 * np.pi * 220 * t) +
                0.1 * np.sin(2 * np.pi * 440 * t) +
                0.05 * np.sin(2 * np.pi * 880 * t))
        right = (0.1 * np.sin(2 * np.pi * 330 * t) +
                 0.1 * np.sin(2 * np.pi * 660 * t) +
                 0.05 * np.sin(2 * np.pi * 1320 * t))

        complex_target = np.column_stack((left, right))
        complex_reference = np.column_stack((left * 1.5, right * 1.5))

        result, result_no_limiter, result_normalized = main(
            complex_target,
            complex_reference,
            self.config,
            need_default=True,
            need_no_limiter=True,
            need_no_limiter_normalized=True
        )

        # Should handle complex signals properly
        assert result.shape == complex_target.shape
        assert np.isfinite(result).all()
        assert np.isfinite(result_no_limiter).all()
        assert np.isfinite(result_normalized).all()