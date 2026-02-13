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
    AdaptiveConfig,
    GenreProfile,
    LimiterConfig,
    UnifiedConfig,
    create_adaptive_config,
    create_default_genre_profiles,
    create_hybrid_config,
    create_reference_config,
    get_default_genre_profile,
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
