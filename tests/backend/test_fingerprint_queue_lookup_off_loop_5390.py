"""The fingerprint-queue worker does its repository lookup off the event loop (#5390).

`self._get_filepath(track_id)` is `get_track_filepath`, a synchronous SQLAlchemy
query. Called straight from `_worker_loop` it blocked the event loop for one DB
round-trip per dequeue, stalling WS pause/resume/seek handling while a large scan's
backlog drained. It now runs through asyncio.to_thread.
"""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from analysis.fingerprint_queue import FingerprintQueue  # noqa: E402


@pytest.mark.asyncio
async def test_the_filepath_lookup_runs_in_a_worker_thread():
    loop_thread = threading.get_ident()
    seen: list[int] = []

    def lookup(track_id: int) -> str:
        seen.append(threading.get_ident())
        return f"/music/{track_id}.flac"

    queue = FingerprintQueue(fingerprint_generator=object(), get_track_filepath=lookup)
    queue._generate_one = AsyncMock()  # type: ignore[method-assign]
    queue.enqueue(7)

    worker = asyncio.create_task(queue._worker_loop())
    for _ in range(100):
        if queue._generate_one.await_count:
            break
        await asyncio.sleep(0.01)
    queue._shutdown = True
    await asyncio.wait_for(worker, timeout=2.0)

    queue._generate_one.assert_awaited_once_with(7, "/music/7.flac")
    assert seen and seen[0] != loop_thread, "the lookup ran on the event-loop thread"


@pytest.mark.asyncio
async def test_a_missing_track_is_still_skipped_and_counted_failed():
    queue = FingerprintQueue(fingerprint_generator=object(), get_track_filepath=lambda _id: None)
    queue._generate_one = AsyncMock()  # type: ignore[method-assign]
    queue.enqueue(9)

    worker = asyncio.create_task(queue._worker_loop())
    for _ in range(100):
        if queue._state.failed:
            break
        await asyncio.sleep(0.01)
    queue._shutdown = True
    await asyncio.wait_for(worker, timeout=2.0)

    queue._generate_one.assert_not_awaited()
    assert queue._state.failed == 1 and queue._state.processing is None
