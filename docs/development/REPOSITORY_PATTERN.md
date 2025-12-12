# Repository Pattern in Auralis

## Overview

The Repository Pattern provides a consistent abstraction layer for all database access operations in Auralis. This pattern ensures:

- **Testability**: Business logic can be tested without database dependencies
- **Maintainability**: Database queries are centralized and easy to update
- **Consistency**: All data access follows the same patterns and conventions
- **Separation of Concerns**: Routers/Services handle business logic; repositories handle data access

## Core Principles

### 1. Session Management

All repositories use the session factory pattern to manage database sessions:

```python
class MyRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def get_by_id(self, id: int) -> Optional[MyModel]:
        session = self.get_session()
        try:
            result = session.query(MyModel).filter(MyModel.id == id).first()
            if result:
                session.expunge(result)
            return result
        finally:
            session.close()
```

**Key Points:**
- Each method gets a fresh session via `session_factory()`
- Always use try-finally to ensure session cleanup
- Call `session.close()` in the finally block

### 2. Object Detachment (CRITICAL)

Objects must be detached from the session before returning, using `session.expunge()`:

```python
# ❌ WRONG - Returns attached object
def get_by_id(self, id: int):
    session = self.get_session()
    try:
        return session.query(MyModel).filter(...).first()
    finally:
        session.close()  # Session closed but object still attached -> errors later

# ✅ CORRECT - Detaches before returning
def get_by_id(self, id: int):
    session = self.get_session()
    try:
        obj = session.query(MyModel).filter(...).first()
        if obj:
            session.expunge(obj)  # Detach from session
        return obj
    finally:
        session.close()
```

**Why This Matters:**
- Detached objects can be used outside the session context
- Prevents "object is already attached to session" errors
- Allows multiple sessions to operate independently
- Critical for concurrent and async operations

### 3. Pagination Standard

Pagination always returns a tuple of `(results, total_count)`:

```python
def get_all(self, limit: int = 50, offset: int = 0) -> tuple[List[Model], int]:
    """
    Get paginated results.

    Returns:
        Tuple of (results list, total count)
    """
    session = self.get_session()
    try:
        total = session.query(Model).count()
        results = (
            session.query(Model)
            .limit(limit)
            .offset(offset)
            .all()
        )

        for obj in results:
            session.expunge(obj)

        return results, total
    finally:
        session.close()
```

**Benefits:**
- Consistent return type across all repositories
- Enables pagination UI (show "5 of 50 items")
- Single query for both data and total count

### 4. Eager Loading for N+1 Prevention

Use `joinedload()` to prevent N+1 query problems:

```python
# ❌ WRONG - Causes N+1 queries
def get_albums(self):
    session = self.get_session()
    try:
        albums = session.query(Album).all()
        # Accessing album.artist for each album triggers N+1 queries
        return [(album.title, album.artist.name) for album in albums]
    finally:
        session.close()

# ✅ CORRECT - Eager loads relationships
def get_albums(self):
    from sqlalchemy.orm import joinedload

    session = self.get_session()
    try:
        albums = (
            session.query(Album)
            .options(joinedload(Album.artist))  # Load artist in same query
            .all()
        )

        for album in albums:
            session.expunge(album)

        return albums
    finally:
        session.close()
```

**Common Eager Load Patterns:**
- `joinedload(Model.relationship)` - Single JOIN query
- `selectinload(Model.relationship)` - Separate query for related objects
- Chain multiple: `.options(joinedload(A.b), joinedload(A.c))`

### 5. Transaction Handling for Writes

Write operations (create, update, delete) must handle transactions properly:

```python
def create(self, **data) -> Model:
    """Create and commit in transaction with rollback on error."""
    session = self.get_session()
    try:
        obj = Model(**data)
        session.add(obj)
        session.commit()          # Commit transaction
        session.refresh(obj)      # Get auto-generated ID
        session.expunge(obj)      # Detach before returning
        return obj
    except Exception as e:
        session.rollback()         # Roll back on any error
        raise                      # Re-raise the exception
    finally:
        session.close()

def delete(self, id: int) -> bool:
    """Delete with proper transaction handling."""
    session = self.get_session()
    try:
        obj = session.query(Model).filter(Model.id == id).first()
        if not obj:
            return False

        session.delete(obj)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
```

