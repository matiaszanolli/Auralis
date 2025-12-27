# -*- coding: utf-8 -*-

"""
Hybrid Processor Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular components for hybrid audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .dynamics_manager import DynamicsManager
from .preference_manager import PreferenceManager
from .realtime_manager import RealtimeEQManager

__all__ = [
    'RealtimeEQManager',
    'DynamicsManager',
    'PreferenceManager',
]
