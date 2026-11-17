---
description: "Audit for race conditions, missing locks, thread-safety violations, state-machine bugs, unsafe concurrent access"
argument-hint: "[--focus <dimensions>] [--depth shallow|deep] [--limit <N>]"
---

# Concurrency and State Integrity Audit

Perform a deep audit of Auralis for race conditions, missing locks, thread safety violations, state machine bugs, and unsafe concurrent access.

**Architecture**: This is an orchestrator. Each dimension runs as an Agent-tool subagent (`subagent_type: general-purpose`, `model: sonnet`). Max 3 run concurrently.

See `.claude/commands/_audit-common.md` for project layout, severity framework, methodology, context management rules, deduplication, and finding format.

## Parameters (from $ARGUMENTS)

- `--focus <dimensions>`: Comma-separated dimension numbers or names (e.g., `1,3` or `player,pipeline,backend`). Default: all 5.
- `--depth shallow|deep`: `shallow` = check key patterns only; `deep` = trace full execution paths. Default: `deep`.
- `--limit <N>`: Stop after N findings. Default: unlimited.

## Severity Examples

| Severity | Concurrency-Specific Examples |
|----------|------------------------------|
| **CRITICAL** | Concurrent writes to audio buffer, race between player state and output, database corruption from parallel access |
| **HIGH** | Seek during gapless transition, queue modification during playback, parallel DSP chunk processing errors |
| **MEDIUM** | Unprotected shared state, missing copy-before-modify, in-memory state without persistence |
| **LOW** | Coarse-grained locks, unnecessary serialization, redundant locking |

## Audit Dimensions

### Dimension 1: Player Thread Safety

**Key files**: `auralis/player/enhanced_audio_player.py` (+ its `player_*_mixin.py` siblings), `auralis/player/gapless_playback_engine.py` (+ `gapless_prebuffer.py`), `auralis/player/queue_controller.py` (+ `queue_loading.py`, `queue_locked_state.py`), `auralis/player/components/queue_manager.py` (+ `queue_navigation.py`, `queue_shuffle.py`), `auralis/player/integration_manager.py` (+ `integration_library.py`, `integration_reporting.py`), `auralis/player/realtime/`

