"""
Auralis Optimization Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Performance optimization components for real-time audio processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .performance_optimizer import (
    PerformanceOptimizer,
    get_performance_optimizer,
)
from .profiling import PerformanceProfiler

__all__ = [
    # Core components
    'PerformanceOptimizer',
    'PerformanceProfiler',

    # Factory functions
    'get_performance_optimizer',
]