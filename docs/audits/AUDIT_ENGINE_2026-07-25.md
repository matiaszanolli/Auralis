# Audio Engine Audit — 2026-07-25

**Scope**: Auralis core audio engine — `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/optimization/`, `auralis/analysis/`, `auralis/library/`, `auralis/services/`, `vendor/auralis-dsp/`
**Depth**: deep (full call-graph tracing)
**Method**: 7 independent dimension agents, fresh read of current source at `54d055df`. 168 commits since the prior engine audit (2026-07-12) — nothing was carried over from that report without re-verification.
**Dedup baseline**: 159 open GitHub issues + all closed issues, `docs/audits/AUDIT_ENGINE_2026-07-12.md`, `.claude/issues/`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 8 |
| LOW | 9 |
| **Total** | **19** |

**No CRITICAL findings.** The audio-integrity core is in good shape: every sample-count invariant, copy-before-modify discipline, dtype-preservation cast, and NaN containment checkpoint traced in Dimension 1 held up under verification, including the newest un-audited code (`mastering_branches/` from commit `211cfaba`). Dimension 1 produced **zero** findings — the first time this has happened for that dimension.

### Key themes

1. **Silent wrong-data paths beat crashes.** Both HIGH findings and several MEDIUMs share a shape: the code produces *plausible but wrong* output with no error, no warning, and no log line. A cache returns another track's audio (ENG-D5-1); a queue restore discards user edits (ENG-D3-1); a callback stops firing forever (ENG-D5-2); a fingerprint gets permanently stamped with the less-accurate of two algorithms (ENG-D6-1). None of these surface a diagnostic.

2. **Incomplete fixes are the dominant new-bug source.** Three findings are siblings the original fix missed: the `* 20000` centroid denormalization fixed in `_classify()` but not in the three parameter generators (ENG-D6-2); the `reset_history()` treatment applied to two of three quality analyzers (ENG-D6-3); the `#4119` ffprobe hardening applied to one of two ffprobe wrappers (ENG-D4-1). All three are duplicate implementations of the same logic that drifted — the DRY violation *is* the bug mechanism.

3. **A large amount of carefully-hardened concurrency code is unreachable.** The whole `auralis/optimization/parallel/` package, `ParallelSpectrumAnalyzer`, `MemoryPool`, and `HybridProcessor.process_realtime_chunk()`'s entire EQ chain have zero production callers. This is why two currently-open issues (#4506, #4502) are scoped "latent only", and it means point-fixes keep accruing on code nothing calls.

4. **Loader contract divergence.** `auralis/io/` guarantees a `(samples, channels)` contract that in practice depends on file extension, not audio content (ENG-D4-2), and its two ffprobe implementations disagree on error behavior (ENG-D4-1).

### Most impactful issues

- **ENG-D5-1 (HIGH)** — the `SmartCache` monkey-patch on `AdaptiveMode.process` keys on `repr()` of a NumPy array, which NumPy truncates to 6 elements. Reproducible collision between arrays differing in 90% of samples. Reachable via the public `hybrid` processing mode; the `ProcessorPool` deliberately reuses the instance across jobs, so `repr(self)` is stable too. Re-submitting the same file within the 300 s TTL is a 100 % collision.
- **ENG-D3-1 (HIGH)** — `unshuffle()` restores a stale pre-shuffle snapshot, silently deleting every queue edit made while shuffled. Fully deterministic, no concurrency needed, wired end-to-end from `PUT /player/queue/shuffle`.

---

## Findings

### HIGH

