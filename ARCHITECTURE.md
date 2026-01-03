# Auralis Architecture

This document provides an overview of Auralis' architecture, focusing on processor hierarchy, service patterns, and naming conventions.

## Processor Hierarchy

Auralis uses a layered processor architecture for audio processing:

### 1. Core Engine Layer (`auralis/core/`)

**HybridProcessor** - Main unified processor
- Supports both reference-based and adaptive mastering
- Delegates to specialized mode processors:
  - `AdaptiveMode`: Spectrum-based adaptive processing
  - `HybridMode`: Combined reference + adaptive
  - `ContinuousMode`: Continuous learning mode
  - `RealtimeDSPPipeline`: Low-latency chunk processing

**Deprecated**: `processor.py` - Old reference-based processor (use HybridProcessor instead)

### 2. Specialized Processing Layer (`auralis/core/processing/`)

- **EQProcessor**: Equalization processing
- **RealtimeProcessor**: Real-time DSP operations
- **AdaptiveMode**: Spectrum-based adaptation
- **HybridMode**: Multi-mode processing

### 3. Backend/Streaming Layer (`auralis-web/backend/`)

**ChunkedAudioProcessor** - WebSocket streaming processor
- Processes audio in 15-second chunks (10s intervals, 5s overlap)
- Fast first-chunk streaming for instant playback
- Background processing of remaining chunks
- Crossfade between chunks for gapless playback

**ProcessorFactory** - Processor lifecycle management
- Creates and caches HybridProcessor instances
- Maintains processor state across chunks
- Prevents audio artifacts at chunk boundaries

**Deprecated**: `ProcessorManager` - Replaced by ProcessorFactory

### 4. Player Layer (`auralis/player/`)

**RealtimeProcessor** - Low-latency player processing
- Real-time chunk processing for playback
- Minimal latency for interactive use

### 5. Optimization Layer (`auralis/optimization/`)

**ParallelProcessor** - Multi-threaded batch processing
- Parallel processing for batch operations
- Optimal CPU utilization

### 6. Library/Batch Layer (`auralis/library/scanner/`)

**BatchProcessor** - Library scanning
- Bulk fingerprint extraction
- Metadata extraction from audio files

## Service Architecture

### Repository Pattern

All database access MUST use the repository pattern via `RepositoryFactory`:

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
        self.lib_manager = LibraryManager()  # Violates repository pattern
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
  - Example: `LibraryManager` (deprecated - use RepositoryFactory)
  - Pattern: Lifecycle management, resource pooling

- **Repository**: Data access abstraction (CRUD operations)
  - Example: `TrackRepository`, `AlbumRepository`, `FingerprintRepository`
  - Pattern: Database access only, no business logic

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
├── services/       # Business logic services (CLI-focused)
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

**FingerprintQueue** (Multiple implementations):
- `auralis/services/fingerprint_queue.py`: Bulk scanning (4-24 worker threads)
- `auralis-web/backend/fingerprint_queue.py`: On-demand extraction (single async worker, 404 handling)
- Not duplicates - different concurrency models for different use cases

## Best Practices

1. **DRY Principle**: Improve existing code rather than duplicating logic
2. **Repository Pattern**: ALL database access via repositories
3. **Dependency Injection**: Pass dependencies via constructor
4. **Module-level Imports**: Avoid lazy imports (indicates circular dependency)
5. **Single Responsibility**: Each service/processor has one clear purpose
6. **Naming Clarity**: Use consistent naming (Processor/Service/Manager/Repository/Factory)
7. **No "Enhanced" Variants**: Refactor in-place instead of creating V2/Enhanced versions

## Architecture Evolution

### Phase 1 (Complete): Duplicate Elimination
- ✅ Removed duplicate WebM encoder (234 lines)
- ✅ Consolidated encoding module structure

### Phase 2 (Complete): Repository Pattern Enforcement
- ✅ Fixed repository pattern violations in MasteringTargetService
- ✅ Eliminated lazy imports
- ✅ Added dependency injection for repository access

### Phase 3 (Current): Documentation & Conventions
- ✅ Documented processor hierarchy
- ✅ Established naming conventions
- ✅ Clarified service patterns

## Future Improvements

- Consolidate WebSocket dependency management
- Standardize async/sync service patterns
- Improve processor factory caching strategies
- Consider service adapter pattern for backend→core access
