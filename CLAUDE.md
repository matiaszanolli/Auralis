# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

**📌 Version**: 1.1.0-beta.2 | **🐍 Python**: 3.14+ | **📦 Node**: 24+

**Core Principles:**
- Always prioritize improving existing code rather than duplicating logic
- Coverage ≠ Quality: Test behavior and invariants, not implementation
- Modular design: Keep modules under 300 lines, one purpose per component

---

## 🚀 Quick Start

```bash
# Web interface (recommended)
pip install -r requirements.txt
python launch-auralis-web.py --dev    # http://localhost:8765

# Desktop app
pip install -r requirements.txt && cd desktop && npm install && npm run dev

# Tests
python -m pytest tests/ -v                         # Backend (850+ tests)
cd auralis-web/frontend && npm run test:memory    # Frontend (use memory flag!)
```

**Critical Ports:** 8765 (Backend), 3000 (Frontend dev), 8000 (Worker, if applicable)

---

## 🎯 Common Tasks

| Task | Command |
|------|---------|
| Run all backend tests | `python -m pytest tests/ -v` |
| Run invariant tests | `python -m pytest -m invariant -v` |
| Skip slow tests | `python -m pytest -m "not slow" -v` |
| Run specific tests | `python -m pytest tests/backend/ -v` |
| Backend only | `cd auralis-web/backend && python -m uvicorn main:app --reload` |
| Frontend tests | `npm run test:memory` (full suite with 2GB heap) |
| Type check | `mypy auralis/ auralis-web/backend/` |
| Free port 8765 | `lsof -ti:8765 \| xargs kill -9` |

---

## 📁 Project Structure

**Audio Engine** (`auralis/`): `core/` (processing), `dsp/` (EQ, dynamics), `analysis/` (fingerprints, content analysis), `library/` (SQLite + cache), `player/`, `io/`, `optimization/`

**Web Interface** (`auralis-web/`): `backend/` (FastAPI, modular routers, chunked processor), `frontend/` (React/TypeScript, design-system with tokens)

**Desktop** (`desktop/`): Electron wrapper with native OS integration

**Tests** (`tests/`): 850+ backend tests organized by category (backend/auralis/boundaries/integration/invariants/mutation/performance/security)

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

**Data Flow**: LibraryManager → HybridProcessor (DSP) → EnhancedAudioPlayer → FastAPI (REST + WebSocket)

**Key Optimizations**: Query caching (136x), chunked processing (30s, WAV PCM), NumPy vectorization (1.7x), thread-safe with `threading.RLock()`

**Backend**: Modular routers auto-included in `main.py`, use FastAPI dependency injection

**Database**: Repository pattern only (`auralis/library/repositories/`), pagination for large sets, queries auto-cached

---

## 🚨 Critical Invariants (MUST NOT Break)

**Audio Processing:**
```python
assert len(output) == len(input)    # Sample count preserved
assert isinstance(output, np.ndarray)  # NumPy array, never list
output = audio.copy(); output *= gain  # Never modify in-place
```

**Player State:**
- Position never exceeds track duration
- Queue position valid for current length
- State changes atomic (no partial updates)
- WebSocket updates ordered (no race conditions)

**Database:**
- Track metadata immutable after insert
- Connection pooling thread-safe
- Queries cached only when deterministic
- Foreign keys always valid

---

## ⚠️ Common Issues & Fixes

| Problem | Solution |
|---|---|
| Port 8765 in use | `lsof -ti:8765 \| xargs kill -9` |
| Backend won't start | `pip install -r requirements.txt` |
| Frontend blank page | Check backend: `curl http://localhost:8765/api/health` |
| Frontend tests OOM | Use `npm run test:memory` (2GB heap) |
| Hardcoded colors in UI | Use `import { tokens } from '@/design-system'` |
| Tests hanging | Run `pytest -m "not slow" -v` to skip slow tests |
| Database locked | `pkill -9 python && restart` |

---

## 🔨 Build & Debugging

**Build:**
```bash
make build          # Full build with tests
make build-fast     # Skip tests
make package        # Desktop installers
python sync_version.py 1.1.0-beta.2  # Update version
```

**Debug:**
```bash
DEBUG=1 python launch-auralis-web.py --dev          # Backend logging
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) FROM tracks;"  # DB inspect
curl http://localhost:8765/api/docs                 # API documentation
python -m pytest tests/backend/test_player.py::test_play_track -vv -s  # Single test
```

---

## 📚 Key Documentation

- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - Test quality standards
- [UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md) - Frontend UI requirements
- [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md) - WebSocket endpoints
- [docs/README.md](docs/README.md) - Full documentation index

---

## 💾 Repository Info

- **Git**: Branch `master` (main branch for PRs)
- **License**: GPL-3.0
- **GitHub**: https://github.com/matiaszanolli/Auralis
- **API Docs** (running): http://localhost:8765/api/docs

---

## 🔑 Code Organization

**Module Size**: Keep Python modules < 300 lines, React components < 300 lines

**One Component Per Purpose**: Don't create "Enhanced"/"V2"/"Advanced" duplicates—refactor in-place

**Database**: Repository pattern only in `auralis/library/repositories/`, never direct SQL

**Imports**:
```python
from auralis.dsp.eq import PsychoacousticEQ
from auralis.dsp.utils import spectral_centroid
from auralis.analysis.quality import QualityMetrics
```

---

**Note**: Worker project lives in `../worker_aithentia/` (separate service)
