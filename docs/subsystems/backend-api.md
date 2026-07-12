# Subsystem: FastAPI Backend & WebSocket Streaming

[`auralis-web/backend/`](../../auralis-web/backend/) is the FastAPI application that fronts
the audio engine: REST for library/metadata/processing, and a single WebSocket for real-time
audio streaming and state sync. It binds to **`127.0.0.1:8765`** — Auralis is an Electron
desktop app, so there is no remote/LAN/TLS surface by design.

> **Scope.** App assembly, routers, the WebSocket protocol, chunk orchestration, and the
> concurrency model. For the DSP that runs behind it, see [dsp-engine.md](dsp-engine.md).

---

## 1. App assembly (`main.py` is a thin orchestrator)

[`main.py`](../../auralis-web/backend/main.py) (~213 lines) does **not** build the app or
register routers inline — it wires together factories from `config/`:

```
create_lifespan(deps)  →  create_app(lifespan=…)  →  setup_middleware(app)  →  setup_routers(app, deps)
```

Key pieces:

- **`globals_dict`** ([`main.py:97`](../../auralis-web/backend/main.py)) — the central registry
  of shared components, all `None` at import and populated during lifespan. A `deps` dict
  bundles feature flags + `ConnectionManager` + `globals` and threads them into lifespan and
  routers.
