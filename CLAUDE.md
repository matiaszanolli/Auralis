# CLAUDE.md

**Project**: Auralis — Music player with real-time audio enhancement
**Version**: 1.2.0-beta.3 (`auralis/version.py` is source of truth)
**Python**: 3.14+ | **Node**: 24+ | **Rust**: Required (PyO3 DSP module)
**License**: AGPL-3.0 (dual-licensed, see COMMERCIAL_LICENSE.md)

## Commands

```bash
# Run (web)
pip install -r requirements.txt
python launch-auralis-web.py --dev      # Backend :8765, Frontend :3000

# Run (components)
cd auralis-web/backend && python -m uvicorn main:app --reload
cd auralis-web/frontend && npm install && npm run dev
cd desktop && npm install && npm run dev

# Test
python -m pytest tests/ -v                         # All (~2-3 min)
python -m pytest -m "not slow" -v                   # Fast subset
python -m pytest tests/path.py::test_name -vv -s    # Single test
cd auralis-web/frontend && npm run test:memory       # Frontend (2GB heap)

# Type check
mypy auralis/ auralis-web/backend/ --ignore-missing-imports
cd auralis-web/frontend && npm run type-check

# Build Rust DSP (required before first run)
cd vendor/auralis-dsp && maturin develop
```

## Codebase Map

```
auralis/                          Core Python audio engine
├── core/                         Processing pipeline
│   ├── hybrid_processor.py         HybridProcessor — main DSP pipeline
│   ├── simple_mastering.py         SimpleMastering algorithm
│   ├── processor.py                Core entry point
│   ├── config.py                   Processing configuration
│   └── recording_type_detector.py  Content type detection
├── dsp/                          Signal processing
│   ├── unified.py                  Unified DSP pipeline
│   ├── psychoacoustic_eq.py        Psychoacoustic EQ
│   ├── advanced_dynamics.py        Dynamics control
│   └── realtime_adaptive_eq.py     Real-time adaptive EQ
├── analysis/                     Audio analysis (largest module, 92 files)
│   ├── fingerprint/                25D fingerprinting system
│   │   ├── analyzers/                Batch & streaming analyzers
│   │   ├── metrics/                  Spectral, harmonic, temporal
│   │   └── utilities/                DSP ops, backend selection
│   ├── content/                    Content-aware analysis
│   ├── ml/                         Genre classification (neural nets)
│   └── quality/                    Quality assessment (loudness, distortion, DR)
├── player/                       Playback engine
│   ├── enhanced_audio_player.py    Main player with adaptive DSP
│   ├── gapless_playback_engine.py  Gapless playback
│   ├── queue_controller.py         Queue management
│   └── realtime_processor.py       Real-time processing
├── library/                      SQLite library (~/.auralis/library.db)
│   ├── manager.py                  LibraryManager
│   ├── repositories/               12 repos (track, album, artist, playlist, genre,
│   │                                 stats, fingerprint, queue, settings, similarity...)
│   ├── scanner.py                  Folder scanning
│   └── migration_manager.py        DB migrations (schema v3)
├── io/                           Audio I/O
│   ├── unified_loader.py           Unified loading (FFmpeg, SoundFile)
│   └── results.py                  Output formats (pcm16, pcm24)
├── optimization/                 Performance
│   └── parallel_processor.py       Parallel audio processing
├── services/                     Background services (fingerprint, artwork)
├── learning/                     Preference engine, reference analysis
└── utils/                        Logging, helpers, preview creator

auralis-web/
├── backend/                      FastAPI REST + WebSocket (:8765)
│   ├── main.py                     App entry point
│   ├── routers/                    18 route handlers (player, library, albums,
│   │                                 artists, playlists, enhancement, metadata,
│   │                                 artwork, system, similarity, streaming...)
│   ├── processing_engine.py        Audio processing orchestration
│   ├── chunked_processor.py        30s chunks, 3s crossfade
│   ├── audio_stream_controller.py  WebSocket audio streaming
│   ├── schemas.py                  Request/response schemas
│   └── services/, core/, config/   Service layer, encoding, config
└── frontend/                     React 18 + TypeScript + Vite + Redux
    └── src/
        ├── components/               UI components
        ├── hooks/                    Domain hooks (player, library, enhancement,
        │                               websocket, api, app, fingerprint, shared)
        ├── store/                    Redux state management
        ├── design-system/            Design tokens (single source of truth)
        ├── services/                 API clients
        └── test/                     Test utilities

vendor/auralis-dsp/               Rust DSP via PyO3 (HPSS, YIN, Chroma)
desktop/                          Electron wrapper
tests/                            850+ tests across 21 dirs (unit, integration,
                                    boundary, concurrency, security, load, regression...)
docs/                             20 topic dirs (development, features, frontend...)
```

## Architecture Flow

```
User → FastAPI (REST + WebSocket :8765) → Backend Services
         → LibraryManager (SQLite) → HybridProcessor (DSP pipeline)
         → ChunkedProcessor (30s chunks) → WebSocket stream → React (Redux)
```

## Critical Invariants

**Audio processing** — sample count preservation is critical for gapless playback:
```python
assert len(output) == len(input)              # Never change sample count
assert isinstance(output, np.ndarray)         # Always NumPy, never lists
assert output.dtype in [np.float32, np.float64]
output = audio.copy()                         # Never modify in-place
```

**Player state**: position ≤ duration, queue index valid, state changes atomic (RLock).
**Database**: thread-safe pooling (`pool_pre_ping=True`), no N+1 (`selectinload()`), all access via repositories.

## Patterns

**Python backend**: Routers auto-included via `include_router()`. All handlers `async def`. Errors via `HTTPException`. Shared state protected with `threading.RLock()`.

**React frontend**: `@/` absolute imports only. Colors via `import { tokens } from '@/design-system'`. Components < 300 lines. Tests use `vi.*` (Vitest), `render` from `@/test/test-utils`.

**Audio DSP**: Load metadata (sample rate, channels) BEFORE processing. Vectorize with NumPy (chunks, not samples). Copy before modify.

## Principles

1. **DRY** — Improve existing code, never duplicate. Use utilities for shared logic.
2. **Modular** — < 300 lines per module, single responsibility.
3. **No variants** — No "Enhanced"/"V2"/"Advanced" copies. Refactor in-place.
4. **Repository pattern** — All DB via `auralis/library/repositories/`, never raw SQL.

## Git

Branch from `master`. Prefixes: `feature/`, `fix/`, `refactor/`, `docs/`. Commit: `type: description`. Before PR: `pytest -m "not slow" -v` + type checks.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Port 8765 in use | `lsof -ti:8765 \| xargs kill -9` |
| Frontend tests OOM | `npm run test:memory` (2GB heap) |
| Database locked | Kill python, delete `~/.auralis/library.db` |
| Rust module missing | `cd vendor/auralis-dsp && maturin develop` |

## Reference Docs

- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md)
- [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md)
- [FIRST_TIME_SETUP.md](FIRST_TIME_SETUP.md)
