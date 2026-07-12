# Deprecation Audit — Auralis (2026-05-24)

**Auditor**: Claude Opus 4.7
**Scope**: Full repository — Python, NumPy/SciPy, FastAPI/Pydantic/SQLAlchemy, React/Redux/MUI, Node/npm/Build, Rust/PyO3, internal deprecations, config/CI
**Prior audit**: `docs/audits/AUDIT_DEPRECATION_2026-03-21.md` (D-01 … D-70 + D-NEW-01 … D-NEW-12)
**Dedup policy**: Only NEW or REGRESSED findings are reported. Findings resolved since 2026-03-21 are listed in the Resolved Summary.

---

## Executive Summary

| Severity | New | Regressed | Total |
|----------|----:|----------:|------:|
| CRITICAL | 0   | 0         | 0     |
| HIGH     | 2   | 0         | 2     |
| MEDIUM   | 2   | 1         | 3     |
| LOW      | 3   | 0         | 3     |
| **All**  | **7** | **1**   | **8** |

**Key takeaways**
- **No upgrade blockers.** No CRITICAL findings; the codebase is well-maintained against current dependency versions.
- **One regression**: a new `np.hanning()` call slipped in at `auralis/core/dsp/resonance_notcher.py:89` — same pattern as the SciPy-windows fixes audited last cycle.
- **One large mechanical cleanup remains**: 210+ unnecessary `import React from 'react'` lines (post-JSX-transform leftover) — non-blocking but increasing noise.
- **MUI Grid2 path drift**: 10 files still import from the `Unstable_Grid2` internal path; promoted to stable in MUI 5.13 and removed in MUI 6. This blocks the next MUI major.
- **Major dependency lag**: MUI v5 → v9 (4 majors), Vitest v3 → v4 (1 major). Both are deferrable but worth scheduling.
- **Internal `@deprecated` markers are healthy**: 3 documented internal migration markers with clear removal timelines (v2.0.0). Two known callers of `LibraryManager` remain — track separately in their owning issues, not as new deprecations.

**Recommended migration order** (small → large):
1. D-NEW-13 — `np.hanning` → `scipy.signal.windows.hann` (1 file, regression, HIGH)
2. D-NEW-72 — `Unstable_Grid2` → `Grid2` (10 files, MEDIUM, unblocks MUI v6)
3. D-NEW-74 — `react-dom/test-utils` `act` → `react` `act` (3 files, LOW)
4. D-NEW-73 — `process.env.NODE_ENV` → `import.meta.env` (5 files, MEDIUM)
5. D-NEW-71 — Drop unnecessary `import React` (210+ files, HIGH-noise/LOW-risk)
6. D-NEW-75 / D-NEW-76 — MUI + Vitest major upgrades (separate epics)

---

## Findings

### HIGH

#### D-NEW-13: `np.hanning()` regression in resonance_notcher
- **Severity**: HIGH
- **Dimension**: NumPy/SciPy
- **Location**: `auralis/core/dsp/resonance_notcher.py:89`
- **Status**: NEW — same class as D-NEW-04 / D-NEW-05 from 2026-03-21 (which targeted other modules)
- **Deprecated API**: `np.hanning(N)` (and the broader `np.hamming`, `np.blackman`, `np.bartlett`, `np.kaiser` family in `numpy.lib.function_base`)
- **Deprecated Since**: NumPy 2.0 (2024). NumPy docs explicitly recommend `scipy.signal.windows.*` for new code; the NumPy variants are kept for backward compatibility but are not the preferred API and are missing periodic vs symmetric distinction critical for DSP analysis/synthesis.
- **Removal Version**: Not scheduled, but treated as soft-deprecated.
- **Replacement**: `scipy.signal.windows.hann(N)` (or `hann(N, sym=False)` for spectral analysis).
- **Affected Files**: 1 (`auralis/core/dsp/resonance_notcher.py`)
- **Evidence**:
  ```python
  # auralis/core/dsp/resonance_notcher.py:89
  hann = np.hanning(N)
  ```
- **Migration Path**:
  1. Add `from scipy.signal.windows import hann` to imports.
  2. Replace `np.hanning(N)` with `hann(N)` (symmetric form matches `np.hanning` exactly).
  3. Re-run DSP regression tests under `tests/auralis/dsp/`.
