# LibraryManager Deprecation - Migration Guide

## Overview

As of **Auralis v1.1.0**, `LibraryManager` is marked **DEPRECATED** in favor of the `RepositoryFactory` pattern. This guide helps you migrate your code to the new pattern.

**Timeline:**
- **v1.1.0** (current): LibraryManager deprecated, all methods still work
- **v1.2.0**: Deprecation warnings in all methods
- **v2.0.0+**: LibraryManager removed or converted to minimal facade only

---

## Quick Summary

### Old Pattern (Deprecated)
```python
from auralis.library.manager import LibraryManager

manager = LibraryManager()  # ⚠️ Warning emitted
tracks, total = manager.get_all_tracks(limit=50)
```

### New Pattern (Recommended)
```python
from auralis.library.repositories import RepositoryFactory
from sqlalchemy.orm import sessionmaker

factory = RepositoryFactory(SessionLocal)  # ✅ No warning
tracks, total = factory.tracks.get_all(limit=50)
```

**Key Benefits:**
- ✅ No deprecation warnings
- ✅ Explicit repository access (more type-safe)
- ✅ Better for dependency injection
- ✅ Cleaner separation of concerns

---

## Migration Examples

### Track Operations

#### Before (LibraryManager)
```python
from auralis.library.manager import LibraryManager

manager = LibraryManager()

# Add track
track = manager.add_track({'filepath': '/path/to/song.mp3', ...})

# Get track
track = manager.get_track(track_id=123)

# Search tracks
tracks, total = manager.search_tracks('query', limit=50)

# Get all tracks
tracks, total = manager.get_all_tracks(limit=50, offset=0)
```

#### After (RepositoryFactory)
```python
from auralis.library.repositories import RepositoryFactory
from sqlalchemy.orm import sessionmaker
from auralis.library.models import Base

engine = create_engine('sqlite:///path/to/database.db')
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

factory = RepositoryFactory(SessionLocal)

# Add track
track = factory.tracks.add({'filepath': '/path/to/song.mp3', ...})

# Get track
track = factory.tracks.get_by_id(track_id=123)

# Search tracks
tracks, total = factory.tracks.search('query', limit=50)

# Get all tracks
tracks, total = factory.tracks.get_all(limit=50, offset=0)
```

### Playlist Operations

#### Before (LibraryManager)
```python
manager = LibraryManager()

# Create playlist
playlist = manager.create_playlist('My Playlist')

# Add track to playlist
manager.add_track_to_playlist(playlist_id=1, track_id=123)

# Get playlist
playlist = manager.get_playlist(playlist_id=1)
```

#### After (RepositoryFactory)
```python
factory = RepositoryFactory(SessionLocal)

# Create playlist
playlist = factory.playlists.create('My Playlist')

# Add track to playlist
factory.playlists.add_track(playlist_id=1, track_id=123)

# Get playlist
playlist = factory.playlists.get_by_id(playlist_id=1)
```

### Statistics and Analytics

#### Before (LibraryManager)
```python
manager = LibraryManager()

# Record track play
manager.record_track_play(track_id=123)

# Set favorite
manager.set_track_favorite(track_id=123, favorite=True)

# Get stats
stats = manager.get_library_stats()
```

#### After (RepositoryFactory)
```python
factory = RepositoryFactory(SessionLocal)

# Record track play
factory.tracks.record_play(track_id=123)

# Set favorite
factory.tracks.set_favorite(track_id=123, favorite=True)

# Get stats
stats = factory.stats.get_library_stats()
```

---

## Repository Interface Reference

The `RepositoryFactory` provides access to 11 repositories, each with specific methods:

