# Regression Verification Audit — 2026-03-02

**Auditor**: Claude Opus 4.6
**Methodology**: Per `.claude/commands/audit-regression.md` and `_audit-common.md`

---

## Sources

| Source | Count |
|--------|-------|
| Seed registry (critical invariants) | 12 |
| Git fix commits (`git log --grep=fix -30`) | 8 verified |
| Closed GitHub issues (HIGH/MEDIUM) | 17 verified |
| **Total fixes checked** | **37** |

---

## Seed Registry Verification

### 1. Equal-power crossfade between mastering chunks
- **Status**: PASS
- **Source**: Seed registry, commit `0a5df7a3`
- **Files checked**: `auralis-web/backend/core/chunked_processor.py:911-914`, `core/chunk_operations.py:290-292`, `auralis/core/simple_mastering.py:220-222`
- **Fix present**: Yes — all three locations use `sin²/cos²` equal-power curves
- **Tests exist**: Yes
- **Test files**: `tests/backend/test_chunked_processor.py` (TestCrossfade), `tests/backend/test_chunked_processor_invariants.py` (4 tests)
- **Notes**: Overlap is 5s in streaming, 3s in mastering — both correct for their contexts

### 2. Parallel processing for sub-bass control
- **Status**: PASS
- **Source**: Seed registry, commit `8bc5b217`
- **Files checked**: `auralis/core/simple_mastering.py:659-713`, `auralis/core/dsp/parallel_eq.py:96-112`
- **Fix present**: Yes — parallel path via `ParallelEQUtilities.apply_low_shelf_boost()`, difference-based gain application
- **Tests exist**: Yes
- **Test files**: `tests/regression/test_parallel_eq_dtype.py`, `tests/regression/test_mastering_regression.py`, `tests/auralis/dsp/test_parallel_eq_gain_accumulation.py`

### 3. Double-windowing removal in EQ
- **Status**: PASS
- **Source**: Seed registry, commit `cca59d9c`
- **Files checked**: `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:93-119`, `auralis/dsp/eq/filters.py:63-103`
- **Fix present**: Yes — no windowing applied in FFT EQ processing, explicit comments documenting rationale
- **Tests exist**: Yes
- **Test files**: `tests/auralis/dsp/test_eq_double_window_artifact.py` (4 tests), `tests/test_fix_2166_double_windowing.py` (4 tests)

### 4. Audio loading thread safety
- **Status**: PARTIAL
- **Source**: Seed registry, commit `53cef6b4`
- **File checked**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:171-211`
- **Fix present**: Yes — ThreadPoolExecutor created without `with`, explicit `KeyboardInterrupt` handler with `cancel_futures=True`
- **Tests exist**: No — no test exercises the `KeyboardInterrupt` path specifically
- **Test files**: `tests/test_phase_7_3_fingerprint_optimization.py` (thread safety tested, but not interrupt handling)
- **Notes**: Testing `KeyboardInterrupt` in `ThreadPoolExecutor` is difficult but a structural test verifying the `cancel_futures=True` parameter would be valuable

### 5. Cursor-based pagination in cleanup
- **Status**: PASS
- **Source**: Seed registry, commit `bd94fd59`
- **File checked**: `auralis/library/repositories/track_repository.py:759-821`
- **Fix present**: Yes — ID-cursor pagination with `Track.id > last_id`, cursor advance at line 812
- **Tests exist**: Yes
- **Test files**: `tests/regression/test_cleanup_missing_files_pagination.py` (2 tests, 100-track multi-batch scenario)

### 6. SQLAlchemy engine disposal
- **Status**: PASS
- **Source**: Seed registry, commit `8adb8d0a`
- **File checked**: `auralis/library/migration_manager.py:322-325`
- **Fix present**: Yes — `self.engine.dispose()` called in `close()`, called from `finally` block in `check_and_migrate_database()`
- **Tests exist**: Yes
- **Test files**: `tests/backend/test_migration_manager_fd_leak.py` (FD leak test, pool state test)

### 7. Sample count preservation in DSP pipeline
- **Status**: PASS
- **Source**: Seed registry
- **Files checked**: `auralis/core/hybrid_processor.py:305-309,337-341`
- **Fix present**: Yes — explicit `assert processed.shape == target_audio.shape` in both adaptive and hybrid modes
- **Tests exist**: Yes
- **Test files**: `tests/regression/test_sample_count_invariant.py` (4 tests), `tests/auralis/test_audio_processing_invariants.py`, `tests/auralis/core/test_compression_expansion_invariants.py`

### 8. Copy-before-modify pattern
- **Status**: PASS
- **Source**: Seed registry
- **Files checked**: `auralis/core/simple_mastering.py:303`, `auralis/core/mastering_branches.py:174,266,342`
- **Fix present**: Yes — `processed = audio.copy()` at entry of all processing methods
- **Tests exist**: Yes
- **Test files**: `tests/auralis/core/test_compression_expansion_invariants.py` (9 input-preservation tests)

### 9. Thread-safe player state (RLock)
- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/player/playback_controller.py:39` (RLock), all state-mutating methods protected
- **Fix present**: Yes — `self._lock = threading.RLock()`, all 12 state-mutating methods use `with self._lock:`
- **Tests exist**: Yes
- **Test files**: `tests/auralis/player/test_playback_controller.py` (5 test classes, ~20 tests including concurrent seek, callback-outside-lock, position setter)

