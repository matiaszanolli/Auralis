"""
Dynamics Processing Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular dynamics processing system

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .brick_wall_limiter import (
    BrickWallLimiter,
    BrickWallLimiterSettings,
    create_brick_wall_limiter,
)
from .compressor import AdaptiveCompressor
from .envelope import EnvelopeFollower
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
    'create_brick_wall_limiter',
]
