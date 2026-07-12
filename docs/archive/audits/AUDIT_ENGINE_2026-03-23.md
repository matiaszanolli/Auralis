# Engine Audit — 2026-03-23

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: Core audio engine — `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/optimization/`, `auralis/analysis/`, `auralis/library/`, `vendor/auralis-dsp/`
**Dimensions**: Sample Integrity, DSP Pipeline, Player State, Audio I/O, Parallel Processing, Analysis, Library & Database
**Method**: 3 parallel dimension agents (Sonnet), merged with dedup against 5 open engine issues and 15 recent fix commits.

## Executive Summary

This audit found **28 genuinely new findings** after deduplicating against 15 recent fixes and all open engine issues. Four HIGH findings represent real audio quality and stability risks.

**Key themes:**

1. **DSP correctness** (ENG-22 through ENG-26) — The EQ processor's OLA synthesis violates COLA constraint causing ~6dB ripple. The Rust onset detector panics/OOMs on short audio. Limiters have flawed lookahead window origins.

2. **True peak measurement discarded** (DIM5-02) — `LoudnessMeter.finalize_measurement` overwrites the oversampled true-peak with sample peak, making Spotify compliance checks unreliable.

3. **Parallel processing error handling** (DIM5-01) — Grouped-band parallel path lacks the per-future error handling that the flat-band path has.

4. **Player state gaps** (PSM-1 through PSM-5) — Position lock doesn't actually protect position reads; auto-advance overrides explicit stop; ERROR state silently swallows play.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 7 |
| LOW | 17 |
| **Total** | **28** |

---

## HIGH

---

### ENG-22: EQ processor OLA synthesis violates COLA constraint — ~6dB periodic ripple
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/eq_processor.py:165-180`
- **Status**: NEW
- **Description**: Overlap-add synthesis applies a Hann window on output without matching analysis window. At 50% overlap this violates COLA, producing systematic ~6dB amplitude error with periodic ripple at hop rate (~46ms). Final normalization partially masks it but EQ shape accuracy is degraded.
- **Impact**: Audible amplitude ripple on all EQ-processed audio. EQ curve applied inaccurately.
- **Suggested Fix**: Apply matching analysis window or use sqrt-Hann on both analysis and synthesis sides.

---

### ENG-23: Rust onset_detector unsigned subtraction wraps on short audio — OOM/hang
- **Severity**: HIGH
- **Dimension**: DSP Pipeline / Sample Integrity
- **Location**: `vendor/auralis-dsp/src/onset_detector.rs:58`
- **Status**: NEW
- **Description**: `(audio.len() - self.fft_size)` is unsigned subtraction. When audio < 2048 samples (~46ms), wraps to huge usize in release mode, causing enormous allocation.
- **Impact**: OOM crash or hang on very short audio clips (intros, transitions, samples).
- **Suggested Fix**: Add length guard: `if audio.len() < self.fft_size { return Ok(vec![]); }`.

---

### DIM5-01: ParallelBandProcessor grouped-band path has no per-future error handling
- **Severity**: HIGH
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel_processor.py` (ParallelBandProcessor._process_band_groups)
- **Status**: NEW
- **Description**: `future.result()` inside list comprehension has no error handling. A single bad filter kills entire grouped-band output. The flat-band parallel path correctly catches per-future exceptions.
- **Impact**: One band failure silently corrupts all parallel band output — audio quality loss.
- **Suggested Fix**: Wrap `future.result()` in try/except matching the flat-band path pattern.

---

### DIM5-02: LoudnessMeter.finalize_measurement discards true peak — compliance check unreliable
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/quality/loudness_meter.py` (finalize_measurement)
- **Status**: NEW
- **Description**: Both `peak_level_dbfs` and `true_peak_dbfs` set to running sample peak. The correctly oversampled true-peak computed in `measure_chunk` is discarded. `LoudnessAssessor` uses `true_peak_dbfs` for Spotify max-peak compliance.
- **Impact**: Over-limit audio passes Spotify compliance check. True peak always underreported.
- **Suggested Fix**: Store oversampled true-peak separately in `measure_chunk` and use it in `finalize_measurement`.

---

## MEDIUM

---

### ENG-24: VectorizedEnvelopeFollower allocates float64 regardless of input dtype
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/advanced_dynamics.py` (VectorizedEnvelopeFollower.process_buffer_vectorized)
- **Status**: NEW
- **Description**: Working buffer always float64, result cast back to float32. Breaks dtype-preservation invariant.
- **Suggested Fix**: Allocate working buffer matching input dtype.

---

