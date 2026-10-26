---
description: "Deep audit of the core audio engine — DSP pipeline, player, chunked mastering, analysis, library"
argument-hint: "[--focus <dimensions>] [--depth shallow|deep] [--limit <N>]"
---

# Audio Engine Audit

Perform a deep audit of the Auralis core audio engine — DSP pipeline, player, analysis, library.

**Architecture**: This is an orchestrator. Each dimension runs as an Agent-tool subagent (`subagent_type: general-purpose`, `model: sonnet`). Max 3 run concurrently.

See `.claude/commands/_audit-common.md` for project layout, severity framework, methodology, context management rules, deduplication, and finding format.

## Parameters (from $ARGUMENTS)

- `--focus <dimensions>`: Comma-separated dimension numbers or names (e.g., `1,3` or `sample-integrity,player`). Default: all 7.
- `--depth shallow|deep`: `shallow` = check key patterns only; `deep` = trace full call graphs. Default: `deep`.
- `--limit <N>`: Stop after N findings (useful for time-boxed audits). Default: unlimited.

## Scope

| Component | Path | Key Files |
|-----------|------|-----------|
| Core Pipeline | `auralis/core/` | The shipped app path: `hybrid_processor.py` + `hybrid_setup.py` → `processing/` (`HybridProcessor.process()` → `mode_dispatch.py` → `ContinuousMode`; the dynamics facade, *auralis/core/hybrid/* and *auralis/dsp/advanced_dynamics.py* were deleted in #6201 — `AdaptiveCompressor` survives, live in `player/realtime/auto_master.py`), plus `processors/`, `analysis/`, `dsp/`, `utils/`. The **offline CLI subsystem**: `simple_mastering.py` (+ `mastering_stage_delegates.py`, `StageDelegatesMixin`, #5838), the `mastering_*.py` modules, `mastering_branches/` and `stages/` (12 stage modules + the shared `hf_budget.py` helper). Its only non-test caller is the root `auto_master.py` CLI — kept on purpose (#4873): rate its findings as offline-tool bugs, not user-facing ones, and do not re-file it as dead code. |
| Continuous Processing | `auralis/core/processing/` | `continuous_space.py` (`ProcessingSpaceMapper`, `_smooth_unit`) + `continuous_space_types.py` (`ProcessingCoordinates` — the 3D space replacing discrete presets — `ProcessingParameters`, `PreferenceVector`; split out in #6272), `continuous_mode.py`, `adaptive_mode.py`, `hybrid_mode.py`, `parameter_generator.py`, `target_derivation.py`, `delta_eq.py`, `cross_dimensional_guard.py`, `base/`. See the Retired Architecture table in `_audit-common.md` — categorical branch classification is gone; do not report its absence. |
| Core Config | `auralis/core/config/` | `unified_config.py` (UnifiedConfig), `settings.py`, `preset_profiles.py` (only an `'adaptive'` entry since 2026-09-13 — see Retired Architecture), `genre_profiles.py`. This package is now the *only* config layer — the same-named legacy module was deleted in #4918, and the *factory.py* `create_*_config` helpers in #5770 (`d76026a4`), so there is no second construction path to reconcile. |
| DSP Modules | `auralis/dsp/` | `basic.py`, `eq/psychoacoustic_eq.py` + `eq/parallel_eq_processor/`, `dynamics/`, `utils/` |
| Player | `auralis/player/` | `enhanced_audio_player.py` (class `AudioPlayer`, composed from `player_callbacks_mixin.py`, `player_file_loading_mixin.py`, `player_properties_mixin.py`, `player_queue_navigation_mixin.py`, `player_streaming_mixin.py`, `fingerprint_loader_mixin.py`), `gapless_playback_engine.py` (+ `gapless_prebuffer.py`, `PrebufferMixin`), `queue_controller.py` (+ `queue_locked_state.py`, `queue_loading.py`), `playback_controller.py`, `integration_manager.py` (+ `integration_library.py`, `integration_reporting.py`), `realtime/` (`processor.py`, `auto_master.py`, `gain_smoother.py`, `level_matcher.py`, `performance_monitor.py`), `components/` (`queue_manager.py` + `queue_navigation.py` / `queue_shuffle.py`), `audio_file_manager.py`. The mixin splits are #5836. |
| Audio I/O | `auralis/io/` | `unified_loader.py` (loading) + `audio_probe.py` (`get_audio_info`, split out in #6273), `loader.py`, `loaders/` (`ffmpeg_loader.py` orchestrates `ffmpeg_probe.py` / `ffmpeg_process.py` (subprocess supervision, cancellation) / `ffmpeg_command.py` since #5835; `soundfile_loader.py`), `formats.py`, `processing.py`, `saver.py`, `results.py` |
| Chunked Mastering | `auralis/core/` | `mastering_chunk_loop.py`, `mastering_chunk_assembly.py` (chunk read, True Peak guard, crossfaded write region, `true_peak_4x`, `two_pass_correction_gain`; #5839, #5694), `mastering_process_chunk.py`, `mastering_prepare.py`, `mastering_notch_context.py`, `mastering_diagnostics.py`, `mastering_config.py` — the offline-CLI chunk loop (#4873) that replaced the deleted parallel processor (#4565) |
| Optimization (LIVE) | `auralis/optimization/` | `performance_optimizer.py` (the `get_performance_optimizer()` singleton) and `profiling/`. The cache, buffer-pool, SIMD and config pieces were deleted in #5769 (nothing drove them). **Live engine code — audit at full severity (#5142).** `auralis/core/hybrid_processor.py` calls `hybrid_setup.apply_module_optimizations()` at module-import time and that wraps `AdaptiveMode.process` in a profiling-only decorator, so it sits on every real mastering call. The production importer set is pinned by `scripts/check_optimization_importers.py`; the old "test-only, cap at LOW" instruction was false and suppressed findings. |
| Analysis | `auralis/analysis/` | `fingerprint/` (25D system), `ml/` (`feature_extractor.py` + `feature_extractor_mfcc.py`), `quality/`, `quality_assessors/` |
| Library | `auralis/library/` | `database.py` (`LibraryDatabase` — the sole composition root: migration, sessions, shutdown; since #5837 it delegates engine/pragma bootstrap to `database_engine.py`, scan slots and the destructive-operation flag to `scan_coordinator.py`, and repository accessors to `database_accessors.py`; the `LibraryManager` facade and its cache layer were deleted in #4915), `repositories/` (12 repos + `base.py` BaseRepository; track, album, playlist and fingerprint are split across mixin/helper files), `scanner/` (`scanner.py` + `scan_stages.py`, `file_discovery.py`), `models/`, `migrations/`, `migration_manager.py` (+ `migration_engine.py`, `migration_steps.py`, `migration_backup.py`, `pre_migration_backup.py`, `migration_lock.py`, `migration_versions.py`; schema v28), `sidecar_manager.py` (+ `sidecar_validation.py`), `artwork.py` (+ `artwork_tags.py`), `metadata_editor/`, `resource_monitor.py`, `path_key.py`, `fingerprint_quantizer.py` |
| Services | `auralis/services/` | `artwork_service.py` (+ `artwork_sources/`: `musicbrainz.py`, `lastfm.py`, `discogs.py`), `fingerprint_extractor.py`, `fingerprint_queue.py` + `fingerprint_queue_scaling.py` (adaptive sizing) / `fingerprint_worker.py` (execution), `resizable_semaphore.py` |
| Rust DSP | `vendor/auralis-dsp/` | PyO3 bindings in `vendor/auralis-dsp/src/py_bindings.rs` — 2 exposed functions: compute_fingerprint (live; its one Python adapter is `auralis/analysis/fingerprint/rust_fingerprint.py`) and process_chunks (no Python caller, #5738 open); the other nine bindings were removed in #5764 (`44e4d433`). Rhythm was ported in from the deleted standalone fingerprint server (#4533). |

Out of scope: React frontend, FastAPI backend (routing, WebSocket layer), Electron desktop. DO verify engine public API contracts.

## Severity Examples

| Severity | Engine-Specific Examples |
|----------|------------------------|
| **CRITICAL** | Sample count mismatch causing clicks/gaps, buffer corruption from missing copy, in-place modification of shared array, database corruption from concurrent writes |
| **HIGH** | Discontinuity at a mastering chunk seam, RLock deadlock in player, gapless transition audible gap, memory leak during extended playback |
| **MEDIUM** | Inconsistent dtype handling across stages, missing copy-before-modify in non-critical path, fingerprint accuracy degradation at edge cases |
| **LOW** | Redundant array copies hurting performance, sub-optimal FFT windowing, unused analysis metrics |

## Audit Dimensions

### Dimension 1: Sample Integrity

**Key files**: `auralis/core/hybrid_processor.py`, `auralis/core/simple_mastering.py`, all DSP modules

**Check**:
- [ ] `len(output) == len(input)` — verified at EVERY processing stage, not just the outer wrapper?
- [ ] `audio.copy()` before ANY in-place NumPy operation — no exceptions?
- [ ] dtype preservation — does audio stay `float32`/`float64` throughout? Any silent casts?
- [ ] Clipping prevention — is audio clamped to [-1.0, 1.0] before output? Inter-stage clipping?
- [ ] NaN/Inf propagation — can a NaN from one DSP stage corrupt the entire output? In-stage `validate_audio_finite(..., repair=True)` is bounded by `repair_max_fraction=MAX_IN_STAGE_REPAIR_FRACTION` (0.1%, `auralis/utils/audio_validation.py`, #6105): above it the stage must raise `ModuleError`, not zero the buffer into a silent cached chunk. Only the last-boundary writers (`io/saver.py`, `player/realtime/processor.py`) repair unconditionally.
- [ ] Mono/stereo handling — are mono files correctly handled through stereo pipelines?
- [ ] Bit depth output — does `auralis/io/results.py` (pcm16, pcm24) correctly scale and quantize?

### Dimension 2: DSP Pipeline Correctness

**Key files**: `auralis/core/hybrid_processor.py`, `auralis/core/processing/continuous_space.py` + `auralis/core/processing/continuous_space_types.py`, `auralis/core/processing/continuous_mode.py` + `auralis/core/processing/continuous_stages.py`, offline: `auralis/core/simple_mastering.py` + `auralis/core/mastering_process_chunk.py` / `auralis/core/mastering_chunk_loop.py` / `auralis/core/mastering_branches/`, `auralis/core/stages/`, `auralis/core/dsp/`, `auralis/dsp/eq/psychoacoustic_eq.py`, `auralis/dsp/dynamics/`

**Check**:
- [ ] Processing chain order — the shipped path's order is the `stages` list in `ContinuousStagesMixin._apply_dsp_stages` (`auralis/core/processing/continuous_stages.py`: EQ → dynamics → stereo width → normalization; the input-gain stage was dead and removed in #5576, `fd99dfae`), its single source of truth. Does anything run a stage outside that list or reorder it?
- [ ] Stage independence — does each stage receive clean input, or can a failed stage leave dirty state?
- [ ] Parameter validation — are gain, frequency, Q factor ranges validated before DSP math?
- [ ] Windowing — are FFT windows applied correctly? Double-windowing removed? (Fix: `cca59d9c`)
- [ ] Spectral leakage — are FFT sizes appropriate for the sample rate?
- [ ] Phase coherence — does multi-band processing maintain phase relationships?
- [ ] Sub-bass parallel path — correctly mixed back in? (Fix: `8bc5b217`)
- [ ] EQ band mapping — is the psychoacoustic EQ curve mapped to bands **by frequency**, not by raw index? An out-of-range index used to fall back silently to the simple EQ (fix `2b3c5b35`).
- [ ] WOLA overlap — the psychoacoustic path uses a fixed 50% hop with a full-Hann synthesis window. Any configurable-overlap change must re-derive COLA; flag if one was introduced without it.
- [ ] Parameter-space continuity — mastering is driven by continuous `ProcessingCoordinates` (spectral_balance, dynamic_range, energy_level) from `auralis/core/processing/continuous_space.py` (types in `continuous_space_types.py`). Does any consumer reintroduce a categorical step — a hard `if coord > X` threshold, a clamp that flattens the range, or a lookup table with discrete buckets? Two fingerprints that differ slightly must not produce audibly different mastering.
- [ ] Monotonicity — as one coordinate increases with the others fixed, do the derived parameters move monotonically, without plateaus or clipped ranges? Non-monotonic parameter generation makes mastering unpredictable across a catalog.
- [ ] Coordinate derivation — are the 3 axes computed from the 25D fingerprint with bounded, finite math? `_smooth_unit()` uses `tanh` to map unbounded measurements into (0, 1) — check every axis actually routes through a bounded mapping and cannot emit NaN/Inf from a degenerate fingerprint.
- [ ] Config reachability — a parameter defined in `auralis/core/config/unified_config.py` must actually be read on the path that claims to honor it. Trace from the definition to the DSP call site; a parameter with no reader is dead config, and a DSP stage with a hardcoded value that shadows a config field is the inverse bug. The same applies to `ProcessingParameters`: every field needs a `ContinuousMode` stage reader or a place in `REPORTING_ONLY_FIELDS` (`continuous_space_types.py`, pinned by `tests/auralis/core/test_processing_parameters_have_readers_5576.py`; the generated compression threshold/attack/release are reporting-only by design). (The old "legacy `config.py` vs package" duality is gone — that module was deleted in #4918.)
- [ ] Optimizer wrapper — `auralis/optimization/performance_optimizer.py` wraps `AdaptiveMode.process` at import time. Does the wrapper preserve the return value, exceptions and sample count exactly, and are the singleton and its profiler (`auralis/optimization/profiling/`) safe when concurrent backend chunk workers call through it? This is live DSP code (#5142), not test-only tooling.
- [ ] Preset tables — `PreferenceVector.from_preset_name` in `auralis/core/processing/continuous_space_types.py` and `create_preset_profiles` in `auralis/core/config/preset_profiles.py` now carry only `'adaptive'`. An unknown or legacy name must degrade to the neutral vector / `None` without raising. Flag any engine table that still defines a removed preset — except `auralis/core/analysis/spectrum_mapper/preset_anchors.py`, whose anchors are content calibration, not a user menu.
- [ ] Rust DSP boundary — the only live binding is `compute_fingerprint` (analysis, not audio output). Does `auralis/analysis/fingerprint/rust_fingerprint.py` handle its errors and map its dict to the schema correctly?
- [ ] GIL handling — does Rust code release the GIL during compute? Can concurrent calls corrupt state?

### Dimension 3: Player State Machine

**Key files**: `auralis/player/enhanced_audio_player.py`, `auralis/player/gapless_playback_engine.py` + `auralis/player/gapless_prebuffer.py`, `auralis/player/queue_controller.py` + `auralis/player/queue_locked_state.py`, `auralis/player/playback_controller.py`, `auralis/player/realtime/`, `auralis/player/components/`, `auralis/player/audio_file_manager.py`

**Check**:
- [ ] State transitions — are play/pause/stop/seek transitions atomic under RLock?
- [ ] Position invariant — can `position > duration` ever occur? During seek?
- [ ] Queue bounds — can index go out of bounds during skip/previous/remove?
- [ ] Gapless transitions — is the next track pre-loaded? Race between load and play?
- [ ] Callback safety — are callbacks invoked outside the lock to prevent deadlock?
- [ ] Resource cleanup — does stop() release file handles, audio buffers, threads?
- [ ] Real-time processor lifecycle — started/stopped atomically with playback? The chain follows the loaded track's sample rate: `get_audio_chunk` passes `file_manager.sample_rate` each chunk and `AutoMasterProcessor.set_sample_rate()` rebuilds the compressor/transient enhancer on change, including gapless swaps (#5729, pinned by `tests/auralis/player/test_realtime_track_sample_rate_5729.py`). A rate-dependent stage built once for `config.sample_rate` is a regression.
- [ ] Can `stop()` race with `play()` leaving player in undefined state?
- [ ] Mixin composition — `AudioPlayer` is assembled from the `player_*_mixin.py` files plus `fingerprint_loader_mixin.py`; since #5836 `QueueController` (`QueueLockedStateMixin`, `QueueLoadingMixin`), `QueueManager` (`QueueNavigationMixin`, `ShuffleMixin`), `GaplessPlaybackEngine` (`PrebufferMixin`) and `IntegrationManager` (`LibraryLoadingMixin`, `PlaybackReportingMixin`) are mixin-composed too. Do all of them mutate shared state under their host's lock, or does one mixin touch position/queue/prebuffer fields unlocked? Host hooks a mixin calls are typed as bare class-level `Callable` annotations, never `raise NotImplementedError` stubs that would shadow a sibling mixin in the MRO (#6235).

### Dimension 4: Audio I/O

**Key files**: `auralis/io/unified_loader.py`, `auralis/io/loaders/ffmpeg_loader.py` + `auralis/io/loaders/ffmpeg_process.py` / `auralis/io/loaders/ffmpeg_probe.py` / `auralis/io/loaders/ffmpeg_command.py`, `auralis/io/results.py`

**Check**:
- [ ] Format coverage — MP3, FLAC, WAV, AAC, OGG, OPUS, M4A all tested?
- [ ] Corrupt file handling — crash vs meaningful error on corrupt header?
- [ ] Large file handling — files > 1GB without OOM?
- [ ] Sample rate detection — always from metadata, never assumed?
- [ ] Channel handling — files with > 2 channels downmixed correctly?
- [ ] FFmpeg subprocess — properly terminated on cancellation? Zombie risk?
- [ ] File path safety — paths validated before passing to FFmpeg?
- [ ] Metadata extraction — ID3/Vorbis/FLAC tags parsed robustly? Malformed tags?

### Dimension 5: Chunked Mastering Loop

**Key files**: `auralis/core/mastering_chunk_loop.py`, `auralis/core/mastering_chunk_assembly.py`, `auralis/core/mastering_process_chunk.py`, `auralis/core/mastering_prepare.py`, `auralis/core/mastering_config.py`, `auralis/core/simple_mastering.py`

This dimension replaced the old "Parallel Processing" one: *auralis/optimization/parallel_processor.py* and its *parallel/* package were deleted as unreachable in #4565. The chunk model now lives in the engine's sequential overlap-and-crossfade mastering loop and in the backend's concurrent chunk processor (the latter belongs to `/audit-backend`, not here). Do not report the deleted processor's absence. The engine loop belongs to the offline CLI subsystem (#4873): it streams `CHUNK_DURATION_SEC` chunks from the file, each read with `CROSSFADE_DURATION_SEC` of overlap, renders each independently, and joins them with an equal-gain raised-cosine crossfade (`assemble_write_region`, #4966). `process_chunks` renders twice since #5694 (`8d0252a0`): pass one runs the identical loop with no sink and measures the final post-guard, post-crossfade sample peak and 4x true peak, then `two_pass_correction_gain` derives one uniform gain (≤ 1) applied in pass two, so the write clamp is no longer the only protection against hard clipping (pinned by `tests/auralis/core/test_offline_file_gain_postchain_5694.py`). Severity examples above apply at offline-tool weight.

**Check**:
- [ ] Chunk independence — does each iteration get a true copy, or a view into the caller's buffer that a later stage mutates in place?
- [ ] Seam settling — the transient shaper and loudness limiter restart their envelopes fresh on every chunk *by design*; seam continuity relies on the crossfade outlasting their settle time, which `SimpleMasteringConfig.__post_init__` enforces (#5339, `3edbd9f2`). Flag a new per-chunk-stateful stage whose time constant is not in that check, or a switch to an equal-power (sin/cos) crossfade, which bulges +3 dB on this correlated overlap (#4966).
- [ ] Reassembly — `sum(chunk_lengths) == total_length`, and chunks are concatenated in index order, never arrival order?
- [ ] Boundary continuity — is the seam between consecutive chunks free of discontinuity? Two identical inputs mastered whole vs chunked should match within float tolerance.
- [ ] Partial failure — one chunk raising must not silently drop audio or leave the carried context poisoned for the remainder.
- [ ] Analysis scope — are per-chunk measurements (loudness, crest, spectral balance) computed against the whole-track target, not re-derived per chunk? Re-deriving makes mastering drift across a long track.
- [ ] Rust `process_chunks` — it has no Python caller (#5738, open: dead code that returns silent zeros or aborts when overlap ≥ chunk size). A finding against it is a duplicate of #5738 unless a caller has appeared.
- [ ] Two-pass determinism — the measurement pass must reproduce the render exactly (it relies on the pipeline carrying no cross-chunk DSP state beyond `_notches`, written once per file); a new cross-chunk-stateful stage breaks the measured correction. The correction must stay one constant per file, or the macro-dynamics invariant of #5559 (a quiet movement is not lifted to the loudest section's level) breaks.
- [ ] Last chunk — a short final chunk must not be zero-padded into the output (added samples) or dropped (missing samples).

### Dimension 6: Analysis Subsystem

**Key files**: `auralis/analysis/fingerprint/` (`rust_fingerprint.py`, `windowed_compute.py`), `auralis/analysis/ml/`, `auralis/analysis/quality/`, `auralis/analysis/quality_assessors/`, `auralis/analysis/loudness_meter.py` + `auralis/analysis/loudness_filters.py`, `auralis/analysis/dynamic_range.py` + `auralis/analysis/dynamic_range_dynamics.py`

**Check**:
- [ ] Fingerprint determinism — same file always produces same fingerprint? The central `.25d` cache (`auralis/analysis/fingerprint/fingerprint_storage.py`) stamps `fingerprint_version` on `save()` and `load()` refuses a missing or older stamp (#5697); `save()` refuses to write without a real sample rate and duration instead of defaulting to 44100/0.0 (#6231). Flag a reader or writer of `.25d` files that bypasses it.
- [ ] Resource bounds — pathological files (silence, noise, 6hr podcast) bounded in CPU/memory?
- [ ] Batch vs streaming — both analysis paths produce identical results?
- [ ] ML model lifecycle — loaded once and reused, not reloaded per-track? Genre-classifier features must use the real sample rate (#5244), the engine's samples×channels layout when downmixing (#5746) and windows spread over the whole track (#6142), not the first seconds or an assumed 44.1 kHz.
- [ ] Quality metrics — LUFS, dynamic range, distortion correctly computed?
- [ ] Thread safety — concurrent analysis tasks don't interfere?
- [ ] KeyboardInterrupt — analysis can be interrupted cleanly? (Fix: `53cef6b4`)

### Dimension 7: Library & Database

**Key files**: `auralis/library/database.py` + `auralis/library/database_engine.py`, `auralis/library/scan_coordinator.py`, `auralis/library/repositories/`, `auralis/library/models/`, `auralis/library/scanner/`, `auralis/library/migrations/`, `auralis/library/migration_manager.py`, `auralis/library/migration_lock.py`, `auralis/library/sidecar_manager.py`, `auralis/library/resource_monitor.py`

**Check**:
- [ ] Repository pattern — ALL database access via the 12 repository classes? No raw SQL?
- [ ] Detached ORM instances — repositories `expunge()` what they return, so any relationship a query did not eager-load raises `DetachedInstanceError` when `to_dict()` touches it. Do read paths carry `selectinload()`, and does `to_dict()` go through `_safe_collection()` / `_safe_scalar()` in `auralis/library/models/_helpers.py`? `refresh()` expires without re-applying query options — post-commit paths must touch the relationship while still attached.
- [ ] `BaseRepository._session_scope()` (`auralis/library/repositories/base.py`) — every repository goes through it (migration finished in #4604/#5202), and since #5117 it rolls back on any escaping exception, so a per-method `except: rollback()` is redundant. Swallow-and-log write paths use `BaseRepository._guarded(message)` (logs once at ERROR, rolls back via the scope, returns the method's default) and get-one/list reads use `_first_detached` / `_all_detached` (`expunge_all()`, so eager-loaded relatives detach too; #6212, `c5690a73`, pinned by `tests/auralis/library/test_repository_guarded_6212.py`). Flag a new hand-rolled `get_session()` or `except Exception` + `rollback()` in a repository, a per-item `expunge(obj)` on a read that eager-loads relationships, and a method that catches its own failure and returns objects still attached (the #2624 hazard the scope's docstring names). A failure is still indistinguishable from not-found for callers (#5940).
- [ ] Dropped columns — migrations v26-v28 (#5755) dropped the never-populated `tracks` columns `fingerprint_status`/`_computed_at`/`_error_message`/`_vector`, `bit_depth`, `bitrate`, `peak_level`, `rms_level` and `lufs_level`, plus `file_hash`, the `tracks.fingerprint_*` indexes and the `library_stats` table/`LibraryStats` model. Flag any repository, `to_dict()` or API field that reads or writes them again; fingerprint status lives in `track_fingerprints`.
- [ ] SQLite config — `check_same_thread=False`, `pool_pre_ping=True` set?
- [ ] N+1 queries — list operations use `selectinload()`?
- [ ] Scanner robustness — symlinks, permission errors, Unicode filenames handled?
- [ ] Migration safety — can run while app is serving requests? (Uses file locking)
- [ ] Concurrent scans — two scan operations can't conflict? Slot and path-reservation accounting lives in `auralis/library/scan_coordinator.py`; `LibraryScanner` calls it directly, with no `except AttributeError` fail-open wrapper, since #5802 (`446edc4c`, pinned by `tests/auralis/library/test_scanner_guards_fail_closed_5802.py`). A reintroduced swallow around the guard is a regression.
- [ ] Cleanup — `cleanup_missing_files` (`auralis/library/repositories/track_repository_maintenance.py`) handles large libraries without OOM? (Fix: `bd94fd59`) Does it treat only `ENOENT`/`ENOTDIR` as "gone" (`_file_is_definitely_missing`), so an unreadable folder or dead mount cannot prune tracks, playlist rows and play counts (#5698, `16e0aab0`, pinned by `tests/auralis/library/test_cleanup_unreadable_folder_5698.py`)?
- [ ] Engine disposal — SQLAlchemy engine disposed on close? (Fix: `8adb8d0a`)

## Phase 1: Setup

1. Parse `$ARGUMENTS` for `--focus`, `--depth`, `--limit`
2. `mkdir -p /tmp/audit/auralis/engine`
3. Fetch dedup baseline: the canonical dump from `_audit-common.md` Deduplication step 1 (`--limit 100000` + truncation assertion), redirected to `/tmp/audit/auralis/engine/issues.json`
4. Scan `docs/audits/` for prior engine audit reports

## Phase 2: Launch Dimension Agents

Launch one Agent-tool subagent per dimension (max 3 concurrent). Each agent writes its output to `/tmp/audit/auralis/engine/dim_<N>.md`.

Every agent prompt MUST include:
- The project root is `/mnt/data/src/matchering`
- The depth parameter value
- The limit parameter value (if set)
- Reference to dedup file: `/tmp/audit/auralis/engine/issues.json`
- The context management rules from `_audit-common.md`
- The per-finding format below

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Sample Integrity | DSP Pipeline | Player State | Audio I/O | Chunked Mastering | Analysis | Library & Database
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet or exact call path
- **Impact**: What breaks — audio artifacts, crashes, data loss
- **Suggested Fix**: Brief direction (1-3 sentences)
```

Dimension → Output mapping:
- Dimension 1 (Sample Integrity) → `/tmp/audit/auralis/engine/dim_1.md`
- Dimension 2 (DSP Pipeline) → `/tmp/audit/auralis/engine/dim_2.md`
- Dimension 3 (Player State) → `/tmp/audit/auralis/engine/dim_3.md`
- Dimension 4 (Audio I/O) → `/tmp/audit/auralis/engine/dim_4.md`
- Dimension 5 (Chunked Mastering) → `/tmp/audit/auralis/engine/dim_5.md`
- Dimension 6 (Analysis) → `/tmp/audit/auralis/engine/dim_6.md`
- Dimension 7 (Library & Database) → `/tmp/audit/auralis/engine/dim_7.md`

## Phase 3: Merge

1. Read all `/tmp/audit/auralis/engine/dim_*.md` files
2. Combine into `docs/audits/AUDIT_ENGINE_<TODAY>.md` with structure:
   - **Executive Summary** — Total findings by severity, key themes, most impactful issues
   - **Findings** — Grouped by severity (CRITICAL first), deduplicated across dimensions
   - **Relationships** — How findings interact, shared root causes
   - **Prioritized Fix Order** — What to fix first and why
3. Remove cross-dimension duplicates (same file:line found by multiple dimensions)

## Phase 4: Cleanup

1. `rm -rf /tmp/audit/auralis/engine`
2. Inform user the report is ready
3. Suggest: `/audit-publish docs/audits/AUDIT_ENGINE_<TODAY>.md`

## Labels

Use labels when publishing: severity label + domain labels (`audio-integrity`, `dsp`, `player`, `library`, `fingerprint`, `performance`) + `bug`
