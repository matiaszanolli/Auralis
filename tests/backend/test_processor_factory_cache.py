# -*- coding: utf-8 -*-

"""
Tests for ProcessorFactory config-based caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression tests for content-based config hashing (issue #2707).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
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


def test_config_mode_selection_does_not_mutate_caller_owned_config():
    factory = ProcessorFactory()
    config = UnifiedConfig()

    with patch("auralis.core.hybrid_processor.HybridProcessor") as processor_cls:
        factory.get_or_create_from_config(config, mode="reference")

    owned_config = processor_cls.call_args.args[0]
    assert owned_config is not config
    assert owned_config.adaptive.mode == "reference"
    assert config.adaptive.mode == "adaptive"


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


def test_cleanup_track_closes_removed_processors():
    """cleanup_track() must call close() on every processor it removes."""
    factory = ProcessorFactory()
    mock_processor = MagicMock()
    key = _make_key(7)
    factory._processor_cache[key] = mock_processor
    factory._active_processors[7] = mock_processor

    factory.cleanup_track(7)

    mock_processor.close.assert_called_once()
    assert key not in factory._processor_cache
    assert 7 not in factory._active_processors


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
