"""
A timed-out chunk render must not leave its processor cached (#5059)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`asyncio.wait_for` cancels only the awaiting side of `process_chunk_safe`;
the thread doing the render keeps running inside the processor. The worker
used to keep that processor in `_processor_cache`, so the next 1 Hz tick got
the still-busy instance back. It is now evicted on timeout and closed only
once the orphaned render has finished.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import streamlined_worker
from core.streamlined_worker import StreamlinedCacheWorker
from core.file_signature import FileSignatureService

TRACK_ID = 7
# The cache key now includes file_signature (#5349); track.filepath below is
# always set to __file__ ("any file that exists"), so its signature is
# computed once here to match.
KEY = (TRACK_ID, "adaptive", 0.5, FileSignatureService.generate(__file__))


class _Processor:
    """A ChunkedAudioProcessor stand-in whose first render can be held open."""

    def __init__(self, release: asyncio.Event | None) -> None:
        self.release = release
        self.file_signature = "sig"
        self.close = Mock()
        self.render_cancelled = False

    async def process_chunk_safe(self, chunk_idx: int) -> tuple[str, None]:
        if self.release is not None:
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.render_cancelled = True
                raise
        return (f"/tmp/chunk_{chunk_idx}.wav", None)


@pytest.fixture
def worker() -> StreamlinedCacheWorker:
    cache_manager = Mock()
    cache_manager.add_chunk = AsyncMock(return_value=True)
    return StreamlinedCacheWorker(cache_manager, Mock())


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> list[_Processor]:
    """Every processor the worker builds; the first one hangs until released."""
    release = asyncio.Event()
    created: list[_Processor] = []

    def build(**_kwargs: Any) -> _Processor:
        created.append(_Processor(release if not created else None))
        return created[-1]

    monkeypatch.setattr("core.chunked_processor.ChunkedAudioProcessor", build)
    monkeypatch.setattr(streamlined_worker, "_CHUNK_TIMEOUT_SECONDS", {"tier1": 0.05, "tier2": 0.05})
    return created


async def _process(worker: StreamlinedCacheWorker, chunk_idx: int) -> str | None:
    track = Mock(filepath=__file__)  # any file that exists
    return await worker._process_chunk(track, TRACK_ID, chunk_idx, "adaptive", 0.5, "tier1")


class TestTimeoutEviction:

    async def test_timeout_evicts_and_the_next_chunk_gets_a_new_processor(
        self, worker: StreamlinedCacheWorker, built: list[_Processor]
    ) -> None:
        assert await _process(worker, 0) is None
        assert KEY not in worker._processor_cache
        assert KEY not in worker._processor_build_locks

        assert await _process(worker, 1) == "/tmp/chunk_1.wav"
        assert len(built) == 2
        assert worker._processor_cache[KEY] is built[1]

    async def test_evicted_processor_is_closed_only_after_its_render_ends(
        self, worker: StreamlinedCacheWorker, built: list[_Processor]
    ) -> None:
        await _process(worker, 0)
        hung = built[0]
        assert hung.release is not None

        await asyncio.sleep(0)
        hung.close.assert_not_called()

        hung.release.set()
        for _ in range(5):
            await asyncio.sleep(0)
        hung.close.assert_called_once_with()
        assert not hung.render_cancelled

    async def test_worker_cancellation_still_cancels_the_render(
        self, worker: StreamlinedCacheWorker, built: list[_Processor], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(streamlined_worker, "_CHUNK_TIMEOUT_SECONDS", {"tier1": 30, "tier2": 30})
        task = asyncio.ensure_future(_process(worker, 0))
        for _ in range(5):
            await asyncio.sleep(0)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(5):
            await asyncio.sleep(0)

        assert built[0].render_cancelled
        # Not a timeout, so the processor stays cached for reuse (#2737).
        assert worker._processor_cache[KEY] is built[0]
