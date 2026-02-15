# Comprehensive Auralis Audit — 2026-02-14

## Executive Summary

Full-codebase audit of Auralis v1.2.0-beta.3 covering all 10 audit dimensions: Audio Integrity, DSP Pipeline, Player State, Backend API, Frontend State, Library/Database, Security, Concurrency, Error Handling, and Test Coverage.

**Total findings: 52 NEW** (after deduplication against 93+ existing open issues)

| Severity | Count | Key Themes |
|----------|-------|------------|
| CRITICAL | 1 | Threading deadlock in gapless playback |
| HIGH | 13 | Audio invariant violations, missing thread safety, no WebSocket auth, path traversal, data loss |
| MEDIUM | 29 | DSP correctness bugs, async/sync boundary issues, memory leaks, security gaps, library bugs |
| LOW | 9 | Dead code, minor inconsistencies, non-deterministic state |

**Additionally identified 8 findings that match existing open issues** (confirmed as duplicates).

### Most Impactful Issues

1. **C-01: GaplessPlaybackEngine deadlock** — `threading.Lock` (non-reentrant) acquired twice in the same call chain. Guaranteed deadlock on every gapless track transition. Blocks the entire player.
2. **H-07: EQ padding changes sample count** — When audio chunk < FFT size, output is padded to FFT size. Violates `len(output) == len(input)` invariant. Causes clicks/gaps in gapless playback.
3. **H-05: LowMidTransientEnhancer dead computation** — Expansion envelope and crossfade ramps computed but never assigned. The transient enhancer does nothing beyond a simple additive boost.
4. **H-04: Tanh limiter distorts all samples** — Applies `tanh()` to the entire signal when any sample exceeds 0.95, causing subtle but measurable dynamic range compression.

### Key Themes

- **Thread safety is inconsistent**: GaplessPlaybackEngine uses non-reentrant `Lock`, PlaybackController has no lock at all, backend state manager uses blocking `threading.Lock` in async code.
- **Audio invariant violations**: EQ padding, dtype coercion (float32 forcing), and stereo FFT bugs violate the project's critical audio invariants.
- **Dead/ineffective code**: Multiple DSP modules compute values that are never used (transient enhancer, gain smoother).
- **Async/sync boundary**: Backend mixes `threading.Lock` with asyncio, synchronous file I/O in async handlers, and `asyncio.create_task` from background threads.

---

## Findings

### CRITICAL

### C-01: GaplessPlaybackEngine deadlock — non-reentrant Lock acquired twice
- **Severity**: CRITICAL
- **Dimension**: Concurrency / Player State
- **Location**: `auralis/player/gapless_playback_engine.py:125-143`
- **Status**: NEW
- **Description**: `get_prebuffered_track()` acquires `self.update_lock` (a `threading.Lock()`, non-reentrant), then calls `has_prebuffered_track()` which also tries to acquire the same lock. Since `threading.Lock` is NOT reentrant, this is a guaranteed deadlock.
- **Evidence**:
  ```python
  # Line 48: Non-reentrant lock
  self.update_lock = threading.Lock()

  # Line 125-129: Acquires lock
  def has_prebuffered_track(self) -> bool:
      with self.update_lock:  # Acquires lock
          return (self.next_track_buffer is not None and
                  self.next_track_info is not None)

  # Line 131-143: Acquires same lock, then calls above
  def get_prebuffered_track(self) -> tuple[np.ndarray | None, int | None]:
      with self.update_lock:  # Lock acquired
          if self.has_prebuffered_track():  # DEADLOCK: tries to acquire same lock
              audio = self.next_track_buffer
              sr = self.next_track_sample_rate
              return audio, sr
      return None, None
  ```
  **Call path**: `AudioPlayer.next_track()` → `GaplessPlaybackEngine.advance_with_prebuffer()` → `get_prebuffered_track()` → `has_prebuffered_track()` → DEADLOCK
- **Impact**: Every gapless track transition deadlocks the player thread. The player hangs permanently. Requires application restart.
- **Related**: #2075 (gapless thread cleanup), #2154 (seek/prebuffer)
- **Suggested Fix**: Either change `threading.Lock()` to `threading.RLock()` (reentrant), or inline the check in `get_prebuffered_track` instead of calling `has_prebuffered_track()`.

---

### HIGH

### H-01: PlaybackController has no thread safety
- **Severity**: HIGH
- **Dimension**: Concurrency / Player State
- **Location**: `auralis/player/playback_controller.py:35-38`
- **Status**: NEW
- **Description**: PlaybackController manages playback state (PLAYING/PAUSED/STOPPED/LOADING/ERROR) and position, but has no lock whatsoever. The CLAUDE.md invariant requires "state changes atomic (RLock)" for player state.
- **Evidence**:
  ```python
  class PlaybackController:
      def __init__(self) -> None:
          self.state = PlaybackState.STOPPED  # No lock protection
          self.position = 0                    # No lock protection
          self.callbacks: list[...] = []       # No lock protection
  ```
  All state transitions (`play()`, `pause()`, `stop()`, `seek()`) read and write `self.state` and `self.position` without any synchronization.
