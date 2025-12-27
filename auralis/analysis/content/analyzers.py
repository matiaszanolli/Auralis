# -*- coding: utf-8 -*-

"""
Genre and Mood Analyzers
~~~~~~~~~~~~~~~~~~~~~~~~~

Genre classification and mood analysis for audio content

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from ..fingerprint.common_metrics import MetricUtils
from .content_operations import ContentAnalysisOperations


@dataclass
class ContentFeatures:
    """Basic audio content features"""
    # Amplitude characteristics
    rms_energy: float
    peak_energy: float
    crest_factor_db: float
    dynamic_range_db: float

    # Spectral characteristics
    spectral_centroid: float
    spectral_rolloff: float
    spectral_spread: float
    spectral_flux: float

    # Temporal characteristics
    zero_crossing_rate: float
    tempo_estimate: float
    attack_time_ms: float

    # Tonal characteristics
    fundamental_frequency: float
    harmonic_ratio: float
    inharmonicity: float

    # Rhythmic characteristics
    rhythm_strength: float
    beat_consistency: float


@dataclass
class GenreClassification:
    """Genre classification results"""
    primary_genre: str
    confidence: float
    genre_scores: Dict[str, float]
    features_used: List[str]


@dataclass
class MoodAnalysis:
    """Mood and energy analysis"""
    energy_level: str  # "low", "medium", "high"
    valence: float     # 0-1 (sad to happy)
    arousal: float     # 0-1 (calm to energetic)
    danceability: float # 0-1
    acousticness: float # 0-1


class GenreAnalyzer:
    """Rule-based genre classification"""

    def __init__(self) -> None:
        """Initialize genre analyzer with classification rules"""
        self.genre_rules = self._create_genre_classification_rules()

    def classify_genre(self, features: ContentFeatures) -> GenreClassification:
        """Classify genre based on extracted features"""
        genre_scores = {}

        for genre, rules in self.genre_rules.items():
            score = 0.0
            features_used = []

            # Apply each rule
            for rule in rules:
                feature_name = rule['feature']
                feature_value = getattr(features, feature_name)

                if 'min' in rule and feature_value >= rule['min']:
                    score += rule['weight']
                    features_used.append(feature_name)
                elif 'max' in rule and feature_value <= rule['max']:
                    score += rule['weight']
                    features_used.append(feature_name)
                elif 'range' in rule:
                    min_val, max_val = rule['range']
                    if min_val <= feature_value <= max_val:
                        score += rule['weight']
                        features_used.append(feature_name)

            genre_scores[genre] = score

        # Find best genre
        primary_genre = max(genre_scores, key=lambda g: genre_scores.get(g, 0.0))
        total_score = max(sum(genre_scores.values()), 1.0)
        # Normalize confidence to 0-1 using MetricUtils
        confidence = MetricUtils.normalize_to_range(genre_scores[primary_genre], total_score, clip=True)

        # Use default if confidence too low
        if confidence < 0.3:
            primary_genre = "pop"
            confidence = 0.5

        # Collect features used across all genres
        all_features_used = []
        for genre, rules in self.genre_rules.items():
            for rule in rules:
                all_features_used.append(rule['feature'])

        return GenreClassification(
            primary_genre=primary_genre,
            confidence=confidence,
            genre_scores=genre_scores,
            features_used=list(set(all_features_used))
        )

    def _create_genre_classification_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Create rule-based genre classification system"""
        return {
            "classical": [
                {"feature": "tempo_estimate", "range": (60, 120), "weight": 0.3},
                {"feature": "dynamic_range_db", "min": 20, "weight": 0.4},
                {"feature": "harmonic_ratio", "min": 0.6, "weight": 0.3},
                {"feature": "attack_time_ms", "min": 30, "weight": 0.2}
            ],
            "rock": [
                {"feature": "tempo_estimate", "range": (110, 160), "weight": 0.3},
                {"feature": "rhythm_strength", "min": 0.6, "weight": 0.4},
                {"feature": "spectral_centroid", "range": (1500, 3500), "weight": 0.2},
                {"feature": "dynamic_range_db", "range": (8, 20), "weight": 0.2}
            ],
            "electronic": [
                {"feature": "tempo_estimate", "range": (120, 160), "weight": 0.3},
                {"feature": "rhythm_strength", "min": 0.7, "weight": 0.4},
                {"feature": "spectral_centroid", "min": 2000, "weight": 0.2},
                {"feature": "beat_consistency", "min": 0.7, "weight": 0.3}
            ],
            "jazz": [
                {"feature": "tempo_estimate", "range": (80, 140), "weight": 0.2},
                {"feature": "harmonic_ratio", "min": 0.5, "weight": 0.4},
                {"feature": "dynamic_range_db", "min": 15, "weight": 0.3},
                {"feature": "rhythm_strength", "range": (0.3, 0.7), "weight": 0.2}
            ],
            "pop": [
                {"feature": "tempo_estimate", "range": (100, 140), "weight": 0.3},
                {"feature": "dynamic_range_db", "range": (6, 15), "weight": 0.3},
                {"feature": "beat_consistency", "min": 0.5, "weight": 0.3}
            ],
            "ambient": [
                {"feature": "tempo_estimate", "max": 100, "weight": 0.3},
                {"feature": "dynamic_range_db", "min": 25, "weight": 0.4},
                {"feature": "rhythm_strength", "max": 0.3, "weight": 0.4},
                {"feature": "attack_time_ms", "min": 50, "weight": 0.2}
            ]
        }


