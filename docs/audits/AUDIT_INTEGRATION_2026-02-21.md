# Integration Audit — 2026-02-21

**Scope**: Cross-layer integration between audio engine, FastAPI backend, and React frontend.
**Auditor**: Claude (automated)
**Flows Covered**: All 7 (Playback, Library Browsing, Audio Enhancement, Library Scanning, WebSocket Lifecycle, Fingerprint/Similarity, Artwork)

---

## Methodology

Traced all 7 integration flows using parallel static analysis of frontend hooks, backend routers, engine modules, and WebSocket message definitions. Each finding was verified against concrete code before inclusion.

---

## Summary Table

| ID | Severity | Flow | Status | Title |
|----|----------|------|--------|-------|
| INT-01 | HIGH | Playback | NEW | Volume endpoint: frontend sends query param, backend requires JSON body |
| INT-02 | HIGH | Library Browsing | NEW | useLibraryWithStats falls back to mock data on API failure |
| INT-03 | HIGH | Library Scanning | NEW | scan_progress WebSocket broadcasts have no frontend subscriber |
| INT-04 | MEDIUM | WebSocket Lifecycle | NEW | `audio_chunk` TypeScript interface field name wrong: `data` should be `samples` |
| INT-05 | MEDIUM | WebSocket Lifecycle | NEW | `fingerprint_progress` TypeScript interface wrong fields: `progress/stage` vs `status/message` |
| INT-06 | MEDIUM | WebSocket Lifecycle | NEW | `audio_stream_start` TypeScript interface missing 6+ backend fields |
| INT-07 | MEDIUM | Audio Enhancement | NEW | set_enhancement_intensity missing multi-tier buffer manager update |
| INT-08 | MEDIUM | Library Browsing | NEW | `Playlist` domain interface uses snake_case unlike all other domain types |
| INT-09 | MEDIUM | Fingerprint | NEW | Fingerprint completion stats inflated by placeholder rows (lufs=-100.0) |
| INT-10 | MEDIUM | WebSocket Lifecycle | NEW | Enhancement settings not rebroadcast on WebSocket reconnect |
| INT-11 | MEDIUM | Artwork | NEW | Album artwork response returns filesystem path, not API URL |
| INT-12 | LOW | Library Browsing | NEW | `/api/library/albums` duplicates `/api/albums` — dead code endpoint |
| INT-13 | LOW | Artwork | NEW | Artwork MIME type defaults to `image/jpeg` for unrecognized file extensions |

---

## Findings

