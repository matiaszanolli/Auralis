# -*- coding: utf-8 -*-

"""
Configuration Factory Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convenience functions for creating common configurations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

from .settings import AdaptiveConfig
from .unified_config import UnifiedConfig


def create_adaptive_config(**kwargs: Any) -> UnifiedConfig:
    """Create configuration optimized for adaptive processing"""
    adaptive_settings = {
        "mode": "adaptive",
        "enable_genre_detection": True,
        "enable_user_learning": True,
        "adaptation_strength": 0.8,
        **kwargs
    }
    return UnifiedConfig(adaptive=AdaptiveConfig(**adaptive_settings))


def create_reference_config(**kwargs: Any) -> UnifiedConfig:
    """Create configuration for traditional reference-based processing"""
    adaptive_settings = {
        "mode": "reference",
        "enable_genre_detection": False,
        "enable_user_learning": False,
        "adaptation_strength": 0.0,
        **kwargs
    }
    return UnifiedConfig(adaptive=AdaptiveConfig(**adaptive_settings))


def create_hybrid_config(**kwargs: Any) -> UnifiedConfig:
    """Create configuration for hybrid processing mode"""
    adaptive_settings = {
        "mode": "hybrid",
        "enable_genre_detection": True,
        "enable_user_learning": True,
        "adaptation_strength": 0.5,
        **kwargs
    }
    return UnifiedConfig(adaptive=AdaptiveConfig(**adaptive_settings))
