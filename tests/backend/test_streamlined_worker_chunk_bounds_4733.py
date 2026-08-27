"""Regression tests for bounded StreamlinedCacheWorker chunk requests (#4733)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from cache.manager import PlaybackSnapshot
from core.streamlined_worker import StreamlinedCacheWorker


def _worker(*, current_chunk: int = 2, total_chunks: int = 3):
    cache_manager = Mock()
    cache_manager.current_track_id = 7
    cache_manager.get_playback_snapshot = AsyncMock(
        return_value=PlaybackSnapshot(
            track_id=7,
            position=float(current_chunk * 10),
            chunk_idx=current_chunk,
            preset="adaptive",
            intensity=1.0,
        )
    )
    status = Mock(total_chunks=total_chunks)
    cache_manager.get_track_cache_status = Mock(return_value=status)
    cache_manager.is_track_fully_cached = Mock(return_value=True)

    library_database = Mock()
    library_database.tracks.get_by_id = Mock(return_value=Mock())

    return StreamlinedCacheWorker(cache_manager, library_database)


class TestPriorityPrefetchBounds:
    @pytest.mark.asyncio
    async def test_last_chunk_does_not_prefetch_total_chunks(self, monkeypatch):
        worker = _worker(current_chunk=2, total_chunks=3)
        ensure_tier1 = AsyncMock()
        monkeypatch.setattr(worker, "_ensure_tier1_chunk", ensure_tier1)

        await worker._process_priorities()

        ensure_tier1.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_in_range_next_chunk_is_still_prefetched(self, monkeypatch):
        worker = _worker(current_chunk=1, total_chunks=3)
        ensure_tier1 = AsyncMock()
        monkeypatch.setattr(worker, "_ensure_tier1_chunk", ensure_tier1)

        await worker._process_priorities()

        ensure_tier1.assert_awaited_once()
        assert ensure_tier1.await_args.args[2] == 2


class TestImmediateProcessingBounds:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("chunk_index", [-1, 3])
    async def test_out_of_range_request_is_rejected_before_track_lookup(
        self, monkeypatch, chunk_index
    ):
        worker = _worker(total_chunks=3)
        process_chunk = AsyncMock()
        monkeypatch.setattr(worker, "_process_chunk", process_chunk)

        result = await worker.trigger_immediate_processing(
            track_id=7,
            chunk_idx=chunk_index,
            preset="adaptive",
            intensity=1.0,
        )

        assert result is False
        worker.library_database.tracks.get_by_id.assert_not_called()
        process_chunk.assert_not_awaited()


class TestImmediateProcessingReportsActualOutcome:
    """#5063: trigger_immediate_processing used to return True unconditionally
    after awaiting _process_chunk, even though _process_chunk swallows every
    failure (timeout, FileNotFoundError, PermissionError, catch-all) and
    returns None rather than raising — so the caller could never tell "chunk
    cached" from "chunk failed to build"."""

    @pytest.mark.asyncio
    async def test_returns_false_when_process_chunk_reports_failure(self, monkeypatch):
        worker = _worker(current_chunk=1, total_chunks=3)
        monkeypatch.setattr(worker, "_process_chunk", AsyncMock(return_value=None))

        result = await worker.trigger_immediate_processing(
            track_id=7, chunk_idx=1, preset="adaptive", intensity=1.0,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_process_chunk_produces_a_path(self, monkeypatch):
        worker = _worker(current_chunk=1, total_chunks=3)
        monkeypatch.setattr(
            worker, "_process_chunk", AsyncMock(return_value="/tmp/chunk_001.wav")
        )

        result = await worker.trigger_immediate_processing(
            track_id=7, chunk_idx=1, preset="adaptive", intensity=1.0,
        )

        assert result is True
