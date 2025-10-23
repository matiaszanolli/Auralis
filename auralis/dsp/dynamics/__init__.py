# -*- coding: utf-8 -*-

"""
Dynamics Processing Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular dynamics processing system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .settings import (
    DynamicsMode, CompressorSettings, LimiterSettings, DynamicsSettings
)
from .envelope import EnvelopeFollower, create_envelope_follower
from .compressor import AdaptiveCompressor, create_adaptive_compressor
from .limiter import AdaptiveLimiter, create_adaptive_limiter
from .brick_wall_limiter import BrickWallLimiter, BrickWallLimiterSettings, create_brick_wall_limiter

__all__ = [
    # Enums and settings
    'DynamicsMode',
    'CompressorSettings',
    'LimiterSettings',
    'DynamicsSettings',
    'BrickWallLimiterSettings',

    # Processors
    'EnvelopeFollower',
    'AdaptiveCompressor',
    'AdaptiveLimiter',
    'BrickWallLimiter',

    # Factory functions
    'create_envelope_follower',
    'create_adaptive_compressor',
    'create_adaptive_limiter',
    'create_brick_wall_limiter',
]
