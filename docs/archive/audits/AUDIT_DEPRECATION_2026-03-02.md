# Deprecation Audit Report

**Date**: 2026-03-02
**Auditor**: Claude Code (Opus 4.6)
**Scope**: All layers — Python engine, FastAPI backend, React frontend, Rust DSP, config/CI
**Previous audit**: 2026-02-12 (10 findings: 0 CRITICAL, 2 HIGH, 5 MEDIUM, 3 LOW)

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1     |
| HIGH     | 1     |
| MEDIUM   | 5     |
| LOW      | 5     |
| **Total**| **12** |

**Key findings**:

1. **`np.hann()` does not exist in NumPy** (CRITICAL) — The previous fix for deprecated `np.hanning()` (#2595) recommended `np.hann()` as the replacement, but this function does not exist in NumPy. All 10 call sites will raise `AttributeError` at runtime. Confirmed on NumPy 2.3.5. The correct replacement is `scipy.signal.windows.hann()`.
2. **PyO3 module init uses legacy `&PyModule` signature** (HIGH) — PyO3 0.21 introduced the bound API; `&PyModule` will be removed in 0.23.
3. **SQLAlchemy `session.query()` still at 141 call sites** (MEDIUM) — unchanged from prior audit, blocking SQLAlchemy 2.1+ upgrade.
4. **CI workflows target wrong Python/Node versions** (MEDIUM) — Workflows test Python 3.12–3.13 and Node 20, but project requires Python 3.14+ and Node 24+.

**Progress since 2026-02-12 audit**:
- D-01 (`datetime.utcnow()`): **MOSTLY FIXED** — reduced from 23+ sites to 6 (all in test files)
- D-02 (`@app.on_event()`): **FIXED** — no longer in backend source
- D-03 (Pydantic `class Config:`): **FIXED** — migrated to `model_config`
- D-06 (`declarative_base()`): **FIXED** — migrated to `DeclarativeBase`

**Recommended migration order**:
1. `np.hann()` → `scipy.signal.windows.hann()` (CRITICAL, 10 sites — runtime crash)
2. PyO3 `&PyModule` → `Bound<'_, PyModule>` (HIGH, 1 site — blocks PyO3 0.23 upgrade)
3. `session.query()` → `select()` + `session.execute()` (MEDIUM, 141 sites — largest effort)
4. CI version matrix update (MEDIUM, 4 workflow files)
5. Remaining MEDIUM/LOW items at convenience

---

## Findings

### D-NEW-01: `np.hann()` does not exist — regression from #2595 fix

- **Severity**: CRITICAL
- **Dimension**: NumPy/SciPy
- **Location**: 10 call sites across 7 files (see list below)
- **Status**: Regression of #2595
- **Deprecated API**: `np.hanning()` (deprecated since NumPy 1.25)
- **What happened**: Issue #2595 recommended replacing `np.hanning()` with `np.hann()`. However, `np.hann()` **does not exist** in NumPy. The function was `np.hanning()`, and its replacement is `scipy.signal.windows.hann()`.
- **Removal Version**: `np.hanning()` removed in NumPy 2.0
- **Replacement**: `scipy.signal.windows.hann(N)` or `numpy.hanning(N)` (still available in NumPy 2.3.5 despite deprecation)
- **Affected Files**:
  - `auralis/dsp/eq/psychoacoustic_eq.py:126`
  - `auralis/dsp/utils/spectral.py:45`
  - `auralis/dsp/utils/interpolation_helpers.py:116`
  - `auralis/analysis/quality_assessors/base_assessor.py:205`
  - `auralis/optimization/parallel_processor.py:55,61,70`
  - `tests/auralis/dsp/test_lowmid_transient_enhancer.py:41`
  - `tests/auralis/optimization/test_parallel_processor.py:286,294`
- **Evidence**:
  ```python
  # Confirmed on NumPy 2.3.5:
  >>> np.hann(10)
  AttributeError: module 'numpy' has no attribute 'hann'

  # Current code (all 10 sites):
  window = np.hann(len(audio_segment))  # CRASHES at runtime
  ```
- **Migration Path**:
  1. Add `from scipy.signal.windows import hann` to affected files
  2. Replace `np.hann(N)` with `hann(N)` at all 10 call sites
  3. Verify `scipy` is already a dependency (it is)
- **Risk**: **Runtime crash** — every DSP code path using Hanning windows will fail with `AttributeError`
- **Migration Effort**: Small (10 call sites, 7 files)

---

### D-NEW-02: PyO3 module init uses legacy `&PyModule` signature

- **Severity**: HIGH
- **Dimension**: Rust/PyO3
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:27`
- **Status**: NEW
- **Deprecated API**: `fn auralis_dsp(_py: Python<'_>, m: &PyModule) -> PyResult<()>`
- **Deprecated Since**: PyO3 0.21
- **Removal Version**: PyO3 0.23
- **Replacement**: `fn auralis_dsp(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()>`
- **Affected Files**: 1 file, 1 call site
- **Evidence**:
  ```rust
  // vendor/auralis-dsp/src/py_bindings.rs:27
  #[pymodule]
  fn auralis_dsp(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
  ```
  Currently compiles via deref coercion on PyO3 0.21, but the `&PyModule` reference pattern will be removed in 0.23.
- **Note**: The rest of the Rust codebase correctly uses the bound API (`.new_bound(py)`, `.into_pyarray_bound(py).unbind()`). Only the module init signature is legacy.
- **Migration Path**:
  1. Change signature to `m: &Bound<'_, PyModule>`
  2. Update `wrap_pyfunction!` calls if needed for new signature
  3. Test with `maturin develop`
- **Risk**: Blocks upgrade to PyO3 0.23+
- **Migration Effort**: Small (1 call site)

---

### D-NEW-03: SQLAlchemy 1.x `session.query()` at 141 call sites

- **Severity**: MEDIUM
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: 141 call sites across 13 files in `auralis/library/repositories/`
- **Status**: Existing: D-04 from 2026-02-12 audit (was 134 sites, now 141 — slight growth)
- **Deprecated API**: `session.query(Model).filter(...)` pattern
- **Deprecated Since**: SQLAlchemy 1.4 (legacy query API)
- **Removal Version**: SQLAlchemy 2.1+ (currently supported but discouraged)
- **Replacement**: `select(Model).where(...)` + `session.execute()`
- **Affected Files** (top 5 by count):
  - `track_repository.py` (33 sites)
  - `fingerprint_repository.py` (16 sites)
  - `queue_template_repository.py` (12 sites)
  - `playlist_repository.py` (11 sites)
  - `queue_history_repository.py` (11 sites)
- **Evidence**:
  ```python
  # auralis/library/repositories/track_repository.py
  return session.query(Track).filter(Track.id == track_id).first()
  ```
- **Migration Path**: Replace each `session.query(Model).filter(X)` with `session.execute(select(Model).where(X)).scalar_one_or_none()`
- **Risk**: Not blocking current operation but prevents future SQLAlchemy 2.1+ compatibility
- **Migration Effort**: Large (141 call sites, 13 files)

---

### D-NEW-04: Vitest deprecated configuration options

- **Severity**: MEDIUM
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/vite.config.mts:153-160`
- **Status**: NEW
- **Deprecated API**: `threads`, `maxThreads`, `minThreads`, `forceExitTimeout`
- **Deprecated Since**: Vitest 2.0
- **Replacement**: `pool: 'threads'` with `poolOptions.threads.maxThreads` / `poolOptions.threads.minThreads`
- **Affected Files**: 1 file
- **Evidence**:
  ```typescript
  // vite.config.mts:153-160
  threads: true,
  maxThreads: 2,           // deprecated
  minThreads: 1,           // deprecated
  forceExitTimeout: 5000,  // deprecated
  ```
- **Migration Path**:
  ```typescript
  pool: 'threads',
  poolOptions: {
    threads: { maxThreads: 2, minThreads: 1 }
  },
  ```
- **Risk**: Vitest will ignore these options and may emit warnings; memory management behavior may revert to defaults
- **Migration Effort**: Small (1 file, config-only change)

---

### D-NEW-05: CI workflows target wrong Python/Node versions

- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `.github/workflows.backup/` — 4 workflow files
- **Status**: NEW
- **Deprecated API**: Python 3.12–3.13 matrix, Node.js 20
- **Required versions**: Python 3.14+ (per CLAUDE.md), Node 24+ (per CLAUDE.md)
- **Affected Files**:
  - `backend-tests.yml` — Python `['3.12', '3.13']`
  - `build-release.yml` — Python `'3.13'` (3 sites), Node `'20'` (3 sites)
  - `ci.yml` — Python `'3.13'` (2 sites), Node `'20'` (1 site)
  - `frontend-build.yml` — Node `['20']` (1 matrix)
- **Risk**: CI tests against wrong Python/Node versions, potentially missing Python 3.14-specific behavior
- **Note**: Files are in `.github/workflows.backup/` — may be inactive. If active workflows exist elsewhere, verify those too.
- **Migration Effort**: Small (4 files, version string changes)

---

### D-NEW-06: CRA remnants in package.json

- **Severity**: MEDIUM
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/package.json:67-71,101`
- **Status**: Partially Existing: #2652 covers `proxy` field; `eslintConfig` is NEW
- **Deprecated API**: CRA-specific `eslintConfig` and `proxy` fields (project uses Vite)
- **Affected Fields**:
  ```json
  "eslintConfig": {
    "extends": ["react-app", "react-app/jest"]  // CRA-specific, ignored by Vite
  },
  "proxy": "http://localhost:8000"  // CRA-specific, Vite proxy is in vite.config.mts
  ```
- **Risk**: Confusing for developers; `react-app` ESLint config may conflict with project's actual ESLint setup
- **Migration Path**: Remove both fields; ensure ESLint config is in `eslint.config.js` or `.eslintrc.*`
- **Migration Effort**: Small (1 file, delete 2 fields)

---

### D-NEW-07: `np.hamming()` deprecated (2 call sites)

- **Severity**: MEDIUM
- **Dimension**: NumPy/SciPy
- **Location**: 2 call sites across 2 files
- **Status**: NEW
- **Deprecated API**: `np.hamming(N)`
- **Deprecated Since**: NumPy 1.25
- **Replacement**: `scipy.signal.windows.hamming(N)`
- **Affected Files**:
  - `auralis/dsp/utils/interpolation_helpers.py:118`
  - `tests/auralis/optimization/test_parallel_processor.py:147`
- **Evidence**:
  ```python
  custom_window = np.hamming(fft_size)
  ```
- **Risk**: `np.hamming()` still works on NumPy 2.3.5 (unlike `np.hann` which doesn't exist), but will be removed in a future version
- **Migration Effort**: Small (2 call sites)

---

### D-NEW-08: SQLAlchemy `Column()` without `Mapped[]` annotations (170 sites)

- **Severity**: LOW
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: 170 column definitions across 6 model files in `auralis/library/models/`
- **Status**: Existing: D-07 from 2026-02-12 audit (noted `Column()` pattern)
- **Deprecated API**: `Column(Type)` without `Mapped[type]` annotation
- **Deprecated Since**: SQLAlchemy 2.0
- **Replacement**: `name: Mapped[str] = mapped_column(String)`
- **Risk**: Style/forward-compat only; current code works fine with SQLAlchemy 2.0
- **Migration Effort**: Large (170 sites, 6 files — should be done alongside session.query migration)

---

### D-NEW-09: SQLAlchemy `relationship()` without `Mapped[]` (13 sites)

- **Severity**: LOW
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: 13 relationship definitions across 2 model files
- **Status**: NEW
- **Deprecated API**: `relationship("Model")` without `Mapped[list["Model"]]` annotation
- **Deprecated Since**: SQLAlchemy 2.0
- **Replacement**: `tracks: Mapped[list["Track"]] = relationship(...)`
- **Risk**: Style/forward-compat only
- **Migration Effort**: Small (13 sites, 2 files)

---

### D-NEW-10: `React.FC` pattern across 280 occurrences

- **Severity**: LOW
- **Dimension**: React/Redux/Frontend
- **Location**: 280 occurrences across 245 files in `auralis-web/frontend/src/`
- **Status**: NEW
- **Deprecated API**: `React.FC<Props>` / `React.FunctionComponent<Props>`
- **Deprecated Since**: React 18.3+ (implicit `children` prop removed)
- **Replacement**: Plain function signatures: `function Component(props: Props) {}`
- **Risk**: No runtime impact; `React.FC` still works but is discouraged in modern React. The main issue is the implicit `children` prop was removed in React 18, causing type mismatches.
- **Migration Effort**: Large (280 occurrences, 245 files — best done with codemod)

---

### D-NEW-11: `datetime.utcnow()` remaining in test files

- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: 6 call sites across 3 test files
- **Status**: Partially Existing: D-01 from 2026-02-12 (was 23+ sites, now 6 — production code fixed)
- **Deprecated API**: `datetime.utcnow()`
- **Deprecated Since**: Python 3.12
- **Replacement**: `datetime.now(timezone.utc)`
- **Affected Files**:
  - `tests/backend/test_websocket_protocol_b3.py` (3 sites)
  - `tests/backend/test_albums_api.py` (2 sites)
  - `tests/backend/test_cache_integration_b2.py` (1 site)
- **Risk**: Deprecation warnings in test output only; no production impact
- **Migration Effort**: Small (6 sites, 3 files)

---

### D-NEW-12: Internal deprecated modules with active consumers

- **Severity**: LOW
- **Dimension**: Internal
- **Location**: Multiple files (see breakdown)
- **Status**: NEW
- **Description**: Several modules marked as deprecated internally still have active consumers, indicating incomplete migration.
- **Active deprecated modules**:
  1. **`auralis/library/manager.py`** (`LibraryManager`) — Deprecated with v2.0.0 removal timeline. Still imported by ~14 production files (routers, services, CLI) and ~90+ test files.
  2. **`auralis/analysis/fingerprint/spectral_analyzer.py`** — Backward-compat shim re-exporting from new location. Still imported by `auralis/learning/reference_analyzer.py` (production) and 7 test files.
  3. **`auralis/analysis/fingerprint/harmonic_analyzer.py`** — Same pattern, similar consumer count.
  4. **`auralis/analysis/fingerprint/harmonic_analyzer_sampled.py`** — Same pattern.
  5. **`auralis/analysis/fingerprint/variation_analyzer.py`** — Same pattern.
  6. **`auralis/analysis/fingerprint/streaming_harmonic_analyzer.py`** — Same pattern.
  7. **`auralis/core/processor.py:process()`** — Deprecated function, consumers need to migrate to `HybridProcessor`.
  8. **Frontend**: `useCurrentTrack()`, `useIsPlaying()` hooks, 13 `makeSelect*()` factory aliases, 4 deprecated easing functions — all marked `@deprecated` with replacements specified.
- **Risk**: Deprecation warnings emitted at runtime; consumers won't get improvements from new APIs. Migration debt grows over time.
- **Migration Effort**: Large (distributed across entire codebase)

---

## Dependency Upgrade Roadmap

| Package | Current | Target | Blocked By | Priority |
|---------|---------|--------|------------|----------|
| NumPy | 2.3.5 | — | `np.hann()` crash (D-NEW-01) | **CRITICAL** — fix immediately |
| PyO3 | 0.21 | 0.23+ | Module init signature (D-NEW-02) | HIGH |
| SQLAlchemy | 2.0 | 2.1+ | `session.query()` (D-NEW-03), `Column()` (D-NEW-08) | MEDIUM |
| Vitest | Current | — | Deprecated config (D-NEW-04) | MEDIUM |

## Migration Effort Summary

| Finding | Effort | Call Sites | Files |
|---------|--------|------------|-------|
| D-NEW-01: np.hann() crash | Small | 10 | 7 |
| D-NEW-02: PyO3 module init | Small | 1 | 1 |
| D-NEW-03: session.query() | Large | 141 | 13 |
| D-NEW-04: Vitest config | Small | 4 | 1 |
| D-NEW-05: CI versions | Small | ~10 | 4 |
| D-NEW-06: CRA remnants | Small | 2 | 1 |
| D-NEW-07: np.hamming() | Small | 2 | 2 |
| D-NEW-08: Column() types | Large | 170 | 6 |
| D-NEW-09: relationship() | Small | 13 | 2 |
| D-NEW-10: React.FC | Large | 280 | 245 |
| D-NEW-11: datetime.utcnow() | Small | 6 | 3 |
| D-NEW-12: Internal deprecated | Large | Distributed | ~100+ |

## Prior Audit Status

| Finding from 2026-02-12 | Status Now |
|--------------------------|-----------|
| D-01: datetime.utcnow() (23+ sites) | **MOSTLY FIXED** — 6 remain in tests (D-NEW-11) |
| D-02: @app.on_event() (2 sites) | **FIXED** — migrated to lifespan |
| D-03: Pydantic class Config (1 site) | **FIXED** — migrated to model_config |
| D-04: session.query() (134 sites) | **OPEN** — now 141 sites (D-NEW-03) |
| D-05: pytest.ini warnings filter | Unchanged |
| D-06: declarative_base() (1 site) | **FIXED** — migrated to DeclarativeBase |
| D-07: Column() without Mapped[] | **OPEN** — 170 sites (D-NEW-08) |
| D-08: Legacy typing imports | **OPEN** — still in tests/scripts |
| D-09: React.FC pattern | **OPEN** — 280 occurrences (D-NEW-10) |
| D-10: Deprecated internal shims | **OPEN** — consumers remain (D-NEW-12) |
