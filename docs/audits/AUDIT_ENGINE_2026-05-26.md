# Engine Audit — 2026-05-26

**Scope**: `auralis/` core audio engine — DSP pipeline, player, audio I/O, parallel processing, analysis, library/database, Rust DSP boundary.
**Depth**: deep (full call-graph tracing).
**Methodology**: 7 dimension agents running in parallel, each verifying findings against the current code and deduplicating against `gh issue list --state all --limit 300` and prior `docs/audits/AUDIT_ENGINE_*.md` reports (latest 2026-05-20).

Prior open issues confirmed still open (NOT re-reported here): `#3458` (stats sum without WHERE — re-noted as ENG-NEW-115), `#3477` (BatchAnalyzer KeyboardInterrupt-only try/except), `#3478` (ResonanceNotcher `find_peaks(distance=10)`), `#3438` (fingerprint daemon threads), `#3446` (executor not shut down), `#3459` (fingerprint upsert race — code-level fix verified present), `#3479` (auto-refresh reference cloud).

Prior fixes confirmed in place (regression checks passed): SI-01 #3468 (stereo widening dtype), IO-01 #3465, IO-02 #3471, IO-03 #3472, #3482 (np.hanning regression), DSP-01/02 #3469/#3470 (TransientShaper / HarmonicExciter sosfiltfilt), #3437, #3428, #3426, #3463 (PLR-01), #3474 (PLR-03), #3434, #3354, #3510 (WebM encoder CancelledError), #3441, #3440, #3373, #3355 (band processor copy), #3430 (band fallback), #3444, #3475, #3467, `#bd94fd59` (cleanup_missing_files OOM), `#8adb8d0a` (engine disposal).

---

## Executive Summary

| Severity | Count |
|----------|------:|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 26 |
| LOW | 27 |
| **Total NEW findings** | **56** |

**One prior-open re-reference** (`ENG-NEW-115 → #3458`) noted in passing; not re-published as a new issue.

### Themes

1. **Float64 dtype creep in DSP hot path**: 8 findings (`ENG-NEW-22/23/24/26/29` and supporting siblings) share the same root cause — `np.zeros()` / `np.empty()` allocated without `dtype=` argument silently promotes float32 audio to float64. `filters.py:39` has the correct pattern; the rest of the DSP modules missed it. `BrickWallLimiter` is the worst offender — runs at the end of every `HybridProcessor` mode.

2. **Causal `sosfilt` in parallel-add chains**: 4 findings (`ENG-NEW-40/45/47` + the closed DSP-01/02 set) all do `band = sosfilt(audio); result = audio + band * gain` which produces a comb-filter artefact because the dry signal is zero-delay while the band is group-delayed. `ParallelEQUtilities` (`ENG-NEW-47`) is the widest — touches all 6 tonal stages of `SimpleMasteringPipeline`.

3. **Player lock ordering**: `ENG-NEW-55` holds `_audio_lock` during file I/O on first track add, starving audio chunk reads. The same path creates the lock-inversion deadlock surface in `ENG-NEW-63`. The race fix is one structural change in `add_to_queue` and resolves both.

4. **Fingerprint determinism**: `ENG-NEW-95` (HIGH) — the Python fallback in `FingerprintExtractor` skips the 22 050 Hz resample that `FingerprintService` always applies. Same file → different 25D fingerprints depending on code path. Breaks similarity search and adaptive-mastering target lookup.

5. **Auto makeup gain over-compensation**: `ENG-NEW-41` (HIGH) — the formula uses worst-case gain reduction (at 0 dBFS) as makeup gain, applying 6-13 dB excess on realistic content. Streaming path feeds an already-compressed signal +8 dB hot into the brick-wall limiter, defeating the compressor's dynamic intent.

6. **Unbounded queries in the library layer**: `ENG-NEW-110/112` use `get_all()` with no limit; `ENG-NEW-117` is the root cause (`if limit:` truthiness guard). A 50 000-track library produces a multi-hundred-MB allocation burst on `refresh_cloud`.

7. **Test coverage gaps**: `ENG-NEW-73` — every FFmpeg-routed audio format (MP3, AAC, OGG, OPUS, M4A) has zero real-decode test coverage. Format-detection tests only.

### Most impactful surgical fixes

