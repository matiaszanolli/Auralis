"""
Regression tests for stale-truthy globals on synchronous init failure (#3898)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

_init_processing_engine / _init_streamlined_cache each assign
globals_dict['processing_engine'] / ['streamlined_cache'] BEFORE the rest of
their setup (worker-task spawn, worker.start()) is known to have succeeded.
If a later step in the same try block raised, the except handler logged and
returned WITHOUT resetting the dict entry — so routers gating on
`globals_dict.get(...) is None` kept returning 200/202 for a component that
was never actually usable (a job would queue forever with no worker running
it; a chunk request would silently take the slow uncached path forever).

This is distinct from #4318 / _watch_critical_worker_task, which handles a
worker that started fine and died LATER (see
test_startup_worker_death_watchdog.py) — these tests cover the *synchronous*
failure path, before the worker was ever considered up.

:license: GPLv3
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import _init_processing_engine, _init_streamlined_cache


class TestProcessingEngineRollsBackOnPartialFailure:
    @pytest.mark.asyncio
    async def test_processing_engine_key_not_left_truthy_after_late_failure(self):
        """ProcessingEngine() construction succeeds and is assigned to
        globals_dict, but a later step in the same try block (here,
        reclaim_stale_temp_entries) raises. The dict must not retain the
        partially-initialized engine."""
        globals_dict: dict = {}

        with patch(
            "config.startup.reclaim_stale_temp_entries",
            side_effect=RuntimeError("disk read failed"),
        ):
            await _init_processing_engine(True, globals_dict)

        assert globals_dict.get('processing_engine') is None
        assert globals_dict.get('_processing_worker_task') is None

    @pytest.mark.asyncio
    async def test_processing_engine_key_not_left_truthy_when_constructor_fails(self):
        """The constructor itself raising (never even assigned) must not
        leave a stale key either -- pop(..., None) must be a safe no-op."""
        globals_dict: dict = {}

        with patch(
            "core.processing_engine.ProcessingEngine",
            side_effect=RuntimeError("out of memory"),
        ):
            await _init_processing_engine(True, globals_dict)

        assert 'processing_engine' not in globals_dict
        assert '_processing_worker_task' not in globals_dict

    @pytest.mark.asyncio
    async def test_healthy_init_leaves_processing_engine_truthy(self):
        """Sanity check: the happy path must still populate the global --
        the fix must not turn every init into a rollback."""
        globals_dict: dict = {}

        from core.processing_engine import ProcessingEngine

        await _init_processing_engine(True, globals_dict)

        engine = globals_dict.get('processing_engine')
        assert isinstance(engine, ProcessingEngine)
        await engine.stop_worker()


class TestStreamlinedCacheRollsBackOnPartialFailure:
    @pytest.mark.asyncio
    async def test_streamlined_cache_key_not_left_truthy_after_worker_start_failure(self):
        """streamlined_cache is assigned (the global singleton), but
        StreamlinedCacheWorker construction/.start() fails. Neither
        streamlined_cache nor streamlined_worker may survive as stale
        truthy entries -- a cache with nothing draining it is not usable
        (see audio_stream_controller.py's degraded-mode fallback, which
        assumes `streamlined_cache` is None exactly in this situation)."""
        globals_dict: dict = {'library_manager': MagicMock()}

        with patch(
            "core.streamlined_worker.StreamlinedCacheWorker",
            side_effect=RuntimeError("worker init failed"),
        ):
            await _init_streamlined_cache(True, globals_dict)

        assert globals_dict.get('streamlined_cache') is None
        assert globals_dict.get('streamlined_worker') is None

    @pytest.mark.asyncio
    async def test_streamlined_cache_skipped_without_library_manager_is_unaffected(self):
        """The pre-existing early-return (no library_manager) must still
        just return -- not touch globals_dict at all."""
        globals_dict: dict = {}

        await _init_streamlined_cache(True, globals_dict)

        assert 'streamlined_cache' not in globals_dict
        assert 'streamlined_worker' not in globals_dict
