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
├── vendor/auralis-dsp/   Rust DSP via PyO3 (+ gRPC fingerprint server)
├── desktop/              Electron wrapper
├── tests/                ~5,100 test functions across 18 subdirs
└── docs/                 This documentation
```

---

## `auralis/` — core engine

```
auralis/
├── core/                       Processing pipeline
│   ├── hybrid_processor.py       HybridProcessor — streaming engine entry
│   ├── simple_mastering.py       SimpleMasteringPipeline — offline file masterer
│   ├── mastering_branches.py     Material-classified mastering branches
│   ├── processing/               Mode processors (adaptive, continuous, hybrid, realtime)
│   └── config/                   UnifiedConfig, preset_profiles
├── dsp/                        Signal processing primitives
│   ├── basic.py                  rms, normalize, amplify, mid/side
│   ├── advanced_dynamics.py      DynamicsProcessor (gate/comp/limit)
│   ├── eq/                       PsychoacousticEQ (26 Bark bands, WOLA)
│   ├── realtime_adaptive_eq/     RealtimeAdaptiveEQ (FIFO, exact-length)
│   └── stages.py                 Legacy Matchering reference matcher
├── analysis/                   Largest module (~80 files)
│   ├── fingerprint/              25D fingerprint: schema, analyzers, metrics, utilities,
│   │                               normalizer, distance, similarity, knn_graph
│   ├── content/                  Genre/mood/recommendation (content-aware)
│   ├── ml/                       RuleBasedGenreClassifier (linear, NOT a neural net)
│   └── quality/                  Quality assessment (loudness, DR, distortion)
├── library/                    SQLite library (~/.auralis/library.db)
│   ├── manager.py                LibraryManager
│   ├── repositories/             14 repos + base.py (BaseRepository) + factory.py
│   ├── scanner.py                Folder scanning
│   ├── sidecar_manager.py        Per-file .25d sidecars
│   └── migration_manager.py      DB migrations (schema v16)
├── io/                         unified_loader.py (FFmpeg/SoundFile), results.py (PCM output)
├── player/                     enhanced_audio_player, gapless engine, queue_controller
├── services/                   Background: fingerprint_queue, fingerprint_extractor, artwork
├── learning/                   Preference engine, reference analysis
├── optimization/               parallel_processor
└── utils/                      Logging, helpers, preview creator
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
│   ├── middleware.py         CORS / SecurityHeaders / NoCache / RateLimit
│   ├── routes.py             Router registration + DI (get_component lambdas)
│   ├── startup.py            Lifespan (startup order, rollback, watchdog, shutdown)
│   └── globals.py            ConnectionManager + globals_dict + WS origin allowlist
├── routers/                ~23 route modules (player, library, albums, artists, playlists,
│                             enhancement, metadata, artwork, similarity, wav_streaming,
│                             processing_api, cache_streamlined, system (WS), health, …)
├── ws_handlers/            WebSocket connection lifecycle + message dispatch
├── core/                   Engine room
│   ├── chunk_boundaries.py    Chunk geometry — SINGLE SOURCE OF TRUTH
│   ├── chunked_processor.py   ChunkedAudioProcessor (WS chunk DSP)
│   ├── processing_engine.py   ProcessingEngine (REST batch jobs)
│   ├── processor_factory.py   HybridProcessor LRU cache
│   ├── audio_stream_controller.py + stream_*.py   WS streaming (god-file split)
│   └── encoding/              Output encoders
├── services/               library_auto_scanner, playback/queue, recommendation, artwork
└── schemas.py              Pydantic request/response models
```

**Deep dive:** [backend-api.md](../subsystems/backend-api.md).

---

## `auralis-web/frontend/` — React

```
frontend/src/
├── index.tsx               Live entry (main.tsx is stale — ignore it)
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
├── components/             265 .tsx, domain-grouped (player, library, enhancement, core, …)
├── types/                  ws/ registry (exhaustive message-type union), api types
├── config/api.ts           API_BASE_URL / WS_BASE_URL
└── test/                   setup.ts (global WS mock), test-utils.tsx
```

**Deep dive:** [frontend.md](../subsystems/frontend.md).

---

## `vendor/auralis-dsp/` — Rust

```
auralis-dsp/src/
├── py_bindings.rs             PyO3 module: hpss, yin, chroma_cqt, compute_fingerprint, …
├── fingerprint_compute.rs     Native 25D fingerprint
└── bin/
    └── grpc_fingerprint_server.rs   Standalone gRPC server (primary fingerprint path, :8766)
```

Built with `cd vendor/auralis-dsp && maturin develop`. See
[dsp-engine.md §5](../subsystems/dsp-engine.md#5-rust-dsp-module-vendorauralis-dsp).

---

## `tests/` — 18 subdirectories

`unit`, `integration`, `boundary`, `concurrency`, `security`, `load`, `regression`, and more.
See [../CONTRIBUTING.md](../CONTRIBUTING.md#testing) for how to run them (and which suites are
known-flaky).

---

## Finding things fast

- **"Who calls this / what's the structure?"** — use the `codebase-memory` skill (graph
  queries over the indexed codebase) rather than grepping blind.
- **"Trace a user action through the layers"** — the `trace-flow` skill.
- **"Where does audio X happen?"** — start at the relevant [subsystem doc](../subsystems/); each
  ends with a "where to start reading" list.