- **Impact**: Race conditions when playback state is accessed from multiple threads (UI thread, audio callback thread, prebuffer thread). Can lead to invalid state transitions (e.g., STOPPED → PAUSED) or corrupted position values.
- **Related**: C-01 (threading issues in player)
- **Suggested Fix**: Add `threading.RLock()` and protect all state reads/writes.

### H-02: AudioPlayer state setter bypasses state machine
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py` (state.setter)
- **Status**: NEW
- **Description**: The `state` property setter on AudioPlayer directly assigns to `self.playback.state`, bypassing the state machine's transition validation, callbacks, and logging in PlaybackController's `play()`/`pause()`/`stop()` methods.
- **Evidence**:
  ```python
  @state.setter
  def state(self, value: PlaybackState) -> None:
      """Set playback state (for compatibility)"""
      self.playback.state = value  # Direct assignment, no validation
  ```
- **Impact**: External code can set arbitrary state transitions (e.g., ERROR → PLAYING) without going through the state machine. State change callbacks are not fired, leaving the UI out of sync.
- **Related**: H-01 (PlaybackController thread safety)
- **Suggested Fix**: Remove the setter or route through PlaybackController's transition methods.

### H-03: EQ filter forces float32 output regardless of input dtype
- **Severity**: HIGH
- **Dimension**: Audio Integrity
- **Location**: `auralis/dsp/eq/filters.py:99`
- **Status**: NEW
- **Description**: `apply_eq_mono()` always returns `dtype=np.float32` regardless of input dtype. If input is float64, precision is silently lost.
- **Evidence**:
  ```python
  return np.asarray(processed_audio[:len(audio_mono)], dtype=np.float32)
  ```
- **Impact**: Violates the audio invariant `output.dtype in [np.float32, np.float64]` matching input. float64→float32 truncation introduces quantization noise in high-precision processing chains.
- **Related**: #2158 (dtype promotion in parallel EQ), #2167 (dtype inconsistency in envelope followers)
- **Suggested Fix**: Use `dtype=audio_mono.dtype` to preserve input precision.

### H-04: Realtime processor tanh limiter distorts all samples when max > 0.95
- **Severity**: HIGH
- **Dimension**: DSP Pipeline / Audio Integrity
- **Location**: `auralis/player/realtime/processor.py:142-145`
- **Status**: NEW
- **Description**: When any sample in the chunk exceeds 0.95 (but not 1.0), the limiter applies `tanh()` to the ENTIRE signal, not just the peaks. This introduces nonlinear distortion across all samples.
- **Evidence**:
  ```python
  else:
      # "Just gentle saturation" — actually distorts ALL samples
      processed = np.tanh(processed / target_peak) * target_peak
  ```
  For a signal with max 0.96, a quiet sample at 0.1 becomes `tanh(0.1/0.98)*0.98 ≈ 0.0997` — minor. But a sample at 0.8 becomes `tanh(0.816)*0.98 ≈ 0.659*0.98 ≈ 0.646` — significant peak reduction (19% loss). This compresses dynamic range audibly.
- **Impact**: Audible dynamic range compression on any audio with peaks above -0.45 dBFS. Most mastered music triggers this.
- **Suggested Fix**: Only apply soft-clipping to samples above the threshold, leave everything below untouched.

### H-05: LowMidTransientEnhancer discards computed expansion envelope
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/lowmid_transient_enhancer.py:149-155`
- **Status**: NEW
- **Description**: The expansion envelope and crossfade ramps are computed but the results are never assigned to variables. The function computes `np.power(...)` and `np.linspace(...)` but throws away the results.
- **Evidence**:
  ```python
  # Line 151: Computed but NOT assigned
  np.power(relative_level, 1.0 - intensity)

  # Lines 154-155: Crossfade ramps computed but NOT assigned
  np.linspace(0, 1, min(20, end - start))
  np.linspace(1, 0, min(20, end - start))
  ```
  The actual transient boost at line 160 is just a simple additive boost: `output[start:end] += boost_amount * low_mid[start:end]`, without any of the computed expansion or crossfade.
- **Impact**: The transient enhancer is fundamentally broken — it does a crude additive boost instead of the intended frequency-dependent expansion with crossfading. Transient enhancement is ineffective.
- **Suggested Fix**: Assign the computed values and use them: `expansion_env = np.power(...)`, then apply `output[start:end] = low_mid[start:end] * expansion_env`.

### H-06: Content analysis FFT produces wrong results on stereo input
- **Severity**: HIGH
- **Dimension**: Audio Integrity / Analysis
- **Location**: `auralis/analysis/content/content_operations.py:71`
- **Status**: NEW
- **Description**: `calculate_spectral_spread()` calls `fft(audio[:8192])` without specifying axis. For stereo audio (shape `(N, 2)`), NumPy's `fft` operates on the last axis by default, computing 8192 separate 2-point FFTs instead of one 8192-point FFT.
- **Evidence**:
  ```python
  fft_result = fft(audio[:8192])  # If audio is (N,2): 8192 two-point FFTs
  magnitude = np.abs(fft_result[:4096])
  ```
  For stereo input, result shape is `(8192, 2)` where each row is a meaningless 2-point FFT. The spectral spread calculation returns garbage values.