1. `ENG-NEW-22` — Add `dtype=audio.dtype` to `BrickWallLimiter` allocations. Fixes the dominant float64 leak.
2. `ENG-NEW-25` — Add `np.clip(write_region, -1.0, 1.0)` before `output_file.write()` in `simple_mastering.py`. One line; defends every chunk-mode export.
3. `ENG-NEW-41` — Change `auto_makeup_gain = abs(threshold) * (1 - 1/ratio)` to `max(0, (rms - threshold) * (1 - 1/ratio))`. Stops the realtime pipeline from saturating the limiter.
4. `ENG-NEW-47` — `sosfilt → sosfiltfilt` in `ParallelEQUtilities`. Same template as #3469/#3470. Affects all 6 tonal stages.
5. `ENG-NEW-55` — Restructure `add_to_queue` to drop `_audio_lock` before the file load. Fixes the dropout AND resolves `ENG-NEW-63` inversion.
6. `ENG-NEW-58` — Move `_stop_requested.clear()` to after `playback.play()` succeeds. One line; restores auto-advance after a stop/play race.
7. `ENG-NEW-71` — Change `'-ac', str(source_channels)` to `'-ac', '2'` in the ffmpeg command. Restores vocal/center content on 5.1 audio.
8. `ENG-NEW-95` — Add the 22 050 Hz resample to `FingerprintExtractor.extract_and_store()` Python fallback (or push it into `AudioFingerprintAnalyzer.analyze()` itself).
9. `ENG-NEW-117` — Change `if limit:` to `if limit is not None:` in `fingerprint_repository.get_all`. Root-cause fix for `ENG-NEW-110/112`.

---

## Per-Dimension Index

| Dimension | NEW Findings | HIGH | MEDIUM | LOW |
|-----------|:-:|:-:|:-:|:-:|
| 1. Sample Integrity | 8 | 0 | 3 | 5 |
| 2. DSP Pipeline | 9 | 1 | 6 | 2 |
| 3. Player State | 9 | 1 | 4 | 4 |
| 4. Audio I/O | 5 | 0 | 2 | 3 |
| 5. Parallel Processing | 6 | 0 | 3 | 3 |
| 6. Analysis | 10 | 1 | 4 | 5 |
| 7. Library & Database | 11 (1 existing) | 0 | 4 | 6 |
| **Total** | **58 (56 new + 2 existing/duplicate)** | **3** | **26** | **27** |

---

## HIGH-severity findings (3)

### ENG-NEW-41: `DynamicsProcessor` auto makeup gain formula overcompensates by 6–13 dB in streaming path
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/advanced_dynamics.py:243-244`; call chain `RealtimeDSPPipeline.process_chunk` → `DynamicsProcessor.process` → `_adapt_to_content`
- **Status**: NEW
- **Description**: `auto_makeup_gain = abs(new_threshold) * (1 - 1/new_ratio)` computes the *maximum possible* gain reduction (at 0 dBFS). For real audio at −10 to −6 dBFS peak the actual reduction is `(|peak| − |threshold|) * (1 − 1/ratio)`, 6-9 dB less than the formula produces. For threshold=−18 dB, ratio=4:1 the formula gives **13.5 dB**; actual need is ~5 dB. The compressor exits 8 dB hot; the downstream `BrickWallLimiter` then fires on every chunk, defeating the compressor's dynamic intent. Runs in `RealtimeDSPPipeline` on every streaming chunk.
- **Suggested Fix**: `auto_makeup_gain = max(0, (rms_level - threshold) * (1 - 1/ratio))` with current measured RMS, OR the standard approximation `-threshold / ratio` which gives 4-5 dB for typical settings. Cap at 12 dB regardless.

### ENG-NEW-55: `add_to_queue` holds `_audio_lock` during blocking file I/O — hard audio dropout on first track add
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:383-391` (and `audio_file_manager.py:60`)
- **Status**: NEW
- **Description**: The fix for #3359 wrapped `is_loaded()` + auto-load inside `with file_manager._audio_lock`. But `AudioFileManager.load_file()` performs its blocking disk I/O (`load(file_path, "target")`) BEFORE acquiring its own inner `_audio_lock`. Because the outer RLock is held for the entire load duration (hundreds of ms for large FLAC/WAV), `get_audio_chunk()` — which acquires the same `_audio_lock` — blocks for that whole duration. Result: audible audio dropout whenever a track is first added to an empty queue.
- **Impact**: Hard dropout on first track add. Pairs with `ENG-NEW-63` (lock inversion) — fixing this also resolves that deadlock surface.
- **Suggested Fix**: Acquire `_audio_lock` only for the `is_loaded()` check, release, then call `load_file()` without holding it. Use a `loading_in_progress` boolean flag for the TOCTOU window.

