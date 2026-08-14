# Tech-Debt Audit — 2026-08-13

**Scope**: whole repo — `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/src/`, `tests/`, `docs/`, `.claude/commands/`
**Depth**: deep · **Dimensions**: all 10 · **Tree state**: `188db72a` (master, clean)
**Dedup baseline**: 292 OPEN + 2,000 CLOSED issues (315 carrying `tech-debt`)

> This is a fresh sweep of the live tree. No prior `AUDIT_TECH_DEBT_*.md` report was read or reused as a source of findings.

---

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | **2** |
| LOW | **11** |
| **Total** | **13** |

**Headline**: the codebase's own debt hygiene is in good shape — genuine marker debt is **zero**, chunk geometry has **zero** literal bypasses, design tokens have **zero** raw-hex violations, and the version string is consistent across all five files that carry it. The two MEDIUM findings are both in the **audit tooling itself**, not the product: `_audit-common.md` now tells every auditor that a package on the main DSP pipeline is dead code, and the path-reference gate that was supposed to prevent exactly that class of drift has been red on every run since 2026-08-07 and is `|| true`'d by the skills that call it.

The single highest-value item is **TD10-1** — a false claim introduced into the shared audit protocol *today* (`188db72a`) that is actively misleading the other audits running in this same suite.

### Direction vs. the Phase-1 baseline

