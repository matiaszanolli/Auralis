"""
Stereo Width NaN Guard Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2611:
stereo_width_analysis must return 0.0 (not NaN) for silent or
constant-value audio channels where np.corrcoef would produce NaN.
"""

import numpy as np
import pytest

from auralis.dsp.utils.stereo import stereo_width_analysis


@pytest.mark.regression
class TestStereoWidthNaNGuard:
    """Regression tests for stereo_width_analysis NaN guard (#2611)."""

    def test_silent_stereo_returns_zero(self):
        """All-zero stereo audio should return 0.0, not NaN."""
        audio = np.zeros((44100, 2))
        result = stereo_width_analysis(audio)
        assert result == 0.0
        assert not np.isnan(result)

    def test_constant_stereo_returns_zero(self):
        """Constant-value stereo audio should return 0.0, not NaN."""
        audio = np.ones((44100, 2)) * 0.5
        result = stereo_width_analysis(audio)
        assert result == 0.0
        assert not np.isnan(result)

    def test_one_silent_channel_returns_zero(self):
        """One silent channel and one active should return 0.0."""
        audio = np.zeros((44100, 2))
        audio[:, 0] = np.random.RandomState(42).randn(44100)
        result = stereo_width_analysis(audio)
        assert result == 0.0
        assert not np.isnan(result)

    def test_normal_stereo_returns_valid_width(self):
        """Normal stereo audio should return a value in [0, 1]."""
        rng = np.random.RandomState(42)
        audio = rng.randn(44100, 2)
        result = stereo_width_analysis(audio)
        assert 0.0 <= result <= 1.0
        assert not np.isnan(result)

    def test_identical_channels_returns_near_zero(self):
        """Identical left/right channels (mono) should have width near 0."""
        mono = np.random.RandomState(42).randn(44100)
        audio = np.column_stack([mono, mono])
        result = stereo_width_analysis(audio)
        assert result < 0.05  # Near zero for perfectly correlated

    def test_mono_input_returns_default(self):
        """Mono (1D) input should return the 0.5 default."""
        audio = np.random.RandomState(42).randn(44100)
        result = stereo_width_analysis(audio)
        assert result == 0.5

    def test_result_is_never_nan(self):
        """Exhaustive check: no edge case should produce NaN."""
        edge_cases = [
            np.zeros((100, 2)),                            # all zeros
            np.ones((100, 2)),                             # all ones
            np.full((100, 2), -1.0),                       # all negative
            np.full((100, 2), 1e-15),                      # near-zero
            np.column_stack([np.zeros(100), np.ones(100)]),  # one constant
        ]
        for audio in edge_cases:
            result = stereo_width_analysis(audio)
            assert not np.isnan(result), f"NaN for input shape {audio.shape}"
