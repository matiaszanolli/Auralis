"""
Regression tests: the proactive buffer and the live stream write the same durable
chunk key with the same provenance (#6090).

The buffer used to skip any chunk whose file existed (so a cache hit never reached
the level manager, and chunk 1 was then smoothed against a cold baseline) and
rendered chunk 0 with ``fast_start=False`` while the live stream uses ``True``, so
the persisted chunk 0/1 bytes depended on which writer won the startup race.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import proactive_buffer
from core.chunk_stream_state import fast_start_for


class _FakeChunkedProcessor:
    """Records process_chunk_safe calls; chunks in ``cached`` model a hit that
    only process_chunk_safe turns into a recorded level."""

    instances: list["_FakeChunkedProcessor"] = []

    def __init__(self, **kwargs) -> None:
        self.cached: set[int] = set(getattr(_FakeChunkedProcessor, "preset_cached", ()))
        self.calls: list[tuple[int, bool]] = []
        self.levels_recorded: list[int] = []
        self.closed = False
        _FakeChunkedProcessor.instances.append(self)

    def _get_chunk_path(self, chunk_idx: int) -> Path:
        raise AssertionError("the buffer must not probe the chunk path itself (.exists() shortcut)")

    async def process_chunk_safe(self, chunk_idx: int, fast_start: bool = False):
        self.calls.append((chunk_idx, fast_start))
        if chunk_idx in self.cached:  # cache hit: level restored from the file
            self.levels_recorded.append(chunk_idx)
        else:  # a miss renders and records too; chunk N-1's level must already be there
            assert chunk_idx == 0 or chunk_idx - 1 in self.levels_recorded
            self.levels_recorded.append(chunk_idx)
        return f"/cache/{chunk_idx}.wav", object()

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _fake_processor():
    _FakeChunkedProcessor.instances = []
    _FakeChunkedProcessor.preset_cached = ()
    with patch("core.chunked_processor.ChunkedAudioProcessor", _FakeChunkedProcessor):
        yield


async def _run(chunks: int = 3) -> _FakeChunkedProcessor:
    ok = await proactive_buffer._buffer_one_preset(
        "adaptive", 1, "/music/a.flac", 1.0, chunks, None, lambda: False
    )
    assert ok is True
    return _FakeChunkedProcessor.instances[-1]


def test_fast_start_rule_is_the_live_streams():
    assert fast_start_for(0) is True
    assert fast_start_for(1) is False
    assert fast_start_for(2) is False


@pytest.mark.asyncio
async def test_every_chunk_goes_through_process_chunk_safe_with_the_live_fast_start_rule():
    proc = await _run()

    assert proc.calls == [(0, True), (1, False), (2, False)]


@pytest.mark.asyncio
async def test_an_already_written_chunk_zero_is_still_recorded_before_chunk_one_renders():
    _FakeChunkedProcessor.preset_cached = (0,)

    proc = await _run()

    # chunk 0 was a hit, yet its level is recorded ahead of chunk 1's render
    # (the fake asserts that ordering inside process_chunk_safe).
    assert proc.levels_recorded[:2] == [0, 1]
    assert proc.calls[0] == (0, True)


@pytest.mark.asyncio
async def test_the_buffer_processor_is_still_released():
    proc = await _run()

    assert proc.closed is True
