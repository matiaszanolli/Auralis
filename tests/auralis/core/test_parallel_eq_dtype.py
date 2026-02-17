"""
Tests for ParallelEQUtilities dtype preservation (issue #2158)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

sosfilt() always returns float64 regardless of input dtype. Without the fix,
float32 audio is silently promoted to float64, doubling memory usage across
every EQ stage and causing dtype mismatches downstream.

All three methods (apply_low_shelf_boost, apply_high_shelf_boost,
apply_bandpass_boost) must preserve the input dtype for both mono and stereo.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.core.dsp.parallel_eq import ParallelEQUtilities


SAMPLE_RATE = 44100
DURATION_SAMPLES = SAMPLE_RATE  # 1 second


@pytest.fixture(params=[np.float32, np.float64])
def dtype(request):
    return request.param


@pytest.fixture(params=["mono", "stereo"])
def audio(request, dtype):
    rng = np.random.default_rng(42)
    if request.param == "mono":
        return rng.standard_normal(DURATION_SAMPLES).astype(dtype)
    else:
        # (channels, samples) layout used by ParallelEQUtilities stereo path
        return rng.standard_normal((2, DURATION_SAMPLES)).astype(dtype)


class TestLowShelfDtype:
    def test_output_dtype_matches_input(self, audio, dtype):
        out = ParallelEQUtilities.apply_low_shelf_boost(
            audio, boost_db=2.0, freq_hz=120.0, sample_rate=SAMPLE_RATE
        )
        assert out.dtype == dtype, (
            f"apply_low_shelf_boost: expected {dtype}, got {out.dtype}"
        )

    def test_output_shape_preserved(self, audio, dtype):
        out = ParallelEQUtilities.apply_low_shelf_boost(
            audio, boost_db=2.0, freq_hz=120.0, sample_rate=SAMPLE_RATE
        )
        assert out.shape == audio.shape

    def test_output_is_finite(self, audio, dtype):
        out = ParallelEQUtilities.apply_low_shelf_boost(
            audio, boost_db=2.0, freq_hz=120.0, sample_rate=SAMPLE_RATE
        )
        assert np.all(np.isfinite(out))

    def test_zero_boost_is_identity(self, audio, dtype):
        """0 dB boost (boost_diff = 0) should return audio unchanged."""
        out = ParallelEQUtilities.apply_low_shelf_boost(
            audio, boost_db=0.0, freq_hz=120.0, sample_rate=SAMPLE_RATE
        )
        np.testing.assert_array_equal(out, audio)


class TestHighShelfDtype:
    def test_output_dtype_matches_input(self, audio, dtype):
        out = ParallelEQUtilities.apply_high_shelf_boost(
            audio, boost_db=1.5, freq_hz=8000.0, sample_rate=SAMPLE_RATE
        )
        assert out.dtype == dtype, (
            f"apply_high_shelf_boost: expected {dtype}, got {out.dtype}"
        )

    def test_output_shape_preserved(self, audio, dtype):
        out = ParallelEQUtilities.apply_high_shelf_boost(
            audio, boost_db=1.5, freq_hz=8000.0, sample_rate=SAMPLE_RATE
        )
        assert out.shape == audio.shape

    def test_output_is_finite(self, audio, dtype):
        out = ParallelEQUtilities.apply_high_shelf_boost(
            audio, boost_db=1.5, freq_hz=8000.0, sample_rate=SAMPLE_RATE
        )
        assert np.all(np.isfinite(out))

    def test_zero_boost_is_identity(self, audio, dtype):
        out = ParallelEQUtilities.apply_high_shelf_boost(
            audio, boost_db=0.0, freq_hz=8000.0, sample_rate=SAMPLE_RATE
        )
        np.testing.assert_array_equal(out, audio)


class TestBandpassDtype:
    def test_output_dtype_matches_input(self, audio, dtype):
        out = ParallelEQUtilities.apply_bandpass_boost(
            audio, boost_db=2.0, low_hz=200.0, high_hz=2000.0,
            sample_rate=SAMPLE_RATE
        )
        assert out.dtype == dtype, (
            f"apply_bandpass_boost: expected {dtype}, got {out.dtype}"
        )

    def test_output_shape_preserved(self, audio, dtype):
        out = ParallelEQUtilities.apply_bandpass_boost(
            audio, boost_db=2.0, low_hz=200.0, high_hz=2000.0,
            sample_rate=SAMPLE_RATE
        )
        assert out.shape == audio.shape

    def test_output_is_finite(self, audio, dtype):
        out = ParallelEQUtilities.apply_bandpass_boost(
            audio, boost_db=2.0, low_hz=200.0, high_hz=2000.0,
            sample_rate=SAMPLE_RATE
        )
        assert np.all(np.isfinite(out))

    def test_zero_boost_is_identity(self, audio, dtype):
        out = ParallelEQUtilities.apply_bandpass_boost(
            audio, boost_db=0.0, low_hz=200.0, high_hz=2000.0,
            sample_rate=SAMPLE_RATE
        )
        np.testing.assert_array_equal(out, audio)


class TestFloat32QualityPreservation:
    """Verify that float32 output is numerically close to float64 output.

    If the fix introduces meaningful quality degradation (beyond float32
    precision), these tests will catch it.
    """

    def _mono_audio(self):
        rng = np.random.default_rng(0)
        return rng.standard_normal(SAMPLE_RATE)

    def test_low_shelf_float32_vs_float64(self):
        base = self._mono_audio()
        out32 = ParallelEQUtilities.apply_low_shelf_boost(
            base.astype(np.float32), boost_db=3.0, freq_hz=120.0,
            sample_rate=SAMPLE_RATE
        )
        out64 = ParallelEQUtilities.apply_low_shelf_boost(
            base.astype(np.float64), boost_db=3.0, freq_hz=120.0,
            sample_rate=SAMPLE_RATE
        )
        # float32 precision is ~1e-7 relative; allow generous rtol for filter
        np.testing.assert_allclose(out32.astype(np.float64), out64, rtol=2e-3)

    def test_high_shelf_float32_vs_float64(self):
        base = self._mono_audio()
        out32 = ParallelEQUtilities.apply_high_shelf_boost(
            base.astype(np.float32), boost_db=2.0, freq_hz=8000.0,
            sample_rate=SAMPLE_RATE
        )
        out64 = ParallelEQUtilities.apply_high_shelf_boost(
            base.astype(np.float64), boost_db=2.0, freq_hz=8000.0,
            sample_rate=SAMPLE_RATE
        )
        np.testing.assert_allclose(out32.astype(np.float64), out64, rtol=2e-3)

    def test_bandpass_float32_vs_float64(self):
        base = self._mono_audio()
        out32 = ParallelEQUtilities.apply_bandpass_boost(
            base.astype(np.float32), boost_db=2.5, low_hz=500.0, high_hz=4000.0,
            sample_rate=SAMPLE_RATE
        )
        out64 = ParallelEQUtilities.apply_bandpass_boost(
            base.astype(np.float64), boost_db=2.5, low_hz=500.0, high_hz=4000.0,
            sample_rate=SAMPLE_RATE
        )
        np.testing.assert_allclose(out32.astype(np.float64), out64, rtol=2e-3)
