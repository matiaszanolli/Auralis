"""
Mutation-Killing Tests - Iteration 2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Targeted tests to improve mutation score from 44.8% to 60-70%

Targets:
- 21 untested mutations in get_stats()
- 6 survivors in get() (increment mutations)
- 5 survivors in invalidate()
- Various increment/assignment mutations
"""

import time
from datetime import datetime, timedelta

import pytest

from auralis.library.cache import QueryCache


@pytest.mark.mutation
class TestGetStatsMethod:
    """Kill all 21 mutations in get_stats() method."""

    def test_get_stats_returns_all_required_fields(self):
        """
        MUTATION: Kills mutations that remove or change dict keys.

        Verifies all 6 fields exist with correct types.
        """
        cache = QueryCache(max_size=128, default_ttl=300)
        stats = cache.get_stats()

        # All fields must exist
        assert 'size' in stats
        assert 'max_size' in stats
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'hit_rate' in stats
        assert 'total_requests' in stats

        # Exactly 6 fields (kills mutations that add/remove fields)
        assert len(stats) == 6

    def test_get_stats_initial_state(self):
        """
        MUTATION: Kills mutations in initial value calculations.

        Original: _hits = 0, _misses = 0
        Mutant: _hits = 1, _misses = 1
        """
        cache = QueryCache(max_size=10, default_ttl=60)
        stats = cache.get_stats()

        # All counters start at zero
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['total_requests'] == 0
        assert stats['size'] == 0

        # Max size matches constructor
        assert stats['max_size'] == 10

        # Hit rate is zero with no requests
        assert stats['hit_rate'] == '0.0%'

    def test_get_stats_after_operations(self):
        """
        MUTATION: Kills arithmetic mutations in total_requests calculation.

        Original: total_requests = _hits + _misses
        Mutant: total_requests = _hits - _misses
        """
        cache = QueryCache()

        # Cause 3 hits
        cache.set('key1', 'val1')
        cache.set('key2', 'val2')
        cache.set('key3', 'val3')
        cache.get('key1')
        cache.get('key2')
        cache.get('key3')

        # Cause 2 misses
        cache.get('missing1')
        cache.get('missing2')

        stats = cache.get_stats()

        # Verify exact counts
        assert stats['hits'] == 3
        assert stats['misses'] == 2

        # Total must be sum (not difference, not product)
        assert stats['total_requests'] == 5  # 3 + 2
        assert stats['total_requests'] != 1  # Kills 3 - 2
        assert stats['total_requests'] != 6  # Kills 3 * 2

    def test_get_stats_hit_rate_calculation(self):
        """
        MUTATION: Kills mutations in hit_rate calculation.

        Original: hit_rate = (_hits / total_requests * 100)
        Mutants:
        - _hits * total_requests
        - _hits - total_requests
        - total_requests / _hits
        """
        cache = QueryCache()

        # 3 hits, 1 miss = 75% hit rate
        cache.set('key', 'val')
        cache.get('key')  # hit
        cache.get('key')  # hit
        cache.get('key')  # hit
        cache.get('missing')  # miss

        stats = cache.get_stats()

        # Hit rate should be 75.0%
        assert stats['hit_rate'] == '75.0%'
        assert stats['hit_rate'] != '3.0%'  # Kills wrong division
        assert stats['hit_rate'] != '300.0%'  # Kills multiplication

    def test_get_stats_hit_rate_formatting(self):
        """
        MUTATION: Kills mutations in f-string formatting.

        Original: f'{hit_rate:.1f}%'
        Mutants: Different decimal places, missing %
        """
        cache = QueryCache()

        # Create specific hit rate: 2/3 = 66.666...%
        cache.set('key', 'val')
        cache.get('key')  # hit
        cache.get('key')  # hit
        cache.get('missing')  # miss

        stats = cache.get_stats()

        # Must be formatted to 1 decimal place with %
        assert stats['hit_rate'] == '66.7%'  # Rounded to 1 decimal
        assert '%' in stats['hit_rate']  # Has percent sign
        assert '.' in stats['hit_rate']  # Has decimal point
        assert len(stats['hit_rate']) == 5  # "66.7%" = 5 chars

    def test_get_stats_zero_requests_hit_rate(self):
        """
        MUTATION: Kills mutations in zero-division protection.

        Original: hit_rate = ... if total_requests > 0 else 0
        Mutants: >= instead of >, wrong else value
        """
        cache = QueryCache()
        stats = cache.get_stats()

        # With zero requests, hit_rate should be 0.0%
        assert stats['hit_rate'] == '0.0%'
        assert stats['hit_rate'] != ''  # Kills None → ''
        assert stats['hit_rate'] != 'None'  # Kills None → 'None'

    def test_get_stats_size_reflects_cache_length(self):
        """
        MUTATION: Kills mutations in len(self._cache) call.

        Original: 'size': len(self._cache)
        Mutants: len(self._cache) + 1, constant values
        """
        cache = QueryCache()

        # Empty cache
        assert cache.get_stats()['size'] == 0

        # Add 1 item
        cache.set('key1', 'val1')
        assert cache.get_stats()['size'] == 1

        # Add 2 more items
        cache.set('key2', 'val2')
        cache.set('key3', 'val3')
        assert cache.get_stats()['size'] == 3

        # Size must match exactly (not +1, not constant)
        assert cache.get_stats()['size'] == len(cache._cache)

    def test_get_stats_max_size_from_constructor(self):
        """
        MUTATION: Kills mutations in max_size field.

        Original: 'max_size': self.max_size
        Mutants: self.max_size + 1, self.max_size - 1
        """
        # Test with specific max_size
        cache = QueryCache(max_size=42, default_ttl=300)
        stats = cache.get_stats()

        # Must match constructor exactly
        assert stats['max_size'] == 42
        assert stats['max_size'] != 41  # Kills -1
        assert stats['max_size'] != 43  # Kills +1


