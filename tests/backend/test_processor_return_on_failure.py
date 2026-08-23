"""
Every process_job exit path reclaims the processor it owns (#4567)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`ProcessorPool.get_or_create()` POPS the instance out of the cache so no
concurrent job shares it (#3201); whoever takes it must give it back.
`process_job` honoured that on three of its four exit paths — the catch-all
`except Exception` neither returned the processor nor closed it, so every failed
job dropped a warm instance. Its `fingerprint_analyzer` owns a 5-thread executor
that the threading module keeps reachable, so GC never reclaims it (#3746): N
failing jobs accumulated 5N idle threads, and the next job with the same config
paid the full 200-500 ms `HybridProcessor.__init__` again.

Cleanup is hoisted into `finally`: reusable processors return to the cache,
while timed-out or cancelled processors are closed because an abandoned worker
thread may still be mutating them (#4727/#4759).

Also covers #4370: `return_to_cache`'s FIFO eviction dropped the evicted
processor without closing it, which would have leaked a *different* instance
right back.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import inspect
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from core.job_lifecycle import process_job as _job_lifecycle_process_job
from core.processing_engine import ProcessingEngine, ProcessingJob, ProcessingStatus
from core.processor_pool import ProcessorPool

pytestmark = pytest.mark.asyncio


def _make_engine() -> ProcessingEngine:
    return ProcessingEngine(max_concurrent_jobs=2)


def _make_job() -> ProcessingJob:
    job = ProcessingJob.__new__(ProcessingJob)
    job.job_id = "job-1"
    job.input_path = "/fake/in.flac"
    job.output_path = "/fake/out.wav"
    job.mode = "adaptive"
    job.settings = {"output_format": "wav", "bit_depth": 16}
    job.status = ProcessingStatus.QUEUED
    job.started_at = None
    job.completed_at = None
    job.result_data = None
    job.error_message = None
    return job


def _make_config() -> MagicMock:
    """A config stub whose cache_key is stable.

    ProcessorPool.cache_key() hashes `repr()` of several adaptive attributes, and
    a bare MagicMock's repr embeds its object id — so two stub configs that are
    semantically identical would hash differently and every job would get its
    own cache slot. Pin the hashed attributes to plain values.
    """
    config = MagicMock()
    config.internal_sample_rate = 44100
    config.mastering_profile = ""
    config.adaptive.mode = "adaptive"
    for attr in ("eq_gains", "compressor", "target_lufs", "gain", "genre_override"):
        setattr(config.adaptive, attr, None)
    return config


def _prepared(engine, processor, config=None):
    """Patch _prepare_job to hand back a known processor + config."""
    audio = np.zeros(1024, dtype=np.float32)
    return patch.object(
        engine,
        "_prepare_job",
        AsyncMock(return_value=(audio, 44100, config or _make_config(), processor)),
    )


class TestProcessorIsAlwaysReclaimed:
    async def test_generic_exception_returns_the_processor(self):
        """The regression: a ValueError used to drop the processor entirely."""
        engine = _make_engine()
        job = _make_job()
        processor = MagicMock()

        with _prepared(engine, processor), patch.object(
            engine, "_execute_job", AsyncMock(side_effect=ValueError("bad audio"))
        ):
            await engine.process_job(job)

        assert job.status == ProcessingStatus.FAILED
        assert processor in engine._pool.processors.values()

    async def test_timeout_path_discards_poisoned_processor(self):
        engine = _make_engine()
        job = _make_job()
        processor = MagicMock()

        with _prepared(engine, processor), patch.object(
            engine, "_execute_job", AsyncMock(side_effect=TimeoutError())
        ):
            await engine.process_job(job)

        assert job.status == ProcessingStatus.FAILED
        assert processor not in engine._pool.processors.values()
        processor.close.assert_called_once()

    async def test_cancelled_path_discards_possibly_active_processor(self):
        engine = _make_engine()
        job = _make_job()
        job.status = ProcessingStatus.PROCESSING
        processor = MagicMock()

        with _prepared(engine, processor), patch.object(
            engine, "_execute_job", AsyncMock(side_effect=asyncio.CancelledError())
        ):
            with pytest.raises(asyncio.CancelledError):
                await engine.process_job(job)

        assert job.status == ProcessingStatus.CANCELLED
        assert processor not in engine._pool.processors.values()
        processor.close.assert_called_once()

    async def test_success_path_still_returns_exactly_once(self):
        engine = _make_engine()
        job = _make_job()
        processor = MagicMock()

        with _prepared(engine, processor), patch.object(
            engine, "_execute_job", AsyncMock(return_value=np.zeros(8, dtype=np.float32))
        ), patch.object(engine, "_finalize_job", MagicMock()):
            await engine.process_job(job)

        assert list(engine._pool.processors.values()).count(processor) == 1

    async def test_failure_before_acquisition_is_a_no_op(self):
        """_prepare_job raising means there is no processor to return."""
        engine = _make_engine()
        job = _make_job()

        with patch.object(
            engine, "_prepare_job", AsyncMock(side_effect=RuntimeError("no file"))
        ):
            await engine.process_job(job)

        assert job.status == ProcessingStatus.FAILED
        assert engine._pool.processors == {}

    async def test_repeated_failures_do_not_accumulate_processors(self):
        """20 failing jobs must not leave 20 orphaned instances."""
        engine = _make_engine()
        processor = MagicMock()
        config = _make_config()

        for i in range(20):
            job = _make_job()
            job.job_id = f"job-{i}"
            with _prepared(engine, processor, config), patch.object(
                engine, "_execute_job", AsyncMock(side_effect=ValueError("boom"))
            ):
                await engine.process_job(job)

        # Same config every time → exactly one cache entry, not 20 orphans.
        assert len(engine._pool.processors) == 1

    async def test_a_failing_return_falls_back_to_close(self):
        """Cleanup must never leave the processor un-reclaimed."""
        engine = _make_engine()
        job = _make_job()
        processor = MagicMock()

        with _prepared(engine, processor), patch.object(
            engine, "_execute_job", AsyncMock(side_effect=ValueError("boom"))
        ), patch.object(
            engine, "_return_processor", AsyncMock(side_effect=RuntimeError("pool down"))
        ):
            await engine.process_job(job)

        processor.close.assert_called_once()
        # And the original failure is still what the job reports.
        assert job.status == ProcessingStatus.FAILED

    async def test_cancellation_during_pool_return_finishes_cleanup(self):
        engine = _make_engine()
        job = _make_job()
        processor = MagicMock()
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        cleanup_finished = asyncio.Event()

        async def _contended_return(*_args):
            cleanup_started.set()
            await release_cleanup.wait()
            cleanup_finished.set()

        engine._cancel_events[job.job_id] = threading.Event()
        with _prepared(engine, processor), patch.object(
            engine, "_execute_job", AsyncMock(return_value=np.zeros(8, dtype=np.float32))
        ), patch.object(engine, "_finalize_job", MagicMock()), patch.object(
            engine, "_return_processor", side_effect=_contended_return
        ):
            task = asyncio.create_task(engine.process_job(job))
            await asyncio.wait_for(cleanup_started.wait(), timeout=1.0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()

            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError):
                await task

        assert cleanup_finished.is_set()
        assert job.job_id not in engine._cancel_events


class TestPoolEvictionClosesTheEvicted:
    """#4370 — a FIFO eviction that drops without closing leaks the same way."""

    async def test_eviction_closes_the_evicted_processor(self):
        pool = ProcessorPool(AsyncMock(), max_cached=2)
        evicted_candidates = []

        for i in range(3):
            processor = MagicMock()
            evicted_candidates.append(processor)
            config = _make_config()
            config.mastering_profile = f"profile-{i}"
            await pool.return_to_cache("adaptive", config, processor)

        assert len(pool.processors) <= 2
        # The first one in is the one evicted, and it must have been closed.
        evicted_candidates[0].close.assert_called_once()
        evicted_candidates[-1].close.assert_not_called()

    async def test_lru_not_fifo_eviction(self):
        """Eviction is least-recently-*used*, not oldest-inserted (#4370).

        The code looks like insertion-order FIFO, which is how #4370 read it —
        but that reading came from the pre-#4250 inline version where a cache
        hit left the entry in place. `get_or_create()` POPS on hit (#3201), so a
        returned processor is always re-appended and insertion order tracks
        last-return order. This test pins that invariant: touch the oldest entry
        mid-way and a *different* one must be evicted.
        """
        pool = ProcessorPool(AsyncMock(), max_cached=2)
        configs, processors = [], []
        for i in range(3):
            config = _make_config()
            config.mastering_profile = f"profile-{i}"
            configs.append(config)
            processors.append(MagicMock())

        # Fill to capacity with 0 and 1.
        await pool.return_to_cache("adaptive", configs[0], processors[0])
        await pool.return_to_cache("adaptive", configs[1], processors[1])

        # Use 0 again — pop, then return. It becomes the most recent.
        taken = await pool.get_or_create("adaptive", configs[0])
        assert taken is processors[0]
        await pool.return_to_cache("adaptive", configs[0], processors[0])

        # Adding a third must now evict 1 (least recently used), not 0.
        await pool.return_to_cache("adaptive", configs[2], processors[2])

        processors[1].close.assert_called_once()
        processors[0].close.assert_not_called()
        assert processors[0] in pool.processors.values()


class TestSingleReturnSite:
    """#4567 CONSISTENCY — one call site, so a new branch cannot miss it.

    process_job()'s try/except/finally orchestration body now lives in
    job_lifecycle.process_job() (#4250 follow-up); ProcessingEngine.process_job
    is a thin delegate that no longer contains this source text, so the
    assertion targets the module the logic actually moved to.
    """

    async def test_process_job_reclaims_the_processor_from_finally_only(self):
        src = inspect.getsource(_job_lifecycle_process_job)

        assert src.count("_cleanup_processor(") == 1
        finally_body = src.split("finally:", 1)[1]
        assert "_cleanup_processor(" in finally_body
        assert "asyncio.shield(cleanup_task)" in finally_body
