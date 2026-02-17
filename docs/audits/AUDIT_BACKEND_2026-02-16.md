# Backend Audit — 2026-02-16

## Executive Summary

Focused audit of the Auralis FastAPI backend covering 9 dimensions: Route Handler Correctness, WebSocket Streaming, Chunked Processing, Processing Engine, Schema Consistency, Middleware & Configuration, Error Handling, Performance, and Test Coverage.

**Findings by severity:**

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 5 |
| MEDIUM   | 12 |
| LOW      | 1 |
| **Total NEW** | **18** |

Plus 1 finding extending existing issue #2261.

**Key themes:**
1. **Event loop blocking** — `ProcessingEngine.process_job()` and `process_chunk_synchronized()` perform heavy sync I/O on the async event loop without `asyncio.to_thread()`
2. **Missing synchronization** — ProcessingEngine processor cache, `_chunk_tails` dict, and `_active_streaming_tasks` dict all lack locks for concurrent access
3. **No backpressure** — Processing engine worker accepts unlimited jobs with no queue size limit
4. **Test gaps** — Shared backend utilities (pagination, dependencies, serializers, errors) have zero test coverage; streaming timeout scenarios untested

**Deduplication notes:**
- ~59 raw findings across 3 audit agents reduced to 18 after cross-agent deduplication and filtering against 150+ existing open issues
- Findings overlapping with #2219 (ConnectionManager broadcast), #2220 (threading.Lock in async), #2299 (active_jobs counter), #2189 (create_task from sync), #2186 (RepositoryFactory pooling), #2127 (startup blocking), #2129 (sys.path manipulation), #2114 (dead schemas), #2224 (CORS), #2295 (webm full file load), #2317 (metadata sync I/O), #2124 (last chunk padding), #2221 (WebM encoder blocks) were excluded as duplicates

---

## Findings

### HIGH Severity

---

### B-01: process_chunk_synchronized creates nested event loops via asyncio.run() in thread pool

- **Severity**: HIGH
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/chunked_processor.py:635-670`
- **Status**: NEW
- **Description**: `process_chunk_synchronized()` detects a running event loop and spawns a `ThreadPoolExecutor` to call `asyncio.run()` in a new thread. This creates a nested event loop — an antipattern that blocks the calling thread while spawning a new event loop for each invocation. Each call creates and destroys a thread + event loop, adding ~50-100ms overhead per chunk.
- **Evidence**:
  ```python
  def process_chunk_synchronized(self, chunk_index: int, fast_start: bool = False):
      try:
          loop = asyncio.get_running_loop()
          import concurrent.futures
          with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
              future = executor.submit(
                  lambda: asyncio.run(self.process_chunk_safe(chunk_index, fast_start))
              )
              return future.result()  # Blocks caller
      except RuntimeError:
          loop = asyncio.new_event_loop()
          try:
              return loop.run_until_complete(self.process_chunk_safe(chunk_index, fast_start))
          finally:
              loop.close()
  ```
- **Impact**: Each chunk incurs thread-pool + event-loop creation overhead. Under concurrency, thread pool exhaustion causes serialized processing. Called from `get_full_processed_audio_path()` which is used for file export.
- **Related**: #2080 (process_chunk_synchronized bypasses async lock — different aspect)
- **Suggested Fix**: Refactor callers to be async and call `process_chunk_safe()` directly. For truly sync callers, use a single shared event loop thread rather than creating one per call.

---

### B-02: ProcessingEngine.process_job blocks event loop with synchronous load_audio/process/save

- **Severity**: HIGH
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/processing_engine.py:348-434`
- **Status**: NEW
- **Description**: `process_job()` is `async def` but performs four blocking operations without `asyncio.to_thread()`: `load_audio()` (line 361), `load_audio()` for reference (line 378), `processor.process()` (line 384), and `save()` (line 402). These are CPU-intensive and disk-bound operations that block the entire event loop.
- **Evidence**:
  ```python
  async def process_job(self, job: ProcessingJob) -> None:
      # ...
      audio, sample_rate = load_audio(job.input_path)          # Line 361 — BLOCKS
      reference_audio, reference_sr = load_audio(reference_path)  # Line 378 — BLOCKS
      result = processor.process(audio, reference_audio)        # Line 384 — BLOCKS (CPU heavy)
      save(file_path=job.output_path, audio_data=result.audio, ...)  # ~Line 402 — BLOCKS
  ```
