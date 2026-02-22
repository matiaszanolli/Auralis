# Audio Engine Audit Report

**Date**: 2026-02-22
**Auditor**: Claude Opus 4.6 (automated)
**Scope**: Auralis core audio engine — 7 dimensions
**Method**: Systematic code review with agent-assisted exploration, followed by manual verification of all findings against source code. False positives eliminated.

## Executive Summary

Audited the Auralis core audio engine across all 7 dimensions: Sample Integrity, DSP Pipeline Correctness, Player State Machine, Audio I/O, Parallel Processing, Analysis Subsystem, and Library & Database. Reviewed 30+ source files, cross-referenced against 80+ existing GitHub issues.

**Results**: 10 confirmed findings (0 CRITICAL, 0 HIGH, 6 MEDIUM, 4 LOW). 6+ false positives eliminated during verification.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 6 |
| LOW | 4 |

## Findings

---

### ENG-01: Linear crossfade in chunk_operations vs equal-power in chunked_processor
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis-web/backend/core/chunk_operations.py:289-290` vs `auralis-web/backend/core/chunked_processor.py:911-914`
- **Status**: NEW
- **Description**: Two crossfade implementations exist in the backend. `chunked_processor.py` uses equal-power (sin²/cos²) curves (fix for #2080), but `chunk_operations.py` still uses linear crossfade (`np.linspace`). Any code path that uses `chunk_operations.crossfade_chunks()` instead of the chunked processor's crossfade will produce a ~3dB energy dip at the midpoint of crossfade regions.
- **Evidence**:
  ```python
  # chunk_operations.py:289-290 — LINEAR crossfade
  fade_out = np.linspace(1.0, 0.0, actual_overlap)
  fade_in = np.linspace(0.0, 1.0, actual_overlap)

  # chunked_processor.py:911-914 — EQUAL-POWER crossfade (correct)
  t = np.linspace(0.0, np.pi / 2, actual_overlap)
  fade_out = np.cos(t) ** 2
  fade_in = np.sin(t) ** 2
  ```
- **Impact**: Audible volume dip at chunk boundaries when the `chunk_operations` path is used. At the crossfade midpoint, linear fade sums to 1.0 (0.5 + 0.5) but equal-power sums to ~1.0 in energy (sin²+cos²=1). Linear crossfade causes perceived loudness drop.
- **Suggested Fix**: Replace the linear crossfade in `chunk_operations.py` with the same equal-power curves used in `chunked_processor.py`, or extract a shared crossfade utility.

---

### ENG-02: Stereo RMS calculation averages channels before computing RMS
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/continuous_mode.py:427`
- **Status**: NEW
- **Description**: The RMS normalization calculates loudness by first averaging L+R channels (`np.mean(audio, axis=1)`), then computing RMS of the average. This is mathematically incorrect — it underestimates the true RMS by up to 3dB when channels are uncorrelated (e.g., wide stereo mixes). The correct approach is to compute RMS across all samples of all channels, or compute per-channel RMS and then combine.
- **Evidence**:
  ```python
  # continuous_mode.py:427 — averages channels BEFORE RMS
  current_rms = calculate_rms(np.mean(audio, axis=1) if audio.ndim == 2 else audio)
  ```
  Also repeated at line 438:
  ```python
  new_rms = calculate_rms(np.mean(audio, axis=1) if audio.ndim == 2 else audio)
  ```
- **Impact**: Systematic loudness underestimation for stereo content. Normalization applies more gain than needed, potentially causing clipping after amplification. The error is consistent (always underestimates), so it doesn't cause random artifacts, but violates the target loudness.
- **Suggested Fix**: Replace `np.mean(audio, axis=1)` with `audio.flatten()` or compute `calculate_rms(audio.ravel())` to include all channel samples in the RMS calculation.

---

