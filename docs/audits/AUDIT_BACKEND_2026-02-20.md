# Backend Audit — 2026-02-20

**Scope**: FastAPI backend — routers, WebSocket streaming, chunked processing, processing engine, schemas, middleware, error handling, performance, test coverage
**Auditor**: Claude Sonnet 4.6 (automated)
**Methodology**: Full code trace of each dimension; findings disproved before inclusion; deduplication against 200 open issues.

---

## Summary

| ID | Severity | Dimension | Status | Issue |
|----|----------|-----------|--------|-------|
| BE-01 | LOW | Route Handlers | NEW | #2483 |
| BE-02 | MEDIUM | Route Handlers / WebSocket | NEW | #2484 |
| BE-03 | MEDIUM | Schema Consistency | NEW | #2485 |
| — | MEDIUM | Performance | Existing: #2330 | — |
| — | MEDIUM | Performance | Existing: #2295 | — |
| — | MEDIUM | Performance | Existing: #2301 | — |
| — | MEDIUM | Performance | Existing: #2257 | — |
| — | MEDIUM | WebSocket Streaming | Existing: #2315 | — |
| — | MEDIUM | WebSocket Streaming | Existing: #2326 | — |
| — | MEDIUM | Processing Engine | Existing: #2328 | — |
| — | MEDIUM | Processing Engine | Existing: #2296 | — |
| — | MEDIUM | Error Handling | Existing: #2331 | — |
| — | MEDIUM | Error Handling | Existing: #2324 | — |
| — | MEDIUM | Test Coverage | Existing: #2334 | — |
| — | MEDIUM | Test Coverage | Existing: #2333 | — |
| — | LOW | Schema Consistency | Existing: #2282 | — |
| — | LOW | Route Handlers | Existing: #2312 | — |
| — | LOW | Performance | Existing: #2317 | — |
| — | LOW | Performance | Existing: #2314 | — |

---

## Dimension Coverage Notes

### Dimension 1: Route Handler Correctness

All 18 routers are `async def`. Input validation uses Pydantic models across most endpoints. **EXCEPTION**: `set_volume`, `toggle_enhancement`, `set_enhancement_preset`, and `set_enhancement_intensity` all take simple scalar parameters (`float` / `bool` / `str`) directly in the function signature — FastAPI treats these as **query parameters** on POST routes, not request body. This is schema inconsistency → **BE-03**.

Path security is solid: `load_track` and `add_to_queue` validate via database before accessing filesystem. **However**, `add_to_queue` (player.py:383-388) still broadcasts and returns `track_path: track.filepath` in both `queue_updated` WS broadcast and REST response. The `load_track` REST response (player.py:233) also returns `track_path` despite the broadcast being fixed in #2479. → **BE-01**.

No route conflicts found. Dependency injection pattern (factory pattern + lambda closures) is consistent across all routers.

### Dimension 2: WebSocket Streaming

