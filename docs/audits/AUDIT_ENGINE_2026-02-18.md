# Audio Engine Audit
**Date**: 2026-02-18
**Auditor**: Claude (automated, 7 parallel agents)
**Scope**: Core audio engine — DSP pipeline, player, I/O, parallel processing, analysis, library, Rust DSP
**Issues Created**: E-01 – E-09 (9 new findings)

---

## Summary

| Severity | Count | New Issues |
|----------|-------|-----------|
| CRITICAL | 1 | E-01 |
| HIGH | 2 | E-02, E-03 |
| MEDIUM | 5 | E-04, E-05, E-06, E-07, E-08 |
| LOW | 1 | E-09 |
| **TOTAL NEW** | **9** | |
| Skipped (duplicates) | 12 | See deduplication table |

---

## Deduplication Reference

The following existing issues were checked before reporting. Findings that matched were skipped:

| Existing Issue | Title | Agent Finding |
|---------------|-------|---------------|
| #2424 | band_results list aliasing drops audio bands in parallel processor | Parallel EQ spectrum merge loss |
| #2423 | AudioFileManager.audio_data written from gapless thread without lock | AudioFileManager no synchronization |
| #2427 | QueueManager tracks/current_index modified without lock | QueueManager race conditions |
| #2426 | RealtimeLevelMatcher shared state not protected | RealtimeLevelMatcher concurrent process() |
| #2433 | IntegrationManager.callbacks mutated without lock | Callback iteration not atomic |
| #2308 | PlaybackController.add_callback not thread-safe | PlaybackController callback race |
| #2441 | _auto_advancing Event allows duplicate auto-advance | Auto-advance TOCTOU |
| #2431 | FingerprintRepository.upsert() bypasses SQLAlchemy pool | Raw sqlite3 writes in fingerprint repo |
| #2288 | FingerprintExtractor raw SQL DELETE bypasses repository | FingerprintExtractor deletion pattern |
| #2438 | Concurrent library scans insert duplicate tracks | Concurrent scan conflict |
| #2167 | dtype inconsistency between vectorized and numba envelope followers | Envelope follower dtype mismatch |
| #2226 | Soundfile loader logs wrong channel count | Channel count warning bug |

---

## Dimension 2: DSP Pipeline Correctness

### E-01: Double-Windowing in ParallelEQProcessor Causes Amplitude Modulation
- **Severity**: CRITICAL
- **Dimension**: DSP Pipeline Correctness
- **Location**: `auralis/dsp/eq/parallel_eq_processor/parallel_processor.py:127-155` (parallel path), `auralis/dsp/eq/parallel_eq_processor/parallel_processor.py:340-364` (sequential path)
- **Status**: NEW
- **Description**: The ParallelEQProcessor applies a Hanning window **twice** — once before FFT (analysis window) and once after IFFT (synthesis window). For single-frame processing (no overlap-add), this causes amplitude modulation where signal edges are attenuated to zero. Commit `cca59d9c` fixed this exact pattern in `VectorizedEQProcessor` but left the identical bug in `ParallelEQProcessor`.
- **Evidence**:
  ```python
  # Parallel path: lines 127-128 (first window) + line 155 (second window)
  window = np.hanning(fft_size)
  windowed_audio = audio_mono[:fft_size] * window   # ← Window #1
  spectrum = fft(windowed_audio)
  # ... band processing ...
  processed_audio = np.real(ifft(spectrum))
  processed_audio *= window                          # ← Window #2 = DOUBLE!

  # Sequential path: lines 340-341 (first window) + line 364 (second window)
  window = np.hanning(fft_size)
  windowed_audio = audio_mono[:fft_size] * window   # ← Window #1
  # ...
  processed_audio *= window                          # ← Window #2 = DOUBLE!
  ```
- **Impact**: ~50% energy loss at mid-signal. Signal edges attenuated to zero. Audible as volume dip with muffled character when ParallelEQProcessor is active. Affects all EQ processing through the parallel path.
- **Suggested Fix**: Remove the post-IFFT window multiplication (line 155 and line 364), matching the fix applied in `cca59d9c` for VectorizedEQProcessor. For single-frame EQ processing, no windowing is needed (as demonstrated in `auralis/dsp/eq/filters.py:84-101`).

---

## Dimension 6: Analysis Subsystem

