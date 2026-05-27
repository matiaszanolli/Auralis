# Concurrency & State Integrity Audit — 2026-05-26

**Auditor**: Claude Opus 4.7 (automated)
**Scope**: Player thread safety, audio processing pipeline, backend streaming, library/database, frontend state
**Dimensions**: 5 parallel agents (Sonnet/Opus) with manual merge, deduplication, and verification of prior findings
**Method**: Deep — full execution-path tracing, with re-read verification of every prior finding from `AUDIT_CONCURRENCY_2026-03-25.md`

## Executive Summary

19 concurrency findings: **0 CRITICAL, 5 HIGH, 9 MEDIUM, 5 LOW**.

The good news: 16 of 32 prior findings from the 2026-03-25 audit have been verified as fixed (AutoMasterProcessor lock, position snapshot, atomic load-and-stop, scanner cancellation, gapless prebuffer, callback-outside-lock, atomic playlist DELETE, lazy-load eager fixes, seek-path lock coverage, chunk-tail check-then-set, `_stop_requested` ordering, batched `get_by_ids`, scan-complete payload). The earlier `_audio_lock` split, sample-count assertions, dtype guards, and `setCurrentTrackAndSyncQueue` thunk all hold up under re-audit.

The bad news: 2 regressions of previously-closed HIGH findings, the HybridProcessor cache HIGH from March was never actually fixed (and got worse), and a new HIGH around backend sync-on-event-loop calls was missed by every prior audit.

**Most impactful clusters:**

1. **HybridProcessor cache races, doubled down by #3530** (APP-2-1, APP-2-3) — Concurrent same-key requests share the cached instance with no per-processor lock. #3530 added a *mutating* `set_fixed_mastering_targets` call on every cache hit, swapping parameters mid-track on the in-flight caller. This is a regression of CONC-07/08 with worse symptoms; HIGH.

2. **Player state regression cluster** (PTS-R-1, PTS-R-2) — Two HIGH regressions from the player layer's recent refactor wave. `previous_track()` now never resumes playback (deterministic, user-visible). The `seek()` fix from #3357 only made the `max_samples` snapshot atomic, not the seek call itself — a gapless transition to a shorter track during a user seek still violates the position invariant.

3. **Backend sync-on-event-loop** (BST-N-1) — `PlaybackService.{play,pause,stop,seek,set_volume}` call sync engine methods directly on the FastAPI event loop. `seek()` can block for seconds during concurrent `load_file()`, freezing the worker and stalling every other request. This pattern is correctly handled in `QueueService.set_queue` — `PlaybackService` is the outlier. Bonus: `set_volume` is a silent no-op because the engine method doesn't exist (`hasattr` returns False).

4. **HIGH-severity instance-state DSP cluster** (APP-2-2) — `SimpleMasteringPipeline._notches` is written inside `process()` and read on every chunk. Concurrent `process()` calls on a shared instance cross-contaminate DSP parameters mid-track.

5. **Auto-advance + fingerprint TOCTOU** (PTS-N-2, PTS-N-3) — The compare-and-clear of `_advance_generation` in the finally block of `_auto_advance_next` is not lock-protected; rapid track turnover can spawn duplicate advance threads. The fingerprint-loader's staleness check is similarly unlocked, allowing a stale fingerprint to overwrite the current one.

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 5     |
| MEDIUM   | 9     |
| LOW      | 5     |
| **Total**| **19**|

## Concurrency Matrix

