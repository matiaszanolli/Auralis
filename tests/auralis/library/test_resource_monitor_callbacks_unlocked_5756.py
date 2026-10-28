"""The adaptive monitor's callbacks run after its own lock is released (#5756).

_check_and_adjust_resources called on_worker_count_change / on_semaphore_change inside
`with self._lock`. The consumers take their own locks (the queue's stats_lock, the semaphore's), so
the order was monitor lock -> consumer lock by construction; any consumer that ever called back
into the monitor from another thread would have deadlocked. The monitor's lock is an RLock, so the
callback's own thread cannot tell whether it is held: the check below asks from a second thread.
"""

import threading
from types import SimpleNamespace
from unittest.mock import patch

from auralis.library.resource_monitor import AdaptiveResourceMonitor, ResourceLimits


def _lock_free_from_another_thread(monitor: AdaptiveResourceMonitor) -> bool:
    result: list[bool] = []

    def probe() -> None:
        acquired = monitor._lock.acquire(timeout=1.0)
        if acquired:
            monitor._lock.release()
        result.append(acquired)

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    return result[0]


def _tick(monitor: AdaptiveResourceMonitor, ram_percent: float) -> None:
    with patch(
        "auralis.library.resource_monitor.psutil.virtual_memory",
        return_value=SimpleNamespace(percent=ram_percent),
    ):
        monitor._check_and_adjust_resources()


def test_the_worker_count_callback_runs_without_the_monitor_lock_held():
    seen: list[bool] = []
    monitor = AdaptiveResourceMonitor(limits=ResourceLimits(), on_worker_count_change=lambda _n: None)
    monitor.on_worker_count_change = lambda _n: seen.append(_lock_free_from_another_thread(monitor))

    _tick(monitor, ram_percent=20.0)  # low RAM: scale up

    assert seen == [True]


def test_the_semaphore_callback_runs_without_the_monitor_lock_held():
    seen: list[bool] = []
    monitor = AdaptiveResourceMonitor(limits=ResourceLimits(max_semaphore=32))
    monitor.on_semaphore_change = lambda _n: seen.append(_lock_free_from_another_thread(monitor))

    _tick(monitor, ram_percent=90.0)  # high RAM: scale the semaphore down

    assert seen == [True]


def test_callbacks_still_receive_the_new_value_and_stats_still_count_the_change():
    workers: list[int] = []
    monitor = AdaptiveResourceMonitor(limits=ResourceLimits(), on_worker_count_change=workers.append)
    before = monitor.current_worker_count

    _tick(monitor, ram_percent=20.0)

    assert workers == [before + 1]
    assert monitor.get_stats()['scale_ups'] == 1


def test_a_raising_callback_does_not_stop_the_semaphore_callback():
    called: list[int] = []

    def boom(_n: int) -> None:
        raise RuntimeError("consumer failed")

    monitor = AdaptiveResourceMonitor(
        limits=ResourceLimits(max_semaphore=32),
        on_worker_count_change=boom,
        on_semaphore_change=called.append,
    )

    _tick(monitor, ram_percent=90.0)

    assert called == [31]
