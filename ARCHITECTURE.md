# Auralis Architecture: Service and Naming Conventions

The cross-cutting conventions every new service, processor, worker and repository follows. For
the layer model, design rules and invariants see
[docs/architecture/overview.md](docs/architecture/overview.md); for the request flows see
[docs/architecture/data-flow.md](docs/architecture/data-flow.md); for the file layout see
[docs/architecture/module-map.md](docs/architecture/module-map.md).

## Repository pattern

All database access goes through repositories. Every repository extends `BaseRepository`
(`auralis/library/repositories/base.py`), directly or through its mixins. `BaseRepository` owns the
session factory and the `get_session()` / `_session_scope()` lifecycle (close, and roll back when an
exception escapes), so a pooling or retry change is a one-file edit. `RepositoryFactory`
(`auralis/library/repositories/factory.py`) exposes the repositories as properties: `tracks`,
`albums`, `artists`, `genres`, `playlists`, `fingerprints`, `fingerprint_scheduler`,
`fingerprint_stats`, `stats`, `settings`, `processing_jobs`, `similarity_graph`.

```python
# Correct: via the factory. LibraryDatabase builds one and exposes it as `.repositories`.
track = library_database.repositories.tracks.get_by_id(track_id)

# Incorrect: a session and a query written outside a repository.
session.query(Track).filter_by(id=track_id).first()
```

Repositories return detached objects, so a query must eager-load every relationship a caller
touches. The rules are in [CLAUDE.md](CLAUDE.md).

In a router the factory arrives per request, never as a global:

```python
_repo_deps = RepositoryFactoryDeps("tracks")                 # routers/repo_deps.py

async def get_track(track_id: int, repos: Any = Depends(_repo_deps.get_repos)):
    return await asyncio.to_thread(repos.tracks.get_by_id, track_id)
```

## Dependency injection

Components receive collaborators through their constructor, usually as zero-argument getters, and
never construct their own. A getter is late-bound, so a component can be handed something that does
not exist yet when it is built.

```python
# Correct: the repository getter is injected.
service = MasteringTargetService(get_fingerprints_repository=lambda: factory.fingerprints)
scanner = LibraryAutoScanner(settings_repo, library_database, fingerprint_queue, connection_manager)

# Incorrect: the service builds its own database.
class MyService:
    def __init__(self):
        self._repos = LibraryDatabase().repositories
```

Where the wiring happens:

- **Backend startup** (`auralis-web/backend/config/startup/`) builds the components and stores
  them in a registry (`config/globals.py`).
- **Routers** are built by factories, `create_*_router(get_component_a, ...)`, called from
  `config/routes.py::setup_routers`, whose `get_component(key)` returns a lambda over the registry.
  A router keeps its injected getters in a per-router `RouterDeps` holder
  (`routers/dependencies.py`) and resolves them with `Depends(...)`.
- **WebSocket handlers** receive a `WSDeps` dataclass (`ws_handlers/context.py`).
- **Process-wide singletons** have an accessor rather than a constructor call:
  `get_processor_factory` (`core/processor_registry.py`), `get_mastering_target_service`
  (`core/mastering_target_service.py`), `get_fingerprint_queue` (`analysis/fingerprint_queue.py`),
  `get_artwork_downloader` (`services/artwork_downloader.py`). Use the accessor; do not construct a
  second instance.

## Imports

Imports go at module level. A function-level import is for breaking a real import cycle or for an
optional or heavy dependency, and carries a comment saying which. A function-level import with no
such reason hides a dependency from readers and tooling.

## Split modules

Large classes are split into a coordinator plus sibling modules to keep modules under 300 lines
(files already split have a ceiling in `loc-ceilings.json` that only goes down). Two shapes are in use; follow whichever the surrounding code uses.

- **Delegating coordinator.** The class keeps thin methods; the logic lives in sibling modules whose
  functions take the instance as their first argument. `ChunkedAudioProcessor`
  (`auralis-web/backend/core/chunked_processor.py`) delegates to `chunk_render.py`,
  `chunk_streaming.py`, `chunk_processor_init.py` and others; `HybridProcessor` delegates to
  `hybrid_setup.py` and `processing/mode_dispatch.py`. The methods stay on the class so
  `patch.object(instance, ...)` keeps working.
- **Mixins.** `ProcessorFactory` composes `ProcessorLeaseMixin` and `ProcessorMaintenanceMixin`;
  `StreamlinedCacheManager` composes several `*_mixin.py` classes; the player composes
  `player_*_mixin.py`. A mixin that calls a method its host provides declares it as a bare
  class-level annotation with a `# Provided by X.` comment, never as a `raise NotImplementedError`
  stub, because a runtime stub sits ahead of sibling mixins in the MRO.

## Naming conventions

- **Processor** transforms audio (input to output) and is stateful across calls.
  `HybridProcessor` (`auralis/core/hybrid_processor.py`), `ChunkedAudioProcessor`
  (`auralis-web/backend/core/chunked_processor.py`), `EQProcessor`
  (`auralis/core/processing/eq_processor.py`).
