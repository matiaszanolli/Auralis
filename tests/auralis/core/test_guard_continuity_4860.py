"""
Cross-dimensional guard continuity tests — issue #4860.

`ContinuousMode._apply_dsp_stages` measured a continuous quantity after each of
the EQ / dynamics / stereo stages and gated a corrective DSP action behind a
hard `if measured > threshold`. The correction jumped straight to a
substantial, audible value the instant the boundary was crossed, reintroducing
the categorical on/off step that the continuous-space architecture exists to
eliminate. Measured before the fix:

    lufs_drift 1.49  -> 0.00 dB      lufs_drift 1.51  -> -1.51 dB
    bass_shift 0.099 -> 0.00 dB      bass_shift 0.101 -> -1.01 dB
    phase_drop -0.199 -> blend 0.0   phase_drop -0.201 -> blend 0.50

Each gate is now a `smooth_gate` knee centred on the old threshold, so the
far-field behaviour is unchanged (nothing well below, full capped correction
well above) and only the transition became a ramp.

These test the guard *arithmetic* rather than driving audio through the whole
pipeline: the defect was entirely in how a measured scalar maps to a correction
magnitude, and a fine-grained sweep is the only thing that can demonstrate the
absence of a step.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.core.processing import continuous_guards as cm
from auralis.core.processing.cross_dimensional_guard import smooth_gate

# The correction formulas as _stage_eq / _stage_stereo_width compute them;
# the tilt correction is the stage's own function.


def eq_correction(lufs_drift: float) -> float:
    gate = smooth_gate(abs(lufs_drift), cm.EQ_DRIFT_KNEE_START, cm.EQ_DRIFT_KNEE_END)
    return max(-3.0, min(3.0, -lufs_drift)) * gate


def tilt_correction(bass_shift: float, high_shift: float = 0.0) -> float:
    # The stage's own function, not a copy of its formula (#6121).
    return cm.tilt_correction_db(bass_shift, high_shift)[0]


def phase_blend(phase_drop: float, post_phase: float) -> float:
    drop_gate = smooth_gate(-phase_drop, cm.PHASE_DROP_KNEE_START, cm.PHASE_DROP_KNEE_END)
    level_gate = smooth_gate(-post_phase, -cm.PHASE_LEVEL_KNEE_START, -cm.PHASE_LEVEL_KNEE_END)
    return cm.MAX_PHASE_BLEND * drop_gate * level_gate


def max_adjacent_jump(fn, lo: float, hi: float, n: int = 20001) -> float:
    xs = np.linspace(lo, hi, n)
    ys = np.array([fn(x) for x in xs])
    return float(np.abs(np.diff(ys)).max())


class TestSmoothGate:
    """The shared helper's own contract."""

    def test_clamps_below_and_above_the_knee(self):
        assert smooth_gate(0.5, 1.0, 2.0) == 0.0
        assert smooth_gate(1.0, 1.0, 2.0) == 0.0
        assert smooth_gate(2.0, 1.0, 2.0) == 1.0
        assert smooth_gate(9.0, 1.0, 2.0) == 1.0

    def test_is_one_half_at_the_knee_midpoint(self):
        assert smooth_gate(1.5, 1.0, 2.0) == pytest.approx(0.5)

    def test_is_monotonically_non_decreasing(self):
        xs = np.linspace(0.0, 3.0, 2000)
        ys = np.array([smooth_gate(x, 1.0, 2.0) for x in xs])
        assert np.all(np.diff(ys) >= -1e-12)

    def test_derivative_vanishes_at_both_knees(self):
        """C1 continuity — the ramp eases in, it does not corner."""
        eps = 1e-6
        d_lo = (smooth_gate(1.0 + eps, 1.0, 2.0) - smooth_gate(1.0, 1.0, 2.0)) / eps
        d_hi = (smooth_gate(2.0, 1.0, 2.0) - smooth_gate(2.0 - eps, 1.0, 2.0)) / eps
        assert d_lo == pytest.approx(0.0, abs=1e-4)
        assert d_hi == pytest.approx(0.0, abs=1e-4)

    def test_degenerate_knee_does_not_divide_by_zero(self):
        assert smooth_gate(5.0, 2.0, 2.0) == 1.0
        assert smooth_gate(1.0, 2.0, 2.0) == 0.0


class TestNoDiscontinuity:
    """Sweep each measured quantity across its old hard threshold."""

    # A step would show as a jump of ~1.0-1.5 between adjacent samples; a ramp
    # over these sweeps stays ~1e-4.
    MAX_ALLOWED_JUMP = 1e-3

    def test_eq_lufs_correction_is_continuous(self):
        assert max_adjacent_jump(eq_correction, 0.0, 4.0) < self.MAX_ALLOWED_JUMP

    def test_eq_correction_continuous_for_negative_drift(self):
        assert max_adjacent_jump(eq_correction, -4.0, 0.0) < self.MAX_ALLOWED_JUMP

    def test_spectral_tilt_correction_is_continuous(self):
        assert max_adjacent_jump(tilt_correction, -0.3, 0.3) < self.MAX_ALLOWED_JUMP

    def test_phase_blend_is_continuous_in_the_drop(self):
        assert max_adjacent_jump(lambda d: phase_blend(d, 0.25), -0.5, 0.0) < self.MAX_ALLOWED_JUMP

    def test_phase_blend_is_continuous_in_the_post_correlation(self):
        assert max_adjacent_jump(lambda p: phase_blend(-0.25, p), 0.0, 0.6) < self.MAX_ALLOWED_JUMP