| Component | Lock Type | Status |
|-----------|-----------|--------|
| PlaybackController | RLock (`_lock`) | Correct; `get_state_snapshot` / `get_position_snapshot` verified atomic |
| QueueManager | RLock (`_lock`) | Mostly correct; `previous_track()` reads `current_index` without it (PTS-N-4 LOW) |
| IntegrationManager | RLock (`_position_lock`) | Verified correct (PTS-2 FIXED via `get_position_snapshot`) |
| AutoMasterProcessor | `threading.Lock()` | FIXED (PTS-1) — added per-object lock on every method |
| HybridProcessor (cached) | `OrderedDict` lock only | **STILL RACY** (APP-2-1 HIGH) — cache insertion locked, returned instance is not |
| SimpleMasteringPipeline | None | **RACY** (APP-2-2 HIGH) — `_notches` is per-instance mutable state |
| ProcessorFactory | `threading.Lock()` on cache | **Made worse by #3530** (APP-2-3 MEDIUM) — mutating call on cache hit |
| AudioStreamController | `_active_streams_lock`, `_chunk_tails_lock` | FIXED — seek path now updates `active_streams` under lock |
| ConnectionManager | asyncio.Lock | Verified correct |
| ProcessingEngine | `threading.Lock()` (`_jobs_lock`) | Not re-audited this cycle |
| PlaybackService | None | **Bypasses to_thread** (BST-N-1 HIGH) — sync engine calls on the event loop |
| QueueService | None | **No service-level lock** (BST-N-2 MEDIUM) — interleavable `set_queue` calls |
| PlayerStateManager | `_lock` (asyncio.Lock) | Broadcast outside lock → ordering window (BST-N-4 MEDIUM) |
| LibraryScanner | `should_stop: bool` | Works under GIL; bool not Event (BST-N-5 LOW) |
| TrackRepository | Session-per-call | Correct contract; only `queue_service.py` misused it (fixed today) |
| PlaylistRepository | None on add | **No DB-level uniqueness** (LDB-26-1 MEDIUM) — concurrent ADDs duplicate |
| MigrationManager | File lock + `pool_pre_ping=True` | All 3 library engines now covered (FIXED via #3702, #3682) |
| Rust DSP (PyO3) | `py.allow_threads + catch_unwind` | Verified correct on all 12 kernels |
| Redux store | Single-threaded dispatch | Correct; new `setCurrentTrackAndSyncQueue` thunk verified safe |
| WebSocketContext | unmemoed `value` | Cosmetic (FSC-5-1 LOW); no race window |

## Findings

### HIGH (5)

#### PTS-R-1: `previous_track()` never resumes playback — regression of #2684
- **Severity**: HIGH
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:377-401`
- **Status**: Regression of #2684 (the #3361 guard pattern copy-pasted into `previous_track()` interacts pathologically with `load_file()`'s `load_and_stop()`)
- **Trigger Conditions**: User presses "previous" while playing. **Deterministic — no concurrency required.**
- **Evidence**:
  ```python
  def previous_track(self) -> bool:
      was_playing = self.playback.is_playing()      # True
      ...
      if file_path and self.load_file(file_path):    # load_file() → playback.load_and_stop() → state=STOPPED
          # Re-check state to avoid restarting playback after a
          # concurrent stop() call (#3361).
          if was_playing and not self.playback.is_stopped():  # is_stopped() is ALWAYS True here
              self.playback.play()                            # never reached
          return True
  ```
  `playback.load_and_stop()` (`playback_controller.py:185-203`) unconditionally writes `self.state = PlaybackState.STOPPED`. After `self.load_file(...)` returns, `self.playback.is_stopped()` is True, so `not self.playback.is_stopped()` is False. `play()` is unreachable.
- **Impact**: Pressing "previous track" while playing always halts playback. User-visible functional regression.
- **Suggested Fix**: Use `_stop_requested.is_set()` as the cancellation signal instead:
  ```python
  if was_playing and not self._stop_requested.is_set():
      self.playback.play()
  ```

#### PTS-R-2: `seek()` bounds-check uses stale `max_samples` after lock release — partial regression of #3357
- **Severity**: HIGH
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:157-177`
- **Status**: Regression of #3357 (closed 2026-03-26; the original fix was incomplete)
- **Trigger Conditions**: User-initiated seek concurrent with a gapless auto-advance into a shorter track.
- **Evidence**:
  ```python
  with self.file_manager._audio_lock:
      if not self.file_manager.is_loaded():
          return False
      max_samples = self.file_manager.get_total_samples()  # 10-min track → 26 460 000
      sample_rate = self.file_manager.sample_rate
  # _audio_lock released
  position_samples = int(position_seconds * sample_rate)
  return self.playback.seek(position_samples, max_samples)  # clamp uses stale 26.4M
  ```
  After lock release, a gapless `advance_with_prebuffer` can swap `audio_data` to a shorter track (e.g. 3-min, length 7.9M). The seek then writes a position > new track length, producing silence + immediate auto-advance.
- **Impact**: Position invariant `position <= len(audio_data)` violated. Returns silence until the next chunk fires another auto-advance, effectively skipping the new track.
- **Suggested Fix**: Hold `_audio_lock` across the entire `playback.seek()` call (no lock-inversion risk — `PlaybackController.seek()` only takes its own `_lock`):
  ```python
  with self.file_manager._audio_lock:
      if not self.file_manager.is_loaded():
          return False
      max_samples = self.file_manager.get_total_samples()
      sample_rate = self.file_manager.sample_rate
      position_samples = int(position_seconds * sample_rate)
      return self.playback.seek(position_samples, max_samples)
  ```

#### APP-2-1: Cached `HybridProcessor` still shared across concurrent requests — CONC-07/08 regression amplified
- **Severity**: HIGH
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/core/processor_factory.py:150-206` (`ProcessorFactory.get_or_create`); `auralis/core/hybrid_processor.py:530-562` (`_get_or_create_processor`)
- **Status**: NEW (regression of CONC-07/08 — original fix never shipped; #3530 made it worse)
- **Trigger Conditions**: Two concurrent requests for the same `(track_id, preset, intensity)` cache key (same user opening two players, prefetch + active stream, frontend reconnect bursts).
- **Evidence**:
  - Factory `_lock` guards only `OrderedDict` insertion (`processor_factory.py:155`). Two callers on the same cache key receive the **identical instance** (line 168) and both invoke `processor.process(...)` outside the lock.
  - `HybridProcessor` stores mutable per-call DSP state on `self` (`self.current_targets` set by `set_fixed_mastering_targets`, `hybrid_processor.py:168`). Concurrent process() calls share that state.
  - **#3530 worsened this**: `processor_factory.py:166-167` re-applies `mastering_targets` on every cache hit. Caller A mid-process can have its remaining chunks switch DSP parameters when caller B hits the cache with different targets.
  - The module-level cache in `_get_or_create_processor` has the identical shape.
- **Impact**: Wrong DSP applied (LUFS/EQ/compression bleed between concurrent tracks), audible parameter swap mid-track on cache hit, potential NumPy buffer aliasing inside `HybridProcessor` state.
- **Suggested Fix**: Wrap each cached processor in a `(processor, threading.RLock)` tuple — callers `with lock: processor.process(...)`. Or push per-track state out of the instance into a parameter to `process()`. The cache-hit re-apply (#3530) must happen inside the per-instance lock.

#### APP-2-2: `SimpleMasteringPipeline._notches` shared across concurrent `process()` calls
- **Severity**: HIGH
- **Dimension**: Audio Processing
- **Location**: `auralis/core/simple_mastering.py:47` (`self._notches: list[Notch] = []`), written at 124 + 151, read inside the chunk loop at 613.
- **Status**: NEW
- **Trigger Conditions**: Same `SimpleMasteringPipeline` instance used for two concurrent `process()` invocations. Today this only happens if a caller deliberately reuses the instance, but the factory `create_simple_mastering_pipeline()` at line 1518 invites it, and the docstring at line 613 ("applied to every chunk via `self._notches`") makes the instance-state contract explicit.
- **Evidence**: `process()` writes `self._notches = []` then `self._notches = self._contextualize_notches(...)` then iterates chunks reading `self._notches`. Two concurrent calls race on the attribute; one track's resonance notches will be applied to the other.
- **Impact**: Cross-track DSP contamination — Track B gets Track A's resonance notch frequencies/depths, audibly mis-EQ'ing a track with notches it didn't analyze. `prev_tail` is correctly local; only the notch state races.
- **Suggested Fix**: Pass `_notches` as a local argument through `process()` → `_process()` → `_apply_notches()`. Or add an instance `_process_lock = threading.RLock()` and document single-active-call semantics.

#### BST-N-1: `PlaybackService.{play,pause,stop,seek,set_volume}` bypass `asyncio.to_thread` — sync engine calls on the event loop
- **Severity**: HIGH
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/playback_service.py:130, 164, 196, 237, 278`
- **Status**: NEW
- **Trigger Conditions**: Any client POST to `/api/player/{play,pause,stop,seek,volume}`. Manifests visibly when one of these coincides with another engine operation that holds an internal lock (e.g. `load_file()`, gapless `advance_with_prebuffer()`, a queue swap).
- **Evidence**:
  ```python
  # services/playback_service.py:130 / 164 / 196 / 237 / 278
  self.audio_player.play()                # sync — RLock + state mutation
  self.audio_player.pause()
  self.audio_player.stop()
  if hasattr(self.audio_player, 'seek'):
      self.audio_player.seek(position)    # sync — file_manager._audio_lock held
  if hasattr(self.audio_player, 'set_volume'):
      self.audio_player.set_volume(volume)  # silent no-op — see BST-N-3
  ```
  `QueueService.set_queue` correctly offloads via `await asyncio.to_thread(...)`. `PlaybackService` is the outlier. `seek()` acquires `file_manager._audio_lock`, which a concurrent `load_file()` reading a 100MB FLAC can hold for hundreds of ms to seconds.
- **Impact**: Pause/stop/play during a concurrent track-load or queue change freezes the FastAPI worker. `_position_update_loop` misses its 1s tick → frontend position cursor jumps. Other in-flight HTTP requests stall. Violates the documented invariant.
- **Suggested Fix**:
  ```python
  await asyncio.to_thread(self.audio_player.play)
  await asyncio.to_thread(self.audio_player.pause)
  await asyncio.to_thread(self.audio_player.stop)
  await asyncio.to_thread(self.audio_player.seek, position)
  ```

### MEDIUM (9)

#### PTS-N-1: `next_track()` leaves position stale between gapless swap and `seek(0)` — gapless audio glitch
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:340-375`
- **Status**: NEW
- **Trigger Conditions**: Auto-advance (or manual `next_track()`) firing while the audio callback is calling `get_audio_chunk()`.
- **Evidence**:
  ```python
  def next_track(self) -> bool:
      was_playing = self.playback.is_playing()
      if self.gapless.advance_with_prebuffer(was_playing):     # swaps audio_data under _audio_lock
          self.integration.record_track_completion()
          # position is still the END of the OLD track here
          self.playback.seek(0, self.file_manager.get_total_samples())  # resets to 0
  ```
  Between `advance_with_prebuffer` returning and `playback.seek(0, ...)` executing, the audio callback may acquire `_audio_lock` and call `read_and_advance_position(chunk_size)`. It reads the old position (e.g. ~26.4M samples) against the new shorter `audio_data`, returns silence, fires another auto-advance (suppressed by `_auto_advancing`).
- **Impact**: One chunk (~10-50 ms) of silence on every gapless transition — defeats the <10 ms gapless guarantee. Audible click/pop.
- **Suggested Fix**: Reset position inside the gapless swap's critical section:
  ```python
  with self.file_manager._audio_lock:
      self.file_manager.audio_data = audio_data
      self.file_manager.sample_rate = sample_rate
      self.file_manager.current_file = file_path
      self.playback.seek(0, len(audio_data))   # atomic with swap
  ```

#### PTS-N-2: `_advance_generation` compare-and-clear not lock-protected — duplicate advance threads
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:534-539` (vs. spawn at 480-512)
- **Status**: NEW
- **Trigger Conditions**: Rapid track turnover where `_auto_advance_next` for generation N reaches its `finally` block at the same instant another `get_audio_chunk()` increments `_advance_generation` to N+1 and spawns a new advance thread.
- **Evidence**:
  ```python
  # get_audio_chunk (holds _audio_lock):
  self._advance_generation += 1                  # under _audio_lock
  gen = self._advance_generation
  ...spawn thread...

  # _auto_advance_next (NO lock held in finally):
  finally:
      if self._advance_generation == generation: # unlocked compare
          self._auto_advancing.clear()           # unlocked clear
  ```
  Race: thread A (gen=5) reads `== 5` → True. Another `get_audio_chunk` increments to 6 and spawns B. Thread A executes `clear()` — flag now clear while B is still running. Next `get_audio_chunk` sees flag clear, increments to 7, spawns C. B and C both run concurrently.
- **Impact**: Two concurrent `_auto_advance_next` threads → two `next_track()` calls → queue index advances twice from one end-of-track event, skipping a track silently. Possibly audio buffer races between the two `advance_with_prebuffer` calls.
- **Suggested Fix**:
  ```python
  finally:
      with self.file_manager._audio_lock:
          if self._advance_generation == generation:
              self._auto_advancing.clear()
  ```

#### PTS-N-3: `_track_generation` TOCTOU between staleness check and `processor.set_fingerprint()`
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:252-291`
- **Status**: NEW (partially addressed by #3473, but the reader-side race remains)
- **Trigger Conditions**: Rapid track changes — fingerprint loader thread T_A passes the staleness check, then a new `_schedule_fingerprint_load()` spawns T_B before T_A reaches `processor.set_fingerprint()`.
- **Evidence**:
  ```python
  if self._track_generation != generation:    # CHECK — atomic int read (GIL)
      return
  if fingerprint:
      with self._fingerprint_lock:
          self._current_fingerprint = fingerprint
      self.processor.set_fingerprint(fingerprint)  # ACT — may overwrite newer value
  ```
  T_A computed fp for track 5, passes check. User skips to track 6 → T_B spawned. T_B's fp hits cache, passes check, calls `processor.set_fingerprint(fp6)`. T_A (still in flight) calls `processor.set_fingerprint(fp5)` — overwrites fp6.
- **Impact**: Stale fingerprint applied to current track → wrong adaptive-mastering parameters → audible mastering anomaly for ~1 track until next load. Mirrors #3463 but in the opposite direction (stale consumer rather than stale producer).
- **Suggested Fix**: Hold `_fingerprint_lock` across the compare + the processor write:
  ```python
  if fingerprint:
      with self._fingerprint_lock:
          if self._track_generation != generation:
              return
          self._current_fingerprint = fingerprint
          self.processor.set_fingerprint(fingerprint)
  ```

#### APP-2-3: `ProcessorFactory` cache-hit re-application of mastering targets ignores in-flight processing
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/core/processor_factory.py:166-167`
- **Status**: NEW (sub-issue of APP-2-1, broken out because the fix is more localised)
- **Trigger Conditions**: Cache hit on a `(track_id, preset, intensity)` while the previous caller is iterating chunks.
- **Evidence**: `cached.set_fixed_mastering_targets(mastering_targets)` is invoked unconditionally on every cache hit (when targets are provided), even though the cached processor may be actively running `process_chunk(...)` on another thread.
- **Impact**: Targets swap mid-track on the active caller. Even if both callers use identical targets the write is racy with the chunk loop's reads of `self.current_targets`.
- **Suggested Fix**: Only call `set_fixed_mastering_targets` when creating a new processor. If late updates are required, gate on a per-processor `idle` flag (CAS) and reject (or wait) when busy.

#### BST-N-2: `PlaybackService.set_queue` ordering interleavable across concurrent requests
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/queue_service.py:213-297`
- **Status**: NEW
- **Trigger Conditions**: Two near-simultaneous POSTs to `/api/player/queue` (double-click "Play album", rapid playlist switch while network RTT ~50-200 ms).
- **Evidence**: `set_queue` performs 7 awaitable steps with no service-level lock. Each `await` is a yield point. Two concurrent calls A and B can interleave: A reaches step 5 (`load_file` ~hundreds of ms), scheduler runs B which completes steps 2-7 with track-B; then A returns from step 5 and overwrites with track-A and calls `play()` on track-A. Final state: `player_state_manager` reports track-B but the engine plays track-A.
- **Impact**: User-visible "ghost playback" — UI shows track-B, audio plays track-A. Recovery requires manual pause/play. Scales with disk latency for `load_file()`.
- **Suggested Fix**: Serialise `set_queue` with a service-level `asyncio.Lock`:
  ```python
  def __init__(self, ...):
      self._queue_lock = asyncio.Lock()
  async def set_queue(self, ...):
      async with self._queue_lock:
          # existing body
  ```

#### BST-N-3: `PlaybackService.set_volume` is a silent no-op
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/playback_service.py:277-285`; `auralis/player/enhanced_audio_player.py` (no `set_volume` method)
- **Status**: NEW
- **Trigger Conditions**: Any POST to `/api/player/volume` after initial construction. Deterministic, not concurrency-dependent — surfaced during the sync-call invariant audit.
- **Evidence**:
  ```python
  if hasattr(self.audio_player, 'set_volume'):
      self.audio_player.set_volume(volume)
  ```
  `grep -rn "def set_volume\b" auralis/player/` returns no matches in `EnhancedAudioPlayer` or any component. The Protocol declares `set_volume` but the real object doesn't implement it. `hasattr` evaluates False; engine volume never changes. The WS `volume_changed` broadcast fires, so clients see the slider move.
- **Impact**: Volume control silently broken at the engine level. The frontend appears responsive (broadcast echo) but the audio level is unchanged. Hides the regression from manual QA.
- **Suggested Fix**: Either add `set_volume(volume: float)` to `EnhancedAudioPlayer` (delegating to the audio backend's gain stage), or drop the route. If adding, wrap in `await asyncio.to_thread(...)` per BST-N-1.

#### BST-N-4: `state_manager.set_track` lacks per-call sequence guard — out-of-order WS deliveries on rapid track switches
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/state_manager.py:71-96` (`set_track`), `_broadcast_state` (190-195)
- **Status**: NEW
- **Trigger Conditions**: User clicks track A, then quickly clicks track B before A finishes loading.
- **Evidence**: `update_state` releases `_lock` before `_broadcast_state`. Two concurrent `set_track` calls produce snapshots A and B with `_lock` acquired in some order, but the broadcasts run unsynchronised — `await ws_manager.broadcast(...)` can yield, and A's broadcast may complete after B's. No monotonic counter on outgoing `player_state` messages.
- **Impact**: Frontend can render the stale track A after B was selected — visible as 100-500 ms flicker. Self-heals within 1s when `position_changed` ticks resume on B, but rapid scrubbing feels unstable.
- **Suggested Fix**: Either (a) move `_broadcast_state` inside the `_lock` block; or (b) add `_update_seq: int` counter, include `seq` in the payload, have the frontend reducer drop `seq < last_seen`.

#### LDB-26-1: `track_playlist` association has no unique constraint — concurrent `add_track` produces duplicates
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/models/base.py:38-42`, `auralis/library/repositories/playlist_repository.py:180-230`
- **Status**: NEW
- **Trigger Conditions**: Two concurrent `POST /playlists/{id}/tracks` for the same `(playlist_id, track_id)`.
- **Evidence**: Association table defined without PK or unique constraint. `add_track` defends with `SELECT EXISTS` then `playlist.tracks.append(track)` — no row lock between check and insert. Two concurrent requests both pass the EXISTS check and both INSERT silently. `remove_track`'s DELETE deletes only one of them (atomic but `rowcount > 1` possible). Tracks duplicate on read.
- **Impact**: Playlist duplication via fast double-click, retried POST after slow response, or concurrent backend tests. Duplicate rows accumulate silently (some queries DISTINCT them away in the UI).
- **Suggested Fix**: Add `UniqueConstraint('track_id', 'playlist_id')` (or `PrimaryKeyConstraint`) to the `track_playlist` Table. Convert `add_track` to `INSERT OR IGNORE` (SQLite) or try-INSERT + IntegrityError-on-duplicate. Position assignment then needs a separate UPDATE.

#### LDB-26-2: `add_track` position parameter races even on first insert
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/playlist_repository.py:215-218`
- **Status**: NEW (related to LDB-26-1)
- **Evidence**:
  ```python
  if position is not None and 0 <= position <= len(playlist.tracks):
      playlist.tracks.insert(position, track)
  else:
      playlist.tracks.append(track)
  ```
  `len(playlist.tracks)` triggers a lazy SELECT of the full collection (`add_track` re-queries via raw `select(Playlist)` and doesn't eager-load). Two concurrent inserts at `position=None` race on implicit ordering — both see the same `len(...)`; SQLAlchemy's secondary-table ordering is by row-insert order, not an explicit `position` column.
- **Impact**: Visible reordering glitches in the UI after rapid adds; tests of position-based insert are flaky.
- **Suggested Fix**: Either (a) serialize playlist mutation via a per-playlist lock in `PlaylistRepository`, or (b) add an explicit `position` column to `track_playlist` and assign it atomically inside the same transaction (`SELECT MAX(position) + 1` then INSERT).

### LOW (5)

#### PTS-N-4: `previous_track()` reads queue.current_index without `_lock` for rollback baseline
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:389`
- **Status**: NEW (partial — write side fixed by #3668, read side not)
- **Evidence**: `saved_index = self.queue.queue.current_index` — unlocked read of mutable shared int.
- **Impact**: On file-load failure, `rollback_index(saved_index)` may restore a stale value. CPython's GIL guarantees the int read isn't torn, but the value's relationship to the queue contents is racy.
- **Suggested Fix**: Add `snapshot_index()` to `QueueManager` that captures `current_index` under `_lock`.

#### PTS-N-5: `cleanup()` join timeout silently allows `_advance_thread` to write `audio_data` post-clear
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:687-704`
- **Status**: NEW (fix in #3694 covers the common case; timeout path is documented but not handled)
- **Evidence**: `_advance_thread.join(timeout=2.0)` times out; cleanup proceeds; in-flight advance thread later swaps `audio_data` into a freshly-cleared player.
- **Impact**: Post-cleanup, `audio_data` can become non-None again, breaking the test invariant. Benign in production (Electron process exits seconds later); causes intermittent test flakes.
- **Suggested Fix**: After the timeout warning, set a `_cleanup_in_progress` event that the advance thread checks before its final swap; or extend the timeout to the maximum reasonable I/O latency.

#### BST-N-5: Scanner `should_stop` is plain attribute (not `threading.Event`)
- **Severity**: LOW
- **Dimension**: Backend Streaming (scanner cancellation pattern from #3710)
- **Location**: `auralis/library/scanner/scanner.py:51, 76-80, 168-191`
- **Status**: NEW
- **Trigger Conditions**: Works under CPython 3.14 because of the GIL. Would be a data race on a free-threading interpreter (PEP 703) or `python -X gil=0`.
- **Impact**: None today on default CPython. Forward-compat risk for free-threaded Python. Also: large batches don't check `should_stop` mid-batch, so the 5s grace can elapse — but `release_scan_slot()` still fires in the thread's `finally`, so a subsequent scan is correctly rejected via HTTP 409 (no race in the slot itself).
- **Suggested Fix**: Replace `self.should_stop: bool` with `threading.Event()`; reads → `is_set()`, setter → `set()`. Optionally check `should_stop` between files within a batch.

#### LDB-26-3: `normalize_existing_artists` migration leaves engine open on exception
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migrations/normalize_existing_artists.py:64-69`
- **Status**: NEW
- **Evidence**: Standalone migration script calls `create_engine(... pool_pre_ping=True)` with no `try/finally engine.dispose()`. If it raises mid-migration, the engine leaks until process exit.
- **Impact**: Not catastrophic because it's a script (process dies), but inconsistent with `MigrationManager.dispose()` discipline.
- **Suggested Fix**: Wrap migration body in `try/finally`, dispose the engine in `finally`.

#### FSC-5-1: `WebSocketContext` Provider `value` not memoized — fresh object every render
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:479-500`
- **Status**: NEW (style / micro-perf)
- **Evidence**: All seven method members are `useCallback`-stable. `setResumePositionGetter` is an inline arrow created every render. The container object identity changes on every Provider render, so every `useWebSocketContext()` consumer re-renders whenever `isConnected` / `connectionStatus` changes.
- **Race-condition impact**: None. Native `ws.onmessage` / `onopen` execute via the browser event loop, never during React's commit phase. The cleanup/resubscribe window inside React commit is zero from the WS message dispatcher's POV.
- **Suggested Fix**: Wrap in `useMemo` + lift `setResumePositionGetter` to a `useCallback`. Cosmetic; bundle in a broader "context-providers missing `useMemo`" sweep in the next frontend audit.

## Relationships & Compound Races

- **PTS-R-1 + PTS-N-2 + PTS-N-3** all converge on the `next_track` / auto-advance / fingerprint-loader interaction. The three together form a "rapid skip" hotspot: skip A→B fast enough and you can simultaneously (a) fail to resume on the user's "previous" click (PTS-R-1), (b) spawn duplicate advance threads (PTS-N-2), and (c) apply the wrong fingerprint to the wrong track (PTS-N-3). All three are individually low-frequency; together they create a "rapid skip is buggy" reputation.

- **APP-2-1 + APP-2-2 + APP-2-3** are the DSP-instance-state cluster. The shared HybridProcessor cache (APP-2-1), the shared `_notches` attribute (APP-2-2), and the cache-hit re-apply (APP-2-3) all stem from the same underlying assumption that DSP processors are single-active-call objects. The fix in each case is either an instance lock or moving per-call state out of `self`.

- **BST-N-1 + BST-N-2** together produce the worst-case backend regression: a `seek()` request blocks the event loop (BST-N-1) while a concurrent `set_queue` is already partway through its 7-await sequence (BST-N-2). The frontend sees stalled position updates and an inconsistent track display — the two surfaces compound into "the backend is broken" UX.

- **LDB-26-1 + LDB-26-2** are inseparable: any fix to one shape requires touching the other. Adding the unique constraint forces position handling to be explicit.

## Prioritized Fix Order

1. **PTS-R-1** (`previous_track()` never resumes) — HIGH, deterministic, user-visible, one-line fix.
2. **BST-N-3** (`set_volume` silent no-op) — MEDIUM but trivially testable; the route is misleading.
3. **PTS-R-2** (`seek()` stale `max_samples`) — HIGH, real but lower-frequency than PTS-R-1.
4. **BST-N-1** (`PlaybackService` sync-on-event-loop) — HIGH, 5 one-line `await asyncio.to_thread(...)` wraps.
5. **APP-2-3 then APP-2-1** (HybridProcessor cache) — fix APP-2-3 first (skip the mutating call on cache hit) as a stop-gap; APP-2-1 needs per-instance lock design.
6. **APP-2-2** (`SimpleMasteringPipeline._notches`) — pass as local; affects fewer call sites than the HybridProcessor fix.
7. **PTS-N-1 / PTS-N-2 / PTS-N-3** — three small fixes, do as a batch.
8. **BST-N-2** (`set_queue` ordering) — service-level `asyncio.Lock`, three-line patch.
9. **BST-N-4** (WS ordering) — add monotonic counter to outgoing `player_state`; frontend reducer drops stale.
10. **LDB-26-1 + LDB-26-2** — schema migration + repository refactor; lower urgency because race window is small in practice.
11. **LOW findings** — bundle into a single follow-up commit; no urgency.

## Verified Fixed Since Prior Audit (2026-03-25)

The following findings from `AUDIT_CONCURRENCY_2026-03-25.md` are confirmed fixed in current code:

**Player layer**:
- PTS-1 (AutoMasterProcessor no per-object lock) — fixed: `auralis/player/realtime/auto_master.py:34` now has `threading.Lock()` on every method.
- PTS-2 (`_get_position_seconds` no controller lock) — fixed via `get_position_snapshot()`.
- PTS-4 (`add_to_queue` non-atomic) — re-architected (#3656): the TOCTOU is now intentional and documented; file I/O is outside the critical section.
- PTS-5 (`next_track()` restarts after stop) — fixed for `next_track()` via the `was_playing and not is_stopped()` pattern (but see PTS-R-1: the same pattern copy-pasted into `previous_track()` broke it).
- PTS-6 (`load_track_from_library` non-atomic) — fixed via `load_and_stop()`.
- PTS-8 (`_auto_advancing` cleared prematurely) — fixed via #3350 compare-and-clear (but see PTS-N-2: the compare-and-clear itself is racy).
- PTS-10 (callback registration ordering) — fixed with warning on late registration.

**Backend streaming**:
- DIM-3-01 (`active_streams` not updated in seek path) — fixed: `audio_stream_controller.py:1673-1674` wraps in `_active_streams_lock`.
- Chunk-tail check-then-set race (#2326) — fixed via `_chunk_tails_lock` covering the full sequence.
- #3669 (`_stop_requested` clear-vs-set race) — fixed.
- #3554 (per-track sync calls in `set_queue` blocking event loop) — fixed via batched `get_by_ids` + `asyncio.to_thread`.
- #3502 (`scan_complete` payload mismatch) — fixed; both paths emit canonical superset.

**Library/DB**:
- DB-C-01 (migration session leak) — fixed via bounded sessions with `pool_pre_ping=True`.
- DB-C-04 (playlist lazy-load race in `remove_track`) — fixed via atomic DELETE (#3340).
- CONC-04 (playlist `DetachedInstanceError` on read) — fixed via `selectinload` + `expunge_all` (#3707, #3709).

**DSP**:
- #3355 / #3673 (band_filters input aliasing) — fixed: all worker submissions pass `audio.copy()`; fallback path captures `audio` before worker submission.
- #3700 (DSP sample-count invariant assertion) — present in `simple_mastering.py:242-245`.
- #3701 (AudioFingerprintAnalyzer class-level executor) — **safe**: all sub-analyzers verified as pure functions; double-checked locking on `_get_executor` correct.
- Rust GIL boundary — correct: all 12 heavy kernels use `py.allow_threads + catch_unwind`.

**Frontend state**:
- FSC-1 (`handleNext/handlePrevious` stale read) — fixed in #3587 via `setCurrentTrackAndSyncQueue` thunk.
- FSC-3 (`usePlayNormal` subscribes inside `playNormal()`) — fixed in #3377 via dedicated mount-only `useEffect` + pending-chunks queue.

**Scanner cancellation pattern (#3710)** — verified functionally correct: the `shield + stop_scan + wait_for` pattern delivers cancellation; `release_scan_slot()` runs in the worker thread's `finally`, so a new scan racing the old thread is rejected via HTTP 409 (no race in the slot).

## Still-Open Prior Findings (Not Re-Verified)

- PTS-9 (advance_with_prebuffer peeks twice) — tracked as #3352.
- FSC-2 (`usePlayerAPI` private state) — deprecated, migration incomplete.
- FSC-4 (singleton stale after rapid skips + WS disconnect) — refactored away under that name; deferred to a streaming-resume audit.
- CONC-07/08 (HybridProcessor cache) — re-filed as APP-2-1 above.
- #3438 (Fingerprint daemon threads survive cleanup) — still open.

---

*Report generated 2026-05-26 by Claude Opus 4.7 (audit-concurrency orchestrator + 5 dimension agents).*

*Suggest next*: `/audit-publish docs/audits/AUDIT_CONCURRENCY_2026-05-26.md` to create GitHub issues for the 14 NEW findings (5 HIGH, 9 MEDIUM, 5 LOW — minus the 2 regressions which should be re-opened against the original issue numbers).
