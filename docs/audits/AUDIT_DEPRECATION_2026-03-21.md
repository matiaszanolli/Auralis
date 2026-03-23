# Deprecation Audit Report

**Date**: 2026-03-21
**Auditor**: Claude Opus 4.6 (automated, 4 parallel dimension agents)
**Scope**: All layers — Python engine, FastAPI backend, React frontend, Rust DSP, config/CI
**Previous audit**: 2026-03-02 (12 findings: 1 CRITICAL, 1 HIGH, 5 MEDIUM, 5 LOW)

---

## Executive Summary

| Severity | Count |
|----------|-------|
| HIGH | 1 |
| MEDIUM | 6 |
| LOW | 23 |
| **Total** | **30** |

**Significant progress since 2026-03-02**: 7 of 12 prior findings fully resolved, 2 partially fixed.

**Key findings**:
1. **`np.hanning()` — last remaining site** (HIGH) — one call site in `eq_processor.py:171` survived the D-NEW-01 fix. Will crash on NumPy ≥ 2.0.
2. **`sessionmaker(bind=engine)` deprecated in SQLAlchemy 2.0** (MEDIUM) — 5 sites. The `bind=` kwarg was removed; these calls work today but will break on SA 2.1.
3. **PyO3 `&PyArray` unbound refs** (MEDIUM) — all 11 `#[pyfunction]` wrappers use legacy GIL-ref forms, blocking PyO3 0.22+ upgrade.
4. **MUI Grid v1 deprecated API** (MEDIUM) — 10 files use `item xs sm md lg` props, blocking MUI v6 upgrade.
5. **Duplicate Vitest config** (MEDIUM) — `vite.config.mts` and `vitest.config.ts` both have conflicting `test:` blocks.
6. **Legacy `actix-web` deps in Rust crate** (MEDIUM) — heavy crates for a stub-only dev server, bloating every build.

**Prior audit progress**:
| Prior Finding | Status |
|---|---|
| D-NEW-01: `np.hann()` crash (10 sites) | **9/10 FIXED** — 1 remains (D-30) |
| D-NEW-02: PyO3 `&PyModule` | **FIXED** |
| D-NEW-03: `session.query()` (141 sites) | **133/141 FIXED** — 8 remain in one file |
| D-NEW-04: Vitest deprecated config | NOT FIXED (see D-54) |
| D-NEW-05: CI Python/Node versions | **MOSTLY FIXED** (1 action at v1) |
| D-NEW-06: CRA remnants | **FIXED** |
| D-NEW-07: `np.hamming()` (2 sites) | **FIXED** |
| D-NEW-08: `Column()` without `Mapped[]` (170 sites) | **FIXED** |
| D-NEW-09: `relationship()` without `Mapped[]` (13 sites) | **FIXED** |
| D-NEW-10: `React.FC` (280 occurrences) | **FIXED** |
| D-NEW-11: `datetime.utcnow()` (6 sites) | **FIXED** |
| D-NEW-12: Internal deprecated modules | Partially fixed — 1 production consumer remains |

---

## Findings

### HIGH Severity

---

### D-30: `np.hanning()` — last remaining call site in EQ processor
- **Severity**: HIGH
- **Dimension**: NumPy/SciPy
- **Location**: `auralis/core/processing/eq_processor.py:171`
- **Status**: Existing: D-NEW-01 (partially fixed — last remaining site)
- **Deprecated API**: `np.hanning(N)`
- **Deprecated Since**: NumPy 1.25 (removed in NumPy 2.0)
- **Replacement**: `scipy.signal.windows.hann(N)` (already used in 9 other files)
- **Affected Files**: 1 file, 1 call site
- **Evidence**:
  ```python
  synthesis_window = np.hanning(chunk_size)   # line 171
  ```
- **Migration Effort**: Small (1 site)
- **Risk**: **Runtime crash** (`AttributeError`) on NumPy ≥ 2.0 in the main EQ processing loop

---

### MEDIUM Severity

---

### D-40: `sessionmaker(bind=engine)` — deprecated in SQLAlchemy 2.0
- **Severity**: MEDIUM
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: 5 sites across 4 files
- **Status**: NEW
- **Deprecated API**: `sessionmaker(bind=engine)` keyword argument
- **Deprecated Since**: SQLAlchemy 2.0
- **Replacement**: `sessionmaker(engine)` (positional)
- **Affected Files**:
  - `auralis/library/manager.py:154`
  - `auralis/library/migration_manager.py:145`
  - `auralis/library/migrations/normalize_existing_artists.py:54`
  - `auralis/library/repositories/factory.py:40`
  - `auralis/analysis/fingerprint/fingerprint_service.py:99`
- **Migration Effort**: Small (5 sites)
- **Risk**: Will raise `TypeError` on SQLAlchemy 2.1+

---

