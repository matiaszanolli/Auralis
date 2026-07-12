# Deprecation Audit Report

**Date**: 2026-02-12
**Auditor**: Claude Code (Opus 4.6)
**Scope**: All layers — Python engine, FastAPI backend, React frontend, Rust DSP, config/CI

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 2     |
| MEDIUM   | 5     |
| LOW      | 3     |
| **Total**| **10** |

**Key findings**:

1. **`datetime.utcnow()` used in 23+ locations** (HIGH) — deprecated since Python 3.12, returns naive UTC datetime that is ambiguous. Affects models, schemas, and WebSocket protocol.
2. **FastAPI `@app.on_event()` deprecated** (HIGH) — scheduled for removal, blocks adoption of lifespan context manager pattern.
3. **SQLAlchemy 1.x `session.query()` used in 134 call sites** across all 12 repositories (MEDIUM) — largest migration effort, but not blocking since SQLAlchemy 2.0 still supports it.
4. **258 Python files use legacy `typing` imports** (LOW) — `List`, `Dict`, `Optional`, `Tuple` instead of builtins + PEP 604 union syntax.

**No CRITICAL findings** — no deprecated APIs that are already removed in targeted runtime versions. All findings are forward-looking deprecations.

**Upgrade blockers**: None immediate. The `datetime.utcnow()` and `@app.on_event()` findings are HIGH because they emit deprecation warnings and are scheduled for removal in upcoming versions.

**Recommended migration order**:
1. `datetime.utcnow()` → `datetime.now(timezone.utc)` (highest risk, simplest fix)
2. `@app.on_event()` → lifespan context manager (2 call sites)
3. Pydantic `class Config:` → `model_config = ConfigDict(...)` (1 call site)
4. `declarative_base()` → `DeclarativeBase` class (1 call site, cascading changes)
5. `session.query()` → `select()` + `session.execute()` (134 call sites, largest effort)
6. Enable `pytest.ini` deprecation warnings (monitoring)
7. Remaining LOW items at convenience

---

## Findings

### D-01: `datetime.utcnow()` across backend and models

- **Severity**: HIGH
- **Dimension**: Python Stdlib
- **Location**: `auralis-web/backend/websocket_protocol.py` (12 occurrences), `auralis-web/backend/schemas.py` (8 occurrences), `auralis/library/models/base.py:44-45`, `auralis/library/models/schema.py:27`, `auralis-web/backend/cache/monitoring.py` (3 occurrences)
- **Status**: NEW
- **Deprecated API**: `datetime.utcnow()` / `datetime.datetime.utcnow`
- **Deprecated Since**: Python 3.12
- **Removal Version**: Python 3.16 (tentative, per PEP 387 timeline)
- **Replacement**: `datetime.now(timezone.utc)` (returns timezone-aware datetime)
- **Affected Files**: 5 source files, 23+ call sites (excluding `dist/` and `desktop/resources/` copies)
- **Evidence**:
  ```python
  # auralis/library/models/base.py:44-45
  created_at = Column(DateTime, default=datetime.utcnow)
  updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

  # auralis-web/backend/schemas.py:32
  timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

  # auralis-web/backend/websocket_protocol.py:130
  elapsed = datetime.utcnow() - self.last_activity
  ```
