# Deprecation Audit — 2026-09-13

**Scope**: entire Auralis repo at `ce119be1` (master): Python engine and backend, React/TS frontend, Electron desktop, Rust DSP (PyO3), third-party dependencies, config/CI.
**Method**: fresh audit of the current tree, across 8 dimensions grouped into 4 passes: Python stdlib + NumPy/SciPy, FastAPI/Pydantic/SQLAlchemy + internal, React/Node/build, Rust + config/CI. Every finding was checked against the **installed** library version (`.venv`, `node_modules`, `Cargo.lock`), and where possible confirmed from the library's own source (`@deprecated` tags, `DeprecationWarning` emitters) or with a runtime probe. Prior reports in `docs/audits/` were not used as a source. Dedup: `gh issue list` (1,000 most recent issues, all states, plus all 130 `deprecation`-labelled issues), `gh issue list --search`, and `.claude/issues/`.
**Constraints honoured**: read-only (no installs, no commits, no issues, no `git stash`), and only individual test files were run.

## Executive Summary

| Severity | Count | NEW | Existing | Regression |
|---|---|---|---|---|
| CRITICAL | 0 | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 | 0 |
| MEDIUM | 2 | 2 | 0 | 0 |
| LOW | 32 | 27 | 4 | 1 |
| **Total** | **34** | **29** | **4** | **1** |

Existing (not to be re-filed): DEP-PY-6 → #4624, DEP-API-1 → #4333, DEP-INT-2 → #4973/#5164/#5165/#5231/#5232/#5233/#5234, DEP-CFG-5 → #4336 (widened with new siblings). Regression: DEP-NP-3 → #3482 (project window convention only; not a real NumPy deprecation, see the finding).

**Headline: no removed API is called anywhere.** Every check for removed or breaking deprecations came back clean against the installed versions, and several were confirmed at runtime:
- **Python and NumPy/SciPy**: none of the Python 3.12–3.14 stdlib removals or NumPy 2.x removals are used, and neither are the SciPy 1.13–1.15 removals. Importing every `auralis.*` module with warnings forced on raised 0 DeprecationWarnings.
- **Backend**: none of the Pydantic V1 idioms, FastAPI `on_event` or SQLAlchemy 1.x ORM patterns appear in production. `import main` under `-W default` raised 0 warnings.
- **Frontend**: none of the React 18-removed APIs, legacy lifecycles, `connect()`/`createStore` or MUI v9-deprecated props are used. `type-check:prod` is a clean gate.
- **Desktop and Rust**: no deprecated Electron 43 APIs are used, and `cargo check --all-targets` reports 0 deprecation warnings.

**The two MEDIUM findings are both about keeping CI trustworthy, not runtime breakage:**
1. **DEP-INT-1**: 13 backend tests still send the enhancement presets retired today (`warm`/`bright`/`punchy`/`gentle`) and fail. None of them is in `pytest-baseline.json`, so `backend-tests.yml` (which runs all of `tests/` with `-m "not slow"`) fails its ratchet on them. No production surface accepts or emits a removed name.
2. **DEP-NODE-1**: both pnpm projects keep their advisory-driven security overrides under the `pnpm` field of `package.json`, which pnpm 11+ no longer reads. This blocks any `packageManager` bump past 10.x until the overrides move to `pnpm-workspace.yaml`.

**Key upgrade blockers**:
- **pnpm 11+**: blocked by DEP-NODE-1.
- **TypeScript 6/7**: blocked by `baseUrl` (DEP-FE-1).
- **NumPy 2.5**: blocked by numba 0.66's `numpy<2.5` cap (numba 0.67 is now out and may lift it).
- **pyo3/numpy-rs 0.29**: known-blocked by an ABI runtime failure, but the evidence is stale because it was recorded against NumPy 2.3.x and 2.4.6 is now pinned (DEP-RS-1).
- **librosa 1.0**: removes the audioread backend, which currently pulls in removed-stdlib backports (DEP-NP-1).

**Recommended migration order**:
1. DEP-INT-1, to restore the backend gate.
2. Config rot that makes tooling claims false: DEP-CFG-1 (strict mypy never applied), DEP-CFG-2 (coverage floor inert), DEP-CFG-3 (Makefile), DEP-CFG-4, and DEP-API-2.
3. DEP-NODE-1, before any pnpm bump.
4. Cheap forward-compat items: DEP-FE-1, DEP-NP-2, DEP-PY-2, DEP-PY-4.
5. Bundle the rest with their upgrade: Vite 8 (DEP-NODE-3/5), React 19 (DEP-FE-2), librosa 1.0 (DEP-NP-1), pyo3 re-verification (DEP-RS-1 → DEP-RS-2).
6. Dead internal compat shims (DEP-INT-3..8) opportunistically.

### Severity calibration notes

