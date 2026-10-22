# Tech-Debt Audit — 2026-10-21

**Scope**: whole repo (`auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/`, `tests/`, docs, `.claude/` skills and agents). All 10 dimensions, `--depth deep`, no `--limit`.
**HEAD**: `db9cc2e7` (2026-10-21). 381 commits since the previous tech-debt audit (`AUDIT_TECH_DEBT_2026-09-13.md`).
**Method**: one Sonnet subagent per dimension (max 3 concurrent), dedup against 178 open issues + 453 `tech-debt`-labelled issues (all states), orchestrator merge with spot-verification of the load-bearing claims.

---

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 86 |
| **Total** | **88** |

| Dim | 1 Markers | 2 Dead code | 3 Duplication | 4 Magic nums | 5 Stubs | 6 Tests | 7 Docs | 8 Compat | 9 Complexity | 10 Audit rot |
|---|---|---|---|---|---|---|---|---|---|---|
| Findings | 0 | 20 | 14 (2 MEDIUM) | 7 | 5 | 6 | 6 | 11 | 12 | 7 |

Dim 1 has no findings left after the merge: its two were folded into #5738 and TD2-04 (see Merge Log).

Plus one `Existing: #5481` update (TD9-10, listed under Deferred) and ~70 open issues confirmed as already tracking adjacent debt (not re-reported).

