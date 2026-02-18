# Comprehensive Audit — 2026-02-17

## Executive Summary

**25 new findings** across all 10 audit dimensions. No findings regressed existing fixes.

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 9 |
| MEDIUM | 11 |
| LOW | 4 |

**Key themes:**
1. **Audio integrity failures in the DSP pipeline** — double Hanning window in VectorizedEQ, BrickWallLimiter dropping cross-chunk gain state, and EQ frequency asymmetry all produce audible artifacts on every processed track.
2. **Event loop blocking** — `process_chunk_safe` runs 5–30s of CPU-bound DSP synchronously on the asyncio event loop, freezing all WebSocket and HTTP activity during each audio chunk.
3. **Data loss on file upload** — The upload handler stores the temp file path in the database then unconditionally deletes the temp file, making every uploaded track immediately unplayable.
4. **Missing test coverage for critical paths** — 72% of chunked processor tests are permanently skipped; no event-loop-responsiveness test exists for the blocking call.

**Skipped (extend existing open issues):**
- `process_chunk_safe` mastering recommendation endpoint → extends #2301
- Gapless prebuffered path skips position reset → extends #2283
- `GET /api/metadata` sync I/O → extends #2317
- Album search fabricated total in `library.py` router → extends #2380
- `_active_streaming_tasks` module-level dict never pruned → extends #2321

---

## Findings

### S-01: `process_chunk_safe` Blocks asyncio Event Loop for Up to 30s Per Chunk
- **Severity**: CRITICAL
- **Dimension**: Concurrency / Backend API
- **Location**: `auralis-web/backend/chunked_processor.py:632-638`
- **Status**: NEW
- **Description**: `process_chunk_safe` acquires an `asyncio.Lock` then calls `self.process_chunk()` synchronously — no `asyncio.to_thread`. The code comment explicitly acknowledges this: `"While this blocks the event loop, it guarantees correctness"`. Processing a 15-second chunk runs CPU-intensive HPSS separation, EQ, and loudness normalization on the event loop thread for 5–30 seconds depending on hardware.
- **Evidence**:
  ```python
  async with self._processor_lock:
      # While this blocks the event loop, it guarantees correctness
      chunk_path, audio_array = self.process_chunk(chunk_index, fast_start)
  ```
- **Impact**: All WebSocket and HTTP activity freezes for every audio chunk. Pause/seek commands cannot be handled. Proxy or client-side WebSocket timeouts drop connections. On multi-user deployments, one user's playback blocks all others.
- **Related**: #2319 (processing_engine blocks — fixed), #2330 (enhancement router blocks)
- **Suggested Fix**: `chunk_path, audio_array = await asyncio.to_thread(self.process_chunk, chunk_index, fast_start)`. Replace the `asyncio.Lock` with `asyncio.to_thread`-compatible coordination.

---

### S-02: VectorizedEQProcessor Applies Hanning Window Before and After IFFT — Squared Attenuation Produces Audible ~11 Hz Tremolo
- **Severity**: HIGH
- **Dimension**: Audio Integrity / DSP Pipeline
- **Location**: `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:94,120`
- **Status**: NEW
- **Description**: The vectorized EQ path applies a Hanning window before the FFT (`windowed_audio = audio_mono[:fft_size] * window`) and again after the IFFT (`processed_audio *= window`). The correct FFT filtering pattern uses windows only for analysis, not for synthesis. The double application produces `w(n)^2` amplitude envelope — squared Hanning — which attenuates samples at chunk edges toward zero. Since `fft_size = 4096` at 44100 Hz, this creates amplitude modulation at `44100 / 4096 ≈ 10.8 Hz`, squarely in the audible range. `VectorizedEQProcessor` is the preferred (active) path when `VECTORIZED_EQ_AVAILABLE`.
- **Evidence**:
  ```python
  # vectorized_processor.py
  window = np.hanning(fft_size)
  windowed_audio = audio_mono[:fft_size] * window  # window applied before FFT
  spectrum = fft(windowed_audio)
  ...
  processed_audio = np.real(ifft(spectrum))
  processed_audio *= window                        # window applied AGAIN after IFFT → w^2
  ```
  Standard path in `filters.py` explicitly states: "No windowing is applied for EQ processing" and applies none.
