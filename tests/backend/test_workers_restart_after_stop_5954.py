"""Background workers can be restarted after stop() (#5954, #5955).

Library reset stops every background worker, bulk-deletes, then starts them again.
The fingerprint queue never cleared ``should_stop``, so its new workers exited at once
(and ``stop()`` joined them on the event loop); the auto-scanner never cleared its
stop event, so its restarted loop returned immediately. Both are left dead by a reset.
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.services.fingerprint_queue import FingerprintExtractionQueue


def _queue(num_workers=2, linger=0.0):
    queue = FingerprintExtractionQueue(
        fingerprint_extractor=Mock(), get_repository_factory=Mock(), num_workers=num_workers,
        enable_adaptive_scaling=False,
    )

    # Workers idle in a loop that honours should_stop, like the real one; `linger`
    # keeps one running after the stop signal, like a worker finishing a track.
    def idle(worker_id):
        while not queue.should_stop:
            time.sleep(0.01)
        time.sleep(linger)

    queue._worker_loop = idle  # type: ignore[method-assign]
    return queue


@pytest.mark.asyncio
async def test_fingerprint_queue_runs_workers_again_after_stop():
    queue = _queue(2)
    await queue.start()
    assert await queue.stop() is True
    assert queue.workers == []

    await queue.start()
    try:
        assert len(queue.workers) == 2
        assert all(w.is_alive() for w in queue.workers)
        assert queue.should_stop is False
    finally:
        await queue.stop()


@pytest.mark.asyncio
async def test_fingerprint_queue_stop_does_not_block_the_event_loop():
    queue = _queue(1, linger=0.3)
    await queue.start()
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.005)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        assert await queue.stop(timeout=5) is True
    finally:
        task.cancel()

    assert ticks >= 10  # the loop kept turning for the ~0.3 s stop() waited


@pytest.mark.asyncio
async def test_auto_scanner_runs_again_after_stop():
    from services.library_auto_scanner import LibraryAutoScanner

    scanner = LibraryAutoScanner(Mock(), Mock(), None, Mock())
    cycles = 0

    async def cycle():
        nonlocal cycles
        cycles += 1
        await asyncio.sleep(0.01)

    scanner._run_cycle = cycle  # type: ignore[method-assign]
    with patch.object(scanner, "_stop_watchdog", Mock()):
        await scanner.start()
        await asyncio.sleep(0.05)
        await scanner.stop()
        before = cycles

        await scanner.start()
        await asyncio.sleep(0.05)
        await scanner.stop()

    assert before >= 1
    assert cycles > before  # the restarted loop actually ran
