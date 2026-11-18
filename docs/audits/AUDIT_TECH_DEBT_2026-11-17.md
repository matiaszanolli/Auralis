# Tech-Debt Audit — 2026-11-17

Fresh audit of the current tree at `7029fa50a` (master), run with the ten dimensions of `.claude/commands/audit-tech-debt.md`, `--depth deep`, no `--limit`. Prior reports were not consulted; the previous tech-debt report (2026-10-22) appears only as the Baseline Snapshot comparison column, taken from its Baseline Snapshot table. No GitHub issues were created.

## Executive Summary

**123 findings after merging cross-dimension duplicates: 0 CRITICAL, 0 HIGH, 3 MEDIUM, 120 LOW.** (127 raw findings from the dimension agents; 4 merged, see "Merge log".)

| Dim | Name | Findings | Notes |
|---|---|---|---|
| 1 | Stale Markers | 6 (6 LOW) | Marker census healthy; all 6 findings are untracked prose deferrals or mis-pointed trackers. |
| 2 | Dead Code & Unused Surface | 14 (14 LOW) | Dominated by regrown unused imports after the #6269-#6273 splits and dead production surface only tests reach. |
| 3 | Logic Duplication | 20 (2 MEDIUM+18 LOW) | 2 MEDIUM: the guarded copy of two helpers is not the one the pipeline uses. |
| 4 | Magic Numbers & Hardcoded Constants | 17 (17 LOW) | Chunk geometry is clean. Debt is peak-ceiling / sample-rate / timing constants with no single home. |
| 5 | Stub & Placeholder Implementations | 3 (3 LOW) | No reachable `NotImplementedError`/`pass` stubs. Debt is API fields and parameters accepted but not applied. |
| 6 | Test Hygiene | 13 (1 MEDIUM+12 LOW) | 1 MEDIUM: guard for three closed HIGH frontend bugs is baselined-red or vacuous. |
| 7 | Stale Documentation & Comments | 19 (19 LOW) | Gate-visible docs are clean (strict 0, ratchet 120/120); debt is symbol-level and prose rot the gate cannot see. |
| 8 | Backwards-Compat Cruft & No-Variants | 15 (15 LOW) | Breadcrumb ratchet has a too-narrow regex; dead duplicate UI; playback settings with no consumer. |
| 9 | File / Function / Module Complexity | 14 (14 LOW) | Python files >300 LOC down 33 -> 9; ratchet file is missing most split targets. |
| 10 | Audit-Finding Rot | 2 (2 LOW) | Skill/agent files are clean on closed-issue prose and dimension counts. |
| | **Total** | **123** | |

