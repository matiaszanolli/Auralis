"""
Auralis Optimization Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Performance optimization components for real-time audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .acceleration import SIMDAccelerator
from .caching import SmartCache
from .config import PerformanceConfig
from .memory import MemoryPool
from .performance_optimizer import (
    PerformanceOptimizer,
    cached,
    create_performance_optimizer,
    get_performance_optimizer,
    optimized,
)
from .profiling import PerformanceProfiler

__all__ = [
    # Configuration
    'PerformanceConfig',

    # Core components
    'PerformanceOptimizer',
    'MemoryPool',
    'SmartCache',
    'SIMDAccelerator',
    'PerformanceProfiler',

    # Factory functions
    'get_performance_optimizer',
    'create_performance_optimizer',

    # Decorators
    'optimized',
    'cached',
]