# Auralis Tech-Debt Audit — 2026-05-30

**Audit type**: Tech-Debt (10 dimensions, depth=deep, limit=unlimited)
**Scope**: `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/`, `tests/`, docs & audit skills
**Method**: 10 parallel dimension agents (general-purpose, sonnet), cross-deduplicated against 133 open GitHub issues + prior `docs/audits/` reports.
**Goal**: Surface decay that raises the cost of every future change; enforce project principles (DRY, Modular <300 lines, No Variants, Repository pattern). Not a correctness audit — real bugs are routed to the owning audit as `Related`.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| HIGH     | 0 |
| MEDIUM   | 3 |
| LOW      | 92 |
| **Total (after cross-dedup)** | **95** |

**Delta vs baseline**: This is the **first** tech-debt audit — it establishes the baseline. No prior `AUDIT_TECH_DEBT_*.md` report exists to diff against.

**Findings by dimension** (post-dedup):

| Dim | Name | Findings |
|-----|------|----------|
| 1 | Stale Markers | 0 (all 3 reclassified into Dim 5 — reachability decided severity) |
| 2 | Dead Code | 21 |
| 3 | Logic Duplication | 5 (1 MEDIUM) |
| 4 | Magic Numbers | 9 |
| 5 | Stub Implementations | 6 (2 MEDIUM) |
| 6 | Test Hygiene | 10 |
| 7 | Stale Documentation | 14 |
| 8 | Backwards-Compat Cruft | 15 |
| 9 | File/Function Complexity | 12 |
| 10 | Audit-Finding Rot | 3 |

**Headline themes**:
1. **Version & doc drift is pervasive** — `pyproject.toml` (1.1.0.beta.5), `auralis/__init__.py` (1.0.0), `CLAUDE.md`/`README.md` (1.2.0-beta.3) and `system.py` (1.2.1-beta.1) all disagree with the SoT `auralis/version.py` (1.2.1-beta.2). `system.py` reports `db_schema_version=3` while the live schema is **16**.
2. **Chunk-geometry constants are copied into 5 files** despite `chunk_boundaries.py` being the declared "SINGLE SOURCE OF TRUTH" — and one copy (`webm_streaming.py` default `chunk_duration=10`) *conflicts* with the canonical 15.
3. **Modularization left re-export shims behind** — 8 backward-compat wrapper modules (DSP, core config, analysis) with only in-repo callers; deletable since Auralis is desktop-only.
4. **Two near-identical 500+ line streaming hooks** (`usePlayNormal` / `usePlayEnhanced`) and **56 hand-rolled `try/except HTTPException` blocks** across 16 routers — one (`playlists.py`) carries a 500-vs-503 divergence the shared helper already fixed.
5. **178 files exceed the 300-line rule** (107 Python, 71 TS); 7 exceed 1000 lines, led by `audio_stream_controller.py` at 1962L.

**Correctness spillover** (NOT counted as tech-debt findings — routed to owning audits):
- `content_analyzer._estimate_dynamic_range` hard-codes `window_size = 44100` → wrong DR at 48/96 kHz → **/audit-engine** (see TD4-05).
- `webm_streaming` advertises `chunk_duration=10` while backend emits 15s chunks → client seek/total-chunks mismatch → **/audit-backend** + **/sync-contracts** (see TD4-03).
- `playlists.py` returns HTTP 500 for transient `OperationalError` instead of retryable 503 → **/audit-backend** (see TD3-02).
- Chunk-boundary regression tests are skipped while #3803 (CRITICAL) is open → **/audit-engine** owns the bug (see TD6-04).

---

## Baseline Snapshot (Phase 1 — for next audit to diff)

```
TODO/FIXME/HACK/XXX (py):     0
TODO/FIXME/HACK/XXX (ts):     2
NotImplementedError:          2
type: ignore (py):            162
@ts-ignore/@ts-expect-error:  2
': any' / 'as any' (ts):      557
skipped tests (py):           90
skipped tests (ts):           3
py files >300 LOC:            107
ts/tsx files >300 LOC:        173
allow(dead_code) (rust):      0
```
Path-reference validate gate: **PASS** — all 164 backticked refs across 25 skill files resolve.

---

## Top 10 Quick Wins (trivial/small effort, immediate payoff)

1. **TD5-04** *(MEDIUM, trivial)* — `queue_statistics.ts:222` `extractGenre()` always returns `'unknown'`. One-line fix `return track.genre ?? 'unknown'` un-breaks the live genre stats panel.
2. **TD7-01..04** *(trivial)* — Fix the version-drift constellation: set `pyproject.toml` and `auralis/__init__.py` to import from `auralis.version`; correct `system.py` fallback `db_schema_version` 3→16.
3. **TD2-03** *(trivial)* — Delete dead `typing.Annotated` + `fastapi.Path` imports in 6 routers (+ `artwork.py`).
4. **TD4-01/02** *(trivial/small)* — Replace duplicated `CHUNK_DURATION/INTERVAL/...` literals in `chunked_processor.py` and `cache/manager.py` with imports from `chunk_boundaries.py`.
5. **TD7-11** *(small)* — Remove all 13 `python -m auralis.library.init` instructions from docs (command never existed).
6. **TD10-01/02/03** *(trivial)* — Fix stale counts in `_audit-common.md` (18→15 routers, 92→83 analysis files, 21→18 test dirs) that propagate into every audit.
7. **TD8-11 + TD8-12** *(trivial)* — Delete the 35-line commented-out player REST block and 10 `# REMOVED (Phase N)` tombstones (CLAUDE.md: no breadcrumbs).
8. **TD2-06** *(trivial)* — Delete duplicate `from collections import deque` in `learning_system.py:17`.
9. **TD4-08** *(trivial)* — Replace two bare `30.0` literals in `audio_stream_controller.py` with the named `CHUNK_PROCESS_TIMEOUT`.
10. **TD8-15 + TD2-18** *(trivial)* — Delete deprecated zero-consumer artifacts: `useAppKeyboardShortcuts` (+test), `useAlbumsQueryLegacy` alias, `selectLastUpdate` alias.

---

## Top 5 Medium Investments (consolidations & splits)

1. **TD3-02** *(MEDIUM, medium)* — Migrate the 16 routers still hand-rolling `try/except HTTPException` to the existing `@with_error_handling` decorator. Do `playlists.py` first to close the 500→503 retryability gap.
2. **TD3-03** *(large)* — Extract `useAudioStreamingCore(streamType, options)` from `usePlayNormal`/`usePlayEnhanced` (~500 verbatim-shared lines). Stops future audio bugs landing in one hook but not the other.
3. **TD9-01** *(large)* — Split `audio_stream_controller.py` (1962L): `SimpleChunkCache` → `chunk_cache.py`; the three streaming coroutines → `stream_handlers.py`; `_send_*` → `stream_protocol.py`.
4. **TD9-02** *(large)* — Decompose `simple_mastering.py` (1551L, 288L god-method) into a `stages/` package, one DSP transform per module.
5. **TD3-04** *(medium)* — Collapse `common_metrics.py` (1178L re-implementation, 13 callers) into a re-export of the canonical `fingerprint/metrics/` submodule, then delete. (Also resolves the Dim 9 1178-line offender.)

---

# Findings

## MEDIUM

