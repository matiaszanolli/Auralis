"""#5554 — mastering-target EQ must treat band shares as fractions, not percent.

The fingerprint's ``*_pct`` fields are 0-1 fractions. ``generate_targets_from_fingerprint``
compared them with percent-scaled ideals (5.0 ... 22.0) and a 0.5 dB-per-unit
slope, so every band saturated at the +-6 dB clamp and every track received the
same content-independent tilt.
"""

import sys
from pathlib import Path

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.mastering_target_service import MasteringTargetService  # noqa: E402

IDEALS = {
    'sub_bass': 0.05, 'bass': 0.15, 'low_mid': 0.18, 'mid': 0.22,
    'upper_mid': 0.20, 'presence': 0.13, 'air': 0.07,
}


def _fingerprint(**overrides: float) -> dict[str, float]:
    fp = {f'{band}_pct': ideal for band, ideal in IDEALS.items()}
    fp.update({'lufs': -14.0, 'crest_db': 12.0})
    fp.update(overrides)
    return fp


def _eq(**overrides: float) -> dict[str, float]:
    return MasteringTargetService().generate_targets_from_fingerprint(_fingerprint(**overrides))['eq_adjustments_db']


def test_ideal_balance_needs_no_eq() -> None:
    assert _eq() == {band: pytest.approx(0.0, abs=1e-6) for band in IDEALS}


def test_adjustment_is_proportional_and_not_saturated() -> None:
    eq = _eq(bass_pct=0.25)  # 10 percentage points too much bass
    assert eq['bass'] == pytest.approx(-5.0)
    assert -6.0 < eq['bass'] < 0.0
    assert eq['mid'] == pytest.approx(0.0, abs=1e-6)  # other bands untouched


def test_small_error_gives_small_adjustment() -> None:
    assert _eq(presence_pct=0.11)['presence'] == pytest.approx(1.0)


def test_extreme_error_still_clamps() -> None:
    assert _eq(bass_pct=0.9)['bass'] == -6.0
    assert _eq(air_pct=0.0)['air'] == pytest.approx(3.5)


def test_different_tracks_get_different_eq() -> None:
    assert _eq(bass_pct=0.30) != _eq(bass_pct=0.05)
