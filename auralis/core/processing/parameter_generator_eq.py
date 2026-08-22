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
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from .continuous_space import PreferenceVector, ProcessingCoordinates


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
    fp = coords.fingerprint

    # Robust centers from the deterministic 512-track corpus sample. They
    # define the origin of a signed continuous correction, not an ideal
    # profile or a pass/fail range. ``tanh`` approaches the DSP envelope
    # smoothly instead of clipping bands into deficit/excess classes.
    low_shelf_gain = _signed_band_gain(fp['bass_pct'], 0.4561, 4.0)
    low_mid_gain = _signed_band_gain(
        fp.get('low_mid_pct', 0.1009), 0.1009, 2.0
    )
    mid_gain = _signed_band_gain(fp['mid_pct'], 0.1983, 2.0)
    high_mid_source = fp.get('upper_mid_pct', 0.0733) + fp['presence_pct']
    high_mid_gain = _signed_band_gain(high_mid_source, 0.1030, 3.0)
    high_shelf_gain = _signed_band_gain(fp['air_pct'], 0.0063, 3.0)

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

    return {
        # Gains (dB)
        'low_shelf_gain': float(5.0 * np.tanh(low_shelf_gain / 5.0)),
        'low_mid_gain': float(3.0 * np.tanh(low_mid_gain / 3.0)),
        'mid_gain': float(2.0 * np.tanh(mid_gain / 2.0)),
        'high_mid_gain': float(4.0 * np.tanh(high_mid_gain / 4.0)),
        'high_shelf_gain': float(4.0 * np.tanh(high_shelf_gain / 4.0)),

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
        abs(np.log((fp['bass_pct'] + epsilon) / 0.4561)),
        abs(np.log((fp['air_pct'] + epsilon) / 0.0063)),
        abs(np.log((fp['mid_pct'] + epsilon) / 0.1983)),
    )
    mean_deviation = float(np.mean(deviations))
    eq_blend = 0.35 + 0.55 * (1.0 - np.exp(-mean_deviation))

    return float(eq_blend)
