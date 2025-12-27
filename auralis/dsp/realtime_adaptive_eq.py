# -*- coding: utf-8 -*-

"""
Real-time Adaptive EQ
~~~~~~~~~~~~~~~~~~~~~

Real-time adaptive EQ system with critical band analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

BACKWARD COMPATIBILITY WRAPPER
This file re-exports from the modular realtime_adaptive_eq package.
"""

# Re-export all public classes and functions for backward compatibility
from .realtime_adaptive_eq import (
    AdaptationEngine,
    RealtimeAdaptiveEQ,
    RealtimeEQSettings,
    create_realtime_adaptive_eq,
)

__all__ = [
    'RealtimeEQSettings',
    'AdaptationEngine',
    'RealtimeAdaptiveEQ',
    'create_realtime_adaptive_eq',
]
