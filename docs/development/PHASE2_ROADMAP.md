# Phase 2: Quality Improvements - Roadmap

**Date:** November 7, 2024
**Status:** 🚀 **ACTIVE**
**Phase 1 Completion:** 91% pass rate (129/135 tests passing)

---

## Overview

Phase 2 focuses on addressing the systemic issues discovered during Phase 1 testing:

1. **Cache System Limitations** - Pattern-based invalidation impossible due to MD5 hashed keys
2. **API Inconsistencies** - Mixed return types across similar methods
3. **Missing Test Coverage** - Cache behavior, edge cases not tested
4. **Documentation Gaps** - No API design guidelines

**Duration:** 2-3 weeks
**Target:** Production-ready library management system with 95%+ test coverage

---

## Phase 1 Key Findings

### Critical Issues Found

1. **Cache Invalidation Bug** (Fixed in Phase 1)
   - **Symptom:** Deleted/updated tracks still visible in queries
   - **Root Cause:** Cache keys are MD5 hashes, pattern matching doesn't work
   - **Current Fix:** Full cache clear on mutations (performance trade-off)
   - **Phase 2 Goal:** Enable pattern-based invalidation

2. **API Return Type Inconsistency** (Not fixed)
   - `get_all_tracks()` returns `(List[Track], int)` (paginated)
   - `search_tracks()` returns `List[Track]` (no total)
   - `get_favorite_tracks()` returns `List[Track]` (no total)
   - **Impact:** 20+ test failures due to unpacking errors

3. **Missing CRUD Methods** (Fixed in Phase 1)
   - Added: `TrackRepository.delete()`, `TrackRepository.update()`
   - Added: `LibraryManager.delete_track()`, `LibraryManager.update_track()`

---

## Phase 2 Goals

### Primary Objectives

✅ **Enable pattern-based cache invalidation** (eliminate full cache clears)
✅ **Standardize API return types** (consistent pagination)
✅ **Add cache behavior tests** (verify invalidation works)
✅ **Create API design guidelines** (prevent future inconsistencies)

### Success Metrics

- **95%+ test pass rate** (up from 91%)
- **Cache hit rate > 80%** after mutations (vs. 0% with full clear)
- **Zero API inconsistencies** across library methods
- **100% cache invalidation tests passing**

---

## Implementation Plan

### Week 1: Cache System Refactoring

**Goal:** Enable pattern-based cache invalidation without breaking changes

#### Task 1.1: Refactor Cache Key System (3-4 hours)

**Current implementation:**
```python
# auralis/library/cache.py
def _generate_cache_key(self, func_name, args, kwargs):
    """Generate MD5 hash key (no function name stored)"""
    key_data = f"{func_name}:{args}:{kwargs}"
    return hashlib.md5(key_data.encode()).hexdigest()
```

**Problem:** Pattern matching like `invalidate_cache('get_all_tracks')` can't match MD5 hashes.

**New implementation:**
```python
# Store both function name AND hash for pattern matching
def _generate_cache_key(self, func_name, args, kwargs):
    """Generate cache key with metadata for pattern matching"""
    hash_key = hashlib.md5(f"{func_name}:{args}:{kwargs}".encode()).hexdigest()
    return {
        'key': hash_key,
        'func': func_name,
        'args_hash': hashlib.md5(str(args).encode()).hexdigest()
    }

# Enable pattern-based invalidation
def invalidate_cache(self, pattern=None):
    """Clear cache by pattern or all if pattern is None"""
    if pattern is None:
        self._cache.clear()  # Full clear
    else:
        # Remove entries matching pattern
        keys_to_remove = [
            k for k, v in self._cache.items()
            if v['func'].startswith(pattern)
        ]
        for key in keys_to_remove:
            del self._cache[key]
```

**Files to modify:**
- `auralis/library/cache.py` - Cache key generation
- `auralis/library/manager.py` - Update invalidation calls

**Tests to add:**
- `test_pattern_based_cache_invalidation()`
- `test_cache_survives_unrelated_mutations()`
- `test_cache_hit_rate_after_targeted_invalidation()`

**Expected impact:**
- Cache hit rate after mutations: 0% → 80%+
- Performance improvement: 136x speedup preserved on unrelated queries

#### Task 1.2: Update Manager Methods (1-2 hours)

