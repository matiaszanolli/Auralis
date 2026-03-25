# Concurrency & State Integrity Audit — 2026-03-25

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: Player thread safety, audio processing pipeline, backend streaming, library/database, frontend state
**Dimensions**: 5 parallel agents (Sonnet), followed by manual merge and deduplication
**Method**: Deep — full execution path tracing

## Executive Summary

This audit reveals **32 concurrency findings** across all 5 dimensions: 5 HIGH, 11 MEDIUM, 16 LOW. No CRITICAL findings.

**Most impactful clusters:**

1. **Shared HybridProcessor cache** (CONC-07, CONC-08) — The module-level LRU-cached processor is shared across concurrent API requests with no lock. Mutable instance state races between threads.

2. **Player state transitions** (PTS-1 through PTS-6) — Multiple race windows between auto-advance, seek, stop, and load operations. The `_auto_advancing` flag can be prematurely cleared, and `next_track()` can restart playback after an explicit stop.

3. **Database concurrent writes** (DB-C-01 through DB-C-04) — Migration session leak, missing IntegrityError guard on album creation, non-atomic scan folder CRUD, and playlist lazy-load race.

4. **Frontend stale-closure races** (FSC-1 through FSC-4) — handleNext/Previous reads stale queue index, usePlayerAPI private state diverges from Redux, usePlayNormal misses stream start on subscribe-inside-callback.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 5 |
| MEDIUM | 11 |
| LOW | 16 |
| **Total** | **32** |

## Concurrency Matrix

| Component | Lock Type | Status |
|-----------|-----------|--------|
| PlaybackController | RLock (`_lock`) | Mostly correct; some external reads bypass it |
| QueueManager | RLock (`_lock`) | Relies on RLock re-entrancy for shuffle |
| IntegrationManager | RLock (`_position_lock`) | Position reads fixed; torn-read risk on 32-bit |
| AutoMasterProcessor | None | No per-object lock — relies on caller's lock |
| HybridProcessor (cached) | None | **Shared across threads with no protection** |
| PerformanceOptimizer | None | gc_counter non-atomic increment |
| AudioStreamController | asyncio.Lock (`_active_streams_lock`, `_chunk_tails_lock`) | Mostly correct; seek path misses active_streams update |
| ConnectionManager | asyncio.Lock | Fixed in recent commit |
| ProcessingEngine | threading.Lock (`_jobs_lock`) | get_job/register_callback skip lock |
| SQLite/SQLAlchemy | Connection pool | pool_pre_ping=True set; migration session leaked |
| Redux Store | Single-threaded dispatch | Correct; issues are in hook closures |
| WebSocket hooks | Event-driven | Subscribe-inside-callback creates race windows |

## Findings

### HIGH

---

### CONC-07: Shared HybridProcessor from LRU cache races between concurrent requests
- **Severity**: HIGH
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py` (module-level `process_adaptive/reference/hybrid`)
- **Status**: NEW
- **Trigger Conditions**: Two concurrent API requests for different tracks sharing same cache key
- **Impact**: Mutable instance state (`last_content_profile`, `last_fingerprint`, `adaptive_params`) overwritten mid-processing; wrong enhancement applied to audio
- **Suggested Fix**: Add per-processor `threading.Lock` or use `copy.deepcopy()` from cache

---

### CONC-08: Unprotected read-mutate-restore of `use_fingerprint_analysis` flag
- **Severity**: HIGH
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py` (`apply_enhancement`, `_process_chunk_with_hybrid_processor`)
- **Status**: NEW
- **Trigger Conditions**: Two ChunkedAudioProcessor instances sharing cached HybridProcessor
- **Impact**: One request's fingerprint analysis setting overwritten by another; wrong DSP applied
- **Suggested Fix**: Pass flag as parameter instead of mutating shared instance state

---

