# -*- coding: utf-8 -*-

"""
Phase 7.5.2 Tests: Fingerprint Validator

Tests for FingerprintValidator with comprehensive coverage:
- Similarity metric calculation
- Per-metric accuracy tracking
- Confidence assessment
- Validation state machine
- Edge cases and robustness
"""

import pytest
import numpy as np
from auralis.library.caching.fingerprint_validator import (
    FingerprintValidator,
    ValidationResult,
)


class TestValidationResult:
    """Test ValidationResult class."""

    def test_validation_result_creation(self):
        """Test creating validation result."""
        result = ValidationResult(
            is_valid=True,
            similarity_score=0.98,
            metric_scores={'metric1': 0.97, 'metric2': 0.99},
            confidence_level='high',
        )

        assert result.is_valid is True
        assert result.similarity_score == 0.98
        assert result.confidence_level == 'high'

    def test_validation_result_repr(self):
        """Test validation result string representation."""
        result = ValidationResult(
            is_valid=True,
            similarity_score=0.98,
            metric_scores={'metric1': 0.97},
            confidence_level='high',
        )

        repr_str = repr(result)
        assert 'ValidationResult' in repr_str
        assert 'valid=True' in repr_str
        assert 'similarity=0.980' in repr_str
        assert 'high' in repr_str


class TestCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_identical_fingerprints(self):
        """Test similarity of identical fingerprints."""
        fp1 = {
            'metric1': 0.5,
            'metric2': 0.6,
            'metric3': 0.7,
        }
        fp2 = {
            'metric1': 0.5,
            'metric2': 0.6,
            'metric3': 0.7,
        }

        similarity = FingerprintValidator._cosine_similarity(fp1, fp2)
        assert similarity == pytest.approx(1.0)

    def test_orthogonal_fingerprints(self):
        """Test similarity of orthogonal fingerprints."""
        fp1 = {'metric1': 1.0, 'metric2': 0.0}
        fp2 = {'metric1': 0.0, 'metric2': 1.0}

        similarity = FingerprintValidator._cosine_similarity(fp1, fp2)
        assert similarity == pytest.approx(0.0)

    def test_opposite_fingerprints(self):
        """Test similarity of opposite direction vectors.

        Note: Fingerprints won't have negative values in practice, but we test
        that negative similarity is clamped to 0.0 for use as confidence metric.
        """
        fp1 = {'metric1': 1.0, 'metric2': 1.0}
        fp2 = {'metric1': -1.0, 'metric2': -1.0}

        similarity = FingerprintValidator._cosine_similarity(fp1, fp2)
        # Negative similarity is clamped to 0
        assert similarity == pytest.approx(0.0)

    def test_partially_similar(self):
        """Test partially similar fingerprints."""
        fp1 = {
            'metric1': 1.0,
            'metric2': 0.0,
            'metric3': 0.0,
        }
        fp2 = {
            'metric1': 0.866,  # cos(30°)
            'metric2': 0.5,    # sin(30°)
            'metric3': 0.0,
        }

        similarity = FingerprintValidator._cosine_similarity(fp1, fp2)
        # cos(30°) ≈ 0.866
        assert similarity == pytest.approx(0.866, abs=0.01)

    def test_empty_fingerprints(self):
        """Test similarity with empty fingerprints."""
        fp1 = {}
        fp2 = {}

        similarity = FingerprintValidator._cosine_similarity(fp1, fp2)
        assert similarity == 0.0

    def test_no_common_metrics(self):
        """Test fingerprints with no common metrics."""
        fp1 = {'metric1': 0.5}
        fp2 = {'metric2': 0.6}

        similarity = FingerprintValidator._cosine_similarity(fp1, fp2)
        assert similarity == 0.0


