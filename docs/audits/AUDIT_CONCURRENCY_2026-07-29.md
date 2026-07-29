# Concurrency & State Integrity Audit — 2026-07-29

**Repo**: `/mnt/data/src/matchering` @ `master` (HEAD `9e03236c`)
**Scope**: 5 dimensions — Player Thread Safety, Audio Processing Pipeline, Backend WebSocket & Streaming, Library & Database, Frontend State Consistency
**Depth**: deep · **Method**: static analysis + two executable repros · **Source access**: read-only
**Dedup baseline**: 241 GitHub issues (`gh issue list --limit 300`), `docs/audits/AUDIT_CONCURRENCY_2026-07-25.md`, plus this session's `docs/audits/AUDIT_BACKEND_2026-07-29.md`, `docs/audits/AUDIT_ENGINE_2026-07-29.md`, `docs/audits/AUDIT_FRONTEND_2026-07-29.md`

Every finding below is tagged **PROVED** or **HYPOTHESIS**. *PROVED* means a running repro, or an interleaving argument pinned to concrete line numbers in code that was read fresh this session. Nothing is presented as a confirmed race on the strength of plausibility alone.

---

## Executive Summary

| Severity | New findings |
|---|---|
| CRITICAL | 1 |
| HIGH | 4 |
| MEDIUM | 5 |
| LOW | 1 |
| **Total** | **11** |

