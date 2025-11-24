# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

**📌 Current Version**: **1.1.0-beta.2** (November 23, 2025)
**🐍 Python**: 3.14+ | **📦 Node**: 24+ | **Pyenv virtualenv**: auralis-3.14.0

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

**Critical Ports:** 8765 (Backend API, NOT 8000!), 3000 (Frontend), 8000 (Worker, if applicable)

---

## 📊 Test Status Dashboard

| Test Category | Count | Command |
|---|---|---|
| **Total Backend** | 850+ | `pytest tests/ -v` |
| Invariant Tests | 305 | `pytest -m invariant -v` |
| Integration Tests | 85 | `pytest tests/integration/ -v` |
| Boundary Tests | 151+ | `pytest tests/boundaries/ -v` |
| Backend API Tests | 96 | `pytest tests/backend/ -v` |
| **Frontend Tests** | 1,084/1,425 | `npm run test:memory` |
| **Coverage** | 74%+ backend, 55%+ frontend | See test commands |

---

## ⚡ Quick Start (30 seconds)

```bash
# Web interface (recommended)
pip install -r requirements.txt
python launch-auralis-web.py --dev    # http://localhost:8765

# Or Desktop app
pip install -r requirements.txt && cd desktop && npm install && npm run dev

# Run tests
python -m pytest tests/ -v                    # Backend
cd auralis-web/frontend && npm run test:memory  # Frontend
```

---

## ✅ First-Time Setup

**Requirements:** Python 3.14+, Node 24+, Git, ports 8765/3000/8000 available

**Install:**
```bash
pip install -r requirements.txt
cd auralis-web/frontend && npm install
cd desktop && npm install  # if building desktop app
```

**Verify:**
```bash
python launch-auralis-web.py --dev
# In another terminal: curl http://localhost:8765/api/health
```

---

## 🎛️ Development Modes

