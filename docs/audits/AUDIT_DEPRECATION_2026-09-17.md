# Deprecation Audit — 2026-09-17

**Scope**: Python (`auralis/`, `auralis-web/backend/`, `tests/`, `scripts/`), frontend (`auralis-web/frontend/`), Electron (`desktop/`), Rust (`vendor/auralis-dsp/`), configuration and CI (`pyproject.toml`, `pytest.ini`, requirements files, `.github/`)
**HEAD**: `6a44703f` (233 commits since the 2026-09-13 deprecation audit)
**Method**: three parallel agents covered dimensions 1+2+7, 3+6+8 and 4+5. Every claim was checked against the **installed** package version (its source, `.d.ts` `@deprecated` tags, or a warning at run time), not recalled from memory. The orchestrator re-ran the key greps and re-checked the only finding. Findings were deduplicated against the last 2,000 GitHub issues and the 2026-09-13 report.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 0 |
| MEDIUM   | 0 |
| LOW      | 1 |
| **Total**| **1** |

The codebase has almost no deprecated usage left. Fixes landed since 2026-09-13 closed 9 of that audit's Python/internal findings and every Config/CI finding. The frontend is now on MUI 9 with none of the props deprecated in that version. Nothing blocks an upgrade that isn't already tracked in an open issue.

**Warning probes (run time)**
- `python -W error::DeprecationWarning -W error::PendingDeprecationWarning`, importing `auralis`, `auralis.core.hybrid_processor`, `auralis.library.database`, `auralis.player.enhanced_audio_player` and `auralis.analysis.fingerprint.fingerprint_service`: **no warnings**.
- The same probe on the backend `main` module: **no warnings**.
- `cargo check` in `vendor/auralis-dsp` (clean incremental cache): 7 warnings, all unused variables or `mut`. **None are deprecation warnings.**

**Installed versions checked**: Python 3.14.0 · numpy 2.4.6 · fastapi 0.141.1 · starlette 1.3.1 · pydantic 2.13.4 · sqlalchemy 2.0.51 · uvicorn 0.52.1 · mypy 2.3.0 · ruff 0.16.1 · React 18.3.1 · react-redux 9.2.0 · @reduxjs/toolkit 2.11.2 · @mui/material 9.0.1 · Vitest 4.1.7 · Electron 43.2.0 · electron-builder 26.15.7 · pyo3 0.23.5 · numpy-rs 0.23.0 · Rust edition 2024.

### Checked and clean, per dimension

