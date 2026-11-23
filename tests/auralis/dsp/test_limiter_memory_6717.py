"""Brick-wall limiter working memory (#6717).

Whole-track processing jobs run the final limiter over the full track, so every
full-length temporary it holds multiplies the job's peak RSS. The limiter used
to pad and |abs| the stereo buffer twice over and build each gain array out of
place (5.6x the input); the values are unchanged, only the buffers are fewer.
"""

import tracemalloc

import numpy as np
import pytest
from scipy.ndimage import minimum_filter1d, uniform_filter1d

from auralis.dsp.dynamics.brick_wall_limiter import create_brick_wall_limiter
from auralis.dsp.dynamics.limiter_ramp import ramp_gain_reduction

SR = 44100


def _reference_ramp(target_gains, sample_peaks, lookahead, threshold_linear):
    """The out-of-place formula ramp_gain_reduction computed before #6717."""
    origin = (lookahead - 1) // 2
    gains = target_gains.astype(np.float64)
    ramped = uniform_filter1d(gains, size=lookahead, mode='nearest', origin=origin)
    no_limiting = minimum_filter1d(gains, size=lookahead, mode='nearest', origin=origin) >= 1.0
    ramped[no_limiting] = 1.0
    cap = threshold_linear / np.maximum(sample_peaks, 1e-10)
    return np.minimum(ramped, np.minimum(cap, 1.0))


@pytest.mark.parametrize("dtype", [np.float64, np.float32])
def test_ramp_matches_the_out_of_place_formula_exactly(dtype):
    rng = np.random.default_rng(5)
    peaks = np.abs(1.4 * rng.standard_normal(20_000)).astype(dtype)
    thr = 10 ** (-0.3 / 20)
    gains = np.where(peaks > thr, thr / np.maximum(peaks, 1e-10), 1.0)

    expected = _reference_ramp(gains, peaks, 220, thr)
    actual = ramp_gain_reduction(gains.copy(), peaks, 220, thr)

    assert actual.dtype == expected.dtype
    np.testing.assert_array_equal(actual, expected)


def test_limiter_does_not_mutate_its_input():
    x = 1.5 * np.random.default_rng(6).standard_normal((SR, 2))
    before = x.copy()
    create_brick_wall_limiter(SR, threshold_db=-0.3).process(x)
    np.testing.assert_array_equal(x, before)


def test_limiter_peak_working_memory_stays_under_two_buffers():
    x = 1.5 * np.random.default_rng(7).standard_normal((SR * 20, 2))
    limiter = create_brick_wall_limiter(SR, threshold_db=-0.3)
    limiter.process(x[:SR])  # warm any lazy state outside the measurement

    tracemalloc.start()
    try:
        start = tracemalloc.get_traced_memory()[0]
        out = limiter.process(x)
        peak = tracemalloc.get_traced_memory()[1] - start
    finally:
        tracemalloc.stop()

    assert out.shape == x.shape
    # Mono gain arrays, then the output: ~1.6x measured since the gains reuse their
    # buffers (was ~2.1x; the pre-#6717 code, with two padded |x| copies, ~5.6x).
    assert peak <= 1.9 * x.nbytes, f"limiter peaked at {peak / x.nbytes:.2f}x its input"

