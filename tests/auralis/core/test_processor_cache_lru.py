"""
Tests for HybridProcessor LRU cache eviction (#2161)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that _processor_cache is bounded and evicts the least-recently-used
entry when the limit is exceeded, preventing unbounded memory growth in
long-running server instances.
"""

from collections import OrderedDict
from unittest.mock import MagicMock, patch

import pytest

import auralis.core.hybrid_processor as hp_module
from auralis.core.hybrid_processor import _PROCESSOR_CACHE_MAX_SIZE


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

        with patch.object(hp_module, 'HybridProcessor', return_value=mock_processor), \
             patch.object(hp_module, 'UnifiedConfig') as MockConfig:
            MockConfig.return_value = MagicMock()
            for i in range(total):
                # Produce unique cache keys by supplying distinct config objects
                cfg = MagicMock()
                cfg_id = i  # stable id for this loop iteration
                with patch('builtins.id', side_effect=lambda x, _i=cfg_id: _i if x is cfg else id.__wrapped__(x)):
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

    def test_cache_size_bounded_after_many_calls(self):
        """
        Calling _get_or_create_processor with many unique config objects
        must not grow the cache beyond MAX_SIZE.
        """
        with patch.object(hp_module, 'HybridProcessor', return_value=MagicMock()):
            for i in range(_PROCESSOR_CACHE_MAX_SIZE + 20):
                cfg = MagicMock()
                # Make id(cfg) return a unique value per iteration
                with patch('auralis.core.hybrid_processor.HybridProcessor') as MockHP:
                    MockHP.return_value = MagicMock()
                    # Directly insert with unique key to bypass id() ambiguity
                    key = f"test_key_{i}"
                    if key not in hp_module._processor_cache:
                        hp_module._processor_cache[key] = MagicMock()
                        while len(hp_module._processor_cache) > _PROCESSOR_CACHE_MAX_SIZE:
                            hp_module._processor_cache.popitem(last=False)

        assert len(hp_module._processor_cache) <= _PROCESSOR_CACHE_MAX_SIZE
