# Backend-Frontend-Engine Integration Audit — 2026-03-20

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: 7 cross-layer data flows — Track Playback, Library Browsing, Audio Enhancement, Library Scanning, WebSocket Lifecycle, Fingerprint & Similarity, Artwork
**Method**: 7 parallel flow agents (Sonnet), followed by manual merge, deduplication, and cross-flow analysis.

## Executive Summary

This audit traces data across all three layers (React frontend, FastAPI backend, Python audio engine) through 7 critical flows. Found **10 HIGH**, **21 MEDIUM**, and **14 LOW** findings — a significant increase over the prior audit (March 5: 1 MEDIUM, 1 LOW), reflecting deeper analysis into serialization, type contracts, and WebSocket protocol coverage.

**Most impactful clusters:**

1. **Serialization gaps** (Flow 2) — `Album.to_dict()` omits `total_duration`, `Track.to_dict()` omits `bitrate`, and the artist detail endpoint returns `artist_id`/`artist_name` while the frontend type expects `id`/`name`. The serializer fallback path drops 4 critical track fields.

2. **Enhancement dual control** (Flow 3) — Two independent frontend subsystems (`EnhancementContext` and `useEnhancementControl`) each maintain their own state and make independent REST calls. Worse, `EnhancementContext` sends query params while the backend expects JSON body — all its calls silently fail with 422.

3. **Dual WebSocket connections** (Flow 5) — `WebSocketContext` and `WebSocketProtocolClient` are two independent singletons opening separate connections to the same endpoint. Every broadcast is received twice.

4. **Fingerprint field name mismatch** (Flow 6) — Backend renames 3 fingerprint dimensions (`pitch_stability` → `pitch_confidence`, etc.) in the API response, but the frontend type uses the original names. Gradient rendering receives `undefined` for 3 of 25 dimensions.

5. **Artwork cache invalidation** (Flow 7) — 1-year `Cache-Control` headers with no cache-busting token means artwork updates are invisible to the browser.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 10 |
| MEDIUM | 21 |
| LOW | 14 |
| **Total** | **45** |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| INT-11: Manual scan missing library_scan_started | #2711 | STILL OPEN |
| INT-12: Album serializer artwork_path vs artwork_url | #2627 related | STILL OPEN |
| #2625: Enhancement intensity silent clamping | #2625 | STILL OPEN |
| #2633: EnhancementContext isProcessing races | #2633 | STILL OPEN |

---

## New Findings

### HIGH

---

### INT-13: AudioWorklet hardcodes stereo channel count for all tracks
- **Severity**: HIGH
- **Flow**: Track Playback
- **Boundary**: Backend PCM encoder → Frontend AudioWorklet
- **Location**: `audio-worklet-processor.js:60` → `AudioPlaybackEngine.ts:381`
- **Status**: NEW
- **Description**: The worklet unconditionally computes `samplesNeeded = framesNeeded * 2` and the feed loop uses `feedChunkSize = bufferSize * 2`. Backend correctly sends `channels=1` in `audio_stream_start` for mono files and transmits single-channel PCM. The worklet consumes samples at twice the correct rate.
- **Impact**: Mono files play at half speed, one octave too low, with rapid buffer underruns.
- **Suggested Fix**: Propagate `channels` from `PCMStreamBuffer.getMetadata()` to worklet via port message.

---

### INT-14: `Album.to_dict()` omits `total_duration` — breaks album list transformer
- **Severity**: HIGH
- **Flow**: Library Browsing
- **Boundary**: Backend model → Frontend transformer
- **Location**: `auralis/library/models/core.py:190` → `albumTransformer.ts:32`
- **Status**: NEW
- **Description**: `Album.to_dict()` does not include `total_duration`. The serializer adds it post-hoc, but `serialize_object()` calls `to_dict()` first and returns directly. Frontend `AlbumApiResponse` declares `total_duration: number` as non-optional with no null guard.
- **Impact**: `album.totalDuration` is `undefined` throughout all album views. Running time shows nothing or NaN.
- **Suggested Fix**: Add `total_duration` to `Album.to_dict()`.

---

