# Concurrency and State Integrity Audit — 2026-07-25

**Scope**: Race conditions, missing locks, thread-safety violations, state-machine bugs, unsafe concurrent access
**Depth**: deep (full execution-path tracing)
**Method**: Fresh static analysis of the current tree. No tests executed. Prior reports (*docs/audits/AUDIT_CONCURRENCY_2026-07-12.md* et al.) were **not** used as a finding source; the full GitHub issue set (4,335 issues, all states) was used for deduplication only.
**Dedup baseline**: `gh issue list --state all --limit 5000` (4,335 issues; 97 carry the `concurrency` label)

> **Execution note**: this audit is normally an orchestrator that fans out 5 dimension subagents. The global concurrent-subagent limit was saturated by sibling audits in the `comprehensive` suite for the whole run, so all five dimensions were traced directly by the orchestrator. Coverage is complete for dimensions 1–4; dimension 5 (frontend) is narrower than a dedicated agent would have achieved — see *Coverage Gaps*.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 4 |
| MEDIUM   | 8 |
| LOW      | 5 |
| **Total NEW** | **17** |
| Already tracked (OPEN, not re-reported) | 9 |

### Key themes

1. **The chunk cache is the weakest link.** The engine's *in-process* locking discipline is genuinely excellent — the player, queue, and playback-controller paths have been hardened issue-by-issue over ~40 fixes and I could not break them. But the **on-disk** chunk cache has no concurrency story at all: files are written non-atomically to a deterministic path that three independent subsystems can target simultaneously, and every reader validates with a bare `Path.exists()`. This is the single most impactful finding (**BST-1**).

2. **Lifecycle asymmetry in background workers.** Several workers are cancelled but never awaited (`JobWorker.stop`), or hold caches that are only pruned on a code path that a fully-cached track never reaches (`StreamlinedCacheWorker`, **BST-2**). Both compound over a long session.

