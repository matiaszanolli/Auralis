# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**📌 Version**: 1.1.0-beta.2 | **🐍 Python**: 3.13+ | **📦 Node**: 24+

**Core Principles:**
- Always prioritize improving existing code rather than duplicating logic
- Coverage ≠ Quality: Test behavior and invariants, not implementation
- Modular design: Keep modules under 300 lines, one purpose per component

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Web interface (recommended)
python launch-auralis-web.py --dev    # http://localhost:8765

# Desktop app
cd desktop && npm install && npm run dev

# Backend only (with hot reload)
cd auralis-web/backend && python -m uvicorn main:app --reload

# Run tests
python -m pytest tests/ -v                         # Backend (850+ tests)
cd auralis-web/frontend && npm run test:memory    # Frontend (use memory flag!)
```

**Critical Ports:** 8765 (Backend), 3000 (Frontend dev Vite), 8000 (Worker API)

---

## 🎯 Common Tasks

| Task | Command |
|------|---------|
| Run all backend tests | `python -m pytest tests/ -v` |
| Run invariant tests | `python -m pytest -m invariant -v` |
| Skip slow tests | `python -m pytest -m "not slow" -v` |
| Run specific test | `python -m pytest tests/backend/test_player.py::test_play_track -vv -s` |
| Run boundary tests | `python -m pytest tests/boundaries/ -v` |
| Frontend memory tests | `cd auralis-web/frontend && npm run test:memory` |
| Type check backend | `mypy auralis/ auralis-web/backend/` |
| Lint Python | `python -m py_compile auralis_gui.py && find auralis/ -name "*.py" -exec python -m py_compile {} \;` |
| Free port 8765 | `lsof -ti:8765 \| xargs kill -9` |
| Database inspect | `sqlite3 ~/.auralis/library.db "SELECT COUNT(*) FROM tracks;"` |

---

## 📁 Project Structure

### Audio Processing Engine (`auralis/`)
- **`core/`** - Master processing pipeline, HybridProcessor, streaming infrastructure
- **`dsp/`** - Digital Signal Processing: EQ (critical bands, filters, curves), Dynamics (compressor, limiter, soft clipper), Realtime Adaptive EQ
- **`analysis/`** - Audio analysis: fingerprinting (25D), spectral analysis, quality metrics, content analysis
- **`library/`** - SQLite database, repository pattern for queries, metadata management, query caching (136x speedup)
- **`player/`** - Playback engine, state management, queue handling
- **`io/`** - Multi-format audio I/O: WAV, FLAC, MP3, OGG, M4A (supports 16/24-bit PCM)
- **`optimization/`** - Performance optimizations, vectorization, memory management
- **`learning/`** - Adaptive learning system for profile selection
- **`utils/`** - Shared utilities and helpers

### Web Interface (`auralis-web/`)
- **`backend/`** - FastAPI REST API + WebSocket server
  - `main.py` - Entry point, router integration, health checks
  - `routers/` - Modular route handlers (auto-included in main.py)
  - `chunked_processor.py` - Streaming audio processing (30s chunks, WAV PCM)
  - `streamlined_cache.py` - Query caching with time-based invalidation
  - `state_manager.py` - Player state synchronization
  - `processing_engine.py` - Real-time audio DSP processing
  - `webm_encoder.py` - WebM/Opus encoding for efficient streaming
- **`frontend/`** - React/TypeScript/Vite + Redux
  - `components/` - React components (keep < 300 lines, one purpose each)
  - `design-system/tokens.ts` - Single source of truth for colors, spacing, typography
  - `contexts/` - Redux store, WebSocket context, player context
  - `hooks/` - Custom hooks (infinite scroll, playback, state management)
  - `services/` - API calls, WebSocket communication
  - `test/` - Test utilities, mocks, setup

### Desktop App (`desktop/`)
- Electron wrapper for native platform integration
- IPC bridge via preload.js
- Cross-platform builds: Windows (.exe), Linux (AppImage/DEB), macOS

### Tests (`tests/`)
- **850+ automated tests** organized by category:
  - `auralis/` - Core audio engine tests
  - `backend/` - FastAPI endpoint tests
  - `boundaries/` - Edge case and limit tests (30-150 planned)
  - `integration/` - Cross-component behavior tests (85 tests)
  - `audio/` - Invariant property tests for audio processing (305 tests)
  - `mutation/` - Mutation testing (kill-testing for test quality)
  - `concurrency/` - Thread-safety and race condition tests
  - `performance/` - Performance and benchmark tests
  - `security/` - OWASP Top 10 coverage (SQL injection, XSS, path traversal)
- **Pytest markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.boundary`, `@pytest.mark.invariant`, etc.