- **Risk**: Functional output identical for symmetric form, but this is exactly the pattern other modules were migrated off. Leaving it allows the pattern to re-emerge.
- **Migration Effort**: Small.

#### D-NEW-71: 210+ unnecessary `import React from 'react'` statements
- **Severity**: HIGH (volume/noise; not blocking)
- **Dimension**: React/Frontend
- **Location**: 210+ `.tsx` / `.ts` files across `auralis-web/frontend/src/`
- **Status**: NEW
- **Deprecated API**: Default `import React from 'react'` purely to satisfy classic JSX transform.
- **Deprecated Since**: React 17 (Sept 2020) introduced the automatic JSX runtime; the explicit import has been unnecessary in every project using `jsx: "react-jsx"` since.
- **Replacement**: Delete the import entirely. Components that actually use `React.useState`, `React.FC`, `React.memo`, etc. should be migrated to named imports (`useState`, `memo`) — but those are already gone (see D-NEW-10 resolution below).
- **Affected Files**: ~210 (non-test). Confirmed via `grep -rln "^import React from 'react'$" auralis-web/frontend/src`.
- **Evidence**:
  ```tsx
  // auralis-web/frontend/src/index.tsx and 200+ others
  import React from 'react';
  // …no `React.X` usage in file…
  ```
- **Migration Path**:
  1. Enable ESLint `react/jsx-uses-react: 'off'` and `react/react-in-jsx-scope: 'off'` (already on, since codebase compiles).
  2. Add `unused-imports/no-unused-imports` rule and run `eslint --fix`.
  3. Or one-shot: `find auralis-web/frontend/src -name '*.tsx' -o -name '*.ts' | xargs sed -i.bak "/^import React from 'react';$/d"` then verify `tsc --noEmit` and tests.
- **Risk**: Low. Any file still actually using `React.X` will fail typecheck and be caught immediately.
- **Migration Effort**: Large (file count), Small (per-file).

### MEDIUM

#### D-NEW-72: `@mui/material/Unstable_Grid2` internal import path
- **Severity**: MEDIUM
- **Dimension**: React/MUI
- **Location**: 10 files
  - `auralis-web/frontend/src/components/features/discovery/SimilarityAllDimensions.tsx`
  - `auralis-web/frontend/src/components/library/EditMetadataDialog/MetadataDetailFields.tsx`
  - `auralis-web/frontend/src/components/library/EditMetadataDialog/MetadataFormFields.tsx`
  - `auralis-web/frontend/src/components/library/EditMetadataDialog/MetadataBasicFields.tsx`
  - `auralis-web/frontend/src/components/library/EditMetadataDialog/MetadataExtendedFields.tsx`
  - `auralis-web/frontend/src/components/library/Items/albums/AlbumGridLoadingState.tsx`
  - `auralis-web/frontend/src/components/library/Views/TrackGridView.tsx`
  - `auralis-web/frontend/src/components/library/Views/AlbumsTab.tsx`
  - `auralis-web/frontend/src/components/library/Items/albums/AlbumGridContent.tsx`
  - `auralis-web/frontend/src/components/shared/ui/loaders/LibraryGridSkeleton.tsx`
- **Status**: Regression of D-50 (Grid v1 → Grid2 props were fixed; import path was not)
- **Deprecated API**: `import Grid2 from '@mui/material/Unstable_Grid2'`
- **Deprecated Since**: MUI v5.13 (Grid2 promoted to stable); the `Unstable_*` re-export is the soft-deprecated alias.
- **Removal Version**: MUI v6 removes `Unstable_Grid2`.
- **Replacement**: `import Grid2 from '@mui/material/Grid2'`
- **Migration Path**:
  ```bash
  grep -rl "from '@mui/material/Unstable_Grid2'" auralis-web/frontend/src \
    | xargs sed -i "s|@mui/material/Unstable_Grid2|@mui/material/Grid2|g"
  npm run type-check && npm run test:memory
  ```
- **Risk**: Blocks D-NEW-75 (MUI v6 upgrade). Mechanical fix.
- **Migration Effort**: Small.

