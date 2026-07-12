# Integration Audit — 2026-02-19

**Scope**: Backend-Frontend-Engine integration across all 7 data flows
**Auditor**: Claude Sonnet 4.6 (automated)
**Methodology**: Full code trace of each flow; findings disproved before inclusion; deduplication against open issues.

---

## Summary

| ID | Severity | Flow | Status | Issue |
|----|----------|------|--------|-------|
| INT-01 | HIGH | Flow 6 – Fingerprint | NEW | #TBD |
| INT-02 | MEDIUM | Flow 1 – Track Playback | NEW | #TBD |
| INT-03 | LOW | Flow 1 – Track Playback | NEW | #TBD |
| INT-04 | MEDIUM | Flow 4 – Library Scanning | NEW | #TBD |
| INT-05 | LOW | Flow 4 – Library Scanning | NEW | #TBD |
| INT-06 | MEDIUM | Flow 2 – Library Browsing | NEW | #TBD |
| — | MEDIUM | Flow 3 – Enhancement | Existing: #2256 | — |
| — | MEDIUM | Flow 3 – Enhancement | Existing: #2255 | — |
| — | LOW | Flow 5 – WebSocket | Existing: #2282 | — |
| — | HIGH | Flow 2 – Library | Existing: #2267 | — |
| — | HIGH | Flow 2 – Library | Existing: #2378 | — |
| — | MEDIUM | Flow 2 – Library | Existing: #2276 | — |
| — | MEDIUM | Flow 2 – Library | Existing: #2270 | — |
| — | LOW | Flow 3 – Enhancement | Existing: #2228 | — |
| — | LOW | Flow 5 – WebSocket | Existing: #2315 | — |
| — | HIGH | Flow 1 – Playback | Existing: #2381 | — |

---

## Flow Coverage Notes

### Flow 1: Track Playback
- REST: `POST /api/player/load` → `player.py:179` validates track via DB, calls `audio_player.add_to_queue()` ✓
- WebSocket: `play_enhanced` → `system.py:153` → `AudioStreamController.stream_enhanced_audio()` ✓
- Chunking: `chunked_processor.py` CHUNK_DURATION=15, CHUNK_INTERVAL=10 ✓
- Frontend: `usePlayEnhanced` → PCMStreamBuffer → AudioPlaybackEngine → Web Audio API ✓
- Sample rate: `audio_stream_start` sends `sample_rate`, frontend creates AudioContext with matching SR ✓

