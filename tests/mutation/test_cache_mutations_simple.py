"""
Simple Mutation-Killing Tests for QueryCache
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These tests target specific mutations in auralis/library/cache.py
"""

import pytest
import time
from datetime import datetime, timedelta
from auralis.library.cache import QueryCache


@pytest.mark.mutation
class TestCacheBasicOperations:
    """Test basic cache operations to kill simple mutations."""

    def test_cache_get_returns_none_for_missing_key(self):
        """
        MUTATION: Kills mutations in 'key not in self._cache' check.

        Original: if key not in self._cache: return None
        Mutant: if key in self._cache: return None (would reverse logic)
        """
        cache = QueryCache()
        result = cache.get('missing_key')

        # Must be None (not False, not empty string)
        assert result is None
        assert result is not False
        assert result != ''

    def test_cache_set_and_get_stores_value(self):
        """
        MUTATION: Kills mutations that break basic storage.
        """
        cache = QueryCache()
        cache.set('key1', 'value1')
        result = cache.get('key1')

        # Exact value match
        assert result == 'value1'
        assert result is not None

    def test_cache_overwrite_existing_key(self):
        """
        MUTATION: Kills mutations in key existence check.

        Original: if key not in self._cache (for LRU)
        """
        cache = QueryCache()
        cache.set('key1', 'first_value')
        cache.set('key1', 'second_value')

        result = cache.get('key1')
        assert result == 'second_value'


@pytest.mark.mutation
class TestCacheExpiration:
    """Test TTL expiration to kill datetime comparison mutations."""

    def test_expired_entry_returns_none(self):
        """
        MUTATION: Kills > → >= in expiry check.

        Original: if expiry and datetime.now() > expiry: return None
        """
        cache = QueryCache()

        # Set with 1 second TTL
        cache.set('short_lived', 'value', ttl=1)

        # Immediately should be available
        assert cache.get('short_lived') == 'value'

        # Wait for expiration
        time.sleep(1.1)

        # Should now return None
        result = cache.get('short_lived')
        assert result is None

    def test_non_expired_entry_returns_value(self):
        """
        MUTATION: Kills mutations that always expire or never expire.
        """
        cache = QueryCache()

        # Set with 10 second TTL
        cache.set('long_lived', 'value', ttl=10)

        # Should still be available
        result = cache.get('long_lived')
        assert result == 'value'
        assert result is not None


@pytest.mark.mutation
class TestCacheSizeLimits:
    """Test LRU eviction to kill comparison mutations."""

    def test_evicts_when_over_max_size(self):
        """
        MUTATION: Kills >= → > in size check.

        Original: if len(self._cache) >= self.max_size
        """
        cache = QueryCache(max_size=3)

        # Fill cache exactly to max
        cache.set('key1', 'val1')
        cache.set('key2', 'val2')
        cache.set('key3', 'val3')

        # All should be present
        assert cache.get('key1') is not None
        assert cache.get('key2') is not None
        assert cache.get('key3') is not None

        # Add one more (should evict oldest)
        cache.set('key4', 'val4')

        # Size should not exceed max
        assert len(cache._cache) <= 3

    def test_no_eviction_at_max_size_minus_one(self):
        """
        MUTATION: Kills off-by-one errors in size check.
        """
        cache = QueryCache(max_size=3)

        # Fill to max_size - 1
        cache.set('key1', 'val1')
        cache.set('key2', 'val2')

        # All should still be present
        assert cache.get('key1') is not None
        assert cache.get('key2') is not None

        # Size should be exactly 2
        assert len(cache._cache) == 2


@pytest.mark.mutation
class TestCacheStats:
    """Test hit/miss counting to kill increment mutations."""

    def test_miss_increments_by_one(self):
        """
        MUTATION: Kills +=1 → +=2 or +=0 mutations.
        """
        cache = QueryCache()
        initial_misses = cache._misses

        # Cause exactly one miss
        cache.get('missing_key')

        # Should increment by exactly 1
        assert cache._misses == initial_misses + 1
        assert cache._misses != initial_misses + 2
        assert cache._misses != initial_misses

    def test_hit_increments_by_one(self):
        """
        MUTATION: Kills +=1 → +=2 or +=0 mutations.
        """
        cache = QueryCache()
        cache.set('existing_key', 'value')

        initial_hits = cache._hits

        # Cause exactly one hit
        cache.get('existing_key')

        # Should increment by exactly 1
        assert cache._hits == initial_hits + 1
        assert cache._hits != initial_hits + 2
        assert cache._hits != initial_hits


@pytest.mark.mutation
class TestDefaultTTL:
    """Test default TTL usage to kill constant mutations."""

    def test_uses_default_ttl_when_none_specified(self):
        """
        MUTATION: Kills mutations in default TTL assignment.

        Original: if ttl is None: ttl = self.default_ttl
        """
        cache = QueryCache(default_ttl=2)

        # Set without explicit TTL (should use default)
        cache.set('key', 'value')  # Uses default_ttl=2

        # Should be available immediately
        assert cache.get('key') == 'value'

        # Wait for default TTL to expire
        time.sleep(2.1)

        # Should now be expired
        assert cache.get('key') is None

    def test_explicit_ttl_overrides_default(self):
        """
        MUTATION: Kills mutations that ignore explicit TTL.
        """
        cache = QueryCache(default_ttl=1)

        # Set with explicit long TTL (overrides default)
        cache.set('key', 'value', ttl=10)

        # Wait past default TTL
        time.sleep(1.1)

        # Should still be available (using explicit TTL, not default)
        result = cache.get('key')
        assert result == 'value'
        assert result is not None


@pytest.mark.mutation
class TestCacheInvalidation:
    """Test cache invalidation to kill mutations."""

    def test_invalidate_removes_matching_patterns(self):
        """
        MUTATION: Kills mutations in invalidate logic.
        """
        cache = QueryCache()

        # Add entries with metadata
        cache.set('key1', 'val1', metadata={'func': 'get_tracks'})
        cache.set('key2', 'val2', metadata={'func': 'get_albums'})
        cache.set('key3', 'val3', metadata={'func': 'get_tracks'})

        # All should exist
        assert cache.get('key1') is not None
        assert cache.get('key2') is not None
        assert cache.get('key3') is not None

        # Invalidate 'get_tracks' pattern
        cache.invalidate('get_tracks')

        # get_tracks entries should be gone
        assert cache.get('key1') is None
        assert cache.get('key3') is None

        # get_albums should still exist
        assert cache.get('key2') is not None


@pytest.mark.mutation
class TestZeroTTL:
    """Test zero TTL (no expiration) to kill comparison mutations."""

    def test_zero_ttl_never_expires(self):
        """
        MUTATION: Kills mutations in TTL > 0 check.

        Original: if ttl > 0: expiry = ...
        Mutant: if ttl >= 0: expiry = ... (would set expiry for ttl=0)
        """
        cache = QueryCache()

        # Set with zero TTL (no expiration)
        cache.set('permanent', 'value', ttl=0)

        # Should be available immediately
        assert cache.get('permanent') == 'value'

        # Wait a bit
        time.sleep(0.5)

        # Should still be available (no expiration)
        result = cache.get('permanent')
        assert result == 'value'
        assert result is not None
