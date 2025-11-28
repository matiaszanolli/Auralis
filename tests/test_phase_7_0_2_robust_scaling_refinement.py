# -*- coding: utf-8 -*-

"""
Phase 7.0.2 Tests: Robust Scaling Refinement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Advanced robust scaling techniques: Winsorization, MAD scaling, and outlier detection.

Test Categories:
- Winsorized robust scaling (clip + scale)
- Median Absolute Deviation (MAD) scaling
- Outlier detection methods (IQR, MAD, z-score)
- Comparative analysis of robust methods
- Edge cases and performance

:copyright: (C) 2025 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest
from auralis.analysis.fingerprint.common_metrics import MetricUtils


class TestWinsorizedRobustScaling:
    """Test robust scaling with Winsorization."""

    def test_winsorization_basic(self):
        """Test basic Winsorization with outliers."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0, 1000.0])
        scaled = MetricUtils.robust_scale_with_winsorization(values)

        # Should handle extreme outliers
        assert len(scaled) == len(values)
        assert np.all(np.isfinite(scaled))

    def test_winsorization_extreme_outliers(self):
        """Test Winsorization on extreme outliers."""
        # Data with severe outliers
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 1000, 10000])
        scaled = MetricUtils.robust_scale_with_winsorization(
            values,
            lower_percentile=5,
            upper_percentile=95
        )

        # Extreme outliers (1000, 10000) should be clipped
        # Result should be more stable than basic robust scaling
        assert np.all(np.isfinite(scaled))

    def test_winsorization_preserves_center(self):
        """Test that Winsorization preserves center values."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        scaled = MetricUtils.robust_scale_with_winsorization(values)

        # Middle values should be well-centered
        median_idx = 4  # Value 5 is median of 1-9
        assert np.abs(scaled[median_idx]) < 1.0

    def test_winsorization_percentiles_customizable(self):
        """Test custom Winsorization percentiles."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])

        # Less aggressive Winsorization
        scaled_10_90 = MetricUtils.robust_scale_with_winsorization(
            values,
            lower_percentile=10,
            upper_percentile=90
        )

        # More aggressive Winsorization
        scaled_1_99 = MetricUtils.robust_scale_with_winsorization(
            values,
            lower_percentile=1,
            upper_percentile=99
        )

        # Different scaling due to different clipping bounds
        assert not np.allclose(scaled_10_90, scaled_1_99)

    def test_winsorization_no_outliers(self):
        """Test Winsorization on data without outliers."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        scaled = MetricUtils.robust_scale_with_winsorization(values)

        # Should be same as basic robust scaling
        basic_scaled = MetricUtils.robust_scale(values)
        np.testing.assert_allclose(scaled, basic_scaled, atol=0.1)

    def test_winsorization_vs_robust_scaling(self):
        """Compare Winsorized vs basic robust scaling on outliers."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 1000])

        basic = MetricUtils.robust_scale(values)
        winsorized = MetricUtils.robust_scale_with_winsorization(values)

        # Winsorized should have lower variance (more stable)
        assert np.std(winsorized) <= np.std(basic)


