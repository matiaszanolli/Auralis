# -*- coding: utf-8 -*-

"""
Machine Learning Genre Classification System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ML-based genre classification with comprehensive feature extraction

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .features import AudioFeatures
from .feature_extractor import FeatureExtractor
from .genre_classifier import MLGenreClassifier, create_ml_genre_classifier
from .genre_weights import initialize_genre_weights

__all__ = [
    'AudioFeatures',
    'FeatureExtractor',
    'MLGenreClassifier',
    'create_ml_genre_classifier',
    'initialize_genre_weights',
]