### INT-01: Volume Endpoint Mismatch — Query Param vs JSON Body
- **Severity**: HIGH
- **Flow**: 1 — Track Playback
- **Boundary**: Frontend → Backend
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:289-293` → `auralis-web/backend/routers/player.py:325-342`
- **Status**: NEW
- **Description**: Frontend sends volume as URL query parameter (`?volume=80`) on a POST request. Backend declares the endpoint with a Pydantic `BaseModel` body parameter (`SetVolumeRequest`), which FastAPI routes to the JSON request body, not the query string. The query parameter is silently ignored; the body is missing or `{}`, causing FastAPI to return `422 Unprocessable Entity`. Volume changes always fail.
- **Evidence**:

  Frontend (`usePlaybackControl.ts:289-293`):
  ```typescript
  const validVolume = Math.max(0.0, Math.min(1.0, volume)) * 100;
  // Comment says: "Backend expects volume as query parameter (0-100)"
  await api.post(`/api/player/volume?volume=${Math.round(validVolume)}`);
  ```

  Backend (`player.py:325-342`):
  ```python
  @router.post("/api/player/volume", response_model=None)
  async def set_volume(body: SetVolumeRequest) -> dict[str, Any]:
      """Set playback volume.
      Args:
          body: JSON body with volume level (0-100, ...)
      """
      normalized_volume = body.volume / 100.0
  ```

  `SetVolumeRequest` model (`player.py:93-100`):
  ```python
  class SetVolumeRequest(BaseModel):
      volume: float
      @field_validator('volume')
      def clamp_volume(cls, v: float) -> float:
          return max(0.0, min(100.0, v))
  ```

- **Impact**: Users cannot change volume via the API. Any call to `setVolume()` will throw a 422 error caught in the hook's `catch` block and shown as an error toast. Volume control is non-functional.
- **Suggested Fix**: Either change the backend to accept `volume: float = Query(...)` query param (matching frontend), or change the frontend to send a JSON body: `await api.post('/api/player/volume', { volume: Math.round(validVolume) })`. The frontend comment is incorrect and must be updated alongside whichever approach is chosen.

---

### INT-02: useLibraryWithStats Falls Back to Mock Data on API Failure
- **Severity**: HIGH
- **Flow**: 2 — Library Browsing
- **Boundary**: Frontend — internal error handling
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:265-281`
- **Status**: NEW
- **Description**: When `fetchTracks()` returns a failure response or throws, the hook calls `loadMockData()`, silently filling the library view with fabricated placeholder tracks. The user cannot distinguish real failure from mock data. The code comments reference issue #2344 as having fixed this ("never fall back to mock data in production"), but the fallback remains in the error handling path.
- **Evidence**:

  ```typescript
  // Line 265-281
  if (view !== 'favourites' && resetPagination) {
    loadMockData();  // ← Still present despite #2344 fix note
  }
  // ...
  } catch (err) {
    console.error('Error fetching tracks:', err);
    setError(errorMsg);
    if (view !== 'favourites') {
      loadMockData();  // ← Second invocation in catch block
    }
  ```

- **Impact**: Any transient backend error (startup delay, port conflict, network issue) shows users 50 fake "Demo Track" entries instead of an error state. Users may not notice the failure and assume the library is empty or contains wrong tracks.
- **Suggested Fix**: Remove both `loadMockData()` calls from the error path. Display an error state/retry UI instead. `loadMockData()` may be retained for Storybook/testing purposes only, invoked explicitly rather than on error.

---

### INT-03: Backend Broadcasts `scan_progress` WebSocket Messages — No Frontend Subscriber
- **Severity**: HIGH
- **Flow**: 4 — Library Scanning
- **Boundary**: Backend → Frontend (WebSocket)
- **Location**: `auralis-web/backend/routers/library.py:506-532` → Frontend (no subscriber file found)
- **Status**: NEW
- **Description**: The backend broadcasts `scan_progress` WebSocket messages during folder scanning. The frontend type system defines `ScanProgressMessage` and includes it in the `AnyWebSocketMessage` union. However, no frontend hook or component subscribes to `scan_progress` messages. Users see no progress indicator during library scans.
- **Evidence**:

  Backend broadcast (`library.py:514-529`):
  ```python
  asyncio.run_coroutine_threadsafe(
      connection_manager.broadcast({
          "type": "scan_progress",
          "data": {
              "current": processed,
              "total": total,
              "percentage": percentage,
              "current_file": progress_data.get('current_file')
          }
      }),
      loop,
  )
  ```

  Frontend grep result: No file calls `subscribe('scan_progress', ...)` or `subscribe('scan_complete', ...)`. The only references to `scan_progress` are in type definitions (`types/websocket.ts`) and test mocks — not in any live component or hook.

- **Impact**: During long scans (100k+ file libraries), the user sees a static loading spinner with no feedback. The scan may appear to have stalled. The progress data is computed and broadcast on the backend but silently discarded by the frontend.
- **Suggested Fix**: Add a `useScanProgress` hook that subscribes to `scan_progress` and `scan_complete` messages and surfaces them in the library management UI. Wire the hook into the scan trigger component.

---

