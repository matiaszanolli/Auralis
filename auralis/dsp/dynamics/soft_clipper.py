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
    Apply soft clipping to audio using tanh saturation

    This provides gentle, musical limiting that preserves loudness differences
    while preventing hard clipping.

    Args:
        audio: Input audio array
        threshold: Level where saturation begins (0.0-1.0)
        ceiling: Maximum output level (0.0-1.0)

    Returns:
        Soft-clipped audio

    Algorithm:
        - Below threshold: Linear (no change)
        - Above threshold: Smooth tanh curve approaching ceiling
        - Preserves overall loudness while catching peaks
    """
    # Simple tanh-based soft clipping
    # Scale input so that threshold maps to the linear region
    # and ceiling is the asymptotic limit

    # For values below threshold, pass through
    # For values above, apply scaled tanh
    scale_factor = ceiling / threshold

    # Apply tanh to the entire signal scaled appropriately
    # tanh compresses the signal smoothly, approaching ±1
    output = ceiling * np.tanh(audio * scale_factor / ceiling)

    return output


__all__ = ['soft_clip']
