# -*- coding: utf-8 -*-

"""
Confidence Scoring for Adaptive Strategy Selection

Computes feature-level confidence scores to assess reliability of sampling
vs full-track analysis. Uses chunk variance analysis and feature stability
metrics to determine fallback strategies.

Confidence Tiers:
  - >= 0.90: High confidence (safe to use sampling)
  - 0.75-0.90: Acceptable confidence (use sampling with validation)
  - < 0.75: Low confidence (fallback to full-track for accuracy)

Feature Scoring:
  - Temporal features (centroid, spread, flux): Variance-based stability
  - Spectral features (centroid, bandwidth, contrast): FFT-based stability
  - Harmonic features (CQT, YIN pitch): Harmonic content stability
  - Percussive features (HPSS, dynamics): Percussion stability
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, cast
import numpy as np

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """
    Assesses confidence in sampled analysis by computing feature-level
    stability metrics and chunk variance analysis.
    """

    def __init__(self) -> None:
        """Initialize confidence scorer with default thresholds."""
        # Confidence thresholds
        self.high_confidence_threshold = 0.90
        self.acceptable_confidence_threshold = 0.75

        # Feature weight distribution
        self.feature_weights = {
            "temporal": 0.25,      # 25% - centroid, spread, flux
            "spectral": 0.30,      # 30% - centroid, bandwidth, contrast
            "harmonic": 0.25,      # 25% - CQT, pitch stability
            "percussive": 0.20,    # 20% - HPSS, dynamics
        }

        logger.debug("ConfidenceScorer initialized")

    def score_features(
        self,
        sampled_features: Dict[str, float],
        full_track_features: Dict[str, float],
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Compute overall confidence score by comparing sampled vs full-track features.

        Args:
            sampled_features: Feature dict from sampling strategy
            full_track_features: Feature dict from full-track strategy

        Returns:
            (confidence_score, details) where:
              - confidence_score: 0.0-1.0 indicating reliability
              - details: dict with per-feature breakdown
        """
        if not sampled_features or not full_track_features:
            logger.warning("Empty feature dicts provided")
            return 0.0, {"error": "Empty feature dictionaries"}

        details = {
            "temporal": self._score_temporal_features(sampled_features, full_track_features),
            "spectral": self._score_spectral_features(sampled_features, full_track_features),
            "harmonic": self._score_harmonic_features(sampled_features, full_track_features),
            "percussive": self._score_percussive_features(sampled_features, full_track_features),
        }

        # Compute weighted average confidence
        overall_score = sum(
            details[cat]["score"] * self.feature_weights[cat]
            for cat in details
        )

        details["overall"] = {
            "score": overall_score,
            "tier": self._determine_confidence_tier(overall_score),
            "recommendation": self._get_recommendation(overall_score),
        }

        logger.debug(
            f"Confidence score: {overall_score:.2f} ({details['overall']['tier']})"
        )

        return overall_score, details

    def _score_temporal_features(
        self, sampled: Dict[str, float], full_track: Dict[str, float]
    ) -> Dict[str, Any]:
        """Score temporal feature stability (centroid, spread, flux)."""
        score = self._compute_feature_similarity(
            sampled, full_track, ["temporal_centroid", "spectral_centroid_time"]
        )

        return {
            "score": score,
            "weight": self.feature_weights["temporal"],
            "category": "temporal",
        }

    def _score_spectral_features(
        self, sampled: Dict[str, float], full_track: Dict[str, float]
    ) -> Dict[str, Any]:
        """Score spectral feature stability (centroid, bandwidth, contrast)."""
        score = self._compute_feature_similarity(
            sampled, full_track, ["spectral_centroid", "spectral_bandwidth", "spectral_contrast"]
        )

        return {
            "score": score,
            "weight": self.feature_weights["spectral"],
            "category": "spectral",
        }

    def _score_harmonic_features(
        self, sampled: Dict[str, float], full_track: Dict[str, float]
    ) -> Dict[str, Any]:
        """Score harmonic feature stability (CQT, pitch)."""
        score = self._compute_feature_similarity(
            sampled, full_track, ["cqt_energy", "pitch_mean", "pitch_stability"]
        )

        return {
            "score": score,
            "weight": self.feature_weights["harmonic"],
            "category": "harmonic",
        }

    def _score_percussive_features(
        self, sampled: Dict[str, float], full_track: Dict[str, float]
    ) -> Dict[str, Any]:
        """Score percussive feature stability (HPSS, dynamics)."""
        score = self._compute_feature_similarity(
            sampled, full_track, ["percussive_energy", "dynamic_range", "rms_energy"]
        )

        return {
            "score": score,
            "weight": self.feature_weights["percussive"],
            "category": "percussive",
        }

    def _compute_feature_similarity(
        self, sampled: Dict[str, Any], full_track: Dict[str, Any], feature_names: List[str]
    ) -> float:
        """
        Compute similarity between sampled and full-track features.
        Returns 1.0 (identical) to 0.0 (completely different).
        """
        if not sampled or not full_track:
            return 0.0

        similarities = []
        for feature_name in feature_names:
            sampled_val = sampled.get(feature_name)
            full_val = full_track.get(feature_name)

            if sampled_val is None or full_val is None:
                continue

            # Compute similarity using percent error metric
            if full_val == 0 and sampled_val == 0:
                similarity = 1.0
            elif full_val == 0:
                # If reference is 0, use difference metric
                similarity = max(0.0, 1.0 - abs(sampled_val) / (abs(sampled_val) + 1e-10))
            else:
                # Percent error: abs((sampled - full) / full)
                percent_error = abs(sampled_val - full_val) / abs(full_val)
                # Convert error to similarity (0.05 error = 0.95 similarity)
                similarity = max(0.0, 1.0 - percent_error)

            similarities.append(similarity)

        # Return average similarity if we found any matching features
        if similarities:
            return float(np.mean(similarities))
        else:
            # No matching features found - return neutral score
            return 0.5

    def score_chunk_variance(
        self,
        sampled_chunks: List[Dict[str, float]],
        full_track_features: Dict[str, float],
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Assess confidence based on chunk-to-chunk variance in sampled analysis.

        Args:
            sampled_chunks: List of feature dicts from consecutive chunks
            full_track_features: Reference full-track features

        Returns:
            (variance_score, details) where variance_score indicates consistency
        """
        if not sampled_chunks or len(sampled_chunks) < 2:
            logger.warning("Insufficient chunks for variance analysis")
            return 0.5, {"error": "Need >= 2 chunks"}

        # Compute coefficient of variation for key features
        variations = []
        for feature_name in ["spectral_centroid", "temporal_centroid", "rms_energy"]:
            values = [chunk.get(feature_name, 0) for chunk in sampled_chunks]

            if not values or all(v == 0 for v in values):
                continue

            # Coefficient of variation = std / mean
            mean_val = np.mean(values)
            if mean_val > 0:
                cv = np.std(values) / mean_val
                variations.append(cv)

        # Score based on consistency (lower CV = higher consistency = higher confidence)
        # CV > 0.5 = high variance = low confidence
        # CV < 0.1 = low variance = high confidence
        avg_cv: Optional[float] = None
        if variations:
            avg_cv = float(np.mean(variations))
            # Convert CV to confidence: score = max(0, 1 - (cv * 2))
            variance_score = max(0.0, 1.0 - (avg_cv * 2))
        else:
            variance_score = 0.5  # Neutral if no features

        details = {
            "coefficient_of_variation": avg_cv,
            "score": variance_score,
            "tier": self._determine_confidence_tier(variance_score),
        }

        logger.debug(f"Chunk variance score: {variance_score:.2f}")
        return variance_score, details

    def _determine_confidence_tier(self, score: float) -> str:
        """Determine confidence tier from score."""
        if score >= self.high_confidence_threshold:
            return "HIGH"
        elif score >= self.acceptable_confidence_threshold:
            return "ACCEPTABLE"
        else:
            return "LOW"

    def _get_recommendation(self, confidence_score: float) -> str:
        """Get strategy recommendation based on confidence."""
        if confidence_score >= self.high_confidence_threshold:
            return "Use sampling (high confidence)"
        elif confidence_score >= self.acceptable_confidence_threshold:
            return "Use sampling with validation"
        else:
            return "Fallback to full-track for accuracy"

    def configure_thresholds(
        self,
        high_confidence: Optional[float] = None,
        acceptable_confidence: Optional[float] = None,
    ) -> None:
        """
        Configure confidence thresholds.

        Args:
            high_confidence: Score >= this = high confidence (default 0.90)
            acceptable_confidence: Score >= this = acceptable (default 0.75)
        """
        if high_confidence is not None:
            self.high_confidence_threshold = high_confidence
            logger.info(f"High confidence threshold set to {high_confidence}")

        if acceptable_confidence is not None:
            self.acceptable_confidence_threshold = acceptable_confidence
            logger.info(f"Acceptable confidence threshold set to {acceptable_confidence}")


def create_default_scorer() -> ConfidenceScorer:
    """
    Factory function to create a default confidence scorer.

    Returns:
        ConfidenceScorer with default configuration
    """
    return ConfidenceScorer()
