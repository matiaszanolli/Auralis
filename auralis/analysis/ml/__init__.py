"""
Machine Learning Genre Classification System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ML-based genre classification with comprehensive feature extraction

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .feature_extractor import FeatureExtractor
from .features import AudioFeatures
from .genre_classifier import RuleBasedGenreClassifier, create_ml_genre_classifier
from .genre_weights import initialize_genre_weights

__all__ = [
    'AudioFeatures',
    'FeatureExtractor',
    'RuleBasedGenreClassifier',
    'create_ml_genre_classifier',
    'initialize_genre_weights',
]
