# Backend-Frontend-Engine Integration Audit — 2026-02-17

## Executive Summary

Traced 7 critical data flows across the audio engine, FastAPI backend, and React frontend.

- **Total raw findings**: 20
- **Deduplicated against existing issues**: 9 skipped (extend or duplicate existing open issues)
- **New findings**: 11 (2 CRITICAL, 4 HIGH, 1 MEDIUM, 4 LOW)
- **Issues created**: #2377–#2387

---

## Findings

### INT-01: `usePlayerAPI.play()` and `usePlayerAPI.pause()` call commented-out REST endpoints — always 404
- **Severity**: HIGH
- **Flow**: Flow 1 (Track Playback)
- **Boundary**: Frontend `usePlayerAPI.ts` → Backend `player.py`
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerAPI.ts:94-143` → `auralis-web/backend/routers/player.py:235-261`
- **Status**: NEW
- **Description**: `usePlayerAPI.play()` issues `POST /api/player/play` and `pause()` issues `POST /api/player/pause`. Both endpoints were deliberately commented out in `player.py` (lines 235-261) with a deprecation comment directing to WebSocket instead. The routes are never registered. Any component that calls `usePlayerAPI.play()` or `.pause()` silently receives a 404.
- **Evidence**:
  ```typescript
  // usePlayerAPI.ts:94
  const response = await fetch(`/api/player/play`, { method: 'POST', ... });
  ```
  ```python
  # player.py:235-260 — entire endpoint commented out:
  # @router.post("/api/player/play", response_model=None)
  # async def play_audio() -> Dict[str, Any]:
  #     """DEPRECATED: Use WebSocket 'play_enhanced' message instead."""
  ```
- **Impact**: Any code path that still calls `usePlayerAPI.play()` / `.pause()` (rather than the newer `usePlaybackControl.play()`) fails silently with 404. The newer `usePlaybackControl` is the intended path via WebSocket.
- **Suggested Fix**: Remove `play()` and `pause()` from `usePlayerAPI` or replace them with no-ops that warn. Audit callers to confirm they've all migrated to `usePlaybackControl`.

---

### INT-02: Album `trackCount` and `totalDuration` always `undefined` — snake_case response, no transformer
- **Severity**: HIGH
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend `serialize_album()` → Frontend `Album` TypeScript type
- **Location**: `auralis-web/backend/routers/serializers.py:168-173` → `auralis-web/frontend/src/types/domain.ts:56`
- **Status**: NEW
- **Description**: `serialize_album()` returns `track_count` and `total_duration` in snake_case. The frontend `Album` interface defines `trackCount: number` and `totalDuration?: number` in camelCase. `useLibraryQuery.extractItemsFromResponse()` uses the response verbatim with no case conversion. The fields are therefore permanently `undefined`.
- **Evidence**:
  ```python
  # serializers.py
  DEFAULT_ALBUM_FIELDS = {
      'track_count': 0,    # snake_case
      'total_duration': 0  # snake_case
  }
  ```
  ```typescript
  // domain.ts:56-57
  export interface Album {
    trackCount: number;      // camelCase — never populated
    totalDuration?: number;  // camelCase — never populated
  }
  // useLibraryQuery.ts:162-169 — no transformation
  case 'albums':
    return response.albums || response.items || [];
  ```
- **Impact**: Album track count and duration display as `NaN` or empty in any component rendering these fields.
- **Suggested Fix**: Either add a camelCase transformer in `useLibraryQuery` (consistent with the rest of the codebase), or rename the `Album` interface fields to snake_case to match the backend.

---

### INT-03: `useLibraryQuery` builds `/api/library/albums` and `/api/library/artists` — routes are `/api/albums` and `/api/artists` (404)
- **Severity**: CRITICAL
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Frontend `useLibraryQuery.ts` → Backend album/artist routers
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:183` → `auralis-web/backend/routers/albums.py:41`, `artists.py:97`
- **Status**: NEW
- **Description**: `useLibraryQuery.buildEndpoint()` constructs URLs as `/api/library/${queryType}`, meaning albums → `/api/library/albums` and artists → `/api/library/artists`. The actual backend routes are registered under `/api/albums` and `/api/artists` respectively. The library router only exposes `/api/library/tracks`, `/api/library/stats`, etc.
- **Evidence**:
  ```typescript
  // useLibraryQuery.ts:183
  const baseUrl = `/api/library/${queryType}`;
  // albums  → /api/library/albums   ✗ (404)
  // artists → /api/library/artists  ✗ (404)
  // tracks  → /api/library/tracks   ✓
  ```
  ```python
  # albums.py:41
  @router.get("/api/albums")
  # artists.py:97
  @router.get("/api/artists", response_model=ArtistsListResponse)
  ```