### 10. SQLite thread-safe pooling
- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/library/manager.py:115-122`
- **Fix present**: Yes — `pool_pre_ping=True`, `pool_size=5`, `max_overflow=5`, WAL mode, PRAGMAs
- **Tests exist**: Yes
- **Test files**: `tests/regression/test_sqlite_pool_config.py` (pool bounds, concurrent writes), `tests/concurrency/test_thread_safety.py`

### 11. Repository pattern (no raw SQL)
- **Status**: PASS
- **Source**: Seed registry
- **Files checked**: All 13 repository files in `auralis/library/repositories/`
- **Fix present**: Yes — all DB access via repositories; automated codebase scan prevents leaks
- **Tests exist**: Yes
- **Test files**: `tests/regression/test_no_raw_sql_leaks.py` (automated scan), `tests/integration/test_repositories.py`

### 12. Gapless playback engine
- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/player/gapless_playback_engine.py`
- **Fix present**: Yes — prebuffering, identity-validated transitions, atomic audio swap under dual locks, position reset, sample rate validation
- **Tests exist**: Yes
- **Test files**: `tests/auralis/player/test_gapless_playback_engine.py` (deadlock, position reset, thread lifecycle), `tests/regression/test_fixed_bugs.py`

---

## Recent Fix Commit Verification

### 13. Escape key listener unconditionally attached (#2661)
- **Status**: PARTIAL
- **Source**: Commit `c5103ab4`
- **File checked**: `auralis-web/frontend/src/a11y/focusManagement.ts:110-157`
- **Fix present**: Yes — keydown handler attached before checking focusable elements; focusable elements re-queried on each Tab
- **Tests exist**: No
- **Notes**: New fix from this sprint, no tests yet

### 14. as-any casts removed in usePlaybackState (#2650)
- **Status**: PARTIAL
- **Source**: Commit `215e8ea4`
- **File checked**: `auralis-web/frontend/src/hooks/player/usePlaybackState.ts`
- **Fix present**: Yes — zero `as any` casts, uses `transformPlayerState()` and `RawPlayerStateData`
- **Tests exist**: No

### 15. Dialog accessibility — role=dialog, focus trapping, Escape key (#2649)
- **Status**: PARTIAL
- **Source**: Commit `f6bc9ad3`
- **Files checked**: `hooks/shared/useDialogAccessibility.ts` + 3 consumers
- **Fix present**: Yes — all 3 dialogs have `role="dialog"`, `aria-modal="true"`, `aria-labelledby`
- **Tests exist**: No

### 16. Raw fetch replaced with centralized apiRequest (#2653, #2634)
- **Status**: PARTIAL
- **Source**: Commit `bef066b1`
- **Files checked**: `contexts/EnhancementContext.tsx`, `services/settingsService.ts`
- **Fix present**: Yes — zero raw `fetch()` calls, uses `post()` from `@/utils/apiRequest`
- **Tests exist**: No (frontend-specific)

