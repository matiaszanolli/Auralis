"""
Adaptive Resource Monitor for Fingerprinting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Monitors system RAM usage and dynamically adjusts worker parallelism
to maximize throughput while staying within safe memory limits.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

import psutil

from ..utils.logging import debug, error, info


@dataclass
class ResourceLimits:
    """Resource limits for adaptive scaling"""
    max_memory_percent: float = 75.0  # Max 75% RAM usage
    min_workers: int = 4              # Minimum workers (for safety)
    max_workers: int = 32             # Maximum workers (hard limit)
    max_semaphore: int = 16           # Maximum concurrent audio processors
    check_interval: float = 2.0       # Check RAM every 2 seconds
    scale_up_threshold: float = 50.0  # Start workers if RAM < 50%
    scale_down_threshold: float = 80.0  # Reduce workers if RAM > 80%


class AdaptiveResourceMonitor:
    """
    Monitors system resources and dynamically adjusts fingerprinting parallelism.

    Ensures the fingerprinting system uses maximum available resources without
    exceeding safe memory thresholds.
    """

    def __init__(
        self,
        limits: ResourceLimits | None = None,
        on_worker_count_change: Callable[[int], None] | None = None,
        on_semaphore_change: Callable[[int], None] | None = None,
    ):
        """
        Initialize resource monitor.

        Args:
            limits: Resource limits (uses defaults if None)
            on_worker_count_change: Callback when optimal worker count changes
            on_semaphore_change: Callback when semaphore size changes
        """
        self.limits = limits or ResourceLimits()
        self.on_worker_count_change = on_worker_count_change
        self.on_semaphore_change = on_semaphore_change

        self.current_worker_count = self.limits.min_workers
        self.current_semaphore_size = 4  # Start conservative

        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.RLock()

        self._stats = {
            'samples_collected': 0,
            'avg_memory_percent': 0.0,
            'max_memory_percent': 0.0,
            'scale_ups': 0,
            'scale_downs': 0,
        }

    def start(self) -> None:
        """Start monitoring resources in background thread"""
        if self._monitor_thread is not None:
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self._monitor_thread.start()
        info("Adaptive resource monitor started")

    def stop(self) -> None:
        """Stop monitoring resources"""
        if self._monitor_thread is None:
            return

        self._stop_event.set()
        self._monitor_thread.join(timeout=5.0)
        self._monitor_thread = None
        info("Adaptive resource monitor stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop - runs in background thread"""
        try:
            while not self._stop_event.is_set():
                try:
                    self._check_and_adjust_resources()
                    self._stop_event.wait(self.limits.check_interval)
                except Exception as e:
                    error(f"Error in resource monitor: {e}")
                    self._stop_event.wait(1.0)
        except Exception as e:
            error(f"Resource monitor crashed: {e}")

    def _check_and_adjust_resources(self) -> None:
        """Check RAM usage and adjust worker count if needed"""
        memory_percent = psutil.virtual_memory().percent

        with self._lock:
            # Update statistics
            self._stats['samples_collected'] += 1
            old_avg = self._stats['avg_memory_percent']
            self._stats['avg_memory_percent'] = (
                (old_avg * (self._stats['samples_collected'] - 1) + memory_percent) /
                self._stats['samples_collected']
            )
            self._stats['max_memory_percent'] = max(
                self._stats['max_memory_percent'],
                memory_percent
            )

            # Determine optimal worker count based on memory
            if memory_percent < self.limits.scale_up_threshold:
                # Memory is low, we can use more workers
                optimal_workers = min(
                    self.current_worker_count + 1,
                    self.limits.max_workers
                )
            elif memory_percent > self.limits.scale_down_threshold:
                # Memory is high, reduce workers
                optimal_workers = max(
                    self.current_worker_count - 1,
                    self.limits.min_workers
                )
            else:
                # Memory is in safe zone, keep current
                optimal_workers = self.current_worker_count

            # Apply worker count change if needed
            if optimal_workers != self.current_worker_count:
                old_count = self.current_worker_count
                self.current_worker_count = optimal_workers
                self._stats['scale_ups' if optimal_workers > old_count else 'scale_downs'] += 1

                if self.on_worker_count_change:
                    try:
                        self.on_worker_count_change(optimal_workers)
                    except Exception as e:
                        error(f"Error in worker count callback: {e}")

                direction = "↑" if optimal_workers > old_count else "↓"
                info(
                    f"{direction} Adaptive scaling: {old_count} → {optimal_workers} workers "
                    f"(RAM: {memory_percent:.1f}%)"
                )

            # Also adjust processing semaphore (max concurrent audio loads)
            if memory_percent < self.limits.scale_up_threshold:
                optimal_semaphore = min(
                    self.current_semaphore_size + 1,
                    self.limits.max_semaphore
                )
            elif memory_percent > self.limits.scale_down_threshold:
                optimal_semaphore = max(
                    self.current_semaphore_size - 1,
                    2  # Keep at least 2 concurrent
                )
            else:
                optimal_semaphore = self.current_semaphore_size

            if optimal_semaphore != self.current_semaphore_size:
                old_size = self.current_semaphore_size
                self.current_semaphore_size = optimal_semaphore

                if self.on_semaphore_change:
                    try:
                        self.on_semaphore_change(optimal_semaphore)
                    except Exception as e:
                        error(f"Error in semaphore callback: {e}")

                direction = "↑" if optimal_semaphore > old_size else "↓"
                debug(
                    f"{direction} Adaptive semaphore: {old_size} → {optimal_semaphore} "
                    f"(RAM: {memory_percent:.1f}%)"
                )

    def get_current_worker_count(self) -> int:
        """Get current recommended worker count"""
        with self._lock:
            return self.current_worker_count

    def get_current_semaphore_size(self) -> int:
        """Get current recommended semaphore size"""
        with self._lock:
            return self.current_semaphore_size

    def get_stats(self) -> dict[str, Any]:
        """Get monitoring statistics"""
        with self._lock:
            return self._stats.copy()
