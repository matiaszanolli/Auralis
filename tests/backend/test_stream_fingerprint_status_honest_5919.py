"""The stream's fingerprint_progress says "queued" only when the track is really queued (#5919).

A missing queue, a raising enqueue and a full queue all logged at debug and still sent
status="queued", so the UI promised an analysis that would never run.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from analysis.fingerprint_queue import FingerprintQueue, get_fingerprint_queue, set_fingerprint_queue  # noqa: E402
from core.stream_fingerprint import check_or_queue_fingerprint  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest.fixture
def queue():
    previous = get_fingerprint_queue()
    q = FingerprintQueue(MagicMock(), lambda track_id: None)
    set_fingerprint_queue(q)
    yield q
    set_fingerprint_queue(previous)


def _controller():
    repo = MagicMock()
    repo.exists.return_value = False
    factory = MagicMock()
    factory.fingerprints = repo
    controller = MagicMock()
    controller._get_repository_factory = MagicMock(return_value=factory)
    controller._send_fingerprint_progress = AsyncMock()
    return controller


async def _status(controller, track_id=7):
    await check_or_queue_fingerprint(controller, track_id, websocket=MagicMock())
    return controller._send_fingerprint_progress.await_args.kwargs["status"]


async def test_a_track_that_is_enqueued_reports_queued(queue):
    assert await _status(_controller()) == "queued"
    assert queue.is_pending(7)


async def test_a_track_already_in_the_queue_still_reports_queued(queue):
    queue.enqueue(7)

    assert await _status(_controller()) == "queued"


async def test_a_full_queue_reports_failed_not_queued(queue):
    queue.MAX_QUEUE_SIZE = 1
    queue.enqueue(1)

    assert await _status(_controller()) == "failed"
    assert not queue.is_pending(7)


async def test_no_queue_reports_failed():
    previous = get_fingerprint_queue()
    set_fingerprint_queue(None)
    try:
        assert await _status(_controller()) == "failed"
    finally:
        set_fingerprint_queue(previous)