### INT-04: `audio_chunk` TypeScript Interface Has Wrong PCM Field Name
- **Severity**: MEDIUM
- **Flow**: 5 — WebSocket Lifecycle
- **Boundary**: Backend → Frontend (WebSocket schema definition)
- **Location**: `auralis-web/frontend/src/types/websocket.ts:343-350` → `auralis-web/backend/core/audio_stream_controller.py:1040`
- **Status**: NEW
- **Description**: The TypeScript `AudioChunkMessage` interface declares the PCM payload field as `data: string` (base64), but the backend sends the field as `samples: string`. The `decodeAudioChunkMessage` utility correctly reads `data.samples` at runtime (using `message: any`), so audio playback works at runtime. However, the type definition is incorrect, breaking type safety and IDE autocomplete for any typed consumer.
- **Evidence**:

  Backend (`audio_stream_controller.py:1033-1048`):
  ```python
  message = {
      "type": "audio_chunk",
      "data": {
          "chunk_index": chunk_index,
          "chunk_count": total_chunks,
          "frame_index": frame_idx,
          "frame_count": num_frames,
          "samples": pcm_base64,        # ← field is "samples"
          "sample_count": frame_samples.size,
          "crossfade_samples": crossfade_samples,
          "stream_type": _stream_type_var.get(),
      },
  }
  ```

  Frontend TypeScript type (`websocket.ts:343-350`):
  ```typescript
  export interface AudioChunkMessage extends WebSocketMessage {
    type: 'audio_chunk';
    data: {
      track_id: number;      // ← not sent by backend
      chunk_index: number;
      data: string;          // ← wrong: backend sends "samples"
    };
  }
  ```

  Correct runtime decoder (`pcmDecoding.ts:278`):
  ```typescript
  if (!data.samples || typeof data.samples !== 'string') {
    throw new Error('Missing or invalid samples field in audio_chunk');
  }
  ```

- **Impact**: TypeScript compiler will report an error if `AudioChunkMessage.data.samples` is accessed via a typed reference. Any refactor that adds proper typing to `decodeAudioChunkMessage` will immediately break. The `track_id` field in the type definition doesn't exist in backend output.
- **Suggested Fix**: Update `AudioChunkMessage` in `types/websocket.ts` to match backend schema: replace `data: string` → `samples: string`, remove `track_id`, add `chunk_count`, `frame_index`, `frame_count`, `sample_count`, `crossfade_samples`, `stream_type`.

---

### INT-05: `fingerprint_progress` TypeScript Interface Has Wrong Field Names
- **Severity**: MEDIUM
- **Flow**: 6 — Fingerprint & Similarity / WebSocket Lifecycle
- **Boundary**: Backend → Frontend (WebSocket schema definition)
- **Location**: `auralis-web/frontend/src/types/websocket.ts:305-312` → `auralis-web/backend/core/audio_stream_controller.py:1165-1194`
- **Status**: NEW
- **Description**: The TypeScript `FingerprintProgressMessage` interface defines `progress: number` (0-100) and `stage?: string`, but the backend sends `status: string` (enum-like: "analyzing", "complete", "failed", "error", "cached", "queued") and `message: string`. The hook `usePlayEnhanced` correctly reads `status` and `message` via `message: any`, so runtime works, but the type definition is wrong.
- **Evidence**:

  Backend (`audio_stream_controller.py:1175-1185`):
  ```python
  progress_message = {
      "type": "fingerprint_progress",
      "data": {
          "track_id": track_id,
          "status": status,    # e.g. "analyzing", "complete", "failed"
          "message": message,  # human-readable string
          "stream_type": _stream_type_var.get(),
      },
  }
  ```

  Frontend TypeScript type (`websocket.ts:305-312`):
  ```typescript
  export interface FingerprintProgressMessage extends WebSocketMessage {
    type: 'fingerprint_progress';
    data: {
      track_id: number;
      progress: number; // 0-100 — DOES NOT EXIST IN BACKEND
      stage?: string;   // DOES NOT EXIST IN BACKEND
    };
  }
  ```

- **Impact**: Broken type safety for fingerprint progress messages. Any typed consumer using `FingerprintProgressMessage.data.progress` will always get `undefined` at runtime. TypeScript won't flag access of `status`/`message` because they're typed as `any` via cast in the hook.
- **Suggested Fix**: Update `FingerprintProgressMessage.data` to: `{ track_id: number; status: 'analyzing' | 'complete' | 'failed' | 'error' | 'cached' | 'queued'; message: string; stream_type?: string; }`.

