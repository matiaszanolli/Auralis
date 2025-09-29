# -*- coding: utf-8 -*-

"""
Performance Optimizer
~~~~~~~~~~~~~~~~~~~~

Advanced performance optimization for real-time audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

High-performance optimization system with intelligent caching and acceleration
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
import threading
import time
from collections import deque, OrderedDict, defaultdict
from functools import lru_cache, wraps
import hashlib
import pickle
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp

from ..utils.logging import debug, info


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


class MemoryPool:
    """High-performance memory pool for audio buffers"""

    def __init__(self, pool_size_mb: int = 64):
        self.pool_size_bytes = pool_size_mb * 1024 * 1024
        self.available_buffers = {}  # size -> deque of buffers
        self.allocated_buffers = set()
        self.total_allocated = 0
        self.lock = threading.RLock()

        debug(f"Memory pool initialized: {pool_size_mb}MB")

    def get_buffer(self, shape: Tuple[int, ...], dtype=np.float32) -> np.ndarray:
        """Get a buffer from the pool or allocate new one"""
        buffer_size = np.prod(shape) * np.dtype(dtype).itemsize

        with self.lock:
            # Check if we have a suitable buffer
            if shape in self.available_buffers and self.available_buffers[shape]:
                buffer = self.available_buffers[shape].popleft()
                self.allocated_buffers.add(id(buffer))
                return buffer

            # Allocate new buffer if we have space
            if self.total_allocated + buffer_size <= self.pool_size_bytes:
                buffer = np.zeros(shape, dtype=dtype)
                self.allocated_buffers.add(id(buffer))
                self.total_allocated += buffer_size
                return buffer

            # Pool is full, return temporary buffer (will be GC'd)
            return np.zeros(shape, dtype=dtype)

    def return_buffer(self, buffer: np.ndarray):
        """Return buffer to the pool"""
        buffer_id = id(buffer)

        with self.lock:
            if buffer_id in self.allocated_buffers:
                self.allocated_buffers.remove(buffer_id)

                # Clear buffer and add to available pool
                buffer.fill(0)
                shape = buffer.shape

                if shape not in self.available_buffers:
                    self.available_buffers[shape] = deque(maxlen=10)

                if len(self.available_buffers[shape]) < 10:
                    self.available_buffers[shape].append(buffer)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory pool statistics"""
        with self.lock:
            return {
                'total_allocated_mb': self.total_allocated / (1024 * 1024),
                'pool_size_mb': self.pool_size_bytes / (1024 * 1024),
                'utilization': self.total_allocated / self.pool_size_bytes,
                'active_buffers': len(self.allocated_buffers),
                'available_buffer_types': len(self.available_buffers)
            }


