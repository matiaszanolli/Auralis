# Audio Engine Audit — 2026-09-13

**Scope**: `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/analysis/`, `auralis/services/`, `auralis/library/`, `auralis/optimization/`, `vendor/auralis-dsp/`
**Depth**: deep | **Dimensions**: all 7 | **HEAD**: `ce119be1`
**Method**: fresh read of the live tree, one dimension agent per area, then an orchestrator re-check of every HIGH/MEDIUM claim against the source. Deduplicated against 1,500 GitHub issues (134 open).

Context: the enhancement presets were narrowed to `'adaptive'` on 2026-09-13 (`c195ac80`, `ae9d28e3`). This was a deliberate change and is not reported as a regression. Dimensions 1, 2 and 7 found no engine table, settings default or migration that still accepts a removed preset name.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 3 |
| MEDIUM   | 6 |
| LOW      | 11 |
| **Total**| **20** |

Per dimension, after merge and severity re-calibration:

| Dimension | H | M | L |
|---|---|---|---|
| 1 Sample Integrity | 0 | 1 | 0 |
| 2 DSP Pipeline | 1 | 1 | 1 |
| 3 Player State | 0 | 1 | 2 |
| 4 Audio I/O | 1 | 1 | 1 |
| 5 Chunked Mastering | 0 | 0 | 3 |
| 6 Analysis | 1 | 1 | 2 |
| 7 Library & Database | 0 | 1 | 2 |

**Severity changes made during merge** (each re-checked against the code):
- ENG-D2-01: HIGH → MEDIUM. It causes up to 3 dB of loudness deviation, not a click, gap or phase artifact.
- ENG-D7-01: HIGH → MEDIUM. The measured overhead is about 3 ms per claim at 29k tracks, which is small next to the seconds each fingerprint extraction takes.
- ENG-D5-01: MEDIUM → LOW. It is a scope extension of open issue #5116 (LOW), with the same trigger window and the same failure mode.
- ENG-D4-02: stays HIGH, with a wider description. The orchestrator found that the `.bak` file is never removed after a successful single-track write, so data loss does not need a concurrent request.
- ENG-D6-02: reframed. The indexes do exist on databases upgraded through v003→v004. They are missing only on databases created fresh by `create_all`.

**Key themes**
1. **The track's real sample rate never reaches the mastering processor.** Both production paths build `UnifiedConfig()` with its 44100 default, while the audio stays at the file's own rate (ENG-D2-03). This is the most impactful finding: it silently mistunes EQ and loudness on every 48 kHz or 96 kHz track.
2. **Silent failure recovery in background and safety paths.** Fingerprint placeholders are never cleared after a failed extraction (ENG-D6-01). A stale `.bak` file can be restored over the audio file (ENG-D4-02). The realtime chain has no NaN guard (ENG-D1-01). The True Peak guard swallows every exception (ENG-D5-02).
3. **Fingerprint database scaling.** A fresh database lacks the eight fingerprint indexes that upgraded databases have (ENG-D6-02). The scheduler rescans the table without a cursor (ENG-D7-01). Both grow with library size, and together they compound on new installs.
4. **Areas that are already well hardened.** Stage sample counts and copies, WOLA/COLA, the chunk-loop reassembly invariant (verified end to end), Rust GIL release and panic mapping, migration locking and backups, and FFmpeg lifecycle all passed re-verification. Most residual findings are narrow.

---

## Findings

### HIGH

