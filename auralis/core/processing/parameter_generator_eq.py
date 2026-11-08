"""
EQ-Family Parameter Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Frequency-curve parameter generation for the continuous processing space:
the legacy deficit-based curve and the delta-from-target curve, plus the
EQ blend factor.

Split out of ``parameter_generator.py`` (#4511) so each parameter family
lives in its own module behind the ``ContinuousParameterGenerator`` facade.
Pure functions of their inputs — no state, no behavior change from the
original methods they replace.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

from ...dsp.constants import CORPUS_BAND_CENTERS
from .continuous_space_types import PreferenceVector, ProcessingCoordinates

# Corpus-calibrated band centers live in dsp/constants.CORPUS_BAND_CENTERS —
# the single table shared with the fixed-target path (#5695). When a band is
# missing the fallback is its own center, i.e. a zero correction --
# deliberately not the FingerprintUnpacker typical-track default.
_LOW_MID_CENTER = CORPUS_BAND_CENTERS['low_mid']
_UPPER_MID_CENTER = CORPUS_BAND_CENTERS['upper_mid']


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


def _band_gains(fp: dict[str, float]) -> dict[str, float]:
    """Raw signed gain per EQ band (dB) from a fingerprint's band shares.

    Robust centers from the deterministic 512-track corpus sample. They define the
    origin of a signed continuous correction, not an ideal profile or a pass/fail
    range. ``tanh`` approaches the DSP envelope smoothly instead of clipping bands
    into deficit/excess classes.
    """
    high_mid_source = fp.get('upper_mid_pct', _UPPER_MID_CENTER) + fp['presence_pct']
    return {
        'low_shelf_gain': _signed_band_gain(fp['bass_pct'], CORPUS_BAND_CENTERS['bass'], 4.0),
        'low_mid_gain': _signed_band_gain(
            fp.get('low_mid_pct', _LOW_MID_CENTER), _LOW_MID_CENTER, 2.0
        ),
        'mid_gain': _signed_band_gain(fp['mid_pct'], CORPUS_BAND_CENTERS['mid'], 2.0),
        'high_mid_gain': _signed_band_gain(
            high_mid_source,
            # Combined center: the corpus pins 0.1030 for the SUM of the two
            # bands (presence alone has no separate measurement).
            CORPUS_BAND_CENTERS['upper_mid'] + CORPUS_BAND_CENTERS['presence'],
            3.0,
        ),
        # No correction is derived from the air share. The fingerprint analyses at
        # 22.05 kHz, so its 8-20 kHz band stops at 11 kHz: a tiny, noisy share whose
        # corpus center comes from the same truncated spectrum. On six reference
        # records it was the largest remaining EQ move on excellent masters (+1.8 dB
        # on one, +2.5 dB on another) and the cause of every remaining bench miss.
        # User treble preferences still reach the shelf (``generate_eq_curve``).
        # Revisit once the fingerprint measures above 11 kHz (no tracking issue yet).
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


def eq_curve_from_fingerprint(fp: dict[str, float]) -> dict[str, float]:
    """The five EQ gains (dB) for a track, with no user preference applied.

    The single law for "what this track's tonal balance needs": the per-chunk
    path (``generate_eq_curve``) adds preference on top of it, and the fixed-target
    path the app streams with (``mastering_target_generation``) uses it as is, so
    the two cannot disagree about the same fingerprint.
    """
    return _saturate(_band_gains(fp))


def generate_eq_curve(
    coords: ProcessingCoordinates,
    preference: PreferenceVector | None,
) -> dict[str, float]:
    """
    Generate frequency-specific EQ adjustments.

    Strategy:
    - Analyze what's missing (bass deficit, air deficit)
    - Boost deficits to bring balance
    - Respect user bass/treble preferences
    - Use actual frequency percentages from fingerprint

    Args:
        coords: Processing space coordinates
        preference: Optional user preference

    Returns:
        Dictionary with EQ curve parameters
    """
    gains = _band_gains(coords.fingerprint)
    low_shelf_gain, high_shelf_gain = gains['low_shelf_gain'], gains['high_shelf_gain']
    high_mid_gain = gains['high_mid_gain']

    # Apply user preference adjustments
    if preference:
        # Bass preference (0 to 1) adds extra bass boost
        low_shelf_gain += preference.bass_boost * 2.0

        # Treble preference (0 to 1) adds extra treble boost
        high_shelf_gain += preference.treble_boost * 2.0
        high_mid_gain += preference.treble_boost * 1.5

        # Spectral bias shifts overall tonality
        if preference.spectral_bias > 0:  # Brighter
            high_shelf_gain += preference.spectral_bias * 1.5
            low_shelf_gain -= preference.spectral_bias * 1.0
        else:  # Darker
            low_shelf_gain += abs(preference.spectral_bias) * 1.5
            high_shelf_gain -= abs(preference.spectral_bias) * 1.0

    saturated = _saturate({
        **gains,
        'low_shelf_gain': low_shelf_gain,
        'high_mid_gain': high_mid_gain,
        'high_shelf_gain': high_shelf_gain,
    })
    return {
        # Gains (dB)
        **saturated,

        # Frequencies (Hz)
        'low_shelf_freq': 200,
        'low_mid_freq': 500,
        'mid_freq': 1500,
        'high_mid_freq': 4000,
        'high_shelf_freq': 8000,
    }


def generate_eq_curve_from_target(
    coords: ProcessingCoordinates,
    target_spectrum: dict[str, float],
    preference: PreferenceVector | None,
) -> dict[str, float]:
    """Compute the 5-shelf curve via delta-from-target (Phase 4).

    Replaces the deficit-based math when the mastering pipeline has a
    reference cloud and was able to derive a target. Symmetric (can cut),
    capped per-band, smoothly saturated via tanh — see delta_eq.py.

    User preference still applies as additive bias on top of the delta
    curve, but with reduced strength since the cloud already encodes
    most of the "what should this sound like" intent.
    """
    from .delta_eq import compute_delta_eq, to_eq_curve

    delta_result = compute_delta_eq(coords.fingerprint, target_spectrum)
    curve = to_eq_curve(delta_result)

    # Apply user preference adjustments at half-strength (cloud carries
    # most of the intent; preference becomes a gentle nudge, not the
    # primary signal it was in the deficit-based path).
    if preference is not None:
        curve['low_shelf_gain']  += preference.bass_boost * 1.0
        curve['high_shelf_gain'] += preference.treble_boost * 1.0
        curve['high_mid_gain']   += preference.treble_boost * 0.75
        if preference.spectral_bias > 0:        # brighter
            curve['high_shelf_gain'] += preference.spectral_bias * 0.75
            curve['low_shelf_gain']  -= preference.spectral_bias * 0.5
        elif preference.spectral_bias < 0:      # darker
            curve['low_shelf_gain']  += abs(preference.spectral_bias) * 0.75
            curve['high_shelf_gain'] -= abs(preference.spectral_bias) * 0.5

    # Re-clamp to the existing ProcessingParameters envelope so
    # downstream EQProcessor sees values it expects.
    curve['low_shelf_gain']  = float(np.clip(curve['low_shelf_gain'],  -5.0, 5.0))
    curve['low_mid_gain']    = float(np.clip(curve['low_mid_gain'],    -3.0, 3.0))
    curve['mid_gain']        = float(np.clip(curve['mid_gain'],        -2.0, 2.0))
    curve['high_mid_gain']   = float(np.clip(curve['high_mid_gain'],   -4.0, 4.0))
    curve['high_shelf_gain'] = float(np.clip(curve['high_shelf_gain'], -4.0, 4.0))

    return curve


def calculate_eq_blend(coords: ProcessingCoordinates) -> float:
    """
    Calculate how much EQ to apply.

    Strategy:
    - Unbalanced material: More EQ (blend closer to 1.0)
    - Already balanced: Less EQ (blend closer to 0.5)

    Args:
        coords: Processing space coordinates

    Returns:
        EQ blend factor (0.0 to 1.0)
    """
    fp = coords.fingerprint

    epsilon = 1e-8
    deviations = (
        abs(np.log((fp['bass_pct'] + epsilon) / CORPUS_BAND_CENTERS['bass'])),
        abs(np.log((fp['air_pct'] + epsilon) / CORPUS_BAND_CENTERS['air'])),
        abs(np.log((fp['mid_pct'] + epsilon) / CORPUS_BAND_CENTERS['mid'])),
    )
    mean_deviation = float(np.mean(deviations))
    eq_blend = 0.35 + 0.55 * (1.0 - np.exp(-mean_deviation))

    return float(eq_blend)