- **Impact**: Every call to `useAlbumsQuery()`, `useArtistsQuery()`, and `useLibraryQuery('albums'/'artists')` returns 404. Album and artist browsing pages are completely non-functional for these hooks.
- **Suggested Fix**: Fix `buildEndpoint()` to use `/api/albums` and `/api/artists` for those query types, or add `/api/library/albums` and `/api/library/artists` aliases in the backend.

---

### INT-04: Album search fabricates `total` count and produces incorrect `has_more` — infinite scroll loop
- **Severity**: MEDIUM
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend `albums.py` search path → Frontend pagination
- **Location**: `auralis-web/backend/routers/albums.py:72-76`
- **Status**: NEW
- **Description**: When `search` is provided to `GET /api/albums`, `total` is computed as `len(albums) + offset` (not a real count), and `has_more` is derived from `len(albums) >= limit`. If the final page is exactly `limit` items, `has_more` is `True` even though no more results exist, causing an infinite-scroll loop.
- **Evidence**:
  ```python
  # albums.py:72-76
  if search:
      albums = repos.albums.search(search, limit=limit, offset=offset)
      total = len(albums) + offset  # BUG: not the real total
      has_more = len(albums) >= limit  # BUG: last full page always reports has_more=True
  ```
  Compare with correct non-search path:
  ```python
  albums, total = repos.albums.get_all(limit=limit, offset=offset, order_by=order_by)
  has_more = (offset + len(albums)) < total
  ```
- **Impact**: Album search pagination is broken: the `total` count shown in the UI is wrong, and infinite scroll fires one extra page request on every search result whose count is a multiple of `limit`.
- **Suggested Fix**: Add `search_count()` to `AlbumRepository` and use it here, mirroring the pattern used in the non-search path.

---