- **Impact**: All spectral analysis metrics (spread, centroid, flux) are wrong for stereo audio. Affects content-type detection and adaptive processing decisions.
- **Related**: Same pattern likely exists in `calculate_spectral_flux` (line 84+)
- **Suggested Fix**: Convert to mono first: `audio_mono = np.mean(audio[:8192], axis=1) if audio.ndim == 2 else audio[:8192]`.

### H-07: EQ apply_eq_gains padding changes sample count
- **Severity**: HIGH
- **Dimension**: Audio Integrity
- **Location**: `auralis/dsp/eq/filters.py:35-42`
- **Status**: NEW
- **Description**: When `len(audio_chunk) < fft_size`, the function pads the chunk to `fft_size` samples, then passes the padded array to `apply_eq_mono()`. The mono function returns `processed_audio[:len(audio_mono)]` where `audio_mono` is the padded array, so the output has `fft_size` samples, not the original chunk length.
- **Evidence**:
  ```python
  # Lines 35-42: Pads audio_chunk variable to fft_size
  if len(audio_chunk) < fft_size:
      padded = np.zeros((fft_size, ...))
      audio_chunk = padded.squeeze()  # Now len = fft_size

  # Line 46: Passes padded chunk to apply_eq_mono
  return apply_eq_mono(audio_chunk, ...)  # audio_chunk has fft_size samples

  # Line 99 (in apply_eq_mono): Returns padded length
  return np.asarray(processed_audio[:len(audio_mono)], dtype=np.float32)
  # len(audio_mono) = fft_size, NOT original length
  ```
- **Impact**: Violates `len(output) == len(input)`. Short chunks at track boundaries grow in size, causing clicks, gaps, or buffer overruns in gapless playback.
- **Related**: #2157 (zero-length boundary in crossfade)
- **Suggested Fix**: Store original length before padding, then trim output: `original_len = len(audio_chunk)` ... `return output[:original_len]`.

### H-08: processingService uses REACT_APP_ env vars in Vite project
- **Severity**: HIGH
- **Dimension**: Frontend
- **Location**: `auralis-web/frontend/src/services/processingService.ts:102-103`
- **Status**: NEW
- **Description**: Uses `process.env.REACT_APP_*` which is the Create React App convention. Vite uses `import.meta.env.VITE_*`. These variables are always `undefined` in Vite, so the service always falls back to hardcoded defaults.
- **Evidence**:
  ```typescript
  this.baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8765';
  this.wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8765/ws';
  ```
- **Impact**: Environment-based configuration is completely broken for the processing service. Cannot configure API URLs via environment variables for production deployment.
- **Suggested Fix**: Change to `import.meta.env.VITE_API_URL` and `import.meta.env.VITE_WS_URL`.

### H-09: WebSocket endpoint has no authentication
- **Severity**: HIGH
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/system.py:96-107`
- **Status**: NEW
- **Description**: The `/ws` WebSocket endpoint accepts any connection without authentication. CORS middleware only covers HTTP, not WebSocket upgrades.
- **Evidence**:
  ```python
  @router.websocket("/ws")
  async def websocket_endpoint(websocket: WebSocket) -> None:
      await manager.connect(websocket)  # No auth check
  ```
  Rate limiting was added (fix #2156) but authentication is still absent.
- **Impact**: Any client can connect and receive broadcast messages (scan progress with file paths, processing status, player state). Can also send messages to trigger processing.
- **Related**: #2185 (no concurrent stream limits)
- **Suggested Fix**: Add token-based authentication before `manager.connect()`, or at minimum validate Origin header.

### H-10: Queue index off-by-one allows out-of-bounds access
- **Severity**: HIGH
- **Dimension**: Library/Database
- **Location**: `auralis/library/repositories/queue_repository.py:80-81, 139-141`
- **Status**: NEW
- **Description**: `set_queue_state()` validates `current_index > len(track_ids)` instead of `>=`. A queue with 3 tracks (indices 0,1,2) accepts `current_index=3`, which is out of bounds.
- **Impact**: Invalid index persisted to DB. `track_ids[current_index]` raises IndexError at playback.
- **Suggested Fix**: Change `>` to `>=`.

### H-11: backup_database does not checkpoint WAL before copying
- **Severity**: HIGH
- **Dimension**: Library/Database
- **Location**: `auralis/library/migration_manager.py:296-328`
- **Status**: NEW
- **Description**: Uses `shutil.copy2()` to copy the `.db` file in WAL mode. Misses all data in the `-wal` file. `-wal` and `-shm` files are not copied.
- **Impact**: Pre-migration backups silently lose recent writes. Restoring after failed migration causes data loss.
- **Suggested Fix**: Run `PRAGMA wal_checkpoint(TRUNCATE)` before copying, or use `sqlite3.Connection.backup()`.

### H-12: Player load_track endpoint accepts unvalidated file paths
- **Severity**: HIGH
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/player.py:159-188`
- **Status**: NEW
- **Description**: `POST /api/player/load` accepts a `track_path` parameter with no path validation. Any filesystem path can be passed to the audio player.
- **Impact**: Arbitrary file access via the audio player.
- **Related**: #2181 (path traversal in library scan)
- **Suggested Fix**: Require tracks to be loaded by `track_id` only.

