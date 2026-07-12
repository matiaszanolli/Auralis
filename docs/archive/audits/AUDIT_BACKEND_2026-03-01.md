# Backend Audit — 2026-03-01 (v3)

**Auditor**: Claude Sonnet 4.6 (automated)
**Scope**: FastAPI backend — `auralis-web/backend/`
**Dimensions**: Route Handlers · WebSocket Streaming · Chunked Processing · Processing Engine · Schema Consistency · Middleware & Config · Error Handling · Performance · Test Coverage
**Method**: 3 parallel exploration agents (core streaming/processing, routers/serializers, config/schemas/fingerprint), followed by manual verification of all candidate findings against source. Prior findings BE-16–BE-18 re-verified. 17+ false positives from agents eliminated.

## Executive Summary

The backend is in strong shape after the fixes landed in commit `7a22efe0`. All three prior open findings (BE-16, BE-17, BE-18) are confirmed fixed. The codebase demonstrates well-structured semaphore management, correct asyncio locking patterns, and thorough error recovery in the streaming layer.

**Results**: 3 new confirmed findings (0 CRITICAL, 0 HIGH, 0 MEDIUM, 3 LOW). Total open findings: 3 (all new, all low).

| Severity | New | Carried-over (open) | Total Open |
|----------|-----|---------------------|------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 0 | 0 |
| LOW | 3 | 0 | 3 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| BE-16: Enhancement router uses CHUNK_DURATION instead of CHUNK_INTERVAL | #2607 | **FIXED** — commit `7a22efe0` corrects chunk indexing to use CHUNK_INTERVAL |
| BE-17: WebSocket error handler exposes raw exception string to client | #2608 | **FIXED** — commit `7a22efe0` adds `_send_error` with sanitized messages at 6 sites |
| BE-18: Artist search joinedload causes N+1 on tracks and genres | #2609 | **FIXED** — commit `7a22efe0` replaces nested joinedload with selectinload in artist repository |

## New Findings

---

