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
7. **Specialists are a last resort, not a default.** Each one is a fresh context window — only delegate (`subagent_type: dsp-specialist | backend-specialist | frontend-specialist | library-specialist`) when the issue genuinely spans a subsystem you can't trace yourself. When you do, ask for a conclusion (file:line + root cause), not file dumps.

Don't re-read files already in context, and don't pre-read a whole package — stay on the code path.

**INVESTIGATION.md is optional.** Skip it for single-site fixes — the commit body covers those. Write the 3-5 sentence root-cause analysis only when the investigation surfaced something non-obvious worth preserving (cross-file interaction, a wrong-looking-but-correct invariant).

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

**Inner loop = `mypy <changed-files> --ignore-missing-imports`** (or `pnpm run type-check` for frontend) while iterating — the fastest signal. Do *not* run pytest on every edit; save it for Phase 6.

## Phase 6: Run Tests

Scope first, widen once at the end. Use `-q` (not `-v`) so passes collapse to dots
and only failures print in full — `-v` dumps every test name into context. Scope
both pytest and mypy to what the fix touched. The whole backend suite is a CI job,
not an inner loop: it takes tens of minutes, `tests/backend/test_system_api.py`
and `tests/concurrency/test_thread_safety.py` hang when run whole, and a large
set of known failures is baselined in `pytest-baseline.json`, so a raw failure is not
evidence of a regression (see "Test Baselines" in `_audit-common.md`).

```bash
# Inner loop — the matching tests/ subdir (e.g. tests/backend, tests/audio,
# tests/concurrency, tests/security) or the specific test module for the fix:
python -m pytest -q -m "not slow" tests/<subdir> 2>&1 | tail -30
mypy <changed-dirs-or-files> --ignore-missing-imports 2>&1 | tail -20

# Widen once, only for a fix that crosses subsystems — the slice that imports what
# you changed, never the whole tree, and never the two hanging files:
python -m pytest -q -m "not slow" tests/<subdir-a> tests/<subdir-b> \
  --ignore=tests/backend/test_system_api.py \
  --ignore=tests/concurrency/test_thread_safety.py 2>&1 | tail -30
```

A failure is only yours if it is not listed in `pytest-baseline.json`. The
inverse also bites: `check_pytest_baseline.py --strict-stale` fails CI on a baseline
entry whose test now passes, so a fix that turns a listed test green must drop its
entry (backend: `scripts/check_pytest_baseline.py`; frontend:
`pnpm run test:ci && pnpm run test:baseline:update`, run locally per CLAUDE.md). When in
doubt, run the same test on an unmodified `git worktree` of `HEAD` (never
`git stash`) and compare.

For a fix confined to one domain, the scoped run is sufficient evidence — note
that you scoped it in the commit. If frontend files were changed:
```bash
cd auralis-web/frontend && pnpm run test:memory -- <test-file-or-dir> 2>&1 | tail -30
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
- [ ] **PARALLEL**: If chunked processing is touched — true copies per chunk, correct reassembly order, and emitted chunks still tile with no boundary crossfade (#4642)? A crossfade that comes back must be equal-gain sin²/cos² (#3878), not bare sin/cos equal-power.
- [ ] **SIBLING**: Same bug pattern checked in related files (see `_audit-common.md` Sibling Detection table)?
- [ ] **REPO**: All DB access via `auralis/library/repositories/`? No raw SQL added?
- [ ] **LOCK**: Any new lock acquired in canonical order? No lock held across `await` or callback?
- [ ] **GIL**: Rust PyO3 long compute releases the GIL?
- [ ] **SCHEMA**: If a Pydantic model changed, frontend types match?
- [ ] **TOKEN**: If frontend code touched, no raw hex colors (use `tokens`)?
- [ ] **TEST**: Regression test added when applicable, with a real assertion? (`scripts/check_weak_assertions.py` rejects new `is not None`-only and zero-assertion tests.)
- [ ] **NEST**: No function nested deeper than four control-flow levels? (`tests/regression/test_control_flow_nesting_5839.py` fails on one; flatten with guard clauses or a helper.)
- [ ] **DELETION**: If the fix deletes or renames a file or symbol — grep its name across `.claude/`, `docs/architecture`, `docs/subsystems` and `CLAUDE.md`, and run `.claude/commands/_audit-validate.sh` (strict scope must exit 0). Since `2030b97d` (#5818) the `path-references` pre-commit hook (`scripts/pre_commit_path_references.sh`) runs the same gate automatically on any commit that deletes or renames files, but it never fires for a deleted symbol and checks only backticked paths — the grep is still yours. Leave no "was removed in #NNNN" comment behind: `scripts/check_breadcrumbs.py` (a `backend-tests.yml` step) fails on it, and the git log carries that history (#6257). Deletion refactors that skipped this turned the path gate red on master twice (#5526 in `7088915d`, #5642 in `05cbb1c1`).
- [ ] **LOC**: If this issue is a god-file/oversized-module split, re-run `wc -l` on the target file before closing (#4673) — close only when it's under the project's 300-LOC rule, otherwise re-scope the issue (update its body with the current LOC and what remains) and leave it open rather than closing on partial progress. Four issues (#4245, #4249, #4250, #4254) were closed in 2026-07 while their targets stayed 2.3-2.7x over the limit, understating the real backlog until re-audited. Since #5830 the closed split targets are held by `loc-ceilings.json`: run `python scripts/check_loc_ratchet.py` for any fix that adds lines to a listed file (a `backend-tests.yml` step; ceilings only go down, so put new code in a sibling module), and enrol each new split target at its measured size with `--update` in the same commit (#6268).

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
