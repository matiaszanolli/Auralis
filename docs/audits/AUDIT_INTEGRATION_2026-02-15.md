# Integration Audit Report — 2026-02-15

## Executive Summary

Traced **7 critical data flows** end-to-end across Auralis' Frontend ↔ Backend ↔ Engine boundaries, verified regression status of all 37 prior findings from the [Feb 12 audit](AUDIT_INTEGRATION_2026-02-12.md), and identified **33 new integration issues** across 33 GitHub issues (#2250-#2282).

The most urgent findings are:
- **Fingerprint endpoints crash/return zeros** (#2260, #2261): Track fingerprint endpoint references non-existent model attributes (`fp.sub_bass` vs `fp.sub_bass_pct`), causing `AttributeError` at runtime. Album fingerprint silently returns all-zero data.
- **Scan broken in recommended hook** (#2262): `useLibraryWithStats` sends `{directory}` (singular) while backend expects `{directories}` (plural list), failing with 422.
- **Artwork field name regression** (#2250): `usePlayerStateSync` maps to old `coverUrl` while `Track` type now expects `artworkUrl`, silently dropping artwork.

| Severity | Count | Key Themes |
|----------|-------|------------|
| CRITICAL | 4 | Fingerprint AttributeError, fingerprint zeros, scan field mismatch, artwork regression |
| HIGH | 8 | Pause doesn't stop engine, REST endpoints removed, playlist WS types, playlist body format, shared Redux state, artists array/singular, missing serializer fields, buffer threshold |
| MEDIUM | 15 | Volume scale, intensity hardcoded, backend ignores settings, stereo framing, playlist timestamps, artwork path leak, intensity schema, LibraryStats disconnected, unpaginated albums, similarity defaults, mixed case types, artwork broadcasts, dual fingerprint types, correlation_id stripped, coverUrl in state sync |
| LOW | 6 | Full library fetch, seek time offset, not exported hook, nullable created_at, missing WS types, seek ignores settings |

**Prior findings status**: 10 FIXED, 2 REGRESSIONS, 25 STILL OPEN (many tracked by existing issues).

---

## Regression Check — All 37 Prior Findings (Feb 12 Audit)

### Fixed (10)

| ID | Title | Prior Severity | Evidence |
|----|-------|---------------|----------|
| INT-01 | usePlayNormal AudioContext sample rate mismatch | CRITICAL | Lines 215-227 now pass `{ sampleRate: sourceSampleRate }` |
| INT-02 | stream_normal_audio overlapping chunks | CRITICAL | Lines 596-599: `interval_samples = chunk_samples` (no overlap) |
| INT-03 | usePlaybackControl uses non-existent sendMessage | CRITICAL | Line 90 uses `const { send } = useWebSocketContext()` |
| INT-05 | WS enhancement message types mismatch | CRITICAL | All REST endpoints broadcast `enhancement_settings_changed` |
| INT-06 | Two decoupled enhancement config systems | CRITICAL | `play_enhanced` reads from stored settings per #2103 |
| INT-07 | Frontend pcmDecoding wrong field names | HIGH | `decodeAudioChunkMessage` now uses correct `message.data` fields |
| INT-08 | usePlayNormal doesn't filter stream_type | HIGH | Lines 199, 306, 368, 386 check `stream_type !== 'normal'` |
| INT-16 | No validation of preset/intensity in WS | HIGH | `system.py:174-190` validates preset + clamps intensity 0.0-1.0 |
| INT-17 | WebSocket scan progress type mismatch | MEDIUM | `library.py:487-496` sends matching `scan_progress` type |
| INT-19 | Volume 0-1 vs 0-100 scale mismatch | MEDIUM | `usePlaybackControl.ts:271-272` converts 0-1 → 0-100 |

### Regressions (2)

| ID | Title | Prior Severity | Status | New Issue |
|----|-------|---------------|--------|-----------|
| INT-09 | Track artwork field naming chaos | HIGH | `playerSlice.Track.artworkUrl` renamed but `usePlayerStateSync` still maps to `coverUrl` | **#2250** |
| INT-19 | Volume scale inconsistency | MEDIUM | Three different initial values persist (1.0, 70, 80) across layers | **#2251** |

### Still Open (25)

| ID | Title | Severity | Tracked By |
|----|-------|----------|------------|
| INT-04 | Scan request body key mismatch (`directory` vs `directories`) | CRITICAL | Partial fix — `useLibraryData` fixed but `useLibraryWithStats` still broken → **#2262** |
| INT-10 | Album artwork_path leaks filesystem paths | HIGH | #2237 (path traversal), **#2270** (listing leak) |
| INT-11 | Hardcoded image/jpeg Content-Type | HIGH | #2108 |
| INT-12 | Track artwork field naming chaos across 4 layers | HIGH | Part of #2222 |
| INT-13 | Artist artwork never populated in API responses | HIGH | #2110 |
| INT-14 | Error response format mismatch (detail vs message) | HIGH | #2092 |
| INT-15 | Library stats response shape mismatch | HIGH | **#2272** |
| INT-18 | schemas.py dead code (719 lines, mostly unused) | MEDIUM | #2114 |
| INT-20 | usePlayNormal buffer threshold too low | MEDIUM | #2115, **#2268** |
| INT-21 | usePlayNormal time tracking never starts | MEDIUM | #2115 |
| INT-22 | Dual WebSocket client systems | MEDIUM | #2117, **#2281** |
| INT-23 | Three competing Track interfaces in frontend | MEDIUM | #2222 |
| INT-24 | SimilarTrack dual types (snake_case vs camelCase) | MEDIUM | Manual mapping works |
| INT-25 | startStreaming hardcodes intensity 1.0 | MEDIUM | **#2255** |
| INT-26 | Mock fingerprint data in production path | MEDIUM | #2118 |
| INT-28 | Dual album endpoints with inconsistent serialization | MEDIUM | #2119 |
| INT-29 | /api/library/albums has no pagination | MEDIUM | #2119, **#2273** |
| INT-30 | fetchMore errors silent to user | MEDIUM | General pattern |
| INT-31 | Track duration can be null but frontend type is required | MEDIUM | General pattern |
| INT-32 | Cache-busting defeats server cache headers | LOW | Inconsistent between `artworkService` and `AlbumArt` |
| INT-33 | Audio streaming types missing from canonical WS types | LOW | **#2282** |
| INT-34 | No track limit enforcement | LOW | #2168 |
| INT-35 | No WebP support in artwork extraction | LOW | Part of #2108 |
| INT-36 | enhancement_status returns raw dict | LOW | General pattern |
| INT-37 | genre field: array from backend, string in frontend | LOW | **#2263** |

---

## New Findings

### Flow 1: Track Playback

#### F1-01: usePlayerStateSync maps album_art to coverUrl but Track type expects artworkUrl
- **Severity**: CRITICAL
- **Boundary**: Backend (WebSocket) → Frontend (Redux)
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:70,119` → `auralis-web/frontend/src/store/slices/playerSlice.ts:25`
- **Status**: Regression of #2109 → **#2250**
- **Description**: `usePlayerStateSync.handlePlayerState` maps `state.current_track.album_art` to `coverUrl`, but the `Track` interface now expects `artworkUrl`. The field is silently dropped.
- **Impact**: All track artwork via WebSocket `player_state` is `undefined`. No artwork displays.

#### F1-02: Volume scale inconsistency across three state layers
- **Severity**: MEDIUM
- **Boundary**: Backend → Frontend (multiple layers)
- **Location**: `playerSlice.ts:73` (70) + `usePlaybackState.ts:40` (1.0) + backend `PlayerState` (80)
- **Status**: Regression of #2116 → **#2251**
- **Description**: Three different initial volume values. `usePlaybackState` initializes at 1.0 (0-1 scale) but receives 80 (0-100) from backend.
- **Impact**: Brief volume jump on first WebSocket message.

#### F1-03: usePlaybackControl.pause/stop sends WebSocket but doesn't stop AudioPlaybackEngine
- **Severity**: HIGH
- **Boundary**: Frontend internal (control hook → audio engine)
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:140-188`
- **Status**: NEW → **#2252**
- **Description**: `pause()` and `stop()` send WebSocket messages but never call `playbackEngineRef.current?.pausePlayback()`. Audio continues from buffer for 8-12 seconds after pressing pause.
- **Impact**: Pause/stop appears broken to the user.

#### F1-04: usePlayerAPI.seek sends position in body but backend expects query parameter
- **Severity**: HIGH
- **Boundary**: Frontend (usePlayerAPI) → Backend (player.py)
- **Location**: `usePlayerAPI.ts:220-224` → `player.py:250-251`
- **Status**: NEW → **#2253**
- **Description**: JSON body `{position}` vs FastAPI query parameter. Returns 422.
- **Impact**: All seek via legacy `usePlayerAPI` fails. Only `usePlaybackControl.seek()` works.

#### F1-05: REST play/pause/stop/volume endpoints removed but hooks still call them
- **Severity**: HIGH
- **Boundary**: Frontend → Backend (player.py)
- **Location**: `usePlayerAPI.ts:94,124,238-255` + `usePlaybackControl.ts:276` → `player.py:223-286`
- **Status**: NEW → **#2254**
- **Description**: Backend endpoints commented out. Frontend hooks still call them → 404.
- **Impact**: Volume changes via REST fail silently. Legacy API hooks are dead code.

#### F1-06: startStreaming Redux action hardcodes intensity 1.0 in usePlayEnhanced
- **Severity**: MEDIUM
- **Boundary**: Frontend internal (streaming hooks → Redux)
- **Location**: `usePlayEnhanced.ts:313` + `usePlayNormal.ts:263`
- **Status**: NEW → **#2255**
- **Description**: `handleStreamStart` ignores `message.data.intensity` and hardcodes 1.0.
- **Impact**: Redux `streaming.intensity` always shows 1.0 regardless of actual level.

#### F1-07: Backend play_enhanced ignores frontend-sent preset and intensity
- **Severity**: MEDIUM
- **Boundary**: Frontend → Backend (WebSocket)
- **Location**: `system.py:157-171`
- **Status**: NEW → **#2256**
- **Description**: Server reads stored settings instead of message data. Intentional per #2103 but creates race condition.
- **Impact**: UI shows one set of settings while playback may use another.

#### F1-08: _send_pcm_chunk stereo framing oversized
- **Severity**: MEDIUM
- **Boundary**: Backend internal (audio_stream_controller)
- **Location**: `audio_stream_controller.py:887-888`
- **Status**: NEW → **#2257**
- **Description**: `len(pcm_samples)` on 2D array returns frames not elements. Stereo frames are 2x target (~800KB vs 400KB).
- **Impact**: Approaches 1MB WebSocket frame limit for stereo audio.

#### F1-09: Both streaming hooks fetch full library on every play
- **Severity**: LOW
- **Boundary**: Frontend → Backend (REST)
- **Location**: `usePlayNormal.ts:421-434` + `usePlayEnhanced.ts:500-513`
- **Status**: NEW → **#2258**
- **Description**: `GET /api/library/tracks` fetches all tracks, then `.find()` by ID. Only returns first 50.
- **Impact**: Track beyond position 50 won't display metadata in player bar.

#### F1-10: Seek does not offset displayed time
- **Severity**: LOW
- **Boundary**: Frontend internal (streaming → time display)
- **Location**: `usePlayEnhanced.ts:239`
- **Status**: NEW → **#2259**
- **Description**: `seek_position` read but never used to offset `samplesPlayed`.
- **Impact**: Progress bar shows 0:00 after seeking to 2:00.

---

### Flow 2: Library Browsing

#### F2-01: Track artists/genres array vs singular mismatch in transformer
- **Severity**: HIGH
- **Boundary**: Engine model → Frontend transformer
- **Location**: `core.py:113-143` → `types.ts:59-85` → `trackTransformer.ts:24`
- **Status**: NEW → **#2263**
- **Description**: Backend returns `artists: list[str]` and `genres: list[str]`. Frontend `TrackApiResponse` expects `artist: string` and `genre?: string`. Transformer maps non-existent singular field → `undefined`.
- **Impact**: Artist and genre fields are `undefined` for all tracks via transformation layer.

#### F2-02: DEFAULT_TRACK_FIELDS missing critical metadata fields
- **Severity**: HIGH
- **Boundary**: Backend serializer → Frontend transformer
- **Location**: `serializers.py:18-24` → `types.ts:62`
- **Status**: NEW → **#2267**
- **Description**: Fallback serializer only includes `id, title, filepath, duration, format`. Missing `artist, album, artwork_url, genres, year`.
- **Impact**: If `to_dict()` fails, serialized tracks lack all metadata.

#### F2-03: Playlist WebSocket broadcast types not in frontend type union
- **Severity**: HIGH
- **Boundary**: Backend playlists router → Frontend WebSocket types
- **Location**: `playlists.py:279-285,320-325,357-361` → `websocket.ts:12-43`
- **Status**: NEW → **#2264**
- **Description**: Backend sends `playlist_tracks_added`, `playlist_track_removed`, `playlist_cleared`. Frontend only defines `playlist_created/updated/deleted`.
- **Impact**: No real-time playlist updates. View shows stale data.

#### F2-04: addTrackToPlaylist sends wrong body format
- **Severity**: HIGH
- **Boundary**: Frontend service → Backend router
- **Location**: `playlistService.ts:115` → `playlists.py:47-49`
- **Status**: NEW → **#2265**
- **Description**: Sends `{track_id}` (singular) but backend expects `{track_ids: [...]}` (plural list). Pydantic defaults to empty list.
- **Impact**: Adding tracks to playlists silently fails with "No tracks were added".

#### F2-05: Playlist updated_at vs modified_at mismatch
- **Severity**: MEDIUM
- **Boundary**: Engine model → Frontend types
- **Location**: `core.py:316` → `domain.ts:95`
- **Status**: NEW → **#2269**
- **Description**: Backend returns `updated_at`, frontend expects `modified_at`.
- **Impact**: "Last modified" display always empty.

#### F2-06: Album artwork_path leaks filesystem path in serializer fallback
- **Severity**: MEDIUM
- **Boundary**: Backend router → Frontend transformer
- **Location**: `albums.py:110` → `serializers.py:30`
- **Status**: NEW → **#2270**
- **Description**: `to_dict()` correctly converts to API URL, but `getattr` fallback returns raw filesystem path.
- **Impact**: Internal paths leak to frontend; images fail to load.

#### F2-07: domain.ts LibraryStats completely disconnected from backend
- **Severity**: MEDIUM
- **Boundary**: Backend repository → Frontend types
- **Location**: `stats_repository.py:29-78` → `domain.ts:234-242`
- **Status**: NEW → **#2272**
- **Description**: `domain.ts` expects `total_size_mb, average_bitrate, supported_formats, total_duration_seconds` — none exist in backend. Two competing `LibraryStats` interfaces.
- **Impact**: Components importing from `domain.ts` get `undefined` for all fields.

#### F2-08: useLibraryQuery hits unpaginated /api/library/albums
- **Severity**: MEDIUM
- **Boundary**: Frontend hook → Backend router
- **Location**: `useLibraryQuery.ts:183` → `library.py:389`
- **Status**: NEW → **#2273**
- **Description**: Frontend sends `limit=50&offset=0` but backend ignores params, returns all albums.
- **Impact**: `hasMore` logic broken. All albums loaded regardless of pagination.

#### F2-09: Playlist created_at can be null but frontend requires string
- **Severity**: LOW
- **Boundary**: Engine model → Frontend types
- **Location**: `core.py:315` → `domain.ts:94`
- **Status**: NEW → **#2278**
- **Description**: Backend returns `None` for null `created_at`, frontend type expects required `string`.
- **Impact**: Minor — null playlists fail type guard.

---

### Flow 3: Audio Enhancement

#### F3-01: useLibraryWithStats sends singular directory field breaking scan
- **Severity**: CRITICAL
- **Boundary**: Frontend hook → Backend router
- **Location**: `useLibraryWithStats.ts:392` → `schemas.py:665`
- **Status**: NEW → **#2262**
- **Description**: Sends `{directory: folderPath}` while `ScanRequest` requires `{directories: [folderPath]}`. The "recommended" hook is broken; only the legacy `useLibraryData` works.
- **Impact**: Scanning broken for any component using `useLibraryWithStats` → 422.

#### F3-02: PlayEnhancedData allows intensity 2.0 vs 1.0 everywhere else
- **Severity**: MEDIUM
- **Boundary**: Backend schema → Backend router → Frontend types
- **Location**: `schemas.py:628` → `enhancement.py:262` → `domain.ts:141`
- **Status**: NEW → **#2271**
- **Description**: Schema allows `le=2.0`, REST validates `0.0-1.0`, frontend clamps to `0.0-1.0`. WebSocket path may not clamp.
- **Impact**: Possible over-processing causing audio clipping via WS.

#### F3-03: Shared Redux streaming state causes collision in A/B mode
- **Severity**: HIGH
- **Boundary**: Frontend hooks → Redux store
- **Location**: `usePlayEnhanced.ts:309-315` + `usePlayNormal.ts:259-265` → `playerSlice.ts:32-41`
- **Status**: NEW → **#2266**
- **Description**: Both hooks dispatch to the same `streaming` state. Both mounted simultaneously for A/B comparison. One overwrites the other.
- **Impact**: A/B comparison mode shows incorrect progress/state.

#### F3-04: usePlayNormal not exported from enhancement index
- **Severity**: LOW
- **Boundary**: Frontend module structure
- **Location**: `hooks/enhancement/index.ts:15-16`
- **Status**: NEW → **#2277**
- **Description**: `usePlayEnhanced` exported but `usePlayNormal` is not.
- **Impact**: Minor DX — requires direct file import path.

---

### Flow 4: Library Scanning

*(All scanning-related findings are captured in F3-01 above and prior INT-04/INT-17)*

---

### Flow 5: WebSocket Lifecycle

#### F5-01: usePlayNormal buffer threshold ignores channel count
- **Severity**: HIGH
- **Boundary**: Backend audio_stream_controller → Frontend usePlayNormal
- **Location**: `usePlayNormal.ts:289,345`
- **Status**: NEW → **#2268**
- **Description**: Threshold `bufferedSamples >= sampleRate` ignores channels. `usePlayEnhanced` correctly uses `sampleRate * channels * 2`. Stereo gets 0.5s buffer instead of 1.0s.
- **Impact**: Stereo audio stutters and underruns in normal playback.

#### F5-02: PlayerStateData mixes camelCase and snake_case
- **Severity**: MEDIUM
- **Boundary**: Backend WebSocket → Frontend types
- **Location**: `websocket.ts:67-78`
- **Status**: NEW → **#2276**
- **Description**: `currentTrack`, `isPlaying` (camelCase) alongside `gapless_enabled`, `crossfade_enabled` (snake_case) in same interface.
- **Impact**: Consumers must handle mixed conventions; wrong convention → `undefined`.

#### F5-03: WebSocketProtocolClient correlation_id stripped by backend
- **Severity**: MEDIUM
- **Boundary**: Frontend protocolClient → Backend websocket_security
- **Location**: `protocolClient.ts:173-183` → `websocket_security.py:150-153`
- **Status**: NEW → **#2281**
- **Description**: Pydantic V2 strips `correlation_id` during `model_validate`. Response correlation impossible.
- **Impact**: All `responseRequired: true` messages time out.

#### F5-04: fingerprint_progress and seek_started missing from canonical types
- **Severity**: LOW
- **Boundary**: Backend → Frontend types
- **Location**: `audio_stream_controller.py:1020-1028` + `system.py:428-434` → `websocket.ts:12-43`
- **Status**: NEW → **#2282**
- **Description**: Backend sends these types but they're not in `WebSocketMessageType` union. `seek_started` has no frontend handler at all.
- **Impact**: `seek_started` acknowledgment silently dropped.

#### F5-05: Seek ignores frontend-sent preset/intensity
- **Severity**: LOW
- **Boundary**: Frontend usePlayEnhanced → Backend system.py
- **Location**: `usePlayEnhanced.ts:647-656` → `system.py:394-412`
- **Status**: NEW (related to F1-07) → covered by **#2256**
- **Description**: Backend always uses stored settings for seek, same pattern as play_enhanced.
- **Impact**: Post-seek audio may use different enhancement settings.

---

### Flow 6: Fingerprint & Similarity

#### F6-01: Track fingerprint endpoint references non-existent model attributes
- **Severity**: CRITICAL
- **Boundary**: Backend library router → Engine TrackFingerprint model
- **Location**: `library.py:641-671` → `fingerprint.py:39-76`
- **Status**: NEW → **#2260**
- **Description**: Endpoint references `fp.sub_bass`, `fp.percussive_ratio`, `fp.pitch_confidence`, etc. Model has `sub_bass_pct`, `harmonic_ratio`, `pitch_stability`. 6 attributes don't exist at all.
- **Impact**: Every call raises `AttributeError`. Fingerprint display completely broken.

#### F6-02: Album fingerprint endpoint silently returns all-zero values
- **Severity**: CRITICAL
- **Boundary**: Backend albums router → Engine TrackFingerprint model
- **Location**: `albums.py:258-266` → `fingerprint.py:39-76`
- **Status**: NEW → **#2261**
- **Description**: Uses `getattr(fp, dim, 0.0)` with wrong dimension names. `getattr` returns `0.0` default for all.
- **Impact**: Album Character Pane shows flat, meaningless all-zero gradients.

#### F6-03: Similarity endpoint defaults mismatched
- **Severity**: MEDIUM
- **Boundary**: Frontend useSimilarTracks → Backend similarity router
- **Location**: `useSimilarTracks.ts:117` → `similarity.py:86`
- **Status**: NEW → **#2274**
- **Description**: Frontend defaults `includeDetails=true`, backend defaults `include_details=False`.
- **Impact**: Direct API calls without explicit param get results missing metadata.

#### F6-04: Dual AudioFingerprint types with incompatible schemas
- **Severity**: MEDIUM
- **Boundary**: Frontend `types/domain.ts` ↔ `utils/fingerprintToGradient.ts`
- **Location**: `domain.ts:206-226` ↔ `fingerprintToGradient.ts:14-44`
- **Status**: NEW → **#2280**
- **Description**: Two interfaces named `AudioFingerprint` with completely different fields. `domain.ts` has legacy spectral fields; gradient utility has 25D fields.
- **Impact**: Passing one type where the other is expected → undefined fields, incorrect visualizations.

---

### Flow 7: Artwork

#### F7-01: Artwork WebSocket broadcast types not handled by frontend
- **Severity**: MEDIUM
- **Boundary**: Backend artwork router → Frontend WebSocket
- **Location**: `artwork.py:122-128,164-167,229-238` → `websocket.ts:12-43`
- **Status**: NEW → **#2279**
- **Description**: Backend sends `artwork_extracted`, `artwork_downloaded`, `artwork_deleted`. Frontend only defines `artwork_updated`.
- **Impact**: Artwork changes never trigger frontend refresh. Stale display.

#### F7-02: usePlayerStateSync coverUrl vs artworkUrl in state mapping
- **Severity**: MEDIUM
- **Boundary**: Backend WebSocket → Frontend state sync
- **Location**: `usePlayerStateSync.ts:70,119`
- **Status**: NEW → **#2275**
- **Description**: Same root cause as F1-01 (#2250) but specifically in the playback state synchronization path.
- **Impact**: Artwork not propagated to player state correctly.

---

## Relationships & Clusters

### Cluster 1: Schema Naming Chaos (12 findings)
Root cause: No shared type system between Python/TypeScript. Each layer defines its own types independently.
- **Field naming**: `coverUrl`/`artworkUrl`/`artwork_url`/`album_art`/`artwork_path` (#2250, #2275, #2270)
- **Plural vs singular**: `artists`/`artist`, `genres`/`genre`, `directories`/`directory`, `track_ids`/`track_id` (#2263, #2262, #2265)
- **Case conventions**: camelCase/snake_case mixed (#2276)
- **Timestamp naming**: `updated_at` vs `modified_at` (#2269)
- **Competing interfaces**: `LibraryStats` (#2272), `AudioFingerprint` (#2280), `Track` (#2222)

### Cluster 2: Fingerprint Pipeline Broken (3 findings)
Root cause: Model columns renamed with `_pct` suffix but endpoint code not updated.
- #2260 → Track fingerprint crashes (AttributeError)
- #2261 → Album fingerprint returns zeros (getattr fallback)
- #2280 → Frontend has two incompatible `AudioFingerprint` types

### Cluster 3: WebSocket Message Type Drift (4 findings)
Root cause: Backend adds new message types without updating frontend's canonical union.
- #2264 → Playlist WS types not in frontend union
- #2279 → Artwork WS types not in frontend union
- #2282 → `fingerprint_progress`, `seek_started` missing
- #2281 → ProtocolClient correlation_id stripped

### Cluster 4: Playback Control Disconnect (4 findings)
Root cause: Migration from REST to WebSocket-based control is incomplete.
- #2252 → Pause/stop doesn't stop AudioPlaybackEngine
- #2254 → REST endpoints removed but hooks still call them
- #2253 → Legacy seek sends body instead of query param
- #2266 → Shared Redux streaming state collision

### Cluster 5: Unpaginated Endpoints (3 findings)
Root cause: `/api/library/*` endpoints lack pagination while `/api/*` have it.
- #2258 → Full library fetch on every play
- #2273 → useLibraryQuery sends pagination params that are ignored
- #2119 → Dual endpoint problem (existing)

---

## Prioritized Fix Order

### Phase 1: Critical Blockers (fix immediately)
1. **#2260 + #2261** — Fingerprint attribute names. Straightforward rename. Unblocks Album Character Pane and track fingerprint display.
2. **#2262** — Scan directory field. One-line fix (`directory` → `directories: [folderPath]`). Unblocks scanning via recommended hook.
3. **#2250 + #2275** — `coverUrl` → `artworkUrl` rename. Two-line fix each. Restores all artwork display.

### Phase 2: High-Impact Functional Fixes (fix before release)
4. **#2252** — Pause/stop must stop AudioPlaybackEngine. Requires shared engine ref or Redux action.
5. **#2265** — `track_id` → `track_ids: [trackId]`. One-line fix. Unblocks playlist add.
6. **#2264** — Align playlist WS broadcast types with frontend union.
7. **#2266** — Split Redux streaming state for enhanced/normal. Enables A/B mode.
8. **#2268** — Buffer threshold must include channel count. One-line fix.
9. **#2254** — Remove or migrate dead REST endpoint calls.
10. **#2263 + #2267** — Fix transformer for plural fields and extend DEFAULT_TRACK_FIELDS.

### Phase 3: Medium-Impact Improvements (fix within 2 sprints)
11. **#2271** — Change `schemas.py:628` from `le=2.0` to `le=1.0`.
12. **#2279** — Handle artwork broadcast types in frontend.
13. **#2281** — Fix or remove correlation_id pattern.
14. **#2276** — Complete camelCase mapping in PlayerStateData.
15. **#2280** — Consolidate dual AudioFingerprint types.
16. **#2272** — Align domain.ts LibraryStats with backend.
17. **#2273** — Add pagination to /api/library/albums or redirect to /api/albums.
18. **#2269, #2270, #2274** — Fix timestamp naming, artwork path leak, similarity defaults.

### Phase 4: Low-Priority Cleanup
19. **#2251, #2255, #2256, #2257** — Volume scale, intensity hardcode, enhancement settings, stereo framing.
20. **#2258, #2259, #2277, #2278, #2282** — Library fetch, seek offset, exports, nullable types, missing WS types.

---

## Cross-Cutting Recommendations

### 1. Shared Schema Layer
The root cause of 12+ findings is the lack of a shared type system. Recommend:
- Generate TypeScript types from backend Pydantic models (e.g., `pydantic-to-typescript` or OpenAPI codegen)
- Establish a single canonical `Track`, `Album`, `Playlist`, `AudioFingerprint` type in `types/domain.ts`
- Remove all local type redefinitions in hooks

### 2. WebSocket Message Registry
Backend sends 25+ message types, but the frontend union only covers 18. Recommend:
- Single-source registry of all WS message types in both backend and frontend
- CI check that all backend broadcast types exist in frontend union
- Typed message factories on both sides

### 3. Serialization Boundary
Multiple serialization paths (`to_dict()`, `serialize_object()`, inline) produce inconsistent output. Recommend:
- Standardize on `to_dict()` everywhere, with mandatory test coverage
- Remove `DEFAULT_*_FIELDS` fallback pattern (it masks bugs)
- Add integration tests that verify serialized output matches frontend types

### 4. Playback Control Architecture
The REST-to-WebSocket migration left orphaned code paths. Recommend:
- Complete the migration: remove all REST control endpoints and hooks
- Establish a shared `PlaybackEngineRef` context for pause/stop/seek
- Split Redux streaming state into `streaming.enhanced` and `streaming.normal`

### 5. Integration Test Suite
Add automated tests for each of the 7 traced flows:
- Mock WebSocket messages with real backend payload shapes
- Verify frontend type guards accept actual backend data
- Verify all WS message types are handled

---

## Complete Issue Index

| # | Finding | Severity | Flow | Issue |
|---|---------|----------|------|-------|
| 1 | artworkUrl field name regression | CRITICAL | Playback | **#2250** |
| 2 | Fingerprint endpoint AttributeError | CRITICAL | Fingerprint | **#2260** |
| 3 | Album fingerprint returns all-zeros | CRITICAL | Fingerprint | **#2261** |
| 4 | Scan directory field mismatch | CRITICAL | Scanning | **#2262** |
| 5 | Pause/stop doesn't stop AudioPlaybackEngine | HIGH | Playback | **#2252** |
| 6 | usePlayerAPI.seek sends body not query param | HIGH | Playback | **#2253** |
| 7 | REST endpoints removed, hooks still call them | HIGH | Playback | **#2254** |
| 8 | Track artists/genres array vs singular | HIGH | Library | **#2263** |
| 9 | Playlist WS broadcast types mismatch | HIGH | Library | **#2264** |
| 10 | addTrackToPlaylist body format wrong | HIGH | Library | **#2265** |
| 11 | Shared Redux streaming state collision | HIGH | Enhancement | **#2266** |
| 12 | DEFAULT_TRACK_FIELDS missing fields | HIGH | Library | **#2267** |
| 13 | usePlayNormal buffer threshold stereo | HIGH | WebSocket | **#2268** |
| 14 | Volume scale inconsistency (3 layers) | MEDIUM | Playback | **#2251** |
| 15 | startStreaming hardcodes intensity 1.0 | MEDIUM | Playback | **#2255** |
| 16 | Backend ignores frontend settings | MEDIUM | Playback | **#2256** |
| 17 | _send_pcm_chunk stereo framing oversized | MEDIUM | Playback | **#2257** |
| 18 | Playlist updated_at vs modified_at | MEDIUM | Library | **#2269** |
| 19 | Album artwork_path leaks filesystem path | MEDIUM | Library | **#2270** |
| 20 | PlayEnhancedData allows intensity 2.0 | MEDIUM | Enhancement | **#2271** |
| 21 | domain.ts LibraryStats disconnected | MEDIUM | Library | **#2272** |
| 22 | useLibraryQuery hits unpaginated endpoint | MEDIUM | Library | **#2273** |
| 23 | Similarity defaults mismatched | MEDIUM | Fingerprint | **#2274** |
| 24 | usePlayerStateSync coverUrl mapping | MEDIUM | Artwork | **#2275** |
| 25 | PlaybackState mixes camelCase/snake_case | MEDIUM | WebSocket | **#2276** |
| 26 | Artwork WS broadcast types unhandled | MEDIUM | Artwork | **#2279** |
| 27 | Dual AudioFingerprint types | MEDIUM | Fingerprint | **#2280** |
| 28 | ProtocolClient correlation_id stripped | MEDIUM | WebSocket | **#2281** |
| 29 | Full library fetch on every play | LOW | Playback | **#2258** |
| 30 | Seek doesn't offset time display | LOW | Playback | **#2259** |
| 31 | usePlayNormal not exported | LOW | Enhancement | **#2277** |
| 32 | Playlist created_at nullable | LOW | Library | **#2278** |
| 33 | Missing WS types (seek_started, etc.) | LOW | WebSocket | **#2282** |
