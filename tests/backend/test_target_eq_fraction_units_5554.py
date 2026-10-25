"""#5554 — mastering-target EQ must treat band shares as fractions, not percent.

The fingerprint's ``*_pct`` fields are 0-1 fractions. ``generate_targets_from_fingerprint``
compared them with percent-scaled ideals (5.0 ... 22.0) and a 0.5 dB-per-unit
slope, so every band saturated at the +-6 dB clamp and every track received the
same content-independent tilt.

#5695: the ideals are now the 512-track corpus medians shared with the
per-chunk EQ path (auralis/dsp/constants.CORPUS_BAND_CENTERS), not the
hand-set "ideal shares" this file used to pin — a corpus-median track got
bass clamped at -6 dB under those.
"""

import sys
from pathlib import Path

import pytest

from auralis.dsp.constants import CORPUS_BAND_CENTERS

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.mastering_target_service import MasteringTargetService  # noqa: E402

IDEALS = CORPUS_BAND_CENTERS


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
    # 2 percentage points below the bass center -> +1 dB (on the slope)
    eq = _eq(bass_pct=CORPUS_BAND_CENTERS['bass'] - 0.02)
    assert eq['bass'] == pytest.approx(1.0)
    assert 0.0 < eq['bass'] < 6.0
    assert eq['mid'] == pytest.approx(0.0, abs=1e-6)  # other bands untouched


def test_small_error_gives_small_adjustment() -> None:
    # 2 percentage points below the presence center -> +1 dB
    eq = _eq(presence_pct=CORPUS_BAND_CENTERS['presence'] - 0.02)
    assert eq['presence'] == pytest.approx(1.0)


def test_extreme_error_still_clamps() -> None:
    assert _eq(bass_pct=0.9)['bass'] == -6.0
    assert _eq(bass_pct=0.0)['bass'] == 6.0


def test_different_tracks_get_different_eq() -> None:
    # Both on the proportional slope, either side of the bass center.
    assert _eq(bass_pct=0.40) != _eq(bass_pct=0.50)