### D-50: MUI Grid v1 deprecated API (`xs`/`sm`/`md`/`lg` props)
- **Severity**: MEDIUM
- **Dimension**: React/Redux/MUI
- **Location**: 10 files, ~22 JSX instances in `auralis-web/frontend/src/`
- **Status**: NEW
- **Deprecated API**: `<Grid item xs={12} sm={6}>` (Grid v1)
- **Deprecated Since**: MUI v5 (removed in v6)
- **Replacement**: `<Grid2 size={{ xs: 12, sm: 6 }}>` from `@mui/material/Grid2`
- **Migration Effort**: Medium (22 JSX instances, 10 files)
- **Risk**: Blocks MUI v6 upgrade

---

### D-53: Duplicate Vitest configuration across two files
- **Severity**: MEDIUM
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/vite.config.mts:147-182`, `auralis-web/frontend/vitest.config.ts`
- **Status**: NEW
- **Deprecated API**: `test:` block in `vite.config.mts` when `vitest.config.ts` exists
- **Replacement**: Keep only `vitest.config.ts`
- **Evidence**: `vite.config.mts` has `pool: 'threads'`, `vitest.config.ts` has `pool: 'forks'` — only the latter is used
- **Migration Effort**: Small (remove one config block)
- **Risk**: Confusion about active configuration; wrong settings may be assumed active

---

### D-60: PyO3 `&PyArray1`/`&PyArray2` unbound refs in all `#[pyfunction]` signatures
- **Severity**: MEDIUM
- **Dimension**: Rust/PyO3
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs` — 11 function signatures
- **Status**: NEW
- **Deprecated API**: `audio: &PyArray1<f64>` (GIL-ref form)
- **Deprecated Since**: PyO3 0.21
- **Removal Version**: PyO3 0.22
- **Replacement**: `audio: &Bound<'_, PyArray1<f64>>`
- **Affected Files**: 1 file, 11 functions
- **Migration Effort**: Medium (11 signatures + call-site updates)
- **Risk**: Blocks PyO3 0.22+ upgrade; compile warnings on current 0.21

---

### D-63: `actix-web`/`actix-rt` legacy deps for stub-only dev server
- **Severity**: MEDIUM
- **Dimension**: Rust/PyO3
- **Location**: `vendor/auralis-dsp/Cargo.toml:14-16`, `src/bin/fingerprint_server.rs`
- **Status**: NEW
- **Deprecated API**: Full web framework dependencies for a hardcoded-stub binary
- **Replacement**: Remove binary + deps, or gate behind Cargo feature flag
- **Migration Effort**: Small (delete 1 binary, 2 Cargo.toml lines)
- **Risk**: Adds ~30s to every `maturin develop` build with zero production value

---

### D-65: Production code imports deprecated `spectrum_analyzer.py` wrapper
- **Severity**: MEDIUM
- **Dimension**: Internal
- **Location**: `auralis/learning/reference_analyzer.py:21`
- **Status**: Existing: D-NEW-12 (partially fixed)
- **Deprecated API**: `from auralis.analysis.spectrum_analyzer import SpectrumAnalyzer`
- **Replacement**: `from auralis.analysis.base_spectrum_analyzer import BaseSpectrumAnalyzer`
- **Migration Effort**: Small (1 import)
- **Risk**: Chains two deprecated wrappers in a production call path; emits DeprecationWarning at runtime

---

### LOW Severity

---

### D-NEW-03 (updated): `session.query()` — reduced to 8 sites
- **Severity**: LOW (downgraded from MEDIUM — now contained in 1 file)
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: `auralis-web/backend/routers/library.py:780-787` — 8 sites in `_reset_all()`
- **Status**: Existing: D-NEW-03 (was 141 sites, now 8)
- **Migration Effort**: Small (8 sites, 1 file)

### D-31: `typing.Deque` deprecated alias
- **Severity**: LOW
- **Location**: 5 files, 7 annotation sites
- **Migration Effort**: Small

### D-32: `typing.Optional[X]` in SQLAlchemy models
- **Severity**: LOW
- **Location**: 6 model files, 67 annotations
- **Migration Effort**: Medium (mechanical sed)

### D-33: `os.path` usage where `pathlib` preferred
- **Severity**: LOW
- **Location**: 10 files, 27 call sites
- **Migration Effort**: Medium

### D-41: `pyproject.toml` stale dependency specs (pydantic>=1.8.0, etc.)
- **Severity**: LOW
- **Location**: `pyproject.toml:26-35`
- **Risk**: `pip install .` could resolve Pydantic V1, which is incompatible

### D-42: `pyproject.toml` classifiers include unsupported Python 3.12/3.13
- **Severity**: LOW
- **Location**: `pyproject.toml:21-22`

### D-43: `setup.cfg` tool config should migrate to `pyproject.toml`
- **Severity**: LOW
- **Location**: `setup.cfg`

### D-44: `pytest-asyncio` mode not configured
- **Severity**: LOW
- **Location**: `pytest.ini`

### D-45: `softprops/action-gh-release@v1` outdated
- **Severity**: LOW
- **Location**: `.github/workflows.backup/build-release.yml:408`

