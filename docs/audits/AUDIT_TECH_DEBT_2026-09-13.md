# Auralis Tech-Debt Audit — 2026-09-13

**Scope**: The whole repo: `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/`, `tests/`, `docs/`, `.claude/`. All 10 dimensions, `--depth deep`, no `--limit`. This is a fresh audit of the tree at `ce119be1` (plus today's uncommitted frontend `settingsService`/`serviceFactory` edits).
**Prior report**: [`AUDIT_TECH_DEBT_2026-08-23.md`](AUDIT_TECH_DEBT_2026-08-23.md). Only its baseline figures were used, for the deltas. No finding was carried forward without re-verification.
**Deduplicated against**: open issues, all `tech-debt`-labelled issues, the last 1000 issues in any state, and today's sibling reports (`AUDIT_BACKEND/ENGINE/FRONTEND/INTEGRATION/DEPRECATION_2026-09-13.md`).

---

## Executive Summary

| | Count |
|---|---|
| **NEW findings** | 45 |
| **Regressions** | 0 (the closed-but-regrown god-file splits are reported as NEW; see TD9-01) |
| **Existing items re-verified and skipped** | 27 (see "Skipped as Existing") |

| Severity | Count | Delta vs 2026-08-23 |
|---|---|---|
| CRITICAL | 0 | = |
| HIGH | 0 | = |
| MEDIUM | 2 | -3 (was 5) |
| LOW | 43 | +2 (was 41) |
| **Total** | **45** | -1 (was 46) |

By dimension: Stale Markers 2 · Dead Code 15 · Logic Duplication 5 (1 MEDIUM) · Magic Numbers 2 · Stubs 0 · Test Hygiene 3 (1 MEDIUM) · Stale Documentation 8 · Backwards-Compat Cruft 2 · Complexity 8 · Audit-Finding Rot 0.

**Headline items**
- **TD6-01 (MEDIUM, act first)**: today's preset-narrowing commits (`c195ac80` / `ae9d28e3`) left **19 backend tests across 6 files** still sending or asserting `warm`/`bright`/`punchy`/`gentle`. I re-ran each file on its own and all 19 fail. None are in `pytest-baseline.json`, so `backend-tests.yml`'s ratchet will fail on them as new failures. Absorbing them into the baseline would re-permit real regressions in the preset-persistence path (#4409/#4587/#4742).
- **TD3-02 (MEDIUM)**: #4700's type-based error mapping reached only the queue endpoints in `routers/player.py`. Seven playback, seek, volume and history sites still hard-code a status code. `set_volume` already reports "Audio player not available" as **400**, which is the exact bug class #4700 fixed. The fix has to start in the service layer: `playback_service.py` and `navigation_service.py` raise untyped `ValueError`s, so swapping in `raise_for_service_error` alone would turn today's 503s into 400s.
- **TDX-02**: 453 source files say `:license: GPLv3`, but `LICENSE` is AGPL-3.0. Zero files say AGPL, and 172 of the stale headers are in files created after 2026-02-12, so new files keep copying it.
- **TD9-01**: three god-file splits that closed under or near 300 LOC have regrown: `chunked_processor.py` 297→319, `enhanced_audio_player.py` 299→311, `processing_engine.py` 365→377.

**Direction of travel**: Markers stay clean: 0 in shipped code, and 3 in `tests/`, all citing OPEN issues. Stubs (Dim 5) and audit-finding rot (Dim 10) came back with **zero** findings; every hardcoded skill-file count and all 51 issue callouts checked out. Magic numbers are down to 2 LOW, because chunk geometry, limits, env config and colour tokens are all consolidated. Dead code is still the largest bucket (15 findings), mostly leftovers of closed fixes that swept one symbol and missed its neighbours (#4592 → `reference_library.py`, #4393 → `errorHandling.ts`, #5171 → `escape_like`). New debt from today's commits is concentrated in the preset-narrowing change (TD6-01, TD3-04, and the one new `any`).

---

## Baseline Snapshot

Captured 2026-09-13 with the Phase 1 greps from `.claude/commands/audit-tech-debt.md`. Labels follow the #4564 metric notes.

| Metric | 2026-09-13 | 2026-08-23 | Read it as |
|---|---|---|---|
| markers, genuine (src) | **0** | 0 | The real marker debt in shipped code. 0 is the expected, good value. |
| markers, genuine (tests/) | **3** | 4 | `test_boundary_data_integrity.py:555` TODO(#5172), `test_boundary_advanced_scenarios.py:652` TODO(#5172), `test_database_migrations.py:338` TODO(#5174). Both issues are **OPEN**, and all three markers date from `7144b920` (2026-08-16). Legitimate. Down by one since #5173 closed and its marker went with it. |
| markers, raw (pre-filter) | 2 | 2 | Diagnostic only. Both are filtered false positives: `schema.py:37` `#3xxx` (see TD1-01) and a `0.xxxxxxxx` test string. |
| prose deferrals (non-test) | 8 | 6 | Read individually: 6 are ordinary prose (HTTP 503 "temporarily unavailable", "501 Not Implemented", "not a workaround", a scoped set/restore). 2 are real untracked deferrals → TD1-02. |
| NotImplementedError | 3 | 3 | All in `duplicate_detector.py`. An intentional input-contract guard (#4241), but the whole path is test-only → TDX-04. |
| type: ignore (py) | 67 | 66 | `mypy --warn-unused-ignores` over all 30 affected files found 0 stale; all carry error codes. |
| @ts-ignore/@ts-expect-error | 2 | 3 | — |
| 'any' non-test (ts) | 14 | 13 | The type-safety debt that ships, but **7 of the 14 hits are comment prose** (TDX-05). Genuine: `loggerMiddleware.ts` ×2, `Text.tsx`, `serviceFactory.ts` ×2 (FE-13), `useAlbumDetails.ts` (FE-04), and `keyboardShortcutDefinitions.ts:21` (**new today**, part of #5231). |
| 'any' raw incl. tests (ts) | 486 | 488 | Trend continuity only. |
| skipped tests (py) | 46 | 44 | +2, both legitimate new platform/dependency `skipif`s (`test_downmix_layout_routing_5242.py`, `test_default_dir_hardening_4824.py`). |
| skipped tests (ts) | 16 | 16 | 14 of them are the `describe.skip` integration cluster tracked by #5179/#5186. |
| py files >300 LOC | 88 | 90 | See Dim 9. |
| ts/tsx files >300 LOC | 113 | 113 | 28 non-test. |
| allow(dead_code) (rust) | 0 | 0 | Clean. |
| sample_rate=44100 defaults | 30 | 30 | **A drift indicator, not a debt count** (#4924). No change and no new sites. The 21 files: `analysis/{base_spectrum_analyzer, dynamic_range, loudness_meter, phase_correlation, ml/feature_extractor, quality/mastering_evaluation, quality/quality_metrics}`, `core/analysis/content_analysis_facade` (7), `core/analysis/content_analyzer` (2), `core/config/unified_config`, `core/dsp/parallel_eq` (3, doctest only), `dsp/dynamics/{brick_wall_limiter, settings}`, `dsp/eq/psychoacoustic_eq`, `learning/reference_library`, `player/{audio_file_manager, config}`, backend `analysis/analysis_extractor`, `config/startup`, `core/chunk_boundaries`, `core/level_manager`. The live-bug counterpart is ENG-D2-03 (HIGH, engine audit). |

Other gates checked this run: `_audit-validate.sh` exit 0 (strict 0 stale; ratchet 302 against a 302 baseline). `scripts/check_doc_counts.py` matches CLAUDE.md and `_audit-common.md` (55 / 20 / 611 / 6,759 / 18). `pytest-baseline.json` has 157 entries and `test-baseline.json` has 108, both matching the docs. `auralis/version.py`, `pyproject.toml` and all `package.json` files say 1.5.1.

---

## Top 10 Quick Wins (trivial/small effort)

1. **TD6-01**: update the 19 preset tests to `'adaptive'`, plus one invalid-value 422/degrade assertion each (small). This unblocks the backend CI ratchet.
2. **TDX-03**: delete the stale "pytest MUST stay at 9.0.x" comment and pin in `backend-tests.yml`, since #4529 deleted the hook it protects (trivial).
3. **TD3-05**: replace 4 inline LIKE-escape chains with the existing `escape_like()` (trivial).
4. **TD3-01**: move the byte-identical `ChunkPumpResult` into `stream_protocol.py` (trivial).
5. **TDX-01 + TD1-01**: delete 5 unused `FingerprintConstants` normalization attributes and fix the `#3xxx` / nonexistent-call comment on `CENTROID_NORMALIZATION_HZ` (trivial).
6. **TD8-01 + TD2-01**: drop 4 unused "backward compatibility" re-exports from `advanced_dynamics.py` and the `apply_crossfade_between_chunks` re-export from `chunked_processor.py` (trivial).
7. **TD2-12 + TD2-05 + TD2-02 + TD2-04**: delete `serialize_track` / `serialize_artists`, the five `version.py` helpers, `QueueStats` and `CorruptedTrackError` (trivial).
8. **TD7-01 + TD7-02**: fix README and FIRST_TIME_SETUP test commands (add `-m "not slow"` and the two `--ignore`s, fix the 5,400 / "700+ in 1-2 min" claims, stop recommending the REC-01 launcher) (trivial).
9. **TD6-02**: delete the dead first `vi.mock('@/contexts/WebSocketContext')` in `Integration.test.tsx` (trivial).
10. **TD7-04 + TD7-05 + TD8-02**: remove comments that cite deleted `ProcessorManager`, `realtime_processor.py` and `get_parallel_processor`, and the duplicated #4975 `reason` breadcrumbs (trivial).

## Top 5 Medium Investments

1. **TD3-02**: type the `PlaybackService` / `NavigationService` raises (`ServiceUnavailable` / `InvalidRequest`), then route the 7 remaining `player.py` sites through `raise_for_service_error`.
2. **TD9-03**: apply #4670's hoist-to-module-level recipe to the 9 routers that still hide handlers in 122–288-line `create_*_router()` closures, one per PR.
3. **TD9-04 + TD9-06**: split `routers/player.py` (881) and `processing_api.py` (861) by sub-resource; split `config/middleware.py` (542) one class per file.
4. **TD9-01 + TD9-02**: bring the three regrown coordinators back under 300 by moving helpers into their existing sibling families, and split `HybridProcessor` (598). Close each only when `wc -l` is under 300 (#4673).
5. **TDX-02**: one mechanical commit replacing `:license: GPLv3` in 453 headers, plus a CI grep that stops new copies.

---

## Findings — MEDIUM

### TD6-01: The preset-narrowing commits left 19 backend tests asserting the removed presets; all fail and none are baselined
- **Severity**: MEDIUM. There is no exact promotion row; promoted because these are regression tests for closed issues that now fail the CI ratchet as new failures, and baselining them would re-permit the regressions they guard.
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_settings_router.py` (3 tests: 177-181, 207-218, 221-224), `tests/backend/test_scan_and_enhancement_helpers.py` (2: 62-68, 83-89), `tests/backend/test_enhancement_settings_persistence_4587.py` (9), `tests/backend/test_enhancement_settings_cross_connection_4742.py` (3), `tests/backend/test_enhancement_router_handler_seam_4670.py` (1: `test_set_enhancement_preset_notifies_the_buffer_manager`), `tests/backend/test_main_api.py::TestPlayerEnhancementEndpoints::test_set_enhancement_preset` (1)
- **Status**: NEW
- **Age**: `c195ac80` / `ae9d28e3`, 2026-09-13. No commit since has touched these files, and `git status` shows no uncommitted test edits.
- **Effort**: small
- **Description**: `schemas.py` now defines `VALID_PRESETS = ["adaptive"]` and `EnhancementPresetLiteral = Literal["adaptive"]`. The request models reject other names (Pydantic `literal_error`). `SettingsResponse._degrade_unknown_preset` and `helpers.seed_enhancement_settings` degrade stored unknown presets to the default. These tests still send, store, or expect `warm`/`bright`/`punchy`/`gentle` and assert the old pass-through behaviour, or assert the OpenAPI enum is the five-preset set.
- **Evidence** (orchestrator re-run, one file at a time): settings_router + helpers → `5 failed, 26 passed`; persistence_4587 + cross_connection_4742 + handler_seam_4670 (+ `test_last_content_profile_lock.py`, which passes) → `13 failed, 15 passed`; `test_main_api.py -k enhancement_preset` → `1 failed`. Typical errors: `Input should be 'adaptive' [type=literal_error, input_value='warm']` and `assert 'adaptive' == 'bright'` with log `Stored default_preset 'bright' is not one of ['adaptive']; keeping 'adaptive'`. `grep -c` of all six files in `pytest-baseline.json` → 0.
- **Impact**: `backend-tests.yml` fails on 19 unbaselined failures. These are the only regression tests for #4424 (preset enum validation), #4409/#4587 (persisted settings reaching live playback), #4742 (cross-connection enhancement settings), #4710 and #4670. Adding them to the baseline would silence exactly the regressions they catch.
- **Siblings**: `tests/backend/test_system_api.py:610-627` also uses old preset literals. It was not run (it hangs as a whole file); check its targeted tests.
- **Related**: #4861 (closed, motivated the narrowing); Retired Architecture "Discrete enhancement presets" row. This is test-side fallout of an intentional change, not an engine bug.
- **Suggested Fix**: Replace each old literal with `'adaptive'`. Keep one deliberately invalid value per file asserted to 422 or degrade, as `test_settings_router.py::test_update_settings_rejects_invalid_preset` already does. For the persistence and cross-connection tests, which need two *distinct* presets, switch the distinguishing field to `intensity` or `enabled`. Assert `preset_enum == {"adaptive"}`.

### TD3-02: #4700's type-based error mapping stopped at the queue endpoints; 7 playback, seek, volume and history sites still hard-code status codes
- **Severity**: MEDIUM. Promotion row: duplicated logic with divergent bug-fix history (the fixed copy maps by type; the unfixed copy still reports an outage as 400).
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/player.py:403-404` (status, 503), `:523-524` (seek, 503), `:551-552` (volume, 400), `:621-622` (record history, 400), `:678-679` (undo, 400), `:800-801` (next, 503), `:809-810` (previous, 503). Service side: `auralis-web/backend/services/playback_service.py:155-354`, `navigation_service.py:124-255`
- **Status**: NEW (follow-up to closed #4700, `2561e970`)
- **Age**: The unmigrated handlers predate #4700; last touched by `2e07049d` (#4670 hoist).
- **Effort**: small
- **Description**: `routers/errors.py::raise_for_service_error` maps `ServiceUnavailable`→503, `ResourceNotFound`→404, `InvalidRequest`→400, `OperationFailed`→500, and untyped `ValueError`→400. `queue_service.py` raises those typed subclasses, and the 9 queue endpoints use the helper. `PlaybackService` and `NavigationService` raise **bare `ValueError`** for both outages ("Audio player not available") and bad input ("Position must be non-negative", "Volume must be between 0.0 and 1.0"). The routers then pick one hard-coded status per site, so `set_volume` returns 400 for a missing player and `seek` returns 503 for a negative position. (`player.py:650` is a deliberate degrade-and-log, not a mapping site.)
- **Evidence**: 17 `except ValueError` sites in `player.py`, 9 of which call `raise_for_service_error`. `grep "raise ValueError(" playback_service.py navigation_service.py` → 16 untyped raises mixing both classes of condition.
- **Impact**: Clients get the wrong status class for playback outages and bad input. Every future change to the service error taxonomy has to be re-applied by hand at these sites.
- **Siblings**: TD2-11 (the four unused `*UnavailableError` classes, whose messages are retyped by hand in the same files).
- **Related**: #4700 (closed); BE-D7-02 (the similarity routers map "database is locked" to 500).
- **Suggested Fix**: First convert the `playback_service.py` / `navigation_service.py` raises to `ServiceUnavailable` / `InvalidRequest`, mirroring `queue_service.py`. Then replace the 7 router mappings with `raise_for_service_error(e, "<op>")`. Swapping the router calls **without** typing the services would downgrade today's correct 503s to 400. The two queue-history sites (621/678) map repository `ValueError`s and can stay 400, but should use `BadRequestError` for consistency.

---

## Findings — LOW

### Dimension 1: Stale Markers

#### TD1-01: Fingerprint schema comment cites a placeholder issue `#3xxx` and a call that does not exist
- **Severity**: LOW · **Dimension**: Stale Markers · **Status**: NEW · **Age**: `7f937cca` 2026-05-24 · **Effort**: trivial
- **Location**: `auralis/analysis/fingerprint/schema.py:36-39`
- **Description**: The comment on `CENTROID_NORMALIZATION_HZ` says it "Matches SpectralOperations.calculate_spectral_centroid (#3xxx) which uses MetricUtils.normalize_to_range(centroid_median, 8000.0, clip=True)". The issue number was never filled in, and no `normalize_to_range(..., 8000...)` call exists anywhere. The live consumer is `rust_fingerprint.py:93` (`raw / CENTROID_NORMALIZATION_HZ`). The census filter `#[0-9]xxx` hides this placeholder from every marker sweep.
- **Evidence**: `grep -rn "normalize_to_range" auralis | grep -iE "centroid|8000"` → only the comment itself.
- **Impact**: It misdirects readers on the constant behind INT-F6-01's Hz vs normalized confusion.
- **Siblings / Related**: TDX-01 (a second, unused 8 kHz constant); INT-F6-01.
- **Suggested Fix**: Rewrite the comment to point at `rust_fingerprint.py`, and drop the placeholder and the nonexistent call.

#### TD1-02: Two conditional deferrals are written as untracked prose, one pointing at a CLOSED issue
- **Severity**: LOW · **Dimension**: Stale Markers · **Status**: NEW · **Effort**: trivial
- **Location**: `auralis-web/backend/config/middleware.py:169-170`; `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:97-98`
- **Description**: CLAUDE.md principle 5 requires `TODO(#NNNN)`. `middleware.py` defers a script-src CSP hash/nonce with "Revisit if Vite's own CSP/nonce plugin support … lands" and cites no issue. `useAlbumFingerprint.ts` says "Revisit with #5122's close comment", but #5122 is CLOSED.
- **Impact**: Neither is visible to any marker sweep (#4564, #5143).
- **Suggested Fix**: File a tracking issue and convert to `TODO(#NNNN)`, or reword as a settled decision with no revisit clause.

### Dimension 2: Dead Code

#### TDX-01: Five `FingerprintConstants` normalization attributes have zero users; a sixth is test-only
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: `530cf6a9` 2026-01-02 · **Effort**: trivial
- **Location**: `auralis/analysis/fingerprint/metrics/constants.py:48-60`
- **Description**: The class calls itself the "Single source of truth for all fingerprint-related constants". Production reads only `EPSILON` (`safe_operations.py:23`) and `CV_DEFAULT_SCALE` (`range_ops.py:26`). `SPECTRAL_CENTROID_MAX = 8000.0`, `SPECTRAL_ROLLOFF_MAX = 10000.0`, `CHROMA_ENERGY_MAX`, `ONSET_DENSITY_MAX` and `CV_HARMONIC_SCALE` have no reader anywhere, tests included. `FINGERPRINT_DIMENSIONS` is read only by 2 tests. The live Hz normalizers are defined separately in `schema.py`.
- **Evidence**: A per-name grep over `auralis/`, `auralis-web/`, `vendor/`, `scripts/` and `tests/` found only the definition lines, plus 2 test asserts for `FINGERPRINT_DIMENSIONS`.
- **Impact**: There are two homes for the 8 kHz / 10 kHz normalization values. Retuning the dead one silently does nothing.
- **Suggested Fix**: Delete the 5 attributes. Point the 2 tests at `len(FINGERPRINT_DIMENSION_NAMES)`, or keep `FINGERPRINT_DIMENSIONS` and assert against it in the extractor.

#### TDX-04: Whole-library duplicate detection (#4241) is reachable only from tests
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Effort**: small
- **Location**: `auralis/library/scanner/scanner.py:474-484`; `auralis/library/scanner/duplicate_detector.py:45-120`
- **Description**: `LibraryScanner` builds a `DuplicateDetector` on every construction and exposes `find_duplicates()`, but nothing in `auralis/`, `auralis-web/` (backend or frontend), `desktop/` (excluding the gitignored `desktop/resources/` copy), `scripts/` or the launcher calls it. The only consumer is `tests/auralis/library/test_duplicate_detector_whole_library.py`. The path also accounts for all 3 `NotImplementedError` census hits and a `# type: ignore[no-any-return]` (`duplicate_detector` is typed `Any`).
- **Impact**: #4241 fixed and tested a feature no user can reach.
- **Related**: #4241 (closed); same "fixed but never wired" shape as ENG-D7-02 `QueueRepository`.
- **Suggested Fix**: Product call. Either expose it (e.g. `GET /api/library/duplicates`) or delete `DuplicateDetector`, the scanner wrapper and attribute, and the test.

#### TD2-01: `apply_crossfade_between_chunks` is re-exported for compatibility but has zero non-test callers
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: `f51e1a22` 2026-07-15 · **Effort**: trivial
- **Location**: `auralis-web/backend/core/chunk_crossfade.py:39`; re-export at `auralis-web/backend/core/chunked_processor.py:76` (`# noqa: F401`)
- **Description**: All 13 call sites are in `tests/` (`test_equal_gain_crossfade.py`, `test_chunked_processor.py`, `test_chunked_processor_invariants.py`). `_audit-common.md`'s Retired Architecture table documents the function as having no production caller, but no issue tracks deleting the re-export.
- **Suggested Fix**: Delete the `chunked_processor.py` re-export and import from `core.chunk_crossfade` in the three tests. Keep the equal-gain curve as-is (#3878).

#### TD2-02: `QueueStats` dataclass is never instantiated
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Effort**: trivial
- **Location**: `auralis-web/backend/analysis/fingerprint_queue.py:33-40`
- **Description**: It duplicates `FingerprintQueueState`'s shape. `get_stats()` returns a plain dict, and `grep -rn "QueueStats"` hits only the class definition.
- **Related**: BE-D10-03 (the same `analysis/` package has other no-caller classes).
- **Suggested Fix**: Delete it, or have `get_stats()` return it.

#### TD2-03: Four `reference_library.py` functions have been orphaned since #4592 deleted their only caller
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: orphaned by `d62c9c1c` (#4592) · **Effort**: trivial
- **Location**: `auralis/learning/reference_library.py:389-415` (`get_references_for_genre`, `get_quality_benchmark`, `list_all_references`, `get_high_priority_references`)
- **Description**: `reference_analyzer.py` was their only consumer, and it was deleted in #4592. Now only the definitions remain. #4278 removed the sibling `get_engineer_profile` for the same reason.
- **Related**: #4592, #4278 (closed); #5204/#5207 (open, same pattern elsewhere).
- **Suggested Fix**: Delete all four.

#### TD2-04: `CorruptedTrackError` is defined but never raised or caught
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: `9e82ae2f` 2026-01-02 · **Effort**: trivial
- **Location**: `auralis/services/fingerprint_extractor.py:30`
- **Related**: ENG-D6-01 (failed extraction leaves a placeholder row). Check whether this class was meant to signal that case before deleting it.
- **Suggested Fix**: Delete it, or raise it from the corruption branch and catch it specifically.

#### TD2-05: Five public functions in `auralis/version.py` have zero callers
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Effort**: trivial
- **Location**: `auralis/version.py:32-34` (`get_version`), `:69-86` (`is_prerelease`, `is_beta`, `is_rc`, `get_short_version`)
- **Evidence**: Grepped each name across `auralis/`, `auralis-web/`, `desktop/`, `scripts/`, `tests/`, `launch-auralis-web.py` and `sync_version.py`: 0 hits apart from `health.py`'s unrelated route handler named `get_version`.
- **Suggested Fix**: Delete them. The constants and `get_version_info()` stay.

#### TD2-07: `auralis/utils/checker.py` is a Matchering-legacy module with only test callers
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: last touched `030831e4` 2026-06-02 · **Effort**: small
- **Location**: `auralis/utils/checker.py:1-119` (`check`, `check_equality`, `is_audio_file`, `check_file_permissions`)
- **Description**: No production module imports it (hits only in gitignored build copies). It is used by `tests/auralis/utils_module/test_checker.py`, `tests/regression/test_format_consistency_and_rf64.py` and `tests/auralis/core/test_core.py`. `unified_loader.py` defines its own `is_audio_file`.
- **Suggested Fix**: Delete it and repoint or delete its tests. If `check()` has unique validation, fold it into `audio_validation.py` first.

#### TD2-08: `errorHandling.ts` has more dead surface than FE-17 named
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: `89377d8e` 2025-11-12 · **Effort**: small
- **Location**: `auralis-web/frontend/src/utils/errorHandling.ts:69` (`DEFAULT_WEBSOCKET_CONFIG`), `:308` (`classifyErrorSeverity`), `:369` (`createTimeoutPromise`), `:390` (`ErrorLogger`), `:443` (`globalErrorLogger`)
- **Evidence**: 0 references anywhere in `src/` outside their own definitions, tests included.
- **Related**: FE-17 (the same file's retry cluster); #4393 (closed; deleted `ErrorRecoveryChain`, `withErrorLogging` and `resilientFetch` from this file but did not cover these five).
- **Suggested Fix**: Delete them together with FE-17's cluster in one pass.

#### TD2-09: Seven exported PCM utilities in `pcmDecoding.ts` have no production callers
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: `afd33155` 2025-12-04 · **Effort**: small
- **Location**: `auralis-web/frontend/src/utils/audio/pcmDecoding.ts:101,125,161,197,224,344,361` (`monoToStereo`, `stereoInterleavedToChannels`, `validatePCMSamples`, `clipPCMSamples`, `resamplePCM`, `durationToSampleCount`, `sampleCountToDuration`)
- **Description**: Production code imports only `decodeAudioChunkMessage`, which uses `decodeBinaryPCM`. The seven are exercised only by `__tests__/pcmDecoding.test.ts`.
- **Related**: DEP-INT-5 (base64 legacy decode branch in the same file); ENG-D1-01 (no NaN guard). Check whether `validatePCMSamples` should be wired in rather than deleted.
- **Suggested Fix**: Delete the 5 conversion helpers; wire in or delete `validatePCMSamples` / `clipPCMSamples`.

#### TD2-10: `playlistService.addTrackToPlaylist` / `removeTrackFromPlaylist` are unreachable from the UI
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: `9339df2d` 2025-10-21 · **Effort**: small
- **Location**: `auralis-web/frontend/src/services/playlistService.ts:220`, `:244`
- **Description**: The UI calls only the batch `addTracksToPlaylist` (`useTrackContextMenu.ts:64,76`). Nothing in `components/` or `hooks/` calls either singular function. They are used only by the service unit test and an integration test that calls the service directly.
- **Related**: A possible product gap (no remove-from-playlist UI); frontend audit to judge.
- **Suggested Fix**: Delete `addTrackToPlaylist`. Wire `removeTrackFromPlaylist` into the playlist detail view, or delete it.

#### TD2-11: `routers/errors.py`'s four `*UnavailableError` classes are never raised, while call sites retype their messages
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Age**: `f6d5e612` 2025-11-12 · **Effort**: small
- **Location**: `auralis-web/backend/routers/errors.py:55-73`. Hand-rolled copies: `routers/dependencies.py:41,60,70`, `routers/library_scan.py:61,78`, `routers/player.py:377,438`, `services/queue_service.py:252,395`
- **Evidence**: No `raise` of any of the four in `auralis-web/backend`. The only users are the construction tests in `tests/backend/test_error_responses.py:136-156`.
- **Related**: TD3-02 (same error-taxonomy consolidation).
- **Suggested Fix**: Repoint the `require_*` dependencies and the listed sites to the existing classes (or `ServiceUnavailable` in services), or delete the classes and their tests.

#### TD2-12: `serialize_track` and `serialize_artists` have zero callers
- **Severity**: LOW · **Dimension**: Dead Code · **Status**: NEW · **Effort**: trivial
- **Location**: `auralis-web/backend/routers/serializers.py:197`, `:301`
- **Evidence** (orchestrator recount including in-file calls): `serialize_track` has no caller anywhere; the only hit outside tests is a docstring mention in `schemas.py`. `serialize_artists` is never called; it only calls `serialize_artist` internally. The other six functions all have router call sites. `serialize_objects` looks externally unused but is live via `serialize_tracks` (`:220`).
- **Suggested Fix**: Delete both, and update the `schemas.py` docstring reference and the tests.

### Dimension 3: Logic Duplication

#### TD3-01: `ChunkPumpResult` is copied verbatim across the three chunk-pump siblings
- **Severity**: LOW · **Dimension**: Logic Duplication · **Status**: NEW (a leftover of the closed #5032 split) · **Effort**: trivial
- **Location**: `auralis-web/backend/core/stream_normal_chunks.py:56-64`, `stream_enhanced_chunks.py:42-50`, `stream_seek_chunks.py:42-50`
- **Description**: Three byte-identical `@dataclass` definitions (`stopped_early`, `failed_chunks`, `delivered_samples`), each feeding `send_stream_completion`.
- **Impact**: A field added to one copy silently doesn't exist on the others.
- **Suggested Fix**: Define it once in `stream_protocol.py` and import it in all three.

#### TD3-03: `FingerprintSimilarityMixin` hand-rolls session lifecycle instead of `_session_scope()`
- **Severity**: LOW · **Dimension**: Logic Duplication · **Status**: NEW · **Effort**: trivial
- **Location**: `auralis/library/repositories/fingerprint_similarity_mixin.py:75-85, 104-116, 127-134`
- **Description**: Three write methods use `session = self.get_session(); try … commit … finally close`, with no rollback. Every other repository write path uses `BaseRepository._session_scope()`; this file is the only non-base caller of `get_session()`.
- **Suggested Fix**: Convert all three to `with self._session_scope() as session:`.

#### TD3-04: `useEnhancementControl.ts` hardcodes the preset list instead of importing `ENHANCEMENT_PRESETS`
- **Severity**: LOW · **Dimension**: Logic Duplication · **Status**: NEW · **Age**: left by `ae9d28e3` 2026-09-13 · **Effort**: trivial
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:317` vs `auralis-web/frontend/src/types/domain.ts:158-160`
- **Description**: The file imports the `EnhancementPreset` type from `@/types/domain` but redeclares `const validPresets: EnhancementPreset[] = ['adaptive']`. This is an eighth mirror of the preset list, and the only one not documented in Sibling Detection.
- **Related**: FE-12 (`ENHANCEMENT_PRESETS` is listed as a dead export). Importing it here resolves both.
- **Suggested Fix**: `import { ENHANCEMENT_PRESETS } from '@/types/domain'` and use it.

#### TD3-05: `escape_like()` exists, but 4 repositories still carry the inline expression it replaced
- **Severity**: LOW · **Dimension**: Logic Duplication · **Status**: NEW (the follow-up #5171's own docstring deferred) · **Effort**: trivial
- **Location**: `auralis/library/repositories/track_repository_search.py:39`, `album_repository.py:188`, `artist_repository.py:224`, `genre_repository.py:272` (helper at `base.py:26-44`)
- **Evidence**: The same `query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')` chain appears at all 4 sites plus the helper. The helper's docstring names these 4 as a "mechanical follow-up", and no issue tracks it.
- **Impact**: A fix to LIKE escaping (#2405 class) has to land in 5 places.
- **Suggested Fix**: Replace each inline chain with `escape_like(query)`.

### Dimension 4: Magic Numbers

#### TD4-01: `PhaseCorrelationAnalyzer._calculate_phase_coherence` hardcodes `nperseg=1024` regardless of sample rate
- **Severity**: LOW · **Dimension**: Magic Numbers · **Status**: NEW (the one site #4308 did not convert) · **Effort**: trivial
- **Location**: `auralis/analysis/phase_correlation.py:229-233`
- **Description**: `signal.welch(..., nperseg=1024)` ×2 and `signal.csd(..., nperseg=1024)`. The window spans 23 ms at 44.1 kHz but about 11 ms at 96 kHz. #4308 converted the 4 sibling sites to `frames_for_seconds()`. This is a metric-consistency issue, not audio corruption.
- **Related**: #4308, #4029 (closed); ENG-D2-03.
- **Suggested Fix**: `nperseg = frames_for_seconds(self.sample_rate, 1024 / 44100)`, as in `feature_extractor.py`.

#### TD4-02: `PlayerConfig.buffer_size` defaults to 4410, but the only production caller always passes 1024
- **Severity**: LOW · **Dimension**: Magic Numbers · **Status**: NEW · **Effort**: trivial
- **Location**: `auralis/player/config.py:20`; `auralis-web/backend/config/startup.py:855-863`; fallback `auralis/player/enhanced_audio_player.py:95` (`PlayerConfig()`)
- **Impact**: Latent. If the explicit argument is ever dropped, the realtime buffer silently grows from about 23 ms to 100 ms.
- **Related**: #4914, #4622 (closed; same "default disagrees with the only caller" shape).
- **Suggested Fix**: Make 1024 the default, or name a `REALTIME_BUFFER_SAMPLES` constant used by both sites.

### Dimension 6: Test Hygiene

#### TD6-02: `Integration.test.tsx` declares `vi.mock('@/contexts/WebSocketContext')` twice
- **Severity**: LOW · **Dimension**: Test Hygiene · **Status**: NEW · **Effort**: trivial
- **Location**: `auralis-web/frontend/src/components/__tests__/Integration.test.tsx:36-46` (dead) and `:136-149` (effective, #5005)
- **Description**: Mocks are keyed by path, so the first factory never takes effect. It also lacks the `unsubscribe` / `setResumePositionGetter` / `reissueActiveStreamAs` members that `PlaybackSessionProvider` needs.
- **Suggested Fix**: Delete the first block.

#### TD6-03: Six non-skipped test functions have a bare `pass` body
- **Severity**: LOW · **Dimension**: Test Hygiene · **Status**: NEW (not in #5225's print-only list) · **Effort**: small
- **Location**: `tests/backend/test_boundary_max_min_values.py:508,519,823`; `tests/backend/test_boundary_exact_conditions.py:411`; `tests/auralis/core/test_nan_detection.py:300,306`
- **Impact**: Illusory coverage. They report green for large-offset pagination, large-library search, concurrent adds, and NaN through filter and crossfade.
- **Related**: #5225, #5149 (open); #4767, #4046 (closed, same family).
- **Suggested Fix**: Write the described assertions, or convert to `pytest.mark.skip(reason="#NNNN …")`.

### Dimension 7: Stale Documentation

#### TDX-02: 453 source files carry a `:license: GPLv3` header; the project is AGPL-3.0
- **Severity**: LOW · **Dimension**: Stale Documentation · **Status**: NEW (closed #4327 covered only "GPL-3.0" in old `docs/releases/` notes) · **Effort**: small
- **Location**: 453 files: `auralis-web/backend` 116, `auralis/core` 76, `auralis/library` 74, `auralis-web/frontend` 49, `auralis/analysis` 41, `auralis/dsp` 31, others. Examples: `auralis/analysis/fingerprint/metrics/constants.py:8`, `auralis-web/backend/routers/library.py:25`
- **Description**: `LICENSE` is the GNU AGPL v3, and README and CLAUDE.md state AGPL-3.0 with a commercial dual license. Source docstrings say `:license: GPLv3, see LICENSE for more details.` and none say AGPL. 172 of the 453 files were **created after 2026-02-12** (e.g. `config/origins.py`, `core/chunk_batch.py`), so new modules keep copying the wrong header.
- **Evidence**: `grep -rlE "GPLv3|GPL v3|GNU General Public License v3" <src dirs>` → 453; the same grep for `AGPL` → 0.
- **Impact**: Every file contradicts the actual license terms. Reported as doc drift, not a legal opinion.
- **Suggested Fix**: One mechanical commit to `:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)`, plus a CI grep that rejects new `GPLv3` headers.

#### TDX-03: Backend CI still pins `pytest==9.0.1` for a conftest hook #4529 deleted
- **Severity**: LOW · **Dimension**: Stale Documentation · **Status**: NEW (#4529 lifted the ceiling in `pyproject.toml` but not in CI) · **Age**: comment `43c983ad` 2026-07-26; hook deleted `80d509b1` 2026-07-29 · **Effort**: trivial
- **Location**: `.github/workflows/backend-tests.yml:120-123`
- **Description**: The comment says "pytest MUST stay at 9.0.x: 9.1 removed the legacy pytest_ignore_collect(path, config) hook signature that tests/conftest.py still uses". `tests/conftest.py` no longer defines `pytest_ignore_collect`, and `pyproject.toml:86-92` records the deletion and verified collection on 9.1.1 (`pytest>=9.0.1`).
- **Impact**: A false "MUST" in the gate that decides the backend job. CI and a fresh dev environment run different pytest versions.
- **Related**: #4529 (closed), #4624 (open).
- **Suggested Fix**: Delete the comment and install a range matching `pyproject.toml` (e.g. `'pytest>=9.0.1,<10'`), or document a different reason for keeping 9.0.1. Regenerate `pytest-baseline.json` from CI if the version moves.

#### TD7-01: README "Run Tests" tells readers to run the whole `tests/` tree and undercounts it
- **Severity**: LOW · **Dimension**: Stale Documentation · **Status**: NEW · **Age**: last touched `750890d8` 2026-08-22 · **Effort**: trivial
- **Location**: `README.md:322-345`
- **Description**: It claims "roughly 5,400 backend … tests"; the live count is 6,759 (`check_doc_counts.py`). It uses `python -m pytest tests/ -v` and `--cov` on the whole tree with no `-m "not slow"` and no `--ignore` for the two files CLAUDE.md says hang.
- **Siblings**: `docs/development/TESTING_GUIDELINES.md:997-1001`.
- **Related**: the already-known drift where CLAUDE.md says CI ignores those two files but `backend-tests.yml` no longer does.
- **Suggested Fix**: Use CLAUDE.md's scoped command, and quote the count from `check_doc_counts.py`.

#### TD7-02: FIRST_TIME_SETUP.md recommends the REC-01-blocked launcher and promises "700+ tests in ~1-2 minutes"
- **Severity**: LOW · **Dimension**: Stale Documentation · **Status**: NEW · **Age**: `5393d122` 2025-12-17 · **Effort**: trivial
- **Location**: `FIRST_TIME_SETUP.md:146-181`
- **Description**: "Option A (**Recommended**)" is `python launch-auralis-web.py --dev`, which README.md:150-151 says is blocked by REC-01. The verify step runs the whole tree unscoped and claims a runtime CLAUDE.md says is "tens of minutes".
- **Suggested Fix**: Mirror README's two-terminal flow and the scoped test command; drop the runtime claim.

#### TD7-03: Two `docs/features/` guides still describe player fingerprinting as a gap or pending
- **Severity**: LOW · **Dimension**: Stale Documentation · **Status**: NEW · **Age**: `8525944b` 2026-07-09 (rename pass; content older) · **Effort**: trivial
- **Location**: `docs/features/PLAYER_FINGERPRINTING_GAP_ANALYSIS.md:1-11`, `docs/features/FINGERPRINT_SERVICE_INTEGRATION.md:1-12` (its "⏳ Pending: Integration into player code" checklist)
- **Evidence**: `auralis/player/enhanced_audio_player.py:24,119,159` imports and constructs `FingerprintService` and logs "fingerprinting enabled".
- **Suggested Fix**: Archive both with a superseded banner, as `docs/troubleshooting/PRESET_SWITCHING_LIMITATION.md` already has.

#### TD7-04: Backend `core/` docstrings credit consolidation from files that no longer exist
- **Severity**: LOW · **Dimension**: Stale Documentation · **Status**: NEW · **Age**: `ab6d6ef9` 2026-08-21 carried it forward · **Effort**: trivial
- **Location**: `auralis-web/backend/core/processor_factory.py:1-13,73-74,203-204` (`processor_manager.py: ProcessorManager`); `auralis-web/backend/core/audio_processing_pipeline.py:1-13,33-36` (`realtime_processor.py`)
- **Evidence**: `grep -rn ProcessorManager auralis auralis-web` → only these self-references; no `realtime_processor.py` in the tree (#4334).
- **Suggested Fix**: Drop the dead provenance lines, or point at `auralis/player/realtime/processor.py`.

#### TD7-05: `content_analysis_facade.py` comments compare against `get_parallel_processor`, which was deleted in #4565
- **Severity**: LOW · **Dimension**: Stale Documentation · **Status**: NEW · **Age**: `3ee8a956` 2026-07-27 · **Effort**: trivial
- **Location**: `auralis/core/analysis/content_analysis_facade.py:107,280`
- **Related**: #5207 (open: the facade itself has no production callers). If that issue deletes the file, this goes with it.
- **Suggested Fix**: Drop `get_parallel_processor` from both comments.

#### TDX-05: The `'any' non-test` census metric counts comment prose as type debt
- **Severity**: LOW · **Dimension**: Stale Documentation (audit metric definition) · **Status**: NEW · **Effort**: trivial
- **Location**: `.claude/commands/audit-tech-debt.md` Phase 1 (the `'any' non-test (ts)` grep)
- **Description**: The grep `':\s*any\b|as any|<any>'` matches English text in comments. 7 of today's 14 hits are prose: `responseGuards.ts:4`, `apiRequest.ts:79`, `useRestAPI.ts:23` ("`Promise<any>`"), `window.d.ts:5`, `useDropZone.ts:91`, `FingerprintCoverageCard.tsx:7` ("since before there was anywhere"), `QueuePanelExpanded.tsx:60` ("identity: any reorder"). The metric note tells readers to "Quote this one", so it overstates shipped `any` debt by 2x. This is the class #4564 asked to fix in the skill rather than by hand.
- **Suggested Fix**: Exclude comment lines in the grep (e.g. `grep -vE '^\S+:[0-9]+:\s*(\*|//|/\*)'`), or count with a TS-aware check (`@typescript-eslint/no-explicit-any` in report mode).

### Dimension 8: Backwards-Compat Cruft

#### TD8-01: `advanced_dynamics.py` re-exports four symbols "for backward compatibility" that nothing imports through it
- **Severity**: LOW · **Dimension**: Backwards-Compat Cruft · **Status**: NEW (not in DEP-INT-2's shim table) · **Age**: `134c74ae` 2026-09-03 (#5295) · **Effort**: trivial
- **Location**: `auralis/dsp/advanced_dynamics.py:20-38`
- **Evidence**: The only importers through this path (`hybrid_processor.py:19`, `hybrid/dynamics_manager.py:13`, `tests/regression/test_dynamics_processor_wiring.py:27`) import `DynamicsMode`, `DynamicsProcessor` and `create_dynamics_processor`. `AdaptiveCompressor`, `CompressorSettings`, `DynamicsSettings` and `EnvelopeFollower` are always imported from `auralis.dsp.dynamics`.
- **Related**: #5232, #5234, #5164 (the same shim shape, already filed).
- **Suggested Fix**: Remove the 4 names from the import block and `__all__`.

#### TD8-02: Duplicated breadcrumb comments about the `reason` field removed in #4975
- **Severity**: LOW · **Dimension**: Backwards-Compat Cruft · **Status**: NEW · **Age**: `3eade5b0` 2026-09-03 · **Effort**: trivial
- **Location**: `auralis-web/backend/routers/library_scan.py:249-254`; `auralis-web/backend/services/library_auto_scanner.py:395-397`
- **Description**: Both carry multi-line history of a field that is no longer sent (verified gone). The only present-tense content is "Fields here must match `LibraryUpdatedMessage`".
- **Siblings**: The `routers/library.py:14-22` module docstring narrates deleted duplicate routes (#3824) the same way.
- **Suggested Fix**: Keep the one contract sentence and drop the history.

### Dimension 9: File / Function / Module Complexity

Acceptance criterion for every split below (#4673): **close only when the target file is verified under 300 LOC with `wc -l`; otherwise re-scope and keep it open.**

#### TD9-01: Three closed god-file splits have regrown past their closing size
- **Severity**: LOW · **Dimension**: File/Function/Module Complexity · **Status**: NEW (regrowth after closure) · **Effort**: small per file
- **Location / history** (orchestrator-verified against closing comments and `git log`):
  - `auralis-web/backend/core/chunked_processor.py`: **319** LOC. #4245 closed 2026-08-22 at **297**. Regrown by `a105047f` (#4815, +12) and `8a23447b` (+10).
  - `auralis/player/enhanced_audio_player.py`: **311** LOC. #4249 closed 2026-08-22 at **299**. Regrown mainly by `727b39fd` (#5240, +17).
  - `auralis-web/backend/core/processing_engine.py`: **377** LOC. #4250 closed 2026-08-26 at **365**, by an explicit maintainer threshold decision (not a <300 close). Since grown by `824adf06` (#3886, +12).
- **Description**: Each fix that landed afterwards added lines to the coordinator rather than its established sibling family (`chunk_*`, `player_*_mixin.py`, `job_*`). Nothing gates LOC after close, so the "closed" state no longer matches the tree.
- **Suggested Fix**: Move 20–80 lines per file into the existing siblings (no new modules). For `processing_engine.py`, either re-affirm the 365-LOC waiver as the new ceiling or bring it under 300. Consider a LOC ratchet script like `check_pytest_baseline.py` for closed split targets.

#### TD9-02: `hybrid_processor.py` is 598 LOC; #4266 only moved the wrappers out
- **Severity**: LOW · **Dimension**: File/Function/Module Complexity · **Status**: NEW (#4266's scope was the wrapper move, which landed) · **Effort**: medium
- **Location**: `auralis/core/hybrid_processor.py` (one `HybridProcessor` class body, lines 49-553, plus `_apply_module_optimizations`)
- **Suggested Fix**: Split the class by responsibility (setup/validation, stage dispatch, result assembly), matching the coordinator/sibling pattern.

#### TD9-03: #4670's closure-factory fix skipped 9 routers, which still nest handlers in 122–288-line factories
- **Severity**: LOW · **Dimension**: File/Function/Module Complexity · **Status**: NEW (a gap #4670 left, not a regression) · **Effort**: large (one router per PR)
- **Location**: `routers/library_scan.py:40-327` (288, nested 4 levels: `create_library_scan_router` → `scan_library` → `_progress_callback` / `_enqueue_added`), `routers/settings.py:208-404` (197), `routers/fingerprint_queue.py:83-279` (197), `routers/tracks.py:58-231` (174), `routers/system.py:304-477` (174), `routers/artists.py:144-316` (173), `routers/fingerprint_status.py:58-203` (146), `routers/cache_streamlined.py:63-202` (140), `routers/library.py:88-209` (122). All paths are under `auralis-web/backend/`.
- **Impact**: No handler can be imported or unit-tested without building the whole closure, which blocks cross-cutting work such as the #3838 `response_model` rollout.
- **Suggested Fix**: Apply #4670's recipe: module-level handlers with `Depends()`, and the factory reduced to an `add_api_route` assembler under 30 LOC, with the `/openapi.json` path set unchanged.

#### TD9-04: `routers/player.py` (881) and `routers/processing_api.py` (861) are the largest untracked files
- **Severity**: LOW · **Dimension**: File/Function/Module Complexity · **Status**: NEW · **Effort**: medium
- **Description**: Both already have #4670's function-level fix. `player.py` mixes playback control, queue mutation and queue history; `processing_api.py` mixes upload, job status and parameter inspection. `routers/similarity.py` (517) is a smaller instance.
- **Suggested Fix**: Split `player.py` into `player.py`, `player_queue.py` and `player_queue_history.py` under the same prefix, and split `processing_api.py` the same way. Do this together with TD3-02 to avoid churning it twice.

#### TD9-05: `useLibraryQuery.ts` (575) and `useAudioStreamingCore.ts` (565) are the largest frontend hooks
- **Severity**: LOW · **Dimension**: File/Function/Module Complexity · **Status**: NEW (#5043 and #5041 are narrower and not size-based) · **Effort**: medium
- **Suggested Fix**: Move `useLibraryQuery`'s pure shaping functions into a co-located `.ts` module (this also closes #5043). Split `useAudioStreamingCore` by state domain (buffering, watchdog, position).

#### TD9-06: `schemas.py` (559) and `config/middleware.py` (542)
- **Severity**: LOW · **Dimension**: File/Function/Module Complexity · **Status**: NEW · **Effort**: small (middleware) / medium (schemas)
- **Suggested Fix**: `config/middleware/` with one file per middleware class (`NoCache`, `SecurityHeaders`, `RateLimit`, `OriginCheck`), with `setup_middleware()` as the single wiring point. Split `schemas.py` by domain and re-export from `schemas.py`.

#### TD9-07: `PlaylistList.tsx` juggles 4 concerns with 9 `useState` / `useEffect` calls
- **Severity**: LOW · **Dimension**: File/Function/Module Complexity · **Status**: NEW · **Effort**: small
- **Location**: `auralis-web/frontend/src/components/playlist/PlaylistList.tsx:59-87`
- **Suggested Fix**: Extract `usePlaylistData()`, and replace the three dialog/menu flags with one discriminated-union state.

#### TD9-09: Python function-length census: 76 functions over 100 LOC
- **Severity**: LOW · **Dimension**: File/Function/Module Complexity · **Status**: NEW (informational) · **Effort**: small–medium each
- **Description**: The functions fall into three groups. (1) The 9 router factories: TD9-03. (2) Six streaming handlers and pumps (183–257 LOC): #5032 deliberately deferred these, and its <300-file criterion is met, so leave them alone (see Deferred). (3) 61 one-offs, the largest being `compute_windowed_fingerprint` (297, `fingerprint/windowed_compute.py:133`), `scan_directories` (292, `scanner/scanner.py:137`), `load_with_ffmpeg` (230), `_render_to_sink` (209, `mastering_chunk_loop.py`), `_do_scan` (199), and `ContinuousMasteringBranch.apply` (197).
- **Suggested Fix**: Take group 3 opportunistically when the containing file gets its file-level split.

**Ranked table of non-test offenders (116 files: 88 py, 28 ts/tsx)**. Rows marked Existing already have an open split issue. The top 30:

| LOC | File | Split axis | Status |
|---|---|---|---|
| 1182 | `auralis-web/backend/config/startup.py` | init / teardown / tempfile reclamation | Existing: #5236 (grown from 1132 at filing) |
| 881 | `auralis-web/backend/routers/player.py` | playback / queue / queue-history | TD9-04 |
| 861 | `auralis-web/backend/routers/processing_api.py` | upload / job-status / parameters | TD9-04 |
| 837 | `auralis-web/backend/cache/manager.py` | eviction / recommendation cache / core | Existing: #5238 (grown from 713) |
| 749 | `auralis-web/backend/services/queue_service.py` | mutation / persistence-read | Existing: #5237 |
| 717 | `auralis-web/backend/routers/enhancement.py` | settings / prewarm / recommendation | NEW |
| 697 | `auralis-web/backend/routers/artwork.py` | fetch-download / thumbnail | NEW |
| 657 | `auralis-web/backend/routers/playlists.py` | CRUD / membership-ordering | NEW |
| 641 | `auralis-web/backend/routers/metadata.py` | single / batch | NEW |
| 598 | `auralis/core/hybrid_processor.py` | class body by stage | TD9-02 |
| 575 | `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts` | pure shaping / hooks | TD9-05 |
| 565 | `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts` | by state domain | TD9-05 |
| 559 | `auralis-web/backend/schemas.py` | by domain | TD9-06 |
| 542 | `auralis-web/backend/config/middleware.py` | one class per file | TD9-06 |
| 525 | `auralis/io/loaders/ffmpeg_loader.py` | subprocess / parsing | NEW |
| 524 | `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts` | by sub-domain | NEW |
| 523 | `auralis-web/backend/core/processor_factory.py` | by responsibility | NEW |
| 517 | `auralis-web/backend/routers/similarity.py` | similar-tracks / graph-stats | TD9-04 sibling |
| 517 | `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts` | by concern | NEW |
| 515 | `auralis-web/frontend/src/theme/themeConfig.ts` | by responsibility | NEW |
| 506 | `auralis/analysis/mastering_profile.py` | by metric family | NEW |
| 498 | `auralis-web/backend/ws_handlers/playback_commands.py` | by command family | NEW |
| 493 | `auralis-web/backend/websocket/outbound_messages.py` | by message family | NEW |
| 492 | `auralis/library/scanner/scanner.py` | orchestration / per-file | NEW |
| 492 | `auralis/core/recording_type_detector.py` | by metric family | NEW |
| 483 | `auralis-web/backend/services/library_auto_scanner.py` | lifecycle / scan | NEW |
| 483 | `auralis-web/backend/core/mastering_target_service.py` | by responsibility | NEW |
| 478 | `auralis-web/backend/routers/system.py` | health / WS / stream | TD9-03 |
| 469 | `auralis-web/frontend/src/utils/queue/queue_recommender.ts` | by concern | NEW |
| 462 | `auralis/player/gapless_playback_engine.py` | mixins by concern | NEW |

The remaining 86 offenders run from 462 down to 302 LOC. That includes `useReduxState.ts` (460, Existing: #5239) and the TD9-01 coordinators. Re-run the Dim 9 `find` commands to regenerate the full list; membership drifts, so it is intentionally not hardcoded.

---

## Deferred

| Finding | Gated on |
|---|---|
| TDX-04 (whole-library duplicate detection) | A product decision: expose it or delete it. |
| TD2-10 (`removeTrackFromPlaylist`) | A product decision on whether a remove-from-playlist UI should exist (frontend audit). |
| TD2-09 (`validatePCMSamples` / `clipPCMSamples`) | DSP/frontend judgement on whether a client-side PCM safety net is wanted (ENG-D1-01). |
| TD9-09 group 2 (streaming handler function length) | #5032's documented deferral of the semaphore/cancellation skeleton. Do not refactor opportunistically. |
| TD7-05 | #5207 (the facade may be deleted wholesale). |
| TD9-04 `player.py` split | Sequence after TD3-02 to avoid double churn. |

---

## Skipped as Existing (re-verified, not re-filed)

- **Dead code / unused surface**: #5207 (`content_analysis_facade.py` no production callers), #5204 (`is_same_artist`), #5205 (`sanitize_path_for_response`), BE-D10-03 (`TrackAnalysisCache` / `AnalysisExtractor` / `CacheMonitor`), ENG-D7-02 / INT-F9-04 (`QueueRepository`), ENG-D2-02 (PerformanceOptimizer mostly uncalled), FE-07 / FE-10 / FE-11 / FE-12 / FE-13 / FE-17 / FE-21 (frontend dead hooks and exports), BE-D4-01 (`JobWorker.cancel_task`).
- **Compat shims**: #4973 (`QueueHistoryRepository.undo` unused param), #5231 (`useKeyboardShortcuts` V1 API and stale preset shortcuts), #5232 (`queue_service.__all__` re-export), #5234 (`domain.ts` `formatDuration` re-export), #5164 (`PlayEnhanced` alias), #5245 (`ProcessingBranch` single-subclass ABC), DEP-INT-3 / 5 / 6 (token legacy aliases, base64 PCM transport, `_stream_type`).
- **Test hygiene**: #5224 (`check_weak_assertions.py` not in CI; 2 baseline entries now shrinkable), #5225 (23 print-only tests), #5149 (`tests/validation/` never collected), #5179 / #5186 (14 `describe.skip` integration suites).
- **Complexity**: #5236 (`startup.py`), #5238 (`cache/manager.py`), #5237 (`queue_service.py`), #5239 (`useReduxState.ts`). Note on #5236 and #5238: both files have grown since filing (1132→1182, 713→837).
- **Docs**: INT-F5-02 (`WEBSOCKET_API.md` fictitious `player_state` and removed presets, incl. `:637`), #5231 (`KEYBOARD_SHORTCUTS` preset list), the known CLAUDE.md claim that CI `--ignore`s `test_system_api.py` / `test_thread_safety.py`, ENG-D6-03 (`estimate_lufs` cites closed #4123).
- **Magic numbers**: #5223, #4622, #4924, #4914, #4029. All fixes are still in place, and the `sample_rate=44100` count holds at 30.

## Checked and Clean (summary)

- **Markers**: 0 in shipped code. The 3 in `tests/` all cite OPEN issues.
- **Stubs (Dim 5)**: The AST sweep over `auralis/` and `auralis-web/backend/` found only Protocol / `@overload` / ABC bodies with real implementers, the documented `_unavailable()` DI default, and the `PLACEHOLDER_LUFS_SENTINEL` design. No reachable stub.
- **Mastering stages**: All 13 in `auralis/core/stages/` share the `no_op()` (`audio.copy()`) and `ParallelEQUtilities` scaffolding. No copy or sample-count guard divergence, so no HIGH candidate.
- **Imports and ignores**: `ruff --select F401,F811` is clean. `mypy --warn-unused-ignores` over all 30 files with `# type: ignore` reports 0 stale. Rust has 0 `allow(dead_code)`.
- **Config homes**: Chunk geometry lives only in `chunk_boundaries.py`, and backend limits and env config are consolidated. Frontend hex colours: every raw hit is inside a history comment.
- **Variant pairs**: `unified_loader.py` vs `loader.py`, `simple_mastering.py` vs `HybridProcessor`, `advanced_dynamics.py` vs `dsp/dynamics/`, and the `useEnhanced*` hooks are all legitimate distinct roles. The DB migration chain v0→v18 is required for desktop users on old schemas.
- **Skips**: Every skip, skipif or xfail citing an issue cites an open one, or is an environment gate added with a closed fix. The #4969 narrowing is intact at all 13 sites. All "must not regress" tests named in the skills are present and unskipped.
- **Docs and skills (Dims 7, 10)**: Versions agree at 1.5.1. CLAUDE.md map spot-checks (schema v18, 13 repos, `optimization/` subdirs, hook dirs) match. Every hardcoded count in the skill files matches the live tree: 57 backend `core` modules, 26 router files, 19 `.rs` files, 11 PyO3 functions, 13 stages, 9 hook subdirs, "all 10" dimensions. All 51 `#NNNN` callouts in `.claude/` are closed and cited historically. No `docs/audits/` report is older than 90 days. No skill claims the frontend ratchet has `--strict-stale`, consistent with FE-02.

---

*Suggested next step:* `/audit-publish docs/audits/AUDIT_TECH_DEBT_2026-09-13.md`
