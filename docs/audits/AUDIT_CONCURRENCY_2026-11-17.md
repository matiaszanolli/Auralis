# Concurrency and State Integrity Audit - 2026-11-17

Fresh audit of the current source (5 dimensions, depth deep, no limit). Dedup baseline: `gh issue list --state all` dump, 6090 issues, highest #6346, no truncation. No prior report was consulted.

## Executive Summary

**Total findings: 41** - CRITICAL 0, HIGH 0, MEDIUM 11, LOW 30.

Status: 1 Regression of #6084 (C1-01), 1 Existing (#6082, C3-11), the rest NEW. Per dimension: Player 8, Audio Processing 2, Backend Streaming 11, Library & DB 13, Frontend 7.

No CRITICAL or HIGH race was found. The engine DSP core is well protected (per-instance RLock around every mutating entry point and `process()`, stateless GIL-releasing Rust, no module-level mutable DSP state), the migration thread+file lock, scan slot / path reservation, three-engine timeout constants, analysis gate, prebuffer re-arm, gapless swap snapshot and pause-flag fixes are all still in place. The remaining risk is concentrated in three themes:

1. **Lease/lifecycle of `ChunkedAudioProcessor` and its leased `HybridProcessor`** (C3-01, C3-02, C3-03, C3-09, C2-01, C2-02, C3-08): `close()` has no closed state and does not wait for an uncancellable executor render, abandoned constructor threads and the recommendation path never close their lease, and a warm lease is handed to the next stream with stale limiter/EQ state.
2. **Check-then-act across separate lock acquisitions or commits** (C3-04, C3-07, C3-11, C4-01, C4-03, C4-05, C4-06, C4-07, C1-06, C1-07, C1-08): queue mirror bypassing the set-queue generation, ticker stop after restart, reference-cloud refresh as three commits, fingerprint stored for the version on disk after analysis rather than the version analysed.
3. **Frontend request/response ordering** (C5-01, C5-02, C5-03): skip bursts exceed the WS rate limit and desync the UI, a local enhancement command's own broadcast is treated as external (double stream re-issue), and `refresh()` leaves the in-flight flag stuck so infinite scroll dies.

Most impactful: C3-01/C3-02/C3-03 (leaked or double-used processor leases and temp-WAV holds), C4-02 (a removed scan folder is re-imported by an in-flight auto-scan), C5-01 (UI shows a track that is not playing), C3-04 (stale queue mirrored over a newer `set_queue`).

Reachability caveat (Dim 1): the shipped backend never calls `AudioPlayer.get_audio_chunk()`; only tests and embedders do. C1-01, C1-04 and C1-05 therefore need an embedding audio callback and are rated LOW.

## Concurrency Matrix

