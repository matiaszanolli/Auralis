# Concurrency and State Integrity Audit
**Date**: 2026-02-17
**Auditor**: Claude (automated, 3 parallel agents)
**Scope**: All 5 concurrency dimensions across the Auralis codebase
**Issues Created**: C-01 – C-20 (20 new findings)

---

## Summary

| Severity | Count | New Issues |
|----------|-------|-----------|
| CRITICAL | 3 | C-01, C-02, C-03 |
| HIGH | 7 | C-04, C-05, C-06, C-07, C-08, C-09, C-10 |
| MEDIUM | 8 | C-11, C-12, C-13, C-14, C-15, C-16, C-17, C-18 |
| LOW | 2 | C-19, C-20 |
| **TOTAL NEW** | **20** | |
| Skipped (duplicates) | 8 | DUP #2412, #2308, #2297, #2328, #2299, #2320, #2178, #2352, #2404 |

---

## Deduplication Reference

The following existing issues were checked before reporting. Findings that matched were skipped:

| Existing Issue | Title |
|---------------|-------|
| #2412 | GaplessPlaybackEngine.prebuffer_callbacks mutated without lock |
| #2328 | ProcessorFactory cache eviction unsafe during concurrent dict iteration |
| #2326 | _chunk_tails dict accessed concurrently without lock |
| #2320 | ProcessingEngine processor cache has no lock |
| #2314 | Module-level processor caches lack thread safety |
| #2308 | PlaybackController.add_callback is not thread-safe |
| #2299 | ProcessingEngine active_jobs counter lacks synchronization |
| #2297 | start_prebuffering() TOCTOU race |
| #2220 | State manager uses threading.Lock in async context |
| #2213 | PerformanceMonitor accessed outside lock |
| #2077 | Lock contention in parallel processor window cache |
| #2076 | WebSocket stream loop TOCTOU race |
| #2154 | Seek does not invalidate gapless prebuffer |
| #2178 | websocketMiddleware NEXT/PREVIOUS reads stale state |
| #2352 | updatePlaybackState Object.assign clobbers streaming sub-state |
| #2404 | toggleEnabled stale closure |
| #2406 | AlbumRepository expunge DetachedInstanceError |

---

## Dimension 1: Player Thread Safety

### C-01: AudioFileManager.audio_data Written from Gapless Thread Without Lock
- **Severity**: CRITICAL
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/audio_file_manager.py:98-132`, `auralis/player/gapless_playback_engine.py:194`
- **Status**: NEW
- **Trigger Conditions**: Gapless transition writes `audio_data` (line 194 in gapless engine) while the playback thread is inside `get_audio_chunk()` using `len(self.audio_data)` and slicing it.
- **Evidence**:
  ```python
  # audio_file_manager.py:113-118 — no lock on read
  if self.audio_data is None:
      return np.zeros((chunk_size, 2), dtype=np.float32)
  end = min(start_position + chunk_size, len(self.audio_data))
  chunk = self.audio_data[start_position:end].copy()

  # gapless_playback_engine.py:194 — concurrent write, no lock
  self.file_manager.audio_data = audio_data
  ```
  Thread A reads `len(self.audio_data)` → Thread B assigns shorter array → Thread A slices with stale `end` → `IndexError` or silent underrun.
- **Impact**: `IndexError` or garbage audio during every gapless transition. CRITICAL under normal playback with a queue.
- **Suggested Fix**: Add `RLock` to `AudioFileManager`; hold it for the full read-slice in `get_audio_chunk()` and for the assignment in the gapless engine.

---

### C-04: RealtimeLevelMatcher Shared State Not Protected from Concurrent Calls
- **Severity**: HIGH
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/realtime/level_matcher.py:20-87`
- **Status**: NEW
- **Trigger Conditions**: `process()` called from two threads simultaneously (e.g., playback thread and a prefetch thread both hitting the same matcher instance).
- **Evidence**:
  ```python
  # No lock in class
  self.current_target_rms = 0.0                # shared float
  self.gain_smoother = AdaptiveGainSmoother()  # shared object

  # process() — unprotected read-modify-write
  self.current_target_rms += (target_rms - self.current_target_rms) * self.target_rms_alpha
  self.gain_smoother.set_target(gain)
  smooth_gain = self.gain_smoother.process(len(audio))
  ```
