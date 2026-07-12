# Backend-Frontend-Engine Integration Audit Report

**Date**: 2026-03-05
**Auditor**: Claude Opus 4.6 (automated)
**Scope**: 7 cross-layer data flows — Track Playback, Library Browsing, Audio Enhancement, Library Scanning, WebSocket Lifecycle, Fingerprint & Similarity, Artwork
**Method**: 4 parallel exploration agents (playback+WS, library+scanning, enhancement+fingerprint, artwork+schemas) followed by manual source code verification of all findings. Existing issues checked against 40 open issues.

## Executive Summary

Integration audit of the Auralis three-layer architecture (React frontend, FastAPI backend, Python audio engine). The system is well-integrated overall: WebSocket protocols match, audio streaming is robust with proper chunking/crossfading, and most API contracts are consistent. Found 2 new issues and verified 3 existing open issues.

**Results**: 2 confirmed NEW findings (0 CRITICAL, 0 HIGH, 1 MEDIUM, 1 LOW).

| Severity | Count (NEW) |
|----------|-------------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 1 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| ArtworkResponse type mismatch (`artwork_path` vs `artwork_url`) | #2627 | **STILL OPEN** — Extract endpoint returns `artwork_url` (artwork.py:187), frontend `ArtworkResponse` expects `artwork_path` (artworkService.ts:15) |
| Enhancement intensity clamping silently clamps instead of 400 | #2625 | **STILL OPEN** — `SetIntensityRequest.clamp_intensity()` at enhancement.py:58 clamps to [0,1] without error |
| EnhancementContext shared isProcessing flag races | #2633 | **STILL OPEN** — Shared flag between concurrent API calls |

## New Findings

---

### INT-11: Manual scan endpoint does not broadcast `library_scan_started` WebSocket message

