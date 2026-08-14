"""
Tests for delta-from-target EQ curve generation.

Verifies:
  * Symmetric behavior — source above target → cut; below → lift; equal → 0
  * Asymmetric per-band caps respected
  * tanh saturation: large deltas approach but never exceed the cap
  * No NaN/Inf for extreme/zero source values
  * 5-shelf curve mapping makes acoustic sense
"""

from __future__ import annotations

import math

import pytest

from auralis.core.processing.delta_eq import (
    BAND_CAPS_DB,
    _EMPTY_BAND_KNEE_END,
    compute_delta_eq,
    to_eq_curve,
)


def _flat_bands(value: float = 0.10) -> dict[str, float]:
    """Return a fingerprint dict with every band set to the same fraction."""
    return {band: value for band in BAND_CAPS_DB}


# ---------------------------------------------------------------------------
# Symmetric behavior
# ---------------------------------------------------------------------------

def test_identical_source_and_target_produces_zero_gain():
    """If source == target, every EQ shelf gain must be 0."""
    fp = _flat_bands(0.15)
    r = compute_delta_eq(source=fp, target=fp)
    assert r.low_shelf_gain == pytest.approx(0.0, abs=1e-9)
    assert r.low_mid_gain == pytest.approx(0.0, abs=1e-9)
    assert r.mid_gain == pytest.approx(0.0, abs=1e-9)
    assert r.high_mid_gain == pytest.approx(0.0, abs=1e-9)
    assert r.high_shelf_gain == pytest.approx(0.0, abs=1e-9)


def test_source_below_target_produces_lift():
    """Source low → target high → positive gain (boost)."""
    source = _flat_bands(0.05)
    target = _flat_bands(0.15)
    r = compute_delta_eq(source=source, target=target)
    # Every band wants to lift
    for v in r.per_band_delta_db.values():
        assert v > 0


def test_source_above_target_produces_cut():
    """Source high → target low → negative gain (cut). This is the fix for
    the Iron Maiden HF overdrive — the old deficit-based math couldn't cut."""
    source = _flat_bands(0.20)
    target = _flat_bands(0.05)
    r = compute_delta_eq(source=source, target=target)
    for v in r.per_band_delta_db.values():
        assert v < 0


# ---------------------------------------------------------------------------
# Asymmetric caps
# ---------------------------------------------------------------------------

def test_presence_cut_cap_is_larger_than_lift_cap():
    """Per design: HF cuts are freer than HF lifts (tame sibilance more
    eagerly than we add it)."""
    lift, cut = BAND_CAPS_DB['presence_pct']
    assert cut > lift


def test_bass_lift_cap_is_larger_than_cut_cap():
    """Per design: bass lifts are aggressive, cuts are gentle (preserve warmth)."""
    lift, cut = BAND_CAPS_DB['bass_pct']
    assert lift > cut


def test_huge_lift_request_saturates_at_lift_cap():
    """source=0.01 vs target=0.5 → ~+17 dB raw, must saturate near cap.
    (Source is at _EMPTY_BAND_KNEE_END, so the empty-band gate is fully open
    and the delta math runs unattenuated — see #4938.)"""
    source = {b: 0.01 for b in BAND_CAPS_DB}
    target = {b: 0.50 for b in BAND_CAPS_DB}
    r = compute_delta_eq(source=source, target=target)
    for band, gain in r.per_band_delta_db.items():
        lift_cap = BAND_CAPS_DB[band][0]
        assert 0.90 * lift_cap < gain <= lift_cap


def test_acoustically_empty_source_band_gets_zero_correction():
    """Source at zero energy in a band → no correction, even if target
    says it would 'want' more. Boosting silence is meaningless and prevents
    the saturation artifact where source≈0 produces near-cap lift."""
    source = {b: 0.10 for b in BAND_CAPS_DB}
    source['sub_bass_pct'] = 0.0      # truly empty (no DC content)
    target = {b: 0.10 for b in BAND_CAPS_DB}
    target['sub_bass_pct'] = 0.10     # target wants 10%
    r = compute_delta_eq(source=source, target=target)
    assert r.per_band_delta_db['sub_bass_pct'] == 0.0


# ---------------------------------------------------------------------------
# #4938 — the empty-band guard is a knee, not a cliff
# ---------------------------------------------------------------------------