### E-02: Rust DSP Functions Hold Python GIL During All Computation
- **Severity**: HIGH
- **Dimension**: Analysis / Parallel Processing
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:88-128` (hpss), `:150-179` (yin), `:198-227` (chroma), and 8 other wrapper functions
- **Status**: NEW
- **Description**: All 11 PyO3 wrapper functions in `py_bindings.rs` use `#[pyfunction]` which holds the Python GIL throughout execution. None call `py.allow_threads()` to release the GIL during compute-intensive DSP operations (HPSS, YIN pitch detection, chroma CQT, etc.). This forces single-threaded execution even when multiple Python threads attempt concurrent DSP calls.
- **Evidence**:
  ```rust
  // py_bindings.rs:88-122 — GIL held during entire HPSS computation
  #[pyfunction]
  fn hpss_wrapper(
      py: Python<'_>,
      audio: &PyArray1<f64>,
      // ...
  ) -> PyResult<(Py<PyArray1<f64>>, Py<PyArray1<f64>>)> {
      let audio_vec: Vec<f64> = audio.to_vec()?;
      // GIL NOT released here — all other threads blocked
      let (harmonic, percussive) = std::panic::catch_unwind(|| {
          hpss::hpss(&audio_vec, &config)
      })?;
      // ...
  }
  ```
- **Impact**: With 16 fingerprint workers using ThreadPoolExecutor, only 1 worker can execute Rust DSP at a time. Estimated 5x throughput loss. The fingerprint service comments mention "98% worker idle time" — this is the root cause.
- **Suggested Fix**: Wrap the compute-intensive section in `py.allow_threads()`:
  ```rust
  let (harmonic, percussive) = py.allow_threads(|| {
      std::panic::catch_unwind(|| hpss::hpss(&audio_vec, &config))
  }).map_err(|e| ...)?;
  ```

---

### E-03: HarmonicOperations Methods Raise Instead of Returning Fallback Values
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/utilities/harmonic_ops.py:64-66`, `:106-108`, `:152-154`
- **Status**: NEW
- **Description**: All three `HarmonicOperations` static methods (`calculate_harmonic_ratio`, `calculate_pitch_stability`, `calculate_chroma_energy`) re-raise exceptions instead of returning fallback values. While `calculate_all()` (line 157) propagates these raises, the direct callers in `SampledHarmonicAnalyzer._analyze_chunk` DO catch and return defaults. However, any future caller that doesn't wrap in try/except will crash the fingerprint pipeline.
- **Evidence**:
  ```python
  # harmonic_ops.py:64-66
  except Exception as e:
      logger.error(f"Harmonic ratio calculation failed: {e}")
      raise  # ← Propagates instead of returning 0.5

  # harmonic_ops.py:106-108 — same pattern
  # harmonic_ops.py:152-154 — same pattern

  # calculate_all (line 157-169) has NO try/except — propagates all raises
  ```
- **Impact**: If Rust DSP library is unavailable or audio is pathological, entire fingerprint analysis crashes. Current callers (`SampledHarmonicAnalyzer`) handle this gracefully, but the contract violation (docstring says "Returns ... or default values") makes the API fragile.
- **Suggested Fix**: Add fallback returns in each method's except block: `return 0.5` (harmonic_ratio), `return 0.7` (pitch_stability), `return 0.5` (chroma_energy). This matches the DEFAULT_FEATURES in `SampledHarmonicAnalyzer` and the documented return contract.

---

### E-04: VectorizedEQProcessor ifft() Returns float64 Without Restoring Input dtype
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline Correctness
- **Location**: `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:112-115`
- **Status**: NEW
- **Description**: The `VectorizedEQProcessor.apply_eq_mono()` method calls `np.real(ifft(spectrum))` which always returns `float64`. If the input audio was `float32`, the output is silently promoted to `float64`, doubling memory usage and causing dtype inconsistency in downstream processing.
- **Evidence**:
  ```python
  # vectorized_processor.py:112-115
  processed_audio = np.real(ifft(spectrum))  # Always float64
  return cast(np.ndarray, processed_audio[:len(audio_mono)])
  # ← No dtype restoration!

  # Contrast with correct implementation in filters.py:103
  return np.asarray(processed_audio[:len(audio_mono)], dtype=audio_mono.dtype)
  ```
- **Impact**: 2x memory usage for float32 audio paths. Precision inconsistency when mixing VectorizedEQ output with other float32 DSP stages. May cause subtle numerical differences in downstream processing.
- **Suggested Fix**: Cast output back to input dtype: `return np.asarray(processed_audio[:len(audio_mono)], dtype=audio_mono.dtype)`

---

### E-05: Unbounded Chunk Extraction in SampledHarmonicAnalyzer
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/batch/harmonic_sampled.py:74-81`
- **Status**: NEW
- **Description**: The `_extract_chunks()` method has no upper bound on the number of chunks extracted. For pathological files (e.g., a 10-hour podcast), it extracts `duration / interval_duration` chunks (3600+ for a 10-hour file with default 10s intervals), each copied via `.copy()`.
- **Evidence**:
  ```python
  # harmonic_sampled.py:74-81
  start_sample = 0
  while start_sample + chunk_samples <= len(audio):
      end_sample = start_sample + chunk_samples
      chunk = audio[start_sample:end_sample].copy()  # Copies each chunk
      chunks.append(chunk)                            # No cap on list size
      start_sample += interval_samples
  # 10-hour file: 3600 chunks × 5s × 44100 × 4 bytes ≈ 3.1 GB RAM
  ```
