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

See `.claude/commands/_audit-severity.md` for the unified severity scale (CRITICAL / HIGH / MEDIUM / LOW) and classification rules.

## Context Management Rules

- **Max 1500 lines per Read** — use `offset` and `limit` to paginate files larger than 1500 lines.
- **Grep before Read** — search for the specific pattern first, then read only relevant sections.
- **Incremental writes** — append findings to the report as you go; do not hold everything in memory.
- **One dimension at a time** — complete and write up one dimension before starting the next.

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

## Report Finalization

1. Save your report to: `docs/audits/AUDIT_<TYPE>_<TODAY>.md` (YYYY-MM-DD format)
2. Do NOT create GitHub issues directly during the audit
3. Inform the user the report is ready and suggest:
   ```
   /audit-publish docs/audits/AUDIT_<TYPE>_<TODAY>.md
   ```

## Domain Labels

Use these labels when creating issues: `audio-integrity`, `dsp`, `player`, `backend`, `frontend`, `library`, `security`, `concurrency`, `performance`, `websocket`, `streaming`, `fingerprint`, `deprecation`
