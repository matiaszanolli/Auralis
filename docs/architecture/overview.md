# Architecture Overview

Auralis is a music player that masters audio as it plays. It ships as a single Electron desktop
application and everything runs on localhost: the backend binds `127.0.0.1` (port `8765` by
default, `AURALIS_PORT` to override), there is one client, and there is no TLS, multi-user or
LAN surface. Several design choices follow from that, such as file-based locking and a
loopback-only origin allowlist.

Read this page for the map, [data-flow.md](data-flow.md) for how a request travels through it, and
[module-map.md](module-map.md) for the file layout. Detail lives in the subsystem docs, linked
below, and is not repeated here.

---

## The four layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  Electron shell (desktop/)                                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  React frontend  (auralis-web/frontend/)                       │  │
│  │  React 18 · Redux Toolkit · Vite · Web Audio (AudioWorklet)    │  │
│  └───────────────┬───────────────────────────┬───────────────────┘  │
│         REST (HTTP)                    WebSocket (/ws)                │
│  ┌───────────────▼───────────────────────────▼───────────────────┐  │
│  │  FastAPI backend  (auralis-web/backend/)  127.0.0.1:8765      │  │
│  │  routers · WebSocket streaming · chunk rendering               │  │
│  └───────┬───────────────────────┬───────────────────┬───────────┘  │
│  ┌───────▼──────────┐  ┌─────────▼─────────┐  ┌───────▼───────────┐  │
│  │ Audio engine     │  │ Library (SQLite)  │  │ Analysis /         │  │
│  │ auralis/core     │  │ auralis/library   │  │ fingerprinting     │  │
│  │ auralis/dsp      │  │ auralis/player    │  │ auralis/analysis   │  │
│  └───────┬──────────┘  └───────────────────┘  └───────┬───────────┘  │
│  ┌───────▼─────────────────────────────────────────────▼──────────┐  │
│  │  Rust  (vendor/auralis-dsp/)  25D fingerprint, PyO3, in-process│  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

| Layer | Path | Language | Responsibility | Deep dive |
|-------|------|----------|----------------|-----------|
| Renderer | [`auralis-web/frontend/`](../../auralis-web/frontend/) | TypeScript / React | UI, Redux state, PCM buffering and Web Audio playback | [frontend.md](../subsystems/frontend.md) |
| Backend | [`auralis-web/backend/`](../../auralis-web/backend/) | Python / FastAPI | REST, the `/ws` socket, chunk rendering, background workers | [backend-api.md](../subsystems/backend-api.md) |
| Engine | [`auralis/`](../../auralis/) | Python | DSP, analysis, library, player state | [dsp-engine.md](../subsystems/dsp-engine.md), [fingerprinting.md](../subsystems/fingerprinting.md), [library.md](../subsystems/library.md), [player.md](../subsystems/player.md) |
| Rust | [`vendor/auralis-dsp/`](../../vendor/auralis-dsp/) | Rust / PyO3 | 25D fingerprint computation | [fingerprinting.md](../subsystems/fingerprinting.md) |

The Electron wrapper ([`desktop/`](../../desktop/)) spawns the bundled backend binary and loads
the renderer from the backend's own origin (`http://127.0.0.1:8765`) when packaged, or from the
Vite dev server in development. The browser-preview launcher exists for renderer development
only and is not a supported way to run the app.

The audio is rendered by the backend and played by the renderer. The engine's player
(`auralis/player/`) owns the queue and playback state that the backend publishes; the sound comes
from PCM streamed to the browser's Web Audio graph, not from a server-side output device.

---

## Design rules

### 1. Analysis is whole-track; mastering is rendered per chunk from a track-level plan

A track is analysed once into a 25-dimension fingerprint. That fingerprint, together with the
reference cloud, yields one set of mastering targets, and every chunk of the track is rendered
against those same targets.

- `auralis-web/backend/core/mastering_target_service.py::MasteringTargetService.load_fingerprint`
  produces the plan: database row, then `.25d` sidecar, then extraction from the audio. The plan
  is cached per track and file signature.
- Tracks up to `FINGERPRINT_FULL_TRACK_MAX_S` seconds are analysed in full; longer files use
  body and probe windows (`auralis/analysis/fingerprint/windows.py`).
- `auralis-web/backend/core/chunk_processor_init.py::init_fingerprint_and_processor` loads the plan
  before the first chunk renders, and the `HybridProcessor` leased to the stream is built with
  those targets installed.
- Each chunk goes through `auralis/core/hybrid_processor.py::HybridProcessor.process` on that one
  processor, so compressor, EQ and limiter state carry across chunk seams.
- Never fingerprint per chunk. When no plan can be obtained the processor falls back to analysing
  each chunk on its own, which is the degraded path, not a feature.

### 2. Adaptive mastering in a continuous space, not presets