class TestMetricAccuracy:
    """Test per-metric accuracy calculation."""

    def test_perfect_metric_match(self):
        """Test accuracy for perfect metric match."""
        accuracy = FingerprintValidator._calculate_single_metric_accuracy(
            streaming_val=0.5,
            batch_val=0.5,
            metric_range=(0.0, 1.0),
        )
        assert accuracy == pytest.approx(1.0)

    def test_metric_half_range_error(self):
        """Test accuracy at half range error."""
        accuracy = FingerprintValidator._calculate_single_metric_accuracy(
            streaming_val=0.2,
            batch_val=0.7,
            metric_range=(0.0, 1.0),
        )
        # Error of 0.5 in range of 1.0 = accuracy of 0.5
        assert accuracy == pytest.approx(0.5)

    def test_metric_out_of_range(self):
        """Test accuracy when error exceeds range."""
        accuracy = FingerprintValidator._calculate_single_metric_accuracy(
            streaming_val=0.0,
            batch_val=1.5,
            metric_range=(0.0, 1.0),
        )
        # Error of 1.5 exceeds range of 1.0, clipped to 0
        assert accuracy == pytest.approx(0.0)

    def test_large_range_metric_relative_error(self):
        """Test relative error for large range metrics (tempo)."""
        # 10% error on tempo (batch=120, streaming=108)
        accuracy = FingerprintValidator._calculate_single_metric_accuracy(
            streaming_val=108.0,
            batch_val=120.0,
            metric_range=(40.0, 200.0),  # Large range
        )
        # 10% relative error = 0.9 accuracy
        assert accuracy == pytest.approx(0.9, abs=0.01)

    def test_metric_accuracy_collection(self):
        """Test collecting accuracy for multiple metrics.

        Note: This test uses actual streaming metrics from STREAMING_METRICS list
        since _calculate_metric_accuracy only processes metrics defined there.
        """
        # Use first 3 actual streaming metrics
        metric_names = FingerprintValidator.STREAMING_METRICS[:3]

        streaming = {
            metric_names[0]: 0.5,
            metric_names[1]: 100.0,
            metric_names[2]: 0.8,
        }
        batch = {
            metric_names[0]: 0.5,
            metric_names[1]: 100.0,
            metric_names[2]: 0.7,
        }

        metric_scores = FingerprintValidator._calculate_metric_accuracy(
            streaming, batch
        )

        # Should have accuracy scores for metrics that match
        assert len(metric_scores) > 0
        assert metric_scores[metric_names[0]] == pytest.approx(1.0)  # Perfect match
        assert metric_scores[metric_names[1]] == pytest.approx(1.0)  # Perfect match
        assert metric_scores[metric_names[2]] == pytest.approx(0.9)  # 0.8 vs 0.7 = 90% accuracy


class TestConfidenceAssessment:
    """Test confidence level assessment."""

    def test_high_confidence(self):
        """Test high confidence assessment."""
        metric_scores = {
            'metric1': 0.95,
            'metric2': 0.96,
            'metric3': 0.97,
        }

        confidence = FingerprintValidator._assess_confidence(
            similarity_score=0.98,
            metric_scores=metric_scores,
        )
        assert confidence == 'high'

    def test_medium_confidence(self):
        """Test medium confidence assessment."""
        metric_scores = {
            'metric1': 0.85,
            'metric2': 0.86,
            'metric3': 0.87,
        }

        confidence = FingerprintValidator._assess_confidence(
            similarity_score=0.88,
            metric_scores=metric_scores,
        )
        assert confidence == 'medium'

    def test_low_confidence(self):
        """Test low confidence assessment."""
        metric_scores = {
            'metric1': 0.7,
            'metric2': 0.6,
            'metric3': 0.5,
        }

        confidence = FingerprintValidator._assess_confidence(
            similarity_score=0.75,
            metric_scores=metric_scores,
        )
        assert confidence == 'low'

    def test_empty_metrics_low_confidence(self):
        """Test that empty metrics result in low confidence."""
        confidence = FingerprintValidator._assess_confidence(
            similarity_score=0.99,
            metric_scores={},
        )
        assert confidence == 'low'


