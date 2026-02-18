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
| Equal-power crossfade between mastering chunks | `0a5df7a3` | `auralis-web/backend/chunked_processor.py` | Crossfade uses equal-power (sqrt) curve, not linear. Overlap region is 3s. |
| Parallel processing for sub-bass control | `8bc5b217` | `auralis/core/simple_mastering.py` | Sub-bass processing uses parallel path to prevent excessive loss |
| Double-windowing removal in EQ | `cca59d9c` | `auralis/dsp/` | No double-windowing in VectorizedEQProcessor |
| Audio loading thread safety | `53cef6b4` | `auralis/analysis/fingerprint/` | Audio loading doesn't block on KeyboardInterrupt |
| Cursor-based pagination in cleanup | `bd94fd59` | `auralis/library/` | `cleanup_missing_files` uses ID-cursor, not offset pagination |
| SQLAlchemy engine disposal | `8adb8d0a` | `auralis/library/migration_manager.py` | Engine is disposed in `MigrationManager.close()` |
| Sample count preservation in DSP pipeline | — | `auralis/core/hybrid_processor.py`, `auralis/dsp/unified.py` | `len(output) == len(input)` invariant maintained across all processing stages |
| Copy-before-modify pattern | — | `auralis/core/simple_mastering.py`, `auralis/dsp/unified.py` | `audio.copy()` called before any in-place operations |
| Thread-safe player state (RLock) | — | `auralis/player/enhanced_audio_player.py` | All state mutations protected by RLock |
| SQLite thread-safe pooling | — | `auralis/library/manager.py` | `pool_pre_ping=True` and proper connection pooling configured |
| Repository pattern (no raw SQL) | — | `auralis/library/repositories/` | All database access goes through repository classes, no raw SQL |
| Gapless playback engine | — | `auralis/player/gapless_playback_engine.py` | No gap or click at track boundaries |

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

## Phase 2: Create Issues for FAILs

For any fix with status **FAIL** (regression detected):

1. Create a GitHub issue:
   - **Title**: `[<TODAY>] HIGH - Regression: <fix description> no longer present`
   - **Labels**: `high`, `bug`, + relevant domain label (`audio-integrity`, `player`, `backend`, `library`, `concurrency`)
   - **Body**: Summary of what regressed, original fix source, what code is now missing, impact, acceptance criteria

## Phase 3: Create Issues for PARTIALs

For any fix with status **PARTIAL** (fix present but no tests):

1. Create a GitHub issue:
   - **Title**: `[<TODAY>] LOW - Missing regression test: <fix description>`
   - **Labels**: `low`, `enhancement`
   - **Body**: Summary of the fix, why a regression test is needed, what the test should assert
