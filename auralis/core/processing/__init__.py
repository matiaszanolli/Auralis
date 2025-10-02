# -*- coding: utf-8 -*-

"""
Audio Processing Modes
~~~~~~~~~~~~~~~~~~~~~~

Modular processing engine with multiple mastering modes

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .hybrid_processor import HybridProcessor
from .content_analyzer import ContentAnalyzer
from .target_generator import AdaptiveTargetGenerator
from .adaptive_mode import AdaptiveMode
from .reference_mode import ReferenceMode
from .hybrid_mode import HybridMode

# Factory functions
def create_hybrid_processor(config=None, **kwargs):
    """Create hybrid processor with optional configuration"""
    from ..unified_config import UnifiedConfig
    if config is None:
        config = UnifiedConfig()
    return HybridProcessor(config, **kwargs)

__all__ = [
    'HybridProcessor',
    'ContentAnalyzer',
    'AdaptiveTargetGenerator',
    'AdaptiveMode',
    'ReferenceMode',
    'HybridMode',
    'create_hybrid_processor',
]
