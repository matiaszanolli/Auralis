---
description: "Audit accumulated technical debt — stale markers, dead code, duplication, magic numbers, stub impls, doc rot, oversized files"
argument-hint: "[--focus <dimensions>] [--depth shallow|deep] [--limit <N>]"
---

# Tech-Debt Audit

Audit Auralis for accumulated technical debt: code that runs, passes tests, and ships, but quietly raises the cost of every future change. The goal is **not** to find correctness bugs (`/audit-engine`, `/audit-backend`, `/audit-frontend`, `/audit-concurrency`, `/audit-security` cover those) — it's to surface decay that has crept in since the last cleanup pass, and to enforce the project's own principles (DRY, Modular < 300 lines, No Variants, Repository pattern — see CLAUDE.md).

**Architecture**: This is an orchestrator. Each dimension runs as a Task agent (subagent_type: general-purpose, model: sonnet, max_turns: 25). Max 3 agents run concurrently.

See `.claude/commands/_audit-common.md` for project layout, methodology, deduplication, context-management rules, and the base finding format. See `.claude/commands/_audit-severity.md` for the unified severity scale.

## Parameters (from $ARGUMENTS)

- `--focus <dimensions>`: Comma-separated dimension numbers or names (e.g., `1,3,5` or `markers,duplication,complexity`). Default: all 10.
- `--depth shallow|deep`: `shallow` = surface counts and worst offenders; `deep` = file-by-file with concrete fix proposals. Default: `deep`.
- `--limit <N>`: Stop after N findings per dimension (useful for time-boxed audits). Default: unlimited.

## Scope

Tech debt across the whole repo:

- **Python engine**: `auralis/`
- **Python backend**: `auralis-web/backend/`
- **Frontend**: `auralis-web/frontend/src/`
- **Rust DSP**: `vendor/auralis-dsp/`
- **Tests**: `tests/`, `auralis-web/frontend/src/test/` and co-located specs
- **Docs & skills**: `docs/`, `CLAUDE.md`, `README.md`, `auralis-web/backend/WEBSOCKET_API.md`, `.claude/commands/audit-*.md`

Out of scope: correctness/security bugs (route them to the matching audit), and `~/.auralis/` runtime DB/cache.

## Extra Per-Finding Fields

In addition to the base format in `_audit-common.md`, every tech-debt finding adds:

- **Dimension**: Stale Markers | Dead Code | Logic Duplication | Magic Numbers | Stub Implementations | Test Hygiene | Stale Documentation | Backwards-Compat Cruft | File/Function Complexity | Audit-Finding Rot
- **Age** (when applicable): commit hash + date the debt was introduced (`git blame` / `git log -L`)
- **Effort**: trivial (≤30 min) | small (≤2 h) | medium (≤1 day) | large (>1 day — decompose first)

## Severity Guidance for Tech Debt

Tech-debt findings are almost always **LOW** under the standard scale (`_audit-severity.md`). Promote only when there's amplification:

| Promotion Trigger | Floor |
|-------------------|-------|
| Duplicated logic with divergent bug-fix history (one copy fixed, the other still carries the bug) | MEDIUM |
| `raise NotImplementedError` / `pass`-only / `...` stub reachable from a shipped route or the player pipeline | MEDIUM |
| `@pytest.mark.skip` / `it.skip` guarding a regression test for a closed CRITICAL/HIGH issue | MEDIUM |
| Stale doc/audit baseline that has misled an audit in the last 90 days | MEDIUM |
| Duplicated DSP scaffolding where one copy drops `audio.copy()` or a sample-count guard the other has | HIGH (audio integrity — see `_audit-severity.md`) |
| Magic constant that would silently truncate/overflow audio (sample rate, chunk size, buffer length) under documented use | HIGH |

Default every tech-debt finding to LOW unless one of the above fires. Do **not** invent correctness findings here — if you find a real bug, note it as `Related` and point the user at the owning audit.

## Phase 1: Setup

1. Parse `$ARGUMENTS` for `--focus`, `--depth`, `--limit`.
2. `mkdir -p /tmp/audit/tech-debt`
3. Fetch dedup baseline (see `_audit-common.md` "Deduplication"):
   ```bash
   gh issue list --limit 200 --json number,title,state,labels > /tmp/audit/tech-debt/issues.json
   gh issue list --limit 500 --state all --label tech-debt --json number,title,state > /tmp/audit/tech-debt/issues_tech_debt.json
   ```
