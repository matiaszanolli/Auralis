"""
Tests for StreamlinedCacheWorker processor reuse (issue #2737)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that the same ChunkedAudioProcessor instance is reused across
chunks for a given (track_id, preset, intensity), so DSP state (compressor
envelope, EQ history) is preserved at chunk boundaries.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.streamlined_worker import StreamlinedCacheWorker


@pytest.fixture
def mock_cache_manager():
    """Create a mock StreamlinedCacheManager"""
    cm = Mock()
    cm.current_track_id = 1
    cm.current_position = 0.0
    cm.current_preset = "balanced"
    cm.intensity = 0.5
    cm.auto_mastering_enabled = True
    cm._get_current_chunk = Mock(return_value=0)
    cm.is_track_fully_cached = Mock(return_value=False)
    cm.add_chunk = AsyncMock(return_value=True)
    cm.warm_tier1_immediately = AsyncMock()
    cm.get_chunk = AsyncMock(return_value=(None, None))

    status = Mock()
    status.total_chunks = 3
    status.cached_chunks_original = set()
    status.cached_chunks_processed = set()
    cm.get_track_cache_status = Mock(return_value=status)
    return cm


@pytest.fixture
def mock_library_manager():
    """Create a mock LibraryManager"""
    lm = Mock()
    track = Mock()
    track.filepath = "/tmp/test_track.wav"
    lm.tracks.get_by_id = Mock(return_value=track)
    return lm


@pytest.fixture
def worker(mock_cache_manager, mock_library_manager):
    return StreamlinedCacheWorker(mock_cache_manager, mock_library_manager)


class TestProcessorReuse:
    """Verify processor instances are reused across chunks (fixes #2737)"""

    @pytest.mark.asyncio
    async def test_same_processor_used_for_all_chunks(self, worker):
        """Building cache for 3 chunks should use the same processor instance"""
        created_processors = []

        with patch("core.streamlined_worker.Path") as mock_path, \
             patch("core.chunked_processor.ChunkedAudioProcessor") as MockProcessor:

            mock_path.return_value.exists.return_value = True

            mock_proc_instance = Mock()
            mock_proc_instance.process_chunk_safe = AsyncMock(
                return_value=("/tmp/chunk.wav", None)
            )
            MockProcessor.return_value = mock_proc_instance

            # Track every call to ChunkedAudioProcessor constructor
            def track_creation(*args, **kwargs):
                inst = Mock()
                inst.process_chunk_safe = AsyncMock(
                    return_value=("/tmp/chunk.wav", None)
                )
                created_processors.append(inst)
                return inst

            MockProcessor.side_effect = track_creation

            track = Mock()
            track.filepath = "/tmp/test.wav"

            # Process 3 chunks with the same (track_id, preset, intensity)
            for chunk_idx in range(3):
                await worker._process_chunk(
                    track, track_id=1, chunk_idx=chunk_idx,
                    preset="balanced", intensity=0.5, tier="tier2"
                )

            # Only one processor should have been created
            assert len(created_processors) == 1
            # And it should have been called 3 times
            assert created_processors[0].process_chunk_safe.await_count == 3

    @pytest.mark.asyncio
    async def test_different_preset_gets_different_processor(self, worker):
        """Different presets should use different processor instances"""
        created_processors = []

        with patch("core.streamlined_worker.Path") as mock_path, \
             patch("core.chunked_processor.ChunkedAudioProcessor") as MockProcessor:

            mock_path.return_value.exists.return_value = True

            def track_creation(*args, **kwargs):
                inst = Mock()
                inst.process_chunk_safe = AsyncMock(
                    return_value=("/tmp/chunk.wav", None)
                )
                created_processors.append(inst)
                return inst

            MockProcessor.side_effect = track_creation

            track = Mock()
            track.filepath = "/tmp/test.wav"

            # Process with preset "balanced"
            await worker._process_chunk(
                track, track_id=1, chunk_idx=0,
                preset="balanced", intensity=0.5, tier="tier2"
            )
            # Process with preset=None (original)
            await worker._process_chunk(
                track, track_id=1, chunk_idx=0,
                preset=None, intensity=0.5, tier="tier2"
            )

            # Two different presets → two processor instances
            assert len(created_processors) == 2

    @pytest.mark.asyncio
    async def test_track_change_evicts_old_processors(self, worker):
        """Changing tracks should evict processors for the old track"""
        with patch("core.streamlined_worker.Path") as mock_path, \
             patch("core.chunked_processor.ChunkedAudioProcessor") as MockProcessor:

            mock_path.return_value.exists.return_value = True

            MockProcessor.side_effect = lambda **kw: Mock(
                process_chunk_safe=AsyncMock(return_value=("/tmp/chunk.wav", None))
            )

            track = Mock()
            track.filepath = "/tmp/test.wav"

            # Populate cache for track 1
            await worker._process_chunk(
                track, track_id=1, chunk_idx=0,
                preset="balanced", intensity=0.5, tier="tier2"
            )
            assert (1, "balanced", 0.5) in worker._processor_cache

            # Simulate track change via _build_tier2_cache state reset
            worker._building_track_id = 1  # was building track 1
            # Now building track 2 triggers eviction
            status = Mock()
            status.total_chunks = 0
            status.cached_chunks_original = set()
            status.cached_chunks_processed = set()
            worker.cache_manager.get_track_cache_status = Mock(return_value=status)
            worker.cache_manager.is_track_fully_cached = Mock(return_value=False)

            await worker._build_tier2_cache(track, track_id=2, current_chunk=0,
                                            preset="balanced", intensity=0.5)

            # Old track's processor should be evicted
            assert (1, "balanced", 0.5) not in worker._processor_cache


class TestProcessorConstructionOffload:
    """Regression tests for #3817: ChunkedAudioProcessor's blocking
    constructor (sync SoundFile open, DB fingerprint lookup, HybridProcessor
    construction — 200-500ms) must run via asyncio.to_thread, not directly
    on the event loop. The worker loop ticks every 1s, so an inline
    construction on a cache miss stalls in-flight stream chunk sends for the
    whole duration."""

    @pytest.mark.asyncio
    async def test_processor_construction_does_not_block_event_loop(self, worker):
        import time

        def slow_constructor(**kwargs):
            time.sleep(0.3)  # simulates SoundFile open + DB lookup + HybridProcessor init
            inst = Mock()
            inst.process_chunk_safe = AsyncMock(return_value=("/tmp/chunk.wav", None))
            return inst

        with patch("core.streamlined_worker.Path") as mock_path, \
             patch("core.chunked_processor.ChunkedAudioProcessor") as MockProcessor:
            mock_path.return_value.exists.return_value = True
            MockProcessor.side_effect = slow_constructor

            track = Mock()
            track.filepath = "/tmp/test.wav"

            # A concurrent task that should tick every ~30ms if the event
            # loop stays responsive while the processor is "constructing".
            ticks: list[float] = []

            async def tick_counter() -> None:
                for _ in range(10):
                    ticks.append(time.monotonic())
                    await asyncio.sleep(0.03)

            counter_task = asyncio.create_task(tick_counter())

            await worker._process_chunk(
                track, track_id=1, chunk_idx=0,
                preset="balanced", intensity=0.5, tier="tier2"
            )
            await counter_task

            gaps = [b - a for a, b in zip(ticks, ticks[1:])]
            assert max(gaps) < 0.15, (
                f"largest gap between event-loop ticks was {max(gaps):.3f}s "
                "while ChunkedAudioProcessor was constructing — the event "
                "loop was blocked (construction must run via asyncio.to_thread)"
            )

    @pytest.mark.asyncio
    async def test_cached_processor_path_still_skips_construction(self, worker):
        """Sanity check: the offload change must not affect the reuse path
        (#2737) — a cached processor should never re-invoke the constructor."""
        with patch("core.streamlined_worker.Path") as mock_path, \
             patch("core.chunked_processor.ChunkedAudioProcessor") as MockProcessor:
            mock_path.return_value.exists.return_value = True

            mock_instance = Mock()
            mock_instance.process_chunk_safe = AsyncMock(return_value=("/tmp/chunk.wav", None))
            MockProcessor.return_value = mock_instance

            track = Mock()
            track.filepath = "/tmp/test.wav"

            await worker._process_chunk(
                track, track_id=1, chunk_idx=0,
                preset="balanced", intensity=0.5, tier="tier2"
            )
            await worker._process_chunk(
                track, track_id=1, chunk_idx=1,
                preset="balanced", intensity=0.5, tier="tier2"
            )

            assert MockProcessor.call_count == 1
