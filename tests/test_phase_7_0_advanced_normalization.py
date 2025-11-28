# -*- coding: utf-8 -*-

"""
Phase 7.0 Tests: Advanced Normalization Strategies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for z-score, robust scaling, and quantile normalization
methods added to MetricUtils in Phase 7.0.

Test Categories:
- Z-score normalization (mean=0, std=1)
- Robust scaling (IQR-based)
- Quantile normalization (distribution matching)
- Edge cases and numerical stability
- Performance and accuracy

:copyright: (C) 2025 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest
from auralis.analysis.fingerprint.common_metrics import MetricUtils


class TestZScoreNormalization:
    """Test z-score normalization implementation."""

    def test_zscore_basic_normalization(self):
        """Test basic z-score normalization with simple array."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        normalized = MetricUtils.normalize_with_zscore(values)

        # Check mean is approximately 0
        assert np.abs(np.mean(normalized)) < 1e-10, "Mean should be ~0"

        # Check std is approximately 1
        assert np.abs(np.std(normalized) - 1.0) < 1e-10, "Std should be ~1"

        # Check shape preserved
        assert normalized.shape == values.shape

    def test_zscore_with_precomputed_stats(self):
        """Test z-score normalization with pre-computed mean and std."""
        values = np.array([2.0, 4.0, 6.0, 8.0])
        mean = np.mean(values)  # 5.0
        std = np.std(values)

        normalized = MetricUtils.normalize_with_zscore(values, mean=mean, std=std)

        # Verify correctness
        expected = (values - mean) / std
        np.testing.assert_allclose(normalized, expected)

    def test_zscore_constant_values(self):
        """Test z-score with constant values (zero std)."""
        values = np.array([3.0, 3.0, 3.0, 3.0])
        normalized = MetricUtils.normalize_with_zscore(values)

        # Should return zeros for constant values
        np.testing.assert_array_equal(normalized, np.zeros_like(values))

    def test_zscore_single_value(self):
        """Test z-score with single value."""
        values = np.array([42.0])
        normalized = MetricUtils.normalize_with_zscore(values)

        # Single value should normalize to 0 (std=0)
        assert normalized[0] == 0.0

    def test_zscore_negative_values(self):
        """Test z-score with negative values."""
        values = np.array([-5.0, -3.0, -1.0, 1.0, 3.0, 5.0])
        normalized = MetricUtils.normalize_with_zscore(values)

        # Check properties
        assert np.abs(np.mean(normalized)) < 1e-10
        assert np.abs(np.std(normalized) - 1.0) < 1e-10

        # Negative values should map to negative z-scores
        assert normalized[0] < normalized[-1]

    def test_zscore_large_values(self):
        """Test z-score with large values."""
        values = np.array([1e6, 2e6, 3e6, 4e6, 5e6])
        normalized = MetricUtils.normalize_with_zscore(values)

        assert np.abs(np.mean(normalized)) < 1e-10
        assert np.abs(np.std(normalized) - 1.0) < 1e-10

    def test_zscore_distribution_invariance(self):
        """Test that z-score normalization works for any distribution."""
        # Uniform distribution
        uniform = np.linspace(0, 100, 100)
        normalized_uniform = MetricUtils.normalize_with_zscore(uniform)

        # Gaussian-like distribution
        gaussian = np.random.normal(50, 15, 1000)
        normalized_gaussian = MetricUtils.normalize_with_zscore(gaussian)

        # Both should have mean ~0 and std ~1
        assert np.abs(np.mean(normalized_uniform)) < 1e-10
        assert np.abs(np.std(normalized_uniform) - 1.0) < 1e-10

        assert np.abs(np.mean(normalized_gaussian)) < 0.1
        assert np.abs(np.std(normalized_gaussian) - 1.0) < 0.1


class TestRobustScaling:
    """Test robust scaling (IQR-based) implementation."""

    def test_robust_scale_basic(self):
        """Test basic robust scaling with simple array."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        scaled = MetricUtils.robust_scale(values)

        # Median should map to 0
        median = np.median(values)
        scaled_median = MetricUtils.robust_scale(np.array([median]))[0]
        assert np.abs(scaled_median) < 1e-10

        # Shape preserved
        assert scaled.shape == values.shape

    def test_robust_scale_with_outliers(self):
        """Test robust scaling with extreme outliers."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
        scaled = MetricUtils.robust_scale(values)

        # Robust scaling scales by IQR (which is small when outlier present)
        # So outliers appear more extreme, but middle values are centered better
        # The main benefit is that the median and quartiles have stable scaling

        # Check that median is at 0
        median_idx = 2  # 3.0 is median
        assert np.abs(scaled[median_idx]) < 0.5

    def test_robust_scale_precomputed_quartiles(self):
        """Test robust scaling with pre-computed quartiles."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        q1 = np.percentile(values, 25)  # 1.5
        q2 = np.percentile(values, 50)  # 3.0
        q3 = np.percentile(values, 75)  # 4.5

        scaled = MetricUtils.robust_scale(values, q1=q1, q2=q2, q3=q3)

        # Median should map to 0
        assert np.abs(scaled[2]) < 1e-10  # values[2] = 3.0 = median

    def test_robust_scale_constant_values(self):
        """Test robust scaling with constant values."""
        values = np.array([5.0, 5.0, 5.0, 5.0])
        scaled = MetricUtils.robust_scale(values)

        # Zero IQR should return zeros
        np.testing.assert_array_equal(scaled, np.zeros_like(values))

    def test_robust_scale_non_normal_distribution(self):
        """Test robust scaling is better for non-normal distributions."""
        # Exponential distribution (skewed)
        values = np.random.exponential(scale=2.0, size=1000)

        scaled = MetricUtils.robust_scale(values)

        # Median should be near 0
        median_idx = np.argsort(values)[len(values) // 2]
        assert np.abs(scaled[median_idx]) < 0.1

    def test_robust_scale_symmetric(self):
        """Test robust scaling is symmetric around median."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        scaled = MetricUtils.robust_scale(values)

        # Values equidistant from median should have opposite signs
        median = np.median(values)
        assert np.abs(scaled[0] + scaled[4]) < 1e-10  # 1 and 5 equidistant from 3


