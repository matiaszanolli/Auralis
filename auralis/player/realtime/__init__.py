# -*- coding: utf-8 -*-

"""
Real-time Processing Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular real-time audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .performance_monitor import PerformanceMonitor
from .gain_smoother import AdaptiveGainSmoother
from .level_matcher import RealtimeLevelMatcher
from .auto_master import AutoMasterProcessor
from .processor import RealtimeProcessor

__all__ = [
    'PerformanceMonitor',
    'AdaptiveGainSmoother',
    'RealtimeLevelMatcher',
    'AutoMasterProcessor',
    'RealtimeProcessor',
]
