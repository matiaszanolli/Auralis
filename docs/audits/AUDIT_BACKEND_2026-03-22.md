# Backend Audit — 2026-03-22

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: FastAPI backend — `auralis-web/backend/`
**Dimensions**: Route Handlers, WebSocket Streaming, Chunked Processing, Processing Engine, Schema Consistency, Middleware & Config, Error Handling, Performance, Test Coverage
**Method**: 9 parallel dimension agents (Sonnet), followed by manual merge and deduplication.

## Executive Summary

This audit reveals **4 HIGH**, **17 MEDIUM**, and **30 LOW** findings across the backend. No CRITICAL findings. The most impactful cluster involves chunked audio processing — silence insertion at track end, crossfade doubling artefacts, and a race condition on concurrent play requests.

**Key themes:**

1. **Chunked processing defects (2 HIGH, 2 MEDIUM)** — Trailing chunk loads beyond file end inserting silence (CP-01), `active_streams` dict race on concurrent play (CP-02), crossfade replace-head model causes pre-echo (CP-03), recovery position calculation off by 50% (CP-05).

2. **Unregistered router (HIGH + HIGH)** — `webm_streaming.py` defines 5 endpoints never registered in `config/routes.py` (MC-01). Its 24 tests all silently pass against 404 responses (TC-1).

3. **Event loop blocking (3 MEDIUM)** — Synchronous SQLAlchemy calls in metadata router (6 sites), settings router (5 sites), and webm streaming router (2 sites) block the async event loop.

4. **Schema inconsistencies (2 MEDIUM, 10 LOW)** — Volume uses 3 incompatible scales, repeat mode has REST/WS value divergence, 12+ endpoints lack response_model.

5. **Processing engine state safety (3 MEDIUM)** — Missing `stop_worker()` leaks background task, `jobs` dict mutated without lock, processor state reset races with concurrent jobs.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 17 |
| LOW | 30 |
| **Total** | **51** |

## Route Coverage Matrix

| Router File | Endpoints | Issues Found | Notes |
|-------------|-----------|--------------|-------|
| `player.py` | 18 | ROUT-4, SC-1, SC-2, TC-2 | shuffle query param, volume/repeat schema |
| `library.py` | 8 | ROUT-6 | Module-level router |
| `albums.py` | 4 | ROUT-7, TC-3 | order_by unvalidated, fingerprint untested |
| `artists.py` | 4 | — | Clean |
| `playlists.py` | 6 | ROUT-6 | Module-level router |
| `enhancement.py` | 5 | ROUT-5, ROUT-6 | No try/except on status, module-level router |
| `metadata.py` | 4 | ROUT-2, PERF-02 | Sync DB calls |
| `settings.py` | 3 | ROUT-3 | Sync DB calls |
| `artwork.py` | 3 | — | Clean |
| `system.py` | 2+WS | TC-4 | WS origin test gap |
| `similarity.py` | 6 | PERF-03 | N+1 queries |
| `streaming.py` | 2 | — | Clean |
| `fingerprint.py` | 4 | — | Clean |
| `processing_api.py` | 3 | BE-DIM7-4, TC-5 | Temp file leak, magic byte untested |
| `cache.py` | 4 | — | Clean |
| `webm_streaming.py` | 5 | MC-01, PERF-01, TC-1 | **Never registered — all 404** |
| `stats.py` | 2 | — | Clean |
| `search.py` | 1 | — | Clean |

---

## Findings

### HIGH (4)

---

### CP-01: Trailing chunk loads beyond file duration, inserting silence at end of every track
- **Severity**: HIGH
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py` (load_chunk_from_file)
- **Status**: NEW
- **Description**: `load_end` is not capped at `total_duration` for the trailing context window. For the last chunk, soundfile returns fewer samples than requested; `trim_context` fires a guard warning; `extract_chunk_segment` zero-pads the gap — inserting silence at the end of every track.
- **Impact**: Audible silence appended to every played track. Breaks gapless playback.
- **Suggested Fix**: Cap `load_end = min(load_end, total_duration)` before the soundfile read.

---

### CP-02: active_streams dict race on concurrent play — first stream uncancellable, second leaks semaphore
- **Severity**: HIGH
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/audio_stream_controller.py` (active_streams)
- **Status**: NEW
- **Description**: `active_streams` is written by concurrent asyncio tasks with no lock. When the same `track_id` is requested twice concurrently, the first task's handle is silently overwritten and can never be cancelled; the second leaks its semaphore slot.
- **Impact**: Semaphore exhaustion after ~5 double-plays; subsequent streams hang.
- **Suggested Fix**: Use an asyncio.Lock around `active_streams` mutations; cancel the existing stream before overwriting.

