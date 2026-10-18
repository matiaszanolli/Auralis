"""
Regression: _calculate_spectral_balance survives the denominator's zero
crossing and saturates on Inf (#5534)

Two defects from the #5505 guard's shape:

1. ``low_energy == -_ENERGY_EPSILON`` exactly made the denominator ``0.0``
   and the plain-float division raised ``ZeroDivisionError`` — uncaught up
   through ``process() -> _resolve_parameters()``, aborting the whole
   mastering call for that chunk/track.
2. Crossing the denominator from positive to negative abandoned the
   saturating curve for the flat neutral 0.5 — a ~0.35 jump between
   fingerprints that differ by a fraction of a percent of band energy.
   The positive-side limit is smooth saturation toward the high-energy
   asymptote; the negative side now continues that saturation via ±Inf
   instead of collapsing to neutral. ``_smooth_unit`` likewise maps ±Inf to
   the interval ends (as large-finite inputs already were) while keeping
   NaN -> neutral (#5505).
"""

import math

from auralis.core.processing.continuous_space import (
    ProcessingSpaceMapper,
    _smooth_unit,
)

EPS = 1e-8


def _fingerprint(low_energy: float, high_energy: float = 10.0) -> dict:
    return {
        'sub_bass_pct': 0.0,
        'bass_pct': low_energy - 0.1,   # low = sub_bass + bass + low_mid
        'low_mid_pct': 0.1,
        'upper_mid_pct': high_energy - 0.2,
        'presence_pct': 0.1,
        'air_pct': 0.1,
        'spectral_centroid': 0.5,
        'lufs': -14.0,
        'crest_db': 8.0,
    }


def test_zero_denominator_does_not_raise():
    """low_energy == -EPSILON exactly used to raise ZeroDivisionError."""
    mapper = ProcessingSpaceMapper()
    fp = _fingerprint(low_energy=0.1 - EPS - 0.1 + 0.1)  # sum = 0.1; see below
    # Construct the exact degenerate case: low_total == 0.0.
    fp['sub_bass_pct'] = 0.0
    fp['bass_pct'] = -EPS - 0.1
    fp['low_mid_pct'] = 0.1
    value = mapper.map_fingerprint_to_space(fp).spectral_balance  # must not raise
    assert 0.0 <= value <= 1.0


def test_negative_denominator_continues_the_saturation():
    """Just past the crossing the coordinate must stay on the high-energy
    asymptote (~0.85+), not jump ~0.35 down to the neutral 0.504."""
    mapper = ProcessingSpaceMapper()
    just_positive = mapper.map_fingerprint_to_space(
        _fingerprint(low_energy=+1e-6)
    ).spectral_balance
    just_negative = mapper.map_fingerprint_to_space(
        _fingerprint(low_energy=-1e-6)
    ).spectral_balance

    assert just_positive > 0.85
    assert just_negative > 0.85, (
        f"negative-side crossing collapsed to neutral: {just_negative}"
    )
    assert just_negative <= 1.0


def test_symmetric_numerator_crossing_saturates_low():
    """Crossing the numerator's zero must continue the saturating curve, not
    jump to the neutral 0.5. The blended coordinate has a centroid term, so
    assert continuity against the just-positive neighbour plus saturation
    toward the low end, rather than an absolute bound."""
    mapper = ProcessingSpaceMapper()
    just_positive = dict(_fingerprint(low_energy=10.0, high_energy=0.0))
    just_positive['upper_mid_pct'] = -0.1 + 1e-6
    just_positive['presence_pct'] = 0.05
    just_positive['air_pct'] = 0.05

    just_negative = dict(just_positive)
    just_negative['upper_mid_pct'] = -0.1 - 1e-6

    high_val = mapper.map_fingerprint_to_space(just_positive).spectral_balance
    low_val = mapper.map_fingerprint_to_space(just_negative).spectral_balance

    assert high_val < 0.45, f"just-positive should sit near the low asymptote: {high_val}"
    assert low_val <= high_val, (
        f"negative numerator jumped up instead of saturating: {low_val} vs {high_val}"
    )


def test_smooth_unit_saturates_on_inf():
    assert _smooth_unit(math.inf, 0.0, 1.0) == 1.0
    assert _smooth_unit(-math.inf, 0.0, 1.0) == 0.0
    # Large-but-finite inputs already saturate through tanh — Inf must agree.
    assert _smooth_unit(1e10, 0.0, 1.0) == 0.5 + 0.5 * math.tanh(1e10 / 2.0)
    # NaN stays neutral (#5505).
    assert _smooth_unit(math.nan, 0.0, 1.0) == 0.5
