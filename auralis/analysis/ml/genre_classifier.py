"""
ML Genre Classifier
~~~~~~~~~~~~~~~~~~~

Machine learning-based genre classification using audio features

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from functools import lru_cache
from typing import Any, cast

import numpy as np

from ...utils.logging import debug
from .feature_extractor import FeatureExtractor
from .features import AudioFeatures
from .genre_weights import initialize_genre_weights

# Rate the default extractor is built for — the historical fixed rate and
# still the fallback when classify() gets no explicit rate.
DEFAULT_CLASSIFIER_SAMPLE_RATE = 44100


class RuleBasedGenreClassifier:
    """
    Rule-based genre classifier using hand-coded feature weights.

    Uses extracted audio features to classify music genres.
    """

    def __init__(self) -> None:
        """Initialize genre classifier"""
        # One extractor per distinct sample rate seen (#5244): the mel
        # filterbank is built once at construction from the configured rate,
        # so a single hardcoded 44100 extractor silently mis-scaled every
        # Hz-based feature when the pipeline runs at another rate. Extractors
        # are immutable after construction, so cached ones can be shared.
        self._feature_extractors: dict[int, FeatureExtractor] = {}
        self.feature_extractor = self._extractor_for(DEFAULT_CLASSIFIER_SAMPLE_RATE)
        self.genres = [
            "classical", "rock", "electronic", "jazz", "pop",
            "hip_hop", "acoustic", "ambient", "metal", "country"
        ]

        # Rule-based feature weights — hand-tuned, the accepted permanent
        # design (not loaded from a trained model; see genre_weights.py).
        self.weights = initialize_genre_weights(self.genres)
        self.confidence_threshold = 0.6

        debug(f"ML Genre Classifier initialized with {len(self.genres)} genres")

    def _extractor_for(self, sample_rate: int) -> FeatureExtractor:
        """Return a FeatureExtractor configured for ``sample_rate``.

        The cache holds at most one entry per distinct rate, and the rate is
        a per-process config value in practice, so it stays tiny. A benign
        race exists if two threads first request the same rate concurrently
        (one extractor is discarded); extract_features never mutates the
        extractor, so sharing the winner is safe.
        """
        extractor = self._feature_extractors.get(sample_rate)
        if extractor is None:
            extractor = FeatureExtractor(sample_rate=sample_rate)
            self._feature_extractors[sample_rate] = extractor
        return extractor

    def classify(self, audio: np.ndarray, sample_rate: int | None = None) -> dict[str, Any]:
        """
        Classify audio genre using ML model

        Args:
            audio: Audio signal to classify
            sample_rate: Sample rate of ``audio`` in Hz. When omitted, the
                default 44100 Hz extractor is used (historical behavior).

        Returns:
            Dictionary with classification results
        """
        debug("Running ML genre classification")

        # Extract features
        if sample_rate is None:
            extractor = self.feature_extractor
        else:
            extractor = self._extractor_for(sample_rate)
        features = extractor.extract_features(audio)

        # Calculate scores for each genre
        scores = {}
        for genre in self.genres:
            score = self._calculate_genre_score(features, genre)
            scores[genre] = score

        # Apply softmax for probability distribution
        probabilities = self._softmax(list(scores.values()))
        genre_probs = dict(zip(self.genres, probabilities))

        # Find the most likely genre
        primary_genre = max(genre_probs, key=lambda g: genre_probs[g])
        confidence = genre_probs[primary_genre]

        # If confidence is too low, fall back to "pop" as safe default
        if confidence < self.confidence_threshold:
            primary_genre = "pop"
            confidence = 0.5

        debug(f"ML Classification result: {primary_genre} (confidence: {confidence:.3f})")

        return {
            "primary": primary_genre,
            "confidence": float(confidence),
            "probabilities": {k: float(v) for k, v in genre_probs.items()},
            "features_used": self._get_feature_importance(primary_genre)
        }

    def _calculate_genre_score(self, features: AudioFeatures, genre: str) -> float:
        """Calculate classification score for a specific genre"""
        weights = self.weights[genre]
        score = weights['bias']

        # Add weighted feature contributions
        score += features.rms * weights['rms']
        score += features.crest_factor_db * weights['crest_factor_db']
        score += features.zero_crossing_rate * weights['zero_crossing_rate']
        score += features.spectral_centroid * weights['spectral_centroid'] / 1000  # Normalize
        score += features.spectral_rolloff * weights['spectral_rolloff'] / 1000
        score += features.spectral_bandwidth * weights['spectral_bandwidth'] / 1000
        score += features.spectral_flatness * weights['spectral_flatness']
        score += features.tempo * weights['tempo'] / 100  # Normalize
        score += features.tempo_stability * weights['tempo_stability']
        score += features.onset_rate * weights['onset_rate']
        score += features.harmonic_ratio * weights['harmonic_ratio']
        score += features.energy_low * weights['energy_low']
        score += features.energy_mid * weights['energy_mid']
        score += features.energy_high * weights['energy_high']

        return score

    def _softmax(self, scores: list[float]) -> list[float]:
        """Apply softmax to convert scores to probabilities"""
        scores_array = np.array(scores)
        exp_scores = np.exp(scores_array - np.max(scores_array))  # Numerical stability
        probabilities = exp_scores / np.sum(exp_scores)
        return cast(list[float], probabilities.tolist())

    def _get_feature_importance(self, genre: str) -> dict[str, float]:
        """Get feature importance for the classified genre"""
        weights = self.weights[genre]

        # Calculate absolute importance of each feature
        importance = {
            'spectral': abs(weights['spectral_centroid']) + abs(weights['spectral_rolloff']),
            'temporal': abs(weights['tempo']) + abs(weights['onset_rate']),
            'energy': abs(weights['energy_low']) + abs(weights['energy_mid']) + abs(weights['energy_high']),
            'harmonic': abs(weights['harmonic_ratio']),
            'dynamics': abs(weights['crest_factor_db']) + abs(weights['rms'])
        }

        # Normalize
        total_importance = sum(importance.values())
        if total_importance > 0:
            importance = {k: v / total_importance for k, v in importance.items()}

        return importance



@lru_cache(maxsize=1)
def create_ml_genre_classifier() -> RuleBasedGenreClassifier:
    """
    Factory function to create genre classifier.

    Result is cached so FeatureExtractor and genre weights
    are only allocated once (fixes #2528).

    Returns:
        Cached RuleBasedGenreClassifier instance
    """
    return RuleBasedGenreClassifier()
