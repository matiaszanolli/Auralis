---
description: "Run the full pre-release checklist and emit a READY / NOT READY verdict"
argument-hint: "[<target-version>]"
---

# Pre-Release Verification Gate

Run complete pre-release checklist. Produces READY / NOT READY verdict.

**Input**: `$ARGUMENTS` = optional target version (default: read from `auralis/version.py`)

## Step 1: Determine Version

```bash
# Read current version
grep -E "^__version__" auralis/version.py
# If $ARGUMENTS provided, use that as target version
```

## Step 2: Run All 13 Gates

Execute each gate and record PASS / FAIL / WARN:

### Gate 1: Version Consistency

Check that version strings match across all sources (`auralis/version.py` is the source of truth; `sync_version.py` propagates it):
```bash
python scripts/validate_release_metadata.py            # add --expected <target-version> when $ARGUMENTS names one
```
This is the same stdlib-only check the `build-release.yml` preflight runs.

**Verdict**: FAIL if versions don't match.

### Gate 2: Python Type Checks

```bash
mypy auralis/ auralis-web/backend/ --ignore-missing-imports 2>&1 | tail -20
```

**Verdict**: FAIL on any type error. WARN on notes/hints.

### Gate 3: Frontend Type Checks

```bash
cd auralis-web/frontend && pnpm run type-check 2>&1 | tail -20
```

**Verdict**: FAIL on any type error. WARN if command not available.

### Gate 4: Python Tests

```bash
python -m pytest -q -m "not slow" -p no:randomly \
  --ignore=tests/backend/test_system_api.py \
  --ignore=tests/concurrency/test_thread_safety.py \
  --junitxml=pytest-results.xml 2>&1 | tail -5
python scripts/check_pytest_baseline.py pytest-results.xml --strict-stale
```

This is the one place the whole backend suite runs: it takes tens of minutes, and the two ignored files hang when run whole. The suite is a ratchet against `pytest-baseline.json`, so a raw failure is not a finding (see the Test Baselines section of `_audit-common.md`).

**Verdict**: FAIL on any failure not listed in `pytest-baseline.json`, or on a baseline entry that ran and passed (`--strict-stale`), or if the report is missing or collected 0 tests. Report count: passed/failed/skipped.

### Gate 5: Frontend Tests

```bash
cd auralis-web/frontend && pnpm run test:ci || true
pnpm run test:baseline -- --strict-stale
```

**Verdict**: FAIL on any failure not listed in `auralis-web/frontend/test-baseline.json`, or on a stale baseline entry. WARN if no tests found.

### Gate 6: DSP Invariants

Invoke the `/verify-dsp` checklist mentally (read all DSP files and verify the 6 invariants). Report any CRITICAL violations.

**Verdict**: FAIL on any CRITICAL violation. WARN on non-critical.

### Gate 7: Open Blockers

```bash
gh issue list --label "critical" --state open --json number,title
gh issue list --label "high" --state open --json number,title
```

**Verdict**: FAIL if any critical issues open. WARN if high issues open. Report counts.

### Gate 8: Audit Freshness

Check `docs/audits/` for the most recent audit of each type:
```bash
ls -la docs/audits/AUDIT_*.md
```

**Verdict**: WARN if any audit type is older than 14 days. Report dates.

### Gate 9: Regression Seeds

Check that regression test markers exist and pass:
```bash
python -m pytest -q -m "regression" \
  --ignore=tests/backend/test_system_api.py \
  --ignore=tests/concurrency/test_thread_safety.py 2>&1 | tail -20
```

**Verdict**: FAIL if regression tests fail. WARN if no regression tests found.

### Gate 10: Dependencies

Check for unpinned or outdated dependencies:
```bash
# Python
cat requirements.txt | head -30

# Frontend
cd auralis-web/frontend && pnpm outdated 2>&1 | head -20
```

**Verdict**: WARN on unpinned deps. INFO on outdated.

### Gate 11: Rust DSP Build

```bash
cd vendor/auralis-dsp && maturin develop 2>&1 | tail -10
```

**Verdict**: FAIL if build fails. PASS if succeeds or Rust not required.

### Gate 12: Frontend Build

```bash
cd auralis-web/frontend && pnpm run build 2>&1 | tail -20
```

**Verdict**: FAIL if build fails.

### Gate 13: Audit-Skill Sync Age

The audit skills describe the code, and nothing but `/audit-sync` re-checks their claims (the path gate only catches deleted paths). Report how far they have drifted:
```bash
BASE=$(cut -d' ' -f1 .claude/commands/audit-sync/BASELINE)
git rev-list --count "$BASE"..HEAD
```

**Verdict**: WARN if more than 100 commits have landed since the sync baseline (recommend `/audit-sync`). Never FAIL.

## Step 3: Generate Verdict

### Report Format

```
# Pre-Release Verification: v<VERSION>
Date: <TODAY>

## Gate Results

| # | Gate | Status | Details |
|---|------|--------|---------|
| 1 | Version Consistency | PASS/FAIL | |
| 2 | Python Type Checks | PASS/FAIL | N errors |
| 3 | Frontend Type Checks | PASS/FAIL/WARN | |
| 4 | Python Tests | PASS/FAIL | X passed, Y failed |
| 5 | Frontend Tests | PASS/FAIL | X passed, Y failed |
| 6 | DSP Invariants | PASS/FAIL/WARN | N violations |
| 7 | Open Blockers | PASS/FAIL/WARN | N critical, M high |
| 8 | Audit Freshness | PASS/WARN | Oldest: N days |
| 9 | Regression Seeds | PASS/FAIL/WARN | N tests |
| 10 | Dependencies | PASS/WARN | |
| 11 | Rust DSP Build | PASS/FAIL | |
| 12 | Frontend Build | PASS/FAIL | |
| 13 | Audit-Skill Sync Age | PASS/WARN | N commits since sync |

## Verdict: READY / NOT READY

### Blockers (if NOT READY)
- <list of FAIL gates with details>

### Warnings
- <list of WARN gates with details>

### Recommendations
- <actions needed before release>
```

## Rules

- **FAIL on any gate failure**: A single FAIL makes the overall verdict NOT READY
- **WARN is non-blocking**: Warnings should be reviewed but don't block release
- **Critical open issues are automatic blockers**; open high issues are a WARN (Gate 7)
- **Run gates sequentially**: Some gates depend on earlier ones (e.g., tests need builds)
- **Be honest**: Don't skip gates or mark them PASS without actually checking
