"""The adaptive monitor starts from the semaphore size the queue really built (#6140).

It used to assume 4 while the queue's semaphore started at ``max(8, max_workers)``,
so the first low-RAM tick resized a 32-slot semaphore down to 5, and in the
50-80% band nothing was ever resized.
"""

from types import SimpleNamespace
from unittest.mock import patch

from auralis.library.resource_monitor import AdaptiveResourceMonitor, ResourceLimits


def _monitor(max_semaphore=32):
    changes = []
    monitor = AdaptiveResourceMonitor(
        limits=ResourceLimits(max_semaphore=max_semaphore),
        on_semaphore_change=changes.append,
    )
    return monitor, changes


def _tick(monitor, ram_percent):
    with patch(
        "auralis.library.resource_monitor.psutil.virtual_memory",
        return_value=SimpleNamespace(percent=ram_percent),
    ):
        monitor._check_and_adjust_resources()


def test_starts_at_the_configured_capacity():
    monitor, _ = _monitor(max_semaphore=32)
    assert monitor.current_semaphore_size == 32


def test_idle_first_tick_does_not_shrink_the_semaphore():
    monitor, changes = _monitor(max_semaphore=32)

    _tick(monitor, ram_percent=20.0)

    assert changes == []
    assert monitor.current_semaphore_size == 32


def test_memory_squeeze_engages_from_the_first_tick():
    monitor, changes = _monitor(max_semaphore=32)

    _tick(monitor, ram_percent=90.0)

    assert changes == [31]