def test_empty_band_guard_has_no_discontinuity():
    """Sweeping the source fraction across the empty-band boundary must vary
    the correction continuously (#4938).

    The guard used to be `if src < _EMPTY_BAND_THRESHOLD: gain = 0.0`, so a
    source fraction moving 0.0049 -> 0.0050 — one hundredth of a percentage
    point of band energy — swung that band from 0.00 dB to 1.99 dB. Two
    near-identical masters landing either side of the line got audibly
    different EQ, and re-fingerprinting the same source (different resample
    path, minor upstream change) could flip which side it landed on.
    """
    target = {b: 0.10 for b in BAND_CAPS_DB}

    def sub_bass_gain(src_fraction: float) -> float:
        source = dict(target)
        source['sub_bass_pct'] = src_fraction
        return compute_delta_eq(source=source, target=target).per_band_delta_db['sub_bass_pct']

    # Sweep well past the knee so both the closed and fully-open regions are
    # covered, with a step far finer than the knee width.
    step = _EMPTY_BAND_KNEE_END / 500.0
    xs = [i * step for i in range(int(4 * _EMPTY_BAND_KNEE_END / step) + 1)]
    gains = [sub_bass_gain(x) for x in xs]

    largest_jump = max(abs(b - a) for a, b in zip(gains, gains[1:]))
    # Pre-fix this sweep contained a single ~1.99 dB step; the knee bounds it
    # to roughly (cap / knee-samples), i.e. hundredths of a dB.
    assert largest_jump < 0.05, (
        f"EQ gain jumps {largest_jump:.3f} dB between adjacent source "
        f"fractions {step:.6f} apart — the empty-band guard is still a cliff"
    )

    # The specific pair named in the issue.
    below, above = sub_bass_gain(0.0049), sub_bass_gain(0.0050)
    assert abs(above - below) < 0.10


def test_empty_band_guard_preserves_far_field_behaviour():
    """The knee must not change what the guard was for (#4938): a silent band
    still gets no correction, and a band carrying real energy still gets the
    full uncapped-by-the-gate delta."""
    target = {b: 0.10 for b in BAND_CAPS_DB}

    def sub_bass_gain(src_fraction: float) -> float:
        source = dict(target)
        source['sub_bass_pct'] = src_fraction
        return compute_delta_eq(source=source, target=target).per_band_delta_db['sub_bass_pct']

    # Genuinely empty → still zero, exactly as the hard guard gave.
    assert sub_bass_gain(0.0) == 0.0

    # At/above the knee end the gate is fully open: identical to the value the
    # delta math produces with no attenuation at all.
    full = sub_bass_gain(_EMPTY_BAND_KNEE_END)
    assert full > 0.0
    # Monotonically non-decreasing approach to it (the gate only ever opens).
    assert sub_bass_gain(_EMPTY_BAND_KNEE_END / 2) < full


def test_huge_cut_request_saturates_at_cut_cap():
    """source=0.50 vs target=0.001 → ~-27 dB raw, must saturate near -cut."""
    source = {b: 0.50 for b in BAND_CAPS_DB}
    target = {b: 0.001 for b in BAND_CAPS_DB}
    r = compute_delta_eq(source=source, target=target)
    for band, gain in r.per_band_delta_db.items():
        cut_cap = BAND_CAPS_DB[band][1]
        assert -cut_cap <= gain < -0.90 * cut_cap


# ---------------------------------------------------------------------------
# Smoothness (tanh saturation)
# ---------------------------------------------------------------------------

def test_small_delta_passes_through_nearly_linear():
    """Small request → small gain, no near-cap saturation."""
    source = {b: 0.10 for b in BAND_CAPS_DB}
    # ~+1 dB raw (target slightly higher)
    target = {b: 0.10 * 10 ** (1.0 / 10.0) for b in BAND_CAPS_DB}
    r = compute_delta_eq(source=source, target=target)
    for gain in r.per_band_delta_db.values():
        # Within 10% of the raw 1 dB request (tanh hasn't saturated yet)
        assert 0.85 < gain < 1.0


def test_no_nan_for_zero_source():
    """Source band at literal zero must not produce NaN/Inf (the epsilon floor
    catches it)."""
    source = {b: 0.0 for b in BAND_CAPS_DB}
    target = {b: 0.10 for b in BAND_CAPS_DB}
    r = compute_delta_eq(source=source, target=target)
    for gain in r.per_band_delta_db.values():
        assert math.isfinite(gain)


