"""The loudness target bounds the lift, not the absolute target (#6305).

calculate_target_lufs bounds the lift with a tanh at 8.25 dB minus the dynamic
range coordinate, then clipped the target to [-28, -2]. Below about -36 LUFS the
clip won: every source landed on -28 LUFS with a lift of +12 to +24 dB, and a
source above -2 LUFS was attenuated.
"""

import numpy as np
import pytest

from auralis.core.processing.continuous_space_types import PreferenceVector, ProcessingCoordinates
from auralis.core.processing.parameter_generator_dynamics import (
    TARGET_LUFS_CEILING,
    calculate_target_lufs,
)

SOURCES = np.arange(-60.0, 0.01, 0.5)


def _target(source_lufs: float, dynamics: float = 0.2, preference: PreferenceVector | None = None) -> float:
    coords = ProcessingCoordinates(
        spectral_balance=0.5, dynamic_range=dynamics, energy_level=0.5,
        fingerprint={'lufs': source_lufs},
    )
    return calculate_target_lufs(coords, preference)


@pytest.mark.parametrize("dynamics", [0.0, 0.2, 1.0])
def test_lift_never_exceeds_the_documented_bound(dynamics):
    lifts = [_target(s, dynamics) - s for s in SOURCES]
    assert max(lifts) <= 8.25 - dynamics + 1e-9
    assert min(lifts) >= 0.0, "the target law never attenuates without a preference"


def test_very_quiet_sources_keep_their_order():
    """The issue's probe: -40, -50, -60 all landed on -28.00."""
    targets = [_target(s) for s in (-60.0, -50.0, -40.0, -36.5)]
    assert targets == sorted(targets) and len(set(targets)) == 4
    assert _target(-60.0) == pytest.approx(-60.0 + 8.05, abs=0.01)


def test_target_rises_with_the_source_below_the_ceiling():
    quiet = SOURCES[SOURCES <= -15.0]
    targets = np.array([_target(s) for s in quiet])
    assert np.all(np.diff(targets) > 0.0), "plateau in the target law"


def test_ceiling_stops_the_lift_but_does_not_pull_a_hot_source_down():
    assert _target(-5.0) == pytest.approx(TARGET_LUFS_CEILING)
    assert _target(-1.0) == pytest.approx(-1.0, abs=1e-6)


def test_a_negative_preference_still_attenuates():
    quieter = PreferenceVector(loudness_bias=-1.0)
    assert _target(-1.0, preference=quieter) == pytest.approx(-3.0, abs=1e-6)
    assert _target(-50.0, preference=quieter) == pytest.approx(_target(-50.0) - 2.0)


def test_a_positive_preference_cannot_lift_past_the_ceiling():
    louder = PreferenceVector(loudness_bias=1.0)
    assert _target(-6.0, preference=louder) == pytest.approx(TARGET_LUFS_CEILING)