### D-46: `relationship(..., backref=...)` legacy pattern with `Mapped[]`
- **Severity**: LOW
- **Location**: `auralis/library/models/fingerprint.py:90,209`

### D-51: Dead `eslintConfig` in `package.json` references uninstalled CRA config
- **Severity**: LOW
- **Location**: `auralis-web/frontend/package.json:60-65`

### D-52: `browserslist` CRA remnant in `package.json`
- **Severity**: LOW
- **Location**: `auralis-web/frontend/package.json:66-77`

### D-54: Invalid/unrecognized options in `vitest.config.ts`
- **Severity**: LOW
- **Location**: `auralis-web/frontend/vitest.config.ts`
- **Details**: `transformMode`, `environmentSetupModule`, `dom:`, `forceExitTimeout` — all silently ignored

### D-55: `electron-log` v4 — two major versions behind
- **Severity**: LOW
- **Location**: `desktop/package.json`

### D-56: `@types/node` pinned to `^20` while Node 24+ required
- **Severity**: LOW
- **Location**: `auralis-web/frontend/package.json:82`

### D-57: `async` Promise executor anti-pattern in `desktop/main.js`
- **Severity**: LOW
- **Location**: `desktop/main.js:107`

### D-58: Stale `desktop/main-updated.js` artifact
- **Severity**: LOW
- **Location**: `desktop/main-updated.js`

### D-59: `@types/react-virtualized` unused in `devDependencies`
- **Severity**: LOW
- **Location**: `auralis-web/frontend/package.json:83`

### D-61: `PyDict::new_bound()` will rename in PyO3 0.22
- **Severity**: LOW
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs` — 5 sites

### D-62: `ToPyArray` trait imported but unused
- **Severity**: LOW
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:10`

### D-66: `quality_metrics.py` removal deadline (v1.2.0) has passed
- **Severity**: LOW
- **Location**: `auralis/analysis/quality_metrics.py`

### D-67: 6 deprecated fingerprint compat wrappers consumed only by tests
- **Severity**: LOW
- **Location**: 6 wrapper files + ~10 test files

### D-68: Deprecated `require_library_manager` still wired in player router
- **Severity**: LOW
- **Location**: `auralis-web/backend/routers/player.py:188,230,296`

### D-70: Deprecated frontend hooks `useCurrentTrack`/`useIsPlaying` (test-only consumer)
- **Severity**: LOW
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackState.ts:189,219`

---

## Dependency Upgrade Roadmap

| Package | Current | Target | Blocked By | Priority |
|---------|---------|--------|------------|----------|
| NumPy | 2.3.5 | — | `np.hanning()` crash (D-30) | **HIGH** — fix immediately |
| SQLAlchemy | 2.0 | 2.1+ | `sessionmaker(bind=)` (D-40), `session.query()` (8 sites) | MEDIUM |
| PyO3 | 0.21 | 0.22+ | `&PyArray` sigs (D-60), `PyDict::new_bound` (D-61), `ToPyArray` (D-62) | MEDIUM |
| MUI | 5.18 | 6.x | Grid v1 (D-50) | MEDIUM |
| Vitest | 3.2.4 | — | Duplicate config (D-53), invalid options (D-54) | LOW |
| electron-log | 4.4.8 | 5.4.3 | None (compatible API) | LOW |

## Migration Effort Summary

| Finding | Effort | Sites | Files |
|---------|--------|-------|-------|
| D-30: np.hanning() | Small | 1 | 1 |
| D-40: sessionmaker(bind=) | Small | 5 | 4 |
| D-50: MUI Grid v1 | Medium | 22 | 10 |
| D-53: Duplicate Vitest config | Small | 1 | 1 |
| D-60: PyO3 &PyArray | Medium | 11 | 1 |
| D-63: actix-web legacy | Small | 2 | 2 |
| D-65: Deprecated wrapper import | Small | 1 | 1 |
| D-NEW-03: session.query() | Small | 8 | 1 |
| D-32: Optional[X] → X \| None | Medium | 67 | 6 |
| D-33: os.path → pathlib | Medium | 27 | 10 |
| D-67: Compat wrapper test imports | Medium | ~15 | ~10 |
| All other LOW findings | Small | <5 each | 1-2 each |

## Recommended Migration Order

1. **D-30**: Fix `np.hanning()` — 1-line fix, prevents runtime crash
2. **D-40**: Fix `sessionmaker(bind=)` — 5-line fix, prevents SA 2.1 breakage
3. **D-63**: Remove `actix-web` legacy deps — speeds up every Rust build
4. **D-65**: Update production deprecated import — 1-line fix
5. **D-50**: Migrate MUI Grid v1 → Grid2 — before MUI v6 upgrade
6. **D-60**: Migrate PyO3 `&PyArray` signatures — before PyO3 0.22 upgrade
7. **D-53**: Remove duplicate Vitest config — eliminates confusion
8. Remaining LOW items at convenience
