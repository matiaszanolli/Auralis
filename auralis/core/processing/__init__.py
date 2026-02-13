"""
Audio Processing Modes
~~~~~~~~~~~~~~~~~~~~~~

Modular processing engine with multiple mastering modes

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .adaptive_mode import AdaptiveMode
from .continuous_mode import ContinuousMode
from .eq_processor import EQProcessor
from .hybrid_mode import HybridMode
from .realtime_dsp_pipeline import RealtimeDSPPipeline

__all__ = [
    'AdaptiveMode',
    'HybridMode',
    'EQProcessor',
    'RealtimeDSPPipeline',
    'ContinuousMode',
]