---

### MC-01: webm_streaming router (5 endpoints) never registered — all return 404
- **Severity**: HIGH
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/routes.py`
- **Status**: NEW
- **Description**: `routers/webm_streaming.py` defines `create_webm_streaming_router()` with 5 endpoints, but it is never imported or registered. All endpoints return 404 in production. Frontend test mocks model these routes.
- **Impact**: Dead router — chunk streaming via HTTP is non-functional.
- **Suggested Fix**: Register in `config/routes.py` or delete if WebSocket streaming is the canonical path.

---

### TC-1: 24 webm_streaming tests silently pass against 404 — zero enforced coverage
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_webm_streaming_api.py`
- **Status**: NEW
- **Description**: Tests use main app `client` fixture but the router isn't registered. Happy-path tests accept `if response.status_code == 200:` — every request returns 404 and the assertion is skipped. The entire streaming chunk delivery pipeline has zero enforced CI coverage.
- **Impact**: False confidence — tests appear green but verify nothing.
- **Suggested Fix**: Change assertions to `assert response.status_code == 200`. Register the router or delete dead tests.

---

### MEDIUM (17)

---

### ROUT-2: metadata.py has 6 synchronous SQLAlchemy calls blocking event loop
- **Severity**: MEDIUM
- **Dimension**: Route Handlers / Performance
- **Location**: `auralis-web/backend/routers/metadata.py`
- **Status**: NEW

### ROUT-3: settings.py has 5 synchronous DB calls blocking event loop
- **Severity**: MEDIUM
- **Dimension**: Route Handlers / Performance
- **Location**: `auralis-web/backend/routers/settings.py`
- **Status**: NEW

### CP-03: Crossfade uses replace-head model causing ~200ms pre-echo at every boundary
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py` (_apply_boundary_crossfade)
- **Status**: NEW
- **Description**: Previous chunk's tail is already sent to client, then a faded copy is mixed into current chunk's head — producing doubling artefact at every 10s boundary.

### CP-04: Single chunk failure exits entire stream — remaining chunks abandoned
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/audio_stream_controller.py` (stream_enhanced_audio)
- **Status**: NEW

### CP-05: Recovery position calculation off by 50% — uses CHUNK_DURATION not CHUNK_INTERVAL
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/audio_stream_controller.py`
- **Status**: NEW

### PE-1: ProcessingEngine.stop_worker() does not exist — background task never cancelled
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/processing_engine.py`
- **Status**: NEW

### PE-2: create_job() and submit_job() error path mutate jobs dict without lock
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/processing_engine.py`
- **Status**: NEW

### PE-3: Processor state reset races with concurrent job using same HybridProcessor
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/processing_engine.py`
- **Status**: NEW

### SC-1: Volume uses 3 incompatible scales (int 0-100, float 0-100, float 0-1)
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `schemas.py` (PlayerState, SetVolumeRequest, VolumeResponse)
- **Status**: NEW

### SC-2: RepeatMode REST returns "off" but state stores "none" — WS broadcasts diverge
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `routers/player.py`, `schemas.py`
- **Status**: NEW

### MC-02: LibraryManager and audio_player not shut down in lifespan — WAL checkpoint skipped
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/startup.py`
- **Status**: NEW

### WS-2: HeartbeatManager fully implemented but never instantiated — stale clients hold semaphore
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/websocket/websocket_protocol.py`
- **Status**: NEW

### WS-3: WebSocketProtocol, HeartbeatManager, RateLimiter (386 lines) entirely dead code
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/websocket/websocket_protocol.py`
- **Status**: NEW

### WS-4: Stream pause/flow events not cleared between tracks — next stream stalls
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/audio_stream_controller.py`
- **Status**: NEW

### BE-DIM7-2: SQLite OperationalError always surfaces as HTTP 500 instead of 503
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/errors.py`
- **Status**: NEW

### BE-DIM7-3: stream_normal_audio uses sf.SoundFile — MP3/M4A/OGG fail silently
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/audio_stream_controller.py:777,823`
- **Status**: NEW