class TestValidateFingerprintPair:
    """Test full fingerprint validation."""

    def test_validate_identical_fingerprints(self):
        """Test validating identical fingerprints."""
        streaming = {
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 2.0,
            'peak_consistency': 0.6,
            'spectral_centroid': 0.4,
            'spectral_rolloff': 0.5,
            'spectral_flatness': 0.3,
            'tempo_bpm': 120.0,
            'rhythm_stability': 0.7,
            'transient_density': 0.6,
            'silence_ratio': 0.1,
            'harmonic_ratio': 0.8,
            'pitch_stability': 0.9,
            'chroma_energy': 0.7,
        }

        batch = np.array([
            0.5, 2.0, 0.6, 0.4, 0.5, 0.3, 120.0, 0.7, 0.6, 0.1, 0.8, 0.9, 0.7
        ])

        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)

        assert result.is_valid is True
        assert result.similarity_score == pytest.approx(1.0)
        assert result.confidence_level == 'high'

    def test_validate_similar_fingerprints(self):
        """Test validating similar but not identical fingerprints."""
        streaming = {
            'dynamic_range_variation': 0.51,
            'loudness_variation_std': 2.05,
            'peak_consistency': 0.59,
            'spectral_centroid': 0.41,
            'spectral_rolloff': 0.51,
            'spectral_flatness': 0.31,
            'tempo_bpm': 121.0,
            'rhythm_stability': 0.69,
            'transient_density': 0.59,
            'silence_ratio': 0.11,
            'harmonic_ratio': 0.79,
            'pitch_stability': 0.89,
            'chroma_energy': 0.71,
        }

        batch = np.array([
            0.5, 2.0, 0.6, 0.4, 0.5, 0.3, 120.0, 0.7, 0.6, 0.1, 0.8, 0.9, 0.7
        ])

        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)

        assert result.similarity_score > 0.95
        assert result.confidence_level in ['high', 'medium']

    def test_validate_dissimilar_fingerprints(self):
        """Test validating fingerprints with per-metric differences.

        Creates fingerprints with significant per-metric differences to produce
        low per-metric accuracy scores, resulting in low confidence validation.
        Note: Cosine similarity measures vector direction, not absolute differences,
        so we focus on per-metric accuracy instead.
        """
        streaming = {
            'dynamic_range_variation': 0.2,
            'loudness_variation_std': 1.0,
            'peak_consistency': 0.1,
            'spectral_centroid': 0.15,
            'spectral_rolloff': 0.25,
            'spectral_flatness': 0.2,
            'tempo_bpm': 80.0,
            'rhythm_stability': 0.25,
            'transient_density': 0.15,
            'silence_ratio': 0.6,
            'harmonic_ratio': 0.15,
            'pitch_stability': 0.2,
            'chroma_energy': 0.15,
        }

        batch = np.array([
            0.8, 8.0, 0.85, 0.85, 0.8, 0.9, 160.0, 0.9, 0.8, 0.01, 0.85, 0.9, 0.85
        ])

        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)

        # Even though cosine similarity might be high (due to vector direction),
        # per-metric accuracy should be low due to large differences in individual metrics
        assert len(result.metric_scores) > 0
        avg_metric_accuracy = np.mean(list(result.metric_scores.values()))
        assert avg_metric_accuracy < 0.9  # Poor per-metric accuracy
        assert result.confidence_level in ['low', 'medium']  # Low confidence due to poor metrics


class TestIsValidFingerprint:
    """Test fingerprint range validation."""

    def test_valid_fingerprint_ranges(self):
        """Test fingerprint with all valid ranges."""
        fingerprint = {
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 5.0,
            'peak_consistency': 0.7,
            'spectral_centroid': 0.4,
            'spectral_rolloff': 0.6,
            'spectral_flatness': 0.5,
            'tempo_bpm': 120.0,
            'rhythm_stability': 0.8,
            'transient_density': 0.6,
            'silence_ratio': 0.2,
            'harmonic_ratio': 0.7,
            'pitch_stability': 0.85,
            'chroma_energy': 0.75,
        }

        assert FingerprintValidator.is_valid_fingerprint(fingerprint) is True

    def test_invalid_tempo_range(self):
        """Test fingerprint with invalid tempo."""
        fingerprint = {
            'tempo_bpm': 250.0,  # Out of range (40-200)
        }

        assert FingerprintValidator.is_valid_fingerprint(fingerprint) is False

    def test_invalid_normalized_metric(self):
        """Test fingerprint with invalid normalized metric."""
        fingerprint = {
            'spectral_centroid': 1.5,  # Out of range (0-1)
        }

        assert FingerprintValidator.is_valid_fingerprint(fingerprint) is False

    def test_boundary_values(self):
        """Test fingerprint with boundary values."""
        fingerprint = {
            'tempo_bpm': 40.0,  # Min boundary
            'spectral_centroid': 0.0,  # Min boundary
            'spectral_rolloff': 1.0,  # Max boundary
        }

        assert FingerprintValidator.is_valid_fingerprint(fingerprint) is True


class TestMetricDescriptions:
    """Test metric description retrieval."""

    def test_get_metric_descriptions(self):
        """Test getting descriptions for known metrics."""
        metrics = [
            'dynamic_range_variation',
            'tempo_bpm',
            'harmonic_ratio',
            'spectral_centroid',
        ]

        for metric in metrics:
            desc = FingerprintValidator.get_metric_description(metric)
            assert len(desc) > 0
            assert metric.replace('_', ' ') in desc.lower() or 'bpm' in desc.lower()

    def test_get_unknown_metric_description(self):
        """Test description for unknown metric."""
        desc = FingerprintValidator.get_metric_description('unknown_metric')
        assert desc == 'unknown_metric'


