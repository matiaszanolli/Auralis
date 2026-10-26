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
- [ ] State transitions (play/pause/stop/seek) — are they atomic? Can a seek overlap with a gapless transition?
- [ ] Queue modifications during playback — is the queue protected while iterating?
- [ ] Position/duration invariant (`position <= duration`) — can a race violate this?
- [ ] Audio buffer access — can the playback thread and processing thread access the same buffer simultaneously?
- [ ] Callback safety — are player callbacks invoked with or without locks held?
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
- [ ] Seek vs in-flight work — a seek arriving mid-stream must cancel the look-ahead task (`auralis-web/backend/core/stream_enhanced_chunks.py`) and drain `auralis-web/backend/core/proactive_buffer.py`. Per-chunk cancellation and invalidation live in `auralis-web/backend/core/chunk_stream_state.py` (#4815). Can a cancelled task still deliver a chunk into the post-seek stream, or write a stale entry into the cache?
- [ ] Controller state via helpers — `auralis-web/backend/core/stream_chunk_ops.py` and `stream_fingerprint.py` take the controller instance and read/write its attributes. Two concurrent streams on one controller: is that state per-connection or shared?
- [ ] Streaming semaphores — `stream_enhanced.py` / `stream_normal.py` / `stream_seek.py` must release `_stream_semaphore` in `finally`; are all early exits accounted for? The per-WebSocket pause/flow events the pumps wait on live in `stream_gates.py` (#5761): is an entry removed on every disconnect path? The flow wait is bounded by `FLOW_GATE_TIMEOUT_S` (#5863, 3a1ab313) while the pause wait is deliberately unbounded: is any other pump wait on a client signal still unbounded? The normal pump's timeout-wrapped disk reads live in `stream_normal_reads.py` (#5839): a `ReadTimeout` must still count only toward `MAX_CONSECUTIVE_READ_TIMEOUTS`, and the look-ahead slot must be emptied before the await.
- [ ] Executor pools (#5086) — `auralis-web/backend/core/executors.py` reserves a stream pool (`run_in_stream_executor`, per-chunk work only), a small job pool (`run_in_job_executor`, full-track mastering DSP, #5335), and installs an I/O pool as the loop default. Can a per-chunk path still fall back to plain `to_thread` and queue behind scan/repository work, or a job DSP call land on the DB-sized default pool? Are all three pools created inside the running loop and shut down in the lifespan?
- [ ] Set-queue supersession — `services/queue_set_mixin.py` hands every `set_queue` a generation under `_set_queue_lock`; `_superseded()` and `_if_current_generation()` (#5839) are the only places a stale request is dropped, and the check and the mutation must share one lock hold. Can a slow track resolution still commit over a newer request, or does any sibling (`queue_edit_mixin.py`, `navigation_service.py`) mutate the queue without the generation check?
- [ ] Position ticker — `PositionTickerMixin` (`position_ticker.py`) advances `current_time` in `_advance_position` under the state manager's asyncio `_lock` and reads `_update_seq` inside that same hold (#4544). Does any other writer of `current_time` or `_update_seq` bypass the lock?
- [ ] Playback event ordering — `auralis-web/backend/services/playback_event_sequencer.py` orders discrete playback WebSocket events process-wide. Can any broadcaster bypass it and deliver events out of order?
- [ ] Coordinator siblings — the `chunk_*.py` and `job_*.py` siblings mutate the `ChunkedAudioProcessor` / `ProcessingEngine` instance they are handed. A lock taken in the coordinator does not cover a sibling that touches the same attribute from another thread.
- [ ] Processing engine — shared or per-request instances? Thread safety?
- [ ] FastAPI async handlers calling sync audio code — are they using `run_in_executor` / `asyncio.to_thread`? Can blocking calls starve the event loop?
- [ ] Background workers started in the lifespan — are they cancelled and awaited on shutdown?
- [ ] WebSocket disconnect during processing — is cleanup atomic? Resource leaks?

### Dimension 4: Library & Database

**Key files**: `auralis/library/database.py` (+ `database_engine.py`, `database_accessors.py`, `scan_coordinator.py`), `auralis/library/repositories/`, `auralis/library/scanner/` (incl. `scan_stages.py`), `auralis/library/migration_manager.py` (+ `migration_engine.py`, `migration_lock.py`, `migration_backup.py`, `migration_versions.py`), `auralis/library/resource_monitor.py`, `auralis-web/backend/services/library_auto_scanner.py` (+ `scanner_watchdog.py`, `auto_scan_events.py`)

**Check**:
- [ ] SQLite thread safety — `check_same_thread=False`? Connection pooling config? The engine is built in `auralis/library/database_engine.py`.
- [ ] `pool_pre_ping=True` — is it actually set?
- [ ] Lock-wait timeouts — three engines open the same `library.db` (`database_engine.py`, `migration_engine.py`, and `auralis/analysis/fingerprint/fingerprint_service.py`). All three take `SQLITE_BUSY_TIMEOUT_MS` / `SQLITE_CONNECT_TIMEOUT_S` from `auralis/library/constants.py` (8ef11738, #5799); a fourth engine, or a literal timeout, brings back the drift where the shortest wait raises "database is locked".
- [ ] Concurrent scans — can two scan operations run simultaneously and cause conflicts? Slot, per-directory reservation and destructive-operation accounting live in `ScanCoordinator` (`auralis/library/scan_coordinator.py`, one per `LibraryDatabase`, which delegates to it). `claim_scan()` in `auralis/library/scanner/scan_stages.py` takes the slot and reserves the directories. Verify acquisition and release are symmetric on every exception path. Also check that the slot check fails closed: since #5802 no `except AttributeError` wraps it.
- [ ] Auto-scan watcher — `scanner_watchdog.py` callbacks run on the watchdog observer thread, and scan progress in `auto_scan_events.py` is published from the scan's worker thread. Both reach the loop through `call_soon_threadsafe` (#4748). Does any loop-affine call (`call_later`, `create_task`, a `Task.cancel()`) now run off the loop?
- [ ] Detached-instance races — repositories `expunge()` what they return. A post-commit `refresh()` expires the instance *without* re-applying `selectinload()` options, so another thread touching a relationship then raises `DetachedInstanceError`. Are relationships touched while still attached?
- [ ] Swallowed write failures — `BaseRepository._guarded()` (`auralis/library/repositories/base.py`, #6212) rolls back, logs once and swallows, so a write that loses a lock race returns the method's failure default and reads as "not found" to the caller. Does a caller treat that default as a definitive answer (e.g. skip-and-continue in a scan batch)?
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