- **Impact**: All audio processed through psychoacoustic EQ (HybridProcessor and RealtimeAdaptiveEQ) has periodic amplitude scalloping at ~11 Hz — an audible tremolo effect on every track.
- **Suggested Fix**: Remove the `processed_audio *= window` line after IFFT. Only the pre-FFT window is appropriate for overlap-add synthesis; even that may be wrong for pure EQ (not analysis).

---

### S-03: BrickWallLimiter Discards Cross-Chunk Gain State — Click at Every Chunk Boundary
- **Severity**: HIGH
- **Dimension**: Audio Integrity
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:107-133`
- **Status**: NEW
- **Description**: `self.current_gain` and the ring buffer (`self.buffer`) are initialized in `__init__` but never read or written inside `process()`. Each call reconstructs `gain_curve` from scratch, starting at `target_gain = 1.0` for sample 0 regardless of the previous chunk's ending gain. When the limiter engaged near the end of chunk N (gain suppressed to 0.5), the first sample of chunk N+1 starts at gain 1.0 — an instantaneous gain step that produces an audible click at every 30-second chunk boundary.
- **Evidence**:
  ```python
  # __init__
  self.current_gain = 1.0   # initialized but never read in process()
  self.buffer = None        # never assigned after __init__

  # process() — no reference to self.current_gain or self.buffer
  gain_curve = np.ones(num_samples)
  for i in range(num_samples):
      if i == 0:
          gain_curve[i] = target_gain   # always 1.0 regardless of previous chunk
  ```
- **Impact**: Audible click/pop at every 30-second chunk boundary when limiting is active (common on loud tracks). The ring buffer described in the docstring is dead code.
- **Suggested Fix**: At the start of `process()`, initialize `gain_curve[0]` from `self.current_gain` (the saved state). At the end, save `gain_curve[-1]` back to `self.current_gain`.

---

### S-04: `apply_eq_gains` Skips Mirror for Sub-Bass Bins in Band 0 — Hermitian Symmetry Broken, Sub-Bass Energy Lost
- **Severity**: HIGH
- **Dimension**: Audio Integrity / DSP Pipeline
- **Location**: `auralis/dsp/eq/filters.py:88-97`
- **Status**: NEW
- **Description**: When applying EQ gains, the loop skips mirroring negative-frequency bins for band 0 (`if i > 0: skip`). DC is intentionally skipped, but positive-frequency sub-bass bins (1, 2, … up to the band boundary) that belong to band 0 receive gain on their positive side but not on their negative-frequency mirror. The IFFT of this asymmetric spectrum is not purely real — `np.real()` discards the imaginary residual, silently dropping sub-bass energy.
- **Evidence**:
  ```python
  # filters.py:88-97
  for i, gain_db in enumerate(gains):
      gain_linear = 10 ** (gain_db / 20)
      band_mask = freq_to_band_map == i
      spectrum[:fft_size // 2 + 1][band_mask] *= gain_linear   # positive side
      if i > 0:    # band 0 sub-bass bins get no mirror
          spectrum[fft_size // 2 + 1:][band_mask[1:-1][::-1]] *= gain_linear
  ```
- **Impact**: Sub-bass EQ boosts or cuts (band 0 of psychoacoustic EQ) are approximately half as effective as intended. IFFT produces imaginary residuals for sub-bass content that are discarded, causing energy loss. Effect is most audible on bass-heavy material.
- **Suggested Fix**: Change the guard to `if band_mask[0] and not band_mask[1:].any(): skip` to only skip DC when band 0 is purely the DC bin. Otherwise mirror all non-DC bins in band 0.

---

### S-05: File Upload Handler Stores Temp File Path in DB Then Immediately Deletes the File
- **Severity**: HIGH
- **Dimension**: Error Handling / Library
- **Location**: `auralis-web/backend/routers/files.py:112-169`
- **Status**: NEW
- **Description**: The upload handler writes bytes to a `NamedTemporaryFile`, stores `temp_path` as the track's `filepath` in the database via `library_manager.add_track(track_info)`, then unconditionally deletes the temp file in `finally`. The committed DB record points to a path that no longer exists.
- **Evidence**:
  ```python
  with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
      tmp.write(content)
      temp_path = tmp.name                        # e.g. /tmp/tmpXYZabc.mp3

  try:
      track_info = { "filepath": temp_path, ... }
      track = library_manager.add_track(track_info)  # commits temp_path to DB
      ...
  finally:
      Path(temp_path).unlink()                    # file gone; DB record stays
  ```
- **Impact**: Every successfully uploaded track is immediately unplayable. Scanning, fingerprinting, and playback all fail with `FileNotFoundError`. The library accumulates dead records with no cleanup mechanism.
- **Suggested Fix**: Move the uploaded file to a permanent library storage directory (e.g., `~/.auralis/uploads/`) before committing the DB record. Only delete the temp file after the permanent copy is confirmed.

---

### S-06: WebSocket `play_enhanced`/`play_normal`/`seek` Accept Unvalidated/Missing `track_id`
- **Severity**: HIGH
- **Dimension**: Security / Backend API
- **Location**: `auralis-web/backend/routers/system.py:155,301,404`
- **Status**: NEW
- **Description**: All three WebSocket handlers extract `track_id` via `data.get("track_id")` with no type check or presence validation. `None`, strings, floats, and negative integers all pass through to `controller.stream_enhanced_audio(track_id=track_id, ...)`. The repository performs `tracks.get_by_id(None)`, which returns no row but not before executing a DB query with a null key.
- **Evidence**:
  ```python
  data = message.get("data", {})
  track_id = data.get("track_id")  # None if field missing; any type accepted
  task = asyncio.create_task(stream_audio())  # launched with track_id=None
  ```
- **Impact**: Malformed WebSocket messages create orphaned background tasks that log an error and exit — consuming resources and producing confusing delayed error messages. Makes client-side debugging difficult. REST endpoints validate via Pydantic `int` type; WebSocket handlers bypass this entirely.
- **Suggested Fix**: Add `if not isinstance(track_id, int) or track_id <= 0: await ws.send_json({"type": "error", ...}); return` before launching the streaming task.

---

### S-07: `setStreamingError` Dispatched with Bare String Instead of Required `{streamType, error}` Object
- **Severity**: HIGH
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:353`
- **Status**: NEW
- **Description**: `setStreamingError` requires `PayloadAction<{ streamType: StreamType; error: string }>` as defined in `playerSlice.ts:362-370`. At line 353 of `usePlayEnhanced.ts` it is dispatched with a plain string. At lines 443 and 473 the same hook correctly passes `{ streamType: 'enhanced', error: errorMsg }`. The inconsistent call at line 353 causes `action.payload.streamType` to be `undefined` in the reducer — `state.streaming[undefined]` is silently a no-op, leaving the UI in a stuck previous state with no error indication.
- **Evidence**:
  ```typescript
  // playerSlice.ts — required shape:
  setStreamingError: { reducer(state, action: PayloadAction<{ streamType: StreamType; error: string }>) { ... } }

  // usePlayEnhanced.ts:353 — wrong:
  dispatch(setStreamingError(errorMsg));  // errorMsg is string, not {streamType, error}

  // usePlayEnhanced.ts:443,473 — correct:
  dispatch(setStreamingError({ streamType: 'enhanced', error: errorMsg }));
  ```
- **Impact**: When `handleStreamStart` fails, the streaming error state is never updated. Player UI stays in the previous state (possibly "playing") with no error feedback. The user sees silence with no explanation.
- **Suggested Fix**: Change line 353 to `dispatch(setStreamingError({ streamType: 'enhanced', error: errorMsg }))`.

---

### S-08: `MigrationManager` Creates a New SQLAlchemy Engine on Every `LibraryManager` Init — Engine Never Disposed
- **Severity**: HIGH
- **Dimension**: Library/Database
- **Location**: `auralis/library/migration_manager.py` (`MigrationManager.__init__`, `close()`)
- **Status**: NEW
- **Description**: `MigrationManager.__init__` creates a SQLAlchemy `engine` via `create_engine(...)`. `close()` calls only `self.session.close()` — the engine is never disposed. A new `MigrationManager` is instantiated on every `LibraryManager.__init__` call (startup, re-init after schema check). Each leaked engine holds a connection pool with open file descriptors to the SQLite database file.
- **Evidence**:
  ```python
  class MigrationManager:
      def __init__(self, db_path: str):
          self.engine = create_engine(...)  # new engine, never disposed
          self.session = sessionmaker(bind=self.engine)()

      def close(self) -> None:
          self.session.close()   # only closes session, not engine
  ```
- **Impact**: File descriptor leak on every server restart and every `LibraryManager` re-creation. Under frequent restarts or CI test runs (where `LibraryManager` is created many times), this exhausts OS file descriptor limits.
- **Suggested Fix**: Add `self.engine.dispose()` to `close()`. Or use a context manager pattern that guarantees disposal.

---

### S-09: `useWebSocketSubscription` Silently No-ops When `globalWebSocketManager` Is Null — Player UI Freezes
- **Severity**: HIGH
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts:61-68`
- **Status**: NEW
- **Description**: The legacy `useWebSocketSubscription` hook returns early without subscribing if `globalWebSocketManager` is null. `usePlaybackState` uses this hook for all player state updates (`player_state`, `playback_started`, `playback_paused`, etc.). If the global manager is not set before components mount (startup race condition, or when using `WebSocketContext` path without setting the global), all player state updates are silently dropped.
- **Evidence**:
  ```typescript
  const manager = getWebSocketManager();
  if (!manager) {
      // Silently return - this hook is legacy code
      return;
  }
  ```
  `usePlaybackState` subscribes to all core player events via this hook. If `manager` is null, the player bar never updates position, play state, or current track.
- **Impact**: Player UI permanently frozen at initial state. No error is thrown or logged. The failure is intermittent and startup-order-dependent, making it difficult to reproduce.
- **Suggested Fix**: Either ensure `globalWebSocketManager` is always set before any component using `usePlaybackState` mounts (documented startup contract), or migrate `usePlaybackState` to use `useWebSocketContext` exclusively.

---

### S-10: 72% of `test_chunked_processor.py` Permanently Skipped — Zero Unit Coverage of `process_chunk_safe`
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_chunked_processor.py:63,80,96,114,...` (13 of 18 tests)
- **Status**: NEW
- **Description**: 13 of 18 tests carry `@pytest.mark.skip(reason="Mock pattern doesn't properly intercept _load_metadata - covered by integration tests")`. The integration tests they reference require real audio files absent from the repo and are themselves conditionally skipped. The 5 remaining tests only check module-level constants and crossfade math. `process_chunk_safe`, `_get_cache_key`, `_get_chunk_path`, `process_chunk`, and `_generate_file_signature` have zero unit test coverage.
- **Evidence**:
  ```python
  @pytest.mark.skip(reason="Mock pattern doesn't properly intercept _load_metadata...")
  def test_initialization_basic(self):
  ```
  13 of 18 tests decorated this way.
- **Impact**: The blocking behavior in S-01 went undetected precisely because no test can observe event loop stalls. Every change to `ChunkedAudioProcessor` is unverified in the standard test suite.
- **Suggested Fix**: Fix the mock pattern (mock at the `soundfile.read` or OS level, not at `_load_metadata`), remove the skip decorators, and restore unit test coverage.

---

### S-11: No Test Verifying `process_chunk_safe` Does Not Block the Event Loop
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `tests/backend/` (absent)
- **Status**: NEW
- **Description**: No test exercises `process_chunk_safe` concurrently with another coroutine and asserts the other coroutine makes progress. Without this test, S-01's blocking behavior is invisible to CI.
- **Evidence**: `grep -r "event.loop\|loop.responsive\|process_chunk_safe" tests/` yields zero assertions on event loop responsiveness during chunk processing.
- **Impact**: S-01 persists undetected across all refactoring cycles. Any future fix can also silently regress without a test guard.
- **Suggested Fix**: Add a test using `asyncio.gather(process_chunk_safe(...), increment_counter())` and assert the counter incremented during processing.

---

### S-12: `_handle_variable_chunk_size` Creates 1-D Zero-Pad Array for Stereo Input — `ValueError` on Assignment
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/realtime_adaptive_eq/realtime_eq.py:143-146`
- **Status**: NEW
- **Description**: When the last remainder chunk is smaller than `buffer_size`, the code creates `padded_chunk = np.zeros(self.buffer_size)` (1-D) then assigns `padded_chunk[:len(chunk)] = chunk`. If `chunk` is 2-D (stereo, shape `(N, 2)`), this assignment raises `ValueError: could not broadcast input array from shape (N,2) into shape (N,)`. The exception is caught by the outer handler which returns `audio_chunk` unprocessed — EQ silently skipped.
- **Evidence**:
  ```python
  padded_chunk = np.zeros(self.buffer_size)         # 1-D
  padded_chunk[:len(chunk)] = chunk                 # ValueError if chunk is (N, 2)
  ```
- **Suggested Fix**: `padded_chunk = np.zeros((self.buffer_size,) + chunk.shape[1:])` to match channel dimensionality.

---

### S-13: `PsychoacousticEQ.current_gains` Not Reset Between Tracks — EQ Bleeds Across Track Boundaries
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline / Player State
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:79,234-241`
- **Status**: NEW
- **Description**: `HybridProcessor` creates one `PsychoacousticEQ` instance and never calls `reset()` between tracks. `current_gains` (the EQ state used for smoothing) retains the previous track's final EQ curve. The first 5–10 seconds of each new track use EQ derived from the previous track's spectral content.
- **Evidence**:
  ```python
  # psychoacoustic_eq.py:234-241
  adaptive_gains[i] = smooth_parameter_transition(
      self.current_gains[i],   # previous track's last gain — never reset
      target_gains[i], self.settings.adaptation_speed
  )
  self.current_gains = adaptive_gains.copy()
  ```
  `enhanced_audio_player.load_file()` never calls `self.processor.psychoacoustic_eq.reset()`.
- **Impact**: Genre changes (e.g., orchestral → electronic) produce incorrect EQ on the first ~8 seconds of the new track, audible as too-bright or too-dark coloration at track start.
- **Suggested Fix**: Call `psychoacoustic_eq.reset()` and `realtime_eq.reset()` inside `load_file()` or at the start of each track's processing run.

---

### S-14: `RealtimeAdaptiveEQ` Returns Silence (Not Passthrough) on Buffer Underrun
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/realtime_adaptive_eq/realtime_eq.py:153-156`
- **Status**: NEW
- **Description**: When the input buffer does not yet have enough samples, the method returns `np.zeros_like(audio_chunk)` (silence) instead of the original audio. This produces an audible dropout at the start of each track or stream.
- **Evidence**:
  ```python
  else:
      self.performance_stats['buffer_underruns'] += 1
      return np.zeros_like(audio_chunk)   # silence, not passthrough
  ```
- **Suggested Fix**: Return `audio_chunk` (dry passthrough) during underrun rather than silence. The EQ is simply not applied yet — the audio itself is valid.

---

### S-15: `SimpleMastering.master_file` Uses First-Chunk Peak for All-Chunk Peak-Reduction Gate
- **Severity**: MEDIUM
- **Dimension**: Audio Integrity / DSP Pipeline
- **Location**: `auralis/core/simple_mastering.py:138-143`
- **Status**: NEW
- **Description**: `peak_db` is computed from the first chunk only and passed unchanged to every subsequent `_process(chunk, ..., peak_db, ...)` call. If the first chunk is a quiet intro and the chorus is much louder, peak reduction never engages for the loud parts. If the first chunk is a loud intro, soft sections receive unnecessary soft-clipping.
- **Evidence**:
  ```python
  first_chunk = audio_file.read(chunk_size)
  peak_db = self._peak_db(first_chunk.T)   # computed once

  while read_pos < total_frames:
      chunk = audio_file.read(...)
      processed_chunk, _ = self._process(chunk, fingerprint, peak_db, ...)
      # peak_db never updated — stale for all subsequent chunks
  ```
- **Suggested Fix**: Compute `peak_db` per chunk, or do a two-pass approach (scan entire file for peak first, then process).

---

### S-16: `QueueManager.remove_track` Leaves Stale Audio Loaded When Removing Currently-Playing Track
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:102-114`
- **Status**: NEW
- **Description**: When the currently-playing track is removed from the queue, `queue_manager.remove_track()` updates the queue index but sends no signal to stop playback or reload audio. The audio file manager continues streaming the removed track's audio while `get_current_track()` now returns the next track. Track metadata (title, artist, duration) diverges from audio output.
- **Evidence**:
  ```python
  def remove_track(self, index: int) -> bool:
      if 0 <= index < len(self.tracks):
          self.tracks.pop(index)
          if index < self.current_index: self.current_index -= 1
          elif index == self.current_index:
              if self.current_index >= len(self.tracks):
                  self.current_index = len(self.tracks) - 1
          return True  # no stop/reload signal
  ```
- **Impact**: Display shows next track's metadata while audio from the removed track continues playing. Play statistics logged for wrong track.
- **Suggested Fix**: Emit a state-change callback if `index == self.current_index` so the player can stop and reload.

---

### S-17: `toggleEnabled` Reads Stale `state.enabled` on Rapid Double-Click — Duplicate API Requests
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:179-205`
- **Status**: NEW
- **Description**: `toggleEnabled` is `useCallback` with `[post, state.enabled]` deps. Two rapid clicks before the first re-render both compute `newEnabled = !state.enabled` from the same stale value and send two identical API requests. The final state is unchanged — toggle appears broken.
- **Evidence**:
  ```typescript
  const toggleEnabled = useCallback(async () => {
    const newEnabled = !state.enabled;  // stale if clicked twice fast
    await post('/api/player/enhancement/toggle', undefined, { enabled: newEnabled });
    setState((prev) => ({ ...prev, enabled: newEnabled }));  // both calls set same value
  }, [post, state.enabled]);
  ```
- **Suggested Fix**: Use a `useRef` to track in-flight toggle state, or disable the button while the API call is in progress (already tracks `isLoading` — just disable on `isLoading`).

---

### S-18: LIKE Search Patterns Don't Escape `%` and `_` Metacharacters — Unintended Full-Scan on `%` Query
- **Severity**: MEDIUM
- **Dimension**: Library/Database
- **Location**: `auralis/library/repositories/track_repository.py:287`, `album_repository.py:139`, `artist_repository.py:140`, `genre_repository.py:275`
- **Status**: NEW
- **Description**: All search repositories construct LIKE patterns with raw user input: `search_term = f"%{query}%"`. A user query of `%` matches all rows; `_` matches any single character. On large libraries, a `%` search forces a full-table scan with no index benefit.
- **Evidence**:
  ```python
  search_term = f"%{query}%"
  Track.title.ilike(search_term),  # raw % and _ not escaped
  ```
- **Suggested Fix**: Escape `%` → `\%` and `_` → `\_` in user query before interpolation: `query.replace('%', r'\%').replace('_', r'\_')`. Use `ilike(search_term, escape='\\')` in SQLAlchemy.

---

### S-19: `AlbumRepository.get_by_id` Expunges Album but Leaves Related Tracks in Session — `DetachedInstanceError` Risk
- **Severity**: MEDIUM
- **Dimension**: Library/Database
- **Location**: `auralis/library/repositories/album_repository.py:33-47`
- **Status**: NEW
- **Description**: `get_by_id` calls `session.expunge(album)` after `joinedload(Album.tracks)`. The album object is detached but the `Track` objects remain session-associated. Subsequent access to `album.tracks` outside the session context can raise `DetachedInstanceError` if SQLAlchemy hasn't fully populated the collection in memory.
- **Evidence**:
  ```python
  album = session.query(Album).options(joinedload(Album.tracks)).first()
  session.expunge(album)  # album detached; tracks still in session
  return album
  # Caller accesses album.tracks → potential DetachedInstanceError
  ```
- **Suggested Fix**: Use `make_transient_to_detached` or `expunge_all()` after the query, or use `session.expunge(album)` followed by manually expunging each `track in album.tracks`.

---

### S-20: `backup` Query Parameter on Metadata Write Endpoint Is Client-Suppressible
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/metadata.py:179`
- **Status**: NEW
- **Description**: `PUT /api/metadata/tracks/{track_id}` exposes `backup: bool = True` as a FastAPI query parameter. Any client can pass `?backup=false` to skip the safety copy before overwriting embedded file tags. If the write fails mid-operation, the audio file is corrupted with no recovery path.
- **Evidence**:
  ```python
  @router.put("/api/metadata/tracks/{track_id}")
  async def update_track_metadata(track_id: int, request: ..., backup: bool = True):
  ```
- **Suggested Fix**: Remove `backup` as a public query parameter. Always perform backups server-side. If backup suppression is needed (e.g., bulk operations), require it via an authenticated internal flag, not a user-accessible query param.

---

### S-21: No Test for Gapless Prebuffer With Tracks of Different Sample Rates
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `tests/auralis/player/test_gapless_playback_engine.py`
- **Status**: NEW
- **Description**: All 4 existing gapless engine tests use 44100 Hz. `advance_with_prebuffer` copies `sample_rate` from the prebuffered track directly without validation or resampling. Mixed-rate playlists (44.1 kHz CD + 48 kHz studio) will play the second track at the wrong pitch/speed with no error.
- **Evidence**:
  ```python
  # gapless_playback_engine.py:175-178 — no rate validation
  self.file_manager.sample_rate = sample_rate  # accepted unconditionally
  ```
  All 4 tests use same sample rate fixture.
- **Suggested Fix**: Add test with `track_A_sr=44100`, `track_B_sr=48000` and assert that `advance_with_prebuffer` either resamples or raises a meaningful error.

---

### S-22: `AdaptationEngine` Smoothing Factor Semantics Inverted for Low/High Frequency Bands
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/realtime_adaptive_eq/adaptation_engine.py:168-177`
- **Status**: NEW
- **Description**: Comments say "Low frequencies — slower adaptation" but code uses `smoothing_factor * 1.2` (higher alpha = faster). Comments say "High frequencies — faster adaptation" but code uses `smoothing_factor * 0.8` (lower alpha = slower). The intent and implementation are inverted throughout.
- **Evidence**:
  ```python
  if i < 8:   # Low frequencies - slower adaptation
      smoothing = smoothing_factor * 1.2  # ACTUALLY faster (higher alpha)
  elif i > 20: # High frequencies - faster adaptation
      smoothing = smoothing_factor * 0.8  # ACTUALLY slower (lower alpha)
  ```
- **Suggested Fix**: Swap the multipliers: use `* 0.8` for low-frequency bands and `* 1.2` for high-frequency bands.

---

### S-23: `console.log` on Every Player State WebSocket Message in Production
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:129`
- **Status**: NEW
- **Description**: Every `player_state` message (sent at regular position-update intervals) unconditionally logs the full state object. Thousands of console entries per playback session, degrading DevTools performance and potentially exposing track paths in browser logs.
- **Evidence**:
  ```typescript
  console.log('[usePlayerStateSync] Redux updated from WebSocket:', state);
  ```
- **Suggested Fix**: Guard with `if (process.env.NODE_ENV === 'development')` or remove entirely.

---

### S-24: `TrackRepository.update` Lists `bitrate` as Valid Field but `add` Never Populates It
- **Severity**: LOW
- **Dimension**: Library/Database
- **Location**: `auralis/library/repositories/track_repository.py:633`
- **Status**: NEW
- **Description**: `update()` iterates `['title', 'duration', 'bitrate', ...]` but `add()` never sets `bitrate`. If the `Track` model has no `bitrate` column, `setattr(track, 'bitrate', value)` sets an instance attribute SQLAlchemy ignores — silent data loss.
- **Evidence**:
  ```python
  for field in ['title', 'duration', 'bitrate', 'sample_rate', ...]:  # bitrate here
      if field in track_info: setattr(track, field, track_info[field])
  ```
  `add()` at lines 115-133: no `bitrate` assignment.
- **Suggested Fix**: Either add `bitrate` to `add()` and verify the `Track` model has a `bitrate` column, or remove it from `update()`.

---

### S-25: `GaplessPlaybackEngine.prebuffer_callbacks` Mutated and Iterated Without Lock
- **Severity**: LOW
- **Dimension**: Concurrency
- **Location**: `auralis/player/gapless_playback_engine.py:51-61`
- **Status**: NEW
- **Description**: `add_prebuffer_callback` (main thread) appends to `self.prebuffer_callbacks` without holding `self.update_lock`. `_notify_prebuffer_callbacks` (worker thread) iterates the same list without the lock. Concurrent access produces `RuntimeError: list changed size during iteration`, killing the worker thread silently.
- **Evidence**:
  ```python
  def add_prebuffer_callback(self, callback):
      self.prebuffer_callbacks.append(callback)   # no lock

  def _notify_prebuffer_callbacks(self, track_info):
      for callback in self.prebuffer_callbacks:   # no lock, worker thread
  ```
- **Suggested Fix**: Protect both methods with `self.update_lock`.

---

## Relationships

- **S-01 + S-10 + S-11**: The event loop blocking in `process_chunk_safe` went undetected because 72% of its tests are permanently skipped and no concurrency test exists. These three findings form a causal chain.
- **S-02 + S-03 + S-04**: Three independent audio integrity bugs in the DSP pipeline all produce audible artifacts on every processed track. They compound — a track with heavy EQ has double-windowing tremolo, limiter clicks at chunk boundaries, AND sub-bass energy loss.
- **S-05**: The file upload orphan bug means the "Add to Library" feature is completely broken — this is likely the most impactful user-facing defect in this audit.
- **S-07**: The wrong `setStreamingError` dispatch silences error reporting for streaming failures, making S-01's fallout (WebSocket timeout, stream abort) invisible to the user.

## Prioritized Fix Order

1. **S-01** (CRITICAL): Event loop blocking in `process_chunk_safe` — affects all users during playback
2. **S-05** (HIGH): File upload dead record — feature completely broken
3. **S-02** (HIGH): Double Hanning window — audible tremolo on all EQ'd tracks
4. **S-03** (HIGH): BrickWallLimiter state loss — click every 30s during streaming
5. **S-07** (HIGH): `setStreamingError` wrong type — error state silently swallowed
6. **S-08** (HIGH): MigrationManager engine leak — compounds on every restart
7. **S-09** (HIGH): `useWebSocketSubscription` null silent fail — player UI frozen
8. **S-10 + S-11** (HIGH): Restore chunked processor test coverage and add non-blocking test
9. **S-04** (HIGH): Sub-bass EQ asymmetry — bass EQ half as effective as intended

## Cross-References to Existing Issues

| Skipped Finding | Extends / Matches | Existing Issue |
|----------------|-------------------|----------------|
| Gapless prebuffer path doesn't reset position | Extends | #2283 |
| Mastering recommendation blocks event loop | Extends | #2301 |
| `GET /api/metadata` sync I/O in async handler | Extends | #2317 |
| Album search fabricated total in `library.py` router | Second instance of | #2380 |
| `_active_streaming_tasks` module-level never pruned | Explains mechanism for | #2321 |
