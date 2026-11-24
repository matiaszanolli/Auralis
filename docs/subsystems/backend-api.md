# Subsystem: FastAPI Backend

[`auralis-web/backend/`](../../auralis-web/backend/) is the FastAPI application in front of the
audio engine. REST serves library, metadata, settings and batch processing; one WebSocket (`/ws`)
carries real-time state and the binary PCM audio stream. It binds to `127.0.0.1` on port 8765
(`AURALIS_PORT`). Auralis is an Electron desktop app, so there is no LAN or TLS surface by design.

Related docs, each the owner of its own facts:

| Topic | Doc |
|---|---|
| WebSocket messages, validation, rate limits | [WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md) |
| Environment variables and limits | [CONFIG.md](../../auralis-web/backend/CONFIG.md) |
| Chunk geometry, chunk cache, cache keys | [CHUNK_AND_CACHE_ARCHITECTURE.md](../features/cache-system/CHUNK_AND_CACHE_ARCHITECTURE.md) |
| Defenses (origins, path validation, limits) | [SECURITY_MODEL.md](../security/SECURITY_MODEL.md) |
| Router conventions | [API_DESIGN_GUIDELINES.md](../development/API_DESIGN_GUIDELINES.md) |
| DSP behind the backend | [dsp-engine.md](dsp-engine.md) |

## 1. App assembly

[`main.py`](../../auralis-web/backend/main.py) is a thin orchestrator over factories in
`config/`:

```
create_lifespan(deps) -> create_app(lifespan) -> setup_middleware(app) -> setup_routers(app, deps)
  -> register_fallback_routes(app) -> mount_frontend(app, backend_dir)
```

- **`globals_dict`** (`main.py::globals_dict`) is the process-wide component registry. Every
  component is `None` at import and populated during the lifespan. It is also registered through
  `config/globals.py::set_component_registry`, so modules that cannot be handed dependencies
  (the fingerprint accessor in `ChunkedAudioProcessor`) resolve components from it. The library
  lives under the key `library_database`.
- **`deps`** bundles `globals_dict`, the `ConnectionManager`, the shared `enhancement_settings`
  dict and the `HAS_AURALIS` / `HAS_PROCESSING` / `HAS_STREAMLINED_CACHE` / `HAS_SIMILARITY`
  flags. The flags are constants set to `True`: the process has no degraded import mode. They stay
  as the seam tests use to start the lifespan or build routers with one component off.
- **`create_app`** (`config/app.py`): title "Auralis Web API", version from `auralis/version.py`.
  Swagger, ReDoc (`/api/docs`, `/api/redoc`) and the raw OpenAPI schema exist
  only in dev mode (`--dev` or `AURALIS_DEV_MODE`). Exception handlers: `HTTPException` returns
  `{"detail"}`; `RequestValidationError` returns 422 `{"detail": "Validation error", "errors":
  [{field, message}]}`; `WAVEncoderError` returns 500 `Audio encoding failed`; anything else
  returns 500 `Internal server error` with the traceback logged server-side only.
- **Fallbacks** (`config/fallback_routes.py`): an unmatched `/api/*` path answers a JSON 404, or a
  405 with `Allow` when another method matches; an unregistered WebSocket path is closed with 1008.
  Both exist because the SPA's `StaticFiles` mount at `/` would otherwise swallow them.
- **Frontend mount** (`config/fallback_routes.py::mount_frontend`): `StaticFiles` at `/` in
  production; in dev a stub page is served instead, because a mount at `/` would shadow `/ws`.
  Do not add the mount in dev.
