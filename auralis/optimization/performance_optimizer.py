"""
Performance Optimizer
~~~~~~~~~~~~~~~~~~~~

Advanced performance optimization for real-time audio processing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Main orchestrator for performance optimization system. Coordinates:
- Memory pool management
- Intelligent caching
- SIMD acceleration
- Parallel processing
- Performance profiling
"""

from functools import wraps
from typing import Any
from collections.abc import Callable

import numpy as np

from ..utils.logging import info
from .acceleration import ParallelProcessor, SIMDAccelerator
from .caching import SmartCache

# Import from modular components
from .config import PerformanceConfig
from .memory import MemoryPool
from .profiling import PerformanceProfiler


class PerformanceOptimizer:
    """Main performance optimization system"""

    def __init__(self, config: PerformanceConfig | None = None) -> None:
        self.config: PerformanceConfig = config or PerformanceConfig()

        # Initialize components
        self.memory_pool: MemoryPool | None = MemoryPool(self.config.memory_pool_size_mb) if self.config.enable_caching else None
        self.cache: SmartCache | None = SmartCache(self.config.cache_size_mb, self.config.cache_ttl_seconds) if self.config.enable_caching else None
        self.simd: SIMDAccelerator | None = SIMDAccelerator() if self.config.enable_simd else None
        self.parallel: ParallelProcessor | None = ParallelProcessor(self.config.max_threads) if self.config.enable_parallel else None
        self.profiler: PerformanceProfiler = PerformanceProfiler()

        # Optimization state
        self.optimization_enabled: bool = True
        self.gc_counter: int = 0

        info(f"Performance optimizer initialized with config: {self.config}")

    def cached_function(self, func_name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator for caching function results"""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            actual_name: str = func_name or func.__name__

            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if not self.config.enable_caching or not self.cache:
                    return func(*args, **kwargs)

                # Generate cache key
                cache_key: str = self.cache._generate_key(actual_name, args, kwargs)

                # Try to get from cache
                cached_result: Any = self.cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Execute function and cache result
                result: Any = func(*args, **kwargs)
                self.cache.put(cache_key, result)

                return result

            return wrapper
        return decorator

    def optimized_fft(self, audio: np.ndarray, fft_size: int | None = None) -> np.ndarray:
        """Optimized FFT with caching and SIMD"""
        if self.simd and len(audio) >= self.config.vectorization_threshold:
            return self.simd.fast_fft(audio, fft_size)
        else:
            return np.fft.fft(audio, fft_size)

    def optimized_convolution(self, signal: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """Optimized convolution"""
        if self.simd:
            return self.simd.fast_convolution(signal, kernel)
        else:
            return np.convolve(signal, kernel, mode='same')

    def get_audio_buffer(self, shape: tuple[int, ...], dtype: Any = np.float32) -> np.ndarray:
        """Get optimized audio buffer"""
        if self.memory_pool:
            return self.memory_pool.get_buffer(shape, dtype)
        else:
            return np.zeros(shape, dtype=dtype)

    def return_audio_buffer(self, buffer: np.ndarray) -> None:
        """Return audio buffer to pool"""
        if self.memory_pool:
            self.memory_pool.return_buffer(buffer)

    def optimize_real_time_processing(self, process_func: Callable[..., Any]) -> Callable[..., Any]:
        """Optimize function for real-time processing"""

        # Add profiling
        timed_func: Callable[..., Any] = self.profiler.time_function(process_func.__name__)(process_func)

        # Add caching if beneficial
        if self.config.enable_caching:
            cached_func: Callable[..., Any] = self.cached_function(process_func.__name__)(timed_func)
        else:
            cached_func = timed_func

        @wraps(process_func)
        def optimized_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Periodic garbage collection
            self.gc_counter += 1
            if self.gc_counter >= self.config.garbage_collect_interval:
                self._cleanup()
                self.gc_counter = 0

            return cached_func(*args, **kwargs)

        return optimized_wrapper

    def _cleanup(self) -> None:
        """Perform periodic cleanup"""
        if self.cache:
            self.cache.clear_expired()

    def get_optimization_stats(self) -> dict[str, Any]:
        """Get comprehensive optimization statistics"""
        stats = {
            'config': {
                'caching_enabled': self.config.enable_caching,
                'parallel_enabled': self.config.enable_parallel,
                'simd_enabled': self.config.enable_simd,
                'max_threads': self.config.max_threads
            }
        }

        if self.cache:
            stats['cache'] = self.cache.get_stats()

        if self.memory_pool:
            stats['memory_pool'] = self.memory_pool.get_stats()

        stats['performance'] = self.profiler.get_performance_report()

        return stats

    def shutdown(self) -> None:
        """Shutdown optimizer and cleanup resources"""
        if self.parallel:
            self.parallel.shutdown()

        info("Performance optimizer shutdown complete")


# Global performance optimizer instance
_global_optimizer: PerformanceOptimizer | None = None


def get_performance_optimizer(config: PerformanceConfig | None = None) -> PerformanceOptimizer:
    """Get global performance optimizer instance"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = PerformanceOptimizer(config)
    return _global_optimizer


def create_performance_optimizer(config: PerformanceConfig | None = None) -> PerformanceOptimizer:
    """Create new performance optimizer instance"""
    return PerformanceOptimizer(config)


# Convenience decorators
def optimized(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to apply all optimizations to a function"""
    optimizer: PerformanceOptimizer = get_performance_optimizer()
    return optimizer.optimize_real_time_processing(func)


def cached(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to add caching to a function"""
    optimizer: PerformanceOptimizer = get_performance_optimizer()
    return optimizer.cached_function()(func)