---

## 🧪 Frontend Testing

- **ALWAYS** use `npm run test:memory` for full suite (2GB heap prevents OOM)
- Import `render` from `@/test/test-utils`, use `vi.*` (Vitest not Jest)
- Use `screen.getByRole()` or `screen.getByTestId()`, not implementation details
- API Mocking: Use MSW in `src/test/mocks/handlers.ts` with WAV format (16/24-bit PCM)

## 🎨 Design System (MANDATORY)

**Single Source of Truth**: `auralis-web/frontend/src/design-system/tokens.ts`

```typescript
import { tokens } from '@/design-system'
// ✅ Use design system tokens
<div style={{ color: tokens.colors.text.primary, padding: tokens.spacing.md }}>
// ❌ Never hardcode colors
<div style={{ color: '#ffffff', padding: '16px' }}>
```

**Component Guidelines**: Keep < 300 lines, one purpose per component, no "Enhanced"/"V2" duplicates

---

## 🏗️ Architecture

### Data Flow
```
LibraryManager (SQLite)
    ↓ (cached queries)
HybridProcessor (DSP pipeline)
    ├─ Realtime Adaptive EQ
    ├─ Dynamics Processing
    ├─ Psychoacoustic Analysis
    └─ Profile-based Enhancement (Adaptive/Gentle/Warm/Bright/Punchy)
    ↓
ChunkedProcessor (30s WAV PCM)
    ↓ (WebSocket streaming)
Frontend React App (Redux state)
    ↓ (user interaction)
FastAPI REST + WebSocket API
```

### Key Optimizations
- **Query Caching**: 136x speedup on repeated queries (deterministic only)
- **Chunked Processing**: 30-second audio chunks in WAV PCM format
- **NumPy Vectorization**: 1.7x speedup on DSP operations
- **Thread Safety**: All shared state protected with `threading.RLock()`
- **Memory Efficiency**: Progressive streaming, MSE (Media Source Extensions) buffering
- **Audio Quality**: Preserves sample count, prevents in-place modifications, uses copy-on-write

### Backend Architecture
- **Framework**: FastAPI with Pydantic v2 for validation
- **Routers**: Modular endpoints auto-discovered and included in `main.py`
- **Dependency Injection**: FastAPI deps for database, auth, state management
- **WebSocket**: Real-time player state sync, audio streaming
- **Database**: SQLite with connection pooling, repository pattern only (no direct SQL)
- **Caching**: Time-based invalidation in `streamlined_cache.py`

### Frontend Architecture
- **State Management**: Redux for global player state, local component state for UI
- **Styling**: Design tokens in `tokens.ts` (no hardcoded colors/spacing)
- **Components**: Max 300 lines, single responsibility, no "Enhanced"/"V2" duplicates
- **Testing**: Vitest + React Testing Library, memory-managed test runs
- **API Communication**: MSW mocks for tests, real WebSocket in production

---

## 🚨 Critical Invariants (MUST NOT Break)