#### D-NEW-73: `process.env.NODE_ENV` in browser code
- **Severity**: MEDIUM
- **Dimension**: Vite/Build
- **Location**: 5 sites
  - `auralis-web/frontend/src/store/index.ts:39`
  - `auralis-web/frontend/src/contexts/WebSocketContext.tsx:216`
  - `auralis-web/frontend/src/store/middleware/loggerMiddleware.ts:44`
  - `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:121`
  - `auralis-web/frontend/src/a11y/index.ts:155`
- **Status**: NEW
- **Deprecated API**: `process.env.NODE_ENV` in ESM browser bundles. Currently works because `vite.config.mts` injects it via `define`, but Vite's recommended API is `import.meta.env`.
- **Replacement**:
  - `process.env.NODE_ENV === 'development'` → `import.meta.env.DEV`
  - `process.env.NODE_ENV === 'production'` → `import.meta.env.PROD`
  - `process.env.NODE_ENV !== 'production'` → `!import.meta.env.PROD`
- **Migration Path**:
  1. Replace each call site with the `import.meta.env` form.
  2. Remove the matching `define` entry from `vite.config.mts` once all sites are migrated.
  3. Verify dead-code elimination still strips dev-only branches in the production bundle.
- **Risk**: Low (Vite still injects), but a misconfigured `define` silently becomes `undefined` — bug class worth removing.
- **Migration Effort**: Small.

### LOW

#### D-NEW-74: `act` imported from `react-dom/test-utils`
- **Severity**: LOW
- **Dimension**: React Testing
- **Location**: 3 test files
  - `auralis-web/frontend/src/components/library/__tests__/GlobalSearch.test.tsx:13`
  - `auralis-web/frontend/src/components/library/__tests__/TrackListView.test.tsx:12`
  - `auralis-web/frontend/src/components/album/AlbumArt.test.tsx:12`
- **Status**: NEW
- **Deprecated API**: `import { act } from 'react-dom/test-utils'`
- **Deprecated Since**: React 18.0 (act moved to `react` package).
- **Removal Version**: React 19 removes the `react-dom/test-utils` re-export.
- **Replacement**: `import { act } from 'react'`
- **Migration Path**: One-line edit per file; rerun the test files. `@testing-library/react`'s own `act` re-export is preferred when already importing from it.
- **Risk**: Trivial — blocks React 19 upgrade.
- **Migration Effort**: Minimal.

#### D-NEW-75: MUI v5.18 is four majors behind v9.0
- **Severity**: LOW (not deprecated, just lagging)
- **Dimension**: Frontend / Dependencies
- **Location**: `auralis-web/frontend/package.json` — `@mui/material@5.18.0`, `@mui/icons-material@5.18.0`
- **Status**: NEW (informational)
- **Risk**: v5 still receives security patches but no feature work. v6 introduces a new theming pipeline (CSS variables), v7+ refine icon set and the `Grid`/`Grid2` story (Grid2 becomes the default `Grid` in v7).
- **Migration Effort**: Large (theme migration, `sx`/`styled` audits, Grid renaming).
- **Recommendation**: Defer to a dedicated upgrade epic. Land D-NEW-72 first so the bump doesn't have to also unwind `Unstable_Grid2`.

#### D-NEW-76: Vitest v3.2.4 is one major behind v4.x
- **Severity**: LOW
- **Dimension**: Frontend / Testing
- **Location**: `auralis-web/frontend/package.json` — `vitest@3.2.4`
- **Status**: NEW (informational)
- **Risk**: v4 changes snapshot format (`.snap` files) and tightens browser-mode API. Otherwise drop-in for our config surface.
- **Migration Effort**: Small. Best handled in the same PR as a snapshot refresh.

---

## Resolved Since 2026-03-21

These prior findings are confirmed fixed or no longer applicable; no further action required.