- **Feature-probe flags** `HAS_AURALIS / HAS_PROCESSING / HAS_STREAMLINED_CACHE / HAS_SIMILARITY`
  are set via real import probes (#3534) — not hard-coded `True`.
- **App factory** `create_app`
  ([`config/app.py:28`](../../auralis-web/backend/config/app.py)): title "Auralis Web API",
  version **"1.0.0"** — note this is *not* the product version (that's
  [`auralis/version.py`](../../auralis/version.py)). Swagger/ReDoc mount only in dev
  (`/api/docs`, `/api/redoc`). Registers three global exception handlers (`HTTPException` →
  `{detail}`, `RequestValidationError` → 422, catch-all → 500 with server-side logging).
- **Static frontend mount** is skipped in `--dev` because a `StaticFiles` mount at `/` would
  shadow the `/ws` route. Don't "fix" the missing dev mount.

### Lifespan (`config/startup.py`)

Startup builds services in a strict order (all under `if HAS_AURALIS`): temp-chunk cleanup →
`LibraryManager` → `RepositoryFactory` → `FingerprintExtractor` / `FingerprintExtractionQueue`
→ `SettingsRepository` → scan-folder allowlist → `LibraryAutoScanner` → `AudioPlayer` →
`PlayerStateManager` → `FingerprintSimilarity` (auto-fit in a background daemon) →
`ProcessingEngine(max_concurrent_jobs=2)` → `StreamlinedCacheWorker`.

Three resilience patterns to know:

- **Partial-startup rollback** — a startup exception triggers `_rollback_partial_startup`,
  which stops already-running services and nulls all components so routers gate to **503**
  instead of `AttributeError` → 500.
- **Worker-death watchdog** — `_watch_critical_worker_task` attaches a done-callback that nulls
  the relevant globals if a long-running worker dies after startup (cancellation is *not*
  treated as failure).
- **Ordered shutdown** — background workers stopped via the shared `BACKGROUND_WORKER_KEYS`
  list, then processing engine, audio player, `ProcessorFactory` cache clear (frees thread
  pools, #3746), artwork aiohttp session, and finally `LibraryManager.shutdown()` (WAL
  checkpoint) last.

---

## 2. Middleware (`config/middleware.py`)

Starlette runs middleware in **reverse** add order, so the inbound chain is:

```
CORS → SecurityHeaders → NoCache → RateLimit → app
```

This ordering is deliberate: a 429 from the rate limiter still gets security headers (#3843).

| Middleware | Behavior |
|------------|----------|
| **CORS** | Explicit origin allowlist over `{localhost,127.0.0.1} × ports[3000–3006, 8765]`; `allow_credentials=True`, no wildcards |
| **SecurityHeaders** | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, CSP allowing `ws://localhost:*` / `http://localhost:*` in `connect-src` |
| **NoCache** | Disables caching only for frontend static assets (`.html/.js/.css`, `/`); never touches `/api` or `/ws` |
| **RateLimit** | Per-`{client_ip}:{path}` sliding window guarded by an `asyncio.Lock`. Limits: upload 5/60s, processing 10/60s, scan 2/60s, similarity 20/60s. Returns 429 + `Retry-After` |

> **Two separate origin allowlists.** WS upgrades are not covered by CORS, so there is a
> distinct WS origin allowlist in `config/globals.py`. **Add new origins to both.**

---

## 3. Routers

`setup_routers(app, deps)` ([`config/routes.py`](../../auralis-web/backend/config/routes.py))
imports router factories, calls `create_*_router(...)`, and `include_router`s each. Dependency
injection is via **`get_component(key)` lambdas** that read `globals_dict` fresh per request —
essential because components are `None` at setup time and only populated later.

> ⚠️ **Guarded router imports (commit `0472776a` / #3907).** `processing_api`,
> `cache_streamlined`, `similarity`, and `wav_streaming` factories are imported **locally inside
> their own `try/except` blocks**, not at module top. A module-level import would raise *before*
> the guard and hard-crash startup. Do not hoist them.

Most routers declare full inline paths (`@router.get("/api/...")`); only `cache_streamlined`
(`/api/cache`), `processing_api` (`/api/processing`), and `similarity` (`/api/similarity`) use
an `APIRouter(prefix=...)`.

| Group | Routers |
|-------|---------|
| **Player / playback** | `player.py` (`/api/player/*` — the exemplar, 19 routes all typed), `enhancement.py` (`/api/player/enhancement/*`) |
| **Library browse** | `library.py`, `tracks.py`, `albums.py`, `artists.py`, `playlists.py`, `library_scan.py`, `fingerprint_status.py` |
| **Metadata / artwork** | `metadata.py`, `artwork.py` |
| **Streaming / processing** | `wav_streaming.py` (REST chunk delivery), `processing_api.py`, `cache_streamlined.py` |
| **System / infra** | `system.py` (**WebSocket `/ws` only**, no HTTP), `health.py` (`/api/health`, `/api/version`), `similarity.py`, `files.py`, `settings.py` |

Shared router infra (not routers): `dependencies.py`, `errors.py`, `pagination.py`,
`serializers.py`.

---

## 4. WebSocket protocol (`/ws`)

A single connection at `ws://localhost:8765/ws` multiplexes all real-time traffic. The handler
in [`routers/system.py`](../../auralis-web/backend/routers/system.py) is a thin wrapper that
delegates to [`ws_handlers/`](../../auralis-web/backend/ws_handlers/).

**Connection setup** ([`ws_handlers/connection.py:33`](../../auralis-web/backend/ws_handlers/connection.py)):
`manager.connect()` (origin validation) → start a 30 s heartbeat loop → **immediately push
`enhancement_settings_changed` and a `player_state` snapshot**. This is the "reconnect is the
common case" design (#2507, #2606): a reconnecting client resyncs Redux without waiting for the
next broadcast. Handle these idempotently.

**Receive loop:** every message passes through a `WebSocketRateLimiter` (10 msg/s) →
`validate_and_parse_message` (size/structure) → `dispatch_message` (routes by `type`).

**Client → server** (validated subset in `schemas.py::WebSocketMessageType`, inbound-only):
`ping/pong/heartbeat`, `play_enhanced`, `play_normal`, `pause/resume/stop/seek`,
`buffer_full/buffer_ready`, `subscribe_job_progress`, `processing_settings_update`,
`ab_track_loaded`.

**Server → client streaming protocol:**

```
audio_stream_start
  → audio_chunk_meta (JSON text frame)  immediately followed by  binary PCM frame
  → … repeated per chunk …
audio_stream_end            (or audio_stream_error {code} on failure)
```

`audio_chunk_meta` carries a **monotonic per-stream `seq`** counter that persists across chunk
boundaries.

### Concurrency details worth knowing

- **`contextvars` for per-task isolation** — `_stream_type_var` and `_frame_seq_var` are
  `ContextVar`s (per asyncio Task), fixing cross-stream clobbering of shared instance state
  (#2493, #3841). `_frame_seq_var` holds a **mutable one-element list cell** because the frame
  producer runs in a copied context (via `asyncio.gather`).
- **Global stream semaphore** — module-level `asyncio.Semaphore(MAX_CONCURRENT_STREAMS)`
  (default 10, env `AURALIS_MAX_CONCURRENT_STREAMS`), shared across all controller instances
  (#2469). Per-chunk DSP timeout `CHUNK_PROCESS_TIMEOUT = 30.0`.
- **Task snapshotting** — `stream_*` handlers snapshot per-message locals (track_id, preset…)
  as keyword-only default args so a later receive-loop message can't leak into an in-flight
  task's error paths (#3829). Each task self-cleans idempotently under a lock.
- **`AudioStreamController` is a god-file split** (#4071): its methods are thin delegates to
  `stream_*` submodules; the public/test surface is preserved.
- **`ConnectionManager`** ([`config/globals.py:46`](../../auralis-web/backend/config/globals.py))
  snapshots `active_connections` under an `asyncio.Lock`, sends outside the lock, and prunes
  stale connections. Origin enforcement on connect allows loopback + dev ports + `file://`
  (Electron).

The full protocol reference is [`WEBSOCKET_API.md`](../../auralis-web/backend/WEBSOCKET_API.md).

> ⚠️ **`WEBSOCKET_API.md` is stale on chunk size** — it says "30-second chunks", but the actual
> constants are **15 s duration / 10 s interval / 5 s overlap**. Trust the code
> ([`chunk_boundaries.py:19`](../../auralis-web/backend/core/chunk_boundaries.py)).

---

## 5. Chunk orchestration — three paths

Chunk geometry is sourced *only* from
[`core/chunk_boundaries.py`](../../auralis-web/backend/core/chunk_boundaries.py):
`CHUNK_DURATION=15`, `CHUNK_INTERVAL=10`, `OVERLAP_DURATION=5`, `CONTEXT_DURATION=5`. Count
chunks with `content_chunk_count()`, never naive `ceil(duration / CHUNK_DURATION)`. See
[dsp-engine.md §6](dsp-engine.md#6-chunked-streaming-auralis-webbackendcore) for crossfade math
and `ProcessorFactory` lifecycle.

| Path | Class | Use |
|------|-------|-----|
| **WS streaming** | `ChunkedAudioProcessor` ([`core/chunked_processor.py`](../../auralis-web/backend/core/chunked_processor.py)) | Live playback. DSP offloaded via `asyncio.to_thread`, serialized by a `threading.Lock`, keeping the event loop free for heartbeats/pause/seek (#2388) |
| **REST batch job** | `ProcessingEngine` ([`core/processing_engine.py`](../../auralis-web/backend/core/processing_engine.py)) | Full-file jobs. State machine QUEUED→PROCESSING→COMPLETED/FAILED/CANCELLED; `processor.process()` wrapped in `asyncio.wait_for(asyncio.to_thread(...), timeout)` so a hung Rust DSP can't hold a slot (#2747). `max_concurrent_jobs=2` |
| **REST WAV chunk** | [`routers/wav_streaming.py`](../../auralis-web/backend/routers/wav_streaming.py) | `GET /api/stream/{id}/chunk/{idx}`. Response headers (`X-Sample-Rate`, `X-Total-Samples`, `X-Playable-Samples`, `X-Overlap-Samples`, `X-Start-Sample-Offset`) let the client place each chunk by absolute sample offset. Serves from streamlined cache when available |

> **Default overlap is 5 s, everywhere.** Both the WS and REST WAV paths default to
> `duration=15 / interval=10`. No-overlap happens only when a caller explicitly passes equal
> duration/interval, or on short/final chunks.

Cached WAV chunks are **16-bit PCM WAV** (distinct from the float32 WS wire format) and the
chunk dir is **wiped on every startup** to avoid serving stale-preset chunks.

---

## 6. Schemas & the `response_model` gap (`schemas.py`)

Pydantic v2. Generic wrappers: `SuccessResponse[T]`, `ErrorResponse`,
`PaginatedResponse[T]` + `PaginationMeta`, `CacheAwareResponse[T]`. Batch models, entity bases
(`TrackBase/ArtistBase/AlbumBase`), param models (`PaginationParams` limit 1–500), and health/
version models all live here.

> **Known gap (#3838, deferred LARGE).** `response_model=` coverage is uneven. Fully typed:
> `player` (19/19), `settings`, `artists`, `health`, `processing_api` (8/9). **Zero coverage:**
> `albums`, `artwork`, `metadata`, `library`, `playlists`, `tracks`, `files`,
> `fingerprint_status`. Those return raw dicts — their shape is guaranteed only by convention.
> When you touch one of these routers, adding a `response_model` is a welcome incremental fix.

`WebSocketMessageType` documents **inbound** types only, despite the generic name; outbound
types live in the frontend TS union — see [frontend.md](frontend.md).

---

## 7. Concurrency model (cheat sheet)

| State kind | Primitive | Examples |
|------------|-----------|----------|
| Async-loop state | `asyncio.Lock` | `ConnectionManager._lock`, `_active_streams_lock`, `RateLimitMiddleware._lock` |
| Thread-pool / CPU state | `threading.RLock` / `Lock` | `ProcessorFactory._lock`, `ChunkedAudioProcessor._processor_lock` |
| Per-task isolation | `contextvars.ContextVar` | `_stream_type_var`, `_frame_seq_var` |
| Bounded concurrency | `Semaphore` | global stream semaphore (10), `ProcessingEngine` (2 jobs) |

**DSP offload discipline:** every sync engine/DSP/repo call is wrapped in `asyncio.to_thread`;
long DSP additionally in `asyncio.wait_for(..., timeout)` to bound event-loop-free windows and
release concurrency slots.

---

## 8. Error handling conventions

- Handlers **raise `HTTPException`**, never bare exceptions. 404 for missing track/file (with
  generic messages that don't leak server paths, #3541), 500 on timeouts, **503 when a
  component is `None`** (post-rollback / worker-death gating).
- `_safe_error_message()` maps exception *types* to user-safe categories and excludes the raw
  exception (callers log the raw one server-side).
- WS errors are `audio_stream_error` frames with a machine-readable `code`
  (`STREAMING_ERROR`, `PROCESSOR_UNAVAILABLE`, `SEEK_ERROR`, `ENHANCEMENT_DISABLED`, …) rather
  than HTTP status.

---

## 9. End-to-end flows

- **REST browse:** request → middleware chain → `async def` handler →
  `get_repository_factory()()` → `asyncio.to_thread(repos.X.get_by_id, …)` → SQLite → serialize
  → JSON.
- **REST processing job:** `POST /api/processing/process` → `ProcessingEngine.submit_job` →
  worker `process_job` → `to_thread(HybridProcessor.process)` → save → WS `job_progress`
  (client subscribes with `subscribe_job_progress`).
- **WS audio stream:** client `play_enhanced` → `dispatch_message` →
  `handle_play_enhanced` → spawn `stream_audio` task → `AudioStreamController` → per chunk:
  `ChunkedAudioProcessor.process_chunk_safe` (`to_thread` → `ProcessorFactory` →
  `HybridProcessor`) → `audio_chunk_meta` + binary PCM → client.
- **REST → WS broadcasts:** player/playlist/enhancement/artwork/scan mutations fan state
  changes out to all clients via `ConnectionManager.broadcast()`.

---

## 10. Gotchas for new devs

- **Never hoist the guarded router imports** (§3) — keep them inside their `try/except` blocks.
- **Inject components via `get_component` lambdas**, never bind the object (it's `None` at
  setup time).
- **Port 8765 / `127.0.0.1` only** — desktop app, no remote/LAN/TLS. Don't flag missing TLS or
  remote-CORS.
- **`create_app` version "1.0.0" ≠ product version** ([`auralis/version.py`](../../auralis/version.py)).
- **Update both origin allowlists** (CORS in `middleware.py`, WS in `globals.py`) when adding
  an origin.
- **`player_state` / `enhancement_settings_changed` are pushed on every connect** — handle
  idempotently.

**Related:** [dsp-engine.md](dsp-engine.md) · [frontend.md](frontend.md) ·
[../architecture/data-flow.md](../architecture/data-flow.md)
