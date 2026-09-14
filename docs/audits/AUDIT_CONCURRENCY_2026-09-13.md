# Concurrency & State Integrity Audit — 2026-09-13

- **Scope**: all 5 dimensions (Player Thread Safety, Audio Processing, Backend Streaming, Library & Database, Frontend State)
- **Depth**: deep (full execution-path traces) · **Limit**: none
- **Tree**: `master` at `ce119be1`
- **Method**: fresh static analysis of the live source, one sub-agent per dimension. No prior report was reused. Every finding was re-checked against the code by the orchestrator before merging, and severities were re-calibrated where the trigger or impact did not hold up (see each finding's **Calibration** line). No tests were run.
- **Dedup baseline**: `gh issue list` (134 open, last 1000 all-state), plus today's sibling reports (`docs/audits/AUDIT_ENGINE_2026-09-13.md`, `docs/audits/AUDIT_INTEGRATION_2026-09-13.md`) and the backend audit's already-reported `handle_stop`/`transition_lock` finding.
- **Intentional change, not a finding**: enhancement presets narrowed to `'adaptive'` only (2026-09-13, `c195ac80` / `ae9d28e3`).

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 6 |
| LOW | 7 |
| **Total** | **13** |

Five sub-agent HIGHs were re-verified and each came down one or two levels. C2-1, C1-1, C3-3 and C3-4 moved to MEDIUM; C3-1 moved to LOW because its stall premise rests on a stale code comment. No CRITICAL or HIGH finding survived verification. This subsystem is heavily hardened: nearly every lock in the player, library and frontend streaming layers carries an issue-numbered fix, and most candidate races were disproved by a fix that is still in place.

### Key themes

1. **The streaming path's `ProcessorFactory` is a shared, non-leased cache.** `ProcessorPool` (offline jobs) pops an instance on checkout and discards poisoned ones. `ProcessorFactory`, used by every live chunk, returns the same `HybridProcessor` to every caller with a matching key. The processor's EQ and limiter carry state from one `process()` call to the next, so two concurrent consumers interleave that state (C2-1). A hung DSP call also leaves the shared instance wedged, with no eviction (C3-4). The proactive buffer is a second concurrent consumer that nothing cancels (C3-5).
2. **Protocols applied to one method but not its siblings.** `set_queue`'s generation protocol does not cover `clear_queue` and the other queue mutators (C1-1). `jump_to_track` broadcasts under the sequencer lock that `next_track` and `previous_track` correctly release first (C3-3). `_scan_folders_lock` guards 2 of the 4 write paths on the settings row (C4-1). One cache-hit per-chunk call still uses the default executor after #5086 (C3-2).
3. **Frontend staleness guards are uneven.** `fingerprint_progress` ignores `track_id` (C5-1). `audio_stream_start` is adopted without an ordering check (C5-2, currently unreachable because the backend serializes per connection).

### Most impactful races

- **C2-1**: live enhanced chunks and background builds (proactive buffer, Tier-2 cache worker) share one `HybridProcessor`'s continuity state, so chunk order through the limiter and EQ is not preserved. This risks audible level or EQ discontinuities in live playback, and it bakes them into cached chunk WAVs.
- **C3-4**: one genuinely hung DSP call permanently wedges that track at that preset until the backend restarts.
- **C1-1**: a Clear Queue landing inside an in-flight `set_queue` leaves the engine playing a track that is not in the empty queue, while the UI shows nothing playing.

## Concurrency Matrix

| Component | Shared by | Lock / mechanism | Status |
|---|---|---|---|
| `AudioPlayer` + mixins (`auralis/player/enhanced_audio_player.py`) | audio thread, auto-advance thread, backend `to_thread` workers | `PlaybackController._lock` (RLock), `AudioFileManager._audio_lock`, `defer_notifications()` outer nesting (#3781) | Safe; C1-4 (unlocked `audio_data`/`reference_data` getters, no production reader) |
| `GaplessPlaybackEngine` (`auralis/player/gapless_playback_engine.py`) | prebuffer thread, audio thread | `update_lock` + `_audio_lock` swap, `advance_if_next_matches` peek/commit (#3352), lock-free disk fallback (#5105) | Safe |
| `QueueManager` / `QueueController` (`auralis/player/components/queue_manager.py`, `auralis/player/queue_controller.py`) | audio thread, prebuffer thread, backend services | `QueueManager._lock` (RLock) per call | Per-call safe; C1-2 (clear+repopulate not atomic) |
| `QueueService` (`auralis-web/backend/services/queue_service.py`) | concurrent REST requests (event loop) | `_set_queue_lock` + `_set_queue_engine_lock` (asyncio) + generation counter, **set_queue only** | **C1-1**, C1-3 |
| `PlaybackService` (`auralis-web/backend/services/playback_service.py`) | REST + WS transport | `playback_event_sequencer.transition_lock` (process-wide asyncio.Lock); broadcast outside the lock (#4581) | C3-1 (engine call inside the lock; LOW); sibling `handle_stop` finding already reported by the backend audit |
| `NavigationService` (`auralis-web/backend/services/navigation_service.py`) | REST next/previous/jump | `_TrackChangeSequencer.lock` (asyncio) | next/previous safe; **C3-3** (`jump_to_track`) |
| `RealtimeProcessor` / `AutoMasterProcessor` (`auralis/player/realtime/`) | audio callback thread | owning `_lock` | Safe |
| `HybridProcessor` (`auralis/core/hybrid_processor.py`) | every stream/job that resolves the same factory key | `_process_lock` (RLock) on `process()` and all mutators (#3787) | Data-race safe; **C2-1** ordering, **C3-4** hang |
| `ProcessorFactory` (`auralis-web/backend/core/processor_factory.py`) | live streams, proactive buffer, Tier-2 worker | `threading.Lock` on the cache dict; **no lease, no discard-on-timeout** | **C2-1**, **C3-4** |
| `ProcessorPool` (`auralis-web/backend/core/processor_pool.py`) | offline job pipeline | asyncio.Lock, pop-on-acquire, `discard()` for poisoned instances (#4727) | Safe |
| `hybrid_processor_singleton` cache (`auralis/core/hybrid_processor_singleton.py`) | convenience API (not streaming) | lock, construction outside lock (#4689) | Safe |
| `PerformanceOptimizer` / `SmartCache` / `PerformanceProfiler` / `MemoryPool` (`auralis/optimization/`) | all mastering calls (profiling wrap is process-wide, #5142) | double-checked `threading.Lock` singleton; RLock on each | Safe; `MemoryPool` not wired to the hot path |
| Rust DSP (`vendor/auralis-dsp/src/py_bindings.rs`) | concurrent Python callers | `py.allow_threads` + `catch_unwind`, no global mutable state | Safe |
| `MasteringTargetService` (`auralis-web/backend/core/mastering_target_service.py`) | streams | RLock; fresh dict per call | Safe |
| Stream semaphore / look-ahead (`auralis-web/backend/core/stream_enhanced.py` and siblings) | per-connection streams | release in `finally`; look-ahead drained; `drain_cancelled_task` uses `Task.cancelling()` (#5083) | Safe |
| Proactive buffer task (`auralis-web/backend/core/proactive_buffer.py`) | spawned per enhanced stream start | untracked `spawn_background_task` | C3-5 (not cancellable) and a trigger for C2-1 |
| Executors (`auralis-web/backend/core/executors.py`) | per-chunk DSP vs scan/repository work | stream pool vs I/O default pool (#5086) | C3-2 (cache-hit branch on the I/O pool) |
| Chunk / thumbnail caches (`auralis-web/backend/core/encoding/atomic_io.py`, `auralis-web/backend/core/chunk_cache_manager.py`, `auralis-web/backend/cache/manager.py`) | concurrent writers | unique temp + fsync + `os.replace`; `is_wav_complete` read gate; per-key thumbnail lock | Safe (duplicate work is #5258) |
| Job worker (`auralis-web/backend/core/job_worker.py`) | job queue | `acquired` flag; bounded `stop()`; startup watchdog | Safe |
| `LibraryDatabase` (`auralis/library/database.py`) | all repositories | `check_same_thread=False`, `pool_pre_ping=True`, WAL + `busy_timeout` on every connection; scan slots on the shared instance | Safe |
| Migrations (`auralis/library/migration_lock.py`) | startup | same-process `threading.Lock` **and** `fcntl`/`msvcrt` file lock; double-checked; runs before lifespan `yield` | Safe |
| Fingerprint claims / upsert / play count (`auralis/library/repositories/`) | fingerprint workers, REST | DB-level atomic claim / `ON CONFLICT` / `UPDATE ... + 1` | Safe |
| `SettingsRepository` (`auralis/library/repositories/settings_repository.py`) | REST settings routes | `_scan_folders_lock` on add/remove only | **C4-1** |
| `ResizableSemaphore` / resource monitor (`auralis/services/resizable_semaphore.py`, `auralis/library/resource_monitor.py`) | fingerprint workers | one `Condition`; one-directional lock order | Safe |
| Frontend player-state sync (`auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts`) | WS messages | four independent monotonic seq watermarks, reset on reconnect | Safe |
| Frontend enhancement/transport (`auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts`, `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx`) | rapid user actions | per-setter requestId (#4339), `commandPendingRef` coalescing, AbortController | Safe |
| Frontend streaming ingest (`auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts`) | WS frames → PCM buffer → worklet | main-thread-only buffer; chunk epoch equality check | C5-2 (defense in depth) |
| Frontend fingerprint status (`auralis-web/frontend/src/hooks/enhancement/useFingerprintStatus.ts`) | WS `fingerprint_progress` | none | C5-1 |

## Findings

### CRITICAL

None.

### HIGH

None survived verification. See the calibration notes on C2-1, C1-1, C3-3, C3-4 and C3-1.

### MEDIUM

### C2-1: Live streams and background chunk builders share one `HybridProcessor`, so its cross-chunk EQ/limiter state is fed out of chunk order
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/core/processor_factory.py:238-248`, `auralis-web/backend/core/chunked_processor.py:168`, `auralis-web/backend/core/proactive_buffer.py:68-89`, `auralis-web/backend/core/stream_enhanced.py:174-179`, `auralis-web/backend/core/streamlined_processor_cache.py:195-207`, `auralis-web/backend/core/streamlined_tiers.py:44-88`, `auralis/core/hybrid_processor.py:463-487`
- **Status**: NEW (related: #4354 closed, which fixed the toggle-flag race on the same shared instance; its fix is still in place and does not cover ordering)
- **Trigger Conditions**: Two independent consumers resolve the same factory key `(track_id, preset, config_hash, targets_hash)` (intensity is not part of the key, #4707), and both run `process()` for chunks of the same track concurrently.
  1. **Proactive buffer (common)**: every enhanced stream start spawns `buffer_presets_for_track` (`auralis-web/backend/core/stream_enhanced.py:174-179`). It builds its own `ChunkedAudioProcessor` and processes chunks 0-2 while the live stream processes those same chunks. Whenever both wrappers load the same mastering targets (fingerprint already in the DB), they get the same `HybridProcessor`.
  2. **Tier-2 cache worker (rarer)**: `StreamlinedCacheWorker` (started by default, `auralis-web/backend/config/startup.py:1076-1090`) idles until `cache_manager.update_position()` seeds a snapshot. The only production callers are the preset route (unreachable now that presets are adaptive-only) and the intensity route (`auralis-web/backend/routers/enhancement.py:499`, wired at `auralis-web/backend/config/routes.py:140`). After one mid-playback intensity change, the worker builds Tier-1 `current+1` and then Tier-2 from `_building_chunk_idx` across the whole track, while the same track keeps streaming.
- **Evidence**:
  ```python
  # processor_factory.py:238-248 — cache hit hands out the shared instance (no lease)
  with self._lock:
      cached = self._processor_cache.get(cache_key)
      if cached is not None:
          self._processor_cache.move_to_end(cache_key)
          return cached

  # hybrid_processor.py — reset_limiter() docstring
  # "current_gain persists across process() calls for intra-track continuity (#2390)"
  ```
  Each `ChunkedAudioProcessor` has its own `_processor_lock`, so only `HybridProcessor._process_lock` serializes the two consumers. That prevents torn writes but imposes no chunk order. The continuity state (psychoacoustic EQ `current_gains`/`target_gains`, `brick_wall_limiter.current_gain`, dynamics manager) is reset only on the job path (`auralis-web/backend/core/job_execution.py:73-75`), never on the streaming path.
- **Impact**: Live chunk N can inherit limiter gain reduction and EQ smoothing left by a background build of a different chunk: the same region for the proactive buffer, a far region for the Tier-2 worker. The result can be a level or EQ discontinuity at a chunk seam. Chunks built this way are written to disk and later served as cache hits without reprocessing, so the discontinuity persists. There is no data corruption and the sample count is unaffected.
- **Siblings**: `ContinuousMode.last_fingerprint` / `last_coordinates` / `last_parameters` (`auralis/core/processing/continuous_mode.py`) are overwritten on every call and read back for preference learning, so the same interleave mixes their values between consumers. A dual-tab stream of the same track, or a seek whose new stream starts before the old one finishes tearing down, produces the same interleave.
- **Calibration**: Sub-agent HIGH → MEDIUM. The sharing and the carried state are verified. There is no torn data, the audibility of the mismatch has not been measured, and the more common trigger interleaves overlapping chunks, which minimizes the state difference.
- **Suggested Fix**: Make `ProcessorFactory.get_or_create` a lease like `ProcessorPool`: pop the instance on acquire and return it after the stream ends, building a second instance for the same key while one is checked out. Alternatively, give background builders (proactive buffer, Tier-2 worker) their own factory namespace so they never touch a live stream's instance. Fixing this together with C3-4 closes both.

### C3-4: `ProcessorFactory` never evicts a `HybridProcessor` whose DSP call timed out, so a genuine hang wedges that track/preset for the life of the process
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/processor_factory.py:192-319`, `auralis-web/backend/core/stream_chunk_ops.py:111-123`, `auralis-web/backend/core/chunk_streaming.py:61`, `auralis/core/hybrid_processor.py` (`process()` under `_process_lock`)
- **Status**: NEW. #4999 (closed) explicitly deferred this as a follow-up ("a proper fix … needs a `ProcessorFactory`-level discard mirroring `processing_engine._pool.discard()`") and it was never filed. Related to #4727, and to #5059 (open), which is the same gap in `StreamlinedCacheWorker`'s own wrapper cache.
- **Trigger Conditions**: A chunk's DSP call never returns. `asyncio.wait_for(..., CHUNK_PROCESS_TIMEOUT)` (30 s, `auralis-web/backend/core/audio_stream_controller.py:134`) cancels only the awaiting coroutine. The executor thread stays inside `HybridProcessor.process()` holding `_process_lock`.
- **Evidence**:
  ```python
  # stream_chunk_ops.py:116-123 — timeout path: logs and re-raises, no invalidate()
  except TimeoutError as e:
      logger.error(f"Chunk {chunk_index} DSP timed out ...")
      raise TimeoutError(...) from e
  ```
  The only `ProcessorFactory.invalidate()` call is in `auralis-web/backend/core/chunk_streaming.py:61`, and it runs only from `process_chunk`'s own `except Exception`. That path is unreachable for a call that never returns. #4999's fix ends the current stream but leaves the factory entry in place.
- **Impact**: Every later stream of that `(track, preset, targets)` receives the same instance and blocks on `_process_lock` until each chunk times out. The track is effectively unplayable with enhancement until the backend restarts or 32 other keys push the entry out of the LRU.
- **Siblings**: #5059 (open, the `StreamlinedCacheWorker` wrapper cache).
- **Calibration**: Sub-agent HIGH → MEDIUM. The consequence is severe, but the trigger is speculative. A merely slow chunk (over 30 s) releases the lock when it finishes, and the Rust DSP runs under `allow_threads` + `catch_unwind`, with no known hang.
- **Suggested Fix**: On the `TimeoutError` branch (`stream_chunk_ops.py`, and its handling in `stream_enhanced_chunks.py` / `stream_seek_chunks.py`), call `processor._processor_factory.invalidate(track_id=..., preset=..., mastering_targets=...)` so the next stream gets a fresh instance. The C2-1 lease model subsumes this.

### C1-1: `QueueService.clear_queue()` and the other queue mutators bypass `set_queue`'s generation protocol, so a racing `set_queue` still loads and plays after a Clear
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis-web/backend/services/queue_service.py:80-96` (lock rationale), `:254-372` (`set_queue` / `_set_queue_impl`), `:709-748` (`clear_queue`); siblings at `:378-707`
- **Status**: NEW. Sibling gap of #3721 (closed, MEDIUM): that fix and its own comment deliberately scope the lock to `set_queue` vs `set_queue`. Not a regression.
- **Trigger Conditions**: `POST /api/player/queue/set` (Play album) is between its generation check and its `to_thread(queue.set_queue)` → `load_file` → `play` steps (hundreds of ms on a large queue or slow disk) when `clear_queue()` arrives from a double action or a second client.
- **Evidence**:
  ```python
  # clear_queue — no _set_queue_lock / _set_queue_engine_lock, no generation bump
  queue_manager.clear()
  await asyncio.to_thread(self.audio_player.stop)
  await self.player_state_manager.set_playing(False)
  await self.player_state_manager.set_track(None, None)

  # _set_queue_impl — every guard still passes, so it proceeds
  async with self._set_queue_lock:
      if generation != self._set_queue_generation:
          return result
  await asyncio.to_thread(self.audio_player.load_file, current_track.filepath)
  await asyncio.to_thread(self.audio_player.play)
  ```
- **Impact**: The engine plays a track outside the queue it just cleared (or later repopulated), while `PlayerStateManager` publishes nothing playing. Auto-advance has nothing to advance to. The user recovers by pressing play or stop. `add_track_to_queue`, `reorder_queue`, `move_track_in_queue` and `shuffle_queue`/`unshuffle_queue` can be silently discarded by the `clear()` inside `queue.set_queue()`.
- **Siblings**: `add_track_to_queue`, `remove_track_from_queue`, `reorder_queue`, `move_track_in_queue`, `shuffle_queue`/`unshuffle_queue` in the same file.
- **Calibration**: Sub-agent HIGH → MEDIUM, matching #3721's rating for the same desync class: the user can recover, and the race needs a user action inside a sub-second window.
- **Suggested Fix**: Run every queue-shape mutator under `_set_queue_engine_lock` (it covers no broadcast, so #4825 is not reintroduced), and bump `_set_queue_generation` in `clear_queue()` so an in-flight `_set_queue_impl` aborts before `load_file()` / `play()`.

### C3-3: `jump_to_track` broadcasts player state while holding `_TrackChangeSequencer.lock`
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/navigation_service.py:260-278`; `auralis-web/backend/core/state_manager.py:124-139`
- **Status**: NEW (same bug class as #3732 and #4581, both closed)
- **Trigger Conditions**: A client jumps to a queue entry while a WebSocket client is slow to drain (backgrounded window, congested socket), and a concurrent next/previous/jump arrives.
- **Evidence**:
  ```python
  async with _sequencer.lock:
      ...
      await asyncio.to_thread(self.audio_player.play)
      await self.player_state_manager.set_playing(True)   # broadcast=True by default
      seq = _sequencer.next_seq()
  ```
  `set_playing()` awaits `broadcast_state()` when `broadcast=True`. That is bounded by `BROADCAST_SEND_TIMEOUT = 2.0` per client (`auralis-web/backend/config/globals.py:59`). `next_track` / `previous_track` in the same file broadcast after releasing the lock, and `queue_service.set_queue` passes `broadcast=False` and broadcasts afterwards.
- **Impact**: Next, previous and jump stall for up to 2 s behind one slow client, undoing the #4582 design goal that one slow WS client cannot stall the next command.
- **Siblings**: None; `jump_to_track` is the only outlier. Related logic defect, not a concurrency bug: `QueueController` has no `set_current_index`, so `jump_to_track` always takes the `load_file` fallback and never moves `current_index`.
- **Calibration**: Sub-agent HIGH → MEDIUM. The lock serializes only navigation, not all transport (#4581 was HIGH because it froze every control), and the stall is bounded, matching #3732 (MEDIUM).
- **Suggested Fix**: Call `set_playing(True, broadcast=False)` inside the lock and `broadcast_state(snapshot)` after releasing it, next to the existing `track_changed` broadcast.

### C3-2: Cache-hit `note_cached_chunk_level` runs on the default (I/O) executor on the per-chunk hot path
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/stream_chunk_ops.py:93-97`
- **Status**: NEW (missed site of #5086, closed)
- **Trigger Conditions**: A stream serves cache-hit chunks while a library scan or repository-heavy requests occupy the 8-worker I/O pool, which `install_executors()` installs as the loop default (`auralis-web/backend/core/executors.py`).
- **Evidence**:
  ```python
  note_level = getattr(processor, "note_cached_chunk_level", None)
  if note_level is not None:
      await asyncio.to_thread(note_level, pcm_samples, chunk_index, cached_gain_db)
  ```
  The cache-miss DSP call a few lines away uses `run_in_stream_executor` (`auralis-web/backend/core/chunk_streaming.py:208-214`).
- **Impact**: Each cache-hit chunk's delivery waits for an I/O worker. There is no `wait_for` around it, so the result is a delay rather than a timeout, but during a scan the delay can underrun the client buffer. This is exactly what the executor split was built to prevent.
- **Siblings**: None found on the per-chunk path.
- **Suggested Fix**: Call `note_cached_chunk_level` synchronously (it updates an in-memory deque), or route it through `run_in_stream_executor`.

### C4-1: `SettingsRepository._scan_folders_lock` covers only 2 of the 4 write paths on the singleton settings row
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/settings_repository.py:32` (lock), `:34-50` (`get_settings`), `:52-108` (`update_settings`), `:110-127` (`reset_to_defaults`), `:141-183` (guarded `add_scan_folder` / `remove_scan_folder`); `auralis-web/backend/routers/settings.py:326-340`
- **Status**: NEW (related: #3339 and #4956 introduced the lock; #4765 is closed)
- **Trigger Conditions**: `POST /api/settings/scan-folders` (locked) runs concurrently with `PUT /api/settings` carrying `scan_folders` (unlocked) or `POST /api/settings/reset` (unlocked). A background auto-save plus a folder dialog, or two windows, is enough.
- **Evidence**:
  ```python
  _scan_folders_lock = threading.RLock()            # used only at :143 and :165
  def update_settings(self, updates):                # no lock
      if 'scan_folders' in updates:
          settings.scan_folders = json.dumps(updates['scan_folders'])
  def reset_to_defaults(self):                       # no lock
      session.execute(delete(UserSettings))
  ```
  The PUT route also takes an unlocked `get_settings()` snapshot (`auralis-web/backend/routers/settings.py:331-335`) and later diffs the path allowlist against it.
- **Impact**: A just-added or just-removed scan folder is lost (last writer wins), and the allowlist diff runs against a stale snapshot, so allowlist registration can drift from the stored folder list. A `reset_to_defaults()` that deletes the row mid-`add_scan_folder` surfaces as `StaleDataError`, returned as a 500.
- **Siblings**: `QueueRepository.get_queue_state()` / `set_queue_state()` (`auralis/library/repositories/queue_repository.py`) use the same unguarded first-or-create pattern, but no router calls them.
- **Suggested Fix**: Hold one process-wide lock across the full read-modify-write and commit in all five settings methods, and take it across the PUT route's snapshot-plus-write.

### LOW

### C1-2: `QueueController.set_queue()` / `load_playlist()` clear then repopulate outside a single lock
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/queue_controller.py:227-273`, `:355-372`; `auralis/player/components/queue_manager.py:52-56`, `:213-218`
- **Status**: NEW
- **Trigger Conditions**: A backend `to_thread(queue.set_queue)` overlaps the audio thread's end-of-track `has_next_track()` or the gapless prebuffer thread's `peek_next_track()`.
- **Evidence**: `self.queue.clear()` is followed by a loop of individually locked `self.queue.add_track(track)` calls; only the trailing `current_index` write is inside `with self.queue._lock`.
- **Impact**: A reader can see a momentarily empty queue. The worst case is a skipped auto-advance or prebuffer cycle that the following `load_file` / `play` corrects.
- **Siblings**: `load_playlist()`.
- **Suggested Fix**: Hold `self.queue._lock` (an RLock) across the whole clear, repopulate and index write.

### C1-3: `remove_track_from_queue`'s `was_current` check is separated from the removal
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis-web/backend/services/queue_service.py:466-487`
- **Status**: NEW
- **Trigger Conditions**: Auto-advance, next/previous, or a second remove moves `current_index` between the two reads.
- **Evidence**: `was_current = (index == queue_manager.current_index)` and `queue_manager.remove_track(index)` take two separate lock acquisitions.
- **Impact**: A stale `was_current` either skips the reload/stop follow-up (the #2403 desync) or reloads a track that is still current.
- **Siblings**: None.
- **Suggested Fix**: Add an atomic `remove_if_index_matches_current()` on `QueueManager`, modeled on `advance_if_next_matches`.

### C1-4: `AudioPlayer.audio_data` / `.reference_data` getters skip the lock their setters take
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/player_properties_mixin.py:73-91`
- **Status**: NEW
- **Trigger Conditions**: A read races `load_file()`, the gapless swap, or the setters.
- **Evidence**: `return self.file_manager.audio_data` has no `_audio_lock`, while the setter and the `current_file` / `sample_rate` getters lock.
- **Impact**: A stale composite read, not a torn array. No production code reads these getters (tests only).
- **Siblings**: None.
- **Suggested Fix**: Wrap both getters in `with self.file_manager._audio_lock:`.

### C3-1: `PlaybackService` runs engine calls inside the process-wide `transition_lock`, and the seek comment that justifies it is stale
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/playback_service.py:316-325` (`seek`), plus `play` / `pause` / `stop`; `auralis-web/backend/services/playback_event_sequencer.py:14-48`
- **Status**: NEW. Related to the backend audit's already-reported `handle_stop` finding (same lock) and to #4581 / #4751 (closed; broadcasts under this lock).
- **Trigger Conditions**: A REST seek while WS pause/resume/stop or another transport call arrives.
- **Evidence**: `async with self._playback_lock:` wraps `await asyncio.to_thread(self.audio_player.seek, position)`. The comment above it says `load_file()` can hold `_audio_lock` for "hundreds of ms to seconds while decoding". That is no longer true: `auralis/player/audio_file_manager.py:59-64` decodes outside the lock and only swaps under it, and the gapless disk fallback also runs lock-free (#5105).
- **Impact**: Transport commands serialize behind a short engine call. No multi-second stall is reachable today.
- **Siblings**: `play()`, `pause()`, `stop()` in the same file.
- **Calibration**: Sub-agent HIGH → LOW. The lock scope is verified, but the multi-second blocking premise depends on the stale comment.
- **Suggested Fix**: Correct the comment. Optionally move the `to_thread(audio_player.*)` calls out of the lock, since `seek()` allocates no seq and mutates no `PlayerStateManager` state.

### C3-5: Proactive-buffer task is untracked and survives stop, seek and disconnect
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/stream_enhanced.py:174-179`, `auralis-web/backend/core/proactive_buffer.py:26-118`
- **Status**: NEW. #5281 (open, LOW) says `buffer_presets_for_track` is never called, which the current source contradicts: it is called on every enhanced stream start. #5281 should be re-verified and closed or re-scoped.
- **Trigger Conditions**: The user stops, seeks, or disconnects right after an enhanced play starts.
- **Evidence**: `spawn_background_task(buffer_presets_for_track(...))` returns a bare task that is never registered with `_cancel_prior_task` / `handle_stop` / connection teardown.
- **Impact**: Up to 3 chunks of DSP keep running after the user moves on, contending for the shared processor. More importantly, this task is the common trigger for C2-1.
- **Siblings**: None.
- **Calibration**: Sub-agent MEDIUM → LOW. The work is bounded and ends on its own, and the harmful effect is reported under C2-1.
- **Suggested Fix**: Register the task in the per-`ws_id` structures that stop and seek already drain, or remove proactive buffering now that only one preset exists.

### C5-1: `fingerprint_progress` is applied without a `track_id` check
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useFingerprintStatus.ts:74-92`
- **Status**: NEW
- **Trigger Conditions**: Track A's `fingerprint_progress` is in flight when the user skips to B. `resetFingerprint()` runs at click time, and A's message lands after it.
- **Evidence**: The handler destructures only `status` and `message` from `message.data` and ignores `data.track_id`. The stream reducers in `playerStreamingReducers.ts` gate on `trackId` (#4434).
- **Impact**: The fingerprint status shown for B briefly reflects A. The live enhanced path (`check_or_queue_fingerprint`, `auralis-web/backend/core/stream_fingerprint.py:120-180`) only emits `complete` for cached fingerprints, and `complete` auto-clears after 2 s. Sends inside the cancelled stream task cannot fire late, because `CancelledError` bypasses `except Exception`.
- **Siblings**: None.
- **Calibration**: Sub-agent MEDIUM → LOW. The effect is cosmetic, self-clearing, and limited to the message already in flight.
- **Suggested Fix**: Drop messages whose `data.track_id` does not match the current track ref.

### C5-2: `audio_stream_start` is adopted without an ordering check (defense in depth)
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:403-426` (also audioChunkIngest.ts and useEnhancedStreamStart.ts in the same hook family)
- **Status**: NEW
- **Trigger Conditions**: Currently unreachable. `auralis-web/backend/routers/system.py` awaits each WS `dispatch_message`, and `_cancel_prior_task` in `auralis-web/backend/ws_handlers/playback_commands.py` awaits the previous task's cancellation before creating the next stream, so a stale start cannot follow a newer one on a single connection.
- **Evidence**: `streamEpochRef.current = start.data?.stream_epoch ?? null` is overwritten unconditionally, and the chunk filter only checks `incomingEpoch !== currentEpoch` (equality, not ordering).
- **Impact**: If the backend serialization is ever relaxed, the frontend would revert to the older stream and reject the newer track's progress events.
- **Siblings**: None.
- **Suggested Fix**: Reject an `audio_stream_start` whose `stream_epoch` is lower than the current one.

## Relationships

- **R1: shared `ProcessorFactory` instance (C2-1, C3-4, C3-5, #5059).** One design gap: the live streaming path has no lease or discard, unlike `ProcessorPool`. C3-5's untracked proactive buffer is the everyday trigger for C2-1's interleaving. C3-4 is the hang variant of the same sharing, and #5059 is the same poisoning one layer up, in the Tier-2 worker's wrapper cache. A lease-plus-discard model in `ProcessorFactory` closes C2-1 and C3-4 and makes C3-5 harmless.
- **R2: lock held across a slow await (C3-3, C3-1, backend audit's `handle_stop`).** All three sit on the transport and navigation serialization locks introduced by #3734 and #4582. The broadcast-outside-the-lock rule from #3732 and #4581 was applied per method and missed `jump_to_track` (C3-3). C3-1 is the benign engine-call variant on the same `transition_lock` that the backend audit's `handle_stop` finding holds across task teardown.
- **R3: queue-mutation protocol coverage (C1-1, C1-2, C1-3).** `set_queue` has a generation protocol, `advance_if_next_matches` has atomic peek-and-commit, and the remaining queue mutators have neither. C1-1's aftermath (engine playing, state saying stopped) compounds with INT-F9-03 from the integration audit, where the backend auto-advances on a wall-clock guess: the two layers can then disagree about both the track and the play state. `jump_to_track` never updating `current_index` (noted under C3-3) is a further source of queue-index drift.
- **R4: frontend trusts backend serialization (C5-1, C5-2).** Both are safe or near-safe only because `routers/system.py` dispatches serially and `_cancel_prior_task` awaits cancellation. A regression in either backend invariant would make C5-2 live and widen C5-1.
- **R5: singleton-row writes (C4-1).** This follows the #3339/#4956 lock pattern but stops two methods short. It is unrelated to the engine audit's ENG-D4-02 (`.bak` path collision in concurrent metadata edits), though both are last-writer-wins on user-edited data.

## Prioritized Fix Order

1. **C2-1 + C3-4 (+ C3-5)**: one change. Make `ProcessorFactory` lease-exclusive with discard on timeout, or isolate background builders. It removes the only audio-path concurrency defect found and the one permanent-wedge failure mode.
2. **C3-3**: a two-line fix (`broadcast=False` plus a deferred broadcast) that restores the #4582 guarantee.
3. **C1-1 (+ C1-3, C1-2)**: extend the queue protocol to every mutator. This prevents a user-visible audio/UI desync and removes queue-index races that feed INT-F9-03.
4. **C3-2**: a one-line executor fix on the chunk hot path, most noticeable while a scan is running.
5. **C4-1**: widen the settings lock to all row writers.
6. **LOW cleanup**: C3-1 (fix the stale comment and optionally narrow the lock), C5-1 (`track_id` guard), C1-4 (lock the getters), C5-2 (epoch ordering). Separately, re-verify #5281 against `auralis-web/backend/core/stream_enhanced.py:174`.

## Existing Issues Confirmed Still Open

- **#5059** (MEDIUM): `StreamlinedCacheWorker` reuses a timed-out `ChunkedAudioProcessor`. Still present; sibling of C3-4.
- **#5258** (LOW): no single-flight dedup for concurrent same-key chunk renders. Still present, and it extends to `auralis-web/backend/core/chunk_batch.py`. Atomic writes keep it a performance issue only.
- **#5068** (LOW): blocking `shutil.rmtree` on the event loop during lifespan temp reclaim. Still present in `auralis-web/backend/config/startup.py`.
- **#5247**: `TrackRepository.update_metadata()` returns a detached `Track` without eager-loaded relationships (`auralis/library/repositories/track_repository_mutation.py`). Still present; current callers don't serialize relationships.
- **#5281** (LOW): its "never called" premise is **stale**. See C3-5.
- **#4354** (closed): the shared-processor toggle fix in `audio_processing_pipeline.py` is still in place (not regressed).
- **#5083** (closed): `drain_cancelled_task`'s `Task.cancelling()` distinction is still in place (not regressed).

## Verified Safe (highlights)

- **Player**: `PlaybackController` state plus `state_info` snapshot under `_lock`, with notifications fired outside it; `AudioFileManager` decodes outside `_audio_lock` and swaps atomically; gapless peek/load/commit with retry (#3352) and a lock-free disk fallback (#5105); `IntegrationManager._position_lock` composite reads (#3786/#4552) respect Player→Library lock ordering; fingerprint loader generation compare-and-write (#3719).
- **Engine**: `HybridProcessor._process_lock` covers `process()` and every mutator (#3787); `mastering_chunk_loop` is sequential with `.copy()`'d carried tails and serialized per pipeline (#3715); targets are deep-copied before a processor gets them; optimizer singleton uses double-checked locking; `SmartCache` / `PerformanceProfiler` / `MemoryPool` are fully locked; Rust bindings release the GIL and hold no global state.
- **Backend**: `AudioStreamController` is constructed per stream, with per-`ws_id` state under a lock; stream semaphores release in `finally` (#4329); the look-ahead task is drained on every exit; chunk and thumbnail cache writes are atomic behind a completeness gate; `ProcessorPool` pops on acquire, discards poisoned instances (#4727) and shields cleanup (#4759); job worker has an acquire flag, bounded stop, and a startup watchdog (#4318/#4819); background workers are stopped and awaited before the engine is disposed.
- **Library**: `check_same_thread=False`, `pool_pre_ping=True`, and WAL/`busy_timeout` pragmas on every pooled connection; scan slots and paths are held on the shared `LibraryDatabase` and released on every exit; migrations take both the thread lock and the file lock, are double-checked, and finish before requests are served; fingerprint claim, upsert, play-count increment and playlist reorder are all DB-atomic.
- **Frontend**: four independent seq watermarks reset on reconnect; chunk seq-desync detection resets per epoch; the PCM buffer is touched only from the main thread (the worklet receives cloned arrays); the shared-promise memo clears on rejection; requestId supersession for preset/intensity; per-field generation rollback for optimistic queue edits; transport command coalescing; AbortController supersession for play commands; WS singleton reuse across StrictMode remounts; queue-then-resume replay without a double send.

## Dismissed Candidates (notable)

- **Plain-`bool` stop flags** (`fingerprint_queue.py`, scanner `file_discovery.py` / `batch_processor.py`): these would race only under free-threaded CPython, which #4962 records as a hard build failure for the Rust DSP crate. They are atomic under the GIL.
- **`LibraryDatabase.shutdown()` unsynchronized `self.engine` read**: the atexit call and the lifespan teardown run sequentially, never concurrently.
- **`cache/manager.py` `get_chunk` / `add_chunk` lock asymmetry**: there is no suspension point between check and mutation on the event loop.
- **Stage-level `processed = audio` aliasing** (`bass_enhancement`, `sub_bass_control`): the caller already copies (`mastering_process_chunk.py`), so the buffer is private to one call.
- **`handle_pause` / `handle_resume` under `transition_lock`**: only synchronous work runs inside the lock.
- **Concurrent `next_track` (user skip plus auto-advance)**: `advance_if_next_matches` is designed so each legitimate request advances exactly once.
- **Old stream's chunks landing after a newer skip or seek**: prevented by backend per-connection serialization; recorded as C5-2 (defense in depth).
- **Genre/playlist delete TOCTOU**: genre delete has no router caller, and the playlist route is deliberately idempotent (#4734).

## Coverage and Confidence

- All 5 dimensions ran to completion. Findings come from static analysis only; the timing windows (C1-1, C2-1, C3-3) were not reproduced under load.
- Confidence is high on the existence of every finding: each has code evidence re-read by the orchestrator. Confidence in the severities is medium. C2-1's audibility is unmeasured, and C3-4 depends on a hang that has not been observed.
- Not re-audited here: the four items already reported by today's sibling audits (backend `handle_stop` under `transition_lock`, ENG-D4-02, INT-F4-04, INT-F9-03). They are referenced above where relevant.

---

Publish with: `/audit-publish docs/audits/AUDIT_CONCURRENCY_2026-09-13.md`
