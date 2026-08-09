"""
Reusable Executor Pool
~~~~~~~~~~~~~~~~~~~~~~~

Long-lived, lazily-created executors shared across repeated parallel calls
(#3762).

Every parallel entry point in this package used to open its own
``with ProcessPoolExecutor(...)`` / ``with ThreadPoolExecutor(...)`` block, so
each call paid full worker-startup cost and then tore the workers down again:
~50-100 ms per process on Linux, 500-1000 ms on Windows. For a batch loop or a
per-chunk FFT that startup dominates the actual DSP.

``ExecutorPool`` keeps one executor per (kind, max_workers) pair alive for the
lifetime of its owner, so only the first call pays startup. Workers are still
spawned lazily by ``concurrent.futures`` — one per pending work item, up to
``max_workers`` — so sizing a pool at the configured maximum does not spawn more
workers than there are tasks.

**Nesting caveat**: a task running *on* a pooled executor must not submit to the
same pool and block on the result — a bounded pool makes that deadlock. Each
sub-processor therefore owns its own ExecutorPool rather than sharing one, so
the cross-component nesting that does occur (e.g. band processing inside a
batch worker) never contends for the same workers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor

from ...utils.logging import debug

_KIND_PROCESS = "process"
_KIND_THREAD = "thread"


class ExecutorPool:
    """Cache of long-lived executors keyed by ``(kind, max_workers)``.

    Thread-safe: ``get()`` may be called concurrently from worker threads.
    """

    def __init__(self, owner: str = "parallel") -> None:
        self._owner = owner
        self._executors: dict[tuple[str, int], Executor] = {}
        self._lock = threading.Lock()

    def get(self, max_workers: int, use_multiprocessing: bool = False) -> Executor:
        """Return the cached executor for this (kind, size), creating it if needed.

        A previously-cached executor that has become unusable — a
        ``BrokenProcessPool`` after a worker segfaulted, or one that was shut
        down — is discarded and replaced. Without that check a single crashed
        worker would poison every later call, which the old create-per-call code
        could not do.
        """
        kind = _KIND_PROCESS if use_multiprocessing else _KIND_THREAD
        key = (kind, max_workers)

        with self._lock:
            executor = self._executors.get(key)
            if executor is not None and not self._is_unusable(executor):
                return executor

            if executor is not None:
                debug(f"{self._owner}: discarding unusable {kind} pool ({max_workers} workers)")
                executor.shutdown(wait=False)

            factory = ProcessPoolExecutor if use_multiprocessing else ThreadPoolExecutor
            executor = factory(max_workers=max_workers)
            self._executors[key] = executor
            debug(f"{self._owner}: created {kind} pool ({max_workers} workers)")
            return executor

    @staticmethod
    def _is_unusable(executor: Executor) -> bool:
        """True if *executor* can no longer accept work.

        ``_broken`` / ``_shutdown`` are private but have been the stable
        internal state flags for both executor types since they were
        introduced; ``getattr`` defaults keep this safe if that ever changes.
        """
        return bool(getattr(executor, "_broken", False)) or bool(
            getattr(executor, "_shutdown", False)
        )

    def close(self, wait: bool = True) -> None:
        """Shut down every cached executor and clear the cache.

        Idempotent. The pool stays usable afterwards: a later ``get()`` builds a
        fresh executor rather than raising, so closing a processor that is
        subsequently reused degrades to the old create-on-demand cost instead of
        breaking it.
        """
        with self._lock:
            executors = list(self._executors.values())
            self._executors.clear()

        for executor in executors:
            executor.shutdown(wait=wait)
        if executors:
            debug(f"{self._owner}: closed {len(executors)} pool(s)")