#### ENG-D5-1: PerformanceOptimizer's result cache can return a different track's processed audio
- **Severity**: HIGH
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/performance_optimizer.py:59-84,112-135`; key generation `auralis/optimization/caching/smart_cache.py:39-44`; wiring `auralis/core/hybrid_processor.py:557-589`
- **Status**: NEW
- **Description**: At import, `hybrid_processor.py` unconditionally monkey-patches `AdaptiveMode.process` at the **class** level with `PerformanceOptimizer.optimize_real_time_processing`, wrapping it in `cached_function`. Caching is on by default (`auralis/optimization/config.py:18`), so every call is memoized in the process-wide `SmartCache` singleton. The cache key is `md5(str((func_name, args, sorted(kwargs.items()))))` — i.e. `repr()` of the call arguments, including the `target_audio` NumPy array. NumPy summarizes `repr()` for arrays over 1000 elements (every real audio buffer) to first-3/last-3 samples plus `...`. Two completely different audio arrays therefore hash to the same key.
- **Evidence**:
  ```python
  # smart_cache.py:39-44 — key built from repr(args), no size/identity guard
  def _generate_key(self, func_name, args, kwargs):
      key_data = (func_name, args, sorted(kwargs.items()))
      return hashlib.md5(str(key_data).encode('utf-8')).hexdigest()
  ```
  ```python
  # hybrid_processor.py:574-577 — unconditional class-level patch at import
  AdaptiveMode.process = perf_opt.optimize_real_time_processing(AdaptiveMode.process)
  ```
  Collision reproduced locally: two `(2, 661500)` float32 arrays differing in ~595,000 of 661,500 samples produce `repr(a) == repr(b) == True`.
  Reachability: `HybridMode.process` unconditionally calls `self.adaptive_processor.process(...)` (`auralis/core/processing/hybrid_mode.py:68,101`); `hybrid` is a mode the public REST API accepts (`auralis-web/backend/routers/processing_api.py:61`); `auralis-web/backend/core/processor_pool.py` deliberately reuses one `HybridProcessor` across jobs of identical config, so `repr(self)` is stable across unrelated files inside the 300 s TTL.
- **Impact**: A hybrid-mode mastering job can silently receive another track's (or an earlier run's) processed audio — wrong audio written to the user's output with no error. Most reliably triggered by re-submitting the same input file within 5 minutes (byte-identical arrays → guaranteed hit), an ordinary action since neither reference track nor intensity is part of the cached `process()` signature. Does **not** affect the default playback/continuous-space path (`ContinuousMode` is never wrapped).
- **Suggested Fix**: Never key a cache on `repr()` of a NumPy array. Either exclude `ndarray` args from the key (hash shape/dtype/`array.tobytes()` content instead), or stop caching `AdaptiveMode.process` entirely — it mutates `self.last_content_profile`, so it is not a pure function and should not be memoized by a generic decorator.

#### ENG-D3-1: `QueueManager.unshuffle()` silently discards queue edits made while shuffled
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:289-335`
- **Status**: NEW
- **Description**: `shuffle()` snapshots the queue into `_pre_shuffle_tracks` (line 296). `unshuffle()` restores by **wholesale replacing** `self.tracks` with that snapshot (line 323). Any `add_track()`, `remove_track()`, `remove_tracks()`, or `reorder_tracks()` between the two mutates `self.tracks` in place but never updates `_pre_shuffle_tracks`, so `unshuffle()` throws those edits away. Fully deterministic — no concurrency required.
- **Evidence**:
  ```python
  # queue_manager.py:296 (shuffle)
  self._pre_shuffle_tracks = list(self.tracks)   # snapshot taken HERE
  # queue_manager.py:323 (unshuffle)
  self.tracks = self._pre_shuffle_tracks         # wholesale overwrite; edits lost
  ```
  Repro: `add(a); add(b); shuffle(); add(c); unshuffle()` → `c` is gone.
- **Impact**: Reachable production path: `PUT /player/queue/shuffle` → `auralis-web/backend/services/queue_service.py` (`unshuffle_queue`) → `QueueController.unshuffle()` (`auralis/player/queue_controller.py:325-327`) → `QueueManager.unshuffle()`. A user who shuffles, edits the queue, then turns shuffle off silently loses those edits — while the broadcast still reports `"Queue restored to original order"`.
- **Siblings**: None — `shuffle()`/`unshuffle()` are the only methods touching `_pre_shuffle_tracks`.
- **Suggested Fix**: Invalidate `_pre_shuffle_tracks` (set to `None`) on any queue-mutating call while shuffled, so `unshuffle()` declines to restore a stale snapshot. Declining to restore is strictly better than silently losing data.

---

### MEDIUM

#### ENG-D6-1: Batch and on-demand fingerprint paths use different windowing; the less-accurate one wins permanently
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/services/fingerprint_extractor.py:147-158` vs `auralis/analysis/fingerprint/fingerprint_service.py:240-404`
- **Status**: NEW
- **Description**: Two live independent implementations compute the 25D fingerprint with materially different sampling strategies. The **batch/library-scan** path (`FingerprintExtractor.extract_and_store`, driven by `FingerprintExtractionQueue`, started at app boot) truncates to the **first 90 s from the start** and runs a single-window analysis. The **on-demand** path (`FingerprintService._compute_fingerprint`, used by `auralis/core/mastering_prepare.py` and `auralis/player/fingerprint_loader_mixin.py`) uses a body window at 50 % of duration plus two 30 s probes at 25 %/75 %, replacing `lufs`/`crest_db` with the median. The file's own comment cites a 34-track validation study: single-window LUFS RMSE 1.96 dB / max 9.2 dB vs multi-window 1.07 dB / max 3.6 dB.
- **Evidence**: `get_or_compute()` checks the DB cache first (`fingerprint_service.py:145-149`) and `claim_next_unfingerprinted_track` only picks tracks with no fingerprint row — so whichever path runs first wins permanently, and the background queue almost always runs first.
- **Impact**: Essentially every track in a scanned library ends up stamped with the empirically-worse fingerprint; the validated accuracy improvement in `FingerprintService` is effectively dead in production. Downstream consumers (mastering target selection, similarity kNN graph, recording-type detection) all read the cached value.
- **Suggested Fix**: Have `FingerprintExtractor` call `FingerprintService.get_or_compute()` rather than duplicating load/analyze logic, so both paths share the body+probe windowing.

#### ENG-D6-2: `RecordingTypeDetector` parameter tuning still uses the `* 20000` centroid denormalization fixed in the same file's classifier
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/core/recording_type_detector.py:312,348,388`
- **Status**: NEW (incomplete prior fix — commit `7f937cca`)
- **Description**: Commit `7f937cca` diagnosed and fixed `_classify()` for denormalizing the 0-1 `spectral_centroid` with `* 20000` when the fingerprint actually clips at 8000 Hz (`CENTROID_NORMALIZATION_HZ`), replacing it with `centroid_to_hz()`. The three parameter-generation methods in the same file — `_parameters_studio`, `_parameters_bootleg`, `_parameters_metal` — still use the unfixed `* 20000`.
- **Evidence**: `git log -p 7f937cca -- auralis/core/recording_type_detector.py` shows the change applied only to `_classify`; `grep -n '\* 20000'` still matches lines 312, 348, 388. A real 700 Hz centroid (normalized 0.0875) computes as 1750 instead of 700, so the `< 600` / `> 800` branches never see realistic values.
- **Impact**: `_generate_parameters()` runs on every mastering pass through `HybridProcessor`/`ContinuousModeProcessor`. The per-type bass/treble fine-tuning (0.5-1.5 dB deltas) is driven by a value 2.5× too large, so the "brighter/darker than reference" nuance is broken for realistic content.
- **Siblings**: All three methods share the identical pattern.
- **Suggested Fix**: Replace all three call sites with `centroid_to_hz(...)`, matching `_classify`.

