"""
Performance Optimizer
~~~~~~~~~~~~~~~~~~~~

Process-wide performance instrumentation for the mastering pipeline.

#5325: the apply-point surface this class used to advertise —
``cached_function``, ``optimize_real_time_processing``,
``optimized_fft``/``optimized_convolution``,
``get_audio_buffer``/``return_audio_buffer`` and the ``@optimized``/``@cached``
decorators — had zero production callers and was deleted. What remains is what
actually runs: the singleton whose ``PerformanceProfiler`` wraps
``AdaptiveMode.process`` at import time (hybrid_setup.apply_module_optimizations;
profiling only, never memoization — #4524), and the ``SmartCache``/``MemoryPool``
instances that ``get_optimization_stats()`` reports on. Neither component has a
production apply-point: the cache is never filled and the pool never dispenses.
They are kept constructed because the stats endpoint reports them, and their
key-faithfulness fixes (#4524, #4992) stay pinned by their own test suites for
whenever a real caller is wired in.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

import threading

from .caching import SmartCache

# Import from modular components
from .config import PerformanceConfig
from .memory import MemoryPool
from .profiling import PerformanceProfiler
from ..utils.logging import info


class PerformanceOptimizer:
    """Main performance optimization system"""

    def __init__(self, config: PerformanceConfig | None = None) -> None:
        self.config: PerformanceConfig = config or PerformanceConfig()

        # Reporting-only components (see module docstring): constructed so
        # get_optimization_stats() can report them, never driven in production.
        self.memory_pool: MemoryPool | None = MemoryPool(self.config.memory_pool_size_mb) if self.config.enable_caching else None
        self.cache: SmartCache | None = SmartCache(self.config.cache_size_mb, self.config.cache_ttl_seconds) if self.config.enable_caching else None
        # #3476: the old `self.parallel = ParallelProcessor(...)` was dead —
        # the only method that class exposed (`parallel_band_processing`)
        # had zero callers, leaving a `ThreadPoolExecutor` allocated and
        # idle for the lifetime of the process. Removed entirely.
        # #5325: `self.simd` (SIMDAccelerator) went the same way — only
        # optimized_fft/optimized_convolution read it, and those had no
        # callers either.
        self.profiler: PerformanceProfiler = PerformanceProfiler()

        info(f"Performance optimizer initialized with config: {self.config}")

    def get_optimization_stats(self) -> dict[str, Any]:
        """Get statistics for the live (profiling) and reporting-only components"""
        stats: dict[str, Any] = {}

        if self.cache:
            stats['cache'] = self.cache.get_stats()

        if self.memory_pool:
            stats['memory_pool'] = self.memory_pool.get_stats()

        stats['performance'] = self.profiler.get_performance_report()

        return stats

    def shutdown(self) -> None:
        """Shutdown optimizer and cleanup resources"""
        info("Performance optimizer shutdown complete")


# Global performance optimizer instance
_global_optimizer: PerformanceOptimizer | None = None
_global_optimizer_lock = threading.Lock()


def get_performance_optimizer(config: PerformanceConfig | None = None) -> PerformanceOptimizer:
    """Get global performance optimizer instance (thread-safe double-check)"""
    global _global_optimizer
    if _global_optimizer is None:
        with _global_optimizer_lock:
            if _global_optimizer is None:
                _global_optimizer = PerformanceOptimizer(config)
    return _global_optimizer