- **uvicorn** (`main.py`): `ws_max_size` = `WS_MAX_MESSAGE_SIZE`, `proxy_headers=False`,
  `log_config=None` (so the sanitizing root log handler sees uvicorn's lines),
  `timeout_graceful_shutdown` = one shutdown step budget.

### Lifespan (`config/startup/`)

`config/startup/__init__.py` holds `create_lifespan` and the Auralis-component rollback boundary;
the steps live in `components`, `fingerprint`, `workers`, `tempfiles`, `rollback` and `shutdown`.

Startup order:

1. Install the thread pools (`core/executors.py`, section 7) and start the stdin lifeline
   (`config/parent_lifeline.py`, active only under Electron).
2. Sweep leftovers: the chunk cache and orphaned stream/decode temp WAVs
   (`config/startup/tempfiles.py`), the fingerprint store and the thumbnail store.
3. Auralis components, under one rollback boundary: `LibraryDatabase` (owns migration, engine,
   sessions, scan slots) and its repository factory, fingerprint extraction queue, settings seeding
   into `enhancement_settings`, scan-folder allowlist registration, reference-cloud refresh hook,
   `LibraryAutoScanner`, `AudioPlayer` and `PlayerStateManager`, on-demand fingerprint queue,
   similarity system (fits in the background).
4. `ProcessingEngine(max_concurrent_jobs=2)` (jobs are restored from the library, section 5), then
   `StreamlinedCacheWorker`.

Resilience:

- **Partial-startup rollback** (`rollback.py::_rollback_partial_startup`): a failure in step 3
  stops running services, tears down the player state manager, audio player and database, and nulls
  the components, so routers answer 503 instead of failing with `AttributeError`. Steps that catch
  their own failure (fingerprint queues, auto-scanner, similarity) do not trigger it.
- **Worker-death watchdog** (`workers.py::_watch_critical_worker_task`): a done-callback nulls the
  component's globals if the processing or cache worker dies after startup (cancellation is not a
  failure) and schedules its teardown, so routers return 503 rather than queueing work no one runs.
- **Ordered, bounded shutdown** (`shutdown.py`): stop steps share `SHUTDOWN_TOTAL_TIMEOUT_S`:
  watchdog teardowns, player state manager, background workers (`BACKGROUND_WORKER_KEYS` in
  `config/background_workers.py`), cache worker, processing engine, audio player, processor-factory
  caches, processing pool, artwork session, fingerprint executor, converted-WAV registry. The library
  database (WAL checkpoint) and thread pools are always torn down last, even after a timeout.

## 2. Middleware (`config/middleware/`)

`setup_middleware` registers innermost first; the request-inbound chain is:

```
CORS -> SecurityHeaders -> NoCache -> OriginCheck -> TrustedHost -> RateLimit -> UnhandledException -> app
```

SecurityHeaders wraps everything below it, so 403, 429, 400 and 500 responses still carry the
security headers.

| Middleware | Behavior |
|---|---|
| **CORS** | Origins from `config/middleware/hosts.py::cors_allowed_origins`; credentials allowed; explicit method and header lists (no wildcards), including `X-Confirm-Reset` |
| **SecurityHeaders** | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, and a CSP with loopback-only `connect-src` |
| **NoCache** | `no-store` for `/` and `.html/.js/.css` outside `/assets/`; content-hashed `/assets/` bundles are `immutable`; `/api` and `/ws` untouched |
| **OriginCheck** | `POST/PUT/DELETE/PATCH` under `/api` need a trusted `Origin` (or none, from a loopback peer); cross-site `GET` under `/api` is refused when the browser marks it `Sec-Fetch-Site: cross-site/same-site` without a trusted Origin or Referer. 403 `Untrusted origin` |
| **TrustedHost** | `Host` must be `localhost` or `127.0.0.1` (DNS-rebinding defense); test hosts only under pytest |
| **RateLimit** | Sliding window per `{client_ip}:{method}:{path prefix}` under an `asyncio.Lock`; 429 with `Retry-After`, `rule` and `retry_after_seconds`. Prefixes and limits are in [CONFIG.md](../../auralis-web/backend/CONFIG.md) |
| **UnhandledException** | Turns an exception escaping a route into the generic 500 |

One origin policy, `config/origins.py`, feeds CORS, the WebSocket handshake allowlist and the CSP.
Add a host or port there, once. Vite dev ports 3000-3006 are included only in dev mode.

## 3. Routers

