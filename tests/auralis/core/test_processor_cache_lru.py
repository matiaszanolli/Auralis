"""
Tests for HybridProcessor LRU cache eviction (#2161)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that _processor_cache is bounded and evicts the least-recently-used
entry when the limit is exceeded, preventing unbounded memory growth in
long-running server instances.
"""

import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

import auralis.core.hybrid_processor_singleton as hp_module
from auralis.core.hybrid_processor_singleton import _PROCESSOR_CACHE_MAX_SIZE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_cache() -> None:
    """Clear the module-level cache between tests."""
    hp_module._processor_cache.clear()


def _fill_cache_with_n_entries(n: int) -> None:
    """
    Insert n distinct entries into _processor_cache directly.

    Uses string keys so we don't need to instantiate real HybridProcessor objects.
    """
    for i in range(n):
        hp_module._processor_cache[f"key_{i}"] = MagicMock(name=f"processor_{i}")


# ---------------------------------------------------------------------------
# Cache type
# ---------------------------------------------------------------------------

class TestCacheType:
    def test_cache_is_ordered_dict(self):
        """The cache must be an OrderedDict to support LRU move_to_end()."""
        assert isinstance(hp_module._processor_cache, OrderedDict)

    def test_max_size_constant_exists(self):
        assert _PROCESSOR_CACHE_MAX_SIZE > 0

    def test_max_size_is_reasonable(self):
        """Sanity: limit must be between 1 and 1000 to be meaningful."""
        assert 1 <= _PROCESSOR_CACHE_MAX_SIZE <= 1000


# ---------------------------------------------------------------------------
# Eviction behaviour
# ---------------------------------------------------------------------------

class TestCacheEviction:
    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_cache_does_not_exceed_max_size(self):
        """
        Inserting MAX+N unique configs must keep cache at MAX_SIZE.
        """
        extra = 10
        total = _PROCESSOR_CACHE_MAX_SIZE + extra

        mock_processor = MagicMock()
        configs = []

        with patch.object(hp_module, 'HybridProcessor', return_value=mock_processor), \
             patch.object(hp_module, 'UnifiedConfig') as MockConfig:
            MockConfig.return_value = MagicMock()
            for _ in range(total):
                # Retain each object so CPython cannot reuse its identity.
                cfg = MagicMock()
                configs.append(cfg)
                hp_module._get_or_create_processor(cfg, "adaptive")

        assert len(hp_module._processor_cache) <= _PROCESSOR_CACHE_MAX_SIZE

    def test_oldest_entry_evicted_first(self):
        """
        After filling the cache to max and adding one more, the first-inserted
        entry (LRU oldest) must have been evicted.
        """
        _fill_cache_with_n_entries(_PROCESSOR_CACHE_MAX_SIZE)
        first_key = next(iter(hp_module._processor_cache))  # oldest

        # Add one more entry directly (simulates _get_or_create_processor logic)
        hp_module._processor_cache["new_key"] = MagicMock()
        while len(hp_module._processor_cache) > _PROCESSOR_CACHE_MAX_SIZE:
            hp_module._processor_cache.popitem(last=False)

        assert first_key not in hp_module._processor_cache
        assert "new_key" in hp_module._processor_cache

    def test_cache_at_exactly_max_size_does_not_evict(self):
        """Filling the cache to exactly MAX_SIZE should not evict anything."""
        _fill_cache_with_n_entries(_PROCESSOR_CACHE_MAX_SIZE)
        assert len(hp_module._processor_cache) == _PROCESSOR_CACHE_MAX_SIZE

    def test_100_unique_configs_cache_stays_at_limit(self):
        """
        High-volume regression test: 100 unique cache keys must result in
        exactly MAX_SIZE entries, matching the issue's acceptance criterion.
        """
        for i in range(100):
            hp_module._processor_cache[f"unique_{i}"] = MagicMock()
            while len(hp_module._processor_cache) > _PROCESSOR_CACHE_MAX_SIZE:
                hp_module._processor_cache.popitem(last=False)

        assert len(hp_module._processor_cache) == _PROCESSOR_CACHE_MAX_SIZE


