"""
Performance Optimization Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration settings for performance optimization system.

#5325: trimmed to the settings actually consulted. Every remaining field
constructs or sizes a real component of ``PerformanceOptimizer`` — the
previously-advertised cache/SIMD/memory-pool apply-points never had a caller
and were deleted, along with the fields only they read
(``vectorization_threshold``, ``garbage_collect_interval``, ``enable_simd``)
or nothing read at all (``enable_prefetch``, ``thread_pool_size``) or only a
stats line lied about (``enable_parallel``/``max_threads`` — no parallel
processor exists since #3476).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass


@dataclass
class PerformanceConfig:
    """Performance optimization configuration"""
    enable_caching: bool = True

    # Cache settings
    cache_size_mb: int = 128
    cache_ttl_seconds: int = 300

    # Memory settings
    memory_pool_size_mb: int = 64
