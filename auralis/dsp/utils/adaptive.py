# -*- coding: utf-8 -*-

"""
Adaptive Processing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for adaptive and intelligent audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from .conversion import to_db
from .audio_info import mono_to_stereo
from ..basic import rms


def adaptive_gain_calculation(target_rms: float,
                             reference_rms: float,
                             adaptation_factor: float = 0.8) -> float:
    """
    Calculate adaptive gain with smoother transitions

    Computes the gain needed to match target RMS to reference RMS,
    with optional smoothing for gradual adaptation.

    Args:
        target_rms: RMS of target signal
        reference_rms: RMS of reference or target level
        adaptation_factor: How aggressively to adapt (0-1)
                          1.0 = full adaptation, 0.0 = no adaptation

    Returns:
        Gain factor (linear)
    """
    if target_rms > 0:
        raw_gain = reference_rms / target_rms

        # Special case: if adaptation_factor is 1.0, return raw gain
        if adaptation_factor >= 0.99:
            return np.clip(raw_gain, 0.1, 10.0)

        # Apply adaptation factor for smoother transitions
        # adaptation_factor of 0.8 means 80% of the way to the target
        gain = 1.0 + (raw_gain - 1.0) * adaptation_factor

        # Limit gain to reasonable range
        return np.clip(gain, 0.1, 10.0)
    return 1.0


def psychoacoustic_weighting(frequencies: np.ndarray) -> np.ndarray:
    """
    Apply psychoacoustic weighting to frequency spectrum

    Creates a weighting curve based on human hearing sensitivity,
    similar to A-weighting but simplified.

    Args:
        frequencies: Array of frequency values in Hz

    Returns:
        Weighting factors for each frequency (0-1)
    """
    # Simplified A-weighting-like curve
    weights = np.ones_like(frequencies)

    for i, freq in enumerate(frequencies):
        if freq < 20:
            weights[i] = 0.1  # Very low frequencies (barely audible)
        elif freq < 100:
            weights[i] = 0.5  # Low frequencies (bass)
        elif freq < 1000:
            weights[i] = 0.8  # Mid-low frequencies
        elif freq < 4000:
            weights[i] = 1.0  # Most important range (speech/presence)
        elif freq < 8000:
            weights[i] = 0.9  # High frequencies
        elif freq < 16000:
            weights[i] = 0.7  # Very high frequencies
        else:
            weights[i] = 0.3  # Ultrasonic (limited perception)

    return weights


def smooth_parameter_transition(current_value: float,
                               target_value: float,
                               smoothing_factor: float = 0.1) -> float:
    """
    Smooth parameter transitions to avoid artifacts

    Implements a simple low-pass filter for parameter changes,
    preventing abrupt changes that could cause clicks or pops.

    Args:
        current_value: Current parameter value
        target_value: Target parameter value
        smoothing_factor: Speed of transition (0-1)
                         0.0 = no change, 1.0 = instant change

    Returns:
        Smoothed parameter value
    """
    return current_value + (target_value - current_value) * smoothing_factor


def calculate_loudness_units(audio: np.ndarray, sample_rate: int = 44100) -> float:
    """
    Simple loudness calculation (approximation of LUFS)

    This is a simplified loudness calculation. For precise measurements,
    use a full ITU-R BS.1770-4 implementation.

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz

    Returns:
        Loudness in approximate LUFS
    """
    if audio.ndim == 1:
        audio = mono_to_stereo(audio)

    # Simple K-weighting approximation
    # This is a simplified version - real LUFS calculation is more complex
    rms_value = rms(audio)
    if rms_value > 0:
        loudness_db = to_db(rms_value)
        # Rough conversion to LUFS-like scale
        lufs_approx = loudness_db - 23.0  # Offset to approximate LUFS scale
        return lufs_approx
    else:
        return -70.0  # Very quiet