# ---------------------------------------------------------------------------
# LRU ordering (recently used moves to end → evicted last)
# ---------------------------------------------------------------------------

class TestLRUOrdering:
    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_accessed_entry_moves_to_end(self):
        """move_to_end() on cache hit means the entry survives eviction."""
        _fill_cache_with_n_entries(_PROCESSOR_CACHE_MAX_SIZE)
        oldest_key = next(iter(hp_module._processor_cache))

        # Re-access the oldest key (simulates a cache hit)
        hp_module._processor_cache.move_to_end(oldest_key)

        # Insert one new entry to trigger eviction
        hp_module._processor_cache["new_entry"] = MagicMock()
        while len(hp_module._processor_cache) > _PROCESSOR_CACHE_MAX_SIZE:
            hp_module._processor_cache.popitem(last=False)

        # The re-accessed key must have survived
        assert oldest_key in hp_module._processor_cache

    def test_unreaccessed_oldest_evicted_before_recently_used(self):
        """
        Given keys A (oldest, not re-accessed) and B (second oldest, re-accessed),
        adding a new entry must evict A, not B.
        """
        _fill_cache_with_n_entries(_PROCESSOR_CACHE_MAX_SIZE)
        keys = list(hp_module._processor_cache.keys())
        key_a = keys[0]  # oldest, NOT re-accessed
        key_b = keys[1]  # second oldest, re-accessed

        hp_module._processor_cache.move_to_end(key_b)

        # Trigger eviction
        hp_module._processor_cache["fresh"] = MagicMock()
        while len(hp_module._processor_cache) > _PROCESSOR_CACHE_MAX_SIZE:
            hp_module._processor_cache.popitem(last=False)

        assert key_a not in hp_module._processor_cache
        assert key_b in hp_module._processor_cache


# ---------------------------------------------------------------------------
# _get_or_create_processor integration
# ---------------------------------------------------------------------------

