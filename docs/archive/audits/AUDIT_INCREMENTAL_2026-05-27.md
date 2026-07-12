# Incremental Audit — 2026-05-27

**Range**: `HEAD~11..HEAD` (commits 059ac4ad → 3b7b8104)
**Method**: Self-review of the session's 11 commits — was the work complete? Did any of the fixes introduce contract breaks, lock-ordering hazards, or new gaps?
**Tone**: skeptical of my own work; assume bugs.

## Change Summary

52 files changed (+2 121, −1 196). The 11 commits split cleanly into four arcs:

1. **Frontend brand + redux + tests** (`059ac4ad..b895b256`, 6 commits) — token-driven AlbumCharacterPane, setCurrentTrackAndSyncQueue thunk, deprecated hook removal, font tokens, Player.test redux Provider.
2. **Backend queue fix** (`4978106b`) — QueueService.set_queue dict-iteration bug.
3. **Concurrency audit batches 1–4** (`d84d701d..75815287`, 4 commits) — player races, DSP shared instances, backend serialisation, playlist schema v016.
4. **Audit report** (`3b7b8104`) — documentation.

## High-Risk Changes (audit focus)

- `auralis/player/enhanced_audio_player.py` — 5 modifications spanning `previous_track`, `next_track`, `seek`, `_auto_advance_next`, `_load_fingerprint_for_file`, `cleanup`. Highest single-file risk surface.
- `auralis/core/{hybrid_processor,simple_mastering}.py` — lock-discipline change on cache-shared DSP instances.
- `auralis-web/backend/services/{playback,queue}_service.py` + `core/state_manager.py` — async event-loop offload + serialisation surface.
- `auralis/library/{models/base,models/core,repositories/playlist_repository}.py` + new migration `migration_v015_to_v016.sql` — schema-level change with backfill.

## Findings

### INC-N-1: PlaylistRepository.create() assigns position=0 to every initial track
- **Severity**: MEDIUM
- **Changed File**: `auralis/library/repositories/playlist_repository.py:39-78` (commit `75815287`)
- **Status**: NEW
- **Description**: Schema v016 added a `position` column to `track_playlist` with `default=0` at the Python level. `PlaylistRepository.create(name, track_ids=[...])` uses the SQLAlchemy relationship assignment `playlist.tracks = tracks` — which generates an INSERT per row with no explicit position, so SQLAlchemy uses the column default of `0` for every row. Every initial track in the playlist gets `position=0`.

  Reproduction (confirmed by running against an in-memory SQLite):
  ```python
  playlist.tracks = [t0, t1, t2]
  session.commit()
  # rows: (t0_id, p_id, 0), (t1_id, p_id, 0), (t2_id, p_id, 0)
  ```

  Downstream effects:
  - `Playlist.tracks` relationship has `order_by=track_playlist.c.position`, so the listed track order falls back to row-insertion / rowid tie-break — non-deterministic across DB engines.
  - `reorder_track` issues `UPDATE WHERE position > from_index AND position <= to_index` — but every row has position=0, so the shift matches nothing. Reorder silently no-ops on a freshly-created playlist.
  - `add_track(playlist_id, track_id)` (append) computes `COALESCE(MAX(position), -1) + 1` and lands at `position=1`. Subsequent appends climb (2, 3, ...) but the initial tracks remain stuck at 0 with the same rowid tie-break ordering.

