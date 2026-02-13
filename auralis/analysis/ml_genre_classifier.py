"""
ML Genre Classifier - Backward Compatibility Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module maintains backward compatibility while the actual implementation
has been refactored into smaller, focused modules under auralis/analysis/ml/

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

DEPRECATED: Import from auralis.analysis.ml instead
"""

from .ml.feature_extractor import FeatureExtractor

# Re-export everything from the new modular structure
from .ml.features import AudioFeatures
from .ml.genre_classifier import MLGenreClassifier, create_ml_genre_classifier
from .ml.genre_weights import initialize_genre_weights

# Maintain all public exports for backward compatibility
__all__ = [
    'AudioFeatures',
    'FeatureExtractor',
    'MLGenreClassifier',
    'create_ml_genre_classifier',
    'initialize_genre_weights',
]
