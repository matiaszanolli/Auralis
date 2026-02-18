# Incremental / Delta Audit

Audit only the code that has changed in a recent commit range, then create GitHub issues for any new findings.

**Shared protocol**: Read `.claude/commands/_audit-common.md` first for project layout, severity framework, methodology, deduplication rules, and GitHub issue template.

## Arguments

This command accepts an optional commit range argument: `$ARGUMENTS`

- If provided, use it as the git range (e.g., `v1.1.0..HEAD`, `HEAD~20..HEAD`, `abc123..def456`)
- If empty or not provided, default to `HEAD~10..HEAD`

## Severity Examples

| Severity | Delta-Specific Examples |
|----------|------------------------|
| **CRITICAL** | The change introduces audio corruption, data loss, or exploitable vulnerability |
| **HIGH** | The change breaks existing behavior or introduces a race condition |
| **MEDIUM** | The change is correct but incomplete or inconsistent with existing patterns |
| **LOW** | Style, naming, or minor quality issues in the changed code |

## Step 1: Gather Changed Files

```bash
cd /mnt/data/src/matchering
RANGE="${ARGUMENTS:-HEAD~10..HEAD}"
git log --oneline $RANGE
git diff $RANGE --name-only
```

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

Use labels: severity label + domain labels (`audio-integrity`, `dsp`, `player`, `backend`, `frontend`, `library`, `concurrency`, `websocket`, `streaming`) + `bug`
