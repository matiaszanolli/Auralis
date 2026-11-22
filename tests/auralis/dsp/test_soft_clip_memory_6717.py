"""soft_clip works on the over-threshold samples only (#6717).

It used to build full-size |audio|, sign(audio) and output arrays, two masks and
a gathered copy of every below-threshold sample at once (~4.1x its input) on
whole-track compression. Values are unchanged.
"""

import tracemalloc

import numpy as np
import pytest

from auralis.dsp.dynamics.soft_clipper import soft_clip


def _reference_soft_clip(audio, threshold=0.9, ceiling=0.99):
    """The pre-#6717 body (above the early returns), kept to pin the values."""
    threshold = min(threshold, ceiling * 0.99)
    headroom = ceiling - threshold
    abs_audio = np.abs(audio)
    sign = np.sign(audio)
    output = np.empty_like(audio)
    below = abs_audio <= threshold
    output[below] = audio[below]
    above = ~below
    if np.any(above):
        excess = abs_audio[above] - threshold
        output[above] = sign[above] * (threshold + headroom * np.tanh(excess / (headroom * 1.5)))
    return output


@pytest.mark.parametrize("dtype", [np.float64, np.float32])
@pytest.mark.parametrize("threshold, ceiling", [(0.9, 0.99), (0.5, 0.6), (2.0, 0.99)])
def test_values_match_the_full_array_algorithm(dtype, threshold, ceiling):
    x = (1.2 * np.random.default_rng(1).standard_normal((20_000, 2))).astype(dtype)
    x.flat[::997] = np.nan
    x.flat[3::1499] = np.inf
    x.flat[5::1999] = -0.0

    with np.errstate(invalid="ignore"):
        expected = _reference_soft_clip(x, threshold, ceiling)
        actual = soft_clip(x, threshold, ceiling)

    assert actual.dtype == expected.dtype
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(np.signbit(actual), np.signbit(expected))


def test_peak_working_memory_is_about_two_buffers():
    x = 0.6 * np.random.default_rng(2).standard_normal((44100 * 20, 2))
    soft_clip(x[:1000])

    tracemalloc.start()
    try:
        start = tracemalloc.get_traced_memory()[0]
        soft_clip(x)
        peak = tracemalloc.get_traced_memory()[1] - start
    finally:
        tracemalloc.stop()

    # Output (1x) plus one transient |x| (1x) plus masks: ~2.1x measured; ~4.1x before.
    assert peak <= 2.5 * x.nbytes, f"soft_clip peaked at {peak / x.nbytes:.2f}x its input"
