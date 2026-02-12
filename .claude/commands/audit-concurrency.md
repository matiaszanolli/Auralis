# Concurrency and State Integrity Audit

Audit Auralis for race conditions, missing locks, thread safety violations, state machine bugs, and unsafe concurrent access patterns in the audio player, processing pipeline, and backend services. Then create GitHub issues for every new confirmed finding.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`:

- **Audio Engine**: `auralis/` — Core Python audio engine (player, DSP, library)
- **Backend**: `auralis-web/backend/` — FastAPI REST + WebSocket (:8765)
- **Frontend**: `auralis-web/frontend/` — React 18, Redux
- **Rust DSP**: `vendor/auralis-dsp/` — PyO3 module
- **Tests**: `tests/` — 850+ tests across 21 directories

## Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | Audio corruption or data loss under normal concurrency. | Concurrent writes to audio buffer, race between player state and output, database corruption from parallel access |
| **HIGH** | Race conditions triggered under realistic usage patterns. | Seek during gapless transition, queue modification during playback, parallel DSP chunk processing errors |
| **MEDIUM** | Unsafe patterns that haven't caused issues yet but will at scale. | Unprotected shared state, missing copy-before-modify, in-memory state without persistence |
| **LOW** | Sub-optimal concurrency patterns with negligible current impact. | Coarse-grained locks, unnecessary serialization, redundant locking |

## Audit Dimensions

### Dimension 1: Player Thread Safety

**Key files**:
- `auralis/player/enhanced_audio_player.py` — Main player with adaptive DSP
- `auralis/player/gapless_playback_engine.py` — Gapless playback
- `auralis/player/queue_controller.py` — Queue management
- `auralis/player/realtime_processor.py` — Real-time audio processing

**Check**:
- [ ] RLock usage — is every shared state access protected? Are locks properly scoped?
- [ ] State transitions (play/pause/stop/seek) — are they atomic? Can a seek overlap with a gapless transition?
- [ ] Queue modifications during playback — is the queue protected while iterating?
- [ ] Position/duration invariant (`position <= duration`) — can a race violate this?
- [ ] Audio buffer access — can the playback thread and processing thread access the same buffer simultaneously?
- [ ] Callback safety — are player callbacks invoked with or without locks held?
- [ ] Can `stop()` race with `play()` leaving the player in an undefined state?

### Dimension 2: Audio Processing Pipeline

**Key files**:
- `auralis/core/hybrid_processor.py` — HybridProcessor: main DSP pipeline
- `auralis/core/simple_mastering.py` — SimpleMastering algorithm
- `auralis/optimization/parallel_processor.py` — Parallel audio processing
- `auralis/dsp/unified.py` — Unified DSP pipeline
- `vendor/auralis-dsp/` — Rust DSP module (PyO3)

**Check**:
- [ ] Parallel processor — are audio chunks independently copied before processing? Can adjacent chunks interfere?
- [ ] Copy-before-modify pattern — is `audio.copy()` consistently used before in-place NumPy operations?
- [ ] Rust DSP boundary — does PyO3 correctly handle GIL release during processing? Can concurrent calls corrupt shared state?
- [ ] HybridProcessor chain — if one stage fails mid-array, is the pipeline state consistent?
- [ ] Sample count preservation — can parallel processing paths produce different lengths?
- [ ] Crossfade between chunks (recent fix `0a5df7a3`) — is the crossfade buffer shared or independent?

### Dimension 3: Backend WebSocket & Streaming

**Key files**:
- `auralis-web/backend/audio_stream_controller.py` — WebSocket audio streaming
- `auralis-web/backend/chunked_processor.py` — 30s chunks, 3s crossfade
- `auralis-web/backend/processing_engine.py` — Audio processing orchestration
- `auralis-web/backend/main.py` — FastAPI app

**Check**:
- [ ] Multiple WebSocket clients — can two clients request different tracks simultaneously?
- [ ] Chunked processor state — is it per-request or shared? Can concurrent requests corrupt chunk state?
- [ ] Processing engine — shared or per-request instances? Thread safety?
- [ ] FastAPI async handlers calling sync audio code — are they using `run_in_executor`? Can blocking calls starve the event loop?
- [ ] WebSocket disconnect during processing — is cleanup atomic? Resource leaks?

### Dimension 4: Library & Database

**Key files**:
- `auralis/library/manager.py` — LibraryManager
- `auralis/library/repositories/` — 12 repository classes
- `auralis/library/scanner.py` — Folder scanning
- `auralis/library/migration_manager.py` — Schema migrations

**Check**:
- [ ] SQLite thread safety — `check_same_thread=False`? Connection pooling config?
- [ ] `pool_pre_ping=True` — is it actually set?
- [ ] Concurrent scans — can two scan operations run simultaneously and cause conflicts?
- [ ] Repository pattern — any raw SQL bypassing the ORM?
- [ ] Library writes during playback reads — can a scan update a track that's currently playing?
- [ ] Migration execution — safe to run while the app is serving requests?

### Dimension 5: Frontend State Consistency

**Key files**:
- `auralis-web/frontend/src/store/` — Redux state management
- `auralis-web/frontend/src/hooks/` — WebSocket and player hooks
- `auralis-web/frontend/src/services/` — API clients

**Check**:
- [ ] Redux dispatch ordering — can WebSocket messages arrive and dispatch out of order?
- [ ] Stale closure bugs in hooks — do effect cleanup functions race with new connections?
- [ ] Optimistic updates — are they reconciled correctly when the backend responds?
- [ ] WebSocket reconnection — does the frontend correctly re-sync state after reconnect?
- [ ] Multiple rapid user actions (skip, skip, skip) — does the frontend handle rapid state changes?

## Deduplication (MANDATORY)

Before reporting ANY finding:
1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. Search for keywords from your finding in existing issue titles
3. If a matching issue exists:
   - **OPEN**: Skip
   - **CLOSED**: Verify fix is in place. If regressed, report as regression
4. If no match: Report as NEW

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_CONCURRENCY_<TODAY>.md`** (use today's date).

### Per-Finding Format
```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Player Thread Safety | Audio Processing | Backend Streaming | Library & Database | Frontend State
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Trigger Conditions**: Exact timing/concurrency scenario needed
- **Evidence**: Code snippet showing the unsafe pattern
- **Impact**: What state gets corrupted, what audio artifacts occur
- **Suggested Fix**: Lock type, copy pattern, or state machine change needed
```

## Phase 2: Publish to GitHub

For every finding with **Status: NEW** or **Regression**, create a GitHub issue:
- **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
- **Labels**: severity label (`critical`, `high`, `medium`, `low`) + `concurrency` + `bug`
- **Body**: Summary, Evidence, Trigger Conditions, Impact, Related Issues, Proposed Fix, Acceptance Criteria, Test Plan
- **Cross-reference** related existing issues with `gh issue comment`.
- **Print summary table** at the end.
