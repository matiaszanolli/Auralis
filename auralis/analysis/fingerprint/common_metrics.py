# -*- coding: utf-8 -*-

"""
Common Metrics and Utilities for Fingerprint Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Consolidates repeated mathematical operations and patterns across
all fingerprint analyzers (spectral, temporal, harmonic, variation, stereo).

Provides single source of truth for:
- Coefficient of variation calculations
- Normalization and scaling operations
- Safe mathematical operations (division, logarithm)
- Audio metrics conversions (RMS to dB)
- Vector aggregation methods
- Fingerprint validation

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Optional, Dict, Any
import librosa


class FingerprintConstants:
    """
    Constants for fingerprint analysis.
    Single source of truth for all fingerprint-related constants.
    """

    # Core fingerprint dimensions
    FINGERPRINT_DIMENSIONS = 25
    EPSILON = 1e-10  # Safe epsilon for division/log operations

    # Normalization constants
    SPECTRAL_CENTROID_MAX = 8000.0
    SPECTRAL_ROLLOFF_MAX = 10000.0
    CHROMA_ENERGY_MAX = 0.4
    ONSET_DENSITY_MAX = 10.0

    # Stability/consistency scaling factors
    CV_HARMONIC_SCALE = 10.0  # Harmonic pitch stability uses higher sensitivity
    CV_DEFAULT_SCALE = 1.0    # Standard coefficient of variation scaling

    @staticmethod
    def validate_vector(vector, expected_dims: int = None) -> bool:
        """
        Validate fingerprint vector dimensions.

        Args:
            vector: Vector to validate
            expected_dims: Expected dimensions (default: FINGERPRINT_DIMENSIONS)

        Returns:
            True if valid

        Raises:
            ValueError: If dimensions don't match
        """
        if expected_dims is None:
            expected_dims = FingerprintConstants.FINGERPRINT_DIMENSIONS

        if len(vector) != expected_dims:
            raise ValueError(
                f"Expected {expected_dims}-element vector, got {len(vector)}"
            )

        return True


class SafeOperations:
    """
    Safe mathematical operations to prevent numerical errors.
    Consolidates epsilon guards and fallback handling.
    """

    EPSILON = FingerprintConstants.EPSILON

    @staticmethod
    def safe_divide(
        numerator: np.ndarray,
        denominator: np.ndarray,
        fallback: float = 0.0
    ) -> np.ndarray:
        """
        Safe division with epsilon guard.

        Prevents division by zero and handles edge cases gracefully.

        Args:
            numerator: Numerator array/scalar
            denominator: Denominator array/scalar
            fallback: Value to use when denominator is too small

        Returns:
            Result of division with fallback where denominator is near zero
        """
        numerator = np.asarray(numerator)
        denominator = np.asarray(denominator)

        # Create safe denominator with epsilon guard
        safe_denom = np.where(
            np.abs(denominator) > SafeOperations.EPSILON,
            denominator,
            SafeOperations.EPSILON
        )

        # Perform division, using fallback where original denominator was too small
        result = np.divide(numerator, safe_denom)
        result = np.where(
            np.abs(denominator) <= SafeOperations.EPSILON,
            fallback,
            result
        )

        return result

    @staticmethod
    def safe_log(
        value: np.ndarray,
        fallback: float = -np.inf
    ) -> np.ndarray:
        """
        Safe logarithm operation.

        Prevents log(0) and handles small values gracefully.

        Args:
            value: Value or array to take log of
            fallback: Value to use for log(x <= epsilon)

        Returns:
            Logarithm with fallback for invalid inputs
        """
        value = np.asarray(value)

        # Create safe value with epsilon guard
        safe_value = np.maximum(value, SafeOperations.EPSILON)

        # Compute log
        result = np.log(safe_value)

        # Use fallback where original value was too small
        result = np.where(
            value <= SafeOperations.EPSILON,
            fallback,
            result
        )

        return result

    @staticmethod
    def safe_power(
        base: np.ndarray,
        exponent: float,
        fallback: float = 0.0
    ) -> np.ndarray:
        """
        Safe power operation for positive bases.

        Args:
            base: Base value(s)
            exponent: Exponent (typically 0.5 for square root, 1/3 for cube root)
            fallback: Value to use for base <= epsilon

        Returns:
            Result of base^exponent with fallback for small bases
        """
        base = np.asarray(base)

        # Create safe base with epsilon guard
        safe_base = np.maximum(base, SafeOperations.EPSILON)

        # Compute power
        result = np.power(safe_base, exponent)

        # Use fallback where original base was too small
        result = np.where(
            base <= SafeOperations.EPSILON,
            fallback,
            result
        )

        return result


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
        ref_value = np.percentile(values, percentile)

        if ref_value <= SafeOperations.EPSILON:
            return np.ones_like(values) * 0.5

        normalized = values / ref_value

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
        mean: Optional[float] = None,
        std: Optional[float] = None,
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
        q1: Optional[float] = None,
        q2: Optional[float] = None,
        q3: Optional[float] = None,
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
    def quantile_normalize(
        values: np.ndarray,
        reference: Optional[np.ndarray] = None,
        quantiles: Optional[np.ndarray] = None
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


class AudioMetrics:
    """
    Audio-specific metrics and conversions.
    Consolidates RMS, loudness, and dB conversions.
    """

    @staticmethod
    def rms_to_db(
        rms: np.ndarray,
        ref: float = None
    ) -> np.ndarray:
        """
        Convert RMS to dB using librosa standard.

        Args:
            rms: RMS values (can be scalar or array)
            ref: Reference level (default: max of input)

        Returns:
            RMS values in dB
        """
        if ref is None:
            ref = np.max(np.abs(rms)) if np.any(rms) else 1.0

        return librosa.amplitude_to_db(np.asarray(rms), ref=ref)

    @staticmethod
    def loudness_variation(
        rms: np.ndarray,
        ref: float = None
    ) -> float:
        """
        Calculate loudness variation (standard deviation of dB values).

        Measures how much loudness varies across frames.

        Args:
            rms: RMS values per frame
            ref: Reference level for dB conversion

        Returns:
            Loudness variation in dB
        """
        rms_db = AudioMetrics.rms_to_db(rms, ref=ref)
        return float(np.std(rms_db))

    @staticmethod
    def silence_ratio(
        rms: np.ndarray,
        threshold_db: float = -40.0,
        ref: float = None
    ) -> float:
        """
        Calculate ratio of silent frames.

        Silent frame = frame with RMS below threshold_db.

        Args:
            rms: RMS values per frame
            threshold_db: dB threshold for silence (default -40 dB)
            ref: Reference level for dB conversion

        Returns:
            Ratio of silent frames in [0, 1]
        """
        rms_db = AudioMetrics.rms_to_db(rms, ref=ref)
        silent_frames = np.sum(rms_db < threshold_db)

        return float(silent_frames / len(rms_db))

    @staticmethod
    def peak_to_rms_ratio(
        audio: np.ndarray
    ) -> float:
        """
        Calculate peak-to-RMS ratio (dynamic range indicator).

        Args:
            audio: Audio signal

        Returns:
            Ratio of peak amplitude to RMS (typically 3-20)
        """
        peak = np.max(np.abs(audio))
        rms_val = np.sqrt(np.mean(audio ** 2))

        if rms_val <= SafeOperations.EPSILON:
            return 1.0

        return float(peak / rms_val)


class AggregationUtils:
    """
    Methods for aggregating frame-level features to track-level features.
    """

    @staticmethod
    def aggregate_frames_to_track(
        frame_values: np.ndarray,
        method: str = "median"
    ) -> float:
        """
        Aggregate frame-level values to single track-level feature.

        Different aggregation methods capture different aspects:
        - median: Robust to outliers, typical behavior
        - mean: Average behavior
        - std: Variability
        - percentile: Percentile-based (upper/lower extreme)

        Args:
            frame_values: Array of per-frame values
            method: Aggregation method ('median', 'mean', 'std', 'min', 'max')

        Returns:
            Single aggregated feature value
        """
        frame_values = np.asarray(frame_values)

        if len(frame_values) == 0:
            return 0.5

        if method == "median":
            return float(np.median(frame_values))
        elif method == "mean":
            return float(np.mean(frame_values))
        elif method == "std":
            return float(np.std(frame_values))
        elif method == "min":
            return float(np.min(frame_values))
        elif method == "max":
            return float(np.max(frame_values))
        elif method == "percentile_95":
            return float(np.percentile(frame_values, 95))
        else:
            raise ValueError(f"Unknown aggregation method: {method}")

    @staticmethod
    def aggregate_multiple(
        frame_values: np.ndarray,
        methods: list = None
    ) -> Dict[str, float]:
        """
        Aggregate frame values using multiple methods.

        Useful for feature extraction where multiple perspectives are needed.

        Args:
            frame_values: Array of per-frame values
            methods: List of methods to apply (default: ['median', 'std'])

        Returns:
            Dictionary with aggregation method as key
        """
        if methods is None:
            methods = ["median", "std"]

        return {
            method: AggregationUtils.aggregate_frames_to_track(frame_values, method)
            for method in methods
        }


class SpectralOperations:
    """
    Spectral analysis utility operations.
    Consolidates spectral normalization and processing patterns.
    """

    @staticmethod
    def normalize_magnitude(
        magnitude: np.ndarray,
        axis: int = 0
    ) -> np.ndarray:
        """
        Normalize magnitude spectrogram to [0, 1] per frequency bin or frame.

        Args:
            magnitude: Magnitude spectrogram (frequency x time or other)
            axis: Axis to normalize across

        Returns:
            Normalized magnitude spectrogram
        """
        norm = np.sum(np.abs(magnitude), axis=axis, keepdims=True)
        norm = np.maximum(norm, SafeOperations.EPSILON)

        return magnitude / norm

    @staticmethod
    def spectral_flatness(
        magnitude: np.ndarray,
        axis: int = 0
    ) -> np.ndarray:
        """
        Calculate spectral flatness (Wiener entropy).

        Measures how white the spectrum is (flat = white noise, peaked = tonal).

        Args:
            magnitude: Magnitude spectrogram
            axis: Frequency axis

        Returns:
            Spectral flatness per frame [0, 1]
        """
        # Geometric mean
        geom_mean = SafeOperations.safe_power(
            np.prod(np.maximum(magnitude, SafeOperations.EPSILON), axis=axis),
            1.0 / magnitude.shape[axis]
        )

        # Arithmetic mean
        arith_mean = np.mean(magnitude, axis=axis)

        # Flatness = geom_mean / arith_mean
        flatness = SafeOperations.safe_divide(geom_mean, arith_mean)

        return np.clip(flatness, 0, 1)

    @staticmethod
    def spectral_centroid_safe(
        magnitude: np.ndarray,
        frequencies: np.ndarray
    ) -> float:
        """
        Calculate spectral centroid (brightness) safely.

        Args:
            magnitude: Magnitude spectrum
            frequencies: Corresponding frequencies

        Returns:
            Spectral centroid in Hz
        """
        magnitude = np.asarray(magnitude)
        frequencies = np.asarray(frequencies)

        # Normalize magnitude
        mag_norm = SafeOperations.safe_divide(
            magnitude,
            np.sum(magnitude)
        )

        # Weighted average of frequencies
        centroid = np.sum(frequencies * mag_norm)

        return float(centroid)
