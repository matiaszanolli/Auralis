# Common Audit Protocol

**Do not invoke this file directly.** It is referenced by all specialized audit commands.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`:

| Layer | Path | Description |
|-------|------|-------------|
| Audio Engine | `auralis/` | Core Python audio engine (DSP, analysis, player, library, I/O) |
| Backend | `auralis-web/backend/` | FastAPI REST + WebSocket server (:8765) |
| Frontend | `auralis-web/frontend/` | React 18, TypeScript, Vite, Redux, MUI |
| Rust DSP | `vendor/auralis-dsp/` | PyO3 module (HPSS, YIN, Chroma) |
| Desktop | `desktop/` | Electron wrapper |
| Tests | `tests/` | 850+ tests across 21 directories |

## Severity Framework

All audits use this unified 4-level scale. Each audit adds domain-specific examples.

| Severity | Definition |
|----------|-----------|
| **CRITICAL** | Happening NOW in production. Causes data loss, audio corruption, or exploitable security breach. No workaround. |
| **HIGH** | Triggered under realistic usage conditions. Must fix before next release. |
| **MEDIUM** | Requires specific conditions or has workarounds. Fix within 2 sprints. |
| **LOW** | Code quality, maintainability, or minor inconsistencies. Fix opportunistically. |

## Methodology

- Be skeptical. Assume there are bugs even if the code "looks fine."
- For each claim, re-read the code path to confirm before including it.
- Prefer evidence from concrete code paths (call sites, data structures, configs) over assumptions.
- After making a finding, attempt to disprove it. Only include findings you cannot disprove.
- Pay special attention to audio integrity — sample count mismatches cause audible artifacts.
- Trace audio data through the full pipeline: load → analyze → process → stream → playback.

## Critical Invariants

```python
# Audio processing — sample count preservation
assert len(output) == len(input)              # NEVER change sample count
assert isinstance(output, np.ndarray)         # Always NumPy, never lists
assert output.dtype in [np.float32, np.float64]
output = audio.copy()                         # NEVER modify in-place
```

- **Player state**: position <= duration, queue index valid, state changes atomic (RLock)
- **Database**: thread-safe pooling (`pool_pre_ping=True`), no N+1 (`selectinload()`), all access via repositories
- **WebSocket**: chunked streaming must maintain audio continuity across 30s boundaries

## Deduplication (MANDATORY)

Before reporting ANY finding:

1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. Search for keywords from your finding in existing issue titles
3. Check existing audit reports in `docs/audits/` for prior coverage
4. If a matching issue exists:
   - **OPEN**: Note as "Existing: #NNN" and skip — do NOT re-report
   - **CLOSED**: Verify the fix is still in place. If regressed, report as "Regression of #NNN"
5. If no match: Report as NEW

## Phase 2: Publish to GitHub

After completing the audit report, for every finding with **Status: NEW** or **Regression**:

1. **Create a GitHub issue** with:
   - **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
   - **Labels**: severity label (`critical`, `high`, `medium`, `low`) + domain-specific labels (see each audit) + `bug`
   - **Body** (adapt fields to audit type):
     ```
     ## Summary
     <description>

     ## Evidence / Code Paths
     - **File**: `<path>:<line-range>`
     - **Code**: <relevant snippet>
     - **Call path**: <how execution reaches the problem>

     ## Impact
     - **Severity**: <SEVERITY>
     - **What breaks**: <failure mode>
     - **When**: <trigger conditions>
     - **Blast radius**: <scope>

     ## Related Issues
     - #NNN — <relationship>

     ## Proposed Fix
     <recommended approach>

     ## Acceptance Criteria
     - [ ] <criterion>

     ## Test Plan
     - <test description> — assert <expected>
     ```

2. **Cross-reference**: For each new issue that relates to an existing issue:
   ```
   gh issue comment <EXISTING_ISSUE> --body "Related: #<NEW_ISSUE> — <brief description>"
   ```

3. **Print a summary table** at the end:
   ```
   | Finding | Severity | Action | Issue |
   |---------|----------|--------|-------|
   | <title> | CRITICAL | CREATED | #NNN |
   | <title> | HIGH | DUPLICATE of #NNN | — |
   ```

## Domain Labels

Use these labels when creating issues: `audio-integrity`, `dsp`, `player`, `backend`, `frontend`, `library`, `security`, `concurrency`, `performance`, `websocket`, `streaming`, `fingerprint`, `deprecation`
