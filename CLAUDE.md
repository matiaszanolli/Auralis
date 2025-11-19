# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Project-Specific Guidance**: This CLAUDE.md contains Auralis-specific development guidelines. For user-specific preferences across all projects, see `~/.claude/CLAUDE.md`.

**Key Project Principles:**
- Always prioritize improving existing code rather than duplicating logic
- Coverage ≠ Quality: Test behavior and invariants, not implementation
- Modular design: Keep modules under 300 lines, use facade pattern for backward compatibility

---

## 🚀 Quick Reference Card

| Task | Command | Notes |
|------|---------|-------|
| **Start development** | `python launch-auralis-web.py --dev` | Backend + frontend dev servers |
| **Frontend tests** | `npm run test:memory` (from frontend/) | ⚠️ ALWAYS use for full suite (2GB heap) |
| **Backend tests** | `python -m pytest tests/ -v` | 850+ tests, use -m flags to filter |
| **Run backend only** | `cd auralis-web/backend && python -m uvicorn main:app --reload` | Swagger UI: http://localhost:8765/api/docs |
| **Desktop app** | `cd desktop && npm run dev` | Full stack + Electron |
| **Type check** | `mypy auralis/ auralis-web/backend/` | Python type validation |
| **Free port 8765** | `lsof -ti:8765 \| xargs kill -9` | If backend won't start |

**Critical Ports:**
- **8765** = Backend API (NOT 8000!)
- **3000** = Frontend dev server (proxies to 8765)
- **8000** = Worker project (if applicable, separate repo)

---

## ⚡ Quick Start (30 seconds)

**Web Interface (recommended for development):**
```bash
pip install -r requirements.txt
python launch-auralis-web.py --dev    # http://localhost:8765
```

**Desktop Application (full stack):**
```bash
pip install -r requirements.txt && cd desktop && npm install
npm run dev                           # Starts backend + frontend + Electron
```

**Run Tests:**
```bash
python -m pytest tests/ -v                    # All tests
cd auralis-web/frontend && npm run test:memory  # Frontend tests (memory safe)
```

---

## 🎯 Common Development Tasks

### Running the Application

**Web Interface:**
```bash
# Development mode (auto-reloads, http://localhost:8765)
python launch-auralis-web.py --dev

# Production mode (serves built frontend from backend)
python launch-auralis-web.py

# Backend only (FastAPI with Swagger UI at http://localhost:8765/api/docs)
cd auralis-web/backend && python -m uvicorn main:app --reload --port 8765
```

**Desktop Application (Electron):**
```bash
cd desktop

# Development mode (starts backend + frontend dev server + Electron window)
npm run dev

# Build for production (all platforms: Linux, Windows, macOS)
npm run package

# Platform-specific builds
npm run package:linux   # Linux AppImage + DEB
npm run package:win     # Windows installer (requires Windows)
npm run package:mac     # macOS app (requires macOS)
```

**Frontend Separately (debugging):**
```bash
# Requires backend running on port 8765
cd auralis-web/frontend && npm start   # Dev server at http://localhost:3000 (proxies to backend)
```

### Running Tests
```bash
# All tests
python -m pytest tests/ -v

# Specific categories
python -m pytest tests/backend/ -v                    # API endpoints (96 tests)
python -m pytest tests/auralis/ -v                    # Audio processing (24 tests)
python -m pytest tests/boundaries/ -v                 # Boundary conditions (151 tests)
python -m pytest tests/integration/ -v                # Integration tests (85 tests)
python -m pytest tests/invariants/ -v                 # Critical invariants (305 tests)
python -m pytest tests/mutation/ -v                   # Mutation tests (quality validation)

# Run with coverage
python -m pytest tests/ --cov=auralis --cov=auralis-web --cov-report=html

# Run single test file
python -m pytest tests/backend/test_player.py -v

# Run single test
python -m pytest tests/backend/test_player.py::test_play_track -v

# Run tests matching pattern
python -m pytest -k "test_enhance" -v

# Run tests by marker
python -m pytest -m "invariant" -v     # Invariant tests only
python -m pytest -m "boundary" -v      # Boundary tests only
python -m pytest -m "not slow" -v      # Skip slow tests
```

**⚠️ Test Collection Performance Note:**
- Test collection is fast (< 10 seconds) thanks to fixes in Nov 2024
- Fixed issues: Import typos in repository files + O(n) collection hook
- If collection becomes slow again (30+ min), check:
  - `tests/conftest.py` - `pytest_collection_modifyitems()` hook (disabled for performance)
  - `auralis/library/repositories/*.py` - Import statements use `from auralis.library.repositories import X`
  - Run with `--collect-only -q` to isolate collection issues

### Making Code Changes

**Backend API (FastAPI):**
```bash
# 1. Edit endpoint in auralis-web/backend/routers/*.py
# 2. Run affected tests
python -m pytest tests/backend/ -v
# 3. Test manually at http://localhost:8765/api/docs (Swagger UI)
# 4. Backend auto-reloads with --reload flag
```

**Core Audio Processing:**
```bash
# 1. Edit in auralis/core/ or auralis/dsp/
# 2. Run core tests
python -m pytest tests/auralis/ -v
# 3. Run validation tests
python -m pytest tests/validation/ -v
# 4. Check performance impact
python benchmark_performance.py
```

**Frontend (React/TypeScript):**
```bash
# 1. Edit in auralis-web/frontend/src/
# 2. Dev server auto-reloads
cd auralis-web/frontend

# Running tests (use test:memory for full suite to avoid OOM)
npm test                                  # Interactive test mode (light)
npm run test:run                          # Single test run (fast)
npm run test:memory                       # Full suite with memory management (RECOMMENDED)
npm run test:coverage                     # Coverage report (light, watch mode)
npm run test:coverage:memory              # Coverage + memory management
npm run build                             # Production build

# Run specific frontend test files
npm test -- src/components/library/__tests__/CozyAlbumGrid.test.tsx
npm test -- EnhancementPaneV2             # Partial filename match
```

**Frontend Test Guidelines (CRITICAL - Read This!):**
1. ⚠️ **Memory Management**: Always use `npm run test:memory` for full test runs (2GB heap + GC)
2. ⚠️ **Provider Wrapper**: ALWAYS import render from `@/test/test-utils`, NOT from `@testing-library/react`
   - Provides: Router, DragDrop, WebSocket, Theme, Enhancement, Toast providers
   - Never wrap components with custom Wrapper - use test-utils instead