Plus: **1 escalation** of an already-open issue (#3735) with a newly-identified mechanism, **1 cross-audit confirmation** (BE4-6), and **6 prior-audit findings verified genuinely FIXED**.

### Key themes

1. **One shared thread pool is the whole backend's single point of failure.** `loop.set_default_executor` is never called anywhere in the repo, so all **173** `asyncio.to_thread` / `run_in_executor` call sites in `auralis-web/backend/` — including *every REST database read* — contend for one `min(32, cpu_count + 4)`-slot pool. Five `wait_for(to_thread(...))` sites leak slots from it permanently, and one of them sits on the ordinary playback hot loop. This is **BST-9**, and it converts what the backend audit filed as a per-job defect (BE7-1) into a whole-process failure mode.

2. **`asyncio.wait_for` was used as if it could cancel a thread.** It cannot. Four separate subsystems — offline mastering jobs, enhanced streaming, seek, and the background cache worker — rely on a `wait_for` timeout to bound work that is running inside `asyncio.to_thread`. The coroutine unwinds; the thread does not. Every one of those timeouts is a permanent resource leak, and in `stream_chunk_ops.py` the recovery branch then re-submits into a lock the abandoned thread still holds.

3. **"There is a reset method" and "the reset is actually called" are different claims.** `processing_engine._execute_job` resets three components between pooled jobs; the brick-wall limiter is the fourth stateful component on the same processor and is never reset. `BrickWallLimiter.reset()` has **zero production call sites**. Reproduced: 12.3 dB of the previous track's gain reduction survives into the next track's opening (**AP-6**). Same defect class as #2400, which fixed two of the four.

4. **Locks are correct; what happens *around* them is not.** The audit found essentially no torn state. `HybridProcessor._process_lock` genuinely serialises every mutating path (traced attribute by attribute). The player subsystem is the most hardened code in the tree. The failures are all *blocking-in-the-wrong-place*: a `threading.RLock.acquire()` executed on the asyncio event loop (**AP-5**), a full-file audio decode performed while an `RLock` is held by an outer frame (**#3735 escalation**), a `Thread.join(timeout=5)` on the loop (BE4-6), locks held across WebSocket broadcasts (**BST-12**).

5. **Structural fixes stopped one caller short.** `reset_library` pauses three registered workers but not the ad-hoc scanner an in-flight `POST /api/library/scan` creates (**LDB-3**). The seq-ordering guard covers two WS message types and not the other six (#4582). The rapid-click guard in the transport hooks is wired to a Redux field nothing ever sets (**FST-3**).

### Most impactful races

- **BST-9** — total backend functional deadlock, no self-recovery, reachable from ordinary playback of one slow-decoding file.
- **AP-5** — the same timeout freezes the entire event loop on the *next* job, because three locked setters are called synchronously from an `async def`.
- **AP-6** — deterministic, silent, audible: baked into the rendered output file, not just playback.

---

## Concurrency Matrix

| Component | Primary guard | Thread-safety status |
|---|---|---|
| `AudioPlayer` / `AudioFileManager` | `_audio_lock` (RLock) | Correct, but held across blocking decode on the `next_track()` fallback path (#3735 escalation) |
| `PlaybackController` / `IntegrationManager` | `_lock`, `_position_lock` + `defer_notifications` | **Correct.** AB-BA closed; prior PTS-1/2/3 all fixed |
| `QueueManager` (engine) | `_lock` (RLock) | **Correct** — composite atomic ops (`advance_if_next_matches`, snapshot/rollback) |
| `GaplessPlaybackEngine` | `update_lock`, `_thread_lock` | Correct; #3782 nesting still latent, #4631 unlocked read still open |
| `HybridProcessor` | `_process_lock` (RLock) | **State-safe** (verified attribute-by-attribute); the lock is blocked *on the event loop* (AP-5); limiter state not reset between pooled jobs (AP-6) |
| 13 named DSP stages | none needed | **Correct** — zero in-place writes on caller arrays; sample-count assertions present |
| Rust PyO3 (`vendor/auralis-dsp/`) | `py.allow_threads` ×12 | **Correct** — GIL released, inputs copied before the boundary, no `static`/`unsafe` in the crate |
| Parallel band / FFT / feature processors | `with` -scoped executors | **Correct** — `audio.copy()` on every worker path; prior AP-3 fixed |
| Default asyncio executor | **none — unbounded, unowned** | **CRITICAL (BST-9)** — 173 consumers, 5 permanent leak sites, no watchdog |
| `ProcessorPool` / `ProcessorFactory` | asyncio lock / RLock | Pop-on-acquire is correct; hold-across-construction tracked as #4689 / #4675 |
| `ChunkedAudioProcessor` | `_processor_lock` (RLock), `_sync_cache_lock` | Serialises correctly, but a timed-out worker never releases it |
| Chunk WAV cache | `atomic_write_bytes` + `is_wav_complete` | **FIXED** since 2026-07-25 (prior BST-1) |
| `ChunkCacheManager` prune | class-level `_prune_lock` | Correct but coarse (BST-13) |
| `JobWorker` | `_jobs_lock`, `_concurrency_semaphore` | `stop()` now drains (prior BST-3 fixed); shutdown gate defeated by the watchdog (BST-11) |
| Streaming semaphores | `_stream_semaphore` | **Correct on all 8 sites** — independently re-verified; balance is incidental, see note |
| `PlayerStateManager` | `_lock` (asyncio) | **Correct** — mutates under lock, broadcasts outside |
| `QueueService` | `_set_queue_lock` | Held across two broadcasts + four `to_thread` round-trips (BST-12) |
| `LibraryDatabase` | WAL + `busy_timeout=60000` + `_scan_slots_lock` | **Correct** — pragmas, scan-slot semaphore, migration `threading.Lock` all survived #4619 intact |
| `migration_lock` | `flock`/`msvcrt` + `_thread_lock` | **FIXED and improved** — prior LDB-1 closed; both entry points now covered |
| `ResizableSemaphore` / fingerprint queue | `Condition` | **Correct** — grow notifies, shrink is lazy, release floors at 0 |
| `reset_library` vs ad-hoc scan | `BACKGROUND_WORKER_KEYS` (3 keys) | **HIGH (LDB-3)** — manual scan is not in the registry |
| Redux queue optimistic updates | `stateRef` snapshot | Full-array rollback can clobber a newer mutation (FST-4) |
| WS message ordering | `lastSeenSeqRef` | Guards 2 of 8 message types — tracked as #4582 |
| Transport rapid-click guard | `isLoading` / `executingCommand` | **Inert** — neither is read on the gating path (FST-3) |
| PCM audio path (frontend) | single-threaded by construction | **Correct** — worklet receives cloned arrays; no `MediaSource`/`SourceBuffer` in production |

---

## CRITICAL

### BST-9: The shared default asyncio executor is the entire backend's single choke point, and five `wait_for(to_thread(...))` sites leak its threads permanently

- **Severity**: CRITICAL
- **Confidence**: **PROVED** (mechanism); the *frequency* of the >30 s trigger is HYPOTHESIS — see "Honest limits" below
- **Dimension**: Backend Streaming
- **Location**:
  - Leak sites: `auralis-web/backend/core/processing_engine.py:404-419`, `auralis-web/backend/core/stream_enhanced.py:126-140`, `auralis-web/backend/core/stream_seek.py:130-144`, `auralis-web/backend/core/stream_chunk_ops.py:110-122`, `auralis-web/backend/core/streamlined_worker.py:481-490`
  - Consumers: 173 `asyncio.to_thread(` / `run_in_executor(` call sites across `auralis-web/backend/`
- **Status**: NEW — escalation of **BE7-1** (`docs/audits/AUDIT_BACKEND_2026-07-29.md:525`), which covers only the processor-reuse half, only the 300 s job path, and does not map the blast radius
- **Trigger Conditions**: any single `wait_for` timeout, or any DSP call that never returns

**1. Executor sizing.** `grep -rn "set_default_executor" --include="*.py" .` returns **0** hits repo-wide (independently re-verified by the orchestrator). Every `asyncio.to_thread()` therefore resolves through CPython's default path, which constructs `ThreadPoolExecutor(thread_name_prefix='asyncio')` with no `max_workers`, falling back to `min(32, (os.cpu_count() or 1) + 4)`. There is exactly one such executor per event loop, and the backend runs one loop. Concrete capacities: 4-core desktop = 8 threads; 8-core = 12; 16-core = 20.

The only other explicit `ThreadPoolExecutor` in the tree is a separate 5-thread pool in `auralis/analysis/fingerprint_generator.py`; it does not relieve the default pool. This is also *not* the Starlette/anyio threadpool (40 slots, serves sync `def` route handlers) — all 173 sites bypass that entirely.

**2. Consumer census.** Independently re-verified: **173** in `auralis-web/backend/`, **0** in `auralis/`. Seventeen router files use it, i.e. **every REST database read goes through this pool** — along with enhanced/normal/seek streaming, prefetch, the proactive buffer, the background cache worker, offline mastering jobs, transport (play/pause/stop/seek), queue mutation, queue enrichment, WS playback commands, and the auto-scanner. The backend audit named "streaming, path validation, and queue enrichment"; the true surface is the whole data layer.

**3. The leak.** `asyncio.wait_for` cancels the *future*; `ThreadPoolExecutor` has no interrupt. On timeout the slot is gone until (and unless) the callable returns on its own.

```python
# core/processing_engine.py:416-419
            result = await asyncio.wait_for(
                asyncio.to_thread(processor.process, audio),
                timeout=timeout,
            )
```
```python
# core/stream_chunk_ops.py:110-114
        try:
            _chunk_path, pcm_samples = await asyncio.wait_for(
                processor.process_chunk_safe(chunk_index, fast_start=fast_start),
                timeout=_asc.CHUNK_PROCESS_TIMEOUT,
            )
```

Timeouts: `DEFAULT_PROCESSING_TIMEOUT = 300.0`, `CHUNK_PROCESS_TIMEOUT = 30.0`, and 20/60 s in the cache worker. **BE7-1 names only the 300 s job path. The 30 s chunk path is on the ordinary playback hot loop and fires far more often.**

**4. Why it compounds without bound — the lock cascade.** `process_chunk_safe` is itself a `to_thread` onto a re-entrant lock (verified in source by the orchestrator):

```python
# core/chunked_processor.py:614
        return await asyncio.to_thread(self.process_chunk, chunk_index, fast_start, True)
```
```python
# core/chunked_processor.py:524-526
        if locked:
            with self._processor_lock:
                return self.process_chunk(chunk_index, fast_start, locked=False)
```

Interleaving, all against one `ChunkedAudioProcessor`:
1. Chunk *N* misses cache → an executor worker takes `_processor_lock` and starts a slow decode.
2. 30 s elapse. `wait_for` raises; `stream_chunk_ops.py:115-122` re-raises as a plain `Exception`, which `stream_enhanced.py:255` catches, logs, and `continue`s past (`stream_enhanced.py:290`). **The worker thread is still inside the RLock.**
3. Chunk *N+1* submits a **second** executor thread, which blocks on `_processor_lock.acquire()` — no timeout of its own.
4. Repeat for every remaining chunk. A 4-minute track is ≈24 chunks at `CHUNK_INTERVAL = 10 s`, so **one slow chunk can leak ~24 threads in a single playback** — more than the whole pool on any desktop with ≤16 cores.

The per-chunk recovery branch is what converts one stall into an unbounded leak: it is *designed* to keep going after a chunk failure, so it re-submits ~24 times into a lock a dead thread holds. Note the irony — the `#3852` comment above that `wait_for` reads *"Bound the per-chunk DSP so a hung thread can't wedge the stream forever"*. It bounds the coroutine, not the thread.

**5. Blast radius.** `ThreadPoolExecutor.submit()` does not raise when saturated; it queues on an **unbounded** `SimpleQueue`. The failure mode is therefore not an exception but a silent, permanent hang of every `await asyncio.to_thread(...)` in the process: all streaming, all transport, the entire REST API, queue mutation, the offline mastering queue, and the cache worker — simultaneously. The event loop stays alive, so the WS heartbeat keeps answering pings: **the app looks up while being completely non-functional.** Nothing recovers it short of a restart — no executor watchdog, no `shutdown(cancel_futures=...)`, and the leaked threads never exit.

| CPU cores | Executor slots | Timed-out chunks to total backend death |
|---|---|---|
| 2 | 6 | 6 (≈1 min of one bad track) |
| 4 | 8 | 8 (≈1.3 min) |
| 8 | 12 | 12 (2 min) |
| 16 | 20 | 20 (3.3 min) |
| ≥28 | 32 (cap) | 32 — one 5½-minute track |

- **Impact**: whole-process functional deadlock with no self-recovery. Strictly worse than BE7-1's stated impact.
- **Honest limits**: the *mechanism* is proved from source. What is **not** proved is how often a chunk actually exceeds 30 s in practice. BE8-06 (this session's backend audit) establishes that every enhanced chunk of an M4A/AAC/WMA track triggers a full-file FFmpeg decode, which makes a >30 s chunk plausible on a long track or slow/network storage — but no measurement was taken. Treat the trigger rate as HYPOTHESIS and the consequence as PROVED.
- **Siblings**: all five leak sites; the processor-reuse half is BE7-1 (`processing_engine.py:553-576`); BST-10 is the transient variant.
- **Suggested Fix**: (a) install a dedicated, explicitly sized DSP executor at startup so DSP stalls can never starve DB reads; (b) make the DSP callables cooperatively cancellable via a `threading.Event` — the pattern already exists at `processing_engine.py:137,347,620-622` for FFmpeg decode — and set it on every `wait_for` timeout; (c) in `stream_chunk_ops.py`, abandon the whole processor after the first chunk timeout rather than re-submitting into a held lock.

---

## HIGH

### AP-5: A DSP timeout leaves `_process_lock` held, and the next job's three `reset_*` calls block the asyncio event loop on it

- **Severity**: HIGH
- **Confidence**: **PROVED** (interleaving argument, concrete line numbers)
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py:235-236,474-477,488-491,503-504` + `auralis-web/backend/core/processing_engine.py:380-382,416-419,553-565`
- **Status**: NEW — this is the engine-side answer to BE7-1's blast-radius question
- **Trigger Conditions**: `processor.process()` exceeds `processing_timeout`. `wait_for` raises, the `to_thread` worker keeps running **holding `self._process_lock`**, and the `finally` returns that same instance to the pool. The next job pops it and reaches `_execute_job`.
- **Evidence**:
```python
# auralis/core/hybrid_processor.py:235-236
        with self._process_lock:
            return self._process_impl(target, reference, results, preview_target, preview_result)
```
```python
# auralis/core/hybrid_processor.py:474-477
    def reset_realtime_eq(self) -> None:
        """Reset real-time EQ state (#3787: locked)."""
        with self._process_lock:
            self.realtime_eq_manager.reset()
```
```python
# auralis-web/backend/core/processing_engine.py:380-382  — plain sync calls inside an `async def`
        processor.reset_realtime_eq()
        processor.reset_dynamics()
        processor.reset_psychoacoustic_eq()
```
- **Impact**: the next job's `reset_realtime_eq()` executes **on the event-loop thread** and performs a blocking `threading.RLock.acquire()` on a lock held by an orphaned DSP thread. Because it is `lock.acquire()` and not `await`, the **entire FastAPI event loop freezes** — every HTTP route, the WebSocket audio stream, and progress notifications stall for the unbounded remainder of the orphaned call (which by definition already exceeded its timeout). A single slow track becomes a whole-app hang: audio dropout plus an unresponsive UI, not just a failed job. The poisoned processor also stays in the pool and re-freezes every subsequent job.
- **Siblings**: `processing_engine.py:381` and `:382`; any synchronous call to a `#3787`-locked setter from an `async def` has the same shape.
- **Suggested Fix**: do not return a processor to the pool on the `TimeoutError` branch — `close()` it and drop it, since its thread is unreclaimable; and/or move the three `reset_*` calls into `asyncio.to_thread(...)` with a bounded `acquire(timeout=...)`, so the event loop is never the thread that waits on `_process_lock`.

### AP-6: The pooled `HybridProcessor`'s brick-wall limiter is never reset between jobs — 12 dB of the previous track's gain reduction bleeds into the next track's opening

- **Severity**: HIGH
- **Confidence**: **PROVED — executable repro, re-run and confirmed by the orchestrator**
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py:102-107,305,360,387` + `auralis/dsp/dynamics/brick_wall_limiter.py:204-206,235-236,239-243` + `auralis-web/backend/core/processing_engine.py:375-382`
- **Status**: NEW — same defect class as #2400, which fixed the two EQs and missed the limiter
- **Trigger Conditions**: **no race required.** Any two jobs landing on the same pooled/cached `HybridProcessor` where the first engages the limiter. Pooling alone suffices; concurrency only widens which pairs collide.
- **Evidence**: one limiter is built per processor instance (`hybrid_processor.py:102-107`) and reused by all three process paths (`:305`, `:360`, `:387` — verified by grep). `brick_wall_limiter.py:204-205` seeds each call from the previous call's ending gain and `:236` persists it, deliberately, for #2390 cross-chunk continuity. The inter-job reset block is explicit about what it covers:
```python
# processing_engine.py:375-382
        # Reset EQ state before each job so cached processors don't bleed
        # the previous track's psychoacoustic EQ curve into the new track (fixes #2400).
        ...
        processor.reset_realtime_eq()
        processor.reset_dynamics()
        processor.reset_psychoacoustic_eq()
```
  `BrickWallLimiter.reset()` exists at `brick_wall_limiter.py:239-243`, and a repo-wide grep for its call sites returns **zero in production** — the only `limiter.reset()` hit anywhere is `auralis/dsp/advanced_dynamics.py:332`, a different limiter.
- **Repro** (re-run by the orchestrator against `.venv/bin/python`):
```
initial current_gain = 1.0
after hot job A, current_gain = 0.24151423573493958
after the three reset_* calls, current_gain = 0.24151423573493958
RESULT: PROVED — limiter gain state survives the inter-job resets
max abs difference over first 512 samples of job B: 0.149918 (-2.5 dB rel.)
```
- **Impact**: the next track begins at a factor of 0.2415 (**-12.3 dB**) and recovers only via the 50 ms release coefficient — roughly 5 time constants ≈ **250 ms**. Every job that follows a loud job on the same pooled processor gets an audible quarter-second fade-in, **written into the rendered output file**, not merely heard during playback. Deterministic and silent.
- **Repro caveat (stated for honesty)**: the script drives `brick_wall_limiter.process()` directly rather than a full `process()` call, so it proves the state-persistence mechanism and the reset gap exactly; the *magnitude* on real program material will vary with how hard the first track engages the limiter.
- **Siblings**: `hybrid_processor.py:305` and `:387` share the limiter. `self.buffer` / `self.buffer_pos` are also never reset, but are currently unused by `process()`.
- **Suggested Fix**: add `reset_limiter()` (or a single `reset_state()`) on `HybridProcessor` calling `self.brick_wall_limiter.reset()`, and call it alongside the existing three. Alternatively have `process()` reset the limiter itself, since the offline path always receives a whole track rather than a chunk stream.

### BST-10: Every stream cancellation (track change, seek, WS disconnect) orphans a live executor thread — a scrub storm transiently freezes the whole backend

- **Severity**: HIGH
- **Confidence**: **PROVED**
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:34-55,200,257,319-339`; `auralis-web/backend/ws_handlers/connection.py:168-180`; `auralis-web/backend/core/stream_chunk_ops.py:110-114`; `auralis-web/backend/core/chunked_processor.py:614,524-526`
- **Status**: NEW
- **Trigger Conditions**: two `play_enhanced`/`seek`/disconnect events arriving while a chunk is mid-DSP — i.e. ordinary progress-bar scrubbing or rapid next-track presses. **No error condition required.**
- **Evidence**: cancelling the stream task is prompt because `asyncio.futures.wrap_future` chains only the asyncio side — the wrapper future cancels immediately while the underlying `concurrent.futures.Future` is already RUNNING and refuses `.cancel()`. The coroutine unwinds at once; the executor thread runs to completion, unreferenced.
```python
# ws_handlers/playback_commands.py:48-55  (_cancel_prior_task)
    if old_task and not old_task.done():
        logger.info(f"Cancelling existing streaming task for ws {ws_id}")
        old_task.cancel()
        # Await cancellation so the old task releases pause/flow events (#3219)
        try:
            await old_task
        except (asyncio.CancelledError, Exception):
            pass
```
  `handle_seek` (`playback_commands.py:325-339`) carries a comment that explicitly acknowledges the thread outlives the cancel — *"the prior 100ms wait_for/shield let the old task's DSP work (200ms-2s inside asyncio.to_thread) outlive the timeout"*. The `await old_task` fix stopped the **frame interleaving** but does nothing about the thread: the await returns when the coroutine unwinds, not when the worker finishes.
- **Impact**: on a 4-core desktop (8 slots), **8 scrubs inside one chunk-processing window saturate the pool**. Unlike BST-9 this is self-healing — threads eventually return — but while saturated every `to_thread` in the process queues, so the UI freezes completely: no streaming, no transport, no REST. Secondary correctness effect: the orphan still holds `_processor_lock` and runs to completion, writing its result into the shared chunk cache and the `LevelManager` gain history *after* the requesting stream is gone — so gain state for a cancelled position lands in the history the next stream smooths against.
- **Siblings**: `processing_engine.cancel_job()` (`processing_engine.py:624-628`) — which is exactly why `_cancel_events` exists for FFmpeg but not for `processor.process`.
- **Suggested Fix**: propagate a cooperative-cancel token into `ChunkedAudioProcessor` so `_cancel_prior_task`/`teardown_connection` can signal the in-flight chunk to abort; failing that, give streaming its own bounded executor so a scrub storm cannot reach the REST layer.

### LDB-3: `POST /api/library/reset` pauses three registered workers but not an in-flight manual scan, so a confirmed destructive reset can be silently undone

- **Severity**: HIGH
- **Confidence**: **PROVED**
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/routers/library.py:113-143` vs `auralis-web/backend/routers/library_scan.py:37-135`; `auralis-web/backend/config/background_workers.py:26-30`; `auralis/library/repositories/factory.py:178-216`
- **Status**: NEW
- **Trigger Conditions**:
  1. Client calls `POST /api/library/scan` on a large tree. The handler builds a fresh, ephemeral `LibraryScanner` (`library_scan.py:53`) and runs it via `asyncio.to_thread`. Each file is imported in its own short-lived session — many small independently-committed transactions, not one held transaction.
  2. While that runs, `POST /api/library/reset` with `X-Confirm-Reset: RESET` calls `stop_background_workers(...)`, which iterates exactly `BACKGROUND_WORKER_KEYS = ("auto_scanner", "ondemand_fingerprint_queue", "fingerprint_queue")`.
  3. The manual scanner is a transient object created inside the route handler — never registered under any of those keys, so `stop_background_workers` cannot see it. `reset_library()` also never checks `try_acquire_scan_slot()` / `_active_scans`.
  4. `repos.reset_library()` deletes every content row and commits. SQLite's single-writer semantics prevent *corruption*, but nothing stops the scan thread's next file — queued the moment the write lock releases — from inserting fresh rows into the now-empty library.
- **Evidence**: `reset_library()`'s own docstring states the precondition it cannot enforce — *"Callers must pause background workers first so no rows are inserted between the deletes and the commit."* The manual-scan caller is not in that set.
```python
# config/background_workers.py:26-30
BACKGROUND_WORKER_KEYS: tuple[str, ...] = (
    "auto_scanner",
    "ondemand_fingerprint_queue",
    "fingerprint_queue",
)
```
- **Impact**: a user who explicitly confirmed a one-way, header-gated library wipe gets a 200 promising a clean library, then watches tracks reappear seconds later with no indication anything went wrong. It silently defeats the exact invariant #3342/#4111 were filed to establish, for a common trigger those fixes did not consider.
- **Siblings**: any other ad-hoc write path outside the three keys — e.g. a metadata-editor bulk update in flight during a reset.
- **Suggested Fix**: have the reset route check `try_acquire_scan_slot()` and reject with 409 while a scan is active (mirroring the scan endpoint's own 409-on-conflict), or route ad-hoc scans through the same registry `stop_background_workers` consults, so there is one write-path list rather than two independently maintained ones.

---

## MEDIUM

### BST-11: When the processing worker dies, the watchdog nulls the very global that `_shutdown_components` gates on — so `stop_worker()` is skipped and in-flight DSP threads outlive teardown

- **Severity**: MEDIUM
- **Confidence**: **PROVED**
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/config/startup.py:194-212` (watchdog) vs `auralis-web/backend/config/startup.py:118-124` (shutdown gate)
- **Status**: NEW — the concurrency angle of BE6-2, but a different function and a different mechanism (BE6-2 is `_rollback_partial_startup`; this is `_watch_critical_worker_task` + `_shutdown_components`)
- **Trigger Conditions**: `start_worker()`'s task finishes for any reason other than cancellation, at any point after startup, while `_run_job` tasks are in flight; then the app shuts down.
- **Evidence**:
```python
# config/startup.py:194-212
    def _on_done(t: asyncio.Task[Any]) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        ...
        for key in keys_to_clear:
            globals_dict[key] = None
```
  wired with `keys_to_clear = ('processing_engine',)`. The shutdown path then reads `if globals_dict.get('processing_engine'):` before calling `stop_worker()`. `JobWorker.stop()` (`auralis-web/backend/core/job_worker.py:117-193`) is the **only** thing that cancels the per-job tasks in `self._tasks` — they are spawned fire-and-forget and nothing else holds them.
- **Impact**: with the global nulled, `stop_worker()` never runs, those tasks are never cancelled, their `asyncio.to_thread(processor.process, ...)` threads keep running, and the `#4543` comment's own stated hazard is reinstated verbatim — a live `HybridProcessor` and DSP threads outlive `LibraryDatabase.shutdown()` (which WAL-checkpoints SQLite) and `audio_player.cleanup()`. Interpreter exit then blocks on `loop.shutdown_default_executor()`; the visible symptom is an Electron quit that hangs.
- **Siblings**: identical shape for the streamlined cache worker — `keys_to_clear = ('streamlined_cache', 'streamlined_worker')` vs the `if globals_dict.get('streamlined_worker')` gate.
- **Suggested Fix**: keep the object under a separate key the shutdown path uses and null only the router-facing key; or have `_on_done` schedule the stop before nulling.

### BST-12: `QueueService._set_queue_lock` is held across a WebSocket broadcast and four `to_thread` audio-player calls

- **Severity**: MEDIUM
- **Confidence**: **PROVED**
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/queue_service.py:216-217,219-277`
- **Status**: NEW — sibling of BE4-15, which is filed against `PlaybackService._playback_lock`; this is a different class and a different lock
- **Trigger Conditions**: any `set_queue` while a WS client's TCP receive buffer is full, or while the shared executor is saturated (BST-9 / BST-10).
- **Evidence**:
```python
# services/queue_service.py:216-217
        async with self._set_queue_lock:
            return await self._set_queue_impl(track_ids, start_index)
```
  and inside `_set_queue_impl` (219-277), still under the lock: `await asyncio.to_thread(tracks_repo.get_by_ids, ...)` (234), `await asyncio.to_thread(_fetch_individually)` (245), `await self.player_state_manager.set_queue(...)` (255) — which reaches `_broadcast_state` → `ws_manager.broadcast` — `await asyncio.to_thread(self.audio_player.load_file, ...)` (273), `await asyncio.to_thread(self.audio_player.play)` (274), and `await self.player_state_manager.set_playing(True)` (277), a second broadcast.
- **Impact**: the lock's stated purpose (#3721) is to serialise double-clicked set-queue requests, but its hold now spans two full broadcasts and four executor round-trips. Under BST-9 the hold becomes permanent and every subsequent queue operation wedges too. The *multi-client* half of this is LOW on a single-client desktop; the executor-starvation half applies to a single client.
- **Siblings**: `PlaybackService._playback_lock` (BE4-15, already filed).
- **Suggested Fix**: narrow the lock to the queue-state mutation and release before the player calls and broadcasts; or replace it with a per-request generation counter that drops stale results.

### AP-7: `_get_or_create_processor` mutates a caller-owned `UnifiedConfig` outside the owning processor's `_process_lock`

- **Severity**: MEDIUM
- **Confidence**: **PROVED** (by code reading — the aliasing and the missing lock are both unambiguous)
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py:639,651-654` vs the locked equivalent at `:553-566`
- **Status**: NEW — an escape hatch around the #3714 fix
- **Trigger Conditions**: any caller passing the *same* `UnifiedConfig` object to two of `process_adaptive` / `process_reference` / `process_hybrid`. The second call takes a different cache key, misses, and executes `config.set_processing_mode(mode)` — mutating the object the first cached processor still holds as `self.config`.
- **Evidence**:
```python
# hybrid_processor.py:639 — key is per-(config-identity, mode), so one config backs several processors
    cache_key: str = f"{id(config)}_{mode}" if config else f"default_{mode}"
```
```python
# hybrid_processor.py:651-654 — the caller's config is mutated in place, then stored by reference
        if config is None:
            config = UnifiedConfig()
        config.set_processing_mode(mode)  # type: ignore[arg-type]
        _processor_cache[cache_key] = HybridProcessor(config)
```
  Compare `hybrid_processor.py:553-566`, where the identical write is deliberately serialised because *"the mode write into `self.config` is read by `process()` to dispatch between adaptive / reference / hybrid pipelines. A concurrent cache-shared caller swapping modes mid-process would otherwise send chunks down the wrong pipeline."* `_get_or_create_processor` performs exactly that write and takes only `_processor_cache_lock`.
- **Impact**: (1) single-threaded — a later cache hit returns a processor whose shared config now reads a different mode, so `_process_impl`'s dispatch routes audio down the wrong pipeline or raises `ValueError`. (2) Concurrent — the mode can flip between the `is_reference_mode()` check and the mode-dependent work that follows, which is precisely what #3714 was filed to prevent.
- **Reachability caveat (why MEDIUM, not HIGH)**: `process_adaptive` / `process_reference` are public API (`auralis/__init__.py`) but have **no in-tree production caller** — the backend uses `ProcessorPool`, whose key is content-derived, not `id()`-derived. This is a library-consumer defect.
- **Siblings**: `auralis-web/backend/core/processor_factory.py:302` performs the same bare `config.set_processing_mode(mode)` — worth verifying whether that config is ever shared with an already-cached processor.
- **Suggested Fix**: deep-copy the config (or build a fresh `UnifiedConfig` from its fields) before `set_processing_mode`, so each cached processor owns its config exclusively; or key the cache on config *content* the way `ProcessorPool` does.

### FST-3: The transport rapid-click guard is entirely disconnected — the `disabled` prop is wired to a Redux field nothing ever sets

- **Severity**: MEDIUM
- **Confidence**: **PROVED**
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:107-320`; `auralis-web/frontend/src/components/shared/PlayerControls/PlayerControls.tsx:39-40,85`; `auralis-web/frontend/src/components/shared/PlayerControls/TransportControls.tsx`; `auralis-web/frontend/src/store/slices/playerSlice.ts:210-217,546`
- **Status**: NEW
- **Trigger Conditions**: a user double- or rapid-clicks Next, Previous, Play/Pause, or drags the seek bar. No timing subtlety — the guard never engages at all.
- **Evidence**: three independent pieces of dead scaffolding.
  - `usePlaybackControl.ts:111`: `const executingCommand = useRef<string | null>(null);` is written in every command and cleared in every `finally`, but is **never read anywhere in the file**. It looks like a re-entrancy guard and is not one.
  - `usePlaybackControl.ts:107-108`: a **local** `useState` `isLoading` that *does* toggle correctly around each request.
  - `PlayerControls.tsx:85`: the prop actually passed to `TransportControls` (`disabled={isLoading}` on all three buttons) is `player.isLoading` — the **Redux** `state.player.isLoading`, not the hook's own.
  - `playerSlice.ts:210-217`: the `setIsLoading` action that would flip that Redux field is referenced only at its own definition; a repo-wide grep for `dispatch(setIsLoading(` returns **zero production call sites**. `state.player.isLoading` is permanently `false` from `initialState` onward.
- **Impact**: Next/Previous/Play-Pause are never disabled while a command is in flight. N rapid clicks send N independent `POST /api/player/next` (or the `previous` / `seek` / `volume` equivalents) with no coalescing, no abort-the-prior-request, and no UI feedback. These are real server-side mutations, so the user gets more skips or seeks than intended — and the hook's own bookkeeping creates a false impression that a guard exists.
- **Siblings**: `pause`, `stop`, `seek`, `setVolume` in the same file — all six share the identical non-functional scaffolding.
- **Suggested Fix**: wire `TransportControls`'s `isLoading` to `usePlaybackControl().isLoading` (the value that actually toggles), or use `executingCommand` as a real re-entrancy guard. Delete whichever source is not adopted, so the dead-code trap does not recur.

### FST-4: Queue-mutation optimistic rollback can clobber a later, already-succeeded mutation

- **Severity**: MEDIUM
- **Confidence**: **PROVED** (interleaving argument from the code; requires a real timing window to trigger)
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:90-137`; `auralis-web/frontend/src/store/slices/queueSlice.ts:163-172`
- **Status**: NEW
- **Trigger Conditions**: two `runOptimistic` mutations issued back-to-back before the first settles, where the **first** rejects **after** the second's `apply()` has run.
- **Evidence**: `useQueueMutations.ts:109-137` captures `previousTracks = stateRef.current.tracks` and, on failure, dispatches `reduxSetQueue(previousTracks)` — a **full-array overwrite**, not a targeted undo of this mutation's delta (`queueSlice.ts:163-172`: `state.tracks = action.payload`). Concretely: A (`addTrack`) snapshots `orig`; B (`removeTrack`) snapshots `orig + trackA` and applies on top; B succeeds; A then rejects and dispatches `reduxSetQueue(orig)`, discarding B entirely. The code's own comment (lines 106-108) acknowledges it relies on a trailing `queue_changed` broadcast to correct compounding — but that broadcast is not synchronised with rollback timing, so a rollback arriving after it silently reintroduces stale state.
- **Impact**: a user firing two queue actions in quick succession can see the queue revert to a stale, incorrect state if the *earlier* request is the one that fails — even though the later one succeeded and correct server state briefly reached Redux.
- **Siblings**: `toggleShuffle` (224-247) and `setRepeatMode` (249-283) use the same rollback-from-ref pattern but overwrite a single scalar, so the blast radius there is one field rather than the whole queue.
- **Suggested Fix**: track a generation counter per `runOptimistic` call and skip the rollback if a newer optimistic mutation has since been applied; or dispatch a targeted inverse of `apply()` rather than a wholesale array replace.

---

## LOW

### BST-13: `ChunkCacheManager._prune_lock` is a process-wide lock held across a full directory scan and unlink loop, taken from executor threads on the chunk-write hot path

- **Severity**: LOW
- **Confidence**: **PROVED**
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/chunk_cache_manager.py:138-139,249-263,265-316`
- **Status**: NEW
- **Trigger Conditions**: every 32nd cached chunk write across all `ChunkedAudioProcessor` instances.
- **Evidence**:
```python
# core/chunk_cache_manager.py:255-263
        cls = type(self)
        with cls._prune_lock:
            cls._write_counter += 1
            if cls._write_counter < self._prune_every:
                return
            cls._write_counter = 0
            # Prune under the lock so concurrent writers don't launch overlapping
            # reapers; a scan of a few hundred files is sub-millisecond-to-ms.
            self.prune_chunk_directory(chunk_dir, self._max_disk_bytes)
```
  `prune_chunk_directory` does `chunk_dir.iterdir()` plus a `p.stat()` per file, then an `unlink()` loop. With `MAX_CHUNK_DISK_BYTES = 512 MB` over ~1 MB WAV chunks, the comment's "few hundred files" is really up to ~500 `stat()` calls plus deletions, on cold page cache or spinning/network storage.
- **Impact**: every chunk-cache write in the process — from all concurrent streams and the background cache worker, all on executor threads — serialises behind one prune. Because those are *default-executor* threads (BST-9), a slow prune occupies multiple executor slots at once. Bounded and self-clearing, hence LOW, but a direct multiplier on BST-9/BST-10.
- **Siblings**: none.
- **Suggested Fix**: take the lock only to test-and-reset the counter, then run the scan outside it; a second `try_lock` guard is enough to prevent overlapping reapers.

---

## Escalation of an Existing Issue (not re-filed)

### Addendum to #3735: `next_track()`'s prebuffer-miss fallback runs a blocking disk decode while `_audio_lock` is held by the whole call

- **Severity**: HIGH (matches #3735's own tag) · **Confidence**: **PROVED** (mechanism independently re-verified by the orchestrator)
- **Location**: `auralis/player/enhanced_audio_player.py:340-342` → `auralis/player/gapless_playback_engine.py:195-363` (fallbacks at `:322-358` and `:266-305`) → `auralis/player/audio_file_manager.py:59-64`
- **Status**: **Existing: #3735** — adds the mechanism detail explaining why the partial fix did not close the window
- **Why this matters**: #3735's landed fix narrowed what happens *after* the `with` block (see the comment at `enhanced_audio_player.py:333-339`). It did not touch the fallback branch, which is the actual wide-lock window.

`next_track()` opens `with self.playback.defer_notifications(), self.file_manager._audio_lock:` at `:340` and calls `advance_with_prebuffer()` at `:342`, inside that block. The fallback path then does:
```python
# gapless_playback_engine.py:337-342
            with self.file_manager._audio_lock:
                old_audio = self.file_manager.audio_data
                old_sr = self.file_manager.sample_rate
                old_file = self.file_manager.current_file
            if not self.file_manager.load_file(file_path):
                return False
```
and `AudioFileManager.load_file()` performs the decode *before* its own swap:
```python
# audio_file_manager.py:59-64
            # Load outside the lock (I/O may be slow); then swap atomically.
            audio_data, loaded_sample_rate = load(file_path, "target")
            with self._audio_lock:
```
Because `_audio_lock` is an **RLock** and the same thread already holds it via the outer `with`, the recursion counter never reaches zero — the "load outside the lock" discipline is defeated by the caller, and the lock stays unavailable to *other* threads for the full decode.

- **Impact**: the real-time audio callback thread's `get_audio_chunk()` blocks on `_audio_lock` for the duration of a full-file decode instead of the microseconds a slice/swap needs. That stalls chunk delivery past the real-time deadline — an audible dropout during exactly the gapless-transition path this code exists to make seamless. Per the severity rules ("gapless transition with audible gap >1 ms" = HIGH), and this is the *fallback* path, hit on any prebuffer miss, not a rare edge case.
- **Siblings**: the mismatch-fallback at `gapless_playback_engine.py:266-305` has identical shape.
- **Suggested Fix**: release `_audio_lock` before `load_file()` on the fallback paths and re-acquire only for the atomic swap + queue-advance commit — mirroring `add_to_queue()` (`enhanced_audio_player.py:432-448`, fixed for exactly this class under #3656). This requires restructuring the fallback's snapshot/restore, since today's rollback-on-mutation correctness depends on the RLock's reentrancy.

---

## Cross-Audit Confirmations (already filed this session — not re-counted)

- **BE4-6** (`docs/audits/AUDIT_BACKEND_2026-07-29.md:1472`) — `LibraryAutoScanner._stop_watchdog()` blocks the event loop on `Observer.join(timeout=5)`. Dimension 4 rediscovered this independently at `auralis-web/backend/services/library_auto_scanner.py:390-430` and adds one detail: it fires not only at shutdown but on every folder-list change via `reload_config()`, which is a live-playback moment. Filed there; not double-counted here.
- **BE4-5** — `NavigationService` calls blocking `AudioPlayer` methods on the event loop. Dimension 1 raised this independently as a HYPOTHESIS; dimension 3 confirmed it is already filed. Note the compound with the #3735 escalation above: a prebuffer-miss `next_track()` arriving through that endpoint blocks the *whole event loop* for a decode, not just the audio thread.
- **BE7-1** — the processor-reuse half of BST-9. BST-9 is the blast-radius escalation, not a duplicate.
- **BE4-15** — `PlaybackService._playback_lock` across a broadcast. BST-12 is the same pattern in a different class/lock.
- **#4582** (OPEN, MEDIUM) — discrete WS player events have no ordering guard. Sibling sweep confirms `player_state` and `position_changed` are seq-guarded in `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts` while `playback_started`/`resumed`/`paused`/`stopped`, `volume_changed` and `track_changed` are not. Verified still present; not re-filed.

---

## Verified FIXED since the 2026-07-25 audit (regression checks, not re-filed)

| Prior finding | Verdict | Evidence |
|---|---|---|
| **BST-1** — chunk WAV cache written non-atomically | **FIXED** | `chunked_processor.py:791` now uses `atomic_write_bytes`; `atomic_io.py:49-79` stages via `mkstemp` + `fsync` + `os.replace`; read path gated by `is_wav_complete` |
| **BST-3** — `JobWorker.stop()` cancels but never awaits | **FIXED** | `job_worker.py:154-162`, `asyncio.wait(cancelled, timeout=...)` (#4543) |
| **BST-8** — stale `_worker_task` after `StreamlinedCacheWorker.stop()` | **FIXED** | `streamlined_worker.py:145-149` (#4577), plus an `is_running` property checking all three dead states |
| **LDB-1** — `migration_lock` deletes its own lock file during teardown | **FIXED** | `migration_manager.py:127-140` no longer unlinks; docstring at `:60-65` documents why (#4523). The `threading.Lock` also moved *into* `migration_lock()` itself, so both migration entry points are now covered — better than before |
| **PTS-1** — `RealtimeLevelMatcher.get_stats()` unlocked | **FIXED** | `auralis/player/realtime/level_matcher.py:122-146` (#4551) |
| **PTS-2** — `IntegrationManager` holds `_position_lock` across ORM `to_dict()` | **FIXED** | `auralis/player/integration_manager.py:106-129` materialises the dict before taking the lock (#4552) |
| **PTS-3** — `PlayerPropertiesMixin` setters bypass locks | **FIXED** | `auralis/player/player_properties_mixin.py` setters now route through locked paths (#4574) |
| **AP-3** — `ParallelBandProcessor` un-copied array per band group | **FIXED** | `auralis/optimization/parallel/band_processor.py` — `audio.copy()` on all 8 paths (#4572) |

---

## Verified Safe (checked and found correct)

**The `manager.py` → `database.py` composition-root move (#4619) is clean.** Explicitly re-verified because the prior audit's safety evidence pointed at the old location: `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=60000`, `check_same_thread` and `pool_pre_ping` all live in the `connect` listener at `auralis/library/database.py:145-164`. `manager.py` no longer defines its own engine at all — it subclasses `LibraryDatabase`, so there is exactly one pragma-setting path rather than two that can drift. The scan-slot counted semaphore moved intact to `database.py:262-288` (check-and-increment in one critical section, release floors at 0).

**`HybridProcessor._process_lock` genuinely serialises — the BE7-1 damage is a stall, not corruption.** Every instance attribute written during a `process()` call was traced and all are inside the RLock: `last_content_profile`, `current_targets`, all of `ContinuousMode`'s `last_*` / `_reference_cloud` / `_distance_stats` / `_quality_gate_call_count`, `AdaptiveMode.last_content_profile`, `PsychoacousticEQ.current_gains`, `BrickWallLimiter.current_gain`. Every mutating public setter takes it too. Two threads cannot tear the state; the second blocks — which is exactly what makes AP-5 dangerous. The only unlocked reads are pure getters; the worst outcome is `_finalize_job` reading a `last_content_profile` written by a different job — telemetry only, never audio.

**The engine audit's `loudness_maximizer` judgement is CORRECT — and does not generalise.** `auralis/core/stages/loudness_maximizer.py:80-85` constructs a fresh limiter inside `apply()` on every call, so no limiter state crosses chunk or call boundaries; `gained = audio * (...)` allocates a new array and the caller's `audio` is never written. The in-code comment is accurate. **However**, the same class used *statefully* by `HybridProcessor` is not safe — that is AP-6, and it is how the gap surfaced.

**Streaming semaphores — independent verdict: CORRECTLY BALANCED, prior claim CONFIRMED not refuted.** All 8 `_stream_semaphore` sites (the complete set) were walked: enhanced acquires at `stream_enhanced.py:71` / releases in the `finally` at `:335`; normal at `stream_normal.py:65` / `:360`; seek at `stream_seek.py:79` / `:350`. Between each acquire and its guarding `try:` there are only assignments — **no `await`** on any of the three. The 5 s acquire timeout path returns without having acquired. Python 3.12+ `Semaphore.acquire` restores `_value` on cancellation, so the cancelled-while-queued case does not lose a permit. **Robustness note, not a defect**: the balance depends on a blanket `contextlib.suppress(CancelledError, Exception)` in `drain_cancelled_task` (`stream_chunk_ops.py:217-230`) — a helper whose docstring is about something else (#3493) — happening to let the `finally` reach `release()`. Moving `release()` above the drain would make the invariant explicit rather than incidental.

**Rust / PyO3 boundary — clean.** 11 `#[pyfunction]`s and 12 `py.allow_threads` sites in `vendor/auralis-dsp/src/py_bindings.rs`; every long compute releases the GIL inside `catch_unwind`. Inputs are copied out of the NumPy buffer *before* crossing the boundary (`as_array().to_vec()` / `.to_owned()`), and returns hand back ownership of a fresh Vec via `into_pyarray`. Repo-wide greps over `vendor/auralis-dsp/src/` for `static` / `lazy_static` / `once_cell` / `thread_local` and for `unsafe` return **zero hits**.

**Copy-before-modify across the DSP pipeline — clean.** A targeted grep across all 13 stage modules in `auralis/core/stages/` for in-place operators (`*=`, `+=`, `-=`, `/=`), `out=` and `arr[...] =` on the caller's array found **zero** in-place writes. Entry copies confirmed on every mode path. `dsp/basic.py` `normalize`/`amplify` return new arrays. `sanitize_audio` copies before repairing.

**Player lock ordering — correct.** The only two locks that ever nest are `_position_lock` and `_audio_lock`, and every path acquires them in that single order. `defer_notifications()` exists specifically to stop callback dispatch (which would take `_position_lock`) from firing while `_audio_lock` is held, closing the AB-BA documented at `auralis/player/playback_controller.py:71-87`. Verified against every `with ... _lock` site in the six player files. Callbacks are snapshotted under the lock and invoked after release — no callback runs with a player lock held.

**Auto-advance and queue mutation — correct.** `_auto_advance_next` is gated by an Event plus a monotonic generation counter, both mutated under `_audio_lock` at spawn and at the compare-and-clear (#3718/#3434). `cleanup()` reads the thread reference under the lock (#4227). `GaplessPlaybackEngine.start_prebuffering()` double-checks `is_alive()` inside `_thread_lock`. Every `QueueManager` mutator and reader goes through its RLock, including composite atomic ops. `stop()`/`play()` races (#3669, #4126) confirmed still fixed.

**Task-registry lock discipline — correct.** All three cancel-and-await paths pop under `state.active_tasks_lock` then cancel/await **outside** it; the stream tasks' `finally` self-cleanup re-acquires the same lock guarded by an `is my_task` identity check, so the #3828/#2425/#2430 deadlock cannot recur.

**`PlayerStateManager` — correct.** Mutates and snapshots under `_lock`, broadcasts outside; `_position_update_loop`'s `await self.next_track()` is outside the locked block, so it cannot self-deadlock.

**`ResizableSemaphore` and the fingerprint queue — correct.** Grow calls `notify_all()`, shrink is lazy and never preempts, `release()` guards against going negative, single `Condition` with no nested locks. `claim_next_unfingerprinted_track` / `claim_next_outdated_fingerprint` are genuinely atomic claims (UNIQUE-constraint race-loser check and `rowcount != 1` check respectively), and both `expunge_all()` before returning a detached shell rather than a session-bound ORM object.

**Frontend audio path — no cross-thread race despite the AudioWorklet architecture.** `BufferScheduler.startFeeding()` reads `PCMStreamBuffer` inside a main-thread `setInterval` and forwards *cloned* sample arrays over `workletNode.port.postMessage`; the worklet never touches the buffer instance. The `ScriptProcessorNode` fallback's `onaudioprocess` is also main-thread. So `read()`/`append()` are single-threaded in practice. Separately, there is **no `MediaSource`/`SourceBuffer` in production** (only a test file), so the `appendBuffer`-while-`updating` race class does not apply.

**Frontend request-race guards — mature where they exist.** `useRestAPI.ts` has a per-endpoint sequence-number stale-response guard, unmount-time `AbortController` cleanup, and a counter-based `isLoading` that survives overlapping requests. The enhanced-playback stack uses per-stream `stream_epoch` matching to drop pre-seek frames and `AbortController`-based supersede handling in `useEnhancedPlayCommand.ts:83-100`.

**Also checked and dismissed**: `spawn_background_task` GC hazard (a strong reference exists at every suspension point); `ChunkCacheManager.clear_track_cache` / `get_statistics` unlocked dict iteration (**zero production callers** — dead code); `hybrid_processor._processor_cache`'s `id()` key (each entry holds a strong config reference, so id-reuse cannot occur — though the *mutation* of that config is AP-7); `useOptimisticUpdate.ts`'s generic rollback race (zero production call sites); `RealtimeProcessor.process_chunk`'s one-chunk-stale effects flag (deliberate, documented at #3784).

---

## Relationships

- **BST-9 ↔ BST-10 ↔ AP-5 ↔ BST-13 ↔ BST-12 are one root cause with five faces**: *the backend has exactly one unowned, unbounded, unmonitored thread pool, and every subsystem that wants to do blocking work reaches for it.* BST-9 is permanent exhaustion, BST-10 is transient exhaustion, AP-5 is the event loop itself joining the queue of blocked waiters, BST-13 multiplies each occupied slot's duration, and BST-12 turns a saturated pool into a wedged queue subsystem. **A dedicated, explicitly sized DSP executor plus a cooperative-cancel token fixes or de-fangs all five.** This is by far the highest-leverage structural change in this report.
- **AP-5 + AP-6 are both consequences of processor pooling** meeting code written as if each processor were fresh. AP-6 is state that should have been reset; AP-5 is a lock that should have been released. Both would disappear if a timed-out processor were closed rather than returned — which is also part of BE7-1's fix.
- **AP-6 ↔ #2400**: #2400 fixed two of the four stateful components on the pooled processor and its comment enumerates exactly what it covers. The limiter was the third. `advanced_dynamics.py`'s `DynamicsProcessor` cross-call state is the fourth and was **not** enumerated this pass — see coverage gaps.
- **BST-11 ↔ BE6-2** are the same anti-pattern in two functions: *nulling a global as an error signal, when a later teardown step gates on that same global being non-null.* Both should be fixed by separating the "is this healthy?" flag from the "here is the object to shut down" reference.
- **#3735 escalation ↔ BE4-5**: individually, one blocks the audio thread and one blocks the event loop. Composed — a prebuffer-miss `next_track()` arriving over the REST/WS transport — they block both at once for the duration of one file decode.
- **LDB-3 ↔ #3342/#4111 ↔ #4509**: three findings all circling the same gap — there is no single authoritative registry of "things that can write to the library", so each fix enumerates the writers it happened to know about.
- **FST-3 ↔ FST-4 ↔ #4582** are all *client-side ordering discipline applied to some paths and not others*: a guard exists (`isLoading`, generation tracking, `seq`) and is simply not wired to every consumer.

---

## Prioritized Fix Order

1. **BST-9** — install a dedicated, sized DSP executor and stop leaking it. Highest blast radius in the report (whole backend, no self-recovery), and the fix is additive and low-risk. Do this first; it de-fangs BST-10, BST-12, BST-13 and halves AP-5.
2. **AP-5 + BE7-1 together** — do not return a processor to the pool on the `TimeoutError` branch, and move the three `reset_*` calls off the event loop. Same code region, same root cause, one changeset.
3. **AP-6** — add `reset_limiter()` and call it with the other three. Smallest diff in the report and the only finding here that puts a defect in the user's rendered output file.
4. **LDB-3** — gate `reset_library` on `try_acquire_scan_slot()`. A user-confirmed destructive action must not silently fail; the fix is a few lines and mirrors an existing 409 pattern.
5. **#3735 escalation** — restructure the `advance_with_prebuffer` fallbacks to decode outside `_audio_lock`. Real-time audio correctness; needs care because rollback currently depends on RLock reentrancy.
6. **BST-10** — cooperative-cancel token into `ChunkedAudioProcessor`. Naturally follows from BST-9's fix (b).
7. **BST-11** — separate the health flag from the shutdown reference (and do the same for `streamlined_worker`).
8. **BST-12** — narrow `_set_queue_lock`; batch with BE4-15, which is the identical pattern.
9. **FST-3** — one-line prop rewire plus deleting the dead scaffolding. Cheap, and it removes a trap that will otherwise be re-encountered.
10. **AP-7, FST-4, BST-13** — hardening; batchable into one commit each.

---

## Dimensions Covered

All five dimensions produced a non-empty report with an explicit coverage statement. **No dimension was lost or unrecoverable.**

| Dim | Area | Output | Findings |
|---|---|---|---|
| 1 | Player Thread Safety | complete | 0 new (1 escalation of #3735, 3 prior findings verified fixed) |
| 2 | Audio Processing Pipeline | complete | 2 HIGH, 1 MEDIUM (1 with executable repro) |
| 3 | Backend WebSocket & Streaming | complete | 1 CRITICAL, 1 HIGH, 2 MEDIUM, 1 LOW |
| 4 | Library & Database | complete | 1 HIGH new (+1 duplicate of BE4-6) |
| 5 | Frontend State Consistency | complete | 2 MEDIUM |

### Coverage Gaps — declared so the next pass knows where to look

**Highest-value unreached ground, in priority order:**

1. `auralis/dsp/advanced_dynamics.py` — `DynamicsProcessor`'s cross-call state was **not** enumerated. `reset_dynamics()` *is* called between jobs, but AP-6 is precisely the lesson that "a reset method exists" and "the reset covers all the state" are different claims. This is the single most likely place for an AP-6 sibling.
2. `auralis-web/backend/ws_handlers/playback_control.py` and `ws_handlers/messages.py` — the pause/flow `asyncio.Event` set/clear discipline against a concurrently-replaced event object is unverified. Dimension 3 rates this the most likely remaining race in its area.
3. `auralis-web/backend/core/chunk_cache.py` (`SimpleChunkCache` internals) and `core/processor_factory.py` — neither's own locking was read this pass.
4. `auralis-web/backend/config/globals.py` — `ConnectionManager.connect`/`disconnect`/`broadcast` fan-out locking not read (relevant to the #3870 concurrent-send hazard, which the prior audit argued is under-triaged at LOW).
5. Player-reads-during-scan-writes: can a scan update or delete a currently-playing track's row while the player holds a stale ORM reference? Not traced.

**Also not reached**: 12 of the 14 repositories (only `fingerprint_scheduler_repository.py` and `factory.py` were read in full); `auralis/library/caching/`, `auralis/library/metadata_editor/`, and the four remaining `auralis/library/scanner/` modules; `auralis/dsp/realtime_adaptive_eq/` internals (deprioritised — documented unwired per #4615); `auralis/core/processing/` support modules (`continuous_space.py`, `parameter_generator.py`, `target_derivation.py`, etc.); the other Rust sources in `vendor/auralis-dsp/src/` beyond `py_bindings.rs` (grep-level only); frontend `auralis-web/frontend/src/store/middleware/`, `auralis-web/frontend/src/store/selectors/`, `auralis-web/frontend/src/hooks/library/`, `auralis-web/frontend/src/hooks/fingerprint/`, `hooks/websocket/useWebSocketMessages.ts` and `websocketConnectionCore.ts`, `auralis-web/frontend/src/api/transformers/`, and `services/audio/PlaybackPositionTracker.ts`.

**Testing**: no tests were executed, per the audit constraints and the known hangs in `tests/backend/test_system_api.py` and `tests/concurrency/test_thread_safety.py`. Two throwaway repro scripts were run against `.venv/bin/python` (the AP-6 script is preserved in the session scratchpad as *repro_limiter_bleed.py*; it is ~50 lines and reconstructible from the AP-6 evidence above) (the AP-6 limiter-bleed repro, re-run and confirmed by the orchestrator; and an `inspect.getsource` probe of CPython's `run_in_executor` used as evidence for BST-9). Every other finding is static-analysis-derived, with trigger conditions reasoned from code rather than observed — which is why each finding carries an explicit PROVED/HYPOTHESIS marker.

---

## Suggested Next Step

```
/audit-publish docs/audits/AUDIT_CONCURRENCY_2026-07-29.md
```

Publish labels: severity (`critical` / `high` / `medium` / `low`) + `concurrency` + `bug`, plus the domain label per finding (`player`, `backend`, `streaming`, `dsp`, `library`, `frontend`).

**Publishing note**: BST-9 is an *escalation* of BE7-1, not an independent defect. If BE7-1 has already been filed from `docs/audits/AUDIT_BACKEND_2026-07-29.md`, prefer raising that issue's severity and appending BST-9's blast-radius analysis over opening a second issue for the same code path. LDB-2 was deliberately folded into BE4-6 and is not counted in the totals above.