- **Migration Path**:
  1. Add `from datetime import timezone` to affected files
  2. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` in all call sites
  3. Replace `default=datetime.utcnow` with `default=lambda: datetime.now(timezone.utc)` in SQLAlchemy columns
  4. Replace `default_factory=datetime.datetime.utcnow` with `default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)` in Pydantic fields
  5. Verify timestamp comparison logic still works (timezone-aware vs naive)
- **Risk**: Emits `DeprecationWarning` on every call in Python 3.12+. Currently suppressed by `pytest.ini` filter. Will be removed in a future Python version.
- **Migration Effort**: Medium (23 call sites across 5 files)

---

### D-02: FastAPI `@app.on_event()` deprecated

- **Severity**: HIGH
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: `auralis-web/backend/config/startup.py:52`, `auralis-web/backend/config/startup.py:311`
- **Status**: NEW
- **Deprecated API**: `@app.on_event("startup")` / `@app.on_event("shutdown")`
- **Deprecated Since**: FastAPI 0.93 (Starlette 0.26)
- **Removal Version**: FastAPI 1.0 (planned)
- **Replacement**: `asynccontextmanager` lifespan function passed to `FastAPI(lifespan=lifespan)`
- **Affected Files**: 1 file, 2 call sites
- **Evidence**:
  ```python
  # auralis-web/backend/config/startup.py:52
  @app.on_event("startup")
  async def startup_event() -> None:
      """Initialize Auralis components on startup"""
      ...

  # auralis-web/backend/config/startup.py:311
  @app.on_event("shutdown")
  async def shutdown_event() -> None:
      """Clean up resources on shutdown"""
      ...
  ```
- **Migration Path**:
  1. Create an `asynccontextmanager` lifespan function:
     ```python
     @asynccontextmanager
     async def lifespan(app: FastAPI):
         # startup logic here
         yield
         # shutdown logic here
     ```
  2. Pass `lifespan=lifespan` to `FastAPI()` constructor in `main.py`
  3. Remove `@app.on_event()` decorators
- **Risk**: FastAPI emits deprecation warning. Will be removed in FastAPI 1.0. Related to existing issue #2127 (startup blocks event loop with synchronous auto-scan).
- **Migration Effort**: Small (2 call sites in 1 file, straightforward refactor)

---

### D-03: Pydantic V1 `class Config:` pattern

- **Severity**: MEDIUM
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: `auralis-web/backend/routers/metadata.py:48-49`
- **Status**: NEW
- **Deprecated API**: `class Config:` inner class on Pydantic models
- **Deprecated Since**: Pydantic V2 (2.0)
- **Removal Version**: Pydantic V3 (planned)
- **Replacement**: `model_config = ConfigDict(extra="forbid")`
- **Affected Files**: 1 file, 1 occurrence
- **Evidence**:
  ```python
  # auralis-web/backend/routers/metadata.py:48-49
  class Config:
      extra = "forbid"  # Don't allow unknown fields
  ```
- **Migration Path**:
  1. Add `from pydantic import ConfigDict` to imports
  2. Replace `class Config: extra = "forbid"` with `model_config = ConfigDict(extra="forbid")`
- **Risk**: Works today via Pydantic V2's backward-compatibility layer. Will break on Pydantic V3. One-line fix.
- **Migration Effort**: Small (1 occurrence)

---

### D-04: SQLAlchemy `declarative_base()` legacy function

- **Severity**: MEDIUM
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: `auralis/library/models/base.py:16,19`
- **Status**: NEW
- **Deprecated API**: `from sqlalchemy.orm import declarative_base` / `Base = declarative_base()`
- **Deprecated Since**: SQLAlchemy 2.0
- **Removal Version**: SQLAlchemy 3.0 (planned)
- **Replacement**: `class Base(DeclarativeBase): pass` using `from sqlalchemy.orm import DeclarativeBase`
- **Affected Files**: 1 file defining Base, used by 6 model files
- **Evidence**:
  ```python
  # auralis/library/models/base.py:16,19
  from sqlalchemy.orm import declarative_base
  Base = declarative_base()
  ```
- **Migration Path**:
  1. Replace `declarative_base()` with:
     ```python
     from sqlalchemy.orm import DeclarativeBase
     class Base(DeclarativeBase):
         pass
     ```
  2. Update association tables to use `Base.metadata` (unchanged)
  3. Optionally migrate `Column()` to `mapped_column()` with `Mapped[]` type hints (separate effort)
- **Risk**: Works today via SQLAlchemy 2.0 compatibility. Will be removed in SQLAlchemy 3.0. This is the foundation class — changing it is low-risk but affects the entire model hierarchy.
- **Migration Effort**: Small (1 call site, but verify 6 model files still work)

---

### D-05: SQLAlchemy 1.x `session.query()` API

- **Severity**: MEDIUM
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: All 12 repository files under `auralis/library/repositories/`
- **Status**: NEW
- **Deprecated API**: `session.query(Model).filter(...)` (SQLAlchemy 1.x Query API)
- **Deprecated Since**: SQLAlchemy 2.0 (legacy, not formally deprecated yet but 2.0-style is recommended)
- **Removal Version**: SQLAlchemy 3.0 (planned)
- **Replacement**: `session.execute(select(Model).where(...))` (SQLAlchemy 2.0-style)
- **Affected Files**: 12 repository files, 134 call sites
  - `queue_template_repository.py` — 10 occurrences
  - `stats_repository.py` — 12 occurrences
  - `queue_history_repository.py` — 8 occurrences
  - `queue_repository.py` — 10 occurrences
  - `album_repository.py` — 14 occurrences
  - `track_repository.py` — 18 occurrences
  - `genre_repository.py` — 8 occurrences
  - `fingerprint_repository.py` — 10 occurrences
  - `playlist_repository.py` — 12 occurrences
  - `similarity_graph_repository.py` — 10 occurrences
  - `artist_repository.py` — 12 occurrences
  - `settings_repository.py` — 10 occurrences
- **Evidence**:
  ```python
  # auralis/library/repositories/track_repository.py (typical pattern)
  template = session.query(QueueTemplate).filter(
      QueueTemplate.id == template_id
  ).first()
  ```
- **Migration Path**:
  1. Add `from sqlalchemy import select` to each repository file
  2. Replace `session.query(Model).filter(cond).first()` with `session.execute(select(Model).where(cond)).scalar_one_or_none()`
  3. Replace `session.query(Model).all()` with `session.execute(select(Model)).scalars().all()`
  4. Replace `session.query(Model).count()` with `session.execute(select(func.count()).select_from(Model)).scalar()`
  5. Test each repository method individually
- **Risk**: SQLAlchemy 2.0 still fully supports `session.query()`. It will be removed in 3.0. No urgency, but this is the largest migration effort in the codebase.
- **Migration Effort**: Large (134 call sites across 12 files)

---

### D-06: `asyncio.get_event_loop()` without running loop

- **Severity**: MEDIUM
- **Dimension**: Python Stdlib
- **Location**: `auralis-web/backend/fingerprint_generator.py:239`
- **Status**: NEW
- **Deprecated API**: `asyncio.get_event_loop()` (when called outside a running event loop)
- **Deprecated Since**: Python 3.10 (emits DeprecationWarning in 3.10+, behavioral change in 3.12)
- **Removal Version**: Behavior changed in Python 3.12 — no longer creates a new loop implicitly
- **Replacement**: `asyncio.get_running_loop()` (when inside an async context)
- **Affected Files**: 1 file, 1 occurrence
- **Evidence**:
  ```python
  # auralis-web/backend/fingerprint_generator.py:239
  loop = asyncio.get_event_loop()
  ```
- **Migration Path**:
  1. Replace `loop = asyncio.get_event_loop()` with `loop = asyncio.get_running_loop()`
  2. This function is called from an `async` context, so `get_running_loop()` is correct
- **Risk**: In Python 3.12+, `get_event_loop()` emits a DeprecationWarning if no loop is running. Since this code runs inside FastAPI (which has a running loop), it works, but using `get_running_loop()` is both correct and future-proof.
- **Migration Effort**: Small (1 occurrence, one-line change)

---

### D-07: `pytest.ini` silences all DeprecationWarnings

- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `pytest.ini:73`
- **Status**: NEW
- **Deprecated API**: N/A (configuration issue, not a deprecated API)
- **Deprecated Since**: N/A
- **Removal Version**: N/A
- **Replacement**: Selective warning filters instead of blanket suppression
- **Affected Files**: 1 file
- **Evidence**:
  ```ini
  # pytest.ini:72-74
  filterwarnings =
      ignore::DeprecationWarning
      ignore::PendingDeprecationWarning
  ```
- **Migration Path**:
  1. Remove blanket `ignore::DeprecationWarning` filter
  2. Add specific filters for known third-party warnings that can't be fixed:
     ```ini
     filterwarnings =
         default::DeprecationWarning
         ignore::DeprecationWarning:PyAudio
         ignore::DeprecationWarning:soundfile
         ignore::PendingDeprecationWarning
     ```
  3. Run test suite and triage new warnings
  4. Fix internal deprecation warnings revealed by the change
- **Risk**: This filter masks ALL deprecation warnings from both internal code and dependencies, preventing early detection of deprecated API usage. Findings D-01 through D-06 are currently invisible in test output because of this filter.
- **Migration Effort**: Small (1 file change), but will surface hidden warnings that need triage

---

### D-08: Legacy `typing` imports across 258 Python files

- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: 258 files across `auralis/` and `auralis-web/backend/`
- **Status**: NEW
- **Deprecated API**: `from typing import List, Dict, Optional, Tuple, Set` (PEP 585 / PEP 604)
- **Deprecated Since**: Python 3.9 (PEP 585 generics), Python 3.10 (PEP 604 `X | None`)
- **Removal Version**: Not scheduled for removal (typing module aliases are not deprecated, just unnecessary)
- **Replacement**: `list[str]`, `dict[str, Any]`, `str | None`, `tuple[int, ...]`
- **Affected Files**: 258 Python files
- **Evidence**:
  ```python
  # Typical pattern across codebase
  from typing import List, Dict, Optional, Tuple, Any

  def process(tracks: List[Dict[str, Any]]) -> Optional[Tuple[int, ...]]:
      ...

  # Modern equivalent (Python 3.10+)
  def process(tracks: list[dict[str, Any]]) -> tuple[int, ...] | None:
      ...
  ```
- **Migration Path**:
  1. Since Python 3.14+ is required, all modern syntax is available
  2. Use automated tool: `pyupgrade --py314-plus` or ruff's `UP` rules
  3. Replace `Optional[X]` with `X | None`
  4. Replace `List`, `Dict`, `Tuple`, `Set` with builtins
  5. Keep `from typing import Any` (still required)
- **Risk**: No runtime impact. Pure style/consistency issue. The `typing` module aliases are not deprecated, but modern builtins are preferred.
- **Migration Effort**: Large (258 files), but fully automatable with `pyupgrade` or `ruff`

---

### D-09: `tsconfig.json` uses `moduleResolution: "node"` instead of `"bundler"`

- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/tsconfig.json:10`
- **Status**: NEW
- **Deprecated API**: `"moduleResolution": "node"` (legacy Node.js resolution)
- **Deprecated Since**: TypeScript 5.0 (introduced `"bundler"` mode)
- **Removal Version**: Not scheduled for removal, but `"bundler"` is recommended for Vite projects
- **Replacement**: `"moduleResolution": "bundler"`
- **Affected Files**: 1 file
- **Evidence**:
  ```json
  {
    "compilerOptions": {
      /* Bundler mode */
      "moduleResolution": "node",
  ```
  Note: The comment says "Bundler mode" but the value is `"node"`.
