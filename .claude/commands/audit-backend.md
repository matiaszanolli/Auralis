---
description: "Deep audit of the FastAPI backend — routers, WebSocket streaming, chunked processing, schemas, middleware"
argument-hint: "[--focus <dimensions>] [--depth shallow|deep] [--limit <N>]"
---

# Backend Audit

Perform a deep audit of the Auralis FastAPI backend — routes, WebSocket streaming, chunked processing, schemas, middleware.

**Architecture**: This is an orchestrator. Each dimension runs as an Agent-tool subagent (`subagent_type: general-purpose`, `model: sonnet`). Max 3 run concurrently. Use `.claude/agents/backend-specialist.md` (`subagent_type: backend-specialist`) for deep dives into a single dimension.

See `.claude/commands/_audit-common.md` for project layout, severity framework, methodology, context management rules, deduplication, and finding format.

## Parameters (from $ARGUMENTS)

- `--focus <dimensions>`: Comma-separated dimension numbers or names (e.g., `1,3` or `routes,websocket,schemas,caching,seek`). Default: all 11.
- `--depth shallow|deep`: `shallow` = check key patterns only; `deep` = trace full call graphs. Default: `deep`.
- `--limit <N>`: Stop after N findings (useful for time-boxed audits). Default: unlimited.

## Scope

This audit covers ONLY the backend code:

