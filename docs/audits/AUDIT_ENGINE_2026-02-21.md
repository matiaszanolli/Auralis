# Audio Engine Audit
**Date**: 2026-02-21
**Auditor**: Claude Sonnet 4.6 (automated)
**Scope**: Sample integrity, DSP pipeline correctness, player state safety, audio I/O robustness, parallel processing correctness, analysis reliability, and library/database integrity.

---

## Deduplication — Existing Open Issues Excluded

The following engine-related issues are already open and **excluded** from new findings:

| Issue | Description |
|-------|-------------|
| #2306 | `SimpleMastering` output normalization only normalizes UP, never reduces hot peaks |
| #2293 | `BrickWallLimiter` sample-by-sample Python loop — O(n × lookahead) performance |
| #2226 | Soundfile loader logs wrong channel count after truncation |
| #2074 | FFmpeg process not terminated on timeout (pre-existing; `subprocess.run` timeout=300 now handles kill) |
| #2327 | Chunk boundary calculations may produce fractional samples at non-standard sample rates |
| #2316 | `_load_audio_placeholder` returns random noise, reachable in production |
| #2310 | AutoMasterProcessor uses pre-compression peak for gain reduction |
| #2408 | No test for gapless prebuffer with tracks of different sample rates |
| #2369 | Missing regression test: runtime sample count assertion in HybridProcessor |
| #2368 | Missing regression test: parallel sub-bass processing (ParallelEQUtilities) |

---

## Dimension 1: Sample Integrity

**Files audited**: `auralis/core/simple_mastering.py`, `auralis/dsp/dynamics/brick_wall_limiter.py`, `auralis/utils/audio_validation.py`, `auralis/dsp/eq/filters.py`, `auralis/dsp/dynamics/compressor.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| `processed = audio.copy()` before in-place ops | `simple_mastering.py:298` | Explicit copy at top of `_process()` |
| `validate_audio_finite(repair=False)` at input | `simple_mastering.py:301` | Fail-fast on NaN/Inf before processing begins |
| `sanitize_audio()` at output | `simple_mastering.py:361` | Graceful NaN replacement for production resilience |
| Equal-power crossfade (`sin²/cos²`) at chunk boundaries | `simple_mastering.py:220-223` | Correct spectral preservation at transitions |
| Transactional tail commit | `simple_mastering.py:244-248` | `prev_tail` updated only after successful write |
| `prev_gain` seeded from `self.current_gain` | `brick_wall_limiter.py:110` | Cross-chunk gain envelope continuity (fixes #2390) |
| `audio_chunk.dtype` preserved through padding | `filters.py:39` | Explicit `dtype=audio_chunk.dtype` prevents float32→float64 promotion during FFT padding |
| `np.asarray(..., dtype=audio_mono.dtype)` | `filters.py:103` | dtype explicitly restored after IFFT |

### Findings: NONE beyond excluded issues

The `filters.py` padding-and-squeeze pattern is correct:
- Mono 1D → shaped to `(fft_size, 1)` → `squeeze()` → `(fft_size,)` → routed to mono path. ✓
- Stereo `(N, 2)` → padded to `(fft_size, 2)` → `squeeze()` is a no-op → routed to stereo path. ✓
- Both paths slice output to `[:original_len]` after `apply_eq_mono` returns `fft_size`-length arrays. ✓

The `compressor.py` lookahead buffer update (lines 175-176) is correct:
- `np.roll()` returns a new array (not a view).
- Slice assignment `self.lookahead_buffer[-audio_len:] = audio` copies values — buffer does not alias `audio`. ✓

The `_apply_safety_limiter()` returning `audio` unchanged (line 437) when no clipping occurs is safe:
- All callers immediately rebind `processed = self.pipeline._apply_safety_limiter(processed, verbose)`.
- The returned reference is not mutated; if limiting triggers, a new `soft_clip` result is returned. ✓

---

## Dimension 2: DSP Pipeline Correctness

**Files audited**: `auralis/core/hybrid_processor.py`, `auralis/core/mastering_branches.py`, `auralis/dsp/unified.py`, `auralis/dsp/psychoacoustic_eq.py`, `auralis/dsp/advanced_dynamics.py`, `auralis/dsp/eq/filters.py`, `auralis/dsp/utils/spectral.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| `mono_audio.astype(np.float64)` scoped locally | `spectral.py:204` | Local variable for Rust FFI; original array not modified; returns `float` not array |
| Gains clipped to ±12 dB | `psychoacoustic_eq.py:226` | Prevents runaway gain from fingerprint mismatch |
| Division-by-zero guards (`max(value, 1e-10)`) | `compressor.py:118`, `limiter.py:109-113` | All `log10()` calls protected |
| `fixed_targets` skip content analysis | `hybrid_processor.py:163` | 8× speedup for preset mode; safe since targets pre-validated |
| HybridProcessor components created once in `__init__` | `hybrid_processor.py:60-125` | No per-request state reset needed; pipeline is stateless across calls |

### Findings: NONE beyond excluded issues