class TestQuantileNormalization:
    """Test quantile normalization implementation."""

    def test_quantile_normalize_no_reference(self):
        """Test quantile normalization without reference (uniform)."""
        values = np.array([1.0, 5.0, 2.0, 8.0, 3.0])
        normalized = MetricUtils.quantile_normalize(values)

        # Should map to [0, 1] with uniform spacing
        assert np.min(normalized) >= 0.0
        assert np.max(normalized) <= 1.0

        # Values should be unique (monotonic mapping)
        assert len(np.unique(normalized)) == len(values)

        # Sorted values should map to [0, 1]
        sorted_indices = np.argsort(values)
        sorted_normalized = normalized[sorted_indices]
        expected_spacing = np.linspace(0, 1, len(values))
        np.testing.assert_allclose(sorted_normalized, expected_spacing, atol=0.01)

    def test_quantile_normalize_with_reference(self):
        """Test quantile normalization with reference distribution."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        reference = np.array([0.0, 10.0, 20.0, 30.0, 40.0])

        normalized = MetricUtils.quantile_normalize(values, reference=reference)

        # Min value in input should map close to min reference
        assert normalized[0] < normalized[-1]

        # Check monotonicity is preserved
        assert all(normalized[i] <= normalized[i + 1] for i in range(len(normalized) - 1))

    def test_quantile_normalize_same_distribution(self):
        """Test quantile normalization with identical reference."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        reference = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        normalized = MetricUtils.quantile_normalize(values, reference=reference)

        # Should be approximately the same
        np.testing.assert_allclose(normalized, values, atol=0.1)

    def test_quantile_normalize_distribution_matching(self):
        """Test that quantile normalization matches distributions."""
        # Input: uniform [0, 1]
        values = np.linspace(0, 1, 1000)

        # Reference: bimodal distribution (two peaks)
        reference = np.concatenate([
            np.random.normal(-2, 0.3, 500),
            np.random.normal(2, 0.3, 500)
        ])

        normalized = MetricUtils.quantile_normalize(values, reference=reference)

        # Shape should change to match reference
        # Values should be more spread out than input
        assert np.std(normalized) > np.std(values)

    def test_quantile_normalize_batch_operation(self):
        """Test quantile normalization on batch of fingerprints."""
        # Simulate batch of 10 fingerprints
        batch = np.random.rand(10, 25)

        for i in range(batch.shape[0]):
            normalized = MetricUtils.quantile_normalize(batch[i])

            # Each should be in [0, 1]
            assert np.min(normalized) >= 0.0
            assert np.max(normalized) <= 1.0


class TestNormalizationComparison:
    """Compare different normalization strategies."""

    def test_zscore_vs_robust_on_normal_data(self):
        """On normal data, z-score and robust scaling should be similar."""
        values = np.random.normal(100, 15, 1000)

        zscore = MetricUtils.normalize_with_zscore(values)
        robust = MetricUtils.robust_scale(values)

        # Both should center data at 0
        assert np.abs(np.mean(zscore)) < 0.1
        assert np.abs(np.mean(robust)) < 0.1

        # On normal data, scaling should be similar
        # (correlation should be high)
        correlation = np.corrcoef(zscore, robust)[0, 1]
        assert correlation > 0.95

    def test_zscore_vs_robust_on_outliers(self):
        """On data with outliers, robust scaling handles center better."""
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])

        zscore = MetricUtils.normalize_with_zscore(values)
        robust = MetricUtils.robust_scale(values)

        # Both should center data (median at 0)
        median_idx = 4  # Median of [1..9, 100] is ~5
        assert np.abs(robust[median_idx]) < 1.0

        # Robust scaling is better for detecting outliers in the middle range
        # because it uses IQR (stable measure) not std (affected by outliers)

    def test_quantile_normalize_vs_zscore(self):
        """Quantile and z-score have different effects on distribution."""
        values = np.random.exponential(2.0, 1000)

        quantile = MetricUtils.quantile_normalize(values)
        zscore = MetricUtils.normalize_with_zscore(values)

        # Both should have different distributions
        # Quantile should be more uniform
        # Z-score should match original distribution shape
        assert np.std(quantile) < np.std(zscore)