---

### INT-06: `audio_stream_start` TypeScript Interface Missing 6+ Backend Fields
- **Severity**: MEDIUM
- **Flow**: 5 — WebSocket Lifecycle
- **Boundary**: Backend → Frontend (WebSocket schema definition)
- **Location**: `auralis-web/frontend/src/types/websocket.ts:326-334` → `auralis-web/backend/core/audio_stream_controller.py:1090-1103`
- **Status**: NEW
- **Description**: The TypeScript `AudioStreamStartMessage` interface only declares `{ track_id, sample_rate, channels, total_chunks }`, but the backend sends 10+ fields including `preset`, `intensity`, `chunk_duration`, `total_duration`, `stream_type`, `is_seek`, `start_chunk`, `seek_position`, and `seek_offset`. The hook `usePlayEnhanced` accesses `message.data.total_duration` (line ~260) which is not in the TypeScript type, causing a type error. Runtime works via `message: any` cast.
- **Evidence**:

  Backend (`audio_stream_controller.py:1087-1103`):
  ```python
  message = {
      "type": "audio_stream_start",
      "data": {
          "track_id": track_id,
          "preset": preset,
          "intensity": intensity,
          "sample_rate": sample_rate,
          "channels": channels,
          "total_chunks": total_chunks,
          "chunk_duration": chunk_duration,
          "total_duration": total_duration,
          "stream_type": _stream_type_var.get(),
          # + seek fields when applicable
      },
  }
  ```

  Frontend TypeScript type (`websocket.ts:326-334`) — only 4 fields declared:
  ```typescript
  export interface AudioStreamStartMessage extends WebSocketMessage {
    type: 'audio_stream_start';
    data: {
      track_id: number;
      sample_rate: number;
      channels: number;
      total_chunks: number;
      // Missing: preset, intensity, chunk_duration, total_duration, stream_type...
    };
  }
  ```

- **Impact**: TypeScript compiler error if `total_duration`, `preset`, or `intensity` accessed via typed reference. Seek resumption logic may silently fail if `seek_position`/`seek_offset` fields are untyped. Prevents meaningful type checking for the most important stream initialization message.
- **Suggested Fix**: Extend `AudioStreamStartMessage.data` to include all 10+ fields. Add optional fields for seek: `is_seek?: boolean; start_chunk?: number; seek_position?: number; seek_offset?: number;`.

---

### INT-07: `set_enhancement_intensity` Endpoint Missing Multi-Tier Buffer Manager Update
- **Severity**: MEDIUM
- **Flow**: 3 — Audio Enhancement
- **Boundary**: Backend internal — enhancement router vs chunked processor
- **Location**: `auralis-web/backend/routers/enhancement.py:276-324` (intensity handler) vs `:196-257` (preset handler)
- **Status**: NEW
- **Description**: When the user changes the enhancement **preset**, the endpoint correctly invalidates the processing cache AND updates the multi-tier buffer manager's position/prediction model. When the user changes the enhancement **intensity**, the endpoint only invalidates the processing cache but does NOT update the multi-tier buffer manager. Pre-buffered chunks at the old intensity level remain in the prediction queue.
- **Evidence**:

  Preset handler updates buffer manager (`enhancement.py:236-250`):
  ```python
  if get_multi_tier_buffer and get_player_state_manager and old_preset != preset:
      buffer_manager = get_multi_tier_buffer()
      ...
      await buffer_manager.update_position(
          track_id=state.current_track.id,
          position=state.current_time,
          preset=preset,
          intensity=enhancement_settings["intensity"]
      )
  ```

  Intensity handler — no buffer update (`enhancement.py:276-315`):
  ```python
  async def set_enhancement_intensity(body: SetIntensityRequest) -> dict[str, Any]:
      enhancement_settings["intensity"] = intensity
      # Cache invalidation present...
      # ← Multi-tier buffer update ABSENT
  ```