| Metric | Value | Read |
|---|---|---|
| **markers, genuine (all src)** | **0** | The real marker debt. Zero is the expected and correct value for this repo. |
| markers, raw (pre-filter) | 2 | Diagnostic only. Both verified false positives (a `#3xxx` issue placeholder in `auralis/analysis/fingerprint/schema.py:37`, a `0.xxxx` string in a vitest spec). Not debt. |
| prose deferrals (non-test) | 9 | High recall / low precision — hits were read individually, not quoted as debt. 3 are genuine deferrals; 2 of those are already tracked (#4243, #4239); 1 is new (TD1-1). The other 6 are ordinary prose. |
| NotImplementedError | 3 | All in `auralis/library/scanner/duplicate_detector.py` and all deliberate: one docstring, one re-raise, one documented precondition guard from #4241. Not debt. |
| type: ignore (py) | 72 | Not individually audited this pass — see *Not Covered*. |
| @ts-ignore / @ts-expect-error | 3 | All three are in test files with justifying comments. Clean. |
| **'any' non-test (ts)** | **29** | The type-safety debt that ships. Nearly all are legitimate generic constraints (`ComponentType<any>`, `(...args: any[])`); 13 of the 29 sit inside `src/performance/`, already tracked dead code (#4696). Healthy. |
| 'any' raw incl. tests (ts) | 516 | Trend continuity only. Specs and mocks dominate. |
| skipped tests (py) | 59 | See TD6-2 and the Deduped section. |
| skipped tests (ts) | 2 | One `describe.skip` with a documented rationale, one comment. Clean. |
| **py files >300 LOC** | **105** | Up from 102 at #4673 (2026-07-25). See TD9-1. |
| ts/tsx files >300 LOC | 127 raw / **36 non-test** | The raw number includes specs. **36** is the production figure — down from 44 at #4673. |
| allow(dead_code) (rust) | 0 | Clean. |

Path-reference gate: **306 STALE** refs, **all 306 in `docs/`**, **0 in `.claude/`**. The skill-file half of the gate is genuinely clean; the docs half is not (TD7-1).

### Verified clean (no findings — recorded so the next run can detect regression)

- **Chunk geometry**: zero literals bypass `auralis-web/backend/core/chunk_boundaries.py`. Every `total_chunks` computation in the tree routes through the overlap-aware `content_chunk_count()` (`chunked_processor.py:328,343`, `routers/enhancement.py:169`, `chunk_boundaries.py:150`, `cache/manager.py:30`). No naive `ceil(duration / CHUNK_DURATION)` survives.
- **Design tokens**: zero hardcoded hex/rgb colors in `auralis-web/frontend/src/components/`. All 12 grep hits are comments *annotating* a token's resolved value (e.g. `tokens.colors.audioSemantic.identity;  // #7366F0`).
- **Version drift**: `auralis/version.py` (1.5.1) matches `package.json`, `desktop/package.json`, `auralis-web/frontend/package.json`, and `pyproject.toml`. `vendor/auralis-dsp/Cargo.toml` at 0.1.0 is an independently-versioned crate, not drift.
- **Documented structural counts**: `python scripts/check_doc_counts.py` reports 54 analysis files / 20 routers / 519 test files / 6,040 test functions / 18 docs dirs — matching both CLAUDE.md and `_audit-common.md` exactly. The #4982 dual-maintenance hazard is currently in sync.
- **Rust DSP**: zero `#[allow(dead_code)]`.

---

## Quick Wins (trivial / small effort)

| # | Finding | Effort | Payoff |
|---|---|---|---|
| 1 | **TD10-1** — delete the false "no production importers" sentence from `_audit-common.md` (2 places) | trivial | Stops every audit from under-rating live DSP-pipeline code |
| 2 | **TD2-2** — `rm -r auralis/library/caching/` (empty package, `__all__ = []`) | trivial | −1 package, closes the last #4915 residue |
| 3 | **TD7-2** — correct CLAUDE.md:68 and `_audit-common.md`:94: the backend pytest baseline **is** checked in as of 2026-08-12 | trivial | Stops contributors overwriting a CI-derived baseline with a local one |
| 4 | **TD2-3b** — drop the dead `tests/obsolete` entry from `pytest.ini:12` `norecursedirs` | trivial | Config stops referencing a directory deleted long ago |
| 5 | **TD2-3a** — delete `tests/validation/` (13 orphaned scripts, 2,168 LOC, already excluded from collection) | small | −2,168 LOC that no runner, CI job, or doc references |
| 6 | **TD2-1** — move `WAVEncoderError` into `core/encoding/`, delete `auralis-web/backend/encoding/` | small | −112 LOC + kills 3 fragile bare `from encoding.…` sys.path imports |
| 7 | **TD2-4** — delete `tests/backend/full_stack_smoke.py` (uncollected, wrong port) | trivial | Closes AUDIT_RECOVERY_2026-07-24 item 8 the honest way |
| 8 | **TD6-2** — add issue refs to (or delete) the 4 untracked permanent skips | trivial | Every skip becomes traceable |
| 9 | **TD8-2** — add a breadcrumb-comment grep gate instead of filing a 5th cleanup issue | small | Ends a 4-cycle recurrence |
| 10 | **TD6-1** — strengthen the 22 residual sole-`is not None` assertions | small | Closes out #4049/#4257 for real |
| 11 | **TD1-1** — convert `path_security.get_allowed_directories()`'s prose deferral to `# TODO(#NNNN):` | trivial | Restores greppability of the one untracked deferral |

## Top 5 Medium Investments

1. **TD7-1** — get `_audit-validate.sh` back to green (306 refs) and wire it into CI, or the gate stays decorative. Budget: 1 day, mostly mechanical.
2. **TD9-1** — the >300 LOC census is *growing* (102 → 105 Python) while #4511 tracks 8 files. Re-scope #4511 against the live census and adopt #4673's acceptance criterion (close only when verified <300 LOC).
3. **TD8-1** — rename the `library_manager` identifier to `library_database` across 29 files / 118 references and fix the 4 docstrings that describe a deleted class in the present tense.
4. **#4604** (existing) — `BaseRepository._session_scope()` adoption is now **3/16 repos** with **81** hand-rolled session sites. Update the issue's counts and finish the sweep.
5. **#4511 / #4673** — the four issues closed in 2026-07 with their targets still 2.3–2.7× over the limit remain the strongest argument for the LOC acceptance criterion.

---

# Findings

## MEDIUM

### TD10-1: `_audit-common.md` declares a live DSP-pipeline package to be dead code — twice
- **Severity**: MEDIUM *(promotion trigger: stale audit baseline that has misled an audit in the last 90 days)*
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/_audit-common.md:23`, `.claude/commands/_audit-common.md:81`
- **Status**: NEW
- **Age**: `188db72a` 2026-08-13 — introduced **today**, in the current HEAD commit
- **Effort**: trivial
- **Description**: The shared protocol file that every audit skill loads first asserts that `auralis/optimization/` has no production importers, and instructs auditors to downgrade severity there on that basis. The assertion is false. `auralis/core/hybrid_processor.py` — the main DSP pipeline per CLAUDE.md's own Codebase Map — imports and uses it on the hot path.
- **Evidence**:
  ```
  .claude/commands/_audit-common.md:23
    "…performance_optimizer.py. NO production code imports this package — the only
     importers are tests. … Treat the remainder as unreferenced-by-runtime: a bug
     here has no user-visible blast radius, so cap severity accordingly and prefer
     a tech-debt finding over an engine finding."

  .claude/commands/_audit-common.md:81 (Retired Architecture table)
    "The rest of `auralis/optimization/` survives but is imported only by tests."
  ```
  Contradicted by:
  ```
  auralis/core/hybrid_processor.py:27   from ..optimization.performance_optimizer import get_performance_optimizer
  auralis/core/hybrid_processor.py:139      self.performance_optimizer = get_performance_optimizer()
  auralis/core/hybrid_processor.py:566      return self.performance_optimizer.get_optimization_stats()
  auralis/core/hybrid_processor.py:612      perf_opt = get_performance_optimizer()
  ```
  `performance_optimizer.py` in turn pulls in `SIMDAccelerator`, `SmartCache`, `MemoryPool`, `PerformanceProfiler` and `PerformanceConfig` (lines 27–33), so **five of the six** surviving submodules are transitively live. Only `auralis/optimization/config.py`'s test-only surface and the `acceleration/__init__.py` redirect note are genuinely test-only.
- **Impact**: Every audit in the currently-running comprehensive suite is being told to cap severity on ~779 LOC that sits on the main mastering path. A CRITICAL DSP bug in `SmartCache` or `MemoryPool` would be written up as LOW tech debt. The instruction is not merely wrong, it is *actively severity-suppressing* — the worst failure mode for an audit baseline.
- **Siblings**: This is the ninth issue in a family of false/stale `_audit-common.md` claims — #4979 (false WAVEncoderError duality), #4922, #4685, #4067, #4066, #4065, #5045 (test counts, 3rd occurrence), #4974 (false pytest-baseline claim, OPEN). The file has no automated verification for its prose claims, only for its backticked paths.
- **Related**: #4565 (the deletion this claim over-generalized from — `parallel/` *was* dead; the rest of the package is not). Route any actual bug found in `auralis/optimization/` to `/audit-engine`, not here.
- **Suggested Fix**: Replace the sentence at line 23 with "`performance_optimizer.py` is imported by `auralis/core/hybrid_processor.py` and pulls in `acceleration/`, `caching/`, `memory/` and `profiling/` — treat these as live engine code. Only `config.py`'s standalone surface is test-only." Amend line 81 the same way. Then extend `scripts/check_doc_counts.py` (or a sibling script) with an importability assertion so a "no production importers" claim is machine-checked rather than hand-maintained.

### TD7-1: The path-reference gate has been red on every run since 2026-08-07 and is `|| true`'d by the skills that call it
- **Severity**: MEDIUM *(promotion trigger: stale doc baseline that has misled an audit — the detection mechanism itself is inert)*
- **Dimension**: Stale Documentation
- **Location**: `.claude/commands/_audit-validate.sh:103-126`, `.claude/commands/audit-tech-debt.md:68`
- **Status**: NEW *(the underlying 128-ref count is CLOSED as #4547; the gate-inertness is a distinct, new problem)*
- **Age**: `06b9d0aa` 2026-08-07 (the #4984 widening of the gate's scope to `docs/`)
- **Effort**: medium (306 refs, mostly mechanical) — or small, if the historical trees are excluded instead
- **Description**: #4984 widened the gate from 11 docs files to ~13 glob patterns across `docs/`. The widening was never followed by a cleanup pass, so the gate now reports **306 stale backticked path refs and exits 1 on every invocation**. Because it can never pass, `audit-tech-debt.md:68` invokes it as `.claude/commands/_audit-validate.sh || true`, and it is **not wired into any CI workflow**. A gate that always fails and whose failure is always swallowed cannot distinguish new rot from old, which is the entire function it was built for (#4052, #4063, #4258).
- **Evidence**:
  ```
  $ .claude/commands/_audit-validate.sh; echo $?
  Checked 1717 refs across 138 skill files.
  Checked 240 markdown links across 11 doc files.
  FAIL: 306 stale path reference(s).
  1

  $ grep -RIn "audit-validate" .github/workflows/
  (no matches)

  .claude/commands/audit-tech-debt.md:68
    .claude/commands/_audit-validate.sh || true   # STALE lines → auto-eligible Dim 7/10 findings
  ```
  Concentration (top offenders): `docs/features/cache-system/CACHE_AND_CHUNKING_AUDIT.md` (22), `docs/frontend/PHASE1_2_3_LAUNCH_CHECKLIST.md` (21), `docs/frontend/analysis/PLAYER_COMPONENT_CONSOLIDATION_PLAN.md` (20), `docs/UI_DESIGN_GUIDELINES.md` (20), `docs/ui_audit/IMPLEMENTATION_STATUS.md` (16). **40 files hold all 306.**
- **Impact**: The one structural defence against path drift is disabled. TD10-1 above is precisely the class of drift it was meant to catch (though prose, not paths) — and no auditor is alerted when a *new* stale ref lands, because the exit code is identical before and after.
- **Siblings**: 0 stale refs in `.claude/` — the skill-file half of the gate is clean and worth preserving as a separate, green, CI-enforced check.
- **Related**: #4547 (CLOSED, 128 refs), #4984 (CLOSED, the widening that caused this), #4052 / #4063 / #4258 (the three `docs/README.md` recurrences the gate was built to stop).
- **Suggested Fix**: Split the gate into two exit codes: fail hard on `.claude/**` (currently 0 stale — keep it that way and put it in CI), and emit a *tracked baseline count* for `docs/**` that may shrink but never grow, mirroring the `test-baseline.json` ratchet the project already uses. Then either fix or de-backtick the 306 refs; ~85 of them sit in five historical planning docs (`docs/ui_audit/`, `docs/frontend/PHASE*`) that should arguably move under `docs/archive/` and out of the gate's scope entirely.

---

## LOW

### TD2-1: `auralis-web/backend/encoding/` survives only to host one exception class
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/backend/encoding/wav_encoder.py:35-90`, `auralis-web/backend/encoding/__init__.py:11-16`
- **Status**: NEW
- **Age**: `a0179495` 2026-08-07 (last touched); the module predates the `core/encoding/` replacement
- **Effort**: small
- **Description**: `encode_to_wav()` has **zero production callers** — the file says so itself. Its only remaining consumers are three tests. The whole legacy package stays alive because `WAVEncoderError` is defined in it, and three live modules reach for that exception through a bare `from encoding.wav_encoder import …` absolute import that resolves only because `pytest.ini`/uvicorn put `auralis-web/backend` on `sys.path`.
- **Evidence**:
  ```python
  # auralis-web/backend/encoding/wav_encoder.py:60-64 — the module's own admission
  # Currently this function has no production caller — #4895 rerouted the one
  # live call path (get_wav_chunk_path) through the already-guarded
  # WAVEncoder.encode_and_save instead — but it remains public API
  # (encoding/__init__.py exports it), so this is fixed rather than
  # left correct-only-by-accident.
  ```
  The three fragile importers:
  ```
  auralis-web/backend/core/processing_engine.py:68    from encoding.wav_encoder import WAVEncoderError
  auralis-web/backend/core/encoding/wav_encoder.py:18 from encoding.wav_encoder import WAVEncoderError
  auralis-web/backend/core/chunked_processor.py:66    from encoding.wav_encoder import WAVEncoderError
  ```
  `encode_to_wav` callers repo-wide: `tests/backend/test_encode_to_wav_nonfinite_guard_4672.py`, `tests/backend/test_absolute_path_log_hygiene.py` — tests only.
- **Impact**: 112 LOC of maintained-but-unreachable code that has absorbed real fix effort as recently as #4672 (a NaN guard added to a function nothing calls). The bare `from encoding.…` imports break the moment anything is run with a different working directory or packaged differently — exactly the failure mode the 2026-03 PyInstaller packaging regression exhibited.
- **Siblings**: `auralis-web/backend/core/encoding/wav_encoder.py` (260 LOC, class-based) is the live implementation. `_audit-common.md:42` already flags the pair as "a known duplication hotspot" but frames it as two live implementations; only one is live.
- **Related**: #4919 (CLOSED — fixed error typing in the *live* copy), #4895, #4672, #3872 (all effort spent on the dead copy), #3912 (OPEN — `WAVEncoderError` unmapped in the global handler; fixing TD2-1 first makes that a one-file change).
- **Suggested Fix**: Move `class WAVEncoderError` into `auralis-web/backend/core/encoding/wav_encoder.py`, re-export it from `core/encoding/__init__.py`, repoint the three importers to `from core.encoding import WAVEncoderError`, then delete `auralis-web/backend/encoding/` and the two tests that exercise `encode_to_wav`. Update `_audit-common.md:42` in the same change so the "two live implementations" framing does not outlive the deletion.

### TD2-2: `auralis/library/caching/` is an empty package left behind by #4915
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/library/caching/__init__.py:1-9`
- **Status**: NEW
- **Age**: `2ff696c9` 2026-02-13 (last content change); emptied by #4915 on 2026-07-29
- **Effort**: trivial
- **Description**: The package contains nothing but a docstring and `__all__ = []`. The cache layer it wrapped was deleted with `LibraryManager` in #4915; the directory was left behind.
- **Evidence**:
  ```python
  """
  Caching Layer for Auralis Library
  Provides caching infrastructure for queries and persistent storage.
  DSP-related caches have been removed post-Rust migration.
  """
  __all__ = []
  ```
  Directory listing: `__init__.py` and `__pycache__` only. No importers anywhere in the tree.
- **Impact**: Minimal at runtime, but it makes the library subtree misrepresent itself: a reader (or an auditing agent) grepping for a caching layer finds a package that promises one and delivers nothing. `_audit-common.md:82` already documents it as "now an empty package" — encoding the debt into the protocol instead of deleting it.
- **Siblings**: None — the other #4915 residue (`manager.py`) was deleted correctly.
- **Related**: #4915 (CLOSED).
- **Suggested Fix**: `rm -r auralis/library/caching/` and drop the "`auralis/library/caching/` is now an empty package" clause from `_audit-common.md:82`.

### TD2-3: `tests/validation/` holds 2,168 LOC of orphaned scripts that pytest is configured never to collect
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `tests/validation/` (13 files), `pytest.ini:12`
- **Status**: NEW
- **Age**: `2ca72012` 2026-08-12 (last touched, incidentally)
- **Effort**: small
- **Description**: Thirteen `validate_*.py` scripts sit in `tests/validation/`. None matches `python_files = test_*.py`, and the directory is *additionally* named in `norecursedirs`, so pytest excludes it twice over. No runner, CI workflow, script, or doc references any of them. Separately, `norecursedirs` still excludes `tests/obsolete`, a directory that no longer exists.
- **Evidence**:
  ```ini
  # pytest.ini
  testpaths = tests
  python_files = test_*.py
  norecursedirs = tests/validation tests/obsolete .git __pycache__ build dist *.egg-info
  ```
  ```
  $ ls -d tests/obsolete
  ls: cannot access 'tests/obsolete': No such file or directory

  $ find tests/validation -name 'validate_*.py' | xargs wc -l | tail -1
  2168 total   # across 13 files

  $ grep -RIn "tests/validation\|validate_comprehensive\|validate_all_behaviors" \
      --include='*.py' --include='*.md' --include='*.yml' . | grep -v tests/validation/
  pytest.ini:12:norecursedirs = tests/validation …     # the exclusion itself, nothing else
  ```
- **Impact**: 2,168 LOC that every repo-wide grep, every "does a test cover this?" search, and every agent sweep must wade through, for code that cannot run. It also distorts the documented test census (519 files / 6,040 functions) by implying coverage that is not executed.
- **Siblings**: `tests/stress/stress_test_suite.py` is also uncollected but is a documented manual entry point (`python tests/stress/stress_test_suite.py --all`) — keep it. `tests/backend/full_stack_smoke.py` is TD2-4. The four `helpers.py` files under `tests/{performance,concurrency,stress,security}/` are legitimate imported support modules — keep them.
- **Related**: #4246 (CLOSED — the adjacent "pure print(), zero assertions" convention).
- **Suggested Fix**: Delete `tests/validation/` and remove both it and the non-existent `tests/obsolete` from `pytest.ini:12`'s `norecursedirs`. If any script has residual value as a manual tool, move it to `scripts/development/` where an uncollected script belongs.

### TD2-4: `full_stack_smoke.py` is uncollected, points at the wrong port, and was flagged 7 weeks ago
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface *(also Audit-Finding Rot)*
- **Location**: `tests/backend/full_stack_smoke.py:46,87,110,154,169`
- **Status**: NEW *(as a debt finding; the underlying fact was published in AUDIT_RECOVERY_2026-07-24 and never triaged into an issue)*
- **Age**: `9efbe580` 2026-06-28
- **Effort**: trivial
- **Description**: The file is not named `test_*.py`, so pytest collects zero tests from it, and every request it makes targets `http://localhost:8000` while the backend binds 8765. It is doubly inert. AUDIT_RECOVERY_2026-07-24 documented both facts and listed "convert `full_stack_smoke.py` into a collected isolated subprocess test" as remediation item 8; seven weeks later nothing has changed and no GitHub issue tracks it.
- **Evidence**:
  ```python
  tests/backend/full_stack_smoke.py:46   requests.get("http://localhost:8000/api/health", timeout=1)
  tests/backend/full_stack_smoke.py:87   requests.get(f"http://localhost:8000{endpoint}", timeout=2)
  tests/backend/full_stack_smoke.py:110  requests.get("http://localhost:8000/", timeout=2)
  tests/backend/full_stack_smoke.py:154  requests.get(f"http://localhost:8000/static/css/{css_file}", timeout=2)
  ```
  ```
  docs/audits/AUDIT_RECOVERY_2026-07-24.md:189
    "tests/backend/full_stack_smoke.py is not named test_*.py, collects zero tests,
     and polls localhost:8000 while the backend hardcodes 8765."
  ```
- **Impact**: A file named "smoke test" that provides no smoke coverage is worse than no file — it reads as coverage in a directory listing. It is also a live example of the Dim 10 rot pattern: a published audit finding with no issue behind it silently expires.
- **Siblings**: The `docs/audits/` tree holds several reports older than 90 days; AUDIT_RECOVERY_2026-07-24's remediation list is the one with un-triaged items reachable from the current tree.
- **Related**: AUDIT_RECOVERY_2026-07-24 item 8.
- **Suggested Fix**: Delete the file. If a real full-stack smoke test is wanted, write it fresh as `tests/backend/test_full_stack_smoke.py` reading the port from `auralis-web/backend/core/env_config.py` rather than a literal — reviving a file that has been wrong on two axes since June is more work than replacing it.

### TD6-1: 22 sole-`is not None` smoke tests survive the #4049 / #4257 cleanups
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_string_input_boundaries.py`, `tests/boundaries/test_string_input_boundaries.py`, `tests/backend/test_boundary_*.py`, +8 more files
- **Status**: Regression of #4257 *(partial-fix residual — 56 → 22, not 0)*
- **Age**: various; the pattern predates both cleanup issues
- **Effort**: small
- **Description**: An AST-style sweep of every `test_*` function under `tests/` finds 22 whose *only* assertions are `is not None`. #4049 fixed 31, #4257 fixed a further 56 across 32 files, and both closed — but the pattern was never gated, so a residue remains. The worst offender is a security boundary test.
- **Evidence**:
  ```
  tests/backend/test_string_input_boundaries.py::test_sql_injection_in_title  (2 asserts, both `is not None`)
  tests/backend/test_string_input_boundaries.py::test_null_bytes_in_string    (1 assert)
  tests/backend/test_string_input_boundaries.py::test_newlines_in_title       (1 assert)
  tests/backend/test_boundary_advanced_scenarios.py::test_corrupted_audio_file_handling (1 assert)
  tests/backend/test_boundary_advanced_scenarios.py::test_invalid_metadata_values       (1 assert)
  tests/integration/test_e2e_workflows.py::test_add_track_with_metadata_extraction      (4 asserts, all `is not None`)
  tests/boundaries/test_audio_processing_boundaries.py::test_wrong_shape_1d_array       (1 assert)
  … 15 more
  ```
  `test_sql_injection_in_title` asserting only that a result is non-null means an injection that *succeeded* and returned a row would pass the test.
- **Impact**: 22 tests that cannot fail for the reason they exist. `test_e2e_workflows.py::test_add_track_with_metadata_extraction` is the highest-value one — a four-assert E2E test that verifies four things are non-null and nothing about their values, i.e. it would pass against a metadata extractor that returned the wrong data for every field.
- **Siblings**: 91 test files call `print()`; #4246 (CLOSED) covered the `test_summary_stats()` convention specifically, and the remainder are diagnostics alongside real assertions — not re-reported here.
- **Related**: #4049 (CLOSED, 31 tests), #4257 (CLOSED, 56 tests / 32 files).
- **Suggested Fix**: Strengthen the 22 in one pass, prioritising `test_sql_injection_in_title` (assert the stored title round-trips byte-identically and no extra rows exist) and `test_add_track_with_metadata_extraction` (assert the extracted title/artist/album/duration equal the fixture's known values). Then add the AST check used to produce this list as a pytest collection-time warning so the count cannot climb back.

### TD6-2: Four permanent skips carry no issue reference, one of them for an endpoint that never existed
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_boundary_max_min_values.py:377,431,505`, `tests/backend/test_api_endpoint_integration.py:175`
- **Status**: NEW *(adjacent to #4400, which covers skips for **removed** endpoints; these are different)*
- **Effort**: trivial
- **Description**: Four `@pytest.mark.skip` markers state a limitation as permanent fact with no tracking issue, so nothing will ever prompt a re-check. One of them describes an endpoint that was never implemented and is not on any roadmap — the test is aspirational, not deferred.
- **Evidence**:
  ```python
  tests/backend/test_boundary_max_min_values.py:377
    @pytest.mark.skip(reason="Known limitation: Extreme DC offset edge case not fully handled. …")
  tests/backend/test_boundary_max_min_values.py:431
  tests/backend/test_boundary_max_min_values.py:505
    @pytest.mark.skip(reason="Known limitation: Repository deduplicates by filepath. Test requires unique files per track.")
  tests/backend/test_api_endpoint_integration.py:175
    @pytest.mark.skip(reason="Endpoint /api/library/search not yet implemented (returns 404)")
  ```
  `/api/library/search` does not exist and never has — `auralis-web/backend/routers/library.py` registers exactly three routes (`/api/library/refresh-references`, `/api/library/stats`, `/api/library/reset`).
- **Impact**: "Known limitation" with no issue is indistinguishable from "someone gave up"; the DC-offset one in particular asserts a documented DSP gap that `/audit-engine` would want to know about. The `/api/library/search` skip advertises a planned feature that isn't planned.
- **Siblings**: The other 55 py skips are accounted for — 9+5 `xfail(strict=True)` with `see #4548`, 9 with `see #4269`, ~12 dependency guards (`MUTAGEN_AVAILABLE`, `_HAS_FFMPEG`, registry presence) which are correct usage, 5 removed-endpoint skips under **#4400 (OPEN)**, and 2 identical unreferenced perf skips under **#5024 (OPEN)**.
- **Related**: #4400 (OPEN), #5024 (OPEN), #4548 (CLOSED).
- **Suggested Fix**: Delete `test_api_endpoint_integration.py:175` outright (testing an endpoint nobody intends to build is not deferred work). For the three "Known limitation" skips, either file one issue covering both limitations and add `(#NNNN)` to each reason string, or delete the two repository-dedup ones and rewrite them against the actual dedup contract.

### TD8-1: `library_manager` names a class that was deleted three weeks ago — 118 references across 29 files
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/config/startup.py:369-376`, `auralis/library/database.py:9-16`, `auralis/library/__init__.py:16-21`, `auralis-web/backend/routers/dependencies.py:88-91`, +25 files
- **Status**: NEW *(#4312 covers only the dead constructor **parameter**; this is the identifier and the present-tense docstrings)*
- **Age**: `LibraryManager` deleted 2026-07-29 (#4915); the naming survived intact
- **Effort**: medium
- **Description**: `LibraryManager` no longer exists — no `manager.py`, no class definition anywhere in `auralis/`. But the global that holds the `LibraryDatabase` instance is still keyed `library_manager`, and four docstrings describe the deleted class in the **present tense** as a live component, which is precisely the construction `_audit-common.md:82` warns is "stale by construction."
- **Evidence**:
  ```
  $ grep -RIn "class LibraryManager" auralis/          → no matches
  $ ls auralis/library/manager.py                      → No such file or directory
  $ grep -RIn "library_manager\|LibraryManager" auralis auralis-web/backend \
      --include='*.py' | grep -vE '/tests?/|test_' | wc -l   → 118  (29 files)
  ```
  ```python
  # auralis-web/backend/config/startup.py:369  — the variable is a LibraryDatabase
  globals_dict['library_manager'] = LibraryDatabase()

  # auralis/library/database.py:15-16 — present tense, about a deleted class
  "…LibraryManager is now a legacy query facade over this class and
   nothing on the startup path constructs it."

  # auralis-web/backend/routers/dependencies.py:89-91
  "This is the Phase 2 dependency injection mechanism that enables
   gradual migration from the deprecated LibraryManager facade to
   direct repository usage."
  ```
- **Impact**: Every reader and every agent that greps `library_manager` is led to a class that does not exist; several prior audits have had to be corrected on exactly this point (which is why the Retired Architecture table has a row for it). The variable name also actively mis-describes its own type at the composition root.
- **Siblings**: `auralis/player/enhanced_audio_player.py:76,84` and `auralis/player/queue_controller.py:31,38` still declare `library_manager: Any | None = None` parameters documented "Deprecated, kept for backward compatibility only" — accepted and dropped on the floor (`QueueController.__init__` never assigns it). That specific pair is **Existing: #4312**.
- **Related**: #4915 (CLOSED), #4619 (CLOSED), #4312 (OPEN), #5031 (OPEN — the same rot in `docs/subsystems/backend-api.md`).
- **Suggested Fix**: Rename the globals key `library_manager` → `library_database` (mechanical, 29 files, guarded by `mypy` plus the backend router tests), and rewrite the four docstrings at `database.py:9-16`, `library/__init__.py:16-21`, `dependencies.py:89-91` and `startup.py:363-368` in the past tense as one-line historical notes. Doing this closes #4312 as a side effect and removes the need for the Retired Architecture row.

### TD8-2: Breadcrumb-comment cleanup is on its fourth recurrence with no automated guard
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: repo-wide; ~30 instances, concentrated in `auralis-web/frontend/src/hooks/player/index.ts:13,22,24,30`, `auralis-web/frontend/src/types/api.ts:152,164,177,296`, `auralis-web/backend/routers/library.py:132-133`
- **Status**: NEW *(as a **process** finding; the instance cleanup is **Existing: #5034**, itself the 4th in the chain)*
- **Effort**: small
- **Description**: CLAUDE.md/`audit-tech-debt.md` require `// removed:` breadcrumbs to be deleted outright. The same cleanup has now been filed four times — #4088 (10 instances) → #4293 ("#4088 fix incomplete + 1 new") → #4649 ("5 regrown in 4 new files, 3rd recurrence") → #5034 ("regrown in 7 more files, 4th recurrence"). Each was fixed by hand; none added a guard, so the fifth recurrence is already accruing. This is debt about the debt process, not about any particular comment.
- **Evidence**: The recurrence chain in the issue titles is itself the evidence. Current live examples:
  ```typescript
  // auralis-web/frontend/src/hooks/player/index.ts:13,22,24,30 — four in one file
  // usePlaybackState removed (#3126) — parallel WS-shadow state with no production consumers.
  // usePlayerControls removed (#4387) — orphaned hook with zero production consumers…
  // usePlaybackControl removed (#4541) — it drove a REST/WS control plane…
  // #3776: usePlayerStreaming removed — was 475 lines of dead code…
  ```
- **Impact**: Four hand-cleanups over ~3 months for a pattern a 3-line grep would prevent. The cost is the recurring triage, not the comments.
- **Siblings**: Some of these comments are genuinely load-bearing ("do NOT re-add X, here's why") — `BufferScheduler.ts:253` is explicitly marked "DELIBERATELY KEPT, do not re-report." Any guard needs an opt-out marker rather than a blanket ban.
- **Related**: #4088 (CLOSED), #4293 (CLOSED), #4649 (OPEN), #5034 (OPEN).
- **Suggested Fix**: Instead of filing a fifth cleanup issue, add a grep check to the existing `scripts/` gate set: fail on `^\s*(//|#)\s*\w+ removed \(#\d+\)` unless the line also carries `DELIBERATELY KEPT`. Then close #4649 and #5034 together with the mechanical sweep the gate forces.

### TD9-1: The >300 LOC census is growing while #4511 tracks eight files
- **Severity**: LOW
- **Dimension**: File / Function / Module Complexity
- **Location**: repo-wide — 105 Python + 36 production frontend modules
- **Status**: Existing: #4511 *(scope)* — but the census drift is NEW information
- **Effort**: large (decompose per-file; do not file as one issue)
- **Description**: CLAUDE.md sets a <300 LOC module rule. The live census is **105 Python** files over the limit, up from the 102 recorded when #4673 closed on 2026-07-25, and **36 production frontend** files (down from 44). #4511 tracks 8. The Python side is therefore moving *away* from the rule while the tracking issue's scope stays fixed.
- **Evidence**:
  ```
  Python, top 10:
    1066  auralis/library/repositories/track_repository.py
     961  auralis-web/backend/core/processing_engine.py
     942  auralis-web/backend/core/chunked_processor.py
     853  auralis-web/backend/config/startup.py
     795  auralis/library/repositories/fingerprint_repository.py
     767  auralis-web/backend/routers/player.py
     766  auralis-web/backend/routers/processing_api.py
     761  auralis/core/processing/continuous_mode.py
     756  auralis/core/hybrid_processor.py
     741  auralis-web/backend/services/queue_service.py

  Frontend (production only), top 5:
     575  src/hooks/library/useLibraryQuery.ts
     574  src/hooks/enhancement/useAudioStreamingCore.ts
     571  src/store/slices/playerSlice.ts
     538  src/store/middleware/errorTrackingMiddleware.ts
     515  src/theme/themeConfig.ts
  ```
  Note for the next run: the skill's baseline grep counts **127** frontend files because it includes specs. The production figure is **36**. Do not compare the two.
- **Impact**: `track_repository.py` at 1,066 LOC is 3.5× the limit and is the file every library change touches. Four issues (#4245, #4249, #4250, #4254) were closed in 2026-07 with their targets still 2.3–2.7× over — the reason #4673 introduced the "close only when verified <300 LOC" acceptance criterion.
- **Siblings**: Split axes worth proposing now — `track_repository.py` by read/write/search responsibility; `startup.py` by lifespan phase (DB / player / workers / routers); `chunked_processor.py` by cache-path vs render-path; `playerSlice.ts` by transport vs enhancement state.
- **Related**: #4511 (OPEN), #4673 (CLOSED — the acceptance criterion), #4403 (CLOSED), #4245 / #4249 / #4250 / #4254 (closed prematurely).
- **Suggested Fix**: Re-scope #4511 against the live 105-file census rather than its frozen list of 8, and split it into one issue per file for the top 10 only — each carrying #4673's explicit acceptance criterion (verify <300 LOC at close, otherwise re-scope and keep open). Leave the tail untracked; a 310-line module is not worth an issue.

### TD7-2: CLAUDE.md and `_audit-common.md` both still say the backend pytest baseline does not exist — it was committed yesterday
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `CLAUDE.md:68`, `.claude/commands/_audit-common.md:94`
- **Status**: NEW
- **Age**: stale since `003c9312` 2026-08-12 (one day)
- **Effort**: trivial
- **Description**: `pytest-baseline.json` was generated and checked in on 2026-08-12. Both authoritative documents still describe it as absent, and `_audit-common.md` additionally de-backticks the filename to signal "does not exist" per the path-reference convention — so the convention is now itself carrying a false signal.
- **Evidence**:
  ```
  $ git ls-files pytest-baseline.json
  pytest-baseline.json                       # tracked, 50,162 bytes
  $ git log -1 --format='%h %ad' --date=short -- pytest-baseline.json
  003c9312 2026-08-12
  $ head -c 130 pytest-baseline.json
  { "_comment": "Known-failing pytest tests (#4562). CI fails on any failure NOT listed here. …" }
  ```
  Contradicted by:
  ```
  CLAUDE.md:68
    "`pytest-baseline.json` does not exist yet, so `backend-tests.yml` cannot pass
     until one is generated from a real run."

  .claude/commands/_audit-common.md:94
    "*pytest-baseline.json* at the repo root — generate it with
     scripts/check_pytest_baseline.py if absent (it is not tracked yet)"
  ```
- **Impact**: Both files tell a contributor the backend CI gate is unusable when it is now live and enforcing. Someone acting on CLAUDE.md would regenerate a baseline from a local run — which the same section explicitly warns against ("Generate a baseline from a CI artifact, not a local run") — and overwrite a good CI-derived one with a worse one. That is a real footgun, not just cosmetic rot.
- **Siblings**: Same dual-maintenance hazard as the structural counts (#4982): CLAUDE.md and `_audit-common.md` hold independent copies of the same fact and drift apart when only one is edited.
- **Related**: #4974 (OPEN — filed for the *previous* direction of this drift; it is now closeable), #4562, #4640.
- **Suggested Fix**: Update both lines to state the baseline is checked in and CI-enforced, and re-backtick `pytest-baseline.json` in `_audit-common.md:94` now that the path resolves. Close #4974 in the same change, noting the tree overtook it.

### TD1-1: `get_allowed_directories()` records a deferral as prose instead of `TODO(#NNNN)`
- **Severity**: LOW
- **Dimension**: Stale Markers
- **Location**: `auralis-web/backend/security/path_security.py:85-87`
- **Status**: NEW
- **Effort**: trivial
- **Description**: Genuine marker debt in this repo is zero, which is the project convention working. The convention's counterpart — that deferrals be written as `# TODO(#NNNN):` with a real issue — has one unmet case: a security-relevant function whose deferral is invisible to every marker sweep.
- **Evidence**:
  ```python
  # auralis-web/backend/security/path_security.py:85-87
  Note:
      In production, this should read from configuration.
      For now, we default to user's home directory and standard music folders.
  ```
- **Impact**: The allow-list that backs path containment is hardcoded, and the intent to make it configurable is recorded where no marker sweep can find it — exactly the invisibility #4564 was filed about. Low product impact (Auralis is desktop-only, localhost-bound, and `_extra_allowed_dirs` already accepts runtime scan folders), but it is the one live counterexample to an otherwise clean convention.
- **Siblings**: The other two genuine prose deferrals are already tracked — `auralis/library/scanner/scanner.py:470` is **#4243 (OPEN)** and `auralis-web/frontend/src/hooks/fingerprint/useFingerprintCache.ts:102` is **#4239 (OPEN)**. The remaining six grep hits ("Service temporarily unavailable", "not a workaround", etc.) are ordinary prose, not deferrals.
- **Related**: #4564 (the metric-definition issue this convention came from). Route any containment-bypass concern to `/audit-security`.
- **Suggested Fix**: Either file an issue for config-driven allowed directories and rewrite the note as `# TODO(#NNNN): read the allow-list from UnifiedConfig`, or — since `_extra_allowed_dirs` already covers the real use case — delete the "In production, this should…" sentence as an intention nobody holds.

---

## Deduped — confirmed present, already tracked, not re-filed

| Debt | Live state (verified this run) | Issue |
|---|---|---|
| `BaseRepository._session_scope()` adoption stalled | Now **3 of 16** repo files use it; **81** hand-rolled session sites remain (was "2/14" / "111 sites"). Worth updating the issue's counts. | #4604 (OPEN) |
| `sample_rate=44100` defaults on DSP entry points | Still present (~48 sites). Spot-checked the four most pipeline-central (`calculate_loudness_units`, `tempo_estimate`, `spectral_centroid`, `_compute_phase_correlation`) — **every live call site passes an explicit rate**, so no HIGH promotion is warranted today. | #4622, #4924 (OPEN) |
| `library_manager` dead parameter threaded through `EnhancedAudioPlayer` → `QueueController` | Confirmed: declared at `enhanced_audio_player.py:76` and `queue_controller.py:31`, never assigned in `QueueController.__init__`. | #4312 (OPEN) |
| `useFingerprintCache` DEV-only simulated Web Worker + its three unused exports | Confirmed at `useFingerprintCache.ts:102-125`; zero production consumers (only `hooks/fingerprint/index.ts` re-export and its own spec). | #4239, #4667 (OPEN) |
| `Scanner._update_library_stats()` is a reachable log-only no-op | Confirmed at `scanner.py:466-472`, called from `scanner.py:384`. Impact is nil in practice — `stats_repository.get_library_stats()` computes counts live with `func.count()`, so the `library_stats` table is never read. | #4243 (OPEN) |
| `// X removed (#NNNN)` breadcrumb instances | ~30 live. Instance cleanup is tracked; the missing **guard** is filed above as TD8-2. | #4649, #5034 (OPEN) |
| Skipped tests for removed/deprecated REST endpoints | 5 confirmed in `test_main_api.py` and `test_api_endpoint_integration.py:81`. | #4400 (OPEN) |
| Two identical unreferenced perf skips ("Memory measurement unreliable") | Confirmed at `test_audio_processing_performance.py:708` and `test_memory_profiling.py:307`. | #5024 (OPEN) |
| `docs/subsystems/backend-api.md` still describes `LibraryManager` as startup-constructed | Confirmed still stale. | #5031 (OPEN) |
| Frontend `src/performance/` toolkit is dead code | Confirmed; also accounts for 13 of the 29 shipped `any` usages. | #4696 (OPEN) |
| `_audit-common.md` test-count drift (3rd occurrence) | **Currently in sync** — `check_doc_counts.py` matches the documented 54/20/519/6040/18. Verify before closing. | #5045 (OPEN) |
| `_audit-common.md` falsely claims the backend pytest baseline is checked in | **Resolved by the tree, not by the issue** — `pytest-baseline.json` was committed on 2026-08-12 (`003c9312`) and is git-tracked. #4974 is now closeable, but the docs drifted the other way: see TD7-2. | #4974 (OPEN, closeable) |
| `WAVEncoderError` / `WebMEncoderError` unmapped in the global handler | Confirmed. Fixing TD2-1 first collapses this to a one-file change. | #3912 (OPEN) |

## Deferred

| Item | Gated on |
|---|---|
| Splitting the top-10 oversized Python modules (TD9-1) | #4511 must be re-scoped against the live census first; splitting `startup.py` should also wait on #4764 (startup-rollback shutdown ordering) to avoid two concurrent rewrites of the same lifespan. |
| Re-greening `_audit-validate.sh` for `docs/**` (TD7-1) | A decision on whether the five historical planning trees (`docs/ui_audit/`, `docs/frontend/PHASE*`, `docs/frontend/analysis/`) move to `docs/archive/` — that choice removes ~85 of the 306 refs without editing a line. |

## Not Covered This Pass

- **72 Python `# type: ignore` comments** were counted but not individually validated against current `mypy` output. Establishing which are stale needs a per-module `mypy` run with each ignore conceptually removed — a dedicated pass. Recorded here so the next audit does not mistake the omission for a clean result.
- **Correctness** is out of scope by design. Nothing in this report should be read as a bug finding; the two items closest to correctness (`test_sql_injection_in_title`'s weak assertion, the DC-offset "known limitation") are flagged for `/audit-security` and `/audit-engine` respectively.

---

*Report generated 2026-08-13 against `188db72a`. No GitHub issues were created. No repository files were modified.*

**Next step**: `/audit-publish docs/audits/AUDIT_TECH_DEBT_2026-08-13.md`
