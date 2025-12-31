# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Project**: Auralis - Professional music player with real-time audio enhancement
**Version**: 1.2.0-beta.1 | **Python**: 3.14+ | **Node**: 20+ LTS | **Rust**: Required
**License**: GPL-3.0 | **GitHub**: https://github.com/matiaszanolli/Auralis

## Quick Start

```bash
# Web interface (primary development)
pip install -r requirements.txt
python -m auralis.library.init          # First time only
python launch-auralis-web.py --dev      # Backend :8765, Frontend :3000

# Backend only
cd auralis-web/backend && python -m uvicorn main:app --reload

# Frontend only
cd auralis-web/frontend && npm install && npm run dev

# Desktop app
cd desktop && npm install && npm run dev
```

## Testing

```bash
# Backend tests (850+)
python -m pytest tests/ -v                          # All tests (~2-3 min)
python -m pytest -m "not slow" -v                   # Skip slow tests
python -m pytest tests/backend/test_player.py -v   # Single file
python -m pytest tests/path.py::test_name -vv -s   # Single test with output

# Frontend tests
cd auralis-web/frontend
npm test                    # Watch mode
npm run test:memory         # Full suite (2GB heap, recommended)
npm run test:coverage       # With coverage

# Type checking
mypy auralis/ auralis-web/backend/ --ignore-missing-imports   # Python
cd auralis-web/frontend && npm run type-check                  # TypeScript
```

## Build

```bash
# Rust DSP module (required before running)
cd vendor/auralis-dsp && maturin develop

# Release build
python build_auralis.py                    # Full (tests + package)
python build_auralis.py --skip-tests       # Fast (no tests)

# Desktop
cd desktop && npm run package              # All platforms
```

## Architecture

```
User → FastAPI (REST + WebSocket :8765) → Backend Services
                    ↓
          LibraryManager (SQLite ~/.auralis/library.db)
                    ↓
          HybridProcessor (DSP pipeline)
                    ↓
          ChunkedProcessor (30s chunks, 3s crossfade)
                    ↓
          WebSocket streaming → React Frontend (Redux)
```

### Directory Structure

| Directory | Purpose |
|-----------|---------|
| `auralis/` | Core audio engine (Python) |
| `auralis/core/` | Master processing pipeline, HybridProcessor |
| `auralis/dsp/` | EQ, dynamics, compressor, limiter |
| `auralis/analysis/` | Fingerprinting (25D), spectrum analysis |
| `auralis/library/` | SQLite database, repository pattern |
| `vendor/auralis-dsp/` | Rust DSP via PyO3 (HPSS, YIN, Chroma) - **Required** |
| `auralis-web/backend/` | FastAPI REST API + WebSocket server |
| `auralis-web/backend/routers/` | Modular route handlers |
| `auralis-web/frontend/` | React/TypeScript/Vite + Redux |
| `auralis-web/frontend/src/hooks/` | Domain-organized hooks (8 categories) |
| `auralis-web/frontend/src/design-system/` | Design tokens (single source of truth) |
| `desktop/` | Electron wrapper |
| `tests/` | 850+ tests (unit, integration, boundary, invariant) |

## Core Principles

1. **DRY**: Improve existing code rather than duplicating logic. Use Utilities Pattern for shared logic.
2. **Modular Design**: Keep modules < 300 lines, one purpose per component.
3. **No Duplication**: No "Enhanced"/"V2"/"Advanced" variants—refactor in-place.
4. **Repository Pattern**: ALL database access via `auralis/library/repositories/`, never raw SQL.
5. **Make Every Cycle Count**: Async for concurrent workloads, measure actual utilization.

## Critical Invariants (MUST NOT Break)

### Audio Processing
```python
# Sample count preservation - CRITICAL for gapless playback
assert len(output) == len(input)

# Always return NumPy arrays, never Python lists
assert isinstance(output, np.ndarray)
assert output.dtype in [np.float32, np.float64]

# Never modify audio in-place
output = audio.copy()  # Always copy before modification
```

### Player State
- Position never exceeds track duration
- Queue position always valid for queue length
- State changes are atomic (use locks)

### Database
- Connection pooling thread-safe (`pool_pre_ping=True`)
- Foreign keys always valid
- No N+1 queries (use `selectinload()`)

## Key Patterns

### Backend (Python)
- **Routers**: Each `routers/*.py` auto-included via `include_router()` pattern
- **Async**: Use `async def` for all route handlers
- **Errors**: Raise `HTTPException` with appropriate status codes
- **Thread safety**: Shared state protected with `threading.RLock()`

### Frontend (React/TypeScript)
- **Imports**: Always use `@/` absolute paths, never relative
- **Design tokens**: Always `import { tokens } from '@/design-system'`, never hardcode colors
- **Components**: < 300 lines, single responsibility
- **Testing**: Use `vi.*` (Vitest), import `render` from `@/test/test-utils`
- **Hooks**: Domain-organized in `hooks/` (player, library, enhancement, websocket, api, app, fingerprint, shared)

### Audio Processing
- Metadata first: Load sample rate, duration, channels BEFORE processing
- NumPy vectorization: Loop over chunks, not samples
- Copy semantics: `output = audio.copy()` before modifications

## Common Issues

| Problem | Solution |
|---------|----------|
| Port 8765 in use | `lsof -ti:8765 \| xargs kill -9` |
| Port 3000 in use | `lsof -ti:3000 \| xargs kill -9` |
| Backend won't start | `pip install -r requirements.txt && python -m auralis.library.init` |
| Frontend tests OOM | Use `npm run test:memory` (2GB heap) |
| Database locked | `pkill -9 python` then delete `~/.auralis/library.db` |
| Rust module missing | `cd vendor/auralis-dsp && maturin develop` |

## WebSocket Streaming

**Endpoint**: `/ws` (unified for all audio streaming)

**Client → Server**:
```json
{"type": "play_enhanced", "data": {"track_id": 123, "preset": "adaptive", "intensity": 1.0}}
```

**Server → Client**: `audio_stream_start`, `audio_chunk` (PCM base64), `audio_stream_end`, `audio_stream_error`

## Git Workflow

- **Branch from**: `master`
- **Naming**: `feature/`, `fix/`, `refactor/`, `docs/` prefixes
- **Commit format**: `type: description` (feat, fix, refactor, perf, test, docs)
- **Before PR**: Run `pytest -m "not slow" -v` and type checks

## Key Documentation

- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - Test quality standards
- [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md) - WebSocket protocol
- [FIRST_TIME_SETUP.md](FIRST_TIME_SETUP.md) - Environment setup guide

## Performance Targets

- Audio Processing: 36.6x real-time
- Library Scanning: 740+ files/second
- Query Response: < 50ms cached, < 200ms uncached
- Frontend Render: < 16ms (60 FPS)
- Memory: < 200MB idle, < 500MB at load
