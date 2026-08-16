"""
Fingerprint Queue Sizing and Adaptive Scaling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Worker-pool sizing and dynamic-scaling helper for
``FingerprintExtractionQueue`` (#5039): CPU-derived worker bounds, the
processing semaphore, the ``AdaptiveResourceMonitor`` lifecycle, and the
callbacks that apply the monitor's recommendations to the live pool.

Split out of ``fingerprint_queue.py`` as a **pure move** — no signature,
default, log message or exception type changed. The callbacks are a mixin
rather than free functions so ``self.processing_semaphore`` / ``self.stats``
stay reachable and the monitor keeps receiving bound methods of the queue.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import threading
from typing import Any
from collections.abc import Callable

from auralis.services.resizable_semaphore import ResizableSemaphore

from ..library.resource_monitor import AdaptiveResourceMonitor, ResourceLimits
from ..utils.logging import debug, info


def resolve_worker_bounds(
    num_workers: int | None, max_workers: int | None
) -> tuple[int, int]:
    """Auto-detect optimal worker bounds based on CPU cores."""
    cpu_count = os.cpu_count() or 16

    # Set initial worker count if not specified (0.5x ratio - conservative)
    if num_workers is None:
        num_workers = max(4, int(cpu_count * 0.5))

    # Set max worker ceiling if not specified (2.0x ratio - aggressive)
    if max_workers is None:
        max_workers = int(cpu_count * 2.0)

    return num_workers, max_workers


def build_processing_semaphore(max_workers: int) -> ResizableSemaphore:
    """Memory-aware processing semaphore.

    Limits concurrent audio file loading to prevent memory bloat.
    Generous limit: 1 semaphore per worker (allows full parallelism with Rust
    server). Rust server has 64 blocking threads, so allow high concurrency in
    Python. Resizable so the adaptive monitor's recommendation can actually be
    applied at runtime (#4404), not just logged.
    """
    return ResizableSemaphore(
        max(8, max_workers)  # At least 8, up to max_workers
    )


def build_resource_monitor(
    min_workers: int,
    max_workers: int,
    on_worker_count_change: Callable[[int], None],
    on_semaphore_change: Callable[[int], None],
) -> AdaptiveResourceMonitor:
    """Create adaptive monitor with 75% RAM limit and dynamic worker bounds."""
    limits = ResourceLimits(
        max_memory_percent=75.0,
        min_workers=min_workers,  # Start at 0.5x ratio
        max_workers=max_workers,  # Scale up to 2.0x ratio based on RAM
        max_semaphore=max(8, max_workers),  # Allow full parallelism with Rust server
        check_interval=2.0,
        scale_up_threshold=50.0,  # Scale up if RAM < 50%
        scale_down_threshold=80.0  # Scale down if RAM > 80%
    )
    return AdaptiveResourceMonitor(
        limits=limits,
        on_worker_count_change=on_worker_count_change,
        on_semaphore_change=on_semaphore_change
    )


def start_resource_monitor(monitor: AdaptiveResourceMonitor | None) -> None:
    """Start adaptive resource monitor if enabled."""
    if monitor:
        monitor.start()
        info("Adaptive resource monitor started (RAM threshold: 75%, workers: 4-32)")


def stop_resource_monitor(monitor: AdaptiveResourceMonitor | None) -> None:
    """Stop resource monitor if running."""
    if monitor:
        monitor_stats = monitor.get_stats()
        monitor.stop()
        info(
            f"Adaptive resource monitor stopped. "
            f"Stats: {monitor_stats['scale_ups']} scale-ups, "
            f"{monitor_stats['scale_downs']} scale-downs, "
            f"avg RAM: {monitor_stats['avg_memory_percent']:.1f}%, "
            f"max RAM: {monitor_stats['max_memory_percent']:.1f}%"
        )


class AdaptiveScalingMixin:
    """Applies ``AdaptiveResourceMonitor`` recommendations to the live pool.

    The state below is owned and initialised by the composing class; it is
    declared here (annotation only, never assigned) so the moved callbacks keep
    type-checking against it.
    """

    workers: list[threading.Thread]
    current_num_workers: int
    processing_semaphore: ResizableSemaphore
    stats: dict[str, Any]
    stats_lock: threading.RLock

    def _on_worker_count_change(self, new_worker_count: int) -> None:
        """
        Callback invoked by AdaptiveResourceMonitor when worker count should change.

        Args:
            new_worker_count: New recommended worker count

        NOTE (#4596): `current_num_workers` is ADVISORY BOOKKEEPING ONLY — no
        thread is spawned or joined here, so it can drift far above the real
        thread count (`len(self.workers)`, fixed at `start()`). Never use it as
        a completion threshold or to size anything real; use `len(self.workers)`.
        Doing so is what permanently stalled the `on_drained` callback.
        """
        with self.stats_lock:
            old_count = self.current_num_workers
            self.current_num_workers = new_worker_count
            self.stats['scale_events'] += 1

        if len(self.workers) > 0:
            direction = "↑" if new_worker_count > old_count else "↓"
            info(
                f"{direction} Worker scaling callback: {old_count} → {new_worker_count} "
                f"(Note: dynamic scaling requires worker pool restart)"
            )

    def _on_semaphore_change(self, new_semaphore_size: int) -> None:
        """
        Callback invoked by AdaptiveResourceMonitor when semaphore size changes.

        Applies the monitor's recommendation to the processing semaphore
        (#4404). ResizableSemaphore supports safe runtime resizing — growing
        wakes waiting workers, shrinking takes effect as in-flight extractions
        release — so the adaptive concurrency signal is no longer a no-op.

        Args:
            new_semaphore_size: Recommended concurrent audio processing limit from monitor
        """
        old_size = self.processing_semaphore.capacity
        if new_semaphore_size == old_size:
            return
        self.processing_semaphore.resize(new_semaphore_size)
        direction = "↑" if new_semaphore_size > old_size else "↓"
        debug(
            f"{direction} Adaptive semaphore resize: {old_size} → {new_semaphore_size} "
            f"concurrent audio processors"
        )