### INT-15: `ArtistDetailApiResponse` shape mismatch — `artist_id`/`artist_name` vs `id`/`name`
- **Severity**: HIGH
- **Flow**: Library Browsing
- **Boundary**: Backend router → Frontend type
- **Location**: `routers/artists.py:188` → `types.ts:133`
- **Status**: NEW
- **Description**: Backend returns `artist_id`/`artist_name` but frontend type `extends ArtistApiResponse` which has `id`/`name`. `useArtistDetailsData` works around it manually.
- **Impact**: Type system provides false safety. Any code trusting the type receives `undefined` for identity fields.
- **Suggested Fix**: Define `ArtistDetailApiResponse` independently to match actual backend shape.

---

### INT-16: `Album.to_dict()` returns `artist_id` (int FK) but frontend `Album` domain model has no `artistId`
- **Severity**: HIGH
- **Flow**: Library Browsing
- **Boundary**: Backend model → Frontend domain type
- **Location**: `core.py:205` → `domain.ts:58-74`
- **Status**: NEW
- **Description**: The integer FK `artist_id` is present in the API response but dropped by the transformer because the domain `Album` type has no `artistId` field.
- **Impact**: Album-to-artist navigation impossible from list views without separate API call.
- **Suggested Fix**: Add `artistId` to `Album` domain type and `transformAlbum()`.

---

### INT-17: EnhancementContext sends query params; backend expects JSON body — all calls silently fail
- **Severity**: HIGH
- **Flow**: Audio Enhancement
- **Boundary**: EnhancementContext → enhancement.py router
- **Location**: `config/api.ts:66-68` → `routers/enhancement.py:44-59`
- **Status**: NEW
- **Description**: `ENDPOINTS.ENHANCEMENT_TOGGLE(enabled)` builds URLs like `?enabled=true` and calls `post(url)` with no body. Backend handlers use Pydantic body models — FastAPI returns 422. Error silently swallowed.
- **Impact**: All enhancement calls from `EnhancementContext` (used by `EnhancementPane`, `EnhancementSettingsPanel`) silently fail. State never reaches backend.
- **Suggested Fix**: Pass payload as JSON body, fix ENDPOINTS to not encode as query params.

---

### INT-18: Dual enhancement control paths create state divergence
- **Severity**: HIGH
- **Flow**: Audio Enhancement
- **Boundary**: EnhancementContext ↔ useEnhancementControl
- **Location**: `EnhancementContext.tsx` ↔ `useEnhancementControl.ts`
- **Status**: NEW
- **Description**: Two independent subsystems own and mutate enhancement state — both subscribe to `enhancement_settings_changed` WS broadcast but maintain separate local React state and make independent REST calls. During round-trip window, they show different values.
- **Impact**: UI flickers between different enhancement states when both components are rendered.
- **Suggested Fix**: Consolidate into single state authority. Delete `EnhancementContext`, migrate consumers to `useEnhancementControl`.

---

### INT-19: Dual WebSocket connections — two singletons, one endpoint
- **Severity**: HIGH
- **Flow**: WebSocket Lifecycle
- **Boundary**: Frontend → Backend WebSocket
- **Location**: `WebSocketContext.tsx:209` + `protocolClient.ts:354`
- **Status**: NEW
- **Description**: `WebSocketManager` and `WebSocketProtocolClient` are independent singletons that both connect to `ws://localhost:8765/ws`. Any hook using `useWebSocketProtocol({ autoConnect: true })` opens a second connection. Backend broadcasts all messages to both connections.
- **Impact**: Every broadcast received twice. Side-effect handlers fire twice per broadcast. Doubles server-side connection tracking.
- **Suggested Fix**: Eliminate `WebSocketProtocolClient` as separate connection. Delegate to `WebSocketManager` singleton.

---

