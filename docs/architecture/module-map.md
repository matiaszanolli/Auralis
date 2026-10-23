# Architecture: Module Map

A file-level guide to *where things live*. Use this to find the right directory before diving
into a [subsystem doc](../subsystems/). Counts are approximate and drift over time — trust the
tree, not the numbers.

---

## Top level

```
matchering/
├── auralis/              Core Python engine (audio, analysis, library, player)
├── auralis-web/
│   ├── backend/          FastAPI REST + WebSocket (:8765)
│   └── frontend/         React + TypeScript + Vite + Redux
├── vendor/auralis-dsp/   Rust DSP via PyO3 (in-process fingerprint module)
├── desktop/              Electron wrapper
├── tests/                ~7,000 test functions across 16 subdirs
└── docs/                 This documentation
```

---

## `auralis/` — core engine

```
auralis/
├── core/                       Processing pipeline
│   ├── hybrid_processor.py       HybridProcessor — streaming engine entry
│   ├── simple_mastering.py       SimpleMasteringPipeline — offline file masterer
│   ├── mastering_*.py            Offline chunk loop/assembly, presets, config,
│   │                             diagnostics, prepare, stage delegates
│   ├── mastering_branches/       ContinuousMasteringBranch (continuous.py) +
│   │                             soft_clip_params.py — one continuous branch, no
│   │                             material classification
│   ├── processing/               Mode processors (adaptive, continuous, hybrid) plus the
│   │                             continuous-space/parameter-generation machinery
│   └── config/                   UnifiedConfig, preset_profiles, genre_profiles
├── dsp/                        Signal processing primitives
│   ├── basic.py                  rms, normalize, amplify, mid/side
│   ├── advanced_dynamics.py      DynamicsProcessor (gate/comp/limit)
│   ├── dynamics/                 Compressor, brick-wall limiter, envelope, soft clipper
│   ├── eq/                       PsychoacousticEQ (26 Bark bands, WOLA)
│   └── utils/                    Loudness targets, filters, conversion, audio_info
├── analysis/                   Largest module (59 files)
│   ├── fingerprint/              25D fingerprint: schema, audio_fingerprint_analyzer,
│   │                             rust_fingerprint, windowed_compute, metrics/,
│   │                             normalizer, distance, similarity, knn_graph
│   ├── ml/                       RuleBasedGenreClassifier (linear, NOT a neural net)
│   ├── quality/ + quality_assessors/  Loudness/DR/distortion quality assessment
│   └── mastering_*.py, spectrum_*.py  Mastering profiles/recommendation, spectrum tools
├── library/                    SQLite library (~/.auralis/library.db)
│   ├── database.py               LibraryDatabase (engine, migration, sessions, scan slots)
│   ├── repositories/             12 repos + base.py (BaseRepository) + factory.py
│   ├── scanner/                  Folder scanning (a package, not a module)
│   ├── sidecar_manager.py        Per-file .25d sidecars
│   └── migration_manager.py      DB migrations (schema version imported from
│                                   auralis/__version__.py)
├── io/                         unified_loader.py (FFmpeg/SoundFile), results.py (PCM
│                                 output), saver.py, loaders/
├── player/                     enhanced_audio_player, gapless engine, queue_controller,
│                                 playback mixins, realtime/
├── services/                   Background: fingerprint_queue, fingerprint_extractor,
│                                 fingerprint worker/queue manager, artwork_service
├── learning/                   reference_seeder.py (the preference engine was
│                                 removed, #5763)
├── optimization/               performance_optimizer (LIVE — applied at import time by
│                                 core/hybrid_processor.py), profiling/.
│                                 SmartCache/MemoryPool/SIMD/config deleted (#5769); parallel_processor +
│                                 parallel/ were deleted (#4565); no rust_integration.py (#5168)
└── utils/                      Logging, validation, atomic writes, artwork security, queue
```

**Deep dives:** [dsp-engine.md](../subsystems/dsp-engine.md) covers `core/` + `dsp/`;
[fingerprinting.md](../subsystems/fingerprinting.md) covers `analysis/`.

---

## `auralis-web/backend/` — FastAPI

