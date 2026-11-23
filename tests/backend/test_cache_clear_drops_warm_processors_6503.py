"""Clear Cache, per-track clear and library reset reach the warm ProcessorFactory tier (#6503).

Released stream processors are parked in ProcessorFactory._processor_cache with their DSP state
and re-leased by the next stream. The cache clears reached chunk files, thumbnails, the target cache
and the streamlined tiers, but not this tier, so "clear and retry" re-rendered on a warmed
instance, and after a library reset a new track reusing an id inherited another track's state.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import cache_cleanup, processor_registry  # noqa: E402
from core.processor_cache_key import build_cache_key  # noqa: E402
from core.processor_factory import ProcessorFactory  # noqa: E402


@pytest.fixture
def factories(monkeypatch):
    stream, worker = ProcessorFactory(), ProcessorFactory()
    monkeypatch.setattr(processor_registry, "_processor_factories", {"stream": stream, "worker": worker})
    parked = {}
    for factory, track_id in ((stream, 1), (stream, 2), (worker, 1)):
        processor = MagicMock(name=f"track{track_id}")
        factory._processor_cache[build_cache_key(track_id, "adaptive", "cfg", "none")] = processor
        parked.setdefault(track_id, []).append(processor)
    leased = MagicMock(name="leased")
    stream._active_processors[1] = leased  # in use: never in the cache
    return stream, worker, parked, leased


def _cached_tracks(factory):
    return sorted(k.track_id for k in factory._processor_cache)


@pytest.mark.asyncio
async def test_a_track_clear_drops_that_tracks_warm_processors_in_every_factory(factories, tmp_path):
    stream, worker, parked, leased = factories

    await cache_cleanup.clear_track_caches(None, 1, chunk_dir=tmp_path)

    assert _cached_tracks(stream) == [2] and _cached_tracks(worker) == []
    assert all(p.close.called for p in parked[1]) and not parked[2][0].close.called
    assert stream._active_processors[1] is leased and not leased.close.called


@pytest.mark.asyncio
async def test_clear_all_drops_every_warm_processor(factories, tmp_path):
    stream, worker, parked, leased = factories

    await cache_cleanup.clear_all_caches(None, tmp_path / "artwork", chunk_dir=tmp_path)

    assert _cached_tracks(stream) == [] and _cached_tracks(worker) == []
    assert all(p.close.called for ps in parked.values() for p in ps)
    assert stream._active_processors[1] is leased and not leased.close.called