### H-13: Artwork endpoint serves files from unvalidated database path
- **Severity**: HIGH
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/artwork.py:52-84`
- **Status**: NEW
- **Description**: Reads `album.artwork_path` from the database and passes directly to `FileResponse()`. If the field is tampered, arbitrary files can be served.
- **Impact**: Arbitrary file read if artwork_path is tampered via SQL injection (#2078) or update endpoints.
- **Suggested Fix**: Validate artwork_path resolves within `~/.auralis/artwork/` before serving.

---

### MEDIUM

### M-01: HybridProcessor._load_audio_placeholder returns random noise
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/hybrid_processor.py:359-363`
- **Status**: NEW
- **Description**: Placeholder method returns `np.random.randn(44100 * 5, 2) * 0.1` — 5 seconds of random audio noise.
- **Evidence**:
  ```python
  def _load_audio_placeholder(self, file_path: str) -> np.ndarray:
      return np.random.randn(44100 * 5, 2) * 0.1
  ```
- **Impact**: Not hit in production (backend passes NumPy arrays, not file paths), but if any code path passes a string, the user gets random noise instead of an error. Non-deterministic output.
- **Suggested Fix**: Raise `NotImplementedError("Audio loading should use unified_loader")`.

### M-02: Critical band zero center frequency in psychoacoustic EQ
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py`
- **Status**: NEW
- **Description**: The first critical band has a center frequency of 0 Hz (DC), which causes division-by-zero in bandwidth calculations and produces meaningless EQ adjustments in the sub-bass region.
- **Impact**: EQ adjustments near 0 Hz have no audible effect but consume processing time. May produce NaN in downstream calculations.
- **Suggested Fix**: Start first critical band at 20 Hz (audible range).

### M-03: AdaptiveGainSmoother ignores num_samples parameter
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/player/realtime/gain_smoother.py`
- **Status**: NEW
- **Description**: The `smooth()` method accepts a `num_samples` parameter but ignores it, always smoothing a single gain value regardless of chunk size.
- **Impact**: Gain transitions are not sample-accurate. Abrupt gain changes at chunk boundaries cause audible clicks.
- **Suggested Fix**: Generate a per-sample gain ramp using `num_samples`.

### M-04: PsychoacousticEQ reset sets gains to 1.0 dB instead of 0.0 dB
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:330-334`
- **Status**: NEW
- **Description**: `reset()` sets `current_gains` and `target_gains` to `np.ones(...)` (1.0 dB per band) instead of `np.zeros(...)` (flat/bypass).
- **Evidence**:
  ```python
  def reset(self) -> None:
      self.current_gains = np.ones(len(self.critical_bands))   # 1.0 dB, not flat
      self.target_gains = np.ones(len(self.critical_bands))    # Should be np.zeros
  ```
- **Impact**: After reset, EQ applies +1 dB across all bands instead of being flat. Subtle but cumulative loudness increase (~1 dB).
- **Suggested Fix**: Change `np.ones` to `np.zeros`.

### M-05: PersonalPreferences version auto-increment uses unsorted dict
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/core/personal_preferences.py`
- **Status**: NEW
- **Description**: Version tracking uses `list(self.history.keys())` to find the latest version, but dict ordering depends on insertion order. If entries are added non-chronologically, the "latest" version may not be the most recent.
- **Impact**: Version conflicts when loading preferences from different sources. May roll back to an older version.
- **Suggested Fix**: Sort keys or use an explicit version counter.

### M-06: PersonalPreferences concurrent save/load without file locking
- **Severity**: MEDIUM
- **Dimension**: Concurrency
- **Location**: `auralis/core/personal_preferences.py`
- **Status**: NEW
- **Description**: Preferences are saved/loaded from JSON files without file locking. Concurrent saves can corrupt the file (partial writes). Concurrent save+load can read a partially written file.
- **Impact**: Preference data loss or corruption in multi-process scenarios (e.g., desktop app + CLI).
- **Suggested Fix**: Use atomic write (write to temp file, rename) and file locking.

### M-07: PerformanceMonitor accessed outside lock in realtime processor
- **Severity**: MEDIUM
- **Dimension**: Concurrency
- **Location**: `auralis/player/realtime/processor.py:148-150`
- **Status**: NEW
- **Description**: `performance_monitor.record_processing_time()` is called after releasing the lock, but the monitor's internal state is not thread-safe.
- **Impact**: Performance statistics may be corrupted under concurrent access (unlikely to cause audio issues but affects monitoring accuracy).
- **Suggested Fix**: Either call within the lock context or make PerformanceMonitor thread-safe.

