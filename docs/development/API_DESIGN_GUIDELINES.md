# API Design Guidelines

**Version:** 1.0
**Date:** November 7, 2024
**Status:** Official Standards

This document defines the official API design standards for the Auralis library management system.

---

## Table of Contents

1. [Return Type Standards](#return-type-standards)
2. [Method Naming Conventions](#method-naming-conventions)
3. [Type Hint Requirements](#type-hint-requirements)
4. [Cache Invalidation Patterns](#cache-invalidation-patterns)
5. [Error Handling Standards](#error-handling-standards)
6. [Pagination Conventions](#pagination-conventions)
7. [Examples and Anti-Patterns](#examples-and-anti-patterns)

---

## Return Type Standards

### Principle: Consistency is King

All similar operations must return the same type structure. Users should never guess what a method returns.

### Paginated Queries

**Rule:** All paginated queries MUST return `tuple[List[T], int]`

**Format:** `(data, total_count)`

**Examples:**
```python
# ✅ CORRECT - Returns tuple
def get_all_tracks(self, limit: int = 50, offset: int = 0) -> tuple[List[Track], int]:
    """Returns: Tuple of (track list, total count)"""
    tracks, total = self.repository.get_all(limit, offset)
    return tracks, total

def search_tracks(self, query: str, limit: int = 50, offset: int = 0) -> tuple[List[Track], int]:
    """Returns: Tuple of (matching tracks, total count)"""
    results, total = self.repository.search(query, limit, offset)
    return results, total

# ❌ WRONG - Inconsistent return types
def get_all_tracks(...) -> tuple[List[Track], int]:  # Returns tuple
    return tracks, total

def search_tracks(...) -> List[Track]:  # Returns list only!
    return tracks  # No total count - inconsistent!
```

**Why tuple?**
- Provides total count for pagination UI
- Enables "Showing X of Y" displays
- Supports "Load More" functionality
- Frontend can calculate total pages

### Single Item Queries

**Rule:** Single item lookups return `Optional[T]`

**Examples:**
```python
# ✅ CORRECT
def get_track(self, track_id: int) -> Optional[Track]:
    """Returns: Track if found, None otherwise"""
    return self.repository.get_by_id(track_id)

def get_album(self, album_id: int) -> Optional[Album]:
    """Returns: Album if found, None otherwise"""
    return self.repository.get_by_id(album_id)

# ❌ WRONG - Raises exception instead of returning None
def get_track(self, track_id: int) -> Track:
    """Returns: Track (raises KeyError if not found)"""
    track = self.repository.get_by_id(track_id)
    if not track:
        raise KeyError(f"Track {track_id} not found")
    return track
```

**Why Optional[T]?**
- Graceful handling of missing items
- No exceptions for expected "not found" cases
- Explicit in type signature that None is possible
- Forces callers to handle None case

### Mutation Operations

**Rule:** Mutations return the affected object or boolean status

**Create/Update:**
```python
# ✅ CORRECT - Return created/updated object
def add_track(self, track_info: dict) -> Optional[Track]:
    """Returns: Created track or None if failed"""
    return self.repository.add(track_info)

def update_track(self, track_id: int, track_info: dict) -> Optional[Track]:
    """Returns: Updated track or None if not found"""
    return self.repository.update(track_id, track_info)
```

**Delete:**
```python
# ✅ CORRECT - Return boolean success
def delete_track(self, track_id: int) -> bool:
    """Returns: True if deleted, False if not found"""
    return self.repository.delete(track_id)
```

**Set Attribute:**
```python
# ✅ CORRECT - Return None (operation always succeeds or raises)
def set_track_favorite(self, track_id: int, favorite: bool = True) -> None:
    """Set track favorite status"""
    self.repository.set_favorite(track_id, favorite)

# Alternative: Return bool if operation can fail
def set_track_favorite(self, track_id: int, favorite: bool = True) -> bool:
    """Returns: True if updated, False if track not found"""
    return self.repository.set_favorite(track_id, favorite)
```

---

## Method Naming Conventions

### Query Methods

**Pattern:** `get_<noun>` or `get_all_<noun>` or `search_<noun>`

```python
# Single item by ID
get_track(track_id: int) -> Optional[Track]
get_album(album_id: int) -> Optional[Album]
get_playlist(playlist_id: int) -> Optional[Playlist]

# All items (paginated)
get_all_tracks(limit, offset) -> tuple[List[Track], int]
get_all_albums(limit, offset) -> tuple[List[Album], int]

# Filtered items (paginated)
get_favorite_tracks(limit, offset) -> tuple[List[Track], int]
get_recent_tracks(limit, offset) -> tuple[List[Track], int]
get_popular_tracks(limit, offset) -> tuple[List[Track], int]

# Search (paginated)
search_tracks(query, limit, offset) -> tuple[List[Track], int]
search_albums(query, limit, offset) -> tuple[List[Album], int]
```

### Mutation Methods

**Pattern:** `<verb>_<noun>`

```python
# Create
add_track(track_info: dict) -> Optional[Track]
create_playlist(name: str, description: str) -> Optional[Playlist]

# Update
update_track(track_id: int, track_info: dict) -> Optional[Track]
update_playlist(playlist_id: int, update_data: dict) -> bool

# Delete
delete_track(track_id: int) -> bool
delete_playlist(playlist_id: int) -> bool

# Set attribute
set_track_favorite(track_id: int, favorite: bool) -> None
record_track_play(track_id: int) -> None
```

### Avoid Ambiguous Names

```python
# ❌ WRONG - Ambiguous what it returns
def tracks(...) -> ???  # Is this get_tracks? search_tracks? all tracks?

# ❌ WRONG - Unclear if it's a query or mutation
def favorite(track_id: int) -> ???  # Get favorites? Set favorite? Toggle?

# ✅ CORRECT - Clear intent
def get_all_tracks(...) -> tuple[List[Track], int]
def set_track_favorite(track_id: int, favorite: bool) -> None
def get_favorite_tracks(...) -> tuple[List[Track], int]
```

---

## Type Hint Requirements

### Mandatory Type Hints

**Rule:** ALL public methods MUST have type hints on:
1. All parameters
2. Return value

```python
# ✅ CORRECT - Full type hints
def search_tracks(
    self,
    query: str,
    limit: int = 50,
    offset: int = 0
) -> tuple[List[Track], int]:
    """
    Search tracks by query.

    Args:
        query: Search query string
        limit: Maximum results to return
        offset: Number of results to skip

    Returns:
        Tuple of (matching tracks, total count)
    """
    return self.repository.search(query, limit, offset)

# ❌ WRONG - Missing type hints
def search_tracks(self, query, limit=50, offset=0):
    return self.repository.search(query, limit, offset)
```

### Complex Type Hints

**Use standard typing module:**
```python
from typing import List, Dict, Optional, Tuple, Any, Union

# Collections
List[Track]
Dict[str, Any]
tuple[List[Track], int]  # Python 3.9+ syntax

# Optional values
Optional[Track]  # Same as Union[Track, None]

# Multiple possible types
Union[Track, Album]

# Any type (use sparingly)
Dict[str, Any]  # For flexible dictionaries
```

### Docstring Requirements

**Rule:** All public methods MUST have docstrings with Args and Returns sections

```python
def search_tracks(
    self,
    query: str,
    limit: int = 50,
    offset: int = 0
) -> tuple[List[Track], int]:
    """
    Search tracks by title, artist, album, or genre.

    Args:
        query: Search query string (case-insensitive)
        limit: Maximum number of results to return (default: 50)
        offset: Number of results to skip for pagination (default: 0)

    Returns:
        Tuple of (matching tracks, total count)

    Example:
        >>> tracks, total = manager.search_tracks("metallica", limit=10)
        >>> print(f"Found {total} tracks, showing {len(tracks)}")
        Found 42 tracks, showing 10
    """
    return self.repository.search(query, limit, offset)
```

---

## Cache Invalidation Patterns

### Principle: Invalidate Minimum Necessary

**Rule:** Only invalidate caches that are affected by the mutation

### Pattern-Based Invalidation

```python
from auralis.library.cache import invalidate_cache

# ✅ CORRECT - Targeted invalidation
def set_track_favorite(self, track_id: int, favorite: bool = True) -> None:
    """Set track favorite status"""
    self.repository.set_favorite(track_id, favorite)
    # Only invalidate favorite-related queries
    invalidate_cache('get_favorite_tracks')

def record_track_play(self, track_id: int) -> None:
    """Record track play"""
    self.repository.record_play(track_id)
    # Invalidate play count and recent queries
    invalidate_cache('get_popular_tracks', 'get_recent_tracks', 'get_all_tracks', 'get_track')

# ❌ WRONG - Full cache clear (too broad)
def set_track_favorite(self, track_id: int, favorite: bool = True) -> None:
    self.repository.set_favorite(track_id, favorite)
    invalidate_cache()  # Clears EVERYTHING including unrelated caches!
```

### Invalidation Strategies by Operation

**Add track:**
```python
def add_track(self, track_info: dict) -> Optional[Track]:
    track = self.repository.add(track_info)
    if track:
        # Invalidate queries listing tracks
        invalidate_cache('get_all_tracks', 'search_tracks', 'get_recent_tracks')
    return track
```

**Update track metadata:**
```python
def update_track(self, track_id: int, track_info: dict) -> Optional[Track]:
    track = self.repository.update(track_id, track_info)
    if track:
        # Invalidate queries showing metadata
        invalidate_cache('get_track', 'search_tracks', 'get_all_tracks')
    return track
```

**Delete track:**
```python
def delete_track(self, track_id: int) -> bool:
    result = self.repository.delete(track_id)
    if result:
        # Broad invalidation (delete affects many queries)
        invalidate_cache('get_all_tracks', 'get_track', 'search_tracks',
                         'get_favorite_tracks', 'get_recent_tracks', 'get_popular_tracks')
    return result
```

**Set favorite:**
```python
def set_track_favorite(self, track_id: int, favorite: bool = True) -> None:
    self.repository.set_favorite(track_id, favorite)
    # Only favorites affected
    invalidate_cache('get_favorite_tracks')
```

**Record play:**
```python
def record_track_play(self, track_id: int) -> None:
    self.repository.record_play(track_id)
    # Play count and recent affected
    invalidate_cache('get_popular_tracks', 'get_recent_tracks', 'get_all_tracks', 'get_track')
```

### When to Use Full Clear

**Use `invalidate_cache()` (no args) only when:**
1. You don't know which caches are affected
2. The operation is rare and performance doesn't matter
3. It's a debug/maintenance operation

```python
# ✅ ACCEPTABLE - Maintenance operation
def cleanup_library(self) -> None:
    """Remove tracks with missing files (rare operation)"""
    self.repository.cleanup_missing_files()
    invalidate_cache()  # Full clear is fine for rare maintenance

# ✅ ACCEPTABLE - Unknown impact
def rebuild_indexes(self) -> None:
    """Rebuild database indexes"""
    self.repository.rebuild_indexes()
    invalidate_cache()  # Full clear since indexes affect all queries
```

---

## Error Handling Standards

### Principle: Graceful Degradation

**Rule:** Expected failures return None/False, unexpected failures raise exceptions

### Expected Failures (Return None/False)

```python
# ✅ CORRECT - Return None for "not found"
def get_track(self, track_id: int) -> Optional[Track]:
    """Returns: Track if found, None otherwise"""
    track = self.repository.get_by_id(track_id)
    if not track:
        return None  # Expected case
    return track

# ✅ CORRECT - Return False for "already deleted"
def delete_track(self, track_id: int) -> bool:
    """Returns: True if deleted, False if not found"""
    result = self.repository.delete(track_id)
    return result  # False if track doesn't exist
```

### Unexpected Failures (Raise Exception)

```python
# ✅ CORRECT - Raise for database errors
def add_track(self, track_info: dict) -> Optional[Track]:
    """Returns: Created track or None if validation fails"""
    try:
        track = self.repository.add(track_info)
        return track
    except ValidationError as e:
        # Expected validation failure - return None
        logger.warning(f"Track validation failed: {e}")
        return None
    except DatabaseError as e:
        # Unexpected database error - reraise
        logger.error(f"Database error adding track: {e}")
        raise
```

### Input Validation

```python
# ✅ CORRECT - Validate early, fail fast
def search_tracks(
    self,
    query: str,
    limit: int = 50,
    offset: int = 0
) -> tuple[List[Track], int]:
    """Search tracks"""
    # Validate inputs
    if not isinstance(query, str):
        raise TypeError(f"query must be str, got {type(query)}")
    if limit < 1 or limit > 1000:
        raise ValueError(f"limit must be 1-1000, got {limit}")
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset}")

    return self.repository.search(query, limit, offset)
```

---

## Pagination Conventions

### Standard Parameters

**Rule:** All paginated methods use `limit` and `offset` parameters

```python
def get_all_<noun>(
    self,
    limit: int = 50,      # Maximum results per page
    offset: int = 0,      # Number of results to skip
    order_by: str = 'title'  # Optional: sort column
) -> tuple[List[T], int]:
    """
    Args:
        limit: Maximum results to return (default: 50, max: 1000)
        offset: Number of results to skip (default: 0)
        order_by: Column to sort by (default: 'title')

    Returns:
        Tuple of (results list, total count)
    """
    ...
```

### Limits and Defaults

**Recommended defaults:**
- Default limit: **50** (good balance)
- Maximum limit: **1000** (prevent abuse)
- Default offset: **0** (start at beginning)

```python
# ✅ CORRECT - Enforce limits
def get_all_tracks(
    self,
    limit: int = 50,
    offset: int = 0
) -> tuple[List[Track], int]:
    # Clamp limit to max
    limit = min(limit, 1000)
    return self.repository.get_all(limit, offset)
```

### Page Calculation Example

```python
def get_page(self, page: int = 1, per_page: int = 50) -> dict:
    """
    Get paginated results by page number.

    Args:
        page: Page number (1-indexed)
        per_page: Results per page

    Returns:
        Dict with results and pagination info
    """
    offset = (page - 1) * per_page
    results, total = self.get_all_tracks(limit=per_page, offset=offset)

    total_pages = (total + per_page - 1) // per_page  # Ceiling division

    return {
        'results': results,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_next': page < total_pages,
        'has_prev': page > 1
    }
```

---

## Examples and Anti-Patterns

### Complete Good Example

```python
from typing import List, Optional, Dict, Any
from auralis.library.cache import cached_query, invalidate_cache

class LibraryManager:
    """Library management with proper API design"""

    @cached_query(ttl=60)
    def search_tracks(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Track], int]:
        """
        Search tracks by title, artist, album, or genre.

        Args:
            query: Search query (case-insensitive)
            limit: Max results (1-1000, default: 50)
            offset: Skip count (default: 0)

        Returns:
            Tuple of (matching tracks, total count)

        Example:
            >>> tracks, total = manager.search_tracks("metallica")
            >>> print(f"Found {total} tracks")
            Found 42 tracks
        """
        # Validate inputs
        if not query:
            return [], 0
        limit = min(max(limit, 1), 1000)
        offset = max(offset, 0)

        # Delegate to repository
        return self.repository.search(query, limit, offset)

    def add_track(self, track_info: Dict[str, Any]) -> Optional[Track]:
        """
        Add a track to the library.

        Args:
            track_info: Track metadata dictionary

        Returns:
            Created track or None if validation failed

        Raises:
            DatabaseError: If database operation fails
        """
        track = self.repository.add(track_info)
        if track:
            # Targeted cache invalidation
            invalidate_cache('get_all_tracks', 'search_tracks', 'get_recent_tracks')
        return track

    def get_track(self, track_id: int) -> Optional[Track]:
        """
        Get track by ID.

        Args:
            track_id: Track ID

        Returns:
            Track if found, None otherwise
        """
        return self.repository.get_by_id(track_id)

    def delete_track(self, track_id: int) -> bool:
        """
        Delete a track.

        Args:
            track_id: Track ID to delete

        Returns:
            True if deleted, False if not found
        """
        result = self.repository.delete(track_id)
        if result:
            # Broad invalidation for delete
            invalidate_cache(
                'get_all_tracks', 'get_track', 'search_tracks',
                'get_favorite_tracks', 'get_recent_tracks', 'get_popular_tracks'
            )
        return result
```

### Common Anti-Patterns

```python
# ❌ ANTI-PATTERN 1: Inconsistent return types
def get_all_tracks(...) -> tuple[List[Track], int]:  # Returns tuple
    return tracks, total

def search_tracks(...) -> List[Track]:  # Returns list - INCONSISTENT!
    return tracks

# ✅ CORRECT: Consistent
def get_all_tracks(...) -> tuple[List[Track], int]:
    return tracks, total

def search_tracks(...) -> tuple[List[Track], int]:  # Consistent!
    return tracks, total


# ❌ ANTI-PATTERN 2: Missing type hints
def search(query, limit=50):
    return self.repo.search(query, limit)

# ✅ CORRECT: Full type hints
def search_tracks(
    self,
    query: str,
    limit: int = 50
) -> tuple[List[Track], int]:
    return self.repository.search(query, limit)


# ❌ ANTI-PATTERN 3: Over-invalidation
def set_favorite(track_id, favorite):
    self.repo.set_favorite(track_id, favorite)
    invalidate_cache()  # Clears EVERYTHING!

# ✅ CORRECT: Targeted invalidation
def set_track_favorite(self, track_id: int, favorite: bool = True) -> None:
    self.repository.set_favorite(track_id, favorite)
    invalidate_cache('get_favorite_tracks')  # Only favorites


# ❌ ANTI-PATTERN 4: Raising exceptions for expected cases
def get_track(track_id):
    track = self.repo.get(track_id)
    if not track:
        raise KeyError("Track not found")  # Expected case!
    return track

# ✅ CORRECT: Return None for expected failures
def get_track(self, track_id: int) -> Optional[Track]:
    return self.repository.get_by_id(track_id)  # Returns None if not found


# ❌ ANTI-PATTERN 5: Ambiguous method names
def tracks():  # What does this return?
def favorite(id):  # Get or set?
def delete(id):  # Delete what?

# ✅ CORRECT: Clear names
def get_all_tracks() -> tuple[List[Track], int]:
def set_track_favorite(track_id: int, favorite: bool) -> None:
def delete_track(track_id: int) -> bool:
```

---

## Summary

### Quick Checklist

Before committing new API code, verify:

- [ ] Return type is consistent with similar methods
- [ ] Paginated queries return `(data, total)` tuple
- [ ] All parameters have type hints
- [ ] Return value has type hint
- [ ] Method name clearly indicates operation
- [ ] Docstring has Args and Returns sections
- [ ] Expected failures return None/False
- [ ] Unexpected failures raise exceptions
- [ ] Cache invalidation is targeted (not full clear)
- [ ] Input validation is performed early

### Reference

**For more examples, see:**
- `auralis/library/manager.py` - Manager layer API
- `auralis/library/repositories/track_repository.py` - Repository layer
- `tests/backend/test_cache_invalidation.py` - Cache patterns

---

**Last Updated:** November 7, 2024
**Version:** 1.0
**Maintainers:** Auralis Team
