"""
Fingerprint worker sizing has one statement of each number (#6641)

build_resource_monitor retyped every ResourceLimits default, max(8, max_workers) was typed twice
(the #6140 bug was those two drifting), and start_resource_monitor logged a literal
"workers: 4-32" while the real ceiling is 2 x cpu_count (48 on a 24-core host).
"""

from unittest.mock import MagicMock, patch

import pytest

from auralis.library.resource_monitor import ResourceLimits
from auralis.services import fingerprint_queue_scaling as scaling


@pytest.mark.parametrize("max_workers", [2, 8, 48])
def test_semaphore_and_monitor_agree_on_processing_permits(max_workers):
    semaphore = scaling.build_processing_semaphore(max_workers)
    monitor = scaling.build_resource_monitor(4, max_workers, MagicMock(), MagicMock())

    assert monitor.limits.max_semaphore == scaling.processing_permits(max_workers)
    assert monitor.limits.max_semaphore == max(scaling.MIN_PROCESSING_PERMITS, max_workers)
    assert semaphore.capacity == monitor.limits.max_semaphore


def test_monitor_thresholds_come_from_resource_limits_defaults():
    limits = scaling.build_resource_monitor(4, 48, MagicMock(), MagicMock()).limits
    defaults = ResourceLimits()

    assert (limits.max_memory_percent, limits.check_interval) == (
        defaults.max_memory_percent, defaults.check_interval,
    )
    assert (limits.scale_up_threshold, limits.scale_down_threshold) == (
        defaults.scale_up_threshold, defaults.scale_down_threshold,
    )


def test_start_log_reports_the_real_worker_range():
    monitor = scaling.build_resource_monitor(12, 48, MagicMock(), MagicMock())
    with patch.object(monitor, "start"), patch.object(scaling, "info") as info:
        scaling.start_resource_monitor(monitor)

    message = info.call_args.args[0]
    assert "workers: 12-48" in message
    assert "4-32" not in message


def test_worker_bounds_follow_the_named_ratios():
    with patch.object(scaling.os, "cpu_count", return_value=24):
        assert scaling.resolve_worker_bounds(None, None) == (12, 48)
    with patch.object(scaling.os, "cpu_count", return_value=2):
        assert scaling.resolve_worker_bounds(None, None) == (scaling.MIN_WORKERS_FLOOR, 4)
