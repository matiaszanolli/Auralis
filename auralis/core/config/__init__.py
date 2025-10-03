# -*- coding: utf-8 -*-

"""
Core Configuration Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular configuration system for audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .settings import LimiterConfig, AdaptiveConfig, GenreProfile
from .genre_profiles import create_default_genre_profiles, get_default_genre_profile
from .unified_config import UnifiedConfig
from .factory import create_adaptive_config, create_reference_config, create_hybrid_config
from .legacy import Config  # Legacy Config class for backward compatibility

__all__ = [
    'LimiterConfig',
    'AdaptiveConfig',
    'GenreProfile',
    'create_default_genre_profiles',
    'get_default_genre_profile',
    'UnifiedConfig',
    'create_adaptive_config',
    'create_reference_config',
    'create_hybrid_config',
    'Config',  # Legacy
]
