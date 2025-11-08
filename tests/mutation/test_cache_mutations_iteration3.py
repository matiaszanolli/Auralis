"""
Mutation-Killing Tests - Iteration 3
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Final push to >80% mutation score

Targets:
- Remaining edge cases from Iteration 2
- Focus on methods that are testable (not decorator/private methods)
"""

import pytest
from auralis.library.cache import QueryCache


@pytest.mark.mutation
class TestRemainingEdgeCases:
    """Target any remaining survivors from Iteration 2."""

    def test_cache_size_exactly_at_max(self):
        """
        MUTATION: Kills >= vs > mutation in max_size check.

        Cache at exactly max_size should not evict yet.
        """
        cache = QueryCache(max_size=3)

        # Fill exactly to max
        cache.set('k1', 'v1')
        cache.set('k2', 'v2')
        cache.set('k3', 'v3')

        # All 3 should be present
        assert len(cache._cache) == 3
        assert cache.get('k1') is not None
        assert cache.get('k2') is not None
        assert cache.get('k3') is not None

    def test_cache_eviction_removes_oldest(self):
        """
        MUTATION: Kills mutations in FIFO eviction logic.

        When exceeding max_size, oldest entry should be evicted.
        """
        import time
        cache = QueryCache(max_size=3)

        # Add in order with slight delays
        cache.set('oldest', 'v1')
        time.sleep(0.01)
        cache.set('middle', 'v2')
        time.sleep(0.01)
        cache.set('newest', 'v3')

        # Now add one more (should evict oldest)
        cache.set('fourth', 'v4')

        # Oldest should be gone
        assert cache.get('oldest') is None

        # Others should remain
        assert cache.get('middle') is not None
        assert cache.get('newest') is not None
        assert cache.get('fourth') is not None

    def test_stats_with_zero_division_edge_case(self):
        """
        MUTATION: Kills mutations in zero-check condition.

        Ensures > 0 check (not >= 0) for division protection.
        """
        cache = QueryCache()
        stats = cache.get_stats()

        # With zero total_requests, should not divide by zero
        assert stats['total_requests'] == 0
        assert stats['hit_rate'] == '0.0%'

    def test_invalidate_updates_cache_correctly(self):
        """
        MUTATION: Kills mutations in invalidate loop logic.

        Invalidation should actually remove entries.
        """
        cache = QueryCache()

        # Add multiple entries
        for i in range(5):
            cache.set(f'key{i}', f'val{i}', metadata={'func': 'test_func'})

        initial_size = len(cache._cache)
        assert initial_size == 5

        # Invalidate all
        cache.invalidate('test_func')

        # All should be removed
        assert len(cache._cache) == 0
        for i in range(5):
            assert cache.get(f'key{i}') is None

    def test_get_increments_hits_not_misses_on_success(self):
        """
        MUTATION: Kills mutations that increment wrong counter.

        Successful get should only increment hits, not misses.
        """
        cache = QueryCache()
        cache.set('key', 'val')

        initial_misses = cache._misses

        # Successful get
        result = cache.get('key')
        assert result == 'val'

        # Misses should not change
        assert cache._misses == initial_misses
        assert cache._hits > 0

    def test_get_increments_misses_not_hits_on_failure(self):
        """
        MUTATION: Kills mutations that increment wrong counter.

        Failed get should only increment misses, not hits.
        """
        cache = QueryCache()

        initial_hits = cache._hits

        # Failed get
        result = cache.get('nonexistent')
        assert result is None

        # Hits should not change
        assert cache._hits == initial_hits
        assert cache._misses > 0

    def test_expiry_none_when_ttl_zero(self):
        """
        MUTATION: Kills mutations in expiry calculation.

        When ttl=0, expiry should be None (no expiration).
        """
        cache = QueryCache()

        cache.set('permanent', 'value', ttl=0)

        # Check internal state (expiry should be None)
        entry = cache._cache.get('permanent')
        assert entry is not None
        value, expiry, metadata = entry
        assert expiry is None  # No expiration!

    def test_hit_rate_calculation_with_100_percent(self):
        """
        MUTATION: Kills arithmetic mutations in hit_rate.

        100% hit rate should be exactly 100.0%.
        """
        cache = QueryCache()
        cache.set('key', 'val')

        # 5 hits, 0 misses
        for _ in range(5):
            cache.get('key')

        stats = cache.get_stats()
        assert stats['hit_rate'] == '100.0%'

    def test_hit_rate_calculation_with_0_percent(self):
        """
        MUTATION: Kills arithmetic mutations in hit_rate.

        0% hit rate should be exactly 0.0%.
        """
        cache = QueryCache()

        # 5 misses, 0 hits
        for i in range(5):
            cache.get(f'missing{i}')

        stats = cache.get_stats()
        assert stats['hit_rate'] == '0.0%'

    def test_total_requests_is_sum_not_other_operation(self):
        """
        MUTATION: Kills +/- /* mutations in total_requests.

        total_requests must be hits + misses (not -, *, /).
        """
        cache = QueryCache()
        cache.set('key', 'val')

        # 3 hits
        cache.get('key')
        cache.get('key')
        cache.get('key')

        # 2 misses
        cache.get('m1')
        cache.get('m2')

        stats = cache.get_stats()

        # Must be sum
        assert stats['total_requests'] == 5  # 3 + 2
        assert stats['total_requests'] != 1  # Not 3 - 2
        assert stats['total_requests'] != 6  # Not 3 * 2


