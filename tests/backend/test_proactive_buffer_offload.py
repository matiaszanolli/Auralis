"""
Regression tests for proactive_buffer event-loop offloading (#3853)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`buffer_presets_for_track` constructs a ChunkedAudioProcessor per preset.
The constructor is sync and slow (SoundFile open + fingerprint load +
HybridProcessor init, ~200-500 ms each). Building it directly in the async
function stalled the event loop for up to ~2.5 s across 5 presets. The fix
wraps construction in `asyncio.to_thread`, so it runs on a worker thread and
the loop stays responsive.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.proactive_buffer import AVAILABLE_PRESETS, buffer_presets_for_track


def _fake_processor_factory(record_threads, block_seconds=0.0):
    """Build a fake ChunkedAudioProcessor ctor that records its thread and
    optionally blocks (to simulate slow sync construction)."""

    def _ctor(**kwargs):
        record_threads.append(threading.current_thread())
        if block_seconds:
            time.sleep(block_seconds)  # blocking, like the real sync ctor
        inst = Mock()
        # Make every chunk look already-cached so the loop skips processing
        # and the test stays focused on construction offloading.
        cached_path = Mock()
        cached_path.exists.return_value = True
        inst._get_chunk_path.return_value = cached_path
        inst.close = Mock()
        return inst

    return _ctor


class TestProactiveBufferOffload:
    @pytest.mark.asyncio
    async def test_constructor_runs_off_event_loop_thread(self, monkeypatch):
        """Each ChunkedAudioProcessor is built on a worker thread (to_thread)."""
        main_thread = threading.current_thread()
        seen_threads: list[threading.Thread] = []

        monkeypatch.setattr(
            "core.chunked_processor.ChunkedAudioProcessor",
            _fake_processor_factory(seen_threads),
        )

        await buffer_presets_for_track(track_id=1, filepath="/fake.wav", total_chunks=1)

        # One construction per preset, all off the main (event-loop) thread.
        assert len(seen_threads) == len(AVAILABLE_PRESETS)
        assert all(t is not main_thread for t in seen_threads), (
            "ChunkedAudioProcessor must be constructed via asyncio.to_thread, "
            "not directly on the event-loop thread"
        )

    @pytest.mark.asyncio
    async def test_event_loop_stays_responsive_during_construction(self, monkeypatch):
        """A concurrent coroutine keeps ticking while constructors block."""
        seen_threads: list[threading.Thread] = []
        # Each ctor blocks 100ms; 5 presets = ~0.5s of blocking work total.
        monkeypatch.setattr(
            "core.chunked_processor.ChunkedAudioProcessor",
            _fake_processor_factory(seen_threads, block_seconds=0.1),
        )

        ticks = 0

        async def _ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        ticker_task = asyncio.create_task(_ticker())
        try:
            await buffer_presets_for_track(track_id=1, filepath="/fake.wav", total_chunks=1)
        finally:
            ticker_task.cancel()
            try:
                await ticker_task
            except asyncio.CancelledError:
                pass

        # If construction blocked the loop (~0.5s), the ticker would barely
        # advance. With to_thread offloading it ticks freely (~50 times in
        # 0.5s). A conservative floor proves the loop was not frozen.
        assert ticks >= 10, (
            f"Event loop appeared blocked during construction (only {ticks} ticks); "
            "constructor is likely running on the event-loop thread"
        )