### ENG-NEW-95: Fingerprint non-determinism — Python fallback uses native sample rate; service path always resamples to 22 050 Hz
- **Dimension**: Analysis
- **Location**: `auralis/services/fingerprint_extractor.py:341-351` vs `auralis/analysis/fingerprint/fingerprint_service.py:202-224`
- **Status**: NEW
- **Description**: `FingerprintService._compute_fingerprint()` always resamples to 22 050 Hz before calling `AudioFingerprintAnalyzer.analyze()`. The Python fallback in `FingerprintExtractor.extract_and_store()` calls `load_audio(filepath)` at native sample rate (44 100 / 48 000 Hz) and passes the array directly. Because `AudioFingerprintAnalyzer` passes `sr` to librosa (`beat_track`, `onset_strength`, `spectral_centroid`), FFT sizes, bin widths, and hop-length-to-time mappings all differ. Normalization constants (8 000 Hz for centroid, 10 000 Hz for rolloff) are fixed, so the same file produces measurably different 25D fingerprints depending on which path computed it.
- **Impact**: Fingerprints from the background scanner and the player path are not comparable. Similarity search returns wrong neighbours; adaptive mastering picks the wrong target.
- **Suggested Fix**: Push the 22 050 Hz resample into `AudioFingerprintAnalyzer.analyze()` so no caller can bypass it. Alternatively duplicate the normalization block from `fingerprint_service.py:207-221` into `fingerprint_extractor.py:341`.

---

## MEDIUM-severity findings (26)

### Dimension 1 — Sample Integrity (3)

#### ENG-NEW-22: `BrickWallLimiter` allocations promote float32 audio to float64
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:109-162`
- `np.zeros((lookahead_samples, num_channels))` and `np.empty(num_samples)` default to float64. After `vstack`, `per_sample_max`, `target_gains`, and `gain_curve` are all float64; `audio * gain_curve.reshape(-1, 1)` produces float64 output. Runs at the end of every `HybridProcessor` adaptive/hybrid/reference mode.
- **Fix**: `np.zeros(..., dtype=audio.dtype)`, `np.empty(num_samples, dtype=np.float32 if audio.dtype == np.float32 else np.float64)`.

#### ENG-NEW-23: `VectorizedEQProcessor` / `ParallelEQProcessor` short-chunk padding promotes float32 → float64
- **Location**: `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:50-56`, `parallel_processor.py:54-60`
- `np.zeros((fft_size, ...))` without `dtype=` promotes audio. `filters.py:39` has the correct pattern. Hits every real-time chunk shorter than `fft_size` (2048 default).
- **Fix**: `np.zeros((fft_size, ...), dtype=audio_chunk.dtype)`.

#### ENG-NEW-25: `simple_mastering.py` writes PCM_24 without `np.clip` — bypasses #3471 fix
- **Location**: `auralis/core/simple_mastering.py:299-301`
- `SimpleMasteringPipeline.master_file()` constructs its own `sf.SoundFile` writer and bypasses `saver.py` (which got the clip fix in #3471). Constructive interference at chunk boundaries can write samples outside [-1.0, 1.0].
- **Fix**: `write_region = np.clip(write_region, -1.0, 1.0)` before the write at line 301.

### Dimension 2 — DSP Pipeline (6)

#### ENG-NEW-40: Causal `sosfilt` in `_apply_spectral_tilt_correction` — comb artefact near 250 Hz when dynamics guard fires
- **Location**: `auralis/core/processing/continuous_mode.py:62-79`
- `low = sosfilt(...)` is delayed; `high = audio - low` is instantaneous. Recombination produces a comb at the crossover. Same template as DSP-01/02.
- **Fix**: `sosfilt → sosfiltfilt`.

#### ENG-NEW-42: HPSS ISTFT missing OLA normalization — output ~1.5× too loud
- **Location**: `vendor/auralis-dsp/src/hpss.rs:258-303`
- 75% Hann overlap with second Hann window at synthesis: OLA sum converges to ~1.499, but only `n_fft` normalization is applied. `harmonic + percussive ≈ 1.499 × original`. Fingerprint path doesn't use HPSS, but the exported `auralis_dsp.hpss()` API is silently wrong.
- **Fix**: Divide each output sample by the pre-computed OLA normalization constant (~1.5 for constant Hann at 75% overlap).

#### ENG-NEW-43: `PsychoacousticEQ` analysis window mismatch — gains derived from Hann-windowed spectrum, applied to un-windowed
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:126-133`, `auralis/dsp/eq/filters.py:84-85`
- Analysis windows the first `fft_size` samples; application explicitly does not window (comment: "no windowing for EQ"). Gains over-boost the edges of the frame. Also: `hop_size` is computed (line 67) but never used — the documented 75% overlap is never applied.
- **Fix**: Drop the Hann window from `analyze_spectrum` for the EQ-driven path, OR implement the WOLA loop that the dead `hop_size` was intended for.