### INT-20: AudioFingerprint interface field name mismatch between API and frontend type
- **Severity**: HIGH
- **Flow**: Fingerprint & Similarity
- **Boundary**: Backend fingerprint endpoint → Frontend type
- **Location**: `routers/library.py:689-697` → `fingerprintToGradient.ts:36-41`
- **Status**: NEW
- **Description**: Backend renames 3 dimensions: `pitch_stability` → `pitch_confidence`, `chroma_energy` → `chroma_energy_mean`, `phase_correlation` → `stereo_correlation`. Frontend `AudioFingerprint` uses the original names.
- **Impact**: Gradient rendering receives `undefined` for 3 of 25 dimensions. Fingerprint visualization is incomplete.
- **Suggested Fix**: Either remove the rename in the backend endpoints or update the frontend type to match.

---

### INT-21: 1-year Cache-Control on artwork with no cache-busting token
- **Severity**: HIGH
- **Flow**: Artwork
- **Boundary**: Backend artwork endpoint → Browser cache
- **Location**: `routers/artwork.py` → Frontend `<img>` elements
- **Status**: NEW
- **Description**: `Cache-Control: public, max-age=31536000` on artwork endpoint. After extract/download, the WS `artwork_updated` message provides the same URL (no cache-busting query param). Browsers serve the old image.
- **Impact**: Updated artwork invisible to users until manual cache clear.
- **Suggested Fix**: Append `?v={hash}` or `?t={timestamp}` to artwork URLs on update.

---

### INT-22: `artwork_updated` WebSocket message never subscribed by any frontend code
- **Severity**: HIGH
- **Flow**: Artwork
- **Boundary**: Backend broadcast → Frontend
- **Location**: `routers/artwork.py` → (no subscriber)
- **Status**: NEW
- **Description**: The type and guard exist in `types/websocket.ts` but zero production code subscribes to `artwork_updated`. Album/track UI does not refresh after artwork operations.
- **Impact**: After extract/download/delete artwork, UI shows stale image until manual refresh.
- **Suggested Fix**: Add `useWebSocketSubscription(['artwork_updated'])` in album/artwork components to trigger re-fetch.

---

### MEDIUM

---

### INT-23: Blob binary frame race drops PCM frames on Safari
- **Severity**: MEDIUM
- **Flow**: Track Playback
- **Boundary**: WebSocket binary frame → PCM decoder
- **Location**: `WebSocketContext.tsx:285-287`
- **Status**: NEW
- **Description**: `pendingAudioChunkMeta` cleared inside async `.then()` of `Blob.arrayBuffer()`. Multiple in-flight Blob conversions can clear metadata for newer frames.
- **Impact**: Dropped audio frames during streaming on Safari (which uses Blob-based binary frames).
- **Suggested Fix**: Clear `pendingAudioChunkMeta = null` synchronously before launching `arrayBuffer()`.

---

### INT-24: `usePlayNormal` missing disconnect recovery — stale/dual engine
- **Severity**: MEDIUM
- **Flow**: Track Playback
- **Boundary**: Frontend WebSocket → AudioPlaybackEngine
- **Location**: `usePlayNormal.ts` (missing) vs `usePlayEnhanced.ts` (has disconnect watcher)
- **Status**: NEW
- **Description**: `usePlayEnhanced` has `wsContext.isConnected` watcher that stops engine on disconnect. `usePlayNormal` has no equivalent. On reconnect, old engine keeps running concurrently.
- **Impact**: Dual audio engines playing simultaneously after WS reconnect.
- **Suggested Fix**: Add same disconnect-recovery `useEffect` as `usePlayEnhanced`.

---

### INT-25: Serializer fallback drops `album_id`, `track_number`, `disc_number`, `favorite`
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Boundary**: Backend serializer → Frontend transformer
- **Location**: `serializers.py:18-36` → `types.ts:58-88`
- **Status**: NEW
- **Description**: `DEFAULT_TRACK_FIELDS` lacks these 4 fields. When `to_dict()` fails, fallback path drops them.
- **Impact**: Album navigation and favorite state broken for affected tracks.

---

### INT-26: `fetchMore()` offset overshoots on last page
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Location**: `useLibraryQuery.ts:293-313`
- **Status**: NEW
- **Description**: Sets offset from `limit` not from `response.offset`. Triggers redundant empty API call on last page.

---

