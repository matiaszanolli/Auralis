# Architecture: Module Map

A file-level guide to where things live. Use it to find the right directory before opening a
[subsystem doc](../subsystems/). The tree is the authority: when a name here and `git ls-files`
disagree, the tree wins. Files are grouped by role, not listed exhaustively; test files
(`__tests__/`, `*.test.*`) are omitted throughout.

Many modules are split into a coordinator plus sibling modules (`chunk_*.py`, `*_mixin.py`,
`*_deps.py`, `*_models.py`). The split files are named for what they own, so a prefix is usually
enough to find a family. See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) for the convention.

---

## Top level

```
matchering/
├── auralis/              Core Python engine (audio, analysis, library, player)
├── auralis-web/
│   ├── backend/          FastAPI REST + WebSocket (:8765)
│   └── frontend/         React + TypeScript + Vite + Redux
├── vendor/auralis-dsp/   Rust crate, built to the Python module auralis_dsp (PyO3)
├── desktop/              Electron shell
├── tests/                16 tracked subdirectories (counts: scripts/check_doc_counts.py)
├── scripts/              Repo tooling: CI baselines, doc-count and path gates, benches
├── tools/                Alembic config and validation scripts
├── docs/                 This documentation (docs/archive and docs/audits are history)
├── auto_master.py        Offline mastering CLI (see "Offline mastering" below)
├── launch-auralis-web.py Browser-preview launcher; `pnpm run dev` starts Electron
└── sync_version.py       Propagates auralis/version.py to every package manifest
```

---

## `auralis/` core engine

### `auralis/core/` : processing pipeline

The live path is `HybridProcessor` to `ContinuousMode`. Everything under "Offline mastering" is a
separate subsystem.

- `auralis/core/hybrid_processor.py` : `HybridProcessor`, the thread-safe entry point; `process()`
  validates input and dispatches by mode. Support: `auralis/core/hybrid_setup.py` (component
  construction), `auralis/core/hybrid_stage_dispatch.py` (input validation, reference-mode stages),
  `auralis/core/hybrid_processor_singleton.py` (module-level convenience API).
- `auralis/core/processing/` : the mode processors and the continuous-space machinery.
  - Modes: `mode_dispatch.py`, `adaptive_mode.py`, `continuous_mode.py` (the live adaptive engine),
    `hybrid_mode.py`; `auralis/core/processors/reference_mode.py` for reference matching.
  - Continuous mode: `continuous_stages.py` (stage sequence), `continuous_dsp_ops.py`,
    `continuous_guards.py`, `continuous_quality.py`, `continuous_space.py`,
    `continuous_space_types.py`, `cross_dimensional_guard.py`, `stage_snapshot.py`.
  - Targets: `mastering_targets.py` (fingerprint to targets), `target_derivation.py` and
    `target_weights.py` (soft k-NN derivation), `reference_cloud.py`, `fixed_target_params.py`
    (targets to processing parameters), `album_target.py`.
  - EQ: `eq_processor.py`, `eq_curve.py`, `parameter_generator_eq.py`.
  - `base/` : measurement, compression/expansion, normalization, peak management, stereo width.
- `auralis/core/analysis/` : `content_analyzer.py`, `target_generator.py`, `spectrum_mapper/`
  (spectrum position and parameter mapping).
- `auralis/core/config/` : `unified_config.py` (`UnifiedConfig`), `preset_profiles.py`
  (`DEFAULT_PRESET_NAME`), `genre_profiles.py`, `settings.py`, `config_hash.py`.
- `auralis/core/utils/` : `smooth_curves.py`, `fingerprint_unpacker.py`, `stage_recorder.py`.
- `auralis/core/fingerprint_repository_provider.py` : how the engine finds the fingerprint repository.
- `auralis/core/recording_type_detector.py`, `auralis/core/recording_type_parameters.py` : used by
  `scripts/rate_track.py`, not by the app's audio path.