#### ENG-NEW-45: HF-aware limiter causal `sosfilt` corrupts complementary split
- **Location**: `auralis/core/processing/hf_aware_limiter.py:87-101, 122-124`
- "Perfect reconstruction" docstring is misleading: `low + high == audio` algebraically, but `high = audio - delayed_low` is not a true HF band — contains phase artefacts at the 6 kHz crossover.
- **Fix**: `sosfilt → sosfiltfilt` in `_band_low`.

#### ENG-NEW-46: RMS ≈ LUFS conflation in `_apply_final_normalization` — ±3-6 dB systematic error
- **Location**: `auralis/core/processing/continuous_mode.py:654-672`
- `target_rms_db = params.target_lufs` treats unweighted RMS as equivalent to K-weighted gated LUFS. Bass-heavy material is under-normalized; bright material is over-normalized. Downstream limiter compensates.
- **Fix**: Use `calculate_loudness_units(...)` (already imported at line 338) for the normalization target.

#### ENG-NEW-47: `ParallelEQUtilities` uses causal `sosfilt` — comb artefact at every shelf/bandpass in `SimpleMasteringPipeline`
- **Location**: `auralis/core/dsp/parallel_eq.py:96-99, 167-169, 244-246`
- All three methods (`apply_low_shelf_boost`, `apply_high_shelf_boost`, `apply_bandpass_boost`) do `band = sosfilt(audio); return audio + band * (boost - 1)`. Affects every tonal stage: bass, sub-bass, mid warmth, presence, clarity, air. Docstring claims "phase-linear" — incorrect.
- **Fix**: `sosfilt → sosfiltfilt` in all three methods + `astype(audio.dtype)`. Same template as #3469/#3470.

### Dimension 3 — Player State (4)

#### ENG-NEW-56: `load_file` audio-data swap and position reset not atomic
- **Location**: `auralis/player/enhanced_audio_player.py:185-186`, `audio_file_manager.py:60-64`
- `file_manager.load_file(fp)` swaps audio_data; `playback.load_and_stop()` resets position separately. Between them, `get_audio_chunk()` can serve a chunk of the new track at the old position.
- **Fix**: Single atomic critical section that swaps audio + resets position together.

#### ENG-NEW-57: `previous_track()` rollback reads/writes `current_index` without `QueueManager._lock`
- **Location**: `auralis/player/enhanced_audio_player.py:362, 373`
- Concurrent `next_track()` / `remove_track()` clobbered by the bare-attribute rollback write. Stale rollback corrupts the queue index.
- **Fix**: Add `rollback_index(saved_index)` method to `QueueController` that takes `_lock`.

#### ENG-NEW-58: `play()` race — `_stop_requested.clear()` before `playback.play()` silences auto-advance for the session
- **Location**: `auralis/player/enhanced_audio_player.py:126-130`
- Sequence: `play()` clears flag → `stop()` sets flag → `play()` proceeds. Result: `_stop_requested` set with state=PLAYING. Auto-advance permanently suppressed; user has to stop+play again to fix.
- **Fix**: Move `_stop_requested.clear()` to after `playback.play()` succeeds.

#### ENG-NEW-63: Lock inversion — `_audio_lock` → `_position_lock` vs `_position_lock` → `_audio_lock`
- **Location**: `enhanced_audio_player.py:383`, `integration_manager.py:149,254`
- Path A: `add_to_queue` holds `_audio_lock` while invoking external callbacks that call `get_playback_info()` (needs `_position_lock`). Path B: state-change handler holds `_position_lock` while calling `get_duration()` (needs `_audio_lock`). Both threads deadlock.
- **Fix**: Resolved as a side effect of `ENG-NEW-55` (drop `_audio_lock` before the I/O).

### Dimension 4 — Audio I/O (2)