### BE-19: `_FINGERPRINT_WORKERS` evaluates to 0 on single-core CPU
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:48,58`
- **Status**: NEW → #2621
- **Description**: The worker count formula `min(2, (os.cpu_count() or 4) // 2)` returns 0 when `os.cpu_count()` is 1. On a single-core CPU: `(1 or 4) // 2 = 1 // 2 = 0`, then `min(2, 0) = 0`. Passing `max_workers=0` to `ProcessPoolExecutor` raises `ValueError` at line 58, crashing fingerprint initialization for any user on a single-core machine.
- **Evidence**:
  ```python
  # fingerprint_generator.py:48
  _FINGERPRINT_WORKERS = min(2, (os.cpu_count() or 4) // 2)
  # On cpu_count=1: min(2, 0) = 0

  # fingerprint_generator.py:58 — crashes with ValueError
  _fingerprint_executor = ProcessPoolExecutor(
      max_workers=_FINGERPRINT_WORKERS,  # 0 → ValueError: max_workers must be greater than 0
  )
  ```
  The `or 4` guard only fires when `os.cpu_count()` returns `None` (impossible to determine), not when it returns the integer `1`.
- **Impact**: Background fingerprint generation fails entirely on single-core hosts. The `ValueError` propagates through `_get_fingerprint_executor()` on first fingerprint request, logging an unhandled exception. Subsequent audio streaming falls back to non-fingerprint-optimized parameters silently.
- **Suggested Fix**: Change the formula to `max(1, min(2, (os.cpu_count() or 2) // 2))` to guarantee at least one worker.

---

### BE-20: `cancel_job()` does not remove the job's `progress_callbacks` entry
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/processing_engine.py:539-561`
- **Status**: NEW → #2622
- **Description**: `cancel_job()` marks the job `CANCELLED` and cancels its asyncio Task, but never removes the corresponding entry from `self.progress_callbacks`. The callback reference is only cleaned up in `cleanup_old_jobs()` (lines 589–590), which runs on the default TTL of `completed_job_ttl_hours` (24 hours). This means the callback closure — which may hold references to external objects — is retained in memory for up to 24 hours after a job is explicitly cancelled by the user.
- **Evidence**:
  ```python
  # processing_engine.py:539-561 — cancel_job() never touches progress_callbacks
  def cancel_job(self, job_id: str) -> bool:
      job = self.jobs.get(job_id)
      if not job:
          return False
      if job.status in [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]:
          job.status = ProcessingStatus.CANCELLED
          job.completed_at = datetime.now()
          task = self._tasks.get(job_id)
          if task and not task.done():
              task.cancel()
          return True
      return False
      # ↑ progress_callbacks[job_id] is never removed here

  # cleanup_old_jobs() lines 589-590 — only cleanup path
  if job_id in self.progress_callbacks:
      del self.progress_callbacks[job_id]
  ```
- **Impact**: Callback closures for cancelled jobs accumulate until the next cleanup cycle (up to 24h). Under heavy cancellation load (e.g., users repeatedly queuing and cancelling jobs), memory grows proportionally to cancellation rate × TTL. Functionally correct — the callbacks are never invoked for completed/cancelled jobs — but the cleanup is later than necessary.
- **Suggested Fix**: Add `self.progress_callbacks.pop(job_id, None)` at the end of the `if` branch in `cancel_job()`.

---

### BE-21: Fingerprint generation exception traceback logged only at DEBUG level
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:270-273`
- **Status**: NEW → #2623
- **Description**: The broad `except Exception` handler in `FingerprintGenerator.generate_fingerprint()` logs the exception message at ERROR level but logs the full traceback at DEBUG level. In production, where the effective log level is INFO, the traceback is invisible. This makes fingerprint failures extremely difficult to diagnose — the error log shows only the exception type and message, not the call chain that caused it.
- **Evidence**:
  ```python
  # fingerprint_generator.py:270-273
  except Exception as e:
      logger.error(f"Unexpected error during fingerprint generation for track {track_id}: {e}")
      import traceback
      logger.debug(traceback.format_exc())  # ← only at DEBUG; invisible in production
  ```
  Compare to correct pattern at the `RuntimeError` handler (line 268): `logger.error(f"Rust fingerprinting error for track {track_id}: {e}")` — still no traceback, but at least the error class is more informative.
- **Impact**: When fingerprinting silently fails in production, the only log line is `"Unexpected error during fingerprint generation for track N: <message>"` with no stack trace. Root-cause diagnosis requires reproducing the issue locally with DEBUG logging enabled.
- **Suggested Fix**: Replace the two-line pattern with `logger.error(f"Unexpected error during fingerprint generation for track {track_id}: {e}", exc_info=True)` — the `exc_info=True` flag attaches the traceback to the ERROR-level log line automatically.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| Semaphore not released on `TimeoutError` early return (line 474 / 673) | The `TimeoutError` branch fires when `acquire()` times out — the semaphore was never acquired, so there is nothing to release. Correct behavior. |
| Semaphore not released on processor `TimeoutError` (line 514) | Line 514 `return` is inside the outer `try` block (line 497) whose `finally` at line 635 always calls `self._stream_semaphore.release()`. Python executes `finally` on `return`. |
| `_chunk_tails.pop()` without `_chunk_tails_lock` at lines 603, 633 | These pops are in `except`/`finally` blocks with no `await` between read and write. asyncio's single-threaded event loop makes the entire sequence atomic — no other coroutine can run between non-awaited statements. |
| `asyncio.gather(_producer, _consumer)` without error handling | `_producer()` has a `finally: await queue.put(None)` that always sends the sentinel even if an exception is raised, so `_consumer()` always terminates cleanly. |
| `RateLimitMiddleware` race condition on `self._windows` | All operations on `self._windows` in `dispatch()` (lines 107-119) are synchronous (no `await`). In asyncio's cooperative concurrency model, no other coroutine can interleave between these lines. |
| `webm_streaming.py` position mismatch: `chunk_idx * chunk_duration` (line 359) vs `chunk_idx * chunk_interval` (line 445) | Default values are `chunk_duration=10` and `chunk_interval=10` (equal). `main.py` does not override these values, so the two expressions always produce the same result. No real mismatch. |
| `system.py` pause event race: old task may read old event after `_stream_pause_events[ws_id]` is overwritten | Each streaming task captures its `pause_event` object by closure at task-creation time. Overwriting `_stream_pause_events[ws_id]` at line 353 doesn't affect the old task's captured reference. External pause/resume messages route to the new event, not the old task. |
| `artists.py` `has_more = (offset + limit) < total` off-by-one | This formula is equivalent to `(offset + actual_count) < total` when the repository returns up to exactly `limit` rows. The formula is correct for a standard forward-pagination sentinel: it correctly returns `False` when `offset + limit >= total` (no further pages) and `True` otherwise. |
| `cancel_job()` sync access to `self.jobs` races with `cleanup_old_jobs()` | `cancel_job()` only mutates attributes on a `job` object (`.status`, `.completed_at`); it does not add/remove keys from `self.jobs`. `cleanup_old_jobs()` iterates `self.jobs` under `_jobs_lock`. Field writes on a job object are atomic at the Python object level and cannot cause a `RuntimeError` in dict iteration. |

## Dimension Checklist Summary

### Dimension 1: Route Handler Correctness
- [x] All handlers are `async def`
- [x] Input validation via Pydantic / Query validators (`ge`, `le`, regex)
- [x] Error responses use `HTTPException` with correct status codes
- [x] Dependency injection via `require_repository_factory()`
- [x] Idempotency of PUT/DELETE — all verified safe

### Dimension 2: WebSocket Streaming
- [x] Connection lifecycle — `accept()`/`close()` handled; resources cleaned in `finally` blocks
- [x] Binary frame format — PCM chunks consistent with frontend `AudioPlaybackEngine` expectations
- [x] Backpressure — `asyncio.Queue` between producer/consumer; `abort_event` stops producer on disconnect
- [x] Multiple clients — state is per-WebSocket task; `active_streams` keyed by `track_id`
- [x] Error during streaming — `_send_error()` with sanitized message sent before return
- [x] Message type consistency — text control + binary audio correctly discriminated

### Dimension 3: Chunked Processing
- [x] Chunk boundaries — samples aligned; `ChunkedAudioProcessor` handles boundary math
- [x] Crossfade correctness — `_chunk_tails_lock` guards crossfade state; applied per-chunk
- [x] First/last chunk — `fast_start=True` for chunk 0; last-chunk short length handled
- [x] Processing failure — chunk error logs and sends recovery position to frontend (#2085)
- [x] Concurrent chunk requests — semaphore (`MAX_CONCURRENT_STREAMS`) limits concurrent streams

### Dimension 4: Processing Engine
- [x] Engine lifecycle — `ProcessingEngine` is a singleton; per-request jobs
- [x] Async/sync boundary — CPU-bound calls wrapped in `asyncio.to_thread()` with timeouts
- [x] State management — job state protected by `_jobs_lock` (asyncio.Lock)
- [ ] **`cancel_job()` callback leak** — BE-20 (new, LOW)

### Dimension 5: Schema Consistency
- [x] All endpoints use Pydantic models for input/output
- [x] `snake_case` throughout; transformer layer handles camelCase conversion in frontend
- [x] Optional fields marked correctly; sensible defaults
- [x] Enum values used for `ProcessingStatus`, `PlaybackState`

### Dimension 6: Middleware & Configuration
- [x] CORS — explicit origin list; no wildcard with `allow_credentials=True` (#2224)
- [x] Rate limiting — `RateLimitMiddleware` added for expensive endpoints (#2575)
- [x] Security headers — `X-Frame-Options`, `X-Content-Type-Options`, CSP set
- [x] Router registration — all routers included with correct prefixes

### Dimension 7: Error Handling & Resilience
- [x] Global exception handler — `RequestValidationError` and generic `Exception` caught
- [x] WebSocket error propagation — sanitized error messages sent before close (#2608 fix)
- [x] File not found — handled with 404 `HTTPException`
- [ ] **Fingerprint traceback at DEBUG** — BE-21 (new, LOW)

### Dimension 8: Performance & Resource Management
- [x] Event loop blocking — all sync I/O via `asyncio.to_thread()` with timeouts
- [x] Connection pooling — SQLAlchemy `pool_pre_ping=True` configured
- [x] Streaming efficiency — audio streamed chunk-by-chunk, not loaded into memory
- [x] Concurrent request handling — semaphore limits concurrent streams
- [ ] **`_FINGERPRINT_WORKERS` = 0 on single-core** — BE-19 (new, LOW)
- [ ] **`progress_callbacks` not cleaned in `cancel_job()`** — BE-20 (new, LOW)

### Dimension 9: Test Coverage
- [x] Router coverage — major routers have test files
- [x] WebSocket testing — streaming connection/disconnect tested
- [x] Error scenario tests — corrupt files, missing tracks tested
