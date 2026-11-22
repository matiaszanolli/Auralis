#!/usr/bin/env python3

"""
Thread-pool executors
~~~~~~~~~~~~~~~~~~~~~

Two explicit pools, installed at lifespan startup, replacing the single
implicit CPython default `ThreadPoolExecutor` that every `asyncio.to_thread`
call site shared (#5086 / #4810).

**Why two pools.** Nothing called `loop.set_default_executor(...)`, so all
~207 `to_thread` sites across the backend competed for one pool sized
`min(32, os.cpu_count() + 4)` — 6-8 workers on a typical 2-4 core desktop.
`MAX_CONCURRENT_STREAMS` (10) admits up to 2 executor submissions per stream
(per-chunk DSP + look-ahead disk read), so streaming alone could submit ~20.
Past the pool's size, `to_thread` work queues FIFO and undifferentiated: a
latency-critical chunk-DSP call ends up behind an unrelated `tracks.get_all()`
or the multi-minute library scan's work, and `CHUNK_PROCESS_TIMEOUT` (30s,
#3852) then fires on *queueing* delay rather than a genuine DSP hang —
misattributing the failure and stalling audio.

A single flat cap cannot fix both halves of this. #4810 asked for 8 workers to
protect the 10-connection SQLAlchemy pool (`pool_size=5 + max_overflow=5`);
that number is right for DB-bound work but would make streaming strictly worse
than the status quo. Splitting resolves both without compromise:

- `STREAM_EXECUTOR` — sized to streaming demand (`2 x MAX_CONCURRENT_STREAMS`,
  floor 4), used *only* by the per-chunk hot path, so DSP and chunk reads
  never queue behind repository or scan work.
- `IO_EXECUTOR` — installed as the loop's default, so it absorbs every other
  `to_thread` site (repository calls in routers, PIL thumbnailing, the
  shielded library scan) at a size that cannot starve the DB pool.

A small `TRANSPORT_EXECUTOR` runs the audio engine's play/pause/stop/seek calls
while the playback lock is held (#6093): on the I/O pool those queued behind a
library scan, and every WS transport handler waiting on that lock in its receive
loop stalled behind them (flow control, pongs).

A third, small `JOB_EXECUTOR` runs full-track mastering-job DSP (#5335). A job
DSP call is bounded by `asyncio.wait_for`, but that cancels only the asyncio
wrapper — the OS thread keeps running the hung call. On the default pool each
such timeout pinned one of the 8 DB-sized workers, so a handful of pathological
files could stall every repository call in the process. On its own pool a hung
job can only delay other jobs.

Deliberately NOT routed to `STREAM_EXECUTOR`: per-stream setup and teardown —
track lookup, path validation, temp-WAV conversion, `rmtree`, prefetch,
fingerprint existence checks. Those run once per stream, not once per chunk,
and several are repository calls that belong on the DB-sized pool. Only work
that repeats per chunk is latency-critical enough to warrant the reservation.

Thread reservation is a ceiling, not an allocation: `ThreadPoolExecutor`
spawns workers lazily, so an idle app holds zero threads and a typical
single-stream desktop session holds about two.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import contextvars
import functools
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, TypeVar

from .env_config import get_int_env

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Imported lazily inside _stream_pool_size() rather than at module scope:
# audio_stream_controller imports plenty of heavy backend modules, and this
# module is pulled in by startup wiring that must stay cheap to import.


def _stream_pool_size() -> int:
    """Workers reserved for the per-chunk streaming hot path.

    `2 x MAX_CONCURRENT_STREAMS` because each admitted stream can have two
    submissions in flight at once — its chunk DSP and its look-ahead disk
    read. The floor of 4 keeps a single-core machine (or a deployment that
    lowered MAX_CONCURRENT_STREAMS to 1) from serialising those two against
    each other.
    """
    from .audio_stream_controller import MAX_CONCURRENT_STREAMS

    return max(4, 2 * MAX_CONCURRENT_STREAMS)


# Default executor size. Must stay at or below the SQLAlchemy pool's ceiling
# (pool_size=5 + max_overflow=5 = 10, auralis/library/database.py) — past that,
# the 11th concurrent session-holding worker blocks for SQLAlchemy's 30s
# pool_timeout and then surfaces as a 500 rather than back-pressure (#4810).
# 8 leaves headroom for the non-repository work sharing this pool.
_DB_POOL_CEILING = 10
_requested_io_workers = get_int_env("AURALIS_IO_POOL_WORKERS", 8)
if _requested_io_workers > _DB_POOL_CEILING:
    logger.warning(
        f"AURALIS_IO_POOL_WORKERS={_requested_io_workers} exceeds the DB pool ceiling "
        f"({_DB_POOL_CEILING}); using {_DB_POOL_CEILING} (#5991)"
    )
IO_POOL_SIZE: int = min(_DB_POOL_CEILING, _requested_io_workers)

# Mastering-job DSP (#5335). Matches ProcessingEngine(max_concurrent_jobs=2) in
# config/startup/workers.py: the job semaphore already admits at most that many jobs,
# so more workers would only ever serve threads a timeout has abandoned.
JOB_POOL_SIZE: int = get_int_env("AURALIS_JOB_POOL_WORKERS", 2)

# Transport engine calls (#6093). Serialised by the playback lock already, so more
# than a couple of workers could only ever serve threads a stuck call abandoned.
TRANSPORT_POOL_SIZE: int = get_int_env("AURALIS_TRANSPORT_POOL_WORKERS", 2)


@dataclass
class _Pool:
    """One named pool: how to size it, its thread-name prefix, and (once installed) the executor.

    Every pool is built, run on and torn down the same way, so adding one is a
    single `_Pool(...)` row in `_POOLS` plus its two public wrappers (#6697).
    """

    label: str
    prefix: str
    size: Callable[[], int]  # read at install time, so the *_POOL_SIZE globals stay patchable
    executor: ThreadPoolExecutor | None = None

    def start(self) -> int:
        """Build the executor; returns its worker count for the install log."""
        workers = self.size()
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=self.prefix)
        return workers

    def stop(self, wait: bool) -> None:
        executor, self.executor = self.executor, None
        if executor is None:
            return
        try:
            executor.shutdown(wait=wait, cancel_futures=True)
        except Exception as e:
            # Mirrors #4569's rule for shutdown steps: one failing step
            # must not abort the rest of teardown.
            logger.warning(f"Failed to shut down the {self.label} thread pool: {e}")

    async def run(self, func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """`asyncio.to_thread` on this pool, or on the default executor when not installed.

        Like `to_thread`, the current context is propagated into the worker —
        streaming reads `_stream_type_var` / `_track_id_var` contextvars, so
        dropping that would change logging behaviour.
        """
        executor = self.executor
        if executor is None:
            return await asyncio.to_thread(func, *args, **kwargs)

        loop = asyncio.get_running_loop()
        ctx = contextvars.copy_context()
        call = functools.partial(ctx.run, func, *args, **kwargs)
        return await loop.run_in_executor(executor, call)


_STREAM = _Pool("streaming", "auralis-stream", _stream_pool_size)
_IO = _Pool("IO", "auralis-io", lambda: IO_POOL_SIZE)
_JOB = _Pool("job", "auralis-job", lambda: JOB_POOL_SIZE)
_TRANSPORT = _Pool("transport", "auralis-transport", lambda: TRANSPORT_POOL_SIZE)
_POOLS: tuple[_Pool, ...] = (_STREAM, _IO, _JOB, _TRANSPORT)
_lock = threading.Lock()


def get_stream_executor() -> ThreadPoolExecutor | None:
    """The streaming pool, or None if `install_executors()` has not run.

    Returning None rather than lazily creating one is deliberate: a pool
    created outside the lifespan would never be shut down, and the `run_in_*`
    wrappers already treat None as "use the default executor", which is exactly
    the pre-#5086 behaviour. Tests and scripts that drive streaming functions
    directly therefore keep working unchanged.

    The getters exist for test introspection (pool identity/sizing assertions),
    not as hot-path API: `run_in_stream_executor` reads the pool directly (#5206),
    and production reaches the IO pool implicitly as the loop's default executor.
    """
    return _STREAM.executor


def get_io_executor() -> ThreadPoolExecutor | None:
    """The general I/O pool (the loop's default), or None if not installed."""
    return _IO.executor


def get_job_executor() -> ThreadPoolExecutor | None:
    """The mastering-job pool, or None if `install_executors()` has not run."""
    return _JOB.executor


def get_transport_executor() -> ThreadPoolExecutor | None:
    """The transport pool, or None if `install_executors()` has not run."""
    return _TRANSPORT.executor


async def run_in_stream_executor(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """`asyncio.to_thread`, but on the dedicated streaming pool (#5086).

    Falls back to the default executor when no pool is installed, so this is a
    drop-in replacement for `asyncio.to_thread` at every call site.
    """
    return await _STREAM.run(func, *args, **kwargs)


async def run_in_job_executor(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """`asyncio.to_thread` on the mastering-job pool (#5335); same fallback."""
    return await _JOB.run(func, *args, **kwargs)


async def run_in_transport_executor(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """`asyncio.to_thread` on the transport pool (#6093); same fallback."""
    return await _TRANSPORT.run(func, *args, **kwargs)


def install_executors() -> tuple[ThreadPoolExecutor, ThreadPoolExecutor]:
    """Create the pools and install the I/O pool as the loop's default.

    Idempotent: calling twice returns the existing pools rather than orphaning
    the first set (the lifespan can run more than once in a test process).

    Must be called from inside the running event loop — `set_default_executor`
    is per-loop, and installing it against the wrong loop is the silent
    wiring failure #4810's WIRING check warns about.
    """
    with _lock:
        started = [f"{pool.label}={pool.start()}" for pool in _POOLS if pool.executor is None]
        stream, io = _STREAM.executor, _IO.executor
        assert stream is not None and io is not None  # every pool was just started or already was
        if started:
            asyncio.get_running_loop().set_default_executor(io)
            logger.info(
                f"Thread pools installed: {', '.join(started)} workers "
                "(streaming = 2 x MAX_CONCURRENT_STREAMS; IO <= the 10-connection DB pool)"
            )
        return stream, io


def shutdown_executors(wait: bool = False) -> None:
    """Tear the pools down and clear the module state.

    `wait=False` by default so shutdown is not held hostage by a worker stuck
    in a blocking read on unreachable storage — precisely the orphaned-thread
    case #5082/#4815/#4727 record, where the thread outlives the coroutine
    that abandoned it. Python's interpreter shutdown joins non-daemon pool
    threads regardless; this just avoids blocking the lifespan on them.
    """
    with _lock:
        # Detach the IO pool from the loop BEFORE shutting it down. Leaving a
        # shut-down executor installed as the default would make any later
        # `asyncio.to_thread` raise "cannot schedule new futures after
        # shutdown"; clearing it lets asyncio lazily build its own if
        # something still needs to offload during late teardown.
        #
        # Assigned directly because there is no public detach API:
        # `set_default_executor` rejects anything that is not a
        # ThreadPoolExecutor, None included. `_default_executor` is the same
        # attribute that method writes. Guarded with getattr/hasattr so a
        # future asyncio internal change degrades to "not detached" instead of
        # crashing shutdown.
        try:
            loop = asyncio.get_running_loop()
            if _IO.executor is not None and getattr(loop, "_default_executor", None) is _IO.executor:
                loop._default_executor = None  # type: ignore[attr-defined]
        except RuntimeError:
            # No running loop (shutdown from a sync context) — nothing to detach.
            pass
        except Exception as e:
            logger.debug(f"Could not detach the default executor: {e}")

        for pool in _POOLS:
            pool.stop(wait)