### 17. API client retries restricted for non-idempotent methods (#2648)
- **Status**: PASS
- **Source**: Commit `6e332b81`
- **File checked**: `services/api/standardizedAPIClient.ts:249-252`
- **Fix present**: Yes — POST/PUT/DELETE default to `maxAttempts = 0`, explicit `idempotent` opt-in
- **Tests exist**: Yes
- **Test files**: `services/api/__tests__/standardizedAPIClient.test.ts` (5 dedicated test cases)

### 18. selectinload for artist queries (#2613)
- **Status**: PARTIAL
- **Source**: Commit `6742dc53`
- **File checked**: `auralis/library/repositories/artist_repository.py` (all methods)
- **Fix present**: Yes — all 5 methods use `selectinload()`, `joinedload` not imported
- **Tests exist**: No dedicated repository test

### 19. Player state push on WebSocket connect (#2606)
- **Status**: PARTIAL
- **Source**: Commit `955b8065`
- **File checked**: `auralis-web/backend/routers/system.py:143-155`
- **Fix present**: Yes — full `player_state` pushed immediately after connect
- **Tests exist**: No backend test; frontend tests cover `position_changed` but not initial connect push

### 20. NaN prevention in stereo_width_analysis (#2611)
- **Status**: PARTIAL
- **Source**: Commit `1cd52ca4`
- **File checked**: `auralis/dsp/utils/stereo.py:39-42`
- **Fix present**: Yes — guard `if np.std(left) < 1e-9 or np.std(right) < 1e-9: return 0.0`
- **Tests exist**: No direct test calling `stereo_width_analysis(np.zeros(...))`

---

## Closed GitHub Issue Verification (HIGH Severity)

### 21. Nine duplicate Track interfaces (#2642)
- **Status**: PARTIAL
- **Source**: Closed 2026-03-02, commit `8225beed`
- **File checked**: `auralis-web/frontend/src/types/domain.ts:48-52`
- **Fix present**: Yes — 5 named `Pick<>` subsets defined, adopted across 37 files
- **Tests exist**: Indirect (type-check script)

### 22. TypeScript incompatible with tsconfig (#2632)
- **Status**: PARTIAL
- **Source**: Closed 2026-03-02, commits `592891db`, `6e332b81`
- **File checked**: `auralis-web/frontend/package.json` (TS 5.9.3, `type-check` script)
- **Fix present**: Yes
- **Tests exist**: Indirect (type-check script itself is the guard)

### 23. No browser security headers (#2574)
- **Status**: PARTIAL
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/backend/config/middleware.py:47-64`
- **Fix present**: Yes — `SecurityHeadersMiddleware` sets X-Content-Type-Options, X-Frame-Options, etc.
- **Tests exist**: Partial (unit test checks header values, no middleware integration test)

### 24. InternalServerError leaks raw exception messages (#2573)
- **Status**: PARTIAL (with residual leak)
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/backend/config/app.py:70-76` (global handler)
- **Fix present**: Yes — global handler returns generic `"Internal server error"`
- **Tests exist**: No
- **Notes**: **Residual leak** — 6 `HTTPException` raise sites in `enhancement.py` (lines 212, 272, 339, 391, 423, 548) still include `str(e)` in the detail field, bypassing the generic error pattern. These are endpoint-specific handlers that catch exceptions before the global handler.

### 25. ProcessingEngine cache key config.sample_rate (#2571)
- **Status**: PARTIAL
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/backend/core/processing_engine.py:222`
- **Fix present**: Yes — uses `config.internal_sample_rate` (valid attribute)
- **Tests exist**: Indirect (config attribute tested elsewhere)

### 26. Backend position_changed WebSocket messages (#2570)
- **Status**: PASS
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/backend/core/state_manager.py:247-251`
- **Fix present**: Yes — `position_changed` broadcast in `_position_update_loop`
- **Tests exist**: Yes — 5+ frontend tests for position_changed handling

