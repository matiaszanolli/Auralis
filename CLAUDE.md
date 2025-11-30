# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**📌 Current Version**: 1.1.0-beta.4 | **🐍 Python**: 3.13+ | **📦 Node**: 20+ LTS

**Core Principles:**
- Always prioritize improving existing code rather than duplicating logic
- Coverage ≠ Quality: Test behavior and invariants, not implementation
- Modular design: Keep modules under 300 lines, one purpose per component
- Avoid component duplication (no "Enhanced"/"V2" variants)—refactor in-place instead

---

## 🚀 Quick Start

**Web Interface (Primary Development)**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database (first time only)
python -m auralis.library.init

# 3. Launch web interface (starts both backend + frontend)
python launch-auralis-web.py --dev
# Visits: http://localhost:8765 (backend), http://localhost:3000 (Vite dev frontend)
```

**Backend Only (API Development)**
```bash
cd auralis-web/backend
python -m uvicorn main:app --reload     # Hot reload on port 8765
# API docs: http://localhost:8765/api/docs
```

**Frontend Only (React Development)**
```bash
cd auralis-web/frontend
npm install
npm run dev                             # Vite dev server on port 3000
```

**Desktop App (Electron)**
```bash
cd desktop
npm install
npm run dev                             # Electron development mode
```

**Run Tests**
```bash
# Backend (850+ tests, ~2-3 minutes)
python -m pytest tests/ -v

# Backend - skip slow tests
python -m pytest -m "not slow" -v

# Frontend (requires memory management)
cd auralis-web/frontend && npm run test:memory

# Specific test file
python -m pytest tests/backend/test_player.py -v
```

**Critical Ports**
- **8765**: FastAPI backend (REST API + WebSocket)
- **3000**: React development server (Vite)
- **8000**: Worker API (if running)

---

## 🎯 Common Tasks

| Task | Command |
|------|---------|
| Run all backend tests | `python -m pytest tests/ -v` |
| Run with coverage | `python -m pytest tests/ --cov=auralis --cov-report=html` |
| Run specific test | `python -m pytest tests/backend/test_player.py::test_play_track -vv -s` |
| Run only fast tests | `python -m pytest -m "not slow" -v` |
| Run invariant tests | `python -m pytest -m invariant -v` |
| Run boundary tests | `python -m pytest tests/boundaries/ -v` |
| Run integration tests | `python -m pytest -m integration -v` |
| Frontend full test suite | `cd auralis-web/frontend && npm run test:memory` |
| Frontend test watch mode | `cd auralis-web/frontend && npm test` |
| Frontend coverage | `cd auralis-web/frontend && npm run test:coverage:memory` |
| Type check Python | `mypy auralis/ auralis-web/backend/ --ignore-missing-imports` |
| Type check TypeScript | `cd auralis-web/frontend && npx tsc --noEmit` |
| Check Python syntax | `python -m py_compile auralis/ && python -m py_compile auralis-web/` |
| Free port 8765 | `lsof -ti:8765 \| xargs kill -9` |
| Free port 3000 | `lsof -ti:3000 \| xargs kill -9` |
| Database inspect | `sqlite3 ~/.auralis/library.db "SELECT COUNT(*) FROM tracks;"` |
| Format Python code | `black auralis/ auralis-web/backend/` |
| Import sort | `isort auralis/ auralis-web/backend/` |

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

### System Overview
```
User (Web/Desktop) → FastAPI REST API + WebSocket → Backend Services
                         ↓
                   LibraryManager (SQLite)
                         ↓
                   HybridProcessor (DSP)
                         ↓
                   ChunkedProcessor (30s)
                         ↓
                   React Frontend (Redux state)
```

### Audio Processing Pipeline
```
Input Audio (WAV/FLAC/MP3)
    ↓
LibraryManager (loads track metadata + caching)
    ↓
HybridProcessor (master DSP pipeline)
    ├─ Realtime Adaptive EQ (critical bands)
    ├─ Dynamics (compressor + soft clipper)
    ├─ Psychoacoustic Analysis
    └─ Profile-based Enhancement (Adaptive/Gentle/Warm/Bright/Punchy)
    ↓
ChunkedProcessor (processes in 30s chunks)
    ├─ WAV PCM encoding
    ├─ 3-second crossfade at boundaries
    └─ Sample count preservation
    ↓
