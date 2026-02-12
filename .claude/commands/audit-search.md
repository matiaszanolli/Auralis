# Comprehensive Auralis Audit

Perform a complete audit of the Auralis music player and audio enhancement platform, then create GitHub issues for every new confirmed finding.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`:

- **Audio Engine**: `auralis/` — Core Python audio engine (DSP, analysis, player, library, I/O)
- **Backend**: `auralis-web/backend/` — FastAPI REST + WebSocket server (:8765)
- **Frontend**: `auralis-web/frontend/` — React 18, TypeScript, Vite, Redux, MUI
- **Rust DSP**: `vendor/auralis-dsp/` — PyO3 module (HPSS, YIN, Chroma)
- **Desktop**: `desktop/` — Electron wrapper
- **Tests**: `tests/` — 850+ tests across 21 directories

## Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | Audio corruption, data loss, or exploitable vulnerability in production NOW. | Sample count mismatch causing clicks/gaps, database corruption, unvalidated file paths |
| **HIGH** | Failures under realistic conditions (concurrency, large libraries, long playback). Fix before next release. | Race conditions in player state, memory leaks during streaming, WebSocket disconnect data loss |
| **MEDIUM** | Incorrect behavior with workarounds, or affects non-critical paths. Fix within 2 sprints. | Inconsistent API schemas, missing input validation, stale Redux state |
| **LOW** | Code quality, maintainability, or minor inconsistencies. Fix opportunistically. | Dead code, naming inconsistencies, missing type hints, undocumented APIs |

## Audit Dimensions

Cover ALL of these systematically:

1. **Audio Integrity** — Sample count preservation, bit depth handling, clipping prevention, gapless playback, crossfade correctness, phase coherence across processing stages
2. **DSP Pipeline Correctness** — HybridProcessor chain, SimpleMastering algorithm, psychoacoustic EQ, dynamics control, Rust DSP module integration
3. **Player State Management** — State transitions (play/pause/stop/seek), queue management, RLock usage, gapless engine, real-time processor lifecycle
4. **Backend API & WebSocket** — REST endpoint correctness, WebSocket streaming reliability, chunked processing (30s chunks, 3s crossfade), schema consistency
5. **Frontend State & UI** — Redux store consistency, WebSocket hook lifecycle, component state management, design token usage
6. **Library & Database** — SQLite thread safety, repository pattern adherence, migration integrity, scanner reliability, query performance (N+1)
7. **Security** — File path validation, WebSocket auth, input sanitization, CORS configuration, dependency vulnerabilities
8. **Concurrency** — RLock correctness, parallel processor safety, thread-safe player state, async/sync boundary handling
9. **Error Handling & Recovery** — Graceful degradation on corrupt files, WebSocket reconnection, database recovery, FFmpeg failures
10. **Test Coverage Gaps** — Untested critical paths, missing edge cases, mocked-only external deps

## Key Entry Points

### Audio Engine (`auralis/`)
- `core/hybrid_processor.py` — HybridProcessor: main DSP pipeline
- `core/simple_mastering.py` — SimpleMastering algorithm (actively modified)
- `core/processor.py` — Core processing entry point
- `core/config.py` — Processing configuration
- `dsp/unified.py` — Unified DSP pipeline
- `dsp/psychoacoustic_eq.py` — Psychoacoustic EQ
- `player/enhanced_audio_player.py` — Main player with adaptive DSP
- `player/gapless_playback_engine.py` — Gapless playback engine
- `player/queue_controller.py` — Queue management
- `player/realtime_processor.py` — Real-time audio processing
- `optimization/parallel_processor.py` — Parallel audio processing
- `library/manager.py` — LibraryManager (SQLite)
- `library/repositories/` — 12 repository classes
- `io/unified_loader.py` — Audio file loading (FFmpeg, SoundFile)
- `analysis/fingerprint/` — 25D fingerprinting system

### Backend (`auralis-web/backend/`)
- `main.py` — FastAPI app entry point
- `routers/` — 18 route handlers
- `processing_engine.py` — Audio processing orchestration
- `chunked_processor.py` — 30s chunk processing with 3s crossfade
- `audio_stream_controller.py` — WebSocket audio streaming
- `schemas.py` — Request/response schemas

### Frontend (`auralis-web/frontend/src/`)
- `components/` — UI components
- `hooks/` — Domain hooks (player, library, enhancement, websocket, api)
- `store/` — Redux state management
- `services/` — API clients
- `design-system/` — Design tokens

## Critical Invariants to Verify

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
- **Crossfade**: equal-power crossfade between chunks (recent fix in `0a5df7a3`)

## Deduplication (MANDATORY)

Before reporting ANY finding:

1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. Search for keywords from your finding in existing issue titles
3. Check existing audit reports in `docs/audits/` for prior coverage
4. If a matching issue exists:
   - **OPEN**: Note as "Existing: #NNN" and skip — do NOT re-report
   - **CLOSED**: Verify the fix is still in place. If regressed, report as "Regression of #NNN"
5. If no match: Report as NEW

## Methodology

- Be skeptical. Assume there are bugs even if the code "looks fine."
- For each claim, re-read the code path to confirm before including it.
- Prefer evidence from concrete code paths (call sites, data structures, configs) over assumptions.
- After making a finding, attempt to disprove it. Only include findings you cannot disprove.
- Pay special attention to audio integrity — sample count mismatches cause audible artifacts.
- Trace audio data through the full pipeline: load -> analyze -> process -> stream -> playback.

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_SEARCH_<TODAY>.md`** (use today's date, format YYYY-MM-DD).

### Report Structure

1. **Executive Summary** — Total findings by severity, key themes, most impactful issues
2. **Findings** — Grouped by severity (CRITICAL first), using the per-finding format below
3. **Relationships** — How findings interact, shared root causes, cascading effects
4. **Prioritized Fix Order** — What to fix first and why (dependency + severity)
5. **Cross-Cutting Recommendations** — Architecture, audio integrity, reliability, testing

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Audio Integrity | DSP Pipeline | Player State | Backend API | Frontend | Library | Security | Concurrency | Error Handling | Test Coverage
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet or exact call path demonstrating the issue
- **Impact**: What breaks, when, blast radius
- **Related**: Links to related findings or issues
- **Suggested Fix**: Brief direction (1-3 sentences)
```

## Phase 2: Publish to GitHub

After completing the audit report, for every finding with **Status: NEW** or **Regression**:

1. **Create a GitHub issue** with:
   - **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
   - **Labels**: severity label (`critical`, `high`, `medium`, `low`) + domain label(s) (`audio-integrity`, `dsp`, `player`, `backend`, `frontend`, `library`, `security`, `concurrency`, `performance`, `websocket`, `streaming`, `fingerprint`) + `bug`
   - **Body**:
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

2. **Cross-reference**: For each new issue that relates to an existing issue, add a comment to the existing issue:
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