### INT-27: Artist list response not transformed — snake_case fields reach camelCase consumers
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Location**: `useLibraryQuery.ts:187`
- **Status**: NEW
- **Description**: `artists` branch of `extractItemsFromResponse()` returns raw objects. `artist.trackCount` and `artist.albumCount` are always `undefined`.

---

### INT-28: `/api/library/artists` ignores `search` parameter — wrong endpoint for artist search
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Location**: `useLibraryQuery.ts:119` → `routers/library.py:332-390`
- **Status**: NEW
- **Description**: Library router has no `search` param. FastAPI silently ignores it. Artist search returns all artists unfiltered.

---

### INT-29: `DEFAULT_PLAYLIST_FIELDS` lacks `is_smart`
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Location**: `serializers.py:59-65`
- **Status**: NEW
- **Description**: Fallback serialization path drops smart playlist flag. Smart playlists appear as regular.

---

### INT-30: `AudioStreamEndMessage` type missing `total_samples`, `duration`, `stream_type`
- **Severity**: MEDIUM
- **Flow**: Audio Enhancement
- **Boundary**: Backend → Frontend type
- **Location**: `audio_stream_controller.py:1340-1348` → `types/websocket.ts:412-418`
- **Status**: NEW
- **Description**: Backend sends 3 fields not in the frontend type. `stream_type` filter works at runtime but is accessing an undeclared field.

---

### INT-31: `audio_stream_error` payload `code` and `stream_type` not in frontend type
- **Severity**: MEDIUM
- **Flow**: Audio Enhancement
- **Location**: `routers/system.py:286-295` → `types/websocket.ts`
- **Status**: NEW
- **Description**: `ENHANCEMENT_DISABLED` error code discarded. Frontend cannot distinguish it from DSP failure.

---

### INT-32: Seek handler overrides frontend-sent preset with stored global
- **Severity**: MEDIUM
- **Flow**: Audio Enhancement
- **Location**: `usePlayEnhanced.ts:684-713` → `routers/system.py:563-568`
- **Status**: NEW
- **Description**: If user changed preset mid-stream, seek restarts at new preset — unexpected quality jump.

---

### INT-33: Enhancement toggle during active streaming doesn't stop in-flight chunks
- **Severity**: MEDIUM
- **Flow**: Audio Enhancement
- **Location**: `routers/enhancement.py:152-212` → `audio_stream_controller.py:580-698`
- **Status**: NEW
- **Description**: `toggle_enhancement(enabled=false)` updates the global dict but the streaming loop never checks it. Enhanced audio continues while UI shows "disabled".

---

### INT-34: `scan_complete` — `filesRemoved` bleeds from previous scan
- **Severity**: MEDIUM
- **Flow**: Library Scanning
- **Location**: Manual scan endpoint → `useScanProgress`
- **Status**: NEW
- **Description**: Manual scan never calls `cleanup_missing_files`. Frontend copies stale `filesRemoved` from previous scan result.

---

### INT-35: `library_scan_error` not in frontend type system — `isScanning` stuck
- **Severity**: MEDIUM
- **Flow**: Library Scanning
- **Location**: `LibraryAutoScanner._do_scan()` → `useScanProgress`
- **Status**: NEW
- **Description**: Type absent from `WebSocketMessageType`. When auto-scan errors, `isScanning` stays `true` permanently.

---

### INT-36: Rejected scan (concurrency guard) indistinguishable from empty scan
- **Severity**: MEDIUM
- **Flow**: Library Scanning
- **Location**: `scanner.py` → frontend
- **Status**: NEW
- **Description**: `ScanResult(rejected=True)` not checked — broadcasts `scan_complete` with all-zeros. No 409 returned.

---

### INT-37: Library views don't refresh after auto-scan
- **Severity**: MEDIUM
- **Flow**: Library Scanning
- **Location**: `LibraryAutoScanner` → frontend
- **Status**: NEW
- **Description**: `library_updated` message is defined but never broadcast by either scan path. Views remain stale after tracks are added.

---

### INT-38: `playback_resumed` backend message has no frontend consumer
- **Severity**: MEDIUM
- **Flow**: WebSocket Lifecycle
- **Location**: `system.py:492` → (no subscriber)
- **Status**: NEW
- **Description**: String `'playback_resumed'` absent from `WebSocketMessageType` union. Resume acknowledgments silently dropped.