- **Migration Path**:
  1. Change `"moduleResolution": "node"` to `"moduleResolution": "bundler"`
  2. Verify that all imports still resolve correctly (bundler mode is less strict about extensions)
  3. This may require `"module": "ESNext"` (already set) and removing `"esModuleInterop"` (optional)
- **Risk**: No runtime impact. The `"node"` resolution works with Vite but doesn't take advantage of TypeScript's bundler-aware features like `package.json` `exports` field resolution.
- **Migration Effort**: Small (1 file, 1 line change, verify build)

---

### D-10: Internal backward-compatibility shims still active

- **Severity**: LOW
- **Dimension**: Internal
- **Location**: 5 compatibility modules + 2 deprecated classes
- **Status**: NEW
- **Deprecated API**: Internal backward-compatibility modules and classes
- **Deprecated Since**: Auralis v1.1.0
- **Removal Version**: Auralis v2.0.0 (per deprecation warnings)
- **Replacement**: Direct imports from new locations
- **Affected Files**: 7 files
  - `auralis/analysis/fingerprint/harmonic_analyzer_sampled.py` — re-exports `SampledHarmonicAnalyzer`
  - `auralis/analysis/fingerprint/spectral_analyzer.py` — re-exports analyzer
  - `auralis/analysis/fingerprint/streaming_harmonic_analyzer.py` — re-exports analyzer
  - `auralis/analysis/fingerprint/variation_analyzer.py` — re-exports analyzer
  - `auralis/analysis/fingerprint/harmonic_analyzer.py` — re-exports analyzer
  - `auralis/core/processor.py:70-78` — `process()` function wrapping `HybridProcessor`
  - `auralis/library/manager.py:80-88` — `LibraryManager` wrapping `RepositoryFactory`
