---
description: "Verify previously fixed issues have not regressed; check that the fix code is still present and tests exist"
argument-hint: "[--since <date>] [--commits <N>]"
---

# Regression Verification Audit

Verify that ALL previously fixed issues and recent critical fixes have not regressed. For each fix, confirm the code is still present and check whether regression tests exist.

**Shared protocol**: Read `.claude/commands/_audit-common.md` first for project layout, severity framework, methodology, deduplication rules, and GitHub issue template.

## Fix Discovery (Dynamic)

Build the full list of fixes to verify by combining BOTH sources below.

### Source 1: Git History

Run these commands to discover recent fixes dynamically:

```bash
cd /mnt/data/src/matchering
git log --oneline --grep="fix" -30
git log --oneline --grep="Fix" -30
```

For each fix commit found, read the changed files and understand what was fixed.

### Source 2: Closed GitHub Issues

Run this command to find recently closed bug fixes:

```bash
gh issue list --state closed --label bug --limit 50 --json number,title,closedAt
```

For each closed issue, verify the fix is still present in the current code.

### Source 3: Seed Registry

These are known critical invariants that must ALWAYS be verified, regardless of what git history shows. If a fix commit is listed, verify that specific commit's changes are still present.

| Fix Description | Commit | File(s) to Check | What to Verify |
|----------------|--------|-------------------|----------------|
| Emitted chunks tile with no boundary crossfade | #4642 (supersedes `0a5df7a3`) | `auralis-web/backend/core/chunk_file_loading.py` / `chunk_segment_extraction.py`, `auralis-web/backend/core/stream_chunk_ops.py` | Each chunk is rendered with context and trimmed to a non-overlapping `CHUNK_INTERVAL` segment; nothing in the emitted path crossfades (`tests/backend/test_audio_stream_crossfade.py`). The crossfade `0a5df7a3` added was later removed from that path, so its return is a regression. The unused `apply_crossfade_between_chunks` helper and its *chunk_crossfade.py* module were deleted in `a014ad66` (#5776); if a crossfade helper returns, it must be equal-**gain** sin²/cos² (#3878) — bare sin/cos "equal-power" is a regression, not a fix. |
| Chunk constants have a single source of truth | — | `auralis-web/backend/core/chunk_boundaries.py` | `CHUNK_DURATION=15.0`, `CHUNK_INTERVAL=10.0`, `OVERLAP_DURATION=5.0`, `CONTEXT_DURATION=5.0`; no module redefines them, and chunk counting goes through the overlap-aware `content_chunk_count()`, not `ceil(duration / CHUNK_DURATION)` |
| Parallel processing for sub-bass control | `8bc5b217` | `auralis/core/stages/sub_bass_control.py` (`auralis/core/mastering_stage_delegates.py` is the one-line delegate `SimpleMastering` calls it through) | The sub-bass cut goes through the parallel low-shelf path (`ParallelEQUtilities`), not a blanket high-pass; the zero-phase HP only fires on elevated sub-bass, with depth ramping in continuously |
| Double-windowing removal in EQ | `cca59d9c` | `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py` | No analysis window is applied before the FFT in `VectorizedEQProcessor` (`tests/auralis/dsp/test_eq_double_window_artifact.py`) |
| EQ curve mapped to bands by frequency | `2b3c5b35` | `auralis/core/processing/eq_processor.py` (`_eq_curve_to_array`) | Gains are assigned by each critical band's `center_freq`, not by raw index. A band-25 IndexError used to silently fall back to the simple EQ; that fallback was deleted in `23f53cff` (#4972), so an index bug now raises instead of being masked — a reinstated silent fallback is itself a regression. |
| WOLA fixed 50% hop + full-Hann synthesis window | — | `auralis/core/processing/eq_curve.py` (`process_with_psychoacoustic_eq`, the WOLA loop, moved out of `eq_processor.py` in #6272; `auralis/dsp/eq/psychoacoustic_eq.py` only notes it) | `hop_size = chunk_size // 2` with a single full-Hann synthesis window and no analysis pre-window, and output sample 0 restored from frame 0's unwindowed EQ output (#5575) (`tests/regression/test_eq_overlap_add.py`, `tests/auralis/core/test_eq_wola_sample0_5575.py`). Overlap/hop is not configurable. If someone made it configurable, COLA must have been re-derived — otherwise this is a regression. |
| Abandoned fingerprint work cannot block shutdown | `53cef6b4` (the original `ThreadPoolExecutor` fix is obsolete: that code moved to the in-process Rust engine) | `auralis/services/fingerprint_worker.py` | Per-track extraction runs on a **daemon** thread joined with a timeout, never a `ThreadPoolExecutor` — the stdlib executor joins its threads at interpreter exit regardless of `cancel_futures`, so one hung track would hang shutdown |
| Cursor-based pagination in cleanup | `bd94fd59` | `auralis/library/repositories/track_repository_maintenance.py` | `cleanup_missing_files` uses ID-cursor, not offset pagination (`tests/regression/test_cleanup_missing_files_pagination.py`) |
| SQLAlchemy engine disposal | `8adb8d0a` | `auralis/library/migration_manager.py` | Engine is disposed in `MigrationManager.close()` (`tests/backend/test_migration_manager_fd_leak.py`) |
| Migration lock covers threads too | — | `auralis/library/migration_lock.py` | Inter-process file lock (`fcntl`/`msvcrt`) **and** a same-process `threading.Lock` + double-check. The file lock alone does not serialize threads in one process. |
| Sample count preservation in DSP pipeline | — | `auralis/core/hybrid_processor.py`, `auralis/core/mastering_process_chunk.py` | `len(output) == len(input)` invariant maintained across all processing stages |
| Copy-before-modify pattern | — | `auralis/core/stages/`, `auralis/core/dsp/` | No stage mutates the array it was handed in place; the pipeline caller's input array is unchanged after `apply()` (run `/verify-dsp` for the mechanical check) |
| Thread-safe player state (RLock) | — | `auralis/player/playback_controller.py`, `auralis/player/audio_file_manager.py`, `auralis/player/components/queue_manager.py` (+ its `queue_navigation.py` / `queue_shuffle.py` mixins), `auralis/player/gapless_playback_engine.py` (+ `gapless_prebuffer.py`) | Each class that owns mutable playback or queue state holds an `RLock` (not a `Lock`: `advance_with_prebuffer()` and `_audio_lock` re-enter) and mutates that state only inside it. Since #5836 the mutations live mostly in the mixins, which take the host's `self._lock` / `update_lock` — check them, not just the host file |
| SQLite thread-safe pooling | — | `auralis/library/database_engine.py` (split out of `database.py` in #5837), `auralis/library/migration_engine.py` | `pool_pre_ping=True` and proper connection pooling configured |
| Seekable chunk reads | — | `auralis-web/backend/core/seekable_source.py` | Chunk readers get a seekable path; a non-seekable source is converted **once**, never re-decoded whole per chunk (#4737) |
| Parallel-processor cluster stays deleted | `2ca72012` | `auralis/optimization/` | No *parallel_processor.py* / *parallel/* package reappears (#4565). The rest of `auralis/optimization/` **is** live: `python3 scripts/check_optimization_importers.py` must pass and `tests/test_optimization_is_live_5142.py` must exist (#5142). A skill or doc re-describing the package as test-only is itself a regression. |
| LibraryManager stays deleted | `44af56d8` | `auralis/library/` | No `manager.py`; `LibraryDatabase` is the only composition root and nothing constructs a `LibraryManager` (#4915) |
| Repository pattern (no raw SQL) | — | `auralis/library/repositories/` | All database access goes through repository classes, no raw SQL |
| Gapless playback engine | — | `auralis/player/gapless_playback_engine.py` | No gap or click at track boundaries |
| Path containment | — | `auralis-web/backend/security/path_security.py`, `auralis-web/backend/routers/processing_api.py`, `auralis-web/backend/core/stream_track_resolution.py`, `auralis-web/backend/routers/artwork.py`, `auralis-web/backend/routers/processing_jobs.py` | User-supplied paths go through `path_security.validate_file_path` / `validate_user_chosen_directory`, not hand-rolled checks; the two file-serving routes (artwork, processed-job download) contain the resolved path with `is_relative_to` / `relative_to` against their own root, never a string `startswith` prefix check (`tests/security/test_scan_path_validation.py`, `tests/backend/test_artwork_path_validation.py`; the processed-job download containment (#2561) has no guard test). *routers/files.py* serves no files and never used `path_security` |
| HybridProcessor has no dynamics facade or realtime chain | `7279aac8` (#6201), #4873 | `auralis/core/hybrid_processor.py`, `auralis/core/processing/continuous_mode.py` | No `dynamics_processor` / `dynamics_manager` / `reset_dynamics` / `realtime_processor` attribute and no second dynamics stage on `ContinuousMode`; `auralis.dsp.advanced_dynamics` and `auralis.core.hybrid` stay unimportable (`tests/regression/test_dynamics_processor_wiring.py`, now negative guards only) |
| No function nests control flow deeper than four levels | `0ba655c5` (#5839) | `auralis/`, `auralis-web/backend/` | The census stays at zero, both streaming pumps included (`tests/regression/test_control_flow_nesting_5839.py`) |
| BaseRepository owns the swallow-and-log write guard and the detach policy | `c5690a73` (#6212) | `auralis/library/repositories/base.py` | `_guarded()` / `_first_detached()` / `_all_detached()` exist and repositories use them rather than re-rolling `except Exception: session.rollback()` or per-file `expunge` scaffolds (`tests/auralis/library/test_repository_guarded_6212.py`) |
| Never-populated `tracks` columns and unread scanner data stay dropped | `9885b16f`, `4f6c7111`, `ac983208` (#5755) | `auralis/library/models/`, `auralis/library/scan_models.py`, `auralis/library/migration_manager.py` | No `fingerprint_*` status columns or indexes, audio columns or `AudioFileInfo.file_hash` return without a reader (`tests/auralis/library/test_scanner_unused_data_5755.py`) |
| Test-quality and size gates stay wired | `7c75b75c` (#5830), `d1b70c13` (#6237), `9cc0a245` (#6257) | `.github/workflows/backend-tests.yml`, `scripts/check_loc_ratchet.py`, `loc-ceilings.json`, `scripts/check_weak_assertions.py`, `scripts/check_breadcrumbs.py` | Each script still runs as a CI step and exits 0 on HEAD; a ceiling is never raised, a weak-assertion baseline never grows (`tests/regression/test_check_loc_ratchet_5830.py`, `tests/regression/test_check_weak_assertions_zero_5807.py`, `tests/regression/test_check_breadcrumbs_6257.py`) |
| Enhancement presets stay narrowed to `'adaptive'` | `c195ac80`, `ae9d28e3` | `auralis-web/backend/schemas/enhancement.py`, `auralis-web/backend/core/proactive_buffer.py`, `auralis/core/processing/continuous_space.py`, `auralis/core/config/preset_profiles.py`, `auralis-web/frontend/src/types/domain.ts` | `VALID_PRESETS == ["adaptive"]` and every mirror agrees; no removed name (gentle, warm, bright, punchy, live) reappears in an engine table, API literal, keyboard shortcut or UI. Intentional exceptions: `auralis/core/analysis/spectrum_mapper/preset_anchors.py` (calibration anchors) and the `'warm'` pass-through sentinel in the Player and PlaybackSessionContext transport tests. User directive, not a bug fix — do not "restore" the old presets. |

**Note**: This registry should be updated when new critical fixes are made. Add entries when closing important bugs.

## Verification Method

For each fix (from all sources):

### Step 1: Confirm Fix Code
1. Read the file(s) listed or changed in the commit
2. Look for the specific code described in "What to Verify"
3. Verdict: **FIX PRESENT** or **FIX MISSING** (regression)

### Step 2: Check for Regression Tests
1. Search for test files related to the fix: `grep -r "<keyword>" tests/`
2. Look for test files named after the fix behavior
3. Check if the specific invariant is asserted in any test
4. Verdict: **TESTS PRESENT** (list files) or **NO TESTS**

**If you run tests to confirm**: scope them. Two files hang when run whole — `tests/backend/test_system_api.py` and `tests/concurrency/test_thread_safety.py` — so run specific classes/tests from those. The full `tests/backend` suite is not green (its known failures are baselined, see below); gate on targeted domain tests, not the whole tree. An untargeted `pytest -m "not slow"` over the repo takes tens of minutes.

**Before calling a failing test a regression**, check it against the tracked baselines — see the Test Baselines section in `_audit-common.md`. Frontend known-failures are listed in `auralis-web/frontend/test-baseline.json`; backend known-failures are listed in `pytest-baseline.json` (checked by `scripts/check_pytest_baseline.py --strict-stale`). A test that was already failing before the fix landed is not a regression of that fix.

### Step 3: Assign Status
- **PASS**: Fix present + tests exist
- **PARTIAL**: Fix present but no regression tests
- **FAIL**: Fix missing or broken (REGRESSION)
- **N/A**: Fix pending or not applicable

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_REGRESSION_<TODAY>.md`** (use today's date).

### Per-Fix Format

```
## <Fix Description>
- **Status**: PASS | PARTIAL | FAIL | N/A
- **Source**: Git commit <hash> | GitHub issue #NNN | Seed registry
- **File checked**: `<path>:<line>`
- **Fix present**: Yes / No
- **Fix description**: <what the fix does, confirmed in code>
- **Tests exist**: Yes / No
- **Test files**: `<path>` (if applicable)
- **Notes**: <concerns, known limitations>
```

### Summary Table

```
| Fix | Source | Status | Fix Present | Tests | Notes |
|-----|--------|--------|-------------|-------|-------|
| Chunks tile, no crossfade | #4642 | PASS | Yes | Yes | — |
| ...                    | ...      | ...  | ... | ... | ... |

Results: X PASS, Y PARTIAL, Z FAIL, W N/A
```

## Phase 2: Report Finalization

1. Save the report to `docs/audits/AUDIT_REGRESSION_<TODAY>.md`
2. Do NOT create GitHub issues directly
3. Inform the user the report is ready and suggest:
   ```
   /audit-publish docs/audits/AUDIT_REGRESSION_<TODAY>.md
   ```

**Note**: When publishing, FAILs become HIGH severity issues and PARTIALs become LOW enhancement issues.
