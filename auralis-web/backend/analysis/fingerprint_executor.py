"""
Fingerprint Executor
~~~~~~~~~~~~~~~~~~~~

The fingerprint thread-pool lifecycle split from fingerprint_generator.py
(#6271): lazy creation, shutdown (unbounded and bounded) and the
in-thread compute wrapper. The thread pool exists so fingerprint DSP never
runs on the asyncio event loop; see the generator's module docstring.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import atexit
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from auralis.analysis.fingerprint.windowed_compute import compute_windowed_fingerprint
from core.env_config import get_int_env

logger = logging.getLogger(__name__)

# Number of worker threads for fingerprinting. Override via
# AURALIS_FINGERPRINT_WORKERS (#3917) — see auralis-web/backend/CONFIG.md.
_FINGERPRINT_WORKERS = get_int_env(
    "AURALIS_FINGERPRINT_WORKERS", max(1, min(2, (os.cpu_count() or 2) // 2))
)


# Module-level ThreadPoolExecutor (lazy initialized)
_fingerprint_executor: ThreadPoolExecutor | None = None


def _get_fingerprint_executor() -> ThreadPoolExecutor:
    """Get or create the fingerprint ThreadPoolExecutor (lazy initialization)."""
    global _fingerprint_executor
    if _fingerprint_executor is None:
        _fingerprint_executor = ThreadPoolExecutor(
            max_workers=_FINGERPRINT_WORKERS,
            thread_name_prefix="fingerprint",
        )
        logger.info(f"🔧 Created fingerprint ThreadPoolExecutor with {_FINGERPRINT_WORKERS} workers")
    return _fingerprint_executor


def shutdown_fingerprint_executor() -> None:
    """Shutdown the fingerprint executor gracefully.

    Synchronous, non-blocking (wait=False) — this is the atexit safety net
    for abnormal exits where the FastAPI lifespan never ran shutdown, so it
    must not risk stalling interpreter exit. The normal path is
    shutdown_fingerprint_executor_bounded() below, called explicitly from
    the lifespan (#4756); by the time atexit fires, _fingerprint_executor is
    already None and this is a no-op.
    """
    global _fingerprint_executor
    if _fingerprint_executor is not None:
        logger.info("🛑 Shutting down fingerprint ThreadPoolExecutor...")
        _fingerprint_executor.shutdown(wait=False, cancel_futures=True)
        _fingerprint_executor = None


async def shutdown_fingerprint_executor_bounded(timeout: float = 10.0) -> None:
    """Bounded-wait shutdown for the FastAPI lifespan (#4756).

    Every other worker/pool in config/startup.py's _shutdown_components()
    is explicitly torn down there, in a fixed order relative to the library
    database shutdown; the fingerprint executor was the one component only
    reachable via atexit — which runs *after* the lifespan (so after the
    library database is already WAL-checkpointed and disposed) and blocks
    process exit until every in-flight fingerprint computation finishes
    (ThreadPoolExecutor threads cannot be force-killed, and stdlib's own
    atexit hook joins them regardless of cancel_futures).

    Unlike the atexit path, this waits (wait=True) so an in-flight
    computation cannot race the library-database shutdown that follows it —
    but bounded by `timeout`, offloaded via asyncio.to_thread so the event
    loop stays responsive, so a pathologically slow computation cannot stall
    process shutdown indefinitely. If the bound is exceeded, the worker
    thread keeps running in the background (join() cannot be aborted) and
    the stdlib's own interpreter-exit hook still guarantees it's joined
    before the process actually exits.
    """
    global _fingerprint_executor
    if _fingerprint_executor is None:
        return
    executor = _fingerprint_executor
    _fingerprint_executor = None
    logger.info("🛑 Shutting down fingerprint ThreadPoolExecutor...")
    try:
        await asyncio.wait_for(
            asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True),
            timeout=timeout,
        )
        logger.info("✅ Fingerprint ThreadPoolExecutor shut down")
    except TimeoutError:
        logger.warning(
            f"⚠️  Fingerprint ThreadPoolExecutor shutdown exceeded {timeout}s bound — "
            "an in-flight computation may still be running; continuing shutdown"
        )


# Register cleanup on exit — safety net for abnormal exits that skip the
# lifespan's shutdown_fingerprint_executor_bounded() call above.
atexit.register(shutdown_fingerprint_executor)


def _compute_windowed_fingerprint_in_thread(filepath: str) -> dict[str, Any] | None:
    """Run the shared windowed fingerprint pipeline on an executor worker.

    #5531: this used to be a full-file decode followed by a raw call to the
    Rust schema glue — unsanitized (a NaN/Inf Rust result was stored verbatim
    and poisoned every later read), uncapped (a multi-hour file was decoded in
    full), and without the #4595 body+probe LUFS/crest bias correction, so it
    disagreed with the same track's batch-scan fingerprint.
    compute_windowed_fingerprint() closes all three at once and returns the
    exact fingerprint the batch path produces.

    Kept at module level so executor submission stays simple. Runs in a worker
    thread of the current process — the PyO3 Rust engine releases the GIL, so
    it does not block the event loop or playback threads.

    Returns:
        Dict with 25 sanitized fingerprint dimensions, or None on failure.
    """
    try:
        from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
            AudioFingerprintAnalyzer,
        )
        from auralis.analysis.fingerprint.windowed_compute import (
            compute_windowed_fingerprint,
        )

        return compute_windowed_fingerprint(AudioFingerprintAnalyzer(), Path(filepath))
    except Exception as e:
        logging.getLogger(__name__).error(f"Windowed fingerprint computation failed: {e}")
        return None
