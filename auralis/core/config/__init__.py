"""
Core Configuration Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular configuration system for audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .factory import (
    create_adaptive_config,
    create_hybrid_config,
    create_reference_config,
)
from .genre_profiles import create_default_genre_profiles, get_default_genre_profile
from .preset_profiles import (
    PresetProfile,
    create_preset_profiles,
    get_available_presets,
    get_preset_profile,
)
from .settings import AdaptiveConfig, GenreProfile, LimiterConfig
from .unified_config import UnifiedConfig

__all__ = [
    'LimiterConfig',
    'AdaptiveConfig',
    'GenreProfile',
    'create_default_genre_profiles',
    'get_default_genre_profile',
    'PresetProfile',
    'get_preset_profile',
    'get_available_presets',
    'create_preset_profiles',
    'UnifiedConfig',
    'create_adaptive_config',
    'create_reference_config',
    'create_hybrid_config',
]
