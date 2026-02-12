# Regression Verification Audit

Verify that ALL previously fixed issues and recent critical fixes have not regressed. For each fix, confirm the code is still present and check whether regression tests exist.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`:

- **Audio Engine**: `auralis/` — Core Python audio engine
- **Backend**: `auralis-web/backend/` — FastAPI REST + WebSocket (:8765)
- **Frontend**: `auralis-web/frontend/` — React 18, TypeScript
- **Rust DSP**: `vendor/auralis-dsp/` — PyO3 module
- **Tests**: `tests/` — 850+ tests across 21 directories

## Known Fixes Registry

Check ALL of the following. For each: read the file(s), confirm the fix, check for tests.

**IMPORTANT**: This registry should be updated as new critical fixes are made. Add entries when closing important bugs.

| Fix Description | Commit | File(s) to Check | What to Verify |
|----------------|--------|-------------------|----------------|
| Equal-power crossfade between mastering chunks | `0a5df7a3` | `auralis-web/backend/chunked_processor.py` | Crossfade uses equal-power (sqrt) curve, not linear. Overlap region is 3s. |
| Parallel processing for sub-bass control | `8bc5b217` | `auralis/core/simple_mastering.py` | Sub-bass processing uses parallel path to prevent excessive loss |
| Sample count preservation in DSP pipeline | — | `auralis/core/hybrid_processor.py`, `auralis/dsp/unified.py` | `len(output) == len(input)` invariant maintained across all processing stages |
| Copy-before-modify pattern | — | `auralis/core/simple_mastering.py`, `auralis/dsp/unified.py` | `audio.copy()` called before any in-place operations |
| Thread-safe player state (RLock) | — | `auralis/player/enhanced_audio_player.py` | All state mutations protected by RLock |
| SQLite thread-safe pooling | — | `auralis/library/manager.py` | `pool_pre_ping=True` and proper connection pooling configured |
| Repository pattern (no raw SQL) | — | `auralis/library/repositories/` | All database access goes through repository classes, no raw SQL |
| Gapless playback engine | — | `auralis/player/gapless_playback_engine.py` | No gap or click at track boundaries |

Additionally, dynamically discover recent fixes by running:
```bash
git log --oneline --grep="fix:" -20
git log --oneline --grep="Fix" -20
```

For each recent fix commit found, verify the fix is still present in the current code.

## Verification Method

For each issue:

### Step 1: Confirm Fix Code
1. Read the file(s) listed in the registry
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

## Output

Write your report to: **`docs/audits/AUDIT_REGRESSION_<TODAY>.md`** (use today's date).

### Per-Fix Format
```
## <Fix Description>
- **Status**: PASS | PARTIAL | FAIL | N/A
- **Commit**: <hash>
- **File checked**: `<path>:<line>`
- **Fix present**: Yes / No
- **Fix description**: <what the fix does, confirmed in code>
- **Tests exist**: Yes / No
- **Test files**: `<path>` (if applicable)
- **Notes**: <concerns, known limitations>
```

### Summary Table
```
| Fix | Status | Fix Present | Tests | Notes |
|-----|--------|-------------|-------|-------|
| Equal-power crossfade | PASS | Yes | Yes | — |
| ...                    | ...  | ... | ... | ... |

Results: X PASS, Y PARTIAL, Z FAIL, W N/A
```

## Phase 2: Create Issues for FAILs

For any fix with status **FAIL** (regression detected):

1. Create a GitHub issue:
   - **Title**: `[<TODAY>] HIGH - Regression: <fix description> no longer present`
   - **Labels**: `high`, `bug`, + relevant domain label (`audio-integrity`, `player`, `backend`, `library`, `concurrency`)
   - **Body**: Summary of what regressed, original fix commit, what code is now missing, impact, acceptance criteria

2. Print summary at the end.

## Phase 3: Create Issues for PARTIALs

For any fix with status **PARTIAL** (fix present but no tests):

1. Create a GitHub issue:
   - **Title**: `[<TODAY>] LOW - Missing regression test: <fix description>`
   - **Labels**: `low`, `enhancement`
   - **Body**: Summary of the fix, why a regression test is needed, what the test should assert
