---
description: "Shared audit protocol — project layout, methodology, dedup, finding format. Referenced by all audit skills."
---

# Common Audit Protocol — Auralis

**Do not invoke this file directly.** It is referenced by all specialized audit commands.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`.

```
Audio Engine:        auralis/                                Core Python audio engine
Core Pipeline:       auralis/core/                           hybrid_processor.py, simple_mastering.py, processing/, config/, recording_type_detector.py
DSP:                 auralis/dsp/                            stages.py (pipeline main()), basic.py, advanced_dynamics.py, eq/ (psychoacoustic_eq), realtime_adaptive_eq/ (realtime_eq), dynamics/, utils/
Player:              auralis/player/                         enhanced_audio_player.py, gapless_playback_engine.py, queue_controller.py, realtime_processor.py
Library:             auralis/library/                        manager.py, scanner/ (package), models/ (ORM package), migration_manager.py
Repositories:        auralis/library/repositories/           14 repos + base.py (BaseRepository) + factory.py (RepositoryFactory): track, album, artist, playlist, genre, stats, fingerprint, fingerprint_scheduler, fingerprint_stats, queue, queue_history, queue_template, settings, similarity_graph
Analysis:            auralis/analysis/                       56 files; fingerprint/ (25D), ml/, quality/, quality_assessors/
Audio I/O:           auralis/io/                             unified_loader.py, results.py (pcm16/pcm24)
Parallel:            auralis/optimization/                   parallel_processor.py
Services:            auralis/services/                       fingerprint, artwork background services
Learning:            auralis/learning/                       preference engine, reference analysis
Utils:               auralis/utils/                          logging, helpers, preview_creator

Backend:             auralis-web/backend/                    FastAPI :8765
Backend Routers:     auralis-web/backend/routers/            19 route handlers (24 .py files incl. dependencies/errors/serializers/pagination helpers)
Backend Streaming:   auralis-web/backend/core/               chunked_processor.py, audio_stream_controller.py, processing_engine.py
Backend Schemas:     auralis-web/backend/schemas.py
Backend Services:    auralis-web/backend/services/
Backend Config:      auralis-web/backend/config/             startup.py (lifespan); LibraryAutoScanner now in services/library_auto_scanner.py
Backend Core:        auralis-web/backend/core/

Frontend:            auralis-web/frontend/src/               React 18 + TS + Vite + Redux + MUI
Frontend Components: auralis-web/frontend/src/components/
Frontend Hooks:      auralis-web/frontend/src/hooks/         player, library, enhancement, websocket, api, app, audio, fingerprint, shared
Frontend Store:      auralis-web/frontend/src/store/         Redux slices
Frontend Design:     auralis-web/frontend/src/design-system/ Design tokens (single source of truth)
Frontend Services:   auralis-web/frontend/src/services/      API clients
Frontend Test Utils: auralis-web/frontend/src/test/

