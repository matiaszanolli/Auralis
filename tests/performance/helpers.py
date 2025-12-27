"""
Performance Test Helpers
~~~~~~~~~~~~~~~~~~~~~~~~

Utility functions for performance testing and benchmarking.
"""

import gc
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, List

import numpy as np
import psutil


def benchmark(func: Callable, iterations: int = 10, warmup: int = 2) -> Dict[str, float]:
    """
    Benchmark function with multiple iterations.

    Args:
        func: Function to benchmark
        iterations: Number of iterations to run
        warmup: Number of warmup iterations (not counted)

    Returns:
        Dictionary with timing statistics (mean, median, min, max, std)
    """
    # Warmup runs
    for _ in range(warmup):
        func()

    # Timed runs
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    times_array = np.array(times)

    return {
        'mean': float(np.mean(times_array)),
        'median': float(np.median(times_array)),
        'min': float(np.min(times_array)),
        'max': float(np.max(times_array)),
        'std': float(np.std(times_array)),
        'iterations': iterations,
    }


def measure_memory(func: Callable) -> tuple[Any, float]:
    """
    Measure memory usage of function.

    Args:
        func: Function to measure

    Returns:
        Tuple of (function_result, memory_increase_mb)
    """
    gc.collect()
    process = psutil.Process()
    before_mb = process.memory_info().rss / 1024 / 1024

    result = func()

    gc.collect()
    after_mb = process.memory_info().rss / 1024 / 1024
    increase_mb = after_mb - before_mb

    return result, increase_mb


def assert_realtime_factor(processing_time: float, audio_duration: float,
                          threshold: float = 20.0, message: str = None):
    """
    Assert real-time factor exceeds threshold.

    Args:
        processing_time: Time to process audio (seconds)
        audio_duration: Duration of audio (seconds)
        threshold: Minimum acceptable real-time factor
        message: Custom assertion message
    """
    rt_factor = audio_duration / processing_time

    if message is None:
        message = (
            f"Real-time factor {rt_factor:.1f}x below threshold {threshold}x "
            f"(processed {audio_duration:.1f}s in {processing_time:.3f}s)"
        )

    assert rt_factor > threshold, message


def assert_speedup(optimized_time: float, baseline_time: float,
                  threshold: float = 1.5, message: str = None):
    """
    Assert optimization achieves speedup threshold.

    Args:
        optimized_time: Time with optimization
        baseline_time: Time without optimization
        threshold: Minimum acceptable speedup factor
        message: Custom assertion message
    """
    speedup = baseline_time / optimized_time

    if message is None:
        message = (
            f"Speedup {speedup:.2f}x below threshold {threshold}x "
            f"(baseline: {baseline_time:.3f}s, optimized: {optimized_time:.3f}s)"
        )

    assert speedup > threshold, message


def assert_latency(measured_latency: float, max_latency: float,
                  unit: str = 'ms', message: str = None):
    """
    Assert latency is below maximum threshold.

    Args:
        measured_latency: Measured latency value
        max_latency: Maximum acceptable latency
        unit: Unit of measurement (ms, s, etc.)
        message: Custom assertion message
    """
    if message is None:
        message = (
            f"Latency {measured_latency:.2f}{unit} exceeds max {max_latency:.2f}{unit}"
        )

    assert measured_latency < max_latency, message


def assert_cache_hit_rate(hits: int, total: int, min_rate: float = 0.8,
                         message: str = None):
    """
    Assert cache hit rate meets minimum threshold.

    Args:
        hits: Number of cache hits
        total: Total number of requests
        min_rate: Minimum acceptable hit rate (0.0 to 1.0)
        message: Custom assertion message
    """
    hit_rate = hits / total if total > 0 else 0.0

    if message is None:
        message = (
            f"Cache hit rate {hit_rate:.1%} below minimum {min_rate:.1%} "
            f"({hits}/{total} hits)"
        )

    assert hit_rate >= min_rate, message


def assert_memory_usage(measured_mb: float, max_mb: float, message: str = None):
    """
    Assert memory usage is below maximum threshold.

    Args:
        measured_mb: Measured memory usage (MB)
        max_mb: Maximum acceptable memory (MB)
        message: Custom assertion message
    """
    if message is None:
        message = f"Memory usage {measured_mb:.1f}MB exceeds max {max_mb:.1f}MB"

    assert measured_mb < max_mb, message


def assert_query_time(query_time: float, max_time_ms: float, message: str = None):
    """
    Assert database query time is below maximum.

    Args:
        query_time: Query execution time (seconds)
        max_time_ms: Maximum acceptable time (milliseconds)
        message: Custom assertion message
    """
    query_time_ms = query_time * 1000

    if message is None:
        message = (
            f"Query time {query_time_ms:.1f}ms exceeds max {max_time_ms:.1f}ms"
        )

    assert query_time_ms < max_time_ms, message