#### ENG-D6-3: `SpectrumAnalyzer.smoothing_buffer` not reset between `assess_quality()` calls — sibling the #4221 fix missed
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/quality/quality_metrics.py:95-99`; buffer at `auralis/analysis/base_spectrum_analyzer.py:60,152-159,193-195`
- **Status**: NEW (sibling of fixed #4221)
- **Description**: `assess_quality()` resets `phase_analyzer` and `dynamic_range_analyzer` history per #4221, but never resets `self.spectrum_analyzer`, which carries a persistent `smoothing_buffer` read and overwritten on every chunk in `_create_chunk_result()`. Only the never-called-here `reset_smoothing()` clears it, and `analyze_file()` doesn't reset at file start.
- **Evidence**: `compare_quality()` (`quality_metrics.py:218-230`) calls `assess_quality(audio1)` then `assess_quality(audio2)` on the same instance, so even a single comparison bleeds audio1's trailing smoothed spectrum into audio2's first chunk.
- **Impact**: Live in `ContinuousModeProcessor`'s Quality Gate (`auralis/core/processing/continuous_mode.py:385-400`), which reuses one `_quality_metrics` instance across the session. Every gated call's `frequency_response_score`/`spectral_centroid`/`spectral_rolloff` is contaminated by the previous call. Bounded to diagnostics today (the gate only logs on regression, never rejects audio) — but it undermines the pipeline's one automated regression check.
- **Suggested Fix**: Add `self.spectrum_analyzer.reset_smoothing()` alongside the two existing resets.

#### ENG-D6-4: Rust `estimate_tempo` reimplements a naive O(bins x N) per-frame DFT instead of reusing the existing FFT tempo module
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/fingerprint_compute.rs:317-392` (vs the FFT implementation in `vendor/auralis-dsp/src/tempo.rs`)
- **Status**: NEW
- **Description**: `estimate_tempo` (called from `compute_complete_fingerprint`) computes a manual DFT per analysis frame: for each of 513 bins, an O(frame_size) accumulation with two trig calls per sample. For a 90 s-capped 22050 Hz buffer that is roughly 3,900 frames x 513 bins x 1024 samples x 2 trig calls ≈ 4×10⁹ transcendental calls. The crate already links `rustfft` and already ships an FFT-based spectral-flux onset detector (`tempo::detect_tempo` / `compute_spectral_flux`) doing the equivalent work in O(N log N) per frame.
- **Evidence**:
  ```rust
  // fingerprint_compute.rs:340-350 — "Simple DFT magnitude for low bins (cheap approximation)"
  for k in 0..half {
      for (n, &s) in frame.iter().enumerate() {
          let angle = -2.0 * PI * k as f32 * n as f32 / frame_size as f32;
          re += s * angle.cos(); im += s * angle.sin();
      }
  }
  ```
- **Impact**: Very likely the dominant cost behind the ~75 s-per-track fingerprint time noted in `fingerprint_extractor.py`'s own docstring. Bounded (90 s / 300 MB caps prevent runaway), so this is efficiency, not a hang — but it multiplies across every track in a fresh scan and across all concurrent fingerprint workers.
- **Suggested Fix**: Replace the frame-magnitude loop with `rustfft`, or call `tempo::detect_tempo`/`compute_spectral_flux` directly.

