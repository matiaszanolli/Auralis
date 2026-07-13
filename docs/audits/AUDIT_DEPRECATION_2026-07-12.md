# Deprecation Audit — Auralis

- **Date**: 2026-07-12
- **Scope**: Full codebase — Python (`auralis/`, `auralis-web/backend/`, `tests/`), TypeScript/React (`auralis-web/frontend/`), Rust/PyO3 (`vendor/auralis-dsp/`), Electron (`desktop/`), and all config/CI (`pyproject.toml`, `pytest.ini`, `.github/workflows/`).
- **Method**: Fresh grep-and-verify sweep across 8 dimensions, each candidate confirmed by reading the exact source lines. Runtime targets: Python 3.14+, NumPy 2.3.5, SciPy 1.16.3, SQLAlchemy 2.0.44, Pydantic 2.12.4, FastAPI 0.122.0, React 18.2, MUI 9.0.1, Redux Toolkit 2.11, Vite 7.3, Vitest 4.1, Electron 39.8, PyO3 0.23 (Rust edition 2021). librosa 0.11.0 is a live dependency.
- **Dedup baseline**: `gh issue list` (142 open issues) snapshotted to `/tmp/audit/issues.json`.

## Executive Summary

**The Auralis codebase is exceptionally well-modernized. No upgrade blockers exist.** All findings are **LOW** severity — dead backward-compat code, test-only legacy idioms, and loose dev-tool version floors. There is nothing that emits a runtime error, nothing that blocks a dependency upgrade, and nothing in production hot paths.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 0 |
| MEDIUM   | 0 |
| LOW      | 8 |
| **Total**| **8** |

All 8 findings are **NEW**. Five pre-existing deprecation issues were confirmed still-open and deduped (not re-reported): **#4314, #4313, #4307, #3770, #3720**.

### Key clean results (explicit negatives)

- **Python stdlib**: 0 `datetime.utcnow()`, 0 `pkg_resources`, 0 `distutils`, 0 `imp`, 0 legacy `unittest` asserts, 0 `collections`-ABC misimports, 0 `ssl.PROTOCOL_TLS`, 0 `locale.getdefaultlocale`, 0 `setDaemon`. Typing is well-migrated (0 `Optional[`, 912 `| None`).
- **NumPy 2.x / SciPy / audio**: 0 removed NumPy aliases (`np.bool/int/float/...`, `np.product`, `np.trapz`, `np.NaN`, `np.float_`), 0 `scipy.fftpack`, 0 deprecated librosa/soundfile calls. All APIs current.
- **Pydantic V2 / FastAPI / SQLAlchemy 2.0**: production code is fully on modern idioms — `model_config = ConfigDict(...)`, `@field_validator`, `lifespan` (no `@app.on_event`), `DeclarativeBase` + `Mapped[]`/`mapped_column`, `select()` + `session.execute()` (zero `session.query()` in production).
- **React 18 / Redux / MUI 9**: `createRoot()` entry, 0 legacy lifecycles, 0 `findDOMNode`, 0 `connect()` HOC, RTK `configureStore`, MUI Grid v2 (`size=`), 0 `@mui/styles`/`makeStyles`, react-query v5 idioms (`gcTime`, `initialPageParam`). 0 findings.
- **Node / Vite 7 / Vitest 4 / Electron 39**: secure `contextBridge` preload, no deprecated Node APIs, current Vite/Vitest config keys. 0 findings.
- **Rust / PyO3 0.23**: fully migrated to the Bound API (`&Bound<'_, PyModule>`, `wrap_pyfunction!`, `into_pyarray(py).unbind()`). No gil-refs, no `acquire_gil`/`to_object`/`IntoPy`, no edition-2024 std blockers. 0 findings.
- **GitHub Actions**: checkout@v4, setup-python@v5, setup-node@v4, upload-artifact@v4, download-artifact@v4, action-gh-release@v2 — all current, no deprecated v3 artifact actions.

### Recommended order (all LOW, opportunistic)

1. Delete dead backward-compat code (INT-2, INT-3) — zero-risk removals.
2. Repoint the 2 live callers off the `realtime_processor` shim, then delete it (INT-1).
3. Tighten dev-tool floors in `pyproject.toml` (CI-1) and drop the unused `edge_cases` marker (CI-2).
4. Mechanically rewrite test-suite `session.query()` (SQL-1) and `event_loop` fixtures (PY-1) when those files are next touched.

---

## Findings

_All findings are LOW severity._

