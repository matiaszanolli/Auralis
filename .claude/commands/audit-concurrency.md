# Concurrency and State Integrity Audit

Audit Auralis for race conditions, missing locks, thread safety violations, state machine bugs, and unsafe concurrent access patterns in the audio player, processing pipeline, and backend services. Then create GitHub issues for every new confirmed finding.

**Shared protocol**: Read `.claude/commands/_audit-common.md` first for project layout, severity framework, methodology, deduplication rules, and GitHub issue template.

## Severity Examples

| Severity | Concurrency-Specific Examples |
|----------|------------------------------|
| **CRITICAL** | Concurrent writes to audio buffer, race between player state and output, database corruption from parallel access |
| **HIGH** | Seek during gapless transition, queue modification during playback, parallel DSP chunk processing errors |
| **MEDIUM** | Unprotected shared state, missing copy-before-modify, in-memory state without persistence |
| **LOW** | Coarse-grained locks, unnecessary serialization, redundant locking |

## Audit Dimensions

### Dimension 1: Player Thread Safety

**Key files**: `auralis/player/enhanced_audio_player.py`, `auralis/player/gapless_playback_engine.py`, `auralis/player/queue_controller.py`, `auralis/player/realtime_processor.py`

**Check**:
- [ ] RLock usage — is every shared state access protected? Are locks properly scoped?
- [ ] State transitions (play/pause/stop/seek) — are they atomic? Can a seek overlap with a gapless transition?
- [ ] Queue modifications during playback — is the queue protected while iterating?
- [ ] Position/duration invariant (`position <= duration`) — can a race violate this?
- [ ] Audio buffer access — can the playback thread and processing thread access the same buffer simultaneously?
- [ ] Callback safety — are player callbacks invoked with or without locks held?
- [ ] Can `stop()` race with `play()` leaving the player in an undefined state?

### Dimension 2: Audio Processing Pipeline

**Key files**: `auralis/core/hybrid_processor.py`, `auralis/core/simple_mastering.py`, `auralis/optimization/parallel_processor.py`, `auralis/dsp/unified.py`, `vendor/auralis-dsp/`

**Check**:
- [ ] Parallel processor — are audio chunks independently copied before processing? Can adjacent chunks interfere?
- [ ] Copy-before-modify pattern — is `audio.copy()` consistently used before in-place NumPy operations?
- [ ] Rust DSP boundary — does PyO3 correctly handle GIL release during processing? Can concurrent calls corrupt shared state?
- [ ] HybridProcessor chain — if one stage fails mid-array, is the pipeline state consistent?
- [ ] Sample count preservation — can parallel processing paths produce different lengths?
- [ ] Crossfade between chunks (recent fix `0a5df7a3`) — is the crossfade buffer shared or independent?

### Dimension 3: Backend WebSocket & Streaming

**Key files**: `auralis-web/backend/audio_stream_controller.py`, `auralis-web/backend/chunked_processor.py`, `auralis-web/backend/processing_engine.py`, `auralis-web/backend/main.py`

**Check**:
- [ ] Multiple WebSocket clients — can two clients request different tracks simultaneously?
- [ ] Chunked processor state — is it per-request or shared? Can concurrent requests corrupt chunk state?
- [ ] Processing engine — shared or per-request instances? Thread safety?
- [ ] FastAPI async handlers calling sync audio code — are they using `run_in_executor`? Can blocking calls starve the event loop?
- [ ] WebSocket disconnect during processing — is cleanup atomic? Resource leaks?

### Dimension 4: Library & Database

**Key files**: `auralis/library/manager.py`, `auralis/library/repositories/`, `auralis/library/scanner.py`, `auralis/library/migration_manager.py`

**Check**:
- [ ] SQLite thread safety — `check_same_thread=False`? Connection pooling config?
- [ ] `pool_pre_ping=True` — is it actually set?
- [ ] Concurrent scans — can two scan operations run simultaneously and cause conflicts?
- [ ] Repository pattern — any raw SQL bypassing the ORM?
- [ ] Library writes during playback reads — can a scan update a track that's currently playing?
- [ ] Migration execution — safe to run while the app is serving requests?

### Dimension 5: Frontend State Consistency

**Key files**: `auralis-web/frontend/src/store/`, `auralis-web/frontend/src/hooks/`, `auralis-web/frontend/src/services/`

**Check**:
- [ ] Redux dispatch ordering — can WebSocket messages arrive and dispatch out of order?
- [ ] Stale closure bugs in hooks — do effect cleanup functions race with new connections?
- [ ] Optimistic updates — are they reconciled correctly when the backend responds?
- [ ] WebSocket reconnection — does the frontend correctly re-sync state after reconnect?
- [ ] Multiple rapid user actions (skip, skip, skip) — does the frontend handle rapid state changes?

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

Use labels: severity label + `concurrency` + `bug`
