# -*- coding: utf-8 -*-

"""
Unified Configuration System (Backward Compatibility Wrapper)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module maintains backward compatibility by re-exporting from the modular structure.
For new code, prefer importing from auralis.core.config directly.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Re-export all components from modular structure
from .config import (
    LimiterConfig,
    AdaptiveConfig,
    GenreProfile,
    create_default_genre_profiles,
    get_default_genre_profile,
    UnifiedConfig,
    create_adaptive_config,
    create_reference_config,
    create_hybrid_config,
)

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
]