3. ⚠️ **API Mocking**: Use MSW (handlers in `src/test/mocks/handlers.ts`) - never fetch() mocks
4. ⚠️ **Async Operations**: Use `waitFor(() => expect(...))` from test-utils, NEVER hardcoded `setTimeout`
5. ⚠️ **Vitest Syntax**: Use `vi.mock()`, `vi.fn()`, NOT `jest.*` (setup.ts provides compatibility layer)
6. File size: Keep under 400 lines (split if needed), use test template at `src/test/TEMPLATE.test.tsx`
7. Selectors: Use `screen.getByRole()` or `screen.getByTestId()` (avoid querySelector)
8. Cleanup: Automatic via setup.ts (no manual afterEach needed)
9. Recent fixes: Last 5+ commits fixed selector/assertion issues - follow existing test patterns in library/
10. See [FRONTEND_TEST_MEMORY_IMPROVEMENTS_APPLIED.md](docs/guides/FRONTEND_TEST_MEMORY_IMPROVEMENTS_APPLIED.md)

### Code Quality
```bash
# Type checking
mypy auralis/ auralis-web/backend/

# Linting
python -m lint auralis/ auralis-web/backend/

# Code formatting (if set up)
black auralis/ auralis-web/backend/
```

### Building & Packaging
```bash
# Build desktop app for all platforms
make build                  # Runs tests + builds (see Makefile for details)

# Build without tests (faster)
make build-fast

# Package only (for distribution)
make package

# Platform-specific builds
make build-linux
make build-windows          # Windows only
make build-macos            # macOS only

# Clean build artifacts
make clean
```

---

## 📁 Project Structure

**Core Audio Engine** (`auralis/`):
- `core/` - Main processing engine (adaptive mastering, reference mode, hybrid mode)
- `dsp/` - Digital signal processing modules (EQ, dynamics, filtering)
  - `eq/` - 26-band psychoacoustic EQ system
  - `dynamics/` - Compression, limiting, envelope following
  - `utils/` - Audio utilities (normalization, gain, stereo processing)
- `analysis/` - Audio analysis framework (spectrum, loudness, quality metrics)
  - `fingerprint/` - 25D audio fingerprint system (NEW)
  - `ml/` - Machine learning genre classification
  - `quality/` - Quality metrics (frequency response, dynamic range, etc.)
- `library/` - Library management with SQLite backend
  - `repositories/` - Data access layer with pagination support
  - `cache.py` - Query result caching (136x speedup on cache hits)
- `player/` - Audio playback engine with real-time processing
- `io/` - Audio file I/O and format handling
- `optimization/` - Performance optimizations (Numba JIT, NumPy vectorization)

**Web Interface** (`auralis-web/`):
- `backend/` - FastAPI server (614 lines, modular routers)
  - `main.py` - FastAPI app initialization and routes
  - `routers/` - Modular endpoint handlers (player, library, enhancement, etc.)
  - `chunked_processor.py` - Streaming audio processor (30s chunks)
  - `streaming/` - MSE + Multi-Tier Buffer streaming system
- `frontend/` - React/TypeScript UI
  - `components/` - Main UI components (player, library, enhancement panel)
  - `hooks/` - Custom React hooks (player logic, library data, etc.)
  - `services/` - API communication layer
  - `design-system/` - Design tokens and reusable UI primitives

**Desktop Application** (`desktop/`):
- `main.js` - Electron main process (spawns backend, loads frontend)
- `preload.js` - IPC bridge for native file selection

**Tests** (`tests/`):
- `backend/` - API endpoint tests (96 tests, 74% coverage)
- `auralis/` - Audio processing tests (24 tests)
- `boundaries/` - Edge case and boundary tests (151 tests)
- `concurrency/` - Thread-safety and race condition tests
- `edge_cases/` - Complex edge cases and corner conditions
- `integration/` - Cross-component integration tests (85 tests)
- `invariants/` - Critical invariant tests (305 tests)
- `load_stress/` - Load and stress testing (large datasets)
- `mutation/` - Mutation testing for test quality validation
- `performance/` - Performance benchmarks and regression tests
- `regression/` - Regression test suite
- `security/` - Security and OWASP Top 10 tests
- `conftest.py` - Pytest fixtures and configuration

**Frontend Tests** (`auralis-web/frontend/src/`):
- **Total**: 60 test files across components, services, hooks, contexts, and integrations
- **Organization**: Co-located `__tests__/` subdirectories next to source files
- **Test Infrastructure**:
  - `test/setup.ts` - Global environment, polyfills, cleanup (131 lines)
  - `test/test-utils.tsx` - Custom render() with all providers (71 lines)
  - `test/mocks/` - MSW server (12 lines), handlers (80+ endpoints), mockData
  - `test/utils/test-helpers.ts` - 12+ reusable async helpers (180 lines)
- **Memory Status**: ✅ Fixed - Tests use `npm run test:memory` with 2GB heap + GC
- **Categories**:
  - Components: 35+ test files (library, enhancement, player, visualizations, etc.)
  - Integration tests: 14 test files (WebSocket, streaming, library management, etc.)
  - Services: 6 test files
  - Hooks: 4 test files
  - Contexts: 1 test file
- **Coverage Target**: 55%+ overall frontend

---

## 🚀 Launch Script Guide

The [launch-auralis-web.py](launch-auralis-web.py) script is your primary development entry point:

```bash
# Development mode (starts backend + frontend dev server)
python launch-auralis-web.py --dev

# Production mode (serves built frontend from backend)
python launch-auralis-web.py

# Custom port
python launch-auralis-web.py --port 9000

# Skip browser auto-open
python launch-auralis-web.py --dev --no-browser
```

**What it does:**
1. Checks Python and Node.js dependencies
2. Starts FastAPI backend (port 8765)
3. In `--dev` mode: Starts React dev server (port 3000)
4. Opens browser automatically (can skip with `--no-browser`)
5. Manages process lifecycle (Ctrl+C stops all servers)

**For desktop app:** Use `cd desktop && npm run dev` instead for Electron integration.

---

## 🧪 Frontend Test Infrastructure

### Test Setup & Utilities

**Global Setup** (`auralis-web/frontend/src/test/setup.ts`, 131 lines):
- Vitest configuration & Jest compatibility layer (`jest.*` → `vi.*`)
- Polyfills: `matchMedia`, `IntersectionObserver`, `ResizeObserver`, `WebSocket`, `scrollTo`
- MSW server initialization with `onUnhandledRequest: 'warn'`
- Cleanup strategy:
  - React Testing Library cleanup
  - Mock clearing (`vi.clearAllMocks()`)
  - Timer reset (`vi.useRealTimers()`)
  - Aggressive GC if available (`global.gc()`)
  - 100ms final delay

**Custom Render** (`auralis-web/frontend/src/test/test-utils.tsx`, 71 lines):
```typescript
// ✅ ALWAYS use this instead of @testing-library/react
import { render } from '@/test/test-utils'

// Includes all required providers:
// - BrowserRouter (React Router)
// - DragDropContext (drag-and-drop)
// - WebSocketProvider (real-time updates)
// - ThemeProvider (dark/light mode)
// - EnhancementProvider (audio processing)
// - ToastProvider (notifications)
```