#### ENG-NEW-70: `unified_loader.load_audio()` has no duration guard for FFmpeg-routed formats
- **Location**: `auralis/io/unified_loader.py:89-90`; compare `auralis/io/loader.py:51-57`
- A 90-minute stereo MP3 produces ~900 MB temp WAV (tmpfs = RAM) then 1.8 GB float32 array = ~2.7 GB peak. `reference_analyzer.py`, `fingerprint_extractor.py` Python fallback, and any direct caller hit this.
- **Fix**: Add `MAX_DURATION_SECONDS = 7200` guard (matching `loader.py`) inside `load_with_ffmpeg` post-probe (early bail) AND post-load in `unified_loader.load_audio()`.

#### ENG-NEW-71: FFmpeg preserves source channels — vocal/center channel silently lost on 5.1 content
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:141-142`; `soundfile_loader.py:70-74`
- `-ac {source_channels}` writes all 6 channels; `soundfile_loader` then truncates to `[:, :2]` (L, R) — center channel (vocals) discarded entirely. Should use `-ac 2` to invoke FFmpeg's downmix matrix.
- **Fix**: Change `'-ac', str(source_channels)` to `'-ac', '2'`. Multi-channel truncation branch in `soundfile_loader` becomes dead code.

### Dimension 5 — Parallel Processing (3)

#### ENG-NEW-85: `ParallelFeatureExtractor` passes shared array reference to all thread workers — no `.copy()`
- **Location**: `auralis/optimization/parallel_processor.py:415-419`
- Same one-line bug pattern as #3355 (band processor); the feature extractor in the same file was not updated.
- **Fix**: `executor.submit(extractor, audio.copy())`.

#### ENG-NEW-86: `ParallelFeatureExtractor.extract_features_parallel` no exception handling on `future.result()`
- **Location**: `auralis/optimization/parallel_processor.py:424-426`
- Single failing extractor aborts the entire fingerprint computation. `ParallelBandProcessor` already has the correct `try/except` pattern (lines 280-285).
- **Fix**: Wrap `future.result()` in `try/except Exception`, log a warning, fall back to None.

#### ENG-NEW-87: Band-fallback path applies filter without gain — wrong level on partial failure (3 paths)
- **Location**: `auralis/optimization/parallel_processor.py:255, 270, 345`
- ProcessPool, ThreadPool, and group fallback all do `band_filters[i](audio)` without `* (10 ** (gain / 20))`. EQ cuts become pass-throughs; EQ boosts become neutral. Comment says "unprocessed signal" but it's actually "filtered without gain".
- **Fix**: Apply gain in all three fallback sites.

### Dimension 6 — Analysis (4)

#### ENG-NEW-96: `StreamingFingerprint` is dead code — exports zero call sites
- **Location**: `auralis/analysis/fingerprint/analyzers/streaming/fingerprint.py:39`
- 5 modules / ~500 lines with no imports outside their own tree. Streaming path only produces 13 of the 25 dimensions; wiring it in would silently degrade similarity search.
- **Fix**: Delete or complete the streaming path. Document decision in `fingerprint/__init__.py`.

#### ENG-NEW-97: LUFS trailing-block skip — sub-400 ms tail always excluded from integrated loudness
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:338-342`, `quality_metrics.py:105-109`
- `if len(chunk) >= block_size:` guards both feeds, so up to 399 ms (typically fade-out / quiet) is always discarded. Biases integrated LUFS upward by ~0.1-0.3 LU systematically.
- **Fix**: Remove the guard; `LoudnessMeter.measure_chunk()` already handles short blocks.

#### ENG-NEW-98: THD estimation collapses harmonics to Nyquist bin for high-frequency fundamentals
- **Location**: `auralis/analysis/quality_assessors/utilities/estimation_ops.py:54-66`
- For fundamentals in the upper half of the spectrum, all 4 harmonic indices clamp to `N-1` (Nyquist) — `harmonic_power = 4 * magnitude[Nyquist]^2`, meaningless for bright content (cymbals, distorted guitar). `DistortionAssessor` weights THD at 40%.
- **Fix**: Skip harmonics that fall outside the valid spectrum; only use harmonics within `[10, N//2]`.

