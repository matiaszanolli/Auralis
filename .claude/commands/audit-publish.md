# Publish Audit Findings as GitHub Issues

Validate findings from an audit report and create GitHub issues for each confirmed, new finding.

See `.claude/commands/_audit-common.md` for project layout, methodology, deduplication, context rules, and domain labels.

## Input

The `$ARGUMENTS` should be the path to an audit report file (e.g., `docs/audits/AUDIT_BACKEND_2026-03-19.md`).

If no argument is provided, look for the most recent file in `docs/audits/` by modification time and confirm with the user before proceeding.

## Step 1: Load and Parse Report

Read the report file. Extract each finding:
- ID, severity, title, location (file:line), status, description, evidence, impact, suggested fix.

If the report does not use the standard per-finding format, adapt — but ensure you extract at minimum: title, severity, file location, and description for each finding.

Skip any finding already marked as "Existing: #NNN" in the report — these were already deduplicated during the audit.

## Step 2: Validate Each Finding Against Current Code

For every finding with status **NEW** or **Regression**:

1. **Read the referenced file(s) and line(s)** to confirm the issue still exists in the current code.
2. If the code has changed and the issue no longer applies, mark the finding as **STALE** and skip it.
3. If the evidence is weak, attempt to gather stronger evidence (follow the call graph, check related files).
4. If you cannot confirm or deny, mark as **UNVERIFIABLE** with an explanation.

Record validation status for each: **CONFIRMED**, **STALE**, or **UNVERIFIABLE**.

## Step 3: Deduplication Check

Before creating any issue:

1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. For each CONFIRMED finding, search for keywords in existing issue titles.
3. Also scan `docs/audits/` for prior reports that may have covered the same finding.
4. If a matching **open** issue exists: mark as **DUPLICATE of #NNN** and skip.
5. If a matching **closed** issue exists and the fix has regressed: mark as **REGRESSION of #NNN** and create a new issue referencing the original.
6. If no match: mark as **NEW**.

## Step 3b: Classify Incomplete-Fix Risk

30% of audit findings are bugs that were "fixed" but incompletely — dead code, missing sibling updates, broken chains. Before creating issues, classify each finding's incomplete-fix risk so the issue body includes the right verification hints.

For each CONFIRMED finding, check which risk patterns apply:

| Pattern | Detection | Completeness Check to Add |
|---------|-----------|--------------------------|
| **Dead code risk** | Fix requires adding a new function, validator, or decorator | `WIRING: Verify <function> is called from <expected caller>.` |
| **Sibling divergence risk** | Fix touches a file that has a sibling with similar logic (e.g., multiple DSP modules, multiple repository files) | `SIBLING: Apply same fix to <sibling_file>.` |
| **Migration chain risk** | Fix creates or modifies a database migration | `MIGRATION: Verify the migration chain has exactly 1 head.` |
| **Return value risk** | Fix adds a guard/check that returns a sentinel (None, False, error) | `RETURN VALUE: Verify all callers of <function> check the return value.` |
| **Cross-file consistency risk** | Fix applies a pattern change that exists in multiple files (same DSP pattern, same repository method, same hook pattern) | `CONSISTENCY: Same pattern exists in <file1>, <file2>, ... — fix ALL or note as out of scope.` |

**How to detect siblings**: When a finding references a file, check for files with similar names or roles:
- `auralis/dsp/psychoacoustic_eq.py` → check other `auralis/dsp/*.py` for same pattern
- `auralis/library/repositories/track_repository.py` → check other `repositories/*_repository.py`
- `auralis-web/backend/routers/albums.py` → check other `routers/*.py` for same pattern
- `auralis-web/frontend/src/hooks/player/` → check other `hooks/*/` directories

**How to detect wiring risk**: When the proposed fix says "add function", "create validator", "add middleware" — the new code MUST be called from somewhere.

Tag each finding with applicable patterns. These get injected into the issue's `## Completeness Checks` section.

## Step 4: Create GitHub Issues

For each finding that is CONFIRMED + NEW (or REGRESSION), create a GitHub issue:

**Title format**: `[YYYY-MM-DD] <SEVERITY> - <Short Title>`

**Labels**: Apply all relevant:
- **Severity** (exactly one): `critical`, `high`, `medium`, `low`
- **Domain** (one or more): from the domain labels in `_audit-common.md`
- **Type**: `bug`

**Body format** (use a heredoc for `gh issue create`):

```
## Summary
<1-2 sentence description of the issue>

## Evidence / Code Paths
- **File**: `<path>:<line-range>`
- **Code**:
\`\`\`python
<relevant code snippet>
\`\`\`
- **Call path**: <how execution reaches the problematic code>

## Impact
- **Severity**: <SEVERITY>
- **What breaks**: <specific failure mode>
- **When**: <conditions that trigger the issue>
- **Blast radius**: <scope — audio quality, single track, all playback, data integrity, etc.>

## Related Issues
- #NNN — <describe relationship: root cause, compounds, blocks, etc.>

## Proposed Fix
<recommended approach, 1-2 paragraphs>

## Completeness Checks
<MANDATORY — include ALL that apply from Step 3b classification. These prevent the fix from being incomplete.>

<Include ONLY the checks that apply to THIS specific finding. Examples:>

- [ ] **WIRING**: After adding `validate_sample_rate()`, verify it's called from `hybrid_processor.py`. Run: `grep -rn "validate_sample_rate" auralis/ --include='*.py' | grep -v "def validate_sample_rate"` — must show at least 1 caller.
- [ ] **SIBLING**: Same bug exists in `advanced_dynamics.py:120-135`. Apply the same fix there.
- [ ] **RETURN VALUE**: All callers of `<function>()` must check the return value.
- [ ] **CONSISTENCY**: Pattern `<old_pattern>` also exists in `<file2>`, `<file3>`. Fix all or document as out of scope.

<If no risk patterns apply, write: "No special completeness checks required for this fix.">

## Acceptance Criteria
- [ ] <testable criterion 1>
- [ ] <testable criterion 2>
- [ ] All Completeness Checks above pass

## Test Plan
1. **Unit test**: <what to test> — assert <expected result>
2. **Integration test** (if applicable): <what to test> — assert <expected result>
```

## Step 5: Cross-Reference Related Issues

For each newly created issue that references existing issues in its "Related Issues" section:

```bash
gh issue comment <RELATED_ISSUE_NUMBER> --body "Related: #<NEW_ISSUE_NUMBER> — <brief description of relationship>"
```

This ensures bidirectional linking.

## Step 6: Summary Output

After processing all findings, print a summary table:

```
## Publish Summary

| # | Finding | Severity | Validation | Dedup | Issue |
|---|---------|----------|------------|-------|-------|
| 1 | <title> | CRITICAL | CONFIRMED  | NEW   | #NNN  |
| 2 | <title> | HIGH     | CONFIRMED  | DUPLICATE of #NNN | — |
| 3 | <title> | MEDIUM   | STALE      | —     | —     |
| 4 | <title> | HIGH     | CONFIRMED  | REGRESSION of #NNN | #MMM |
| 5 | <title> | LOW      | UNVERIFIABLE | —   | —     |

**Created**: X new issues
**Skipped**: Y duplicates, Z stale, W unverifiable
```