```
backend/
├── main.py                 Thin orchestrator (lifespan → app → middleware → routers)
├── config/                 App assembly
│   ├── app.py                create_app + global exception handlers
│   ├── middleware/           CORS / SecurityHeaders / NoCache / RateLimit / OriginCheck
│   ├── routes.py             Router registration + DI (get_component lambdas) — the
│   │                         list of the 20 registered routers lives here
│   ├── startup/              Lifespan package (startup order, rollback, watchdog,
│   │                         shutdown, workers)
│   └── globals.py            ConnectionManager + globals_dict + WS origin allowlist
├── routers/                75 modules, of which 20 are registered in config/routes.py
│                             (player, library, albums, artists, playlists, enhancement,
│                             metadata, artwork, similarity, library_scan, …; the rest
│                             are per-router *_deps/*_models helper modules)
├── ws_handlers/            WebSocket connection lifecycle + message dispatch
├── websocket/              Outbound typed messages, protocol, security
├── core/                   Engine room
│   ├── chunk_boundaries.py    Chunk geometry — SINGLE SOURCE OF TRUTH
│   ├── chunked_processor.py   ChunkedAudioProcessor (WS chunk DSP)
│   ├── processing_engine.py   ProcessingEngine (REST batch jobs)
│   ├── processor_factory.py   HybridProcessor LRU cache
│   ├── audio_stream_controller.py + stream_*.py   WS streaming (god-file split)
│   └── encoding/              Output encoders
├── cache/                  StreamlinedCacheManager (tiered chunk cache) + mixins
├── analysis/               Fingerprint generation + queue services
├── security/               Security helpers
├── services/               library_auto_scanner, playback/queue, recommendation, artwork
└── schemas/                Pydantic request/response models, by domain
```

**Deep dive:** [backend-api.md](../subsystems/backend-api.md).

---

## `auralis-web/frontend/` — React

```
frontend/src/
├── index.tsx               Live entry point
├── App.tsx                 Provider tree
├── ComfortableApp.tsx      App shell (local-useState view switching, no router)
├── store/                  Redux: player, queue, cache, connection slices
├── contexts/               ThemeContext, WebSocketContext (singleton WS connection)
├── hooks/                  9 domain groups: player, enhancement, library, websocket,
│                             api, app, fingerprint, audio, shared
├── services/
│   ├── api/                  standardizedAPIClient + domain services
│   └── audio/                PCMStreamBuffer, AudioPlaybackEngine, audioConstants
├── design-system/          tokens (single source of truth) + ~20 primitives
├── components/             195 non-test .tsx, domain-grouped (player, library,
│                             enhancement, core, …)
├── types/                  ws/ registry (exhaustive message-type union), api types
├── config/api.ts           API_BASE_URL / WS_BASE_URL
└── test/                   setup.ts (global WS mock), test-utils.tsx
```

**Deep dive:** [frontend.md](../subsystems/frontend.md).

---

## `vendor/auralis-dsp/` — Rust

```
auralis-dsp/src/
├── py_bindings.rs             PyO3 module: compute_fingerprint (+ dead process_chunks, #5738)
├── fingerprint_compute.rs     Native 25D fingerprint (the ONLY fingerprint path)
└── chroma.rs, rhythm.rs, spectral_features.rs, stereo_analysis.rs,
    variation_analysis.rs, dsp_math.rs, chunk_processor.rs, …   feature extractors
```

Built with `cd vendor/auralis-dsp && maturin develop`. See
[dsp-engine.md §5](../subsystems/dsp-engine.md#5-rust-dsp-module-vendorauralis-dsp).

---

## `tests/` — 16 subdirectories

`audio`, `auralis`, `backend`, `boundaries`, `concurrency`, `edge_cases`, `input_media`,
`integration`, `load_stress`, `performance`, `regression`, `results`, `security`, `stress`,
`utils`, `vendor`.
See [../CONTRIBUTING.md](../CONTRIBUTING.md#testing) for how to run them (and which suites are
known-flaky).

---

## Finding things fast

- **"Who calls this / what's the structure?"** — use the `codebase-memory` skill (graph
  queries over the indexed codebase) rather than grepping blind.
- **"Trace a user action through the layers"** — the `trace-flow` skill.
- **"Where does audio X happen?"** — start at the relevant [subsystem doc](../subsystems/); each
  ends with a "where to start reading" list.
