# Audit Suite — Preset Workflows

Run a predefined sequence of audits. This command **actually executes** each audit in the preset by launching a Task agent per audit.

See `.claude/commands/_audit-common.md` for project layout, methodology, and context management rules.

## Parameters (from $ARGUMENTS)

- `--preset <name>`: Which preset to run. Required. Options below.

## Available Presets

### `pre-release` — Run before tagging a release
```
1. /audit-regression          — Verify all known fixes still in place
2. /audit-incremental         — Check recent changes for new bugs
3. /audit-security --depth shallow  — Quick security sanity check
```
**When**: Before every release tag.

### `comprehensive` — Full platform audit
```
1. /audit-engine              — Deep audio engine dive
2. /audit-backend             — Deep backend dive
3. /audit-frontend            — Deep frontend dive
4. /audit-integration         — Cross-layer flow tracing
5. /audit-security            — OWASP Top 10
6. /audit-concurrency         — Race conditions and state integrity
7. /audit-deprecation         — Deprecated APIs and patterns
```
**When**: Monthly or after major architecture changes.

### `post-sprint` — End-of-sprint verification
```
1. /audit-incremental --commits 30  — All changes this sprint
2. /audit-regression                — Verify fixes from this sprint
```
**When**: End of every sprint.

### `security-deep` — Deep security review
```
1. /audit-security             — Full OWASP Top 10
2. /audit-frontend --focus auth,security  — Frontend auth/security
3. /audit-integration --flows 1,5   — Playback + WebSocket auth flows
```
**When**: After auth changes, before security review.

### `audio-deep` — Audio pipeline integrity
```
1. /audit-engine               — Full engine audit
2. /audit-integration --flows 1,3  — Playback + Enhancement flows
3. /audit-concurrency --focus 1,2  — Player + Processing pipeline
```
**When**: After DSP changes, crossfade modifications, or parallel processing updates.

## Execution

### Step 1: Print the Execution Plan

Print a table showing which audits will run:

```
## Audit Suite: <preset name>

| Step | Audit | Focus | Type |
|------|-------|-------|------|
| 1 | audit-regression | All known fixes | Lightweight |
| 2 | audit-incremental | Last 10 commits | Lightweight |
| 3 | audit-security --depth shallow | Quick check | Deep (subagents) |
```

### Step 2: Launch Audits in Parallel

Each audit is independent — they read different files and write separate reports. Launch them ALL simultaneously using the Agent tool.

**Parallelization strategy by preset**:

- **`comprehensive`** (7 audits): Launch ALL 7 as background agents in a single message. Each writes to its own report file — no conflicts.
- **`pre-release`** (3 audits): Launch all 3 in parallel.
- **`post-sprint`** (2 audits): Launch both in parallel.
- **`security-deep`** (3 audits): Launch all 3 in parallel.
- **`audio-deep`** (3 audits): Launch all 3 in parallel.

**Agent configuration for each audit**:
- `subagent_type`: `general-purpose`
- `run_in_background`: `true`

**Agent prompt template** (adapt for each audit):
```
You are running the <audit-name> audit as part of the <preset-name> suite.

CRITICAL: You MUST perform a FRESH audit by reading and analyzing the CURRENT source code.
Do NOT reuse, summarize, or reference any existing report files in docs/audits/.
Existing reports may be outdated — the code has changed since they were written.
Delete any previous report at the target path before starting.

Read the audit command file at `.claude/commands/audit-<name>.md` and follow ALL of its instructions exactly:
- Phase 1: Setup (create /tmp dirs, fetch dedup baseline)
- Phase 2: Launch dimension agents (as described in the file)
- Phase 3: Merge results into the final report
- Phase 4: Cleanup

<any --focus or --depth overrides from the preset>

Write the final report to: docs/audits/AUDIT_<TYPE>_<TODAY>.md

IMPORTANT: Follow the context management rules from `.claude/commands/_audit-common.md`.
```

**Launch example for `comprehensive`**:
Send a SINGLE message with 7 Agent tool calls, all with `run_in_background: true`. Do NOT wait for one to finish before launching the next.

### Step 3: Wait for All Agents to Complete

You will be notified as each background agent completes. As each finishes, note:
- Whether it succeeded or failed
- The report path (if written)
- The finding count (read the executive summary section)

Wait until ALL agents have completed before proceeding to Step 4.

### Step 4: Print Final Summary

After ALL audits have completed, print:

```
## Audit Suite Results: <preset name>

| # | Audit | Status | Report | Findings |
|---|-------|--------|--------|----------|
| 1 | audit-regression | DONE | docs/audits/AUDIT_REGRESSION_<TODAY>.md | 3 PASS, 1 FAIL |
| 2 | audit-incremental | DONE | docs/audits/AUDIT_INCREMENTAL_<TODAY>.md | 5 findings |
| 3 | audit-security | DONE | docs/audits/AUDIT_SECURITY_<TODAY>.md | 2 CRITICAL, 4 HIGH |

### Next Steps

For each report with NEW findings, run `/audit-publish` in a new conversation:
- `/audit-publish docs/audits/AUDIT_REGRESSION_<TODAY>.md`
- `/audit-publish docs/audits/AUDIT_INCREMENTAL_<TODAY>.md`
- `/audit-publish docs/audits/AUDIT_SECURITY_<TODAY>.md`
```

## Important Notes

- Each audit runs as an isolated background agent — it will NOT exhaust this conversation's context.
- Deep audits (engine, backend, frontend, etc.) internally launch their own sub-agents for each dimension.
- The `comprehensive` preset launches 7 audits in parallel — typically completes in ~15 min instead of ~60 min.
- Always review reports before publishing to GitHub with `/audit-publish`.
- If an audit fails, note the error — other audits continue independently since they run in parallel.