**Test Helpers** (`auralis-web/frontend/src/test/utils/test-helpers.ts`, 180 lines):
- `waitForElement(selector, timeout)` - Wait for element with timeout
- `waitForApiCall(endpoint, timeout)` - Wait for API to complete
- `typeWithDelay(element, text)` - Simulate user typing
- `waitForLoadingToFinish()` - Wait for loading spinner
- `simulateNetworkDelay(ms)` - Network latency simulation
- `waitForConditions(conditions)` - Multiple condition waiting
- And 6+ more helpers for robust async testing

### MSW (Mock Service Worker)

**Server Setup** (`src/test/mocks/server.ts`, 12 lines):
```typescript
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

**Handlers** (`src/test/mocks/handlers.ts`, 1500+ lines):
- **80+ endpoint mocks** covering:
  - Player control (play, pause, seek, volume, etc.)
  - Library management (tracks, albums, artists)
  - Enhancement/processing (parameters, presets)
  - Metadata editing (tags, artwork)
  - Playlists and search
- Base URLs: `http://localhost:8765/api` and `/api` (relative)
- All handlers include `delay()` for realistic latency

**Mock Data** (`src/test/mocks/mockData.ts`):
- `mockTracks` - 100 test tracks with metadata
- `mockAlbums` - 20 test albums
- `mockArtists` - 10 test artists
- `mockPlaylists` - Predefined playlists
- `mockPlayerState` - Player state object

### Test Organization & Patterns

**Component Test Example:**
```typescript
import { render, screen, waitFor } from '@/test/test-utils'
import { MyComponent } from './MyComponent'

describe('MyComponent', () => {
  it('loads and displays data', async () => {
    render(<MyComponent />)

    // Use waitFor for async operations
    await waitFor(() => {
      expect(screen.getByText('Loaded')).toBeInTheDocument()
    })
  })
})
```

**File Locations** - Tests co-located with source:
```
src/
├── components/
│   ├── MyComponent.tsx
│   └── __tests__/
│       └── MyComponent.test.tsx
├── services/
│   ├── playerService.ts
│   └── __tests__/
│       └── playerService.test.ts
├── hooks/
│   ├── usePlayer.ts
│   └── __tests__/
│       └── usePlayer.test.ts
```

**Memory Management** (CRITICAL):
```bash
# ✅ For full test suite (prevents OOM)
npm run test:memory                    # 2GB heap + GC enabled

# ✅ For watch mode (lighter)
npm test                               # Interactive mode

# ✅ For single run (fast)
npm run test:run                       # Fast run, same heap as standard

# ✅ For coverage
npm run test:coverage:memory           # Coverage with memory management
```

### Vite Configuration (`auralis-web/frontend/vite.config.ts`)

**Key Test Settings:**
- **Test environment**: jsdom
- **Setup file**: `./src/test/setup.ts`
- **Max threads**: 2 (memory management)
- **Timeout**: 30s per test
- **Coverage provider**: v8

**Dev Server Configuration:**
- **Port**: 3000
- **Proxy**: `/api` and `/ws` → `http://localhost:8765`

**Build Output**: `build/` directory

---

## 🎨 Design System (MANDATORY for Frontend)

**Location**: `auralis-web/frontend/src/design-system/tokens.ts` (270 lines - SINGLE SOURCE OF TRUTH)

### Required Usage
✅ **ALWAYS import and use tokens**:
```typescript
import { colors, spacing, typography, shadows } from '@/design-system'

// ✅ CORRECT
<div style={{ color: colors.text.primary, padding: spacing.md }}>

// ❌ WRONG - hardcoded colors/values
<div style={{ color: '#ffffff', padding: '16px' }}>
```

### Token Categories

**Colors** (60+ predefined):
- `colors.background.primary`, `colors.background.secondary`
- `colors.text.primary`, `colors.text.secondary`, `colors.text.disabled`
- `colors.accent.*`, `colors.danger.*`, `colors.success.*`
- `colors.border.*`, `colors.overlay.*`
- Component-specific: `colors.playerBar.*`, `colors.sidebar.*`, `colors.rightPanel.*`

**Spacing** (8px grid system):
- `spacing.xs` (4px) → `spacing.xxxl` (64px)
- Examples: `spacing.sm` (8px), `spacing.md` (16px), `spacing.lg` (24px)

**Typography**:
- `typography.fontFamily.*` (primary, mono)
- `typography.fontSize.*` (xs, sm, md, lg, xl, 2xl, 3xl)
- `typography.fontWeight.*` (light, normal, medium, semibold, bold)
- `typography.lineHeight.*` (tight, normal, relaxed)

**Shadows** (7 levels):
- `shadows.sm` → `shadows['2xl']`, `shadows.glow`, `shadows.glowStrong`

**Transitions**:
- `transitions.fast` (100ms), `transitions.base` (200ms), `transitions.slow` (300ms)

**Z-Index Scale** (11 levels):
- `zIndex.base` (1) → `zIndex.max` (1000)
- Layer ordering: base → tooltip → dropdown → modal → toast

**Animations**:
- `animations.pulse`, `animations.fadeIn`, `animations.slideUp`

### Component Guidelines

✅ **Keep components modular** (< 300 lines):
- Extract subcomponents if exceeding limit
- Use facade pattern for backward compatibility

✅ **One component per purpose**:
- Don't create "Enhanced", "V2", or "Advanced" duplicates
- Refactor existing component in-place when possible

✅ **Design system integration**:
- All colors must use tokens
- All spacing must use tokens
- No hardcoded colors, fonts, or spacing values
- Consistency with existing component patterns

---

## 🏗️ Architecture Patterns & Key Interdependencies

### Data Flow: Library → Processor → Player → WebSocket
1. **LibraryManager** scans folders → SQLite database with caching
2. **HybridProcessor** loads audio → applies DSP pipeline → returns processed frames
3. **EnhancedAudioPlayer** queues tracks → plays with real-time processing
4. **FastAPI backend** exposes REST endpoints + WebSocket for live updates

### Key Classes & Their Relationships
- **LibraryManager** (`auralis/library/manager.py`): Singleton managing SQLite, caching queries via LRU
- **HybridProcessor** (`auralis/core/hybrid_processor.py`): Orchestrates DSP pipeline with pluggable stages
- **ChunkedProcessor** (`auralis-web/backend/chunked_processor.py`): Streams audio in 30s chunks with MSE encoding
- **PlayerStateManager** (`auralis-web/backend/state_manager.py`): Thread-safe WebSocket state synchronization
- **PsychoacousticEQ** (`auralis/dsp/eq/`): 26-band EQ with genre-specific curves

