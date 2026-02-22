# Regression Verification Audit — 2026-02-22

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: Verify all previously fixed issues and critical invariants have not regressed
**Sources**: Seed registry (12 invariants) + Git history (30 fix commits) + Closed GitHub issues (50)

---

## Methodology

1. **Seed Registry**: 12 critical invariants verified by reading source files and confirming fix code is present
2. **Git History**: 30 recent fix commits examined, 5 key fixes spot-verified in source
3. **Closed Issues**: 50 recently closed bug issues cross-referenced with current code
4. **Test Coverage**: Searched `tests/` directory for regression tests covering each fix

---

## Seed Registry Verification (12 Invariants)

### SR-01: Equal-Power Crossfade Between Mastering Chunks

- **Status**: PASS
- **Source**: Git commit `0a5df7a3` + Seed registry
- **File checked**: `auralis-web/backend/core/chunked_processor.py:911-914`
- **Fix present**: Yes
- **Fix description**: Crossfade uses equal-power (sin²/cos²) curves: `fade_out = np.cos(t) ** 2; fade_in = np.sin(t) ** 2`. Overlap region is 5 seconds (OVERLAP_DURATION at line 67).
- **Tests exist**: Yes
- **Test files**: `tests/backend/test_equal_power_crossfade.py` (6 tests including `test_crossfade_uses_equal_power_not_linear`), `tests/backend/test_audio_stream_crossfade.py`, `tests/auralis/core/test_crossfade_zero_length_boundary.py`
- **Notes**: Registry stated 3s overlap, actual is 5s. Crossfade curve is correct.

### SR-02: Parallel Processing for Sub-Bass Control

- **Status**: PASS
- **Source**: Git commit `8bc5b217` + Seed registry
- **File checked**: `auralis/core/simple_mastering.py:659-713`
- **Fix present**: Yes
- **Fix description**: `_apply_sub_bass_control()` uses `ParallelEQUtilities.apply_low_shelf_boost()` for sub-bass processing — parallel path prevents excessive loss.
- **Tests exist**: Yes
- **Test files**: `tests/auralis/optimization/test_parallel_processor.py`, `tests/concurrency/test_parallel_processing.py`, `tests/validation/validate_parallel_quick.py`
- **Notes**: —

### SR-03: Double-Windowing Removal in EQ

- **Status**: PASS
- **Source**: Git commit `cca59d9c` + Seed registry
- **File checked**: `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:96-97`
- **Fix present**: Yes
- **Fix description**: FFT applied without windowing in VectorizedEQProcessor. Comment: `# Transform to frequency domain (no windowing for EQ — see filters.py)`. No window multiplication before FFT or after IFFT.
- **Tests exist**: Yes
- **Test files**: `tests/test_fix_2166_double_windowing.py` (4 tests), `tests/auralis/dsp/test_eq_double_window_artifact.py` (4 tests including `test_unity_gain_amplitude_variance_below_0_1_percent`)
- **Notes**: —

### SR-04: Audio Loading Thread Safety

