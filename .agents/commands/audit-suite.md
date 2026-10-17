---
description: "Run a preset audit workflow (pre-release, audio-deep, security-deep, etc.) — executes a sequence of audits"
argument-hint: "<preset-name>"
---

# Audit Suite — Preset Workflows

Run a predefined sequence of audits. This command **actually executes** each audit in the preset by launching one Agent-tool subagent per audit.

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
8. /audit-tech-debt           — Accumulated debt (markers, dead code, duplication, complexity)
```
**When**: Monthly or after major architecture changes.

### `tech-debt-deep` — Surface accumulated debt
```
1. /audit-tech-debt                  — All 10 debt dimensions
2. /audit-incremental --commits 30   — New debt introduced this sprint
```
**When**: After a milestone closes, before opening the next.

### `post-sprint` — End-of-sprint verification
```
1. /audit-incremental --commits 30  — All changes this sprint
2. /audit-regression                — Verify fixes from this sprint
```
**When**: End of every sprint.

### `security-deep` — Deep security review
```
1. /audit-security             — Full OWASP Top 10
2. /audit-frontend --focus 3,6       — WebSocket hooks + API client (the frontend audit has no auth/security dimension)
3. /audit-integration --flows 1,5   — Playback + WebSocket auth flows
```
**When**: After auth changes, before security review.

### `audio-deep` — Audio pipeline integrity
```
1. /audit-engine               — Full engine audit
2. /audit-integration --flows 1,3  — Playback + Enhancement flows
3. /audit-concurrency --focus 1,2  — Player + Processing pipeline
```
**When**: After DSP changes, chunk-seam or chunked-mastering updates, or changes to `auralis/optimization/` (live engine code since #5142).

### `streaming-deep` — Streaming, seek, and cache correctness
```
1. /audit-backend --focus 2,3,10,11  — WebSocket + chunking + caching + seek
2. /audit-integration --flows 1,5,8  — Playback + WebSocket lifecycle + Seek & Rebuffer
3. /audit-concurrency --focus 3      — Backend streaming races
```
**When**: After changes to the stream_* modules, the chunk or thumbnail caches, `seekable_source.py`, or the look-ahead/buffer path. These four surfaces share state and their bugs present identically to the user (wrong or missing audio), so auditing one without the others usually misattributes the cause.

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

Each audit is independent — they read different files and write separate reports. Launch them in parallel using the Agent tool, subject to the batching rule below.

**Parallelization strategy by preset**:

- **`comprehensive`** (8 audits): Launch in **two batches of 4**, not all 8 at once. Each deep audit spawns its own dimension agents; 8 simultaneous orchestrators saturated the concurrent-subagent limit on 2026-07-25, and deprecation and concurrency had every dimension launch rejected and ran inline with coverage gaps. Batch 1: engine, backend, frontend, integration. Batch 2: security, concurrency, deprecation, tech-debt.
- **`tech-debt-deep`** (2 audits): Launch both in parallel.
- **`streaming-deep`** (3 audits): Launch all 3 in parallel.
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
Send one message with the 4 batch-1 Agent tool calls, all with `run_in_background: true`. Launch batch 2 the same way as soon as batch 1 has completed.

### Step 3: Wait for All Agents to Complete

You will be notified as each background agent completes. As each finishes, note:
- Whether it succeeded or failed
- The report path (if written)
- The finding count (read the executive summary section)

Wait until ALL agents have completed before proceeding to Step 4. An orchestrator audit can stall after launching its dimension agents without merging them; if one goes quiet with its dimension files written, nudge it with SendMessage to run its Merge phase.

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
- The `comprehensive` preset runs 8 audits in two parallel batches of 4 — much faster than sequential without exhausting the subagent limit.
- Always review reports before publishing to GitHub with `/audit-publish`.
- If an audit fails, note the error — other audits continue independently since they run in parallel.