#### ENG-D4-1: `get_audio_info()` masks corrupt-file errors behind an `UnboundLocalError`
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/unified_loader.py:199-257` (`_get_info_with_ffprobe`) — `raise` at line 222 vs `import json` at line 224
- **Status**: NEW
- **Description**: `import json` appears *after* the `returncode != 0` check. Because it appears anywhere in the body, `json` is a local name for the whole function. When ffprobe exits non-zero (corrupt input), the `raise ModuleError(...)` at line 222 is matched against `except json.JSONDecodeError:` — evaluating that clause reads the unbound local `json`, so Python raises `UnboundLocalError` and buries the real error.
- **Evidence**: Reproduced against current source with 2048 random bytes named `corrupt.mp3`:
  ```
  >>> get_audio_info(Path("corrupt.mp3"))['error']
  "cannot access local variable 'json' where it is not associated with a value"
  ```
  The sibling `_probe_audio()` in `auralis/io/loaders/ffmpeg_loader.py` places `import json` first inside its `try:` and produces the intended message for the same file.
- **Impact**: `get_audio_info()` is the primary metadata source for chunked playback (`auralis-web/backend/core/chunked_processor.py::_load_metadata`, the #4497 fix). When this fires, `_load_metadata()` logs a meaningless message and falls back to a full decode that fails again — one wasted FFmpeg conversion, plus root-causing "why does this upload fail" becomes needlessly hard from logs.
- **Siblings**: The same function calls only `check_ffmpeg()`, never `check_ffprobe()` — the exact gap #4119 fixed in `ffmpeg_loader.py`. If ffprobe is missing while ffmpeg is present, `FileNotFoundError` isn't in the except tuple and hits the identical masking bug. This is a partial regression of #4119's intent: `unified_loader.py` reimplements ffprobe logic instead of reusing the fixed version.
- **Suggested Fix**: Move `import json` to the top of the `try:`. More durably, delete the duplicate ffprobe invocation and call `ffmpeg_loader._probe_audio()`, removing the drift risk permanently.

#### ENG-D4-2: `get_audio_info()`'s channel count disagrees with what `load_audio()` decodes for mono FFmpeg sources
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:337-345` (hardcoded `-ac 2`) vs `auralis/io/unified_loader.py:246-251`
- **Status**: NEW
- **Description**: `load_with_ffmpeg()` always passes `-ac 2` regardless of source channels (`source_channels` is probed but only used in the log line). #3672 added this to fix 5.1/7.1 center-channel loss, but being unconditional it also duplicates a genuinely mono source into fake stereo. `get_audio_info()` meanwhile reports the true source channel count from ffprobe. The two functions of the same package disagree.
- **Evidence**: Reproduced with a genuine 1-channel MP3:
  ```python
  >>> get_audio_info(Path("mono.mp3"))['channels']   # 1
  >>> load_audio(Path("mono.mp3"))[0].shape          # (88200, 2), channels bit-identical
  >>> load_with_soundfile(Path("mono.wav"))[0].shape # (88200,) — real mono
  ```
- **Impact**: (1) Any caller sizing a buffer or making a mono/stereo decision from `get_audio_info()['channels']` is wrong for every mono FFmpeg-routed file — `chunked_processor._load_metadata()` sets `self.channels` straight from this field. (2) The same `load_audio()` call with default args returns 1-D for WAV/FLAC/AIFF/AU but 2-D for MP3/M4A/AAC/OGG/WMA/OPUS — the `(samples, channels)` contract depends on file extension, not content. Also doubles memory/CPU for mono files through FFmpeg for zero quality benefit.
- **Siblings**: None — `loader.py::load()` and `soundfile_loader.py` both correctly gate downmix on `n_channels > 2`.
- **Suggested Fix**: Use `'-ac', str(min(source_channels, 2))` so mono stays mono through the FFmpeg path exactly as it does through soundfile.

#### ENG-D5-2: Fingerprint queue's adaptive worker count desyncs from real threads, permanently stalling `on_drained`
- **Severity**: MEDIUM
- **Dimension**: Parallel Processing
- **Location**: `auralis/services/fingerprint_queue.py:178-215,239-258`; driven by `auralis/library/resource_monitor.py:112-157`
- **Status**: NEW
- **Description**: `start()` spawns exactly `initial_num_workers` threads and never spawns more — the count is fixed for the queue's life. `AdaptiveResourceMonitor` (on by default) polls RAM every 2 s and, whenever usage is under the 50 % scale-up threshold, increments `current_worker_count` and calls `_on_worker_count_change`, which sets `self.current_num_workers` — pure bookkeeping, no thread spawned. That same value is the completion threshold in `_on_worker_drained`: `self._drained_workers >= max(1, self.current_num_workers)`. `_drained_workers` is bounded at `2 * initial_num_workers` (each real worker contributes at most 2), so once the recommendation ratchets past the real thread count, the threshold is permanently unreachable.
- **Evidence**:
  ```python
  # fingerprint_queue.py:198-215
  self.current_num_workers = new_worker_count   # no thread spawned/killed
  info(f"... (Note: dynamic scaling requires worker pool restart)")
  ```