### PTS-1: AutoMasterProcessor has no per-object lock
- **Severity**: HIGH
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/realtime_processor.py` (AutoMasterProcessor class)
- **Status**: NEW
- **Trigger Conditions**: Future direct call bypassing RealtimeProcessor.lock
- **Impact**: Race between audio callback's `process()` and any concurrent state mutation
- **Suggested Fix**: Add `threading.Lock()` to AutoMasterProcessor

---

### PTS-2: IntegrationManager._get_position_seconds reads position without PlaybackController lock
- **Severity**: HIGH
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/integration_manager.py` (`_get_position_seconds`)
- **Status**: NEW
- **Trigger Conditions**: Concurrent seek during position read on 32-bit platform
- **Impact**: Torn read producing position > duration (invariant violation)
- **Suggested Fix**: Read position under PlaybackController._lock

---

### DB-C-01: MigrationManager leaks long-lived session and uses dual connection paths
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_manager.py:146-148, 246-296`
- **Status**: NEW
- **Trigger Conditions**: Migration failure during startup
- **Impact**: raw_conn write-lock blocks pool for 15s; hard startup failure
- **Suggested Fix**: Use context manager for session; use single connection path

---

### MEDIUM

---

### FSC-1: handleNext/handlePrevious read stale currentQueueIndex after dispatch
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx`
- **Status**: NEW
- **Trigger**: Auto-advance effect + manual Next button race
- **Impact**: playEnhanced() called twice for same track

---

### FSC-2: usePlayerAPI private playerState diverges from Redux after WS reconnect
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerAPI.ts`
- **Status**: NEW
- **Impact**: Components consuming usePlayerAPI see different data than Redux

---

### FSC-3: usePlayNormal subscribes to WS inside playNormal() — misses stream start
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts`
- **Status**: NEW
- **Trigger**: Fast track switch; WS delivers audio_stream_start before subscribe completes
- **Impact**: Buffer never initialized, streaming stalls in "buffering" state

---

### FSC-4: singletonLastStreamCommand not invalidated during rapid skips + WS disconnect
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx`
- **Status**: NEW
- **Impact**: Wrong-track resumption from arbitrary offset after reconnect

---

### DIM-3-01: Seek handler does not update _active_streaming_track_ids
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/routers/system.py:~762`
- **Status**: NEW
- **Trigger**: Seek followed by immediate play_enhanced for same track
- **Impact**: Duplicate concurrent streams, crossfade tearing

---

### CONC-09: PerformanceOptimizer.gc_counter non-atomic increment
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis/optimization/parallel_processor.py`
- **Status**: NEW

---

### CONC-10: _apply_module_optimizations monkey-patches class method non-idempotently
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis/optimization/parallel_processor.py`
- **Status**: NEW

---

### PTS-3: seek() reads get_total_samples() and seeks in two separate lock acquisitions
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py`
- **Status**: NEW
- **Trigger**: Concurrent gapless transition between two lock acquisitions
- **Impact**: position > len(audio_data)

---

### PTS-4: add_to_queue() checks is_loaded() then loads without re-acquiring lock
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py`
- **Status**: NEW

---

### PTS-5: next_track() restarts playback after explicit stop() due to stale is_playing snapshot
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py`
- **Status**: NEW

---

### DB-C-02: Album creation has no IntegrityError guard for concurrent scans
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository.py:122-133`
- **Status**: NEW
- **Trigger**: max_concurrent_scans > 1, two files from same album
- **Impact**: IntegrityError on INSERT INTO albums, track counted as failed

---

### DB-C-03: add_scan_folder/remove_scan_folder non-atomic read-modify-write
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/settings_repository.py:148-188`
- **Status**: NEW
- **Trigger**: Rapid double-click adding/removing folder
- **Impact**: Second write silently overwrites first, folder lost

---

### DB-C-04: PlaylistRepository.remove_track uses lazy-loaded collection without eager load
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/playlist_repository.py:228-250`
- **Status**: NEW

---

### LOW

---