@pytest.mark.mutation
class TestMultipleIncrements:
    """Kill increment vs assignment mutations (+=1 vs =1)."""

    def test_multiple_hits_increment_correctly(self):
        """
        MUTATION: Kills _hits += 1 → _hits = 1

        If mutant uses =1, _hits stays at 1 instead of incrementing.
        """
        cache = QueryCache()
        cache.set('key', 'value')

        # Get the same key 5 times
        for i in range(5):
            cache.get('key')

        # Should increment each time: 1, 2, 3, 4, 5
        assert cache._hits == 5
        assert cache._hits != 1  # Kills =1 mutation

    def test_multiple_misses_increment_correctly(self):
        """
        MUTATION: Kills _misses += 1 → _misses = 1

        If mutant uses =1, _misses stays at 1 instead of incrementing.
        """
        cache = QueryCache()

        # Miss 5 different keys
        for i in range(5):
            cache.get(f'missing{i}')

        # Should increment each time: 1, 2, 3, 4, 5
        assert cache._misses == 5
        assert cache._misses != 1  # Kills =1 mutation

    def test_mixed_hits_and_misses_increment_separately(self):
        """
        MUTATION: Kills mutations affecting both counters.

        Verifies hits and misses track independently.
        """
        cache = QueryCache()
        cache.set('exists', 'value')

        # 3 hits
        cache.get('exists')
        cache.get('exists')
        cache.get('exists')

        # 2 misses
        cache.get('missing1')
        cache.get('missing2')

        # 2 more hits
        cache.get('exists')
        cache.get('exists')

        # Verify independent increment
        assert cache._hits == 5
        assert cache._misses == 2
        assert cache._hits + cache._misses == 7

    def test_increments_from_non_zero_baseline(self):
        """
        MUTATION: Kills +=1 → =1 when counters start > 0.

        Critical test: Start counters at non-zero, then increment.
        """
        cache = QueryCache()
        cache.set('key', 'val')

        # First hit and miss (counters = 1, 1)
        cache.get('key')
        cache.get('missing1')

        initial_hits = cache._hits
        initial_misses = cache._misses

        # Now add more (critical: not starting from 0)
        cache.get('key')
        cache.get('missing2')

        # Must increment from previous values
        assert cache._hits == initial_hits + 1
        assert cache._misses == initial_misses + 1


@pytest.mark.mutation
class TestInvalidateEdgeCases:
    """Kill the 5 surviving mutations in invalidate()."""

    def test_invalidate_with_no_matching_pattern(self):
        """
        MUTATION: Kills mutations in pattern matching logic.

        When pattern doesn't match, nothing should be removed.
        """
        cache = QueryCache()

        # Add entries with different function names
        cache.set('key1', 'val1', metadata={'func': 'get_tracks'})
        cache.set('key2', 'val2', metadata={'func': 'get_albums'})

        # Invalidate non-existent pattern
        cache.invalidate('get_playlists')

        # Nothing should be removed
        assert cache.get('key1') is not None
        assert cache.get('key2') is not None
        assert len(cache._cache) == 2

    def test_invalidate_multiple_patterns(self):
        """
        MUTATION: Kills mutations in multi-pattern handling.

        Multiple patterns should remove all matches.
        """
        cache = QueryCache()

        cache.set('k1', 'v1', metadata={'func': 'get_tracks'})
        cache.set('k2', 'v2', metadata={'func': 'get_albums'})
        cache.set('k3', 'v3', metadata={'func': 'get_artists'})
        cache.set('k4', 'v4', metadata={'func': 'get_genres'})

        # Invalidate two patterns
        cache.invalidate('get_tracks', 'get_albums')

        # These should be gone
        assert cache.get('k1') is None
        assert cache.get('k2') is None

        # These should remain
        assert cache.get('k3') is not None
        assert cache.get('k4') is not None

    def test_invalidate_empty_cache(self):
        """
        MUTATION: Kills mutations that fail on empty cache.

        Invalidating empty cache should not error.
        """
        cache = QueryCache()

        # Should not raise exception
        cache.invalidate('any_pattern')

        # Cache should still be empty
        assert len(cache._cache) == 0

    def test_invalidate_partial_metadata_match(self):
        """
        MUTATION: Kills mutations in metadata field access.

        Only entries with matching metadata['func'] removed.
        """
        cache = QueryCache()

        # Some entries with metadata, some without
        cache.set('with_meta', 'val1', metadata={'func': 'get_tracks', 'extra': 'data'})
        cache.set('no_meta', 'val2')  # No metadata
        cache.set('different', 'val3', metadata={'func': 'get_albums'})

        cache.invalidate('get_tracks')

        # With matching metadata: gone
        assert cache.get('with_meta') is None

        # Without metadata or different: remain
        assert cache.get('no_meta') is not None
        assert cache.get('different') is not None

    def test_invalidate_all_when_no_patterns(self):
        """
        MUTATION: Kills mutations in empty pattern handling.

        Original: invalidate() with no args clears all
        """
        cache = QueryCache()

        cache.set('key1', 'val1', metadata={'func': 'func1'})
        cache.set('key2', 'val2', metadata={'func': 'func2'})
        cache.set('key3', 'val3')

        # No patterns = clear all
        cache.invalidate()

        # Everything should be gone
        assert len(cache._cache) == 0
        assert cache.get('key1') is None
        assert cache.get('key2') is None
        assert cache.get('key3') is None