- **Impact**: After an intensity change mid-playback, the buffer manager continues pre-fetching chunks using the stale intensity parameter. Pre-buffered chunks at the old intensity level are served to the player, causing audible audio quality/level changes mid-stream that lag behind the user's slider adjustment.
- **Suggested Fix**: Add the same `buffer_manager.update_position()` call in `set_enhancement_intensity` that exists in `set_preset`. Condition on `old_intensity != intensity`.

---

### INT-08: `Playlist` Domain Interface Uses snake_case Unlike All Other Domain Types
- **Severity**: MEDIUM
- **Flow**: 2 — Library Browsing
- **Boundary**: Frontend — type definition inconsistency
- **Location**: `auralis-web/frontend/src/types/domain.ts:86-97`
- **Status**: NEW
- **Description**: The `Playlist` interface uses raw backend snake_case field names (`track_count`, `is_smart`, `created_at`, `modified_at`), while `Track`, `Album`, and `Artist` all use camelCase (`trackCount`, `artworkUrl`, `dateAdded`). There are no transformers for Playlist responses that convert to camelCase, meaning components consuming `Playlist` must handle mixed casing.
- **Evidence**:

  ```typescript
  // domain.ts:86-97 — snake_case (inconsistent)
  export interface Playlist {
    id: number;
    name: string;
    description?: string;
    track_count: number;   // ← should be trackCount
    is_smart: boolean;     // ← should be isSmart
    created_at?: string;   // ← should be createdAt
    modified_at?: string;  // ← should be modifiedAt
  }

  // domain.ts:45-60 — camelCase (consistent pattern)
  export interface Album {
    trackCount: number;
    totalDuration: number;
    artworkUrl?: string;
  }
  ```

- **Impact**: Frontend code accessing `playlist.trackCount` (following the pattern) will always get `undefined`. Components that destructure `{ track_count }` will work but violate the established naming convention. Inconsistency complicates refactoring and increases chance of field name bugs.
- **Suggested Fix**: Add a `PlaylistTransformer` following the `albumTransformer.ts` pattern. Update `Playlist` interface to camelCase. Update all consumer sites (playlist hooks, components).

---

### INT-09: Fingerprint Completion Stats Inflated by Placeholder Rows
- **Severity**: MEDIUM
- **Flow**: 6 — Fingerprint & Similarity
- **Boundary**: Engine → Backend → Frontend (stats display)
- **Location**: `auralis/library/repositories/fingerprint_repository.py:408-484` (claim), `:680-710` (stats)
- **Status**: NEW
- **Description**: The `claim_next_unfingerprinted_track()` atomically inserts a placeholder `TrackFingerprint` row with `lufs=-100.0` to prevent parallel workers from processing the same track. The `get_fingerprint_stats()` method counts all rows in `track_fingerprints`, including these placeholders. A track is reported as "fingerprinted" the instant it is claimed, before the actual computation completes. This can overstate completion by the number of currently-processing tracks.
- **Evidence**:

  Placeholder insert (`fingerprint_repository.py:448-462`):
  ```python
  placeholder = TrackFingerprint(
      track_id=track_id,
      lufs=-100.0,  # sentinel value for "in-progress"
      # all other 24 dimensions = 0.0
      fingerprint_version=1,
  )
  session.add(placeholder)
  session.commit()
  ```

  Stats query counts ALL rows including placeholders (`fingerprint_repository.py:695-698`):
  ```python
  fingerprinted_count = (
      session.query(func.count(TrackFingerprint.id))
      .scalar() or 0
  )
  ```

  Cleanup method exists but not called in normal flow (`fingerprint_repository.py:712-740`):
  ```python
  def cleanup_incomplete_fingerprints(self) -> int:
      # Bulk delete incomplete fingerprints (placeholders with LUFS=-100.0, #2453)
      incomplete_count = session.query(TrackFingerprint).filter(
          TrackFingerprint.lufs == -100.0
      ).delete(...)
  ```

