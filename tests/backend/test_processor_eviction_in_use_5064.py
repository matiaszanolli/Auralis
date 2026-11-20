"""An evicted processor is not closed while a render is using it (#5064).

LRU eviction closed the dropped processor immediately, which rmtree's its temp WAV; a render
still running in its thread would then read a file that no longer exists.
"""

import sys
from collections import OrderedDict
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.streamlined_processor_cache import remember_processor  # noqa: E402
from core.streamlined_processor_disposal import close_dropped_processor, leased  # noqa: E402


def _key(n: int):
    return (n, "adaptive", 1.0, "sig")


def test_eviction_during_a_render_defers_the_close_until_it_ends():
    cache: OrderedDict = OrderedDict()
    busy, other = MagicMock(), MagicMock()
    remember_processor(cache, {}, _key(1), busy, max_size=1)

    with leased(busy):
        remember_processor(cache, {}, _key(2), other, max_size=1)  # evicts `busy`
        assert list(cache) == [_key(2)]
        busy.close.assert_not_called()

    busy.close.assert_called_once()
    other.close.assert_not_called()


def test_an_idle_processor_is_still_closed_on_eviction():
    cache: OrderedDict = OrderedDict()
    idle = MagicMock()
    remember_processor(cache, {}, _key(1), idle, max_size=1)
    remember_processor(cache, {}, _key(2), MagicMock(), max_size=1)

    idle.close.assert_called_once()


def test_close_waits_for_the_last_of_several_overlapping_renders():
    cache: OrderedDict = OrderedDict()
    busy = MagicMock()
    remember_processor(cache, {}, _key(1), busy, max_size=1)

    with leased(busy):
        with leased(busy):
            remember_processor(cache, {}, _key(2), MagicMock(), max_size=1)
        busy.close.assert_not_called()  # one render still running

    busy.close.assert_called_once()


def test_a_lease_that_is_never_dropped_does_not_close_a_live_processor():
    live = MagicMock()
    with leased(live):
        pass

    live.close.assert_not_called()


async def test_process_chunk_holds_a_lease_while_the_render_runs(tmp_path, monkeypatch):
    """End to end through the worker: an eviction mid-render waits for the render."""
    import asyncio
    from types import SimpleNamespace

    from core import streamlined_worker as sw

    track_file = tmp_path / "t.wav"
    track_file.write_bytes(b"x")
    started, release = asyncio.Event(), asyncio.Event()

    class _Processor:
        close = MagicMock()

        async def process_chunk_safe(self, chunk_idx):
            started.set()
            await release.wait()
            return None, None

    processor = _Processor()

    async def get_processor(worker, cache_key, filepath):
        return processor

    monkeypatch.setattr(sw, "get_or_build_processor", get_processor)
    worker = sw.StreamlinedCacheWorker(MagicMock(), MagicMock())
    task = asyncio.ensure_future(
        worker._process_chunk(SimpleNamespace(filepath=str(track_file)), 1, 0, "adaptive", 1.0, "tier1")
    )
    await started.wait()

    close_dropped_processor(_key(1), processor)  # what an eviction does mid-render
    processor.close.assert_not_called()

    release.set()
    await task
    processor.close.assert_called_once()
