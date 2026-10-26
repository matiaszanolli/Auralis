# -*- coding: utf-8 -*-

"""
Tests for ProcessorFactory config-based caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression tests for content-based config hashing (issue #2707).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from core.processor_factory import (
    _PROCESSOR_CACHE_MAX,
    ProcessorCacheKey,
    ProcessorFactory,
)

from auralis.core.config.unified_config import UnifiedConfig


def test_config_hash_identical_for_equal_configs():
    """Two UnifiedConfig objects with same settings must produce the same hash."""
    factory = ProcessorFactory()
    config_a = UnifiedConfig()
    config_b = UnifiedConfig()

    assert id(config_a) != id(config_b)
    assert factory._get_config_hash(config_a) == factory._get_config_hash(config_b)


def test_config_hash_differs_for_different_configs():
    """Configs with different settings must produce different hashes."""
    factory = ProcessorFactory()
    config_a = UnifiedConfig(fft_size=4096)
    config_b = UnifiedConfig(fft_size=2048)

    assert factory._get_config_hash(config_a) != factory._get_config_hash(config_b)


def test_config_hash_none_returns_default():
    """None config must return the sentinel 'default' string."""
    factory = ProcessorFactory()
    assert factory._get_config_hash(None) == "default"


def test_get_or_create_reuses_processor_for_equal_configs():
    """Calling get_or_create twice with equivalent configs must return the same processor."""
    factory = ProcessorFactory()
    config_a = UnifiedConfig()
    config_b = UnifiedConfig()

    processor_a = factory.get_or_create(track_id=0, config=config_a)
    processor_b = factory.get_or_create(track_id=0, config=config_b)

    assert processor_a is processor_b
    assert len(factory._processor_cache) == 1


def test_factory_does_not_mutate_caller_owned_config():
    factory = ProcessorFactory()
    config = UnifiedConfig()
    config.mastering_profile = "gentle"

    with patch("auralis.core.hybrid_processor.HybridProcessor") as processor_cls:
        factory.get_or_create(preset="bright", config=config)

    owned_config = processor_cls.call_args.args[0]
    assert owned_config is not config
    assert owned_config.mastering_profile == "bright"
    assert config.mastering_profile == "gentle"


def test_different_cold_keys_construct_without_global_lock_serialization():
    factory = ProcessorFactory()
    first_started = threading.Event()
    release_first = threading.Event()

    def create(config):
        if config.mastering_profile == "first":
            first_started.set()
            assert release_first.wait(timeout=2.0)
        return MagicMock(name=f"processor-{config.mastering_profile}")

    with patch("auralis.core.hybrid_processor.HybridProcessor", side_effect=create):
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(factory.get_or_create, preset="first")
            assert first_started.wait(timeout=1.0)
            second_future = executor.submit(factory.get_or_create, preset="second")
            try:
                second = second_future.result(timeout=0.5)
            finally:
                release_first.set()
            first = first_future.result(timeout=1.0)

    assert first is not second


def test_same_cold_key_keeps_one_processor_and_closes_race_loser():
    factory = ProcessorFactory()
    construction_barrier = threading.Barrier(2)
    created: list[MagicMock] = []
    created_lock = threading.Lock()

    def create(_config):
        processor = MagicMock(name="racing-processor")
        with created_lock:
            created.append(processor)
        construction_barrier.wait(timeout=1.0)
        return processor

    with patch("auralis.core.hybrid_processor.HybridProcessor", side_effect=create):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(factory.get_or_create, preset="adaptive")
                for _ in range(2)
            ]
            first, second = [future.result(timeout=2.0) for future in futures]

    assert first is second
    assert list(factory._processor_cache.values()) == [first]
    assert len(created) == 2
    loser = next(processor for processor in created if processor is not first)
    loser.close.assert_called_once()
    first.close.assert_not_called()


# ---------------------------------------------------------------------------
# mastering_targets in the cache key (#3720) — the whole replacement for the
# deleted set_mastering_targets() setter (#4618)
# ---------------------------------------------------------------------------

def test_different_mastering_targets_get_distinct_processors():
    """#4618: distinct targets land in distinct cache entries, so no caller ever
    needs to mutate a cached processor in place (which raced with an in-flight
    process_chunk on the same instance)."""
    factory = ProcessorFactory()

    processor_a = factory.get_or_create(track_id=1, mastering_targets={"lufs": -14.0})
    processor_b = factory.get_or_create(track_id=1, mastering_targets={"lufs": -9.0})

    assert processor_a is not processor_b
    assert len(factory._processor_cache) == 2

    # Identical targets still hit the same entry.
    assert factory.get_or_create(track_id=1, mastering_targets={"lufs": -14.0}) is processor_a
    assert len(factory._processor_cache) == 2


def _factory_building(*processors):
    """A ProcessorFactory whose HybridProcessor constructor yields ``processors`` in order."""
    return ProcessorFactory(), patch(
        "auralis.core.hybrid_processor.HybridProcessor", side_effect=list(processors)
    )


def test_two_unreleased_leases_of_one_key_are_distinct_instances():
    """#6091: two live streams of the same track must not share a HybridProcessor."""
    first, second = MagicMock(name="stream-a"), MagicMock(name="stream-b")
    factory, builder = _factory_building(first, second)

    with builder:
        assert factory.acquire(track_id=7, preset="adaptive") is first
        assert factory.acquire(track_id=7, preset="adaptive") is second