Rust DSP:            vendor/auralis-dsp/                     PyO3 module (HPSS, YIN, Chroma)
Desktop:             desktop/                                Electron wrapper
Tests:               tests/                                  ~5,000 test functions (410 files) across 17 dirs
Audit Reports:       docs/audits/                            Generated audit reports
Local Issue Cache:   .claude/issues/                         Issue snapshots (per audit-publish / fix-issue)
Specialist Agents:   .claude/agents/                         dsp, backend, frontend, library specialists
```

## Severity Framework

See `_audit-severity.md` for the unified severity scale (CRITICAL / HIGH / MEDIUM / LOW), special-rule minimum-severity table, and decision tree.

## Methodology

- Be skeptical. Assume there are bugs even if the code "looks fine."
- For each claim, re-read the code path to confirm before including it.
- Prefer evidence from concrete code paths (call sites, data structures, configs) over assumptions.
- After making a finding, attempt to disprove it. Only include findings you cannot disprove.
- Pay special attention to audio integrity — sample-count mismatches cause audible artifacts.
- Trace audio data through the full pipeline: load → analyze → process → stream → playback.

## Audio/Python Context Rules

- **NumPy ownership**: Always check whether a function returns a view or a copy. `arr[:]` is a view; `arr.copy()` is a copy.
- **dtype propagation**: Trace dtype through every stage. A silent `float64` cast can mask a downstream bug.
- **GIL across PyO3**: Rust DSP must release the GIL during long compute or it serializes Python callers.
- **Lock ordering**: Player RLock → Library Session is the only safe order. Reverse it and you deadlock.
- **Async vs threads**: FastAPI handlers are `async def`; the DSP/player run on threads. `await` on a sync method is a bug.
- **WebSocket lifetime**: Connections survive backend reloads in `--dev` mode; treat reconnect as the common case.

## Context Management Rules

- **Max 1500 lines per Read** — use `offset` and `limit` to paginate larger files.
- **Grep before Read** — search for the specific pattern first, then read only relevant sections.
- **Incremental writes** — append findings to the report as you go; do not hold everything in memory.
- **One dimension at a time** — complete and write up one dimension before starting the next.

## Path-Reference Convention

Backticked file/dir paths in any `audit-*.md` skill (or this file) **must resolve against the live repository tree**. The validate gate at `.claude/commands/_audit-validate.sh` enforces this and is the structural fix for stale-path drift after refactors.

- Backticks = "this path exists right now". The gate fails the audit if it doesn't.
- Forward-looking refs (a file that doesn't yet exist) or backward-looking refs (a file that was deleted) **must not** use backticks — write them as plain text or italics.
- Trailing `:NN` or `:NN-NN` line ranges are stripped before existence check (line numbers may drift; the file must still exist).
- Run `.claude/commands/_audit-validate.sh` before committing edits to any audit skill.

## Specialist Agents

For complex investigations, the orchestrator audits (`audit-engine`, `audit-backend`, `audit-frontend`, `audit-integration`) may delegate to specialists in `.claude/agents/`:

| Specialist | Domain |
|------------|--------|
| `dsp-specialist` | `auralis/core/`, `auralis/dsp/`, `vendor/auralis-dsp/`, signal flow, audio invariants |
| `backend-specialist` | `auralis-web/backend/` — routers, streaming, WebSocket, schemas |
| `frontend-specialist` | `auralis-web/frontend/` — components, hooks, Redux, design tokens |
| `library-specialist` | `auralis/library/` — 14 repositories (+ `BaseRepository`), migrations, SQLite, scanner |

Invoke via the Task tool with `subagent_type: <name>`.

## Deduplication (MANDATORY)

Before reporting ANY finding:

1. Run: `gh issue list --limit 200 --json number,title,state,labels > /tmp/audit/issues.json`
2. Search for keywords from your finding in existing issue titles.
3. Scan `docs/audits/` for prior reports covering the same issue.
4. Scan `.claude/issues/` for local snapshots of prior fixes.
5. If a matching issue exists:
   - **OPEN**: Note as "Existing: #NNN" and skip — do NOT re-report.
   - **CLOSED**: Verify the fix is still in place. If regressed, report as "Regression of #NNN".
6. If no match: Report as NEW.

## Sibling Detection

When a bug pattern exists, check ALL siblings before declaring scope. Common sibling groups in Auralis:

| Pattern | Where to grep |
|---------|---------------|
| DSP stage missing `.copy()` | All files under `auralis/dsp/` and `auralis/core/` |
| Repository raw SQL | All 14 repos under `auralis/library/repositories/` (each extends `BaseRepository` in `base.py`; also check `factory.py`) |
| Router missing input validation | All 19 route handlers under `auralis-web/backend/routers/` |
| Hook missing cleanup | All files under `auralis-web/frontend/src/hooks/` |
| Component > 300 lines | All files under `auralis-web/frontend/src/components/` |
| Service without lifecycle | All files under `auralis/services/` and `auralis-web/backend/services/` |

Use a single `grep -rn <pattern> <dir>/` and report all siblings in the SAME finding (do not file N separate issues).

## Base Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: <audit area>
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet or exact call path demonstrating the issue
- **Impact**: What breaks, when, blast radius
- **Siblings**: Other locations with the same pattern (if any)
- **Related**: Links to related findings or issues
- **Suggested Fix**: Brief direction (1-3 sentences)
```

Specialized audit commands add extra fields (e.g., `Trigger Conditions`, `Flow`, `Changed File`) — see each command for details.

## Domain Labels

Severity: `critical`, `high`, `medium`, `low`
Domain: `audio-integrity`, `dsp`, `player`, `backend`, `frontend`, `library`, `security`, `concurrency`, `performance`, `websocket`, `streaming`, `fingerprint`, `deprecation`, `tech-debt`
Type: `bug`, `enhancement`, `maintenance`

## Report Finalization

1. Save your report to: `docs/audits/AUDIT_<TYPE>_<TODAY>.md` (YYYY-MM-DD format).
2. Do NOT create GitHub issues directly during the audit.
3. Inform the user the report is ready and suggest:
   ```
   /audit-publish docs/audits/AUDIT_<TYPE>_<TODAY>.md
   ```