- **Impact**: Frontend progress bar shows 100% fingerprinting completion before workers finish. Tracks with placeholder fingerprints return incorrect similarity scores (all zeros) until computation overwrites the placeholder. Users may trigger similarity search on incompletely fingerprinted libraries.
- **Suggested Fix**: In `get_fingerprint_stats()`, exclude rows where `lufs == -100.0` (incomplete placeholder) from the `fingerprinted_count`. Add: `.filter(TrackFingerprint.lufs != -100.0)`.

---

### INT-10: Enhancement Settings Not Rebroadcast After WebSocket Reconnect
- **Severity**: MEDIUM
- **Flow**: 5 — WebSocket Lifecycle / 3 — Audio Enhancement
- **Boundary**: Backend → Frontend (reconnect state sync)
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:243-248` and `auralis-web/backend/routers/enhancement.py`
- **Status**: NEW
- **Description**: On WebSocket reconnect, the frontend re-issues the last stream command (`play_enhanced`/`play_normal`) to resume audio (issue #2385 fix). However, the backend does not rebroadcast the current `enhancement_settings_changed` state. If the user changed preset or intensity while the WS was disconnected (and the API call completed), the frontend Redux store reflects the new value but the reconnected stream uses the correct backend settings — but if the call failed mid-disconnect, the states diverge silently.
- **Evidence**:

  Reconnect handler re-issues stream (`WebSocketContext.tsx:243-248`):
  ```typescript
  let singletonLastStreamCommand: any = null;
  // Re-issued after every reconnect to restore audio stream (issue #2385).
  ```

  No broadcast of enhancement state on reconnect found in `enhancement.py` or `audio_stream_controller.py`. Backend `enhancement_settings` dict is in-memory; on reconnect the client has no way to verify it matches local state.

- **Impact**: Rare but hard-to-diagnose: after a brief connectivity interruption, the frontend may display different preset/intensity than what is actually applied to the audio stream. The symptom is silent — no error, just audible quality mismatch.
- **Suggested Fix**: On WebSocket reconnect, either (a) include enhancement config in `audio_stream_start` message so frontend can sync state, or (b) have the connection handler broadcast `enhancement_settings_changed` to newly-connected clients with the current settings.

---

### INT-11: Album Artwork Response Returns Filesystem Path Instead of API URL
- **Severity**: MEDIUM
- **Flow**: 7 — Artwork
- **Boundary**: Backend → Frontend (artwork URL)
- **Location**: `auralis-web/backend/routers/artwork.py:165-170` → `auralis-web/frontend/src/hooks/library/useLibraryData.ts:111`
- **Status**: NEW
- **Description**: The artwork extraction endpoint (`POST /api/albums/{id}/artwork/extract`) returns `{"artwork_path": "/home/user/.auralis/artwork/album_123.jpg"}` — a filesystem path. The frontend expects an API URL like `/api/albums/123/artwork` to fetch the image. Storing or displaying the raw filesystem path exposes server internals and doesn't work in the browser.
- **Evidence**:

  Backend response (`artwork.py:165-170`):
  ```python
  return {
      "message": "Artwork extracted successfully",
      "artwork_path": artwork_url,  # Comment says "Returns URL" but it's a path
      "album_id": album_id
  }
  ```

  Frontend artwork field lookup (`useLibraryData.ts:111`):
  ```typescript
  albumArt: track.artwork_url || track.album_art || track.albumArt,
  // Note: backend returns artwork_path (filesystem), not artwork_url (API URL)
  ```

  Database stores filesystem path:
  ```python
  # auralis/library/models/core.py — Album model
  artwork_path = Column(String)  # Filesystem path, e.g. /home/user/.auralis/artwork/123.jpg
  ```

- **Impact**: After artwork extraction, the returned `artwork_path` value is a local filesystem path not accessible to the browser. The album art will not display for newly-extracted artwork until the library is re-fetched (which reads from `/api/albums/{id}/artwork`). The API response field name also misleads callers.
- **Suggested Fix**: Return `artwork_url: f"/api/albums/{album_id}/artwork"` instead of the filesystem path in the extraction response. Update the field name from `artwork_path` to `artwork_url` to match the artist endpoint convention (documented in `types.ts`).

---

### INT-12: `/api/library/albums` Duplicates `/api/albums` — Dead Code
- **Severity**: LOW
- **Flow**: 2 — Library Browsing
- **Boundary**: Backend (endpoint duplication)
- **Location**: `auralis-web/backend/routers/library.py:393-440` vs `auralis-web/backend/routers/albums.py:41-88`
- **Status**: NEW
- **Description**: Two separate router files expose functionally identical album listing endpoints. The frontend routes to `/api/albums` (albums.py). The `/api/library/albums` route in library.py is dead code — same serializer, same pagination, same response structure.
- **Evidence**:

  `library.py:393`: `@router.get("/api/library/albums")`
  `albums.py:41`: `@router.get("/api/albums")`

  Frontend hook routes to albums.py:
  ```typescript
  const QUERY_TYPE_ENDPOINT = {
    albums: '/api/albums',  // ← not /api/library/albums
  };
  ```

- **Impact**: Maintenance burden — any schema change must be applied twice or divergence occurs. Unclear which is canonical.
- **Suggested Fix**: Remove `/api/library/albums` from `library.py`. Retain `/api/albums` in `albums.py` as the canonical endpoint.

---

### INT-13: Artwork MIME Type Defaults to `image/jpeg` for Unrecognized Extensions
- **Severity**: LOW
- **Flow**: 7 — Artwork
- **Boundary**: Backend — artwork GET response
- **Location**: `auralis-web/backend/routers/artwork.py:109-112`
- **Status**: NEW
- **Description**: When serving artwork, the endpoint uses `mimetypes.guess_type()` and falls back to `image/jpeg` if the type is unknown or not an image. A PNG file with a missing or mismatched extension will be served with `Content-Type: image/jpeg`, causing browser decoding failure.
- **Evidence**:

  ```python
  media_type, _ = mimetypes.guess_type(str(requested_path))
  if not media_type or not media_type.startswith("image/"):
      media_type = "image/jpeg"  # Default even for PNG files
  ```

  The extraction layer correctly detects PNG:
  ```python
  # auralis/library/artwork.py:145-146
  mime_type = 'image/png' if artwork_file.suffix.lower() in ['.png'] else 'image/jpeg'
  ```

- **Impact**: PNG artwork files with unknown extensions served with wrong MIME type will display as broken images in the browser.
- **Suggested Fix**: Read the file magic bytes (first few bytes) to detect PNG (`\x89PNG`) vs JPEG (`\xFF\xD8`) instead of relying on file extension alone. Use `python-magic` or inline byte check.

---

## Flows with No New Findings

- **Flow 6 (Fingerprint/Similarity)**: Similarity schema (`distance` + `similarity_score`) correctly matched between `SimilarTrack` Pydantic model and frontend `SimilarTrack` interface. Missing fingerprint gracefully enqueues and frontend polls until ready. No new issues beyond INT-09.
- **Flow 5 (WebSocket Lifecycle)**: Reconnection handling (issue #2385) correctly re-issues stream commands with exponential backoff. Origin header validation present and correct (#2413). Backpressure correctly implemented on backend via bounded `asyncio.Queue(maxsize=4)`. The type definition issues (INT-04, INT-05, INT-06) are the only new concerns.

---

## Previously Reported — Not Re-filed

| Finding | Covered By |
|---------|-----------|
| Backend `play_enhanced` ignores preset/intensity in play message | #2256 |
| startStreaming hardcodes intensity 1.0 | #2255 |
| Dual AudioFingerprint schema interfaces | #2280 |
| WebSocket endpoint no authentication | #2206 |
| AudioStreamController._stream_type assumes per-request instantiation | #2315 |
| ScriptProcessorNode deprecated (no AudioWorklet) | #2347 |
| Album fingerprint _pct field mapping | AUDIT_INTEGRATION_2026-02-19 INT-01 |
