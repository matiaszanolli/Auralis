# -*- coding: utf-8 -*-

"""
Tests for ProcessorFactory config-based caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression tests for content-based config hashing (issue #2707).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from unittest.mock import MagicMock, patch

from auralis.core.config.unified_config import UnifiedConfig
from core.processor_factory import ProcessorFactory, ProcessorCacheKey, _PROCESSOR_CACHE_MAX


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


# ---------------------------------------------------------------------------
# close() on eviction / cleanup (#3746 — thread-pool leak)
# ---------------------------------------------------------------------------
#
# HybridProcessor.fingerprint_analyzer owns a 5-thread executor. Dropping a
# cached HybridProcessor reference without calling close() leaked those
# threads indefinitely. Every path that removes a processor from
# ProcessorFactory's cache must now call close() on it first.

def _make_key(i: int) -> ProcessorCacheKey:
    return ProcessorCacheKey(track_id=i, preset="adaptive", intensity=1.0, config_hash=f"hash_{i}", targets_hash="none")


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
