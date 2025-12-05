# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**📌 Current Version**: 1.1.0-beta.5 (Python), 1.0.0-beta.12.1 (Desktop) | **🐍 Python**: 3.13+ | **📦 Node**: 20+ LTS | **🦀 Rust**: Optional (vendor/auralis-dsp via PyO3)

**Architecture**: Hybrid Python + Rust
- Python layer: Research, orchestration, REST API, database
- Rust layer: `vendor/auralis-dsp` for performance-critical DSP (HPSS, YIN, Chroma via PyO3)
- Graceful fallback to librosa when Rust module unavailable

**Project**: Auralis - Professional music player with real-time audio enhancement (like iTunes + mastering studio)
**License**: GPL-3.0
**GitHub**: https://github.com/matiaszanolli/Auralis

**Core Principles:**
- **DRY (Don't Repeat Yourself)**: Always prioritize improving existing code rather than duplicating logic
  - Use **Utilities Pattern** when multiple modules share similar logic: Extract to static utility methods, refactor modules to thin wrappers
  - Example: Phase 7.2 consolidated 900 lines of duplicate spectrum/content analysis via SpectrumOperations + BaseSpectrumAnalyzer
- **Coverage ≠ Quality**: Test behavior and invariants, not implementation details
- **Modular Design**: Keep modules under 300 lines, one clear purpose per component
- **No Component Duplication**: Avoid "Enhanced"/"V2"/"Advanced" variants—refactor shared logic in-place instead
- **Content-Aware Processing**: Adapt DSP parameters based on source characteristics (loudness, dynamics, frequency content)
- **No Sugar-Coating, No Timelines**: Be honest about what's done vs. what's uncertain. Never suggest production readiness without validation. For audio, quality and testing are not optional—they are the foundation of improvement. No dates without confidence. Test rigorously or don't claim readiness.

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

# Frontend watch mode (lightweight)
cd auralis-web/frontend && npm test

# Specific test file
python -m pytest tests/backend/test_player.py -v
```

**Critical Ports**
- **8765**: FastAPI backend (REST API + WebSocket)
- **3000**: React development server (Vite)
- **8000**: Worker API (if running)

---

## 🎯 Common Tasks

### Via Build Scripts
| Task | Command |
|------|---------|
| Build + test + package (all platforms) | `python build_auralis.py` |
| Build (skip tests, faster) | `python build_auralis.py --skip-tests` |
| Build portable package only | `python build_auralis.py --skip-tests --portable-only` |

### Via Makefile
| Task | Command |
|------|---------|
| Show all available targets | `make help` |
| Clean build artifacts | `make clean` |
| Install dependencies | `make install` |
| Build for current platform | `make build` |
| Build fast (skip tests) | `make build-fast` |
| Build for Linux | `make build-linux` |
| Build for Windows | `make build-windows` |
| Build for macOS | `make build-macos` |
| Run backend tests | `make test` |
| Lint & check syntax | `make lint` |
| Type check Python | `make typecheck` |

### Testing & Quality
| Task | Command |
|------|---------|
| Run all backend tests | `python -m pytest tests/ -v` |
| Run fast tests only (skip slow) | `python -m pytest -m "not slow" -v` |
| Run with coverage report | `python -m pytest tests/ --cov=auralis --cov-report=html` |
| Run specific test file | `python -m pytest tests/backend/test_player.py -v` |
| Run specific test | `python -m pytest tests/backend/test_player.py::test_play_track -vv -s` |
| Frontend watch mode (lightweight) | `cd auralis-web/frontend && npm test` |
| Frontend full suite (2GB heap) | `cd auralis-web/frontend && npm run test:memory` |
| Frontend with coverage | `cd auralis-web/frontend && npm run test:coverage` |
| Type check Python | `mypy auralis/ auralis-web/backend/ --ignore-missing-imports` |
| Type check TypeScript | `cd auralis-web/frontend && npm run type-check` |
| Format Python code | `black auralis/ auralis-web/backend/` |
| Sort Python imports | `isort auralis/ auralis-web/backend/` |

### Development & Debugging
| Task | Command |
|------|---------|
| Free port 8765 (backend) | `lsof -ti:8765 \| xargs kill -9` |
| Free port 3000 (frontend) | `lsof -ti:3000 \| xargs kill -9` |
| Inspect database | `sqlite3 ~/.auralis/library.db "SELECT COUNT(*) FROM tracks;"` |
| Check Python syntax | `python -m py_compile auralis/ && python -m py_compile auralis-web/` |
| Build frontend (production) | `cd auralis-web/frontend && npm run build` |
| Update version across files | `python sync_version.py 1.1.0-beta.6` |

---

## 📁 Project Structure

### Audio Processing Engine (`auralis/`)
- **`core/`** - Master processing pipeline, HybridProcessor, streaming infrastructure
- **`dsp/`** - Digital Signal Processing: EQ (critical bands, filters, curves), Dynamics (compressor, limiter, soft clipper), Realtime Adaptive EQ
- **`analysis/`** - Audio analysis: fingerprinting (25D), spectral analysis, quality metrics, content analysis (Phase 7.2 consolidation)
  - `spectrum_analyzer.py` - Vectorized FFT-based spectrum analysis
  - `parallel_spectrum_analyzer.py` - Thread-pooled parallel spectrum analysis
  - `content_analyzer.py` - Content-aware source characteristics detection
  - Note: Heavy lifting (HPSS, YIN, Chroma extraction) delegated to `vendor/auralis-dsp` (Rust) with librosa fallback
- **`library/`** - SQLite database, repository pattern for queries, metadata management, query caching (136x speedup)
- **`player/`** - Playback engine, state management, queue handling
- **`io/`** - Multi-format audio I/O: WAV, FLAC, MP3, OGG, M4A (supports 16/24-bit PCM)
- **`optimization/`** - Performance optimizations, vectorization, memory management
- **`learning/`** - Adaptive learning system for profile selection
- **`utils/`** - Shared utilities and helpers

### Rust DSP Module (`vendor/auralis-dsp/`)
- **Language**: Rust via PyO3 bindings (optional, with graceful librosa fallback)
- **Build**: `maturin develop` (development) or `maturin build` (release)
- **Modules**:
  - **HPSS** (Harmonic/Percussive Source Separation) - Separates melodic and rhythmic content
  - **YIN** - Fundamental frequency detection for pitch analysis
  - **Chroma** - 12-bin chromatic pitch analysis for harmonic content
- **Integration**: Called from `auralis/analysis/` modules via `try_import_rust_module()`
- **Fallback**: If Rust module unavailable (compilation failed, not installed), gracefully falls back to librosa equivalents
- **Performance**: Provides 2-5x speedup for heavy DSP operations (HPSS decomposition, YIN pitch tracking)

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
  - `boundaries/` & `edge_cases/` - Edge case and limit tests (30-150 planned)
  - `integration/` - Cross-component behavior tests (85 tests)
  - `audio/` - Invariant property tests for audio processing (305 tests)
  - `mutation/` - Mutation testing (kill-testing for test quality)
  - `concurrency/` - Thread-safety and race condition tests
  - `performance/` - Performance and benchmark tests
  - `stress/` & `load_stress/` - Load and stress testing for memory/concurrency
  - `regression/` - Regression tests for previously fixed bugs
  - `security/` - OWASP Top 10 coverage (SQL injection, XSS, path traversal)
- **Pytest markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.boundary`, `@pytest.mark.invariant`, `@pytest.mark.slow`, etc.

### Build & Launch Scripts
- **`launch-auralis-web.py`** - Primary entry point for web interface development (manages backend + frontend start)
- **`build_auralis.py`** - Build system: compile, test, package for distribution
- **`sync_version.py`** - Update version numbers across all project files

---

## 🧪 Frontend Testing

- **Watch mode** (lightweight): `cd auralis-web/frontend && npm test` - For development iteration
- **Single run**: `cd auralis-web/frontend && npm run test:run` - For CI or one-off testing
- **With memory heap**: `cd auralis-web/frontend && npm run test:memory` - Full suite with 2GB heap (prevents OOM)
- **With coverage**: `cd auralis-web/frontend && npm run test:coverage` - For coverage reports
- **Type checking**: `cd auralis-web/frontend && npm run type-check` - TypeScript validation (0 critical errors)
- Import `render` from `@/test/test-utils`, use `vi.*` (Vitest, not Jest)
- Use `screen.getByRole()` or `screen.getByTestId()`, not implementation details
- API Mocking: Use MSW in `src/test/mocks/handlers.ts` with WAV format (16/24-bit PCM)
- **Known Issues**: Some tests may fail due to async cleanup and provider nesting - use `npm run test:memory` for stability

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

## 🎯 Frontend Hook Architecture

**Organization**: Hooks are organized by domain in `auralis-web/frontend/src/hooks/` (Phase 1.3 consolidation)

**Hook Categories** (organized for maintainability):
- **`usePlayer.ts`** - Playback control and state management
- **`useLibrary.ts`** - Library browsing and search
- **`usePlaylist.ts`** - Queue and playlist operations
- **`useAudio.ts`** - Audio processing and visualization
- **`useUI.ts`** - UI state (modals, sidebars, theme)
- **`useWebSocket.ts`** - WebSocket communication
- **`useKeyboardShortcuts.ts`** - Keyboard event handling
- **`useSettings.ts`** - User preferences and configuration

**Import Pattern**: Use absolute paths with `@/hooks`
```typescript
// ✅ Correct (absolute path)
import { usePlayer } from '@/hooks'
import { useLibrary } from '@/hooks'

// ❌ Wrong (relative path)
import { usePlayer } from '../../../hooks'
```

**Hook Size Limit**: Max 250 lines per hook (same as components)
- If exceeding limit, split into smaller composable hooks
- Example: `usePlayer.ts` (core) + `usePlayerQueue.ts` (queue-specific)

**Hook Testing**: Test hooks with `renderHook` from `@testing-library/react`
```typescript
const { result } = renderHook(() => usePlayer())
act(() => { result.current.play() })
expect(result.current.isPlaying).toBe(true)
```

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
- **Hooks**: Domain-organized in `hooks/` with 8 categories (Phase 1.3 consolidation)
- **Imports**: Always use absolute paths (`@/components`, `@/hooks`, `@/services`) from TypeScript path aliases
- **Build Tool**: Vite for fast development builds
- **Testing**: Vitest + React Testing Library (use `npm run test:memory` for full suite)
- **Type Safety**: 100% TypeScript (zero critical errors) - enforced via `npm run type-check`
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
  - **Repository Pattern**: Data access abstraction for testability and consistency
    - Repository classes handle all database queries: `TracksRepository`, `ArtistsRepository`, `AlbumsRepository`
    - Routers call repositories, never execute queries directly
    - Example: `repo.find_by_id(track_id)` NOT `db.execute("SELECT * FROM tracks WHERE id = ?")`
- **Async/Await**: FastAPI endpoints are async; use `async def` for all route handlers
- **Pydantic models**: Define request/response shapes, let FastAPI handle serialization
- **Error handling**: Raise `HTTPException` from `fastapi` with appropriate status codes (400, 404, 422, 500)
- **Thread safety**: All shared state (PlayerState, config) protected with `threading.RLock()`
- **Caching**: Only cache deterministic queries (no time-dependent results)—use `streamlined_cache.py`

### Frontend (React/TypeScript)
- **Imports**: Use absolute paths from TypeScript path aliases
  - ✅ `import { Button } from '@/components'`
  - ❌ `import { Button } from '../../../components'`
- **Design tokens**: ALWAYS use `import { tokens } from '@/design-system'` for colors, spacing, typography—never hardcode
- **Component structure**: Keep components < 300 lines; split responsibilities if growing larger
- **Hooks**: Domain-organized (player, library, playlist, audio, UI, WebSocket, keyboard, settings)
- **Type safety**: Enforce with `npm run type-check` - zero critical errors required
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

## 📋 Build System & Scripts

This project uses a multi-faceted build system:

### Main Build Scripts
- **`build_auralis.py`** - Production build: Runs tests, compiles code, packages for all platforms
  - `python build_auralis.py` - Full build with tests
  - `python build_auralis.py --skip-tests` - Fast build (no tests)
  - `python build_auralis.py --skip-tests --portable-only` - Portable package only
- **`launch-auralis-web.py`** - Development launcher: Starts backend + frontend with hot reload
- **`sync_version.py <version>`** - Version synchronization across all config files

### Build Tools
- **`Makefile`** - Standard targets: `make help`, `make clean`, `make build-linux`, `make build-windows`, `make build-macos`
- **Python**: `pyproject.toml` (build config), `requirements.txt` (dependencies)
- **Frontend**: `auralis-web/frontend/package.json` (npm scripts, build config)
- **Desktop**: `desktop/package.json` (Electron build config)

---

## 🔍 Advanced Debugging

### Python Debugging
```bash
# Debug a single test with breakpoints (pdb)
python -m pytest tests/backend/test_player.py::test_play_track -vv -s --pdb

# Run with detailed logging
python -m pytest tests/ -v --log-cli-level=DEBUG --log-cli-format="%(asctime)s [%(levelname)8s] %(message)s"

# Profile function execution times
python -m cProfile -s cumtime -m pytest tests/audio/test_processing.py -v

# Check for memory leaks in tests
python -m pytest tests/ -v --benchmark-only --benchmark-compare
```

### Frontend Debugging
```bash
# Run tests with detailed output and source maps
cd auralis-web/frontend && npm test -- --reporter=verbose

# Debug a specific component
cd auralis-web/frontend && npm test -- src/components/Player.test.tsx --watch

# Check bundle size
cd auralis-web/frontend && npm run build && npm run analyze-bundle

# Inspect Redux state during tests
# Add `console.log(store.getState())` in test and run with output
cd auralis-web/frontend && npm test -- --reporter=default
```

### WebSocket Debugging
```bash
# Monitor WebSocket messages in real-time
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8765/ws

# Use websocat for interactive WebSocket testing
# Install: cargo install websocat
websocat ws://localhost:8765/ws
```

### Database Debugging
```bash
# Export database for inspection
sqlite3 ~/.auralis/library.db ".dump tracks" > tracks_dump.sql

# Performance analysis
sqlite3 ~/.auralis/library.db "EXPLAIN QUERY PLAN SELECT * FROM tracks WHERE artist_id = 1;"

# Check table indexes
sqlite3 ~/.auralis/library.db ".schema tracks"

# Analyze query performance
sqlite3 ~/.auralis/library.db "PRAGMA table_info(tracks);"
```

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

### Build Rust DSP Module (Optional)
```bash
# Install Rust build tools (one time)
pip install maturin

# Development build (hot reload)
cd vendor/auralis-dsp
maturin develop

# Release build (optimized)
maturin build --release

# Build with ABI3 forward compatibility (Python version support)
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop
```

**Note**: The Rust module is optional. If not installed or compilation fails, the system gracefully falls back to librosa implementations with no loss of functionality (just slower performance on HPSS, YIN, Chroma analysis).

### Build for Release
```bash
# Full release (tests + build, all platforms)
python build_auralis.py

# Development build (skip tests)
python build_auralis.py --skip-tests

# Portable package only
python build_auralis.py --skip-tests --portable-only

# Desktop app only (Electron)
cd desktop && npm run package

# Platform-specific builds via Makefile
make build-linux      # Linux AppImage/DEB
make build-windows    # Windows .exe (Windows only)
make build-macos      # macOS .dmg (macOS only)

# Update version across files
python sync_version.py 1.1.0-beta.6
```

---

## 📝 Key Development Guidelines

### Code Organization
- **Module Size**: Keep Python modules < 300 lines, React components < 300 lines
- **Single Responsibility**: Each file has ONE purpose; split if growing too large
- **No Duplication**: Don't create "Enhanced"/"V2"/"Advanced" variants—refactor in-place
  - **Utilities Pattern**: When multiple modules have similar logic (e.g., spectrum analysis, content detection), extract to a utilities module with static methods (see Phase 7.2: SpectrumOperations + BaseSpectrumAnalyzer eliminated 900 lines of duplication)
  - **Thin Wrappers**: Once utilities extracted, module implementations become thin wrappers that delegate to the utility module
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

## 🎯 Current Development Phase

**Phase**: Frontend Enhanced Playback Controls & Streaming (1.1.0-beta.5+)

**Completed Phases**:
- ✅ **Phase 7.2**: Spectrum and Content Analysis Consolidation (eliminated 900 lines of duplicate code via Utilities Pattern)
- ✅ **Phase 8**: Preset-Aware Peak Normalization (fixed preset differentiation bug, Gentle now 0.20 dB louder than Adaptive)
- ✅ **Phase 9A**: Matchering Baseline Analysis (analyzed two Slayer albums, established content-aware scaling patterns)
- ✅ **Phase 9D**: Audio Downsampling & Energy-Adaptive LUFS (5/10 tracks within target boost range, 65 sec/track processing at 48 kHz)
- ✅ **Phase 10**: Heavy Performance Optimizations (7 major improvements: Rust tempo detection, processor caching, channel-vectorized EQ, spectral flux onset detection, limiting optimization, 27-28ms per chunk tempo detection)
- ✅ **Phase 11**: Persistent Fingerprint Cache (2GB SQLite cache, 500-1000ms savings per hit, lazy tempo detection, pre-generated preset parameters 20-40x speedup)
- ✅ **Phase 1-3 Frontend**: Hook consolidation (8 domain categories), 100% TypeScript type safety, absolute path imports (@/)

**Current Focus** (Phase 3.4 - In Progress):
- **Keyboard shortcuts for enhanced playback controls** (Phase 3.4)
- Enhanced playback UI controls (streaming progress, error boundaries, visual feedback)
- WebSocket PCM streaming infrastructure (30-second chunks, WAV PCM format)
- Design system token refinements for streaming controls
- Frontend quality improvements and design consistency across enhancement components

**Recent Frontend Work** (Phases 2.2-3.4):
- Phase 2.2: PCM streaming infrastructure via WebSocket
- Phase 2.3: `usePlayEnhanced` hook for streaming playback
- Phase 2.4: Unit tests for streaming services
- Phase 3.1: Enhanced playback UI controls component
- Phase 3.2: Streaming error boundary & progress bar components
- Phase 3.3: Integration of streaming controls into main player UI
- Phase 3.4: Keyboard shortcuts for enhanced playback controls (active)

**Research Folder**:
- Location: `research/` (excluded from git via .gitignore)
- Contains: Audio analysis data, validation scripts, baseline comparisons
- Publishing: Will be FOSS'd after paper completion (not ready for public yet)

**Key Documentation Files**:
- `PHASE_11_COMPLETION_SUMMARY.md` - Phase 11 persistent cache implementation
- `PHASE_11_HEAVY_OPTIMIZATIONS.md` - Performance optimization details
- `PERFORMANCE_OPTIMIZATIONS_IMPLEMENTED.md` - Phase 10 optimizations breakdown
- Phase 3.1-3.4 summaries - Frontend streaming architecture

---

## 🎙️ Frontend Streaming Architecture (Phases 2.2-3.4)

### WebSocket PCM Streaming
- **Protocol**: WebSocket connection via `/ws` endpoint for real-time streaming
- **Format**: 30-second WAV PCM chunks (16/24-bit, preserves sample count)
- **Features**:
  - Gapless playback via 3-second crossfade at chunk boundaries
  - Lazy loading with sample-accurate seeking
  - Real-time progress updates and error handling
  - Progress bar component (`StreamingProgressBar`)
  - Error boundary (`StreamingErrorBoundary`) for graceful error recovery

### Enhanced Playback Controls
- **Component**: `EnhancedPlaybackControls` - Streaming-specific UI controls
- **Hook**: `usePlayEnhanced` - Manages streaming playback state and WebSocket communication
- **Features**:
  - Real-time playback progress display
  - Chunk-aware position tracking
  - Error recovery and reconnection
  - Design system token integration (verified fix in recent commits)
  - Keyboard shortcut support (Phase 3.4)

### Key Files for Streaming
- `auralis-web/frontend/src/components/enhancement/` - Enhancement UI components
- `auralis-web/frontend/src/hooks/usePlayEnhanced.ts` - Streaming playback hook
- `auralis-web/frontend/src/components/enhancement/StreamingProgressBar.tsx` - Progress UI
- `auralis-web/frontend/src/components/enhancement/StreamingErrorBoundary.tsx` - Error handling
- `auralis-web/backend/routers/webm_streaming.py` - WebSocket streaming endpoint

### Design System for Streaming UI
- All streaming components use `import { tokens } from '@/design-system'`
- Color scheme, spacing, typography defined in `design-system/tokens.ts`
- Recent work fixed remaining token references in `EnhancedPlaybackControls` container

---

## 🚀 CI/CD & Automation

### GitHub Actions Workflows
Located in `.github/workflows/`:
- **`ci.yml`** - Main CI pipeline (lint, test, build checks on every push)
- **`backend-tests.yml`** - Backend test suite (850+ tests, ~2-3 minutes)
- **`frontend-build.yml`** - Frontend build verification (Vite build, type-check)
- **`desktop-build.yml`** - Desktop app builds (Electron packaging for all platforms)
- **`build-release.yml`** - Release build (full packaging, all platforms: Windows .exe, Linux AppImage/DEB, macOS .dmg)

### Pre-commit Hooks
- **`.pre-commit-config.yaml`** - Automated checks before commit:
  - Python syntax validation
  - Black code formatting
  - isort import sorting
  - mypy type checking
  - TypeScript type checking (frontend)

### Build & Release Process
- **Local development**: `python launch-auralis-web.py --dev` (hot reload)
- **Production build**: `python build_auralis.py` (runs tests + package all platforms)
- **Fast build**: `python build_auralis.py --skip-tests` (no test execution)
- **Version sync**: `python sync_version.py <version>` (updates all config files)

### Mutation Testing (Phase-specific quality assurance)
- **Config**: `.mutmut-config.py` - Mutation testing configuration
- **Purpose**: Kill-testing to verify test quality (tests catch code changes)
- **Run**: `pytest --mutate` (requires mutmut library)

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
  - `components/enhancement/` - Streaming controls, progress bar, error boundary (Phases 2.2-3.4)
  - `design-system/tokens.ts` - Single source of truth for styling

---

## 🔧 Claude Code Configuration

### Local Settings (`.claude/settings.local.json`)
Claude Code in this repository has local configuration settings that allow safe execution of common development commands:

**Permissions Allowed**:
- Git operations: `git add`, `git commit`, `git status`, `git diff`, `git log`
- Package management: `npm install`, `npm run`, `pip install`
- Python testing: `pytest`, `python -m pytest`, test discovery and execution
- Build tools: `make` targets, build scripts
- Development utilities: Type checking, formatting, linting

**Approved Commands**: See `.claude/settings.local.json` for full list of allowed commands that can be safely executed.

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
