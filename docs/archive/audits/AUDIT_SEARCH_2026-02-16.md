# Comprehensive Auralis Audit — 2026-02-16

## Executive Summary

Full 10-dimension audit of the Auralis music player codebase. Covered Audio Integrity, DSP Pipeline, Player State, Backend API/WebSocket, Frontend State, Library/Database, Security, Concurrency, Error Handling, and Test Coverage.

**Findings by severity:**

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 8 |
| MEDIUM   | 17 |
| LOW      | 10 |
| **Total NEW** | **35** |

Plus 4 existing issues verified/extended: #2189 (confirmed), #2230 (4 remaining sync call sites), #2236 (confirmed NOT fixed), #2240 (extends to SettingsRepository/GenreRepository).

**Key themes:**
1. **Player position safety** — Gapless transition doesn't reset position; `position` setter bypasses RLock
2. **Frontend reference instability** — `useRestAPI` produces new object references on every request, causing infinite re-fetch loops
3. **Raw SQL bypassing repository pattern** — FingerprintRepository and FingerprintExtractor use direct sqlite3 connections
4. **Async/sync boundary violations** — Multiple async handlers call synchronous file I/O
5. **Test coverage gaps** — AudioFileManager, QueueController, ArtworkService have zero tests

**Recent fixes verified as correct:** #2197 (GaplessPlaybackEngine deadlock), #2198 (PlaybackController RLock), #2153 (position read-modify-write), #2199 (state setter bypass), order_by whitelisting (aba78151), mastering path validation (7cff7339).

---

## Findings

### HIGH Severity

---

### AS-01: Gapless transition does not reset playback position to zero

- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:171-186`, `auralis/player/enhanced_audio_player.py:269-277`
- **Status**: NEW
- **Description**: `advance_with_prebuffer()` sets `file_manager.audio_data` to the new track's audio but never resets `PlaybackController.position` to 0. After transition, the stale position from the previous track causes `get_audio_chunk()` to read beyond the new track's length, producing silence.
- **Evidence**:
  ```python
  # gapless_playback_engine.py:175-179
  with self.update_lock:
      self.file_manager.audio_data = audio_data    # New track data
      self.file_manager.sample_rate = sample_rate
      self.file_manager.current_file = file_path
      # NO position reset!
  ```
  The non-gapless path calls `self.playback.stop()` which resets position to 0, but the gapless path calls `self.playback.play()` which does not.
- **Impact**: After every gapless track transition, playback produces silence. Defeats the purpose of gapless playback.
- **Related**: #2152 (position on sample rate change — distinct: this affects ALL gapless transitions)
- **Suggested Fix**: Add `self.playback.position = 0` (or better, `self.playback.seek(0, ...)`) inside the `with self.update_lock:` block after setting audio_data.

---

### AS-02: useEnhancementControl infinite re-fetch loop via unstable `api` dependency

- **Severity**: HIGH
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:154-174`
- **Status**: NEW
- **Description**: The `useEffect` at line 154 has `[api]` as its dependency, where `api` comes from `useRestAPI()`. Every API call toggles `isLoading`, producing a new `api` reference, re-triggering the effect, creating an infinite HTTP request loop to `/api/player/enhancement/status`.
- **Evidence**:
  ```typescript
  useEffect(() => {
    const fetchInitialState = async () => {
      const response = await api.get<EnhancementState>('/api/player/enhancement/status');
      // ...
    };
    fetchInitialState();
  }, [api]);  // api reference changes on every isLoading toggle
  ```
- **Impact**: Continuous HTTP requests as long as the component is mounted. Dozens of requests per second limited only by network latency.
- **Related**: AS-03 (root cause)
- **Suggested Fix**: Remove `api` from deps, use `useRef` for api methods, or destructure stable method references.

---

### AS-03: useRestAPI useMemo reference instability (root cause of AS-02)