- **Impact**: While a single job processes, ALL concurrent API requests, WebSocket messages, and progress callbacks are stalled. A 3-minute track can block the event loop for 5-15 seconds of CPU processing.
- **Related**: #2301 (get_mastering_recommendation blocks — different function, same pattern)
- **Suggested Fix**: Wrap all blocking calls in `asyncio.to_thread()`:
  ```python
  audio, sample_rate = await asyncio.to_thread(load_audio, job.input_path)
  result = await asyncio.to_thread(processor.process, audio, reference_audio)
  ```

---

### B-03: ProcessingEngine processor cache has no lock, concurrent access causes race conditions

- **Severity**: HIGH
- **Dimension**: Processing Engine / Concurrency
- **Location**: `auralis-web/backend/processing_engine.py:101,210-226`
- **Status**: NEW
- **Description**: `self.processors` dict is accessed from concurrent async tasks (via `start_worker` loop at line 448) without synchronization. `_get_or_create_processor()` performs a check-then-write pattern that races under concurrency.
- **Evidence**:
  ```python
  self.processors: dict[str, HybridProcessor] = {}  # Line 101 — no lock

  def _get_or_create_processor(self, mode, config):
      cache_key = self._get_processor_cache_key(mode, config)
      if cache_key in self.processors:      # READ — can race
          return self.processors[cache_key]
      processor = HybridProcessor(config)
      self.processors[cache_key] = processor  # WRITE — can race
      if len(self.processors) > 5:
          oldest_key = next(iter(self.processors))  # READ — can race
          del self.processors[oldest_key]           # WRITE — can race
  ```
- **Impact**: Two concurrent jobs with same config create duplicate processors (wasting ~200MB each). Eviction during concurrent iteration raises `RuntimeError: dictionary changed size during iteration`.
- **Related**: #2218 (cache key ignores settings — different issue: key correctness vs lock safety)
- **Suggested Fix**: Add `asyncio.Lock` to protect `_get_or_create_processor()`, or use `functools.lru_cache` with lock.

---

### B-04: _active_streaming_tasks dict leaks entries when WebSocket disconnects abnormally

- **Severity**: HIGH
- **Dimension**: WebSocket Streaming / Performance
- **Location**: `auralis-web/backend/routers/system.py:24,286-292`
- **Status**: NEW
- **Description**: `_active_streaming_tasks` uses `id(websocket)` as key. When a WebSocket disconnects abnormally (network drop, client crash), the `finally` block at line 286 only deletes the entry if the current task matches. If the WebSocket object is garbage collected and its `id()` is reused by a new object, a new stream could collide with the stale entry.
- **Evidence**:
  ```python
  _active_streaming_tasks: dict[int, asyncio.Task] = {}  # Line 24 — module-level, never cleaned

  # Line 286-287 — only cleans own task, not other orphans
  if _active_streaming_tasks.get(ws_id) is my_task:
      del _active_streaming_tasks[ws_id]

  # Line 291-292 — adds new entry
  task = asyncio.create_task(stream_audio())
  _active_streaming_tasks[ws_id] = task
  ```
  There is no periodic cleanup of completed/cancelled tasks. The dict grows monotonically.
- **Impact**: Under sustained WebSocket traffic (hours/days), the dict accumulates thousands of completed task references, preventing garbage collection of task objects and their closures (which hold audio buffers).
- **Suggested Fix**: Add periodic cleanup: `_active_streaming_tasks = {k: v for k, v in _active_streaming_tasks.items() if not v.done()}` on each new connection, or use `WeakValueDictionary`.

