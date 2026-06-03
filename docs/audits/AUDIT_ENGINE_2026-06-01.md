# Audio Engine Audit — 2026-06-01

**Scope**: Auralis core audio engine — DSP pipeline, player, analysis, library, parallel processing, audio I/O.
**Depth**: deep (full call-graph tracing). **Limit**: unlimited.
**Dedup baseline**: 186 open GitHub issues + prior `docs/audits/` engine reports through 2026-05-27.
**Dimensions**: all 7 (Sample Integrity, DSP Pipeline, Player State, Audio I/O, Parallel Processing, Analysis, Library & Database).

---

## Executive Summary

35 distinct findings (one cross-dimension duplicate merged). **2 are already-tracked open issues** (#4030, #4029), leaving **33 actionable findings**: 2 of those are regressions of previously-closed fixes (#3808, #3760).

| Severity | Count (new/actionable) | IDs |
|----------|------------------------|-----|
| **CRITICAL** | 0 | — |
| **HIGH** | 7 | SI-03, DSP-01, PP-01, PP-02, AN-01, AN-02, AN-03 |
| **MEDIUM** | 11 | SI-01, SI-02, SI-04, SI-06, DSP-02, DSP-03, PS-03, IO-01, AN-04, AN-05, LIB-02 |
| **LOW** | 14 | SI-05, DSP-05, PS-01, PS-02, PS-04, IO-02, IO-03, IO-04, IO-05, IO-06, AN-07, AN-08, LIB-01, LIB-03 |
| Existing (tracked) | 2 | DSP-04 (#4030), AN-06 (#4029) |

**No CRITICAL findings.** The hard audio-integrity invariants are well-defended: sample-count assertions, NaN/Inf validation at pipeline boundaries, the all-zeros guard, dtype-preserving `sosfiltfilt` casts across most DSP stages, `np.clip` before PCM write, Rust GIL release + `catch_unwind` panic safety, repository-pattern DB access, SQLite thread-safe pooling, migration file-locking, and N+1 prevention via `selectinload()`.

### Key Themes

1. **Rust/Python fingerprint divergence (highest-value cluster).** Four of the 25 fingerprint dimensions produce different values depending on which extraction path ran — and the Rust server is the default. `pitch_stability` is a hardcoded constant `0.5` (AN-01); `silence_ratio` and `rhythm_stability` use algorithmically incompatible formulas (AN-02); `lufs` is a non-gated RMS approximation (AN-08); `chroma_energy` was already known (#3690). This silently degrades similarity search and adaptive-mastering target selection across the entire library.

2. **Unbounded resource use on long files.** `MasteringFingerprint.from_audio_file()` decodes the full file with no `duration=` cap (AN-03, HIGH) — reachable from normal streaming playback; a 6-hour file ≈ 14 GB and OOM-kills the desktop process. Every sibling fingerprint path caps at 90 s.

3. **Concurrency regressions from the recent Phase-1 chunked-processor refactor.** `get_wav_chunk_path` guards the shared `HybridProcessor` with a *different* lock than `process_chunk_safe`, so two concurrent streams for the same track race on stateful DSP (PP-01, regression of #3808; the original fix is now dead code).

4. **Chunk sample-count violation.** ~49% of track durations get up to 5 s of trailing silence padded into the penultimate chunk because of an `is_last` detection gap (PP-02, HIGH).

5. **NaN-from-silence and dtype-promotion latent bugs.** Silent audio can become fully-NaN output via `amplify(audio, +inf)` and crash the stream (SI-03, HIGH). Several `sosfiltfilt`/`hann` paths silently promote float32→float64 (SI-04, SI-06, PP-03).

6. **Latent copy-before-modify gaps.** Stage bypass paths and an empty-input early return alias the caller's array (SI-01, SI-02) — benign in today's callers, a foot-gun for any future one.

---

## Findings

### HIGH

#### SI-03: Silent audio → fully-NaN output via `amplify(audio, +inf)` crashes the stream
- **Severity**: HIGH
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/continuous_mode.py:680-692`
- **Status**: NEW
- **Description**: `_apply_final_normalization` guards the LUFS measurement with `np.isfinite(current_lufs)` and falls back to `DBConversion.to_db(rms)`. For pure silence `rms == 0.0` → `to_db` returns `-inf`; there is **no second finite check** after the RMS fallback, so `adjustment = target_lufs - (-inf) = +inf`, and `amplify(silence, +inf)` computes `0.0 × inf = NaN` across the buffer.
- **Evidence**: `current_lufs = DBConversion.to_db(current_rms)` → `-inf`; `adjustment = target_lufs - current_lufs` → `+inf`; `audio = amplify(audio, adjustment)` → NaN (confirmed by execution).
- **Impact**: Silent chunks (intros, gaps, fades) routed through ContinuousMode produce all-NaN output, which hits `validate_audio_finite(..., repair=False)` in `_process_adaptive_mode` and raises `ModuleError`, crashing the stream for that track.
- **Suggested Fix**: After the RMS fallback, add `if not np.isfinite(current_lufs): return audio` (mirroring the all-zeros guard in `_process_impl`). Check `adaptive_mode.py` for the same normalization pattern.

#### DSP-01: Causal `sosfilt` high-pass on the direct signal smears bass transients
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/stages/sub_bass_control.py:58-63`
- **Status**: NEW
- **Description**: The rumble-removal HP (fires when `sub_bass_pct >= SUB_HP_ACTIVATE_PCT`) uses causal `sosfilt` on the main mastered signal. Every sibling stage was migrated to zero-phase `sosfiltfilt` (#3469/#3470/#3666); this is the last remaining causal IIR on the direct path. A 2nd-order Butterworth HP at 20–30 Hz adds ~15–30 ms group delay at 60 Hz.
- **Evidence**: `processed = np.asarray(sosfilt(hp_sos, processed, axis=axis), dtype=processed.dtype)` — vs `sosfiltfilt` in `parallel_eq.py:101`, `harmonic_exciter.py:135`, `resonance_notcher.py:205`, `continuous_mode.py:70`.
- **Impact**: Audible pre-echo / softened kick-drum attack on bass-heavy material when the HP engages (live recordings with strong room rumble).
- **Suggested Fix**: Replace `sosfilt` → `sosfiltfilt` + `.astype(processed.dtype, copy=False)`; update the import on line 6.

#### PP-01: `get_wav_chunk_path` and `process_chunk_safe` use different locks → shared `HybridProcessor` race
- **Severity**: HIGH
- **Dimension**: Parallel Processing
- **Location**: `auralis-web/backend/core/chunked_processor.py:803-882` (`get_wav_chunk_path`), `:638-670` (`process_chunk_safe`), `auralis-web/backend/core/audio_processing_pipeline.py:145-238`
- **Status**: Regression of #3808
- **Description**: `process_chunk_safe` accesses the cached processor under `_processor_lock`; `get_wav_chunk_path` calls `_process_chunk_core` under `_sync_cache_lock` — a *different* lock. `ProcessorFactory` caches one `HybridProcessor` per `(track_id, preset, intensity, ...)`, so two concurrent streams for the same track (WAV endpoint + WebSocket endpoint) both mutate `processor.content_analyzer.use_fingerprint_analysis` and call `processor.process()` on the same stateful object with no mutual exclusion. The original #3808 fix `_process_chunk_with_hybrid_processor` is now **dead code** (zero callers after the Phase-1 refactor).
- **Evidence**: `with self._sync_cache_lock:` … `self._process_chunk_core(...)` vs `with self._processor_lock:` … `self.process_chunk(...)`; both reach `processor.process()`.
- **Impact**: Corrupted compressor envelopes, EQ filter state, gain-reduction tracking, and fingerprint flag → pitched artefacts, volume discontinuities, wrong mastering decisions.
- **Suggested Fix**: In `get_wav_chunk_path`, wrap the `_process_chunk_core` call in `with self._processor_lock:` (or route through `_process_chunk_locked`). Remove the dead `_process_chunk_with_hybrid_processor`.

#### PP-02: `extract_chunk_segment` pads the penultimate chunk with silence for ~49% of durations
- **Severity**: HIGH
- **Dimension**: Parallel Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:146-270`; callers `chunked_processor.py:606-616`, `:844-855`
- **Status**: NEW
- **Description**: With `CHUNK_INTERVAL=10s`/`OVERLAP_DURATION=5s`, any duration in `(n×10, n×10+5)` s allocates an extra trailing chunk that emits 0 samples, and the penultimate chunk (not marked `is_last`) is padded with silence up to the expected 10 s. Monte-Carlo sweep (15–360 s): 48.9% of durations affected. Example: a 21 s track emits 25 s.
- **Evidence**: `expected_samples = int(round(chunk_interval * sample_rate))` (always 10 s) then `padding = np.zeros(...)`, `np.vstack([extracted, padding])`. Simulation: `total=21s → emitted=25s MISMATCH`.
- **Impact**: Up to 5 s of trailing silence appended to streamed output; incorrect displayed duration / seek-to-end; a 0-sample WAV cached to disk per affected track.
- **Suggested Fix**: Add an "effective last" check — if `max(0, total - (chunk_index*interval + overlap)) < interval`, treat the chunk as `is_last` and use the `remaining_duration` formula instead of padding. Related to #3807.

#### AN-01: Rust fingerprint server hardcodes `pitch_stability = 0.5`
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `fingerprint-server/src/analysis/analyzer.rs:512`
- **Status**: NEW
- **Description**: `analyze_harmonic()` assigns `let pitch_stability: f64 = 0.5; // Simplified` unconditionally. The Python fallback computes a real value via YIN. The Rust server handles the vast majority of scans, so this dimension is effectively constant library-wide.
- **Evidence**: `analyzer.rs:512`; Python `harmonic_ops.py:calculate_pitch_stability()` uses Rust YIN.
- **Impact**: `pitch_stability` carries no information for Rust-path tracks; similarity is blind to it; any mastering parameter derived from it applies a constant correction.
- **Suggested Fix**: Implement real pitch stability in the Rust server using the `yin` already exported by `vendor/auralis-dsp/src/`, so both paths converge.

#### AN-02: Rust `silence_ratio` and `rhythm_stability` use algorithmically incompatible formulas vs Python
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `fingerprint-server/src/analysis/analyzer.rs:219-278`
- **Status**: NEW (extends #3690 to two more dimensions)
- **Description**: Rust `silence_ratio` derives from global RMS vs a −60 dB threshold; Python counts per-frame RMS below −40 dB (`librosa.feature.rms()`). Rust `rhythm_stability` is the CV of per-100 ms RMS frames (a *loudness* metric); Python uses `librosa.beat.beat_track()` inter-beat-interval stddev (a *rhythmic* metric).
- **Evidence**: `analyze_temporal()` lines 223–236 (rhythm) and 259–271 (silence) vs `temporal_ops.py:calculate_rhythm_stability()` / `calculate_silence_ratio()`.
- **Impact**: Two more of 25 dimensions carry path-dependent semantics; cross-path similarity scores are degraded; adaptive mastering uses `silence_ratio` for density classification.
- **Suggested Fix**: Port the Python algorithms to Rust (beat tracker + per-frame silence), or exclude these dimensions from similarity distance until converged.

#### AN-03: `MasteringFingerprint.from_audio_file()` decodes the full file (no `duration` cap) — OOM on long files
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/mastering_fingerprint.py:97`, called from `auralis-web/backend/core/chunked_processor.py:701`
- **Status**: NEW
- **Description**: `librosa.load(file_path, sr=sr, mono=False)` with no `duration=`. Reached from `ChunkedAudioProcessor.get_mastering_recommendation()` during normal playback when no recommendation is cached. A 6-hour stereo file ≈ 14 GB. Every other fingerprint path caps at 90 s.
- **Evidence**: `mastering_fingerprint.py:97` (no `duration`); `chunked_processor.py:701` calls it when `self.fingerprint is None`. Contrast `FingerprintService._compute_fingerprint()` passing `duration=90.0`.
- **Impact**: OOM-kill on long files (podcasts, DJ mixes, audiobooks) for an 8 GB desktop on any file > ~30 min; blocks the calling thread during full decode.
- **Suggested Fix**: Add `duration=90.0` to the `librosa.load()` call (sufficient for all 6 features) and to `analyze_album()`.

### MEDIUM

#### SI-01: All 11 mastering stage modules return the caller's array alias on bypass paths
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/stages/safety_limiter.py:29` (+ 17 sibling sites across 10 stage modules)
- **Status**: NEW
- **Description**: Stage `apply()` functions return the raw `audio` parameter (not a copy) on their no-op early-exit paths. Today's callers in `mastering_branches.py` pass an already-copied `processed`, so no mutation occurs — but the signatures advertise an independent result, so any future caller that stores or mutates the return value silently corrupts its own input.
- **Evidence**: `safety_limiter.py:26-29` returns `audio` when `current_peak <= ceiling`. Same pattern: `air_enhancement.py:44,52`, `bass_enhancement.py:76`, `clarity_boost.py:41,59`, `harmonic_exciter.py:58`, `mid_warmth.py:43,51`, `presence_enhancement.py:43,51`, `resonance_notches.py:29`, `stereo_expansion.py:46,52,87`, `sub_bass_control.py:66`, `transient_shaper.py:45,56`.
- **Impact**: Latent aliasing foot-gun; the safety limiter is highest-risk (last stage, alias returned up two frames).
- **Siblings**: All 11 stage modules (above).
- **Suggested Fix**: Return `audio.copy()` on bypass paths, or document + enforce a "returns a new array" contract via a wrapper.

#### SI-02: `HybridProcessor._process_impl` returns the caller's empty array without `.copy()`
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity (also surfaced by DSP Pipeline as DSP-06 — merged)
- **Location**: `auralis/core/hybrid_processor.py:252-253`
- **Status**: NEW
- **Description**: The `len(target_audio) == 0` early return aliases the caller's array, while the silence guard 18 lines later (`:271`) correctly returns `target_audio.copy()`. Inconsistent with the project "always return a copy" invariant and with `BrickWallLimiter.process()`/`DynamicsProcessor.process()`.
- **Evidence**: `:252 return target_audio` vs `:271 return target_audio.copy()`.
- **Impact**: Latent/theoretical (empty array has no samples), but breaks the contract and the consistency with the adjacent branch. Sibling near-miss: `RealtimeDSPPipeline.process_chunk:90` returns the caller's array on exception.
- **Suggested Fix**: Change line 253 to `return target_audio.copy()`.

#### SI-04: `hf_aware_limiter._band_low` returns `sosfiltfilt` output uncast → float32→float64 promotion of all intermediates
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/hf_aware_limiter.py:91-92`, `_band_low:132`
- **Status**: NEW
- **Description**: `_band_low` returns `sosfiltfilt(...)` (always float64) without casting to `audio.dtype`, so `low_band`, `high_band`, `ducked`, `restored` all compute in float64 for float32 input. The final output is cast back (quality unaffected), but working-set memory silently doubles for the limiter's duration — against the pattern used by every other `sosfiltfilt` caller.
- **Evidence**: `_band_low` returns `sosfiltfilt(sos, audio, axis=0)` with no cast; cf. `parallel_eq.py:101,103`, `stereo.py:144-146`, `resonance_notcher.py:205`, `transient_shaper.py:97`, `harmonic_exciter.py:135,147`.
- **Impact**: ~2× transient memory per HF-aware-limiter call (~10→20 MB per 30 s stereo chunk).
- **Suggested Fix**: `return np.asarray(sosfiltfilt(sos, audio, axis=0), dtype=audio.dtype)`.

#### SI-06: WOLA accumulation uses float64 `wola_window` against a float32 buffer in the psychoacoustic-EQ path
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/eq_processor.py:183-212`
- **Status**: NEW
- **Description**: The accumulation buffer is correctly `dtype=audio.dtype`, but `wola_window = np.sqrt(hann(chunk_size))` is float64. `chunk * wola_window` promotes float32 chunks to float64 (so `process_realtime_chunk` receives float64), and the in-place `+=` truncates each float64 contribution back to float32 every overlap-add step (75% overlap → 4× per sample).
- **Evidence**: `:184 wola_window = np.sqrt(hann(chunk_size))` (float64); `:199 chunk = chunk * wola_window[...]`; `:210-212 processed_audio[...] += processed_chunk[...] * wola_window[...]`.
- **Impact**: Slight quantization-noise increase (inaudible in practice) + dtype inconsistency feeding the psychoacoustic EQ's internal arrays.
- **Suggested Fix**: `wola_window = np.sqrt(hann(chunk_size)).astype(audio.dtype, copy=False)`.

#### DSP-02: No inter-stage NaN/Inf guard in `SimpleMasteringPipeline` — one bad stage silently poisons all downstream
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/simple_mastering.py:415-481`; `auralis/core/mastering_branches.py:162-260, 278-353, 374-560`
- **Status**: NEW
- **Description**: Input is validated at entry and output at exit (`sanitize_audio`), but the 8–10 intermediate stages have no inter-stage check. A NaN from any stage propagates silently; the end-only `sanitize_audio` zeroes the output, masking the root-cause stage. `HybridProcessor` and `ChunkedAudioProcessor` validate per stage/chunk.
- **Evidence**: `_process()` validates `processed` then runs 8–10 stages with no checks before `sanitize_audio`. Same in all three branch `apply()` methods.
- **Impact**: A DSP regression yields silent zeroed output with no error; root-cause requires manually bisecting 10 stages.
- **Suggested Fix**: Add `validate_audio_finite(..., repair=False)` spot-checks at branch entry/exit or between stage groups; keep `sanitize_audio` only at the final boundary.

#### DSP-03: `PsychoacousticEQ.analyze_spectrum()` uses an un-windowed FFT → bass spectral leakage biases masking
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:138-148`
- **Status**: NEW
- **Description**: The Hann window was removed (#3663) to match the EQ-*application* path, but the *analysis* path (band energies feeding the masking calculator) has a different correctness requirement. A rectangular window's −13 dB first sidelobe leaks bass energy ±3–4 critical bands.
- **Evidence**: `spectrum = fft(audio_mono[:self.fft_size])` (no window) feeding `_calculate_band_energies` → masking calculator. Called from `process_realtime_chunk()` and `realtime_eq.py:130-138`.
- **Impact**: Systematic over-cut in bass-adjacent bands on bass-heavy material ("thin"/"honky" adaptive correction).
- **Suggested Fix**: Apply a Hann window (with +6.02 dB gain correction) inside `analyze_spectrum()` only, keeping the EQ-application path un-windowed. Analysis and filtering have independent requirements.

#### PS-03: Gapless double-mutation fallback swaps `audio_data` then aborts → audio/queue desync
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:265-285`
- **Status**: NEW
- **Description**: In `advance_with_prebuffer()`, when the first advance fails (queue mutated), the fallback calls `file_manager.load_file(fresh_path)` (swaps `audio_data` atomically) then re-checks `advance_if_next_matches`. If a *second* mutation makes that fail, the method returns False — but `audio_data` is already the new track while `current_index` still points at the old one. The player then reads the new audio from the old position.
- **Evidence**: `:278 load_file(fresh_path)` then `:280` re-check; on failure `:283 return False` with `audio_data` already updated. `AudioPlayer.next_track()` only resets position/plays on a True return.
- **Impact**: Requires two rapid concurrent queue mutations (tens of ms window) — rare in single-user desktop, but yields wrong audio + UI track mismatch until the next advance; reachable in queue-stress tests.
- **Suggested Fix**: Snapshot `old_audio = file_manager.audio_data` under `_audio_lock` before the fallback load and restore it (or reload the prior track) on the abort path.

#### IO-01: AIFF/AU files are scanned into the library but rejected by `unified_loader` → silent fingerprint failure
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/config.py:12-15`, `auralis/io/unified_loader.py:25-34`, `auralis/services/fingerprint_extractor.py:341`
- **Status**: NEW
- **Description**: `scanner/config.py AUDIO_EXTENSIONS` includes `.aiff/.au/.mp4/.m4p/.webm`, so these are ingested and play back via libsndfile in `loader.py`. But `unified_loader.SUPPORTED_FORMATS` lists only 8 extensions; `fingerprint_extractor` calls `unified_loader.load_audio()`, which raises `ERROR_UNSUPPORTED_FORMAT` for AIFF/AU. The fingerprint never generates. Three independent format lists are mutually inconsistent.
- **Evidence**: `unified_loader.py:83-84` gate raises on `.aiff`/`.au`; third list `utils/checker.py:92-94` also diverges (omits `.aac`).
- **Impact**: AIFF/AU tracks play normally but are permanently absent from similarity, recommendations, and adaptive-mastering target selection — silently (no UI warning).
- **Siblings**: `utils/checker.py:92-94`, `processing_api.py:32`.
- **Suggested Fix**: Add `.aiff/.aif/.au` to `SUPPORTED_FORMATS` (soundfile path); route `.mp4/.webm` through `FFMPEG_FORMATS` or drop them from `AUDIO_EXTENSIONS`. Consolidate the three lists into one source of truth.

#### AN-04: `SampledHarmonicAnalyzer` creates a new `ThreadPoolExecutor` per call, shut with `wait=False`
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/batch/harmonic_sampled.py:131-151`
- **Status**: NEW
- **Description**: `_analyze_impl()` builds `ThreadPoolExecutor(max_workers=4)` per call and `shutdown(wait=False, cancel_futures=True)` in `finally`. If `results = [results_map[i] ...]` raises (missing index), up to 4 workers are still running when the executor is released. This partially undoes the executor-reuse fix #3701 for the inner analyzer.
- **Evidence**: `:131` new executor per call; `:149` `KeyError`-prone comprehension; `:151` `wait=False`.
- **Impact**: Up to 32 extra short-lived threads under full scan load; thread leak window on the exception path.
- **Suggested Fix**: Reuse a long-lived executor (as `AudioFingerprintAnalyzer` does), or change `wait=False`→`wait=True` so `finally` always joins.

#### AN-05: `DynamicRangeAnalyzer.crest_history` accumulates across tracks on a shared instance
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/quality/quality_metrics.py:68`, `auralis/analysis/dynamic_range.py:32-33,74`
- **Status**: NEW
- **Description**: `QualityMetrics` holds one `DynamicRangeAnalyzer` (created once), reused across `analyze_content()` calls. `analyze_dynamic_range()` appends to `crest_history` (cap 200) with no reset between tracks; `reset_history()` exists (`:434`) but is never called.
- **Evidence**: `dynamic_range.py:74 self.crest_history.append(...)`; no `reset_history()` call in `quality_metrics.py` / `content_analysis.py`.
- **Impact**: `get_crest_factor_history()` returns crest values spanning multiple tracks; the 200-cap means old-track data displaces current-track data, biasing temporal statistics.
- **Suggested Fix**: Call `self.dynamic_range_analyzer.reset_history()` at the start of `assess_quality()` (and before its invocation in `ContentAnalyzer.analyze_content()`).

#### LIB-02: `POST /api/library/reset` bypasses the repository pattern and leaves two background workers running during bulk deletes
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/routers/library.py:177-211`
- **Status**: NEW
- **Description**: The reset endpoint builds a raw `session = repos.session_factory()` (the only router doing so) and issues bulk `delete(Model)` calls, pausing only `fprint_queue`. `auto_scanner` (`LibraryAutoScanner`) and `ondemand_fingerprint_queue` keep running and can insert rows between `delete(Track)` and `commit()`, making the reset non-atomic. Stale `LibraryManager` query cache (#3770) also survives.
- **Evidence**: only `fprint_queue.stop()/start()` is awaited; `auto_scanner`/`ondemand_fingerprint_queue` are never paused.
- **Impact**: Library can retain rows inserted during the delete window; cache stays stale post-reset.
- **Siblings**: #3812 (lifespan-rollback gap, related but distinct).
- **Suggested Fix**: Pause all three workers before deletes, restart after commit, and invalidate the query cache.

### LOW

#### SI-05: `Result.use_limiter` / `Result.normalize` flags have no consumers — dead API with a false safety contract
- **Severity**: LOW · **Dimension**: Sample Integrity · **Location**: `auralis/io/results.py:70-77` · **Status**: NEW
- A caller using `pcm16(use_limiter=True)` expecting auto-limiting gets none; no write path reads these flags. **Fix**: implement the semantics in `Result.write()` or remove the flags and document that callers must clamp to [-1, 1] (template: `simple_mastering.py:360`).

#### DSP-05: `SimpleMasteringPipeline` chain order is undocumented and diverges from the HybridProcessor canonical order
- **Severity**: LOW · **Dimension**: DSP Pipeline · **Location**: `auralis/core/mastering_branches.py:374-560`, `auralis/core/simple_mastering.py:443-460` · **Status**: NEW
- `QuietBranch` interlaces EQ and dynamics (soft-clip last) with no rationale comment; branches use mirror-opposite gain-staging patterns. Maintenance hazard. **Fix**: add a stage-order + rationale block comment to each `apply()` (docs-only).

#### PS-01: `set_shuffle()` / `set_repeat()` bypass `QueueManager._lock` on write
- **Severity**: LOW · **Dimension**: Player State · **Location**: `auralis/player/queue_controller.py:273-280` · **Status**: NEW
- Direct raw-attribute writes bypass the locked property setters (`:88-92`, `:101-104`), while readers (`peek_next`, `next_track`) read under `_lock`. Benign under GIL, a genuine race under free-threaded 3.13+. **Fix**: assign via the locked properties (one-char change each).

#### PS-02: `load_playlist()` / `set_queue()` write `current_index` directly (bypass `_lock` + TOCTOU)
- **Severity**: LOW · **Dimension**: Player State · **Location**: `auralis/player/queue_controller.py:251-253, 334-336` · **Status**: NEW
- Writes bypass the locked `current_index` setter and use a stale `get_queue()` length snapshot; a concurrent shrink can push the index out of bounds (player ends up stopped with no track). **Fix**: use the locked `current_index` property.

#### PS-04: `get_playback_info()` reads `current_track` outside `_position_lock` (partial regression of the #3786 fix)
- **Severity**: LOW · **Dimension**: Player State · **Location**: `auralis/player/integration_manager.py:277` · **Status**: NEW
- The write side is locked (#3786), but the polling read pairs new-track position with old-track metadata for one WebSocket cycle. **Fix**: read `current_track` inside the `_position_lock` block.

#### IO-02: `_get_wav_declared_size` misreads the legacy RF64 `0xFFFFFFFF` sentinel → valid WAV rejected as "truncated"
- **Severity**: LOW · **Dimension**: Audio I/O · **Location**: `auralis/io/loaders/soundfile_loader.py:20-35, 46-58` · **Status**: NEW
- A RIFF WAV using the old RF64 overflow marker reports ~4 GB declared size; files < ~400 MB hit `ERROR_TRUNCATED_FILE`. **Fix**: `if chunk_size == 0xFFFFFFFF: return None`.

#### IO-03: `loader.py` bare `except Exception` re-wraps `ModuleError` into `RuntimeError` (unfixed sibling of #3695)
- **Severity**: LOW · **Dimension**: Audio I/O · **Location**: `auralis/io/loader.py:112-113` · **Status**: NEW
- Erases structured diagnostic codes (`ERROR_TRUNCATED_FILE`, `ERROR_FFMPEG_TIMEOUT`, …) on the player load path. **Fix**: add `except ModuleError: raise` before the generic handler (mirror `ffmpeg_loader.py:204-209`).

#### IO-04: `check_ffmpeg()` uncached — one `ffmpeg -version` subprocess per file load
- **Severity**: LOW · **Dimension**: Audio I/O · **Location**: `auralis/io/loaders/ffmpeg_loader.py:22-32, 97` · **Status**: NEW
- A 1,000-file scan forks 1,000 probe processes. **Fix**: `@functools.lru_cache` or a module-level `_FFMPEG_AVAILABLE` sentinel.

#### IO-05: `_probe_audio` omits `FileNotFoundError` → misleading error when `ffprobe` is absent
- **Severity**: LOW · **Dimension**: Audio I/O · **Location**: `auralis/io/loaders/ffmpeg_loader.py:44-90, 87` · **Status**: NEW
- Missing `ffprobe` surfaces as `ERROR_FFMPEG_CONVERSION` instead of `ERROR_FFMPEG_NOT_FOUND`. **Fix**: catch `FileNotFoundError`; add a `check_ffprobe()` guard.

#### IO-06: OGG `COVERART` tag returned as a base64 string, not decoded bytes → silent artwork failure
- **Severity**: LOW · **Dimension**: Audio I/O · **Location**: `auralis/library/artwork.py:214-226` · **Status**: NEW
- `f.write(str)` in binary mode raises `TypeError`, caught silently; no art for files using the deprecated `COVERART`/`COVER` tags. **Fix**: `base64.b64decode(tags[key][0])` and return bytes.

#### AN-07: `MasteringFingerprint.from_audio_file()` uses `print()` instead of the logger
- **Severity**: LOW · **Dimension**: Analysis · **Location**: `auralis/analysis/mastering_fingerprint.py:134` · **Status**: NEW
- Errors bypass structured logging and are invisible headless. **Fix**: module-level `logger` + `logger.error(...)`.

#### AN-08: Rust server LUFS is a non-gated RMS approximation diverging from the BS.1770-4 `LoudnessMeter`
- **Severity**: LOW · **Dimension**: Analysis · **Location**: `fingerprint-server/src/analysis/analyzer.rs:169-216` · **Status**: NEW
- `lufs = -0.691 + 10·log10(RMS)` — no K-weighting/gating/true-peak; diverges 3–8 LU from the Python path on dynamic content. Fourth Rust/Python dimension divergence (with AN-01, AN-02, #3690). **Fix**: port K-weighting + two-stage gating to Rust (see also #4022, #4020 duplication).

#### LIB-01: `FingerprintStatsRepository.update_status()` still uses raw `text()` UPDATE (incomplete #3711 migration)
- **Severity**: LOW · **Dimension**: Library & Database · **Location**: `auralis/library/repositories/fingerprint_stats_repository.py:44-60` · **Status**: NEW
- The hot-path worker update uses raw SQL while `cleanup_incomplete_fingerprints` was migrated to ORM. No injection risk; would break silently on a future table rename. **Siblings**: `fingerprint_scheduler_repository.py:138,160`. **Fix**: use `update(TrackFingerprint).where(...).values(...)`.

#### LIB-03: `FingerprintNormalizer.fit()` materializes the entire `track_fingerprints` table in RAM
- **Severity**: LOW · **Dimension**: Library & Database · **Location**: `auralis/analysis/fingerprint/normalizer.py:130` · **Status**: NEW
- `get_all()` (limit=None) + a full numpy array; ~100–200 MB spike on 50k-track libraries, doubled if `/api/similarity/fit` is called concurrently. **Fix**: project only the 25 numeric columns, or use Welford's online stats with a `batch_size`.

### Existing / Already-Tracked (verified, not re-filed)

- **DSP-04 / AN-... — `resonance_notcher.py:86` hard-codes `N=16384` FFT** — **Existing: #4030**.
- **AN-06 — `content_analyzer.py:375` hard-codes `window_size=44100`** — **Existing: #4029**.

---

## Relationships & Shared Root Causes

- **Rust/Python fingerprint divergence (AN-01, AN-02, AN-08 + existing #3690).** Single root cause: the Rust fingerprint server reimplements analysis with simplified formulas rather than calling the shared `vendor/auralis-dsp` DSP that the Python path uses. 4 of 25 dimensions are unreliable on the default path. Fix them together by converging both paths on the Rust DSP library; #4022/#4020 note duplicate LUFS/metric implementations to consolidate.
- **dtype float32→float64 promotion (SI-04, SI-06, PP-03).** Same pattern — a `sosfiltfilt`/`hann` result used without `.astype(audio.dtype)`. PP-03 is literally the un-fixed sibling of #3760's fix. One sweep across all filter call sites resolves all three.
- **Copy-before-modify aliasing (SI-01, SI-02/DSP-06).** Same invariant gap on no-op/early-exit return paths. Low real risk today; a consistent "stages return a new array" contract closes the class.
- **Phase-1 chunked-processor refactor regressions (PP-01, PP-02).** Both stem from the recent decomposition: PP-01 left two lock domains for one shared processor (and orphaned the #3808 fix as dead code); PP-02 is an `is_last` detection gap in the new chunk-operations module. Re-audit the refactor's lock/boundary invariants.
- **Silence/NaN edge cases (SI-03, DSP-02).** SI-03 produces the NaN; DSP-02 is the missing inter-stage guard that would localize it. Fixing SI-03 removes the specific crash; DSP-02 hardens the pipeline against the next one.
- **QueueManager lock-bypass (PS-01, PS-02).** Same root cause: write paths bypass the locked properties introduced by #3783. Both are one-line fixes routing through the existing setters.
- **Inconsistent error-context erasure (IO-03 ↔ #3695, LIB-01 ↔ #3711).** A fix applied to one sibling but not the other in the same file/module. Pattern: when fixing an error-handling or ORM-migration bug, grep all siblings.

---

## Prioritized Fix Order

1. **AN-03 (HIGH) — add `duration=90.0` cap to `MasteringFingerprint.from_audio_file()`.** One-line change; removes a real OOM-kill reachable from normal playback on long files. Highest impact-to-effort.
2. **SI-03 (HIGH) — second finite guard after the RMS fallback in `continuous_mode`.** One-line change; eliminates a stream-crashing NaN path on silent audio.
3. **PP-01 (HIGH) — unify the lock in `get_wav_chunk_path`; delete dead `_process_chunk_with_hybrid_processor`.** Restores the #3808 guarantee; prevents DSP-state corruption across concurrent streams.
4. **PP-02 (HIGH) — fix `is_last`/`extract_chunk_segment` so the penultimate chunk isn't silence-padded.** Affects ~49% of tracks; restores the sample-count invariant.
5. **DSP-01 (HIGH) — `sosfilt`→`sosfiltfilt` in `sub_bass_control`.** Removes audible bass-transient smear; matches every sibling stage.
6. **AN-01 + AN-02 (HIGH ×2) — converge Rust fingerprint dimensions on real algorithms.** Larger effort (Rust); fixes the dominant fingerprint-quality theme. Batch with AN-08 (LOW) and #3690.
7. **MEDIUM cluster — quick wins first:** SI-02 (one-line copy), AN-05 (`reset_history()` call), DSP-02 (inter-stage guards), IO-01 (consolidate format lists), AN-04 (executor reuse / `wait=True`), LIB-02 (pause all workers on reset), SI-04/SI-06 (dtype casts — batch with PP-03), PS-03 (gapless restore), DSP-03 (analysis-path window).
8. **LOW cluster — batch by theme:** dtype casts (PP-03 with SI-04/SI-06); QueueManager lock-bypass (PS-01, PS-02, PS-04); I/O robustness (IO-02–IO-06); ORM/logging hygiene (LIB-01, AN-07); resource bounds (LIB-03); dead-API cleanup (SI-05); docs (DSP-05).

---

## Confirmed-Clean / Verified-Fixed (highlights)

Sample-count assertions after the brick-wall limiter; NaN/Inf validation at pipeline entry/exit and per chunk; all-zeros guard in `_process_impl`; double-windowing removed (#3663) with no double-window; sub-bass parallel path zero-phase (#8bc5b217/#3469-3470); HPSS OLA normalization (#3662); Hermitian symmetry in FFT EQ; Rust GIL release + `catch_unwind` on all 11 PyO3 wrappers; per-call (non-shared) Rust `MultiBandEQ`; psychoacoustic-EQ / dynamics / adaptive-EQ state locks (#3747/#3788/#3789); brick-wall lookahead clamp (#3750); prior IO fixes ENG-NEW-70/71/72/74; surround downmix (loader + soundfile); repository pattern across 15 repos; `check_same_thread=False` + `pool_pre_ping=True`; `selectinload()`/`joinedload()` everywhere; scanner symlink-cycle/permission/Unicode handling; migration fcntl/msvcrt locking + double-check; `cleanup_missing_files` cursor batching + TOCTOU re-verify (#3310); engine disposal on shutdown (#2066/#3769); `.25d` cache-miss fix; ML genre classifier `@lru_cache`; streaming smoothing-buffer race fix.