4. Scan `docs/audits/` for prior tech-debt reports (`AUDIT_TECH_DEBT_*.md`).
5. Run the path-reference gate so Dim 7 / Dim 10 can treat its output as pre-confirmed findings:
   ```bash
   .claude/commands/_audit-validate.sh || true   # STALE lines → auto-eligible Dim 7/10 findings (effort: trivial)
   ```
6. Snapshot current totals as a baseline (so the report can show direction and the next run can diff):
   ```bash
   {
     echo "TODO/FIXME/HACK/XXX (py):   $(grep -RInE '(TODO|FIXME|HACK|XXX)\b' auralis auralis-web/backend --include='*.py' | wc -l)"
     echo "TODO/FIXME/HACK/XXX (ts):   $(grep -RInE '(TODO|FIXME|HACK|XXX)\b' auralis-web/frontend/src --include='*.ts' --include='*.tsx' | wc -l)"
     echo "NotImplementedError:        $(grep -RInE 'NotImplementedError' auralis auralis-web/backend --include='*.py' | wc -l)"
     echo "type: ignore (py):          $(grep -RIn 'type: ignore' auralis auralis-web/backend --include='*.py' | wc -l)"
     echo "@ts-ignore/@ts-expect-error: $(grep -RInE '@ts-(ignore|expect-error)' auralis-web/frontend/src | wc -l)"
     echo "': any' / 'as any' (ts):     $(grep -RInE ':\s*any\b|as any|<any>' auralis-web/frontend/src --include='*.ts' --include='*.tsx' | wc -l)"
     echo "skipped tests (py):         $(grep -RInE '@pytest\.mark\.(skip|skipif|xfail)' tests | wc -l)"
     echo "skipped tests (ts):         $(grep -RInE '\b(it|test|describe)\.(skip|todo)\b' auralis-web/frontend/src | wc -l)"
     echo "py files >300 LOC:          $(find auralis auralis-web/backend -name '*.py' -exec wc -l {} + | awk '$1>300 && $2!="total"' | wc -l)"
     echo "ts/tsx files >300 LOC:      $(find auralis-web/frontend/src \( -name '*.ts' -o -name '*.tsx' \) -exec wc -l {} + | awk '$1>300 && $2!="total"' | wc -l)"
     echo "allow(dead_code) (rust):    $(grep -RInE 'allow\(dead_code\)' vendor/auralis-dsp/src 2>/dev/null | wc -l)"
   } > /tmp/audit/tech-debt/baseline.txt
   ```

## Phase 2: Launch Dimension Agents

Launch one Task agent per selected dimension (max 3 concurrent). Each agent writes its output to `/tmp/audit/tech-debt/dim_<N>.md`.

Every agent prompt MUST include:
- The project root is `/mnt/data/src/matchering`.
- The `--depth` value and the `--limit` value (if set).
- The dedup files: `/tmp/audit/tech-debt/issues.json` and `/tmp/audit/tech-debt/issues_tech_debt.json` (apply the dedup protocol from `_audit-common.md`).
- The baseline file `/tmp/audit/tech-debt/baseline.txt`.
- The context-management rules from `_audit-common.md` (max 1500 lines/Read, grep-before-read, incremental writes).
- The per-finding format below (base format + the three extra fields), and the LOW-by-default severity rule with the promotion table above.
- A reminder: this is a **debt** audit — propose a concrete deletion/consolidation/extraction for every finding; do not re-derive correctness.

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: LOW (default) | MEDIUM | HIGH (only per the promotion table)
- **Dimension**: <one of the 10 names>
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Age**: <commit> <date> (git blame; omit if not determinable)
- **Effort**: trivial | small | medium | large
- **Description**: What the debt is and why it raises change-cost
- **Evidence**: Code snippet or exact path demonstrating it
- **Impact**: What it slows down / what bug class it invites
- **Siblings**: Other locations with the same pattern (see `_audit-common.md` Sibling Detection)
- **Related**: Links to related findings / issues / owning audit
- **Suggested Fix**: Concrete deletion, consolidation site, or split axis (1-3 sentences)
```

### Dimension 1: Stale Markers (TODO / FIXME / HACK / XXX)
**Entry points**: `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/src/`
**Checklist**:
- Each marker: how old? (`git blame` → commit + date — anything older than 6 months gets reported). Skip markers from the last 30 days unless they reference a closed issue.
- Does the marker reference an issue number (`#NNNN`)? Cross-check against the dedup files — a marker citing a CLOSED issue has outlived its driver (delete or reopen).
- `# TODO: implement` / `// TODO` markers in code paths now reachable from a shipped FastAPI route (`auralis-web/backend/routers/`) or the player pipeline (`auralis/player/`).
- `HACK` / `XXX` around DSP math (`auralis/dsp/`, `auralis/core/`) — note but route correctness concerns to `/audit-engine` as `Related`.
**Output**: `/tmp/audit/tech-debt/dim_1.md`