### Flow 2: Library Browsing
- Pagination: consistent `{tracks, total, offset, limit, has_more}` shape across library/albums/artists endpoints ✓
- camelCase/snake_case: all responses use snake_case, frontend type `PlaybackState` mixes both (#2276) ⚠
- `DEFAULT_TRACK_FIELDS` fallback misses many fields (#2267) ⚠

### Flow 3: Audio Enhancement
- Settings: `GET /api/player/enhancement/status` → `POST /api/player/enhancement/preset|intensity|toggle` ✓
- WebSocket `play_enhanced` ignores frontend preset/intensity in favor of stored settings (#2256) ⚠

### Flow 4: Library Scanning
- Scan: `POST /api/library/scan` → `LibraryScanner.scan_directories()` → WS broadcasts ✓
- `scan_progress` field mismatch → INT-04 ⚠
- `scan_complete` field naming → INT-05 ⚠

### Flow 5: WebSocket Lifecycle
- Connection: `/ws` endpoint in `system.py` ✓
- Rate limiting: `WebSocketRateLimiter(10 msg/s)` applied ✓
- Reconnection: `usePlayEnhanced` cleans up on disconnect, resubscribes on mount ✓
- `fingerprint_progress` and `seek_started` not in `WebSocketMessageType` enum (#2282) ⚠

### Flow 6: Fingerprint & Similarity
- Track fingerprint: `GET /api/tracks/{track_id}/fingerprint` returns sans-`_pct` field names ✓
- Album fingerprint: `GET /api/albums/{album_id}/fingerprint` returns with `_pct` suffix → INT-01 ✗
- Similarity: `GET /api/similarity/tracks/{track_id}/similar` with `SimilarTrack` Pydantic model ✓

### Flow 7: Artwork
- Path traversal protection: `is_relative_to(~/.auralis/artwork)` check ✓
- Cache-Control: 1 year max-age set ✓
- MIME detection: `mimetypes.guess_type()` with `image/jpeg` fallback ✓

---

## Findings

### INT-01: Album Fingerprint API Returns `_pct`-Suffixed Fields That Frontend Cannot Consume
- **Severity**: HIGH
- **Flow**: Flow 6 – Fingerprint & Similarity
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/routers/albums.py:224-237` → `auralis-web/frontend/src/utils/fingerprintToGradient.ts:14-53`
- **Status**: NEW

**Description**: The album fingerprint endpoint (`GET /api/albums/{album_id}/fingerprint`) returns the 7 frequency-band dimensions with a `_pct` suffix (`sub_bass_pct`, `bass_pct`, `low_mid_pct`, `mid_pct`, `upper_mid_pct`, `presence_pct`, `air_pct`). The frontend `AudioFingerprint` TypeScript interface and all consumers expect these fields WITHOUT the suffix (`sub_bass`, `bass`, `low_mid`, …). The track fingerprint endpoint (`GET /api/tracks/{track_id}/fingerprint`) correctly uses the unsuffixed names. When the frontend renders album gradients or album character panes using data from the album endpoint, all 7 frequency fields resolve to `undefined`, producing `NaN` in all arithmetic.

**Evidence**:

Backend returns (albums.py:224-237):
```python
dimensions = [
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct', 'upper_mid_pct', 'presence_pct', 'air_pct',
    ...
]
```

Frontend expects (fingerprintToGradient.ts:14-22):
```typescript
export interface AudioFingerprint {
  sub_bass: number;      // 20-60 Hz
  bass: number;          // 60-250 Hz
  low_mid: number;
  mid: number;
  upper_mid: number;
  presence: number;
  air: number;
```

Consumer (fingerprintToGradient.ts:60):
```typescript
const bassEnergy = fp.sub_bass + fp.bass + fp.low_mid;  // NaN for album fingerprints
```

`useAlbumFingerprint.ts:41-42` fetches the album endpoint and types the response as `AudioFingerprint`, directly feeding the mismatch to UI components.

Additional field-name differences between the two endpoints:
- Track: `pitch_confidence`, Album: `pitch_stability`
- Track: `chroma_energy_mean`, Album: `chroma_energy`
- Track: `stereo_correlation`, Album: `phase_correlation`
- Album includes `dynamic_range_variation`, `loudness_variation_std`, `peak_consistency` not in track endpoint

**Impact**: Album character pane gradients and all fingerprint-derived visualizations render incorrectly (NaN-based calculations silently produce wrong colors/values) for every album with fingerprints. Album-level fingerprint data is completely unusable.

**Suggested Fix**: Align the album endpoint to use the same field names as the track endpoint and the `AudioFingerprint` interface. In `albums.py`, change `sub_bass_pct` → `sub_bass`, `bass_pct` → `bass`, etc. This is a one-line-per-field rename in the `dimensions` list.

---

### INT-02: AudioPlaybackEngine Buffer Threshold Inconsistent with usePlayEnhanced Auto-Start
- **Severity**: MEDIUM
- **Flow**: Flow 1 – Track Playback
- **Boundary**: Frontend (usePlayEnhanced) → Frontend (AudioPlaybackEngine)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:344-348` → `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:63,109-117`
- **Status**: NEW

**Description**: `usePlayEnhanced` auto-starts playback when `bufferedSamples >= sampleRate * channels * 2` (~2 seconds of audio). `AudioPlaybackEngine.startPlayback()` enforces its own internal threshold: `minBufferSamples = 240000` (hardcoded, ~5s at 48kHz mono or ~2.7s at 44100Hz stereo). When `usePlayEnhanced` calls `engine.startPlayback()` before the engine's threshold is met, the engine logs a warning, transitions to `'error'` state, and invokes the underrun callback — without actually starting playback. The `'error'` state is not propagated to Redux (the `onStateChanged` callback only handles `'paused'` and `'playing'`), so the UI does not reflect the failure. Subsequent chunk arrivals retry `startPlayback()`, and eventually the engine's threshold is met. Result: a silent delay of 0.7–3 seconds longer than expected before audio begins, plus a transient `'error'` state in the engine that is invisible to the user.

**Evidence**:

usePlayEnhanced.ts:344-348 (stream_start handler):
```typescript
const minBufferSamples = message.data.sample_rate * message.data.channels * minBufferSeconds;
if (buffer.getAvailableSamples() >= minBufferSamples) {  // 2s threshold
  engine.startPlayback();
```

AudioPlaybackEngine.ts:63,110-117:
```typescript
private minBufferSamples: number = 240000; // ~5 seconds at 48kHz
// ...
if (availableSamples < this.minBufferSamples) {
  // ...
  this.setState('error');        // enters error state
  this.onBufferUnderrun();
  return;                        // does NOT start playback
}
```

**Impact**: Playback start is delayed by up to 3 seconds relative to UI expectations; the engine enters an undisplayed error state on the first startPlayback call. No actual audio data is lost, but the user experience is degraded.

**Suggested Fix**: Either raise the `usePlayEnhanced` threshold to match the engine (`minBufferSeconds = 5` or `minBufferSamples = this.engine.minBufferSamples`), or expose a `getMinBufferSamples()` method from `AudioPlaybackEngine` so `usePlayEnhanced` can read it. Additionally, the engine should return `false` (or throw) rather than entering `'error'` state for an early call before the buffer is ready.

---

### INT-03: `track_loaded` WebSocket Broadcast Leaks Filesystem Path to All Clients
- **Severity**: LOW
- **Flow**: Flow 1 – Track Playback
- **Boundary**: Backend → All WebSocket clients
- **Location**: `auralis-web/backend/routers/player.py:217-220`
- **Status**: NEW

**Description**: When a track is loaded via `POST /api/player/load`, the backend broadcasts `{"type": "track_loaded", "data": {"track_path": track.filepath}}` to ALL connected WebSocket clients. `track.filepath` is an absolute filesystem path (e.g. `/home/user/Music/song.mp3`). The REST response (line 232) also returns `track_path`. The `track_id` is already known to the requester, and no connected client needs the filesystem path for any documented purpose.

**Evidence** (player.py:217-220):
```python
await connection_manager.broadcast({
    "type": "track_loaded",
    "data": {"track_path": track.filepath}
})
```

**Impact**: Exposes server filesystem structure (home directory, music folder layout) to any WebSocket-connected browser client. Not exploitable for path traversal (path validation is input-side), but an information leak in a multi-user or network-accessible deployment.

**Suggested Fix**: Remove `track_path` from the broadcast payload; use `track_id` only. Update any frontend listeners to use the `track_id` to retrieve metadata.

---

### INT-04: `scan_progress` WebSocket Message Sends Directory Path in `current_file` Field
- **Severity**: MEDIUM
- **Flow**: Flow 4 – Library Scanning
- **Boundary**: Backend → Frontend (WebSocket)
- **Location**: `auralis-web/backend/routers/library.py:519-522` → `auralis-web/frontend/src/contexts/WebSocketContext.tsx:74` / `auralis-web/frontend/src/types/websocket.ts:300`
- **Status**: NEW

**Description**: The scan progress callback in `library.py` populates the `current_file` field with the value of `progress_data.get('directory')` — a directory path, not a file path. The frontend TypeScript type for `scan_progress` declares `current_file?: string` expecting a filename (the mock at `src/test/mocks/websocket.ts:194` uses `current_file: '/path/to/current.mp3'`). UI components displaying "currently scanning file" will show directory names instead.

**Evidence** (library.py:519-522):
```python
"current_file": progress_data.get('directory'),  # 'directory' value, not the file being scanned
```

Frontend type (types/websocket.ts:300):
```typescript
current_file?: string;  // frontend expects a filename
```

Mock (test/mocks/websocket.ts:194):
```typescript
current_file: currentFile,  // mock uses a file path like '/music/song.mp3'
```

**Impact**: UI displays the directory name being scanned rather than the filename currently being processed. The semantic intent of the field is broken; any progress indicator showing "Scanning: …" will display misleading text.

**Suggested Fix**: Change `progress_data.get('directory')` to `progress_data.get('current_file')` or `progress_data.get('file')` — whichever key the `LibraryScanner` populates with the currently-being-scanned filename. If the scanner only reports the directory, rename the field to `current_directory` and update the frontend type accordingly.

---

### INT-05: `scan_complete` WebSocket Uses `tracks_added`, REST Response Uses `files_added`
- **Severity**: LOW
- **Flow**: Flow 4 – Library Scanning
- **Boundary**: Backend (WebSocket broadcast) ↔ Backend (REST response)
- **Location**: `auralis-web/backend/routers/library.py:554-558` vs `library.py:562-570`
- **Status**: NEW

**Description**: The `scan_complete` WebSocket broadcast names the count of newly added tracks `tracks_added` (line 556: `"tracks_added": result.files_added`). The REST response from the same endpoint names the same metric `files_added` (line 564). Clients subscribing to `scan_complete` and also reading the REST response must handle two different field names for the same value.

**Evidence**:

WebSocket broadcast (library.py:553-558):
```python
await connection_manager.broadcast({
    "type": "scan_complete",
    "data": {
        "tracks_added": result.files_added,  # "tracks_added" key
    }
})
```

REST response (library.py:562-564):
```python
return {
    "files_added": result.files_added,      # "files_added" key
```

Frontend type (types/websocket.ts:308):
```typescript
tracks_added: number;  // correct for WS
```

Frontend hook (hooks/library/useLibraryWithStats.ts:381):
```typescript
alert(`✅ Scan complete!\nAdded: ${result.files_added || 0} tracks`);  // reads REST response
```

**Impact**: No runtime breakage (each consumer reads from the correct channel), but the dual naming adds confusion and makes adding new consumers error-prone. Both channels should use the same field name.

**Suggested Fix**: Standardize on `files_added` in both channels (matches the `ScanResult` attribute name). Update the WebSocket broadcast to use `"files_added": result.files_added` and update the frontend `websocket.ts:308` type accordingly.

---

### INT-06: Album Search Returns Incorrect `total` Count (Estimated, Not Actual)
- **Severity**: MEDIUM
- **Flow**: Flow 2 – Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/routers/albums.py:72-76` (and mirrored at `library.py:420-424` for the duplicate albums endpoint)
- **Status**: NEW

**Description**: When the `search` parameter is provided to `GET /api/albums`, the backend calls `repos.albums.search(...)` which returns only a `list` (no total count). The router estimates: `total = len(albums) + offset`. For the first page with `limit=50` and 60 matching albums: the backend returns 50 items, `total = 50 + 0 = 50`, `has_more = True`. The frontend sees `total=50` but there are 60 albums; it may render "50 results" and stop paginating after the second page fetch returns 0 items. By contrast, the track search endpoint (`library.py:118`) correctly returns `(tracks, total)` from `repos.tracks.search()`.

**Evidence**:

albums.py:72-76:
```python
if search:
    albums = repos.albums.search(search, limit=limit, offset=offset)
    # For search, we don't have total count yet, so estimate
    total = len(albums) + offset       # WRONG: underestimates true total
    has_more = len(albums) >= limit    # heuristic only
```

library.py:118-119 (track search, CORRECT):
```python
tracks, total = repos.tracks.search(search, limit=limit, offset=offset)
has_more = (offset + len(tracks)) < total   # correct
```

**Impact**: Album search pagination is broken when there are more results than `limit`. UI shows wrong result count; infinite scroll or "load more" stops one page early or misreports the total.

**Suggested Fix**: Update `repos.albums.search()` to return `(list, total)` like `repos.tracks.search()`, or add a separate `repos.albums.search_count()` call. Then replace the estimation with a real total.

---

## Previously-Confirmed Existing Issues (Not Re-Reported)

| Issue | Description |
|-------|-------------|
| #2256 | `play_enhanced` WS ignores frontend preset/intensity; uses stored settings |
| #2255 | `startStreaming` Redux action hardcodes `intensity: 1.0` |
| #2381 | Seek WS message preset/intensity discarded by backend |
| #2282 | `fingerprint_progress` and `seek_started` missing from `WebSocketMessageType` enum |
| #2378 | Album `trackCount` and `totalDuration` always undefined (no camelCase transformer) |
| #2276 | `PlaybackState` interface mixes camelCase and snake_case |
| #2267 | `DEFAULT_TRACK_FIELDS` fallback missing critical metadata fields |
| #2270 | Album `artwork_path` leaks filesystem path in serializer fallback |
| #2228 | Enhancement `_preprocess_upcoming_chunks` is a no-op (wrong cache layer) |
| #2315 | `AudioStreamController._stream_type` assumes per-request instantiation |
| #2390 | BrickWallLimiter discards cross-chunk gain state |
