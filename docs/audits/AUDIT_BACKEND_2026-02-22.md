# Backend Audit — 2026-02-22

**Scope**: FastAPI backend — route handlers, WebSocket streaming, chunked processing, processing engine, schemas, middleware, error handling, performance, test coverage (9 dimensions).

**Methodology**: Three parallel exploration agents audited Dimensions 1-3, 4-6, and 7-9 respectively. All candidate findings manually verified against source code. 15+ false positives eliminated.

**Prior audit**: First backend audit (2026-02-21) produced 9 findings (#2559-#2567), all CLOSED. This is a second-pass audit looking for issues the first pass missed.

**Result**: 3 NEW findings confirmed. The backend demonstrates strong post-fix hygiene — most patterns identified in the first audit have been properly remediated.

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 3 | BE-16, BE-17, BE-18 |
| LOW | 0 | — |
| **Total** | **3** | |

---

## Findings

### BE-16: Enhancement router uses CHUNK_DURATION instead of CHUNK_INTERVAL for chunk indexing
- **Severity**: MEDIUM
- **Dimension**: Route Handlers / Chunked Processing
- **Location**: `auralis-web/backend/routers/enhancement.py:102,110`
- **Status**: NEW
- **Description**: The enhancement toggle endpoint launches a background task to pre-process upcoming chunks when enhancement is enabled mid-playback. This task calculates chunk indices using `CHUNK_DURATION` (15s — the actual audio length per chunk), but the `ChunkedAudioProcessor` indexes chunks using `CHUNK_INTERVAL` (10s — the playback interval between chunk starts, accounting for 5s overlap). This produces wrong chunk indices and an incorrect total chunk count.
- **Evidence**:

Enhancement router (`enhancement.py:102,110`):
```python
from core.chunk_boundaries import CHUNK_DURATION  # = 15.0s

current_chunk_idx = int(current_time / CHUNK_DURATION)     # Line 102
total_chunks = int(total_duration / CHUNK_DURATION) + 1    # Line 110
```

ChunkedAudioProcessor (`chunked_processor.py:221-223` and `chunk_boundaries.py:49`):
```python
CHUNK_INTERVAL = 10  # seconds - playback interval
self.total_chunks = int(np.ceil(self.total_duration / CHUNK_INTERVAL))
```

For a 60s track at 30s playback position:
- Enhancement router: `chunk_idx = int(30/15) = 2`, `total = int(60/15)+1 = 5`
- Actual processor: `chunk_idx at 30s = int(30/10) = 3`, `total = ceil(60/10) = 6`
- Pre-processes chunks [3,4,5] but processor expects chunks [4,5,6]

- **Impact**: Pre-processing targets wrong chunk indices. The pre-cached WAV files won't be found when the streaming engine requests them, defeating the purpose of the optimization. Users experience a brief audio pause when enabling enhancement mid-playback (the exact scenario this code was meant to prevent).
- **Suggested Fix**: Replace `CHUNK_DURATION` with `CHUNK_INTERVAL` for index calculations:
```python
from core.chunk_boundaries import CHUNK_INTERVAL

current_chunk_idx = int(current_time / CHUNK_INTERVAL)
total_chunks = int(np.ceil(total_duration / CHUNK_INTERVAL))
```

---

### BE-17: WebSocket _send_error sends raw exception messages to client
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming / Error Handling
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:493,630,692,821,1294,1411`
- **Status**: NEW
- **Description**: The HTTP error path was properly sanitized in #2573 (InternalServerError strips exception details, sending only `"Failed to {operation}"`). However, the WebSocket error path was NOT updated — 6 call sites pass raw `str(e)` directly to `_send_error()`, which embeds the exception message in the JSON sent to the client. This can expose filesystem paths, database details, or system configuration.
- **Evidence**:

Six call sites send raw exception strings:
```python
# Line 493
await self._send_error(websocket, track_id, str(e))
# Line 630
await self._send_error(websocket, track_id, str(e))
# Line 692
await self._send_error(websocket, track_id, str(e))
# Line 821
await self._send_error(websocket, track_id, str(e))
# Line 1294
await self._send_error(websocket, track_id, str(e))
# Line 1411
await self._send_error(websocket, track_id, str(e))
```

The `_send_error` method (line 1171-1199) directly embeds the message in JSON:
```python
data: dict[str, Any] = {
    "track_id": track_id,
    "error": error_message,  # Raw exception string
    "code": "STREAMING_ERROR",
    ...
}
await websocket.send_text(json.dumps(message))
```

Example leak: `FileNotFoundError: /home/user/.auralis/chunks/track_123.wav` exposes filesystem structure.

- **Impact**: Information disclosure via WebSocket. While Auralis is a localhost desktop app (mitigating remote exploitation), the principle of defense in depth means internal details should not reach the client. Browser DevTools would show these messages.
- **Suggested Fix**: Sanitize error messages before sending. Log the full exception server-side, send a generic message to the client:
```python
logger.error(f"Streaming error for track {track_id}: {e}", exc_info=True)
await self._send_error(websocket, track_id, "Audio streaming failed")
```

---

### BE-18: artist_repository.search() still uses joinedload causing Cartesian product
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis/library/repositories/artist_repository.py:155-156`
- **Status**: NEW (incomplete fix of #2516)
- **Description**: Issue #2516 fixed `artist_repository.get_all()` to use `selectinload` instead of nested `joinedload`, preventing Cartesian product row explosion. However, `artist_repository.search()` was NOT updated and still uses the original `joinedload(Artist.tracks).joinedload(Track.genres)` pattern. For search results with popular artists (many tracks, many genres), this produces massive result sets.
- **Evidence**:

`get_all()` (fixed in #2516, line 111):
```python
# Use selectinload (separate IN queries) instead of nested joinedload
# to avoid the N×M Cartesian-product row explosion (fixes #2516).
.options(
    selectinload(Artist.tracks).selectinload(Track.genres),
    selectinload(Artist.albums)
)
```

`search()` (NOT fixed, line 155):
```python
.options(
    joinedload(Artist.tracks).joinedload(Track.genres),  # Cartesian product!
    joinedload(Artist.albums)
)
```

For a search returning 20 artists averaging 15 tracks with 3 genres each:
- `joinedload`: Returns 20 × 15 × 3 = 900 rows from SQLite
- `selectinload`: Returns 20 + 300 + 900 = 1,220 total rows across 3 queries, but each is flat (no multiplication)

- **Impact**: Artist search becomes slow as library grows. Users searching "The" (common prefix) may trigger queries returning thousands of duplicate rows, causing visible UI lag.
- **Suggested Fix**: Mirror the `get_all()` fix:
```python
.options(
    selectinload(Artist.tracks).selectinload(Track.genres),
    selectinload(Artist.albums)
)
```

---

## Verification Log: False Positives Eliminated

### Agent 1 (Dimensions 1-3)

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| Crossfade tail race despite lock | FALSE POSITIVE | Entire crossfade operation IS inside `async with self._chunk_tails_lock:` (lines 925-942). Agent misread the lock scope |
| stream_normal_audio doesn't clean _chunk_tails | FALSE POSITIVE | Normal streaming never populates `_chunk_tails` (crossfade_samples=0). Nothing to clean up |
| Last chunk truncation in stream_normal_audio | FALSE POSITIVE | Short last chunks are standard in audio streaming. Frontend receives `total_duration` in stream_start and handles variable chunk sizes |

### Agent 2 (Dimensions 4-6)

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| RateLimitMiddleware memory leak | FALSE POSITIVE | Auralis is a localhost desktop app — only 1 client IP. Max 4 entries (1 IP × 4 rate-limited paths). Not a practical concern |
| RateLimitMiddleware race condition | FALSE POSITIVE | No `await` between lines 107-119. asyncio single-threaded model prevents races within synchronous code sections |
| ConnectionManager stale WS cleanup race | FALSE POSITIVE | Snapshot + `if stale in` check pattern is correct for asyncio. `disconnect()` and `broadcast()` don't interfere destructively |
| CORS ws:// origin scheme entries | FALSE POSITIVE | Redundant but harmless. Browsers always send `Origin: http://...` for WebSocket upgrades. No security impact |
| Version endpoint fallback stale | FALSE POSITIVE | Currently matches `auralis/version.py` (1.2.1-beta.1). Fragile pattern but not a bug today |
| NoCacheMiddleware inefficiency | FALSE POSITIVE | Trivial performance impact. Early return for `/api` paths already present |

### Agent 3 (Dimensions 7-9)

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| Audio format error handling gap | FALSE POSITIVE | `ChunkedAudioProcessor` raises `ValueError` with descriptive messages (e.g., "Unsupported format"). The WebSocket path sends these via `_send_error` (which is BE-17, but the error differentiation itself works) |
| handle_query_error always returns 500 | NOT FILED | True that all DB errors become 500, but for a localhost desktop app, this is LOW priority and doesn't cause practical user issues |
| FFmpeg process leak on timeout | FALSE POSITIVE | `proc.kill()` + `await proc.communicate()` correctly drains pipes. The `except Exception: pass` is for cleanup — if communicate() fails after kill, the process is already dead |
| WebSocket error not sent before close | FALSE POSITIVE | The system.py handler catches `WebSocketDisconnect` (expected), and other exceptions are caught at the individual message handler level, not at the connection level |
| N+1 query in artists router | FALSE POSITIVE | `artist_repository.get_all()` already uses `selectinload` (fix #2516). However, `search()` was NOT fixed → promoted to BE-18 |
| Semaphore not released on error | FALSE POSITIVE | Agent self-corrected. All error paths include `self._stream_semaphore.release()` |
| WebM temp file cleanup | FALSE POSITIVE | `finally` block always runs. `unlink(missing_ok=True)` handles race conditions. Warning log is appropriate for non-critical cleanup |

---

## Dimensions Verified Clean

The following dimensions had no new findings after thorough verification:

1. **Route Handler Correctness**: All handlers `async def`. Input validation via Pydantic. Proper `HTTPException` usage. No route conflicts.
2. **Chunked Processing**: Chunk boundaries correct (CHUNK_INTERVAL-based). Equal-power crossfade curves. First/last chunk handled. Sample rate consistent.
3. **Processing Engine**: Properly uses `asyncio.to_thread` for sync operations. Per-request ChunkedAudioProcessor instances. Configuration propagation correct.
4. **Schema Consistency**: All Pydantic models well-typed. Validators enforce ranges. Consistent snake_case with camelCase aliases.
5. **Middleware & Configuration**: CORS restricted to localhost. Security headers present (#2574). Rate limiting on expensive endpoints (#2575). Startup/shutdown events handle resources.
6. **Error Handling**: `InternalServerError` sanitizes HTTP responses (#2573). Global exception handler present. Timeouts on audio processing (30s).
7. **Test Coverage**: Router tests exist. WebSocket protocol tests present. Chunked processing tests run. Schema validation tests cover key scenarios.
