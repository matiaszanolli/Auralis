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
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import _shutdown_components, _watch_critical_worker_task


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


# ============================================================================
# #4819: teardown must still run when a watched task dies unexpectedly,
# even though _shutdown_components gates its OWN call on the exact global
# this watchdog just nulled.
# ============================================================================


@pytest.mark.asyncio
async def test_teardown_runs_on_death_even_though_the_global_is_nulled():
    """The whole point of #4819: teardown_key/teardown must be invoked on
    the live object BEFORE it's discarded, so an unexpectedly-dead worker's
    in-flight work still gets cancelled."""
    engine = Mock()
    engine.stop_worker = AsyncMock()
    globals_dict = {'processing_engine': engine}

    async def dying_worker():
        raise RuntimeError("worker crashed")

    task = asyncio.create_task(dying_worker())
    _watch_critical_worker_task(
        task, globals_dict, ('processing_engine',), "ProcessingEngine",
        teardown_key='processing_engine',
        teardown=lambda e: e.stop_worker(),
    )

    with pytest.raises(RuntimeError):
        await task
    # Let the scheduled teardown task actually run.
    pending = globals_dict.get('_watchdog_teardown_tasks', [])
    if pending:
        await asyncio.wait(pending)

    assert globals_dict['processing_engine'] is None
    engine.stop_worker.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_teardown_scheduled_when_task_is_cancelled():
    """Graceful shutdown already calls stop_worker() itself — the watchdog
    must not ALSO schedule a second, redundant teardown for an intentional
    cancellation."""
    engine = Mock()
    engine.stop_worker = AsyncMock()
    globals_dict = {'processing_engine': engine}

    async def long_running_worker():
        await asyncio.sleep(60)

    task = asyncio.create_task(long_running_worker())
    _watch_critical_worker_task(
        task, globals_dict, ('processing_engine',), "ProcessingEngine",
        teardown_key='processing_engine',
        teardown=lambda e: e.stop_worker(),
    )

    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert globals_dict.get('_watchdog_teardown_tasks') is None
    engine.stop_worker.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_teardown_scheduled_without_teardown_key_or_teardown():
    """Backward compatibility: existing callers that don't pass
    teardown_key/teardown (none currently do outside processing_engine/
    streamlined_worker) keep the pre-#4819 behaviour exactly — no
    '_watchdog_teardown_tasks' tracking, no scheduled call."""
    globals_dict = {'processing_engine': object()}

    async def dying_worker():
        raise RuntimeError("boom")

    task = asyncio.create_task(dying_worker())
    _watch_critical_worker_task(task, globals_dict, ('processing_engine',), "ProcessingEngine")

    with pytest.raises(RuntimeError):
        await task

    assert globals_dict['processing_engine'] is None
    assert '_watchdog_teardown_tasks' not in globals_dict


class TestShutdownComponentsAwaitsWatchdogTeardown:
    """Integration: _shutdown_components must give a watchdog-scheduled
    teardown a chance to actually complete as part of the SAME shutdown
    sequence, not just fire-and-forget it (#4819)."""

    def _quiet_externals(self):
        return (
            patch("core.processor_factory.get_processor_factory", MagicMock()),
            patch("services.artwork_downloader.close_artwork_downloader", AsyncMock()),
            patch("analysis.fingerprint_generator.shutdown_fingerprint_executor_bounded", AsyncMock()),
        )

    async def _run(self, globals_dict):
        factory, artwork, fingerprint = self._quiet_externals()
        with factory, artwork, fingerprint:
            await _shutdown_components(globals_dict)

    @pytest.mark.asyncio
    async def test_shutdown_awaits_a_pending_watchdog_teardown_task(self):
        engine_stop_ran = asyncio.Event()

        async def _slow_stop_worker():
            await asyncio.sleep(0.01)
            engine_stop_ran.set()

        # Simulate exactly what the watchdog leaves behind: the global
        # already nulled, and a scheduled-but-not-yet-finished teardown task.
        watchdog_task = asyncio.ensure_future(_slow_stop_worker())
        globals_dict = {
            'processing_engine': None,  # already nulled by the watchdog
            '_watchdog_teardown_tasks': [watchdog_task],
        }

        await self._run(globals_dict)

        assert engine_stop_ran.is_set(), (
            "_shutdown_components must await pending watchdog teardown tasks, "
            "not just skip them because the gated global is already None"
        )
        assert '_watchdog_teardown_tasks' not in globals_dict

    @pytest.mark.asyncio
    async def test_shutdown_proceeds_normally_with_no_pending_watchdog_teardown(self):
        """The common case (no watchdog ever fired) must be completely
        unaffected — no AttributeError/KeyError from the new step."""
        globals_dict = {'processing_engine': None}
        await self._run(globals_dict)  # must not raise
