# Automated Issue Remediation

Read a GitHub issue, investigate root cause, implement the fix, run tests, commit, and close.

**Input**: `$ARGUMENTS` = issue number (e.g. `2613`) or URL

## Step 1: Understand the Issue

```bash
ISSUE="${ARGUMENTS}"
ISSUE="${ISSUE##*/}"
gh issue view "$ISSUE" --json number,title,body,labels,comments,state
```

If the issue is already CLOSED, inform the user and stop.

## Step 2: Classify Domain

Map the issue to a codebase domain using labels and content:

| Domain | Labels | Key Paths |
|--------|--------|-----------|
| Audio Core | `audio-integrity`, `dsp` | `auralis/core/`, `auralis/dsp/` |
| Player | `player` | `auralis/player/` |
| Audio I/O | `audio-integrity` | `auralis/io/` |
| Library/DB | `library` | `auralis/library/` |
| Analysis | `fingerprint` | `auralis/analysis/` |
| Backend | `backend`, `streaming`, `websocket` | `auralis-web/backend/` |
| Frontend | `frontend` | `auralis-web/frontend/src/` |
| Rust DSP | `dsp` | `vendor/auralis-dsp/` |
| Concurrency | `concurrency` | Cross-cutting |
| Security | `security` | Cross-cutting |

If the issue body mentions specific files or line numbers, start there. Otherwise, search by keywords from the issue title and description.

## Step 3: Investigate Root Cause

**CRITICAL RULE**: Never start implementing before fully understanding the root cause.

1. Read the files mentioned in the issue evidence
2. Trace the code path from entry point to the bug location
3. Identify WHY the bug occurs, not just WHERE
4. Check if similar patterns exist elsewhere in the same file or module
5. Check git blame on the affected lines to understand the intent of existing code
6. Look for existing tests that should have caught this

Write a brief root cause analysis (3-5 sentences) before proceeding.

## Step 4: Check Scope

Count how many files need changes. If **more than 5 files** need modification:

1. STOP and summarize the plan:
   - List each file and what changes it needs
   - Explain the fix strategy
   - Note any risks or side effects
2. Ask the user to confirm before proceeding

If 5 or fewer files, proceed directly.

## Step 5: Implement the Fix

Follow project conventions from CLAUDE.md:

- **DRY**: Improve existing code, never duplicate logic
- **Modular**: Keep files under 300 lines, single responsibility
- **Repository pattern**: All DB access via `auralis/library/repositories/`
- **Audio DSP**: `audio.copy()` before modify, preserve sample count, preserve dtype
- **Python backend**: `async def` handlers, errors via `HTTPException`, `RLock` for shared state
- **React frontend**: `@/` imports only, colors from `tokens`, components < 300 lines

### If audio code is touched — verify 6 invariants:

1. `len(output) == len(input)` at every stage
2. `audio.copy()` before any in-place NumPy ops
3. `float32`/`float64` throughout, no silent casts
4. Guards on division, log, sqrt — no NaN/Inf propagation
5. Clamped to `[-1.0, 1.0]` before output
6. True copies in parallel processing, correct reassembly order

## Step 6: Run Tests

```bash
python -m pytest -m "not slow" -v 2>&1 | tail -30
mypy auralis/ auralis-web/backend/ --ignore-missing-imports 2>&1 | tail -20
```

If frontend files were changed:
```bash
cd auralis-web/frontend && npm run test:memory 2>&1 | tail -30
```

If tests fail:
1. Read the failure output carefully
2. Determine if the failure is related to your fix or pre-existing
3. If related: fix the issue and re-run
4. If pre-existing: note it but proceed

## Step 7: Commit and Close

Stage and commit with the conventional format:

```bash
git add <specific-files>
git commit -m "fix: <description> (#$ISSUE)"
gh issue close "$ISSUE" --comment "Fixed in $(git rev-parse --short HEAD). <brief summary of what was changed>"
```

## Error Handling

- If the issue description is unclear, ask the user for clarification before investigating
- If the root cause is in a dependency (not project code), report this to the user instead of fixing
- If the fix requires architectural changes, summarize the options and ask the user to choose
- If tests reveal other bugs unrelated to this issue, note them but don't fix them
