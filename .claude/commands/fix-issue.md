---
description: "Fetch a GitHub issue, investigate, plan, implement, test, commit, and close"
argument-hint: "<issue-number-or-url>"
---

# Automated Issue Remediation

Read a GitHub issue, investigate root cause, implement the fix, run tests, commit, and close.

**Input**: `$ARGUMENTS` = issue number (e.g. `2613`) or URL.

## Phase 1: Fetch & Snapshot

```bash
ISSUE="${ARGUMENTS}"
ISSUE="${ISSUE##*/}"
mkdir -p ".claude/issues/$ISSUE"
gh issue view "$ISSUE" --json number,title,body,labels,comments,state \
  > ".claude/issues/$ISSUE/ISSUE.json"
gh issue view "$ISSUE" > ".claude/issues/$ISSUE/ISSUE.md"
```

If the issue is already CLOSED, inform the user and stop.

If `.claude/issues/$ISSUE/ISSUE.md` already exists from a prior run, use it as additional context — it may contain investigation notes worth carrying forward.

## Phase 2: Classify Domain

Map the issue to a codebase domain using labels and content:

| Domain | Labels | Key Paths | Consult Specialist |
|--------|--------|-----------|-------------------|
| Audio Core | `audio-integrity`, `dsp` | `auralis/core/`, `auralis/dsp/` | `dsp-specialist` |
| Player | `player` | `auralis/player/` | `dsp-specialist` |
| Audio I/O | `audio-integrity` | `auralis/io/` | `dsp-specialist` |
| Library/DB | `library` | `auralis/library/` | `library-specialist` |
| Analysis | `fingerprint` | `auralis/analysis/` | `dsp-specialist` |
| Backend | `backend`, `streaming`, `websocket` | `auralis-web/backend/` | `backend-specialist` |
| Frontend | `frontend` | `auralis-web/frontend/src/` | `frontend-specialist` |
| Rust DSP | `dsp` | `vendor/auralis-dsp/` | `dsp-specialist` |
| Concurrency | `concurrency` | Cross-cutting | (depends on subsystem) |
| Security | `security` | Cross-cutting | `backend-specialist` |

If the issue body mentions specific files or line numbers, start there. Otherwise, search by keywords from the issue title and description.

## Phase 3: Investigate Root Cause

**CRITICAL RULE**: Never start implementing before fully understanding the root cause.

1. Read the files mentioned in the issue evidence.
2. Trace the code path from entry point to the bug location.
3. Identify WHY the bug occurs, not just WHERE.
4. Check for sibling bugs — same pattern in adjacent files (see `_audit-common.md` "Sibling Detection" table).
5. Check `git blame` on the affected lines to understand the intent of existing code.
6. Look for existing tests that should have caught this.
7. If the domain is complex, delegate to the matching specialist via the Task tool (`subagent_type: dsp-specialist | backend-specialist | frontend-specialist | library-specialist`).

Write a brief root-cause analysis (3-5 sentences) to `.claude/issues/$ISSUE/INVESTIGATION.md` before proceeding.

## Phase 4: Scope Check

Count how many files need changes. If **more than 5 files** need modification:

1. STOP and summarize the plan:
   - List each file and what changes it needs.
   - Explain the fix strategy.
   - Note any risks or side effects.
2. Ask the user to confirm before proceeding.

If 5 or fewer files, proceed directly.

## Phase 5: Implement the Fix

Follow project conventions from CLAUDE.md:

- **DRY**: Improve existing code, never duplicate logic.
- **Modular**: Keep files under 300 lines, single responsibility.
- **Repository pattern**: All DB access via `auralis/library/repositories/`.
- **Audio DSP**: `audio.copy()` before modify, preserve sample count, preserve dtype.
- **Python backend**: `async def` handlers, errors via `HTTPException`, `RLock` for shared state.
- **React frontend**: `@/` imports only, colors from `tokens`, components < 300 lines.

## Phase 6: Run Tests

```bash
python -m pytest -m "not slow" -v 2>&1 | tail -30
mypy auralis/ auralis-web/backend/ --ignore-missing-imports 2>&1 | tail -20
```

If frontend files were changed:
```bash
cd auralis-web/frontend && npm run test:memory 2>&1 | tail -30
```

If tests fail:
1. Read the failure output carefully.
2. Determine if the failure is related to your fix or pre-existing.
3. If related: fix the issue and re-run.
4. If pre-existing: note it but proceed (and mention in the commit).

## Phase 7: Completeness Checks

Before committing, verify each keyed check. Reference these tags in the commit if applicable:

- [ ] **COPY**: If audio code is touched — `audio.copy()` before any in-place NumPy op?
- [ ] **SAMPLE**: `len(output) == len(input)` preserved at every stage?
- [ ] **DTYPE**: `float32` / `float64` preserved? No silent casts?
- [ ] **NAN**: Division / log / sqrt guarded against NaN/Inf?
- [ ] **CLIP**: Output clamped to `[-1.0, 1.0]` before PCM emission?
- [ ] **PARALLEL**: True copies in parallel processing, correct reassembly order, equal-power crossfade?
- [ ] **SIBLING**: Same bug pattern checked in related files (see `_audit-common.md` Sibling Detection table)?
- [ ] **REPO**: All DB access via `auralis/library/repositories/`? No raw SQL added?
- [ ] **LOCK**: Any new lock acquired in canonical order? No lock held across `await` or callback?
- [ ] **GIL**: Rust PyO3 long compute releases the GIL?
- [ ] **SCHEMA**: If a Pydantic model changed, frontend types match?
- [ ] **TOKEN**: If frontend code touched, no raw hex colors (use `tokens`)?
- [ ] **TEST**: Regression test added when applicable?

## Phase 8: Commit and Close

Stage and commit with the conventional format:

```bash
git add <specific-files>
git commit -m "fix: <description> (#$ISSUE)"
gh issue close "$ISSUE" --comment "Fixed in $(git rev-parse --short HEAD). <brief summary>"
```

Append the close comment to the local snapshot:
```bash
echo "Closed: $(date -Iseconds) — $(git rev-parse --short HEAD)" \
  >> ".claude/issues/$ISSUE/CLOSED.md"
```

## Error Handling

- If the issue description is unclear, ask the user for clarification before investigating.
- If the root cause is in a dependency (not project code), report this to the user instead of fixing.
- If the fix requires architectural changes, summarize the options and ask the user to choose.
- If tests reveal other bugs unrelated to this issue, note them but don't fix them.
