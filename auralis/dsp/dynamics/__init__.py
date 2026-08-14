"""
Dynamics Processing Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular dynamics processing system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .brick_wall_limiter import (
    BrickWallLimiter,
    BrickWallLimiterSettings,
    create_brick_wall_limiter,
)
from .compressor import AdaptiveCompressor, create_adaptive_compressor
from .envelope import EnvelopeFollower, create_envelope_follower
from .settings import (
    CompressorSettings,
    DynamicsMode,
    DynamicsSettings,
)

__all__ = [
    # Enums and settings
    'DynamicsMode',
    'CompressorSettings',
    'DynamicsSettings',
    'BrickWallLimiterSettings',

    # Processors
    'EnvelopeFollower',
    'AdaptiveCompressor',
    'BrickWallLimiter',

    # Factory functions
    'create_envelope_follower',
    'create_adaptive_compressor',
    'create_brick_wall_limiter',
]