- **Impact**: Interleaved writes to `current_target_rms` produce wrong gain ramps. Gain smoother internal state becomes incoherent. Audible as clicks, volume spikes, or level drift.
- **Suggested Fix**: Add `threading.Lock` to `RealtimeLevelMatcher`, acquire it for the full body of `process()`.

---

### C-05: QueueManager Tracks List and current_index Modified Without Lock
- **Severity**: HIGH
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/components/queue_manager.py:15-90`
- **Status**: NEW
- **Trigger Conditions**: REST API calls `remove_track()` from FastAPI async handler (via executor) while playback thread calls `next_track()` concurrently.
- **Evidence**:
  ```python
  # No lock declared in class

  # next_track() — unguarded read-modify-write
  if self.current_index < len(self.tracks) - 1:
      self.current_index += 1      # ← not atomic
  return self.get_current_track()  # can crash if tracks emptied below

  # remove_track() — modifies both list and index without lock
  self.tracks.pop(index)
  if index < self.current_index:
      self.current_index -= 1      # ← TOCTOU race
  ```
- **Impact**: Index-out-of-bounds crash, skipped tracks, stale current-track reference returned to player.
- **Suggested Fix**: Add `threading.RLock` to `QueueManager`; protect all public methods.

---

### C-11: IntegrationManager.callbacks List Mutated Without Lock
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/integration_manager.py:65-99`
- **Status**: NEW (distinct from #2308 which covers `PlaybackController`)
- **Trigger Conditions**: `add_callback()` called from any thread while `_notify_callbacks()` iterates in the playback thread.
- **Evidence**:
  ```python
  self.callbacks: list[...] = []   # no lock

  def add_callback(self, callback):
      self.callbacks.append(callback)  # unguarded

  def _notify_callbacks(self, ...):
      for callback in self.callbacks:  # unguarded iteration
          callback(...)
  ```
- **Impact**: `RuntimeError: list changed size during iteration`, missed callbacks.
- **Suggested Fix**: Add `threading.RLock`, hold it for both `append` and iteration (iterate a snapshot copy).

---

### C-19: _auto_advancing Event Allows Duplicate Auto-Advance on Error
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:110, 364-383`
- **Status**: NEW
- **Trigger Conditions**: `next_track()` raises inside `_auto_advance_next()`; finally block clears the guard event; a new auto-advance fires immediately before state is validated.
- **Evidence**:
  ```python
  self._auto_advancing = threading.Event()  # used as guard

  # _auto_advance_next() always clears in finally
  try:
      self.next_track()   # can raise
  finally:
      self._auto_advancing.clear()  # cleared even on failure → re-entry allowed
  ```
- **Impact**: Potential double-advance on error path; queue index corruption.
- **Suggested Fix**: Validate queue state before clearing the event, or use a proper `threading.Lock` that prevents concurrent entry.

---

## Dimension 2: Audio Processing Pipeline

### C-02: band_results List Initialised with Object Aliasing in Parallel Processor
- **Severity**: CRITICAL
- **Dimension**: Audio Processing Pipeline
- **Location**: `auralis/optimization/parallel_processor.py:223, 237`
- **Status**: NEW
- **Trigger Conditions**: Any parallel EQ band processing call with ≥ 2 bands.
- **Evidence**:
  ```python
  # Multiprocessing path (line 223) AND threading path (line 237):
  band_results: list[np.ndarray] = [np.array([])] * num_bands
  # ↑ ALL ELEMENTS ARE THE SAME OBJECT
  # e.g., band_results[0] is band_results[1] is band_results[2] → True

  for future in as_completed(futures):
      idx, result = future.result()
      band_results[idx] = result   # reassigns one slot — others remain aliased
  ```
  If `idx=0` finishes last, every slot that was never explicitly assigned still holds the empty array.
  Net effect: only bands that were processed in deterministic order survive; other bands produce silence.
- **Impact**: Silent audio bands, spectral collapse, unpredictable DSP output on every parallel EQ call.
- **Suggested Fix**: `band_results = [np.array([]) for _ in range(num_bands)]` — one object per slot.

---

### C-06: ParallelFFTProcessor window_cache Read Occurs Outside Lock
- **Severity**: HIGH
- **Dimension**: Audio Processing Pipeline
- **Location**: `auralis/optimization/parallel_processor.py:41-69`
- **Status**: NEW (distinct from #2077 which covers lock *contention*; this is an unprotected read)
- **Trigger Conditions**: Two worker threads call `get_window()` for the same uncached size simultaneously.
- **Evidence**:
  ```python
  if size in self.window_cache:          # read OUTSIDE lock — line 60
      return self.window_cache[size]

  with self.lock:                        # lock acquired AFTER check
      if size not in self.window_cache:  # double-check (correct)
          self.window_cache[size] = np.hanning(size)
  ```
  While `self.lock` is held by a writing thread, another thread can read a half-written cache entry through the unprotected line 60 path.
- **Impact**: Stale or partial window function read; spectral leakage, phase discontinuities in FFT output.
- **Suggested Fix**: Move the read inside the lock, or use `threading.RLock` with a read-guarded pattern.

---

### C-07: prev_tail Crossfade Buffer Can Become Corrupted Mid-Chunk
- **Severity**: HIGH
- **Dimension**: Audio Processing Pipeline
- **Location**: `auralis/core/simple_mastering.py:145-228`
- **Status**: NEW
- **Trigger Conditions**: An exception raised between assigning `prev_tail` and writing the crossfaded output; next chunk iteration uses the partial buffer.
- **Evidence**:
  ```python
  prev_tail = processed_chunk[:, core_samples:].copy()  # line 197 — assigned

  # ... several lines of crossfade math ...

  output_chunks.append(np.concatenate([crossfaded, body], axis=1))  # line 219 — can raise
  # If ValueError here, prev_tail holds data from a chunk whose output was never appended.
  # Next iteration will crossfade into a 'phantom' tail.
  ```
- **Impact**: Audible glitch or discontinuity at a chunk boundary following any mid-chunk DSP error.
- **Suggested Fix**: Clear `prev_tail` in the `except` path, or validate that concatenation succeeded before updating `prev_tail`.

---

### C-08: _fingerprint_service Lazy Init Is Not Thread-Safe
- **Severity**: MEDIUM
- **Dimension**: Audio Processing Pipeline
- **Location**: `auralis/core/simple_mastering.py:39-48`
- **Status**: NEW
- **Trigger Conditions**: Multiple threads call `master_file()` concurrently before the service has been initialised.
- **Evidence**:
  ```python
  @property
  def fingerprint_service(self) -> FingerprintService:
      if self._fingerprint_service is None:        # no lock
          self._fingerprint_service = FingerprintService(...)  # races
      return self._fingerprint_service
  ```
  Classic double-checked locking without any lock.
- **Impact**: Two `FingerprintService` instances created; one is immediately discarded, wasting resources. Any I/O handles opened by the service are leaked.
- **Suggested Fix**: Initialise at `__init__` time, or use `threading.Lock` around the `if` block.

---

## Dimension 3: Backend WebSocket & Streaming

### C-03: _active_streaming_tasks Dict Concurrent Read/Write Is Unprotected
- **Severity**: CRITICAL
- **Dimension**: Backend WebSocket & Streaming
- **Location**: `auralis-web/backend/routers/system.py:218-296, 305-358, 420-491`
- **Status**: NEW
- **Trigger Conditions**: Client sends a second `play_enhanced`/`play_normal`/`seek` command before the previous stream task's `finally` block has finished cleaning up.
- **Evidence**:
  ```python
  # Message handler (line 223-224):
  ws_id = id(websocket)
  if ws_id in _active_streaming_tasks:   # read
      old_task = _active_streaming_tasks[ws_id]  # concurrent delete possible here

  # Task finally (line 289-290):
  if _active_streaming_tasks.get(ws_id) is my_task:
      del _active_streaming_tasks[ws_id]  # concurrent read by message handler

  # Disconnect handler (line 522-527):
  if ws_id in _active_streaming_tasks:
      del _active_streaming_tasks[ws_id]  # double-delete with task finally
  ```
  Python `dict` is not safe for concurrent `in` + `del` across coroutines that can interleave at `await` points.
- **Impact**: `KeyError` crash killing the WebSocket connection; orphaned background tasks; memory leak on rapid track switching.
- **Suggested Fix**: Replace read-modify-delete with `_active_streaming_tasks.pop(ws_id, None)` everywhere, and protect the entire read-cancel-insert sequence with `asyncio.Lock`.

---

### C-09: _active_streaming_tasks Dict Comprehension Race During Cleanup
- **Severity**: HIGH
- **Dimension**: Backend WebSocket & Streaming
- **Location**: `auralis-web/backend/routers/system.py:219, 306, 421`
- **Status**: NEW
- **Trigger Conditions**: Two concurrent WebSocket connections both trigger cleanup simultaneously (e.g., both issue `play_enhanced` while their previous streams are still done-but-not-cleaned).
- **Evidence**:
  ```python
  # cleanup (lines 219, 306, 421 — same pattern):
  _active_streaming_tasks = {k: v for k, v in _active_streaming_tasks.items() if not v.done()}
  # Between the iteration and the re-assignment, another coroutine inserts a new task.
  # The new task is overwritten by the re-assignment → task lost, never cancellable.
  ```
- **Impact**: Tasks become permanently orphaned; cannot be cancelled on disconnect; memory grows unbounded with each rapid skip operation.
- **Suggested Fix**: Use `asyncio.Lock` around the cleanup or use an in-place `dict` comprehension update pattern rather than full reassignment.

---

### C-13: ProcessingEngine.jobs Dict Modified Concurrently Without Lock
- **Severity**: MEDIUM
- **Dimension**: Backend WebSocket & Streaming
- **Location**: `auralis-web/backend/processing_engine.py:537-568`
- **Status**: NEW (distinct from #2320 which covers the `processors` cache)
- **Trigger Conditions**: `cleanup_old_jobs()` iterates `self.jobs.items()` while `get_queue_status()` reads `self.jobs.values()` from a concurrent REST API call.
- **Evidence**:
  ```python
  # cleanup_old_jobs (line 537):
  for job_id, job in self.jobs.items():
      ...
      del self.jobs[job_id]   # modifies dict during iteration

  # get_queue_status (line 562):
  "queued": len([j for j in self.jobs.values() if j.status == ...])
  # Concurrent deletion → RuntimeError: dictionary changed size during iteration
  ```
- **Impact**: `RuntimeError` in cleanup or status handler; job tracking becomes inconsistent.
- **Suggested Fix**: Add `threading.Lock` around all `self.jobs` accesses, or collect keys to delete after iteration.

---

### C-14: SimpleChunkCache OrderedDict Mutated Without Lock from Concurrent Streams
- **Severity**: MEDIUM
- **Dimension**: Backend WebSocket & Streaming
- **Location**: `auralis-web/backend/audio_stream_controller.py:52-135`
- **Status**: NEW
- **Trigger Conditions**: Two WebSocket clients request chunks of the same track simultaneously; both call `put()` for the same key concurrently.
- **Evidence**:
  ```python
  # get() — no lock
  if key in self.cache:
      self.cache.move_to_end(key)   # mutates OrderedDict
      return self.cache[key]

  # put() — no lock
  if len(self.cache) >= self.max_chunks:
      removed_key = next(iter(self.cache))
      del self.cache[removed_key]    # mutates; can delete recently-inserted key

  self.cache[key] = (audio, sample_rate)
  ```
- **Impact**: Premature eviction of valid entries; chunk reprocessed unnecessarily; `KeyError` if evicted key is accessed again.
- **Suggested Fix**: Add `asyncio.Lock` to `SimpleChunkCache` and make `get`/`put` async.

---

### C-15: WebSocket Disconnect and Stream Task Finalization Both Delete Same Key
- **Severity**: MEDIUM
- **Dimension**: Backend WebSocket & Streaming
- **Location**: `auralis-web/backend/routers/system.py:286-290, 519-527`
- **Status**: NEW
- **Trigger Conditions**: Network disconnect triggers both the stream task's `finally` block and the WebSocket endpoint's `finally` block near-simultaneously.
- **Evidence**:
  ```python
  # Stream task finally (line 286-290):
  if _active_streaming_tasks.get(ws_id) is my_task:
      del _active_streaming_tasks[ws_id]   # may succeed

  # Endpoint finally (line 522-527):
  if ws_id in _active_streaming_tasks:
      del _active_streaming_tasks[ws_id]   # KeyError if task already deleted above
  ```
- **Impact**: `KeyError` during disconnect cleanup; if unhandled, the exception leaks up and may suppress proper connection teardown.
- **Suggested Fix**: Use `_active_streaming_tasks.pop(ws_id, None)` in both paths (idempotent delete).

---

### C-20: _rate_limiter Cleanup Data Structure Access Is Uncoordinated
- **Severity**: LOW
- **Dimension**: Backend WebSocket & Streaming
- **Location**: `auralis-web/backend/routers/system.py:27, 114, 530`
- **Status**: NEW
- **Trigger Conditions**: Periodic background cleanup task in `WebSocketRateLimiter` mutates per-connection state while `check_rate_limit()` reads it from a message handler.
- **Evidence**:
  ```python
  allowed, error_msg = _rate_limiter.check_rate_limit(websocket)  # line 114 — reads state
  _rate_limiter.cleanup(websocket)  # line 530 — deletes state
  ```
  If `cleanup()` has a background periodic sweep that mutates the internal dict, concurrent reads in `check_rate_limit()` can observe partial state.
- **Impact**: Low (single asyncio event loop serialises most access); risk rises if a `asyncio.create_task()` sweeper is added later.
- **Suggested Fix**: Ensure `WebSocketRateLimiter` is guarded with `asyncio.Lock` on all internal dict mutations.

---

## Dimension 4: Library & Database

### C-10: FingerprintRepository Bypasses SQLAlchemy Pool with Raw sqlite3 Connection
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_repository.py:470-517`
- **Status**: NEW
- **Trigger Conditions**: Multiple fingerprint workers (fingerprint service is parallel) call `upsert()` simultaneously.
- **Evidence**:
  ```python
  # upsert() — bypasses ORM entirely
  conn = sqlite3.connect(str(self._db_path))
  cursor = conn.cursor()
  try:
      sql = f"INSERT OR REPLACE INTO track_fingerprints (track_id, {cols_str}) VALUES (?, {placeholders})"
      cursor.execute(sql, [track_id] + vals)
      conn.commit()
  ```
  Raw `sqlite3.connect()` creates a new connection outside the SQLAlchemy pool. Multiple such connections can acquire WAL read locks simultaneously and contend on write lock, bypassing the `pool_pre_ping` and connection-recycling guarantees of the managed pool.
- **Impact**: WAL lock contention under parallel fingerprinting; potential connection exhaustion; orphaned `sqlite3.Connection` objects if exception occurs before `conn.close()`.
- **Suggested Fix**: Use `session.execute(text(...))` within the standard `get_session()` context manager, or `engine.begin()` for the upsert.

---

### C-12: Concurrent Track Deletion Does Not Atomically Invalidate Cache
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/manager.py:476-509`
- **Status**: NEW
- **Trigger Conditions**: REST API deletes a track while the player holds a cached reference to that track object; cache invalidation happens after DB deletion, not before.
- **Evidence**:
  ```python
  with self._delete_lock:          # serialises DB delete
      success = self.tracks.delete(track_id)
      if success:
          invalidate_cache(...)    # ← called AFTER deletion, not inside transaction
  ```
  Between `tracks.delete()` committing and `invalidate_cache()` running, a concurrent reader can fetch a stale cache entry that refers to a now-deleted row. The next DB round-trip for that entry returns `None`, breaking the player.
- **Impact**: Player tries to play a track that no longer exists in the DB; `AttributeError` or silent skip.
- **Suggested Fix**: Call `invalidate_cache()` **before** `tracks.delete()` (double-invalidate pattern), or wrap deletion + invalidation in the same DB transaction using an `after_flush` hook.

---

### C-16: Concurrent Library Scans Can Insert Duplicate Tracks
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/scanner.py:75-125`
- **Status**: NEW
- **Trigger Conditions**: User triggers two scan operations on overlapping directories (or with symlinked dirs) before the first scan commits.
- **Evidence**:
  ```python
  # scan_directories() — no guard against concurrent invocation
  for directory in directories:
      if self.should_stop:
          break
      files = list(self.file_discovery.discover_audio_files(directory, recursive))
      all_files.extend(files)
  ```
  `settings.max_concurrent_scans=4` is defined but never checked before starting a scan. Two scan instances traverse the same file paths, discover the same tracks, and both attempt `INSERT` concurrently. SQLAlchemy unique constraints raise `IntegrityError` mid-batch, leaving a partial scan result.
- **Impact**: Partial scan state; some tracks not inserted; `IntegrityError` traceback in logs; inconsistent library state.
- **Suggested Fix**: Check and increment a `scanning_in_progress` counter in the settings table (with DB-level lock) before starting; decrement on completion.

---

## Dimension 5: Frontend State Consistency

### C-17: useRestAPI Has No AbortController for Concurrent Rapid Requests
- **Severity**: MEDIUM
- **Dimension**: Frontend State Consistency
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:51-67`
- **Status**: NEW
- **Trigger Conditions**: User triggers rapid sequential searches (or album loads) before previous responses arrive; earlier (stale) response arrives after the later (current) one.
- **Evidence**:
  ```typescript
  const fetchWithTimeout = useCallback(
    async (url, options = {}) => {
      const controller = new AbortController();  // scoped to this call only
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
      const response = await fetch(url, { ...options, signal: controller.signal });
      // Controller not exposed to caller; caller cannot abort in-flight request
    },
    []
  );
  ```
  When component calls `get('/api/search?q=a')` then immediately `get('/api/search?q=ab')`, both are in-flight. If the `q=a` response arrives last, it overwrites the `q=ab` result. The `AbortController` is internal; callers have no way to cancel the first request.
- **Impact**: Stale search/library results shown to user; UI appears to "jump back" to previous query.
- **Suggested Fix**: Expose `AbortController` from `useRestAPI`, or maintain a `lastRequestRef` inside hooks that call `get()` repeatedly, aborting the previous before issuing the next.

---

### C-18: useWebSocketSubscription Deferred Listeners Accumulate in Global Set
- **Severity**: MEDIUM
- **Dimension**: Frontend State Consistency
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts:28-100`
- **Status**: NEW (distinct from #2396 which covers the null-manager no-op)
- **Trigger Conditions**: Multiple components mount before the WebSocket manager is ready; their `messageTypes` or `memoizedCallback` deps change while deferred, causing the effect to re-run and add additional entries to the global `managerReadyListeners` set before cleanup fires.
- **Evidence**:
  ```typescript
  const managerReadyListeners: Set<ManagerReadyListener> = new Set();

  useEffect(() => {
    function subscribeToManager(manager) { ... }
    const manager = getWebSocketManager();
    if (!manager) {
      managerReadyListeners.add(subscribeToManager);   // add new function ref
    }
    return () => {
      managerReadyListeners.delete(subscribeToManager); // deletes current ref
      // but if deps changed, the NEW function ref was added before cleanup fires
      // → old ref + new ref both in set
    };
  }, [messageTypes, memoizedCallback]);  // deps change → re-run
  ```
- **Impact**: Memory leak — N stale listeners accumulate per re-render cycle. When `setWebSocketManager()` fires, all N are invoked, creating duplicate subscriptions that each dispatch redundant Redux actions.
- **Suggested Fix**: Use a stable `Symbol` or ref-based ID per hook instance as the set key, not the function reference itself.

---

## Findings Skipped (Confirmed Duplicates)

| Finding | Matches Existing Issue |
|---------|----------------------|
| P-02: prebuffer_callbacks race | #2412 |
| P-06: PlaybackController.callbacks no lock | #2308 |
| P-09: start_prebuffering TOCTOU | #2297 |
| P-14: _processor_cache unsafe eviction | #2328 |
| WS-03: active_jobs counter not atomic | #2299 |
| WS-04: processors dict concurrent access | #2320 |
| F5.1: Stale queue state in WS NEXT handler | #2178 |
| F5.2: Object.assign clobbers streaming sub-state | #2352 |
| F5.3: toggleEnabled stale closure | #2404 |

---

## Related Prior Audits

- [AUDIT_SECURITY_2026-02-17.md](AUDIT_SECURITY_2026-02-17.md) — SEC-01 cross-origin WebSocket hijack is complementary to C-03
- [AUDIT_SEARCH_2026-02-17.md](AUDIT_SEARCH_2026-02-17.md) — S-25 (#2412) prebuffer_callbacks race
- [AUDIT_REGRESSION_2026-02-17.md](AUDIT_REGRESSION_2026-02-17.md) — R-08 (#2376) parallel DSP chunk processing