def test_a_released_lease_is_reused_by_the_next_stream():
    """A single stream keeps one instance, and a later stream of the same track
    gets the warm one back once the first has released it."""
    first = MagicMock(name="stream-a")
    factory, builder = _factory_building(first)

    with builder:
        leased = factory.acquire(track_id=7, preset="adaptive")
        factory.release_lease(leased, track_id=7, preset="adaptive")
        assert factory.acquire(track_id=7, preset="adaptive") is first

    first.close.assert_not_called()


def test_a_lease_is_exclusive_while_held():
    first = MagicMock(name="stream-a")
    factory, builder = _factory_building(first)

    with builder:
        factory.acquire(track_id=7, preset="adaptive")

    assert factory._processor_cache == {}
    assert factory.active_processors == {7: first}


def test_discarded_lease_is_closed_and_never_returned_to_the_cache():
    """Replaces the old invalidate(): an advanced processor (#5274, DSP timeout
    #5335) is dropped, so the retry's lease is a fresh instance."""
    advanced, fresh = MagicMock(name="advanced-processor"), MagicMock(name="fresh-processor")
    factory, builder = _factory_building(advanced, fresh)

    with builder:
        leased = factory.acquire(track_id=7, preset="warm")
        factory.discard_lease(leased, track_id=7)
        assert factory.acquire(track_id=7, preset="warm") is fresh

    advanced.close.assert_called_once()
    fresh.close.assert_not_called()
    assert factory._processor_cache == {}


def test_overlapping_same_key_releases_keep_the_last_and_close_the_other():
    a, b = MagicMock(name="stream-a"), MagicMock(name="stream-b")
    factory, builder = _factory_building(a, b)

    with builder:
        lease_a = factory.acquire(track_id=7, preset="adaptive")
        lease_b = factory.acquire(track_id=7, preset="adaptive")
        factory.release_lease(lease_a, track_id=7, preset="adaptive")
        factory.release_lease(lease_b, track_id=7, preset="adaptive")

    assert len(factory._processor_cache) == 1
    assert list(factory._processor_cache.values()) == [b]
    a.close.assert_called_once()
    b.close.assert_not_called()


def test_release_respects_the_lru_cap_and_closes_the_evicted():
    procs = [MagicMock(name=f"p{i}") for i in range(3)]
    factory = ProcessorFactory(max_cached=2)

    with patch("auralis.core.hybrid_processor.HybridProcessor", side_effect=procs):
        leases = [factory.acquire(track_id=i + 1, preset="adaptive") for i in range(3)]
        for i, leased in enumerate(leases):
            factory.release_lease(leased, track_id=i + 1, preset="adaptive")

    assert len(factory._processor_cache) == 2
    procs[0].close.assert_called_once()
    procs[2].close.assert_not_called()


def test_racy_set_mastering_targets_setter_is_gone():
    """#4618: the deprecated in-place setter must not come back. It looked up the
    OLD-shape key (targets_hash="none") and mutated that shared processor."""
    assert not hasattr(ProcessorFactory, "set_mastering_targets")


# ---------------------------------------------------------------------------
# close() on eviction / cleanup (#3746 — thread-pool leak)
# ---------------------------------------------------------------------------
#
# HybridProcessor.fingerprint_analyzer owns a 5-thread executor. Dropping a
# cached HybridProcessor reference without calling close() leaked those
# threads indefinitely. Every path that removes a processor from
# ProcessorFactory's cache must now call close() on it first.

def _make_key(i: int) -> ProcessorCacheKey:
    # #4707: intensity is no longer a key field — it never reached the
    # constructed processor.
    return ProcessorCacheKey(track_id=i, preset="adaptive", config_hash=f"hash_{i}", targets_hash="none")


def test_lru_eviction_closes_evicted_processor():
    """Exceeding the cache cap must call close() on the LRU-evicted processor."""
    factory = ProcessorFactory()
    mock_processors = [MagicMock(name=f"processor_{i}") for i in range(_PROCESSOR_CACHE_MAX + 1)]

    with patch('auralis.core.hybrid_processor.HybridProcessor', side_effect=mock_processors), \
         patch.object(UnifiedConfig, 'set_processing_mode'):
        for i in range(_PROCESSOR_CACHE_MAX + 1):
            factory.get_or_create(track_id=i, preset="adaptive", intensity=1.0, config=UnifiedConfig())

    # First-created (oldest, LRU) must have been evicted and closed.
    mock_processors[0].close.assert_called_once()
    for surviving in mock_processors[1:]:
        surviving.close.assert_not_called()
    assert len(factory._processor_cache) == _PROCESSOR_CACHE_MAX


def test_clear_cache_closes_all_processors():
    """clear_cache() must call close() on every cached processor before clearing."""
    factory = ProcessorFactory()
    mock_processors = [MagicMock(name=f"processor_{i}") for i in range(3)]
    for i, proc in enumerate(mock_processors):
        factory._processor_cache[_make_key(i)] = proc

    factory.clear_cache()

    for proc in mock_processors:
        proc.close.assert_called_once()
    assert len(factory._processor_cache) == 0
