"""
Fingerprint Claim Retry
~~~~~~~~~~~~~~~~~~~~~~~

A worker leaves a queue phase when its claim returns ``None``. That has to mean
"queue empty" and nothing else. The scheduler's claim methods used to log a
database error and return ``None`` too (#6334), so one lock timeout past the
busy timeout during a heavy scan took a worker out of the pool until restart.
They now raise, and this helper rides out a transient failure: it retries with
backoff and gives up (returns ``None``, ending the phase as before) only after
``CLAIM_FAILURE_LIMIT`` consecutive failures, so a dead database cannot spin a
worker forever either.

Only the claim is retried. An extraction failure is per-track, is handled where
it happens, and must never count toward a worker leaving the pool.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import time
from collections.abc import Callable
from typing import TypeVar

from ..utils.logging import error

T = TypeVar("T")

# Consecutive failed claims before a worker gives up on the phase.
CLAIM_FAILURE_LIMIT = 5
CLAIM_RETRY_BASE_SECONDS = 0.1
CLAIM_RETRY_MAX_SECONDS = 2.0


def claim_with_retry(
    claim: Callable[[], T | None],
    worker_id: int,
    should_stop: Callable[[], bool],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> T | None:
    """Run ``claim()``; return its result, or ``None`` if the queue is empty or the phase should end.

    ``None`` from ``claim`` is returned as is (queue empty). An exception is
    logged and retried after an exponentially growing pause, unless the pool is
    stopping.
    """
    for attempt in range(1, CLAIM_FAILURE_LIMIT + 1):
        try:
            return claim()
        except Exception as e:
            error(f"Worker {worker_id} claim failed (attempt {attempt}/{CLAIM_FAILURE_LIMIT}): {e}")
            if should_stop() or attempt == CLAIM_FAILURE_LIMIT:
                break
            sleep(min(CLAIM_RETRY_BASE_SECONDS * 2 ** (attempt - 1), CLAIM_RETRY_MAX_SECONDS))
    error(f"Worker {worker_id} giving up claiming tracks after repeated database errors")
    return None
