# Tech-Debt Audit — 2026-07-06

Full re-audit of accumulated technical debt across `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/`, `tests/`, and `docs/`, per `.claude/commands/audit-tech-debt.md` (all 10 dimensions, `--depth deep`, no `--limit`). This is a fresh pass — every finding below was re-derived from current source, not carried over from `docs/audits/AUDIT_TECH_DEBT_2026-05-30.md`. Ten dimension agents ran (max 3 concurrent), each performing its own dedup pass against `gh issue list` (141 open issues) and the tech-debt-labeled issue history (93 open+closed) before reporting.

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 5 |
| LOW | 74 |
| **Total NEW/Regression findings** | **79** |

No CRITICAL or HIGH findings — consistent with tech-debt findings defaulting to LOW per `_audit-severity.md`, with only 5 clearing a promotion trigger (divergent-fix-history or reachable-stub) to MEDIUM. Zero findings needed the HIGH audio-integrity/truncation floor this run.

By dimension (NEW/Regression only; "Existing: #NNN" and "Skipped as duplicate/closed" items excluded from these counts):

| # | Dimension | NEW/Regression | MEDIUM | LOW |
|---|---|---|---|---|
| 1 | Stale Markers | 1 | 0 | 1 |
| 2 | Dead Code & Unused Surface | 14 | 0 | 14 |
| 3 | Logic Duplication | 8 | 2 | 6 |
| 4 | Magic Numbers & Hardcoded Constants | 6 | 1 | 5 |
| 5 | Stub & Placeholder Implementations | 5 | 1 | 4 |
| 6 | Test Hygiene | 11 | 0 | 11 |
| 7 | Stale Documentation & Comments | 6 | 0 | 6 |
| 8 | Backwards-Compat Cruft & "No Variants" | 8 | 0 | 8 |
| 9 | File/Function/Module Complexity | 19 | 0 | 19 |
| 10 | Audit-Finding Rot | 1 | 1 | 0 |
| | **Total** | **79** | **5** | **74** |

