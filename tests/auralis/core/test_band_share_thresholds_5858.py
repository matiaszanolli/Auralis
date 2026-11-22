"""Band-share EQ rules discriminate between tracks (#5858).

apply_fingerprint_enhancements compared fractional band shares against percent
thresholds (bass_pct < 10.0, mid_pct < 20.0, presence+air < 10.0), so every real
track took the bass-light, mid-scooped and dark branches: +1.5 dB bass, +1.2 dB
mids and +1.8 dB treble on everything in hybrid mode.
"""

import pytest

from auralis.core.analysis.target_fingerprint_adjustments import (
    BAND_SHARE_TAILS,
    apply_fingerprint_enhancements,
)

BASE = {"bass_boost_db": 0.0, "midrange_clarity_db": 0.0, "treble_enhancement_db": 0.0}
# The median of the calibration sample (bass 0.459, mid 0.206, presence+air 0.038).
TYPICAL = {"bass_pct": 0.46, "mid_pct": 0.21, "presence_pct": 0.03, "air_pct": 0.008}


def _eq(fingerprint: dict[str, float]) -> tuple[float, float, float]:
    out = apply_fingerprint_enhancements(dict(BASE), fingerprint)
    return out["bass_boost_db"], out["midrange_clarity_db"], out["treble_enhancement_db"]


def test_a_typical_track_gets_no_band_correction():
    assert _eq(TYPICAL) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "change, expected",
    [
        ({"bass_pct": 0.20}, (1.5, 0.0, 0.0)),
        ({"bass_pct": 0.65}, (-1.0, 0.0, 0.0)),
        ({"mid_pct": 0.07}, (0.0, 1.2, 0.0)),
        ({"mid_pct": 0.40}, (0.0, -0.8, 0.0)),
        ({"presence_pct": 0.004, "air_pct": 0.001}, (0.0, 0.0, 1.8)),
        ({"presence_pct": 0.07, "air_pct": 0.02}, (0.0, 0.0, -1.2)),
    ],
    ids=["bass-light", "bass-heavy", "mid-scooped", "mid-heavy", "dark", "bright"],
)
def test_only_a_track_in_a_tail_is_corrected(change, expected):
    assert _eq(TYPICAL | change) == pytest.approx(expected)


def test_a_missing_band_share_skips_its_rule():
    assert _eq({}) == (0.0, 0.0, 0.0)
    assert _eq({"presence_pct": 0.001}) == (0.0, 0.0, 0.0)


def test_thresholds_are_fractions_of_the_spectrum():
    for low, high in BAND_SHARE_TAILS.values():
        assert 0.0 < low < high < 1.0
