# -*- coding: utf-8 -*-

"""
Auralis Optimization Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Performance optimization components for real-time audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .performance_optimizer import (
    PerformanceOptimizer,
    PerformanceConfig,
    MemoryPool,
    SmartCache,
    SIMDAccelerator,
    ParallelProcessor,
    get_performance_optimizer,
    create_performance_optimizer,
    optimized,
    cached
)

__all__ = [
    'PerformanceOptimizer',
    'PerformanceConfig',
    'MemoryPool',
    'SmartCache',
    'SIMDAccelerator',
    'ParallelProcessor',
    'get_performance_optimizer',
    'create_performance_optimizer',
    'optimized',
    'cached'
]