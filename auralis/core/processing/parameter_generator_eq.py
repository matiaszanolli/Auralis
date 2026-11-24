"""
EQ Law
~~~~~~

The single law for "what this track's tonal balance needs": five EQ gains from a
fingerprint's band shares and the band centers they are pulled toward.

Every render path calls ``eq_curve_from_fingerprint`` through
``mastering_targets.generate_targets_from_fingerprint`` -- streaming fixed
targets, whole-file jobs and the per-chunk fallback -- so no two paths can tone
the same fingerprint differently. The centers are the corpus centers, or the soft
k-NN target when a reference cloud exists. A second band-to-gain law used to run
on the reference-cloud path (``delta_eq``) and put air-share correction back on
the high shelf this one deliberately leaves flat (#6356).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Mapping

import numpy as np

from ...dsp.constants import CORPUS_BAND_CENTERS


def _signed_band_gain(
    source_fraction: float,
    center_fraction: float,
    limit_db: float,
    transition_db: float = 6.0,
) -> float:
    """Return a smooth signed gain from a source/center energy ratio."""
    epsilon = 1e-8
    delta_db = 10.0 * np.log10(
        (center_fraction + epsilon) / (source_fraction + epsilon)
    )
    return float(limit_db * np.tanh(delta_db / transition_db))


def band_centers_from_target(target: Mapping[str, float] | None) -> dict[str, float]:
    """``CORPUS_BAND_CENTERS``-keyed centers from a k-NN target's ``*_pct`` shares.

    A band the target does not carry keeps its corpus center; None (no cloud)
    gives the corpus centers themselves.
    """
    if not target:
        return dict(CORPUS_BAND_CENTERS)
    return {
        band: float(target.get(f'{band}_pct', center))
        for band, center in CORPUS_BAND_CENTERS.items()
    }


def _band_gains(fp: Mapping[str, float], centers: Mapping[str, float]) -> dict[str, float]:
    """Raw signed gain per EQ band (dB) from a fingerprint's band shares.

    The centers are the origin of a signed continuous correction, not an ideal
    profile or a pass/fail range. ``tanh`` approaches the DSP envelope smoothly
    instead of clipping bands into deficit/excess classes. A band missing from
    the fingerprint sits at its own center, i.e. gets no correction.
    """
    def share(band: str) -> float:
        return float(fp.get(f'{band}_pct', centers[band]))

    return {
        'low_shelf_gain': _signed_band_gain(share('bass'), centers['bass'], 4.0),
        'low_mid_gain': _signed_band_gain(share('low_mid'), centers['low_mid'], 2.0),
        'mid_gain': _signed_band_gain(share('mid'), centers['mid'], 2.0),
        # One combined band: the corpus pins its center for the SUM of the two
        # (presence alone has no separate measurement).
        'high_mid_gain': _signed_band_gain(
            share('upper_mid') + share('presence'),
            centers['upper_mid'] + centers['presence'],
            3.0,
        ),
        # No correction is derived from the air share. The fingerprint analyses at
        # 22.05 kHz, so its 8-20 kHz band stops at 11 kHz: a tiny, noisy share whose
        # corpus center comes from the same truncated spectrum. On six reference
        # records it was the largest remaining EQ move on excellent masters (+1.8 dB
        # on one, +2.5 dB on another) and the cause of every remaining bench miss.
        # It stays flat with a reference-cloud target too: the references' air
        # shares are truncated the same way.
        # TODO(#6721): derive it once the fingerprint measures above 11 kHz.
        'high_shelf_gain': 0.0,
    }


#: Per-band authority (dB): the most a band's gain can reach after saturation.
_BAND_AUTHORITY_DB: dict[str, float] = {
    'low_shelf_gain': 5.0, 'low_mid_gain': 3.0, 'mid_gain': 2.0,
    'high_mid_gain': 4.0, 'high_shelf_gain': 4.0,
}


def _saturate(gains: dict[str, float]) -> dict[str, float]:
    return {
        band: float(limit * np.tanh(gains[band] / limit))
        for band, limit in _BAND_AUTHORITY_DB.items()
    }


#: The 2-4 kHz (high-mid) correction is asymmetric, from gain-matched listening
#: (2026-11): a CUT is twice the symmetric law and a BOOST half of it. On a crowded
#: track (Overkill "Where It Hurts", share 6 dB over the center) the cut alone at
#: twice the law (-4.1 dB) sounded as good as the whole plan at twice; on a milder
#: one (Iron Maiden "Holy Smoke", 1.7 dB over) twice was no worse than the law.
#: Boosts amplify what a thin or overdriven vintage source already has (Velvet
#: Underground "Femme Fatale", 7 dB under): half strength at most. It also halves
#: the boost on excellent masters that sit a little under the center. Scaling the
#: saturated gain keeps both sides bounded (cuts by 2 x the 4 dB authority) and
#: continuous through zero. Other bands keep the symmetric law: no evidence there.
_HIGH_MID_CUT_SCALE = 2.0
_HIGH_MID_BOOST_SCALE = 0.5


def _asymmetric_high_mid(curve: dict[str, float]) -> dict[str, float]:
    gain = curve['high_mid_gain']
    scale = _HIGH_MID_CUT_SCALE if gain < 0.0 else _HIGH_MID_BOOST_SCALE
    return {**curve, 'high_mid_gain': gain * scale}


def eq_curve_from_fingerprint(
    fp: Mapping[str, float],
    centers: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """The five EQ gains (dB) for a track.

    Args:
        fp: The track's fingerprint (only the ``*_pct`` band shares are read).
        centers: Band shares to pull toward, keyed like ``CORPUS_BAND_CENTERS``;
            None means the corpus centers.
    """
    return _asymmetric_high_mid(
        _saturate(_band_gains(fp, centers if centers is not None else CORPUS_BAND_CENTERS))
    )