**Direction.** Every finding from the 2026-09-13 report that was published is fixed and has stayed fixed (39 of 40 published issues closed; the open one is the informational #5481). The headline counters moved the right way: `type: ignore` 67 → 51, `'any'` non-test 14 → 3, `NotImplementedError` 3 → 0, Python skips 46 → 35, frontend skips 16 → 0 (the census reads 3, all string matches inside a guard test), `sample_rate=44100` defaults 30 → 22 (two deleted files, zero new sites). The seven largest backend files of the last report were all split.

**Where the debt is now.** Four shapes account for most of the 88:

1. **Deletion without follow-through** (Dims 2, 7, 10). This month's big "delete the dead X" commits left orphans one layer down: `hf_aware_limiter.py` after #5577 (TD2-04), `queue_shuffler.ts` after #5642 (TD2-05), `SmartCache`/`MemoryPool`/`SIMDAccelerator` after #5325 (TD2-07), `chunk_crossfade.py` after #5366 (TD2-14). They also left stale doc refs. **The path-reference gate (`path-references.yml`) is red on master**, verified: the last 6 runs failed, the latest at 2026-10-22T00:17Z. Two causes: the queue-history retirement (#5526, TD7-01) and the #5642/#5521 frontend deletions (TD7-02).
2. **Whole subsystems with no production caller**. The preference-learning write path, about 900 lines (TD2-01). 9 of the 11 PyO3 bindings, about 2,800 lines of Rust (TD2-02). `reference_library.py` (TD2-03). `recording_type_detector.py` (TD2-18). Several are product calls, not mechanical deletions.
3. **Copy-paste where a fix landed in only some copies.** Both MEDIUMs are here:
   - **TD3-01**: the enhanced and seek stream pumps are hand-synced copies. The seek copy's own comments record two fixes that missed it the first time. The drift is live today: the enhanced pump's DSP-timeout branch sends no `recovery_position`, while the seek copy's identical branch does (verified at `stream_enhanced_chunks.py:165-169` vs `stream_seek_chunks.py:184-189`).
   - **TD3-02**: #5262's per-request router-deps isolation was pasted into 6 routers. 4 siblings (`albums`, `enhancement`, `library_scan`, `player_deps`) still use the overwritten-singleton pattern #5262 removed.
4. **Coordinator regrowth** (Dim 9). Closed split targets keep re-crossing 300 LOC through unrelated bug fixes:
   - `enhanced_audio_player.py` is at 314 (Regression of #4249).
   - `chunked_processor.py` is at exactly 300.
   - `hybrid_processor.py` is at 419, past its own documented waiver of 415.

   Nothing gates LOC after an issue closes (TD9-01).

**Severity calls made at merge.** Dimension agents proposed MEDIUM for TD7-01 (stale audit-tooling docs and the red gate) and TD10-01 (`/verify-release`, `/fix-issue` and `/gen-test` run the hanging whole suite with npm). Neither strictly matches a promotion row. The "stale audit baseline that has misled an audit" row needs a demonstrated misled audit, and none is shown. Both are recorded as LOW, but they rank first and third in the Quick Wins below. No HIGH trigger fired:
- Dim 3 swept every DSP family for a copy that drops `.copy()`, a sample-count guard or a NaN guard that a sibling has, and found none.
- Dim 4 found no hardcoded rate feeding samples↔seconds maths.

**Possible real bugs surfaced in passing.** These are routed to their owning audits and not counted as debt:
- The enhanced-pump timeout branch lacks `recovery_position` (TD3-01, `/audit-backend`).
- The `AURALIS_PORT` override is not applied to the origin allow-list's `BACKEND_PORT`, so a non-default port may be rejected (TD4-02, `/audit-backend`, unverified).
- `LibraryScanner`'s `except AttributeError: pass` guards make the scan-slot concurrency guard fail open (TD5-01, `/audit-concurrency`).
- A settings *reset* toasts "Settings saved successfully" (TD5-03, `/audit-frontend`).
- `check_normalization_side_effects` ignores its `post_dynamics` argument, which may be a dropped check (TD8-03, `/audit-engine`).
- Two misplaced `# type: ignore`s expose a live `arg-type` error, so `mypy auralis-web/backend` is not clean today (TD2-20).

---

## Baseline Snapshot

Captured 2026-10-21 at `db9cc2e7` with the Phase 1 greps in `.claude/commands/audit-tech-debt.md`. Labels follow the #4564 metric notes.

| Metric | 2026-10-21 | 2026-09-13 | Read it as |
|---|---|---|---|
| markers, genuine (src) | **2** | 0 | `security_headers.py:96` `TODO(#5484)`: the issue is OPEN, so the marker is legitimate. `py_bindings.rs:765` `TODO(#5537)`: #5537 is **CLOSED** (2026-10-18, docstring-only fix). This is the closed-issue marker shape from #5143. It is not filed separately because open #5738 already names it; retarget it to `TODO(#5738)` or delete it with the binding. |
| markers, genuine (tests/) | **0** | 3 | The three TODO(#5172)/TODO(#5174) markers were removed properly; both issues closed with in-place decision comments. |
| markers, raw (pre-filter) | 3 | 2 | Diagnostic only. The gap is `errorTrackingMiddleware.test.ts:451` (`0.xxxxxxxx`), a filtered false positive. |
| prose deferrals (non-test) | 10 | 8 | 1 genuine untracked deferral: `continuous_dsp_ops.py:285` "revisit if peaky-chunk loudness loss matters" (merged into TD2-04). The other 9 are ordinary prose (503 copy, "501 Not Implemented", the umask explanation, "not a workaround", "Settled decision", and the `TODO(#5484)` line double-counted). |
| NotImplementedError | **0** | 3 | `duplicate_detector.py` was deleted whole (`aedab0dc`, #5362). |
| type: ignore (py) | 51 | 67 | `mypy --warn-unused-ignores` over the 27 files: 3 unused, 2 of them misplaced and hiding a real error (TD2-20). |
| @ts-ignore/@ts-expect-error | 10 | 2 | Not a regression. 2 are in `test/setup.ts`, 4 are deliberate type-level assertions in `apiRequest.typePredicate.test.ts` and `errorHandling.WebSocketManager.test.ts` (an unused `@ts-expect-error` *is* their failure signal), and 4 are comment lines mentioning the directive. 0 are in shipped code. |
| 'any' non-test (ts) | **3** | 14 | `loggerMiddleware.ts:93,160` and `Text.tsx:102` (`ref as any`). The `useAlbumDetails.ts` and `serviceFactory.ts` hits are gone. |
| 'any' raw incl. tests (ts) | 496 | 486 | Trend continuity only. |
| skipped tests (py) | 35 | 46 | 1 cites an open issue (#5187), 2 are strict xfails (#5191, open), 1 is a fixture-wide skip (#5685, open), and 4 are unconditional skips citing no issue (TD6-03). The rest are platform or dependency skips. |
| skipped tests (ts) | 3 (**0 real**) | 16 | All 3 hits are the string `describe.skip` inside the guard test `integration-tests-exercise-production-code.test.ts`. #5179/#5186 are resolved. |
| py files >300 LOC | 89 | 88 | Dim 9 re-measured 90 later in the run (95 at `c870728a` by the same command). 42 files grew and 7 newly crossed 300. |
| ts/tsx files >300 LOC | 104 | 113 | 25 shipped + 79 test (was 28 shipped). |
| allow(dead_code) (rust) | 0 | 0 | Clean, but `rustc` cannot see the dead `pub mod`s; see TD2-02. |
| sample_rate=44100 defaults | 22 | 30 | **A drift indicator, not a debt count** (#4924). −8 come from two deleted files: `core/analysis/content_analysis_facade.py` (7 sites, `139f8bd4` #5207) and backend `analysis/analysis_extractor.py` (1 site, `34a3fe4b` #5085). There are **zero new sites**, and the file list is otherwise identical to 2026-09-13. |

Other gates checked this run:
- **`_audit-validate.sh` exit 1.** Strict scope has 4 stale refs; the ratchet has 295 against a baseline of 287 (8 new). See TD7-01/02.
- **`scripts/check_doc_counts.py`.** It reports 12 repositories against 13 in three skill files, and 701-702 test files / 7,195-7,207 functions against the documented 611 / 6,759. See TD7-03.
- **Baseline files.** `pytest-baseline.json` has 127 entries, 2 of them phantom (TD6-05); the docs say 157. `test-baseline.json` has 101, 2 of them phantom; the docs say 108.
- **Version.** `auralis/version.py`, `pyproject.toml`, all `package.json` files and README agree on 1.5.1.
- **DB schema.** v22 (`auralis/__version__.py:11`); CLAUDE.md says v21 and `_audit-common.md` says "through v017_to_v018" (TD7-03).

---

## Top 10 Quick Wins (trivial/small effort)

| # | ID | Effort | Win |
|---|---|---|---|
| 1 | TD7-01 + TD7-02 | trivial | **Turn the red path-reference gate green.** De-backtick 3 queue-history refs and 1 frontend test ref, fix the 8 ratchet-new refs, and change "13 repos" to "12" in 5 places. Every PR currently shows a failing check unrelated to its change. |
| 2 | TD6-05 | trivial | Remove the 4 phantom baseline entries (tests that no longer exist; they silently re-permit any future test reusing the name), plus the ~31 entries for files that now pass. These are probably what keeps `backend-tests.yml`'s `--strict-stale` red. |
| 3 | TD10-01 | small | Make `/verify-release` Gates 4/5/9, `/fix-issue`'s final gate and `/gen-test` use the CI commands (the two `--ignore`s, the baseline checkers, `pnpm`). As written, Gate 4 hangs and cannot ever PASS. |
| 4 | TD2-19 + TD2-20 | trivial | Delete 5 unused imports/locals and fix 3 stale or misplaced `type: ignore`s. This makes `mypy auralis-web/backend` clean again. |
| 5 | TD2-03 + TD2-14 | trivial | Delete two whole dead modules: `learning/reference_library.py` (357 lines, zero importers including tests) and `core/chunk_crossfade.py` (test-only), plus the three stale "crossfade math lives in…" docstring sentences. |
| 6 | TD2-04 (+TD1-02) | small | Delete `hf_aware_limiter.py` (no production importer since #5577) and its tests, and replace the untracked "revisit if…" deferral with a one-line history note. |
| 7 | TD4-02 | trivial | Make `config/origins.py` the single source for the backend port (`get_int_env("AURALIS_PORT", 8765)`) and import it in `main.py`. This removes a possible origin-rejection on non-default ports. |
| 8 | TD10-02 | trivial | Change the 11 dedup commands to `--state all`. Today the documented "CLOSED match → Regression of #NNN" branch cannot fire, because closed issues are never in the dedup file. |
| 9 | TD7-05 + TD7-06 | trivial | Drop the 5 deleted modules from the PyInstaller `hiddenimports`, and `git rm quick_build.sh`, which calls the long-gone `build_auralis.py`. |
| 10 | TD10-03 + TD10-04 | trivial/small | Fix `library-specialist.md`'s "schema v18" claims and its unsatisfiable "every migration has up and down" item. Repoint the 4 `audit-regression` seed rows whose files no longer hold the fix (they would generate false HIGH regressions). |

---

## Top 5 Medium Investments

| # | ID | Effort | Investment |
|---|---|---|---|
| 1 | **TD3-01** (MEDIUM) | medium | Collapse `pump_enhanced_chunks`/`pump_seek_chunks` into one parameterised pump, and hoist the pause/flow gate out of `routers.system` into `core/`. This fixes the live `recovery_position` divergence as a side effect. |
| 2 | **TD3-02** (MEDIUM) | small+small | Add one `RouterDeps[T]` helper in `routers/dependencies.py` and migrate all 10 routers to it, including the 4 still on the overwritten singleton. Extend the #5262 isolation test to the full list. |
| 3 | TD2-01 / TD2-02 / TD2-07 | medium–large | Make three product decisions and delete what loses: the preference-learning write path (about 900 lines, untested), the 9 unwired PyO3 bindings (about 2,800 lines of Rust; coordinate with #5738), and the idle `SmartCache`/`MemoryPool`/`SIMDAccelerator`. Together this is the largest LOC reduction available. |
| 4 | TD4-01 | medium | Make `FingerprintUnpacker` the only holder of fingerprint defaults. 92 raw `fp.get('<dim>', <default>)` fallbacks across 17 files have already drifted; for example, the LUFS fallback is −14, 0 or −20 depending on the file. |
| 5 | TD9-01 (+TD9-02/03) | small, then medium per router | Add `scripts/check_loc_ratchet.py` with ceilings for the closed split targets, wired into `backend-tests.yml`, so split work stops regressing. Then apply the #5472 models/deps/sub-resource recipe to the 10 bundled routers and the #5166 recipe to the 8 closure-factory routers. |

---

## Findings

### HIGH (0)

None. No promotion trigger fired: no DSP copy drops `.copy()`, a sample-count guard or a NaN guard that its sibling has (Dim 3 sweep), and no hardcoded rate or chunk constant feeds audio length or position maths (Dim 4 sweep).

### MEDIUM (2)

##### TD3-01: The three stream pumps and handlers are hand-synced copies; a fix lands in one and the sibling lags (or still lacks it)
- **Severity**: MEDIUM (promotion row: duplicated logic with divergent bug-fix history; named fix commits below)
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/core/stream_enhanced_chunks.py:42-213` vs `stream_seek_chunks.py:43-235` vs `stream_normal_chunks.py`; handler skeletons `stream_enhanced.py:41-310` vs `stream_seek.py:41-302` vs `stream_normal.py`
- **Status**: NEW (follow-up to closed #5032, which extracted the loops but left them as parallel copies; #5403 only deduplicated the result dataclass)
- **Age**: `71e65a55` 2026-08-26 (#5032 extraction); drift history `4d861dd4` 2026-08-07 (#5074)
- **Effort**: medium
- **Description**: `pump_enhanced_chunks` and `pump_seek_chunks` are the same loop. The only intended differences are `range(start_chunk_idx, ...)`, the first-chunk seek trim, and the recovery position for the first chunk. The rest (enhancement-toggle stop, pause/flow gating, look-ahead task and drain, `ConnectionError`, `TimeoutError`, generic-exception branches, `failed_chunks`) is copied. The handlers repeat the same semaphore, cancel-event, processor-instantiation-timeout and metadata-validation skeleton.
- **Evidence** (drift already recorded in the code's own comments):
  - `stream_seek_chunks.py:166-169`: "Lifted from stream_enhanced.py's #4999 fix, which never reached this structurally identical seek-path loop (#5074)".
  - `stream_seek_chunks.py:77-79`: "fixes missing pause check in seek path — pre-existing bug".
  - `error_code="SEEK_ERROR"` was added only to the seek copy (`cc61d3b8`, #3909).
  - **Still divergent today**: the enhanced pump's `TimeoutError` branch (`stream_enhanced_chunks.py:166-170`) calls `_send_error(...)` with no `recovery_position`. The seek copy of the identical branch (`stream_seek_chunks.py:183-190`) sends `recovery_position`. In the enhanced file the sibling `not delivered` and generic-exception branches do send it, so a client that hits a chunk-DSP timeout on a normal enhanced play cannot resume from the failed chunk.
  - Metadata validation differs: `stream_enhanced.py:167-169` loops over `getattr(processor, attr)` and raises `AttributeError` if `processor` is None. `stream_seek.py:159-178` has a `processor is None` check plus five hand-written checks.
- **Impact**: Every streaming fix has to be remembered 2-3 times. Already happened twice (#4999→#5074, #2106 pause check). The seek copy is the more recently corrected one, so the enhanced path is the one that now lags.
- **Siblings**: the `from routers.system import _stream_pause_events, _stream_flow_events` gate block is pasted in all three pumps (`stream_enhanced_chunks.py:74-80`, `stream_seek_chunks.py:77-86`, `stream_normal_chunks.py:109-116`). It imports private names from a router module into `core/`, an inverted layering.
- **Related**: #5258 (seek single-flight, open); owning audit `/audit-backend`. The missing `recovery_position` on the enhanced timeout branch is a small correctness gap; hand it to `/audit-backend` if the consolidation is not scheduled.
- **Suggested Fix**: Collapse `pump_enhanced_chunks` and `pump_seek_chunks` into one `pump_chunks(..., start_chunk_idx=0, seek_offset=0.0, effective_position=None, error_code=None)` in `stream_enhanced_chunks.py`. Seek is the enhanced pump with a non-zero start and a first-chunk trim. Hoist the pause/flow gate into one `await wait_for_stream_gates(websocket)` in `stream_protocol.py`, with the registry passed in or owned by `core/` so `core/` stops importing from `routers.system`. Share the processor-metadata validation as one helper.

##### TD3-02: Per-request router dependency isolation (#5262) was applied to 6 routers by copy-paste; 4 siblings still use the overwritten-singleton the fix removed
- **Severity**: MEDIUM (promotion row: duplicated logic with divergent bug-fix history; fixed in `playlists`, `artwork`, `metadata`, `files`, not in `albums`, `enhancement`, `library_scan`, `player_deps`)
- **Dimension**: Logic Duplication
- **Location**: ContextVar copies at `routers/playlists.py:153-170`, `artwork.py:304-321`, `metadata.py:264-281`, `files.py:152-169`, `similarity.py:159-180`, `processing_deps.py:70-90`. Unfixed singletons at `albums.py:139` + `:394`, `enhancement.py:139` + `:751-755`, `library_scan.py:168` + `:504-505`, `player_deps.py:59` + its factory.
- **Status**: NEW (follow-up to closed #5262, `afcd0bca`)
- **Age**: `afcd0bca` 2026-09-03
- **Effort**: small (helper) + small (migrate 4)
- **Description**: #5262 fixed the "second `create_*_router()` call repoints the live router's deps at test mocks" bug by porting a ContextVar and `_make_deps_binder` pattern into four routers one at a time. The same ~15 lines (`_active_deps` ContextVar, `_current_deps()`, `_make_deps_binder()`, the "publish this router's deps" `_bind_deps`) now exist six times with slight shape differences (`similarity`/`processing` use different defaults). `tests/backend/test_router_dependency_isolation_5262.py` covers only the 4 fixed ones.
- **Evidence**: `albums.py:117-125` still asserts "nothing in this codebase calls create_albums_router() more than once in the same process", the claim #5262 showed empirically false for its siblings. `create_enhancement_router(` is called 10 times across 6 test files, `create_library_scan_router(` 12 times across 8, `create_player_router(` 6 times across 4.
- **Impact**: The bug class #5262 closed (order-dependent false pass/fail across the suite) is still open for the enhancement, library-scan, player and albums routes. Future routers will copy whichever variant they open first.
- **Siblings**: the trivial accessors `_get_connection_manager()` (5 copies: `player_deps.py:74`, `enhancement.py:151`, `artwork.py:323`, `playlists.py:172`, `library_scan.py:181`) and `_get_repository_factory()` (3 copies: `metadata.py:283`, `albums.py:142`, `enhancement.py:169`).
- **Related**: #5262, #5177 (closed); owning audit `/audit-backend`.
- **Suggested Fix**: Add a small `RouterDeps[T]` helper to `routers/dependencies.py` that owns the ContextVar, `current()` and `make_binder()`. Migrate all 10 routers to it, then extend the #5262 isolation test to the full list.

### LOW (86)

#### Dimension 2: Dead Code & Unused Surface

##### TD2-01: The user preference-learning write path is unreachable (about 900 lines, zero tests)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/core/hybrid_processor.py:353-386` (`set_user`, `record_user_feedback`, `record_parameter_adjustment`, `get_user_insights`, `save_user_preferences`); `auralis/core/hybrid/preference_manager.py:21-96` (all of `PreferenceManager` except `set_content_profile`); `auralis/learning/preference_engine.py:27-391`; `auralis/learning/components/{models,predictor}.py` (210 lines); `auralis/core/analysis/target_generator.py:59-65` (the `current_user_id` branch)
- **Status**: NEW
- **Age**: `36ce3c81` 2025-09-29 (HybridProcessor + engine), `9d5c9ecf` 2025-10-02 (PreferenceManager). It was never called from any shipped surface.
- **Effort**: medium
- **Description**: `HybridProcessor.set_user()` is the only way to give the processor a `current_user_id`. Nothing in `auralis/`, `auralis-web/`, `scripts/`, `desktop/` or `tests/` calls it. `current_user_id` therefore stays `None` (`hybrid_setup.py:122`). `target_generator.py:59` only consults `preference_engine.get_adaptive_parameters` when that attribute is truthy. `PreferenceManager.record_feedback`/`record_adjustment` also bail when no user is set. Every record/save/insight method on `HybridProcessor` is likewise uncalled. The only live use is `preference_manager.set_content_profile()` (`hybrid_processor.py:268`), which stores a value no one reads. `git grep` for `PreferenceLearningEngine`, `PreferenceManager`, `create_preference_engine` and `record_user_action` in `tests/` returns nothing, so the learning logic is also untested.
- **Evidence**: `git grep -n "set_user\b"` -> only the two definitions and the delegating call at `hybrid_processor.py:361`. `git grep -n "record_user_action\|get_or_create_user"` -> only `preference_manager.py:33,62,79`.
- **Impact**: Constructing every `HybridProcessor` runs `create_preference_engine()` (`hybrid_setup.py:85`), which does `Path.home()/".auralis"/"preferences"` `.mkdir()`, a filesystem side effect for a feature that cannot fire. Audits keep reading this as live "learning" code (`docs/MASTER_ROADMAP.md:135` lists it as a roadmap item).
- **Siblings**: `auralis/learning/__init__.py` re-exports (`UserProfile`, `UserAction`, `create_preference_engine`); `PreferenceLearningEngine.cleanup_old_data` and `get_learning_statistics` (zero callers even inside the cluster); `HybridProcessor.preference_engine` / `preference_manager` annotations.
- **Related**: Product call (wire it in or delete). Same shape as #4750 (closed, `learning_system.py`) and #4592 (closed, `personal_preferences.py`), the earlier deletions in this package.
- **Suggested Fix**: Delete the 5 `HybridProcessor` delegates, `PreferenceManager`, `preference_engine.py`, `learning/components/`, the `current_user_id` branch in `target_generator.py` and the `hybrid_setup.py` construction. Keep only `reference_seeder.py` in `learning/` (live via `refresh_cloud`). If the feature is still wanted, open an issue to expose `set_user` from the player and add tests.

##### TD2-02: 9 of the 11 PyO3 bindings have no production Python caller; about 2,800 lines of Rust exist for tests and benchmarks
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs` (registrations at `:29-65`); `hpss.rs` (400), `yin.rs` (540), `tempo.rs` (280), `compressor.rs` (342), `limiter.rs` (319), `envelope.rs` (206), `biquad_filter.rs` (208), `onset_detector.rs` (250), `chunk_processor.rs` (250)
- **Status**: NEW for `hpss`, `yin`, `chroma_cqt`, `detect_tempo`, `envelope_follow`, `compress`, `limit`, `apply_multiband_eq`, `detect_onsets`. `process_chunks` is already tracked as #5738 (OPEN); #5537, which held its TODO, was closed by a docstring fix only.
- **Age**: The Python callers were removed by `29650ea0` 2026-07-12 ("remove dead sampling/librosa fingerprint subsystem") and earlier refactors (`2a5d7635` 2025-11-29). `detect_tempo` was deliberately never wired (`auralis/dsp/utils/spectral.py:223-236`, #5168).
- **Effort**: large (a product decision, not a deletion; decompose first)
- **Description**: In `auralis/` and `auralis-web/backend/` the only `auralis_dsp` imports are for `compute_fingerprint` (`rust_fingerprint.py:164-166`, `fingerprint_generator.py:37`). `hpss`, `yin`, `chroma_cqt` and `apply_multiband_eq` are exercised only by `tests/test_*_rust_validation.py`, `test_phase5_rust_benchmark.py`, `test_pyo3_channel_axis_guards_4502.py` and `tests/vendor/test_rust_panic_handler.py`. `envelope_follow` and `detect_onsets` have no caller at all, tests included. `compress` and `limit` have no production caller either. `rustc` cannot flag any of this because every module is `pub mod` in a lib crate. `chroma.rs` is the exception: `fingerprint_compute.rs:543` calls `chroma::chroma_cqt`. Only `compute_fingerprint` and its dependencies (`fingerprint_compute`, `frequency_analysis`, `spectral_features`, `stereo_analysis`, `variation_analysis`, `rhythm`, `dsp_math`, `chroma`) are live.
- **Evidence**: `grep -rn "auralis_dsp" auralis auralis-web/backend --include='*.py'` shows 2 import sites, both `compute_fingerprint`. `CLAUDE.md` still advertises "Rust DSP via PyO3 (HPSS, YIN, Chroma)".
- **Impact**: The crate costs `maturin develop` (a documented first-run requirement) and a CI desktop build for four targets. About 2,800 lines of unused Rust sit in the build, and an audit that finds a bug in `hpss.rs` or `limiter.rs` is auditing code no user reaches.
- **Siblings**: `biquad_filter.rs:51` `BiquadFilter::highpass` (no caller even in Rust); `frequency_analysis.rs:22` `to_array` (no caller). Both are `pub fn`s that `rustc` cannot warn about.
- **Related**: #5738 (OPEN, `process_chunks`), #5537 (closed), #4594 (closed; earlier Rust pub-fn sweep).
- **Suggested Fix**: One decision issue: either drop the 9 bindings and their private modules (keeping `compute_fingerprint`'s dependency closure) together with the related validation and benchmark tests, or name an owner for each binding that will wire it in. Update `CLAUDE.md` accordingly.

##### TD2-03: `auralis/learning/reference_library.py` is a whole dead module (357 lines)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/learning/reference_library.py:1-357`
- **Status**: NEW (a leftover of the closed #5372, which deleted only the four accessor functions)
- **Age**: Orphaned by `d62c9c1c` 2026-08-22 (#4592 deleted `reference_analyzer.py`, its only consumer). #5372 (`44e6ec81` 2026-09-15) removed the helper functions but left the data.
- **Effort**: trivial
- **Description**: After #5372 the module holds the `MasteringEngineer`, `Genre` and `ReferenceTrack` types and the `REFERENCE_LIBRARY` and `ENGINEER_PROFILES` tables. `git grep reference_library -- '*.py'` returns no match anywhere, tests included. `learning/__init__.py` does not import it, and `reference_seeder.py` is a different module.
- **Impact**: 357 lines of static data that look like a live reference set. They also contribute a `sample_rate=44100` default to the drift census.
- **Siblings**: Listed in `.claude/commands/_audit-common.md:25` and `.agents/skills/source-command-audit-common/SKILL.md:33`; `docs/MASTER_ROADMAP.md:135`.
- **Suggested Fix**: Delete the file and remove it from the two layout tables.

##### TD2-04: `hf_aware_limiter.py` is now a test-only module after #5577 removed its only call site
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/core/processing/hf_aware_limiter.py:1-145`; comment `auralis/core/processing/continuous_dsp_ops.py:281-286`
- **Status**: NEW (follow-through of closed #5577, which kept the module deliberately)
- **Age**: Orphaned by `3a72a371` 2026-10-20
- **Effort**: small
- **Description**: `continuous_dsp_ops.py` no longer imports it. The remaining consumers are 4 test files: `test_hf_aware_limiter.py`, `test_hf_aware_limiter_dtype.py`, `test_bypass_copy_contract_5107.py` and `test_post_limiter_invariants_5533.py`. They pin dtype, bypass-copy and invariant fixes (#4105, #5107, #5533) for code with no production path.
- **Impact**: Three closed regression issues keep "guarding" dead code, so a future audit will re-read it as live. `.claude/commands/audit-engine.md:25` lists it as an active module.
- **Related**: #5577 (closed), #5107, #4105
- **Suggested Fix**: Delete the module and its tests (or the relevant cases), and drop the name from `audit-engine.md`. If the limiter is meant to return, file an issue instead of keeping the file.
- **Merged — TD1-02 (Dim 1, Stale Markers)**: the `continuous_dsp_ops.py:279-285` comment left by #5577 (`3a72a371`, 2026-10-20) ends in an untracked conditional deferral, "revisit if peaky-chunk loudness loss matters". There is no `TODO(#NNNN)` and no issue, which violates CLAUDE.md Principle 5, and it is the only stated reason the module is kept. Delete it with the module and leave a one-line history note. If the concern is real, file an issue and write `# TODO(#NNNN): ...` instead.

##### TD2-05: The queue "extras" logic layer (about 2,000 lines of hooks and utils) is dead behind the orphaned panels; `queue_shuffler.ts` was orphaned today
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis-web/frontend/src/utils/queue/queue_shuffler.ts` (383), `queue_recommender.ts` (469), `queue_statistics.ts` (394), `trackFormat.ts` (44); `src/hooks/player/useQueueSearch.ts` (270), `useQueueStatistics.ts` (216), `useQueueRecommendations.ts` (228)
- **Status**: NEW. It extends #5628 (OPEN), which lists only components. `ShuffleModeSelector.tsx`, named in #5628, no longer exists.
- **Age**: `queue_shuffler.ts` orphaned by `05cbb1c1` 2026-10-21 (#5642). The rest has been orphaned since the panels were unmounted.
- **Effort**: small
- **Description**: `queue_shuffler.ts` now has no importer except its own tests (and `Phase7Integration.test.tsx`); #5642 deleted the only component that used it. The other two utils and the three hooks are reachable only from the panels #5628 already lists (`QueueRecommendationsPanel`, `QueueSearchPanel`, `QueueStatisticsPanel`) and from the barrel `hooks/player/index.ts:15-17`. A line-level grep shows no other production consumer.
- **Impact**: Deleting the panels per #5628 leaves about 2,000 lines plus their tests, which is the "silently orphan the next layer" trap #5129 describes for selectors.
- **Siblings**: `hooks/enhancement/useMasteringRecommendation.ts` (110 lines; importers are only its test and the unused `hooks/enhancement/index.ts` barrel); `hooks/shared/useAutoHide.ts` and `useAPIHealthPoll.ts` (consumed only by the orphaned `ConnectionStatusIndicator`, covered by #5628 and #5615).
- **Related**: #5628, #5129 (same pattern), #5642 (closed)
- **Suggested Fix**: Extend #5628's deletion list with these files and their tests, in one pass. Delete `queue_shuffler.ts` now.

##### TD2-06: `quality_assessors` carries about 470 lines of helper methods that nothing calls
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/analysis/quality_assessors/base_assessor.py:55-239` (`get_assessment_category`, `_normalize_audio`, `_to_mono`, `_get_stereo_channels`, `_validate_audio`, `_compute_rms`, `_compute_spectrum`, `_interpolate_score`, about 178 lines); `utilities/estimation_ops.py:187-440` (`estimate_dynamic_range`, `detect_phase_issues`, `estimate_stereo_width`, `estimate_mono_compatibility`, `detect_excessive_noise`, `detect_excessive_distortion`, about 190 lines; `estimate_fundamental_frequency` is test-only, 49 lines); `utilities/scoring_ops.py:152` `percentile_score` (48); `utilities/assessment_constants.py:195` `is_compliant_with_standard`
- **Status**: NEW
- **Age**: introduced `1c1514b0` / `19c64a58` 2025-11-29; no caller added since (`git log -S`).
- **Effort**: small
- **Description**: The five assessors under `analysis/quality/` subclass `BaseAssessor` but call none of its 7 helpers; each carries its own audio prep. Of the 11 `EstimationOperations` static methods, only `estimate_thd`, `detect_clipping`, `estimate_noise_floor` and `compute_stereo_correlation` are used. Several duplicate math that lives elsewhere (`phase_correlation.py`, `loudness_meter.py`).
- **Evidence**: Per-name `grep -w` across `auralis/`, `auralis-web/`, `scripts/` and `tests/` returns only the `def` line for each name above (except `estimate_fundamental_frequency`, 3 test hits).
- **Impact**: Open correctness issues #5714 and #5745 concern the same assessors, and a fix could be applied to a helper no assessor runs.
- **Siblings**: `auralis/analysis/spectrum_operations.py:297,322` `calculate_spectral_spread`, `calculate_spectral_flatness` (49 lines, zero callers).
- **Suggested Fix**: Delete the helpers (BaseAssessor keeps `assess`, `detailed_analysis`, `clear_cache`) and the unused static methods.

##### TD2-07: `SmartCache`, `MemoryPool` and `SIMDAccelerator` survive #5325; their only "consumer" is a dead stats method
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/optimization/caching/smart_cache.py:1-199`, `memory/memory_pool.py:1-100`, `acceleration/simd_accelerator.py:15-93`; `performance_optimizer.py:44-71`; `auralis/core/hybrid_processor.py:384-386` (`get_performance_stats`)
- **Status**: NEW
- **Age**: `a31a790c` 2025-11-05 (SIMD); #5325 `ede0fa1d` 2026-10-19 deleted the apply-points but kept the objects.
- **Effort**: small
- **Description**: `PerformanceOptimizer.__init__` builds a `SmartCache` and a `MemoryPool` "so `get_optimization_stats()` can report them". `get_optimization_stats` has exactly one caller, `HybridProcessor.get_performance_stats()`, which nothing calls. `SIMDAccelerator` is not constructed anywhere and its four static methods have no caller, tests included; it survives as a re-export in `optimization/__init__.py:11,30`. The module docstring concedes "the cache is never filled and the pool never dispenses". `SmartCache.clear_expired` is likewise uncalled.
- **Impact**: Two idle objects are allocated at import time of the main pipeline. The only live piece of the package is `PerformanceProfiler`, so the "live engine code, full severity" label in `_audit-common.md` wrongly covers the whole package. Two test suites (`test_smart_cache_key_4524`, `test_memory_pool_dtype_key_4992`) pin dead code.
- **Related**: #5325 (closed), #5142 (closed; the importers gate stays valid for the profiler), #4524, #4992
- **Suggested Fix**: Delete `SIMDAccelerator`, `SmartCache`, `MemoryPool` and `HybridProcessor.get_performance_stats`. Let `get_optimization_stats` report only the profiler. Update `scripts/check_optimization_importers.py` and the `_audit-common.md` Optimization row.

##### TD2-08: Ten `create_*` convenience factories and `energy_profile` have no caller anywhere
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/core/config/factory.py:17,29,41` (`create_adaptive_config`, `create_reference_config`, `create_hybrid_config`); `core/analysis/content_analyzer.py:402`; `core/analysis/target_generator.py:380`; `dsp/dynamics/compressor.py:204`; `dsp/dynamics/envelope.py:58`; `dsp/eq/parallel_eq_processor/factory.py:15`; `optimization/performance_optimizer.py:93`; `player/components/queue_manager.py:488`; `dsp/utils/spectral.py:179` (`energy_profile`)
- **Status**: NEW (the closed #5201 covered three other factories)
- **Age**: 2025-09-29 to 2025-10-24 (`git log -S"def <name>"`)
- **Effort**: trivial
- **Description**: Each is re-exported from a package `__init__.py` (`auralis/__init__.py:24-25,49-50` exports two of the config factories as public API). Per-name grep over `auralis/`, `auralis-web/`, `scripts/`, `desktop/`, `launch-auralis-web.py` and `tests/` finds only the `def` and the `__init__` re-export. No docs mention them either.
- **Impact**: Parallel construction paths for `UnifiedConfig` and others invite a second way to configure the engine. `auralis/__init__.py` advertises the factories as public API with no consumer.
- **Suggested Fix**: Delete them and their `__init__` re-exports. For `auralis/__init__.py`, confirm no external package imports `create_adaptive_config` before removal.

##### TD2-09: Analysis layer: dead methods in the mastering-profile, fingerprint and spectrum modules
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/analysis/adaptive_mastering_engine.py:334-391` (`analyze_and_recommend`, `analyze_album_and_recommend`, `get_profile_database`, `export_profiles`, `import_profiles`, 42 lines); `mastering_profile.py:158,189,238` (`to_yaml_str`, `from_yaml_str`, `find_best_profile`); `mastering_fingerprint.py:185` (`to_json`); `phase_correlation.py:269` (`analyze_stereo_field`, 68 lines); `fingerprint/distance.py:116,122,136` (`equal_weights`, `frequency_focused`, `dynamics_focused`); `fingerprint/normalizer.py:265,375` (`normalize_batch`, `get_stats_summary`); `fingerprint/similarity.py:348,360` (`save_normalizer`, `load_normalizer`); `fingerprint/knn_graph.py:201` (`update_graph`); `ml/features.py:83` (`get_feature_names`); `quality/mastering_evaluation.py:27` (`evaluate_audio`)
- **Status**: NEW
- **Age**: 2025-09-17 (`phase_correlation`) to 2025-11-27 (`adaptive_mastering_engine`, `mastering_profile`)
- **Effort**: small
- **Description**: Per-name grep over the whole repo, tests included, returns only the definition. The live parts of these modules are `AdaptiveMasteringEngine.recommend_weighted` (via `chunk_mastering.py:69`) and the fingerprint distance and normalizer cores. `mastering_profile`'s YAML helpers are API for a profile editor that does not exist.
- **Impact**: About 350 lines. Open issues #5716 (normalizer fit) and #5747 (KNN builder) concern neighbouring code, and `update_graph` and `save_normalizer` could look like the intended fix surface.
- **Related**: #5743 (`phase_correlation` polarity bug, a different function)
- **Suggested Fix**: Delete the listed methods.

##### TD2-10: Engine DSP and core: dead methods with zero callers
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/dsp/eq/masking.py:63,89` (`calculate_simultaneous_masking`, `calculate_temporal_masking`, 63 lines); `dsp/utils/adaptive_loudness.py:176,201` (`should_apply_makeup_gain`, `get_adaptive_processing_params`, 63 lines); `core/simple_mastering.py:305` (`_apply_safety_limiter`); `core/processing/base/audio_measurement.py:106` (`crest_delta_info`), `db_conversion.py:48` (`db_delta`), `processing_logger.py:42` (`stereo_width_change`); `core/config/unified_config.py:138` (`update_adaptive_settings`); `player/gapless_playback_engine.py:65` (`add_prebuffer_callback`); `player/realtime/auto_master.py:68` (`set_use_transient_enhancement`)
- **Status**: NEW
- **Age**: 2025-10-02 (`masking`) to 2025-12-15 (`adaptive_loudness`)
- **Effort**: small
- **Description**: `MaskingThresholdCalculator.calculate_masking` is live but its two helper methods are never called; this is the "masking" logic that #5703 says is mislabelled. `simple_mastering.py:305` `_apply_safety_limiter` is a private method with 0 references.
- **Related**: #5703 (open): fixing masking behaviour should not extend to the two dead helpers.
- **Suggested Fix**: Delete the methods listed above.

##### TD2-11: Library and services: dead repository finders, sidecar and scan-resource getters
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/library/repositories/fingerprint_similarity_mixin.py:142` (`get_by_dimension_range`, 42 lines); `similarity_graph_repository.py:85,189` (`add_edge`, `count_edges`, 41 lines); `settings_repository.py:161` (`update_scan_folders`); `library/sidecar_manager.py:361,386` (`compute_checksum`, `bulk_delete`), with `get_processing_cache` and `update_processing_cache` test-only; `library/resource_monitor.py:194,199` (`get_current_worker_count`, `get_current_semaphore_size`); `services/fingerprint_extractor.py:63,322,347` (`_delete_corrupted_track`, `extract_missing_fingerprints`, `update_fingerprint`, 69 lines)
- **Status**: NEW. `GenreRepository.get_tracks_by_genre` is already tracked by #5754 and excluded here.
- **Age**: 2025-10-29 (`sidecar_manager`) to 2026-08-22 (`get_by_dimension_range`)
- **Effort**: small
- **Description**: Zero callers in production and in tests. `_delete_corrupted_track` is the remaining body of the corrupted-track path whose exception class (`CorruptedTrackError`) was already deleted; nothing invokes it. `extract_missing_fingerprints` and `update_fingerprint` duplicate the live `extract_batch` / queue path.
- **Impact**: Repository methods are the audited DB surface; dead ones accumulate N+1 and eager-load findings like #5754.
- **Related**: #5754, #5368
- **Suggested Fix**: Delete the methods listed (the test-only sidecar cache methods together with their tests).

##### TD2-12: Backend: facade wrappers and a push-notification path with no production caller
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis-web/backend/core/processing_engine.py:199-225` (`register_progress_callback`, `unregister_progress_callback`, `_get_processor_cache_key`, `_return_processor`, `_discard_processor`); `core/job_progress.py:51-138` (`ProgressNotifier.register/unregister/notify`); `core/streamlined_worker.py:105-115` (`_close_dropped_processor`); `core/audio_processing_pipeline.py:373-392` (`AudioValidationError`, `validate_audio_array`); `core/chunk_boundaries.py:340,425` (`get_overlap_samples`, `log_chunk_info`); `core/chunk_cache_manager.py:363,395` (`get_cached_fingerprint`, `cache_fingerprint`); `core/file_signature.py:113` (`validate_signature`); `core/processor_factory.py:543` (`create_processor_factory`); test-only: `ProcessorFactory.cleanup_track`/`get_or_create_from_config`, `executors.get_io_executor`/`get_job_executor`, `chunk_cache_manager.get_statistics`/`clear_track_cache`, `wav_encoder.cleanup_track_chunks`
- **Status**: NEW. `process_all_chunks_async` (#5495) and `HeartbeatManager.is_alive` (#5494) are already tracked.
- **Age**: 2025-12-05 (`chunk_boundaries`), 2025-12-16 (`audio_processing_pipeline`), 2026-02-21 (`processing_engine`)
- **Effort**: small
- **Description**: The #4250 split left one-line wrappers in `processing_engine.py` and `streamlined_worker.py` that delegate to `_pool` and `_progress`. Four of these wrappers have no caller at all. `register_progress_callback` is called only by tests (16 hits) and an `INTEGRATION_INSTRUCTIONS.md` snippet, so `ProgressNotifier` never has a subscriber in production; `notify()` iterates an always-empty map, and clients poll `job.progress` instead. `ChunkCacheManager` still carries a track-level fingerprint plane (`get_cached_fingerprint`, `cache_fingerprint`), although the per-track cache is `mastering_target_service`.
- **Siblings**: `auralis-web/backend/INTEGRATION_INSTRUCTIONS.md:14,90` documents `processing_api` setup that no longer exists.
- **Related**: #5495, #5494
- **Suggested Fix**: Delete the dead wrappers and the fingerprint plane. For the progress path, either delete `ProgressNotifier` and its engine wrappers with their tests, or wire a real subscriber.

##### TD2-13: `# noqa: F401` re-exports in `chunked_processor.py` and others survive only as test patch targets; some have no consumer at all
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/core/chunked_processor.py:39-67`; `auralis/dsp/utils/adaptive.py:15`; `auralis/io/unified_loader.py:36`; `auralis/library/scanner/config.py:15`; `auralis-web/backend/core/stream_seek.py:20`, `stream_enhanced.py:20`
- **Status**: NEW (#5366, closed, removed only the crossfade re-export)
- **Age**: re-export block from #4245 (2026-07-06); `adaptive.py:15` from `ae2e2a76` 2025-10-02
- **Effort**: small
- **Description**: No production module imports any re-export from `chunked_processor`. Zero consumers anywhere: `CONTEXT_DURATION` (re-exported "for callers" that do not exist) and `_reset_registry_miss_warning`, plus `adaptive.rms` (the comment claims "tests/validation imports it from here"; nothing does). Test-patch-only: `AudioProcessingPipeline`, `ChunkOperations`, `get_last_content_profile`, `_last_content_profiles`, `_last_content_profiles_lock`, `_default_get_fingerprints_repository`, `MAX_LEVEL_CHANGE_DB`, `OVERLAP_DURATION`. `scanner/config.py` `AUDIO_EXTENSIONS` has one test consumer. The `stream_seek.py` / `stream_enhanced.py` `Path` imports and `unified_loader.check_ffmpeg` are kept for `monkeypatch`.
- **Impact**: The comment ("pre-#4245 test patch targets") keeps these indefinitely. They make `chunked_processor.py` look like the owner of state it merely mirrors, which is how tests end up patching the wrong module.
- **Related**: #5366, #4645 (closed; similar re-export sweep)
- **Suggested Fix**: Delete the three zero-consumer names now. Repoint the tests that patch via `chunked_processor` to the defining modules, then delete the rest.

##### TD2-14: `chunk_crossfade.py` is a whole module with only test importers
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis-web/backend/core/chunk_crossfade.py:1-89`; stale docstring claims at `core/chunk_render.py:15`, `core/chunk_operations.py:13,46`
- **Status**: NEW (#5366 removed the re-export and kept the module, so the module itself was never judged)
- **Age**: `fce816f3` 2026-09-13 removed the last non-test import
- **Effort**: trivial
- **Description**: `apply_crossfade_between_chunks` is imported only by `test_equal_gain_crossfade.py`, `test_chunked_processor_invariants.py` and a `patch()` in `test_no_nested_event_loop.py`, which patches a function nothing calls. `chunk_operations.py` and `chunk_render.py` still say "Crossfade math lives solely in `chunk_crossfade.apply_crossfade_between_chunks`", which reads as live. The Retired Architecture table documents the absence of a seam crossfade but does not decide whether the file should stay.
- **Related**: #5366, #3878 (equal-gain curve; do not alter the curve)
- **Suggested Fix**: Delete the module, its tests, the dead patch target and the three stale docstring sentences, or record in the file why it is kept.

##### TD2-15: Production methods and functions with test callers only (test-only surface)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: see Siblings
- **Status**: NEW
- **Age**: mixed (2025-10 to 2026-08)
- **Effort**: medium (decide per cluster)
- **Description**: Production code kept alive only by its own tests. Production hits by name are 0 for each; test references exist.
- **Evidence**: vulture 60% list reclassified by whole-repo word grep (prod / tests split).
- **Impact**: Each also suppresses the "no callers" signal for the next audit.
- **Siblings**: `cache/monitoring.py:103,302` (`update_metrics`, `get_summary`); `track_repository_search.py:83,115,144` (`get_by_genre`, `get_recent`, `get_popular`); `album_repository.py:101,157`; `artist_repository.py:142`; `genre_repository.py:71`; `scanner.py:423-427` (`scan_single_directory`, `scan_folder`); `file_discovery.py:86` (`count_audio_files`); `fingerprint_quantizer.py:184-215` (3 methods, 68 lines); `analysis/fingerprint/metrics/` (`aggregate_multiple`, `safe_log`, `validate_vector`, `from_intervals`, `from_values`, `calculate_from_*`, `normalize_magnitude`, `spectral_centroid_safe`, `apply_to_fingerprint`, `peak_to_rms_ratio`); `utils/helpers.py:17,30,55` (`get_temp_folder`, `format_duration`, `format_filesize`: 54 lines, 65 test refs); `utils/logging.py:106,114,143`; `utils/audio_validation.py:70` (`check_audio_finite`); `utils/queue/queue_exporter.py` (`export_to_file`, `detect_format`); `analysis/dynamic_range.py:454` and `phase_correlation.py:338` (history getters); `player/components/queue_manager.py:297,471`; `gapless_playback_engine.py:214,220`; `playback_controller.py:299`; `queue_controller.py:350,362`; `core/hybrid_processor.py:318,322` (`get_dynamics_info`, `set_dynamics_mode`); `core/processing/continuous_mode.py:189` (`process_album`); `core/processing/base/normalization_step.py:133`; `compression_expansion.py:199`; `unified_config.py:147,151,176`; `services/artwork_service.py:317`; `library/artwork.py:309`; backend `recommendation_service.py:163`, `seekable_source.py:196`, `state_manager.py:141`, `chunk_render.py:96`, `cache/recommendations_mixin.py:100`
- **Related**: #5189 (queue reorder unreachable) overlaps `queue_manager`
- **Suggested Fix**: Treat as a backlog. Delete each method together with its tests, starting with the largest (`fingerprint_quantizer`, `helpers`, `track_repository_search`).

##### TD2-16: 27 frontend barrel `index.ts` files have no importer (about 520 lines)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `src/hooks/index.ts` (37), `hooks/{api,app,audio,enhancement,websocket}/index.ts`, `src/components/library/index.ts` (81), `components/library/{Controls,Details,EditMetadataDialog,Hooks,Items,Items/albums,Items/artists,Items/tables,Items/tracks,Items/utilities,Search,Styles,Views}/index.ts`, `components/{album/AlbumCard,layouts,shared/DropZone,shared/feedback,shared/ui,shared/ui/badges,track}/index.ts`
- **Status**: NEW (the open #5628 / #5129 cover the orphaned components and selectors, not the barrels)
- **Age**: 2025-10 to 2026-06
- **Effort**: small
- **Description**: A TS import-graph walk finds no file, production or test, that imports these barrels by alias or relative path. Only two further unreachable barrels are test-imported (`QueueRecommendationsPanel`, `QueueSearchPanel`, see TD2-05). Several barrels also re-export the orphaned components of #5628, which hides how dead those are.
- **Impact**: Every new component gets added to a barrel nobody consumes, and the barrels keep orphaned files reachable in a casual grep.
- **Related**: #5628, #5129, #4206 (barrel-kept selectors comment)
- **Suggested Fix**: Delete the 27 barrels in the same pass as #5628. Add `knip` to `package.json` so the walk is repeatable.

##### TD2-17: Frontend exports with zero references or test-only references
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: see Description
- **Status**: NEW (the selector cluster in `store/selectors` is #5129, OPEN; design-system primitives #5132, OPEN)
- **Age**: not determined per symbol
- **Effort**: small
- **Description**: Zero references anywhere in `src/` (tests included): `components/library/Styles/Shadow.styles.ts` (`compoundShadows`, `focusShadows`, `glowShadows`, `notificationShadows`), `EditMetadataDialog.styles.ts` `ContentBox`, `Views/TrackListView.styles.ts` `TrackItemWrapper`, `track/TrackCardStyles.ts` `StyledTrackCard`, `store/slices/playerSlice.ts` `selectPlayerState`, `utils/timeFormat.ts` `getProgress` and `formatHumanDuration`, `hooks/audio/audioVisualization.ts` `resetAudioVisualization`, `hooks/websocket/websocketConnectionCore.ts` `resetStreamFrameTracking`. Test-only: `api/transformers/artistTransformer.ts` `transformArtistsResponse`, `trackTransformer.ts` `transformTracksResponse`, `config/api.ts` `getWsUrl`, `utils/eraGrouping.ts` `getEraLabel`, `utils/fingerprintToGradient.ts` `computeMedianFingerprint`, `hooks/player/usePlayerDisplay.ts` `calculateProgressPercentage` and `formatBufferedPercentage`, `hooks/fingerprint/similarityCache.ts` `clearSimilarityCache` and `similarityCacheSize`, `store/selectors/queue.ts` (`makeSelectTrackAtIndex`, `makeSelectTracksInRange`, `makeSelectFilteredTracks`, `makeSelectTracksByDuration`, `selectFormattedQueueTime`), `store/slices/cacheSlice.ts` `selectIsHealthy`, `queueSlice.ts` `selectQueueLength`, `services/queueService.ts` `removeTrackFromQueue`, `hooks/shared/useStandardizedAPI.ts` `useCacheHealth`, `types/api.ts` `isApiError`.
- **Evidence**: Scratch script `/tmp/claude-1000/-mnt-data-src-matchering/81edcd9c-5e45-4167-8c79-dd6e56e87c74/scratchpad/fe.py`: for each `export const|function|class|type|interface|enum` in non-test `src/`, no other non-test file references the name as a word.
- **Impact**: Mostly small. `queueService.removeTrackFromQueue` is part of the unreachable queue edit gap (#5189).
- **Related**: #5129, #5132, #5646, #5189
- **Suggested Fix**: Delete the zero-reference items; fold the test-only items into the #5129 pass.

##### TD2-18: `recording_type_detector.py` (492 lines) has no engine caller; only dev scripts and tests use it
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/core/recording_type_detector.py:1-492`
- **Status**: NEW
- **Age**: `fd37cc1b` 2025-11-17
- **Effort**: small
- **Description**: `git grep` finds importers in `scripts/rate_track.py`, `scripts/analyze_feedback.py`, `scripts/update_profile.py` and several test files, but none in `auralis/` or `auralis-web/backend/`. The project map in `CLAUDE.md` lists it under `core/` as live "Content type detection". Mastering parameters now come from the continuous 3D space, which makes a per-recording-type classifier redundant.
- **Impact**: A reader of the codebase map expects the pipeline to classify recording types.
- **Suggested Fix**: Product call. Either move it under `scripts/` with its tests or delete it along with the three scripts that depend on it, and fix the `CLAUDE.md` map line.

##### TD2-19: 5 unused imports and locals reported by ruff (F401/F841)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis-web/backend/routers/player_deps.py:23` (`LibraryManagerUnavailableError`); `auralis/core/simple_mastering.py:34` (`import soundfile as sf`); `auralis/library/repositories/playlist_ordering_mixin.py:18` (`func`); `auralis/player/gapless_playback_engine.py:313` (`prebuffered_info`, F841); `auralis-web/backend/routers/player_models.py:12` (`typing.Any`)
- **Status**: NEW
- **Age**: `player_deps.py` import from `b883d3b5` (#5472, router split); the `prebuffered_info` local from `99ee1809` (#5583)
- **Effort**: trivial
- **Description**: `ruff 0.12.12 check --select F401,F811,F841 auralis auralis-web/backend` reports exactly these five; none is a re-export (no `__all__`, no `noqa`). `simple_mastering.py:34` is not patched by any test (`grep "simple_mastering.sf"` is empty). `player_models.py` currently has uncommitted edits from another terminal, so that line may change before anyone acts. `LibraryManagerUnavailableError` is also a stale `LibraryManager` name (#4915), but it is live at its other import sites.
- **Impact**: Trivial. `ruff` is not wired into CI, so these accumulate: the 2026-08-23 sweep (#5209) found 6, and this one finds 5 more.
- **Related**: #5209, #4888 (closed sweeps)
- **Suggested Fix**: `ruff check --select F401,F841 --fix` on those files, and add the check to pre-commit or CI.

##### TD2-20: Three stale or misplaced `# type: ignore` comments (and live mypy errors behind them)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/analysis/fingerprint/metrics/audio_metrics.py:58`; `auralis-web/backend/services/artwork_downloader.py:236,307`; related error `auralis/analysis/fingerprint/metrics/spectral_ops.py:75`
- **Status**: NEW
- **Age**: `530cf6a9` 2026-01-02 (`audio_metrics`); `a59e77de` 2026-09-17 (`artwork_downloader`)
- **Effort**: trivial
- **Description**: `mypy --warn-unused-ignores --ignore-missing-imports` over the 27 files that hold the 51 ignores reports 6 errors. Three are `unused-ignore`: `audio_metrics.py:58` (`[no-any-return]` is no longer needed), and the comments at `artwork_downloader.py:236` and `:307`. Those two sit on the `) as resp:` line, but mypy reports the `[arg-type]` error on the `params=params` line two rows earlier (`:235`, `:306`), so the ignore silences nothing and the real error is exposed. The sixth error is a `no-any-return` at `spectral_ops.py:75` (`np.clip(...)`).
- **Evidence**: mypy output: `artwork_downloader.py:235: error: Argument "params" to "get" ... [arg-type]`, then `:236: error: Unused "type: ignore" comment`.
- **Impact**: `mypy auralis-web/backend` is not clean today, though the project requires it before PRs. The ignore count is 51 (was 67 on 2026-09-13), so the downward trend holds apart from these.
- **Related**: #4887, #4256 (closed sweeps). The `spectral_ops.py:75` and `artwork_downloader` errors are typing issues for the owning audits (`/audit-engine`, `/audit-backend`).
- **Suggested Fix**: Delete the `audio_metrics.py:58` ignore. Move the two `artwork_downloader.py` ignores to the lines `:235` and `:306` (or type `params` as `dict[str, str]`), and add a cast in `spectral_ops.py:75`.

#### Dimension 3: Logic Duplication

##### TD3-03: Router 503/400/404 are still hand-raised in ~55 places beside typed `errors.py` classes, including the same message 9 times
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `routers/processing_jobs.py:48,67,118,144,168,179`, `processing_upload.py:82`, `processing_api.py:88` (all `"Processing engine not available"`); `dependencies.py:118`; `files.py:171-176`; `similarity.py:289,350,408`; `fingerprint_queue.py:175,226`; and others. Static count: `HTTPException(status_code=…)` literals in `routers/*.py` are 25×503, 24×400, 6×404, 8×500, against `ServiceUnavailableError(` 3×, `BadRequestError(` 3×. `NotFoundError(` is used 44×, so the 404 helper works and the others are the outliers.
- **Status**: NEW
- **Effort**: small
- **Description**: `errors.py` defines `ServiceUnavailableError` and three typed unavailable subclasses (audio player, player state, connection manager), but there is none for the processing engine, repository factory, similarity system, fingerprint queue or settings. Each is re-spelled inline. `dependencies.require_repository_factory` itself raises a bare `HTTPException(503, ...)` while its `require_audio_player` and `require_player_state_manager` siblings raise typed errors. `files._get_repos` re-implements the same 503. `IntegrationManager._get_repos` (`auralis/player/integration_manager.py:172-185`) and `QueueController._get_repos` (`auralis/player/queue_controller.py:64-77`) are byte-identical copies in the engine. `similarity.py:289,350,408` hand-raise 503 for "not fitted" in three different wordings next to `require_similarity_system`.
- **Impact**: Changing the unavailable contract (a Retry-After header, a shared detail format) is a ~25-site edit. The wording already drifted ("Similarity system not initialized" vs "…not available. Please wait…").
- **Siblings**: `similarity_common._with_similarity_error_handling` is a hand mirror of `with_error_handling` (its docstring says "Mirrors"). Its divergence (DB-locked maps to 500) is tracked in #5381.
- **Suggested Fix**: Add `require_processing_engine()` and a parameterised `require_service(value, name)` to `routers/dependencies.py`. Make `require_repository_factory` and `files._get_repos` raise `ServiceUnavailableError`. Fold the two player `_get_repos` copies into one helper in `auralis/player/`.

##### TD3-04: Mono downmix and channel-layout detection hand-rolled at 15 sites with 4 incompatible strategies; the one helper is dead
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `dsp/eq/psychoacoustic_eq.py:155` (axis=1); `core/dsp/resonance_notcher.py:82-88` (guess by `shape[0]==2`); `core/mastering_prepare.py:67` (axis=1); `analysis/quality_assessors/base_assessor.py:165,196` and `utilities/estimation_ops.py:39,134,208,360` (axis=1); `analysis/fingerprint/windowed_compute.py:329` (axis=0); `analysis/fingerprint/audio_fingerprint_analyzer.py:140-151` (shape heuristic); `core/analysis/content_analyzer.py:82,279` (axis=1); `analysis/ml/feature_extractor.py:63` (axis=0)
- **Status**: NEW (the live symptom, the genre classifier on `(N, 2)` input, is already open as #5746)
- **Effort**: small
- **Description**: The engine deliberately uses both `(samples, channels)` (I/O, analysis) and `(channels, samples)` (the stage pipeline), with transposes at the boundaries. Each analyzer re-decides the layout with its own idiom. `BaseAssessor._to_mono` (`base_assessor.py:89`) is defined and has zero callers; the same class inlines `np.mean(audio_data, axis=1)` at lines 165 and 196. `dsp/utils/audio_info.py` hosts `is_mono`/`channel_count`/`mono_to_stereo`, but only `dsp/utils/adaptive.py` imports them, and those assume `(samples, channels)`.
- **Evidence**: `feature_extractor.py:60-63` documents "the codebase convention is (channels, samples), so axis=0", while `content_analyzer.py:82` on the same project uses `axis=1`. The #2452 fix touched only the feature extractor.
- **Impact**: A layout-dependent bug fixed in one analyzer (#2452) stays latent in the others; #5746 is the same bug class.
- **Related**: #5746, #5744 (open); owning audit `/audit-engine`.
- **Suggested Fix**: Add `to_mono(audio, layout='samples_channels'|'channels_samples')` to `dsp/utils/audio_info.py` (explicit layout, no shape guessing). Replace the 15 inline sites and delete `BaseAssessor._to_mono`.

##### TD3-05: Level measurement (dB conversion, peak, RMS) re-implemented ~35 times with three different silence conventions
- **Severity**: LOW (no guard-omission found; each inline site guards zero in some way)
- **Dimension**: Logic Duplication
- **Location**: helpers: `core/processing/base/db_conversion.py:22-36` (`DBConversion`, returns -inf on <=0) and `dsp/utils/conversion.py:14` (`to_db`, 1e-10 floor, used only by `dsp/utils/spectral.py:168`). Inline `20*np.log10` (35 sites in 20 files), e.g. `core/mastering_process_chunk.py:34` and `core/mastering_prepare.py:221` (floor -96.0), `analysis/dynamic_range.py:99,107` and `analysis/loudness_meter.py:284,302` (-inf), `dsp/eq/masking.py:58,124` (+1e-10). Inline `np.sqrt(np.mean(x**2))` at 28 sites vs `dsp/basic.rms`; `AudioMeasurement` (`core/processing/base/audio_measurement.py:34-35`) and `core/analysis/content_analyzer.py:180-183` re-spell `DBConversion.to_db` in the package that defines it.
- **Status**: NEW
- **Effort**: small
- **Description**: `DBConversion`'s docstring claims it "Replaces 17+ instances", but only 11 files import either helper. Silent input maps to -inf, -96.0 or about -200 dB depending on the file. The two mastering sites that use -96.0 feed the pipeline's own peak/headroom maths.
- **Impact**: Comparing or subtracting dB values from two modules mixes sentinels; `-96.0` and `-inf` take different branches in downstream `isfinite` checks.
- **Siblings**: `windowed_compute.py:327-338` and `mastering_prepare.py:55-70` are two copies of "mono mean to float64 RMS to crest dB" with different semantics (RMS proxy vs BS.1770). That mismatch is already #5700.
- **Related**: #5700 (open), #4021 (closed, the earlier `dsp/basic` duplicate pair).
- **Suggested Fix**: Keep one module (`dsp/utils/conversion.py`) with `to_db(x, floor=None)` and `peak_db(audio)` / `rms_db(audio)`, with an explicit silence convention. Make `DBConversion` delegate. Move the inline sites onto it and onto `dsp.basic.rms`, starting with the 6 mastering files.

##### TD3-06: The 25-dimension fingerprint name list is copied 4 times next to a documented single source of truth; `_numpy_to_python` / `_band_pct_valid` exist twice
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: SoT `analysis/fingerprint/schema.py:52` (`DIMENSION_SCHEMA`, "Single source of truth"). Hand copies: `analysis/fingerprint/normalizer.py:86`, `library/fingerprint_quantizer.py:92`, `analysis/fingerprint/metrics/constants.py:24` (a frozenset), `analysis/fingerprint/fingerprint_service.py:36` (`_FP_KEYS`). The 7-band key tuple is repeated at `windowed_compute.py:45`, `fingerprint_service.py:219`, `learning/reference_seeder.py:73` and as the prefix of `core/processing/target_derivation.py:61`. `FingerprintService._numpy_to_python` (`fingerprint_service.py:281-310`) duplicates `windowed_compute.py:64-86`, and `_band_pct_valid` is duplicated at `fingerprint_service.py:225` and `windowed_compute.py:58`.
- **Status**: NEW
- **Effort**: small
- **Description**: I imported all five lists: they are identical and in the same order today (25 names). Tests pin only the lengths (`len(...) == 25`), not agreement with the schema. `catalog.py:17` and `sidecar_manager.py` already derive from `DIMENSION_SCHEMA` correctly. `FingerprintService._numpy_to_python` has no caller outside its own recursion, so it is a dead copy.
- **Impact**: Adding or reordering a dimension (the vector order matters for the quantizer and normalizer) means five hand edits and no test fails if one is missed.
- **Suggested Fix**: In `schema.py` add `DIMENSION_NAMES = tuple(DIMENSION_SCHEMA)` and `BAND_PCT_KEYS`, and derive the four lists and the band tuples from them. Delete `FingerprintService._numpy_to_python`. Make `windowed_compute` import one `band_pct_valid` shared with the service.

##### TD3-07: Frontend time formatting: `formatSeconds` is a private copy of `formatDuration`, and three more "Xh Ym" formatters sit beside `utils/timeFormat.ts`
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `store/selectors/player.ts:13-22` (`formatSeconds`); `store/selectors/queue.ts:40,49`; `utils/queue/queue_statistics.ts:238-250`; `components/library/Details/AlbumMetadata.tsx:18-24`; `hooks/player/usePlayerDisplay.ts:36` (a local `formatTime` shim that ignores its `showHours` argument)
- **Status**: NEW
- **Effort**: trivial
- **Description**: `formatSeconds` is the body of `utils/timeFormat.ts::formatDuration` without its `isFinite`/negative guard, so `formatSeconds(NaN)` yields `"NaN:NaN"`. It feeds `selectFormattedTime` and `selectPlaybackState`, which are `@internal` and have no component subscribers today. The three "Xh Ym" / "Xm Ys" formatters overlap `formatHumanDuration` in the same util.
- **Impact**: Time-format behaviour (rounding, hour threshold, NaN handling) is decided in 5 places.
- **Suggested Fix**: Replace `formatSeconds` with `formatDuration`. Give `timeFormat.ts` one `formatHoursMinutes` variant and use it in `queue_statistics`, `AlbumMetadata` and `queue.ts`.

##### TD3-08: `useAlbumsQuery` is defined twice, and the three "convenience" query hooks have no production consumers
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `hooks/library/useAlbumsQuery.ts:39` vs `hooks/library/useLibraryQueries.ts:37`; `hooks/library/index.ts:9-10` exports from one path while `useLibraryQuery.ts:298` re-exports the other
- **Status**: NEW
- **Effort**: trivial
- **Description**: Both are `useLibraryQuery('albums', options)` one-liners, split by the #5478 file-size refactor. Grep shows `useAlbumsQuery`, `useTracksQuery` and `useInfiniteScroll` referenced only in comments, in their own definitions and in tests; the only live consumer in the group is `useArtistsQuery` (`CozyArtistList.tsx`).
- **Impact**: Two import paths that return slightly different types (`UseLibraryQueryResult<Album>` vs inferred), and a real album grid that uses `useInfiniteAlbums` instead.
- **Related**: Dim 2 (dead-code) overlap; the delete decision belongs there too.
- **Suggested Fix**: Delete `useAlbumsQuery.ts` and its test, keep the `useLibraryQueries.ts` one. Decide separately whether `useTracksQuery` and `useInfiniteScroll` stay.

##### TD3-09: WS subscribe/unsubscribe is hand-rolled in 3 hooks beside `useWebSocketMessages`; the "stable `subscribe`" fix landed piecemeal
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `hooks/enhancement/useEnhancedSeek.ts:97-107`, `hooks/enhancement/useFingerprintStatus.ts:116-128`, `hooks/enhancement/useStreamSubscriptions.ts:77-146`; the shared hook is `hooks/websocket/useWebSocketMessages.ts`
- **Status**: NEW
- **Age**: `8cd04ec5` 2026-08-25 (#4668); `useStreamSubscriptions` fixed later as "#4668's missed sibling, #5621"
- **Effort**: small
- **Description**: `useWebSocketMessages` already does the ref-held callback, order-independent key and stable-`subscribe` dependency. `useEnhancedSeek` and `useFingerprintStatus` re-implement it for a single message type, including the same long #4668 comment. `useStreamSubscriptions` does it for four types. All three now carry the fix, but #4668 had to be applied hook by hook and was missed once.
- **Impact**: The next subscription-lifecycle fix has to be applied in 4 places again. The `unsubscribe?.()` optional-chaining in two of the copies also hides a missing-unsubscribe case.
- **Siblings**: 8 other hooks already use `useWebSocketMessages` (e.g. `useQueueSubscription`, `useServerRestartNotice`).
- **Suggested Fix**: Migrate `useEnhancedSeek` and `useFingerprintStatus` to `useWebSocketMessages(['seek_started'], ...)` and `(['fingerprint_progress'], ...)`. For `useStreamSubscriptions`, add an overload that takes a type-to-handler map, keeping its watchdog-on-every-message behaviour in the handlers.

##### TD3-10: Backend services repeat the same unavailable-guard 28 times and the same queue-mutation scaffold 8 times
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `services/playback_service.py` (8), `navigation_service.py` (5), `queue_edit_mixin.py` (7), `queue_order_mixin.py` (4), `queue_set_mixin.py` (3), `queue_service.py` (1) for `raise ServiceUnavailable("... not available")`; mutator scaffold in `queue_edit_mixin.py:64,157,213,285` and `queue_order_mixin.py:62,120,171,224`
- **Status**: NEW
- **Effort**: small
- **Description**: Every queue mutator opens with `if not self.audio_player or not hasattr(self.audio_player, 'queue'): raise ServiceUnavailable("Queue manager not available")`. It then calls `_invalidate_set_queue_generation()`, takes `_set_queue_engine_lock`, mutates, and calls `_broadcast_queue_changed`. `PlaybackService`, `NavigationService` and `QueueServiceBase` each take the same four collaborators (`audio_player`, `player_state_manager`, `connection_manager`, `create_track_info_fn`) in separate `__init__`s with the same guards.
- **Impact**: The #5320 fix ("clear_queue and the other mutators bypassed set_queue's generation protocol") had to be applied to all 8 mutators by hand. All 8 currently have it, so nothing is divergent, but a ninth mutator will not get it automatically.
- **Suggested Fix**: Add an async context manager `_queue_mutation()` to `QueueServiceBase` that does the guard, generation invalidation and engine lock. Add a `require_collaborators(...)` helper in `services/errors.py` for the audio-player and state-manager guards.

##### TD3-11: Four near-identical correlated-count (and two total-duration) subquery helpers across repositories
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `album_repository.py:23`, `artist_repository.py:22`, `genre_repository.py:23`, `playlist_query_mixin.py:84` (`_track_count_subquery`); `album_repository.py:35` and `playlist_query_mixin.py:97` (`_total_duration_subquery`)
- **Status**: NEW (the open #5499 is about the response envelope, not this)
- **Effort**: trivial
- **Description**: Each is `select(func.count()).select_from(assoc).where(assoc.c.parent_id == Parent.id).correlate(Parent).scalar_subquery()`. Each docstring says "same shape as the other one" and cites its predecessor (#4777, #5084, #5111).
- **Impact**: A change to the counting semantics (the distinct count needed for duplicate links, the `.correlate` form) is a four-file edit.
- **Suggested Fix**: Add `correlated_count(assoc_table, fk_col, parent_model)` to `repositories/base.py` next to `escape_like`. The album helper stays separate because it counts `Track.album_id` directly with no association table.

##### TD3-12: Three copies of the envelope-follower recursion; the "vectorized" path is a plain Python loop
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `dsp/dynamics/envelope.py:19-71`, `dsp/dynamics/vectorized_envelope.py:45-86` (`process_buffer_vectorized`), and the numba kernel at `:144-170`; selected by a try/except in `dsp/dynamics/compressor.py:20-26`
- **Status**: NEW
- **Effort**: small
- **Description**: The attack/release coefficient code and the sample loop are copied three times. `process_buffer_vectorized` contains no vectorized code, only a scalar loop with a comment about a "scan algorithm", although the module docstring promises "10-20x". The fix history is split: the dtype-preservation fixes #4225 and #4934 landed only in `VectorizedEnvelopeFollower`. The plain class is safe because it uses `zeros_like`, so nothing is currently wrong. This is the "No variants" principle in CLAUDE.md.
- **Impact**: Any change to the envelope maths must be made in three places, and the compressor silently uses whichever imports.
- **Related**: #4309 (closed; the sibling `LookaheadBuffer` dedupe, verified still in place).
- **Suggested Fix**: Keep one `EnvelopeFollower` with a numba kernel and a pure-Python fallback inside `process_buffer`. Delete `process_buffer_vectorized` and the `try/except ImportError` in `compressor.py`.

##### TD3-13: Three same-named, structurally different types: `ProcessingParameters`, `PlaybackState`, `BroadcastManager`
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/processing/continuous_space.py:58` vs `auralis/core/analysis/spectrum_mapper/data_classes.py:39` (`ProcessingParameters`, different fields entirely); `auralis-web/backend/player_state.py:28` vs `auralis/player/playback_controller.py:27` (`PlaybackState`, identical five members); `websocket/outbound_messages.py:30` vs `services/recommendation_service.py:23` (`BroadcastManager` Protocol)
- **Status**: NEW
- **Effort**: small
- **Description**: The two `ProcessingParameters` classes are unrelated and imported by different modules, so `from … import ProcessingParameters` is a coin flip for a reader or auto-import. The two `PlaybackState` enums have identical members; the backend already imports `auralis`, so there is no layering reason for a mirror. The two `BroadcastManager` protocols describe the same capability.
- **Suggested Fix**: Rename the spectrum-mapper one to `SpectrumParameters`. Have the backend `PlaybackState` subclass or reuse the engine enum (wire values unchanged). Keep one `BroadcastManager` Protocol in `outbound_messages.py` and import it in `recommendation_service.py`.
- **Merged — TD5-05 (Dim 5)**: a *third* copy of the one-method broadcast Protocol is `services/playback_service.py:70-75` `ConnectionManager`, which also shadows the real `config.globals.ConnectionManager` by name (`navigation_service.py:25` imports the real one under `TYPE_CHECKING`). Fold all three onto `websocket/outbound_messages.BroadcastManager`.

##### TD3-14: The default preset is spelled `"adaptive"` in 16 places; the only named constant is local to one WS module
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `ws_handlers/playback_commands.py:36` (`DEFAULT_PRESET`); literals at `helpers.py:125`, `main.py:230`, `ws_handlers/connection.py:139`, `routers/enhancement.py:376,540,678`, `routers/processing_parameters.py:132`, `routers/system.py:76,224`, `player_state.py:116`, `cache/manager.py:120`, `cache/playback_mixin.py:97`, `services/recommendation_service.py:87`, `core/chunked_processor.py:86`, `core/processor_factory.py:91,197`
- **Status**: NEW
- **Effort**: trivial
- **Description**: `schemas/enhancement.py:31-32` is the SoT for `VALID_PRESETS` and `EnhancementPresetLiteral`, and every preset *list* now agrees (verified), but the *default* is a free string in each caller.
- **Impact**: Low today, since there is one preset and the user directive of 2026-09-13 forbids resurrecting the old list. It only matters if the default ever has to change or a second preset returns.
- **Suggested Fix**: Add `DEFAULT_PRESET: EnhancementPresetLiteral = "adaptive"` beside `VALID_PRESETS` and import it in the REST, WS and cache callers. `core/` modules (`proactive_buffer`, `chunked_processor`, `processor_factory`) keep a local constant on purpose, per the existing layering note in `proactive_buffer.py`.

#### Dimension 4: Magic Numbers & Hardcoded Constants

##### TD4-01: 92 raw `fp.get('<dim>', <default>)` fallbacks across 17 files re-type, and disagree with, `FingerprintUnpacker`'s defaults
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/core/utils/fingerprint_unpacker.py:90-229` (the claimed "single source of truth"); raw copies in `auralis/core/mastering_diagnostics.py` (24), `auralis/core/analysis/target_generator.py` (20), `auralis-web/backend/core/mastering_target_service.py` (9), `auralis/player/realtime/auto_master.py` (8), `auralis/core/recording_type_detector.py` (5), `auralis/learning/components/predictor.py` (4), `auralis/core/processing/continuous_space.py` (4), `.../base/normalization_step.py` (4), plus 9 more files with 1-3 each
- **Status**: NEW (no open or closed issue matches "fingerprint default"/"unpacker")
- **Age**: unpacker `9f460102` 2026-02-14; raw copies accrued since
- **Effort**: medium (mechanical, ~17 files)
- **Description**: `FingerprintUnpacker`'s docstring promises "Single source of truth for defaults ... unpacker.lufs instead of fp.get('lufs', -14.0)". Only 5 modules (`mastering_branches/{base,continuous}.py`, `mastering_process_chunk.py`, `utils/__init__.py`, the unpacker itself) use it; everything else re-types a numeric fallback per call. The re-typed values have already drifted.
- **Evidence** (key -> distinct fallback values outside/inside the unpacker, from `grep -rnE "\.get\('(lufs|crest_db|...)', -?[0-9]"`): `lufs` {-14.0 x6, 0 x8, -20.0 x1}; `crest_db` {12.0 x5, 15.0, 5.0, 0 x4}; `stereo_width` {0.5 x4, 0.7 x4, 0}; `pitch_stability` {0.5 x2, 0.7}; `spectral_centroid` {2000 x5, 0.5 x3}; `upper_mid_pct` {0.25, 0.20, 0.0733, 0.0}. E.g. `target_generator.py:300-301` `fingerprint.get("lufs", -20.0)` / `("crest_db", 15.0)` vs `auto_master.py:106-107` `-14.0` / `12.0` vs `recording_type_detector.py:190` `crest_db` default `5.0`. (Some differing values are a different scale, e.g. percent vs fraction; that confusion is itself the hazard.)
- **Impact**: A fingerprint missing a dimension (partial/old `.25d` cache, failed analyzer) is mastered with different assumptions depending on which branch reads it. Tuning a default means editing ~17 files.
- **Siblings**: `-14.0` "default target LUFS" also appears as a literal in `core/hybrid_setup.py:71`, `dsp/dynamics/settings.py:80`, `dsp/advanced_dynamics.py:70,130`, `core/processing/fixed_target_params.py:85`, `routers/processing_parameters.py:33,170`, `mastering_target_service.py:416,423` (`streaming_target = -14.0`); only `assessment_constants.py` names it.
- **Related**: Dim 3 (logic duplication) may report the same cluster from the duplication angle; owning audit `/audit-engine`.
- **Suggested Fix**: Make `FingerprintUnpacker` (or a `FINGERPRINT_DEFAULTS` dict it reads) the only place with defaults; convert the 17 call sites to `FingerprintUnpacker.from_dict(fp).<prop>`; add `DEFAULT_TARGET_LUFS`/`STREAMING_TARGET_LUFS` to `core/config/` and reference it from the 8 target-LUFS sites. Log-only `get('lufs', 0)` in f-strings can stay.

##### TD4-02: Backend port 8765 defined independently in `main.py` and `config/origins.py`; `AURALIS_PORT` moves one but not the other
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/main.py:445` (`get_int_env("AURALIS_PORT", 8765)`); `auralis-web/backend/config/origins.py:32` (`BACKEND_PORT = 8765`, used by `allowed_origin_ports()` at :47)
- **Status**: NEW (#4805 added the env var; nothing tracks the duplicate)
- **Age**: `BACKEND_PORT` `b02c8543` 2026-07-29; env var #4805
- **Effort**: trivial
- **Description**: The bind port is env-tunable, the origin allow-list port is a separate hardcoded literal. `launch-auralis-web.py:68-71` threads `--port` into `AURALIS_PORT` and says it "must stay in sync with main.py", i.e. the sync is manual.
- **Evidence**: `_port = get_int_env("AURALIS_PORT", 8765)` vs `BACKEND_PORT = 8765`; frontend `src/config/api.ts:18,21` hardcodes `localhost:8765` as a third copy (overridable by `VITE_API_URL`/`VITE_WS_URL`).
- **Impact**: With `--port N` in a packaged build, the SPA origin is `http://127.0.0.1:N`, which the origin matrix (`origin_matrix`) does not list. If that is the case the CORS/WS-origin/host checks reject the page on any non-default port.
- **Siblings**: `config/globals.py:37-39`, `config/middleware/hosts.py:22-29` (comments quoting 8765).
- **Related**: possible functional bug, to be confirmed by `/audit-backend` (not verified here).
- **Suggested Fix**: `BACKEND_PORT = get_int_env("AURALIS_PORT", 8765)` in `origins.py` and have `main.py` import it (env_config is stdlib-only, no cycle).

##### TD4-03: Fingerprint window geometry (22050 Hz, 90 s body, 30 s probe, 0.25/0.50/0.75) is function-local in a 300-line function and duplicated elsewhere
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/analysis/fingerprint/windowed_compute.py:117-119` (`_target_sr = 22050`, `_probe_s = 30.0`, `_body_s = 90.0`), fractions `0.50` at :132,227,291 and `(0.25, 0.75)` at :237,252
- **Status**: NEW
- **Age**: `ae5c6bd2` 2026-07-17
- **Effort**: small
- **Description**: The only module-level constant in the file is `_SEEK_PREROLL_S`. The sample rate is declared twice (`windowed_compute._target_sr` and `audio_fingerprint_analyzer._TARGET_SR = 22050`, which `windowed_compute` already imports from, `:40`), and the 90 s window is re-typed in `analysis/mastering_fingerprint.py:130` (`duration=90.0`, comment "Matches the cap used by every other fingerprint path") and documented in `services/fingerprint_extractor.py:206`. `mastering_target_service.py:46` also returns `(0.0, 22050)` as a sentinel rate.
- **Impact**: The comments say changing the 90 s window shifts LUFS bias statistics (study: 34 tracks); the value lives in 3 places and an edit to one silently diverges the mastering fingerprint from the library fingerprint.
- **Suggested Fix**: Promote to module constants in `audio_fingerprint_analyzer.py` (`FINGERPRINT_SR`, `BODY_WINDOW_S`, `PROBE_WINDOW_S`, `PROBE_POSITIONS`, `BODY_POSITION`); import in `windowed_compute`, `mastering_fingerprint`, and the 22050 sentinel. The repeated `min(frac*total, max(0, total-win))` offset expression (x5) should become one helper (Dim 3 sibling).

##### TD4-04: `ffprobe` timeout 30 s typed twice (the pair that already drifted once), plus a bare 300 s decode timeout
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:300` (`timeout=30`), `auralis/io/unified_loader.py:268` (`timeout=30`); `ffmpeg_loader.py:241,274` (`timeout=10`), `:161,164` (`wait(timeout=5)`), `:514` (`timeout=300  # 5 minute timeout`)
- **Status**: NEW
- **Age**: not determined (unified_loader comment cites #5326)
- **Effort**: trivial
- **Description**: `unified_loader` comment says its ffprobe call was "two hand-written copies ... had already drifted apart once (#5326)"; the command was unified through `ffprobe_command()` but the timeout was not. The decode timeout `300` is a bare literal that caps total decode time regardless of file length.
- **Suggested Fix**: `FFPROBE_TIMEOUT_S`, `FFMPEG_VERSION_CHECK_TIMEOUT_S`, `FFMPEG_DECODE_TIMEOUT_S` beside `ffprobe_command()` in `ffmpeg_loader.py`; `unified_loader` imports it.
- **Related**: whether 300 s is enough for multi-hour FFmpeg-format inputs is an `/audit-engine` question (#5739 covers FFmpeg full-decode).

##### TD4-05: `PRAGMA busy_timeout=60000` typed in three connection-setup sites
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/library/database.py:176`, `auralis/library/migration_engine.py:59`, `auralis/analysis/fingerprint/fingerprint_service.py:60`
- **Status**: NEW
- **Age**: `6899d0c7` 2026-07-26 (database.py)
- **Effort**: trivial
- **Description**: Same literal, in an f-less SQL string, in three independent PRAGMA blocks (two commented `# 60s`, one not). `database.py:143-144` also hardcodes `pool_size=5, max_overflow=5` with comments that restate the arithmetic.
- **Suggested Fix**: `SQLITE_BUSY_TIMEOUT_MS = 60_000` in `auralis/library/` (a `sqlite_pragmas.py` or `database.py` constant) and an `apply_connection_pragmas(cursor)` helper if the other PRAGMAs (WAL, foreign_keys) are also repeated; the fingerprint_service copy imports it.

##### TD4-06: Frontend WebSocket reconnect policy and request timeout are each defined twice, with diverging values
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: reconnect: `auralis-web/frontend/src/utils/errorHandling.ts:36-41` (`DEFAULT_WEBSOCKET_CONFIG`: 10 / 1000 / 30000 / backoff 1.5) vs `hooks/websocket/useWebSocketConnection.ts:189-193` (10 or 3 / 1000 / 30000 / backoff **2**); timeout: `utils/apiRequest.ts:43` (`DEFAULT_TIMEOUT_MS = 30000`) vs `hooks/api/useRestAPI.ts:19` (`REQUEST_TIMEOUT = 30000`)
- **Status**: NEW (#5190 is about missing timeouts, not duplicated values)
- **Age**: `166f8fba` 2025-11-30 (reconnect); `bb410dec` 2026-03-22 (heartbeat)
- **Effort**: small
- **Description**: `useWebSocketConnection` is the only `new WebSocketManager(...)` caller and overrides every field of the default, so `DEFAULT_WEBSOCKET_CONFIG`'s 1.5x multiplier is unreachable and misleading. `useRestAPI` re-implements the same 30 s AbortController timeout that `apiRequest` exports as a constant. Related literal clusters: React-Query `staleTime: 5 * 60 * 1000` x4 (`App.tsx:20` as `1000*60*5`, `useTrackFingerprint.ts:87`, `useAlbumFingerprint.ts:93,151`) plus `similarityCache.ts:42 CACHE_TTL_MS = 5*60*1000`; search debounce `300` ms in `useSearchLogic.ts:63` (inline), `navigation/SearchBar.tsx:22`, `library/SearchBar.tsx:48` (defaults) and `core/useSearchInput.ts:11` (named `SEARCH_DEBOUNCE_MS`).
- **Impact**: Retuning needs 2-4 edits; the unreachable default invites someone to "fix" the wrong copy.
- **Suggested Fix**: Delete the per-field overrides in `useWebSocketConnection` (keep only `maxReconnectAttempts` dev override) or delete the defaults; import `DEFAULT_TIMEOUT_MS` in `useRestAPI`; add `QUERY_STALE_TIME_MS`/`SEARCH_DEBOUNCE_MS` to a shared `config/timing.ts` (or the design-system `layout`/`motion` tokens).
- **Siblings (backend)**: heartbeat `30`/`10` s defaults in `websocket/websocket_protocol.py:20` re-typed as `HeartbeatManager(interval_seconds=30, timeout_seconds=10)` at `ws_handlers/connection.py:117`, while the other WS limits live in `config/limits.py:195-202`; move to `config/limits.py`.

##### TD4-07: Accent RGB triple `115, 102, 240` and a dark-page palette re-typed outside the design system
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/frontend/src/components/library/AlbumCharacterPane/animations.ts:16,19,71,74` (`var(--accent-rgb, 115, 102, 240)` fallback x4; `--accent-rgb` is defined globally at `styles/globalStyles.ts:58`); `src/index.tsx:54` (`background:#1a1a1a;color:#fff` boot-failure page), `:25-26` (`color: #00d4ff` console style)
- **Status**: NEW (not covered by #5648, which is spacing/radius/line-height/duration)
- **Effort**: trivial
- **Description**: Raw colors in non-test `.ts/.tsx` outside `design-system/` total only ~17 genuine literals (the rest of the 1344 regex hits are `#NNNN` issue numbers in comments). Remaining non-dynamic ones: `store/middleware/loggerMiddleware.ts:63-67,215,221` (7 console-styling hexes, dev-only) and the sites above. The fallback in `animations.ts` is redundant since the variable is always defined.
- **Suggested Fix**: Drop the `, 115, 102, 240` fallbacks; leave `loggerMiddleware`/`index.tsx` console styles (dev tooling, no token consumer) or reference `tokens.colors.*`.

#### Dimension 5: Stub & Placeholder Implementations

##### TD5-01: `LibraryScanner` wraps four real-DB calls in `except AttributeError: pass` purely to tolerate mock databases
- **Severity**: LOW
- **Dimension**: Stub Implementations (test-double accommodation in shipped code)
- **Location**: `auralis/library/scanner/scanner.py:113-128` (`_release_scan_slot_safe`, `_release_scan_paths_safe`), `:152-157` (`try_acquire_scan_slot`), `:173-177` (`try_reserve_scan_paths`)
- **Status**: NEW
- **Age**: guard #2438 / #3455 / #4509 (comments still say "lightweight mock library_database"); text last carried through `b75d62a4` 2026-08-27 (rename)
- **Effort**: small
- **Description**: Both production callers (`routers/library_scan.py:230`, `services/library_auto_scanner.py:225`) pass a real `LibraryDatabase`, which always defines `try_acquire_scan_slot`, `try_reserve_scan_paths`, `release_scan_slot` and `release_scan_paths` (`library/database.py:308,340`). The four `except AttributeError: pass` blocks therefore exist only so tests can hand the scanner a bare `MagicMock()` or stub. Worse, they make the concurrency guard fail open: an `AttributeError` raised *inside* the real method (e.g. a renamed attribute) is swallowed, `_acquired` stays `True`, and the scan runs unguarded.
- **Evidence**:
  ```python
  try:
      _acquired, _max_scans = self.library_database.try_acquire_scan_slot()
  except AttributeError:
      pass  # library_database is a lightweight mock; skip guard
  ```
- **Impact**: Hides a real concurrency-guard regression behind a test convenience; every new `library_database` method added to the scan path invites the same copy-pasted guard.
- **Siblings**: only these 4 `except AttributeError` sites exist in non-test code (`grep -rn "except AttributeError" auralis auralis-web/backend`).
- **Related**: `/audit-concurrency` (fail-open guard).
- **Suggested Fix**: Delete the four try/except wrappers and call the methods directly; give the tests that pass `MagicMock()` a `spec=LibraryDatabase` mock (which carries the four methods) instead.

##### TD5-02: `serialize_object()` branches on the *class name* "Mock" and keeps three `DEFAULT_*_FIELDS` maps that real rows never reach
- **Severity**: LOW
- **Dimension**: Stub Implementations (test-double accommodation in shipped code)
- **Location**: `auralis-web/backend/routers/serializers.py:18-40` (block comment), `:120-170` (`serialize_object`), `DEFAULT_TRACK_FIELDS` / `DEFAULT_ALBUM_FIELDS` / `DEFAULT_ARTIST_FIELDS` / `DEFAULT_PLAYLIST_FIELDS`, `:309-318` (`serialize_playlist` Mock-guard); also `auralis-web/backend/player_state.py:147-152` ("`getattr` on a Mock auto-creates a Mock attribute")
- **Status**: NEW (#4708 documented the divergence and is CLOSED; it did not remove the mechanism)
- **Age**: `f6d5e612` 2025-11-12
- **Effort**: medium (the tests that feed Mocks must move to real or `spec=`'d objects first)
- **Description**: `serialize_object` returns `obj.to_dict()` unless `'Mock' in type(obj).__name__`, in which case it projects `getattr` over a per-type defaults map. Its own comment states the maps are "NOT the response contract" and are reached only by Mocks or a `to_dict()` that raised. So four hand-maintained default maps, a name-sniffing branch, and the `try/except (TypeError, SQLAlchemyError)` in `serialize_playlist` exist to serve tests. They have already diverged from `to_dict()` (#4708) and need a pinned test (`test_serializer_fallback_divergence_4708.py`) just to stay documented.
- **Evidence**: `if 'Mock' not in obj_type_name and 'MagicMock' not in obj_type_name:` (serializers.py:147); `tests/backend/test_serializers.py` and `test_main_api.py:153` assert the *default maps*, not the API.
- **Impact**: Production behavior depends on a type name; the dead maps are a trap for anyone who reads them as the response contract (that misreading is the origin of #4708).
- **Siblings**: `schemas/library.py:71-72` re-explains the same fallback; `routers/artists.py:28,68,109` carry comments about it.
- **Related**: TD5-01 (same smell). Owning audit: `/audit-backend`.
- **Suggested Fix**: Make `serialize_object` call `obj.to_dict()` for objects that have one, with the exception path logged and re-raised; delete the Mock check and the four maps; convert the Mock-based serializer tests to small real dataclass/ORM fixtures.

##### TD5-03: Frontend no-op / debug-only callbacks left in shipped components
- **Severity**: LOW
- **Dimension**: Stub Implementations
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:167-168`; `components/ComfortableApp.tsx:216-219`; `components/library/AlbumCharacterPane/AlbumCharacterPane.tsx:161`; `components/library/Items/tables/TrackTableRowItem.tsx:140`
- **Status**: NEW (the `TrackTableRowItem`/`TrackRow` `onPlaylistsLoad` no-op is the cause of OPEN #5617, which is also what `Siblings` below refers to)
- **Age**: `b197637e` 2025-11-23 (Stage 7 refactor: `onSelectAllInfo`, `onPlaylistsLoad`); `7ebf04f5` 2025-10-22 (`console.log('Settings changed')`)
- **Effort**: trivial
- **Description**: (a) `useLibraryKeyboardShortcuts` declares `onSelectAllInfo` / `onClearSelectionInfo` as **required** but the only caller passes inline `() => {}`; because each render creates new function identities and both are in the effect's dependency array, the `window` keydown listener is torn down and re-added on every render of `CozyLibraryView`. (b) `ComfortableApp`'s `onSettingsChange` handler is `console.log('Settings changed:', settings)` plus a toast; `useSettingsDialog` also invokes it from `handleReset` (line 95), so a *reset* toasts "Settings saved successfully". (c) `onEnhancementToggle ?? (() => {})`: `useEnhancementControl().setEnabled` is always defined, so the fallback is dead. (d) `onPlaylistsLoad={() => {}}` is the stub behind #5617 (`fetchPlaylists` exists and is returned by `useTrackContextMenu` but no component calls it).
- **Evidence**: `onSelectAllInfo: () => {}, onClearSelectionInfo: () => {}`; `console.log('Settings changed:', settings); success('Settings saved successfully');`
- **Impact**: Per-render listener churn on the library view; a misleading success toast on reset; a debug `console.log` in the shipped build; (d) is user-visible (see #5617).
- **Siblings**: `components/library/Items/tracks/TrackRow.tsx:192-194` (`onPlaylistsLoad={() => { /* fetch playlists */ }}`, same #5617); `components/shared/ContextMenu/contextMenuActions.tsx:57-234` (22 `callbacks.onX || (() => {})` menu items, tracked by OPEN #5614).
- **Related**: `/audit-frontend` for the reset-toast mismatch (real, minor bug).
- **Suggested Fix**: Make the two `*Info` params optional and drop the inline no-ops; make `onSettingsChange` a plain toast (and have reset call a separate "settings reset" path or none); drop the `?? (() => {})`; fix (d) via #5617.

##### TD5-04: `components/shared/ui/index.ts` is a placeholder barrel with zero importers, advertising six directories that do not exist
- **Severity**: LOW
- **Dimension**: Stub Implementations (overlaps Dim 2 Dead Code and Dim 7 Stale Documentation)
- **Location**: `auralis-web/frontend/src/components/shared/ui/index.ts:1-52`, `badges/index.ts`, `feedback/index.ts`, `media/index.ts` ("Future ... components will be added here"), `components/shared/ui/README.md:1-30`
- **Status**: NEW
- **Age**: `2d33253d` 2025-11-23 (header comment); README predates the RadialPresetSelector removal (#4861 follow-up)
- **Effort**: small
- **Description**: The barrel header lists `bars/ cards/ dialogs/ inputs/ lists/ tooltips/` as "ready for organization"; none exist. No file imports `@/components/shared/ui` (consumers import `.../ui/ThemeToggle`, `.../ui/feedback`, `.../ui/media` directly), so the barrel's only unique export, `ParameterChip` (`badges/ParameterChip.tsx`, 36 lines), has **no consumer anywhere**. The README still documents `RadialPresetSelector.tsx` (302 lines), which the barrel itself says was deleted, and shows `import { RadialPresetSelector } from '@/components/shared/ui'`.
- **Evidence**: `grep -rln ParameterChip src` returns only `ui/index.ts`, `ui/badges/{ParameterChip.tsx,index.ts}`; `grep -rnE "from '@/components/shared/ui'" src` returns nothing outside the README.
- **Impact**: New components get filed into a scheme (empty dirs, "Phase 3") that no longer exists; the README sends readers to a deleted component.
- **Siblings**: the three "Future ... components will be added here" lines in `badges/`, `feedback/`, `media/` `index.ts`.
- **Related**: Dim 2 (dead `ParameterChip`), Dim 7 (README rot).
- **Suggested Fix**: Delete `shared/ui/index.ts`, `badges/` (with `ParameterChip`) and the README's stale sections (or reduce the README to a 5-line directory description); drop the "Future ..." comments.
- **Merged — TD7-04 (Dim 7)**: `components/shared/ui/README.md` (`4664e1e1`, 2025-11-23, never touched since) gives a file tree, import examples and a "Phase 3" refactor plan for `RadialPresetSelector` and its planned `PresetItem`/`usePresetSelection`/`presetConfig` extractions. All of it was deleted in `ae9d28e3` (2026-09-13, presets narrowed to `'adaptive'`). The path gate cannot see it because the refs are not backticked paths. Rewrite the README to the six live entries or delete it.

##### TD5-06: Single-implementer ABCs left over after the multi-branch mastering design was removed
- **Severity**: LOW
- **Dimension**: Stub Implementations (abstract interface with exactly one concrete class)
- **Location**: `auralis/core/mastering_branches/base.py:24-80` (`ProcessingBranch`, sole subclass `ContinuousMasteringBranch` in `continuous.py:25`); `auralis/analysis/base_spectrum_analyzer.py:40` (`BaseSpectrumAnalyzer`, sole subclass `SpectrumAnalyzer` at `:229` in the same file)
- **Status**: NEW
- **Age**: `d96e7729` 2026-07-28 (removed the other branches; `ProcessingBranch` kept)
- **Effort**: small
- **Description**: `ProcessingBranch`'s docstring now says it is the shared interface for "the single measurement-driven mastering path", i.e. one implementation. Its only non-subclass consumer is a doc'd helper `_assert_finite` (tested at `tests/auralis/core/test_nan_detection.py:283`). `BaseSpectrumAnalyzer` + `SpectrumAnalyzer` live in the same 287-line file and nothing else subclasses or type-hints against the base. CLAUDE.md principle 3 says "no variants".
- **Evidence**: `grep -rn "ProcessingBranch" auralis tests` returns the base, `continuous.py`, `__init__.py` and one test docstring; `grep -rn BaseSpectrumAnalyzer` returns only its own file.
- **Impact**: An extra indirection layer to read through for each change; an abstract `apply` signature (8 params) that must stay in sync with its single override.
- **Siblings**: none (`BaseAssessor` has 5 implementers and is legitimate).
- **Related**: Dim 9 (the `base_spectrum_analyzer.py` file size).
- **Suggested Fix**: Fold `ProcessingBranch` into `ContinuousMasteringBranch` (keeping `_assert_finite`), and fold `BaseSpectrumAnalyzer` into `SpectrumAnalyzer`; update the one test and the `mastering_branches/__init__.py` export.

### Not a finding, trivial note
`AudioFingerprintAnalyzer.__init__` (`analysis/fingerprint/audio_fingerprint_analyzer.py:84`, body `pass`) and `SidecarManager.__init__` (`library/sidecar_manager.py:48`, docstring only) are empty constructors; delete them with the next edit to either file. Not worth an issue on its own.

#### Dimension 6: Test Hygiene

##### TD6-01: ~20 collected tests have zero assertions and a "documents expected behavior" comment (post-#5225 residue)
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_boundary_max_min_values.py:733,763,798,862`; `tests/stress/test_edge_cases.py:224,343,438`; `tests/stress/test_processing_stress.py:384,567`; `tests/backend/test_error_handling.py:271,390`; `tests/backend/test_boundary_data_integrity.py:309`; `tests/backend/test_boundary_integration_stress.py:193`; `tests/backend/test_artwork_integration.py:132,181`; `tests/auralis/core/test_core.py:157`; `tests/auralis/player/test_enhanced_player.py:312`; `tests/auralis/player/test_enhanced_player_detailed.py:104`; `tests/backend/test_database_migrations.py:306`; `tests/regression/test_version_compatibility.py:120`
- **Status**: NEW (#5225 closed the print-only set, #5023 narrowed `except Exception: pass`; neither covers assertion-free tests that don't print)
- **Age**: mostly `52a6704d` 2025-11-07 / `8b9f0d70` 2025-11-09; still present at HEAD
- **Effort**: small
- **Description**: AST scan of `tests/` (test_* function with no `assert`, no `pytest.raises`, no `assert*/check*/verify*` call): 81 hits, of which ~60 are legitimate (fixtures named `test_db`/`test_audio_dir`, "does not raise" no-op checks, `@pytest.mark.skip` bodies). The ~20 above are not: the docstring promises behaviour and the body ends in a comment instead of an assertion.
- **Evidence**:
  - `test_repeated_processing_no_memory_leak`: loops `processor.process()` 100x then `# Memory usage should be stable (no leak)  # This test documents expected behavior`.
  - `test_sql_injection_attempt_in_search`: ends `tracks, total = db.tracks.get_all(limit=10)  # Should not raise "no such table" error`, discarding the result.
  - `test_circular_playlist_reference`: creates a `Playlist`, then `# This is a conceptual test`.
  - `test_network_timeout_handling` (`test_processing_stress.py:567`): opens a raw socket to 192.0.2.1 and swallows both outcomes; it exercises no Auralis code at all.
  - `test_artwork_extraction_creates_cache` / `test_extract_embedded_artwork`: docstring workflow of 3-4 steps, body is two comments (`# Test would verify cache file exists and is valid`).
  - `test_effects_and_processing` (`test_enhanced_player.py:312`): two `try: ... except Exception: pass  # May not be implemented`.
- **Impact**: Green with no coverage; `check_weak_assertions.py` deliberately skips zero-assert tests ("a different defect, #4246"), and #5225's AST required `print(`, so nothing gates this class.
- **Siblings**: 21 more `except Exception/bare: pass` handlers inside test bodies in 11 files (AST count): `tests/auralis/player/test_enhanced_player.py` 5, `tests/edge_cases/test_filesystem_errors.py` 4, `tests/backend/test_boundary_advanced_scenarios.py` 3, `tests/security/test_data_security.py` 2, plus 1 each in `tests/auralis/dsp/test_basic.py:119`, `tests/auralis/io_module/test_saver.py:238`, `tests/backend/test_absolute_path_log_hygiene.py:118`, `tests/backend/test_error_handling.py:362`, `tests/backend/test_scan_fingerprint_enqueue.py:219`, `tests/edge_cases/test_resource_exhaustion.py:385`, `tests/load_stress/test_memory_resource_stress.py:174` (down from ~60 at #5023).
- **Related**: #5225, #4246, #5023, #5154 (all closed).
- **Suggested Fix**: For each, assert the one observable the docstring names (stored value after injection, `len(result)==len(audio)` in the leak loop, cache file exists) or delete it. Extend `check_weak_assertions.py` with a second mode that fails on new zero-assertion `test_*` functions outside a small allowlist, so the class is gated the way `is not None` now is.

##### TD6-02: Capability guards that cannot fire, and first-party `ImportError` converted to `pytest.skip`
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/conftest.py:54-61,84,96,556,559`; `tests/backend/conftest.py:225-272`; `tests/auralis/core/test_core.py:308,323,353,383,401,420`; `tests/auralis/player/test_enhanced_player_detailed.py:59,216,226,274,314,406,450` (7+ "Enhanced audio player not available")
- **Status**: NEW (#4969 narrowed the boundary-test skips; #4867 deleted one instance of this exact shape; neither swept these)
- **Age**: `9333e1cc` 2025-09-13 (HAS_*), `3cfa7e39` 2025-11-18 (backend `client`)
- **Effort**: small
- **Description**: (a) `tests/conftest.py` defines `HAS_MATCHERING = True` / `HAS_PLAYER = True` inside `try:` blocks that contain no import, so the `except ImportError` arm and the four `pytest.skip("matchering player not available")` consumers (fixtures `test_config`, `full_config`, hook `pytest_runtest_setup`) are unreachable. No other file imports either flag. (b) The backend `client` fixture wraps `from main import app` **and** `with TestClient(app)` (lifespan startup) in `except ImportError: pytest.skip("Backend main app not available")`; an `ImportError` anywhere in app import or startup silently skips every API test built on it (15 files define or use it). (c) `test_core.py` and `test_enhanced_player_detailed.py` import first-party modules inside the test and skip on `ImportError`; `test_core.py` also has `except Exception as e: assert 'config' in str(e).lower()` branches that bless a crash message.
- **Evidence**: `tests/conftest.py:58-61` `try: HAS_PLAYER = True / except ImportError: HAS_PLAYER = False`; `test_core.py:358-364` records that #4867 found a test in this file that "skipped on every run it ever made".
- **Impact**: Renaming `RealtimeProcessor` or breaking a `main.py` import turns tests into skips, not failures. Both CI gates only check for new failures and a non-zero collected count, so a mass skip passes.
- **Siblings**: `tests/integration/test_priority4_streaming_integration.py:9-10` already documents this hazard and fixed its own instance.
- **Related**: #4969, #4867, #4691 (its ratchet `tests/backend/test_no_unaccountable_skips_4691.py` only inspects module-level `pytestmark` skips, not dynamic ones).
- **Suggested Fix**: Delete `HAS_MATCHERING`/`HAS_PLAYER` and their four skips. Replace the `ImportError` arms with plain top-of-module imports (let collection fail loudly); drop the backend `client` fixture's `except ImportError` so an import error is an error, not a skip.

##### TD6-03: Four unconditional skips carry no issue reference and have been dead 11-12 months
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/test_preset_system.py:353` (`test_empty_audio_handling`); `tests/backend/test_api_endpoint_integration.py:435` (`test_playlist_create_api`); `tests/backend/test_library_pagination_invariants.py:965` (`test_pagination_consistency_with_concurrent_modifications`); `tests/stress/test_processing_stress.py:326` (`test_process_many_channels`, `@pytest.mark.skip(reason="Multi-channel audio not yet supported")`)
- **Status**: NEW (#5155 swept four other skips; #5024 two perf skips; these four were outside both)
- **Age**: `8d124952` 2025-10-23, `241512d5` 2025-11-18, `d7620c96` 2025-11-06, `8b9f0d70` 2025-11-09
- **Effort**: trivial
- **Description**: Each is an unconditional skip (in-body `pytest.skip("...")` or a bare decorator) with prose reasons ("not yet implemented", "requires repository session refactoring", "Known limitation") and no `#NNNN`. `tests/backend/test_no_unaccountable_skips_4691.py` only polices module-level `pytestmark`, so unconditional skips in function bodies and method decorators are invisible. Two document a design limit rather than a pending fix (offset pagination vs concurrent writes; empty audio into the analyzer), and `test_playlist_create_api` is superseded by playlist tests that now pass.
- **Evidence**: `test_library_pagination_invariants.py:964-965`: `# This test is intentionally marked as expected to have issues` then `pytest.skip("Known limitation: ...")` (observed `SKIPPED` in a `-rs` run of the file).
- **Impact**: Indistinguishable from "someone gave up"; the bodies are the same empty-shape that #4767 and #5428 removed elsewhere.
- **Siblings**: documented slow-test skips `tests/stress/test_large_library.py:71,468` and `test_processing_stress.py:74` carry timing reasons and are acceptable (see Checked and clean).
- **Related**: #5155, #5024, #4691.
- **Suggested Fix**: Delete the three design-limit/duplicate tests (pagination-concurrency, empty-audio, playlist-create), and either delete the multi-channel stub or cite an issue in its `reason=`. Extend the #4691 ratchet to AST-walk `pytest.skip(...)`/`mark.skip(...)` call sites in all of `tests/` and require `#\d{3,}` or an allowlisted environment keyword.

##### TD6-04: Three API tests structurally skip because they depend on ambient library contents
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_api_endpoint_integration.py:320-324,367-376,465,496-500` (skips: "No tracks in library" at 324, 371, 500; sibling failure `IndexError` at 467 is the baselined `test_playlist_add_tracks_api`)
- **Status**: NEW (same shape as closed #4789, whose fix targeted `test_library_pagination_invariants.py` only)
- **Age**: `241512d5` 2025-11-18
- **Effort**: small
- **Description**: Verified with `HOME=<scratch> pytest -rs tests/backend/test_api_endpoint_integration.py`: three tests report `SKIPPED ... No tracks in library` and a fourth crashes on `["tracks"][0]`, because the `client` fixture boots against whatever `~/.auralis/library.db` holds. On CI (empty home) and on any clean checkout these never run; on a developer machine with a real library they run against real data.
- **Evidence**: `tests/backend/test_api_endpoint_integration.py:324` `pytest.skip("No tracks in library")`.
- **Impact**: Metadata, delete and favorites flows have no CI coverage here, and the #4789 closure reads as complete.
- **Siblings**: `tests/auralis/analysis/fingerprint/test_similarity_system.py:110-263` (8 data-count skips; its fixture does populate and they did not fire in the run, so defensive only); `test_library_pagination_invariants.py` has 12 "No albums/tracks" skips that did not fire after #4789 and could become `assert total > 0`.
- **Related**: #4789 (closed), #5398.
- **Suggested Fix**: Seed tracks through the repository inside the test (the `TrackRepository.add` pattern used by `test_library_pagination_invariants.py`) and turn the "No X" skips into `assert total > 0`.

##### TD6-05: Both failure baselines list tests that no longer exist (invisible to `--strict-stale`), plus entries that now pass
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `pytest-baseline.json` lines 64 and 108; `auralis-web/frontend/test-baseline.json` entries `src/hooks/shared/__tests__/useReduxState.test.tsx::Redux State Hooks usePlayer should return player state and actions` and `... usePlayer should seek to position`
- **Status**: NEW (#5091 closed the "passes but still baselined" half; the "no longer exists" half is outside `--strict-stale`, which "counts only tests actually present in the report")
- **Age**: renamed test `ebce480c` 2026-09-14 (#5192); deleted module removed by `d62c9c1c` 2026-08-22 (#4592); frontend `usePlayer` describe removed by `82a1d4cd` 2026-10-20 (#5354)
- **Effort**: trivial
- **Description**: Static check of every nodeid (127 pytest, 101 frontend): pytest has 2 phantom entries: `tests.integration.test_repositories.TestDualModeCompatibility::test_static_and_factory_repositories_equivalent` (renamed to `test_library_database_and_factory_equivalent` in #5192; no such method exists) and `tests.regression.test_personal_preferences_atomic.TestAtomicWrite::test_atomic_write_overwrites_existing` (file deleted). Frontend has 2 phantom entries (`usePlayer` describe deleted in #5354). A phantom entry silently re-permits a future test that reuses the name.
- **Evidence**: `ls tests/regression | grep personal` returns nothing; `grep -n usePlayer useReduxState.test.tsx` returns nothing.
- **Impact**: Baseline integrity. The pytest baseline also still carries 25 `tests/integration/test_repositories.py` entries although the whole file now passes (35 passed locally after #5192), 6 `test_cross_dimensional_interactions.py` entries (27 passed locally) and 4 `test_rust_fingerprint_glue.py` entries (9 passed locally; these last may depend on the CI Rust wheel). `--strict-stale` should fail CI on the first two groups, so the backend job is likely red for this reason and not for new failures (CI logs for the last failed run had expired, so not confirmed).
- **Siblings**: `.claude/commands/_audit-common.md:95` still says "157 `failures` entries as of `3e78c75d`"; the file now has 127 and `generatedFrom.failedTests` reads 149 (Dim 7 territory).
- **Related**: #5091, #4974, #5195 (open, 3 untracked failures).
- **Suggested Fix**: Hand-remove the 4 phantom entries and the entries for passing files now (per the baseline's own `_comment`: remove rather than regenerate locally). Add a `--prune-missing` step to both gate scripts that statically verifies each nodeid's file and test name exist, so phantom entries fail the gate.

##### TD6-06: `useAppDragDrop.test.ts` has nine behaviour-titled tests that assert only `result.current` is defined
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `auralis-web/frontend/src/hooks/app/__tests__/useAppDragDrop.test.ts:98-118,121-138,143-163,166-183,188-207,210-227,232-250,253-270,299-321`
- **Status**: NEW (not in #5674's file list, which names `testFixtures`, `useLibraryQuery`, `usePlaybackQueue`, `useRestAPI`; not in #5677)
- **Age**: `4890ac57` 2025-12-02
- **Effort**: small
- **Description**: Titles like "adds track to queue on drop", "reorders tracks in queue", "handles playlist reorder error" end in `expect(result.current).toBeDefined()` after a mocked handler call. The file's own comment at :414 admits this is why #5189 (within-list drag calls the add endpoint and duplicates the track) "went unnoticed", and then pins the buggy endpoints at :454 and :474 with `// should be ['PUT move']`.
- **Evidence**: `:138: expect(result.current).toBeDefined();` for "handles queue add error".
- **Impact**: A rewrite of `handleDragEnd` cannot fail 9 of its tests; the only real checks are the two characterization tests that must be flipped when #5189 lands.
- **Siblings**: a rough scan of frontend specs finds ~41 `it` blocks whose every `expect` is `toBeDefined/toBeTruthy/not.toBeNull`, concentrated in `useAppDragDrop.test.ts` (9), `useRestAPI.test.ts` (7, in #5674), `AlbumCharacterPaneComponents.test.tsx` (3, in #5677), `testFixtures.test.ts` (3, in #5674/#5682), `useAppLayout.test.ts` (2). The frontend equivalent of `check_weak_assertions.py` is #5682.
- **Related**: #5189 (OPEN, bug; owning audit `/audit-frontend`), #5674, #5677, #5682.
- **Suggested Fix**: Make each test assert the endpoint hit (reuse the `recordEndpoint` MSW helper already in the file) or the toast called, and delete the two characterization tests when #5189 is fixed.

#### Dimension 7: Stale Documentation & Comments

##### TD7-01: Queue-history retirement (#5526) not propagated to agent/command docs; strict path gate red
- **Severity**: LOW (the dimension agent proposed MEDIUM; demoted at merge because no promotion row strictly fires: no audit has been shown to have been misled. Ranked as a top Quick Win instead)
- **Dimension**: Stale Documentation
- **Location**: `.claude/agents/backend-specialist.md:22` (`player_queue_history.py`); `.claude/agents/library-specialist.md:9,37` ("13 repositories", `queue_history_repository.py`); `.claude/commands/audit-integration.md:150` (path in backticks); `.claude/commands/_audit-common.md:20,172` ("13 repos ... queue_history"); `.claude/commands/audit-engine.md:149` ("13 repository classes"); `CLAUDE.md:117-119` ("13 repos ... queue_history"); `docs/development/REPOSITORY_PATTERN.md:212` ("QueueHistoryRepository - Undo/redo history")
- **Status**: NEW
- **Age**: deleting commit `7088915d` 2026-10-19 "refactor: retire the unwired queue history/undo feature (#5526)" (26 files, -2339 lines). It touched `docs/MIGRATION_GUIDE.md` and `docs/subsystems/backend-api.md` but none of the files above. Gate was last green 2026-10-17 (`657cbeec`); first red master run is the 2026-10-21T23:00Z push that carried it.
- **Effort**: trivial
- **Description**: The queue undo feature, its router (`player_queue_history.py`), `queue_history_repository.py`, ORM models (`queue_state`, `queue_history` tables dropped by migration v20->v21), and the frontend `useQueueHistory` hook were all removed. The live repository count is now **12** (`scripts/check_doc_counts.py` says so and flags 3 of the 5 count locations). Four backticked refs to the deleted files make the strict half of `_audit-validate.sh` exit 1. `library-specialist.md:37` still tells the agent that `queue_history_repository.py` is a live repository "and the singleton `QueueState` row it hangs off", and `audit-integration.md:150` lists it as the "Persisted queue" data-flow endpoint.
- **Evidence**: `validate.txt` strict failures: `STALE: .claude/agents/backend-specialist.md — player_queue_history.py`, `STALE: .claude/agents/library-specialist.md — queue_history_repository.py`, `STALE: .claude/commands/audit-integration.md — auralis/library/repositories/queue_history_repository.py`. `ls auralis/library/repositories/` has no `queue_*`. CLAUDE.md:119 still lists `queue_history` in the repo enumeration. `check_doc_counts.py` does not look at CLAUDE.md's repo count at all, which is why the Codebase Map copy is not in its report.
- **Impact**: Library/integration auditors are told to audit a repository and a data flow that do not exist (wasted audit budget, false "missing coverage" findings). The red gate also trains contributors to ignore it, which is how #5144 happened the first time.
- **Siblings**: `.claude/agents/backend-specialist.md:21` also says "36 `.py` files: 20 registered + 6 shared + 10 router siblings" (live: 34, see TD7-03). `docs/subsystems/backend-api.md:111` already carries the correct "retired unwired" note and is the model to copy.
- **Related**: #5526 (closed, the retirement), #5144 (closed, made the gate enforce), #5044 (closed, the previous repo-count regression).
- **Suggested Fix**: De-backtick (italics) the three deleted paths, delete `library-specialist.md:37` and `REPOSITORY_PATTERN.md:212`, change "13" to "12" and drop `queue_history` from the five enumeration sites, and drop the "Persisted queue" row (or restate it as "queue is not persisted") in `audit-integration.md`. Extend `check_doc_counts.py` to also scan CLAUDE.md's Codebase Map for the repo count so the sixth site cannot hide.

##### TD7-02: Frontend deletions in #5521 and #5642 left stale path refs in 6 docs (ratchet 295 vs 287) plus a wrong provider tree
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: Strict: `docs/subsystems/frontend.md:163` (`design-system/__tests__/cssVariablesTokenParity.test.ts`). Ratchet-new: `docs/frontend/FRONTEND_REMEDIATION_PLAN.md` (`ShuffleModeSelector.module.css`, `index.css`); `docs/frontend/analysis/PLAYER_COMPONENT_CONSOLIDATION_PLAN.md` (`player/TrackInfo.tsx` x3); `docs/frontend/implementation/README_PLAYER_ANALYSIS.md` (`player/TrackInfo.tsx`); `docs/frontend/testing/FRONTEND_TESTING_STRATEGY.md` (`ShuffleModeSelector.test.tsx`); `docs/ui_audit/IMPLEMENTATION_STATUS.md` (`TrackInfo.tsx`). Content drift: `docs/subsystems/frontend.md:36,171`
- **Status**: NEW
- **Age**: `05cbb1c1` 2026-10-21 "delete the never-loaded index.css and the dead ShuffleModeSelector (#5642)" deleted `index.css`, `ShuffleModeSelector.{tsx,module.css,test.tsx}` and `cssVariablesTokenParity.test.ts`; `711d8860` 2026-10-18 (#5521) deleted `player/TrackInfo.tsx`. The `frontend.md` line dates to `dbb3b4a5` 2026-07-11.
- **Effort**: trivial
- **Description**: Eight ratchet-new stale refs (7 distinct docs lines) plus one strict failure. Separately, the authoritative `frontend.md` provider-tree line names `AudioReactiveStarfield`, which was deleted (the wrapper was folded into `StarfieldBackground` by #5661; `App.tsx:49` says so) and omits `PlaybackSessionProvider`, which `App.tsx` now nests around `ComfortableApp` (#4541). `frontend.md:171` lists `background/ (AudioReactiveStarfield)` too.
- **Evidence**: `git log --diff-filter=DR` for each target lands on `05cbb1c1` or `711d8860`. `App.tsx` tree: `ThemeProvider > StarfieldBackground + ToastProvider > WebSocketProvider > PlayerStateSync + PlaybackSessionProvider > ComfortableApp`.
- **Impact**: Second red contributor to the gate (with TD7-01); the `docs/frontend/*` plans describe components that no longer exist and are indistinguishable from live design docs.
- **Siblings**: `docs/frontend/*` and `docs/ui_audit/*` are a ~290-entry baselined ratchet of the same pattern; none of these should have grown the baseline.
- **Related**: TD7-01 (same gate); #5642, #5521 (closed); #5661 (starfield).
- **Suggested Fix**: Fix `frontend.md` (replace the test ref with the test that now guards token parity, e.g. `theme/__tests__/cssCustomPropertyProducers.test.ts`, and correct the provider tree). For the 6 `docs/frontend/` and `docs/ui_audit/` files, de-backtick the deleted names, or archive the player-consolidation plan and `README_PLAYER_ANALYSIS.md` under `docs/archive/` with a superseded banner.

##### TD7-03: Hand-copied structural counts drifted again in CLAUDE.md, `_audit-common.md`, and the agent/architecture docs
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: see Evidence table
- **Status**: NEW (closed precedents #4685, #4982, #5033, #5045, #5044 are each one earlier instance of the same defect)
- **Age**: Most lines from `15dcf4c2` 2026-09-13; `_audit-common.md:32` from `54d055df` 2026-07-25; `docs/architecture/overview.md:119` and `module-map.md:19` from `dbb3b4a5` 2026-07-11; `module-map.md:51` from `e216021f` 2026-08-16.
- **Effort**: small
- **Description**: Numbers copied by hand into prose, only partly covered by `check_doc_counts.py`, which WARNs (non-blocking) on test counts and blocks only on the repo count. Nothing at all checks the baseline-entry counts, schema version, router-file or service counts.
- **Evidence** (claim -> live, recomputed 2026-10-21/22):

  | Claim | Where | Live |
  |---|---|---|
  | 611 test files / ~6,759 functions | `CLAUDE.md:24,165`; `_audit-common.md:56` | 702 files / 7,207 functions (+15% files; script WARNs at 10%) |
  | `pytest-baseline.json` 157 entries | `CLAUDE.md:69`; `_audit-common.md:95` | 127 (`4f7c1a10`/`b00fe3e3`, 2026-10-20) |
  | frontend `test-baseline.json` 108 entries | `_audit-common.md:94` | 101 (`63baf189`, 2026-09-16) |
  | DB schema v21 | `CLAUDE.md:122` | 22 (`auralis/__version__.py:11`, #5574; `migration_v021_to_v022.sql`) |
  | migrations "through v017_to_v018" | `_audit-common.md:19` | v021_to_v022 |
  | DB schema v18 / v16 | `docs/architecture/module-map.md:51`; `overview.md:119` | 22; and `overview.md` points at `migration_manager.py` for the number, which only imports it from `auralis/__version__.py` |
  | ~5,100 test functions | `docs/architecture/module-map.md:19` | 7,207 |
  | routers dir "26 .py files" | `_audit-common.md:32` | 34 (+ `__init__.py`): 20 registered + 5 shared + 9 `player_*`/`processing_*` siblings |
  | routers dir "36 .py files: 20 + 6 shared + 10 siblings" | `.claude/agents/backend-specialist.md:21` | 34 (5 shared + 9 siblings, after `player_queue_history.py` was removed) |
  | services "11 modules" | `.claude/commands/audit-backend.md:36` | 17 (list omits `missing_tracks`, `scanner_stop`, `queue_service_base`, `queue_{edit,order,set}_mixin`) |

  Verified still correct: analysis files 55, registered routers 20, `backend/core/` 54 modules, stages 13, Rust `src/*.rs` 19 and 11 exposed functions, docs topic dirs 18, version 1.5.1 everywhere (README and `docs/README.md` correctly describe it as the unreleased recovery milestone and the last binary as v1.2.0-beta.2).
- **Impact**: `_audit-common.md` is the file every audit agent is told to trust; a wrong "baseline has 157 entries" or "26 files" makes an auditor distrust a correct tree. This is the fifth round of the same drift.
- **Siblings**: all rows above. The CLAUDE.md note about running `check_doc_counts.py` already acknowledges the hazard but the script covers only a subset.
- **Related**: TD7-01 (repo count); #4982 (closed), #5045 (closed).
- **Suggested Fix**: Stop quoting derivable numbers: replace each with "run `python scripts/check_doc_counts.py`" or "count the file", as README.md and the frontend-baseline row already do. Where a number must stay, extend `check_doc_counts.py` to compute and verify baseline entry counts, `__db_schema_version__`, router file count, and service count against both docs, and make the test-count tolerance blocking.

##### TD7-05: PyInstaller spec lists five deleted backend modules as `hiddenimports`
- **Severity**: LOW
- **Dimension**: Stale Documentation (stale references in packaging config)
- **Location**: `auralis-web/backend/auralis-backend.spec:61-65` (`metrics_collector`, `audio_content_predictor`, `learning_system`, `self_tuner`, `memory_monitor`)
- **Status**: NEW
- **Age**: entries added `805bf9d8` 2025-12-27 / `57c5a289` 2025-12-21; targets deleted `ef2d6818` 2026-07-13 (self_tuner), `25cb394c` 2026-08-23 (memory_monitor, metrics_collector), `954dee54` 2026-08-23 (audio_content_predictor, learning_system). File last touched `34a3fe4b` 2026-09-16 (#5085), which did not clean these.
- **Effort**: trivial
- **Description**: PyInstaller treats a missing hidden import as a warning, so the desktop build still succeeds; the stale list asserts modules exist that do not and hides the real warning signal in `warn-auralis-backend.txt`. `desktop/` build pipeline was restored 2026-07-18 so this spec is live, not archival.
- **Evidence**: `find auralis-web/backend -name 'metrics_collector.py' ...` returns nothing for all five. (`schemas` also has no `schemas.py` now, but it is a package, so it resolves.)
- **Impact**: Low; erodes trust in the spec as the list of what the frozen backend really needs and invites re-adding "fixed" shims.
- **Related**: #4766, #5085 (closed deleters).
- **Suggested Fix**: Delete the five lines; consider generating hidden imports from `config/routes.py` so deletions cannot desync.

##### TD7-06: `quick_build.sh` invokes `build_auralis.py`, which does not exist
- **Severity**: LOW
- **Dimension**: Stale Documentation (broken documented entry point)
- **Location**: `quick_build.sh:107` (`python build_auralis.py $BUILD_ARGS`); header line 4 says `./scripts/quick_build.sh` but the file is at the repo root; `.claude/settings.local.json:7` also allowlists `python build_auralis.py *`
- **Status**: NEW (closed #5439 removed the stale Makefile and #4062 fixed `APPIMAGE_FIX.md`, but this tracked sibling was missed; first reported in `docs/audits/AUDIT_ENGINE_2026-07-25.md:349`, never filed)
- **Age**: last touched `46b4b951` 2026-07-16; `build_auralis.py` was deleted `f7d0a75d` 2025-09-29, so the script has been unrunnable for ~13 months.
- **Effort**: trivial
- **Description**: The script parses `--skip-tests/--portable-only/--clean`, prints a banner, then fails at the one line that matters. The real build path is the desktop pipeline (`desktop/` + PyInstaller spec + CI `build-release.yml`).
- **Impact**: A tracked, executable "quick build" that cannot work; the memory note "`build_auralis.py` does NOT exist" exists precisely because docs kept sending people to it.
- **Related**: #5439, #4062 (closed), `docs/audits/AUDIT_DEPRECATION_2026-09-13.md:694-715`.
- **Suggested Fix**: `git rm quick_build.sh` and the settings allowlist entry, or rewrite it to call the actual desktop build script.

##### TD7-07: Deletion commits do not run the path-reference gate, so every large deletion turns CI red after merge
- **Severity**: LOW
- **Dimension**: Stale Documentation (process cause of TD7-01/02)
- **Location**: `.github/workflows/path-references.yml` (CI only); `.claude/commands/_audit-validate.sh`; no pre-commit hook
- **Status**: NEW
- **Age**: gate made enforcing in `454101c4` 2026-08-16 (#5144); recurrences 2026-09-16 (`7e2f80a1`/`5b25ce5b`, resolved in-day) and now 2026-10-21 (still red)
- **Effort**: small
- **Description**: The gate only runs on push/PR, after the author has finished; both offending commits are large "delete the dead X" refactors by the same contributor that grepped code but not `.claude/` and `docs/`. The remaining 14 red runs sit on dependabot merges that have nothing to do with docs, so a real signal is buried under unrelated failures.
- **Impact**: Each deletion refactor costs a follow-up doc-fix commit; during the red window every unrelated PR shows a failing check.
- **Related**: #5144 (closed); TD7-01, TD7-02.
- **Suggested Fix**: Add `bash .claude/commands/_audit-validate.sh` (strict scope only) to the pre-commit/commit-msg hook set when a commit contains `D` entries, and add a "grep `.claude/` and `docs/architecture,subsystems`" step to the `fix-issue` skill's delete checklist.

#### Dimension 8: Backwards-Compat Cruft & "No Variants"

##### TD8-01: Residue of the deleted `LibraryManager`: a live exception class, user-visible 503 text, and "Phase 6B/6C" docstrings
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/routers/errors.py:55-58` (`LibraryManagerUnavailableError`, detail `"Library manager not available"`); raised at `routers/library_scan.py:203,228`, `routers/player_playback.py:96`, imported by `routers/player_deps.py:23`; literal `ServiceUnavailable("Library manager not available")` at `services/queue_edit_mixin.py:47,130`, `services/queue_set_mixin.py:49`; log text `config/startup/workers.py:174`
- **Status**: NEW (#4650/#4314 closed the "removal in v2.0.0" promise; #5162 renamed the globals key only)
- **Age**: class `f6d5e612` 2025-11-12; class deleted by #4915 (2026-08/09), name never followed
- **Effort**: small
- **Description**: `LibraryManager` was deleted in #4915 and the globals key was renamed `library_database` in #5162 so that "grepping the old name should return nothing" (`library/database.py:19`). It still returns 30+ hits in shipped code. The exception class and 4 message literals name the dead class and are what a client sees in a 503 body. Eight docstrings carry the migration-phase breadcrumb "Phase 6B/6C: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)". 12 `Raises:` lines in `playlists.py`/`artwork.py`/`metadata.py`/`albums.py` say "library manager/factory not available". Two module docstrings (`library/__init__.py:15-21`, `library/database.py:9-21`) narrate the deletion history.
- **Evidence**: `class LibraryManagerUnavailableError(ServiceUnavailableError): """Library manager service unavailable"""`. Phase docstrings at `routers/albums.py:392`, `artists.py:156`, `artwork.py:668`, `metadata.py:648`, `playlists.py:630`, `player/integration_manager.py:34`, `player/queue_controller.py:25`, `player/enhanced_audio_player.py:54`; `routers/library.py:112` carries "Phase 6B" too, and `config/routes.py:146,162,200,208,215` label router registrations "Phase 6B".
- **Impact**: Every future reader (and audit) has to re-derive that "library manager" now means `LibraryDatabase`/`RepositoryFactory`; the exact grep the #5162 rename wanted to make clean is still noisy.
- **Siblings**: `config/startup/components.py:41`, `cli/fetch_artwork.py:153`, `library/scanner/batch_processor.py:111`, `services/fingerprint_queue_manager.py:42`, `library/scanner/{scanner.py:53,65, batch_processor.py:34, metadata_extractor.py:184,190}` ("library manager instance" for a `LibraryDatabase`), `core/state_manager.py:102`, `config/startup/fingerprint.py:38`.
- **Related**: tests in `tests/backend/test_error_responses.py` import the class (19 references total); update with the rename.
- **Suggested Fix**: Rename to `LibraryUnavailableError` with detail "Library not available" (one sed over 19 refs), unify the 3 `ServiceUnavailable("Library manager ...")` literals onto it, delete the 8 "Phase 6B/6C" lines and the two history essays (keep one sentence in `database.py`: "composition root").

##### TD8-02: "removed in #NNNN" breadcrumbs have regrown (5th recurrence: #4088, #4293, #4649, #5034, now this)
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: about 30 sites, grouped below
- **Status**: Regression of #5034 (closed 2026-08-07; same pattern, new instances)
- **Age**: mostly 2026-09 to 2026-10 (#5245, #5561, #5577, #5425, #5492, #5387, #5423, #5396, #5620)
- **Effort**: small (comment-only)
- **Description**: Comments that describe code that no longer exists, citing the issue that deleted it. The git history already carries this; the comment only adds a "this used to exist" line to a place where nothing exists.
- **Evidence** (all shipped code; present-tense content, if any, should be kept as one sentence):
  - Python: `auralis/core/hybrid_setup.py:170` ("was deleted with the rest of the..."), `core/mastering_process_chunk.py:139-142` ("STAGE 3 (output normalization) was removed in #5245"), `core/processing/continuous_dsp_ops.py:89,280` (#5561, #5577), `dsp/eq/curves.py:69` (#5201), `optimization/caching/smart_cache.py:27`, `optimization/acceleration/__init__.py:7` (#4565), `backend/core/audio_stream_controller.py:55` (#5425), `core/targets_hash.py:17` (#5492), `core/job_execution.py:69`, `core/audio_processing_pipeline.py:9` (#4334), `core/encoding/atomic_io.py:17` (#5208), `core/chunked_processor.py:196-197` (#5056), `routers/player.py:113-116` (#3884), `routers/metadata.py:342,392,499` ("Deliberately kept, not deleted (#5080)"), `config/app.py:113` (#5147), `config/routes.py:279` (#4435), `player_state.py:44`
  - TypeScript: `types/domain.ts:131-136` (#2280), `:160-177` (a 17-line list of deleted types, #5371/#4830/#5234), `hooks/fingerprint/index.ts:6-17` (12 lines about `useFingerprintCache`, #4239/#5215), `store/slices/connectionSlice.ts:173` and `playerSlice.ts:198` (#4921), `utils/errorHandling.ts:11` (#5387), `utils/audio/pcmDecoding.ts:8`, `types/ws/streaming.ts:106` (#5423), `store/middleware/errorTrackingMiddleware.ts:17` (#4695), `hooks/library/useScanProgress.ts:43` (#4648), `components/core/AppMainContent.tsx:27` (#5396), `components/library/Styles/ArtistDetail.styles.ts:17` (#4537), `ComfortableApp.tsx:160` (#5620), `theme/themeConfig.ts:386,398` (#4584, #4645), `hooks/shared/usePlayerRedux.ts:33`, `hooks/websocket/websocketConnectionCore.ts:87`
  - Stale "kept for compat" labels that no longer match the code: `dsp/advanced_dynamics.py:27` (`# Re-export for backward compatibility` above an `__all__` that now lists only live names), `hybrid_processor.py:233` ("NOTE: This method still exists for backward compatibility"), `hooks/player/useQueueFetch.ts:64` ("Kept as a fallback in case a legacy payload shape is ever seen": the code reads only `shuffle_enabled`).
- **Impact**: Recurring review noise; four earlier sweeps did not stick. Each such comment is also a place where a future refactor must decide whether the history is still true.
- **Related**: #5034, #4649, #4293, #4088 (all closed). CLAUDE.md Principle 5 prefers `# TODO(#NNNN)` markers for deferrals and no prose history.
- **Suggested Fix**: Delete the history sentences in one pass (keep only what constrains present code, e.g. "Deliberately kept (#5080): existence check now ..."). Add a grep gate to `scripts/` (e.g. `check_doc_counts.py` neighbour) that fails on `(was|were) (removed|deleted) (in|by|with) #\d+` in `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/` so a fifth sweep is not needed.

##### TD8-03: Parameters kept "for call-site compatibility" or left behind by refactors, still fed by live callers
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: see Evidence (all under `auralis-web/backend/` unless prefixed)
- **Status**: NEW (TD2-21 covers only `quantiles`, `post_dynamics`, `allow_silence`; none of these)
- **Age**: `routers/player.py` factory comment `3e551429` 2026-08-25; `chunk_operations.py` `e43cd538` 2026-08-05; `stream_enhanced_chunks.py` from #5032 split
- **Effort**: small
- **Description**: An AST pass for parameters never read in the function body (excluding `_`-prefixed, `self`/`cls`, `__exit__`, SQLAlchemy/watchdog/FastAPI callback signatures, and the uniform `auralis/core/stages/*.apply` interface) found a cluster where the caller still computes and passes the argument. The router-factory ones are explicitly annotated "accepted for call-site compatibility", which is a compatibility shim between two files of the same package.
- **Evidence**:
  - `routers/player.py:87-95,112-117`: `create_player_router(chunked_audio_processor_class, get_enhancement_settings, get_multi_tier_buffer)` accepted and ignored; passed at `config/routes.py:223-232` (the `chunked_audio_processor_class` import chain in `main.py` and the `lambda` closures exist only to feed them)
  - `routers/enhancement.py:726,747-750`: `get_processing_engine` ignored; passed at `config/routes.py:140`
  - `routers/system.py:294-299`: `HAS_AURALIS` ignored by `create_system_router`; passed at `config/routes.py:93,105`
  - `ws_handlers/connection.py:207-214`: `teardown_connection(..., get_processing_engine, ...)` ignored; passed at `routers/system.py:450-453`
  - `core/stream_enhanced_chunks.py:41-50`: `pump_enhanced_chunks(preset, intensity)` ignored (the removed-preset era left a `preset` string flowing through a function that no longer branches on it); passed at `core/stream_enhanced.py:242-243`
  - `core/chunk_operations.py:54-62`: `load_chunk_from_file(overlap_duration=...)` documented "Unused directly"; passed at `core/chunk_render.py:130`
  - `core/stream_fingerprint.py:120-125`: `check_or_queue_fingerprint(filepath)` ignored; passed by `audio_stream_controller.py:269`
  - `core/state_manager.py:94-95`: `set_track(track, library_database)` ignores `library_database`; passed at `services/queue_set_mixin.py:140-144`
  - `core/stream_chunk_ops.py:172-181`: `process_and_stream_chunk(on_progress)` ignored, docstring "(legacy entry point)"; the whole chain `AudioStreamController._process_and_stream_chunk` -> `process_and_stream_chunk` has only test callers (`tests/backend/test_stream_disconnect_toctou.py`)
  - `auralis/player/gapless_playback_engine.py:235-238`: `advance_with_prebuffer(was_playing)` ignored; passed at `player_queue_navigation_mixin.py:109`
  - `auralis/core/hybrid_processor.py:229,287` and `hybrid_stage_dispatch.py:101`: `results` ignored in `_process_adaptive_mode`, `_process_hybrid_mode`, `process_reference_mode`
  - `core/mastering_target_service.py:232-236`: `extract_fingerprint_from_audio(sample_rate=None)` never read, never passed
  - Less certain, also never read: `auralis/analysis/spectrum_operations.py:184 map_to_bands(sample_rate)`, `analysis/adaptive_mastering_engine.py:276,292 (fingerprint, profile)`, `analysis/ml/genre_classifier.py:117 (features)`, `analysis/fingerprint/metrics/robust_scaling.py:141 (epsilon)`, `quality_assessors/utilities/estimation_ops.py:22,395 (sr)`, `core/processing/adaptive_mode.py:147 (spectrum_position)`, `core/processing/hybrid_mode.py:70 (content_profile)`, `core/analysis/target_generator.py:252 (content_profile)`, `core/analysis/content_analyzer.py:292 (rolloff)`, `core/utils/smooth_curves.py:180 bipolar_s_curve(center)`, `dsp/utils/adaptive_loudness.py:177 (current_rms_db, rms_diff_from_target)`, `core/streamlined_tiers.py:164 build_tier2_cache(current_chunk)`, `learning/preference_engine.py:124 (action)`
- **Impact**: A reader assumes `preset`/`intensity`/`HAS_AURALIS` influence the function; a future caller "fixes" a bug by passing a different value that nothing reads.
- **Related**: TD2-21 (same pattern, different sites), TD8-08 (the `HAS_*` flags). `get_multi_tier_buffer` in `routers/player.py` is the dead end of the cache-naming split in TD8-11. Possible dropped logic behind `post_dynamics`/`results`/`spectrum_position`: `/audit-engine`.
- **Suggested Fix**: Delete the parameter and the call-site argument for each confirmed row (the router-factory ones also remove the closures in `config/routes.py`). Treat the "less certain" list as a follow-up sweep with `vulture --min-confidence 100` on the parameter names.
- **Merged — TD2-21 (Dim 2)**: three more never-read parameters, reported by vulture at 100%: `analysis/fingerprint/metrics/distribution_ops.py:98-102` (`quantiles`); `core/processing/cross_dimensional_guard.py:155` (`post_dynamics`, passed at `:218`; possibly a dropped check, so route it to `/audit-engine`); `backend/core/audio_processing_pipeline.py:381` (`allow_silence`, on a dead function, TD2-12).

##### TD8-04: Frontend parameters and flags that do nothing
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerDisplay.ts:36,68,101-110,134-135,192-193`; `utils/albumCharacterDescriptors.ts:207,368`; `components/library/Details/AlbumDetailView.tsx:52`; `components/library/Items/tracks/TrackRow.tsx:67`
- **Status**: NEW
- **Age**: `usePlayerDisplay` `1736a164` 2026-03-22
- **Effort**: trivial
- **Description**: `formatTime = (seconds, _showHours = false) => formatDuration(seconds)` discards its flag, yet the hook publishes a `forceShowHours` option, threads it through three `useMemo` dependency lists, and exports `formatSecondToTime(seconds, showHours)` that forwards it into the void. No caller outside this file passes `forceShowHours`. `generateDescription(fp, _tags)` takes a tag list it never reads (caller passes `selectedTags`). Two destructures bind a name only to rename it with `_` (`palette: _palette`, `imageError: _imageError`); simply not destructuring is the fix.
- **Evidence**: `const formatTime = (seconds: number, _showHours = false): string => formatDuration(seconds);`
- **Impact**: `forceShowHours: true` looks like a working switch and is not.
- **Related**: if hours should be forceable, that is a behaviour bug for `/audit-frontend`; as shipped the option is dead.
- **Siblings**: the `_fetchAbortRef`/`_statsAbortRef`/`_scanAbortRef` destructures in `hooks/library/useLibraryWithStats.ts:57-59` are the rest-omit idiom and are fine.
- **Suggested Fix**: Drop `forceShowHours`, `_showHours`/`showHours` (and `formatSecondToTime`'s second parameter), `_tags`, and the two `_x` destructures.

##### TD8-05: Same field under two spellings on the wire: `current_index`/`currentIndex`, `has_more`/`hasMore`, and the Track fallback twin fields
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/frontend/src/types/ws/queue.ts:38-42` and `hooks/player/useQueueSubscription.ts:65`; `hooks/library/libraryQueryTypes.ts:115-123` (+ call sites `useLibraryQuery.ts:165,238`); `api/transformers/types.ts:71-86`, `trackTransformer.ts:22-23,66-67`; backend `routers/serializers.py:46-80` (`DEFAULT_TRACK_FIELDS`) and `schemas/library.py:118-140` (`TrackResponse`)
- **Status**: NEW (#5401, #4909 touched serializers only for dead helpers)
- **Age**: `currentIndex` type `e2f71d38` 2026-06-02; singular fallback fields `7838e91e` 2026-02-21 (#2263); `has_more ?? hasMore` `ca49fde6` 2026-10-20
- **Effort**: small (frontend halves), medium (backend union)
- **Description**: Auralis is a single-client desktop app with one backend, so a transformer that accepts both spellings is dead weight. Verified emitters: the backend emits only `current_index` for `queue_changed` (`services/queue_service.py:62-80`, `websocket/outbound_messages.py:108`) and only `has_more` for every paginated route (`routers/pagination.py`, `tracks.py:91`, `albums.py:199`). The comment on `QueueChangedMessage` ("some emitters historically used camelCase") names no emitter. For Track, `to_dict()` emits `artists`, `genres`, `created_at`, `updated_at`, `lufs_level`; the singular `artist`, `genre`, and `date_added`, `date_modified`, `loudness` exist only in `DEFAULT_TRACK_FIELDS`, which `serializers.py:14-40` itself says is reached only for Mocks or when `to_dict()` raises. `TrackResponse` declares both sets, `TrackApiResponse` declares both sets, and `trackTransformer` reads `artists?.[0] ?? artist`, `genres?.[0] ?? genre`, `date_added ?? created_at`, `date_modified ?? updated_at`.
- **Impact**: Every Track field touch (the 2026-07 `genres` bug #2263/#4830 was this exact seam) needs two names considered in four files. The Pydantic union test (`tests/backend/test_response_model_coverage.py`) pins the duplication, so nobody can delete a twin without noticing.
- **Related**: #3838 (response_model rollout) is the owner of the union design; coordinate.
- **Suggested Fix**: Frontend: delete `currentIndex` from the type and `?? data.currentIndex`, drop `?? response.hasMore`, and make `deriveHasMore` read `has_more` only. Backend: shrink `DEFAULT_TRACK_FIELDS` to the `to_dict()` key set (the fallback should build the same shape), drop the twins from `TrackResponse`/`TrackApiResponse`, then remove the transformer fallbacks.

##### TD8-06: Removed preset vocabulary persists in the database and is tolerated at three read sites instead of being migrated once
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/helpers.py:109-128`; `routers/settings.py:154-182` (`_degrade_unknown_preset`); `ws_handlers/playback_commands.py:55-100,219-221`; frontend `components/settings/SettingsDialogContent.tsx:84-90`, `services/settingsService.ts:38-45` (`default_preset: ... | null`); vestigial columns `auralis/library/models/playlist.py:35` (`mastering_profile`, default `'balanced'`), `library/models/genre.py:31` (`preferred_profile`, default `'balanced'`, comment "warm, bright, punchy, balanced"); stale docstrings `core/stream_enhanced.py:55` and `core/stream_seek.py:61` ("Processing preset (adaptive, gentle, warm, etc.)")
- **Status**: NEW (#5332 fixed the tests; the 2026-09-13 narrowing was not paired with a data migration)
- **Age**: narrowing 2026-09-13; columns from the initial schema (`migration_v000_to_v001`)
- **Effort**: small
- **Description**: `user_settings.default_preset` rows written before the narrowing may hold `gentle|warm|bright|punchy|live`. Instead of one migration (`UPDATE user_settings SET default_preset='adaptive' WHERE default_preset != 'adaptive'`, schema v22 to v23), three code paths and the frontend's `| null` type each degrade an off-list value with a warning, so the legacy value is re-encountered and re-logged on every boot and every GET. Separately, `Playlist.mastering_profile` and `Genre.preferred_profile` are string columns defaulting to `'balanced'` (not a valid preset), written by nobody, and `mastering_profile` is serialized to the client and typed in `PlaylistWire` (`services/playlistService.ts:31`) with no reader. No removed preset name survives as a code literal (checked: only the deliberate `preset_anchors.py` and the Player test sentinel).
- **Evidence**: `if stored_preset in VALID_PRESETS: ... else: logger.warning(f"Stored default_preset {stored_preset!r} is not one of ...")`
- **Impact**: The tolerance code can never be deleted while the data could still be bad, and the null-able frontend type spreads that uncertainty into the UI.
- **Related**: #5755 (open) covers other dead `tracks` columns, not these two; `/audit-engine` for the migration mechanics.
- **Suggested Fix**: Add `migration_v022_to_v023.sql` normalizing `default_preset`, then delete the three degrade branches and make `default_preset` non-null in `SettingsResponse`/`settingsService.ts`. Fold `playlists.mastering_profile` and `genres.preferred_profile` into #5755's column-removal migration. Fix the two docstrings now.

##### TD8-07: `use_continuous_space` is a config toggle that is always `True`; its `False` branches are unreachable
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/core/config/unified_config.py:85-88`; `auralis/core/hybrid_processor.py:229-263`; `auralis-web/backend/core/job_finalize.py:50-69`; `auralis/core/processing/adaptive_mode.py:38-43`; sibling `auralis/core/hybrid_setup.py:121-122`
- **Status**: NEW (STREAMLINING_PLAN #5 kept `AdaptiveMode` for the `hybrid`/`reference` modes; that decision does not cover the flag)
- **Age**: `ad7f5245` 2025-11-04
- **Effort**: small
- **Description**: `grep use_continuous_space` over `auralis/`, `auralis-web/backend/` and `tests/` finds one assignment (`= True`) and no `= False` anywhere; two docstrings say "the only value the app ever sets". The `else:` arm in `_process_adaptive_mode` ("Using legacy preset-based processing") and the "(use_continuous_space=False, ...)" branch comments in `job_finalize` are therefore dead as written. The `hybrid`/`reference` modes that keep `AdaptiveMode` alive do not go through this flag. `_process_adaptive_mode`'s docstring ("still exists for backward compatibility") is also stale. Sibling shadow state: `processor.current_user_id = None  # Shared state (backwards compatibility)` duplicates `PreferenceManager.current_user_id`, kept in sync by `set_user` and read by `AdaptiveTargetGenerator`.
- **Evidence**: `self.use_continuous_space = True  # Default: enabled` / `# Set to False to use legacy preset-based processing`
- **Impact**: A tuning toggle that cannot be toggled; the adaptive-mode branch's tests cover a path no config can select.
- **Related**: STREAMLINING_PLAN #5 (kept `AdaptiveMode` for hybrid/reference only).
- **Suggested Fix**: Remove the attribute, collapse `_process_adaptive_mode` to the `ContinuousMode` arm, update `job_finalize` and the `AdaptiveMode` docstring to name only `hybrid`/`reference`. Route `TargetGenerator`'s user lookup through `processor.preference_manager.current_user_id` and delete `processor.current_user_id`.

##### TD8-08: `HAS_AURALIS` / `HAS_PROCESSING` / `HAS_STREAMLINED_CACHE` / `HAS_SIMILARITY` guard modules that cannot be missing; "demo mode" is unreachable
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/main.py:171-210,244-247`; consumers `config/startup/__init__.py:82-169`, `config/startup/workers.py:106,168`, `config/startup/fingerprint.py:112`, `config/routes.py:62-64,76,138-140,230,241,257`, `routers/health.py:27-48`, `routers/system.py:294-299` (see TD8-03)
- **Status**: NEW
- **Age**: `ef4e57d0` 2025-11-05 (flags `12c73e2f` 2025-09-16)
- **Effort**: medium
- **Description**: Four booleans model "optional engine/cache/similarity import" from the era when the web backend could run without `auralis` installed. `main.py:164` already does an unguarded `from auralis.utils.logging import ...`, so the `try: import auralis` probe at line 187 and the `if not HAS_AURALIS: ... "running in demo mode"` branch (`startup/__init__.py:103-105`) can never fire. `core.chunked_processor`, `cache` and `auralis.analysis.fingerprint` are imported unguarded by routers loaded in the same process, and the desktop build bundles them, so the other three probes are the same shape. The flags are plumbed through 6 files and 12 signatures (`deps.get('HAS_...', False)`).
- **Evidence**: `HAS_AURALIS = True` ... `try: import auralis as _auralis_probe ... except ImportError: HAS_AURALIS = False`
- **Impact**: Every startup helper carries an `if not HAS_X: return` arm that no run exercises, and the router wiring re-states each condition inline (`if HAS_STREAMLINED_CACHE else None`).
- **Related**: TD8-03 (HAS_AURALIS parameter on `create_system_router`); `/audit-backend` if a real degrade story is wanted instead.
- **Suggested Fix**: Delete the four flags, the probes, the demo-mode early return, and the `if HAS_...` arms in `routes.py`/`startup`; let an import error fail the boot loudly. Keep the *runtime* component checks `routers/health.py` already does.

##### TD8-09: Compatibility shims that exist only so tests keep their old import path
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/services/fingerprint_queue.py:274-292` (lazy `__getattr__` re-export of `FingerprintQueueManager` + `__all__`); `auralis/library/repositories/fingerprint_repository.py:44-66` (`__all__` re-exporting `is_current_fingerprint`, `PLACEHOLDER_LUFS_SENTINEL`, `_FINGERPRINT_WRITABLE_COLS`, `_validate_fingerprint_columns`); `auralis-web/backend/websocket/websocket_security.py:27-33` (`MAX_MESSAGE_SIZE = WS_MAX_MESSAGE_SIZE` and two siblings); `auralis-web/backend/core/processing_engine.py:101-104` (`job_queue` "a legacy test that assigns engine.job_queue directly still works")
- **Status**: NEW (TD2-13 covers the `# noqa: F401` re-exports in `chunked_processor.py`, `adaptive.py`, `unified_loader.py`, `scanner/config.py`, `stream_*.py`; these four are different mechanisms)
- **Age**: `fingerprint_queue.__getattr__` `3276792c` 2026-08-16 (#5039); `websocket_security` aliases from #3902
- **Effort**: small
- **Description**: (1) `FingerprintQueueManager` moved to `fingerprint_queue_manager.py` in #5039; the only importers of the old path are two tests in `tests/test_fingerprint_extraction.py:192,206`, and the shim needs a module `__getattr__` to dodge a circular import. (2) `fingerprint_repository.__all__` lists 4 helper names whose real home is `fingerprint_shared`; only `tests/` import them through the facade (production mixins import from `fingerprint_shared`). The comment spends 12 lines defending them from `ruff --fix`. (3) The `MAX_*` aliases are re-exports "under their original names since callers/tests import them"; in production they are used only inside the same file, so they are a second spelling of `WS_*` in `config/limits.py`. (4) `engine.job_queue` is the same object as `engine._worker.job_queue`; production code reads both spellings (`processing_engine.py:177,329` vs `job_worker.py`).
- **Impact**: Four more "where does this live" ambiguities; each blocks a clean move because a test patches the old name.
- **Related**: TD2-13, TD2-14.
- **Suggested Fix**: Repoint the tests to the defining modules (`fingerprint_queue_manager`, `fingerprint_shared`, `config.limits`, `engine._worker.job_queue`) and delete the shims. Use `WS_*` directly inside `websocket_security.py`.

##### TD8-10: `ChunkedAudioProcessor` carries a second copy of LevelManager's history and a second name for its duration
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/core/chunked_processor.py:194-195,205-213`; `core/chunk_render.py:178-183,220-224`; reader `core/chunk_streaming.py:127`
- **Status**: NEW
- **Age**: history mirrors `30ddbbab` 2026-08-22; `duration` property `8a8bd5a4` 2026-02-21
- **Effort**: small
- **Description**: `processor.chunk_rms_history` and `processor.chunk_gain_history` are re-copied with `list(...)` from `LevelManager.history` / `gain_adjustments` (themselves copies of `rms_history` / `gain_history`) after every chunk and every cache hit, under comments "legacy history tracking for backward compatibility" and "Keep the legacy history mirrors in sync". The single production reader is `chunk_streaming._remember_written_chunk_level` (`getattr(processor, "chunk_gain_history", None)`, then `[-1]`), which could ask `_level_manager.gain_adjustments` directly; the rest are tests asserting the mirror equals the manager. Two O(n) list copies per chunk for the life of the stream. Separately `ChunkedAudioProcessor.duration` is documented "alias for total_duration for AudioStreamController compatibility" and used by 8 call sites in `stream_seek.py`/`stream_enhanced.py` while `chunk_render`/`chunked_processor` use `total_duration` (12 sites); its sibling `chunk_duration` docstring still says "for crossfade calculations" (crossfade is retired).
- **Evidence**: `processor.chunk_rms_history = list(history) if hasattr(history, '__iter__') else []`
- **Impact**: Two sources of truth for the level history (the divergence hazard is the #3832/#4367 class of bug); two names for the duration.
- **Related**: `/audit-concurrency` if the mirror write outside `_level_manager`'s lock matters.
- **Suggested Fix**: Delete both mirror attributes and both write blocks; have `_remember_written_chunk_level` read `processor._level_manager.gain_adjustments`; update the 3 tests that assert the mirror. Replace `.duration` with `.total_duration` and delete the property.

##### TD8-11: Variant-style names whose base was deleted: `Streamlined*`, `UnifiedConfig`/`unified_loader`, `Simple*`
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/cache/manager.py:69` (`StreamlinedCacheManager`; docstring "Replaces the complex multi-tier buffer system (1,459 lines)"), `core/streamlined_{worker,tiers,processor_cache}.py`, `routers/cache_streamlined.py` (`create_streamlined_cache_router`), globals key `streamlined_cache`, flag `HAS_STREAMLINED_CACHE`, 138 hits across 27 files; `auralis/core/config/unified_config.py:30` (`UnifiedConfig`, 70 hits; the legacy `Config` it unified was deleted in #4918); `auralis/io/unified_loader.py`; `auralis/core/mastering_config.py:35` (`SimpleMasteringConfig`) and `core/simple_mastering.py:59` (`SimpleMasteringPipeline`)
- **Status**: NEW (name-only; the brief's "live families" are confirmed live, so this is the rename-only LOW case)
- **Age**: `ba3f628c` 2026-09-14 (`StreamlinedCacheManager` last touched); `UnifiedConfig` `ad7f5245` 2025-11-04
- **Effort**: medium (mechanical rename across 27 + 70 + tests; do per family)
- **Description**: Verified base-gone for each: the multi-tier buffer manager no longer exists (only the router parameter `get_multi_tier_buffer` and the comments in `routers/enhancement.py:125,468,542` still use that name, so the same object is called "multi-tier buffer", "streamlined cache" and `cache` in three layers); `Config`/`LimiterConfig` were deleted (#4918); there is no non-"Simple" mastering pipeline (`ContinuousMasteringBranch` is the only branch). No base+variant pair is live, so nothing needs merging.
- **Impact**: The No-Variants rule in CLAUDE.md is quoted against these names in every audit; a newcomer reasonably searches for the "non-streamlined" cache or the "complex" mastering pipeline that does not exist.
- **Related**: TD8-03 (`get_multi_tier_buffer` is also an ignored parameter on the player router), TD8-08 (`HAS_STREAMLINED_CACHE`). CLAUDE.md itself names `UnifiedConfig` and `SimpleMastering`, so the doc must change with any rename.
- **Suggested Fix**: Cheapest first: rename `get_multi_tier_buffer`/`_get_multi_tier_buffer` to the cache name and drop the comments mentioning the old system (touches 4 files). Then `StreamlinedCacheManager` -> `ChunkCacheManager`-style name only if the maintainers want it; otherwise record "Streamlined is the proper name" in CLAUDE.md so audits stop re-flagging.

#### Dimension 9: File / Function / Module Complexity

##### TD9-01: Closed split targets keep regrowing; `enhanced_audio_player.py` is over 300 again and `hybrid_processor.py` has passed its own waiver ceiling
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis/player/enhanced_audio_player.py` (314), `auralis-web/backend/core/chunked_processor.py` (300), `auralis/core/hybrid_processor.py` (419; waiver 415 stated at `:10-14`), `auralis-web/backend/core/processing_engine.py` (330; waiver 330 stated at `:13`)
- **Status**: Regression of #4249 (also #5454, which re-verified the player at 296 on 2026-09-16)
- **Age**: `c3c37ec7` 2026-09-14 trimmed the player to 296; regrown by `eebb2189` (#5508, 299), `8f0c89cf` (#5588, 309) and `99ee1809` (#5583, 314). `chunked_processor.py` went 295 -> 296 -> 300 via `aa1c5279` (#5489) and `a2a72d91` (#5056). `hybrid_processor.py` +4 via `2d26fd42` (#5533).
- **Effort**: small
- **Description**: This is the anecdote in `.claude/commands/audit-tech-debt.md` Dim 9, re-measured. #4245 (chunked_processor) was re-fixed at 295 on 2026-09-16 and now sits at exactly 300, which fails CLAUDE.md's "< 300". #4249 (enhanced_audio_player) was closed at 296 and is 314 after three unrelated player fixes, with no open follow-up. #4250's processing_engine waiver (330) is met exactly, with zero headroom. `hybrid_processor.py`'s docstring says "415 LOC is this file's explicit waiver ceiling" and the file is 419. The pattern is the one #5454 documented: each fix adds lines to the coordinator rather than to its sibling family, and nothing re-checks LOC after close.
- **Evidence**: `wc -l` gives 314 / 300 / 419 / 330. `git show <commit>:auralis/player/enhanced_audio_player.py | wc -l` over the last six commits: 314, 309, 299, 296, 311, 311. No script under `scripts/` checks file length (`ls scripts | grep -i "loc|size|ratchet"` finds only `check_pytest_baseline.py`).
- **Impact**: Each of these files has now been "closed" two or three times. The documented waiver numbers are unenforced, so the next audit has to re-measure by hand.
- **Siblings**: `auralis/player/playback_controller.py` 302 -> 315 and `auralis/player/gapless_playback_engine.py` 462 -> 518 (TD9-07) are the same player family regrowing.
- **Related**: #4245, #4249, #4250, #5454, #5463 (all closed). The sentence "Verified 2026-09-14 ... chunked_processor.py 358L, enhanced_audio_player.py 311L" at `.claude/commands/audit-tech-debt.md:294` is now stale again; this report supersedes it.
- **Suggested Fix**: (1) Move about 15 lines out of `enhanced_audio_player.py` into the existing `player_*_mixin.py` siblings (the pause / prebuffer-invalidation glue from #5583/#5588) and at least 1 line out of `chunked_processor.py` into a `chunk_*` sibling; no new modules. (2) Add `scripts/check_loc_ratchet.py` modelled on `check_pytest_baseline.py`: a checked-in `loc-ceilings.json` for the closed split targets (`chunked_processor.py` 299, `enhanced_audio_player.py` 299, `processing_engine.py` 330, `hybrid_processor.py` 419), wired into `backend-tests.yml`, failing when a listed file grows. (3) Correct the `hybrid_processor.py` docstring ceiling to the enforced number. Close only when `wc -l` of the player and the chunked processor is verified under 300.

##### TD9-02: Ten router modules still bundle Pydantic models, dependency plumbing, helpers and every handler (316-770 LOC); only `player` and `processing` got the #5472 treatment
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: all under `auralis-web/backend/routers/`: `enhancement.py` 770, `artwork.py` 697, `metadata.py` 670, `playlists.py` 657, `library_scan.py` 520, `similarity.py` 517, `files.py` 433, `settings.py` 430, `albums.py` 407, `artists.py` 316
- **Status**: NEW. The 2026-09-13 ranked table marked `enhancement`, `artwork`, `playlists`, `metadata` NEW but only #5472 (player/processing) was filed and closed.
- **Age**: since 2026-09-13: `enhancement.py` +4, `metadata.py` +29, `library_scan.py` +47, `settings.py` +26, `albums.py` +10.
- **Effort**: medium per file (small for the models/deps step)
- **Description**: #5472 established the recipe: `player_models.py`, `player_deps.py`, `player_playback.py`, `player_queue.py`; `processing_models.py`, `processing_deps.py`, `processing_upload.py`, `processing_jobs.py`, `processing_parameters.py`. The ten files above still hold everything. Concrete axes from the function maps:
  - `enhancement.py`: 5 request/response models (lines 51-96) -> `enhancement_models.py`; `_track_is_live_streaming`, `_preprocess_upcoming_chunks` (117) and `_maybe_prewarm_upcoming_chunks` (about 190 lines together) -> `enhancement_prewarm.py`; `get_mastering_recommendation` (117) -> `enhancement_recommendation.py`; the toggle/preset/intensity/status handlers stay.
  - `artwork.py`: the thumbnail helpers `_bucket_size` ... `_get_or_create_thumbnail` (lines 85-290, about 200 lines with no HTTP in them) -> `artwork_thumbnails.py`; `get_album_artwork` is 130 lines on its own.
  - `metadata.py`: 8 models (lines 42-167) -> `metadata_models.py`; single-track handlers (`get_editable_fields`, `get_track_metadata`, `update_track_metadata` 107) vs `batch_update_metadata` (118) -> `metadata_batch.py`.
  - `playlists.py`: 10 models (lines 48-119) -> `playlists_models.py`; CRUD vs membership (`add_tracks_to_playlist`, `add_track_to_playlist`, `reorder_playlist_track`, `remove_track_from_playlist`, `clear_playlist`, about 210 lines) -> `playlists_tracks.py`.
  - `library_scan.py`: `_watch_for_disconnect` / `_await_scan` (lines 53-160) -> `library_scan_lifecycle.py`; `scan_library` is a 290-line handler (see TD9-10).
  - `similarity.py`, `files.py`, `settings.py`, `albums.py`, `artists.py`: models first, then split by sub-resource.
- **Evidence**: `grep -c "BaseModel" routers/*.py` finds 2-9 model classes in each of these files; only `player_models.py` (21) and `processing_models.py` (10) were extracted.
- **Impact**: A handler change reviews against 600-line files whose first 300 lines are plumbing. `_current_deps` / `_make_deps_binder` is repeated in at least `artwork.py`, `metadata.py` and `playlists.py` (Dim 3 territory: do the deps step with one shared helper in `routers/dependencies.py` rather than copying it into new `*_deps.py` files).
- **Siblings**: `routers/serializers.py` 332 (shrank from 358).
- **Related**: #5472 (closed), #3838 (the `response_model=` rollout is easier once models are out of the handler files).
- **Suggested Fix**: One PR per router, models + deps first (pure code motion, no behaviour change), then the sub-resource split. Close each only when the router file is verified under 300.

##### TD9-03: Eight routers still define their endpoints as nested closures inside a 140-223 line `create_*_router()` factory; #5166 closed saying "none remain" about a different list of ten
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/backend/routers/settings.py:208` (223 lines, 9 nested defs, 5 endpoints), `fingerprint_queue.py:83` (197), `tracks.py:58` (174, 6 endpoints), `artists.py:144` (173), `system.py:294` (167; its `websocket_endpoint` alone is 147), `library.py:88` (159), `fingerprint_status.py:59` (147), `cache_streamlined.py:63` (140). `similarity_graph.py:45` (86) is the smallest instance.
- **Status**: NEW (a scope gap: the 2026-09-13 report's TD9-03 listed these, but #5166 was closed on 2026-09-14 after converting only `library_scan.py`)
- **Age**: `0b0e6d0e` (#5166 close) 2026-09-14.
- **Effort**: large overall (one router per PR; small each)
- **Description**: #5166's ten routers were `processing_api`, `player`, `enhancement`, `playlists`, `artwork`, `metadata`, `library_scan`, `similarity`, `albums`, `files`; its closing comment states "none remain". The eight above were never on that list and still nest their handlers.
- **Evidence**: AST walk over `routers/*.py` for `create_*` functions with nested `FunctionDef`s gives the line counts above and 1-9 nested defs per factory, with every endpoint-decorated handler inside the closure. `grep -n "def create_.*router" routers/*.py` finds 20 factories in total.
- **Impact**: No handler can be imported or unit-tested without building the closure, and the #3838 `response_model=` rollout has to edit decorators inside functions of 150-220 lines.
- **Siblings**: the already converted routers; `routers/library_scan.py::create_library_scan_router` (22 lines of `add_api_route` registration) is the reference.
- **Related**: #5166, #4670 (closed), TD9-02.
- **Suggested Fix**: Apply the #5166/#4670 recipe: module-level handlers taking `Depends()`, the factory reduced to an `add_api_route` assembler. Do `system.py` and `settings.py` first (largest). Close each when the factory is under 30 LOC and the registered `(path, methods)` set is unchanged (pin it with a test like `tests/backend/test_library_scan_handler_seam_5166.py`).
- **Publication note — TD10-08 (Dim 10)**: this is the same finding as TD9-03 of `AUDIT_TECH_DEBT_2026-09-13.md`. It was the only finding of that report never published: 40 of 42 were published and 39 of those are closed. Publish it this time, or close it with an explicit "closure factories accepted" decision.

##### TD9-04: Backend core caches and streaming modules grow as single classes (`processor_factory`, `mastering_target_service`, `chunk_cache_manager`, `chunk_streaming`, `streamlined_worker`)
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/backend/core/processor_factory.py` 553 (`ProcessorFactory` 413 lines, `get_or_create` 127), `mastering_target_service.py` 542 (`MasteringTargetService` 445), `chunk_cache_manager.py` 501, `chunk_streaming.py` 434, `streamlined_worker.py` 326 (new crossing; `_process_chunk` 93 -> 132)
- **Status**: NEW (the 2026-09-13 table listed `processor_factory` and `mastering_target_service` as NEW; no issue exists)
- **Age**: since 2026-09-13: `mastering_target_service` +59 (#5531, #5556, #5554, #5552, #5489, #5085), `chunk_streaming` +79 (`b2ffc8d4` #4669, +108), `streamlined_worker` +46 (#5059, #5349, #5490), `processor_factory` +38, `chunk_cache_manager` +16.
- **Effort**: medium each
- **Description**: Split axes by responsibility:
  - `processor_factory.py`: `ProcessorCacheKey` + `_get_cache_key` + `_get_config_hash` (cache identity, about 80 lines) and the module-level singleton accessors (`get_processor_factory`, `all_processor_factories`, `create_processor_factory`, `PROACTIVE_BUFFER_CONSUMER`, lines 497-553) -> `processor_registry.py`; the class keeps create/release/invalidate.
  - `mastering_target_service.py`: fingerprint acquisition (`load_fingerprint_from_database` 70, `load_fingerprint_from_file` 47, `extract_fingerprint_from_audio` 78, `load_fingerprint` 74, about 270 lines) vs target generation (`generate_targets_from_fingerprint` 78, `_calculate_eq_adjustment`) and the cache -> `fingerprint_loading.py` plus the service.
  - `chunk_cache_manager.py`: the two key builders (`get_chunk_cache_key` 44, `get_fingerprint_cache_key` 21) and the fingerprint cache (`get_cached_fingerprint`, `cache_fingerprint`) vs chunk-file get/put/prune/clear -> `chunk_fingerprint_cache.py`.
  - `streamlined_worker.py` (326): the LRU/lock bookkeeping vs tier-priority scheduling (the axis of the closed #5037); the #5059/#5349/#5490 code made `_process_chunk` 132 lines.
- **Evidence**: `ast` class/method maps; `git log c870728a..HEAD -- <file>`.
- **Impact**: These are the files a streaming bug fix lands in, and every fix in the last five weeks added 10-60 lines to a class that already held 400+.
- **Siblings**: `chunk_boundaries.py` 435 is constants and pure functions and cohesive (the "sole chunk-geometry authority"); leave it. `audio_stream_controller.py` 343 shrank from 396 and is not a priority.
- **Related**: #5037 (closed), TD9-10 (stream handlers).
- **Suggested Fix**: Take `processor_factory` and `mastering_target_service` first (class-level extraction with names re-exported from the original module, so no caller changes). Close each only when verified under 300.

##### TD9-05: `auralis-web/backend/main.py` is 454 lines and keeps growing: logging bootstrap, path bootstrap, DI dict assembly and catch-all routing in one script
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/backend/main.py:54-176` (dev-mode flag, `resolve_log_level`, `logging.basicConfig`, the `AURALIS_LOG_LEVEL` warning, `sys.path` setup for PyInstaller / Electron / dev), `:302-408` (`FRONTEND_MISSING_HTML`, `_unregistered_websocket`, `_methods_allowed_for`, `_unmatched_api_path`)
- **Status**: NEW
- **Age**: 380 -> 454 since 2026-09-13: `9101e300` (#5065, +62), `64d59ea2` (#5393, +14).
- **Effort**: small
- **Description**: The file is the composition root, but about 120 lines are logging and import-path bootstrap and about 110 are catch-all/404 routing, neither of which depends on the DI wiring between them. `config/` already holds `app.py`, `routes.py`, `globals.py`, `origins.py`, `limits.py`.
- **Evidence**: `grep -nE "^(def |async def |[A-Za-z_]+ = |@app)" main.py` shows the three blocks.
- **Impact**: Each logging or fallback-route fix lands in the entry script, which has import-order constraints (`sys.path` must be set before `from config.app import ...`) that make edits riskier than their size suggests.
- **Siblings**: none (other entry scripts are small).
- **Suggested Fix**: Move the logging and `sys.path` block into `config/bootstrap.py` (importable because `main.py`'s directory is already on `sys.path` when it runs as a script) and the catch-all routes into `config/fallback_routes.py` with a `register_fallback_routes(app)` call at the same point. Keep the order of side effects unchanged; verify with a `python main.py --dev` boot. Close when `wc -l main.py` is under 300.

##### TD9-06: `ffmpeg_loader.py` (581, +56) mixes the ffprobe layer, subprocess supervision and the load orchestration; `load_with_ffmpeg` is 236 lines
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis/io/loaders/ffmpeg_loader.py`: probe helpers `ffprobe_command` (78), `check_ffprobe` (263), `_probe_audio` (281); process helpers `redact_subprocess_output` (109), `_terminate_process` (152), `_run_ffmpeg_cancellable` (169); `check_ffmpeg` (223), `_parse_ffmpeg_version` (136); `load_with_ffmpeg` (346-581)
- **Status**: NEW (the 2026-09-13 table lists it as NEW; no issue)
- **Age**: grew 525 -> 581 via `c7491222` (#5326), `e5f355cf` (#5317), `f16836a1` (#5555), `0805cd31` (#5590).
- **Effort**: medium
- **Description**: Three responsibilities in one module. `load_with_ffmpeg` is a straight-line function with five phases visible from its comments: tool availability and path validation (lines 371-391), probe and fail-fast (392-443), temp-file creation (444-456), the conversion subprocess with error mapping, and the read-back into the result.
- **Evidence**: the function map above; the file's own comments reference #4119, #3697, #3671, #2495 and #2908, so each phase has a separate bug-fix history.
- **Impact**: Four fixes in five weeks each touched this one function.
- **Siblings**: `auralis/io/unified_loader.py` 341 (shrank from 380).
- **Suggested Fix**: `ffmpeg_probe.py` (probe command, `check_*`, `_probe_audio`, version parse) and `ffmpeg_process.py` (redaction, terminate, cancellable run); then cut `load_with_ffmpeg` into `_validate_input`, `_probe_or_fail`, `_convert_to_temp_wav` and `_read_converted` (each under about 60 lines). Close when the loader file is verified under 300.

##### TD9-07: Player: `GaplessPlaybackEngine` (518), `QueueManager` (495), `QueueController` (448) and `IntegrationManager` (444) are one-class files that grew with every queue fix
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis/player/gapless_playback_engine.py` (`GaplessPlaybackEngine` 495 lines, `advance_with_prebuffer` 172, `_prebuffer_worker` 93), `auralis/player/components/queue_manager.py` (26 methods), `auralis/player/queue_controller.py` (38 methods, `load_playlist` 55), `auralis/player/integration_manager.py` (`__init__` 53, `get_playback_info` 54, `load_track_from_library` 52)
- **Status**: NEW (`gapless_playback_engine.py` was in the 2026-09-13 table; no issue)
- **Age**: since 2026-09-13: gapless +56 (`99ee1809` #5583 alone +126/-69), `queue_controller` +77 (`eebb2189` #5508 +65, plus #5582, #5587, #5360, #5355, #5315), `queue_manager` +47 (`5eb10eee` #5582 and others).
- **Effort**: medium
- **Description**: Split axes. (a) `GaplessPlaybackEngine`: the prebuffer lifecycle (`start_prebuffering`, `_prebuffer_worker`, `invalidate_prebuffer`, `_entries_match`, `_prebuffer_matches`, `on_queue_changed`, the callback registry, about 230 lines) -> `gapless_prebuffer.py`, leaving `advance_with_prebuffer` and `cleanup`; `advance_with_prebuffer` is itself a 172-line method that should be cut into select-next / swap-buffers / schedule-prebuffer steps. (b) `QueueController` wraps `QueueManager` (`self.queue`) and mirrors most of its surface: `add_track`, `insert_track`, `next_track`, `advance_if_next_matches`, `rollback_index`, `snapshot_index`, `shuffle`, `unshuffle`, `reorder_tracks`, `move_track` and `remove_if_index_matches_current` exist on both, and several 2026-09/10 fixes (#5582, #5587) edited both files for one behaviour. Where the controller method is a pure delegate, expose `controller.queue` (or `__getattr__`-free explicit properties) instead of a second signature; keep only what adds behaviour (`set_change_listener` / `_notify_changed`, `_get_repos`, `load_playlist`, `add_track_from_library`, `search_and_add`, `set_queue`). (c) `IntegrationManager`: reporting (`get_playback_info`, `record_track_completion`, `_get_position_seconds`) vs loading (`load_track_from_library`, `_auto_select_reference`).
- **Evidence**: the class method maps above (`QueueController` 38 methods, `QueueManager` 26).
- **Impact**: The #5508 / #5582 / #5583 / #5587 series each touched two or three of these files for a single behaviour.
- **Siblings**: `auralis/player/playback_controller.py` 302 -> 315 (TD9-01).
- **Related**: `/audit-concurrency` for lock ordering when thinning the controller (the controller notifies its listener after `QueueManager._lock` is released, see its docstring).
- **Suggested Fix**: First thin `QueueController` to its behaviour-adding methods, then move the prebuffer lifecycle out of the gapless engine. Close each file only when verified under 300.

##### TD9-08: Library layer: `database.py` (505), `scanner.py` (478), `library_auto_scanner.py` (479), `migration_manager.py` (332, new crossing)
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis/library/database.py` (`LibraryDatabase.__init__` 168 lines; the scan-slot / path-reservation / exclusive-access methods, about 95 lines; `shutdown` 57), `auralis/library/scanner/scanner.py` (`scan_directories` 292 lines), `auralis-web/backend/services/library_auto_scanner.py` (`_do_scan` 192), `auralis/library/migration_manager.py` (287 -> 332 via `21c66b07` #5316 and `5ee4644a` #5174), also `sidecar_manager.py` 405, `artwork.py` 360, `metadata_editor/metadata_editor.py` 359, `repositories/album_repository.py` 366, `artist_repository.py` 318, `genre_repository.py` 311 (crossed via `9c1b040b` #5111)
- **Status**: NEW (`database.py`, `scanner.py` and `library_auto_scanner.py` were in the 2026-09-13 table; #5481 mentions the two functions)
- **Age**: `migration_manager.py` crossed 300 on 2026-09-15; `genre_repository.py` on 2026-09-15; `scanner.py` 492 -> 478.
- **Effort**: medium
- **Description**: Axes: `database.py` -> a `ScanCoordinator` class (`try_acquire_scan_slot`, `release_scan_slot`, `try_reserve_scan_paths`, `release_scan_paths`, `try_begin_exclusive_access`, `end_exclusive_access`, `is_scanning`; self-contained lock state) plus a `_build_repositories()` helper to cut `__init__` from 168 lines; `scanner.py` -> cut `scan_directories` into slot acquisition (lines 152-195), path pre-count with a bounded cache (211-260), the `_process_batch` / `_feed` closures and the cache-overflow fallback; `library_auto_scanner.py` -> `_DebounceHandler`, `_sync_watchdog` and `_stop_watchdog` (watchdog glue) vs the scan loop (`_run`, `_run_cycle`, `_do_scan`); `migration_manager.py` -> the backup/restore code from #5316 into `migration_backup.py`, beside the existing `migration_lock.py` and `migration_steps.py`.
- **Evidence**: method maps above; `scan_directories` is 292 lines at nesting 5, `_do_scan` 192 at nesting 4.
- **Impact**: Concurrency fixes (scan slots, exclusive access) live in the same 168-line constructor as repository wiring.
- **Siblings**: the repositories grow by finder method and are the lowest priority.
- **Related**: `/audit-concurrency` for the scan-slot lock state; #5481.
- **Suggested Fix**: `ScanCoordinator` first (self-contained; `LibraryDatabase` keeps thin delegating methods). Close each file when verified under 300.

##### TD9-09: Analysis and DSP files in the 380-510 band with a clear second responsibility
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis/analysis/mastering_profile.py` 506 (`DetectionRules` + `MasteringProfile` + `MasteringProfileDatabase`), `auralis/analysis/dynamic_range.py` 459 (`DynamicRangeAnalyzer`, 439 lines, 14 methods), `auralis/analysis/adaptive_mastering_engine.py` 433 (`MasteringRecommendation` 94 + `AdaptiveMasteringEngine` 256), `auralis/core/analysis/content_analyzer.py` 416 (`analyze_content` 95, `analyze_input_level` 94, `_classify_genre` 61), `auralis/dsp/eq/psychoacoustic_eq.py` 409 (`PsychoacousticEQ` 348), `auralis/core/simple_mastering.py` 393 (`_master_file_impl` 130, +21), `auralis/analysis/spectrum_operations.py` 397, `auralis/analysis/fingerprint/normalizer.py` 398, `auralis/analysis/loudness_meter.py` 385, `auralis/analysis/fingerprint/windowed_compute.py` 385
- **Status**: NEW (listed in the 2026-09-13 table, never filed)
- **Age**: stable apart from `simple_mastering.py` +21 and `phase_correlation.py` 336 -> 343.
- **Effort**: small to medium each
- **Description**: Axes: `mastering_profile.py` by class (rules/targets/profile data vs the database and `describe_profile`) -> `mastering_profile_db.py`; `adaptive_mastering_engine.py` -> move `MasteringRecommendation` (94-line dataclass with a 31-line `summary`) to `mastering_recommendation.py`; `dynamic_range.py` by metric family (`_estimate_compression_ratio`, `_estimate_attack_time`, `_analyze_envelope`, `_assess_loudness_war`, about 160 lines) -> `dynamic_range_dynamics.py`; `content_analyzer.py` -> genre classification (`_classify_genre*`, `_categorize_energy_level`) into its own module; `psychoacoustic_eq.py` -> `analyze_spectrum` (63) and band-energy helpers vs gain calculation/apply. `windowed_compute.py` is mainly one 298-line function (TD9-10).
- **Evidence**: `ast` class/method maps above.
- **Impact**: Moderate. These files are stable, so change cost is low today; the point is to split them when next touched.
- **Siblings**: oversized files whose content is dead are in "Checked and clean".
- **Suggested Fix**: Opportunistic, one file per PR, only when the file is next touched for a behaviour change. Close each when verified under 300.

##### TD9-11: Control-flow nesting above 4 in 32 functions; `proactive_buffer.buffer_presets_for_track` has a dead loop level
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: top of the list: `auralis/core/mastering_chunk_loop.py:126` `_render_to_sink` (7), `auralis/analysis/fingerprint/windowed_compute.py:88` (6), `auralis-web/backend/core/proactive_buffer.py:27` `buffer_presets_for_track` (6, 132 lines), `auralis/library/utils/artist_normalizer.py:101` `parse_featured_artists` (6, 80 lines), `auralis/library/scanner/file_discovery.py:110` `_walk_directory` (6, 73 lines), `auralis/library/migration_steps.py:154` `apply_migration_sql` (6, 63 lines); at 5: `scan_directories`, `scan_library`, the three `pump_*_chunks`, `_normalize_inner`, `QueueSetMixin._set_queue_impl` (124), `TrackRepositoryLifecycleMixin.add` (117), `routers/enhancement.py:205` `_preprocess_upcoming_chunks` (117)
- **Status**: NEW
- **Age**: `AVAILABLE_PRESETS = ["adaptive"]` dates from the preset narrowing (2026-09-13, memory note and #4861 follow-up).
- **Effort**: small each
- **Description**: Concrete refactors:
  - `proactive_buffer.py:71` `for preset in AVAILABLE_PRESETS:` iterates a one-element list (`AVAILABLE_PRESETS = ["adaptive"]`, `:23`), and the module docstring still says "for all presets ... instant preset switching". Hoist the loop body into `_buffer_one_preset(preset, ...)` and drop the loop and its second `_cancelled()` check; nesting goes 6 -> 4 and the per-chunk `try/except` (lines 82-105) becomes a small helper. There is one caller, `core/stream_enhanced.py:190`.
  - `artist_normalizer.parse_featured_artists`: replace the `FEATURING_PATTERNS` loop plus the nested `for part in parts / for sub in sub_artists` with a `_split_featuring(artist_string)` that returns a flat list, followed by the `&`/`and` fallback as a second early-return function.
  - `file_discovery._walk_directory`: extract `_classify_entry(entry, visited_inodes)` returning skip / descend / yield, so the `scandir` loop has one dispatch and no nested `try` for the inode check.
  - `_render_to_sink`: see TD9-10.
- **Evidence**: `ast` nesting scan; `proactive_buffer.py:23` and `:71`.
- **Impact**: Branch coverage is hard in deep nests; the three pump functions and `_render_to_sink` sit on the audio streaming path.
- **Siblings**: the `proactive_buffer.py` docstring and comment still describe multi-preset switching (a Dim 7 doc note, not filed separately).
- **Suggested Fix**: As above, in the order listed; each is under 2 hours.

##### TD9-12: Frontend: `BufferScheduler` (+103), `useLibraryPagination`, `PlaybackSessionContext`, `useProgressBarInteraction` and `CozyLibraryView` grew or crossed 300; `useEnhancementControl` is a 304-line hook
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/frontend/src/services/audio/BufferScheduler.ts` (381 -> 484), `hooks/library/useLibraryPagination.ts` (206 -> 310), `contexts/PlaybackSessionContext.tsx` (273 -> 346; `PlaybackSessionProvider` is a 304-line function), `components/player/useProgressBarInteraction.ts` (263 -> 320; hook is 279 lines), `components/library/CozyLibraryView.tsx` (294 -> 302), `hooks/enhancement/useEnhancementControl.ts` (517 -> 521; `useEnhancementControl` is 304 lines at `:158`), `hooks/player/useQueueMutations.ts` (361 -> 385; hook is 307 lines), `hooks/player/usePlayerStateSync.ts` 344, `services/audio/PCMStreamBuffer.ts` (293 -> 324), `hooks/websocket/useWebSocketConnection.ts` 372 (hook is 307 lines), `hooks/websocket/websocketConnectionCore.ts` 342
- **Status**: NEW. #5478 split `useLibraryQuery` (298) and `useAudioStreamingCore` (294) and is closed; the sibling `useLibraryPagination` was extended by `4570c658` (#5626, +88) to 310 in the same week.
- **Age**: all growth is from bug-fix commits 2026-10-17 to 2026-10-20: `a5ee430b` (#5657, +93 in BufferScheduler), `a97a6953` (#5625, +101/-44), `a48dac29` (#5605/#5613, +74), `c45e57d4` (#5624).
- **Effort**: small to medium each
- **Description**: Axes:
  - `BufferScheduler.ts`: one class; separate the AudioWorklet path (lookahead cap, underrun posting, tail play-out from #5657/#5665) from the `AudioBufferSourceNode` scheduling path.
  - `useLibraryPagination.ts`: move the in-place refresh logic (`refreshTracks`, #5626) and the request-id / abort bookkeeping into `libraryPageFetch.ts` (pure fetch + guard), leaving state in the hook. 7 `useState`, 1 `useEffect` and 5 refs in one hook read as three hooks.
  - `PlaybackSessionContext.tsx`: the provider holds the repeat-mode and retry logic from #5605/#5613; extract `usePlaybackRepeat()` and `useStartTrackRetry()` and keep the provider as wiring.
  - `useProgressBarInteraction.ts`: separate the drag state machine (pointer events, commit-on-release from #5625) from the pure position/percent maths.
  - `useEnhancementControl.ts`: the file already holds three small hooks (`usePresetControl`, `useIntensityControl`, `useEnhancementToggle`, lines 471-521); move `_fetchEnhancementStatusOnce` and the status-sync effects into `useEnhancementStatusSync.ts`.
  - `CozyLibraryView.tsx` (302): move the last handler cluster into its existing `components/CozyLibraryView/` directory (it already holds `useLibraryKeyboardShortcuts.ts` and `LibrarySearchControls.tsx`).
- **Evidence**: sizes from `wc -l` today vs `git show c870728a:auralis-web/frontend/<path> | wc -l`; function sizes from the brace-matching scan.
- **Impact**: These are the files #5600-#5665 touched; each fix needed a re-read of 300+ lines of state-machine code.
- **Siblings**: `queue_recommender.ts` 469, `queue_statistics.ts` 394, `queue_shuffler.ts` 383 are not split candidates (they are in TD2-05 for deletion).
- **Related**: #5478 (closed), `/audit-frontend`.
- **Suggested Fix**: Take `useLibraryPagination` and `CozyLibraryView` first (smallest; about 10-110 lines to move). Close each only when `wc -l` is verified under 300.

##### TD9-13: Frontend files that never got split: `errorTrackingMiddleware.ts`, `colorExtraction.ts`, `albumCharacterDescriptors.ts`, `themeConfig.ts`, `globalStyles.ts`, `apiRequest.ts`, `errorHandling.ts`, `useRestAPI.ts`
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts` 412, `utils/colorExtraction.ts` 409, `utils/albumCharacterDescriptors.ts` 379, `theme/themeConfig.ts` 399 (`createAuralisTheme` is a 374-line function), `styles/globalStyles.ts` 348, `utils/apiRequest.ts` 326 (+14), `utils/errorHandling.ts` 332, `hooks/api/useRestAPI.ts` 308, `contexts/WebSocketContext.tsx` 329, `store/slices/queueSlice.ts` 304
- **Status**: NEW (the 2026-09-13 table listed `errorTrackingMiddleware` and `themeConfig` as NEW; the rest are new in this list)
- **Age**: unchanged since 2026-09-13 except `apiRequest.ts` +14. `themeConfig.ts` already shrank 515 -> 399, `errorHandling.ts` 443 -> 332, `useRestAPI.ts` 402 -> 308.
- **Effort**: small each
- **Description**: Axes: `errorTrackingMiddleware.ts` -> `errorCategorization.ts` (`categorizeError` 136-194, the two action-name sets, `isAllowedErrorAction`) vs the middleware factory; `colorExtraction.ts` -> `kMeans.ts` + `colorSpace.ts` (rgbToHex / rgbToHsl / colorDistance / kMeansClustering, lines 73-235) vs `extractArtworkColors` and the gradient helpers; `albumCharacterDescriptors.ts` -> fingerprint analysis (`analyzeEnergy` ... `analyzeEnergyTags`, lines 40-206) vs description generation (207-333); `themeConfig.ts` -> split `createAuralisTheme` by MUI key group (`palette`, `typography`, `components`) into a `theme/` directory; `globalStyles.ts` by concern.
- **Evidence**: file and function maps above.
- **Impact**: Low (stable files); the cost is the project rule only.
- **Siblings**: CLAUDE.md's "Components < 300 lines" is met by files: the only shipped `.tsx` files over 300 are `PlaybackSessionContext.tsx` 346, `WebSocketContext.tsx` 329 and `CozyLibraryView.tsx` 302. Component bodies over 150 lines: `StarfieldBackground` 241, `QueuePanelExpanded` 239, `ConnectionDetailsPanel` 236 (reachable only from the orphaned `ConnectionStatusIndicator`, #5628), `AlbumCharacterPane` 229, `ComfortableApp` 228, `TrackListViewContent` 216, `QueueSearchPanel` 215 (orphaned, #5628), `AlbumDetailView` 205, `Player` 190, `CacheStatsDashboard` 181.
- **Related**: #4456 and #4916 (closed component splits), #5628 (orphaned components: delete, do not split).
- **Suggested Fix**: Only when next touched. Close each when verified under 300. Do not spend effort on `QueueSearchPanel`, `ConnectionDetailsPanel` or the `queue_*.ts` utilities.

#### Dimension 10: Audit-Finding Rot

##### TD10-01: `/verify-release`, `/fix-issue` and `/gen-test` run commands CLAUDE.md says hang, use npm, and judge by raw pass/fail
- **Severity**: LOW (the dimension agent proposed MEDIUM; demoted at merge because no promotion row strictly fires: no audit has been shown to have been misled. Ranked as a top Quick Win instead)
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/verify-release.md:44,52,60,93,106,122`; `.claude/commands/fix-issue.md:99,105`; `.claude/commands/gen-test.md:104`
- **Status**: NEW
- **Age**: `verify-release.md` added `633eb671` 2026-03-01 and never re-synced for these lines; `fix-issue.md:99/105` last touched `eee8384a` 2026-08-07 (a different paragraph); `gen-test.md:104` from `9234b345` 2026-05-20
- **Effort**: small
- **Description**: CLAUDE.md is explicit: pnpm is the only supported JS package manager (#4357); the whole backend suite takes tens of minutes and `tests/backend/test_system_api.py` plus `tests/concurrency/test_thread_safety.py` hang when run whole, so they must be `--ignore`d "exactly like CI does"; `-v` dumps every test name into context; both suites are ratchets against `pytest-baseline.json` / `test-baseline.json` (127 and 101 known failures today). Three skills still carry the pre-ratchet instructions.
- **Evidence**:
  - `verify-release.md:52`: `python -m pytest -m "not slow" -v 2>&1 | tail -40`, verdict "FAIL on any test failure". No `--ignore`, `-v`, and with 127 baselined failures it can never PASS even if it finished. It never mentions `scripts/check_pytest_baseline.py`.
  - `verify-release.md:93` (Gate 9): `python -m pytest -m "regression" -v` is also repo-wide.
  - `verify-release.md:44,60,106,122`, `fix-issue.md:105`: `npm run type-check`, `npm run test:memory`, `npm outdated`, `npm run build`; `gen-test.md:104`: `npx vitest run`. `auralis-web/frontend/package.json` declares `"packageManager": "pnpm@10.20.0"` and only `pnpm-lock.yaml` exists.
  - `fix-issue.md:99`: "Final gate — full suite, ONCE before commit: `python -m pytest -q -m "not slow"`" (hangs on the same two files; the user-memory rule is to never run the broad suite).
  - Gate 3/5 verdicts are "FAIL on any type error / test failure" while `frontend-test.yml` and `_audit-common.md:94` define the frontend gate as "no failure outside the baseline".
- **Impact**: The pre-release checklist cannot produce a READY verdict (Gate 4 hangs, then fails on known baseline), so it either gets skipped or its FAILs get discounted by hand, which defeats the gate. `npm` against a pnpm lockfile also creates a stray `package-lock.json` and a different dependency tree.
- **Siblings**: `audit-regression.md:83` already has the correct wording ("Two files hang when run whole ... gate on targeted tests") and `_audit-common.md:90-104` has the baseline commands: copy those.
- **Related**: #4357 (pnpm only), #4562/#4640 (baselines), #5091 (strict-stale). `/audit-sync` Phase 3 should have caught this but has never run (TD10-07).
- **Suggested Fix**: In `verify-release.md` replace Gates 4/5/9 with `python scripts/check_pytest_baseline.py` / `pnpm run test:ci && pnpm run test:baseline` (the CI commands) and change the verdict to "FAIL on any failure not in the baseline"; swap `npm`/`npx` for `pnpm` in the three files; in `fix-issue.md:99` change the final gate to the CI invocation with the two `--ignore`s.

##### TD10-02: Ten dedup commands list only OPEN issues, capped at 200, so the "CLOSED match -> check for regression" branch can never fire
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/_audit-common.md:180`; `audit-publish.md:42`; `audit-engine.md:164`; `audit-backend.md:197`; `audit-frontend.md:156`; `audit-integration.md:170`; `audit-security.md:139`; `audit-concurrency.md:108`; `audit-tech-debt.md:62` (the same file's line 63 does it right); `sync-contracts.md:145`, `verify-dsp.md:139` ("check `gh issue list`")
- **Status**: NEW
- **Age**: `_audit-common.md` line from `6c8d1db5` 2026-02-18; `audit-publish.md` from `b869bca7` 2026-03-19
- **Effort**: trivial
- **Description**: `gh issue list` defaults to `--state open`, so `--limit 200 --json number,title,state,labels` yields a file whose `state` is always `OPEN`. The protocol then says (`_audit-common.md:187-188`, `audit-publish.md:44-45`) to handle a **CLOSED** match by verifying the fix and reporting "Regression of #NNN" - impossible, because closed issues are not in the baseline; a regressed finding is filed as NEW, or as a DUPLICATE of nothing. The 200 cap is also close to the ceiling: 177 issues are open today. `audit-tech-debt.md:63` already uses `--state all`, but only for the `tech-debt` label.
- **Evidence**: `gh issue list --limit 200 --json number,state` -> every row `OPEN`; `gh issue list --state all --limit 3000` returns the full 3000-row cap (issue numbers reach 5756), so any "scan recent closed" step needs a bigger limit than 200 too.
- **Impact**: Each audit's dedup is half of what its prose promises, so closed-then-regressed defects and closed-but-unfixed ones (11 were found in the 2026-07-25 comprehensive audit) re-surface as NEW findings and the "Regression of" label is never applied by the dedup step.
- **Siblings**: all 11 sites above; `audit-search.md:74` and `verify-release.md:74-75` use `--state open` deliberately and are fine.
- **Related**: #4974 / #5091 are unrelated; the memory note "11 closed issues were never actually fixed" is the cost of this.
- **Suggested Fix**: Define the command once in `_audit-common.md` (`gh issue list --state all --limit 3000 --json number,title,state > ...`) and have the 8 audit skills and `audit-publish.md` reference it instead of repeating a literal; the brief for this run already does this with a full issue dump.

##### TD10-03: `library-specialist.md` describes the schema as v18 / newest migration `v017_to_v018` in three places and tells the agent to check `up` and `down` of migrations that have no `down`
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/agents/library-specialist.md:16,50,71,87`; sibling `.claude/commands/_audit-common.md:19` (already in dim_7 TD7-03)
- **Status**: NEW (the `_audit-common.md` copy is TD7-03; these agent-file copies are not in dim_7 and the gate cannot catch them because `migration_v017_to_v018.sql` still exists on disk)
- **Age**: line 71 from `9234b345` 2026-05-20; "Current schema: v18" from `15dcf4c2` 2026-09-13; schema is v22 since #5574 (`auralis/__version__.py:11`, `migration_v021_to_v022.sql`)
- **Effort**: trivial
- **Description**: Four claims about migrations. (1) `:16` "latest script: `migration_v017_to_v018.sql`"; (2) `:50` "Current schema: v18 (... `migration_v017_to_v018.sql` is the newest)"; (3) `:87` "schema history (currently v18)"; all three are 4 versions old. (4) `:71`, "Migration walk: ... Check that each migration has both `up` and `down`". Migrations are forward-only: `ls auralis/library/migrations/` has no `down` script, no file contains a downgrade section, and neither `migration_manager.py` nor `migration_steps.py` has a downgrade path.
- **Evidence**: `ls auralis/library/migrations | tail -3` -> `migration_v020_to_v021.sql`, `migration_v021_to_v022.sql`; `grep -il "down\|rollback" auralis/library/migrations/*.sql` -> none.
- **Impact**: (4) is a checklist item that is false for every file by construction, so each `/audit-engine` Dim 7 or library audit run is invited to report ~22 "missing down migration" findings (or to waste time arguing them away). (1-3) point the agent at a v18-era ruleset for a v22 schema.
- **Siblings**: `_audit-common.md:19` and `docs/architecture/module-map.md:51`, `overview.md:119` (TD7-03). `audit-regression.md:83` also says "broken v15->v16 migration cascades" for the full `tests/backend` suite (cannot be verified without running it; check the claim next sync).
- **Related**: #5316 (backup restore on a failed step is the actual rollback story), TD7-03.
- **Suggested Fix**: Replace the three version claims with "the highest-numbered file in `auralis/library/migrations/`; schema version is `__db_schema_version__`", and rewrite the `up`/`down` item as "each migration is forward-only SQL; failure is handled by the backup restore in `migration_backup.py`".

##### TD10-04: `audit-regression` seed registry has rows whose "File(s) to Check" no longer contain the fix, so a faithful run reports a false regression
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/audit-regression.md:42-66` (rows: "Parallel processing for sub-bass control", "Audio loading thread safety", "Copy-before-modify pattern", "Thread-safe player state (RLock)")
- **Status**: NEW
- **Age**: rows from `3e44f533` 2026-02-12 and `6c8d1db5` 2026-02-18; the code moved on 2026-03..2026-10 (`#13 Stage 3/4` Rust fingerprint engine, the stage and mixin splits)
- **Effort**: small
- **Description**: The registry is the one list of "must ALWAYS be verified" invariants, and `audit-publish` turns a FAIL into a HIGH issue ("FAILs become HIGH severity"). Four rows point at a file where the fix is no longer present, so the status is FAIL/unverifiable although nothing regressed:
  - **Audio loading thread safety (`53cef6b4`)** -> `auralis/analysis/fingerprint/`, "doesn't block on KeyboardInterrupt". That commit's fix (a `ThreadPoolExecutor` without `with`, `shutdown(wait=False, cancel_futures=True)` on `KeyboardInterrupt`) lived in `audio_fingerprint_analyzer.py`. The file is now 162 lines, with no `ThreadPoolExecutor`, no `KeyboardInterrupt` anywhere under `auralis/analysis/fingerprint/`; the subsystem moved to the in-process Rust engine (`871356f7`, `29650ea0`). The invariant is obsolete, not regressed.
  - **Parallel processing for sub-bass control (`8bc5b217`)** -> `auralis/core/simple_mastering.py`. `simple_mastering.py:364` is now a one-line delegate to `core/stages/sub_bass_control.py`; the file contains no sub-bass filtering at all.
  - **Copy-before-modify** -> `simple_mastering.py` (no `.copy()` in it; the copies are in `core/stages/*.py`).
  - **Thread-safe player state (RLock)** -> `enhanced_audio_player.py`: it holds only `_fingerprint_lock = threading.Lock()` and borrows `file_manager._audio_lock`; the RLocks are in `playback_controller.py:47`, `audio_file_manager.py:34`, `integration_manager.py:101`, `gapless_playback_engine.py:60`.
  Also: there is no `AUDIT_REGRESSION_*.md` in `docs/audits/` since 2026-03-02 (`71859e1e`), so these rows have not been exercised in 7 months.
- **Impact**: First run of `/audit-regression` (or the `pre-release` / `post-sprint` presets) yields 2-4 spurious FAILs that `/audit-publish` would file as HIGH, which is exactly the false-positive class the Retired Architecture table exists to prevent.
- **Siblings**: the other 17 rows were spot-checked and still hold (chunk constants, WOLA, cursor pagination, engine disposal, migration lock, path security, presets, optimization-live gate, LibraryManager).
- **Related**: TD10-07 (no verified sync); `_audit-common.md` Retired Architecture (add "fingerprint thread-pool/KeyboardInterrupt fix (obsolete since Rust engine)").
- **Suggested Fix**: Repoint the sub-bass, copy-before-modify and player-lock rows to `core/stages/sub_bass_control.py`, `core/stages/`, and `player/playback_controller.py` + `audio_file_manager.py`; drop the KeyboardInterrupt row (or restate it for `fingerprint_worker.py`, which is the surviving threaded path).

##### TD10-05: `/sync-contracts` and `/trace-flow` still point at WebSocket layers and a "Manager"/"crossfade"/"queue persistence" that were retired
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/sync-contracts.md:34-42`; `.claude/commands/trace-flow.md:21,22,59,77-78,114`
- **Status**: NEW
- **Age**: both files from `633eb671` 2026-03-01 (untouched for these lines)
- **Effort**: small
- **Description**: `sync-contracts.md` Step 1 tells the agent to scan "all `send_text(json.dumps({...}))` and `send_json({...})` calls" in `core/audio_stream_controller.py`, `routers/system.py` and `services/library_auto_scanner.py`. Live: `audio_stream_controller.py` and `library_auto_scanner.py` contain zero `send_text`/`send_json` (the scanner uses `broadcast_typed`), and the real contract is the typed payloads in `auralis-web/backend/websocket/outbound_messages.py` plus `ws_handlers/*` and `core/stream_protocol.py` - none of which the skill names (other skills do: `audit-integration.md:93-95`). The frontend half says to look for `sendMessage()`, which does not exist anywhere in `frontend/src`; sends are `manager.send(JSON.stringify(...))` in `hooks/websocket/websocketConnectionCore.ts` and `useWebSocketConnection.ts`. `trace-flow.md` lists for the `gapless` flow "Next track preload, **crossfade**, seamless transition" (no crossfade exists under `auralis/player/`; it is retired per `_audit-common.md:83`), for `queue` "**persistence**" (the live queue is not persisted since #5358/#5526), and Layer 3 "**Manager**: Which manager method is called?" with a `manager.py:L55` example row (the `LibraryManager` facade was deleted in #4915).
- **Impact**: `/sync-contracts websocket` is the contract check for the 26 typed outbound messages and scans the wrong files, so it can report "backend never sends X" for types that are defined in `outbound_messages.py`; `/trace-flow gapless|queue` goes looking for removed behaviour.
- **Siblings**: `audit-integration.md:150` (dim_7 TD7-01) has the "Persisted queue" version of the same retired-feature row.
- **Related**: #4915, #5358, #5526, #4642 (all closed).
- **Suggested Fix**: In `sync-contracts.md` replace the three backend files with `auralis-web/backend/websocket/outbound_messages.py`, `ws_handlers/`, `core/stream_protocol.py`, `core/stream_messages.py` and name `broadcast_typed`; for the frontend name `types/ws/` and `hooks/websocket/websocketConnectionCore.ts`. In `trace-flow.md` drop "crossfade" and "persistence" and rename Layer 3's Manager to `LibraryDatabase`/service.

##### TD10-06: `audit-tech-debt.md` contains an expired point-in-time anecdote and a Dim 10 spec that does not match the artifacts it audits
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/audit-tech-debt.md:294`, `:301-309`
- **Status**: NEW
- **Age**: line 294 `5cc6a3d2` 2026-09-14; Dim 10 block from the original skill
- **Effort**: trivial
- **Description**: (a) Line 294 states "**Verified 2026-09-14**: ... #4245 and #4249's targets have since drifted back over 300 LOC ... (chunked_processor.py 358L, enhanced_audio_player.py 311L) without reopening either issue". It was overtaken two days later: #5454 was filed from exactly that finding and closed (2026-09-16, re-affirming a 330-LOC waiver for `processing_engine.py`). Live: `chunked_processor.py` 300, `enhanced_audio_player.py` 314, `processing_engine.py` 330, none of the quoted numbers. The paragraph says "re-check current LOC before citing", then hardcodes numbers that need exactly that re-check. (b) The Dim 10 checklist item "'Existing: #NNN' callouts in skill files where the issue is now CLOSED" matches nothing: no skill or agent file contains an `Existing:` callout, and all 63 `#NNNN` refs are CLOSED provenance ("deleted in #4565"), so the item is permanently vacuous. (c) Dim 10's entry points omit `.claude/agents/*.md` and `_audit-*.md`, which hold most of the claims (and most of TD10-01..05). (d) The dedup/phase paths hardcode `/tmp/audit/tech-debt/` and Phase 4 does `rm -rf /tmp/audit/tech-debt`, which would delete the shared input files a multi-project run depends on (this run had to override it per brief).
- **Impact**: Anyone quoting line 294 repeats 2026-09-14 numbers as current; the Dim 10 spec steers future auditors away from the agents/shared files where the rot actually is.
- **Siblings**: `audit-tech-debt.md:157,160` quote issue numbers (#4405, #4239, #5223) as "e.g." examples only; fine.
- **Related**: #5454 (closed), #4673.
- **Suggested Fix**: Delete the "**Verified 2026-09-14**" sentence (keep the #4673 rule); rewrite the Dim 10 "Existing" item as "cited issues that are CLOSED but phrased as pending (`tracked in`, `until #N lands`)"; add `.claude/agents/*.md` and `_audit-*.md` to its entry points; make Phase 4 remove only this run's own `dim_*.md`.

##### TD10-07: `/audit-sync` has never run, and it cites `/audit-suite` for a rule `/audit-suite` contradicts
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/audit-sync/BASELINE` (`0f722fbb`), `.claude/commands/audit-sync.md:55` vs `.claude/commands/audit-suite.md:99,169`
- **Status**: NEW
- **Age**: skill added `edc191fc` / `0cb5e587` 2026-10-16; `BASELINE` last touched `0cb5e587` 2026-10-16
- **Effort**: small
- **Description**: (a) `audit-sync.md` says `BASELINE` "was seeded with the last commit that touched `.claude/commands`, not a verified sync point". `prep.sh` run today reports "base 0f722fbb (2026-10-16) -> HEAD: 194 commits", "cited & closed since base: 0" and per-group weights frontend 266, integration 115, regression 95, engine 77. No commit has advanced BASELINE since, so the claim-level counterpart to the path gate has never completed a pass, and the drift that followed (queue-history retirement 2026-10-19, TD10-01..05) is the exact failure it exists to catch. (b) `audit-sync.md:55`: "Agents must not start sub-agents: a nested agent's completion notice never reaches its parent (see `/audit-suite`)". `audit-suite.md` contains no such statement; it instead instructs the opposite: each suite audit is a background agent that "internally launch[es] their own sub-agents for each dimension" (`:169`), and `:99` only records that 8 simultaneous orchestrators "saturated the concurrent-subagent limit" and ran inline. Either the suite design is broken (lost notices) or the audit-sync rule is wrong; the cross-reference points at nothing.
- **Impact**: The sync step is not part of any workflow that runs it; the sibling skills keep drifting. A contradictory nesting rule makes it unclear how `comprehensive` is meant to be run.
- **Related**: TD7-01/03, TD10-01..05 are all deltas this skill would have produced.
- **Suggested Fix**: Run `/audit-sync` once and advance `BASELINE` in the same commit; add a "skills synced to <sha>" line to `/verify-release`. Reword `audit-sync.md:55` to state the observed behaviour directly and make `audit-suite.md:169` consistent with it (the safer rule is "suite audits spawn their own agents; sync agents do not").

## Merge Log

Cross-dimension duplicates removed at merge (the content of each is preserved in the target finding):

- **TD1-01** → already tracked by open #5738, which names the stale `TODO(#5537)` marker
- **TD1-02** → merged into TD2-04
- **TD2-21** → merged into TD8-03
- **TD7-04** → merged into TD5-04
- **TD5-05** → merged into TD3-13
- **TD10-08** → merged into TD9-03 (same finding)
- **TD9-10** → Existing: #5481, moved to Deferred

## Deferred

Findings gated on in-progress work or on a product/maintainer decision. They are still listed in Findings above, except TD9-10.

| ID | Gated on |
|---|---|
| TD2-01 | Product call: wire `HybridProcessor.set_user()` into the player, or delete the preference-learning write path. |
| TD2-02 | Product call per PyO3 binding; `process_chunks` is already open as #5738. Decide before deleting the Rust modules. |
| TD2-05, TD2-16 | Do these in the same pass as open #5628 (orphaned components), which they extend. #5628 itself is partly stale: it lists `ShuffleModeSelector`, which #5642 deleted. |
| TD2-18 | Product call: move `recording_type_detector.py` under `scripts/` or delete it together with the 3 dev scripts that use it. |
| TD8-05 (backend half) | Coordinate with #3838 (the `response_model=` rollout owns the `TrackResponse` union). |
| TD8-06 | Needs a `migration_v022_to_v023.sql`; fold the two vestigial columns into open #5755's column-removal migration. |
| TD8-11 | Maintainer decision: rename `Streamlined*`/`Simple*`, or record in CLAUDE.md that they are the proper names so audits stop re-flagging them. |
| TD9-09, TD9-13 | Opportunistic: split only when the file is next touched for a behaviour change. |
| TD9-10 | **Existing: #5481** (open, informational). Update its numbers instead of filing a new issue; the proposals are below. |

<details><summary>TD9-10 (Existing: #5481) — function-length census update</summary>

##### TD9-10: Function-length census, 77 Python functions over 100 LOC; update of #5481 with extraction proposals for the worst eight
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: see the table below
- **Status**: Existing: #5481 (open, informational). Its numbers (76, six examples) are one function out of date, and the proposals below are new.
- **Age**: 77 at base `c870728a` and 77 now, but the set changed. Out: `process_chunk_only` (157 -> 89), `UnifiedConfig.__init__` (127 -> 68), `get_processing_parameters` (114, gone). In: `library_scan.scan_library` (290; a former nested closure, now module-level so it counts on its own), `_shutdown_components` (148, moved by #5236), `_set_queue_impl` (124, moved by #5237), `build_hybrid_components` (114), `upload_and_process` (102). Growers: `_render_to_sink` 209 -> 244, `ContinuousMasteringBranch.apply` 197 -> 225, `StreamlinedCacheWorker._process_chunk` 93 -> 132, `_master_file_impl` 104 -> 130.
- **Effort**: small to medium each
- **Description**: Top of the census (own line count; nest = deepest If/For/While/Try/With):

  | LOC | nest | Function | Proposed extraction |
  |---|---|---|---|
  | 298 | 6 | `analysis/fingerprint/windowed_compute.py:88` `compute_windowed_fingerprint` | One `try` wraps 291 lines. Extract `_load_body_and_probes` (fresh-load vs preloaded-audio branches, lines 121-210; both branches repeat "centre on 50%, round to target rate, crop 25%/75% probes"), `_apply_multiwindow_loudness_correction` (lines 234-290) and `_to_json_safe` (291-end). |
  | 292 | 5 | `library/scanner/scanner.py:130` `scan_directories` | TD9-08: slot acquire / path pre-count / batch pipeline / overflow fallback. |
  | 290 | 5 | `routers/library_scan.py:207` `scan_library` | `_run_scan_with_progress` (the 85-line `_progress_callback` closure, lines 248-335), `_enqueue_added_tracks` (339-364), `_broadcast_scan_result` (365-419), and one `_terminal_frame_for(exc)` mapping for the terminal-frame paths (420-490) that each repeat the "clear scanning state" step. |
  | 270 / 260 / 236 | 3 / 2 / 3 | `core/stream_enhanced.py:41`, `core/stream_seek.py:43`, `core/stream_normal.py:42` | Deliberately deferred by #5032 (closed; its file-size criterion is met). Listed for completeness; the three share a skeleton that the `*_chunks.py` pump functions (224 / 194 / 173) also repeat. |
  | 244 | 7 | `core/mastering_chunk_loop.py:126` `_render_to_sink` | Deepest nesting in the repo. Extract `_read_chunk_window` (read + float32 + channel layout, lines 160-200), `_true_peak_guard` (song-level ceiling, about 30 lines) and `_write_crossfaded_region` (about lines 270-340), so the `while read_pos < total_frames` body fits on one screen. |
  | 241 | 2 | `config/routes.py:44` `setup_routers` | 21 `include_router` calls, each with its own `try/except` for optional modules. Replace with a table of `(flag, module path, factory name, dep selectors)` driven by one loop; the function drops to about 60 lines. |
  | 236 | 3 | `io/loaders/ffmpeg_loader.py:346` `load_with_ffmpeg` | TD9-06. |
  | 225 | 2 | `core/mastering_branches/continuous.py:44` `ContinuousMasteringBranch.apply` | A flat sequence of about 14 DSP stages with long justification comments (lines 61-266). Express it as an ordered list of `_stage_*` methods called from a short loop, so each stage and its comment is independently testable; nesting is not the problem. |
  | 192 / 191 | 4 / 5 | `services/library_auto_scanner.py:207` `_do_scan`, `library/migrations/normalize_existing_artists.py:92` `_normalize_inner` | `_do_scan` per TD9-08; `_normalize_inner` is a one-shot migration, leave it. |

  Other functions over 150: the router factories (TD9-03), `PlaylistMembershipMixin.add_track` 151, `config/startup/shutdown.py:29` `_shutdown_components` 148, `core/stream_protocol.py:137` `send_pcm_chunk` 147, `LibraryDatabase.__init__` 168 (TD9-08), `GaplessPlaybackEngine.advance_with_prebuffer` 172 (TD9-07), `routers/files.py:193` `upload_files` 167, `core/mastering_prepare.py:76` `prepare_file` 157.
- **Evidence**: AST scan (end_lineno - lineno + 1) over 2,382 functions in `auralis/` and `auralis-web/backend/`; 339 are over 50 lines. Nested defs inside a closure are counted separately, so router factory lengths include their handlers.
- **Impact**: Review surface and unit-testability, not correctness.
- **Related**: #5481, #5032, TD9-03.
- **Suggested Fix**: Update #5481's numbers (77; the six named examples are all still above 190) instead of filing a new issue, and take the proposals above opportunistically with the file-level splits in TD9-02/-06/-08.

</details>

## Already Tracked (open issues confirmed during this audit, not re-reported)

**Dim 1 — Stale Markers**

- #5484 - `TODO(#5484)` at `auralis-web/backend/config/middleware/security_headers.py:96`: OPEN; CSP `script-src 'unsafe-inline'` revisit trigger (Vite CSP/nonce support or a browser-driven test suite). Legitimate marker. Blame `254d93059` 2026-09-16. In the middleware applied to every response, so it is reachable from all shipped routes, but it is a documented accepted risk (LOW, Electron-only, no remote content).
- #5738 - OPEN, Rust `process_chunks` dead code + unchecked `chunk_size - overlap`; overlaps TD1-01's subject (see above).

**Dim 2 — Dead Code & Unused Surface**

- #5738 -- Rust `process_chunks` is dead code (the `process_chunks` binding and `chunk_processor.rs`)
- #5628 -- 33 orphaned component files (also stale: it lists `ShuffleModeSelector`, deleted by #5642; extended by TD2-05)
- #5129 -- dead memoized selector cluster in `store/selectors`
- #5132 -- five unused design-system primitives
- #5646 -- `themeConfig.ts` dead parallel palette and `glassEffects`
- #5615 -- connection Redux slice is write-dead; API health poll lives in an unmounted component
- #5754 -- `GenreRepository.get_tracks_by_genre` is a dead method
- #5755 -- scanner computes and the schema carries unused data (`file_hash`, level columns, indexes)
- #5495 -- `process_all_chunks_async` has zero production callers
- #5494 -- `HeartbeatManager.is_alive` is dead
- #5088 -- `get_full_processed_audio_path` is unreachable
- #5189 -- queue/playlist reorder is unreachable from the UI

**Dim 3 — Logic Duplication**

- #5499 — `TrackListResponse` / `AlbumListResponse` paginated envelope duplicated verbatim
- #5381 — similarity/graph/fingerprint-queue routers map DB-locked to 500 (the divergence in `_with_similarity_error_handling` vs `with_error_handling`)
- #5368 — `SimilarityGraphRepository` bypasses `RepositoryFactory`
- #5686 — `QueueController.get_track_count()` / `get_queue_size()` duplicates
- #5649 — four `fetch()` sites bypass the shared transport (the frontend HTTP-layer duplication)
- #5652 — error-message normalization inconsistent (19 inline `instanceof Error ? e.message` sites)
- #5746 / #5744 — layout-dependent analyzer bugs (the symptom side of TD3-04)
- #5700 — RMS-proxy vs K-weighted LUFS mismatch between `windowed_compute` and `mastering_prepare`
- #5130 / #5634 — hook cleanup gaps (not duplication)

**Dim 4 — Magic Numbers & Hardcoded Constants**

- #5648 — residual literal spacing/radius/line-height/animation-duration values bypass design tokens (frontend)
- #5190 — five frontend fetch calls lack timeout/AbortController
- #5244 — ML genre classifier singleton hardcoded to 44.1 kHz `FeatureExtractor`
- #5729 — real-time chain built for `config.sample_rate`, never told the track's rate
- #5558 — `LevelManager` +40 dB `MAX_GAIN_CORRECTION_DB` after the limiter (constant is named; the issue is behavioral)

**Dim 5 — Stub & Placeholder Implementations**

- #5617 — Track context menu never loads playlists (the `onPlaylistsLoad={() => {}}` stub in `TrackRow.tsx:192` and `TrackTableRowItem.tsx:140`; `fetchPlaylists` is defined at `useTrackContextMenu.ts:50` but never called; regression since `b197637e` 2025-11-23). This is the one UI-reachable stub in the tree.
- #5614 — Track context menu lists Favourite / Go to Album / Go to Artist / Track Info items that do nothing (the `callbacks.onX || (() => {})` defaults in `contextMenuActions.tsx`).

**Dim 6 — Test Hygiene**

- #5685 — `tests/integration/test_api_workflows.py` (all 20 tests dark: `api_client` fixture does `pytest.skip`, lines 47-66).
- #5187 — `test_dc_offset_at_maximum` skip cites an OPEN issue; legitimate.
- #5191 — two strict `xfail` in `tests/backend/test_error_handling.py:173,213` cite an OPEN issue; legitimate.
- #5674, #5677, #5678, #5679, #5680, #5681, #5682 — frontend vacuous error assertions, title-only integration specs, no-op `vi.mock` targets, baseline-ratchet floor, harness drift, and the missing frontend weak-assertion gate.
- #5673 — HIGH defects with no pinning test.
- #5195 — three untracked failures in `test_stream_normal_read_timeout_5082.py`.
- #5189 — reorder routing bug the useAppDragDrop characterization tests pin.

**Dim 7 — Stale Documentation & Comments**

- #5070 — `FRONTEND_MISSING_HTML` links to `/api/docs`, which `create_app()` disables outside dev (FIRST_TIME_SETUP's `/api/docs` links are fine because they use `--dev`).
- #5275, #5270, #5538 — individual inaccurate comments/docstrings in the backend/quantizer (not re-checked, owned by their issues).

**Dim 8 — Backwards-Compat Cruft & "No Variants"**

- #5686 — `QueueController.set_queue()` "for backward compatibility" docstring and duplicate `get_track_count()`/`get_queue_size()`
- #5628 — 33 orphaned frontend components; includes both `SearchBar.tsx` copies (`library/SearchBar.tsx` is test-only, `navigation/SearchBar.tsx` only feeds the orphan `LibrarySearchControls`), so the duplicate SearchBar is not re-filed
- #5755 — dead `tracks` columns and indexes (TD8-06 adds the two non-`tracks` columns for it to absorb)
- #5718 — `fingerprint_blob` has no migration (the blob is also write-only: nothing reads `fingerprint_blob` outside tests, though `fingerprint_upsert_mixin.py:131` says it is stored "for backward compatibility"; belongs in that issue's fix)
- #5689 — `pytest.ini` blanket-ignores `PendingDeprecationWarning` (no first-party deprecation warnings exist to hide; only noted)
- Dim 2 (`dim_2.md`) already holds: TD2-13 `# noqa: F401` re-exports, TD2-14 `chunk_crossfade.py`, TD2-21 three ignored parameters

**Dim 9 — File / Function / Module Complexity**

- #5481 — Python function-length census (updated in TD9-10: 77 functions, proposals for the worst eight).
- #5628 — 33 orphaned component files (`QueueSearchPanel` and `ConnectionStatusIndicator`/`ConnectionDetailsPanel` are large but should be deleted, not split).

**Dim 10 — Audit-Finding Rot**

- #5481 - Python function-length census: 76 functions over 100 LOC (previous report's TD9-09; the only OPEN issue from that report).
- Open-issue overlap for this dimension: none. All 63 `#NNNN` refs in `.claude/commands/` and `.claude/agents/` are CLOSED (including #2324, cited as `#2324/#3907`).

## Checked and Clean

Verified as **not** debt this run, recorded so the next audit does not redo them.

<details><summary>Dim 1 — Stale Markers</summary>

- Census FP identified: `auralis-web/frontend/src/store/middleware/__tests__/errorTrackingMiddleware.test.ts:451` ("`0.xxxxxxxx…`" in a comment about `Math.random().toString(36)`) is the single raw-vs-genuine gap (3 raw, 2 genuine). Filtered by `0\.x{3,}`. Confirmed false positive.
- `tests/` tree: 0 genuine markers. The two raw `XXX` hits (`tests/backend/test_similarity_error_redaction.py:66` `(ref XXXXXXXX)` correlation id; `tests/backend/test_thumbnail_concurrency_4527.py:100` `.tmp-XXXX` suffix) are the documented non-marker uses. No `TODO`/`FIXME`/`HACK` in `auralis-web/frontend/src/**/__tests__` or anywhere else under frontend `src` (case-insensitive sweep).
- The 3 former `tests/` markers (`TODO(#5172)` x2, `TODO(#5174)`): both issues CLOSED 2026-09-15, markers replaced with in-place decision comments plus a pinning test (`test_failed_migration_raises_migration_error`). Clean.
- 2026-09-13 TD1-01 (`schema.py` `#3xxx` placeholder + nonexistent `normalize_to_range`): fixed in #5345; the comment now points at `rust_fingerprint.py`.
- 2026-09-13 TD1-02: `#5347` closed; middleware prose is now `TODO(#5484)` against an OPEN issue; `useAlbumFingerprint.ts:97-102` rewritten as "Settled decision, not a pending revisit" and no longer cites closed #5122.
- Prose-deferral hits, classified as ordinary prose (not deferrals):
  - `auralis/core/mastering_chunk_loop.py:103` "temporarily changing the process-wide umask" - explains what the code avoids doing (#5592, CLOSED, fix in place; `95d71a271` 2026-10-17).
  - `auralis-web/backend/core/audio_processing_pipeline.py:197` "Temporarily disable per-chunk fingerprint analysis" - describes a set/process/finally-restore toggle held under `_process_lock` (#4354); not a deferral. Blame `89dc46f78` 2026-07-14.
  - `auralis-web/backend/routers/errors.py:20/21/143` - HTTP 503 "temporarily unavailable" client-facing copy.
  - `auralis-web/frontend/src/utils/errorHandling.ts:297` - "501 Not Implemented" status name.
  - `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:274` - "required behaviour, not a workaround" (#3759/#4659 rationale).
  - `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:99` - "Settled decision, not a pending revisit".
  - `auralis-web/backend/config/middleware/security_headers.py:96` - the genuine `TODO(#5484)`, double-counted by the prose grep.
- High-recall sweep (`not yet|in the future|later we|until we|for now|revisit|for the time being|workaround|eventually|stopgap|quick fix|placeholder|to be implemented` in comments, non-test shipped Python/TS/Rust, case-insensitive): 64 hits read; only `continuous_dsp_ops.py:285` (TD1-02) is a genuine untracked deferral. Others verified ordinary: `routers/processing_parameters.py:25` ("placeholder values until a live profile exists" - documented fallback via `is_default: True`, #3779), `ws_handlers/connection.py:75` ("Re-evaluate rather than sending an extra ping"), `core/job_execution.py:139` ("ever broken ... in the future" - defensive rationale), `loudness_meter.py` short-term windows, fingerprint "claim placeholder" row (a live design), UI "placeholder" skeleton/gradient components, `BufferScheduler.ts` "not yet played".
- `todo!()` / `unimplemented!()` in `vendor/auralis-dsp/src`: 0. `# noqa` / `# type: ignore` justified with "temporary/for now/todo" in `auralis/` and backend: 0.
- `desktop/` and `scripts/`: no `TODO`/`FIXME` (JS/TS/Python).

</details>

<details><summary>Dim 2 — Dead Code & Unused Surface</summary>

- All 15 prior Dimension-2 findings are still fixed: #5352 (`FingerprintConstants`), #5366 (re-export; see TD2-14 for the module), #5372 (4 `reference_library` functions; see TD2-03 for the remainder), #5383 (`version.py`), #5386 (`checker.py` gone), #5388, #5392, #5395, #5401 (`serialize_track`), and the `QueueStats` and `CorruptedTrackError` classes.
- `core/chunk_cache.py` is absent (#5492). No Rust `#[allow(dead_code)]` (0). Rust `pub fn` sweep: only `BiquadFilter::highpass` and `to_array` are uncalled (TD2-02).
- `ruff F811` (redefinition): 0 hits. All other `noqa: F401` sites are legitimate: `main.py:187-208` startup probes, `routers/player.py` and `processing_api.py` re-exports consumed by `files.py` and tests, `cache/manager.py`, `similarity.py`, and `config/middleware/__init__.py` (consumed by tests and `app.py`).
- Route handlers, middleware `dispatch`, `watchdog` `on_*` handlers, Pydantic validators (`validate_position`, `clamp_volume`, `lowercase_preset`), SQLAlchemy event listeners (`set_sqlite_pragma`), `logging.Formatter.formatException` and `__getattr__` lazy exports are vulture false positives and were skipped.
- `routers/errors.py` `*UnavailableError` classes are now wired (`tests/backend/test_typed_unavailable_errors_wired_5400.py`).
- `PerformanceProfiler` is the only live piece of `auralis/optimization/` (wraps `AdaptiveMode.process`); `scripts/check_optimization_importers.py` still matches reality for it (TD2-07 concerns the rest of the package).
- `auralis/cli/fetch_artwork.py` has no importer but is a `python -m` entry point. `FingerprintCatalog` (`analysis/fingerprint/catalog.py`) is used by `scripts/fingerprint.py`. Both are skipped as dev surface.
- No `knip` / `ts-prune` in `package.json`; frontend results come from a custom walk (TD2-16/17) that does not parse `export { ... }` or `export default` forms, so they are conservative.
- The `desktop/resources/auralis/` copy of the engine is gitignored and ignored in all counts.

</details>

<details><summary>Dim 3 — Logic Duplication</summary>

- Enhancement preset mirrors: `schemas.VALID_PRESETS`, `proactive_buffer.AVAILABLE_PRESETS` (deliberate layering exception), `outbound_messages.py`, `types/domain.ts`, `playerSlice`, `usePlayerStateSync`, `useEnhancementControl` all say `'adaptive'` only.
- Supported audio extensions: one source, `auralis/io/formats.py`, imported by the scanner, catalog, files and processing routers. The `processing_jobs.py:98` media-type map is a different concern (output container MIME).
- `escape_like`: used by the 4 repositories (#5406 fix in place); `BaseRepository._session_scope()` adoption complete (115 uses; no stray `get_session()` outside `base.py`); `FingerprintSimilarityMixin` fixed (#5202).
- `ChunkPumpResult` defined once in `stream_messages.py` (#5403 fix in place); `send_stream_completion` shared by all three handlers.
- NaN/Inf repair is centralised in `utils/audio_validation.py` (`validate_audio_finite` / `sanitize_audio`). The only outlier is `BaseAssessor._normalize_audio`, which copies via `np.array(...)` first, so it is safe.
- No in-place mutation of caller audio found in `dsp/`, `core/stages/`, `core/processing/`, `core/dsp/` or `player/realtime/`. `dsp.basic.amplify` copies first; `auto_master` and `level_matcher` work on `.copy()` / new arrays. The HIGH trigger did not fire.
- Stage family (`core/stages/*`): no per-stage copy/NaN duplication left (#4298 closed; the stages delegate to shared DSP objects and the `no_op` helper).
- `AdaptiveCompressor` / `AdaptiveLimiter` lookahead ring buffer: single `LookaheadBuffer` (#4309 fix in place).
- `useRestAPI` / `useStandardizedAPI` (#4300): now a documented split (generic REST vs cache-telemetry polling). `routers/pagination.py::compute_has_more` is used by all 5 paginated routers (#4902).
- Backend and frontend WS message-type lists were not compared here; that belongs to `/sync-contracts`.
- Stale-by-design name collisions not reported: `Genre` (reference enum vs ORM model), `QueueManager` / `PlayerStateManager` / `AudioPlayer` Protocols in `services/` (typing seams over the real classes).

</details>

<details><summary>Dim 4 — Magic Numbers & Hardcoded Constants</summary>

- Chunk geometry: `CHUNK_DURATION`/`INTERVAL`/`OVERLAP`/`CONTEXT` are defined only in `chunk_boundaries.py:20-23`; no `15.0`/`10.0`/`5.0` chunk literals elsewhere in backend; only `ceil` chunk counts are inside `chunk_boundaries.py` (`content_chunk_count`, :38, :177) and `playback_mixin.py:62` is a docstring. #4024/#4025/#4026/#4027/#4289/#4914/#4620 fixes all hold.
- Frontend chunk math: no `Math.ceil(duration/10)`; `audioConstants.ts` (`lowWaterMarkSeconds` 5/8 s, 4096 buffer) and `BufferScheduler.ts:63` only reference the 10 s interval in comments (#4031 fix holds). `audioChunkIngest.ts:120` `/10` is a 10 %-progress throttle, not chunk geometry.
- `sample_rate=44100` default: 22 sites, same file list as 2026-09-13, zero new. `sr: int = 44100` variants (`mastering_fingerprint.py:83,247` librosa load target; `quality_assessors/base_assessor.py:152,182`; `estimation_ops.py:205,346,396`) have no live callers that omit the rate or are resample targets, not position math. `masking.py:87` carries a documented #4622 note on a dead method. `cache/models.py:31` `_NOMINAL_SAMPLE_RATE` is a named, commented eviction-budget estimate. `chunk_render.py:160` and `chunked_processor.py:137` `or 44100` are None-narrowing after metadata load. `chunk_render.py:279` `sample_rate // 10` (100 ms silence) is a commented length.
- Bare `44100`/`48000` in arithmetic: only `frames_for_seconds(sr, 1024/44100)` idiom (`spectral.py:265-266`, `feature_extractor.py:201-202`, `phase_correlation.py:233`), doctests, and a log-message ms estimate (`audio_processing_pipeline.py:90`). No HIGH trigger. Frontend `BufferScheduler.ts:288,430` `|| 44100` and `PCMStreamBuffer.ts:50` `48000` are pre-`initialize()` fallbacks that are always overwritten (the two fallbacks differ, harmless).
- Backend timeouts/queue sizes: `audio_stream_controller.py:132,140` (`CHUNK_PROCESS_TIMEOUT`, `STREAM_ACQUIRE_TIMEOUT_SECONDS`) are consumed by name in `stream_normal.py`, `stream_seek.py`, `recommendation_service.py` (#4032/#4930/#5196 fixes hold); remaining inline `sleep(0.1/1.0)` and `join(timeout=5)` sites are one-off, commented, per-file (not clustered). `env_config.get_int_env` consumers and `config/limits.py` hold the tunables; `executors.py`, `fingerprint_queue.py MAX_QUEUE_SIZE`, `MAX_BATCH_UPDATES` etc. are named.
- Engine FFT sizes: `UnifiedConfig.fft_size` is threaded to `EQSettings` via `hybrid_setup.py:50`; the other 4096 defaults (`SpectrumSettings`, `spectrum_operations.create_window`) are independent analyzers' own defaults; `quality_metrics.py:68` 8192 is an explicit per-analyzer choice. `resonance_notcher` FFT scaling (#4030) holds.
- Frontend colors: 0 hardcoded color literals in components/hooks beyond TD4-07; design-system tokens are used (`GlowingArc`, `toastColors`, `MediaCardArtwork` reference tokens, hex only in comments); `hsl/rgba(${...})` hits are computed from data (fingerprint hue, album palette).
- Frontend timers: named constants for the big ones (`STREAM_START_WATCHDOG_MS`, `RECOMMENDATION_TIMEOUT_MS`, `POLL_INTERVAL_MS`, `CACHE_STATS_REFRESH_INTERVAL_MS`, `SESSION_RESET_TOAST_MS`); the inline ones (`EditMetadataDialog.tsx:75` 1000, `useFingerprintStatus.ts:108` 2000, `usePlaybackTransport.ts:129` 100) are single-use and commented.
- Loudness standards (`-14`, `-23`, `-1.0` true-peak) in `assessment_constants.py` are named per platform; not flagged as protocol magic.

</details>

<details><summary>Dim 5 — Stub & Placeholder Implementations</summary>

- `NotImplementedError`: 0 in `auralis/` and `auralis-web/backend/`; `duplicate_detector.py` gone (`aedab0dc`, #5362). `# TODO` markers: 1 (`security_headers.py:96`, `TODO(#5484)`, Dim 1's concern).
- AST sweep (FunctionDef/AsyncFunctionDef with body only `pass` / `...` / `return`/`None`/`[]`/`{}`/`0.0`): all 70 hits are Protocol bodies (`playback_service`, `queue_protocols`, `outbound_messages`, `recommendation_service`, `cache_cleanup`, `reference_seeder._FingerprintRepoLike`), 25 `@overload`s of `broadcast_typed`, and `@abstractmethod`s (`BaseAssessor` x5 implementers, `ProcessingBranch`, `BaseSpectrumAnalyzer`).
- `routers/similarity.py:138 _unavailable()` returns `None`: documented DI default (#4670), always replaced by a per-router ContextVar binding.
- `AudioFingerprintAnalyzer.close()` no-op: documented, deliberate hook (`HybridProcessor.close()` forwards generically, #4744).
- `PLACEHOLDER_LUFS_SENTINEL` (-100.0) and the `fingerprint_scheduler_repository` claim-placeholder rows: designed claim sentinel, filtered by `fingerprint_shared.py`; cleaned on startup.
- `GET /api/processing/parameters` placeholder dict (`routers/processing_parameters.py:25-38`): returned only until a live `ChunkedAudioProcessor` profile exists, and tagged `is_default: True` (#3779), so it is not mock data passed off as measurements. Note it has no non-test frontend consumer (`/api/processing/*` is unused by `auralis-web/frontend/src`); that is a Dim 2 question for the owner of the processing router, not a stub.
- Literal-dict returns in routers/services (AST scan of `routers/`, `services/`, `ws_handlers/`, `core/`): 23 hits, all status messages (`{"message": "Playlist cleared"}`), empty-state fallbacks (`queue_service.py:62`, `level_manager.get_statistics`, `similarity_graph` clear with no builder), or the 503-style `{"available": False}` for the fingerprint queue. None replaces a repo/engine result.
- "simplified" DSP implementations (`dsp/eq/masking.py`, `analysis/dynamic_range.py:262`, `quality_assessors/utilities/estimation_ops.py:27`, `analysis/ml/feature_extractor.py:266`, `core/analysis/content_analyzer.py:296`): real approximations with working code, not stubs; `analysis/ml/genre_weights.py:35` states the rule-based design is intentional.
- Other frontend greps (`coming soon|not implemented|=> {}|=> undefined`): no "Coming soon" text remains (`AddToPlaylistMenu.tsx:6` only records that #4240 removed it); `ArtistHeader.tsx:89` records that the "Artist" literal placeholder was removed (#5153); `PanePlaceholders.tsx`, skeletons and `MediaCardArtwork` placeholders are real fallback UI; `onBufferUnderrun = () => {}` etc. in `AudioPlaybackEngine`/`PlaybackPositionTracker` are initialized-then-replaced callbacks. No permanently `disabled` buttons.
- `pass` as sole body of non-except blocks: 2 (`soundfile_loader.py:135` mono arm of an if/elif chain, `adaptive_loudness.py:113` "skip bass reduction" arm), both intentional idioms with comments.
- Protocols with no explicit subclasses (`AudioPlayer`, `QueueManager`, `PlayerStateManager`, `ClearableChunkCache`, `_FingerprintRepoLike`): structural; real implementers exist for the backend ones (`EnhancedAudioPlayer`, `QueueController` in `player/queue_controller.py`, `core/state_manager.py:PlayerStateManager`, `cache/clearing_mixin.py:clear_all`); implementer coverage for `_FingerprintRepoLike` was not individually traced.

</details>

<details><summary>Dim 6 — Test Hygiene</summary>

- Frontend: 0 `it.skip`/`describe.skip`/`it.todo`/`xit` (the earlier "3" is a string in the guard test); #5179/#5186 resolved by `5f561702`. 0 commented-out `expect(`; 0 `console.log` in specs. The only spec whose name matches a `vi.mock` target is `apiRequest.test.ts`, and it mentions the mock only in a comment saying it intentionally does not mock it.
- Python: only 2 commented-out asserts in `tests/`, both prose (`test_main_api.py:734`, `test_repositories.py:126`).
- Weak assertions: `scripts/check_weak_assertions.py` passes ("OK: no new weak-assertion tests"); 37 baselined, 0 multi-assert; gate wired at `backend-tests.yml:155`.
- Print-only tests in collected files: 0. `tests/stress/stress_test_suite.py` (4 `test_*` print-only methods, never collected) is a documented manual entry point (`python tests/stress/stress_test_suite.py --all`) - keep. `tests/validation/` no longer exists (#5149).
- Platform/dependency skips (legitimate): ffmpeg (`test_ffmpeg_*`, `test_unified_loader.py`, `test_fingerprint_unification_4595.py`, `test_engine_fixes_4596_4598.py`), mutagen (`test_metadata_editor.py`, `test_metadata_backup_5307.py`, `test_wma_asf_metadata_5536.py`), POSIX/Windows/symlink (`test_filesystem_errors.py`, `test_artwork_*`, `test_default_dir_hardening_4824.py`, `test_settings_router.py`, `test_migrations.py`), psutil/memory-pressure (`tests/performance`, `test_resource_exhaustion.py`), Rust module (`test_chroma_rust_validation.py`, `test_phase5_rust_benchmark.py`, `test_rust_panic_handler.py`), frontend-source-present guards (`test_*_key_contract*`, `test_ws_broadcast_type_registry_contract.py`), real-audio-collection guards (`test_phase6_*`, `test_hpss_rust_validation.py`, `test_mastering_regression.py`).
- Documented slow-test skips (`tests/stress/test_large_library.py:71,468`, `test_processing_stress.py:74`) carry timing reasons; acceptable.
- Boundary tests that skip on "not supported" exceptions (`test_boundary_max_min_values.py`, `test_boundary_exact_conditions.py`, `test_boundary_empty_single.py`, `test_chunked_processing_boundaries.py`) re-raise `AssertionError/ZeroDivisionError/IndexError` first (#4969 fix intact).
- `pytestmark = pytest.mark.asyncio` (26 files) and `pytestmark = pytest.mark.integration` are markers, not skips.
- Vacuous-patch audit: 161 string `patch(...)`/`monkeypatch.setattr(...)` targets resolved statically against the modules they name (including multi-line targets). 0 vacuous; the 8 apparent hits were comments (`test_artists_api.py:752-760`, `test_files_api.py:119`), function-local imports that are correctly patched at their source (`get_audio_info`, `get_processor_factory`, `apply_crossfade_between_chunks`, `get_artwork_downloader`, `handle_pause`), and a split string target (`mastering_file_evaluation.evaluate_mastering_files`, read via local import at `auralis/core/simple_mastering.py:254`). Of the 25 `.py` files deleted since 2026-08-20 in `auralis/` and `auralis-web/backend`, none is still referenced by a test (the `config.middleware`, `config.startup`, `schemas`, `monitoring` hits are now packages).
- Skill "must not regress" files: `tests/backend/test_audio_stream_crossfade.py` and `tests/test_optimization_is_live_5142.py` exist and contain no skip/xfail. Every other `tests/...` path in `.claude/commands/*.md` resolves (the one "missing" `test_baseline.py` is a substring of `check_pytest_baseline.py`).
- `tests/backend/test_no_unaccountable_skips_4691.py` (module-level skip ratchet) is intact.

</details>

<details><summary>Dim 7 — Stale Documentation & Comments</summary>

- `auralis-web/backend/WEBSOCKET_API.md` (updated `3c81a4cf` 2026-10-20, #5476): every `"type"` value documented is either an inbound command (`play_enhanced`, `play_normal`, `seek`) or exists in `websocket/outbound_messages.py` / the emit code; all 26 outbound Literals plus `pong`, `ping`, `heartbeat`, `error`, `audio_stream_start/end/error`, `audio_chunk_meta`, `fingerprint_progress` are mentioned in the doc. No drift either way.
- 2026-09-13 TD7-01..05 and TDX-02/03: README Run Tests, FIRST_TIME_SETUP launcher/test blocks, `docs/features/` fingerprint docs (superseded banners 2026-09-14), `processor_factory.py`/`audio_processing_pipeline.py` provenance (rewritten as "no longer in the tree"), GPLv3 headers (#5434) all resolved.
- Version: `auralis/version.py`, `pyproject.toml`, package.json files, README and `docs/README.md` all agree on 1.5.1 / unreleased; binaries correctly attributed to v1.2.0-beta.2.
- `python -m auralis.library.init` and `build_auralis.py`: no live docs reference them (only archived/audit reports and TD7-06).
- Python/Node version statements (3.14, Node 24) consistent across README, FIRST_TIME_SETUP, `DEVELOPMENT_SETUP_BACKEND.md`, CLAUDE.md.
- Counts that match live tree: analysis files 55, registered routers 20, `backend/core/` 54 modules, mastering stages 13, Rust 19 `src/*.rs` and 11 pyfunctions, docs topic dirs 18.
- Lingering mentions of deleted modules (`stream_prefetch`, `chunk_cache`, `useEnhancedPlaybackShortcuts`, `useFingerprintCache`, `FingerprintCache`, `keyboardShortcutDefinitions`, `AudioReactiveStarfield` in `App.tsx`, `ShuffleModeSelector` in `cssCustomPropertyProducers.test.ts`, `preview_creator`, `personal_preferences`) in source comments and `_audit-common.md:84` are deliberate "was deleted in #NNNN" provenance notes, not stale claims.
- `_audit-common.md` Retired Architecture list uses italics for deleted files (convention respected); no backticked deleted path beyond the four strict failures.
- `hf_aware_limiter.py` exists on disk; `dsp-specialist.md:17` and `audit-engine.md:25` list it as live. Whether it is dead code is a Dim 2 matter, not a doc-staleness finding.

</details>

<details><summary>Dim 8 — Backwards-Compat Cruft & "No Variants"</summary>

- Python `_`-prefixed parameters (AST pass over `auralis/` and `auralis-web/backend/`): 5 hits, all protocol-constrained (`__exit__(_exc)`, SQLAlchemy `connect` listener `_record`, `_refresh_reference_cloud(*_args, **_kwargs)` callback)
- No `@deprecated`, `warnings.warn(..., DeprecationWarning)`, `AliasChoices`/`validation_alias`, `sys.modules[...]` aliasing or `__getattr__` shim in shipped source other than `fingerprint_queue.py` (TD8-09) and `config/__init__.py` (a circular-import guard, not compat)
- `Field(alias="track_number")` on `MetadataUpdateRequest` is the real tag-name/column-name translation (#4731), not an old-name alias
- Removed presets: no `gentle|warm|bright|punchy|live` string literal in `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/` outside `preset_anchors.py`, the Player test sentinel and "removed" comments; `desktop/resources/auralis/**` still has them but is gitignored build output
- DB-schema compat: no `PRAGMA table_info` or column-presence branches; `schema_indexes.create_missing_declared_indexes` and the `track_fingerprints` index comments are repair-by-design, not shims; `.25d` sidecar reader rejects other `format_version`s rather than reading old ones; the "sidecars written before #5552/#5554" branch in `mastering_target_service.py:215-222` re-derives targets (a correctness choice)
- `advanced_dynamics.py` re-exports (#5452) and `reason`-field breadcrumbs (#5453): both fixed and still fixed
- `AdaptiveMode` + `SpectrumMapper`: product decision to keep (STREAMLINING_PLAN #5, #11); not reported
- `AlbumCard`/`TrackCard` "Maintains backwards compatibility" docstrings: thin wrappers over `MediaCard`, no variant duplication; the sentence is stale but harmless (folded into nothing; delete when the file is next touched)
- `unified_loader.SUPPORTED_FORMATS/FFMPEG_FORMATS` "re-exported for backward compatibility": real production importers (`routers/files.py:79`, `core/stream_normal.py:117`), so not cruft
- `core/stages/*.apply` unused arguments (`bass_pct`, `presence_pct`): the uniform stage-call interface, protocol-constrained
- `radius*`/`spacing*` style constants, design-system "semantic aliases": documented convenience names (#4402), live consumers
- `BufferScheduler` `ScriptProcessorNode` fallback: deliberately kept (#4623)
- Frontend dual-spelling that is *not* compat: `CancelButtonForDialog = CancelButton` and `StyledListItem` "renamed for backwards compat" have live importers; the second is a naming nit only
- Component/hook name pairs `usePlayEnhanced`/`useEnhancedPlayCommand`/`useEnhancedStreamStart`/`useEnhancedSeek`, `AdvancedSettingsPanel`, `stream_enhanced*.py`, `enhanced_audio_player.py`: "enhanced" is the domain term for the mastered stream; the hooks are a decomposition of one flow, not copies
- Duplicate basenames: `core/dsp/{harmonic_exciter,transient_shaper}.py` vs `core/stages/*.py` are processor + stage wrapper pairs (the stage imports the dsp class), `ProgressBar` (player vs design-system primitive) are distinct live components

</details>

<details><summary>Dim 9 — File / Function / Module Complexity</summary>

- Oversized but dead or test-only (delete instead of splitting): `auralis/learning/preference_engine.py` 391 (see TD2-01, delete instead), `auralis/learning/reference_library.py` 357 (see TD2-03, delete instead), `auralis/core/recording_type_detector.py` 492 (see TD2-18, delete instead), `auralis/core/processing/hf_aware_limiter.py` (see TD2-04), `src/utils/queue/queue_recommender.ts` 469 / `queue_statistics.ts` 394 / `queue_shuffler.ts` 383 (see TD2-05, delete instead), `auralis/analysis/quality_assessors/utilities/estimation_ops.py` 429 and `scoring_ops.py` 303 (largely dead per TD2-06; delete the dead helpers and re-measure before splitting).
- The 2026-09-13 closures are intact where it matters: `config/startup/` (largest member 260), `config/middleware/` (222), `schemas/` (242), `cache/manager.py` 282, `routers/player.py` 149, `routers/processing_api.py` 191, `services/queue_service.py` 86, `hooks/shared/useReduxState.ts` 26, `useLibraryQuery.ts` 298, `useAudioStreamingCore.ts` 294, `ComfortableApp.tsx` 267 are all under 300. `PlaylistList.tsx` no longer matches the hook-count threshold (#5480 fixed).
- `schemas/__init__.py` re-exports 31 names, the only `__init__.py` over 20, and it is the deliberate compatibility barrel from #5479 (documented in its docstring, no logic). No `index.ts` has more than 22 exports (`components/library/Styles/index.ts` is a pure token barrel). `config/startup/__init__.py` (188 lines, 3 functions) and `config/middleware/__init__.py` (119 lines, `setup_middleware`) hold wiring logic by design.
- React hook counts: no non-test file has >= 8 `useState` or >= 5 `useEffect` except `hooks/enhancement/usePlaybackTransport.ts` (0 state, 6 `useEffect` in 192 lines); each effect there has a distinct, documented dependency set (volume sync, time ticker, play/pause sync, resume-position getter, disconnect) and is not worth extracting. The highest `useState` counts are 7 (`useLibraryPagination`, `useLibraryQuery`), see TD9-12.
- `processing_engine.py` 330 holds the #5454 waiver ceiling exactly; `chunk_boundaries.py` 435 is constants and pure functions and cohesive.
- Test files: 79 frontend test files exceed 300 lines (about 85 last time); excluded from the shipped census per the brief. Python `tests/` was not in scope.

</details>

<details><summary>Dim 10 — Audit-Finding Rot</summary>

- `#NNNN` refs in skills/agents: 63 distinct, 0 OPEN. None is phrased as pending ("tracked in", "until #N lands", "open issue"). Words like "tracked", "separately" near #5143, #5031 and #5044 are provenance ("the docs #5031 tracks" at `_audit-common.md:80` is the one mild present-tense use; #5031 is CLOSED and the line still reads correctly as a pointer, low value to change).
- Dimension/flow/invariant counts match their headings: backend 11, concurrency 5, deprecation 8 (no count claimed), engine 7, frontend 9, integration 9 flows (description and "all 9" x4), security 10 OWASP categories, tech-debt 10, verify-dsp 6 invariants, `audit-suite` preset audit counts (8/2/3/3/2/3/3) and every `--focus`/`--flows` number in presets maps to the intended dimension.
- "Max 3 concurrent" is stated identically in all 8 orchestrator skills; no retired "Task tool" name remains (all say "Agent-tool"); `.agents/commands/*` mirrors are byte-identical to `.claude/commands/` and `scripts/sync_agent_commands.sh --check` reports "mirror is up to date".
- Domain labels in `_audit-common.md:231-235` (severity, 14 domain, 3 type labels) all exist in the repo's 42 labels.
- Symbol anchors: 197 backticked identifiers extracted from `.claude/commands` and `.claude/agents`; each was grepped across `auralis/`, `auralis-web/`, `scripts/`, `vendor/`, `tests/`. Missing ones are all deliberate deprecation targets (`pkg_resources`, `fftpack`, `cumproduct`, `PropTypes`, `getdefaultlocale`, `assertEquals`, `with_gil`), tool/CLI names (`SendMessage`, `subagent_type`, `run_in_background`), a shell variable (`SRC_DIRS`), or the `EnhancementContext` retirement note. `allow_threads` is test-only on purpose. Only `sendMessage` (TD10-05) is a real stale anchor. `audit-publish.md:115`'s `validate_sample_rate()` is an illustrative example in a template, not a checklist item.
- Retired-architecture cross-check: no checklist item assumes removed presets (all preset mentions say "adaptive only" or list the removed names as retired), `LibraryManager`, the parallel processor, chunk crossfade, `EnhancementContext` or `useQueueHistory`, except the queue-history/`queue_history_repository` rows already in dim_7 and the TD10-05 items.
- `docs/audits/` reports older than 90 days (dated before 2026-07-23): all eight are `*_2026-07-12.md`. Their CRITICAL/HIGH findings are all triaged: BACKEND B3-01/B4-01 -> #4352/#4354 CLOSED; CONCURRENCY CC-1 (same defect as B4-01, #4354); ENGINE ENG-D1-1/D3-1/D4-1/D4-2 -> #4494/#4495/#4496/#4497 CLOSED and ENG-D3-3 -> #5105 CLOSED (re-filed 2026-08-13); FRONTEND H3-01 -> #4426 CLOSED; INTEGRATION F5-01/F2-01/F7-01 -> #4406/#4407/#4408 CLOSED. DEPRECATION, SECURITY and TECH_DEBT 07-12 reports have 0 CRITICAL/HIGH (matched on their summary tables). All 12 HIGH findings were matched by a 183-issue `[2026-07-12]` title prefix; the sample was exhaustive for this date.
- Previous tech-debt report publication: 40/42 matched (see TD10-08). The two unmatched were TD3-03 (published as #5202 earlier) and TD9-03 (never published). The report's Dim 10 "0 findings" claim and "every hardcoded count matches" were correct on 2026-09-13.
- `.claude/issues/<N>/ISSUE.md` state drift: deliberately not examined (immutable snapshots).

</details>
