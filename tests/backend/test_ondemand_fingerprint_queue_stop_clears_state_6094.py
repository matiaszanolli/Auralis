"""
Regression tests: the on-demand fingerprint queue forgets its state on stop() (#6094).

stop() cancelled the worker mid-``get_or_generate`` and left ``processing`` set,
so ``enqueue(track_id)`` returned False for the rest of the process ("currently
being fingerprinted"), and ids queued before a library reset stayed queued --
after a reset track ids restart from 1, so they would be fingerprinted against
different tracks.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from analysis.fingerprint_queue import FingerprintQueue


class _BlockingGenerator:
    """get_or_generate parks until cancelled, signalling when it is entered."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()

    async def get_or_generate(self, track_id: int, filepath: str):
        self.entered.set()
        await asyncio.Event().wait()


def _queue(generator) -> FingerprintQueue:
    return FingerprintQueue(generator, Mock(return_value="/fake/path.flac"))


@pytest.mark.asyncio
async def test_cancel_mid_generation_then_restart_allows_reenqueue():
    generator = _BlockingGenerator()
    queue = _queue(generator)
    await queue.start()
    assert queue.enqueue(5)
    await asyncio.wait_for(generator.entered.wait(), timeout=5)
    assert queue.get_stats()["processing"] == 5

    await queue.stop()
    await queue.start()
    try:
        assert queue.get_stats()["processing"] is None
        assert queue.enqueue(5) is True
    finally:
        await queue.stop()


@pytest.mark.asyncio
async def test_stop_drops_ids_queued_before_a_reset():
    generator = _BlockingGenerator()
    queue = _queue(generator)
    await queue.start()
    for track_id in (1, 2, 3):
        assert queue.enqueue(track_id)
    await asyncio.wait_for(generator.entered.wait(), timeout=5)

    await queue.stop()

    stats = queue.get_stats()
    assert stats["queued"] == 0
    assert stats["processing"] is None
    # The ids are enqueueable again, i.e. also gone from the dedup set.
    assert all(queue.enqueue(track_id) for track_id in (1, 2, 3))


@pytest.mark.asyncio
async def test_stop_on_a_never_started_queue_is_harmless():
    queue = _queue(_BlockingGenerator())
    assert queue.enqueue(7)

    await queue.stop()

    assert queue.get_stats()["queued"] == 0


@pytest.mark.asyncio
async def test_normal_processing_still_completes_and_clears_processing():
    generator = Mock()

    async def _done(track_id, filepath):
        return {"ok": True}

    generator.get_or_generate = _done
    queue = _queue(generator)
    await queue.start()
    try:
        assert queue.enqueue(9)
        for _ in range(50):
            if queue.get_stats()["completed"] == 1:
                break
            await asyncio.sleep(0.05)
        stats = queue.get_stats()
        assert stats["completed"] == 1
        assert stats["processing"] is None
    finally:
        await queue.stop()