class SmartCache:
    """Intelligent caching system with LRU and TTL"""

    def __init__(self, max_size_mb: int = 128, ttl_seconds: int = 300):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()
        self.access_times = {}
        self.sizes = {}
        self.current_size = 0
        self.lock = threading.RLock()

        # Statistics
        self.hits = 0
        self.misses = 0

        debug(f"Smart cache initialized: {max_size_mb}MB, TTL: {ttl_seconds}s")

    def _generate_key(self, func_name: str, args: Tuple, kwargs: Dict) -> str:
        """Generate cache key from function arguments"""
        # Create a stable hash from arguments
        key_data = (func_name, args, sorted(kwargs.items()))
        key_str = str(key_data).encode('utf-8')
        return hashlib.md5(key_str).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        with self.lock:
            current_time = time.time()

            if key in self.cache:
                # Check TTL
                if current_time - self.access_times[key] <= self.ttl_seconds:
                    # Move to end (most recently used)
                    self.cache.move_to_end(key)
                    self.access_times[key] = current_time
                    self.hits += 1
                    return self.cache[key]
                else:
                    # Expired
                    self._remove_item(key)

            self.misses += 1
            return None

    def put(self, key: str, value: Any):
        """Put item in cache"""
        with self.lock:
            # Estimate size
            try:
                size = len(pickle.dumps(value))
            except:
                size = 1024  # Default estimate

            current_time = time.time()

            # Remove if already exists
            if key in self.cache:
                self._remove_item(key)

            # Make space if needed
            while self.current_size + size > self.max_size_bytes and self.cache:
                self._remove_oldest()

            # Add new item
            if size <= self.max_size_bytes:  # Only cache if it fits
                self.cache[key] = value
                self.access_times[key] = current_time
                self.sizes[key] = size
                self.current_size += size

    def _remove_item(self, key: str):
        """Remove item from cache"""
        if key in self.cache:
            del self.cache[key]
            del self.access_times[key]
            self.current_size -= self.sizes[key]
            del self.sizes[key]

    def _remove_oldest(self):
        """Remove least recently used item"""
        if self.cache:
            oldest_key = next(iter(self.cache))
            self._remove_item(oldest_key)

    def clear_expired(self):
        """Remove expired items"""
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, access_time in self.access_times.items()
                if current_time - access_time > self.ttl_seconds
            ]

            for key in expired_keys:
                self._remove_item(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0

            return {
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate,
                'size_mb': self.current_size / (1024 * 1024),
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'utilization': self.current_size / self.max_size_bytes,
                'items': len(self.cache)
            }


class SIMDAccelerator:
    """SIMD acceleration for common audio operations"""

    @staticmethod
    def fast_fft(audio: np.ndarray, fft_size: Optional[int] = None) -> np.ndarray:
        """Optimized FFT computation"""
        if fft_size is None:
            fft_size = len(audio)

        # Use power-of-2 sizes for optimal performance
        if fft_size & (fft_size - 1) != 0:  # Not power of 2
            optimal_size = 1 << (fft_size - 1).bit_length()
            if optimal_size <= fft_size * 1.5:  # Within reasonable range
                fft_size = optimal_size

        # Zero-pad if necessary
        if len(audio) < fft_size:
            padded = np.zeros(fft_size, dtype=audio.dtype)
            padded[:len(audio)] = audio
            audio = padded
        elif len(audio) > fft_size:
            audio = audio[:fft_size]

        # Use optimized FFT
        return np.fft.fft(audio)

    @staticmethod
    def fast_convolution(signal: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """Optimized convolution using FFT"""
        if len(kernel) < 64:  # Use direct convolution for small kernels
            return np.convolve(signal, kernel, mode='same')

        # Use FFT convolution for larger kernels
        conv_size = len(signal) + len(kernel) - 1
        fft_size = 1 << (conv_size - 1).bit_length()  # Next power of 2

        signal_fft = np.fft.fft(signal, fft_size)
        kernel_fft = np.fft.fft(kernel, fft_size)

        result = np.fft.ifft(signal_fft * kernel_fft).real

        # Extract the 'same' portion
        start = len(kernel) // 2
        return result[start:start + len(signal)]

    @staticmethod
    def vectorized_gain_apply(audio: np.ndarray, gains: np.ndarray) -> np.ndarray:
        """Apply gains using vectorized operations"""
        if audio.ndim == 1:
            # Mono audio
            return audio * gains
        else:
            # Multi-channel audio
            if len(gains) == audio.shape[1]:
                # Per-channel gains
                return audio * gains[np.newaxis, :]
            else:
                # Single gain for all channels
                return audio * gains

    @staticmethod
    def fast_rms_calculation(audio: np.ndarray, window_size: int = 1024) -> np.ndarray:
        """Fast RMS calculation using sliding window"""
        if len(audio) <= window_size:
            return np.array([np.sqrt(np.mean(audio ** 2))])

        # Use cumulative sum for efficiency
        audio_squared = audio ** 2
        cumsum = np.cumsum(np.concatenate(([0], audio_squared)))

        # Calculate RMS for each window
        num_windows = len(audio) - window_size + 1
        rms_values = np.zeros(num_windows)

        for i in range(num_windows):
            window_sum = cumsum[i + window_size] - cumsum[i]
            rms_values[i] = np.sqrt(window_sum / window_size)

        return rms_values


class ParallelProcessor:
    """Parallel processing for CPU-intensive operations"""

    def __init__(self, max_threads: int = None):
        self.max_threads = max_threads or min(4, mp.cpu_count())
        self.executor = ThreadPoolExecutor(max_workers=self.max_threads)
        debug(f"Parallel processor initialized with {self.max_threads} threads")

    def parallel_band_processing(self, audio: np.ndarray,
                                band_filters: List[Callable],
                                band_gains: np.ndarray) -> np.ndarray:
        """Process frequency bands in parallel"""
        if len(band_filters) < 2:
            # Not worth parallelizing
            return self._sequential_band_processing(audio, band_filters, band_gains)

        # Submit band processing tasks
        futures = []
        for i, (band_filter, gain) in enumerate(zip(band_filters, band_gains)):
            future = self.executor.submit(self._process_single_band, audio, band_filter, gain)
            futures.append(future)

        # Collect results and sum
        result = np.zeros_like(audio)
        for future in futures:
            band_result = future.result()
            result += band_result

        return result

    def _process_single_band(self, audio: np.ndarray,
                           band_filter: Callable, gain: float) -> np.ndarray:
        """Process a single frequency band"""
        filtered = band_filter(audio)
        return filtered * gain

    def _sequential_band_processing(self, audio: np.ndarray,
                                  band_filters: List[Callable],
                                  band_gains: np.ndarray) -> np.ndarray:
        """Sequential fallback for band processing"""
        result = np.zeros_like(audio)
        for band_filter, gain in zip(band_filters, band_gains):
            filtered = band_filter(audio)
            result += filtered * gain
        return result

    def shutdown(self):
        """Shutdown thread pool"""
        self.executor.shutdown(wait=True)


class PerformanceProfiler:
    """Performance profiling and monitoring"""

    def __init__(self):
        self.timings = defaultdict(list)
        self.counters = defaultdict(int)
        self.memory_usage = deque(maxlen=1000)
        self.lock = threading.RLock()

    def time_function(self, func_name: str):
        """Decorator for timing function execution"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    execution_time = (end_time - start_time) * 1000  # ms

                    with self.lock:
                        self.timings[func_name].append(execution_time)
                        self.counters[f"{func_name}_calls"] += 1

                        # Keep only recent timings
                        if len(self.timings[func_name]) > 1000:
                            self.timings[func_name] = self.timings[func_name][-500:]

            return wrapper
        return decorator

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        with self.lock:
            report = {}

            for func_name, times in self.timings.items():
                if times:
                    report[func_name] = {
                        'avg_time_ms': np.mean(times),
                        'min_time_ms': np.min(times),
                        'max_time_ms': np.max(times),
                        'std_time_ms': np.std(times),
                        'total_calls': len(times),
                        'total_time_ms': np.sum(times)
                    }

            return report


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