class TestValidationEdgeCases:
    """Test edge cases in validation."""

    def test_fingerprint_with_missing_metrics(self):
        """Test validation with missing metrics."""
        streaming = {
            'dynamic_range_variation': 0.5,
            'spectral_centroid': 0.4,
            # Missing other metrics
        }

        batch = np.array([
            0.5, 2.0, 0.6, 0.4, 0.5, 0.3, 120.0, 0.7, 0.6, 0.1, 0.8, 0.9, 0.7
        ])

        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)

        # Should still calculate similarity with available metrics
        assert result.similarity_score >= 0.0
        assert result.similarity_score <= 1.0

    def test_fingerprint_with_zero_values(self):
        """Test validation with zero values."""
        streaming = {f'metric{i}': 0.0 for i in range(13)}
        batch = np.zeros(13)

        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)

        # Zero vectors have zero similarity (magnitude = 0)
        assert result.similarity_score == 0.0

    def test_fingerprint_with_nan_values(self):
        """Test validation with NaN values."""
        streaming = {
            'dynamic_range_variation': np.nan,
            'spectral_centroid': 0.4,
        }

        batch = np.array([
            np.nan, 2.0, 0.6, 0.4, 0.5, 0.3, 120.0, 0.7, 0.6, 0.1, 0.8, 0.9, 0.7
        ])

        # Should handle gracefully
        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)
        assert isinstance(result.similarity_score, float)

    def test_batch_array_too_short(self):
        """Test batch array shorter than expected."""
        streaming = {f'metric{i}': 0.5 for i in range(13)}
        batch = np.array([0.5, 0.5])  # Only 2 dimensions

        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)

        # Should still compute with available data
        assert result.similarity_score >= 0.0


class TestValidationIntegration:
    """Integration tests for validation workflow."""

    def test_full_validation_workflow(self):
        """Test complete validation workflow."""
        # Create streaming fingerprint (from progressive analysis)
        streaming = {
            'dynamic_range_variation': 0.52,
            'loudness_variation_std': 2.1,
            'peak_consistency': 0.61,
            'spectral_centroid': 0.41,
            'spectral_rolloff': 0.51,
            'spectral_flatness': 0.31,
            'tempo_bpm': 121.5,
            'rhythm_stability': 0.71,
            'transient_density': 0.61,
            'silence_ratio': 0.11,
            'harmonic_ratio': 0.81,
            'pitch_stability': 0.91,
            'chroma_energy': 0.71,
        }

        # Create batch fingerprint (25D, use first 13)
        batch = np.array([
            0.5, 2.0, 0.6, 0.4, 0.5, 0.3, 120.0, 0.7, 0.6, 0.1, 0.8, 0.9, 0.7,
            # Additional 12 dimensions (batch-only)
            0.75, 0.65, 0.55, 0.45, 0.35, 0.25, 0.15, 0.05, 0.95, 0.85, 0.75, 0.65,
        ])

        # Validate
        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)

        # Check results
        assert isinstance(result, ValidationResult)
        assert result.is_valid in [True, False]
        assert 0.0 <= result.similarity_score <= 1.0
        assert result.confidence_level in ['high', 'medium', 'low']
        assert len(result.metric_scores) > 0

    def test_validation_comparison_accuracy(self):
        """Test that validation accurately identifies differences."""
        streaming_good = {
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 2.0,
            'peak_consistency': 0.6,
            'spectral_centroid': 0.4,
            'spectral_rolloff': 0.5,
            'spectral_flatness': 0.3,
            'tempo_bpm': 120.0,
            'rhythm_stability': 0.7,
            'transient_density': 0.6,
            'silence_ratio': 0.1,
            'harmonic_ratio': 0.8,
            'pitch_stability': 0.9,
            'chroma_energy': 0.7,
        }

        streaming_poor = {
            'dynamic_range_variation': 0.2,
            'loudness_variation_std': 0.5,
            'peak_consistency': 0.3,
            'spectral_centroid': 0.1,
            'spectral_rolloff': 0.2,
            'spectral_flatness': 0.1,
            'tempo_bpm': 80.0,
            'rhythm_stability': 0.3,
            'transient_density': 0.2,
            'silence_ratio': 0.5,
            'harmonic_ratio': 0.2,
            'pitch_stability': 0.3,
            'chroma_energy': 0.2,
        }

        batch = np.array([
            0.5, 2.0, 0.6, 0.4, 0.5, 0.3, 120.0, 0.7, 0.6, 0.1, 0.8, 0.9, 0.7
        ])

        result_good = FingerprintValidator.validate_fingerprint_pair(
            streaming_good, batch
        )
        result_poor = FingerprintValidator.validate_fingerprint_pair(
            streaming_poor, batch
        )

        # Good match should have higher similarity than poor match
        assert result_good.similarity_score > result_poor.similarity_score

        # Good match should be valid if close enough
        if result_good.similarity_score >= 0.95:
            assert result_good.is_valid is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
