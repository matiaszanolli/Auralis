"""
Dynamics-Family Parameter Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Loudness targets, compression, expansion, dynamics blend and limiter
parameters for the continuous processing space.

Split out of ``parameter_generator.py`` (#4511) so each parameter family
lives in its own module behind the ``ContinuousParameterGenerator`` facade.
Pure functions of ``(coords, preference)`` — no state, no behavior change
from the original methods they replace.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from .continuous_space import PreferenceVector, ProcessingCoordinates


def calculate_target_lufs(
    coords: ProcessingCoordinates,
    preference: PreferenceVector | None,
) -> float:
    """
    Calculate target LUFS based on input energy and dynamic range.

    The lift approaches a dynamics-aware maximum smoothly as the source
    moves below the reference loudness. No source category or coordinate
    boundary selects a different formula.

    Args:
        coords: Processing space coordinates
        preference: Optional user preference

    Returns:
        Target LUFS value
    """
    dynamics = coords.dynamic_range
    fp = coords.fingerprint

    input_lufs = fp.get('lufs', -14.0)
    reference_lufs = -12.0
    softness_db = 0.75
    loudness_gap = reference_lufs - input_lufs
    desired_lift = softness_db * np.logaddexp(
        0.0, loudness_gap / softness_db
    )
    maximum_lift = 8.25 - dynamics
    gain_db = maximum_lift * np.tanh(desired_lift / maximum_lift)
    target_lufs = input_lufs + gain_db

    # Apply user loudness preference if provided
    # This is applied AFTER automatic boost calculation
    if preference:
        # Loudness bias affects target (-1 = -2dB quieter, +1 = +2dB louder)
        preference_adjustment = preference.loudness_bias * 2.0
        target_lufs += preference_adjustment

    # Clamp to reasonable range
    # Minimum: -28 dB (very quiet material)
    # Maximum: -2 dB (prevent excessive clipping risk)
    return float(np.clip(target_lufs, -28.0, -2.0))


def calculate_peak_target(
    coords: ProcessingCoordinates,
    preference: PreferenceVector | None,
) -> float:
    """
    Calculate peak normalization target.

    Strategy:
    - Dynamic material: More headroom (-1.0 to -0.7 dB)
    - Compressed material: Less headroom (-0.5 to -0.2 dB)

    Args:
        coords: Processing space coordinates
        preference: Optional user preference

    Returns:
        Peak target in dBFS (negative value)
    """
    dynamics = coords.dynamic_range

    # More dynamics = more headroom
    # Dynamic (1.0) → -1.0 dB
    # Compressed (0.0) → -0.3 dB
    base_peak = -1.0 + (1.0 - dynamics) * 0.7

    # Apply loudness preference (affects headroom slightly)
    preference_adjustment = 0.0
    if preference:
        # Louder preference = less headroom
        preference_adjustment = preference.loudness_bias * 0.2

    peak_target = base_peak + preference_adjustment

    # Clamp to safe range
    return float(np.clip(peak_target, -1.5, -0.2))


def generate_compression(
    coords: ProcessingCoordinates,
    preference: PreferenceVector | None,
) -> dict[str, float]:
    """
    Generate compression parameters.

    Compression strength follows a smooth bell over the dynamics axis:
    minimal near either extreme and strongest around the corpus center.

    Args:
        coords: Processing space coordinates
        preference: Optional user preference

    Returns:
        Compression parameters dictionary
    """
    dynamics = coords.dynamic_range

    # Adjust dynamics based on user preference
    effective_dynamics = dynamics
    if preference:
        # Dynamic bias affects how much we compress
        # Positive bias (preserve dynamics) → treat as more dynamic
        # Negative bias (allow compression) → treat as less dynamic
        effective_dynamics += preference.dynamic_bias * 0.3
        effective_dynamics = np.clip(effective_dynamics, 0.0, 1.0)

    compression_response = np.exp(
        -0.5 * ((effective_dynamics - 0.55) / 0.18) ** 2
    )
    return {
        'ratio': float(1.0 + 0.8 * compression_response),
        'threshold': float(-18.0 - 8.0 * effective_dynamics),
        'attack': float(12.0 + 18.0 * effective_dynamics),
        'release': float(120.0 + 130.0 * effective_dynamics),
        'amount': float(0.55 * compression_response),
    }


def generate_expansion(
    coords: ProcessingCoordinates,
    preference: PreferenceVector | None,
) -> dict[str, float]:
    """
    Generate expansion parameters (de-mastering).

    Expansion strength decays continuously as measured dynamics increase.

    Args:
        coords: Processing space coordinates
        preference: Optional user preference

    Returns:
        Expansion parameters dictionary
    """
    dynamics = coords.dynamic_range

    # Adjust dynamics based on user preference
    effective_dynamics = dynamics
    if preference:
        # Dynamic bias affects expansion threshold
        effective_dynamics += preference.dynamic_bias * 0.3
        effective_dynamics = np.clip(effective_dynamics, 0.0, 1.0)

    inverse_dynamics = 1.0 - effective_dynamics
    return {
        'target_crest_increase': float(3.0 * inverse_dynamics),
        'amount': float(0.85 * inverse_dynamics ** 2),
    }


def calculate_dynamics_blend(
    coords: ProcessingCoordinates,
    preference: PreferenceVector | None,
) -> float:
    """
    Calculate dynamics processing blend.

    Args:
        coords: Processing space coordinates
        preference: Optional user preference

    Returns:
        Dynamics blend factor (0.0 to 1.0)
    """
    # Base blend from dynamic range
    # Less dynamic = more processing
    base_blend = 0.3 + ((1.0 - coords.dynamic_range) * 0.4)

    # User preference can increase/decrease
    if preference and preference.dynamic_bias != 0:
        # Positive bias (preserve dynamics) → less processing
        # Negative bias (allow compression) → more processing
        base_blend -= preference.dynamic_bias * 0.2

    return float(np.clip(base_blend, 0.2, 0.9))


def generate_limiter(coords: ProcessingCoordinates) -> dict[str, float]:
    """
    Generate limiter parameters.

    Strategy:
    - Dynamic material: Gentler limiting (-3 to -2 dB threshold)
    - Compressed material: Tighter limiting (-1.5 to -1 dB threshold)

    Args:
        coords: Processing space coordinates

    Returns:
        Limiter parameters dictionary
    """
    dynamics = coords.dynamic_range

    # More dynamics = gentler limiting (more headroom)
    threshold = -3.0 + ((1.0 - dynamics) * 1.5)  # -3 to -1.5 dB
    release = 120.0 - (dynamics * 40.0)          # 120ms to 80ms

    return {
        'threshold': threshold,
        'release': release,
    }