**Change invalidation strategy:**
```python
# Before (Phase 1 fix)
def delete_track(self, track_id: int) -> bool:
    result = self.tracks.delete(track_id)
    if result:
        invalidate_cache()  # Clears everything!
    return result

# After (Phase 2 improvement)
def delete_track(self, track_id: int) -> bool:
    result = self.tracks.delete(track_id)
    if result:
        # Only invalidate track-related queries
        invalidate_cache('get_all_tracks')
        invalidate_cache('get_track')
        invalidate_cache('search_tracks')
        # Favorites, recent, etc. remain cached!
    return result
```

**Files to modify:**
- `auralis/library/manager.py` - All mutation methods

**Expected invalidation patterns:**
- `delete_track()` → invalidate `get_all_tracks`, `get_track`, `search_tracks`
- `update_track()` → invalidate `get_track`, `search_tracks`
- `set_track_favorite()` → invalidate `get_favorite_tracks` only
- `record_track_play()` → invalidate `get_recent_tracks` only
- `add_track()` → invalidate `get_all_tracks`, `search_tracks`

#### Task 1.3: Add Cache Behavior Tests (2-3 hours)

**Create comprehensive cache test suite:**

```python
# tests/backend/test_cache_invalidation.py

@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.library
def test_delete_invalidates_only_track_queries(populated_library):
    """Verify delete doesn't clear favorite/recent caches"""
    manager, track_ids, _ = populated_library

    # Populate all caches
    manager.get_all_tracks(limit=10)
    manager.set_track_favorite(track_ids[5], True)
    manager.get_favorite_tracks(limit=10)  # Cache favorites

    # Delete unrelated track
    manager.delete_track(track_ids[0])

    # Favorite cache should still be hot (not re-queried)
    stats_before = manager.get_cache_stats()
    favorites = manager.get_favorite_tracks(limit=10)
    stats_after = manager.get_cache_stats()

    # Should be cache hit (no DB query)
    assert stats_after['hits'] == stats_before['hits'] + 1

@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.library
def test_favorite_invalidates_only_favorites(populated_library):
    """Verify favorite toggle doesn't clear all_tracks cache"""
    manager, track_ids, _ = populated_library

    # Populate caches
    all_tracks, total = manager.get_all_tracks(limit=10)
    manager.get_favorite_tracks(limit=10)

    # Toggle favorite
    manager.set_track_favorite(track_ids[0], True)

    # all_tracks cache should still be hot
    stats_before = manager.get_cache_stats()
    all_tracks, total = manager.get_all_tracks(limit=10)
    stats_after = manager.get_cache_stats()

    assert stats_after['hits'] == stats_before['hits'] + 1

@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.library
def test_cache_hit_rate_after_mutations(populated_library):
    """Verify cache effectiveness after various mutations"""
    manager, track_ids, _ = populated_library

    # Perform 100 mixed operations
    for i in range(100):
        if i % 10 == 0:
            manager.set_track_favorite(track_ids[i % len(track_ids)], True)
        else:
            manager.get_all_tracks(limit=10)  # Should be cached

    stats = manager.get_cache_stats()
    hit_rate = stats['hit_rate']

    # Should have high hit rate (most get_all_tracks are cached)
    assert hit_rate > 0.8, f"Cache hit rate too low: {hit_rate:.2%}"
```

**Files to create:**
- `tests/backend/test_cache_invalidation.py` - Cache behavior tests (15-20 tests)

**Test categories:**
- Pattern-based invalidation correctness
- Cache survival after unrelated mutations
- Cache hit rate benchmarks
- Full cache clear fallback behavior

---

### Week 2: API Standardization

**Goal:** Consistent return types and method signatures

#### Task 2.1: Standardize Return Types (2-3 hours)

**Principle:** Paginated queries ALWAYS return `(data, total)`, non-paginated return `data`

**Changes needed:**

```python
# auralis/library/repositories/track_repository.py

# BEFORE (inconsistent)
def search(self, query: str, limit: int = None, offset: int = 0) -> List[Track]:
    """Search tracks - returns list only"""
    # ...
    return results

# AFTER (consistent)
def search(self, query: str, limit: int = None, offset: int = 0) -> Tuple[List[Track], int]:
    """Search tracks - returns (tracks, total) for pagination"""
    # ...
    total = session.query(Track).filter(...).count()
    results = session.query(Track).filter(...).limit(limit).offset(offset).all()
    return results, total
```

**Methods to standardize:**
- `TrackRepository.search()` → return `(List[Track], int)`
- `TrackRepository.get_favorites()` → return `(List[Track], int)`
- `TrackRepository.get_recent()` → return `(List[Track], int)`
- `AlbumRepository.search()` → return `(List[Album], int)`
- `ArtistRepository.search()` → return `(List[Artist], int)`