- **Impact**: Memory exhaustion on long audio files. Each 5-second chunk at 44.1kHz = ~882KB. For a 10-hour file, 3600 chunks = ~3.1GB of copied audio data in memory simultaneously, plus the original audio.
- **Suggested Fix**: Add a `max_chunks` parameter (default 50-100) and cap the while loop. 50 chunks × 5s = 250s of analyzed audio, more than sufficient for accurate fingerprinting.

---

### E-06: ML FeatureExtractor Mono Conversion Uses Wrong Axis
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/ml/feature_extractor.py:55-56`
- **Status**: NEW
- **Description**: The stereo-to-mono conversion uses `np.mean(audio, axis=1)`. The codebase convention is `(channels, samples)` format — with this convention, `axis=1` averages across samples (producing a 2-element array), when it should average across channels (`axis=0`) to produce a mono signal.
- **Evidence**:
  ```python
  # feature_extractor.py:55-56
  if audio.ndim == 2:
      mono_audio = np.mean(audio, axis=1)  # ← BUG: averages across samples
  # For audio shape (2, 44100): np.mean(axis=1) → shape (2,) — wrong!
  # Should be: np.mean(audio, axis=0) → shape (44100,)
  ```
- **Impact**: Genre classification receives a 2-element array instead of a full audio signal. All subsequent feature extraction (MFCC, spectral centroid, etc.) operates on essentially 2 data points. Classification accuracy degrades to near-random.
- **Suggested Fix**: Change to `np.mean(audio, axis=0)` to average across channels.

---

## Dimension 7: Library & Database

### E-07: cleanup_incomplete_fingerprints Loads All Records Into Memory
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_repository.py:707-720`
- **Status**: NEW
- **Description**: The `cleanup_incomplete_fingerprints()` method uses `.all()` to load all incomplete fingerprint records into memory, then deletes them one-by-one via ORM. For large libraries with many crashed/interrupted fingerprinting sessions, this can cause OOM.
- **Evidence**:
  ```python
  # fingerprint_repository.py:707-720
  incomplete_fps = (
      session.query(TrackFingerprint)
      .filter(TrackFingerprint.lufs == -100.0)
      .all()  # ← Loads ALL into memory
  )
  for fp in incomplete_fps:  # ← One-by-one ORM delete
      session.delete(fp)
  session.commit()
  ```
- **Impact**: If 10K+ incomplete fingerprints exist (e.g., after repeated crashes), all records are loaded into memory. Each TrackFingerprint object with 25 float fields + metadata ≈ 1-2KB. At 100K records, this is ~100-200MB of unnecessary memory allocation.
- **Suggested Fix**: Use a single SQL `DELETE` statement instead:
  ```python
  deleted = session.query(TrackFingerprint).filter(
      TrackFingerprint.lufs == -100.0
  ).delete(synchronize_session=False)
  session.commit()
  return deleted
  ```

---

## Dimension 5: Parallel Processing (Services)

### E-08: fingerprint_queue stats_lock Held During Long-Running DB I/O
- **Severity**: MEDIUM
- **Dimension**: Parallel Processing
- **Location**: `auralis/services/fingerprint_queue.py:313-337`
- **Status**: NEW
- **Description**: The `_process_track()` method acquires `stats_lock`, then calls `self.extractor.extract_and_store()` which performs DB I/O (loading audio, computing fingerprint, writing to database). The stats_lock should only protect the stat counters, not gate long-running I/O operations.
- **Evidence**:
  ```python
  # fingerprint_queue.py:313-337
  with self.stats_lock:  # ← Lock acquired
      self.stats['processing'] += 1
      # ... track processing setup ...
      success = self.extractor.extract_and_store(track.id, track.filepath)
      # ↑ DB I/O: load audio (50-150MB), compute fingerprint, write to DB
      # All other workers BLOCKED on stats_lock during this entire operation
      self.stats['processing'] -= 1
  ```
- **Impact**: Other fingerprint workers are blocked on the stats_lock while one worker processes a large FLAC file (potentially seconds). With 16 workers, this serializes processing and dramatically reduces throughput.
- **Suggested Fix**: Move the lock to only protect the stat counter increments/decrements, not the processing:
  ```python
  with self.stats_lock:
      self.stats['processing'] += 1
  try:
      success = self.extractor.extract_and_store(track.id, track.filepath)
  finally:
      with self.stats_lock:
          self.stats['processing'] -= 1
  ```

---

