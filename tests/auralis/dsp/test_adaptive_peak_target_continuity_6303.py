"""calculate_adaptive_peak_target is continuous in source loudness (#6303).

It returned 0.85 / 0.88 / 0.90 with hard `>` tests at -12 and -14 LUFS, so the output peak of two near-identical
tracks straddling a threshold differed by a fixed 0.30 / 0.2 dB step. The plateaus are joined by the same knees
calculate_adaptive_gain uses.
"""

import numpy as np
import pytest

from auralis.dsp.utils.adaptive_loudness import AdaptiveLoudnessControl

peak = AdaptiveLoudnessControl.calculate_adaptive_peak_target


@pytest.mark.parametrize("threshold", [-12.0, -14.0])
def test_no_step_across_a_threshold(threshold):
    below, above = peak(threshold - 0.001), peak(threshold + 0.001)

    assert abs(above[1] - below[1]) < 0.01  # dB; was ~0.30 and ~0.2


def test_the_plateaus_are_unchanged_away_from_the_knees():
    assert peak(-8.0)[0] == pytest.approx(0.85)
    assert peak(-13.0)[0] == pytest.approx(0.88)
    assert peak(-20.0)[0] == pytest.approx(0.90)


def test_quieter_sources_never_get_a_lower_peak_target_and_stay_in_range():
    loudness = np.linspace(-6.0, -40.0, 3401)
    targets = np.array([peak(float(x))[0] for x in loudness])

    assert np.all(np.diff(targets) >= -1e-12)
    assert targets.min() >= 0.85 - 1e-9 and targets.max() <= 0.90 + 1e-9


def test_the_db_value_matches_the_linear_target():
    linear, db = peak(-13.2)

    assert db == pytest.approx(20 * np.log10(linear))
