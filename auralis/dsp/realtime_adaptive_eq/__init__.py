# -*- coding: utf-8 -*-

"""
Realtime Adaptive EQ Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Real-time adaptive EQ system with critical band analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .adaptation_engine import AdaptationEngine
from .factory import create_realtime_adaptive_eq
from .realtime_eq import RealtimeAdaptiveEQ
from .settings import RealtimeEQSettings

__all__ = [
    'RealtimeEQSettings',
    'AdaptationEngine',
    'RealtimeAdaptiveEQ',
    'create_realtime_adaptive_eq',
]
