# -*- coding: utf-8 -*-

"""
Stereo Processing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for stereo width analysis and manipulation

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from ..basic import mid_side_encode, mid_side_decode


def stereo_width_analysis(stereo_audio: np.ndarray) -> float:
    """
    Analyze stereo width of audio signal

    Calculates the stereo width based on the correlation between
    left and right channels.

    Args:
        stereo_audio: Stereo audio signal [samples, 2]

    Returns:
        Stereo width factor (0-1)
        - 0.0 = mono (identical channels)
        - 0.5 = normal stereo
        - 1.0 = maximum width (completely uncorrelated)
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return 0.5  # Default for non-stereo

    left = stereo_audio[:, 0]
    right = stereo_audio[:, 1]

    # Calculate correlation
    correlation = np.corrcoef(left, right)[0, 1]

    # Convert correlation to width (inverse relationship)
    # correlation = 1.0 -> width = 0.0 (mono)
    # correlation = 0.0 -> width = 1.0 (maximum stereo)
    width = 1.0 - np.abs(correlation)

    return np.clip(width, 0.0, 1.0)


def adjust_stereo_width(stereo_audio: np.ndarray, width_factor: float) -> np.ndarray:
    """
    Adjust stereo width of audio signal

    Uses mid-side processing to adjust the stereo image width.

    Args:
        stereo_audio: Stereo audio signal [samples, 2]
        width_factor: Width adjustment factor
                     - 0.0 = mono
                     - 0.5 = normal stereo (no change)
                     - 1.0 = maximum width (doubled side signal)

    Returns:
        Width-adjusted stereo audio
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return stereo_audio

    # Convert to mid-side
    mid, side = mid_side_encode(stereo_audio)

    # Adjust side component based on width factor
    # width_factor of 0.5 = no change, 0 = mono, 1 = maximum width
    side_gain = width_factor * 2.0
    adjusted_side = side * side_gain

    # Convert back to stereo
    return mid_side_decode(mid, adjusted_side)