### ENG-03: Missing parameter validation in dynamics settings
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/compressor.py`, `auralis/dsp/dynamics/limiter.py`
- **Status**: NEW (distinct from #2214 which is about per-chunk vs per-sample gain)
- **Description**: The dynamics processors (compressor, limiter) accept configuration parameters (threshold, ratio, attack, release, knee) without validating ranges. Invalid values (e.g., negative ratio, zero attack time, threshold > 0 dBFS) could produce undefined DSP behavior — division by zero in gain calculations, infinite gain reduction, or no-op processing.
- **Evidence**: The compressor and limiter `__init__` methods accept settings directly without bounds checking. No `ValueError` is raised for out-of-range parameters. The soft clipper has a similar edge case where `ceiling=0` causes `headroom=0` → `scale=0` → division by zero in `excess / scale` (line 68 of `soft_clipper.py`).
- **Impact**: Corrupted audio output or runtime exceptions when invalid parameters reach the DSP stage. In practice, parameters come from the frontend with slider constraints, but the engine API should validate independently.
- **Suggested Fix**: Add parameter validation in the settings dataclass or processor `__init__`. Clamp values to safe ranges: threshold ∈ [-60, 0] dBFS, ratio ∈ [1, 100], attack/release ∈ [0.001, 5.0]s, ceiling > 0.

---

### ENG-04: FingerprintService uses raw sqlite3 instead of repository pattern
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:110, 231`
- **Status**: NEW
- **Description**: The `FingerprintService` class opens raw `sqlite3.connect()` connections to the database, bypassing the SQLAlchemy-based repository pattern used everywhere else. This violates the critical invariant: "All DB access via `auralis/library/repositories/`, never raw SQL." Raw connections don't benefit from SQLAlchemy connection pooling, WAL mode pragma setup, or the `pool_pre_ping` reliability mechanism.
- **Evidence**:
  ```python
  # fingerprint_service.py:110 — raw sqlite3 in _load_from_database()
  conn = sqlite3.connect(str(self.db_path))
  cursor = conn.cursor()

  # fingerprint_service.py:231 — raw sqlite3 in _save_to_database()
  conn = sqlite3.connect(str(self.db_path))
  cursor = conn.cursor()
  ```
- **Impact**: Potential "database locked" errors under concurrent access since raw connections don't use WAL mode or connection pooling. Data could also be written without the thread-safety guarantees of the pooled engine.
- **Suggested Fix**: Refactor `FingerprintService` to accept a `FingerprintRepository` (which already exists at `auralis/library/repositories/`) instead of a raw `db_path`. Replace the raw SQL queries with repository method calls.

---

