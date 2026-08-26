# Auralis Tech-Debt Audit — 2026-08-23

**Scope**: Whole repo (`auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/`, `tests/`, `docs/`, `.claude/`). All 10 dimensions, `--depth deep`, no `--limit`.
**Prior report**: [`AUDIT_TECH_DEBT_2026-08-14.md`](AUDIT_TECH_DEBT_2026-08-14.md)

---

## Executive Summary

| | Count |
|---|---|
| **NEW findings** | 44 |
| **Regressions** (previously-fixed debt that crept back) | 2 |
| **Existing findings re-verified** (already tracked, confirmed still accurate — not re-filed) | 25 |
| **Total findings this cycle (NEW + Regression)** | **46** |

By severity (NEW + Regression only):

| Severity | Count | Notes |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 5 | 1 divergent-bug-fix duplication, 2 load-bearing "simplified" stubs, 1 misleading doc-count regression, 1 misleading "API compat" DSP comment |
| LOW | 41 | the default tier — dead code, duplication, magic numbers, stub bookkeeping, test hygiene, doc drift, complexity |

**Direction of travel vs. the 2026-08-14 report**: the codebase is actively closing debt faster than a single audit cycle finds new debt in most dimensions — Dimension 1 (Stale Markers) is now completely clean (0 findings), Dimension 3 (Logic Duplication) confirmed 8 of 8 tracked findings fixed-and-holding with no regressions, and 3 of the 4 previously-mis-closed god-file issues (#4245/#4249/#4254) were genuinely re-closed since the last report. Dimension 2 (Dead Code) is the exception — 20 new findings, but this is explained entirely by scope: this run swept `store/`, `services/`, `design-system/`, `types/` on the frontend, which a prior report explicitly flagged as never-yet-covered, not by a fresh accumulation of debt in previously-audited territory. Two genuine regressions surfaced: `services/queue_service.py` (#4260) grew past its own filing size after being marked fixed, and `CLAUDE.md`/`_audit-common.md`'s structural counts drifted again (a repeat of closed #4401), both within a day of the counts last being synced.

**Headline items**:
- **TD5-2** (MEDIUM): the real-time mastering pipeline's loudness tracking runs on a self-documented "simplified... not real LUFS" RMS approximation on the hot decision path, while a correct BS.1770-4 `LoudnessMeter` already exists in the codebase for a narrower purpose.
- **TD5-1** (MEDIUM): the live `/api/processing/presets` route hands callers a hand-typed preset catalog whose numbers do not match what the engine actually applies for the same preset name.
- **TD8-10** (MEDIUM): a stereo-DSP function's docstring calls two parameters "kept for API compatibility" when in fact the sole live caller computes real values for them that are silently discarded — a misleading label on what may be a real correctness gap.
- **DIM7-05 / TD9-7** (regressions): the CLAUDE.md/`_audit-common.md` doc-count sync (#4401) and `queue_service.py`'s file-size fix (#4260) both regressed after being marked closed.

---

## Baseline Snapshot

Captured 2026-08-23, for the next audit to diff against.

| Metric | Value | Read it as |
|---|---|---|
| markers, genuine (src) | **0** | Expected/good — real marker debt in shipped code |
| markers, raw (pre-filter) | 2 | Diagnostic only, both false positives (`migration_vXXX_to_vYYY` filename pattern) |
| markers, genuine (tests/) | 4 | All <30 days old, all cite OPEN issues (#5172/#5173/#5174) — legitimate, not debt |
| prose deferrals (non-test) | 6 | High-recall/low-precision; read the hits, don't quote the count |
| NotImplementedError | 3 | All confirmed legitimate structural typing, not debt |
| type: ignore (py) | 66 | — |
| @ts-ignore/@ts-expect-error | 3 | — |
| 'any' non-test (ts) | 13 | The type-safety debt that ships — quote this one |
| 'any' raw incl. tests (ts) | 488 | Trend continuity only |
| skipped tests (py) | 44 | Matches tracked baseline; see Dim 6 |
| skipped tests (ts) | 16 | — |
| py files >300 LOC | 90 | See Dim 9 |
| ts/tsx files >300 LOC | 113 | 85 of these are test files; 28 are non-test source — see Dim 9 |
| allow(dead_code) (rust) | 0 | Clean |
| sample_rate=44100 defaults | 30 (raw) / 20 (precise recount, this run's Dim 4 methodology) | **Drift indicator, not a debt count** (#4924). No new live-risk site found. The skill file's own hardcoded "43" reference is now itself stale — see TD10-B. |

---

## Top 10 Quick Wins (trivial/small effort, immediate payoff)

1. **DIM7-01..04** — de-backtick / correct 4 stale file references across 8 `.claude/`/`docs/` locations (`stream_prefetch.py`, `personal_preferences.py`, `services/learning_system.py`, `streaming-mse.test.tsx`). One PR, mechanical.
2. **D2-10** — `ruff check --select F401 --fix` on 4 files removes 6 fresh unused imports from this week's refactors, no behavior risk.
3. **MN-1** — promote the duplicated bare `5.0`s scan-stop grace period (`library_auto_scanner.py`, `library_scan.py`) to one named constant.
4. **TD8-9** — delete the dead `formatDuration` re-export in `types/domain.ts`; zero consumers.
5. **TD8-7** — drop `queue_service.py`'s unused `AudioPlayerWithQueue`/`QueueManager` re-exports.
6. **D2-4** — fix `hybrid_processor_singleton.py`'s docstring (falsely claims `process_hybrid` is package-re-exported) or add it to `__init__.py`'s exports.
7. **D2-6** — delete the zero-caller `sanitize_path_for_response()`; the invariant it targets is already enforced elsewhere.
8. **D2-5** — delete `is_same_artist()`, zero callers anywhere including doctests-as-tests.
9. **TD9-6** — trim `chunked_processor.py` by ~10 lines to close the last mile on the #4245 split (309→<300).
10. **TD10-A/B** — fix the stale "closed in 2026-07" god-file anecdote (now in 2 locations, #5167 covers only 1) and the stale `sample_rate=44100` diff-base number, both one-line skill-file edits.

## Top 5 Medium Investments

1. **TD9-1** — split `auralis-web/backend/config/startup.py` (1132 LOC, now the single largest file in the codebase) along its three already-implicit lifecycle phases: components, teardown, temp-file reclamation.
2. **TD5-2** — swap the real-time mastering pipeline's loudness tracking from the "simplified" RMS approximation to the existing BS.1770-4 `LoudnessMeter`, re-tuning the empirical tanh-curve constants against true LUFS values.
3. **TD9-9** — split `auralis-web/backend/cache/manager.py` (713 LOC) into chunk-cache core, tier eviction, and the unrelated bolted-on mastering-recommendation cache.
4. **TD9-7** — split `services/queue_service.py` (747 LOC, a regression of closed #4260) by operation-shape (mutation ops vs. read/broadcast), mirroring the proven `chunked_processor.py` delegation pattern.
5. **NEW-1 (Dim 3)** — extract `useRestAPI.ts`'s shared request lifecycle into one private helper instead of 5 hand-duplicated ~45-line copies, before the next fix misses one.

---

## Findings

Findings are grouped MEDIUM → LOW, then by dimension. "Existing" (re-verified, not re-filed) findings are summarized in the **Re-Verified / Not Re-Filed** section at the end of each dimension's block rather than repeated here — see the linked issue for full detail.

### MEDIUM

#### NEW-2 (Dimension: Logic Duplication)
- **Location**: `auralis-web/backend/routers/artists.py:246-259` vs. `auralis/library/models/album.py:59-103`
- **Status**: NEW
- **Effort**: trivial-to-small
- **Description**: `get_artist()`'s detail endpoint hand-derives `track_count`/`total_duration` per nested album instead of calling `Album.to_dict()`, bypassing both its `_safe_collection()` detached-ORM guard and its SQL-aggregate optimization (#4777). Same pattern as the already-fixed #4909 sibling in this file's *list* endpoint — never mirrored to the *detail* endpoint.
- **Impact**: Not a live crash today (the eager-load option always populates the collection in production), but a future unit test mocking an `Artist`/`Album` without `.tracks` configured gets an unguarded crash here, unlike the fixed sibling.
- **Siblings**: `artists.py:197-212` (`get_artists`, fixed by #4909).
- **Related**: #4909 (CLOSED, the list-endpoint sibling), #4641 (the guard), #4777 (the SQL-aggregate optimization bypassed here).
- **Suggested Fix**: Replace the manual derivation with `album.to_dict()['track_count']`/`['total_duration']`, or a `serialize_album_summary()` helper in `serializers.py`.

#### TD5-1 (Dimension: Stub Implementations)
- **Location**: `auralis-web/backend/routers/processing_api.py:593-704` vs. `auralis/core/config/preset_profiles.py:53-283`
- **Status**: NEW (related to Existing: #4861)
- **Effort**: small
- **Description**: The live, registered `GET /api/processing/presets` route returns a fully hand-authored preset catalog whose numeric values (unitless ints like EQ `1`/`2`/`3`, compressor thresholds/ratios) do not correspond to what `create_preset_profiles()` — the module the mastering engine actually uses — applies for the same preset name. Every preset diverges in both units and value; the router also silently drops the engine's 6th preset (`"live"`), the narrower symptom #4861 tracks.
- **Impact**: No live UI currently reads this endpoint's numbers, so today's blast radius is documentation-only (though it is `response_model`-typed and appears in OpenAPI docs) — but nothing would catch the divergence if a future consumer trusted it, since the two payloads share no source and no test compares them.
- **Siblings**: #4861 (missing 6th preset, same root cause).
- **Related**: #3895 (separate camelCase/snake_case naming finding on the same endpoint).
- **Suggested Fix**: Build the response from `create_preset_profiles()` directly, or delete the endpoint entirely if no consumer is expected and let `/sync-contracts` catch its absence.

#### TD5-2 (Dimension: Stub Implementations)
- **Location**: `auralis/dsp/utils/adaptive.py:73-102` (`calculate_loudness_units()`), called from 6 files across `auralis/core/processing/` and `auralis/core/analysis/content_analyzer.py`
- **Status**: NEW
- **Effort**: medium
- **Description**: `calculate_loudness_units()`'s own docstring says it is a "simplified... approximation of LUFS" doing no K-weighting or gating. It is not advisory — it runs on the hot path of every adaptive/continuous-mode pass, directly driving `loudness_coordinate` (a tanh-normalized value that modulates real compression/expansion decisions per the continuous-parameter-space design). A genuinely BS.1770-4-compliant `LoudnessMeter` class already exists in the same codebase (`auralis/analysis/loudness_meter.py`) but is used only for narrower target-window measurement.
- **Impact**: RMS-without-gating vs. gated K-weighted loudness can diverge by several LU on dynamic-range-heavy content (the same magnitude the analogous, already-fixed Rust-side #4123 measured) — moving a real gain-affecting decision for reasons that don't reflect actual perceived loudness. The correctness angle belongs to `/audit-engine`; this audit's remit is the admitted-stub-on-a-hot-path shape.
- **Siblings**: TD5-3 (same "simplified" pattern, but advisory-only, correctly not promoted).
- **Related**: CLOSED #4123 (the analogous Rust-side divergence, which itself names `LoudnessMeter` as the reference implementation).
- **Suggested Fix**: Swap hot-path call sites to `LoudnessMeter` (a mechanical single-shot adapter over its block-based API), re-tuning the empirical tanh-curve constants against real LUFS afterward — or, if the RMS approximation is a deliberate speed/accuracy trade-off, document it as such instead of as an acknowledged gap.

#### DIM7-05 (Dimension: Stale Documentation) — Regression of #4401
- **Location**: `CLAUDE.md:99,164`; `.claude/commands/_audit-common.md:21,56`
- **Status**: Regression of #4401 (closed 2026-07-12, same category); related to open #4982
- **Effort**: trivial
- **Description**: `python scripts/check_doc_counts.py` — which CLAUDE.md itself instructs readers to run before trusting these numbers — now disagrees with both files: analysis-module files documented as 57, live 55; test files documented as 559, live 574; test functions documented as 6,474, live 6,514. Router count (20) and docs topic-dirs (18) still match. Both files agree with each other but both are stale against the tree; the test-count drift accumulated in a single day between the last two syncs.
- **Impact**: A reader or audit agent citing these counts to sanity-check e.g. a pytest collection count gets numbers off by up to 40, in a repo whose own audit tooling explicitly warns against trusting stale structural counts.
- **Siblings**: This is the dual-maintenance hazard CLAUDE.md's own prose already calls out — except here both copies drifted *together* (neither was updated), a failure mode the existing warning doesn't cover.
- **Related**: #4401 (closed, same category, different numbers), #4982 (the dual-maintenance tracking issue).
- **Suggested Fix**: Re-run `check_doc_counts.py` and paste its output into both files in the same commit. Given the metric moved by 40 in a single day, consider widening #4982 to a CI check with a loose tolerance band rather than relying on manual re-sync before every audit.

#### TD8-10 (Dimension: Backwards-Compat Cruft)
- **Location**: `auralis/dsp/utils/stereo.py:113-150`, called from `auralis/core/stages/stereo_expansion.py:102-106`
- **Status**: NEW
- **Effort**: small
- **Description**: `adjust_stereo_width_multiband()`'s docstring labels `original_width`/`bass_content` as "Unused (kept for API compatibility)" — language implying a legacy caller still needs them. In fact there is exactly one caller, and it is not legacy: it computes real per-chunk values (`current_width`, `bass_pct`) specifically to pass in, and the callee drops both on the floor. This is the inverse of ordinary compat cruft — a live caller believes the inputs matter; the callee's docstring says they never did.
- **Impact**: The "API compatibility" framing actively misleads triage into thinking the params are untouchable, when the real situation is one live caller computing values that never influence DSP output. Whether the widening *should* vary with content is a correctness question for `/audit-engine`.
- **Related**: Flag to `/audit-engine` — should these params modulate the widening per the function's own "frequency-appropriate widening" design intent, or is the caller's computation the actual dead code?
- **Suggested Fix**: Either delete both parameters and the caller's now-pointless computations, or wire them into the widening curve and drop the misleading docstring language.

### LOW

*(41 findings. Grouped by dimension; full evidence/suggested-fix detail preserved from each dimension's working file — see the per-finding IDs below for cross-reference.)*

#### Dimension 2 — Dead Code & Unused Surface (20 findings, all LOW, all NEW)

| ID | Location | Summary |
|---|---|---|
| D2-1 | `auralis/utils/checker.py:80-100`, `auralis/io/unified_loader.py:319-321` | Two divergently-implemented `is_audio_file()` functions, both dead outside tests |
| D2-2 | `auralis/io/unified_loader.py:283-311` | `batch_load_info()`/`load_target()` test-only; sibling `load_reference()` confirmed live |
| D2-3 | `auralis/dsp/eq/curves.py`, `filters.py`, `auralis/core/simple_mastering.py` | 3 DSP "convenience factory" functions with zero non-test callers |
| D2-4 | `auralis/core/hybrid_processor_singleton.py:6,131-141` | `process_hybrid()` dead; docstring wrongly claims package re-export |
| D2-5 | `auralis/library/utils/artist_normalizer.py:183-196` | `is_same_artist()` zero callers, only self-referential doctests |
| D2-6 | `auralis-web/backend/security/path_security.py:303-320` | `sanitize_path_for_response()` zero callers; invariant enforced elsewhere |
| D2-7 | `auralis-web/backend/core/executors.py:94-108` | `get_stream_executor()`/`get_io_executor()` — test-introspection only, likely intentional |
| D2-8 | `auralis/core/analysis/content_analysis_facade.py:1-331` | Whole module zero production callers; a real MEDIUM concurrency bug (#4549) was fixed inside it anyway |
| D2-9 | `auralis-web/backend/core/encoding/atomic_io.py:82-88,141-160` | `cleanup_partial_files()` never wired into startup — orphaned `.part` files from crashes accumulate indefinitely |
| D2-10 | 4 files, see dim_2.md | 6 fresh unused imports (ruff F401) from this week's mixin-split refactors |
| D2-11 | `store/selectors/selectorPerformance.ts` + 4 more | Entire selector memoization/aggregation subsystem (~430 LOC) self-referential, never adopted |
| D2-12 | `store/slices/playerSlice.ts:504-513` | 7 dead streaming selectors |
| D2-13 | `store/slices/{cacheSlice,connectionSlice}.ts` | 2nd batch of dead selectors in the same 2 files #4395 already fixed once |
| D2-14 | `store/middleware/{errorTrackingMiddleware,loggerMiddleware}.ts` | Dead `categorizeError` export + dead `getDevToolsConfig()` |
| D2-15 | `services/artworkService.ts`, `services/playlistService.ts:254` | 4 zero-caller service functions (extract/download/delete artwork, clearPlaylist) |
| D2-16 | `services/fingerprint/FingerprintCache.ts:1-378` | 378-line module the code already admits is orphaned (since #4239), never filed |
| D2-17 | `design-system/animations/index.ts:1-258` | ~100% dead; app uses a different animation module instead |
| D2-18 | `design-system/primitives/{Modal,Stack,Toggle,Grid,LinearProgress}.tsx` | 4 more dead primitives beyond #5132 + correction: #5132's proposed "keeper" (`LinearProgress`) has itself gone dead |
| D2-19 | `types/domain.ts:339-409` | 7 zero-reference type-guard/formatting helpers |
| D2-20 | `types/ws/guards.ts:71-167` | 23 of 25 exported WS message-type guards unused |

Full evidence and suggested fixes for each: see `/tmp/audit/tech-debt/dim_2.md` content reproduced in the working notes (each finding above carries its own grep evidence, impact, and a concrete delete/wire-in suggestion in the original per-dimension write-up).

#### Dimension 3 — Logic Duplication (2 LOW; 1 MEDIUM already listed above)

- **NEW-1**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:111-381` — `get`/`post`/`put`/`patch`/`delete_` each hand-roll an identical ~45-line request lifecycle. 6 years of fixes (#2439/#2467/#2489/#3055/#4831/#4896) have each had to be hand-applied to all 5 copies. **Suggested fix**: extract a private `request<T>()` helper; no behavior change.
- **NEW-3**: `auralis/library/repositories/fingerprint_similarity_mixin.py` — 3 of 6 methods still hand-roll `get_session()`/try/finally after the file's other 3 methods (and the rest of the repo layer, per #4604) migrated to `_session_scope()`. **Suggested fix**: convert the 3 remaining methods; no resource leak today, purely change-cost.

#### Dimension 4 — Magic Numbers (1 LOW)

- **MN-1**: `auralis-web/backend/services/library_auto_scanner.py:288` and `auralis-web/backend/routers/library_scan.py:164` both hardcode an identical bare `5.0`s scan-stop grace-period timeout — the same duplication shape already fixed once for the stream-semaphore timeout (#4930), in a different subsystem that fix didn't touch. **Suggested fix**: promote to a named, env-overridable constant (e.g. `SCAN_STOP_GRACE_SECONDS`).

#### Dimension 5 — Stub Implementations (2 LOW; 2 MEDIUM already listed above)

- **TD5-3**: `DynamicRangeAnalyzer._calculate_dr_value()` — a self-documented "simplified" DR calculation, but explicitly advisory-only (never selects a processing path or changes output) — correctly not promoted.
- **TD5-4**: `AnalysisExtractor._derive_mastering_targets()` — a genuine self-admitted "next phase" stub, but the whole class has zero production callers, so this is primarily a Dimension 2 concern flagged here for completeness.

#### Dimension 6 — Test Hygiene (3 LOW)

- **TD6-A**: `scripts/check_weak_assertions.py` (added 3 days ago by closed #5154) is never invoked by CI, pre-commit, or Makefile — only a soft pytest warning exists. Identical failure shape to already-fixed #5091. **Suggested fix**: wire it into `backend-tests.yml` as a required step, same pattern #5091 already proved.
- **TD6-B**: 28 print-only, zero-assertion test functions — an exact residue #5154 itself found and explicitly declined to fix (deferring to closed #4246, which never covered this superset). Two are named for resource-leak invariants (`test_no_connection_leaks`, `test_database_connections_released`) yet assert nothing. **Suggested fix**: file one issue for the 23 collected offenders; prioritize the leak-named tests first.
- **TD6-C**: A permanent skip in `test_boundary_exact_conditions.py:362-367` cites closed #4548 as though it still tracks an `AudioPlayer`-API rewrite — but #4548's actual scope never included that rewrite, only a hygiene bullet satisfied by adding the citation itself. **Suggested fix**: file a small successor issue and repoint the skip reason, or delete the test if the coverage is judged not worth rebuilding.

#### Dimension 7 — Stale Documentation (4 LOW)

- **DIM7-01**: `stream_prefetch.py` stale across 6 `.claude/` files (deleted #3879, same-day regression).
- **DIM7-02**: `personal_preferences.py` stale in `dsp-specialist.md` and `_audit-common.md` (deleted #4592).
- **DIM7-03**: `services/learning_system.py` stale in a dated 2026-02-21 migration-plan doc (deleted #4750).
- **DIM7-04**: `streaming-mse.test.tsx` stale in 2 docs, one of which (`PRESET_SWITCHING_LIMITATION.md`) uses the deleted file's own header comment as its evidentiary citation (deleted #4399).

All 4 verified as legitimate dead-code deletions (not renames) — fix is to de-backtick/reword, not redirect.

#### Dimension 8 — Backwards-Compat Cruft (4 LOW; 1 MEDIUM already listed above)

- **TD8-6**: `useKeyboardShortcuts.ts` ships a whole second "V1 config-based" API surface with zero production callers (the sole call site uses the V2 array form); the V1 surface is exercised only by its own test file. **Suggested fix**: delete the config-object branch entirely.
- **TD8-7**: `queue_service.py` re-exports `AudioPlayerWithQueue`/`QueueManager` "for backwards compatibility" — nothing imports either name from there.
- **TD8-8**: `PlayerCallbacksMixin.get_playback_info()`'s "backward compatibility" flattening serves a whole callback-registration mechanism (`add_callback`/`_notify_callbacks`) with zero production registrants in `auralis-web/backend` — reachable only from tests.
- **TD8-9**: `types/domain.ts`'s `formatDuration` re-export "for backwards compatibility" — every one of ~20 real consumers imports directly from `@/utils/timeFormat` instead.

#### Dimension 9 — File/Function/Module Complexity (3 LOW NEW; 1 LOW Regression already listed in Top 5)

- **TD9-1**: `config/startup.py` (1132 LOC) — now the single largest file in the codebase; #4671 correctly decomposed a 439-line nested function into ~20 named helpers but left them all in one file. *(Also a Top-5 Medium Investment above.)*
- **TD9-9**: `cache/manager.py` (713 LOC) — bolts an unrelated mastering-recommendation cache onto the chunk-cache class; clean, low-risk split axis (5 contiguous, non-interleaved method clusters).
- **TD9-10**: `hooks/shared/useReduxState.ts` (461 LOC, 28 `useCallback`s) — bundles 5 unrelated Redux domains (player/queue/cache/connection/app) in one hook file.
- **TD9-7** (Regression of #4260): `services/queue_service.py` grew 695→747 LOC after being marked fixed; the "persistence from live mutation" half of #4260's ask was never done. *(Also a Top-5 Medium Investment above.)*

Additional re-verified-but-still-open items from this dimension (not new, listed for completeness): TD9-2/3/4 (6 router files where #5166's function-complexity half is fixed but file-size half isn't — #5166 should be re-scoped), TD9-5 (`hybrid_processor.py`'s #4266 fix never relocated the flagged function), TD9-6 (`chunked_processor.py` a 9-line near-miss on the #4673 acceptance line), TD9-8 (`similarity.py` still 72% over budget after a partial split).

#### Dimension 10 — Audit-Finding Rot (1 LOW)

- **TD10-B**: `audit-tech-debt.md`'s hardcoded `sample_rate=44100` diff-base ("43") has no ratchet/CI backing and has already drifted twice (48→43→30/20) with no report recording the intermediate step. **Suggested fix**: either drop the hardcoded number (recompute and diff against the previous report each run, matching how the LOC census is already handled) or track it in a small JSON file the way `pytest-baseline.json` is tracked.

---

## Re-Verified / Not Re-Filed (existing findings confirmed still accurate)

25 previously-tracked findings across 6 dimensions were independently re-derived this cycle and confirmed either still fixed-and-holding (no regression) or still open-and-accurate (no new action). Full detail lives in each dimension's working notes; headline items:

- **Dimension 3**: 8 of 8 tracked duplication findings (#4605, #4604, #4902, #4909, #5028, #4761, #4300, the 07-29 WAV-encoder fix) all confirmed fixed and holding — no regressions in this dimension.
- **Dimension 4**: 8 of 8 tracked magic-number findings confirmed fixed and holding, plus one bookkeeping note: #4610 is still open on GitHub but its underlying file (`auralis/core/config.py`) was already deleted by #4918 — worth closing.
- **Dimension 6**: 5 of 5 tracked test-hygiene findings (#5154, #5155, #5156, #5157, #5179/#5186) confirmed genuinely fixed, not just relabeled.
- **Dimension 8**: 4 of 5 tracked findings (#5162, #5163, #5164, #5165) confirmed still open and accurate (one, #5162, drifted up from 118 to 121 references); a 5th (#4312) confirmed genuinely closed and fixed.
- **Dimension 9**: 6 god-file-split issues re-measured live per #4673's rule rather than trusting closed/open state — #4245/#4249/#4254 confirmed genuinely re-closed after reopening; #4250 confirmed correctly still open; #4270/similarity.py confirmed a genuine partial fix still 72% over budget.
- **Dimension 10**: `pytest-baseline.json` (216) and `test-baseline.json` (111/3538) both confirmed exactly matching their tracked files — no drift.

---

## Deferred

- **TD5-2**'s full remediation (swap the mastering pipeline's loudness measurement to `LoudnessMeter`) needs re-tuning the empirical tanh-curve constants against real LUFS values — this is correctness-adjacent work best scoped as a dedicated `/audit-engine`-adjacent follow-up rather than a mechanical tech-debt fix.
- **TD8-10**'s ultimate resolution (should `original_width`/`bass_content` modulate the stereo-widening curve) is gated on a DSP-design decision — flagged to `/audit-engine`, not resolved here.
- **#5166** (router-factory complexity) should be re-scoped before further action: its function-complexity claim is fixed across 6 files; only the file-size half (tracked here as TD9-2/3/4) remains open.
- **#5167** (stale god-file-closure anecdote) should be resolved together with its previously-unknown sibling location in `fix-issue.md:131` (TD10-A) — do both in the same pass.

---

*Generated 2026-08-23 by `/audit-tech-debt` (10 dimension subagents, `--depth deep`, no `--limit`).*
