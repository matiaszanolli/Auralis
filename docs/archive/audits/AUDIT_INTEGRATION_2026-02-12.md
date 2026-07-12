# Integration Audit Report — 2026-02-12

## Executive Summary

Traced 7 critical data flows across the Frontend → Backend → Engine boundaries. Found **37 integration issues**: 6 CRITICAL, 11 HIGH, 14 MEDIUM, 6 LOW. The most severe findings are audio corruption bugs in the normal playback path (wrong sample rate, overlapping chunks), a completely broken scan endpoint, and pervasive schema mismatches that prevent real-time sync and artwork display.

| Severity | Count | Key Themes |
|----------|-------|------------|
| CRITICAL | 6 | Audio playback corruption, broken scan endpoint, broken playback control, broken enhancement sync |
| HIGH | 11 | Schema mismatches, artwork field chaos, overlapping audio chunks, dual hook collision, error format mismatch |
| MEDIUM | 14 | Volume scale, type inconsistencies, missing validation, dead schemas, stale closures |
| LOW | 6 | Dead code, cache inconsistency, minor naming issues |

---

## Findings

### CRITICAL

### INT-01: usePlayNormal does not match AudioContext sample rate to source
- **Severity**: CRITICAL
- **Flow**: Track Playback
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:210-213`
- **Status**: NEW
- **Description**: `usePlayNormal` creates an `AudioContext` with no `sampleRate` option, defaulting to hardware rate (typically 48000Hz). Source audio is often 44100Hz. The `AudioPlaybackEngine` consumes samples at the AudioContext rate, not the source rate.
- **Evidence**:
  ```typescript
  // usePlayNormal.ts:210-213 — NO sampleRate param
  audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();

  // usePlayEnhanced.ts:259-270 — CORRECTLY matches source
  audioContextRef.current = new AudioContextClass({ sampleRate: sourceSampleRate });
  ```
- **Impact**: All unprocessed playback runs ~8.8% too fast (48000/44100). A 3-min song finishes in ~2:45 with raised pitch.
- **Suggested Fix**: Pass `{ sampleRate: message.data.sample_rate }` to AudioContext constructor, matching `usePlayEnhanced`.

### INT-02: stream_normal_audio sends overlapping chunks without crossfade
- **Severity**: CRITICAL
- **Flow**: Track Playback
- **Boundary**: Backend internal (audio_stream_controller)
- **Location**: `auralis-web/backend/audio_stream_controller.py:596-621`
- **Status**: NEW
- **Description**: Normal streaming uses 15s chunks at 10s intervals (5s overlap). The `crossfade_samples` value passed to `_send_pcm_chunk()` is overridden to 0 at line 813. The comment says "crossfade is already applied server-side" but no server-side crossfade exists for the normal path.
- **Evidence**:
  ```python
  # audio_stream_controller.py:604-607 — overlapping chunks
  start_sample = chunk_idx * interval_samples  # 0, 10s, 20s...
  end_sample = min(start_sample + chunk_samples, len(audio_data))  # 0-15s, 10-25s...

  # Line 813 — crossfade set to 0
  "crossfade_samples": 0,  # "Crossfade is already applied server-side"
  ```
- **Impact**: Every 10 seconds, a 5-second overlap region plays twice, creating echo artifacts. A 3-min song plays as ~3:45.
- **Suggested Fix**: Either apply equal-power crossfade server-side (like `ChunkedAudioProcessor` does), or use non-overlapping chunks for normal path.

### INT-03: usePlaybackControl uses non-existent sendMessage method
- **Severity**: CRITICAL
- **Flow**: Track Playback
- **Boundary**: Frontend internal (hook → context)
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:90` → `auralis-web/frontend/src/contexts/WebSocketContext.tsx:220`
- **Status**: NEW
- **Description**: `usePlaybackControl` destructures `{ sendMessage }` from `useWebSocketContext()`, but the context only exports `send`. All play/pause/stop calls via this hook will crash at runtime.
- **Evidence**:
  ```typescript
  // usePlaybackControl.ts:90 — WRONG
  const { sendMessage } = useWebSocketContext();
  sendMessage({ type: 'play_normal', data: {...} });  // line 117

  // WebSocketContext.tsx:220 — exports "send", not "sendMessage"
  send: (message: any) => void;
  ```
