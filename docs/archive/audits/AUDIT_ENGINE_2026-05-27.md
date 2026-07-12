# Audit — Engine — 2026-05-27

**Type**: Deep audit of the core audio engine — DSP pipeline, player, analysis, library, parallel processing
**Scope**: `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/optimization/`, `auralis/analysis/`, `auralis/library/`, `auralis/services/`, `vendor/auralis-dsp/`
**Dedup baseline**: `gh issue list --limit 200` → 29 open issues (snapshot at audit start)
**Prior reports**: `docs/audits/AUDIT_ENGINE_2026-05-26.md` (most recent)

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 1 |
| MEDIUM   | 7 |
| LOW      | 22 |
| **Total**| **30** |

The engine is in mature shape. Sample-integrity invariants (`len(output) == len(input)`, `.copy()` before in-place mutation, dtype preservation, NaN/Inf handling, output clamping) are well-defended in the main mastering chains with explicit `assert` statements at chunk boundaries (#3700) and after the brick-wall limiter (#2519). The player state machine has received intensive recent hardening (issue cluster #3656–#3727) covering lock ordering, atomic seek/swap, generation-counter staleness checks for fingerprint threads, and cleanup-aware auto-advance. The library subsystem uses comprehensive `selectinload()` / `joinedload()` for N+1 prevention, atomic `INSERT ... ON CONFLICT DO UPDATE` for fingerprint upserts (#3467 / #3459), and inter-process file locking for migrations.

**Key themes in residual findings**:

1. **Determinism** — Genre classifier ships with un-seeded `np.random.normal()` weights (ENG-1, HIGH). This is the single most impactful finding: the same audio is classified differently across instances, producing different EQ adaptations and therefore different masters.
2. **Multi-channel downmix** — Native WAV/FLAC loaders drop surround channels via `[:, :2]` instead of applying ITU-R BS.775 (ENG-3, MEDIUM). FFmpeg path was fixed in #3672; both native-loader sibling paths still have the bug.
3. **Dtype drift** — Several DSP modules still silently promote float32 → float64 (`RealtimeProcessor.process_chunk` final safety mul, `AdaptiveLimiter._oversample`, `soundfile_loader.load_with_soundfile`). Doubled per-chunk memory; partial regression of the #3658 / #3659 dtype-preservation effort.
4. **Partial-failure semantics** — `ParallelAudioProcessor.process_batch` uses `executor.map` and re-raises on first error, killing the whole batch (ENG-5, MEDIUM). `ParallelBandProcessor` does the right thing per-future; the batch helper does not.
5. **Resource lifecycle on cache eviction** — `_get_or_create_processor` LRU-evicts `HybridProcessor` instances but does not call `.close()` on the embedded `AudioFingerprintAnalyzer` (ENG-6, MEDIUM). Long-running sessions accumulate idle thread pools.

Most-impactful items to fix next: ENG-1 (genre nondeterminism), ENG-3 (surround downmix), ENG-5 (batch error handling), ENG-6 (analyzer executor lifecycle).

---

## Findings

### CRITICAL

*(none)*

### HIGH

---

#### ENG-1: Genre classifier weights are non-deterministic — same audio masters differently across invocations
- **Severity**: HIGH
- **Dimension**: DSP Pipeline / Analysis
- **Location**: `auralis/analysis/ml/genre_weights.py:32-56`, `auralis/analysis/ml/genre_classifier.py:38`, `auralis/core/analysis/content_analyzer.py:53`
- **Status**: NEW
- **Description**: `initialize_genre_weights()` populates per-genre feature weights with `np.random.normal(0, 0.1)` and ZERO seeding. `RuleBasedGenreClassifier.__init__` calls this once per instance. `ContentAnalyzer` creates a new classifier per instance, and the resulting genre prediction flows into `EQProcessor._apply_content_adjustments` where it scales `bass_boost`, `treble_boost`, `mid_boost` by up to 30%.
- **Evidence**:
  ```python
  # genre_weights.py:32-56
  weights[genre] = {
      'rms': np.random.normal(0, 0.1),
      ...
      'bias': np.random.normal(0, 0.1)
  }
  ```
  ```python
  # processing/eq_processor.py:128-138 — genre drives EQ:
  if primary_genre == "electronic":
      eq_curve['bass_boost'] *= 1.2
      eq_curve['treble_boost'] *= 1.1
  elif primary_genre == "classical":
      eq_curve['bass_boost'] *= 0.8
  ```
- **Impact**: Two consecutive masters of the same file diverge by the genre-adaptive EQ delta. Breaks A/B testing, profile regression testing, and user trust ("I mastered this twice and got different results"). Also violates the fingerprint-determinism invariant required for the analysis subsystem ("same file always produces same fingerprint").
- **Suggested Fix**: Seed deterministically before generation — `rng = np.random.default_rng(seed=0x6A52A1E5); rng.normal(...)`. Or replace the placeholder with a deterministic table of weights. The docstring already calls this a "simplified linear model representation… would be replaced with actual trained model weights" — at minimum the placeholder must be deterministic.

### MEDIUM

---

#### ENG-2: `apply_eq_gains` silently truncates samples when input is longer than `fft_size`
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity / DSP Pipeline
- **Location**: `auralis/dsp/eq/filters.py:85, 103`, `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:102, 124`
- **Status**: NEW
- **Description**: Both `apply_eq_mono()` and `VectorizedEQProcessor._apply_eq_mono_vectorized()` do `spectrum = fft(audio_mono[:fft_size])` and then `return processed_audio[:len(audio_mono)]`. If `len(audio_mono) > fft_size`, `processed_audio` only contains `fft_size` samples (the IFFT output length) — every sample past `fft_size` is silently dropped without raising or warning.
- **Evidence**:
  ```python
  # filters.py:85-103
  spectrum = fft(audio_mono[:fft_size])
  ...
  processed_audio = np.real(ifft(spectrum))     # length == fft_size
  return np.asarray(processed_audio[:len(audio_mono)], dtype=audio_mono.dtype)
  ```
- **Impact**: Today no caller in the engine passes `len(audio) > fft_size` to this function (`EQProcessor._process_with_psychoacoustic_eq` chunks at `fft_size`). The contract is fragile: any future caller that bypasses the chunking loop (a unit test, a future "fast path", an external integration) will produce shorter audio than input, invisible to upstream `assert processed_chunk.shape[1] == chunk.shape[1]` until it fires.
- **Siblings**: Same bug in both standard and vectorized EQ paths (4 locations).
- **Suggested Fix**: Raise (or pad+process+stitch) when `len(audio_mono) > fft_size`. Even an `assert len(audio_mono) <= fft_size` would surface the violation immediately.

---

#### ENG-3: Native WAV/FLAC loaders drop surround channels via `[:, :2]` instead of ITU-R downmix
- **Severity**: MEDIUM
- **Dimension**: Audio I/O / Sample Integrity
- **Location**: `auralis/io/loader.py:84-86`, `auralis/io/loaders/soundfile_loader.py:70-74`
- **Status**: NEW
- **Description**: For native-format files (`.wav`, `.flac`) with more than 2 channels, both Python loaders take only `audio_data[:, :2]`. This is a hard truncation that drops Center (vocals/dialogue), LFE, and surround channels. In 5.1 content: C, LFE, Ls, Rs are lost; only L/R are kept. FFmpeg path (#3672) properly uses `-ac 2` which applies the standard center→L+R at -3 dB downmix matrix. The two native-loader paths are now inconsistent with the FFmpeg path.
- **Evidence**:
  ```python
  # loader.py:84-86
  elif audio_data.shape[1] > 2:
      audio_data = audio_data[:, :2].copy()
  # soundfile_loader.py:70-74 — same pattern
  if audio_data.shape[1] > 2:
      audio_data = audio_data[:, :2].copy()
      warning(f"Converted {original_channels} channels to stereo")
  ```
- **Impact**: Vocals/dialogue silenced for 5.1 surround music releases (Center channel discarded). Affects mastering quality and fingerprint accuracy for multichannel content.
- **Related**: #3672 (FFmpeg path fixed); this is the matching fix for both native-loader paths.
- **Suggested Fix**: Apply ITU-R BS.775 downmix (`L_out = L + 0.707*C + 0.707*Ls`, `R_out = R + 0.707*C + 0.707*Rs`), then renormalize so peak ≤ 0 dBFS. Or route multi-channel through FFmpeg.

---

#### ENG-4: `RealtimeProcessor.process_chunk` breaks the copy-before-modify invariant on empty input AND promotes float32 → float64 in final safety limiter
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/player/realtime/processor.py:111-134`
- **Status**: NEW
- **Description**: Two issues in the same hot path:
  1. Line 111-112: `if audio is None or len(audio) == 0: return audio` returns the caller's array, not a copy. Every other early-return path in the engine (`HybridProcessor._process_impl:240`, `BrickWallLimiter.process:91`) returns `.copy()` here.
  2. Line 131-134: `max_val = np.max(np.abs(processed))` yields a float64 scalar; `processed * (target_peak / max_val)` then promotes a float32 chunk to float64 silently. This contradicts the dtype-preservation work done in #3658 / #3659 / #2450.
- **Evidence**:
  ```python
  if audio is None or len(audio) == 0:
      return audio                       # <-- not a copy
  ...
  max_val = np.max(np.abs(processed))    # float64 scalar
  if max_val > 0.95:
      target_peak = 0.95
      processed = processed * (target_peak / max_val)   # float32 -> float64
  ```
- **Impact**: Dtype promotion doubles per-chunk memory in the realtime path; mixed-dtype concatenation downstream is a fertile source of intermittent type errors. The empty-array early return is a latent foot-gun.
- **Suggested Fix**: Return `audio.copy()` on the empty branch. Cast `target_peak / max_val` to `processed.dtype` (e.g. `np.float32(target_peak / max_val)`).

---

#### ENG-5: `ParallelAudioProcessor.process_batch` has no per-file error handling — one file's failure aborts entire batch
- **Severity**: MEDIUM
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel_processor.py:489-521`
- **Status**: NEW
- **Description**: `process_batch` uses `executor.map(process_func, audio_files)` and `list(...)` to drain — `executor.map` re-raises the first exception, so a single corrupt file in a batch of 100 raises immediately and the remaining 99 results are discarded. This is the opposite of what `ParallelBandProcessor` does (per-future try/except with fallback, #3430). The `@parallelize` decorator at line 567 inherits the same bug.
- **Evidence**:
  ```python
  if self.config.use_multiprocessing:
      with ProcessPoolExecutor(max_workers=num_workers) as executor:
          results = list(executor.map(process_func, audio_files))    # one raise kills batch
  ```
- **Impact**: Batch tools (bulk fingerprint regeneration, batch mastering) fail-fast on the first bad file. Long-running batch jobs are not robust to single-file errors.
- **Suggested Fix**: Replace `executor.map(...)` with `executor.submit(...) + as_completed` and per-future try/except. Match the pattern at `parallel_processor.py:280-285`.

---

#### ENG-6: `AudioFingerprintAnalyzer.close()` is never called by any consumer — thread-pool leak on `HybridProcessor` cache eviction
- **Severity**: MEDIUM
- **Dimension**: Analysis / Resource Lifecycle
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:90-95`, `auralis/core/hybrid_processor.py:580-587`
- **Status**: NEW
- **Description**: `close()` shuts down the analyzer's 5-thread executor but is never invoked. `_get_or_create_processor` LRU-evicts `HybridProcessor` instances at line 580-587 without calling `close()` on the embedded `FingerprintService.analyzer`. With a 10-instance cache, up to **50 idle fingerprint threads** can accumulate in long-running sessions, never reclaimed.
- **Evidence**:
  ```python
  # hybrid_processor.py:580-587 — LRU evict, no close() of evicted instance
  while len(_processor_cache) > _PROCESSOR_CACHE_MAX_SIZE:
      evicted_key, _ = _processor_cache.popitem(last=False)
      debug(f"Evicted cached HybridProcessor (cache full): key={evicted_key}")
  ```
- **Impact**: Thread leak in long-running sessions. Each idle pool consumes ~16 MB (5 threads × ~3 MB default stack); 10 cached processors = ~160 MB pinned thread overhead. Pins Python interpreter state, preventing graceful shutdown.
- **Suggested Fix**: Call `evicted.fingerprint_analyzer.close()` on cache eviction. Add `HybridProcessor.close()` that propagates to all sub-component close methods. Wire to `LibraryManager.shutdown` / `AudioPlayer.cleanup`.

---

#### ENG-7: `PsychoacousticEQ.current_gains` / `processing_history` mutated without a lock — shared state on cached processor instance
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline / Concurrency
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:79-81, 248-261, 322-330`
- **Status**: NEW
- **Description**: `_smooth_gains()` writes `self.current_gains = adaptive_gains.copy()` and `_update_history()` mutates `self.processing_history` (`.append`, `.pop(0)`). Neither has any lock. `HybridProcessor` holds `_process_lock` (#3714) for `process()`, but `process_realtime_chunk` does NOT acquire it (line 390) — and the cached processor cache holds at most 10 instances but the SAME mode-key reuses the same instance, so two concurrent realtime callers race the gain-smoothing state.
- **Evidence**:
  ```python
  # psychoacoustic_eq.py — no lock anywhere
  def _smooth_gains(self, target_gains):
      ...
      self.current_gains = adaptive_gains.copy()
  def _update_history(self, gains, spectrum_analysis, content_profile):
      self.processing_history.append({...})
      if len(self.processing_history) > 100:
          self.processing_history.pop(0)
  ```
- **Impact**: Smoothed-gain transitions become jittery under concurrent realtime use. The user-visible artefact is band-EQ wobble — subtle but cumulative. The `processing_history.pop(0)` on empty list could raise `IndexError` under contention.
- **Suggested Fix**: Add a `threading.Lock` to `PsychoacousticEQ.__init__`, guard `_smooth_gains` and `_update_history`. Fine-grained (not the per-instance `_process_lock`) to keep realtime latency low.

---

#### ENG-8: `soundfile_loader.load_with_soundfile` returns float64 by default — inconsistent with `loader.py` sibling
- **Severity**: MEDIUM
- **Dimension**: Audio I/O / Dtype
- **Location**: `auralis/io/loaders/soundfile_loader.py:62`, `auralis/io/loader.py:66`
- **Status**: NEW
- **Description**: Two sibling loader functions both wrap soundfile but disagree on the read dtype: `loader.py:66` explicitly passes `dtype=np.float32`; `soundfile_loader.py:62` defaults to float64 for PCM ≥ 16-bit sources. `load_with_soundfile` is called from `unified_loader.load_audio:92` and the FFmpeg path (`ffmpeg_loader.py:180`). Downstream `validate_audio` casts to float32, but the intermediate is double the memory.
- **Evidence**:
  ```python
  # soundfile_loader.py:62 — float64
  audio_data, sample_rate = sf.read(str(file_path), always_2d=False)
  # loader.py:66 — float32
  audio_data, sample_rate = sf.read(file_path, dtype=np.float32, always_2d=True)
  ```
- **Impact**: A 7200 s × 96 kHz × 2 channel load peaks at ~5.3 GB float32 OR ~10.6 GB float64. The `unified_loader` path is the canonical entry, so any user loading a long-form WAV/FLAC via that path uses 2x peak RAM unnecessarily.
- **Suggested Fix**: Pass `dtype=np.float32` and `always_2d=True` to `sf.read` in `soundfile_loader.py:62`.

### LOW

---

#### ENG-9: `unified_loader.load_audio` normalize-on-load can silently promote dtype
- **Severity**: LOW
- **Dimension**: Sample Integrity / Audio I/O
- **Location**: `auralis/io/unified_loader.py:125-129`
- **Status**: NEW
- **Description**: `peak = np.max(np.abs(audio_data))` is a 0-d scalar; `audio_data / peak * 0.98` is dtype-stable in modern NumPy under weak-scalar promotion, but no dtype guard exists after normalize. The two loader entry points are inconsistent (`loader.load` always casts to float32; `unified_loader.load_audio` does not enforce post-normalize).
- **Suggested Fix**: After normalize, `audio_data.astype(audio_data.dtype, copy=False)` or move the dtype enforcement after normalize.

---

#### ENG-10: `BrickWallLimiter.process` crashes when `lookahead_samples == 0`
- **Severity**: LOW
- **Dimension**: Sample Integrity / Edge Cases
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:62, 130-136`
- **Status**: NEW
- **Description**: When `lookahead_ms=0`, `lookahead_samples=0`, and `maximum_filter1d(..., size=0, ...)` raises `ValueError("incorrect filter size")`. Default `lookahead_ms=2.0` masks this; a user/preset disabling lookahead crashes the limiter.
- **Suggested Fix**: Clamp `self.lookahead_samples = max(1, ...)` in `__init__`, OR short-circuit `process()` to `np.clip` when `lookahead_samples == 0`.

---

#### ENG-11: `BrickWallLimiter.process` still contains an O(n) Python release-envelope loop
- **Severity**: LOW
- **Dimension**: DSP Pipeline / Performance
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:152-166`
- **Status**: NEW
- **Description**: Lookahead peak detection is vectorized via `scipy.ndimage.maximum_filter1d` (#2293), but the release envelope is still a per-sample Python loop (1.3 M iterations for 30 s @ 44.1 kHz).
- **Suggested Fix**: Move to Rust (extend `auralis-dsp` envelope follower) or vectorize via `scipy.signal.lfilter` segments. Future optimization.

---

#### ENG-12: `AdaptiveLimiter._oversample()` silently promotes float32 → float64
- **Severity**: LOW
- **Dimension**: DSP Pipeline / Dtype
- **Location**: `auralis/dsp/dynamics/limiter.py:222, 231`
- **Status**: NEW
- **Description**: `np.zeros(len(audio) * factor)` defaults to float64. Float32 input silently promotes. The limiter output is float64 even when input was float32.
- **Related**: #3658, #3659, #2450. Same module as #3427.
- **Suggested Fix**: Pass `dtype=audio.dtype` to both `np.zeros` calls. Cast `filtered.astype(audio.dtype, copy=False)` before returning.

---

#### ENG-13: EQ band masks recomputed per chunk instead of pre-computed once
- **Severity**: LOW
- **Dimension**: DSP Pipeline / Performance
- **Location**: `auralis/dsp/eq/filters.py:88-98`, `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:109-112`
- **Status**: NEW
- **Description**: Both apply-eq paths iterate 26 critical bands and run `band_mask = freq_to_band_map == i` per chunk. The map is constant — masks should be cached.
- **Suggested Fix**: Pre-compute `self._band_masks: list[np.ndarray]` in `PsychoacousticEQ.__init__`.

---

#### ENG-14: `RealtimeProcessor.process_chunk` final safety limiter redundant with brick-wall limiter; hard-coded 0.95 constant
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/player/realtime/processor.py:131-134`
- **Status**: NEW
- **Description**: This is the second authoritative ceiling after `HybridProcessor`'s brick-wall limiter (`threshold_db=-0.3`, ≈0.9661 linear). Hard-coded `0.95` skews master output ~0.4 dB lower than configured. Redundant safety.
- **Suggested Fix**: Either remove (brick-wall is authoritative) or hoist constant to `PlayerConfig` aligned with -0.3 dBFS.

---

#### ENG-15: `next_track()` holds `_audio_lock` across blocking `load_file` on prebuffer miss
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:387-421`
- **Status**: Existing: #3735
- **Description**: Already filed. In the gapless-fallback path (no prebuffer), the outer `_audio_lock` is held during `load_file`'s blocking disk I/O — concurrent `get_audio_chunk` calls block, draining the audio buffer.
- **Suggested Fix**: See #3735.

---

#### ENG-16: Late-arriving fingerprint thread can write into a freshly-cleaned processor after `cleanup()` returns
- **Severity**: LOW
- **Dimension**: Player State / Cleanup
- **Location**: `auralis/player/enhanced_audio_player.py:267-320, 761-783`
- **Status**: NEW
- **Description**: `cleanup()` joins `_advance_thread` (#3694) but the advance thread itself may have just called `_schedule_fingerprint_load` (line 408), spawning a NEW daemon fingerprint thread that runs after cleanup completes. Late `self.processor.set_fingerprint(fp)` write hits a torn-down processor cache. Benign in production (Electron exits), flaky in tests.
- **Suggested Fix**: Add `_cleanup_in_progress.is_set()` check at the start of `_load_fingerprint_for_file`. Short-circuit `_schedule_fingerprint_load` when set.

---

#### ENG-17: `Result.__init__` does not validate file path is writable or that parent dir exists
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/results.py:21-47`
- **Status**: NEW
- **Description**: Validates extension via `sf.check_format` but not parent-dir-exists / writable / regular-file. Errors surface only at `sf.SoundFile(...mode='w')` in `simple_mastering.process_to_file` — after a half-hour of CPU.
- **Suggested Fix**: Early check `Path(file).parent.exists()`, `os.access(parent, os.W_OK)`. Raise from `__init__`.

---

#### ENG-18: `metadata_extractor.extract_metadata_from_file` silently returns `None` when Mutagen unavailable
- **Severity**: LOW
- **Dimension**: Audio I/O / Metadata
- **Location**: `auralis/library/scanner/metadata_extractor.py:61-72`
- **Status**: NEW
- **Description**: Per-file `debug()` log only. Library scanner cannot distinguish "no metadata" from "library missing". Hard-to-diagnose user reports.
- **Suggested Fix**: Promote to `warning()` once at startup. Raise from `MetadataExtractor.__init__` if mutagen is a hard dep (it's in `requirements.txt`).

---

#### ENG-19: `MAX_DURATION_SECONDS=7200` is module-level constant with no user override
- **Severity**: LOW
- **Dimension**: Audio I/O / Configuration
- **Location**: `auralis/io/loader.py:26`
- **Status**: NEW
- **Description**: A 3-hour live concert WAV (legitimate use case) hard-fails. No way to surface to users beyond a load-time error.
- **Suggested Fix**: Read from `SettingsRepository` with the constant as floor default. Or switch to streaming-load path for files above the threshold.

---

#### ENG-20: `ParallelBandProcessor` sums via `np.sum(band_results, axis=0)` — silent dtype promotion on mixed-dtype lists
- **Severity**: LOW
- **Dimension**: Parallel Processing / Dtype
- **Location**: `auralis/optimization/parallel_processor.py:316, 381`
- **Status**: NEW
- **Description**: `np.sum` promotes to highest dtype. One float64 worker result (e.g., from `sosfiltfilt`) promotes the entire sum to float64.
- **Suggested Fix**: `output = np.sum(band_results, axis=0).astype(audio.dtype, copy=False)`.

---

#### ENG-21: `ParallelFFTProcessor.parallel_windowed_fft` shares the `window` array across all worker tasks
- **Severity**: LOW
- **Dimension**: Parallel Processing / Defensive Programming
- **Location**: `auralis/optimization/parallel_processor.py:122-141`
- **Status**: NEW
- **Description**: Chunk is per-worker copied (#3355 pattern), but the SAME `window` array is shared. No current bug (`_process_fft_chunk` does not mutate), but the contract is brittle.
- **Suggested Fix**: Document the invariant, OR pass `window.view()` with read-only flag set.

---

#### ENG-22: `ProcessPoolExecutor` paths re-create the pool on every call
- **Severity**: LOW
- **Dimension**: Parallel Processing / Performance
- **Location**: `auralis/optimization/parallel_processor.py:136-141, 258-269, 514-519`
- **Status**: NEW
- **Description**: Linux: ~50–100 ms per worker startup; Windows: 500–1000 ms. `AudioFingerprintAnalyzer` correctly maintains a long-lived `ThreadPoolExecutor` (#3701); the MP paths don't.
- **Suggested Fix**: Cache a per-instance pool with `close()` lifecycle.

---

#### ENG-23: `BatchAnalyzer` has no progress callback / partial-result hand-back
- **Severity**: LOW
- **Dimension**: Analysis / Interruption
- **Location**: `auralis/analysis/batch_analyzer.py`
- **Status**: Related: #3477
- **Description**: For a 1000-album library, interrupted batch loses all intermediate results.
- **Suggested Fix**: Persist intermediate results per album. Provide `progress_callback`. Catch `KeyboardInterrupt` to flush partial results before re-raising.

---

#### ENG-24: `FingerprintService._numpy_to_python` lacks branches for complex / datetime types
- **Severity**: LOW
- **Dimension**: Analysis / Serialization
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:256-270`
- **Status**: NEW
- **Description**: `np.complex128`, `np.datetime64`, etc. fall through to `else: return obj`, silently breaking JSON serialization downstream of any future analyzer addition.
- **Suggested Fix**: `else: raise TypeError(f"Cannot serialize NumPy type {type(obj).__name__}")`.

---

#### ENG-25: `LoudnessMeter.integrated_buffer` is unbounded — reused across files leaks memory
- **Severity**: LOW
- **Dimension**: Analysis / Memory
- **Location**: `auralis/analysis/loudness_meter.py:43-51`, `auralis/analysis/quality/quality_metrics.py:69`
- **Status**: NEW
- **Description**: `QualityMetrics` keeps one meter and reuses it across `assess_quality` calls. Per ITU-R BS.1770 the integrated buffer must be unbounded for ONE measurement, but reuse across files accumulates indefinitely.
- **Suggested Fix**: Reset `integrated_buffer` and `_total_samples` per `assess_quality` call, or expose `meter.reset()`.

---

#### ENG-26: Outer `analyze()` catch-all returns empty fingerprint dict, which then gets cached as if valid
- **Severity**: LOW
- **Dimension**: Analysis / Error Surface
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:305-307`, `auralis/analysis/fingerprint/fingerprint_service.py:144`
- **Status**: NEW
- **Description**: `except Exception: return {}` is caught by `if fingerprint:` in the cache layer — an empty dict from a transient analyzer error becomes a permanent bad cache entry.
- **Suggested Fix**: Validate `len(fingerprint) == 25` before caching. Or raise from `analyze()` so the cache layer doesn't write a bad entry.

---

#### ENG-27: `LibraryManager.shutdown` swallows engine.dispose() errors without clearing the stale handle
- **Severity**: LOW
- **Dimension**: Library / Resource Lifecycle
- **Location**: `auralis/library/manager.py:202-236, 266-276`
- **Status**: NEW
- **Description**: `self.engine = None` is INSIDE the try block; if `dispose()` raises, `engine` keeps a stale handle and `__del__` re-invokes shutdown from GC where loggers may already be torn down.
- **Suggested Fix**: Set `self.engine = None` in `finally:` block.

---

#### ENG-28: Cache invalidation lives on the deprecated `LibraryManager` facade, not on the repository write methods
- **Severity**: LOW
- **Dimension**: Library / Cache Coherency
- **Location**: `auralis/library/cache.py`, `auralis/library/manager.py:333`, `auralis/library/repositories/track_repository.py:700-724`
- **Status**: NEW
- **Description**: Direct repository writes (TrackRepository.add/update/delete/cleanup_missing_files — the modern entry point) bypass cache invalidation. Cached `@cached_query(ttl=180)` `get_recent_tracks` returns stale data for up to 3 minutes after a direct write. With Phase 6C migration done (`AudioPlayer` uses RepositoryFactory directly), this is MORE likely to be hit.
- **Suggested Fix**: Move invalidation into the repository write methods. Or use SQLAlchemy event listeners.

---

#### ENG-29: `LibraryManager._delete_lock` is initialized but never used
- **Severity**: LOW
- **Dimension**: Library / Dead Code
- **Location**: `auralis/library/manager.py:169`
- **Status**: NEW
- **Description**: `grep -rn "_delete_lock" auralis/` returns only the initialization site. Misleading comment claims synchronization exists.
- **Suggested Fix**: Remove the field + comment, OR wire it into `TrackRepository.delete` / `cleanup_missing_files` if a cascade-delete race is real.

---

#### ENG-30: `FingerprintRepository.upsert` builds SQL via f-string interpolation; whitelist is one-deep defense
- **Severity**: LOW
- **Dimension**: Library / Security (Defense-in-Depth)
- **Location**: `auralis/library/repositories/fingerprint_repository.py:698-735`
- **Status**: NEW
- **Description**: `_validate_fingerprint_columns(cols)` IS the security boundary; one bad refactor of the whitelist re-opens an injection vector.
- **Suggested Fix**: Derive whitelist from `{c.name for c in TrackFingerprint.__table__.columns}`. Add startup self-test. Or migrate to SQLAlchemy's `dialects.sqlite.insert(...).on_conflict_do_update()`.

---

## Relationships

Several findings share root causes and would be addressed together by single refactors:

- **Dtype-drift cluster** (ENG-4, ENG-9, ENG-12, ENG-20): All silent float32 → float64 promotions in DSP / I/O hot paths. Same class of bug as the already-fixed #3658 / #3659 / #2450 — these are the remaining occurrences in non-canonical paths. Fix together by introducing an `auralis.utils.audio_validation.preserve_dtype` decorator that asserts input.dtype == output.dtype on any function decorated with it; then sprinkle on `RealtimeProcessor.process_chunk`, `AdaptiveLimiter._oversample`, `ParallelBandProcessor._process_bands_parallel`, `unified_loader.load_audio` normalize branch, `soundfile_loader.load_with_soundfile`.

- **Multi-channel downmix sibling pair** (ENG-3): One fix shared between `loader.py:84-86` and `soundfile_loader.py:70-74`. Extract `auralis.io.processing.downmix_to_stereo(audio: ndarray) -> ndarray` and call from both sites + (optionally) reuse the FFmpeg matrix.

- **Resource-lifecycle on cache eviction** (ENG-6, ENG-16, ENG-22, ENG-27): All concern threads / pools / handles that outlive their owning cached instance. Best fix is a uniform `HybridProcessor.close()` / `AudioPlayer.cleanup()` propagation that drains: (1) cached fingerprint analyzers, (2) `ProcessPoolExecutor` instances in parallel processor, (3) library engine. Currently each layer's cleanup is isolated.

- **Parallel-processing error-surface** (ENG-5, ENG-23, ENG-26): All "one failure aborts the run / silently caches bad data". The `ParallelBandProcessor` pattern (per-future try/except with named-fallback) is the canonical fix and should be ported to: `process_batch` (ENG-5), `BatchAnalyzer.analyze_album_pair` (ENG-23), and `AudioFingerprintAnalyzer.analyze()` outer catch-all (ENG-26).

- **EQ contract fragility** (ENG-2, ENG-13): Both are about the EQ assuming-but-not-asserting its input size. Adding `assert len(audio) <= fft_size` plus the band-mask pre-computation refactor would harden both.

- **Genre determinism** (ENG-1): Standalone but high-leverage. Seeding `genre_weights` deterministically eliminates a class of "same input, different output" complaints across the engine.

---

## Prioritized Fix Order

1. **ENG-1 (HIGH)** — Genre weight nondeterminism. Single-file fix, eliminates the only HIGH finding and restores the determinism invariant.
2. **ENG-3 (MEDIUM)** — Multi-channel downmix on native loaders. User-visible (vocals silenced on 5.1 FLAC). Mirror of already-fixed #3672.
3. **ENG-5 (MEDIUM)** — `process_batch` per-file error handling. Unblocks robust batch tooling for library-scale operations.
4. **ENG-6 (MEDIUM)** — `AudioFingerprintAnalyzer.close()` on processor cache eviction. Thread leak in long sessions.
5. **ENG-4 (MEDIUM)** — `RealtimeProcessor.process_chunk` copy + dtype. Two-line fix; restores invariants in the realtime hot path.
6. **ENG-7 (MEDIUM)** — `PsychoacousticEQ` state lock. Required if realtime processor is ever concurrently invoked.
7. **ENG-2 (MEDIUM)** — `apply_eq_gains` assertion. Defensive; cheap.
8. **ENG-8 (MEDIUM)** — `soundfile_loader` dtype consistency. Half-the-RAM win on the canonical loader path.
9. **LOW cluster fixes** — Group by relationship (dtype-drift, resource-lifecycle, parallel-error-surface) and ship as small consolidated PRs. Use the relationship section above as the grouping plan.

---

## Suggested next step

```
/audit-publish docs/audits/AUDIT_ENGINE_2026-05-27.md
```
