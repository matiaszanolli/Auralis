# Deprecation Audit — 2026-11-17

**Scope**: Python stdlib and language, NumPy/SciPy/audio libs, FastAPI/Pydantic/SQLAlchemy, React/Redux/MUI, Node/npm/build, Rust/PyO3/Cargo, internal deprecations, config/CI.
**Method**: Fresh read of the live tree. Each pattern was grepped across `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `desktop/`, `scripts/`, `tests/`, `vendor/auralis-dsp/` and the root files. Static sweeps also used `ruff --select UP,DTZ,PTH,B,NPY` (ruff 0.12.12 with `--isolated --target-version py314`) and `cargo check --offline --locked` on the Rust crate. Runtime checks: every key module imported with `-W always::DeprecationWarning`, and several scoped pytest files run with a scratch `HOME` (the real `~/.auralis` library was not touched).
**Dedup**: `gh issue list --state all` dump taken; its highest issue number (6346) matches the highest-number probe. Every finding was title-searched against it.

## 1. Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 6 |
| **Total (all NEW)** | **6** |

The tree is clean of the deprecations this audit is built to catch. There is no `utcnow`, `pkg_resources`, `distutils`, NumPy 1.x alias, Pydantic V1 idiom, `@app.on_event`, SQLAlchemy `Query` API, `ReactDOM.render`, `defaultProps`, `React.FC`, MUI `@mui/styles`/`Grid2`/`*Props` slot prop, `createScriptProcessor` outside the documented fallback, or `PYO3_USE_ABI3_FORWARD_COMPATIBILITY`. All 57 `uses:` entries across the 11 workflows are SHA-pinned at current majors, and every Python CI job is on 3.14. `cargo check` on pyo3/numpy 0.29 emits zero warnings. Importing the engine, backend and the librosa/scipy/soundfile stack under `-W always::DeprecationWarning` emits nothing.

The six findings are all LOW. The one worth acting on first is **DEP-1**: the `numpy<2.5` ceiling in `pyproject.toml` carries a "revisit when numba supports numpy 2.5" note, and numba now does.

**Upgrade blockers**: none. **Recommended migration order**: DEP-1 (unblocks the numpy/numba bump), then DEP-2 (CI reproducibility), then DEP-3 to DEP-6 (housekeeping, any order).

### Previously reported items re-verified as still fixed (no regressions)
#5436 (JSX global namespace; `import type { JSX } from 'react'` is in `Box.tsx` and `ErrorBoundary.test.tsx`), #5435 (`baseUrl` gone), #5433 (`rolldownOptions`), #5431 (vitest `benchmark.outputJson`), #5430, #5415 (`len(SoundFile)`), #5413 (`mktemp`), #5410 (`asyncio.TimeoutError`: 0 hits), #5408 (`Mapping`/`Sequence`; `Callable` was left, see DEP-4), #4957 (`asyncio.iscoroutinefunction`; only `inspect.iscoroutinefunction` remains), #4894 (httpx2), #5441 (PEP 639 license), #5437 (mypy overrides), #6282, #6285 (`Grid2`), #4959, #5485 (pyo3 0.29, ABI3 flag absent).

### Deliberately kept, not findings
- `ScriptProcessorNode` fallback in `auralis-web/frontend/src/services/audio/BufferScheduler.ts`. It is kept on purpose (#4623 decision) and annotated in-code. `navigator.platform` in `keyboardShortcutsService.ts` is a tertiary fallback behind `userAgentData` (#4556).
- `from __future__ import annotations` (98 files), `np.random.seed`/`randn` legacy API (397 test sites) and naive `datetime.now()` (48 sites). None is deprecated in the pinned versions. They are style or semantics notes outside this audit's scope.
- The 5 registry-deprecated packages in `desktop/pnpm-lock.yaml` (`boolean`, `glob@7.2.3`, `inflight`, `lodash.isequal`, `rimraf@2.6.3`) are upstream-blocked via electron-builder/@electron/asar and electron-updater, as recorded in the closed #5429. `frontend/pnpm-lock.yaml` and root `pnpm-lock.yaml` carry none.

## 2. Findings

### DEP-1: `numpy<2.5` ceiling's own revisit condition is now met (numba 0.68.1)
- **Severity**: LOW
- **Dimension**: NumPy/SciPy
- **Location**: `pyproject.toml:45-53`; `requirements.txt:17` (`numpy==2.4.6`); `requirements-lock.txt`; `uv.lock` (numba 0.66, llvmlite 0.48)
- **Status**: NEW
- **Deprecated API**: A stale version cap, not an API. The cap comment says "numba 0.66 (the newest with cp314 wheels) requires `numpy<2.5` ... Revisit when numba supports numpy 2.5."
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: Allow `numpy>=2.4,<2.6` (or move to 2.5.x) and bump numba to 0.68.x with llvmlite to match.
- **Affected Files**: 4 manifests and locks. Code impact is whatever NumPy 2.5 deprecates, which the clean grep makes unlikely.
- **Evidence**: PyPI metadata fetched 2026-11-17 shows `numba 0.68.1` (uploaded 2026-10-27) with `Requires-Dist: numpy<2.6,>=1.22` and cp314 manylinux wheels (x86_64 and aarch64). `numpy 2.5.5` was released 2026-11-15, and `librosa 1.0.1` requires `numpy>=2.1.0`. Installed locally are numpy 2.4.6 and numba 0.66.0.
- **Migration Path**: (1) In a scratch venv, install numpy 2.5.5, numba 0.68.1 and llvmlite 0.50 against the current `requirements.txt`. (2) Run the scoped DSP, analysis and fingerprint test dirs with `-W error::DeprecationWarning`. (3) Relax the cap in `pyproject.toml` and `requirements.txt`. (4) Regenerate `requirements-lock.txt` and `uv.lock`. (5) Confirm the Rust `numpy` crate (0.29) still loads against NumPy 2.5 with `maturin develop` and `tests/auralis/analysis/fingerprint`. The July 2026 ABI blocker was NumPy 2.3.x-specific, but re-test.
- **Risk**: No breakage today. The cost is falling behind: `numpy` 2.4 will stop receiving fixes, and the longer the gap, the larger the deprecation delta when the cap is eventually lifted.

### DEP-2: CI installs pytest plugins unpinned and unhashed next to a hash-locked tree
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `.github/workflows/backend-tests.yml:128`, `.github/workflows/slow-tests.yml:36`
- **Status**: NEW (the closed #5444 fixed only the comment, and the closed #6283 fixed the floors)
- **Deprecated API**: Unpinned `pip install` of test-time plugins.
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: Hash-lock the test extras (add them to `requirements-lock.txt` or a sibling lock) and install with `--require-hashes`, or pin exact versions to match `uv.lock` (pytest-asyncio 1.4.0 and so on).
- **Affected Files**: 2 workflows
- **Evidence**:
  ```
  pip install --require-hashes -r requirements-lock.txt
  # Exact pin for baseline reproducibility ... pytest-baseline.json records failures observed at this version
  pip install 'pytest==9.0.1' pytest-asyncio pytest-timeout httpx2
  ```
  `pytest` is pinned exactly "for baseline reproducibility", but `pytest-asyncio`, `pytest-timeout` and `httpx2` float to whatever PyPI serves. `pytest.ini` runs `asyncio_mode = auto` with `--strict-config`, and `httpx2` backs Starlette's `TestClient`. None of the three is in `requirements-lock.txt`.
- **Migration Path**: Add the three plugins (and `pytest-cov` if used) to the locked set, or pin them to `uv.lock` versions in both workflows. Regenerate `pytest-baseline.json` from a CI artifact if the plugin set changes behaviour.
- **Risk**: A plugin major bump on PyPI can change event-loop scope or collection behaviour and flip the ratchet gate red (or silently green) with no repo change. This is the same failure mode the existing `pytest==9.0.1` pin was added to prevent.

### DEP-3: anyio 4.14.2 pytest plugin emits `PytestRemovedIn10Warning` on every local pytest run
- **Severity**: LOW
- **Dimension**: Python Stdlib (third-party test tooling)
- **Location**: `uv.lock` (anyio 4.14.2); `requirements-lock.txt:182`
- **Status**: NEW
- **Deprecated API**: `from _pytest.python import CallSpec2` in `anyio/pytest_plugin.py:14`
- **Deprecated Since**: pytest 9.1 (alias renamed to `CallSpec`)
- **Removal Version**: pytest 10
- **Replacement**: anyio 4.16.0, whose `pytest_plugin.py` imports `CallSpec` and keeps `CallSpec2` only as a fallback (checked in the 4.16.0 wheel).
- **Affected Files**: 0 first-party. It is a transitive dependency auto-loaded as a pytest plugin.
- **Evidence**: Reproduced at the head of every scoped run on the local pytest 9.1.1:
  ```
  .venv/lib/python3.14/site-packages/anyio/pytest_plugin.py:14: PytestRemovedIn10Warning:
  _pytest.python.CallSpec2 has been renamed to CallSpec. The CallSpec2 alias will be removed in pytest 10.
  ```
  It is not visible on CI, which pins pytest 9.0.1.
- **Migration Path**: Bump anyio to 4.16.0 in `requirements-lock.txt` and `uv.lock` (it pairs with starlette and httpx). Optionally pass `-p no:anyio`, since the suite uses pytest-asyncio.
- **Risk**: This becomes a hard import error when pytest 10 lands, and the project's `minversion` and floor policy already track pytest 9.1+. It is also the single warning in an otherwise silent summary, which hides any future real one.

### DEP-4: Residual legacy `typing.Callable` and exception aliases (15 sites)
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `typing.Callable` in 7 files, `socket.timeout` in 1 file (4 sites), `IOError` in 4 sites. See Evidence.
- **Status**: NEW (siblings of the closed #5408 and #5410, which fixed `Mapping`/`Sequence` and `asyncio.TimeoutError` only)
- **Deprecated API**: `typing.Callable` (deprecated alias of `collections.abc.Callable` since 3.9). `socket.timeout` (alias of `TimeoutError` since 3.10). `IOError` (alias of `OSError`).
- **Deprecated Since**: 3.9 / 3.10 / 3.3
- **Removal Version**: None announced (aliases persist). Linters flag them (ruff UP035, UP041, UP024).
- **Replacement**: `from collections.abc import Callable`, `TimeoutError`, `OSError`.
- **Affected Files**: 11 (1 in `auralis/`, 3 in `scripts/`, 7 in `tests/`)
- **Evidence**:
  ```
  auralis/player/audio_file_manager.py:15           from typing import Callable, cast
  tests/conftest.py:11, tests/auralis/player/conftest.py:8, tests/auralis/dsp/test_no_op_returns_copy_4900.py:24,
  tests/concurrency/helpers.py:16, tests/performance/helpers.py:11, tests/stress/helpers.py:16   (same import)
  tests/edge_cases/test_network_failures.py:68,158,180,204   except socket.timeout
  scripts/analyze_feedback.py:46, scripts/update_profile.py:84,113, tests/test_migrations.py:503   IOError
  ```
- **Migration Path**: `ruff check --isolated --select UP035,UP041,UP024 --fix` over those files (all 15 diagnostics are auto-fixable).
- **Risk**: None functional. This is consistency with the project's own PEP 585/604 sweep (#5408, #4959).

### DEP-5: Unused `concurrently` and `shell-quote` dependencies in the root `package.json`
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `package.json:43-48`; `pnpm-lock.yaml`
- **Status**: NEW
- **Deprecated API**: Stale, unreferenced dependencies. `concurrently ^8.2.2` is a devDependency, and `shell-quote` is pinned at exactly `1.11.0` as a runtime dependency (apparently a transitive advisory pin for `concurrently`).
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: Delete both and regenerate `pnpm-lock.yaml`. `dev.js` is a hand-rolled `child_process` launcher.
- **Affected Files**: 2 (`package.json`, `pnpm-lock.yaml`)
- **Evidence**: A grep for `concurrently` and `shell-quote` across `*.js`, `*.mjs`, `*.cjs`, `*.ts`, `*.json` and `*.yml` outside `node_modules` hits only `package.json` and the lockfile. `dev.js`, `build.js` and `package.js` use only `node:` built-ins. `dependency-audit.yml` still scans this tree, so any advisory against either package would block CI for a package nothing uses.
- **Migration Path**: Remove both entries, run `pnpm install`, commit the lock, and confirm `lockfile-guard.yml` and `dependency-audit.yml` stay green.
- **Risk**: Pure attack-surface and audit-noise cost. There is no functional risk.

### DEP-6: Orphaned `tools/alembic.ini` and `MANIFEST.in` (legacy tooling configs)
- **Severity**: LOW
- **Dimension**: Internal / Config/CI
- **Location**: `tools/alembic.ini`; `MANIFEST.in`
- **Status**: NEW
- **Deprecated API**: Config for tools the project no longer uses. Alembic was replaced by forward-only SQL migrations (`auralis/library/migrations/`), and `pyproject.toml` builds with hatchling, which ignores `MANIFEST.in` (a setuptools sdist file).
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: Delete both.
- **Affected Files**: 2
- **Evidence**: `tools/alembic.ini` sets `script_location = backend/alembic`, but there is no `backend/` directory and no `alembic` dependency (the only mention in `requirements.txt` is a commented-out line, "not needed at runtime"). The build-system block in `pyproject.toml` is `requires = ["hatchling"]`; `[tool.hatch.build.targets.wheel] packages = ["auralis"]` is the only packaging config. `MANIFEST.in` lists `README.md`, `LICENSE` and `requirements.txt`, and nothing references it.
- **Migration Path**: `git rm tools/alembic.ini MANIFEST.in`. Keep `tools/validation/`.
- **Risk**: A contributor may run `alembic` against a database whose schema is managed by `migration_manager.py`, or edit `MANIFEST.in` expecting it to change the wheel.

## 3. Dependency Upgrade Roadmap

Versions are installed vs latest as of 2026-11-17. This is informational. Only DEP-1 is a finding.

| Order | Package | Installed | Latest | Notes |
|-------|---------|-----------|--------|-------|
| 1 | numpy / numba / llvmlite | 2.4.6 / 0.66 / 0.48 | 2.5.5 / 0.68.1 / 0.50 | DEP-1. Gate on the DSP, analysis and fingerprint test dirs. Re-test the Rust `numpy` 0.29 crate against NumPy 2.5. |
| 2 | anyio | 4.14.2 | 4.16.0 | DEP-3. Also clears a local-only pytest-10 warning. |
| 3 | pydantic / pydantic-core | 2.13.4 / 2.46.4 | 2.14.3 / 2.50.4 | No V1 idioms present, so a low-risk minor bump. |
| 4 | fastapi / starlette | 0.141.1 / 1.3.1 | 0.163.2 / 1.10.0 | The 22-minor FastAPI gap is the largest runtime drift. Run `tests/backend` per file (it does not go green as a whole). Starlette 1.x is already in use. |
| 5 | SQLAlchemy | 2.0.51 | 2.1.9 | The codebase is already 2.0-style (`DeclarativeBase`, `Mapped[]`, `select()`, `sessionmaker(engine)`, `query_expression`). Review the 2.1 changelog before bumping. |
| 6 | multidict | 6.7.1 | 7.2.1 | Major, transitive via aiohttp. Gated by `dependency-audit.yml`. |
| 7 | MUI | 9.0.1 | 9.5.0 | Same major. Grid is already the v2 `size` API. |
| 8 | Vitest / @vitest/* | 4.1.12 | 5.1.0 | Major. The config already uses v4 top-level pool options. Check `snapshotFormat` and `mockReset`. |
| 9 | jsdom, @testing-library/jest-dom | 30.1.0, 6.9.1 | 31.0.1, 7.0.1 | Majors. The jsdom 30 FocusTrap history is in the closed #6008. |
| 10 | React / @types/react | 18.2 / 18.3.27 | 19 / 19.3.0 | Deferred. The tree is React 19-friendly except `forwardRef` (8 files, 16 sites), `Context.Provider` (5 files, 12 sites) and one zero-argument `useRef<AbortController>()` at `hooks/enhancement/useAudioStreamingCore.ts:101`. No action is needed until React 19 is adopted. |
| 11 | Electron / electron-builder | ^43.8.3 / ^26.15.7 | not checked | The `desktop/` source uses no removed Electron API. The 5 registry-deprecated transitives are upstream-blocked (closed #5429). |
| — | pyo3 / numpy-rs / ndarray / rustfft | 0.29 / 0.29 / 0.16 / 6.4 | not checked | `cargo check --locked` gives zero warnings. `Cargo.lock` is tracked and `rust-toolchain.toml` pins 1.96.0. |

## 4. Migration Effort Estimate

| Finding | Effort | Call sites |
|---------|--------|-----------|
| DEP-1 numpy/numba cap | Medium (dependency bump plus a test pass; no known code change) | 4 manifests/locks |
| DEP-2 unpinned CI plugins | Small | 2 workflows |
| DEP-3 anyio bump | Small | 2 lock files |
| DEP-4 aliases | Small (auto-fixable) | 15 sites / 11 files |
| DEP-5 root deps | Small | 2 files |
| DEP-6 orphan configs | Small | 2 files |

## 5. Dimension Coverage Notes

1. **Python stdlib/language**: 0 hits for `utcnow`/`utcfromtimestamp`, `get_event_loop*`, `pkg_resources`, `distutils`, `imp`, removed 3.13 modules (`cgi`, `pipes`, `telnetlib`, `audioop`, `aifc`, ...), `unittest` legacy aliases, `collections` ABC imports, `ssl.PROTOCOL_*`, `locale.getdefaultlocale`, `tempfile.mktemp`, `asyncio.TimeoutError`, `typing.Optional/List/Dict/Union`, `rmtree(onerror=)`, `ast.Num`, `tarfile`, `importlib.resources` legacy functions, and `sqlite3` default-adapter use (the catalog writes ISO strings). `multiprocessing` appears only in tests, with an explicit `spawn` context. `os.path` is used in 62 files, but there is no `pathlib` mandate, so it is not reported.
2. **NumPy/SciPy/audio**: 0 hits for removed NumPy aliases, `np.product`/`in1d`/`row_stack`, `numpy.core`/`lib`, `fftpack`, `scipy.signal.hann`-style window names (all use `scipy.signal.windows`) and `ndarray.ptp()` (`np.ptp()` the function is fine). Every direct `librosa.load()` is guarded by `FFMPEG_FORMATS` routing: `mastering_fingerprint.py` branches on it, `track_audio.py` branches on it, and `windowed_loading.py::load_librosa_windows` is reached only from the non-FFmpeg branch at `track_audio.py:160-161`. No `audioread` or `standard-*` backport pins. Pillow use is minimal (`ImageOps`, `Image.Resampling.LANCZOS`).
3. **FastAPI/Pydantic/SQLAlchemy**: 0 hits for `class Config`, `.dict()`/`.parse_obj()`/`.from_orm()`, `@validator`, `schema_extra`, `orm_mode` or `on_event`. The 3 `json_schema_extra` uses are V2. Models are `DeclarativeBase` + `Mapped[]`/`mapped_column`. `Column()` appears only inside the 3 association `Table(...)` definitions, which is correct 2.0 style. There is no `session.query` or `engine.execute`. `sessionmaker(engine)` is the positional form. The 3 `default=lambda: datetime.now(timezone.utc)` are correct.
4. **React/Redux/MUI**: 0 hits for `ReactDOM.render`, `findDOMNode`, `react-dom/test-utils`, lifecycle `componentWill*`, `UNSAFE_`, `defaultProps` on components (the matches are local test constants), `React.FC`, `PropTypes`, string refs, `connect()`, `createStore`, `makeStyles`, `@mui/styles`, `Grid2`, slot-prop families (`InputProps`, `PaperProps`, `TransitionProps`, `componentsProps`, ...), `ListItem button` and barrel icon imports. `ErrorBoundary` is the only class component (legitimate). The `tsconfig` uses `moduleResolution: bundler` with no `baseUrl`.
5. **Node/npm/build**: 0 hits for `url.parse`, `fs.exists`, `new Buffer`, `querystring` and bare built-in `require`. The frontend and root lockfiles carry no `deprecated:` entries. `desktop/` uses `node:` prefixes throughout. There is no legacy ESLint config. The root-package finding is DEP-5.
6. **Rust/PyO3**: `Cargo.toml` is edition 2024 with `pyo3 = 0.29` and `numpy = 0.29`. `cargo check --offline --locked` with Rust 1.96.0 gives zero warnings. There are no `allow_threads`/`with_gil`/`PyObject`/`*_bound` uses and no `#[allow(deprecated)]`. `PyDict::new(py)` is the current constructor. `Cargo.lock` is tracked. There is no `.cargo/config.toml` ABI3 flag anywhere. Only one `#[pyfunction]` exists, as documented.
7. **Internal**: There are no `@deprecated` decorators and no first-party `DeprecationWarning` emissions. The only production "deprecated" mentions are historical comments (`playlist_query_mixin.py`) and the kept `BufferScheduler` fallback. The `AdaptiveMode` "Legacy path" docstring is accurate (it is the adaptive component of the hybrid and reference modes). There are no `TODO(#NNNN)` markers citing closed issues in `auralis/`, `auralis-web/` or `vendor/`.
8. **Config/CI**: All 57 `uses:` entries are 40-char SHA-pinned at `checkout` 7.0.1, `setup-python` 7.1.0 and `upload-artifact` 7.0.2. No `pnpm/action-setup` carries a `version:` input. Every Python job is on 3.14 and every Node job on 24. All guard workflows exist. The baseline gate scripts are still invoked (`check_pytest_baseline.py --strict-stale`, `pnpm run test:baseline -- --strict-stale`) and still fail on a missing report or 0 collected tests (`check_pytest_baseline.py` lines 79-86, `check-test-baseline.mjs` lines 78-79). `pytest.ini` has no `--disable-warnings`, and the `pyproject.toml` `pytest>=9.0.1` floor mirrors `minversion`. Version is 1.5.1 in `version.py`, root, desktop, frontend and `pyproject.toml`. No Dockerfile, `setup.py`, `setup.cfg` or `.eslintrc*` exists. Pre-commit revs (`black` 26.10.1, `mypy` 2.3.0) are current. The orphan configs are DEP-6; the unpinned CI plugins are DEP-2.

### Incidental observation (not a deprecation, unverified cause)
Running `tests/backend/test_metadata.py`, `tests/backend/test_dependencies.py`, `tests/backend/test_albums_api.py` and `tests/auralis/library/test_sidecar_manager.py` together made 20 tests in `test_albums_api.py` fail. The same file passes 24/24 on its own, and none of those 20 is listed in `pytest-baseline.json`. That points to cross-file state leakage in the backend test fixtures, which belongs to a test-isolation audit.