### TD3-02: Raw `try/except HTTPException` boilerplate — 56 instances, not migrated to `with_error_handling`
- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/library.py` (15) · `playlists.py` (8, divergent) · `similarity.py` (7) · `albums.py` (4) · `artwork.py` (4) · `metadata.py` (4) · `settings.py` (4); `artists.py` already uses `@with_error_handling`
- **Status**: NEW
- **Age**: `with_error_handling` added in `7c541aab`; `playlists.py` last touched `18bdead0` without migration
- **Effort**: medium
- **Description**: `routers/dependencies.py:151-218` defines `with_error_handling(operation)` and `routers/errors.py` defines `handle_query_error()` (maps SQLAlchemy `OperationalError`→HTTP 503, the #3222 fix). Only `artists.py` uses the decorator. 16 of 18 routers still carry the 5-line boilerplate. The divergence is not cosmetic: **`playlists.py` raises hard 500 for any exception including transient SQLite `OperationalError`, while the fixed path returns retryable 503.** The bug was fixed in `errors.py` (#3222) but never propagated to `playlists.py` — qualifies for MEDIUM via the "divergent bug-fix history" promotion trigger.
- **Evidence**:
  ```python
  # playlists.py:89-93 (divergent — always 500)
  except Exception as e:
      logger.error(f"Failed to get playlists: {e}")
      raise HTTPException(status_code=500, detail="Failed to get playlists")
  # albums.py:86-89 (correct — handle_query_error → 503 for OperationalError)
  except Exception as e:
      raise handle_query_error("get albums", e)
  ```
- **Impact**: Clients hitting playlist endpoints during a transient SQLite lock get non-retryable 500. Any future error-mapping change must touch 56 call sites.
- **Siblings**: `similarity.py`, `artwork.py`, `metadata.py`, `settings.py`, `library.py` carry the same boilerplate (most delegate to `handle_query_error`; the worst divergence is `playlists.py`).
- **Related**: #3222; `routers/errors.py`; `routers/dependencies.py`. **Correctness side of `playlists.py` → /audit-backend.**
- **Suggested Fix**: Apply `@with_error_handling("...")` to all endpoints in the 6 raw routers, mirroring `artists.py`. Migrate `playlists.py` first to close the 503 gap.

### TD5-04: `QueueStatistics.extractGenre()` always returns `'unknown'` — genre panel permanently broken
- **Severity**: MEDIUM
- **Dimension**: Stub Implementations
- **Location**: `auralis-web/frontend/src/utils/queue/queue_statistics.ts:222-225`
- **Status**: NEW
- **Age**: `b094e489` 2026-05-26
- **Effort**: small
- **Description**: `extractGenre()` returns the hardcoded `'unknown'` with a "placeholder / In a real app…" comment. `calculateStats()` calls it for every queued track; `calculateStats()` is reached via `useQueueStatistics(queue)` (exported from `hooks/player/index.ts`) wired into the live `QueueStatisticsPanel`. The panel therefore always shows `unknown: 100%`. The `Track` model already carries `genre`. Reachable from a shipped UI surface → MEDIUM.
- **Evidence**:
  ```typescript
  private static extractGenre(_track: Track): string {
    // For now, we'll use a placeholder
    return 'unknown';
  }
  ```
  Call path: `QueueStatisticsPanel` → `useQueueStatistics` → `QueueStatistics.calculateStats()` → `extractGenre()`.
- **Impact**: Genre distribution is uselessly always `unknown`, silently — no error surfaced.
- **Siblings**: TD5-05 (`AnalysisExportService` placeholder content).
- **Related**: `hooks/player/useQueueStatistics.ts`, `QueueStatisticsPanel`.
- **Suggested Fix**: `return track.genre ?? 'unknown'`. One line.

### TD5-06: `usePlaylistContextActions.onPlay` fires a toast but never loads tracks — "Play playlist" is a UI stub
- **Severity**: MEDIUM
- **Dimension**: Stub Implementations
- **Location**: `auralis-web/frontend/src/components/playlist/usePlaylistContextActions.ts:31-37`
- **Status**: NEW *(absorbs Dim 1 marker TD1-02)*
- **Age**: `c2034220` 2026-03-22
- **Effort**: small
- **Description**: The playlist context-menu "Play" action calls `info("Playing playlist: X")` and `onPlaylistSelect(id)` (navigation only), then leaves `// TODO: Implement play playlist`. The hook feeds `PlaylistList.tsx` → `SidebarContent.tsx`, so the "Play" item is visible/clickable in the shipped sidebar. Clicking shows a toast implying playback while nothing plays. Reachable from UI → MEDIUM.
- **Evidence**:
  ```typescript
  onPlay: () => {
    info(`Playing playlist: ${playlist.name}`);
    if (onPlaylistSelect) onPlaylistSelect(playlist.id);  // navigates only
    // TODO: Implement play playlist
  },
  ```
