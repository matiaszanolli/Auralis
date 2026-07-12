# Backend-Frontend-Engine Integration Audit — 2026-03-01

**Auditor**: Claude Sonnet 4.6 (automated)
**Scope**: 7 cross-layer data flows — Engine ↔ Backend ↔ Frontend
**Method**: 3 parallel exploration agents (Flows 1+5, Flows 2+4, Flows 3+6+7) followed by manual verification of all candidate findings against source. 12 false positives from agents eliminated.

---

## Executive Summary

The Auralis integration layer is in good shape overall. The WebSocket audio pipeline (Flows 1 and 5) has a correct, well-tested binary encoding/decoding path, consistent message schemas, proper reconnection with state recovery, and correct stream-type isolation between enhanced and normal playback. Library browsing (Flow 2), scanning (Flow 4), similarity (Flow 6), and artwork (Flow 7) all function correctly at runtime.

**Results**: 3 new confirmed findings (0 CRITICAL, 0 HIGH, 0 MEDIUM*, 3 LOW).

*INT-01 is technically a MEDIUM test-correctness bug, but not a runtime or data-integrity issue.

| Severity | New | Total Open |
|----------|-----|------------|
| CRITICAL | 0 | 0 |
| HIGH | 0 | 0 |
| MEDIUM | 1 | 1 |
| LOW | 2 | 2 |

---

## Flow-by-Flow Summary

### Flow 1: Track Playback — CLEAN

All boundary contracts verified correct:

| Checkpoint | Status |
|-----------|--------|
| WebSocket URL (`/ws`, port 8765) | ✅ Matches on both sides |
| Play command fields (`track_id`, `preset`, `intensity`) | ✅ Exact match |
| `stream_start` message fields (sample_rate, channels, total_chunks, etc.) | ✅ Exact match |
| Binary frame format: float32 LE, Base64, split at 400KB | ✅ Encoder/decoder aligned |
| Crossfade: server-side only, frontend does not re-apply | ✅ Correct split |
| Error message format (`track_id`, `error`, `code`, `stream_type`) | ✅ Both sides handle |
| Stream type isolation (`stream_type` field filters messages per hook) | ✅ Correct design |
| Concurrent stream semaphore (10 max) | ✅ OOM prevention |

### Flow 2: Library Browsing — CLEAN

| Checkpoint | Status |
|-----------|--------|
| Pagination `has_more` formula | ✅ `(offset + len(items)) < total` and `(offset + limit) < total` are both mathematically equivalent (see false positives) |
| camelCase/snake_case conversion | ✅ `api/transformers/` layer handles conversion; hooks have documented fallbacks |
| Null artwork handling | ✅ `track.artwork_url \|\| track.album_art \|\| track.albumArt` fallback chain |
| Album `trackCount` / `track_count` | ✅ `useLibraryQuery` uses `??` fallback for both forms |
| N+1 queries | ✅ All list endpoints use `selectinload()` after #2516, #2518, #2613 |

### Flow 3: Audio Enhancement — INT-01

| Checkpoint | Status |
|-----------|--------|
| Preset field validation (valid preset list) | ✅ Validates correctly; frontend sends valid values |
| Intensity range validation | ❌ **INT-01**: validator clamps silently; tests expect HTTP 400 |
| Config field names (snake_case, consistent throughout) | ✅ Consistent |
| Enhancement applied live vs next track | ✅ `set_enhancement_preset` clears buffer and retriggers |

### Flow 4: Library Scanning — CLEAN

| Checkpoint | Status |
|-----------|--------|
| Scan progress via WebSocket (`scan_progress` messages) | ✅ Backend broadcasts progress |
| Duplicate detection on rescan | ✅ `existing = session.query(Track).filter(Track.filepath == ...)` |
| Concurrent scan guard | ✅ `_scan_lock` prevents overlapping scans |
| HTTP fetch timeout for large scans | ✅ `fetch()` in Electron uses Chromium, which has no effective timeout on localhost connections; not a concern for desktop app |