### M-08: Compressor applies single gain to entire chunk
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/` (compressor module)
- **Status**: NEW
- **Description**: The compressor computes a single gain reduction value and applies it uniformly to the entire chunk. Real compressors have per-sample gain envelopes with attack/release timing.
- **Impact**: Pumping artifacts — the entire chunk jumps in level at chunk boundaries. Particularly audible on transient-heavy material (drums).
- **Suggested Fix**: Implement per-sample envelope following with attack/release time constants.

### M-09: FFmpeg loader hardcodes 44100Hz/stereo
- **Severity**: MEDIUM
- **Dimension**: Audio Integrity
- **Location**: `auralis/io/unified_loader.py` (FFmpeg path)
- **Status**: NEW
- **Description**: The FFmpeg loading path hardcodes `-ar 44100 -ac 2` in the command, forcing all audio to 44100 Hz stereo regardless of the source sample rate.
- **Impact**: High-resolution audio (96kHz, 192kHz) is silently downsampled to 44.1kHz. Mono files are upmixed to stereo. The caller is not informed of the resampling.
- **Suggested Fix**: Read source metadata first, then either preserve native rate or inform the caller of the conversion.

### M-10: ProcessingEngine unbounded job dict memory leak
- **Severity**: MEDIUM
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/processing_engine.py`
- **Status**: NEW
- **Description**: Completed processing jobs are never removed from the internal jobs dictionary. In a long-running server, this accumulates indefinitely.
- **Impact**: Memory grows linearly with the number of processed tracks. After thousands of enhancements, significant memory waste.
- **Related**: #2161 (HybridProcessor cache unbounded)
- **Suggested Fix**: Add TTL-based expiry or LRU eviction for completed jobs.

### M-11: ProcessingEngine cancel_job doesn't stop processing
- **Severity**: MEDIUM
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/processing_engine.py`
- **Status**: NEW
- **Description**: `cancel_job()` marks the job as cancelled in the dict but doesn't signal the actual processing thread/task to stop.
- **Impact**: "Cancelled" jobs continue consuming CPU/memory until they complete naturally. Cancellation is cosmetic only.
- **Suggested Fix**: Use `asyncio.Task.cancel()` or a cancellation token pattern.

### M-12: Processor cache key too coarse
- **Severity**: MEDIUM
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/processing_engine.py`
- **Status**: NEW
- **Description**: Cache key is based only on track ID, not processing parameters (preset, intensity, etc.). Different enhancement settings for the same track hit the same cache entry.
- **Impact**: User changes processing settings but gets the cached result from previous settings. Appears as "settings not working."
- **Suggested Fix**: Include processing parameters in the cache key hash.

### M-13: ConnectionManager broadcast list mutation during iteration
- **Severity**: MEDIUM
- **Dimension**: Concurrency / Backend API
- **Location**: `auralis-web/backend/` (ConnectionManager)
- **Status**: NEW
- **Description**: `broadcast()` iterates over the active connections list while `disconnect()` can modify it concurrently. No synchronization between the two.
- **Impact**: `RuntimeError: list changed size during iteration` during broadcast if a client disconnects at the same time.
- **Suggested Fix**: Iterate over a copy: `for conn in list(self.active_connections):`.

### M-14: State manager uses threading.Lock in async context
- **Severity**: MEDIUM
- **Dimension**: Concurrency / Backend API
- **Location**: `auralis-web/backend/state_manager.py:215`
- **Status**: NEW
- **Description**: The `_position_update_loop` coroutine uses `with self._lock:` where `_lock` is a `threading.Lock()`. This blocks the asyncio event loop while holding the lock.
- **Impact**: While the lock is held, no other coroutines can run. If any other thread holds the lock, the event loop freezes. Causes latency spikes in WebSocket message handling.
- **Related**: #2171 (position update drift)
- **Suggested Fix**: Change to `asyncio.Lock()` and use `async with self._lock:`.