**Direction vs 2026-10-22.** The mechanical census improved: Python files over 300 LOC fell 33 -> 9 and the shipped frontend over-300 list is 1 file; nesting over 4 is zero in Python and the frontend; `NotImplementedError` is 0; the one genuine src marker cites an OPEN issue and `tests/` has 0. The new debt is split-refactor fallout (#6269-#6273): unused imports, re-exports kept for tests, source comments naming moved symbols, and closed split targets absent from `loc-ceilings.json`. There is no HIGH finding: every DSP scaffolding pair compared by Dim 3 was at `.copy()` / sample-count parity, and no magic constant would truncate audio under documented use.

**Three MEDIUMs, all by promotion rule:** TD3-01 (the NaN/Inf-safe smooth-unit curve exists in one of nine copies), TD3-02 (the silence-guarded crest helper is not the one the pipeline calls; inline copies return NaN on an all-zero buffer, reproduced), TD6-01 (regression guards for closed HIGH #2346/#2340/#2342 are baselined-red or vacuous). TD3-02 has a correctness flavour: route to `/audit-engine` as Related.

## Baseline Snapshot

Captured 2026-11-17 at `7029fa50a` with the Phase 1 greps in `.claude/commands/audit-tech-debt.md`. Labels follow the #4564 metric notes. Comparison column is the 2026-10-22 report.

| Metric | 2026-11-17 | 2026-10-22 | Read it as |
|---|---|---|---|
| markers, genuine (src) | 1 | 3 | `TODO(#5484)` at `security_headers.py:124`, OPEN. The two others (#5858, #5537) are gone. |
| markers, genuine (tests/) | 0 | 1 | `TODO(#5851)` is gone. None cites a closed issue. |
| markers, raw (pre-filter) | 4 | 4 | Diagnostic only; the gap is `XXXXXXXX` placeholders. |
| prose deferrals (non-test) | 11 | 9 | 9 are ordinary prose; 1 is a real untracked deferral (TD1-01). |
| NotImplementedError | 0 | 12 | The #6235 class-level-annotation idiom landed; reads 0 as the metric note says. |
| type: ignore (py) | 48 | 44 | `mypy --warn-unused-ignores` reports none unused (Dim 2). |
| @ts-ignore/@ts-expect-error | 30 | 10 | All 30 are in specs/mocks; 0 in shipped code. The rise is in test files; composition not itemised here. |
| 'any' non-test (ts) | 0 | 3 | The three prior hits are gone. |
| 'any' raw incl. tests (ts) | 515 | 493 | Trend continuity only. |
| skipped tests (py) | 31 | 31 | 29 real `@pytest.mark` decorators at statement start (0 unconditional skips, 39 `skipif` gates, 2 strict xfails per Dim 6); the regex also matches prose. |
| skipped tests (ts) | 0 | 3 (0 real) | The #6279 anchor works. |
| py files >300 LOC | 9 | 33 | All 9 listed in TD9-01..09; none is in `loc-ceilings.json`. |
| ts/tsx files >300 LOC | 73 | 69 | 1 shipped (`CozyLibraryView.tsx`, 335, TD9-10; `AudioPlaybackEngine.ts` is no longer over) and 72 test files. |
| allow(dead_code) (rust) | 0 | 0 | Clean. |
| sample_rate=44100 defaults | 20 | 20 | **Drift indicator, not a debt count** (#4924). Unchanged at 20. Because the figure is flat, no site is new by count; TD4-03 records the unnamed constant behind them. |

Path-reference gate (`_audit-validate.sh`): exit 0, strict 0 stale, ratchet 120 vs baseline 120 (new 0, fixed 0). `check_doc_counts.py`: all counts current.

Marker census (every genuine hit):

| Location | Cited issue | State |
|---|---|---|
| `auralis-web/backend/config/middleware/security_headers.py:124` | #5484 | OPEN |

## Top 10 Quick Wins

1. **TD2-01 / TD2-02 / TD2-03** — Delete ~46 unused imports (+ 9 in `unified_loader.py`), fix the false `noqa` comments, repoint four vacuous test patches. Cheap and unblocks a ruff F401 CI gate so it stops regrowing (regression of #6209).
2. **TD1-02** — Re-point two comments in `job_config.py` from CLOSED #3490 to `TODO(#5098)`.
3. **TD1-01** — Turn the "no tracking issue yet" air-band deferral into a decision or a `TODO(#NNNN)`.
4. **TD9-11** — Run `python scripts/check_loc_ratchet.py --update` flow to add the closed split targets (and lower `target_fingerprint_adjustments.py` to 144), so TD9-02/07/08 cannot regrow silently.
5. **TD7-04** — Repair the mangled docstring, header and "crossfade" comment in `chunk_boundaries.py` (the chunk-geometry authority) and four sibling comments.
6. **TD2-14** — Remove tracked repo-root junk (`100`, `coverage.json`, `index.html`, `tools/alembic.ini`).
7. **TD3-04 / TD3-07 / TD3-19** — Extract the shared mode-dispatch tail; replace 7 inline channel averages with `to_mono()`; import the default preset instead of 10 bare `'adaptive'` literals.
8. **TD4-04 / TD4-05 / TD4-06 / TD4-07** — Derive chunk constants and the second `ceil` formula inside `chunk_boundaries.py`; name the 0.1 s silence fallback and frame-byte budget.
9. **TD6-02 / TD6-05 / TD6-06** — Delete the permanently red superseded 2166 test, stop two regression tests opening the real `~/.auralis/library.db`, make the strict-xfail tests assert again.
10. **TD7-10 / TD7-12 / TD10-01** — Delete `.github/INTEGRATION_GUIDE.md`, fix the ARCHITECTURE.md example that calls a nonexistent method, fix `trace-flow.md` anchors.

## Top 5 Medium Investments

1. **TD3-01 + TD3-02 (MEDIUM)** — Consolidate the nine hand-written `0.5 + 0.5*tanh(...)` curves onto one NaN-safe helper (`auralis/core/utils/smooth_curves.py`) and route the 5+ peak/RMS/crest sites through `FullAudioMeasurement`, the guarded helper.
2. **TD6-01 + TD6-09 + TD6-03** — Repair the closed-HIGH frontend regression guards, build the Rust module in backend CI, and refresh the Principle 4 allow-list, so the baselines stop absorbing real signal.
3. **TD9-01..09 + TD9-12** — Split the nine Python files over 300 LOC (`seekable_source.py` 411 is the largest; `fingerprint_storage.py` already regrew) and the seven hooks left over 120 lines by #6275, adding each to `loc-ceilings.json` in the same commit.
4. **TD3-13 + TD3-14 + TD3-12** — Finish #6214: one look-ahead/gate/drain/send pump and one permit/handler skeleton for normal and enhanced streaming, plus a shared stream-task registration helper.
5. **TD5-01 + TD5-02** — Decide whether the processing-job API fields and four `ProcessingParameters` fields that no DSP stage reads are deleted or implemented, and stop serving them as live engine state.

## Merge log

- TD8-08 dropped: merged into TD5-03 (same `HybridProcessor.close()` no-op chain).
- TD10-02 dropped: merged into TD9-11 (same `loc-ceilings.json` slack on `target_fingerprint_adjustments.py`).
- TD5-05 dropped: merged into TD3-11 (same null-getter placeholder in the router `*_deps.py` holders).
- TD5-04 dropped: merged into TD8-04 (same `_`-renamed frontend props; the `isLoadingPlaylists` / `trackTitle` / `MediaCardArtwork.variant` / `useBatchActionsMenu.handleAction` / `SegmentedControl` / `_ThemeProvider` sites are added to its fix).
- TD1-02 and TD5-01 both cite CLOSED #3490 but are different defects (a mis-pointed comment vs. an API that ignores its fields); both kept.

## Findings

### HIGH (0)

None.

### MEDIUM (3)

#### Dimension 3: Logic Duplication

##### TD3-01: Logistic "smooth unit" curve hand-written 9 times; only one copy handles NaN/Inf
- **Severity**: MEDIUM (promotion: duplicated logic with divergent bug-fix history — #5505/#5534 fixed one copy only)
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/processing/continuous_space.py:15-31` (canonical `_smooth_unit`), copies at `auralis/core/mastering_process_chunk.py:43-52`, `auralis/core/processing/adaptive_mode.py:155-161`, `auralis/core/mastering_branches/continuous.py:164-166` and `:209-211`, `auralis/core/stages/bass_enhancement.py:76-79`, `auralis/core/mastering_notch_context.py:80-83` and `:98-101`
- **Status**: NEW (adjacent to closed #5505 / #5534, which fixed only `_smooth_unit`)
- **Age**: `_smooth_unit` d96e77291 2026-07-28; the inline copies are older
- **Effort**: small
- **Description**: `0.5 + 0.5 * tanh((x - center) / (2 * scale))` is the one S-curve every continuous-space coordinate uses. `continuous_space._smooth_unit` wraps it with the fix for NaN (maps to 0.5, #5505) and +/-Inf (saturates, #5534). Nine other sites re-spell the bare formula with no guard, so a NaN input propagates straight through `tanh` into the gain/intensity they feed. The corpus calibration constants are copied too: `13.4207 / 1.7884` (crest) and `-14.3887 / 2.7732` (LUFS) appear as literals in `mastering_process_chunk.py:45-48` and `adaptive_mode.py:155-161`, while `continuous_space.py:58-59` holds the crest pair as `_CREST_CENTER_DB/_CREST_SCALE_DB` (the LUFS pair has no named home at all). Re-calibrating the corpus means editing three files by hand.
- **Evidence**: `continuous_space.py:31` `return 0.5 + 0.5 * math.tanh((value - center) / (2.0 * scale))` behind the NaN/Inf branches; vs `adaptive_mode.py:155-160` `0.5 + 0.5 * np.tanh((source_lufs + 14.3887) / (2.0 * 2.7732))` and `0.5 + 0.5 * np.tanh((crest_factor_db - 13.4207) / (2.0 * 1.7884))` with no guard. Reproduced the trigger: on an all-zero buffer `amplitude_to_db(max|x|) - amplitude_to_db(rms)` is `-inf - -inf = nan`, so `crest_coordinate` is `nan` (see TD3-02).
- **Impact**: a NaN crest/LUFS (silent or near-silent chunk, empty window) turns `expansion_response` and `compression_amount` into NaN in `AdaptiveMode._apply_dynamics_processing`, the exact failure class #5505 closed for the continuous path. Re-tuning the calibration drifts between the offline CLI, AdaptiveMode and ContinuousMode.
- **Siblings**: the 9 sites above; also two other 0..1 ramp curves in the same family: `SmoothCurveUtilities.s_curve/ramp_to_s_curve` (cosine, `core/utils/smooth_curves.py:31,64`, no NaN handling) and `smooth_gate` (smoothstep, `core/processing/cross_dimensional_guard.py:27`).
- **Related**: real-bug angle (NaN reaching `AdaptiveMode` dynamics on silence) belongs to `audit-engine`; I could not confirm a live silent-chunk path because `HybridProcessor` short-circuits all-zero input before the mode runs, so treat as PLAUSIBLE.
- **Suggested Fix**: promote `_smooth_unit` to a public `smooth_unit(value, center, scale)` in `auralis/core/utils/smooth_curves.py` (next to `SmoothCurveUtilities`), add named `CREST_CENTER_DB/CREST_SCALE_DB/LUFS_CENTER/LUFS_SCALE` constants beside it, and call it from the 9 sites; keep `ContinuousSpaceMapper._CREST_*` as aliases of the shared constants.

##### TD3-02: Peak/RMS/crest measurement re-implemented in 5+ processing sites; the guarded helper is not used by the pipeline
- **Severity**: MEDIUM (promotion: one copy has the silence guard, the other copies still carry the NaN)
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/processing/base/normalization_step.py:51-66` and `:108-125` (identical `measure_before`/`measure_after` bodies), `auralis/core/processing/base/audio_measurement.py:20-43` (`AudioMeasurement`), `auralis/core/processing/base/full_audio_measurement.py:20-45` (`FullAudioMeasurement`), `auralis/core/processing/adaptive_normalization.py:55-59, 110-115, 121-126`, `auralis/core/processing/adaptive_mode.py:149-153`, `auralis/core/processing/continuous_dsp_ops.py:272-277`, `auralis/core/analysis/content_analyzer.py:177-184`
- **Status**: NEW (residue of closed #5785 "Level measurement ... re-implemented ~35 times"; that fix unified the dB conversion, not the peak+RMS+crest triple)
- **Age**: normalization_step measure_after b90598229 2026-01-02
- **Effort**: small
- **Description**: The same "peak = max|x|, rms = sqrt(mean(x^2)), crest = peak_db - rms_db" triple is computed four different ways: `NormalizationStep` (two copy-pasted methods returning a dict), `AudioMeasurement` (class), `FullAudioMeasurement` (class, + LUFS), and ~8 inline blocks. `dsp/utils/spectral.py:164 crest_factor()` is the fifth, and the only one with the silence guard (`if rms_value > 0 ... else 0.0`, used by `content_analyzer`, `feature_extractor`, `genre_classification`). The processing path uses the unguarded inline form.
- **Evidence**: `adaptive_mode.py:149-153` `crest_factor_db = current_peak_db - current_rms_db` after `amplitude_to_db(...)` with the default `silence_db=-inf`. Run on `np.zeros((1000,2), float32)`: `peak_db=-inf, rms_db=-inf, crest=nan`. `spectral.crest_factor` returns 0.0 for the same input.
- **Impact**: any silent window reaching these sites yields NaN crest (feeds TD3-01 sigmoid and `AdaptiveLoudnessControl.calculate_adaptive_gain`). Changing what "crest" means needs 8 edits.
- **Siblings**: ~19 more inline `np.sqrt(np.mean(x ** 2))` where `dsp.basic.rms` exists (`lowmid_transient_enhancer.py:156`, `ml/feature_extractor.py:97`, `dynamic_range.py:122,145`, `quality_assessors/utilities/estimation_ops.py:207`, `mastering_fingerprint.py:162`, `core/analysis/content_analyzer.py:274`, `reference_profile.py:81`, `phase_correlation.py:77,78,137,138,200,201`, `player/realtime/level_matcher.py:62,115`, `backend/core/level_manager.py:96`) and ~14 inline `20 * np.log10(...)` / `10 ** (x/20)` where `amplitude_to_db` / `db_to_amplitude` exist (`auto_master.py:202,205,210,249,250`, `compression_expansion.py:71,197,209,211`, `loudness_meter.py:187,200`, `estimation_ops.py:193,213`, `safety_limiter.py:42`, `mastering_chunk_assembly.py:212`, `continuous.py:214,274`, `level_transition.py:145,150,197`).
- **Related**: #5785 (closed), TD3-01. NaN-on-silence behaviour is a real-bug concern for `audit-engine`.
- **Suggested Fix**: make `FullAudioMeasurement(audio, sample_rate=None)` (it already exposes peak/rms/crest/lufs) the single measurement, build its crest from `crest_factor()`'s guarded form, delete `AudioMeasurement`'s duplicate arithmetic by delegating to it, rewrite `NormalizationStep.measure_before/after` as one private `_measure()`, and replace the inline triples in `adaptive_normalization.py`, `adaptive_mode.py`, `continuous_dsp_ops.py`, `content_analyzer.py` with it. Sweep the inline RMS/dB one-liners onto `dsp.basic.rms` and `dsp.utils.conversion`.

#### Dimension 6: Test Hygiene

##### TD6-01: Source-grep regression guards for three closed HIGH frontend bugs are baselined-red or vacuous
- **Severity**: MEDIUM (promotion: guard for closed HIGH issues #2346, #2340, #2342 is effectively disabled)
- **Dimension**: Test Hygiene
- **Location**: `tests/regression/test_frontend_hook_patterns.py:19-83`
- **Status**: NEW
- **Age**: `ebc760b3f` 2026-02-22
- **Effort**: small
- **Description**: The file "verifies" three fixed React-hook bugs by substring-grepping `.tsx`/`.ts` source. Three of its six tests are in `pytest-baseline.json` as known failures (`test_handlers_use_commands_prop`, `test_initial_fetch_exists`, `test_primitive_extraction_from_options`) so CI tolerates them. The first reads `components/shared/PlayerControls.tsx`, which no longer exists (FileNotFoundError). The second asserts `"fetchInitialQueue" in source or "useEffect" in source` on `usePlaybackQueue.ts`, but the hook was split and neither string is there any more (it lives in `useQueueFetch.ts`). The other three are vacuous: `test_no_state_in_fetch_deps` loops looking for a `fetchInitialQueue ... useEffect` line that no longer exists, so it asserts nothing; `test_body_stored_in_ref` accepts any `useRef`.
- **Evidence**: `ls components/shared/PlayerControls.tsx` -> no such file; `grep -c fetchInitialQueue hooks/player/usePlaybackQueue.ts` -> 0, `grep -c useEffect` -> 0; baseline entries `tests.regression.test_frontend_hook_patterns.*` x3.
- **Impact**: #2346/#2340/#2342 were HIGH (stale closure in auto-advance, infinite fetch loop). The Python guard that names them cannot detect their return. Behavioural vitest coverage exists (`usePlaybackQueue.test.ts`, `useStandardizedAPI.test.tsx`, `useQueueFetch*.test.ts`) but nothing ties it to these bugs, and a green CI row says "guarded".
- **Siblings**: `tests/regression/test_no_raw_sql_leaks.py` (TD6-03), `tests/test_fix_2166_double_windowing.py` (TD6-02) — same "regression test baselined red" shape.
- **Related**: frontend regression policy belongs to `/audit-frontend`.
- **Suggested Fix**: Delete the file (source-text greps are the wrong tool for hook-loop bugs). Add a vitest in `usePlaybackQueue.test.ts` asserting the initial fetch runs once across re-renders with an unstable `api` object, and one in `useStandardizedAPI.test.tsx` for inline option objects; remove the 3 baseline entries.

### LOW (120)

#### Dimension 1: Stale Markers

##### TD1-01: EQ air-band deferral says "no tracking issue yet" in a code comment
- **Severity**: LOW
- **Dimension**: Stale Markers (prose deferral)
- **Location**: `auralis/core/processing/parameter_generator_eq.py:66-73`
- **Status**: NEW
- **Age**: `a0a2b6565b`, 2026-11-08 (9 days; reported because the comment itself states it is untracked)
- **Effort**: trivial
- **Description**: `high_shelf_gain` is pinned to `0.0` because the fingerprint analyses at 22.05 kHz, so its 8-20 kHz "air" band stops at 11 kHz. The comment defers the real fix ("Revisit once the fingerprint measures above 11 kHz") and explicitly says there is no tracking issue. CLAUDE.md principle 5 requires a deferral to be `TODO(#NNNN):` with a real issue; this one is invisible to the marker census (it is why `markers, genuine` reads 1 while a live deferral sits in the DSP parameter path).
- **Evidence**:
  ```python
  # No correction is derived from the air share. The fingerprint analyses at
  # 22.05 kHz, so its 8-20 kHz band stops at 11 kHz ...
  # Revisit once the fingerprint measures above 11 kHz (no tracking issue yet).
  'high_shelf_gain': 0.0,
  ```
  `grep` of issues.json for `11 kHz|22.05|air|high.shelf|nyquist` finds only closed, unrelated issues (#4862 BAND_RANGES_HZ doc mismatch, #3678 THD Nyquist bin). Related live plumbing that still carries the zeroed band: `_BAND_AUTHORITY_DB['high_shelf_gain']` (line 80), the clip at line 151, `continuous_dsp_ops.py:70/83`.
- **Impact**: A known mastering limitation (no air-band EQ correction on any track) has no owner and will not surface in any marker sweep or `/audit-tech-debt` census.
- **Siblings**: none found (the other EQ bands carry no deferral).
- **Related**: owning audit `/audit-engine` if the air band is judged a mastering-quality gap rather than a settled design decision.
- **Suggested Fix**: Decide which it is. If it is a settled decision (the analysis rate is fixed by design), reword the last comment line to say so and drop "Revisit". If it is a real deferral, file the issue and turn the line into `# TODO(#NNNN): re-derive the air-band correction once the fingerprint measures above 11 kHz.`

##### TD1-02: `job_config.py` cites CLOSED #3490 as the tracker for a deferral whose live tracker is OPEN #5098
- **Severity**: LOW
- **Dimension**: Stale Markers (prose deferral citing a closed issue)
- **Location**: `auralis-web/backend/core/job_config.py:50-52`, `:64-65`
- **Status**: NEW
- **Age**: `de35981be3`, 2026-08-22 (the #3490 wording dates from 2026-05-26)
- **Effort**: trivial
- **Description**: Two comments in `create_processor_config` say the EQ/dynamics/level_matching/genre_override job settings are ignored "until those readers exist (tracked as the wire-up follow-up for #3490)" and "see #3490 follow-up". #3490 is CLOSED (the issue was resolved by logging-and-ignoring); the actual wire-up work is **OPEN #5098** ("Wire up EQ/dynamics/level-matching/genre-override into HybridProcessor's offline pipeline (follow-up to #3490)"). Neither comment names #5098, and neither is in `TODO(#NNNN)` form, so a marker sweep cannot link the live deferral to its issue. This is a code path reachable from the shipped `routers/processing_*` job routes.
- **Evidence**: `jq` on issues.json: `3490 CLOSED`, `5098 OPEN`. `grep -rn "5098" auralis auralis-web` returns no code reference.
- **Impact**: A reader following the comment lands on a closed issue and concludes the work was done or abandoned; the genuine OPEN tracker is undiscoverable from the code.
- **Siblings**: none.
- **Related**: #5098 (OPEN), #5060 (CLOSED, the "silently ignored" fix this logging came from).
- **Suggested Fix**: Replace both references with `# TODO(#5098): ...` (marker form, citing the OPEN issue) and drop the #3490 pointers.

##### TD1-03: `pagination.py` docstring defers an adoption that has mostly happened
- **Severity**: LOW
- **Dimension**: Stale Markers (untracked "eventually" deferral, stale)
- **Location**: `auralis-web/backend/routers/pagination.py:26-32`
- **Status**: NEW
- **Age**: `9e0398aaa2`, 2026-08-07
- **Effort**: trivial
- **Description**: The `has_more` docstring says `artists.py::ArtistsListResponse` is "the per-router-model pattern the other 4 endpoints should eventually adopt". #5499 (CLOSED 2026-09-16) since moved tracks, albums and artists onto the shared `PaginatedResponse` envelope in `schemas/library.py` (`TrackListResponse`, `AlbumListResponse`, `ArtistsListResponse` all subclass it). The "other 4" is wrong, the "eventually" has no issue, and the pattern pointed to is no longer a per-router one. What remains is `PlaylistListResponse` in `routers/playlists_models.py:55`, which still re-declares `total` / `limit` / `offset` / `has_more` by hand.
- **Evidence**: `grep -rn "class .*(List|Paginated).*Response" auralis-web/backend` -> `PaginatedResponse(BaseModel)` + three subclasses; `PlaylistListResponse(BaseModel)` with the four fields duplicated.
- **Impact**: A stale, untracked "should eventually" in the one file meant to be the single source of truth for the has_more rule.
- **Siblings**: `PlaylistListResponse` (the one remaining hand-rolled envelope). `JobListResponse` is a different shape (`jobs` + `total` only) and is not a sibling.
- **Related**: #5499 (CLOSED), #5054 (CLOSED); the PlaylistListResponse duplication belongs to Dim 3 (Logic Duplication).
- **Suggested Fix**: Delete the "other 4 endpoints should eventually adopt" clause (rewrite the docstring to point at `PaginatedResponse`). Optionally make `PlaylistListResponse` subclass `PaginatedResponse` (response keys unchanged, so no frontend contract change) and then the whole paragraph can go.

##### TD1-04: Test docstring defers "splitting the try/except three ways" with no issue; the coupled try/except is still in `routes.py`
- **Severity**: LOW
- **Dimension**: Stale Markers (untracked deferral in tests)
- **Location**: `tests/backend/test_routes_optional_router_import_failure.py:238-244`; production side `auralis-web/backend/config/routes.py:251-269`
- **Status**: NEW
- **Age**: `ff9e1ddcc9`, 2026-08-06
- **Effort**: small (the split itself) / trivial (file the issue)
- **Description**: `test_a_broken_import_silently_drops_all_three_routers` pins that `similarity`, `similarity_graph` and `fingerprint_queue` share ONE `try/except`, so a broken import in any one drops all three. Its docstring says "splitting the try/except three ways is a deliberate follow-up, not done here (see #4717's Proposed Fix)". #4717 is CLOSED (it was a test-coverage issue), and the follow-up has no issue of its own. `routes.py` still has the single `try:` at line 251 covering all three factories, so the debt is live.
- **Evidence**:
  ```python
  # routes.py:251-269
  try:
      from routers.similarity import create_similarity_router
      from routers.similarity_graph import create_similarity_graph_router
      from routers.fingerprint_queue import create_fingerprint_queue_router
      ...
  except Exception as e:
      logger.warning(f"... Failed to register similarity router family: {e}", exc_info=True)
  ```
  jq: `4717 CLOSED`; no issue title matches "three routers" / "try/except split".
- **Impact**: The test deliberately locks in all-or-nothing router loss, and the only pointer to the planned fix is a closed issue. Nobody will find it by sweep.
- **Siblings**: the other optional-router blocks in `routes.py` (lines ~75 and ~235, `cache_streamlined`, `processing_api`) are single-router so do not share the problem.
- **Related**: `/audit-backend` owns whether the all-or-nothing behaviour is a defect.
- **Suggested Fix**: Either do the split (one `try` per factory, then flip the test to assert only the broken router is dropped), or file the issue and change the docstring to `# TODO(#NNNN): split the shared try/except in setup_routers; this test pins the current all-or-nothing behaviour.`

##### TD1-05: Speculative "Future ... components will be added here" comments in two component barrels
- **Severity**: LOW
- **Dimension**: Stale Markers (untracked, speculative deferral)
- **Location**: `auralis-web/frontend/src/components/shared/ui/media/index.ts:10`, `auralis-web/frontend/src/components/shared/ui/feedback/index.ts:11`
- **Status**: NEW
- **Age**: `2d33253d0`, 2025-11-23 (~12 months)
- **Effort**: trivial
- **Description**: Both barrels end with a placeholder promise ("Future media components will be added here" / "Future feedback components will be added here"). There is no issue, no planned component, and a year has passed. The feedback barrel also carries a second breadcrumb (`// Toast has been moved to @/components/shared/Toast`) that `scripts/check_breadcrumbs.py` style rules discourage.
- **Evidence**: `git log -S"Future media components"` -> single introduction commit 2025-11-23; neither line is referenced by any issue.
- **Impact**: Noise only; it reads as pending work that does not exist.
- **Siblings**: `grep -rn "Future .* will be added" auralis-web/frontend/src` finds exactly these two.
- **Related**: none.
- **Suggested Fix**: Delete the "Future ..." lines (and the moved-Toast breadcrumb).

##### TD1-06: "Keeping this test simple with just WAV for now" in an e2e workflow test
- **Severity**: LOW
- **Dimension**: Stale Markers (untracked "for now" in tests)
- **Location**: `tests/integration/test_e2e_workflows.py:403-404`
- **Status**: NEW
- **Age**: `295624b5c9`, 2025-11-07 (~12 months)
- **Effort**: trivial
- **Description**: The test only exercises WAV with a note that FLAC/MP3 "would require those encoders installed ... for now". Format coverage is elsewhere (loader/format tests), so the "for now" has been a standing non-deferral for a year and has no issue.
- **Evidence**: comment text above; no issue match for "e2e format".
- **Impact**: Negligible; an old prose deferral that no sweep can classify as done or pending.
- **Siblings**: none.
- **Related**: Dim 6 (Test Hygiene) if the format coverage gap is judged real.
- **Suggested Fix**: Reword to a plain scope statement ("This workflow test uses WAV only; format coverage lives in tests/auralis/io/") or delete the comment.

#### Dimension 2: Dead Code & Unused Surface

##### TD2-01: 21 unused imports in the engine (`auralis/`), regrown after the #6269-#6273 splits
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/core/processing/adaptive_mode.py:11,18,21,26-29`; `auralis/core/processing/adaptive_normalization.py:12,17,19`; `auralis/core/processing/base/full_audio_measurement.py:13`; `.../base/normalization_step.py:13`; `.../base/stereo_width_processor.py:14`; `auralis/core/processing/eq_processor.py:15`; `auralis/core/recording_type_detector.py:33`; `auralis/core/recording_type_parameters.py:13,17`; `auralis/core/utils/fingerprint_unpacker.py:16`; `auralis/io/audio_probe.py:15`
- **Status**: Regression of #6209 (closed 2026-10-25, `0a1b87aaf`, "five unused imports the god-file splits left behind"; same class, regrown). Also same class as closed #5781.
- **Age**: introduced by `66931f63c` (2026-10-24 split), `c41a92854` (#6213, 2026-10-25, left `db_to_amplitude` unused in 4 files), `4250aefad` (#6258).
- **Effort**: trivial
- **Description**: ruff F401 reports 21 names imported and never read in the engine tree: `db_to_amplitude` (5 files, left behind when #6213 made it "the one inverse"), `AdaptiveLoudnessControl`, `validate_audio_finite`, `NormalizationStep`, `PeakNormalizer`, `ProcessingLogger`, `SafetyLimiter` (all in `adaptive_mode.py`), `SILENCE_FLOOR_DB`, `info`, `hann`, `dataclass`, `SmoothCurveUtilities`, `RecordingType`, `Any`, `os`. None is re-exported (greps for importers through these modules found none; no `noqa`).
- **Evidence**: `PYENV_VERSION=3.11.11 ruff check --no-cache --select F401,F811,F841 auralis` -> 21 hits in the files above. e.g. `adaptive_mode.py:11 from auralis.dsp.utils.conversion import amplitude_to_db, db_to_amplitude` (`db_to_amplitude` never used in the file).
- **Impact**: Each is a false "dependency" edge; the `adaptive_mode.py` block makes `AdaptiveMode` look coupled to four processor classes it does not call.
- **Siblings**: TD2-02 (backend), TD2-03 (`unified_loader.py`), TD2-04 (scripts). Root cause is shared: the F401/F811/F841 hook in `.pre-commit-config.yaml` (scope `^(auralis|auralis-web/backend)/`) is not installed in this checkout (`.git/hooks` has no active hooks) and no workflow in `.github/` runs ruff, so every split re-grows this.
- **Related**: none (no behaviour impact).
- **Suggested Fix**: `ruff check --select F401 --fix auralis` (then drop the `RecordingType` / `SmoothCurveUtilities` lines by hand if `--fix` leaves a blank import). Add a `ruff check --select F401,F811,F841 auralis auralis-web/backend` step to `backend-tests.yml` next to the other static ratchets so the hook's promise is actually enforced.

##### TD2-02: 16 unused imports in the backend, three of them carry a false "body-used" noqa comment
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:21,23,24,31,60`; `core/chunk_file_loading.py:27`; `core/level_manager.py:22,24`; `core/level_transition.py:26`; `core/position_ticker.py:26`; `security/path_security.py:49`; `websocket/outbound/library.py:13`; `websocket/outbound/player.py:13`; `websocket/outbound_messages.py:16,19,34`
- **Status**: Regression of #6209 (same class; new instances from the #6269/#6271/#6272/#6273 splits)
- **Age**: `e37f82c03` 2026-10-25 / `114b5fd5d` 2026-10-24 (splits); noqa comments from the same refactor
- **Effort**: trivial
- **Description**: After the splits moved bodies into sibling modules the old import blocks stayed. `fingerprint_generator.py` still imports `atexit`, `os`, `ThreadPoolExecutor`, `get_int_env` and `shutdown_fingerprint_executor` (the executor now lives in `fingerprint_executor.py`); the last is under a `# noqa: E402  (split #6271; body-used)` comment that is untrue. Likewise `level_manager.py:21` `# noqa: E402 (body-used below ...)` covers `GAIN_RAMP_SECONDS` and `MAX_GAIN_CORRECTION_DB`, and `path_security.py:49` `# noqa: E402 (split #6271; body-used below)` covers `_extra_allowed_dirs` — none used in those files. `outbound_messages.py` imports `AlternativeProfilePayload`, `WeightedProfilePayload`, `ScanFailurePayload` that no overload references.
- **Evidence**: ruff F401 output above. Two names survive only because tests import them from the wrong module: `tests/backend/test_level_ramp_in_emitted_segment_5051.py:35 from core.level_manager import GAIN_RAMP_SECONDS` (real home `core/level_constants.py`) and `tests/backend/test_main_api.py`, `tests/backend/test_remove_scan_folder_prunes_tracks_5467.py` `from security.path_security import _extra_allowed_dirs` (real home `security/path_allowlist.py`). `position_ticker.py:26` `PlayerState` is unused under `TYPE_CHECKING` (line 40 re-imports it as `_PlayerState`).
- **Impact**: The misleading "body-used" claims defeat the next reader's grep; the wrong-module test imports keep dead re-exports alive (the same shape as closed #5775/#6198).
- **Siblings**: TD2-01, TD2-03.
- **Related**: —
- **Suggested Fix**: Delete the 16 names and their false noqa comments; repoint the three test imports at `core.level_constants` / `security.path_allowlist`. `fingerprint_generator.py` loses its whole `os`/`atexit`/`ThreadPoolExecutor`/`get_int_env` header.

##### TD2-03: `unified_loader.py` keeps 9 dead imports left by the #6273 split, and tests patch names the code no longer reads
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/io/unified_loader.py:13,14,20,22,25-28,31` (imports); `:36-41` (`noqa: F401` pre-split re-export block); tests `tests/auralis/io/test_probe_duration_cap_5312.py:64-66`, `tests/auralis/io/test_ffmpeg_protocol_whitelist_5326.py:56`, `tests/auralis/io_module/test_ffprobe_arg_injection_4826.py:~41`, `tests/test_unified_loader.py:196`
- **Status**: NEW
- **Age**: `66931f63c` 2026-10-24 (probe code moved to `audio_probe.py`)
- **Effort**: small
- **Description**: `json`, `subprocess`, `soundfile`, `warning`, `FFPROBE_TIMEOUT_S`, `SUBPROCESS_TEXT_KWARGS`, `check_ffprobe`, `ffprobe_command`, `redact_subprocess_output` are imported and unused: the ffprobe/soundfile probing now lives in `auralis/io/audio_probe.py`, which has its own copies of those imports (`audio_probe.py:24-26`). The only reason they look alive is tests that `monkeypatch.setattr(unified_loader, "check_ffprobe", ...)` / `patch.object(unified_loader.subprocess, ...)`. Those patches no longer intercept the code under test, because `audio_probe.get_audio_info` / `_get_info_with_ffprobe` look `check_ffprobe` up in `audio_probe`'s namespace. `tests/test_unified_loader.py:196` patches `auralis.io.unified_loader._get_info_with_soundfile` and then calls `get_audio_info`, which resolves `_get_info_with_soundfile` in `audio_probe` and cannot see the mock.
- **Evidence**: `audio_probe.py:25 from .loaders.ffmpeg_probe import check_ffprobe, ffprobe_command`; `test_probe_duration_cap_5312.py:64 monkeypatch.setattr(unified_loader, "check_ffprobe", lambda: True)`. (Shared `subprocess` module object means the `subprocess.run` patches still work by accident.)
- **Impact**: Tests that look like they pin the ffprobe path pass only when a real `ffprobe` is installed (or fail on machines without one) — a vacuous-patch trap of the kind recorded for earlier splits.
- **Siblings**: TD2-01/02 (same split fallout). The `noqa: F401` block at `:36-41` (`_get_info_with_ffprobe`, `_get_info_with_soundfile`, `_reject_oversize_probe`) is legitimate only while tests import them from here.
- **Related**: Dim 6 (test hygiene) / `/audit-engine`: verify `tests/test_unified_loader.py::test_get_info_with_soundfile` actually passes (by inspection `mock_info.called` cannot be True; it is not in `pytest-baseline.json`).
- **Suggested Fix**: Delete the 9 imports; repoint the four tests' patch targets to `auralis.io.audio_probe`; then trim the `noqa` re-export block to what tests genuinely import (or have them import from `audio_probe`).

##### TD2-04: ~25 unused imports/locals in `scripts/` and `tools/`, outside the pre-commit hook's scope
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `scripts/analyze_feedback.py:16,18,20,205`; `scripts/rate_track.py:19`; `scripts/run_all_tests.py:23,27`; `scripts/development/{comprehensive_validation.py:23, monitor_fingerprinting.py:16,24, profile_fingerprint_memory.py:9,11,12,47, test_phase5_scenario_a.py:8, test_smooth_scaling_direct.py:13,16}`; `tools/validation/multistyle_mastering_validation.py:25`
- **Status**: NEW
- **Age**: not determined
- **Effort**: trivial
- **Description**: ruff F401/F841 on the non-shipped Python trees. `analyze_feedback.py` imports `Counter`, `median`, `RecordingType`, `timedelta` and never uses them; `run_all_tests.py` assigns `result` and `e` it never reads. (`launch-auralis-web.py:33-34` `fastapi`/`uvicorn` hits are availability probes, not debt.)
- **Evidence**: `ruff check --select F401,F811,F841 scripts tools` -> 21 findings (list above).
- **Impact**: Low; but `scripts/rate_track.py` and `analyze_feedback.py` are the only consumers of `RecordingTypeDetector` (kept deliberately per CLAUDE.md), so stale imports there can hide whether that surface is still used.
- **Siblings**: TD2-01/02.
- **Related**: —
- **Suggested Fix**: `ruff --fix --select F401,F841` over `scripts/ tools/`; widen the pre-commit `files:` regex to include them, or delete the abandoned `scripts/development/test_*` throwaways.

##### TD2-05: `get_streamlined_cache` is plumbed through the enhancement router and never read
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/backend/config/routes.py:135`; `routers/enhancement.py:95,114`; `routers/enhancement_deps.py:19,25,52-56`
- **Status**: NEW (adjacent to open #5959, which covers the cache worker doing no work; this is the router-side dependency wiring)
- **Age**: `a2b11e2d6` 2026-10-22 renamed the parameter (#5829); the consumer was dropped by `29c5816ec` (#5908, 2026-10-26)
- **Effort**: trivial
- **Description**: After #5908 removed the prewarm handlers (`routers/enhancement_prewarm.py`), nothing in the enhancement router calls `_get_streamlined_cache()`; vulture and grep confirm zero callers (0 tests). The factory still accepts `get_streamlined_cache`, `_EnhancementDeps` stores it, and `config/routes.py:135` builds a lambda over `globals_dict['streamlined_cache']` for it.
- **Evidence**: `rg "_get_streamlined_cache|get_streamlined_cache"` -> only the definition/plumbing lines above.
- **Impact**: A phantom dependency suggests the enhancement endpoints still touch the cache; they do not.
- **Siblings**: `routers/enhancement_deps.py` `_get_player_state_manager` / `_get_repository_factory` should be re-checked in the same pass (both still used elsewhere in that module).
- **Related**: #5959 (open), #5908 (closed).
- **Suggested Fix**: Delete `_get_streamlined_cache`, the `get_streamlined_cache` parameter of `create_enhancement_router`, the `_EnhancementDeps` field and the lambda in `config/routes.py`.

##### TD2-06: Seven methods with zero references anywhere (production or tests)
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/backend/core/chunked_processor.py:245` (`ChunkedAudioProcessor._calculate_rms`); `auralis-web/backend/services/queue_enrichment.py:76` (`QueueEnricher.enrich_tracks`); `auralis/analysis/quality_assessors/utilities/estimation_ops.py:215` (`compute_stereo_correlation`); `auralis/analysis/spectrum_operations.py:202` (`get_band_names`); `auralis/dsp/dynamics/compressor.py:177` (`get_current_state`); `auralis/core/utils/smooth_curves.py:142` (`SmoothCurveUtilities.bell_curve`, only referenced by its own docstring example); `auralis/optimization/performance_optimizer.py:39` (`get_optimization_stats`, only referenced by a module docstring)
- **Status**: NEW
- **Age**: not determined
- **Effort**: trivial
- **Description**: vulture flagged them and a word-boundary grep over `auralis/`, `auralis-web/backend/`, `scripts/`, `tools/` and `tests/` finds no call, patch or getattr string. `_calculate_rms` is a one-line delegator to `chunk_render.calculate_rms` (which has another live caller at `chunk_render.py:100`); `enrich_tracks` is a thin wrapper over the live `resolve_tracks`.
- **Evidence**: e.g. `rg -w "_calculate_rms|enrich_tracks"` -> definition lines only.
- **Impact**: Dead surface on live classes; `enrich_tracks`'s docstring (#4374 filtering semantics) reads like a contract that nothing honours.
- **Siblings**: closed #5771/#5772/#5773 deleted the previous generation of these; these are the remainder.
- **Related**: —
- **Suggested Fix**: Delete the seven methods (and their docstring examples). `QueueEnricher` keeps `resolve_tracks`.

##### TD2-07: `auralis/core/processing/album_target.py` is a whole 126-line module with no production importer
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/core/processing/album_target.py:1-126`; only importer `tests/auralis/core/test_album_target_3481.py`
- **Status**: NEW
- **Age**: `3612e400b` "feat: album-consistent target derivation (#3481 Phase 1)" — never wired in
- **Effort**: small
- **Description**: `derive_album_target()` and its result dataclass are not imported by any module in `auralis/`, `auralis-web/backend/`, `scripts/` or `tools/`; the module is not in `core/processing/__init__.py`. "Phase 1" has no Phase 2 caller.
- **Evidence**: `rg "album_target"` outside docs/audits -> the module itself and its single test.
- **Impact**: Reads as a shipped album-consistency feature; it is not on the audio path.
- **Siblings**: `auralis/core/processing/processing_parameter_readers.py` (21 lines, `REPORTING_ONLY_FIELDS`) is imported only by `tests/auralis/core/test_processing_parameters_have_readers_5576.py` — a test-support constant living in the shipped tree; move it into the test.
- **Related**: —
- **Suggested Fix**: Delete `album_target.py` and its test (or file the Phase 2 wiring issue and add a `TODO(#NNNN)`); move `REPORTING_ONLY_FIELDS` into the #5576 test.

##### TD2-08: Library finders and helpers with no production caller (test-only)
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/library/repositories/artist_repository.py:135` and `genre_repository.py:56` (`get_by_name`); `album_repository.py:123` and `track_repository_search.py:107` (`get_recent`); `track_repository_search.py:89` (`get_by_artist`); `fingerprint_query_mixin.py:33` (`get_by_track_ids`); `fingerprint_upsert_mixin.py:152` (`store_fingerprint`); `fingerprint_shared.py:61` (`is_current_fingerprint`); `auralis/library/fingerprint_quantizer.py:145` (`dequantize`); `auralis/utils/queue/queue_exporter.py:73` (`export_to_file`)
- **Status**: NEW (closed #5773 deleted an earlier set of dead finders in `d2ebcb956`; these remain)
- **Age**: not determined
- **Effort**: small
- **Description**: No call from `auralis/`, `auralis-web/backend/`, `scripts/` or `tools/` (`rg "(\.|\b)<name>\("`, 0 production hits each); tests exercise them (e.g. `get_recent` 26 test calls, `store_fingerprint` 10, `dequantize` 9). `FingerprintQuantizer.dequantize` has no consumer because the blob-storing path was retired (#5509 fixed its bounds but left the pair). `store_fingerprint` is the raw-SQL sibling of the live `upsert()`.
- **Evidence**: `rg -n "\.store_fingerprint\(|\.get_recent\(|\.get_by_name\(" auralis auralis-web/backend` -> no call sites (comments only).
- **Impact**: Each test-covered dead method is maintenance weight on the repository mixins (and drags test fixtures); `get_by_name` x2 invite N+1-style ad-hoc lookups that bypass the eager-load option tuples.
- **Siblings**: `similarity_graph_repository.py:83 add_edges` (test-only) belongs to open #5922 and is not repeated here.
- **Related**: #5922 (open).
- **Suggested Fix**: Delete the methods and their tests as one commit per repository; keep `get_by_name` only if a router is about to use it.

##### TD2-09: Engine/DSP/player helpers kept alive only by tests
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/core/processing/base/compression_expansion.py:230` (`ExpansionStrategies.apply_rms_reduction_expansion`); `auralis/dsp/dynamics/compressor.py:168` (`_apply_lookahead`, plus the `lookahead_buffer` property); `auralis/dsp/utils/adaptive.py:18` (`adaptive_gain_calculation`); `auralis/analysis/fingerprint/metrics/safe_operations.py:64` (`safe_power`); `auralis/dsp/utils/interpolation_helpers.py:17,124` (`create_triangular_envelope`, `create_triangular_filterbank`); `auralis/io/unified_loader.py:175` (`is_audio_file`); `auralis/player/gapless_prebuffer.py:178,184` (`has_prebuffered_track`, `get_prebuffered_track`); `auralis/player/components/queue_navigation.py:143` (`snapshot_index`); `auralis/player/integration_reporting.py:41` (`get_playback_info`); `auralis/player/playback_controller.py:246` (`is_paused`); `auralis-web/backend/core/chunk_single_flight.py:65` (`in_flight`); `auralis-web/backend/core/seekable_source.py:270` (`release_idle`)
- **Status**: NEW
- **Age**: `apply_rms_reduction_expansion` orphaned by #5561 (its removal comment is at `continuous_dsp_ops.py:105`)
- **Effort**: medium
- **Description**: 0 production call sites; each has test callers. Two are self-documented leftovers: `apply_rms_reduction_expansion` ("removed following #5309's precedent for the same class of placebo stage" yet the function stayed), and `_apply_lookahead` ("kept as directly-tested helpers ... no longer part of this signal path", `compressor.py:107-110`). `is_audio_file` duplicates the scanner's extension check (`AUDIO_EXTENSIONS`). `get_playback_info` / `is_paused` / `get_prebuffered_track` are public methods of the player surface: confirm no desktop/CLI consumer before deleting.
- **Evidence**: counts from `rg "(\.|\b)<name>\("` excluding tests: 0 for every name listed; test calls: `get_playback_info` 32, `_apply_lookahead` 13, `create_triangular_envelope` 15, `is_audio_file` 18, etc.
- **Impact**: Tests protect behaviour no shipped path has; the #5561-style "removed stage" leaves its implementation and tests behind, so a reader cannot tell the stage is gone.
- **Siblings**: Not flagged on purpose: `core/executors.py` `get_*_executor` getters (docstring states they exist for test introspection, #5206), `scanner.scan_folder` (documented as kept, #4973), `chunk_fingerprint_registry._reset_registry_miss_warning` (test hook).
- **Related**: —
- **Suggested Fix**: Delete the `apply_rms_reduction_expansion` / `_apply_lookahead` pair first (self-declared dead), then the DSP utility functions; for the player/ backend items either delete or document "desktop API" in the docstring like `scan_folder`.

##### TD2-10: Ten styled-component exports in live `components/` files have no importer anywhere
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/frontend/src/components/library/Styles/ArtistList.styles.ts` (`ArtistAvatar`); `FormFields.styles.ts` (`CompactTextField`); `Skeleton.styles.ts` (`ImageLoadingContainer`, `LoadingIconContainer`, `PulsingBox`); `Tabs.styles.ts` (`DetailViewTabs`); `Typography.styles.ts` (`HelperText`, `SecondaryText`, `SmallText`); `components/playlist/PlaylistList.styles.ts` (`PlaylistActions`)
- **Status**: NEW (closed #6062 / #6265 / #6289 swept earlier alias sets; these remain)
- **Age**: not determined
- **Effort**: trivial
- **Description**: `rg -w <name> src` returns only the defining line for each, including tests. The same `Styles/` directory also holds `Container.styles.ts` (8 exports) and `Spinner.styles.ts`, `EmptyState.styles.ts`, `Icon.styles.ts` that are reachable only from orphan files (see Skipped #5628), and `Spacing.styles.ts` exports nine `spacing*` constants that only a test and `spacingPresets` read.
- **Evidence**: `rg -w "PulsingBox|HelperText|SmallText|DetailViewTabs" auralis-web/frontend/src` -> defining file only.
- **Impact**: Dead styled components still ship in the bundle's module graph and look like part of the design system.
- **Siblings**: #5628's orphan list; `BorderRadius.styles.ts` (#6289, closed).
- **Related**: `/audit-frontend` Dim 5.
- **Suggested Fix**: Delete the ten exports; collapse `Spacing.styles.ts` to `spacingPresets` unless the `spacing*` aliases are asserted by `Spacing.styles.test.ts` on purpose.

##### TD2-11: Barrel-exported UI components with no consumer (`AlbumArtDisplay`, `CenteredLoading`, `EmptyPlaylist`, `EmptyQueue`) plus a few test-only selectors
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `components/shared/ui/media/AlbumArtDisplay.tsx` (+ `ui/media/index.ts`); `components/shared/ui/loaders/LoadingSpinner.tsx` (`CenteredLoading` + `loaders/index.ts`); `components/shared/ui/feedback/EmptyState.tsx` (`EmptyPlaylist`, `EmptyQueue` + `feedback/index.ts`); `store/selectors/queue.ts` (`selectFormattedRemainingTime`); `api/transformers/artistTransformer.ts` (`transformArtist` — a duplicate path; the live one is imported via `libraryQueryRequest.ts` / `useArtistDetailsData.ts`, verify before deleting)
- **Status**: NEW
- **Age**: not determined
- **Effort**: small
- **Description**: The barrels are imported (`ProgressiveImage`, `LibraryGridSkeleton`, `EmptyState`, `LoadMoreError` are used), which hides that four sibling exports are not: `AlbumArtDisplay` appears only in `ui/README.md`, `CenteredLoading` nowhere outside its own file, `EmptyPlaylist` nowhere, `EmptyQueue` only in its own announcement test. `selectFormattedRemainingTime` is used by two tests only (#6208 deleted its siblings but left this one).
- **Evidence**: `rg -w "AlbumArtDisplay|CenteredLoading|EmptyPlaylist|EmptyQueue" src` outside `shared/ui` -> none.
- **Impact**: Barrel hides the dead leaves from file-level orphan sweeps (like #5778's), so they survive audits.
- **Siblings**: 190 other exports are exported but only used inside their own file (over-exported; not reported — `export` removal is cosmetic).
- **Related**: `/audit-frontend`.
- **Suggested Fix**: Delete the four components (and their README rows / the `EmptyQueue` test case) and `selectFormattedRemainingTime`.

##### TD2-12: Subpackage barrels re-export ~50 names that nothing imports through the package
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/library/scanner/__init__.py` (7: `AUDIO_EXTENSIONS`, `AudioAnalyzer`, `BatchProcessor`, `DEFAULT_BATCH_SIZE`, `SKIP_DIRECTORIES`, `FileDiscovery`, `MetadataExtractor`); `auralis/analysis/quality/__init__.py` (11); `auralis/analysis/fingerprint/__init__.py` (9: `AggregationUtils`, `AudioMetrics`, `FingerprintConstants`, `MetricUtils`, `SafeOperations`, `DimensionWeights`, `FingerprintDistance`, `GraphStats`, `DimensionStats`); `auralis/analysis/ml/__init__.py` (4); `auralis/library/utils/__init__.py` (3); `auralis/core/processing/base/__init__.py` (`AudioMeasurement`, `MeasurementUtilities`); `auralis/core/analysis/spectrum_mapper/__init__.py` (4); `auralis/optimization/__init__.py` (3); `auralis/core/config/__init__.py` (2); `auralis-web/backend/schemas/__init__.py` (7: `INTENSITY_MIN`, `PaginatedResponse`, `ScanFailure`, `MAX_TRACK_ID_LIST`, `CacheTierStats`, `OverallCacheStats`, `WebSocketMessageType`)
- **Status**: NEW (closed #6274 did this for `dsp/utils/__init__.py`; #6198 for router shims; #5778 for frontend barrels)
- **Age**: not determined
- **Effort**: small
- **Description**: AST import graph over `auralis/`, `auralis-web/backend/`, `scripts/`, `tools/` finds no `from <pkg> import <name>` (nor `pkg.name` attribute access) for these names outside the barrel; real consumers import from the leaf modules. Several are test-only (`schemas.INTENSITY_MIN`, `PaginatedResponse`, `MAX_TRACK_ID_LIST`, `CacheTierStats`). Caveat: these `auralis.*` barrels are arguably the engine's public API for the desktop/CLI; decide per package before pruning. Not reported because body-used or fed to a registry: `config/startup/__init__.py`, `config/middleware/__init__.py` (names are used in the body), `auralis/__init__.py`.
- **Evidence**: custom script output, e.g. `('auralis/library/scanner/__init__.py', ... dead=['AUDIO_EXTENSIONS','AudioAnalyzer','BatchProcessor','DEFAULT_BATCH_SIZE','SKIP_DIRECTORIES','FileDiscovery','MetadataExtractor'])`.
- **Impact**: Each barrel name is an import-time edge: importing `auralis.analysis.quality` pulls all 11 assessors, and eager barrels are what created the circular-import workarounds elsewhere.
- **Siblings**: #6274 precedent.
- **Related**: —
- **Suggested Fix**: Prune to the names with a real importer (backend `schemas/__init__.py` first — `__all__` is the contract); for `auralis.*` barrels drop everything not documented as public API.

##### TD2-13: Rust `AudioFingerprint::to_dict` is test-only and duplicates the 25-key mapping in `py_bindings.rs`
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `vendor/auralis-dsp/src/fingerprint_compute.rs:58-100` (+ test `test_to_dict:841`); duplicate in `vendor/auralis-dsp/src/py_bindings.rs:~110-148`
- **Status**: NEW
- **Age**: not determined
- **Effort**: trivial
- **Description**: `compute_fingerprint_wrapper` builds its PyDict with 25 `dict.set_item` lines and never calls `to_dict()`; the only caller of `to_dict` is its own unit test. Two parallel key lists must be kept in sync by hand.
- **Evidence**: `rg to_dict vendor/auralis-dsp/src` -> definition, test.
- **Impact**: Adding a 26th dimension requires editing three places (struct, `to_dict`, bindings) but only two matter.
- **Siblings**: —
- **Related**: Dim 3 (duplication) of this audit.
- **Suggested Fix**: Delete `to_dict` and `test_to_dict` (or have `py_bindings.rs` consume `to_dict()` to keep one key list — pick one).

##### TD2-14: Repo-root and tooling detritus is tracked: `100`, `coverage.json`, `index.html`, `tools/alembic.ini`
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `/100` (131-byte empty curl cookie jar, added `aac7dae00` 2025-11-20); `/coverage.json` (258 KB generated report, added 2025-11-20, listed in `.gitignore:94` yet tracked); `/index.html` (3.8 KB legacy "Matchering 2.0" landing page, `9466c2fb0` 2025-09-29, referenced by no manifest/build script); `tools/alembic.ini` (`724edf2a4`, alembic is commented out in `requirements.txt:76` and not used)
- **Status**: NEW
- **Age**: 2025-09 to 2025-11
- **Effort**: trivial
- **Description**: Files with no consumer, one of them a generated artifact that the ignore file already says should not be tracked.
- **Evidence**: `git ls-files 100 coverage.json index.html tools/alembic.ini` all tracked; `rg -n "alembic" -g '*.py' -g '*.toml'` -> nothing active.
- **Impact**: Noise in the repo root, and `coverage.json` churns on any local coverage run.
- **Siblings**: —
- **Related**: Dim 7 (stale docs) may also want a `docs/` pointer check.
- **Suggested Fix**: `git rm --cached coverage.json 100`; delete `index.html` and `tools/alembic.ini`. (`FIGMA_TOKENS_EXPORT.json` is referenced by `docs/getting-started/START_HERE.md`; leave it.)

#### Dimension 3: Logic Duplication

##### TD3-03: Two bit-identical FFT-EQ implementations; the "standard" one is only reachable if an in-tree import fails
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/dsp/eq/filters.py:17-109` (`apply_eq_gains`, `apply_eq_mono`) vs `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:20-124` (`apply_eq_gains_vectorized`, `_apply_eq_mono_vectorized`); selector at `auralis/dsp/eq/psychoacoustic_eq.py:26-33,105-133`
- **Status**: NEW (adjacent to closed #4993, which deleted the third sibling `ParallelEQProcessor`)
- **Age**: 474b52de2 2025-10-24
- **Effort**: small
- **Description**: Both implement FFT -> per-critical-band gain -> Hermitian mirror -> IFFT with the same padding, the same `len > fft_size` ValueError guard (#3742), the same dtype preservation (#2450) and the same even-`fft_size` assumption (#4985). `PsychoacousticEQ.apply_eq` picks the vectorized one whenever `VECTORIZED_EQ_AVAILABLE`, which is set by `try: from .parallel_eq_processor import VectorizedEQProcessor` — a package in the same tree, so the `except ImportError` branch cannot fire in a shipped build. I diffed the two on random (N,2)/(N,)/(N,1) float32/float64 input: max abs difference 0.0 (1e-16 for float64 mono).
- **Evidence**: `psychoacoustic_eq.py:125-133` `if self.vectorized_processor is not None: ... apply_eq_gains_vectorized(...) else: return apply_eq_gains(...)`; the `EQSettings.__post_init__` comment at `:46-48` still cites `_apply_eq_mono_parallel/_sequential`, which no longer exist, showing the cost of the mirrored fix history (#3742, #2450, #4985 each landed twice).
- **Impact**: every EQ fix is a two-file edit; the dead fallback adds a code path tests must pin separately (`tests/auralis/dsp/test_eq_*`).
- **Siblings**: `core/processing/eq_curve.py` (WOLA driver) calls through `PsychoacousticEQ` and is not duplicated.
- **Related**: Dim 2 (dead fallback) and Dim 8 ("Vectorized" variant that coexists with its base); filed here as the logic duplication.
- **Suggested Fix**: keep one implementation. Cheapest: have `PsychoacousticEQ.apply_eq` always call `filters.apply_eq_gains` after folding the vectorized gain-curve build (`gain_curve[mask] = gain`, one multiply) into `apply_eq_mono`, delete `parallel_eq_processor/` and the `VECTORIZED_EQ_AVAILABLE` shim, and fix the stale comment. Micro-benchmark first if the "1.7x" claim matters.

##### TD3-04: Limiter -> sample-count guard -> finite guard tail pasted into all three HybridProcessor modes
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/processing/mode_dispatch.py:66-80` (adaptive) and `:95-109` (hybrid), `auralis/core/hybrid_stage_dispatch.py:127-138` (reference)
- **Status**: NEW
- **Age**: guards from #2519/#2520/#5533
- **Effort**: trivial
- **Description**: Each mode ends with `processed = processor.brick_wall_limiter.process(processed)`, `if processed.shape != target_audio.shape: raise RuntimeError(f"Sample count mismatch after limiter ({mode}): ...")`, then `validate_audio_finite(processed, context="<mode> mode output", repair=False)`. Three copies, with the same three fix-history comments. All three are currently at parity (none drops a guard), which is the point: the next guard added (e.g. dtype assert) must be added in three places, and the guard is the gapless-playback invariant.
- **Evidence**: identical blocks at the lines above; the reference one is even in a different module.
- **Impact**: change-cost on the project's most important invariant (`len(output) == len(input)`).
- **Siblings**: the same invariant is also enforced, with different exception types, in `auralis-web/backend/core/audio_processing_pipeline.py:142` (`ValueError`) and `auralis/core/mastering_chunk_loop.py:203` (`RuntimeError`); not merged here because they check different layouts.
- **Related**: none open.
- **Suggested Fix**: add `_finish_mode_output(processor, processed, target_audio, mode)` in `mode_dispatch.py` (limiter + shape guard + finite guard) and call it from the three modes; make `hybrid_stage_dispatch.process_reference_mode` call it too (the cyclic import already forced the deferred `_reference_stage_dispatch` shim, so put the helper in `core/utils/` or `utils/audio_validation.py`).

##### TD3-05: Mastering-stage skeletons and primitive scaffolding that `no_op()` did not absorb
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/stages/presence_enhancement.py:20-77` vs `mid_warmth.py:11-70` (and `air_enhancement.py:12-76`); `auralis/core/dsp/transient_shaper.py:80-93`, `auralis/core/dsp/harmonic_exciter.py:110-121`, `auralis/core/stages/sub_bass_control.py:68-70`
- **Status**: NEW
- **Effort**: small
- **Description**: (a) `presence_enhancement` and `mid_warmth` are the same function with different constants: `content = (a + b)/2; if content >= T: no_op; factor = 1 - ramp_to_s_curve(content, 0, T); boost_db = MAX*intensity*factor(*hf_lift); if boost_db < MIN_AUDIBLE_BOOST_DB: no_op; ParallelEQUtilities.apply_bandpass_boost(...); verbose print; return processed, {...}`. `air_enhancement` and `clarity_boost` share the tail. `intensity = min(intensity, 1.0)` is re-typed in 4 stages, with its own explanatory comment each time. (b) `core/dsp/transient_shaper.py:80-93` re-derives the corner clamp as `max(1e-4, min(0.995, hz/nyq))` while `dsp/utils/filters.normalized_corner` (floor 1e-4, ceiling 0.99) is the shared clamp both #4211 and #6300 were fixed in; the two now disagree on the ceiling. (c) `axis = -1 if audio.ndim > 1 else 0` is kept in the transient shaper, harmonic exciter and sub-bass stage although `ParallelEQUtilities._parallel_add` documents that `axis=-1` already covers 1-D and 2-D. (d) `HarmonicExciter.will_bypass` and the degenerate-donor test are re-checked inline in `stages/harmonic_exciter.py:66-79` "to mirror" the primitive.
- **Evidence**: `presence_enhancement.py:50-60` vs `mid_warmth.py:44-56` differ only in constants; `transient_shaper.py:88-89` clamp vs `filters.py:48` `normalized_corner`.
- **Impact**: the 0.05 dB gate (#6304) and the HF-budget cap each had to be applied per stage; a new "bandpass-boost stage" is a copy-paste.
- **Siblings**: other stages are legitimately different.
- **Related**: offline-CLI-only subsystem (#4873) so low blast radius.
- **Suggested Fix**: add `stages/__init__.py::deficit_boost_stage(audio, content, threshold, max_boost_db, hf_lift, band, ...)` (or a small `apply_deficit_band_boost` helper next to `no_op`) and let presence/mid_warmth call it; switch the transient shaper to `normalized_corner`; drop the ndim branches in the three call sites; let `harmonic_exciter.apply` trust `HarmonicExciter.apply`'s own bypass (return its input only when it is not a copy).

##### TD3-06: Three "if peak > ceiling: soft_clip(threshold) else copy" safety limiters
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/processing/base/peak_management.py:20-57` (`SafetyLimiter.apply_if_needed`), `auralis/core/stages/safety_limiter.py:8-45`, `auralis/core/mastering_process_chunk.py:55-64` (`reduce_peaks`)
- **Status**: NEW
- **Effort**: small
- **Description**: Same decision and same primitive (`dsp/dynamics/soft_clipper.soft_clip`), different thresholds (`0.89` / `ceiling*0.95` / `10**(target_db/20)`), each with its own copy-on-bypass (#5107) and its own dB-measure-and-log. A fourth variant (`StreamingPeakCeiling`) is the realtime one and is a genuinely different algorithm.
- **Evidence**: `peak_management.py:46-49,57` and `safety_limiter.py:34-45` and `mastering_process_chunk.py:60-64`.
- **Impact**: the `.copy()` bypass contract (#5107) had to be applied to each by hand — `peak_management.py:51-57` even documents finding a "fourth site of the same bypass-without-copy shape".
- **Siblings**: `PeakNormalizer.normalize_to_target` (`peak_management.py:60-107`) repeats the `audio.copy()` bypass for near-silence.
- **Suggested Fix**: add `limit_peaks(audio, ceiling, knee=0.95)` to `auralis/dsp/dynamics/soft_clipper.py` (peak test, soft_clip, always-copy bypass) and call it from the three; keep log/dB reporting at the call sites.

##### TD3-07: Inline channel-average downmix survives next to the one `to_mono()` it was meant to replace
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/dsp/utils/spectral.py:68-69, 121-122, 156-157, 243-244`; `auralis/core/analysis/content_analyzer.py:272`; `auralis/core/processing/stage_snapshot.py:72`; `auralis/core/processing/continuous_stages.py:198`
- **Status**: NEW (residue of closed #5746 / #5784 / #2452)
- **Effort**: trivial
- **Description**: `dsp/utils/audio_info.to_mono(audio, layout)` exists specifically because the channel axis "was decided independently at ~15 sites and disagreed (#2452, #5746)". Four of those sites are in `spectral.py`, the sibling module in the same package, and hard-code `axis=1` with no layout parameter (same `if audio.ndim == 2: np.mean(audio, axis=1)` shape that caused #5746).
- **Evidence**: `spectral.py:68` `if audio.ndim == 2: audio = np.mean(audio, axis=1)` (x4); `stage_snapshot.py:72` `chunk.mean(axis=1) if chunk.ndim == 2 else chunk`.
- **Impact**: a `(channels, samples)` array handed to `spectral_centroid` is averaged across time silently, the #5746 bug class.
- **Siblings**: the 7 sites above are the complete list from `grep -rnE "np\.mean\(\w+, axis=(0|1|-1)\)|\.mean\(axis=(0|1)\)"` over `auralis/` and `auralis-web/backend/`.
- **Suggested Fix**: replace each with `to_mono(audio)` from `auralis.dsp.utils.audio_info` (it returns 1-D unchanged; `audio_info` imports only numpy, so no cycle).

##### TD3-08: Rust: `dsp_math.rs` consolidated RMS/LUFS but identical copies and sibling helpers remain
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `vendor/auralis-dsp/src/stereo_analysis.rs:18-26` (`compute_energy`), `fingerprint_compute.rs:555-562` (frame RMS inline), `fingerprint_compute.rs:165-169` vs `frequency_analysis.rs:80-82` (`hz_to_bin`), std-dev at `variation_analysis.rs:63-73`, `fingerprint_compute.rs:526-529`, `stereo_analysis.rs:101-113`, Hann window at `frequency_analysis.rs:31-42`, `spectral_features.rs:174-181`, `rhythm.rs:114-118`
- **Status**: NEW (the module header of `dsp_math.rs` records #4022 consolidating exactly this class)
- **Age**: compute_energy 8a8bd5a4c 2026-02-21
- **Effort**: small
- **Description**: `stereo_analysis::compute_energy` is byte-for-byte `dsp_math::compute_rms`. `hz_to_bin` is defined twice and has diverged: the `fingerprint_compute` copy clamps with `.min(fft_size - 1)`, the `frequency_analysis` copy does not (its single caller clamps the frequency to Nyquist first, so no OOB today). The Hann window is coded three times (two f32 forms differing only in zero-padding, one f64 periodic). Three population std-dev loops.
- **Evidence**: `dsp_math.rs:11-17` vs `stereo_analysis.rs:19-26`; `fingerprint_compute.rs:165` vs `frequency_analysis.rs:80`.
- **Impact**: the earlier `estimate_lufs` duplication "silently diverged" (constants `-0.7` vs `+1.0`); these are the same class, one of them (`hz_to_bin`) already diverged.
- **Suggested Fix**: move `hz_to_bin` (with the clamp), `hann(n, periodic)`, `std_dev` into `dsp_math.rs`, delete `compute_energy`, and have `estimate_transient_density` call `compute_rms` per frame.

##### TD3-09: ~22 redundant `except Exception: session.rollback(); raise` handlers in repositories
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/library/repositories/` — `album_artwork.py:90,115,156`, `artist_repository.py:287`, `fingerprint_scheduler_repository.py:296`, `fingerprint_stats_repository.py:107`, `genre_repository.py:142,179,208`, `settings_repository.py:180,224`, `similarity_graph_repository.py:40,60,79,103`, `track_repository_maintenance.py:82,164,233`, `track_repository_mutation.py:232,275`, `factory.py:209`
- **Status**: NEW (residue of closed #5117 / #6212; #6212 migrated the swallow-and-return handlers but not the re-raise ones)
- **Age**: pattern from #2238
- **Effort**: small
- **Description**: `BaseRepository._session_scope` rolls back on any escaping exception and closes (base.py:130-157); its own docstring says a method "no longer needs its own `except Exception: session.rollback(); raise`". An AST scan finds 22 handlers of exactly that shape in other repository files (plus 3 deliberate "rollback and continue" `IntegrityError` handlers at `fingerprint_scheduler_repository.py:180`, `playlist_membership_mixin.py:207`, `track_repository_lifecycle.py:285` that must stay).
- **Evidence**: e.g. `similarity_graph_repository.py:33-42` `with self._session_scope() as session: try: ... session.commit() ... except Exception: session.rollback(); raise`.
- **Impact**: an `except ... raise` wrapper per write path; a change to the failure policy (retry-on-locked, #5940) would otherwise need 22 edits.
- **Suggested Fix**: delete the try/except wrappers (keep `commit()`), leaving `_session_scope` as the only owner of rollback.

##### TD3-10: Repository read paths: ~23 per-item `expunge` loops beside `_first_detached/_all_detached`, and three hand-listed nested Track option tuples
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: expunge loops in `artist_repository.py:178,222,251`, `fingerprint_query_mixin.py:52,74,137,156,188,268`, `fingerprint_similarity_mixin.py:59,211`, `genre_repository.py:105,242`, `processing_job_repository.py:44`, `similarity_graph_repository.py:133`, `track_repository_lookup.py:45,51,83,89`, `track_repository_search.py:85,102,132,163,195,250`; nested Track options at `album_repository.py:52-58`, `artist_repository.py:96-100`, `playlist_crud_mixin.py:30-34` vs `track_repository.py:40-66` (`_track_eager_options`)
- **Status**: NEW (the get-one half was migrated under closed #6212; the list-read loops and the nested tuples were not)
- **Effort**: medium
- **Description**: `base.py:195-210` gives `_first_detached/_all_detached` as the one detach policy (its docstring says per-item `expunge(obj)` leaves eager-loaded relatives `DetachedInstanceError`-prone, #2406/#4236), yet ~23 list read paths still do `for x in rows: session.expunge(x)`. Separately, `_track_eager_options` centralizes which Track relationships `to_dict()` needs (#4500), but Album/Artist/Playlist detail tuples spell `selectinload(X.tracks).selectinload(Track.genres/artists/album)` by hand. A new Track relationship that `to_dict()` reads has to be added to four places; this is exactly how #4236 and #5961 happened.
- **Evidence**: `playlist_crud_mixin.py:30-34` three hand-written `selectinload(Playlist.tracks).selectinload(Track.<rel>)`; `artist_page.py:29` already composes with `.options(*_ALBUM_LIST_OPTIONS)`, proving nested composition works.
- **Impact**: DetachedInstanceError class (#4236/#5961) stays structurally possible; every Track relationship change is a 4-file sweep.
- **Siblings**: see locations.
- **Related**: #6212 (closed), #5961 (closed).
- **Suggested Fix**: replace the loops with `self._all_detached(session, stmt)`; add `nested_track_options(parent_rel)` next to `_track_eager_options` returning `selectinload(parent_rel).options(*_track_eager_options(collections_via_selectin=True))` and use it for the album/artist/playlist detail tuples.

##### TD3-11: Router `*_deps.py` modules hand-repeat the same holder/getter plumbing
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/player_deps.py:50` and `similarity_deps.py:15` (`_unavailable`); `lambda: None` getter defaults at `system_deps.py:18`, `settings_deps.py:23`, `library_deps.py:20`, `metadata_deps.py:75`, `cache_streamlined.py:60`, `similarity_graph.py:49`, `processing_deps.py:64`; `_get_connection_manager` at `playlists_deps.py:23`, `library_scan_deps.py:38`, `enhancement_deps.py:42`, `player_deps.py:86`, `artwork_deps.py:25`; optional-getter resolver `getter() if getter else None` at `enhancement_deps.py:46-61` (x4) and `library_scan_deps.py:35`; `_get_deps` at `system_deps.py`, `settings_deps.py`, `library_deps.py`, `cache_streamlined.py`, `health.py`
- **Status**: NEW (the repository half is already `RepositoryFactoryDeps`)
- **Effort**: small
- **Description**: `routers/dependencies.py` provides `RouterDeps` and `require_service`, but each router still defines its own `_XDeps` holder with the same `connection_manager` / `get_repository_factory` / `get_enhancement_settings` fields, the same "unavailable -> None" placeholder and the same one-line resolvers.
- **Impact**: adding a shared collaborator (say a second broadcast manager) is a 6-file edit; the placeholder semantics (`None` vs raise) differ per file.
- **Suggested Fix**: add `unavailable()` and `RouterDeps.resolve_optional(name)` to `routers/dependencies.py`, plus a shared `connection_manager`-holder base used by the five routers; delete the local copies.
- **Merge note**: absorbs TD5-05 (the ten copies of the `_unavailable()` / `lambda: None` placeholder getter are the same plumbing; the consolidation site is `unavailable()` in `routers/dependencies.py`).

##### TD3-12: Stream-task registration block pasted into three WebSocket handlers
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:160-185` (play_enhanced) and `:203-225` (play_normal), `auralis-web/backend/ws_handlers/seek_command.py:122-143`
- **Status**: NEW (teardown half already consolidated by `ws_handlers/stream_cancel.detach_stream`)
- **Age**: 6b31531cb 2026-07-11
- **Effort**: trivial
- **Description**: Each handler does `async with state.active_tasks_lock: pause_event = asyncio.Event(); pause_event.set(); state.pause_events[ws_id] = ...; flow_event = ...; state.active_tasks[ws_id] = asyncio.create_task(...); state.active_track_ids[ws_id] = track_id`, with the #3522 "atomic under the lock" and #2106 comments restated. The detach side has a single helper; the attach side does not.
- **Evidence**: the three `async with state.active_tasks_lock:` blocks (`grep -n "async with state.active_tasks_lock"`).
- **Impact**: the lock-ordered install (#3522) is one of the riskiest bits of WS state; a fourth command copies it again. Handlers already diverge on `active_stream_settings` (open #5076).
- **Related**: #5076 (OPEN) — play_normal never records `active_stream_settings`; a shared `attach_stream` is where that fix would go.
- **Suggested Fix**: add `attach_stream(state, ws_id, track_id, make_task)` next to `detach_stream` in `ws_handlers/stream_cancel.py` (or onto `StreamState`) and call it from the three handlers.

##### TD3-13: `stream_normal_audio` keeps its own copy of the permit/handler skeleton `run_enhanced_stream` already owns
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/core/stream_normal.py:56-83` (guards + semaphore acquire + busy error) and `:257-279` (WebSocketDisconnect/Exception handlers + semaphore release); canonical at `auralis-web/backend/core/stream_enhanced_lifecycle.py:67-100,121-148`
- **Status**: NEW (residual of closed #6214: "stream_normal repeats the tail" — the enhanced/seek skeleton was extracted, the normal tail was not)
- **Effort**: small
- **Description**: Same `_stream_type_var.set`, same `controller._get_repository_factory` guard, same `asyncio.wait_for(controller._stream_semaphore.acquire(), timeout=STREAM_ACQUIRE_TIMEOUT_SECONDS)` + "Server busy" error, same `except WebSocketDisconnect / except Exception -> _safe_error_message(...)` and `finally: controller._stream_semaphore.release()`, with the #4329 / #5488 / #3511 fix history restated.
- **Impact**: the cancellation-safety of the permit (#4329) has to be kept identical in two files.
- **Suggested Fix**: extract `stream_permit(controller, track_id, websocket)` (async context manager acquiring/releasing the semaphore and sending the busy error) and `report_stream_failure(controller, websocket, track_id, exc, **error_kwargs)` into `stream_lifecycle.py`; use them from both `run_enhanced_stream` and `stream_normal_audio`.

##### TD3-14: Normal and enhanced chunk pumps are the same look-ahead/gate/drain/send loop
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/core/stream_normal_chunks.py:61-205` vs `auralis-web/backend/core/stream_enhanced_chunks.py:103-297`
- **Status**: NEW (#5032 and the enhanced/seek merge in `pump_chunks` did not touch the normal/enhanced pair)
- **Effort**: medium
- **Description**: Both loops: `wait_for_stream_gates` -> `_is_websocket_connected` check -> `_drain_cancelled_task` -> take the look-ahead task or produce now -> create next look-ahead -> `controller._send_*` -> on not-delivered `_drain_cancelled_task` + `_send_error(recovery_position=...)` + `stopped_early` -> on exception drain, log, `_send_error`, `failed_chunks.append`, `continue` -> `finally: _drain_cancelled_task`. The fix lineage (#3493, #3874, #4790, #5082) is cited in both. They already differ in places a shared loop would force to be deliberate: only the enhanced pump has a dedicated `TimeoutError` abort and `ConnectionError` branch and sends `error_code`; only the normal pump counts consecutive read timeouts (#5082).
- **Impact**: the previous enhanced/seek copy drifted ("#4999's TimeoutError fix reached the seek loop only as #5074", per the module docstring); the normal/enhanced pair is the remaining place that can drift the same way.
- **Suggested Fix**: one `pump_loop(controller, websocket, produce, send, recovery_position, on_chunk_error)` in `stream_chunk_ops.py` with the two flavours supplying `produce`/`send`; keep the read-timeout counter as the normal flavour's `on_chunk_error` hook.

##### TD3-15: Queue index re-basing over dropped entries written twice
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/services/queue_service.py:74-84` and `auralis-web/backend/services/queue_service_base.py:215-226`
- **Status**: NEW (adjacent to closed #5934, which added the second copy)
- **Effort**: trivial
- **Description**: `sum(1 for ti in resolved[:index] if ti is not None) if resolved[index] is not None else -1` (guarded by `0 <= index < len(resolved)`) appears in `get_queue_info` and in the `queue_changed` broadcast; the former's comment says it must match the latter "exactly".
- **Impact**: a fix to one (#5934 was exactly such a divergence) must be mirrored by hand.
- **Suggested Fix**: add `rebase_index(resolved, index) -> int` to `services/queue_enrichment.py` (where `_enricher.resolve_tracks` lives) and call it from both.

##### TD3-16: Two LRU-by-mtime directory pruners and four age-based orphan sweepers
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/core/thumbnail_cache.py:127-180` vs `auralis-web/backend/core/chunk_disk_prune.py:107-157`; sweepers at `auralis-web/backend/config/startup/tempfiles.py:95-125` and `:190-215`, `auralis-web/backend/config/startup/decode_temps.py:15-33`, `auralis-web/backend/core/encoding/atomic_io.py:150-172`, `auralis/analysis/fingerprint/fingerprint_storage.py:272-292`
- **Status**: NEW
- **Age**: thumbnail copy 8ef94616f 2026-09-03 was written after the chunk one (f43114dac 2026-06-01)
- **Effort**: small
- **Description**: Both pruners scan a directory into `(mtime, size, path)`, return early under the cap, sort oldest-first, unlink until under budget, count/log. The thumbnail copy added hardening the chunk copy lacks (symlinked-dir refusal, temp-prefix exclusion, a `keep` argument). The chunk directory is already symlink-guarded upstream (`config/limits.py:95-121`), so no live hole — hence LOW — but the guard lives in only one copy. Four more routines repeat `glob -> stat().st_mtime >= cutoff -> unlink/rmtree -> counter -> log`; `tempfiles.py` follows symlinks via `stat()`/`rmtree`, while `stale_backups.py:25` deliberately uses `follow_symlinks=False`.
- **Impact**: age/size policy fixes (symlink handling, partial-file exclusion) are per-copy.
- **Suggested Fix**: one `prune_directory_lru(directory, max_bytes, *, skip=..., keep=None)` and one `reap_older_than(entries, max_age_s, remover)` in `auralis-web/backend/core/cache_cleanup.py` (the declared shared lifecycle boundary, #5257); the engine-side `fingerprint_storage.sweep_orphans` can take the same helper via a thin import or keep its predicate and share only the age gate.

##### TD3-17: Four `{data, loading, error}` detail hooks repeat the AbortController + isAbortError scaffold
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/frontend/src/components/library/Details/usePlaylistDetails.ts:23-44`, `.../Details/useAlbumDetails.ts:46-109`, `.../Details/useArtistDetailsData.ts:48-100`; variants `hooks/library/useLibraryStats.ts:28-62`, `components/library/Controls/AddToPlaylistMenu.tsx:34-62`
- **Status**: NEW
- **Age**: abort wiring from #3601/#4643/#5653 (applied per hook)
- **Effort**: small
- **Description**: Verbatim: `useState(data/loading=true/error)`, `useEffect(() => { const controller = new AbortController(); const run = async () => { setLoading(true); setError(null); try { const data = await get(..., { signal: controller.signal }); if (controller.signal.aborted) return; set...(data) } catch (err) { if (controller.signal.aborted || isAbortError(err)) return; console.error; setError(ApiErrorHandler.parse(err)) } finally { if (!controller.signal.aborted) setLoading(false) } }; run(); return () => controller.abort(); }, [id])`. The comments in all three cite the same #3601/#4643/#5653 reasoning.
- **Impact**: the abort contract (#5653 "detected three different ways") is repeated; the next hook copies it again. TanStack Query (`useQuery`, already used by `useAlbumFingerprint`/`useInfiniteAlbums`) provides the signal, loading and error state.
- **Suggested Fix**: add `hooks/shared/useAbortableResource(fetcher, deps)` returning `{data, loading, error}` (or move the three to `useQuery` with `queryFn: ({signal}) => get(..., {signal})`), keeping each hook's transform step local.

##### TD3-18: The app scroll element is resolved by string id in 7 components, each re-implementing the layout-effect/ready-state scaffold
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `components/library/Items/albums/VirtualizedAlbumGrid.tsx:49`, `Items/albums/AlbumGridContent.tsx:73`, `Items/albums/EraSection.tsx:78`, `Items/artists/ArtistListContent.tsx:111`, `Views/TrackGridView.tsx:61`, `Views/TracksTab.tsx:50`, `Views/TrackListViewContent.tsx:76` (all under `auralis-web/frontend/src/`); id defined at `components/core/AppMainContent.tsx:66`
- **Status**: NEW (adjacent to closed #5120, which applied the `useLayoutEffect` fix to six of the seven by hand)
- **Age**: 8ff20aca9 2026-08-14 (the #5120 fix touched each copy)
- **Effort**: small
- **Description**: `document.getElementById('app-main-content-scroll')` is a bare string literal in 8 places (the owning component plus 7 readers). Six readers repeat `scrollElementRef + scrollReady state + useLayoutEffect` with a verbatim #5120 comment; `TrackListViewContent.tsx:76` was deliberately left on `useEffect` because it has no fallback branch (per the #5120 commit message), which only a reader of that commit knows. The "near-end load more" effect is likewise re-written per list with different guards (`remainingRows <= 2` in `VirtualizedAlbumGrid.tsx:66-73`, `tracks.length - 10` in `TrackListViewContent.tsx:100-110`, `rows.length - 1 && !loadMoreFailed` in `ArtistListContent.tsx:140-149`).
- **Impact**: renaming the container id or changing the resolution timing is an 8-file edit; the failed-page guard (#5870) exists in some copies and not others.
- **Siblings**: `TrackListView.tsx:99` `scrollableTarget="app-main-content-scroll"` (react-infinite-scroll-component).
- **Suggested Fix**: export `APP_MAIN_SCROLL_ID` from `AppMainContent.tsx`, add `useAppScrollElement()` (layout-effect + state, returns `{ref, ready}`) in `components/library/Items/utilities/useGridVirtualizer.ts`'s neighbourhood, and a `useNearEndLoad({lastIndex, count, hasMore, isLoadingMore, failed, onLoadMore, threshold})`; migrate the seven readers.

##### TD3-19: The default preset `'adaptive'` is still a bare literal at 10 runtime sites outside the `schemas` source of truth
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: frontend `auralis-web/frontend/src/store/slices/playerSlice.ts:51`, `hooks/enhancement/enhancementState.ts:37`, `hooks/enhancement/usePlayEnhanced.ts:190`, `components/settings/SettingsDialogContent.tsx:90` (types/domain.ts:108-112 holds the union and `ENHANCEMENT_PRESETS`, no default constant); engine `auralis/core/config/unified_config.py:74`, `auralis/core/processing/adaptive_mode.py:94`, `auralis/core/analysis/spectrum_mapper/spectrum_mapper.py:84`, `.../content_modifiers.py:18`, `auralis/library/models/processing_job.py:33`, `auralis/library/models/settings.py:50`
- **Status**: NEW (residue of closed #5794 / #5610: the backend web layer got `DEFAULT_PRESET`; the frontend runtime sites and the engine/library layers got no constant; `_audit-common.md` lists only `playerSlice` and `enhancementState`)
- **Effort**: trivial
- **Description**: The user directive reduced presets to `'adaptive'`, so these literals are all correct today; the risk is that the next preset change must find 10 spellings. `usePlayEnhanced.ts:190` (`startPlayback(trackId, 'adaptive', 1.0, 'normal')`) and `SettingsDialogContent.tsx:90` (`?? 'adaptive'`) are not in the audit skill's sibling table at all. `core/` deliberately does not import `schemas` (layering, `proactive_buffer.py`), but the engine has no constant of its own either.
- **Suggested Fix**: add `export const DEFAULT_ENHANCEMENT_PRESET: EnhancementPreset = ENHANCEMENT_PRESETS[0]` in `types/domain.ts` and use it at the four frontend sites; add `DEFAULT_PRESET_NAME = "adaptive"` to `auralis/core/config/preset_profiles.py` for `unified_config.py`, `adaptive_mode.py`, the two spectrum-mapper defaults; leave the two SQLAlchemy column defaults as literals with one contract test asserting equality with `schemas.DEFAULT_PRESET` (library may not import web).

##### TD3-20: Two hooks hand-roll the same module-level refcounted WebSocket subscription
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/frontend/src/hooks/library/useArtworkUpdates.ts:65-105` and `hooks/library/useScanProgress.ts:184-262`
- **Status**: NEW
- **Effort**: trivial
- **Description**: Both keep a `let globalRefCount = 0`, install the subscription on 0->1 and tear it down on 1->0 inside a `useEffect`, bypassing `useMessageSubscriptions` (`hooks/websocket/useWebSocketMessages.ts:53`), which is documented as "the single implementation of the subscription lifecycle". `useArtworkUpdates` adds a StrictMode `initialized` ref guard that `useScanProgress` lacks.
- **Impact**: StrictMode / unmount semantics are fixed in one copy only.
- **Suggested Fix**: add `useSharedSubscription(types, handler)` (module-keyed refcount) to `hooks/websocket/useWebSocketMessages.ts` and use it from both.

#### Dimension 4: Magic Numbers & Hardcoded Constants

##### TD4-01: Frontend mirror of backend stream timing has drifted from PROCESSOR_INIT_TIMEOUT and has no parity guard
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/frontend/src/services/audio/audioConstants.ts:57-72`, `auralis-web/frontend/src/hooks/enhancement/useStreamStartWatchdog.ts:6-33`, `auralis-web/backend/core/audio_stream_controller.py:125-126`; sibling `auralis-web/frontend/src/utils/errorHandling.ts:210`
- **Status**: NEW (follow-up of closed #6232, which introduced the mirror but no guard)
- **Age**: mirror a3488cff8 2026-10-25; backend `PROCESSOR_INIT_TIMEOUT = 90.0` added 12ea90cc0 2026-11-16 (#6336)
- **Effort**: small
- **Description**: `BACKEND_STREAM_TIMING` hand-copies three backend values (`chunkIntervalSeconds: 10`, `chunkProcessTimeoutSeconds: 30`, `streamSemaphoreWaitSeconds: 5`) and derives `STREAM_START_WATCHDOG_DERIVED_MS` = 45 s. The file says "update the mirror here in the same commit", but nothing enforces it (no test reads both sides). It has already drifted: #6336 added `PROCESSOR_INIT_TIMEOUT = 90 s` (enhanced-stream init, which now also runs a missing whole-track analysis), so the 45 s watchdog fires at half the backend's own bound, contradicting the watchdog's stated design ("the backend's `audio_stream_error` surfaces first"). The watchdog docstring still names only the 30 s + 5 s terms.
- **Evidence**:
  ```ts
  export const BACKEND_STREAM_TIMING = { chunkIntervalSeconds: 10, chunkProcessTimeoutSeconds: 30, streamSemaphoreWaitSeconds: 5 } as const;
  ```
  ```python
  CHUNK_PROCESS_TIMEOUT: float = 30.0
  PROCESSOR_INIT_TIMEOUT: float = 90.0  # init also runs a missing whole-track analysis (#6336)
  ```
  The `useStreamStartWatchdog` timer (`STREAM_START_WATCHDOG_MS`) is 45 000 ms. `grep -rn BACKEND_STREAM_TIMING tests auralis-web/frontend/src` finds no parity test. The WebSocket heartbeat (`errorHandling.ts:210`, bare `30000`) mirrors `WS_HEARTBEAT_INTERVAL_SECONDS = 30` in `config/limits.py` with no comment or link at all.
- **Impact**: Retuning any backend budget silently desynchronises the client watchdog/heartbeat; the drift above means a slow first-chunk init can be aborted client-side while the backend is still within its budget.
- **Siblings**: `errorHandling.ts:210` heartbeat; `audioConstants.ts` `lowWaterMarkSeconds`/`highWaterMarkSeconds` ("must stay below CHUNK_INTERVAL" is prose only); `audioChunkIngest.ts:28-41` `FLOW_PAUSE_FILL_PCT`/`MAX_PENDING_CHUNK_FRAMES` ("64 frames of ~300 KB") mirror `stream_protocol.TARGET_FRAME_BYTES`.
- **Related**: audit-integration (stream-start watchdog vs init timeout is a behavioural question). Not a bug filing here.
- **Suggested Fix**: Add a small contract test (Python or a generated JSON the vitest suite reads) asserting the mirrored numbers equal `chunk_boundaries.CHUNK_INTERVAL`, `CHUNK_PROCESS_TIMEOUT`, `STREAM_ACQUIRE_TIMEOUT_SECONDS`, `PROCESSOR_INIT_TIMEOUT` (and add the init term to the watchdog derivation), and give the 30 s heartbeat a named `WS_HEARTBEAT_INTERVAL_MS` constant in `config/timing.ts`.

##### TD4-02: The final peak ceiling and limiter timing live in at least seven places with five different values
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/core/hybrid_setup.py:54-59`, `auralis/core/processing/continuous_dsp_ops.py:47`, `auralis/core/processing/base/peak_management.py:26`, `auralis/dsp/dynamics/brick_wall_limiter.py:26`, `auralis/player/config.py:41`, `auralis/player/realtime/auto_master.py:202`, `auralis/core/mastering_presets.py:283`, `auralis/player/realtime/peak_ceiling.py:40-41`
- **Status**: NEW (related closed #6339, #6310 which touched copies of `SAFE_CEILING_DB` but left the underlying multiplicity)
- **Age**: hybrid_setup literal 22d0228c8 2026-09-16; `SAFE_CEILING_DB` 53e58f572 2026-08-21
- **Effort**: small
- **Description**: "How hot may the output get" is spelled: bare `threshold_db=-0.3, lookahead_ms=2.0, release_ms=50.0` in `hybrid_setup.py` (the HybridProcessor brick-wall limiter); `SAFE_CEILING_DB = -0.3` in `continuous_dsp_ops.py` (a second, separate `-0.3`, which `analysis/reference_profile.py` imports from `core.processing` just to alias it as `SAFE_CEILING_DBFS`); `SAFETY_THRESHOLD_DB = -0.1` in `peak_management.py`; `threshold_db = -0.5` default in `BrickWallLimiter`; `LOUDNESS_LIMITER_CEILING_DB = -1.0` in `mastering_presets.py` (this one is legitimately a different stage); `realtime_safety_peak = 0.95` in `PlayerConfig` (its comment says it should "agree" with the -0.3 dBFS limiter and does not); `0.98 / processed_peak` inline in `auto_master.py`; and `lookahead 2.0 / release 50.0` repeated as `StreamingPeakCeiling` defaults. The agreement between these is documented only in comments.
- **Evidence**:
  ```python
  processor.brick_wall_limiter = create_brick_wall_limiter(threshold_db=-0.3, lookahead_ms=2.0, release_ms=50.0, ...)   # hybrid_setup.py
  SAFE_CEILING_DB = -0.3                                                                                              # continuous_dsp_ops.py
  max_safe_gain_db = 20 * np.log10(0.98 / processed_peak)                                                              # auto_master.py:202
  ```
- **Impact**: Changing the output ceiling means touching up to four independent literals; the realtime path and the offline path already disagree (0.95 vs 0.966 vs 0.98 linear). `analysis/` importing a constant from `core/processing/continuous_dsp_ops` is an upward layering smell caused by the missing shared home.
- **Siblings**: `fixed_target_params.py:78,85` (`-1.0` peak target), `analysis/adaptive_mastering_engine.py:266` (`peak_dbfs=-0.1`), `quality_metrics.py:55` / `loudness_assessment.py:146` (`-1.0` true-peak ceiling, which `AssessmentConstants.SPOTIFY_MAX_TRUE_PEAK` already names).
- **Related**: audit-engine (realtime 0.95 vs offline -0.3 dBFS is a behaviour question).
- **Suggested Fix**: Add `OUTPUT_PEAK_CEILING_DB = -0.3`, `LIMITER_LOOKAHEAD_MS = 2.0`, `LIMITER_RELEASE_MS = 50.0` beside `LOUD_MASTER_TARGET_LUFS` in `auralis/dsp/utils/loudness_targets.py` (dsp is the lower layer, per that module's own rationale); have `hybrid_setup`, `continuous_dsp_ops`, `reference_profile` and `StreamingPeakCeiling` import them, and derive `realtime_safety_peak` as `10 ** (OUTPUT_PEAK_CEILING_DB / 20)` or document it as the deliberate exception next to the constant.

##### TD4-03: Default sample rate 44100 has no named home; ~18 constructors, 3 backend fallbacks and four other "nominal rate" constants retype it
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:38`, `dsp/dynamics/settings.py:70`, `dsp/dynamics/brick_wall_limiter.py:29`, `analysis/spectrum_analyzer.py:34`, `analysis/loudness_meter.py:35`, `analysis/dynamic_range.py:18`, `analysis/phase_correlation.py:22`, `analysis/quality/quality_metrics.py:51`, `analysis/quality/mastering_evaluation.py:21`, `analysis/mastering_fingerprint.py:84`, `analysis/ml/feature_extractor.py:53`, `core/analysis/content_analyzer.py:30`, `core/config/unified_config.py:41,52`, `player/config.py:19`, `player/audio_file_manager.py:32`, `player/realtime/peak_ceiling.py:40`, `auralis-web/backend/core/level_transition.py:72`, `backend/core/chunk_render.py:95`, `backend/core/chunked_processor.py:122`, `backend/cache/models.py:31`
- **Status**: NEW (the closed #4622 deliberately scoped itself to dsp/ and core/processing/ call-through helpers; #5729 is the broader closed tracker; this is the explicitly-left-out remainder, count still 20 in the Phase 1 baseline)
- **Age**: n/a (accumulated)
- **Effort**: medium
- **Description**: The "assume 44.1 kHz when nothing else is known" default is retyped as `44100` in ~18 class constructors/dataclasses; three backend fallbacks write `processor.sample_rate or 44100` (two of them only to narrow `int | None`); `UnifiedConfig.internal_sample_rate` (the supposed config authority) is one more copy plus a second `!= 44100` literal; and several modules invented their own named variant (`DEFAULT_CLASSIFIER_SAMPLE_RATE` in `analysis/ml/genre_classifier.py:23`, `_NOMINAL_SAMPLE_RATE` in `cache/models.py:31`, frontend `DEFAULT_STREAM_SAMPLE_RATE`, `library/models/settings.py:41` ORM default). The fingerprint rate got a proper constant (`FINGERPRINT_SAMPLE_RATE`), the general default did not.
- **Evidence**: `grep -RIn -E 'sample_rate\s*:?\s*(int)?\s*=\s*44100' auralis auralis-web/backend` returns 18 non-test, non-docstring hits.
- **Impact**: Each retyped default is a place where "load metadata before processing" can be silently skipped (the latent hazard #4622 described); the `or 44100` fallbacks hide a None that the code claims cannot happen.
- **Siblings**: `auralis/library/models/settings.py:41`; `auralis-web/backend/routers/files.py:101` (enum list, spec: do not flag).
- **Related**: #4622 (closed, scope-limited), #5729 (closed), #5306 (closed HIGH — the live bug this hazard produced once).
- **Suggested Fix**: Add `DEFAULT_SAMPLE_RATE = 44100` to `auralis/dsp/constants.py` (already the "single owner for numeric conventions", #6229) and point `UnifiedConfig`, `PlayerConfig`, and the analysis/dsp constructors at it; replace the two `or 44100` narrowings with an explicit `assert`/`ValueError` on missing metadata, and fold the ad-hoc variants into the same constant.

##### TD4-04: Normal-path chunk count is a second counting formula in the chunk SoT module
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:177-181,198`
- **Status**: NEW
- **Age**: eac5ec87a 2026-08-25
- **Effort**: trivial
- **Description**: CLAUDE.md names `content_chunk_count()` as "the sole chunk-counting authority". `plan_normal_stream` computes `total_chunks = max(1, int(np.ceil(total_frames / interval_samples)))` where `interval_samples = chunk_samples = CHUNK_DURATION * sr` — literally the `ceil(duration / CHUNK_DURATION)` form the invariant forbids. It is correct for the normal (non-overlapping 15 s) path, but it is an unnamed exception inside the very module that claims authority, and the `seek_offset = pos - start_chunk * chunk_duration` on the next lines is the same unnamed geometry.
- **Evidence**:
  ```python
  chunk_samples = int(chunk_duration * sample_rate)
  interval_samples = chunk_samples  # No overlap for the normal path.
  total_chunks = max(1, int(np.ceil(total_frames / interval_samples)))
  ```
- **Impact**: A future reader (or audit) cannot tell whether the normal path is an intentional second geometry or a missed migration; a change to either formula will not be applied to both.
- **Siblings**: none in the backend (`grep ceil(` finds only this and `content_chunk_count`).
- **Related**: —
- **Suggested Fix**: Extract `normal_chunk_count(total_frames, sample_rate)` next to `content_chunk_count` with a docstring stating the intentional difference (no overlap, `CHUNK_DURATION` stride), and name the stride `NORMAL_CHUNK_STRIDE = CHUNK_DURATION`.

##### TD4-05: CHUNK_INTERVAL and OVERLAP_DURATION are hand-typed instead of derived from CHUNK_DURATION
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:19-23`
- **Status**: NEW
- **Age**: n/a
- **Effort**: trivial
- **Description**: The "SINGLE SOURCE OF TRUTH" block types four independent floats: `CHUNK_DURATION = 15.0`, `CHUNK_INTERVAL = 10.0 # (CHUNK_DURATION - OVERLAP_DURATION)`, `OVERLAP_DURATION = 5.0`, `CONTEXT_DURATION = 5.0`. The comment states the relationship that the code does not enforce; it is pinned only by `tests/backend/test_enhanced_seek_accuracy.py:257`. `emitted_chunk_start`, `content_chunk_count` and `extract_chunk_segment` all rely on it.
- **Evidence**: `CHUNK_INTERVAL = 10.0  # seconds - playback interval (CHUNK_DURATION - OVERLAP_DURATION)`
- **Impact**: Editing one literal compiles fine and only a test notices; anyone changing chunk size has to edit three lines in lockstep.
- **Siblings**: `chunk_segment_extraction.py:32-34` and `chunk_file_loading.py:37-38` take `chunk_duration`/`chunk_interval`/`overlap_duration` as three independent default parameters (again with no relationship check).
- **Related**: —
- **Suggested Fix**: Keep `CHUNK_DURATION = 15.0` and `OVERLAP_DURATION = 5.0` as the inputs and write `CHUNK_INTERVAL = CHUNK_DURATION - OVERLAP_DURATION`; drop the redundant `overlap_duration` parameter in `extract_chunk_segment` in favour of `chunk_duration - chunk_interval`.

##### TD4-06: Chunk-failure fallback emits a bare 0.1 s of silence (three copies, one with hard-coded 2 channels)
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/core/chunk_file_loading.py:109,159`, `auralis-web/backend/core/chunk_render.py:170`
- **Status**: NEW
- **Age**: 0599e61e7 2026-10-23 (line 109)
- **Effort**: trivial
- **Description**: Three error paths return "100 ms of silence" as `int(0.1 * sample_rate)` / `sample_rate // 10`; the first hard-codes `2` channels, the others derive channels, and the log text repeats "100ms". None is named. The value is also unrelated to chunk geometry (a chunk is 10-15 s), so a failed chunk shortens the emitted timeline.
- **Evidence**: `silence = np.zeros((int(0.1 * sample_rate), 2), dtype=np.float32)`
- **Impact**: Three places to retune and one latent channel-count mismatch; the sample-count consequence is the reason to name it.
- **Siblings**: `cache/…` none.
- **Related**: audit-engine / audit-backend (a failed chunk that emits 0.1 s instead of its `CHUNK_INTERVAL` length breaks the "never change sample count" timeline invariant for the failure path; owning audit decides whether it is a bug).
- **Suggested Fix**: One helper in `chunk_boundaries.py` (`silence_fallback(sample_rate, channels, dtype)`) with a named `FALLBACK_SILENCE_SECONDS = 0.1`, used by all three sites.

##### TD4-07: stream_protocol defines its frame-byte budget as function-local "constants"
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/core/stream_protocol.py:181-184`
- **Status**: NEW
- **Age**: 5b3a133fd 2026-07-11
- **Effort**: trivial
- **Description**: `TARGET_FRAME_BYTES: int = 300 * 1024` and `BYTES_PER_SAMPLE: int = 4` are upper-case names assigned inside the send function body, so they look like module constants but cannot be imported, tested, or referenced. The frontend independently encodes the same budget in prose ("64 frames of ~300 KB", `audioChunkIngest.ts:37-41`) and the `# was 400KB base64` comment is stale history. Its sibling `_SEND_QUEUE_MAXSIZE` (env-tunable, module level) shows the intended pattern.
- **Evidence**: see Location.
- **Impact**: Frame sizing cannot be asserted in a test without re-deriving it; the 1 MB WS-frame-limit rationale lives in a comment.
- **Siblings**: `backend/cache/models.py:33` `_PCM16_BYTES_PER_SAMPLE`, `frontend pcmRingOps.ts` (each names its own bytes-per-sample).
- **Related**: —
- **Suggested Fix**: Hoist to module level (`PCM_FRAME_TARGET_BYTES`, `FLOAT32_BYTES`) next to `_SEND_QUEUE_MAXSIZE`; reference the name from the frontend mirror comment (and TD4-01's parity test).

##### TD4-08: `build_resource_monitor` retypes every ResourceLimits default and logs a stale "workers: 4-32"
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/services/fingerprint_queue_scaling.py:34-43,50-52,66-92`, `auralis/library/resource_monitor.py:23-31`
- **Status**: NEW
- **Age**: 3276792cf 2026-08-16
- **Effort**: small
- **Description**: `ResourceLimits(...)` is constructed with `max_memory_percent=75.0`, `check_interval=2.0`, `scale_up_threshold=50.0`, `scale_down_threshold=80.0` — exactly the dataclass defaults — plus `max(8, max_workers)` retyped twice (semaphore size and `max_semaphore`). Worker bounds are `max(4, int(cpu_count * 0.5))` and `int(cpu_count * 2.0)` with `os.cpu_count() or 16`, while `ResourceLimits.min_workers=4 / max_workers=32` are a third statement of the worker range, and `start_resource_monitor` logs the literal `"workers: 4-32"` even though `max_workers` is `2 x cpu_count` (e.g. 48 on a 24-core host).
- **Evidence**: `info("Adaptive resource monitor started (RAM threshold: 75%, workers: 4-32)")`
- **Impact**: Tuning RAM thresholds means editing the dataclass *and* this builder (the builder silently wins); the log line misreports the live bounds.
- **Siblings**: `auralis/services/fingerprint_queue.py` docstring example `num_workers=16`.
- **Related**: closed #6140 (same module, semaphore size assumption).
- **Suggested Fix**: Build `ResourceLimits(min_workers=..., max_workers=..., max_semaphore=...)` and let the dataclass supply the thresholds; name `MIN_PROCESSING_PERMITS = 8`, `MIN_WORKERS_FLOOR = 4`, `WORKERS_PER_CORE_INITIAL/CEILING`; log from `limits` instead of a literal.

##### TD4-09: Worker-loop cadences and caps are inline literals (backend and engine)
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/core/streamlined_lifecycle.py:101` (`sleep(1.0)`), `core/position_ticker.py:106` (`sleep(1.0)`), `core/job_worker.py:264` (`sleep(1)`), `analysis/fingerprint_queue.py:250,278` (`sleep(0.5)`, `sleep(1)`), `core/proactive_buffer.py:46` (`sleep(0.1)`), `core/streamlined_worker.py:233` (`sleep(0.05)`), `services/library_auto_scanner.py:131` (`_interruptible_sleep(30)`), `core/level_manager.py:46-47` (`deque(maxlen=256)` twice), `core/seekable_source.py:85` (`lru_cache(maxsize=64)`), `auralis/services/fingerprint_queue.py:255,273` (`sleep(0.1)`), `auralis/player/gapless_playback_engine.py:269` / `resource_monitor.py:97` (`join(timeout=5.0)`), `auralis/player/enhanced_audio_player.py:280` (`join(timeout=2.0)`), `auralis/io/loader.py:60-63` (`6 * 1024 ** 3` typed twice)
- **Status**: NEW
- **Age**: n/a (accumulated)
- **Effort**: small
- **Description**: The backend's *tunable* budgets are named (`CHUNK_PROCESS_TIMEOUT`, `STREAM_ACQUIRE_TIMEOUT_SECONDS`, `FLOW_GATE_TIMEOUT_S`, `SEND_QUEUE_MAXSIZE`, `BROADCAST_SEND_TIMEOUT`, ...) but the poll/backoff cadences of the background loops are not: three different "back off 1 s after an unexpected error" literals, "0.05/0.1 s to avoid CPU saturation" delays after cached/buffered chunks, a 30 s scanner crash back-off, and thread-join grace periods. `level_manager.py` types the history cap `256` twice next to a `level_constants.py` that exists for exactly this module; `loader.py` types its `6 GiB` default in both the `try` and the `except` branch.
- **Evidence**: `await asyncio.sleep(1)  # Prevent tight loop on persistent errors` (fingerprint_queue.py:278 and job_worker.py:264, identical meaning).
- **Impact**: Low individually; collectively the loop timing cannot be tuned or tested (tests monkeypatch `asyncio.sleep` instead of a constant).
- **Siblings**: `auralis-web/backend/services/similarity_autofit_worker.py:38,42` are already named (`_STOP_TIMEOUT_SECONDS`, `_CHECK_INTERVAL_SECONDS`) — the pattern to follow.
- **Related**: —
- **Suggested Fix**: One `ERROR_BACKOFF_S = 1.0` plus per-loop `*_POLL_S` / `*_YIELD_S` module constants (in `config/limits.py` or the owning module), `LEVEL_HISTORY_MAXLEN` in `level_constants.py`, and a single `_DEFAULT_MAX_DECODED_BYTES` in `loader.py`.

##### TD4-10: Retention / max-age windows are scattered across three units with no shared home
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/core/processing_engine.py:85,265` (`completed_job_ttl_hours=1.0`, `cleanup_old_jobs(max_age_hours=24)`), `routers/processing_jobs.py:169` (`Query(24, gt=0)`), `config/startup/tempfiles.py:58` and `config/startup/decode_temps.py:22` (`max_age_hours=1.0`), `core/encoding/atomic_io.py:51` (`PARTIAL_MAX_AGE_SECONDS=3600.0`), `core/thumbnail_cache.py:59` (`TEMP_FILE_MAX_AGE_SECONDS=300.0`), `core/job_store.py:147` / `core/job_cleanup.py:67` / `tempfiles.py:97,199` (inline `* 3600`)
- **Status**: NEW
- **Age**: n/a
- **Effort**: small
- **Description**: Cleanup ages are expressed in hours in four modules and seconds in two, with the `24` default typed independently in the engine method and the router `Query`, the `1.0 h` stream/decode temp age typed in two startup helpers, and `* 3600` unit conversions inline in four places. `config/limits.py` already hosts the env-tunable budgets and `CONFIG.md` documents them, but none of these appear there.
- **Evidence**: `async def cleanup_old_jobs(self, max_age_hours: float = 24)` and `max_age_hours: float = Query(24, gt=0)`.
- **Impact**: "Why was my temp file/job deleted" requires reading six modules; the router default and engine default can diverge.
- **Siblings**: —
- **Related**: —
- **Suggested Fix**: Add `STALE_TEMP_MAX_AGE_S`, `COMPLETED_JOB_TTL_S`, `JOB_CLEANUP_DEFAULT_AGE_S` to `config/limits.py` (seconds throughout) and have the router and engine read the same constant.

##### TD4-11: Artwork limits defined twice (one copy is dead) plus redirect cap duplicated
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/library/artwork.py:33` (`_MAX_ARTWORK_DIMENSION = 2048`), `auralis/utils/artwork_security.py:75` (`MAX_ARTWORK_DIMENSION = 2048`), `auralis-web/backend/routers/artwork.py:72` (`le=2048`), `auralis-web/backend/services/artwork_providers/trust.py:27` and `services/artwork_downloader.py:54` (`_MAX_ARTWORK_REDIRECTS = 5` each)
- **Status**: NEW
- **Age**: a1b90cb55 2026-10-25 (library/artwork.py copy)
- **Effort**: trivial
- **Description**: `artwork.py`'s private `_MAX_ARTWORK_DIMENSION` is never referenced (the only hit is its definition; the live check is `bound_artwork_dimensions` in `artwork_security.py`), and its comment says it "matches the GET endpoint's maximum requestable size (le=2048)", which is a third literal. The redirect cap `5` is defined separately in the provider trust module and the downloader.
- **Evidence**: `grep -rn _MAX_ARTWORK_DIMENSION auralis auralis-web` returns only the definition.
- **Impact**: A dead constant that looks authoritative; the two redirect caps can drift apart.
- **Siblings**: —
- **Related**: closed #6153 (the artwork-bound fix lives in `artwork_security.py`).
- **Suggested Fix**: Delete `_MAX_ARTWORK_DIMENSION`; import `MAX_ARTWORK_DIMENSION` in `routers/artwork.py` for `le=`; export one `MAX_ARTWORK_REDIRECTS` from `artwork_providers/trust.py` and import it in `artwork_downloader.py`.

##### TD4-12: Backend port 8765 is still typed in five non-test locations outside the config layer
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/frontend/vite.config.mts:112,116`, `auralis-web/frontend/src/config/api.ts:43`, `launch-auralis-web.py:57,132`, `desktop/preload.js:20` (sandboxed, pinned by `preload.test.js`), `desktop/url-safety.js:30` (Electron's own constant, wired through `backend-env.js`)
- **Status**: NEW (follow-up to closed #5796 which unified backend `main.py`/`origins.py`, and closed #6170 which did the Electron side)
- **Age**: n/a
- **Effort**: small
- **Description**: `config/origins.py` is the backend authority (`BACKEND_PORT = get_int_env("AURALIS_PORT", 8765)`). Remaining copies: the Vite dev proxy (`/api`, `/ws` targets, two literals), the dev-mode WebSocket fallback in `api.ts`, and the launcher's `start_backend(port=8765)` and argparse default (typed twice in one file). The Electron pair is a justified exception (sandboxed preload cannot import; `preload.test.js` pins it), but the other three are unpinned, so `AURALIS_PORT=9000` moves the backend while the dev proxy and WS fallback keep targeting 8765.
- **Evidence**: `target: 'http://localhost:8765'` / `'ws://localhost:8765'` in `vite.config.mts`.
- **Impact**: Dev-mode port override is half-supported; each runtime has its own copy.
- **Siblings**: —
- **Related**: #5796, #6170 (closed, partial scope).
- **Suggested Fix**: In `vite.config.mts` read `process.env.AURALIS_PORT ?? 8765` once and build both proxy targets from it; in `launch-auralis-web.py` define `DEFAULT_PORT = 8765` once (or import `BACKEND_PORT`); have `api.ts` derive the dev fallback from `import.meta.env.VITE_BACKEND_PORT`.

##### TD4-13: Two library lists and one search box bypass the named frontend constants
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/frontend/src/components/library/Items/artists/CozyArtistList.tsx:62` (`limit: 50`), `components/library/Items/albums/CozyAlbumGrid.tsx:88` (`limit: 50`), `components/library/CozyLibraryView.tsx:84` (`setTimeout(..., 250)`), `services/playlistService.ts:74` (`PLAYLISTS_PAGE_LIMIT = 200`)
- **Status**: NEW (sibling gap of closed #6217 and #5800, whose own file lists omit these call sites)
- **Age**: 24877c825 2026-10-24
- **Effort**: trivial
- **Description**: #6217 introduced `LIBRARY_PAGE_LIMIT = 50` / `LIBRARY_MAX_PAGE_LIMIT = 200` and #5800 `SEARCH_DEBOUNCE_MS = 300`, yet the artist list and album grid still pass the literal `50`, the library view's top-bar search debounces at `250` (so two debounces with different values now coexist: 250 here, 300 in `SearchBar`/`useSearchLogic`/`useSearchInput`), and `PLAYLISTS_PAGE_LIMIT = 200` restates the backend max rather than using `LIBRARY_MAX_PAGE_LIMIT`.
- **Evidence**: `useArtistsQuery({ limit: 50, search })`; `const t = setTimeout(() => setDebouncedSearch(searchQuery), 250);`
- **Impact**: Changing the page size or the debounce leaves these three behind.
- **Siblings**: —
- **Related**: #6217, #5800 (closed).
- **Suggested Fix**: Replace the literals with `LIBRARY_PAGE_LIMIT`, `SEARCH_DEBOUNCE_MS`, `LIBRARY_MAX_PAGE_LIMIT` (import from `@/config/api` / `@/config/timing`).

##### TD4-14: Design-system tokens retype raw RGB triplets and hex values instead of deriving them; one component hard-codes a three-stop hsla ramp
- **Severity**: LOW
- **Dimension**: Magic Numbers (frontend hardcoded colors; reported here, not as an /audit-frontend finding)
- **Location**: `auralis-web/frontend/src/design-system/tokens/colors.ts` (`115, 102, 240` x16, `#7366F0` x4 incl. gradient), `tokens/effects.ts:25-30` (`115, 102, 240`, `71, 214, 255`), `tokens/surfaces.ts:13-38,60-100` (`rgba(21, 29, 47, …)` x10 = `bg.level2 #151D2F`; gradient stops `#5A5CC4 #47D6FF #00BCC4 #7366F0`), `colors.ts` `#F59E0B` x4, `#10B981` x3, `#EF4444` x3, `#DC2626` x3; `components/library/AlbumCharacterPane/EnergyField.tsx:77-79`
- **Status**: NEW
- **Age**: n/a
- **Effort**: small
- **Description**: Outside `design-system/` the frontend is clean: no hex/rgb literal in any component, hook or style file except the redux-logger console palette (explicitly documented as dev-tooling, #6234, not flagged) and data-driven `hsla(${hue}, …)` in `AlbumCharacterPane` (hue comes from the fingerprint). The residue is inside the token layer: each token category is "self-contained" by comment, so `effects.ts`, `surfaces.ts` and `colors.ts` re-spell the same brand RGB channels and hex values (`semantics.ts` already uses `withOpacity(colors.bg.level0, …)` correctly), and `EnergyField.tsx` hard-codes `hsla(210…) → hsla(45…) → hsla(15…)` as its cool-to-warm ramp. `--accent-rgb: 115, 102, 240` in `globalStyles.ts` is test-pinned to the accent token (`accentChannels.test.ts`) — the pattern to follow.
- **Evidence**: `glowSoft: '0 0 16px rgba(115, 102, 240, 0.20)'` (effects.ts) next to `primary: '#7366F0'` (colors.ts); `background: 'rgba(21, 29, 47, 0.55)'` x10 (surfaces.ts) next to `level2: '#151D2F'`.
- **Impact**: A brand-colour retune requires editing ~35 literals across three files; `withOpacity` exists but is used only in `semantics.ts` of the token files.
- **Siblings**: `colors.ts:216-232` light-theme block duplicates `#DC2626`, `#3B82F6` from the dark semantic block (intended per-theme contrast values; comment-documented, so not counted).
- **Related**: closed #4463 (same duplication class, brand fallback).
- **Suggested Fix**: Build glows/glass/overlay strings in `effects.ts`/`surfaces.ts` from `withOpacity(colors.accent.primary, α)` / `withOpacity(colors.bg.level2, α)` (token-internal import is fine; update the "no cross-category references" comment), reuse `colors.semantic.*` in `status`/`button` entries, and move the EnergyField ramp to `tokens.gradients`/`audioSemantic` tokens.

##### TD4-15: Residual bare loudness literals and duplicated assessment ranges
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/core/analysis/spectrum_mapper/content_modifiers.py:34,158,196,234`, `auralis/core/analysis/target_fingerprint_adjustments.py:87`, `auralis/analysis/quality/loudness_assessment.py:25-27`, `auralis/analysis/quality/quality_metrics.py:53-55`, `auralis/dsp/utils/adaptive_loudness.py:32-33`, `auralis/core/processing/parameter_generator_dynamics.py:48`
- **Status**: NEW (the closed #6226 / #5795 named `DEFAULT_TARGET_LUFS`/`STREAMING_TARGET_LUFS`/`LOUD_MASTER_TARGET_LUFS`; these sites were not converted)
- **Age**: n/a
- **Effort**: small
- **Description**: `content_modifiers.py` falls back to `-16.0` LUFS (twice) and `-14.0` (twice) and blends with ten literal fractions (`* 0.3 … * 0.7`); `target_fingerprint_adjustments.py:87` clamps at `min(-12.0, …)` next to a correctly named `DEFAULT_TARGET_LUFS`; the optimal `(-16.0, -14.0)` / acceptable `(-20.0, -10.0)` / `-1.0` true-peak triple is typed in both `LoudnessAssessor.__init__` and `QualityMetrics.__init__` (the true-peak one even though `AssessmentConstants.SPOTIFY_MAX_TRUE_PEAK` is imported two lines away in the first); `adaptive_loudness.py` has `VERY_LOUD_THRESHOLD = -12.0` / `MODERATELY_LOUD_THRESHOLD = -14.0` with no link to the named targets; `parameter_generator_dynamics.py:48` `reference_lufs = -12.0`.
- **Evidence**: `preset_target_lufs = preset_profile.target_lufs if preset_profile else -16.0`.
- **Impact**: Moving the default loudness anchor still requires a grep despite #5795/#6226.
- **Siblings**: —
- **Related**: #6226 (closed).
- **Suggested Fix**: Add `OPTIMAL_LUFS_RANGE`, `ACCEPTABLE_LUFS_RANGE` to `AssessmentConstants` and use them in both assessors; name the `-16.0`/`-14.0` fallbacks in `loudness_targets.py` (`QUIET_PRESET_FALLBACK_LUFS`) or derive them from `DEFAULT_TARGET_LUFS`.

##### TD4-16: Engine EQ band edges and content thresholds are inline in three helpers, separate from the fingerprint band table
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/core/processing/eq_processor.py:130-159,189-198`, `auralis/dsp/utils/stereo.py:178-182,218-232`, `auralis/core/processing/continuous_guards.py:99`; related tables `auralis/analysis/reference_profile.py:28`, `auralis/dsp/constants.py:30-38`
- **Status**: NEW
- **Age**: eq_processor 1639f0b42 2026-10-25
- **Effort**: medium
- **Description**: `EQProcessor` hard-codes band boundaries (`< 250`, `< 500`, `< 2000`, `< 4000` Hz), spectral-centroid cut-offs (`> 3500`, `< 1000`), a dynamic-range gate (`> 25`, `< 10`) and a genre multiplier table (`1.2 / 0.8 / 1.3 / 1.1`) inside `_apply_content_adjustments`/`_targets_to_eq_curve`; `stereo.py` retypes its own band corners (`300 / 2000 / 8000 / 16000 Hz`, `0.3 + 0.7` ramp) and `continuous_guards.py` a 250 Hz shelf. Meanwhile three other band definitions exist (`CORPUS_BAND_CENTERS` in `dsp/constants.py`, the fingerprint band fractions, `BAND_EDGES_HZ` in `reference_profile.py`). The code is reachable (`apply_psychoacoustic_eq` from `adaptive_mode.py:124` and `continuous_dsp_ops.py:78`). The mastering-parameter generators (`parameter_generator_dynamics.py` etc.) were reviewed and are not flagged: their inline coefficients are the continuous mapping itself.
- **Evidence**: `if centroid > 3500:  # Very bright content` / `eq_curve['treble_boost'] *= 0.7`.
- **Impact**: Four modules define "where bass ends" independently; tuning the EQ voicing means editing code, not config.
- **Siblings**: `auralis/analysis/ml/genre_weights.py:18` records that an earlier genre-scaling block in this same method was already retired once.
- **Related**: audit-engine owns whether the multipliers are musically right.
- **Suggested Fix**: Move the band edges to one tuple in `dsp/constants.py` and the content/genre multipliers to a frozen table in `auralis/core/config/` (UnifiedConfig layer), importing both from `eq_processor.py` and `stereo.py`.

##### TD4-17: Engine "chunk" constants share names with the backend's but mean something else
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/core/mastering_config.py:87-97` (`CHUNK_DURATION_SEC: int = 30`, `CROSSFADE_DURATION_SEC = 3.0`), `auralis/core/mastering_prepare.py:217`, `auralis/core/mastering_chunk_loop.py:67-70` vs `auralis-web/backend/core/chunk_boundaries.py:20`
- **Status**: NEW
- **Age**: n/a
- **Effort**: trivial
- **Description**: The offline file-master chunk loop has its own geometry (30 s core, 3 s crossfade, sequential with carried context), which is legitimate and documented in the Retired Architecture table. But it is spelled `CHUNK_DURATION_SEC` while the streaming SoT is `CHUNK_DURATION` (15.0), so a grep for chunk-geometry bypasses (the check this audit dimension prescribes) lands on it, and `mastering_prepare.py` reuses `config.CHUNK_DURATION_SEC` as the loudness *scan block* size, coupling an analysis block to a render chunk size.
- **Evidence**: `scan_block_frames = sr * config.CHUNK_DURATION_SEC`
- **Impact**: Two unrelated chunk geometries with near-identical names invite a future "unify the chunk constant" edit that would change offline mastering length or the stream timeline.
- **Siblings**: —
- **Related**: —
- **Suggested Fix**: Rename the engine fields `FILE_MASTER_CHUNK_SEC` / `FILE_MASTER_CROSSFADE_SEC`, give the scan block its own `LOUDNESS_SCAN_BLOCK_SEC`, and add a one-line comment pointing at `chunk_boundaries.py` as the *streaming* authority.

#### Dimension 5: Stub & Placeholder Implementations

##### TD5-01: Processing-job API accepts `eq` / `dynamics` / `level_matching` / `genre_override` / `sample_rate` / `fingerprint` and applies none of them
- **Severity**: LOW
- **Dimension**: Stub Implementations
- **Location**: `auralis-web/backend/core/job_config.py:27-118`, `auralis-web/backend/routers/processing_models.py:40-52` (`ProcessingSettings`), `auralis-web/backend/core/job_models.py:66-71`, `auralis-web/backend/core/job_finalize.py:100-102`
- **Status**: NEW (the closed #5060 / #3490 only made the no-op visible; the fields were never wired or removed)
- **Age**: de35981be 2026-08-22 (`ignored_settings` reporting added); fields themselves older
- **Effort**: small (delete the fields + the reporting) — or large if the intent is to wire them (#3490 follow-up)
- **Description**: `POST /api/processing/process` takes a `ProcessingSettings` whose `eq`, `dynamics`, `level_matching`, `genre_override`, `sample_rate` fields are validated, stored on the job, then ignored: `create_processor_config()` builds a `UnifiedConfig` from `mode` and `sample_rate` only, collects every requested-but-unused key into `job.ignored_settings`, logs INFO, and returns. The offline pipeline derives all of these from its own fingerprint analysis. The docstring says "Until those readers exist (tracked as the wire-up follow-up for #3490)" and the log says "See #3490 for the wire-up plan" — #3490 is CLOSED, so the deferral points at nothing live and is prose, not a `TODO(#NNNN)`.
- **Evidence**:
  ```python
  # core/job_config.py
  if eq_settings and eq_settings.get("enabled"): unsupported.append("eq")
  ...
  job.ignored_settings = unsupported
  logger.info("... accepted but not consumed by the offline pipeline ... See #3490 for the wire-up plan.", ...)
  ```
  No frontend source references `/api/processing` at all (only `src/test/mocks/handlers.ts:1161`), so there is no UI consumer for these fields either.
- **Impact**: A shipped route advertises five/six controls that cannot change the output; every future reader of `ProcessingSettings` has to rediscover this; `ignored_settings` plumbing (model, finalize, response schema, tests) exists only to describe the no-op.
- **Siblings**: `core/job_models.py:66`, `core/job_finalize.py:100`, `schemas`/response model carrying `ignored_settings`, tests pinning the ignored list.
- **Related**: #5060 (CLOSED), #3490 (CLOSED, cited as the live deferral). Not a bug, so no owning audit; promotion to MEDIUM per the table (stub reachable from a shipped route) was considered and rejected because the no-op is reported to the client rather than silent.
- **Suggested Fix**: Remove `eq`, `dynamics`, `level_matching`, `genre_override`, `fingerprint` (and the `sample_rate` knob) from `ProcessingSettings` (422 at the boundary instead of 200-and-ignore), then delete `ignored_settings` and the `unsupported` bookkeeping in `create_processor_config()`. If wiring is still wanted, file it and leave a `TODO(#NNNN)` that cites an OPEN issue.

##### TD5-02: Four `ProcessingParameters` fields (plus compressor threshold/attack/release) are generated every chunk but read by no DSP stage, and are served to clients as live engine state
- **Severity**: LOW
- **Dimension**: Stub Implementations
- **Location**: `auralis/core/processing/parameter_generator_dynamics.py:94-190` (`generate_compression` threshold/attack/release, `generate_expansion`, `calculate_dynamics_blend`, `generate_limiter`), `auralis/core/processing/processing_parameter_readers.py:19-21` (`REPORTING_ONLY_FIELDS`), `auralis/core/processing/fixed_target_params.py:67-91`, `auralis-web/backend/routers/processing_parameters.py:162-175`
- **Status**: NEW (closed #5576 documented the situation with `REPORTING_ONLY_FIELDS` and a pinning test; the placebo values are all still generated and exposed)
- **Age**: 476854de8 2026-10-28 (file last touched); #5576 2026-10-16
- **Effort**: medium
- **Description**: `peak_target_db`, `dynamics_blend`, `limiter_params`, `expansion_params` are "produced for display and for the fixed-target schema contract but are not read by any DSP stage" (module docstring). `continuous_dsp_ops.py:103-110` removed the expansion stage (#5561) but left its parameter generator. `generate_compression()` still emits `threshold`, `attack`, `release` that "describe the intended compressor character for reporting" while the stage is an instantaneous waveshaper. `GET /api/processing/parameters` then returns `expansion_amount`, `peak_target_db`, `compression_amount` under the docstring "This shows what the auto-mastering engine is doing in real-time" — values that do not describe anything the engine does. Both the dynamic generator and the fixed-target fast path (`fixed_target_params.py`) must keep producing them in lockstep.
- **Evidence**: `REPORTING_ONLY_FIELDS = frozenset({'peak_target_db', 'dynamics_blend', 'limiter_params', 'expansion_params'})`; `processing_parameters.py:175 "expansion_amount": get_attr(params, 'expansion_params', {}).get('amount', 0.0)`; `continuous_dsp_ops.py:108 "the generator's expansion_params remain available as reporting data."`
- **Impact**: Tuning these functions changes nothing audible but looks like tuning; two generation paths (dynamic + fixed-target) to keep consistent; a router that reports placebo data as telemetry.
- **Siblings**: `auralis/core/processing/continuous_space_types.py:42-59` (dataclass fields + comments), `auralis/core/processing/parameter_generator.py:113-123` (thin wrappers for the three reporting-only generators), `auralis/core/processing/fixed_target_params.py:67-91`.
- **Related**: #5576, #5561, #5309 (all CLOSED). Owning audit for the "endpoint misreports engine state" angle: audit-backend / audit-integration.
- **Suggested Fix**: Delete `generate_expansion`, `generate_limiter`, `calculate_dynamics_blend` and the four reporting-only dataclass fields together with `REPORTING_ONLY_FIELDS` and its pinning test; trim compression to `ratio`/`amount`; drop the corresponding keys from `GET /parameters` (or keep only measured fields). Do it as one change so the dynamic and fixed-target paths cannot diverge.

##### TD5-03: `HybridProcessor.close()` disposal chain releases nothing, and its only target's `close()` is a documented no-op
- **Severity**: LOW
- **Dimension**: Stub Implementations
- **Location**: `auralis/core/hybrid_processor.py:41-56,96-128`, `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:74-78`, `auralis/library/sidecar_manager.py:47`; callers `auralis/core/hybrid_processor_singleton.py:90-97`, `auralis-web/backend/core/processor_pool.py:87,143,164,181,217`, `auralis-web/backend/core/processor_factory.py:202,214`
- **Status**: NEW
- **Age**: 048c4f980 2026-08-21 ("Releases nothing today" docstring); hook from #3746
- **Effort**: small
- **Description**: `HybridProcessor.close()` iterates every owned attribute and calls any `close()` it finds, guarded by `_NOT_OWNED_BY_PROCESSOR`, `_closed` and a swallow-all `except`. The only `close()` it can reach is `AudioFingerprintAnalyzer.close()`, whose body is a docstring: "No-op. The Rust engine holds no Python-side executor; kept for API compat." The docstring of `HybridProcessor.close()` itself says "Releases nothing today ... Kept so the next resource needn't plumb a new hook." Eight call sites (singleton eviction, `ProcessorPool` x5, `ProcessorFactory` x2) invoke it, and `processor_pool.py:116` carries a comment about the lock-ordering consequence of a call that does nothing. `AudioFingerprintAnalyzer.__init__` is a bare `pass` and `SidecarManager.__init__` is docstring-only — empty constructors with no state.
- **Evidence**: `def close(self) -> None: """No-op. The Rust engine holds no Python-side executor; kept for API compat."""`; `# close() releases nothing today; see its docstring (#4744).` (`hybrid_processor_singleton.py:96`).
- **Impact**: Speculative-generality hook: callers carry lock-ordering workarounds and tests (`test_hybrid_processor_close_4744.py`, `test_processor_cache_lru.py`) for behaviour that does not exist; a future real `close()` on any attribute would silently start running on eviction paths that were never exercised.
- **Siblings**: `SidecarManager.__init__` (docstring-only), `AudioFingerprintAnalyzer.__init__` (`pass`).
- **Related**: #4744, #3746 (both CLOSED).
- **Suggested Fix**: Delete `AudioFingerprintAnalyzer.close()` and the empty `__init__`s, delete `HybridProcessor.close()` / `_closed` / `_NOT_OWNED_BY_PROCESSOR`, and remove the eviction-path calls plus the two tests. Re-add the hook the day an attribute owns a real resource.
- **Merge note**: absorbs TD8-08 (identical finding from the Backwards-Compat dimension).

#### Dimension 6: Test Hygiene

##### TD6-02: `test_fix_2166_double_windowing.py` is permanently red against a signature that changed, superseded by the audit-named guard
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/test_fix_2166_double_windowing.py:11-130` (3 tests baselined)
- **Status**: NEW (guarded issue #2166 is HIGH but closed; replacement guard exists, so not promoted)
- **Age**: `7c5ade49e` 2026-02-14
- **Effort**: trivial
- **Description**: Each test feeds 1 s (44100 samples) to `apply_eq_mono(audio, gains, map, fft_size=2048)`. Since #3742, `apply_eq_mono` raises `ValueError` when `len(audio) > fft_size` (`auralis/dsp/eq/filters.py:83`), so all three fail before reaching their amplitude assertions. All three are in `pytest-baseline.json`. The "must not regress" guard that `.claude/commands/audit-regression.md:47` names, `tests/auralis/dsp/test_eq_double_window_artifact.py`, exists and is not skipped.
- **Evidence**: `filters.py:83: if len(audio_mono) > fft_size: raise ValueError`; test uses `duration = 1.0`, `fft_size = 2048`.
- **Impact**: Three permanent baseline slots that re-permit any new failure with these names, and a misleading second "#2166" test.
- **Siblings**: TD6-01, TD6-03.
- **Related**: none.
- **Suggested Fix**: Delete the file; drop its 3 entries from `pytest-baseline.json`.

##### TD6-03: Repository-pattern leak guard has a stale allow-list and is baselined red
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/regression/test_no_raw_sql_leaks.py:20-30`
- **Status**: NEW (originating issue #2370 closed, LOW)
- **Age**: `ebc760b3f` 2026-02-22
- **Effort**: small
- **Description**: This is the only mechanical enforcement of CLAUDE.md Principle 4 (all DB via repositories). `ALLOWED_SQL_PATHS` still lists `auralis/library/manager.py` (deleted) and does not list the files the library split into. Re-running its exact scan statically yields violations in `auralis/library/schema_indexes.py:40`, `migration_steps.py:164-219`, `database_engine.py:80-95`, `migration_engine.py:56-61`, `database.py:182,191`, and `analysis/fingerprint/catalog.py:86-194`. The test is therefore red and baselined (`tests.regression.test_no_raw_sql_leaks...::test_no_raw_sql_outside_repositories`).
- **Evidence**: `ls auralis/library/manager.py` -> missing; baseline entry present.
- **Impact**: A genuine new raw `cursor.execute` in a repository-pattern-protected module cannot fail CI, because the test already fails and is tolerated.
- **Siblings**: TD6-01, TD6-02.
- **Related**: `/audit-engine` for whether `catalog.py` (a second SQLite catalog) should be in the allow-list or behind a repository.
- **Suggested Fix**: Replace the allow-list with the current legitimate set (`database_engine.py`, `migration_engine.py`, `migration_steps.py`, `schema_indexes.py`, `database.py` PRAGMA-only, `fingerprint/catalog.py`, `repositories/`), drop the `manager.py` entry, make it pass and remove its baseline entry.

##### TD6-04: `tests/regression/test_version_compatibility.py` is half-dead: 9 baselined failures, tautologies, and swallowed `ImportError`
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/regression/test_version_compatibility.py` (530 lines, 21 tests; 9 baselined); siblings `tests/regression/test_config_changes.py:379-393`, `tests/regression/test_data_migration.py:354-367`
- **Status**: NEW
- **Age**: `2e9fd0b78` 2025-11-08
- **Effort**: medium
- **Description**: Nine tests (`TestConfigurationCompatibility` x5, `TestBackwardCompatibility` x2, `TestDatabaseSchemaMigrations::test_composite_index_on_favorites`, `TestDeprecatedFeatures::test_deprecated_config_keys_ignored`) are baselined failures. At least five dereference `UnifiedConfig.config_data` / `.sample_rate`, which do not exist (`UnifiedConfig` has `internal_sample_rate`; `grep config_data auralis` -> 0). The passing remainder is weak: `test_old_processing_parameters_mapped` ("Legacy parameter names work") asserts `processor is not None` (weak-baseline entry); `test_eq_curve_generation_stable` wraps `generate_genre_eq_curve("neutral")` in `except ImportError: pass` although `auralis.dsp.eq.generate_genre_eq_curve` exists, so a rename would pass silently; `test_artwork_cache_directory_created` ends in `assert artwork_dir is not None` after building a `Path`.
- **Evidence**: baseline entries listed above; `auralis/dsp/eq/__init__.py:12` exports the function the `except ImportError` pretends may have moved.
- **Impact**: "Backward compatibility with old config/format" has no owner in a desktop-only app with no external consumers, so these tests defend a contract nobody has. They occupy baseline slots and read as regression coverage.
- **Siblings**: `tests/regression/test_fixed_bugs.py` (2 baselined: `test_continuous_mode_state_preservation_bug`, `test_album_artwork_caching_bug`), `tests/regression/test_fingerprint_keyboard_interrupt.py` (2 baselined; its executor-based premise is documented obsolete in `audit-regression.md:50`), `tests/regression/test_data_migration.py` (2 baselined).
- **Related**: Dim 8 (backwards-compat cruft) — the tests exist only to defend compat shims.
- **Suggested Fix**: Delete the dead-API tests (`config_data`, `deprecated_*`, `old_config_format`); keep only the ones that assert a current invariant (output format, determinism) rewritten against `internal_sample_rate`; remove `except ImportError: pass` so a rename fails; delete the `is not None` tautologies; regenerate the baseline (up to 15 entries removable across the four siblings).

##### TD6-05: Two regression tests open the developer's real `~/.auralis/library.db`
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/regression/test_data_migration.py:361`, `tests/regression/test_version_compatibility.py:490`
- **Status**: NEW (closed #3519 and #5810 fixed this for the backend `client` fixture only)
- **Age**: `2e9fd0b78` 2025-11-08
- **Effort**: trivial
- **Description**: Both call `LibraryDatabase()` with no path, so `resolve_database_path(None)` returns `DEFAULT_DB_PATH` and `mkdir`/`chmod 0700`s `~/.auralis`, runs the migration chain on the real library and writes a backup beside it. The `_isolated_library_db` fixture that redirects `DEFAULT_DB_PATH` lives in `tests/backend/conftest.py` and is not autouse, so `tests/regression/` does not get it. `test_artwork_cache_directory_created` never even uses `db`; its only assertion is that a `Path` is not None.
- **Evidence**: `tests/regression/conftest.py` has only `temp_db`/`temp_audio_dir`-style fixtures with no DEFAULT_DB_PATH patch; `LibraryDatabase.__init__(database_path=None)` -> `~/.auralis/library.db` (`database.py:62-74`).
- **Impact**: A test run writes into (and can migrate/lock) the owner's real library; two tests pass or fail depending on the machine's state.
- **Siblings**: `tests/auralis/library/test_default_dir_hardening_4824.py:53` calls `LibraryDatabase()` too but redirects HOME first (not an instance).
- **Related**: none.
- **Suggested Fix**: Move the `_isolated_library_db` patch into root `tests/conftest.py` as an autouse session fixture (one fixture, no duplicate), or pass `tmp_path / "library.db"` at the two call sites; assert the location via the patched constant.

##### TD6-06: The `#5191` strict-xfail tests now xfail by raising, so their assertion never executes
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_error_handling.py:173-190, 213-227`
- **Status**: NEW (cited issue #5191 is CLOSED, fixed in `73cc8b982`, 2026-10-28)
- **Age**: xfail added `c40222f4d` 2026-08-21; made stale by `73cc8b982`
- **Effort**: trivial
- **Description**: `validate_and_normalize_input` now validates NaN/Inf before the short-buffer return (`hybrid_stage_dispatch.py:91`), so `processor.process()` raises `ModuleError` on these 3-sample buffers. `xfail(strict=True)` is satisfied by any exception, so each test reports XFAIL and its `assert not np.isnan(...)` line is never reached. It would also stay green if the bug returned in its old form (the assertion fails, which is also an XFAIL). The real guard, `tests/auralis/core/test_short_buffer_nonfinite_5191.py` (`pytest.raises(ModuleError, match="NaN or Inf")`), already exists.
- **Evidence**: xfail reason text "#5191: ... keeps its NaN" contradicts the closed fix comment; `test_short_buffer_nonfinite_5191.py:29-31`.
- **Impact**: An xfail citing a closed issue (the pattern #5156 closed in 2026-08) that now hides a duplicate of a better test.
- **Siblings**: none (these are the only two xfails).
- **Related**: none.
- **Suggested Fix**: Delete both tests (covered by the `_5191` file) or turn them into `pytest.raises(ModuleError)` and drop the markers. After that the repo has zero xfail markers.

##### TD6-07: Skip guards on hard runtime dependencies cannot fire (psutil, mutagen, soundfile, Pillow)
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: see Evidence
- **Status**: NEW (sibling of closed #5808, which swept only first-party `ImportError`)
- **Age**: various (e.g. `81a64e580` 2026-08-07 for the metadata-editor gates)
- **Effort**: small
- **Description**: `psutil`, `mutagen`, `soundfile` and `pillow` are unconditional dependencies (`requirements.txt:19,22,61,65`; `pyproject.toml` main `dependencies`, not an extra), yet 40+ test sites skip when they are missing. An unreadable environment becomes a pass-with-skips; neither CI gate looks at skip counts.
- **Evidence**:
  - `psutil`: `tests/performance/test_memory_profiling.py:36`, `test_library_operations_performance.py:611`, `test_audio_processing_performance.py:552,595,624,691`, `tests/edge_cases/test_resource_exhaustion.py:137`
  - `mutagen`: 13 `skipif(not MUTAGEN_AVAILABLE)` in `tests/auralis/library/test_metadata_editor.py`, plus `test_metadata_backup_5307.py:23`, `test_metadata_unreadable_file_422_5993.py:32`, `test_metadata_batch_atomicity.py:54`, `importorskip("mutagen")` in `test_lyrics_extraction_5939.py:17`, `test_m4a_bpm_publisher_6111.py:14`, `test_mp3_wav_extra_fields_6110.py:12`, `test_id3_multivalue_6133.py:9`; one test asserts the not-installed behaviour (`test_metadata_editor.py:74`, `skipif(MUTAGEN_AVAILABLE)`) which can never run
  - `soundfile`: `tests/conftest.py:107,521` (`HAS_SOUNDFILE`), `importorskip("soundfile")` x2
  - `Pillow`: `importorskip("PIL.Image")` in `test_thumbnail_concurrency_4527.py:37`, `test_artwork_orientation_and_profile_5927.py:16`, `test_artwork_thumbnails.py:24`
- **Impact**: Low today; a broken install silently drops the metadata/artwork/profiling suites to "skipped".
- **Siblings**: `MUTAGEN_AVAILABLE` itself is a production flag in `auralis/library/metadata_editor.py` with a dead not-installed branch (Dim 8 / Dim 1 candidate).
- **Related**: ffmpeg/ffprobe gates (25 sites) are legitimate (external binary); the Rust module gate is TD6-09.
- **Suggested Fix**: Import these four at module top (collection fails loudly). Delete the `skipif(MUTAGEN_AVAILABLE)` test and the production `MUTAGEN_AVAILABLE` fallback together.

##### TD6-08: `test_mastering_regression.py` and the phase-6 tests sniff for a personal music library by path
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/regression/test_mastering_regression.py:94-140,358-365`; `tests/test_phase6_realworld_validation.py:44-46,301-302`; `tests/test_phase6_library_characterization.py:38`
- **Status**: NEW (the #6242 `local_library` marker was applied to the phase-6 and phase-25 modules but not here)
- **Age**: `dc46ac06a` 2025-12-22
- **Effort**: trivial
- **Description**: `test_mastering_regression` is parametrized over six hard-coded `/mnt/Musica/Musica/...` tracks and ends in `pytest.skip(f"Test file not found")`; it is not marked `local_library`, so it is excluded by an ambient path check, exactly what #6242 replaced elsewhere. The phase-6 modules already carry `pytestmark = local_library` and then re-skip per-test on missing paths (and use `/mnt/audio/...`, a different mount than the other modules), so the inner skips are redundant. On CI all 6 mastering cases skip silently; this is the project's mastering regression suite.
- **Evidence**: `tests/conftest.py:603-609` skips on `"local_library" in item.keywords`; `rg local_library tests/regression` -> no hit.
- **Impact**: Mastering "regression" coverage that does not run anywhere except the owner's machine, and does not advertise that.
- **Siblings**: `tests/test_phase6_*`, `tests/backend/test_adaptive_mastering_weighted.py` (already marked).
- **Related**: `/audit-engine` for the lack of any in-repo synthetic mastering regression.
- **Suggested Fix**: `pytestmark = pytest.mark.local_library` on `test_mastering_regression.py` and delete the inner `Path.exists()` skips; hoist the `/mnt/...` roots to one env-driven constant.

##### TD6-09: Backend CI never builds the Rust module, so every `auralis_dsp` test skips or is baselined red, and skip counts are unmonitored
- **Severity**: LOW (inferred from static reading; verify against a CI artifact)
- **Dimension**: Test Hygiene
- **Location**: `.github/workflows/backend-tests.yml:109-135`; `tests/vendor/test_fingerprint_tempo_5742.py:14`, `tests/test_pyo3_channel_axis_guards_4502.py:13`; baseline entries for `test_rust_fingerprint_glue` (4), `test_fingerprint_band_window_4136` (3), `test_continuous_mode_target_integration` (3), `test_mastering_content_awareness_end_to_end` (3), `test_fingerprint_integration` (2)
- **Status**: NEW
- **Age**: n/a
- **Effort**: medium
- **Description**: The workflow installs `requirements-lock.txt` and runs `pytest -m "not slow"`; there is no `maturin develop`/wheel step (`grep -i maturin\|cargo\|rust backend-tests.yml` -> none), although `auralis/analysis/fingerprint/rust_fingerprint.py` imports `auralis_dsp` and CLAUDE.md calls the module required. Tests that `importorskip("auralis_dsp")` therefore skip in CI, and about 15 fingerprint-dependent tests appear in the known-failure baseline. The pytest step prints no `-rs` skip summary and there is no skip-count ratchet, so a mass skip (the failure mode #4691's ratchet was written for) passes the gate.
- **Evidence**: workflow grep above; baseline module list; `tests/vendor/test_fingerprint_tempo_5742.py:14-17` `importorskip(..., reason="Rust DSP module not built")`.
- **Impact**: The single Rust binding (25D fingerprint, the only compiled code on the analysis path) is covered by zero CI tests, and its baselined failures are indistinguishable from real ones.
- **Siblings**: `.github/workflows/rust-audit.yml` audits dependencies only.
- **Related**: `/audit-engine` (fingerprint), CI owners.
- **Suggested Fix**: Add a `maturin develop` (or prebuilt wheel) step to `backend-tests.yml`, regenerate the baseline from that run's artifact (expect ~15 entries to leave), and add `-rs` plus a ratchet on total skipped count to `check_pytest_baseline.py`.

##### TD6-10: Seven boundary tests convert any non-assertion exception into a skip
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_boundary_max_min_values.py:189,218,238,261,434`; `tests/backend/test_boundary_empty_single.py:545`; `tests/backend/test_boundary_exact_conditions.py:474,528`; `tests/boundaries/test_chunked_processing_boundaries.py:788`
- **Status**: NEW (sibling of closed #4969 / #6241, which only added the `except (AssertionError, ZeroDivisionError, IndexError): raise` pre-clause)
- **Age**: `#4969` partial fix
- **Effort**: small
- **Description**: After the narrowed pre-clause, `except Exception as e: pytest.skip("... not supported: {e}")` still converts `ValueError`, `TypeError`, `RuntimeError`, `ModuleError` etc. into skips. The inputs are in-contract (1-sample, 10-sample, empty, Nyquist, odd sample rates), and `HybridProcessor` now documents that short buffers return unchanged, so a crash on these inputs is a bug, not "unsupported". A skip in these paths also reads as green in both gates. `tests/backend/test_boundary_advanced_scenarios.py:492` skips when threads recorded errors ("DB doesn't support concurrent writes"), which is the same shape on a DB that does support them (WAL + busy_timeout).
- **Evidence**: `test_boundary_empty_single.py:540-547`: `assert len(result) == 0` inside `try`, `except Exception: # Document expected behavior if it should raise` -> `pytest.skip`.
- **Impact**: A crash on empty/1-sample/non-44.1k input would turn 8 boundary tests into SKIPs.
- **Siblings**: `tests/edge_cases/test_resource_exhaustion.py:111,227` (`MemoryError` -> skip, defensible).
- **Related**: `/audit-engine` if any of these inputs really raise today.
- **Suggested Fix**: Decide per input: either `assert len(result) == len(audio)` (no try) or `with pytest.raises(<specific>)`; delete the catch-all skip.

##### TD6-11: Seven frontend assertions are wrapped in `if (element)` guards the weak-test ratchet cannot see
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `auralis-web/frontend/src/components/library/Items/__tests__/TrackRowMetadata.test.tsx:157,177,313,329`; `src/components/album/AlbumArt.test.tsx:73,83`; `src/components/library/__tests__/AlbumDetailView.test.tsx:395`
- **Status**: NEW (sibling of closed #5126, which fixed the Sidebar/RadialPresetSelector click tests)
- **Age**: `ff3b3a5a2` 2025-11-23 / `b78c73d6d` 2025-10-21
- **Effort**: small
- **Description**: Each test does `const el = x.closest(...)` / `queryByRole('img')` and then `if (el) { expect(el)... }`. When the element is absent the test performs no assertion on the behaviour it is named for (`should apply current styling when isCurrent`, `should use correct image URL pattern`), and `check-weak-tests.mjs` passes because the body contains an `expect` call. The AlbumDetailView case has an `else` branch whose assertion (`textContent toContain('play')`) is weaker than the then-branch.
- **Evidence**: `TrackRowMetadata.test.tsx:156-159`: `const parentElement = titleElement.closest('[iscurrent]'); if (parentElement) { expect(parentElement).toHaveAttribute('iscurrent','true') }`.
- **Impact**: Removing the `iscurrent` attribute or the `<img>` leaves these tests green.
- **Siblings**: `check-weak-tests.mjs` could add a "conditional assertion" rule.
- **Related**: `/audit-frontend`.
- **Suggested Fix**: Replace with `getBy*` + unconditional `expect` (or `expect(el).not.toBeNull()` first); extend `check-weak-tests.mjs` to flag an `expect` whose only enclosing statement is an `if` with no `else`.

##### TD6-12: `test_fingerprint_integration.py` is a print-driven script with `return True` test bodies
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/auralis/analysis/test_fingerprint_integration.py` (380 lines: 4 tests, 9 `assert`, 95 `print`)
- **Status**: NEW
- **Age**: legacy
- **Effort**: small
- **Description**: Three tests (`test_fingerprint_extraction`, `test_target_generation`, `test_end_to_end_processing`) end with `return True` after a long `print` narrative; pytest >= 8.4 (project pins 9.x) fails a test that returns non-None. Two of the four tests are baselined known failures. `test_real_audio` skips if the fixture is empty (the fixture synthesises audio, so the guard cannot fire). Other heavily printing collected tests have a normal assert density (`test_phase6_*`: 7 assertions / 140 prints, gated `local_library`).
- **Evidence**: AST scan of `tests/` for `test_*` functions with a non-None `return`: exactly these three, repo-wide.
- **Impact**: Baseline slots for a script posing as a test; the narrative duplicates `tests/auralis/analysis/fingerprint/` coverage.
- **Siblings**: none.
- **Related**: none.
- **Suggested Fix**: Delete the file after confirming the fingerprint-schema tests under `tests/auralis/analysis/fingerprint/` cover extraction + target generation; drop the 2 baseline entries.

##### TD6-13: Dead test scaffolding: `jest` global alias, orphaned `TEMPLATE.example.tsx`, stale tracked `MEMORY_TEST_SUMMARY.txt`
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `auralis-web/frontend/src/test/setup.ts:50-62`; `auralis-web/frontend/src/test/TEMPLATE.example.tsx`; `auralis-web/frontend/MEMORY_TEST_SUMMARY.txt` (302 lines, tracked, last touched `e3b15cea8` 2025-11-23, content dated "January 23, 2025 ... READY FOR TOMORROW")
- **Status**: NEW
- **Age**: 2025
- **Effort**: trivial
- **Description**: `setup.ts` installs `globalThis.jest = { mock, unmock, fn, spyOn, ... }`; `grep jest\.(mock|fn|spyOn|...)` over `src/` finds no caller outside `setup.ts`. `TEMPLATE.example.tsx` is 175 lines of commented-out `expect` calls (not collected: vitest includes only `*.test|spec`), and the README references it. `MEMORY_TEST_SUMMARY.txt` is a status-report artefact listing doc files by name.
- **Evidence**: grep results above; `git ls-files` shows only the .txt tracked (the sibling `*_SUMMARY.md`, `test-results*.log` in the same dir are gitignored local clutter).
- **Impact**: Cosmetic; misleads new spec authors toward a Jest dialect.
- **Siblings**: gitignored but present: `frontend-test-output.txt`, `test-results*.log`, `COMPLETE_FRONTEND_TESTING_SUMMARY.md` (working-tree clutter only).
- **Related**: Dim 7 for the stale doc.
- **Suggested Fix**: Delete the `jest` alias block, the template (or move its comments into `src/test/README.md`), and `MEMORY_TEST_SUMMARY.txt`.

#### Dimension 7: Stale Documentation & Comments

##### TD7-01: docs/subsystems/frontend.md names a dozen hooks/services/singletons that do not exist
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/subsystems/frontend.md:5`, `:71`, `:85-92`, `:112`, `:121-122`
- **Status**: NEW (residue; sibling doc-rot issues #6246/#6247/#6251 are CLOSED and did not touch this file)
- **Age**: dbb3b4a5e 2026-07-11 (version line); hooks table rewritten piecemeal since
- **Effort**: small
- **Description**: The file sits in the gate's STRICT scope but the gate only resolves file paths, not symbols. The "Representative hooks" table and API/WS sections cite names with zero definitions in `auralis-web/frontend/src`: `usePlayerControls`, `usePlayNormal` (consolidated into `usePlayEnhanced`/`useAudioStreamingCore`; only comments mention it), `useMasteringRecommendation`, `useAlbumsQuery` (removed in #6287), `useOptimisticUpdate`, `useReduxState`, `useMutation` wrappers (`hooks/api/` holds only `useRestAPI.ts`), `processingService` and `similarityService` (`services/` has no such files), `singletonWSManager`, `singletonRefCount`, `updatePlaybackState`. Header also says "Vite 7" (package.json `^8.3.3`, installed 8.3.3) and "~805 .ts/.tsx files" (live: 882 incl. tests / 545 non-test).
- **Evidence**: `grep -rw usePlayerControls auralis-web/frontend/src` -> 0 hits; `ls auralis-web/frontend/src/hooks/shared` has no `useOptimisticUpdate.ts`/`useReduxState.ts`; `ls auralis-web/frontend/src/services` lists artworkService, keyboardShortcutsService, libraryService, playlistService, queueService, settingsService only.
- **Impact**: This is the doc an auditor or agent reads first for the frontend; it sends them to non-existent files and makes real hooks look missing.
- **Siblings**: TD7-13 (comments citing `usePlayNormal`), TD7-02, TD7-11.
- **Related**: owning audit `/audit-frontend` for the hook consolidation itself.
- **Suggested Fix**: Regenerate the hooks table from `ls hooks/*/` (list only exported hooks), delete the dead names, update the Vite version and drop the file-count figure (or point at a script like `check_doc_counts.py`).

##### TD7-02: dsp-engine.md loudness-maximizer section describes retired `QuietBranch` and a constant that does not exist
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/subsystems/dsp-engine.md:145-157` (also contradicts its own `:109`)
- **Status**: NEW (residue after #6247)
- **Age**: dbb3b4a5e 2026-07-11
- **Effort**: small
- **Description**: The section opens "In `QuietBranch`, the loudness maximizer is the load-bearing tuning surface", but line 109 of the same file says the categorical branches were deleted. The constants table cites `LOUDNESS_COMPETITIVE_LUFS` (-14.0, "No-op at/above this"), which has no definition anywhere (grep over `auralis/`, tests, scripts). The link text says the constants live in `mastering_config.py`; `LOUDNESS_TARGET_LUFS`, `LOUDNESS_GAP_CLOSURE_FACTOR`, `LOUDNESS_MIN_CREST_DB`, `LOUDNESS_MAX_CREST_REDUCTION_DB` are in `auralis/core/mastering_presets.py`, and the live response is a softplus (`LOUDNESS_RESPONSE_SOFTNESS_DB`) with no "no-op above X" cutoff.
- **Evidence**: `grep -rn LOUDNESS_COMPETITIVE auralis` -> only the doc; `mastering_presets.py:259-280` defines the other four plus `LOUDNESS_RESPONSE_SOFTNESS_DB` ("The response has no zero-gain side").
- **Impact**: The doc calls this "the most-churned tuning area"; someone tuning from this table edits a non-existent knob and misses the real one (and `mastering-dulling` style investigations start from this table).
- **Siblings**: TD7-01.
- **Related**: `/audit-engine`.
- **Suggested Fix**: Rewrite the table from `mastering_presets.py` (add `LOUDNESS_RESPONSE_SOFTNESS_DB`, drop `LOUDNESS_COMPETITIVE_LUFS`), say "the continuous path's loudness maximizer stage (`stages/loudness_maximizer.py`)" instead of `QuietBranch`, and fix the file link.

##### TD7-03: WEBSOCKET_API.md under-documents audio_stream_end / audio_stream_error and still describes a 5 s crossfade
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/backend/WEBSOCKET_API.md:421`, `:476-492`, `:518`
- **Status**: NEW (residue after #6251/#4988)
- **Age**: 4241fd700 2026-08-07 (:421), 46f1e0b62 2026-06-01 (:518)
- **Effort**: small
- **Description**: (a) `audio_stream_start.total_chunks` comment says "10s new-content interval, 5s crossfade overlap"; there is no crossfade (#4642; the doc's own sibling docs say so). (b) `audio_stream_end` is documented as "Sent once when all chunks have been streamed" with payload `{track_id,total_samples,duration,stream_type}`; `core/stream_lifecycle.py::send_stream_end` also sends `reason` (`completed|stopped|errored`, #4659/#4790) and `stream_epoch` (#5861), and the frontend type `types/ws/streaming.ts:99` has `reason?`. The same doc's `audio_stream_error` block already refers to `audio_stream_end{reason:"errored"}`, so it contradicts itself. (c) "Common error codes: STREAMING_ERROR, TRACK_NOT_FOUND, DSP_ERROR, ENCODING_ERROR": only STREAMING_ERROR is ever emitted; the live codes are `SEEK_ERROR`, `ENHANCEMENT_DISABLED`, `PROCESSOR_UNAVAILABLE` (+ client-side `DESYNC`).
- **Evidence**: `grep -rn "TRACK_NOT_FOUND\|DSP_ERROR\|ENCODING_ERROR" auralis-web` -> only the doc; `stream_lifecycle.py:~140` message dict has `reason` and `stream_epoch`.
- **Impact**: A client author following the doc treats a stopped/errored stream as a finished track (the exact bug #4659 fixed) and matches on error codes that never arrive.
- **Siblings**: TD7-04 (backend comments with the same crossfade claim).
- **Related**: `/sync-contracts`.
- **Suggested Fix**: Add `reason` and `stream_epoch` to the `audio_stream_end` payload and reword the lead sentence; replace the error-code list with the four emitted codes; drop "5s crossfade overlap" from the `total_chunks` comment.

##### TD7-04: chunk_boundaries.py (the chunk-geometry authority) has a mangled docstring, a stale header and a "crossfade" constant comment; same claim in four more backend comments
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:3-9`, `:22`, `:49-53`
- **Status**: NEW
- **Age**: 0599e61e7 2026-10-23 (#6270 split damaged the docstring); `:22` a8687a0cd 2025-12-05
- **Effort**: trivial
- **Description**: (1) `emitted_chunk_start`'s docstring was edited mid-sentence by the #6270 split: "...which is what ``get_chunk_boundaries`` returns. The former ChunkOperations module (split in #6270 into chunk_file_loading / chunk_segment_extraction). extract_chunk_segment`` skips ``OVERLAP_DURATION``..." -- the subject of the sentence and an opening backtick are gone, and `get_chunk_boundaries` is no longer in this module (it is `ChunkBoundaryManager.get_chunk_boundaries` in `chunk_boundary_manager.py`). (2) The module header still reads "Chunk Boundary Manager ... Manages chunk boundaries and context windows" although the stateful manager moved to `chunk_boundary_manager.py` and this file is now pure constants + free functions. (3) `OVERLAP_DURATION = 5.0  # seconds - overlap for natural crossfades`: no crossfade exists (Retired Architecture table; `chunk_segment_extraction.py` calls itself "the no-crossfade contract").
- **Evidence**: see lines above; same stale crossfade wording at `core/chunk_file_loading.py:48-49` ("include OVERLAP_DURATION ... for crossfading... no audio is lost during crossfade concatenation"), `core/stream_enhanced.py:9` ("chunk-boundary crossfading"), `core/audio_stream_controller.py:155` ("crossfading at boundaries"), `core/chunked_processor.py:203` ("chunk duration ... for crossfade calculations"), and `frontend/src/services/audio/PCMStreamBuffer.ts:36` ("ChunkOperations.extract_chunk_segment trims", class deleted in #6270).
- **Impact**: CLAUDE.md names this file the sole chunk-geometry authority, so it is the most-read module for this topic; its comments say the opposite of the design (the #4642 crossfade-removal invariant) and invite someone to re-add crossfade math.
- **Siblings**: the five listed comments above; TD7-03(a).
- **Related**: none.
- **Suggested Fix**: Rewrite the `emitted_chunk_start` sentence ("Not the same as the chunk's core start, which `ChunkBoundaryManager.get_chunk_boundaries` returns; `extract_chunk_segment` skips ..."), retitle the module header, change the constant comment to "head overlap re-rendered for context, trimmed by extract_chunk_segment", and fix the five sibling comments (grep `crossfad` under `auralis-web/backend/core`).

##### TD7-05: ten comments/docstrings cite `config/startup.py` / `startup.py` / `schemas.py`, which became packages
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/backend/core/executors.py:109`, `core/streamlined_lifecycle.py:74`, `core/processing_engine.py:199`, `core/seekable_source.py:189`, `services/library_auto_scanner.py:65`, `routers/similarity_common.py:58`, `routers/settings_sync.py:37`, `analysis/fingerprint_executor.py:73`, `security/path_allowlist.py:28`, `security/path_security.py:141`, `config/background_workers.py:6`; `routers/enhancement.py:49` ("single source of truth in schemas.py")
- **Status**: NEW
- **Age**: #5236 (startup split) / #5479 (schemas split), Aug-Sep 2026
- **Effort**: trivial
- **Description**: `config/startup.py` is now the package `config/startup/` (components, fingerprint, workers, rollback, shutdown, ...). Comments still point at the single file, and some name behaviour that moved, e.g. `executors.py:109` says "ProcessingEngine(max_concurrent_jobs=2) in config/startup.py" (it is in `config/startup/workers.py:120`), `library_auto_scanner.py:65` "Wired by startup.py" (it is `config/startup/components.py`), `fingerprint_executor.py:73` "_shutdown_components()" (`config/startup/__init__`/`rollback.py`).
- **Evidence**: `ls auralis-web/backend/config/startup/` -> 8 modules, no `startup.py`; `grep -rn "startup\.py" auralis-web/backend` -> 11 non-provenance hits. `schemas.py` is `schemas/` package.
- **Impact**: Each is a dead-end jump for a reader tracing lifespan wiring; the split modules themselves correctly say "the former single-file config/startup.py", so only the old cross-references are rotted.
- **Siblings**: the six `Split out of schemas.py` / `config/middleware.py` provenance lines are fine (past tense).
- **Related**: none.
- **Suggested Fix**: `sed`-style pass replacing each with the owning submodule (`config/startup/workers.py`, `.../components.py`, `.../rollback.py`) and `schemas/enhancement.py`; one commit.

##### TD7-06: 17 design-system source files and the design-system README point at the archived UI_DESIGN_GUIDELINES.md ("MANDATORY"); README primitive count is wrong
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/frontend/src/design-system/index.ts:10`, `primitives/{List,Slider,SegmentedControl,Badge,layout,Tooltip,Input,typography,Chip,surface,index,Button,Card,CircularProgress,IconButton,control}` (`@see docs/UI_DESIGN_GUIDELINES.md`); `design-system/README.md:276,327,375,391`; `design-system/tokens.ts:11`
- **Status**: NEW
- **Age**: 06b9d0aa7 2026-08-07 (@see lines); archived by #6255
- **Effort**: small
- **Description**: `docs/UI_DESIGN_GUIDELINES.md` no longer exists (moved to `docs/archive/frontend-history/`, per `docs/README.md:80-84`, which names `docs/UI_STYLE_GUIDE.md` and CLAUDE.md as the live rules). The 17 `@see` tags and four README links (one labelled "**MANDATORY**", one a checklist item "Read UI_DESIGN_GUIDELINES.md") still send readers there. The README also says "8 core building blocks" and lists 7, while `primitives/` has ~16 (Alert, Box, Checkbox, Chip, CircularProgress, Container, List, ProgressBar, SegmentedControl, Text...), and describes `tokens.ts` as the single token file although `tokens/` holds six modules.
- **Evidence**: `ls docs/UI_DESIGN_GUIDELINES.md` -> No such file; `find docs -name UI_DESIGN_GUIDELINES.md` -> `docs/archive/frontend-history/`.
- **Impact**: The design-system entry point instructs contributors to read a file it cannot find (and which the project retired as pre-streamlining), while the live rule document is not linked.
- **Siblings**: TD7-01.
- **Related**: `/audit-frontend` Dim 5 for token use itself.
- **Suggested Fix**: Replace `@see docs/UI_DESIGN_GUIDELINES.md` with `@see docs/UI_STYLE_GUIDE.md` in all 17 files (mechanical), repoint the README links, and regenerate the primitives list from the directory.

##### TD7-07: FIRST_TIME_SETUP.md has several instructions that no longer match the project
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `FIRST_TIME_SETUP.md:96-97` (no Rust step), `:100-123` (`.env`), `:216` (broken link), `:266-282` (audioread), `:50-60`/`:277` (`AUDIO_DEPENDENCY_TROUBLESHOOTING.md`), `:225-243` (VS Code)
- **Status**: NEW (residue; #5447/#4558/#4057 fixed other lines of this file)
- **Age**: mixed; link/audioread lines predate 2026
- **Effort**: small
- **Description**: (1) The setup path installs Python deps and frontend deps but never builds the Rust DSP module; README and CLAUDE.md both say `cd vendor/auralis-dsp && maturin develop` is required before first run, and fingerprinting imports `auralis_dsp`. (2) Step 6 tells the reader `cat .env` and "The project uses environment variables from `.env`": `.env` is gitignored (not present on a fresh clone) and nothing reads it (no `load_dotenv`/`env_file` anywhere; python-dotenv is only a uvicorn[standard] transitive dep). (3) "Verify Audio Backend" says "The system uses `audioread`" and lists audioread backends; `pyproject.toml:56` records librosa 1.0 dropped audioread (#5414) and it is not a dependency. (4) Next Steps links `[ADAPTIVE_MASTERING_SYSTEM.md](ADAPTIVE_MASTERING_SYSTEM.md)` at repo root; the file is `docs/features/adaptive-mastering/ADAPTIVE_MASTERING_SYSTEM.md` (and that doc is itself in the ratchet baseline). (5) "Need Help?" cites `AUDIO_DEPENDENCY_TROUBLESHOOTING.md (reference in CLAUDE.md)`: no such file, CLAUDE.md does not mention it. (6) VS Code snippet uses removed `python.linting.enabled` / `python.formatting.provider` keys and "TypeScript Vue Plugin (Vue)" for a React project; `.vscode/settings.json` has none of it.
- **Evidence**: `ls ADAPTIVE_MASTERING_SYSTEM.md AUDIO_DEPENDENCY_TROUBLESHOOTING.md` -> missing; `git check-ignore -v .env` -> `.gitignore:137`; `grep -rn dotenv auralis auralis-web/backend` -> none.
- **Impact**: A fresh-clone user follows it to a backend that cannot fingerprint (no `auralis_dsp`) and chases audioread/.env that do nothing; this is the file CLAUDE.md lists as a reference doc.
- **Siblings**: TD7-08 (README).
- **Related**: none.
- **Suggested Fix**: Add the `maturin develop` step, delete the `.env` step and the audioread section (replace with `ffmpeg -version` / `python -c "import soundfile"`), fix or drop the two dead references, trim the VS Code block.

##### TD7-08: README.md describes UI and counts that no longer exist
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `README.md:100`, `:222-228`, `:269-271`, `:307`, `:316`, `:322` ("18 route handlers"), `:266`, `:321-327`
- **Status**: NEW
- **Age**: 66a55252e 2025-10-14 (Visualizer tab); counts 2026
- **Effort**: small
- **Description**: (1) "Simple Two-Tab Interface: Your Music / Visualizer" and "Audio Visualizer" feature bullet: the sidebar is Songs / Albums / Artists / Favourites / Playlists (`components/layouts/Sidebar/SidebarContent.tsx`), the only visualization is the ambient `StarfieldBackground` switch (#5676); `components/` has no visualizer directory (README `:307` still lists "visualizer"). (2) "Toggle the ✨ Magic switch ... bottom-right of player": no `Magic` control exists in the frontend (`grep -ri magic` hits only a library tagline and a theme file); enhancement is toggled from settings / the album pane (`AlbumCharacterPane` "Auto-Mastering"). (3) `routers/ # 18 route handlers`: 20 registered (CLAUDE.md, `check_doc_counts.py`); the script's `--check-docs` does not scan this line. (4) "Supported Audio Formats" omits AIFF/AIF/AU/OPUS that `auralis/io/formats.py::SUPPORTED_FORMATS` accepts, and an "Output (Export)" section lists WAV/FLAC while the FAQ says export is "Not yet". (5) "Neither complete suite is currently green": the frontend baseline is empty (0 failed of 3677, #6076; CLAUDE.md says "any frontend failure is new").
- **Evidence**: see per-item references; `auralis-web/frontend/test-baseline.json` `"failedTests": 0, "failures": []`.
- **Impact**: First page a user/contributor sees misdescribes the product UI and test health.
- **Siblings**: TD7-07; TD7-18.
- **Related**: none.
- **Suggested Fix**: Rewrite the "How to Use"/"Architecture" UI bullets from the sidebar items, change `18` to `20`, delete the Output list or mark it engine-only, align the formats line to `formats.py`, and reword the test-health sentence to "the frontend gate is a zero-failure ratchet; the backend gate still has baselined failures".

##### TD7-09: TESTING_GUIDELINES.md uses deleted `LibraryManager` in its fixtures and claims an enforced vitest threshold that was removed
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/development/TESTING_GUIDELINES.md:371-372`, `:650-716`, `:1165-1182`, `:1092-1095`
- **Status**: NEW
- **Age**: 5833e2fba 2025-11-06 (fixture), patched 2026-07-08 without fixing the premise
- **Effort**: small
- **Description**: The "Setup" fixture imports `auralis.library.manager.LibraryManager` and a note explains its constructor kwarg and says it is "deprecated in favor of RepositoryFactory (see auralis/library/manager.py's own docstring)": the class and module were deleted in #4915, so the fixture raises ImportError and the cited docstring does not exist; the scan-test example at `:1165-1182` repeats it (`LibraryScanner(library_manager=...)`, `manager.get_all_tracks()`). `:372` says the frontend 85%/80% thresholds are "enforced by `vitest.config.ts`": that file's own comment (`vitest.config.ts:94-105`) says the `thresholds` block was removed (#4640) and must be restored "once the known-failure baseline reaches zero" -- the baseline is now zero (#6076), so both the doc and the config comment are stale. The proposal YAML also uses `npm ci` / `npm run test:coverage` against the pnpm-only policy (#4357).
- **Evidence**: `ls auralis/library/manager.py` -> missing; `grep -n thresholds auralis-web/frontend/vitest.config.ts` -> comment only.
- **Impact**: The guidelines doc (a CLAUDE.md reference doc) gives a copy-paste conftest that cannot import and a coverage gate that is not enforced.
- **Siblings**: `pytest.ini:20-25` comment mentions LibraryManager's removal warning (historical, OK).
- **Related**: decide whether to restore the vitest thresholds now that the baseline is 0 (owning audit: `/audit-frontend`).
- **Suggested Fix**: Rewrite the two fixtures on `LibraryDatabase` + `RepositoryFactory` (tmp-file DB, per the project hazards), change `:372` to "no enforced threshold today (#4640)" or restore thresholds and keep the sentence, and switch the YAML sample to `pnpm`.

##### TD7-10: .github/INTEGRATION_GUIDE.md documents a script and workflows that do not exist
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `.github/INTEGRATION_GUIDE.md` (303 lines; `:5-13`, `:57`, `:98`, `:125`, `:138`, `:165`)
- **Status**: NEW
- **Age**: 43c983ad5 2026-07-26 (last edit added the disclaimer)
- **Effort**: trivial
- **Description**: The whole guide is a how-to for `.github/scripts/create_test_issues.py` (PyGithub auto-issue creation, with line-number edit instructions "Edit ... line 75-88"). That script does not exist (`.github/scripts/` has only `check_build_tools_locked.py`, `check_lock_matches_manifest.py`, `check_pyproject_deps.py`). The banner says `backend-tests.yml` "was deleted long ago ... none of which runs pytest", but `backend-tests.yml` exists and runs pytest with a baseline ratchet (CLAUDE.md CI table).
- **Evidence**: `ls .github/scripts`; `ls .github/workflows` lists `backend-tests.yml`.
- **Impact**: 303 lines of instructions for an unshipped feature, with a self-contradicting disclaimer; any agent reading `.github/` is told the repo has no pytest gate.
- **Siblings**: none.
- **Related**: #5160/#4272 (same genre of CI-claim rot, closed).
- **Suggested Fix**: Delete the file (git history keeps it); if auto-issue creation is wanted, track it as a feature issue.

##### TD7-11: docs/architecture/module-map.md and CLAUDE.md carry stale counts / incomplete lists the gate does not check
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/architecture/module-map.md:19`, `:45`, `:92`; `CLAUDE.md` Codebase Map (`routers/` bullet, `hooks/` bullet)
- **Status**: NEW (residue after #6246)
- **Age**: 2ebe6dc8a 2026-10-23
- **Effort**: trivial
- **Description**: module-map says tests are "~7,000 test functions" (live 8,384; CLAUDE.md says ~8,400), `analysis/` "Largest module (59 files)" (live 75; CLAUDE.md says 75, gate-checked there but not here), and `routers/ 75 modules` (live 76 non-`__init__` .py files). In CLAUDE.md the routers line says "20 registered routers" then lists 18 names, omitting `tracks` and `similarity_graph`/the second similarity router (`config/routes.py` registers 20: ... `tracks`, `similarity`, `similarity_graph`, `fingerprint_queue`); the `hooks/` line omits the `audio` domain (`hooks/audio/`, which `_audit-common.md` does list).
- **Evidence**: `python scripts/check_doc_counts.py` -> analysis 75, tests 8384, routers 20; `ls auralis-web/backend/routers/*.py | wc -l` -> 77 incl. `__init__`.
- **Impact**: Small, but two hand-maintained doc copies disagree again (the exact failure #4982 was meant to stop) because the checker only scans CLAUDE.md/_audit-common.md.
- **Siblings**: none.
- **Related**: #4982, #6250.
- **Suggested Fix**: Extend `scripts/check_doc_counts.py --check-docs` to cover `docs/architecture/module-map.md` (analysis files, test functions, router modules), then fix the three numbers and complete the CLAUDE.md router/hook name lists (or drop the enumerations and say `see config/routes.py`).

##### TD7-12: ARCHITECTURE.md's flagship "CORRECT" repository example calls a method that does not exist
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `ARCHITECTURE.md:15-18`, `:35-38`
- **Status**: NEW
- **Age**: 85b5d4fd5 2026-01-03
- **Effort**: trivial
- **Description**: The example is `repos = repository_factory.create(); track = repos.tracks.get_by_id(track_id)`. `RepositoryFactory` (`auralis/library/repositories/factory.py`) has no `create()`; it is constructed with a session factory and exposes lazy properties (`repos.tracks`, ...). The "violates DI" counter-example repeats the call.
- **Evidence**: `grep -n "def create" auralis/library/repositories/factory.py` -> none.
- **Impact**: The canonical pattern doc shows an AttributeError.
- **Siblings**: none.
- **Related**: none.
- **Suggested Fix**: Use the real shape (`repos = get_repository_factory(); repos.tracks.get_by_id(...)` as in `factory.py`'s docstring) in both snippets.

##### TD7-13: Source comments/docstrings naming symbols that no longer exist
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: see Evidence (13 sites)
- **Status**: NEW
- **Age**: various
- **Effort**: small
- **Description**: Present-tense references with no definition anywhere: `usePlayNormal` (hook gone, consolidated) at `auralis-web/backend/core/stream_lifecycle.py:64`, `frontend/src/store/slices/playerQueueSync.ts:26`, `contexts/WebSocketContext.tsx:93`, `hooks/enhancement/useEnhancedStreamStart.ts:178` ("Kept identical to usePlayNormal.ts"), `hooks/enhancement/streamingCoreTypes.ts:37`; `DistanceCalculator.get_dimension_contributions()` at `auralis-web/backend/routers/similarity_models.py:13` (class is `FingerprintDistance`, `analysis/fingerprint/distance.py`); `TemporalOperations.calculate_rhythm_stability/calculate_silence_ratio` "Python reference" at `vendor/auralis-dsp/src/rhythm.rs:29,52,92,621` (Python class removed with the sampling/librosa subsystem, #13 Stage 4); `library_database.get_all_tracks()` example at `auralis-web/backend/routers/errors.py:133` (a LibraryManager method; no such method on `LibraryDatabase`); `encode_to_wav()` "in core/chunked_processor.py" at `auralis-web/backend/cache/models.py:25` (function deleted, #5147); "Same logic as auto_master.py's generate_adaptive_parameters()" inside `auralis/player/realtime/auto_master.py:133` (self-reference to a name that is `_generate_adaptive_parameters`); `ChunkedProcessor` (class is `ChunkedAudioProcessor`) at `core/audio_stream_controller.py:108`, `core/stream_chunk_ops.py:54,149`, `core/stream_enhanced_lifecycle.py:77` (user-visible `ValueError("ChunkedProcessor not available")`), `auralis-web/backend/CONFIG.md`; `useArtworkUpdates` (hook is `useArtworkRevision`) at `store/slices/playerQueueSync.ts:102`; `stream_normal/enhanced/seek_chunks.py` ("all three pumps") at `core/stream_lifecycle.py:36` (no seek pump since #5761); `python apply_fingerprinting_optimization.py` printed by `scripts/development/optimize_fingerprinting_for_hardware.py:141` (script absent).
- **Evidence**: each name returns zero definitions via `grep -rn "def X\|class X\|function X\|const X"`.
- **Impact**: Each is a small dead-end; the user-facing `ValueError` and the printed command are the only ones a user sees.
- **Siblings**: TD7-04, TD7-05.
- **Related**: `scripts/check_breadcrumbs.py` polices "was removed in #N" phrasing only, not live references to deleted names.
- **Suggested Fix**: One sweep commit per language fixing the 13 sites; consider extending `check_breadcrumbs.py` or adding a small CI check that CamelCase/`useX` identifiers in comments resolve to a definition (the extractor used here found these in minutes).

##### TD7-14: Three `file:LINE` anchors in source comments have rotted
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/backend/core/proactive_buffer.py:84`, `auralis-web/backend/schemas/websocket.py:26`, `auralis-web/backend/routers/artwork_deps.py:37`
- **Status**: NEW
- **Age**: n/a
- **Effort**: trivial
- **Description**: `proactive_buffer.py:84` says "Mirrors the streaming path at audio_stream_controller.py:597" -- the file is 296 lines. `schemas/websocket.py:26` cites `websocket_security.py:187` as the receive-path validation; line 187 is in `force_cleanup`, validation is `validate_and_parse_message` at `:217`. `artwork_deps.py:37` cites `types/ws/enhancement.ts:71-78` (the interface is at `:72`, roughly right but fragile). The gate rejects `path:NNN` only in the strict doc set (#6248) -- not in code comments.
- **Evidence**: `wc -l auralis-web/backend/core/audio_stream_controller.py` -> 296.
- **Impact**: Misdirects; also shows #6248's policy was not applied to source.
- **Siblings**: none (only three exist in non-test source).
- **Related**: #6248.
- **Suggested Fix**: Replace with symbol anchors (`stream_enhanced_lifecycle.py::asyncio.to_thread(ChunkedAudioProcessor, ...)`, `websocket_security.py::validate_and_parse_message`, `types/ws/enhancement.ts::ArtworkUpdatedMessage`).

##### TD7-15: backend/CONFIG.md lists 9 of ~35 AURALIS_* environment variables and points at a private memory file
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/backend/CONFIG.md:3-6`, table
- **Status**: NEW
- **Age**: n/a
- **Effort**: small
- **Description**: The file presents itself as the list of overridable tuning constants. Code reads 28 more `AURALIS_*` variables that are not documented: `AURALIS_DATA_DIR`, `AURALIS_DEV_MODE`, `AURALIS_LOG_LEVEL`, `AURALIS_PORT`, `AURALIS_VERSION`, `AURALIS_MAX_DECODED_BYTES`, `AURALIS_MAX_DURATION_SECONDS`, `AURALIS_FINGERPRINT_TRACK_TIMEOUT`, `AURALIS_IO_POOL_WORKERS`, `AURALIS_JOB_POOL_WORKERS`, `AURALIS_TRANSPORT_POOL_WORKERS`, `AURALIS_DISCOGS_TOKEN`, `AURALIS_LASTFM_KEY`, and fourteen `AURALIS_RATE_LIMIT_*_{MAX,WINDOW}` pairs. Line 5 links `[project_desktop_only.md]`, a file in the maintainer's private memory directory, not in the repo (unresolvable link).
- **Evidence**: `grep -rhoE "AURALIS_[A-Z_0-9]+" auralis auralis-web/backend desktop launch-auralis-web.py | sort -u` vs `grep -oE ... CONFIG.md`.
- **Impact**: Operators cannot discover the data-dir, pool and rate-limit knobs; the dangling link looks like a typo.
- **Siblings**: none.
- **Related**: none.
- **Suggested Fix**: Add the missing variables (generate from `get_int_env(`/`os.environ.get(` call sites), retitle as "reference" and replace the memory-file link with CLAUDE.md's desktop-only statement.

##### TD7-16: docs/subsystems/backend-api.md still counts a removed REST chunk path and lists client messages that do not exist
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/subsystems/backend-api.md:140`, `:178-195`, `:224`
- **Status**: NEW
- **Age**: dbb3b4a5e 2026-07-11 and later patches
- **Effort**: small
- **Description**: (1) `:138-140` "Client -> server (validated subset in `schemas/websocket.py::WebSocketMessageType`)" lists `processing_settings_update` and `ab_track_loaded`: neither exists in the enum, any handler, or the frontend (grep across `auralis-web`). (2) Section 5 is titled "three paths" and its table's third row is "REST WAV chunk (removed)"; the note below it ("Default overlap is 5 s, everywhere. Both the WS and REST WAV paths default to duration=15 / interval=10") refers to the deleted path, and `stream_normal.py:150` documents that normal streaming uses no overlap. (3) The concurrency table lists `_active_streams_lock` (no definition anywhere).
- **Evidence**: `grep -rn "processing_settings_update\|ab_track_loaded\|_active_streams_lock" auralis-web auralis` -> only this doc.
- **Impact**: Mis-states the WS contract and the overlap model in the doc meant to be the backend map.
- **Siblings**: TD7-03.
- **Related**: `/sync-contracts`.
- **Suggested Fix**: Delete the two message names, retitle section 5 "two paths", rewrite the overlap note as "enhanced WS stream: 15 s render / 10 s emitted segments; normal stream: no overlap (`chunk_boundaries.normal_stream_plan`)", and drop `_active_streams_lock`.

##### TD7-17: Frontend test/launch docs use npm and Jest-only flags with no historical marker
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/frontend/testing/TESTING_COMMANDS.md` (39 npm lines, `--testPathPattern`), `docs/frontend/testing/{MEMORY_TEST_README,MEMORY_TEST_SETUP,TESTING_MEMORY_GUIDE,MEMORY_TEST_QUICKSTART,FRONTEND_TESTING_STRATEGY}.md`, `docs/frontend/QUICK_REFERENCE.md` (`npm run typecheck`, script is `type-check`), `docs/getting-started/LAUNCH.md` (`npm run lint`/`format`, no such scripts), `auralis-web/frontend/src/test/README.md`
- **Status**: NEW
- **Age**: Nov-Dec 2025
- **Effort**: medium
- **Description**: CLAUDE.md: "pnpm is the only supported JS package manager (#4357)". About 200 `npm run|test|install|ci` lines remain across these docs; `TESTING_COMMANDS.md` also uses Jest's `--testPathPattern` (not a vitest flag). Only LAUNCH.md and a few siblings carry a "historical" banner. The scripts they name mostly exist, so the failure is policy/flag drift, not total breakage.
- **Evidence**: `grep -rP "(?<!p)npm (run|test|install|ci)\b" docs --include=*.md` (excluding archive/audits) -> 26 files; `package.json` scripts has no `lint`, `format`, `typecheck`.
- **Impact**: A contributor following the cheat-sheet can create an npm lockfile (what #4357/#4558 removed) or run non-existent flags.
- **Siblings**: part of the same population as the 120-entry ratchet baseline (53 entries are `docs/frontend/*`).
- **Related**: #4558.
- **Suggested Fix**: Move `docs/frontend/{testing,analysis,implementation,components}` (historical sprint material) into `docs/archive/frontend-history/` as #6255 did for UI_DESIGN_GUIDELINES.md, keep one current testing page (`docs/subsystems/frontend.md` + CONTRIBUTING), and fix `QUICK_REFERENCE.md`'s script name. This also shrinks the ratchet baseline by ~53 entries.

##### TD7-18: README / RELEASE_CHECKLIST recovery-blocker status is not reconciled with fixes landed since 2026-07-24
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `README.md:416-424,466-480`, `docs/releases/RELEASE_CHECKLIST_1_5_1.md:25-33`, `docs/releases/RELEASE_NOTES_1_5_1.md`
- **Status**: NEW (needs owner re-verification before editing)
- **Age**: audit dated 2026-07-24
- **Effort**: small
- **Description**: README and the checklist list as open release blockers: REC-02 "fresh databases silently fail their first fingerprint inserts", REC-03 "(samples, 1) mono enhancement crashes", REC-04 / #4426 "rapid selection". Since then #5321 (fresh-DB fingerprint indexes), #5550 (HIGH, mono (N,1) crash in K-weighted meter), #6118 (HybridProcessor input contract), #6138, #4494 and #4426 (all CLOSED) landed. The checklist may still be right if the smoke test was not re-run, but no file records a re-verification, and the checklist cites closed #4426 as current.
- **Evidence**: `jq` over `issues.json`: #4426 CLOSED 2026-07-12, #5550 CLOSED 2026-10-16, #6118 CLOSED 2026-10-22.
- **Impact**: The public status page may overstate blockers (or the closed issues may not cover the REC wording); either way the next release decision reads this file.
- **Siblings**: TD7-08.
- **Related**: release gate, `/verify-release`.
- **Suggested Fix**: Run the REC-02/03/04 acceptance checks once, tick or annotate each item with the verifying commit/issue, and mirror the result in README's "Release blockers" list.

##### TD7-19: 120 baselined stale path refs sit in 35 historical docs; the ratchet only freezes them
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `.claude/commands/_audit-validate-baseline.txt` (35 files: `docs/frontend/*` 53 refs, `docs/ui_audit/*` 19, `docs/features/*` 15, `docs/deployment/*` 9, `docs/troubleshooting/*` 7, `docs/testing/*` 7, `docs/getting-started/*` 6, `docs/versions/*` 3)
- **Status**: NEW (the gate tracks it, no issue owns the burn-down)
- **Age**: baseline since #5144 (2026-08)
- **Effort**: medium
- **Description**: The baseline is working as designed but has not moved (120 vs 120). The files are sprint-era analyses (`docs/ui_audit`, `docs/frontend/analysis`, `PLAYERBARV2_REFACTORING_COMPLETE.md`, `PHASE2_COMPLETE.md`) referencing deleted components (`CozyLibraryView.tsx`, `BottomPlayerBarUnified.tsx`, `ProcessingToast.tsx`). `docs/README.md` already marks `docs/archive/` as the place for such material.
- **Evidence**: `awk -F'\t' '{print $1}' _audit-validate-baseline.txt | sort | uniq -c`.
- **Impact**: ~30 files that cannot be trusted and cost every doc grep.
- **Siblings**: TD7-17.
- **Related**: none.
- **Suggested Fix**: Move the 35 files (whole `docs/ui_audit/`, `docs/frontend/{analysis,implementation,components}`, completion reports) to `docs/archive/` in one commit and regenerate the baseline with `--update-baseline`; the ratchet target becomes ~10 entries.

#### Dimension 8: Backwards-Compat Cruft & No-Variants

##### TD8-01: Deletion "breadcrumb" comments survive `check_breadcrumbs.py` because its regex is too narrow
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: ~17 sites (list under Evidence); gate at `scripts/check_breadcrumbs.py:38-42`
- **Status**: NEW (the gate came from #6257; it is the 7th regrowth cycle after #4088/#4293/#4649/#5034/#5820/#6257)
- **Age**: gate 2026-10-22; most comments Oct-Nov 2026
- **Effort**: small
- **Description**: `BREADCRUMB` only matches `(was|were|been) (removed|deleted|dropped|retired) (in|by|with) #N` on ONE line. The same history-narration regrows in forms it cannot see: `gone (#N)`, `retired (#N)`, `went with #N`, `now-deleted, #N`, `removed (#N)`, `(deleted here — #N`, and the phrase wrapped across a line break. `check_breadcrumbs.py` exits 0 on a tree that still has all of these.
- **Evidence** (each is a past-tense deletion note, not a present-tense constraint):
  - `auralis/core/processing/continuous_space_types.py:20-21` "(a third, energy level, was\n removed in #6123: no parameter read it)" (line-wrapped, evades the single-line regex)
  - `auralis/library/repositories/fingerprint_repository.py:18-20` "delegators that used to bridge the split are gone (#6264)"
  - `auralis-web/frontend/src/utils/apiRequest.ts:20-27` "The standardized client is retired (#4693)... The former duplicate is gone (#6216)... `restApiTransport.ts` ... is deleted."
  - `auralis-web/frontend/src/hooks/library/useLibraryQueries.ts:5-8` "had none and were removed (#6287)"
  - `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:5` "(both removed, #6287)"
  - `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts:74` "(now-deleted, #5231)"
  - `auralis-web/frontend/src/services/playlistService.ts:95` "the bare-array legacy serializer tolerance went with #6260"
  - `auralis-web/frontend/src/services/api/cacheShapeGuards.ts:15-16` "Renamed from the retired client's old filename in #6197"
  - `auralis/dsp/dynamics/settings.py:21` "went with AdaptiveLimiter in #4873"; `auralis/dsp/dynamics/compressor.py:106` "now-deleted AdaptiveLimiter — #4873"
  - `auralis/dsp/eq/psychoacoustic_eq.py:162-163` "went with the #5763 engine removal, #6202"
  - `auralis/core/hybrid_processor.py:226` "(#2400) went with #4873"
  - `auralis/core/processing/continuous_dsp_ops.py:108` "Removed following #5309's precedent"
  - `auralis/library/scanner/scanner.py:66-68` "parameter this used to accept went with the dead `_enqueue_fingerprints` (#4648)"
  - `auralis-web/backend/core/chunked_processor.py:177-178` "(#5056: `previous_chunk_tail` removed ... went with #4642/#3880.)"
  - `auralis-web/backend/routers/pagination.py:27` "(deleted here — #5054"; `auralis-web/backend/core/processor_cache_key.py:36` "that executor is gone, see #4744"
  - `vendor/auralis-dsp/src/lib.rs:11-12` "all lacked one and went (#5764, #5738)"
- **Impact**: The comments are history that `git log` already carries, rot as soon as the surrounding code changes, and the "gate" gives false assurance (CLAUDE.md/#6257 say the gate is the control). Dozens more `used to / previously / formerly ... #NNNN` narrations (109 non-test lines carry an issue number; 436 lines match the words at all) are the same habit; most explain a live behaviour change and are not all deletable, but the ones that only describe a deleted thing are.
- **Siblings**: the long tail of "used to ..." comments (e.g. `auralis/core/mastering_branches/continuous.py:49` "abstract ProcessingBranch base used to sit above it", `auralis-web/backend/services/artwork_downloader.py:35-40` "_detect_image_extension used to be defined here", `auralis-web/backend/config/startup/components.py:34` "A ~/Music/Auralis directory used to be created here")
- **Related**: #6257, #5820 (CLOSED; gate regression)
- **Suggested Fix**: Delete the comments above, keeping any present-tense constraint ("Do not re-add X: reason"). Widen `BREADCRUMB` to join each comment block before matching and to accept verbs `gone|went|retired|removed|deleted|dropped` followed within ~30 chars by `#N` (excluding "(#N)" behavioural references like `dropped silently (#3512)`: require the subject to be a symbol/module, or just add the 17 hits to the baseline set while shrinking it).

##### TD8-02: Second, dead `SearchBar` (and a dead GlobalSearch cluster) next to the live one
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft & No Variants
- **Location**: `auralis-web/frontend/src/components/library/SearchBar.tsx` (241 lines) vs `auralis-web/frontend/src/components/navigation/SearchBar.tsx` (97 lines); `auralis-web/frontend/src/components/library/Search/*` (+ `components/library/Styles/SearchStyles.styles.ts`, 653 lines)
- **Status**: NEW
- **Age**: library/SearchBar 2025-11 (b21447340); navigation/SearchBar 2025-10
- **Effort**: small
- **Description**: Two components named `SearchBar` implement the same debounced search input with different APIs (`onSearch` vs `value/onChange`). The only live consumer (`components/CozyLibraryView/LibrarySearchControls.tsx:4`) imports `@/components/navigation/SearchBar`. `components/library/SearchBar.tsx` has zero production importers (only `components/library/__tests__/SearchBar.test.tsx`). Separately the `components/library/Search/` cluster (GlobalSearch, SearchInput, ResultsContainer, ResultGroup, SearchResultItem, ResultAvatar) is imported by nothing outside itself and its test `components/library/__tests__/GlobalSearch.test.tsx`; its entry `GlobalSearch` accepts `onClose` and discards it: `components/library/Search/GlobalSearch.tsx:36` `({ onResultClick, onClose: _onClose })`.
- **Evidence**: `grep -rn "library/SearchBar\|GlobalSearch" src | grep -v __tests__` returns only the files themselves and comments.
- **Impact**: A change to search behaviour (debounce, a11y label, keyboard hint) can be applied to the wrong copy; the dead copy keeps its tests green and inflates the 300-line/ratchet counts.
- **Siblings**: `components/library/Styles/EmptyState.styles.ts` (19 lines, `export {}` with a stale header comment); `components/library/Styles/SearchStyles.styles.ts`
- **Related**: audit-frontend / Dim 2 (dead code) own the deletion side
- **Suggested Fix**: Delete `components/library/SearchBar.tsx` + its test, the `components/library/Search/` cluster + `GlobalSearch.test.tsx`, `SearchStyles.styles.ts`, and `EmptyState.styles.ts` in `library/Styles`.

##### TD8-03: Design-system `ProgressBar` primitive is an unused twin of `components/player/ProgressBar.tsx`
- **Severity**: LOW
- **Dimension**: No Variants
- **Location**: `auralis-web/frontend/src/design-system/primitives/ProgressBar.tsx` (108 lines, exported via `primitives/surface` and `primitives/index.ts:17`) vs `auralis-web/frontend/src/components/player/ProgressBar.tsx` (139 lines, used by `Player.tsx:17`)
- **Status**: NEW
- **Age**: 2025-10 / 2025-11
- **Effort**: small
- **Description**: Two components named `ProgressBar`. The player one is the only one rendered; nothing outside `design-system/` imports the primitive (no `ProgressBar` import from `@/design-system` in any production file), so the "design-system single source of truth" copy is the dead one.
- **Evidence**: `grep -rn "\bProgressBar\b" src --include=*.tsx | grep import` lists only `components/player/Player.tsx`.
- **Impact**: Accessibility fixes (#3608, #2538, #3651 touched both lineages) have to be double-checked against the unused copy.
- **Related**: audit-frontend Dim 5 (design system)
- **Suggested Fix**: Delete the primitive and its `surface`/`index` re-exports and tests; if a shared primitive is wanted, have `player/ProgressBar` build on it instead.

##### TD8-04: Frontend props and hook results accepted and dropped via `_`-renaming
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: see Evidence
- **Status**: NEW
- **Age**: various (SearchKeyboardHint 2025-12-26, 8c39d0215)
- **Effort**: small
- **Description**: CLAUDE.md says delete, don't rename to `_var`. These destructure a prop/result under a `_` name and never read it, and their callers keep feeding them:
  - `components/navigation/SearchKeyboardHint.tsx:11` `({ show: _show })` and the whole component body is `return null`; rendered at `components/navigation/SearchBar.tsx:92` with `show={!internalValue && !autoFocus}`.
  - `components/shared/ui/loaders/LoadingSpinner.tsx:37` `gradient: _gradient = tokens.gradients.aurora` (the prop is declared at line 11 and ignored; the SVG gradient is built from `tokens.colors.*` stops).
  - `components/shared/MediaCard/MediaCardArtwork.tsx:81` `variant: _variant`, passed at `MediaCard.tsx:235` `variant={props.variant}`.
  - `components/shared/ContextMenu/ContextMenu.tsx:57` `trackTitle: _trackTitle`.
  - `components/shared/ContextMenu/PlaylistSection.tsx:72` `isLoadingPlaylists: _isLoadingPlaylists`, fed from `ContextMenu.tsx:125`, `TrackRow.tsx:207`, `TrackTableRowItem.tsx:141`.
  - `components/library/Controls/BatchActionsToolbar.tsx:79` `handleAction: _handleAction` (from `useBatchActionsMenu.ts:20,29`, which exports a handler nothing uses).
  - `design-system/primitives/SegmentedControl.tsx:69` `({ size: _size })`.
  - Five no-op `styled(...)(({ theme: _theme }) => ...)` callbacks: `LoadingSpinner.tsx:87`, `AlbumArtDisplay.tsx:89`, `BatchActionsToolbarStyles.ts:12,43,50,59`, `SelectableTrackRow.styles.ts:10`.
- **Evidence**: see per-line locations; each `_name` has no further reference in its function body.
- **Impact**: A caller can set `gradient` / `variant` / `trackTitle` and believe it has an effect; each dead prop widens the prop interface and test surface.
- **Siblings**: `Components/library/Search/GlobalSearch.tsx:36` (see TD8-02)
- **Related**: #5821 (CLOSED; "Parameters kept for call-site compatibility" sweep did not reach these)
- **Suggested Fix**: Remove each parameter from the component's props interface and from every caller; drop `trackTitle`/`isLoadingPlaylists` plumbing through `ContextMenu`; delete `SearchKeyboardHint` and its render at `SearchBar.tsx:92`; replace the `theme: _theme` callbacks with plain style objects.
- **Merge note**: absorbs TD5-04 (context-menu `isLoadingPlaylists` plumbed through `TrackRow` -> `ContextMenu` -> `PlaylistSection` and never rendered; also `MediaCardArtwork.variant`, `useBatchActionsMenu.handleAction`, `SegmentedControl` `size`, and the dead `_ThemeProvider` import in `src/index.tsx`). Preferred fix for the loading row is to render it.

##### TD8-05: Python parameters left behind by refactors (still fed by callers)
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/core/analysis/target_fingerprint_adjustments.py:28-29`, `auralis/core/analysis/target_preset_overrides.py:20`, `auralis/core/processing/cross_dimensional_guard.py:152-154`, `auralis/library/scanner/scanner.py:266`
- **Status**: NEW
- **Age**: (module-level functions are leftovers of a method-to-function split, #4511-era)
- **Effort**: trivial
- **Description**: `ruff --select ARG` over `auralis/` + `auralis-web/backend/` yields 11 hits; 4 are real dead parameters (the rest are callback/protocol signatures):
  - `apply_fingerprint_enhancements(generator, targets, fingerprint)` and `apply_preset_overrides(generator, targets, ...)` never read `generator`; the only production callers are `target_generator.py:144,148`, which pass `self`; the regression test passes `None` (`tests/auralis/core/test_band_share_thresholds_5858.py:22`).
  - `CrossDimensionalGuard.check_normalization_side_effects(..., post_dynamics=None)` never reads it; `cross_dimensional_guard.py:213-214` computes `dynamics_snap` and passes it anyway.
  - `LibraryScanner.scan_folder(..., **kwargs)` documents "Additional arguments for scan" and drops them (`scanner.py:266-285`).
- **Impact**: Misleading signatures: a reader assumes `generator` state or dynamics snapshots influence the result.
- **Related**: #5821 (CLOSED; same class)
- **Suggested Fix**: Drop `generator` from both functions and their `target_generator.py:141-148` wrappers; drop `post_dynamics` and the `post_dynamics=dynamics_snap` argument; drop `**kwargs` from `scan_folder`.

##### TD8-06: Playback settings with a UI, a DB column and an API field but no consumer anywhere (crossfade, gapless, replay-gain)
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft (legacy path with no remaining producer/consumer)
- **Location**: `auralis/library/models/settings.py:32-35`, `auralis/library/repositories/settings_repository.py:127-128`, `auralis-web/backend/routers/settings_models.py:48-51,118-121`, `auralis-web/frontend/src/components/settings/PlaybackSettingsPanel.tsx:40,57,72,92`, `SettingsDialogContent.tsx:59-61`, `services/settingsService.ts:24-27,64-67`, `types/ws/player.ts:73-75,91-93,109-111`
- **Status**: NEW
- **Age**: columns from the original schema; crossfade machinery removed #2750/#3514/#4642
- **Effort**: medium (needs a product call: delete vs implement)
- **Description**: `crossfade_enabled`, `crossfade_duration`, `gapless_enabled` and `replay_gain_enabled` are stored, validated, returned and editable in Settings, but nothing in `auralis/player/`, `auralis-web/backend/core/` or the streaming path reads them (the gapless prebuffer is unconditional; the streaming path has deliberately no crossfade; no ReplayGain code exists). `transformPlayerState` additionally fabricates `gaplessEnabled=true / crossfadeEnabled=true / crossfadeDuration=3.0` from fields the backend `PlayerState` never emits (own comment at `types/ws/player.ts:65-72` admits this), and nothing consumes them.
- **Evidence**: `grep -rnE "crossfade_(enabled|duration)|gapless_enabled|replay_gain" auralis auralis-web/backend` -> only model/repository/pydantic schema lines; frontend hits are only the settings panel, service types and the unused transformer.
- **Impact**: Three switches and a slider in the UI do nothing (placebo controls), and the retired crossfade stays a user-visible concept.
- **Siblings**: `ProcessingCoordinates.expansion_params` / `dynamics_blend` generated but unconsumed (`continuous_dsp_ops.py:104-112` says "remain available as reporting data")
- **Related**: product decision (same shape as #4861's ship-or-delete); audit-frontend for the UI side
- **Suggested Fix**: If these features are not planned: drop the three controls from `PlaybackSettingsPanel`, the fabricated fields from `types/ws/player.ts`, and add a migration dropping the columns (schema v33) in the same change that removes the API fields. If planned: file the implementation and keep, but stop showing the controls until they work.

##### TD8-07: Re-exports "for existing importers" left by the #6270-#6273 / #4511 splits that only tests use
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: see Evidence
- **Status**: NEW (sibling sweeps #5775 and #5827 were closed on 2026-10-21; these re-exports were created or left after them)
- **Age**: #6273 split, 2026-10-25+
- **Effort**: small
- **Description**: Each module re-exports names so "existing imports keep working", but every production importer already uses the new home; only tests (or nothing) use the old path.
- **Evidence**:
  - `auralis/io/unified_loader.py:35-39` `from .audio_probe import (_get_info_with_ffprobe, _get_info_with_soundfile, _reject_oversize_probe, get_audio_info)  # noqa: F401 (pre-split import paths, #6273)`. Backend uses `auralis.io.audio_probe` directly (`chunk_metadata.py:27`, `seekable_source.py:58`, `files_upload.py:10`). Also nine now-unused imports in the same file (`json`, `subprocess`, `soundfile`, `warning`, `FFPROBE_TIMEOUT_S`, `SUBPROCESS_TEXT_KWARGS`, `check_ffprobe`, `ffprobe_command`, `redact_subprocess_output`) and the comment at `:42-43` claiming `SUPPORTED_FORMATS`/`FFMPEG_FORMATS` are re-exported "for existing importers" (only `tests/test_unified_loader.py` imports them). Real defect it hides: `tests/test_unified_loader.py:196` patches `auralis.io.unified_loader._get_info_with_soundfile`, but `get_audio_info` now lives in `audio_probe` and calls its own module global, so the patch is vacuous (note for the test-hygiene owner).
  - `auralis-web/backend/services/scan_events.py:23` `from .scan_fingerprint_enqueue import enqueue_scanned_for_fingerprinting  # noqa: F401 — re-exported: the two scan sites import everything scan-related from here`; the two scan sites (`library_auto_scanner.py:30`, `library_scan_events.py:19`) import it from `scan_fingerprint_enqueue` directly; only `tests/backend/test_enqueue_updated_tracks_5719.py:17` uses the re-export. The comment is false.
  - `auralis-web/backend/core/chunk_cache_manager.py:25` re-exports `INTENSITY_KEY_DECIMALS` with zero importers anywhere.
  - `auralis-web/backend/core/stream_normal.py:37-39` `MAX_CONSECUTIVE_READ_TIMEOUTS` (test attribute access only); `core/level_manager.py:21-26` `GAIN_RAMP_SECONDS`, `MAX_GAIN_CORRECTION_DB` (tests only); `security/path_security.py:49` `_extra_allowed_dirs` (tests only); `core/processing/continuous_space.py:34` `ProcessingParameters` (tests only); `core/hybrid_processor.py:28` `AdaptiveTargetGenerator, ContentAnalyzer  # re-exported: tests/test_adaptive_processing.py`.
  - `auralis/library/migration_manager.py:7-9,25-31,40-45` re-exports `backup_database`, `restore_database`, `migration_lock` ("so every existing import of this module keeps working" and lists them in `__all__`); only `tests/test_migrations.py:20-26` and `tests/concurrency/test_migration_lock_identity_4523.py:33` import them from here.
  - `auralis-web/backend/core/chunk_fingerprint_registry.py:12-14` says `_default_get_fingerprints_repository` / `_reset_registry_miss_warning` are "re-exported from `core.chunked_processor` (its historical home)"; `chunked_processor.py` re-exports neither (grep empty). Stale claim.
- **Impact**: Keeps dead aliases and F401 suppressions alive, makes the import graph look like it has consumers it lacks, and (unified_loader) hides vacuous test mocks.
- **Siblings**: `auralis-web/backend/core/processing_engine.py:41-42,244` and `core/job_error_mapping.py:12-14` ("keeps working for routers/tests"); `services/artwork_downloader.py:35-40` ("_detect_image_extension ... re-imported under the original name ... tests import keep working")
- **Related**: #5775, #5827 (CLOSED, same class)
- **Suggested Fix**: Delete each re-export and unused import, repoint the listed tests at the real module (`audio_probe`, `scan_fingerprint_enqueue`, `migration_backup`/`migration_lock`, `path_allowlist`, `stream_normal_chunks`, `level_constants`), fix the vacuous `unified_loader._get_info_with_soundfile` patch, and delete the stale docstring claims.
- **Merge note**: shares the `unified_loader.py` re-export block and four vacuous test patches with TD2-03; fix them in one change.

##### TD8-09: AdaptiveCompressor `enable_lookahead` / `lookahead_ms` / `LookaheadBuffer` no longer take part in the signal path
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/dsp/dynamics/compressor.py:36-42,98-110,168-176,193`, `auralis/dsp/dynamics/settings.py:21-29,54-55,63`, `auralis/dsp/dynamics/lookahead_buffer.py` (83 lines)
- **Status**: NEW
- **Age**: lookahead_buffer.py 93b3fc5fe 2026-07-18; made inert by #4913 (2026-07-29)
- **Effort**: small
- **Description**: After #4913 the compressor computes levels from, and applies gain to, the undelayed `audio`; the comment at `compressor.py:107-110` says `_apply_lookahead` / `_lookahead` "are kept as directly-tested helpers ... but are no longer part of this signal path". `CompressorSettings.enable_lookahead` (default True) and `lookahead_ms` (clamped to `LOOKAHEAD_MS_BOUNDS`) therefore configure nothing; `LookaheadBuffer` has no other user (the limiter has its own window); the `lookahead_buffer` property has no production reader.
- **Evidence**: `grep -rn "LookaheadBuffer\|\.lookahead_buffer\|_apply_lookahead" auralis auralis-web/backend` -> only `compressor.py`; tests: `tests/regression/test_compressor_lookahead_buffer.py`, `test_lookahead_buffer_dedup_4309.py`.
- **Impact**: A tunable that silently does nothing, plus 83 lines and two regression tests guarding an unused helper (the compressor is only reachable through `player/realtime/auto_master.py`, a dormant path per #5579).
- **Related**: #4913, #4309, #5579 (CLOSED)
- **Suggested Fix**: Delete `lookahead_buffer.py`, `_lookahead`, `_apply_lookahead`, the property, `enable_lookahead`, `lookahead_ms`, `LOOKAHEAD_MS_BOUNDS` and the two tests; update `settings.py:15-29` comment.

##### TD8-10: `auralis-web/backend/version.py` is dead, and carries a client-compat gate nobody checks
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/version.py:1-36`; `auralis-web/backend/schemas/system.py:44`; `auralis-web/backend/routers/health.py:70-99`
- **Status**: NEW
- **Age**: 2025-10-15 (f17c9ac14 lineage), last touched e4353a53c (version bump)
- **Effort**: trivial
- **Description**: `backend/version.py` defines `API_VERSION`, `API_VERSION_INFO`, `MIN_CLIENT_VERSION = "1.0.0"` ("Minimum client version required to connect") and its own `get_version_info()`. Nothing imports it (the version route uses `auralis.version.get_version_info`, `health.py:74`); no test references it; no client ever sends or checks a version (single-client desktop app). `VersionInfoResponse.api_version` is `"v1"` "for compatibility" (`schemas/system.py:44`), hard-coded again in the degraded fallback at `health.py:94`, and no frontend code reads `api_version` (the only `/api/version` mention is a test mock, `test/mocks/handlers.ts:707`). `sync_version.py:159-162` still rewrites the hard-coded fallback copy in `health.py`.
- **Impact**: A second version authority and a version-compat contract with no enforcement; every release bump touches it.
- **Related**: Dim 2 (dead module); Dim 7 doc `docs/deployment/VERSION_SYSTEM_IMPLEMENTATION.md:40`
- **Suggested Fix**: Delete `backend/version.py`; drop `api_version` from `VersionInfoResponse`/the fallback (and from `auralis/version.py:48` docstring) or leave a single constant; remove the `health.py:80-99` hard-coded "degraded build" copy, since the backend cannot start without `auralis` anyway.

##### TD8-11: Nested-fingerprint layout is tolerated by three readers although no writer produces it
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft (legacy path with no remaining producer)
- **Location**: `auralis/library/sidecar_manager.py:231-237`, `auralis/library/sidecar_fingerprint_check.py:30-38`, `auralis-web/backend/core/mastering_target_generation.py:50-58,70-74`
- **Status**: NEW
- **Age**: sidecar reader 2025-10-29 (6a38afa6d); target generator #2726-era
- **Effort**: small
- **Description**: The only `.25d` writer (`services/fingerprint_extractor.py:225-227` -> `SidecarManager.write`, FORMAT_VERSION 2.0) stores the flat 25-key dict, and `validate` rejects any other `format_version`. `get_fingerprint()` still "Flatten[s] nested structure if needed" (`frequency`/`dynamics`/... sub-dicts) and `fingerprint_block_is_valid` mirrors that branch. In `generate_targets_from_fingerprint`, all three producers (`fingerprint_loading.py:92-113` DB tier, file tier, extract tier) return the flat dict (comment #5938), yet the function still handles a `MasteringFingerprint` object via `hasattr(fingerprint, '__dict__')` and falls back to nested `freq.get(...)` / `dynamics.get(...)`. `MasteringFingerprint` is a 7-field unrelated type that never reaches it.
- **Evidence**: tests only exercise the flat shape (`tests/backend/test_fingerprint_tier1_dict_5938.py`, `test_target_eq_*`); no test builds a nested sidecar.
- **Impact**: Three extra branches that look load-bearing, and `TrackFingerprint.to_dict()` (which does emit the nested form, `models/fingerprint.py:140`) invites the belief that nested is a live interchange format.
- **Related**: #5938 (CLOSED)
- **Suggested Fix**: Delete the nested branches in the two sidecar readers and the object/nested handling in `generate_targets_from_fingerprint`; type its parameter `dict[str, float]`.

##### TD8-12: `useStandardizedAPI.ts` is a misnamed file holding only `useCacheStats`
- **Severity**: LOW
- **Dimension**: No Variants (retired-variant name outlives the variant)
- **Location**: `auralis-web/frontend/src/hooks/shared/useStandardizedAPI.ts` (112 lines), imported by `components/shared/CacheStatsDashboard.tsx:18`; referenced at `services/api/cacheShapeGuards.ts:6`
- **Status**: NEW (#6197 renamed the client file, not this hook file)
- **Age**: 2025-12-02 (d0c15ffd6)
- **Effort**: trivial
- **Description**: The module's own header says it is "Cache telemetry hook - `useCacheStats`" and "NOT a generic REST client", after the `StandardizedAPIClient`/`CacheAwareAPIClient` it was named for were retired (#4693). The file name still advertises the retired variant.
- **Impact**: Misleads anyone searching for the app's API layer (`useRestAPI`, `utils/apiRequest.ts`) into a third candidate.
- **Related**: #6197, #4300, #4693 (CLOSED)
- **Suggested Fix**: `git mv hooks/shared/useStandardizedAPI.ts hooks/shared/useCacheStats.ts`, update the three references and its test.

##### TD8-13: `ApiErrorHandler.parse` scrapes `"HTTP nnn:"` messages that no production thrower emits without a `.status`
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/frontend/src/types/api.ts:44-55`
- **Status**: NEW
- **Age**: #2361-era
- **Effort**: trivial
- **Description**: The fallback regex `^HTTP (\d{3}):` exists "for any thrower that uses neither" `.status` nor `.statusCode`. The one production thrower of that message, `utils/httpError.ts:134`, always attaches `status` via `Object.assign`; `APIRequestError` carries `statusCode`. Only tests construct bare `new Error('HTTP 503: ...')` (`types/__tests__/apiErrorHandler.test.ts:49`, `useQueueMutations.*.test.ts`, `usePlayTrack.test.ts:62`).
- **Impact**: Message-text parsing is what #4467 fixed elsewhere; keeping it invites new throwers to rely on it.
- **Related**: #4467, #4831 (CLOSED)
- **Suggested Fix**: Delete the regex branch (default to 500) and change the tests to throw `httpErrorFromResponse`-shaped errors.

##### TD8-14: `ServiceError(ValueError)` "while call sites migrate" - the migration never happened
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/services/errors.py:9-10,19`; handlers in `auralis-web/backend/routers/player_queue.py:42-169` (10 sites), `player_playback.py:62,175,207,230,239`, `metadata_tracks.py:238`, `processing_jobs.py:87`; `routers/errors.py:110-111`
- **Status**: NEW
- **Age**: #4700 (2026-07)
- **Effort**: small
- **Description**: The typed service errors subclass `ValueError` "so pre-existing `except ValueError` handlers and tests keep working while call sites migrate". Every handler still catches `ValueError` and then calls `raise_for_service_error`, whose final branch is "Untyped ValueError - historical behaviour was 400". No `raise ValueError` remains under `services/`, so the untyped default only absorbs engine-raised `ValueError`s.
- **Impact**: The type-based mapping is defeated in the same breath: any unrelated `ValueError` from the engine is also treated as a 400 service failure.
- **Related**: #4700 (CLOSED)
- **Suggested Fix**: Make `ServiceError(Exception)`, catch `ServiceError` in the 16 handlers, keep a narrow explicit `except ValueError` only where the engine's own `ValueError` is deliberately a 400 (`set_volume`, #5268).

##### TD8-15: `LibraryScanner.scan_single_directory` / `scan_folder` have no production caller (closed #4973 kept them)
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/library/scanner/scanner.py:262-285`, `auralis/library/scanner/scan_stages.py:268-282` (`preview_folder`, "Convert AudioFileInfo to dict for backward compatibility")
- **Status**: Existing, CLOSED #4973 (resolved by documenting "kept as a documented convenience method"); debt still present
- **Age**: -
- **Effort**: small
- **Description**: `scan_single_directory` is used only by `tests/performance/test_realworld_scenarios_performance.py:66,104`; `scan_folder` only by `tests/backend/test_file_format_support.py:296,315` and delegates to `preview_folder`, whose result dict exists "for backward compatibility" with a caller that is the test. Both ship `**kwargs` that are dropped (TD8-05).
- **Impact**: Two public methods and a ~30-line helper maintained for tests.
- **Related**: #4973 (CLOSED)
- **Suggested Fix**: Delete both methods and `preview_folder`; point the three tests at `scan_directories([dir])` and `file_discovery.discover_audio_files`.

##### TD8-16: Self-justifying "backward compatibility" comments that describe no compatibility
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: see Evidence
- **Status**: NEW
- **Effort**: trivial
- **Description**: Docstrings invoke compatibility with callers that do not exist (desktop-only, no external consumers) and misdirect readers.
- **Evidence**:
  - `components/track/TrackCard.tsx:30` / `components/album/AlbumCard/AlbumCard.tsx:52` "Provides backwards compatibility for existing track/album grid views" (they are the live thin `MediaCard` wrappers, used by `TrackGridView` / three album grids).
  - `auralis/player/enhanced_audio_player.py:14` "Uses Facade pattern to maintain backward-compatible API."
  - `auralis/core/mastering_config.py:13` "single flat, backward-compatible attribute namespace"
  - `auralis/library/repositories/fingerprint_upsert_mixin.py:167` "float values for backward compatibility" (the float columns are the live data every reader uses; only the quantized blob is the add-on).
  - `auralis/core/processing/continuous_quality.py:41` "Sampling still uses the legacy config names for compatibility" (they are the only config names).
  - `auralis-web/backend/core/processor_cache_key.py:23` "stays backward-compatible for callers that already use the named fields".
  - `auralis-web/backend/core/chunked_processor.py:198,234` `duration` "alias ... for AudioStreamController compatibility" and `_get_wav_chunk_path` "Alias of `_get_chunk_path`" (production calls only the alias, `chunk_streaming.py:178`; `_get_chunk_path` is only the alias's target and test mocks).
  - `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:78` "kept for API compat" (see TD8-08).
- **Suggested Fix**: Reword to the present-tense purpose or delete; collapse `_get_wav_chunk_path`/`_get_chunk_path` into one name.

#### Dimension 9: File / Function / Module Complexity

##### TD9-01: `seekable_source.py` is 411 lines — three responsibilities in one module
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/core/seekable_source.py` (411 LOC; 63-line docstring)
- **Status**: NEW (no issue; not in `loc-ceilings.json`)
- **Age**: created 2026-07-30 (`e17a2d63e`); crossed 300 via `88101358f` (#6166) and `57272571c` (#5734/#6166), both 2026-11-17
- **Effort**: medium
- **Description**: The file holds (a) the capability probe: `_ffprobe_duration`, `_length_agrees_with_ffmpeg`, `can_seek_natively` (L81-126); (b) the one-shot conversion machinery: `_require_free_space`, `convert_to_temp_wav`, `_Conversion`, `_remove_temp_dirs`, `ConvertedWavRegistry` (92 lines), `_release_late_acquire`, `acquire_conversion` (L129-322); (c) the `SeekableSource` context manager (83 lines). Each recent safety fix (#6166 disk-space check, #5734) went into the same file.
- **Evidence**: `wc -l` 411; outline from AST shows 3 clusters with no cross-cluster state except `acquire_conversion`.
- **Impact**: Largest oversized shipped file; every disk-space/lifecycle fix lands here and pushes it further.
- **Siblings**: TD9-04 (`streamlined_processor_cache.py`, same lease/registry shape), `core/chunk_file_loading.py`.
- **Related**: none (no bug).
- **Suggested Fix**: Split by responsibility: `seekable_probe.py` (probe + tolerance constants), `converted_wav_registry.py` (convert + registry + acquire/release, ~200 LOC), keep `seekable_source.py` for `SeekableSource` + `SeekableSourceClosed` (~110 LOC with the docstring). Update importers and `patch()` targets; enrol all three in `loc-ceilings.json` at measured size. **Acceptance: close only when `seekable_source.py` and both new files are verified <300 LOC; otherwise re-scope and keep open (#4673).**

##### TD9-02: `fingerprint_storage.py` regrew to 337 lines one hour after #6273 brought it under 300
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py` (one 307-line class `FingerprintStorage`)
- **Status**: NEW (regression pattern of #6273/#5454; the file is not in `loc-ceilings.json`, so nothing held it)
- **Age**: `44574394b` 2026-11-17 14:12 "back under 300 lines by condensing two examples and two comments (#6273, part)" -> `4adc3c815` 2026-11-17 15:18 (#6004, +sweep_orphans/_is_dead/clear_all) put it at 337
- **Effort**: small
- **Description**: The earlier fix got under 300 by trimming comments, not by splitting; the next feature re-crossed it. The class mixes (a) key/dir derivation + `save` (72) + `load` (63) + `is_valid` and (b) lifecycle maintenance `delete`, `sweep_orphans`, `_is_dead`, `clear_all` (~85 lines).
- **Evidence**: `git log` of the file; method sizes from AST.
- **Impact**: Same file will cross again on the next cache-version change (it was touched by #5697, #6231, #5751, #6004 in 3 weeks).
- **Siblings**: `config/startup/fingerprint_store.py` (calls the sweep), `core/cache_cleanup.py` (calls `clear_all`).
- **Related**: TD9-11.
- **Suggested Fix**: Move the maintenance half (`delete`, `sweep_orphans`, `_is_dead`, `clear_all`) to `fingerprint_store_maintenance.py` (module functions taking the cache dir, or a `FingerprintStorageMaintenance` mixin) and keep read/write/validity in `fingerprint_storage.py` (~230 LOC). Enrol both in the ratchet. Acceptance: both files <300 LOC verified before close.

##### TD9-03: `websocket_security.py` is 327 lines — rate limiter and message validation are separate jobs
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/websocket/websocket_security.py`
- **Status**: NEW
- **Age**: created 2026-02-21 (`8a8bd5a4c`); last grown in `fdef5d97d` (2026-11-17)
- **Effort**: small
- **Description**: `WebSocketRateLimiter` (144 lines, L63-206, with `_client_ip`, `check_rate_limit` 57 lines, cleanup) sits next to frame-level validation: `_json_nesting_exceeds`, `validate_and_parse_message` (60), `receive_text_frame`, `send_error_response`. The two halves share only `logger` and constants.
- **Evidence**: AST outline; the module docstring already lists "Rate limiting and validation utilities" as two things.
- **Impact**: Unrelated changes (connection cap #6171, rate-limit tweaks, frame validation) all grow one file.
- **Siblings**: TD9-05 (`config/globals.py` holds the `ConnectionManager` for the same sockets).
- **Related**: none.
- **Suggested Fix**: `websocket/rate_limiter.py` (limiter + `_client_ip`, ~150) and `websocket/message_validation.py` (`MAX_JSON_DEPTH`, nesting check, parse, receive, error send, ~180). Update the importers (`routers/system.py`, tests' patch targets); no shim. Enrol both in ceilings.

##### TD9-04: `streamlined_processor_cache.py` is 309 lines — lease/eviction lifecycle plus the build path
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/core/streamlined_processor_cache.py` (`get_or_build_processor` 82 lines; `remember_processor`, `prune_processors_for_track`, `discard_timed_out_processor` 33-37 each)
- **Status**: NEW (the parent `streamlined_worker.py` is a closed split target #5037 and is ratcheted at 243; this extraction was not enrolled)
- **Age**: created 2026-08-16 (`b749b99a9`, #5037); crossed 300 in `b0002733b` (#5064, 2026-11-17)
- **Effort**: small
- **Description**: Free functions take `worker: Any` and reach into its private dicts (`_processor_cache`, `_processor_build_locks`, `_build_waiters`) — it is a mixin written as functions. They cluster into (a) lease/close: `leased`, `_close_now`, `close_dropped_processor`, `discard_timed_out_processor` (~80 lines); (b) cache bookkeeping: `remember_processor`, `prune_processors_for_track`; (c) the build path `get_or_build_processor`.
- **Evidence**: AST outline; `worker: Any` signature on all three public entry points.
- **Impact**: #5064's fix pushed the file over the line; the duck-typed `worker` makes every further fix cross-file.
- **Siblings**: TD9-01 (same lease/registry pattern), `core/processor_factory.py` (ratcheted at 222, #5833, already split into cache key/registry/maintenance).
- **Related**: none.
- **Suggested Fix**: Move the lease/close group to `processor_lease.py` (~100 LOC). Longer term replace `worker: Any` with a small Protocol. Enrol at measured size.

##### TD9-05: `config/globals.py` is 308 lines and is mostly `ConnectionManager`, not "global state"
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/config/globals.py` — `ConnectionManager` L91-270 (180 lines), `WebSocketOriginRejected`, `build_ws_origins`, plus the 25-line component registry (L289-308)
- **Status**: NEW
- **Age**: crossed 300 in `f75423015` (#6171 connection cap, 2026-11-17)
- **Effort**: small
- **Description**: The module docstring says "Global State Management ... and shared utilities like ConnectionManager", but 85% of the file is the WebSocket connection manager and its origin allowlist. Importers: `main.py` (`ConnectionManager`, `set_component_registry`), `routers/system.py` (`WebSocketOriginRejected`), `core/chunk_fingerprint_registry.py` (`get_component_registry`).
- **Evidence**: only 3 import sites in production code (grep).
- **Impact**: The file name hides the largest class; #4714 and #5066 both had to hunt for it.
- **Siblings**: TD9-03 (WebSocket security next door).
- **Related**: none.
- **Suggested Fix**: Move `ConnectionManager`, `WebSocketOriginRejected`, `build_ws_origins` and the origin constants to `websocket/connection_manager.py` (~250 LOC); leave `config/globals.py` as the ~40-line component registry (or rename to `component_registry.py`). Update the 3 importers.

##### TD9-06: `executors.py` is 306 lines — one pool pattern hand-copied four times
- **Severity**: LOW
- **Dimension**: File/Function Complexity (with duplication overlap — see Siblings)
- **Location**: `auralis-web/backend/core/executors.py`
- **Status**: NEW
- **Age**: created 2026-08-13 (`4d1d6434a`); 3rd/4th pools added by #5335 and `a4f899592` (#6093, 2026-10-26)
- **Effort**: small
- **Description**: Four pools (stream, IO, job, transport) each carry a module global, a `*_POOL_SIZE` constant, a `get_*_executor()`, a `run_in_*_executor()`, a construction block in `install_executors` (45 lines) and a teardown tuple + reset in `shutdown_executors` (53 lines). `install_executors` also has a four-way `is not None` idempotency check. Adding a pool today means touching 7 places, which is why the file keeps growing one pool at a time.
- **Evidence**: `install_executors` L207-251, `shutdown_executors` L254-306, `_run_in` L164-179.
- **Impact**: Next pool = another 25 lines; the "install/shutdown names must agree" invariant is hand-maintained.
- **Siblings**: Dim 3 candidate (logic duplication); `core/stream_*` callers.
- **Related**: none.
- **Suggested Fix**: A small `_Pool(name, prefix, size)` dataclass with `.get()`, `.run()`, `.start()`, `.stop()`, held in a `{name: _Pool}` table; keep the four public `get_*`/`run_in_*` functions as thin one-liners over the table (so no caller changes). Net file ~200 LOC.

##### TD9-07: `analysis/fingerprint_queue.py` crossed back over 300 (304) — a closed split target missing from the ratchet
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/analysis/fingerprint_queue.py` — `FingerprintQueue` is 237 lines, `_worker_loop` 56, `enqueue` 37
- **Status**: NEW (closed split target of #5039 at 517 lines; never enrolled in `loc-ceilings.json`)
- **Age**: `262e775b5` / `213a3165b` / `b8863c836` (#5920, #5919, #5390), all 2026-10-28
- **Effort**: small
- **Description**: Three consecutive correctness fixes each added a few lines to the single remaining class. The 56-line `_worker_loop` interleaves dequeue-under-lock, filepath lookup, generation and cancel/error bookkeeping.
- **Evidence**: `git log`; #5039 closed 2026-08-07.
- **Impact**: Will keep growing with each fix; also the two-queues arrangement (`auralis/services/fingerprint_queue.py` 296 lines, a different class `FingerprintExtractionQueue`) means the state-lock/dequeue logic cannot be shared.
- **Siblings**: `auralis/services/fingerprint_queue.py` (296 LOC, unlisted, same family).
- **Related**: TD9-11.
- **Suggested Fix**: Extract the dedup/state bookkeeping (`enqueue`, `enqueue_many`, `is_pending`, `get_stats`, `_pop_next`) into a `FingerprintQueueState`-owned method set (the dataclass already exists at L34, 8 lines) so `_worker_loop` shrinks to ~30 lines, and move the state class + bookkeeping to `fingerprint_queue_state.py`. Enrol in ratchet.

##### TD9-08: `wav_encoder.py` is 303 lines because it also owns chunk-cache deletion
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/core/encoding/wav_encoder.py` — `delete_chunk_files` (51 lines, L253-303) is used only by `core/cache_cleanup.py` and `cache/clearing_mixin.py`
- **Status**: NEW (the module came out of #4250's extraction; not in the ratchet)
- **Age**: file touched last 2026-10-26 (`793a186f7`)
- **Effort**: trivial
- **Description**: An encoder module exports a cache-sweeping function whose only callers are cleanup modules; it also needs `is_partial_path` from the same package.
- **Evidence**: `grep delete_chunk_files` -> `core/cache_cleanup.py:12,54,91`, `cache/clearing_mixin.py:18`, plus tests.
- **Impact**: Wrong cohesion; the file sits at 303 for 51 lines that are not encoding.
- **Siblings**: none.
- **Related**: none.
- **Suggested Fix**: Move `delete_chunk_files` into `core/cache_cleanup.py` (105 -> ~155 LOC) or a new `core/chunk_file_cleanup.py`; `wav_encoder.py` drops to ~250.

##### TD9-09: `mastering_presets.py` is 301 lines — one dataclass holding six unrelated stage tables
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis/core/mastering_presets.py` (`MasteringPresetDefaults`, 275 lines; sections: Resonance Notcher L37, Transient Shaper L85, Clarity Boost L124, Vocal Unmasking L152, Sub-Bass L201, Continuous loudness/crest L244, Progress Reporting L297)
- **Status**: NEW (this file was itself produced by the #4511 split of `mastering_config.py` and sits 1 line over)
- **Age**: created 2026-08-22 (`a62dfa226`), last grown 2026-11-17 (`364525e69`)
- **Effort**: small
- **Description**: Pure tuning constants with long rationale comments, so line count is legitimate, but the six groups are independent. "Progress Reporting" is not even a preset.
- **Evidence**: section headers. `SimpleMasteringConfig` inherits the class, so groups can become sibling dataclass mixins without changing attribute names.
- **Impact**: Low — near the limit, grows by a comment at a time.
- **Siblings**: `auralis/core/mastering_config.py` (279, unlisted).
- **Related**: none.
- **Suggested Fix**: Split along the stage axis into `NotcherDefaults`/`TransientDefaults`/`ClarityDefaults` (notcher + transient + clarity + unmask) and `LowEndDefaults`/`LoudnessResponseDefaults` (sub-bass + continuous response), each a `@dataclass` that `SimpleMasteringConfig` inherits (flat attributes preserved). Move "Progress Reporting" into `mastering_config.py`.

##### TD9-10: `CozyLibraryView.tsx` is 335 lines and its ratchet ceiling was set to 335, above the 300 rule
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx` (the component alone is 263 lines, L69-331); `loc-ceilings.json` entry 335
- **Status**: NEW (closed split issues #4456 and #5840 both claimed it; #6267 then enrolled it at 335 as a "not-yet-split offender", but no open issue exists for that split)
- **Age**: `073fade9d` (2026-08-22, #4456 split) -> regrown by #5866/#6010/#6011/#6014 (2026-10-24..28)
- **Effort**: small
- **Description**: Only shipped TS file over 300. The component runs 11 hooks: debounce state + effect (L82-87), `useLibraryWithStats`, a client-side `filteredTracks` memo, `useTrackSelection`, `useNavigationState`, `usePlaybackState`, `useMetadataEditing`, `useSimilarTracksModal`, `useBatchOperations`, a selection-reset effect, `useLibraryKeyboardShortcuts`, then render routing.
- **Evidence**: hook list from L82-201; 2 useState/useEffect + 1 useMemo inline.
- **Impact**: CLAUDE.md "components < 300 lines" is violated by the one component that every library view change touches.
- **Siblings**: TD9-14.
- **Related**: `grep -rn useDebounce` finds no shared debounce hook, so the inline timer is the only copy (not a duplication finding).
- **Suggested Fix**: Extract the data layer (L82-120: debounce, `useLibraryWithStats`, `filteredTracks`) into `useLibraryViewData(view, searchQuery, playlistId)` and the selection/clear-on-view-change/keyboard block (L122-205) into `useLibraryViewSelection`. Component drops to ~220 lines, file to ~230. Acceptance: file verified <300 LOC and ceiling lowered to the new size; the ceiling must not stay above 300.

##### TD9-11: Closed split targets are still missing from `loc-ceilings.json` (and one ceiling has slack)
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `/mnt/data/src/matchering/loc-ceilings.json` vs targets of #5039, #6269, #6270, #6271, #6272, #6273 (all closed)
- **Status**: NEW (#6266 and #6267 enrolled earlier sets; the splits closed 2026-10-22 and the 2026-11-17 regrowth show it again)
- **Age**: #6269-#6273 closed 2026-10-22
- **Effort**: trivial
- **Description**: The ratchet exists to hold closed split targets; these split targets named in issue titles are unlisted: `backend/services/playback_service.py` 295, `core/recording_type_detector.py` 299, `analysis/fingerprint/similarity.py` 275, `backend/core/stream_protocol.py` 290, `backend/core/audio_processing_pipeline.py` 245, `backend/services/artwork_downloader.py` 244, `backend/core/chunk_boundaries.py` 210, `core/analysis/target_generator.py` 148, `services/artwork_service.py` 137, plus `backend/core/stream_enhanced_chunks.py` 297, `services/fingerprint_queue.py` 296 and `ws_handlers/seek_command.py` 144. Already over 300 and unlisted: the nine files of this report (TD9-01..09) — #5039's `fingerprint_queue.py` (304) and #6270's `wav_encoder.py` (303) are exactly the "closed split target regrew" case. Two more sit at exactly 300 (`core/job_worker.py`, `config/limits.py`) and 12 more at 290-299 with no ceiling. Separately, `auralis/core/analysis/target_fingerprint_adjustments.py` is 144 lines against ceiling 145 (slack of 1; `--update` would lower it).
- **Evidence**: my script `d9_ceil.py` (diff of `loc-ceilings.json` vs working tree) and issue-body file-name extraction; `check_loc_ratchet.py --list` shows 148 entries.
- **Impact**: Per #5830's own history, an unlisted file regrows silently (TD9-02 did it in one hour).
- **Siblings**: TD9-02, TD9-07, TD9-10.
- **Related**: none.
- **Suggested Fix**: Run the `--update` flow to add every file of 250-300 LOC that came from a split issue at its measured size, and lower `target_fingerprint_adjustments.py` to 144. Add the files from TD9-01..09 in the same commits that split them. Optionally make `check_loc_ratchet.py` also fail on any unlisted non-test file >300 so it cannot be skipped again.
- **Merge note**: absorbs TD10-02 (`loc-ceilings.json` ceiling for `auralis/core/analysis/target_fingerprint_adjustments.py` is 145 but the file is 144 lines; lowered by the same `--update` run).

##### TD9-12: #6275 closed with seven hooks still above its own 120-line criterion
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `hooks/library/useLibraryPagination.ts` (202), `hooks/enhancement/useAudioStreamingCore.ts` (170), `hooks/enhancement/useEnhancementCommands.ts` (169), `hooks/websocket/useWebSocketConnection.ts` (169), `contexts/PlaybackSessionContext.tsx` `PlaybackSessionProvider` (158), `hooks/player/usePlayerStateSync.ts` (133), `hooks/enhancement/useStreamMessageHandlers.ts` (129) (all under `auralis-web/frontend/src/`)
- **Status**: Regression of #6275 (closed 2026-11-17; its acceptance criterion "No hook listed exceeds 120 lines in a single function" is not met; the closing comment acknowledges 202 lines remain and attributes about 70 of them to comments)
- **Age**: closed today; refactors landed in 10 `(#6275, part)` commits on 2026-11-17
- **Effort**: medium
- **Description**: The duplicated request-guard logic the issue was about is gone, but each hook is still one function. Measured with the TS compiler API: the 7 above. Three others (`useQueueMutations`, `useProgressBarInteraction`, `useLibraryQuery`) are now below 120.
- **Evidence**: `d9_ts_out2.txt` (LONG>100 section).
- **Impact**: Low; the risk is the closed-but-unmet criterion hiding the work from the next audit.
- **Siblings**: TD9-14 (hook-count view of the same files).
- **Related**: #5650 (open, request cancellation) touches `useLibraryPagination`.
- **Suggested Fix**: Re-scope rather than re-open if preferred: (1) `useLibraryPagination` — move the 7 `useState` into a `useReducer` in `libraryPageReducer.ts` (cuts ~40 lines); (2) `useAudioStreamingCore` — 13 refs -> one `useStreamingRefs()` bundle; (3) `useWebSocketConnection` — move reconnect scheduling to the lifecycle file; (4) `PlaybackSessionProvider` — extract context-value assembly (L242-278 era) to `usePlaybackSessionValue`; (5) `useEnhancementCommands`, `usePlayerStateSync`, `useStreamMessageHandlers` — one more pass or accept 130-170 with the criterion amended in the issue. Do not leave the closed criterion unmet without a stated amendment.

##### TD9-13: Non-JSX, non-hook functions over 100 lines in the frontend
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location** (under `auralis-web/frontend/src/`): `store/middleware/errorTrackingMiddleware.ts` `createErrorTrackingMiddleware` (161, whose inner `(next) => (action)` is ~130 lines), `store/middleware/loggerMiddleware.ts` `createLoggerMiddleware` (115), `utils/colorExtraction.ts` `extractArtworkColors` (131), `hooks/player/playerStateSnapshot.ts` `applyPlayerStateSnapshot` (105), `utils/serviceFactory.ts` `createCrudService` (132, a method table), `theme/themeComponents.ts` `createComponents` (275, declarative MUI overrides — leave)
- **Status**: NEW (#5841 closed measured file size; #6275 covered hooks only; #5481 is Python only)
- **Age**: n/a
- **Effort**: small for each
- **Description**: Logic that is not rendering and not a hook, yet runs as one function. `createErrorTrackingMiddleware` mixes action-shape guards, error detection, deferred forward with generation counter, console logging and recovery dispatch; `extractArtworkColors` mixes canvas sampling, quantisation and palette ranking.
- **Evidence**: `d9_ts_out2.txt`; depth is within 4 for all, so this is length only.
- **Impact**: Redux middleware sits on every dispatched action; changing one concern means re-reading all.
- **Siblings**: none.
- **Related**: none.
- **Suggested Fix**: `createErrorTrackingMiddleware` -> pure `extractActionShape(action)`, `detectError(shape, cfg)`, `forwardDeferred(store, gen, ...)` helpers in `errorTrackingHelpers.ts` (ratcheted file is 283 already); `extractArtworkColors` -> `sampleImagePixels`, `quantizeColors`, `rankPalette`; `applyPlayerStateSnapshot` -> one helper per slice (position, queue, enhancement). Skip `createComponents` and `createCrudService`.

##### TD9-14: Components and hooks doing several jobs (hook-count and effect-count census)
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location** (under `auralis-web/frontend/src/`): `components/player/QueuePanel/QueuePanelExpanded.tsx` (242 lines, 19 hook calls, 9 `useCallback`; three identical `try { await x() } catch { console.error }` wrappers, row-key memo); `ComfortableApp.tsx` (240 lines, 18 hooks, 5 `useState`: view/search/mode/settings/reset-token + volume getter + help-ref); `hooks/enhancement/usePlaybackTransport.ts` (**6 `useEffect`**: playback clock, engine pause/resume sync, resume-position getter, WS-disconnect handling); `components/library/Views/TrackListViewContent.tsx` (229 lines, 15 hooks, 4 `useEffect`, roving focus); `components/background/StarfieldBackground.tsx` (209 lines, 3 effects + 7 refs; GL lifecycle inline); `hooks/library/useLibraryQuery.ts` (**8 `useState`**) and `useLibraryPagination.ts` (7 `useState`); `components/settings/useSettingsDialog.ts` (6 `useState` + 10 `useCallback`); `hooks/enhancement/useAudioStreamingCore.ts` (13 `useRef`)
- **Status**: NEW (the thresholds I used: >=10 hook calls, >=5 `useState`, >=4 `useEffect` in one function)
- **Age**: n/a
- **Effort**: medium (each is small)
- **Description**: None of these breaks the 300-line rule except TD9-10, but each combines distinct jobs. 73 shipped TS functions exceed 100 lines; the 20+ JSX components over 150 lines are largely declarative and left alone.
- **Evidence**: `d9_ts_out2.txt` HOOKS section (name, length, useState/useEffect/useCallback/useMemo/useRef counts).
- **Impact**: Effect-order and dependency bugs (#3624, #4668, #5621 are all in `usePlaybackTransport`'s history) concentrate where several effects share one closure.
- **Siblings**: TD9-10, TD9-12.
- **Related**: `/audit-frontend` owns re-render and dependency-array correctness.
- **Suggested Fix**: `usePlaybackTransport` -> `usePlaybackClock`, `useEngineStateSync`, `useResumePositionRegistration` (one effect each); `useLibraryQuery`/`useLibraryPagination` -> `useReducer` state machine; `QueuePanelExpanded` -> `useQueueActions` (the three error-wrapped handlers) + `useQueueRowKeys`; `ComfortableApp` -> `useAppNavigation` (view, mode, reset token, sidebar handler); `StarfieldBackground` -> `useStarfieldGL`. Count of `useEffect` per function should go to <=3.

#### Dimension 10: Audit-Finding Rot

##### TD10-01: trace-flow.md boundary-crossing example names files that do not exist
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/trace-flow.md:76-79`
- **Status**: NEW (residue of CLOSED #5846, which re-pointed the same skill's layers but left this table)
- **Age**: not determined
- **Effort**: trivial
- **Description**: The "Boundary Crossing Table" example rows cite `hook.ts::usePlayTrack`, `router.py::set_queue` and `queue_controller.py::get_queue` as if they were symbol anchors. `hook.ts` and `router.py` are not files in the repo. The real anchors are `auralis-web/frontend/src/hooks/player/usePlayTrack.ts::usePlayTrack`, `auralis-web/backend/routers/player_queue.py::set_queue` (registered at `/api/player/queue` in `routers/player.py`) and `auralis/player/queue_controller.py::get_queue`. The gate does not catch it because the table sits in a fenced block and the bare names do not look like repo paths. An agent following the template copies placeholder names into a real trace.
- **Evidence**: `ls auralis-web/backend/routers/router.py` -> no such file; `grep -n "def set_queue" auralis-web/backend/routers/player_queue.py` -> line 47.
- **Impact**: A trace-flow run can emit unresolvable `file::symbol` anchors, which is exactly the rot the `path::Symbol` convention in `_audit-validate.sh` exists to prevent.
- **Siblings**: none. Every other `path::Symbol` anchor in `.claude/` and CLAUDE.md resolves (checked 8 distinct tokens; the other two non-resolving tokens are the deliberate `some_module.py::function_name` and `tests/path.py::test_name` placeholders).
- **Related**: #5846 (CLOSED); Dim 7.
- **Suggested Fix**: Replace the four example rows with the real anchors above (full repo-relative paths), so the example is itself a valid reference.

##### TD10-03: Four reports past the 90-day mark carry HIGH/CRITICAL findings with no triage record
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `docs/audits/AUDIT_CONCURRENCY_2026-08-13.md`, `docs/audits/AUDIT_INTEGRATION_2026-08-13.md`, `docs/audits/AUDIT_SECURITY_2026-08-13.md`, `docs/audits/AUDIT_RECOVERY_2026-07-24.md`
- **Status**: NEW
- **Age**: reports dated 2026-07-24 and 2026-08-13 (96-116 days old; the 90-day cutoff is 2026-08-19)
- **Effort**: small
- **Description**: I checked every CRITICAL/HIGH finding in all 37 reports dated before 2026-08-19 (134 severity-tagged blocks; ~100 are real findings, the rest are section headers). About 90 map 1:1 by title to a GitHub issue, all CLOSED except #4905 (OPEN, Electron unsigned auto-update, filed from AUDIT_SECURITY_2026-07-29, so it is triaged). The four reports above end with "No GitHub issues were created" and have no finding-to-issue ledger. Eight of their HIGH/CRITICAL findings have no same-titled issue: CONCURRENCY C3-1 (`drain_cancelled_task` re-raise skips semaphore release), C3-2, C1-1; INTEGRATION INT-02, INT-03, INT-04; SECURITY SEC-01; RECOVERY REC-01 and REC-03. I traced each to a differently titled CLOSED issue or fixing commit, so none looks untriaged in substance: C3-2 -> #5253 (`618e2b161`); C3-1 -> #6092 (`769623a34`, teardown helpers no longer swallow cancellation; weaker match); C1-1 -> #5581 / #5726; INT-02 -> #5934; INT-03 -> #5860 (`e562e0d1a`); INT-04 -> #5861 / #5867; SEC-01 -> Starlette is now pinned (`starlette==1.3.1` in `requirements.txt`, `pyproject.toml`, `auralis-web/backend/requirements.txt`; #4871 CLOSED); REC-01 -> #4805 / #5373 / #5447; REC-03 -> #5550 / #4928. These mappings are inferred from titles and commits, not recorded anywhere, so a future auditor cannot confirm triage without redoing this exercise. REC-01's `dev.js` path-construction failure was not re-verified.
- **Evidence**: `grep -n "No GitHub issues" docs/audits/AUDIT_CONCURRENCY_2026-08-13.md` (line 514 in INTEGRATION, 785 in SECURITY); the issue lookups above came from `issues.json`.
- **Impact**: Stale reports are the baseline the next audit dedups against; an unrecorded triage state is how "11 closed issues were never actually fixed" (2026-07-25 comprehensive audit) happens. Risk is low because every finding I could trace is closed.
- **Siblings**: the other pre-08-19 reports that did publish (e.g. AUDIT_BACKEND_2026-07-25, AUDIT_ENGINE_2026-07-29) have titles that map directly to issues #4552-#4581, #4852-#4881, #5103-#5105, #5240-#5260.
- **Related**: `/audit-publish` is the owner of finding-to-issue mapping.
- **Suggested Fix**: Append a short "Triage ledger" (finding ID -> issue number or fixing commit) to each of the four reports, or move the pre-2026-08-19 reports whose findings are all closed into an `archive/` subdirectory so the dedup scan stops reading them as live baselines. Verify the weaker C3-1 and REC-01 mappings first.

## Deferred

- **TD8-06** (crossfade / gapless / replay-gain settings with a UI, DB column and API field but no consumer): needs a product call, delete or implement, before any code change.
- **TD5-01 / TD5-02**: gated on the same decision about whether EQ/dynamics/level-matching wiring for the processing-job API is wanted (open #5098 tracks the wire-up).
- **TD7-19** (120 baselined stale refs in 35 historical docs): the intended fix is archiving, which is gated on a docs-tree decision; the ratchet holds it meanwhile.
- **TD6-09** (Rust module not built in backend CI): severity inferred from static reading; verify against a CI artifact first (workflow edit is out of audit scope).
- Open-issue overlaps skipped: #5484, #6180, #5098 (Dim 1); #5628, #5959, #5922 (Dim 2); #5076, #6119, #5700 (Dim 3); #5481 (Dim 9, function-length census; the 50-function table with split axes is in the appendix).

## Appendix: per-dimension skipped (existing issues) and checked-clean notes

### Dimension 1: Stale Markers

#### Skipped: existing open issues

- **#5484** (OPEN) — `TODO(#5484)` in `security_headers.py:124`. The only genuine marker; cites an OPEN issue with a matching title. Healthy.
- **#6180** (OPEN, LOW, 2026-10-22: "FFmpeg version floor is 4.0 (2018) and only warns; no FFmpeg is bundled for Windows/macOS") — `auralis/io/loaders/ffmpeg_probe.py:23-34` calls the version floor + warning "the interim mitigation until (or instead of) bundling" and cites a non-issue id ("tracked alongside SEC-M2") for the bundling decision. The debt is tracked by #6180; only the comment's pointer is off. Cleanup (trivial): replace "tracked alongside SEC-M2 ... interim" with `TODO(#6180):` so the census sees it. Age: comment from `98ac7615b` (2026-07-18, #4344), moved in `0d2efc303` (2026-10-22).
- **#5098** (OPEN) — the wire-up work behind TD1-02; the finding is only the mis-cited pointer.

#### Checked and clean

- `TODO|FIXME|HACK|XXX` (case-insensitive, all source languages) across `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/src/`: exactly 1 genuine marker (OPEN #5484), rest false positives.
- Same sweep over `tests/` (`*.py`): 0 genuine markers; no marker citing a closed issue (the #5143 problem is not present).
- Same sweep over `scripts/`, `desktop/`, `.github/`, `auralis-web/frontend/scripts/`, `tools/`, root `*.py`/`*.js`: 0 markers.
- Rust: no `todo!()` / `unimplemented!()` / marker comments in `vendor/auralis-dsp/src/`.
- Markers in code paths reachable from shipped routes or the player pipeline (`routers/`, `auralis/player/`): none besides the CSP note (a header-policy deferral, not an unimplemented path).
- `HACK`/`XXX` around DSP math (`auralis/dsp/`, `auralis/core/`): none.
- Baseline "prose deferrals" grep (11 hits): 1 genuine (TD1-01); rest are ordinary English (umask, 503 text, 501 status, "never revisits", "Settled decision, not a pending revisit" in `useAlbumFingerprint.ts`).
- Wider phrasing sweep (interim, eventually, placeholder, stopgap, deferred, known limitation, out of scope, in the meantime, left as-is, "future PR/refactor", "once ... lands", "until ... wired", follow-up, TBD) in src: remaining hits are accurate historical/rationale notes citing real issues, not live deferrals. Notable ones reviewed and judged not findings: `hybrid_mode.py:84` (deliberate "do not wire this without a mastering-quality decision", cites #6258; a guard against change, not a pending task); `chunk_content_profile.py:32/51` and `security_headers.py:41` ("Known limitation" blocks that cite closed #4601 / #4526 but describe a documented, accepted behaviour with rationale, not pending work); `schemas/websocket.py:28` (rename "deferred to avoid churn", documented decision, cites #3551); `processing_parameters.py:28` (`_DEFAULT_PARAMETERS` "placeholder values" is a real default payload flagged `is_default: True`); `routers/similarity_deps.py:16` (a placeholder getter that raises a 503, functional by design).
- Comments mentioning "#2403 reload/stop follow-up" (`queue_manager.py:124`, `queue_edit_mixin.py:215`): the follow-up (stop/reload of the removed current track) is implemented right there (`was_current` branch); historical provenance, not a deferral.
- Frontend specs / `__tests__` prose deferrals: no hits beyond completed "follow-up" provenance.

### Dimension 2: Dead Code & Unused Surface

#### Skipped: existing open issues

- Frontend orphan files: my import-graph count (33 files, 2,921 lines unreachable from `index.tsx`: `SearchBar` x3 variants, `GlobalSearch` / `Search/*`, `ConnectionStatusIndicator`, `ConnectionDetailsPanel`, `ProcessingToast`, `TrackCard*`, `useAPIHealthPoll`, `useAutoHide`, `Styles/Container|Icon|Spinner|EmptyState|SearchStyles`, ...) matches **Existing: #5628** ("33 orphaned component files", filed against ~3,800 lines on 2026-10-16). The file count is unchanged, so nothing has been deleted since. `useAPIHealthPoll` ties to **Existing: #5615**.
- `StreamlinedCacheManager.update_position()` (zero production callers since `29c5816ec`/#5908, whose message says "retiring them is #5495's scope" — but #5495 is closed) and the `StreamlinedCacheWorker` / `core/streamlined_tiers.py` / `get_playback_snapshot` chain behind it: **Existing: #5959** (the worker never does any work). Note for that issue: #5908's note makes the cause the removed feed, and `core/streamlined_*.py` + `cache/playback_mixin.py` (~900 lines) are the dead cluster to retire.
- `SimilarityGraphRepository.add_edges` and the K-NN path: **Existing: #5922**.

#### Checked and clean

- Stale `# type: ignore` (Python): `mypy auralis/ auralis-web/backend/ --warn-unused-ignores` (also set in `pyproject.toml`) reports zero unused ignores; 20 unrelated errors (strict typing gaps, one `redundant-cast` at `auralis/dsp/dynamics/lookahead_buffer.py:78`, one `msvcrt` platform attr) — out of scope.
- Frontend `@ts-ignore` / `@ts-expect-error`: only two, both in `src/test/setup.ts` (legitimate); `any`-suppression debt belongs to Dim 8.
- Rust `vendor/auralis-dsp`: `cargo machete` finds no unused dependencies (`ndarray`/`rayon` used by `chroma.rs`, `numpy` by `rhythm.rs` + bindings); `lib.rs` has no `pub use` block (the #6206 deletion held); zero `#[allow(dead_code)]`; every `pub fn` has a caller in the crate except `to_dict` (TD2-13).
- `if TYPE_CHECKING` imports, pytest fixtures, FastAPI-decorated handlers (`config/app.py` exception handlers, `dispatch` methods, pydantic validators, `scanner_watchdog` callbacks, SQLAlchemy event listeners `set_sqlite_pragma` / `_set_pragmas` / `_register_casefold`): vulture 60%-confidence hits excluded as false positives.
- Intentional test-introspection / documented-kept APIs not flagged: `core/executors.py` getters, `scanner.scan_folder`, `_reset_registry_miss_warning`, `RecordingTypeDetector` (offline scripts, CLAUDE.md), `FingerprintCatalog` / `profile_audio` / `near_identity_violations` (used by `scripts/`), `desktop/resources/auralis` (gitignored build copy; its F841 not counted).
- `schemas/websocket.py` enum members (`PONG`, `HEARTBEAT`, ...): used as a validation registry, not dead.
- `config/startup/__init__.py` and `config/middleware/__init__.py` re-exports: used in the module bodies.
- `auralis.cli.fetch_artwork`, `auralis/version.py`: entry points / dynamic loaders.
- Retired architecture (LibraryManager, parallel processor, categorical branches, preset names, boundary crossfade): not re-reported.

Summary: 14 findings: 0 HIGH, 0 MEDIUM, 14 LOW (plus 3 existing-issue overlaps skipped: #5628, #5959, #5922).

### Dimension 3: Logic Duplication

#### Skipped: existing open issues

- #5076 (OPEN) — `handle_play_normal` never records `active_stream_settings`: cited as Related to TD3-12, not re-reported.
- #6119 (OPEN) — stereo "width" scales mixed in three places: the width-scale duplication in `dsp/utils/stereo.py` / `stage_snapshot.py` is that issue's scope; not re-reported.
- #5700 (OPEN) — per-chunk loudness normalization mixes RMS-proxy and K-weighted loudness: the `_normalize_chunk_loudness` path in `continuous_dsp_ops.py` is that issue's scope, not duplication.

#### Checked and clean

- DSP copy-before-modify / bypass-copy parity: all 12 `auralis/core/stages/*.py` bypasses route through `stages.no_op()` (copy) or return `audio.copy()` (`safety_limiter`); `ParallelEQUtilities._parallel_add` is the single shared tail for the three shelf/bandpass boosts; `peak_management.py` copies on both bypasses; `amplify()` copies; `lowmid_transient_enhancer`, `soft_clipper`, `brick_wall_limiter` preserve shape. No copy-drop or sample-count-guard-drop found, so no HIGH.
- Sample-count guards: `mode_dispatch.py` x2, `hybrid_stage_dispatch.py`, `mastering_chunk_loop.py:203`, `backend/core/audio_processing_pipeline.py:142` are all present (parity checked, only the exception type differs); the realtime chain (`player/realtime/processor.py`) copies up front (`processed = audio.copy()`) and its sub-stages' passthrough returns are only reachable from inside that chain.
- Zero-phase band extraction: `sosfiltfilt_safe` is the only caller of scipy `sosfiltfilt` besides `continuous_guards.py:105`, which gates on `is_long_enough_for_sosfiltfilt` itself.
- Stereo width: `adjust_stereo_width_multiband` is shared by `stereo_expansion` stage, `StereoWidthProcessor.apply_stereo_width_safe` (adaptive and continuous modes), no second implementation.
- Envelope follower recursion: single `_follow_envelope` kernel (#5792 closed); `core/dsp/transient_shaper._onepole` is a different filter form.
- Repository `session open -> query -> map` scaffolding: `_session_scope`, `_guarded`, `_first_detached`, `_all_detached`, `correlated_count/sum`, `sort_terms`, `escape_like` exist and the get-one sites use them; residue is TD3-09/10 only.
- Router validation/error shaping: `with_error_handling` (99 uses), `errors.py`, `raise_for_service_error`, `pagination.compute_has_more/limit_query/offset_query`, `RepositoryFactoryDeps` are in place; no inline 404/500 `HTTPException` copies beyond five domain-specific 500s. Residue is TD3-11.
- `streamlined_*` / `chunk_*` / `job_*` / `processor_*` families: lease/registry/pool split mixins read as one-responsibility (`processor_lease.py` vs `chunk_processor_lease.py` are factory-side vs stream-side halves, not copies); `chunk_boundaries.py` is the sole chunk-geometry owner; cache tiers share `file_signature`.
- Router-level `AbortController` use in `hooks/`: `useSupersedingAbort` and `useLatestRequestGuard` are consumed by the three hooks that needed them; TD3-17 covers only the verbatim detail-hook trio.
- WebSocket subscription lifecycle: `useMessageSubscriptions` is the shared path for all but the two hooks in TD3-20.
- Frontend time formatters: `utils/timeFormat.ts` is the single home after #5787 (`formatSecondToTime` in `usePlayerDisplay.ts:185` is a test-only wrapper, a Dim 2 matter).
- Offline `LowMidTransientEnhancer` (realtime) vs `TransientShaper` (offline stage): different algorithms (peak-window expander vs fast/slow envelope differential); not reported as duplicates.

Summary: 0 HIGH, 2 MEDIUM, 18 LOW (20 findings).

### Dimension 4: Magic Numbers & Hardcoded Constants

#### Skipped: existing open issues

None of the findings above matches an OPEN issue (jq over `issues.json` titles for constant|literal|hard-code|duplicate|mirror|timeout|magic|threshold|ceiling|limiter|debounce|sample rate|8765|retention returns only OPEN #6171, a WebSocket-limits security item with no overlap). Closed predecessors (#4622, #5796, #6170, #6217, #5800, #6226, #6232, #6233, #6229, #6228, #6222, #4024/#4025/#4289) were checked: their fixes are present and the findings here are the residue each one explicitly left, or siblings it never listed. No regression of a closed fix was found (the chunk-constant, pagination-limit, shutdown-budget and FFT-size fixes all still hold).

#### Checked and clean

- Chunk geometry literals (backend `core/`, `cache/`, `services/`, `routers/`, `websocket/`; engine; frontend): every `15`/`10`/`5`/`ceil(` site was traced; all consumers import `CHUNK_DURATION`/`CHUNK_INTERVAL`/`OVERLAP_DURATION`/`CONTEXT_DURATION` from `chunk_boundaries.py`; `cache/playback_mixin.py` and `chunk_boundary_manager.py` delegate to `content_chunk_count()`. Only the normal-path exception (TD4-04) and mirrors (TD4-01) remain.
- `auralis-web/backend/config/limits.py`, `env_config.get_int_env`: upload budgets, rate limits, WS limits, heartbeat, shutdown budgets, scan timeouts all named and env-tunable.
- `core/audio_stream_controller.py` / `stream_gates.py` / `stream_chunk_ops.py` / `stream_normal_reads.py`: `CHUNK_PROCESS_TIMEOUT`, `PROCESSOR_INIT_TIMEOUT`, `STREAM_ACQUIRE_TIMEOUT_SECONDS`, `FLOW_GATE_TIMEOUT_S`, `_SEND_QUEUE_MAXSIZE` are named module constants and every call site reads the constant (verified by grep and by tests that monkeypatch it).
- `cache/models.py` tier sizes (`TIER1/2_MAX_*`), `chunk_disk_prune.MAX_CHUNK_DISK_BYTES`, `thumbnail_cache`, `RECOMMENDATION_TTL_S`, `fingerprint_queue.MAX_QUEUE_SIZE`: named; sizes derived from `CHUNK_DURATION`.
- `routers/pagination.py` (`limit_query`/`PaginationParams`), `schemas/request_bounds.py`: bounds centralised; only `processing_jobs.py:131`, `similarity_*` Query ranges are endpoint-specific and acceptable.
- Engine FFT/hop/window sizes: only `quality_metrics.py:68` (`fft_size=8192`) and `ml/feature_extractor.py:41` (`FFT_SIZE=4096`, documented as its own contract in `dsp/constants.py`) remain; `DEFAULT_FFT_SIZE` and `ANALYSIS_*_S` are shared; no librosa call carries a bare n_fft/hop.
- Rust DSP (`vendor/auralis-dsp/src`): all tunables are named `const`s (`N_FFT`, `HOP`, `HOP_LENGTH`, `MIN_BPM`, ...); only the two `512` hop values in `rhythm.rs`/`chroma.rs` are independently typed and are separate algorithms. Test-module `44100`s ignored.
- Loudness targets: `DEFAULT_TARGET_LUFS`/`STREAMING_TARGET_LUFS`/`LOUD_MASTER_TARGET_LUFS` are used by genre/preset profiles, fixed targets, router defaults (residue in TD4-15).
- Frontend timing/limits: `config/timing.ts`, `config/api.ts` (`LIBRARY_PAGE_LIMIT`), `audioConstants.ts`, `similarityCache`, query stale/gc times are named; remaining inline timers (`usePlaybackTransport` 100 ms tick, `useAudioVisualization` 500 ms poll, `useFingerprintStatus` 2 s idle reset, `EditMetadataDialog` 1 s, `RotatingDescription` 10 s) are UI-local and commented, not worth a finding.
- Frontend hardcoded colors outside `design-system/`: none in components/hooks/styles apart from the documented redux-logger dev palette (`loggerMiddleware.ts:66-70,218,224`, #6234) and data-driven `hsla(${hue}…)` in `AlbumCharacterPane`; no `.css` files in `src/`; `--accent-rgb` is test-pinned.
- Spec/protocol constants deliberately not flagged: WAV/RIFF header bytes, PCM16/PCM24 depths (`_PCM16_BYTES_PER_SAMPLE`), the 400 ms BS.1770 block (`loudness_meter.py:42`, `quality_metrics.py:143`, `mastering_file_evaluation.py:32`), `3.0 s` DR block, HTTP status codes, the `sample_rates` enum list in `routers/files.py:101`, `ConfigHash`/migration SQL literals.

### Dimension 5: Stub & Placeholder Implementations

#### Skipped: existing open issues

- **#5628** (OPEN) — 33 orphaned frontend component files. Covers, among others: `navigation/SearchKeyboardHint.tsx` (renders `null` unconditionally, `show` prop discarded; mounted only by the orphan `navigation/SearchBar.tsx`), `library/Search/GlobalSearch.tsx` (no production importer; `onClose: _onClose` unused), `shared/ConnectionStatusIndicator.tsx`, `shared/feedback/ProcessingToast.tsx`, `ProcessingStatsChips.tsx`, `LoadingSpinner.tsx`, `AlbumArtDisplay.tsx` (the other `_theme` placeholders). Not re-reported.

#### Checked and clean

- `NotImplementedError` census (`auralis/`, `auralis-web/backend/`, `vendor/`; `.py`, `.pyi`, `.rs`): 0. `todo!()` / `unimplemented!()` in Rust: 0.
- AST pass-only / ellipsis / docstring-only bodies, `auralis/` + `auralis-web/backend/` (88 hits): all legitimate. `typing.Protocol` stubs (`reference_seeder._FingerprintRepoLike`, `services/queue_protocols.py`, `services/playback_protocols.py`, `websocket/outbound_messages.BroadcastManager` + 27 `@overload`s, `core/cache_cleanup.ClearableChunkCache`) each have concrete structural implementers in the live tree (fingerprint repo mixins, `QueueService`/player, `cache/clearing_mixin.py`). `BaseAssessor` abstract methods have five concrete subclasses. Docstring-only classes are exception types (`ServiceError` family, `ChunkCancelledError`, `ReadTimeout`, `MigrationError`, ...) and `PlaylistRepository` (mixin composition root). `level_transition.calculate_rms` is a `TYPE_CHECKING` host-hook annotation, the idiom CLAUDE.md prescribes (#6235).
- AST "function whose only body is `return <constant/empty>`": 2 hits, both the null-getter default (TD5-05). No `return None  # TODO` stubs; no function returning `[]`/`{}`/`0.0` with a "stub/real impl later" comment.
- Production Python greps for `stub`, `placeholder`, `mock`, `dummy`, `fake`, `coming soon`, `not implemented`, `for now`, `temporar`, `hardcoded`: remaining hits are fingerprint claim-placeholder rows (`PLACEHOLDER_LUFS_SENTINEL`, a real, deliberate mechanism), tempfile names, SQL bind placeholders, and past-tense comments about fixed bugs. No `Mock*` / `Fake*` / `Dummy*` / `Null*` classes in shipped code.
- Routers returning mock/hardcoded data: `GET /api/processing/parameters` returns `_DEFAULT_PARAMETERS` only with an explicit `is_default: True` marker (#3779), a documented honest default, not mock data (see TD5-02 for the separate reporting-only fields). No HTTP 501 / "not implemented" responses anywhere in the backend. `config/fallback_routes.py` dev/missing-frontend landing pages are intentional.
- Frontend components/hooks (non-test): zero "Coming soon" / TODO / mock-data / lorem / hardcoded-sample-data content; every `mock*` / `Mock*` match is under `src/test/`. Components returning `null` are conditional (empty states, loaders), except the always-null `SearchKeyboardHint` already tracked under #5628.
- Rust `vendor/auralis-dsp/src`: no stub/placeholder/not-implemented/dummy markers; no one-line constant-returning functions.
- `WS handlers`, `services/`, `routers/` handler bodies: none are `pass`/constant-return; `ws_handlers/playback_commands.py:104` mention of "hardcoded `is_default: True` placeholders" is a comment describing a fixed bug (#4601).

**Counts: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 5 (TD5-01 .. TD5-05); 1 skipped as existing open (#5628).**

### Dimension 6: Test Hygiene

#### Skipped: existing open issues

None. `jq` over `issues.json` found no OPEN issue on test skips, xfails, weak assertions, mocks or baselines. (#4691 "Eleven backend test modules hard-skipped" is CLOSED and still holds: zero module-level `pytest.mark.skip` remain and the ratchet `tests/backend/test_no_unaccountable_skips_4691.py` exists, not skipped.)

#### Checked and clean

- "Must not regress" tests named in `.claude/commands/*.md` and `.claude/agents/*.md`: 185 distinct `tests/...` / frontend test paths extracted; all resolve to existing files; every `path::name` reference and the one bare test name resolve; none carries an unconditional skip. Four are env-gated at module level (`test_migration_manager_fd_leak.py` on `/proc/self/fd`, `test_seekable_length_agreement_6314.py` on ffmpeg/ffprobe, `test_id3_multivalue_6133.py` on mutagen, `test_cleanup_unreadable_folder_5698.py` dynamic) — acceptable.
- Skip/xfail issue references: both xfails cite #5191 (CLOSED -> TD6-06); no `skip` cites a closed CRITICAL/HIGH issue.
- Weak-assertion ratchets: `check_weak_assertions.py` 32/32, `--zero` 30/30 (both pass, baselines list existing tests only; the zero-assertion entries are mostly legitimate "does not raise / is a no-op" tests, e.g. `test_close_on_an_unconverted_source_is_a_noop`); frontend `check-weak-tests.mjs` 0/0 (OK).
- Commented-out assertions: Python `^\s*#\s*assert` -> 2 hits, both prose; frontend `// expect(` -> only `TEMPLATE.example.tsx` (TD6-13).
- Frontend `it.skip` / `describe.skip` / `it.todo` / `xit` / `.only` / `fit`: 0. `vi.mock` target resolution: 224 mock paths scanned, 0 unresolved (2 hits are fixtures inside the guard tests); `src/tests/vi-mock-targets-exist.test.ts` and `relativeImports.guard.test.ts` guard this.
- `console.log` in specs: none. `expect(true).toBe(true)` appears once (`websocketSubscribeTyping.test.ts:71`), intentional for a compile-time spec, and the full `type-check` (including test files) is a blocking CI step since #5640.
- `try { await ... } catch { /* Expected */ }` in 9 frontend specs (`useEnhancementControl.test.ts`, `usePlaybackQueue.test.ts`): each is followed by an assertion on the resulting error state, so they are not vacuous.
- Over-mocking: 111 of 334 specs use `vi.mock` (224 calls, median 1-2); the heaviest, `AlbumCharacterPane.test.tsx` (14 mocks: seven child components, hooks, `react-redux`), still makes 27 assertions over 14 tests and is a conventional leaf-isolation spec. `setup.ts` auto-mocks only `WebSocketContext` (+ `WebSocket`, `matchMedia`, observers); #5670's WebSocketManager gap is closed.
- Python print-only tests: the zero-assertion ratchet is the gate; `tests/stress/stress_test_suite.py` is a documented manual entry point (not collected by `python_files = test_*.py`).
- Phase-6 / phase-25 local-library tests are correctly gated by `@pytest.mark.local_library` + the `pytest_collection_modifyitems` hook in `tests/conftest.py:589-609` (the only `mark.skip` creation).
- ffmpeg/ffprobe skip gates (about 25 sites) are legitimate external-binary guards.

**Counts: CRITICAL 0, HIGH 0, MEDIUM 1, LOW 12 (13 findings).**

### Dimension 7: Stale Documentation & Comments

#### Skipped: existing open issues

- #5484 (CSP unsafe-inline TODO) is the only genuine marker (Dim 1 owns it); no open issue matches any finding above. Closed siblings consulted: #6246 (module-map), #6247 (dsp-engine), #6251 / #4988 / #4991 (WEBSOCKET_API), #5447 / #4558 / #4057 (FIRST_TIME_SETUP), #5160 / #4272 / #4064 (TESTING_GUIDELINES): residue remains as described above, so these are reported as NEW rather than regressions.

#### Checked and clean

- Version drift vs `auralis/version.py` (1.5.1): `pyproject.toml`, root/`desktop`/`frontend` `package.json`, `routers/health.py` fallback (kept aligned by `sync_version.py::update_health_fallback`), `schemas/system.py` example, README badge/text, MASTER_ROADMAP (tags v1.2.1-beta.1 correct), `__db_schema_version__` 32 everywhere the gate counts: all consistent. `vendor/auralis-dsp` 0.1.0 is an independent crate version.
- CLAUDE.md codebase-map paths: every file/dir named in the tree exists (spot-check of 50 paths); `check_doc_counts.py` current (75/20/996/8384/18/12/32).
- CLAUDE.md claims: marker census (1 genuine = `TODO(#5484)`, OPEN; tests 0) matches `baseline.txt`; frontend baseline empty (verified `test-baseline.json`); `pytest-baseline.json` tracked (73 failures) and first regenerated in `7c03249e` 2026-08-19; `pnpm/action-setup` has no `version:`; backend CI on Python 3.14; cited closed issues #5091/#5027/#4974/#6076/#5143/#4357/#5086/#6235/#5829/#5764/#5780 are CLOSED as written.
- `recording_type_detector.py` "OFFLINE only" claim: only `scripts/rate_track.py`, `analyze_feedback.py` and tests import it.
- README and FIRST_TIME_SETUP command examples: `uv venv`, `uv pip install -r requirements.txt`, `maturin develop`, `python main.py --dev`, `pnpm run dev|test:memory|build`, desktop `build:linux|win|mac:arm64` all exist in package.json / config; `--dev` is parsed in `config/app.py`.
- WEBSOCKET_API.md: every documented `####` message type has an emitter/handler (only `audio_chunk` is synthesised client-side, documented as such); the TS union block is guarded by `test_ws_type_registry_drift_4680.py`; client->server command payloads match `schemas/websocket.py` comments and `ws_handlers`.
- `schemas/websocket.py` enum docstring vs actual inbound handling: consistent (outbound-only members are labelled).
- docs/architecture/overview.md, data-flow.md and docs/subsystems/{fingerprinting,backend-api (chunk section)}.md chunk/crossfade statements: consistent with the no-crossfade, 15 s/10 s model.
- `vendor/auralis-dsp/UPGRADE_PLAN.md` vs `Cargo.toml` pins (pyo3/numpy 0.29, ndarray 0.16, edition 2024/1.85): consistent; `lib.rs` crate docs match the 10-file layout.
- `.agents/commands` mirror: byte-identical to `.claude/commands` bodies; `sync_agent_commands.sh --check` passes. Audit skill dimension counts (tech-debt 10, integration 9 flows, comprehensive 8) match their headings.
- `_audit-common.md` Project Layout: stage count (12 + hf_budget), Rust file count (10), CI workflow list, script list all match the tree.
- `pyproject.toml` / package descriptions and classifiers: current (3.14, AGPL-3.0-or-later, desktop-only wording).
- `auralis-web/README.md`: current (platform policy, pnpm, `type-check:prod`, 8765).
- Source `file.py:NNN` anchors: only three exist outside tests (all reported in TD7-14).

### Dimension 8: Backwards-Compat Cruft & No-Variants

#### Skipped: existing open issues

- No OPEN issue overlaps with this dimension's findings (checked titles for breadcrumb / compat / legacy / re-export / shim / alias / SearchBar / ProgressBar / lookahead / crossfade / gapless / settings / sidecar / version).
- Closed-issue relationships noted per finding: #4973 (TD8-15, debt remains), #4744 (TD8-08), #5775/#5827 (TD8-07), #5821 (TD8-04/05), #6257 (TD8-01).

#### Checked and clean

- Variant-named files/classes/components (`*v2*`, `*Enhanced*`, `*Advanced*`, `*Legacy*`, `*Old*`, `*New*`, `*Simple*`, `*Basic*`): every hit is a domain name with no coexisting base (`enhanced_audio_player.py`/`AudioPlayer`, `stream_enhanced*`/`EnhancedStream` vs normal stream, `useEnhanced*` hook split of `usePlayEnhanced`, `AdvancedSettingsPanel`, `dsp/basic.py` primitives, `SimpleMasteringPipeline` kept per #4873). `Streamlined*`, `UnifiedConfig`, `unified_loader` not flagged per Principle 3. The real duplicates are TD8-02/03.
- `DeprecationWarning` / `warnings.warn` / `@deprecated` in `auralis/`, `auralis-web/backend/`, `frontend/src`, `vendor/auralis-dsp/src`: zero occurrences.
- Python `_`-prefixed parameters via AST scan: only protocol signatures (`__exit__(_exc)`, SQLAlchemy event `_record`, `_refresh_reference_cloud(*_args)`, `stream_seek.body(_validated_filepath)` callback); no dead renamed params in Python beyond TD8-05.
- Legacy DB schema shims for versions already migrated past (schema 32): no production code references the removed `queue_state`/`queue_history`/`library_stats`/`playlists.mastering_profile`/`fingerprint_*` tracks columns; `migration_manager.initialize_fresh_database` rejects pre-versioning files with a clear error (no silent shim); `schema_indexes.py`, nullable `file_mtime` ("pre-v22 rows" -> rescan once) and `helpers.py:112-125` preset/intensity guards are live data-defence, not shims. (Minor: `Track.filepath_key` is still `Mapped[str | None]` "Nullable so the v017->v018 migration can add the column", while v032 made it unique - a NOT NULL tightening candidate for the library audit.)
- Legacy deficit-based EQ fallback (`parameter_generator.py`, `parameter_generator_eq.py`): still live when the reference cloud is empty (`continuous_mode.py:224-232`).
- `AdaptiveMode` / hybrid / reference modes: still reachable through the processing-jobs API (`job_execution.py:149`) and documented in the class docstring; not flagged.
- `recording_type_detector.py` "legacy" profile wording: domain classification inside an offline-only module (#4873/#5780), not a shim.
- `BufferScheduler.ts` ScriptProcessorNode "legacy fallback": deliberately kept (#4623 in-file note).
- `design-system/tokens/*` "convenience names, not backwards-compat shims" (#4402): confirmed in-file; `BorderRadius` alias layer cleaned (#6289).
- Router coordinators (`routers/player.py`, `routers/enhancement.py`, `routers/processing_api.py`) re-export handlers they themselves register with `add_api_route`; not compat-only (the extra test-patch indirection is Dim 2/6 territory).
- Rust `vendor/auralis-dsp/src`: no compat/deprecated/legacy surface beyond history comments (TD8-01 `lib.rs:11`).
- `scripts/check_breadcrumbs.py` run: reports 0 (the gap is TD8-01).

Count: HIGH 0, MEDIUM 0, LOW 16

### Dimension 9: File / Function / Module Complexity

#### Skipped: existing open issues

- **#5481** (OPEN): Python function-length census. The census is now **50** functions over 100 LOC (was 76) — `d9_funcs.txt`. It is informational and fix-opportunistically, so I do not file them separately. Update its numbers with this list and axes:

  | LOC | Function | Axis |
  |---|---|---|
  | 238 | `core/stream_normal.py::stream_normal_audio` | #5032's deferred streaming handlers; split setup / pump / teardown (the pump is already in `stream_normal_chunks.py` at 170) |
  | 231 | `config/routes.py::setup_routers` | sequential router wiring with 10+ copies of `create_*_router(...); app.include_router; logger.debug`; group into `_include_core_routers / _include_library_routers / _include_optional_routers` or a table of (factory, kwargs) |
  | 223 | `core/mastering_branches/continuous.py::ContinuousMasteringBranch.apply` | stage chain; split low-end (notches, makeup gain, bass, sub-bass, transients, warmth) / HF (exciter, clarity, presence, air) / final (soft clip, limit), keep the `_assert_finite` checkpoints between groups |
  | 197 | `routers/files_upload.py::upload_files` | per-file validate / write-temp / scan stages; a `_process_one_upload()` helper (guard against regressing #5968/#5839 depth) |
  | 196, 170 | `stream_enhanced_chunks.py::pump_chunks`, `stream_normal_chunks.py::pump_normal_chunks` | #5032 deferral; common chunk-pump skeleton |
  | 156, 155, 155 | `GaplessPlaybackEngine.advance_with_prebuffer`, `mastering_prepare.prepare_file`, `mastering_chunk_loop._render_to_sink` | by phase (decode / analyse / plan; prebuffer / swap / notify; render / sink / progress) |
  | 153 | `stream_protocol.py::send_pcm_chunk` | frame build vs send vs accounting |
  | 148, 144 | `PlaylistMembershipMixin.add_track`, `BatchUpdateMixin.batch_update` | validation / mutation / result assembly; the session-scope body is the only part that must stay together |
  | 144, 140, 139 | `LevelTransitionMixin.smooth_transition`, `LibraryScanner.scan_directories`, `extract_chunk_segment` | by phase |
  | 137, 137 | `stereo.adjust_stereo_width_multiband`, `system.py::websocket_endpoint` | band loop helper; receive-loop / dispatch / cleanup |
  | 100-133 (31 more) | see `d9_funcs.txt` | opportunistic |

  Note: `compute_windowed_fingerprint` (297 LOC in the issue's text) and `load_with_ffmpeg` (230) no longer exceed 100 lines.
- #5166 (router factories, CLOSED): `create_*_router` factories are no longer in the >100 census; only the handlers inside them (`upload_files`, `scan_library` 137, `get_album_artwork` 130, `batch_update_metadata` 126) remain.
- #5032 (streaming handlers, CLOSED/deferred): the three handlers are now 238/196/170 lines (were ~400); remain in #5481's group 2.
- #5630 / #5628 (open, frontend wiring and orphaned components) are Dim 2/3 matters and not duplicated here.

#### Checked and clean

- Python control-flow nesting >4 in `auralis/` + `auralis-web/backend/`: 0 offenders over 2,457 functions using the exact rules of `tests/regression/test_control_flow_nesting_5839.py`, and still 0 when `ast.TryStar` (not in the guard's block tuple) is added. 76 functions sit at exactly depth 4 (the boundary), none at 5. #5839 holds.
- TS control-flow nesting >4: 0 (if/for/while/do/switch/try, elif chains not counted), also 0 with callbacks charged to the outermost function.
- `__init__.py` re-exports >20: `backend/schemas/__init__.py` re-exports 36 names and `design-system/index.ts` ~33 items, but both are single-purpose domain-grouped facades documented as such (#5479); `config/startup/__init__.py` (190 lines, 21 re-imported names) mixes the lifespan and the re-imports on purpose so `patch("config.startup.X")` keeps working (stated in its docstring). Not filed. All other `__init__.py` / `index.ts` <=16 names.
- `loc-ceilings.json`: all 148 listed files exist; 147 are at exact size, 1 slack (reported in TD9-11); only 1 ceiling is above 300 (TD9-10); no ceiling is exceeded now (the gate is green for listed files).
- TS test files over 300 LOC: 72 (33 over 500; top: `useLibraryQuery.test.ts` 1586, `usePlayEnhanced.test.ts` 1543, `usePlayerStateSync.test.ts` 1448, `test/mocks/handlers.ts` 1268). Not shipped code; the 300-line rule is not applied to specs here; not filed.
- Python files in `auralis/` and `auralis-web/backend/` between 270 and 300 LOC with no ratchet entry are listed in TD9-11; none is over the rule today.
- React component size: the only shipped component file over 300 is `CozyLibraryView.tsx` (TD9-10); 20+ JSX components at 150-240 lines are declarative render trees and are left alone.

**Summary: 14 findings — 0 CRITICAL, 0 HIGH, 0 MEDIUM, 14 LOW; 1 existing open issue skipped (#5481).**

### Dimension 10: Audit-Finding Rot

#### Skipped: existing open issues

None. No OPEN issue in `issues.json` covers skill-file rot, trace-flow, loc-ceilings or audit-report triage.

Open issues cited from skill files (6) and whether the prose matches: #5615, #5655, #5708, #5960, #6171, #6187. All six are OPEN and every sentence that cites one says so ("open", "stays open", "still open", "Existing: #5615"). The #5615 claim (connection slice write-dead) and #5708 claim (`track_loaded` has no subscriber) still match the code. #6171 partial fix is real (`WS_MAX_CONNECTIONS` in `config/globals.py`, test `tests/backend/test_ws_connection_cap_6171.py` exists).

#### Checked and clean

- Path-reference gate (`_audit-validate.sh`): strict 0 stale, ratchet 120/120 unchanged. The 120 ratchet entries are all under `docs/` (Dim 7 backlog), none in `.claude/**`; no new Dim 10 findings from it.
- Issue references in `.claude/commands/**/*.md` and `.claude/agents/*.md`: 484 distinct `#NNNN`, 478 CLOSED, 6 OPEN, 0 missing from `issues.json`. For all 478 CLOSED I scanned a window around every occurrence for pending language (tracked, until, open, pending, follow-up, deferred, remains, etc.): 58 hits, every one read as provenance ("deleted in #4565", "fixed in ...", "since #5649"), none framing a closed issue as pending. Examples read in full: `audit-security.md:34`, `audit-concurrency.md:96`, `audit-backend.md:31` (the "still open" ones are #6171, #5960, #6187, all genuinely OPEN).
- Dimension and count claims in skill files, each compared with the live list: "all 10" tech-debt dimensions (10 headings, audit-suite.md:41 also says 10), `comprehensive` = 8 audits (8 listed, two batches of 4), integration "9 flows" (9 headings), verify-dsp "6 invariants" (INV-1..INV-6), verify-release "13 gates" (13 headings), "11 workflows" in audit-deprecation (11 files in `.github/workflows`), 20 routers, 12 repositories, 75 analysis files, 996 test files / 8384 functions (gate-verified).
- `audit-suite.md` `--focus` / `--flows` numbers still point at the right dimensions: backend 2,3,10,11 = WebSocket / chunking / caching / seek; frontend 3,6 = hooks / API client; concurrency 1,2,3 = player / pipeline / backend streaming; integration flows 1,3,5,8.
- Symbol anchors (`path::Symbol`) across `.claude/**` and CLAUDE.md: 8 distinct tokens; 5 resolve, 3 are intentional placeholders except for TD10-01.
- Metric notes in `audit-tech-debt.md` versus `baseline.txt` and live greps: `NotImplementedError` reads 0 as the note says; `markers, genuine (src)` = 1 (`security_headers.py:124` `TODO(#5484)`, #5484 OPEN, matches CLAUDE.md "1"); `markers, genuine (tests/)` = 0 (matches CLAUDE.md); `skipped tests (ts)` = 0 (matches #6279 note); `sample_rate=44100 defaults` = 20, no hardcoded diff base in the skill (history 48 -> 43 -> 30 is labelled as past values, now 20; direction down); 'any' non-test = 0. No metric note quotes a stale current value.
- Dim 9 prose facts: commits `591cf2b72`, `53ce32a2a`, `0ba655c5`, `238bde1e`, `7c75b75c`, `78a39d25`, `21083402c`, `a2b11e2d` exist; `scripts/check_loc_ratchet.py`, `scripts/check_doc_counts.py` and `tests/regression/test_control_flow_nesting_5839.py` exist; `FINGERPRINT_ALGORITHM_VERSION` is in `auralis/__version__.py` (audit-incremental.md reference correct). The only ratchet drift is TD10-02.
- `audit-sync/BASELINE` is `b2a74181e` (2026-11-17), so verify-release Gate 13 (WARN at >100 commits) is current.
- Retired Architecture table (`_audit-common.md:71-85`): `parallel_processor.py`, `library/manager.py`, `library/caching/`, `core/config.py`, `stream_prefetch.py`, `cache/monitoring.py`, `utils/helpers.py`, `backend/encoding/`, `preference_engine.py`, `reference_library.py` are all absent from the tree, as claimed. Untracked housekeeping note, not a finding: an empty directory `auralis-web/backend/monitoring/` exists on disk (not tracked by git, so it is invisible to anyone cloning).
- Immutable `.claude/issues/<N>/ISSUE.md` snapshots: not examined for state drift, per the skill.
- Not read: the five `*_2026-11-17.md` reports in `docs/audits` (parallel runs in progress), per instruction.

Summary: 0 CRITICAL, 0 HIGH, 0 MEDIUM, 3 LOW.
