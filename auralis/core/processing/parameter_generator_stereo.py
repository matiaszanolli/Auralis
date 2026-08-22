"""
Stereo-Family Parameter Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Target stereo width for the continuous processing space.

Split out of ``parameter_generator.py`` (#4511) so each parameter family
lives in its own module behind the ``ContinuousParameterGenerator`` facade.
Pure function of ``(coords, preference)`` — no state, no behavior change
from the original method it replaces.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from .continuous_space import PreferenceVector, ProcessingCoordinates


def calculate_stereo_width(
    coords: ProcessingCoordinates,
    preference: PreferenceVector | None,
) -> float:
    """
    Calculate target stereo width.

    Move continuously toward a conservative center while retaining most of
    the source width.

    Args:
        coords: Processing space coordinates
        preference: Optional user preference

    Returns:
        Target stereo width (0.0 to 1.0)
    """
    fp = coords.fingerprint
    current_width = fp.get('stereo_width', 0.7)

    target_width = (
        current_width
        + 0.45 * (0.72 - current_width)
        + 0.04 * (coords.spectral_balance - 0.5)
    )

    # Apply user stereo preference
    if preference:
        # Stereo bias shifts target (-1 = narrower, +1 = wider)
        target_width += preference.stereo_bias * 0.2

    return float(0.5 + 0.45 * np.tanh((target_width - 0.5) / 0.45))