`config/routes.py::setup_routers` imports each router factory, calls `create_*_router(...)` with
`get_component(key)` lambdas that read `globals_dict` fresh per request (components are `None` when
routes are built), and `include_router`s it. Inside a router, a `RouterDeps` holder
(`routers/dependencies.py`) keeps that factory call's collaborators, bound per request by a
router-level dependency, so a second factory call (every test) cannot repoint a live router.

Guard: the processing, cache and similarity factories are imported locally inside `try/except`
blocks, not at module top. A module-level import would raise before the guard and crash startup.
Do not hoist them. The similarity family is three separate `try` blocks so one broken import does
not drop the others.

Twenty routers, 95 HTTP routes and one WebSocket route. Inline-path routers spell the full path
in each route; the four marked *prefix* use `APIRouter(prefix=...)`.

| Router (`routers/`) | Routes |
|---|---|
| `player.py` (+ `player_playback.py`, `player_queue.py`) | `/api/player/`: `status`, `load`, `seek`, `volume`, `next`, `previous`, `queue` (GET, POST), `queue/{index}` (DELETE), `queue/reorder`, `queue/clear`, `queue/add-track`, `queue/add-tracks`, `queue/move`, `queue/shuffle`, `queue/repeat` |
| `enhancement.py` | `/api/player/enhancement/{toggle,preset,intensity,status}`, `GET /api/player/mastering/recommendation/{track_id}` |
| `library.py` | `/api/library/{stats,reset,refresh-references}` |
| `tracks.py` | `/api/library/tracks`, `.../favorites`, `.../{track_id}`, `.../{track_id}/favorite` (POST, DELETE), `.../{track_id}/lyrics` |
| `albums.py` | `/api/albums`, `/api/albums/fingerprints`, `/api/albums/{id}`, `.../tracks`, `.../fingerprint` |
| `artists.py` | `/api/artists`, `/api/artists/{id}`, `.../tracks` |
| `playlists.py` | `/api/playlists`, `/api/playlists/{id}`, `.../tracks`, `.../tracks/add`, `.../tracks/reorder`, `.../tracks/{track_id}` |
| `library_scan.py` | `POST /api/library/scan`, `GET /api/library/scan/status` |
| `fingerprint_status.py` | `GET /api/library/fingerprints/status`, `GET /api/tracks/{id}/fingerprint` |
| `metadata.py` | `/api/metadata/tracks/{id}` (GET, PUT), `.../fields`, `POST /api/metadata/batch` |
| `artwork.py` | `/api/albums/{id}/artwork` (GET, DELETE), `.../extract`, `.../download` |
| `files.py` | `POST /api/files/upload`, `GET /api/audio/formats` |
| `settings.py` | `GET/PUT /api/settings`, `POST /api/settings/scan-folders`, `.../scan-folders/delete`, `.../reset` |
| `processing_api.py` *prefix* `/api/processing` | `process`, `upload-and-process`, `job/{id}`, `job/{id}/download`, `job/{id}/cancel`, `jobs`, `jobs/cleanup`, `queue/status`, `presets`, `parameters` |
| `cache_streamlined.py` *prefix* `/api/cache` | `stats`, `track/{id}/status`, `track/{id}` (DELETE), `clear`, `health` |
| `similarity.py` *prefix* `/api/similarity` | `tracks/{id}/similar`, `tracks/{a}/compare/{b}`, `tracks/{a}/explain/{b}`, `fit` |
| `similarity_graph.py` *prefix* `/api/similarity` | `graph/build`, `graph/stats`, `graph` (DELETE) |
| `fingerprint_queue.py` *prefix* `/api/similarity` | `fingerprint-queue/status`, `.../enqueue/{track_id}`, `.../enqueue-all` |
| `health.py` | `GET /api/health`, `/api/ready`, `/api/version` |
| `system.py` | WebSocket `/ws` only |