- **App Entry**: `auralis-web/backend/main.py` — thin. It builds the lifespan and mounts StaticFiles; the app factory, middleware and router registration were extracted to `config/`.
- **App Wiring**: `auralis-web/backend/config/app.py` (create_app), `auralis-web/backend/config/middleware.py` (CORS + RateLimit + SecurityHeaders + NoCache), `auralis-web/backend/config/routes.py` (registers all 20 routers), `auralis-web/backend/config/startup.py` (lifespan), `auralis-web/backend/config/background_workers.py`, `auralis-web/backend/config/limits.py`
- **Routers**: `auralis-web/backend/routers/` — 26 `.py` files: 20 registered routers (albums, artists, artwork, cache_streamlined, enhancement, files, fingerprint_queue, fingerprint_status, health, library, library_scan, metadata, player, playlists, processing_api, settings, similarity, similarity_graph, system, tracks) + shared helpers (`dependencies.py`, `errors.py`, `pagination.py`, `serializers.py`, `similarity_common.py`). Derive the live list from `auralis-web/backend/config/routes.py`.
- **WebSocket**: `auralis-web/backend/core/audio_stream_controller.py` plus the handler layer in `auralis-web/backend/ws_handlers/` (`connection.py`, `context.py`, `messages.py`, `playback_commands.py`, `playback_control.py`) and `auralis-web/backend/websocket/` (`websocket_protocol.py`, `websocket_security.py`)
- **Chunked Processor**: `auralis-web/backend/core/chunked_processor.py`; constants come from `auralis-web/backend/core/chunk_boundaries.py` (`CHUNK_DURATION=15.0`, `CHUNK_INTERVAL=10.0`, `OVERLAP_DURATION=5.0`, `CONTEXT_DURATION=5.0`) — never hardcode them. Related: `chunk_cache.py`, `chunk_cache_manager.py`, `chunk_crossfade.py`, `chunk_mastering.py`, `chunk_operations.py`.
- **Streaming paths**: `auralis-web/backend/core/stream_enhanced.py`, `auralis-web/backend/core/stream_normal.py`, `auralis-web/backend/core/stream_seek.py`, `auralis-web/backend/core/stream_prefetch.py`, `auralis-web/backend/core/stream_protocol.py`, `auralis-web/backend/core/stream_messages.py`, `auralis-web/backend/core/proactive_buffer.py`. Shared per-chunk helpers extracted from the controller (#4071) live in `auralis-web/backend/core/stream_chunk_ops.py` (used by the enhanced and seek paths only — the normal path reads chunks off disk with no DSP) and `auralis-web/backend/core/stream_fingerprint.py` (fingerprint readiness before/while adaptive mastering streams). Both take the controller instance as a parameter, so they read its mutable state — treat them as part of the controller's surface, not as free functions.
- **Seek support**: `auralis-web/backend/core/seekable_source.py` — guarantees chunk readers a libsndfile-seekable path, converting once when the source is not seekable (#4737). A regression here silently degrades to whole-file decodes per chunk.
- **Processing Engine & workers**: `auralis-web/backend/core/processing_engine.py`, `auralis-web/backend/core/job_models.py` (`ProcessingJob` / `ProcessingStatus`, extracted in #4250 to break a circular import and re-exported from `processing_engine.py`), `auralis-web/backend/core/processor_pool.py`, `auralis-web/backend/core/processor_factory.py`, `auralis-web/backend/core/job_worker.py`, `auralis-web/backend/core/streamlined_worker.py`, `auralis-web/backend/core/state_manager.py`
- **Shared processing helpers**: `auralis-web/backend/core/audio_processing_pipeline.py` (`AudioProcessingPipeline` — consolidation of the chunked/hybrid/realtime paths; imported by `chunked_processor.py`), `auralis-web/backend/core/mastering_target_service.py` (centralized fingerprint load + target generation, replacing three duplicated code paths in `chunked_processor.py`), `auralis-web/backend/core/level_manager.py` (RMS level continuity across chunk transitions). Because each of these was created to *replace* duplicated logic, check that the old copies really are gone — a surviving copy is a No-variants violation and a divergence risk.
- **Caching**: three independent caches with separate keys and lifetimes — `auralis-web/backend/core/chunk_cache.py` + `chunk_cache_manager.py` (invalidated via `auralis-web/backend/core/file_signature.py`, which keys on mtime+size), `auralis-web/backend/core/thumbnail_cache.py` (content-addressed `{path_hash}_{bucket}_{mtime_ns}_{size}{ext}`, #4447 — fresh keys on edit, so superseded entries need explicit eviction), and `auralis-web/backend/cache/` (`manager.py`, `monitoring.py`) behind `auralis-web/backend/routers/cache_streamlined.py`
- **Env-var tuning**: `auralis-web/backend/core/env_config.py` — integer tuning constants read from the environment at import time (#3917). Values read at import cannot be re-tuned at runtime; flag any that a request path assumes it can change.
- **Schemas**: `auralis-web/backend/schemas.py`
- **Services**: `auralis-web/backend/services/` (10 modules incl. `library_auto_scanner.py`, `queue_service.py`, `queue_enrichment.py`, `queue_protocols.py`, `playback_service.py`)
- **Security**: `auralis-web/backend/security/path_security.py`, `auralis-web/backend/websocket/websocket_security.py`
- **Support modules**: `auralis-web/backend/analysis/`, `auralis-web/backend/monitoring/`, and **one** encoding package — `auralis-web/backend/core/encoding/` (`wav_encoder.py`, class-based `WAVEncoder`, plus `atomic_io.py`), which also defines and exports `WAVEncoderError`. A second functional-style *auralis-web/backend/encoding/* package existed until #5147; its `encode_to_wav()` had zero production callers and it survived only to host the exception class. Do not re-report the old "two `WAVEncoder` implementations" duplication or the `_ERROR_CATEGORIES` misclassification that came with it — `auralis-web/backend/core/processing_engine.py` now imports `WAVEncoderError` from `core.encoding` unconditionally, and `auralis-web/backend/core/chunked_processor.py` has a single import.
- **Tests**: Backend-related tests under `tests/`

Out of scope: React frontend, audio engine internals (`auralis/`), Rust DSP. However, DO verify that the backend correctly calls engine APIs and returns responses matching frontend expectations.

## Severity Examples

| Severity | Backend-Specific Examples |
|----------|--------------------------|
| **CRITICAL** | Dropped audio chunks in WebSocket stream, database corruption from concurrent writes, path traversal via router |
| **HIGH** | Blocking sync call starving event loop, WebSocket disconnect leaking resources, unhandled exception returning 500 |
| **MEDIUM** | Schema mismatch with frontend, missing input validation, inconsistent error response format |
| **LOW** | Unused imports, missing type hints, undocumented endpoints, inconsistent naming |

## Audit Dimensions

### Dimension 1: Route Handler Correctness

**Check**:
- [ ] All handlers are `async def` — are there any sync handlers that block the event loop?
- [ ] Input validation — are path parameters, query parameters, and request bodies validated with Pydantic models?
- [ ] Error responses — do all error paths return proper `HTTPException` with appropriate status codes?
- [ ] Response schemas — do actual return values match declared response models?
- [ ] Idempotency — are PUT/DELETE operations safe to retry?
- [ ] Route conflicts — are there overlapping path patterns that could match incorrectly?
- [ ] Dependency injection — are shared resources (`LibraryDatabase`, the repository factory, `ProcessingEngine`) injected via `auralis-web/backend/routers/dependencies.py` rather than reached for as module globals?
- [ ] Missing endpoints — are there frontend API calls that have no corresponding backend route?

### Dimension 2: WebSocket Streaming

**Check**:
- [ ] Connection lifecycle — is accept/close handled correctly in `auralis-web/backend/ws_handlers/connection.py`? Are resources cleaned up on disconnect?
- [ ] Handler split — do `ws_handlers/messages.py`, `playback_commands.py` and `playback_control.py` agree on the message contract in `auralis-web/backend/websocket/websocket_protocol.py`?
- [ ] Origin/auth checks — is `auralis-web/backend/websocket/websocket_security.py` actually applied on connect, and can it be bypassed?
- [ ] Binary frame format — is the audio frame encoding (`auralis-web/backend/core/encoding/wav_encoder.py`) consistent with what the frontend expects?
- [ ] Backpressure — what happens when the client can't consume frames fast enough? Does the server buffer unboundedly?
- [ ] Multiple clients — can multiple WebSocket connections coexist? Is state per-connection or shared?
- [ ] Error during streaming — does a processing error gracefully close the stream or leave it hanging?
- [ ] Message type consistency — are all message types (text control + binary audio) correctly discriminated?
- [ ] Heartbeat / keepalive — is there a mechanism to detect stale connections?
- [ ] Reconnection state — when a client reconnects, can it resume or must it restart?

### Dimension 3: Chunked Processing

**Check**:
- [ ] Chunk constants — does every module read `CHUNK_DURATION`/`CHUNK_INTERVAL`/`OVERLAP_DURATION` from `auralis-web/backend/core/chunk_boundaries.py`, or are there bypassing literals?
- [ ] Chunk counting — is overlap-aware `content_chunk_count()` used, not a naive `ceil(duration / CHUNK_DURATION)`?
- [ ] Chunk boundaries — do 15s chunks align to audio frame boundaries (not mid-sample)?
- [ ] Cached chunk format — cached chunk files are 16-bit PCM WAV, not float32. Do size/duration estimates account for that?
- [ ] Crossfade correctness — is the 5s overlap crossfade in `auralis-web/backend/core/chunk_crossfade.py` using equal-power curves? Is `len(output) == len(input)` maintained?
- [ ] First/last chunk — are the first and last chunks handled correctly (no crossfade at start/end of track)?
- [ ] Sample rate consistency — is the sample rate preserved across chunk boundaries?
- [ ] Processing failure — if one chunk fails, does it corrupt subsequent chunks or gracefully degrade?
- [ ] Memory management — are completed chunks released promptly, or do they accumulate?
- [ ] Concurrent chunk requests — can a new track request arrive while chunks are still being processed for the previous track?

### Dimension 4: Processing Engine

**Check**:
- [ ] Engine lifecycle — is the processing engine a singleton, per-request, or per-connection? Is this appropriate?
- [ ] Audio engine integration — are calls to `auralis/` engine APIs correct (parameters, return types, error handling)?
- [ ] Async/sync boundary — are sync audio processing calls wrapped in `run_in_executor`? Can they starve the event loop?
- [ ] State management — does the engine maintain mutable state between requests? Is this thread-safe?
- [ ] Configuration propagation — do enhancement settings from the frontend correctly reach the DSP pipeline?
- [ ] Resource cleanup — are audio buffers, temporary files, and engine state cleaned up after processing?

### Dimension 5: Schema Consistency

**Check**:
- [ ] Request/Response models — are all endpoints using Pydantic models for both input and output?
- [ ] Field naming — consistent snake_case throughout? Proper `alias` config for camelCase JSON responses?
- [ ] Optional fields — are fields marked Optional only when truly optional? Default values sensible?
- [ ] Type accuracy — do numeric fields use the correct type (int vs float, seconds vs milliseconds)?
- [ ] Nested schemas — are related objects properly nested, not flattened inconsistently?
- [ ] Enum values — are string enums used for fixed sets of values (player state, enhancement mode)?
- [ ] Schema reuse — are common patterns (track info, pagination) shared, not duplicated?

### Dimension 6: Middleware & Configuration

**Check**:
- [ ] CORS — in `auralis-web/backend/config/middleware.py`: is the allow-origins builder properly restricted? Is `allow_credentials=True` combined with wildcard `["*"]` origins (insecure)?
- [ ] Router inclusion — are all 20 routers in `auralis-web/backend/config/routes.py` registered with correct prefixes and tags? Several factories are imported inside `try/except` so a broken dependency degrades instead of crashing startup — does any failure get silently swallowed without a log?
- [ ] Middleware ordering — `add_middleware` is LIFO; verify the resulting request-inbound order (CORS → SecurityHeaders → NoCache → RateLimit) matches the documented intent in `auralis-web/backend/config/middleware.py`.
- [ ] Rate limiting — is `RateLimitMiddleware` applied to the routes that need it, and is its window bookkeeping safe under asyncio interleaving?
- [ ] Static file serving — `main.py` skips the StaticFiles mount in `--dev` mode to preserve WebSocket routes. Is there proper path restriction in the non-dev path?
- [ ] Startup/shutdown events — does the lifespan in `auralis-web/backend/config/startup.py` (plus `auralis-web/backend/config/background_workers.py`) initialize and tear down background tasks, DB connections, and engine resources symmetrically?
- [ ] `--dev` flag — what security or performance features does it change?
- [ ] Logging configuration — appropriate log levels? Sensitive data (file paths, user data) redacted?

### Dimension 7: Error Handling & Resilience

**Check**:
- [ ] Global exception handler — is there a catch-all that prevents 500 errors from leaking stack traces?
- [ ] FFmpeg failures — does the backend gracefully handle corrupt or unsupported audio files?
- [ ] Database errors — are SQLAlchemy errors caught and translated to meaningful HTTP responses?
- [ ] File not found — does the backend handle missing audio files, artwork, or library paths?
- [ ] Timeout handling — are there timeouts on audio processing? What happens when processing takes too long?
- [ ] WebSocket error propagation — are processing errors sent to the client as error messages before closing?
- [ ] Recovery — can the backend recover from a crash (process restart) without losing critical state?

### Dimension 8: Performance & Resource Management

**Check**:
- [ ] Event loop blocking — are there sync I/O calls (file reads, subprocess, CPU-bound work) on the async event loop?
- [ ] Connection pooling — is SQLAlchemy connection pooling configured (`pool_pre_ping=True`, appropriate pool size)?
- [ ] Memory usage — are large audio buffers (15s chunks at 44.1kHz stereo ≈ 5MB each) managed carefully?
- [ ] Concurrent request handling — can the backend handle multiple simultaneous track requests?
- [ ] Streaming efficiency — is audio data streamed chunk-by-chunk, or loaded entirely into memory?
- [ ] Caching — are expensive operations (fingerprinting, analysis) cached to avoid redundant computation?
- [ ] N+1 queries — do list endpoints use `selectinload()` to avoid N+1 database queries?

### Dimension 9: Test Coverage

**Check**:
- [ ] Router coverage — is each of the 20 registered routers tested with happy path and error cases?
- [ ] WebSocket testing — are WebSocket connections tested (connect, send, receive, disconnect)?
- [ ] Chunked processing tests — are chunk boundaries, crossfades, and edge cases tested?
- [ ] Schema validation tests — are invalid request payloads tested for proper rejection?
- [ ] Integration tests — are end-to-end flows (REST → engine → response) tested?
- [ ] Error scenario tests — are corrupt files, missing resources, and timeouts tested?
- [ ] Concurrency tests — are concurrent request scenarios tested?

### Dimension 10: Caching & Invalidation

Three independent caches now exist, each with its own key derivation, eviction policy, and staleness failure mode. A bug here serves *wrong audio or wrong artwork*, which is user-visible and hard to attribute.

**Key files**: `auralis-web/backend/core/chunk_cache.py`, `auralis-web/backend/core/chunk_cache_manager.py`, `auralis-web/backend/core/file_signature.py`, `auralis-web/backend/core/thumbnail_cache.py`, `auralis-web/backend/cache/manager.py`, `auralis-web/backend/cache/monitoring.py`, `auralis-web/backend/routers/cache_streamlined.py`, `auralis-web/backend/analysis/track_analysis_cache.py`

**Check**:
- [ ] Key completeness — does every cache key include everything that changes the cached bytes? Chunk keys must cover the file signature (mtime+size) **and** the mastering parameters; a key that omits enhancement settings serves enhanced audio for an unenhanced request (and the reverse).
- [ ] Stale-after-edit — if the source file is edited in place, does the next read miss the cache? `file_signature.py` keys on mtime+size; a filesystem with coarse mtime granularity or a same-size edit defeats that. Is there a content fallback?
- [ ] Unbounded growth — `thumbnail_cache.py` mints a fresh key on every source edit, so superseded entries are orphaned by construction. Is there eviction (LRU, size cap, TTL), and does it actually run?
- [ ] Torn writes — are cache files written atomically (temp file + rename via `auralis-web/backend/core/encoding/atomic_io.py`), or can a crash mid-write leave a truncated file that later reads accept as valid?
- [ ] Concurrent writers — two requests computing the same key simultaneously: last-writer-wins, or a corrupt interleave? Is there single-flight/dedup?
- [ ] Cache-format assumptions — cached chunk files are 16-bit PCM WAV, not float32. Does every size/duration estimate and every reader agree on that?
- [ ] Invalidation reach — does the cache-clearing endpoint in `auralis-web/backend/routers/cache_streamlined.py` clear all three caches, or only the one it knows about? Partial invalidation leaves inconsistent state across layers.
- [ ] Monitoring truthfulness — do the hit/miss counters in `auralis-web/backend/cache/monitoring.py` count what they claim? A miss recorded as a hit hides a regression.

### Dimension 11: Seek & Buffering

**Key files**: `auralis-web/backend/core/stream_seek.py`, `auralis-web/backend/core/seekable_source.py`, `auralis-web/backend/core/stream_prefetch.py`, `auralis-web/backend/core/proactive_buffer.py`, `auralis-web/backend/core/stream_chunk_ops.py`, `auralis-web/backend/core/chunk_boundaries.py`

**Check**:
- [ ] Seek target → chunk index — is the mapping computed via `chunk_boundaries.py` (overlap-aware), or with a naive `position / CHUNK_DURATION` that lands mid-overlap and repeats or skips audio?
- [ ] Seekable source — does `seekable_source.py` convert non-seekable inputs exactly once and reuse the converted path? A per-chunk conversion (or a per-chunk whole-file decode, the #4737 regression) turns one seek into O(n) full decodes.
- [ ] Rapid seeks — does a second seek arriving mid-service cancel the first, or do both keep streaming into the same connection and interleave chunks?
- [ ] Prefetch cancellation — when a seek invalidates in-flight prefetch work, is that work cancelled and are its buffers released, or does it complete and land stale chunks in the cache/buffer?
- [ ] Buffer reset — is `proactive_buffer.py` drained on seek? Serving pre-seek buffered audio after a seek is an audible jump backwards.
- [ ] Seek past end / negative — clamped, or does it produce an out-of-range chunk index or an empty stream that hangs the client?
- [ ] Level continuity after seek — the chunk starting at a seek target has no predecessor context. Does `level_manager.py` / mastering state initialize sanely, or does the first post-seek chunk come in at the wrong level?
- [ ] Seek during processing — can a seek arrive while the previous chunk is still being mastered, and does the result get discarded rather than emitted out of order?

## Phase 1: Setup

1. Parse `$ARGUMENTS` for `--focus`, `--depth`, `--limit`
2. `mkdir -p /tmp/audit/backend`
3. Fetch dedup baseline: `gh issue list --limit 200 --json number,title,state,labels > /tmp/audit/backend/issues.json`
4. Scan `docs/audits/` for prior backend audit reports

## Phase 2: Launch Dimension Agents

Launch one Agent-tool subagent per dimension (max 3 concurrent). Each agent writes its output to `/tmp/audit/backend/dim_<N>.md`.

Every agent prompt MUST include:
- The project root is `/mnt/data/src/matchering`
- The depth parameter value
- The limit parameter value (if set)
- Reference to dedup file: `/tmp/audit/backend/issues.json`
- The context management rules from `_audit-common.md`
- The per-finding format below

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Route Handlers | WebSocket Streaming | Chunked Processing | Processing Engine | Schema Consistency | Middleware & Config | Error Handling | Performance | Test Coverage | Caching & Invalidation | Seek & Buffering
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet demonstrating the issue
- **Impact**: What breaks, when, user-visible effect
- **Suggested Fix**: Brief direction (1-3 sentences)
```

Dimension → Output mapping:
- Dimension 1 (Route Handlers) → `/tmp/audit/backend/dim_1.md`
- Dimension 2 (WebSocket Streaming) → `/tmp/audit/backend/dim_2.md`
- Dimension 3 (Chunked Processing) → `/tmp/audit/backend/dim_3.md`
- Dimension 4 (Processing Engine) → `/tmp/audit/backend/dim_4.md`
- Dimension 5 (Schema Consistency) → `/tmp/audit/backend/dim_5.md`
- Dimension 6 (Middleware & Config) → `/tmp/audit/backend/dim_6.md`
- Dimension 7 (Error Handling) → `/tmp/audit/backend/dim_7.md`
- Dimension 8 (Performance) → `/tmp/audit/backend/dim_8.md`
- Dimension 9 (Test Coverage) → `/tmp/audit/backend/dim_9.md`
- Dimension 10 (Caching & Invalidation) → `/tmp/audit/backend/dim_10.md`
- Dimension 11 (Seek & Buffering) → `/tmp/audit/backend/dim_11.md`

## Phase 3: Merge

1. Read all `/tmp/audit/backend/dim_*.md` files
2. Combine into `docs/audits/AUDIT_BACKEND_<TODAY>.md` with structure:
   - **Executive Summary** — Total findings by severity, key themes, most impactful issues
   - **Route Coverage Matrix** — Table of all 20 registered routers with validation status
   - **Findings** — Grouped by severity (CRITICAL first), deduplicated across dimensions
   - **Relationships** — How findings interact, shared root causes
   - **Prioritized Fix Order** — What to fix first and why
3. Remove cross-dimension duplicates (same file:line found by multiple dimensions)

## Phase 4: Cleanup

1. `rm -rf /tmp/audit/backend`
2. Inform user the report is ready
3. Suggest: `/audit-publish docs/audits/AUDIT_BACKEND_<TODAY>.md`

## Labels

Use labels when publishing: severity label + `backend` + `bug`
