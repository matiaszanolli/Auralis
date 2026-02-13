"""
Reference Mode Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~

Traditional reference-based audio matching

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from ...dsp.unified import rms
from ...utils.logging import debug


def apply_reference_matching(target_audio: np.ndarray,
                             reference_audio: np.ndarray) -> np.ndarray:
    """
    Apply traditional reference-based matching

    Args:
        target_audio: Audio to process
        reference_audio: Reference audio to match

    Returns:
        Matched audio
    """
    debug("Applying reference-based matching")

    # Calculate RMS levels
    target_rms = rms(target_audio)
    reference_rms = rms(reference_audio)

    # Calculate gain to match RMS levels
    if target_rms > 0:
        gain_factor = reference_rms / target_rms
        # Limit gain to reasonable range
        gain_factor = np.clip(gain_factor, 0.1, 10.0)
    else:
        gain_factor = 1.0

    # Apply gain
    matched_audio = target_audio * gain_factor

    # Only normalize if clipping would occur
    peak_level = np.max(np.abs(matched_audio))
    if peak_level > 0.98:
        # Gentle normalization that preserves RMS ratio as much as possible
        normalization_factor = 0.98 / peak_level
        matched_audio = matched_audio * normalization_factor

    return matched_audio