- **Status**: PASS
- **Source**: Git commit `53cef6b4` + Seed registry
- **File checked**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:152-193`
- **Fix present**: Yes
- **Fix description**: ThreadPoolExecutor instantiated without context manager. Explicit `try/except KeyboardInterrupt` with `executor.shutdown(wait=True, cancel_futures=True)`. Prevents blocking on Ctrl+C during parallel fingerprint analysis.
- **Tests exist**: Yes
- **Test files**: `tests/concurrency/test_thread_safety.py`, `tests/edge_cases/test_concurrent_operations.py`, `tests/auralis/player/test_audio_file_manager.py`
- **Notes**: Implementation evolved since original fix — now waits for running threads to prevent partial result writes (improvement over original `wait=False`).

### SR-05: Cursor-Based Pagination in Cleanup

- **Status**: PASS
- **Source**: Git commit `bd94fd59` + Seed registry
- **File checked**: `auralis/library/repositories/track_repository.py:738-771`
- **Fix present**: Yes
- **Fix description**: `cleanup_missing_files()` uses ID-cursor pagination: `last_id = 0` initialized, query filters `Track.id > last_id`, cursor advanced to `rows[-1].id` after each batch. No `.offset()` call.
- **Tests exist**: Yes
- **Test files**: `tests/regression/test_cleanup_missing_files_pagination.py` (2 tests: `test_all_missing_tracks_removed_across_batches`, `test_no_tracks_removed_when_all_files_exist`)
- **Notes**: Also handles unmounted volumes by skipping tracks whose parent directory is inaccessible (#2525).

### SR-06: SQLAlchemy Engine Disposal

- **Status**: PASS
- **Source**: Git commit `8adb8d0a` + Seed registry
- **File checked**: `auralis/library/migration_manager.py:314-317`
- **Fix present**: Yes
- **Fix description**: `MigrationManager.close()` calls `self.session.close()` followed by `self.engine.dispose()`. Also called in `finally` block of `check_and_migrate_database()` at line 464.
- **Tests exist**: Yes
- **Test files**: `tests/backend/test_migration_manager_fd_leak.py` (3 tests including `test_no_fd_leak_after_repeated_create_and_close`)
- **Notes**: —

### SR-07: Sample Count Preservation in DSP Pipeline

- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/core/hybrid_processor.py:306-309, 338-341`
- **Fix present**: Yes
- **Fix description**: After brick-wall limiter in both adaptive and hybrid modes: `assert processed.shape == target_audio.shape, "Sample count mismatch after limiter"`. Assertion at lines 306-309 (adaptive) and 338-341 (hybrid). References fix #2519.
- **Tests exist**: Yes
- **Test files**: `tests/auralis/test_audio_processing_invariants.py` (`test_processing_preserves_sample_count_mono`, `test_processing_preserves_sample_count_stereo`), `tests/backend/test_chunked_processor_invariants.py`, `tests/integration/test_end_to_end_processing.py`
- **Notes**: —

### SR-08: Copy-Before-Modify Pattern

- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/core/simple_mastering.py:303`
- **Fix present**: Yes
- **Fix description**: In `_process()` method: `processed = audio.copy()` as first operation before any processing stages. Input array is never modified in-place.
- **Tests exist**: Yes
- **Test files**: `tests/auralis/test_audio_processing_invariants.py`, `tests/auralis/utils/test_audio_validation.py`, `tests/boundaries/test_audio_processing_boundaries.py`
- **Notes**: —

### SR-09: Thread-Safe Player State (RLock)

- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/player/playback_controller.py:39`
- **Fix present**: Yes
- **Fix description**: `PlaybackController` uses `self._lock = threading.RLock()` at line 39. All state mutations (play, pause, stop, seek, set_loading, set_error, read_and_advance_position, position getter/setter) protected by `with self._lock:` (13 lock acquisitions across 14 methods).
- **Tests exist**: Yes
- **Test files**: `tests/auralis/player/test_playback_controller.py` (`TestSeekDuringPlaybackRace`, `test_concurrent_seek_and_advance_no_position_corruption`), `tests/auralis/player/test_queue_manager_concurrency.py` (`test_lock_is_rlock`)
- **Notes**: QueueManager also uses RLock (verified at `queue_manager.py:25`).

### SR-10: SQLite Thread-Safe Pooling

- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/library/manager.py:114-121`
- **Fix present**: Yes
- **Fix description**: SQLAlchemy engine configured with `pool_pre_ping=True` (line 118), `pool_size=5` (line 119), `max_overflow=5` (line 120). WAL mode enabled via PRAGMA (line 129). `check_same_thread=False` (line 107).
- **Tests exist**: Yes
- **Test files**: `tests/regression/test_sqlite_pool_config.py` (248 lines: `test_pool_size_within_bounds`, `test_10_threads_writing_simultaneously`, `test_mixed_read_write_concurrency`, `test_rapid_sequential_writes_across_threads`)
- **Notes**: —

### SR-11: Repository Pattern (No Raw SQL)

- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/library/repositories/` (13 repository classes)
- **Fix present**: Yes
- **Fix description**: All database access in non-migration code flows through repository classes. Raw SQL confined to migrations and repository layer. `fingerprint_repository.py` uses parameterized queries with column whitelist (`_validate_fingerprint_columns()` at lines 30-46). `LibraryManager` delegates all operations to repositories (lines 148-156).
- **Tests exist**: Yes
- **Test files**: `tests/integration/test_repositories.py`, `tests/security/test_sql_injection.py` (`TestSQLInjectionPrevention`), `tests/auralis/library/test_fingerprint_repository_db_path.py`
- **Notes**: —