@pytest.mark.mutation
class TestEvictionBoundaryConditions:
    """Additional tests for eviction logic edge cases."""

    def test_eviction_at_size_plus_one(self):
        """
        MUTATION: Kills off-by-one errors in eviction trigger.

        Adding beyond max_size should trigger eviction.
        """
        cache = QueryCache(max_size=2)

        # Fill to max
        cache.set('first', 'v1')
        cache.set('second', 'v2')

        # At max, no eviction yet
        assert len(cache._cache) == 2

        # Add one more - should evict
        cache.set('third', 'v3')

        # Size should be at max, not over
        assert len(cache._cache) == 2
        assert cache.get('first') is None  # First evicted
        assert cache.get('second') is not None
        assert cache.get('third') is not None

    def test_eviction_preserves_recent_entries(self):
        """
        MUTATION: Kills mutations in LRU ordering.

        Eviction should remove oldest, not newest.
        """
        cache = QueryCache(max_size=3)

        # Add 3 entries in order
        cache.set('a', '1')
        cache.set('b', '2')
        cache.set('c', '3')

        # Add 2 more (should evict a and b)
        cache.set('d', '4')
        cache.set('e', '5')

        # Oldest 2 gone, newest 3 remain
        assert cache.get('a') is None
        assert cache.get('b') is None
        assert cache.get('c') is not None
        assert cache.get('d') is not None
        assert cache.get('e') is not None


@pytest.mark.mutation
class TestCounterEdgeCases:
    """Test counter increment edge cases."""

    def test_hits_counter_never_decrements(self):
        """
        MUTATION: Kills mutations that decrement counters.

        Hits should only increase or stay same, never decrease.
        """
        cache = QueryCache()
        cache.set('key', 'val')

        prev_hits = 0
        for _ in range(10):
            cache.get('key')
            current_hits = cache._hits
            assert current_hits >= prev_hits
            prev_hits = current_hits

    def test_misses_counter_never_decrements(self):
        """
        MUTATION: Kills mutations that decrement counters.

        Misses should only increase or stay same, never decrease.
        """
        cache = QueryCache()

        prev_misses = 0
        for i in range(10):
            cache.get(f'missing{i}')
            current_misses = cache._misses
            assert current_misses >= prev_misses
            prev_misses = current_misses

    def test_counters_start_at_zero(self):
        """
        MUTATION: Kills mutations in initial counter values.

        Both counters must start at exactly zero.
        """
        cache = QueryCache()

        assert cache._hits == 0
        assert cache._misses == 0
        assert cache._hits != 1
        assert cache._misses != 1
        assert cache._hits != -1
        assert cache._misses != -1
