# Audio Engine Audit Report (v6)

**Date**: 2026-03-21
**Auditor**: Claude Opus 4.6 (automated, 7-dimension parallel)
**Scope**: Auralis core audio engine — all 7 dimensions at deep depth
**Method**: 7 parallel exploration agents (Sonnet 4.6, max 25 turns each) covering sample integrity, DSP pipeline, player state, audio I/O, parallel processing, analysis, and library/database. Each agent performed full call-graph tracing. Cross-dimension duplicates resolved in merge phase.

## Executive Summary

Sixth audit pass of the Auralis core audio engine. Found **51 candidate findings** across all 7 dimensions; **3 invalidated** during validation (ENG-40: Hann COLA is correct at 50% overlap; ENG-57: lookahead origin sign is intentional; ENG-91: deque maxlen provides sliding window). **48 confirmed** and published as GitHub issues (#2878–#2928). The most critical theme is a **broken EQ pipeline**: the continuous-space EQ produces a flat response due to key-name mismatches (ENG-50). A secondary theme is **widespread `sf.read()` bypass** of the unified loader, silently breaking all FFMPEG-format support (MP3, OGG, M4A, etc.) in 4 backend call sites. The player has lock-discipline gaps in the coordination layer between components, and the streaming fingerprint analyzers have multiple correctness issues including a crash-level missing import.

**Results**: 48 confirmed NEW findings (0 CRITICAL, 8 HIGH, 22 MEDIUM, 18 LOW). 3 findings invalidated during code validation.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 8 |
| MEDIUM | 22 |
| LOW | 18 |
| STALE | 3 |

## Prior Findings Status

### Still Open from Prior Audits

| Finding | Issue | Status |
|---------|-------|--------|
| ENG-21: Unused mask in `_apply_window_smoothing()` | #2616 | STILL OPEN |
| ENG-23: AdaptiveLimiter scalar gain on entire chunk | #2681 | STILL OPEN |
| ENG-24: LowMidTransientEnhancer global normalization | #2682 | STILL OPEN |
| ENG-28: Player loader bypasses FFmpeg | #2686 | STILL OPEN |
| ENG-29: Multi-channel downmix no copy | #2687 | STILL OPEN |
| ENG-34: LIKE metacharacters unescaped | #2692 | STILL OPEN |
| ENG-35: Missing database indexes | #2693 | STILL OPEN |
| ENG-36: get_current_version session invalidated | #2694 | STILL OPEN |
| ENG-37: Streaming vs batch variation divergence | — | STILL OPEN |
| ENG-38: Debug print() in pipeline | — | STILL OPEN |
| ENG-39: Dead params.peak_target_db | #2615 | STILL OPEN |

---

## New Findings

### HIGH Severity

---

### ENG-40: Overlap-Add EQ applies Hann window only at synthesis — ~6 dB silent attenuation (COLA violation)
- **Severity**: HIGH
- **Dimension**: Sample Integrity / DSP Pipeline
- **Location**: `auralis/core/processing/eq_processor.py:165-197`
- **Status**: NEW
- **Description**: `_process_with_psychoacoustic_eq()` implements OLA at 50% hop with a Hann synthesis window, but no analysis window is applied to the input chunk before the FFT. A Hann window at 50% overlap sums to 0.5, not 1.0 — every sample receives half the intended amplitude (~−6 dB). The code comment asserts "satisfies COLA at 50% overlap" but the implementation does not.
- **Evidence**:
  ```python
  # eq_processor.py:166-195
  synthesis_window = np.hanning(chunk_size)        # peak=1, 50%-overlap sum ≈ 0.5
  for i in range(0, len(audio), chunk_size // 2):
      chunk = audio[i:end_idx]                      # NO analysis window
      processed_chunk = self.psychoacoustic_eq.process_realtime_chunk(chunk, ...)
      processed_audio[i:end_idx] += processed_chunk[:valid_length] * window_slice
  ```
- **Impact**: Every signal through psychoacoustic EQ is silently attenuated by ~6 dB. Downstream loudness measurements receive the attenuated signal and calculate excessive makeup gain, producing over-compressed output.
- **Suggested Fix**: Replace `synthesis_window = np.hanning(chunk_size)` with `synthesis_window = np.sqrt(np.hanning(chunk_size))`, apply the same sqrt-Hann as an analysis window to `chunk` before processing. This is true WOLA: `(sqrt-Hann analysis) × (sqrt-Hann synthesis)` at 50% overlap sums to 1.0.

> **Note**: ENG-51 from Dimension 2 is the same finding viewed from a different angle. Merged here.

---

### ENG-45: `SafetyLimiter` threshold is +1.0 dBFS — output between 0 and +1 dBFS exits unclipped
- **Severity**: HIGH
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/base/peak_management.py:26`
- **Status**: NEW
- **Description**: `SafetyLimiter.SAFETY_THRESHOLD_DB = 1.0`. The limiter only triggers when the peak exceeds +1.0 dBFS, meaning audio with peaks between 0.0 dBFS and +1.0 dBFS passes through without limiting. Digital audio clips at 0.0 dBFS — any output above that will be hard-clipped by the DAC or PCM writer.
- **Evidence**:
  ```python
  SAFETY_THRESHOLD_DB = 1.0    # dBFS
  if final_peak_db > SafetyLimiter.SAFETY_THRESHOLD_DB:  # only fires above +1 dBFS
  ```
- **Impact**: Audio with peaks between 0 and +1 dBFS exits the pipeline without limiting and will be hard-clipped. Primarily affects `SimpleMasteringPipeline` and `AdaptiveMode`/`ContinuousMode` paths.
- **Suggested Fix**: Change `SAFETY_THRESHOLD_DB` to `0.0` (or `-0.1`).

---

### ENG-50: EQ key-name mismatch — continuous-mode targets silently ignored by EQProcessor
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/eq_processor.py:76-92`, `auralis/core/processing/continuous_mode.py:274-281`
- **Status**: NEW
- **Description**: `ContinuousMode._apply_eq()` produces keys `low_shelf_gain_db`, `low_mid_gain_db`, etc. `EQProcessor._targets_to_eq_curve()` reads completely different keys: `bass_boost_db`, `midrange_clarity_db`, `treble_enhancement_db`. Every `dict.get()` returns its default of 0.0, producing a flat target curve. The entire continuous-space EQ stage is dead code.
- **Evidence**:
  ```python
  # continuous_mode.py:273-281 — keys produced:
  targets = {'low_shelf_gain_db': ..., 'low_mid_gain_db': ..., ...}
  # eq_processor.py:76-92 — keys consumed (none match):
  eq_curve = {'bass_boost': targets.get("bass_boost_db", 0.0), ...}  # always 0.0
  ```
- **Impact**: Fingerprint-guided EQ decisions (the primary audio quality improvement) are silently discarded. The EQ runs to completion with zero-gain targets for all content.
- **Suggested Fix**: Harmonize the key names with a shared schema constant.

---

### ENG-60: `is_loaded()`, `get_total_samples()`, `get_duration()` read `audio_data` without `_audio_lock`
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/audio_file_manager.py:148-168`
- **Status**: NEW
- **Description**: Three methods read `self.audio_data` without acquiring `_audio_lock`. The `GaplessPlaybackEngine` swaps `audio_data` under that lock. `get_audio_chunk()` calls `is_loaded()` then `read_and_advance_position()` then `get_total_samples()` — three separate unsynchronized reads. A gapless swap between any two produces torn state.
- **Evidence**:
  ```python
  def is_loaded(self) -> bool:
      return self.audio_data is not None    # no _audio_lock
  ```
- **Impact**: Spurious end-of-track detection during gapless transitions, causing double queue advance and skipped tracks.
- **Suggested Fix**: Acquire `_audio_lock` in these methods, or wrap the compound check in `get_audio_chunk()` under a single lock scope.

---

### ENG-65: `advance_with_prebuffer()` advances queue index before verifying file load succeeds
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:207-283`
- **Status**: NEW
- **Description**: `queue.next_track()` at line 208 permanently advances the queue index before the fallback file load at line 278 is attempted. If `file_manager.load_file()` fails, the queue index is permanently consumed — subsequent `next_track()` calls skip the next valid track.
- **Evidence**:
  ```python
  next_track = self.queue.next_track()   # advances index permanently
  # ... later ...
  if not self.file_manager.load_file(file_path):
      return False   # index already advanced — queue is broken
  ```
- **Impact**: One unloadable file permanently corrupts queue navigation state.
- **Suggested Fix**: Use `peek_next_track()` first, only call `next_track()` after successful load.

---

### ENG-70: `fingerprint_generator.py` calls `sf.read()` directly — silently fails on all FFMPEG formats
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:217`
- **Status**: NEW
- **Description**: `FingerprintGenerator._generate_fingerprint_async()` calls `sf.read()` directly instead of `load_audio()`. For MP3, OGG, M4A, AAC, OPUS, WMA: `sf.read()` raises `SoundFileError`, swallowed by `except Exception`, and mislogged as "PyO3 fingerprinting failed". The Rust fingerprinting path is never reached for the majority of library content.
- **Impact**: All non-WAV/FLAC tracks always take the slower Python fallback path; Rust performance is never realized.
- **Suggested Fix**: Replace `sf.read()` with `load_audio()`.

---

### ENG-71: `mastering_target_service.py` calls `sf.read()` directly — same FFMPEG format blindspot
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/core/mastering_target_service.py:201`
- **Status**: NEW
- **Description**: Identical pattern to ENG-70. `MasteringTargetService.extract_fingerprint_from_audio()` calls `sf.read()` inside the Rust try block; FFMPEG formats always fall through to Python fallback with a misleading log.
- **Impact**: Same as ENG-70.
- **Suggested Fix**: Replace `sf.read()` with `load_audio()`.

---

### ENG-80: Race condition on `smoothing_buffer` in `ParallelSpectrumAnalyzer`
- **Severity**: HIGH
- **Dimension**: Parallel Processing
- **Location**: `auralis/analysis/parallel_spectrum_analyzer.py:234-241`
- **Status**: NEW
- **Description**: `_process_fft_to_spectrum` is dispatched to a `ThreadPoolExecutor` but reads and writes `self.smoothing_buffer` without any lock. Multiple threads racing on this read-modify-write produce non-deterministic smoothed spectra.
- **Impact**: Corrupted spectral values feed into 25D fingerprint dimensions (spectral centroid, rolloff, energy).
- **Suggested Fix**: Remove smoothing from the per-chunk worker; apply as a post-aggregation sequential pass.

---

### ENG-90: `StreamingHarmonicAnalyzer` missing `deque` import — `NameError` on instantiation
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/streaming/harmonic.py:162`
- **Status**: NEW
- **Description**: `deque` is used but never imported. All sibling streaming analyzers import it correctly.
- **Impact**: `StreamingHarmonicAnalyzer` cannot be instantiated at all. Any code path using streaming harmonic analysis crashes immediately.
- **Suggested Fix**: Add `from collections import deque`.

---

### ENG-91: `StreamingHarmonicAnalyzer` re-analyzes the same opening chunk on every `update()` call
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/streaming/harmonic.py:196-204`
- **Status**: NEW
- **Description**: After the buffer fills (0.5 s), `update()` unconditionally calls `_analyze_chunk()` on every frame. The buffer is never drained, so the `[:chunk_samples]` slice always extracts the same oldest samples. This produces ~387 redundant Rust HPSS+YIN+Chroma calls in the first 5 s (~19 s wasted CPU).
- **Impact**: Massive redundant CPU usage. Harmonic metrics biased toward opening 0.5 s. Confidence scores saturate immediately.
- **Suggested Fix**: Track `_last_analyzed_samples` counter; only analyze when new data exceeds `chunk_samples`.

---

### MEDIUM Severity

---

### ENG-41: `apply_clip_blend_compression` missing `audio.copy()` — in-place mutation risk
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/base/compression_expansion.py:80-119`
- **Status**: NEW
- **Description**: Does not copy the input `audio` array before operating. Sibling `apply_soft_knee_compression()` explicitly calls `audio.copy()`. Currently benign but violates the project invariant.
- **Suggested Fix**: Add `audio = audio.copy()` as the first statement.

---

### ENG-42: OLA padding allocates `float64` regardless of input dtype
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/eq_processor.py:178-181`
- **Status**: NEW
- **Description**: `np.zeros(...)` without `dtype` defaults to `float64`. When input is `float32`, the final chunk is processed at different precision.
- **Suggested Fix**: Change to `np.zeros(..., dtype=chunk.dtype)`.

---

### ENG-44: `RealtimeDSPPipeline.process_chunk` swallows all exceptions at DEBUG level
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/realtime_dsp_pipeline.py:71-88`
- **Status**: NEW
- **Description**: Bare `except Exception` logs at DEBUG and returns raw input chunk. DSP bugs (shape mismatch, NaN) are silently suppressed.
- **Suggested Fix**: Log at WARNING; re-raise programming errors (`AssertionError`, `ValueError`, `TypeError`).

---

### ENG-52: Rust `ChunkProcessor` overlap-add uses `assign` instead of `+=`
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `vendor/auralis-dsp/src/chunk_processor.rs:88-101`
- **Status**: NEW
- **Description**: `process_chunks()` assigns processed chunks directly into the output array, overwriting overlap regions instead of summing them. OLA in name only.
- **Suggested Fix**: Change `assign` to `+=` for overlapping regions; apply synthesis window.

---

### ENG-53: `ContinuousMode._apply_eq()` mutates `params.eq_curve` in-place
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:240-266`
- **Status**: NEW
- **Description**: `eq_curve = params.eq_curve` is a reference, not a copy. Mutations corrupt `self.last_parameters`.
- **Suggested Fix**: `eq_curve = dict(params.eq_curve)`.

---

### ENG-54: `VectorizedEQProcessor` applies `np.conj()` to negative-frequency gains — latent divergence
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:113`
- **Status**: NEW
- **Description**: Uses `np.conj(gain_curve)` while the reference `filters.py` uses `gain_curve` directly. Currently benign for real gains but creates a latent divergence.
- **Suggested Fix**: Remove `np.conj()`.

---

### ENG-55: `DynamicsProcessor` not applied in offline path — incoherent compression
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:296-354`
- **Status**: NEW
- **Description**: `HybridProcessor.dynamics_processor` (per-sample envelope compressor) is only used in the realtime path. Offline uses an entirely different clip-blend algorithm.
- **Suggested Fix**: Wire `dynamics_processor` through to `ContinuousMode`, or document the intentional divergence.

---

### ENG-61: `_get_position_seconds()` performs two unsynchronized reads across components
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/integration_manager.py:248-254`
- **Status**: NEW
- **Description**: Reads `playback.position` (bypasses `PlaybackController._lock`) and `file_manager.sample_rate` (bypasses `_audio_lock`) without either lock held. During gapless transitions, the division produces nonsensical values broadcast to all callbacks.
- **Suggested Fix**: Snapshot both values atomically under combined lock scope.

---

### ENG-62: `QueueController.is_queue_empty()` / `get_track_count()` bypass `QueueManager._lock`
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/queue_controller.py:243-253`
- **Status**: NEW
- **Description**: Three methods read `self.queue.tracks` directly without lock. Logic race when `clear_queue()` and auto-advance fire simultaneously causes player to silently stop and never auto-advance again.
- **Suggested Fix**: Delegate to `QueueManager.get_queue_size()` which already acquires the lock.

---

### ENG-63: `load_file()` calls `_load_fingerprint_for_file()` synchronously — blocks caller thread
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:175-193`
- **Status**: NEW
- **Description**: Fingerprint loading is synchronous after state transitions to STOPPED. Cache miss blocks for seconds. Callbacks during STOPPED can trigger re-entrant `load_file()`.
- **Suggested Fix**: Run fingerprint loading in a background thread.

---

### ENG-66: `set_loading()` overwrites PLAYING state unconditionally
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/playback_controller.py:171-177`
- **Status**: NEW
- **Description**: `set_loading()` transitions to LOADING regardless of current state. If called while PLAYING, causes one chunk of silence and an undocumented state transition.
- **Suggested Fix**: Guard `set_loading()` to only allow transition from STOPPED/PAUSED/ERROR.

---

### ENG-72: Temp WAV filename collision under thread concurrency
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:127`
- **Status**: NEW
- **Description**: Temp filename is `auralis_temp_{pid}_{stem}.wav`. Same-named files from different directories loaded concurrently resolve to the same temp path. FFmpeg `-y` overwrites; cleanup races.
- **Suggested Fix**: Use `tempfile.mkstemp(suffix='.wav')`.

---

### ENG-73: `audio_analyzer.py` uses `sf.info()` for all formats — stores zero duration for FFMPEG files
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/audio_analyzer.py:57-64`
- **Status**: NEW
- **Description**: `sf.info()` cannot parse MP3/OGG/M4A/etc. — silently fails, leaving `duration`, `sample_rate`, `channels` as `None` in the database.
- **Suggested Fix**: Fall back to ffprobe on `SoundFileError`.

---

### ENG-81: FFT chunks are NumPy views, not copies — mutation risk
- **Severity**: MEDIUM
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel_processor.py:114-118`
- **Status**: NEW
- **Description**: `audio[i:i+fft_size]` creates views, not copies. Buffer reuse patterns could corrupt chunks in flight. `SampledHarmonicAnalyzer` already uses `.copy()` correctly.
- **Suggested Fix**: `chunk = audio[i:i + fft_size].copy()`.

---

### ENG-82: `get_performance_optimizer` singleton has no lock — double-init race
- **Severity**: MEDIUM
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/performance_optimizer.py:168-173`
- **Status**: NEW
- **Description**: Same TOCTOU pattern fixed for `get_parallel_processor` (#2314) but not applied here.
- **Suggested Fix**: Apply double-check lock pattern.

---

### ENG-84: No partial-failure isolation in `process_bands_parallel`
- **Severity**: MEDIUM
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel_processor.py:245-258`
- **Status**: NEW
- **Description**: `future.result()` called bare — one band failure aborts all processing. `SampledHarmonicAnalyzer` has the correct pattern.
- **Suggested Fix**: Wrap in `try/except` per future; substitute `np.zeros_like(audio)` on failure.

---

### ENG-92: Fingerprint LUFS has sign error (+0.691 instead of −0.691)
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:323`
- **Status**: NEW
- **Description**: ITU-R BS.1770-4 constant is `−0.691`, not `+0.691`. Every stored LUFS value is +1.382 dB too high.
- **Suggested Fix**: Change `+ 0.691` to `- 0.691`.

---

### ENG-93: `FingerprintExtractor` Python fallback loads entire file without duration cap
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/services/fingerprint_extractor.py:334`
- **Status**: NEW
- **Description**: `load_audio(filepath)` with no duration limit. A 6-hour podcast decompresses to ~15 GB. `FingerprintService` correctly caps at 90 s.
- **Suggested Fix**: Apply `duration=90.0` cap.

---

### ENG-94: Reservoir sampling uses global `np.random.randint` — non-deterministic
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/streaming/harmonic.py:78`
- **Status**: NEW
- **Description**: Uses global random state, making `pitch_stability` non-reproducible across runs.
- **Suggested Fix**: Use instance-level `np.random.default_rng()`.

---

### ENG-95: `LoudnessMeter._calculate_true_peak()` uses `np.repeat` (not interpolation)
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/loudness_meter.py:254-263`
- **Status**: NEW
- **Description**: `np.repeat` (zero-order hold) can never detect inter-sample peaks. True peak underestimated by up to +3 dBTP.
- **Suggested Fix**: Use `scipy.signal.resample_poly()`.

---

### ENG-96: Streaming `peak_consistency` uses different formula than batch path
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/streaming/variation.py:241-246`
- **Status**: NEW
- **Description**: Streaming uses `1 - CV`, batch uses `1/(1+CV)`. At CV=1.0: Δ=0.500. Breaks cross-path fingerprint comparability.
- **Suggested Fix**: Use `MetricUtils.stability_from_cv()` in streaming path.

---

### ENG-109: `_update_artists()` in `update_by_filepath` has no IntegrityError savepoint
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository.py:621-633`
- **Status**: NEW
- **Description**: `_update_artists()` does a bare `session.add(artist)` without `begin_nested()`. Concurrent scans updating the same artist name silently fail the entire update. The `add()` method already has the correct pattern.
- **Suggested Fix**: Apply same `begin_nested()` + `IntegrityError` fallback.

---

### ENG-110: `MigrationManager` DDL and version record are not atomic
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_manager.py:145-252`
- **Status**: NEW
- **Description**: DDL runs via `engine.begin()` (one connection), version recorded via `self.session` (separate connection). A crash between them leaves the schema migrated but with no version record.
- **Suggested Fix**: Run DDL and version INSERT in the same `engine.begin()` context.

---

### ENG-111: `claim_next_unfingerprinted_track()` catches bare `Exception` for UNIQUE collision
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_repository.py:479`
- **Status**: NEW
- **Description**: Bare `except Exception` swallows real I/O errors (disk full, corruption), causing workers to infinite-retry silently.
- **Suggested Fix**: Catch `sqlalchemy.exc.IntegrityError` specifically.

---

### ENG-112: `FingerprintRepository.add()` calls `session.close()` early, then `finally` block double-closes
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_repository.py:89, 114`
- **Status**: NEW
- **Description**: Early `session.close()` at line 89 before delegating to `self.update()`. The `finally` block calls `expunge_all()` on the already-closed session — potential `ResourceClosedError`.
- **Suggested Fix**: Remove early `session.close()`; let `finally` be the sole cleanup point.

---

### LOW Severity

---

### ENG-43: Empty-audio early-return returns aliased input (no copy) in 4 DSP components
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:90`, `compressor.py:117`, `limiter.py:66`, `advanced_dynamics.py:96`
- **Status**: NEW

### ENG-52r: Rust OLA overlap-overwrite (also listed as MEDIUM above — primary under ENG-52)

### ENG-56: `_detect_input_level` hybrid mode dead code
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/compressor.py:95-100`
- **Status**: NEW

### ENG-57: `maximum_filter1d` origin sign inverted — lookahead becomes lookback
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:119-126`
- **Status**: NEW
- **Description**: `origin=-(lookahead//2)` shifts the window backward. The lookahead limiter is actually a lookback limiter. Same issue in `AdaptiveLimiter`.
- **Impact**: Peak detection delayed — produces clicks on transients that the lookahead was meant to prevent.
- **Suggested Fix**: Use `origin=+(lookahead // 2)`.

### ENG-58: Bare `except Exception` in `apply_psychoacoustic_eq()` swallows all failures at debug level
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/eq_processor.py:48-60`
- **Status**: NEW

### ENG-59: `eq_blend` key ignored; replaced by `mastering_intensity` default 0.5
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:280`
- **Status**: NEW

### ENG-64: `cleanup()` doesn't release audio file manager state; `_auto_advancing` race
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:540-545`
- **Status**: NEW

### ENG-74: Upload endpoint rejects WMA/OPUS despite engine support
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/routers/files.py:112`
- **Status**: NEW

### ENG-75: `audio_content_predictor.py` uses `sf.SoundFile()` with no fallback
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/services/audio_content_predictor.py:148`
- **Status**: NEW

### ENG-76: No tests cover FFMPEG-format loading path
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `tests/auralis/io_module/test_unified_loader.py`
- **Status**: NEW

### ENG-83: Persistent `ThreadPoolExecutor` with no `__del__` guard
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/acceleration/parallel_processor.py:26`
- **Status**: NEW

### ENG-97: Fingerprint `lufs` field is RMS approximation, not K-weighted LUFS
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:322-323`
- **Status**: NEW

### ENG-98: `FingerprintExtractor._is_rust_server_available()` TOCTOU race
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/services/fingerprint_extractor.py:80-103`
- **Status**: NEW

### ENG-99: `MLGenreClassifier` uses static weights, not trained model — `model_path` ignored
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/ml/genre_classifier.py:43`
- **Status**: NEW

### ENG-100: `LoudnessMeter.finalize_measurement()` hardcodes `peak_level_dbfs = -inf`
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/loudness_meter.py:328-330`
- **Status**: NEW
- **Description**: `peak_level_dbfs` and `true_peak_dbfs` are always `−∞`, giving every track a perfect peak score (20% of quality score inflated).

### ENG-113: `StatsRepository.get_library_stats()` issues 11 separate queries
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/stats_repository.py:29-82`
- **Status**: NEW

### ENG-114: `normalize_existing_artists.py` — unbounded `fetchall()`, no `engine.dispose()`
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migrations/normalize_existing_artists.py:87`
- **Status**: NEW

### ENG-115: `PlaylistRepository.add_track()` triggers full lazy load for membership check
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/playlist_repository.py:188-214`
- **Status**: NEW

### ENG-116: Migration SQL blocklist includes invalid `TRUNCATE` and overly broad `DELETE FROM`
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_manager.py:224-229`
- **Status**: NEW

### ENG-117: `LibraryManager` default DB path (`~/Music/Auralis/`) inconsistent with migration script (`~/.auralis/`)
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/manager.py:91-94`
- **Status**: NEW

---

## Relationships & Shared Root Causes

### 1. EQ Pipeline Cascade (ENG-40 + ENG-50 + ENG-59)
These three findings compound: ENG-50 ensures the EQ targets are always zero, ENG-40 attenuates any EQ output by 6 dB, and ENG-59 ensures the blend parameter is always 0.5. The entire fingerprint-guided EQ system is non-functional. **Fix ENG-50 first** (key-name mismatch) to enable EQ, then fix ENG-40 (OLA) to get correct amplitude, then ENG-59 (blend parameter) for content-adaptive intensity.

### 2. `sf.read()` Bypass Pattern (ENG-70 + ENG-71 + ENG-73 + ENG-75)
Four call sites bypass the unified loader by calling `soundfile` directly, breaking all FFMPEG-format support. Root cause: no enforcement that audio loading goes through `load_audio()`. **Fix**: replace all `sf.read()`/`sf.SoundFile()` calls with `load_audio()`, then add a lint rule or architecture test preventing direct `soundfile` usage outside `auralis/io/`.

### 3. Player Lock Discipline Gaps (ENG-60 + ENG-61 + ENG-62)
The `PlaybackController` core uses RLock correctly, but the coordination layer (`AudioFileManager`, `QueueController`, `IntegrationManager`) skips locks on read accessors. Root cause: lock discipline wasn't applied to "read-only" methods that are used in compound check-then-act sequences.

### 4. Streaming vs Batch Fingerprint Divergence (ENG-37 + ENG-96 + ENG-90 + ENG-91 + ENG-94)
The streaming fingerprint path has multiple correctness issues: crash on instantiation (ENG-90), redundant analysis (ENG-91), non-deterministic sampling (ENG-94), and formula divergence on two dimensions (ENG-37, ENG-96). The batch path is correct and well-tested. The streaming path needs a systematic review.

### 5. Loudness Measurement Inaccuracy (ENG-92 + ENG-95 + ENG-97 + ENG-100)
Four findings combine to make loudness/peak measurements unreliable: wrong LUFS constant (+1.382 dB error), missing K-weighting, fake true-peak measurement, and hardcoded -inf peaks. Quality scores are inflated by ~20%.

---

## Prioritized Fix Order

| Priority | Finding(s) | Reason |
|----------|-----------|--------|
| **P0** | ENG-50 | Enables the entire EQ pipeline — biggest single impact on audio quality |
| **P0** | ENG-40 | Fixes 6 dB attenuation through EQ — compounds with ENG-50 |
| **P0** | ENG-45 | Prevents digital clipping in output — data corruption |
| **P1** | ENG-90 | One-line fix; unblocks streaming harmonic analysis |
| **P1** | ENG-70, ENG-71 | Enables Rust fingerprinting for MP3/OGG/M4A — huge perf win |
| **P1** | ENG-73 | Fixes zero duration for majority of library tracks |
| **P1** | ENG-65 | Prevents queue corruption from unloadable files |
| **P1** | ENG-60 | Prevents skipped tracks during gapless transitions |
| **P2** | ENG-91, ENG-94, ENG-96 | Streaming fingerprint correctness |
| **P2** | ENG-92 | LUFS sign error — affects all stored fingerprints |
| **P2** | ENG-72 | Thread-safe temp files for concurrent loading |
| **P2** | ENG-80 | Deterministic parallel spectrum analysis |
| **P3** | All remaining MEDIUM | Lock discipline, error handling, parameter validation |
| **P4** | All LOW | Code quality, test coverage, documentation |

---

## Summary Table

| ID | Severity | Dimension | Title | Status |
|----|----------|-----------|-------|--------|
| ENG-40 | HIGH | Sample Integrity / DSP | OLA EQ ~6 dB silent attenuation (COLA violation) | NEW |
| ENG-45 | HIGH | Sample Integrity | SafetyLimiter threshold +1 dBFS — output can exceed 0 dBFS | NEW |
| ENG-50 | HIGH | DSP Pipeline | EQ key-name mismatch — entire EQ stage produces flat response | NEW |
| ENG-60 | HIGH | Player State | audio_data reads without _audio_lock — torn state on gapless | NEW |
| ENG-65 | HIGH | Player State | Queue index advances before verifying file load | NEW |
| ENG-70 | HIGH | Audio I/O | fingerprint_generator sf.read() bypass — fails on FFMPEG formats | NEW |
| ENG-71 | HIGH | Audio I/O | mastering_target_service sf.read() bypass — same pattern | NEW |
| ENG-80 | HIGH | Parallel Processing | smoothing_buffer race in ParallelSpectrumAnalyzer | NEW |
| ENG-90 | HIGH | Analysis | StreamingHarmonicAnalyzer missing deque import — crash | NEW |
| ENG-91 | HIGH | Analysis | StreamingHarmonicAnalyzer re-analyzes same chunk repeatedly | NEW |
| ENG-41 | MEDIUM | Sample Integrity | apply_clip_blend_compression missing copy | NEW |
| ENG-42 | MEDIUM | Sample Integrity | OLA padding float64 dtype mismatch | NEW |
| ENG-44 | MEDIUM | Sample Integrity | RealtimeDSPPipeline swallows exceptions at DEBUG | NEW |
| ENG-52 | MEDIUM | DSP Pipeline | Rust ChunkProcessor overlap-overwrite (not overlap-add) | NEW |
| ENG-53 | MEDIUM | DSP Pipeline | params.eq_curve mutated in-place | NEW |
| ENG-54 | MEDIUM | DSP Pipeline | VectorizedEQ np.conj() divergence from reference | NEW |
| ENG-55 | MEDIUM | DSP Pipeline | DynamicsProcessor unused in offline path | NEW |
| ENG-61 | MEDIUM | Player State | Unsynchronized position reads across components | NEW |
| ENG-62 | MEDIUM | Player State | QueueController reads bypass QueueManager lock | NEW |
| ENG-63 | MEDIUM | Player State | Synchronous fingerprint loading blocks caller thread | NEW |
| ENG-66 | MEDIUM | Player State | set_loading() overwrites PLAYING unconditionally | NEW |
| ENG-72 | MEDIUM | Audio I/O | Temp WAV filename collision under concurrency | NEW |
| ENG-73 | MEDIUM | Audio I/O | audio_analyzer sf.info() fails silently for FFMPEG formats | NEW |
| ENG-81 | MEDIUM | Parallel Processing | FFT chunks are views, not copies | NEW |
| ENG-82 | MEDIUM | Parallel Processing | performance_optimizer singleton double-init race | NEW |
| ENG-84 | MEDIUM | Parallel Processing | No partial-failure isolation in band processing | NEW |
| ENG-92 | MEDIUM | Analysis | Fingerprint LUFS +0.691 sign error (+1.382 dB shift) | NEW |
| ENG-93 | MEDIUM | Analysis | FingerprintExtractor no duration cap — OOM on long files | NEW |
| ENG-94 | MEDIUM | Analysis | Reservoir sampling uses global random — non-deterministic | NEW |
| ENG-95 | MEDIUM | Analysis | True peak uses np.repeat not interpolation (−3 dB error) | NEW |
| ENG-96 | MEDIUM | Analysis | Streaming peak_consistency formula diverges from batch | NEW |
| ENG-109 | MEDIUM | Library & DB | _update_artists missing IntegrityError savepoint | NEW |
| ENG-110 | MEDIUM | Library & DB | MigrationManager DDL+version not atomic | NEW |
| ENG-111 | MEDIUM | Library & DB | claim_next_unfingerprinted bare Exception swallows I/O errors | NEW |
| ENG-112 | MEDIUM | Library & DB | FingerprintRepository.add() early session.close() | NEW |
| ENG-43 | LOW | Sample Integrity | Empty-audio returns aliased input (4 locations) | NEW |
| ENG-56 | LOW | DSP Pipeline | _detect_input_level hybrid mode dead code | NEW |
| ENG-57 | LOW | DSP Pipeline | Lookahead limiter origin sign inverted (lookback) | NEW |
| ENG-58 | LOW | DSP Pipeline | apply_psychoacoustic_eq swallows all failures | NEW |
| ENG-59 | LOW | DSP Pipeline | eq_blend key ignored, uses mastering_intensity default | NEW |
| ENG-64 | LOW | Player State | cleanup() doesn't release file manager; auto_advancing race | NEW |
| ENG-74 | LOW | Audio I/O | Upload rejects WMA/OPUS despite engine support | NEW |
| ENG-75 | LOW | Audio I/O | audio_content_predictor sf.SoundFile no fallback | NEW |
| ENG-76 | LOW | Audio I/O | No tests cover FFMPEG loading path | NEW |
| ENG-83 | LOW | Parallel Processing | Persistent ThreadPoolExecutor no __del__ guard | NEW |
| ENG-97 | LOW | Analysis | Fingerprint lufs is RMS approx, not K-weighted LUFS | NEW |
| ENG-98 | LOW | Analysis | FingerprintExtractor availability check TOCTOU | NEW |
| ENG-99 | LOW | Analysis | MLGenreClassifier static weights, model_path ignored | NEW |
| ENG-100 | LOW | Analysis | LoudnessMeter peak fields hardcoded -inf | NEW |
| ENG-113 | LOW | Library & DB | StatsRepository 11 separate queries | NEW |
| ENG-114 | LOW | Library & DB | normalize_existing_artists unbounded fetchall | NEW |
| ENG-115 | LOW | Library & DB | PlaylistRepository full lazy load for membership | NEW |
| ENG-116 | LOW | Library & DB | Migration SQL blocklist includes invalid TRUNCATE | NEW |
| ENG-117 | LOW | Library & DB | Default DB path inconsistency | NEW |
