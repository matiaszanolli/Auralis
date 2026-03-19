# Audit Advisor & Orchestrator

Analyze recent changes and audit history to recommend which audit(s) to run, in what order, and with what focus. This is NOT an audit itself — it's the starting point that tells you what to audit.

See `.claude/commands/_audit-common.md` for project layout, methodology, and context management rules.

## Parameters (from $ARGUMENTS)

- `--since <ref>`: Git ref or date to analyze changes from (default: last 2 weeks)
- `--full`: Skip change analysis and recommend the full audit suite

## Step 1: Gather Change Intelligence

```bash
cd /mnt/data/src/matchering
git log --oneline --since="2 weeks ago"
git diff HEAD~20..HEAD --name-only
```

Categorize changed files by risk domain:

| Domain | File Patterns | Maps to Audit |
|--------|--------------|---------------|
| Audio Core/DSP | `auralis/core/*`, `auralis/dsp/*` | `/audit-engine` |
| Player | `auralis/player/*` | `/audit-engine`, `/audit-concurrency` |
| Audio I/O | `auralis/io/*` | `/audit-engine` |
| Parallel Processing | `auralis/optimization/*` | `/audit-engine`, `/audit-concurrency` |
| Analysis/Fingerprint | `auralis/analysis/*` | `/audit-engine` |
| Library/Database | `auralis/library/*` | `/audit-engine`, `/audit-concurrency` |
| Backend Routes | `auralis-web/backend/routers/*` | `/audit-backend` |
| WebSocket/Streaming | `auralis-web/backend/audio_stream*`, `chunked_processor*` | `/audit-backend`, `/audit-integration` |
| Backend Services | `auralis-web/backend/services/*`, `auralis-web/backend/core/*` | `/audit-backend` |
| Frontend Components | `auralis-web/frontend/src/components/*` | `/audit-frontend` |
| Frontend Hooks | `auralis-web/frontend/src/hooks/*` | `/audit-frontend`, `/audit-integration` |
| Frontend Store | `auralis-web/frontend/src/store/*` | `/audit-frontend` |
| Rust DSP | `vendor/auralis-dsp/*` | `/audit-engine`, `/audit-security` |
| Config/Security | `main.py`, CORS, middleware | `/audit-security` |

## Step 2: Check Audit Coverage History

Read `docs/audits/` to see what's been audited recently:

```bash
ls -lt docs/audits/AUDIT_*.md | head -15
```

For each recent report, note the date, type, and finding count. Build a coverage freshness table:

```
| Audit Type    | Last Run   | Days Ago | Status      |
|---------------|------------|----------|-------------|
| engine        | 2026-03-15 | 4        | FRESH       |
| security      | 2026-03-01 | 18       | STALE       |
| backend       | never      | —        | NEVER RUN   |
| ...           | ...        | ...      | ...         |
```

Freshness rules: FRESH = <5 days, OK = 5-14 days, STALE = 14-30 days, NEVER RUN = no report found.

## Step 3: Cross-Reference Open Issues

```bash
gh issue list --limit 200 --state open --json labels --jq '.[].labels[].name' | sort | uniq -c | sort -rn
```

Identify which domains have the most open issues — high counts may indicate diminishing returns from re-auditing vs. fixing.

## Step 4: Generate Recommendations

Based on changes, coverage freshness, and open issues, output a concrete audit plan.

### Output Format

```
## Audit Recommendation — <DATE>

### Change Summary
- N commits, M files changed
- Key domains: <list domains with changes>

### Recommended Audit Sequence

| Priority | Command | Reason | Suggested Focus |
|----------|---------|--------|-----------------|
| 1 | `/audit-security` | CORS/middleware changed + 18 days stale | `--focus A01,A05,A07` |
| 2 | `/audit-engine` | DSP pipeline modified, player changes | `--focus 1,2,5` |
| 3 | `/audit-regression` | 10 days since last run, 5 new fixes merged | — |
| SKIP | `/audit-frontend` | Ran 3 days ago, no component changes | — |

### Quick Wins
- `/audit-incremental` — 15 commits since last run, fast to execute

### Coverage Gaps
- `/audit-deprecation` has NEVER been run. Consider after next dependency update.

### Open Issue Hotspots
- `concurrency`: 8 open — consider fixing backlog before re-auditing
- `security`: 3 open — audit may find more
```

## Important Rules

- Do NOT perform any audit yourself. Your job is to ADVISE, not audit.
- Do NOT create GitHub issues. That's for `/audit-publish`.
- Base recommendations on evidence (git log, file diffs, audit history), not assumptions.
- If `--full` is passed, recommend the full suite: `/audit-suite --preset comprehensive`.
- Always recommend `/audit-incremental` as a quick win if there are unaudited commits.
- **Note**: Deep audits now use subagent architecture internally — they will not exhaust the context window.