3. **Ordering guards are applied inconsistently.** `player_state` broadcasts carry a monotonic `seq` and the frontend drops stale ones (#3732/#4338) — but the 1 Hz `position_changed` tick, which mutates the *same* field, carries no `seq` and is applied unconditionally (**BST-4**). Same class: `RealtimeLevelMatcher`'s setters were locked by #4340 but its reader was not (**PTS-1**).

4. **Singleton construction is locked in two of three places.** `get_parallel_processor` (#2314) and `get_processor_factory` both use double-checked locking; `get_content_analysis_facade` does not (**AP-1**).

5. **Migration locking has an unlink race.** The inter-process file lock deletes its own lock file during teardown, which lets a later caller create a fresh inode and acquire in parallel with a waiter queued on the old one (**LDB-1**).

### Most impactful races

1. **BST-1** — torn chunk WAV served as audio (silent corruption, persists in cache until pruned)
2. **BST-2** — unbounded `ChunkedAudioProcessor` accumulation (each pins a `HybridProcessor` + open `SoundFile`)
3. **FST-1** — orphaned `WebSocketManager` with a live socket and a running reconnect timer
4. **LDB-1** — two concurrent schema migrations against `~/.auralis/library.db`

---

## Concurrency Matrix

| Component | Primitive | Status |
|-----------|-----------|--------|
| `AudioFileManager` | `threading.RLock` (`_audio_lock`) | ✅ Sound. Load I/O outside the lock, atomic swap inside, composite snapshot helpers (`get_state_snapshot`). |
| `PlaybackController` | `threading.RLock` + `threading.local` deferral | ✅ Sound. `defer_notifications()` (#3781) correctly resolves the `_audio_lock` ↔ `_position_lock` AB-BA. |
| `QueueManager` | `threading.RLock` | ✅ Sound. `advance_if_next_matches` closes the peek→commit TOCTOU; every composite read is a single critical section. |
| `GaplessPlaybackEngine` | `threading.Lock` ×2 + `Event` | ⚠️ `update_lock → _audio_lock` nesting is latent-deadlock-shaped (tracked, #3782). Rollback-on-mutation logic (#4100/#4212) verified correct. |
| `IntegrationManager` | 3 × `Lock`/`RLock` | ⚠️ ORM `to_dict()` called under `_position_lock` (**PTS-2**); stats read unlocked. |
| `RealtimeProcessor` / `AutoMaster` / `LevelMatcher` | per-object `threading.Lock` | ⚠️ `LevelMatcher.get_stats()` unlocked (**PTS-1**); `AutoMaster.process()` holds its lock across the full DSP chain (coarse, **AP-5**). |
| Rust DSP (`vendor/auralis-dsp/`) | `py.allow_threads` on every long compute | ✅ Sound. All 11 PyO3 entry points release the GIL; no `static mut` / global state; `catch_unwind` at every boundary. |
| `ProcessorPool` | `asyncio.Lock`, pop-on-acquire | ✅ Sound. Popping prevents sharing; a dropped processor is GC'd, not leaked into the pool. |
| `JobWorker` | `asyncio.Semaphore` + `acquired` flag | ⚠️ Slot accounting correct (#3531); shutdown does not await cancelled tasks (**BST-3**). |
| `SimpleChunkCache` (in-memory) | `threading.Lock` | ✅ Sound. Byte accounting correct on overwrite/evict/invalidate. Returned arrays are never mutated by the send path (verified through `send_pcm_chunk`). |
| `ChunkCacheManager` (on-disk) | class-level prune lock only | ❌ No write-atomicity, no per-key lock. **BST-1**. |
| `StreamlinedCacheWorker` | per-key `asyncio.Lock` (#4369) | ⚠️ Build lock itself is correct double-checked locking; the cache it protects is never bounded (**BST-2**). |
| `PlayerStateManager` | `asyncio.Lock` + `seq` counter | ⚠️ `position_changed` bypasses `seq` (**BST-4**); position loop self-terminates (**BST-5**). |
| `ConnectionManager` | `asyncio.Lock` over the list | ⚠️ List is protected; concurrent `send_text` on one socket is not (tracked, #3870). |
| SQLite engine | `check_same_thread=False`, `pool_pre_ping=True`, WAL, `busy_timeout=60000` | ✅ Verified present in both `manager.py` and `migration_manager.py`. |
| Migration | `fcntl`/`msvcrt` file lock + `threading.Lock` in `manager.py` | ⚠️ Both present (no regression), but the file lock has an unlink race and one entry point bypasses the thread lock (**LDB-1**). |
| Scan slots | `threading.Lock` + counter | ✅ Sound acquire/release. (Per-directory dedup guard is separately tracked, #4509.) |
| Frontend WS | module-level singleton + refcount | ❌ Check-then-create on a connecting/reconnecting manager (**FST-1**). |
| Redux `player_state` sync | `lastSeenSeqRef` monotonic guard | ✅ Sound for `player_state`; absent for `position_changed` (**FST-2**). |

---

# Findings

## HIGH

### BST-1: Chunk WAV cache files are written non-atomically to a deterministic path shared by three concurrent writers
- **Severity**: HIGH
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/encoding/wav_encoder.py:142-149`, `auralis-web/backend/core/chunk_cache_manager.py:189-196`, `auralis-web/backend/core/chunked_processor.py:512-575`
- **Status**: NEW
- **Trigger Conditions**: Any two of these produce the same chunk for the same `(track_id, file_signature, preset, intensity, chunk_index)` at overlapping times:
  (a) `stream_enhanced.py:118-126` constructs a **fresh** `ChunkedAudioProcessor` per WebSocket stream (`MAX_CONCURRENT_STREAMS = 10`), so a reconnect-resume, a seek that opens a second stream, or two clients on the same track each get an independent processor with an independent `_processor_lock`;
  (b) `StreamlinedCacheWorker` (started in the lifespan, `auralis-web/backend/config/startup.py:503-517`) holds its own long-lived processors and ticks every 1 s;
  (c) `auralis-web/backend/core/proactive_buffer.py:64-85` builds a processor per preset (currently wired but never invoked — see Evidence).
- **Evidence**:
  ```python
  # core/encoding/wav_encoder.py:144 — writes straight to the final cache path
  save_audio(str(chunk_path), audio, sample_rate, subtype=subtype)

  # core/chunk_cache_manager.py:191 — the only integrity check any reader performs
  path = Path(cached_value)
  if not path.exists():
      return None
  ```
  The filename is fully deterministic (`wav_encoder.py:96-99`):
  `v3_track_{id}_{sig}_{preset}_{intensity}_chunk_{n}.wav`.
  `ChunkedAudioProcessor._processor_lock` is **per instance** (`chunked_processor.py:181`), so it serialises chunks *within* one processor and provides no protection between processors.
  `proactive_buffer.py:78` shows the read side of the same hazard explicitly: `if chunk_path.exists(): continue` — a half-written file is accepted as complete and never re-derived.
- **Impact**: Two interleaved `sf.write()` calls to one path produce a WAV whose header and data frames come from different writers. A later cache hit (`chunked_processor.py:516-525` → `load_audio(cached_path)`) either raises inside `soundfile` (chunk dropped from the stream) or decodes garbage/truncated audio and streams it to the user. The corrupt file persists until the 512 MB mtime reaper evicts it, so the artefact repeats on every replay of that chunk.
- **Siblings**: The same write-then-`exists()` pattern appears at `chunked_processor.py:630`, `chunked_processor.py:719`, `proactive_buffer.py:78`, and `chunk_cache_manager.py:191`. `#4508` (OPEN, LOW) is the same *class* of bug for `.25d` fingerprint sidecars — this is the audio-path instance and is materially more severe.
- **Suggested Fix**: Write to `chunk_path.with_suffix('.wav.tmp.<pid>.<uuid4>')` and `os.replace()` into place — `os.replace` is atomic within a filesystem, so readers see either the old file or a complete new one. Optionally add a process-wide `dict[str, threading.Lock]` keyed on the chunk cache key so redundant work is skipped rather than duplicated.

### BST-2: `StreamlinedCacheWorker` processor cache is only pruned on a path a fully-cached track never reaches
- **Severity**: HIGH
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/streamlined_worker.py:56-63, 126-131, 226-240, 303-331`
- **Status**: NEW
- **Trigger Conditions**: Normal listening. Every distinct `(track_id, preset, intensity)` tuple seen by `_process_chunk` allocates a `ChunkedAudioProcessor`; entries are evicted **only** inside `_build_tier2_cache`, and `_process_priorities` skips that call entirely once `is_track_fully_cached(track_id)` returns True. `intensity` is a `float` fed by a UI slider, so a single track can mint dozens of keys.
- **Evidence**:
  ```python
  # _process_priorities:130 — the only route to the eviction code
  if not self.cache_manager.is_track_fully_cached(track_id):
      await self._build_tier2_cache(track, track_id, current_chunk, preset, intensity)

  # _build_tier2_cache:227-240 — the only eviction, gated on a track change
  if self._building_track_id != track_id:
      self._processor_cache = {k: v for k, v in self._processor_cache.items() if k[0] == track_id}
      self._processor_build_locks = {k: v for k, v in self._processor_build_locks.items() if k[0] == track_id}
  ```
  There is no size cap, no LRU, and no eviction in `_process_chunk` or `trigger_immediate_processing` (which is the seek/cache-miss path and can insert keys directly at line 331).
- **Impact**: Each retained `ChunkedAudioProcessor` pins a `HybridProcessor` (the pool sizes these at ~200 MB in `processor_pool.py:8`), an open `soundfile` handle, and a cached fingerprint. Over a listening session across many tracks and slider positions this is an unbounded RSS + file-descriptor leak in the always-on backend of a desktop app. `_processor_build_locks` grows in lockstep.
- **Siblings**: The two other processor caches in the codebase are both bounded — `ProcessorPool` (`max_cached=5`, `processor_pool.py:108-111`) and `hybrid_processor._processor_cache` (`_PROCESSOR_CACHE_MAX_SIZE = 10` with `evicted_processor.close()`, `hybrid_processor.py:633-640`). This one is the outlier.
- **Suggested Fix**: Make `_processor_cache` an `OrderedDict` with an explicit cap (mirror `hybrid_processor.py:633-640`, including calling `close()` on the evicted processor to release its `SoundFile`), and evict the matching `_processor_build_locks` entry alongside it. Quantise `intensity` into the cache key (e.g. `round(intensity, 2)`) to stop slider drag from minting keys.

### FST-1: `useWebSocketConnection.connect()` check-then-create orphans a live `WebSocketManager`
- **Severity**: HIGH
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:87-164, 169-185`
- **Status**: NEW
- **Trigger Conditions**: Any `connect()` call that lands while `connState.manager` exists but `isConnected()` is false — i.e. during the initial `await manager.connect()` handshake, or at any point during exponential-backoff reconnection (up to 30 s per attempt, 10 attempts in production).
- **Evidence**:
  ```ts
  // :93 — the reuse guard only matches a FULLY connected manager
  if (connState.manager?.isConnected()) { ... return; }

  // :109-121 — otherwise a second manager is built and silently replaces the first
  const manager = new WebSocketManager(url, { maxReconnectAttempts: maxAttempts, ... });
  connState.manager = manager;   // previous manager is dropped, never .close()d
  ```
  `disconnect()` (:175-179) only ever closes `connState.manager`, so the overwritten instance is unreachable.
- **Impact**: The orphaned manager keeps its socket, its `message`/`open`/`close` handlers, and its reconnect timer alive for the lifetime of the renderer. Its `message` handler still calls `handleSocketFrame(..., dispatchRef.current)`, so a second copy of every inbound frame is dispatched into Redux. Each occurrence compounds; nothing ever reclaims them. In an always-on Electron client a flaky backend restart cycle can accumulate several.
- **Siblings**: The reuse path at :93-99 has a related gap — it does **not** re-register handlers on the reused manager, so a second consumer's `mountedRef`/`dispatchRef` are never wired up and its `isConnected`/`connectionStatus` freeze if the original provider unmounts while `refCount > 0`.
- **Suggested Fix**: Treat "a manager object exists" (not "is connected") as the reuse condition, and store an in-flight connect promise so concurrent callers await the same handshake. If replacement is ever genuinely intended, `connState.manager?.close()` before overwriting.

### LDB-1: `migration_lock` deletes its own lock file during teardown, defeating the lock for a queued waiter
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_manager.py:34-115` (unlink at :111-115), `auralis/library/migrations/normalize_existing_artists.py:59`
- **Status**: NEW
- **Trigger Conditions**: Three concurrent migration attempts (two processes plus a thread, or three processes — the desktop app plus a CLI invocation plus a dev server are all realistic).
  1. A opens the lock file (inode 1) and holds `flock`.
  2. B opens the same path, gets inode 1, blocks in the 0.1 s retry loop.
  3. A releases and **unlinks** inode 1 (`:113`).
  4. B's next retry succeeds on inode 1 — which is now unlinked.
  5. C opens the path, creates a **new** inode 2, and `flock`s it immediately with no contention.
  B and C now both believe they hold the migration lock.
- **Evidence**:
  ```python
  finally:
      if lock_fd:
          ...
          fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
          lock_fd.close()
      try:
          if lock_file.exists():
              lock_file.unlink()      # <-- breaks the path→inode identity the lock depends on
  ```
- **Impact**: Two schema migrations running DDL against `~/.auralis/library.db` at once. `MigrationManager` does take a backup, but concurrent `ALTER TABLE` / version-row writes on a WAL database can leave the schema version and the actual schema out of sync — the failure mode that `#2905` (MigrationManager DDL+version not atomic) was closed to prevent.
- **Siblings**: The same-process `threading.Lock` fix is **not** regressed — `auralis/library/manager.py:46` still defines `_migration_lock` and `:114` still wraps the migration step. But it guards only `LibraryManager.__init__`. The second migration entry point, `auralis/library/migrations/normalize_existing_artists.py:59`, takes `migration_lock()` **without** `_migration_lock`, so same-process threads are unserialised there. On Windows this matters more: `msvcrt.locking` byte-range locks are per-process, so two threads in one process can both acquire.
- **Suggested Fix**: Never unlink the lock file — a zero-byte sentinel in the DB directory is harmless and its persistence is what makes the lock correct. Move `_migration_lock` next to `migration_lock` and acquire both inside the same context manager so every entry point gets thread + process serialisation.

---

## MEDIUM

### BST-3: `JobWorker.stop()` cancels in-flight jobs but never awaits them
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/job_worker.py:97-132`, `:90-95`
- **Status**: NEW
- **Trigger Conditions**: Backend shutdown (or `POST /api/library/reset`) while any job is processing.
- **Evidence**:
  ```python
  for job_id, task in list(self._tasks.items()):
      if not task.done():
          task.cancel()          # no await, no gather
  ...
  logger.info("Processing engine worker stopped")
  ```
  Compounding this, `_run_job`'s cleanup is itself an `await` inside `finally`:
  ```python
  finally:
      self._tasks.pop(job.job_id, None)
      if acquired: ... self._concurrency_semaphore.release()
      await self._engine.cleanup_old_jobs(...)   # re-raises CancelledError immediately
  ```
- **Impact**: `stop()` returns while cancelled jobs are still unwinding. Their `cleanup_old_jobs` never runs, and a job parked in `asyncio.to_thread(processor.process, audio)` keeps a worker thread and a `HybridProcessor` alive past the point the lifespan tears down the library manager. Compare `StreamlinedCacheWorker.stop()` (`streamlined_worker.py:72-81`), which does `await self._worker_task` correctly.
- **Siblings**: `state_manager._stop_position_updates()` (`state_manager.py:220-224`) has the same cancel-without-await shape (lower impact — the loop holds no external resources).
- **Suggested Fix**: `await asyncio.gather(*tasks, return_exceptions=True)` after the cancel loop, with a bounded `asyncio.wait_for`. Move `cleanup_old_jobs` out of the `finally` (or wrap it in `asyncio.shield`) so slot accounting completes on the cancel path.

### BST-4 / FST-2: `position_changed` broadcasts bypass the `seq` ordering guard and can rewind the progress bar
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming + Frontend State
- **Location**: `auralis-web/backend/core/state_manager.py:269-275` (producer), `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:192-197` (consumer)
- **Status**: NEW
- **Trigger Conditions**: A seek that lands within the same ~1 s window as a position tick. The tick reads `self.state.current_time` under `_lock`, releases, then broadcasts *outside* the lock — exactly the arrangement `#3732` introduced `seq` to make safe for `player_state`.
- **Evidence**:
  ```python
  # state_manager.py:271-275 — no seq, no _update_seq bump
  await self.ws_manager.broadcast({
      "type": "position_changed",
      "data": {"position": new_time},
  })
  ```
  ```ts
  // usePlayerStateSync.ts:192-197 — applied unconditionally
  subscribe('position_changed', (message) => {
    if (... Number.isFinite(data.position)) dispatch(setCurrentTime(data.position));
  });
  ```
  The `player_state` sibling at `:98-101` *is* guarded: `if (state.seq < lastSeenSeqRef.current) return;`.
- **Impact**: A stale pre-seek position lands after the post-seek snapshot and `setCurrentTime` rewinds the UI by up to the seek distance until the next tick corrects it. Visible as a jump-back on the scrub bar after every seek that races a tick.
- **Suggested Fix**: Stamp `position_changed` with the same `_update_seq` value (without bumping it), and apply the identical `lastSeenSeqRef` guard in the `position_changed` subscriber.

### BST-5: 1 Hz position broadcasts stop permanently after the first auto-advance
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/state_manager.py:226-277` (`return` at :267), `:116-125`
- **Status**: NEW
- **Trigger Conditions**: A track reaching its end so `new_time >= self.state.duration`.
- **Evidence**:
  ```python
  if track_ended:
      spawn_background_task(self.next_track(), name="StateManager.next_track")
      return          # loop exits for good
  ```
  `next_track()` (`:148-175`) calls `update_state(queue_index=…, current_track=…, current_time=0.0)` — it never calls `set_playing()`, and `_start_position_updates()` is reachable *only* from `set_playing(True)` (`:122-123`).
- **Impact**: After the first queue auto-advance the backend stops emitting `position_changed`, so `redux.player.currentTime` freezes for the remainder of the session — the exact regression `#3937 / RS-5` fixed for the initial case. Recovers only on an explicit user play/pause.
- **Suggested Fix**: Restart the loop at the end of `next_track()` when the resulting state is still PLAYING, or replace the `return` with a `continue` that re-reads state after the advance completes.

### BST-6: `_process_priorities` reads four pieces of cache-manager state without a consistent snapshot
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/streamlined_worker.py:109-131`
- **Status**: NEW
- **Trigger Conditions**: A track change or preset/intensity change landing between any two of the four reads. There is an `await` at `:120` (`asyncio.to_thread(...get_by_id...)`) *after* all four reads, widening the window to a full DB round-trip.
- **Evidence**:
  ```python
  track_id = self.cache_manager.current_track_id
  current_chunk = self.cache_manager._get_current_chunk(self.cache_manager.current_position)
  preset = self.cache_manager.current_preset
  intensity = self.cache_manager.intensity
  track = await asyncio.to_thread(self.library_manager.tracks.get_by_id, track_id)
  ```
- **Impact**: Chunks get processed and cached under a mismatched tuple — e.g. track A's id with track B's playback position, producing a chunk index past A's end (wasted DSP, a logged failure) or a chunk cached under the wrong preset. Self-corrects on the next 1 s tick, so it is wasted work rather than corruption.
- **Suggested Fix**: Add a `StreamlinedCacheManager.get_playback_snapshot()` returning `(track_id, position, preset, intensity)` from one critical section, mirroring the `AudioFileManager.get_state_snapshot()` pattern (#3474).

### AP-1: `get_content_analysis_facade()` is an unlocked check-then-create singleton with unlocked lazy sub-analyzers
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis/core/analysis/content_analysis_facade.py:254-280`, `:88-124`, `:246-250`
- **Status**: NEW
- **Trigger Conditions**: Two `asyncio.to_thread` DSP workers calling the accessor concurrently on a cold process; or any caller invoking `reset()` while another thread is inside `analyze_full`/`analyze_quick`.
- **Evidence**:
  ```python
  global _global_content_analysis_facade
  if _global_content_analysis_facade is None:            # no lock
      _global_content_analysis_facade = ContentAnalysisFacade(...)
  ```
  The lazily-built sub-analyzers repeat the pattern on the shared instance (`:99-107`, `:112-122`), and `reset()` (`:246-250`) nulls both from any thread.
- **Impact**: Duplicate construction (wasted work, one instance silently discarded) and, via `reset()`, a window where one thread holds a reference to a `ContentAnalyzer` that the singleton no longer owns while another builds a replacement — divergent stateful analyzer instances.
- **Siblings**: Both other module-level singleton accessors in the codebase *are* locked: `auralis/optimization/parallel/audio_processor.py:116-129` (double-checked, #2314) and `auralis-web/backend/core/processor_factory.py:450-459`. This one is the only unlocked member of the family.
- **Mitigation**: `get_content_analysis_facade` currently has **zero production callers** (only its own module references it), so this is latent. Reported because the file is live, imported code and the sibling divergence makes it a foot-gun.
- **Suggested Fix**: Copy the `_global_parallel_processor_lock` double-checked pattern; guard the lazy sub-analyzer properties with the same lock and drop `reset()` or make it lock-protected.

### AP-2: `AudioContentAnalyzer` caches on `id(audio_data)`, which CPython reuses after GC
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/services/audio_content_predictor.py:96-100, 125-126`
- **Status**: NEW
- **Trigger Conditions**: Any `analyze_chunk_fast()` call with `filepath=None`. `id()` is the memory address in CPython, so once the first array is collected a *different* array allocated at the same address collides with the cached entry.
- **Evidence**:
  ```python
  cache_key = f"{filepath}_{chunk_idx}" if filepath else f"mem_{id(audio_data)}"
  if cache_key in self.analysis_cache:
      return self.analysis_cache[cache_key]
  ...
  if len(self.analysis_cache) < self._cache_max_size:
      self.analysis_cache[cache_key] = features
  ```
- **Impact**: Wrong `AudioFeatures` returned for unrelated audio, which then drives preset prediction. Secondary: the cache stops accepting *any* new entry once it reaches 100 (there is no eviction), so it silently freezes on the first 100 keys — including any poisoned `mem_*` entries, which then persist for the process lifetime.
- **Siblings**: The two `await` points between the miss check (`:98`) and the write (`:126`) also let two concurrent callers duplicate the analysis; benign, but it means the cache does not actually dedupe concurrent work.
- **Suggested Fix**: Hash the array contents (or refuse to cache when `filepath` is None) and replace the `< max_size` guard with LRU eviction via `OrderedDict`.

### PTS-1: `RealtimeLevelMatcher.get_stats()` reads mutable state without `_lock`
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/realtime/level_matcher.py:122-130`
- **Status**: NEW
- **Trigger Conditions**: `RealtimeProcessor.get_processing_info()` (served by `/api/processing/*` from the event-loop thread) running while the audio callback is inside `process()` or while `reset()` replaces `gain_smoother`.
- **Evidence**:
  ```python
  def get_stats(self) -> dict[str, Any]:
      return {                                  # no `with self._lock:`
          'enabled': self.enabled,
          'reference_rms': self.reference_rms or 0.0,
          'current_gain': self.gain_smoother.current_gain,
          'target_gain': self.gain_smoother.target_gain,
      }
  ```
  `reset()` (`:76-82`) rebinds `self.gain_smoother` **under** `_lock`, so the two attribute reads at `:128-129` can straddle the swap and report `current_gain` from the old smoother with `target_gain` from the new one.
- **Impact**: Torn/inconsistent telemetry surfaced to the UI. No audio impact.
- **Siblings**: The direct sibling `AutoMasterProcessor.get_stats()` (`auralis/player/realtime/auto_master.py:234-237`) *does* take its lock. `#4340` locked this class's `set_enabled`/`reset` but left the reader unguarded — this is the remaining half of that fix.
- **Suggested Fix**: Wrap the dict construction in `with self._lock:`, matching `AutoMasterProcessor.get_stats()`.

### PTS-2: `IntegrationManager` holds `_position_lock` across an ORM `to_dict()`, and reads session stats unlocked
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/integration_manager.py:143-156`, `:259-295`
- **Status**: NEW
- **Trigger Conditions**: Every playback state change and every `get_playback_info()` poll while `self.current_track` is a SQLAlchemy `Track` whose relationships (`artists`, `album`) are not eagerly loaded.
- **Evidence**:
  ```python
  with self._position_lock:
      state_info.update({
          ...
          'current_track': self.current_track.to_dict() if self.current_track else None,
      })
  ```
  and at `:278-280` the same call inside the `get_playback_info()` critical section. Meanwhile `:291-293` reads `self.tracks_played` / `self.total_play_time` **outside** `_stats_lock`, which `record_track_completion()` (`:299-301`) holds for the write.
- **Impact**: `to_dict()` on a lazily-loaded ORM object emits a SQL query. That places a library DB round-trip inside a player lock — the inverse of the project's stated safe ordering (Player lock → Library session; `.claude/commands/_audit-common.md`). It also raises `DetachedInstanceError` under `_position_lock` if the loading session has closed, and blocks `_get_position_seconds()` (the position reporter) for the query duration. The unlocked stats read is cosmetic but is the exact pattern `#2472` fixed on the write side.
- **Suggested Fix**: Materialise `current_track` into a plain dict at assignment time (`:184-185`) and store *that*, so no ORM access happens under a player lock. Take `_stats_lock` for the session block at `:291-293`.

---

## LOW

### AP-3: `ParallelBandProcessor` passes one un-copied array to every band filter in a group
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis/optimization/parallel/band_processor.py:233-235`, `:246-250`, `:102-105`, `:122-125`
- **Status**: NEW
- **Trigger Conditions**: Any band filter that mutates its input in place.
- **Evidence**:
  ```python
  # _process_band_group:233-235 — same `audio` reused for every band in the group
  for band_idx in band_indices:
      filtered = band_filters[band_idx](audio)
      group_result += filtered * (10 ** (band_gains[band_idx] / 20))
  ```
  The *fallback* path immediately above got exactly this fix in `#4229` (`:210-213`: `band_filters[band_idx](audio.copy())`, with the comment "an in-place band filter would otherwise corrupt `audio` for the remaining fallback iterations") — the worker path did not.
- **Impact**: Bands processed after an in-place filter within the same group see corrupted input → wrong EQ curve / phase artefacts. Cross-*worker* corruption is already prevented (`:130`, `:191` pass `audio.copy()`); this is strictly intra-group.
- **Siblings**: `_process_bands_sequential:249` and both `band_fallbacks` precompute loops (`:103`, `:123`) share the pattern.
- **Mitigation** (why LOW, not HIGH): `auralis/optimization/parallel/` has **zero production importers** — the only references outside the package are in `tests/`. `#3355`/`#4229` established this as a real bug class, but no live code path can reach it today.
- **Suggested Fix**: Pass `audio.copy()` at all four sites, matching `#4229`. Alternatively, decide whether `auralis/optimization/parallel/` should be deleted (tech-debt call, out of scope here).

### AP-4: `ParallelFFTProcessor.get_window()` hands out a writable reference to the shared window cache
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis/optimization/parallel/fft_processor.py:44-79`, `:109-120`
- **Status**: NEW
- **Evidence**: `parallel_windowed_fft` explicitly hardens the multi-frame branch (`:119-120`: `window = window.view(); window.setflags(write=False)`, per `#3761`) but the sub-FFT-size early return at `:109-112` passes the raw cached array, and `get_window()` is public.
- **Impact**: A future in-place window modification would silently corrupt every subsequent FFT across all threads. No current caller mutates it (`_process_fft_chunk` only does `chunk * window`).
- **Suggested Fix**: Set `write=False` once inside `get_window()` / `_init_window_cache()` rather than at one call site.

### PTS-3: `PlayerPropertiesMixin` setters bypass the locks their readers use
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/player_properties_mixin.py:41-44, 71-74, 86-89`
- **Status**: NEW (sibling of OPEN `#3785`)
- **Evidence**: `audio_data`'s setter correctly takes `_audio_lock` (`:56-64`, per `#3443`), but its three neighbours do not:
  ```python
  @current_track.setter
  def current_track(self, value): self.integration.current_track = value   # _position_lock not held
  @reference_data.setter
  def reference_data(self, value): self.file_manager.reference_data = value  # _audio_lock not held
  @sample_rate.setter
  def sample_rate(self, value): self.file_manager.sample_rate = value        # _audio_lock not held
  ```
  `#3786` made the internal `current_track` write take `_position_lock`; this public setter is the remaining bypass.
- **Impact**: Under a free-threaded (PEP 703) build, a reader can observe a half-updated composite (e.g. new `sample_rate` with the old `audio_data`). Under the GIL the individual writes are atomic, so this is a hardening gap.
- **Suggested Fix**: Route all three through the same lock the readers hold; fold into the `#3785` fix.

### BST-7: `JobWorker.cancel_task` is documented as thread-safe but is not
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/job_worker.py:160-164`
- **Status**: NEW
- **Evidence**: `"""Cancel the in-flight task for a job, if any (thread-safe)."""` — but `asyncio.Task.cancel()` must be scheduled via `loop.call_soon_threadsafe()` when called from outside the loop thread.
- **Impact**: None today (all callers are on the loop), but the docstring actively invites an unsafe call site.
- **Suggested Fix**: Correct the docstring, or route through `call_soon_threadsafe` and make it genuinely safe.

### BST-8: `StreamlinedCacheWorker.stop()` leaves a stale `_worker_task` reference
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/streamlined_worker.py:72-81`
- **Status**: NEW
- **Evidence**: `stop()` cancels and awaits correctly but never sets `self._worker_task = None`. A later `start()` overwrites it, so nothing breaks — but `auralis-web/backend/config/startup.py:525` reads `globals_dict['streamlined_worker']._worker_task` directly for health reporting and will see a finished task after a stop/start cycle if the ordering ever changes.
- **Suggested Fix**: Set `self._worker_task = None` at the end of `stop()`.

---

## Already Tracked (OPEN — verified still present, not re-reported)

| # | Title (abridged) | Note |
|---|------------------|------|
| **#3870** | Heartbeat `websocket.send_text` unprotected | **Severity looks understated at LOW.** I confirmed *three* independent producers send on the same socket concurrently: `ConnectionManager.broadcast` (`auralis-web/backend/config/globals.py:142`), the heartbeat loop (`auralis-web/backend/ws_handlers/connection.py:57`), and the streaming task's `safe_send`/`safe_send_bytes` (`auralis-web/backend/core/stream_protocol.py:239-245`) — plus the 1 Hz `position_changed` broadcast. Starlette does not support concurrent sends on one connection. Recommend re-triaging as MEDIUM and fixing with a per-connection `asyncio.Lock`. |
| #3867 | `ConnectionManager.broadcast` iterates serially | Still present, `auralis-web/backend/config/globals.py:140-145`. |
| #3890 | `_notify_progress` reads/writes outside `_jobs_lock` | Still present. |
| #3889 | `cancel_job` mutates `progress_callbacks` outside `_jobs_lock` | Still present. |
| #3880 | `_chunk_tails` allocates tails nothing reads | Confirmed: `apply_boundary_crossfade` is a documented no-op (`auralis-web/backend/core/stream_chunk_ops.py:155-186`) yet `:231` still stores a tail copy per chunk. |
| #3785 | `AudioFileManager` raw property reads bypass `_audio_lock` | Still present; see PTS-3 for the setter-side siblings. |
| #3782 | `gapless.update_lock → _audio_lock` on a non-reentrant `Lock` | Still present, `gapless_playback_engine.py:307-313`. Confirmed still *latent*: the only `update_lock`-then-`_audio_lock` site is reached exclusively from `AudioPlayer.next_track()`, which already holds the (reentrant) `_audio_lock`, so no AB-BA partner exists today. |
| #3735 | `next_track` holds `_audio_lock` too wide | The narrowing described in the `#3735` comment block *has* landed (`enhanced_audio_player.py:333-339`); the issue appears stale and closeable. |
| #4509 | Per-directory scan dedup guard is per-instance | Still present. |

---

## Verified Safe (checked and found correct)

These were traced specifically because they are classic failure points; each was confirmed sound in current code.

**Player**
- `AudioPlayer.seek()` / `position.setter` / `load_file()` / `load_track_from_library()` / `next_track()` all use `with self.playback.defer_notifications(), self.file_manager._audio_lock:` in the correct nesting order (defer OUTER), closing the `_audio_lock` ↔ `_position_lock` AB-BA of `#3781`. I checked every other site that mutates `PlaybackController` state and found none that notifies while holding `_audio_lock`.
- The auto-advance generation protocol (`get_audio_chunk` spawn at `enhanced_audio_player.py:526-537` + compare-and-clear at `:582-584`) is fully enclosed in `_audio_lock` on both sides — no duplicate-thread window.
- `GaplessPlaybackEngine`'s stale-prebuffer path is safe: a worker that finishes loading after an `invalidate_prebuffer()` can still publish a stale buffer, but `advance_with_prebuffer`'s identity check (`:233-240`) rejects it and falls back to a fresh load.
- The `#4100` / `#4212` audio-swap rollbacks (`:287-303`, `:337-358`) correctly snapshot and restore `audio_data`/`sample_rate`/`current_file` under `_audio_lock` when the queue mutates mid-advance.
- `QueueManager.advance_if_next_matches` is a genuine atomic peek+commit; `get_queue_info` is a single-critical-section composite snapshot.
- Fingerprint staleness: `_schedule_fingerprint_load` / `_load_fingerprint_for_file` hold `_fingerprint_lock` across check-and-act on all three paths (success, no-fingerprint, exception), so an older generation can never overwrite a newer one.

**Audio processing**
- Rust DSP: all 11 PyO3 entry points wrap long compute in `py.allow_threads(|| catch_unwind(...))`. No `static mut`, no global `Mutex`/`RwLock` state. The `Rust holds GIL during long compute` special rule does not apply.
- `HybridProcessor` module cache (`hybrid_processor.py:604-643`): entire check-and-insert under one lock acquisition, LRU-bounded at 10, and `evicted_processor.close()` releases the evicted instance's thread pool.
- `chunked_processor._last_content_profiles` is guarded by a dedicated module lock on both the writer (`:775`, from `to_thread` workers) and the reader (`:794`, from the event loop).
- `ParallelFeatureExtractor` passes `audio.copy()` to every worker and guards each `future.result()` (#3673/#3674).
- `RealtimeProcessor.process_chunk` copies before any mutation and casts the safety-limiter scalar to the input dtype (no float32→float64 drift).

**Backend streaming**
- `stream_enhanced.py` and `stream_normal.py` each acquire `_stream_semaphore` before a single enclosing `try`, and release exactly once in the outer `finally` (`stream_enhanced.py:298-305`, `stream_normal.py:325-328`). I walked every `return`/`raise`/early-exit inside both — all are inside the guarded block.
- `ProcessorPool.get_or_create` pops on acquire so no two jobs share an instance; a processor lost to an exception is GC'd rather than leaked back into the pool.
- `SimpleChunkCache` byte accounting is correct on overwrite (#3192), count eviction, memory eviction, and `invalidate_chunk`. The array it returns by reference is never mutated downstream — I traced through `stream_processed_chunk` → `apply_boundary_crossfade` (no-op) → `send_pcm_chunk`, where `astype(copy=False)`, `reshape`, and `tobytes()` are all non-mutating.
- `drop_chunk_tail` routes all five `_chunk_tails` pop sites through `_chunk_tails_lock` (#3527).
- `drain_cancelled_task` correctly suppresses `CancelledError` (a `BaseException`) and retrieves exceptions from already-done tasks.
- The `#4369` per-key build lock in `streamlined_worker._process_chunk:303-331` is a correct double-checked pattern: `dict.setdefault` for the lock lookup is atomic on the single-threaded loop, and the re-check inside `async with build_lock` closes the await window. Pruning a lock while a holder is in flight is also safe — the holder keeps its own reference.
- `AudioContentAnalyzer`'s blocking bodies are genuinely offloaded (`_load_chunk_fast` → `to_thread(_load_chunk_fast_sync)`, `_extract_features` → `to_thread(_extract_features_sync)`, per `#4379`). I found no remaining sync DSP/file call on an `async def` path in `core/`.

**Library & database**
- `check_same_thread=False`, `pool_pre_ping=True`, `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=60000` — all confirmed present in **both** `auralis/library/manager.py:123-156` and `auralis/library/migration_manager.py:129-150`.
- The same-process migration `threading.Lock` (`manager.py:46`, used at `:114`) is **not** regressed — it is still there with its `#4232` rationale intact. (Its coverage gap is LDB-1.)
- `try_acquire_scan_slot` / `release_scan_slot` (`manager.py:275-301`) are a correct counted-semaphore pair with a `max(0, …)` floor on release.
- `backup_database` / `restore_database` use the SQLite Online Backup API rather than `shutil.copy2`, so WAL contents are captured — the correct choice for a live database.
- Repository raw SQL: the six `text()` sites are all parameterised. `fingerprint_repository.py:621` interpolates `cols_str` / `named_placeholders` / `update_clause` into an f-string, but these derive from the fixed 25-D schema column list, not user input — no injection surface.

---

## Relationships

- **BST-1 ↔ BST-2 ↔ BST-6** share one root cause: `StreamlinedCacheWorker` and `stream_enhanced` maintain *independent* `ChunkedAudioProcessor` populations for the same logical work, with no shared identity, no shared lock, and no shared bound. Unifying chunk production behind a single keyed registry would fix all three at once and is the highest-leverage structural change in this report.
- **BST-4 ↔ BST-5 ↔ FST-2** are all `PlayerStateManager._position_update_loop` defects. They should be fixed together — the loop needs a restart trigger, a `seq`, and a matching frontend guard.
- **PTS-1, PTS-3, AP-1** are all *sibling-inconsistency* findings: a lock discipline was established and applied to most members of a family but not all. Each is individually LOW/MEDIUM; collectively they indicate that "fix the reported site" has been winning over "grep the family", which is what the audit protocol's Sibling Detection step exists to catch.
- **LDB-1** and **#2905** (closed, "MigrationManager DDL+version not atomic") interact: the atomicity fix assumes only one migrator runs. LDB-1 breaks that assumption, so re-opening the concurrency window partly un-fixes #2905.
- **AP-3** and **AP-1** both live in code with zero production callers (`auralis/optimization/parallel/`, `content_analysis_facade`). Worth a separate tech-debt decision on whether to fix or delete.

---

## Prioritized Fix Order

1. **BST-1** (atomic chunk writes) — the only finding that can put corrupt audio in front of the user, it persists in cache once it happens, and the fix is small and self-contained (`os.replace`).
2. **BST-2** (bound the processor cache) — a compounding memory + FD leak in an always-on backend; the fix is a copy of a pattern already in the tree (`hybrid_processor.py:633-640`).
3. **LDB-1** (migration lock) — highest blast radius (library DB), even though the trigger is rarer. Do not unlink the lock file; unify with `_migration_lock`.
4. **FST-1** (orphaned WebSocketManager) — compounding leak with duplicate Redux dispatches; the reuse condition is a one-line change but the in-flight-promise part needs care.
5. **BST-4 + BST-5 + FST-2** as one changeset — user-visible progress-bar defects, all in `state_manager._position_update_loop` and its consumer.
6. **PTS-2** (ORM access under `_position_lock`) — violates the project's own documented lock ordering and can raise inside a player lock.
7. **BST-3** (await cancelled jobs on shutdown), **BST-6** (snapshot playback state), **AP-2** (`id()` cache key).
8. **#3870 re-triage** — not a new finding, but the concurrent-send hazard is broader than the open issue records.
9. **PTS-1, PTS-3, AP-1, AP-4, BST-7, BST-8** — sibling/hardening cleanups, batchable into one commit.
10. **AP-3** — only after deciding the fate of `auralis/optimization/parallel/`.

---

## Coverage Gaps

Declared honestly so the next pass knows where to look:

- **Dimension 5 (Frontend)** received the least depth. I traced the WebSocket connection lifecycle, the `player_state`/`position_changed` sync path, and the reconnect/replay machinery. **Not** covered: optimistic-update reconciliation across `store/slices/`, `AbortController` usage in `services/api/`, AudioContext/MediaSource lifecycle races in `services/audio/`, and rapid-action de-duplication in the transport hooks. A dedicated `audit-frontend` or a re-run of this dimension is warranted.
- **`auralis/analysis/fingerprint/`** (56 files) was checked only at the service boundary (`FingerprintService.get_or_compute` under `_fingerprint_lock`). Its internal batch/streaming analyzer threading was not traced.
- `auralis-web/backend/services/library_auto_scanner.py` and `auralis/services/fingerprint_queue.py` were not read in full; the scan-slot semaphore in `auralis/library/manager.py` was verified but the scanner's own worker lifecycle was not.
- No tests were run (per instructions and the known hangs in `tests/backend/test_system_api.py` / `tests/concurrency/test_thread_safety.py`). All findings are static-analysis-derived; the trigger conditions are reasoned from code, not observed.

---

## Suggested Next Step

```
/audit-publish docs/audits/AUDIT_CONCURRENCY_2026-07-25.md
```

Publish labels: severity (`high` / `medium` / `low`) + `concurrency` + `bug`, plus the domain label per finding (`player`, `backend`, `streaming`, `library`, `frontend`, `dsp`).
