"""
Live streams and background chunk builders never share a HybridProcessor (#5311)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A HybridProcessor carries EQ, limiter and dynamics state from one process()
call to the next. The proactive buffer and the Tier-2 cache worker used to
resolve the same ProcessorFactory key as the live stream on the same track, so
all three fed chunks into one instance out of order. Each consumer now has its
own factory.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections import OrderedDict
from types import SimpleNamespace

import pytest

from core import processor_factory as pf

BACKGROUND = (pf.PROACTIVE_BUFFER_CONSUMER, pf.CACHE_WORKER_CONSUMER)


class _FakeProcessor:
    def __init__(self, config):
        self.config = config

    def set_fixed_mastering_targets(self, targets):
        self.targets = targets

    def close(self):
        pass


@pytest.fixture
def fresh_factories(monkeypatch):
    monkeypatch.setattr(pf, "_processor_factories", {})
    monkeypatch.setattr("auralis.core.hybrid_processor.HybridProcessor", _FakeProcessor)


def test_each_consumer_has_its_own_factory(fresh_factories):
    stream = pf.get_processor_factory()

    assert pf.get_processor_factory(pf.STREAM_CONSUMER) is stream
    factories = [stream] + [pf.get_processor_factory(c) for c in BACKGROUND]
    assert len({id(f) for f in factories}) == 3
    assert {id(f) for f in pf.all_processor_factories()} == {id(f) for f in factories}


def test_one_key_resolves_to_a_distinct_processor_per_consumer(fresh_factories):
    key = dict(track_id=7, preset="adaptive", mastering_targets={"target_lufs": -14.0})

    live = pf.get_processor_factory().get_or_create(**key)
    background = [pf.get_processor_factory(c).get_or_create(**key) for c in BACKGROUND]

    assert len({id(live), *(id(p) for p in background)}) == 3
    # Each consumer still keeps ONE instance across its own chunks.
    assert pf.get_processor_factory().get_or_create(**key) is live
    for consumer, processor in zip(BACKGROUND, background):
        assert pf.get_processor_factory(consumer).get_or_create(**key) is processor


@pytest.mark.parametrize("consumer", BACKGROUND)
def test_background_factories_keep_a_small_cache(fresh_factories, consumer):
    factory = pf.get_processor_factory(consumer)
    for track_id in range(1, 10):
        factory.get_or_create(track_id=track_id)

    assert factory.get_statistics()["total_cached"] == pf._CONSUMER_CACHE_MAX[consumer]


def _record_construction(monkeypatch, *, raise_after: bool) -> dict:
    captured: dict = {}

    class _Recorder:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            if raise_after:
                raise RuntimeError("stop after construction")

        def close(self):
            pass

    monkeypatch.setattr("core.chunked_processor.ChunkedAudioProcessor", _Recorder)
    return captured


async def test_proactive_buffer_builds_on_its_own_factory(fresh_factories, monkeypatch):
    from core.proactive_buffer import buffer_presets_for_track

    captured = _record_construction(monkeypatch, raise_after=True)
    await buffer_presets_for_track(1, "/nonexistent.wav", total_chunks=1)

    assert captured["processor_factory"] is pf.get_processor_factory(pf.PROACTIVE_BUFFER_CONSUMER)


async def test_cache_worker_builds_on_its_own_factory(fresh_factories, monkeypatch):
    from core.streamlined_processor_cache import get_or_build_processor

    captured = _record_construction(monkeypatch, raise_after=False)
    worker = SimpleNamespace(
        _processor_cache=OrderedDict(), _processor_build_locks={}, _build_waiters={}
    )
    worker._remember_processor = lambda key, proc: worker._processor_cache.__setitem__(key, proc)

    await get_or_build_processor(worker, (3, "adaptive", 1.0), "/nonexistent.wav")

    assert captured["processor_factory"] is pf.get_processor_factory(pf.CACHE_WORKER_CONSUMER)