### PERF-03: N+1 sequential DB queries in GET /similar with include_details=true
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/similarity.py`
- **Status**: NEW

---

### LOW (30)

**Route Handlers (4)**: ROUT-4 (shuffle query param anti-pattern), ROUT-5 (enhancement status no try/except), ROUT-6 (module-level router accumulation risk in 4 files), ROUT-7 (albums order_by unvalidated)

**WebSocket (6)**: WS-1 (active_streams keyed by track_id not connection), WS-5 (id(websocket) reuse-unsafe), WS-6 (_send_error skips connected guard), WS-7 (reconnect doesn't resume), WS-8 (seek routes to enhanced only), WS-9 (text+binary frame interleave risk), WS-10 (active_connections no lock)

**Chunked Processing (3)**: CP-06 (SimpleChunkCache bytes diverge), CP-07 (trim_context under-trims), CP-08 (channel count ambiguous for pathological shapes)

**Processing Engine (4)**: PE-4 (cleanup_old_jobs type mismatch), PE-5 (print not logger), PE-6 (ChunkedAudioProcessor bypasses singleton), PE-7 (ProcessingLockManager dead code)

**Schema (10)**: SC-3 (file_path in PlayerState), SC-4 (QueueInfoResponse dual count fields), SC-5 (12+ endpoints no response_model), SC-6 (scan_complete field name mismatch REST/WS), SC-7 (ArtistDetail vs ArtistResponse naming), SC-8 (ProcessRequest raw filesystem path), SC-9 (lone camelCase alias), SC-10 (enhancement settings untyped dict), SC-11 (fingerprint stats dual naming), SC-12 (track/disc vs track_number/disc_number)

**Middleware (2)**: MC-05 (NoCacheMiddleware matches .tsx), MC-06 (DEV_MODE=false enables dev mode)

**Error Handling (2)**: BE-DIM7-1 (print not logger in worker), BE-DIM7-4 (temp file orphaned on 503)

**Performance (3)**: PERF-01 (webm_streaming sync DB calls), PERF-04 (enqueue-all thread overhead), PERF-05 (RateLimitMiddleware dict grows), PERF-06 (sync unlink inside lock)

**Test Coverage (2)**: TC-2 (POST /queue/repeat untested), TC-3 (album fingerprint endpoint untested), TC-4 (WS origin rejection untested), TC-5 (magic byte gate untested)

---

## Relationships & Shared Root Causes

1. **webm_streaming dead router** (3 findings): MC-01 (not registered) → TC-1 (tests silently pass) → PERF-01 (sync DB calls). Decision needed: register or delete.

2. **Event loop blocking** (3 findings): ROUT-2 (metadata), ROUT-3 (settings), PERF-01 (webm). All sync SQLAlchemy calls without `asyncio.to_thread`. Same fix pattern.

3. **Chunked processing artefacts** (4 findings): CP-01 (silence), CP-03 (pre-echo), CP-05 (wrong recovery position), CP-07 (under-trim). All in `chunk_operations.py` — the crossfade/context model has multiple correctness gaps.

4. **Processing engine concurrency** (3 findings): PE-1 (no stop), PE-2 (lock missing), PE-3 (state reset race). Same file, same root cause: incomplete locking discipline.

5. **Schema naming inconsistency** (5 findings): SC-6, SC-7, SC-11, SC-12, SC-4. Multiple endpoints return the same concept with different field names. A shared `TrackSummary` schema would fix most.

## Prioritized Fix Order

1. **CP-01 + CP-03** — Silence insertion and crossfade doubling. Audible on every track. Core audio quality.
2. **CP-02** — Active streams race. Semaphore exhaustion after ~5 double-plays.
3. **MC-01 + TC-1** — Decide: register webm_streaming or delete it. Fix tests either way.
4. **MC-02** — Add LibraryManager shutdown. WAL checkpoint prevents corruption.
5. **PE-2 + PE-3** — Processing engine lock discipline. Prevents dict mutation crash.
6. **ROUT-2 + ROUT-3** — Wrap sync DB calls in asyncio.to_thread. Event loop health.
7. **SC-1 + SC-2** — Volume scale and repeat mode consistency. Frontend receives wrong values.
8. **WS-2 + WS-4** — Enable heartbeat; clear flow events between tracks. Stream reliability.
9. **BE-DIM7-3** — Normal streaming MP3/M4A support via load_audio.
10. **PERF-03** — Batch similar tracks DB lookup. Eliminates 100 sequential queries.

---

*Report generated by Claude Opus 4.6 — 2026-03-22*
*Suggest next: `/audit-publish docs/audits/AUDIT_BACKEND_2026-03-22.md`*