**Check**:
- [ ] RLock usage — is every shared state access protected? Are locks properly scoped?
- [ ] Mixin lock ownership (#5836 splits) — each lock is created in the base class `__init__` and the mixin only annotates it: `QueueManager._lock` (navigation/shuffle mixins), `GaplessPlaybackEngine.update_lock` / `_thread_lock`, `IntegrationManager._position_lock` / `_stats_lock`. `QueueController`'s mixins borrow *another object's* lock (`self.queue._lock`). Do the lock orders stated in the `gapless_prebuffer.py` and `integration_reporting.py` docstrings still hold at every call site, and does every mixin method that touches base state take the base's lock?
- [ ] Linear work outside audio-thread locks (#6084, 8e46968a) — `queue_loading.py` serialises the playlist rows and `realtime/level_matcher.py` measures the reference RMS *before* taking `queue._lock` / the matcher's `_lock`, which then guard only the swap. Does any new bulk path put O(n) work back inside a lock the audio callback waits on?
- [ ] Prebuffer re-arm (#6083, 1ab16336) — `start_prebuffering()` against a live worker sets `_rearm_requested`, and `_prebuffer_worker` decides "another pass or exit" (`_prebuffer_exiting`) under `_thread_lock`. Can a queue edit landing after the worker's final re-peek still be dropped, or a worker that decided to exit be counted as running?
- [ ] Gapless swap snapshot (#6081, 141ce1a9) — `_track_position_snapshot()` in `integration_reporting.py` reads clamped position, duration and file under one `_audio_lock` hold, the lock the swap and its position reset run under. Does any other reporting path read the three in separate acquisitions (`position > duration` across a swap)?
- [ ] Auto-advance vs `cleanup()` — `advance_with_prebuffer(on_swap, abort)` polls `abort` after the blocking decode and before committing the queue advance; `next_track()` passes the cleanup flag (#6127, 70b6ef13). A `False` `next_track()` finishes playback once through `_finish_playback()` in `player_streaming_mixin.py` instead of re-spawning an advance thread per audio callback (#5706). Is there a commit point between the decode and the abort poll that `cleanup()` can still race?
- [ ] Gapless swap across a sample-rate change (#6307, b49514369) — `advance_with_prebuffer()` no longer discards a ready prebuffer whose rate differs from the current track's: the swap under `update_lock` -> `_audio_lock` installs `audio_data`, `sample_rate` and `current_file` together, as the fallback decode does (pinned by `tests/auralis/player/test_prebuffer_used_across_sample_rate_change_6307.py`). Does any reader still pair a position or duration with a rate read in a separate acquisition?
- [ ] State transitions (play/pause/stop/seek) — are they atomic? Can a seek overlap with a gapless transition?
- [ ] Audio-callback read vs `stop()` (#6308, d2f2adf9a) — `get_audio_chunk()` in `player_streaming_mixin.py` tests PLAYING and advances the position in one `PlaybackController._lock` hold (`read_and_advance_if_playing()`); a separate `is_playing()` then advance let a `stop()` reset be overwritten and emit one extra chunk. Does any other reader of `playback.position` gate on `state` in a separate acquisition?
- [ ] Pause flag across a skip (#6309, 4f2d21942) — `pause()` sets `_pause_requested` before the transition and keeps it when the transition fails (mid-skip the state is briefly STOPPED); only `play()` clears it, and `next_track()` / `previous_track()` re-pause after their resume if it is set (`tests/auralis/player/test_pause_flag_ordering_5588.py`, `test_previous_track_resume.py`). Is there a resume path other than `play()` that reaches PLAYING without clearing it, leaving a stale flag to re-pause a later skip?
- [ ] Completion accounting (#6313, bb149b546) — `next_track(completed=True)` is passed only by the auto-advance in `player_streaming_mixin.py`, and only it calls `record_track_completion()` under `_stats_lock`; `total_play_time` is gone. Does a new caller of `next_track()` set `completed` or skip it wrongly?
- [ ] Queue modifications during playback — is the queue protected while iterating?
- [ ] Position/duration invariant (`position <= duration`) — can a race violate this? `seek()` rejects NaN (returns `False`, #6312, 82a896a1d); inf and huge values are clamped (#6130). `QueueManager.get_queue_info()` computes `has_next` / `has_previous` under `_lock` and counts repeat as wrapping both ways (#6311, 617cae4e4) — does any other navigation predicate disagree with it?
- [ ] Audio buffer access — can the playback thread and processing thread access the same buffer simultaneously?
- [ ] Callback safety — registration and deferred dispatch live in `PlaybackNotifierMixin` (`auralis/player/playback_notifier.py`, split out of `playback_controller.py` in c25418c5f, #6273). Mutators snapshot state under `PlaybackController._lock` and notify after releasing it; a caller that holds `_audio_lock` must open `playback.defer_notifications()` *outside* it. A notification fired inside the `on_loaded` / `on_swap` hooks without that scope raises `LockHeldNotificationError` (`auralis/player/lock_held_hooks.py`, #6085, a6e6ce589; `tests/auralis/player/test_lock_held_hook_guard_6085.py`) instead of the AB-BA deadlock with `IntegrationManager._on_playback_state_change`. Is there a third lock-held hook that skips `lock_held_hook()`? Every event carries a transition-ordered `seq` assigned under `_lock` by `_event()` (#6129, 619a435eb): does a listener that mirrors state drop an older `seq`?
- [ ] Can `stop()` race with `play()` leaving the player in an undefined state?

### Dimension 2: Audio Processing Pipeline

**Key files**: `auralis/core/hybrid_processor.py`, `auralis/core/simple_mastering.py`, `auralis/core/mastering_chunk_loop.py`, `auralis/core/mastering_process_chunk.py`, `vendor/auralis-dsp/`

The engine-side parallel processor (*auralis/optimization/parallel_processor.py* + *parallel/*) was deleted as unreachable in #4565 — audit the engine's sequential chunk loop here, and the backend's concurrent chunk processor in Dimension 3. Do not report the deleted module.

**Check**:
- [ ] Chunk loop — are audio chunks independently copied before processing? Can adjacent chunks interfere through carried context (notch state, level smoothing, limiter memory)?
- [ ] Shared mastering targets — targets derived once per track and read by concurrent chunk workers must be immutable. Is any target dict/array mutated in place by a worker?
- [ ] Copy-before-modify pattern — is `audio.copy()` consistently used before in-place NumPy operations?
- [ ] Rust DSP boundary — does PyO3 correctly handle GIL release during processing? Can concurrent calls corrupt shared state?
- [ ] HybridProcessor chain — if one stage fails mid-array, is the pipeline state consistent?
- [ ] Sample count preservation — can the chunked and whole-file paths produce different lengths?
- [ ] Optimizer singleton — `auralis/optimization/performance_optimizer.py` wraps `AdaptiveMode.process` process-wide (#5142). Are its profiling counters (`auralis/optimization/profiling/`) safe when several backend chunk workers master concurrently?

### Dimension 3: Backend WebSocket & Streaming

**Key files**: `auralis-web/backend/core/audio_stream_controller.py`, `auralis-web/backend/core/chunked_processor.py`, `auralis-web/backend/core/processing_engine.py` (+ `job_lifecycle.py` / `job_execution.py`), `auralis-web/backend/core/executors.py`, `auralis-web/backend/core/processor_pool.py`, `auralis-web/backend/core/processor_factory.py` (+ `processor_maintenance.py`, `processor_registry.py`), `auralis-web/backend/core/job_worker.py`, `auralis-web/backend/core/state_manager.py`, `auralis-web/backend/core/proactive_buffer.py`, `auralis-web/backend/core/chunk_cache_manager.py` (+ `chunk_disk_prune.py`), `auralis-web/backend/core/chunk_stream_state.py`, `auralis-web/backend/core/streamlined_worker.py` (+ `streamlined_lifecycle.py`), `auralis-web/backend/core/stream_gates.py`, `auralis-web/backend/core/position_ticker.py`, `auralis-web/backend/core/stream_normal_chunks.py` (+ `stream_normal_reads.py`), `auralis-web/backend/core/cache_cleanup.py`, `auralis-web/backend/services/queue_set_mixin.py`, `auralis-web/backend/ws_handlers/`, `auralis-web/backend/services/playback_event_sequencer.py`, `auralis-web/backend/config/background_workers.py`

**Check**:
- [ ] Multiple WebSocket clients — can two clients request different tracks simultaneously?
- [ ] Chunked processor state — is it per-request or shared? Can concurrent requests corrupt chunk state?
- [ ] Processor pool — is checkout/return in `auralis-web/backend/core/processor_pool.py` leak-free on every early-exit and exception path?
- [ ] Job worker lifecycle — can `auralis-web/backend/core/job_worker.py` die silently and leave the queue stalled? Is there a watchdog? `JobWorker.cancel_task()` is loop-affine (#4575) and its one caller is `job_lifecycle.cancel_job()` (2ead2c38, #5417): does any thread-side path reach it without `call_soon_threadsafe`?
- [ ] Shared disk reaper — `chunk_disk_prune.py` keeps its throttle counter and two locks (`_prune_lock`, `_prune_scan_lock`, #4838) at *class* level so every `ChunkCacheManager` instance coordinates on one directory. Can a subclass or instance attribute shadow them and split the throttle?
- [ ] Chunk cache — concurrent writers to the same cache key: torn/partial files, or last-writer-wins? Are writes atomic (temp + rename via `auralis-web/backend/core/encoding/atomic_io.py`), and does the same reasoning hold for `auralis-web/backend/core/thumbnail_cache.py` and `auralis-web/backend/cache/manager.py`?
- [ ] Seek vs in-flight work — a seek arriving mid-stream must cancel the look-ahead task (`auralis-web/backend/core/stream_enhanced_chunks.py`) and drain `auralis-web/backend/core/proactive_buffer.py`. Per-chunk cancellation and invalidation live in `auralis-web/backend/core/chunk_stream_state.py` (#4815). The three teardown sites (`_cancel_prior_task` in `playback_commands.py`, `handle_stop` in `playback_control.py`, `teardown_connection` in `connection.py`) share `auralis-web/backend/ws_handlers/stream_cancel.py` (`detach_stream` pops under the caller's lock, `signal_cancel` sets the chunk token before `task.cancel()`; #6292, 5d27e0991) and must still cancel and await *outside* `active_tasks_lock`. The enhanced and seek streams share one skeleton in `stream_enhanced_lifecycle.py` (#6214, 8696368b8): a lifecycle fix applies once there, so check both entry points still reach it on every exit. Can a cancelled task still deliver a chunk into the post-seek stream, or write a stale entry into the cache?
- [ ] Processor init and the analysis gate (#6336, 12ea90cc0) — `init_fingerprint_and_processor()` (`chunk_processor_init.py`) now runs a missing tier-3 whole-track analysis in the `asyncio.to_thread` constructor, queued interactively on `analysis_budget`, so `stream_enhanced.py` / `stream_seek.py` wait `PROCESSOR_INIT_TIMEOUT` (90 s) instead of `CHUNK_PROCESS_TIMEOUT`. The stream's `chunk_cancel_event` is the gate's `should_stop`; it is set on an init timeout, and by `ws_handlers/connection.py` / `playback_control.py` on disconnect, pause and seek. Is there an exit (a `CancelledError` between `to_thread` and the registration, a superseded stream) after which an init thread stays queued on the gate for nobody?
- [ ] Chunk render single-flight (#5258, e0e91f792) — `chunk_single_flight.py` (process-wide, keyed on `ChunkPathCache.cache_key()`) lets one stream render a missing chunk while followers wait and re-read the file; `chunk_render_miss.py` drives it from `chunk_streaming.py`. Can a leader that is cancelled or raises leave a follower waiting forever (a follower polls its own cancel flag), or can a follower inherit the leader's failure instead of claiming the key (`tests/backend/test_chunk_single_flight_5258.py`)?
- [ ] Processor eviction vs a render in flight (#5064, b0002733b) — `streamlined_processor_cache.leased()` marks a processor in use; `close_dropped_processor()` defers `close()` (which removes the temp WAV) until the last lease ends. The lease table is event-loop-only with no lock: does any eviction, prune or discard path call `close()` directly, or run off the loop (`tests/backend/test_processor_eviction_in_use_5064.py`)? This is the streamlined worker's cache, a different object from the per-stream lease below.
- [ ] Controller state via helpers — `auralis-web/backend/core/stream_chunk_ops.py` and `stream_fingerprint.py` take the controller instance and read/write its attributes. Two concurrent streams on one controller: is that state per-connection or shared?
- [ ] Streaming semaphores — `stream_enhanced.py` / `stream_normal.py` / `stream_seek.py` must release `_stream_semaphore` in `finally`; are all early exits accounted for? The per-WebSocket pause/flow events the pumps wait on live in `stream_gates.py` (#5761): is an entry removed on every disconnect path? The flow wait is bounded by `FLOW_GATE_TIMEOUT_S` (#5863, 3a1ab313) while the pause wait is deliberately unbounded: is any other pump wait on a client signal still unbounded? The normal pump's timeout-wrapped disk reads live in `stream_normal_reads.py` (#5839): a `ReadTimeout` must still count only toward `MAX_CONSECUTIVE_READ_TIMEOUTS`, and the look-ahead slot must be emptied before the await.
- [ ] Executor pools (#5086) — `auralis-web/backend/core/executors.py` reserves a stream pool (`run_in_stream_executor`, per-chunk work only), a transport pool, a small job pool (`run_in_job_executor`, full-track mastering DSP, #5335; `job_budget.py` starts a job's DSP timeout when a pool thread picks the call up, not at submission, #5978, 9d6aa12e4), and installs an I/O pool as the loop default. Can a per-chunk path still fall back to plain `to_thread` and queue behind scan/repository work, or a job DSP call land on the DB-sized default pool? Are all four pools created inside the running loop and shut down in the lifespan? The fourth is the small transport pool (`run_in_transport_executor`, #6093, a4f89959): the engine's play/pause/stop/seek calls run on it while `PlaybackService` holds the transition lock, so the lock's hold time cannot depend on the I/O pool. Does any transport call still use plain `to_thread`, and does any other caller reach for the transport pool?
- [ ] Set-queue supersession — `services/queue_set_mixin.py` hands every `set_queue` a generation under `_set_queue_lock`; `_superseded()` and `_if_current_generation()` (#5839) are the only places a stale request is dropped, and the check and the mutation must share one lock hold. Can a slow track resolution still commit over a newer request, or does any sibling (`queue_edit_mixin.py`, `navigation_service.py`) mutate the queue without the generation check?
- [ ] Position ticker — `PositionTickerMixin` (`position_ticker.py`) advances `current_time` in `_advance_position` under the state manager's asyncio `_lock` and reads `_update_seq` inside that same hold (#4544). Does any other writer of `current_time` or `_update_seq` bypass the lock?
- [ ] Set-queue state is process-wide — FastAPI builds a fresh `QueueService` per request, so the lock and generation counters live on the module-level `QueueSetSequencer` (`auralis-web/backend/services/queue_set_sequencer.py`, built on `LoopBoundLock` from `loop_bound_lock.py`), not on the service (#5944). Does any new lock or counter that two overlapping requests must contend on sit on a per-request object instead?
- [ ] Per-stream processor lease — `auralis-web/backend/core/processor_lease.py` pops the cached `HybridProcessor` out of the cache for the life of one stream (`acquire` / `release_lease` / `discard_lease`, #6091; chunk-side use in `chunk_processor_lease.py`, pinned by `tests/backend/test_stream_processor_lease_6091.py`). Is every exit path a release or a discard, and can two live streams of one track ever share an instance?
- [ ] Awaiting a cancelled task — `auralis-web/backend/core/task_cancellation.py` (`caller_is_being_cancelled`) tells "the worker finished its cancellation" from "I am being cancelled too" (#6092). Does any `task.cancel(); await task` still swallow `CancelledError` unconditionally and run on past its own cancellation?
- [ ] Playback event ordering — `auralis-web/backend/services/playback_event_sequencer.py` orders discrete playback WebSocket events process-wide. Can any broadcaster bypass it and deliver events out of order? `queue_changed` frames hold `queue_set_sequencer.broadcast_lock` across read, hydrate and send (`_broadcast_queue_changed` in `queue_service_base.py`) so a slow earlier hydration cannot overtake a later edit (#5935, d2c1cdc75; `tests/regression/test_queue_changed_frames_in_edit_order_5935.py`); the edit itself stays outside the lock (#4825). Does a new sender of `queue_changed` skip it?
- [ ] Coordinator siblings — the `chunk_*.py` and `job_*.py` siblings mutate the `ChunkedAudioProcessor` / `ProcessingEngine` instance they are handed. A lock taken in the coordinator does not cover a sibling that touches the same attribute from another thread.
- [ ] Processing engine — shared or per-request instances? Thread safety?
- [ ] FastAPI async handlers calling sync audio code — are they using `run_in_executor` / `asyncio.to_thread`? Can blocking calls starve the event loop?
- [ ] Background workers started in the lifespan — are they cancelled and awaited on shutdown? The stop steps share one deadline, `SHUTDOWN_TOTAL_TIMEOUT_S` (`config/startup/shutdown.py`, #5992, b0578d862); the database checkpoint and thread-pool teardown run in `_teardown_database_and_pools()` in a `finally`, so a hung step or a cancelled lifespan cannot skip them. Does a new stop step have its own bound, and does anything that must run last sit inside the deadline-bounded part?
- [ ] Broadcast eviction — `ConnectionManager.broadcast()` (`auralis-web/backend/config/globals.py`) drops a client whose send times out or errors and closes it with 1013 in a background task bounded by `BROADCAST_SEND_TIMEOUT`, so the frontend reconnects and resyncs instead of staying connected but blind (#5884, 675e9d49). `disconnect()` is the only other `active_connections.remove` site. Can a path evict without closing, or can the close wait on a caller holding `_playback_lock`? `connect()` also caps the set at `WS_MAX_CONNECTIONS` (16, `config/limits.py`, #6171 part, f75423015), counted under `_lock` after `accept()` so two handshakes cannot both register, and refuses the next with 1013 (`tests/backend/test_ws_connection_cap_6171.py`; #6171 is still open for its remaining limits).
- [ ] WebSocket disconnect during processing — is cleanup atomic? Resource leaks?

### Dimension 4: Library & Database

**Key files**: `auralis/library/database.py` (+ `database_engine.py`, `database_accessors.py`, `scan_coordinator.py`), `auralis/library/repositories/`, `auralis/library/scanner/` (incl. `scan_stages.py`), `auralis/library/migration_manager.py` (+ `migration_engine.py`, `migration_lock.py`, `migration_backup.py`, `migration_versions.py`), `auralis/library/resource_monitor.py`, `auralis/library/scan_paths.py`, `auralis-web/backend/services/library_auto_scanner.py` (+ `scanner_watchdog.py`, `scan_events.py`)

**Check**:
- [ ] SQLite thread safety — `check_same_thread=False`? Connection pooling config? The engine is built in `auralis/library/database_engine.py`.
- [ ] `pool_pre_ping=True` — is it actually set?
- [ ] Lock-wait timeouts — three engines open the same `library.db` (`database_engine.py`, `migration_engine.py`, and `auralis/analysis/fingerprint/fingerprint_service.py`). All three take `SQLITE_BUSY_TIMEOUT_MS` / `SQLITE_CONNECT_TIMEOUT_S` from `auralis/library/constants.py` (8ef11738, #5799); a fourth engine, or a literal timeout, brings back the drift where the shortest wait raises "database is locked".
- [ ] Concurrent scans — can two scan operations run simultaneously and cause conflicts? Slot, per-directory reservation and destructive-operation accounting live in `ScanCoordinator` (`auralis/library/scan_coordinator.py`, one per `LibraryDatabase`, which delegates to it). `claim_scan()` in `auralis/library/scanner/scan_stages.py` takes the slot and reserves the directories. Verify acquisition and release are symmetric on every exception path. Also check that the slot check fails closed: since #5802 no `except AttributeError` wraps it. Reservation keys resolve symlinks and a nested directory is rejected as overlapping (#6097, a98b973d, `auralis/library/scan_paths.py`); `FileDiscovery` and `BatchProcessor` observe stop through the scanner's `threading.Event` (#6100); a library reset is refused while a fingerprint worker has not stopped (#6095).
- [ ] Auto-scan watcher — `scanner_watchdog.py` callbacks run on the watchdog observer thread, and scan progress in `scan_events.py` is published from the scan's worker thread. Both reach the loop through `call_soon_threadsafe` (#4748). Does any loop-affine call (`call_later`, `create_task`, a `Task.cancel()`) now run off the loop?
- [ ] Detached-instance races — repositories `expunge()` what they return. A post-commit `refresh()` expires the instance *without* re-applying `selectinload()` options, so another thread touching a relationship then raises `DetachedInstanceError`. Are relationships touched while still attached?
- [ ] Swallowed write failures — `BaseRepository._guarded()` (`auralis/library/repositories/base.py`, #6212) rolls back, logs once and swallows, so a write that loses a lock race returns the method's failure default and reads as "not found" to the caller. Does a caller treat that default as a definitive answer (e.g. skip-and-continue in a scan batch)? Playlist DELETE, remove-track and create answer 500 on the sentinel and re-check before reporting a lost race as success (#5940, 01f6a77a), and update / add_track / reorder / clear do the same (#5264, 3bba1c39e; `tests/backend/test_playlist_db_error_not_a_404_5264.py`). Does a new playlist write path read the failure default as 'not found'?
- [ ] Resource monitor callbacks — `AdaptiveResourceMonitor._check_and_adjust_resources` (`resource_monitor.py`) decides and updates its stats under its own `_lock`, then calls `on_worker_count_change` / `on_semaphore_change` after releasing it (#5756, 2524d112); the consumers take their own locks (queue `stats_lock`, the semaphore). Does a callback or log line creep back inside the `with self._lock`? It starts from the semaphore size the queue built (#6140).
- [ ] Single-flight and claims — similarity-graph builds are single-flight (#5945), a fingerprint worker that loses a claim race tries the next track (#6080), and only the backend sweeps fingerprint claims, not every `LibraryDatabase()` (#6099). A fingerprint worker reports to `on_drained` once per wave, after BOTH phases (#6324, c4d3faf31; `tests/auralis/services/test_drain_reports_once_per_worker_6324.py`). Can two builders or two sweepers still overlap, or a worker report a wave twice?
- [ ] Fingerprint claim failures (#6334, bd3a1e157) — `claim_next_unfingerprinted_track()` and `claim_next_outdated_fingerprint()` (`fingerprint_scheduler_repository.py`) use `_session_scope()`, not `_guarded()`, so a database error *raises* and `None` means only "queue empty". Both loop up to `_MAX_CLAIM_RACES` on a lost race and advance the cursor each time. `claim_with_retry()` (`auralis/services/fingerprint_claim.py`) retries with backoff and gives up after `CLAIM_FAILURE_LIMIT` consecutive failures; the queue's `_claim()` is its only caller (`tests/auralis/library/test_outdated_claim_race_6334.py`, `tests/auralis/services/test_fingerprint_claim_retry_6334.py`). Does any other claim or sweep path swallow the error back into `None` and quit a worker's phase?
- [ ] Analysis gate (#6336 / #6338, 12ea90cc0) — `analysis_budget` (`auralis/analysis/fingerprint/analysis_budget.py`) is the process-wide, minutes-weighted `threading.Condition` gate in front of every fingerprint analysis: strict ticket order (interactive ahead of background, FIFO within a class), a job admitted alone when nothing runs, and `should_stop` polled every `STOP_POLL_S`. `compute_windowed_fingerprint()` reserves before decoding. Does an exit path between `heappush` and admission leave a ticket in `_waiting` or skip the `notify_all()` that wakes the next head, and does the interactive caller (`fingerprint_loading.py`) pass a `should_stop` that fires on stream cancel (`tests/auralis/analysis/fingerprint/test_analysis_gate_6336_6338.py`)?
- [ ] Repository pattern — any raw SQL bypassing the ORM?
- [ ] Library writes during playback reads — can a scan update a track that's currently playing?
- [ ] Migration execution — safe to run while the app is serving requests? Migrations use inter-process file locking (`fcntl`/`msvcrt`) plus a same-process `threading.Lock`, both in `auralis/library/migration_lock.py`; the file lock alone does NOT serialize threads in one process — verify both are still present.

### Dimension 5: Frontend State Consistency

**Key files**: `auralis-web/frontend/src/store/`, `auralis-web/frontend/src/hooks/`, `auralis-web/frontend/src/services/`

**Check**:
- [ ] Redux dispatch ordering — can WebSocket messages arrive and dispatch out of order?
- [ ] Stale closure bugs in hooks — do effect cleanup functions race with new connections?
- [ ] Optimistic updates — are they reconciled correctly when the backend responds?
- [ ] WebSocket reconnection — does the frontend correctly re-sync state after reconnect?
- [ ] Multiple rapid user actions (skip, skip, skip) — does the frontend handle rapid state changes?

## Phase 1: Setup

1. Parse `$ARGUMENTS` for `--focus`, `--depth`, `--limit`
2. `mkdir -p /tmp/audit/auralis/concurrency`
3. Fetch dedup baseline: the canonical dump from `_audit-common.md` Deduplication step 1 (`--limit 100000` + truncation assertion), redirected to `/tmp/audit/auralis/concurrency/issues.json`
4. Scan `docs/audits/` for prior concurrency audit reports

## Phase 2: Launch Dimension Agents

Launch one Agent-tool subagent per dimension (max 3 concurrent). Each agent writes its output to `/tmp/audit/auralis/concurrency/dim_<N>.md`.

Every agent prompt MUST include:
- The project root is `/mnt/data/src/matchering`
- The depth parameter value
- The limit parameter value (if set)
- Reference to dedup file: `/tmp/audit/auralis/concurrency/issues.json`
- The context management rules from `_audit-common.md`
- The per-finding format below

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Player Thread Safety | Audio Processing | Backend Streaming | Library & Database | Frontend State
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Trigger Conditions**: Exact timing/concurrency scenario needed
- **Evidence**: Code snippet showing the unsafe pattern
- **Impact**: What state gets corrupted, what audio artifacts occur
- **Suggested Fix**: Lock type, copy pattern, or state machine change needed
```

Dimension → Output mapping:
- Dimension 1 (Player Thread Safety) → `/tmp/audit/auralis/concurrency/dim_1.md`
- Dimension 2 (Audio Processing) → `/tmp/audit/auralis/concurrency/dim_2.md`
- Dimension 3 (Backend Streaming) → `/tmp/audit/auralis/concurrency/dim_3.md`
- Dimension 4 (Library & Database) → `/tmp/audit/auralis/concurrency/dim_4.md`
- Dimension 5 (Frontend State) → `/tmp/audit/auralis/concurrency/dim_5.md`

## Phase 3: Merge

1. Read all `/tmp/audit/auralis/concurrency/dim_*.md` files
2. Combine into `docs/audits/AUDIT_CONCURRENCY_<TODAY>.md` with structure:
   - **Executive Summary** — Total findings by severity, key themes, most impactful races
   - **Concurrency Matrix** — Components, lock types, thread-safety status
   - **Findings** — Grouped by severity (CRITICAL first), deduplicated across dimensions
   - **Relationships** — Shared root causes, compound race conditions
   - **Prioritized Fix Order** — What to fix first and why
3. Remove cross-dimension duplicates (same file:line found by multiple dimensions)

## Phase 4: Cleanup

1. `rm -rf /tmp/audit/auralis/concurrency`
2. Inform user the report is ready
3. Suggest: `/audit-publish docs/audits/AUDIT_CONCURRENCY_<TODAY>.md`

## Labels

Use labels when publishing: severity label + `concurrency` + `bug`