**Critical Points:**
- **Always use try-except-rollback** for write operations
- Call `session.refresh()` after commit to update auto-generated fields (ID, timestamps)
- Call `session.expunge()` after refresh to detach
- Re-raise exceptions after rollback (don't swallow errors)

## Available Repositories

### Core Entity Repositories
- **TrackRepository** - Track CRUD, metadata updates, missing file cleanup
- **AlbumRepository** - Album operations, artwork management
- **ArtistRepository** - Artist queries and management
- **GenreRepository** - Genre CRUD, track-by-genre queries
- **PlaylistRepository** - Playlist CRUD, track ordering

### Specialized Repositories
- **FingerprintRepository** - Audio fingerprinting, fingerprint stats, cleanup
- **QueueRepository** - Playback queue state management
- **QueueHistoryRepository** - Undo/redo history
- **QueueTemplateRepository** - Saved queue templates
- **SettingsRepository** - Application settings
- **StatsRepository** - Library analytics and statistics

## Creating a New Repository

### Template
```python
"""
[Entity] Repository
~~~~~~~~~~~~~~~~~~

Data access layer for [entity] operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, List, Callable
from sqlalchemy.orm import Session
import logging

from ..models import MyModel

logger = logging.getLogger(__name__)


class MyModelRepository:
    """Repository for [entity] database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def get_by_id(self, id: int) -> Optional[MyModel]:
        """Get [entity] by ID"""
        session = self.get_session()
        try:
            obj = session.query(MyModel).filter(MyModel.id == id).first()
            if obj:
                session.expunge(obj)
            return obj
        finally:
            session.close()

    def get_all(self, limit: int = 50, offset: int = 0) -> tuple[List[MyModel], int]:
        """Get all [entities] with pagination"""
        session = self.get_session()
        try:
            total = session.query(MyModel).count()
            results = (
                session.query(MyModel)
                .limit(limit)
                .offset(offset)
                .all()
            )

            for obj in results:
                session.expunge(obj)

            return results, total
        finally:
            session.close()

    def create(self, **data) -> MyModel:
        """Create a new [entity]"""
        session = self.get_session()
        try:
            obj = MyModel(**data)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            session.expunge(obj)
            return obj
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def update(self, id: int, **fields) -> Optional[MyModel]:
        """Update [entity] fields"""
        session = self.get_session()
        try:
            obj = session.query(MyModel).filter(MyModel.id == id).first()
            if not obj:
                return None

            for key, value in fields.items():
                if hasattr(obj, key) and value is not None:
                    setattr(obj, key, value)

            session.commit()
            session.refresh(obj)
            session.expunge(obj)
            return obj
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, id: int) -> bool:
        """Delete [entity] by ID"""
        session = self.get_session()
        try:
            obj = session.query(MyModel).filter(MyModel.id == id).first()
            if not obj:
                return False

            session.delete(obj)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
```

### Checklist
- ✅ Session factory pattern
- ✅ Try-finally cleanup (all methods)
- ✅ Object detachment with `session.expunge()`
- ✅ Pagination returns `(results, total_count)` tuple
- ✅ Transaction rollback on write errors
- ✅ Type hints on all methods
- ✅ Docstrings for public methods
- ✅ Logging for important operations
- ✅ Registered in `__init__.py` exports

## Common Patterns

### Searching with Text Query
```python
def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[List[Model], int]:
    """Search models by text (case-insensitive)"""
    session = self.get_session()
    try:
        filter_expr = Model.name.ilike(f"%{query}%")
        total = session.query(Model).filter(filter_expr).count()

        results = (
            session.query(Model)
            .filter(filter_expr)
            .order_by(Model.name)
            .limit(limit)
            .offset(offset)
            .all()
        )

        for obj in results:
            session.expunge(obj)

        return results, total
    finally:
        session.close()
```

### Filtering with Multiple Conditions
```python
def search_by_filters(self, artist_id=None, genre_id=None, year=None):
    """Search tracks with multiple optional filters"""
    session = self.get_session()
    try:
        filters = []

        if artist_id is not None:
            filters.append(Track.artist_id == artist_id)
        if genre_id is not None:
            filters.append(Track.genre_id == genre_id)
        if year is not None:
            filters.append(Track.year == year)

        query = session.query(Track)
        if filters:
            query = query.filter(*filters)  # Apply all filters

        results = query.all()

        for obj in results:
            session.expunge(obj)

        return results
    finally:
        session.close()
```

### Batch Operations
```python
def delete_batch(self, ids: List[int]) -> int:
    """Delete multiple models by ID"""
    session = self.get_session()
    try:
        count = (
            session.query(Model)
            .filter(Model.id.in_(ids))
            .delete(synchronize_session=False)  # Don't sync session
        )
        session.commit()
        return count
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
```

### Counting with Filters
```python
def count_by_artist(self, artist_id: int) -> int:
    """Count tracks by artist"""
    session = self.get_session()
    try:
        count = (
            session.query(Track)
            .filter(Track.artist_id == artist_id)
            .count()
        )
        return count
    finally:
        session.close()
```

## Anti-Patterns (DO NOT USE)

### ❌ Direct Session Usage in Routers
```python
# WRONG - Router should never access database directly
@router.get("/api/tracks/{track_id}")
async def get_track(track_id: int):
    session = library_manager.session.query(Track).filter(...).first()
    return track
```

**Fix:** Use repository through library_manager
```python
# CORRECT - Use repository abstraction
@router.get("/api/tracks/{track_id}")
async def get_track(track_id: int):
    track = library_manager.tracks.get_by_id(track_id)
    return track
```

### ❌ No Object Detachment
```python
# WRONG - Session closes but object stays attached
def get_by_id(self, id: int):
    session = self.get_session()
    try:
        return session.query(Model).first()  # Returns attached object
    finally:
        session.close()
```

### ❌ Manual Transaction Management in Routers
```python
# WRONG - Router should not commit database
def update_track(track_id: int, data: dict):
    track = library_manager.tracks.get_by_id(track_id)
    track.title = data['title']
    session = object_session(track)
    session.commit()  # Don't do this in routers
```

**Fix:** Use repository method that handles transaction
```python
# CORRECT - Repository handles transaction
def update_track(track_id: int, data: dict):
    track = library_manager.tracks.update_metadata(
        track_id,
        title=data['title']
    )
```

### ❌ Lazy Loading After Session Closes
```python
# WRONG - Accessing related objects after session closed
def get_album_with_artist(self, album_id: int):
    session = self.get_session()
    try:
        album = session.query(Album).filter(...).first()
        session.expunge(album)
        return album  # album.artist access later will fail
    finally:
        session.close()
```

**Fix:** Use eager loading
```python
# CORRECT - Eager load all needed relationships
from sqlalchemy.orm import joinedload

def get_album_with_artist(self, album_id: int):
    session = self.get_session()
    try:
        album = (
            session.query(Album)
            .options(joinedload(Album.artist))  # Load artist
            .filter(...)
            .first()
        )
        if album:
            session.expunge(album)
        return album  # album.artist is now available
    finally:
        session.close()
```

## Testing Repositories

### Unit Test with Mocked Session
```python
from unittest.mock import Mock, MagicMock

def test_get_by_id():
    # Mock session factory
    mock_session = Mock()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    session_factory = lambda: mock_session
    repo = MyRepository(session_factory)

    result = repo.get_by_id(1)

    assert result is None
    mock_session.close.assert_called_once()
```

### Integration Test with Real Database
```python
@pytest.mark.integration
def test_create_and_retrieve():
    from auralis.library.repositories import TrackRepository

    # Create track
    track = TrackRepository.create(
        title="Test Track",
        filepath="/tmp/test.wav"
    )
    assert track.id is not None

    # Retrieve track
    retrieved = TrackRepository.get_by_id(track.id)
    assert retrieved.title == "Test Track"

    # Clean up
    TrackRepository.delete(track.id)
```

## Troubleshooting

### "Object is already attached to session"
**Cause:** Trying to attach an object that's already attached to another session
**Fix:** Call `session.expunge(obj)` before returning from repository

### "Session is closed"
**Cause:** Accessing lazy-loaded relationships after session closes
**Fix:** Use eager loading with `joinedload()` in the query

### "Database is locked"
**Cause:** Long-running transactions blocking others
**Fix:** Keep transactions short, commit/rollback quickly

### "No such table"
**Cause:** Model defined but table not created
**Fix:** Run `python -m auralis.library.init` to initialize database

## References

- **SQLAlchemy Session**: https://docs.sqlalchemy.org/en/20/orm/session.html
- **Repository Pattern**: https://martinfowler.com/eaaCatalog/repository.html
- **Data Mapper Pattern**: https://martinfowler.com/eaaCatalog/dataMapper.html
