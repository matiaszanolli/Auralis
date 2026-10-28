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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from core.env_config import get_int_env

from config.limits import SHUTDOWN_STEP_TIMEOUT_S

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


async def shutdown_fingerprint_executor_bounded(
    timeout: float = SHUTDOWN_STEP_TIMEOUT_S,
) -> None:
    """Bounded-wait shutdown for the FastAPI lifespan (#4756).

    Every other pool in config/startup.py's _shutdown_components() is torn down there, in
    order relative to the library database; this executor was reachable only via atexit,
    which runs after the database is disposed and blocks exit until every in-flight
    fingerprint finishes. This waits (wait=True) so an in-flight computation cannot race
    the database shutdown, but bounded by `timeout` and offloaded via asyncio.to_thread so
    the event loop stays responsive. Past the bound the worker keeps running and the
    stdlib's exit hook still joins it before the process exits.
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

    #5531: runs the shared pipeline instead of a raw full-file decode plus Rust glue, so the
    result is sanitized, capped, and bias-corrected (#4595) exactly like the batch scan's.

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