### PTS-6: load_track_from_library uses two-step set_loading + stop instead of atomic load_and_stop
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py`

### PTS-7: QueueManager relies on RLock re-entrancy for shuffle/unshuffle
- **Severity**: LOW
- **Dimension**: Player Thread Safety

### PTS-8: _auto_advancing cleared in finally after next_track triggers new advance
- **Severity**: LOW
- **Dimension**: Player Thread Safety

### PTS-9: advance_with_prebuffer calls peek_next_track twice with gap
- **Severity**: LOW
- **Dimension**: Player Thread Safety

### PTS-10: IntegrationManager callback registration ordering fragile
- **Severity**: LOW
- **Dimension**: Player Thread Safety

### CONC-11: ParallelBandProcessor passes original array (not copy) to thread workers
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis/optimization/parallel_processor.py`

### CONC-12: Free function process_mono_chunks in Rust uses overwrite instead of overlap-add
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `vendor/auralis-dsp/src/chunk_processor.rs`

### DIM-3-02: unregister_progress_callback unlocked sync pop races with async notify
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/processing_engine.py:232-252`

### DIM-3-03: _chunk_tails cross-track contamination during prefetch
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1196-1204`

### DB-C-05: _reset_all bypasses RepositoryFactory and has no worker coordination
- **Severity**: LOW
- **Dimension**: Library & Database

### DB-C-06: restore_database uses shutil.copy2 instead of SQLite online backup API
- **Severity**: LOW
- **Dimension**: Library & Database

### FSC-5: stop() dispatches clearQueue() optimistically with no rollback on error
- **Severity**: LOW
- **Dimension**: Frontend State

### FSC-6: useWebSocketSubscription messageTypes.join dependency triggers on reorder
- **Severity**: LOW
- **Dimension**: Frontend State

### FSC-7: usePlaybackState (library) sends 'pause_playback' instead of 'pause'
- **Severity**: LOW
- **Dimension**: Frontend State

### PTS-6 (additional): load_track_from_library non-atomic load pattern
- **Severity**: LOW
- **Dimension**: Player Thread Safety

---

## Relationships & Shared Root Causes

1. **Shared processor cache**: CONC-07 + CONC-08 are the same root cause — module-level LRU cache returns shared mutable instances. Fixing the cache with per-call `deepcopy()` or a per-processor lock resolves both.

2. **Player state gaps**: PTS-3, PTS-4, PTS-5 all stem from multi-step operations not being atomic. A single "command pattern" with a transaction-like lock scope would address all three.

3. **Frontend parallel state machines**: FSC-1, FSC-2, FSC-3 result from hooks maintaining private state alongside Redux. Consolidating to Redux as single source of truth eliminates the class.

4. **Database session discipline**: DB-C-01, DB-C-03, DB-C-04 all involve session lifecycle issues — leaked sessions, non-atomic reads, lazy loads. A consistent context-manager pattern would prevent all three.

## Prioritized Fix Order

1. **CONC-07 + CONC-08** — Shared HybridProcessor races. High probability of wrong DSP applied. Fix: Add per-instance lock or deepcopy from cache.
2. **DB-C-01** — Migration session leak blocking startup. Fix: Context manager for session lifecycle.
3. **PTS-5** — next_track restarts after stop. Fix: Check _stop_requested before play().
4. **FSC-1** — Double playEnhanced from stale index. Fix: Read currentQueueIndex from Redux inside the handler, not from closure.
5. **FSC-3** — usePlayNormal misses stream start. Fix: Subscribe on mount like usePlayEnhanced does.
6. **DB-C-02** — Album IntegrityError during concurrent scan. Fix: Add begin_nested() + IntegrityError guard matching artist/genre pattern.
7. **DIM-3-01** — Seek doesn't update active_streaming_track_ids. Fix: One-line addition inside lock block.

---

*Report generated by Claude Opus 4.6 — 2026-03-25*
*Suggest next: `/audit-publish docs/audits/AUDIT_CONCURRENCY_2026-03-25.md`*