Processing chain order (EQ → dynamics → safety limiter) verified in `mastering_branches.py`:
- Lines 230 and 301: `_apply_safety_limiter()` is always the final stage. ✓
- Psychoacoustic EQ receives `processed` copy; advanced dynamics receive EQ output. ✓

---

## Dimension 3: Player State Machine

**Files audited**: `auralis/player/enhanced_audio_player.py`, `auralis/player/gapless_playback_engine.py`, `auralis/player/queue_controller.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| `_fingerprint_lock` (threading.Lock) | `enhanced_audio_player.py:110` | Protects `_current_fingerprint` (fixes CC-02 / #2491) |
| `_auto_advancing` threading.Event | `enhanced_audio_player.py:110` | Atomic guard prevents duplicate auto-advance threads |
| Snapshot callbacks before iteration | `gapless_playback_engine.py:62-63` | Lock-free iteration of callback list copy (fixes #2412) |

### Findings: NONE beyond concurrency audit findings

CC-01, CC-02, CC-03 from the preceding concurrency audit (AUDIT_CONCURRENCY_2026-02-20.md) cover the remaining player thread-safety gaps (#2490, #2491, #2492).

---

## Dimension 4: Audio I/O

**Files audited**: `auralis/io/loaders/ffmpeg_loader.py`, `auralis/io/loaders/soundfile_loader.py`, `auralis/io/unified_loader.py`, `auralis/io/results.py`, `auralis/io/saver.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| File existence + `is_file()` check | `ffmpeg_loader.py:98-100` | Validates before FFmpeg invocation |
| Protocol URL guard (`"://" in path`) | `ffmpeg_loader.py:102-104` | Prevents `http://`, `pipe:` injection to FFmpeg |
| `subprocess.run(timeout=300)` kills FFmpeg on timeout | `ffmpeg_loader.py:142` | Python stdlib kills process before raising `TimeoutExpired` (addresses #2074) |
| Temp file in `finally` block | `ffmpeg_loader.py:175-182` | Cleanup runs even on exception |
| Duration percentage validation (10% / 90% thresholds) | `ffmpeg_loader.py:156-167` | Detects severely and moderately truncated files |
| `sf.read(..., always_2d=False)` | `soundfile_loader.py:27` | Consistent mono representation |

### EAE-01: `ffmpeg_loader.py` — Sample Rate Silently Defaults to 44100 Hz on Probe Failure

- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:109-112`
- **Status**: NEW
- **Description**: When `_probe_audio()` returns `None` for `sample_rate` (FFprobe failed or returned unexpected output), the loader falls back to `44100` and immediately uses that rate in the FFmpeg conversion command (`-ar 44100`). A file encoded at 48 kHz, 96 kHz, or any non-44100 rate will be permanently resampled to the assumed 44100 Hz rate, causing irreversible quality loss with no way for the caller to detect the error.
- **Evidence**:
  ```python
  # ffmpeg_loader.py:109-112
  source_sample_rate = probe['sample_rate'] or 44100   # silent fallback
  source_channels   = probe['channels']   or 2         # silent fallback
  if probe['sample_rate'] is None or probe['channels'] is None:
      warning(f"Could not probe sample rate/channels for {file_path}; defaulting to ...")
  # ...
  '-ar', str(source_sample_rate),   # FFmpeg converts to assumed rate
  ```
  A 48 kHz stereo file where FFprobe silently fails will be resampled to 44100 Hz before any processing occurs, degrading the full signal chain downstream.
- **Impact**: Silent sample-rate mismatch for files at 48 kHz, 96 kHz, or 88.2 kHz. All downstream quality measurements (LUFS, crest factor) are computed on the wrongly-resampled audio. Gapless prebuffers between a 44100 Hz track and an assumed-44100 Hz 48 kHz track will produce audible artifacts.
- **Suggested Fix**: Raise `ModuleError` when `probe['sample_rate']` is `None` rather than silently defaulting. A user-surfaced error is preferable to silent quality loss. If a lenient fallback is retained for legacy compatibility, at minimum use a configurable default and emit a WARNING-level log, not DEBUG.

---

## Dimension 5: Parallel Processing

**Files audited**: `auralis/optimization/parallel_processor.py`, `auralis/core/simple_mastering.py`, `auralis/core/mastering_branches.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| List comprehension (not `* n`) for band arrays | `parallel_processor.py:218-222` | Independent arrays per band (fixes #2424) |
| ThreadPoolExecutor in context manager | `parallel_processor.py:108, 112, 225` | Guaranteed cleanup on exception |
| Window/FFT cache behind `threading.Lock` | `parallel_processor.py:42, 60-64` | Lock-protected cache (addresses existing #2077 contention) |
| Equal-power crossfade at chunk boundaries | `simple_mastering.py:220-223` | Correct spectral preservation |
| `new_tail = ...copy()` in crossfade paths | `simple_mastering.py:202, 230, 238` | Independent tail per chunk boundary |

### Findings: NONE

Sample count invariant `sum(chunk_lengths) == total_length` verified through the chunked streaming path — each chunk is independently processed, reassembled in sequence via the ordered `futures` list, and crossfade tails are copied not shared.

---

## Dimension 6: Analysis Subsystem

**Files audited**: `auralis/analysis/quality_assessors/utilities/scoring_ops.py`, `auralis/analysis/quality_assessors/utilities/estimation_ops.py`, `auralis/analysis/quality/quality_metrics.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| `max(noise_level, silence_threshold)` before `log10` | `estimation_ops.py:122` | Prevents `log10(0)` |
| Zero check before stereo correlation division | `estimation_ops.py:158` | Guards `numerator / denominator` |
| `mid_energy == 0` guard for stereo width | `estimation_ops.py:276-277` | Prevents `0 / 0 = nan` on silent audio |

### EAE-02: `scoring_ops.py` — `linear_scale_score()` Has No NaN Guard

- **Severity**: LOW
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/analysis/quality_assessors/utilities/scoring_ops.py:37-46`
- **Status**: NEW
- **Description**: `linear_scale_score()` performs `(value - min_val) / (max_val - min_val)` without first checking whether `value`, `min_val`, or `max_val` is `NaN`. If any upstream quality metric produces a `NaN` (e.g., from a completely silent file, an analysis timeout, or floating-point underflow in a complex pipeline), the NaN propagates through `np.clip(score, 0, 100)` — which returns NaN for NaN inputs — into the final quality score dict. All callers that display or store quality scores will then receive `NaN`.
- **Evidence**:
  ```python
  # scoring_ops.py:37-46
  if max_val == min_val:
      return 100.0 if value == max_val else 0.0   # NaN == min_val is False, falls through

  normalized = (value - min_val) / (max_val - min_val)  # NaN propagates
  score = normalized * 100                               # NaN
  # ...
  return float(np.clip(score, 0, 100))  # np.clip(nan, 0, 100) → nan
  ```
  The existing `max_val == min_val` guard is bypassed by NaN because `NaN == X` is always False.
- **Impact**: Library quality scores stored in the database as NaN; frontend displays `NaN%` or `NaN/100` for quality ratings; sort-by-quality returns incorrect ordering.
- **Suggested Fix**: Add `if not np.isfinite(value): return 0.0` (or `50.0` as a neutral default) at the start of `linear_scale_score()`. Apply the same guard to `range_based_score()` and `exponential_penalty()` for consistency.

---

## Dimension 7: Library & Database

**Files audited**: `auralis/library/manager.py`, `auralis/library/cache.py`, `auralis/library/migration_manager.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| Inter-process migration lock (`fcntl` / `msvcrt`) | `migration_manager.py:34-116` | Non-blocking retry with 30 s timeout |
| Double-check version re-read after acquiring lock | `migration_manager.py:423-426` | Concurrent migrators handled correctly |
| SQLite Online Backup API (`src.backup(dst)`) | `migration_manager.py:349` | Consistent snapshot through WAL |
| `_delete_lock` (RLock) + PRE+POST cache invalidation | `manager.py:527-551` | Serialises concurrent deletes |
| `pool_pre_ping=True` | `manager.py:118` | Prevents stale connection re-use |
| `PRAGMA journal_mode=WAL` | `manager.py:129` | Readers don't block writers |

### Findings: NONE beyond concurrency audit findings

CC-05 from the preceding concurrency audit (QueryCache dict operations not thread-safe, `library/cache.py:70-156`) covers the only new library finding. See #2494.

---

## Summary Table

| ID | Severity | Dimension | Location | Status |
|----|----------|-----------|----------|--------|
| EAE-01 | MEDIUM | Audio I/O | `io/loaders/ffmpeg_loader.py:109-112` | NEW → Issue created |
| EAE-02 | LOW | Analysis Subsystem | `analysis/quality_assessors/utilities/scoring_ops.py:37-46` | NEW → Issue created |
| — | LOW | Audio I/O | `io/loaders/soundfile_loader.py:57-58` | Existing #2226 |
| — | MEDIUM | DSP | `core/simple_mastering.py:353` | Existing #2306 |
| — | MEDIUM | DSP Performance | `dsp/dynamics/brick_wall_limiter.py:112` | Existing #2293 |
| — | LOW | DSP | `io/loaders/ffmpeg_loader.py:142` | Existing #2074 (mitigated) |

## Key Safe Architecture Decisions

- **Two-tier NaN strategy**: `validate_audio_finite(repair=False)` at pipeline input (fail-fast) + `sanitize_audio()` at output (production resilience). No findings.
- **Copy-before-modify**: `processed = audio.copy()` at the top of every `_process()` implementation and at all parallel chunk boundaries. No violations found.
- **dtype preservation**: EQ filter pipeline explicitly preserves `audio_chunk.dtype` through FFT padding and `astype(audio_mono.dtype)` after IFFT. No silent promotions in the hot path.
- **Rust DSP boundary**: `astype(np.float64)` before Rust call is strictly local; result is a Python `float`, never an array. No dtype leakage.
- **FFmpeg path safety**: URL protocol guard + file existence check + process timeout kill covers the attack surface. No path traversal or zombie process findings.
- **Lookahead buffer ownership**: `np.roll()` returns new arrays; slice assignment copies values into the buffer — no aliasing between the lookahead buffer and caller audio arrays.
