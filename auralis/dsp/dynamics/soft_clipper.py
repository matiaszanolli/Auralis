"""
Soft Clipper
~~~~~~~~~~~~

Gentle saturation-based peak limiting

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

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
    # Guard against zero or negative ceiling (#2587)
    if ceiling <= 0.0:
        return np.zeros_like(audio)

    # Ensure threshold < ceiling
    threshold = min(threshold, ceiling * 0.99)

    # Calculate the headroom above threshold
    headroom = ceiling - threshold
    if headroom <= 0.0:
        clipped: np.ndarray = np.clip(audio, -ceiling, ceiling)
        return clipped

    # Below threshold: pass through unchanged (linear region). This is
    # CRITICAL - signals below threshold should not be distorted. Starting from
    # a copy and touching only the samples over the threshold keeps the working
    # set at the output plus one transient |audio|, where full-size abs, sign
    # and below-threshold gather arrays used to coexist (#6717). `~(x <= t)`,
    # not `x > t`, so a NaN still takes the saturation branch as it always has.
    output = audio.copy(order='K')
    above_mask = ~(np.abs(audio) <= threshold)

    # Above threshold: apply soft saturation only to the excess
    # The excess above threshold gets compressed via tanh
    if np.any(above_mask):
        over = audio[above_mask]
        excess = np.abs(over) - threshold

        # Scale factor for tanh: controls how quickly we approach ceiling
        # Higher values = harder knee, lower = softer knee
        # Using headroom as the scale gives natural saturation
        scale = headroom * 1.5  # 1.5x headroom for musical saturation curve

        # Compress the excess using tanh
        # tanh(x/scale) * headroom gives us 0 to headroom range
        compressed_excess = headroom * np.tanh(excess / scale)

        # Final output: threshold + compressed excess, with original sign
        output[above_mask] = np.sign(over) * (threshold + compressed_excess)

    return output