## Dimension 2: DSP Pipeline Correctness (Rust Boundary)

### E-09: Rust fingerprint_compute Has No Sample Rate Range Validation
- **Severity**: LOW
- **Dimension**: DSP Pipeline Correctness
- **Location**: `vendor/auralis-dsp/src/fingerprint_compute.rs:219-244`
- **Status**: NEW
- **Description**: The Rust `compute_fingerprint()` function validates that `sample_rate > 0` but does not check for realistic ranges (8kHz–192kHz). Extreme values cause incorrect FFT bin-to-frequency mapping, producing invalid fingerprints silently.
- **Evidence**: The `hz_to_bin()` function at line 192-195 divides by `sample_rate`, so extreme values (e.g., `1` or `999999`) produce wildly incorrect frequency bin mappings. This would only occur with malformed audio metadata.
- **Impact**: Invalid fingerprints stored for files with corrupted sample rate metadata. Downstream similarity matching produces incorrect results for affected tracks.
- **Suggested Fix**: Add range validation: `if sample_rate < 8000 || sample_rate > 192000 { return Err(...) }`

---

## Audit Checklist Summary

### Dimension 1: Sample Integrity
- [x] `len(output) == len(input)` verified at outer processing stages ✓
- [x] `audio.copy()` before in-place operations — consistently applied ✓
- [x] dtype preservation — **FINDING E-04** (VectorizedEQ)
- [x] Clipping prevention — `sanitize_audio()` at outputs ✓
- [x] NaN/Inf propagation — `validate_audio_finite()` at inputs, `sanitize_audio()` at outputs ✓
- [x] Mono/stereo handling — HybridProcessor line 208 converts mono correctly for downstream ✓
- [x] Bit depth output — `results.py` pcm16/pcm24 delegates to soundfile correctly ✓

### Dimension 2: DSP Pipeline Correctness
- [x] Processing chain order — EQ → dynamics → mastering documented and correct ✓
- [x] Stage independence — each stage receives copy via initial `audio.copy()` ✓
- [x] Parameter validation — ranges validated via config system ✓
- [x] Windowing — **FINDING E-01** (ParallelEQProcessor double-windowing)
- [x] Double-windowing fix `cca59d9c` — applied in VectorizedEQ, NOT in ParallelEQ ✗
- [x] Phase coherence — maintained through single-frame processing ✓
- [x] Rust DSP boundary — **FINDING E-02** (GIL), **E-09** (sample rate validation)

### Dimension 3: Player State Machine
- [x] State transitions atomic under RLock — PlaybackController ✓
- [x] Position invariant — clamped in seek(), reset in stop() ✓
- [x] Queue bounds — existing issue #2427 (no lock)
- [x] Gapless transitions — existing issue #2423 (AudioFileManager not locked)
- [x] Callback safety — existing issues #2308, #2433
- [x] Resource cleanup — proper shutdown sequence ✓
- [x] Real-time processor lifecycle — Lock-protected ✓

### Dimension 4: Audio I/O
- [x] Format coverage — MP3, FLAC, WAV via FFmpeg+SoundFile ✓
- [x] Corrupt file handling — exceptions propagated ✓
- [x] Sample rate detection — from metadata, never assumed ✓
- [x] Channel handling — multi-channel downmixed in soundfile_loader ✓
- [x] FFmpeg subprocess — `subprocess.run()` with timeout ✓
- [x] File path safety — paths validated as Path objects ✓

### Dimension 5: Parallel Processing
- [x] Chunk independence — `.copy()` on each chunk ✓
- [x] Reassembly order — sequential core_samples assembly ✓
- [x] Boundary smoothing — crossfade with equal-power curves ✓
- [x] Sample count — crossfade preserves total length ✓
- [x] Stats lock scope — **FINDING E-08**

### Dimension 6: Analysis Subsystem
- [x] Fingerprint determinism — depends on Rust availability, **FINDING E-03**
- [x] Resource bounds — **FINDING E-05** (unbounded chunks)
- [x] ML model lifecycle — created per-instance (acceptable) ✓
- [x] Quality metrics — LUFS, DR correctly computed ✓
- [x] Mono conversion — **FINDING E-06** (wrong axis)

### Dimension 7: Library & Database
- [x] Repository pattern — all access via repositories (except fingerprint raw SQL, #2431) ✓
- [x] SQLite config — WAL, pool_pre_ping=True, synchronous=NORMAL ✓
- [x] N+1 queries — consistent joinedload/selectinload across all repositories ✓
- [x] Scanner robustness — symlinks, permissions, max depth all handled ✓
- [x] Migration safety — inter-process file locking + double-check ✓
- [x] Cleanup — **FINDING E-07** (incomplete fingerprint cleanup OOM risk)
- [x] Engine disposal — fixed in #2395 ✓