### ENG-D2-03: Mastering processors always assume 44.1 kHz; the track's real sample rate is never passed into `UnifiedConfig`
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/config/unified_config.py:40`; `auralis-web/backend/core/job_config.py:47`; `auralis-web/backend/core/job_execution.py:94-105`; `auralis-web/backend/core/processor_factory.py:261` (`owned_config = deepcopy(config) if config is not None else UnifiedConfig()`); consumers `auralis/core/hybrid_processor.py:63-102`, `auralis/core/processing/continuous_dsp_ops.py:201,222,251,256`, `auralis/core/processing/continuous_stages.py:135-200`, `auralis/core/processing/continuous_mode.py:182,252`, `auralis/core/processing/adaptive_mode.py:115-245`
- **Status**: NEW. It is distinct from #5244 (ML classifier singleton, OPEN) and from #4622/#4924 (default parameters on DSP utilities, CLOSED).
- **Description**: `internal_sample_rate` defaults to 44100. Neither production construction path overrides it:
  - The offline job path loads audio at its own rate (`load_audio(job.input_path, cancel_event=...)`, with no `target_sample_rate`), then builds `engine._create_processor_config(job)` → `UnifiedConfig()` without that rate.
  - The streaming path calls `processor_factory.get_or_create(track_id, preset, intensity, mastering_targets=...)` without a `config`, so it falls back to `UnifiedConfig()`. The chunk loader (`chunk_operations.py:158`) loads at `ChunkedAudioProcessor.sample_rate`, which is the file's real rate.

  No resampler runs in between. `auralis/utils/checker.py::check` would resample to `internal_sample_rate`, but it has no production caller. Every internal consumer therefore reads a 48 kHz or 96 kHz buffer as if it were 44.1 kHz:
  - the psychoacoustic EQ critical-band to FFT-bin mapping, which is about 8.8% off at 48 kHz and 2.18× off at 96 kHz;
  - every `calculate_loudness_units` K-weighting and LUFS target call;
  - the HF-aware limiter crossover;
  - `ContinuousMode`'s fresh-fingerprint fallback (`fingerprint_analyzer.analyze(audio, self.config.internal_sample_rate)`), which resamples to 22050 Hz from the wrong `orig_sr`. That feeds a pitch- and time-distorted signal into the 25D fingerprint that drives every continuous mastering parameter.
- **Evidence**: `grep -rn internal_sample_rate auralis auralis-web/backend` shows exactly one construction site that sets it: `auralis/core/analysis/content_analysis_facade.py:136` (`UnifiedConfig(internal_sample_rate=self.sample_rate)`). `ProcessorPool.cache_key()` (`processor_pool.py:68`) already includes `internal_sample_rate` in its key, so the design expected this value to vary.
- **Impact**: For every non-44.1 kHz track, which covers many real libraries (48 kHz video rips and DAW exports, 96 kHz hi-res FLAC), both export and streaming playback apply EQ at the wrong frequencies and aim at the wrong loudness. On the export/job path, which never calls `set_fixed_mastering_targets`, the whole mastering decision comes from a corrupted fingerprint. The result is audible tonal and loudness mistuning. No error is logged.
- **Siblings**: Every `self.config.internal_sample_rate` consumer listed above.
- **Suggested Fix**: Pass the real rate through both paths. `job_config.create_processor_config(job, sample_rate)` should set `internal_sample_rate=sample_rate`, and `chunk_processor_init.init_fingerprint_and_processor` should build the `UnifiedConfig` from `ChunkedAudioProcessor.sample_rate` and pass it to `get_or_create`. The cache keys already include the rate. Add a regression test that masters a 48 kHz sine and asserts the EQ band frequencies.

### ENG-D4-02: Metadata-edit backup uses a fixed `<file>.bak` that is never cleaned up; a failed write can restore a stale or corrupted copy over the audio file
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis/library/metadata_editor/backup.py:20-60` (`create_backup`, `restore_backup`); `auralis/library/metadata_editor/metadata_editor.py:135-194` (`write_metadata`); caller `auralis-web/backend/routers/metadata.py:418-425` (single-track PATCH, always `backup=True`)
- **Status**: NEW
- **Description**: `create_backup` copies to the fixed path `filepath + '.bak'`, and `write_metadata` ignores its boolean return. On any exception, `restore_backup` runs `shutil.move(<file>.bak, filepath)`, replacing the whole audio file. Nothing serializes writes per file. The orchestrator confirmed a stronger variant of the agent's race:
  1. **Leftover backups.** `cleanup_backup` is called only from `batch_update` (`metadata_editor.py:266,325`). The single-track path never deletes its `.bak`, so every edited track leaves a full copy of the audio file on disk.
  2. **Stale restore without any concurrency.** Edit A succeeds and leaves `<file>.bak` holding the pre-A audio. Later, edit B's `create_backup` fails (disk full, permissions, file locked), which is logged as a warning and ignored. Then B's `audio_file.save()` raises; `writers.write_mp4_metadata`'s `int(parts[0])` on a malformed track or disc value is one plausible trigger. `restore_backup` moves the stale pre-A `.bak` over the file, silently undoing edit A.
  3. **Concurrent requests.** Two requests for the same track (double submit, retry) each `shutil.copy2` to the same `.bak` with no lock. The backup can capture the other request's half-written state, and a failure then restores that.
- **Evidence**:
  ```python
  # metadata_editor.py:155-156, 189-194
  if backup:
      self.backup_manager.create_backup(filepath)      # return value ignored
  ...
  except Exception as e:
      if backup:
          self.backup_manager.restore_backup(filepath)  # moves whatever <file>.bak holds
      raise
  ```
- **Impact**: The user's source audio file can be rolled back to an older state or replaced with a torn copy. Leftover `.bak` files double the disk use for every edited track, and the library scanner may pick them up depending on extension filtering.
- **Siblings**: `batch_update` shares `create_backup`/`restore_backup`. It aborts when a backup fails and cleans up on success, but it is not serialized against a concurrent single-track PATCH on the same file.
- **Suggested Fix**: Write the backup to a unique temp file next to the target (`tempfile.mkstemp`) and track that exact path for restore and cleanup. Abort the write if the backup fails. Delete the backup after a successful save. Serialize writes with a per-path lock.