| Dimension | Result |
|---|---|
| 1 Python stdlib | 0 hits for: `utcnow`/`utcfromtimestamp`, `get_event_loop` outside a running loop, `pkg_resources`, `distutils`, `imp`, `collections` ABCs, `unittest` aliases, `configparser` legacy methods, `setDaemon`/`isAlive`, `ssl` constants, `locale.getdefaultlocale`, and the Python 3.14 removals and deprecations (`asyncio` policy APIs, `asyncio.iscoroutinefunction`, `codecs.open`, `ast.Num`/`Str`, `pty.master_open`, `tarfile` without a filter, `glob0`/`glob1`, `logging.warn`, `unittest.makeSuite`, `inspect.getargspec`, `sre_*`). The one `asyncio.get_event_loop()` call in a new test runs inside a running loop, so it does not warn. |
| 2 NumPy/SciPy/audio | 0 hits for: removed NumPy aliases (`np.float`, `np.NaN`, `np.float_`, …), `np.trapz`, `np.product`/`in1d`/`row_stack`, `numpy.core` imports, `scipy.fftpack`/`misc`/`simps`, deprecated `scipy.signal` window import paths, and deprecated librosa/soundfile/resampy parameters. |
| 3 FastAPI/Pydantic/SQLAlchemy | 0 Pydantic v1 patterns and 0 `on_event` (lifespan is used). 0 legacy SQLAlchemy patterns (`session.query`, `declarative_base`, `engine.execute`, `backref`, list-form `select`) in production code or tests. Starlette 1.3.1 deprecates `HTTP_422_UNPROCESSABLE_ENTITY` in favour of `HTTP_422_UNPROCESSABLE_CONTENT`, and the codebase does not use the old name. |
| 4 React/Redux/MUI | No `ReactDOM.render`, `findDOMNode`, string refs, `UNSAFE_` lifecycles, legacy context, PropTypes, `defaultProps`, `connect()` or legacy RTK syntax. MUI 9.0.1's `.d.ts` files mark 5 symbols `@deprecated`, and none of them are used. The old `*Props` slot props were removed outright in v9, and none remain in `src/`. |
| 5 Node/npm/build | Every Node built-in is imported with the `node:` prefix. No `fs.exists`/`url.parse`/`querystring`/`new Buffer`. `engines` and `packageManager` agree across all 3 `package.json` files. No ESLint config exists. None of the 35 direct dependencies is deprecated on npm. The electron-builder config uses none of the 4 keys that version deprecates. `desktop/main.js` uses `setWindowOpenHandler` and `will-navigate`, with `contextIsolation` and `sandbox` enabled. |
| 6 Rust/PyO3 | `Cargo.lock` is tracked, ndarray is resolved to a single version (0.16.1), and the crate is on edition 2024 (#5443). None of the roughly 24 `#[deprecated]` numpy-rs 0.23 symbols are used. |
| 7 Internal | No internal `DeprecationWarning` emissions. The requirements files and `pyproject.toml` match the installed environment exactly. One back-compatibility alias remains (below). |
| 8 Config/CI | All 9 workflows pin each action to a commit SHA on its current major version (`checkout` v7.0.1, `setup-python` v7.0.0, `setup-node` v7.0.0, `pnpm/action-setup` v6.1.0 with **no** `version:`, `upload-artifact`/`download-artifact` v7/v8). Python 3.14 and Node 24 are pinned everywhere. The baseline gates still fail when the report is missing or zero tests were collected. The guard workflows are wired, and there is no Dockerfile. `pytest.ini` `minversion` (9.0.1) matches the `pyproject.toml` floor. Version 1.5.1 matches across `version.py`, `pyproject.toml` and both `package.json` files. The repo has no ruff config, so there are no deprecated ruff keys. |

---

## Findings

### LOW

### DEP-INT-01: `QueueController.clear()` is a "backward compatibility alias" that the backend still calls in production
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/player/queue_controller.py:126-128`
- **Status**: NEW. It follows the same pattern as the aliases removed in #4973, #4645, #4621 and #4335.
- **Deprecated API**: `QueueController.clear()`, whose docstring reads "Clear all tracks from queue (backward compatibility alias)"
- **Deprecated Since**: internal, never given a date
- **Removal Version**: n/a
- **Replacement**: `QueueController.clear_queue()`
- **Affected Files**: 1 production caller and 5 test files
  - Production: `auralis-web/backend/services/queue_edit_mixin.py:203` (`queue_manager.clear()`, where `queue_manager = self.audio_player.queue`, a `QueueController`)
  - Tests: `tests/auralis/player/test_enhanced_player.py:116,124,133,531`, `tests/auralis/player/test_queue_controller.py:427`, `tests/auralis/player/test_queue_change_invalidates_prebuffer_5508.py:46`, `tests/stress/test_processing_stress.py:128`, `tests/stress/test_large_library.py:502`. Lines 116–133 of `test_enhanced_player.py` may call `QueueManager.clear()` rather than the controller alias; check them when migrating.
- **Evidence**:
  ```python
  # auralis/player/queue_controller.py
  def clear(self) -> None:
      """Clear all tracks from queue (backward compatibility alias)"""
      self.clear_queue()
  ```
  The dimension agent reported zero production callers. The orchestrator found the backend call above, so the alias is still in use and cannot simply be deleted.
- **Migration Path**:
  1. Change `queue_edit_mixin.py:203` to `queue_manager.clear_queue()`.
  2. Point each test call on a `QueueController` at `clear_queue()`. Leave calls on a raw `QueueManager` alone, because `QueueManager.clear()` is its own method and not an alias.
  3. Delete `QueueController.clear()` and drop the `"clear"` row from the #5508 mutation table.
  4. Confirm with `grep -rn "queue\.clear()\|queue_controller\.clear()\|ctrl\.clear()" auralis auralis-web tests`.
- **Risk**: Two names for one operation. Future queue-controller changes (for example the #5508 change listener) have to keep both in sync. Nothing breaks today.
- **Effort**: Small (fewer than 10 sites)

---

## Skipped as Existing (open, re-verified as still accurate)

| Issue | Topic |
|---|---|
| #5405 | Tests still assert that retired presets are accepted |
| #5410 | `asyncio.TimeoutError` alias in 11 backend sites |
| #5411 | `from __future__ import annotations` in 59 modules |
| #5412 | `mimetypes.guess_type()` called with a filesystem path |
| #5413 | `tempfile.mktemp()` in 2 test files |
| #5414 | Removed-stdlib backports pulled in through librosa's audioread backend |
| #5416 | `np.hanning()` in the psychoacoustic EQ |
| #5429 | Deprecated transitive npm packages (the lockfiles have not changed since 2026-09-13) |
| #5430 | Unused `vite-tsconfig-paths` / deprecated `tsconfck` |
| #5431 | Vitest `benchmark.outputFile` |
| #5433 | Vite top-level `esbuild` / `build.rollupOptions` |
| #5435 | tsconfig `baseUrl` |
| #5436 | Global `JSX` namespace in 2 files |
| #5485 | pyo3/numpy 0.29 bump |

**Closed issues re-verified as still fixed** (no regressions): #4333, #4336, #5407, #5408, #5415, #5419, #5420, #5422, #5423, #5425, #5426, #5427, #5437, #5438, #5439, #5440, #5441, #5443, #5452.

---

## Dependency Upgrade Roadmap

| Package | Installed → available | Status and blockers |
|---|---|---|
| pyo3 / numpy-rs | 0.23 → 0.29 | Tracked in #5485, which reports that the NumPy ABI runtime failure no longer reproduces. Do the bump there, and verify at run time on Python 3.14 with NumPy 2.4. |
| librosa | pinned → 1.0 | Tracked in #5414. 1.0 drops the audioread backend. |
| React | 18.3.1 → 19 | Needs #5436 (global `JSX` namespace) first. Otherwise no deprecated React API is used. |
| TypeScript | 5.9 → 7.0 | Needs #5435 (`baseUrl`) first. |
| Vite / Vitest | 7 → 8 / 4.1.7 → 5 | Needs #5433 and #5431 first. |
| MUI | 9.0.1 → 9.4.0 | Minor update. No deprecated usage. |
| @reduxjs/toolkit, @tanstack/react-query | 2.11.2 → 2.12.0, 5.90.12 → 5.103.1 | Minor updates. No blockers. |
| Electron | 43.2.0 → 44 | No deprecated Electron API is in use. |
| numpy (Python) | 2.4.6 | Kept below 2.5 to stay within numba's supported range (documented ceiling). |

The frontend and desktop version gaps were checked with `pnpm outdated` (network), and no packages were changed. Latest PyPI versions were not checked: the project venv has no `pip` module, only `uv`.

## Migration Effort Estimate

| Finding | Effort |
|---|---|
| DEP-INT-01 | Small: 1 production line, about 6 test lines, 1 alias deleted |

## Maintenance Note for the Audit Skill

`.claude/commands/audit-deprecation.md` (Dimension 6) still says the crate pins "edition 2021" and asks for an "edition 2021 → 2024 migration" check. `vendor/auralis-dsp/Cargo.toml` has been on `edition = "2024"` (with `rust-version = "1.85"`) since #5443. Update that line the next time the skill is edited. `_audit-validate.sh` cannot catch this drift, because it is not a path reference.
