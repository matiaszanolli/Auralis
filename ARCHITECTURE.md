# Auralis Architecture — Service & Naming Conventions

This document records the cross-cutting conventions every new service,
processor, and repository must follow. For the processing-pipeline hierarchy
and the data flow, see [docs/architecture/overview.md](docs/architecture/overview.md)
and [docs/subsystems/dsp-engine.md](docs/subsystems/dsp-engine.md); for the
file-level layout, see [docs/architecture/module-map.md](docs/architecture/module-map.md).

## Service Architecture

### Repository Pattern

All database access MUST use the repository pattern via `RepositoryFactory`. Every repository extends `BaseRepository` (`auralis/library/repositories/base.py`), which centralises the session factory and the `get_session()` / `_session_scope()` lifecycle so a pooling, retry, or async change is a one-file edit:

```python
# ✅ CORRECT: Use repository pattern
repos = repository_factory.create()
track = repos.tracks.get_by_id(track_id)

# ❌ INCORRECT: Direct database access
session.query(Track).filter_by(id=track_id).first()
```

### Dependency Injection

Services should receive dependencies via constructor injection, not create them internally:

```python
# ✅ CORRECT: Dependency injection
class MyService:
    def __init__(self, get_repository: Callable[[], Any]):
        self._get_repository = get_repository

# ❌ INCORRECT: Internal instantiation
class MyService:
    def __init__(self):
        self._repos = repository_factory.create()  # Violates DI
```

### Lazy Imports

Avoid lazy imports (imports inside functions) - they indicate circular dependency issues:

```python
# ✅ CORRECT: Module-level imports
from auralis.library.repositories import TrackRepository

# ❌ INCORRECT: Lazy imports
def my_function():
    from auralis.library.repositories import TrackRepository  # Code smell
```

## Naming Conventions

### Processors vs Services vs Managers

- **Processor**: Transforms audio data (input → output)
  - Example: `HybridProcessor`, `ChunkedAudioProcessor`, `EQProcessor`
  - Pattern: Stateful, maintains audio processing state

- **Service**: Provides business logic operations
  - Example: `ArtworkService`, `ArtworkDownloader`, `MasteringTargetService`
  - Pattern: Stateless or thread-safe caching, focused on single domain

- **Manager**: Coordinates lifecycle and resources
  - Example: `ConnectionManager` (`auralis-web/backend/config/globals.py`)
  - Pattern: Lifecycle management, resource pooling

- **Repository**: Data access abstraction (CRUD operations)
  - Example: `TrackRepository`, `AlbumRepository`, `FingerprintRepository` — all 12 extend `BaseRepository`
  - Pattern: Database access only, no business logic; session lifecycle inherited from `BaseRepository`

- **Factory**: Creates and configures instances
  - Example: `ProcessorFactory`, `RepositoryFactory`
  - Pattern: Centralized instance creation

### File Organization

```
auralis/
├── core/           # Core audio processing engine
├── dsp/            # Digital signal processing primitives
├── analysis/       # Audio analysis and fingerprinting
├── library/        # Database models and repositories
├── services/       # Business logic services
├── player/         # Real-time playback
└── optimization/   # Performance optimizations

auralis-web/backend/
├── core/           # Backend-specific processing services
├── routers/        # FastAPI route handlers
├── services/       # Backend-specific services (Web-focused)
├── cache/          # Caching infrastructure
└── config/         # Application configuration
```

## Service Patterns

### Artwork Services (Example of Complementary Services)

Two artwork services serve different purposes:

**ArtworkService** (`auralis/services/artwork_service.py`):
- Purpose: Fetch artist artwork URLs
- Returns: URLs only (no download)
- Usage: CLI batch processing
- Pattern: Synchronous, URL-based

**ArtworkDownloader** (`auralis-web/backend/services/artwork_downloader.py`):
- Purpose: Download album artwork files
- Returns: File paths to cached images
- Usage: Web API on-demand
- Pattern: Asynchronous, file-based with caching

These are NOT duplicates - they serve different entities (artist vs album) and different use cases (CLI vs Web).

### Fingerprint Services (Example of Specialized Services)

**MasteringTargetService** (`auralis-web/backend/core/mastering_target_service.py`):
- Purpose: Load fingerprints and generate mastering targets
- Pattern: 3-tier loading (database → .25d file → extract from audio)
- Usage: Backend audio processing

**FingerprintQueue** (Two implementations):
- `auralis/services/fingerprint_queue.py`: Bulk scanning (worker threads)
- `auralis-web/backend/analysis/fingerprint_queue.py`: On-demand extraction (single async worker, 404 handling)
- Not duplicates - different concurrency models for different use cases

## Best Practices

1. **DRY Principle**: Improve existing code rather than duplicating logic
2. **Repository Pattern**: ALL database access via repositories
3. **Dependency Injection**: Pass dependencies via constructor
4. **Module-level Imports**: Avoid lazy imports (indicates circular dependency)
5. **Single Responsibility**: Each service/processor has one clear purpose
6. **Naming Clarity**: Use consistent naming (Processor/Service/Manager/Repository/Factory)
7. **No "Enhanced" Variants**: Refactor in-place instead of creating V2/Enhanced versions