### ENG-D6-01: A failed fingerprint extraction leaves its placeholder row in place, so the track is not retried until the app restarts
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/library/repositories/fingerprint_scheduler_repository.py:39-100` (`claim_next_unfingerprinted_track` inserts a `lufs=-100.0` placeholder at the current `fingerprint_version`), `:126-178` (`claim_next_outdated_fingerprint`); `auralis/services/fingerprint_worker.py:247-268` (`_process_track` failure branch); `auralis/library/database.py:233,449` (the only caller of `cleanup_incomplete_fingerprints`)
- **Status**: NEW
- **Description**: The claim step commits a placeholder `TrackFingerprint` row before extraction runs. Extraction can fail for ordinary reasons: the file exceeds `MAX_FINGERPRINT_FILE_SIZE_MB`, decoding fails, the vector is incomplete, or the 600 s bounded-extract timeout fires. When that happens, `_process_track` only logs the error and increments `stats['failed']`; the placeholder stays. The track then matches neither claim query:
  - Phase 1 needs `TrackFingerprint.id == None`.
  - Phase 2 needs `fingerprint_version < current_ver AND lufs != -100.0`.

  `cleanup_incomplete_fingerprints()` would re-queue it, but its only caller is `LibraryDatabase.__init__`, which runs once per process.
- **Evidence**: the orchestrator confirmed the failure branch (`except Exception as e: error(...); stats['failed'] += 1; _report_progress(...)`, with no delete or reset) and confirmed that `grep cleanup_incomplete_fingerprints` finds only the startup call site.
- **Impact**: Tracks that fail fingerprinting for transient reasons stay unfingerprinted for the rest of the session. They are left out of similarity and recommendations, and `get_fingerprint_stats()` keeps counting them as `pending`, so the UI shows fingerprinting stuck below 100% and a rescan does not fix it. The tracks most affected are the largest and most unusual files.
- **Siblings**: `fingerprint_queue.py:229-231,253-255` retries a failing claim call every 0.1 s with no backoff, so a sustained DB error makes every worker busy-loop.
- **Suggested Fix**: On failure, delete the placeholder, or mark it with a distinct failed sentinel plus a retry count or timestamp. Retry only transient failures, and keep permanent ones such as oversized files from hot-looping. Alternatively, run `cleanup_incomplete_fingerprints()` periodically, not just at startup.

---

### MEDIUM

### ENG-D2-01: Crest-preservation guard applies a uniform gain, which cannot change crest factor; its only effect is up to 3 dB of extra attenuation
- **Severity**: MEDIUM (downgraded from HIGH at merge)
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_stages.py:224-249` (`_stage_normalization`); `auralis/dsp/basic.py:46-62` (`amplify`)
- **Status**: NEW
- **Description**: When `_apply_final_normalization`'s limiter reduces crest factor by more than 4 dB, the guard calls `amplify(processed_audio, pullback_db)` with `pullback_db ∈ [-3, 0)`. `amplify` multiplies the whole buffer by one scalar, which shifts peak dB and RMS dB equally and leaves crest (`peak_db - rms_db`) unchanged. The guard therefore does not "restore up to 3 dB" of crest. It only turns the output down, below the LUFS target that normalization just computed, and logs a misleading "Crest preservation" message.
- **Evidence**: `continuous_stages.py:238-247`: `crest_crush = post_crest_db - pre_norm_crest.crest_db; if crest_crush < -4.0: pullback_db = max(-3.0, crest_crush + 4.0); processed_audio = amplify(processed_audio, pullback_db)`.
- **Impact**: Heavily limited material comes out up to 3 dB quieter than its computed `target_lufs`, with no dynamics benefit. This produces inconsistent loudness across a catalog, specifically on the loud, dense tracks where the limiter works hardest.
- **Siblings**: None. The other three cross-dimensional guards (EQ→LUFS, dynamics→tilt, stereo→phase) each use a correction that can actually change the quantity they measure.
- **Suggested Fix**: To preserve crest, reduce the pre-limiter makeup gain so the limiter compresses less. Otherwise remove the `amplify` pullback.

