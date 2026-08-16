"""
Statistical and Robust Scaling Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Distribution-aware scaling transforms for audio fingerprint metrics: z-score,
IQR-based robust scaling, winsorized robust scaling and MAD scaling.

Each transform estimates a centre and a spread from the data (or from
caller-supplied statistics) and divides by that spread, so every one of them
carries an epsilon guard against a degenerate (zero) spread.

The outlier/quantile helpers live in ``distribution_ops`` and are re-exported
here so the full statistical operation set stays importable from one module.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from .distribution_ops import outlier_mask, quantile_normalize
from .safe_operations import SafeOperations

__all__ = [
    "normalize_with_zscore",
    "robust_scale",
    "robust_scale_with_winsorization",
    "mad_scaling",
    "outlier_mask",
    "quantile_normalize",
]


def normalize_with_zscore(
    values: np.ndarray,
    mean: float | None = None,
    std: float | None = None,
    epsilon: float = SafeOperations.EPSILON
) -> np.ndarray:
    """
    Z-score normalization: (x - mean) / std.

    Transforms data to have mean=0 and standard deviation=1.
    Useful for distribution-aware normalization and outlier handling.

    Use cases:
    - Fingerprint features with different distributions
    - Metric comparison across different audio types
    - Outlier detection (values > 3σ are anomalous)

    Args:
        values: Array of values to normalize
        mean: Pre-computed mean (calculated from values if None)
        std: Pre-computed standard deviation (calculated from values if None)
        epsilon: Small value for numerical stability

    Returns:
        Z-score normalized array (mean=0, std=1 for input distribution)

    Examples:
        >>> values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        >>> normalized = MetricUtils.normalize_with_zscore(values)
        >>> np.mean(normalized)  # ~0.0
        >>> np.std(normalized)   # ~1.0
    """
    values = np.asarray(values)

    # Calculate mean and std if not provided
    if mean is None:
        mean = float(np.mean(values))
    if std is None:
        std = float(np.std(values))

    # Handle zero std (constant values)
    if abs(std) < epsilon:
        return np.zeros_like(values, dtype=float)

    # Z-score normalization
    normalized = (values - mean) / std

    return normalized


def robust_scale(
    values: np.ndarray,
    q1: float | None = None,
    q2: float | None = None,
    q3: float | None = None,
    epsilon: float = SafeOperations.EPSILON
) -> np.ndarray:
    """
    Robust scaling using interquartile range (IQR).

    Scales data using: (x - Q2) / (Q3 - Q1)
    where Q2 is median, Q1 is 25th percentile, Q3 is 75th percentile.

    More robust to outliers than z-score (uses IQR instead of std).

    Use cases:
    - Data with extreme outliers
    - Non-normal distributions
    - Fingerprint matching with corrupted audio

    Args:
        values: Array of values to scale
        q1: 25th percentile (calculated if None)
        q2: 50th percentile/median (calculated if None)
        q3: 75th percentile (calculated if None)
        epsilon: Small value for numerical stability

    Returns:
        Robustly scaled array (centered at 0, IQR-normalized)

    Examples:
        >>> values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
        >>> scaled = MetricUtils.robust_scale(values)  # Outlier 100 has less impact
    """
    values = np.asarray(values)

    # Calculate quartiles if not provided
    if q1 is None:
        q1 = float(np.percentile(values, 25))
    if q2 is None:
        q2 = float(np.percentile(values, 50))
    if q3 is None:
        q3 = float(np.percentile(values, 75))

    iqr = q3 - q1

    # Handle zero IQR (all values equal)
    if abs(iqr) < epsilon:
        return np.zeros_like(values, dtype=float)

    # Robust scaling
    scaled = (values - q2) / iqr

    return scaled


def robust_scale_with_winsorization(
    values: np.ndarray,
    lower_percentile: float = 5.0,
    upper_percentile: float = 95.0,
    epsilon: float = SafeOperations.EPSILON
) -> np.ndarray:
    """
    Robust scaling with Winsorization (clip outliers before scaling).

    Combines two techniques:
    1. Winsorization: Replace values beyond percentiles with percentile values
    2. Robust scaling: Scale by IQR

    More aggressive outlier handling than basic robust scaling.

    Use cases:
    - Severe outliers (beyond 1-99 percentile)
    - Fingerprinting corrupted/damaged audio
    - Data with known measurement errors at extremes

    Args:
        values: Array of values to scale
        lower_percentile: Lower percentile for clipping (default 5)
        upper_percentile: Upper percentile for clipping (default 95)
        epsilon: Small value for numerical stability

    Returns:
        Winsorized and robustly scaled array

    Examples:
        >>> values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100, 1000])
        >>> scaled = MetricUtils.robust_scale_with_winsorization(values)
        >>> # Extreme outliers 100, 1000 replaced with 95th percentile
    """
    values = np.asarray(values)

    # Calculate winsorization bounds
    lower = float(np.percentile(values, lower_percentile))
    upper = float(np.percentile(values, upper_percentile))

    # Winsorize: clip extreme values
    winsorized = np.clip(values, lower, upper)

    # Apply robust scaling to winsorized values
    return robust_scale(winsorized)


def mad_scaling(
    values: np.ndarray,
    scale_factor: float = 1.4826,
    epsilon: float = SafeOperations.EPSILON
) -> np.ndarray:
    """
    Median Absolute Deviation (MAD) scaling.

    More robust than IQR for outlier detection and scaling.
    MAD is defined as: MAD = median(|x - median(x)|)
    Scaled value: (x - median) / (MAD * scale_factor)

    scale_factor default (1.4826) assumes normal distribution.

    Use cases:
    - Outlier detection (typically |scaled| > 2.5 is outlier)
    - Very robust scaling (handles extreme outliers)
    - Audio quality metrics with skewed distributions

    Args:
        values: Array of values to scale
        scale_factor: Scaling factor (default 1.4826 for normal distribution)
        epsilon: Small value for numerical stability

    Returns:
        MAD-scaled array (centered at 0, MAD-normalized)

    Examples:
        >>> values = np.array([1, 2, 3, 4, 5, 100, 1000])
        >>> scaled = MetricUtils.mad_scaling(values)
        >>> # Extreme outliers have moderate scaled values
    """
    values = np.asarray(values)

    # Calculate median
    median = float(np.median(values))

    # Calculate absolute deviations from median
    deviations = np.abs(values - median)

    # Calculate MAD (median of absolute deviations)
    mad = float(np.median(deviations))

    # Handle zero MAD
    if abs(mad) < epsilon:
        return np.zeros_like(values, dtype=float)

    # Scale using MAD
    scaled = (values - median) / (mad * scale_factor)

    return scaled