Modules without a route table of their own are helpers of the routers above: `*_deps.py`
(dependency holders), `*_models.py` (request/response models), `dependencies.py`, `errors.py`,
`pagination.py`, `serializers.py`, `repo_deps.py`. `player_*.py`, `processing_*.py`,
`playlists_*.py`, `metadata_*.py`, `artwork_*.py`, `albums_fingerprint.py` and the other split
siblings are registered by their parent router's factory, never on their own.

**Health.** `/api/health` is liveness and reports `auralis_available` (engine imported and library
database up) and `fingerprint_engine_available` (the Rust extractor imports). `/api/ready` returns
200 only when the library database, player state manager and fingerprint engine are all up, else
503 with the same body; it echoes `AURALIS_LAUNCH_ID` as `X-Auralis-Launch-Id` so a supervisor can
tell its own child from a stray server that won the port race. `/api/version` returns
`auralis/version.py` plus the database schema version.

## 4. WebSocket and streaming

`routers/system.py::websocket_endpoint` wires one connection: admit, heartbeat, validate, rate-limit,
dispatch. Handlers are in `ws_handlers/`; the wire protocol is entirely in
[WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md). `websocket/connection_manager.py::
ConnectionManager` admits connections (origin allowlist, 16-connection cap) and broadcasts to all
of them concurrently with a per-client timeout, evicting a client that cannot keep up.

State machine for one stream:

```
play_enhanced | play_normal | seek
  -> cancel the connection's previous stream task (await it outside the registry lock)
  -> attach a new task: stream_enhanced / stream_normal / stream_seek
```

Per-stream rules:

- **`core/audio_stream_controller.py::AudioStreamController`** holds the shared module state
  (context variables, timeouts, the global semaphore). Its methods delegate to `stream_*` modules:
  `stream_enhanced.py`, `stream_seek.py`, `stream_normal.py`, the shared pump (`stream_pump.py`
  with `stream_enhanced_chunks.py` / `stream_normal_chunks.py`), `stream_protocol.py` (framing and
  send), `stream_lifecycle.py` and `stream_notifications.py` (control messages), `stream_permit.py`
  (slot acquisition), `stream_gates.py` (pause and flow-control events), `stream_fingerprint.py`.
- **Context variables** `_stream_type_var`, `_frame_seq_var`, `_track_id_var`, `_stream_epoch_var`
  isolate per-stream state per asyncio task. `_frame_seq_var` holds a one-element list cell because
  the frame producer runs in a copied context.
- **Concurrency cap**: a module-level `asyncio.Semaphore(MAX_CONCURRENT_STREAMS)` (default 10),
  acquired with a 5 s timeout; on timeout the client gets `audio_stream_error` "Server busy".
  Per-chunk DSP is bounded by `CHUNK_PROCESS_TIMEOUT` (30 s); processor construction by
  `PROCESSOR_INIT_TIMEOUT` (90 s, it can include whole-track analysis).
- **Cancellation**: handlers snapshot per-message values at task creation. A cancel also sets a
  `threading.Event` per stream (`StreamState.chunk_cancel_events`), so an in-flight DSP call stops
  at its next check; the task is awaited so it releases its semaphore slot and processor lease.
- **Back-pressure**: encoded PCM frames pass through a bounded queue
  (`AURALIS_SEND_QUEUE_MAXSIZE`, default 4); the client's `buffer_full` / `buffer_ready` gate
  delivery between chunks, bounded to 30 s.

## 5. Chunk orchestration and the cache

Geometry, cache keys, invalidation and the on-disk reaper are owned by
[CHUNK_AND_CACHE_ARCHITECTURE.md](../features/cache-system/CHUNK_AND_CACHE_ARCHITECTURE.md);
chunk constants come only from `core/chunk_boundaries.py`. Orchestration:

| Path | Class | Use |
|---|---|---|
| WebSocket streaming | `ChunkedAudioProcessor` (`core/chunked_processor.py`) | One instance per stream. A coordinator over `chunk_*` modules. Chunk DSP runs via `asyncio.to_thread` on the streaming pool, serialized per instance by `_processor_lock` |
| Batch job | `ProcessingEngine` (`core/processing_engine.py`) | Whole-file jobs from `/api/processing`. `ProcessingStatus`: queued, processing, completed, failed, cancelled, interrupted. Every transition is written to the library's `processing_jobs` table by `core/job_store.py`; on start the engine reloads it and marks jobs left queued/processing as interrupted. DSP runs under `asyncio.wait_for(..., timeout)` on the job pool so a hung call cannot hold a slot |