#### ENG-NEW-99: `.25d` cache key reads only first 1 MB — silent stale cache for end-of-file edits
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:55-65`
- VORBIS_COMMENT, ID3v1, embedded artwork all live near or past 1 MB into the file. Re-tag doesn't change the cache key; old fingerprint served indefinitely.
- **Fix**: Use `st_mtime + st_size` from `os.stat()` instead of reading file bytes. O(1) I/O; catches any modification.

### Dimension 7 — Library & Database (4)

#### ENG-NEW-110: `refresh_cloud` loads entire fingerprint table into RAM without limit
- **Location**: `auralis/learning/reference_seeder.py:163`, `fingerprint_repository.py:238-261`
- 50 000-track library = 50 000 ORM-wrapped `TrackFingerprint` instantiated simultaneously, plus NumPy aggregation array. Peak RSS > 1 GB possible.
- **Fix**: Paginate via cursor-style batching like `cleanup_missing_files`, OR pass `limit=config.max_candidates`. Root cause is `ENG-NEW-117`.

#### ENG-NEW-111: `set_reference_flags` N+1 — one SELECT per track on cloud rebuild
- **Location**: `auralis/library/repositories/fingerprint_repository.py:312-319`
- 2 000-track cloud = 2 000 SQLite round-trips before COMMIT. `clear_all_reference_flags` already uses a single bulk UPDATE; the asymmetry is the bug.
- **Fix**: Single `update(TrackFingerprint).where(track_id.in_(ids)).values(is_reference=True)` for flagged, second for cleared.

#### ENG-NEW-114: `normalize_existing_artists` standalone migration bypasses `migration_lock`
- **Location**: `auralis/library/migrations/normalize_existing_artists.py:54-56`
- Own `create_engine()` with no `pool_pre_ping`, no `check_same_thread`, no `migration_lock()`. Concurrent execution with `check_and_migrate_database` can produce partial schema writes or duplicate `schema_version` rows.
- **Fix**: Wrap body in `migration_lock(str(db_path))`.

#### ENG-NEW-117: `fingerprint_repository.get_all(limit=None)` silently disables pagination — root cause of 110/112
- **Location**: `auralis/library/repositories/fingerprint_repository.py:251-256`
- `if limit:` truthiness — `None` is falsy, so the documented default returns unbounded.
- **Fix**: `if limit is not None:` and document that callers requiring all rows must pass an explicit sentinel.

---

## LOW-severity findings (27)

### Dimension 1 — Sample Integrity (5)
- **ENG-NEW-24** — `simple_mastering.py` crossfade ramps are float64; promotes `write_region` to float64 (`:271-281`).
- **ENG-NEW-26** — `ParallelEQProcessor._apply_eq_mono_*` no dtype cast on FFT output (`parallel_processor.py:136-137, 182-183`).
- **ENG-NEW-27** — `RealtimeAdaptiveEQ._handle_variable_chunk_size` no shape assertion after `_process_fixed_chunk` (`:146-149`).
- **ENG-NEW-28** — `normalize()` relies implicitly on NEP-50 for float32 preservation (`basic.py:34-48`).
- **ENG-NEW-29** — `AdaptiveLimiter._compute_peak_envelope` uses `np.zeros(lookahead)` (float64); currently masked by `VectorizedEnvelopeFollower` hard-coding float32 (`limiter.py:154`).

### Dimension 2 — DSP Pipeline (2)
- **ENG-NEW-44** — `RealtimeAdaptiveEQ.input_buffer` `maxlen=10` silently drops oldest chunk; no warning logged (`realtime_eq.py:48, 126-127`).
- **ENG-NEW-48** — `chroma_energy` in Rust fingerprint is normalized RMS, not chroma — duplicates LUFS dimension, reduces effective fingerprint dimensionality (`fingerprint_compute.rs:552-560`).

### Dimension 3 — Player State (4)
- **ENG-NEW-59** — `get_playback_info` reads `playback.state.value` without `PlaybackController._lock`; can return `state="paused"` + `is_playing=true` (`integration_manager.py:256, 260`).
- **ENG-NEW-60** — End-of-queue spin: auto-advance thread spawned ~21 Hz when last track is still in queue (`enhanced_audio_player.py:454-463`).
- **ENG-NEW-61** — `LOADING` state is dead code; `set_loading()` has zero call sites (`playback_controller.py:189-199`).
- **ENG-NEW-62** — `cleanup()` does not join auto-advance daemon thread; post-cleanup audio swap race in long-running test scenarios (`enhanced_audio_player.py:638-644`).

### Dimension 4 — Audio I/O (3)
- **ENG-NEW-72** — `except Exception` re-wraps `ModuleError` losing diagnostic code; truncated-file errors surface as `ERROR_FFMPEG_CONVERSION` (`ffmpeg_loader.py:183-184`).
- **ENG-NEW-73** — No real-decode integration tests for any FFmpeg-routed format (MP3, AAC, OGG, OPUS, M4A); format-detection only (`tests/test_unified_loader.py`).
- **ENG-NEW-74** — `_probe_audio` `except (..., Exception)` swallows programming errors as `Code.ERROR_CORRUPTED` (`ffmpeg_loader.py:84-86`).

### Dimension 5 — Parallel Processing (3)
- **ENG-NEW-88** — `ParallelConfig.adaptive_workers` declared but never read; pool never self-sizes (`parallel_processor.py:34`).
- **ENG-NEW-89** — `ProcessPoolExecutor` path pickles non-picklable `band_filter` callables (closures, lambdas); silent fallback to ENG-NEW-87 bug. Not reached in production (`use_multiprocessing=False` default).
- **ENG-NEW-90** — `simple_mastering.py` chunk loop has no assertion that `_process()` output length equals input length (`:247-307`).

### Dimension 6 — Analysis (5)
- **ENG-NEW-100** — New `ThreadPoolExecutor(max_workers=5)` per `analyze()` call; up to 80 threads under concurrent 16-worker scanning (`audio_fingerprint_analyzer.py:174-224`).
- **ENG-NEW-101** — `lru_cache` genre classifier non-thread-safe on first concurrent call (`genre_classifier.py:158-169`).
- **ENG-NEW-102** — `VariationOperations.calculate_all` computes RMS with inconsistent frame sizes — `dynamic_range_variation` and `loudness_variation_std` are incomparable (`variation_ops.py:213-248`).
- **ENG-NEW-103** — `TemporalOperations.calculate_all` calls `librosa.beat.beat_track` twice with different inputs (~100-400 ms wasted) (`temporal_ops.py:47-48, 84-85`).
- **ENG-NEW-104** — DB and `.25d` file caches can diverge on file re-encode; DB checked first and serves stale (`fingerprint_service.py:132-148`).

### Dimension 7 — Library & Database (6, including 1 existing)
- **ENG-NEW-112** — `similarity.find_similar` fallback calls unbounded `get_all()` on prefilter miss (`similarity.py:147-156`).
- **ENG-NEW-113** — `playlist_repository.reorder_track` accesses `playlist.tracks` without `selectinload()` — implicit lazy SELECT (`playlist_repository.py:294-308`).
- **ENG-NEW-115** — **Existing: #3458** — `stats_repository` sums all tracks without WHERE; orphaned rows inflate library totals.
- **ENG-NEW-116** — `MigrationManager` engine missing `pool_pre_ping=True` (`migration_manager.py:129-135`).
- **ENG-NEW-118** — `playlist.get_all` expunges `Playlist` but not nested `Track` objects; DetachedInstanceError risk on `track.artists`/`track.album` (`playlist_repository.py:99-113`).
- **ENG-NEW-119** — Scanner `should_stop` is per-instance; cancelled `asyncio.to_thread` task leaves the thread running; `wait_for` timeout doesn't actually stop the scan (`scanner.py:52`, `library.py:481`).
- **ENG-NEW-120** — `cleanup_incomplete_fingerprints` uses raw `text()` SQL in a repository method (inconsistency with the rest of the layer) (`fingerprint_repository.py:969-972`).

---

## Cross-dimension relationships

1. **Float64 dtype creep cluster** (`ENG-NEW-22/23/24/26/29` + Rust HPSS gain in `ENG-NEW-42`): one mechanical fix (`dtype=audio.dtype` in `np.zeros`/`np.empty`) addresses 5 of 8 sample-integrity findings. The `BrickWallLimiter` (`ENG-NEW-22`) is the priority target because it runs at the end of every `HybridProcessor` mode.

2. **Causal `sosfilt` parallel-add cluster** (`ENG-NEW-40/45/47` + closed `#3469/#3470`): four findings, all the same template. `ENG-NEW-47` is the widest (6 tonal stages); fix order can mirror the `#3469` precedent: `sosfilt → sosfiltfilt` + `astype(audio.dtype)`.

