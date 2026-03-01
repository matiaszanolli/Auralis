# Pre-Release Verification Gate

Run complete pre-release checklist. Produces READY / NOT READY verdict.

**Input**: `$ARGUMENTS` = optional target version (default: read from `auralis/version.py`)

## Step 1: Determine Version

```bash
# Read current version
grep -E "^__version__" auralis/version.py
# If $ARGUMENTS provided, use that as target version
```

## Step 2: Run All 12 Gates

Execute each gate and record PASS / FAIL / WARN:

### Gate 1: Version Consistency

Check that version strings match across all sources:
- `auralis/version.py` (source of truth)
- `auralis-web/frontend/package.json`
- Any other version references

**Verdict**: FAIL if versions don't match.

### Gate 2: Python Type Checks

```bash
mypy auralis/ auralis-web/backend/ --ignore-missing-imports 2>&1 | tail -20
```

**Verdict**: FAIL on any type error. WARN on notes/hints.

### Gate 3: Frontend Type Checks

```bash
cd auralis-web/frontend && npm run type-check 2>&1 | tail -20
```

**Verdict**: FAIL on any type error. WARN if command not available.

### Gate 4: Python Tests

```bash
python -m pytest -m "not slow" -v 2>&1 | tail -40
```

**Verdict**: FAIL on any test failure. Report count: passed/failed/skipped.

### Gate 5: Frontend Tests

```bash
cd auralis-web/frontend && npm run test:memory 2>&1 | tail -40
```

**Verdict**: FAIL on any test failure. WARN if no tests found.

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
python -m pytest -m "regression" -v 2>&1 | tail -20
```

**Verdict**: FAIL if regression tests fail. WARN if no regression tests found.

### Gate 10: Dependencies

Check for unpinned or outdated dependencies:
```bash
# Python
cat requirements.txt | head -30

# Frontend
cd auralis-web/frontend && npm outdated 2>&1 | head -20
```

**Verdict**: WARN on unpinned deps. INFO on outdated.

### Gate 11: Rust DSP Build

```bash
cd vendor/auralis-dsp && maturin develop 2>&1 | tail -10
```

**Verdict**: FAIL if build fails. PASS if succeeds or Rust not required.

### Gate 12: Frontend Build

```bash
cd auralis-web/frontend && npm run build 2>&1 | tail -20
```

**Verdict**: FAIL if build fails.

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
- **Critical/high open issues are automatic blockers**
- **Run gates sequentially**: Some gates depend on earlier ones (e.g., tests need builds)
- **Be honest**: Don't skip gates or mark them PASS without actually checking
