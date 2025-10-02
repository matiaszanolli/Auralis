# -*- coding: utf-8 -*-

"""
Content Analysis Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular content analysis system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .analyzers import (
    ContentFeatures, GenreClassification, MoodAnalysis,
    GenreAnalyzer, MoodAnalyzer,
    create_genre_analyzer, create_mood_analyzer
)
from .feature_extractors import FeatureExtractor, create_feature_extractor
from .recommendations import RecommendationEngine, create_recommendation_engine

__all__ = [
    # Data classes
    'ContentFeatures',
    'GenreClassification',
    'MoodAnalysis',

    # Analyzers
    'GenreAnalyzer',
    'MoodAnalyzer',
    'FeatureExtractor',
    'RecommendationEngine',

    # Factory functions
    'create_genre_analyzer',
    'create_mood_analyzer',
    'create_feature_extractor',
    'create_recommendation_engine',
]