- **Severity**: MEDIUM
- **Flow**: Flow 4 — Library Scanning
- **Boundary**: Backend → Frontend (WebSocket)
- **Location**: `auralis-web/backend/routers/library.py:486-505` → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:53-58`
- **Status**: NEW
- **Description**: The frontend `useScanProgress` hook subscribes to `library_scan_started` to reset scan state and set `isScanning: true`. The auto-scanner service (`library_auto_scanner.py:180`) broadcasts this message before scanning, but the manual scan endpoint (`POST /api/library/scan` in `library.py`) does not. When a user manually triggers a scan, the frontend never receives `library_scan_started`, so:
  1. `isScanning` stays `false` until the first `scan_progress` message arrives (seconds later for large directories with slow file discovery)
  2. Previous progress values (current, total, percentage, currentFile) are not reset — stale data from a prior scan may briefly display
- **Evidence**:
  ```python
  # library_auto_scanner.py:178-180 — broadcasts library_scan_started
  await connection_manager_safe_broadcast(
      self._connection_manager,
      {"type": "library_scan_started", "data": {"directories": scan_folders}}
  )

  # library.py:487-505 — manual scan only broadcasts scan_progress, never library_scan_started
  def _progress_callback(progress_data: dict[str, Any]) -> None:
      asyncio.run_coroutine_threadsafe(
          connection_manager.broadcast({
              "type": "scan_progress",  # No library_scan_started broadcast
              "data": { ... }
          }), loop)
  ```

  ```typescript
  // useScanProgress.ts:53-58 — resets state only on library_scan_started
  if (message.type === 'library_scan_started') {
    setState((prev) => ({
      ...INITIAL_STATE,
      lastResult: prev.lastResult,
      isScanning: true,  // Never set for manual scans until first scan_progress
    }));
  }
  ```
- **Impact**: When a user clicks "Scan Folder" in the UI, the scan status indicator doesn't immediately show. For small folders (< 100 files), the scan may complete before `scan_progress` fires, resulting in no visible scanning feedback at all. For large folders, stale progress from a previous scan may briefly appear.
- **Suggested Fix**: Add a `library_scan_started` broadcast at the start of the manual scan handler in `library.py`, before calling `scanner.scan_directories()`. Mirror the pattern from `library_auto_scanner.py:178-180`.

---

### INT-12: Album serializer uses `artwork_path` while track and artist serializers use `artwork_url`

- **Severity**: LOW
- **Flow**: Flow 2 — Library Browsing, Flow 7 — Artwork
- **Boundary**: Backend → Frontend (REST)
- **Location**: `auralis-web/backend/routers/serializers.py:44` vs `serializers.py:28,55`
- **Status**: NEW (related to #2627 but distinct — #2627 covers the extract endpoint specifically)
- **Description**: The backend serializer defaults use inconsistent field names for the same concept:
  - `DEFAULT_TRACK_FIELDS` (line 28): `'artwork_url': None`
  - `DEFAULT_ALBUM_FIELDS` (line 44): `'artwork_path': None`
  - `DEFAULT_ARTIST_FIELDS` (line 55): `'artwork_url': None`

  The frontend handles this correctly through separate transformer types (`AlbumApiResponse.artwork_path` and `TrackApiResponse.artwork_url`), so there is no runtime bug. However, the inconsistency:
  1. Forces the frontend to maintain different field name expectations per entity type
  2. Makes the API contract fragile — new consumers must know which entity uses which name
  3. Is the root cause behind #2627 (extract endpoint confusion)
- **Evidence**:
  ```python
  # serializers.py — inconsistent naming
  DEFAULT_TRACK_FIELDS = { 'artwork_url': None, ... }    # line 28
  DEFAULT_ALBUM_FIELDS = { 'artwork_path': None, ... }   # line 44
  DEFAULT_ARTIST_FIELDS = { 'artwork_url': None, ... }   # line 55
  ```

  ```typescript
  // Frontend must use different field names per type
  // types.ts:20
  interface AlbumApiResponse { artwork_path: string | null; }
  // types.ts:40
  interface ArtistApiResponse { artwork_url: string | null; }
  // types.ts:70
  interface TrackApiResponse { artwork_url?: string | null; }
  ```
- **Impact**: No runtime bug (frontend transformers handle it), but increases maintenance burden and confusion. Related to #2627.
- **Suggested Fix**: Rename `artwork_path` to `artwork_url` in `DEFAULT_ALBUM_FIELDS` and update the album serializer's sanitization function (lines 181-187) to use the new name. Update `AlbumApiResponse` in `types.ts` and `albumTransformer.ts` accordingly. This would also resolve #2627 by establishing `artwork_url` as the consistent field name.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| `executor.map(*zip(*chunks))` argument unpacking bug in `parallel_processor.py` | Standard Python idiom. `map(fn, iter_a, iter_b)` calls `fn(a_i, b_i)`. Verified in prior engine audit. |
| Error response format divergence (`ErrorResponse` schema vs `{"detail": "..."}`) | `ErrorResponse` in `schemas.py` is defined but intentionally unused. All routers use FastAPI's built-in `HTTPException(detail=...)` which produces `{"detail": "..."}`. The frontend `fetch` error handling reads `response.json().detail` or `response.statusText`, matching the actual format. The schema is aspirational/unused code, not a contract violation. |
| Missing `library_tracks_removed` broadcast in manual scan | Manual scan only adds tracks. Track removal is done by the auto-scanner's cleanup step (`library_auto_scanner.py:254`). The frontend correctly receives this only from auto-scan. |
| Chunk timing inconsistency between backend and frontend | Backend sends `chunk_duration` and `total_chunks` in `audio_stream_start`. Frontend reads these values directly from the message data, not from hardcoded constants. No mismatch possible. |
| WebSocket `stream_start` vs `audio_stream_start` naming mismatch | Backend sends `audio_stream_start` (audio_stream_controller.py:1127), frontend subscribes to `audio_stream_start` (usePlayEnhanced.ts:715). Names match. Agent report incorrectly used shortened `stream_start` name. |

## Per-Flow Verification Checklist

### Flow 1: Track Playback (Full Pipeline)
- [x] **Schema match**: WebSocket `play_normal`/`play_enhanced` message format matches backend handler expectations
- [x] **Audio streaming**: Backend sends WAV PCM16 chunks via binary frames; frontend decodes with Web Audio API
- [x] **Chunk boundaries**: 15s chunks, 10s interval, 5s overlap — crossfade prevents audible gaps
- [x] **Sample rate**: Passed in `audio_stream_start` message, frontend uses it for `AudioContext`
- [x] **Error handling**: `audio_stream_error` message type handled by both hooks
- [x] **Seek**: Frontend sends `seek` via WebSocket; backend restarts streaming from new position with `is_seek` flag

### Flow 2: Library Browsing
- [x] **Schema match**: Pagination params (`limit`, `offset`) consistent between frontend and backend
- [x] **Response format**: Backend returns `{items/tracks/albums/artists, total, offset, limit, has_more}`; frontend reads these correctly
- [x] **Case conversion**: Frontend transformers correctly convert snake_case → camelCase per entity type
- [x] **Null handling**: Optional fields (`genre`, `year`, `artwork_url`) handled with `?? undefined` in transformers
- [x] **Sort fields**: `order_by` values validated by backend (`title`, `year`, `created_at`, `name`)
- [ ] **Artwork field inconsistency**: Album uses `artwork_path`, others use `artwork_url` — INT-12

### Flow 3: Audio Enhancement
- [x] **Schema match**: Preset names consistent (`adaptive`, `gentle`, `warm`, `bright`, `punchy`)
- [x] **Intensity validation**: Frontend clamps [0,1] before send; backend clamps on receive (defensive)
- [x] **WebSocket broadcast**: `enhancement_settings_changed` received by all connected clients
- [x] **Real-time propagation**: Settings change applies to next chunk without restart
- [ ] **Silent clamping**: Existing: #2625

### Flow 4: Library Scanning
- [x] **Schema match**: `scan_progress` message format matches `ScanProgressMessage` type
- [x] **Schema match**: `scan_complete` message format matches `ScanCompleteMessage` type
- [x] **Error handling**: Backend catches scan exceptions and returns HTTP error
- [x] **Concurrent scans**: `try_acquire_scan_slot()` prevents parallel scans
- [ ] **Missing `library_scan_started`**: INT-11 — manual scan doesn't broadcast it

### Flow 5: WebSocket Lifecycle
- [x] **Connection**: Frontend connects to `ws://localhost:8765/ws`; backend accepts and sends initial state
- [x] **Message routing**: Type-based routing on both sides; all documented message types handled
- [x] **Reconnection**: Exponential backoff (1s → 32s); last command re-issued on reconnect
- [x] **Rate limiting**: 10 messages/second per connection (backend enforced)
- [x] **Cleanup**: Active streaming tasks cancelled on disconnect
- [x] **Initial sync**: Enhancement settings + player state sent on connect (fixes #2507, #2606)

### Flow 6: Fingerprint & Similarity
- [x] **Schema match**: `SimilarTrack` response fields match frontend transformation
- [x] **Missing fingerprint**: Backend returns 400 with "queued for processing" message
- [x] **Graph fallback**: Falls back to real-time search when graph unavailable
- [x] **Score range**: `similarity_score` constrained to [0.0, 1.0] via Pydantic `Field(ge=0.0, le=1.0)`
- [x] **Case conversion**: Frontend converts `track_id` → `trackId`, `similarity_score` → `similarityScore`

### Flow 7: Artwork
- [x] **Image serving**: `GET /api/albums/{id}/artwork` returns `FileResponse` with correct MIME type
- [x] **Cache headers**: `Cache-Control: public, max-age=31536000` (1 year)
- [x] **Path security**: `is_relative_to()` validation prevents path traversal
- [x] **WebSocket broadcasts**: `artwork_updated` with `action` field sent on extract/download/delete
- [ ] **Extract field mismatch**: Existing: #2627 — returns `artwork_url`, service expects `artwork_path`

## Summary Table

| ID | Severity | Flow | Title | Status |
|----|----------|------|-------|--------|
| INT-11 | MEDIUM | Library Scanning | Manual scan endpoint missing `library_scan_started` broadcast | NEW |
| INT-12 | LOW | Library Browsing / Artwork | Album serializer uses `artwork_path` while track/artist use `artwork_url` | NEW (related #2627) |
