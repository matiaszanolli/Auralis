# Concurrency and State Integrity Audit
**Date**: 2026-02-19
**Auditor**: Claude (automated, 5 dimensions)
**Scope**: All 5 concurrency dimensions across the Auralis codebase; delta-focused on changes since 2026-02-17 audit
**Prior Audit**: [AUDIT_CONCURRENCY_2026-02-17.md](AUDIT_CONCURRENCY_2026-02-17.md) — 20 findings (C-01–C-20)
**Issues Created**: C-21 – C-24 (4 new findings)

---

## Summary

| Severity | Count | New Issues |
|----------|-------|-----------|
| CRITICAL | 0 | — |
| HIGH | 1 | C-21 |
| MEDIUM | 2 | C-22, C-23 |
| LOW | 1 | C-24 |
| **TOTAL NEW** | **4** | |
| Fixed since 2026-02-17 | 7 | C-02, C-05, C-06, C-09, C-12, C-15, C-16 |
| Partially fixed | 3 | C-10, C-18, C-19 |
| Still open | 10 | C-01, C-03→C-04, C-07–C-08, C-11, C-13–C-14, C-17, C-20 |

---

## Fix Verification (from C-01–C-20)

The following C-01–C-20 findings from the 2026-02-17 audit were verified against current code:

| Finding | Status | Evidence |
|---------|--------|---------|
| C-02: band_results aliasing in parallel processor | ✅ FIXED | `parallel_eq_processor/parallel_processor.py` replaced per-band parallel dispatch with vectorized `gain_curve` applied in a single pass; no `band_results` list at all |
| C-05: QueueManager tracks/index unprotected | ✅ FIXED | `auralis/player/components/queue_manager.py:25` — `self._lock = threading.RLock()` present; all public methods use `with self._lock` |
| C-06: ParallelFFTProcessor window_cache read outside lock | ✅ FIXED | Per AUDIT_INCREMENTAL_2026-02-18 commit `c603029d`: `get_window()` now returns inside `with self.lock` |
| C-09: _active_streaming_tasks dict comprehension race | ✅ FIXED | `auralis-web/backend/routers/system.py:25` — `_active_streaming_tasks_lock = asyncio.Lock()` present; all access under `async with _active_streaming_tasks_lock` |
| C-12: cache invalidation after track deletion order | ✅ FIXED | `auralis/library/manager.py:527–544` — double-invalidate: `invalidate_cache()` before `tracks.delete()` AND after, all inside `_delete_lock` |
| C-15: WebSocket disconnect double-delete KeyError | ✅ FIXED | `system.py` uses `.pop(ws_id, None)` under lock in all paths |
| C-16: Concurrent library scans duplicate tracks | ✅ FIXED | `auralis/library/manager.py:228–254` — `try_acquire_scan_slot()` / `release_scan_slot()` added; `auralis/library/scanner/scanner.py:96–111` enforces the guard at scan entry |
| C-10: FingerprintRepository raw sqlite3 | ⚠️ PARTIAL | `db_path` is now configurable (commit `218b38fb`) but raw `sqlite3.connect()` bypass still present; WAL lock contention risk remains |
| C-18: useWebSocketSubscription deferred listeners | ⚠️ PARTIAL | Deferred subscribe implemented but reconnect scenario not handled (see AUDIT_INCREMENTAL_2026-02-18 F3) |
| C-19: _auto_advancing Event allows double-advance on error | ⚠️ IMPROVED | `_auto_advance_next()` now calls `self.playback.stop()` in except path; subsequent `get_audio_chunk()` early-returns silence; finally still clears the event, but the stop guard prevents re-triggering |

---

## Deduplication Reference

The following existing issues (from prior audits or known tracker) were checked; no new finding matches them:

| Existing | Title |
|----------|-------|
| C-01 | AudioFileManager.audio_data Written from Gapless Thread Without Lock |
| C-04 | RealtimeLevelMatcher Shared State Not Protected |
| C-07 | prev_tail Crossfade Buffer Can Become Corrupted Mid-Chunk |
| C-08 | _fingerprint_service Lazy Init Is Not Thread-Safe |
| C-11 | IntegrationManager.callbacks List Mutated Without Lock |
| C-13 | ProcessingEngine.jobs Dict Modified Concurrently Without Lock |
| C-14 | SimpleChunkCache OrderedDict Mutated Without Lock |
| C-17 | useRestAPI Has No AbortController for Concurrent Rapid Requests |
| C-20 | _rate_limiter Cleanup Data Structure Access Is Uncoordinated |
| #2412 | GaplessPlaybackEngine.prebuffer_callbacks mutated without lock |
| I-01 | asyncio.Semaphore._value is a private CPython internal |
| I-02 | batch_update() mixed backup flags cause DB/disk inconsistency |
| F3 | useWebSocketSubscription deferred subscriptions not re-established after reconnect |

---

## Dimension 1: Player Thread Safety