### Flow 5: WebSocket Lifecycle — CLEAN

| Checkpoint | Status |
|-----------|--------|
| Reconnection with exponential backoff | ✅ 1s → 30s max, configurable |
| Last stream command replayed on reconnect | ✅ `singletonLastStreamCommand` persisted and re-issued |
| Control message queue during disconnect | ✅ `messageQueueRef` flushed on reconnect |
| Heartbeat: PING (frontend every 30s) / PONG (backend) | ✅ Symmetric |
| Disconnection cleanup: `_active_streaming_tasks` cleared | ✅ Idempotent under lock (#2425) |
| Origin validation (localhost only) | ✅ Rejects non-localhost with code 4003 (#2206) |
| Open issue #2606 (no player state push on reconnect) | Existing open issue — not re-reported |

### Flow 6: Fingerprint & Similarity — CLEAN

| Checkpoint | Status |
|-----------|--------|
| Similarity response fields (`track_id`, `similarity_score`, etc.) | ✅ Manual snake→camel conversion in `useSimilarTracks.ts:168-176`; explicit and correct |
| Missing fingerprint handling | ✅ Backend queues and returns 400 with message; frontend shows error |
| Similarity scores range (0.0–1.0) | ✅ Consistent between engine and API |

### Flow 7: Artwork — CLEAN (2 type definition LOW findings)

| Checkpoint | Status |
|-----------|--------|
| Album artwork served at `/api/albums/{id}/artwork` | ✅ Correct |
| Path traversal protection | ✅ `resolve(strict=False)` + allowlist check (#2508) |
| `extract_artwork` HTTP response: `artwork_url` field | ❌ **INT-03**: frontend type defines `artwork_path` but result unused at runtime |
| `artwork_updated` WebSocket event field `artwork_path` | ✅ Backend and frontend both use `artwork_path` |
| Missing artwork fallback | ✅ Frontend falls back to placeholder |

---

## Findings

---

### INT-01: Enhancement intensity validator clamps silently but tests assert HTTP 400

- **Severity**: MEDIUM
- **Flow**: Flow 3 — Audio Enhancement
- **Boundary**: Backend validator → test contract
- **Location**: `auralis-web/backend/routers/enhancement.py:56-59` ↔ `tests/backend/test_enhancement_api.py:120-132`
- **Status**: NEW → #2625
- **Description**: `SetIntensityRequest` uses a Pydantic `@field_validator` that silently clamps out-of-range intensity to `[0.0, 1.0]` and returns HTTP 200. Two unit tests — `test_set_intensity_below_minimum` and `test_set_intensity_above_maximum` — assert `status_code == 400` with a detail message containing "between 0.0 and 1.0". These tests will always fail against the current implementation.
- **Evidence**:
  ```python
  # enhancement.py:56-59 — clamps silently, returns 200
  @field_validator('intensity')
  @classmethod
  def clamp_intensity(cls, v: float) -> float:
      return max(0.0, min(1.0, v))    # does NOT raise ValueError

  # test_enhancement_api.py:120-125 — expects 400
  def test_set_intensity_below_minimum(self, client):
      response = client.post("/api/player/enhancement/intensity?intensity=-0.1")
      assert response.status_code == 400          # ← always fails; actual is 200
      assert "between 0.0 and 1.0" in response.json()["detail"]
  ```
  The integration test file `test_api_endpoint_integration.py:282-291` was already corrected to accept `[200, 204, 400, 422]` with a comment: *"validator clamps to [0, 1], so this becomes 0.0 and succeeds rather than returning 422"*. The unit test file was not updated.
- **Impact**: `test_enhancement_api.py::TestSetEnhancementIntensity::test_set_intensity_below_minimum` and `test_set_intensity_above_maximum` fail in CI. No runtime or audio quality impact — the frontend already clamps to `[0.0, 1.0]` before sending (`useEnhancementControl.ts:263-268`), so invalid values never reach the backend in normal usage.
- **Suggested Fix**: Update `test_enhancement_api.py:124, 131` to assert `status_code == 200` and verify that the response body reflects the clamped value (e.g., `response.json()["intensity"] == 0.0`). Alternatively, change `clamp_intensity` to `raise ValueError(...)` — but this is a design decision, and clamping is the documented behavior.

---

### INT-02: `scan_complete` WebSocket message field mismatch: `files_added` (backend) vs `tracks_added` (frontend type)

- **Severity**: LOW
- **Flow**: Flow 4 — Library Scanning
- **Boundary**: Backend WebSocket broadcast → Frontend TypeScript type
- **Location**: `auralis-web/backend/routers/library.py:537` → `auralis-web/frontend/src/types/websocket.ts:395`
- **Status**: NEW → #2626
- **Description**: The backend broadcasts `scan_complete` with `files_added` but the frontend TypeScript interface `ScanCompleteMessage` declares the field as `tracks_added`. There is no runtime impact today because `useScanProgress.ts:47-48` ignores the payload entirely (it only resets state). Any future component that reads `message.data.tracks_added` will receive `undefined` silently.
- **Evidence**:
  ```python
  # library.py:534-540
  await connection_manager.broadcast({
      "type": "scan_complete",
      "data": {
          "files_processed": result.files_processed,
          "files_added": result.files_added,      # ← backend field
          "duration": result.scan_time,
      }
  })
  ```
  ```typescript
  // websocket.ts:392-396
  export interface ScanCompleteMessage extends WebSocketMessage {
    type: 'scan_complete';
    data: {
      files_processed: number;
      tracks_added: number;  // ← frontend type: wrong field name
      duration: number;
    };
  }
  ```
- **Impact**: No current runtime failure. Future reads of `message.data.tracks_added` silently return `undefined`. TypeScript does not catch this because `ScanCompleteMessage` is typed but the actual runtime value has a different key.
- **Suggested Fix**: Change `websocket.ts:395` to `files_added: number` to match the backend broadcast.

---

### INT-03: `ArtworkResponse` frontend type uses wrong field name `artwork_path` instead of `artwork_url`

- **Severity**: LOW
- **Flow**: Flow 7 — Artwork
- **Boundary**: Backend HTTP response → Frontend type definition
- **Location**: `auralis-web/backend/routers/artwork.py:187` → `auralis-web/frontend/src/services/artworkService.ts:15`
- **Status**: NEW → #2627
- **Description**: The `POST /api/albums/{id}/artwork/extract` endpoint returns `{ "artwork_url": "..." }` but the frontend `ArtworkResponse` interface declares `artwork_path: string`. There is no runtime impact because the `handleExtractArtwork()` caller discards the return value entirely (only calls `success()` toast and `onArtworkUpdated()` callback). However, the type definition is misleading and will fail silently if code is ever added to use `result.artwork_path`.
- **Evidence**:
  ```python
  # artwork.py:185-189
  return {
      "message": "Artwork extracted successfully",
      "artwork_url": artwork_url,  # ← backend sends "artwork_url"
      "album_id": album_id
  }
  ```
  ```typescript
  // artworkService.ts:13-16
  export interface ArtworkResponse {
    message: string;
    artwork_path: string;  // ← wrong: should be "artwork_url"
    album_id?: number;
  }
  ```
  ```typescript
  // useArtworkHandlers.ts:37-45 — result discarded, so no crash
  const result = await extractArtwork(albumId);
  success(`Extracted artwork from audio files`);  // result not used
  onArtworkUpdated?.();
  ```
- **Impact**: No current runtime failure. Misleading type definition. The download endpoint (`download_artwork`) also returns `artwork_path` in its response body (artwork.py:290, 296) — but note that `download_artwork` returns a different key, and the frontend also discards its result beyond `result.album` and `result.artist`. The `ArtworkResponse` type is only reliable for those two fields.
- **Suggested Fix**: Update `artworkService.ts:15` to `artwork_url: string`. Also verify whether the `download_artwork` endpoint response should share this type or use a narrower one.

---

## False Positives Eliminated

| Candidate Finding | Reason Eliminated |
|------------------|------------------|
| Pagination `has_more`: `(offset + len(items)) < total` vs `(offset + limit) < total` | Both formulas are mathematically identical for valid repository responses (`len(items) ≤ limit`). When the repo returns a partial final page of N items with N < limit: formula 1 gives `(offset + N) < total` which equals `total < total` = FALSE; formula 2 gives `(offset + limit) < total` which also equals FALSE (since `offset + limit > total` on last page). Backend Audit already documented this as a false positive for `artists.py`. |
| `artwork_updated` WebSocket event uses `artwork_path` but value is an API URL | Field name matches on both sides (`artwork_path`). The value happens to be an API URL (not a filesystem path), but both backend and frontend agree on the field name. The naming is semantically misleading but not a contract break. |
| camelCase/snake_case transformer gaps | The project has an explicit transformer layer at `api/transformers/` for albums and artists. Tracks use `useLibraryData.ts:115` with a documented fallback chain (issue #2386). Similarity uses explicit manual mapping in `useSimilarTracks.ts`. All paths are accounted for. Not a systemic gap. |
| `process_parameters` endpoint returns snake_case | The endpoint at `/api/processing/parameters` returns snake_case fields and the frontend type `ProcessingParams` also uses snake_case — no mismatch. The project doesn't require camelCase everywhere; only domain types use camelCase. This endpoint is an internal admin/debug feature. |
| Scan HTTP timeout for large libraries | Auralis is an Electron desktop app (explicitly noted in MEMORY.md). The Chromium WebView used by Electron has no effective HTTP timeout for localhost connections. No timeout issue applies. |
| Similarity error handling: "queued" state not differentiated in UI | Backend correctly queues missing fingerprints. Frontend shows generic error toast. This is a UX gap, not a contract break or data corruption. The fingerprint is correctly enqueued on the backend; the user can retry. Already partially mitigated by background fingerprint processing. |
| `album.artwork_path` vs `artist.artwork_url` schema inconsistency | Historical issue acknowledged in code comments (issue #2110). Transformers at `albumTransformer.ts:30` and `artistTransformer.ts:29` both correctly map to `artworkUrl` (camelCase) for the domain model. Not a runtime bug. |
| Artist list fallback: `artists[]` and `artist: ""` both present in track response | Frontend correctly handles both via `Array.isArray(track.artists) ? track.artists[0] : track.artist || 'Unknown Artist'`. Working and documented. Not a bug. |

---

## Dimension Summary

| Flow | Status |
|------|--------|
| Flow 1: Track Playback | ✅ Clean |
| Flow 2: Library Browsing | ✅ Clean |
| Flow 3: Audio Enhancement | ⚠️ INT-01 (test mismatch) |
| Flow 4: Library Scanning | ✅ Clean |
| Flow 5: WebSocket Lifecycle | ✅ Clean |
| Flow 6: Fingerprint & Similarity | ✅ Clean |
| Flow 7: Artwork | ⚠️ INT-03 (type definition) |

---

## Summary Table

| Finding | Severity | Flow | Status | Issue |
|---------|----------|------|--------|-------|
| INT-01: Enhancement intensity validator clamps but tests expect HTTP 400 | MEDIUM | Flow 3 | NEW → #2625 |
| INT-02: `scan_complete` field `files_added` vs `tracks_added` type mismatch | LOW | Flow 4 | NEW → #2626 |
| INT-03: `ArtworkResponse` type uses `artwork_path` instead of `artwork_url` | LOW | Flow 7 | NEW → #2627 |