- **Impact**: Play/pause/stop from `usePlaybackControl` throws `TypeError: sendMessage is not a function`.
- **Suggested Fix**: Change `sendMessage` to `send` at line 90.

### INT-04: Scan request body key mismatch — scanning completely broken
- **Severity**: CRITICAL
- **Flow**: Library Scanning
- **Boundary**: Frontend → Backend
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryData.ts:273` → `auralis-web/backend/routers/library.py:435`
- **Status**: NEW
- **Description**: Frontend sends `{ directory: folderPath }` (singular string as JSON body). Backend expects `directories: List[str]` (plural, as query param per FastAPI convention for bare params).
- **Evidence**:
  ```typescript
  // Frontend: useLibraryData.ts:270-273
  body: JSON.stringify({ directory: folderPath })  // singular, JSON body

  // Backend: library.py:434-435
  async def scan_library(directories: List[str], ...)  // plural, query param
  ```
- **Impact**: Every scan request fails with 422 Validation Error. Library scanning is non-functional.
- **Suggested Fix**: Either change backend to accept Pydantic body model with `directory` field, or change frontend to send `directories` as query param array.

### INT-05: WebSocket enhancement message types mismatch — real-time sync broken
- **Severity**: CRITICAL
- **Flow**: Audio Enhancement
- **Boundary**: Backend → Frontend (WebSocket)
- **Location**: `auralis-web/backend/routers/enhancement.py:162,227,281` → `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:137`
- **Status**: NEW
- **Description**: Backend broadcasts three different message types (`enhancement_toggled`, `enhancement_preset_changed`, `enhancement_intensity_changed`) but frontend subscribes only to `enhancement_settings_changed` — which the backend never sends.
- **Evidence**:
  ```python
  # Backend broadcasts (enhancement.py)
  "enhancement_toggled"          # line 162
  "enhancement_preset_changed"   # line 227
  "enhancement_intensity_changed" # line 281

  // Frontend subscribes (useEnhancementControl.ts:137)
  ['enhancement_settings_changed']  // NONE of the above
  ```
- **Impact**: Other browser tabs/clients never receive enhancement setting changes. Optimistic UI update masks this for the active tab.
- **Suggested Fix**: Either change backend to broadcast `enhancement_settings_changed`, or change frontend to subscribe to all three types.

### INT-06: Two decoupled enhancement config systems
- **Severity**: CRITICAL
- **Flow**: Audio Enhancement
- **Boundary**: Frontend → Backend (REST vs WebSocket)
- **Location**: `auralis-web/backend/routers/enhancement.py` vs `auralis-web/backend/routers/system.py:131-136`
- **Status**: NEW
- **Description**: Enhancement settings are stored via REST endpoints (`/api/player/enhancement/*`) but the `play_enhanced` WebSocket message sends its own `preset`/`intensity` that override the stored settings. The two paths can diverge silently.
- **Evidence**:
  ```python
  # REST path stores settings in memory
  POST /api/player/enhancement/preset  → updates enhancement_settings dict

  # WebSocket path uses per-message values, ignoring stored settings
  data.get("preset", "adaptive")   # system.py:135
  data.get("intensity", 1.0)       # system.py:136
  ```
- **Impact**: Changing preset via REST has no effect on subsequent play_enhanced messages if the frontend sends stale values.
- **Suggested Fix**: Have `play_enhanced` handler read from the stored enhancement settings instead of per-message overrides, or synchronize them explicitly.

---

### HIGH

### INT-07: Both usePlayEnhanced and usePlayNormal subscribe to same WebSocket message types
- **Severity**: HIGH
- **Flow**: Track Playback / WebSocket Lifecycle
- **Boundary**: Frontend internal
- **Location**: `usePlayEnhanced.ts:653-687` and `usePlayNormal.ts:414-429`
- **Status**: NEW
- **Description**: Both hooks subscribe to `audio_stream_start`, `audio_chunk`, `audio_stream_end`, `audio_stream_error` simultaneously. Both process every chunk, potentially creating dual audio engines playing the same data.
- **Impact**: Audio chunks processed by both hooks; dual Redux dispatches; potential double playback.
- **Suggested Fix**: Include `track_id` and `stream_type` in messages; each hook only processes its own.

### INT-08: PlayerStateData assumes camelCase but backend sends snake_case
- **Severity**: HIGH
- **Flow**: Track Playback
- **Boundary**: Backend → Frontend (WebSocket)
- **Location**: `types/websocket.ts:59-70` vs backend `system.py`
- **Status**: NEW
- **Description**: `usePlaybackState` spreads `msg.data` directly into state. Backend sends `current_track`, `is_playing` (snake_case) but `PlayerStateData` interface has `currentTrack`, `isPlaying` (camelCase).
- **Impact**: `currentTrack`, `isPlaying`, `queueIndex` always `undefined` in `usePlaybackState`.
- **Suggested Fix**: Add explicit snake_case → camelCase mapping in `usePlaybackState`, matching `usePlayerStateSync`.

### INT-09: Backend pause destroys streaming task with no resume
- **Severity**: HIGH
- **Flow**: Track Playback
- **Boundary**: Frontend → Backend (WebSocket)
- **Location**: `auralis-web/backend/routers/system.py:295-313`
- **Status**: NEW
- **Description**: Pause message causes `task.cancel()` destroying the streaming task. Frontend can locally pause the engine, but once buffer is exhausted, no more chunks arrive.
- **Impact**: Pause-then-resume causes silence if buffered audio runs out during pause.
- **Suggested Fix**: Use a pause flag instead of cancellation; resume streaming when unpaused.

### INT-10: Album artwork_path leaks filesystem paths to frontend
- **Severity**: HIGH
- **Flow**: Artwork / Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `auralis/library/models/core.py:190` → `auralis-web/frontend/src/api/transformers/albumTransformer.ts:30`
- **Status**: NEW
- **Description**: Album `to_dict()` returns `artwork_path` as absolute filesystem path (e.g., `/home/user/.auralis/artwork/album_1.jpg`). Frontend maps this to `artworkUrl`. Browser cannot load filesystem paths via `<img src>`.
- **Impact**: Album artwork from transformer path never displays. Also exposes internal paths (security concern).
- **Suggested Fix**: Backend should return `/api/albums/{id}/artwork` URL, not filesystem path.

### INT-11: Hardcoded image/jpeg Content-Type for all artwork
- **Severity**: HIGH
- **Flow**: Artwork
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/routers/artwork.py:79`
- **Status**: NEW
- **Description**: `FileResponse` always uses `media_type="image/jpeg"` even for PNG files.
- **Impact**: PNG artwork served with wrong Content-Type. Most browsers handle this, but breaks standards compliance and can confuse image processing.
- **Suggested Fix**: Detect format from file extension or magic bytes.

### INT-12: Track artwork field naming chaos across 4 layers
- **Severity**: HIGH
- **Flow**: Library Browsing / Track Playback
- **Boundary**: All layers
- **Location**: Multiple files
- **Status**: NEW
- **Description**: Track artwork is named differently at every layer: `album_art` (backend `to_dict()`), `albumArt` (useLibraryData), `artwork_url` (WebSocket types), `artworkUrl` (domain type), `coverUrl` (Redux playerSlice).
- **Impact**: Track artwork fails to display in components that use the wrong field name.
- **Suggested Fix**: Standardize on `artworkUrl` in domain types; add consistent mapping at API boundary.

### INT-13: Artist artwork never populated in API responses
- **Severity**: HIGH
- **Flow**: Library Browsing
- **Boundary**: Backend internal
- **Location**: `auralis-web/backend/routers/artists.py:138-144`
- **Status**: NEW
- **Description**: `ArtistResponse` Pydantic model declares `artwork_url` field but the endpoint constructor never sets it. Frontend transformer reads `artwork_path` (different field name).
- **Impact**: Artist artwork always null in API responses.
- **Suggested Fix**: Populate `artwork_url` from database in artist endpoint.

### INT-14: Error response format mismatch (detail vs message)
- **Severity**: HIGH
- **Flow**: All flows
- **Boundary**: Backend → Frontend
- **Location**: All routers → `auralis-web/frontend/src/types/api.ts:27-31`
- **Status**: Existing: #2092
- **Description**: Backend sends `{"detail": "..."}` (FastAPI default), frontend expects `{"message": "..."}`.
- **Impact**: Error messages never displayed to user.

### INT-15: Library stats response shape mismatch
- **Severity**: HIGH
- **Flow**: Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `auralis/library/repositories/stats_repository.py:39-57` → `auralis-web/frontend/src/hooks/library/useLibraryStats.ts:3-16`
- **Status**: NEW
- **Description**: Backend returns `total_duration`, `total_filesize`, `average_dr`, `average_lufs`. Frontend expects `total_duration_formatted`, `total_filesize_gb`, `avg_dr_rating`, `avg_mastering_quality`. None match.
- **Impact**: Most library stats display as undefined.
- **Suggested Fix**: Add formatting in backend response or frontend transformation layer.

### INT-16: No validation of preset/intensity in WebSocket play_enhanced
- **Severity**: HIGH
- **Flow**: Audio Enhancement
- **Boundary**: Frontend → Backend (WebSocket)
- **Location**: `auralis-web/backend/routers/system.py:131-136`
- **Status**: NEW
- **Description**: WebSocket handler extracts `preset` and `intensity` from message data with no validation. REST endpoints validate (preset in VALID_PRESETS, intensity 0-1), but WebSocket path bypasses all validation.
- **Impact**: Invalid presets or out-of-range intensity can crash processing engine.
- **Suggested Fix**: Add same validation as REST path before creating `ChunkedAudioProcessor`.

### INT-17: WebSocket scan progress type mismatch
- **Severity**: HIGH
- **Flow**: Library Scanning
- **Boundary**: Backend → Frontend (WebSocket)
- **Location**: `auralis-web/backend/routers/library.py:487-491` → `auralis-web/frontend/src/types/websocket.ts:286-294`
- **Status**: NEW
- **Description**: Backend broadcasts `library_scan_progress` type; frontend listens for `scan_progress`. Field shapes also differ (backend: `files_found`, `files_processed`; frontend: `current`, `total`, `percentage`).
- **Impact**: Scan progress never shown in frontend UI.
- **Suggested Fix**: Align message type and field names between backend and frontend.

---

### MEDIUM

### INT-18: schemas.py is 569 lines of dead code
- **Severity**: MEDIUM
- **Flow**: Cross-flow schema consistency
- **Boundary**: Backend internal
- **Location**: `auralis-web/backend/schemas.py`
- **Status**: NEW
- **Description**: No router imports or uses any schema from `schemas.py`. All routers use ad-hoc dicts or local Pydantic models.
- **Impact**: False impression of standardized API contracts; 569 lines of unmaintained dead code.
- **Suggested Fix**: Either delete or adopt as canonical schemas across all routers.

### INT-19: Volume scale inconsistency (0-100 vs 0-1)
- **Severity**: MEDIUM
- **Flow**: Track Playback
- **Boundary**: Frontend internal (Redux vs engine)
- **Location**: `playerSlice.ts:73` (0-100) vs `AudioPlaybackEngine.ts:210` (0-1)
- **Status**: NEW
- **Description**: Redux stores volume as 0-100, AudioPlaybackEngine expects 0-1. Direct pass-through clamps to 1.0.
- **Impact**: Volume control may not work correctly between Redux state and audio engine.

### INT-20: usePlayNormal buffer threshold wrong for stereo
- **Severity**: MEDIUM
- **Flow**: Track Playback
- **Boundary**: Frontend internal
- **Location**: `usePlayNormal.ts:328`
- **Status**: NEW
- **Description**: Buffer threshold `sampleRate * 1` counts interleaved samples, giving only 0.5s of stereo audio before playback starts.
- **Impact**: Higher risk of buffer underrun at playback start compared to `usePlayEnhanced` (which uses `sampleRate * channels * 2`).

### INT-21: usePlayNormal time tracking interval never starts
- **Severity**: MEDIUM
- **Flow**: Track Playback
- **Boundary**: Frontend internal
- **Location**: `usePlayNormal.ts:487-495`
- **Status**: NEW
- **Description**: `useEffect` with empty deps runs at mount when `playbackEngineRef.current` is null, causing early return. Interval never created.
- **Impact**: `currentTime` always 0 during normal playback; progress bar frozen.

### INT-22: Dual WebSocket client systems with incompatible formats
- **Severity**: MEDIUM
- **Flow**: WebSocket Lifecycle
- **Boundary**: Frontend internal
- **Location**: `WebSocketContext.tsx` vs `protocolClient.ts`
- **Status**: NEW
- **Description**: Two WebSocket clients connect to `/ws` with different message formats. Backend only handles `WebSocketContext` format; `protocolClient` messages fall through silently.
- **Impact**: Features using `protocolClient` (via Redux middleware) silently fail.

### INT-23: Three competing Track interfaces in frontend
- **Severity**: MEDIUM
- **Flow**: Cross-flow schema consistency
- **Boundary**: Frontend internal
- **Location**: `types/domain.ts:12`, `useLibraryData.ts:18`, `playerSlice.ts:19`
- **Status**: NEW
- **Description**: Three `Track` interfaces with different artwork fields (`artworkUrl`, `albumArt`, `coverUrl`) and different field shapes.
- **Impact**: Cannot pass track data between library, player, and enhancement subsystems without mapping.

### INT-24: SimilarTrack dual types (snake_case vs camelCase)
- **Severity**: MEDIUM
- **Flow**: Fingerprint & Similarity
- **Boundary**: Frontend internal
- **Location**: `similarityService.ts:21-30` vs `useSimilarTracks.ts:32-47`
- **Status**: NEW
- **Description**: Two `SimilarTrack` interfaces with different casing. Components get different shapes depending on which service they use.
- **Impact**: Potential runtime errors when accessing wrong field name.

### INT-25: startStreaming always hardcodes intensity 1.0
- **Severity**: MEDIUM
- **Flow**: Audio Enhancement
- **Boundary**: Frontend internal
- **Location**: `usePlayEnhanced.ts:310`
- **Status**: NEW
- **Description**: Redux `startStreaming` action always receives `intensity: 1.0` regardless of actual intensity.
- **Impact**: UI always shows 100% intensity regardless of actual processing intensity.

### INT-26: Mock fingerprint data in production path
- **Severity**: MEDIUM
- **Flow**: Fingerprint & Similarity
- **Boundary**: Frontend internal
- **Location**: `useFingerprintCache.ts:108-153`
- **Status**: NEW
- **Description**: `simulateFingerprinting()` creates fake fingerprint data with hardcoded values. No guard prevents production execution.
- **Impact**: Cached fake fingerprints could affect similarity calculations and display.

### INT-27: Mixed snake_case/camelCase in Playlist and PlayerState domain types
- **Severity**: MEDIUM
- **Flow**: Cross-flow schema consistency
- **Boundary**: Frontend internal
- **Location**: `types/domain.ts:86-96,117-132`
- **Status**: NEW
- **Description**: `Playlist` uses `track_count`, `is_smart` (snake_case) while other types use camelCase. `PlayerState` mixes both.
- **Impact**: Inconsistent naming convention across the frontend codebase.

### INT-28: Dual album endpoints with inconsistent serialization
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Boundary**: Backend internal
- **Location**: `routers/albums.py` vs `routers/library.py:384-405`
- **Status**: NEW
- **Description**: `/api/albums` and `/api/library/albums` return albums with different field shapes and different pagination behavior.
- **Impact**: Frontend components see different data shapes for the same entity depending on which hook they use.

### INT-29: /api/library/albums has no pagination params
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `routers/library.py:384-405`
- **Status**: NEW
- **Description**: No `limit`/`offset` query params. Response lacks `offset`, `limit`, `has_more` fields. Frontend `useLibraryQuery` expects all five fields.
- **Impact**: Album pagination broken via this endpoint. Only first 50 albums visible.

### INT-30: fetchMore errors silent to user
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Boundary**: Frontend internal
- **Location**: `useLibraryQuery.ts:282-301` and `useLibraryWithStats.ts:354-355`
- **Status**: NEW
- **Description**: `fetchMore()` catches errors but provides no user notification. Loading indicator disappears with no feedback.
- **Impact**: Pagination failures go unnoticed; user sees incomplete results.

### INT-31: Track duration can be null but frontend type is required
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `auralis/library/models/core.py:38` → `types/domain.ts:16`
- **Status**: NEW
- **Description**: DB `duration = Column(Float)` with no default → can be null. Frontend `Track.duration: number` is non-optional.
- **Impact**: Components computing formatted time from null duration may show `NaN:NaN`.

---

### LOW

### INT-32: Cache-busting defeats server cache headers for artwork
- **Severity**: LOW
- **Flow**: Artwork
- **Location**: `artworkService.ts:59`
- **Status**: NEW
- **Description**: `getArtworkUrl()` appends `?t=${Date.now()}` while backend sets 1-year cache header.

### INT-33: Audio streaming types missing from canonical WebSocketMessageType
- **Severity**: LOW
- **Flow**: WebSocket Lifecycle
- **Location**: `types/websocket.ts:12-43`
- **Status**: NEW
- **Description**: `audio_stream_start`, `audio_chunk`, `audio_stream_end`, etc. not in `WebSocketMessageType` union.

### INT-34: No track limit enforcement on /api/library/tracks
- **Severity**: LOW
- **Flow**: Library Browsing
- **Location**: `routers/library.py:83-88`
- **Status**: NEW
- **Description**: Accepts `limit=999999` with no upper bound. Other endpoints cap at 200.

### INT-35: No WebP support in artwork extraction
- **Severity**: LOW
- **Flow**: Artwork
- **Location**: `auralis/library/artwork.py:250-253`
- **Status**: NEW
- **Description**: Only JPEG/PNG recognized. WebP images saved as .jpg with wrong extension.

### INT-36: enhancement_status endpoint returns raw dict, no wrapper
- **Severity**: LOW
- **Flow**: Audio Enhancement
- **Location**: `routers/enhancement.py:307`
- **Status**: NEW
- **Description**: Returns `{enabled, preset, intensity}` directly. Other enhancement endpoints return `{message, settings}`.

### INT-37: genre field: array from backend, string in frontend
- **Severity**: LOW
- **Flow**: Library Browsing
- **Location**: `core.py:136` → `domain.ts:23`
- **Status**: NEW
- **Description**: Backend returns `genres: string[]`, frontend expects `genre?: string`.

---

## Relationships

### Cluster 1: Playback Audio Corruption (INT-01, INT-02, INT-07)
All three cause audio defects in the normal playback path. INT-01 causes speed/pitch issues, INT-02 causes duplication, INT-07 causes dual processing. Together they make normal playback severely broken.

### Cluster 2: Schema Naming Chaos (INT-08, INT-12, INT-23, INT-24, INT-27)
Pervasive camelCase/snake_case inconsistency with no centralized transformation layer. Root cause: no enforced API contract (INT-18 confirms schemas.py is dead code).

### Cluster 3: Artwork Pipeline (INT-10, INT-11, INT-12, INT-13, INT-32, INT-35)
Artwork is broken across multiple paths: wrong field names, filesystem paths leaked, wrong Content-Type, cache inconsistency.

### Cluster 4: Scan + Progress (INT-04, INT-17)
Library scanning is doubly broken: the request fails (field name mismatch), and even if fixed, progress would never display (message type mismatch).

### Cluster 5: Enhancement Desync (INT-05, INT-06, INT-16)
Enhancement settings can't sync in real-time, have two independent config paths, and the WebSocket path lacks validation.

---

## Prioritized Fix Order

1. **INT-03** (sendMessage → send) — 1-line fix, unblocks playback control
2. **INT-01** (AudioContext sample rate) — 1-line fix, fixes pitch/speed
3. **INT-04** (scan body key) — Simple fix, unblocks scanning
4. **INT-02** (overlapping chunks) — Use non-overlapping for normal path
5. **INT-05** (enhancement WS types) — Align message types
6. **INT-08** (player state snake_case) — Add mapping layer
7. **INT-07** (dual hook subscription) — Add stream routing by type
8. **INT-12, INT-10** (artwork naming) — Standardize field names
9. **INT-18** (dead schemas.py) — Either adopt or delete