- **Evidence**: \`auralis/library/repositories/playlist_repository.py:55-58\`
  ```python
  if track_ids:
      tracks = session.execute(select(Track).where(Track.id.in_(track_ids))).scalars().all()
      playlist.tracks = tracks   # all rows get position=0
  ```
- **Impact**: Every playlist created with initial tracks has its position invariant violated. Hidden because `tests/auralis/library/test_playlist_remove_track_concurrent.py` uses this pattern but only asserts on remove behaviour, not on positions. Reorder operations on freshly-created playlists fail silently.
- **Suggested Fix**: `create()` should assign positions explicitly. Either (a) loop through `track_ids` and call `self.add_track(playlist_id, tid)` after the playlist row is committed, or (b) emit a single `INSERT INTO track_playlist (track_id, playlist_id, position) SELECT id, :pid, row_number() OVER (ORDER BY :order) - 1 FROM tracks WHERE id IN :ids` so the bulk insert assigns sequential positions atomically.

### INC-N-2: state_manager broadcast-under-lock serialises all state mutations behind every WebSocket client's send
- **Severity**: MEDIUM
- **Changed File**: `auralis-web/backend/core/state_manager.py:45-84` (commit `b6b51e9a`)
- **Status**: NEW
- **Description**: Commit `b6b51e9a` (#3723 fix) moved `await self._broadcast_state(snapshot)` INSIDE the `async with self._lock:` block. The audit's option (a) was chosen on the assumption that "fan-out to a fixed pool of WS clients on localhost is microseconds". That assumption holds for healthy localhost connections, but breaks for any client that has backgrounded or has TCP-level back-pressure:

  - `ConnectionManager.broadcast` iterates clients sequentially: `for connection in connections_snapshot: await connection.send_text(...)`.
  - A single client whose receive buffer is full holds up `send_text` for the OS-level TCP timeout (minutes).
  - With my fix, every other `state_manager.update_state(...)` call now waits on `_lock` for the duration. Position updates, track changes, play/pause state — all queue.

  This is a real regression vs the prior behaviour, where `state_manager._lock` was released before broadcast, so mutations could proceed even if the broadcast was slow. The previous code was racy (BST-N-4) but cheap; the new code is correct but can wedge.

- **Evidence**: `auralis-web/backend/core/state_manager.py:81-83` (under the same `async with self._lock`):
  ```python
  state_snapshot = self.state.model_copy(deep=True)
  await self._broadcast_state(state_snapshot)  # holds _lock for full broadcast
  ```
  And `auralis-web/backend/config/globals.py:94-122` — `ConnectionManager.broadcast` loops `await connection.send_text(...)` sequentially per-connection.

- **Impact**: Healthy localhost: no observable change (microsecond broadcasts). One slow / backgrounded / suspended Electron client: ALL state mutations stall until that client's TCP send completes or times out (default minutes). Position updates miss their 1 s tick; play/pause feel frozen.
- **Suggested Fix**: Switch to the audit's option (b) — monotonic `_update_seq` counter inside the lock window, include `seq` in the broadcast payload, and have the frontend reducer drop `seq < last_seen`. The lock then only covers the snapshot + seq increment (microseconds). Alternatively, broadcast to clients in parallel (`asyncio.gather(*[c.send_text(...) for c in conns])`) so a single slow client doesn't block siblings.

### INC-N-3: ProcessorFactory cache key shape change breaks any external monkeypatch that constructs the tuple directly
- **Severity**: LOW
- **Changed File**: `auralis-web/backend/core/processor_factory.py:75-127, 183-186` (commit `47ae0db9`)
- **Status**: NEW
- **Description**: `_get_cache_key` returns a 5-tuple now (was 4-tuple). Code that introspects `_processor_cache` keys keeps working because the only existing introspection is `key[0]` for `track_id` (line 308). But any external test or hot-patch that builds the key by hand to inject a processor would silently fail (tuple of wrong length is never `in` the dict).

  I grepped the live tree and found zero external constructors of the cache key — so this is currently latent. Filing because the existing `cleanup_for_track` (line 305) uses positional unpacking on the key, which is fragile. A future cleanup function that wants to dedupe by (preset, intensity) would have to know the tuple layout.

- **Evidence**: `auralis-web/backend/core/processor_factory.py:308`:
  ```python
  keys_to_remove = [key for key in self._processor_cache if key[0] == track_id]
  ```
- **Impact**: None today. Forward-compat hazard: any introspector that uses fixed slice indices (`key[3]` etc.) is fragile across future key extensions.
- **Suggested Fix**: Replace the tuple with a `NamedTuple` (`CacheKey(track_id, preset, intensity, config_hash, targets_hash)`) so name-based access protects callers from positional drift. Low urgency.

### INC-N-4: PlaybackService.play()/pause()/stop() to_thread wrap arrives BEFORE the state_manager update
- **Severity**: LOW
- **Changed File**: `auralis-web/backend/services/playback_service.py:130-140, 164-174, 196-205, 235-245` (commit `d84d701d`)
- **Status**: NEW
- **Description**: The new ordering is `await asyncio.to_thread(self.audio_player.play)` → `await player_state_manager.set_playing(True)` → `await connection_manager.broadcast({playback_started})`. This is correct ordering for a SUCCESSFUL play. But if the engine call raises, the broadcast was already going to fire (in the old code it didn't, because the engine call was sync and any exception aborted before broadcasting). The `try/except` at line 150 catches and re-raises but does NOT undo the partial broadcast on the engine-fail-after-state-update branch.

  Concretely: today none of `play/pause/stop` raise from the engine in normal use (they're cheap state-machine calls). But `seek()` can raise (the underlying `playback.seek` clamps but doesn't raise; the only realistic path is a torn `is_loaded()` race after #3713). If seek somehow raises post-to_thread but pre-broadcast, the broadcast still fires.

  Looking again — actually the broadcast is in a try-block; if an exception fires before `await self.connection_manager.broadcast(...)`, the broadcast doesn't run. So this is fine for the seek path.

  The actual concern: between `await asyncio.to_thread(self.audio_player.play)` returning success and the subsequent `state_manager.set_playing(True)`, another concurrent `pause()` request could land and call `state_manager.set_playing(False)`. Two concurrent play/pause requests now race on whose `set_playing` call wins — the engine sees play→pause but the state_manager may publish them in reverse order.

  This is the same race as BST-N-4 generalised to non-set_track endpoints. Same root cause, same proposed fix (seq counter).

- **Impact**: Rare. Frontend rate-limits play/pause via debounce; concurrent same-user requests are uncommon. If they happen, the UI briefly shows the wrong state until the next `position_changed` tick.
- **Suggested Fix**: Same seq-counter approach as INC-N-2 — apply it uniformly to all `update_state` callers.

### INC-N-5: enhanced_audio_player.next_track holds _audio_lock across _schedule_fingerprint_load + record_track_completion + play
- **Severity**: LOW
- **Changed File**: `auralis/player/enhanced_audio_player.py:387-413` (commit `d84d701d`)
- **Status**: NEW
- **Description**: PTS-N-1's fix wraps the whole `next_track` body in `_audio_lock` to keep the swap-and-seek atomic. Side-effect: `record_track_completion()` (which fires callbacks), `_schedule_fingerprint_load()` (which spawns a daemon thread), and `playback.play()` are all now called WITH `_audio_lock` held.

  - `record_track_completion` triggers callbacks. Each callback runs synchronously while we hold `_audio_lock`. If a registered callback wants to call back INTO the player (e.g., a UI sync layer that calls `player.is_playing()`), it'd succeed because RLock allows reentry from the same thread — but if it dispatches to a DIFFERENT thread (asyncio task) that thread blocks until next_track returns.
  - `_schedule_fingerprint_load` spawns a daemon thread. The daemon doesn't hold `_audio_lock`, so it's fine.
  - `playback.play()` takes `PlaybackController._lock`. Nesting `_audio_lock → _lock` is the canonical order (used in `get_audio_chunk` and the new seek), so no inversion risk.

  This is a "is the blast radius wider than necessary" finding, not a correctness bug. The actual swap/reset only needs the lock for two operations (`advance_with_prebuffer` and `playback.seek(0, ...)`); the rest could run outside.

- **Impact**: Latency-sensitive callbacks registered on `record_track_completion` run with `_audio_lock` held, blocking the audio callback thread for the duration of the callback work.
- **Suggested Fix**: Tighten the lock to just the swap + seek, then release before `record_track_completion`, `_schedule_fingerprint_load`, and `play`:
  ```python
  with self.file_manager._audio_lock:
      was_playing = self.playback.is_playing()
      advanced = self.gapless.advance_with_prebuffer(was_playing)
      if advanced:
          self.playback.seek(0, self.file_manager.get_total_samples())
  if not advanced:
      return False
  # Now outside the lock for non-time-critical work
  self.integration.record_track_completion()
  ...
  ```

### INC-N-6: Per-channel test coverage gaps for shipped concurrency fixes
- **Severity**: LOW
- **Changed File**: many (commits `d84d701d`, `47ae0db9`, `b6b51e9a`)
- **Status**: NEW
- **Description**: Several behaviour changes from the concurrency audit shipped without dedicated regression tests. The fixes are individually sound (verified by code review and smoke tests), but the absence of tests means a future refactor can silently regress them. Listed in priority order:

  | Fix | What's untested |
  |---|---|
  | #3712 `previous_track` uses `_stop_requested` | No deterministic test that "previous while playing resumes". |
  | #3713 `seek` holds `_audio_lock` across the seek | Concurrency-stress test for seek-during-gapless-advance is hard to make non-flaky. |
  | #3716 `PlaybackService.{play,pause,stop,seek}` use `to_thread` | No test mocks the engine to sleep and asserts the event loop isn't blocked. |
  | #3718 `_advance_generation` compare-and-clear under lock | No concurrency-stress test for duplicate advance threads. |
  | #3719 `_load_fingerprint_for_file` lock across check+act | No test for stale-fingerprint-overwrite. |
  | #3722 `set_volume` route as broadcast-only | No test verifying the route still broadcasts without calling the engine. |
  | #3727 `_cleanup_in_progress` event | No test exercising the slow-load + cleanup race. |
  | #3728 scanner `should_stop` Event | Existing tests pass, but none directly exercise `stop_scan()` mid-batch. |

- **Impact**: Future refactors of these surfaces have no regression net. The fixes themselves are stable; this is technical debt.
- **Suggested Fix**: Add at minimum deterministic tests for #3712 (trivial) and #3722 (trivial). The concurrency-stress tests can be omitted as flaky-by-nature.

## Cross-Layer Impact

Checked all six cross-layer contracts; **no breaks found**:

- **Audio engine ↔ Backend**: `HybridProcessor.process()` signature unchanged. `set_fixed_mastering_targets()` signature unchanged (only adds internal locking). `ProcessorFactory.get_or_create()` signature unchanged. The cache-key shape change is internal to ProcessorFactory.
- **Backend routes ↔ Frontend**: `/api/player/{play,pause,stop,seek,volume,queue}` request/response schemas unchanged. The to_thread wrap is invisible to clients.
- **WebSocket message format**: `player_state` payload shape unchanged. `volume_changed` payload unchanged (still `{volume: 0-100}`).
- **Schema migration v016**: `track_playlist` reshape includes a `position` column; existing repository callers and the `Playlist.tracks` relationship are updated to match. Frontend doesn't query the table directly.
- **Rust DSP**: not touched in this window.
- **Repository pattern**: `PlaylistRepository.{create, add_track, remove_track, reorder_track, clear}` — `create` has the position bug (INC-N-1), the others are correct.

## Missing Test Updates (compounded with INC-N-6)

- `test_playlist_add_track_concurrent.py` covers add_track + reorder_track + remove_track concurrency, but does NOT cover `create()` with initial tracks. The INC-N-1 position-0 bug would have been caught by:
  ```python
  def test_create_with_initial_tracks_assigns_sequential_positions(self, ...):
      playlist = playlist_repo.create('P', track_ids=track_ids)
      rows = _positions_for_playlist(session_factory, playlist.id)
      assert [pos for _, pos in rows] == list(range(len(track_ids)))
  ```

## Verdict

The 11-commit window shipped a substantial volume of changes (52 files, 19 issue closures, 4 commit batches) with **one real medium-severity bug** (INC-N-1: create() position handling), **one architectural trade-off worth re-examining** (INC-N-2: lock-held broadcast can stall under slow clients), and **scattered low-priority gaps** around forward-compat hazards and test coverage.

No CRITICAL or HIGH findings. The concurrency audit follow-ups themselves do what their issue bodies promised.

## Prioritized Fix Order

1. **INC-N-1** — `PlaylistRepository.create()` position assignment. Real correctness bug; small fix; covers a code path tests exercise.
2. **INC-N-2** — state_manager lock-held broadcast. Architectural; user-visible under slow-client conditions. Best to switch to seq-counter approach now while the change is fresh in memory.
3. **INC-N-5** — tighten `next_track` lock scope. Low-impact refactor; only matters for callback-heavy registrations.
4. **INC-N-6** — add deterministic regression tests for `previous_track` and `set_volume`. Trivial; closes obvious gaps.
5. **INC-N-3, INC-N-4** — defer; latent / low-frequency.

---

*Suggest next*: `/audit-publish docs/audits/AUDIT_INCREMENTAL_2026-05-27.md` to create issues for the 6 NEW findings (1 MEDIUM + 1 MEDIUM + 4 LOW).