### 27. Seek endpoint param mismatch (#2569)
- **Status**: PASS
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/backend/routers/player.py:290-326`
- **Fix present**: Yes — `SeekRequest` Pydantic model with JSON body, field validators
- **Tests exist**: Yes — 3 test cases in `test_player_api_comprehensive.py`

---

## Closed GitHub Issue Verification (MEDIUM Severity)

### 28. artist_repository.search() joinedload (#2609)
- **Status**: PARTIAL
- **Source**: Closed 2026-02-22
- **File checked**: `auralis/library/repositories/artist_repository.py:151-158`
- **Fix present**: Yes — uses `selectinload()`, comment references fix
- **Tests exist**: No

### 29. WebSocket _send_error raw messages (#2608)
- **Status**: PARTIAL (with residual leak)
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/backend/core/audio_stream_controller.py`
- **Fix present**: Yes — primary error paths use generic messages
- **Tests exist**: No
- **Notes**: **Residual leak** — 3 chunk-error handlers (lines ~607, ~799, ~1392) still embed raw `{chunk_error}` in client-facing messages

### 30. Enhancement router CHUNK_INTERVAL (#2607)
- **Status**: PARTIAL
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/backend/routers/enhancement.py:27,103-104,113`
- **Fix present**: Yes — uses `CHUNK_INTERVAL` throughout, `CHUNK_DURATION` not referenced
- **Tests exist**: No

### 31. WebSocket reconnect state push (#2606)
- **Status**: PARTIAL
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/backend/routers/system.py:143-155`
- **Fix present**: Yes
- **Tests exist**: No backend test

### 32. useLibraryData loadMore race condition (#2603)
- **Status**: PARTIAL
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/frontend/src/hooks/library/useLibraryData.ts:64,149-152`
- **Fix present**: Yes — ref-based guard (`isLoadingMoreRef`)
- **Tests exist**: No

### 33. EnhancementContext error handling (#2602)
- **Status**: PARTIAL
- **Source**: Closed 2026-02-22
- **File checked**: `auralis-web/frontend/src/contexts/EnhancementContext.tsx:49`
- **Fix present**: Yes — errors caught, stored in state, re-thrown
- **Tests exist**: No

### 34. Stereo RMS per-channel calculation (#2593, regression of #2579)
- **Status**: PARTIAL
- **Source**: Closed 2026-02-22
- **File checked**: `auralis/core/processing/continuous_mode.py:431-433`, `auralis/analysis/dynamic_range.py:45-49`
- **Fix present**: Yes — uses `audio.ravel()` for stereo, not channel averaging
- **Tests exist**: No direct test for this specific fix

### 35. _get_default_fingerprint frequency scale (#2612)
- **Status**: PARTIAL
- **Source**: Closed 2026-03-01
- **File checked**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:362-370`
- **Fix present**: Yes — 0-1 scale, sums to 1.0
- **Tests exist**: No

### 36. artist_repository joinedload Cartesian product (#2613)
- **Status**: PARTIAL
- **Source**: Closed 2026-03-01
- **File checked**: `auralis/library/repositories/artist_repository.py:31-36,50-55`
- **Fix present**: Yes — `selectinload()` used, `joinedload` not imported
- **Tests exist**: No

### 37. Color.styles.ts migration to design tokens (#2617)
- **Status**: PARTIAL
- **Source**: Closed 2026-03-01
- **File checked**: Commit `0acc25a4`
- **Fix present**: Yes
- **Tests exist**: No

---

## Summary Table