**Direction since 2026-05-30**: every dedup'd dimension confirmed its prior batch of fixes is holding (2026-05-30 tech-debt findings verified fixed, not regressed — full detail in each dimension's "Skipped as duplicate/closed" section), with two partial-fix exceptions caught this pass: **TD3-1** (the `BaseRepository._session_scope()` helper added for #4017 was never adopted by any of the 14 repositories) and **TD8-1** (Regression of #4088 — 2 of 3 named sibling breadcrumb comments were never deleted, plus 1 new instance found). Net new debt surfaced this pass is dominated by Dimension 9 (file-size curation, 19 newly-named oversized files not yet tracked) and Dimension 2 (14 dead-code items, mostly small/trivial).

## Baseline Snapshot

Phase-1 mechanical counts, current run vs. the 2026-05-30 audit's snapshot (lower is better for all rows):

| Metric | 2026-05-30 | 2026-07-06 | Δ |
|---|---|---|---|
| TODO/FIXME/HACK/XXX (py) | 0 | 0 | — |
| TODO/FIXME/HACK/XXX (ts) | 2 | 1 | **-1** |
| NotImplementedError | 2 | 1 | **-1** |
| `type: ignore` (py) | 162 | 158 | **-4** |
| `@ts-ignore`/`@ts-expect-error` | 2 | 2 | — |
| `: any` / `as any` (ts) | 557 | 557 | — |
| Skipped tests (py) | 90 | 61 | **-29** |
| Skipped tests (ts) | 3 | 3 | — |
| Py files >300 LOC | 107 | 106 | **-1** |
| TS/TSX files >300 LOC | 173 | 158 | **-15** |
| `allow(dead_code)` (rust) | 0 | 0 | — |

Path-reference validate gate (`.claude/commands/_audit-validate.sh`): **PASS** — 167 refs across 25 skill files, 0 STALE (re-confirmed twice during this run, in Phase 1 and again during Dimension 7/10).

Every metric moved in the improving direction or held steady; none regressed. The 29-test drop in skipped Python tests and 15-file drop in oversized TS/TSX files reflect real cleanup landed since 2026-05-30 (confirmed via the dimension agents' regression checks, not just the raw count).

## Top 10 Quick Wins

Trivial/small effort, immediate readability or build-hygiene payoff:

1. **TD10-1** (MEDIUM) — Fix `audit-suite.md`'s "7 audits" → "8 audits" in 3 places (line 91, 123, 160); the `comprehensive` preset already lists 8 steps. Prevents a future audit run from under-counting background agents and silently dropping `/audit-tech-debt`.
2. **TD8-1** (LOW) — Delete 3 leftover `# REMOVED`/`// Removed:` breadcrumb comments (`realtime_dsp_pipeline.py:92`, `design-system/animations/index.ts:193`, `proactive_buffer.py:114-123`) — 2 are a regression of the "fixed" #4088, 1 is new.
3. **TD2-1** (LOW) — Delete 58 stale `# type: ignore` comments across 20 files (mostly 2 dense clusters: `library/models/*.py` class decorators, `library/repositories/*.py` attribute assignments); `mypy --warn-unused-ignores` gives the exact line list, purely mechanical.
4. **TD6-2** (LOW) — Delete `test_summary_stats()`-style print-only, zero-assertion functions across 29 test files; they add no verification value and at least one file's hand-typed count has already drifted from reality.
5. **TD8-4** (LOW) — Delete the dead `QueueManager = QueueController` compat alias in `enhanced_audio_player.py:36-38` — zero callers, and it name-collides with the real, actively-used `QueueManager` class in `components/queue_manager.py`.
6. **TD8-6** (LOW) — Delete `routers/dependencies.py::require_library_manager` — a `DeprecationWarning`-emitting shim with zero call sites anywhere in the codebase.
7. **TD2-12/TD2-13/TD2-14** (LOW) — Delete 4 unused imports in one pass: `scipy.signal.butter/sosfilt` (`simple_mastering.py:18`), redundant local `import numpy as np` (`chunk_boundaries.py:239`), unused `os` in a local `import tempfile, os` (`fingerprint_service.py:263`).
8. **TD2-10/TD2-11** (LOW) — Delete the dead Rust `detect_isr_peaks` method (`limiter.rs:111-127`, superseded by `oversample()`) and 2 unused imports (`yin.rs:14`'s `PI` → move into its `#[cfg(test)]` block; `chunk_processor.rs:7`'s `Axis` → remove).
9. **TD6-7** (LOW) — Exclude `TEMPLATE.test.tsx` from the vitest glob (rename or add to `exclude`) — ~10 commented-out-body tests currently collect and pass trivially.
10. **TD4-1** (LOW) — Delete the redundant `MAX_LEVEL_CHANGE_DB = 1.5` redeclaration in `chunked_processor.py:97` (it just re-supplies `LevelManager`'s own default) — one-line fix, closes a drift risk the 2026-05-30 chunk-constant consolidation missed.

## Top 5 Medium Investments

File/function splits and duplication consolidations with the highest payoff-to-effort ratio:

1. **TD5-1** (MEDIUM, medium effort) — `useBatchOperations.ts` "Add to playlist" and non-favourites "Remove" are stub toasts (`info('Coming soon!')`) wired into the shipped library multi-select toolbar. Backend already supports add-to-playlist (`POST /api/playlists/{id}/tracks`); wire a playlist-picker modal. Library-remove has no backend route yet — needs one or the button hidden outside favourites.
2. **TD3-2** (MEDIUM, small effort) — `AlbumRepository`/`ArtistRepository` sibling lookup methods (`get_by_id` vs `get_by_title`/`get_all`/`get_recent`; `get_by_id` vs `get_by_name`) received a targeted `DetachedInstanceError` fix (#2406) or nested eager-load that was never copied to the sibling method. Extract named `_FULL_OPTIONS` eager-load constants and standardize `session.expunge_all()` across every method that returns eagerly-loaded relationships.
3. **TD3-3** (MEDIUM, small effort) — Three DSP mode processors (`hybrid_mode.py`, `adaptive_mode.py`, `continuous_mode.py`) each hand-roll their own final normalize/safety-limit preamble; only `hybrid_mode.py` got the `validate_audio_finite(..., repair=True)` NaN/Inf guard from #3429. `AdaptiveMode`'s un-fixed path is reachable from `HybridMode`'s own no-reference fallback. Extract a shared `finalize_and_normalize()` helper in `processing/base.py`.
4. **TD3-1** (LOW severity but foundational, medium effort) — `BaseRepository._session_scope()` was added (closed #4017) specifically to collapse the `session = self.get_session(); try/finally: close()` boilerplate, but none of the 14 repositories (111 manual call sites) has been migrated to use it. Migrate the read-only call sites first, starting with `track_repository.py` (21 sites) and `fingerprint_repository.py` (16 sites).
5. **TD9-1** (LOW severity, large effort) — `chunked_processor.py` (958 lines) mixes chunk metadata/path resolution, crossfade/level-smoothing math, hybrid-processor invocation, and mastering-recommendation logic across 3 overlapping `process_chunk*` entry points. Extract crossfade math to `chunk_crossfade.py`, mastering-recommendation logic to its own module, and collapse the three process-chunk entry points into one method with a `locked: bool` parameter. Pairs naturally with the already-open #4071 (`audio_stream_controller.py` split) as one streaming-subsystem cleanup pass.

---

## Findings

### MEDIUM Severity (5)

#### Dimension 10: Audit-Finding Rot

##### TD10-1: `audit-suite.md` "comprehensive" preset mislabeled "(7 audits)" — actually lists 8
- **Severity**: MEDIUM
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/audit-suite.md:26-36` (preset list), `:91`, `:123`, `:160`
- **Status**: NEW
- **Age**: `1b7b5135` 2026-05-30 (added step 8, `/audit-tech-debt`, to the numbered list without updating the three "7" callouts elsewhere)
- **Effort**: trivial
- **Description**: The `comprehensive` preset numbers its steps 1–8 (ending `/audit-tech-debt`), but three prose statements in the same file still say "7 audits" / "7 Agent tool calls" / "launches 7 audits in parallel."
- **Evidence**: Lines 91, 123, 160 all say "7"; the preset list itself (lines 26-36) has 8 numbered entries.
- **Impact**: An operator following the "7" prose literally could launch only 7 steps and silently drop `/audit-tech-debt`, or under-count how many background agents to wait for.
- **Siblings**: No other preset in the file has this mismatch (`pre-release` 3/3, `post-sprint` 2/2, `security-deep` 3/3, `audio-deep` 3/3 all check out); other skill files' dimension counts (`audit-tech-debt.md` "all 10", `audit-integration.md` "7 flows", `audit-security.md` "OWASP Top 10") are all consistent.
- **Related**: None open on GitHub.
- **Suggested Fix**: Change "(7 audits)" → "(8 audits)" at line 91, "7 Agent tool calls" → "8 Agent tool calls" at line 123, "launches 7 audits" → "launches 8 audits" at line 160.

#### Dimension 3: Logic Duplication

##### TD3-2: `AlbumRepository`/`ArtistRepository` — a correctness fix applied to one lookup method never propagated to its near-identical sibling
- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis/library/repositories/album_repository.py:32-63` (`get_by_id` vs `get_by_title`) and `:65-119` (`get_all`/`get_recent`); `auralis/library/repositories/artist_repository.py:21-61` (`get_by_id` vs `get_by_name`)
- **Status**: NEW
- **Age**: `7773f45c` 2026-02-20 (Album `expunge_all()` fix, #2406); `6742dc53`/`dfc6533a` 2026-03-01/02 (Artist `get_by_name`, never matched to `get_by_id`)
- **Effort**: small
- **Description**: `AlbumRepository.get_by_id` calls `session.expunge_all()` with a comment citing the fix for #2406 ("Expunge the album AND all eagerly-loaded related objects... without hitting DetachedInstanceError"). `get_by_title`, `get_all`, `get_recent`, and `search` still only call `session.expunge(album)` (top-level only, not cascaded). `ArtistRepository.get_by_id` eager-loads `selectinload(Artist.albums).selectinload(Album.tracks)` (nested); `get_by_name` eager-loads only `selectinload(Artist.albums)` — this gap predates and was missed by a later (`aaf9d02c`) fix pass that touched both methods for an unrelated field.
- **Evidence**:
  ```python
  # album_repository.py:41-46 (get_by_id — has the fix)
  session.expunge_all()   # fixes #2406
  # album_repository.py:59-61 (get_by_title — sibling, no fix)
  session.expunge(album)
  ```
- **Impact**: A caller fetching an album via `get_by_title`/`get_all`/`get_recent`/`search` and then accessing a relationship reachable only through the un-cascaded `tracks` collection risks the exact `DetachedInstanceError` #2406 fixed for `get_by_id`. Symmetrically for `ArtistRepository.get_by_name` + `artist.albums[i].tracks`. This is the "one copy fixed, the other still carries the bug" pattern the audit's promotion table floors at MEDIUM.
- **Siblings**: Album: 4 methods missing `expunge_all()`; Artist: 1 method missing the nested eager-load.
- **Related**: Potential live bug for `/audit-engine`/`/audit-backend` if any router path calls the un-fixed methods and touches the un-cascaded relationship — not confirmed via a traced call site, flagged as risk.
- **Suggested Fix**: Extract named eager-load option constants (`AlbumRepository._FULL_OPTIONS`, `ArtistRepository._FULL_OPTIONS`) shared by every lookup method; standardize on `session.expunge_all()` for every method returning eagerly-loaded relationships.

##### TD3-3: Three DSP "mode processor" siblings duplicate the final normalize/safety preamble, but only one got the NaN/Inf repair fix (#3429)
- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/processing/hybrid_mode.py:104-109` (has the fix) vs `auralis/core/processing/adaptive_mode.py:237-327` (`_apply_final_normalization`, no fix) and `auralis/core/processing/continuous_mode.py:670-710` (narrower, independent mitigation)
- **Status**: NEW
- **Age**: `791de0ec` 2026-03-25 ("fix: validate audio finite before normalize in HybridMode (#3429)")
- **Effort**: small
- **Description**: `HybridMode._apply_hybrid_processing()` calls `validate_audio_finite(blended_audio, context="hybrid_mode blend", repair=True)` before `normalize()`, citing #3429 ("normalize() would propagate NaN/Inf silently"). `AdaptiveMode._apply_final_normalization()` — the same "makeup gain → peak-normalize → safety-limit" final stage, also used as `HybridMode`'s own no-reference fallback (`hybrid_mode.py:66-68`) — has zero `validate_audio_finite` calls anywhere in `adaptive_mode.py`. `ContinuousMode` has a narrower, independently-invented silence/`-inf`-only guard (#4104) that doesn't cover the general case.
- **Evidence**: `grep -c validate_audio_finite auralis/core/processing/adaptive_mode.py` → 0. The downstream safety net in `hybrid_processor.py:361` validates with `repair=False` (raises rather than heals) — i.e. a NaN/Inf source reaching pure-adaptive processing crashes instead of self-healing, the opposite of what #3429 achieved for the hybrid blend.
- **Impact**: `HybridMode`'s "no reference provided" branch delegates straight to `AdaptiveMode.process()` — the un-fixed path is reachable from the same call site the fix targeted, just via a different mode selection. Audio-integrity sensitive; floored at MEDIUM per the divergent-DSP-fix promotion rule.
- **Siblings**: `continuous_mode.py:670-710`'s independently-written narrower guard reinforces this preamble is maintained three separate times.
- **Related**: `/audit-engine` — potential live crash-vs-silent-corruption divergence in the adaptive-only path; not confirmed to be actively triggered.
- **Suggested Fix**: Extract a shared `finalize_and_normalize(audio, target_peak, context) -> np.ndarray` helper (e.g. in `processing/base.py`, which already houses `NormalizationStep`/`PeakNormalizer`/`SafetyLimiter`) performing the `validate_audio_finite(..., repair=True)` guard once; all three mode processors' final stage calls it instead of hand-rolling.

#### Dimension 4: Magic Numbers & Hardcoded Constants

##### TD4-3: `cache/manager.py` `CHUNK_SIZE_MB` byte-budget estimate doesn't match its own documented derivation
- **Severity**: MEDIUM
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/cache/manager.py:31-39, 303, 405-406`
- **Status**: NEW
- **Effort**: small
- **Description**: `CHUNK_SIZE_MB = 1.5` is commented "estimated size per chunk (stereo 44.1kHz, float32)". Actual PCM math for a `CHUNK_DURATION=15`s stereo float32 chunk is `2 × 44100 × 15 × 4 ≈ 5.05 MB` — over 3× the constant. This estimate (not a measured size) is the sole input to `TIER1_MAX_SIZE_MB`/`TIER2_MAX_SIZE_MB` budget math and the live eviction-trigger checks at lines 303 and 405-406.
- **Evidence**:
  ```python
  CHUNK_SIZE_MB = 1.5    # estimated size per chunk (stereo 44.1kHz, float32)
  tier2_size_mb = len(self.tier2_cache) * CHUNK_SIZE_MB   # count-based estimate, not measured bytes
  ```
- **Impact**: The module docstring promises Tier 2 "60-120 MB"; if real per-chunk memory is ~3.4× the estimate, actual RSS for a fully warm-cached track can silently be ~3x the documented ceiling before the size-based eviction logic believes it's under budget.
- **Siblings**: None — the sibling `chunk_cache_manager.py` (`MAX_CHUNK_DISK_BYTES`) enforces its cap via a real on-disk byte scan, not an estimate.
- **Related**: None filed for this specific mismatch.
- **Suggested Fix**: Derive `CHUNK_SIZE_MB` from `CHUNK_DURATION` and the actual output dtype/channel count, or switch tier-size accounting to real measured sizes like `chunk_cache_manager.py` already does.

#### Dimension 5: Stub & Placeholder Implementations

##### TD5-1: `BatchActionsToolbar` "Add to playlist" and non-favourites "Remove" are stub toasts wired into the shipped library view
- **Severity**: MEDIUM
- **Dimension**: Stub Implementations
- **Location**: `auralis-web/frontend/src/components/library/useBatchOperations.ts:63-65,85-87`
- **Status**: NEW
- **Age**: `b197637ea` 2025-11-23
- **Effort**: medium
- **Description**: `useBatchOperations` is consumed by `CozyLibraryView.tsx:220-229`, rendering `<BatchActionsToolbar>` whenever tracks are multi-selected in Songs/Recent/Favorites views. `handleBulkAddToPlaylist` unconditionally shows `info('Bulk add to playlist - Coming soon!')` with no API call; `handleBulkRemove`'s non-favourites branch shows `info('Bulk delete from library requires API implementation')` and does nothing. Both are reachable from a real, discoverable shipped UI action.
- **Evidence**:
  ```ts
  const handleBulkAddToPlaylist = useCallback(async () => {
    info('Bulk add to playlist - Coming soon!');
  }, [info]);
  ```
  Backend check: `routers/playlists.py` DOES expose `POST /api/playlists/{playlist_id}/tracks` (add-track is buildable today); `routers/tracks.py` has no track-deletion route at all (library-remove has no backend counterpart yet).
- **Impact**: Two of four buttons in a shipped bulk-action toolbar are silent no-ops disguised as toasts. Reachable from a shipped UI action → promoted per the Dim-5 rule.
- **Siblings**: None found with an identical "toast-only" pattern elsewhere in `hooks/`.
- **Related**: Distinct from closed #4040 (`usePlaylistContextActions.onPlay`) and open #3805 (`useQueueHistory` dead endpoints).
- **Suggested Fix**: For "Add to playlist": add a playlist-picker modal calling the existing add-track route per selected track. For "Remove" in the library context: implement a `DELETE /api/library/tracks/{track_id}` route + wire it, or gate the button so it isn't rendered outside the favourites context until the backend exists.

---

### LOW Severity (74)

#### Dimension 1: Stale Markers (1)

##### TD1-1: Stale "TODO: re-implement artwork management" comment in AlbumCard.tsx — the feature already exists as orphaned sibling code
- **Severity**: LOW
- **Dimension**: Stale Markers
- **Location**: `auralis-web/frontend/src/components/album/AlbumCard/AlbumCard.tsx:11-12,45-46`
- **Status**: NEW
- **Age**: `4f1030c58` 2025-12-27 (~7 months old)
- **Effort**: small
- **Description**: The docstring says artwork management was "temporarily removed" with a TODO to re-implement it via `MediaCard` extension. A full second implementation of exactly this feature (`ArtworkContainer.tsx`, `useArtworkHandlers.ts`, `NoArtworkButtons.tsx`, `LoadingOverlay.tsx`, `ArtworkMenu.tsx`, `ArtworkMenuButton.tsx`, `ArtworkSquareContainer.tsx`) already lives in the same directory, barrel-exported, but has zero consumers outside the directory.
- **Evidence**: `grep -rln "AlbumCard/ArtworkContainer\|AlbumCard/useArtworkHandlers" auralis-web/frontend/src` → no hits; `MediaCard` never references any of them.
- **Impact**: A developer may re-implement the feature a third time, or spend time evaluating whether to wire up `ArtworkContainer` without realizing it's already fully built. Inflates `AlbumCard/` with ~7 files of dead weight.
- **Siblings**: The dead-code sibling set: 7 files listed above, all barrel-exported via `AlbumCard/index.ts` with no external consumer.
- **Related**: No open/closed issue references this. Route the dead-code half to Dimension 2.
- **Suggested Fix**: Decide the feature's fate: wire `ArtworkContainer`+`useArtworkHandlers` into `AlbumCard.tsx` if still wanted, or delete the orphaned sibling set and rewrite the docstring, either way removing the stale "future iteration" comment.

#### Dimension 2: Dead Code & Unused Surface (14)

##### TD2-1: 58 stale `# type: ignore` comments across 20 files — underlying mypy errors no longer exist
- **Severity**: LOW | **Effort**: small
- **Location**: 20 files; densest clusters `auralis/library/models/core.py` (9), `auralis/library/repositories/queue_repository.py` (9), `album_repository.py` (5), `queue_history_repository.py` (5), `settings_repository.py` (4), plus singles across `auralis/io/unified_loader.py`, `auralis-web/backend/player_state.py`, `services/library_auto_scanner.py`, `core/mastering_target_service.py`, `core/chunked_processor.py`.
- **Status**: NEW
- **Description**: Two dominant patterns: (1) `class Track(Base, TimestampMixin):  # type: ignore[misc]` on 8 declarative-model classes — mypy no longer reports `[misc]` there; (2) `column_attr = value  # type: ignore[assignment]` across 6 repository files — mypy now resolves `Mapped[...]` correctly.
- **Evidence**: `mypy auralis/ auralis-web/backend/ --ignore-missing-imports --warn-unused-ignores` emits `Unused "type: ignore" comment` at all 58 locations.
- **Impact**: Hides that mypy's signal-to-noise has improved; a genuinely-broken assignment on these lines is now silently protected by the leftover ignore.
- **Related**: Distinct from open #4028 (`[unreachable]` tag cluster — different sites, different tag).
- **Suggested Fix**: Run `mypy --warn-unused-ignores` in CI; delete the 58 trailing comments, starting with the two dense clusters.

##### TD2-2: 5 entire `auralis/analysis/` modules (1,660 lines) have zero call sites anywhere in the repo
- **Severity**: LOW | **Effort**: medium
- **Location**: `continuous_target_generator.py` (333L), `profile_versioning.py` (310L), `profile_matcher.py` (332L), `auralis_integration.py` (259L), `batch_analyzer.py` (426L)
- **Status**: NEW | **Age**: added 2025-10-26 through 2025-11-27, mechanically touched 2026-02-13
- **Description**: Each file's public class/function has zero references anywhere else; `auralis/analysis/__init__.py` doesn't re-export any of them.
- **Evidence**: `grep -rn "ProfileVersionManager\|ProfileMatcher\|AuralisAdaptiveMasteringBridge\|BatchAnalyzer\|ContinuousTargetGenerator" auralis auralis-web tests` → no hits outside own files.
- **Impact**: 1,660 dead lines in the largest module (81 files) get dragged through every mechanical repo-wide refactor for no benefit.
- **Suggested Fix**: Delete all 5 files; extract intent to a design note first if the ideas are worth reviving.

##### TD2-3: Frontend export/streaming "infrastructure" services — 2,540 lines with only test-file consumers
- **Severity**: LOW | **Effort**: large
- **Location**: `services/AnalysisExportService.ts` (897L), `utils/exportInfrastructure.ts` (525L), `services/RealTimeAnalysisStream.ts` (628L), `utils/streamingInfrastructure.ts` (490L)
- **Status**: NEW | **Age**: `AnalysisExportService.ts` actively maintained as recently as `89853f0e` 2026-06-28 (#4039)
- **Description**: `AnalysisExportService.ts`/`RealTimeAnalysisStream.ts` are imported only by their own test files; the other two are imported only by these two dead services.
- **Evidence**: `grep -rln "from .*services/AnalysisExportService" src/` → only its own `__tests__` file.
- **Impact**: 2,540 lines of untriggered code with matching test suites give a false coverage signal; #4039 shows real engineering time was recently spent hardening dead code.
- **Related**: **Conflicts with open #4078** (proposes splitting `AnalysisExportService.ts` assuming it's live) — resolve #4078 as "superseded" if this is confirmed dead, rather than doing both.
- **Suggested Fix**: Confirm with the user whether an export/stream feature was planned but never wired up; delete all 4 files + tests if truly unused.

##### TD2-4: `useVisualizationOptimization` + `performanceOptimizer.ts` — 1,280-line hook/util pair with zero component consumers
- **Severity**: LOW | **Effort**: medium
- **Location**: `hooks/shared/useVisualizationOptimization.ts` (424L), `utils/performanceOptimizer.ts` (856L), re-exported via `hooks/shared/index.ts:13`
- **Status**: NEW
- **Description**: Exported through the `hooks/shared` barrel but no component or page imports it; `performanceOptimizer.ts` is imported only by this dead hook.
- **Evidence**: `grep -rln "useVisualizationOptimization" src/ | grep -v __tests__` → only the hook's own file and the barrel.
- **Impact**: Re-export through `index.ts` with no consumer — inflates the barrel's apparent surface.
- **Suggested Fix**: Remove the barrel re-export first (reversible signal-check); delete both files if nothing breaks.

##### TD2-5: `HybridProcessor.process()` threads `preview_target`/`preview_result` to `_process_impl()` and silently drops them; the module they'd call is otherwise dead
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis/core/hybrid_processor.py:206-280`, `auralis/utils/preview_creator.py` (75 lines, whole file), `auralis/core/config/unified_config.py:49,51-52,121,123-128`
- **Status**: NEW | **Age**: `preview_creator.py` added 2025-09-14
- **Description**: `process()`/`_process_impl()` accept `preview_target`/`preview_result` but never forward them into any of the three mode-processing methods; no caller anywhere passes these kwargs. `preview_creator.py::create_preview()` has zero callers itself.
- **Evidence**: `grep -rn "preview_target\s*=\|preview_result\s*=" auralis auralis-web tests | grep -v hybrid_processor.py` → none.
- **Impact**: Dead parameter surface; flagged as `Related` to `/audit-engine` in case an A/B-preview feature is meant to be wired up.
- **Suggested Fix**: Delete `preview_creator.py`, the `preview_target`/`preview_result` params, and the three `preview_*` `UnifiedConfig` fields together.

##### TD2-6: `get_engineer_profile()` accessor in `reference_library.py` is dead — callers read `ENGINEER_PROFILES` directly
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/learning/reference_library.py:399-401`
- **Status**: NEW
- **Description**: No caller anywhere imports or calls `get_engineer_profile`; the module's own demo block reads the dict directly.
- **Evidence**: `grep -n "get_engineer_profile" auralis auralis-web tests -r` → only the definition.
- **Suggested Fix**: Delete the function.

##### TD2-7: `compare_albums()` in `mastering_fingerprint.py` — dead trailing function in an otherwise-live file
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/analysis/mastering_fingerprint.py:267-315`
- **Status**: NEW
- **Description**: `MasteringFingerprint`/`analyze_album()` in the same file are heavily used; `compare_albums` has no callers anywhere.
- **Suggested Fix**: Delete the function, or track the "compare two masters" intent as a real issue if wanted later.

##### TD2-8: `PresetParameters` / `get_preset_parameters()` — dead fixed-preset module that contradicts its own "no fixed presets" docstring
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/core/processing/preset_parameters.py` (125 lines, whole file)
- **Status**: NEW
- **Description**: Docstring states "All mastering is adaptive - no fixed presets," yet the file implements exactly that, with zero callers.
- **Evidence**: `grep -rn "PresetParameters\|get_preset_parameters" auralis auralis-web tests | grep -v preset_parameters.py` → none.
- **Suggested Fix**: Delete the file.

##### TD2-9: `auralis/dsp/utils/__init__.py` re-exports 3 functions with zero callers anywhere
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/dsp/utils/__init__.py:11-16,48-79`; defs at `adaptive.py:52`, `audio_info.py:85`, `conversion.py:27`
- **Status**: NEW
- **Description**: `psychoacoustic_weighting`, `count_max_peaks`, `from_db` are all re-exported in `__all__` but never called anywhere (unlike sibling `to_db`, 28 call sites).
- **Suggested Fix**: Delete the 3 unused functions/re-exports, or add a comment noting intentional API symmetry if kept.

##### TD2-10: Rust `detect_isr_peaks` — private method never called (limiter.rs)
- **Severity**: LOW | **Effort**: trivial
- **Location**: `vendor/auralis-dsp/src/limiter.rs:111-127`
- **Status**: NEW
- **Description**: `cargo build --lib` reports this private method never used; `oversample()` right below it is the live inter-sample-peak mitigation.
- **Suggested Fix**: Delete `detect_isr_peaks` (16 lines).

##### TD2-11: Rust unused imports — `PI` (yin.rs) only needed by tests, `Axis` (chunk_processor.rs) needed nowhere
- **Severity**: LOW | **Effort**: trivial
- **Location**: `vendor/auralis-dsp/src/yin.rs:14`, `vendor/auralis-dsp/src/chunk_processor.rs:7`
- **Status**: NEW
- **Suggested Fix**: Move `PI` import inside `#[cfg(test)] mod tests`; remove `Axis` from the `chunk_processor.rs` import list.

##### TD2-12: `scipy.signal.butter`/`sosfilt` imported but unused in `simple_mastering.py`
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/core/simple_mastering.py:18`
- **Status**: NEW
- **Related**: Existing: #4072 (file-size split) — fold this one-line fix into that pass.
- **Suggested Fix**: Delete the unused import.

##### TD2-13: Redundant local `import numpy as np` shadows the module-level import in `chunk_boundaries.py::trim_context`
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:239`
- **Status**: NEW
- **Related**: Existing: #3883 (different method, different problem — not a duplicate).
- **Suggested Fix**: Delete the local import on line 239.

##### TD2-14: Local `os` import unused within its own scope in `fingerprint_service.py`
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:263`
- **Status**: NEW
- **Suggested Fix**: Change `import tempfile, os` to `import tempfile`.

#### Dimension 3: Logic Duplication (6 LOW; 2 MEDIUM listed above)

##### TD3-1: `BaseRepository._session_scope()` was added to close a duplication finding, but zero of the 14 repositories use it
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis/library/repositories/base.py:35-52` vs `*.py` (111 manual call sites)
- **Status**: NEW (the duplication #4017 aimed to close is materially unresolved — not a regression, the adoption step was simply never done)
- **Age**: `0f0fb69c` 2026-07-06 (#4017)
- **Description**: All 14 repos inherit `BaseRepository` and the helper exists, but every repo still hand-rolls `session = self.get_session(); try/finally: close()`.
- **Evidence**: `grep -rn "session = self.get_session()" auralis/library/repositories/ | wc -l` → 111; `grep -rln "_session_scope()"` → only `base.py`'s own docstring.
- **Impact**: Any future session-lifecycle change requires a ~111-site sweep instead of a one-file edit; two competing patterns coexist with no signal which is canonical.
- **Suggested Fix**: Migrate read-only call sites first (largest offenders: `track_repository.py` 21, `fingerprint_repository.py` 16), leave commit/rollback-bearing write paths for a follow-up.

##### TD3-4: 12 DSP "stage" modules share an identical `apply()` contract and early-return guard, duplicated with no shared base
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis/core/stages/{air_enhancement,bass_enhancement,clarity_boost,harmonic_exciter,loudness_maximizer,mid_warmth,presence_enhancement,resonance_notches,stereo_expansion,sub_bass_control,transient_shaper}.py` (11 files) + `safety_limiter.py` (diverges to a bare-array contract)
- **Status**: NEW
- **Description**: `return audio.copy(), None` appears 15 times across 11 files with no shared helper; `safety_limiter.py` alone breaks the `(processed, stage_info)` tuple contract.
- **Evidence**: All 11 tuple-contract stages verified to consistently `.copy()` on every bypass path — **no missing-guard divergence found**, stays LOW.
- **Suggested Fix**: Give `safety_limiter.apply()` the same tuple contract, or add a shared `no_op(audio)` helper in `stages/__init__.py`.

##### TD3-5: Two competing generic frontend API-client hooks (`useRestAPI` vs `useStandardizedAPI`) solve the same problem independently
- **Severity**: LOW | **Effort**: medium
- **Location**: `hooks/api/useRestAPI.ts` (422L) vs `hooks/shared/useStandardizedAPI.ts` (551L)
- **Status**: NEW
- **Description**: `useRestAPI` has 5 production consumers with 4 independent bug fixes already applied (#2489, #2467, #2439, #3055); `useStandardizedAPI` has exactly 1 consumer (`CacheManagementPanel.tsx`).
- **Related**: #3256, #3654 (narrower bugs in each hook, not the duplication itself).
- **Suggested Fix**: Migrate `CacheManagementPanel.tsx` onto `useRestAPI` and delete `useStandardizedAPI.ts` + `standardizedAPIClient` family, or document `useStandardizedAPI` as a cache-aware specialization that reuses `useRestAPI` internally.

##### TD3-6: 35 raw `HTTPException(status_code=404, ...)` call sites across 10 routers bypass the existing `NotFoundError` helper
- **Severity**: LOW | **Effort**: small
- **Location**: `routers/errors.py:25-32` (helper) vs `metadata.py` (7), `similarity.py` (7), `artwork.py` (6), `playlists.py` (5), `processing_api.py` (4), `wav_streaming.py` (2), `enhancement.py`/`settings.py`/`player.py`/`fingerprint_status.py` (1 each)
- **Status**: NEW
- **Evidence**: `grep -n 'HTTPException(status_code=404' routers/*.py | wc -l` → 35; `NotFoundError` already adopted in `artists.py`/`albums.py`/`library.py`/`tracks.py`.
- **Related**: #4018 (OPEN — complementary, not the same edit).
- **Suggested Fix**: Replace the 35 raw raises with `NotFoundError("Track", track_id)` etc.

##### TD3-7: `serializers.serialize_playlist`/`serialize_playlists` are dead — `playlists.py` reimplements the same shape inline instead
- **Severity**: LOW | **Effort**: trivial
- **Location**: `routers/serializers.py:267-296` vs `routers/playlists.py:86,115-117,163`
- **Status**: NEW
- **Description**: `playlists.py` never imports `serializers`, hand-building the same `{**playlist.to_dict(), 'track_count': ...}` shape 3 times.
- **Suggested Fix**: Repoint `playlists.py`'s 3 inline sites at `serialize_playlist`/`serialize_playlists`.

##### TD3-8: `AdaptiveCompressor._apply_lookahead` and `AdaptiveLimiter._apply_lookahead_delay` are a byte-identical ~15-line ring-buffer implementation in two files
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis/dsp/dynamics/compressor.py:160-197` vs `limiter.py:173-206`
- **Status**: NEW | **Age**: `4c5b62a2` 2026-05-27 (limiter's copy hardened with a #3427 comment; compressor's identical code untouched)
- **Description**: Both copies already carry correct `.copy()` guards (no divergence found — stays LOW); the maintenance cost is that the #3427 rationale comment was never ported to the compressor's identical line.
- **Suggested Fix**: Extract a shared `LookaheadBuffer` helper class used by both `AdaptiveCompressor` and `AdaptiveLimiter`.

#### Dimension 4: Magic Numbers & Hardcoded Constants (5 LOW; 1 MEDIUM listed above)

##### TD4-1: `MAX_LEVEL_CHANGE_DB` duplicated verbatim in two backend modules
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis-web/backend/core/level_manager.py:21` and `chunked_processor.py:97`
- **Status**: NEW
- **Description**: Both declare `MAX_LEVEL_CHANGE_DB = 1.5`; `chunked_processor.py`'s copy is entirely redundant (just re-supplies `LevelManager`'s own default). Same copy-instead-of-import pattern the 2026-05-30 audit flagged but its fix (#4024/#4025) only covered the 4 chunk-geometry constants, not this one.
- **Suggested Fix**: Delete the `chunked_processor.py:97` declaration; call `LevelManager()` with no argument.

##### TD4-2: `ChunkOperations` static methods redeclare all four chunk-geometry constants as bare defaults, bypassing `chunk_boundaries.py`
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis-web/backend/core/chunk_operations.py:45-47,89,150-152,336,361`
- **Status**: NEW (named as a "Sibling" of the fixed TD4-01 in the 2026-05-30 report but never itself remediated)
- **Description**: No import from `core.chunk_boundaries` at all; 3 method signatures redeclare `chunk_duration=15`/`chunk_interval=10`/`overlap_duration=5` and one bare inline `context_duration = 5.0`. Currently dead (every call site passes explicit kwargs) but a repeat of the #4124 failure class if a caller ever drops an explicit kwarg.
- **Related**: #4124, #4024/#4025.
- **Suggested Fix**: `from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION, CONTEXT_DURATION` and use those as defaults.

##### TD4-4: `themeConfig.ts` still uses raw pure-black `rgba(0, 0, 0, …)` shadow literals despite the design system's explicit "no pure black" token bucket
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:92,108,245,317,318`
- **Status**: NEW
- **Description**: `design-system/tokens/colors.ts` defines `opacityScale.dark.*` specifically because the Style Guide forbids pure-black shadows; `themeConfig.ts` (the file building the actual MUI theme) has 5 leftover `rgba(0, 0, 0, ...)` literals, 3 in the same string as an already-tokenized value.
- **Related**: overlaps `/audit-frontend` Dimension 5.
- **Suggested Fix**: Replace each with the matching `tokens.colors.opacityScale.dark.*` bucket.

##### TD4-5: Raw `rgba(255, 255, 255, 0.NN)` white-highlight literals scattered across ~10 component style files, despite `opacityScale.white.*` defining the same values
- **Severity**: LOW | **Effort**: small
- **Location**: `AppTopBar.styles.ts:14`, `MediaCard.tsx:162`, `SidebarStyles.ts:96`, `MobileSidebarDrawer.tsx:56`, `PlaybackControlsStyles.ts:46,58,63`, `ArtistList.styles.ts:45,52,108`, `DroppablePlaylist.styles.ts:25`, `TrackListView.styles.ts:6`, `TrackInfo.tsx:118`, `Player.styles.ts:25,129`, `TrackRowAlbumArt.tsx:31`
- **Status**: NEW
- **Description**: Numerous files build a two-part `boxShadow` where the dark/accent half is correctly tokenized but the white-highlight half in the same string is a bare literal matching an exact `opacityScale.white.*` value.
- **Related**: overlaps `/audit-frontend` Dimension 5.
- **Suggested Fix**: Sweep listed sites and replace each with the matching `opacityScale.white.*` bucket.

##### TD4-6: Bare small-window FFT/hop-size literals in three analysis fast paths, unaware of the actual sample rate
- **Severity**: LOW | **Effort**: small
- **Location**: `core/analysis/content_analysis_facade.py:211-214`, `analysis/content_aware_analyzer.py:337-352`, `analysis/ml/feature_extractor.py:189-195`, `dsp/utils/spectral.py:220-238`
- **Status**: NEW (named only as prose "Siblings" of the closed TD4-05 in the 2026-05-30 report, which only fixed `content_analyzer.py:381` — these fast-path windows were never changed)
- **Description**: Four routines hardcode a small FFT window/hop (512/1024/2048 samples) despite having the real sample rate available; at 96kHz the same window covers less time than at 44.1kHz.
- **Related**: Correctness spillover → `/audit-engine` (same family as the already-fixed #4029).
- **Suggested Fix**: Introduce a `frames_for_seconds(sample_rate, seconds)` helper (pattern already used for #4030) and route all four sites through it.

#### Dimension 5: Stub & Placeholder Implementations (4 LOW; 1 MEDIUM listed above)

##### TD5-2: `useFingerprintCache` generates a hardcoded mock fingerprint disguised as Web Worker output — currently dead code
- **Severity**: LOW | **Effort**: medium
- **Location**: `hooks/fingerprint/useFingerprintCache.ts:88-152`
- **Status**: NEW | **Age**: `166f8fba6` 2025-11-30
- **Description**: `startWorker()` never starts a real Web Worker; it fakes progress then writes a hardcoded constant 25D fingerprint for every track. Not consumed by any component today — kept LOW rather than promoted.
- **Related**: Same shape as open #3805 (`useQueueHistory`), not re-reported there.
- **Suggested Fix**: Delete the hook if abandoned, or implement a real `new Worker(...)` before any component adopts it.

##### TD5-3: `DuplicateDetector.find_duplicates(directories=None)` silently returns `[]` for whole-library dedup
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis/library/scanner/duplicate_detector.py:61-65`
- **Status**: NEW | **Age**: `ab8fce286` 2025-10-31
- **Description**: The `directories=None` ("check entire library") branch is a `pass` no-op returning `[]`; not reachable from any shipped route today (no UI surface exists).
- **Suggested Fix**: Implement the whole-library query, or raise `NotImplementedError` explicitly instead of returning a silently-empty result.

##### TD5-4: `SidecarManager.bulk_generate()` never generates a sidecar — every non-cached file is counted as "skipped"
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis/library/sidecar_manager.py:328-359`
- **Status**: NEW | **Age**: `6a38afa6d` 2025-10-29
- **Description**: Zero callers anywhere; the single-file paths used by `fingerprint_extractor.py` are how sidecars are actually produced.
- **Suggested Fix**: Wire `bulk_generate` to `FingerprintExtractor`'s existing `write()` path in a loop, or delete it.

##### TD5-5: `Scanner._update_library_stats()` is a reachable no-op that only logs — never updates any table
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/library/scanner/scanner.py:216,301-308`
- **Status**: NEW
- **Description**: Called unconditionally at the end of every scan (reachable from `LibraryAutoScanner`), but only logs; verified harmless since the real `/api/library/stats` endpoint computes stats live via SQL aggregation and never reads a cached table.
- **Suggested Fix**: Delete `_update_library_stats()` and its call site.

#### Dimension 6: Test Hygiene (11)

##### TD6-1: Artwork test files are 7 "would verify" stubs, not tests
- **Severity**: LOW | **Effort**: small
- **Location**: `tests/backend/test_artwork_integration.py:203-213,225-231,243-247,320-326,335-341`; `tests/backend/test_artwork_management.py:180-189`
- **Status**: NEW
- **Description**: 7 collected functions consist only of a docstring "Workflow: 1... 2... 3..." and a bare `pass` — no fixture, no call, no assertion.
- **Impact**: Anyone reading test output believes cache invalidation, size-limit eviction, and fallback serving are covered. None of it is.
- **Suggested Fix**: Implement against the real `ArtworkExtractor`, or delete and open one tracking issue for the coverage gap.

##### TD6-2: `test_summary_stats` convention — ~29 files, pure `print()`, zero assertions
- **Severity**: LOW | **Effort**: trivial
- **Location**: 29 files across `tests/backend/`, `tests/auralis/`, `tests/integration/` (full list in dimension detail)
- **Status**: NEW
- **Description**: Each defines a `test_summary_stats()` whose entire body is hardcoded `print()` calls with typed-by-hand counts; already drifted in at least one file (`test_artwork_management.py` prints "15" for 13 real tests).
- **Suggested Fix**: Delete all `test_summary_stats`-style functions; use `pytest --collect-only` in CI if a count is wanted.

##### TD6-3: `test_folder_scanner.py` — 4 tests can never fail (print + `return True/False`, no `assert`)
- **Severity**: LOW | **Effort**: small
- **Location**: `tests/auralis/library/test_folder_scanner.py:85-267`
- **Status**: NEW
- **Description**: Exercises the real `LibraryScanner`/`LibraryManager` but verification is via `if/else: print()` + `return True/False`; pytest ignores return values, so `return False` reports PASS.
- **Impact**: A regression that makes the scanner miss files or mis-extract metadata is invisible in CI.
- **Suggested Fix**: Replace every `if/else: print` branch with a plain `assert`.

##### TD6-4: Personal-library-path "validation" scripts collected as pytest tests, zero assertions (sibling of fixed #4047)
- **Severity**: LOW | **Effort**: small
- **Location**: `tests/test_phase7b_dramatic_changes.py`, `test_phase7b_production_styles.py`, `test_phase7b_genre_comprehensive.py`, `test_phase7b_performance_scaling.py`, `tests/backend/test_blind_guardian_comprehensive.py`, `test_phil_collins_matchering_validation.py`
- **Status**: NEW (Related: #4047 CLOSED — same pattern, different files)
- **Description**: Hardcode the developer's personal music-library paths; when absent, guard with bare `print(); return` rather than `pytest.skip()`, so they report PASS with zero verification on every other machine.
- **Suggested Fix**: Same treatment as #4047 — add real threshold assertions and `pytest.skip()`, or rename out of the `test_*.py` glob.

##### TD6-5: `test_boundary_data_integrity.py` unicode/special-char tests never check the stored value
- **Severity**: LOW | **Effort**: trivial
- **Location**: `tests/backend/test_boundary_data_integrity.py:398-435,443-483`
- **Status**: NEW
- **Description**: Docstrings promise "Special chars stored correctly"/"Unicode stored correctly" but bodies only assert `retrieved is not None`, never comparing the actual value.
- **Suggested Fix**: Add `assert retrieved.title == special` / `== unicode_str` after the `is not None` check.

##### TD6-6: Broader "sole `is not None`" smoke-assertion pattern beyond the #4049 fix (56 tests / 32 files)
- **Severity**: LOW | **Effort**: medium
- **Location**: Highest concentrations: `tests/regression/test_detached_instance_error.py` (9), `test_boundary_data_integrity.py` (5), `tests/stress/test_edge_cases.py` (4)
- **Status**: NEW — distinct from closed #4049 (covered a specific 31-test subset; this is the remaining long tail)
- **Description**: 6 of 9 flagged tests in `test_detached_instance_error.py` (settings/queue-state accessors) check only `is not None` with no follow-up attribute access — a real DetachedInstanceError-class regression on a nested attribute wouldn't be caught in exactly the suite meant to guard against it.
- **Suggested Fix**: Add an attribute access after each `is not None` check in `test_detached_instance_error.py`; triage the remaining 25 files opportunistically.

##### TD6-7: `TEMPLATE.test.tsx` is collected and run by vitest — ~10 no-op passing tests
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis-web/frontend/src/test/TEMPLATE.test.tsx:1-170`; glob at `vitest.config.ts:37`
- **Status**: NEW
- **Suggested Fix**: Rename to not match the vitest `include` glob, or add an explicit `exclude` entry.

##### TD6-8: 3 frontend `it.skip` with no tracking issue
- **Severity**: LOW | **Effort**: small
- **Location**: `CacheHealthWidget.test.tsx:370,574`; `Integration.test.tsx:252`
- **Status**: NEW
- **Description**: One skip is a direct consequence of the global `WebSocketContext` auto-mock in `test/setup.ts` making it structurally hard to write a real WS-integration render test.
- **Suggested Fix**: File one tracking issue covering all 3 (ESC-key decision, hook-level auto-refresh test, `vi.unmock`-based integration test).

##### TD6-9: `test_parallel_processing.py` xfails lack `strict=True` / issue refs — sibling of the #4042 fix in the same directory
- **Severity**: LOW | **Effort**: trivial
- **Location**: `tests/concurrency/test_parallel_processing.py:279,374,673,709`
- **Status**: NEW (Related: #4042 CLOSED — same anti-pattern, sibling file untouched)
- **Suggested Fix**: Add `strict=True` to all 4; link or open an issue per distinct reason.

##### TD6-10: HPSS short-audio xfail has no issue reference or `strict=True` (real DSP bug, untracked)
- **Severity**: LOW | **Effort**: trivial
- **Location**: `tests/auralis/test_audio_processing_invariants.py:480`
- **Status**: NEW
- **Description**: Documents a real crash ("ndarray shape overflow in Rust HPSS implementation") with no tracking.
- **Related**: Real bug → route to `/audit-engine`.
- **Suggested Fix**: File an issue for the Rust HPSS shape-overflow bug, link it in `reason=`, add `strict=True`.

##### TD6-11: `test_priority4_streaming_integration.py` — whole test classes permanently dead via wrong import path, invisible to `@pytest.mark.skip` grep
- **Severity**: LOW | **Effort**: small
- **Location**: `tests/integration/test_priority4_streaming_integration.py:30-141` (4 of 10 tests)
- **Status**: NEW (Related: #4044 CLOSED — same import-drift root cause, different file, plus class-name drift)
- **Description**: `try/except ImportError: pytest.skip(...)` wraps imports from the non-existent `auralis_web` (underscore) package with class names that have also drifted (`ChunkedAudioProcessor`/`StreamlinedCacheManager` don't exist under any path). Invisible to the standard skip/xfail grep baseline.
- **Siblings**: Same shape in `tests/auralis/player/test_enhanced_player_detailed.py` (13x) and `tests/auralis/core/test_core.py` (7x) — not read in depth this pass.
- **Suggested Fix**: Fix imports to `from core.chunked_processor import ChunkedProcessor` / `from core.chunk_cache_manager import ChunkCacheManager`, update usages, re-verify execution.

#### Dimension 7: Stale Documentation & Comments (6)

##### TD7-1: `docs/README.md` — stale version banner, wrong "Last Updated", 2 dead links
- **Severity**: LOW | **Effort**: trivial
- **Location**: `docs/README.md:5,75,88,102` (version); `:33,77` (dead links)
- **Status**: NEW
- **Description**: Claims "1.1.0-beta.5" (SoT is 1.2.1-beta.2) and "Last Updated: December 2024" despite the file itself last touched December 2025; links to nonexistent `features/player/` and `../archive/`.
- **Suggested Fix**: Update version banner and timestamp; fix or remove the two dead links.

##### TD7-2: `docs/MASTER_ROADMAP.md` frozen at Nov 2025 but still linked as the primary roadmap resource
- **Severity**: LOW | **Effort**: small
- **Location**: `docs/MASTER_ROADMAP.md:3-6`
- **Status**: NEW | **Age**: last touched 2026-06-01 despite header claiming Nov 2025 content
- **Description**: Header claims version 1.1.0-beta.2 and "Next Release: 1.1.0 (Target: December 2025)" — already 3+ releases stale; both `README.md` and `docs/README.md` still present it as the current roadmap.
- **Suggested Fix**: Update the header/current-state section, or explicitly re-title as a dated historical snapshot.

##### TD7-3: `README.md` "Run from Source → Web Interface" quick start omits the frontend build step and `--dev` flag
- **Severity**: LOW | **Effort**: small
- **Location**: `README.md:122-129`
- **Status**: NEW
- **Description**: Literal instructions (`python launch-auralis-web.py`, no `--dev`, no frontend build) yield either a 404/blank page or the wrong port, since `main.py` only mounts the frontend when `dist/` exists (gitignored, doesn't exist on fresh clone) and not in `--dev` mode. CLAUDE.md's equivalent command is already correct.
- **Suggested Fix**: Add the `npm install && npm run build` step, or switch the example to `python launch-auralis-web.py --dev` (UI at `:3000`).

##### TD7-4: `TESTING_GUIDELINES.md` documents a CI test pipeline that doesn't exist
- **Severity**: LOW | **Effort**: small
- **Location**: `docs/development/TESTING_GUIDELINES.md:1028-1074`
- **Status**: NEW
- **Description**: Describes a `.github/workflows/test.yml` running pytest+coverage and `npm run test:coverage`+codecov; no such file exists (`.github/workflows/` only has `build-release.yml` and `frontend-typecheck.yml`, the latter only runs `tsc`).
- **Related**: `frontend-typecheck.yml`'s own header (added for #4143) already acknowledges CI gaps.
- **Suggested Fix**: Either add the described workflow for real, or mark the section "proposed, not yet implemented."

##### TD7-5: `TESTING_GUIDELINES.md` header date and "Current State" narrative frozen since 2024, out of sync with its own recently-updated CI section
- **Severity**: LOW | **Effort**: trivial
- **Location**: `docs/development/TESTING_GUIDELINES.md:3-4,23-34`
- **Status**: NEW
- **Description**: Header reads "Last Updated: November 6, 2024"; body has "Current State (Nov 2024)" and "Target State (Beta 10.0 - Q1 2025)" — "Beta 10.0" was never the project's actual version scheme (current is 1.2.1-beta.2), and the live test count (5,156) has moved past both framings.
- **Suggested Fix**: Bump header date/version, replace the frozen narrative with a single "as of &lt;date&gt;" test-count line, drop the obsolete "Beta 10.0" label.

##### TD7-6: Root `package.json` version one release behind `auralis/version.py` SoT
- **Severity**: LOW | **Effort**: trivial
- **Location**: `package.json:3`
- **Status**: NEW | **Age**: `50a3c1d4` 2026-01-02
- **Description**: Says `1.2.0-beta.3` while `desktop/package.json` and `auralis-web/frontend/package.json` correctly say `1.2.1-beta.2`. Confirmed cosmetic today (real build path reads `desktop/package.json`), but a latent risk if a future script trusts the root file.
- **Suggested Fix**: Bump to `1.2.1-beta.2` alongside the next SoT bump; add to whatever bumps the other three files.

#### Dimension 8: Backwards-Compat Cruft & "No Variants" Violations (8)

##### TD8-1: `# REMOVED` / `// Removed:` breadcrumb comments — #4088 fix was incomplete + one new instance
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/core/processing/realtime_dsp_pipeline.py:92-93`, `design-system/animations/index.ts:193-194`, `auralis-web/backend/core/proactive_buffer.py:114-123`
- **Status**: Regression of #4088 (2 sibling locations) + NEW (proactive_buffer.py instance)
- **Description**: Closed #4088 explicitly named these two siblings to fix "in the same pass"; both are still present verbatim. A third, previously-unreported 10-line tombstone exists in `proactive_buffer.py`.
- **Suggested Fix**: Delete all three comment blocks; no functional change.

##### TD8-2: Four more DSP/library/analysis modules dead via file-vs-package shadowing (same bug class as closed #4069)
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis/library/scanner.py`, `models.py`, `metadata_editor.py`, `auralis/core/analysis/spectrum_mapper.py`
- **Status**: NEW | **Age**: `2ff696c9` 2026-02-13 (same commit introduced these and the four #4069-fixed shims)
- **Description**: Each is a "BACKWARD COMPATIBILITY WRAPPER" file shadowed by a same-named package directory; Python always resolves the package, so none of these 4 files is ever imported. Verified empirically via `python3 -c "import auralis.library.models as m; print(m.__file__)"` → resolves to `models/__init__.py`, not `models.py`.
- **Siblings**: `auralis/player/realtime_processor.py` is NOT shadowed (re-exports from a differently-named package) — it IS reachable and still used by 4 call sites; lower-priority consolidation.
- **Related**: #4069 (closed) — same author/commit, fix pass missed these four.
- **Suggested Fix**: Delete all 4 shadowed files outright (zero caller impact); separately repoint `realtime_processor.py`'s importers and delete it too.

##### TD8-3: `auralis/analysis/content/feature_extractors.py` — DEPRECATED wrapper with 1 live production caller
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis/analysis/content/feature_extractors.py:1-88`, caller `content_analysis.py:26,61`
- **Status**: NEW | **Age**: `2ff696c9` 2026-02-13
- **Description**: Docstring says "DEPRECATED: Use ContentAnalysisOperations instead"; one production caller remains. Name collides confusingly with the real `ml/feature_extractor.py::FeatureExtractor`.
- **Related**: #4086 (closed) — direct precedent for the fix shape.
- **Suggested Fix**: Repoint `content_analysis.py:61` to call `ContentAnalysisOperations` directly, delete the wrapper.

##### TD8-4: `auralis.player.enhanced_audio_player.QueueManager` — dead compat alias, name-collides with the real `QueueManager`
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis/player/enhanced_audio_player.py:36-38`
- **Status**: NEW | **Age**: `f2e8e394c` 2025-11-19
- **Description**: `QueueManager = QueueController` alias, zero call sites; a completely different real `QueueManager` class exists at `components/queue_manager.py`.
- **Suggested Fix**: Delete the alias line.

##### TD8-5: `library_manager` parameter threaded dead through `AudioPlayer` → `QueueController` (accept-and-drop)
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis/player/enhanced_audio_player.py:65-69,92`, `auralis/player/queue_controller.py:28-41`
- **Status**: NEW
- **Description**: Docstring says "Deprecated, kept for backward compatibility only"; `QueueController.__init__` accepts it but never stores or reads it. No call site anywhere passes it.
- **Siblings**: `routers/files.py:64,72`'s `create_files_router(get_library_manager=...)` has the identical shape, still explicitly resolved and passed at `config/routes.py:124`.
- **Suggested Fix**: Remove the parameter from both classes' signatures and from `create_files_router`/`config/routes.py:124`.

##### TD8-6: `dependencies.py::require_library_manager` — deprecated shim, zero callers
- **Severity**: LOW | **Effort**: trivial
- **Location**: `auralis-web/backend/routers/dependencies.py:31-58`
- **Status**: NEW
- **Description**: Fires a `DeprecationWarning` on every call but is never called anywhere. `require_repository_factory` in the same file is the live replacement, confirming the migration completed.
- **Suggested Fix**: Delete the function entirely.

##### TD8-7: `LibraryManager` class — "DEPRECATED" migration-timeline promise unfulfilled 5 versions later
- **Severity**: LOW | **Effort**: large
- **Location**: `auralis/library/manager.py:1-115`
- **Status**: NEW (distinct from open #3770, cache-invalidation angle only)
- **Description**: Docstring promises "v1.2.0: Deprecation warnings in all methods" — current version is 1.2.1-beta.2, but only `__init__` warns. Still the working facade instantiated at startup, and still being actively extended.
- **Related**: #3770 (open), #4232 (open).
- **Suggested Fix**: Either commit to a dedicated removal migration (large, separate session), or rewrite the docstring to drop the unmet version timeline.

##### TD8-8: Frontend `ArtistDetailApiResponse.artist_id`/`artist_name` — dead post-rollout compat fields, backend never sends them
- **Severity**: LOW | **Effort**: trivial
- **Location**: `api/transformers/types.ts:134-140`, `artistTransformer.ts:61-62`
- **Status**: NEW | **Age**: `6b1dc519` 2026-03-22 (#3211)
- **Description**: Backend's `ArtistDetailResponse` has only ever had `id`/`name` since #3211 — the "during rollout" fallback branch can never fire; the rollout window closed 3+ months ago.
- **Related**: #3211 (closed).
- **Suggested Fix**: Delete `artist_id`/`artist_name` from the type and simplify the transformer to `apiDetail.id`/`apiDetail.name` directly.

#### Dimension 9: File/Function/Module Complexity (19)

##### TD9-1: `chunked_processor.py` — 958-line chunk-processing god class
- **Severity**: LOW | **Effort**: large
- **Location**: `auralis-web/backend/core/chunked_processor.py` (958 lines, whole file)
- **Status**: NEW | **Age**: `c39b1773` 2026-06-28
- **Description**: `ChunkedAudioProcessor` owns metadata loading, adaptive-mastering init, chunk-path resolution, RMS/level-smoothing crossfade math, hybrid-processor invocation, and 3 overlapping `process_chunk*` entry points, plus an unrelated `get_mastering_recommendation`.
- **Siblings**: `audio_stream_controller.py` (#4071) — sibling god-file one layer up the call stack.
- **Related**: #4071, #4124, #3807.
- **Suggested Fix**: Extract crossfade/level-smoothing to `chunk_crossfade.py`; extract `get_mastering_recommendation` to its own module; collapse the three entry points into one method with a `locked: bool` param.

##### TD9-2: Library repositories — `track_repository.py` (942L) + `playlist_repository.py` (603L), each with a 100+ line CRUD method
- **Severity**: LOW | **Effort**: medium
- **Location**: `track_repository.py:38-216` (`add`, 179 lines); `playlist_repository.py:197-342` (`add_track`, 146 lines)
- **Status**: NEW
- **Description**: `TrackRepository.add()` inlines path validation, artist/genre upsert, duplicate detection, metadata normalization in one 179-line method; `PlaylistRepository.add_track()` inlines position-shifting/dedup across 146 lines, duplicating `add_tracks`' batch-variant math.
- **Siblings**: `fingerprint_repository.py` (693L, Existing #4073) — same root cause.
- **Related**: #4073.
- **Suggested Fix**: Extract `_upsert_artists_and_genres()`/`_validate_and_normalize_track_info()` from `add`; extract a shared `_shift_positions()` used by both `add_track` and `add_tracks`.

##### TD9-3: `enhanced_audio_player.py` — 821-line player class covering playback, queue, callbacks, and property surface
- **Severity**: LOW | **Effort**: large
- **Location**: `auralis/player/enhanced_audio_player.py` (821 lines, whole file)
- **Status**: NEW | **Age**: `f28346eb` 2026-06-28
- **Description**: Combines transport controls, fingerprint-scheduling background-thread coordination, queue navigation, and ~15 property getters/setters in one class.
- **Related**: #4141 (fixed), #3735 (open, next_track lock scope).
- **Suggested Fix**: Extract the fingerprint-scheduling pair into a `PlayerFingerprintLoader` helper; move the property block to a mixin.

##### TD9-4: `processing_engine.py` — 786-line orchestrator with a 181-line `process_job`
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis-web/backend/core/processing_engine.py:415-596`
- **Status**: NEW | **Age**: `75899004` 2026-06-01
- **Description**: Job lifecycle, processor-pool management, and worker-loop management are three separable concerns already existing as distinct method groups, just not distinct files.
- **Suggested Fix**: Extract processor-pool management into `processor_pool.py`; extract the worker loop into `job_worker.py`; split `process_job` into `_prepare_job()`/`_execute_job()`/`_finalize_job()`.

##### TD9-5: `mastering_branches.py` — 750-line branch-strategy module, sibling of `simple_mastering.py`
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis/core/mastering_branches.py` (750 lines, whole file)
- **Status**: NEW | **Age**: `e350bf67` 2026-06-28
- **Description**: `MaterialClassifier` + abstract `ProcessingBranch` + 3 concrete branches in one file; `CompressedLoudBranch.apply` alone is 109 lines. Classes are already isolated (mechanical split, not a redesign).
- **Siblings**: `simple_mastering.py` (935L, Existing #4072) — same subsystem, same split axis.
- **Related**: #4072.
- **Suggested Fix**: Split into `mastering_branches/{classifier,base,compressed_loud,dynamic_loud,quiet}.py`, re-exported via `__init__.py`.

##### TD9-6: `continuous_mode.py` — 743-line file; the #4082 method-split relocated size into a new 138-line method
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis/core/processing/continuous_mode.py:332-470` (`_apply_dsp_stages`)
- **Status**: NEW (file-level was never separately tracked; closed #4082 only addressed `process()`)
- **Description**: #4082 correctly split the 214-line `process()`, but `_apply_dsp_stages` is now itself a 138-line method chaining seven DSP sub-operations — the complexity moved, didn't shrink.
- **Related**: #4082 (closed — partially superseded).
- **Suggested Fix**: `_apply_dsp_stages` should become a thin loop over an ordered `(enabled_flag, stage_fn)` list rather than seven sequential inline calls.

##### TD9-7: `queue_service.py` — 695-line service mixing Protocol definitions, queue mutation, and history/template persistence
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis-web/backend/services/queue_service.py` (695 lines, whole file)
- **Status**: NEW | **Age**: `b2651fcb` 2026-06-01
- **Description**: Two `Protocol` interfaces (pure typing) plus a `QueueService` class handling live mutation and persistence that the repository layer already separates elsewhere.
- **Related**: #3916 (concurrency bug in this same file — its size makes that bug easy to miss on review).
- **Suggested Fix**: Move Protocols to `queue_protocols.py`; extract persistence logic into calls against `QueueHistoryRepository`/`QueueTemplateRepository` (verify against #3916 fix in progress first).

##### TD9-8: `hybrid_processor.py` — 656-line orchestrator mixing three processing-mode dispatchers with module-level singleton helpers
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis/core/hybrid_processor.py` (656 lines, whole file)
- **Status**: NEW | **Age**: `d9489fe7` 2026-06-28
- **Description**: `HybridProcessor` class plus 5 appended module-level functions (`process_adaptive`/`process_reference`/`process_hybrid`) form a parallel free-function API alongside the class API — a "No Variants"-adjacent parallel-API risk.
- **Suggested Fix**: Move the module-level wrappers to `hybrid_processor_singleton.py`, or delete if grep shows no callers (check first).

##### TD9-9: Oversized backend routers mixing multiple sub-domains — `wav_streaming.py` (650L) + `similarity.py` (624L)
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis-web/backend/routers/wav_streaming.py`, `routers/similarity.py`
- **Status**: NEW | **Age**: `97dfd9e6`/`51e26c68` 2026-06-28/05-29
- **Description**: `wav_streaming.py` bundles a general-purpose `_AudioFileCache` + chunk-layout math + streaming handlers; `similarity.py` bundles similarity search, graph management, and fingerprint-queue admin under one router.
- **Related**: #4075 (proves the split pattern works — `library.py` was already done this way).
- **Suggested Fix**: Extract `_AudioFileCache` to `services/audio_file_cache.py`; split `similarity.py` into `similarity.py`/`similarity_graph.py`/`fingerprint_queue.py`.

##### TD9-10: `parallel_processor.py` — 634-line file with four independent parallel-processing classes
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis/optimization/parallel_processor.py` (634 lines, whole file)
- **Status**: NEW | **Age**: `1180a8fb` 2026-06-28
- **Description**: Four classes already have clean boundaries and no shared state beyond a common `ParallelConfig` dataclass — a mechanical "one class per file" split.
- **Suggested Fix**: `optimization/parallel/{config,fft_processor,band_processor,feature_extractor,audio_processor}.py`, barrel-reexported.

##### TD9-11: `fingerprint_extractor.py` — 630-line file with a 270-line, 5-level-deep `extract_and_store`
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis/services/fingerprint_extractor.py:264-533`
- **Status**: NEW | **Age**: `5726e75c` 2026-06-28
- **Description**: The single largest method found this audit — nests sidecar validity, sidecar version, Rust-server availability, Rust call, file-size guard, Python fallback, duration cap, and DB write at depth 5+.
- **Related**: #4108, #4136 (hot-path history).
- **Suggested Fix**: Extract each strategy into `_try_sidecar_fingerprint()`/`_try_rust_server_fingerprint()`/`_try_python_fallback_fingerprint()`; `extract_and_store` becomes a ~20-line dispatcher.

##### TD9-12: `helpers.py` — 609-line grab-bag of four unrelated utility domains
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis-web/backend/helpers.py` (609 lines, whole file)
- **Status**: NEW | **Age**: `5de7a25f` 2026-05-26
- **Description**: Mixes asyncio task helpers, pagination, list filtering, and cache-stats estimation — four independent concerns co-located as "helpers."
- **Suggested Fix**: Split into `utils/{async_tasks,pagination,filtering,cache_stats}.py`; keep `helpers.py` as a thin re-export barrel if call-site churn is a concern.

##### TD9-13: `usePlaybackQueue.ts` — 606-line hook (non-test)
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts` (606 lines, whole file)
- **Status**: NEW | **Age**: `0c506382` 2026-06-17
- **Description**: One hook handles initial fetch, WS subscription, shuffle/repeat/reorder, and derived stats. Related open #3925 already flags a missing-`AbortController` bug — the hook's breadth makes that gap easy to miss.
- **Related**: #3925, #4077, #4019.
- **Suggested Fix**: Extract `useQueueFetch` (fixes #3925 as a side effect) and `useQueueSubscription`; keep mutation actions in the top-level hook.

##### TD9-14: `WebSocketContext.tsx` — 605-line context provider
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx` (605 lines, whole file)
- **Status**: NEW | **Age**: `974c830e` 2026-06-28
- **Description**: Combines connection lifecycle/backoff, message dispatch, and subscribe/unsubscribe API in one file — the root of the app's real-time data flow, so its size directly gates reconnect-path review confidence.
- **Suggested Fix**: Extract connection-lifecycle/backoff into a `useWebSocketConnection` hook, leaving the context as a thin provider + subscribe/dispatch surface.

##### TD9-15: `AudioPlaybackEngine.ts` — 595-line playback engine, zero unit tests
- **Severity**: LOW | **Effort**: large
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts` (595 lines, whole file)
- **Status**: NEW | **Age**: `6848315a` 2026-06-28
- **Description**: Manages Web Audio buffer scheduling, gain/crossfade nodes, and playback-position tracking in one untested class; already flagged by open #3997.
- **Related**: #3997.
- **Suggested Fix**: Split into `BufferScheduler`/`CrossfadeController`/`PlaybackPositionTracker` — each independently unit-testable, directly unblocking #3997.

##### TD9-16: Shared API hook/client pair — `useStandardizedAPI.ts` (551L, 6 hooks) + `standardizedAPIClient.ts` (544L)
- **Severity**: LOW | **Effort**: medium
- **Location**: `hooks/shared/useStandardizedAPI.ts`, `services/api/standardizedAPIClient.ts`
- **Status**: NEW | **Age**: `3e81440b`/`661f95b1` 2026-06-28/03-25
- **Description**: 6 separately-usable hooks share one module; a change to one hook's abort logic risks unrelated diff noise against the other 5.
- **Related**: #3256.
- **Suggested Fix**: Split into `hooks/shared/api/{useStandardizedAPI,usePaginatedAPI,useCacheStats,useCacheHealth,useBatchOperations,useInitializeAPI}.ts`, barrel-reexported.

##### TD9-17: `performanceOptimizer.ts` — 856-line survivor of the #4080 consolidation, still a 4-in-1 monolith
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis-web/frontend/src/utils/performanceOptimizer.ts` (856 lines, whole file)
- **Status**: NEW | **Age**: `ef46d855` 2026-05-25
- **Description**: #4080 (closed) removed the 3-file duplication, but the consolidation landed as one 856-line file — the split-axis half of the fix's own suggested fix never shipped.
- **Related**: #4080 (closed — duplication resolved, split not applied).
- **Suggested Fix**: Split into `utils/rendering/{frame-rate-controller,data-decimator,canvas-pool,performance-monitor}.ts` per #4080's original proposal — now safe since there's only one file left.

##### TD9-18: `store/selectors/index.ts` — 496-line barrel mixing 28 selector exports with an embedded performance-tracking class
- **Severity**: LOW | **Effort**: small
- **Location**: `auralis-web/frontend/src/store/selectors/index.ts` (496 lines, 28 exports)
- **Status**: NEW | **Age**: `9deb8681` 2026-06-17
- **Description**: 28 directly-defined selectors plus a `SelectorPerformanceTracker` class and `createMemoizedSelector` factory bundled together — two unrelated jobs.
- **Suggested Fix**: Move selectors to `store/selectors/{player,queue,cache,connection}.ts`; move the performance-tracking pieces to `selectorPerformance.ts`; `index.ts` becomes a genuine re-export-only barrel.

##### TD9-19: `exportInfrastructure.ts` — 525-line shared infra behind the already-flagged `AnalysisExportService.ts`
- **Severity**: LOW | **Effort**: medium
- **Location**: `auralis-web/frontend/src/utils/exportInfrastructure.ts` (525 lines, whole file)
- **Status**: NEW | **Age**: `89853f0e` 2026-06-28
- **Description**: Bundles 6 unrelated concerns (`StatisticsAggregator`, `CanvasRenderingUtils`, `ExportFormatRegistry`, `ProgressTracker`, `DataTransformer`, `ExportOperationManager`) — splitting only `AnalysisExportService.ts` (per #4078) without this file would just relocate the size problem.
- **Related**: #4078 (open — fix alongside it, not instead of it). Note also TD2-3 (this whole subsystem may be dead code — resolve that question first).
- **Suggested Fix**: Split into `utils/export/{statistics,canvas-rendering,format-registry,progress-tracker,data-transformer,operation-manager}.ts`.

---

## Deferred

Findings gated on other in-progress or ambiguous work — do not action until the gate resolves:

- **TD2-3 / TD9-19** (`AnalysisExportService.ts`/`RealTimeAnalysisStream.ts`/`exportInfrastructure.ts`/`streamingInfrastructure.ts`, 2,540+525 lines) — gated on a product decision: is the export/streaming-analysis feature abandoned (delete all of it) or planned (split it, per open #4078)? Doing #4078's split before answering this question risks wasted effort. Deferred to that decision.
- **TD8-7** (`LibraryManager` deprecated-timeline docstring) — gated on a maintainer decision about whether the v2.0.0 removal is still intended; large effort either way, not a drive-by fix.
- **TD9-8** (`hybrid_processor.py` module-level `process_*` wrappers) — gated on confirming via grep whether these free functions have any live callers before deciding "move to a new file" vs. "delete as already-dead" (Dimension 2/8 territory).
- **TD6-4 sibling sweep** (`tests/auralis/player/test_enhanced_player_detailed.py`, `tests/auralis/core/test_core.py` — same `except ImportError: pytest.skip()` pattern as TD6-11, 20 occurrences combined) — not read in depth this pass; flagged as a follow-up sweep, not an independent finding, to avoid speculative severity assignment without reading the files.
- **60 pre-2026-04-07 audit reports** (Dimension 10) — sampled at the oldest/highest-severity end and came back clean (all triaged), but a full sweep of all ~60 reports' CRITICAL/HIGH findings against GitHub was not completed this pass; deferred to a dedicated Dimension-10 pass if audit-history integrity becomes a concern.

---

## Verification Notes (dimension-level regression checks, not new findings)

Each dimension agent re-verified the 2026-05-30 report's findings against current code before reporting anything new. Summary of what was confirmed still-fixed (no regressions except where noted above):

- **Dimension 2**: Prior unused-import batch (#4002–#4012) still fixed; `schemas.PaginatedResponse` (#3892), `proactive_buffer` dead callback (#3884), chunked-processor dead functions (#3879), `SmoothAnimationEngine.ts` (#4013), `src/a11y/` toolkit (#4014), `config/features.ts` (#4015) all confirmed still-open (not re-reported), no regressions.
- **Dimension 3**: `channel_count()`/`size()` duplication (#4021), `usePlayNormal`/`usePlayEnhanced` shared machinery (#4019), `common_metrics.py` duplication (#4020), router error-handling boilerplate (#4018), Rust `compute_rms`/`estimate_lufs` duplication (#4022), `_MAX_UPLOAD_BYTES` duplication (#4033), pagination-shape duplication (#3892), `is_dev_mode` duplication (#3899), `CacheStatsResponse` duplication (#3891) — all confirmed still open, correctly not re-reported.
- **Dimension 4**: All 9 of the 2026-05-30 Dimension-4 findings (TD4-01 through TD4-09) confirmed fixed and holding, **except** the two named-but-unfixed siblings now reported fresh as TD4-2 and TD4-6.
- **Dimension 5**: All 4 prior Dimension-5 findings (`HybridProcessor` str-path placeholder, Rust `median_filter.rs` stub, `ArtworkService` always-None, `AnalysisExportService.exportAsPDF` fake PDF) confirmed fixed via #4035/#4036/#4037/#4039 — no regressions.
- **Dimension 6**: #4042 (xfail `strict=True`), #4041 (deleted broken integration tests), #4046/#4047 (renamed out of collection), #4048/#4050 (import fixes), #4049 (smoke-assertion strengthening) all confirmed fixed and holding — except the two named sibling gaps reported fresh as TD6-4 and TD6-9.
- **Dimension 7**: Version drift (#4051/#4052), codebase-map counts (#4055/#4065/#4066/#4067), `TESTING_GUIDELINES.md` test-count/CI-version drift (#4064), README dead links (#4063), `WEBSOCKET_API.md` mismatches (#4058/#4059/#4060), `DB_SCHEMA_VERSION` drift (#4053/#4054) all confirmed fixed — no regressions found in this pass's scope.
- **Dimension 8**: 11 of the 12 2026-05-30 "No Variants"/compat-cruft fixes (#4068,#4069,#4070,#4076,#4084–#4091) fully confirmed gone from current code; **#4088 (breadcrumb comments) was only partially fixed** — reported fresh as TD8-1 (Regression).
- **Dimension 9**: `design-system/tokens.ts` (#4079) and `types/websocket.ts` (#4081) confirmed properly split; `useLibraryWithStats.ts` (#4083) and `routers/library.py` (#4075) confirmed already fixed in code despite stale OPEN issue state on GitHub (not re-reported per the dedup protocol — code is the source of truth); `ContinuousMode.process()` (#4082) confirmed split at the method level, with a follow-on file-level finding (TD9-6) for where the complexity moved to.
- **Dimension 10**: Prior stale-count findings (#4065/#4066/#4067) confirmed still accurate; the path-reference validate gate is clean (0 STALE, unchanged since Phase 1).

---

*Report generated 2026-07-06 via `/audit-tech-debt` (10/10 dimensions, `--depth deep`, no `--focus`/`--limit`). Suggested next step: `/audit-publish docs/audits/AUDIT_TECH_DEBT_2026-07-06.md`.*