---

### INT-39: `seek_started` typed but never subscribed
- **Severity**: MEDIUM
- **Flow**: WebSocket Lifecycle
- **Location**: `system.py:590` → (no subscriber)
- **Status**: NEW
- **Description**: If follow-up `audio_stream_start` is lost, `isSeeking` state never cleared.

---

### INT-40: Security error format (`"type": "error"`) incompatible with frontend type union
- **Severity**: MEDIUM
- **Flow**: WebSocket Lifecycle
- **Location**: `websocket_security.py` → frontend
- **Status**: NEW
- **Description**: Rate-limit and schema-validation rejections use `{"type": "error"}` — not in `WebSocketMessageType`. Silently dropped.

---

### INT-41: Binary frame endianness assumed, not enforced
- **Severity**: MEDIUM
- **Flow**: WebSocket Lifecycle
- **Location**: `audio_stream_controller.py:1260` → `pcmDecoding.ts`
- **Status**: NEW
- **Description**: `numpy.tobytes()` uses native endianness. Frontend `Float32Array(buffer)` assumes matching. The legacy base64 path uses explicit `getFloat32(i*4, true)`.
- **Suggested Fix**: Use `frame_samples.astype('<f4').tobytes()` to make contract explicit.

---

### INT-42: Backend single-task-slot cancels A/B streams silently
- **Severity**: MEDIUM
- **Flow**: WebSocket Lifecycle
- **Location**: `audio_stream_controller.py`
- **Status**: NEW
- **Description**: `play_normal` cancels any in-flight `play_enhanced` task and vice versa. `CancelledError` path does not send `audio_stream_error`, leaving Redux state stuck in `buffering`/`streaming`.

---

### INT-43: Missing fingerprint returns different HTTP codes across endpoints
- **Severity**: MEDIUM
- **Flow**: Fingerprint & Similarity
- **Location**: `/api/similarity/tracks/{id}/similar` (400) vs `/api/tracks/{id}/fingerprint` (404)
- **Status**: NEW
- **Description**: `useSimilarTracks` has no retry/polling logic. `useTrackFingerprint` polls on 404.

---

### INT-44: `TrackInfo.album_art` in player state is always null
- **Severity**: MEDIUM
- **Flow**: Artwork
- **Location**: `player_state.py` → frontend player state sync
- **Status**: NEW
- **Description**: Unfixed TODO. Player state sync maps `album_art → artworkUrl`, so now-playing bar never receives artwork through WebSocket.

---

### LOW

---

### INT-45: Seek trim uses `getattr` fallback not tied to CHUNK_INTERVAL
- **Severity**: LOW
- **Flow**: Track Playback
- **Location**: `audio_stream_controller.py:1511`
- **Status**: NEW

### INT-46: Flow-control messages counted against WebSocket rate limiter
- **Severity**: LOW
- **Flow**: Track Playback
- **Location**: `system.py:174-178`
- **Status**: NEW

### INT-47: `AlbumInArtist` uses snake_case; domain `Album` uses camelCase — no transform
- **Severity**: LOW
- **Flow**: Library Browsing
- **Location**: `artists.py:53-60` → `useArtistDetailsData.ts:10-16`
- **Status**: NEW

### INT-48: `Track.to_dict()` omits `bitrate` — column populated but never surfaced
- **Severity**: LOW
- **Flow**: Library Browsing
- **Location**: `core.py:117-149`
- **Status**: NEW

### INT-49: Album search ignores `order_by` — sort silently dropped
- **Severity**: LOW
- **Flow**: Library Browsing
- **Location**: `albums.py:72-75`
- **Status**: NEW

### INT-50: `EnhancementContext.setPreset` accepts arbitrary string
- **Severity**: LOW
- **Flow**: Audio Enhancement
- **Location**: `EnhancementContext.tsx:101`
- **Status**: NEW

### INT-51: Settings panel intensity persists to different backend store than live enhancement
- **Severity**: LOW
- **Flow**: Audio Enhancement
- **Location**: `EnhancementSettingsPanel.tsx` → `/api/settings`
- **Status**: NEW

