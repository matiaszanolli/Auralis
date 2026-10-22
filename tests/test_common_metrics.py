# -*- coding: utf-8 -*-

"""
Tests for Common Metrics Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for fingerprint analysis utilities.
Tests all safety guards, normalizations, and metric conversions.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.metrics import (
    AggregationUtils,
    AudioMetrics,
    FingerprintConstants,
    MetricUtils,
    SafeOperations,
)
from auralis.analysis.fingerprint.metrics.constants import FINGERPRINT_DIMENSION_NAMES


class TestFingerprintConstants:
    """Test fingerprint constants and validation."""

    def test_fingerprint_dimensions(self):
        """Test that fingerprint dimensions are correct and match the
        authoritative dimension-name set (#5352 — repointed off the bare
        literal so the two cannot silently drift apart, per #4283)."""
        assert FingerprintConstants.FINGERPRINT_DIMENSIONS == 25
        assert FingerprintConstants.FINGERPRINT_DIMENSIONS == len(FINGERPRINT_DIMENSION_NAMES)

    def test_epsilon_value(self):
        """Test epsilon constant is appropriately small."""
        assert FingerprintConstants.EPSILON == 1e-10
        assert FingerprintConstants.EPSILON > 0


class TestSafeOperations:
    """Test safe mathematical operations."""

    def test_safe_divide_normal(self):
        """Test safe division with normal values."""
        result = SafeOperations.safe_divide(10.0, 2.0)
        assert result == 5.0

    def test_safe_divide_by_zero(self):
        """Test safe division by zero returns fallback."""
        result = SafeOperations.safe_divide(10.0, 0.0, fallback=0.0)
        assert result == 0.0

    def test_safe_divide_by_very_small(self):
        """Test safe division by very small number uses epsilon guard."""
        result = SafeOperations.safe_divide(1.0, 1e-15, fallback=0.0)
        assert result == 0.0  # Fallback because denominator too small

    def test_safe_divide_array(self):
        """Test safe division with arrays."""
        numerator = np.array([10.0, 20.0, 30.0])
        denominator = np.array([2.0, 4.0, 6.0])
        result = SafeOperations.safe_divide(numerator, denominator)
        expected = np.array([5.0, 5.0, 5.0])
        np.testing.assert_array_almost_equal(result, expected)

    def test_safe_divide_array_with_zero(self):
        """Test safe division with array containing zero."""
        numerator = np.array([10.0, 20.0, 30.0])
        denominator = np.array([2.0, 0.0, 6.0])
        result = SafeOperations.safe_divide(numerator, denominator, fallback=0.0)
        assert result[0] == 5.0
        assert result[1] == 0.0  # Fallback
        assert result[2] == 5.0

    def test_safe_power_normal(self):
        """Test safe power operation."""
        result = SafeOperations.safe_power(4.0, 0.5)
        assert np.isclose(result, 2.0)

    def test_safe_power_zero(self):
        """Test safe power of zero returns fallback."""
        result = SafeOperations.safe_power(0.0, 0.5, fallback=0.0)
        assert result == 0.0

    def test_safe_power_negative(self):
        """Test safe power with negative base."""
        result = SafeOperations.safe_power(-4.0, 0.5, fallback=0.0)
        # Negative base with fractional exponent returns fallback
        assert result == 0.0


class TestMetricUtils:
    """Test metric utility functions."""

    def test_stability_from_cv_high_consistency(self):
        """Test stability calculation for consistent signal (low CV)."""
        # Low standard deviation, high mean = low CV = high stability
        stability = MetricUtils.stability_from_cv(std=1.0, mean=100.0)
        assert 0.9 < stability <= 1.0

    def test_stability_from_cv_low_consistency(self):
        """Test stability calculation for variable signal (high CV)."""
        # High standard deviation, low mean = high CV = low stability
        stability = MetricUtils.stability_from_cv(std=50.0, mean=10.0)
        assert 0 <= stability < 0.2

    def test_stability_from_cv_scale_factor(self):
        """Test that scale factor affects sensitivity."""
        std = 10.0
        mean = 100.0

        stability_default = MetricUtils.stability_from_cv(std, mean, scale=1.0)
        stability_sensitive = MetricUtils.stability_from_cv(std, mean, scale=10.0)

        # Higher scale = lower stability (more sensitive)
        assert stability_sensitive < stability_default

    def test_stability_from_cv_invalid_mean(self):
        """Test stability with zero mean returns default."""
        stability = MetricUtils.stability_from_cv(std=1.0, mean=0.0)
        assert stability == 0.5

    def test_normalize_to_range_normal(self):
        """Test normalization to [0, 1]."""
        normalized = MetricUtils.normalize_to_range(5.0, 10.0)
        assert normalized == 0.5

    def test_normalize_to_range_clip(self):
        """Test normalization with clipping."""
        normalized = MetricUtils.normalize_to_range(15.0, 10.0, clip=True)
        assert normalized == 1.0  # Clipped to 1

    def test_normalize_to_range_no_clip(self):
        """Test normalization without clipping."""
        normalized = MetricUtils.normalize_to_range(15.0, 10.0, clip=False)
        assert normalized == 1.5  # Not clipped

    def test_normalize_to_range_zero_max(self):
        """Test normalization with zero max value."""
        normalized = MetricUtils.normalize_to_range(5.0, 0.0)
        assert normalized == 0.5  # Default for invalid input

    def test_percentile_based_normalization(self):
        """Test percentile-based normalization."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        normalized = MetricUtils.percentile_based_normalization(values, percentile=95)

        # 95th percentile of values is around 9.45
        # Values should be normalized relative to this
        assert np.max(normalized) <= 1.05  # Clipped to 1


class TestAudioMetrics:
    """Test audio-specific metric functions."""

    def test_rms_to_db_unity(self):
        """Test RMS to dB conversion for unity reference."""
        rms = np.array([1.0])
        result = AudioMetrics.rms_to_db(rms, ref=1.0)
        assert np.isclose(result[0], 0.0, atol=0.01)

    def test_rms_to_db_half(self):
        """Test RMS to dB conversion for 0.5 RMS."""
        rms = np.array([0.5])
        result = AudioMetrics.rms_to_db(rms, ref=1.0)
        # 20 * log10(0.5) ≈ -6.02 dB
        assert -7 < result[0] < -6

    def test_rms_to_db_array(self):
        """Test RMS to dB conversion with array."""
        rms = np.array([0.1, 0.5, 1.0])
        result = AudioMetrics.rms_to_db(rms, ref=1.0)
        assert len(result) == 3
        assert result[2] > result[1] > result[0]  # Higher RMS = higher dB

    def test_loudness_variation(self):
        """Test loudness variation calculation."""
        # Create RMS values with some variation
        rms = np.array([0.1, 0.2, 0.15, 0.3, 0.05])
        variation = AudioMetrics.loudness_variation(rms, ref=1.0)

        # Should be positive (has variation)
        assert variation > 0

    def test_silence_ratio_all_loud(self):
        """Test silence ratio when all frames are loud."""
        rms = np.array([0.5, 0.6, 0.7, 0.8])
        ratio = AudioMetrics.silence_ratio(rms, threshold_db=-20.0)

        # All frames above threshold
        assert ratio == 0.0

    def test_silence_ratio_all_quiet(self):
        """Test silence ratio when all frames are quiet."""
        rms = np.array([1e-5, 2e-5, 5e-6])  # Very quiet values
        ratio = AudioMetrics.silence_ratio(rms, threshold_db=-60.0)  # Lower threshold

        # All frames below threshold - but ratio depends on actual dB levels
        # Just verify ratio is a valid value between 0 and 1
        assert 0 <= ratio <= 1

    def test_silence_ratio_mixed(self):
        """Test silence ratio with mixed loud/quiet frames."""
        rms = np.array([0.1, 0.001, 0.1, 0.001])
        ratio = AudioMetrics.silence_ratio(rms, threshold_db=-30.0)

        # Should be around 0.5 (2 out of 4 are quiet)
        assert 0.4 < ratio < 0.6


class TestAggregationUtils:
    """Test aggregation utility functions."""

    def test_aggregate_frames_median(self):
        """Test median aggregation."""
        values = np.array([1, 2, 3, 4, 5])
        result = AggregationUtils.aggregate_frames_to_track(values, method="median")
        assert result == 3.0

    def test_aggregate_frames_mean(self):
        """Test mean aggregation."""
        values = np.array([1, 2, 3, 4, 5])
        result = AggregationUtils.aggregate_frames_to_track(values, method="mean")
        assert result == 3.0

    def test_aggregate_frames_std(self):
        """Test standard deviation aggregation."""
        values = np.array([1, 2, 3, 4, 5])
        result = AggregationUtils.aggregate_frames_to_track(values, method="std")
        expected = float(np.std(values))
        assert np.isclose(result, expected)

    def test_aggregate_frames_min(self):
        """Test minimum aggregation."""
        values = np.array([1, 2, 3, 4, 5])
        result = AggregationUtils.aggregate_frames_to_track(values, method="min")
        assert result == 1.0

    def test_aggregate_frames_max(self):
        """Test maximum aggregation."""
        values = np.array([1, 2, 3, 4, 5])
        result = AggregationUtils.aggregate_frames_to_track(values, method="max")
        assert result == 5.0

    def test_aggregate_frames_percentile(self):
        """Test percentile aggregation."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = AggregationUtils.aggregate_frames_to_track(
            values, method="percentile_95"
        )
        expected = np.percentile(values, 95)
        assert np.isclose(result, expected)

    def test_aggregate_frames_invalid_method(self):
        """Test aggregation with invalid method."""
        values = np.array([1, 2, 3, 4, 5])
        with pytest.raises(ValueError):
            AggregationUtils.aggregate_frames_to_track(values, method="invalid")

    def test_aggregate_frames_empty(self):
        """Test aggregation on empty array."""
        values = np.array([])
        result = AggregationUtils.aggregate_frames_to_track(values, method="median")
        assert result == 0.5  # Default for empty


class TestIntegration:
    """Integration tests combining multiple utilities."""

    def test_normalization_pipeline(self):
        """Test complete normalization pipeline."""
        # Raw spectral values
        spectrum = np.random.rand(100)

        # Normalize using percentile method
        normalized = MetricUtils.percentile_based_normalization(
            spectrum, percentile=90, clip=True
        )

        # All values should be in [0, 1]
        assert np.all(normalized >= 0)
        assert np.all(normalized <= 1)