### PY-1: `asyncio.get_event_loop_policy()` / custom `event_loop` fixtures in tests
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `tests/backend/conftest.py:25`, `tests/integration/test_phase4_player_workflow.py:141` (2 files)
- **Status**: NEW
- **Deprecated API**: `asyncio.get_event_loop_policy()` + custom pytest-asyncio `event_loop` fixture
- **Deprecated Since**: Python 3.14 (event-loop-policy system); `event_loop` fixture deprecated by pytest-asyncio
- **Removal Version**: Python 3.16 (policy APIs). Emits `DeprecationWarning` on the 3.14 target today.
- **Replacement**: Rely on pytest-asyncio's managed loop (`asyncio_mode = "auto"` is already set in `pytest.ini`); if an explicit loop is ever required use `asyncio.new_event_loop()` or `asyncio.Runner` (no policy).
- **Affected Files**: 2 — `tests/backend/conftest.py`, `tests/integration/test_phase4_player_workflow.py`
- **Evidence**:
  ```python
  policy = asyncio.get_event_loop_policy()
  loop = policy.new_event_loop()
  ```
- **Migration Path**: Remove the custom `event_loop` fixtures; the auto mode already supplies a loop. Delete the policy calls.
- **Risk**: Test-only. `DeprecationWarning` today; fixtures break when the policy system is removed in Python 3.16. No production impact.

### SQL-1: Legacy `Session.query()` Query API across the test suite
- **Severity**: LOW
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: `tests/test_migrations.py:56` (+ 12 more files, ~47 call sites)
- **Status**: NEW
- **Deprecated API**: `Session.query(Model)` / `Query.filter()` / `.filter_by()` / `.first()` / `.all()` / `.count()` — the 1.x Query API, designated "legacy" in SQLAlchemy 2.0
- **Deprecated Since**: SQLAlchemy 2.0 (2023) — classified legacy; superseded by `select()` + `Session.execute()`
- **Removal Version**: Not scheduled for removal in the 2.x line; still fully functional, no runtime warning by default
- **Replacement**: `session.execute(select(Model).where(...)).scalars().first()/.all()`; counts via `session.scalar(select(func.count()).select_from(Model))`
- **Affected Files**: 13 test files — `tests/test_migrations.py`, `tests/concurrency/test_thread_safety.py`, `tests/auralis/core/test_core.py`, `tests/integration/test_queue_history.py`, `tests/regression/test_data_migration.py`, `tests/security/test_sql_injection.py`, `tests/edge_cases/test_concurrent_operations.py`, `tests/boundaries/test_library_operations_boundaries.py`, `tests/stress/test_edge_cases.py`, `tests/stress/test_large_library.py`, `tests/performance/test_library_operations_performance.py`, `tests/performance/test_realworld_scenarios_performance.py`, `tests/performance/test_throughput_benchmarks.py`
- **Evidence**: `tests/test_migrations.py:56 schema_version = session.query(SchemaVersion).first()`; `tests/concurrency/test_thread_safety.py:197 track = session.query(Track).filter_by(id=track_id).first()`
- **Migration Path**: Mechanical rewrite to `select()` + `session.execute(...).scalars()`. Contained entirely in test code; production repositories are already fully migrated.
- **Risk**: Very low. Test-side only; the Query API is legacy but not removed on 2.0.44, so no functional breakage. Value is consistency with production.