- **Evidence**:
  ```python
  # auralis/analysis/fingerprint/harmonic_analyzer_sampled.py:15-20
  warnings.warn(
      "Importing SampledHarmonicAnalyzer from auralis.analysis.fingerprint.harmonic_analyzer_sampled "
      "is deprecated. Import from auralis.analysis.fingerprint.analyzers.batch.harmonic_sampled instead.",
      DeprecationWarning,
      stacklevel=2
  )

  # auralis/core/processor.py:73-78
  warnings.warn(
      "auralis.core.process is deprecated and will be removed in v2.0.0. "
      "Use HybridProcessor instead.",
      DeprecationWarning,
  )
  ```
- **Migration Path**:
  1. Search for imports from deprecated module paths
  2. Update to new import paths
  3. Once no callers remain, remove shim modules
  4. These are intentional deprecations — track removal for v2.0.0
- **Risk**: No immediate risk. These shims are functioning correctly and emit proper warnings. They exist intentionally for backward compatibility during the v1.x → v2.0 transition.
- **Migration Effort**: Small (remove shims when v2.0.0 is released)

---

## Dependency Upgrade Roadmap

| Package | Current | Latest | Blocking Finding | Upgrade Priority |
|---------|---------|--------|-----------------|-----------------|
| Python | 3.14+ | 3.14 | D-01 (utcnow), D-06 (get_event_loop) | Fix deprecations first |
| FastAPI | 0.100+ | 0.115+ | D-02 (on_event) | Migrate lifespan before 1.0 |
| Pydantic | 2.4+ | 2.10+ | D-03 (class Config) | Low urgency |
| SQLAlchemy | 2.0+ | 2.0.35 | D-04 (declarative_base), D-05 (session.query) | Before 3.0 |
| TypeScript | ^4.9.5 | 5.7 | D-09 (moduleResolution) | Optional upgrade |
| NumPy | Current | Current | None | No action needed |
| Rust/PyO3 | 0.21 | 0.21 | None | No action needed |