Chunk delivery is WebSocket-only; there is no REST chunk endpoint.

**Processor leases.** Each stream takes an exclusive `HybridProcessor` lease from the
`ProcessorFactory` (`core/processor_factory.py`, `processor_lease.py`,
`chunk_processor_lease.py`) at construction and returns it on `close()`, so two live streams of one
track never feed one instance's EQ and limiter state. Factories come from
`core/processor_registry.py` (one per consumer; `AURALIS_PROCESSOR_CACHE_MAX` bounds each).
`core/processor_init_handoff.py` returns the lease of a stream whose init timed out or was
cancelled. `StreamlinedCacheWorker` keeps its own small processor cache
(`core/streamlined_processor_cache.py`, leases and closes in `streamlined_processor_disposal.py`,
closes run off the loop via `processor_close.py`).

**Single flight.** `core/chunk_single_flight.py` ensures one DSP render per chunk cache key across
streams; followers wait for the leader's WAV and re-lookup, never inheriting its failure.

**Cache pieces.**

- `StreamlinedCacheManager` (`cache/manager.py`): in-memory index of chunk WAVs in two tiers,
  Tier 1 (current and next chunk) and Tier 2 (full-track warm cache, 240 MB budget). Exposed through
  `routers/cache_streamlined.py`.
- `StreamlinedCacheWorker` (`core/streamlined_worker.py`, `streamlined_tiers.py`,
  `streamlined_lifecycle.py`): background task that ticks once a second, snapshots the playback
  position, and fills Tier 1 for the next chunk, then Tier 2 for the track, then the previous track.
- `ChunkCacheManager` (`core/chunk_cache_manager.py`) with the reaper in `core/chunk_disk_prune.py`:
  durable WAVs in the shared temp chunk directory, capped at 512 MB.
- `core/cache_cleanup.py`: the one lifecycle boundary for clearing every tier
  (`clear_track_caches`, `clear_all_caches`); also drops warm processors and mastering-target
  entries.

The chunk directory is wiped at startup unless another live process owns it
(`config/startup/tempfiles.py::claim_chunk_cache`).

## 6. Schemas and response models

Pydantic v2. Each router owns its models in a sibling `*_models.py`; shared models live in
`schemas/` (`library.py`, `system.py`, `mastering.py`, `enhancement.py`, `websocket.py`,
`request_bounds.py`), re-exported from `schemas/__init__.py`. Every route declares
`response_model=` except the two file responses (`GET /api/albums/{id}/artwork`,
`GET /api/processing/job/{id}/download`). `routers/pagination.py` owns the shared `limit` (1-200,
default 50) and `offset` query parameters and the `{<key>: [...], total, offset, limit, has_more}`
page envelope. Request bounds (`TrackId`, `QueueIndex`, `INTENSITY_MIN/MAX`) are shared types in
`schemas/`. Conventions are in [API_DESIGN_GUIDELINES.md](../development/API_DESIGN_GUIDELINES.md).

`schemas/websocket.py::WebSocketMessageType` lists only the types the server accepts inbound, plus a
few server-to-client names; outbound payload contracts are the `TypedDict`s in `websocket/outbound/`.

## 7. Concurrency model

| State kind | Primitive | Examples |
|---|---|---|
| Event-loop state | `asyncio.Lock` | `ConnectionManager._lock`, `StreamState.active_tasks_lock`, `RateLimitMiddleware._lock`, `PlayerStateManager._lock`, `PlaybackEventSequencer.transition_lock` |
| Thread and CPU state | `threading.Lock` / `RLock` | `ChunkedAudioProcessor._processor_lock`, the processor registry lock, the single-flight registry, `WebSocketRateLimiter._lock` |
| Per-task isolation | `contextvars.ContextVar` | stream type, frame `seq`, track id, stream epoch |
| Bounded concurrency | `Semaphore` | global stream semaphore (10), `ProcessingEngine` (2 jobs) |