**Files to modify:**
- `auralis/library/repositories/track_repository.py`
- `auralis/library/repositories/album_repository.py`
- `auralis/library/repositories/artist_repository.py`
- `auralis/library/manager.py` - Update wrapper methods

**Breaking change mitigation:**
- Add deprecation warnings to old behavior
- Update all tests to use new return format
- Update documentation

#### Task 2.2: Add Type Hints (1-2 hours)

**Goal:** Full type coverage for all manager methods

```python
from typing import List, Tuple, Optional, Dict, Any

class LibraryManager:
    def get_all_tracks(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Tuple[List[Track], int]:
        """Get all tracks with pagination"""
        # ...

    def search_tracks(
        self,
        query: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Tuple[List[Track], int]:
        """Search tracks with pagination"""
        # ...

    def get_track(self, track_id: int) -> Optional[Track]:
        """Get single track by ID"""
        # ...
```

**Files to modify:**
- All files in `auralis/library/`

**Validation:**
- Run `mypy auralis/library/` (should pass with no errors)
- Update IDE autocomplete tests

#### Task 2.3: Update Tests for New Return Types (2-3 hours)

**Update all tests to expect tuples:**

```python
# BEFORE (Phase 1 tests)
tracks = manager.search_tracks("query")
assert len(tracks) == expected_count

# AFTER (Phase 2 tests)
tracks, total = manager.search_tracks("query")
assert len(tracks) == expected_count
assert total >= len(tracks)  # Total can be higher due to pagination
```

**Files to modify:**
- All 6 `tests/backend/test_boundary_*.py` files
- `tests/backend/test_library_*.py` files
- Any other tests using search/favorites/recent methods

**Expected changes:**
- ~50-60 test updates
- All 6 remaining failures should be fixed
- Pass rate: 91% → 100% (on non-skipped tests)

---

### Week 3: Documentation and Guidelines

**Goal:** Prevent future API inconsistencies

#### Task 3.1: Create API Design Guidelines (3-4 hours)

**Document:** `docs/development/API_DESIGN_GUIDELINES.md`

**Contents:**
```markdown
# API Design Guidelines

## Return Type Standards

### Paginated Queries
All paginated queries MUST return `(data, total)` tuple:
- `data`: List of results for current page
- `total`: Total count of all matching items

Examples:
- ✅ `get_all_tracks(limit, offset) -> Tuple[List[Track], int]`
- ❌ `get_all_tracks(limit, offset) -> List[Track]`

### Single Item Queries
Single item queries return `Optional[T]`:
- ✅ `get_track(id) -> Optional[Track]`
- ❌ `get_track(id) -> Track` (raises exception on not found)

### Mutation Operations
Mutations return the affected object or boolean:
- ✅ `delete_track(id) -> bool` (True if deleted, False if not found)
- ✅ `update_track(id, info) -> Optional[Track]` (None if not found)
- ❌ `delete_track(id) -> None` (no feedback on success)

## Cache Invalidation Standards

### Pattern-Based Invalidation
Always invalidate minimum necessary caches:

```python
def delete_track(self, track_id: int) -> bool:
    result = self.tracks.delete(track_id)
    if result:
        # Only invalidate queries that include deleted track
        invalidate_cache('get_all_tracks')  # Track lists
        invalidate_cache('get_track')        # Single track lookups
        invalidate_cache('search_tracks')    # Search results
        # DON'T invalidate favorites/recent unless track was favorite/recent
    return result
```

### Full Cache Clear
Only use full clear as fallback:
```python
# Use sparingly!
invalidate_cache()  # Clears EVERYTHING
```

## Method Naming Standards

### Query Methods
- `get_X()` - Single item by ID, returns `Optional[X]`
- `get_all_X()` - Paginated list, returns `(List[X], int)`
- `search_X()` - Filtered list, returns `(List[X], int)`

### Mutation Methods
- `add_X()` - Create new, returns `Optional[X]`
- `update_X()` - Modify existing, returns `Optional[X]`
- `delete_X()` - Remove, returns `bool`
- `set_X_Y()` - Set attribute, returns `None` or `bool`

## Type Hint Requirements

All public methods MUST have:
- Parameter type hints
- Return type hints
- Docstring with Args/Returns sections

Example:
```python
def search_tracks(
    self,
    query: str,
    limit: Optional[int] = None,
    offset: int = 0
) -> Tuple[List[Track], int]:
    """
    Search tracks by query string.

    Args:
        query: Search query (matches title, artist, album)
        limit: Maximum results to return (None = all)
        offset: Number of results to skip

    Returns:
        Tuple of (matching tracks, total count)
    """