**No packages are blocked from upgrade by the current codebase.** All findings are about using deprecated APIs that still work but should be migrated proactively.

---

## Migration Effort Summary

| Finding | Effort | Call Sites | Files | Automatable? |
|---------|--------|-----------|-------|-------------|
| D-01: datetime.utcnow() | Medium | 23+ | 5 | Partially (regex) |
| D-02: @app.on_event() | Small | 2 | 1 | No |
| D-03: Pydantic class Config | Small | 1 | 1 | No |
| D-04: declarative_base() | Small | 1 | 1 | No |
| D-05: session.query() | **Large** | 134 | 12 | Partially |
| D-06: asyncio.get_event_loop() | Small | 1 | 1 | Yes |
| D-07: pytest.ini warnings | Small | 1 | 1 | No |
| D-08: Legacy typing imports | Large | 258+ | 258 | **Yes** (pyupgrade/ruff) |
| D-09: tsconfig moduleResolution | Small | 1 | 1 | Yes |
| D-10: Internal shims | Small | 7 | 7 | No (v2.0.0 milestone) |

**Total estimated migration**: ~180 call sites requiring manual changes, ~258 files automatable.

---

## Dimension Checklists

### Python Standard Library & Language
- [x] `datetime.utcnow()` — **D-01**: 23+ occurrences (HIGH)
- [x] `asyncio.get_event_loop()` — **D-06**: 1 occurrence (MEDIUM)
- [x] `typing` legacy imports — **D-08**: 258 files (LOW)
- [ ] `pkg_resources` — Not used
- [ ] `distutils` — Not used
- [ ] `imp` module — Not used
- [ ] `collections` ABCs from `collections` — Not found
- [ ] `locale.getdefaultlocale()` — Not found
- [ ] `ssl.PROTOCOL_TLS` — Not found
- [ ] `configparser` legacy methods — Not found

