# -*- coding: utf-8 -*-

"""
Soft Clipper
~~~~~~~~~~~~

Gentle saturation-based peak limiting

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Uses hyperbolic tangent (tanh) for smooth, musical peak control
"""

import numpy as np


def soft_clip(audio: np.ndarray, threshold: float = 0.9, ceiling: float = 0.99) -> np.ndarray:
    """
    Apply soft clipping to audio using tanh saturation with proper threshold behavior.

    This provides gentle, musical limiting that preserves loudness differences
    while preventing hard clipping.

    Args:
        audio: Input audio array
        threshold: Level where saturation begins (0.0-1.0)
        ceiling: Maximum output level (0.0-1.0)

    Returns:
        Soft-clipped audio

    Algorithm:
        - Below threshold: Linear (no change) - CRITICAL for preserving dynamics
        - Above threshold: Smooth tanh curve approaching ceiling
        - Preserves overall loudness while catching peaks
        - Mid-high frequencies stay clean when below threshold
    """
    # Ensure threshold < ceiling
    threshold = min(threshold, ceiling * 0.99)

    # Calculate the headroom above threshold
    headroom = ceiling - threshold

    # Get absolute values and signs for processing
    abs_audio = np.abs(audio)
    sign = np.sign(audio)

    # Create output array
    output = np.empty_like(audio)

    # Below threshold: pass through unchanged (linear region)
    # This is CRITICAL - signals below threshold should not be distorted
    below_mask = abs_audio <= threshold
    output[below_mask] = audio[below_mask]

    # Above threshold: apply soft saturation only to the excess
    # The excess above threshold gets compressed via tanh
    above_mask = ~below_mask
    if np.any(above_mask):
        excess = abs_audio[above_mask] - threshold

        # Scale factor for tanh: controls how quickly we approach ceiling
        # Higher values = harder knee, lower = softer knee
        # Using headroom as the scale gives natural saturation
        scale = headroom * 1.5  # 1.5x headroom for musical saturation curve

        # Compress the excess using tanh
        # tanh(x/scale) * headroom gives us 0 to headroom range
        compressed_excess = headroom * np.tanh(excess / scale)

        # Final output: threshold + compressed excess, with original sign
        output[above_mask] = sign[above_mask] * (threshold + compressed_excess)

    return output


__all__ = ['soft_clip']
