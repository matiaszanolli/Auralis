"""Direct unit tests for core.job_progress.ProgressNotifier (#4250 follow-up).

ProgressNotifier was extracted out of ProcessingEngine._notify_progress /
register_progress_callback / unregister_progress_callback so the fan-out
logic is testable without constructing a full ProcessingEngine (processor
pool, worker loop, temp dirs). Behavioral coverage of the same semantics via
ProcessingEngine itself lives in test_ws_job_progress_subscriptions.py and
test_processing_engine.py; this file exercises ProgressNotifier in isolation.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.job_progress import ProgressNotifier  # noqa: E402


def _notifier() -> tuple[ProgressNotifier, dict]:
    jobs: dict = {"job-1": SimpleNamespace(progress=0.0)}
    lock = asyncio.Lock()
    return ProgressNotifier(jobs, lock), jobs


@pytest.mark.asyncio
async def test_register_adds_callback():
    notifier, _ = _notifier()
    cb = AsyncMock()

    await notifier.register("job-1", cb)

    assert notifier.callbacks["job-1"] == [cb]


@pytest.mark.asyncio
async def test_register_same_callback_twice_is_not_a_double_subscription():
    notifier, _ = _notifier()
    cb = AsyncMock()

    await notifier.register("job-1", cb)
    await notifier.register("job-1", cb)

    assert notifier.callbacks["job-1"] == [cb]


@pytest.mark.asyncio
async def test_unregister_specific_callback_leaves_others():
    notifier, _ = _notifier()
    cb_a, cb_b = AsyncMock(), AsyncMock()
    await notifier.register("job-1", cb_a)
    await notifier.register("job-1", cb_b)

    await notifier.unregister("job-1", cb_a)

    assert notifier.callbacks["job-1"] == [cb_b]


@pytest.mark.asyncio
async def test_unregister_without_callback_clears_whole_job():
    notifier, _ = _notifier()
    await notifier.register("job-1", AsyncMock())
    await notifier.register("job-1", AsyncMock())

    await notifier.unregister("job-1")

    assert "job-1" not in notifier.callbacks


@pytest.mark.asyncio
async def test_unregister_already_removed_callback_does_not_raise():
    notifier, _ = _notifier()
    cb = AsyncMock()
    await notifier.register("job-1", cb)
    await notifier.unregister("job-1", cb)

    # Second removal of the same callback must be a no-op, not an error.
    await notifier.unregister("job-1", cb)


@pytest.mark.asyncio
async def test_notify_updates_job_progress_even_with_no_subscribers():
    notifier, jobs = _notifier()

    await notifier.notify("job-1", 42.0, "working")

    assert jobs["job-1"].progress == 42.0


@pytest.mark.asyncio
async def test_notify_delivers_to_every_subscriber():
    notifier, _ = _notifier()
    cb_a, cb_b = AsyncMock(), AsyncMock()
    await notifier.register("job-1", cb_a)
    await notifier.register("job-1", cb_b)

    await notifier.notify("job-1", 10.0, "loading")

    cb_a.assert_awaited_once_with("job-1", 10.0, "loading")
    cb_b.assert_awaited_once_with("job-1", 10.0, "loading")


@pytest.mark.asyncio
async def test_notify_prunes_only_the_raising_callback():
    notifier, _ = _notifier()
    cb_bad = AsyncMock(side_effect=RuntimeError("dead socket"))
    cb_good = AsyncMock()
    await notifier.register("job-1", cb_bad)
    await notifier.register("job-1", cb_good)

    await notifier.notify("job-1", 1.0, "")
    await notifier.notify("job-1", 2.0, "")

    # cb_bad raised once and was pruned; cb_good is still subscribed and was
    # called on both notify() calls.
    assert cb_bad.await_count == 1
    assert cb_good.await_count == 2
    assert notifier.callbacks["job-1"] == [cb_good]


@pytest.mark.asyncio
async def test_notify_for_unknown_job_is_a_silent_no_op():
    notifier, jobs = _notifier()

    await notifier.notify("nonexistent-job", 5.0, "")

    assert "nonexistent-job" not in jobs