- **Service** is business logic over one domain, stateless or with thread-safe caching.
  `MasteringTargetService` (`auralis-web/backend/core/mastering_target_service.py`),
  `PlaybackService` and `QueueService` (`auralis-web/backend/services/`), `FingerprintService`
  (`auralis/analysis/fingerprint/fingerprint_service.py`), `ArtworkService`
  (`auralis/services/artwork_service.py`).
- **Manager** coordinates a lifecycle or a pooled resource. `ConnectionManager`
  (`auralis-web/backend/websocket/connection_manager.py`), `PlayerStateManager`
  (`auralis-web/backend/core/state_manager.py`), `StreamlinedCacheManager`
  (`auralis-web/backend/cache/manager.py`), `MigrationManager`
  (`auralis/library/migration_manager.py`).
- **Repository** is data access only, with no business logic and a session lifecycle inherited from
  `BaseRepository`. `TrackRepository`, `AlbumRepository`, `FingerprintRepository` and the rest of the
  twelve above.
- **Factory** creates and configures instances. `RepositoryFactory`, `ProcessorFactory`
  (`auralis-web/backend/core/processor_factory.py`), and the router factories
  (`create_*_router`).
- **Worker / Queue** is a background loop with `start()` and `stop()`.
  `FingerprintExtractionQueue` (`auralis/services/fingerprint_queue.py`), `FingerprintQueue`
  (`auralis-web/backend/analysis/fingerprint_queue.py`), `LibraryAutoScanner`
  (`auralis-web/backend/services/library_auto_scanner.py`), `StreamlinedCacheWorker`
  (`auralis-web/backend/core/streamlined_worker.py`). Backend workers are registered in
  `BACKGROUND_WORKER_KEYS` (`auralis-web/backend/config/background_workers.py`) so shutdown,
  startup rollback and library reset all stop and restart them the same way.

### File organization

```
auralis/
├── core/           Processing pipeline (HybridProcessor, modes, targets, config)
├── dsp/            DSP primitives (dynamics, EQ, filters, conversion)
├── analysis/       Measurement, quality, 25D fingerprinting
├── library/        SQLite models, repositories, scanner, migrations
├── player/         Queue, playback state machine, gapless engine, realtime processors
├── io/             Loading (FFmpeg, SoundFile), saving, format registry
├── services/       Fingerprint worker pool, artist artwork lookup
└── optimization/   Performance optimizer and profiling

auralis-web/backend/
├── config/         App assembly: startup, middleware, router registration, limits
├── core/           Chunk rendering, streaming, processor lifecycle, mastering targets
├── routers/        FastAPI route families, one create_*_router factory each
├── ws_handlers/    Per-message WebSocket handlers
├── websocket/      Connection manager, outbound message types, rate limiting
├── services/       Backend services (playback, queue, auto-scanner, artwork download)
├── analysis/       On-demand fingerprint generation and queue
├── cache/          Streamlined chunk cache manager
└── schemas/        Pydantic request/response models
```

## Complementary services that look alike

These pairs are not duplicates. Each serves a different entity or concurrency model, and neither
should absorb the other.

**Artwork.** `ArtworkService` (`auralis/services/artwork_service.py`) looks up artist artwork
metadata from MusicBrainz, Discogs and Last.fm for the CLI (`auralis/cli/fetch_artwork.py`).
`ArtworkDownloader` (`auralis-web/backend/services/artwork_downloader.py`) downloads and caches
album artwork asynchronously for the web API, from MusicBrainz and iTunes.

**Fingerprinting.** Two queues feed one analysis path.

- `FingerprintExtractionQueue` (`auralis/services/fingerprint_queue.py`): a pool of worker threads
  that claim unfingerprinted and outdated tracks directly from the database, started at backend
  startup.
- `FingerprintQueue` (`auralis-web/backend/analysis/fingerprint_queue.py`): a single asyncio
  worker with an in-memory FIFO and de-duplication, for tracks enqueued after a scan, when a stream
  starts without a fingerprint, or by request.

`MasteringTargetService` loads a track's fingerprint for mastering in three tiers (database, then
`.25d` sidecar, then extraction from the audio) and derives the track's targets once. See
[docs/architecture/data-flow.md](docs/architecture/data-flow.md) for how they connect.

## Best practices

1. **DRY.** Improve existing code rather than duplicating logic.
2. **Repository pattern.** All database access via repositories.
3. **Constructor injection.** Pass dependencies in; use an accessor for a process-wide singleton.
4. **Module-level imports** unless a cycle or an optional dependency forces otherwise.
5. **Single responsibility.** One clear purpose per service, processor or module.
6. **Consistent names.** Processor, Service, Manager, Repository, Factory, Worker.
7. **No variants.** Refactor in place instead of adding a second "Enhanced" or "V2" class beside
   the original.