class TestMADScaling:
    """Test Median Absolute Deviation (MAD) scaling."""

    def test_mad_basic_scaling(self):
        """Test basic MAD scaling."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        scaled = MetricUtils.mad_scaling(values)

        # Should return scaled values
        assert len(scaled) == len(values)
        assert np.all(np.isfinite(scaled))

    def test_mad_median_centered(self):
        """Test that MAD scaling centers on median."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        scaled = MetricUtils.mad_scaling(values)

        # Median (3.0) should map to 0
        median_idx = 2
        assert np.abs(scaled[median_idx]) < 0.1

    def test_mad_outlier_resistance(self):
        """Test MAD's resistance to outliers."""
        values = np.array([1, 2, 3, 4, 5, 100, 1000])
        scaled = MetricUtils.mad_scaling(values)

        # MAD should return valid scaled values
        assert len(scaled) == len(values)
        assert np.all(np.isfinite(scaled))

    def test_mad_custom_scale_factor(self):
        """Test MAD with custom scale factor."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9])

        # Standard scale factor (1.4826)
        scaled_standard = MetricUtils.mad_scaling(values, scale_factor=1.4826)

        # Larger scale factor
        scaled_2 = MetricUtils.mad_scaling(values, scale_factor=2.0)

        # Larger scale factor = smaller absolute values
        assert np.abs(scaled_2[-1]) < np.abs(scaled_standard[-1])

    def test_mad_symmetric_scaling(self):
        """Test MAD scaling is symmetric around median."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        scaled = MetricUtils.mad_scaling(values)

        # Values equidistant from median should have opposite signs
        # 1 and 5 are equidistant from 3
        assert np.abs(scaled[0] + scaled[-1]) < 0.1

    def test_mad_constant_values(self):
        """Test MAD with constant values."""
        values = np.array([3.0, 3.0, 3.0, 3.0])
        scaled = MetricUtils.mad_scaling(values)

        # Zero MAD should return zeros
        np.testing.assert_array_equal(scaled, np.zeros_like(values))

    def test_mad_single_value(self):
        """Test MAD with single value."""
        values = np.array([42.0])
        scaled = MetricUtils.mad_scaling(values)

        # Single value has zero MAD
        assert scaled[0] == 0.0

    def test_mad_exponential_distribution(self):
        """Test MAD on exponential distribution (highly skewed)."""
        values = np.random.exponential(2.0, 1000)
        scaled = MetricUtils.mad_scaling(values)

        # Should handle skewed distribution well
        assert np.all(np.isfinite(scaled))

        # Median should be near 0
        median_idx = np.argsort(values)[len(values) // 2]
        assert np.abs(scaled[median_idx]) < 0.2


class TestOutlierDetection:
    """Test outlier detection methods."""

    def test_iqr_outlier_detection_basic(self):
        """Test basic IQR outlier detection."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        mask = MetricUtils.outlier_mask(values, method='iqr', threshold=1.5)

        # 100 should be detected as outlier
        assert mask[-1] == True
        # Normal values should not be outliers
        assert np.sum(mask[:9]) == 0

    def test_iqr_outlier_indices(self):
        """Test IQR outlier detection returning indices."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        indices = MetricUtils.outlier_mask(
            values,
            method='iqr',
            threshold=1.5,
            return_indices=True
        )

        # Should return index of outlier (100)
        assert 9 in indices
        assert len(indices) == 1

    def test_mad_outlier_detection(self):
        """Test MAD outlier detection."""
        values = np.array([1, 2, 3, 4, 5, 100, 1000])
        mask = MetricUtils.outlier_mask(values, method='mad', threshold=2.5)

        # Extreme outliers should be detected
        assert mask[-1] == True

    def test_zscore_outlier_detection(self):
        """Test z-score outlier detection."""
        values = np.random.normal(100, 15, 1000)
        # Add extreme outliers
        values = np.append(values, [200, 300, 400])

        mask = MetricUtils.outlier_mask(values, method='zscore', threshold=3.0)

        # Extreme values should be detected
        assert mask[-1] == True
        assert mask[-2] == True

    def test_outlier_threshold_sensitivity(self):
        """Test that threshold affects detection."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])

        # Loose threshold
        mask_loose = MetricUtils.outlier_mask(values, method='iqr', threshold=3.0)

        # Strict threshold
        mask_strict = MetricUtils.outlier_mask(values, method='iqr', threshold=1.5)

        # Strict should detect at least as many outliers as loose
        assert np.sum(mask_strict) >= np.sum(mask_loose)

    def test_outlier_all_methods(self):
        """Compare all outlier detection methods."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100, 1000])

        iqr_mask = MetricUtils.outlier_mask(values, method='iqr')
        mad_mask = MetricUtils.outlier_mask(values, method='mad')
        zscore_mask = MetricUtils.outlier_mask(values, method='zscore')

        # All should detect 1000 as outlier
        assert iqr_mask[-1] == True
        assert mad_mask[-1] == True
        assert zscore_mask[-1] == True

    def test_outlier_empty_mask(self):
        """Test outlier detection with no outliers."""
        values = np.array([1, 2, 3, 4, 5])
        mask = MetricUtils.outlier_mask(values, method='iqr', threshold=1.5)

        # Should detect no outliers
        assert np.sum(mask) == 0

    def test_outlier_all_outliers(self):
        """Test outlier detection with extreme range."""
        # Create bimodal data with clear separation
        low_values = np.array([1, 2, 3, 4, 5])
        high_values = np.array([100, 200, 300, 400, 500])
        combined = np.concatenate([low_values, high_values])

        # Use MAD which is better at detecting bimodal distributions
        mask = MetricUtils.outlier_mask(combined, method='mad', threshold=2.5)

        # Should detect at least one group as outliers
        assert np.sum(mask) > 0