### Critical Performance Patterns
1. **Query Caching**: LibraryManager caches `albums()`, `artists()`, `tracks()` → 136x speedup
2. **Chunked Processing**: Backend splits audio into 30s chunks, processes in parallel
3. **NumPy Vectorization**: DSP operations use np.array broadcasting (1.7x EQ speedup)
4. **Numba JIT** (optional): Envelope follower compilation → 40-70x speedup
5. **MSE Streaming**: Chunks encoded as WebM/Opus for efficient browser playback

### Backend Router Pattern
All API endpoints are modular routers in `auralis-web/backend/routers/`:
- Each router handles a domain (player, library, enhancement, etc.)
- Routers use FastAPI dependency injection for shared state
- Automatically included in `main.py` via `app.include_router()`
- Each router test file mirrors the router directory structure

### Thread-Safety Patterns (Important!)

**LibraryManager Thread-Safe Operations** (`auralis/library/manager.py`):
- Uses `threading.RLock()` for reentrant locking on concurrent operations (delete_track)
- Maintains `_deleted_track_ids` set to track successfully deleted tracks
- **Critical**: All lock-protected code must be inside `with self._delete_lock:` block
- **Race Condition Prevention**: Checks `if track_id in self._deleted_track_ids: return False` to prevent multiple deletes reporting success

**Repository Pattern for Data Access**:
- All database operations go through repositories in `auralis/library/repositories/`
- Repositories handle transaction semantics and atomicity
- Query results automatically cached via LibraryManager (configure TTL)
- Repository delete operations must be atomic (all-or-nothing)

**When Adding Thread-Safe Code**:
1. Identify shared state that needs protection (database updates, internal sets, etc.)
2. Use `threading.RLock()` for reentrant locks (safer than Lock)
3. Keep critical section small (lock → check → update → unlock)
4. Test with `tests/concurrency/` boundary tests to catch race conditions
5. Document lock semantics in docstring: "Thread-safe: Uses RLock for X operation"

---

## 🔑 Key Files You'll Modify Most

**Audio Processing:**
- [auralis/core/hybrid_processor.py](auralis/core/hybrid_processor.py) - Main processing orchestrator
- [auralis/dsp/stages.py](auralis/dsp/stages.py) - Processing pipeline stages
- [auralis/core/unified_config.py](auralis/core/unified_config.py) - Processing configuration

**Backend API:**
- [auralis-web/backend/main.py](auralis-web/backend/main.py) - FastAPI app and routes (614 lines)
- [auralis-web/backend/routers/](auralis-web/backend/routers/) - Modular endpoint handlers
- [auralis-web/backend/chunked_processor.py](auralis-web/backend/chunked_processor.py) - Streaming processor

**Frontend UI:**
- [auralis-web/frontend/src/components/ComfortableApp.tsx](auralis-web/frontend/src/components/ComfortableApp.tsx) - Main app layout
- [auralis-web/frontend/src/components/CozyLibraryView.tsx](auralis-web/frontend/src/components/CozyLibraryView.tsx) - Library view (407 lines, refactored)
- [auralis-web/frontend/src/components/BottomPlayerBarUnified.tsx](auralis-web/frontend/src/components/BottomPlayerBarUnified.tsx) - Player controls
- [auralis-web/frontend/src/design-system/](auralis-web/frontend/src/design-system/) - Design tokens (required for all new UI)

**Desktop:**
- [desktop/main.js](desktop/main.js) - Electron process

**Database:**
- [auralis/library/manager.py](auralis/library/manager.py) - Library manager with caching
- [auralis/library/cache.py](auralis/library/cache.py) - Query result caching (136x speedup)
- [auralis/library/repositories/](auralis/library/repositories/) - Data access layer with pagination

---

## ⚠️ Important Gotchas & Common Mistakes

### Worker Project Integration

This machine has a separate worker project at `../worker_aithentia/` with its own backend deployed at https://api.test.aithentia.com:8000/. When working on:
- API integrations or webhooks → Check worker project compatibility
- Database schema changes → Verify worker compatibility
- Authentication or API keys → Consult worker project's .env setup

**Worker project is NOT part of Auralis** - it's a separate service. Don't confuse it with the Auralis backend on port 8765.

### Port Numbers
- **Auralis Backend API**: Port **8765** (NOT 8000)
  - API Docs available at http://localhost:8765/api/docs
  - Use this for all Auralis development
- **Worker API** (if needed): Port 8000 (separate project)
- **Frontend dev**: Port 3000 (proxies to Auralis backend on 8765)
- Check with `lsof -ti:8765` if port is in use

### Audio Processing Invariants
These MUST always hold - test them!

```python
# Output sample count must equal input sample count
assert len(output_audio) == len(input_audio), "Sample count changed!"

# Audio arrays are NumPy, not Python lists
processed = processor.process(audio)  # Returns np.ndarray
assert isinstance(processed, np.ndarray)

# Never modify audio in-place
output = audio.copy()  # NOT audio directly
output *= gain  # Then modify the copy
```

### Testing Philosophy (Read First!)
- **Coverage ≠ Quality**: 100% coverage doesn't catch all bugs (proven by overlap bug)
- **Test invariants**: Properties that must always hold
- **Test behavior**: What the system does, not how it does it
- **Test edge cases**: Boundary conditions, empty inputs, maximum values
- **MANDATORY**: Read [docs/development/TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md)

### API Changes
When adding backend endpoints:
1. Use the modular router pattern (in `routers/` directory)
2. Router is automatically included in `main.py`
3. Use dependency injection for shared state (player, library)
4. Document in [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md) if WebSocket
5. Add tests in `tests/backend/`

### Import Patterns
**Use new modular imports:**
```python
from auralis.dsp.eq import PsychoacousticEQ, generate_genre_eq_curve
from auralis.dsp.utils import spectral_centroid, to_db, adaptive_gain_calculation
from auralis.dsp.dynamics import AdaptiveCompressor
from auralis.analysis.quality import QualityMetrics
from auralis.library.repositories import TrackRepository
```

**Legacy imports still work but are deprecated:**
```python
from auralis.dsp.unified import spectral_centroid  # OLD - don't use
from auralis.dsp.psychoacoustic_eq import PsychoacousticEQ  # OLD
```

### Database Operations
- Always use repository pattern (in `auralis/library/repositories/`)
- Use pagination for large result sets
- Queries are automatically cached (configure TTL in `LibraryManager`)
- Default database location: `~/.auralis/library.db`

### Frontend UI Development
**MANDATORY**: Read [docs/guides/UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md)
- ✅ Use design system tokens (no hardcoded colors/spacing)
- ✅ One component per purpose (no duplicates)
- ✅ Keep components under 300 lines
- ✅ Extract subcomponents if needed
- ❌ Don't create "Enhanced" or variant versions of existing components

### Desktop App Development (Electron)

**Development:**
```bash
cd desktop
npm run dev    # Starts backend + frontend dev server + Electron window
```