### INT-05: Seek sends `preset`/`intensity` that backend silently discards; falls back to `adaptive/1.0` when settings unavailable
- **Severity**: LOW
- **Flow**: Flow 3 (Audio Enhancement)
- **Boundary**: Frontend `usePlayEnhanced.ts` `seekTo()` → Backend seek WebSocket handler
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:653-661` → `auralis-web/backend/routers/system.py:407-413`
- **Status**: NEW
- **Description**: The frontend includes `preset` and `intensity` in the `seek` WebSocket message, but the backend handler always reads these from `get_enhancement_settings()`, ignoring what the frontend sent. If `get_enhancement_settings` is `None` (not configured), seek falls back to `preset="adaptive", intensity=1.0` regardless of the actually-playing preset.
- **Evidence**:
  ```typescript
  // usePlayEnhanced.ts:653-661
  wsContext.send({ type: 'seek', data: { track_id, position, preset, intensity } });
  ```
  ```python
  # system.py:407-413
  preset = "adaptive"
  intensity = 1.0
  if get_enhancement_settings is not None:
      settings = get_enhancement_settings()
      preset = settings.get("preset", "adaptive")
      intensity = settings.get("intensity", 1.0)
  # data.get("preset") and data.get("intensity") never read
  ```
- **Impact**: Low. If `get_enhancement_settings` is not configured, seek always re-processes with `adaptive/1.0` preset, potentially changing enhancement character after seeking.
- **Suggested Fix**: Either read `preset`/`intensity` from the WebSocket message data (fast path) or document that the backend is the single source of truth and stop sending them from the frontend.

---

### INT-06: `asyncio.create_task()` called from synchronous worker thread — fingerprinting silently never starts after scan
- **Severity**: CRITICAL
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: `scanner.py` (sync thread) → asyncio event loop
- **Location**: `auralis/library/scanner/scanner.py:142`
- **Status**: NEW
- **Description**: `scan_directories()` is called via `asyncio.to_thread()` from `library.py:529`, so it runs in a worker thread with no asyncio event loop. At line 142, it calls `asyncio.create_task(self._enqueue_fingerprints(...))`, which raises `RuntimeError: no running event loop`. This exception is silently caught by the outer `except Exception` at `scanner.py:162`, which only logs a warning. Result: fingerprinting is silently never enqueued for any newly scanned track.
- **Evidence**:
  ```python
  # scanner.py:139-142 — runs in worker thread (no event loop):
  if self.fingerprint_queue and batch_result.added_tracks:
      import asyncio
      asyncio.create_task(self._enqueue_fingerprints(batch_result.added_tracks))
      # ^ RuntimeError: no running event loop
  ```
  ```python
  # library.py:529 — calls scanner in thread pool:
  result = await asyncio.to_thread(scanner.scan_directories, directories=request.directories, ...)
  ```
  ```python
  # scanner.py:162 — silently swallows the RuntimeError:
  except Exception as e:
      logger.warning(f"Fingerprint enqueue failed: {e}")
  ```
- **Impact**: After every scan, no newly added tracks are fingerprinted. Fingerprint-dependent features (similarity search, AlbumCharacterPane gradients) never have data for new tracks. The scan appears to succeed in the UI.
- **Suggested Fix**: Replace `asyncio.create_task()` with `asyncio.run_coroutine_threadsafe(coro, loop)` (passing the event loop reference), or return the list of added tracks to the async caller (`library.py`) and enqueue fingerprinting there.

---

### INT-07: MP4/M4A lyrics branch unreachable — `elif hasattr(audio_file, 'get')` matches before MP4 `__getitem__` check
- **Severity**: LOW
- **Flow**: Flow 4 (Library Scanning / Metadata)
- **Boundary**: `library.py` lyrics handler → mutagen MP4 object
- **Location**: `auralis-web/backend/routers/library.py:256-275`
- **Status**: NEW
- **Description**: The lyrics extraction `elif` chain checks `hasattr(audio_file, 'get')` before checking `hasattr(audio_file, '__getitem__')`. Mutagen's `MP4Tags` implements `.get()`, so MP4 files fall into the Vorbis branch and look up lyrics with key `'LYRICS'` instead of the MP4 key `'\xa9lyr'`. The actual MP4 branch (`elif hasattr(audio_file, '__getitem__')`) is never reached.
- **Evidence**:
  ```python
  # library.py:256-275
  if hasattr(audio_file, 'tags') and audio_file.tags:
      ...  # ID3 branch
  elif hasattr(audio_file, 'get'):
      lyrics = audio_file.get('LYRICS', [None])[0]  # WRONG KEY for MP4
  elif hasattr(audio_file, '__getitem__'):
      lyrics = audio_file.get('\xa9lyr', [None])[0]  # UNREACHABLE for MP4
  ```
- **Impact**: All MP4/M4A files with embedded lyrics silently return `None`. Users with AAC/M4A libraries never see lyrics regardless of what's embedded.
- **Suggested Fix**: Check `isinstance(audio_file, mutagen.mp4.MP4)` explicitly, or reorder the elif chain so the MP4 check precedes the generic `hasattr(audio_file, 'get')` check.

---

### INT-08: Scan progress `current_file` always shows directory or `None` — actual filename never reported
- **Severity**: LOW
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Backend scan progress callback → Frontend `ScanProgressMessage`
- **Location**: `auralis-web/backend/routers/library.py:522` → `auralis-web/frontend/src/types/websocket.ts:298`
- **Status**: NEW
- **Description**: The progress callback sets `current_file` to `progress_data.get('directory')`. During the `'discovering'` stage this is the directory being walked; during `'processing'` the scanner reports `{'stage': 'processing', 'processed': ..., 'added': ...}` with no `'directory'` key, so `current_file` becomes `None`.
- **Evidence**:
  ```python
  # library.py:522
  "current_file": progress_data.get('directory'),  # 'directory' absent during processing stage
  ```
  ```python
  # scanner.py:146-152 — processing stage callback has no 'directory' key:
  self._report_progress({'stage': 'processing', 'progress': progress, 'processed': result.files_processed})
  ```
- **Impact**: The scan progress overlay shows the directory name during discovery and `undefined` during file processing — users never see which file is being processed.
- **Suggested Fix**: Add a `current_file` key to the scanner's processing-stage progress dict, populated with the currently processed filepath.

---

### INT-09: WebSocket reconnect does not restart audio stream — playback permanently silenced
- **Severity**: HIGH
- **Flow**: Flow 5 (WebSocket Lifecycle)
- **Boundary**: `WebSocketContext.tsx` reconnect handler → `audio_stream_controller.py` stream loop
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:376-413` → `auralis-web/backend/audio_stream_controller.py:484-486`
- **Status**: NEW
- **Description**: When the WebSocket reconnects, no `play_enhanced` or `play_normal` command is re-sent. The backend stream loop exits on disconnect (`audio_stream_controller.py:484`), so after reconnect the backend is idle. The `WebSocketContext` message queue only holds messages attempted during disconnection, not the stream command that was sent before disconnection. The UI remains in "playing" state with no audio.
- **Evidence**:
  ```typescript
  // WebSocketContext.tsx:384-387 — reconnect only re-sends messages queued during disconnection:
  while (messageQueueRef.current.length > 0) {
    const message = messageQueueRef.current.shift();
    manager.send(JSON.stringify(message));
  }
  // No mechanism to re-issue the active streaming command
  ```
  ```python
  # audio_stream_controller.py:484-486 — backend exits on disconnect:
  if not self._is_websocket_connected(websocket):
      logger.info(f"WebSocket disconnected, stopping stream")
      break
  ```