**Thread pools** (`core/executors.py`, installed in the lifespan): a streaming pool for per-chunk
DSP and chunk reads (`max(4, 2 x MAX_CONCURRENT_STREAMS)` workers); an I/O pool installed as the
loop's default executor (8 workers, never above the 10-connection database pool); a job pool for
batch DSP (2); a transport pool for engine play/pause/seek calls (2). Per-chunk work never queues
behind repository or scan work.

**DSP and I/O offload discipline.** Every synchronous engine, DSP or repository call from a
handler is wrapped in `asyncio.to_thread` (or a `run_in_*_executor` wrapper); long DSP is also under
`asyncio.wait_for(..., timeout)`.

**Transport ordering.** `services/playback_event_sequencer.py` issues the `seq` numbers on playback
events and the `transition_lock` that serializes play/pause/stop across REST and WebSocket.

## 8. Services

`services/` holds logic shared by routers and background tasks:

| Area | Modules |
|---|---|
| Playback and navigation | `playback_service.py` (+ `playback_service_base.py`, `playback_protocols.py`), `navigation_service.py`, `playback_event_sequencer.py` |
| Queue | `queue_service.py` composed from `queue_edit_mixin.py`, `queue_order_mixin.py`, `queue_set_mixin.py`, `queue_enrichment.py`, `queue_set_sequencer.py` |
| Library scanning | `library_auto_scanner.py` (watchdog plus polling, `scanner_watchdog.py`, `scanner_event_filter.py`, `scanner_stop.py`), `scan_events.py`, `scan_complete_broadcast.py`, `scan_fingerprint_enqueue.py`, `missing_tracks.py` |
| Analysis | `recommendation_analysis.py`, `similarity_autofit_worker.py`, `lyrics_extraction.py` |
| Artwork | `artwork_downloader.py`, `artwork_providers/` |
| Errors | `errors.py`: `ServiceError` subclasses `ServiceUnavailable`, `InvalidRequest`, `ResourceNotFound`, `OperationFailed`, mapped to HTTP by type in `routers/errors.py::raise_for_service_error` |

## 9. Error handling

- Handlers raise `HTTPException` subclasses from `routers/errors.py` (`NotFoundError` 404,
  `BadRequestError` 400, `ServiceUnavailableError` 503, `InternalServerError` 500,
  `UnprocessableAudioFileError` 422). 503 is the answer when a component is `None` (after rollback,
  worker death, or before startup finishes); `dependencies.py::require_service` is the one spelling.
- `@with_error_handling("operation")` passes `HTTPException` through and maps other exceptions via
  `errors.py::handle_query_error`: transient SQLite errors to 503, a vanished or unreadable file to
  404 or 403, an integer beyond SQLite's range to 404, everything else to a generic 500.
- Error text sent to clients never contains server paths or raw exception messages;
  `core/job_error_mapping.py::_safe_error_message` maps exception types to fixed categories and
  callers log the raw exception server-side.
- WebSocket errors are `audio_stream_error` frames with a machine-readable `code`, or `error`
  envelopes for rejected commands; see WEBSOCKET_API.md.

## 10. Gotchas

- Do not hoist the guarded router imports (section 3).
- Inject components through `get_component` lambdas; never bind the object itself.
- Do not mount `StaticFiles` in dev mode (section 1).
- Bind address and TLS: `127.0.0.1` only, no remote CORS or TLS to flag.
- The app version string comes from `auralis/version.py`.
- `player_state` and `enhancement_settings_changed` are pushed on every WebSocket connect; handle them
  idempotently.
- Tests that boot the backend open the real library at `~/.auralis`; isolate with `HOME`.

**Related:** [dsp-engine.md](dsp-engine.md) · [frontend.md](frontend.md) ·
[../architecture/data-flow.md](../architecture/data-flow.md)
