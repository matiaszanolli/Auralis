# Concurrency and State Integrity Audit — 2026-02-22

**Scope**: Race conditions, missing locks, thread safety violations, state machine bugs, and unsafe concurrent access patterns across 5 dimensions.

**Methodology**: Parallel agent exploration across Player Thread Safety, Audio Processing Pipeline, and Backend/DB/Frontend concurrency. All candidate findings manually verified against source code — **15+ false positives eliminated** through careful tracing of lock acquisition paths, asyncio execution model, and per-instance component lifecycles.

**Result**: 1 NEW finding, 1 existing cross-reference. The codebase demonstrates strong concurrency hygiene with comprehensive locking, external synchronization patterns, and proper asyncio usage.

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 1 | CONC-01 |
| LOW | 0 | — |
| **Total** | **1** | |

**Existing cross-reference**: useLibraryData loadMore race → #2603 (FE-17)

---

## Findings

### CONC-01: No player state push on WebSocket reconnect
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming / Frontend State Consistency
- **Location**: `auralis-web/backend/routers/system.py:125-141` → `auralis-web/frontend/src/contexts/WebSocketContext.tsx:388-407`
- **Status**: NEW
- **Trigger Conditions**: WebSocket disconnects and reconnects while the player is paused or stopped. The frontend retains stale Redux state (wrong track, wrong position, wrong volume) indefinitely because no state push is triggered until the next player state change.
- **Evidence**:

