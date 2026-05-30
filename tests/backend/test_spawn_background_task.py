"""
Regression tests for spawn_background_task fire-and-forget logging (#3851)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Long-lived background tasks must not die silently. `spawn_background_task`
(the canonical helper since #3512) attaches `log_task_exception` so any
exception escaping a fire-and-forget coroutine is logged at ERROR rather than
vanishing into asyncio's never-retrieved bucket. #3851 migrated the last
holdout (routers/enhancement.py) to this helper.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from helpers import log_task_exception, spawn_background_task


class TestSpawnBackgroundTask:
    """spawn_background_task names the task and logs escaped exceptions."""

    @pytest.mark.asyncio
    async def test_task_runs_and_is_named(self):
        ran = asyncio.Event()

        async def _work():
            ran.set()

        task = spawn_background_task(_work(), name="unit.work")
        assert task.get_name() == "unit.work"
        await task
        assert ran.is_set()

    @pytest.mark.asyncio
    async def test_exception_is_logged_not_silent(self, caplog):
        """An exception escaping the coroutine must surface at ERROR (#3851)."""

        async def _boom():
            raise ValueError("kaboom")

        with caplog.at_level(logging.ERROR, logger="helpers"):
            task = spawn_background_task(_boom(), name="unit.boom")
            # Let the task run and its done-callback fire.
            with pytest.raises(ValueError):
                await task
            # Yield so add_done_callback executes.
            await asyncio.sleep(0)

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert errors, "A raising fire-and-forget task must log an ERROR"
        assert any("unit.boom" in r.getMessage() for r in errors)

    @pytest.mark.asyncio
    async def test_successful_task_logs_nothing(self, caplog):
        async def _ok():
            return 42

        with caplog.at_level(logging.ERROR, logger="helpers"):
            task = spawn_background_task(_ok(), name="unit.ok")
            await task
            await asyncio.sleep(0)

        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


class TestLogTaskException:
    """log_task_exception is robust to cancelled / clean / failed tasks."""

    @pytest.mark.asyncio
    async def test_cancelled_task_is_ignored(self, caplog):
        async def _sleep_forever():
            await asyncio.sleep(3600)

        task = asyncio.create_task(_sleep_forever())
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        with caplog.at_level(logging.ERROR, logger="helpers"):
            log_task_exception(task)  # must not raise, must not log

        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    @pytest.mark.asyncio
    async def test_failed_task_logs_error_with_exc_info(self, caplog):
        async def _boom():
            raise RuntimeError("nope")

        task = asyncio.create_task(_boom(), name="manual.boom")
        with pytest.raises(RuntimeError):
            await task

        with caplog.at_level(logging.ERROR, logger="helpers"):
            log_task_exception(task)

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert errors
        assert any(r.exc_info for r in errors), "Should attach exc_info for traceback"
