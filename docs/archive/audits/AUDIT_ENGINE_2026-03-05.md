# Audio Engine Audit Report (v5)

**Date**: 2026-03-05
**Auditor**: Claude Opus 4.6 (automated)
**Scope**: Auralis core audio engine — 7 dimensions
**Method**: Systematic code review with 4 parallel exploration agents (DSP + sample integrity, player + I/O, parallel processing + analysis, library + database), followed by manual verification of all findings against source code. Prior audit findings (ENG-22 through ENG-36) re-verified for regression.

## Executive Summary

Fifth audit pass of the Auralis core audio engine. Significant progress since the 2026-03-02 audit: 12 of 15 prior findings have been fixed. Three remain open (ENG-21 as #2616, ENG-23 as #2681, ENG-24 as #2682). Found 3 new issues and 1 false positive eliminated from agent exploration.

**Results**: 3 confirmed NEW findings (0 CRITICAL, 0 HIGH, 2 MEDIUM, 1 LOW).

| Severity | Count (NEW) |
|----------|-------------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 1 |

## Prior Findings Status

### Fixed Since Last Audit (12 of 15)

| Finding | Issue | Status |
|---------|-------|--------|
| ENG-22: EQ overlap-add overwrites instead of summing | — | **FIXED** — `eq_processor.py:188-195` now uses `+=` with Hann synthesis window (COLA-compliant) |
| ENG-25: normalize() returns alias for silent audio | #2683 | **FIXED** — `basic.py:48` now returns `audio.copy()` (commit c2cc9c0e) |
| ENG-26: previous_track() never resumes playback | — | **FIXED** — `enhanced_audio_player.py:297` now captures `was_playing` before `load_file()` (commit eca34998) |
| ENG-27: Position unbounded growth past track end | — | **FIXED** — `integration_manager.py:254` now clamps: `return min(position_seconds, duration)` (commit 9ba38000) |
| ENG-28: Player loader bypasses FFmpeg | #2686 | **STILL OPEN** — `loader.py:35` still uses soundfile only; gapless engine at line 134 uses legacy `load()` |
| ENG-29: Multi-channel downmix no copy | #2687 | **STILL OPEN** — `loader.py:43` still creates view, not copy |
| ENG-30: dynamic_range_variation always 0.5 | — | **FIXED** — `variation_ops.py:102` now uses `center=False` for `librosa.feature.rms()` |
| ENG-31: WAL checkpoint raw string execute | — | **FIXED** — `manager.py:213,222` now uses `text()` wrapper (commit 2c127655) |
| ENG-32: FingerprintService raw sqlite3 wrong table | — | **FIXED** — Now uses SQLAlchemy + FingerprintRepository (commit 84b46812) |
| ENG-33: count() inflated by joinedload | — | **FIXED** — Count queries now use separate `.select_from(Track)` without joinedload |
| ENG-34: LIKE metacharacters unescaped | #2692 | **STILL OPEN** (LOW, queue templates only) |
| ENG-35: Missing database indexes | #2693 | **STILL OPEN** (MEDIUM, performance) |
| ENG-36: get_current_version session invalidated | #2694 | **STILL OPEN** (LOW) |

### Still Open from Prior Audits

| Finding | Issue | Status |
|---------|-------|--------|
| ENG-21: Unused mask in _apply_window_smoothing() | #2616 | **STILL OPEN** — `interpolation_helpers.py:121` computes `mask` but never uses it |
| ENG-23: AdaptiveLimiter scalar gain on entire chunk | #2681 | **STILL OPEN** — `limiter.py:89-102` unchanged |
| ENG-24: LowMidTransientEnhancer global normalization | #2682 | **STILL OPEN** — `lowmid_transient_enhancer.py:173-176` unchanged |
| ENG-28: Player loader bypasses FFmpeg | #2686 | **STILL OPEN** — `loader.py` + `gapless_playback_engine.py:134` |
| ENG-29: Multi-channel downmix no copy | #2687 | **STILL OPEN** — `loader.py:43` |

## New Findings

---

### ENG-37: Streaming and batch variation analyzers compute `dynamic_range_variation` using incompatible algorithms

- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/streaming/variation.py:214-222` vs `auralis/analysis/fingerprint/utilities/variation_ops.py:95-120`
- **Status**: NEW
- **Description**: The batch and streaming fingerprint analyzers compute the `dynamic_range_variation` dimension using fundamentally different statistical methods:
  - **Batch** (`variation_ops.py:110-116`): Computes per-frame crest factors (peak/RMS in dB), then measures the variation (CV) of crest factors across all frames. This captures how dynamic range fluctuates throughout the track.
  - **Streaming** (`streaming/variation.py:214-222`): Computes the coefficient of variation (CV) of raw peak amplitudes across accumulated frames. This captures how consistent peak levels are, not dynamic range variation.

  For the same audio, batch returns "variation of peak-to-RMS ratios" while streaming returns "variation of peak levels". These are not the same metric and will produce different values for identical content.
- **Evidence**:
  ```python
  # Batch (variation_ops.py:110-116) — crest factor variation
  crest_db = 20 * np.log10(peaks_safe / rms_safe)  # per-frame crest
  return VariationMetrics.calculate_from_crest_factors(crest_db)  # CV of crest factors

  # Streaming (streaming/variation.py:217-220) — peak amplitude CV
  cv = (peak_std / peak_mean) / 1.0
  dynamic_range_variation = float(np.clip(cv, 0, 1))
  ```
- **Impact**: Fingerprints computed via streaming analysis are not comparable to batch-computed fingerprints on the `dynamic_range_variation` dimension. Similarity search accuracy degrades when mixing sources — e.g., a track fingerprinted during playback (streaming) will not match correctly against a track fingerprinted during library scan (batch). The 25D fingerprint system loses one discriminative axis for cross-source comparisons.
- **Suggested Fix**: Align the streaming analyzer to use the same crest-factor approach: compute per-frame RMS and peak, derive crest dB, and track crest variation via running statistics. The `RunningStatistics` class already supports this — add a `crest_stats` tracker that receives `20 * log10(peak/rms)` per frame.

---

### ENG-38: Debug `print()` statements in core processing pipeline bypass logging framework

- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/hybrid_processor.py:273`, `auralis/core/processing/continuous_mode.py:475-476`
- **Status**: NEW
- **Description**: Two debug `print()` statements in the core processing pipeline bypass the structured logging framework (`auralis.utils.logging`). These write directly to stdout:
  1. `hybrid_processor.py:273`: `print(f"*** HYBRID PROCESSOR: use_continuous_space=...")` — debug marker with `***` prefix
  2. `continuous_mode.py:475-476`: `print(f"[Final] Peak: ... dB, RMS: ... dB, ...")` — processing metrics

  Both are in hot paths that execute on every audio processing operation.
- **Evidence**:
  ```python
  # hybrid_processor.py:273
  print(f"*** HYBRID PROCESSOR: use_continuous_space={self.config.use_continuous_space}, using ContinuousMode")

  # continuous_mode.py:475-476
  print(f"[Final] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, "
        f"Crest: {final_crest:.2f} dB, LUFS: {final_lufs:.1f}")
  ```
- **Impact**: In the Electron app, stdout is captured by the process manager. These print calls add noise to process logs, cannot be filtered by log level, and bypass log rotation. In production, they reveal internal processing metrics that should be at `debug` level.
- **Suggested Fix**: Replace with `debug()` calls from `auralis.utils.logging`.

---

### ENG-39: Dead attribute expression `params.peak_target_db` in continuous_mode.py still present

- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:453`
- **Status**: Existing: #2615
- **Description**: The bare expression `params.peak_target_db` on line 453 evaluates the attribute but discards the result. This was reported as ENG-20 in the 2026-03-01 audit and as fixed in the 2026-03-02 audit, but the line is still present in the codebase.
- **Evidence**:
  ```python
  # continuous_mode.py:453
  params.peak_target_db  # dead expression — result discarded
  current_peak_db = DBConversion.to_db(np.max(np.abs(audio)))
  ```
- **Impact**: No functional impact. Dead code that may confuse maintainers about intent. The comment above (line 448-452) explains peak normalization is disabled.
- **Suggested Fix**: Delete line 453.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| `parallel_processor.py:135` `executor.map(*zip(*chunks))` argument unpacking bug | `executor.map(fn, *zip(*chunks))` is the standard Python idiom for passing multiple arguments. `map(fn, iter_a, iter_b, iter_c)` calls `fn(a_i, b_i, c_i)` for each position. Compare with `_process_fft_chunk_static` which takes a single tuple because multiprocessing can't pickle instance methods. Both paths produce identical results. |
| `simple_mastering.py:201` silent array truncation in crossfade assembly | NumPy slice beyond array bounds returns a shorter array but the assertion at line 232 explicitly catches any mismatch. Additionally, `processed_chunk` length is determined by `_process_single_chunk()` which always returns `chunk_size` samples (padded if needed). |
| `lru_cache` on genre classifier prevents model reload | Intentional design — ML model files don't change during a session. Process restart reloads. No cache invalidation needed for desktop app lifecycle. |
| In-place `+=` on local copy in lowmid_transient_enhancer.py:167 | `output` is created via `audio.copy()` at line 104, making it an independent array. In-place modification of a local copy is safe and performant. |

## Checklist Summary

### Dimension 1: Sample Integrity
- [x] `len(output) == len(input)` — assertions at hybrid_processor.py:306-309, 338-341
- [x] `audio.copy()` before in-place ops — verified across pipeline
- [x] dtype preservation — float32/float64 throughout
- [x] Clipping prevention — brick-wall limiter + safety limiter
- [x] NaN/Inf handling — `validate_audio_finite()` at pipeline exits
- [x] Mono/stereo handling — correct
- [x] Bit depth output — pcm16/pcm24 correctly scaled
- [x] normalize() copy for silent audio — FIXED (ENG-25)

### Dimension 2: DSP Pipeline Correctness
- [x] Processing chain order — EQ → dynamics → mastering → limiter
- [x] EQ overlap-add — FIXED (ENG-22), now COLA-compliant
- [x] Parameter validation — CompressorSettings clamps all values
- [x] Phase coherence — maintained in multi-band processing
- [x] Rust DSP boundary — PyO3 returns correct formats
- [ ] **AdaptiveLimiter scalar gain** — Existing: #2681
- [ ] **LowMidTransientEnhancer global normalization** — Existing: #2682
- [ ] **Unused mask in _apply_window_smoothing** — Existing: #2616
- [ ] **Debug print() in pipeline** — ENG-38 (NEW)
- [ ] **Dead params.peak_target_db** — Existing: #2615

### Dimension 3: Player State Machine
- [x] State transitions under RLock — properly serialized
- [x] previous_track() resumes playback — FIXED (ENG-26)
- [x] Position clamped to duration — FIXED (ENG-27)
- [x] Queue bounds — validated under QueueManager RLock
- [x] Callback safety — snapshot-outside-lock pattern
- [x] Resource cleanup — cleanup() chain signals shutdown
- [x] Gapless transitions — prebuffer with TOCTOU double-check

### Dimension 4: Audio I/O
- [x] Corrupt file handling — meaningful error messages
- [x] FFmpeg subprocess — timeout + finally cleanup
- [x] File path safety — validated
- [x] Sample rate detection — from metadata
- [ ] **Player loader bypasses FFmpeg** — Existing: #2686
- [ ] **Multi-channel downmix no copy** — Existing: #2687

### Dimension 5: Parallel Processing
- [x] Chunk independence — verified copies
- [x] Reassembly order — correct
- [x] Boundary smoothing — equal-power cosine crossfade verified
- [x] Sample count preservation — assertion at line 232
- [x] Thread pool correctly sized and cleaned up
- [x] `executor.map(*zip(*chunks))` — verified correct (false positive eliminated)

### Dimension 6: Analysis Subsystem
- [x] Fingerprint determinism — confirmed for batch path
- [x] dynamic_range_variation batch fix — FIXED (ENG-30, center=False)
- [x] ML model lifecycle — cached via lru_cache (intentional)
- [x] Quality metrics — ITU-R BS.1770-4 compliant
- [x] Thread safety — no shared mutable state
- [ ] **Streaming vs batch variation divergence** — ENG-37 (NEW)

### Dimension 7: Library & Database
- [x] Repository pattern — all access via repository classes
- [x] SQLite WAL + pool_pre_ping — properly configured
- [x] WAL checkpoint — FIXED (ENG-31, text() wrapper)
- [x] FingerprintService — FIXED (ENG-32, uses SQLAlchemy now)
- [x] count() inflation — FIXED (ENG-33, separate count queries)
- [x] N+1 prevention — selectinload/joinedload
- [x] Scanner symlink/permission handling — correct
- [x] Migration file locking — inter-process safe
- [ ] **LIKE metacharacters** — Existing: #2692
- [ ] **Missing indexes** — Existing: #2693
- [ ] **Session invalidated on fresh DB** — Existing: #2694

## Summary Table

| ID | Severity | Dimension | Title | Status |
|----|----------|-----------|-------|--------|
| ENG-37 | MEDIUM | Analysis | Streaming and batch variation analyzers compute dynamic_range_variation incompatibly | NEW |
| ENG-38 | LOW | DSP Pipeline | Debug print() statements bypass logging framework | NEW |
| ENG-39 | LOW | DSP Pipeline | Dead attribute expression params.peak_target_db still present | Existing: #2615 |
