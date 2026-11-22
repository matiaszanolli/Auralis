"""
Dynamics-Family Parameter Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The loudness target and the compression parameters for the continuous processing space. The
expansion, dynamics-blend, limiter and peak-target generators are gone: no stage read their output
(#6650).

Split out of ``parameter_generator.py`` (#4511) so each parameter family
lives in its own module behind the ``ContinuousParameterGenerator`` facade.
Pure functions of ``coords`` — no state, no behavior change from the original
methods they replace.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

from ...dsp.utils.loudness_targets import LOUD_THRESHOLD_LUFS
from ..utils.fingerprint_unpacker import FingerprintUnpacker
from .continuous_space_types import ProcessingCoordinates

# The loudest target a lift may reach (#6305).
TARGET_LUFS_CEILING = -2.0


def calculate_target_lufs(
    coords: ProcessingCoordinates,
) -> float:
    """
    Calculate target LUFS based on input energy and dynamic range.

    The lift approaches a dynamics-aware maximum (8.25 dB minus the dynamic
    range coordinate) smoothly as the source moves below the reference
    loudness, so the target rises with the source at every level. No source
    category or coordinate boundary selects a different formula. A lift never
    carries the target past ``TARGET_LUFS_CEILING``.

    Args:
        coords: Processing space coordinates

    Returns:
        Target LUFS value
    """
    dynamics = coords.dynamic_range
    fp = coords.fingerprint

    input_lufs = FingerprintUnpacker.from_dict(fp).lufs
    reference_lufs = LOUD_THRESHOLD_LUFS
    softness_db = 0.75
    loudness_gap = reference_lufs - input_lufs
    desired_lift = softness_db * np.logaddexp(
        0.0, loudness_gap / softness_db
    )
    maximum_lift = 8.25 - dynamics
    gain_db = maximum_lift * np.tanh(desired_lift / maximum_lift)
    target_lufs = input_lufs + gain_db

    # #6305: bound the boost, not the absolute target. The tanh above already
    # caps the lift at maximum_lift; the old clip to [-28, -2] overrode it,
    # pinning every source below ~-36 LUFS to -28 (a lift of +12 to +24 dB,
    # all landing on one loudness) and attenuating a source above -2. The
    # ceiling still stops a lift past -2 LUFS, but never pulls a hotter source
    # down.
    return float(min(target_lufs, max(TARGET_LUFS_CEILING, input_lufs)))



def generate_compression(
    coords: ProcessingCoordinates,
) -> dict[str, float]:
    """
    Generate compression parameters.

    Compression strength follows a smooth bell over the dynamics axis:
    minimal near either extreme and strongest around the corpus center.

    Args:
        coords: Processing space coordinates

    Returns:
        ``ratio`` and ``amount`` for ``CompressionStrategies.apply_clip_blend_compression``, an
        instantaneous, peak-relative waveshaper: it has no threshold, attack or release, so none
        is generated (#5576, #6650).
    """
    effective_dynamics = coords.dynamic_range

    compression_response = np.exp(
        -0.5 * ((effective_dynamics - 0.55) / 0.18) ** 2
    )
    return {
        'ratio': float(1.0 + 0.8 * compression_response),
        'amount': float(0.55 * compression_response),
    }