@contextmanager
def memory_tracker():
    """
    Context manager for tracking memory usage.

    Usage:
        with memory_tracker() as tracker:
            # ... code to measure ...
            pass
        print(f"Memory increase: {tracker.increase_mb:.1f}MB")
    """
    class MemoryTracker:
        def __init__(self):
            self.before_mb = 0
            self.after_mb = 0
            self.increase_mb = 0
            self.peak_mb = 0

    tracker = MemoryTracker()
    gc.collect()
    process = psutil.Process()
    tracker.before_mb = process.memory_info().rss / 1024 / 1024

    try:
        yield tracker
    finally:
        gc.collect()
        tracker.after_mb = process.memory_info().rss / 1024 / 1024
        tracker.increase_mb = tracker.after_mb - tracker.before_mb
        # Peak memory during execution (if available)
        try:
            tracker.peak_mb = process.memory_info().peak_wset / 1024 / 1024
        except AttributeError:
            tracker.peak_mb = tracker.after_mb


def calculate_percentiles(values: List[float], percentiles: List[int] = None) -> Dict[str, float]:
    """
    Calculate percentile statistics.

    Args:
        values: List of values
        percentiles: List of percentiles to calculate (default: [50, 90, 95, 99])

    Returns:
        Dictionary mapping percentile to value
    """
    if percentiles is None:
        percentiles = [50, 90, 95, 99]

    values_array = np.array(values)
    results = {}

    for p in percentiles:
        results[f'p{p}'] = float(np.percentile(values_array, p))

    return results


def compare_performance(baseline: Dict[str, float], optimized: Dict[str, float]) -> Dict[str, Any]:
    """
    Compare performance metrics between baseline and optimized versions.

    Args:
        baseline: Baseline performance metrics
        optimized: Optimized performance metrics

    Returns:
        Dictionary with comparison statistics
    """
    comparison = {}

    for key in baseline:
        if key in optimized:
            baseline_val = baseline[key]
            optimized_val = optimized[key]

            if baseline_val > 0:
                speedup = baseline_val / optimized_val
                improvement_pct = ((baseline_val - optimized_val) / baseline_val) * 100

                comparison[key] = {
                    'baseline': baseline_val,
                    'optimized': optimized_val,
                    'speedup': speedup,
                    'improvement_pct': improvement_pct,
                }

    return comparison


def format_benchmark_results(results: Dict[str, float], unit: str = 's') -> str:
    """
    Format benchmark results for display.

    Args:
        results: Benchmark results dictionary
        unit: Time unit (s, ms, us)

    Returns:
        Formatted string
    """
    multiplier = {'s': 1, 'ms': 1000, 'us': 1000000}[unit]

    lines = []
    lines.append(f"Benchmark Results ({results.get('iterations', 'N/A')} iterations):")
    lines.append(f"  Mean:   {results['mean'] * multiplier:.3f}{unit}")
    lines.append(f"  Median: {results['median'] * multiplier:.3f}{unit}")
    lines.append(f"  Min:    {results['min'] * multiplier:.3f}{unit}")
    lines.append(f"  Max:    {results['max'] * multiplier:.3f}{unit}")
    lines.append(f"  Std:    {results['std'] * multiplier:.3f}{unit}")

    return '\n'.join(lines)


def get_memory_usage() -> Dict[str, float]:
    """
    Get current memory usage statistics.

    Returns:
        Dictionary with memory statistics (MB)
    """
    process = psutil.Process()
    mem_info = process.memory_info()

    return {
        'rss_mb': mem_info.rss / 1024 / 1024,  # Resident Set Size
        'vms_mb': mem_info.vms / 1024 / 1024,  # Virtual Memory Size
        'percent': process.memory_percent(),
    }


def detect_memory_leak(func: Callable, iterations: int = 100,
                      tolerance_mb: float = 1.0) -> bool:
    """
    Detect memory leaks by running function multiple times.

    Args:
        func: Function to test
        iterations: Number of iterations
        tolerance_mb: Maximum acceptable memory growth (MB)

    Returns:
        True if memory leak detected, False otherwise
    """
    gc.collect()
    process = psutil.Process()
    initial_mb = process.memory_info().rss / 1024 / 1024

    # Run function multiple times
    for _ in range(iterations):
        func()

    gc.collect()
    final_mb = process.memory_info().rss / 1024 / 1024
    growth_mb = final_mb - initial_mb

    return growth_mb > tolerance_mb
