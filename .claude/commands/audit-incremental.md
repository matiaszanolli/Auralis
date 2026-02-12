# Incremental / Delta Audit

Audit only the code that has changed in the last 10 commits, then create GitHub issues for any new findings.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`:

- **Audio Engine**: `auralis/` — Core Python audio engine
- **Backend**: `auralis-web/backend/` — FastAPI REST + WebSocket (:8765)
- **Frontend**: `auralis-web/frontend/` — React 18, TypeScript, Vite, Redux
- **Rust DSP**: `vendor/auralis-dsp/` — PyO3 module
- **Tests**: `tests/` — 850+ tests across 21 directories

## Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | The change introduces audio corruption, data loss, or exploitable vulnerability. | Removed sample count check, broken crossfade, unvalidated file path |
| **HIGH** | The change breaks existing behavior or introduces a race condition. | Missing null check, changed return type without updating callers, broken invariant |
| **MEDIUM** | The change is correct but incomplete or inconsistent. | New endpoint without validation, test not updated, migration missing |
| **LOW** | Style, naming, or minor quality issues in the changed code. | Inconsistent naming, missing type hints, dead code added |

## Step 1: Gather Changed Files

Run to get the last 10 commits' changed files:

```bash
cd /mnt/data/src/matchering && git diff HEAD~10..HEAD --name-only
```

Also run `git log --oneline -10` to understand commit messages and intent.

## Step 2: Categorize Changes

Group changed files by risk domain:

| Domain | Patterns | Risk |
|--------|----------|------|
| **Audio Core** | `auralis/core/*`, `auralis/dsp/*` | HIGH |
| **Player** | `auralis/player/*` | HIGH |
| **Audio I/O** | `auralis/io/*` | HIGH |
| **Backend Streaming** | `auralis-web/backend/audio_stream*`, `chunked_processor*` | HIGH |
| **Backend Routes** | `auralis-web/backend/routers/*` | HIGH |
| **Library/Database** | `auralis/library/*` | HIGH |
| **Analysis** | `auralis/analysis/*` | MEDIUM |
| **Optimization** | `auralis/optimization/*` | MEDIUM |
| **Backend Services** | `auralis-web/backend/services/*` | MEDIUM |
| **Rust DSP** | `vendor/auralis-dsp/*` | HIGH |
| **Frontend Components** | `auralis-web/frontend/src/components/*` | LOW-MEDIUM |
| **Frontend Hooks** | `auralis-web/frontend/src/hooks/*` | MEDIUM |
| **Frontend Store** | `auralis-web/frontend/src/store/*` | MEDIUM |
| **Tests** | `tests/*` | LOW |
| **Config/CI** | `.github/*`, `*.toml`, `*.ini`, `*.cfg` | MEDIUM |

## Step 3: Audit Each Changed File

For each changed file, read the diff and surrounding context. Check:

- [ ] **Audio invariants**: Is `len(output) == len(input)` still maintained? Is `audio.copy()` used before modification? Are dtypes preserved?
- [ ] **New bugs**: Logic errors, off-by-ones, null dereferences, unhandled exceptions?
- [ ] **Security**: File path validation weakened? New unvalidated inputs? CORS changes?
- [ ] **Concurrency**: Shared state without locks? Changed lock scope? RLock still protecting all state?
- [ ] **Contract breaks**: API endpoint changed — did the frontend update? Schema changed — did callers update?
- [ ] **Tests**: Corresponding test updates for new/changed code paths?
- [ ] **DSP correctness**: Phase coherence maintained? Spectral leakage introduced? Crossfade curves correct?

## Step 4: Cross-Layer Impact

For each changed file that crosses a layer boundary:

1. **Audio engine changed**: Does the backend still call it correctly? Does the chunked processor still work?
2. **Backend route changed**: Does the frontend API client match the new contract?
3. **Backend schema changed**: Does the frontend consume the new format correctly?
4. **WebSocket message format changed**: Are both sides in sync?
5. **Database schema changed**: Is there a migration? Do all repositories handle the new schema?
6. **Rust DSP changed**: Is the Python binding still correct? Do callers handle the new behavior?

## Deduplication (MANDATORY)

Before reporting ANY finding:
1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. If OPEN: skip. If no match: NEW.

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_INCREMENTAL_<TODAY>.md`** (use today's date).

### Report Structure
1. **Change Summary** — Files changed, commit range, key themes
2. **High-Risk Changes** — Files in audio core/player/streaming/library domains
3. **Findings** — New bugs, regressions, or gaps from the changes
4. **Cross-Layer Impact** — Contract breaks between engine/backend/frontend
5. **Missing Tests** — Changed code paths without test updates

### Per-Finding Format
```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Changed File**: `<file-path>` (commit: <hash>)
- **Status**: NEW | Existing: #NNN
- **Description**: What the change introduced or broke
- **Evidence**: Diff snippet showing the problematic change
- **Impact**: What breaks or could break
- **Suggested Fix**: What needs to change
```

## Phase 2: Publish to GitHub

For every finding with **Status: NEW**, create a GitHub issue:
- **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
- **Labels**: severity label (`critical`, `high`, `medium`, `low`) + domain label(s) (`audio-integrity`, `dsp`, `player`, `backend`, `frontend`, `library`, `concurrency`, `websocket`, `streaming`) + `bug`
- **Body**: Summary, Evidence (diff), Impact, Related Issues, Proposed Fix, Acceptance Criteria, Test Plan
- **Cross-reference** related existing issues with `gh issue comment`.
- **Print summary table** at the end.
