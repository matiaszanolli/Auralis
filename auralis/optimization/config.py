"""
Performance Optimization Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration settings for performance optimization system.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import multiprocessing as mp
from dataclasses import dataclass


@dataclass
class PerformanceConfig:
    """Performance optimization configuration"""
    enable_caching: bool = True
    enable_parallel: bool = True
    enable_simd: bool = True
    enable_prefetch: bool = True

    # Cache settings
    cache_size_mb: int = 128
    cache_ttl_seconds: int = 300

    # Threading settings
    max_threads: int = min(4, mp.cpu_count())
    thread_pool_size: int = 2

    # SIMD settings
    vectorization_threshold: int = 1024

    # Memory settings
    memory_pool_size_mb: int = 64
    garbage_collect_interval: int = 100