| Component | Lock / mechanism | Status |
|---|---|---|
| `AudioPlayer` + mixins, `PlaybackController` | `PlaybackController._lock` (RLock), `_audio_lock`, deferred notifications, `lock_held_hook` guard, `seq` ordering | Sound; LOW residuals C1-02..C1-07 |
| `QueueController` / `QueueManager` | `QueueManager._lock`; controller mixins borrow `queue._lock` | LOW: shuffle flag and order split across acquisitions (C1-08) |
| `GaplessPlaybackEngine` prebuffer | `update_lock`, `_thread_lock`, re-arm flag | Sound (#6083, #6081, #6307 verified); LOW C1-04/C1-05 |
| `RealtimeProcessor` / `LevelMatcher` | `RealtimeProcessor.lock`, matcher `_lock` | #6084 only partly fixed (C1-01) |
| `HybridProcessor` / stages / optimizer | per-instance RLock; stateless Rust | Sound; lease boundary issues C2-01, C2-02 |
| `ChunkedAudioProcessor` + `processor_lease` | event-loop lease table, no closed state | MEDIUM C3-01..C3-03, LOW C3-08, C3-09 |
| Stream pumps / gates / semaphores | per-WS gates, `active_tasks_lock`, `stream_cancel` | Sound; LOW C3-06 |
| Set-queue / queue_changed ordering | `QueueSetSequencer`, `broadcast_lock` | MEDIUM C3-04 (state mirror), LOW C3-11 |
| `PlayerStateManager` / position ticker | asyncio `_lock`, `_update_seq` | LOW C3-07 |
| Chunk disk prune | class-level throttle + two locks | LOW latent C3-10 |
| Fingerprint analysis gate | `analysis_budget` Condition | Sound; MEDIUM C3-05 (no single-flight/abandon) |
| `LibraryDatabase` engine, scan slot, migrations | pool_pre_ping, shared timeouts, `ScanCoordinator`, thread+file migration lock | Sound |
| Repositories / scanner / auto-scanner | `_session_scope`, `_guarded` | MEDIUM C4-01..C4-03, LOW C4-04..C4-13 |
| Frontend store / hooks / WS client | refs, request-id guards, reconnect resync | MEDIUM C5-01..C5-03, LOW C5-04..C5-07 |

## Findings

### CRITICAL (0)

None.

### HIGH (0)

None.

### MEDIUM (11)

### C3-01: ChunkedAudioProcessor has no "closed" state - a render thread that outlives `close()` re-leases a HybridProcessor and can re-take a temp-WAV hold
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/chunk_processor_lease.py:29-57` (`hybrid_processor`, `_release_processor`); `auralis-web/backend/core/chunk_render.py:59,151` (`process_chunk_core` -> `_source.resolve()` / `hybrid_processor()`); `auralis-web/backend/core/chunked_processor.py:267-270` (`close`); `auralis-web/backend/core/seekable_source.py:353-392` (`resolve`/`_install`)
- **Status**: NEW (residual of closed #5897 / #6091: those cover a `resolve()` already in flight when `close()` runs, not one that starts afterwards)
- **Trigger Conditions**: A seek/stop/disconnect/track-skip cancels a stream while a look-ahead (or the current) chunk render is in its `load_chunk` phase, i.e. after `_raise_if_cancelled()` at the top of `render_chunk` but before `processor.hybrid_processor()` is called. The stream's `finally` (`stream_enhanced_lifecycle.py` ~152, `to_thread(processor.close)`) and `proactive_buffer._buffer_one_preset` `finally` (~116) run `close()` on another thread without taking `_processor_lock` or waiting for the executor thread (the executor thread cannot be cancelled; only the cancel event is polled, once before DSP and once before the durable write). `load_chunk` (15 s + context decode) is a measurable slice of every render, and look-ahead renders are in flight for most of the pump loop, so a seek hits this window routinely.
- **Evidence**:
  ```python
  # chunk_processor_lease.py
  def hybrid_processor(self):
      if self.processor is None:                      # close() set it to None
          self.processor = self._processor_factory.acquire(...)   # re-lease, nobody will release
      return self.processor
  def _release_processor(self):
      leased, self.processor = self.processor, None   # unsynchronised with the line above
  # chunk_render.py: load_chunk (I/O, ~100s of ms) runs BEFORE hybrid_processor(); no cancel poll in between
  audio_chunk, ... = processor.load_chunk(chunk_index, with_context=True)
  processed_chunk = AudioProcessingPipeline.process_audio(..., processor=processor.hybrid_processor(), ...)
  ```
  Same shape for the source: `close()` sets `_resolved=None` and bumps `_epoch`; a `resolve()` that *starts* after that captures the new epoch, so `_install()` succeeds and holds a conversion (`ConvertedWavRegistry` refs=1) that nobody will ever `close()`.
- **Impact**: (1) The abandoned thread pops the warm HybridProcessor the stream just released (or builds a new one), renders a full DSP pass on it, then drops it via `ChunkCancelledError`; `ProcessorFactory._active_processors[track_id]` keeps a strong reference (1-200 MB per factory comment) until the same track id is leased again. The successor stream (the seek) then misses the warm instance and pays a 200-500 ms HybridProcessor build on the seek's first chunk. (2) For m4a/aac/wma/header-less-VBR tracks, a late `resolve()` after `close()` re-decodes (or takes a hold on) the full-track temp WAV and never releases it, so the converted WAV stays on disk (tmpfs = RAM) until process exit / startup sweep. (3) `close()` also returns the HybridProcessor to the factory cache while the abandoned thread may still be inside `process()`; the successor's first chunk (cached to disk) inherits limiter/EQ state advanced by an unrelated chunk (the #6091 seam-state concern, via the cancel path rather than the two-live-streams path).
- **Suggested Fix**: Give `ChunkedAudioProcessor` a `_closed` flag set under a small `threading.Lock` shared by `close()`, `hybrid_processor()` and `SeekableSource.resolve()`; once set, `hybrid_processor()` raises `ChunkCancelledError` and `resolve()` raises `SeekableSourceClosed`. Poll `_raise_if_cancelled()` again between `load_chunk` and `hybrid_processor()`. Optionally have `close()` defer `release_lease` to the in-flight render (discard instead of return when a render was running) so a lease is never returned while an orphaned thread is inside it.

### C3-02: Abandoned `ChunkedAudioProcessor` constructor thread never closes what it builds - leaked processor lease
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/stream_enhanced_lifecycle.py:110-130` (`asyncio.wait_for(asyncio.to_thread(ChunkedAudioProcessor, ...), PROCESSOR_INIT_TIMEOUT)`); `auralis-web/backend/core/proactive_buffer.py:80-96` (`await asyncio.to_thread(ChunkedAudioProcessor, ...)`); `auralis-web/backend/core/streamlined_processor_cache.py` `get_or_build_processor` (`await asyncio.to_thread(ChunkedAudioProcessor, ...)`); lease taken at `auralis-web/backend/core/chunk_processor_init.py:179` (`processor_factory.acquire`), stored at `auralis-web/backend/core/processor_lease.py:105-112`
- **Status**: NEW
- **Trigger Conditions**: The awaiting coroutine is cancelled (seek, stop, track skip, disconnect, proactive-buffer cancel) or times out (90 s `PROCESSOR_INIT_TIMEOUT`) while the constructor thread is still running (tier-3 analysis wait, DB/`.25d` load, or the `acquire()` HybridProcessor build). `to_thread` cannot be cancelled; setting `chunk_cancel_event` only makes the *analysis-gate wait* give up (#6336) - the constructor then continues and ends with `processor_factory.acquire(...)`, returns the finished `ChunkedAudioProcessor` to a cancelled future, and the object is dropped. `stream.processor` is still `None`, so the stream `finally` (`if stream.processor is not None: close()`) never releases it. Rapid track skipping during init is the realistic trigger (each skip abandons one).
- **Evidence**:
  ```python
  stream.processor = await asyncio.wait_for(asyncio.to_thread(controller.chunked_processor_class, ...), timeout=PROCESSOR_INIT_TIMEOUT)
  # thread-side, last step of __init__:  processor = processor_factory.acquire(...)   # pops warm instance / builds; _active_processors[track_id] = processor
  # result of an abandoned to_thread is discarded; close()/release_lease() never called
  ```
- **Impact**: The leased HybridProcessor is held only by `ProcessorFactory._active_processors[track_id]` (a monitoring dict with no size bound; removed only by `release_lease`/`discard_lease` identity match, LRU eviction, `release()` or `clear_cache()`), so one 1-200 MB processor is retained per abandoned track until that track id is leased again; the warm cached instance for the track is also lost (next stream rebuilds). Memory growth compounds with the number of distinct tracks skipped mid-init.
- **Suggested Fix**: Make the constructor result owned by a done-callback like `acquire_conversion` does (`_release_late_acquire`): shield the `to_thread` future and, on cancellation/timeout, attach a callback that calls `processor.close()` off-loop when the thread finally returns. Alternatively have `init_fingerprint_and_processor` re-check `cancel_event` just before `acquire()` and skip the lease when set.

### C3-03: Mastering-recommendation analysis builds a ChunkedAudioProcessor (leasing a stream HybridProcessor) and never closes it
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/recommendation_analysis.py:47-60` (`_analyze`); lease at `auralis-web/backend/core/processor_lease.py:91-112`
- **Status**: NEW
- **Trigger Conditions**: Any uncached recommendation: `POST /api/player/load` schedules `RecommendationService.generate_and_broadcast_recommendation` for every loaded track (`routers/player_playback.py`), and `GET /api/player/mastering/recommendation/{id}` uses the same helper. Each call runs `_analyze()` in an I/O-pool thread.
- **Evidence**:
  ```python
  processor = ChunkedAudioProcessor(track_id=..., filepath=..., preset=DEFAULT_PRESET, intensity=..., chunk_cache={}, cancel_event=abandoned)
  rec = processor.get_mastering_recommendation(confidence_threshold=...)
  return rec.to_response(track_id) ...        # no processor.close(); default factory = get_processor_factory() (the live-stream consumer)
  ```
  `preset=DEFAULT_PRESET` is not `None`, so `__init__` runs `init_fingerprint_and_processor`, which *always* executes `processor_factory.acquire(...)`. The recommendation only needs the fingerprint/`MasteringFingerprint`, not a HybridProcessor.
- **Impact**: Each analysed track (a) pays a 200-500 ms HybridProcessor build for nothing, (b) pops the live-stream factory's warm instance for that (track, targets) key and drops it (the next real stream rebuilds), and (c) leaves the instance strongly referenced from `_active_processors[track_id]` forever (until the track is streamed/leased again). Over a library-browsing session the retained set grows by one HybridProcessor per distinct loaded track. Not reachable from the shipped frontend today (it does not call `/api/player/load`), but the routes are registered and the helper is shared.
- **Suggested Fix**: Wrap in `try/finally: processor.close()`, or - better - construct the analysis processor with `preset=None` (no lease) / a dedicated `processor_factory` consumer, since the analysis path never renders audio.

### C3-04: queue_changed's mirror into PlayerStateManager bypasses the set-queue generation protocol, so a racing `set_queue` can be overwritten by a stale queue
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/queue_service_base.py:236-242` (`_broadcast_queue_changed_locked` -> `player_state_manager.set_queue(...)`); contrast `auralis-web/backend/services/queue_set_mixin.py:158-167` (generation-checked state mutation)
- **Status**: NEW (adjacent to #6082 and closed #5460/#5935; not covered by either)
- **Trigger Conditions**: Queue edit E (add/remove/move/clear...) commits its engine mutation, leaves `_set_queue_engine_lock`, then enters `_broadcast_queue_changed` (reads the engine queue in `to_thread`, hydrates via DB `to_thread`, then mirrors into the state manager). A newer `set_queue` S starts inside that hydration window: S bumps the generation, mutates the state manager (`set_queue(NEW)`) *before* its engine mutation. E, which read the engine queue before S's engine `queue.set_queue`, then writes its OLD hydrated list into `player_state_manager` with no generation check and no engine lock. Two queue operations within ~10-100 ms (double click, bulk action followed by Play) are enough.
- **Evidence**:
  ```python
  # queue_set_mixin: state mutation guarded by generation ...
  async with self._set_queue_lock:
      if generation < self._set_queue_generation: return result
      queue_snapshot = await self.player_state_manager.set_queue(track_infos, start_index, broadcast=False)
  # queue_service_base: ... but the edit's mirror is not
  if hydrated and self.player_state_manager is not None:
      await self.player_state_manager.set_queue([ti for ti in resolved if ti is not None], current_index, broadcast=False)
  ```
  `set_queue` does not emit `queue_changed`, and S's later `set_track`/`set_playing` snapshots copy `state.queue` as E left it.
- **Impact**: PlayerStateManager's queue/`queue_index`/`current_track` end up describing the pre-`set_queue` queue while the engine plays the new one; every subsequent `player_state` broadcast and E's `queue_changed` frame (the last one the client receives) show the stale queue until the next edit. Stale Redux queue after a backend event.
- **Suggested Fix**: Take the generation under `_set_queue_lock` when mirroring (skip the mirror if a newer generation committed since the edit's engine mutation), or perform the mirror inside `_queue_mutation` so it is ordered with `set_queue`'s state mutation; or re-read the engine queue after acquiring the state manager lock.

### C3-05: Interactive tier-3 fingerprint extraction has no per-track single-flight, and an admitted analysis cannot be abandoned
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/chunk_processor_init.py:149-160` (`load_fingerprint(... extract_if_missing=True ...)`), `auralis-web/backend/core/mastering_target_service.py:106-178` (`load_fingerprint`: check -> compute -> store, no in-flight table), `auralis-web/backend/core/fingerprint_loading.py:~175-250` (`extract_from_audio`); gate in `auralis/analysis/fingerprint/analysis_budget.py:62-103` (`should_stop` polled only in `_wait_turn`) and `windowed_compute.py:119-121`
- **Status**: NEW
- **Trigger Conditions**: A track with no DB row and no `.25d` (freshly scanned) is played; before the first analysis finishes (can take up to the 90 s init budget) the stream is replaced - a seek, a second play command, a WS reconnect, a second window - or `GET /api/player/mastering/recommendation/{id}` / `/load` runs `_analyze()` for the same track (its ChunkedAudioProcessor also uses `extract_if_missing=True`). Each new init does its own tier-1/tier-2 lookup (both miss because the first result is not saved yet), then queues a tier-3 analysis.
- **Evidence**:
  ```python
  # analysis_budget.reserve(..., should_stop=...) -> should_stop only checked while WAITING for a ticket (_wait_turn)
  with analysis_budget.reserve(span_s / 60.0, interactive=interactive, should_stop=should_stop):
      audio, sr, probe_audios = load_track_audio(...)
      fingerprint = analyzer.analyze(audio, sr)        # no stop check once admitted
  # mastering_target_service.load_fingerprint: no key -> Future table; two callers both reach extract_from_audio
  ```
- **Impact**: The cancelled stream's already-admitted analysis runs to completion for nobody; the successor (queued behind it, or admitted concurrently when the minutes-weighted capacity allows) then repeats the identical whole-track decode + 25D analysis without re-checking the `.25d`/DB tier the first one just wrote. A seek burst during a first play therefore multiplies full-track CPU/memory work, delays the first chunk of the stream the user is waiting for (strict ticket order: each duplicate waits for the previous), and can push the successor past `PROCESSOR_INIT_TIMEOUT`. The two writers also race on the same `.25d` sidecar.
- **Suggested Fix**: Add a process-wide single-flight keyed on (filepath, file signature) around tier-3 extraction (followers wait on the leader's future, polling their own `should_stop`, then re-run tiers 1/2), and re-check tiers 1/2 after admission in `compute_windowed_fingerprint`; optionally poll `should_stop` between decode and analyze so an abandoned analysis can bail before the heavy step.

### C4-01: Reference-cloud refresh is three separate commits, not an atomic swap, and runs on every auto-scan cycle
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/learning/reference_seeder.py:186-224` (`refresh_cloud`), `auralis/library/repositories/fingerprint_similarity_mixin.py:63-146` (`set_reference_flags`, `set_reference_weights`, `clear_all_reference_flags`), `auralis-web/backend/config/startup/components.py:108-127` (`_refresh_reference_cloud`), reader `auralis/core/processing/continuous_mode.py:127-169` (`_reference_context`, `_reload_reference_cloud`)
- **Status**: NEW
- **Trigger Conditions**: `refresh_cloud` is invoked from the auto-scanner's `on_scan_complete` (scan worker thread, once per cycle, default hourly, "even an empty one"), from the fingerprint queue's `on_drained` (worker thread) and from the REST refresh endpoint. While it runs, a mastering stream renders a chunk on a `ContinuousMode` whose 60 s reference-cloud TTL (`_REFERENCE_CLOUD_TTL_S`) has just expired. Window = commit of the clear until commit of the flags, which includes `get_all_with_track_stats(limit=max_candidates)` plus scoring of every candidate (seconds on a large library). Two producers firing together (scan complete + drain wave) also interleave their clear/flag/weight commits.
- **Evidence**:
```python
cleared = repository.clear_all_reference_flags()          # commit 1: every is_reference=False, weight=0.0
all_fps = repository.get_all_with_track_stats(limit=config.max_candidates)   # seconds
selected = select_references(all_fps, config)
repository.set_reference_flags(flags)                      # commit 2
repository.set_reference_weights(weights)                  # commit 3
```
`set_reference_flags`' docstring says "clears all existing flags then sets the chosen ones in a single transaction so the cloud is never partially populated (atomic refresh)"; the method only sets/unsets the ids it is handed, the clear is a different method and a different transaction. `get_reference_cloud()` (is_reference == True AND current clause) sees an empty cloud after commit 1, a flagged cloud with all weights 0.0 after commit 2 (`apply_reference_weights` treats weight <= 0 as "unweighted"), and the final cloud only after commit 3. An *empty* result is not cached by `_reload_reference_cloud`, but a *partially populated* one (flags set, weights still 0.0, or a union of two interleaved producers) is trusted for 60 s.
- **Impact**: Chunks rendered inside the window use the legacy deficit-based EQ (empty cloud) or an unweighted reference manifold (flags without weights) while earlier/later chunks of the same track use the weighted reference-guided path; chunk files are cached to disk, so the inconsistency persists for that track until the cache is cleared. Two interleaved refreshes leave the union of both selections flagged (the refresh never unflags), with per-row weights from whichever call touched them last.
- **Suggested Fix**: Do the clear, flag and weight writes in one repository method and one transaction (single `UPDATE ... SET is_reference = (track_id IN (...)), reference_weight = CASE ...`), or serialise `refresh_cloud` behind a process-wide lock and compute the selection before the first write. Correct the `set_reference_flags` docstring.

### C4-02: Removing a scan folder while an auto-scan is walking it re-imports the folder's tracks after the prune
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:133-253` (`_run_cycle` / `_do_scan` hold a fixed `scan_folders` snapshot, `scan_future` at :187), `auralis-web/backend/routers/settings.py:63-73` (`_revoke_folder`) and :182-196 (`remove_scan_folder`) / PUT `/api/settings`, `auralis-web/backend/services/missing_tracks.py:53-102` (`prune_tracks_under_folder`)
- **Status**: NEW
- **Trigger Conditions**: An auto-scan cycle is in `scan_directories` (tens of minutes on a large or networked library). The user removes one of the folders being walked (typical: a mistakenly added huge directory). `remove_scan_folder` updates settings, calls `unregister_allowed_directory`, runs `remove_tracks_under_folder` in a thread, then `_notify_scanner` which only does `_trigger_event.set()`. The running scan is not stopped and keeps its list.
- **Evidence**:
```python
# settings.py
settings, removed = await asyncio.to_thread(repo.remove_scan_folder, body.folder)
if removed is not None:
    await _revoke_folder(deps, removed, ...)     # unregister trust + prune rows ONCE
await _notify_scanner(deps)                       # reload_config() == _trigger_event.set() only
# library_auto_scanner.py: scanner.scan_directories(scan_folders, ...) keeps walking the removed folder
```
After the scan the only cleanup is `prune_missing_tracks` (deletes rows whose *file is gone*), so rows for files that still exist under the removed folder survive.
- **Impact**: The rows the prune just deleted are re-inserted by the still-running scan thread (and enqueued for fingerprinting). The folder's tracks reappear in the library but every path-validated endpoint rejects them with 400 because trust was revoked: exactly the "visible-but-broken" state #5467/#5941 were closed to prevent, until the user removes the folder again.
- **Suggested Fix**: Have the folder-removal handlers cancel/stop the in-flight auto-scan (or scans whose directories overlap the removed one) before pruning, or make the scanner/`BatchProcessor` re-check the allowed-directory registry (or the current `scan_folders`) before each add, or re-run `prune_tracks_under_folder` after a scan whose folder list no longer matches settings.

### C4-03: A fingerprint is stored (DB and `.25d`) for whatever file version is on disk after analysis, not the version that was analysed
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/services/fingerprint_extractor.py:81-107` (`extract_and_store`), `auralis/library/repositories/fingerprint_upsert_mixin.py:116-126` (`expected_filepath` guard), `auralis/library/sidecar_manager.py:157-163` (`write` stats the audio after the fact), `auralis/library/repositories/track_repository_mutation.py:109-118` (scan discards the stale row)
- **Status**: NEW (adjacent closed issues: #5719 covers the non-concurrent rescan, #6095 covers a reset; neither covers a file replaced during analysis)
- **Trigger Conditions**: A batch or on-demand worker has claimed a track and is decoding/analysing it (seconds to minutes, plus time queued on `analysis_budget`). The audio at that path is replaced (re-rip, re-encode, tag editor rewrite that changes audio, restored backup) before the worker writes. A rescan in that window runs `update_by_filepath`, sees `_audio_changed`, and deletes the claim placeholder / old fingerprint row.
- **Evidence**:
```python
# fingerprint_extractor.py
fingerprint = self._compute_fingerprint(track_id, filepath_obj, should_stop)   # long
...
self.fingerprint_repo.upsert(track_id, fingerprint, expected_filepath=filepath) # guard: tracks.filepath == path, nothing about content
if not cached:
    self._write_sidecar(track_id, filepath_obj, fingerprint)                   # sidecar_manager.write: audio_path.stat() NOW
# fingerprint_upsert_mixin.py
source = f"SELECT {values} FROM tracks WHERE id = :track_id AND filepath = :expected_filepath"
```
- **Impact**: `upsert` is `INSERT ... ON CONFLICT DO UPDATE`, so it re-creates the row the scan just discarded, stamped with the current algorithm version, from the OLD audio. `SidecarManager.write` records size/mtime of the NEW file next to the OLD fingerprint, so `is_valid()` accepts the sidecar for the new file indefinitely. The wrong 25D vector then feeds mastering targets and similarity for that track until the algorithm version is bumped.
- **Suggested Fix**: Capture `(st_size, st_mtime)` before analysis and pass them through: re-check them just before `upsert` (store only if unchanged, else release the claim) and have the sidecar record the pre-analysis stat instead of re-statting at write time.

### C5-01: Next/Previous key-repeat bursts exceed the WS limiter; rejected `play_*` leaves UI on a track that is not playing
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/contexts/usePlaybackSessionHooks.ts:35-55` (`useTransportCommand.runTransportCommand`), `auralis-web/frontend/src/contexts/usePlaybackNavigation.ts:56-66` (`step`), `auralis-web/frontend/src/hooks/app/useAppShortcuts.ts:79-87` (ArrowRight handler), `auralis-web/frontend/src/services/keyboardShortcutsService.ts:217-235` (`handleKeyDown`, no `event.repeat` filter), `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:105-182` (`startPlayback`), `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:74-253` (`handleStreamStart`); backend limit `auralis-web/backend/config/limits.py:269` (`WS_MAX_MESSAGES_PER_SECOND = 10`), `auralis-web/backend/routers/system.py:47,132-143`
- **Status**: NEW (same class as closed #5885, which fixed it for `seek` only; the #4835 single-flight gate does not cover it, see Evidence)
- **Trigger Conditions**: Hold ArrowRight/ArrowLeft (OS key repeat ~30 Hz after the initial delay), or mash Next, for more than ~10 skips inside any 1 s window while a stream is active and the WS is connected.
- **Evidence**:
  ```ts
  // usePlaybackSessionHooks.ts:35-55 - the gate is held only while `command()` runs
  const runTransportCommand = useCallback(async (command) => {
    if (commandPendingRef.current) return false;
    commandPendingRef.current = true;
    ...
    await command();           // step(): stopPlayback(); dispatch(...); await startTrackForSettings(id)
  // useEnhancedPlayCommand.ts: startPlayback has no await before the end of the function, so
  // `await startTrackForSettings()` resolves after microtasks. wsContext.send({type:'play_enhanced'}) is
  // fire-and-forget (lines 161-179); the gate is free again ~0 ms after each send, long before the key repeats (~33 ms).
  // keyboardShortcutsService.ts:229-233: shortcut.handler() for every keydown, repeat or not.
  ```
  The backend counts every non-exempt frame against a sliding 10 msg/s window (`_RATE_LIMIT_EXEMPT_TYPES` = pong/heartbeat/buffer_full/buffer_ready only) and answers a rejected `play_enhanced` with an `error` frame carrying `command: 'play_enhanced'`. The only consumer of `error.command` is `useEnhancedSeek.ts:141` (`message.command !== 'seek'`); `useWebSocketErrors` just toasts. For `play_*` nothing reacts. Meanwhile each skip has already done `stopPlayback()` + `setCurrentTrackAndSyncQueue(target, index)` and `send()` has recorded the (rejected) command as `connState.lastStreamCommand` (`useOutgoingChannel.ts:206-208`) and `currentTrackInfoRef.current = {trackId}` (`useEnhancedPlayCommand.ts:147`).
  Of ~30 plays/s the backend accepts about 10/s; the last accepted one wins server-side. `handleStreamStart` adopts whatever `audio_stream_start` arrives and dispatches `startStreaming({trackId: message.data.track_id})` without comparing it to the requested/current track, and the first accepted stream's start/chunk frames also call `clearStreamStartWatchdog()` (`useStreamSubscriptions.ts:90,124`), so the 45 s watchdog armed for the rejected final play never fires either.
- **Impact**: After a skip burst the Redux `currentTrack`, `queue.currentIndex`, the seek target (`currentTrackInfoRef`) and the reconnect-resume command (`lastStreamCommand`) all name the last skipped track while the audio (and `streaming.enhanced.trackId`) is an earlier track in the burst. Auto-advance then moves to `currentQueueIndex + 1` of the UI's track, so the queue pointer stays out of step with the audio until the user starts a track explicitly. No error is shown except a generic rate-limit toast.
- **Suggested Fix**: (1) Ignore `event.repeat` for the Next/Previous shortcuts, or trailing-debounce navigation the way `useKeyboardSeek` does for seeks (#5885); (2) make the transport gate span the server's acknowledgement (hold until `audio_stream_start` for the requested track or a short minimum interval), not just the synchronous send; (3) handle `error{command: 'play_enhanced'|'play_normal'}` in the streaming core (reset streaming state, re-send once after the limiter window, as `useEnhancedSeek` does for seek); (4) in `handleStreamStart`, drop an `audio_stream_start` whose `track_id` differs from `currentTrackInfoRef.current.trackId`.

---

### C5-02: Local enhancement command's own broadcast is treated as an "external" change (suppression is armed only after the HTTP response)
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementCommands.ts:81-102` (`runCommand`), `:131-155` (`toggleEnabled.apply`, `markLocalEnhancementCommand` at `:125`/`:149`), `auralis-web/frontend/src/hooks/enhancement/useEnhancementStatusSync.ts:64-82`, `auralis-web/frontend/src/hooks/enhancement/enhancementBroadcastReissue.ts:497-523`; backend ordering `auralis-web/backend/routers/enhancement_controls.py:40-86` (broadcast awaited, then `return`)
- **Status**: NEW (residual gap in the closed #5864/#5874 design; the suppression window and `oncePerMessage` guard are present)
- **Trigger Conditions**: User toggles enhancement from `AlbumCharacterPane` (the only production caller of `setEnabled`) while a stream is active, and the `enhancement_settings_changed` WS frame is dispatched before the `POST /api/player/enhancement/toggle` response resolves in `runCommand` (the server emits the frame first and `await spec.request()` additionally needs `response.json()`; the tests only exercise the reverse order).
- **Evidence**:
  ```ts
  // useEnhancementCommands.ts
  await spec.request();            // line 91: POST resolves AFTER the server already broadcast
  spec.apply();                    // line 93 -> toggleEnabled.apply -> reissueEnhanced()/markLocalEnhancementCommand() (lines 125/149)
  // useEnhancementStatusSync.ts:79-81
  if (onExternalChange && isExternalChange()) {   // _lastLocalCommandAt not yet bumped -> true
    oncePerMessage(message, () => onExternalChange({ enabled, preset, intensity }));
  }
  // enhancementBroadcastReissue.ts:508  isExternalChange() = Date.now() - _lastLocalCommandAt > 2000
  ```
  `handleExternalChange` (`useEnhancementControl.ts:144-154`) sees `enabled !== enabledRef.current` (the ref only changes in `apply`) and calls `reissueActiveStreamAs(...)`. When the POST then resolves, `apply()` re-issues again. The existing spec `'does not re-issue on top of a local command'` (`useEnhancementControl.test.ts:99-117`) delivers the broadcast only after `toggleEnabled()` has finished, so the inverted order is untested.
- **Impact**: One user toggle restarts the stream twice (two `play_*` commands, two `audio_stream_start`s, the PCM ring/engine rebuilt twice, the first stream's DSP work thrown away): an extra audible gap and doubled rate-limiter budget. The same applies to `setPreset`/`setIntensity`, and for a burst of `setIntensity` calls the superseded calls never reach `apply()` (`isStale`), so `markLocalEnhancementCommand` is not called for them at all and each intermediate broadcast reads as external, which defeats the #4339 "one reissue per burst" collapse.
- **Suggested Fix**: Call `markLocalEnhancementCommand()` before `spec.request()` in `runCommand` (at command start), not inside `apply`, so the confirming broadcast is suppressed whichever way the two channels race; optionally also key the suppression on the broadcast's values matching the in-flight command.

---

### C5-03: `useLibraryQuery.refresh()` supersedes an in-flight `executeQuery` without releasing its in-flight/loading state
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQueryFetchers.ts:75-132` (`executeQuery`, finally at `:122-129`), `:135-183` (`fetchMore` guard at `:136`), `:190-201` (`refresh`); caller `auralis-web/frontend/src/components/library/Items/artists/CozyArtistList.tsx:66-67`
- **Status**: NEW (introduced with #5871's in-place refresh; closed #4609/#4885 cover the other supersession paths)
- **Trigger Conditions**: A query for a new search term (`CozyArtistList` `search` prop changes, or any `executeQuery` with rows already shown) is in flight, and a `library_updated` / `metadata_updated` / `metadata_batch_updated` / `library_tracks_removed` frame arrives before it settles (scan or tag edit running while the user types).
- **Evidence**:
  ```ts
  // executeQuery: only the NEWEST request clears the shared flags
  } finally {
    if (!isStale()) { isFetchingRef.current = false; setIsLoading(false); }   // :125-128
  }
  // refresh(): takes a new request id + aborts the HTTP call, but never touches the flags
  const result = await fetchLoadedPages({ ..., isStale: beginRequest(), signal: claimRequest() });  // :192-195
  if (result.kind !== 'refreshed') return;
  setData(...); setOffset(...); setTotal(...); setHasMore(...);                                    // :197-200
  ```
  With `dataLengthRef.current > 0` (old search results still on screen) `refresh` bypasses `executeQuery`, so `executeQuery`'s `isStale()` is true in its finally and `isFetchingRef`/`isLoading` are left set. Nothing else resets them: `fetchMore` returns at `:136` (`isFetchingRef.current` stays true) and `executeQuery` for the same query key returns at `:81` (`queryKeyRef.current === queryKey && isFetchingRef.current`), so Retry/`refetch()` for that key is also dropped. (When `dataLengthRef` is 0 `refresh` calls `executeQuery`, which dedups against the running request, so that path is safe.)
- **Impact**: `isLoading` stays true and infinite scroll (`fetchMore`) plus same-key refetch are dead until the query key changes (another search/sort). Rows shown are correct (refresh applied them), so it presents as a permanently loading list that never pages beyond the first 50.
- **Suggested Fix**: Have `refresh` own the shared flags the way `executeQuery` does (set `isFetchingRef`/`setIsLoading` for non-empty refresh and clear them in its own `finally` when still newest), or move the clear out of the `isStale()` condition into whichever request is superseded last; alternatively make `refresh` a no-op while `isFetchingRef.current` is true.

---

### LOW (30)

### C1-01: RealtimeProcessor.set_reference_audio still holds the processor lock across the O(n) reference RMS
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/realtime/processor.py:70-81` (`RealtimeProcessor.set_reference_audio`), contended at `processor.py:143-145` and `:196-199` (`process_chunk`); inner call `auralis/player/realtime/level_matcher.py:58-62`
- **Status**: Regression of #6084 (incomplete fix: commit 8e46968aa moved the RMS ahead of the matcher's `_lock` only; part (a) of the issue also required computing it before `RealtimeProcessor.lock`)
- **Trigger Conditions**: `AudioPlayer.load_reference()` (or any `set_reference_audio` call) while the audio thread is inside `get_audio_chunk()` -> `process_chunk()` with a long reference.
- **Evidence**:
  ```python
  def set_reference_audio(self, reference):
      with self.lock:                                   # processor.lock taken first
          if self.level_matcher:
              success = self.level_matcher.set_reference_audio(reference)   # does np.sqrt(np.mean(reference ** 2)) here
  ...
  def process_chunk(...):
      with self.lock:                                   # audio thread needs the same lock at chunk start
          level_matching_enabled = ...
  ```
  Probe run on this tree (10-minute stereo float64 reference, process_chunk looping on another thread):
  `set_reference_audio 302.3 ms; worst process_chunk 302.0 ms (budget 23.2 ms)`.
  `tests/auralis/player/test_locks_not_held_across_linear_work_6084.py` only asserts the matcher lock is free during the RMS, so the gap is untested.
- **Impact**: one multi-chunk audible dropout (13x the chunk budget at 10 min) on an explicit reference change during playback; also stalls `set_fingerprint()` / `_schedule_fingerprint_load()` (which take `processor.lock` under `_fingerprint_lock`). No state corruption.
- **Suggested Fix**: compute the RMS in `RealtimeProcessor.set_reference_audio` before `with self.lock` (or drop the outer lock, since `RealtimeLevelMatcher` already serialises itself) and extend the test to assert `processor.lock` is not held during the `**` call.

### C1-02: Gapless/previous-track state events are dispatched with the previous track's `current_track`
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/player_queue_navigation_mixin.py:113-124` (`next_track`), `:183-207` (`previous_track`); `auralis/player/player_file_loading_mixin.py:71-74` (`load_file`); `auralis/player/integration_manager.py:203-219` (`_on_playback_state_change`)
- **Status**: NEW (residual of the closed #5726/#4102 invariant "playback and library.current_track describe one track")
- **Trigger Conditions**: any `next_track()` / `previous_track()`; deterministic, not timing dependent.
- **Evidence**: the `seek(0)` event queued by `_on_swap` is flushed when the `with self.playback.defer_notifications():` block exits (line 117), but `_sync_current_track_from_queue()` (line 124) only runs afterwards, so `_on_playback_state_change` enriches the event with the new `current_file`/`duration_seconds` and the OLD `_current_track_dict`. Probe on this tree (callback registered on `playback`, 2-track queue, `next_track()`):
  `[('seek', '/b.wav', {'id': 1})]` - file is track 2, `current_track` is still track 1. `previous_track()`/`load_file()` behave the same (the `stop` event flushes before the sync at line 207). No further event carries the corrected track until the next state change.
- **Impact**: any engine-level listener (`IntegrationManager.add_callback`, `playback.add_callback`) that mirrors `current_track` from events shows the previous track after every queue-driven advance. Not consumed by the shipped backend (no `add_callback` caller outside the engine), hence LOW.
- **Suggested Fix**: do the `set_current_track` for the advanced entry inside the defer scope (e.g. in `_on_swap` for the track dict, or move `_sync_current_track_from_queue()` before the scope exits), the way `load_track_from_library` already does.

### C1-03: `load_track_from_library` keeps the notification-deferral scope open across DB, decode and reference-decode work
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/player_file_loading_mixin.py:149-150`; `auralis/player/integration_library.py:47-79` (`load_track_from_library`, `_auto_select_reference`)
- **Status**: NEW
- **Trigger Conditions**: any library load; another thread (user `play()`, `pause()`, `seek()`) transitions the controller while the load is still inside the scope.
- **Evidence**: `with self.playback.defer_notifications(): loaded = self.integration.load_track_from_library(...)` encloses `repos.tracks.get_by_id`, the track decode, `record_play`, `_auto_select_reference` (a second full decode plus `find_similar`) and the integration `track_loaded` notification. The `stop` event queued by `on_loaded -> load_and_stop` is therefore delivered only at the end (seconds on a cold reference decode). It is then dispatched AFTER the integration-level `track_loaded` event and after any event another thread raised in the meantime, which is the #6129 reordering window stretched from microseconds to seconds. The `seq` stamped under `_lock` (playback_controller.py:65-74) lets a mirroring listener drop it, but `IntegrationManager._on_playback_state_change` (integration_manager.py:203-219) forwards every event without a `seq` check, and there is no in-tree mirroring listener to rely on.
- **Impact**: observers see `stop` arrive after a later `play`; late/reordered state events for consumers that do not filter on `seq`. No engine state corruption.
- **Suggested Fix**: only the `on_loaded` hook (inside `_audio_lock`) needs deferral. Keep the scope around `file_manager.load_file` alone (e.g. split `load_track_from_library` into decode+swap, then post-load steps outside the scope), or make `_on_playback_state_change` drop events whose `seq` is older than the last forwarded one.

### C1-04: An in-flight auto-advance is not revalidated after its blocking decode (seek-back, stop/play, load_file are overridden)
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/player_streaming_mixin.py:171-217` (`_auto_advance_next`); `auralis/player/gapless_playback_engine.py:106-194` (`advance_with_prebuffer`, abort poll at :173-174)
- **Status**: NEW
- **Trigger Conditions**: end of track reached with no usable prebuffer (so `advance_with_prebuffer` decodes the successor, 100 ms to seconds for hi-res FLAC) and, inside that window, the user seeks back, or calls `load_file()` / `load_track_from_library()`, or `stop()` then `play()`.
- **Evidence**: `_auto_advance_next(generation)` checks `_stop_requested` and `_cleanup_in_progress` once on entry. `advance_with_prebuffer` polls only `abort` (= `_cleanup_in_progress.is_set`) after the decode, then commits `advance_if_next_matches` and swaps unconditionally. `generation` is used only for the compare-and-clear of `_auto_advancing`, never to validate that the end-of-track condition still holds. `AudioPlayer.seek()`, `load_file()` and `stop()` followed by `play()` do not set `_stop_requested` (play() clears it) and do not invalidate the pending advance. `next_track()` then resumes with `was_playing` captured before the advance (line 114), so playback resumes on the successor.
- **Impact**: a seek backwards from the last chunk, or a user-selected track, is silently replaced by the queue's next track when the decode finishes (queue index advanced, position reset to 0). No memory-safety or index corruption; it is a lost user action.
- **Suggested Fix**: pass a validity predicate alongside `abort` that re-checks, just before `advance_if_next_matches`, that the player is still PLAYING at `position >= total_samples` of the same `current_file` the advance started from (or bump a "transport epoch" in seek/load/stop and compare it), and abort without committing otherwise.

### C1-05: `cleanup()` can still lose to a user-thread `next_track()` / `load_file()` between the abort poll and the swap
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/gapless_playback_engine.py:173-215`; `auralis/player/enhanced_audio_player.py:248-291` (`cleanup`); `auralis/player/audio_file_manager.py:66-79`
- **Status**: NEW (the #6127 fix is present and works for the auto-advance thread; this is the residual for every other caller)
- **Trigger Conditions**: shutdown (`AudioPlayer.cleanup()`) while a non-auto-advance thread (backend `to_thread` for next/previous/play-track) is between `abort()` returning False and the `_audio_lock` swap; also `play()` racing `cleanup()` (`play()` checks `is_loaded()` at line 145 and calls `playback.play()` at line 155 in two steps).
- **Evidence**: `cleanup()` sets `_cleanup_in_progress`, then joins only `self._advance_thread`, then `file_manager.clear_all()`. `advance_with_prebuffer` polls `abort()` once (line 173), then does `advance_if_next_matches`, then swaps `audio_data/sample_rate/current_file` under `update_lock -> _audio_lock` with no further abort check. A user-thread caller is not joined, so `clear_all()` can run in the gap and the swap then re-populates `audio_data` after cleanup. `AudioFileManager.load_file` (decode then unconditional swap at :73-76) has no abort at all.
- **Impact**: audio buffer resurrected after `cleanup()` (a full decoded track kept alive; `play()` can reach PLAYING after cleanup). Shutdown-only, window is microseconds to milliseconds.
- **Suggested Fix**: re-check `_cleanup_in_progress` inside the swap's `_audio_lock` hold and bail before installing; have `AudioFileManager.load_file`/`next_track` take the same abort predicate; let `play()` perform its `is_loaded()` test and the state transition under one `_audio_lock` hold (nesting is already `_audio_lock -> PlaybackController._lock`).

### C1-06: Overlapping loads swap audio and `current_track` in separate critical sections, and `add_to_queue` selection assumes no concurrent append
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/integration_library.py:55-65` (`load_track_from_library`), `auralis/player/audio_file_manager.py:73-86` (`load_file`), `auralis/player/player_queue_navigation_mixin.py:219-252` (`add_to_queue`), `auralis/player/components/queue_selection.py:24-30`; route `auralis-web/backend/routers/player_playback.py:99-118`
- **Status**: NEW
- **Trigger Conditions**: two `POST /api/player/load` (or one load plus `next_track`) requests overlapping, e.g. rapid double click on two tracks whose decode times differ.
- **Evidence**: the audio swap happens under `_audio_lock` inside `file_manager.load_file`; `set_current_track(track)` runs afterwards under `_position_lock`, after the lock-free `info()`/`get_duration()` logging at audio_file_manager.py:81-84. Two overlapping loads settle in decode-completion order: `A.swap, B.swap, B.set_current_track, A.set_current_track` leaves audio of B with `current_track` of A. The route has no serialisation (NavigationService's sequencer covers only next/previous). In `add_to_queue`, `needs_load` is computed in a separate `_audio_lock` hold (the #3359/#3656 accepted TOCTOU), and `select_if_unselected(track_info)` requires `tracks[-1] is track_info`, so with two concurrent first adds only the later-appended track is selected while the audio that wins may be the earlier one: queue index points at B, loaded audio is A.
- **Impact**: `current_track` / queue selection describe a different track than the loaded audio until the next load. Self-corrects on the next load; no crash.
- **Suggested Fix**: serialise the engine's load entry points with one lock (taken outside `_audio_lock`, around decode+swap+`set_current_track`), or stamp each load with a monotonically increasing ticket and drop a stale one after its decode (the pattern `_track_generation` already uses for fingerprints).

### C1-07: `_note_failed_load` can leave the controller in ERROR while a concurrent load has just succeeded
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/player_file_loading_mixin.py:90-100` (`_note_failed_load`); `auralis/player/playback_controller.py:231-239` (`set_error`)
- **Status**: NEW
- **Trigger Conditions**: first loads of a session on two threads: load A fails fast (missing file) while load B (slower decode) swaps in between A's `is_loaded()` read and A's `set_error()`.
- **Evidence**: `with self.file_manager._audio_lock: has_audio = self.file_manager.is_loaded()` releases the lock, then `if not has_audio: self.playback.set_error()` runs in a separate step. If B's swap and `load_and_stop` land in between, B finds the state already STOPPED (no transition), A then writes ERROR. `play()` rejects ERROR (playback_controller.py:90-92) and `stop()` returns False, so the player stays wedged with audio loaded until another load succeeds.
- **Impact**: healthy player reports ERROR and refuses `play()` after a loaded track. Window is microseconds; recoverable by any successful load.
- **Suggested Fix**: make "enter ERROR only if nothing is loaded" a single operation under `_audio_lock` (nesting `_audio_lock -> PlaybackController._lock` is the established order), e.g. call `set_error()` inside the same `with` after the `is_loaded()` test, under `defer_notifications()` opened outside it.

### C1-08: `QueueController.shuffle()/unshuffle()/set_shuffle()` update flag and order in separate lock acquisitions
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/queue_controller.py:156-186` (`set_shuffle`), `:231-249` (`shuffle`, `unshuffle`); `auralis/player/components/queue_manager.py:69-75` (`clear` resets the flag under `_lock`)
- **Status**: NEW
- **Trigger Conditions**: engine API used concurrently (the backend serialises its own shuffle/unshuffle/set_queue under `_queue_mutation`, so this needs a second caller of `AudioPlayer.set_shuffle` / `QueueController.shuffle` that bypasses that lock).
- **Evidence**: `shuffle()` runs `self.queue.shuffle()` (lock hold 1) then `self.shuffle_enabled = True` (lock hold 2). A `clear()`/`set_queue()`/`unshuffle()` landing between them leaves `shuffle_enabled == True` over a cleared or restored order, which is exactly the inconsistency #5587/#5728 closed for the single-threaded case. `set_shuffle` additionally reads `already_enabled` and acts on it in separate holds (benign: `QueueManager.shuffle` keeps the first snapshot, #5315).
- **Impact**: `get_queue_info()['shuffle_enabled']` misreports until the next shuffle toggle. No index/list corruption (the queue mutation itself is atomic).
- **Suggested Fix**: wrap the pair in `with self.queue._lock:` (RLock, same borrowed-lock convention as `queue_loading.py`), then notify the change listener after releasing it.

### C2-01: Stream teardown hands the HybridProcessor lease back while an abandoned look-ahead render may still be inside `process()`
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/core/chunked_processor.py:267-270` (`ChunkedAudioProcessor.close`), `auralis-web/backend/core/chunk_processor_lease.py:29-45,47-58` (`hybrid_processor`, `_release_processor`), `auralis-web/backend/core/processor_lease.py:114-146` (`release_lease`), `auralis-web/backend/core/stream_enhanced_lifecycle.py:143-152`, `auralis-web/backend/core/stream_enhanced_chunks.py:135-150,160-165,214-218`
- **Status**: NEW (siblings #4815, #4999, #5335, #5311, #6091 are CLOSED; their fixes are in place, this is the path they leave open: cancel is signalled through `chunk_cancel_event` only on the play/seek/stop/disconnect teardown, not on the pump's own early exits)
- **Trigger Conditions**: A stream ends through a pump-internal exit that does NOT set `stream.chunk_cancel_event`: enhancement toggled off mid-stream (`stopped_early` at stream_enhanced_chunks.py:135-141), `_stream_processed_chunk` returning not-delivered (:160-165), client-disconnect detected by the pump (:143-151), or `ConnectionError` (:213-218), while the look-ahead task for chunk N+1 is mid-DSP in the stream executor thread. The pump cancels the asyncio task (`_drain_cancelled_task`) but a thread inside `run_in_stream_executor` cannot be cancelled. `run_enhanced_stream`'s `finally` then runs `await asyncio.to_thread(stream.processor.close)`. A new stream of the same track (reconnect, replay, seek issued right after) calls `ProcessorFactory.acquire()` with the identical key.
- **Evidence**:
  ```python
  # chunked_processor.py
  def close(self) -> None:
      self._release_processor()      # no _processor_lock, no wait for in-flight DSP, no cancel-event set
      self._source.close()
  # chunk_processor_lease.py
  def _release_processor(self) -> None:
      leased, self.processor = self.processor, None
      ... self._processor_factory.release_lease(leased, ...)   # processor goes back into _processor_cache
  # chunk_processor_lease.py
  def hybrid_processor(self):
      if self.processor is None:
          self.processor = self._processor_factory.acquire(...)  # lazily RE-LEASES on a closed renderer
  # chunk_render_miss.py:39  the only guard in front of hybrid_processor() is the cancel event
  _raise_if_cancelled(processor, chunk_index)
  ```
  The cancel event is set only by `signal_cancel` (ws_handlers/stream_cancel.py) and the init-timeout branch (stream_enhanced_lifecycle.py:123). `ChunkedAudioProcessor` carries no closed flag (`grep closed chunked_processor.py chunk_processor_lease.py` is empty).
- **Impact**: The #6091 invariant "a stream is the only holder, in chunk order" is broken at teardown. The orphan thread keeps running `HybridProcessor.process()` (holding its `_process_lock`) on an instance that is now in `_processor_cache`; the successor stream's `acquire()` pops it and (a) its first render blocks behind the orphan's remaining DSP (up to one chunk render, ~1-2 s of added first-chunk latency), and (b) the limiter `current_gain` / EQ `current_gains` that carry across calls are advanced by chunk N+1 of the old position before the new stream's first chunk, i.e. fed out of chunk order (the #5311 hazard, bounded in practice by the 5 s pre-roll on non-first chunks). No data corruption (the per-instance RLock serialises). Secondary hazard: if the look-ahead render only STARTS after `close()` (stream executor saturated, pool is 2 x MAX_CONCURRENT_STREAMS so unlikely on a desktop), `hybrid_processor()` leases a fresh HybridProcessor for a closed renderer that nothing will release or discard; it sits in `ProcessorFactory._active_processors[track_id]`, and a non-native-seek source (`SeekableSource.resolve()` after `close()` resets `_resolved`) would re-acquire a converted temp WAV that nobody closes.
- **Suggested Fix**: In `ChunkedAudioProcessor.close()` set `self._cancel_event` (or an internal `_closed` flag that `_raise_if_cancelled` also checks) before releasing, and make `hybrid_processor()` raise `ChunkCancelledError` once closed instead of leasing. To keep the lease exclusive, either `discard_lease()` when `_dsp_state_advanced` is True / the `_processor_lock` cannot be acquired without blocking (an in-flight render exists), or acquire `_processor_lock` (try-lock) before `release_lease` and discard on failure, mirroring the timeout path (#5335).

### C2-02: A warm leased HybridProcessor starts a stream with the previous stream's limiter/EQ/profile state (streaming path never resets it; only jobs do)
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/core/processor_lease.py:91-112` (`acquire` pops the warm instance, no reset), `auralis-web/backend/core/processor_lease.py:114-146` (`release_lease` stores it with state), `auralis/core/hybrid_processor.py:221-248` (`reset_psychoacoustic_eq`, `reset_limiter`, `reset_run_state` have callers only in `auralis-web/backend/core/job_execution.py:74-76` and `auralis/core/hybrid_processor_singleton.py:116-118`), `auralis/dsp/dynamics/brick_wall_limiter.py:196-243` (`_release_envelope` seeds from and persists `current_gain`), `auralis/dsp/eq/spectrum_gains.py:84-104` (`_smooth_gains` seeds from and persists `current_gains`)
- **Status**: NEW (the job-path analogue #4811 and the shared-instance #5311 are CLOSED; those fixes are in place, this is the lease-reuse path neither covers)
- **Trigger Conditions**: Stream A of track T ends (skip, stop, seek away) and its processor is returned warm by `release_lease`; stream B of the same (track, preset, config, targets) key starts; chunk 0 (no preceding context, `load_chunk(.., with_context=True)` has nothing before sample 0) or any chunk whose preceding context is short is not in the durable chunk cache (disk-pruned, `Clear Cache`, first play after a seek to 0 following a cache wipe).
- **Evidence**:
  ```python
  # processor_lease.py::acquire
  with self._lock:
      processor = self._processor_cache.pop(key, None)   # warm instance, state untouched
  # brick_wall_limiter.py::_release_envelope
  prev_gain = self.current_gain            # seeded from the last call of the LAST STREAM
  ...
  self.current_gain = float(gain_curve[-1])
  ```
  `grep -rn "reset_limiter\|reset_psychoacoustic_eq\|reset_run_state" auralis-web/backend auralis` shows no streaming-path caller.
- **Impact**: The first samples of an un-pre-rolled chunk are rendered with a gain release / EQ smoothing started from wherever the previous stream stopped (limiter release is 50 ms, so up to ~150-250 ms), and that render is persisted into the durable chunk cache whose key does not include any history, so the cached bytes of chunk 0 depend on what was played before. Magnitude is small (final normalisation already ceilings at -0.3 dBFS, so the limiter rarely holds gain reduction; EQ gains converge to the same fixed target), hence LOW; it is the content-determinism property #5948 wants for the cache. `last_content_profile` / `ContinuousMode.last_*` of the previous stream are also visible to the first `store_content_profile` of the new one.
- **Suggested Fix**: Reset the three states in `acquire()` for a popped (warm) instance, or in `ChunkedAudioProcessor.hybrid_processor()` on first lease (off the event loop: each reset takes `_process_lock`), and on a seek that discards continuity; keep within-stream carry as is.

### C3-06: Two more `task.cancel(); await task` sites swallow the caller's own cancellation (#6092 sibling sweep incomplete)
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/ws_handlers/connection.py:233-238` (heartbeat task) and `251-256` (`except (asyncio.CancelledError, Exception): pass` after `await live` in `teardown_connection`); `auralis-web/backend/analysis/fingerprint_queue.py:~192-199` (`stop()`: `await self._worker_task` / `except asyncio.CancelledError: pass`)
- **Status**: NEW (sibling of closed #6092, whose fix introduced `core/task_cancellation.py::await_cancelled_task` but did not convert these)
- **Trigger Conditions**: The task running `teardown_connection()` (the WebSocket endpoint task, cancelled by a second shutdown cancel / server teardown while it is parked in `await live`) or the task running `FingerprintExtractionQueue.stop()` (library-reset handler cancelled on client disconnect, or lifespan shutdown cancelled twice) is itself cancelled during the await.
- **Evidence**:
  ```python
  heartbeat_task.cancel()
  try: await heartbeat_task
  except asyncio.CancelledError: pass            # cannot tell "heartbeat finished" from "I am cancelled"
  ...
  try: await live
  except (asyncio.CancelledError, Exception): pass
  ```
- **Impact**: The caller's cancellation is lost: the endpoint returns normally (uvicorn sees a clean exit instead of a cancelled handler) and the reset/shutdown path runs on into the steps it was told to abandon. In `teardown_connection` continuing to the rate-limiter/`manager.disconnect` steps is partly desirable, which is why this is LOW; the lost cancel is the defect.
- **Suggested Fix**: Use `await_cancelled_task(task, logger)` (re-raises when `current_task().cancelling() > 0`); in `teardown_connection` run the remaining cleanup in a `finally` so the re-raise cannot skip `manager.disconnect`.

### C3-07: `set_playing(False)` with `broadcast=True` can stop the position ticker after a later `set_playing(True)` has started it
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/state_manager.py:124-138` (`set_playing`); `auralis-web/backend/core/position_ticker.py:44-58` (`_start_position_updates` / `_stop_position_updates`); only broadcasting caller: `auralis-web/backend/services/queue_edit_mixin.py:273` (`clear_queue` -> `set_playing(False)`)
- **Status**: NEW
- **Trigger Conditions**: `clear_queue()` awaits `broadcast_state(snapshot)` (a network await) between `_mutate_state(state=PAUSED)` and `_stop_position_updates()`. A `PlaybackService.play()` (REST, under `transition_lock`, `broadcast=False`) lands in that await: its `set_playing(True)` calls `_start_position_updates()`, sees the old task still alive (`not task.done()`) and does nothing. `clear_queue` resumes and cancels that task.
- **Evidence**:
  ```python
  state_snapshot = await self._mutate_state(state=new_state)
  if broadcast: await self.broadcast_state(state_snapshot)     # window
  if playing: self._start_position_updates()                    # no-op: old task alive
  else: await self._stop_position_updates()                     # kills the ticker the newer play relied on
  ```
- **Impact**: State is PLAYING with no ticker, so `position_changed` stops and the UI position freezes until the next pause/play. Needs two transport actions within one broadcast round-trip; `clear_queue` also runs `set_track(None)` right afterwards, so reach is small.
- **Suggested Fix**: Decide start/stop from the state under `_lock` (e.g. reconcile the ticker to `state.is_playing` after the await instead of using the pre-await `playing` argument), or make `set_playing` start/stop the ticker inside the same lock hold as the mutation.

### C3-08: Proactive-buffer teardown (and streamlined-worker `stop`) call `ChunkedAudioProcessor.close()` synchronously on the event loop
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/proactive_buffer.py:112-120` (`finally: processor.close()` in an `async def`); `auralis-web/backend/core/streamlined_processor_cache.py:95-99` (`_close_now`, called from `leased()`/eviction on the loop); `auralis-web/backend/core/streamlined_lifecycle.py:53-67` (`_close_cached_processors`)
- **Status**: NEW
- **Trigger Conditions**: `close()` -> `SeekableSource.close()` -> `ConvertedWavRegistry.release()` -> `_remove_temp_dirs()` (`shutil.rmtree` of a decoded full-track WAV) runs inline when the released conversion pushes the idle set over `IDLE_CONVERSIONS_RETAINED` (e.g. two idle conversions after quick skips among m4a/aac/wma tracks), and `release_lease()` may also `close()` evicted processors under the factory lock. The stream path deliberately does `await asyncio.to_thread(stream.processor.close)` and `stream_normal.py` does the same for `converted_wavs.release` (#4754); these siblings do not.
- **Evidence**:
  ```python
  finally:   # proactive_buffer._buffer_one_preset (async)
      if processor is not None and hasattr(processor, "close"):
          try: processor.close()
  ```
- **Impact**: Blocks the single event loop (all WebSockets, heartbeats, chunk sends) for the duration of a large unlink/rmtree on slow or tmpfs-pressured storage. Rare, short in the common case.
- **Suggested Fix**: `await asyncio.to_thread(processor.close)` in `_buffer_one_preset` (shielded so a cancel cannot skip it); for the streamlined worker, route eviction closes through an executor-backed helper.

### C3-09: `StreamlinedCacheWorker.stop()` closes cached processors directly, bypassing the #5064 lease deferral
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/streamlined_lifecycle.py:53-67` (`_close_cached_processors` -> `processor.close()`); compare `auralis-web/backend/core/streamlined_processor_cache.py:102-115` (`close_dropped_processor` defers while `id(processor) in _leases`)
- **Status**: NEW
- **Trigger Conditions**: Worker `stop()` while `_process_chunk` has a render running in an executor thread: the cancelled `render.cancel()` only abandons the awaiting side, `leased()` exits, and `_close_cached_processors` closes every cached processor immediately (hand-back of the lease + `SeekableSource.close()`), under the render thread. Shutdown-time only; the streamlined worker is also unfed in production (see `_audit-common.md` Backend Cache note).
- **Evidence**: `for processor in list(cache.values()): processor.close()` - no `_leases` / `_close_when_idle` check.
- **Impact**: At shutdown the in-flight render can lose its temp WAV or have its leased HybridProcessor returned to the cache mid-render; errors are logged, nothing persists. Low reach.
- **Suggested Fix**: Call `close_dropped_processor(key, processor)` for each entry so a leased one is closed when its render ends.

### C3-10: `ChunkDiskPruneMixin` throttle counter is shadowed per subclass (latent split of the shared reaper throttle)
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/chunk_disk_prune.py:81-86` (`cls = type(self)`; `cls._write_counter += 1` / `= 0`)
- **Status**: NEW (hardening; no subclass exists today)
- **Trigger Conditions**: Any subclass of `ChunkCacheManager`. `cls._write_counter += 1` reads the inherited value but *assigns on the subclass*, creating a subclass-level counter, so the subclass and the base class each count to `PRUNE_EVERY_N_WRITES` separately; the locks (`_prune_lock`, `_prune_scan_lock`) stay shared because they are only read. An instance attribute cannot shadow it (all access goes through `cls`).
- **Evidence**: `cls = type(self)` ... `cls._write_counter += 1`.
- **Impact**: None today (grep finds no subclass). A future subclass halves/doubles the throttle cadence and breaks the "one directory, one reaper cadence" invariant of #4838/#3834.
- **Suggested Fix**: Address the counter on `ChunkDiskPruneMixin` explicitly (`ChunkDiskPruneMixin._write_counter`) and add a test that a subclass shares it.

### C3-11: Engine transport calls in set-queue / queue-edit / navigation run outside `transition_lock` (pause overridden by a later `play`)
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/queue_set_mixin.py:97-106` (`_start_playback`: `asyncio.to_thread(self.audio_player.play)` then `set_playing(True)`), `auralis-web/backend/services/queue_edit_mixin.py:171-182,262-268` (`load_file`, `playback.stop`, `audio_player.stop` via plain `to_thread`), `auralis-web/backend/services/navigation_service.py:169-170` (`_sequencer.lock`, plain `to_thread`)
- **Status**: Existing: #6082 (OPEN) - its Siblings/Completeness section names exactly `queue_set_mixin` load_file + play outside `transition_lock`. Noted here only to record the state-manager divergence: a `PlaybackService.pause()` that lands between the engine `play()` and `set_playing(True)` leaves the engine PAUSED and the state manager PLAYING. These calls also use plain `to_thread` (I/O pool) rather than `run_in_transport_executor`, which is harmless only because none of them holds `transition_lock` (#6093 reasoning does not apply).
- **Trigger Conditions / Evidence / Impact / Suggested Fix**: see #6082.

### C4-04: The scanner stamps the change-detection watermark after reading the file, so an edit during the read is recorded as "already scanned"
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/batch_processor.py:168-200` (`process_single_file`; `file_mtime` stat at :189 follows `extract_audio_info` :169 and `extract_metadata_from_file` :176), `auralis/library/metadata_editor/metadata_editor.py:157-199` (in-place `audio_file.save()` under `lock_files`, a lock the scanner never takes)
- **Status**: NEW
- **Trigger Conditions**: The user saves a tag edit (`PUT` metadata route, which writes the file in place and then the DB row) while a scan is between reading that file's tags and `update_by_filepath`. Or any external writer touching a file during its scan.
- **Evidence**:
```python
audio_info = self.audio_analyzer.extract_audio_info(file_path)        # old content
metadata = self.metadata_extractor.extract_metadata_from_file(file_path)
...
track_info['file_mtime'] = Path(file_path).stat().st_mtime            # may already be the NEW mtime
track = tracks_repo.update_by_filepath(file_path, track_info, replace_tags=True)
```
- **Impact**: The scan writes OLD tags (and, with `replace_tags=True`, clears relations for tags absent from a half-written read) together with the NEW mtime/size, so `_skip_existing_track` considers the row current. The editor's own DB update can be overwritten the same way. The row stays stale until the file changes again.
- **Suggested Fix**: `stat()` before reading the content and store that pair; ideally re-stat after the read and skip the row (leave the watermark untouched) if it changed. Optionally take `lock_files([path])` around the per-file read in the scanner.

### C4-05: Playlist remove / reorder / re-position compute their writes from reads taken outside the write transaction
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/playlist_ordering_mixin.py:52-85` (`remove_track`), :140-175 (`reorder_track`), `auralis/library/repositories/playlist_membership_mixin.py:125-147` (`add_track` re-position branch), `auralis/library/repositories/track_deletion.py` (compaction after delete)
- **Status**: NEW
- **Trigger Conditions**: Two playlist mutations on the same playlist from two request threads (`asyncio.to_thread` workers) interleave, e.g. two quick drag-reorders, or two remove-track requests for neighbouring rows. The second thread's SELECT runs before the first thread's commit.
- **Evidence**:
```python
removed_position = session.scalar(select(track_playlist.c.position)...)      # outside any transaction
session.execute(delete(track_playlist)...)                                   # BEGIN happens here
session.execute(update(track_playlist).where(position > removed_position).values(position=position - 1))
...
ordered_track_ids = list(session.execute(select(track_playlist.c.track_id).order_by(position)...))  # reorder_track
for new_position, track_id in enumerate(ordered_track_ids): UPDATE ... SET position=new_position
```
Playlist `[A0 B1 C2 D3]`; `remove(B)` and `remove(C)` race: the second shifts rows with `position > 2` using its stale position and leaves `D` at 2 -> `[A0 D2]`. Two concurrent `reorder_track` calls: the later commit rewrites every row from its stale ordering and silently discards the earlier move. The docstrings ("single transaction", "SQLite serializes writes within a transaction", "positions contiguous 0..N-1 under concurrent traffic") describe more than is true.
- **Impact**: Gaps in `position` (tolerated by `reorder_track`'s logical-index healing, so no corruption) and lost reorder updates. No duplicate PKs or orphaned rows.
- **Suggested Fix**: Start the transaction before reading (`BEGIN IMMEDIATE` via `session.execute(text("BEGIN IMMEDIATE"))`, or perform a no-op write first), or express compaction/reorder as single statements that recompute positions in SQL (`ROW_NUMBER() OVER (ORDER BY position) - 1`).

### C4-06: Artist find-or-create resolves on `normalized_name`, but only `name` is unique, so a concurrent first-insert of two spellings creates duplicate artists
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_lifecycle.py:41-67` (`_get_or_create`), :93-114 (`_get_or_create_artists`), `auralis/library/models/artist.py:30-31` (`name` unique, `normalized_name` only indexed)
- **Status**: NEW (the closed #2594 fixed the exact-name case)
- **Trigger Conditions**: Two scans (default allows 4) or a scan plus a tag edit add tracks for a not-yet-known artist at the same moment, with spellings that normalise equal but differ in `name` ("AC/DC" vs "ac/dc", punctuation or accent variants).
- **Evidence**:
```python
row = session.execute(select(model).where(Artist.normalized_name == normalized)).scalars().first()
if row is None:
    session.execute(sqlite_insert(model).values(name=name, normalized_name=normalized).on_conflict_do_nothing())
    row = <re-select by normalized_name>
```
`ON CONFLICT DO NOTHING` only fires for the `name` UNIQUE; two different `name` values never conflict, both inserts commit.
- **Impact**: Two artist rows with the same `normalized_name` (the duplicate the normaliser exists to prevent); the artist list shows the artist twice and later `.first()` lookups pick one arbitrarily.
- **Suggested Fix**: Add a unique index on `artists.normalized_name` (migration, with a dedupe step) so the conflict path covers it, or serialise artist creation behind a lock.

### C4-07: `add()` / retag can lose to `prune_orphans` and fail with a foreign-key error on a pre-existing, about-to-be-pruned album/artist/genre
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_lifecycle.py:41-67,176-225` (`add`), `auralis/library/repositories/track_repository_mutation.py:73-118` (`update_by_filepath`), `auralis/library/repositories/orphan_pruning.py:51-84`, `auralis/library/repositories/track_deletion.py:36-82`
- **Status**: NEW
- **Trigger Conditions**: Thread 1 deletes the last track of album/artist/genre X (`cleanup_missing_files`, `remove_tracks_under_folder`, track delete) and `prune_orphans` removes X when it commits. Thread 2 (another scan, or the post-scan prune of the previous cycle) is inside `add()` having already SELECTed X (reads are outside the write transaction) and then inserts a track/association row pointing at X.
- **Evidence**: `_get_or_create` returns the existing X without taking any lock; `session.add(track); session.commit()` runs later with `foreign_keys=ON`, so the INSERT into `tracks`/`track_artist`/`track_genre` raises `IntegrityError`, which `_guarded("Failed to add track")` turns into `None`.
- **Impact**: The file is reported as `failed` ("Database insert failed") in `ScanResult.failures` although it is valid; the next scan retries it. No corruption.
- **Suggested Fix**: Retry `add()` once on `IntegrityError` (re-running the get-or-create), or perform the `_get_or_create` lookups inside the write transaction.

### C4-08: `relocate_missing_track` failure default is read as "not a moved file", so a failed relocation becomes a twin row that the post-scan prune then deletes the original of
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/batch_processor.py:201-214`, `auralis/library/repositories/track_repository_relocation.py:53-74` (`_guarded`), `auralis/library/repositories/base.py:157-189,228-235` (`_guarded` swallow)
- **Status**: NEW (sibling of the #6212/#5940 pattern in the scan path)
- **Trigger Conditions**: The relocation commit raises (lock wait past the 60 s busy timeout during heavy fingerprint writes, or an IntegrityError). Typical situation: an album folder was renamed.
- **Evidence**:
```python
moved = tracks_repo.relocate_missing_track(file_path, filesize, duration)   # None on "no unique match" AND on a swallowed DB error
if moved: ...
track = tracks_repo.add(track_info)                                           # adds a twin at the new path
```
Then `prune_missing_tracks` (`cleanup_missing_files`) deletes the old row because its file is gone.
- **Impact**: The old row's playlist membership, favourite flag, play counts and fingerprint are lost, which is the data loss #5880 introduced relocation to avoid.
- **Suggested Fix**: Have `relocate_missing_track` use `_session_scope()` (raise on a DB error, `None` only for "no unique match"), and let the batch processor report the file as failed instead of adding.

### C4-09: `SimilarityAutoFitWorker.start()` after a timed-out `stop()` is a no-op and the abandoned thread then exits, leaving the worker dead
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/services/similarity_autofit_worker.py:58-80` (`start` / `stop`), `:90-96` (`_run`)
- **Status**: NEW (sibling of the closed #5954, which only fixed the auto-scanner and the fingerprint queue)
- **Trigger Conditions**: Library reset (stop all workers, delete, start all workers) while `fit()` is mid-batch and does not observe `_stop_event` within `_STOP_TIMEOUT_SECONDS` (10 s), e.g. blocked on a locked DB read or in the non-interruptible numpy/calibration phase.
- **Evidence**:
```python
async def start(self):
    if self._task is not None and not self._task.done():   # abandoned thread still running -> returns, stop_event stays set
        return
    self._stop_event.clear()
    ...
# stop(): except TimeoutError: warn and abandon
# _run(): while not self._stop_event.wait(interval): ...   # stop_event still set -> thread exits
```
- **Impact**: After the reset the similarity auto-fit/refit worker never runs again until process restart (K-NN graph builder never becomes available, `/api/similarity/*` stays unfitted after the library is repopulated).
- **Suggested Fix**: In `start()`, if the old task is still running, wait for it or restart with a fresh `Event` per run (as the fingerprint queue does by counting live workers).

### C4-10: `FingerprintNormalizer.normalize()` re-reads `self.stats` per dimension while a refit publishes a new dict
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/analysis/fingerprint/normalizer.py:170-171` (publish) vs `:195-198` (`normalize` loop `stats = self.stats[dim_name]`); `auralis/analysis/fingerprint/similarity.py:129-146` (`reference_distance` updated after the stats are already live)
- **Status**: NEW
- **Trigger Conditions**: The auto-fit worker or `POST /api/similarity/fit` refits (`needs_refit`) while another thread is mid-`normalize()` (a similarity request or a K-NN graph batch).
- **Evidence**: `#5243` made the publish one dict assignment, but readers index `self.stats` 25 times per call, so a swap between iterations normalises one vector with dimensions from two different models; `fit()` also sets `self.fitted = True` / `reference_distance` after `self.stats` is already new.
- **Impact**: One similarity result (or a few edges in a graph build) with a mixed-range distance; the score scale briefly mismatches `reference_distance`.
- **Suggested Fix**: Snapshot `stats = self.stats` once at the top of `normalize()` and publish `(stats, reference_distance)` together as one immutable object.

### C4-11: Album artwork is written in place over its content-addressed file, which the DB may already reference and a GET may be streaming
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/artwork.py:177-190` (`_save_artwork`), `auralis-web/backend/services/artwork_downloader.py:205-209` (`filepath.write_bytes`), `auralis-web/backend/routers/artwork_manage.py:40-47` (the comment acknowledges an "in-place overwrite (same path, fresh mtime)")
- **Status**: NEW
- **Trigger Conditions**: Re-extraction or re-download yields the same bytes (same `album_<id>_<hash>.<ext>` name) as the album's current artwork — the "Extract artwork" action on an album that already has that art, or two scans adding tracks of one album in parallel — while the artwork GET (or thumbnail renderer) reads that file.
- **Evidence**: `with open(artwork_path, 'wb') as f: f.write(artwork_data)` truncates the live file before writing; unlike the `.25d` writers (`utils/atomic_write.py`, #4508/#4638) there is no temp-file-plus-`os.replace`.
- **Impact**: A reader sees a zero-length or partial image (broken cover, or a thumbnail cached from a truncated source). Self-heals on the next load.
- **Suggested Fix**: Write via a temp file in the same directory and `os.replace`, or skip the write when the target already exists with identical size.

### C4-12: `RepositoryFactory` lazy properties are unsynchronised and the fingerprint scheduler is first touched by N worker threads at once
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/factory.py:46-53` (docstring "created during application startup"), `:124-130` (`fingerprint_scheduler`), `auralis/services/fingerprint_queue.py:222-225` (`_claim`)
- **Status**: NEW
- **Trigger Conditions**: `FingerprintExtractionQueue.start()` spawns all workers together; nothing in startup touches `repository_factory.fingerprint_scheduler` first (checked: `config/startup/*` only touches `settings`/`fingerprint_stats`), so each worker's first `_claim` races `if not self._fingerprint_scheduler_repo: self._fingerprint_scheduler_repo = FingerprintSchedulerRepository(...)`.
- **Evidence**: The #5310 claim cursors live on the scheduler instance ("RepositoryFactory keeps one per process"); several instances may be created, each with its own `_cursors` starting at 0, the last assignment winning.
- **Impact**: Correctness is preserved by the DB-level claim; the early claims use cursor 0 on private instances, so every worker walks from the lowest unfingerprinted id and loses races on the same row (up to `_MAX_CLAIM_RACES`) on the first call. Performance only.
- **Suggested Fix**: Create the repositories eagerly in `RepositoryFactory.__init__` (they are cheap) or guard the lazy getters with a lock.

### C4-13: A K-NN graph build aborts with an FK error if a neighbouring track is deleted while the multi-minute build runs
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/analysis/fingerprint/knn_graph.py:124-200` (`_build_graph_locked`), `auralis/library/repositories/similarity_graph_repository.py:42-56` (`replace_edges`), model FK at `auralis/library/models/fingerprint.py:255-256`
- **Status**: NEW
- **Trigger Conditions**: `POST /api/similarity/graph/build` runs while a scan prune (`cleanup_missing_files`), a scan-folder removal or a track delete removes a track that is in the fitted similarity candidate set.
- **Evidence**: `find_similar()` returns `similar_track_id`s from fingerprints read earlier; `replace_edges` inserts them with `track_id`/`similar_track_id` FKs (`foreign_keys=ON`). The batch rolls back and the exception propagates out of `build_graph` -> 500.
- **Impact**: The build fails partway (earlier batches already replaced, later ones keep old edges); it must be re-run. No corruption.
- **Suggested Fix**: Filter `edges` to ids that still exist inside `replace_edges` (or catch `IntegrityError` per batch and retry without the missing ids).

---

### C5-04: `AudioPlaybackEngine` async start window drops a user pause and can swallow a post-stop start
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:90-142` (`startPlayback`, `start`), `:147-160` (`pausePlayback`), `:201-212` (`stopPlayback`); `auralis-web/frontend/src/hooks/enhancement/streamingCoreLifecycle.ts:128-139` (`startPlaybackWhenBuffered`); `auralis-web/frontend/src/hooks/enhancement/usePlaybackTransport.ts:90-94`; `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:216-222`
- **Status**: NEW (residual gap in the closed #6043 fix; `startAttempt`/`starting` are present and correct for stop/dispose)
- **Trigger Conditions**: (a) User pauses inside the start window (between `startPlayback()` and the end of `start()`: `await audioContext.resume()` when suspended, `await bufferScheduler.ensureReady()` = `audioWorklet.addModule(...)` on the first track). (b) `stopPlayback()` (seek / `sendSeek`) while a `start()` attempt is still awaiting, then a new `startPlayback()` before that old attempt unwinds.
- **Evidence**:
  ```ts
  startPlayback(): Promise<void> {
    if (this.positionTracker.isPlaying()) return Promise.resolve();
    this.starting ??= this.start(this.startAttempt).finally(() => { this.starting = null; });  // :92
    return this.starting;
  }
  pausePlayback(): void { if (!this.positionTracker.isPlaying()) return; ... }                  // :147-150, 'playing' only set at :136
  stopPlayback(): void { this.startAttempt += 1; ... }                                          // :202; old `starting` promise is NOT cleared
  ```
  (a) `pausePlayback()` returns immediately because the state is not yet `'playing'`; the hook sets `pauseHoldRef=true` and `setIsPaused(true)`, but the in-flight `start()` never re-checks the hold and finishes with `setState('playing')`, whose callback does `core.setIsPaused(false)` (`useEnhancedStreamStart.ts:216-218`). (b) The second caller gets the old promise (`??=`), whose attempt token is stale, so it exits at `:119`/`:129` without starting; playback resumes only when a later chunk calls `startPlaybackWhenBuffered` again, and not at all if the (short or flow-paused) stream has nothing more to send.
- **Impact**: (a) A pause pressed in the first few hundred ms of the first track is silently undone (audio plays while the transport may show paused until the next state event). (b) After a seek issued during startup, audio can stay silent until another chunk arrives. Narrow windows; self-heals in the common case.
- **Suggested Fix**: In `start()`, re-check a `pauseRequested` flag (or let `pausePlayback` record intent when state is not `playing` and `starting` is set) before `setState('playing')`; in `stopPlayback()`/`dispose()` also null `this.starting` so a following `startPlayback()` creates a fresh attempt.

---

### C5-05: `lastRecoveryAttemptRef` is never reset, so the one-shot chunk-failure recovery is spent for the lifetime of the session
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:164-190` (`handleStreamError`), ref declared `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:114`
- **Status**: NEW (residual of closed #4655's loop guard)
- **Trigger Conditions**: A transient chunk failure (worker timeout, backend busy) reports `recovery_position` P for track T and recovery succeeds; later in the same app session the user replays T (or it comes round again) and the same chunk fails at the same P.
- **Evidence**:
  ```ts
  const alreadyAttempted =
    lastRecoveryAttemptRef.current?.trackId === trackId &&
    lastRecoveryAttemptRef.current?.position === recoveryPosition;
  if (typeof recoveryPosition === 'number' && Number.isFinite(recoveryPosition) && !alreadyAttempted) {
    lastRecoveryAttemptRef.current = { trackId, position: recoveryPosition };   // grep: never cleared anywhere else
  ```
  The ref is not reset by `playEnhanced`/`startPlayback`, a successful stream, a stop, or a seek. Chunk boundaries are deterministic, so the same (trackId, position) pair recurs on any replay of the same track.
- **Impact**: The second failure at the same point is treated as terminal (`endActiveStream`, `cleanupStreaming`), killing playback although a fresh stream attempt is exactly what the guard intends to allow. The guard is meant to bound a loop within one stream, not across plays.
- **Suggested Fix**: Clear `lastRecoveryAttemptRef.current = null` whenever a new user-initiated play/seek starts (in `useEnhancedPlayCommand` and `sendSeek`), or when the recovered stream passes the failing position.

---

### C5-06: Library lists, album grid and stats are not re-synced after a WebSocket reconnect
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:316-324`, `auralis-web/frontend/src/hooks/library/useLibraryChangeSync.ts:374-392` (`useLibraryChangeSync`), `auralis-web/frontend/src/components/library/Items/artists/CozyArtistList.tsx:66-67` (all refresh only on `library_updated`-family frames); compare `useScanProgress.ts:267-269` (resync on `connected`) and `components/playlist/usePlaylistWebSocket.ts:39-45` (refresh on reconnect, #6042)
- **Status**: NEW
- **Trigger Conditions**: The socket is down (backend restart, retries up to the give-up limit) while the library changes (startup auto-scan, folder removal, tag edit); the `library_updated`/`metadata_*`/`library_tracks_removed` frame is broadcast-only and never replayed on reconnect (the connect-time push in `ws_handlers/connection.py:140-170` carries only enhancement settings and `player_state`).
- **Evidence**: Only scan status and the playlist list register a reconnect refresh; `grep connectionStatus|isConnected` in `hooks/library` finds no other consumer. `useLibraryWithStats`, `useLibraryChangeSync` (React Query `['albums']`, `['album-fingerprint']`) and the artist list invalidate solely inside their message handlers.
- **Impact**: Track list, stats, album grid and artist list keep the pre-outage data (removed albums remain clickable and 404 on open; new tracks missing) until a manual refresh or remount.
- **Suggested Fix**: Add one `useReconnectResync` effect (connectionStatus transition to `connected`) that calls `refreshTracks`/`refetchStats`, `queryClient.invalidateQueries(['albums'])` and the artist `refresh`, the same way `usePlaylistWebSocket` does for playlists.

---

### C5-07: `connect()` increments the provider ref count on every retry but nothing decrements it
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:93-96` (`connState.refCount++`), `:179-197` (`disconnect`), `:216` (`useReconnectOnNetwork(connectionStatus === 'error', connect)`), `auralis-web/frontend/src/hooks/websocket/useReconnectOnNetwork.ts:20-31`
- **Status**: NEW
- **Trigger Conditions**: The manager gives up (status `'error'`) and the `online`/`visibilitychange` retry calls `connect()` one or more times (it also fires while a reconnect backoff is merely between attempts and the transient `'error'` status from the socket `error` event is set).
- **Evidence**: `connect` is the effect's mount-time entry and the retry callback; each call does `connState.refCount++` but only the effect cleanup calls `disconnect()` (once). After N retries the count is N+1 for one provider, so `connState.refCount === 0` is never reached on the last unmount and `closeCurrentManager()` is skipped.
- **Impact**: On provider unmount (HMR in dev, test teardown, a future second provider) the socket, its handlers and its reconnect timer survive and keep dispatching into stale subscribers. Not reachable in the packaged app's steady state (the provider lives for the window's lifetime).
- **Suggested Fix**: Separate "acquire" (refcount) from "ensure connected" - have `useReconnectOnNetwork` call an internal `ensureConnected()` that does not touch `refCount`, or only increment in the mount effect.

---

## Relationships

- **C3-01, C2-01, C3-02, C3-03, C3-09, C3-08** share one root: `ChunkedAudioProcessor.close()` / lease release has no closed state, cannot wait for or cancel a render already inside the stream executor, and is called from paths (constructor abandonment, recommendation analysis, streamlined worker, proactive buffer) that either skip it or run it on the loop. One fix (a closed flag checked in `hybrid_processor` + a render-in-flight count that defers release, mirroring `streamlined_processor_cache.leased()`) closes most of them.
- **C2-02** compounds C3-01/C2-01: a lease released while a render is still running, or never reset, hands the next stream mutated limiter/EQ/`last_*` state.
- **C3-04, C3-11, C3-07** are the state-manager mirror of the engine transport race tracked in #6082: the state manager and the engine are updated by separate calls outside one lock.
- **C4-01, C4-03, C4-05, C4-07, C4-13** are read-compute-write patterns spanning separate commits or sessions; C4-07 and C4-13 both turn a deletion into an FK failure.
- **C4-02, C4-04, C4-08** all involve the scanner acting on a stale snapshot (folder list, file mtime, failure default read as "not found"), the last being the `_guarded()` sentinel pitfall.
- **C5-01 and C5-02** both stem from the frontend assuming command acknowledgement ordering the backend does not provide (rate-limited commands, broadcast before HTTP response).
- **C1-04, C1-05, C1-06, C1-07** are the same family: a blocking decode between a read and a commit with no revalidation.

## Prioritized Fix Order

1. C3-01 / C3-02 / C3-03 (+ C2-01, C3-09): processor lease lifecycle; leaks and double-use of a stateful processor and temp-WAV holds.
2. C4-02: removed scan folder re-imported (data the user explicitly deleted comes back).
3. C5-01: skip bursts desync UI from playback; cheap fix (coalesce or ack commands).
4. C3-04: stale queue mirror overwriting a newer `set_queue`.
5. C4-03 and C4-01: wrong-version fingerprint and non-atomic reference-cloud swap.
6. C3-05: tier-3 analysis single-flight and abandonability.
7. C5-02, C5-03: double stream re-issue, stuck infinite scroll.
8. C1-01: finish #6084 (compute reference RMS before `RealtimeProcessor.lock`).
9. Remaining LOW items, batching by file (C4-05..C4-13, C1-02..C1-08, C3-06..C3-11, C5-04..C5-07, C2-02).

## Verified-OK Checklist Items (per dimension)

### Dimension 1: Player Thread Safety

- RLock usage / lock scoping: every `PlaybackController` state and position access is under `_lock` (`playback_controller.py:76-257`); `_advance_thread`, `_advance_generation` are written/read under `_audio_lock` (`player_streaming_mixin.py:114-124,215-217`, `enhanced_audio_player.py:277-279`); `tracks_played` under `_stats_lock` (`integration_reporting.py:66-70,88-90`); prebuffer fields under `update_lock`, `prebuffer_thread` / `_rearm_requested` / `_prebuffer_exiting` under `_thread_lock` (`gapless_prebuffer.py:54-94`).
- Mixin lock ownership (#5836): `QueueManager._lock` is created in `queue_manager.py:28` and every method of `QueueNavigationMixin`, `ShuffleMixin`, `QueueSelectionMixin` takes it for its whole read-modify-write; `_invalidate_shuffle_snapshot_unlocked` is only called with it held. `QueueController` mixins borrow `self.queue._lock` (`queue_locked_state.py`, `queue_loading.py:83,113`). `update_lock` / `_thread_lock` / `_position_lock` / `_stats_lock` are created in the base `__init__` and only annotated in the mixins.
- Lock orders: `update_lock -> _audio_lock -> PlaybackController._lock` (`gapless_playback_engine.py:199-215`) and `_position_lock -> _audio_lock -> PlaybackController._lock` (`integration_reporting.py:121`) hold at every call site; `_audio_lock -> queue._lock` only in `get_audio_chunk` (`player_streaming_mixin.py:113`) and no path takes `queue._lock` then `_audio_lock`/`update_lock` (change listener runs after the queue lock is released, `queue_controller.py:56-63`); `_thread_lock` is never held while waiting on `update_lock` or joining; `_stats_lock` never nests inside `_position_lock`. `grep "with .*_audio_lock|update_lock"` shows no other acquirers.
- Linear work outside audio-thread locks: `queue_loading.py:82` serialises rows before `queue._lock` (#6084 b); `level_matcher.py:62` measures RMS before the matcher lock (#6084 a, matcher half only; processor half is C1-01). No other O(n) work under `_audio_lock` (swap, slice+copy of one chunk only).
- Prebuffer re-arm (#6083): the exit decision and `_rearm_requested` share `_thread_lock` (`gapless_prebuffer.py:89-94`); an edit after the worker's last re-peek either sets the flag (worker alive, not exiting) or spawns a new worker (exiting) (`:64-69`); stale stores are rejected at use by `_prebuffer_matches` / `advance_if_next_matches`.
- Gapless swap snapshot (#6081): `_track_position_snapshot()` reads position, duration and file in one `_audio_lock` hold (`integration_reporting.py:112-126`); `_get_position_seconds` is only called from it; nothing outside the engine reads these (`grep file_manager|get_playback_info` in backend: no hits).
- Auto-advance vs cleanup (#6127/#5706): `abort` is polled after the decode and before the commit (`gapless_playback_engine.py:173`); a `False` `next_track()` ends through `_finish_playback()` once (`player_streaming_mixin.py:187-194`, stop() makes subsequent callbacks return silence); `_cleanup_in_progress` set before the join (`enhanced_audio_player.py:254`). Residual for non-advance threads is C1-05.
- Gapless swap across sample-rate change (#6307): swap installs `audio_data`, `sample_rate`, `current_file` together under `_audio_lock` (`gapless_playback_engine.py:205-208`); `get_audio_chunk` reads the rate outside the lock by documented design (#5729) and costs at most one chunk.
- State transitions: `play/pause/stop/seek/load_and_stop` mutate state under one `_lock` hold and notify after release; `seek()` and the `position` setter hold `_audio_lock` across clamp+seek with `defer_notifications()` outer (`enhanced_audio_player.py:204-212,242-244`); seek vs gapless swap serialised by `_audio_lock`; `_stop_requested` / `_pause_requested` interleavings with `play()/stop()/pause()` all end consistent with the last user action (checked each of the 4 orderings).
- Audio-callback read vs `stop()` (#6308): `read_and_advance_if_playing` tests PLAYING and advances in one `_lock` hold (`playback_controller.py:170-180`); no other reader gates a decision on `state` and `position` in separate acquisitions (`get_playback_info` reads both only for display).
- Pause flag across a skip (#6309): `pause()` sets before transition and keeps it on failure; only `play()` clears. The next/previous resume reaches PLAYING via `playback.play()` without clearing, but re-pauses immediately when the flag is set (`player_queue_navigation_mixin.py:153-158,201-206`), so the flag cannot go stale in PLAYING (a brief PLAYING flicker is the documented trade-off).
- Completion accounting (#6313): only `_auto_advance_next` passes `completed=True`; `record_track_completion` under `_stats_lock` after a successful advance; backend `NavigationService` calls `next_track()` with the default.
- Queue modifications during playback: all `QueueManager` mutators hold `_lock`; `advance_if_next_matches`, `step_previous`, `rollback_index` (compare-and-set), `remove_if_index_matches_current`, `insert_track`, `reorder_tracks`, `move_track` are single-acquisition read-modify-writes; `load_playlist`/`set_queue` replace contents atomically (`queue_loading.py:83-94,113-128`).
- Position/duration invariant: `read_and_advance_position` clamps (`playback_controller.py:165-168`), `seek()` rejects NaN and clamps inf (`enhanced_audio_player.py:191-211`), `PlaybackController.seek` clamps again, `load_and_stop`/`on_swap` reset position inside the swap's `_audio_lock` hold. `get_queue_info()` `has_next`/`has_previous` agree with `peek_next`/`advance_if_next_matches`/`step_previous` including repeat and `current_index == -1` (`queue_manager.py:231-232` vs `queue_navigation.py:38-114,129-141`).
- Audio buffer access: slices are `.copy()`d under `_audio_lock` (`audio_file_manager.py:148`); the prebuffered array becomes `audio_data` by reference but is never mutated in place; `process_chunk` copies before modifying (`processor.py:147`); the reference array is only read for its RMS.
- Callback safety: mutators snapshot under `_lock` and notify outside; `defer_notifications()` is thread-local, re-entrant and flushes in order on the outermost exit including the exception path (`playback_notifier.py:33-78`); every in-tree `_audio_lock`-held hook (`on_loaded`, `on_swap`) is wrapped in `lock_held_hook()` (`audio_file_manager.py:78`, `gapless_playback_engine.py:210`) and called inside a caller-opened defer scope (`player_file_loading_mixin.py:71,149`, `player_queue_navigation_mixin.py:113`); no third lock-held hook found (`get_audio_chunk`, `_note_failed_load`, `cleanup` take `_audio_lock` but fire no notification inside it). `seq` is assigned under `_lock` (`playback_controller.py:65-74`); there is no in-tree state-mirroring listener (the only `add_callback` caller is `IntegrationManager.__init__`), so no listener drops an older `seq`.
- Prebuffer worker shutdown: `_shutdown` re-checked under `_thread_lock` (`gapless_prebuffer.py:57`), worker polls it every 200 ms during the load, `cleanup()` snapshots and joins outside the lock (`gapless_playback_engine.py:262-271`).
- Fingerprint staleness: generation bump, `_current_fingerprint` and `processor.set_fingerprint` all under `_fingerprint_lock` (`fingerprint_loader_mixin.py:55-65,98-122`); `cleanup()` bumps the generation first (`enhanced_audio_player.py:263-264`).
- Realtime chain: `AutoMasterProcessor` and `RealtimeLevelMatcher` serialise on their own locks, `StreamingPeakCeiling.apply/reset` on a leaf lock, `PerformanceMonitor` only under `RealtimeProcessor.lock`; the order `processor.lock -> component._lock` is never reversed (the audio thread drops `processor.lock` before entering a component).

### Dimension 2: Audio Processing Pipeline

- Chunk loop copies (offline engine loop): `auralis/core/mastering_chunk_loop.py:175-188` (fresh `read_chunk` array; `process_chunk` does `audio.copy()` at `mastering_process_chunk.py:84`); crossfade tail is `.copy()`-ed (`mastering_chunk_assembly.py:143,197`); the "no cross-chunk DSP state" premise holds (no `pipeline.*` writes in the loop or in `mastering_branches/continuous.py`; only `mastering_prepare.py:144-147,161,184,226` write per-file state once, under `SimpleMasteringPipeline._process_lock` held by `master_file`, `simple_mastering.py:138`).
- Live chunk path copies: `HybridProcessor._process_impl` -> `validate_and_normalize_input` returns new arrays (`remove_dc` allocates, `hybrid_stage_dispatch.py:110`, `dsp/dc_blocker.py`), `ContinuousMode.process` starts with `target_audio.copy()` (`continuous_mode.py:186`), `amplify()` copies before `*=` (`dsp/basic.py:55-61`), `BrickWallLimiter.process` returns `audio * gain_curve` (new array, `brick_wall_limiter.py:150-155`), WOLA EQ only reads `audio` (`eq_curve.py:73-111`); grep for augmented assignment on caller-owned arrays in `core/processing`, `core/processors`, `dsp/basic.py`, `dsp/utils`, `dsp/dynamics` finds only local buffers.
- Shared mastering targets are never mutated by a worker: `MasteringTargetService` returns the same cached `(fingerprint, targets)` tuple (`mastering_target_service.py:134-141`) to every stream, but the only consumer is `chunk_processor_init.py:149`; `ProcessorLeaseMixin._build_processor` deep-copies targets into the processor (`processor_lease.py:76`); `convert_targets_to_parameters` only reads (`fixed_target_params.py:41-96`); `generate_targets_from_fingerprint` returns a fresh dict from a read-only `__dict__` (`mastering_target_generation.py:60-96`); no `targets[...] =`, `.update`, `.pop` on `mastering_targets` or `fingerprint` anywhere under `auralis-web/backend` (grep).
- Per-instance serialisation of HybridProcessor state: `process`, `set_fixed_mastering_targets`, `set_processing_mode`, `reset_psychoacoustic_eq`, `reset_limiter`, `reset_run_state` all take `_process_lock` (RLock) (`hybrid_processor.py:145,168,228,234,247,274`); `_process_from_clean_state` holds it across reset+process (`hybrid_processor_singleton.py:115-119`); no code outside `auralis/core/processing` and `hybrid_*` touches `brick_wall_limiter`, `psychoacoustic_eq`, `continuous_mode`, `adaptive_mode`, `eq_processor`, `current_targets` (grep over `auralis/` and `auralis-web/backend/`). The non-lease shared path (`ProcessorFactory.get_or_create`) has no production caller (only `AudioProcessingPipeline.select_processor`, itself only reached from tests).
- Inner stateful DSP locking: `PsychoacousticEQ._smooth_gains` and `reset()` hold `_state_lock` (`spectrum_gains.py:84-104`, `psychoacoustic_eq.py:157-166`); `VectorizedEQProcessor` and `process_with_psychoacoustic_eq` keep no instance state; `BrickWallLimiter` state is only reachable through the locked HybridProcessor (and `_apply_final_normalization` builds a fresh limiter per call, `continuous_dsp_ops.py:264`).
- Lazy attributes inside `ContinuousMode` (`_reference_cloud`, `_distance_stats`, `_quality_metrics`, `_mastering_evaluator`, `_quality_gate_call_count`) are read-modify-written only from `process()`, which runs under the owning HybridProcessor's `_process_lock` (`continuous_mode.py:128-170`, `continuous_quality.py:41-67`); the reference-cloud DB read uses `BaseRepository._session_scope()` per call (`fingerprint_similarity_mixin.py:53`).
- Rust DSP boundary: `compute_fingerprint_wrapper` copies the array to a `Vec<f32>` then runs the compute inside `py.detach(...)` wrapped in `catch_unwind` (`vendor/auralis-dsp/src/py_bindings.rs:84-109`); the crate has no `static`/`lazy`/`OnceLock`/`Mutex`/`thread_local` (grep), rayon is used only for a read-only per-CQT-bin map (`chroma.rs:116-136`), `Cargo.toml` has no `panic = "abort"` so `catch_unwind` is effective; the Python glue is stateless (`audio_fingerprint_analyzer.py`, `rust_fingerprint.py`, `preloaded_fingerprint.py`).
- HybridProcessor chain failure consistency: output guards raise rather than return partial audio (`mode_dispatch.py:68-79,97-108`, `hybrid_stage_dispatch.py:128-138`); a failed `process()` can leave EQ/limiter smoothing advanced, but that is the same class as C2-02 and is absorbed by the 5 s pre-roll; `_stage_*` guards in `continuous_stages.py` copy before writing (`:199`).
- Sample count preservation: `process_*_mode` raise `RuntimeError` on shape mismatch (`mode_dispatch.py:71-75,100-104`, `hybrid_stage_dispatch.py:130-134`); early returns are `target_audio.copy()` of the (N,2) input (`hybrid_stage_dispatch.py:89-107`); the offline loop checks `processed_chunk.shape[1] != chunk.shape[1]` and `write_region.shape[1] != core_samples` (`mastering_chunk_loop.py:201-205`, `mastering_chunk_assembly.py:192-196`) and the final `chunks_processed != total_chunks` guard (`mastering_chunk_loop.py:258-263`).
- Optimizer singleton and profiling counters: `get_performance_optimizer` is double-checked under `_global_optimizer_lock` (`performance_optimizer.py:49-60`); `PerformanceProfiler.time_function` updates `timings`, `counters`, `total_time_ms` and trims under its RLock and `get_performance_report` reads under the same lock (`performance_profiler.py:44-51,58-72`); `apply_module_optimizations` is idempotent via `AdaptiveMode._optimized` and runs once under the import lock at `hybrid_processor.py:282`; the wrapper is profiling-only (no memoisation, #4524) and only reached through HybridMode.
- Module-level caches: `_processor_cache` in `hybrid_processor_singleton.py` is guarded by `_processor_cache_lock` with construction and eviction-close outside it (`:57-101`); `fingerprint_repository_provider._provider` is a single-assignment hook; no other module-level mutable DSP state exists under `auralis/core`, `auralis/dsp`, `auralis/analysis/fingerprint` (grep for `global`, module-level `{}`/`[]`/`OrderedDict`, `lru_cache`).
- Fingerprint memory gate: `AnalysisBudget` admits strictly by heap-head ticket under one Condition, removes and re-notifies on cancel/failure, and admits a lone oversize job so it cannot deadlock (`analysis/fingerprint/analysis_budget.py:49-102`).
- Config mutation outside `_process_lock` in the job fallback (`job_execution.py:189-194`) is safe: the processor is exclusively owned (popped from the pool, #3201) and a timed-out instance is discarded (#4727), so no `process()` can read the mode mid-flip.

### Dimension 3: Backend WebSocket & Streaming

- Multiple WebSocket clients: `AudioStreamController` is built per stream (`routers/system_streams.py` `stream_audio`/`stream_normal`/`stream_from_position`); per-ws state is keyed by a uuid `ws_id` (`audio_stream_controller.py:ws_id`); `StreamState` per connection; two clients on different tracks share only the global semaphore, process-wide registries and single-flight table.
- Chunked processor state: per stream (`chunked_processor.py` `__init__`, own `chunk_cache` dict, `_processor_lock` RLock, `_sync_cache_lock`, `_level_manager`); `process_chunk(locked=True)` serialises per instance (`chunk_streaming.py:90-92`).
- Processor pool (`processor_pool.py`): pop-on-acquire under `_lock`, construction outside it, redundant-build close, `cleanup()` always returns or discards (`job_lifecycle.py` single `finally`, shielded `cleanup_task`); no lock inversion.
- Job worker lifecycle: dispatcher watchdog `_watch_critical_worker_task` (`config/startup/workers.py:29-103`) nulls the global and schedules teardown; slot accounting symmetric (`job_worker.py` `_run_job`, `_on_job_task_done`, `start` BaseException release); `cancel_task()` has a single caller (`job_lifecycle.cancel_job`, on the loop); `stop()` uses `await_cancelled_task` and a bounded `asyncio.wait`.
- Shared disk reaper (`chunk_disk_prune.py`): counter test-and-reset under `_prune_lock`, scan under non-blocking `_prune_scan_lock`; instance attributes cannot shadow (class-addressed) - subclass counter shadowing recorded as C3-10 (latent). Reaper deletes oldest-first and a staged `.part` file is the newest mtime, so it is not reachable in practice.
- Chunk cache writes: `atomic_io._stage_and_replace` (mkstemp sibling + fsync + `os.replace`), `is_wav_complete` gate on read, `delete_chunk_files` skips staging files; `thumbnail_cache` / `routers/artwork_thumbnails._render_thumbnail` use per-writer temp + `Path.replace`, pruner skips `.tmp-*`; last-writer-wins on one key is benign (every writer renders identically, single-flight limits duplicates).
- Seek vs in-flight work: three teardown sites share `stream_cancel.detach_stream` (pops under `active_tasks_lock`) and `signal_cancel` (token set before `task.cancel()`), and cancel/await outside the lock (`playback_commands._cancel_prior_task`, `playback_control.handle_stop` awaits outside `transition_lock`, `connection.teardown_connection`); lock order transition_lock -> active_tasks_lock has no inverse; enhanced and seek streams both go through `run_enhanced_stream`; durable write guarded by `_raise_if_cancelled` before and after DSP (`chunk_render_miss.py:39,63`); stream epoch discriminates in-flight frames (`audio_stream_controller.py` `next_stream_epoch`).
- Analysis gate / processor init: `chunk_cancel_event` is registered before track resolution (`stream_enhanced_lifecycle.py:97`) and set on init timeout (`:123`) and by `signal_cancel` on every cancel path, so a *waiting* init thread leaves the gate; the residual (admitted analysis / no single-flight) is C3-05, and the abandoned-constructor lease is C3-02.
- Chunk render single-flight (`chunk_single_flight.py` + `chunk_streaming.process_chunk`): leader always `release()`s in `finally`, a follower polls its own cancel flag, re-looks-up and re-claims (never inherits failure); no wait cycle (one claim per thread, per-processor locks).
- Processor eviction vs render in flight (#5064): lease table is event-loop-only and every drop goes through `close_dropped_processor`; direct `close()` bypass recorded as C3-09 (shutdown only).
- Controller state via helpers: `stream_chunk_ops.py` / `stream_fingerprint.py` read only per-stream controller attributes; contextvars (`_stream_type_var`, `_frame_seq_var`, `_track_id_var`, `_stream_epoch_var`) are per Task; the frame-seq cell is mutated, not rebound.
- Streaming semaphores: acquired immediately before the `try` with no await in between (`stream_enhanced_lifecycle.py:82-98`, `stream_normal.py:71-105`) and released in `finally` on every exit; `asyncio.wait_for(semaphore.acquire())` cannot leak a permit on 3.12+; pause/flow entries are popped by `detach_stream` on stop/disconnect/replace (a naturally finished stream leaves them until the next play or disconnect - bounded per connection); flow wait bounded (`stream_gates.py:46-66`), pause wait unbounded by design and always cancelled by `signal_cancel`; normal pump empties the look-ahead slot before awaiting (`stream_normal_chunks.py`, `armed, lookahead_read = lookahead_read, None`) and counts only `ReadTimeout` toward `MAX_CONSECUTIVE_READ_TIMEOUTS`.
- Executor pools: all four created together by `install_executors()` from the lifespan on the running loop (`config/startup/__init__.py:166`, called inside `lifespan`) and shut down in `_teardown_database_and_pools` (`shutdown.py`); per-chunk DSP/reads use `run_in_stream_executor` (`chunk_streaming.py:145`, `stream_normal_reads.py`, `stream_normal_chunks.py`), job DSP uses `run_job_dsp` -> `run_in_job_executor`, PlaybackService engine calls use `run_in_transport_executor` (`playback_service.py:82,125,164,226`). Plain `to_thread` remains only for per-stream setup/teardown and repository work, as designed.
- Set-queue supersession: generation + lock live on the process-wide `QueueSetSequencer` (`queue_set_sequencer.py`, `LoopBoundLock`); `_if_current_generation` does check + mutation in one lock hold; every queue mutator enters `_queue_mutation()` (`queue_edit_mixin.py`, `queue_order_mixin.py`); only the state-manager mirror in `_broadcast_queue_changed_locked` bypasses it (C3-04).
- Position ticker: `current_time` / `_update_seq` are written only inside `_mutate_state` / `_advance_position` under the manager's `_lock` (grep shows no other writer); `get_state()` is a no-await shallow copy; only the start/stop race in C3-07.
- Per-stream processor lease: `acquire` pops from the cache so two live streams of one track never share an instance (`processor_lease.py:91-112`); `release_lease`/`discard_lease` identity-check `_active_processors`; chunk timeout and post-DSP failure discard (`stream_chunk_ops.py`, `chunk_stream_state.py:invalidate_pooled_processor`). Leaks on abandoned constructor / analysis-only construction / post-close re-lease are C3-01..03.
- Playback event ordering: all transport events carry `playback_event_sequencer.next_transport_seq()` drawn under `transition_lock` (`playback_service.py`, `playback_control.py`); `queue_changed` has a single sender (`queue_service_base._broadcast_queue_changed`) holding `broadcast_lock` across read/hydrate/send; broadcast happens outside `transition_lock`.
- Coordinator siblings: `chunk_*` siblings that touch `processor.processor` are the C3-01 case; `_dsp_state_advanced` is reset under `_processor_lock` in `chunk_render_miss.py` / `chunk_streaming.py`; `ProcessingEngine` is one instance with `_jobs_lock` (asyncio) around `jobs`, `_cancel_events` popped in `finally`.
- Processing engine: single shared instance, per-job `threading.Event` token, per-job leased processor from `ProcessorPool`; DSP on the job pool with the budget starting on pickup (`job_budget.py`); timed-out/cancelled processors are poisoned and discarded (`job_lifecycle.py:131-159`).
- FastAPI handlers calling sync audio code: offloaded (`to_thread` / dedicated executors); the only sync engine-queue calls on the loop are short RLock-guarded `QueueController` reads (`queue_edit_mixin.py`), not DSP.
- Lifespan workers: auto scanner / fingerprint queues / similarity via `stop_background_workers` (individually guarded); player-state ticker `shutdown()`; streamlined worker `stop()` and `ProcessingEngine.stop_worker()` await the cancelled task via `await_cancelled_task`; `_stop_components` runs under `SHUTDOWN_TOTAL_TIMEOUT_S` and `_teardown_database_and_pools()` is synchronous in a `finally` (`shutdown.py:169-206`), so DB checkpoint and pool shutdown cannot be skipped. (Note: `fingerprint_queue.stop(timeout=30)` equals the 30 s total deadline, so it can consume the whole budget and abandon later stop steps, which are all re-derivable at next start; not filed.)
- Broadcast eviction (`config/globals.py:186-270`): concurrent bounded sends, eviction removes from `active_connections` under `_lock` and always schedules `_close_evicted` (1013) in a background task; `disconnect()` is the only other removal site; `connect()` counts under `_lock` after `accept()` and refuses over `WS_MAX_CONNECTIONS`.
- WebSocket disconnect during processing: `teardown_connection` runs every step independently guarded, pops all registries, signals the cancel token, awaits the stream (so it releases semaphore/processor), then `rate_limiter.cleanup` and `manager.disconnect`; `heartbeat_task` leaks on a failing `setup_connection` are guarded (`connection.py:241-243`, `system.py` finally).

### Dimension 4: Library & Database

- SQLite thread safety — `check_same_thread=False`, `pool_size=5`, `max_overflow=5`, 8 MB cache cap, WAL + `busy_timeout`: `auralis/library/database_engine.py:48-96`. Pysqlite legacy mode means reads never hold a snapshot, so no `SQLITE_BUSY_SNAPSHOT` upgrade failures.
- `pool_pre_ping=True` is set on all three engines: `database_engine.py:61`, `migration_engine.py:50`, `fingerprint_service.py:48`.
- Lock-wait timeouts — all three engines take `SQLITE_BUSY_TIMEOUT_MS` / `SQLITE_CONNECT_TIMEOUT_S` from `auralis/library/constants.py` (`database_engine.py:49,95`, `migration_engine.py:43,61`, `fingerprint_service.py:47,56`); no fourth engine on `library.db` (`analysis/fingerprint/catalog.py` opens its own separate standalone file; the `sqlite3.connect` calls in `migration_backup.py` are one-shot backup/restore under the migration lock).
- Concurrent scans — `ScanCoordinator` slot/exclusive flag share one `_scan_slots_lock`, paths use their own lock with symlink-resolved, ancestry-aware keys (`scan_coordinator.py:45-143`, `scan_paths.py`); `claim_scan` has no `except AttributeError`, releases the slot on rejection (`scan_stages.py:26-65`) and `LibraryScanner.scan_directories` releases paths then slot in `finally` (`scanner.py:248-250`); `scan_roots`/`reservation_key` run before the slot is taken so nothing between claim and `try` can raise. `FileDiscovery` and `BatchProcessor` share the scanner's `threading.Event` (`scanner.py:96-104`). Reset takes exclusive access before stopping workers and refuses on an unstopped worker (`routers/library.py:117-164`).
- Auto-scan watcher — watchdog callbacks use `call_soon_threadsafe` then `call_later`/`create_task` on the loop (`scanner_watchdog.py:58-70`); scan progress bridge uses `call_soon_threadsafe` (`scan_events.py:84-92`); `_sync_watchdog` re-checks `_stop_event` after the offloaded join (`scanner_watchdog.py:96-98`); `stop()` cancels, uses `asyncio.wait` (does not swallow own cancellation) and `stop_scanner` re-raises (`library_auto_scanner.py:85-96,194-201`, `scanner_stop.py`).
- Detached-instance handling — every post-commit `refresh()` is followed by a forced relationship touch or an eager reload before `expunge` (`genre_repository.py:135-139,175-178`, `album_artwork.py:142-148`, `playlist_crud_mixin.py:106-110`, `_reload_detached` in `track_repository_mutation.py:34-46`, `add()` reload at `track_repository_lifecycle.py:238-248`).
- Swallowed write failures — scan paths: reads use `_session_scope()` (raise); `add` / `update_by_filepath` failure defaults are surfaced as per-file `failed` with reasons (`batch_processor.py:197-214`); only `relocate_missing_track` has the problem reported in C4-08. Playlist `remove_track`, `add_track`, `reorder_track`, `clear` raise on DB errors (`playlist_*_mixin.py`).
- Resource monitor callbacks — decisions and stats are updated under `_lock`; callbacks and log lines run after release (`resource_monitor.py:114-202`); initial semaphore size is `limits.max_semaphore` (`:63`). `ResizableSemaphore` notify/wait logic is sound (`resizable_semaphore.py`).
- Single-flight and claims — similarity graph builds: class-level non-blocking `_busy` lock, only caller is the router (`knn_graph.py:67-120,260-275`); fingerprint claims: unfingerprinted claim relies on UNIQUE(track_id) + cursor walk with `_MAX_CLAIM_RACES`, outdated claim on `UPDATE ... rowcount == 1` (`fingerprint_scheduler_repository.py:108-278`); only the backend runs `cleanup_incomplete_fingerprints` (`config/startup/components.py:38`, not `LibraryDatabase.__init__`); drained reporting: one `_on_worker_drained` per worker after both phases, state under `_drain_state_lock` (`fingerprint_queue.py:275-279`, `fingerprint_worker.py:115-141`).
- Fingerprint claim failures — both claim methods use `_session_scope()` and raise (`fingerprint_scheduler_repository.py:119,212`); `claim_with_retry` retries with backoff and caps at `CLAIM_FAILURE_LIMIT` (`fingerprint_claim.py:35-57`); `_claim` is its only caller (`fingerprint_queue.py:222-225`).
- Analysis gate — `reserve()` pushes the ticket and always removes it, re-heapifies and `notify_all()` on any exit before admission, including `AnalysisCancelled` (`analysis_budget.py:85-105`); head-only admission with the "alone is always admitted" rule (`:56-59`); `windowed_compute.py:119` reserves before decode and maps `AnalysisCancelled` to `None`; the interactive caller forwards the stream's cancel event as `should_stop` (`fingerprint_loading.py:214`, `chunk_processor_init.py:161`).
- Repository pattern — no `text()`/raw `Session` use outside `auralis/library/repositories/`, models and migrations (grep over `auralis/` and `auralis-web/backend/`).
- Library writes during playback reads — a scan's `update_by_filepath` only changes DB rows (the player reads files, not rows); `delete_tracks_by_ids` removes the three association tables, compacts playlist positions and prunes orphans in one transaction (`track_deletion.py:36-82`); `record_play` is a single atomic UPDATE (`track_repository_maintenance.py:31-59`); settings read-modify-write paths all take the class-level `_settings_lock` (`settings_repository.py:40-226`) and callers use `asyncio.to_thread` (`routers/settings.py:85,133,173,187,204`).
- Migration execution — both layers are present: module-level `_thread_lock` plus the `fcntl`/`msvcrt` file lock under one shared deadline, lock file never unlinked (`migration_lock.py:43-130`); version re-checked after taking the lock, pre-migration backup, restore on failure, engine disposed before restore (`migration_manager.py:165-241`, `migration_backup.py:141-166`); each step is one explicit `BEGIN ... COMMIT` with the version row (`migration_steps.py:175-225`). Migrations only run in `LibraryDatabase.__init__` before the engine and repositories exist.
- Album/artist/genre race handling for exact-name collisions — `INSERT ... ON CONFLICT DO NOTHING` + re-select, with partial unique indexes on `albums` (`track_repository_lifecycle.py:41-67`, `models/album.py:49-58`); `add_tracks` / `_insert_track_at_next_position` use atomic INSERT...SELECT MAX+1 with `OR IGNORE` on the composite PK (`playlist_membership_mixin.py:40-64`).

### Dimension 5: Frontend State Consistency

- Redux dispatch ordering of WS messages: `player_state`, `position_changed`, transport events, `volume_changed`, `track_changed` each use their own sequence watermark, equal-seq ticks are applied, watermarks reset on `server_instance_id` change in the same handler that applies the snapshot - `hooks/player/playerSyncWatermarks.ts:1-63`, `hooks/player/usePlayerStateSync.ts:68-178`; `queue_changed` frames are ordered because the backend serialises read+hydrate+send under `queue_set_sequencer.broadcast_lock` - `backend/services/queue_service_base.py:156-180`, and the frontend reconciles the index against the playing track - `hooks/player/queueIndexReconciliation.ts:20-44`.
- Binary PCM pairing: the Blob branch captures and clears `pendingMeta` synchronously (and is unreachable anyway: `ws.binaryType = 'arraybuffer'`, `utils/errorHandling.ts` `connect`); a stale meta is dropped on `audio_stream_error`, on reconnect (`resetStreamFrameTracking`), and seq gaps are reported - `hooks/websocket/socketFrameParser.ts:35-152`, `websocketConnectionState.ts:129-133`.
- WebSocket reconnect/StrictMode cleanup: single timer per manager, no retry after `close()`, 1008 treated as permanent, exhausted manager retired, URL change tears the old socket down, handlers re-attached on the reuse path - `utils/errorHandling.ts` `attemptReconnect`/`close`/`detachSocket`, `hooks/websocket/websocketConnectionLifecycle.ts:345-401`, `useWebSocketConnection.ts:93-174`.
- Stale closures in subscriptions: handlers are ref-held and the effect depends only on the type key + stable `subscribe`, so status flaps do not resubscribe - `hooks/websocket/useWebSocketMessages.ts:343-370`; hooks that read live Redux state use `store.getState()` (`usePlayerStateSync`, `useStreamMessageHandlers.isSupersededTrack`, `useFollowRemovedTrack`).
- Stream epoch/supersession: late chunks from a superseded stream are queued while uninitialised and dropped at drain by the epoch filter; end/error frames are gated by epoch and track; a lower-epoch start is ignored - `hooks/enhancement/audioChunkIngest.ts:71-105`, `useEnhancedStreamStart.ts:255-268`, `useStreamSubscriptions.ts:64-143`, `useStreamMessageHandlers.ts:215-231`, reducers drop mismatched `trackId` - `store/slices/playerStreamingReducers.ts:106-206`.
- Reconnect resume: queued play/stop/pause tracked, positions re-read at replay, `streamActive` latch prevents restarting finished tracks, enhancement/player state pushed by the server on connect - `hooks/websocket/websocketConnectionCore.ts:267-306`, `useOutgoingChannel.ts:201-287`, `backend/ws_handlers/connection.py:140-170`.
- Optimistic queue updates: call-time snapshot, per-field generation counters, in-flight counter, `queue_changed` reconciles - `hooks/player/queueMutationRunner.ts:123-154`, `queueMutationGuards.ts:195-257`, `useQueueEditMutations.ts`, `useQueueModeMutations.ts`.
- Rapid-action guards that are sound: seek bursts coalesced (`components/player/useKeyboardSeek.ts:26-76`, `useProgressBarDrag.ts:147-156`), flow-control resume does not depend on the next chunk (`hooks/enhancement/flowDrainWatch.ts:386-401`), `usePlayTrack` aborts the superseded queue POST (`hooks/player/usePlayTrack.ts:39-75`), stream-start watchdog cleared on unmount (`useStreamStartWatchdog.ts:444-476`).
- Library pagination: shared request-id + abort supersession, `runGuarded` clears flags in the right order, loadMore/refresh interlock via `fetchInProgressRef` - `hooks/shared/useLatestRequestGuard.ts:11-17`, `hooks/library/useLibraryPagination.ts:83-234` (the equivalent hole in `useLibraryQuery` is C5-03).
- Scan status reconnect resync with frame-epoch discard; playlist refresh on reconnect with request-id guard; enhancement status GET does not overwrite newer WS writes - `hooks/library/useScanProgress.ts:200-231`, `components/playlist/usePlaylistWebSocket.ts:39-45`, `components/playlist/usePlaylistData.ts:35-52`, `hooks/enhancement/useEnhancementStatusSync.ts:493-537`.
- Audio engine stop/dispose cancellation of an in-flight `start()` via `startAttempt`; worklet lookahead accounting - `services/audio/AudioPlaybackEngine.ts:96-142,201-228`, `services/audio/WorkletOutput.ts:159-194` (residual gaps in C5-04).
- Redux reducers: all index-taking queue reducers validate bounds, `setCurrentTime` clamps to duration, `setDuration` re-clamps - `store/slices/queueSlice.ts`, `store/slices/playerSlice.ts:82-132`.
