"""
Regression tests for the critical-worker death watchdog (#4318).

CONTEXT: ProcessingEngine.start_worker() and StreamlinedCacheWorker's
_worker_loop() are long-running background tasks started once at startup.
#3512 added a done-callback that only LOGS a silently-failing task —
globals_dict['processing_engine'] / ['streamlined_cache'] /
['streamlined_worker'] stayed truthy forever even after the underlying
task died, so routers gating on them kept accepting requests a dead
worker would never service.

_watch_critical_worker_task() closes that gap: it nulls the relevant
globals_dict entries when the watched task finishes for any reason OTHER
than intentional cancellation (the expected signal from stop_worker()/
worker.stop() during graceful shutdown).

:license: GPLv3
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import _watch_critical_worker_task


@pytest.mark.asyncio
async def test_nulls_globals_when_task_raises_exception():
    """A worker task that dies with an uncaught exception must null its
    globals_dict entries — this is the exact scenario #4318 describes."""
    globals_dict = {'processing_engine': object()}

    async def dying_worker():
        raise RuntimeError("worker crashed")

    task = asyncio.create_task(dying_worker())
    _watch_critical_worker_task(task, globals_dict, ('processing_engine',), "ProcessingEngine")

    with pytest.raises(RuntimeError):
        await task

    assert globals_dict['processing_engine'] is None


@pytest.mark.asyncio
async def test_nulls_globals_when_task_completes_without_being_stopped():
    """A worker task that exits cleanly (returns) without an explicit
    stop() call is still an unexpected death — its loop is meant to run
    forever until cancelled, so a clean return means it silently gave up."""
    globals_dict = {'streamlined_cache': object(), 'streamlined_worker': object()}

    async def returning_worker():
        return None

    task = asyncio.create_task(returning_worker())
    _watch_critical_worker_task(
        task, globals_dict, ('streamlined_cache', 'streamlined_worker'), "StreamlinedCacheWorker"
    )

    await task

    assert globals_dict['streamlined_cache'] is None
    assert globals_dict['streamlined_worker'] is None


@pytest.mark.asyncio
async def test_does_not_null_globals_on_intentional_cancellation():
    """Cancellation (the stop_worker()/worker.stop() graceful-shutdown path)
    must NOT be treated as a failure — the global should stay untouched."""
    marker = object()
    globals_dict = {'processing_engine': marker}

    async def long_running_worker():
        await asyncio.sleep(60)

    task = asyncio.create_task(long_running_worker())
    _watch_critical_worker_task(task, globals_dict, ('processing_engine',), "ProcessingEngine")

    # Let the task actually start running before cancelling it.
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert globals_dict['processing_engine'] is marker


@pytest.mark.asyncio
async def test_nulls_only_the_specified_keys():
    """Unrelated globals_dict entries must be left alone."""
    globals_dict = {'processing_engine': object(), 'library_manager': object()}

    async def dying_worker():
        raise RuntimeError("boom")

    task = asyncio.create_task(dying_worker())
    _watch_critical_worker_task(task, globals_dict, ('processing_engine',), "ProcessingEngine")

    with pytest.raises(RuntimeError):
        await task

    assert globals_dict['processing_engine'] is None
    assert globals_dict['library_manager'] is not None