### ENG-05: ML genre classifier re-allocates Mel filterbank per track
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/ml/feature_extractor.py:259` → `auralis/dsp/utils/interpolation_helpers.py:182-226`
- **Status**: NEW
- **Description**: The `FeatureExtractor._extract_mfcc()` method calls `self._create_mel_filterbank(self.n_mfcc, 2049)` on every invocation. Since `extract_features()` is called once per track during genre classification, the Mel filterbank (13 filters × 2049 bins = 26,637 float32 values) is re-allocated for every track analyzed. The filterbank is deterministic — it depends only on sample rate, n_filters, and n_fft, not on track content.
- **Evidence**:
  ```python
  # feature_extractor.py:259 — called per track
  mel_filters = self._create_mel_filterbank(self.n_mfcc, 2049)

  # interpolation_helpers.py:211 — allocates numpy array per filter
  filt = np.zeros(n_fft, dtype=np.float32)
  ```
- **Impact**: Unnecessary memory allocation and GC pressure during batch genre classification (e.g., library scan of 10,000 tracks). Not a correctness issue, but a performance waste.
- **Suggested Fix**: Cache the filterbank as an instance variable in `FeatureExtractor.__init__()` or use `@functools.lru_cache` keyed on `(n_filters, n_fft, sample_rate)`.

---

### ENG-06: Queue remove_tracks() has redundant nested RLock acquisition
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:127-147`
- **Status**: NEW (distinct from #2159 which is about reorder_tracks, not remove_tracks)
- **Description**: `remove_tracks()` acquires `self._lock` (an RLock) and then calls `self.remove_track(index)` in a loop, which also acquires `self._lock`. While RLock permits re-entrant acquisition (so it won't deadlock), this design means the inner method performs its own bounds checking and index adjustment against state that the outer method is iterating over. If `remove_track()` were ever refactored to release the lock, the outer loop would become unsafe.
- **Evidence**:
  ```python
  # queue_manager.py:138-144
  def remove_tracks(self, indices: list[int]) -> int:
      with self._lock:                          # Outer lock
          sorted_indices = sorted(set(indices), reverse=True)
          removed_count = 0
          for index in sorted_indices:
              if self.remove_track(index):      # Inner lock (re-entrant)
                  removed_count += 1
          return removed_count
  ```
- **Impact**: Not a current bug due to RLock, but fragile design. The redundant lock acquisitions also add unnecessary overhead per removal.
- **Suggested Fix**: Extract the removal logic from `remove_track()` into a private `_remove_track_unlocked()` helper. Have both `remove_track()` and `remove_tracks()` call the helper while holding a single lock.

---

### ENG-07: Soundfile loader returns view for multi-channel downmix
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/soundfile_loader.py:58`
- **Status**: NEW
- **Description**: When loading a multi-channel file (e.g., 5.1 surround), the loader takes the first two channels via `audio_data[:, :2]`, which returns a NumPy view — not a copy. The original N-channel array remains alive in memory as long as the 2-channel view exists, wasting memory proportional to the number of extra channels.
- **Evidence**:
  ```python
  # soundfile_loader.py:55-58
  if audio_data.shape[1] > 2:
      original_channels = audio_data.shape[1]
      audio_data = audio_data[:, :2]  # View, not copy
  ```
- **Impact**: For a 10-minute 5.1 file at 48kHz float32: 48000×600×6×4 = 691MB stays alive instead of the 230MB needed for stereo. Not a correctness issue.
- **Suggested Fix**: Add `.copy()` after the slice: `audio_data = audio_data[:, :2].copy()`.

---

### ENG-08: RealtimeProcessor uses static config sample rate
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/realtime/processor.py:139`
- **Status**: Related: #2408 (different component, same root cause)
- **Description**: The `RealtimeProcessor` uses `self.config.sample_rate` (set once at initialization) for calculating chunk durations. When tracks with different sample rates are played back-to-back, the `AudioFileManager.sample_rate` is updated but the `RealtimeProcessor.config.sample_rate` remains at the initial value. This causes inaccurate timing calculations.
- **Evidence**:
  ```python
  # realtime/processor.py:139 — uses static config
  chunk_duration = len(audio) / self.config.sample_rate
  # But AudioFileManager.sample_rate updates per-track at load time
  ```
- **Impact**: Incorrect performance metrics and timing calculations after the first track if subsequent tracks have different sample rates. Does not affect audio output, only monitoring/logging accuracy.
- **Suggested Fix**: Have `RealtimeProcessor` read sample rate from `AudioFileManager` rather than its own static config, or update config when track changes.

---

### ENG-09: Pathological fingerprint input handling
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/` (analyzers)
- **Status**: NEW
- **Description**: The fingerprint analyzers don't have explicit guards for pathological inputs: very short audio (< 1 second), pure silence, or pure DC offset. These edge cases could produce degenerate fingerprints (all zeros, NaN from log(0), or division by zero in normalization) without error messages.
- **Evidence**: Batch and streaming analyzers process whatever audio is passed in. No minimum length check or silence detection before fingerprint computation.
- **Impact**: Degenerate fingerprints could pollute similarity search results. Low severity because these inputs are uncommon in real music libraries.
- **Suggested Fix**: Add input validation: minimum audio length (e.g., 1 second), check for silence/DC, and return a sentinel or raise a descriptive error for unprintable audio.

---

### ENG-10: Soft clipper division by zero when ceiling equals zero
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/soft_clipper.py:64,68`
- **Status**: NEW
- **Description**: If `ceiling=0.0` is passed, then `headroom = ceiling - threshold` is zero or negative, and `scale = headroom * 1.5 = 0`. The subsequent `excess / scale` on line 68 causes a division by zero, producing NaN/Inf in the output.
- **Evidence**:
  ```python
  # soft_clipper.py:64,68
  scale = headroom * 1.5  # If headroom=0, scale=0
  compressed_excess = headroom * np.tanh(excess / scale)  # div by zero
  ```
- **Impact**: Only triggered if `ceiling=0.0`, which is an unrealistic parameter (muting all audio). Frontend sliders don't allow this value. Extremely low risk.
- **Suggested Fix**: Add a guard: `if headroom <= 0: return np.zeros_like(audio)` or clamp `ceiling` to a minimum of e.g., 0.001.

---

## False Positives Eliminated

The following findings from automated exploration were disproved during manual verification:

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| Compressor/limiter mono lookahead buffer crash | `arr[-N:, ...]` is valid NumPy for 1D arrays (Ellipsis fills zero remaining dims) |
| FFT chunk views shared between parallel workers | `chunk * window` creates a new array; workers never mutate the view |
| FFmpeg temp file leak on timeout | Python's `finally` block always runs; `subprocess.run()` kills child on timeout |
| FFmpeg zombie process on cancellation | `subprocess.run()` with `timeout` internally calls `Popen.kill()` |
| Memory pool race condition in buffer return | RLock covers the entire return-to-pool sequence (fill zeros + append) |
| Compressor settings missing validation (CRITICAL) | Downgraded to MEDIUM — invalid params are unrealistic from frontend, but API should still validate |

## Checklist Summary

### Dimension 1: Sample Integrity
- [x] `len(output) == len(input)` — verified at all processing stages
- [x] `audio.copy()` before in-place ops — confirmed in `simple_mastering.py:303`, `unified.py`
- [x] dtype preservation — float32/float64 throughout
- [x] Clipping prevention — output clamped in results.py
- [ ] **Stereo RMS calculation** — ENG-02 (averages channels before RMS)
- [x] Mono/stereo handling — correct in hybrid_processor.py
- [x] Bit depth output — pcm16/pcm24 correctly scaled in results.py

### Dimension 2: DSP Pipeline Correctness
- [x] Processing chain order — EQ → dynamics → mastering, documented
- [x] Stage independence — each stage receives clean input
- [ ] **Parameter validation** — ENG-03 (no range checks on dynamics params)
- [x] Windowing — double-windowing removed (fix `cca59d9c` verified)
- [x] Phase coherence — maintained across multi-band
- [x] Sub-bass parallel path — correctly mixed (fix `8bc5b217` verified)
- [x] Rust DSP boundary — PyO3 calls handle errors correctly
- [ ] **Crossfade inconsistency** — ENG-01 (linear in chunk_operations vs equal-power in chunked_processor)
- [ ] **Soft clipper edge case** — ENG-10 (div-by-zero when ceiling=0)

### Dimension 3: Player State Machine
- [x] State transitions — atomic under RLock (playback_controller.py:39)
- [x] Position invariant — position ≤ duration maintained
- [ ] **Queue remove_tracks()** — ENG-06 (redundant nested RLock)
- [x] Gapless transitions — prebuffer with daemon thread + shutdown Event
- [x] Callback safety — callbacks outside lock
- [x] Resource cleanup — stop() releases handles
- [ ] **RealtimeProcessor sample rate** — ENG-08 (static config vs dynamic rate)

### Dimension 4: Audio I/O
- [x] Format coverage — MP3, FLAC, WAV, AAC, OGG, OPUS handled
- [x] Corrupt file handling — meaningful errors raised
- [x] Sample rate detection — from metadata, never assumed
- [ ] **Multi-channel downmix** — ENG-07 (returns view, keeps full array alive)
- [x] FFmpeg subprocess — properly terminated, temp files cleaned up
- [x] Metadata extraction — robust parsing confirmed

### Dimension 5: Parallel Processing
- [x] Chunk independence — workers receive new arrays (chunk * window = new)
- [x] Reassembly order — correct ordering maintained
- [x] Boundary smoothing — crossfade applied at chunk boundaries
- [x] Sample count — preserved across parallel processing
- [x] Thread pool — sized appropriately, cleaned up on cancellation

### Dimension 6: Analysis Subsystem
- [ ] **Fingerprint edge cases** — ENG-09 (pathological inputs)
- [ ] **Mel filterbank re-allocation** — ENG-05 (per-track instead of cached)
- [ ] **FingerprintService raw SQL** — ENG-04 (bypasses repository pattern)
- [x] Quality metrics — LUFS, DR correctly computed
- [x] Thread safety — analysis tasks don't interfere (verified)

### Dimension 7: Library & Database
- [x] Repository pattern — all access via repositories (except ENG-04)
- [x] SQLite config — `pool_pre_ping=True`, WAL mode, `check_same_thread=False`
- [x] Scanner robustness — symlinks, permissions handled
- [x] Migration safety — inter-process file locking
- [x] Engine disposal — `MigrationManager.close()` disposes engine
- [x] Cleanup — cursor-based pagination (fix `bd94fd59` verified)