**Key Files:**
- [desktop/main.js](desktop/main.js) - Electron main process (spawns backend, loads frontend)
- [desktop/preload.js](desktop/preload.js) - IPC bridge for native file selection and OS integration
- [desktop/package.json](desktop/package.json) - Electron build configuration

**Important Notes:**
- Backend starts automatically by main.js; don't start it separately
- Frontend loads from http://localhost:3000 (dev) or built files (production)
- IPC communication between Electron and renderer for file picking
- Use `npm run package` to build installers for distribution
- Cross-platform builds require native tools (may fail on wrong OS)

### Common Testing Gotchas
1. **AsyncIO Tests**: Use `@pytest.mark.asyncio` for async functions; backend tests may need `await` handling
2. **WebSocket State**: ChunkedProcessor maintains state; tests must initialize PlayerStateManager properly
3. **Audio Fixtures**: Use fixtures from `conftest.py` (sample_audio, test_audio_file); don't create inline
4. **Library Transactions**: Tests may need isolation; check if test needs new LibraryManager instance
5. **Boundary Tests**: When writing boundaries, test both minimum (0, empty, None) and maximum values
6. **Invariant Tests**: If modifying core processors, update invariant tests in `tests/invariants/`
7. **FastAPI TestClient**: ⚠️ CRITICAL - TestClient must use context manager syntax or startup events won't run:
   - ❌ WRONG: `@pytest.fixture\ndef client(): return TestClient(app)`
   - ✅ CORRECT: `@pytest.fixture\ndef client():\n    with TestClient(app) as client:\n        yield client`
   - Without context manager, all `@app.on_event("startup")` handlers are skipped!

---

## 🧪 Testing Patterns

### Test Structure (Arrange-Act-Assert)
```python
def test_processor_preserves_sample_count():
    """Invariant: Output sample count == input sample count"""
    # Arrange
    audio = np.random.randn(44100)
    processor = AudioProcessor()

    # Act
    output = processor.process(audio)

    # Assert
    assert len(output) == len(audio), "Sample count must be preserved"
```

### Test Markers
```python
@pytest.mark.boundary
def test_maximum_audio_duration():
    """Boundary: Test at extreme values"""
    pass

@pytest.mark.invariant
def test_compression_ratio_invariant():
    """Invariant: Properties that must always hold"""
    pass

@pytest.mark.integration
def test_end_to_end_processing_pipeline():
    """Integration: Test across components"""
    pass

@pytest.mark.mutation
def test_quality_metric_catches_subtle_bugs():
    """Mutation: Designed to catch specific code mutations"""
    pass

@pytest.mark.slow
def test_large_audio_file_processing():
    """Slow test: Skip with -m "not slow" """
    pass
```

### Fixtures for Common Setup
```python
# Available in conftest.py:
@pytest.fixture
def sample_audio():
    """16-bit PCM 44.1kHz audio"""
    pass

@pytest.fixture
def test_audio_file():
    """Path to test WAV file"""
    pass

@pytest.fixture
def hybrid_processor():
    """Configured HybridProcessor instance"""
    pass
```

See [tests/conftest.py](tests/conftest.py) for all available fixtures.

---

## 📊 Test Organization (850+ tests)

**Phase 1 - Complete (541 tests):**
- ✅ Week 1: 305 critical invariant tests
- ✅ Week 2: 85 advanced integration tests
- ✅ Week 3: 151 boundary tests (101% of target)

**Key Test Files:**
- `tests/backend/` - API tests (96 tests)
- `tests/auralis/` - Audio processing (24 tests)
- `tests/boundaries/` - Edge cases (151 tests)
- `tests/integration/` - Cross-component (85 tests)
- `tests/invariants/` - Critical invariants (305 tests)
- `tests/mutation/` - Test quality validation
- `tests/validation/` - End-to-end validation

**Running Test Suites:**
```bash
python -m pytest tests/boundaries/ -v              # All 151 boundary tests
python -m pytest tests/boundaries/test_chunked_processing_boundaries.py -v  # Just chunked (31)
python -m pytest tests/boundaries/test_pagination_boundaries.py -v          # Just pagination (30)
python -m pytest -m "invariant" -v                  # All invariant tests
python -m pytest -m "not slow" -v                   # Skip slow tests
```

---

## 🔧 Performance & Optimization

### Performance Metrics
- **Real-time factor**: 36.6x (process 1 hour in ~98 seconds)
- **Envelope follower**: 40-70x speedup with Numba JIT
- **EQ processing**: 1.7x speedup with NumPy vectorization
- **Cache hits**: 136x faster queries with LRU cache

### Optimizations Used
```bash
# 1. Numba JIT compilation (optional, ~2-3x overall speedup)
pip install numba

# 2. NumPy vectorization (included, 1.7x EQ speedup)
# 3. Query result caching (included, 136x speedup)
# 4. Memory pools and SIMD (included)
```

### Checking Performance
```bash
# Quick validation (~30 seconds)
python tests/validation/test_integration_quick.py

# Comprehensive benchmark (~2-3 minutes)
python benchmark_performance.py
```

---

## 🎵 Key Processing Concepts

### Processing Modes
1. **Adaptive** (default): Intelligent mastering without reference tracks
2. **Reference**: Traditional reference-based mastering
3. **Hybrid**: Combines reference guidance with adaptive intelligence

### Processing Presets
- Adaptive, Gentle, Warm, Bright, Punchy

### Audio Fingerprint System (NEW)
25-dimensional acoustic fingerprint for intelligent processing:
- **Frequency** (7D): Bass, mids, treble distribution
- **Dynamics** (3D): Loudness, crest factor, compression
- **Temporal** (4D): Tempo, rhythm, transients
- **Spectral** (3D): Tonal characteristics
- **Harmonic** (3D): Vocals vs drums detection
- **Variation** (3D): Loudness dynamics
- **Stereo** (2D): Width and phase

Automatically used by `HybridProcessor` for intelligent parameter selection.

---

## 📚 Documentation References

**Frontend Testing:**
- [docs/guides/PHASE2_ENHANCEMENT_ROADMAP.md](docs/guides/PHASE2_ENHANCEMENT_ROADMAP.md) - **IN PROGRESS** - Phase 2 enhancement component tests & Phase 3 planning

**Development Guidelines:**
- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - **MANDATORY** test quality
- [TEST_IMPLEMENTATION_ROADMAP.md](docs/development/TEST_IMPLEMENTATION_ROADMAP.md) - Testing roadmap

**Architecture & Design:**
- [docs/guides/UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md) - UI requirements
- [docs/guides/MULTI_TIER_BUFFER_ARCHITECTURE.md](docs/guides/MULTI_TIER_BUFFER_ARCHITECTURE.md) - Streaming architecture
- [docs/guides/AUDIO_FINGERPRINT_GRAPH_SYSTEM.md](docs/guides/AUDIO_FINGERPRINT_GRAPH_SYSTEM.md) - Fingerprint system

