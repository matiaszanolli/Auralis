"""calculate_loudness_units streams the K-weighting a channel at a time (#6717).

It used to K-weight the whole buffer into a full-size array and then square its
columns; a whole-track job measures loudness several times per pipeline pass,
so that array (plus the filter temporaries) sat on top of every stage's peak.
"""

import tracemalloc

import numpy as np
import pytest

from auralis.analysis.loudness_filters import mean_square_to_lufs
from auralis.analysis.loudness_meter import LoudnessMeter
from auralis.dsp.utils.adaptive import calculate_loudness_units

SR = 48000


@pytest.mark.parametrize("dtype", [np.float64, np.float32])
@pytest.mark.parametrize("channels", [2, 6])
def test_streamed_mean_square_equals_the_materialised_one_exactly(dtype, channels):
    x = (0.3 * np.random.default_rng(channels).standard_normal((SR * 2, channels))).astype(dtype)

    streamed = mean_square_to_lufs(LoudnessMeter(sample_rate=SR).k_weighted_mean_square(x))
    meter = LoudnessMeter(sample_rate=SR)
    materialised = meter.calculate_block_loudness(meter.apply_k_weighting(x))

    assert streamed == materialised


def test_silence_is_minus_infinity():
    assert mean_square_to_lufs(LoudnessMeter(sample_rate=SR).k_weighted_mean_square(np.zeros((SR, 2)))) == -np.inf


def test_loudness_measurement_holds_well_under_two_buffers():
    x = 0.3 * np.random.default_rng(9).standard_normal((SR * 20, 2))
    calculate_loudness_units(x[:SR], SR)  # warm imports outside the measurement

    tracemalloc.start()
    try:
        start = tracemalloc.get_traced_memory()[0]
        calculate_loudness_units(x, SR)
        peak = tracemalloc.get_traced_memory()[1] - start
    finally:
        tracemalloc.stop()

    # ~1.5x measured (one channel's filter chain); the full-array version peaked at ~2.5x.
    assert peak <= 1.8 * x.nbytes, f"loudness measurement peaked at {peak / x.nbytes:.2f}x its input"
