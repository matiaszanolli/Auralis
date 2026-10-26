"""
Tests for the shared background-worker lifecycle helpers (#4111)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``config.background_workers`` is the single source of truth for which
long-running workers exist and how they are stopped/started. Both the lifespan
shutdown and the library-reset endpoint use it so the sets cannot diverge.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.background_workers import (
    BACKGROUND_WORKER_KEYS,
    start_background_workers,
    stop_background_workers,
)

pytestmark = pytest.mark.asyncio


def test_canonical_worker_set():
    """The four known background workers are the canonical set."""
    assert set(BACKGROUND_WORKER_KEYS) == {
        "auto_scanner",
        "ondemand_fingerprint_queue",
        "fingerprint_queue",
        "similarity_autofit",
    }
    # auto_scanner stops first (it may enqueue into the fingerprint queues).
    assert BACKGROUND_WORKER_KEYS[0] == "auto_scanner"
    # similarity_autofit only reads fingerprints and depends on nothing else
    # in the set (#4682), so it's appended last / restarted first.
    assert BACKGROUND_WORKER_KEYS[-1] == "similarity_autofit"


async def test_stop_returns_only_present_workers():
    order: list[str] = []
    workers = {}
    for key in BACKGROUND_WORKER_KEYS:
        w = MagicMock()
        w.stop = AsyncMock(side_effect=lambda k=key: order.append(k))
        workers[key] = w
    # One worker is absent from the registry.
    del workers["fingerprint_queue"]

    stopped = await stop_background_workers(lambda k: workers.get(k))

    assert stopped == ["auto_scanner", "ondemand_fingerprint_queue", "similarity_autofit"]
    assert order == ["auto_scanner", "ondemand_fingerprint_queue", "similarity_autofit"]


async def test_start_restarts_in_reverse_order():
    order: list[str] = []
    workers = {}
    for key in BACKGROUND_WORKER_KEYS:
        w = MagicMock()
        w.start = AsyncMock(side_effect=lambda k=key: order.append(k))
        workers[key] = w

    await start_background_workers(lambda k: workers.get(k), list(BACKGROUND_WORKER_KEYS))

    # Reverse of stop order so dependencies come back up before their producers.
    assert order == list(reversed(BACKGROUND_WORKER_KEYS))


async def test_stop_skips_none_and_survives_errors():
    good = MagicMock()
    good.stop = AsyncMock()
    bad = MagicMock()
    bad.stop = AsyncMock(side_effect=RuntimeError("boom"))
    registry = {"auto_scanner": bad, "ondemand_fingerprint_queue": good}

    # A worker raising on stop must not abort the others, and is not reported
    # as successfully stopped.
    stopped = await stop_background_workers(lambda k: registry.get(k))

    assert "ondemand_fingerprint_queue" in stopped
    assert "auto_scanner" not in stopped
    good.stop.assert_awaited_once()


async def test_handles_synchronous_stop_start():
    """Workers with sync (non-awaitable) start/stop are still handled."""
    calls: list[str] = []
    worker = MagicMock()
    worker.stop = MagicMock(side_effect=lambda: calls.append("stop"))
    worker.start = MagicMock(side_effect=lambda: calls.append("start"))
    registry = {"auto_scanner": worker}

    stopped = await stop_background_workers(lambda k: registry.get(k))
    await start_background_workers(lambda k: registry.get(k), stopped)

    assert calls == ["stop", "start"]


async def test_stop_reporting_false_is_unstopped_and_not_restartable():
    """A stop() that returns False (FingerprintExtractionQueue on its timeout)
    left the worker alive: it is reported as unstopped, not as stopped (#6095)."""
    stuck = MagicMock()
    stuck.stop = AsyncMock(return_value=False)
    fine = MagicMock()
    fine.stop = AsyncMock(return_value=True)
    sync_none = MagicMock()
    sync_none.stop = MagicMock(return_value=None)
    registry = {
        "auto_scanner": sync_none,
        "ondemand_fingerprint_queue": stuck,
        "fingerprint_queue": fine,
    }

    unstopped: list[str] = []
    stopped = await stop_background_workers(lambda k: registry.get(k), unstopped)

    assert unstopped == ["ondemand_fingerprint_queue"]
    # None (a stop() with no verdict) still counts as stopped; the others
    # keep stopping after the stuck one.
    assert stopped == ["auto_scanner", "fingerprint_queue"]


async def test_unstopped_list_is_optional():
    stuck = MagicMock()
    stuck.stop = AsyncMock(return_value=False)

    assert await stop_background_workers(lambda k: stuck if k == "fingerprint_queue" else None) == []