### Audio Processing
```python
# Sample count preservation - CRITICAL for gapless playback
assert len(output) == len(input)

# Always return NumPy arrays (never Python lists)
assert isinstance(output, np.ndarray)
assert output.dtype in [np.float32, np.float64]

# Never modify audio in-place (prevents corruption)
output = audio.copy()  # Always copy before modification
output *= gain
output[:] = new_data  # Never audio[:] = for direct assignment

# Chunk boundaries must align (prevent gaps/fuzz)
chunk_samples = int(sample_rate * chunk_duration)
assert chunk_samples % 2 == 0  # Even samples for stereo
```

### Player State
- Position never exceeds track duration (enforce with `min(position, duration)`)
- Queue position always valid for current queue length (bounds check on changes)
- State changes are atomic (use locks for multi-step updates)
- WebSocket updates ordered (sequence numbers or queue-based delivery)
- Playback state never contradicts audio state (sync on every update)

### Database
- Track metadata immutable after insert (use schema constraints)
- Connection pooling thread-safe (SQLAlchemy `pool_pre_ping=True`)
- Queries cached only when deterministic (no time-dependent queries)
- Foreign keys always valid (enable SQLite `PRAGMA foreign_keys`)
- No N+1 queries (always join or use `selectinload()`)

### WebSocket
- Messages ordered (no race conditions on position/state)
- Subscriptions cleaned up on disconnect (prevent memory leaks)
- Backpressure handled (don't buffer unlimited messages)

---

## ⚠️ Common Issues & Fixes

| Problem | Solution |
|---|---|
| Port 8765 in use | `lsof -ti:8765 \| xargs kill -9` |
| Port 3000 in use (Vite frontend) | `lsof -ti:3000 \| xargs kill -9` |
| Backend won't start | `pip install -r requirements.txt` |
| Missing audioread backend | `python -c "import audioread; print(audioread.get_backends())"` |
| Frontend blank page | Check backend: `curl http://localhost:8765/api/health` |
| WebSocket connection fails | Ensure backend running on 8765, check CORS in `main.py` |
| Frontend tests OOM | Use `npm run test:memory` (2GB heap with GC) |
| Async test failures | Wrap state updates with `act()`, clean up subscriptions in afterEach |
| Hardcoded colors in UI | Use `import { tokens } from '@/design-system'` instead |
| Tests hanging | Run `pytest -m "not slow" -v` to skip slow tests (~5s+ tests) |
| Database locked | `pkill -9 python && rm ~/.auralis/library.db` (will rescan) |
| Audio distortion/clipping | Check gain applied before hard limiter in HybridProcessor |
| Gap between chunks | Verify crossfade parameters in ChunkedProcessor (default 3s) |

---

## 🔨 Build & Debugging

### Build Commands
```bash
# Full release build (with tests, all platforms)
make release

# Development build (skip tests, local only)
make build-fast

# Desktop installers only (Windows .exe, Linux deb/AppImage)
make package

# Platform-specific builds
make build-linux      # Linux packages
make build-windows    # Windows packages (Windows only)
make build-macos      # macOS packages (macOS only)

# Docker build (if needed)
make docker-build

# Update version across all files
python sync_version.py 1.1.0-beta.2
```

### Debug & Inspection
```bash
# Backend with verbose logging
DEBUG=1 python launch-auralis-web.py --dev

# Frontend with Vite debug logging
cd auralis-web/frontend && VITE_LOG=debug npm start

# API documentation (when running)
curl http://localhost:8765/api/docs

# Database inspection
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) FROM tracks;"
sqlite3 ~/.auralis/library.db ".tables"
sqlite3 ~/.auralis/library.db ".schema tracks"

# Run single test with output
python -m pytest tests/backend/test_player.py::test_play_track -vv -s

# Run tests matching pattern with markers
python -m pytest tests/ -k "audio" -m invariant -vv

# Profile audio processing performance
python -m cProfile -s cumtime -m pytest tests/performance/test_streaming.py

# Check WebSocket connection
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8765/ws
```

### Type Checking
```bash
# Type check Python backend
mypy auralis/ auralis-web/backend/ --ignore-missing-imports

# TypeScript type checking (frontend)
cd auralis-web/frontend && npx tsc --noEmit
```

### Linting & Code Quality
```bash
# Lint Python (check syntax)
make lint

# Lint with mypy (if available)
make typecheck

# Format Python code (if black installed)
black auralis/ auralis-web/backend/
isort auralis/ auralis-web/backend/
```

---

## 📝 Key Development Guidelines

### Code Organization
- **Module Size**: Keep Python modules < 300 lines, React components < 300 lines
- **One Component Per Purpose**: Don't create "Enhanced"/"V2"/"Advanced" duplicates—refactor in-place
- **Database Access**: Repository pattern ONLY (`auralis/library/repositories/`), never raw SQL in business logic
- **No Premature Abstraction**: Don't create helpers for single-use operations

### Audio Processing
- Always handle metadata BEFORE processing: sample rate, duration, channels
- Process in chunks appropriate to the algorithm (ChunkedProcessor uses 30s default)
- Validate input arrays: non-empty, correct dtype (float32/float64), finite values
- Use NumPy operations (vectorized), avoid Python loops for samples
- Thread-safe: All shared state protected with locks

### Frontend Components
- Import `render` from `@/test/test-utils`, use `vi.*` (Vitest not Jest)
- Use `screen.getByRole()` or `screen.getByTestId()`, not implementation details
- Always clean up subscriptions in `afterEach` (WebSocket, timers, observers)
- Use `act()` wrapper for state updates in tests
- Design tokens ONLY from `@/design-system/tokens.ts`

### API Endpoints (FastAPI)
- Use Pydantic models for request/response validation
- Document WebSocket flows in [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md)
- Return appropriate status codes (400, 404, 422, 500)
- Validate file uploads: format, size, sample rate
- Stream large responses (audio, lists > 1000 items)

### Testing
- **Unit**: Fast, isolated, no I/O (< 100ms)
- **Integration**: Multiple components, real file I/O, real database (< 5s)
- **Boundary**: Edge cases, limits, extreme values (tag with `@pytest.mark.boundary`)
- **Invariant**: Properties that MUST always hold (tag with `@pytest.mark.invariant`)
- **Mutation**: Designed to kill specific bugs (tag with `@pytest.mark.mutation`)
- Use markers: `@pytest.mark.unit`, `@pytest.mark.slow`, `@pytest.mark.audio`, etc.

### Git Workflow
- Branch from `master` (main branch)
- Commit message format: `type: description` (e.g., `feat: Add audio fingerprinting`)
  - Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`
- Keep commits focused (one feature/fix per commit)
- Squash merge to `master` when PR approved

---

## 📚 Key Documentation

- **[TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md)** - Test quality standards (MANDATORY READ)
- **[WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md)** - WebSocket protocol and endpoints
- **[README.md](README.md)** - User-facing documentation
- **[docs/README.md](docs/README.md)** - Full documentation index
- **[DEVELOPMENT_ROADMAP_1_1_0.md](DEVELOPMENT_ROADMAP_1_1_0.md)** - Planned features and direction

---

## 💾 Repository Info

- **Git**: Branch `master` (main branch for PRs)
- **License**: GPL-3.0 (see LICENSE for details)
- **GitHub**: https://github.com/matiaszanolli/Auralis
- **API Docs** (when running): http://localhost:8765/api/docs
- **Issue Tracking**: GitHub Issues for bugs and features

---

## 🎯 Performance Targets

- **Audio Processing**: 36.6x real-time (10 seconds audio in < 275ms)
- **Library Scanning**: 740+ files/second
- **Query Response**: < 50ms (cached), < 200ms (uncached)
- **WebSocket Messages**: < 10ms delivery with ordering
- **Frontend Render**: < 16ms (60 FPS target)
- **Memory Usage**: < 200MB idle, < 500MB at full load
