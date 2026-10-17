---
description: "Re-sync every audit skill against the code that landed since the last sync — closed-issue sweep, delta read, premise re-measure"
argument-hint: "[--base <rev>]"
---

# Audit-Skill Sync

Audit skills describe the code: file and router counts, test names, schema versions, known-open issues. Fix commits change the code without touching those files, so the skills go stale (#5492 and #5044 are the typical shape: a deleted module or repository survived in several skills for weeks). Most of the rot is closed issues still described as open. This skill brings every `.claude/commands/*.md` (the `audit-*`, `verify-*`, `sync-contracts`, `trace-flow`, `gen-test` and `fix-issue` commands), the shared `_audit-*` files and the `.claude/agents/*.md` specialists back in line with HEAD. It does not audit the code and does not fix it: real bugs that surface are reported to the user, not fixed.

`_audit-validate.sh` catches a stale *path*; it cannot catch a stale *claim*. This skill is the claim-level counterpart.

Files in `.claude/commands/audit-sync/`:
- `.claude/commands/audit-sync/prep.sh`: the deterministic preparation step.
- `brief.tmpl`: the instructions every agent reads.
- `groups.txt`: which agent owns which commands, and the path prefixes that feed its weight.
- `BASELINE`: the commit the last sync matched.

## Phase 1: Prep

```bash
SCRATCH=<session scratchpad>/audit-sync
.claude/commands/audit-sync/prep.sh "$SCRATCH"            # base = BASELINE; override with --base <rev>
```

The script writes the following into `$SCRATCH`:
- *BRIEF.md*
- *open.txt*
- *closed_since.tsv*
- *cited_closed_recent_map.txt*
- *weights.tsv*
- *changed.txt*
- an empty *proposals.md*

It also prints each group's weight: the changed files under the group's path prefixes, and the cited issues closed since the base. It exits non-zero if `groups.txt` misses a command or lists one twice. A newly added command must go into a group first.

Look at the printed weights. If one group carries well over ~2× the median of either number, split it in `groups.txt` before fanning out. Two weights are inflated by churn, not code: `regression` (every `tests/` edit) and `debt` (every `docs/` edit). Discount those two before splitting. `engine` is the group most likely to need a split (`auralis/` is the largest tree), e.g. `engine` into `core+dsp` and `analysis+library+player`.

`BASELINE` was seeded with the last commit that touched `.claude/commands`, not a verified sync point, so expect the first sync to find more than later ones.

## Phase 2: Fan out

Launch one background `general-purpose` agent per `groups.txt` line, all in a single message. Each prompt contains:
- an instruction to read `$SCRATCH/BRIEF.md` first and follow it exactly;
- the exact files the agent owns (`.claude/commands/<name>.md` for each command on its line);
- the path prefixes from its `groups.txt` line, as the main delta paths;
- any hot spots: issues from `cited_closed_recent_map.txt`, or a recent refactor in the area (`git log --oneline <base>..HEAD --grep '^refactor\|^fix'`).

The `meta` group also owns the following:
- `_audit-common.md`, `_audit-severity.md`, `_audit-validate.sh` and `_audit-validate-baseline.txt`;
- the `.claude/agents/*.md` specialists (`backend-specialist`, `dsp-specialist`, `frontend-specialist`, `library-specialist`). Their layout facts must point at `CLAUDE.md` and `docs/architecture` instead of hand-typed trees wherever possible, and `scripts/check_doc_counts.py` already warns on their repository counts;
- the domain→audit routing table in `audit-search.md`, which is the only ownership map this repo has. A new top-level package or a split module needs a row there.

Agents must not start sub-agents: a nested agent's completion notice never reaches its parent (see `/audit-suite`). Because no agent here spawns children, all groups can launch at once; the 20-concurrent-subagent limit only bites for the nested audits.

## Phase 3: Collect

As each report arrives:
1. Append its "proposed edits to files I don't own", code gaps and fixed-but-open issues to `$SCRATCH/proposals.md`. Keep a heading per group.
2. Once that agent is finished, fold any proposal aimed at another agent's file into that file yourself. Never edit a file whose owning agent is still running. Check each claim against the code before you write it: an agent's proposal is a lead, not a fact.
3. Run `git log --oneline -3` and `git status --short`. Background agents have committed and pushed the whole dirty tree unprompted before (see *audit-agents-unauthorized-commit-hazard*), and the brief forbids it but cannot enforce it. If one did, stop and tell the user. Do not force-push.

A group that goes quiet with its files edited but no report may have stopped after its last edit; nudge it with `SendMessage` to send the report.

## Phase 4: Verify

```bash
bash .claude/commands/_audit-validate.sh 2>&1 | grep -E 'FAIL|STALE|OK:'
git diff --stat -- .claude
```

The validator's `Doc structural counts` section is warn-only, but read it: it is the cheapest check on the counts the agents just re-measured.

Skill-reading checks: rerun any whose matched text was touched.

| Check | Reads | Run |
|---|---|---|
| `check_doc_counts.py --check-docs` (warn-only, already run by the validator) | the "~N test functions (M files)" line in `CLAUDE.md` and `_audit-common.md`; every "N repositories" in `.claude/agents/*.md` and `.claude/commands/*.md` | `python3 scripts/check_doc_counts.py --check-docs` |
| `check_optimization_importers.py` (also a step in `path-references.yml`) | the `auralis/optimization/` row in `_audit-common.md` | `python3 scripts/check_optimization_importers.py` |
| `test_optimization_is_live_5142.py` | the same row, dynamically | `python -m pytest -q tests/test_optimization_is_live_5142.py` |

To re-derive the list: `git grep -n '\.claude/commands' -- '*.py' '*.ts' '*.tsx' '*.yml' ':!.claude'`, keeping the non-comment hits.

## Phase 5: Close

1. Write the HEAD that prep reported (`<short-hash> <YYYY-MM-DD>`) into `.claude/commands/audit-sync/BASELINE`. That is the commit the agents synced against, not a later HEAD.
2. Report to the user:
   - one line per file on what was wrong and what changed;
   - **real code gaps or bugs to file**, after checking each one yourself;
   - **issues fixed in code but still open**, with their fixing commits. A `Fix #A, #B` subject auto-closes only `#A`.
3. Commit only when the user asks: `docs(audit): re-sync audit skills against <base>..<head>`. Stage only `.claude/` paths: the tree usually carries unrelated WIP (`.codebase-memory/`, `activate.sh`).
