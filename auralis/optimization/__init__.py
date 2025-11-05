# -*- coding: utf-8 -*-

"""
Auralis Optimization Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Performance optimization components for real-time audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .config import PerformanceConfig
from .memory import MemoryPool
from .caching import SmartCache
from .acceleration import SIMDAccelerator, ParallelProcessor
from .profiling import PerformanceProfiler
from .performance_optimizer import (
    PerformanceOptimizer,
    get_performance_optimizer,
    create_performance_optimizer,
    optimized,
    cached
)

__all__ = [
    # Configuration
    'PerformanceConfig',

    # Core components
    'PerformanceOptimizer',
    'MemoryPool',
    'SmartCache',
    'SIMDAccelerator',
    'ParallelProcessor',
    'PerformanceProfiler',

    # Factory functions
    'get_performance_optimizer',
    'create_performance_optimizer',

    # Decorators
    'optimized',
    'cached',
]