**Performance:**
- [docs/completed/performance/PERFORMANCE_OPTIMIZATION_QUICK_START.md](docs/completed/performance/PERFORMANCE_OPTIMIZATION_QUICK_START.md) - Optimization guide
- [docs/completed/LARGE_LIBRARY_OPTIMIZATION.md](docs/completed/LARGE_LIBRARY_OPTIMIZATION.md) - Library performance

**Complete Index:**
- [docs/README.md](docs/README.md) - Documentation index (163 active files + 158 archived)

---

## 🚀 Release & Version Management

**Version File**: [auralis/version.py](auralis/version.py)

```bash
# Check current version
python -c "from auralis.version import get_version; print(get_version())"

# Bump version (updates all files)
python scripts/sync_version.py 1.0.0-beta.13

# Git workflow for releases
git commit -am "chore: bump version to X.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin master && git push origin vX.Y.Z
```

**Current Version**: 1.0.0-beta.12 (see README.md for latest)

---

## 🐛 Troubleshooting

### Backend Won't Start
```bash
# Check port is free
lsof -ti:8765 | xargs kill -9

# Check dependencies
pip install -r requirements.txt

# Run directly to see errors
cd auralis-web/backend && python -m uvicorn main:app --reload
```

### Tests Failing
```bash
# Run with verbose output
python -m pytest tests/ -vv --tb=long

# Check test dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio

# Run single test to isolate issue
python -m pytest tests/backend/test_player.py::test_play_track -vv

# Run only fast tests (skip slow ones)
python -m pytest -m "not slow" -v
```

### Audio Files Not Found
```bash
# Check test file location
ls test_files/
cd tests && python -m pytest test_*.py
```

### Frontend Won't Build
```bash
cd auralis-web/frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### Database Errors
```bash
# Reset database (WARNING: deletes all library data)
rm ~/.auralis/library.db
# Will be recreated on next app launch
```

### Performance Debugging
```bash
# Profile audio processing
python -m cProfile -s cumtime -o profile.stats auralis/core/hybrid_processor.py
python -m pstats profile.stats

# Check memory usage during library scan
watch -n 1 'ps aux | grep python'

# Benchmark specific operation
python benchmark_performance.py

# Check query cache effectiveness
python -c "from auralis.library import LibraryManager; m = LibraryManager(); print(m.cache_info())"
```

---

## 💾 Repository Info

- **Git Status**: Current branch `master`
- **Main Branch**: `master` (use for PRs)
- **License**: GPL-3.0
- **Project Name**: Auralis (matchering-player)

---

## 🔗 Useful Links

- **GitHub**: https://github.com/matiaszanolli/Auralis
- **API Docs**: http://localhost:8765/api/docs (when running)
- **WebSocket Protocol**: [auralis-web/backend/WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md)
- **Release Downloads**: https://github.com/matiaszanolli/Auralis/releases

---

## 🔍 Code Organization Principles

### Module Size Guidelines
- Keep Python modules under 300 lines
- Keep React components under 300 lines
- Extract subcomponents when exceeding limits
- Use facade pattern for backward compatibility when refactoring

### Component Organization
**One component per purpose:**
- Don't create duplicate "Enhanced" or "V2" versions of existing components
- If improving a component, refactor it in-place when possible
- Extract distinct UI patterns into reusable primitives in design-system/

**Modular Design Pattern (Backend):**
- Each router handles a single domain (player, library, enhancement, etc.)
- Routers use FastAPI dependency injection for shared state
- Mirror test structure to router structure: `routers/player.py` → `tests/backend/test_player.py`

### Repository Pattern (Data Access)
- Always use repository pattern in `auralis/library/repositories/`
- Never direct database queries outside repositories
- Implement pagination for large result sets
- Queries automatically cached via LibraryManager (configure TTL)

---

## 🔄 Refactoring Strategy

### When to Refactor
1. **Duplication**: DRY principle violation (code appears 2+ times)
2. **Size Violation**: Module/component > 300 lines
3. **Complexity**: Method has 3+ responsibilities (SRP violation)
4. **Performance**: Profiling shows bottleneck
5. **Clarity**: Code intent unclear without extensive comments

### Before Refactoring
- Write tests for current behavior first
- Ensure test coverage > 80% for target code
- Create branch with descriptive name (e.g., `refactor/simplify-eq-calculation`)
- Document invariants that must hold

### After Refactoring
- All tests still pass
- Performance metrics unchanged or improved
- No new duplicate code introduced
- Document breaking changes if any

---

## 📋 Frequently Updated Files

When working on features, check these files for context and dependencies:

**Configuration & Version:**
- [auralis/version.py](auralis/version.py) - Version string (bumped for releases)
- [auralis/core/unified_config.py](auralis/core/unified_config.py) - Processing parameters
- [pyproject.toml](pyproject.toml) - Python version, dependencies

**Frontend Styling:**
- [auralis-web/frontend/src/design-system/](auralis-web/frontend/src/design-system/) - All design tokens (required for new UI)
- [auralis-web/frontend/src/theme/](auralis-web/frontend/src/theme/) - Theme colors, spacing, typography

**Backend State:**
- [auralis-web/backend/state_manager.py](auralis-web/backend/state_manager.py) - WebSocket state (modify carefully - thread-safe code)
- [auralis-web/backend/chunked_processor.py](auralis-web/backend/chunked_processor.py) - Streaming processor (complex state machine)

**Database Schema:**
- [auralis/library/repositories/](auralis/library/repositories/) - All data access (repository pattern, no direct SQL)

**Frontend State:**
- [auralis-web/frontend/src/contexts/](auralis-web/frontend/src/contexts/) - Global state management
- [auralis-web/frontend/src/hooks/](auralis-web/frontend/src/hooks/) - Shared React hooks

---

## ⚡ Performance Considerations

### Before Optimizing
1. Profile to identify actual bottleneck: `python -m cProfile -s cumtime script.py`
2. Establish baseline metric (execution time, memory, etc.)
3. Set target improvement % (typically 20-40%)

### Common Optimizations Available
```python
# 1. NumPy Vectorization (typical 1.5-2.5x speedup)
# Instead of: for loop over samples
# Use: np.array operations with broadcasting

# 2. Numba JIT Compilation (40-70x for tight loops)
from numba import jit
@jit(nopython=True)
def expensive_calculation(x):
    # ... tight loop code ...

# 3. Query Caching (136x on cache hit)
# LibraryManager.albums() automatically cached
# Configure cache TTL in __init__

# 4. Chunked Processing (parallel loading)
# Backend already uses 30s chunks with Promise.all()
# Don't add more chunking without profiling first
```

### Validating Performance
```bash
# Quick: ~30 seconds
python tests/validation/test_integration_quick.py