### Dimension 2: Dead Code & Unused Surface
**Entry points**: `auralis/` (largest: `auralis/analysis/`), `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/src/`
**Checklist**:
- Python: unused functions / classes / imports (`ruff check --select F401,F811` or `vulture` if installed; otherwise grep the symbol for non-definition call sites). Private module functions no other module imports.
- Stale `# type: ignore` comments whose underlying error no longer exists (`mypy` no longer reports there).
- Frontend: unused exports / dead components / dead hooks (`ts-prune` or `eslint` `no-unused-vars` if configured; otherwise grep the export name across `src/`).
- Re-exports through `__init__.py` / `index.ts` that no consumer uses.
- Rust DSP: every `#[allow(dead_code)]` — is the item actually called from the PyO3 boundary now, or still dead?
- **Don't flag**: `if TYPE_CHECKING:` imports, `pytest` fixtures, FastAPI dependency-injection callables, public API of `auralis/` that the desktop/CLI surface consumes, PyO3 `#[pyfunction]`/`#[pymethods]` exposed to Python.
**Output**: `/tmp/audit/tech-debt/dim_2.md`

### Dimension 3: Logic Duplication
**Entry points**: any subsystem with N>1 similar files — the Sibling Detection groups in `_audit-common.md` are the prime targets: `auralis/library/repositories/` (12 repos), `auralis-web/backend/routers/` (18 routers), `auralis/dsp/`, `auralis-web/frontend/src/hooks/`.
**Checklist**:
- Repeated query scaffolding across `auralis/library/repositories/` (session open → query → `selectinload` → map) — should it funnel through a base-repository helper?
- Repeated request-validation / error-`HTTPException` / response-shaping boilerplate across `auralis-web/backend/routers/` (cross-reference `/sync-contracts` for the schema side).
- Repeated DSP pre/post-amble in `auralis/dsp/` and `auralis/core/` (copy-before-modify, normalize, clip-to-[-1,1]) — propose a shared utility, but FLAG (do not silently merge) any copy that omits a guard a sibling has.
- Repeated `useEffect` cleanup / WebSocket subscribe-unsubscribe patterns across `auralis-web/frontend/src/hooks/`.
- **Cross-reference the user policy** (CLAUDE.md): "Always prioritize improving existing code rather than duplicating logic." Every duplication finding must name a specific consolidation site.
**Output**: `/tmp/audit/tech-debt/dim_3.md`

### Dimension 4: Magic Numbers & Hardcoded Constants
**Entry points**: `auralis/core/`, `auralis/dsp/`, `auralis-web/backend/`, `auralis-web/frontend/src/`
**Checklist**:
- Bare audio constants inline (sample rates, FFT/window sizes, hop lengths, crossfade durations, chunk sizes/intervals) that should live in `auralis/core/config.py`. Note: chunk boundaries already have a single source of truth in `auralis-web/backend/core/chunk_boundaries.py` (`CHUNK_INTERVAL`) — flag any literal that bypasses it.
- Backend timeouts / TTLs / queue sizes / frame-byte budgets hardcoded inline (should be named module constants).
- Frontend: hardcoded hex/rgb colors that bypass `auralis-web/frontend/src/design-system/` tokens (overlaps `/audit-frontend` Dim 5 — report under whichever you run; dedup at merge).
- **Don't flag**: protocol/spec magic — WAV/audio-format header bytes, PCM bit depths (16/24), standard sample rates used as documented enum values, HTTP status codes. These are spec, not arbitrary tunables.
**Output**: `/tmp/audit/tech-debt/dim_4.md`