- **Impact**: `on_drained` (per #3479) drives reference-cloud refresh when fresh fingerprints land. On any machine under 50 % RAM (the common case) the callback stops firing within roughly `(max_workers - initial_num_workers) * 2` seconds of queue start — `max_workers` is 2× CPU count vs `min_workers` 0.5×, a 4× spread. No crash, no error: similarity/genre data just silently stops refreshing.
- **Suggested Fix**: Use `len(self.workers)` (the actual thread count) as the drain threshold, decoupled from the resource monitor's recommendation — or make the scaling real.

#### ENG-D7-A1: `TrackRepository.delete()` raises `IntegrityError` for any fingerprinted track, silently swallowed as `False`
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository.py:661-685`; `auralis/library/models/fingerprint.py:40,218-219`; `auralis/library/models/core.py:88-89`
- **Status**: NEW
- **Description**: `delete()` calls ORM-level `session.delete(track)`. `Track.fingerprint` and `Track.similar_tracks` point at `TrackFingerprint`/`SimilarityGraph`, whose `track_id` FKs are `nullable=False` with DB-level `ondelete='CASCADE'` — but neither relationship declares `passive_deletes=True`. Without it, SQLAlchemy's unit-of-work does not defer to the DB CASCADE; it loads the children and tries to NULL their FK first, which fails the NOT NULL constraint. The blanket `except Exception` reports it as an ordinary "delete failed".
- **Evidence**: Reproduced against the real models (in-memory SQLite, `PRAGMA foreign_keys=ON`):
  ```
  sqlite3.IntegrityError: NOT NULL constraint failed: track_fingerprints.track_id
  [SQL: UPDATE track_fingerprints SET track_id=?, updated_at=? WHERE track_fingerprints.id = ?]
  ```
  The Core-level bulk delete used in `cleanup_missing_files` / `RepositoryFactory.reset_library` does not hit this — bulk DELETE bypasses ORM relationship management and lets SQLite CASCADE work.
- **Impact**: `TrackRepository.delete()` / `LibraryManager.delete_track()` is the only "delete a track" implementation, and it would fail for virtually every track in a real library (background workers fingerprint everything). **Currently unreachable in production** — no REST endpoint or other caller invokes it today, and existing tests never populate a fingerprint first — which is why it is MEDIUM rather than HIGH. It breaks the moment the feature is wired up.
- **Siblings**: None — every other `session.delete(<obj>)` in the repo layer targets secondary-table associations or leaf objects.
- **Suggested Fix**: Add `passive_deletes=True` to `Track.fingerprint`, `Track.similar_tracks`, and the `SimilarityGraph.track` back-reference. Add a regression test that fingerprints a track before deleting it.

---

### LOW

#### ENG-D2-1: `auralis/core/config.py` is entirely dead — shadowed by the `auralis/core/config/` package
- **Severity**: LOW
- **Dimension**: DSP Pipeline (config duality)
- **Location**: `auralis/core/config.py` (whole file); shadowing package `auralis/core/config/__init__.py`
- **Status**: NEW
- **Description**: A module and a package of the same name are siblings in `auralis/core/`. Python resolves the package, so `import auralis.core.config` always binds to `config/__init__.py` — never to `config.py`. Verified: `c.__file__` resolves to the package; `c.LimiterConfig`/`c.UnifiedConfig` both come from the package. A repo-wide grep finds zero importers of the legacy module by any mechanism.
- **Impact**: No runtime impact — there is no active "two configs disagreeing" bug. The risk is maintenance: a contributor editing "the config file" by filename search edits an unreachable copy and sees no effect. The shadowed file's `Config`/`LimiterConfig` disagree in defaults and types with the package versions.
- **Suggested Fix**: Delete `auralis/core/config.py`, or rename it (e.g. to a `legacy_matchering_config` module) so the collision is resolved intentionally rather than by import-resolution accident.

#### ENG-D2-2: `AdaptiveConfig.critical_bands` is validated but never wired to the actual band count
- **Severity**: LOW
- **Dimension**: DSP Pipeline (config duality)
- **Location**: `auralis/core/config/settings.py:65,73`; `auralis/dsp/eq/critical_bands.py:27-43`; `auralis/dsp/eq/psychoacoustic_eq.py:95`
- **Status**: NEW
- **Description**: `AdaptiveConfig` exposes `critical_bands: int = 26` with a validated `8 <= x <= 64` range, appearing to be a tunable EQ-resolution setting. `PsychoacousticEQ.__init__` always calls `create_critical_bands()` with no arguments, which always returns exactly 25 fixed Bark-scale bands. The field is never read outside its own `__post_init__` assert, and its default (26) doesn't even match the real band count (25).
- **Impact**: Silent no-op for anyone adjusting the value. No current UI exposes it, so present user-facing impact is nil.
- **Siblings**: None — all other `AdaptiveConfig` fields are genuinely consumed.
- **Suggested Fix**: Either thread `config.adaptive.critical_bands` into `create_critical_bands(num_bands=...)`, or remove the field and document the band count as an engine constant.

#### ENG-D2-3: Realtime-streaming EQ path applies block FFT gain with no window or overlap-add
- **Severity**: LOW (would be HIGH if reachable — see Impact)
- **Dimension**: DSP Pipeline (windowing / WOLA)
- **Location**: `auralis/dsp/realtime_adaptive_eq/realtime_eq.py:132-148`; `auralis/dsp/eq/filters.py:63-118`
- **Status**: NEW
- **Description**: The offline path (`EQProcessor._process_with_psychoacoustic_eq`, `auralis/core/processing/eq_processor.py:152-222`) correctly wraps `process_realtime_chunk` in a fixed 50 %-hop WOLA loop with a full-Hann synthesis window (COLA-correct, per the #4217 fix — verified still present). `RealtimeAdaptiveEQ._process_fixed_chunk` instead calls `apply_eq()` directly per block, with **no window and no overlap-add**. `apply_eq_mono` is documented as intentionally un-windowed with overlap-add expected at the chunk level — but this caller never adds that layer. Consecutive blocks get independently-adapted gains with no window to smooth the seam.
- **Impact**: If reached, audible clicking/spectral smearing every ~20 ms whenever adaptive gains are non-flat. However `HybridProcessor.process_realtime_chunk()` — the only caller of this chain — has **zero production callers**; the real streaming path goes through the offline `HybridProcessor.process()` → `ContinuousMode`/`AdaptiveMode` → `EQProcessor` WOLA path. Exercised only by tests today, hence LOW.
- **Suggested Fix**: Either route it through the same WOLA scheme `EQProcessor` uses, or document explicitly that the path is reserved/dead so a future integration doesn't wire it up assuming WOLA safety.

#### ENG-D3-2: `GaplessPlaybackEngine.cleanup()` reads `prebuffer_thread` without the lock that guards its creation
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:377-392` (cleanup) vs `:70-93` (start_prebuffering)
- **Status**: NEW
- **Description**: `start_prebuffering()` assigns `self.prebuffer_thread` only under `_thread_lock`. `cleanup()` sets `_shutdown` then reads `self.prebuffer_thread` **without** the lock. If a caller invokes `start_prebuffering()` in the window between its own `_shutdown.is_set()` check and `cleanup()`'s set-and-read, a new non-daemon thread can be assigned after `cleanup()` already read the old value, outliving cleanup unjoined. `enhanced_audio_player.cleanup()` explicitly guards exactly this for `_advance_thread` (comments at `enhanced_audio_player.py:711-716`, per #3694/#4227), but the discipline was never applied here.
- **Impact**: Narrow — requires a track-load API call concurrent with `player.cleanup()`, not a normal pattern in single-user desktop use. Worst case a stray prebuffer thread outlives cleanup; no audio corruption. Existing tests cover only the sequential cases.
- **Suggested Fix**: Read `self.prebuffer_thread` under `_thread_lock`, join outside the lock — mirroring the `_advance_thread` pattern.

#### ENG-D3-3: `RealtimeProcessor.is_processing` is set once and never updated
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/realtime/processor.py:42`
- **Status**: NEW
- **Description**: Set to `False` in `__init__` and never read or written anywhere else (`grep -rn "\.is_processing\b" auralis/ auralis-web/` returns only the assignment). The only consumer is a test asserting `hasattr`.
- **Impact**: Dead/misleading state — future code reading it expecting live status always gets `False`.
- **Suggested Fix**: Remove it, or wire it to toggle around `process_chunk()`'s body under `self.lock`.

#### ENG-D5-3: The entire `auralis/optimization/parallel/` package is unreachable from production
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel/band_processor.py`, `auralis/optimization/parallel/feature_extractor.py`, `auralis/optimization/parallel/audio_processor.py`, `auralis/optimization/parallel/decorators.py`, and transitively `auralis/analysis/parallel_spectrum_analyzer.py`
- **Status**: NEW
- **Description**: Grepping every production call site (excluding the package's internals and `tests/`) finds **zero** callers of `ParallelBandProcessor.process_bands_parallel`, `ParallelFeatureExtractor.extract_features_parallel`, `ParallelAudioProcessor.process_batch`, `@parallelize`, or `ParallelSpectrumAnalyzer`. The only reachable-by-instantiation class is `ParallelFFTProcessor`, whose sole caller (`ParallelSpectrumAnalyzer.analyze_file`) is itself dead.
- **Impact**: No runtime impact (dead code can't corrupt audio) — a maintenance finding. It directly explains why open issues #4506 and #4502 are scoped "latent only", and it means fixes for #2314/#2526/#3355/#3430/#3439/#3673-#3675/#3699/#3745/#3760-#3762/#3791/#4125/#4229 have accrued on code nothing calls.
- **Suggested Fix**: Wire it into a real caller (if the intended spectrum-analysis speedup is still wanted) or delete the unused surface and close #4506/#4502 as moot.

#### ENG-D5-4: Stale hardcoded "/3" in the fingerprint worker debug log
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/services/fingerprint_queue.py:378-380`
- **Status**: NEW
- **Description**: The log and comment claim "Only 3 workers can process audio simultaneously", but `processing_semaphore` is `ResizableSemaphore(max(8, max_workers))` (`fingerprint_queue.py:122-124`) — at least 8, usually more.
- **Impact**: Cosmetic; misleading debug output only.
- **Suggested Fix**: Use `self.processing_semaphore.capacity` instead of the literal `3`.

#### ENG-D7-A2: `SidecarManager.write()` writes the `.25d` sidecar non-atomically
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/sidecar_manager.py:166-211`
- **Status**: NEW (independent sibling of #4508, which covers a different file)
- **Description**: `write()` opens the destination `<audiofile>.25d` in `'w'` mode and streams `json.dump()` — no temp file, no `os.replace()`. This is a separate path and separate on-disk file from #4508 (`FingerprintStorage.save()`, which writes to `~/.auralis/fingerprints/<hash>.25d`). `SidecarManager` writes portable sidecars next to the source audio and is used in production: `auralis/services/fingerprint_extractor.py` constructs it with `use_sidecar_files=True` by default and calls `write()` after every extraction.
- **Impact**: Low — `read()`/`is_valid()` catch `JSONDecodeError`/`OSError` and treat a torn file as a cache miss, so the worst case is a wasted re-extraction, not corruption.
- **Suggested Fix**: Write to a `NamedTemporaryFile` in the same directory and `os.replace()` onto the final path, matching #4508's prescribed fix.

#### ENG-D7-A3: `Genre.to_dict()` accesses `len(self.tracks)` uncaught, with no eager-load in `GenreRepository`
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/models/core.py:280-291`; `auralis/library/repositories/genre_repository.py`
- **Status**: NEW
- **Description**: `Genre.to_dict()` unconditionally does `'track_count': len(self.tracks)`. Every `GenreRepository` method returning a `Genre` expunges it without loading `Genre.tracks` (no `selectinload`/`joinedload` anywhere in the file). Unlike `Track.to_dict()`'s equivalent gap (fixed as #4500), `Genre.to_dict()` has no `try/except`, so `DetachedInstanceError` would propagate.
- **Impact**: **Currently dead code** — there is no genre router in the backend and nothing calls `Genre.to_dict()`. Latent until wired.
- **Siblings**: None — `album_repository.py` and `artist_repository.py` both eager-load consistently.
- **Suggested Fix**: Add `selectinload(Genre.tracks)` to `GenreRepository`'s read paths, or guard the `track_count` access the way `Track.to_dict()` already does.

---

## Relationships

**Shared root cause — duplicate implementations that drifted** (the largest cluster; 5 findings):
- ENG-D6-2, ENG-D6-3, ENG-D4-1 are all *incomplete fixes*: the correct change was made in one of two/three copies of the same logic and the siblings were missed.
- ENG-D6-1 and ENG-D4-1/ENG-D4-2 are all cases where two implementations of the same operation (fingerprint windowing, ffprobe invocation, channel-count reporting) disagree.
- ENG-D6-4 is the Rust-side instance of the same shape: a second, worse tempo/onset implementation alongside the good one.
- Fixing the *duplication* rather than each symptom is the durable move, and matches the project's DRY principle.

**Shared root cause — unreachable code accumulating fixes** (3 findings): ENG-D5-3, ENG-D2-3, and the noted-but-unscored `MemoryPool` `id()` hazard. All are hardened, tested, actively-patched code with zero production callers. Open issues #4506 and #4502 sit inside this cluster.

**Shared shape — silent wrong output** (ENG-D5-1, ENG-D3-1, ENG-D5-2, ENG-D6-1, ENG-D7-A1): each fails without an exception, a log line, or a user-visible signal. None would be caught by monitoring; all require a targeted test to detect.

**Interaction**: ENG-D6-1 (batch path wins the fingerprint race) amplifies ENG-D6-2 (parameter tuning reads an inflated centroid) — the recording-type detector consumes the DB-cached fingerprint, so both errors compound in the same mastering decision.

**Non-interaction worth noting**: ENG-D5-1's cache and the default playback path are disjoint. Normal listening is unaffected; only explicit `hybrid`-mode processing jobs are at risk.

---

## Prioritized Fix Order

1. **ENG-D5-1** (HIGH) — wrong audio delivered to the user with no error is the worst outcome in this report, and the fix is small and local (stop keying the cache on `repr()` of arrays, or stop caching an impure method). Fix first.
2. **ENG-D3-1** (HIGH) — silent user-data loss on a fully-wired, trivially-reachable UI path. One-line invalidation fixes it.
3. **ENG-D6-2** (MEDIUM) — three-line fix completing an already-designed correction; affects every mastering pass today.
4. **ENG-D4-1** (MEDIUM) — one-line `import json` move restores diagnosability for every corrupt-file report; do the `_probe_audio()` consolidation in the same change to close the drift.
5. **ENG-D6-3** (MEDIUM) — one-line reset restoring the continuous pipeline's only automated regression check.
6. **ENG-D7-A1** (MEDIUM) — `passive_deletes=True` plus a regression test. Unreachable today, so not urgent, but it is a landmine under any future "delete track" feature and costs minutes to defuse.
7. **ENG-D5-2** (MEDIUM) — swap the drain threshold to `len(self.workers)`; restores reference-cloud refresh.
8. **ENG-D4-2** (MEDIUM) — `-ac min(source_channels, 2)`; verify no downstream code depends on the accidental always-stereo behavior before changing.
9. **ENG-D6-1** (MEDIUM) — larger change (unify two fingerprint paths) and it invalidates existing fingerprints, so it wants a dedicated session with a re-fingerprint migration plan.
10. **ENG-D6-4** (MEDIUM) — Rust change requiring `maturin develop` rebuild; high payoff for scan times but no correctness impact, so schedule with other Rust work (e.g. #4123).
11. **LOW cluster** — opportunistic. Group ENG-D5-3 + ENG-D2-3 into one "delete or wire up dead parallel/realtime paths" decision, which also lets #4506 and #4502 be closed as moot. ENG-D2-1/ENG-D2-2 are config cleanups; ENG-D3-2/ENG-D3-3/ENG-D5-4/ENG-D7-A2/ENG-D7-A3 are each small standalone fixes.

---

## Verified Clean (highlights)

Substantial surface was traced and confirmed correct. Notably:

- **Sample integrity (Dimension 1): zero findings.** Sample-count asserts hold at every stage and are not stripped in the shipped build (`auralis-backend.spec` sets `optimize=0`). Copy-before-modify holds across all of `auralis/core/stages/`, including the new `mastering_branches/` from `211cfaba`. Every `sosfiltfilt`/`filtfilt` call site casts float64 back to input dtype. NaN containment checkpoints per #4099 are present in every branch. Clipping to `[-1, 1]` happens before every sink write.
- **WOLA/COLA correctness** (#4217) and **EQ band mapping by frequency, not index** (`2b3c5b35`) both verified still correct, with the regression test still targeting them.
- **Rust PyO3 boundary**: every `#[pyfunction]` wraps compute in `py.allow_threads(|| catch_unwind(...))` — GIL released, panics converted to `PyRuntimeError`.
- **Player lock discipline**: callbacks are dispatched outside locks everywhere; `_position_lock → _audio_lock` ordering has no reversal; the #4495/#4328 `record_track_completion()` fix holds; DB sessions are always closed before player locks are taken.
- **FFmpeg cancellation** (#4496): `Popen` + SIGTERM→SIGKILL escalation verified intact, no zombie risk, no temp-file leak on `CancelledError`.
- **Executor lifecycle**: every `ThreadPoolExecutor`/`ProcessPoolExecutor` in `auralis/` is context-managed — no pool leaks anywhere.
- **Database**: no SQL injection (whitelist-validated identifiers); WAL + `busy_timeout` + `pool_pre_ping` + `foreign_keys=ON` consistent across both engines; migration file-locking, double-check, and fail-fast backup all intact; `cleanup_missing_files` cursor pagination (`bd94fd59`) and engine disposal (`8adb8d0a`) both still present; ~130 hand-rolled session call sites all close correctly.
- **Fingerprint determinism**: pure function of `(audio, sr)`; the previously-unseeded `np.random.normal` in `genre_weights.py` now uses a fixed-seed generator; all three call sites agree on the same 25 dimension names; ML classifier is `@lru_cache(maxsize=1)`-wrapped (#2528).

### Hypotheses investigated and disproven

- `python -O` stripping the engine's safety asserts in the packaged desktop build — disproven (`optimize=0`).
- `AudioPlayer.stop()`'s unlocked `_auto_advancing.clear()` reopening the #3434/#3718 double-advance race — disproven (`_stop_requested` is set first and independently gates every advance thread).
- A separate Python streaming fingerprint analyzer diverging from the Rust batch one — disproven (both funnel into one Rust call; only the windowing differs, which is ENG-D6-1).

### Deduped, not re-reported

Confirmed still OPEN and skipped: #4502, #4503, #4504, #4505, #4506, #4507, #3878, #3735, #3782, #4334, #4312, #4311, #4509, #4510, #3762, #4508.
Confirmed still FIXED (no regression): #4494, #4495/#4328, #4496, #4500, #4501, #4404, #4217, #4216, and the `bd94fd59` / `8adb8d0a` / `2b3c5b35` fixes.

### Out-of-scope observation

`quick_build.sh:104` invokes `python build_auralis.py`, a file that does not exist in this repo — a broken legacy build entry point. Build-tooling debt, not an engine finding; noted so it isn't lost.

---

*Fresh audit, 7 dimensions, deep depth. Report generated 2026-07-25.*