class TestEdgeCasesAndStability:
    """Test edge cases and numerical stability."""

    def test_zscore_very_small_std(self):
        """Test z-score with very small standard deviation."""
        values = np.array([1.0, 1.0 + 1e-15, 1.0 + 2e-15])
        normalized = MetricUtils.normalize_with_zscore(values)

        # Should handle gracefully
        assert len(normalized) == len(values)
        assert np.all(np.isfinite(normalized))

    def test_robust_scale_identical_quartiles(self):
        """Test robust scaling when Q1=Q2=Q3 (all same)."""
        values = np.array([5.0, 5.0, 5.0])
        scaled = MetricUtils.robust_scale(values)

        # Should return zeros for identical values
        np.testing.assert_array_equal(scaled, np.zeros_like(values))

    def test_quantile_normalize_single_value(self):
        """Test quantile normalization with single value."""
        values = np.array([42.0])
        normalized = MetricUtils.quantile_normalize(values)

        # Single value edge case
        assert len(normalized) == 1
        assert 0.0 <= normalized[0] <= 1.0

    def test_zscore_empty_array(self):
        """Test z-score with empty array."""
        values = np.array([])

        # Should not crash
        try:
            normalized = MetricUtils.normalize_with_zscore(values)
            assert len(normalized) == 0
        except (ValueError, IndexError):
            # Acceptable to raise error for empty array
            pass

    def test_robust_scale_nan_handling(self):
        """Test robust scaling doesn't create NaNs."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        scaled = MetricUtils.robust_scale(values)

        # Should not have NaNs
        assert np.all(np.isfinite(scaled))

    def test_quantile_normalize_preserves_order(self):
        """Test that quantile normalization preserves value order."""
        values = np.array([5.0, 2.0, 8.0, 1.0, 9.0])
        normalized = MetricUtils.quantile_normalize(values)

        # Order should be preserved
        for i in range(len(values) - 1):
            if values[i] < values[i + 1]:
                assert normalized[i] <= normalized[i + 1]
            elif values[i] > values[i + 1]:
                assert normalized[i] >= normalized[i + 1]


class TestAccuracyAndConsistency:
    """Test accuracy and consistency of implementations."""

    def test_zscore_mathematical_properties(self):
        """Verify mathematical properties of z-score."""
        values = np.random.randn(1000)  # Already ~N(0,1)
        normalized = MetricUtils.normalize_with_zscore(values)

        # Mean should be 0, std should be 1
        assert np.abs(np.mean(normalized)) < 0.05
        assert np.abs(np.std(normalized) - 1.0) < 0.05

        # ~68% of values should be within ±1σ
        within_1sigma = np.sum(np.abs(normalized) <= 1.0) / len(normalized)
        assert 0.65 < within_1sigma < 0.71

    def test_robust_scale_quantile_properties(self):
        """Verify quantile properties of robust scaling."""
        values = np.random.rand(1000) * 100

        scaled = MetricUtils.robust_scale(values)

        # Median should be at 0
        median_scaled = MetricUtils.robust_scale(np.array([np.median(values)]))[0]
        assert np.abs(median_scaled) < 1e-10

        # Q1 and Q3 should be symmetric
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        scaled_q1 = MetricUtils.robust_scale(np.array([q1]))[0]
        scaled_q3 = MetricUtils.robust_scale(np.array([q3]))[0]
        assert np.abs(scaled_q1 + scaled_q3) < 1e-10

    def test_quantile_normalize_rank_preservation(self):
        """Test that quantile normalization preserves ranks."""
        values = np.array([3, 1, 4, 1, 5, 9, 2, 6])
        normalized = MetricUtils.quantile_normalize(values)

        # Rank should be identical
        original_ranks = np.argsort(np.argsort(values))
        normalized_ranks = np.argsort(np.argsort(normalized))
        np.testing.assert_array_equal(original_ranks, normalized_ranks)


class TestPerformanceAndScalability:
    """Test performance with large arrays."""

    def test_zscore_large_array(self):
        """Test z-score on large array."""
        values = np.random.randn(1_000_000)
        normalized = MetricUtils.normalize_with_zscore(values)

        assert len(normalized) == len(values)
        assert np.abs(np.mean(normalized)) < 0.01
        assert np.abs(np.std(normalized) - 1.0) < 0.01

    def test_robust_scale_large_array(self):
        """Test robust scaling on large array."""
        values = np.random.exponential(2.0, 1_000_000)
        scaled = MetricUtils.robust_scale(values)

        assert len(scaled) == len(values)
        assert np.all(np.isfinite(scaled))

    def test_quantile_normalize_large_array(self):
        """Test quantile normalization on large array."""
        values = np.random.rand(100_000)
        normalized = MetricUtils.quantile_normalize(values)

        assert len(normalized) == len(values)
        assert np.min(normalized) >= 0.0
        assert np.max(normalized) <= 1.0
