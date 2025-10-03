# -*- coding: utf-8 -*-

"""
Performance Optimization Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular performance optimization system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .config import PerformanceConfig
from .memory_pool import MemoryPool
from .smart_cache import SmartCache
from .simd_accelerator import SIMDAccelerator
from .parallel_processor import ParallelProcessor
from .profiler import PerformanceProfiler
from .optimizer import PerformanceOptimizer

__all__ = [
    'PerformanceConfig',
    'MemoryPool',
    'SmartCache',
    'SIMDAccelerator',
    'ParallelProcessor',
    'PerformanceProfiler',
    'PerformanceOptimizer',
]