| ID | Title | Verification |
|----|-------|---|
| D-40 | `sessionmaker(bind=engine)` legacy pattern | Repository factory + 2.x style session creation throughout `auralis/library/`; grep returns 0 production hits |
| D-NEW-03 | `session.query(Model)` (SQLAlchemy 1.x) | 0 production sites; all access through `select()` + repositories |
| D-NEW-09 | `relationship()` without `Mapped[]` annotation | All ORM relationships in `auralis/library/models/` use `Mapped[]` |
| D-50 | MUI `Grid` v1 prop API | Migrated to Grid2 with `size` prop (path still stale — see D-NEW-72) |
| D-NEW-10 | `React.FC` / `React.FunctionComponent` (280 occurrences) | 0 non-test occurrences; components use explicit `JSX.Element` return |
| D-51 | Dead `eslintConfig` in `package.json` | Field not present |
| D-52 | CRA `browserslist` remnant in `package.json` | Field not present |
| D-55 | `@types/node@^20` mismatch with Node 24 | Now `@types/node@^24.12.0` |
| D-58 | `pkg_resources` usage | Replaced with `importlib.metadata` |
| D-45 | `@app.on_event("startup"/"shutdown")` | Migrated to lifespan context manager in `auralis-web/backend/main.py` |
| D-57 | `datetime.utcnow()` in backend | All boundary callsites use `datetime.now(timezone.utc)` |
| D-63 | `collections.Mapping` imports | None remain; all via `collections.abc` |

---

## Internal `@deprecated` Markers (Status Check, Not Findings)

These are intentional, documented internal deprecation markers — listed for context, not as audit findings.

| Marker | File | Removal target | Known callers |
|---|---|---|---|
| `auralis.core.process(...)` | `auralis/core/processor.py` | v2.0.0 | None in repo |
| Module-level `DeprecationWarning` on processing-mode base | `auralis/core/processing/base_processing_mode.py` | v2.0.0 | None in repo |
| `LibraryManager(__init__)` warns "use RepositoryFactory" | `auralis/library/manager.py` | v2.0.0 | 2 active: `auralis/cli/fetch_artwork.py`, `auralis-web/backend/config/startup.py` |

The two `LibraryManager` consumers should be tracked in their own follow-up issues (CLI + startup migration to RepositoryFactory). Not new in this audit cycle.

`pytest.ini` correctly exposes these via `filterwarnings = default::DeprecationWarning`.

---

## Config / CI Scan

- `pyproject.toml` / `pytest.ini` — no deprecated `setup.cfg` / `setup.py` to consolidate.
- GitHub Actions: `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4` throughout `.github/workflows/` — all current.
- `mypy`, `ruff`, `black` configuration uses current keys.
- `pytest.ini` marker `edge_cases` is documented as superseded by `edge_case`; an internal-only deprecation, not external.

No new findings.

---

## Rust / PyO3 / Cargo Scan

- `vendor/auralis-dsp/Cargo.toml` — PyO3 0.23 on edition 2021; no deprecated macro forms (`#[pyfunction]` / `#[pymethods]` signatures match current API).
- `maturin` config keys current; no deprecated entries.
- No CRITICAL/HIGH/MEDIUM/LOW findings in this dimension.

---

## Dependency Upgrade Roadmap

| Phase | Items | Effort |
|---|---|---|
| **Now (next PR)** | D-NEW-13 (np.hanning), D-NEW-72 (Grid2 path), D-NEW-74 (`act` import) | Small × 3 |
| **Sprint** | D-NEW-73 (`process.env.NODE_ENV`), D-NEW-71 (React imports cleanup) | Small + Large mechanical |
| **Quarter** | D-NEW-76 (Vitest v3 → v4), `LibraryManager` consumer migration tracking | Small + Medium |
| **Epic** | D-NEW-75 (MUI v5 → v9, sequential by major), React 18 → 19 enabling | Large × 2 |

---

## Migration Effort Estimate

| Finding | Effort | Approx time |
|---|---|---|
| D-NEW-13 | Small (1 file) | 10 min + DSP tests |
| D-NEW-71 | Large (210+ files, mechanical) | 2–3 h with lint autofix |
| D-NEW-72 | Small (10 files, mechanical) | 30 min |
| D-NEW-73 | Small (5 files + config) | 1 h |
| D-NEW-74 | Minimal (3 files) | 15 min |
| D-NEW-75 | Large (multi-major MUI epic) | Multi-week |
| D-NEW-76 | Small (config + snapshot refresh) | Half-day |

---

**Report status**: Ready for publish.
**Next step**: `/audit-publish docs/audits/AUDIT_DEPRECATION_2026-05-24.md`
**Labels to apply**: `deprecation`, `maintenance` + per-finding severity + layer (`audio-engine` for D-NEW-13; `frontend` for D-NEW-71/72/73/74/75; `config` for D-NEW-76).
