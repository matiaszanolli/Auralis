# -*- coding: utf-8 -*-

"""
Realtime Adaptive EQ Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Real-time adaptive EQ system with critical band analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .settings import RealtimeEQSettings
from .adaptation_engine import AdaptationEngine
from .realtime_eq import RealtimeAdaptiveEQ
from .factory import create_realtime_adaptive_eq

__all__ = [
    'RealtimeEQSettings',
    'AdaptationEngine',
    'RealtimeAdaptiveEQ',
    'create_realtime_adaptive_eq',
]