- No pass proposed a CRITICAL or HIGH finding. The removed-API sweeps (the only route to CRITICAL/HIGH under this audit's severity table) were all clean, and that was cross-checked with runtime import and warning probes.
- **DEP-INT-1 (MEDIUM, confirmed by the coordinator)**:
  - The baseline has no entry for any of the four test files.
  - A scoped run of one file reproduced the `Input should be 'adaptive'` failure.
  - `backend-tests.yml` collects the whole `tests/` tree.
  - The impact is a red CI gate with no production effect, so MEDIUM rather than HIGH.
- **DEP-NODE-1 (kept at MEDIUM, risk statement corrected)**: CI installs use `--frozen-lockfile` everywhere, and both lockfiles record the overrides, so a pnpm 11 bump most likely fails CI loudly rather than silently. The silent path is a local non-frozen lockfile regeneration. It stays MEDIUM because it is a hard prerequisite for the package-manager upgrade and it protects security pins.
- **DEP-NP-3 keeps its "Regression of #3482" status, but it is LOW convention drift only**: the pass verified that NumPy 2.4.6 does not deprecate `np.hanning`, so the premise of #3482 and #2929 was wrong.
- **Deprecated-but-working APIs (LOW by default)**: DEP-PY-2 `asyncio.TimeoutError`, DEP-NP-2 `SoundFile.__len__`, DEP-PY-4 `mimetypes.guess_type(path)` and DEP-FE-2 global `JSX` are LOW. None emits a warning at runtime, and none is removed in an installed version.

## Findings — CRITICAL (0)


None.

## Findings — HIGH (0)


None.

## Findings — MEDIUM (2)


### DEP-INT-1: Tests still assert the retired presets ('warm'/'bright'/'punchy'/'gentle') are accepted — 13 new failures outside the CI baseline
- **Severity**: MEDIUM
- **Dimension**: Internal
- **Location**: `tests/backend/test_enhancement_settings_persistence_4587.py` (9 failing), `tests/backend/test_scan_and_enhancement_helpers.py:60-90` (2), `tests/backend/test_enhancement_router_handler_seam_4670.py:43-102` (1), `tests/backend/test_main_api.py:1588-1596` (1); plus non-collected siblings and one stale docstring (below)
- **Status**: NEW (follow-up gap from the 2026-09-13 preset narrowing, `c195ac80`/`ae9d28e3`; none of these test files were touched by those commits — last touched by `698408da` (#4587))
- **Deprecated API**: Internal preset names removed on 2026-09-13 (`VALID_PRESETS = ["adaptive"]`, `EnhancementPresetLiteral = Literal["adaptive"]`, `auralis-web/backend/schemas.py:36-37`)
- **Deprecated Since**: 2026-09-13 (removed, not deprecated)
- **Removal Version**: Already removed
- **Replacement**: `'adaptive'`, or assertions that a retired name gets a 422 / degrades to 'adaptive' (as `tests/test_preset_system.py:108-113,128-136` already do correctly)
- **Affected Files**: Production surfaces that accept or emit a removed name: **0** (verified — REST `SetPresetRequest.preset: EnhancementPresetLiteral` (`routers/enhancement.py:56`), settings PUT `default_preset: EnhancementPresetLiteral` (`routers/settings.py:109`), settings response degrade validator (`routers/settings.py:170-176`), startup seed degrade (`helpers.py:119-126`), WS `playback_commands.py:76-98,245`, `proactive_buffer.AVAILABLE_PRESETS = ["adaptive"]`, `PreferenceVector.from_preset_name` falls back to neutral, frontend `types/domain.ts:152`). Failing tests: 4 files / 13 tests. Non-collected (under `norecursedirs = tests/validation`), dead: `tests/validation/test_e2e_processing.py:65-82`, `tests/validation/test_preset_integration.py:123-132`, `tests/validation/validate_real_world_presets.py:114-115`. Stale doc: `auralis-web/backend/core/chunk_content_profile.py:48`. Uses 'warm' but still passes (preset only used as a cache-key string): `tests/backend/test_processor_cache_key_intensity_4707.py:125`. Deliberate survivors, not reported: `Player.test.tsx` 'warm' sentinel, `preset_anchors.py`, `auto_master.py` profile ids (`test_mastering_recommendation_response.py:149 primary_profile_id="warm"`).
- **Evidence**:
  ```python
  # tests/backend/test_enhancement_settings_persistence_4587.py:320-326
  resp = client.post("/api/player/enhancement/preset", json={"preset": "punchy"})
  assert resp.status_code == 200          # now 422
  assert settings["preset"] == "punchy"
  # tests/backend/test_enhancement_router_handler_seam_4670.py:85
  SetPresetRequest(preset="WARM")  # -> ValidationError: Input should be 'adaptive'
  # tests/backend/test_main_api.py:1593
  response = client.post("/api/player/enhancement/preset", json={"preset": "warm"})
  # auralis-web/backend/core/chunk_content_profile.py:48
  preset: Preset name (e.g., "adaptive", "gentle", "warm", etc.)
  ```
  Scoped run: `pytest -q tests/backend/test_enhancement_settings_persistence_4587.py tests/backend/test_scan_and_enhancement_helpers.py tests/backend/test_enhancement_router_handler_seam_4670.py tests/backend/test_processor_cache_key_intensity_4707.py` → **12 failed, 26 passed**; `pytest tests/backend/test_main_api.py::TestPlayerEnhancementEndpoints::test_set_enhancement_preset` → **1 failed**. None of these node ids are in `pytest-baseline.json`.
- **Migration Path**: (1) For persistence/round-trip/seed tests, switch the "changed" value to 'adaptive' where the test only needs a valid value. Where the test needs two different values (e.g. `test_unchanged_preset_does_not_trigger_a_redundant_write`, seed `test_maps_all_three_fields`), assert on intensity/enabled instead, or add a separate "retired name → 422 / degrades to adaptive" case. (2) Fix `handler_seam_4670` to use `SetPresetRequest(preset="ADAPTIVE")`. (3) Fix `test_main_api::test_set_enhancement_preset` to post 'adaptive'. (4) Delete or rewrite the three `tests/validation/` preset scripts. (5) Update the `chunk_content_profile.py:48` docstring.
- **Risk**: `backend-tests.yml`'s baseline ratchet fails on 13 unlisted failures, so the backend gate is red until these are fixed or (wrongly) baselined. Baselining them would re-permit asserting the retired contract.
- **Effort**: Small (4 collected files, ~13 tests)
- **Verification**: Scoped pytest runs above; `grep -rnE "['\"](gentle|warm|bright|punchy)['\"]"` over `auralis auralis-web/backend auralis-web/frontend/src desktop scripts vendor/auralis-dsp/src tests` with comment lines excluded; read each production validation site listed.
- **Coordinator re-verification**:
  - Grepping `pytest-baseline.json` for the four test files returns nothing.
  - `pytest -q tests/backend/test_enhancement_router_handler_seam_4670.py` → 1 failed, 3 passed (`Input should be 'adaptive' [type=literal_error, input_value='warm']`).
  - None of the four files was touched after `c195ac80`/`ae9d28e3`.
  - `backend-tests.yml` runs `python -m pytest -q -m "not slow"` over the whole `tests/` tree, so the failures reach the ratchet.
  - MEDIUM: the CI gate is red, with no production impact.
- **Related**: #5149 (OPEN) covers the never-collected `tests/validation/` files, including the three preset scripts listed here.

### DEP-NODE-1: `pnpm.overrides` in package.json is ignored from pnpm 11 on, so the security overrides would be dropped without an error
- **Severity**: MEDIUM
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/package.json:84-93`, `desktop/package.json:38-45` (2 files)
- **Status**: NEW
- **Deprecated API**: settings under the `pnpm` field of `package.json` (`pnpm.overrides`). The frontend also has a top-level `overrides` key. That key is npm-only and pnpm never read it.
- **Deprecated Since**: pnpm 10 made `pnpm-workspace.yaml` the preferred home for settings. pnpm 11 stopped reading the field (pnpm 11.27.0 CHANGELOG.md:1975: "pnpm no longer reads settings from the `pnpm` field of `package.json`. Settings should be defined in `pnpm-workspace.yaml`").
- **Removal Version**: pnpm 11.0. A later 11.x only added a warning (CHANGELOG.md:1636: "Previously these were silently ignored after the upgrade from v10"). Latest pnpm is 12.4.1. The repo pins `packageManager: pnpm@10.20.0`.
- **Replacement**: an `overrides:` block in a `pnpm-workspace.yaml` next to each lockfile. No `pnpm-workspace.yaml` exists anywhere in the repo.
- **Affected Files**: 2 prod manifests, 0 test files
- **Evidence**:
  - `auralis-web/frontend/package.json`: `"overrides": { "rollup": ">=4.59.0" }` plus `"pnpm": { "overrides": { "rollup": ">=4.59.0" } }`
  - `desktop/package.json`: `"pnpm": { "overrides": { "app-builder-lib": "26.15.7", "electron-builder-squirrel-windows": "26.15.7", "fast-uri": "^3.1.5", "js-yaml": "^4.3.1" } }`
- **Migration Path**:
  1. Create `auralis-web/frontend/pnpm-workspace.yaml` and `desktop/pnpm-workspace.yaml`, each holding `overrides:` with the same entries.
  2. Delete the `pnpm` blocks, and the dead npm `overrides` key in the frontend.
  3. Run `pnpm install --lockfile-only` on pnpm 10.20.0 and confirm the lockfile `overrides:` header is unchanged.
  4. Only then bump `packageManager`.
- **Risk**: The overrides pin patched versions for advisories (rollup, fast-uri, js-yaml, app-builder-lib per #4883). Once `packageManager` moves past 10.x, CI's `pnpm install --frozen-lockfile` (8 sites across `frontend-test.yml`, `frontend-typecheck.yml` and `build-release.yml`) is expected to fail loudly on the lockfile/config `overrides` mismatch. The silent path is a local non-frozen `pnpm install` on pnpm 11+. It regenerates the lockfile without the `overrides:` header and re-resolves to vulnerable versions, and that lockfile then passes CI.
- **Effort**: Small (2 files, 5 entries)
- **Verification**: `pnpm view pnpm version` returned 12.4.1. `npm pack pnpm@11.27.0` into the scratchpad, then grepped CHANGELOG.md. `ls */pnpm-workspace.yaml` found no such file.
- **Coordinator re-verification**:
  - Both `pnpm.overrides` blocks are present (`desktop/package.json:39-46`, `auralis-web/frontend/package.json:85-89`).
  - No `pnpm-workspace.yaml` exists at the root, in the frontend or in desktop.
  - All three `packageManager` fields are `pnpm@10.20.0`.
  - Both lockfiles carry an `overrides:` header.
  - Every CI install uses `--frozen-lockfile`.
  - Severity kept at MEDIUM: this is a hard prerequisite for the package-manager upgrade and it protects security pins. The pass's original "CI would not fail" risk statement was corrected above.

## Findings — LOW (32)


### DEP-PY-1: Deprecated `typing.Mapping` / `typing.Sequence` aliases in production code
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `auralis/core/processing/target_derivation.py:39`, `auralis/core/processing/delta_eq.py:30`, `auralis/library/repositories/artist_repository.py:11` (3 files)
- **Status**: NEW (#4624 covers only the test tree and states "production Python is 100% migrated". Its grep only looked for `Optional|List|Dict|Tuple|Union`, so these aliases were missed. #2147 and #2934 were closed for the older, broader sweep.)
- **Deprecated API**: `typing.Mapping`, `typing.Sequence` (PEP 585 aliases of `collections.abc` ABCs)
- **Deprecated Since**: Python 3.9
- **Removal Version**: Not scheduled (docs: "may be removed" once 3.8 support ends; no warning emitted)
- **Replacement**: `from collections.abc import Mapping, Sequence` (82 production files already import from `collections.abc`)
- **Affected Files**: 3 prod / 0 test in this finding (the test tree is tracked in DEP-PY-6)
- **Evidence**:
  - `auralis/core/processing/target_derivation.py:39` `from typing import Any, Mapping` (blame c6451f646, 2026-05-24)
  - `auralis/core/processing/delta_eq.py:30` `from typing import Mapping` (6051d5e83, 2026-05-24)
  - `auralis/library/repositories/artist_repository.py:11` `from typing import Any, Sequence` (188db72af, 2026-08-13, after #4624 was filed)
- **Migration Path**: Change the three imports to `collections.abc`. No behaviour change: under PEP 649 the annotations are not evaluated eagerly anyway. Optionally enable ruff `UP035` to stop the pattern coming back. No `ruff` UP rule is configured today; `pyproject.toml` has only black `target-version = ["py314"]`.
- **Risk**: None at runtime. It is a consistency gap, and it shows #4624's "production is clean" claim is incomplete.
- **Effort**: Small
- **Verification**: `grep -rnE '^\s*from typing import .*\b(List|Dict|Tuple|Set|Optional|Union|Type|Deque|Callable|Iterable|Iterator|Sequence|Mapping|MutableMapping|Generator|...)\b' auralis auralis-web/backend scripts *.py`. There were exactly 3 hits. Every production `from typing import` name was tallied; the rest are `Any`, `TYPE_CHECKING`, `cast`, `Literal`, `Annotated`, `Protocol`, and similar non-deprecated names. The residual `List[`/`Dict[` matches in production are all inside docstrings (`interpolation_helpers.py:196`, `queue_repository.py:103`, `track_analysis_cache.py:117-119`, `analysis_extractor.py:103-105`).

### DEP-PY-2: `asyncio.TimeoutError` deprecated alias used in backend streaming/scan/worker code
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: 7 production files, 11 sites (e.g. `auralis-web/backend/core/stream_normal.py:75`)
- **Status**: NEW (no issue mentions `TimeoutError` in either dedup list)
- **Deprecated API**: `asyncio.TimeoutError`
- **Deprecated Since**: Python 3.11. Since then it has been a plain alias of the builtin `TimeoutError`, and the asyncio docs call it "A deprecated alias of TimeoutError".
- **Removal Version**: Not scheduled; no warning emitted
- **Replacement**: builtin `TimeoutError`, which `asyncio.wait_for` and `asyncio.timeout` raise directly on 3.11+
- **Affected Files**: 11 prod sites in 7 files, plus 6 test sites.
  - Prod: `auralis-web/backend/services/similarity_autofit_worker.py:73`
  - Prod: `auralis-web/backend/services/library_auto_scanner.py:146,308,413`
  - Prod: `auralis-web/backend/core/stream_seek.py:84`
  - Prod: `auralis-web/backend/core/stream_normal.py:75`
  - Prod: `auralis-web/backend/core/stream_enhanced.py:77`
  - Prod: `auralis-web/backend/routers/library_scan.py:184,188,272`
  - Prod: `auralis-web/backend/analysis/fingerprint_generator.py:127`
- **Evidence**: `auralis-web/backend/core/stream_normal.py:75` `except asyncio.TimeoutError:`; `library_auto_scanner.py:146` `except (asyncio.CancelledError, asyncio.TimeoutError):`
- **Migration Path**: Mechanical replacement `asyncio.TimeoutError` → `TimeoutError`. The identity holds on 3.14 (`asyncio.TimeoutError is TimeoutError`), so catching is unchanged. Ruff `UP041` automates it.
- **Risk**: None today. Cosmetic until CPython actually schedules removal.
- **Effort**: Medium (17 sites total)
- **Verification**: `grep -rnE --include='*.py' 'asyncio\.TimeoutError' auralis auralis-web/backend tests`: 11 prod + 6 test. `concurrent.futures.TimeoutError` (the sibling deprecated alias) has 0 sites.

### DEP-PY-3: `from __future__ import annotations` in a PEP 649 (3.14-only) codebase
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: 59 production modules (e.g. `auralis/services/resizable_semaphore.py`, `auralis/core/processing/target_derivation.py`, `auralis/dsp/utils/filters.py`, `auralis/core/mastering_branches/base.py`); 69 more across `tests/`, `scripts/`, root `*.py`
- **Status**: NEW (no dedup hit for `__future__` / PEP 649 / PEP 749)
- **Deprecated API**: `from __future__ import annotations` (PEP 563 stringified annotations)
- **Deprecated Since**: Not yet emitting warnings. PEP 749, accepted for 3.14, says the future import "will be deprecated and eventually removed" once 3.13 is EOL (Oct 2029). It is officially slated for deprecation.
- **Removal Version**: TBD (after the deprecation period that follows 3.13 EOL)
- **Replacement**: Delete the import. On 3.14, PEP 649/749 deferred evaluation already makes forward references and self-referencing annotations work lazily. The project already depends on that: CLAUDE.md notes that the PEP 649 annotations fail at import on 3.13.
- **Affected Files**: 59 prod / 69 test+scripts+root (395 production modules do not use it)
- **Evidence**: `grep -rlE '^from __future__ import annotations' auralis auralis-web/backend | wc -l` → 59; the same grep over `scripts tests *.py` → 69.
- **Migration Path**:
  1. Remove the import module-by-module.
  2. Check any runtime introspection of annotations; Pydantic/FastAPI resolve both forms. `typing.get_type_hints` / `__annotations__` are used only in 2 test sites, and `annotationlib` / `inspect.get_annotations` are unused.
  3. Run the scoped tests plus mypy for each touched domain.
- **Risk**: Very low. The two annotation models are mixed module by module, so `__annotations__` holds strings in 59 modules and lazily evaluated objects elsewhere. That only matters to code that introspects annotations, which production does not do directly. Flagged for consistency ahead of the PEP 749 deprecation, not for breakage.
- **Effort**: Large (128 files, mechanical)
- **Verification**: grep counts above; PEP 749 text ("Deprecation of `from __future__ import annotations`" section).

### DEP-PY-4: `mimetypes.guess_type()` called with a filesystem path (soft-deprecated in 3.13)
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `auralis-web/backend/routers/artwork.py:422`
- **Status**: NEW
- **Deprecated API**: Passing a file path, rather than a URL, to `mimetypes.guess_type()`
- **Deprecated Since**: Python 3.13 (soft deprecation; `guess_file_type()` added)
- **Removal Version**: Not scheduled (soft deprecation, no warning)
- **Replacement**: `mimetypes.guess_file_type(requested_path)`, which accepts `os.PathLike` directly. It is present in the venv: `hasattr(mimetypes, 'guess_file_type')` → True.
- **Affected Files**: 1 prod / 1 test hit for `guess_type` (test not inspected further; test-only)
- **Evidence**: `auralis-web/backend/routers/artwork.py:422` `media_type, _ = mimetypes.guess_type(str(requested_path))`
- **Migration Path**: `media_type, _ = mimetypes.guess_file_type(requested_path)`. This also drops the `str()` round-trip.
- **Risk**: None today. `guess_type()` URL-parses its argument, so unusual characters in a path (`#`, `?`) could in principle be misread as URL syntax. `guess_file_type()` exists to avoid exactly that.
- **Effort**: Small
- **Verification**: `grep -rnE 'mimetypes\.guess_type' auralis auralis-web/backend scripts` → 1; 3.13 "What's New" (mimetypes: `guess_file_type()` added, passing paths to `guess_type()` soft deprecated).

### DEP-PY-5: `tempfile.mktemp()` in tests
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `tests/edge_cases/test_filesystem_errors.py:602`, `tests/integration/test_e2e_workflows.py:322`
- **Status**: NEW
- **Deprecated API**: `tempfile.mktemp()`
- **Deprecated Since**: Python 2.3 (documented as deprecated and insecure: TOCTOU race)
- **Removal Version**: Not scheduled
- **Replacement**: the pytest `tmp_path` fixture (already used in 60+ test files), or `tempfile.NamedTemporaryFile(delete=False)` / `mkstemp()`
- **Affected Files**: 0 prod / 2 test
- **Evidence**: `tests/integration/test_e2e_workflows.py:322` `temp_output = tempfile.mktemp(suffix=".wav")`; `tests/edge_cases/test_filesystem_errors.py:602` `temp_db_path = tempfile.mktemp(suffix='.db')`
- **Migration Path**: Use `tmp_path / "out.wav"`. That also removes the manual cleanup and the leaked-file risk if the test fails.
- **Risk**: Test-only; possible leaked temp files, plus a theoretical race on a shared `/tmp`.
- **Effort**: Small
- **Verification**: `grep -rnE --include='*.py' 'tempfile\.mktemp\(' auralis auralis-web/backend tests scripts` → 2 (both tests).

### DEP-PY-6: Legacy typing generics in the test tree
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `tests/` (14 files using #4624's own regex; 16 with a wider alias list)
- **Status**: Existing: #4624 (OPEN)
- **Deprecated API**: `typing.List/Dict/Tuple/Optional/Union/...` (PEP 585/604)
- **Deprecated Since**: Python 3.9 / 3.10
- **Removal Version**: Not scheduled
- **Replacement**: builtin generics, `X | None`
- **Affected Files**: 0 prod / 14–16 test. #4624 counted 20 at filing, so the count is shrinking. `scripts/` and root `*.py` have 0, confirming that #4959's fix still holds.
- **Evidence**: `grep -rlnE "from typing import.*(Optional|List|Dict|Tuple|Union)" tests | wc -l` → 14
- **Migration Path**: Per #4624.
- **Risk**: None.
- **Effort**: Medium
- **Verification**: grep above; `gh issue view 4624` (OPEN).

### DEP-NP-1: Production fingerprint paths import `audioread`, which runs on PyPI backports of stdlib modules removed in 3.13; librosa 1.0.0 (now released) drops the backend
- **Severity**: LOW
- **Dimension**: NumPy/SciPy
- **Location**: The first `librosa.load`/`librosa.resample` call imports `librosa.core.audio`, whose line 11 is `import audioread`. On first decode that reaches `audioread/rawread.py:16-19` (`import aifc`, `import audioop`, `import sunau`). Production triggers: `auralis/analysis/mastering_fingerprint.py:125,129,133`, `auralis/analysis/fingerprint/windowed_compute.py:239,246,288,299,328,330`, `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:65,70`, `auralis-web/backend/analysis/analysis_extractor.py:222` (4 prod files).
- **Status**: NEW. #4890 (CLOSED) routed M4A/AAC/WMA away from the audioread *decode fallback*, and that fix is still in place at `mastering_fingerprint.py:104-131`. This finding is about the import-time dependency on removed-stdlib backports and the now-released librosa 1.0, which no issue covers; dedup grep for `aifc|sunau|audioop|standard-` returned nothing.
- **Deprecated API**: librosa's audioread backend, plus the `aifc`, `sunau` and `audioop` stdlib modules it imports
- **Deprecated Since**: librosa 0.10.0 (`@deprecated(version="0.10.0", version_removed="1.0")` on `__audioread_load`, `librosa/core/audio.py:227`); `aifc`/`sunau`/`audioop` were deprecated in Python 3.11 (PEP 594) and removed in 3.13
- **Removal Version**: librosa 1.0.0, which is available on PyPI now (`uv pip list --outdated` → `librosa 0.11.0 → 1.0.0`). The librosa 1.0 changelog lists the "`audioread` backend" among expired deprecations.
- **Replacement**: On librosa 1.0, soundfile is the only in-library decoder. Formats soundfile cannot decode must go through `auralis.io.unified_loader` / `load_with_ffmpeg`, which the #4890 fix already does for `FFMPEG_FORMATS`.
- **Affected Files**: 4 prod (librosa call sites) / 6 test files import librosa directly (`tests/test_phase6_*`, `tests/test_phase5_rust_benchmark.py`, `tests/test_hpss_rust_validation.py`, `tests/test_chroma_rust_validation.py`, `tests/regression/test_mastering_regression.py`) + `scripts/rate_track.py`
- **Evidence**:
  - Import of `librosa` alone does not load audioread (`'audioread' in sys.modules` → False). After `librosa.resample(...)` it does (→ True).
  - Running `tests/test_fingerprint_unification_4595.py` with `-W always::DeprecationWarning` shows `audioread/rawread.py:16: DeprecationWarning: aifc was removed in Python 3.13. Please be aware that you are currently NOT using standard 'aifc', but instead a separately installed 'standard-aifc'.` and the same warning for `sunau`.
  - Dependency chain (installed metadata): `librosa -> standard-aifc; python_version >= "3.13"`, `audioread -> standard-sunau`, `standard-aifc -> audioop-lts, standard-chunk`. None of these are declared by Auralis itself; they are transitive only.
  - `pytest.ini` hides both signals: it has `ignore:.*was removed in Python 3\.13.*separately installed.*:DeprecationWarning` and `ignore:.*__audioread_load.*:FutureWarning`.
- **Migration Path**:
  1. Treat librosa 1.0 as the upgrade target, and confirm no production path still reaches `librosa.load()` for a format soundfile cannot open. The non-FFmpeg branch at `mastering_fingerprint.py:133` and `windowed_compute.py:288,299` relies on the `FFMPEG_FORMATS` list staying complete.
  2. Consider replacing the remaining production `librosa.load` calls with `unified_loader.load_audio` so decoding has a single authority. `librosa.resample` alone still imports `librosa.core.audio`; audioread is imported, but no decode happens.
  3. Review test-visible 1.0 behaviour changes before bumping: `note_to_hz` default quantization removed (used in `tests/test_phase5_rust_benchmark.py:138-139`); `yin` accuracy changes in 0.11/1.0 (used by the Rust YIN validation tests). No production call uses the removed `win_length`, `set_fftlib`, `filters.constant_q` or `stream(filename=)`.
  4. Once audioread is no longer imported, remove the two pytest.ini ignore lines.
- **Risk**: No breakage on the pinned 0.11.0. The warnings are invisible in production under default filters. The runtime depends on third-party revivals of removed stdlib modules (`audioop-lts` is a C extension, which adds wheel-availability risk on new platforms and Pythons). A librosa 1.0 bump turns any stray non-soundfile decode into a hard error instead of a warning.
- **Effort**: Small (4 prod files)
- **Verification**:
  - Installed source: `librosa/core/audio.py:11,227`; `audioread/__init__.py:79`, which imports `rawread` lazily; `audioread/rawread.py:16-19`.
  - `importlib.metadata.requires()` for audioread and librosa.
  - Ran one scoped test file with warnings forced on.
  - `uv pip list --outdated`.
  - librosa changelog (librosa.org/doc/latest/changelog.html).

### DEP-NP-2: `len(soundfile.SoundFile)` — deprecated frame-count idiom
- **Severity**: LOW
- **Dimension**: NumPy/SciPy
- **Location**: `auralis/core/mastering_prepare.py:121`, `auralis-web/backend/core/stream_normal.py:148`, `auralis/analysis/fingerprint/windowed_compute.py:171` (3 prod sites)
- **Status**: NEW
- **Deprecated API**: `SoundFile.__len__`
- **Deprecated Since**: soundfile (upstream python-soundfile issue #199). The installed 0.14.0 source says at `soundfile.py:811`: `# Note: This is deprecated and will be removed at some point, see https://github.com/bastibe/python-soundfile/issues/199`. There is no runtime warning.
- **Removal Version**: Unscheduled ("at some point"). Removing it will also change `__bool__`, which soundfile keeps returning True only "until `__len__` is removed".
- **Replacement**: `SoundFile.frames`, already the majority idiom: 10 production uses, e.g. `auralis/analysis/quality/mastering_file_evaluation.py:30-31`.
- **Affected Files**: 3 prod / 1 test file (2 sites)
- **Evidence**:
  - `auralis/core/mastering_prepare.py:121` `total_frames = len(audio_file)`
  - `auralis-web/backend/core/stream_normal.py:148` `return audio_file.samplerate, audio_file.channels, len(audio_file)`
  - `auralis/analysis/fingerprint/windowed_compute.py:171` `_total_s = len(_f) / _f.samplerate`
  - test: `tests/auralis/core/test_prev_tail_corruption_guard.py:205,210` `expected_frames = len(f)` / `actual_frames = len(f)`
- **Migration Path**: Replace `len(x)` with `x.frames` at the 5 sites.
- **Risk**: A future soundfile release could drop `__len__`. That would raise `TypeError` on the master-file prepare path, the normal-stream metadata path, and the fingerprint windowing path, all of which are hot. This audit found no `pytest.ini` filter hiding it (the method emits nothing), but pytest.ini does blanket-ignore `DeprecationWarning:soundfile`, so a warning added in a future release would stay hidden.
- **Effort**: Small
- **Verification**: installed `soundfile.py:810-819`; `grep -rnE 'SoundFile\(.*\) as (\w+)'` to find the handle names, then `len(<handle>)` greps per name; `grep -rnE '\.frames\b' auralis auralis-web/backend | wc -l` → 10.

### DEP-NP-3: `np.hanning()` back in production DSP code (project window policy, not an actual NumPy deprecation)
- **Severity**: LOW
- **Dimension**: NumPy/SciPy
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:105`
- **Status**: Regression of #3482 (CLOSED). The pattern that #3482, #2929, #2675 and #2670 migrated to `scipy.signal.windows.*` is back at one site, added with the #4101 analysis-window change.
- **Deprecated API**: `numpy.hanning`. For accuracy: NumPy 2.4.6 does **not** deprecate it. `np.hanning(8)` runs with no warning, and `np.hanning.__doc__` has no deprecation note. #3482's "soft-deprecated in NumPy 2.0" premise, and #2929's "crashes on NumPy >= 2.0", do not hold for the installed version. What this finding reports is drift from the project convention.
- **Deprecated Since**: n/a in NumPy (project convention since #2670/#2929)
- **Removal Version**: none
- **Replacement**: `from scipy.signal.windows import hann`; `hann(self.fft_size, sym=True)`. The symmetric form gives coefficients identical to `np.hanning`, so the `_analysis_window_gain` scaling is unchanged. Other production modules already use it: 5 import sites of `scipy.signal.windows.hann`.
- **Affected Files**: 1 prod / 0 test
- **Evidence**: `auralis/dsp/eq/psychoacoustic_eq.py:105` `self._analysis_window = np.hanning(self.fft_size)`
- **Migration Path**: Swap to `hann(self.fft_size)` (scipy default `sym=True`, identical values). Keep it symmetric: switching to periodic would change the coherent gain, and with it the adaptive-gain scale that #4101's comment warns about.
- **Risk**: None functional. Convention and consistency only.
- **Effort**: Small
- **Verification**: runtime probe `np.hanning(8)` under `warnings.simplefilter("always")` → no warning; `grep -rnE 'np\.(hanning|hamming|blackman|bartlett|kaiser)\('` → 1 prod hit.

### DEP-API-1: Legacy `Session.query()` Query API still spreading in the test tree (production is clean)
- **Severity**: LOW
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: 15 test files, 50 call sites (plus `scripts/development/monitor_fingerprinting.py:37-38`, `tests/stress/test_large_library.py:346`)
- **Status**: Existing: #4333 (issue says "~13 test files"; current count is 15 files / 50 sites, so it has grown slightly)
- **Deprecated API**: `Session.query(Model)` (the 1.x `Query` object, "legacy" in 2.0); also `Session.bulk_save_objects()` (legacy bulk API in 2.0)
- **Deprecated Since**: SQLAlchemy 2.0 (Query marked legacy; `bulk_save_objects` legacy)
- **Removal Version**: Not yet scheduled (Query remains "legacy" in 2.0/2.1; no warning is emitted)
- **Replacement**: `session.execute(select(Model)...)` / `session.scalars(select(...))`, `session.scalar(select(func.count(...)))`; `session.execute(insert(Model), [dicts])` for bulk inserts
- **Affected Files**: Production (`auralis/`, `auralis-web/backend/`): **0**. Dev scripts: 1 (`scripts/development/monitor_fingerprinting.py`, 2 sites, not shipped). Tests: 15 files / 50 sites — `tests/regression/test_data_migration.py`, `tests/performance/test_throughput_benchmarks.py`, `tests/performance/test_realworld_scenarios_performance.py`, `tests/performance/test_library_operations_performance.py`, `tests/concurrency/test_thread_safety.py`, `tests/test_engine_fixes_4596_4598.py`, `tests/edge_cases/test_concurrent_operations.py`, `tests/integration/test_queue_history.py`, `tests/security/test_sql_injection.py`, `tests/boundaries/test_library_operations_boundaries.py`, `tests/test_migrations.py`, `tests/stress/test_edge_cases.py`, `tests/stress/test_large_library.py`, `tests/auralis/core/test_core.py`, `tests/auralis/library/test_fingerprint_repository_placeholder_guard_4822.py`. `bulk_save_objects`: 1 test site.
- **Evidence**:
  - `scripts/development/monitor_fingerprinting.py:37` `total_tracks = session.query(Track).count()`
  - `scripts/development/monitor_fingerprinting.py:38` `session.query(func.count(TrackFingerprint.id)).scalar()`
  - `tests/stress/test_large_library.py:346` `session.bulk_save_objects(tracks)`
- **Migration Path**: Convert each site to `select()` + `session.scalars()/scalar()`; add a regression grep (like `tests/regression/test_selectinload_artist_queries.py`) that forbids `.query(` in `auralis/library` so production stays clean.
- **Risk**: None today. It is an obstacle if SQLAlchemy ever removes Query, and new tests copying the pattern keep the count growing (13 → 15).
- **Effort**: Medium (50 sites)
- **Verification**: `grep -rn --include='*.py' -E "\.query\([A-Z]" tests | wc -l` → 50; `grep -rlE ... tests | wc -l` → 15; same grep over `auralis auralis-web/backend` → 0.

### DEP-API-2: Raw-string `Session.execute("SELECT 1")` — API removed in SQLAlchemy 2.0; test can never pass and is hidden by the baseline
- **Severity**: LOW
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**: `tests/load_stress/test_memory_resource_stress.py:198`
- **Status**: NEW
- **Deprecated API**: Passing a plain string to `Session.execute()` (implicit textual SQL coercion)
- **Deprecated Since**: SQLAlchemy 1.4 (RemovedIn20Warning)
- **Removal Version**: 2.0 (removed; installed 2.0.51 raises `ArgumentError`)
- **Replacement**: `session.execute(text("SELECT 1"))`
- **Affected Files**: Production 0; tests 1 file / 1 site. (The `conn.execute("PRAGMA ...")` strings in `tests/test_migrations.py:292-338` and the production `cursor.execute("PRAGMA ...")` calls are stdlib `sqlite3` / DBAPI cursors, not SQLAlchemy — clean.)
- **Evidence**:
  ```python
  # tests/load_stress/test_memory_resource_stress.py:195-199
  for i in range(100):
      session = temp_db()
      session.execute("SELECT 1")
      session.close()
  ```
  `pytest-baseline.json:107` lists `tests.load_stress.test_memory_resource_stress.TestResourceCleanup::test_database_connections_released`, so the CI ratchet permanently allows this failure.
- **Migration Path**: `from sqlalchemy import text`; `session.execute(text("SELECT 1"))`. Then drop the entry from `pytest-baseline.json` (the `--strict-stale` gate will require that once the test passes).
- **Risk**: The connection-leak stress test has measured nothing since the 2.0 migration. It raises on its first loop iteration, and the baseline entry hides that.
- **Effort**: Small (1 site)
- **Verification**: `python -c "from sqlalchemy import create_engine; from sqlalchemy.orm import sessionmaker; sessionmaker(create_engine('sqlite://'))().execute('SELECT 1')"` → `sqlalchemy.exc.ArgumentError: Textual SQL expression 'SELECT 1' should be explicitly declared as text('SELECT 1')`; `grep -n test_database_connections_released pytest-baseline.json` → line 107.

### DEP-INT-2: Open backward-compat shim issues — still present, counts unchanged
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: see table
- **Status**: Existing: #4973, #5164, #5165, #5231, #5232, #5233, #5234
- **Deprecated API**: Self-declared "backward compatibility" shims with zero production callers
- **Deprecated Since**: n/a (internal)
- **Removal Version**: n/a
- **Replacement**: Delete the shim / inline at test call sites
- **Affected Files**:
  | Issue | Symbol | Location | Prod callers | Test refs (now) |
  |---|---|---|---|---|
  | #4973 | `QueueHistoryRepository.undo(queue_repository=None)` | `auralis/library/repositories/queue_history_repository.py:99,110` | 0 | 0 by keyword |
  | #4973 | `create_psychoacoustic_eq()` | `auralis/dsp/eq/__init__.py:18-30` | 0 | 4 |
  | #4973 | `LibraryScanner.scan_folder()` / `scan_single_directory()` | `auralis/library/scanner/scanner.py:430,434` | 0 | 22 / 18 |
  | #5165 | `QueueController.tracks` property ("for old test code") | `auralis/player/queue_controller.py:55-59` | 0 | per issue |
  | #5164 | `PlayEnhanced` type alias | `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:54-55` (+ barrel `index.ts:26`) | 0 | 0 |
  | #5231 | `useKeyboardShortcuts` V1 config-object API | `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts:1-9,80-100` | 0 (sole caller `ComfortableApp.tsx:247` passes an array) | — |
  | #5232 | `queue_service.__all__` re-export of `AudioPlayerWithQueue`/`QueueManager` | `auralis-web/backend/services/queue_service.py:34-37` | 0 importers | 0 |
  | #5233 | `PlayerCallbacksMixin.get_playback_info()` flattening | `auralis/player/player_callbacks_mixin.py:68-90` | flattened keys read nowhere | — |
  | #5234 | `formatDuration` re-export from `types/domain.ts` | `auralis-web/frontend/src/types/domain.ts:333-334` | 0 importers | 0 |
- **Evidence**: see table rows; e.g. `auralis/dsp/eq/__init__.py:18` `# Factory function for backward compatibility`
- **Migration Path**: Per each issue's Proposed Fix.
- **Risk**: Maintenance only; every grep for "backward compatibility" keeps surfacing them.
- **Effort**: Small each
- **Verification**: `grep -rnE '\.scan_folder\(|scan_single_directory\(|create_psychoacoustic_eq\(' auralis auralis-web/backend` (non-def) → 0; `grep -rn "from .*queue_service import .*(QueueManager|AudioPlayerWithQueue)"` → 0; `grep -wn PlayEnhanced frontend/src` → 2 (definition + barrel).

### DEP-INT-3: `tokens.colors.bg` "Backwards compatibility" alias block — zero production consumers (missed sibling of #4402)
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis-web/frontend/src/design-system/tokens/colors.ts:31-36`
- **Status**: NEW (sibling of CLOSED #4402, which targeted the `// Legacy aliases` blocks at `colors.ts:112` and `effects.ts:98,113`. This `bg` block dates from `5ceaf5ed` (#4079, 2026-06-02), predates #4402 and was not touched by it, so it is not a regression)
- **Deprecated API**: `tokens.colors.bg.primary` / `.secondary` / `.tertiary` / `.elevated` / `.overlay` (duplicates of `bg.level0..level3` plus an rgba overlay)
- **Deprecated Since**: Internal — superseded by the `level0-4` scale (Design Language §2.1)
- **Removal Version**: n/a
- **Replacement**: `tokens.colors.bg.level0..level4`
- **Affected Files**: Production consumers 0 (all five aliases). Test: `src/theme/__tests__/darkOnlyTokenLeak.test.ts:149-152` pins four of them equal to `level0-3`. `bg.overlay`: 0 references anywhere. Canonical `level0-4` have 17 production references.
- **Evidence**:
  ```ts
  // colors.ts:30-36
  // Backwards compatibility
  primary: '#0B1020',
  secondary: '#101729',
  tertiary: '#151D2F',
  elevated: '#1A2338',
  overlay: 'rgba(11, 16, 32, 0.95)',
  ```
- **Migration Path**: Delete the five keys. Drop the four alias assertions in `darkOnlyTokenLeak.test.ts:146-152` (the comment there says the rewrites to `level*` already happened). Run `pnpm run type-check`.
- **Risk**: None functional. It is a second name for each surface level that a new component could pick up, which reintroduces drift.
- **Effort**: Small
- **Verification**: `grep -rnE "bg\.(primary|secondary|tertiary|elevated|overlay)\b|bg\[['\"](primary|...)"` over `src` and `scripts` → only the 4 test lines; no `Object.entries/keys(...bg)` iteration; `git log -S "// Backwards compatibility" -- src/design-system/tokens/colors.ts` → `5ceaf5ed`.

### DEP-INT-4: Playlist `modified_at` wire alias "for frontend compatibility" — the frontend never reads it
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/library/models/playlist.py:85-86`, `auralis-web/backend/schemas.py:340`
- **Status**: NEW
- **Deprecated API**: `Playlist.to_dict()['modified_at']` (duplicate of `updated_at`) and the `modified_at` field on the playlist response schema
- **Deprecated Since**: Internal (#2269-era alias)
- **Removal Version**: n/a
- **Replacement**: `updated_at` (already emitted alongside)
- **Affected Files**: Producers 2 (model + schema). Consumers: frontend `src/` **0** references to `modified_at` (tests included); backend/tests **0** playlist consumers. The `sidecar_manager.py` `modified_at` hits are an unrelated file-mtime key.
- **Evidence**:
  ```python
  # auralis/library/models/playlist.py:84-86
  'updated_at': self.updated_at.isoformat() if self.updated_at else None,
  # Alias for frontend compatibility — frontend Playlist type uses modified_at (fixes #2269)
  'modified_at': self.updated_at.isoformat() if self.updated_at else None,
  # auralis-web/backend/schemas.py:340
  modified_at: str | None = Field(default=None, description="Alias of updated_at")
  ```
- **Migration Path**: Remove the dict key and the schema field in one commit (frontend and backend ship as one Electron bundle, same rationale as #4975). Regenerate OpenAPI/TS types if generated.
- **Risk**: None. The comment's premise ("frontend Playlist type uses modified_at") is now false, which misleads the next reader.
- **Effort**: Small
- **Verification**: `grep -rn modified_at --include='*.ts' --include='*.tsx' auralis-web/frontend/src` → 0; `grep -rn modified_at --include='*.py' auralis-web/backend auralis tests` → only the two producers plus unrelated sidecar keys.

### DEP-INT-5: Frontend keeps a base64 PCM "legacy transport" branch the backend no longer emits
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis-web/frontend/src/utils/audio/pcmDecoding.ts:9,13,42-60,271,302-303`; `auralis-web/frontend/src/types/ws/streaming.ts:107,126-128`
- **Status**: NEW
- **Deprecated API**: `AudioChunkMessage.data.samples` (base64 float32 PCM) + `decodePCMBase64()` fallback in `decodeAudioChunkMessage()`
- **Deprecated Since**: Internal — binary WS transport (`audio_chunk_meta` + binary frame) replaced it (#2764 / #3944)
- **Removal Version**: n/a
- **Replacement**: `pcm_binary` ArrayBuffer path (`decodeBinaryPCM`)
- **Affected Files**: Backend producers of a `samples` key in any WS payload: **0**; backend base64 hits are only historical comments (`core/stream_protocol.py:149,180`). Frontend production: 1 fallback branch (`pcmDecoding.ts:302-303`), 1 exported decoder, 1 optional type field. Tests: `utils/audio/__tests__/pcmDecoding.test.ts` (5 `decodePCMBase64` cases).
- **Evidence**:
  ```ts
  // pcmDecoding.ts:300-306
  if (data.pcm_binary instanceof ArrayBuffer) {
    samples = decodeBinaryPCM(data.pcm_binary);
  } else if (data.samples && typeof data.samples === 'string') {
    samples = decodePCMBase64(data.samples);
  } ...
  // streaming.ts:107  "The `samples` base64 path remains for legacy clients only."
  ```
- **Migration Path**: Drop the base64 branch (throw on missing `pcm_binary`), delete `decodePCMBase64` and its tests, and remove `samples?: string` from `AudioChunkMessage`. There are no independently versioned "legacy clients" in a single Electron bundle.
- **Risk**: Low. The dead branch also hides a real protocol break: a malformed frame missing `pcm_binary` but carrying a stray string would be decoded as base64 garbage instead of failing loudly.
- **Effort**: Small
- **Verification**: `grep -rnE "['\"]samples['\"]" --include='*.py' auralis-web/backend` (non-test) → 0; `grep -rn decodePCMBase64 frontend/src` → definition, 1 internal call, tests.

### DEP-INT-6: `AudioStreamController._stream_type` — self-labelled "Deprecated" attribute, never read; tests still assign it
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:239` (and comment at :57)
- **Status**: NEW
- **Deprecated API**: `self._stream_type` instance attribute (replaced by the `_stream_type_var` ContextVar, #2493)
- **Deprecated Since**: #2493
- **Removal Version**: n/a
- **Replacement**: `_stream_type_var.get()` / `.set()`
- **Affected Files**: Production readers **0** (only the initializing assignment). Tests: `tests/backend/test_audio_stream_crossfade.py` assigns `controller._stream_type = "enhanced"` at 8 sites (65, 85, 105, 130, 166, 200, ...). The assignments have no effect, because production reads the ContextVar.
- **Evidence**:
  ```python
  # audio_stream_controller.py:239
  self._stream_type: str | None = None  # Deprecated; reads now use _stream_type_var.get() (fixes #2493)
  ```
- **Migration Path**: Delete the attribute. In the test file, replace the assignments with `_stream_type_var.set("enhanced")` if the stream type matters to the assertion, otherwise delete them.
- **Risk**: Tests that believe they set the stream type are not setting it, so a stream-type-dependent regression could pass unnoticed.
- **Effort**: Small (1 prod + 8 test sites)
- **Verification**: `grep -rnE "\._stream_type\b[^_]" --include='*.py' auralis auralis-web/backend tests`.

### DEP-INT-7: `ContentAnalyzer` "promotes fingerprint features to top level for backward compatibility" — all three promoted keys are unread
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/core/analysis/content_analyzer.py:151-155`
- **Status**: NEW
- **Deprecated API**: `content_profile["spectral_centroid_normalized"]`, `content_profile["lufs_fingerprint"]`, and the overwrite of `content_profile["crest_factor_db"]` with the fingerprint's `crest_db`
- **Deprecated Since**: Internal (25D fingerprint rollout)
- **Removal Version**: n/a
- **Replacement**: `content_profile["fingerprint"][...]` (already stored at :149)
- **Affected Files**: Readers of `spectral_centroid_normalized` / `lufs_fingerprint`: **0** (prod and tests). Readers of `content_profile["crest_factor_db"]` as a dict key: **0**. The `crest_factor_db` hits in `analysis/ml/*` and `dsp/utils/adaptive_loudness.py` are a different object/attribute.
- **Evidence**:
  ```python
  # content_analyzer.py:151-155
  # Promote key fingerprint features to top level for backward compatibility
  # This allows existing code to work while new code can use full fingerprint
  content_profile["spectral_centroid_normalized"] = fingerprint.get("spectral_centroid", 0.5)
  content_profile["crest_factor_db"] = fingerprint.get("crest_db", crest_factor_db)
  content_profile["lufs_fingerprint"] = fingerprint.get("lufs", content_profile["estimated_lufs"])
  ```
- **Migration Path**: Delete lines 151-155. Confirm with `grep -rn "spectral_centroid_normalized\|lufs_fingerprint"` → 0 afterwards. Note that the crest overwrite silently changes the key's provenance, from time-domain crest to fingerprint crest, depending on whether fingerprinting ran; removing it makes `crest_factor_db` consistent.
- **Risk**: None functional today (no readers). The overwrite is a latent inconsistency if a reader is ever added.
- **Effort**: Small
- **Verification**: `grep -rnE "spectral_centroid_normalized|lufs_fingerprint" auralis auralis-web tests scripts` → only the two writes; `grep -rnE "(content_profile|profile|analysis)(\[|\.get\()['\"]crest_factor_db"` → only the write.

### DEP-INT-8: `auralis.library.migrations` package re-exports `migration_manager` "for backward compatibility" — only importer is a never-collected validation script
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/library/migrations/__init__.py:12-22`
- **Status**: NEW
- **Deprecated API**: `from auralis.library.migrations import MigrationManager, backup_database, check_and_migrate_database`
- **Deprecated Since**: Internal (logic moved to `auralis/library/migration_manager.py`)
- **Removal Version**: n/a
- **Replacement**: `from auralis.library.migration_manager import ...`
- **Affected Files**: Production importers **0**. Only importer: `tests/validation/validate_version_system.py:38,97`, and `tests/validation` is in `pytest.ini` `norecursedirs` (and the file is not named `test_*.py`), so it is never collected. The re-export was even extended (`backup_database`) purely for that script.
- **Evidence**:
  ```python
  # auralis/library/migrations/__init__.py:12-20
  # Re-export from parent migration_manager.py for backward compatibility.
  from auralis.library.migration_manager import (MigrationManager, backup_database, check_and_migrate_database)
  ```
- **Migration Path**: Point `validate_version_system.py` at `auralis.library.migration_manager` (or delete the script if obsolete), then reduce `migrations/__init__.py` to its docstring.
- **Risk**: None; dead compat surface.
- **Effort**: Small
- **Verification**: `grep -rnE "from auralis\.library\.migrations import|from \.migrations import" --include='*.py' auralis auralis-web tests scripts`; `grep -n norecursedirs pytest.ini` → `tests/validation`.
- **Related**: #5149 (OPEN). The only importer lives in the never-collected `tests/validation/` tree.

### DEP-NODE-2: Deprecated transitive npm packages in both lockfiles
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `desktop/pnpm-lock.yaml:213,516,577,652,861`, `auralis-web/frontend/pnpm-lock.yaml:1748` (the tsconfck entry at :1614 is covered in DEP-NODE-3)
- **Status**: NEW (#4879 was about audit advisories, not deprecation flags)
- **Deprecated API** (pnpm `deprecated:` field → parent in the lockfile snapshot):
  - desktop `boolean@3.2.0` ("Package no longer supported") ← `global-agent@3.0.0`, `roarr@2.15.4` (Electron binary download / proxy chain; build time)
  - desktop `glob@7.2.3` ("Old versions of glob are not supported…") ← `@electron/asar@3.4.1`, `rimraf@2.6.3` (build time)
  - desktop `inflight@1.0.6` ("leaks memory. Do not use it") ← `glob@7.2.3` (build time)
  - desktop `rimraf@2.6.3` ("versions prior to v4 are no longer supported") ← `temp@0.9.4` (build time)
  - desktop `lodash.isequal@4.5.0` ("Use require('node:util').isDeepStrictEqual") ← `electron-updater@6.8.9`. **This one ships in the packaged app runtime.** electron-updater 6.8.9 is already the latest, so there is no upstream fix yet.
  - frontend `whatwg-encoding@3.1.1` ("Use @exodus/bytes instead") ← `jsdom@27.3.0`, `html-encoding-sniffer@4.0.0` (test only; latest jsdom is 30.0.1)
- **Deprecated Since**: flagged on the npm registry, as recorded in the lockfiles
- **Removal Version**: n/a (unmaintained)
- **Replacement**: bump the parents: jsdom to 28+/30, electron-builder/@electron/asar when upstream moves off glob 7. electron-updater has no fix available.
- **Affected Files**: 2 lockfiles. No direct dependency is itself deprecated.
- **Evidence**: `grep -n "deprecated:" desktop/pnpm-lock.yaml auralis-web/frontend/pnpm-lock.yaml` → 7 entries. Root `pnpm-lock.yaml` → 0.
- **Migration Path**: Upgrade jsdom when the vitest environment is next touched. Track electron-builder/electron-updater releases. No code change is possible now.
- **Risk**: Low. Everything except lodash.isequal is build- or test-time only. lodash.isequal is a pure function with no known advisory.
- **Effort**: Small
- **Verification**: awk over the lockfile `snapshots:` section to find each parent.

### DEP-NODE-3: `vite-tsconfig-paths` is an unused devDependency that pulls in the deprecated `tsconfck`
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/package.json:79`
- **Status**: NEW
- **Deprecated API**: `tsconfck@3.1.6` (lockfile: `deprecated: unmaintained`), the only dependent being `vite-tsconfig-paths@4.3.2`
- **Deprecated Since**: flagged on the npm registry
- **Removal Version**: n/a
- **Replacement**: delete the dependency. The `@` alias is already set by `resolve.alias` in `vite.config.mts` and `vitest.config.ts`. (Latest vite-tsconfig-paths is 6.1.1, and Vite 8 has native tsconfig path support, so upgrading instead makes no sense.)
- **Affected Files**: 1 manifest. 0 importers in `vite.config.mts`, `vitest.config.ts`, `vite.manualChunks.ts`, `scripts/` or `src/`.
- **Evidence**: `grep -rn "tsconfig-paths\|tsconfigPaths" auralis-web/frontend --exclude-dir=node_modules` → only `package.json:79`
- **Migration Path**: `pnpm remove vite-tsconfig-paths`. That also drops tsconfck from the lockfile.
- **Risk**: None. Unused.
- **Effort**: Small
- **Verification**: grep above. Lockfile snapshot `vite-tsconfig-paths@4.3.2 -> tsconfck: 3.1.6`.

### DEP-NODE-4: Vitest config uses `benchmark.outputFile`, deprecated in the installed Vitest 4.1.7, plus a redundant `/// <reference types="vitest" />`
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/vitest.config.ts:1`, `:112-116`
- **Status**: NEW (#2948/#2673/#3488 handled other vitest keys and are still fixed)
- **Deprecated API**: `test.benchmark.outputFile`. Separately, `/// <reference types="vitest" />` as a config-typing mechanism.
- **Deprecated Since**: Vitest 4.x (installed 4.1.7): `node_modules/vitest/dist/chunks/reporters.d.CtLUhkkA.d.ts:2557` `@deprecated Use \`benchmark.outputJson\` instead`. In 4.x only `vitest/dist/config.d.ts` augments `vite`'s `UserConfig`. The main `vitest` types no longer do, so the triple-slash reference adds nothing here (the file already imports `defineConfig` from `vitest/config`).
- **Removal Version**: next major (latest is Vitest 5.0.0; not checked whether 5.0 removed it)
- **Replacement**: `benchmark.outputJson: './test-results/bench.json'`. Delete line 1.
- **Affected Files**: 1 (config)
- **Evidence**: `vitest.config.ts:112` `benchmark: {` … `:115` `outputFile: './test-results/bench.json',`
- **Migration Path**: Rename the key. Remove the reference line. `pnpm run type-check` still covers `tsconfig.node.json`.
- **Risk**: Low. It only matters in `vitest bench` mode, and package.json has no bench script.
- **Effort**: Small
- **Verification**: installed d.ts `@deprecated` tag. `grep -ln "declare module ['\"]vite['\"]" node_modules/vitest/dist/*.d.ts` → only `config.d.ts`.

### DEP-NODE-5: Vite config keys deprecated in Vite 8 (upgrade roadmap)
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/vite.config.mts:118-123` (`esbuild`), `:127-135` (`build.rollupOptions` incl. `output.manualChunks`)
- **Status**: NEW
- **Deprecated API**: top-level `esbuild` option. `build.rollupOptions`.
- **Deprecated Since**: Vite 8.0. Neither is deprecated in the installed 7.3.5. vite@8.3.0 `dist/node/index.d.ts:3538` `@deprecated Use \`oxc\` option instead.` (esbuild) and `:2901` `@deprecated Use \`rolldownOptions\` instead.` (build.rollupOptions). Vite 8 bundles with Rolldown (`"rolldown": "~1.2.6"`).
- **Removal Version**: not announced (kept as aliases in 8.x)
- **Replacement**: `oxc: { … }` (console/debugger dropping needs the Oxc/Rolldown equivalent rather than a key rename), `build.rolldownOptions`. `manualChunks` (a function, `vite.manualChunks.ts`) is load-bearing for the custom `fix-vendor-loading-order` HTML plugin (#4697). Re-verify its semantics under Rolldown. Its deprecation status in Rolldown was not checked locally.
- **Affected Files**: 1 prod build config (+ `vite.manualChunks.ts` and `src/__tests__/viteChunking.test.ts` depend on the chunking contract)
- **Evidence**: `esbuild: { drop: mode === 'production' ? ['console', 'debugger'] : [] }`. `rollupOptions: { output: { manualChunks: vendorChunk, … } }`
- **Migration Path**: When moving to Vite 8 + `@vitejs/plugin-react` 6: rename to `rolldownOptions`, port the `drop` option to Oxc/minifier config, and re-run `viteChunking.test.ts` plus a packaged Electron smoke test (the loader-script race fix depends on the vendor chunk name).
- **Risk**: Nothing breaks on the installed version. On the upgrade there will be deprecation warnings, and possible chunk-name changes could break the vendor-first loader.
- **Effort**: Small
- **Verification**: `npm pack vite@8.3.0` into the scratchpad, then grep `@deprecated` in `dist/node/index.d.ts`. `pnpm view vite version` → 8.3.0.

### DEP-FE-1: `baseUrl` in tsconfig.json is deprecated in TypeScript 6.0 and stops working in 7.0
- **Severity**: LOW
- **Dimension**: React/Redux/MUI (tsconfig per spec Dimension 4)
- **Location**: `auralis-web/frontend/tsconfig.json` (`"baseUrl": "."`, "Path mapping" block). Inherited by `tsconfig.build.json`.
- **Status**: NEW (#2148 moduleResolution is still fixed: it is `bundler`)
- **Deprecated API**: `compilerOptions.baseUrl`
- **Deprecated Since**: TypeScript 6.0. typescript@6.0.3 `lib/typescript.js` `checkDeprecations("6.0", "7.0", …)` contains `if (options.baseUrl !== void 0) createDeprecatedDiagnostic("baseUrl", …)`. Installed is 5.9.3, so there is no diagnostic today.
- **Removal Version**: TypeScript 7.0 (latest on npm is 7.0.2)
- **Replacement**: delete `baseUrl`. `paths` entries resolve relative to the tsconfig and have not needed `baseUrl` since TS 4.1. `"@/*": ["./src/*"]` is already written relative.
- **Affected Files**: 1 config (applies to prod `type-check:prod` gate and tests)
- **Evidence**: `"baseUrl": ".", "paths": { "@/*": ["./src/*"] }`
- **Migration Path**: Remove the line. Run `pnpm run type-check:prod` (must stay 0) and `pnpm run type-check`.
- **Risk**: On TS 6 the deprecation diagnostic is an error unless `ignoreDeprecations: "6.0"` is set, so `frontend-typecheck.yml` would go red on the bump. On TS 7 the option is removed. The other options in the file are clear of the 6.0 table (`esModuleInterop`/`allowSyntheticDefaultImports` are `true`; `target` ES2020; `moduleResolution` bundler).
- **Effort**: Small (1 line)
- **Verification**: tarball grep above. `pnpm view typescript version` → 7.0.2.

### DEP-FE-2: Global `JSX` namespace, deprecated in @types/react 18.3 and removed in React 19 types
- **Severity**: LOW
- **Dimension**: React/Redux/MUI
- **Location**: `auralis-web/frontend/src/design-system/primitives/Box.tsx:6`. Tests: `src/components/core/__tests__/ErrorBoundary.test.tsx:20,24,105`.
- **Status**: NEW (#3483/#2677 JSX-runtime and React.FC cleanups are still fixed: 0 `React.FC` sites)
- **Deprecated API**: global `JSX.IntrinsicElements` / `JSX.Element`
- **Deprecated Since**: @types/react 18.3.x (installed 18.3.27): `node_modules/@types/react/index.d.ts:4348` `@deprecated Use \`React.JSX\` instead of the global \`JSX\` namespace.`
- **Removal Version**: @types/react 19 (the global namespace is gone). Latest react is 19.3.0.
- **Replacement**: `React.JSX.IntrinsicElements` / `React.JSX.Element` (`import type { JSX } from 'react'`)
- **Affected Files**: 2 files. Prod 1 (1 site). Test 1 (3 sites).
- **Evidence**: `Box.tsx:6` `as?: keyof JSX.IntrinsicElements;`. `ErrorBoundary.test.tsx:20` `function Boom(...): JSX.Element {`
- **Migration Path**: Add `import type { JSX } from 'react'` and leave the references as they are, or qualify them as `React.JSX`.
- **Risk**: No runtime effect. The prod type-check breaks on a React 19 types upgrade.
- **Effort**: Small (4 sites)
- **Verification**: `grep -rnE "\bJSX\." --include='*.ts' --include='*.tsx' src` → 4 sites. The @types/react d.ts tag is quoted above.

### DEP-CFG-1: mypy per-module overrides for backend services/cache use hyphenated module names and never match — the "strict" backend typing is inert
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pyproject.toml:146`, `pyproject.toml:151`, `pyproject.toml:167`
- **Status**: NEW
- **Deprecated API**: `[[tool.mypy.overrides]] module = "auralis-web.backend.services.*"` (and `.cache.*`, `.backend.*`). A mypy module pattern is a dotted *Python import name*; `auralis-web` contains a hyphen and cannot be one. Backend modules are imported as `services.*` / `cache.*` / `core.*` because `pytest.ini` / uvicorn put `auralis-web/backend` on `sys.path`.
- **Deprecated Since**: n/a (never valid)
- **Removal Version**: n/a
- **Replacement**: `module = ["services.*"]`, `["cache.*"]`, and a gradual-typing block for `["core.*", "routers.*", "config.*", ...]`, or run mypy with `mypy_path = "auralis-web/backend"` and `explicit_package_bases`.
- **Affected Files**: 1 (`pyproject.toml`, 3 override blocks). Also exercised through `.pre-commit-config.yaml` (mirrors-mypy hook reads the same config) and the `Makefile` `typecheck` target.
- **Evidence**:
  ```toml
  # pyproject.toml:144-147
  # Backend services type checking (strict - our new code)
  [[tool.mypy.overrides]]
  module = "auralis-web.backend.services.*"
  strict = true
  ```
  mypy itself reports it (installed mypy 2.3.0, `warn_unused_configs = true`):
  ```
  $ .venv/bin/mypy auralis/version.py
  pyproject.toml: note: unused section(s): module = ['auralis-web.backend.*', 'auralis-web.backend.cache.*', 'auralis-web.backend.services.*']
  ```
- **Migration Path**: 1) Decide the canonical import root for the backend (`auralis-web/backend` on the path). 2) Rewrite the three `module =` values to the real import names. 3) Run `mypy auralis-web/backend/services/` and triage the errors that strict mode will now surface (expect a non-trivial count — strictness has never actually applied). 4) Confirm the "unused section(s)" note disappears.
- **Risk**: No runtime impact. The comments claim backend services and cache get strict type checking, but they never have. Anyone relying on the pre-commit mypy hook for that guarantee is misled. No CI workflow runs mypy, which caps the severity.
- **Effort**: Small (3 config lines; follow-up type fixes may be Medium)
- **Verification**: ran mypy 2.3.0 from `.venv`; the "unused section(s)" note names all three blocks. `grep -n auralis-web.backend pyproject.toml`.

### DEP-CFG-2: `[coverage:run]` / `[coverage:report]` sections live in pytest.ini, which coverage.py never reads — `fail_under = 85` and `branch = true` are inert; plus dead pytest.ini entries
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pytest.ini:131-152` (coverage), `pytest.ini:12` (`norecursedirs`), `pytest.ini:107` (pyaudio filter)
- **Status**: NEW
- **Deprecated API**: coverage configuration in a file coverage.py does not search. coverage 7.15.3 `config_files_to_try()` searches `.coveragerc`, `.coveragerc.toml`, `setup.cfg`, `tox.ini`, `pyproject.toml` only. Neither coverage nor pytest-cov references `pytest.ini`.
- **Deprecated Since**: n/a (never effective)
- **Removal Version**: n/a
- **Replacement**: `[tool.coverage.run]` / `[tool.coverage.report]` in `pyproject.toml`.
- **Affected Files**: 1 (`pytest.ini`)
- **Evidence**:
  ```ini
  # pytest.ini:131-152
  [coverage:run]
  branch = true
  omit =
      */site-packages/*
      */distutils/*
      ...
      setup.py
  [coverage:report]
  ...
  fail_under = 85
  ```
  ```
  $ .venv/bin/python -c "import coverage; c=coverage.Coverage(); print(c.config.fail_under, c.config.branch, c.config.config_files_read)"
  fail_under= 0.0 branch= False files_read= ['/mnt/data/src/matchering/pyproject.toml']
  ```
  Siblings in the same file:
  - `norecursedirs = tests/validation tests/obsolete ...`: `tests/obsolete` does not exist.
  - `ignore::DeprecationWarning:pyaudio`: nothing in `auralis/`, `auralis-web/backend/` or `tests/` imports pyaudio.
  - The omit globs `*/distutils/*` and `setup.py` target a stdlib module removed in 3.12 and a file this repo does not have.
- **Migration Path**: 1) Move the two sections to `pyproject.toml` as `[tool.coverage.*]`. 2) Decide whether 85% is a real target; the suite has never been measured against it, so enabling it will probably fail any `--cov` run. Set it to the measured value or drop it. 3) Drop `tests/obsolete`, the pyaudio filter, and the `distutils`/`setup.py` omit globs.
- **Risk**: Tooling only. The 85% coverage floor and branch coverage look enforced but are not. Local `pytest --cov` runs silently use line coverage with no threshold.
- **Effort**: Small
- **Verification**: coverage 7.15.3 source `coverage/config.py:659-665`, a live `Coverage().config` probe, `ls tests/obsolete`, and `grep -rlE 'import pyaudio|from pyaudio' auralis auralis-web/backend tests` (0 hits).

### DEP-CFG-3: Makefile is stale end to end — targets invoke deleted scripts, a deleted Dockerfile, and bare `pip` in a uv-managed repo
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `Makefile:11-82` (whole file; last touched `18e0b009`, 2025-12-05)
- **Status**: NEW (related: #4903 CLOSED deleted the *Dockerfile* but left the `docker-build` target that consumes it)
- **Deprecated API**: build entry points retired from the repo:
  - *build_auralis.py*: targets `clean`, `build`, `build-fast`, `package`, `build-linux/windows/macos`
  - root *run_all_tests.py*: target `test`; it now lives at `scripts/run_all_tests.py`
  - *auralis_gui.py*: target `lint`
  - *Dockerfile*: target `docker-build`
  - *REPOSITORY_CLEANUP_SUMMARY.md*: target `docs`
  - `install`/`dev` use bare `pip install`, bypassing the uv toolchain; in a uv venv that falls through to the system pip.
- **Deprecated Since**: build path replaced by `auralis-web/backend/auralis-backend.spec` + `.github/workflows/build-release.yml` (PyInstaller/electron-builder); tooling moved pyenv/pip → uv 2026-07.
- **Removal Version**: already removed
- **Replacement**: `uv pip install -r requirements.txt` / `uv pip install -e '.[dev]'`, `python -m pytest` (scoped), the `build-release.yml` steps for packaging; delete `docker-build`.
- **Affected Files**: 1 (`Makefile`; 11 of its 14 targets fail)
- **Evidence**:
  ```make
  # Makefile:11-12, 21-22, 51, 74-76
  clean:		## Clean build artifacts
  	python build_auralis.py --clean
  test:		## Run test suite
  	python run_all_tests.py
  	python -m py_compile auralis_gui.py
  docker-build:	## Build using Docker
  	docker build -t auralis-builder .
  ```
  `ls build_auralis.py run_all_tests.py auralis_gui.py REPOSITORY_CLEANUP_SUMMARY.md Dockerfile` → all "No such file or directory".
- **Migration Path**: Delete the Makefile, or rewrite it as a thin wrapper over the commands in `CLAUDE.md` (uv venv, scoped pytest, `maturin develop`, `pnpm run dev`). Drop `docker-build` in either case; Auralis is desktop-only, so container build config should not come back.
- **Risk**: A contributor's first `make test` / `make build` / `make clean` fails with a missing-file error, and `make docker-build` suggests a container path that was deliberately retired. `make dev` can install into the system interpreter instead of `.venv`.
- **Effort**: Small
- **Verification**: `cat -n Makefile`, `ls` on every referenced file, `git log -1 -- Makefile`; dedup search for "Makefile" and "build_auralis" across all issues found nothing.

### DEP-CFG-4: `[tool.mutmut] paths_to_mutate` points at a file deleted in #4915; `tests/mutation/` is empty
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pyproject.toml:175-178`
- **Status**: NEW
- **Deprecated API**: `paths_to_mutate = "auralis/library/cache.py"`. The library cache layer went with the LibraryManager deletion (#4915) and the stub package removal (#5148).
- **Deprecated Since**: #4915
- **Removal Version**: already removed
- **Replacement**: point it at a live module worth mutation-testing, or delete the `[tool.mutmut]` block along with the empty `tests/mutation/` package and the `mutation` marker in `pytest.ini`.
- **Affected Files**: `pyproject.toml`; `tests/mutation/` holds only an `__init__.py`.
- **Evidence**:
  ```toml
  [tool.mutmut]
  paths_to_mutate = "auralis/library/cache.py"
  tests_dir = "tests/mutation/"
  ```
  `ls auralis/library/cache.py` → No such file or directory; `ls tests/mutation` → `__init__.py` only.
- **Migration Path**: remove the block (and the empty test package), or retarget it deliberately.
- **Risk**: None at runtime. A `mutmut run` fails immediately; the config documents a mutation-testing practice that no longer exists.
- **Effort**: Small
- **Verification**: `ls`; mutmut is not installed in `.venv` and no workflow calls it.

### DEP-CFG-5: Dev-dependency floors are older than the config that uses them (widens #4336)
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pyproject.toml:93`, `pyproject.toml:106-110`; `pytest.ini:4`, `pytest.ini:19`
- **Status**: Existing: #4336 (covers black/mypy). The siblings below are not in its body; add them to that issue rather than filing a new one.
- **Deprecated API**: floors that admit tool releases which cannot parse the repo's config:
  - `pytest-asyncio>=0.17.0`: `asyncio_default_fixture_loop_scope` (set at `pytest.ini:4`) was added in pytest-asyncio 0.24. With `--strict-config` (`pytest.ini:19`), any 0.17–0.23 install turns that key into an "unknown config option" error, so collection aborts.
  - `black>=22.0.0`, `mypy>=0.950`: already in #4336 (py314 target).
  - `pylint>=2.14.0`, `isort>=5.10.0`, `pre-commit>=2.17.0`: all predate Python 3.14.
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: floor at the versions `.pre-commit-config.yaml` already pins (black 26.5.1, isort 8.0.1, mypy 2.3.0, pylint 4.0.6), `pytest-asyncio>=0.24` (installed 1.4.0), `pre-commit>=4`.
- **Affected Files**: `pyproject.toml`
- **Evidence**:
  ```toml
  "pytest-asyncio>=0.17.0",   # pyproject.toml:93
  "black>=22.0.0",            # :106
  "mypy>=0.950",              # :108
  "pylint>=2.14.0",           # :109
  ```
  Installed in `.venv`: pytest-asyncio 1.4.0, black 26.5.1, mypy 2.3.0, pylint 4.0.6, isort 8.0.1, pre-commit 4.6.1.
- **Migration Path**: raise the floors in one edit, then confirm `requirements-pin-guard.yml` / `check_pyproject_deps.py` still pass.
- **Risk**: A fresh `uv pip install -e '.[dev]'` resolves the latest versions, so it only breaks under a constrained or backtracking resolve. Local dev only.
- **Effort**: Small
- **Verification**: `importlib.metadata` versions from `.venv`; `pytest.ini` contents.

### DEP-CFG-6: License declared only by a Trove classifier, deprecated by PEP 639
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pyproject.toml:20` (no `license` key under `[project]`)
- **Status**: NEW
- **Deprecated API**: `"License :: OSI Approved :: GNU Affero General Public License v3"` classifier as the sole license declaration.
- **Deprecated Since**: PEP 639 (core metadata 2.4; hatchling 1.27+, 2024-12)
- **Removal Version**: not scheduled. PEP 639 lets build tools warn or reject license classifiers when `license` is an SPDX expression.
- **Replacement**: `license = "AGPL-3.0-only"` (or `AGPL-3.0-or-later`, plus the commercial dual-license note elsewhere) and `license-files = ["LICENSE*", "COMMERCIAL_LICENSE.md"]`; delete the classifier.
- **Affected Files**: 1
- **Evidence**: `pyproject.toml:14-22` classifiers list; `grep -n '^license' pyproject.toml` → no match.
- **Migration Path**: add the SPDX `license` + `license-files`, then remove the License classifier. The two cannot coexist under hatchling's PEP 639 handling.
- **Risk**: None today (the wheel is not published to PyPI). Future hatchling/packaging releases may warn or fail on the classifier.
- **Effort**: Small
- **Verification**: pyproject read; PEP 639 "Deprecate license classifiers" section.

### DEP-RS-1: pyo3/numpy-rs 0.23 upgrade is correctly held, but its blocker evidence is stale — recorded against NumPy 2.3.x, while every manifest now pins NumPy 2.4.6
- **Severity**: LOW
- **Dimension**: Rust/PyO3
- **Location**: `vendor/auralis-dsp/Cargo.toml:17-18`; `vendor/auralis-dsp/.cargo/config.toml:23-29`; `vendor/auralis-dsp/UPGRADE_PLAN.md:11-24`; `pyproject.toml:46`; `.github/workflows/rust-audit.yml:78-80`
- **Status**: NEW (the upgrade plan came out of #4360, CLOSED; this finding covers the staleness of its premise, not a routine bump)
- **Deprecated API**: `pyo3 = 0.23` (0.23.5 locked) and `numpy = 0.23` (0.23.0), built with `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` because pyo3 0.23 caps at CPython 3.13. This is a **known-blocked upgrade**, not a stale pin: bumping to 0.29 was found to compile, but every array-accepting call then raised `TypeError: 'ndarray' object is not an instance of 'ndarray'`.
- **Deprecated Since**: pyo3 0.23 is several minors behind (0.24 through 0.29 released). Two advisories are `--ignore`d in `rust-audit.yml` (RUSTSEC-2025-0020, fixed in 0.24.1; RUSTSEC-2026-0177, fixed in 0.29), both assessed non-reachable.
- **Removal Version**: n/a
- **Replacement**: pyo3 ≥0.29 + matching numpy-rs, *once the ABI failure is re-checked against the current NumPy*.
- **Affected Files**: 1 source file uses the PyO3 surface (`vendor/auralis-dsp/src/py_bindings.rs`); 3 docs carry the stale premise.
- **Evidence**:
  - `.cargo/config.toml:25-26`: "...numpy-rs 0.29 targets NumPy's "ABI v2" and is incompatible with the NumPy 2.3.x pinned in requirements.txt."
  - `UPGRADE_PLAN.md:22-24`: "...against the NumPy 2.3.x we run on... Python 3.14 migration (still transitional)."
  - `UPGRADE_PLAN.md:11-12`: table says "Latest major available 0.25 / 0.26", while the blocked target discussed is 0.29.
  - `pyproject.toml:46`: "requirements.txt's `numpy==2.3.5` sits inside this range", sitting directly above `numpy>=2.4,<2.5`. 2.3.5 is not inside that range.
  - Actual pins: `requirements.txt:17`, `auralis-web/backend/requirements.txt:17` and `requirements-lock.txt:1016` are all `numpy==2.4.6`. The Python 3.14 migration finished on 2026-07-28.
- **Migration Path**:
  1. In a scratch git worktree (never git stash), bump `pyo3`/`numpy` to 0.29, `maturin develop` against NumPy 2.4.6, and call each array-accepting entry point in `py_bindings.rs` (`hpss`, `yin`, `chroma_cqt`, `compress`, `limit`, `apply_multiband_eq`, `process_chunks`, ...).
  2. If the ABI error persists, update the three docs to say "reproduced against NumPy 2.4.6 on <date>" and fix the table and the pyproject comment.
  3. If it is gone, plan the API migration: pyo3 0.26+ renames `Python::with_gil` → `attach` and `py.allow_threads` → `detach` (7 `allow_threads` sites in `py_bindings.rs`), deprecates the `PyObject` alias in favour of `Py<PyAny>` (2 return types), and switches to `IntoPyObject`. Then remove the forward-compat env var and both `--ignore` flags.
- **Risk**: The blocker may already be gone or may have changed shape, so the crate could stay on an advisory-carrying pyo3 longer than needed. The forward-compat flag also forces a limited-API build and rules out free-threaded 3.14t (#4911/#4962).
- **Effort**: Small (verification) / Medium (the actual bump, ~20 PyO3 call sites)
- **Verification**: `Cargo.lock` versions, grep of `py_bindings.rs`, manifest numpy pins, `rust-audit.yml` ignore list. The 0.29 bump was **not** attempted here (read-only audit).

### DEP-RS-2: Crate still on Rust edition 2021 while the pinned toolchain (1.96.0) supports edition 2024
- **Severity**: LOW
- **Dimension**: Rust/PyO3
- **Location**: `vendor/auralis-dsp/Cargo.toml:4`, `vendor/auralis-dsp/Cargo.toml:11` (`rust-version = "1.80"`), `vendor/auralis-dsp/rust-toolchain.toml`
- **Status**: NEW
- **Deprecated API**: `edition = "2021"` (superseded by edition 2024, stable since Rust 1.85, 2025-02)
- **Deprecated Since**: Rust 1.85
- **Removal Version**: editions are never removed; 2021 stays supported.
- **Replacement**: `edition = "2024"` with `rust-version = "1.85"` (or higher), via `cargo fix --edition`.
- **Affected Files**: 1 manifest; 19 `src/*.rs` get checked by `cargo fix --edition`.
- **Evidence**: `edition = "2021"`; `rust-toolchain.toml` → `channel = "1.96.0"`.
- **Migration Path**: `cargo fix --edition` → set `edition = "2024"`, bump `rust-version` to ≥1.85 → `cargo check --all-targets` → rebuild with `maturin develop` → run the Rust DSP test files. Watch for the 2024 `unsafe extern`, RPIT lifetime-capture and `gen` keyword changes. PyO3 0.23 macros are 2024-compatible.
- **Risk**: None now. Purely forward hygiene: 2024-edition lints and idioms are unavailable.
- **Effort**: Small
- **Verification**: `cargo check --all-targets` on toolchain 1.96.0 finished with 0 deprecation warnings (only 5 unused-variable warnings, see below).

## Dependency Upgrade Roadmap

| Order | Upgrade | Installed → available | Prerequisites (findings) | What breaks / changes |
|---|---|---|---|---|
| 0 | *(no upgrade)* restore gates and tooling truth | — | DEP-INT-1, DEP-API-2, DEP-CFG-1, DEP-CFG-2, DEP-CFG-3, DEP-CFG-4 | Backend ratchet goes back to judging real regressions. Strict mypy on backend services/cache will surface a backlog of type errors the first time it actually applies. |
| 1 | pnpm `packageManager` | 10.20.0 → 12.4.1 | DEP-NODE-1 | Without moving `overrides` to `pnpm-workspace.yaml`, the security pins (rollup, fast-uri, js-yaml, app-builder-lib) stop applying. CI `--frozen-lockfile` fails on the config mismatch, and a local non-frozen install silently re-resolves without them. |
| 2 | TypeScript | 5.9.3 → 6.0.3 / 7.0.2 | DEP-FE-1 | TS 6: the `baseUrl` deprecation diagnostic fails `type-check:prod` unless `ignoreDeprecations: "6.0"` is set. TS 7: the option is removed. |
| 3 | Vite + @vitejs/plugin-react | 7.3.5 / 5.1.2 → 8.3.0 / 6.1.1 | DEP-NODE-5, DEP-NODE-3 | Rolldown bundler; `esbuild` → `oxc`, `build.rollupOptions` → `rolldownOptions`. The `manualChunks` vendor-first loader (#4697) must be re-verified with `viteChunking.test.ts` and a packaged smoke test. |
| 4 | Vitest | 4.1.7 → 5.0.0 | DEP-NODE-4 | `benchmark.outputFile` → `outputJson`. The 5.0 breaking changes were not assessed. |
| 5 | React / @types/react | 18.3.1 → 19.3.0 | DEP-FE-2 | Global `JSX` namespace removed (4 sites). `forwardRef` becomes optional (16 prod sites, not breaking). |
| 6 | jsdom | 27.3.0 → 30.0.1 | DEP-NODE-2 | Drops deprecated `whatwg-encoding` (test-only). |
| 7 | librosa | 0.11.0 → 1.0.0 | DEP-NP-1 | audioread backend removed: any non-soundfile decode through `librosa.load` becomes a hard error. `note_to_hz` default quantization removed; YIN accuracy changes (Rust YIN validation tests). The `standard-aifc`/`standard-sunau`/`audioop-lts` backports and the two `pytest.ini` ignores can then go. |
| 8 | NumPy | 2.4.6 → 2.5.3 | numba ≥0.67 (check its numpy ceiling), then relax `pyproject.toml` `<2.5` | The resolver backtracking failure documented at `pyproject.toml:37-48` if relaxed first. |
| 9 | pyo3 + numpy-rs | 0.23.5 / 0.23.0 → 0.29 | DEP-RS-1 (re-verify ABI failure against NumPy 2.4.6 in a git worktree) | If cleared: `allow_threads` → `detach`, `with_gil` → `attach`, `PyObject` → `Py<PyAny>`; remove `PYO3_USE_ABI3_FORWARD_COMPATIBILITY`, both `cargo audit --ignore`s, and the limited-API/free-threaded restriction. If not cleared: update the evidence in `.cargo/config.toml`, `UPGRADE_PLAN.md` and `pyproject.toml`. |
| 10 | Rust edition | 2021 → 2024 | DEP-RS-2 (after 9, to avoid a double churn of `py_bindings.rs`) | `rust-version` must rise to ≥1.85 (toolchain already 1.96.0). |
| — | FastAPI 0.141.1 / Starlette 1.3.1 / Pydantic 2.13.4 / SQLAlchemy 2.0.51 / uvicorn 0.52.1 | current pins | none | Production is 2.0/V2-native with 0 import-time warnings. SQLAlchemy 2.1 is test-only work (#4333). |
| — | Electron | 43.2.0 → 44.3.0 | none | No deprecated Electron API in use. |
| — | MUI | 9.0.1 → 9.4.0 | none | Minor. No deprecated props in use. |
| — | Python forward hygiene (3.14 → 3.15+) | — | DEP-PY-2, DEP-PY-3, DEP-PY-4, DEP-NP-2 | Nothing breaks today. `from __future__ import annotations` is slated for deprecation after 3.13 EOL (PEP 749). soundfile `__len__` removal is unscheduled. |

## Migration Effort Estimate

| Finding | Severity | Effort | Call sites |
|---|---|---|---|
| DEP-INT-1 | MEDIUM | Small | 4 collected test files / 13 tests (+3 uncollected validation scripts, 1 docstring) |
| DEP-NODE-1 | MEDIUM | Small | 2 manifests / 5 override entries |
| DEP-PY-1 | LOW | Small | 3 prod imports |
| DEP-PY-2 | LOW | Medium | 11 prod + 6 test |
| DEP-PY-3 | LOW | Large | 59 prod + 69 test/scripts modules |
| DEP-PY-4 | LOW | Small | 1 prod |
| DEP-PY-5 | LOW | Small | 2 test |
| DEP-PY-6 | LOW | Medium | 14–16 test files (#4624) |
| DEP-NP-1 | LOW | Small | 4 prod files (librosa decode/resample call sites) |
| DEP-NP-2 | LOW | Small | 3 prod + 2 test |
| DEP-NP-3 | LOW | Small | 1 prod |
| DEP-API-1 | LOW | Medium | 50 test sites / 15 files + 2 dev-script sites (#4333) |
| DEP-API-2 | LOW | Small | 1 test |
| DEP-INT-2 | LOW | Small each | 7 open issues (see table in finding) |
| DEP-INT-3 | LOW | Small | 5 token keys + 4 test assertions |
| DEP-INT-4 | LOW | Small | 2 producers |
| DEP-INT-5 | LOW | Small | 1 prod branch + 1 decoder + 1 type field + 5 tests |
| DEP-INT-6 | LOW | Small | 1 prod + 8 test |
| DEP-INT-7 | LOW | Small | 3 lines |
| DEP-INT-8 | LOW | Small | 1 re-export module + 1 script |
| DEP-NODE-2 | LOW | Small | 2 lockfiles (transitive only) |
| DEP-NODE-3 | LOW | Small | 1 devDependency |
| DEP-NODE-4 | LOW | Small | 1 config key + 1 line |
| DEP-NODE-5 | LOW | Small | 2 config keys |
| DEP-FE-1 | LOW | Small | 1 tsconfig line |
| DEP-FE-2 | LOW | Small | 1 prod + 3 test |
| DEP-CFG-1 | LOW | Small (config) / Medium (type fixes it unlocks) | 3 override blocks |
| DEP-CFG-2 | LOW | Small | 2 ini sections + 3 dead entries |
| DEP-CFG-3 | LOW | Small | 1 Makefile (11 of 14 targets broken) |
| DEP-CFG-4 | LOW | Small | 1 config block |
| DEP-CFG-5 | LOW | Small | 6 dependency floors (#4336) |
| DEP-CFG-6 | LOW | Small | 1 classifier |
| DEP-RS-1 | LOW | Small (verify) / Medium (bump, ~20 PyO3 sites) | 1 source file, 3 docs |
| DEP-RS-2 | LOW | Small | 1 manifest |

## Checked and Clean

Each item below was verified against the current tree, with the grep or probe used stated inline. A reappearance of any of these patterns is a regression.

### Python Stdlib + NumPy/SciPy/Audio (Dimensions 1-2)

Python stdlib / language (grep scope `auralis auralis-web/backend tests scripts *.py`, `--include='*.py'`):
- `datetime.utcnow()` / `utcfromtimestamp()`: 0 (`'utcnow\(|utcfromtimestamp\('`). #2140 and #2678 fixes hold.
- `asyncio.get_event_loop()` / `set_event_loop()`: 0. Event-loop policy APIs (`get/set_event_loop_policy`, `*EventLoopPolicy`): 0. #4332 and #2145 fixes hold.
- `asyncio.iscoroutinefunction`: 0 (#4957 fix holds). `@asyncio.coroutine` / `types.coroutine`: 0. Child-watcher APIs (removed 3.14): 0. `loop=` kwargs on asyncio primitives: 0; the 4 `loop=` hits are the project's own `_DebounceHandler`.
- `pkg_resources`: 0. `distutils`: 0. `imp`: 0. Removed PEP 594 modules imported directly (`asynchat|asyncore|smtpd|imghdr|sndhdr|audioop|aifc|sunau|chunk|cgi|cgitb|crypt|nntplib|pipes|telnetlib|uu|xdrlib|msilib|nis|spwd|mailcap|ossaudiodev|lib2to3`, anchored `^\s*(import|from)`): 0. The only indirect use is via audioread (DEP-NP-1).
- unittest deprecated aliases (`assertEquals|assertNotEquals|assertItemsEqual|assertRegexpMatches|assertDictContainsSubset|failUnless|assert_(`): 0. `unittest.makeSuite|findTestCases|getTestCaseNames`: 0.
- `configparser` `readfp` / `has_key`: 0.
- ABCs from `collections` instead of `collections.abc`: 0. `typing.ByteString` / `collections.abc.ByteString` / `typing.Text`: 0.
- Thread `daemon` set after `start()` / `setDaemon|isDaemon|currentThread|activeCount|getName|setName`: 0. All 28 daemon uses are `Thread(..., daemon=True)` constructor kwargs.
- `ssl.PROTOCOL_*` / `ssl.wrap_socket`: 0.
- `locale.getdefaultlocale` / `locale.format` / `locale.resetlocale`: 0; no `locale.` usage at all.
- `typing.no_type_check_decorator`: 0. `ast.Num/Str/Bytes/NameConstant/Ellipsis`: 0.
- `tarfile` / `zipfile` extraction without `filter=` (3.14 default change): 0; neither module is used.
- `shutil.rmtree(..., onerror=)`: 0 (60 `rmtree` calls, none pass `onerror`).
- `PurePath.is_reserved`: 0. `relative_to` / `is_relative_to` with extra positional args (removed 3.14): 0.
- `codecs.open` (deprecated 3.14): 0.
- `pkgutil.find_loader` / `get_loader`: 0. `importlib.abc.ResourceReader` / `importlib.abc.Traversable`: 0. Legacy `importlib.resources.open_text|read_text|path|contents|is_resource`: 0.
- `os.popen`: 0. `os.fork` / `pty`: 0 (the "empty" grep hits were substring false positives).
- Multiprocessing `fork`→`forkserver` default (3.14): production uses `multiprocessing` only for `mp.cpu_count()` (`auralis/optimization/config.py:28`); there is no `ProcessPoolExecutor` or `Process` in production (#4939 closed; `parallel_processor` retired). The test `ProcessPoolExecutor` uses in `tests/concurrency/test_parallel_processing.py` that submit local closures are already `xfail(strict=True)` under #5188 for picklability; that failure is independent of start method. The explicit `get_context("spawn")` tests are unaffected.
- `functools.partial` as a class-attribute method descriptor (FutureWarning 3.13): 0; the 2 production uses are direct calls (`executors.py:127`, `stream_track_resolution.py:73`).
- `re.sub/subn/split` with positional `count`/`flags` (deprecated 3.13): 0; all 24 calls pass `count=` / `flags=` by keyword.
- `sqlite3` default datetime adapters/converters (deprecated 3.12): 0. Raw `sqlite3` in `fingerprint/catalog.py` stores `datetime.now(UTC).isoformat()` strings; `migration_backup.py` uses the backup API only.
- `logging.warn` / `Logger.warn`: 0. `Condition.notifyAll` / `Event.isSet`: 0. `abc.abstractproperty/abstractclassmethod/abstractstaticmethod`: 0. `inspect.getargspec/formatargspec/getcallargs`: 0.
- `array.array('u')`: 0. `co_lnotab`: 0. `xml.etree.cElementTree` / `getchildren` / `getiterator` / Element truth-testing: 0 (`xspf_handler.py` uses `find()` results without bool tests on Elements).
- `json.loads(..., encoding=)` (removed 3.9): 0; the 2 grep hits are `Path.read_text(encoding=...)`.
- `datetime.strptime` without a year (3.13 deprecation): 0 (no `strptime`). `argparse.FileType` (deprecated 3.14): 0.
- `NotImplemented` in boolean context (TypeError in 3.14): 0 (`return NotImplemented` has 0 hits).
- `os.path` vs `pathlib`: production has only 5 functional `os.path` calls (`path_key.py:72`, `scanner.py:179`, `database.py:104`, `routers/enhancement.py:266`, plus docstrings). The `normpath`/`realpath` string-normalisation uses are deliberate (`path_key.py:17` explains why). Not reported.
- `IOError` / `EnvironmentError`: 0 in production; 3 in `scripts/` (`analyze_feedback.py:46`, `update_profile.py:84,113`). They are aliases of `OSError`, not formally deprecated. Not reported.
- `socket.timeout` (deprecated alias): 0 in production, 7 in tests.

NumPy (installed 2.4.6; runtime-probed with `warnings.simplefilter("always")`):
- Removed scalar aliases `np.bool|int|float|complex|object|str|long|unicode` (non-suffixed): 0 code hits (1 docstring in `tests/test_pyproject_dependencies_4528.py:102`).
- NumPy 2.0 removed aliases `np.float_|complex_|NaN|Inf|NINF|PINF|NZERO|PZERO|infty|Infinity|string_|unicode_|int0|uint0|bool8|object0|longfloat|singlecomplex|cfloat|longcomplex|clongfloat`: 0.
- Removed/deprecated functions `np.cast|round_|asfarray|find_common_type|product|cumproduct|sometrue|alltrue|in1d|row_stack|msort|trapz|asscalar|alen|safe_eval|set_string_function|issubclass_|issctype|obj2sctype|sctype2char|sctypes|maximum_sctype|deprecate|disp|fastCopyAndTranspose|geterrobj|seterrobj|recfromcsv|recfromtxt|who|source|lookfor|byte_bounds|compare_chararrays|format_parser|mat|DataSource`: 0. Probes confirm `np.trapz`, `np.in1d` and `np.product` raise `AttributeError` and `np.row_stack` warns, so none of these would work if present.
- `np.core.*` / `numpy.core` / `np.linalg.linalg` / `np.lib.<private submodule>`: 0.
- Exception classes from old locations (`AxisError|ComplexWarning|VisibleDeprecationWarning|RankWarning|TooHardError`): 0.
- `ndarray.ptp()` (removed 2.0): 0. The 2 production hits are the function `np.ptp(...)` (`analysis/dynamic_range.py:210,369`), which is supported. `.newbyteorder()` / `.itemset()` / `ndarray.tostring()`: 0 (the `ET.tostring` hit is XML). `.setflags(write=False)` at `dsp/eq/curves.py:43` is valid.
- `np.array(..., copy=False)` (ValueError in 2.x when a copy is needed): 0. All 12 production `copy=False` uses are `ndarray.astype(..., copy=False)`, which is unchanged in 2.x (probe OK).
- `np.reshape(newshape=)` (removed 2.4): 0. `np.save(fix_imports=)`: 0.
- Setting `arr.strides` (deprecated 2.4) / `arr.shape =` / `arr.dtype =`: 0.
- `np.sum(generator)` (TypeError in 2.4): 0 (the one grep hit, `ml/feature_extractor.py:139`, is an array expression). Deprecated dtype string `'a'`: 0 (dtype grep hits were f-string log messages).
- Every `np.<name>` referenced in production was harvested (108 names) and resolved against numpy 2.4.6. None are missing and none carry a deprecation in their docstring. The one "missing" name, `np.float64_scalar`, is text inside a comment at `core/processing/base/peak_management.py:95`.
- `np.random` legacy global API in production: 0 functional (docstring examples in `core/dsp/parallel_eq.py` only; `ml/genre_weights.py` uses `default_rng`).
- Runtime sweep: importing all `auralis.*` modules via `pkgutil.walk_packages` produced 0 Deprecation/PendingDeprecation/FutureWarnings and 0 import failures. Scoped runs of `tests/auralis/core/test_master_file_mono_input.py`, `tests/test_fingerprint_unification_4595.py` and `tests/auralis/analysis/test_mastering_evaluation.py` (26 passed) with warnings forced on showed only the audioread `aifc`/`sunau` warnings in DEP-NP-1. There were no ndim>0-to-scalar conversion warnings and no NEP-50 warnings.

SciPy (installed 1.18.0):
- `scipy.fftpack`: 0 (production uses `scipy.fft`).
- Window functions from the `scipy.signal` namespace (`signal.hann/hamming/...`, removed 1.13): 0; production imports from `scipy.signal.windows` (5 sites) or uses `signal.get_window` (`analysis/spectrum_operations.py:59`, supported).
- `scipy.integrate.simps|cumtrapz|trapz|romberg|quadrature`: 0. `scipy.misc`: 0. `interp2d`: 0. `sph_harm`: 0. `signal.cwt|ricker|morlet|morlet2|qmf|bspline|cubic|quadratic|spline_filter|lsim2|impulse2|step2`: 0.
- Private or deprecated submodule namespaces (`scipy.signal.signaltools|filter_design|...`, `scipy.ndimage.filters|...`, `scipy.stats.stats|morestats`, `scipy.linalg.basic|decomp`): 0.
- `binom_test|itemfreq|pinv2`: 0. `interp1d` (legacy): 0.
- Every SciPy attribute used in production was probed: `ndimage.maximum_filter1d, signal.butter, csd, filtfilt, find_peaks, get_window, hilbert, lfilter, lfilter_zi, resample_poly, savgol_filter, welch, sosfilt, sosfiltfilt, tf2sos, windows.hann/hamming, fft.fft/ifft/rfft/rfftfreq`. All exist, none carry a deprecated/legacy docstring note, and none warn at runtime. `signal.stft/istft/spectrogram` (legacy vs `ShortTimeFFT`, not deprecated) are not used in production.

Audio libraries:
- librosa production API surface (`load, resample, stft, feature.spectral_centroid/bandwidth/rolloff, feature.zero_crossing_rate, amplitude_to_db`) contains none of the 0.11 `@deprecated` symbols (`filters.constant_q`, `filters.constant_q_lengths`, `set_fftlib`, `__audioread_load` beyond DEP-NP-1). No `rename_kw` legacy keywords are used (`get_duration(filename=)`, `stream(filename=)`: 0). No `yin(win_length=)`.
- soundfile 0.14.0: beyond `__len__` (DEP-NP-2), the only in-source deprecation notes are `__bool__` / `__nonzero__`, which the code does not use on SoundFile handles. `sf.read/write/info/SoundFile/available_subtypes/check_format` are all current.
- resampy 0.4.3 (latest): imports cleanly with no warnings, no `pkg_resources`; only used behind `try/except ImportError` in `auralis/io/processing.py:22-40`.
- pyloudnorm, pydub, pyaudio, pedalboard, torch: not installed and not imported in production.
- mutagen 1.48.1: imports cleanly with no warnings; no deprecated API usage found.

### FastAPI/Pydantic/SQLAlchemy + Internal (Dimensions 3, 7)

#### Dimension 3
- Pydantic V1 `class Config:` — 0 (`grep -rnE "^\s+class Config\b" auralis auralis-web/backend scripts desktop tests`); all models use `model_config = ConfigDict(...)` or a dict literal.
- `.dict()` / `.json()` on models — 0 in production (`grep -E "\.dict\("`; `.json()` hits are all HTTP response objects).
- `.parse_obj` / `.parse_raw` / `.parse_file` / `.from_orm` / `.schema_json` / `.update_forward_refs` / `.construct(` / `__fields__` / `.copy(update=|deep=|include=|exclude=)` — 0.
- `validator` / `root_validator` imports — 0 (only prose "validator" in comments); `field_validator` / `model_validator` used.
- `schema_extra`, `orm_mode`, `allow_population_by_field_name`, `populate_by_name`, `min_items`, `max_items`, `unique_items`, `const=`, `allow_mutation`, `smart_union`, `json_encoders`, `pydantic.v1`, `BaseSettings` — 0 in production (`populate_by_name` only in #4960's regression-test docstring; `metadata.py:55` uses `validate_by_name` / `validate_by_alias`).
- `regex=` (Field / Query / Path) — 0; `example=` / `examples=` in Query/Path/Body — 0.
- Instance access to `model_fields` (deprecated 2.11) — 0 in production (`routers/files.py:390` is class access `ProcessingSettings.model_fields`; test helpers access it on classes).
- `@app.on_event` / `on_startup` / `on_shutdown` / `add_event_handler` — 0; `main.py:183-186` uses `create_lifespan` → `FastAPI(lifespan=...)`.
- `HTTP_422_UNPROCESSABLE_ENTITY`, `HTTP_413_REQUEST_ENTITY_TOO_LARGE`, `HTTP_414_REQUEST_URI_TOO_LONG`, `HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE`, `WS_1004/1005` names — 0 (production uses numeric `status_code=422` at `processing_api.py:340`, `config/app.py:100`; only `status.HTTP_404/405` constants used).
- `ORJSONResponse` / `UJSONResponse` / `TemplateResponse` / `Jinja2Templates` / `WSGIMiddleware` — 0.
- `jsonable_encoder(sqlalchemy_safe=|custom_encoder=)` — 0.
- Starlette direct imports (`BaseHTTPMiddleware`, `TrustedHostMiddleware`, `Request`, `JSONResponse`, `Response`, `routing.Match`, `WebSocketState`) — all still supported in starlette 1.3.1; `websocket.client_state` usage OK.
- `declarative_base()` / `sqlalchemy.ext.declarative` — 0; `models/base.py:20` `class Base(DeclarativeBase)`.
- `Column()` in ORM classes — 0; the 7 `Column(` hits are Core `Table()` association-table definitions in `models/base.py:28-52` (correct 2.0 usage). 157 `mapped_column`, 178 `Mapped[`.
- `relationship()` without `Mapped[]` — 0 (all 15 relationships annotated); `backref=`, `lazy='dynamic'`, `cascade_backrefs`, `with_parent`, `from_self`, `select([...])`, `as_scalar()` — 0 (`scalar_subquery()` used).
- `Query.get()` — 0; `engine.execute` / `engine.table_names` / `has_table` / `run_callable` / `contextual_connect` — 0.
- `autoload=` / `autoload_with` / `MetaData(bind=)` / `Session(autocommit=True)` / `future=True` — 0. `sessionmaker(bind=engine)` (keyword form, still valid in 2.0) only in tests/scripts; production uses positional `sessionmaker(engine)`. `sessionmaker(autocommit=False)` in `scripts/development/test_phase5_scenario_a.py:97` is accepted (`Literal[False]`), no warning.
- String loader options (`selectinload("rel")`) — 0; `bulk_insert_mappings` / `bulk_update_mappings` — 0 (`bulk_save_objects` 1 test site, folded into DEP-API-1).
- `datetime.utcnow` / `utcfromtimestamp` in Column defaults or anywhere — 0; model defaults use `lambda: datetime.now(timezone.utc)` (`models/base.py:60-61`, `schema.py:28`, `queue.py:51`).
- `create_engine` legacy kwargs (`convert_unicode`, `encoding`, `strategy`, `case_sensitive`) — 0.

#### Dimension 7
- `warnings.warn(...)` / `DeprecationWarning` emission in shipped code (`auralis/`, `auralis-web/backend/`, `vendor/auralis-dsp/src`, `desktop/` excluding ignored `desktop/resources/`) — 0.
- JSDoc `@deprecated` / `console.warn(...deprecat...)` in `auralis-web/frontend/src` — 0.
- `TODO|FIXME` mentioning migrate/remove/deprecate/legacy/compat/sunset — 0 in shipped code (`grep -rniE "TODO.*(migrat|remov|deprecat|legacy|compat|sunset)"`).
- Removed enhancement preset names accepted/emitted by any production surface — 0 (see DEP-INT-1 for the verified surfaces); only deliberate survivors remain.
- Old config keys accepted: only `metadata.py:46-47` `Field(alias="track_number"/"disc_number")` (current V2 alias mechanism, #4960 fixed); no `AliasChoices` / `validation_alias` dual-name acceptance elsewhere.
- Checked and NOT dead (live callers, not reported): `unified_loader` `SUPPORTED_FORMATS`/`FFMPEG_FORMATS` re-export (prod importers `routers/files.py:79`, `core/stream_normal.py:120`); `dsp/advanced_dynamics.py` re-export (prod importers `core/hybrid_processor.py:19`, `core/hybrid/dynamics_manager.py:13`); `ChunkedAudioProcessor.chunk_rms_history` / `chunk_gain_history` "legacy mirrors" (prod reader `core/stream_chunk_ops.py:150`); `ProcessingEngine.job_queue` (prod use `processing_engine.py:195,376`); `ChunkedAudioProcessor.duration` alias (7 prod readers in `stream_seek.py` / `stream_enhanced.py`); `HybridProcessor.current_user_id` (read by `target_generator.py:60`); `stream_chunk_ops.process_and_stream_chunk` "legacy entry point" (called by `audio_stream_controller.py:352`); `QueueController.set_queue` / `clear` (verified live per #4973's note); `fingerprint_repository.__all__` re-exports (documented test contract, #5209).
- Deliberately kept, not re-reported: `useQueueFetch.ts:51-62` phantom `currentIndex` / `is_shuffled` / `isShuffled` fallbacks (#4787 decision); `BufferScheduler.ts:250-288` ScriptProcessorNode fallback (#4623); `use_continuous_space=False` AdaptiveMode path (documented keep at `adaptive_mode.py:38-42`); `TrackCard` / `AlbumCard` wrappers (live components, "backwards compatibility" is prose only).
- `desktop/resources/auralis/**` contains stale copies of shims deleted upstream (e.g. `base_spectrum_analyzer` wrappers, `library_manager` params), but it is gitignored (`.gitignore:158`, `git ls-files desktop/resources` → 0), so it is a build artifact and not reported.
- `requirements.txt` vs `pyproject.toml` runtime deps — consistent: `python .github/scripts/check_pyproject_deps.py` → "OK: pyproject.toml declares 15 runtime dependencies, consistent with requirements.txt (4 documented exceptions)".

### React/Redux/MUI + Node/npm/Build (Dimensions 4-5)

- `ReactDOM.render` / `hydrate` / `unmountComponentAtNode` / `renderToNodeStream`: 0 (`grep -rnE 'ReactDOM\.render\(|hydrate\(|unmountComponentAtNode|renderToNodeStream' src`). Entry uses `createRoot` (1 prod site).
- `componentWillMount/ReceiveProps/Update`, `UNSAFE_*`: 0 (`grep -rnE 'componentWill(Mount|ReceiveProps|Update)|UNSAFE_' src`).
- `findDOMNode`: 0.
- `defaultProps` on components: 0. All 55 `.defaultProps` hits are spreads of a local test variable named `defaultProps` (`{...defaultProps}`) in 4 test files. There is no `X.defaultProps =` assignment.
- `propTypes`/`PropTypes`: 0. String refs: 0 (the one `ref="` hit is `href="` inside an XSS test string). Legacy `contextTypes`/`childContextTypes`: 0.
- `act` from `react-dom/test-utils`: 0 (#3486 still fixed). `act` imports come from `react` (3), `@testing-library/react` (68), and `@/test/test-utils` (1). `react-test-renderer`, `Simulate`, `renderIntoDocument`: 0.
- react-redux `connect()` HOC: 0. All 28 `connect(` hits are WebAudio `node.connect()` or the WebSocket manager. `batch`, `TypedUseSelectorHook`, `DefaultRootState`: 0.
- `createStore`/`legacy_createStore` from redux: 0. The test hits are local helpers named `createStore` wrapping `configureStore`. `getDefaultMiddleware` import: 0; all hits are the `middleware: (getDefaultMiddleware) =>` callback parameter (RTK 2 form). `extraReducers` object notation: 0. `AnyAction`: 0.
- `@mui/styles`, `makeStyles`, `withStyles`, `createMuiTheme`, `experimentalStyled`, `@mui/lab`, `<Hidden>`: 0.
- MUI v9.0.1 deprecated props: across its component `.d.ts` files, installed `@mui/material` 9.0.1 carries only 5 `@deprecated` tags (`darkScrollbar`, `CssVarsProvider`/ThemeProviderWithVars, `adaptV4Theme`, `utils/createSvgIcon`, `StandardProps`), and none is used in src. The v5–v7 prop deprecations appear to have been removed from v9's types. Grepping for `components=`, `componentsProps=`, `TransitionComponent=`, `TransitionProps=`, `PaperProps=`, `InputProps=`, `inputProps=`, `InputLabelProps=`, `FormHelperTextProps=`, `SelectProps=`, `MenuProps=`, `PopperProps=`, `BackdropProps=`, `BackdropComponent=`, `ListboxProps=`, `primaryTypographyProps`, `<ListItem button`, `paragraph`, `renderTags`, `disableEscapeKeyDown`, `onBackdropClick` found 0 of each. `slotProps=` is used (15 prod sites). Because `type-check:prod` is a clean gate, a removed prop could not compile anyway.
- MUI Grid legacy API (`item`, `xs=`) and `Unstable_Grid2`: 0 (#2933, #3484 still fixed). The `Grid2` name is a local alias for `import Grid2 from '@mui/material/Grid'` using the v7+ `size` prop (all 4 `item.*xs=` hits are `itemType=` on `GridLoadingState`).
- `React.FC` / `FunctionComponent` / `VFC` / `ReactChild` / `ReactFragment` / `ReactText` / `createFactory`: 0.
- `forwardRef`: 16 prod sites in 8 files (`design-system/primitives/*`, `InfiniteScrollTrigger.tsx`). Not deprecated in React 18. Noted only (see Dependency notes).
- Browser `process.env` in src: 0 (#3485 still fixed). `substr(`: 0 (#4623 still fixed). `navigator.platform` is confined to one helper under a guard test (#4556). `ScriptProcessorNode` in `services/audio/BufferScheduler.ts` is the documented AudioWorklet fallback that #4623 left in place; not re-reported.
- @testing-library deprecated option types (`BaseRenderOptions`, `ClientRenderOptions`, `HydrateOptions`, `*RenderHookOptions`): 0. `@testing-library/react-hooks`: 0 (`renderHook` from `@testing-library/react`).
- msw v1 (`rest.`, `ctx.json`) and deprecated `StrictResponse`: 0 (msw 2 `http`/`HttpResponse` used).
- @tanstack/react-query v4-era options (`cacheTime`, `keepPreviousData`, `useErrorBoundary`, `onSuccess:` on queries, `isInitialLoading`): 0.
- Vitest removed/deprecated keys: `poolOptions`, `maxForks`, `threads`, `workspace`, `deps.inline`, `environmentMatchGlobs`, `coverage.all`, `transformMode`, `environmentSetupModule`: all absent from `vitest.config.ts`. There is no `vitest.workspace.*`. Old generic `vi.fn<[Args], R>` and `SpyInstance`: 0 (2 `vi.fn<(fn-type)>` sites use the v3+ form). `node_modules/vitest/vitest.mjs` exists, so the `test:memory`/`test:ci` script paths are valid.
- Vite 7.3.5 deprecated keys (`build.polyfillModulePreload`, `optimizeDeps.disabled`, `server.hmr.*` aliases, plugin `enforce`/`transform` in `transformIndexHtml`): absent. `transformIndexHtml` already uses `order`/`handler`.
- tsconfig: `moduleResolution: bundler` (both tsconfigs), no `importsNotUsedAsValues`/`preserveValueImports`/`downlevelIteration`/`outFile`/`target ES3|ES5`/`alwaysStrict:false`/`esModuleInterop:false`. `tsconfig.node.json` includes only files that exist (#4588 still fixed). No `jsconfig.json` (#4589 still fixed).
- ESLint legacy `.eslintrc*`: none anywhere outside node_modules (`find . -name '.eslintrc*' -o -name 'eslint.config.*'`). ESLint is not a dependency at all (#4908), so there is no flat-config migration to do.
- Node built-ins without the `node:` prefix: 0 across `desktop/*.js`, root `dev.js`/`build.js`/`package.js`, `auralis-web/frontend/scripts/*`, `vite.config.mts`, `vitest.config.ts` (#4591 still fixed). Every non-`node:` require/import is a relative module, `electron*`, or `vite`/`vitest`.
- Deprecated Node APIs (`url.parse`, `fs.exists(`, `new Buffer(`, `punycode`, `util.is*`, `util._extend`, `querystring`, `process.binding`, `fs.rmdir(…recursive)`, `crypto.createCipher`, `SlowBuffer`, `req.connection`, `res.finished`, `_headers`): 0 in the same file set. `fs.existsSync` is not deprecated. `assert.deepEqual` in `desktop/preload.test.js:44` is "legacy", not deprecated.
- Electron 43.2.0 deprecated APIs: installed `electron.d.ts` carries about 60 deprecated symbols (BrowserView family, `protocol.register*/intercept*Protocol`, `webContents.goBack/canGoBack/clearHistory/…`, `session.setPreloads/getPreloads/loadExtension/…`, `webFrameMain.routingId`, `accessibilityDisplayShouldReduceTransparency`, `openAsHidden`). None is used by `desktop/main.js` or `desktop/preload.js`. Also confirmed: `setWindowOpenHandler` (no `new-window` event), `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, no `remote`, no `nativeWindowOpen`, no `registerFileProtocol`, no `ipcRenderer.sendTo`, `will-navigate`/`will-redirect` handled.
- electron-builder 26.15.7 `build` config: `app-builder-lib/scheme.json` marks only `snap` (→ `snapcraft`) as deprecated, and the config does not use `snap`. No deprecated `win.certificateFile`/`publisherName`/`sign` at top level.
- Third-party runtime React warnings: `react-infinite-scroll-component@6.1.1` has no `componentWill*`/`UNSAFE_` (only `componentWillUnmount`). The `@hello-pangea/dnd@18.0.1` `contextTypes` hit (dnd.js:1075) is a static-hoisting key list, not legacy-context usage.
- Direct dependencies flagged `deprecated:` in any lockfile: 0 (frontend, desktop, root).

### Rust/PyO3/Cargo + Config/CI (Dimensions 6, 8)

- **GitHub Actions versions**: all 9 workflows pin every `uses:` to a 40-char SHA at current majors: checkout v7.0.1, setup-python v7.0.0, setup-node v7.0.0, pnpm/action-setup v6.1.0, upload-artifact v7.0.1, download-artifact v8.0.1, softprops/action-gh-release v3.0.3, taiki-e/install-action v2.87.9, dtolnay/rust-toolchain master@2026-08-14. Checked with `grep -rn 'uses:' .github/workflows/`.
- **pnpm/action-setup `version:` input**: absent at all 5 sites (build-release.yml:99/262/401, frontend-test.yml:48, frontend-typecheck.yml:39).
- **Python version in CI**: `'3.14'` everywhere (backend-tests.yml:106, build-release.yml:58/97/260/399, requirements-pin-guard.yml:117/129). Node `'24'` everywhere.
- **Baseline gates wired**: `backend-tests.yml:143` runs `check_pytest_baseline.py pytest-results.xml --strict-stale`, and the script `_die`s on no testsuite (l.73) or 0 collected (l.77-78). `frontend-test.yml:69` runs `pnpm run test:baseline`, and `check-test-baseline.mjs` exits 1 on a missing report or `!numTotalTests` (l.56-58).
- **Guard workflows present and wired**:
  - `action-pin-guard.yml`, `lockfile-guard.yml`, `rust-audit.yml` (weekly cron + push/PR)
  - `requirements-pin-guard.yml` (runs `.github/scripts/check_pyproject_deps.py`)
  - `path-references.yml` (runs `.claude/commands/_audit-validate.sh` and `scripts/check_optimization_importers.py`)
- **No Docker / setup.py / setup.cfg / tox.ini / .eslintrc / .coveragerc / .flake8 tracked**: `git ls-files | grep -iE 'dockerfile|docker-compose|setup\.py$|setup\.cfg$|tox\.ini|\.eslintrc|\.coveragerc'` returns nothing. The only Docker residue is the Makefile target (DEP-CFG-3).
- **Version drift**: `auralis/version.py` 1.5.1 = `pyproject.toml` 1.5.1 = `package.json` / `auralis-web/frontend/package.json` / `desktop/package.json` 1.5.1.
- **pytest floor**: `pyproject.toml` `pytest>=9.0.1` matches `pytest.ini` `minversion = 9.0.1`; installed 9.0.1. #4529 is still fixed.
- **`asyncio_default_fixture_loop_scope`**: set (`pytest.ini:4`), so #4899 is still fixed.
- **`.pre-commit-config.yaml`**: revs are current (pre-commit-hooks v6.0.0, black 26.5.1, isort 8.0.1, mypy v2.3.0, pylint v4.0.6), so #4904 is still fixed.
- **requirements manifests**: `requirements.txt` and `auralis-web/backend/requirements.txt` are identical after stripping comments (`diff` empty). `requirements-desktop.txt` is only `-r requirements.txt`.
- **`Cargo.lock` tracked, toolchain pinned**: `git ls-files vendor/auralis-dsp` lists `Cargo.lock` and `rust-toolchain.toml` (1.96.0), so #4531 is still fixed.
- **Rust deprecation warnings**: `cargo check --all-targets` produced 0 `deprecated` warnings, only unused variables at `src/py_bindings.rs:93` (`sr`), `src/fingerprint_compute.rs:429,476,477` and `src/biquad_filter.rs:175`. These are tech debt, not deprecation.
- **Deprecated Rust std idioms**: none. `grep -rnE 'lazy_static!|mem::uninitialized|try!\(|\.description\(\)|std::f(32|64)::(EPSILON|MAX|MIN|NAN|INFINITY)\b|std::(u|i)(8|16|32|64|size)::(MAX|MIN)|trim_left|trim_right' vendor/auralis-dsp/src` returns nothing.
- **PyO3 0.23 API usage**: the code already uses the 0.23 non-`_bound` numpy constructors (`into_pyarray(py).unbind()`) and `PyReadonlyArray`. No `IntoPy`/`ToPyObject`/`GILPool`/`acquire_gil`/`&PyAny` GIL-ref APIs remain, so nothing is deprecated *at 0.23*. The 0.26+ renames are captured in DEP-RS-1.
- **Deprecated/unmaintained crates in Cargo.lock**: no `atty`, `instant`, `paste`, `serde_cbor`, `proc-macro-error` or `lazy_static`. `cargo audit` in CI covers the rest, with 2 documented ignores.
- **PyInstaller spec**: `auralis-web/backend/auralis-backend.spec` has no `block_cipher`/`cipher=`/`win_no_prefer_redirects`/`win_private_assemblies` (removed in PyInstaller 6); installed PyInstaller is 6.22.0.
- **mypy deprecated options**: no removed options in `[tool.mypy]`. The only mypy config defect is DEP-CFG-1.
- **black/ruff config**: `[tool.black]` is valid for black 26.5.1. No ruff config is tracked; `.ruff_cache/` is untracked residue (#4946 closed).

---

Suggested next step:

```
/audit-publish docs/audits/AUDIT_DEPRECATION_2026-09-13.md
```