### INT-1: `realtime_processor.py` backward-compat re-export shim with 2 live callers
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/player/realtime_processor.py:1-27`
- **Status**: NEW
- **Deprecated API**: Module `auralis.player.realtime_processor` — pure BC wrapper re-exporting from canonical `auralis.player.realtime`
- **Deprecated Since**: n/a (docstring: "maintains backward compatibility... For new code, prefer importing from `auralis.player.realtime` directly")
- **Removal Version**: unset
- **Replacement**: `from auralis.player.realtime import RealtimeProcessor`
- **Affected Files**: 2 live callers — `auralis/player/fingerprint_loader_mixin.py:17`, `auralis/player/enhanced_audio_player.py:36`
- **Evidence**: shim body is only `from .realtime import (...)` + `__all__`; both callers still import `RealtimeProcessor` from the shim
- **Migration Path**: Repoint both imports to `.realtime`, then delete the shim module.
- **Risk**: None functional; the self-declared migration simply never completed.

### INT-2: `base_spectrum_analyzer.py` — 4 dead "backward compatibility wrapper" methods
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/analysis/base_spectrum_analyzer.py:228-278`
- **Status**: NEW
- **Deprecated API**: `_a_weighting_curve`, `_c_weighting_curve`, `_map_to_bands`, `_calculate_rolloff` (each docstring'd "backward compatibility wrapper")
- **Replacement**: the `SpectrumOperations.*` static methods they delegate to (already called directly elsewhere)
- **Affected Files**: 0 callers of these wrappers. `parallel_spectrum_analyzer.py:224/258/234/281` call the `_map_to_bands_vectorized` / `_calculate_rolloff_vectorized` variants, not these.
- **Evidence**: grep-minus-defs yields zero hits for `_a_weighting_curve` / `_c_weighting_curve`; the other two hits are the `*_vectorized` siblings.
- **Migration Path**: Delete the 4 wrapper methods.
- **Risk**: Dead code only.

### INT-3: `track_repository.get_track_by_path` dead BC alias
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/library/repositories/track_repository.py:283`
- **Status**: NEW
- **Deprecated API**: `get_track_by_path` — "Alias for `get_by_path` for backward compatibility"
- **Replacement**: `get_by_path`
- **Affected Files**: 0 callers (grep-minus-def empty across `auralis/` + `auralis-web/`)
- **Migration Path**: Delete the alias.
- **Risk**: Dead code only.

### CI-1: `black`/`mypy` target versions require newer tools than the dev pins guarantee
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pyproject.toml` — `[tool.black] target-version = ["py314"]`, `[tool.mypy] python_version = "3.14"`, dev pins `black>=22.0.0`, `mypy>=0.950`
- **Status**: NEW
- **Deprecated/Mismatch**: `target-version = ["py314"]` is a valid Black `TargetVersion` only in Black 25.x (Py3.14 support landed 2025); Black 22–24 hard-errors on `py314`. Same shape for mypy `python_version = 3.14` vs `mypy>=0.950`.
- **Replacement**: Raise floors to `black>=25.9.0` and a mypy release that recognizes Python 3.14.
- **Affected Files**: 1 (`pyproject.toml`). Local-dev only — no CI job runs black/mypy (workflows are `frontend-typecheck.yml` + `build-release.yml`).
- **Risk**: A fresh `pip install -e .[dev]` normally resolves the latest and works; the loose lower bound just does not guarantee it.

### CI-2: `pytest.ini` declares a deprecated marker with zero usages
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pytest.ini` markers block — `edge_cases: Edge case tests (deprecated, use edge_case)`
- **Status**: NEW
- **Deprecated API**: the `edge_cases` marker (self-labeled deprecated in favor of `edge_case`)
- **Affected Files**: 0 test usages (`@pytest.mark.edge_cases` grep empty)
- **Migration Path**: Drop the `edge_cases` marker line (safe under `--strict-markers` since it is unused).
- **Risk**: None.

---

## Deduplicated (Pre-Existing, Still Open)

Confirmed still-present and matched to open issues; **not** re-reported:

| Issue | Summary | Location |
|-------|---------|----------|
| #4314 | `LibraryManager` deprecated facade raises `DeprecationWarning` | `auralis/library/manager.py:91` |
| #4313 | `require_library_manager` shim with zero production callers | `auralis-web/backend/routers/dependencies.py:48` |
| #4307 | `feature_extractors.py` DEPRECATED wrapper with 1 live caller | `auralis/analysis/.../feature_extractors.py` |
| #3770 | Cache invalidation lives on the deprecated `LibraryManager` facade | `auralis/library/manager.py` |
| #3720 | `processor_factory.set_mastering_targets` DEPRECATED, no in-tree callers | `auralis-web/backend/core/processor_factory.py:365` |

---

## Dependency Upgrade Roadmap

**No upgrades are required for correctness.** Every runtime dependency is already on a current major version and the code uses that version's modern API. Optional, opportunistic tightening only:

| Package | Current pin | Action | Blocks anything? |
|---------|-------------|--------|------------------|
| black (dev) | `>=22.0.0` | Raise to `>=25.9.0` (matches `target-version = py314`) | No — local formatting only |
| mypy (dev) | `>=0.950` | Raise to a Py3.14-aware release | No — local type-check only |
| Runtime deps (numpy, scipy, fastapi, pydantic, sqlalchemy, react, mui, vite, vitest, electron, pyo3) | current | none | No |

There is **no forward-migration cliff**: PyO3 is already on the 0.23 Bound API (0.24 removes gil-refs — already done), SQLAlchemy is on the 2.0 style, Pydantic on V2, MUI on Grid v2, react-query on v5, GitHub artifact actions on v4.

## Migration Effort Estimate

| Finding | Sites | Effort |
|---------|-------|--------|
| PY-1 (event_loop fixtures) | 2 | Small |
| SQL-1 (test Query API) | ~47 across 13 files | Medium (mechanical) |
| INT-1 (realtime_processor shim) | 2 callers + 1 module | Small |
| INT-2 (dead spectrum wrappers) | 4 methods, 0 callers | Small |
| INT-3 (dead repo alias) | 1 method, 0 callers | Small |
| CI-1 (dev-tool floors) | 1 file | Small |
| CI-2 (unused marker) | 1 line | Small |

---

## Next Step

Report ready. To triage into GitHub issues:

```
/audit-publish docs/audits/AUDIT_DEPRECATION_2026-07-12.md
```

Suggested labels on publish: `low` + `deprecation` + `maintenance` + layer label (`audio-engine`, `backend`, `library`, `config`) per finding.