class TestOldThresholdsNoLongerStep:
    """The issue's exact reproduction points."""

    def test_lufs_drift_either_side_of_1_5(self):
        # Was 0.00 vs -1.51 dB.
        delta = abs(eq_correction(1.51) - eq_correction(1.49))
        assert delta < 0.1, f"still steps by {delta:.3f} dB"

    def test_bass_shift_either_side_of_0_10(self):
        # Was 0.00 vs -1.01 dB.
        delta = abs(tilt_correction(0.101) - tilt_correction(0.099))
        assert delta < 0.1, f"still steps by {delta:.3f} dB"

    def test_phase_drop_either_side_of_0_2(self):
        # Was blend 0.0 vs 0.5 — a full half-collapse toward mono.
        delta = abs(phase_blend(-0.201, 0.301) - phase_blend(-0.199, 0.299))
        assert delta < 0.05, f"still steps by {delta:.3f}"


class TestFarFieldBehaviourUnchanged:
    """Smoothing must not weaken the guards where they genuinely should act."""

    def test_large_drift_still_fully_compensated_and_capped(self):
        assert eq_correction(3.0) == pytest.approx(-3.0)
        assert eq_correction(10.0) == pytest.approx(-3.0)

    def test_large_tilt_still_capped_at_2db(self):
        assert tilt_correction(0.5) == pytest.approx(-2.0)

    def test_severe_phase_collapse_still_blends_the_full_50_percent(self):
        assert phase_blend(-0.35, 0.15) == pytest.approx(cm.MAX_PHASE_BLEND)

    def test_quiet_measurements_still_produce_no_correction(self):
        assert eq_correction(0.5) == 0.0
        assert tilt_correction(0.02) == 0.0
        assert phase_blend(-0.05, 0.9) == 0.0

    def test_blend_never_exceeds_its_cap(self):
        for drop in np.linspace(-1.0, 0.0, 50):
            for post in np.linspace(-1.0, 1.0, 50):
                assert 0.0 <= phase_blend(drop, post) <= cm.MAX_PHASE_BLEND


class TestKneesBracketTheOldThresholds:
    """A knee moved off-centre would silently shift when guards engage."""

    @pytest.mark.parametrize(
        "start,end,old_threshold",
        [
            (cm.EQ_DRIFT_KNEE_START, cm.EQ_DRIFT_KNEE_END, 1.5),
            (cm.TILT_SHIFT_KNEE_START, cm.TILT_SHIFT_KNEE_END, 0.10),
            (cm.PHASE_DROP_KNEE_START, cm.PHASE_DROP_KNEE_END, 0.2),
        ],
    )
    def test_knee_is_centred_on_the_threshold_it_replaced(self, start, end, old_threshold):
        assert start < old_threshold < end
        assert (start + end) / 2 == pytest.approx(old_threshold)

    def test_phase_level_knee_descends_through_its_threshold(self):
        # Lower correlation is worse, so this knee runs downward.
        assert cm.PHASE_LEVEL_KNEE_END < 0.3 < cm.PHASE_LEVEL_KNEE_START
        assert (cm.PHASE_LEVEL_KNEE_START + cm.PHASE_LEVEL_KNEE_END) / 2 == pytest.approx(0.3)

    def test_epsilons_stay_far_below_audibility(self):
        # These exist to skip pointless work, not to gate audible corrections.
        assert cm.GUARD_EPSILON_DB <= 0.01
        assert cm.GUARD_EPSILON_BLEND <= 0.001


class TestTiltDriverContinuity6121:
    """The tilt used to follow whichever shift was larger by abs(), so across a
    tie the correction jumped between the two drivers and flipped sign."""

    def test_no_jump_when_bass_and_high_shifts_cross_a_tie(self):
        # high moves 0.20 in the SAME direction as bass (mid band dropped); sweep
        # bass through the tie at 0.20.
        below = tilt_correction(0.199, 0.20)
        above = tilt_correction(0.201, 0.20)
        assert abs(above - below) < 0.05

    def test_shifts_in_the_same_direction_are_no_tilt(self):
        assert tilt_correction(0.20, 0.20) == pytest.approx(0.0)
        assert tilt_correction(-0.15, -0.15) == pytest.approx(0.0)

    def test_a_lone_shift_is_unchanged_from_the_old_behaviour(self):
        assert tilt_correction(0.12, 0.0) == pytest.approx(-1.2 * smooth_gate(0.12, cm.TILT_SHIFT_KNEE_START, cm.TILT_SHIFT_KNEE_END))
        assert tilt_correction(0.0, 0.12) == pytest.approx(+1.2 * smooth_gate(0.12, cm.TILT_SHIFT_KNEE_START, cm.TILT_SHIFT_KNEE_END))

    def test_opposite_shifts_add_up_as_a_real_tilt(self):
        # bass up and highs down: a genuine tilt, stronger than either alone.
        assert tilt_correction(0.10, -0.10) < tilt_correction(0.10, 0.0) <= 0.0

    def test_cap_is_still_2db(self):
        assert tilt_correction(0.5, -0.5) == pytest.approx(-2.0)
        assert tilt_correction(-0.5, 0.5) == pytest.approx(2.0)

    def test_correction_is_continuous_in_both_arguments(self):
        for high in (-0.3, -0.1, 0.0, 0.1, 0.3):
            assert max_adjacent_jump(lambda b, h=high: tilt_correction(b, h), -0.4, 0.4) < self.MAX_ALLOWED_JUMP

    MAX_ALLOWED_JUMP = 0.15