### INT-52: `files_failed` absent from `scan_complete` WS payload
- **Severity**: LOW
- **Flow**: Library Scanning
- **Status**: NEW

### INT-53: Discovery phase emits `percentage=0` — progress bar frozen
- **Severity**: LOW
- **Flow**: Library Scanning
- **Status**: NEW

### INT-54: No timeout on `asyncio.to_thread(scanner.scan_directories)`
- **Severity**: LOW
- **Flow**: Library Scanning
- **Status**: NEW

### INT-55: `_DebounceHandler._schedule()` calls `loop.call_later()` from watchdog thread (not thread-safe)
- **Severity**: LOW
- **Flow**: Library Scanning
- **Status**: NEW

### INT-56: `usePlayNormal` subscribes inside `playNormal()` — subscription gap
- **Severity**: LOW
- **Flow**: WebSocket Lifecycle
- **Location**: `usePlayNormal.ts`
- **Status**: NEW
- **Description**: Already tracked as FE-46/#2604 in frontend audit; cross-layer manifestation confirmed.

### INT-57: `fingerprint_progress` WS handler lacks `stream_type` filter
- **Severity**: LOW
- **Flow**: Fingerprint & Similarity
- **Status**: NEW

### INT-58: `AlbumGridContent.tsx` defines local `Album` interface with raw snake_case
- **Severity**: LOW
- **Flow**: Artwork
- **Location**: `AlbumGridContent.tsx`
- **Status**: NEW

---

## Cross-Flow Relationships

1. **Dual system problem**: INT-17 (query params), INT-18 (dual state), INT-50 (string preset) all stem from `EnhancementContext` being a legacy system that coexists with `useEnhancementControl`. Deleting `EnhancementContext` and migrating consumers fixes all three.

2. **WebSocket type completeness**: INT-30, INT-31, INT-38, INT-39, INT-40 share the root cause — the frontend `WebSocketMessageType` union is incomplete and backend messages are silently dropped. A comprehensive type sync would fix all five.

3. **Serializer `to_dict()` gaps**: INT-14 (total_duration), INT-48 (bitrate), INT-16 (artist_id) — the model `to_dict()` methods are missing fields that the serializer post-processing expects to add. Fixing each model's `to_dict()` resolves the issue at the source.

4. **snake_case ↔ camelCase boundary**: INT-27 (artist list), INT-47 (AlbumInArtist), INT-58 (AlbumGridContent) all bypass transformers and expose raw backend casing to React components. A consistent transformation policy at the API boundary would prevent all three.

5. **Artwork stale cache**: INT-21 (cache headers) + INT-22 (no subscriber) compound — even if cache-busting is added, no frontend code listens for the update signal.

## Prioritized Fix Order

1. **INT-17 + INT-18** — Enhancement dual system. Fix INT-17 first (query params → JSON body), then consolidate paths (INT-18). Unblocks all enhancement functionality from `EnhancementContext` consumers.
2. **INT-13** — AudioWorklet mono playback. Mono files play at wrong speed. Quick fix in worklet.
3. **INT-19** — Dual WebSocket connections. Halves server load and eliminates double-broadcast processing.
4. **INT-20** — Fingerprint field name mismatch. 3 of 25 dimensions invisible in visualization.
5. **INT-21 + INT-22** — Artwork cache + subscriber. Users see stale artwork after updates.
6. **INT-14 + INT-16** — Album `to_dict()` gaps. Fixes album duration display and artist navigation.
7. **INT-30 + INT-31 + INT-38-40** — WebSocket type completeness sweep. Add missing message types.
8. **INT-33** — Enhancement toggle during streaming. Audio disagrees with UI state.
9. **INT-35** — `library_scan_error` type missing. Scan spinner stuck permanently.
10. **INT-27 + INT-28** — Artist list transform + search endpoint fix.

---

*Report generated by Claude Opus 4.6 — 2026-03-20*
*Suggest next: `/audit-publish docs/audits/AUDIT_INTEGRATION_2026-03-20.md`*
