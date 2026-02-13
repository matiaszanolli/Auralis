"""
Statistical Metric Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Statistical metric utilities for audio fingerprinting.
Consolidates repeated metric calculations across analyzers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from .constants import FingerprintConstants
from .safe_operations import SafeOperations


class MetricUtils:
    """
    Statistical metric utilities for audio fingerprinting.
    Consolidates repeated metric calculations across analyzers.
    """

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
        return MetricUtils.robust_scale(winsorized)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