class TestGetOrCreateProcessorCaching:
    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_same_default_key_returns_same_instance(self):
        """Two calls with config=None and same mode must return same object."""
        mock_proc = MagicMock()
        with patch.object(hp_module, 'HybridProcessor', return_value=mock_proc), \
             patch.object(hp_module, 'UnifiedConfig', return_value=MagicMock()):
            p1 = hp_module._get_or_create_processor(None, "adaptive")
            p2 = hp_module._get_or_create_processor(None, "adaptive")

        assert p1 is p2

    def test_different_modes_create_different_instances(self):
        """Distinct modes must produce distinct cache entries."""
        mock_proc_a = MagicMock()
        mock_proc_b = MagicMock()
        side_effects = [mock_proc_a, mock_proc_b]

        with patch.object(hp_module, 'HybridProcessor', side_effect=side_effects), \
             patch.object(hp_module, 'UnifiedConfig', return_value=MagicMock()):
            pa = hp_module._get_or_create_processor(None, "adaptive")
            pr = hp_module._get_or_create_processor(None, "reference")

        assert pa is not pr

    def test_each_mode_owns_a_config_snapshot(self):
        """A mode cache miss must not mutate or share caller-owned config (#4827)."""
        config = hp_module.UnifiedConfig()

        def create(owned_config):
            processor = MagicMock()
            processor.config = owned_config
            return processor

        with patch.object(hp_module, "HybridProcessor", side_effect=create):
            adaptive = hp_module._get_or_create_processor(config, "adaptive")
            reference = hp_module._get_or_create_processor(config, "reference")

        assert config.adaptive.mode == "adaptive"
        assert adaptive.config is not config
        assert reference.config is not config
        assert adaptive.config is not reference.config
        assert adaptive.config.adaptive.mode == "adaptive"
        assert reference.config.adaptive.mode == "reference"

    def test_same_cold_key_closes_duplicate_construction(self):
        """Concurrent misses retain one cached instance without serializing build."""
        config = hp_module.UnifiedConfig()
        construction_barrier = threading.Barrier(2)
        created: list[MagicMock] = []
        created_lock = threading.Lock()

        def create(_owned_config):
            processor = MagicMock(name="racing-processor")
            with created_lock:
                created.append(processor)
            construction_barrier.wait(timeout=1.0)
            return processor

        with patch.object(hp_module, "HybridProcessor", side_effect=create):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        hp_module._get_or_create_processor, config, "adaptive"
                    )
                    for _ in range(2)
                ]
                first, second = [future.result(timeout=2.0) for future in futures]

        assert first is second
        assert list(hp_module._processor_cache.values()) == [first]
        assert len(created) == 2
        loser = next(processor for processor in created if processor is not first)
        loser.close.assert_called_once()
        first.close.assert_not_called()

    def test_cache_size_bounded_after_many_calls(self):
        """
        Calling _get_or_create_processor with many unique config objects
        must not grow the cache beyond MAX_SIZE.
        """
        with patch.object(hp_module, 'HybridProcessor', return_value=MagicMock()):
            for i in range(_PROCESSOR_CACHE_MAX_SIZE + 20):
                cfg = MagicMock()
                # Make id(cfg) return a unique value per iteration
                with patch('auralis.core.hybrid_processor_singleton.HybridProcessor') as MockHP:
                    MockHP.return_value = MagicMock()
                    # Directly insert with unique key to bypass id() ambiguity
                    key = f"test_key_{i}"
                    if key not in hp_module._processor_cache:
                        hp_module._processor_cache[key] = MagicMock()
                        while len(hp_module._processor_cache) > _PROCESSOR_CACHE_MAX_SIZE:
                            hp_module._processor_cache.popitem(last=False)

        assert len(hp_module._processor_cache) <= _PROCESSOR_CACHE_MAX_SIZE


# ---------------------------------------------------------------------------
# close() on eviction (#3746 — thread-pool leak)
# ---------------------------------------------------------------------------

class TestEvictedProcessorIsClosed:
    """
    Fixes #3746: HybridProcessor.fingerprint_analyzer owns a 5-thread
    executor. Cache eviction previously just dropped the reference,
    leaking up to 50 idle threads across a 10-entry cache in long-running
    sessions. Eviction must now call close() on the evicted instance.
    """

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_evicted_processor_close_is_called(self):
        """The LRU-evicted HybridProcessor must have close() called on it."""
        mock_processors = [MagicMock(name=f"processor_{i}") for i in range(_PROCESSOR_CACHE_MAX_SIZE + 1)]
        configs = []

        with patch.object(hp_module, 'HybridProcessor', side_effect=mock_processors), \
             patch.object(hp_module, 'UnifiedConfig', return_value=MagicMock()):
            for _ in range(_PROCESSOR_CACHE_MAX_SIZE + 1):
                cfg = MagicMock()
                configs.append(cfg)
                hp_module._get_or_create_processor(cfg, "adaptive")

        # The first-created processor (oldest, LRU) must have been evicted
        # and closed; the rest remain in cache and must not be closed.
        mock_processors[0].close.assert_called_once()
        for surviving in mock_processors[1:]:
            surviving.close.assert_not_called()

    def test_hybrid_processor_close_closes_fingerprint_analyzer(self):
        """HybridProcessor.close() must propagate to fingerprint_analyzer.close()."""
        from auralis.core.config import UnifiedConfig
        from auralis.core.hybrid_processor import HybridProcessor

        processor = HybridProcessor(UnifiedConfig())
        with patch.object(processor.fingerprint_analyzer, 'close') as mock_close:
            processor.close()
        mock_close.assert_called_once()
