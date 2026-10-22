"""
Performance Optimizer
~~~~~~~~~~~~~~~~~~~~

Process-wide performance instrumentation for the mastering pipeline.

What remains is what actually runs: the singleton whose ``PerformanceProfiler``
wraps ``AdaptiveMode.process`` at import time (hybrid_setup.apply_module_optimizations;
profiling only, never memoization — #4524).

The rest of the surface this class used to carry is gone because nothing drove it:
#5325 deleted the apply-points (``cached_function``, ``optimize_real_time_processing``,
``optimized_fft``/``optimized_convolution``, the audio-buffer pool calls and the
``@optimized``/``@cached`` decorators), and #5769 then deleted the ``SmartCache``,
``MemoryPool`` and ``SIMDAccelerator`` objects that were kept constructed only so
``get_optimization_stats()`` could report an empty cache and an idle pool, along
with ``PerformanceConfig``, whose every field sized one of them. If a real
cache or buffer pool is wanted later it should be built against a caller.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any

from ..utils.logging import info
from .profiling import PerformanceProfiler


class PerformanceOptimizer:
    """Owns the process-wide profiler"""

    def __init__(self) -> None:
        self.profiler: PerformanceProfiler = PerformanceProfiler()

        info("Performance optimizer initialized")

    def get_optimization_stats(self) -> dict[str, Any]:
        """Profiling report for the instrumented pipeline methods"""
        return {'performance': self.profiler.get_performance_report()}

    def shutdown(self) -> None:
        """Shutdown optimizer and cleanup resources"""
        info("Performance optimizer shutdown complete")


# Global performance optimizer instance
_global_optimizer: PerformanceOptimizer | None = None
_global_optimizer_lock = threading.Lock()


def get_performance_optimizer() -> PerformanceOptimizer:
    """Get global performance optimizer instance (thread-safe double-check)"""
    global _global_optimizer
    if _global_optimizer is None:
        with _global_optimizer_lock:
            if _global_optimizer is None:
                _global_optimizer = PerformanceOptimizer()
    return _global_optimizer
