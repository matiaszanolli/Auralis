# Incremental Audit — 2026-02-22

**Range**: `HEAD~10..HEAD` (commits `44cd4a99..255b39a7`)
**Auditor**: Claude Opus 4.6 (automated)
**Date**: 2026-02-22

---

## 1. Change Summary

10 batch-fix commits resolving ~90 issues across all layers. 73 files changed, +2857/-653 lines.

| Commit | Description |
|--------|-------------|
| `255b39a7` | batch 23: audio integrity, security, correctness |
| `d2fe8f97` | batch 22: integration, streaming, type correctness |
| `09c69b38` | audit fix: integration issues, WebSocket subscription |
| `4e3aa8b7` | batch 21: frontend, integration, backend |
| `855f9fb8` | batch 20: security, concurrency, correctness |
| `5343b23d` | batch 19: DSP, type-safety, security, UX |
| `1a4a0eb4` | batch 18: type-safety, DSP, correctness |
| `78b0e861` | batch 17: performance, accessibility, correctness |
| `f9c8b4fd` | batch 16: frontend/backend/DSP correctness and performance |
| `44cd4a99` | batch 15: correctness, performance, integration |

## 2. High-Risk Changes

### Audio Core (`auralis/core/`, `auralis/dsp/`)

| File | Change | Risk Assessment |
|------|--------|-----------------|
| `hybrid_processor.py` | `sanitize_audio()` → `validate_audio_finite(repair=False)` + sample-count assert after limiter | **OK** — fail-fast surfaces DSP bugs instead of silently masking them (#2520). `validate_audio_finite` raises `ModuleError` which propagates cleanly. |
| `psychoacoustic_eq.py` | +6.02 dB Hanning window compensation in analysis path | **OK** — correct: Hanning coherent gain = 0.5 = -6.02 dB. Without compensation, adaptive EQ over-boosts by ~6 dB (#2518). |
| `critical_bands.py` | First Bark frequency: 0 → 20 Hz | **OK** — fixes division-by-zero: `sqrt(0 * 100) = 0 Hz` center frequency (#2208). |
| `io/processing.py` | Preserve input dtype during resampling (was hardcoded float32) | **OK** — correct fix (#2227). `copy=False` avoids redundant copy when dtype matches. |
| `vectorized_envelope.py` | `except:` → `except Exception:` | **OK** — code quality. |
| `unified_loader.py` | Added OPUS format support | **OK** — added to both `SUPPORTED_FORMATS` and `FFMPEG_FORMATS` (#2529). |

### Player (`auralis/player/`)

| File | Change | Risk Assessment |
|------|--------|-----------------|
| `enhanced_audio_player.py` | Invalidate prebuffer on shuffle/repeat toggle | **OK** — correct fix (#2154). Without this, gapless transition would use the wrong track. |
| `gapless_playback_engine.py` | Validate prebuffered track ID/path matches expected next track before use | **FINDING** — see INC-02. Two separate lock acquisitions create TOCTOU window. |
| `realtime/processor.py` | Replaced tanh saturation with linear gain reduction | **OK** — correct fix (#2201). tanh added harmonic distortion to all samples, not just clipping ones. Linear preserves signal shape. |

### Backend Core

| File | Change | Risk Assessment |
|------|--------|-----------------|
| `audio_stream_controller.py` | Send `crossfade_samples=0` to prevent double-crossfade; flatten stereo PCM for framing | **OK** — correct fixes (#2188, #2257). Server applies crossfade, client should not re-apply. Stereo flatten prevents ~800KB frames. |
| `state_manager.py` | Wall-clock elapsed time for position; lightweight position broadcast | **OK** — correct fixes (#2171, #2570). Moves `next_track()` and broadcast outside lock to prevent deadlock. |
| `proactive_buffer.py` | Resource cleanup, tempdir fix, comment corrections | **OK** — adds `processor.close()` in finally block (#2567). |
| `processing_engine.py` | `config.sample_rate` → `config.internal_sample_rate` | **OK** — verified `internal_sample_rate` exists on both `Config` and `UnifiedConfig`. Old attribute didn't exist; was likely a latent AttributeError. |
| `path_security.py` | Removed `Path.home()` from allowed dirs | **OK** — security fix (#2562). Prevents traversal to `~/.ssh`, `~/.gnupg`. |

### Backend Routers

| File | Change | Risk Assessment |
|------|--------|-----------------|
| `routers/library.py` | Removed `GET /api/library/albums` (duplicate of `/api/albums`); added `GET /api/library/tracks/{track_id}` | **FINDING** — see INC-01. Frontend search still calls the removed endpoint. |
| `routers/player.py` | Removed exception details from HTTP 500 responses | **OK** — security fix (#2573). Logs `exc_info=True` for debugging; user sees generic message. |
| `routers/processing_api.py` | Upload size limit, magic byte validation, UUID filenames, path validation | **OK** — comprehensive security hardening (#2559, #2560, #2170). `open(..., "xb")` prevents symlink TOCTOU. |
| `routers/artwork.py` | Magic byte detection for MIME type; field rename `artwork_path` → `artwork_url` | **OK** — MIME fix correct (#2510). Field rename consistent with other serializers (#2508). |
| `routers/enhancement.py` | Single-source CHUNK_DURATION import; buffer manager notification on intensity change | **OK** — correct fixes (#2564, #2504). |
| `routers/system.py` | Send enhancement settings on WS connect; accept frontend-sent preset/intensity as primary | **OK** — correct fixes (#2507, #2256). Validates preset/intensity before accepting. |
| `routers/webm_streaming.py` | LRU cache for decoded audio files; read-only flag | **FINDING** — see INC-03. Cache has no file-change invalidation. Read-only flag is correct (`np.clip` and `astype` create new arrays in encoder). |
| `routers/serializers.py` | Added `artwork_url`/`artwork_source` to artist defaults | **OK** — prevents `KeyError` when serializing artists without artwork (#2511). |
| `schemas.py` | `extra='allow'` on WebSocket messages | **OK** — preserves protocol envelope fields (#2281). Localhost-only, low security risk. |
| `middleware.py` | Explicit CORS methods/headers instead of wildcards | **OK** — security fix (#2224). |

### Library/Database

| File | Change | Risk Assessment |
|------|--------|-----------------|
| `album_repository.py` | `joinedload(Album.tracks)` → `selectinload(Album.tracks)` in 5 queries | **OK** — fixes N×M row explosion for albums with many tracks. Separate IN query is correct (#2523). |
| `artist_repository.py` | Added `selectinload(Artist.tracks, Artist.albums)` in `get_all_artists` | **OK** — fixes `DetachedInstanceError` when accessing relationships after session close (#2524). |
| `fingerprint_repository.py` | Filter placeholder fingerprints (lufs=-100.0) from completion count | **OK** — correct fix (#2506). Placeholders inflated progress percentage. |
| `track_repository.py` | `joinedload(Track.genres)` → `selectinload(Track.genres)` | **OK** — fixes N×G row explosion (#2523). |
| `models/*.py` | `except:` → `except Exception:` (4 instances) | **OK** — code quality. |

### Analysis/Fingerprint

| File | Change | Risk Assessment |
|------|--------|-----------------|
| `harmonic_sampled.py` | `as_completed()` for parallel chunk analysis; graceful failure with defaults | **OK** — correct fix (#2527). Failed chunk uses defaults instead of blocking. |
| `streaming/harmonic.py` | Reservoir sampling for pitch values (replaces tail-biased deque) | **OK** — correct fix (#2530). Uniform sampling over entire track. |
| `audio_fingerprint_analyzer.py` | `executor.shutdown(wait=True)` on KeyboardInterrupt; NaN dimension counting | **OK** — correct fixes (#2514, #2531). wait=True prevents partial writes. |
| `dsp_backend.py` | FFI input validation (empty array, sr=0, dtype coercion) | **OK** — correct fix (#2521). Prevents Rust panics. |

### Security / Vendor

| File | Change | Risk Assessment |
|------|--------|-----------------|
| `fingerprint_server.rs` | `0.0.0.0:8766` → `127.0.0.1:8766` | **OK** — correct security fix (#2243). No authentication on this endpoint. |
| `requirements.txt` | Pinned all dependency versions | **OK** — reproducible installs (#2414). |

### Frontend (summary)

| Area | Changes | Risk Assessment |
|------|---------|-----------------|
| Hooks | `usePlaybackState` excludes `position_changed` to prevent 10Hz re-renders; `usePlayEnhanced` refactored; `useReduxState` memoizes O(n) queue computations | **OK** — verified `position_changed` is handled by dedicated `usePlaybackPosition()` hook. |
| Components | `TrackRow` drops custom memo comparator (stale closures #2540); `Player` always mounts queue panel (CSS hide); `ProgressBar`/`GlobalSearch` accessibility improvements | **OK** — TrackRow fix is correct: custom comparator ignored callback changes. |
| Types | `playlistTransformer.ts` new file for snake→camel; WebSocket types updated | **OK** — fills gap (#2505). |
| Design system | Removed deprecated `bounce` alias; tokens used for placeholder gradients | **OK** — clean removal (#2233, #2551). |

## 3. Findings

---

### INC-01: Album search calls removed `/api/library/albums` endpoint
- **Severity**: HIGH
- **Changed File**: `auralis-web/backend/routers/library.py` (commit: `4e3aa8b7`)
- **Status**: NEW
- **Description**: Batch 21 removed the `GET /api/library/albums` endpoint (duplicate of `GET /api/albums`, fixes #2509), but the frontend `useSearchLogic.ts:92` still calls `fetch('/api/library/albums')` directly. Additionally, `config/api.ts:59` still defines `LIBRARY_ALBUMS: '/api/library/albums'`. The removal breaks the search-by-album functionality.
- **Evidence**:
  ```typescript
  // useSearchLogic.ts:92 — calls REMOVED endpoint
  const albumsResponse = await fetch('/api/library/albums');
  ```
  ```typescript
  // config/api.ts:59 — stale constant
  LIBRARY_ALBUMS: '/api/library/albums',
  ```
  Backend removal:
  ```python
  # routers/library.py — endpoint removed
  # Removed: GET /api/library/albums — dead endpoint, duplicate of GET /api/albums (fixes #2509)
  ```
- **Impact**: Album results silently disappear from search. `albumsResponse.ok` returns `false` (404), so the code gracefully skips albums — no crash, but incomplete search results.
- **Suggested Fix**: Update `useSearchLogic.ts` to use `/api/albums` instead of `/api/library/albums`. Update `config/api.ts` to point `LIBRARY_ALBUMS` to `/api/albums`. Update test mocks in `handlers.ts:195`.

---

### INC-02: TOCTOU in gapless prebuffer validation
- **Severity**: MEDIUM
- **Changed File**: `auralis/player/gapless_playback_engine.py` (commit: `d2fe8f97`)
- **Status**: NEW
- **Description**: The prebuffer validation fix (#2303) reads `audio_data` via `get_prebuffered_track()` (which acquires `update_lock`), then reads `next_track_info` in a separate `with self.update_lock:` block. Between these two lock acquisitions, `invalidate_prebuffer()` — now called from `set_shuffle()` and `set_repeat()` (fix #2154 in the same batch) — can clear or replace the prebuffer state. This creates a window where `audio_data` belongs to track A but `prebuffered_info` belongs to track B (or is None).
- **Evidence**:
  ```python
  # gapless_playback_engine.py:219-222 — TWO separate lock acquisitions
  audio_data, sample_rate = self.get_prebuffered_track()  # Lock #1

  with self.update_lock:                                   # Lock #2
      prebuffered_info = self.next_track_info
  ```
  Between Lock #1 and Lock #2, `invalidate_prebuffer()` can run from another thread (e.g., user toggles shuffle), clearing `next_track_info` while `audio_data` still holds the old prebuffered audio.
- **Impact**: In the worst case, a gapless transition could play the wrong track's audio (audio_data from old prebuffer, validated against info from new prebuffer). Practical risk is very low (microsecond window, requires exact timing of shuffle toggle during track transition), but the pattern is incorrect.
- **Suggested Fix**: Read both `audio_data` and `next_track_info` in a single lock acquisition. Either extend `get_prebuffered_track()` to return `(audio_data, sample_rate, track_info)`, or combine the reads into one `with self.update_lock:` block.

---

### INC-03: WebM streaming LRU cache has no file-change invalidation
- **Severity**: LOW
- **Changed File**: `auralis-web/backend/routers/webm_streaming.py` (commit: `78b0e861`)
- **Status**: NEW
- **Description**: The new `_load_audio_cached` LRU cache (fixes #2295) caches decoded audio by filepath with no TTL, mtime check, or manual invalidation. If a user re-imports or re-encodes a file at the same path, the cache serves stale audio until LRU eviction or process restart. The read-only flag (`audio.flags.writeable = False`) is correctly applied to prevent mutation of cached data.
- **Evidence**:
  ```python
  # webm_streaming.py:624-633
  @lru_cache(maxsize=8)
  def _load_audio_cached(filepath: str):
      audio, sr = load_audio(filepath)
      audio.flags.writeable = False  # Correct: prevent mutation
      return audio, sr
  # No mtime check, no TTL, no invalidation hook
  ```
- **Impact**: Stale audio served after file replacement. Low severity because: (1) file replacement is rare for a music library, (2) cache is small (8 entries), (3) process restart clears cache.
- **Suggested Fix**: Include `os.path.getmtime(filepath)` in the cache key, or wrap with a custom cache that checks mtime before returning cached entries.

---

### INC-04: Test mocks and config reference removed/renamed endpoints
- **Severity**: LOW
- **Changed File**: Multiple frontend test/config files (not updated in this batch)
- **Status**: NEW
- **Description**: Several frontend files reference the removed `GET /api/library/albums` endpoint or the renamed `artwork_path` response field:
  - `config/api.ts:59` defines `LIBRARY_ALBUMS: '/api/library/albums'`
  - `test/mocks/handlers.ts:195` mocks the removed endpoint
  - `test/mocks/handlers.ts:685` returns `artwork_path` (backend now returns `artwork_url`)
  - `test/mocks/api.ts:150,161` uses `artwork_path`
  - `test/mocks/mockData.ts:30` uses `artwork_path`
  - `tests/integration/error-handling/error-handling.test.tsx:70` includes `/api/library/albums?limit=10`
- **Impact**: Test mocks are stale but don't cause test failures (mocks still work, they just don't match the real backend). Could mask real integration issues in tests.
- **Suggested Fix**: Update all references to match the current backend contract: `LIBRARY_ALBUMS` → `/api/albums`, `artwork_path` → `artwork_url`.

---

## 4. Cross-Layer Impact

| Change | Sender | Receiver | Status |
|--------|--------|----------|--------|
| Removed `GET /api/library/albums` | Backend | Frontend search | **BROKEN** (INC-01) |
| `artwork_path` → `artwork_url` in extract response | Backend | Frontend (if used) | **Stale mocks** (INC-04), production frontend appears to not read this field |
| `position_changed` lightweight broadcast | Backend | Frontend | **OK** — frontend `usePlaybackPosition` handles this message type |
| `enhancement_settings_changed` on WS connect | Backend | Frontend | **OK** — frontend handles this message type |
| `crossfade_samples=0` in PCM chunk | Backend | Frontend | **OK** — prevents double crossfade |
| Flattened stereo PCM frames | Backend | Frontend | **OK** — frames now correctly sized below 1MB limit |
| `extra='allow'` on WS messages | Backend schema | WS clients | **OK** — preserves envelope fields |
| Pinned dependency versions | `requirements.txt` | Build system | **OK** — reproducible builds |

## 5. Missing Tests

| Change | Test Coverage |
|--------|--------------|
| Prebuffer invalidation on shuffle/repeat toggle (#2154) | No test for shuffle-during-transition race |
| `validate_audio_finite(repair=False)` fail-fast (#2520) | No test that NaN in DSP output raises instead of being silently replaced |
| `_load_audio_cached` read-only cache (#2295) | No test that cached array mutation raises ValueError |
| Upload magic-byte validation (#2560) | No test for rejected non-audio uploads |
| HPSS/YIN/Chroma FFI input validation (#2521) | No test for empty array or sr=0 at Rust boundary |
| +6.02 dB window compensation (#2518) | No test that analysis magnitudes align with synthesis |

## Summary

| Finding | Severity | Action |
|---------|----------|--------|
| INC-01: Album search calls removed endpoint | HIGH | CREATE |
| INC-02: TOCTOU in gapless prebuffer validation | MEDIUM | CREATE |
| INC-03: WebM LRU cache no file-change invalidation | LOW | CREATE |
| INC-04: Test mocks reference removed/renamed endpoints | LOW | CREATE |

**Overall assessment**: The batch fixes are well-constructed and address real issues. The biggest concern is the cross-layer contract break (INC-01) where a backend endpoint removal wasn't coordinated with the frontend. The TOCTOU (INC-02) was inadvertently introduced by combining two correct fixes (#2303 prebuffer validation + #2154 shuffle invalidation) that interact unsafely.
