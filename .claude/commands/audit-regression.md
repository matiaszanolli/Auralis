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
| Equal-power crossfade between mastering chunks | `0a5df7a3` | `auralis-web/backend/core/chunked_processor.py`, `auralis-web/backend/core/chunk_crossfade.py` | Crossfade uses equal-power (sqrt) curve, not linear. Overlap length comes from `OVERLAP_DURATION` in `auralis-web/backend/core/chunk_boundaries.py` (currently 5.0s) — verify against that constant, never a hardcoded number. |
| Chunk constants have a single source of truth | — | `auralis-web/backend/core/chunk_boundaries.py` | `CHUNK_DURATION=15.0`, `CHUNK_INTERVAL=10.0`, `OVERLAP_DURATION=5.0`, `CONTEXT_DURATION=5.0`; no module redefines them, and chunk counting goes through the overlap-aware `content_chunk_count()`, not `ceil(duration / CHUNK_DURATION)` |
| Parallel processing for sub-bass control | `8bc5b217` | `auralis/core/simple_mastering.py` | Sub-bass processing uses parallel path to prevent excessive loss |
| Double-windowing removal in EQ | `cca59d9c` | `auralis/dsp/` | No double-windowing in VectorizedEQProcessor |
| EQ curve mapped to bands by frequency | `2b3c5b35` | `auralis/dsp/eq/psychoacoustic_eq.py` | Bands are selected by frequency, not raw index. A band-25 IndexError used to silently fall back to the simple EQ — the fallback must not be reachable via index math. |
| WOLA fixed 50% hop + full-Hann synthesis window | — | `auralis/dsp/eq/` | Overlap/hop is not configurable. If someone made it configurable, COLA must have been re-derived — otherwise this is a regression. |
| Audio loading thread safety | `53cef6b4` | `auralis/analysis/fingerprint/` | Audio loading doesn't block on KeyboardInterrupt |
| Cursor-based pagination in cleanup | `bd94fd59` | `auralis/library/` | `cleanup_missing_files` uses ID-cursor, not offset pagination |
| SQLAlchemy engine disposal | `8adb8d0a` | `auralis/library/migration_manager.py` | Engine is disposed in `MigrationManager.close()` |
| Migration lock covers threads too | — | `auralis/library/migration_manager.py` | Inter-process file lock (`fcntl`/`msvcrt`) **and** a same-process `threading.Lock` + double-check. The file lock alone does not serialize threads in one process. |
| Sample count preservation in DSP pipeline | — | `auralis/core/hybrid_processor.py`, `auralis/core/mastering_process_chunk.py` | `len(output) == len(input)` invariant maintained across all processing stages |
| Copy-before-modify pattern | — | `auralis/core/simple_mastering.py`, `auralis/core/stages/` | `audio.copy()` called before any in-place operations |
| Thread-safe player state (RLock) | — | `auralis/player/enhanced_audio_player.py` | All state mutations protected by RLock |
| SQLite thread-safe pooling | — | `auralis/library/database.py` | `pool_pre_ping=True` and proper connection pooling configured |
| Seekable chunk reads | — | `auralis-web/backend/core/seekable_source.py` | Chunk readers get a seekable path; a non-seekable source is converted **once**, never re-decoded whole per chunk (#4737) |
| Parallel-processor cluster stays deleted | `2ca72012` | `auralis/optimization/` | No *parallel_processor.py* / *parallel/* package reappears, and nothing in production imports `auralis.optimization` (#4565) |
| LibraryManager stays deleted | `44af56d8` | `auralis/library/` | No `manager.py`; `LibraryDatabase` is the only composition root and nothing constructs a `LibraryManager` (#4915) |
| Repository pattern (no raw SQL) | — | `auralis/library/repositories/` | All database access goes through repository classes, no raw SQL |
| Gapless playback engine | — | `auralis/player/gapless_playback_engine.py` | No gap or click at track boundaries |
| Path containment on file-serving routes | — | `auralis-web/backend/security/path_security.py`, `auralis-web/backend/routers/files.py` | File-serving routes validate through `path_security`, not hand-rolled prefix checks |

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

**If you run tests to confirm**: scope them. Two files hang when run whole — `tests/backend/test_system_api.py` and `tests/concurrency/test_thread_safety.py` — so run specific classes/tests from those. The full `tests/backend` suite never goes green (broken v15→v16 migration cascades); gate on targeted domain tests, not the whole tree. An untargeted `pytest -m "not slow"` over the repo takes ~75 min, not the 1-2 min CLAUDE.md implies.

**Before calling a failing test a regression**, check it against the tracked baselines — see the Test Baselines section in `_audit-common.md`. Frontend known-failures are listed in `auralis-web/frontend/test-baseline.json`; the backend equivalent is generated by `scripts/check_pytest_baseline.py`. A test that was already failing before the fix landed is not a regression of that fix.

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
| Equal-power crossfade | 0a5df7a3 | PASS | Yes | Yes | — |
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
