# Concurrency & State Integrity Audit — 2026-08-13

**Scope**: race conditions, missing locks, thread-safety violations, state-machine
bugs, unsafe concurrent access across all five dimensions (player, audio
processing, backend streaming, library/database, frontend state).

**Method**: fresh read of the working tree at `master` (`188db72a`). No prior
audit report was used as a source; the three prior concurrency reports
(2026-07-12 / 07-25 / 07-29) were consulted for deduplication only, alongside
292 open and 2,000 closed GitHub issues.

**Baseline note**: this audit lands one commit after `674162c7`
("fix: let a caller-targeted cancellation escape `drain_cancelled_task` (#5083)",
2026-08-13). That commit is the direct cause of the highest-severity finding
below — it is correct in isolation but changed the exception contract of a helper
that three `finally:` blocks depend on.

**Protocol correction applied**: `.claude/commands/_audit-common.md:23` instructs
auditors that `auralis/optimization/` has "NO production code imports — the only
importers are tests" and to "cap severity accordingly." **That statement is false**
and was corrected mid-audit; the package was then re-analyzed without the cap. See
**C2-3** for the tooling defect and **C2-2** for what the re-analysis found. The
verified import chain is `auralis/core/hybrid_processor.py:27` →
`optimization.performance_optimizer.get_performance_optimizer`, used at `:139`,
`:566`, and inside `_apply_module_optimizations()` which executes at **module import
time** (`:642`) and monkey-patches `AdaptiveMode.process` for every mastering call.

---

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 4 |
| LOW | 6 |
| **Total** | **13** |

HIGH: C3-1, C3-2, C1-1 · MEDIUM: C3-3, C4-1, C1-2, C2-2 · LOW: C2-3, C2-1, C3-4, C4-2, C4-3, C4-4

### Key themes

1. **Cancellation contracts are the weak seam.** Two of the three HIGH findings
   and one MEDIUM all stem from the same place: a `CancelledError` delivered to a
   *calling* task versus a cancellation of an *awaited* task. `#5083` fixed the
   distinction in one helper (`drain_cancelled_task`) but (a) its new re-raise
   escapes through three `finally:` blocks *before* the semaphore is released, and
   (b) two sibling call sites in `ws_handlers/playback_commands.py` still use the
   blanket `except (asyncio.CancelledError, Exception): pass` that `#5083` was
   filed to remove.

2. **Per-instance guards standing in for cross-instance guards.** Two independent
   findings share this shape: `LibraryScanner._active_paths` (the #3455 duplicate-
   scan guard) and the streaming path's ownership of `ChunkedAudioProcessor`. In
   both cases the object carrying the guard/lifecycle is constructed fresh per
   request, so the protection it advertises never actually spans the concurrent
   callers it was written for.