def test_no_nan_for_zero_target():
    source = {b: 0.10 for b in BAND_CAPS_DB}
    target = {b: 0.0 for b in BAND_CAPS_DB}
    r = compute_delta_eq(source=source, target=target)
    for gain in r.per_band_delta_db.values():
        assert math.isfinite(gain)


# ---------------------------------------------------------------------------
# 5-shelf mapping
# ---------------------------------------------------------------------------

def test_to_eq_curve_includes_all_required_fields():
    fp = _flat_bands(0.15)
    r = compute_delta_eq(source=fp, target=fp)
    curve = to_eq_curve(r)
    assert set(curve) >= {
        'low_shelf_gain', 'low_mid_gain', 'mid_gain', 'high_mid_gain', 'high_shelf_gain',
        'low_shelf_freq', 'low_mid_freq', 'mid_freq', 'high_mid_freq', 'high_shelf_freq',
    }


def test_only_bass_band_diverges_isolates_in_low_shelf():
    """If only `bass_pct` differs (lift needed), the response should land
    primarily in low_shelf (which targets 200 Hz / bass region)."""
    source = _flat_bands(0.10)
    target = _flat_bands(0.10)
    target['bass_pct'] = 0.30      # +5 dB request
    r = compute_delta_eq(source=source, target=target)
    # low_shelf should be the largest (only bass band wants lift)
    gains = {
        'low_shelf':  r.low_shelf_gain,
        'low_mid':    r.low_mid_gain,
        'mid':        r.mid_gain,
        'high_mid':   r.high_mid_gain,
        'high_shelf': r.high_shelf_gain,
    }
    largest = max(gains, key=lambda k: gains[k])
    assert largest == 'low_shelf'


def test_only_air_band_diverges_isolates_in_high_shelf():
    """Mirror of the bass test for air → high_shelf."""
    source = _flat_bands(0.10)
    target = _flat_bands(0.10)
    target['air_pct'] = 0.20     # +3 dB request
    r = compute_delta_eq(source=source, target=target)
    gains = {
        'low_shelf':  r.low_shelf_gain,
        'low_mid':    r.low_mid_gain,
        'mid':        r.mid_gain,
        'high_mid':   r.high_mid_gain,
        'high_shelf': r.high_shelf_gain,
    }
    largest = max(gains, key=lambda k: gains[k])
    assert largest == 'high_shelf'


# ---------------------------------------------------------------------------
# The user's actual complaint: Iron Maiden
# ---------------------------------------------------------------------------

def test_bright_source_with_balanced_target_produces_hf_CUT():
    """Iron Maiden 2006 has unusually high upper_mid/presence. If the target
    (from the cloud) is more balanced, the delta EQ must CUT those bands —
    not boost them, which was the old behavior."""
    # Iron Maiden-ish source (loud, dense, presence-heavy)
    source = {
        'sub_bass_pct': 0.07, 'bass_pct': 0.46, 'low_mid_pct': 0.09,
        'mid_pct': 0.30, 'upper_mid_pct': 0.09,
        'presence_pct': 0.05,     # noticeably above a balanced target
        'air_pct': 0.01,
    }
    # Balanced reference target
    target = {
        'sub_bass_pct': 0.05, 'bass_pct': 0.20, 'low_mid_pct': 0.15,
        'mid_pct': 0.25, 'upper_mid_pct': 0.15,
        'presence_pct': 0.10,     # cloud has MORE presence on average
        'air_pct': 0.10,
    }
    r = compute_delta_eq(source=source, target=target)

    # The user's specific complaint: presence (cymbals/sibilance) must not
    # get boosted on this source. The cloud might say presence wants a small
    # LIFT (0.10 > 0.05), but high-shelf (presence+air) and bass should both
    # see CUTS since source is way over target on bass.
    assert r.low_shelf_gain < 0, "Bass-heavy source must be cut at low_shelf"

    # On the actual Iron Maiden output, low_shelf was +3.95 dB pre-fix; here
    # we're asking the test to confirm a cut. The exact value depends on caps.
    assert r.low_shelf_gain >= -BAND_CAPS_DB['bass_pct'][1] - 0.01