Connection lifecycle: `ConnectionManager.connect()` validates Origin header (fixed #2413). `disconnect()` is always called in `finally` block. Rate limiting via `WebSocketRateLimiter(10 msg/s)` applied globally.

Task management: `_active_streaming_tasks` uses `asyncio.Lock` for all dict access (fixed #2425). Old streaming task correctly cancelled when new `play_enhanced` / `play_normal` / `seek` arrives.

Binary frame format: PCM samples sent as float32, base64-encoded, with correct frame splitting at ~400KB per message.

Backpressure: `asyncio.Queue(maxsize=4)` bounded producer/consumer in `_send_pcm_chunk` prevents unbounded heap growth (fixed #2122).

Known issue: `_chunk_tails` dict accessed concurrently without lock → Existing #2326. `_stream_type` shared across streaming calls → Existing #2315.

### Dimension 3: Chunked Processing

CHUNK_DURATION=15s, CHUNK_INTERVAL=10s, OVERLAP_DURATION=5s. Chunk boundaries calculated via `ChunkBoundaryManager`. Context trimming and level smoothing applied.

Crossfade: 5s server-side overlap via `ChunkOperations.extract_chunk_segment()` PLUS 200ms boundary crossfade in `_apply_boundary_crossfade()`. Equal-power fade curves (sin²/cos²) used correctly.

Thread safety: `_processor_lock` (threading.Lock) serializes concurrent `process_chunk` calls. `_sync_cache_lock` prevents cache double-miss.

Memory: chunks processed and cached to disk; only `max_chunks=50` held in memory via `SimpleChunkCache`.

`process_chunk_safe()` correctly uses `asyncio.to_thread()` for CPU-bound work (fixed #2388).

### Dimension 4: Processing Engine

`ProcessingEngine` is initialized as singleton at startup (max_concurrent_jobs=2). `_jobs_lock` and `_processor_lock` guard all dict mutations (fixed #2320, #2435). Semaphore enforces concurrency cap.

Audio processing calls (`ChunkedProcessor.process_chunk`) are offloaded via `asyncio.to_thread()`. No blocking event loop starvation in the streaming hot path.

`_background_auto_scan` in startup.py is fired with `asyncio.create_task()` (non-blocking) with outer `except Exception` safety net.

**Known issue**: `_preprocess_upcoming_chunks` in enhancement.py:108-109 calls `processor.get_wav_chunk_path(chunk_idx)` synchronously on the asyncio event loop → Existing #2330.

### Dimension 5: Schema Consistency

Most endpoints return untyped `dict[str, Any]` (using `response_model=None`) rather than declared Pydantic models. This prevents OpenAPI schema generation and client-side validation.

**Known schema gap**: Several endpoints return `track_path: track.filepath` → BE-01.

Pagination shapes are consistent across library endpoints. `total`, `offset`, `limit`, `has_more` used uniformly. Album search was correctly updated to return `(albums, total)` tuple (fixes INT-06 / #2482).

`WebSocketMessageType` enum is missing `fingerprint_progress`, `seek_started` → Existing #2282.

### Dimension 6: Middleware & Configuration

CORS: `allow_origins` is an explicit allowlist (localhost:3000-3006, 8765). `allow_credentials=True` is not combined with wildcard `["*"]` — secure.

Router registration: 11 routers explicitly registered in `config/routes.py`. `processing_api`, `cache_streamlined`, and `similarity` routers conditionally registered with error handling. ✓

Middleware order: `NoCacheMiddleware` added before `CORSMiddleware`. Per Starlette docs, middleware is processed outermost-to-innermost, so CORS runs first on inbound requests — correct.

`--dev` flag: disables API docs (`/api/docs`, `/api/redoc`) in production. StaticFiles not mounted in dev mode to preserve WebSocket routes. ✓

Logging: Standard Python logging at INFO level. No sensitive data redaction other than the filepath fix. Stack traces logged at ERROR level in exception handlers but not returned to clients.

### Dimension 7: Error Handling & Resilience

Global exception handler: No explicit catch-all added to the FastAPI app. FastAPI's default 500 handler returns `{"detail": "Internal Server Error"}` without stack traces. ✓

All router handlers wrap business logic in `try/except` with `HTTPException` re-raise and generic 500 fallback.

`_background_auto_scan`: outer `except Exception` at startup.py:123 catches all failures and broadcasts `library_scan_error`. ✓

`process_chunk_safe()`: exceptions propagate up to `stream_enhanced_audio` which sends `audio_stream_error` message to client and returns (no hanging streams). Chunk cache invalidation on failure prevents replay of corrupt entries. ✓

**Known issue**: Scan worker exception handler loses stack trace (scan_e logged but traceback not captured) → Existing #2331.

### Dimension 8: Performance & Resource Management

`asyncio.to_thread()` used for: chunk processing, file metadata reads (soundfile), scan operations, processor initialization. Event loop protected from CPU-bound work. ✓

SQLAlchemy connection pooling: `pool_pre_ping=True` set in LibraryManager (confirmed by CLAUDE.md). Repository pattern prevents raw SQL and N+1 queries. ✓

Memory management: Normal streaming path reads one 15s chunk at a time (#2121 fix). Enhanced streaming streams via cached numpy arrays — no disk round-trip. ✓

`SimpleChunkCache` LRU with max 50 chunks. Global semaphore limits concurrent streams to 10.

**Known issues**:
- webm_streaming loads entire audio file per chunk (#2295)
- Metadata router has synchronous I/O calls (#2317)
- `_send_pcm_chunk` can produce oversized WebSocket frames (#2257)

### Dimension 9: Test Coverage

Backend test suite is extensive: 90+ test files in `tests/backend/` covering player API, streaming, WebSocket, chunk processing, enhancement, library operations, artwork, schemas, migrations, concurrency, error handling. ✓

**Known gaps**:
- No concurrent WebSocket streaming stress tests (#2334)
- Streaming timeout scenarios untested (#2333)
- ArtworkService has zero test coverage (#2305)

---

## Findings

### BE-01: `add_to_queue` Leaks Filesystem Path; `load_track` REST Response Leaks Path
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/player.py:233` and `player.py:383-388`
- **Status**: NEW

**Description**: Issue #2479 fixed the `track_loaded` WebSocket broadcast to omit `filepath`. However, three other leak points were not addressed:

1. `load_track` REST response (line 233) still returns `"track_path": track.filepath` to the caller
2. `add_to_queue` WebSocket broadcast (lines 383-385) still includes `"track_path": track.filepath` in the `queue_updated` message to ALL connected clients
3. `add_to_queue` REST response (line 388) returns `"track_path": track.filepath`

**Evidence**:

`load_track` REST response (player.py:233):
```python
return {"message": "Track loaded successfully", "track_path": track.filepath}
```

`add_to_queue` broadcast and response (player.py:383-388):
```python
await connection_manager.broadcast({
    "type": "queue_updated",
    "data": {"action": "added", "track_path": track.filepath}
})
return {"message": "Track added to queue", "track_path": track.filepath}
```

**Impact**: Server filesystem paths broadcast to all WebSocket clients on every `add_to_queue` call. REST callers also receive the path. In a network-accessible deployment, any connected browser tab can learn the music folder layout via queue operations.

**Suggested Fix**: Replace `track_path` with `track_id` in all three locations. For REST responses that need a path (e.g. for client-side display), expose only the relative filename, not the absolute path.

---

### BE-02: Background Auto-Scan Progress Callback Still Reports Directory Name (Incomplete Fix of #2384)
- **Severity**: MEDIUM
- **Dimension**: Route Handlers / WebSocket
- **Location**: `auralis-web/backend/config/startup.py:80`
- **Status**: NEW

**Description**: Issue #2384 identified that `scan_progress` WebSocket messages send a directory name in the `current_file` field instead of the filename being scanned. The fix was applied to the scan endpoint in `routers/library.py:518`:

```python
# library.py:518 — FIXED
"current_file": progress_data.get('current_file') or progress_data.get('file'),
```

However, the background auto-scan triggered at startup (`config/startup.py`) was **not updated** and still contains the original bug:

```python
# startup.py:80 — STILL BROKEN
"current_file": progress_data.get('directory'),
```

**Evidence**:

startup.py progress callback:
```python
await connection_manager.broadcast({
    "type": "scan_progress",
    "data": {
        "current": processed,
        "total": total,
        "percentage": percentage,
        "current_file": progress_data.get('directory'),  # ← directory, not filename
    }
})
```

library.py (correctly fixed):
```python
"current_file": progress_data.get('current_file') or progress_data.get('file'),
```

**Impact**: The auto-scan that runs at application startup (scanning `~/Music`) sends directory names in `current_file`. Any UI progress indicator showing "Scanning: …" will display the folder name instead of the file being processed during startup scans. This is the most common scan path for new users.

**Suggested Fix**: Apply the same fix as in library.py:518 to startup.py:80. Change `progress_data.get('directory')` to `progress_data.get('current_file') or progress_data.get('file')`.

---

### BE-03: `set_volume` POST Endpoint Accepts `volume` as Query Parameter (Schema Inconsistency)
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/player.py:316`
- **Status**: NEW

**Description**: The `POST /api/player/volume` endpoint declares `volume` as a bare `float` function parameter. FastAPI treats all simple scalar types in POST handler signatures as **query parameters**, not request body parameters. The client must call `POST /api/player/volume?volume=75.0`. If the frontend sends a JSON body `{"volume": 75}`, FastAPI returns 422 (Unprocessable Entity) because `volume` is missing from the query string.

All other player endpoints use Pydantic `BaseModel` subclasses (e.g. `LoadTrackRequest`, `SeekRequest`, `SetQueueRequest`) to receive body data. `set_volume` is the only exception.

**Evidence**:

player.py:316:
```python
@router.post("/api/player/volume", response_model=None)
async def set_volume(volume: float) -> dict[str, Any]:  # ← query param, not body
```

Correctly-formed endpoints in the same file:
```python
class SeekRequest(BaseModel):
    position: float

async def seek_position(request: SeekRequest) -> dict[str, Any]:  # ← body via Pydantic
```

**Impact**: Calls via JSON body (the REST convention used everywhere else) return 422. Tests targeting this endpoint with JSON body will also fail with 422. The same anti-pattern exists in the enhancement router for `toggle_enhancement(enabled: bool)`, `set_enhancement_preset(preset: str)`, and `set_enhancement_intensity(intensity: float)` — all use scalar query parameters on POST routes.

**Suggested Fix**: Replace the bare `volume: float` parameter with a Pydantic model:
```python
class SetVolumeRequest(BaseModel):
    volume: float = Field(ge=0.0, le=100.0)

async def set_volume(request: SetVolumeRequest) -> dict[str, Any]:
```
Apply the same pattern to the three enhancement endpoints. Alternatively, annotate each scalar with `Body()` to explicitly declare body intent without a wrapper model.

---

## Previously-Confirmed Existing Issues (Not Re-Reported)

| Issue | Description |
|-------|-------------|
| #2330 | Enhancement router `get_wav_chunk_path` blocks event loop without `asyncio.to_thread` |
| #2328 | `ProcessorFactory` cache eviction unsafe during concurrent dict iteration |
| #2326 | `_chunk_tails` dict accessed concurrently without lock causing crossfade race |
| #2324 | `processing_api` router registration catches only `ImportError` |
| #2317 | metadata.py 4 synchronous I/O calls in async handlers |
| #2315 | `AudioStreamController._stream_type` shared state across calls |
| #2314 | Module-level processor caches lack thread safety |
| #2312 | system.py variable name `data` shadowed in WebSocket handler |
| #2301 | `get_mastering_recommendation` blocks event loop with synchronous I/O |
| #2296 | Fire-and-forget `asyncio.create_task` without exception handling |
| #2295 | webm_streaming loads entire audio file per chunk request |
| #2282 | `fingerprint_progress` and `seek_started` missing from `WebSocketMessageType` enum |
| #2257 | `_send_pcm_chunk` stereo framing can produce oversized WebSocket frames |
| #2334 | No concurrent WebSocket streaming stress tests |
| #2333 | Streaming timeout scenarios untested |
| #2331 | Scan worker exception handler loses stack trace |