### C-23: AudioPlayer.add_callback() Double-Registers Callbacks Causing Duplicate Invocation
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:403-406`, `auralis/player/integration_manager.py:73`, `auralis/player/playback_controller.py:44-58`
- **Status**: NEW
- **Trigger Conditions**: Every playback state change (play, pause, stop, seek) while any application callback is registered.
- **Evidence**:
  ```python
  # AudioPlayer.__init__ (implicitly via IntegrationManager.__init__):
  self.playback.add_callback(self._on_playback_state_change)  # integration registers first

  # AudioPlayer.add_callback:
  def add_callback(self, callback):
      self.integration.add_callback(callback)   # added to integration.callbacks
      self.playback.add_callback(callback)       # ALSO added to playback.callbacks

  # When PlaybackController._notify_callbacks fires:
  # playback.callbacks = [integration._on_playback_state_change, user_callback]
  # Step 1: integration._on_playback_state_change(state_info) is called:
  #   → mutates state_info dict (adds position, duration, current_file)
  #   → calls integration._notify_callbacks(enriched_state_info)
  #     → calls user_callback(enriched_state_info)   ← FIRST INVOCATION
  # Step 2: user_callback(enriched_state_info) is called directly  ← SECOND INVOCATION
  ```
  Both invocations deliver the same (enriched) dict. The user's callback is called twice per state change.
- **Impact**: Every Redux dispatch, WebSocket notification, or UI render triggered by player callbacks fires twice per event. If callbacks have side effects (queuing network requests, incrementing counters, updating playback state), those side effects occur twice. This is not data-corrupting but is a correctness bug and causes unnecessary re-renders in the frontend.
- **Suggested Fix**: Remove `self.playback.add_callback(callback)` from `AudioPlayer.add_callback()`. Application callbacks should be routed exclusively through `IntegrationManager`, which already receives all state changes via its registered `_on_playback_state_change` callback.

---

### C-24: IntegrationManager.record_track_completion() Non-Atomic Counter Increment
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/integration_manager.py:233-234`
- **Status**: NEW
- **Trigger Conditions**: Auto-advance thread calls `record_track_completion()` while the REST API handler concurrently processes a manual `/next` command that also calls `record_track_completion()`.
- **Evidence**:
  ```python
  def record_track_completion(self) -> None:
      self.tracks_played += 1   # ← not atomic; no lock
      self._notify_callbacks(...)
  ```
  In CPython, `x += 1` on an integer compiles to `LOAD_ATTR` + `BINARY_ADD` + `STORE_ATTR` — three bytecodes separated by GIL release points. Two threads can both read `tracks_played=N`, both add 1, and both write `N+1`, losing one increment.
- **Impact**: `tracks_played` session counter is under-counted when two completion events race. UI shows incorrect "tracks played this session" count.
- **Suggested Fix**: Add `threading.Lock` to `IntegrationManager` and hold it for the `+=` operation, or use `threading.RLock` shared with the existing callback notification path.

---

## Dimension 2: Audio Processing Pipeline

*No new findings. C-02 (band_results aliasing) confirmed FIXED. C-06 (window_cache outside lock) confirmed FIXED. C-07 and C-08 remain open from prior audit.*

---

## Dimension 3: Backend WebSocket & Streaming

### C-21: MAX_CONCURRENT_STREAMS Semaphore Defeated by Per-Request AudioStreamController Instantiation
- **Severity**: HIGH
- **Dimension**: Backend WebSocket & Streaming
- **Location**: `auralis-web/backend/audio_stream_controller.py:192-194`, `auralis-web/backend/routers/system.py:238-253`, `auralis-web/backend/routers/system.py:327-341`, `auralis-web/backend/routers/system.py:485-493`
- **Status**: NEW
- **Trigger Conditions**: Two or more concurrent WebSocket `play_enhanced`, `play_normal`, or `seek` commands.
- **Evidence**:
  ```python
  # audio_stream_controller.py:192-194 (AudioStreamController.__init__)
  self._stream_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)
  # ↑ semaphore created fresh on every instantiation

  # system.py — stream_audio() closure (called for every play_enhanced message)
  async def stream_audio():
      controller = AudioStreamController(   # ← NEW INSTANCE PER REQUEST
          chunked_processor_class=ChunkedAudioProcessor,
          get_repository_factory=get_repository_factory,
      )
      await controller.stream_enhanced_audio(...)  # semaphore.acquire() → value goes 10→9
      # ↑ only ever 1 holder per semaphore; cap of 10 is never approached

  # Same pattern in stream_normal() and stream_from_position()
  ```
  With 20 concurrent `play_enhanced` messages:
  - 20 `AudioStreamController` instances created, each with its own `asyncio.Semaphore(10)`
  - Each semaphore transitions 10→9→10; they are completely independent
  - All 20 streams run simultaneously — the limit of `MAX_CONCURRENT_STREAMS = 10` is never enforced