```
```

**Files to create:**
- `docs/development/API_DESIGN_GUIDELINES.md`

#### Task 3.2: Update Repository Pattern Documentation (1-2 hours)

**Document:** `docs/guides/REPOSITORY_PATTERN.md`

**Contents:**
- Why repository pattern?
- How to add new repositories
- Cache integration guidelines
- Testing repositories
- Common pitfalls

#### Task 3.3: Create Cache System Documentation (1-2 hours)

**Document:** `docs/guides/CACHE_SYSTEM.md`

**Contents:**
- How the cache works
- Pattern-based invalidation
- Performance characteristics
- When to use caching
- Debugging cache issues

---

## Testing Strategy

### Test Coverage Goals

- **Week 1:** Add 15-20 cache invalidation tests
- **Week 2:** Update 50-60 existing tests for new return types
- **Week 3:** Add 10-15 API contract tests

**Total new tests:** ~30-40
**Updated tests:** ~50-60
**Final test count:** ~180 boundary tests (up from 143)

### Test Categories

**Cache Tests:**
- Pattern-based invalidation correctness
- Cache hit rate benchmarks
- Cross-cache interaction tests
- Concurrency safety tests

**API Contract Tests:**
- Return type validation
- Type hint compliance
- Pagination consistency
- Error handling standards

**Regression Tests:**
- Phase 1 bugs don't reappear
- Cache invalidation bug fixed
- API mismatches resolved

---

## Success Criteria

### Must Have (P0)

✅ **Cache system refactored** with pattern-based invalidation
✅ **API return types standardized** across all methods
✅ **100% pass rate** on non-skipped tests (up from 91%)
✅ **API design guidelines** documented

### Should Have (P1)

✅ **Cache hit rate > 80%** after mutations
✅ **Type hints on all manager methods**
✅ **Repository pattern documented**
✅ **30+ new tests** for cache behavior

### Nice to Have (P2)

- Create missing modules for 8 skipped tests
- Add property-based testing for invariants
- Performance benchmarks for cache system
- API versioning strategy

---

## Risk Mitigation

### Breaking Changes

**Risk:** API return type changes break existing code

**Mitigation:**
- Add deprecation warnings before removing old behavior
- Update all internal tests first
- Document migration path in CHANGELOG
- Version bump to 1.1.0 (minor version)

### Performance Regression

**Risk:** Pattern-based cache invalidation slower than full clear

**Mitigation:**
- Benchmark before/after
- Optimize pattern matching algorithm
- Add caching of pattern matches
- Fallback to full clear if pattern matching too slow

### Cache Complexity

**Risk:** Pattern-based invalidation has edge cases

**Mitigation:**
- Comprehensive test suite (30+ tests)
- Conservative invalidation (clear more rather than less)
- Full clear fallback for complex scenarios
- Document invalidation patterns clearly

---

## Dependencies

**None** - Phase 2 is self-contained, doesn't depend on external changes.

---

## Deliverables

### Code Changes

1. **auralis/library/cache.py** - Refactored cache system
2. **auralis/library/manager.py** - Updated invalidation calls
3. **auralis/library/repositories/*.py** - Standardized return types
4. **tests/backend/test_cache_invalidation.py** - New cache tests
5. **tests/backend/test_boundary_*.py** - Updated for new return types

### Documentation

1. **docs/development/API_DESIGN_GUIDELINES.md** - API standards
2. **docs/guides/REPOSITORY_PATTERN.md** - Repository guide
3. **docs/guides/CACHE_SYSTEM.md** - Cache guide
4. **docs/development/PHASE2_COMPLETE.md** - Phase 2 summary

### Metrics

- **Test pass rate:** 91% → 100% (non-skipped)
- **Cache hit rate:** 0% → 80%+ (after mutations)
- **API consistency:** 3 return type patterns → 1 standard
- **Documentation:** 3 new guides

---

## Next Steps (Phase 3)

After Phase 2 completion:

1. **Refactor 200 existing tests** to match Phase 1 quality
2. **Add 300 more tests** to reach 600 total
3. **Achieve 85%+ code coverage**
4. **Implement property-based testing** for invariants
5. **Add mutation testing** with >80% mutation score

---

**Prepared by:** Claude Code
**Phase:** 2 of 4
**Status:** 🚀 Active
**Target Completion:** 3 weeks from start