# Comprehensive: ~2-3 minutes
python benchmark_performance.py

# Profile specific component
python -m cProfile -s cumtime -o stats.prof script.py
python -m pstats stats.prof
```

---

## 💡 Development Workflow

### Starting a New Feature

1. **Scope & Plan**
   - Check existing code for similar functionality (avoid duplication)
   - Read relevant test files to understand expected behavior
   - Check `docs/MASTER_ROADMAP.md` for planned features or conflicts

2. **Create Branch**
   ```bash
   git checkout -b feature/short-description
   # Examples: feature/search-improvement, fix/websocket-race-condition
   ```

3. **Implement with Tests**
   - Write tests first (TDD) or alongside code
   - Run tests frequently: `pytest tests/ -v`
   - Ensure no existing tests break

4. **Code Review Checklist**
   - ✅ All tests pass (including new and existing)
   - ✅ No module/component > 300 lines
   - ✅ No code duplication introduced
   - ✅ Design system tokens used (frontend)
   - ✅ Docstrings for public functions
   - ✅ Type hints present (Python)
   - ✅ No hardcoded values (colors, strings, paths)

5. **Performance Check (if applicable)**
   ```bash
   python -m pytest tests/ --cov=auralis --cov=auralis-web --cov-report=html
   python benchmark_performance.py  # Check for regressions
   ```

6. **Commit with Clear Message**
   ```bash
   git commit -m "feat: brief description of change

   Longer explanation if needed. References any related issues.
   Breaks/Changes: Document if this breaks existing behavior."
   ```

### Common Workflows by Component

**Fixing a Bug:**
1. Write a failing test that reproduces the bug
2. Fix the code
3. Verify test passes
4. Check no other tests break
5. Commit with `fix:` prefix

**Adding a New Endpoint:**
1. Create router file in `auralis-web/backend/routers/`
2. Include router in `main.py` via `app.include_router()`
3. Add tests in `tests/backend/test_*.py` (mirror structure)
4. Document in `auralis-web/backend/WEBSOCKET_API.md` if WebSocket

**Refactoring Existing Code:**
1. Ensure >80% test coverage for code being refactored
2. Create `refactor/` branch
3. Run tests constantly while refactoring
4. No behavior changes (tests should pass unchanged)
5. Document in commit: "refactor: description, no behavior changes"

---

## 🚨 Critical Invariants (MUST NOT Break)

These properties must hold at all times. Tests verify them in `tests/invariants/`:

**Audio Processing:**
- ✅ Output sample count == input sample count (always)
- ✅ Output is NumPy ndarray, not Python list
- ✅ Audio never modified in-place (always copy first)
- ✅ No NaN/Inf values in output
- ✅ Loudness never increases beyond configured maximum

**Player State:**
- ✅ Player position never exceeds track duration
- ✅ Queue position valid for current queue length
- ✅ State changes atomic (no partial updates)
- ✅ WebSocket updates ordered (no race conditions)

**Database:**
- ✅ Track metadata immutable (read-only after insert)
- ✅ Database connection pooling thread-safe
- ✅ Queries cached only when deterministic
- ✅ Foreign keys always valid (referential integrity)

**Modifying these?** Update corresponding tests in `tests/invariants/` first!

---

## 🎯 Quick Reference & Common Mistakes

### Quick Command Reference

```bash
# Start development
python launch-auralis-web.py --dev        # Web UI dev mode
npm run dev                               # Desktop app full stack

# Run tests (most common)
python -m pytest tests/ -v                # All tests
python -m pytest tests/boundaries/ -v    # Just boundaries (151 tests)
python -m pytest -k "test_name" -v       # Single test by name
python -m pytest -m "not slow" -v        # Skip slow tests

# Build & package
make build                                # Full build with tests
make build-fast                           # Fast build without tests
npm run package                           # Create installers

# Debug & check
lsof -ti:8765 | xargs kill -9            # Free port 8765
pip install -r requirements.txt          # Reinstall deps
mypy auralis/ auralis-web/backend/       # Type check
```

### Common Mistakes & How to Avoid

**❌ Port 8000 instead of 8765**
- Backend runs on **8765**, not 8000 (CRITICAL!)
- Frontend dev server on 3000 (configured to proxy to 8765 in vite.config.ts)
- Check: `lsof -ti:8765` before starting
- Note: Worker project (if present) may use port 8000 - don't confuse them

**❌ Frontend tests: Not using test-utils render()**
```tsx
// ❌ WRONG - missing providers, will fail
import { render } from '@testing-library/react'
render(<MyComponent />)

// ✅ CORRECT - includes all 6 required providers
import { render } from '@/test/test-utils'
render(<MyComponent />)
```

**❌ Mixing Jest and Vitest syntax in tests**
```typescript
// ❌ WRONG - Jest syntax won't work
jest.mock('./module')
jest.fn()

// ✅ CORRECT - Vitest syntax
vi.mock('./module')
vi.fn()
```

**❌ Hardcoded colors/spacing in React components**
```tsx
// ❌ WRONG - hardcoded values, inconsistent
<div style={{ backgroundColor: '#FF5733', padding: '12px' }}>

// ✅ CORRECT - always use design tokens
import { colors, spacing } from '@/design-system'
<div style={{ backgroundColor: colors.background.primary, padding: spacing.md }}>
```

**❌ Frontend tests with hardcoded delays**
```tsx
// ❌ WRONG - flaky, slow, unpredictable
await new Promise(resolve => setTimeout(resolve, 1000))

// ✅ CORRECT - waits for actual condition with timeout
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument()
}, { timeout: 3000 })
```

**❌ Creating test Wrapper instead of using test-utils**
```tsx
// ❌ WRONG - duplicates providers, causes nested Router errors
const Wrapper = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider>{children}</ThemeProvider>
  </BrowserRouter>
)
render(<Component />, { wrapper: Wrapper })

// ✅ CORRECT - test-utils already includes all providers
render(<Component />)
```

**❌ Audio array in-place modification (Python)**
```python
# ❌ WRONG - modifies input, breaks invariants
audio *= gain

# ✅ CORRECT - creates copy first
audio = audio.copy()
audio *= gain
```

**❌ Direct database queries in backend**
```python
# ❌ WRONG - bypasses repository pattern, skips caching
session.query(Track).filter(...).all()

# ✅ CORRECT - use repository with automatic caching
from auralis.library.repositories import TrackRepository
repo = TrackRepository()
repo.find_by_genre(genre)  # Cached automatically
```

**❌ Creating duplicate components ("Enhanced" versions)**
```tsx
// ❌ WRONG - duplicates existing EnhancementPane
export function EnhancementPaneV2() { ... }