- **Severity**: HIGH
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:257-268`
- **Status**: NEW
- **Description**: `useRestAPI` returns its object through `useMemo` with `isLoading` and `error` in the dependency array. Since `isLoading` toggles on every request, the returned object changes at least twice per API call. All 11 files importing `useRestAPI` are potentially affected.
- **Evidence**:
  ```typescript
  return useMemo(
    () => ({ get, post, put, patch, delete: delete_, clearError, isLoading, error }),
    [get, post, put, patch, delete_, clearError, isLoading, error]
    //                                           ^^^^^^^^^  ^^^^^ change per request
  );
  ```
- **Impact**: Cascading re-renders across the application. Any hook using `api` as a dependency re-executes on every API call.
- **Suggested Fix**: Split into stable methods `useMemo` (no `isLoading`/`error`) and separate reactive state.

---

### AS-04: FingerprintRepository.upsert() SQL injection via f-string column names

- **Severity**: HIGH
- **Dimension**: Security
- **Location**: `auralis/library/repositories/fingerprint_repository.py:486-494`
- **Status**: NEW
- **Description**: The `upsert()` method constructs raw SQL using f-string interpolation of dictionary keys. Column names are inserted directly into the SQL string without sanitization. The same pattern exists in `store_fingerprint()` at lines 562-573.
- **Evidence**:
  ```python
  cols = list(fingerprint_data.keys())
  cols_str = ', '.join(cols)
  sql = f"INSERT OR REPLACE INTO track_fingerprints (track_id, {cols_str}) VALUES (?, {placeholders})"
  ```
- **Impact**: SQL injection if caller passes unsanitized dictionary keys. Defense-in-depth violation.
- **Suggested Fix**: Whitelist column names against `TrackFingerprint.__table__.columns.keys()`.

---

### AS-05: AudioPlayer.position setter bypasses PlaybackController._lock

- **Severity**: HIGH
- **Dimension**: Concurrency
- **Location**: `auralis/player/enhanced_audio_player.py:492-495`
- **Status**: NEW
- **Description**: The `position` property setter writes directly to `self.playback.position` without acquiring `self.playback._lock`. This undermines the RLock protection added in #2198/#2153.
- **Evidence**:
  ```python
  @position.setter
  def position(self, value: int) -> None:
      self.playback.position = value  # No lock!
  ```
- **Impact**: Partially undermines #2153 fix. Legacy code using `player.position = X` races with the playback loop.
- **Suggested Fix**: Delegate to `self.playback.seek(value, max_samples)` which acquires the lock.

---

### AS-06: FingerprintExtractor._delete_corrupted_track uses raw SQL DELETE, bypasses repository pattern

- **Severity**: HIGH
- **Dimension**: Error Handling
- **Location**: `auralis/services/fingerprint_extractor.py:219-265`
- **Status**: NEW
- **Description**: Opens a direct `sqlite3.connect()` to hardcoded database paths and executes `DELETE FROM tracks WHERE id = ?`. Bypasses SQLAlchemy session management, connection pooling, and cascading delete constraints.
- **Evidence**:
  ```python
  conn = sqlite3.connect(db_path)
  cursor.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
  ```
  The hardcoded path guessing (lines 236-241) may target the wrong database.
- **Impact**: Orphaned fingerprints, playlist entries, and stats for deleted tracks. May delete from wrong database.
- **Suggested Fix**: Use `repository_factory.tracks.delete()` via the existing DI pattern.

---

### AS-07: AudioFileManager has zero dedicated unit tests

- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: No test file for `auralis/player/audio_file_manager.py`
- **Status**: NEW
- **Description**: AudioFileManager handles loading audio files, providing chunks for playback, stereo conversion, and padding. It has no dedicated tests. Only referenced in `conftest.py` as a fixture.
- **Impact**: Core audio I/O layer for the player has no direct test coverage.
- **Suggested Fix**: Create `tests/auralis/player/test_audio_file_manager.py` covering load_file, get_audio_chunk boundaries, mono-to-stereo, and padding.

---

### AS-08: QueueController has no dedicated test file

- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: No test file for `auralis/player/queue_controller.py`
- **Status**: NEW
- **Description**: QueueController manages track navigation, shuffle, repeat, and playlist loading. No dedicated tests. Critical functionality like `load_playlist()`, `reorder_tracks()`, and `set_queue()` have no coverage.
- **Impact**: Queue navigation bugs (off-by-one, shuffle, repeat) would not be caught.
- **Suggested Fix**: Create `tests/auralis/player/test_queue_controller.py`.

---

### MEDIUM Severity

---

### AS-09: _notify_callbacks invoked while holding RLock — fragile callback-under-lock

- **Severity**: MEDIUM
- **Dimension**: Player State / Concurrency
- **Location**: `auralis/player/playback_controller.py:73,87,104,142,153,159`
- **Status**: NEW
- **Description**: All state-change methods call `_notify_callbacks()` while holding `_lock`. Callbacks execute arbitrary code with the lock held, blocking all state transitions. `IntegrationManager._on_playback_state_change` calls back into PlaybackController methods (safe due to RLock reentrance, but fragile).
- **Impact**: Slow callbacks block all playback state transitions. Future callbacks dispatching to other threads risk deadlock.
- **Suggested Fix**: Release lock before invoking callbacks, or copy state and notify after lock release.

---

### AS-10: SimpleMastering transpose heuristic fails for short stereo audio

- **Severity**: MEDIUM
- **Dimension**: Audio Integrity / DSP Pipeline
- **Location**: `auralis/core/simple_mastering.py:174-175,222-223`
- **Status**: NEW
- **Description**: Uses `chunk.shape[0] > chunk.shape[1]` to detect `(samples, channels)` vs `(channels, samples)`. Fails for 2-sample stereo audio where shape is `(2, 2)` — produces wrong result for square arrays.
- **Impact**: Corrupted audio for very short files or edge-case last chunks.
- **Suggested Fix**: Use `chunk.shape[-1] <= 2` or check against expected channel count.

---

### AS-11: BrickWallLimiter sample-by-sample Python loop — O(n × lookahead) performance

- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline / Performance
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:107-132`
- **Status**: NEW
- **Description**: `process()` uses `for i in range(num_samples)` with per-sample `np.max(np.abs(lookahead_window))`. For 44100 samples this is extremely slow (100-500ms per second of audio).
- **Impact**: Consistently blows CPU budget in HybridProcessor adaptive/hybrid modes, triggering PerformanceMonitor degradation.
- **Suggested Fix**: Vectorize with `scipy.ndimage.maximum_filter1d` or NumPy sliding window.

