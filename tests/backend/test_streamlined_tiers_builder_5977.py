"""The Tier-2 builder retries failed chunks, builds only processed renders, logs completion once (#5975, #5977)."""

import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache.models import TrackCacheStatus  # noqa: E402
from core import streamlined_tiers  # noqa: E402
from core.streamlined_worker import StreamlinedCacheWorker  # noqa: E402


class _FakeCache:
    def __init__(self, total_chunks: int) -> None:
        self.status = TrackCacheStatus(track_id=1, total_chunks=total_chunks)

    def get_track_cache_status(self, track_id):
        return self.status

    def is_track_fully_cached(self, track_id):
        return self.status.is_fully_cached()


def _worker(total_chunks: int, outcomes: dict[int, list[bool]]):
    """A real worker whose _process_chunk succeeds/fails per the scripted outcomes."""
    worker = StreamlinedCacheWorker(_FakeCache(total_chunks), MagicMock())
    worker.calls = []  # type: ignore[attr-defined]

    async def process_chunk(track, track_id, chunk_idx, preset, intensity, tier):
        worker.calls.append((chunk_idx, preset))  # type: ignore[attr-defined]
        queue = outcomes.get(chunk_idx, [True])
        ok = queue.pop(0) if len(queue) > 1 else queue[0]
        if ok:
            worker.cache_manager.status.cached_chunks_processed.add(chunk_idx)
            return Path(f"/tmp/chunk_{chunk_idx}.wav")
        return None

    worker._process_chunk = process_chunk  # type: ignore[method-assign]
    return worker


async def _drain(worker, ticks: int) -> None:
    for _ in range(ticks):
        await streamlined_tiers.build_tier2_cache(worker, SimpleNamespace(), 1, "adaptive", 1.0)


@pytest.mark.asyncio
async def test_a_failed_chunk_is_retried_not_skipped():
    worker = _worker(3, {1: [False, True]})
    await _drain(worker, 4)

    assert worker.cache_manager.status.is_fully_cached()
    assert [c for c, _ in worker.calls].count(1) == 2


@pytest.mark.asyncio
async def test_a_chunk_that_keeps_failing_is_given_up_after_the_cap():
    worker = _worker(3, {1: [False]})
    await _drain(worker, 10)

    assert [c for c, _ in worker.calls].count(1) == streamlined_tiers.MAX_CHUNK_ATTEMPTS
    assert 2 in worker.cache_manager.status.cached_chunks_processed  # later chunks still built
    assert not worker.cache_manager.status.is_fully_cached()


@pytest.mark.asyncio
async def test_only_processed_renders_are_built_and_the_track_completes(caplog):
    worker = _worker(3, {})
    with caplog.at_level(logging.INFO):
        await _drain(worker, 8)

    assert {preset for _, preset in worker.calls} == {"adaptive"}  # never preset=None
    assert worker.cache_manager.status.is_fully_cached()
    assert sum("Tier 2 cache complete" in r.message for r in caplog.records) == 1


@pytest.mark.asyncio
async def test_no_completion_log_for_a_track_that_is_not_fully_cached(caplog):
    worker = _worker(2, {0: [False]})
    with caplog.at_level(logging.INFO):
        await _drain(worker, 8)

    assert not worker.cache_manager.status.is_fully_cached()
    assert not any("Tier 2 cache complete" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_tier1_never_renders_an_unprocessed_chunk(monkeypatch, tmp_path):
    worker = _worker(3, {})
    monkeypatch.setattr(streamlined_tiers.FileSignatureService, "generate", staticmethod(lambda path: "sig"))

    async def get_chunk(*args, **kwargs):
        return None, "miss"

    async def warm(**kwargs):
        worker.warmed = kwargs["chunk_paths"]  # type: ignore[attr-defined]
        return len(kwargs["chunk_paths"])

    worker.cache_manager.get_chunk = get_chunk
    worker.cache_manager.warm_tier1_immediately = warm
    track = SimpleNamespace(filepath=str(tmp_path / "x.flac"))

    await streamlined_tiers.ensure_tier1_chunk(worker, track, 1, 0, "adaptive", 1.0)

    assert worker.calls == [(0, "adaptive")]
    assert [preset for _, _, preset in worker.warmed] == ["adaptive"]  # type: ignore[attr-defined]