Backend sends enhancement settings on connect (#2507) but NOT player state:
```python
# system.py:125-141 — after WebSocket accept
await manager.connect(websocket)
# Enhancement settings pushed immediately (fix #2507):
if get_enhancement_settings is not None:
    _settings = get_enhancement_settings()
    await websocket.send_text(json.dumps({
        "type": "enhancement_settings_changed",
        "data": { ... }
    }))
# ← No equivalent player_state push here
```

If the player is playing, a `position_changed` message arrives within ~1 second (from the position update loop in `state_manager.py:208-251`), but this is a lightweight message containing only `{"position": float}` — it does NOT include current track, queue, volume, shuffle/repeat mode, or mastering state.

If the player is paused or stopped, no update is sent until the next state transition.

- **Impact**: After WebSocket reconnect, the frontend UI may display stale player information (wrong track name, wrong position, wrong volume level) until the user or auto-advance triggers the next state change. In the worst case (paused during reconnect), the stale state persists indefinitely.
- **Suggested Fix**: Send a full `player_state` message immediately after WebSocket accept, mirroring the enhancement settings pattern. In `system.py`, after the `enhancement_settings_changed` push, add:
```python
if get_player_state is not None:
    _state = get_player_state()
    await websocket.send_text(json.dumps({
        "type": "player_state",
        "data": _state.model_dump()
    }))
```

---

## Verification Log: False Positives Eliminated

The following candidate findings were reported by exploration agents and eliminated after manual verification against source code:

### Dimension 1: Player Thread Safety — All Clear

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| AutoMasterProcessor concurrent access (set_fingerprint/process) | FALSE POSITIVE | Externally synchronized by `RealtimeProcessor.lock` — every call path goes through `processor.py:88-98,100-143` which acquires the lock |
| LevelMatcher concurrent access | FALSE POSITIVE | Same external synchronization via `RealtimeProcessor.lock` at `processor.py:121` |
| PerformanceMonitor concurrent access | FALSE POSITIVE | Same external synchronization via `RealtimeProcessor.lock` at `processor.py:141,149` |
| AutoMaster profile race (set_profile vs process) | FALSE POSITIVE | `set_profile` called through `set_auto_master_profile()` → `IntegrationManager` → `RealtimeProcessor.set_profile()` which acquires the same lock |
| TOCTOU in get_audio_chunk end-of-track check | FALSE POSITIVE | Protected by `_auto_advancing` Event (atomic test-and-set prevents duplicate auto-advance). Audio callback is single-threaded. `AudioFileManager._audio_lock` protects data access (`audio_file_manager.py:122-131`) |
| stop() racing with get_audio_chunk() | FALSE POSITIVE | `stop()` only changes PlaybackController state (under RLock). `AudioFileManager` doesn't unload on stop — data remains valid. Worst case: one extra chunk read (benign) |
| load_file() racing with get_audio_chunk() | FALSE POSITIVE | `AudioFileManager.load_file()` loads data outside lock, then atomically swaps reference under `_audio_lock` (line 59-64). `get_audio_chunk()` holds `_audio_lock` for entire slice (line 122-131, fix #2423) |
| Callback invocation under lock (deadlock risk) | FALSE POSITIVE | Callbacks use snapshot pattern — list copied inside lock, invoked outside lock (fix #2291, `playback_controller.py:57-64`) |

### Dimension 2: Audio Processing Pipeline — All Clear

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| FFT chunks as NumPy views sharing memory | FALSE POSITIVE | `chunk = audio[i:i+fft_size]` creates a view, but `windowed = chunk * window` creates a NEW array. Workers never modify the original (`parallel_processor.py:116,146`) |
| Limiter/compressor lookahead buffer races | FALSE POSITIVE | `AdaptiveLimiter` and `AdaptiveCompressor` instances are per-DynamicsProcessor, which is per-pipeline. No sharing between threads |
| SimpleMasteringPipeline concurrent access | FALSE POSITIVE | Used per-call in batch/CLI contexts. Backend creates per-request instances via `ChunkedAudioProcessor`. `_fp_service_lock` protects lazy init (fix #2434) |

### Dimension 3: Backend WebSocket & Streaming — 1 Finding

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| `active_streams` dict write without lock | FALSE POSITIVE | asyncio single-threaded event loop — dict operations are atomic between await points. `active_streams` is only used for cleanup tracking (set/pop), never queried |
| `_chunk_tails.pop()` outside asyncio.Lock | FALSE POSITIVE | `.pop()` is a single atomic dict operation in asyncio context. The lock is specifically for check-then-set patterns (comment at line 231-233) |
| Stream cancellation race (old task cleanup vs new task registration) | FALSE POSITIVE | Router properly cancels old task under `_active_streaming_tasks_lock` (system.py:342-356). Even if cleanup races, `active_streams` is only for cleanup tracking |
| **No player state on reconnect** | **CONFIRMED** | **→ CONC-01** |

### Dimension 4: Library & Database — All Clear

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| SQLite thread safety config | FALSE POSITIVE | Properly configured: `check_same_thread=False`, `pool_pre_ping=True`, WAL mode, 5+5 pool (`manager.py:106-122`) |
| Concurrent scans | FALSE POSITIVE | `try_acquire_scan_slot()` with `_scan_slots_lock` limits to 1 concurrent scan (`manager.py:239-261`, `scanner.py:96-111`) |
| Migration during serving | FALSE POSITIVE | Uses file-based locking with guaranteed cleanup via context manager |

### Dimension 5: Frontend State Consistency — All Clear (1 Existing)

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| Redux dispatch ordering (rapid skip) | FALSE POSITIVE | WebSocket stream cancellation in router (system.py:346-349) ensures only the latest request is active. TCP guarantees message ordering |
| singletonLastStreamCommand stale after server-side stop | FALSE POSITIVE | Auralis is a single-user desktop app — server only acts on client commands. Client pauses/stops always clear the command (WebSocketContext.tsx:505-515) |
| useLibraryData loadMore race | Existing: #2603 | Already filed as FE-17 in frontend audit |
| WebSocket singleton StrictMode safety | FALSE POSITIVE | Module-level singletons with ref counting properly survive double-mounting (WebSocketContext.tsx:230-274) |

---

## Architecture Strengths

The codebase demonstrates strong concurrency patterns that prevented most agent-reported findings from being real:

1. **External synchronization pattern**: `RealtimeProcessor.lock` provides a single coarse-grained lock for all real-time DSP sub-components (AutoMaster, LevelMatcher, PerformanceMonitor). This eliminates entire classes of races without requiring each component to manage its own locking.

2. **Atomic swap pattern**: `AudioFileManager.load_file()` loads data outside the lock (slow I/O), then atomically swaps the reference under `_audio_lock`. This prevents blocking the audio callback while maintaining safety.

3. **Snapshot callback pattern**: `PlaybackController._notify_callbacks()` copies the callback list inside the lock, then invokes callbacks outside the lock. This prevents deadlocks from callbacks that re-enter player state.

4. **Event-based dedup**: `_auto_advancing` Event prevents duplicate auto-advance threads without requiring heavy synchronization.

5. **asyncio task lifecycle management**: The router's `_active_streaming_tasks_lock` + `cancel()` pattern ensures clean transitions between stream requests.

6. **Database WAL mode**: SQLite WAL enables concurrent readers without blocking writers, properly configured with `pool_pre_ping=True` for connection health checks.
