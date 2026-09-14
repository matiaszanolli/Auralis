"""
Audio Processing Modes
~~~~~~~~~~~~~~~~~~~~~~

Modular processing engine with multiple mastering modes

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .adaptive_mode import AdaptiveMode
from .continuous_mode import ContinuousMode
from .eq_processor import EQProcessor
from .hybrid_mode import HybridMode

__all__ = [
    'AdaptiveMode',
    'HybridMode',
    'EQProcessor',
    'ContinuousMode',
]
