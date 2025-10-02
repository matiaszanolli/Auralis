# -*- coding: utf-8 -*-

"""
ML Genre Classifier
~~~~~~~~~~~~~~~~~~~

Machine learning-based genre classification using audio features

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, List, Optional

from .features import AudioFeatures
from .feature_extractor import FeatureExtractor
from .genre_weights import initialize_genre_weights
from ...utils.logging import debug


class MLGenreClassifier:
    """
    Machine Learning-based genre classifier

    Uses extracted audio features to classify music genres
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize genre classifier

        Args:
            model_path: Optional path to saved model weights
        """
        self.feature_extractor = FeatureExtractor()
        self.genres = [
            "classical", "rock", "electronic", "jazz", "pop",
            "hip_hop", "acoustic", "ambient", "metal", "country"
        ]

        # Model weights (this would normally be loaded from a trained model)
        self.weights = initialize_genre_weights(self.genres)
        self.confidence_threshold = 0.6

        debug(f"ML Genre Classifier initialized with {len(self.genres)} genres")

    def classify(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Classify audio genre using ML model

        Args:
            audio: Audio signal to classify

        Returns:
            Dictionary with classification results
        """
        debug("Running ML genre classification")

        # Extract features
        features = self.feature_extractor.extract_features(audio)

        # Calculate scores for each genre
        scores = {}
        for genre in self.genres:
            score = self._calculate_genre_score(features, genre)
            scores[genre] = score

        # Apply softmax for probability distribution
        probabilities = self._softmax(list(scores.values()))
        genre_probs = dict(zip(self.genres, probabilities))

        # Find the most likely genre
        primary_genre = max(genre_probs, key=genre_probs.get)
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
            "features_used": self._get_feature_importance(features, primary_genre)
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

    def _softmax(self, scores: List[float]) -> List[float]:
        """Apply softmax to convert scores to probabilities"""
        scores_array = np.array(scores)
        exp_scores = np.exp(scores_array - np.max(scores_array))  # Numerical stability
        probabilities = exp_scores / np.sum(exp_scores)
        return probabilities.tolist()

    def _get_feature_importance(self, features: AudioFeatures, genre: str) -> Dict[str, float]:
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

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the classifier model"""
        return {
            "model_type": "Linear Feature-based Classifier",
            "num_genres": len(self.genres),
            "genres": self.genres,
            "confidence_threshold": self.confidence_threshold,
            "feature_count": {
                "basic": 4,
                "spectral": 7,
                "temporal": 3,
                "harmonic": 2,
                "energy": 3,
                "advanced": 31  # MFCC + Chroma + Tonnetz
            }
        }


def create_ml_genre_classifier(model_path: Optional[str] = None) -> MLGenreClassifier:
    """
    Factory function to create ML genre classifier

    Args:
        model_path: Optional path to saved model weights

    Returns:
        Configured MLGenreClassifier instance
    """
    return MLGenreClassifier(model_path)
