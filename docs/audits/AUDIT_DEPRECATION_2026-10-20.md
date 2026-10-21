# Deprecation Audit — 2026-10-20

**Scope**: Python (`auralis/`, `auralis-web/backend/`, `tests/`, `scripts/`), frontend (`auralis-web/frontend/`), Electron (`desktop/`), Rust (`vendor/auralis-dsp/`), configuration and CI (`pyproject.toml`, `pytest.ini`, requirements files, `.github/`)
**HEAD**: `64d59ea2` (152 commits since the 2026-09-17 deprecation audit)
**Method**: one orchestrator pass, no sub-agents. Every claim was checked against the **pinned** dependency set, not the local `.venv`. The repo `.venv` is stale (numpy 2.3.5, fastapi 0.122.0, librosa 0.11.0), so a scratch venv was built from `requirements.txt` (numpy 2.4.6, scipy 1.18.0, fastapi 0.141.1, starlette 1.3.1, pydantic 2.13.4, SQLAlchemy 2.0.51, librosa 1.0.0) and all run-time probes used it. Findings were deduplicated against the last 300 GitHub issues (open and closed), the 2026-09-13 and 2026-09-17 deprecation reports, and the 2026-09-13 tech-debt report.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 0 |
| MEDIUM   | 0 |
| LOW      | 4 |
| **Total**| **4** |

Nothing in the tree is deprecated against the pinned versions, and nothing blocks an upgrade that is not already tracked. All four findings are LOW housekeeping: one internal duplicate method pair, one vestigial pnpm override, one test-side leftover of an already-closed production fix, and one over-broad warning filter.

Every issue the 2026-09-17 report listed as "existing, open" has since been closed. All of them were re-verified against HEAD (table below). None regressed, and #5411 is closed with production fully done but its test/script scope left in place (see "Checked and intentionally not reported").

**Warning probes (run time, pinned versions)**
- `python -X dev -W error::DeprecationWarning -W error::PendingDeprecationWarning -W error::SyntaxWarning`, importing `auralis`, `auralis.core.hybrid_processor`, `auralis.library.database`, `auralis.player.enhanced_audio_player`, `auralis.analysis.fingerprint.fingerprint_service`, `auralis.io.unified_loader` and `auralis.dsp.eq.psychoacoustic_eq`: **no warnings**.
- The same probe on the backend `main` module: **no warnings**. (It logs "Rust fingerprinting module not available" because the scratch venv has no `auralis_dsp` wheel; that is not a deprecation.)
- `python -W error -m compileall` over `auralis`, `auralis-web/backend`, `scripts` and `tests`: **clean** (no `SyntaxWarning`, e.g. invalid escape sequences).
- Ten test files across dsp, io, player, library and backend (293 tests) ran with `-W default::DeprecationWarning -W default::PendingDeprecationWarning -W default::FutureWarning`: all passed, **0 warnings**. `HOME` was pointed at a scratch directory so the real library was not touched.
- `cargo check --locked --all-targets` (toolchain 1.96.0, edition 2024, pyo3 0.29.2, numpy-rs 0.29.0): 3 warnings, all unused variables (`biquad_filter.rs:175`, `fingerprint_compute.rs:431`, `py_bindings.rs:93`). **None are deprecation warnings.**
- **Forward probe**: in a second scratch venv upgraded to the newest releases (FastAPI 0.156.4, Starlette 1.9.0, Pydantic 2.14.1, SQLAlchemy **2.1.5**), the backend still imports with deprecation warnings as errors, and 121 tests pass. The one warning is Starlette's "Using `httpx` with `starlette.testclient` is deprecated; install `httpx2`". It appeared only because that venv followed `requirements.txt`, which does not carry `httpx2`. CI already installs `httpx2` (`backend-tests.yml:128`) and `pyproject.toml` lists `httpx2>=2.9`, so it is handled.

**Versions checked**: Python 3.14.0 · numpy 2.4.6 · scipy 1.18.0 · soundfile 0.14.0 · librosa 1.0.0 · fastapi 0.141.1 · starlette 1.3.1 · pydantic 2.13.4 · sqlalchemy 2.0.51 · React 18.3.1 · @types/react 18.3.27 · @mui/material 9.0.1 · @reduxjs/toolkit 2.11.2 · Vite 8.3.0 · Vitest 4.1.7 · TypeScript 5.9 · Electron 43.2.0 · electron-builder 26.15.7 · pyo3 0.29.2 · numpy-rs 0.29.0 · ndarray 0.16.1.

