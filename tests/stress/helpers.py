# -*- coding: utf-8 -*-

"""
Stress Test Helpers
~~~~~~~~~~~~~~~~~~~

Helper functions for stress and load testing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import time
import psutil
import gc
from typing import Callable, Dict, Any, List
import os


def measure_memory_usage(func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """
    Measure memory usage of a function.

    Args:
        func: Function to measure
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function

    Returns:
        Dictionary with 'before', 'after', 'peak', 'increase' in MB and 'result'
    """
    process = psutil.Process(os.getpid())
    gc.collect()

    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    # Run function
    result = func(*args, **kwargs)

    gc.collect()
    mem_after = process.memory_info().rss / 1024 / 1024  # MB

    return {
        'before_mb': mem_before,
        'after_mb': mem_after,
        'increase_mb': mem_after - mem_before,
        'result': result
    }


def simulate_sustained_load(
    func: Callable,
    duration: int,
    interval: float = 1.0,
    *args,
    **kwargs
) -> Dict[str, Any]:
    """
    Simulate sustained load by calling function repeatedly.

    Args:
        func: Function to call
        duration: Duration in seconds
        interval: Interval between calls
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function

    Returns:
        Dictionary with 'calls', 'errors', 'duration', 'calls_per_second'
    """
    start = time.time()
    calls = 0
    errors = []

    while time.time() - start < duration:
        try:
            func(*args, **kwargs)
            calls += 1
        except Exception as e:
            errors.append(str(e))

        time.sleep(interval)

    actual_duration = time.time() - start

    return {
        'calls': calls,
        'errors': len(errors),
        'error_messages': errors[:5],  # First 5 errors
        'duration_seconds': actual_duration,
        'calls_per_second': calls / actual_duration if actual_duration > 0 else 0
    }


def monitor_resource_usage(func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """
    Monitor CPU and memory usage during function execution.

    Args:
        func: Function to monitor
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function

    Returns:
        Dictionary with CPU%, memory MB, duration seconds, and result
    """
    process = psutil.Process(os.getpid())
    gc.collect()

    # Initial measurements
    cpu_before = psutil.cpu_percent(interval=0.1)
    mem_before = process.memory_info().rss / 1024 / 1024

    # Run function
    start = time.time()
    result = func(*args, **kwargs)
    duration = time.time() - start

    # Final measurements
    gc.collect()
    cpu_after = psutil.cpu_percent(interval=0.1)
    mem_after = process.memory_info().rss / 1024 / 1024

    return {
        'cpu_before': cpu_before,
        'cpu_after': cpu_after,
        'cpu_increase': cpu_after - cpu_before,
        'memory_before_mb': mem_before,
        'memory_after_mb': mem_after,
        'memory_increase_mb': mem_after - mem_before,
        'duration_seconds': duration,
        'result': result
    }


def create_large_test_library(session_maker, n_tracks: int = 1000) -> None:
    """
    Create large test library in database.

    Args:
        session_maker: SQLAlchemy session maker
        n_tracks: Number of tracks to create
    """
    from auralis.library.models import Track, Album, Artist

    session = session_maker()

    # Create artists (10% of tracks)
    n_artists = max(10, n_tracks // 10)
    artists = []
    for i in range(n_artists):
        artist = Artist(name=f"Artist {i}")
        session.add(artist)
        artists.append(artist)

    # Create albums (20% of tracks)
    n_albums = max(20, n_tracks // 5)
    albums = []
    for i in range(n_albums):
        album = Album(
            title=f"Album {i}",
            artist=artists[i % len(artists)]
        )
        session.add(album)
        albums.append(album)

    # Create tracks
    batch_size = 100
    for batch_start in range(0, n_tracks, batch_size):
        for i in range(batch_start, min(batch_start + batch_size, n_tracks)):
            track = Track(
                filepath=f"/test/track_{i:05d}.mp3",
                title=f"Track {i:05d}",
                duration=180.0 + (i % 300),
                album=albums[i % len(albums)],
                artist=artists[i % len(artists)],
                track_number=(i % 20) + 1,
                year=2000 + (i % 25)
            )
            session.add(track)

        session.commit()

    session.close()


def measure_query_performance(query_func: Callable, iterations: int = 100) -> Dict[str, float]:
    """
    Measure query performance over multiple iterations.

    Args:
        query_func: Function that executes a query
        iterations: Number of iterations to run

    Returns:
        Dictionary with min, max, avg, median query times in milliseconds
    """
    times = []

    for _ in range(iterations):
        start = time.time()
        query_func()
        duration = (time.time() - start) * 1000  # Convert to ms
        times.append(duration)

    times.sort()

    return {
        'min_ms': times[0],
        'max_ms': times[-1],
        'avg_ms': sum(times) / len(times),
        'median_ms': times[len(times) // 2],
        'p95_ms': times[int(len(times) * 0.95)],
        'p99_ms': times[int(len(times) * 0.99)],
        'iterations': iterations
    }


def check_memory_leak(
    func: Callable,
    iterations: int = 10,
    threshold_mb: float = 50.0
) -> Dict[str, Any]:
    """
    Check for memory leaks by running function multiple times.

    Args:
        func: Function to check
        iterations: Number of iterations
        threshold_mb: Memory increase threshold in MB

    Returns:
        Dictionary with leak_detected bool and memory measurements
    """
    process = psutil.Process(os.getpid())
    memory_measurements = []

    for i in range(iterations):
        gc.collect()
        mem_before = process.memory_info().rss / 1024 / 1024

        func()

        gc.collect()
        mem_after = process.memory_info().rss / 1024 / 1024

        memory_measurements.append({
            'iteration': i,
            'before_mb': mem_before,
            'after_mb': mem_after,
            'increase_mb': mem_after - mem_before
        })

    # Calculate trend
    total_increase = memory_measurements[-1]['after_mb'] - memory_measurements[0]['before_mb']
    leak_detected = total_increase > threshold_mb

    return {
        'leak_detected': leak_detected,
        'total_increase_mb': total_increase,
        'measurements': memory_measurements,
        'threshold_mb': threshold_mb
    }


def wait_for_condition(
    condition_func: Callable[[], bool],
    timeout: float = 10.0,
    interval: float = 0.1
) -> bool:
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


def simulate_batch_processing(
    process_func: Callable,
    items: List[Any],
    batch_size: int = 10,
    delay: float = 0.1
) -> Dict[str, Any]:
    """
    Simulate batch processing with delays.

    Args:
        process_func: Function to process each item
        items: List of items to process
        batch_size: Items per batch
        delay: Delay between batches

    Returns:
        Dictionary with results and timing
    """
    results = []
    errors = []
    start = time.time()

    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]

        for item in batch:
            try:
                result = process_func(item)
                results.append(result)
            except Exception as e:
                errors.append((item, str(e)))

        if i + batch_size < len(items):
            time.sleep(delay)

    duration = time.time() - start

    return {
        'total_items': len(items),
        'successful': len(results),
        'failed': len(errors),
        'duration_seconds': duration,
        'items_per_second': len(items) / duration if duration > 0 else 0,
        'errors': errors[:10]  # First 10 errors
    }


def get_system_limits() -> Dict[str, Any]:
    """
    Get current system resource limits.

    Returns:
        Dictionary with CPU count, memory, disk space
    """
    return {
        'cpu_count': psutil.cpu_count(),
        'cpu_count_logical': psutil.cpu_count(logical=True),
        'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
        'memory_available_gb': psutil.virtual_memory().available / 1024 / 1024 / 1024,
        'disk_total_gb': psutil.disk_usage('/').total / 1024 / 1024 / 1024,
        'disk_free_gb': psutil.disk_usage('/').free / 1024 / 1024 / 1024,
    }
