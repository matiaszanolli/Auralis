"""
Background Worker Lifecycle
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Single source of truth for the set of long-running background workers and
helpers to stop/start them. Both the lifespan shutdown (``startup.py``) and the
destructive ``POST /api/library/reset`` handler (``routers/library.py``) operate
on this same set so they can never drift apart (#4111, #3812).

Each worker is resolved by its component-registry key via a ``resolve`` callable
(``resolve(key) -> worker | None``) and is expected to expose async
``start()`` / ``stop()`` methods.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

# Canonical set of background workers, in stop order (auto_scanner first since it
# may enqueue work into the fingerprint queues). Restart order is the reverse.
BACKGROUND_WORKER_KEYS: tuple[str, ...] = (
    "auto_scanner",
    "ondemand_fingerprint_queue",
    "fingerprint_queue",
    # #4682: the one-shot similarity auto-fit pass used to run on an
    # untracked daemon thread with no stop signal. Stopped last / restarted
    # first — it only reads fingerprints (never enqueues into the queues
    # above it) so its ordering relative to them doesn't matter for
    # correctness; it's appended here rather than reordering the existing
    # three.
    "similarity_autofit",
)

# Per-worker keyword arguments for ``stop()``. Lives here rather than at the
# call sites so the lifespan shutdown, the startup rollback, and the
# library-reset endpoint cannot disagree about how a worker is stopped (#4569).
# ``FingerprintExtractionQueue.stop(timeout=30.0)`` already defaults to 30s;
# passing it explicitly keeps the contract visible.
WORKER_STOP_KWARGS: dict[str, dict[str, Any]] = {
    "fingerprint_queue": {"timeout": 30.0},
}

Resolve = Callable[[str], Any]


async def stop_background_workers(resolve: Resolve) -> list[str]:
    """Stop every registered background worker, best-effort.

    Each ``stop()`` is individually guarded: one worker failing must not
    prevent the rest of the fleet — or the caller's remaining shutdown steps —
    from running (#4569).

    Args:
        resolve: ``resolve(key)`` returns the worker instance or ``None``.

    Returns:
        The keys of the workers that were actually stopped (existed and were
        asked to stop), so the caller can restart exactly that set.
    """
    stopped: list[str] = []
    for key in BACKGROUND_WORKER_KEYS:
        worker = resolve(key)
        if worker is None:
            continue
        try:
            await _maybe_await(worker.stop(**WORKER_STOP_KWARGS.get(key, {})))
            stopped.append(key)
            logger.debug("Background worker stopped: %s", key)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Failed to stop background worker %s: %s", key, e)
    return stopped


async def start_background_workers(resolve: Resolve, keys: list[str]) -> None:
    """Restart the given background workers (reverse of stop order)."""
    for key in reversed(keys):
        worker = resolve(key)
        if worker is None:
            continue
        try:
            await _maybe_await(worker.start())
            logger.debug("Background worker started: %s", key)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Failed to start background worker %s: %s", key, e)


async def _maybe_await(result: Awaitable[Any] | Any) -> None:
    """Await ``result`` if it is awaitable (start/stop may be sync or async)."""
    if hasattr(result, "__await__"):
        await result