- **Impact**: `MAX_CONCURRENT_STREAMS` was added in issue #2185 to prevent OOM under load. That protection is now completely absent. Each concurrent stream holds a `ChunkedProcessor` in memory (~200 MB for a 10-min track at 44.1 kHz stereo). 50 concurrent streams = 10 GB heap. The application will OOM-kill or severely degrade under moderate load.
- **Suggested Fix**: Move `AudioStreamController` (or at minimum its `_stream_semaphore`) to module-level singleton scope. Create a single `_stream_semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)` at the top of `audio_stream_controller.py` (module level) and reference it from each request's streaming coroutine, or instantiate `AudioStreamController` once in `create_system_router` and capture it in the closures via closure variable.

---

## Dimension 4: Library & Database

### C-22: QueueController.get_queue_info() Composite Snapshot Is Not Atomic
- **Severity**: MEDIUM
- **Dimension**: Library & Database (Player Queue)
- **Location**: `auralis/player/queue_controller.py:225-237`
- **Status**: NEW
- **Trigger Conditions**: REST API reads queue state (`GET /api/queue`) while a concurrent `remove_track()` or `next_track()` modifies `QueueManager.current_index` and `tracks`.
- **Evidence**:
  ```python
  # queue_controller.py:225-237 — no lock held for the composite read
  def get_queue_info(self) -> dict:
      current = self.get_current_track()      # acquires + releases _lock
      return {
          'tracks': self.queue.tracks.copy(),      # ← direct attr access, no lock
          'current_index': self.queue.current_index,  # ← direct attr access, no lock
          'current_track': current,
          'track_count': len(self.queue.tracks),  # ← direct attr access, no lock
          'has_next': self.queue.current_index < len(self.queue.tracks) - 1,  # ← TOCTOU
          'has_previous': self.queue.current_index > 0,
          ...
      }
  ```
  Between `get_current_track()` (which acquires/releases `QueueManager._lock`) and `self.queue.tracks.copy()`, another thread can call `remove_track()` which under `_lock` adjusts both `tracks` and `current_index`. The snapshot then contains:
  - `current_track` from before the remove
  - `tracks` from after the remove (shorter list)
  - `current_index` from after the remove (adjusted)
  - `has_next` computed from after-remove `current_index` vs. after-remove `tracks`
  ...but with `current_track` pointing to an entry that is now at a different index.
- **Impact**: Frontend receives inconsistent queue state: `current_track` may not match `tracks[current_index]`; `has_next` / `has_previous` may be wrong. UI shows wrong track highlighted or incorrect navigation buttons. Not a crash, but an observable correctness failure.
- **Suggested Fix**: Add a `get_queue_info()` method to `QueueManager` that holds `_lock` for the entire composite read, or have `QueueController.get_queue_info()` call `self.queue.get_queue()` (which uses `with self._lock`) and then compute the derived fields from that locked snapshot.

---

## Dimension 5: Frontend State Consistency

*No new findings. F3 (deferred subscription reconnect) remains open from AUDIT_INCREMENTAL_2026-02-18. C-17 and C-18 remain open from prior audits.*

---

## Architecture Observation: SimpleChunkCache Per-Request Instantiation Defeats Cross-Request Caching

- **Not a concurrency finding** — this is a performance regression but does not cause race conditions.
- **Location**: `auralis-web/backend/audio_stream_controller.py:171`, `auralis-web/backend/routers/system.py:238-253`
- **Observation**: Each streaming coroutine creates a new `AudioStreamController` with a fresh `SimpleChunkCache`. Chunks processed in one request are never reused by a subsequent request for the same track. The cache comment "avoids reprocessing chunks" is only valid within a single streaming session (i.e., when consecutive chunks of the same request are processed). Seeking, A/B toggle, or page refresh triggers full reprocessing even for recently-processed chunks.
- **Note**: This same architectural change that causes C-21 (per-request instantiation) also causes this regression. Fixing C-21 by making the controller a singleton would automatically restore cache sharing.

---

## Findings Skipped (Confirmed Duplicates or Out of Scope)

| Finding Candidate | Matches Existing |
|-------------------|-----------------|
| GaplessPlaybackEngine.prebuffer_callbacks not locked | #2412 |
| PlaybackController.add_callback not thread-safe | #2308 |
| FingerprintRepository raw sqlite3 bypass | C-10 (partial fix ongoing) |
| asyncio.Semaphore._value private attribute in ProcessingEngine | I-01 (AUDIT_INCREMENTAL_2026-02-18) |
| useWebSocketSubscription reconnect deferred subscribers lost | F3 (AUDIT_INCREMENTAL_2026-02-18) |

---

## Related Prior Audits

- [AUDIT_CONCURRENCY_2026-02-17.md](AUDIT_CONCURRENCY_2026-02-17.md) — 20 findings, 7 confirmed fixed in this audit
- [AUDIT_INCREMENTAL_2026-02-18.md](AUDIT_INCREMENTAL_2026-02-18.md) — I-01 (asyncio.Semaphore._value), I-02 (batch_update mixed flags), F3 (reconnect deferred subscribe)
- [AUDIT_ENGINE_2026-02-18.md](AUDIT_ENGINE_2026-02-18.md) — parallel DSP fixes verified