// ✅ CORRECT - refactor existing component in-place
// Update EnhancementPane, extract subcomponents if it grows > 300 lines
```

**❌ Not running full test suite before committing**
```bash
# ❌ WRONG - might break other tests silently
git commit -m "Add feature"

# ✅ CORRECT - verify everything works
npm run test:memory              # Frontend tests (2GB heap)
python -m pytest tests/ -v       # Backend tests
git commit -m "Add feature"
```

**❌ Ignoring recent test selector/assertion fixes**
- Last 5+ commits (Nov 2024) fixed selector issues across components
- Fixes: `screen.getByRole()` preferred over `querySelector()`
- Follow patterns in `auralis-web/frontend/src/components/library/__tests__/`
- Copy from existing passing tests when uncertain

**❌ Long-running methods without progress feedback**
- If operation > 2 seconds, provide user feedback
- Use existing progress indicators: `PlayerStatus`, `LibraryScanning`
- Don't block UI thread (async/await in frontend, threading in backend)

### When Something's Broken

**Test hangs or fails intermittently:**
- Check for race conditions in async code
- Verify WebSocket state isolation (each test needs fresh PlayerStateManager)
- Look for hardcoded delays or timeouts

**Frontend not updating:**
- Check React Query cache is invalidated: `queryClient.invalidateQueries()`
- Verify state changes propagated through contexts
- Check console for errors (DevTools F12)

**Backend returns wrong data:**
- Verify cache TTL hasn't stalled old data: Check `LibraryManager.cache_info()`
- Check repository queries are using correct filters
- Verify database migrations ran: `sqlite3 ~/.auralis/library.db ".schema"`

**Audio sounds wrong:**
- Check processing pipeline disabled/enabled correctly
- Verify sample rate unchanged (44.1kHz)
- Check for clipping: max output amplitude should be < 1.0
- Run: `python -m pytest tests/invariants/ -v` to validate

---

## 📊 Project Health Metrics

**Current Status (Beta 12.0):**
- Backend: 850+ tests, 74%+ coverage
- Frontend: 234 tests passing, 95.5% pass rate
- Code Quality: Type hints, comprehensive docstrings, linting
- Performance: 36.6x real-time, 740+ files/sec library scanning
- CI/CD: GitHub Actions with multi-platform builds

**Before Shipping Changes:**
- ✅ All tests pass (`pytest tests/ -v`)
- ✅ No performance regression (baseline vs. current)
- ✅ No new warnings in linting
- ✅ Type checking passes (`mypy`)
- ✅ Frontend builds without errors (`npm run build`)

---

## 🔧 Recent Implementation Improvements (November 2024)

### LibraryManager Thread-Safety & Validation Enhancements

**Problem**: Boundary tests exposed missing validation and thread-safety issues:
1. `test_invalid_file_path_handling` - `add_track()` should validate file existence
2. `test_concurrent_delete_same_track` - Multiple concurrent deletes should not all succeed

**Solutions Implemented** (in `auralis/library/manager.py`):

**1. File Path Validation in `add_track()`:**
```python
def add_track(self, track_info: Dict[str, Any]) -> Optional[Track]:
    """Add a track to the library with file path validation"""
    # Validate filepath exists before adding to database
    if 'filepath' not in track_info:
        raise ValueError("track_info must contain 'filepath' key")

    filepath = track_info['filepath']
    if not Path(filepath).exists():
        raise FileNotFoundError(f"Audio file not found: {filepath}")

    track = self.tracks.add(track_info)
    if track:
        invalidate_cache('get_all_tracks', 'search_tracks', 'get_recent_tracks')
    return track
```
**Result**: ✅ `test_invalid_file_path_handling` PASSES

**2. Thread-Safe Deletion with Race Condition Prevention:**
```python
def __init__(self):
    # ... existing code ...
    # Thread-safe locking for delete operations (prevents race conditions)
    self._delete_lock = threading.RLock()
    # Track IDs that have been successfully deleted (prevents double-deletion)
    self._deleted_track_ids = set()

def delete_track(self, track_id: int) -> bool:
    """Delete a track and invalidate caches (thread-safe)"""
    with self._delete_lock:
        # Check if this track has already been deleted by another thread
        if track_id in self._deleted_track_ids:
            return False

        # Check if track still exists before deleting
        existing_track = self.tracks.get_by_id(track_id)
        if not existing_track:
            return False

        # Perform the deletion inside the lock
        result = self.tracks.delete(track_id)
        if result:
            # Mark this track as deleted to prevent double-deletion
            self._deleted_track_ids.add(track_id)
            invalidate_cache('get_all_tracks', 'get_track', 'search_tracks',
                             'get_favorite_tracks', 'get_recent_tracks', 'get_popular_tracks')
        return result
```

**Key Design Decisions**:
- **RLock (Reentrant Lock)**: Allows same thread to acquire lock multiple times (safer than regular Lock)
- **_deleted_track_ids Set**: Tracks which tracks were successfully deleted, preventing race conditions where all concurrent threads report success
- **Atomic Operations**: Lock held for entire operation (check → delete → mark)
- **Fail-Fast**: Returns False immediately if track already deleted or doesn't exist

**Result**: ✅ `test_invalid_file_path_handling` PASSES; `test_concurrent_delete_same_track` validation logic correct (test infrastructure may need investigation)

**Testing Implications**:
- File validation tests pass naturally with `FileNotFoundError` exception
- Concurrent deletion tests validate thread-safety with multiple threads attempting simultaneous deletes
- Add tests using `test_audio_file` fixture or create temporary files for file path validation

### FastAPI TestClient Startup Events (December 2024)

**Problem**: Integration tests were failing with 503 Service Unavailable errors because API components (LibraryManager, AudioPlayer, etc.) were not initialized.

**Root Cause**: TestClient does NOT call FastAPI startup events unless used as a context manager. Direct instantiation `TestClient(app)` skips startup/shutdown completely.

**Solution**: Update FastAPI test fixtures to use context manager syntax:

```python
# ❌ WRONG - startup events never run
@pytest.fixture
def client():
    return TestClient(app)

# ✅ CORRECT - startup events run on entry, shutdown on exit
@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
```

**Critical Impact**:
- Fixes all FastAPI integration tests that depend on `@app.on_event("startup")`
- Enabled initialization of LibraryManager, AudioPlayer, ProcessingEngine, etc.
- This single fix unlocked 11+ previously failing API tests

**When to Apply**:
- All FastAPI TestClient fixtures must use context manager syntax
- If tests fail with "not available" or 503 errors during integration testing, check if TestClient fixture uses context manager
- Documented in `tests/integration/test_api_integration.py` as example pattern

---

## Notes from ~/.claude/CLAUDE.md

- Always prioritize improving existing code rather than duplicating logic
- In this computer, the worker project lives in ../worker_aithentia relative to this project
- The backend is properly deployed at https://api.test.aithentia.com:8000/
