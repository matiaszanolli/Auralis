"""
Range Normalization Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simple range operations for audio fingerprint metrics: normalize, clip and
scale scalar (or elementwise) values into a bounded target range.

These helpers are deliberately distribution-free: they never estimate a
distribution from the data, they only map values through a fixed range using
an epsilon guard for degenerate denominators.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from .constants import FingerprintConstants
from .safe_operations import SafeOperations


def stability_from_cv(
    std: float,
    mean: float,
    scale: float = FingerprintConstants.CV_DEFAULT_SCALE
) -> float:
    """
    Convert coefficient of variation to stability score (0-1).

    Coefficient of Variation (CV) = std / mean
    Stability = 1.0 / (1.0 + CV * scale)

    Lower CV = higher stability (more consistent)
    Higher CV = lower stability (more variable)

    Args:
        std: Standard deviation
        mean: Mean value
        scale: Scaling factor for sensitivity (default 1.0)
               Use higher values for more sensitive stability (e.g., 10.0 for pitch)

    Returns:
        Stability score in range [0, 1]
    """
    if mean <= SafeOperations.EPSILON:
        return 0.5  # Default for invalid input

    cv = std / mean
    stability = 1.0 / (1.0 + cv * scale)

    return float(np.clip(stability, 0, 1))


def normalize_to_range(
    value: float,
    max_val: float,
    clip: bool = True
) -> float:
    """
    Normalize value to [0, 1] range.

    Divides by max_val and optionally clips to [0, 1].

    Args:
        value: Value to normalize
        max_val: Maximum expected value for denominator
        clip: Whether to clip result to [0, 1]

    Returns:
        Normalized value in [0, 1] range (if clip=True)
    """
    if max_val <= SafeOperations.EPSILON:
        return 0.5

    normalized = value / max_val

    if clip:
        normalized = np.clip(normalized, 0, 1)

    return float(normalized)


def percentile_based_normalization(
    values: np.ndarray,
    percentile: float = 95.0,
    clip: bool = True
) -> np.ndarray:
    """
    Normalize values based on percentile (robust normalization).

    Uses percentile instead of max to be robust to outliers.

    Args:
        values: Array of values to normalize
        percentile: Percentile to use as reference (default 95)
        clip: Whether to clip to [0, 1]

    Returns:
        Normalized array
    """
    ref_value: float = float(np.percentile(values, percentile))

    if ref_value <= SafeOperations.EPSILON:
        return np.ones_like(values, dtype=float) * 0.5

    normalized: np.ndarray = values / ref_value

    if clip:
        normalized = np.clip(normalized, 0, 1)

    return normalized


def clip_to_range(
    value: float,
    min_val: float,
    max_val: float
) -> float:
    """
    Clip value to specified range with safe bounds checking.

    Common use cases:
    - Tempo: 40-200 BPM
    - Loudness variation: 0-10 dB
    - Correlation coefficients: -1 to +1

    Args:
        value: Value to clip
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clipped value within [min_val, max_val]
    """
    if min_val > max_val:
        min_val, max_val = max_val, min_val  # Swap if reversed

    return float(np.clip(value, min_val, max_val))


def scale_to_range(
    value: float,
    old_min: float,
    old_max: float,
    new_min: float = 0.0,
    new_max: float = 1.0
) -> float:
    """
    Scale value from one range to another.

    Performs linear interpolation: new_val = new_min + (value - old_min) * scale_factor

    Use cases:
    - Tempo (40-200 BPM) → (0-1) for analysis
    - Loudness variation (0-10 dB) → (0-1) for metrics
    - Correlation (-1 to +1) → (0-1) for similarity

    Args:
        value: Value to scale
        old_min: Original range minimum
        old_max: Original range maximum
        new_min: Target range minimum (default: 0.0)
        new_max: Target range maximum (default: 1.0)

    Returns:
        Scaled value in [new_min, new_max] range
    """
    if old_max <= old_min:
        return (new_min + new_max) / 2.0  # Return midpoint for invalid range

    # Linear scaling with fallback to midpoint if out of range
    scale_factor = (new_max - new_min) / (old_max - old_min)
    scaled = new_min + (value - old_min) * scale_factor

    return float(np.clip(scaled, min(new_min, new_max), max(new_min, new_max)))