**Offline mastering** (called by `auto_master.py` and development scripts; not on the app's audio path):
`auralis/core/simple_mastering.py` (`SimpleMasteringPipeline`), `auralis/core/mastering_*.py`
(chunk loop and assembly, presets, config, diagnostics, file preparation, stage delegates),
`auralis/core/mastering_branches/`, `auralis/core/stages/` (spectral and dynamics stages) and
`auralis/core/dsp/` (exciter, notcher, transient shaper, parallel-EQ helpers).

### `auralis/dsp/` : signal-processing primitives

`basic.py` (rms, normalize, amplify, mid/side), `dc_blocker.py`, `constants.py`, `dynamics/`
(`compressor.py`, `brick_wall_limiter.py`, `soft_clipper.py`, `envelope.py`, limiter ramp, settings),
`eq/` (`psychoacoustic_eq.py` plus critical bands, curves, filters, padding, spectrum gains),
`utils/` (loudness targets, filters, conversion, stereo, `audio_info.py`, adaptive helpers).
See [dsp-engine.md](../subsystems/dsp-engine.md).

### `auralis/analysis/` : measurement and fingerprinting

- `fingerprint/` : the 25D fingerprint. `schema.py` (dimension names and semantics),
  `audio_fingerprint_analyzer.py`, `rust_fingerprint.py` (glue to `auralis_dsp`),
  `windowed_compute.py` / `windowed_loading.py` / `windows.py` / `track_audio.py` (what audio is
  analysed), `preloaded_fingerprint.py`, `fingerprint_service.py`, `fingerprint_storage.py`,
  `normalizer.py`, `distance.py`, `dimension_weights.py`, `similarity.py`, `knn_graph.py`,
  `metrics/` (per-dimension helpers). See [fingerprinting.md](../subsystems/fingerprinting.md).
- `adaptive_mastering_engine.py`, `mastering_profile.py`, `mastering_profiles_builtin.py`,
  `mastering_recommendation.py`, `mastering_fingerprint.py`, `reference_profile.py` : mastering
  profiles and recommendations.
- `loudness_meter.py` (+ `loudness_filters.py`, `loudness_filter_design.py`, `loudness_range.py`,
  `loudness_true_peak.py`), `dynamic_range*.py`, `phase_correlation.py`, `spectrum_*.py` : meters.
- `quality/` and `quality_assessors/` : loudness, dynamics, frequency, stereo and distortion
  assessment; mastering evaluation. `ml/` : `RuleBasedGenreClassifier` and its feature extractors
  (linear and rule-based, not a neural net).

### `auralis/library/` : SQLite library

See [library.md](../subsystems/library.md).

- `database.py` (`LibraryDatabase`), `database_engine.py`, `database_accessors.py`, `sqlite_wal.py`,
  `scan_coordinator.py` (scan slots), `data_dir.py`, `constants.py`.
- `models/` : SQLAlchemy models (`track.py`, `album.py`, `artist.py`, `genre.py`, `playlist.py`,
  `fingerprint.py`, `processing_job.py`, `settings.py`, `schema.py`, `_helpers.py`).
- `repositories/` : `base.py` (`BaseRepository`), `factory.py` (`RepositoryFactory`), and the 12
  repositories it exposes (track, album, artist, genre, playlist, fingerprint, fingerprint
  scheduler, fingerprint stats, stats, settings, processing job, similarity graph). Large
  repositories are split into `*_mixin.py` / `track_repository_*.py` modules.
- `scanner/` : `scanner.py` (`LibraryScanner`), `file_discovery.py`, `metadata_extractor.py`,
  `audio_analyzer.py`, `batch_processor.py`, `scan_stages.py`, `config.py`.
- `migration_manager.py` + `migration_*.py` (engine, lock, steps, versions, backups) and
  `migrations/` (numbered SQL files; the schema version is `__db_schema_version__` in
  `auralis/__version__.py`).
- `sidecar_manager.py` + `sidecar_*.py` : `.25d` fingerprint sidecars and their validation.
- `metadata_editor/` : tag reading, writing and backup. `artwork*.py`, `folder_artwork.py`,
  `picture_choice.py` : embedded and folder artwork. `resource_monitor.py` : adaptive scaling input.

### `auralis/player/` : playback engine

`enhanced_audio_player.py` (`AudioPlayer` facade), `playback_controller.py` (state machine),
`queue_controller.py` + `components/` (queue manager, navigation, selection, shuffle),
`gapless_playback_engine.py` + `gapless_prebuffer.py`, `audio_file_manager.py`,
`integration_manager.py` (+ `integration_*.py`), `player_*_mixin.py`, `realtime/` (realtime
processor, auto-master, gain smoothing, level matching, peak ceiling). See
[player.md](../subsystems/player.md).

### Other packages

- `auralis/io/` : `unified_loader.py` (entry point), `loader.py`, `loaders/` (FFmpeg decode and its
  guards, `soundfile_loader.py`), `formats.py`, `audio_probe.py`, `saver.py`, `results.py`,
  `wav_sanitize.py`.
- `auralis/services/` : the fingerprint worker pool (`fingerprint_queue.py`
  `FingerprintExtractionQueue`, `fingerprint_worker.py`, `fingerprint_extractor.py`,
  `fingerprint_claim.py`, `fingerprint_queue_scaling.py`, `fingerprint_track_runner.py`,
  `resizable_semaphore.py`) and artist artwork lookup (`artwork_service.py`, `artwork_sources/`).
- `auralis/learning/reference_seeder.py` : seeds and refreshes the reference cloud.
- `auralis/optimization/` : `performance_optimizer.py` (applied at import time by
  `auralis/core/hybrid_processor.py`), `profiling/`.
- `auralis/utils/` : logging, `audio_validation.py` (`validate_audio_finite`, `sanitize_audio`),
  `atomic_write.py`, `artwork_security.py`, `host_throttle.py`, `queue/` (M3U/XSPF import and export).
- `auralis/cli/fetch_artwork.py`, `auralis/version.py` (product version),
  `auralis/__version__.py` (`__db_schema_version__`, `FINGERPRINT_ALGORITHM_VERSION`).

---

## `auralis-web/backend/` : FastAPI

See [backend-api.md](../subsystems/backend-api.md) and
[WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md).

- `main.py` : thin orchestrator (bootstrap, lifespan, app, uvicorn on 127.0.0.1).
  `helpers.py`, `player_state.py` (`PlayerState` schema), `CONFIG.md` (environment variables).
- `config/` : app assembly. `app.py` (`create_app`, exception handlers), `routes.py`
  (`setup_routers`, the registered-router list and DI lambdas), `middleware/` (CORS, security
  headers, no-cache, origin check, trusted host, rate limit, unhandled-exception), `startup/`
  (lifespan: components, workers, fingerprint, rollback, shutdown, startup sweeps),
  `globals.py` (component registry), `limits.py`, `origins.py`, `retention.py`,
  `background_workers.py`, `fallback_routes.py` (frontend serving), `parent_lifeline.py`,
  `bootstrap.py`.
- `routers/` : one module family per domain, each with a `create_*_router(...)` factory
  registered in `config/routes.py`. Helper suffixes: `*_deps.py` (dependency holders),
  `*_models.py` (request/response models).
  - Library: `library.py`, `library_scan*.py`, `tracks.py`, `albums*.py`, `artists*.py`,
    `playlists*.py`, `metadata*.py`, `artwork*.py`, `files*.py`.
  - Playback: `player*.py` (state and queue), `enhancement*.py` (settings and recommendation),
    `processing_*.py` (REST batch jobs), `system.py` + `system_streams.py` (the `/ws` endpoint).
  - Analysis: `similarity*.py`, `fingerprint_status.py`, `fingerprint_queue*.py`.
  - Other: `settings*.py`, `cache_streamlined.py`, `health*.py`.
  - Shared: `dependencies.py` (`RouterDeps`, `with_error_handling`), `repo_deps.py`, `errors.py`,
    `pagination.py`, `serializers*.py`.
- `ws_handlers/` : per-message WebSocket handlers. `connection.py` (setup, heartbeat, dispatch,
  teardown), `playback_commands.py` (`play_enhanced`, `play_normal`), `playback_control.py`
  (pause, resume, flow control, stop), `seek_command.py`, `stream_cancel.py`, `context.py`
  (`StreamState`, `WSDeps`), `enhancement_params.py`, `messages.py`.
- `websocket/` : `connection_manager.py` (`ConnectionManager`, origin allowlist),
  `outbound_messages.py` + `outbound/` (typed broadcast payloads), `message_validation.py`,
  `rate_limiter.py`, `websocket_protocol.py` (heartbeat).
- `core/` : the engine-facing layer.
  - Geometry: `chunk_boundaries.py` (the only source of chunk constants and counts),
    `chunk_boundary_manager.py`, `chunk_segment_extraction.py`.
  - Chunk rendering: `chunked_processor.py` (`ChunkedAudioProcessor`, a coordinator over
    `chunk_render.py`, `chunk_render_miss.py`, `chunk_streaming.py`, `chunk_processor_init.py`,
    `chunk_file_loading.py`, `chunk_mastering.py`, `chunk_metadata.py`), `audio_processing_pipeline.py`,
    `level_manager.py` (+ `level_*.py`), `seekable_source.py`, `converted_wav_registry.py`.
  - Chunk cache: `chunk_cache_manager.py`, `chunk_path_cache.py`, `chunk_single_flight.py`,
    `chunk_disk_prune.py`, `encoding/` (16-bit PCM WAV encoder).
  - Processor lifecycle: `processor_factory.py` (`ProcessorFactory`), `processor_registry.py`
    (one factory per consumer), `processor_lease.py`, `chunk_processor_lease.py`,
    `processor_cache_key.py`, `processor_pool.py`, `processor_maintenance.py`.
  - Targets: `mastering_target_service.py` (`MasteringTargetService`), `fingerprint_loading.py`,
    `fingerprint_single_flight.py`, `targets_hash.py`.
  - Streaming: `audio_stream_controller.py` (`AudioStreamController`) with `stream_enhanced*.py`,
    `stream_normal*.py`, `stream_seek.py`, `stream_pump.py`, `stream_protocol.py` (PCM frames),
    `stream_lifecycle.py`, `stream_permit.py`, `stream_gates.py`, `stream_fingerprint.py`,
    `stream_notifications.py`, `stream_track_resolution.py`, `executors.py` (streaming and I/O
    thread pools).
  - Background builders: `proactive_buffer.py`, `streamlined_worker.py` (+ `streamlined_*.py`).
  - REST jobs: `processing_engine.py` (`ProcessingEngine`) with `job_*.py`.
  - State: `state_manager.py` (`PlayerStateManager`), `position_ticker.py`.
- `cache/` : `manager.py` (`StreamlinedCacheManager`) and its mixins.
- `analysis/` : `fingerprint_generator.py`, `fingerprint_queue.py` (on-demand queue),
  `fingerprint_executor.py`, `fingerprint_queue_state.py`.
- `services/` : `library_auto_scanner.py` (+ `scanner_*.py`, `scan_*.py`, `missing_tracks.py`),
  `playback_service.py`, `queue_service.py` (+ `queue_*.py`), `navigation_service.py`,
  `artwork_downloader.py` + `artwork_providers/`, `similarity_autofit_worker.py`,
  `lyrics_extraction.py`, `recommendation_analysis.py`.
- `schemas/` : Pydantic models by domain (`enhancement.py`, `library.py`, `mastering.py`,
  `system.py`, `websocket.py`, `request_bounds.py`). `security/` : path allowlist and validation.

---

## `auralis-web/frontend/src/` : React

See [frontend.md](../subsystems/frontend.md).

- `index.tsx` (entry), `App.tsx` (provider tree), `ComfortableApp.tsx` (app shell; views switch by
  local state, there is no router).
- `store/` : Redux Toolkit. `slices/` (`playerSlice.ts`, `queueSlice.ts`, `cacheSlice.ts`,
  `connectionSlice.ts` and helpers), `selectors/`, `middleware/` (logging, error tracking).
- `contexts/` : `WebSocketContext.tsx` (the single socket), `PlaybackSessionContext.tsx` (the one
  streaming session), `ThemeContext.tsx`.
- `hooks/` : nine domain groups. `player/` (queue, transport state, `usePlayTrack`),
  `enhancement/` (`usePlayEnhanced`, stream handlers, chunk ingest), `websocket/` (connection,
  frame parser), `library/` (`useLibraryQuery`, scan hooks), `fingerprint/`, `api/`
  (`useRestAPI`), `app/`, `audio/`, `shared/`.
- `services/` : `audio/` (`PCMStreamBuffer.ts`, `AudioPlaybackEngine.ts`, `BufferScheduler.ts`,
  `WorkletOutput.ts`, position tracking), REST service wrappers (`libraryService.ts`,
  `playlistService.ts`, `queueService.ts`, `settingsService.ts`, `artworkService.ts`),
  `api/cacheShapeGuards.ts`.
- `utils/` : `apiRequest.ts` (the only HTTP transport), `audio/pcmDecoding.ts`, error handling,
  formatting, colour utilities. `api/` : response guards and `transformers/` (REST to domain types).
- `types/` : `ws/` (message-type registry and per-domain unions), `domain.ts`, `api.ts`.
- `components/` : domain-grouped UI. `player/` (transport bar, queue panel), `library/` (views,
  items, details, search, metadata dialog), `playlist/`, `settings/`, `shared/` (toasts, context
  menu, drop zone, enhancement toggle, cache dashboard), `core/` (app chrome, error boundaries),
  `layouts/`, `navigation/`, `album/`, `background/`, `track/`, `platform/`.
- `design-system/` : `tokens/` (single source of truth for colour, type, layout, effects) and
  `primitives/`. `theme/` and `styles/` build the MUI theme and global styles from the tokens.
- `config/api.ts` (`ENDPOINTS`, base URLs), `config/timing.ts`, `a11y/`, `test/` (global setup,
  mocks, `test-utils.tsx`).
- Tooling in `auralis-web/frontend/`: `vite.config.mts`, `vitest.config.ts`, `test-baseline.json`
  (CI ratchet), `public/audio-worklet-processor.js` (the AudioWorklet).

---

## `vendor/auralis-dsp/` : Rust

One PyO3 module, `auralis_dsp`, with one production entry point: `compute_fingerprint`.

- `vendor/auralis-dsp/src/py_bindings.rs` : the module and the `compute_fingerprint` wrapper.
- `vendor/auralis-dsp/src/fingerprint_compute.rs` : assembles the 25 dimensions.
- Feature extractors: `chroma.rs`, `rhythm.rs`, `frequency_analysis.rs`, `spectral_features.rs`,
  `variation_analysis.rs`, `stereo_analysis.rs`, `dsp_math.rs`; `lib.rs` declares the modules.

Build with `cd vendor/auralis-dsp && maturin develop`. Do not add a module without a production
Python caller.

---

## `desktop/` : Electron

- `desktop/main.js` : app lifecycle and window. Packaged, it spawns the bundled backend binary and
  loads `http://127.0.0.1:8765`; in development it loads the Vite origin.
- `desktop/preload.js` : the renderer's IPC surface, gated by sender origin.
- `desktop/url-safety.js` (origin and navigation allowlists, backend log escaping),
  `desktop/backend-env.js`, `desktop/backend-integrity.js` (digest check of the packaged backend),
  `desktop/backend-shutdown.js`, `desktop/error.html`,
  `desktop/scripts/record-backend-digest.js`.

---

## `tests/` : 16 subdirectories

`audio`, `auralis`, `backend`, `boundaries`, `concurrency`, `edge_cases`, `input_media`,
`integration`, `load_stress`, `performance`, `regression`, `results`, `security`, `stress`,
`utils`, `vendor`. How to run them, and which files must be excluded from a whole-suite run:
[../CONTRIBUTING.md](../CONTRIBUTING.md#4-testing) and the commands section of
[../../CLAUDE.md](../../CLAUDE.md).

---

## Finding things fast

- "Who calls this?" : the `codebase-memory` graph tools rather than blind grep.
- "Trace a user action through the layers" : the `trace-flow` skill, or [data-flow.md](data-flow.md).
- "Where does audio X happen?" : start at the relevant [subsystem doc](../subsystems/).
