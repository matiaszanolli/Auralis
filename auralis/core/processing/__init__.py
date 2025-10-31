# -*- coding: utf-8 -*-

"""
Audio Processing Modes
~~~~~~~~~~~~~~~~~~~~~~

Modular processing engine with multiple mastering modes

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .adaptive_mode import AdaptiveMode
from .hybrid_mode import HybridMode
from .eq_processor import EQProcessor
from .realtime_processor import RealtimeProcessor

__all__ = [
    'AdaptiveMode',
    'HybridMode',
    'EQProcessor',
    'RealtimeProcessor',
]