### ENG-25: BrickWallLimiter maximum_filter1d origin parameter gives centred window not forward-looking
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/advanced_dynamics.py` (BrickWallLimiter)
- **Status**: NEW
- **Description**: `origin=-(lookahead//2)` produces centred window instead of forward-looking. Effective lookahead halved (~1ms instead of ~2ms).
- **Impact**: Transients partially escape limiter detection.
- **Suggested Fix**: Use `origin=-lookahead` for fully forward-looking detection.

---

### ENG-26: Rust Limiter uses block-uniform gain — audible pumping at boundaries
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `vendor/auralis-dsp/src/limiter.rs` (Limiter.process_core)
- **Status**: NEW
- **Description**: Computes single scalar gain from block maximum, applies uniformly. Causes over-limiting of non-peak samples and pumping at block boundaries.
- **Suggested Fix**: Implement per-sample gain curve with release time constant.

---

### PSM-1: _position_lock does not actually protect playback.position reads
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/integration_manager.py` (_get_position_seconds)
- **Status**: NEW
- **Description**: `playback.position` is mutated under `PlaybackController._lock` (separate RLock). During gapless transition, old position + new sample_rate produces meaningless result.
- **Suggested Fix**: Read position under PlaybackController._lock, or make position an atomic value.

---

### IO-1: loader.py bypasses WAV truncation detection in soundfile_loader.py
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loader.py`
- **Status**: NEW
- **Description**: Player load path calls `sf.read()` directly, bypassing RIFF declared-size vs actual-size truncation check. Truncated WAV loaded with partial data.
- **Suggested Fix**: Route through `soundfile_loader.py` or add truncation check to `loader.py`.

---

### DIM5-03: BatchProcessor.process_single_file queries get_track_by_filepath twice
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner.py` (BatchProcessor.process_single_file)
- **Status**: NEW
- **Description**: Queries same filepath twice on modification-check path. Doubles DB round-trips and opens TOCTOU gap.
- **Suggested Fix**: Cache first query result and reuse.

---

### DIM5-04: MigrationManager persistent session never closed on constructor exception
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_manager.py`
- **Status**: NEW
- **Description**: `self.session` not closed on constructor exception paths. Rollback at line 285 is no-op for raw_connection DDL path.
- **Suggested Fix**: Use context manager for session lifecycle. Add proper rollback for raw_connection path.

---

## LOW (17 findings)

### DSP / Sample Integrity (4)
- **ENG-27**: `amplify()` has no documented copy guarantee — relies on implicit NumPy behavior.
- **ENG-28**: `_process_reference_mode` skips brick-wall limiter unlike other modes — no peak ceiling before PCM.
- **ENG-29**: `AdaptiveCompressor._apply_lookahead` partial-chunk branch returns zero-padded start.
- **ENG-30**: Bare `print()` in `hybrid_processor.py:273` not covered by existing #2706 fix.

### Player State (4)
- **PSM-2**: `load_file()` PLAYING→LOADING→STOPPED not atomic — `previous_track()` drops resume.
- **PSM-3**: `get_audio_chunk()` gap between `is_loaded()`/`is_playing()` and `read_and_advance_position()`.
- **PSM-4**: `_auto_advance_next` no combined lock — user `stop()` overridden by advance thread.
- **PSM-5**: `PlaybackController.play()` silently returns False from ERROR state — no user feedback.

### Audio I/O (3)
- **IO-2**: No file-size/duration guard before loading converted WAV into RAM — OOM risk.
- **IO-3**: `_get_info_with_ffprobe` `int("N/A")` raises ValueError for Ogg/OPUS bitrate.
- **IO-4**: `AudioFileManager.load_reference()` reads reference_data after releasing lock — race.

### Parallel Processing (1)
- **DIM5-10**: `@parallelize` decorator creates unpicklable closure — breaks with `use_multiprocessing=True`.

### Analysis (3)
- **DIM5-05**: `AudioFingerprintAnalyzer.analyze` swallows sub-analyzer failures, stores zero-vector fingerprint.
- **DIM5-07**: `LoudnessMeter.measurement_duration` reports call count × 0.1s instead of actual duration.
- **DIM5-08**: `BatchAnalyzer.export_profiles_yaml` try block contains only `pass` — dead ImportError fallback.

### Library (3)
- **DIM5-06**: `cleanup_missing_files` TOCTOU between exists() check and batch DELETE.
- **DIM5-09**: MigrationManager engine lacks `PRAGMA busy_timeout=60000`.
- **DIM5-11**: Non-recursive FileDiscovery uses case-sensitive globs — skips `.MP3`, `.FLAC` on Linux.

---

## Relationships & Shared Root Causes

1. **Limiter accuracy chain**: ENG-25 (Python BrickWallLimiter origin), ENG-26 (Rust Limiter block-uniform), and ENG-28 (reference mode skips limiter) all compound — tracks can exceed peak ceiling through multiple paths.

2. **Lock discipline gaps**: PSM-1 (position lock misalignment), PSM-2/PSM-3/PSM-4 (non-atomic state transitions) share root cause of separate locks for related state.

3. **Error swallowing pattern**: DIM5-01 (band processor), DIM5-05 (fingerprint analyzer) both silently eat exceptions and return degraded data without logging.

## Prioritized Fix Order

1. **ENG-23** — Rust unsigned subtraction. Crash on short audio. One-line guard.
2. **DIM5-02** — True peak discarded. Compliance check broken. Store separately.
3. **ENG-22** — COLA violation in EQ. Systematic audio quality issue. Add analysis window.
4. **DIM5-01** — Grouped-band error handling. Match flat-band pattern.
5. **ENG-25 + ENG-26** — Limiter accuracy. Fix origin parameter and add per-sample gain.
6. **PSM-1** — Position lock alignment. Prevents gapless glitches.
7. **IO-1** — WAV truncation bypass. Route through soundfile_loader.

---

*Report generated by Claude Opus 4.6 — 2026-03-23*
*Suggest next: `/audit-publish docs/audits/AUDIT_ENGINE_2026-03-23.md`*