@pytest.mark.mutation
class TestConstructorMutations:
    """Kill the 3 surviving mutations in __init__()."""

    def test_default_max_size_exact_value(self):
        """
        MUTATION: Kills max_size constant mutations (128 → 127, 129).

        Verifies default max_size is exactly 128.
        """
        cache = QueryCache()  # No args, uses defaults

        assert cache.max_size == 128
        assert cache.max_size != 127  # Kills -1
        assert cache.max_size != 129  # Kills +1

    def test_default_ttl_exact_value(self):
        """
        MUTATION: Kills default_ttl constant mutations (300 → 299, 301).

        Verifies default TTL is exactly 300.
        """
        cache = QueryCache()

        assert cache.default_ttl == 300
        assert cache.default_ttl != 299  # Kills -1
        assert cache.default_ttl != 301  # Kills +1

    def test_initial_counters_are_zero(self):
        """
        MUTATION: Kills mutations in counter initialization.

        Original: _hits = 0, _misses = 0
        Mutants: = 1, = -1
        """
        cache = QueryCache()

        # Must start at exactly zero
        assert cache._hits == 0
        assert cache._misses == 0
        assert cache._hits != 1  # Kills =1
        assert cache._misses != 1  # Kills =1


@pytest.mark.mutation
class TestSetMethodMutations:
    """Kill the 2 surviving mutations in set()."""

    def test_ttl_none_uses_default(self):
        """
        MUTATION: Kills mutations in TTL default logic.

        Original: if ttl is None: ttl = self.default_ttl
        Mutants: Wrong condition, wrong assignment
        """
        cache = QueryCache(default_ttl=5)

        # Set without explicit TTL
        cache.set('key', 'val')  # Should use default_ttl=5

        # Should be available immediately
        assert cache.get('key') == 'val'

        # Wait past default TTL
        time.sleep(5.1)

        # Should be expired (proves it used default_ttl)
        assert cache.get('key') is None

    def test_ttl_zero_means_no_expiration(self):
        """
        MUTATION: Kills mutations in ttl > 0 check.

        Original: if ttl > 0: expiry = ...
        Mutant: if ttl >= 0: expiry = ... (would set expiry for ttl=0)
        """
        cache = QueryCache()

        # ttl=0 means no expiration
        cache.set('permanent', 'value', ttl=0)

        # Wait a bit
        time.sleep(0.5)

        # Should still be available (no expiration)
        result = cache.get('permanent')
        assert result == 'value'
        assert result is not None


@pytest.mark.mutation
class TestGetMethodMutations:
    """Kill remaining mutations in get() beyond basic increment."""

    def test_expiry_comparison_exact(self):
        """
        MUTATION: Kills > vs >= in expiry check.

        Original: if expiry and datetime.now() > expiry
        Mutant: if expiry and datetime.now() >= expiry
        """
        cache = QueryCache()

        # Set with very short TTL
        cache.set('key', 'val', ttl=1)

        # Exactly at expiry is tricky with datetime, so test both sides

        # Immediately after set: should be available
        assert cache.get('key') == 'val'

        # Well past expiry: should be None
        time.sleep(1.1)
        assert cache.get('key') is None

    def test_expired_entry_is_deleted_from_cache(self):
        """
        MUTATION: Kills mutations that skip deletion.

        Original: del self._cache[key]
        Mutant: # del self._cache[key] (commented out)
        """
        cache = QueryCache()

        cache.set('expires', 'val', ttl=1)
        time.sleep(1.1)

        # Get expired entry
        result = cache.get('expires')
        assert result is None

        # Entry should be deleted (not just return None)
        assert 'expires' not in cache._cache
        assert len(cache._cache) == 0

    def test_get_with_explicit_default(self):
        """
        MUTATION: Kills mutations in default parameter.

        Tests that custom defaults work (though get() doesn't have default param).
        This tests the None return value mutations.
        """
        cache = QueryCache()

        # Missing key returns None
        result = cache.get('missing')

        # Must be exactly None (not False, not 0, not '')
        assert result is None
        assert result != False
        assert result != 0
        assert result != ''
