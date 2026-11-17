"""A NaN buffer must not drive the realtime level matcher to +20 dB (#6299)

``min(10.0, nan)`` is 10.0, so one NaN sample made ``set_target(nan)`` mean "apply the maximum
gain", and the smoother carried that into the following clean buffers.
"""

import numpy as np

from auralis.player.config import PlayerConfig
from auralis.player.realtime.gain_smoother import AdaptiveGainSmoother
from auralis.player.realtime.level_matcher import RealtimeLevelMatcher


def test_smoother_ignores_a_non_finite_target():
    smoother = AdaptiveGainSmoother()
    smoother.set_target(2.0)

    smoother.set_target(float("nan"))
    smoother.set_target(float("inf"))

    assert smoother.target_gain == 2.0


def test_one_nan_sample_leaves_the_gain_where_it_was():
    config = PlayerConfig()
    matcher = RealtimeLevelMatcher(config)
    matcher.set_reference_audio(np.full((4096, 2), 0.1, dtype=np.float32))
    clean = np.full((1024, 2), 0.02, dtype=np.float32)
    for _ in range(50):
        matcher.process(clean.copy())
    steady = matcher.gain_smoother.current_gain

    corrupt = clean.copy()
    corrupt[10, 0] = np.nan
    matcher.process(corrupt)

    assert matcher.gain_smoother.target_gain < 10.0
    assert abs(matcher.gain_smoother.current_gain - steady) < 0.5