- **Impact**: Silent UX failure — misleading toast + navigation, no audio, no error.
- **Siblings**: `useQueueHistory.redo` throws `Error('Redo not yet implemented')` (sibling stubbed-UI-action; tracked under #3805).
- **Related**: `PlaylistList.tsx:144`, `SidebarContent.tsx:74`.
- **Suggested Fix**: Fetch tracks via `GET /api/playlists/{id}/tracks` and dispatch to the Redux queue (same as "play album"), or disable the menu item and drop the toast until implemented.

---

## LOW

### Dimension 2 — Dead Code & Unused Surface

> Tooling: `pyflakes` (Python), `npx ts-prune` (TS), AST-confirmed, grep-verified.

#### TD2-01: Three unused imports in `simple_mastering.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `47ae0db9` 2026-05-27
- **Location**: `auralis/core/simple_mastering.py:21,23,29`
- **Description**: `amplify`, `AdaptiveLoudnessControl`, `ExpansionStrategies` imported, never referenced in the 1551-line file. (`normalize` on line 21 *is* used — keep it.)
- **Suggested Fix**: Drop `amplify` from line 21; delete lines 23 and 29.
- **Siblings**: TD2-02 (same file cluster).

#### TD2-02: `SafetyLimiter` unused import in `continuous_mode.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `3351cdd5` 2026-05-27
- **Location**: `auralis/core/processing/continuous_mode.py:33-37`
- **Description**: `SafetyLimiter` imported from `.base`, never used (real limiting goes via `HFAwareLimiter`).
- **Suggested Fix**: Remove `SafetyLimiter` from the `.base` import block.

#### TD2-03: `typing.Annotated` + `fastapi.Path` dead-import cluster — 6 router files
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `51e26c68` 2026-05-29
- **Location**: `routers/metadata.py:19,22` · `playlists.py:23,26` · `cache_streamlined.py:13,17` · `similarity.py:14,17` · `artists.py:12,15` · `library.py:26,29`
- **Description**: Leftover from a refactor that replaced typed path params with plain args. `artwork.py` also has dead `Annotated` (its `pathlib.Path` IS used — only remove `fastapi.Path`).
- **Suggested Fix**: Remove `Annotated` from `typing` and `Path` from `fastapi` in each.

#### TD2-04: `import time` unused in `helpers.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis-web/backend/helpers.py:469`
- **Description**: Module-level `import time`; the `time.time()` it served was removed (comment at line 597). 
- **Suggested Fix**: Delete line 469.

#### TD2-05: `import struct` dead import in `processing_api.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `c5a1568a` 2026-05-30
- **Location**: `auralis-web/backend/routers/processing_api.py:15`
- **Suggested Fix**: Delete line 15.

#### TD2-06: Duplicate `deque` import in `learning_system.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `0417064f` 2026-03-22
- **Location**: `auralis-web/backend/services/learning_system.py:14,17`
- **Description**: `deque` imported twice (line 14 covers it already).
- **Suggested Fix**: Delete line 17.

#### TD2-07: `serialize_albums` imported but never called in `library.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `51e26c68` 2026-05-29
- **Location**: `auralis-web/backend/routers/library.py:35,37`
- **Description**: Only real caller is `albums.py`; copy-paste artifact creating false coupling.
- **Related**: #3892 (serializer debt — thematically related).
- **Suggested Fix**: Remove `serialize_albums` from the `.serializers` import.

#### TD2-08: Unused `pathlib.Path` in `enhancement.py` and `typing.Any` in `path_security.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `routers/enhancement.py:21` · `security/path_security.py:16`
- **Suggested Fix**: Delete both unused import lines.

#### TD2-09: `ProcessorFactory` unused import in `chunked_processor.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `0c2424d4` 2026-05-29
- **Location**: `auralis-web/backend/core/chunked_processor.py:46`
- **Description**: Factory is injected via constructor (`self._processor_factory`); the top-level import is dead and confuses DI reading.
- **Suggested Fix**: Remove line 46.

#### TD2-10: `pathlib.Path` unused in `factory.py`; `sqlalchemy.text` unused in `migration_manager.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis/library/repositories/factory.py:13` · `auralis/library/migration_manager.py:19`
- **Suggested Fix**: Delete both import lines.

#### TD2-11: `mutagen.id3.APIC` unused import in `artwork.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `2ff696c9` 2026-02-13
- **Location**: `auralis/library/artwork.py:17`
- **Description**: `ID3` used, `APIC` class never instantiated.
- **Suggested Fix**: `from mutagen.id3 import ID3`.

#### TD2-12: `watchdog.events.FileSystemEvent` unused in `library_auto_scanner.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `e07cdb2c` 2026-05-29
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:29`
- **Suggested Fix**: Remove the `FileSystemEvent` import.

#### TD2-13: `asyncio` and `LibraryScanner` unused imports in `startup.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `e07cdb2c` 2026-05-29
- **Location**: `auralis-web/backend/config/startup.py:17,84`
- **Description**: `import asyncio` (zero uses) implies async infra the file lacks; `LibraryScanner` is an unused probe import.
- **Related**: MEMORY.md — `_background_auto_scan` replaced by `LibraryAutoScanner`.
- **Suggested Fix**: Delete line 17; for line 84 alias as `_scanner_probe` (matching `main.py` pattern) or remove.

#### TD2-14: `SmoothAnimationEngine.ts` — 721-line module with zero production consumers
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `ef3f32d6` 2026-05-30
- **Location**: `auralis-web/frontend/src/utils/SmoothAnimationEngine.ts:1-721`
- **Description**: Exports `EasingFunctions`, `SmoothAnimationEngine`, `globalAnimationEngine`, `useSmoothAnimation` — zero importers anywhere in `src/`. `performanceOptimizer.ts` already duplicated the easing logic. Still receiving type-fix commits despite being orphaned. **Supersedes the Dim 9 top-offenders row for this file — delete, do not split.**
- **Siblings**: `performanceOptimizer.ts:65-107` (duplicate `EasingFunctions` incl. deprecated bounce easings).
- **Suggested Fix**: Delete the file; remove the deprecated `easeIn/OutElastic/Bounce` entries from `performanceOptimizer.ts`.

#### TD2-15: `src/a11y/` — 2.5K-line accessibility toolkit with near-zero app consumers
- **Severity**: LOW · **Effort**: large · **Status**: NEW · **Age**: created `62733980` 2025-11-28; last touched `69280b29` 2026-05-30
- **Location**: `src/a11y/wcagAudit.ts` (631) · `ariaUtilities.ts` (400) · `contrastChecker.ts` (342) · `useKeyboardNavigation.ts` (433) · `index.ts` (255) + 444-line self-test
- **Description**: Only real consumer is `useDialogAccessibility.ts` importing `focusManager` from `@/a11y/focusManagement` (bypassing the barrel). `wcagAudit`, `contrastChecker`, `ariaUtilities`, `useKeyboardNavigation` have zero `src/` consumers; WCAG audit fns never integrated into CI/dev panel. Active bugfixes applied to dead surface.
- **Related**: #2617–#2620 (a11y findings the toolkit was meant to address but never wired in).
- **Suggested Fix**: Keep `focusManagement.ts`; delete the other four modules + `index.ts` + `__tests__/a11y.test.ts`. (Supersedes TD2-22 sub-finding `wcagCriteria`.)

#### TD2-16: `config/features.ts` — feature-flag helpers never imported
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `110290ec` 2025-10-30
- **Location**: `auralis-web/frontend/src/config/features.ts:31,38`
- **Description**: `FEATURES`, `isFeatureEnabled()`, `getEnabledFeatures()` have zero importers; both flags hardcoded `true`. `MSE_DEBUG: true` in production is likely unintentional.
- **Suggested Fix**: Delete the helpers; set `MSE_DEBUG: false` or remove. Use `import.meta.env.*` if toggling is later needed.

#### TD2-18: `selectLastUpdate` deprecated alias in `cacheSlice.ts`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `cb3f1107` 2026-05-30
- **Location**: `auralis-web/frontend/src/store/slices/cacheSlice.ts:177-178`
- **Description**: `@deprecated` alias for `selectLastUpdated`, zero consumers.
- **Suggested Fix**: Delete lines 177-178.

#### TD2-19: Duplicate `compute_rms` / `estimate_lufs` private functions in Rust DSP
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `5393d122` 2025-12-17
- **Location**: `vendor/auralis-dsp/src/fingerprint_compute.rs:102,129` · `variation_analysis.rs:25,35`
- **Description**: Functionally-equivalent RMS/LUFS implemented independently in two modules; `estimate_lufs` signatures already differ (one takes `sample_rate`), inviting silent divergence.
- **Suggested Fix**: Extract to `src/dsp_math.rs` with `pub(crate)` visibility; both modules import.

#### TD2-20: Stale `type: ignore[name-defined]` on `np.ndarray` in `chunk_boundaries.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `593145fe` 2026-03-22
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:196,199`
- **Description**: String-literal `"np.ndarray"` annotations + suppression, but `numpy as np` is at module scope (line 14) — both unnecessary; they mask any future real `name-defined` error.
- **Suggested Fix**: Unquote `np.ndarray`, delete both `# type: ignore[name-defined]`.

#### TD2-21: `type: ignore[unreachable]` cluster masking reachable post-guard code (9 sites)
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `monitoring/metrics_collector.py:117,263` · `core/chunked_processor.py:193,652,670` · `routers/similarity.py:405,427`
- **Description**: After `if not X: raise/return`, mypy narrows `X` to `Never` and marks the continuing (runtime-reachable) line unreachable. 9 suppressions look like dead-code markers.
- **Suggested Fix**: Replace each with `assert X is not None` before the post-guard statement.

#### TD2-23: Local `import os` inside function body, unused
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis/services/fingerprint_extractor.py:281`
- **Description**: Local `import os` never used (pathlib handles filesystem ops); evaluated on every call. (`import time` on line 282 IS used — keep.)
- **Suggested Fix**: Delete the `import os`.

---

### Dimension 3 — Logic Duplication

#### TD3-01: Repository session-lifecycle boilerplate repeated across all 12 repositories
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: every file under `auralis/library/repositories/` (e.g. `album_repository.py:24-32`, `track_repository.py:26-39`, … all 12)
- **Description**: Each repo independently defines identical `__init__(self, session_factory)` + 2-line `get_session()`; the `session=get_session()`→`try`→`finally: session.close()` pattern repeats ~110×. No base class. Any session-lifecycle change (pooling instrumentation, async support) is a 12-file edit with partial-update risk.
- **Siblings**: `finally: session.close()` ×114; `session.expunge` ×78 across the same files.
- **Related**: `repositories/factory.py` (natural home).
- **Suggested Fix**: Add `repositories/base.py` `BaseRepository` with `__init__`, `get_session()`, and a `_with_session(fn)` context-manager helper; all 12 inherit.

#### TD3-03: `usePlayNormal` and `usePlayEnhanced` share ~500 lines of identical streaming machinery
- **Severity**: LOW · **Effort**: large · **Status**: NEW
- **Location**: `hooks/enhancement/usePlayNormal.ts:148-678` · `usePlayEnhanced.ts:174-942`
- **Description**: Identical ref declarations, `cleanupStreaming()`, `handleStreamStart` AudioContext logic, `handleChunk` 75%/50% flow-control, `handleStreamEnd/Error`, and the 4-event WS subscription `useEffect`. They differ only in stream-type tag and enhanced's `preset/intensity/seekTo/fingerprint` extras. `usePlayNormal` even comments "Mirror usePlayEnhanced" (line 403) — drift will land audio bugs in one hook only.
- **Evidence**: identical flow-control block at `usePlayNormal:376-383` and `usePlayEnhanced:479-487`.
- **Related**: #2604, #3588.
- **Suggested Fix**: Extract `hooks/enhancement/useAudioStreamingCore.ts` holding shared refs + `cleanupStreaming` + `handleChunk` + `handleStreamEnd/Error` + WS subscription effect; both hooks supply only their stream-type-specific `handleStreamStart`.

#### TD3-04: `common_metrics.py` — 1178-line re-implementation of the `metrics/` submodule, 13 active callers
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `2ff696c9` 2026-02-13
- **Location**: `auralis/analysis/fingerprint/common_metrics.py:1-1178` vs canonical `fingerprint/metrics/{normalization,safe_operations,audio_metrics,aggregation}.py`
- **Description**: Self-labelled "DEPRECATED" but still contains complete standalone copies of all five utility classes (not re-exports). 13 callers in `analysis/` still import it; `metrics/` has 51+ callers. Two independently-maintained copies of normalization/safe-math/audio-metric logic. **Also the Dim 9 #3 top-offender (1178L) — deletion resolves both the duplication and the complexity.**
- **Evidence**: `normalize_to_range` byte-identical at `common_metrics.py:252-279` and `metrics/normalization.py:58-84`.
- **Suggested Fix**: Replace class bodies with `from .metrics import …`, migrate the 13 callers to `.metrics` directly, delete `common_metrics.py`.

#### TD3-05: `dsp/basic.py` `channel_count()`/`size()` duplicated in `dsp/utils/audio_info.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis/dsp/basic.py:17-26` · `auralis/dsp/utils/audio_info.py:15-40` · stale importers `auralis/core/processor.py:16` + `desktop/resources/auralis/core/processor.py:16`
- **Description**: Refactor moved these helpers to `audio_info.py` but left the originals in `basic.py`. `unified.py` re-exports the canonical copy, but `processor.py` (hot path) imports the stale `basic` path — a fix to `audio_info` (e.g. >2-channel handling) would silently not reach it.
- **Suggested Fix**: Delete the two functions from `basic.py`; point `processor.py` (both copies) at `auralis.dsp.utils.audio_info`.

---

### Dimension 4 — Magic Numbers & Hardcoded Constants

#### TD4-01: `chunked_processor.py` redeclares chunk constants already in `chunk_boundaries.py`
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `dd55f058`
- **Location**: `auralis-web/backend/core/chunked_processor.py:66-70`
- **Description**: Locally redefines `CHUNK_DURATION=15`, `CHUNK_INTERVAL=10`, `OVERLAP_DURATION=5`, `CONTEXT_DURATION=5` — the exact values `chunk_boundaries.py` declares as "SINGLE SOURCE OF TRUTH". Drift → silent wrong segment sizes/counts.
- **Siblings**: TD4-02, `chunk_operations.py:45-47` (hardcoded defaults).
- **Suggested Fix**: Import the four constants from `core.chunk_boundaries`; promote `MAX_LEVEL_CHANGE_DB` into `chunk_boundaries.py`.

#### TD4-02: `cache/manager.py` redeclares chunk-duration constants
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `68e05a1b`
- **Location**: `auralis-web/backend/cache/manager.py:27-28` (+ re-exported by `cache/__init__.py:23-24,48-49`)
- **Description**: Own `CHUNK_DURATION=15.0`/`CHUNK_INTERVAL=10.0` used for cache index arithmetic — a third copy; drift → cache misses/stale data.
- **Suggested Fix**: Import from `core.chunk_boundaries`; re-export from there in `cache/__init__.py`.

#### TD4-03: `webm_streaming.py` factory default `chunk_duration=10` conflicts with canonical 15
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `09f87be1`
- **Location**: `auralis-web/backend/routers/webm_streaming.py:145-146`
- **Description**: `create_webm_streaming_router()` defaults `chunk_duration=10`; the sole caller passes nothing, so the default is live and conflicts with `CHUNK_DURATION=15`. `StreamMetadata` advertises 10s chunks while the processor emits 15s → wrong `total_chunks` and seek mapping on the client.
- **Related**: **Latent client-server contract bug → /audit-backend + /sync-contracts.**
- **Suggested Fix**: Default the params from `core.chunk_boundaries.CHUNK_DURATION/CHUNK_INTERVAL`.

#### TD4-04: `audio_content_predictor.py` hardcodes `chunk_duration=10.0` instead of `CHUNK_INTERVAL`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `b15f5f5d`
- **Location**: `auralis-web/backend/services/audio_content_predictor.py:139`
- **Description**: `_load_chunk_fast` uses a bare `10.0` (really the chunk *interval*) for offset/frame math; chunk-model change → reads the wrong window → wrong content features.
- **Suggested Fix**: Import and use `CHUNK_INTERVAL`.

#### TD4-05: `content_analyzer.py` hard-codes `window_size=44100` instead of `self.sample_rate`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `2ff696c9`
- **Location**: `auralis/core/analysis/content_analyzer.py:381`
- **Description**: `_estimate_dynamic_range` uses a fixed 44100-sample window though `self.sample_rate` is available; at 48k it's 0.92s, at 96k 0.46s → biased DR estimates feeding preset selection.
- **Related**: **Latent correctness bug → /audit-engine.** Siblings: `content_analysis_facade.py:211-214` (bare 512), `dsp/utils/spectral.py:231-232` (bare 1024/512).
- **Suggested Fix**: `window_size = int(DYNAMIC_RANGE_WINDOW_SECONDS * self.sample_rate)` with `DYNAMIC_RANGE_WINDOW_SECONDS=1.0` in `core/config.py`.

#### TD4-06: `resonance_notcher.py` hard-codes `N=16384` FFT size
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `4c5b62a2`
- **Location**: `auralis/core/dsp/resonance_notcher.py:86`
- **Description**: Welch PSD window fixed at 16384 samples while the companion notch-separation `distance` was *already* made sample-rate-aware — resolution silently varies by rate (≈5.9 Hz bins @96k vs ≈1.35 Hz @22k).
- **Suggested Fix**: Anchor in time: `RESONANCE_FFT_WINDOW_SECONDS=0.37` in `core/config.py`; `N = max(4096, next_pow2(int(sec*sr)))`.

#### TD4-07: `AudioPlaybackEngine.ts` — multiple bare buffer-geometry constants
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `fa225c12`
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:35-36,71-80`
- **Description**: `fftSize=2048`, `smoothingTimeConstant=0.8`, `bufferSize=4096`, `minBufferSamples=96000`, `lowWaterMarkSeconds=5.0`, `highWaterMarkSeconds=8.0`, `setInterval(...,50)` — latency/underrun knobs with hidden relationships to the backend `CHUNK_INTERVAL=10`.
- **Suggested Fix**: Extract a `PLAYBACK_ENGINE_CONFIG` object (or `audioConstants.ts`) with JSDoc relating water-marks to the backend chunk interval.

#### TD4-08: `audio_stream_controller.py` uses raw `30.0` at two sites, bypassing `CHUNK_PROCESS_TIMEOUT`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `09f87be1`
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:633,1780` (named constant defined line 95, used correctly at 1180)
- **Description**: Two processor-init `asyncio.wait_for(timeout=30.0)` calls bypass the named constant; tuning the timeout silently misses them.
- **Siblings**: `webm_streaming.py:393,409` (`timeout=30.0` for WAV reads).
- **Suggested Fix**: Use `CHUNK_PROCESS_TIMEOUT` (or extract a `PROCESSOR_INIT_TIMEOUT`).

#### TD4-09: `_MAX_UPLOAD_BYTES` defined independently in two routers
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `19dc841c`
- **Location**: `routers/files.py:138` · `routers/processing_api.py:31`
- **Description**: Both define `500 * 1024 * 1024` separately; an operator changing the cap must edit two files.
- **Suggested Fix**: Move `MAX_UPLOAD_BYTES` (and `MAX_ARTWORK_BYTES`, `MAX_MESSAGE_SIZE`) into a single `backend/config/limits.py`.

---

### Dimension 5 — Stub & Placeholder Implementations
*(Dim 1's three stale markers were reclassified here, since reachability is the deciding axis.)*

#### TD5-01: `HybridProcessor.process()` str-path raises `NotImplementedError` — type advertises unimplemented file-path support
- **Severity**: LOW · **Effort**: small · **Status**: NEW *(absorbs Dim 1 marker TD1-03)* · **Age**: `3351cdd5` 2026-05-27
- **Location**: `auralis/core/hybrid_processor.py:207-213,242-243,294-295,380-381,447-452`
- **Description**: `process()` declares `target: str | np.ndarray`; the `str` branch calls `_load_audio_placeholder()` which raises. All production callers pre-load with `load_audio()` and pass arrays — not reachable from any shipped route today. But `process_adaptive/reference/hybrid` wrappers advertise `target: Any` and would hit it.
- **Suggested Fix**: Drop `str` from the unions, delete `_load_audio_placeholder` — or implement it via `UnifiedLoader.load()`.

#### TD5-02: Rust `median_filter_vertical/horizontal` return all-zeros stubs
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW *(absorbs Dim 1 marker TD1-01)* · **Age**: `0e7ee0aa` 2025-11-24
- **Location**: `vendor/auralis-dsp/src/median_filter.rs:8-17`
- **Description**: Two `pub fn` return `Array2::zeros(...)` with `// TODO`. `hpss.rs` uses its own private copies; the module is `pub mod` but not re-exported via `pub use`, so it's unreachable from the Python boundary. Not reachable → LOW, but any future external caller gets silent zeros.
- **Suggested Fix**: Promote the working `hpss.rs` implementations into `median_filter.rs` and delete the private duplicates, or delete `median_filter.rs` + its `pub mod`.

#### TD5-03: `ArtworkService.fetch_album_artwork()` logs "not yet implemented", returns `None`
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `f79be6fa` 2026-02-21
- **Location**: `auralis/services/artwork_service.py:264-282`
- **Description**: Unconditionally returns `None`. Only imported by two CLI scripts, never from a route; the artist path (`fetch_artist_artwork`) is fully implemented.
- **Suggested Fix**: Implement via the existing MusicBrainz/CoverArtArchive pattern, or delete the method + CLI usage.

#### TD5-05: `AnalysisExportService.exportAsPDF()` returns plain text as `application/pdf`
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `059ac4ad` 2026-05-26
- **Location**: `auralis-web/frontend/src/services/AnalysisExportService.ts:565-593`
- **Description**: `generatePDFContent()` returns a text string served with `mimeType='application/pdf'` and `.pdf` extension — a corrupt PDF. Dormant: `useAnalysisExport()` is imported by no component. (Same file is the Dim 9 TD9-08 size offender.)
- **Suggested Fix**: Implement with jsPDF/pdfmake, or remove `'pdf'` from the `ExportFormat` union and the switch case.

---

### Dimension 6 — Test Hygiene

#### TD6-01: `test_library_integration.py` — 16 tests permanently skipped as "DEPRECATED"
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `cf644a77` 2025-11-13
- **Location**: `tests/integration/test_library_integration.py:71-660`
- **Description**: All 16 tests skipped (>6 months) for using the old `LibraryScanner.scan_folder`/`TrackRepository.get_all()` API; no replacement written. Library scan→persist→query has no running integration test.
- **Related**: #3923.
- **Suggested Fix**: Delete the file; open a tracking issue to rewrite against `LibraryAutoScanner` + `TrackRepository.add()`.

#### TD6-02: `test_thread_safety.py` — 13 `xfail` markers, vague reasons, no issue refs, no `strict`
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `8a5ecc5e` 2025-11-09
- **Location**: `tests/concurrency/test_thread_safety.py:84,130,166,212,262,299,469,532,582,606,635,817,851`
- **Description**: 13/18 thread-safety methods `xfail("API compatibility…"/"complex fixtures")`, none `strict=True` → XPASS is swallowed, so a real pass (or regression) is invisible. Covers RLock ordering & concurrent-DB-write safety.
- **Siblings**: `tests/concurrency/test_parallel_processing.py:279,374,673,709`.
- **Related**: #3781, #3808, #3736.
- **Suggested Fix**: Fix fixtures and remove markers, or convert to `skip` with issue ref + `strict=True` on any retained xfail; the "complex fixtures" cluster can use the existing `temp_db` conftest fixture.

#### TD6-03: `test_concurrent_connection_cleanup` skip guards a known unfixed migration race, no issue
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `fa18a719` 2025-11-18
- **Location**: `tests/backend/test_concurrent_operations.py:386`
- **Description**: Unconditional skip ("migrations are not thread-safe") with no tracking issue → the known `LibraryManager.__init__` migration race is invisible to the backlog.
- **Suggested Fix**: Open an issue, add its number to `reason=`, propose the existing inter-process migration-lock pattern.

#### TD6-04: 8 boundary tests skipped for "Missing module: auralis_web/player" after relocation
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `816a0594` 2025-11-07
- **Location**: `tests/backend/test_boundary_exact_conditions.py:215,254,294,367,533` · `test_boundary_max_min_values.py:101,261`
- **Description**: Chunk-boundary tests import `from auralis_web.backend.chunked_processor import …` (wrong dotted path); the module exists at `auralis-web/backend/core/chunked_processor.py`. They cover the exact domain of CRITICAL open #3803.
- **Related**: **#3803 owns the bug → /audit-engine.**
- **Suggested Fix**: Fix the import path / `sys.path`, remove the skips.

#### TD6-05: `test_enhanced_player_detailed.py` — two whole test classes skipped 6+ months (fixture)
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `f365c009` 2025-11-29
- **Location**: `tests/auralis/player/test_enhanced_player_detailed.py:38,136`
- **Description**: `TestQueueManager` + `TestEnhancedAudioPlayerCore` skipped for "DB migration errors — requires conftest fixture integration"; perpetuates the player's total coverage gap.
- **Related**: #2601, #3997.
- **Suggested Fix**: Use the `repository_factory` conftest fixture (handles migration) instead of constructing `LibraryManager` in the player ctor under test; re-enable.

#### TD6-06: `test_full_stack.py` — 4 functions permanently skipped; not valid tests
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `147d6acb` 2025-10-28
- **Location**: `tests/backend/test_full_stack.py:16,74,105,140`
- **Description**: All skipped since Oct 2025; bodies `print`, `subprocess.Popen`, and `return True` (pytest ignores returns) — not runnable even if unskipped.
- **Related**: #3819.
- **Suggested Fix**: Delete the file; if needed, write a real `uvicorn`+`httpx` integration test behind an env-var/`@pytest.mark.integration` guard.

#### TD6-07: `test_phase7b_remaster_comparison.py` — no assertions, hardcoded developer-local paths
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `1dee221a` 2025-11-26
- **Location**: `tests/test_phase7b_remaster_comparison.py:271`
- **Description**: Zero `assert`s; paths hardcoded to `/mnt/Musica/...`; passes trivially in CI (existence checks short-circuit). A debug script committed as a test.
- **Siblings**: `tests/test_phase7a_sampling_integration.py:441` (print-only summary "test").
- **Suggested Fix**: Delete the file; if worth testing, use synthesized audio (conftest sine generators) with a correlation/feature-distance assertion.

#### TD6-08: SQL-injection artwork test skipped because `AlbumRepository.create()` doesn't exist
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `tests/backend/test_artwork_security.py:235`
- **Description**: `test_sql_injection_artwork_path_blocked` permanently skipped, no issue ref → artwork-endpoint SQLi protection is untested (a security regression test).
- **Suggested Fix**: Rewrite to create an album via `track_repository.add(...)`, then exercise the artwork endpoint with a malicious path; remove the skip.

#### TD6-09: Cluster of 31 tests whose only assertion is `assert X is not None`
- **Severity**: LOW · **Effort**: medium · **Status**: NEW
- **Location**: 31 functions across `tests/backend/test_boundary_*`, `tests/boundaries/test_string_input_boundaries.py`, `tests/integration/test_e2e_workflows.py:880,902,962`, etc.
- **Description**: Smoke-only asserts; many wrap the call in `try/except → pytest.skip`, silencing real failures. Empty lists, wrong types, corrupted audio all pass.
- **Suggested Fix**: Assert result type + meaningful properties; remove the `try/except → skip` so the API throwing fails the test.

#### TD6-10: `test_async_operations.py` uses `xfail` instead of `skipif` for server-dependent tests
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `8a5ecc5e` 2025-11-09
- **Location**: `tests/concurrency/test_async_operations.py:30,46`
- **Description**: `xfail("Requires running FastAPI server")` without `strict=True` — semantically "broken", and XPASS is swallowed if a server happens to be up.
- **Suggested Fix**: `@pytest.mark.skipif(not _server_available(), ...)` or an `@pytest.mark.integration` + env-var guard.

---

### Dimension 7 — Stale Documentation & Comments

#### TD7-01: `pyproject.toml` version three minors behind `version.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `pyproject.toml:7` (`1.1.0.beta.5` vs SoT `1.2.1-beta.2`)
- **Siblings**: `auralis/__init__.py:14` hardcodes `1.0.0`.
- **Suggested Fix**: Set `pyproject.toml` to match; make `auralis/__init__.py` do `from auralis.version import __version__`.

#### TD7-02: `CLAUDE.md` / `README.md` quote `1.2.0-beta.3` (one release behind)
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `CLAUDE.md:4`, `README.md:9,15,94-115,364,435,450`
- **Suggested Fix**: Global-replace to `1.2.1-beta.2` (incl. installer filenames, badge URLs, changelog headers).

#### TD7-03: `routers/system.py` fallback hardcodes stale version and `db_schema_version=3`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis-web/backend/routers/system.py:104-116`
- **Description**: `/api/system/version` import-failure fallback reports `1.2.1-beta.1`, `build_date="2026-02-20"`, and `db_schema_version=3` while the live schema is **16** — could drive false "no migration needed" conclusions in monitoring.
- **Suggested Fix**: Remove the hardcoded fallback (or read `auralis.__version__.__db_schema_version__`).

#### TD7-04: `auralis/version.py` declares `DB_SCHEMA_VERSION=3` (actual 16)
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis/version.py:30`
- **Description**: The self-described SoT exports a 13-versions-stale schema number; `migration_manager.py` uses `auralis.__version__.__db_schema_version__=16` instead.
- **Suggested Fix**: Remove `DB_SCHEMA_VERSION` (point to `__version__.py`) or set to 16.

#### TD7-05: `CLAUDE.md` codebase-map counts all wrong
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `CLAUDE.md:49,64,80,100,102`
- **Description**: analysis `92→83`, repos `12→13`, routers `18→15`, "850+ tests/21 dirs" → ~4,600 functions/18 dirs, docs `20→21`.
- **Related**: TD10-01/02/03 (same numbers embedded in audit skill files).
- **Suggested Fix**: Update the five counts.

#### TD7-06: `README.md` / `FIRST_TIME_SETUP.md` / `DEVELOPMENT_SETUP_BACKEND.md` require Python 3.13 (actual 3.14+)
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `README.md:34,47-73`, `FIRST_TIME_SETUP.md:13,75,82,247`, `docs/development/DEVELOPMENT_SETUP_BACKEND.md:34,47-73`
- **Description**: `requires-python = ">=3.14"` — pip rejects 3.13, wasting setup time.
- **Suggested Fix**: Replace `3.13` → `3.14` (incl. `conda create ... python=3.14`).

#### TD7-07: `FIRST_TIME_SETUP.md` requires Node 20+ LTS (actual 24+)
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `5393d122` 2025-12-17
- **Location**: `FIRST_TIME_SETUP.md:14,252`
- **Suggested Fix**: `Node.js 20+` → `Node.js 24+`.

#### TD7-08: `WEBSOCKET_API.md` omits 18 of 35 message types; stale TS union
- **Severity**: LOW · **Effort**: medium · **Status**: NEW
- **Location**: `auralis-web/backend/WEBSOCKET_API.md:693-710` vs `frontend/src/types/websocket.ts:14-61`
- **Description**: The doc's `WebSocketMessageType` lists 17 members; the canonical type has 35. Missing include `audio_chunk_meta`, `audio_stream_start/end`, `fingerprint_progress`, queue/library/metadata variants.
- **Related**: #3873 (partial). **Cross-ref /sync-contracts.**
- **Suggested Fix**: Replace the stale block with a reference to `types/websocket.ts` + narrative for the four streaming messages.

#### TD7-09: `WEBSOCKET_API.md` has no docs for core audio-streaming S→C messages
- **Severity**: LOW · **Effort**: medium · **Status**: NEW
- **Location**: `WEBSOCKET_API.md` (absent) vs `audio_stream_controller.py:1479,1593,1620,1662,1685`
- **Description**: `audio_chunk_meta`, `audio_stream_start/end/error` — the messages that carry audio — are undocumented; integrators must reverse-engineer.
- **Suggested Fix**: Add an "Audio Streaming Messages" section with payload shapes; add them to the REST→WS mapping table.

#### TD7-10: `WEBSOCKET_API.md` references nonexistent files
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `e9f70a3c` 2025-10-23
- **Location**: `WEBSOCKET_API.md:641,716-717`
- **Description**: Points to `websocket_manager.py` (actually `config/globals.py:46`), `WEBSOCKET_CONSOLIDATION_PLAN.md` (absent), `docs/design/AURALIS_ROADMAP.md` (`docs/design/` absent).
- **Suggested Fix**: Fix line 641 to `config/globals.py`; remove/replace the dead links.

#### TD7-11: 13 doc occurrences of `python -m auralis.library.init` (command never existed)
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `b28373df` 2025-12-13
- **Location**: `docs/development/DEVELOPMENT_SETUP_BACKEND.md` (10×), `REPOSITORY_PATTERN.md:575`, `docs/phases/.../PHASE_A_IMPLEMENTATION_PLAN.md:253`, `docs/releases/RELEASE_NOTES_1_1_0_BETA4.md:236`
- **Description**: `auralis/library/` has no `__main__.py`. The very first Quick-Start step fails.
- **Suggested Fix**: Remove all 13; state "DB initializes automatically on first run"; for reset use `rm ~/.auralis/library.db`.

#### TD7-12: `docs/deployment/APPIMAGE_FIX.md` references nonexistent `build_auralis.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `f673499f` 2025-12-26
- **Location**: `docs/deployment/APPIMAGE_FIX.md:62,65,122,128,156`
- **Suggested Fix**: Replace with the real Electron packaging commands (`npm run package:linux` from `desktop/package.json`).

#### TD7-13: `README.md` links to nonexistent roadmap + `docs/archive/`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `README.md:53,354-356`
- **Description**: `DEVELOPMENT_ROADMAP_1_1_0.md` and `docs/archive/releases/RELEASE_NOTES_BETA9.*.md` do not exist.
- **Suggested Fix**: Remove/replace with existing docs (e.g. `docs/releases/CHANGELOG.md`).

#### TD7-14: `TESTING_GUIDELINES.md` shows stale test count (486), Python 3.11 / Node 18 CI, mutpy
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `5833e2fb` 2025-11-06
- **Location**: `docs/development/TESTING_GUIDELINES.md:28-30,376,1044,1066`
- **Description**: "486 tests" (actual ~4,600 functions), CI `python-version:'3.11'`/`node-version:'18'` (need 3.14/24), `pip install mutpy` for a CLI that isn't used.
- **Suggested Fix**: Update counts and CI versions; replace mutpy block with the `@pytest.mark.mutation` note (`python -m pytest -m mutation`).

---

### Dimension 8 — Backwards-Compat Cruft & "No Variants" Violations

> Auralis is desktop-only (no external API consumers) → compat shims/deprecations with only in-repo callers are pure rot: **delete, don't deprecate.**

#### TD8-01: `EnhancedAudioPlayer = AudioPlayer` alias propagated through the codebase
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `2ff696c9`
- **Location**: `auralis/player/enhanced_audio_player.py:797`, `auralis/__init__.py:38,49`; 5 callers (`navigation_service`, `playback_service`, `routers/player`, `routers/dependencies`, `config/startup`)
- **Description**: A "backward compatibility" alias re-exported in `__all__`; readers must resolve two names for one class. (Note: contrary to the severity-scale aside that treats `EnhancedAudioPlayer` as the real player, it is in fact an alias.)
- **Suggested Fix**: Delete the alias, update 5 callers to `AudioPlayer`, drop the `__all__` entry.

#### TD8-02..05: Four DSP backward-compat re-export wrapper modules
- **Severity**: LOW · **Effort**: small/trivial · **Status**: NEW · **Age**: `2ff696c9`
- **Location**: `auralis/dsp/unified.py` (caller: `advanced_dynamics.py:30`) · `auralis/dsp/psychoacoustic_eq.py` (3 callers) · `auralis/dsp/realtime_adaptive_eq.py` (3 callers) · `auralis/dsp/eq/parallel_eq_processor.py` (1 caller)
- **Description**: Flat-file "DEPRECATED: import from X instead" shims from the v1.1 modularization. TD8-04/05 additionally cause file-vs-package module-shadowing on the same import path. All callers are in-repo.
- **Suggested Fix**: Repoint each caller to the real module, delete the shims.

#### TD8-06: `base_processing_mode.py` — deprecated, fires `warnings.warn` on import, zero callers
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `cd083e63`
- **Location**: `auralis/core/processing/base_processing_mode.py:1-65`
- **Suggested Fix**: Delete the module.

#### TD8-07: `auralis/core/processor.py::process()` — 160-line deprecated wrapper, zero callers
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `2ff696c9`
- **Location**: `auralis/core/processor.py:28-186`, re-exported in `auralis/__init__.py:32,49` and `core/__init__.py:14`
- **Description**: `DeprecationWarning` "removed in v2.0.0"; no production callers. (Companion: `version.py:is_compatible()`, `API_VERSION`, `MIN_COMPATIBLE_VERSION` are also caller-less compat infra — remove in the same pass.)
- **Suggested Fix**: Delete `process()` and its `__all__` exports.

#### TD8-08: `auralis/core/unified_config.py` — backward-compat re-export, 7 callers
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `2ff696c9`
- **Location**: `auralis/core/unified_config.py:1-36`
- **Suggested Fix**: Repoint the 7 callers to `auralis.core.config`, delete the shim.

#### TD8-09: `auralis/analysis/spectrum_analyzer.py` — deprecated wrapper re-exported with `# type: ignore`
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `0048589e`
- **Location**: `auralis/analysis/spectrum_analyzer.py:1-100`, `analysis/__init__.py:15-21`; callers `quality_metrics.py:19`, `content_analysis.py:40`
- **Description**: The `# type: ignore[attr-defined]` suppresses the very warning that would surface the debt.
- **Suggested Fix**: Repoint callers to `BaseSpectrumAnalyzer`, drop the re-export, delete the wrapper.

#### TD8-10: `auralis/analysis/ml_genre_classifier.py` — deprecated wrapper, 1 caller + stale alias
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `133af798`
- **Location**: `auralis/analysis/ml_genre_classifier.py:1-27`; caller `content_analyzer.py:16`
- **Related**: #2916 (the rename that created the shim).
- **Suggested Fix**: Repoint to `analysis.ml.genre_classifier`, drop the `MLGenreClassifier` alias, delete the wrapper.

#### TD8-11: Commented-out deprecated REST playback endpoints in `player.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `0c2424d4`
- **Location**: `auralis-web/backend/routers/player.py:351-385`
- **Description**: 35 lines of commented-out `/api/player/play|pause|stop` with "Legacy implementation removed" breadcrumbs.
- **Suggested Fix**: Delete the block (CLAUDE.md: no breadcrumbs).

#### TD8-12: Ten `# REMOVED (Phase N)` breadcrumb comments in `chunked_processor.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW · **Age**: `0c2424d4`
- **Location**: `auralis-web/backend/core/chunked_processor.py:216,240,292,408,628,631,634,690,693,768`
- **Siblings**: `realtime_dsp_pipeline.py:92`, `design-system/animations/index.ts:193`.
- **Suggested Fix**: Delete the tombstones.

#### TD8-13: `PlayerBarV2` — "No Variants" violation, implemented but never wired into `Player.tsx`
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `cbc08fa1`
- **Location**: `auralis-web/frontend/src/components/player-bar-v2/PlayerBarV2.tsx:1-149`
- **Description**: Fully implemented (got an image fix this week) but referenced only by two tests that themselves say "not yet implemented". `Player.tsx` doesn't import it. Textbook variant left un-wired.
- **Suggested Fix**: Wire it into `Player.tsx` as the presentational layer, or delete the component + tests. *(Deferred — needs a product decision; see Deferred.)*

#### TD8-14: `usePlayerAPI` — deprecated `play()/pause()` stubs, hook has zero production callers
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `709231ec`
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerAPI.ts:110-134`
- **Description**: `console.warn` deprecated methods inside a hook that no component imports (exported from `hooks/player/index.ts` only).
- **Suggested Fix**: Delete the hook + its export (migrate any `status` polling into `usePlaybackControl`).

#### TD8-15: `useAppKeyboardShortcuts` — `@deprecated` wrapper, zero production callers
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW *(absorbs Dim 2 finding TD2-17)* · **Age**: `09d9b5a3`
- **Location**: `auralis-web/frontend/src/hooks/app/useAppKeyboardShortcuts.ts:1-120` (+ its test)
- **Description**: Delegates to `useKeyboardShortcuts`; `ComfortableApp.tsx` already uses the real hook directly. Test exercises only the indirection.
- **Siblings**: `useAlbumsQueryLegacy` alias in `hooks/library/index.ts:9` (also zero consumers).
- **Suggested Fix**: Delete the hook + test; remove the `useAlbumsQueryLegacy` alias.

---

### Dimension 9 — File / Function / Module Complexity

> Project rule: <300 LOC/module. **Systemic:** 178 files exceed it (107 Python, 71 non-test TS); 62 exceed 600L; 7 exceed 1000L. `#3938`, `#3939`, `#3997` already cover three specific files — skipped here.

**Worst offenders & proposed split axes:**

| Rank | File | LOC | Split axis |
|---|---|---|---|
| 1 | `core/audio_stream_controller.py` | 1962 | `chunk_cache.py` / `stream_handlers.py` / `stream_protocol.py` |
| 2 | `core/simple_mastering.py` | 1551 | `pipeline.py` + `stages/` package (one DSP transform per file) |
| 3 | `analysis/fingerprint/common_metrics.py` | 1178 | **delete — see TD3-04** (re-export of `metrics/`) |
| 4 | `library/repositories/fingerprint_repository.py` | 1016 | `fingerprint_scheduler.py` / `fingerprint_queries.py` |
| 5 | `library/repositories/track_repository.py` | 938 | read vs write repositories |
| 6 | `frontend/.../usePlayEnhanced.ts` | 942 | `useFingerprintStatus` / `useEnhancedStreamSubscriptions` / `usePlaybackTimer` |
| 7 | `frontend/services/AnalysisExportService.ts` | 934 | `exporters/` package + `hooks/useAnalysisExport.ts` |
| 8 | `routers/library.py` | 908 | `routers/tracks.py` / `artists.py` / `albums.py` / `scan.py` |
| 9 | `routers/system.py` | 906 | `ws_handlers/` package + `routers/health.py` |
| 10 | `design-system/tokens.ts` | 914 | `tokens/{colors,spacing,typography,effects}.ts` (barrel re-export) |

#### TD9-01: `audio_stream_controller.py` — 1962-line god controller
- **Severity**: LOW · **Effort**: large · **Status**: NEW · **Age**: `5389ddb7` 2026-05-30 (still growing)
- **Description**: `SimpleChunkCache` + `AudioStreamController` (22 methods) + four streaming coroutines (274/292/263/131L). Every streaming fix navigates ~1700 lines; touched by #3803/#3806/#3828/#3874.
- **Suggested Fix**: Extract cache → `chunk_cache.py`, protocol helpers → `stream_protocol.py`, the three entry points → `stream_handlers.py`.

#### TD9-02: `simple_mastering.py` — 1551-line monolith, 288L god-method
- **Severity**: LOW · **Effort**: large · **Status**: NEW · **Age**: `47ae0db9` 2026-05-27
- **Description**: 25 methods; `_master_file_impl` 288L; each `_apply_*` is a standalone DSP transform. Changes every tuning pass.
- **Suggested Fix**: `core/stages/<stage>.py` each exposing `apply(audio, params)->np.ndarray`; class becomes an orchestrator.

#### TD9-04: `fingerprint_repository.py` — 1016-line mixed-concern repository
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `1f3070ea` 2026-05-27
- **Description**: 22 methods mixing CRUD, 83L pessimistic-lock "claim" scheduling, batch status, stats.
- **Related**: #3762, #3746.
- **Suggested Fix**: Scheduler methods → `fingerprint_scheduler_repository.py`; stats/cleanup → `fingerprint_stats_repository.py`.

#### TD9-05: `routers/system.py` — 906-line WS dispatch router, nesting depth 6+
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `05457127` 2026-05-28
- **Description**: A single `websocket_endpoint` (~785L) with 4 nested coroutines (`stream_audio` 144L, `stream_normal` 214L, `stream_from_position` 95L, `progress_callback`). Health/version unrelated.
- **Related**: #3809/#3813/#3820/#3821.
- **Suggested Fix**: Health/version → `routers/health.py`; inner coroutines → top-level fns in `ws_handlers/stream.py`; endpoint becomes a thin dispatcher.

#### TD9-06: `routers/library.py` — 908-line multi-domain router
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `f7799d7d` 2026-05-28
- **Description**: 14 handlers (tracks/artists/albums/fingerprint/scan/lyrics/favorites) in one closure; `scan_library` 190L with inline callbacks.
- **Related**: #3824, #3914.
- **Suggested Fix**: Split by domain into separate `create_X_router()` modules; scan callbacks → `scan_service.py`.

#### TD9-07: `usePlayEnhanced.ts` — 942-line hook, 13 useState/useEffect
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `a3d065a2` 2026-05-30
- **Description**: One hook doing WS subscriptions + fingerprint state machine + playback timer + PCM buffering.
- **Related**: #2601, #2604.
- **Suggested Fix**: Extract `useFingerprintStatus`, `useEnhancedStreamSubscriptions`, `usePlaybackTimer`; compose.

#### TD9-08: `AnalysisExportService.ts` — 934-line service + embedded hook
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `059ac4ad` 2026-05-27
- **Description**: CSV/JSON/report exporters + chart-image gen in one class; `useAnalysisExport` hook appended at the bottom. (PDF path is the TD5-05 stub.)
- **Suggested Fix**: `services/exporters/` package; move the hook to `hooks/useAnalysisExport.ts`; class becomes a facade.

#### TD9-09: `design-system/tokens.ts` — 914-line single token object
- **Severity**: LOW · **Effort**: small · **Status**: NEW · **Age**: `26d1e278` 2026-05-30
- **Description**: All colors/spacing/typography/shadows/transitions/radii in one object; reliable merge conflicts; no barrier against token duplication.
- **Related**: #3927, #3947, #3948, #3949.
- **Suggested Fix**: Split into `tokens/{colors,spacing,typography,effects}.ts`; re-export merged `tokens` via spread (zero call-site changes).

#### TD9-10: `performanceOptimizer.ts` + `VisualizationOptimizer.ts` + `AdvancedPerformanceOptimizer.ts` — near-duplicate util trio
- **Severity**: LOW · **Effort**: medium · **Status**: NEW · **Age**: `ef46d855` 2026-05-26
- **Description**: ~1877L across three files redefining `FrameRateController`, `DataDecimator`, `CanvasPool`, `PerformanceMonitor` with divergent implementations — highest silent-drift risk; consumers pick imports arbitrarily.
- **Suggested Fix**: Consolidate into `utils/rendering/{frame-rate,data-decimator,canvas-pool,performance-monitor}.ts`; delete the three originals after migration.

#### TD9-11: `types/websocket.ts` — 815-line type monolith
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Description**: 30+ interfaces + a 40-literal union; every WS feature appends here.
- **Related**: #3809, #3873, #3780.
- **Suggested Fix**: `types/ws/{player,library,streaming,fingerprint}.ts`; barrel re-export (zero consumer changes).

#### TD9-12: `ContinuousMode.process` — 214-line god method
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `auralis/core/processing/continuous_mode.py:253-467`
- **Description**: Two execution paths (fast / fingerprint) + 7 DSP sub-ops + inline recording-type/confidence branching, single entry point.
- **Suggested Fix**: Extract `_process_fast_path()` / `_process_fingerprint_path()`; `process()` becomes a ~20-line dispatcher.

#### TD9-13: `useLibraryWithStats.ts` — 476-line hook, 17 combined React hooks
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Description**: 11 useState + 4 useRef + 2 useEffect covering pagination, scan progress, stats, abort lifecycle, Electron path detection, and an `offsetRef` stale-closure workaround.
- **Related**: #3943.
- **Suggested Fix**: Extract `useLibraryPagination`, `useLibraryStats`, `useLibraryScan`; compose.

---

### Dimension 10 — Audit-Finding Rot

> All three stem from one shared file (`_audit-common.md`, `9234b345` 2026-05-20) whose hardcoded counts propagate into `audit-backend.md`, `audit-security.md`, `audit-tech-debt.md`, and CLAUDE.md.

#### TD10-01: `_audit-common.md` claims "18 route handlers" — actual 15
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `.claude/commands/_audit-common.md:28,123`
- **Description**: 4 files in `routers/` (`dependencies`, `errors`, `pagination`, `serializers`) are utilities, not handlers → 15. Propagates to `audit-backend.md:107,139,196`, `audit-security.md:35,104`, `audit-tech-debt.md:139`, `CLAUDE.md:80`. Auditors hunt for 3 non-existent routers.
- **Suggested Fix**: `18`→`15` in all listed locations; add a "re-verify on router add/remove" note.

#### TD10-02: `_audit-common.md` claims "92 files" in `auralis/analysis/` — actual 83
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `.claude/commands/_audit-common.md:20` (+ MEMORY.md note)
- **Description**: False size baseline hides real drift. (25D fingerprint claim is still correct.)
- **Suggested Fix**: `92`→`83`, or replace with a "re-run `find … | wc -l`" note.

#### TD10-03: `_audit-common.md` claims "850+ tests across 21 dirs" — actual 18 named subdirs
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `.claude/commands/_audit-common.md:45`
- **Description**: Dir count off by 3; "850+" now understates the ~1,195 top-level / ~4,635 total test functions.
- **Suggested Fix**: "1000+ test functions across 18 subdirs", or drop the literal counts.

---

## Deferred (gated on in-progress work or a product decision)

- **TD6-04** (chunk-boundary tests skipped) — the underlying bug is **CRITICAL open #3803**; re-enable the tests as part of that fix, not standalone.
- **TD6-05** (player test classes skipped) — gated on the player-fixture refactor tracked by **#2601 / #3997**.
- **TD8-13** (`PlayerBarV2`) — wire-in vs delete is a **product/design decision** about the player layout; not a mechanical cleanup.
- **TD3-03 / TD9-01 / TD9-02** (large splits) — high-value but `large` effort; schedule deliberately, not as drive-by edits, since `audio_stream_controller.py` and `simple_mastering.py` are in active hot-fix territory.

---

## Cross-Dedup Notes (folded findings)

- Dim 1's three stale markers (median_filter stub, HybridProcessor str-path, playlist onPlay TODO) were reclassified into **TD5-02 / TD5-01 / TD5-06** respectively — reachability is the deciding axis, so they live under Stub Implementations.
- **TD2-17** (`useAppKeyboardShortcuts` dead code) folded into **TD8-15** (deprecation cruft).
- **TD9-03** (`common_metrics.py` 1178-line complexity) folded into **TD3-04** (duplication) — deleting the re-implementation resolves both.
- `SmoothAnimationEngine.ts` appears in the Dim 9 offender table but is dead code (**TD2-14**) → delete, not split.

## Severity & Promotion Audit Trail

- 0 HIGH: no duplicated DSP scaffolding dropped a guard a sibling had; no magic constant *silently* truncates/overflows audio under documented use (TD4-05's window bug is biased, not truncating → routed to /audit-engine, kept LOW here).
- 3 MEDIUM via the documented triggers: TD3-02 (divergent bug-fix history), TD5-04 & TD5-06 (stubs reachable from a shipped UI).
- All other 93 findings default to LOW per `_audit-severity.md`.