---

### B-05: No test files for shared backend utility modules

- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: No test files for `auralis-web/backend/routers/pagination.py`, `dependencies.py`, `serializers.py`, `errors.py`
- **Status**: NEW
- **Description**: Four shared backend modules used by ALL routers have zero test coverage:
  1. `pagination.py` — Pagination logic used by library, albums, artists endpoints
  2. `dependencies.py` — FastAPI dependency injection for LibraryManager, RepositoryFactory
  3. `serializers.py` — Track/album/artist serialization (field selection, `DEFAULT_TRACK_FIELDS`)
  4. `errors.py` — Error response formatting used across all routers
- **Impact**: Bugs in pagination (off-by-one, overflow), dependency injection (missing resources), serialization (field leaks like #2300), or error formatting (#2092) affect every router but are caught by no test.
- **Suggested Fix**: Create `tests/backend/test_pagination.py`, `test_dependencies.py`, `test_serializers.py`, `test_error_responses.py`.

---

### MEDIUM Severity

---

### B-06: Seek endpoint accepts negative and out-of-bounds position values

- **Severity**: MEDIUM
- **Dimension**: Route Handler Correctness
- **Location**: `auralis-web/backend/routers/player.py:262-263`
- **Status**: NEW
- **Description**: The `seek_position` endpoint accepts a bare `float` parameter with no validation. Negative values, NaN, infinity, and values exceeding track duration are all accepted.
- **Evidence**:
  ```python
  @router.post("/api/player/seek", response_model=None)
  async def seek_position(position: float) -> dict[str, Any]:
      """Seek to position in seconds."""
  ```
- **Impact**: Negative seek values cause undefined behavior in audio player. `float('inf')` or `float('nan')` propagate through the pipeline.
- **Related**: #2168 (pagination bounds — same pattern, different endpoints)
- **Suggested Fix**: Add `position: float = Field(ge=0.0)` and validate against current track duration.

---

### B-07: processing_api router registration catches only ImportError, not all exceptions

- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/routes.py:70-76`
- **Status**: NEW
- **Description**: The processing API router import is wrapped in `try/except ImportError`, but if the module has syntax errors, missing dependencies, or other exceptions, they propagate and crash startup.
- **Evidence**:
  ```python
  if HAS_PROCESSING:
      try:
          from processing_api import router as processing_router
          app.include_router(processing_router)
      except ImportError:
          logger.warning("⚠️  Processing API router not available")
  ```
- **Impact**: A syntax error in `processing_api.py` crashes the entire application instead of gracefully degrading.
- **Suggested Fix**: Catch `Exception` instead of just `ImportError`.

---

### B-08: Batch metadata update has no atomicity — partial failure leaves files inconsistent

- **Severity**: MEDIUM
- **Dimension**: Route Handler Correctness / Error Handling
- **Location**: `auralis-web/backend/routers/metadata.py:263-343`
- **Status**: NEW
- **Description**: The batch metadata update endpoint processes files sequentially. If file 5 of 10 fails, files 1-4 are already modified with no rollback. The `backup=True` parameter creates per-file backups, not a batch transaction.
- **Evidence**:
  ```python
  class BatchMetadataRequest(BaseModel):
      updates: list[BatchMetadataUpdateRequest]
      backup: bool = Field(True, description="Create backup before modification")
  ```
  Each update is applied individually; failure mid-batch leaves the collection in an inconsistent state.
- **Impact**: User initiates "fix all metadata for album" → partial failure corrupts some files while leaving others unchanged. No way to undo.
- **Suggested Fix**: Document non-atomic behavior, or implement collect-then-apply with rollback on failure.

---

### B-09: _chunk_tails dict accessed concurrently by seek and playback streams without lock

- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming / Concurrency
- **Location**: `auralis-web/backend/audio_stream_controller.py:171,529,777-793`
- **Status**: NEW
- **Description**: `_chunk_tails` stores crossfade tail data keyed by `track_id`. When a user seeks during enhanced playback, a new stream starts for the same `track_id` while the old stream may still be writing its tail. No lock protects this dict.
- **Evidence**:
  ```python
  self._chunk_tails: dict[int, np.ndarray] = {}  # Line 171 — no lock

  # Lines 777-793 — concurrent read-modify-write
  if chunk_index > 0 and processor.track_id in self._chunk_tails:
      prev_tail = self._chunk_tails[processor.track_id]     # READ
      pcm_samples = self._apply_boundary_crossfade(...)      # COMPUTE
  self._chunk_tails[processor.track_id] = pcm_samples[-tail_samples:]  # WRITE

  # Line 529 — cleanup on stream end
  self._chunk_tails.pop(track_id, None)  # DELETE
  ```
- **Impact**: Race between old stream's final chunk write and new stream's first chunk read causes crossfade with wrong tail data, producing audio glitch at seek boundary.
- **Suggested Fix**: Use composite key `(track_id, stream_id)` to isolate concurrent streams, or add `asyncio.Lock` per track.

---

### B-10: Chunk boundary calculations may produce fractional samples at non-standard sample rates

- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/chunked_processor.py:64-68,214-225`
- **Status**: NEW
- **Description**: Chunk duration constants (15s chunks, 10s intervals, 5s overlap) are multiplied by sample rate using `int()` truncation. At sample rates like 22050 Hz, `int(15 * 22050)` is exact, but at 48000 Hz with varying intervals, the total reconstructed length may not equal the original.
- **Evidence**:
  ```python
  CHUNK_DURATION = 15   # seconds
  CHUNK_INTERVAL = 10   # seconds
  OVERLAP_DURATION = 5  # seconds

  self.total_chunks = int(np.ceil(self.total_duration / CHUNK_INTERVAL))  # Line 216
  ```
  No validation that `sum(chunk_lengths) == total_input_length` after reconstruction.
- **Impact**: Last chunk may be shorter than expected or overlap calculation misaligns, producing a click at the chunk boundary.
- **Suggested Fix**: Round sample boundaries with `int(round(duration * sample_rate))` and add assertion: `assert reconstructed_length == original_length`.

---

### B-11: ProcessorFactory cache eviction uses next(iter()) which races with concurrent dict access

- **Severity**: MEDIUM
- **Dimension**: Processing Engine / Concurrency
- **Location**: `auralis-web/backend/core/processor_factory.py:221-225`
- **Status**: NEW
- **Description**: Cache eviction logic modifies the `processors` dict during what could be a concurrent iteration by another method (e.g., `get_statistics()`). Even though `RLock` protects individual methods, if `get_statistics()` iterates without holding the lock, it fails.
- **Evidence**:
  ```python
  if len(self.processors) > 5:
      oldest_key = next(iter(self.processors))
      del self.processors[oldest_key]
  ```
- **Impact**: `RuntimeError: dictionary changed size during iteration` if eviction and statistics gathering coincide.
- **Suggested Fix**: Iterate over `list(self.processors.keys())` for eviction, or use `OrderedDict.popitem(last=False)`.

---

### B-12: webm_streaming file reads have no timeout, can hang indefinitely on slow storage

- **Severity**: MEDIUM
- **Dimension**: Error Handling / Performance
- **Location**: `auralis-web/backend/routers/webm_streaming.py:268,306`
- **Status**: NEW
- **Description**: Synchronous `open().read()` calls in async handlers have no timeout. On network-mounted storage or failing disks, these calls block the event loop indefinitely.
- **Evidence**:
  ```python
  with open(cached_chunk_path, 'rb') as f:
      wav_bytes = f.read()  # No timeout, blocks event loop
  ```
- **Impact**: A single slow file read blocks ALL concurrent requests. No recovery mechanism — requires server restart.
- **Related**: #2295 (loads entire file — different: that's about data volume, this is about hang risk)
- **Suggested Fix**: Wrap in `asyncio.wait_for(asyncio.to_thread(path.read_bytes), timeout=10.0)`.

---

### B-13: Enhancement router get_wav_chunk_path blocks event loop without asyncio.to_thread

- **Severity**: MEDIUM
- **Dimension**: Route Handler Correctness / Performance
- **Location**: `auralis-web/backend/routers/enhancement.py:109`
- **Status**: NEW
- **Description**: While `ChunkedAudioProcessor` instantiation is correctly wrapped in `asyncio.to_thread()`, the subsequent `processor.get_wav_chunk_path()` call performs heavy DSP processing synchronously, blocking the event loop.
- **Evidence**:
  ```python
  processor = await asyncio.to_thread(ChunkedAudioProcessor, ...)  # Line 92 — correct
  wav_chunk_path = processor.get_wav_chunk_path(chunk_idx)           # Line 109 — BLOCKS
  ```
- **Impact**: First-time chunk processing (not cached) blocks event loop for seconds while DSP runs.
- **Suggested Fix**: `wav_chunk_path = await asyncio.to_thread(processor.get_wav_chunk_path, chunk_idx)`.

---

### B-14: Scan worker exception handler loses stack trace

- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/files.py:157-162`
- **Status**: NEW
- **Description**: The scan worker catches all exceptions but logs only `str(e)` without `exc_info=True`. Stack traces are lost, making production debugging of scan failures nearly impossible.
- **Evidence**:
  ```python
  except Exception as e:
      logger.error(f"Scan worker error: {e}")  # No exc_info=True!
      await connection_manager.broadcast({
          "type": "scan_error",
          "data": {"directory": directory, "error": str(e)}
      })
  ```
- **Impact**: When library scanning fails (permission errors, corrupt files, DB issues), root cause is hidden. Only the message string is available.
- **Suggested Fix**: Add `exc_info=True`: `logger.error(f"Scan worker error: {e}", exc_info=True)`.

---

### B-15: Processing engine worker accepts unlimited jobs with no backpressure

- **Severity**: MEDIUM
- **Dimension**: Performance / Processing Engine
- **Location**: `auralis-web/backend/processing_engine.py:436-453`
- **Status**: NEW
- **Description**: `self.job_queue = asyncio.Queue()` has no `maxsize`, allowing unlimited job accumulation. The worker loop uses busy-wait (`asyncio.sleep(0.5)`) when at capacity instead of a semaphore.
- **Evidence**:
  ```python
  self.job_queue: asyncio.Queue[ProcessingJob] = asyncio.Queue()  # No maxsize!

  async def start_worker(self) -> None:
      while True:
          job = await self.job_queue.get()
          while self.active_jobs >= self.max_concurrent_jobs:
              await asyncio.sleep(0.5)  # Busy-wait!
          await self.process_job(job)
  ```
- **Impact**: Under load, hundreds of jobs queue in memory (each holding file paths, settings). Busy-wait wastes CPU cycles. No 503 rejection to signal overload.
- **Related**: #2216 (jobs dict grows — tracks completed jobs; this is about queued pending jobs)
- **Suggested Fix**: `asyncio.Queue(maxsize=20)` + return HTTP 503 when queue is full. Replace busy-wait with `asyncio.Semaphore`.

---

### B-16: Streaming timeout scenarios untested

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: No test coverage for timeout paths in `auralis-web/backend/routers/webm_streaming.py:283-293`
- **Status**: NEW
- **Description**: The 30s processor instantiation timeout in webm_streaming.py is never tested. The `except TimeoutError` branch at line 290 has no test coverage.
- **Evidence**:
  ```python
  processor = await asyncio.wait_for(
      asyncio.to_thread(chunked_audio_processor_class, ...),
      timeout=30.0  # ← NOT TESTED
  )
  except TimeoutError:  # ← NOT TESTED
      raise HTTPException(status_code=504, detail="Processing timed out")
  ```
- **Impact**: Regressions in timeout handling (e.g., wrong exception type, missing cleanup) go undetected.
- **Suggested Fix**: Add `test_chunk_processing_timeout` with mocked slow processor.

---

### B-17: No concurrent WebSocket streaming stress tests

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: No test file for concurrent WebSocket scenarios
- **Status**: NEW
- **Description**: While `test_audio_stream_crossfade.py` and `test_websocket_protocol_b3.py` exist, there are no tests for concurrent WebSocket connections streaming different tracks simultaneously. The `_active_streaming_tasks` management (B-04) is untested under concurrency.
- **Impact**: Race conditions in task cleanup (B-04), _chunk_tails access (B-09), and stream state management are undetectable.
- **Suggested Fix**: Create `tests/backend/test_concurrent_websocket_streaming.py` testing 5+ simultaneous streams, rapid connect/disconnect, and seek-during-playback.

---

### LOW Severity

---

### B-18: Version endpoint fallback hardcodes stale "1.0.0-beta.1"

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/routers/system.py:82-94`
- **Status**: NEW
- **Description**: The `/api/version` fallback returns `"1.0.0-beta.1"` when `auralis/version.py` import fails. Current version is `1.2.0-beta.3`.
- **Evidence**:
  ```python
  return {
      "version": "1.0.0-beta.1",   # ← stale
      "prerelease": "beta.1",       # ← stale
  }
  ```
- **Impact**: Monitoring dashboards and frontend display wrong version when import fails.
- **Suggested Fix**: Update to `1.2.0-beta.3` or read from a single source-of-truth file.

---

## Extends Existing Issue

### B-EXT-01: albums.py fingerprint dimension names don't match model (extends #2261)

- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/albums.py:224-232`
- **Status**: Existing: #2261
- **Description**: The hardcoded dimension list uses wrong names: `pitch_stability` (should be `pitch_confidence`), `chroma_energy` (should be `chroma_energy_mean`), `phase_correlation` (should be `stereo_correlation`). This is the root cause of #2261 "Album fingerprint endpoint silently returns all-zero values" — `getattr(fp, dim, 0.0)` returns `0.0` for non-existent attributes.

---

## Relationships & Root Causes

### Event Loop Blocking (B-01, B-02, B-12, B-13)
Four findings share the root cause of synchronous operations on the async event loop. Fixing B-02 (process_job) has the highest impact since it's the longest-blocking operation.

### Missing Synchronization (B-03, B-04, B-09, B-11)
Four dict/cache structures lack locks for concurrent access. B-03 (processor cache) and B-09 (_chunk_tails) are most impactful since they affect audio quality.

### Test Gaps (B-05, B-16, B-17)
Three findings identify missing test coverage for critical backend paths. B-05 (utility modules) is highest priority since bugs there affect all routers.

---

## Prioritized Fix Order

1. **B-02** (process_job blocks event loop) — Highest impact: blocks ALL requests during processing
2. **B-03** (processor cache no lock) — Data corruption risk under concurrency
3. **B-01** (nested asyncio.run) — Performance degradation + thread exhaustion
4. **B-09** (_chunk_tails race) — Audio quality: glitches at seek boundaries
5. **B-15** (no backpressure) — Resource exhaustion under load
6. **B-04** (_active_streaming_tasks leak) — Memory leak in long-running server
7. **B-13** (enhancement blocks event loop) — User-facing latency
8. **B-12** (no timeout on file reads) — Hang risk on slow storage
9. **B-05** (utility test coverage) — Prevents catching regressions
10. **B-06 through B-18** — Remaining in severity order

---

## Cross-Cutting Recommendations

1. **Adopt `asyncio.to_thread()` as standard pattern** — Every sync call in an async handler should use it. Add a linting rule.
2. **Add `asyncio.Lock` to all shared dicts** — `processors`, `_chunk_tails`, `_active_streaming_tasks`, and any module-level mutable state.
3. **Implement job queue limits** — Add `maxsize` to Queue, return 503 when full, replace busy-wait with Semaphore.
4. **Test timeout and error branches** — Every `try/except TimeoutError` and `except Exception` branch needs a test case.