| # | Fix | Source | Status | Fix Present | Tests | Notes |
|---|-----|--------|--------|-------------|-------|-------|
| 1 | Equal-power crossfade | Seed 0a5df7a3 | **PASS** | Yes | Yes | 7+ tests |
| 2 | Parallel sub-bass control | Seed 8bc5b217 | **PASS** | Yes | Yes | 8+ tests |
| 3 | Double-windowing removal | Seed cca59d9c | **PASS** | Yes | Yes | 8 tests, 2 files |
| 4 | Audio loading thread safety | Seed 53cef6b4 | **PARTIAL** | Yes | No | Missing KeyboardInterrupt test |
| 5 | Cursor-based pagination | Seed bd94fd59 | **PASS** | Yes | Yes | 2 tests, multi-batch |
| 6 | Engine disposal | Seed 8adb8d0a | **PASS** | Yes | Yes | FD leak + pool test |
| 7 | Sample count preservation | Seed | **PASS** | Yes | Yes | Assertions + 4 tests |
| 8 | Copy-before-modify | Seed | **PASS** | Yes | Yes | 9 tests |
| 9 | Thread-safe player (RLock) | Seed | **PASS** | Yes | Yes | 5 classes, ~20 tests |
| 10 | SQLite pooling | Seed | **PASS** | Yes | Yes | Pool config + concurrency |
| 11 | Repository pattern | Seed | **PASS** | Yes | Yes | Automated scan + integration |
| 12 | Gapless playback | Seed | **PASS** | Yes | Yes | Deadlock + lifecycle tests |
| 13 | Escape key listener | #2661 c5103ab4 | **PARTIAL** | Yes | No | — |
| 14 | as-any casts removed | #2650 215e8ea4 | **PARTIAL** | Yes | No | — |
| 15 | Dialog accessibility | #2649 f6bc9ad3 | **PARTIAL** | Yes | No | — |
| 16 | Raw fetch → apiRequest | #2653 bef066b1 | **PARTIAL** | Yes | No | — |
| 17 | Retry restrictions | #2648 6e332b81 | **PASS** | Yes | Yes | 5 test cases |
| 18 | selectinload artist | #2613 6742dc53 | **PARTIAL** | Yes | No | — |
| 19 | WS connect state push | #2606 955b8065 | **PARTIAL** | Yes | No | — |
| 20 | NaN stereo_width | #2611 1cd52ca4 | **PARTIAL** | Yes | No | — |
| 21 | Track type consolidation | #2642 8225beed | **PARTIAL** | Yes | Indirect | type-check guard |
| 22 | TS 5 + type-check | #2632 | **PARTIAL** | Yes | Indirect | type-check script |
| 23 | Security headers | #2574 | **PARTIAL** | Yes | Partial | Missing middleware integration test |
| 24 | Exception leak | #2573 | **PARTIAL** | Yes | No | **6 enhancement endpoints still leak str(e)** |
| 25 | Cache key fix | #2571 | **PARTIAL** | Yes | Indirect | — |
| 26 | position_changed WS | #2570 | **PASS** | Yes | Yes | 5+ frontend tests |
| 27 | Seek param fix | #2569 | **PASS** | Yes | Yes | 3 test cases |
| 28 | search() selectinload | #2609 | **PARTIAL** | Yes | No | — |
| 29 | _send_error sanitization | #2608 | **PARTIAL** | Yes | No | **3 chunk-error paths still leak** |
| 30 | CHUNK_INTERVAL | #2607 | **PARTIAL** | Yes | No | — |
| 31 | WS reconnect push | #2606 | **PARTIAL** | Yes | No | — |
| 32 | loadMore race | #2603 | **PARTIAL** | Yes | No | — |
| 33 | Enhancement errors | #2602 | **PARTIAL** | Yes | No | — |
| 34 | Stereo RMS ravel | #2593 | **PARTIAL** | Yes | No | — |
| 35 | Fingerprint scale | #2612 | **PARTIAL** | Yes | No | — |
| 36 | artist joinedload | #2613 | **PARTIAL** | Yes | No | — |
| 37 | Color.styles tokens | #2617 | **PARTIAL** | Yes | No | — |

---

## Results

| Status | Count | Details |
|--------|-------|---------|
| **PASS** | 15 | Fix present + regression tests |
| **PARTIAL** | 22 | Fix present, no/limited regression tests |
| **FAIL** | 0 | — |

**No regressions detected.** All 37 verified fixes remain in the codebase.

**Key concern**: 22 fixes lack dedicated regression tests, making them vulnerable to future regressions. Two fixes (#2573, #2608) have residual issues where the primary fix is present but edge-case paths still exhibit the original bug pattern.