class MoodAnalyzer:
    """Mood and energy analysis"""

    def __init__(self) -> None:
        """Initialize mood analyzer with parameters"""
        self.mood_parameters = self._create_mood_parameters()

    def analyze_mood(self, features: ContentFeatures, audio: np.ndarray) -> MoodAnalysis:
        """Analyze mood and energy characteristics"""

        # Energy level classification
        if features.rms_energy > 0.3:
            energy_level = "high"
        elif features.rms_energy > 0.1:
            energy_level = "medium"
        else:
            energy_level = "low"

        # Valence (happiness/sadness) - based on harmonic content and key
        valence = features.harmonic_ratio * 0.5 + (1.0 - features.inharmonicity) * 0.3
        if features.spectral_centroid > 2000:
            valence += 0.2  # Brighter sounds tend to be happier
        valence = MetricUtils.normalize_to_range(valence, 1.0, clip=True)

        # Arousal (energy/calmness) - based on tempo and dynamics
        arousal = min(features.tempo_estimate / 180.0, 1.0) * 0.4
        arousal += min(features.dynamic_range_db / 30.0, 1.0) * 0.3
        arousal += features.rhythm_strength * 0.3
        arousal = MetricUtils.normalize_to_range(arousal, 1.0, clip=True)

        # Danceability - rhythm and tempo
        danceability = features.rhythm_strength * 0.5 + features.beat_consistency * 0.5
        if 100 <= features.tempo_estimate <= 130:  # Optimal dance tempo
            danceability *= 1.2
        danceability = MetricUtils.normalize_to_range(danceability, 1.0, clip=True)

        # Acousticness - based on harmonic content and inharmonicity
        acousticness = features.harmonic_ratio * 0.6 + (1.0 - features.inharmonicity) * 0.4
        if features.spectral_centroid < 2000:  # Warmer, more acoustic
            acousticness *= 1.1
        acousticness = MetricUtils.normalize_to_range(acousticness, 1.0, clip=True)

        return MoodAnalysis(
            energy_level=energy_level,
            valence=valence,
            arousal=arousal,
            danceability=danceability,
            acousticness=acousticness
        )

    def _create_mood_parameters(self) -> Dict[str, Any]:
        """Create mood analysis parameters"""
        return {
            "valence_weights": {
                "harmonic_ratio": 0.4,
                "spectral_brightness": 0.3,
                "inharmonicity": -0.3
            },
            "arousal_weights": {
                "tempo": 0.4,
                "dynamic_range": 0.3,
                "spectral_flux": 0.3
            }
        }


def create_genre_analyzer() -> GenreAnalyzer:
    """Factory function to create genre analyzer"""
    return GenreAnalyzer()


def create_mood_analyzer() -> MoodAnalyzer:
    """Factory function to create mood analyzer"""
    return MoodAnalyzer()
