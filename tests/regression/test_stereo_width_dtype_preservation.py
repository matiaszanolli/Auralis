"""
Stereo Width Dtype Preservation Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #3468:
`scipy.signal.sosfiltfilt` always returns float64. Before the fix,
`adjust_stereo_width_multiband` did not cast its three `sosfiltfilt`
outputs back to the input dtype, so the final
`stereo_audio + diff_lowmid + diff_highmid + diff_high` add promoted
float32 input to float64 — doubling memory bandwidth and violating the
project's float32 invariant for downstream mastering stages.
"""

from typing import Any

import numpy as np
import pytest

from auralis.dsp.utils.stereo import adjust_stereo_width_multiband


def _stereo_signal(n_samples: int = 4096, dtype: Any = np.float32) -> np.ndarray:
    """Generate a stereo signal with non-trivial content in every band."""
    rng = np.random.RandomState(42)
    audio = 0.1 * rng.randn(n_samples, 2)
    return audio.astype(dtype)


@pytest.mark.regression
class TestStereoWidthMultibandDtypePreservation:
    """Regression for #3468 — float32 input must produce float32 output."""

    def test_float32_input_stays_float32(self):
        audio = _stereo_signal(dtype=np.float32)
        result = adjust_stereo_width_multiband(audio, width_factor=0.8, sample_rate=44100)
        assert result.dtype == np.float32, (
            f"adjust_stereo_width_multiband promoted float32 to {result.dtype} — "
            f"#3468 regression"
        )

    def test_float64_input_stays_float64(self):
        audio = _stereo_signal(dtype=np.float64)
        result = adjust_stereo_width_multiband(audio, width_factor=0.8, sample_rate=44100)
        assert result.dtype == np.float64

    def test_no_op_short_circuit_preserves_dtype(self):
        """width_factor=0.5 hits the early-return path; dtype must still match."""
        audio = _stereo_signal(dtype=np.float32)
        result = adjust_stereo_width_multiband(audio, width_factor=0.5, sample_rate=44100)
        assert result.dtype == np.float32

    def test_sample_count_preserved(self):
        """Sanity check: the fix doesn't accidentally truncate/extend the signal."""
        audio = _stereo_signal(n_samples=8192, dtype=np.float32)
        result = adjust_stereo_width_multiband(audio, width_factor=0.75, sample_rate=44100)
        assert result.shape == audio.shape

    def test_output_finite_for_typical_input(self):
        """No NaN/Inf introduced by the dtype cast."""
        audio = _stereo_signal(dtype=np.float32)
        result = adjust_stereo_width_multiband(audio, width_factor=0.8, sample_rate=44100)
        assert np.isfinite(result).all()