3. **Player lock-ordering cluster** (`ENG-NEW-55/63/56`): one structural change in `add_to_queue` (drop `_audio_lock` before I/O) resolves the HIGH dropout AND the MEDIUM deadlock surface. `ENG-NEW-56` is a smaller atomic-section fix in `load_file`.

4. **Realtime-pipeline over-gain chain** (`ENG-NEW-41 + ENG-NEW-46`): both feed excess gain into the streaming brick-wall limiter. ENG-NEW-41 in realtime path; ENG-NEW-46 in adaptive/continuous path. Both produce continuous transparent limiting that defeats the compressor's dynamic intent.

5. **Unbounded query cluster** (`ENG-NEW-110/112/117`): one truthiness-guard fix (`ENG-NEW-117`: `if limit is not None`) is the structural root cause for the unbounded reads. Adding default caps to call sites is the per-call defensive fix.

6. **Fingerprint divergence cluster** (`ENG-NEW-95/99/104`): non-deterministic 25D vectors (95), stale `.25d` cache (99), divergent DB/file caches (104). All produce wrong fingerprints being served. Combined fix: push resample into analyzer + use `st_mtime` for cache key + unify the two cache tiers.

---

## Prioritized fix order

### Tier 1 — single-PR surgical wins (high impact, low risk)