### ENG-D7-01: Fingerprint scheduler claim queries rescan the table from the start on every claim (no cursor), making a full-library run O(N²)
- **Severity**: MEDIUM (downgraded from HIGH at merge)
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_scheduler_repository.py:39-100`, `:126-178`
- **Status**: NEW
- **Description**: Each call claims one row and re-runs a query that walks `tracks` (or `track_fingerprints`) in id order, stepping past every already-claimed row. `EXPLAIN QUERY PLAN` shows `SCAN tracks` and `SCAN tf USING INDEX sqlite_autoindex_track_fingerprints_1`. With no `id > :cursor` high-water mark, the total cost is quadratic.
- **Evidence**: The agent measured on a scratch database with 30,000 tracks: 0.069 ms per claim at the start, 3.08 ms per claim after 29,000 claims (44× slower). A 20,000-track run spent 20.9 s on scheduling overhead alone.
- **Impact**: This is extra overhead, not a failure. It becomes minutes of wasted DB work at 100k tracks and gets worse with more worker threads. `claim_next_outdated_fingerprint` hits the worst case on every `FINGERPRINT_ALGORITHM_VERSION` bump, when the whole library is re-processed. On fresh databases there is also no `idx_fingerprints_version` index (see ENG-D6-02).
- **Siblings**: Both claim methods in the file.
- **Suggested Fix**: Keep a per-session cursor (last claimed id), add `WHERE id > :cursor`, and do one full pass at the end to catch rows skipped by races. Alternatively, claim a batch of ids per round trip.

### ENG-D1-01: The live realtime playback chain has no NaN/Inf guard, and its peak clamp does nothing when the chunk contains NaN
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/player/realtime/processor.py:156-176` (`RealtimeProcessor.process_chunk` final safety limiting); siblings `auralis/player/realtime/auto_master.py`, `level_matcher.py`, `gain_smoother.py`
- **Status**: NEW (related to #5191, which covers the `HybridProcessor` short-buffer path)
- **Description**: `HybridProcessor`, `ContinuousMode`, `AdaptiveMode` and `SimpleMasteringPipeline` all validate or repair non-finite samples. The orchestrator confirmed that `grep -rnE "isfinite|validate_audio_finite|isnan|nan_to_num|sanitize" auralis/player/` returns nothing. The final clamp, `max_val = np.max(np.abs(processed)); if max_val > target_peak: ...`, compares NaN, and `NaN > x` is False, so a NaN chunk passes through unclamped to the output device.
- **Evidence**: The agent executed the two most likely NaN sources (adaptive gain with ±inf/NaN LUFS, and silent chunks). Both are already clamped upstream, so this is a missing safety net, not a demonstrated crash.
- **Impact**: If any stage in this chain produces a non-finite sample in the future, it reaches the audio device with no log or repair. Every other pipeline in the engine either raises or repairs in that case.
- **Suggested Fix**: End `process_chunk` with `validate_audio_finite(processed, context="realtime chunk output", repair=True)`, the same call `ContinuousMode` makes.

### ENG-D3-01: A second `shuffle()` before `unshuffle()` overwrites the pre-shuffle snapshot, so the original queue order is lost
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:334-357` (`shuffle`); `auralis/player/queue_controller.py:283-303` (`set_shuffle`)
- **Status**: NEW. It is distinct from closed #4525, which covered queue edits made while shuffled, and #4986, which made `set_shuffle` actually reorder the queue.
- **Description**: `shuffle()` always sets `self._pre_shuffle_tracks = list(self.tracks)`, even when a snapshot is already stored. `set_shuffle(True)` calls `self.queue.shuffle()` whether or not shuffle is already on. A repeated enable (double click, retried request, UI race) saves the already-shuffled order, and `unshuffle()` then restores that order instead of the original.
- **Evidence**: Deterministic repro: `add(a..d); shuffle(); shuffle(); unshuffle()` does not give back `[a, b, c, d]`. The orchestrator confirmed the code.
- **Impact**: "Restore original order" silently restores the wrong order. No crash and no audio impact.
- **Suggested Fix**: Take the snapshot only when `_pre_shuffle_tracks is None`, and/or make `set_shuffle(True)` do nothing when shuffle is already enabled.

### ENG-D4-01: FFmpeg intermediate decode is hardcoded to 16-bit PCM regardless of source bit depth
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:431-435` (`'-acodec', 'pcm_s16le'`); `_probe_audio()` (~line 232) never reads `bits_per_raw_sample`
- **Status**: NEW
- **Description**: Every file decoded through FFmpeg (mp3, m4a, aac, ogg, wma, opus) goes through a 16-bit WAV. `-ar` keeps the original sample rate (#2495), but bit depth is not kept. 24-bit ALAC-in-M4A and WMA Lossless are truncated to 16 bits (about 96 dB of dynamic range) before any DSP or fingerprinting runs.
- **Impact**: Precision is lost silently and permanently for lossless sources decoded through FFmpeg. There is no audible corruption in normal listening, but it contradicts the loader's own care about preserving the source.
- **Suggested Fix**: Use `pcm_s24le`, or `pcm_f32le` since soundfile reads the result back as float32 anyway, either always or when ffprobe reports more than 16 bits. The cost is only temp-file size.

### ENG-D6-02: Fresh databases lack the fingerprint dimension indexes that upgraded databases have, so similarity-graph builds on new installs do a full table scan per track
- **Severity**: MEDIUM
- **Dimension**: Analysis (schema drift — Library & Database)
- **Location**: `auralis/library/models/fingerprint.py:104-112` (`__table_args__` declares only `ix_fingerprints_is_reference`); `auralis/library/migrations/migration_v003_to_v004.sql:62-84` (creates `idx_fingerprints_{track_id,bass_pct,mid_pct,lufs,crest_db,tempo_bpm,composite,version}`); hot path `auralis/analysis/fingerprint/knn_graph.py:129-137` → `similarity.py::_get_prefiltered_candidates` → `auralis/library/repositories/fingerprint_similarity_mixin.py:189-224`
- **Status**: NEW (reframed by the orchestrator)
- **Description**: The agent reported the pre-filter columns as unindexed. The orchestrator found that databases upgraded through v003→v004 do have these indexes. However, a database created by `LibraryDatabase` → `Base.metadata.create_all` on a new install gets only `sqlite_autoindex_track_fingerprints_1` and `ix_fingerprints_is_reference`. This was verified by creating a scratch database under `/tmp`. The model's own comment says it mirrors migration indexes for fresh databases, but it mirrors only the v015 index. `KNNGraphBuilder.build_graph()` runs one `lufs`/`crest_db`/`bass_pct`/`tempo_bpm` range query per track, so on a new install every one of those queries scans the whole table, and the build is O(N²).
- **Impact**: Similarity-graph builds and rebuilds get much slower as the library grows, but only for users whose database was created new. The same install also lacks `idx_fingerprints_version` (compounding ENG-D7-01), so performance differs between new and upgraded installs.
- **Suggested Fix**: Declare the v004 indexes in `TrackFingerprint.__table_args__` (or add a migration step that creates them `IF NOT EXISTS`), and add a test that a `create_all` schema has the same index set as a migrated one.

---

### LOW

### ENG-D5-01: Raw `sosfiltfilt` crashes on a very short final chunk — three more sites in the chunk path than #5116 lists
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/dsp/resonance_notcher.py:214`, `auralis/core/dsp/transient_shaper.py:102`, `auralis/core/dsp/harmonic_exciter.py:135,147`
- **Status**: Existing: #5116 (OPEN), scope extension. #5116 lists only `parallel_eq.py` and `sub_bass_control.py`, and those are confirmed still unguarded. Comment on #5116 rather than filing a new issue.
- **Description**: The last iteration of `mastering_chunk_loop.py` reads `total_frames - read_pos` samples with no overlap (`:152-158`). When that is shorter than scipy's `padlen` (9-15 samples for these filters), `sosfiltfilt` raises `ValueError`.
- **Evidence**: The agent reproduced it end to end: `SimpleMasteringPipeline.master_file` on a 2×44100+5-sample file with `CHUNK_DURATION_SEC=1` crashed in `resonance_notcher.py:214`. Thanks to #5109 no output file was published.
- **Impact**: Mastering fails for the whole file at certain file lengths. Nothing is corrupted, and the batch driver continues with the next file.
- **Siblings**: `parallel_eq.py:101,103,175,177,252,254`, `sub_bass_control.py:72` (both in #5116). The orchestrator's grep also found raw calls at `auralis/core/processing/continuous_guards.py:78` and `auralis/core/processing/hf_aware_limiter.py:138`, which are on the `HybridProcessor` path. Whether those two can receive input shorter than `padlen` was not verified.
- **Suggested Fix**: Send every site through `sosfiltfilt_safe` in `auralis/dsp/utils/filters.py`, or fold a tiny final remainder into the previous chunk.

### ENG-D2-02: Most of the live `PerformanceOptimizer` (cache, memory pool, SIMD) is never called
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/optimization/performance_optimizer.py:39-142`, `auralis/optimization/caching/smart_cache.py`, `auralis/optimization/memory/memory_pool.py`, `auralis/optimization/acceleration/simd_accelerator.py`, `auralis/optimization/config.py`
- **Status**: NEW. It is narrower than #5142 (whether the package is live) and does not regress #4524 (cache returning another track's audio): the cache is never filled on any real request.
- **Description**: Of the singleton's surface, only `profiler.time_function` runs in production. `cached_function`, `optimize_real_time_processing`, `get_audio_buffer`/`return_audio_buffer` and `optimized_fft`/`optimized_convolution` have no callers outside `performance_optimizer.py`. The `PerformanceConfig` settings for caching, SIMD and the memory pool are unused.
- **Impact**: No correctness impact. Configurable-looking code that never runs, with no production exercise.
- **Suggested Fix**: Either wire a real hot path through it or delete the unused surface and trim `PerformanceConfig`. Update `scripts/check_optimization_importers.py` expectations to match.

### ENG-D3-02: `audio_data` / `reference_data` getters read without `_audio_lock`, unlike their setters and the class docstring
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_properties_mixin.py:73-97`
- **Status**: NEW (the gap was left open by #3785 and #4574)
- **Description**: The setters take `file_manager._audio_lock`; the getters return `self.file_manager.audio_data` directly. That breaks the "every data-bearing property acquires its writer's lock" rule written in the class docstring. It is harmless under the GIL and a torn-read risk under free-threaded 3.14.
- **Impact**: No production caller was found (test-only), so the risk is small.
- **Suggested Fix**: Wrap both getters in `with self.file_manager._audio_lock:`.

### ENG-D3-03: Stale lock-ordering comment in `GaplessPlaybackEngine` contradicts the only nesting that happens after #5105
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:48-61` (comment) vs `:375-386` (`with self.update_lock: with self.file_manager._audio_lock:`)
- **Status**: NEW
- **Description**: The comment says `_audio_lock` is always the outer lock and forbids taking `update_lock` first. Since #5105, `next_track()` no longer holds `_audio_lock`, so the only nesting left is `update_lock` → `_audio_lock`, exactly what the comment forbids. The agent grepped every acquisition of both locks; there is no reverse nesting today, so no deadlock.
- **Impact**: The comment could lead a future change into an AB-BA deadlock.
- **Suggested Fix**: Rewrite the comment to state the current `update_lock` → `_audio_lock` order.

### ENG-D4-03: End-to-end decode tests for FFmpeg formats cover only MP3
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `tests/input_media/` (only `.mp3`); `tests/auralis/io/test_ffmpeg_bounded_decode_5110.py` and siblings mock `subprocess`
- **Status**: NEW
- **Description**: Of the six `FFMPEG_FORMATS`, m4a, aac, ogg, opus and wma are covered only by command-construction tests with mocked subprocess calls.
- **Impact**: A format-specific regression in `-ac`, `-ar` or codec handling would not be caught.
- **Suggested Fix**: Add an ffmpeg-gated test that encodes a short synthetic WAV to each format and round-trips it through `load_with_ffmpeg`, checking frame count, sample rate and channel count.

### ENG-D5-02: True Peak safety guard swallows every exception without logging
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:204-212`
- **Status**: NEW
- **Description**: The 4× oversampled True Peak ceiling runs inside `try: ... except Exception: pass`. `resample_poly` handles 1-10-sample input without raising, so this is not triggered today. Any future failure would silently turn off the ceiling for that chunk, even though the code comment justifies the ceiling with "74% of outputs exceeded 0 dBFS True Peak".
- **Suggested Fix**: Log a warning and/or record `true_peak_guard_failed` in the chunk `info` dict.

### ENG-D5-03: Chunk-seam safety depends on an unchecked "crossfade much longer than stage settle time" relationship
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_config.py:61-64` (`CHUNK_DURATION_SEC`, `CROSSFADE_DURATION_SEC`); `auralis/core/dsp/transient_shaper.py` (`fast_ms`, `slow_ms`); `auralis/core/mastering_presets.py:280` (`LOUDNESS_LIMITER_RELEASE_MS`)
- **Status**: NEW
- **Description**: The transient envelopes and the loudness limiter start fresh on every chunk. That is fine because the 3 s crossfade is 12-50× longer than their settle times: the agent found no measurable step at chunk boundaries (within ±0.06 dB, the same as normal variance mid-chunk). Nothing links these constants, though, so a shorter crossfade or a longer release could bring back a step at every 30 s boundary.
- **Suggested Fix**: Assert the ratio in the config's `__post_init__`, or add a cross-referencing comment and a seam-continuity test.

### ENG-D6-03: `estimate_lufs` doc comment presents closed #4123 as planned work
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/dsp_math.rs:20-24`
- **Status**: NEW. #4123 was CLOSED on purpose in `b9751733`: the RMS proxy stays so all paths agree.
- **Description**: The comment says "see #4123 for the planned proper implementation", but no BS.1770 port is planned. The orchestrator confirmed the text.
- **Suggested Fix**: Describe it as an intentional RMS proxy shared across paths (with `LoudnessMeter` as the BS.1770 path) and remove the "planned" wording.

### ENG-D6-04: `FingerprintQuantizer.quantize()` silently turns NaN into the dimension's maximum
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/library/fingerprint_quantizer.py:114` (`clamped = max(min_val, min(max_val, value))`)
- **Status**: NEW (defense-in-depth for #5103)
- **Description**: `min(max_val, nan)` returns `max_val`; the agent confirmed this by running it. Both current callers sanitize non-finite values in `windowed_compute._sanitize_non_finite()` first, so it is unreachable today. A new `upsert()` caller would store maxed-out values that look valid, in the lossy 25-byte blob.
- **Suggested Fix**: Check `math.isfinite` for each dimension and raise, or fall back to the midpoint with a warning.

### ENG-D7-02: `QueueRepository` has no production callers, and it carries a latent duplicate-row race
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/queue_repository.py` (whole file); wired through `auralis/library/repositories/factory.py:155-160` and `auralis/library/database.py:281-283`
- **Status**: NEW (related: Existing #5246, which covers one method of the same class). This could be folded into #5246 at publish time.
- **Description**: The orchestrator confirmed that no production code calls `get_queue_state`, `set_queue_state` or `update_queue_state`. The `clear_queue` hits belong to the unrelated in-memory player and `QueueService`. All four methods select the first row or insert a default, with no singleton constraint, so two concurrent first calls could create two rows that are later read in arbitrary order.
- **Suggested Fix**: Delete the repository and the `QueueState` table usage, or build real persistence with a fixed-PK upsert. Same "wire it or remove it" call as #4997 (`QueueTemplateRepository`).

### ENG-D7-03: `SimilarityGraphRepository` bypasses `RepositoryFactory`
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/analysis/fingerprint/knn_graph.py:78-79`; `auralis/library/repositories/factory.py` (no `similarity_graph` property)
- **Status**: NEW
- **Description**: `KNNGraphBuilder` constructs `SimilarityGraphRepository(session_factory)` directly. It is the only one of the 13 repositories not reachable through the factory, contrary to the "single source of repositories" docstring in `database.py`. It shares the same session factory, so there is no pool or pragma drift.
- **Suggested Fix**: Add a cached `similarity_graph` property to `RepositoryFactory` and inject the factory into `KNNGraphBuilder`.

---

## Existing Issues Confirmed Still Present (not re-reported)

| Issue | State | Confirmed at |
|---|---|---|
| #5106 | OPEN MEDIUM | Unwrapped `np.clip` scalar promotes to float64 — `auralis/core/processors/reference_mode.py:37`, `auralis/core/processing/eq_processor.py:302,306` |
| #5191 | OPEN LOW | `HybridProcessor` `MIN_SAMPLES` early return before `validate_audio_finite` — `auralis/core/hybrid_processor.py:312-326` |
| #5245 | OPEN LOW | `process_chunk` Stage 3 output-normalization branch unreachable — `auralis/core/mastering_process_chunk.py:141-155` |
| #5116 | OPEN LOW | Raw `sosfiltfilt` in `parallel_eq.py` / `sub_bass_control.py` (scope extended by ENG-D5-01) |
| #5202 | OPEN LOW | Hand-rolled sessions in `fingerprint_similarity_mixin.py` reference-flag methods |
| #5247 | OPEN LOW | `TrackRepository.update_metadata()` returns a track whose relationships were not eager-loaded (`track_repository_mutation.py:161-195`) |
| #5246 | OPEN LOW | `QueueRepository.update_queue_state()` out-of-bounds `current_index` |
| #4823 | OPEN LOW | Scanner follows symlinks with no containment check (`auralis/library/scanner/file_discovery.py`) |
| #5174 | OPEN LOW | `LibraryDatabase.__init__` raises bare `Exception` on migration failure (`database.py:123`) |
| #5244 | OPEN LOW | ML genre classifier singleton hardcoded to 44.1 kHz (related to ENG-D2-03) |

Closed fixes re-verified as still present (no regressions): #2495, #2157, #2515, #3352, #3471, #3700, #3781, #3782, #4104/#4237, #4217 (`2b3c5b35`), #4525, #4574, #4595/#4994, #4596, #4611/#4597, #4834, #4837, #4875/#5104, #4966, #4989, #5103, #5105, #5107, #5109, #5110, `cca59d9c`, `8bc5b217`, `bd94fd59`, `8adb8d0a`, `53cef6b4`.

## Checked and Clean (summary)

- **Sample integrity**: all 13 `auralis/core/stages/` stages, `auralis/core/dsp/`, `auralis/dsp/dynamics/`, the `ContinuousMode`/`AdaptiveMode` paths and `auralis/io/saver.py` preserve shape and dtype and copy before mutating. The PCM write clips to [-1, 1].
- **DSP**: stage order is input_gain → EQ → dynamics → stereo → normalization. WOLA uses a fixed 50% hop with full-Hann synthesis and window-weight normalization. No double windowing. EQ bands are mapped by frequency. Sub-bass mix-back is zero-phase. The continuous coordinate math is tanh/smoothstep based and guarded against epsilon. Preset tables hold only `'adaptive'`, and unknown names fall back to neutral.
- **Rust boundary**: all 11 PyO3 wrappers use `py.allow_threads` and `catch_unwind` → `PyRuntimeError` and validate inputs. `process_chunks` has no production caller.
- **Player**: callbacks are dispatched outside locks. `defer_notifications` flushes in `finally`. Seek and position are clamped under `_audio_lock`. Queue index maintenance uses object identity (#4776). Library I/O never happens while a player lock is held.
- **Chunk loop**: sample-count reassembly verified end to end (396,900 in = 396,900 out). Whole-file analysis values are computed once per file. The output is written via a staged temp file and renamed only on success.
- **Audio I/O**: no hardcoded sample-rate fallback. Multichannel downmix is layout-aware. FFmpeg uses bounded timeouts and SIGTERM→SIGKILL on cancel, with no `shell=True`. Protocol paths are rejected. Decode-size ceilings and truncation detection are in place.
- **Analysis**: fingerprints are deterministic (windowing derived from duration, single Rust backend). Hilbert and decode lengths are capped. The ML classifier is rule-based and `lru_cache`d. There is no swallowing `except BaseException`.
- **Library**: pragmas are applied per connection (WAL, `busy_timeout`, `foreign_keys`). The engine is disposed at shutdown. Migrations take the file lock plus a thread lock, back up first and fail fast, and apply each step in one transaction. Get-or-create uses a savepoint plus `IntegrityError` handling. Cascades and playlist ordering are atomic. `cleanup_missing_files` pages with a cursor. Sidecar writes are atomic. `to_dict()` goes through `_safe_collection`/`_safe_scalar`. There is no raw SQL outside repositories, migrations and the composition root.

---

## Relationships

- **ENG-D2-03 ↔ #5244**: both come from components assuming 44.1 kHz instead of reading the real track rate. ENG-D2-03 is the live-DSP case; #5244 is the classifier case. One pass that passes the rate through `UnifiedConfig` should cover both.
- **ENG-D2-03 → fingerprint-driven mastering**: on the export path the wrong `orig_sr` corrupts the 25D fingerprint, and then ENG-D2-01's crest guard and the rest of the continuous parameter generation work from bad coordinates. Fix ENG-D2-03 before tuning any loudness or crest behaviour, or the tuning is done against distorted input.
- **ENG-D6-01, ENG-D7-01 and ENG-D6-02 share the fingerprint scheduler and table**: tracks stuck after a failure (D6-01) sit in the id prefix that every cursor-less claim walks past (D7-01), and on fresh databases the missing `idx_fingerprints_version` and dimension indexes (D6-02) make both the claims and the KNN build slower. Fix them together in one change to `fingerprint_scheduler_repository.py` plus the model's indexes.
- **ENG-D1-01 and ENG-D5-02** are the same kind of problem: a safety net that fails silently (no finite check; `except: pass`). ENG-D6-04 is the same pattern at the storage layer.
- **ENG-D5-01 and ENG-D5-03** both concern the chunk loop's final and boundary chunks. Folding a tiny remainder into the previous chunk would remove D5-01's trigger, and a seam test for D5-03 could use the same fixture.
- **ENG-D6-02 and ENG-D7-03** both touch `knn_graph.py`. A single refactor can inject the factory and fix the index gap.
- **ENG-D7-02 and #5246 / #4997**: the same "repository with no production callers" pattern as the already-deleted `QueueTemplateRepository`.

## Prioritized Fix Order

1. **ENG-D2-03 (HIGH)**: silent, audible mistuning on a large share of real tracks, on both export and streaming. The fix is small (pass one value through two construction sites), and cache keys already support it.
2. **ENG-D4-02 (HIGH)**: can roll back or overwrite user audio files. The fix is local to `backup.py` and `write_metadata`: unique temp backup, abort if the backup fails, delete on success, per-path lock.
3. **ENG-D6-01 (HIGH)**, together with **ENG-D7-01** and **ENG-D6-02 (MEDIUM)**: one fingerprint-scheduler change covering placeholder cleanup and retry policy, a claim cursor, and model index parity with a schema-parity test.
4. **ENG-D2-01 (MEDIUM)**: remove or replace the no-op crest pullback. Do this after #1 so loudness is re-validated on correct fingerprints.
5. **ENG-D1-01, ENG-D3-01, ENG-D4-01 (MEDIUM)**: small, independent fixes (one guard call, one snapshot condition, one codec flag).
6. **LOW batch**: comment on #5116 with the ENG-D5-01 sites and fix all sites with `sosfiltfilt_safe`. Then take D5-02, D6-04 (silent-guard hardening), D3-02, D3-03, D6-03 (lock and doc accuracy), D2-02, D7-02, D7-03 (dead surface and consistency) and D4-03, D5-03 (tests).

---

Suggested next step: `/audit-publish docs/audits/AUDIT_ENGINE_2026-09-13.md`