### M-15: WebM encoder blocks event loop with synchronous encoding
- **Severity**: MEDIUM
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/` (encoding module)
- **Status**: NEW
- **Description**: WebM audio encoding calls FFmpeg synchronously (subprocess.run) inside an async handler, blocking the event loop for the entire encoding duration.
- **Impact**: All other WebSocket clients and HTTP requests are blocked during encoding. For a 5-minute track, the server is unresponsive for several seconds.
- **Suggested Fix**: Use `asyncio.create_subprocess_exec()` or run in `asyncio.to_thread()`.

### M-16: Duplicate selector systems in Redux store
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/store/selectors/index.ts`, `auralis-web/frontend/src/store/selectors/advanced.ts`
- **Status**: NEW
- **Description**: Two separate selector files define overlapping selectors for the same state. `index.ts` has factory selectors, `advanced.ts` has memoized selectors. Components use both, creating confusion about which to use.
- **Impact**: Inconsistent selector usage across components. Some components use memoized selectors (good), others use factory selectors that create new references (bad, per #2131).
- **Related**: #2131 (factory selectors return new references)
- **Suggested Fix**: Consolidate into a single selector file using `createSelector` from reselect.

### M-17: StandardizedAPIClient response cache grows unbounded
- **Severity**: MEDIUM
- **Dimension**: Frontend
- **Location**: `auralis-web/frontend/src/services/` (API client)
- **Status**: NEW
- **Description**: The API client caches all responses in a Map without eviction. Over time, this accumulates all API responses ever fetched.
- **Impact**: Memory leak in the browser. After extended use, the tab's memory usage grows continuously.
- **Related**: #2084 (chunk cache unbounded)
- **Suggested Fix**: Add LRU eviction or TTL-based cache expiry.

### M-18: CORS allows all headers/methods with allow_credentials=True
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis-web/backend/config/middleware.py:62-79`
- **Status**: NEW
- **Description**: CORS configuration uses `allow_methods=["*"]` and `allow_headers=["*"]` combined with `allow_credentials=True`. This is an overly permissive configuration.
- **Evidence**:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_credentials=True,
      allow_methods=["*"],   # Should be ["GET", "POST", "DELETE", "OPTIONS"]
      allow_headers=["*"],   # Should whitelist specific headers
  )
  ```
- **Impact**: Weakens CSRF protections. A malicious website can make authenticated cross-origin requests with arbitrary headers.
- **Suggested Fix**: Whitelist only needed methods and headers.

### M-19: Missing Rust panic handler in Python bindings
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:86-110`
- **Status**: NEW
- **Description**: Rust DSP functions (HPSS, YIN, Chroma) are called without `std::panic::catch_unwind()` protection. If a Rust function panics (e.g., NaN input, division by zero), the entire Python process crashes.
- **Impact**: Malformed audio data can crash the application with no Python-level error handling or recovery.
- **Suggested Fix**: Wrap DSP calls in `catch_unwind()` or ensure all Rust functions return `Result`.

### M-20: AlbumRepository missing rollback on commit failure
- **Severity**: MEDIUM
- **Dimension**: Library/Database
- **Location**: `auralis/library/repositories/album_repository.py:199-243`
- **Status**: NEW
- **Description**: `update_artwork()` and `delete_artwork()` have try/finally but no except clause with `session.rollback()`. If `session.commit()` fails, the session is left dirty. The sibling `update_artwork_path()` correctly includes rollback.
- **Impact**: Dirty session returned to pool, causing stale data or InvalidRequestError for subsequent operations.
- **Suggested Fix**: Add `except Exception: session.rollback(); raise`.

### M-21: QueueHistoryRepository.undo() uses cross-session writes
- **Severity**: MEDIUM
- **Dimension**: Library/Database / Concurrency
- **Location**: `auralis/library/repositories/queue_history_repository.py:116-164`
- **Status**: NEW
- **Description**: `undo()` opens Session A to read history, delegates to `queue_repository.set_queue_state()` which commits in Session B, then returns to Session A to delete the history entry. Two writes not in the same transaction.
- **Impact**: Crash between commits leaves undo replayable. May revert queue past intended state.
- **Suggested Fix**: Perform both operations in the same session/transaction.

### M-22: Unconstrained setattr in repository update methods
- **Severity**: MEDIUM
- **Dimension**: Security / Library
- **Location**: `auralis/library/repositories/queue_template_repository.py:217-220`, `settings_repository.py:92-94`
- **Status**: NEW
- **Description**: Both use `hasattr()` + `setattr()` from user-controlled input. `hasattr()` returns True for SQLAlchemy internal attributes like `_sa_instance_state`, `metadata`, `registry`.
- **Impact**: ORM state corruption, ID/timestamp manipulation.
- **Related**: #2165 (getattr in query)
- **Suggested Fix**: Replace `hasattr()` with a whitelist of allowed fields.

### M-23: MigrationManager creates engine without WAL mode or pragmas
- **Severity**: MEDIUM
- **Dimension**: Library/Database
- **Location**: `auralis/library/migration_manager.py:128`
- **Status**: NEW
- **Description**: Creates bare engine `create_engine(f'sqlite:///{self.db_path}')` with no WAL mode, busy_timeout, or pool config.
- **Impact**: Migrations may block on lock. Journal mode conflicts with WAL from main engine.
- **Suggested Fix**: Configure with same pragmas as LibraryManager.

### M-24: cleanup_missing_files uses offset pagination while deleting, skipping rows
- **Severity**: MEDIUM
- **Dimension**: Library/Database
- **Location**: `auralis/library/repositories/track_repository.py:711-765`
- **Status**: NEW
- **Description**: Uses `offset += batch_size` while deleting rows within each batch. Deleted rows shift remaining rows, causing some to be skipped.
- **Impact**: Some tracks with missing files are never cleaned up.
- **Suggested Fix**: Use ID-based cursor: `filter(Track.id > last_id)`.

### M-25: Fingerprint server binds to 0.0.0.0 with no authentication
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `vendor/auralis-dsp/src/bin/fingerprint_server.rs:71-81`
- **Status**: NEW
- **Description**: Rust fingerprint server binds to all interfaces (0.0.0.0:8766) with no authentication or TLS. Accepts arbitrary file paths.
- **Impact**: Network-accessible unauthenticated service.
- **Suggested Fix**: Bind to `127.0.0.1:8766`.

### M-26: Discogs API token exposed in URL query string
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis/services/artwork_service.py:183-184`
- **Status**: NEW
- **Description**: Discogs API token included in URL query string, visible in logs and proxy records.
- **Impact**: Token exposure in application/proxy logs.
- **Suggested Fix**: Use Authorization header.

### M-27: Rust fingerprint hardcodes 3 of 25 dimensions as placeholders
- **Severity**: MEDIUM
- **Dimension**: Rust DSP
- **Location**: `vendor/auralis-dsp/src/fingerprint_compute.rs:258, 269, 329-336`
- **Status**: NEW
- **Description**: `rhythm_stability` (0.7), `pitch_stability` (0.75), and `estimate_tempo()` (120.0 BPM) are hardcoded. 12% of the 25D fingerprint is constant across all tracks.
- **Impact**: Similarity searches treat all tracks identically on 3 dimensions.
- **Related**: #2118 (frontend mock data)
- **Suggested Fix**: Implement actual onset detection, IOI variance, and pitch variance.

### M-28: FingerprintExtractor._delete_corrupted_track bypasses repository pattern
- **Severity**: MEDIUM
- **Dimension**: Library/Database
- **Location**: `auralis/services/fingerprint_extractor.py:219-265`
- **Status**: NEW
- **Description**: Uses raw `sqlite3.connect()` with hardcoded path guessing to DELETE tracks. Bypasses ORM cascades, WAL mode, and busy_timeout.
- **Impact**: Raw DELETE bypasses cascade rules. May use wrong database.
- **Related**: #2082 (hardcoded db_path)
- **Suggested Fix**: Accept a TrackRepository instance.

### M-29: Non-daemon fingerprint worker threads prevent clean process exit
- **Severity**: MEDIUM
- **Dimension**: Concurrency
- **Location**: `auralis/services/fingerprint_queue.py:202-209`
- **Status**: NEW
- **Description**: Worker threads are `daemon=False`, preventing Python process exit if `stop()` is not called.
- **Impact**: Process hangs on Ctrl+C or crash. Requires kill -9.
- **Related**: #2075 (gapless thread cleanup)
- **Suggested Fix**: Change to `daemon=True`.

### M-30: File upload endpoint has no size limit
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/files.py:173-218`
- **Status**: NEW
- **Description**: `POST /api/files/upload` reads entire file into memory with no size limit. Accepts a list of files.
- **Impact**: Multi-GB upload can OOM the server. DoS via concurrent uploads.
- **Suggested Fix**: Read in chunks with a max size check.

---

### LOW

### L-01: Soundfile loader logs wrong channel count
- **Severity**: LOW
- **Dimension**: Audio Integrity
- **Location**: `auralis/io/unified_loader.py` (SoundFile path)
- **Status**: NEW
- **Description**: The log message for loaded audio reports the wrong channel count (always reports the array shape dimension instead of actual channels).
- **Impact**: Misleading debug logs. No functional impact.

### L-02: Resample fallback dtype inconsistency
- **Severity**: LOW
- **Dimension**: Audio Integrity
- **Location**: `auralis/io/unified_loader.py` (resample function)
- **Status**: NEW
- **Description**: The scipy resample fallback path doesn't preserve the input dtype, potentially returning float64 when float32 was input.
- **Impact**: Minor dtype mismatch in edge cases. Usually corrected downstream.

### L-03: Enhancement preprocess_upcoming_chunks never processes
- **Severity**: LOW
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/` (enhancement router)
- **Status**: NEW
- **Description**: `preprocess_upcoming_chunks()` is defined and called but the implementation is a no-op or returns immediately.
- **Impact**: Preloading optimization is non-functional. No current degradation since it's an optimization.

### L-04: Mastering recommendation accepts user filepath without validation
- **Severity**: LOW
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/` (mastering recommendation endpoint)
- **Status**: NEW
- **Description**: Accepts a filepath from the user without validating it against allowed directories.
- **Impact**: Potential path traversal, though the endpoint only reads metadata, not file contents.
- **Related**: #2181 (path traversal in library scan)

### L-05: Metadata handlers use sync I/O in async context
- **Severity**: LOW
- **Dimension**: Backend API
- **Location**: `auralis-web/backend/routers/metadata.py` (3 endpoints)
- **Status**: NEW
- **Description**: `get_track_metadata`, `write_metadata`, and `batch_metadata_update` perform synchronous file I/O inside `async def` handlers.
- **Impact**: Event loop blocked during metadata operations. Minor latency impact for other requests.
- **Suggested Fix**: Use `asyncio.to_thread()` for file I/O operations.

### L-06: loggerMiddleware never connected to Redux store
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/store/middleware/loggerMiddleware.ts`
- **Status**: NEW
- **Description**: The logger middleware is defined but never included in the store's middleware chain.
- **Impact**: Dead code. No logging benefit. Occupies space in the codebase.

### L-07: Date.now() in reducers creates non-deterministic state
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/store/slices/` (multiple slices)
- **Status**: NEW
- **Description**: Redux reducers call `Date.now()` to set timestamps. This makes the state non-deterministic and breaks time-travel debugging.
- **Impact**: Redux DevTools time-travel debugging is unreliable. Snapshot tests may be flaky.
- **Suggested Fix**: Move `Date.now()` into action creators (thunks) and pass as payload.

### L-08: Animation system duplicates definitions across files
- **Severity**: LOW
- **Dimension**: Frontend
- **Location**: `auralis-web/frontend/src/design-system/animations/index.ts`
- **Status**: NEW
- **Description**: Some animation keyframes (fade, slide) are duplicated or defined with both an original name and a deprecated alias (e.g., `bounce = gentleFloat`).
- **Impact**: Bundle size slightly increased. Maintenance burden from multiple definitions.

### L-09: QueueTemplateRepository.get_by_tag loads all templates into memory
- **Severity**: LOW
- **Dimension**: Library/Database
- **Location**: `auralis/library/repositories/queue_template_repository.py:153-180`
- **Status**: NEW
- **Description**: Queries ALL templates with `.all()` then filters in Python by parsing JSON tags. Should use SQL LIKE filter.
- **Impact**: Performance degrades linearly with template count.
- **Suggested Fix**: Use SQL LIKE filter.

---

## Confirmed Duplicates

| Finding | Matches Issue | Notes |
|---------|--------------|-------|
| Selector factories return new references | #2131 | Exact match |
| websocketMiddleware NEXT/PREVIOUS stale state | #2178 | Exact match |
| useDragAndDrop/lazyLoader hardcoded colors | #2135 | Instance of general finding |
| StreamlinedCacheManager.get_chunk not lock-protected | #2184 | Exact match |
| SQL injection in fingerprint column names | #2078 | Exact match |
| Hardcoded db_path in FingerprintRepository | #2082 | Exact match |
| _get_original_wav_chunk loads entire file per chunk | #2121 | Related (same pattern, different function) |
| PersonalPreferences fragile version parsing | #2211 | Already filed (version auto-increment) |

---

## Relationships

### Shared Root Causes

1. **Thread safety inconsistency** (C-01, H-01, M-06, M-07, M-13, M-14): The codebase uses a mix of `threading.Lock`, `threading.RLock`, `asyncio.Lock`, and no locks at all. No consistent policy is enforced.

2. **Audio invariant violations** (H-03, H-07, M-09): Three separate modules break the `len(output) == len(input)` and dtype preservation invariants. These compound — EQ changes sample count, then forces float32, then FFmpeg resamples without notice.

3. **Unbounded caches/collections** (M-10, M-12, M-17): Multiple subsystems accumulate data without eviction. Combined, these create a slow memory leak across the entire stack.

4. **Async/sync boundary confusion** (M-14, M-15, L-05): The backend mixes synchronous blocking calls with asyncio, degrading server responsiveness.

5. **Dead/ineffective computation** (H-05, M-03, L-03, L-06): Code that looks functional but does nothing — computed values discarded, parameters ignored, middleware never connected.

### Cascading Effects

- **C-01 → Gapless playback completely broken**: The deadlock means gapless transitions never succeed. Users must manually skip tracks.
- **H-07 + H-03 → Compound audio corruption**: EQ pads samples AND changes dtype. A short chunk processed by EQ grows in size (H-07) and loses precision (H-03).
- **H-04 + M-08 → Double dynamic distortion**: The realtime tanh limiter compresses dynamics (H-04), then the compressor applies chunk-level gain (M-08), causing pumping + saturation.

---

## Prioritized Fix Order

### Tier 1: Fix immediately (blocks core functionality)
1. **C-01**: GaplessPlaybackEngine deadlock — Change `Lock` to `RLock` (1-line fix)
2. **H-07**: EQ padding sample count — Store and restore original length
3. **H-05**: Transient enhancer dead computation — Assign computed values
4. **H-01**: PlaybackController thread safety — Add RLock

### Tier 2: Fix before release (audio quality / security)
5. **H-04**: Tanh limiter — Only apply to samples above threshold
6. **H-03**: EQ dtype forcing — Preserve input dtype
7. **H-06**: Stereo FFT — Convert to mono before analysis
8. **H-09**: WebSocket authentication — Add token validation
9. **M-04**: PsychoacousticEQ reset — Change `np.ones` to `np.zeros`
10. **H-08**: Vite env vars — Change to `import.meta.env.VITE_*`

### Tier 3: Fix within 2 sprints (reliability / performance)
11. **M-14**: Async lock in state manager
12. **M-13**: Broadcast list mutation
13. **M-10**: Job dict memory leak
14. **M-09**: FFmpeg sample rate hardcoding
15. **M-18**: CORS configuration
16. **M-19**: Rust panic handler
17. **H-02**: State setter bypass

### Tier 4: Fix opportunistically (quality / maintenance)
18. Remaining MEDIUM and LOW findings

---

## Cross-Cutting Recommendations

### 1. Enforce Audio Invariants with Runtime Checks
Add a decorator or wrapper that asserts `len(output) == len(input)` and `output.dtype == input.dtype` after every DSP function. This catches violations like H-03, H-07 at development time.

### 2. Standardize Thread Safety Policy
Decide on one approach: `threading.RLock` for the player (Python threads), `asyncio.Lock` for the backend (async code). Document which lock type to use where. Add a linting rule.

### 3. Add Unbounded Collection Linting
Audit all `dict`, `list`, `Map`, `Set` collections that grow without eviction. Add size limits or TTL to all caches.

### 4. Async/Sync Boundary Discipline
All backend handlers that touch files or subprocesses must use `asyncio.to_thread()` or async subprocess APIs. Add a custom pylint rule to flag `subprocess.run()` and `open()` inside `async def`.

### 5. DSP Integration Tests
Add tests that pipe audio through the full chain (load → analyze → EQ → dynamics → limiter → encode) and assert: sample count preserved, dtype preserved, no NaN/Inf, peaks within [-1, 1], SNR above threshold.