The only preset is `adaptive` (`auralis/core/config/preset_profiles.py::DEFAULT_PRESET_NAME`; the
API accepts `schemas/enhancement.py::VALID_PRESETS`). The fingerprint is mapped to targets by a
soft k-nearest-neighbour pull toward a reference cloud, and the targets become continuous
processing parameters. Do not reintroduce a preset list. See
[dsp-engine.md](../subsystems/dsp-engine.md).

### 3. Gapless chunked streaming

Chunks are rendered with context on each side and emitted as non-overlapping segments that tile
the timeline exactly, with no boundary crossfade. Chunk geometry has one source of truth
(`auralis-web/backend/core/chunk_boundaries.py`); never hand-roll chunk counting. Rendered chunks
are cached on disk as 16-bit PCM WAV; on the wire they are float32 PCM. See
[backend-api.md](../subsystems/backend-api.md).

### 4. Rust only for the fingerprint

The 25D fingerprint is computed in Rust (`auralis_dsp.compute_fingerprint`) and called in-process
from Python. There is no Python fallback and no out-of-process fingerprint server, so the module
must be built (`cd vendor/auralis-dsp && maturin develop`) before first run. Everything else in the
DSP chain is NumPy/SciPy.

---

## Project-wide invariants

```python
assert len(output) == len(input)               # never change sample count (gapless)
assert isinstance(output, np.ndarray)          # always NumPy, never lists
assert output.dtype in (np.float32, np.float64)
output = audio.copy()                          # never modify in place
```

- No NaN/Inf escapes the pipeline: `auralis/utils/audio_validation.py` (`validate_audio_finite`,
  `sanitize_audio`) and `auralis-web/backend/core/audio_processing_pipeline.py`
  (`AudioProcessingPipeline.apply_enhancement` falls back to the input on a non-finite result and
  raises on a changed length).
- All database access goes through the repositories behind
  [`RepositoryFactory`](../../auralis/library/repositories/factory.py), never raw SQL.
  Repositories detach what they return, so relationships must be eager-loaded; the rules are in
  [CLAUDE.md](../../CLAUDE.md).
- DSP never runs on the event loop: chunk renders go through `run_in_stream_executor`
  (`auralis-web/backend/core/executors.py`), repository calls through `asyncio.to_thread`.
- Shared backend state is lock-guarded: `asyncio.Lock` for event-loop state, `threading.RLock` for
  state touched from worker threads, `contextvars` for per-stream identity
  (`auralis-web/backend/core/audio_stream_controller.py`).
- Parallelism is thread-based. The Rust call releases the GIL, fingerprint workers are threads,
  and `HybridProcessor` holds a `threading.RLock` and is not designed to cross a process boundary.
  Do not add a process pool without a measured need.

The `verify-dsp` skill checks the audio invariants across the pipeline.

---

## Source-of-truth registry

When a doc and the code disagree, the code in this table wins. Link to these rather than
restating them.

| Fact | Owner |
|------|-------|
| Product version | [`auralis/version.py`](../../auralis/version.py), propagated by `sync_version.py` to every manifest and injected into the renderer as `__APP_VERSION__` |
| DB schema version, fingerprint algorithm version | [`auralis/__version__.py`](../../auralis/__version__.py) (`__db_schema_version__`, `FINGERPRINT_ALGORITHM_VERSION`); migrations in `auralis/library/migrations/` |
| Fingerprint dimensions, names, units | [`auralis/analysis/fingerprint/schema.py`](../../auralis/analysis/fingerprint/schema.py) |
| Chunk geometry and chunk counting | [`auralis-web/backend/core/chunk_boundaries.py`](../../auralis-web/backend/core/chunk_boundaries.py) |
| Repository set | [`auralis/library/repositories/factory.py`](../../auralis/library/repositories/factory.py) (`RepositoryFactory`) |
| Registered routers and their DI | [`auralis-web/backend/config/routes.py`](../../auralis-web/backend/config/routes.py) (`setup_routers`) |
| WebSocket messages | [`WEBSOCKET_API.md`](../../auralis-web/backend/WEBSOCKET_API.md) and the frontend registry `auralis-web/frontend/src/types/ws/registry.ts` |
| Backend environment variables | [`auralis-web/backend/CONFIG.md`](../../auralis-web/backend/CONFIG.md) |
| Loopback hosts, port, allowed origins | [`auralis-web/backend/config/origins.py`](../../auralis-web/backend/config/origins.py) |
| Design tokens | `auralis-web/frontend/src/design-system/tokens/` |
| CI failure baselines | `pytest-baseline.json`, `auralis-web/frontend/test-baseline.json` (rules in [CLAUDE.md](../../CLAUDE.md)) |

---

## Where to go next

- End to end: [data-flow.md](data-flow.md)
- File layout: [module-map.md](module-map.md)
- Conventions for new services, processors and repositories: [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- Setup and contribution: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- Subsystems: [DSP engine](../subsystems/dsp-engine.md) · [Fingerprinting](../subsystems/fingerprinting.md) ·
  [Backend API](../subsystems/backend-api.md) · [Frontend](../subsystems/frontend.md) ·
  [Player](../subsystems/player.md) · [Library](../subsystems/library.md)