### Dimension 5: Stub & Placeholder Implementations
**Entry points**: `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`
**Checklist**:
- Every `raise NotImplementedError` / `pass`-only body / bare `...` ellipsis body / `return None # TODO` — is the call site reachable from a shipped route, the player pipeline, or a UI action? (Reachable → promote to MEDIUM per the table.)
- Functions returning empty `[]` / `{}` / `0.0` with a "stub" / "placeholder" / "real impl later" comment.
- Routes returning hardcoded/mock data instead of real engine/DB output.
- Frontend components rendering placeholder/"Coming soon" content wired into a shipped route.
- Abstract methods or Protocol stubs with no concrete implementation that any code path needs.
**Output**: `/tmp/audit/tech-debt/dim_5.md`

### Dimension 6: Test Hygiene
**Entry points**: `tests/`, `auralis-web/frontend/src/test/` and co-located `*.test.ts(x)` / `*_test.py` / `test_*.py`
**Checklist**:
- Every `@pytest.mark.skip` / `skipif` / `xfail` and frontend `it.skip` / `describe.skip` / `it.todo`: is there a referenced issue, and is it still open? A skip guarding a closed CRITICAL/HIGH regression test → MEDIUM.
- Smoke-only assertions (`assert result is not None` / `expect(x).toBeTruthy()` and nothing else) where the returned value should be asserted.
- Commented-out assertions inside otherwise-passing tests.
- Tests that print rather than assert (`print(...)` / `console.log(...)` with no follow-up assertion).
- Over-mocking: `vi.*` / `unittest.mock` mocks so broad the test no longer exercises real behavior (cross-reference the global auto-mocks in `auralis-web/frontend/src/test/`).
- Cross-reference "must not regress" baselines named in other `audit-*.md` skills — confirm each named regression test still exists and is not skipped.
- Note the known frontend vitest baseline (pre-existing failures) — do NOT report individual pre-existing failures as debt; report only skip/xfail rot and assertion-quality issues.
**Output**: `/tmp/audit/tech-debt/dim_6.md`

### Dimension 7: Stale Documentation & Comments
**Entry points**: `docs/`, `CLAUDE.md`, `README.md`, `auralis-web/backend/WEBSOCKET_API.md`, `docs/development/TESTING_GUIDELINES.md`, `.claude/commands/audit-*.md`, doc comments / docstrings in source
**Checklist**:
- Start from the `_audit-validate.sh` output captured in Phase 1 — every STALE line is a trivial-effort Dim 7 finding (backticked path that no longer resolves).
- **Version drift**: `auralis/version.py` is the single source of truth. Flag any other file (notably `pyproject.toml`, `README.md`, docs) quoting a different version string.
- CLAUDE.md "Codebase Map" counts that have drifted (e.g. "18 routers", "12 repos", "92 files") — recompute and flag mismatches.
- Docstrings / comments referencing renamed or deleted symbols (grep the named symbol; if it has no definition, the doc is stale).
- README / docs command examples that no longer work (changed flags, moved entry points; cross-check against the verified facts — e.g. entry point is `launch-auralis-web.py`).
- `auralis-web/backend/WEBSOCKET_API.md` message-shape descriptions that no longer match `auralis-web/backend/schemas.py` or the emitted payloads (cross-reference `/sync-contracts`).
- **Convention**: backticked path refs in `audit-*.md` claim "this path exists now". Forward-looking or deleted refs must NOT use backticks (the validate gate enforces this).
**Output**: `/tmp/audit/tech-debt/dim_7.md`

### Dimension 8: Backwards-Compat Cruft & "No Variants" Violations
**Entry points**: `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`
**Checklist**:
- **No-Variants principle** (CLAUDE.md): flag `*_v2`, `*Enhanced`, `*Advanced`, `*New`, `*Old`, `*Legacy` duplicate modules/classes/components that should have been refactored in place. (Distinguish genuine domain names like `EnhancedAudioPlayer` — the real player — from copy-of-X variants; verify by checking whether both the base and the variant are live.)
- `_unused` / `_`-renamed parameters or fields that survived a refactor — CLAUDE.md says delete, don't rename to `_var`.
- `# removed:` / `// removed:` breadcrumb comments — delete completely, no breadcrumbs.
- `@deprecated` / `warnings.warn(DeprecationWarning)` items with no remaining consumers — delete instead of deprecate (Auralis is desktop-only with no external API consumers; see CLAUDE.md / memory).
- Re-exports of deleted/renamed symbols kept "for compatibility" — rot, since there are no external consumers.
- Compatibility shims for old DB schema versions already migrated past (cross-reference `auralis/library/` migrations; route correctness to `/audit-engine`).
**Output**: `/tmp/audit/tech-debt/dim_8.md`

