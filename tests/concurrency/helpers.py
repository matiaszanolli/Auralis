# -*- coding: utf-8 -*-

"""
Concurrency Test Helpers
~~~~~~~~~~~~~~~~~~~~~~~~

Helper functions for concurrency testing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, List, Tuple


def run_concurrent(func: Callable, n_threads: int = 10, timeout: float = 30, *args, **kwargs) -> List[Any]:
    """
    Run function concurrently in n_threads threads.

    Args:
        func: Function to run
        n_threads: Number of threads
        timeout: Timeout in seconds
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function

    Returns:
        List of results from each thread

    Raises:
        Exception: If any thread raises an exception
    """
    results = []
    errors = []
    lock = threading.Lock()

    def worker():
        try:
            result = func(*args, **kwargs)
            with lock:
                results.append(result)
        except Exception as e:
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]

    start_time = time.time()
    for t in threads:
        t.start()

    for t in threads:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            raise TimeoutError(f"Concurrent execution timed out after {timeout}s")
        t.join(timeout=remaining)

    if errors:
        raise errors[0]

    return results


def run_concurrent_with_barrier(func: Callable, barrier: threading.Barrier, *args, **kwargs) -> List[Any]:
    """
    Run function concurrently with all threads starting simultaneously.

    Args:
        func: Function to run
        barrier: Barrier to synchronize thread start
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function

    Returns:
        List of results from each thread
    """
    results = []
    errors = []
    lock = threading.Lock()
    n_threads = barrier.parties

    def worker():
        try:
            barrier.wait()  # Wait for all threads to be ready
            result = func(*args, **kwargs)
            with lock:
                results.append(result)
        except Exception as e:
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        raise errors[0]

    return results


def measure_concurrency_speedup(
    sequential_func: Callable,
    parallel_func: Callable,
    *args,
    **kwargs
) -> Tuple[float, float, float]:
    """
    Measure speedup from parallelization.

    Args:
        sequential_func: Sequential implementation
        parallel_func: Parallel implementation
        *args: Arguments to pass to both functions
        **kwargs: Keyword arguments to pass to both functions

    Returns:
        Tuple of (speedup, sequential_time, parallel_time)
    """
    # Sequential
    start = time.time()
    sequential_result = sequential_func(*args, **kwargs)
    sequential_time = time.time() - start

    # Parallel
    start = time.time()
    parallel_result = parallel_func(*args, **kwargs)
    parallel_time = time.time() - start

    speedup = sequential_time / parallel_time if parallel_time > 0 else 0

    return speedup, sequential_time, parallel_time


def detect_race_condition(func: Callable, n_iterations: int = 100, n_threads: int = 10) -> bool:
    """
    Run function many times concurrently to detect race conditions.

    Args:
        func: Function to test for race conditions
        n_iterations: Number of iterations to run
        n_threads: Number of concurrent threads

    Returns:
        True if race condition detected (inconsistent results), False otherwise
    """
    results = set()

    for _ in range(n_iterations):
        try:
            result = run_concurrent(func, n_threads=n_threads, timeout=5)
            # Convert to hashable type
            results.add(tuple(sorted(str(r) for r in result)))
        except Exception:
            # Exceptions can also indicate race conditions
            return True

    # If results vary significantly, there's likely a race condition
    return len(results) > 1


def stress_test(func: Callable, duration: float = 5.0, n_threads: int = 10) -> dict:
    """
    Stress test a function by running it concurrently for a duration.

    Args:
        func: Function to stress test
        duration: Duration to run test (seconds)
        n_threads: Number of concurrent threads

    Returns:
        Dictionary with statistics (calls, errors, duration, calls_per_second)
    """
    stop_event = threading.Event()
    calls = []
    errors = []
    lock = threading.Lock()

    def worker():
        while not stop_event.is_set():
            try:
                start = time.time()
                func()
                elapsed = time.time() - start
                with lock:
                    calls.append(elapsed)
            except Exception as e:
                with lock:
                    errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]

    start_time = time.time()
    for t in threads:
        t.start()

    time.sleep(duration)
    stop_event.set()

    for t in threads:
        t.join(timeout=1)

    actual_duration = time.time() - start_time

    return {
        'calls': len(calls),
        'errors': len(errors),
        'duration': actual_duration,
        'calls_per_second': len(calls) / actual_duration if actual_duration > 0 else 0,
        'avg_call_time': sum(calls) / len(calls) if calls else 0,
        'max_call_time': max(calls) if calls else 0,
    }


def wait_for_condition(condition_func: Callable[[], bool], timeout: float = 10.0, interval: float = 0.1) -> bool:
    """
    Wait for a condition to become true.

    Args:
        condition_func: Function that returns True when condition is met
        timeout: Maximum time to wait
        interval: Check interval

    Returns:
        True if condition met, False if timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False


def run_with_timeout(func: Callable, timeout: float = 10.0, *args, **kwargs) -> Any:
    """
    Run function with timeout using threading.

    Args:
        func: Function to run
        timeout: Timeout in seconds
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function

    Returns:
        Result from function

    Raises:
        TimeoutError: If function doesn't complete in time
    """
    result = [None]
    error = [None]

    def worker():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        raise TimeoutError(f"Function did not complete within {timeout}s")

    if error[0]:
        raise error[0]

    return result[0]
