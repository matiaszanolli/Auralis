# -*- coding: utf-8 -*-

"""
Real-time Audio Processor (Backward Compatibility Wrapper)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module maintains backward compatibility by re-exporting from the modular structure.
For new code, prefer importing from auralis.player.realtime directly.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Re-export all components from modular structure
from .realtime import (
    PerformanceMonitor,
    AdaptiveGainSmoother,
    RealtimeLevelMatcher,
    AutoMasterProcessor,
    RealtimeProcessor,
)

__all__ = [
    'PerformanceMonitor',
    'AdaptiveGainSmoother',
    'RealtimeLevelMatcher',
    'AutoMasterProcessor',
    'RealtimeProcessor',
]