### Dimension 9: File / Function / Module Complexity
**Entry points**: `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`
**Checklist**:
- The project rule is **< 300 lines per module** (CLAUDE.md Principles; frontend components explicitly < 300). List offenders:
  ```bash
  find auralis auralis-web/backend -name '*.py' -exec wc -l {} + | awk '$1>300 && $2!="total"' | sort -rn | head -40
  find auralis-web/frontend/src \( -name '*.ts' -o -name '*.tsx' \) -exec wc -l {} + | awk '$1>300 && $2!="total"' | sort -rn | head -40
  ```
  Do NOT hardcode the offender list in this skill — re-run each audit (membership drifts). For each oversized file propose a split **axis** (by responsibility / submodule), not by line count alone.
- Functions / methods > 100 LOC — propose extraction.
- Deeply nested conditionals (depth > 4) — often a strategy/lookup-table or early-return refactor.
- React components with too many `useState`/`useEffect` hooks (a sign the component is doing several jobs) — propose a custom-hook extraction.
- `__init__.py` / `index.ts` with > 20 re-exports (the module is doing two jobs).
**Output**: `/tmp/audit/tech-debt/dim_9.md`

### Dimension 10: Audit-Finding Rot
**Entry points**: `.claude/commands/audit-*.md`, `docs/audits/`, `.claude/issues/`
**Checklist**:
- Run `.claude/commands/_audit-validate.sh` (done in Phase 1) — any STALE refs it reports are auto-eligible Dim 10 findings (effort: trivial). For symbol-anchor refs it can't verify (e.g. `module.py::function_name`), spot-check the symbol still exists.
- "Existing: #NNN" callouts in skill files where the issue is now CLOSED — should the prose reference the closed-state baseline differently?
- Audit reports in `docs/audits/` older than 90 days whose CRITICAL/HIGH findings are not all triaged (open or closed) on GitHub.
- Skill files that reference dimension counts ("all 9 dimensions") that no longer match the current list — including THIS file (keep "all 10" honest).
- **Do NOT** flag `.claude/issues/<N>/ISSUE.md` state drift — those are immutable snapshots of the issue as filed; GitHub is authoritative for current state.
**Output**: `/tmp/audit/tech-debt/dim_10.md`

## Phase 3: Merge

1. Read all `/tmp/audit/tech-debt/dim_*.md` files.
2. Combine into `docs/audits/AUDIT_TECH_DEBT_<TODAY>.md` (YYYY-MM-DD) with structure:
   - **Executive Summary** — total findings by severity + delta vs `/tmp/audit/tech-debt/baseline.txt`.
   - **Baseline Snapshot** — the counts captured in Phase 1, so the next audit can diff direction.
   - **Top 10 Quick Wins** — trivial/small effort with immediate readability or build-time payoff.
   - **Top 5 Medium Investments** — file/function splits, duplication consolidations.
   - **Findings** — grouped by severity (HIGH → MEDIUM → LOW), then by dimension.
   - **Deferred** — findings gated on in-progress work; note the gating item.
3. Remove cross-dimension duplicates (e.g. a TODO inside a dead function reports under Dim 2, not also Dim 1; a hardcoded color reports under Dim 4 or `/audit-frontend` Dim 5, not both).
4. Do NOT create GitHub issues during the audit.

## Phase 4: Cleanup

1. `rm -rf /tmp/audit/tech-debt`
2. Inform the user the report is ready.
3. Suggest: `/audit-publish docs/audits/AUDIT_TECH_DEBT_<TODAY>.md`

## Labels

This audit publishes findings under the `tech-debt` label (registered in `_audit-common.md` Domain Labels), in addition to the standard severity label and the relevant domain label (`audio-integrity`, `backend`, `frontend`, `library`, `dsp`, …) and a type label (usually `maintenance`). `/audit-publish` applies them when it processes the report.