### Checked and clean, per dimension

| Dimension | Result |
|---|---|
| 1 Python stdlib | 0 hits in production for: `utcnow`/`utcfromtimestamp`, `get_event_loop`, `pkg_resources`, `distutils`, `imp`, `collections` ABC imports, `unittest` aliases, `configparser` legacy methods, `setDaemon`/`isAlive`/`currentThread`, `ssl` constants, `locale.getdefaultlocale`, `asyncio` policy APIs and `asyncio.iscoroutinefunction` (the `inspect` form is current), `asyncio.TimeoutError`, `shutil.rmtree(onerror=)`, `typing.ByteString`, `pkgutil.find_loader`, `sqlite3` default adapters, `ast.Num`/`Str`, `tarfile` without a filter, `logging.warn`, `inspect.getargspec`, `importlib.resources` legacy functions, `codecs.open`. The `datetime`, `Optional`/`List`/`Dict` legacy-typing and `typing` ABC-alias searches return 0 as well (the 7 remaining `from typing import Callable` hits are the still-valid `typing.Callable` form). The only `get_event_loop()` calls (`test_jump_to_track_broadcast_outside_lock_5324.py`) run inside a running loop, so they do not warn. Test-side `asyncio.TimeoutError` is **DEP-PY-01**. |
| 2 NumPy/SciPy/audio | 0 hits for removed NumPy aliases (`np.float`, `np.bool`, `np.NaN`, `np.float_`, …), `np.product`/`in1d`/`row_stack`/`trapz`, `numpy.core` imports, `scipy.fftpack`/`misc`/`simps`, and `scipy.signal.<window>` top-level window functions. All 7 window imports use `scipy.signal.windows`, and `np.hanning` is gone from production (#5416). `np.ptp` (function form) is still current. Every `librosa.load()` in production is either behind an `FFMPEG_FORMATS` check that routes M4A/AAC/WMA through `load_with_ffmpeg` (`mastering_fingerprint.py:109`, `windowed_compute.py:137`) or in the non-FFmpeg `else` branch. No `audioread` or backport pin (`standard-aifc`, `audioop-lts`, …) is reintroduced. |
| 3 FastAPI/Pydantic/SQLAlchemy | 0 Pydantic v1 patterns (`class Config`, `.dict()`, `@validator`, `orm_mode`, `schema_extra`, `parse_obj`, …): the three `json_schema_extra` hits are the v2 spelling. 0 `on_event` (lifespan in use). 0 legacy SQLAlchemy: no `session.query`, `declarative_base`, `engine.execute`, `backref`, list-form `select`, or `Column()` (159 `mapped_column`, 181 `Mapped[]`, `DeclarativeBase` in `models/base.py`; 0 un-annotated `relationship()`). The `sessionmaker(bind=engine)` calls in `tests/` are the documented form. The raw `cursor.execute("PRAGMA …")` calls are on DB-API cursors, not SQLAlchemy sessions. Starlette's `HTTP_422_UNPROCESSABLE_ENTITY` rename is not used. |
| 4 React/Redux/MUI | No `ReactDOM.render`, `findDOMNode`, string refs, `UNSAFE_`/`componentWill*`, legacy context, `PropTypes`, `defaultProps`, `connect()`, `createStore`, `makeStyles`/`@mui/styles`, or `React.FC`. The global `JSX` namespace is gone (#5436 fixed in `a6d26321`; `Box.tsx` and `ErrorBoundary.test.tsx` now `import type { JSX } from 'react'`). `@tanstack/react-query` v5 option names only. |
| 5 Node/npm/build | No unprefixed Node built-in imports, `fs.exists`, `url.parse`, `querystring`, `new Buffer`, or `util.is*` in `desktop/`, `scripts/` or the frontend config files. `desktop/main.js` runs with `nodeIntegration:false`, `contextIsolation`, `sandbox`, `webSecurity`, and uses `setWindowOpenHandler`/`will-navigate` rather than the removed `new-window`. `engines` and `packageManager` agree. No ESLint config exists. The Vite config is on Vite 8 (`vite.config.mts`, Rolldown options); `baseUrl` is gone from `tsconfig.json`; `vite-tsconfig-paths` is removed; Vitest uses `outputJson`. No `deprecated:` entry in the frontend lockfile. The 5 in `desktop/pnpm-lock.yaml` are all transitive and tracked in closed #5429, which records them as blocked upstream (`lodash.isequal` via `electron-updater` at latest; `boolean`, `glob@7`, `inflight`, `rimraf@2` build-time only). |
| 6 Rust/PyO3 | Edition 2024, `rust-version = "1.85"`, pyo3 0.29.2, numpy-rs 0.29.0, `Cargo.lock` tracked, ndarray resolved once (0.16.1). 0 hits for `allow_threads`, `with_gil`, `PyObject`, `into_py`, `ToPyObject`, `to_object`, `*_bound`, `GILPool`; `PyDict::new(py)` is the current constructor. `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` appears only in `build-release.yml` comments explaining why it is gone. |
| 7 Internal | No `DeprecationWarning` emissions or `@deprecated` decorators. Remaining "backward compatibility" markers were each traced to their callers: `ChunkedAudioProcessor.duration` is read by 8 production sites (`stream_seek.py`, `stream_enhanced.py`, `stream_normal.py`) and the `chunk_rms_history`/`chunk_gain_history` mirrors are read in `chunk_streaming.py:127`, so both are live and not reported. The re-export blocks in `advanced_dynamics.py`, `unified_loader.py`, `fingerprint_repository.py` and `models/core.py` are import-surface shims, not deprecations, and the first three were already evaluated in earlier reports. One real duplicate method pair remains (**DEP-INT-01**). |
| 8 Config/CI | All 9 workflows pin every action to a commit SHA, with `checkout` v7.0.1, `setup-python` v7.0.0, `pnpm/action-setup` v6.1.0 (no `version:` input), `download-artifact` v8.0.1 and `action-gh-release` v3.0.3 at their latest majors (`upload-artifact` v7.0.1, `setup-node` v7.0.0 and `install-action` v2.87.13 trail by a patch or minor only). Python 3.14 and Node 24 everywhere. `check_pytest_baseline.py` is invoked with `--strict-stale` and exits non-zero on a missing report or 0 collected tests; the frontend job runs `pnpm run test:baseline -- --strict-stale`. All guard workflows are wired (`action-pin-guard`, `lockfile-guard`, `requirements-pin-guard` → `check_lock_matches_manifest.py` + `check_pyproject_deps.py`, `rust-audit`, `path-references` → `_audit-validate.sh` + `check_optimization_importers.py`). No Dockerfile, `setup.py` or `setup.cfg`. Version 1.5.1 matches across `version.py`, `pyproject.toml`, the root, frontend and desktop `package.json`. `pyproject.toml` uses the PEP 639 SPDX `license` (#5441). `pytest.ini` `minversion` 9.0.1 matches the `pyproject.toml` floor. The warning filter is **DEP-CFG-01**. |

### Closed issues re-verified at HEAD (no regressions)

| Issue | Was | Verified |
|---|---|---|
| #5405 | Tests accept retired presets | Fixed in `18f6a6b1` and `40c3c13c`. |
| #5410 | `asyncio.TimeoutError` in 11 production sites | 0 hits in `auralis/` and `auralis-web/backend/`. Test-side siblings remain (DEP-PY-01). |
| #5411 | `from __future__ import annotations` | 0 in `auralis/` and `auralis-web/backend/`. See "intentionally not reported". |
| #5412 | `mimetypes.guess_type()` on a path | `guess_type` has 0 hits in production. |
| #5413 | `tempfile.mktemp()` | 0 `tempfile.mktemp`. The 3 remaining `mktemp(` hits are `tmp_path_factory.mktemp`, which is the pytest API. |
| #5414 | audioread backports via librosa | Gated, see Dimension 2. |
| #5416 | `np.hanning` in the psychoacoustic EQ | 0 hits. |
| #5429 | Deprecated transitive npm packages | Frontend: 0. Desktop: 5, blocked upstream. |
| #5430 | `vite-tsconfig-paths` / `tsconfck` | 0 hits in the lockfile. |
| #5431 | Vitest `benchmark.outputFile` | `outputFile` at `vitest.config.ts:66` is the `coverage`/reporter key, not `benchmark`; `4914fc30` switched benchmark to `outputJson`. |
| #5433 | Vite top-level `esbuild` / `rollupOptions` | On Vite 8.3.0, `rolldownOptions` in use. |
| #5435 | tsconfig `baseUrl` | Removed. |
| #5436 | Global `JSX` namespace | Fixed. |
| #5485 | pyo3/numpy 0.29 | Landed, `cargo check` clean. |
| #5513 | `QueueController.clear()` alias | Deleted in `e5e2cd05`, `hasattr(QueueController, 'clear')` is False. Its sibling is DEP-INT-01. |

---

## Findings

### LOW

### DEP-INT-01: `QueueController` carries two names for one operation, and a "backward compatibility" docstring on a live method
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/player/queue_controller.py:362-368` (`get_track_count` / `get_queue_size`), `auralis/player/queue_controller.py:427-428` (`set_queue`)
- **Status**: NEW. Same pattern as #5513 (`clear()` alias, closed), #4973, #4645, #4621 and #4335.
- **Deprecated API**: `QueueController.get_track_count()`, which is a verbatim duplicate of `get_queue_size()`. Separately, `QueueController.set_queue()` is documented "for backward compatibility" but is the live path for the backend `set_queue` service.
- **Deprecated Since**: internal, never dated
- **Removal Version**: n/a
- **Replacement**: Keep `get_queue_size()`, which matches `QueueManager.get_queue_size()` underneath. Delete `get_track_count()`. Reword the `set_queue` docstring.
- **Affected Files**: 1 production file, 2 test files
  - Production callers of `get_queue_size()`: `auralis-web/backend/services/queue_order_mixin.py:47,229`, `auralis-web/backend/services/queue_edit_mixin.py:120`.
  - Production callers of `get_track_count()`: **none**.
  - Test callers of `get_track_count()`: `tests/auralis/player/test_queue_controller.py` (19 mentions) and `tests/auralis/player/conftest.py` (1).
  - `set_queue` production caller: `auralis-web/backend/services/queue_set_mixin.py:125` (`asyncio.to_thread(self.audio_player.queue.set_queue, …)`), plus 35 test call sites. It is not dead code.
- **Evidence**:
  ```python
  # auralis/player/queue_controller.py
  def get_track_count(self) -> int:
      """Get number of tracks in queue"""
      return self.queue.get_queue_size()

  def get_queue_size(self) -> int:
      """Get queue size (alias for get_track_count)"""   # backwards: this is the one production uses
      return self.queue.get_queue_size()
  ```
  The docstring names the unused method as the original and the used one as the alias.
- **Migration Path**:
  1. Point the `get_track_count()` uses in `test_queue_controller.py` and `conftest.py` at `get_queue_size()`.
  2. Delete `QueueController.get_track_count()`.
  3. Change the `set_queue` docstring to describe what it does ("Replace the queue with `track_list`, atomically") and drop "for backward compatibility".
  4. Confirm with `grep -rn "get_track_count" auralis auralis-web tests`.
- **Risk**: Nothing breaks today. The cost is the same one #5513 named: two names to keep in sync, with the docstring pointing the wrong way. The #5508 mutation table carried a redundant row for the `clear()` alias for the same reason (removed in #5513).
- **Effort**: Small (about 20 test lines, 1 method deleted, 1 docstring)

### DEP-NODE-01: pnpm `overrides: rollup` pins a package the frontend no longer installs
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/pnpm-workspace.yaml:5-8`; the matching `overrides:` header at `auralis-web/frontend/pnpm-lock.yaml:8`
- **Status**: NEW. A leftover from #5407 (moved the override) combined with #5433 (moved Vite to 8, which bundles Rolldown instead of Rollup).
- **Deprecated API**: `overrides: { rollup: '>=4.59.0' }`, a security pin for a package that is no longer in the dependency graph.
- **Deprecated Since**: Vite 8 replaced Rollup with Rolldown. This repo's frontend moved in `bacd9063` (2026-09-17).
- **Removal Version**: n/a
- **Replacement**: Delete the `overrides:` block, regenerate the lockfile, and keep a one-line note that the advisory is moot under Vite 8.
- **Affected Files**: 2 (`pnpm-workspace.yaml`, `pnpm-lock.yaml`)
- **Evidence**:
  ```
  $ grep -n rollup auralis-web/frontend/pnpm-lock.yaml
  8:  rollup: '>=4.59.0'                # the overrides header, and nothing else
  $ grep -n 'rolldown@' auralis-web/frontend/pnpm-lock.yaml
  1435:  rolldown@1.2.9:
  2949:  rolldown@1.2.9:
  ```
  The lockfile resolves no `rollup@…` package, so the pin applies to nothing. `desktop/pnpm-lock.yaml` has no rollup entry either.
- **Migration Path**:
  1. Remove the `overrides:` block (and its comment) from `pnpm-workspace.yaml`.
  2. Run `pnpm install --lockfile-only` in `auralis-web/frontend` and confirm only the `overrides:` header changes.
  3. Check `lockfile-guard.yml` still passes.
  4. If you would rather keep a guard against a future transitive Rollup, say so in the comment instead.
- **Risk**: None functionally. A stale override reads as a live security control and makes the next person reason about a package that is not installed.
- **Effort**: Small (2 files)

### DEP-PY-01: `asyncio.TimeoutError` still used in 5 test sites after the production sweep
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `tests/backend/test_websocket_flow_control.py:65`, `tests/backend/test_scan_start_and_cancel_frames.py:275`, `tests/backend/test_processing_engine.py:586`, `tests/backend/test_concurrent_streaming.py:64`, `tests/concurrency/test_async_operations.py:172`
- **Status**: NEW. Test-side sibling of #5410 (closed after its 11 production sites were fixed). No regression.
- **Deprecated API**: `asyncio.TimeoutError`, which has been an alias of the builtin `TimeoutError` since Python 3.11
- **Deprecated Since**: 3.11 (alias only; it emits no warning on 3.14)
- **Removal Version**: none announced
- **Replacement**: builtin `TimeoutError`
- **Affected Files**: 5 test files, 5 call sites
- **Evidence**:
  ```python
  with pytest.raises(asyncio.TimeoutError):
      await asyncio.wait_for(engine._concurrency_semaphore.acquire(), timeout=0.05)
  ```
  The backend has 33 uses of the builtin form in production and tests combined, so this is the minority spelling.
- **Migration Path**: Replace with `TimeoutError` at the 5 sites. `asyncio.TimeoutError is TimeoutError` on 3.11+, so behaviour is identical. Drop the `asyncio` import if it becomes unused (it will not in these files).
- **Risk**: None. Style drift against the production code, and the first thing a linter's `UP041` rule will flag.
- **Effort**: Small (5 lines)

### DEP-CFG-01: `pytest.ini` blanket-ignores `PendingDeprecationWarning`
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pytest.ini:104-111` (`filterwarnings`, line 107)
- **Status**: NEW
- **Deprecated API**: n/a — a warning filter that hides the earliest deprecation signal
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: Remove `ignore::PendingDeprecationWarning`, or narrow it to the specific third-party module that needs it.
- **Affected Files**: 1 (`pytest.ini`)
- **Evidence**:
  ```ini
  filterwarnings =
      default::DeprecationWarning
      ignore::DeprecationWarning:soundfile
      ignore::PendingDeprecationWarning        # all modules, first-party included
  ```
  The line dates from `9333e1cc` (2025-09-13). #4559 later removed `--disable-warnings` precisely so first-party deprecation signals would be visible, and the comment under the block says first-party warnings are "deliberately NOT filtered". `PendingDeprecationWarning` is the one category that comment does not hold for.
  Enabling it did not surface anything today: 10 test files (293 tests) ran with `-W default::PendingDeprecationWarning` and produced 0 warnings. The filter currently hides nothing, which is also why removing it is cheap.
- **Migration Path**:
  1. Delete the line.
  2. Run one scoped pass per area (dsp, io, player, library, backend) and check the warnings summary.
  3. If a third-party module is noisy, add `ignore::PendingDeprecationWarning:<module>` for that module only.
- **Risk**: Pending deprecations in NumPy, SQLAlchemy or Starlette reach the project only when they become real `DeprecationWarning`s, one release later. Nothing breaks now.
- **Effort**: Small (1 line, plus one verification pass)

---

## Skipped as Existing / Not Reported

No open deprecation issue remains: everything the 2026-09-17 report carried as open is now closed (table above).

**Checked and intentionally not reported**
- `from __future__ import annotations` in 73 test files and 5 `scripts/*.py` files. #5411 was closed with its production scope complete and the test/script remainder explicitly left as incremental. PEP 749 does not deprecate the import before Python 3.13 reaches end of life (October 2029), and the import is not harmful on 3.14. Reporting it again would re-litigate a closed decision.
- The 5 transitive `deprecated:` entries in `desktop/pnpm-lock.yaml`: tracked in #5429, blocked upstream.
- `inspect.iscoroutinefunction` (7 uses). It is the non-deprecated form; `asyncio.iscoroutinefunction` is the one deprecated in 3.14.
- `ChunkedAudioProcessor.duration` and the `chunk_rms_history` / `chunk_gain_history` mirrors are described as legacy or compatibility in comments, but production reads both (Dimension 7 above).

---

## Dependency Upgrade Roadmap

| Package | Pinned → latest | Status and blockers |
|---|---|---|
| SQLAlchemy | 2.0.51 → 2.1.5 | No blocker found. No legacy 1.x patterns in code; the import probe and 121 tests passed on 2.1.5 with deprecation warnings enabled. |
| FastAPI / Starlette / Pydantic | 0.141.1 / 1.3.1 / 2.13.4 → 0.156.4 / 1.9.0 / 2.14.1 | No blocker found; same probe, clean. Starlette 1.9's `TestClient` wants `httpx2`, which CI and `pyproject.toml` already carry. Add `httpx2` to `requirements.txt` if local runs should match CI. |
| uvicorn | 0.52.1 → 0.54.0 | Minor. No blockers. |
| numpy | 2.4.6 → 2.5.4 | Held by the documented `<2.5` ceiling (numba/librosa/resampy). Revisit when numba supports 2.5. |
| scipy | 1.18.0 → 1.18.1 | Patch. |
| pillow | 12.3.0 → 13.0.0 | Major. Not checked for API changes; nothing in this audit depends on it. |
| React / ReactDOM / @types | 18.3.1 → 19.3.1 | No deprecated React API is in use and the global `JSX` namespace is gone, so the earlier #5436 blocker is cleared. A real 19 migration still needs a check of `react-infinite-scroll-component` 6 → 7 and the MUI/`@hello-pangea/dnd` peer ranges. |
| MUI | 9.0.1 → 9.5.0 | Minor. |
| @reduxjs/toolkit / react-redux | 2.11.2 → 2.13.0 / 9.2.0 → 9.3.0 | Minor. |
| @tanstack/react-query / react-virtual | 5.90.12 → 5.104.5 / 3.13.13 → 3.14.21 | Minor. |
| Vitest / @vitest/* | 4.1.7 → 5.0.5 | Major. No deprecated Vitest config in use; verify the `test:ci` baseline after bumping. |
| jsdom | wanted 30.1.0 | The local `node_modules` still holds 27.3.0 while the lockfile wants 30.1.0. Run `pnpm install`; not a repo defect. |
| msw / happy-dom / @testing-library/jest-dom | 2.12.4 / 20.8.9 / 6.9.1 → 3.0.3 / 21.0.4 / 7.0.1 | Majors, test-only. |
| Electron | 43.2.0 → 44.9.2 | Electron supports the latest three majors, so 43 is still supported. No deprecated Electron API in use. |
| pyo3 / numpy-rs | 0.29.2 / 0.29.0 | Current. |
| Local `.venv` | numpy 2.3.5, fastapi 0.122.0, librosa 0.11.0 | Behind `requirements.txt`. Rebuild with `uv venv --python-preference only-managed && uv pip install -r requirements.txt` before trusting any local probe. |

## Migration Effort Estimate

| Finding | Effort |
|---|---|
| DEP-INT-01 | Small: 1 method deleted, about 20 test lines, 1 docstring |
| DEP-NODE-01 | Small: 2 files |
| DEP-PY-01 | Small: 5 lines |
| DEP-CFG-01 | Small: 1 line plus a verification pass |

Total: four Small items, roughly an hour in one commit each.

## Maintenance Note for the Audit Skill

`.claude/commands/audit-deprecation.md` now states the Rust pins correctly (edition 2024, pyo3/numpy 0.29), so the 2026-09-17 maintenance note is resolved. One remaining gap: Dimension 8 should tell the auditor that the repo `.venv` can lag `requirements.txt` and to build a scratch venv for run-time probes. This audit found the local venv three minor versions behind on numpy, FastAPI and librosa.
