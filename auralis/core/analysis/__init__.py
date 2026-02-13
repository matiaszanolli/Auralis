"""
Core Analysis Components
~~~~~~~~~~~~~~~~~~~~~~~~

Content analysis and adaptive target generation

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .content_analyzer import ContentAnalyzer, create_content_analyzer
from .target_generator import AdaptiveTargetGenerator, create_adaptive_target_generator

__all__ = [
    'ContentAnalyzer',
    'create_content_analyzer',
    'AdaptiveTargetGenerator',
    'create_adaptive_target_generator',
]