### NumPy / SciPy / Audio Libraries
- [ ] `np.bool`, `np.int`, `np.float` — Not found (already using builtins)
- [ ] `np.product`, `np.cumproduct`, etc. — Not found
- [ ] `scipy.fftpack` — Not found (using `scipy.fft`)
- [ ] `librosa` deprecated APIs — Not found
- **Result**: Clean. No deprecated NumPy/SciPy APIs detected.

### FastAPI / Pydantic / SQLAlchemy
- [x] `@app.on_event()` — **D-02**: 2 occurrences (HIGH)
- [x] Pydantic `class Config:` — **D-03**: 1 occurrence (MEDIUM)
- [x] `declarative_base()` — **D-04**: 1 occurrence (MEDIUM)
- [x] `session.query()` — **D-05**: 134 occurrences (MEDIUM)
- [ ] `from pydantic import validator` — Not found (not using field validators)
- [ ] `orm_mode = True` — Not found
- [ ] `engine.execute()` — Not found

### React / Redux / Frontend Libraries
- [ ] `ReactDOM.render()` — Not found (using createRoot)
- [ ] `componentWillMount` etc. — Not found (functional components)
- [ ] `findDOMNode` — Not found
- [ ] `defaultProps` on function components — Not found
- [ ] `connect()` HOC — Not found (using hooks)
- [ ] `createStore` — Not found (using configureStore)
- [ ] `@mui/styles` (JSS) — Not found
- [x] `moduleResolution: "node"` — **D-09**: 1 occurrence (LOW)
- **Result**: Frontend is clean of deprecated React/Redux/MUI patterns.

### Node.js / npm / Build Tools
- [x] `tsconfig.json` — **D-09** (covered above)
- [ ] Deprecated npm packages — None detected
- [ ] ESLint flat config — Not applicable (no `.eslintrc`)
- **Result**: Minimal issues.

### Rust / PyO3 / Cargo
- [ ] Deprecated Rust APIs — Not found
- [ ] PyO3 deprecated macros — Not found (using current 0.21 patterns)
- [ ] Deprecated `Cargo.toml` keys — Not found
- **Result**: Clean. Rust/PyO3 layer is up to date.

### Internal Codebase Deprecations
- [x] Internal shims — **D-10**: 7 files with DeprecationWarning (LOW)
- [ ] Duplicate utility functions — Not found beyond known shims

### Configuration & CI/CD
- [x] `pytest.ini` warning suppression — **D-07** (MEDIUM)
- [ ] `setup.cfg` / `setup.py` consolidation — Not applicable
- [ ] GitHub Actions versions — No CI workflows present (see #2097)
- [ ] mypy/black/ruff config — Not found deprecated options
