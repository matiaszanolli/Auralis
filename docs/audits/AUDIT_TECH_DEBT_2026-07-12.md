# Tech-Debt Audit — Auralis — 2026-07-12

**Scope**: whole repo (`auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/`, `tests/`, `docs/`, skills).
**Depth**: deep. **Method**: 10 debt dimensions, grep-driven evidence, dedup against 142 open + 172 tech-debt-labeled GitHub issues.
**Dedup outcome**: A comprehensive tech-debt sweep on **2026-07-06** (issues #4245–#4314) already tracks the large majority of structural debt. This report confirms those remain valid (no regressions) and adds the **newly-surfaced** findings below.

---

## Executive Summary

| Severity | NEW findings | Already tracked (confirmed) |
|----------|-------------|------------------------------|
| HIGH     | 0           | 0 |
| MEDIUM   | 2           | — |
| LOW      | 23          | ~30 (see "Confirmed Existing") |
| **Total NEW** | **25** | |

- **No HIGH/CRITICAL debt.** No audio-integrity amplification triggered (no duplicated DSP scaffold dropping `audio.copy()`/sample-count guards; no magic constant that truncates audio). The `_audit-severity.md` promotion table did not fire above MEDIUM.
- **Two MEDIUM findings**, both frontend architectural: a dead/duplicated WebSocket subscription system (TD3-01) and a "placeholder → trained model" ML promise unfulfilled for 9+ months in the shipped EQ path (TD1-04). Both carry a *correctness* question routed to `/audit-frontend` / `/audit-engine` as `Related` — not asserted here.
- The codebase is **essentially clean of canonical `TODO/FIXME/HACK/XXX` markers** (0 in Python, 1 in TS — already tracked #4290) and of Rust `#[allow(dead_code)]` / `todo!()` macros (0). The remaining stale-marker debt is soft-language ("for now", "placeholder", "would be replaced") on deferred features.
- Systemic modularity debt persists: **101 Python + 155 TS/TSX files exceed the 300-LOC rule**; most are tracked by the #42xx god-file-split series, but 8 production files (largest: `track_repository.py` at 928L) are **untracked** (TD9-01).

**Baseline direction**: No prior `AUDIT_TECH_DEBT_*.md` report exists — this is the first tech-debt baseline. Future runs can diff `Baseline Snapshot` below.

---

## Baseline Snapshot (2026-07-12)

```
TODO/FIXME/HACK/XXX (py):    0
TODO/FIXME/HACK/XXX (ts):    1     (AlbumCard.tsx — #4290)
NotImplementedError:         3     (all in duplicate_detector.py — a proper guard, not a stub)
type: ignore (py):           96    (1 stale per mypy --warn-unused-ignores → TD2-10; rest needed)
@ts-ignore/@ts-expect-error: 2
': any' / 'as any' (ts):     555
skipped tests (py):          58
skipped tests (ts):          5
py files >300 LOC:           101
ts/tsx files >300 LOC:       155
allow(dead_code) (rust):     0
```

---

## Top 10 Quick Wins (trivial/small, immediate payoff)

1. **TD2-01** — `ruff check --fix` removes 11 unused `except Exception as e:` bindings in `routers/player.py` (auto, zero behavior change).
2. **TD2-02** — delete `remaining_chunks` + its stale `#3768` comment in `stream_normal.py:156`.
3. **TD2-10** — remove the one stale `# type: ignore[import-untyped]` on `mastering_profile.py:26` (only unused-ignore in the whole tree).
4. **TD7-01 / TD7-02** — fix two stale counts in CLAUDE.md ("81 files"→56 analysis; "369 files / 18 subdirs"→410 / 19 tests).
5. **TD2-03** — delete two `ruff F841` unused locals (`fingerprint_storage.py:181`, `normalization_step.py:152`).
6. **TD2-11** — delete 33 unused REST-contract interfaces + `buildQueryParams` in `types/api.ts` (all grep-count 1; mechanical).
7. **TD2-05 / TD2-06** — delete 9 dead a11y + error-handling exports (`a11y/focusManagement.ts`, `utils/errorHandling.ts`, `utils/apiRequest.ts`).
8. **TD2-07 / TD2-08 / TD2-09** — delete 14 dead frontend hooks/selectors/exports (zero consumers).
9. **TD6-01** — delete (not skip) the 879-line `streaming-mse.test.tsx` (20 tests exercise only their own mock fixtures; MSE was never adopted).
10. **TD1-08** — delete the "optionally verify checksum" comment in `sidecar_manager.py:131` (size+mtime is the intended permanent design).

---

## Top 5 Medium Investments (splits / consolidations)

1. **TD3-01** — Collapse the two parallel WebSocket subscription systems onto `WebSocketContext.tsx`; migrate 7 consumers off the never-armed `useWebSocketSubscription.ts` singleton, then delete it. (Also resolves TD1-03, TD1-09's WS pieces.)
2. **TD9-01** — Split the 8 untracked oversized production files, starting with `track_repository.py` (928L → per-entity query modules).
3. **#4294** (existing) — Migrate 111 hand-rolled `get_session()/finally: close()` call sites onto `BaseRepository._session_scope()`.
4. **TD2-11** — Decide whether `types/api.ts` should become the *adopted* canonical REST contract (wire `services/*.ts` to it) or be deleted; today it is 33 dead types drifting from the real shapes (compounds #3892).
5. **TD1-04** — Resolve the genre-classifier "placeholder for trained model" language: either open a real tracking issue or rewrite the docstrings to document the rule-based model as the permanent design (it feeds the shipped EQ pipeline).

---

# Findings

## MEDIUM

### TD3-01: Two parallel WebSocket subscription systems; the "legacy" one is never armed in production
- **Severity**: MEDIUM (duplication + divergent evolution; correctness angle routed out)
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts` vs. `auralis-web/frontend/src/contexts/WebSocketContext.tsx`
- **Status**: NEW
- **Age**: coexisting since commit `1c0e82b7` (Dec 2025, "Silence legacy WebSocket subscription warnings"); the "legacy" file kept receiving fixes for 7+ months after being declared legacy.
- **Effort**: medium
- **Description**: Two independent pub/sub implementations. `WebSocketContext.subscribe/subscribeAll` is backed by the real `WebSocketManager` and used by 7 hooks. `useWebSocketSubscription.ts` is a module-singleton armed only by `setWebSocketManager()` — which is **never called in production** (`grep -rn "setWebSocketManager(" src` → only its own file + test files). So `globalWebSocketManager` stays `null` and its 7 consumers (`useWebSocketErrors`, `useEnhancementControl`, `useArtworkUpdates`, `usePlaybackQueue`, `useLibraryWithStats`, `useScanProgress`, barrel) sit permanently in the "manager not available" branch.
- **Evidence**: `useEnhancementControl.ts` imports **both** systems in one file (uses `wsContext` for `reissueActiveStreamAs` at line 164, but subscribes to `enhancement_settings_changed` via the dead singleton at line 176).
- **Impact**: Duplicated subscribe/unsubscribe/cleanup scaffolding (violates CLAUDE.md DRY); plus a *possible* live functional gap (security-error toasts / scan-progress / artwork / enhancement-sync may never fire) — flagged for verification, not asserted.
- **Siblings**: same subscribe-in-`useEffect`+ref+cleanup shape re-invented a 3rd time in `useAudioStreamingCore.ts:316` and `usePlayEnhanced.ts:543`.
- **Related**: TD1-03, TD1-09 (same root); route correctness to `/audit-frontend` or `/audit-integration` (candidate HIGH functional bug); adjacent to open #3654.
- **Suggested Fix**: Consolidation site `WebSocketContext.tsx`. Migrate the 7 consumers to `useWebSocketContext().subscribe(...)`, then delete `useWebSocketSubscription.ts`, `setWebSocketManager`, `globalWebSocketManager`. Port the "subscribe to many message types by key" convenience on top of `WebSocketContext.subscribe` if any consumer needs it.

### TD1-04: Genre classifier documented as a "placeholder" for a trained model since 2025-10, live in the EQ pipeline
- **Severity**: MEDIUM
- **Dimension**: Stub Implementations (surfaced via stale marker)
- **Location**: `auralis/analysis/ml/genre_weights.py:14-24`; `auralis/analysis/ml/genre_classifier.py` (`RuleBasedGenreClassifier`, `initialize_genre_weights()`)
- **Status**: NEW
- **Age**: commit `e116da5e` 2025-10-02; module copyright 2024 — 9+ months.
- **Effort**: large (a real trained model) — or trivial to re-document as permanent.
- **Description**: `initialize_genre_weights()` docstring promises *"In production, this would be replaced with actual trained model weights."* The #3741 fix (deterministic seed) explicitly calls it "the placeholder weight initialiser." `RuleBasedGenreClassifier` is wired through `content_analyzer.py` into `EQProcessor._apply_content_adjustments` (bass/mid/treble scaling) — i.e. this "placeholder" is **live in the shipped mastering/EQ path**, not a side stub.
- **Evidence**: `genre_classifier.py`: *"This is a simplified linear model representation. In production, this would be replaced with actual trained model weights."*
- **Impact**: Not a correctness bug (#3741's seed guard works). The debt is a misleading unfulfilled-promise comment with no tracking issue for the follow-up; per project memory "ML is rule-based" is the accepted architecture, so the comment actively misdescribes reality.
- **Related**: `/audit-engine` if genre-classification quality is ever scoped.
- **Suggested Fix**: Either open a "replace with trained model" tracking issue, or rewrite the docstrings/comments to document the rule-based model as the permanent design and delete the "would be replaced" language.

---

## LOW

### Stale Markers (Dimension 1)

### TD1-02: Queue `redo()` is a permanent no-op stub, full-stack, since Phase 7A
- **Severity**: LOW (guarded: `canRedo` hardwired `false`, so not reachable as a live action)
- **Dimension**: Stub Implementations
- **Location**: `auralis/library/repositories/queue_history_repository.py:163-174`; `auralis-web/frontend/src/hooks/player/useQueueHistory.ts:308-310,349`
- **Status**: NEW
- **Age**: commit `ed709420` 2025-12-01 (Phase 7A) — 7+ months.
- **Effort**: small
- **Description**: Backend `redo()` unconditionally `return None`; frontend `redo()` `throw new Error('Redo not yet implemented')` and `canRedo: false // Not yet implemented`. No `/redo` route exists. Dead public API on both sides with no tracking issue for the deferred feature.
- **Impact**: No user-visible bug (`canRedo` never flips true); dead surface for 7+ months.
- **Suggested Fix**: Delete `redo()`/`canRedo`/the frontend `redo` callback until a driving feature exists, or implement the redo stack mirroring `undo()`.

### TD1-05: `SelfTuner._enforce_cache_size_limits` is a partial no-op — and `SelfTuner` has zero production callers
- **Severity**: LOW
- **Dimension**: Dead Code / Stub
- **Location**: `auralis-web/backend/services/self_tuner.py:264-271`
- **Status**: NEW
- **Age**: commit `586d4e74` 2025-10-25 — 8+ months.
- **Effort**: trivial (delete) / small (implement)
- **Description**: Method only clears a tier when `max_size_mb == 0.0`, not for nonzero shrink, despite its docstring ("Evict excess cache entries if caches shrunk"). Separately, `SelfTuner`/`self_tuner` is never imported/instantiated outside its own file — fully unreachable from any route/`main.py`/`startup.py`.
- **Suggested Fix**: Delete `self_tuner.py` (8 months unreferenced), or implement proportional eviction and wire it up if intended to ship.

### TD1-06: `Scanner._update_library_stats` promises to update stats but only logs
- **Severity**: LOW
- **Dimension**: Stub
- **Location**: `auralis/library/scanner/scanner.py:302-308` (called at `scanner.py:217`)
- **Status**: NEW
- **Age**: commit `ab8fce28` 2025-10-31 — 8+ months.
- **Effort**: small
- **Description**: Body is `# This would update the LibraryStats table / # For now, just log the results` + an `info()` call; never touches `stats_repository`. Reachable from the shipped folder-scan flow.
- **Related**: `/audit-engine` / library-specialist (does the stats repo get written via a different path, making this vestigial?).
- **Suggested Fix**: Wire to `stats_repository.py`, or rename to `_log_scan_result` and drop the "would update" comment.

### TD1-07: Adaptive semaphore resize recommendation is logged but never applied
- **Severity**: LOW
- **Dimension**: Stub
- **Location**: `auralis/services/fingerprint_queue.py:216-230`
- **Status**: NEW
- **Age**: commit `102b0f92` 2025-12-10 — 7+ months.
- **Effort**: medium
- **Description**: `_on_semaphore_change()` only logs the recommended size ("Python's Semaphore doesn't provide a safe way to dynamically resize … For now, we just log"). The fingerprint pipeline is shipped, so the "adaptive" semaphore signal is a production no-op.
- **Related**: `/audit-concurrency`.
- **Suggested Fix**: Implement a counter+lock resizable semaphore, or drop the callback registration + the recommendation entirely.

### TD1-08: Sidecar checksum validation permanently deferred by comment
- **Severity**: LOW
- **Dimension**: Stale Marker
- **Location**: `auralis/library/sidecar_manager.py:130-131`
- **Status**: NEW
- **Age**: commit `6a38afa6` 2025-10-29 — 8+ months.
- **Effort**: trivial
- **Description**: Comment describes an optional checksum path that was never built ("For now, size + mtime is sufficient"). Reads as a still-valid design decision, not a broken stub.
- **Suggested Fix**: Delete the "optionally verify checksum" comment (size+mtime is the working, intended strategy).

### TD1-09: Three orphaned player/fingerprint hooks carry unresolved "for now" stubs, zero consumers
- **Severity**: LOW
- **Dimension**: Dead Code / Stale Marker
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useFingerprintCache.ts:99-104`; `hooks/fingerprint/useTrackFingerprint.ts:110-115`; `hooks/player/usePlayerControls.ts:205-212`
- **Status**: NEW
- **Age**: 6-8 months (commits `166f8fba`, `8c9e420f`, `ac6cc536`).
- **Effort**: trivial (delete) / small (wire up)
- **Description**: `useFingerprintCache` simulates a Web Worker in the main thread; `usePlayingTrackFingerprint` is permanently `enabled:false`; `usePlayerControls.togglePlayPause` always returns `{success:false}`. None imported by any component outside their barrel `index.ts`.
- **Suggested Fix**: Delete all three hooks + barrel exports absent a near-term plan.

### TD1-10: `useQueueSearch` `currentTrackOnly` filter is a known-incomplete no-op, live in the shipped Queue Search panel
- **Severity**: LOW
- **Dimension**: Stub
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueSearch.ts:240-245`
- **Status**: NEW
- **Age**: commit `04e2cf15` 2025-12-01 — 7+ months.
- **Effort**: small
- **Description**: The `currentTrackOnly` branch `continue`s unconditionally ("For now, we'll skip this check"), so the filter always returns zero results; the comparison logic (`queue.indexOf(queue[0])`, always index 0) is also wrong. Unlike TD1-09 this hook **is** shipped (`QueueSearchPanel.tsx`).
- **Impact**: If a "current track only" UI toggle is wired, checking it silently returns empty — a user-facing correctness angle.
- **Related**: `/audit-frontend` (is the toggle reachable?).
- **Suggested Fix**: Thread the current-track index in from `usePlaybackQueue`, or remove the toggle + dead branch.

### Dead Code (Dimension 2)

### TD2-01: `except Exception as e` binds unused exception 11× in `routers/player.py`
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis-web/backend/routers/player.py:325,399,437,465,481,493,613,625,637,650,662,677,718,730`
- **Description**: 11 handlers bind `e` but log a fixed string + raise a fixed detail. `ruff --select F841` confirms. Fix: `ruff check --fix` → `except Exception:`.

### TD2-02: `remaining_chunks` computed but unused; comment falsely claims it's load-bearing
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis-web/backend/core/stream_normal.py:156`
- **Description**: `#3768: kept only for the logging line below` — but the log block references only `total_chunks`/`start_chunk`. Delete assignment + stale comment.

### TD2-03: Two more `ruff F841` unused locals
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:181` (`except … as e` unused), `auralis/core/processing/base/normalization_step.py:152` (`crest_delta` computed, never printed while `rms_delta` is).
- **Description**: Delete the bindings. Note `crest_delta` may have been *meant* to be printed alongside `peak_delta`/`rms_delta` — worth a glance (correctness → `/audit-engine`).

### TD2-05: `a11y/focusManagement.ts` — 5 exports with zero call sites
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `auralis-web/frontend/src/a11y/focusManagement.ts:208,296,371,380,400`
- **Description**: `injectFocusStyles`, `focusModeDetector`, `focusVisibilityMonitor`, `announceFocus`, `getAccessibleName` — grep count 1 each. Dead a11y tooling that looks like it should be wired into bootstrap. Delete or wire up.

### TD2-06: Dead error-handling utility exports
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `auralis-web/frontend/src/utils/errorHandling.ts:373,469,486`; `utils/apiRequest.ts:13`
- **Description**: `ErrorRecoveryChain`, `withErrorLogging`, `resilientFetch`, `APIError` — grep count 1 each. Abandoned resiliency infra. Delete, or adopt `resilientFetch` in the real fetch path.

### TD2-07: Unused sub-hooks in `usePlaybackControl.ts`
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:348,368,387,406`
- **Description**: `usePlayPauseControl`, `useSeekControl`, `useVolumeControl`, `useSkipControl` — referenced only in their own JSDoc `@example`. Delete the 4 wrappers; keep `usePlaybackControl`.

### TD2-08: Dead Redux selectors in `cacheSlice.ts` / `connectionSlice.ts`
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `store/slices/cacheSlice.ts:176-177`; `store/slices/connectionSlice.ts:204-211`
- **Description**: `selectLastUpdated`, `selectCacheState`, `selectMaxReconnectAttempts`, `selectLastError`, `selectLastReconnectTime`, `selectConnectionState` — zero `useSelector`/imports. (Distinct from closed #4016's `selectLastUpdate`.) Delete, or wire the connection selectors into `ConnectionStatusIndicator.tsx`.

### TD2-09: Unused convenience exports across service/middleware files
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `services/AnalysisExportService.ts:845` (`useAnalysisExport`); `services/RealTimeAnalysisStream.ts:580` (`useRealTimeAnalysisStream`); `services/fingerprint/FingerprintCache.ts:383` (`resetFingerprintCache`); `store/middleware/errorTrackingMiddleware.ts:395` (`createRecoveryDispatcher`)
- **Description**: grep count 1 each. Delete after confirming no string-based lookup. `useAnalysisExport` should be delete-candidate, not move-candidate, in #4078's split.

### TD2-10: One stale `# type: ignore[import-untyped]` (only unused-ignore in the tree)
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `auralis/analysis/mastering_profile.py:26` (`import yaml`)
- **Description**: `mypy --warn-unused-ignores` flags exactly one unused ignore across all 96. Distinct from closed #4256's 58 sites. Remove the comment.

### TD2-11: `types/api.ts` — 33 unused REST-contract types + `buildQueryParams`, no runtime consumer
- **Severity**: LOW · **Effort**: medium · **Status**: NEW
- **Location**: `auralis-web/frontend/src/types/api.ts:54-464`
- **Description**: 33 request/response interfaces (player/library/metadata/enhancement/playlist/artwork/search/fingerprint/similarity/health/cache/streaming) + `buildQueryParams` are grep-count 1; actual `services/*.ts` use ad-hoc inline shapes instead (compounds #3892). Delete the dead block, or make it the adopted canonical contract (separate, larger effort).
- **Related**: #3892 (ad-hoc pagination shapes bypass dead `schemas.PaginatedResponse`).

### Test Hygiene (Dimension 6)

### TD6-01: 879-line `streaming-mse.test.tsx` is skipped fixture-only test code — delete, don't skip
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `auralis-web/frontend/src/tests/integration/streaming-audio/streaming-mse.test.tsx:439`
- **Description**: `describe.skip` guards 20 tests that exercise only `TestMSEPlayer`/`MockMediaSource`/`MockSourceBuffer` defined in-file. Auralis never adopted MediaSource Extensions (streaming is WebSocket PCM). The #3935 fix correctly stopped the false-green by adding `.skip`, but the right end-state is deletion — the file can never regress against production code. Real coverage lives in `services/audio/__tests__/AudioPlaybackEngine.test.ts`.
- **Related**: #3935 (added the skip; this proposes the follow-up deletion).
- **Suggested Fix**: Delete the file.

### TD6-02: Skipped tests for removed REST endpoints should be deleted
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `tests/backend/test_main_api.py:525,530,535,608,1559`; `tests/backend/test_api_endpoint_integration.py:81,175`
- **Description**: Multiple `@pytest.mark.skip(reason="… deprecated — now WebSocket-only" / "… REST stream endpoint removed" / "… not implemented")` guard tests for endpoints that no longer exist. Skips referencing *removed* features are dead weight, not regression guards — delete the tests (the WebSocket path has its own coverage).
- **Suggested Fix**: Delete the skipped functions; if a WS-equivalent assertion is missing, file it separately.

### Stale Documentation (Dimension 7)

### TD7-01: CLAUDE.md Codebase Map says `analysis/` is "81 files" — actual 56
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `CLAUDE.md:50`
- **Description**: `find auralis/analysis -name '*.py' | wc -l` → 56. `_audit-common.md:20` already says 56; CLAUDE.md (and project memory) still say 81. Update to 56.

### TD7-02: CLAUDE.md test counts stale ("369 files / 18 subdirs")
- **Severity**: LOW · **Effort**: trivial · **Status**: NEW
- **Location**: `CLAUDE.md:103`
- **Description**: Live: 410 `*.py` under `tests/`, ~5,001 test functions, 19 subdirs. CLAUDE.md says "~5,100 test functions (369 files) across 18 subdirs"; `_audit-common.md:45` says "410 files … 17 dirs" (dir count also off by 2). Reconcile both to 410 files / 19 dirs.
- **Note**: Version strings are consistent everywhere (`1.2.1-beta.2` in version.py, pyproject `1.2.1b2`, package.json, README, CLAUDE.md) — **no version drift** (project memory's "pyproject stale" note is now outdated).

### Backwards-Compat Cruft (Dimension 8)

### TD8-01: Design-system "Legacy aliases" blocks kept for backwards compatibility (no external consumers)
- **Severity**: LOW · **Effort**: small · **Status**: NEW
- **Location**: `auralis-web/frontend/src/design-system/tokens/colors.ts:112`; `design-system/tokens/effects.ts:98,113`
- **Description**: Explicit `// Legacy aliases (for backwards compatibility)` blocks. Auralis is desktop-only with no external token consumers (CLAUDE.md / memory), so "backwards compatibility" has no audience — either delete the aliases (after repointing any internal users) or drop the "legacy/compat" framing.
- **Suggested Fix**: grep each alias; migrate internal references to the canonical token and delete the alias block.

### File / Function Complexity (Dimension 9)

### TD9-01: 8 oversized production files exceed the 300-LOC rule and are untracked by the god-file-split series
- **Severity**: LOW · **Effort**: medium (per file) · **Status**: NEW
- **Location** (LOC): `auralis/library/repositories/track_repository.py` (928), `auralis/library/repositories/fingerprint_repository.py` (693), `auralis/library/repositories/playlist_repository.py` (607), `auralis/core/mastering_config.py` (583), `auralis/core/processing/parameter_generator.py` (577), `auralis/library/migration_manager.py` (562), `auralis/library/models/core.py` (548), `auralis-web/frontend/src/services/RealTimeAnalysisStream.ts` (628)
- **Status**: NEW (the other ~40 oversized files ARE tracked — see Confirmed Existing)
- **Description**: 101 py + 155 ts/tsx files exceed 300 LOC. Issues #4245/#4250/#4252/#4254/#4260/#4266/#4270/#4276/#4288/#4292/#4297/#4077/#4078/#4273/#4301/#4305 cover the worst offenders, but these 8 have no tracking issue. `track_repository.py` (928L) is the single largest module in the repo.
- **Suggested split axes**: `track_repository.py` → per-concern query modules (CRUD / search / stats / fingerprint-join); `models/core.py` → one ORM model per file; `mastering_config.py` → config dataclasses vs. defaults/presets; `RealTimeAnalysisStream.ts` → stream transport vs. analysis-frame decoding.
- **Suggested Fix**: File one split issue per module (or a #42xx-series batch), split by responsibility not line count.

---

## Confirmed Existing (re-verified present, NOT re-filed)

Re-verified against HEAD `7ecd34c9`; no regressions found.

**Duplication / structure**
- **#4294** — `BaseRepository._session_scope()` unused; exactly **111** hand-rolled `get_session()` sites across 13 repos (count matches filing).
- **#4298** — 12 DSP stage `apply()` guards duplicated; `core/stages/safety_limiter.py` still returns a bare ndarray, breaking the sibling `(audio, metadata)` tuple contract.
- **#4304** — raw `HTTPException(status_code=404)` bypasses `NotFoundError`; now **36** sites (was 35; +1 in `fingerprint_status.py:82` from recent Rust-glue work).
- **#4309** — `AdaptiveCompressor`/`AdaptiveLimiter` duplicate a lookahead ring buffer.
- **#4033** — `_MAX_UPLOAD_BYTES = 500*1024*1024` redeclared in `files.py:138` and `processing_api.py:30`.
- **#4289** — `ChunkOperations` redeclares chunk-geometry constants instead of importing `chunk_boundaries`.
- **#4284** — `MAX_LEVEL_CHANGE_DB` duplicated in `chunked_processor.py`.

**Dead code / unused imports**
- **#4012** (`startup.py` asyncio + LibraryScanner), **#4008** (`chunked_processor.py` ProcessorFactory), **#4011** (`library_auto_scanner.py` FileSystemEvent), **#4286** (`fingerprint_service.py` os), **#4275** (scipy in simple_mastering), **#4268** (Rust unused imports), **#4306** (`serialize_playlist` dead), **#3879** (dead module-level prefetch/crossfade fns), **#4273** (`useVisualizationOptimization` + `performanceOptimizer`, 1,280L zero-consumer).

**Deprecation cruft**
- **#4314** (LibraryManager deprecation timeline unfulfilled), **#4313** (`require_library_manager` shim, zero production callers), **#4307** (`feature_extractors.py` deprecated wrapper), **#3770** (cache invalidation on deprecated facade), **#4015** (MSE feature-flags never imported).

**Test hygiene**
- **#4042** (CLOSED) — `test_thread_safety.py` 13 xfail markers: **fix verified in place** (`strict=True` present on all 13). Not regressed.
- **#4269** (`test_parallel_processing.py` xfails lack strict/issue refs), **#4274** (HPSS short-audio xfail untracked), **#4264** (3 frontend `it.skip` untracked), **#4244** (artwork "would verify" test stubs).

**God-file splits (oversized, tracked)**
- **#4245** chunked_processor.py, **#4250** processing_engine.py, **#4252** mastering_branches.py, **#4254** continuous_mode.py, **#4260** queue_service.py, **#4266** hybrid_processor.py, **#4270** wav_streaming.py + similarity.py, **#4276** parallel_processor.py, **#4288** helpers.py, **#4292** usePlaybackQueue.ts, **#4297** WebSocketContext.tsx, **#4077** usePlayEnhanced.ts, **#4078** AnalysisExportService.ts, **#4301** AudioPlaybackEngine.ts, **#4305** useStandardizedAPI.ts (since resolved by `7ecd34c9`), **#4028**/**#3838** router splits.

---

## Dimensions with no NEW findings

- **Dim 4 (Magic Numbers)**: All real occurrences are tracked (#4289 chunk geometry, #4033/#4284 duplicated constants, #3901/#3902 middleware TTLs). Inline `44100` occurrences found were docstring/log-label text (`interpolation_helpers.py` examples, an f-string "at 44.1kHz" label), not arbitrary tunables — not reported. Chunk boundaries retain their single source of truth (`chunk_boundaries.py`).
- **Dim 10 (Audit-Finding Rot)**: `.claude/commands/_audit-validate.sh` passes clean (161 path refs across 25 skill files, all resolve). No `#NNN` "Existing:" callouts in audit skills point at closed issues. `docs/audits/` had no prior report. The only doc-count drift is CLAUDE.md (TD7-01/02) and the minor `_audit-common.md` test-dir count. No rot beyond that.

---

## Deferred / Watch-Items

- **`type: ignore` (py) count 58 → 96**: closed #4256 removed 58 stale ignores; the tree now has 96, of which `mypy --warn-unused-ignores` flags exactly **one** as stale (TD2-10). The other 95 appear needed (untyped third-party/PyO3 boundaries). Not a regression of #4256, but re-run `mypy --warn-unused-ignores` at the next audit to confirm the delta stays clean.
- **`as any`/`: any` (ts) count 555**: large but out of tech-debt scope for individual reporting; a typed-boundary hardening pass would be a separate `/audit-frontend` initiative.
- **Correctness angles routed out** (do NOT fix here): TD3-01 / TD1-03 (dead WS manager may silence real-time features) → `/audit-frontend` / `/audit-integration`; TD1-10 (`currentTrackOnly` empty results) → `/audit-frontend`; TD1-06 (scanner stats gap), TD2-03 (`crest_delta`) → `/audit-engine`; TD1-07 (semaphore non-responsiveness) → `/audit-concurrency`.

---

*Report generated 2026-07-12. Publish with: `/audit-publish docs/audits/AUDIT_TECH_DEBT_2026-07-12.md` (labels: `tech-debt` + severity + domain + `maintenance`).*