- **Impact**: Any WebSocket disconnect (network hiccup, backend restart, browser tab switching on mobile) during enhanced/normal playback permanently silences the stream. The player UI shows "playing" with no audio and no error recovery.
- **Suggested Fix**: In `WebSocketContext`, store the current streaming command (type + payload). On reconnect, re-issue it. On the backend, make the stream loop check for a reconnect-with-resume message type.

---

### INT-10: Track library response uses `artwork_url` but `useLibraryData` reads `album_art`/`albumArt` — track artwork always `undefined`
- **Severity**: HIGH
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Backend `Track.to_dict()` → Frontend `useLibraryData.ts` track transformer
- **Location**: `auralis/library/models/core.py:141` → `auralis-web/frontend/src/hooks/library/useLibraryData.ts:164`
- **Status**: NEW
- **Description**: `Track.to_dict()` returns artwork under the key `'artwork_url'` (standardized, comment: "was album_art"). The frontend transformer in `useLibraryData.ts` reads `track.album_art || track.albumArt` to populate the `albumArt` field. Neither key exists in the response. The field `artwork_url` is never read.
- **Evidence**:
  ```python
  # core.py:141
  'artwork_url': album_artwork,   # Standardized field name (was album_art)
  ```
  ```typescript
  // useLibraryData.ts:163-165
  albumArt: track.album_art || track.albumArt,  // reads 'album_art' or 'albumArt'
  // 'artwork_url' from the response is never read → albumArt always undefined
  ```
  Same pattern repeated at `useLibraryData.ts:228-232` in `loadMore`.
- **Impact**: Track artwork is always `undefined` in the library view's track list. Components relying on `Track.albumArt` from `useLibraryData` show no cover art.
- **Suggested Fix**: Update `useLibraryData.ts` to read `track.artwork_url || track.album_art || track.albumArt` to handle the current name and legacy names.

---