### TrackRepository (`factory.tracks`)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `add()` | `add(track_info: Dict) -> Track` | Add new track |
| `get_by_id()` | `get_by_id(track_id: int) -> Track` | Get track by ID |
| `get_by_path()` | `get_by_path(filepath: str) -> Track` | Get track by filepath |
| `get_all()` | `get_all(limit=50, offset=0, order_by='title') -> Tuple[List, int]` | Get all tracks with pagination |
| `search()` | `search(query: str, limit=50, offset=0) -> Tuple[List, int]` | Search tracks |
| `get_by_genre()` | `get_by_genre(genre_name: str, limit=100) -> List[Track]` | Get tracks by genre |
| `get_by_artist()` | `get_by_artist(artist_name: str, limit=100) -> List[Track]` | Get tracks by artist |
| `get_recent()` | `get_recent(limit=50, offset=0) -> Tuple[List, int]` | Get recently added tracks |
| `get_popular()` | `get_popular(limit=50, offset=0) -> Tuple[List, int]` | Get most played tracks |
| `get_favorites()` | `get_favorites(limit=50, offset=0) -> Tuple[List, int]` | Get favorite tracks |
| `record_play()` | `record_play(track_id: int) -> None` | Record track play |
| `set_favorite()` | `set_favorite(track_id: int, favorite: bool) -> None` | Set favorite status |
| `delete()` | `delete(track_id: int) -> bool` | Delete track |
| `update()` | `update(track_id: int, track_info: Dict) -> Track` | Update track metadata |
| `cleanup_missing_files()` | `cleanup_missing_files() -> int` | Remove tracks with missing files |
| `find_similar()` | `find_similar(track: Track, limit: int) -> List[Track]` | Find similar tracks |

### PlaylistRepository (`factory.playlists`)

| Method | Purpose |
|--------|---------|
| `create(name, description, track_ids)` | Create new playlist |
| `get_by_id(playlist_id)` | Get playlist by ID |
| `get_all()` | Get all playlists |
| `update(playlist_id, update_data)` | Update playlist |
| `delete(playlist_id)` | Delete playlist |
| `add_track(playlist_id, track_id)` | Add track to playlist |
| `remove_track(playlist_id, track_id)` | Remove track from playlist |
| `clear(playlist_id)` | Remove all tracks from playlist |

### Other Repositories

- **`factory.albums`** - Album queries (get_by_id, get_all, get_by_artist, etc.)
- **`factory.artists`** - Artist queries (get_by_id, get_all, search, etc.)
- **`factory.genres`** - Genre management
- **`factory.fingerprints`** - Fingerprint operations (cleanup_incomplete, etc.)
- **`factory.stats`** - Library statistics (get_library_stats, etc.)
- **`factory.queue`** - Queue management
- **`factory.settings`** - Settings storage
- **`factory.queue_history`** - Queue history tracking
- **`factory.queue_templates`** - Queue template management

---

## Dependency Injection Pattern (FastAPI Routers)

### Before (LibraryManager)
```python
# routers/library.py
from fastapi import APIRouter, Depends
from dependencies import require_library_manager, get_library_manager

router = APIRouter()

@router.get("/api/tracks")
async def get_tracks(limit: int = 50):
    manager = require_library_manager(get_library_manager)
    tracks, total = manager.get_all_tracks(limit=limit)
    return {"tracks": tracks, "total": total}
```

### After (RepositoryFactory)
```python
# routers/library.py
from fastapi import APIRouter, Depends
from dependencies import require_repository_factory, get_repository_factory

router = APIRouter()

@router.get("/api/tracks")
async def get_tracks(limit: int = 50):
    factory = require_repository_factory(get_repository_factory)
    tracks, total = factory.tracks.get_all(limit=limit)
    return {"tracks": tracks, "total": total}
```

---

## Database Initialization

### Before (LibraryManager)
```python
from auralis.library.manager import LibraryManager

# Manager handles database initialization
manager = LibraryManager(database_path="/path/to/database.db")
```

### After (RepositoryFactory)
```python
from auralis.library.repositories import RepositoryFactory
from auralis.library.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Explicit database setup
database_url = "sqlite:////path/to/database.db"
engine = create_engine(database_url)

# Create tables if needed
Base.metadata.create_all(engine)

# Create session factory
SessionLocal = sessionmaker(bind=engine)

# Create repository factory
factory = RepositoryFactory(SessionLocal)
```

---

## Cache Invalidation

### Before (LibraryManager)
```python
manager = LibraryManager()

# Automatic cache invalidation
manager.add_track(track_info)  # Invalidates caches automatically
```