1. **`ENG-NEW-22`** — `dtype=audio.dtype` in BrickWallLimiter allocations. Fixes the dominant float64 leak in the streaming pipeline.
2. **`ENG-NEW-25`** — `np.clip` before `output_file.write()` in `simple_mastering.py`. One-line defense at the encode boundary.
3. **`ENG-NEW-41`** — Fix `auto_makeup_gain` formula. Stops streaming-path over-compression.
4. **`ENG-NEW-47`** — `sosfilt → sosfiltfilt` in `ParallelEQUtilities`. Same template as #3469/#3470. Affects all 6 tonal mastering stages.
5. **`ENG-NEW-55`** — Restructure `add_to_queue` to drop `_audio_lock` before file I/O. Fixes audio dropout AND `ENG-NEW-63` deadlock surface.
6. **`ENG-NEW-58`** — Move `_stop_requested.clear()` after `playback.play()`. One line; restores auto-advance after stop/play race.
7. **`ENG-NEW-71`** — `'-ac', '2'` in FFmpeg command. Restores 5.1 vocal content.
8. **`ENG-NEW-95`** — Push 22 050 Hz resample into `AudioFingerprintAnalyzer.analyze()`. Fingerprint determinism.
9. **`ENG-NEW-117`** — `if limit is not None:` in `fingerprint_repository.get_all`. Root cause of `ENG-NEW-110/112`.

### Tier 2 — medium-effort cleanups

10. **`ENG-NEW-23/26/29`** — Apply the `dtype=` pattern to the remaining DSP allocators.
11. **`ENG-NEW-40/45`** — Two more `sosfilt → sosfiltfilt` sites (tilt correction, HF limiter).
12. **`ENG-NEW-46`** — Use real LUFS measurement for normalization target.
13. **`ENG-NEW-85/86/87`** — `ParallelFeatureExtractor` parity fixes with `ParallelBandProcessor`.
14. **`ENG-NEW-56/57`** — Player lock-ordering improvements (atomic load/swap, queue index rollback).
15. **`ENG-NEW-70`** — Duration guard in `unified_loader` for FFmpeg formats.
16. **`ENG-NEW-97`** — Remove `if len(chunk) >= block_size` guard in LUFS feeds.
17. **`ENG-NEW-99`** — Switch `.25d` cache key from MD5(1 MB) to `st_mtime + st_size`.
18. **`ENG-NEW-110/111/114`** — Library layer correctness wins (paginate cloud refresh, bulk update flags, migration lock on standalone migration).

### Tier 3 — larger restructures / defer

19. **`ENG-NEW-43`** — PsychoacousticEQ analysis/application window unification (requires architecture decision: drop analysis window OR implement WOLA).
20. **`ENG-NEW-42`** — Rust HPSS OLA normalization (Rust crate change + maturin rebuild).
21. **`ENG-NEW-48`** — `chroma_energy` replacement with real chroma_cqt (Rust + downstream similarity recalibration).
22. **`ENG-NEW-96`** — Decide on `StreamingFingerprint`: complete (12D missing) or delete.
23. **`ENG-NEW-119`** — Scanner cancellation needs a structural fix (per-request registry or shared `threading.Event`).
24. **`ENG-NEW-100`** — Reuse `ThreadPoolExecutor` across fingerprint analyzer calls.

### Tier 4 — opportunistic cleanup

LOW-severity items not in Tier 2/3: schedule as opportunistic cleanup during related work or in a dedicated cleanup sprint.

---

*Audit performed by 7 parallel dimension agents (Claude Sonnet 4.6) coordinated by /audit-engine on 2026-05-26.*
*Full per-dimension reports archived at `/tmp/audit/engine/dim_{1..7}.md` (transient; cleaned up post-merge).*