---

### AS-12: AudioContext resource leak in usePlayEnhanced

- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:263-273,752-758`
- **Status**: NEW
- **Description**: Creates `AudioContext` at line 272 but cleanup effect at line 752-758 never calls `audioContextRef.current.close()`. Browsers limit concurrent AudioContexts (Chrome: 6 per tab).
- **Impact**: After 6 mount/unmount cycles, audio playback fails silently.
- **Suggested Fix**: Add `audioContextRef.current?.close()` to cleanup effect.

---

### AS-13: webm_streaming loads entire audio file per chunk request

- **Severity**: MEDIUM
- **Dimension**: Backend API / Performance
- **Location**: `auralis-web/backend/routers/webm_streaming.py:377-415`
- **Status**: NEW
- **Description**: `_get_original_wav_chunk` calls `load_audio(filepath)` for every chunk request, loading the entire file (~100MB for 5-min stereo) just to extract ~3.5MB.
- **Impact**: 10x memory usage for a 10-chunk song. 3 concurrent unenhanced listeners = ~1GB transient allocation.
- **Suggested Fix**: Cache loaded audio per filepath with LRU eviction, or use seek-based reading.

---

### AS-14: Fire-and-forget asyncio tasks without exception handling

- **Severity**: MEDIUM
- **Dimension**: Backend API / Error Handling
- **Location**: `auralis-web/backend/routers/files.py:165`, `auralis-web/backend/routers/enhancement.py:155`
- **Status**: NEW
- **Description**: `asyncio.create_task()` called without storing the task reference. Task exceptions are logged as "never retrieved" warnings. Task objects are eligible for GC which could cancel them.
- **Impact**: Background task failures go unnoticed. Scans may fail silently. Chunk pre-caching failures degrade latency.
- **Suggested Fix**: Store task references and add `done_callback` for exception logging.

---

### AS-15: FingerprintRepository bypasses SQLAlchemy with hardcoded DB path

- **Severity**: MEDIUM
- **Dimension**: Library/Database
- **Location**: `auralis/library/repositories/fingerprint_repository.py:478-498,554-581,599-626`
- **Status**: NEW
- **Description**: Three methods (`upsert`, `store_fingerprint`, `update_status`) open direct `sqlite3` connections to hardcoded `Path.home() / '.auralis' / 'library.db'`. Bypasses WAL mode settings, pool limits, and transaction isolation.
- **Impact**: Silent data loss if DB is at non-default path. WAL contention with SQLAlchemy pool.
- **Suggested Fix**: Use `self.session_factory()` or derive DB path from engine URL.

---

### AS-16: Track.filepath exposed to all API clients

- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis/library/models/core.py:118`, `auralis-web/backend/routers/serializers.py:21`
- **Status**: NEW (distinct from #2270 which covers Album.artwork_path)
- **Description**: `Track.to_dict()` includes `filepath` in output. `DEFAULT_TRACK_FIELDS` includes `filepath`. All track serialization exposes full server-side filesystem paths.
- **Impact**: Reveals directory structure, usernames, OS details. Can be used for targeted path traversal attacks.
- **Suggested Fix**: Remove `filepath` from `DEFAULT_TRACK_FIELDS` and `to_dict()`, or replace with a safe identifier.

---

### AS-17: Metadata router reads/writes DB-stored path without re-validation

- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/metadata.py:116-128`
- **Status**: NEW
- **Description**: Metadata endpoints retrieve `track.filepath` from database and pass it directly to `MetadataEditor.read_metadata()` and `write_metadata()` without path validation. If a malicious filepath was stored, these endpoints become file read/write primitives.
- **Impact**: Combined with any path-storage vulnerability, enables arbitrary file read/write via metadata API.
- **Suggested Fix**: Validate DB-retrieved filepaths with `validate_file_path()` before I/O.

---

### AS-18: start_prebuffering() has TOCTOU race — can spawn duplicate threads

- **Severity**: MEDIUM
- **Dimension**: Concurrency
- **Location**: `auralis/player/gapless_playback_engine.py:63-83`
- **Status**: NEW
- **Description**: Checks `self.prebuffer_thread.is_alive()` then creates/starts a new thread without locking. Two concurrent callers can both pass the check and start duplicate prebuffer threads.
- **Impact**: Two concurrent prebuffer workers may overwrite each other's buffer, causing playback of the wrong track.
- **Suggested Fix**: Protect the check-and-start with `self.update_lock`.

---

### AS-19: ProcessingEngine.active_jobs counter lacks synchronization

- **Severity**: MEDIUM
- **Dimension**: Concurrency
- **Location**: `auralis-web/backend/processing_engine.py:97,356,434,444`
- **Status**: NEW
- **Description**: `active_jobs` integer incremented/decremented without lock or atomic operation. While currently in asyncio single-threaded context, refactoring to use threads would introduce a race.
- **Impact**: Job concurrency limiter could allow more concurrent jobs than `max_concurrent_jobs`.
- **Suggested Fix**: Use `asyncio.Semaphore` instead of counter polling.

---

### AS-20: get_mastering_recommendation blocks event loop with sync I/O

- **Severity**: MEDIUM
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/routers/enhancement.py:355-368`
- **Status**: NEW
- **Description**: `async def` handler creates `ChunkedAudioProcessor` synchronously at line 362. The constructor loads audio and performs DSP analysis, blocking the event loop for seconds.
- **Impact**: All concurrent requests and WebSocket messages stall during analysis.
- **Suggested Fix**: Wrap in `asyncio.to_thread()`.

---

### AS-21: Prebuffered track not validated against expected queue track

- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis/player/gapless_playback_engine.py:146-196`
- **Status**: NEW
- **Description**: `advance_with_prebuffer()` gets next track from queue and prebuffered audio separately, never verifying they match. If queue was modified after prebuffering started (reorder, shuffle toggle), the prebuffered audio is for the wrong track.
- **Impact**: User hears wrong track during gapless transition if queue was modified.
- **Suggested Fix**: Compare `next_track_info` against `next_track` before using prebuffered audio.

---

### AS-22: IntegrationManager has no dedicated test file

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: No test file for `auralis/player/integration_manager.py`
- **Status**: NEW
- **Description**: Coordinates library integration, auto-reference selection, and callback coordination. No tests.
- **Suggested Fix**: Create `tests/auralis/player/test_integration_manager.py`.

---

### AS-23: ArtworkService has zero test coverage

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: No test file for `auralis/services/artwork_service.py`
- **Status**: NEW
- **Description**: Makes HTTP requests to MusicBrainz, Discogs, and Last.fm. No tests, no HTTP mocking.
- **Suggested Fix**: Create tests with mocked HTTP responses.

---

### AS-24: AudioStreamController streaming lifecycle untested

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_audio_stream_crossfade.py`
- **Status**: NEW
- **Description**: Existing tests only cover `_apply_boundary_crossfade()` helper. The actual streaming methods (`stream_enhanced_audio`, `stream_normal_audio`) are untested end-to-end.
- **Impact**: The primary audio streaming feature has minimal test coverage.
- **Suggested Fix**: Add end-to-end tests for streaming methods with mocked WebSocket.

---

### AS-25: FingerprintExtractionQueue worker lifecycle untested

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: No tests for `auralis/services/fingerprint_queue.py` worker loop
- **Status**: NEW
- **Description**: Worker loop, graceful shutdown, adaptive resource scaling, and semaphore concurrency are untested.
- **Related**: #2247 (non-daemon threads preventing shutdown)
- **Suggested Fix**: Create lifecycle tests for start/stop/graceful-shutdown.

---

### LOW Severity

---

### AS-26: Output normalization only normalizes UP, never reduces hot peaks

- **Severity**: LOW
- **Dimension**: Audio Integrity
- **Location**: `auralis/core/simple_mastering.py:330`
- **Status**: NEW
- **Description**: Normalization only activates when `current_peak < output_target` (0.95). Hot material above 0.95 is not reduced, creating inconsistent output levels between tracks.
- **Suggested Fix**: Apply bidirectional normalization to output_target.

---

### AS-27: PlaybackController.add_callback is not thread-safe

- **Severity**: LOW
- **Dimension**: Concurrency
- **Location**: `auralis/player/playback_controller.py:44-46`
- **Status**: NEW
- **Description**: `add_callback` appends to list without lock. `_notify_callbacks` iterates under lock. Concurrent modification raises `RuntimeError: list changed size during iteration`.
- **Suggested Fix**: Acquire `_lock` in `add_callback`.

---

### AS-28: AutoMasterProcessor uses pre-compression peak for gain reduction

- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/player/realtime/auto_master.py:162`
- **Status**: NEW
- **Description**: Hot-input gain reduction uses `input_peak` from original audio, not post-compression `processed` array. Creates incorrect gain scaling.
- **Suggested Fix**: Compute peak from `processed` array after compression.

---

### AS-29: library.py bare except clause silently swallows all exceptions

- **Severity**: LOW
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/routers/library.py:274`
- **Status**: NEW
- **Description**: `except:` catches everything including `SystemExit` and `KeyboardInterrupt` during lyrics extraction.
- **Suggested Fix**: Replace with `except Exception:`.

---

### AS-30: system.py variable name `data` shadowed in WebSocket handler

- **Severity**: LOW
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/routers/system.py:111,154`
- **Status**: NEW
- **Description**: Outer `data` (raw JSON string) shadowed by inner `data = message.get("data", {})` (parsed dict).
- **Suggested Fix**: Rename inner variable to `payload`.

---

### AS-31: MigrationManager _record_migration no rollback on commit failure

- **Severity**: LOW
- **Dimension**: Library/Database
- **Location**: `auralis/library/migration_manager.py:165-172`
- **Status**: NEW
- **Description**: `session.commit()` in `_record_migration` has no error handling. Failure leaves session in inconsistent state and DB partially migrated.
- **Suggested Fix**: Wrap in try/except with rollback.

---

### AS-32: Module-level processor caches lack thread safety

- **Severity**: LOW
- **Dimension**: Concurrency
- **Location**: `auralis/core/hybrid_processor.py:474-500`, `auralis/optimization/parallel_processor.py:436-444`
- **Status**: NEW
- **Description**: `_processor_cache` dict and `_global_parallel_processor` singleton accessed without locks. TOCTOU in check-then-set pattern.
- **Impact**: Duplicate expensive instances created. Not a correctness bug, wastes memory.
- **Suggested Fix**: Add `threading.Lock` for cache access.

---

### AS-33: AudioStreamController._stream_type assumes per-request instantiation

- **Severity**: LOW
- **Dimension**: Concurrency
- **Location**: `auralis-web/backend/audio_stream_controller.py:148,394,552`
- **Status**: NEW
- **Description**: Instance field `_stream_type` set per-stream call. Currently safe (new controller per request) but fragile if controller is shared.
- **Suggested Fix**: Pass `stream_type` as parameter instead of instance state.

---

### AS-34: _load_audio_placeholder returns random noise, is reachable in production

- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis/core/hybrid_processor.py:359-363`
- **Status**: NEW
- **Description**: Returns `np.random.randn(44100 * 5, 2) * 0.1` (5 seconds of random noise). Reachable if `process()` is called with a file path string.
- **Suggested Fix**: Raise `NotImplementedError` or remove the placeholder.

---

## Existing Issues Verified/Extended

| Issue | Status | Notes |
|-------|--------|-------|
| #2189 | Confirmed | `asyncio.create_task` from worker thread in startup.py:87 still present |
| #2230 | Partial fix | Only 1 of 5 metadata.py sync I/O calls wrapped in `asyncio.to_thread`. 4 remaining at lines 161, 212, 240, 303 |
| #2236 | NOT fixed | Player `load_track` and `add_to_queue` still accept unvalidated paths |
| #2240 | Extends | SettingsRepository and GenreRepository also have unconstrained setattr |

## Recent Fixes Verified as Correct

- **#2197** (GaplessPlaybackEngine deadlock): Inlined check, Lock (not RLock) is correct since no nested locking
- **#2198** (PlaybackController RLock): All state methods properly guarded
- **#2153** (Position read-modify-write): `read_and_advance_position()` is atomic under RLock
- **#2199** (State setter bypass): `AudioPlayer.state` property is now read-only
- **aba78151** (Order_by whitelisting): Comprehensive across all repositories
- **7cff7339** (Mastering filepath validation): Correct for enhancement.py:351

## Relationships & Clusters

### Cluster 1: Player Position Safety
AS-01 (gapless position reset) + AS-05 (position setter bypasses lock) + #2153 (position race fix). The position setter at AS-05 partially undermines the #2153 fix. AS-01 is an independent bug that causes silence after gapless transitions.

### Cluster 2: Frontend Reference Instability
AS-02 (infinite re-fetch) + AS-03 (root cause). Fix AS-03 in `useRestAPI` and AS-02 is automatically resolved. All 11 `useRestAPI` consumers benefit.

### Cluster 3: Raw SQL / Repository Bypass
AS-04 (SQL injection) + AS-06 (raw DELETE) + AS-15 (hardcoded DB path). Three separate locations bypass the repository pattern with direct sqlite3. Root cause: these were written before the repository pattern was established.

### Cluster 4: Async/Sync Boundary
AS-20 (mastering blocks loop) + #2230 partial (metadata sync I/O) + #2189 (create_task from thread). Inconsistent patterns — some handlers correctly use `asyncio.to_thread`, adjacent code doesn't.

### Cluster 5: Security — Path Exposure
AS-16 (Track.filepath exposed) + AS-17 (metadata path not re-validated) + #2236 (player paths unvalidated). Full chain: paths stored in DB → exposed to API → accepted back without validation.

### Cluster 6: Test Coverage Gaps
AS-07, AS-08, AS-22, AS-23, AS-24, AS-25. Core player components (AudioFileManager, QueueController, IntegrationManager) and primary streaming path lack dedicated tests.

## Prioritized Fix Order

1. **AS-03** (useRestAPI instability) — Fixes AS-02 automatically, affects all frontend API consumers
2. **AS-01** (gapless position reset) — One-line fix, restores gapless playback
3. **AS-05** (position setter bypass) — Restores full thread safety from #2153
4. **AS-04** (SQL injection) — Security: whitelist column names
5. **AS-06** (raw SQL DELETE) — Replace with repository call
6. **AS-15** (hardcoded DB path) — Use session_factory
7. **AS-12** (AudioContext leak) — One-line fix in cleanup effect
8. **AS-16 + AS-17** (path exposure) — Remove filepath from API responses, validate DB paths
9. **AS-11** (BrickWallLimiter) — Vectorize for real-time viability
10. **AS-09** (callbacks under lock) — Release lock before notifying

## Cross-Cutting Recommendations

1. **Repository enforcement**: Add a CI lint rule that flags `sqlite3.connect` anywhere outside migration code
2. **Async boundary lint**: Flag synchronous file I/O (`open()`, `read_metadata()`, `load_audio()`) inside `async def` handlers
3. **Frontend API hook**: Split `useRestAPI` return into stable methods + reactive state
4. **Path security**: Apply `validate_file_path()` to all endpoints accepting file paths, and to DB-retrieved paths before I/O
5. **Test coverage**: Prioritize AudioFileManager, QueueController, and AudioStreamController streaming lifecycle