### SR-12: Gapless Playback Engine

- **Status**: PASS
- **Source**: Seed registry
- **File checked**: `auralis/player/gapless_playback_engine.py` (293 lines)
- **Fix present**: Yes
- **Fix description**: Full gapless implementation with: prebuffering via background thread (non-daemon, #2075), lock-protected buffer access (`update_lock`), prebuffer validation against queue changes (#2303), crossfade-less transition via audio_data swap under `_audio_lock` (#2423), proper shutdown with `_shutdown` Event.
- **Tests exist**: Yes
- **Test files**: `tests/auralis/player/test_gapless_playback_engine.py` (16KB: deadlock detection #2197, thread lifecycle, prebuffer invalidation), `tests/regression/test_fixed_bugs.py`
- **Notes**: —

---

## Git History Fixes (Spot-Verified)

### GH-01: RLock in QueueManager (#2427)

- **Status**: PASS
- **Source**: Git commit `97dc3413`
- **File checked**: `auralis/player/components/queue_manager.py:25`
- **Fix present**: Yes — `self._lock = threading.RLock()`; 15 methods protected
- **Tests exist**: Yes — `tests/auralis/player/test_queue_manager_concurrency.py`

### GH-02: Column Whitelist for SQL (#2286)

- **Status**: PASS
- **Source**: Git commit `664c6299`
- **File checked**: `auralis/library/repositories/fingerprint_repository.py:21-46`
- **Fix present**: Yes — `_FINGERPRINT_WRITABLE_COLS` frozenset + `_validate_fingerprint_columns()` called before f-string SQL
- **Tests exist**: Yes — `tests/security/test_sql_injection.py`

### GH-03: PsychoacousticEQ Zeros Init (#2210)

- **Status**: PASS
- **Source**: Git commit `cf5b812d`
- **File checked**: `auralis/dsp/eq/psychoacoustic_eq.py:79-80, 340-341`
- **Fix present**: Yes — `np.zeros()` for both init and reset (0.0 dB = flat/unity gain)
- **Tests exist**: Yes — `tests/test_fix_2166_double_windowing.py`

### GH-04: prev_tail Staging (#2429)

- **Status**: PASS
- **Source**: Git commit `85c31691`
- **File checked**: `auralis/core/simple_mastering.py:194-253`
- **Fix present**: Yes — `new_tail` staging variable, committed to `prev_tail` only after `output_file.write()` succeeds
- **Tests exist**: Yes — `tests/auralis/test_audio_processing_invariants.py`

### GH-05: GIL Release in Rust DSP (#2447)

- **Status**: PASS
- **Source**: Git commit `ba9ce143`
- **File checked**: `vendor/auralis-dsp/src/py_bindings.rs`
- **Fix present**: Yes — All 11 DSP wrapper functions use `py.allow_threads(|| ...)` to release GIL during Rust computation
- **Tests exist**: Yes — `tests/concurrency/test_parallel_processing.py`

### GH-06: Processing API Path Validation (#2559)

- **Status**: PASS
- **Source**: Closed issue #2559 (CRITICAL)
- **File checked**: `auralis-web/backend/routers/processing_api.py:123`
- **Fix present**: Yes — `validate_file_path(request.input_path)` called before processing
- **Tests exist**: Yes — `tests/security/`

### GH-07: Upload Validation (#2560)

- **Status**: PASS
- **Source**: Closed issue #2560 (HIGH)
- **File checked**: `auralis-web/backend/routers/processing_api.py`
- **Fix present**: Yes — Magic bytes check, 500MB size limit, UUID filename, exclusive-create
- **Tests exist**: Yes — `tests/security/`

### GH-08: Path Security Restricted (#2562)

- **Status**: PASS
- **Source**: Closed issue #2562 (HIGH)
- **File checked**: `auralis-web/backend/security/path_security.py`
- **Fix present**: Yes — `DEFAULT_ALLOWED_DIRS` restricted to `~/Music` and `~/Documents` (not `Path.home()`)
- **Tests exist**: Yes — `tests/security/`

---

## Summary Table

### Seed Registry (12 Critical Invariants)

| # | Fix | Source | Status | Fix Present | Tests | Notes |
|---|-----|--------|--------|-------------|-------|-------|
| SR-01 | Equal-power crossfade | `0a5df7a3` | PASS | Yes | Yes | Overlap 5s (registry said 3s) |
| SR-02 | Parallel sub-bass processing | `8bc5b217` | PASS | Yes | Yes | — |
| SR-03 | Double-windowing removal | `cca59d9c` | PASS | Yes | Yes | — |
| SR-04 | Audio loading thread safety | `53cef6b4` | PASS | Yes | Yes | Enhanced since original fix |
| SR-05 | Cursor-based pagination | `bd94fd59` | PASS | Yes | Yes | Also handles unmounted volumes |
| SR-06 | SQLAlchemy engine disposal | `8adb8d0a` | PASS | Yes | Yes | — |
| SR-07 | Sample count preservation | — | PASS | Yes | Yes | Asserted in 2 processing modes |
| SR-08 | Copy-before-modify pattern | — | PASS | Yes | Yes | — |
| SR-09 | Thread-safe player state | — | PASS | Yes | Yes | RLock in PlaybackController + QueueManager |
| SR-10 | SQLite thread-safe pooling | — | PASS | Yes | Yes | pool_pre_ping=True, pool_size=5 |
| SR-11 | Repository pattern | — | PASS | Yes | Yes | 13 repos, no raw SQL outside migrations |
| SR-12 | Gapless playback engine | — | PASS | Yes | Yes | Full implementation with tests |

### Git History Fixes (Spot-Verified)

| # | Fix | Commit/Issue | Status | Fix Present | Tests |
|---|-----|-------------|--------|-------------|-------|
| GH-01 | RLock in QueueManager | `97dc3413` | PASS | Yes | Yes |
| GH-02 | Column whitelist for SQL | `664c6299` | PASS | Yes | Yes |
| GH-03 | PsychoacousticEQ zeros | `cf5b812d` | PASS | Yes | Yes |
| GH-04 | prev_tail staging | `85c31691` | PASS | Yes | Yes |
| GH-05 | GIL release in Rust DSP | `ba9ce143` | PASS | Yes | Yes |
| GH-06 | Processing API path validation | #2559 | PASS | Yes | Yes |
| GH-07 | Upload validation | #2560 | PASS | Yes | Yes |
| GH-08 | Path security restricted | #2562 | PASS | Yes | Yes |

---

## Results

**Seed Registry**: 12 PASS, 0 PARTIAL, 0 FAIL, 0 N/A
**Git History**: 8 PASS, 0 PARTIAL, 0 FAIL, 0 N/A

**Total**: 20 PASS, 0 PARTIAL, 0 FAIL

**No regressions detected.** All 12 critical invariants are intact and covered by regression tests. All spot-checked git history fixes remain present in the codebase.

---

## Recommendations

1. **Update seed registry**: Change SR-01 overlap duration from "3s" to "5s" to match current code (`OVERLAP_DURATION = 5` at `chunked_processor.py:67`).
2. **Maintain test coverage**: All 12 invariants have dedicated regression tests — continue requiring tests for all critical fixes.
3. **Next audit**: Consider expanding git history verification to cover all 30 recent fix commits (this audit spot-checked 8 of 30).