### INT-11: `getArtworkUrl()` appends `Date.now()` timestamp — defeats `max-age=31536000` cache header
- **Severity**: LOW
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Frontend `artworkService.ts` → Backend `artwork.py` cache headers
- **Location**: `auralis-web/frontend/src/services/artworkService.ts:59` ↔ `auralis-web/backend/routers/artwork.py:118-121`
- **Status**: NEW
- **Description**: The artwork endpoint sets `Cache-Control: public, max-age=31536000` (1 year). `artworkService.getArtworkUrl()` appends `?t=${Date.now()}` to every URL, ensuring each call produces a unique URL that is never served from cache. The browser fetches the image from the network on every render.
- **Evidence**:
  ```typescript
  // artworkService.ts:59
  return `${API_BASE_URL}/api/albums/${albumId}/artwork?t=${Date.now()}`;
  ```
  ```python
  # artwork.py:118-121
  return FileResponse(str(requested_path), headers={"Cache-Control": "public, max-age=31536000"})
  ```
- **Impact**: Every album card/detail render triggers a network request for artwork, even if the image was just loaded. In a library view with 100 albums, this causes 100 redundant network requests.
- **Suggested Fix**: Remove `?t=${Date.now()}` from `getArtworkUrl()`. If cache-busting after artwork changes is needed, use a content hash or version parameter updated only when artwork actually changes.

---

## Skipped Findings (Existing Issues)

| Finding | Reason | Existing Issue |
|---------|--------|----------------|
| Play hooks fetch full library to find one track | Exact duplicate | #2258 |
| `usePlayNormal` buffer threshold ignores channel count | Exact duplicate | #2268 |
| Volume scale inconsistency across frontend layers | Extends | #2251 |
| Artist `artwork_url` vs `artworkUrl` (snake→camel) | Extends | #2110 |
| `preprocess_upcoming_chunks` cache dict ephemeral | Extends | #2228 |
| Fingerprint endpoint `track.artist` AttributeError | Exact duplicate | #2260 |
| `fingerprint_progress` missing from WS type union | Exact duplicate | #2282 |
| Dual WS systems with different proxy URLs | Extends | #2117 |
| Fingerprint field name mismatch (pitch_stability etc.) | Exact duplicate | #2280 |

## Summary Table

| ID | Severity | Flow | Description | Issue |
|----|----------|------|-------------|-------|
| INT-01 | HIGH | Flow 1 | `usePlayerAPI.play/pause` call non-existent REST endpoints | #2377 |
| INT-02 | HIGH | Flow 2 | Album `trackCount`/`totalDuration` always `undefined` — no camelCase transformer | #2378 |
| INT-03 | CRITICAL | Flow 2 | `useLibraryQuery` builds `/api/library/albums` but route is `/api/albums` — 404 | #2379 |
| INT-04 | MEDIUM | Flow 2 | Album search fabricates `total` count and incorrect `has_more` | #2380 |
| INT-05 | LOW | Flow 3 | Seek ignores frontend `preset`/`intensity`; falls back to `adaptive/1.0` when unconfigured | #2381 |
| INT-06 | CRITICAL | Flow 4 | `asyncio.create_task()` in sync thread — fingerprinting silently never queued after scan | #2382 |
| INT-07 | LOW | Flow 4 | MP4 lyrics branch unreachable — wrong `elif` order causes `©lyr` key never checked | #2383 |
| INT-08 | LOW | Flow 4 | Scan progress `current_file` shows directory or `None`, never actual filename | #2384 |
| INT-09 | HIGH | Flow 5 | WebSocket reconnect does not restart audio stream — playback permanently silenced | #2385 |
| INT-10 | HIGH | Flow 7 | `Track.to_dict()` returns `artwork_url`; `useLibraryData` reads `album_art` — always `undefined` | #2386 |
| INT-11 | LOW | Flow 7 | `getArtworkUrl()` appends `Date.now()`, defeating 1-year cache header | #2387 |

**Results: 2 CRITICAL, 4 HIGH, 1 MEDIUM, 4 LOW — 11 new findings**
