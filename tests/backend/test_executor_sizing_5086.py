"""
Regression tests for explicit thread-pool sizing (#5086, reconciling #4810)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Nothing called `loop.set_default_executor(...)`, so all ~207 `asyncio.to_thread`
sites across the backend shared CPython's default pool
(`min(32, os.cpu_count() + 4)` — 6-8 workers on a 2-4 core desktop).
`MAX_CONCURRENT_STREAMS` (10) admits up to 2 submissions per stream (per-chunk
DSP + look-ahead disk read), so streaming alone could submit ~20, before any
repository call, PIL thumbnail job, or the multi-minute library scan competed
for the same pool. Past the pool size, work queues FIFO and undifferentiated
and `CHUNK_PROCESS_TIMEOUT` (#3852) starts firing on *queueing* delay.

#4810 proposed a flat 8-worker cap for the opposite reason (protecting the
10-connection SQLAlchemy pool). Applied alone that would have made streaming
strictly worse. The reconciliation is two pools:

- streaming pool at `2 x MAX_CONCURRENT_STREAMS` for the per-chunk hot path;
- an 8-worker default/IO pool for everything else, under the DB pool's ceiling.

These tests pin both sizes, the wiring (#4810's WIRING check — an executor
defined but never installed is the failure mode it flags), and the fallback
that keeps everything working when no pool is installed.
"""

import asyncio
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import executors
from core.audio_stream_controller import MAX_CONCURRENT_STREAMS


@pytest.fixture(autouse=True)
async def _clean_executors():
    """The pools are module-global and replace the running loop's default
    executor, so every test must start and end from a clean slate."""
    executors.shutdown_executors()
    try:
        yield
    finally:
        executors.shutdown_executors()


@pytest.fixture
async def installed():
    """Install the pools inside the running loop.

    Must be an *async* fixture: `install_executors()` calls
    `set_default_executor` on `asyncio.get_running_loop()`, which is exactly
    the per-loop wiring #4810's WIRING check is about. A sync fixture has no
    running loop and would install against nothing.
    """
    executors.install_executors()
    yield executors


@pytest.mark.regression
class TestPoolSizing:

    @pytest.mark.asyncio
    async def test_streaming_pool_accommodates_max_concurrent_streams(self, installed):
        """#5086's acceptance criterion, verbatim: >= 2 x MAX_CONCURRENT_STREAMS,
        because each admitted stream can have its chunk DSP and its look-ahead
        read in flight simultaneously."""
        pool = installed.get_stream_executor()
        assert pool is not None, "streaming pool was not created"
        assert pool._max_workers >= 2 * MAX_CONCURRENT_STREAMS, (
            f"streaming pool has {pool._max_workers} workers, needs at least "
            f"{2 * MAX_CONCURRENT_STREAMS} for {MAX_CONCURRENT_STREAMS} streams"
        )

    @pytest.mark.asyncio
    async def test_io_pool_cannot_starve_the_db_connection_pool(self, installed):
        """#4810's concern: the DB pool tops out at pool_size=5 + max_overflow=5.
        More concurrent session-holding workers than that means the extras block
        for SQLAlchemy's 30s pool_timeout and surface as a 500."""
        pool = installed.get_io_executor()
        assert pool is not None, "IO pool was not created"
        assert pool._max_workers <= 10, (
            f"IO pool has {pool._max_workers} workers against a 10-connection "
            f"DB pool — the mismatch #4810 reported"
        )

    @pytest.mark.asyncio
    async def test_the_two_pools_are_distinct(self, installed):
        """The whole point of splitting: routing streaming through the same
        pool as scan/DB work would re-couple exactly what this separates."""
        assert installed.get_stream_executor() is not installed.get_io_executor()


@pytest.mark.regression
class TestWiring:
    """#4810's WIRING completeness check — an executor that is defined but
    never installed changes nothing at runtime."""

    @pytest.mark.asyncio
    async def test_io_pool_is_installed_as_the_loop_default(self, installed):
        loop = asyncio.get_running_loop()
        assert loop._default_executor is installed.get_io_executor(), (
            "the IO pool was created but never set as the loop's default "
            "executor, so plain asyncio.to_thread calls still use CPython's"
        )

    @pytest.mark.asyncio
    async def test_plain_to_thread_runs_on_the_io_pool(self, installed):
        """Behavioural counterpart to the wiring assertion above."""
        name = await asyncio.to_thread(lambda: threading.current_thread().name)
        assert name.startswith("auralis-io"), (
            f"asyncio.to_thread ran on {name!r}, not the installed IO pool"
        )

    @pytest.mark.asyncio
    async def test_run_in_stream_executor_uses_the_streaming_pool(self, installed):
        """The per-chunk hot path must land on the dedicated pool, not the
        default one — that separation is the fix."""
        name = await executors.run_in_stream_executor(
            lambda: threading.current_thread().name
        )
        assert name.startswith("auralis-stream"), (
            f"streaming work ran on {name!r}, not the dedicated streaming pool"
        )

    @pytest.mark.asyncio
    async def test_install_is_idempotent(self, installed):
        """The lifespan can run more than once in a test process; a second
        install must not orphan the first pair of pools."""
        first_stream = installed.get_stream_executor()
        first_io = installed.get_io_executor()
        installed.install_executors()
        assert installed.get_stream_executor() is first_stream
        assert installed.get_io_executor() is first_io


@pytest.mark.regression
class TestFallbackWithoutInstall:
    """Streaming functions are driven directly by plenty of tests and scripts
    that never run the lifespan. Those must keep working on the default pool —
    the pre-#5086 behaviour."""

    @pytest.mark.asyncio
    async def test_run_in_stream_executor_works_with_no_pool_installed(self):
        assert executors.get_stream_executor() is None
        result = await executors.run_in_stream_executor(lambda x: x * 2, 21)
        assert result == 42

    @pytest.mark.asyncio
    async def test_run_in_stream_executor_propagates_arguments_and_errors(self):
        assert await executors.run_in_stream_executor(pow, 2, 10) == 1024

        with pytest.raises(ValueError, match="boom"):
            await executors.run_in_stream_executor(
                lambda: (_ for _ in ()).throw(ValueError("boom"))
            )

    @pytest.mark.asyncio
    async def test_shutdown_is_safe_when_nothing_was_installed(self):
        executors.shutdown_executors()  # must not raise
        assert executors.get_stream_executor() is None


@pytest.mark.regression
class TestShutdown:

    @pytest.mark.asyncio
    async def test_shutdown_clears_both_pools(self):
        executors.install_executors()
        assert isinstance(executors.get_stream_executor(), ThreadPoolExecutor)

        executors.shutdown_executors()

        assert executors.get_stream_executor() is None
        assert executors.get_io_executor() is None