WebSocket streaming → Frontend (Redux state + HTML5 Audio)
```

### Key Optimizations
- **Query Caching**: 136x speedup on repeated queries (deterministic only, ~50ms uncached → <1ms cached)
- **Chunked Processing**: 30-second audio chunks in WAV PCM format prevent memory bloat
- **NumPy Vectorization**: 1.7x speedup on DSP operations (all sample loops use NumPy)
- **Thread Safety**: All shared state protected with `threading.RLock()`
- **Memory Efficiency**: Progressive streaming via HTTP Range requests, MSE buffering (500MB max)
- **Audio Quality**: Sample count always preserved, copy-on-write semantics, no in-place modifications

### Backend Architecture (FastAPI)
- **Framework**: FastAPI 0.104.0+ with Pydantic v2 for validation
- **Routers**: Modular endpoints in `routers/` auto-discovered and included in `main.py`
  - `routers/library.py` - Library scanning and metadata
  - `routers/player.py` - Playback control, state management
  - `routers/enhancement.py` - Audio processing presets
  - `routers/albums.py`, `artists.py` - Metadata browsing
  - `routers/similarity.py` - Audio fingerprinting and similarity search
  - `routers/webm_streaming.py` - Efficient WebM/Opus streaming
- **Dependency Injection**: FastAPI deps for database connections, state, caching
- **WebSocket**: Real-time player state sync via `/ws` endpoint
- **Database**: SQLite with connection pooling (repository pattern only, no raw SQL in business logic)
- **Caching**: Time-based invalidation in `streamlined_cache.py` (3-5 minute TTL)
- **Error Handling**: Custom exceptions in `routers/errors.py` with proper HTTP status codes

### Frontend Architecture (React + Redux)
- **State Management**: Redux for global player state, local React state for UI
- **Styling**: Design tokens ONLY from `src/design-system/tokens.ts` (colors, spacing, typography)
- **Components**: Keep < 300 lines, single responsibility (no "Enhanced"/"V2"/"Advanced" duplicates)
- **Build Tool**: Vite for fast development builds
- **Testing**: Vitest + React Testing Library (use `npm run test:memory` for full suite)
- **API Communication**: MSW mocks for tests, real WebSocket in production
- **Performance**: React.memo for expensive components, useCallback for handler stability

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

## 🔧 Key Patterns & Conventions

### Backend (Python)
- **Routers as modules**: Each `routers/*.py` file is auto-included in `main.py` via `include_router()` pattern
- **Database access**: ALWAYS use repository pattern (`auralis/library/repositories/*.py`), never raw SQL in business logic
- **Async/Await**: FastAPI endpoints are async; use `async def` for all route handlers
- **Pydantic models**: Define request/response shapes, let FastAPI handle serialization
- **Error handling**: Raise `HTTPException` from `fastapi` with appropriate status codes (400, 404, 422, 500)
- **Thread safety**: All shared state (PlayerState, config) protected with `threading.RLock()`
- **Caching**: Only cache deterministic queries (no time-dependent results)—use `streamlined_cache.py`

### Frontend (React/TypeScript)
- **Design tokens**: ALWAYS use `import { tokens } from '@/design-system'` for colors, spacing, typography—never hardcode
- **Component structure**: Keep components < 300 lines; split responsibilities if growing larger
- **Testing**: Use `render` from `@/test/test-utils`, use Vitest (`vi.*`), NOT Jest
- **Async/React**: Wrap state updates in `act()`, always clean up subscriptions in `afterEach`
- **WebSocket**: Listen for updates via `WebSocketContext`, clean up listeners to prevent memory leaks
- **Performance**: Use `React.memo()` for expensive components, `useCallback()` for handler stability

### Audio Processing
- **Sample count**: ALWAYS preserve `len(output) == len(input)` for gapless playback
- **NumPy only**: Return `np.ndarray`, never Python lists; use `np.float32` or `np.float64`
- **Copy semantics**: ALWAYS copy before modifying: `output = audio.copy(); output *= gain`
- **Chunk alignment**: Even sample counts for stereo: `chunk_samples % 2 == 0`
- **Metadata first**: Load sample rate, duration, channels BEFORE processing
- **Vectorization**: Loop over chunks, not samples; use NumPy operations throughout

### Testing
- **Unit tests**: Fast (< 100ms), isolated, no I/O—mark with `@pytest.mark.unit`
- **Integration tests**: Multiple components, real files/database—mark with `@pytest.mark.integration`
- **Boundary tests**: Edge cases, limits, extreme values—mark with `@pytest.mark.boundary`
- **Invariant tests**: Properties that MUST always hold—mark with `@pytest.mark.invariant`
- **Slow tests**: Tests > 5 seconds—mark with `@pytest.mark.slow`, run with `pytest -m "not slow"`
- **Frontend memory**: ALWAYS use `npm run test:memory` for full suite (2GB heap prevents OOM)

---

## ⚠️ Common Issues & Fixes

| Problem | Solution |
|---|---|
| Port 8765 in use | `lsof -ti:8765 \| xargs kill -9` |
| Port 3000 in use (Vite) | `lsof -ti:3000 \| xargs kill -9` |
| Backend won't start | `pip install -r requirements.txt && python -m auralis.library.init` |
| Missing audio library | `python -c "import audioread; print(audioread.get_backends())"` |
| Frontend blank page | Check backend health: `curl http://localhost:8765/api/health` |
| WebSocket connection fails | Verify backend on 8765, check CORS and `/ws` endpoint |
| Frontend tests OOM | Use `npm run test:memory` (2GB heap with garbage collection) |
| Async test failures | Wrap state updates with `act()`, clean up listeners in `afterEach` |
| Hardcoded colors in UI | Use `import { tokens } from '@/design-system'` instead |
| Tests hanging | Run `pytest -m "not slow" -v` to skip tests > 5 seconds |
| Database locked | `pkill -9 python` then delete `~/.auralis/library.db` (will rescan) |
| Audio distortion/clipping | Check gain before hard limiter in `HybridProcessor.process()` |
| Gap between chunks | Verify crossfade duration in `ChunkedProcessor` (default 3.0s) |
| Component test flakes | Add proper cleanup: unsubscribe, cancel timers, unmount providers |

---

## 🔨 Build & Debugging

### Development Mode
```bash
# 🎯 Recommended: Full web interface with hot reload
python launch-auralis-web.py --dev
# Watches backend (http://8765) and frontend (http://3000 via Vite)

# Backend only with hot reload
cd auralis-web/backend && python -m uvicorn main:app --reload

# Frontend only with hot reload
cd auralis-web/frontend && npm run dev
```

### Testing & Debugging
```bash
# Run specific test with output (debugging)
python -m pytest tests/backend/test_player.py::test_play_track -vv -s --tb=short

# Run tests matching pattern with marker
python -m pytest tests/ -k "audio" -m invariant -vv

# Run with coverage report
python -m pytest tests/ --cov=auralis --cov-report=html

# Profile audio processing performance
python -m cProfile -s cumtime -m pytest tests/performance/test_streaming.py

# Run with detailed logging
python -m pytest tests/ -v --log-cli-level=DEBUG
```

### Database Inspection
```bash
# SQLite shell
sqlite3 ~/.auralis/library.db

# Check track count
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) FROM tracks;"

# List tables
sqlite3 ~/.auralis/library.db ".tables"

# Show schema
sqlite3 ~/.auralis/library.db ".schema tracks"

# Query with formatting
sqlite3 ~/.auralis/library.db ".headers on" ".mode column" "SELECT * FROM tracks LIMIT 5;"
```

### API Inspection
```bash
# API documentation (when backend running)
curl http://localhost:8765/api/docs

# Health check
curl http://localhost:8765/api/health

# Test WebSocket connection
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8765/ws

# List library files
curl http://localhost:8765/api/library/files | python -m json.tool
```

### Type Checking
```bash
# Type check Python (backend + library)
mypy auralis/ auralis-web/backend/ --ignore-missing-imports

# Type check TypeScript (frontend)
cd auralis-web/frontend && npx tsc --noEmit
```

### Code Quality
```bash
# Syntax check (all Python)
python -m py_compile auralis/ auralis-web/

# Format Python code
black auralis/ auralis-web/backend/

# Sort imports
isort auralis/ auralis-web/backend/

# Make target for linting
make lint      # Basic syntax check
make typecheck # mypy type checking (if available)
```

### Build for Release
```bash
# Full release (tests + build, all platforms)
make release

# Development build (skip tests)
make build-fast

# Desktop app only (Electron)
cd desktop && npm run package

# Platform-specific builds
make build-linux      # Linux AppImage/DEB
make build-windows    # Windows .exe (Windows only)
make build-macos      # macOS .dmg (macOS only)

# Update version across files
python sync_version.py 1.1.0-beta.4
```

---

## 📝 Key Development Guidelines

### Code Organization
- **Module Size**: Keep Python modules < 300 lines, React components < 300 lines
- **Single Responsibility**: Each file has ONE purpose; split if growing too large
- **No Duplication**: Don't create "Enhanced"/"V2"/"Advanced" variants—refactor in-place
- **Database Access**: Repository pattern ONLY (`auralis/library/repositories/`), never raw SQL in business logic
- **No Premature Abstraction**: Don't create helpers for one-time operations
- **Clear naming**: Use descriptive names that make purpose obvious without comments

### Audio Processing
- **Metadata first**: Load sample rate, duration, channels BEFORE processing
- **Chunk processing**: Use ChunkedProcessor (30s default) to manage memory and prevent bloat
- **Input validation**: Check arrays non-empty, correct dtype (float32/float64), all finite values
- **NumPy only**: Use vectorized operations throughout; loop over chunks, not samples
- **Thread safety**: All shared state protected with `threading.RLock()`
- **Sample preservation**: ALWAYS `assert len(output) == len(input)` for gapless playback
- **Copy semantics**: Never modify in-place; use `output = audio.copy()` before operations

### Frontend Components
- **Testing**: Import `render` from `@/test/test-utils`, use `vi.*` (Vitest NOT Jest)
- **Selectors**: Use `screen.getByRole()` or `screen.getByTestId()`, not implementation details
- **Cleanup**: Always clean up subscriptions, timers, observers in `afterEach()`
- **Async wrapping**: Use `act()` for all state updates in tests
- **Design system**: Import `tokens` from `@/design-system/tokens.ts`, NEVER hardcode colors/spacing
- **Performance**: Use `React.memo()` for expensive renders, `useCallback()` for handler stability
- **WebSocket**: Clean up listeners in `afterEach()` to prevent memory leaks

### API Endpoints (FastAPI)
- **Validation**: Use Pydantic models for request/response shapes
- **Status codes**: Return appropriate codes (400=bad input, 404=not found, 422=validation, 500=server error)
- **File uploads**: Validate format, size, sample rate BEFORE processing
- **Streaming**: Stream large responses (audio, lists > 1000 items) to prevent memory bloat
- **Error handling**: Use custom exceptions with descriptive messages
- **Documentation**: Document complex endpoints; WebSocket flows go in [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md)
- **Async**: Use `async def` for all route handlers to prevent blocking

### Testing Standards
- **Unit Tests**: Fast (< 100ms), isolated, no I/O—mark with `@pytest.mark.unit`
- **Integration Tests**: Multiple components, real files/database, < 5s—mark with `@pytest.mark.integration`
- **Boundary Tests**: Edge cases, limits, extreme values—mark with `@pytest.mark.boundary`
- **Invariant Tests**: Properties that MUST ALWAYS hold—mark with `@pytest.mark.invariant` (MOST IMPORTANT)
- **Slow Tests**: > 5 seconds—mark with `@pytest.mark.slow`, skip with `pytest -m "not slow"`
- **Frontend**: Use `npm run test:memory` for full suite (2GB heap prevents OOM)
- **Coverage**: Coverage ≠ Quality—focus on testing behavior and invariants, not implementation

### Git Workflow
- **Branch from**: Always branch from `master` (main branch)
- **Commit format**: `type: description` (e.g., `fix: Resolve audio gap in ChunkedProcessor`)
  - Types: `feat` (new feature), `fix` (bug fix), `refactor` (code structure), `perf` (optimization), `test` (test-only), `docs` (documentation)
- **Commit scope**: Keep commits focused on one logical change
- **Merge strategy**: Squash merge to `master` when PR approved (keeps history clean)

---

## 📚 Key Documentation

### Core Development Docs (MANDATORY READ)
- **[docs/development/TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md)** - Test quality standards & invariant testing philosophy
- **[DEVELOPMENT_SETUP_BACKEND.md](DEVELOPMENT_SETUP_BACKEND.md)** - Backend environment setup guide
- **[DEVELOPMENT_SETUP_FRONTEND.md](DEVELOPMENT_SETUP_FRONTEND.md)** - Frontend environment setup guide
- **[DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md)** - Complete coding standards (Python & TypeScript)

### Architecture & API Docs
- **[auralis-web/backend/WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md)** - WebSocket protocol and real-time endpoints
- **[ADAPTIVE_MASTERING_SYSTEM.md](ADAPTIVE_MASTERING_SYSTEM.md)** - Audio enhancement DSP algorithms and profiles
- **[CRITICAL_OPTIMIZATIONS_IMPLEMENTED.md](CRITICAL_OPTIMIZATIONS_IMPLEMENTED.md)** - Performance optimization details

### Project Direction
- **[README.md](README.md)** - User-facing project overview
- **[DEVELOPMENT_ROADMAP_1_1_0.md](DEVELOPMENT_ROADMAP_1_1_0.md)** - Current phase and feature roadmap
- **[docs/README.md](docs/README.md)** - Complete documentation index

### Frontend Components (Reference)
- **[auralis-web/frontend/](auralis-web/frontend/)** - React component library organized by feature
  - `components/shared/` - Reusable UI components
  - `components/library/` - Library browsing components
  - `components/player/` - Player controls
  - `design-system/tokens.ts` - Single source of truth for styling

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
