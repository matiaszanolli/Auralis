# -*- coding: utf-8 -*-

"""
Phase 7C: Confidence Scorer Tests

Comprehensive tests for feature-level confidence scoring and chunk variance analysis.

Test Categories:
  1. Feature similarity scoring (3 tests)
  2. Confidence tier classification (3 tests)
  3. Chunk variance analysis (3 tests)
  4. Threshold configuration (2 tests)
  5. Recommendation logic (2 tests)
  6. Integration tests (2 tests)
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.confidence_scorer import (
    ConfidenceScorer,
    create_default_scorer,
)


class TestFeatureSimilarityScoring:
    """Test scoring of feature similarity between strategies"""

    def test_identical_features_returns_high_score(self):
        """Identical features should return high score"""
        scorer = ConfidenceScorer()

        # Provide features across all categories for accurate scoring
        sampled = {
            "spectral_centroid": 2000.0,
            "spectral_bandwidth": 500.0,
            "temporal_centroid": 100.0,
            "pitch_mean": 440.0,
            "pitch_stability": 0.9,
            "percussive_energy": 0.3,
            "rms_energy": 0.5,
        }
        full_track = sampled.copy()

        score, details = scorer.score_features(sampled, full_track)

        assert score >= 0.90  # Near identical across all categories
        assert details["overall"]["tier"] == "HIGH"

    def test_slightly_different_features_returns_acceptable_score(self):
        """Features with < 10% difference should return acceptable score"""
        scorer = ConfidenceScorer()

        sampled = {
            "spectral_centroid": 2000.0,
            "temporal_centroid": 100.0,
            "pitch_mean": 440.0,
        }
        full_track = {
            "spectral_centroid": 2100.0,  # 5% difference
            "temporal_centroid": 105.0,   # 5% difference
            "pitch_mean": 450.0,          # 2.3% difference
        }

        score, details = scorer.score_features(sampled, full_track)

        assert 0.75 <= score < 0.95
        assert details["overall"]["tier"] == "ACCEPTABLE"

    def test_significantly_different_features_returns_low_score(self):
        """Features with > 50% difference should return low score"""
        scorer = ConfidenceScorer()

        sampled = {
            "spectral_centroid": 1000.0,
            "temporal_centroid": 50.0,
            "pitch_mean": 220.0,
        }
        full_track = {
            "spectral_centroid": 4000.0,  # 75% difference
            "temporal_centroid": 200.0,   # 75% difference
            "pitch_mean": 880.0,          # 75% difference
        }

        score, details = scorer.score_features(sampled, full_track)

        assert score < 0.75
        assert details["overall"]["tier"] == "LOW"


class TestConfidenceTierClassification:
    """Test confidence tier classification"""

    def test_high_confidence_tier_at_0_95(self):
        """Score >= 0.90 should be classified as HIGH"""
        scorer = ConfidenceScorer()

        sampled = {
            "spectral_centroid": 2000.0,
            "spectral_bandwidth": 500.0,
            "temporal_centroid": 100.0,
            "pitch_mean": 440.0,
            "pitch_stability": 0.95,
            "percussive_energy": 0.3,
            "rms_energy": 0.5,
        }
        full_track = {
            "spectral_centroid": 2010.0,
            "spectral_bandwidth": 505.0,
            "temporal_centroid": 101.0,
            "pitch_mean": 441.0,
            "pitch_stability": 0.96,
            "percussive_energy": 0.31,
            "rms_energy": 0.51,
        }

        score, details = scorer.score_features(sampled, full_track)

        assert score >= scorer.high_confidence_threshold
        assert details["overall"]["tier"] == "HIGH"

    def test_acceptable_confidence_tier_at_0_80(self):
        """Score 0.75-0.90 should be classified as ACCEPTABLE"""
        scorer = ConfidenceScorer()

        sampled = {
            "spectral_centroid": 2000.0,
            "spectral_bandwidth": 500.0,
            "temporal_centroid": 100.0,
            "pitch_mean": 440.0,
            "pitch_stability": 0.9,
            "percussive_energy": 0.3,
            "rms_energy": 0.5,
        }
        full_track = {
            "spectral_centroid": 2200.0,  # 10% difference
            "spectral_bandwidth": 600.0,  # 20% difference
            "temporal_centroid": 115.0,   # 15% difference
            "pitch_mean": 485.0,          # 10.2% difference
            "pitch_stability": 0.81,      # 10% difference
            "percussive_energy": 0.39,    # 30% difference
            "rms_energy": 0.6,            # 20% difference
        }

        score, details = scorer.score_features(sampled, full_track)

        # Score should be in acceptable range with ~10-20% differences
        assert 0.75 <= score < 0.92
        assert details["overall"]["tier"] == "ACCEPTABLE"

    def test_low_confidence_tier_below_0_75(self):
        """Score < 0.75 should be classified as LOW"""
        scorer = ConfidenceScorer()

        sampled = {"spectral_centroid": 1000.0, "pitch_mean": 220.0}
        full_track = {"spectral_centroid": 5000.0, "pitch_mean": 880.0}

        score, details = scorer.score_features(sampled, full_track)

        assert score < scorer.acceptable_confidence_threshold
        assert details["overall"]["tier"] == "LOW"


class TestChunkVarianceAnalysis:
    """Test chunk variance scoring for consistency analysis"""

    def test_consistent_chunks_returns_high_confidence(self):
        """Consistent chunk values should return high variance score"""
        scorer = ConfidenceScorer()

        # Three chunks with very similar features
        chunks = [
            {"spectral_centroid": 2000.0, "rms_energy": 0.5, "temporal_centroid": 100.0},
            {"spectral_centroid": 2010.0, "rms_energy": 0.51, "temporal_centroid": 101.0},
            {"spectral_centroid": 2005.0, "rms_energy": 0.49, "temporal_centroid": 100.5},
        ]

        reference = {
            "spectral_centroid": 2005.0,
            "rms_energy": 0.5,
            "temporal_centroid": 100.5,
        }

        score, details = scorer.score_chunk_variance(chunks, reference)

        assert score >= 0.85  # Consistent chunks
        assert details["tier"] == "HIGH"

    def test_inconsistent_chunks_returns_low_confidence(self):
        """Highly variable chunks should return low variance score"""
        scorer = ConfidenceScorer()

        # Three chunks with very different features
        chunks = [
            {"spectral_centroid": 1000.0, "rms_energy": 0.2, "temporal_centroid": 50.0},
            {"spectral_centroid": 3000.0, "rms_energy": 0.8, "temporal_centroid": 150.0},
            {"spectral_centroid": 2000.0, "rms_energy": 0.5, "temporal_centroid": 100.0},
        ]

        reference = {
            "spectral_centroid": 2000.0,
            "rms_energy": 0.5,
            "temporal_centroid": 100.0,
        }

        score, details = scorer.score_chunk_variance(chunks, reference)

        assert score < 0.75  # Inconsistent chunks
        assert details["tier"] == "LOW"

    def test_empty_chunks_returns_neutral_score(self):
        """Empty or insufficient chunks should return neutral score"""
        scorer = ConfidenceScorer()

        # Empty chunk list
        score, details = scorer.score_chunk_variance([], {})

        assert score == 0.5
        assert "error" in details


class TestThresholdConfiguration:
    """Test configurable confidence thresholds"""

    def test_configure_high_confidence_threshold(self):
        """Should be able to configure high confidence threshold"""
        scorer = ConfidenceScorer()

        # Default high threshold is 0.90
        assert scorer.high_confidence_threshold == 0.90

        # Change to 0.95
        scorer.configure_thresholds(high_confidence=0.95)

        assert scorer.high_confidence_threshold == 0.95

        # Score with complete features should yield a high value
        sampled = {
            "spectral_centroid": 2000.0,
            "spectral_bandwidth": 500.0,
            "temporal_centroid": 100.0,
            "pitch_mean": 440.0,
            "pitch_stability": 0.95,
            "percussive_energy": 0.3,
            "rms_energy": 0.5,
        }
        full_track = {
            "spectral_centroid": 2040.0,  # 2% diff
            "spectral_bandwidth": 510.0,  # 2% diff
            "temporal_centroid": 102.0,   # 2% diff
            "pitch_mean": 448.8,          # 2% diff
            "pitch_stability": 0.969,     # 2% diff
            "percussive_energy": 0.306,   # 2% diff
            "rms_energy": 0.51,           # 2% diff
        }

        score, details = scorer.score_features(sampled, full_track)

        # With 2% differences across all features, score should be high
        assert details["overall"]["score"] >= 0.95

    def test_configure_acceptable_confidence_threshold(self):
        """Should be able to configure acceptable confidence threshold"""
        scorer = ConfidenceScorer()

        # Default acceptable threshold is 0.75
        assert scorer.acceptable_confidence_threshold == 0.75

        # Change to 0.85
        scorer.configure_thresholds(acceptable_confidence=0.85)

        assert scorer.acceptable_confidence_threshold == 0.85


class TestRecommendationLogic:
    """Test strategy recommendations based on confidence"""

    def test_high_confidence_recommends_sampling(self):
        """High confidence should recommend sampling"""
        scorer = ConfidenceScorer()

        sampled = {
            "spectral_centroid": 2000.0,
            "spectral_bandwidth": 500.0,
            "temporal_centroid": 100.0,
            "pitch_mean": 440.0,
            "pitch_stability": 0.95,
            "percussive_energy": 0.3,
            "rms_energy": 0.5,
        }
        full_track = {
            "spectral_centroid": 2010.0,
            "spectral_bandwidth": 505.0,
            "temporal_centroid": 101.0,
            "pitch_mean": 441.0,
            "pitch_stability": 0.96,
            "percussive_energy": 0.31,
            "rms_energy": 0.51,
        }

        score, details = scorer.score_features(sampled, full_track)

        recommendation = details["overall"]["recommendation"]
        assert "sampling" in recommendation.lower()
        # High confidence tier should recommend "high confidence" or "use sampling"
        assert "high confidence" in recommendation.lower() or score >= 0.90

    def test_low_confidence_recommends_fulltrack(self):
        """Low confidence should recommend fallback to full-track"""
        scorer = ConfidenceScorer()

        sampled = {"spectral_centroid": 1000.0, "pitch_mean": 220.0}
        full_track = {"spectral_centroid": 5000.0, "pitch_mean": 880.0}

        score, details = scorer.score_features(sampled, full_track)

        recommendation = details["overall"]["recommendation"]
        assert "full-track" in recommendation.lower()
        assert "fallback" in recommendation.lower()


class TestIntegration:
    """Integration tests for confidence scorer"""

    def test_default_scorer_factory(self):
        """Default scorer factory should work correctly"""
        scorer = create_default_scorer()

        assert scorer is not None
        assert scorer.high_confidence_threshold == 0.90
        assert scorer.acceptable_confidence_threshold == 0.75

    def test_complete_scoring_workflow(self):
        """Complete workflow: score features and variance together"""
        scorer = ConfidenceScorer()

        # Sampled and full-track features
        sampled = {
            "spectral_centroid": 2000.0,
            "temporal_centroid": 100.0,
            "pitch_mean": 440.0,
            "rms_energy": 0.5,
        }
        full_track = {
            "spectral_centroid": 2050.0,
            "temporal_centroid": 105.0,
            "pitch_mean": 445.0,
            "rms_energy": 0.51,
        }

        # Score features
        feature_score, feature_details = scorer.score_features(sampled, full_track)

        # Score chunk variance
        chunks = [
            sampled.copy(),
            {"spectral_centroid": 2010.0, "temporal_centroid": 102.0},
            {"spectral_centroid": 1990.0, "temporal_centroid": 98.0},
        ]

        variance_score, variance_details = scorer.score_chunk_variance(chunks, full_track)

        # Both scores should be valid
        assert 0.0 <= feature_score <= 1.0
        assert 0.0 <= variance_score <= 1.0
        assert feature_details["overall"]["tier"] in ["HIGH", "ACCEPTABLE", "LOW"]
        assert variance_details["tier"] in ["HIGH", "ACCEPTABLE", "LOW"]


if __name__ == "__main__":
    # Run with: pytest tests/test_phase_7c_confidence_scorer.py -v
    pytest.main([__file__, "-v", "-s"])