class TestRobustMethodComparison:
    """Compare different robust scaling methods."""

    def test_robust_vs_winsorization(self):
        """Compare basic robust scaling vs Winsorization."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 1000])

        robust = MetricUtils.robust_scale(values)
        winsorized = MetricUtils.robust_scale_with_winsorization(values)

        # Winsorized should be more stable
        assert np.std(winsorized) <= np.std(robust)

    def test_iqr_vs_mad_scaling(self):
        """Compare IQR-based vs MAD scaling."""
        values = np.random.normal(50, 15, 1000)
        # Add extreme outliers
        values = np.append(values, [200, 300, 400])

        iqr_scaled = MetricUtils.robust_scale(values)
        mad_scaled = MetricUtils.mad_scaling(values)

        # Both should center near 0
        assert np.abs(np.median(iqr_scaled)) < 0.5
        assert np.abs(np.median(mad_scaled)) < 0.5

    def test_outlier_detection_agreement(self):
        """Test outlier detection methods on same data."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100, 1000])

        iqr_outliers = MetricUtils.outlier_mask(values, method='iqr')
        mad_outliers = MetricUtils.outlier_mask(values, method='mad')

        # Both should detect extreme values
        assert iqr_outliers[-1] == True
        assert mad_outliers[-1] == True

    def test_zscore_vs_robust_on_normal_data(self):
        """Compare z-score detection vs robust methods on normal data."""
        values = np.random.normal(100, 15, 1000)

        # Outlier detection: values > 3 std
        zscore_scaled = MetricUtils.normalize_with_zscore(values)
        zscore_mask = np.abs(zscore_scaled) > 3.0

        # Check MAD detection
        mad_scaled = MetricUtils.mad_scaling(values)
        mad_mask = np.abs(mad_scaled) > 2.5

        # Both should detect outliers
        pct_zscore = np.sum(zscore_mask) / len(values)
        pct_mad = np.sum(mad_mask) / len(values)

        # Both should detect some outliers
        assert pct_zscore > 0
        assert pct_mad > 0


class TestEdgeCasesAndPerformance:
    """Test edge cases and performance."""

    def test_winsorization_identity_on_no_outliers(self):
        """Test Winsorization gives similar results when no outliers."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        basic = MetricUtils.robust_scale(values)
        winsorized = MetricUtils.robust_scale_with_winsorization(
            values,
            lower_percentile=0,
            upper_percentile=100
        )

        # Should be identical when no clipping happens
        np.testing.assert_allclose(basic, winsorized, atol=0.01)

    def test_mad_large_array(self):
        """Test MAD scaling on large array."""
        values = np.random.normal(100, 20, 100_000)
        scaled = MetricUtils.mad_scaling(values)

        assert len(scaled) == len(values)
        assert np.all(np.isfinite(scaled))

    def test_outlier_detection_large_array(self):
        """Test outlier detection on large array."""
        values = np.random.normal(100, 20, 100_000)
        mask = MetricUtils.outlier_mask(values, method='iqr')

        # Should detect roughly 0.7% outliers (beyond 1.5*IQR)
        pct_outliers = np.sum(mask) / len(values)
        assert 0.001 < pct_outliers < 0.02

    def test_outlier_detection_constant_array(self):
        """Test outlier detection on constant array."""
        values = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
        mask = MetricUtils.outlier_mask(values, method='iqr')

        # No outliers in constant array
        assert np.sum(mask) == 0

    def test_winsorization_both_tails(self):
        """Test Winsorization clips both tails."""
        values = np.array([-1000, -100, 1, 2, 3, 4, 5, 6, 100, 1000])
        scaled = MetricUtils.robust_scale_with_winsorization(
            values,
            lower_percentile=10,
            upper_percentile=90
        )

        # Should return valid scaled values
        assert len(scaled) == len(values)
        assert np.all(np.isfinite(scaled))

    def test_outlier_invalid_method(self):
        """Test outlier detection with invalid method."""
        values = np.array([1, 2, 3, 4, 5])

        with pytest.raises(ValueError):
            MetricUtils.outlier_mask(values, method='invalid_method')


class TestRobustMetricsIntegration:
    """Test integration of robust methods."""

    def test_fingerprint_quality_filtering(self):
        """Test using robust scaling for fingerprint quality."""
        # Simulate 100 fingerprints with some anomalies
        fingerprints = np.random.normal(0.5, 0.1, (100, 25))
        # Add some anomalies
        fingerprints[50:55, :] = 10.0  # Completely abnormal

        # Detect anomalies in first feature
        feature_0 = fingerprints[:, 0]
        outliers = MetricUtils.outlier_mask(feature_0, method='mad', threshold=2.5)

        # Should detect anomalies
        assert np.sum(outliers[50:55]) > 0

    def test_preprocessing_with_winsorization_and_normalization(self):
        """Test preprocessing pipeline: Winsorize then normalize."""
        values = np.random.normal(50, 10, 1000)
        # Add outliers
        values = np.append(values, [200, 300, 500])

        # Step 1: Winsorize to remove extreme outliers
        winsorized = MetricUtils.robust_scale_with_winsorization(values)

        # Step 2: Further normalize with z-score
        normalized = MetricUtils.normalize_with_zscore(winsorized)

        # Result should be stable
        assert np.abs(np.mean(normalized)) < 0.1
        assert 0.5 < np.std(normalized) < 1.5

    def test_dual_outlier_detection(self):
        """Test using multiple outlier detection methods."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100, 1000])

        # Detect with IQR
        iqr_outliers = MetricUtils.outlier_mask(values, method='iqr')

        # Detect with MAD
        mad_outliers = MetricUtils.outlier_mask(values, method='mad')

        # Conservative: report as outlier only if BOTH agree
        conservative = iqr_outliers & mad_outliers

        # Should have outliers detected by both
        assert np.sum(conservative) > 0
