"""
The 2-4 kHz correction is asymmetric: cuts at twice the symmetric law, boosts at half
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Calibrated by gain-matched listening (2026-11). On Overkill "Where It Hurts" (2-4 kHz
share 5.95 dB over the center) the cut alone at twice the law sounded as good as the
whole plan at twice; on Iron Maiden "Holy Smoke" (1.7 dB over) twice was no worse than
the law; on Velvet Underground "Femme Fatale" (7.3 dB under) a boost was wanted at half
strength at most. The anchors below are those tracks' measured shares.
"""

import numpy as np
import pytest

from auralis.core.processing import parameter_generator_eq as eq_law
from auralis.dsp.constants import CORPUS_BAND_CENTERS

CENTER = CORPUS_BAND_CENTERS['upper_mid'] + CORPUS_BAND_CENTERS['presence']


def _fingerprint(high_mid_excess_db: float) -> dict[str, float]:
    """Corpus-median bands, with the 2-4 kHz share ``excess`` dB over its center."""
    fp = {f'{band}_pct': share for band, share in CORPUS_BAND_CENTERS.items()}
    fp['upper_mid_pct'] = CENTER * 10 ** (high_mid_excess_db / 10) - fp['presence_pct']
    return fp


def _symmetric(fp):
    return eq_law._saturate(eq_law._band_gains(fp, CORPUS_BAND_CENTERS))


@pytest.mark.parametrize('excess', [0.5, 1.7, 3.0, 5.95, 9.0])
def test_a_cut_is_twice_the_symmetric_law(excess):
    fp = _fingerprint(excess)
    assert eq_law.eq_curve_from_fingerprint(fp)['high_mid_gain'] == pytest.approx(
        2.0 * _symmetric(fp)['high_mid_gain']
    )


@pytest.mark.parametrize('deficit', [0.5, 1.66, 4.0, 7.27])
def test_a_boost_is_half_the_symmetric_law(deficit):
    fp = _fingerprint(-deficit)
    assert eq_law.eq_curve_from_fingerprint(fp)['high_mid_gain'] == pytest.approx(
        0.5 * _symmetric(fp)['high_mid_gain']
    )


@pytest.mark.parametrize('excess, expected', [
    (5.95, -4.12),   # Where It Hurts: the cut-only x2 audition, preferred
    (1.70, -1.64),   # Holy Smoke: x2, no worse than x1
    (-7.27, +1.11),  # Femme Fatale: half strength
])
def test_the_listening_anchors(excess, expected):
    assert eq_law.eq_curve_from_fingerprint(_fingerprint(excess))['high_mid_gain'] == pytest.approx(
        expected, abs=0.05
    )


def test_only_the_high_mid_band_is_asymmetric():
    for excess in (-6.0, 6.0):
        fp = _fingerprint(excess)
        new, old = eq_law.eq_curve_from_fingerprint(fp), _symmetric(fp)
        for band in ('low_shelf_gain', 'low_mid_gain', 'mid_gain', 'high_shelf_gain'):
            assert new[band] == old[band]


def test_continuous_through_zero_and_bounded():
    excesses = np.linspace(-15.0, 15.0, 3001)
    gains = np.array([eq_law.eq_curve_from_fingerprint(_fingerprint(e))['high_mid_gain'] for e in excesses])
    assert np.max(np.abs(np.diff(gains))) < 0.05             # no step anywhere, including at 0
    assert np.all(np.diff(gains) <= 1e-12)                    # more excess never cuts less
    assert gains.min() > -2.0 * eq_law._BAND_AUTHORITY_DB['high_mid_gain']
    assert gains.max() < 0.5 * eq_law._BAND_AUTHORITY_DB['high_mid_gain']
