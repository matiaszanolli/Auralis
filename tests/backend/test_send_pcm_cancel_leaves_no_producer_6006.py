"""Cancelling send_pcm_chunk mid-chunk must not leave its producer task parked (#6006).

The producer's ``finally: await queue.put(None)`` blocked forever on the still-full queue once the
consumer had been cancelled, so the task and its queued frames survived until a GC cycle collected it.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import AudioStreamController, _frame_seq_var
from core.stream_protocol import send_pcm_chunk


def _producers() -> list[asyncio.Task]:
    return [
        t for t in asyncio.all_tasks()
        if getattr(t.get_coro(), "__qualname__", "") == "send_pcm_chunk.<locals>._producer" and not t.done()
    ]


async def test_cancelling_a_slow_send_leaves_no_parked_producer():
    controller = AudioStreamController()
    release = asyncio.Event()

    async def slow_send(_ws, _message):
        await release.wait()  # the client is slow: the consumer parks, the queue fills
        return True

    controller._safe_send = slow_send  # type: ignore[assignment]
    controller._safe_send_bytes = AsyncMock(return_value=True)  # type: ignore[assignment]
    _frame_seq_var.set([0])
    pcm = np.zeros(76_800 * 12, dtype=np.float32)  # 12 frames: more than the queue holds

    task = asyncio.ensure_future(send_pcm_chunk(controller, object(), pcm, 0, 1))  # type: ignore[arg-type]
    await asyncio.sleep(0.05)  # the queue is full, the producer is parked in put()
    assert _producers()

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    for _ in range(5):
        await asyncio.sleep(0)

    assert _producers() == []


async def test_a_normal_send_still_completes_and_returns_true():
    controller = AudioStreamController()
    controller._safe_send = AsyncMock(return_value=True)  # type: ignore[assignment]
    controller._safe_send_bytes = AsyncMock(return_value=True)  # type: ignore[assignment]
    _frame_seq_var.set([0])

    sent = await send_pcm_chunk(controller, object(), np.zeros(76_800 * 6, dtype=np.float32), 0, 1)  # type: ignore[arg-type]

    assert sent is True
    assert controller._safe_send.await_count == 6
