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

Deliberately NOT routed to `STREAM_EXECUTOR`: per-stream setup and teardown —
track lookup, path validation, temp-WAV conversion, `rmtree`, prefetch,
fingerprint existence checks. Those run once per stream, not once per chunk,
and several are repository calls that belong on the DB-sized pool. Only work
that repeats per chunk is latency-critical enough to warrant the reservation.

Thread reservation is a ceiling, not an allocation: `ThreadPoolExecutor`
spawns workers lazily, so an idle app holds zero threads and a typical
single-stream desktop session holds about two.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import contextvars
import functools
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
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
IO_POOL_SIZE: int = get_int_env("AURALIS_IO_POOL_WORKERS", 8)

_stream_executor: ThreadPoolExecutor | None = None
_io_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def get_stream_executor() -> ThreadPoolExecutor | None:
    """The streaming pool, or None if `install_executors()` has not run.

    Returning None rather than lazily creating one is deliberate: a pool
    created outside the lifespan would never be shut down, and callers below
    already treat None as "use the default executor", which is exactly the
    pre-#5086 behaviour. Tests and scripts that drive streaming functions
    directly therefore keep working unchanged.
    """
    return _stream_executor


def get_io_executor() -> ThreadPoolExecutor | None:
    """The general I/O pool, or None if `install_executors()` has not run."""
    return _io_executor


async def run_in_stream_executor(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """`asyncio.to_thread`, but on the dedicated streaming pool (#5086).

    Falls back to the default executor when no pool is installed, so this is a
    drop-in replacement for `asyncio.to_thread` at every call site.

    Like `to_thread`, the current context is propagated into the worker —
    streaming reads `_stream_type_var` / `_track_id_var` contextvars, so
    dropping that would change logging behaviour.
    """
    executor = _stream_executor
    if executor is None:
        return await asyncio.to_thread(func, *args, **kwargs)

    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    call = functools.partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(executor, call)


def install_executors() -> tuple[ThreadPoolExecutor, ThreadPoolExecutor]:
    """Create both pools and install the I/O pool as the loop's default.

    Idempotent: calling twice returns the existing pools rather than orphaning
    the first pair (the lifespan can run more than once in a test process).

    Must be called from inside the running event loop — `set_default_executor`
    is per-loop, and installing it against the wrong loop is the silent
    wiring failure #4810's WIRING check warns about.
    """
    global _stream_executor, _io_executor

    with _lock:
        if _stream_executor is not None and _io_executor is not None:
            return _stream_executor, _io_executor

        stream_workers = _stream_pool_size()
        _stream_executor = ThreadPoolExecutor(
            max_workers=stream_workers, thread_name_prefix="auralis-stream"
        )
        _io_executor = ThreadPoolExecutor(
            max_workers=IO_POOL_SIZE, thread_name_prefix="auralis-io"
        )

        asyncio.get_running_loop().set_default_executor(_io_executor)

        logger.info(
            f"Thread pools installed: streaming={stream_workers} workers "
            f"(2 x MAX_CONCURRENT_STREAMS), default/IO={IO_POOL_SIZE} workers "
            f"(<= the 10-connection DB pool)"
        )
        return _stream_executor, _io_executor


def shutdown_executors(wait: bool = False) -> None:
    """Tear both pools down and clear the module state.

    `wait=False` by default so shutdown is not held hostage by a worker stuck
    in a blocking read on unreachable storage — precisely the orphaned-thread
    case #5082/#4815/#4727 record, where the thread outlives the coroutine
    that abandoned it. Python's interpreter shutdown joins non-daemon pool
    threads regardless; this just avoids blocking the lifespan on them.
    """
    global _stream_executor, _io_executor

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
            if _io_executor is not None and getattr(loop, "_default_executor", None) is _io_executor:
                loop._default_executor = None  # type: ignore[attr-defined]
        except RuntimeError:
            # No running loop (shutdown from a sync context) — nothing to detach.
            pass
        except Exception as e:
            logger.debug(f"Could not detach the default executor: {e}")

        for name, executor in (("streaming", _stream_executor), ("IO", _io_executor)):
            if executor is None:
                continue
            try:
                executor.shutdown(wait=wait, cancel_futures=True)
            except Exception as e:
                # Mirrors #4569's rule for shutdown steps: one failing step
                # must not abort the rest of teardown.
                logger.warning(f"Failed to shut down the {name} thread pool: {e}")

        _stream_executor = None
        _io_executor = None