- **Mode 1 (Recommended)**: `python launch-auralis-web.py --dev` - Web interface with hot reload
- **Mode 2**: `cd desktop && npm run dev` - Desktop app with full stack
- **Mode 3**: `cd auralis-web/backend && python -m uvicorn main:app --reload --port 8765` - Backend only (API docs at http://localhost:8765/api/docs)
- **Mode 4**: `cd auralis-web/frontend && npm start` - Frontend only (requires backend running)

---

## 🎯 Common Development Tasks

### Running Tests

```bash
# Backend
python -m pytest tests/ -v                    # All tests
python -m pytest tests/backend/ -v            # API tests (96)
python -m pytest tests/boundaries/ -v         # Edge cases (151)
python -m pytest tests/integration/ -v        # Integration (85)
python -m pytest tests/invariants/ -v         # Invariants (305)
python -m pytest -m "not slow" -v             # Skip slow tests

# Frontend
npm run test:memory                           # Full suite (2GB heap + GC)
npm test                                      # Interactive watch mode
npm run test:coverage:memory                  # Coverage report
```

### Making Code Changes

**Backend API:** Edit `auralis-web/backend/routers/*.py` → Test with `pytest tests/backend/ -v` → Manual test at http://localhost:8765/api/docs

**Audio Processing:** Edit `auralis/core/` or `auralis/dsp/` → Test with `pytest tests/auralis/ -v`

**Frontend:** Edit `auralis-web/frontend/src/` → Auto-reload at http://localhost:3000 → Test with `npm run test:memory`

---

## 📁 Project Structure (Quick Overview)

**Core Audio** (`auralis/`): `core/` (processing), `dsp/` (EQ, dynamics), `analysis/`, `library/` (SQLite + cache), `player/`, `io/`, `optimization/`

**Web Interface** (`auralis-web/`): `backend/` (FastAPI, routers, chunked processor), `frontend/` (React/TypeScript components, hooks, services, design-system)

**Desktop** (`desktop/`): `main.js` (Electron), `preload.js` (IPC bridge)

**Tests** (`tests/`): `backend/` (96), `auralis/` (24), `boundaries/` (151), `integration/` (85), `invariants/` (305), `mutation/`, `performance/`, `security/`, `conftest.py` (fixtures)

**Frontend Tests** (`auralis-web/frontend/src/`): 60 test files co-located with source, infrastructure in `test/` (setup.ts, test-utils.tsx, mocks/)

---

## 🧪 Frontend Test Guidelines (CRITICAL)

- **ALWAYS** use `npm run test:memory` for full suite (2GB heap + GC prevents OOM)
- **ALWAYS** import `render` from `@/test/test-utils`, NOT `@testing-library/react`
- **ALWAYS** use `waitFor()` from test-utils, NEVER hardcoded `setTimeout`
- **ALWAYS** use `vi.*` (Vitest), NOT `jest.*`
- **ALWAYS** use `screen.getByRole()` or `screen.getByTestId()`
- **API Mocking**: Use MSW in `src/test/mocks/handlers.ts` with WAV format (16/24-bit PCM)
- See [FRONTEND_TEST_MEMORY_IMPROVEMENTS_APPLIED.md](docs/guides/FRONTEND_TEST_MEMORY_IMPROVEMENTS_APPLIED.md)

---

## 🎨 Design System (MANDATORY for Frontend)

**Single Source of Truth**: `auralis-web/frontend/src/design-system/tokens.ts`

**Usage:**
```typescript
import { tokens } from '@/design-system'
// or for aurora-specific colors
import { auroraOpacity } from '@/components/library/Color.styles'

// ✅ CORRECT
<div style={{ color: tokens.colors.text.primary, padding: tokens.spacing.md }}>

// ❌ WRONG - hardcoded colors/values
<div style={{ color: '#ffffff', padding: '16px' }}>
```

**Token Categories**: Colors (60+), Spacing (8px grid), Typography, Shadows (7 levels), Transitions, Z-Index, Animations

**Phase 10 Design System Consolidation** (November 2025):
- Eliminated 170+ hardcoded aurora colors across 50+ components
- 88% reduction in duplicate definitions
- Created 7 centralized style files (Color, Shadow, BorderRadius, Spacing, Animation, Dialog, etc.)
- **Zero legacy auralisTheme imports remaining** - file archived
- See [auroraOpacity pattern](auralis-web/frontend/src/components/library/Color.styles.ts) for modern approach

**Component Guidelines**: Keep < 300 lines, extract subcomponents if larger, one purpose per component, no "Enhanced" or "V2" duplicates

---

## 🏗️ Architecture Patterns

**Data Flow**: LibraryManager (SQLite + cache) → HybridProcessor (DSP pipeline) → EnhancedAudioPlayer (real-time) → FastAPI (REST + WebSocket)

**Key Optimizations**:
- Query Caching: 136x speedup on cache hits
- Chunked Processing: 30s chunks with WAV format (16/24-bit PCM)
- NumPy Vectorization: 1.7x EQ speedup
- Numba JIT: 40-70x speedup (optional)
- MSE Streaming: Efficient browser playback

**Backend Router Pattern**: Modular routers in `auralis-web/backend/routers/`, auto-included in `main.py`, use FastAPI dependency injection

**Thread-Safety**: Use `threading.RLock()` for concurrent operations, maintain `_deleted_track_ids` set for race condition prevention, test with `tests/concurrency/` suite

---

## 🔑 Key Files You'll Modify Most

**Audio**: `auralis/core/hybrid_processor.py`, `auralis/dsp/stages.py`, `auralis/core/unified_config.py`

**Backend**: `auralis-web/backend/main.py`, `auralis-web/backend/routers/`, `auralis-web/backend/chunked_processor.py`

**Frontend**: `auralis-web/frontend/src/components/`, `auralis-web/frontend/src/design-system/`, `auralis-web/frontend/src/hooks/`, `auralis-web/frontend/src/services/`

**Database**: `auralis/library/manager.py`, `auralis/library/cache.py`, `auralis/library/repositories/`

---

## ⚠️ Important Gotchas & Common Mistakes

### Port Numbers
- **8765** = Auralis Backend (NOT 8000!), API docs at http://localhost:8765/api/docs
- **3000** = Frontend dev server (proxies to 8765)
- **8000** = Worker project (separate service if applicable)

### Audio Processing Invariants (MUST always hold!)
```python
assert len(output_audio) == len(input_audio)  # Sample count preserved
assert isinstance(processed, np.ndarray)       # NumPy arrays only
output = audio.copy(); output *= gain         # Never modify in-place
```

### Testing
- **Coverage ≠ Quality**: Test invariants and behavior, not implementation
- **TestClient**: Must use context manager syntax or `@app.on_event("startup")` won't run
- **AsyncIO**: Use `@pytest.mark.asyncio` for async tests
- **WebSocket**: ChunkedProcessor maintains state, initialize PlayerStateManager in tests
- **Fixtures**: Use fixtures from `conftest.py` (sample_audio, test_audio_file, hybrid_processor)

### API Changes
1. Use modular router pattern (in `routers/` directory)
2. Router auto-included via `app.include_router()`
3. Use dependency injection for shared state
4. Document in [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md) if WebSocket
5. Add tests in `tests/backend/`

### Frontend UI
- **MANDATORY**: Read [UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md)
- Use design system tokens (no hardcoded colors/spacing)
- One component per purpose (no duplicates)
- Keep components under 300 lines
- Don't create "Enhanced" or "V2" versions

### Database
- Always use repository pattern in `auralis/library/repositories/`
- Use pagination for large result sets
- Queries auto-cached via LibraryManager
- Default location: `~/.auralis/library.db`

---

## 🧪 Testing Patterns

```python
# Arrange-Act-Assert structure
def test_processor_preserves_sample_count():
    """Invariant: Output sample count == input sample count"""
    audio = np.random.randn(44100)
    processor = AudioProcessor()
    output = processor.process(audio)
    assert len(output) == len(audio)
```

**Test Markers**: `@pytest.mark.boundary`, `@pytest.mark.invariant`, `@pytest.mark.integration`, `@pytest.mark.mutation`, `@pytest.mark.slow`

**Fixtures**: `sample_audio`, `test_audio_file`, `hybrid_processor` (see [conftest.py](tests/conftest.py))

---

## 🚀 Build & Release

```bash
make build              # Full build with tests
make build-fast         # Fast build without tests
make package            # Create installers (desktop)

python sync_version.py 1.1.0-beta.2  # Bump version across all files
```

---

## 🔍 Debugging Tips

**Backend Logging:**
```bash
DEBUG=1 python launch-auralis-web.py --dev
import logging; logging.basicConfig(level=logging.DEBUG)
```

**Database Inspection:**
```bash
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) FROM tracks;"
```

**Frontend DevTools:** F12 in browser, use React DevTools extension, check Network/WebSocket tabs

**Single Test:** `python -m pytest tests/backend/test_player.py::test_play_track -vv -s`

---

## 🆚 Common Mistakes & Fixes

| Problem | Solution |
|---|---|
| Port 8765 already in use | `lsof -ti:8765 \| xargs kill -9` |
| Backend won't start | Reinstall deps: `pip install -r requirements.txt` |
| Frontend blank page | Verify backend running on 8765: `curl http://localhost:8765/api/health` |
| Frontend tests fail with OOM | Use `npm run test:memory` (2GB heap) instead of `npm test` |
| Hardcoded colors in UI | Use `import { tokens } from '@/design-system'` or `auroraOpacity` from Color.styles |
| Database locked | Kill Python: `pkill -9 python`, restart |
| Tests hanging | Run `pytest -m "not slow" -v` to skip slow tests |
| TypeScript errors after Node upgrade | `npm install typescript@latest && npm ci` |

---

## 📚 Documentation References

- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - **MANDATORY** test quality
- [UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md) - Frontend UI requirements
- [FRONTEND_TEST_MEMORY_IMPROVEMENTS_APPLIED.md](docs/guides/FRONTEND_TEST_MEMORY_IMPROVEMENTS_APPLIED.md) - Frontend test infrastructure
- [AUDIO_PLAYBACK_STATUS.md](docs/guides/AUDIO_PLAYBACK_STATUS.md) - Comprehensive audio playback guide
- [MULTI_TIER_BUFFER_ARCHITECTURE.md](docs/guides/MULTI_TIER_BUFFER_ARCHITECTURE.md) - Streaming architecture
- [AUDIO_FINGERPRINT_GRAPH_SYSTEM.md](docs/guides/AUDIO_FINGERPRINT_GRAPH_SYSTEM.md) - Fingerprint system
- [docs/README.md](docs/README.md) - Full documentation index

---

## 🚨 Critical Invariants (MUST NOT Break)

**Audio Processing:**
- Output sample count == input sample count (always)
- Output is NumPy ndarray, not Python list
- Audio never modified in-place (always copy first)
- No NaN/Inf values in output
- Loudness never exceeds configured maximum

**Player State:**
- Player position never exceeds track duration
- Queue position valid for current queue length
- State changes atomic (no partial updates)
- WebSocket updates ordered (no race conditions)

**Database:**
- Track metadata immutable after insert
- Database connection pooling thread-safe
- Queries cached only when deterministic
- Foreign keys always valid

---

## 💾 Repository Info

- **Git**: Current branch `master`, main branch for PRs is `master`
- **License**: GPL-3.0
- **GitHub**: https://github.com/matiaszanolli/Auralis
- **API Docs** (when running): http://localhost:8765/api/docs
- **Version**: 1.1.0-beta.2 (November 23, 2025)

---

## 🔑 Essential Code Organization Principles

**Module Size**: Keep Python modules < 300 lines, React components < 300 lines

**One Component Per Purpose**: Don't create "Enhanced", "V2", or "Advanced" duplicates; refactor in-place

**Repository Pattern**: All database queries through `auralis/library/repositories/`, never direct SQL

**Import Patterns**:
```python
# New modular imports
from auralis.dsp.eq import PsychoacousticEQ
from auralis.dsp.utils import spectral_centroid
from auralis.analysis.quality import QualityMetrics
```

---

## Notes from ~/.claude/CLAUDE.md

- Always prioritize improving existing code rather than duplicating logic
- Worker project lives in `../worker_aithentia/` (separate service)
- Backend deployed at https://api.test.aithentia.com:8000/ (not Auralis)