3. **The mature parts are genuinely mature.** The player module, the Rust PyO3
   boundary, the engine chunk loop, the migration double-lock, the chunk-cache
   atomic-write layer, and the frontend's stream-epoch/sequence guards were all
   examined in depth and found sound. Several currently-OPEN issues (#3785, #4219,
   #4102) were verified as already fixed in live code and are **not** re-reported;
   several CLOSED ones (#4574, #3786, #4141, #3443) were verified as **not**
   regressed.

4. **Identity-keyed state is a recurring anti-pattern.** Three separate places key
   long-lived state on `id()` of an object they do not hold a reference to
   (`MemoryPool.allocated_buffers` — C2-2; `_get_or_create_processor`'s cache key —
   C2-1; historically `ws_id()`, since fixed). CPython reuses addresses after GC, so
   every one of these is a latent wrong-object bug. `SmartCache._identify` (#4524)
   and `ProcessorFactory._get_cache_key` show the correct content-hash approach and
   are the models to copy.

### Most impactful races

- **C3-1** is the one to fix first: it is a *permanent, unrecoverable* resource
  leak reachable on an ordinary seek or track change, it compounds, and after 10
  occurrences all audio streaming in the session fails with "Server busy". It was
  introduced yesterday and its regression test does not cover the path. Verified
  by a standalone asyncio reproduction (see Evidence).
- **C3-2** leaks a full-track float WAV per play for FFmpeg-only formats
  (`.m4a`/`.aac`/`.wma`) — ~212 MB for a 10-minute stereo track — and the startup
  temp sweep does not match the directory prefix, so it never self-heals.
- **C1-1** leaves the "now playing" metadata permanently describing a different
  track than the audio actually loaded.

---

## Concurrency Matrix

| Component | Primary synchronization | Status |
|---|---|---|
| `PlaybackController` | `threading.RLock` (`_lock`) + deferred-notify queue | Sound — snapshot-in-lock / notify-out-of-lock throughout |
| `AudioFileManager` | `threading.RLock` (`_audio_lock`) | Sound for its own methods; bypassed by 2 raw getters (C1-2) |
| `QueueController` / `queue_manager` | `threading.RLock` | Sound — `advance_if_next_matches` closes the prebuffer-commit TOCTOU |
| `GaplessPlaybackEngine` | `RLock` + `Lock` + `Event` | Sound — documented `_audio_lock → update_lock` nesting invariant holds |
| `IntegrationManager` | `RLock` (`_position_lock`) + 2 `Lock`s | Sound per call; **not** serialized across two full loads (C1-1) |
| `AudioPlayer` facade / `PlayerPropertiesMixin` | delegates | 4 raw unlocked getters remain (C1-2) |
| Player fingerprint loader | `Lock` + generation counter | Sound — newest generation wins, all 3 write sites verified |
| `HybridProcessor` | `threading.RLock` (`_process_lock`) on `process()` + every public setter | Sound — no half-applied targets/fingerprint/profile |
| `ProcessorFactory` | `threading.RLock`, construction outside the lock, close-outside-lock on eviction | Sound |
| `auralis/core/stages/` (13 stages) | none needed (pure functions) | Sound — no in-place ops on caller arrays found |
| `mastering_chunk_loop` | single-threaded; `new_tail` `.copy()`d | Sound — cannot alias `processed_chunk` |
| `vendor/auralis-dsp` (PyO3) | GIL released via `py.allow_threads` in all 11 fns | Sound — inputs copied to owned buffers first; no `static`/`Mutex`/`unsafe` |
| Module-level `_processor_cache` | `threading.Lock` | Sound locking; **unsound key** (`id(config)`) — C2-1 |
| `PerformanceOptimizer` singleton | `threading.Lock` + double-checked `None` test | Sound — reachable from `HybridProcessor.__init__:139` |
| `PerformanceProfiler` (wraps `AdaptiveMode.process` on the hot path) | `threading.RLock` | Sound — timing append/counter increment fully locked; bounded at 1000 samples/key |
| `SmartCache` | `threading.RLock` | Locking sound, keys content-faithful (#4524); no production caller |
| `MemoryPool` | `threading.RLock` | Locking sound, **free-list keyed on `id()` of unreferenced arrays** — C2-2; constructed on the mastering path, no production caller yet |
| `SIMDAccelerator` | none needed (all `@staticmethod`, no state) | Sound |
| `_apply_module_optimizations()` (import-time monkey-patch) | Python import lock + `AdaptiveMode._optimized` flag | Sound — single call site, executed once under the import lock |
| `AudioStreamController` | per-task `contextvars` (stream type / seq / track / epoch) | Sound — no shared mutable per-stream state on the instance |
| Stream semaphore (`_global_stream_semaphore`) | module-level `asyncio.Semaphore(10)` | **Leaks a permit on cancellation** — C3-1 |
| `ChunkedAudioProcessor` | `RLock` (`_processor_lock`) + `Lock` (`_sync_cache_lock`) | Locking sound; **lifecycle unowned** on the streaming path — C3-2 |
| `SimpleChunkCache` | `threading.Lock` | Sound — byte accounting correct on overwrite/evict/invalidate |
| `ChunkCacheManager` | class-level `_prune_lock` for the on-disk reaper | Sound; `cleanup_partial_files` never wired up — C3-4 |
| `encoding/atomic_io` | mkstemp + fsync + `os.replace` | Sound — readers see whole file or none |
| `ProcessorPool` | `asyncio.Lock`, construct/close outside it | Sound — pop-on-acquire, `discard()` for timed-out instances |
| `JobWorker` | `asyncio.Semaphore` + `acquired` flag + bounded `asyncio.wait` drain | Sound |
| `ws_handlers` task registry | `asyncio.Lock` (`active_tasks_lock`), cancel+await outside it | Sound structurally; **swallows caller cancellation** — C3-3 |
| `LibraryDatabase` | `Lock` (scan slots) + `RLock` (delete) | Sound; `shutdown()` has a benign TOCTOU — C4-4 |
| `migration_manager` | `threading.Lock` **and** `fcntl`/`msvcrt` file lock + double-check | Sound — both layers present as required |
| `LibraryScanner` | `Event` (`should_stop`) + `Lock` (`_active_paths`) | Slot accounting symmetric on all exception paths; **dedup guard scoped wrong** — C4-1 |
| `SettingsRepository` | class-level `RLock` for scan-folder RMW | Sound for scan folders; create-if-missing unguarded — C4-2 |
| Frontend WS singleton | refcount + single-slot handler registry + `connectPromise` join | Sound — no duplicate sockets or handlers |
| Frontend stream ingestion | `stream_epoch` + `seq` + `track_id` guards, `AbortController` on 13 hooks | Sound — superseded frames correctly dropped |

---

## Findings

### CRITICAL

None.

---

### HIGH

### C3-1: `drain_cancelled_task`'s new re-raise (#5083) escapes all three streaming `finally:` blocks before the semaphore is released — permanent permit leak
- **Severity**: HIGH
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/stream_chunk_ops.py:212-266` (helper), `auralis-web/backend/core/stream_enhanced.py:402-407`, `auralis-web/backend/core/stream_normal.py:419-437`, `auralis-web/backend/core/stream_seek.py:430-433`
- **Status**: NEW (regression introduced by `674162c7` / #5083; reopens the class of failure #4329 closed, through a different path)
- **Trigger Conditions**: The streaming task is cancelled (a seek, a track change via `_cancel_prior_task`, or `teardown_connection`) at any moment when `lookahead_task` is non-`None` — i.e. essentially any point inside the chunk loop after the first chunk, which is the overwhelmingly common case for a seek during playback.
- **Evidence**: All three entry points end with the identical shape:
  ```python
  finally:
      await controller._drain_cancelled_task(lookahead_task)
      controller._stream_semaphore.release()          # <-- never reached
  ```
  `#5083` changed `drain_cancelled_task` to stop swallowing a cancellation aimed at the *caller*:
  ```python
  try:
      await task
  except asyncio.CancelledError:
      if _caller_is_being_cancelled():                # current_task().cancelling() > 0
          raise
  ```
  `Task.cancelling()` is incremented by `Task.cancel()` and only decremented by
  `uncancel()`, which nothing here calls. So once the outer streaming task has been
  cancelled, `_caller_is_being_cancelled()` stays `True` for the rest of its life —
  including inside its own `finally`. The re-raise therefore fires *from within the
  `finally`*, skipping `release()` entirely.

  **Disproof attempt / confirmation**: I could not disprove it, and reproduced it
  directly with a standalone script isolating only the two primitives (no Auralis
  imports):
  ```
  initial 2
  after acquire 1
  final 1 (2 == ok, 1 == LEAK)      # "RELEASE RAN" never printed
  ```
  I also checked the existing regression test `tests/backend/test_stream_semaphore_cancel_leak.py`
  — it cancels during the *track lookup*, where `lookahead_task` is still `None`, so
  `drain_cancelled_task` returns immediately and `release()` runs. The test passes and
  the bug is untested.
- **Impact**: One permit of `MAX_CONCURRENT_STREAMS` (default 10) is lost per
  cancelled-mid-loop stream, permanently, for the process lifetime. After ~10
  seeks/track-changes every subsequent stream waits 5 s on
  `asyncio.wait_for(acquire, timeout=5.0)` and then fails with
  "Server busy - too many active streams" — all playback dead until the backend
  restarts, with no error explaining why. In `stream_normal.py` the leak is worse:
  the temp-WAV cleanup block sits *after* `release()` (lines 423-437), so the same
  escape also leaks a full-track temp WAV directory.
- **Siblings**: All three streaming entry points (`stream_enhanced.py`,
  `stream_normal.py`, `stream_seek.py`) — same two lines, same order.
- **Related**: #4329 (the original permit leak, closed), #3806, #3493, #5083.
- **Suggested Fix**: Reverse the order and/or shield the drain, so the permit is
  released unconditionally. Minimal form:
  ```python
  finally:
      try:
          await controller._drain_cancelled_task(lookahead_task)
      finally:
          controller._stream_semaphore.release()
  ```
  Apply to all three files, and extend `test_stream_semaphore_cancel_leak.py` with a
  parametrized case that cancels *after* the loop has spawned a look-ahead task.

---

### C3-2: The streaming path never calls `ChunkedAudioProcessor.close()` — a full-track temp WAV leaks per play for FFmpeg-only formats, and the startup sweep does not match its prefix
- **Severity**: HIGH
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/stream_enhanced.py:131-147,402-407`, `auralis-web/backend/core/stream_seek.py` (same construct/finally pair), `auralis-web/backend/core/chunked_processor.py:719-731` (`close()`), `auralis-web/backend/core/seekable_source.py:56,79-133`, `auralis-web/backend/config/startup.py:271-282,342`
- **Status**: NEW
- **Trigger Conditions**: Play (or seek within) any track libsndfile cannot open natively — `.m4a`, `.aac`, `.wma` — over the WebSocket streaming path. Fires on the first cache-missing chunk load, i.e. essentially every fresh play of such a track.
- **Evidence**: `ChunkedAudioProcessor.__init__` constructs `self._source = SeekableSource(filepath)` (chunked_processor.py:179). On the first `load_chunk()` the source converts the whole track to a temp WAV:
  ```python
  # seekable_source.py:56
  def convert_to_temp_wav(filepath, *, prefix="auralis_seekable_") -> tuple[str, str]:
      temp_dir = tempfile.mkdtemp(prefix=prefix)
      ...
      sf.write(wav_path, audio, sample_rate, format="WAV", subtype="FLOAT")
  ```
  and its docstring states the contract explicitly: *"Owns any temp directory it
  creates, so the holder must call `close()`."* `ChunkedAudioProcessor.close()`
  exists and does exactly that — but grepping all three streaming modules for
  `.close()` returns **nothing**; their `finally:` blocks only drain the look-ahead
  task and release the semaphore. Only `streamlined_worker.py:151` and
  `proactive_buffer.py:101` call it, and neither is on the WebSocket streaming path.

  **Disproof attempts**: (1) I checked for a `__del__`/`weakref.finalize` on
  `SeekableSource` and `ChunkedAudioProcessor` — there is none, so GC never reclaims
  the directory. (2) I checked the startup temp sweep as a possible safety net:
  `reclaim_leftover_stream_temps` globs `temp_root.glob("auralis_stream_*")`
  (startup.py:282) — `stream_normal.py:154` passes `prefix='auralis_stream_'` for its
  *own* temp, but `SeekableSource` uses the default `auralis_seekable_` prefix, which
  no sweep matches. The leak therefore persists across restarts too.
- **Impact**: Unbounded growth of the system temp directory. A 10-minute stereo
  track at 44.1 kHz written as WAV `FLOAT` is ~212 MB; a listening session over an
  AAC/ALAC library accumulates gigabytes and never reclaims them. On a small
  `/tmp` tmpfs this exhausts RAM-backed storage and takes the rest of the
  application down with it.
- **Siblings**: `stream_enhanced.py` and `stream_seek.py` both construct a
  `ChunkedAudioProcessor` and both omit the close. `stream_normal.py` does not
  construct one (it manages its own `temp_dir` correctly, per #4365).
- **Related**: #4737 (introduced `SeekableSource`), #4365, #4713, #5068.
- **Suggested Fix**: Add `processor.close()` to the `finally:` of `stream_enhanced.py`
  and `stream_seek.py` (guarded by `if processor is not None`, since it is bound
  inside the `try`), and add `auralis_seekable_*` to
  `reclaim_leftover_stream_temps`'s glob so pre-existing leaks are reclaimed on the
  next boot.

---

### C1-1: Concurrent `load_track_from_library()` / `load_file()` calls for different tracks permanently desync `current_track` metadata from the loaded audio
- **Severity**: HIGH
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/integration_manager.py:241-285`, `auralis/player/audio_file_manager.py:44-75`; reachable via `auralis-web/backend/services/queue_service.py:317-348,389-409` and `auralis-web/backend/services/navigation_service.py:152-195`
- **Status**: NEW
- **Trigger Conditions**: Two `load_track_from_library(track_id)` (or `load_file`) calls for **different** tracks dispatched concurrently. Confirmed reachable: `queue_service.py` and `navigation_service.py` both wrap these in `await asyncio.to_thread(...)`, so two rapid HTTP requests (double-click on two library tracks, or `jump_to_track` racing `next_track`) run them on two OS threads against the same singleton `AudioPlayer`.
- **Evidence**: `load_track_from_library` performs two individually-locked but mutually unserialized writes under **different** locks:
  ```python
  # integration_manager.py:259 — swaps audio under AudioFileManager._audio_lock
  if not self.file_manager.load_file(cast(str, track.filepath)):
      return False
  # integration_manager.py:267 — swaps metadata under IntegrationManager._position_lock
  self.set_current_track(track)
  ```
  Interleaving A(songA)/B(songB): B's `_audio_lock` swap lands last (songB audio is
  live), then A's `_position_lock` swap lands last (`_current_track_dict` describes
  songA). Final state is a terminal mismatch.

  **Disproof attempts**: the reader-side fixes #4102/#4552 make a single
  `get_playback_info()` internally consistent, but they faithfully report the
  inconsistent state the two writers left behind — they do not prevent it. The
  generation-counter arbitration used correctly for fingerprint loading
  (`fingerprint_loader_mixin.py:57-59`, hardened in #3445/#3473/#3719) has no
  equivalent on this path.
- **Impact**: `library.current_track` (title/artist/artwork/id) and
  `playback.current_file`/duration describe two different tracks indefinitely — the
  UI shows the wrong "now playing" for the audio actually streaming, and it does not
  self-correct on the next poll. `_auto_select_reference(track)`
  (`integration_manager.py:287`) compounds it by selecting a reference for the losing
  thread's track.
- **Siblings**: `AudioPlayer.load_file()` (`enhanced_audio_player.py:219-253`) raced
  against `load_track_from_library()` — same root cause, lower impact (metadata goes
  stale rather than actively wrong).
- **Related**: #4219, #4102, #3786 (all verified fixed; this is the level above them).
- **Suggested Fix**: Serialize the whole "load a track" operation with one
  load-in-progress mutex (file I/O can stay outside it; only the metadata+audio
  *commit* needs to be one critical section), or adopt the monotonic
  generation-counter arbitration already proven on the fingerprint path so a loser
  thread's writes are discarded rather than landing last.

---

### MEDIUM

### C3-3: `_cancel_prior_task` and `handle_seek` still swallow a caller-targeted `CancelledError` — the unfixed siblings of #5083
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:48-55` (`_cancel_prior_task`), `auralis-web/backend/ws_handlers/playback_commands.py:342-356` (`handle_seek`)
- **Status**: NEW
- **Trigger Conditions**: The WebSocket receive-loop task is cancelled (connection teardown, backend shutdown) while a `play_enhanced`/`play_normal`/`seek` handler is parked at `await old_task`.
- **Evidence**: Both sites use the exact construct `#5083` was filed to remove:
  ```python
  # playback_commands.py:52-55 and 353-356 — identical
  try:
      await old_task
  except (asyncio.CancelledError, Exception):
      pass
  ```
  `#5083`'s own commit message states the distinction: a `CancelledError` from the
  awaited task may be suppressed; one delivered to the *calling* task must
  propagate. `drain_cancelled_task` now makes that distinction via
  `Task.cancelling()`; these two call sites do not, and they are the very functions
  `#5083`'s message names (`handle_seek`, `teardown_connection`) as the cancellers.

  **Disproof attempt**: I checked whether the handler is unreachable during teardown —
  it is not; `connection.py:228-233` cancels the active stream task from
  `teardown_connection` while the receive loop may be mid-dispatch, and
  `handle_seek` explicitly documents awaiting unconditionally (#3806).
- **Impact**: A cancellation aimed at the receive loop is silently absorbed; the
  handler then proceeds past line 356 to `safe_send_text(... "seek_started" ...)` and
  `asyncio.create_task(deps.stream_from_position(...))`, starting a **new** streaming
  task on a connection that is being torn down. That task is not registered with any
  live teardown path, so it runs to completion against a closing socket. Not the
  data-corrupting variant of the bug, but it defeats structured cancellation and
  leaks a task plus (per C3-2) a processor per occurrence.
- **Siblings**: Both listed locations; no third instance of the pattern exists under
  `ws_handlers/`.
- **Related**: #5083, #3828, #3806, #3219.
- **Suggested Fix**: Route both through the now-correct
  `stream_chunk_ops.drain_cancelled_task` (or extract its `_caller_is_being_cancelled()`
  check into a shared helper) so a caller-targeted cancellation re-raises here too.

---

### C4-1: The per-directory duplicate-scan guard (#3455) is per-`LibraryScanner`-instance, but every production call site builds a fresh scanner — with `max_concurrent_scans` defaulting to 4, it never fires
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/scanner.py:79-80,158-176`, `auralis-web/backend/routers/library_scan.py:76`, `auralis-web/backend/services/library_auto_scanner.py:209`, `auralis/library/models/settings.py:61`
- **Status**: NEW
- **Trigger Conditions**: Two scans of the same directory started while `max_concurrent_scans > 1` — e.g. the auto-scanner firing while the user triggers a manual `POST /api/library/scan` on the same folder, or two manual scans in quick succession.
- **Evidence**: The guard lives on the instance:
  ```python
  # scanner.py:79-80
  self._active_paths: set[str] = set()
  self._active_paths_lock = threading.Lock()
  ```
  and both production constructions are per-invocation:
  ```python
  # routers/library_scan.py:76
  scanner = LibraryScanner(library_manager)
  # services/library_auto_scanner.py:209
  scanner = LibraryScanner(self._library_manager, fingerprint_queue=self._fingerprint_queue)
  ```
  So two concurrent scans each check their own empty set and both proceed. The only
  effective serialization left is the scan-slot counter — and its ceiling is
  `UserSettings.max_concurrent_scans`, whose column default is **4**
  (`models/settings.py:61`), not 1.

  **Disproof attempt**: I checked whether duplicate *rows* can result. They cannot —
  `Track.filepath` and `Track.filepath_key` are both `unique=True`
  (`models/core.py:94,104`) and `TrackRepository.add()` catches the resulting
  `IntegrityError` in a broad `except Exception`, rolls back and returns `None`
  (`track_repository.py:297-300`). That is what caps this at MEDIUM rather than
  HIGH. The scan-slot acquire/release symmetry itself I verified as correct on every
  exception path, including the early return at `scanner.py:172-174` (#4330) and the
  `finally` at :394-398.
- **Impact**: Up to 4× duplicated filesystem walks, metadata extraction and audio
  probing for the same folder — the exact wasted work #3455 exists to prevent — plus
  inflated `files_failed` counts from the losing inserts and, via #4841, misleading
  per-file failure lists surfaced to the user.
- **Siblings**: `should_stop`/`file_discovery`/`batch_processor` state is likewise
  per-instance, which is *correct* given per-invocation scanners; only `_active_paths`
  advertises cross-scan protection it cannot provide.
- **Related**: #3455, #4330, #2438.
- **Suggested Fix**: Move the active-path set to where the scan slots already live —
  `LibraryDatabase`, next to `_scan_slots_lock`/`_active_scans` — so it is process-wide
  like the counter it complements, and have `try_acquire_scan_slot()` take the
  directory list.

---

### C1-2: `state` / `position` / `audio_data` / `reference_data` getters bypass the locked-accessor discipline used everywhere else, and `position` is unclamped
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:208-211,670-673`, `auralis/player/player_properties_mixin.py:73-76,88-91`
- **Status**: NEW (sibling gap; OPEN #3785 scoped only `sample_rate`/`current_file`/`reference_file`, CLOSED #4574 fixed only the setter side)
- **Trigger Conditions**: Any direct read of these four properties (rather than
  `get_playback_info()` / `get_state_snapshot()` / `get_position_snapshot()`) while a
  mutator runs on another thread.
- **Evidence**: All four are raw `return self.<delegate>.<attr>` with no lock, while
  the locked equivalents exist a few lines away (`playback_controller.py:281-284,296-302`).
  Separately, `position` skips the `min(position_seconds, duration)` clamp that
  `_get_position_seconds()` applies (`integration_manager.py:406-427`), and
  `read_and_advance_position()` (`playback_controller.py:201-216`) advances
  unconditionally — so with `auto_advance` disabled or no next track
  (`enhanced_audio_player.py:530`), `position` grows past `total_samples` without
  bound.

  **Disproof attempts**: `sys._is_gil_enabled()` is `True` on this repo's 3.14.0
  interpreter, so these single `LOAD_ATTR` reads cannot tear today. Grepping all of
  `auralis-web/backend` found no router or service reading any of the four directly —
  the live REST/WebSocket path correctly goes through `get_playback_info()`. Both
  facts are why this is MEDIUM, not HIGH.
- **Impact**: A direct reader can observe state inconsistent with a paired read — the
  exact class `get_state_snapshot()` was built to prevent — and `player.position` can
  report a sample count exceeding track length, violating the documented
  `position <= duration` invariant. Current blast radius is the back-compat/test
  surface, not production audio.
- **Siblings**: All four getters share the shape; grouped as one finding per the
  sibling rule.
- **Related**: #3785 (fold into it — its own completeness checklist named this exact property set and never finished it).
- **Suggested Fix**: Route `state` through `get_state_snapshot()`, `position` through
  `get_position_snapshot()` **with** the `min(position, duration)` clamp, and
  `audio_data`/`reference_data` through `_audio_lock`, mirroring their own
  already-fixed setters.

---

### C2-2: `MemoryPool`'s free list is keyed on `id()` of arrays it does not reference, so `return_buffer()` can zero a caller-owned array in place and hand it to a second thread
- **Severity**: MEDIUM (latent — the pattern is CRITICAL-shaped; capped only because I verified there is currently no caller, see Evidence)
- **Dimension**: Audio Processing
- **Location**: `auralis/optimization/memory/memory_pool.py:26,32-69`; constructed from `auralis/optimization/performance_optimizer.py:43`, reached on the mastering path via `auralis/core/hybrid_processor.py:27,139`
- **Status**: NEW
- **Trigger Conditions**: Any code calling `PerformanceOptimizer.get_audio_buffer()` / `return_audio_buffer()` (or `MemoryPool` directly) from more than one thread. The pool is already instantiated on every `HybridProcessor` construction, so the first call site added inherits the defect silently.
- **Evidence**: The pool tracks outstanding buffers by identity, in a `set[int]`:
  ```python
  # memory_pool.py:26
  self.allocated_buffers: set[int] = set()
  ```
  `get_buffer()` allocates, records `id(buffer)`, and returns the array
  (`np.asarray(buffer, dtype=dtype)` is a no-op when dtype already matches, so the
  returned object **is** `buffer`):
  ```python
  # memory_pool.py:45-48
  buffer = np.zeros(shape, dtype=dtype)
  self.allocated_buffers.add(id(buffer))
  self.total_allocated += buffer_size
  return np.asarray(buffer, dtype=dtype)
  ```
  Nothing removes the id when the caller simply drops the array — only an explicit
  `return_buffer()` does. So after GC the set holds ids of dead objects whose
  addresses CPython is free to reissue. `return_buffer()` then gates purely on that
  stale identity and **mutates the array in place**:
  ```python
  # memory_pool.py:57-69
  with self.lock:
      if buffer_id in self.allocated_buffers:
          self.allocated_buffers.remove(buffer_id)
          buffer.fill(0)                     # <-- in-place zero of a caller-owned array
          ...
          self.available_buffers[shape].append(buffer)   # <-- then shared with the next taker
  ```
  An unrelated array that happens to land on a recycled address is therefore accepted,
  zeroed in place, and published into the free list — where `get_buffer()` hands it to
  another thread while the original owner still holds it. That is simultaneously the
  "in-place mutation of a caller-owned NumPy array" and "same buffer handed to two
  threads" cases the severity table lists as CRITICAL.

  A second, independent defect in the same object: `self.total_allocated` is
  incremented at line 47 and **never decremented anywhere**. Once cumulative
  allocations reach `pool_size_bytes` (64 MB by default) the `total_allocated +
  buffer_size <= pool_size_bytes` test at line 44 is permanently false, so the pool
  degrades to the "Pool is full" path forever and stops pooling entirely — while
  `get_stats()['utilization']` reports a number that grows without bound past 1.0.

  **Reachability — verified by me, not inherited**: I grepped all of `auralis/` and
  `auralis-web/` (excluding `auralis/optimization/` itself and `tests/`) for
  `get_audio_buffer`, `return_audio_buffer`, `get_buffer` and `return_buffer`. The
  only hit in the entire tree is a *comment* at `hybrid_processor.py:615`. So the
  dangerous methods have no production caller **today** — but unlike the stale
  `_audit-common.md` claim this correction supersedes, the *pool object itself* is
  very much on the production mastering path: `HybridProcessor.__init__:139` calls
  `get_performance_optimizer()`, which constructs `MemoryPool(64)` at
  `performance_optimizer.py:43`. It is allocated, live, and one call site away from
  firing.
- **Impact**: If wired up: silent corruption of caller audio (zeroed samples →
  audible dropouts) and two threads writing one buffer → interleaved garbage.
  Today: the pool is dead weight whose accounting is already wrong, and any
  developer who reaches for the "optimized buffer" API gets a data race with no
  warning.
- **Siblings**: `auralis/core/hybrid_processor.py:667` (C2-1) is the same
  `id()`-as-identity anti-pattern in a different cache. `SmartCache._identify`
  (`caching/smart_cache.py:51-87`) and `ProcessorFactory._get_cache_key` are the
  two places that got it right and should be the reference.
- **Related**: C2-1, #4524 (fixed the identical repr/`id()` identity flaw in `SmartCache`), #3476.
- **Suggested Fix**: Track outstanding buffers in a `weakref.WeakValueDictionary`
  (or drop the tracking set entirely and gate `return_buffer` on shape/dtype plus an
  explicit ownership token), never on `id()`. Decrement `total_allocated` when a
  buffer is returned or evicted. Given there is no caller, deleting `MemoryPool` and
  the `get_audio_buffer`/`return_audio_buffer` façade is the lower-risk option and
  matches how #3476 handled the dead `ParallelProcessor` field in the same class.

---

### LOW

### C2-3: `_audit-common.md` tells every audit that `auralis/optimization/` is test-only and to cap severity there — it is imported by `hybrid_processor.py` and runs at import time
- **Severity**: LOW (audit tooling — no runtime impact, but it systematically suppresses findings in a package on the mastering path)
- **Dimension**: Audit Tooling
- **Location**: `.claude/commands/_audit-common.md:23`
- **Status**: NEW
- **Trigger Conditions**: Any audit run that follows the shared protocol — i.e. all of them, including the orchestrator and every dimension subagent, since the instruction is in the file all audit skills reference.
- **Evidence**: The Project Layout table asserts:
  > *"NO production code imports this package — the only importers are tests. … Treat the remainder as unreferenced-by-runtime: a bug here has no user-visible blast radius, so cap severity accordingly and prefer a tech-debt finding over an engine finding."*

  Contradicted directly by the live tree:
  ```python
  # auralis/core/hybrid_processor.py:27
  from ..optimization.performance_optimizer import get_performance_optimizer
  ```
  used at `hybrid_processor.py:139` (every `HybridProcessor` construction),
  `:566` (`get_optimization_stats`), and `:612`/`:624` inside
  `_apply_module_optimizations()`, which executes at **module import time**
  (`:642`) and replaces `AdaptiveMode.process` with a profiling wrapper for the
  life of the process. Through `PerformanceOptimizer.__init__` this transitively
  instantiates 4 of the package's 5 submodules — `memory/` (`MemoryPool`),
  `caching/` (`SmartCache`), `acceleration/` (`SIMDAccelerator`), `profiling/`
  (`PerformanceProfiler`) — plus `config.py`.

  The claim was most likely true when `#4565` deleted `parallel_processor.py` and
  became stale when nothing re-checked the remaining importers.
- **Impact**: Every audit is instructed to downgrade findings in a package whose
  `PerformanceProfiler` wrapper is on the hot mastering path and whose `MemoryPool`
  is constructed on every processor build. In this audit it would have suppressed
  **C2-2** to a tech-debt note. The blast radius is all future audits, not this one.
- **Siblings**: The same table's other reachability claims (the Retired Architecture
  rows) are load-bearing in the same way and are not covered by
  `_audit-validate.sh`, which checks only that backticked *paths exist* — not that
  statements about them are still true.
- **Related**: #4565 (deleted the sibling cluster, plausibly when this went stale), #4982 (the existing hand-maintained-counts drift problem in the same file).
- **Suggested Fix**: Correct the row to state that
  `optimization/performance_optimizer.py` (and transitively `profiling/`, `caching/`,
  `memory/`, `acceleration/`, `config.py`) **is** imported by
  `auralis/core/hybrid_processor.py` and remove the severity cap. Longer term,
  extend `_audit-validate.sh` with a check that any "no production importers" claim
  is re-derived from a `grep` over the tree, the way
  `scripts/check_doc_counts.py` re-derives the structural counts.

---

### C2-1: The module-level `HybridProcessor` cache is keyed on `id(config)`, which CPython reuses after GC
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py:654-712` (`_get_or_create_processor`), specifically line 667
- **Status**: NEW
- **Trigger Conditions**: A caller passes a `UnifiedConfig`, drops the reference, and a *different* `UnifiedConfig` is later allocated at the same address — CPython's small-object allocator makes this routine, not exotic.
- **Evidence**:
  ```python
  # hybrid_processor.py:667
  cache_key = f"{id(config)}_{mode}" if config is not None else f"default_{mode}"
  ```
  `_processor_cache` stores only the *processor*, never the config, so nothing keeps
  the keyed object alive and its `id()` is free for reuse. The locking around the
  cache is correct (`_processor_cache_lock`, construct-outside-lock, close-outside-lock);
  it is the key that is unsound. The same hazard is called out and *avoided* elsewhere
  in this codebase — `audio_stream_controller.ws_id()` documents "Using `id(websocket)`
  is unsafe because CPython reuses memory addresses after GC" and assigns a UUID instead.

  **Disproof attempt / why LOW**: the only reachable callers are the
  `auralis/__init__.py` public exports `process_adaptive` / `process_reference`.
  Grepping `auralis-web/` found no runtime path through this function — the backend
  uses `core/processor_factory.py`, whose key is a content hash
  (`ProcessorCacheKey`), not an identity. Blast radius is the library's public API
  surface only.
- **Impact**: A caller can receive a processor configured for an entirely different
  `UnifiedConfig` — wrong EQ/dynamics/target LUFS applied with no error. Silent wrong
  audio, but only via the public API.
- **Siblings**: `ProcessorFactory._get_cache_key` (content hash — correct);
  `ws_id()` (UUID — correct). This is the last identity-keyed cache.
- **Suggested Fix**: Reuse `ProcessorFactory`'s approach — hash `config.to_dict()` —
  or hold a `weakref` to the config alongside the entry so the key cannot be
  recycled while the entry lives.

---

### C3-4: `cleanup_partial_files` — the sweep half of #4576 — is never called from production code
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/encoding/atomic_io.py:141-160`
- **Status**: NEW
- **Trigger Conditions**: An unclean exit (Electron quit, `kill -9`, OOM, power loss) during a staged chunk write.
- **Evidence**: The module docstring describes the fix as *"Two halves, both needed"* —
  `atomic_write_bytes`/`atomic_save_audio` for the write, `is_wav_complete` for the
  read gate — and provides `cleanup_partial_files` for the leftovers. Grepping the
  whole tree for callers returns only its own definition and
  `tests/backend/test_atomic_cache_writes_4576.py:169`. Nothing in `config/startup.py`
  or `chunk_cache_manager.py` invokes it.

  **Disproof attempt**: I checked whether `ChunkCacheManager.prune_chunk_directory`
  incidentally reclaims them. It counts every file in the directory toward the
  512 MB cap and deletes oldest-mtime-first — so leftovers are only removed once the
  directory exceeds the cap. Below the cap they persist indefinitely.
- **Impact**: Orphaned `.<name>.<rand>.part.wav` staging files accumulate in
  `/tmp/auralis_chunks` across crashes, consuming disk and counting against the
  512 MB chunk-cache budget so real cached chunks are evicted sooner than intended.
  Correctness is unaffected — `is_partial_path` keeps them out of the cache index.
- **Related**: #4576.
- **Suggested Fix**: Call `cleanup_partial_files(chunk_dir)` from the lifespan
  startup, next to `reclaim_leftover_stream_temps` (`config/startup.py:342`).

---

### C4-2: `SettingsRepository.get_settings()` / `update_settings()` create-if-missing is an unguarded read-modify-write on a table with no singleton constraint
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/settings_repository.py:34-53,55-...`, `auralis/library/models/settings.py:21-25`
- **Status**: NEW
- **Trigger Conditions**: First boot against a fresh database, when two components read settings concurrently — e.g. `LibraryDatabase.try_acquire_scan_slot()` (which calls `get_settings()` on every scan) racing the startup seeding of `enhancement_settings`, or the auto-scanner racing a settings REST read.
- **Evidence**:
  ```python
  # settings_repository.py:39-48
  settings = session.execute(select(UserSettings)).scalars().first()
  if not settings:
      settings = UserSettings()
      session.add(settings)
      session.commit()
  ```
  There is no uniqueness or check constraint pinning `user_settings` to one row —
  the model declares only `id: Mapped[int] = mapped_column(Integer, primary_key=True)`.
  `update_settings()` has the identical unguarded create branch. Note the contrast:
  the same class *does* carry `_scan_folders_lock` (a class-level `RLock`) for the
  `add_scan_folder`/`remove_scan_folder` RMW window (#4956), so the pattern is
  understood here — it just was not applied to the create path.
- **Impact**: Two rows in `user_settings`. Every reader uses `.first()`, so behaviour
  stays deterministic, but a settings write can land on the row that is not the one
  subsequently read, silently losing the user's change until restart. Low because it
  is a first-boot-only window and self-limiting.
- **Siblings**: `update_settings()` (same file, same branch).
- **Suggested Fix**: Extend the existing class-level `_scan_folders_lock` (or add a
  sibling `_settings_lock`) over the select-then-create window in both methods, and
  add a `CheckConstraint('id = 1')` or a unique singleton column to `UserSettings`.

---

### C4-3: Three cross-thread stop flags remain plain `bool` — unmigrated siblings of #3728's `threading.Event` fix
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/services/fingerprint_queue.py:141,323,372,387,394,396,410`, `auralis/library/scanner/batch_processor.py:42,46,65`, `auralis/library/scanner/file_discovery.py:34,38,72,131`
- **Status**: NEW
- **Trigger Conditions**: Free-threaded CPython (`python -X gil=0` / PEP 703), available on this project's Python 3.14 target.
- **Evidence**: `#3728` converted `LibraryScanner.should_stop` to a `threading.Event`
  with an explicit rationale, still in the source:
  > *"under default CPython the GIL kept plain-bool reads atomic, but free-threaded Python (PEP 703 / `python -X gil=0`) would race on the bare attribute. Event is the idiomatic choice"*

  The three siblings were not converted. All are genuinely cross-thread:
  `FingerprintExtractionQueue.stop()` sets `self.should_stop = True` from the caller
  thread (line 323) while N worker threads spin on `while not self.should_stop`
  (lines 372/396); `LibraryScanner.stop_scan()` calls `file_discovery.stop()` and
  `batch_processor.stop()` from the event-loop/router thread while the scan body runs
  in an `asyncio.to_thread` worker.

  **Disproof attempt**: under the current default build (`sys._is_gil_enabled()` is
  `True`) these reads cannot tear, which is why this is LOW and not MEDIUM.
- **Impact**: On a free-threaded interpreter a worker can miss the stop signal
  indefinitely, so `stop(timeout=30.0)` times out and shutdown proceeds with live
  worker threads still touching the database.
- **Siblings**: All three listed; no fourth instance remains.
- **Related**: #3728, #3710.
- **Suggested Fix**: Convert all three to `threading.Event` (`.set()` / `.is_set()`),
  matching the scanner. Mechanical and behaviour-preserving under the current build.

---

### C4-4: `LibraryDatabase.shutdown()` reads `self.engine` three times without synchronization
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/database.py:319-387`
- **Status**: NEW
- **Trigger Conditions**: Two shutdown paths overlapping — the FastAPI lifespan calling `shutdown()` while the `atexit` handler (registered at line 214) fires, or `__del__` running from GC on a non-main thread.
- **Evidence**: The guard and the uses are separate reads of a mutable attribute:
  ```python
  if not hasattr(self, 'engine') or self.engine is None:
      return
  ...
  with self.engine.connect() as conn:        # may be None by now
  ...
  self.engine.dispose()                      # may be None by now
  ```
  with `self.engine = None` assigned in the `finally` (line 375, #3769).

  **Disproof attempt**: the resulting `AttributeError: 'NoneType' object has no
  attribute 'connect'` is caught by the broad `except Exception` at line 366, so it
  degrades to one logged error rather than a crash — that is why this is LOW. There
  is a second, subtler consequence I could not disprove: a background worker issuing
  a query *after* `dispose()` transparently reopens the pool, recreating the
  `-wal`/`-shm` sidecars the `wal_checkpoint(TRUNCATE)` just removed, so the "clean
  shutdown" guarantee of #2066 is only as good as the caller's worker-quiescence
  discipline.
- **Impact**: A spurious `Error during library database shutdown` in the log, and
  potential WAL sidecar resurrection after the checkpoint. No data loss (SQLAlchemy
  `dispose()` detaches rather than severing checked-out connections).
- **Suggested Fix**: Snapshot the engine into a local under a `threading.Lock` and
  clear the attribute *before* teardown, so the second entrant returns at the guard:
  `with self._shutdown_lock: engine, self.engine = self.engine, None` then operate on
  `engine`.

---

## Relationships

**Shared root cause — cancellation semantics (C3-1, C3-3):** both are the same
question ("whose cancellation is this?") answered inconsistently across the
codebase. `#5083` answered it correctly in `drain_cancelled_task` but did not
propagate the answer to (a) the `finally:` blocks that call it or (b) the two
`ws_handlers` sites that use the old blanket-suppress form. Fixing them as one
change — extract `_caller_is_being_cancelled()` into a shared helper, audit every
`except (asyncio.CancelledError, Exception)` and every `await` in a `finally` —
is cheaper and safer than three separate patches.

**Compound race (C3-1 + C3-2 + C3-3):** these chain. A seek during playback
triggers C3-3 (cancellation swallowed in `handle_seek`, though it usually is not
teardown so the handler proceeds normally), and reliably triggers C3-1 (permit
leaked) and C3-2 (temp WAV leaked). One user action — seeking through an AAC
track ten times — can therefore exhaust the stream semaphore *and* fill `/tmp`
with ~2 GB of decoded audio. Neither self-heals.

**Shared root cause — per-instance guard for a cross-instance problem (C3-2, C4-1):**
`LibraryScanner._active_paths` and the streaming path's ownership of
`ChunkedAudioProcessor` both put a lifecycle/exclusion concern on an object that is
constructed per request. The fix shape is the same in both: hoist the concern to the
process-wide component that already owns the analogous state (`LibraryDatabase` for
scan slots; the stream's `finally` for processor lifetime).

**Shared root cause — incomplete sibling sweeps (C1-2, C4-3, C3-4):** three findings
are the unfinished tails of fixes that were correct as far as they went. #3785 named
six attributes and closed four. #3728 converted one of four stop flags. #4576 shipped
both halves of its design but wired up only one. A `grep` for the *pattern* rather
than the reported symptom would have caught all three at fix time.

**Shared root cause — identity-as-key (C2-1, C2-2):** both key long-lived state on
`id()` of an object the structure does not keep alive, so CPython address reuse
yields a wrong-object hit. `#4524` already fixed exactly this in `SmartCache`
(replacing `repr`/`id`-derived keys with a blake2b content digest) and `ws_id()`
documents the hazard verbatim — the fix pattern is established, it just was not
swept across the remaining two sites. Fix them together and the anti-pattern is
gone from the tree.

**Tooling ↔ findings (C2-3 → C2-2):** C2-3 is why C2-2 was nearly missed, and why
it is worth treating the audit protocol file as auditable code. The instruction to
cap severity in `auralis/optimization/` would have demoted a shared-buffer data
race to a tech-debt note. Any audit that ran against this instruction since #4565
should be regarded as having under-covered that package.

---

## Prioritized Fix Order

| # | Finding | Severity | Why this order |
|---|---|---|---|
| 1 | **C3-1** semaphore permit leak | HIGH | Introduced yesterday, reachable on an ordinary seek, permanently kills all streaming after ~10 occurrences, and the fix is two lines per file. Highest severity-to-effort ratio in the report. Ship with the extended regression test. |
| 2 | **C3-2** `ChunkedAudioProcessor` never closed | HIGH | Same blast radius (a normal play), gigabytes of `/tmp` per session, does not self-heal across restarts because the sweep prefix does not match. One line per file plus one glob. |
| 3 | **C3-3** unfixed `#5083` siblings | MEDIUM | Fix together with #1 — same root cause, same reviewer context, and doing them separately risks a third pass. |
| 4 | **C1-1** load-track desync | HIGH | Highest *user-visible* wrongness (wrong now-playing metadata), but needs a real design decision (coarse mutex vs generation counter), so it wants its own session rather than being rushed alongside the streaming fixes. |
| 5 | **C4-1** scan dedup guard scoped wrong | MEDIUM | Wastes up to 4× the work on every overlapping scan; contained fix (move the set next to the scan-slot counter). |
| 6 | **C1-2** unlocked player getters | MEDIUM | No production reader today, so it is hardening — but fold it into the still-open #3785 rather than leaving that issue's checklist perpetually half-done. |
| 7 | **C2-3** false "test-only" instruction in `_audit-common.md` | LOW | Cheap (a few lines of prose) but it gates the *quality of every future audit*, including the re-audits that will verify the fixes above. Correct it before the next suite run, not after. |
| 8 | **C2-2** `MemoryPool` identity-keyed free list | MEDIUM | No caller today, so it cannot fire — but it is constructed on every `HybridProcessor` build and is one call site from a shared-buffer data race. Fix together with #9 (same anti-pattern) or delete the dead façade outright, as #3476 did for `ParallelProcessor`. |
| 9 | **C2-1** `id(config)` cache key | LOW | Public-API-only reach, but silent wrong audio when it fires; content-hash the config as `ProcessorFactory` already does. Batch with #8. |
| 10 | **C4-3** plain-bool stop flags | LOW | Mechanical, behaviour-preserving, and forward-looking for free-threaded Python. Good batch candidate with #6. |
| 11 | **C3-4** unwired partial-file sweep | LOW | One call in the lifespan. Batch with #2, which touches the same startup sweep function. |
| 12 | **C4-2** unguarded settings create-if-missing | LOW | First-boot-only window, self-limiting; the class already has the lock pattern to copy. |
| 13 | **C4-4** `shutdown()` TOCTOU | LOW | Cosmetic today (caught by the broad `except`); worth doing when the shutdown path is next touched. |

---

## Coverage and Confidence

**Examined in depth and found sound** (no findings — recorded so a future audit
does not re-tread them):

- **Rust PyO3 boundary** (`vendor/auralis-dsp/`): all 11 exposed functions copy
  inputs into owned `Vec`/`ndarray` before `py.allow_threads`, release the GIL for
  the compute, and wrap it in `catch_unwind`. No `static`, `lazy_static`, `OnceCell`,
  `thread_local`, `Mutex`, `RwLock` or `unsafe` anywhere in `src/*.rs`.
- **Engine chunk loop** (`auralis/core/mastering_chunk_loop.py`): `new_tail` is
  `.copy()`d so it cannot alias `processed_chunk`; `prev_tail` is committed only
  after a successful write (#2429); sample-count and crossfade-width asserts present.
- **Copy-before-modify across the 13 named stages** and `auralis/dsp/`: no in-place
  operation on a caller-owned array or view found.
- **`use_fingerprint_analysis` toggle** (`audio_processing_pipeline.py:177-228`):
  correctly wrapped in `processor._process_lock` on both branches (#4354).
- **Migration locking** (`auralis/library/migration_manager.py:48-140,520-595`): the
  same-process `threading.Lock` *and* the `fcntl`/`msvcrt` inter-process lock are both
  present, the timeout is a shared budget as documented, the lock file is deliberately
  never unlinked (#4523), and the post-lock version re-check (double-check pattern)
  is intact. Backup-before-migrate aborts on backup failure.
- **Scan-slot accounting** (`database.py:275-313`, `scanner.py:141-176,394-398`):
  acquire/release symmetric on every exception and early-return path, including the
  #4330 pre-`try` early return. `_report_progress` cannot leak a slot — it swallows
  callback exceptions.
- **`SimpleChunkCache`** byte accounting: correct on overwrite (#3192), count
  eviction, memory eviction, and `invalidate_chunk`.
- **`encoding/atomic_io`**: mkstemp in the destination directory, fsync, `os.replace`,
  unlink-on-failure. Readers see a whole file or none.
- **`ProcessorPool` and `JobWorker`**: pop-on-acquire leases, `acquired`-flag-guarded
  release (#3531), `discard()` for timed-out instances (#4727), bounded
  `asyncio.wait` drain that cannot hang on a task swallowing `CancelledError` (#4543).
- **`ProcessorFactory`**: content-hashed keys including `targets_hash` (#3720),
  construction outside the lock with a lost-race reclaim, close-outside-lock on
  eviction.
- **Frontend WebSocket singleton**: `WebSocketManager.on()` assigns a single handler
  slot (cannot duplicate dispatches), reuse joins the in-flight `connectPromise`
  rather than racing a second manager (#4522), exhausted managers are retired, and
  only one `WebSocketProvider` is mounted (`App.tsx:46`) so the last-attacher-wins
  path is unreachable.
- **Frontend stream ingestion**: the backend's `stream_epoch` (#4563), `seq` (#3841)
  and `track_id` (#4434) discriminators are all recorded and enforced client-side
  (`useAudioStreamingCore.ts:244-253,420-431`, `websocketConnectionCore.ts:139-158`);
  `cleanupStreaming()` resets buffer, pending queue, last-chunk index and epoch
  together. 13 hooks use `AbortController`; timer set/clear counts balance across
  `hooks/`.
- **`auralis/optimization/` — the reachable surface** (re-audited without the
  severity cap, per the protocol correction): `get_performance_optimizer()` uses a
  correct double-checked lock (`performance_optimizer.py:182-189`);
  `PerformanceProfiler.time_function` — the one component genuinely on the hot
  mastering path, wrapping `AdaptiveMode.process` for every call — does all of its
  mutation under `self.lock` and is bounded at 1000 samples per key
  (`profiling/performance_profiler.py:43-49`); `SmartCache` is fully `RLock`-guarded
  with content-faithful keys (#4524); `SIMDAccelerator` is stateless
  (`@staticmethod` only); `_apply_module_optimizations()` runs once under the Python
  import lock behind an `AdaptiveMode._optimized` flag with a single call site. The
  `_gc_lock → cache.lock` nesting in `optimize_real_time_processing` is consistently
  ordered (no AB-BA) and has no production caller. The one defect found is C2-2.

**Deliberately not reported** (investigated, disproved):

- LRU eviction closing a live `HybridProcessor` — `close()` is a documented no-op
  today (`AudioFingerprintAnalyzer.close()`), so there is no executor to shut down
  out from under an in-flight `process()`. (The `hybrid_processor.close()` docstring
  claiming a "5-thread executor" is now stale prose, not a bug.)
- Concurrent same-track streams sharing one pooled `HybridProcessor` and polluting
  each other's carried DSP state — `_process_lock` prevents torn state, and the two
  paths that would make this routine are not live: `_cancel_prior_task`/`handle_seek`
  await the old task before starting the new one, and `proactive_buffer.buffer_presets_for_track`
  is wired through `main.py` → `config/routes.py` → `routers/player.py` but **never
  called** (dead parameter). The residual window is the orphaned executor thread of
  #4815, already tracked.
- `ChunkedAudioProcessor`'s two disjoint locks (`_processor_lock` vs
  `_sync_cache_lock`) guarding one cache dict — the two entry points
  (`process_chunk_safe` from streaming, `get_wav_chunk_path` from
  `routers/enhancement.py:207`) never share an instance, and each instance gets its
  own `chunk_cache` dict (already noted as #4760).
- `_stream_pause_events` / `_stream_flow_events` identity between `routers/system.py`
  and `StreamState` — verified to be the same objects, passed by reference.
- Multiple `WebSocketProvider` instances clobbering each other's handler slot —
  only one provider exists.
- Frontend `pendingChunksRef` retaining stale queued chunks — cleared in
  `cleanupStreaming()`, and stale entries carry the old epoch so they would be
  dropped anyway.

**Deduplication**: every finding above was checked against `/tmp/audit/issues.json`
(292 open) and `/tmp/audit/issues-closed.json` (2,000 closed) by keyword, and
against the three prior concurrency reports. All thirteen are NEW. Findings verified as
already-fixed-despite-open (#3785 partially, #4219, #4102) and already-tracked
(#4815, #4819, #4838, #4760, #5068) were excluded rather than re-reported.

**Scope caveat**: dimensions 1 (Player) ran as a dedicated agent; dimensions 2-5
were audited directly by the orchestrator because the subagent pool was saturated
by concurrent audits in the same suite. Dimension 3 (Backend Streaming) and
Dimension 4 (Library & Database) received full depth. Dimension 2 (Audio
Processing) covered the Rust boundary, the chunk loop, the 13 stages' copy
discipline, the shared-processor question, module-level DSP state, and — after the
protocol correction — all of `auralis/optimization/` (779 lines across 5
submodules, read in full), but did not exhaustively trace every function in
`auralis/dsp/`; a follow-up pass focused on `auralis/dsp/eq/parallel_eq_processor/`
and `auralis/player/realtime/` would close that gap. Dimension 5 (Frontend State)
covered the WebSocket lifecycle, stream ingestion, abort/timer discipline and the
epoch/sequence guards, but not every Redux slice reducer.

**Confidence note on C2-3**: because the false "test-only" instruction has been in
`_audit-common.md` since at least the #4565 cleanup, prior audit reports' coverage
of `auralis/optimization/` should be treated as unreliable rather than as evidence
that the package is clean. This audit's verdict on it (sound except C2-2) is based
on a full read of all 779 lines, not on the inherited claim.
