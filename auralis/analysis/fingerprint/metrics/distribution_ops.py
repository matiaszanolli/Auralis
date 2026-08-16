"""
Distribution-Based Metric Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Operations that work on the empirical distribution of a value array:
outlier detection and quantile (distribution-matching) normalization.

Split out of the robust-scaling family so that the scaling transforms and the
distribution inspection/remapping transforms stay independently readable.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from .safe_operations import SafeOperations


def outlier_mask(
    values: np.ndarray,
    method: str = 'iqr',
    threshold: float = 1.5,
    return_indices: bool = False
) -> np.ndarray:
    """
    Detect outliers using robust methods.

    Methods:
    - 'iqr': Interquartile range (outliers > Q1 - threshold*IQR or Q3 + threshold*IQR)
    - 'mad': Median absolute deviation (outliers where |scaled| > threshold)
    - 'zscore': Z-score based (outliers where |z| > threshold)

    Use cases:
    - Quality control for fingerprints
    - Identifying corrupted or unusual audio
    - Filtering anomalous samples before normalization

    Args:
        values: Array of values to test
        method: Detection method ('iqr', 'mad', 'zscore')
        threshold: Sensitivity threshold
                  - IQR: 1.5 (standard), 3.0 (extreme)
                  - MAD: 2.5 (standard), 3.5 (extreme)
                  - z-score: 3.0 (standard), 2.0 (sensitive)
        return_indices: If True, return indices of outliers; if False, return boolean mask

    Returns:
        Boolean mask (True = outlier) or indices of outliers

    Examples:
        >>> values = np.array([1, 2, 3, 4, 5, 100])
        >>> mask = MetricUtils.outlier_mask(values, method='iqr')
        >>> outliers = values[mask]
        >>> print(outliers)  # [100]

        >>> indices = MetricUtils.outlier_mask(values, method='iqr', return_indices=True)
        >>> print(indices)  # [5]
    """
    values = np.asarray(values)

    if method == 'iqr':
        q1 = float(np.percentile(values, 25))
        q3 = float(np.percentile(values, 75))
        iqr = q3 - q1
        lower_bound = q1 - threshold * iqr
        upper_bound = q3 + threshold * iqr
        mask = (values < lower_bound) | (values > upper_bound)

    elif method == 'mad':
        median = float(np.median(values))
        deviations = np.abs(values - median)
        mad = float(np.median(deviations))
        if abs(mad) < SafeOperations.EPSILON:
            mask = np.zeros_like(values, dtype=bool)
        else:
            scaled = np.abs((values - median) / (mad * 1.4826))
            mask = scaled > threshold

    elif method == 'zscore':
        mean = float(np.mean(values))
        std = float(np.std(values))
        if abs(std) < SafeOperations.EPSILON:
            mask = np.zeros_like(values, dtype=bool)
        else:
            scaled = np.abs((values - mean) / std)
            mask = scaled > threshold

    else:
        raise ValueError(f"Unknown method: {method}")

    if return_indices:
        return np.where(mask)[0]
    else:
        return mask


def quantile_normalize(
    values: np.ndarray,
    reference: np.ndarray | None = None,
    quantiles: np.ndarray | None = None
) -> np.ndarray:
    """
    Quantile normalization: Transform to match reference distribution.

    Maps quantiles of input to quantiles of reference distribution.
    If no reference, normalizes to uniform distribution [0, 1].

    Use cases:
    - Batch normalization for fingerprints
    - Distribution matching for similar audio
    - Handling different recording qualities

    Args:
        values: Array of values to normalize
        reference: Reference distribution (uses uniform [0,1] if None)
        quantiles: Pre-computed quantile positions (calculated if None)

    Returns:
        Quantile-normalized array

    Examples:
        >>> values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        >>> reference = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        >>> normalized = MetricUtils.quantile_normalize(values, reference)
    """
    values = np.asarray(values)

    # If no reference, use uniform distribution
    if reference is None:
        # Create uniform distribution [0, 1]
        sorted_indices = np.argsort(values)
        result = np.zeros_like(values, dtype=float)
        result[sorted_indices] = np.linspace(0, 1, len(values))
        return result

    # Quantile normalization with reference
    reference = np.asarray(reference)

    # Get sorted positions
    sorted_indices = np.argsort(values)
    sorted_reference = np.sort(reference)

    # Create result array
    result = np.zeros_like(values, dtype=float)

    # Interpolate reference values at sorted positions
    reference_quantiles = np.linspace(0, len(reference) - 1, len(values))
    interpolated = np.interp(
        reference_quantiles,
        np.arange(len(sorted_reference)),
        sorted_reference
    )

    # Assign interpolated values back to original positions
    result[sorted_indices] = interpolated

    return result
