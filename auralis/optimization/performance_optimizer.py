# -*- coding: utf-8 -*-

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

import numpy as np
from typing import Dict, Tuple, Optional, Any, Callable
from functools import wraps

# Import from modular components
from .config import PerformanceConfig
from .memory import MemoryPool
from .caching import SmartCache
from .acceleration import SIMDAccelerator, ParallelProcessor
from .profiling import PerformanceProfiler

from ..utils.logging import info, debug


class PerformanceOptimizer:
    """Main performance optimization system"""

    def __init__(self, config: PerformanceConfig = None):
        self.config = config or PerformanceConfig()

        # Initialize components
        self.memory_pool = MemoryPool(self.config.memory_pool_size_mb) if self.config.enable_caching else None
        self.cache = SmartCache(self.config.cache_size_mb, self.config.cache_ttl_seconds) if self.config.enable_caching else None
        self.simd = SIMDAccelerator() if self.config.enable_simd else None
        self.parallel = ParallelProcessor(self.config.max_threads) if self.config.enable_parallel else None
        self.profiler = PerformanceProfiler()

        # Optimization state
        self.optimization_enabled = True
        self.gc_counter = 0

        info(f"Performance optimizer initialized with config: {self.config}")

    def cached_function(self, func_name: str = None):
        """Decorator for caching function results"""
        def decorator(func):
            actual_name = func_name or func.__name__

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.config.enable_caching or not self.cache:
                    return func(*args, **kwargs)

                # Generate cache key
                cache_key = self.cache._generate_key(actual_name, args, kwargs)

                # Try to get from cache
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Execute function and cache result
                result = func(*args, **kwargs)
                self.cache.put(cache_key, result)

                return result

            return wrapper
        return decorator

    def optimized_fft(self, audio: np.ndarray, fft_size: Optional[int] = None) -> np.ndarray:
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

    def get_audio_buffer(self, shape: Tuple[int, ...], dtype=np.float32) -> np.ndarray:
        """Get optimized audio buffer"""
        if self.memory_pool:
            return self.memory_pool.get_buffer(shape, dtype)
        else:
            return np.zeros(shape, dtype=dtype)

    def return_audio_buffer(self, buffer: np.ndarray):
        """Return audio buffer to pool"""
        if self.memory_pool:
            self.memory_pool.return_buffer(buffer)

    def optimize_real_time_processing(self, process_func: Callable) -> Callable:
        """Optimize function for real-time processing"""

        # Add profiling
        timed_func = self.profiler.time_function(process_func.__name__)(process_func)

        # Add caching if beneficial
        if self.config.enable_caching:
            cached_func = self.cached_function(process_func.__name__)(timed_func)
        else:
            cached_func = timed_func

        @wraps(process_func)
        def optimized_wrapper(*args, **kwargs):
            # Periodic garbage collection
            self.gc_counter += 1
            if self.gc_counter >= self.config.garbage_collect_interval:
                self._cleanup()
                self.gc_counter = 0

            return cached_func(*args, **kwargs)

        return optimized_wrapper

    def _cleanup(self):
        """Perform periodic cleanup"""
        if self.cache:
            self.cache.clear_expired()

    def get_optimization_stats(self) -> Dict[str, Any]:
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

    def shutdown(self):
        """Shutdown optimizer and cleanup resources"""
        if self.parallel:
            self.parallel.shutdown()

        info("Performance optimizer shutdown complete")


# Global performance optimizer instance
_global_optimizer = None


def get_performance_optimizer(config: PerformanceConfig = None) -> PerformanceOptimizer:
    """Get global performance optimizer instance"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = PerformanceOptimizer(config)
    return _global_optimizer


def create_performance_optimizer(config: PerformanceConfig = None) -> PerformanceOptimizer:
    """Create new performance optimizer instance"""
    return PerformanceOptimizer(config)


# Convenience decorators
def optimized(func):
    """Decorator to apply all optimizations to a function"""
    optimizer = get_performance_optimizer()
    return optimizer.optimize_real_time_processing(func)


def cached(func):
    """Decorator to add caching to a function"""
    optimizer = get_performance_optimizer()
    return optimizer.cached_function()(func)
