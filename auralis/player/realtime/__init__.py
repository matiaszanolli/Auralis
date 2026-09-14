"""
Real-time Processing Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular real-time audio processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .auto_master import AutoMasterProcessor
from .gain_smoother import AdaptiveGainSmoother
from .level_matcher import RealtimeLevelMatcher
from .performance_monitor import PerformanceMonitor
from .processor import RealtimeProcessor

__all__ = [
    'PerformanceMonitor',
    'AdaptiveGainSmoother',
    'RealtimeLevelMatcher',
    'AutoMasterProcessor',
    'RealtimeProcessor',
]