### After (RepositoryFactory)
```python
from auralis.library.cache import invalidate_cache

factory = RepositoryFactory(SessionLocal)

# Manual cache invalidation when needed
factory.tracks.add(track_info)
invalidate_cache('get_all_tracks', 'search_tracks', ...)
```

---

## Backward Compatibility

**LibraryManager will continue to work** through v1.2.0 with deprecation warnings. This gives you time to migrate. However, to avoid warnings in your logs and prepare for v2.0.0, we recommend migrating as soon as possible.

### Suppressing Deprecation Warnings (Temporary)

If you need to temporarily suppress warnings while migrating:

```python
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="auralis.library.manager")

manager = LibraryManager()  # No warning shown
```

**⚠️ Note:** This is not recommended for production. Use only during migration period.

---

## Testing with RepositoryFactory

### Before (Pytest with LibraryManager)
```python
import pytest
from auralis.library.manager import LibraryManager

@pytest.fixture
def library_manager():
    manager = LibraryManager(database_path=":memory:")
    yield manager

def test_track_operations(library_manager):
    track = library_manager.add_track({'filepath': 'test.mp3', ...})
    assert track is not None
```

### After (Pytest with RepositoryFactory)
```python
import pytest
from auralis.library.repositories import RepositoryFactory
from auralis.library.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def repository_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return RepositoryFactory(SessionLocal)

def test_track_operations(repository_factory):
    track = repository_factory.tracks.add({'filepath': 'test.mp3', ...})
    assert track is not None
```

---

## Frequently Asked Questions

### Q: When will LibraryManager be removed?
**A:** v2.0.0 (estimated 3-6 months after v1.2.0). The deprecation window gives you time to migrate.

### Q: Will my code break immediately?
**A:** No. Deprecation warnings are shown, but all functionality continues to work. Breaking changes only occur in v2.0.0.

### Q: Can I use both patterns together?
**A:** Yes, during migration. You can gradually convert modules to use RepositoryFactory while keeping others on LibraryManager.

### Q: How do I handle cache invalidation with RepositoryFactory?
**A:** Import `invalidate_cache` from `auralis.library.cache` and call it explicitly after mutations.

```python
from auralis.library.cache import invalidate_cache

factory = RepositoryFactory(SessionLocal)
factory.tracks.add(track_info)
invalidate_cache('get_all_tracks', 'search_tracks')  # Explicit invalidation
```

### Q: What about transaction management?
**A:** Repositories handle session management internally. For advanced use cases, you can pass a custom session:

```python
session = SessionLocal()
try:
    # ... operations ...
    session.commit()
except:
    session.rollback()
finally:
    session.close()
```

### Q: Is RepositoryFactory thread-safe?
**A:** The factory itself is thread-safe for lazy initialization. However, repositories share a session factory, so you should create new sessions per thread/request (FastAPI does this automatically).

---

## Migration Checklist

- [ ] Create RepositoryFactory instance in application startup
- [ ] Update imports from `LibraryManager` to `RepositoryFactory`
- [ ] Replace manager method calls with repository methods
- [ ] Update cache invalidation calls
- [ ] Run tests to verify functionality
- [ ] Remove LibraryManager imports from production code
- [ ] Update type hints to use repositories
- [ ] Document new patterns in team documentation
- [ ] Verify no deprecation warnings in logs
- [ ] Plan removal of LibraryManager in future version

---

## Getting Help

If you encounter issues during migration:

1. **Check the Repository Interfaces** - Reference the table above for method names and signatures
2. **Review Examples** - Look at `auralis-web/backend/routers/` for RepositoryFactory usage examples
3. **Test Early** - Add tests to verify each converted module works correctly
4. **Enable Warnings** - Use `python -W always` to see all deprecation warnings

---

## See Also

- [Phase 6 Deprecation Plan](PHASE_6_DEPRECATION_PLAN.md) - Technical details of the deprecation strategy
- [Phase 5 Migration Overview](PHASE_5_MIGRATION_OVERVIEW.md) - Test suite migration details
- Repository source code: `auralis/library/repositories/`

