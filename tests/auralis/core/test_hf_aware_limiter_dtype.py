"""
Regression test: hf_aware_limiter preserves float32 working dtype (#4105)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_band_low` returned `sosfiltfilt(...)` (always float64) without casting back to
the input dtype, so for float32 input every intermediate band computed in
float64 — silently ~2x working-set memory. It now casts back, matching every
other sosfiltfilt caller.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
import pytest
from scipy.signal import butter

from auralis.core.processing.hf_aware_limiter import _band_low, apply_hf_aware_limiter

SR = 44100


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_band_low_preserves_input_dtype(dtype):
    audio = np.zeros((SR // 4, 2), dtype=dtype)
    sos = butter(2, 6000.0, btype="low", fs=SR, output="sos")

    out = _band_low(audio, sos)

    assert out.dtype == dtype, f"_band_low must return {dtype}, got {out.dtype}"
    assert out.shape == audio.shape


def test_hf_aware_limiter_float32_output_dtype_and_shape():
    """A float32 input that triggers limiting stays float32, same shape (#4105)."""
    rng = np.random.default_rng(7)
    # Loud enough to exceed the safety ceiling and engage the limiter.
    audio = (rng.standard_normal((SR, 2)) * 0.9).astype(np.float32)

    out, _limited = apply_hf_aware_limiter(audio, SR)

    assert out.dtype == np.float32
    assert out.shape == audio.shape
    # Clamp contract still holds.
    assert np.max(np.abs(out)) <= 1.0 + 1e-6
