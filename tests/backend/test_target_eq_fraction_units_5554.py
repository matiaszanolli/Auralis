"""#5554 — mastering-target EQ must treat band shares as fractions, not percent.

The fingerprint's ``*_pct`` fields are 0-1 fractions. ``generate_targets_from_fingerprint``
compared them with percent-scaled ideals (5.0 ... 22.0) and a 0.5 dB-per-unit
slope, so every band saturated at the +-6 dB clamp and every track received the
same content-independent tilt.

#5695: the ideals are the 512-track corpus medians shared with the per-chunk EQ
path (auralis/dsp/constants.CORPUS_BAND_CENTERS).

Both paths now use ONE law (``eq_curve_from_fingerprint``: a log-ratio from the
corpus center, saturated per band), because the earlier linear law (0.5 dB per
percentage point) asked a track whose mids were 17 points over the center for -6 dB
and its bass 14 points under for +12 dB -- on a record rated excellent.
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
BANDS = ('low_shelf_gain', 'low_mid_gain', 'mid_gain', 'high_mid_gain', 'high_shelf_gain')


def _fingerprint(**overrides: float) -> dict[str, float]:
    fp = {f'{band}_pct': ideal for band, ideal in IDEALS.items()}
    fp.update({'lufs': -14.0, 'crest_db': 12.0})
    fp.update(overrides)
    return fp


def _eq(**overrides: float) -> dict[str, float]:
    return MasteringTargetService().generate_targets_from_fingerprint(_fingerprint(**overrides))['eq_curve_db']


def test_ideal_balance_needs_no_eq() -> None:
    assert _eq() == {band: pytest.approx(0.0, abs=1e-6) for band in BANDS}


def test_fractions_not_percent() -> None:
    """A band 0.02 off its center (2 percentage points) must not saturate."""
    eq = _eq(bass_pct=IDEALS['bass'] - 0.02)
    assert 0.0 < eq['low_shelf_gain'] < 1.0
    assert eq['mid_gain'] == pytest.approx(0.0, abs=1e-6)  # other bands untouched


def test_the_correction_follows_the_sign_of_the_error() -> None:
    assert _eq(bass_pct=IDEALS['bass'] - 0.1)['low_shelf_gain'] > 0.0   # bass-light: boost
    assert _eq(bass_pct=IDEALS['bass'] + 0.1)['low_shelf_gain'] < 0.0   # bass-heavy: cut
    assert _eq(mid_pct=IDEALS['mid'] + 0.1)['mid_gain'] < 0.0


def test_extreme_error_stays_inside_the_band_authority() -> None:
    assert _eq(bass_pct=0.9)['low_shelf_gain'] >= -5.0
    assert _eq(bass_pct=0.001)['low_shelf_gain'] <= 5.0


def test_a_large_share_difference_is_not_a_large_correction() -> None:
    """The linear law turned 17 points of mid energy into -6 dB; a track with a
    dominant mid range is still the same record."""
    eq = _eq(mid_pct=IDEALS['mid'] + 0.17)
    assert -2.0 <= eq['mid_gain'] < 0.0


def test_different_tracks_get_different_eq() -> None:
    assert _eq(bass_pct=0.40) != _eq(bass_pct=0.50)


def test_the_air_share_does_not_drive_the_high_shelf() -> None:
    """The fingerprint analyses at 22.05 kHz, so the 8-20 kHz band stops at 11 kHz."""
    assert _eq(air_pct=0.0)['high_shelf_gain'] == 0.0
    assert _eq(air_pct=0.2)['high_shelf_gain'] == 0.0


def test_a_treble_preference_still_reaches_the_high_shelf() -> None:
    from types import SimpleNamespace

    from auralis.core.processing.parameter_generator_eq import generate_eq_curve
    from auralis.core.processing.continuous_space_types import PreferenceVector

    coords = SimpleNamespace(fingerprint=_fingerprint())
    flat = generate_eq_curve(coords, None)['high_shelf_gain']
    boosted = generate_eq_curve(coords, PreferenceVector(treble_boost=1.0))['high_shelf_gain']

    assert flat == 0.0
    assert boosted > 0.0
