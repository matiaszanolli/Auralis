# Backend Audit — 2026-03-05

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: FastAPI backend — `auralis-web/backend/`
**Dimensions**: Route Handlers · WebSocket Streaming · Chunked Processing · Processing Engine · Schema Consistency · Middleware & Config · Error Handling · Performance · Test Coverage
**Method**: 3 parallel exploration agents (routers/middleware, streaming/processing, services/security), followed by manual verification of all candidate findings against source. Prior findings BE-19–BE-21 re-verified. 12+ false positives from agents eliminated.

## Executive Summary

The backend remains in good shape overall, with all prior low-severity findings (BE-19–BE-21) still open but tracked. This audit uncovered 4 new findings: 0 CRITICAL, 0 HIGH, 2 MEDIUM, 2 LOW. The MEDIUM findings relate to cache key correctness (ProcessorFactory using object identity instead of content hash) and a thread-safety gap in the fingerprint queue's sync `enqueue()` method.

**Results**: 4 new confirmed findings (0 CRITICAL, 0 HIGH, 2 MEDIUM, 2 LOW).

| Severity | New | Carried-over (open) | Total Open |
|----------|-----|---------------------|------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 2 | 0 | 2 |
| LOW | 2 | 3 | 5 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| BE-16: Enhancement router uses CHUNK_DURATION instead of CHUNK_INTERVAL | #2607 | **FIXED** |
| BE-17: WebSocket error handler exposes raw exception string to client | #2608 | **FIXED** |
| BE-18: Artist search joinedload causes N+1 on tracks and genres | #2609 | **FIXED** |
| BE-19: `_FINGERPRINT_WORKERS` evaluates to 0 on single-core CPU | #2621 | **OPEN** — still present at `fingerprint_generator.py:48` |
| BE-20: `cancel_job()` does not remove `progress_callbacks` entry | #2622 | **OPEN** — still present at `processing_engine.py:539-561` |
| BE-21: Fingerprint exception traceback logged only at DEBUG level | #2623 | **OPEN** — still present at `fingerprint_generator.py:270-273` |

## New Findings

---

### BE-22: ProcessorFactory._get_config_hash uses object identity instead of content hash
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processor_factory.py:98-102`
- **Status**: NEW
- **Description**: The `_get_config_hash()` method uses `str(id(config))` as the cache key component for config-based processor lookup. Python's `id()` returns the memory address of the object, which means two `UnifiedConfig` objects with identical settings produce different cache keys. This defeats the purpose of caching — every call with a fresh config object creates a new `HybridProcessor` instead of reusing the cached one.
- **Evidence**:
  ```python
  # processor_factory.py:98-102
  def _get_config_hash(self, config: Any | None) -> str:
      if config is None:
          return "default"
      # Use object id as hash (same instance = same hash)
      return str(id(config))
  ```
  Called by `get_or_create()` at line 136:
  ```python
  config_hash = self._get_config_hash(config)
  cache_key = self._get_cache_key(track_id, preset, intensity, config_hash)
  ```
  And by `get_or_create_from_config()` at line 206 which creates a new `UnifiedConfig()` each call:
  ```python
  if config is None:
      config = UnifiedConfig()  # New object → new id() → cache miss
  ```
- **Impact**: `HybridProcessor` instances accumulate in `_processor_cache` unboundedly. Each processor holds DSP state (envelope followers, gain reduction buffers). For config-based usage (CLI tools, batch processing via `process_adaptive()`/`process_reference()`/`process_hybrid()`), every call creates a new processor, negating the cache and increasing memory usage. Track-based caching (the primary streaming path) is unaffected since it uses `track_id` as the primary key.
- **Suggested Fix**: Compute a content-based hash from the config's processing-relevant attributes: `hashlib.md5(json.dumps(config.to_dict(), sort_keys=True).encode()).hexdigest()`. If `UnifiedConfig` doesn't have `to_dict()`, hash the relevant fields (`mastering_profile`, `processing_mode`, etc.).

---

### BE-23: FingerprintQueue.enqueue() is sync but accesses shared state without synchronization
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/analysis/fingerprint_queue.py:92-117`
- **Status**: NEW
- **Description**: `FingerprintQueue.enqueue()` is a synchronous method that reads and mutates shared state (`_state.queued_set`, `_state.queue`) without any lock protection. The class has an `asyncio.Lock` at line 90, but it cannot be acquired from a sync method. The docstring claims the method is "Thread-safe" but this is incorrect.
- **Evidence**:
  ```python
  # fingerprint_queue.py:92-117
  def enqueue(self, track_id: int) -> bool:
      """Thread-safe. Deduplicates (same track won't be queued twice)."""
      # RACE: check and mutate are not atomic
      if track_id in self._state.queued_set:       # READ
          return False
      if track_id == self._state.processing:        # READ
          return False
      self._state.queue.append(track_id)            # WRITE
      self._state.queued_set.add(track_id)          # WRITE
      return True
  ```
  Called from multiple async handlers concurrently:
  - `routers/library.py:525` — during library scan (may add hundreds of tracks)
  - `routers/similarity.py:118,494,559` — on fingerprint miss
  - `core/audio_stream_controller.py:411` — during stream setup
  - `services/library_auto_scanner.py:239` — during auto-scan
- **Impact**: Under concurrent library scan + stream start, the read-check-write pattern can race. Two coroutines checking `queued_set` simultaneously for the same `track_id` could both pass the check and both add the track, violating the dedup invariant. In asyncio's single-threaded model, this race requires an `await` between the check and write — which doesn't exist here, so the race is currently **unexploitable**. However, if any future refactoring adds an `await` between lines 105 and 114, or if `enqueue()` is called from a thread (e.g., `asyncio.to_thread()`), the race becomes real. The "Thread-safe" docstring is misleading and should be corrected.
- **Suggested Fix**: Either (a) make `enqueue()` async and acquire `self._lock`, or (b) replace `_lock` with `threading.Lock()` and acquire it in `enqueue()` for true thread-safety, or (c) remove the "Thread-safe" docstring claim since it relies on asyncio's implicit single-thread guarantee.

---

### BE-24: NavigationService.next_track() / previous_track() fetch state but discard result
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/services/navigation_service.py:79-86, 121-128`
- **Status**: NEW
- **Description**: Both `next_track()` and `previous_track()` call `self.player_state_manager.get_state()` but discard the return value. The state is fetched but never used or updated before broadcasting the track change event to WebSocket clients. This means the broadcast notifies clients of a track change without actually synchronizing the backend's player state.
- **Evidence**:
  ```python
  # navigation_service.py:79-86
  if self.player_state_manager and hasattr(self.audio_player, 'queue'):
      self.player_state_manager.get_state()  # ← return value discarded
      if hasattr(self.audio_player.queue, 'current_index'):
          await self.connection_manager.broadcast({
              "type": "track_changed",
              "data": {"action": "next"}
          })
  ```
  Identical pattern at lines 121-128 for `previous_track()`.
- **Impact**: The frontend receives a `track_changed` broadcast but the backend's `PlayerStateManager` is not updated with the new track info. Subsequent `GET /api/player/state` requests may return stale track metadata until the next periodic state sync. The actual player state (via `audio_player`) is correct — only the state manager's cached view is stale.
- **Suggested Fix**: Replace the unused `get_state()` call with `await self.player_state_manager.update_from_player()` or similar method that syncs the state manager with the audio player's current position/track.

---

### BE-25: ProcessingLockManager.process_sync_in_async_context() uses asyncio.Lock across event loops
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_lock_manager.py:123-134`
- **Status**: NEW
- **Description**: `process_sync_in_async_context()` submits a lambda to a `ThreadPoolExecutor` that calls `asyncio.run(self.process_async(process_fn))`. This creates a new event loop in the thread. The `self._lock` is an `asyncio.Lock` which is not thread-safe — using it from both the main event loop (via `process_async()`) and a child event loop in a thread pool simultaneously could cause undefined behavior (torn reads/writes on internal `_locked` flag and `_waiters` deque).
- **Evidence**:
  ```python
  # processing_lock_manager.py:62-66
  def __init__(self) -> None:
      self._lock = asyncio.Lock()  # Not thread-safe
      self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

  # processing_lock_manager.py:129-132
  future = self._executor.submit(
      lambda: asyncio.run(self.process_async(process_fn))  # New event loop in thread
  )
  result = future.result()  # Blocks calling thread
  ```
- **Impact**: Currently **not triggered in production**. The only caller (`get_full_processed_audio_path`) was refactored in #2318 to use `process_chunk_safe()` directly, bypassing `process_sync_in_async_context()`. The method remains as a public API with a latent bug. If any future code calls it while `process_async()` is concurrently executing on the main loop, behavior is undefined.
- **Suggested Fix**: Either (a) replace `asyncio.Lock` with `threading.Lock` + `asyncio.to_thread()` for cross-context safety, or (b) mark `process_sync_in_async_context()` as deprecated with a comment explaining the thread-safety limitation, or (c) remove the method entirely since its only caller was refactored away.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| RateLimitMiddleware race condition on `_windows` dict | All operations on `self._windows` in `dispatch()` are synchronous (no `await` between read/write). Asyncio's cooperative model prevents interleaving. Prior audit (2026-03-01) confirmed this as safe. |
| Unbounded memory in root `middleware.py` RateLimitMiddleware | The root `middleware.py` file contains a legacy version NOT used in production. `config/middleware.py` is the active version (registered in `setup_middleware()`), which has bounded eviction (#2630). |
| AudioContentPredictor cache unbounded | Cache IS bounded at line 122: `if len(self.analysis_cache) < self._cache_max_size` prevents growth beyond 100 entries. Agent finding was incorrect. |
| CORS wildcard with credentials | CORS is configured with explicit origin whitelist (10 specific localhost origins), not wildcards. Already noted as safe in prior audit. |
| WebSocket rate limiter "never called" | The `WebSocketRateLimiter` in `websocket_security.py` is a utility class. Rate limiting for WebSocket text messages is handled in `routers/system.py` via `validate_and_parse_message()`. Binary audio streaming has backpressure via bounded `asyncio.Queue` instead. |
| Chunk extraction silent padding as audio corruption | The pad/trim logic in `chunk_operations.py:224-249` is a defensive measure for floating-point rounding at chunk boundaries. Sample counts can differ by 1-2 samples due to `int(round(duration * sample_rate))` rounding. The warning log at lines 239-241 flags the anomaly. This is correct design — failing the entire stream over 1-2 samples would be worse than padding. |
| Normal audio streaming has no backpressure | Normal streaming at `audio_stream_controller.py:774` reads one chunk at a time via `asyncio.to_thread()` and immediately sends it. The `await websocket.send_bytes()` call itself provides flow control — it will block if the WebSocket send buffer is full. The enhanced path needs an explicit queue because it has a separate producer (processor) and consumer (sender). |
| Settings PUT accepts raw dict without Pydantic | Comment at `settings.py:80` confirms "whitelist enforced by SettingsRepository". The repository's `update_settings()` only applies known fields, ignoring unknown keys. This is by design. |
| NavigationService: state inconsistency from missing update | Downgraded from MEDIUM to LOW after verifying that `PlayerStateManager` has periodic sync from the player timer. The `get_state()` call is unnecessary but the stale window is seconds, not permanent. |

## Dimension Checklist Summary

### Dimension 1: Route Handler Correctness
- [x] All handlers are `async def`
- [x] Input validation via Pydantic / Query validators (`ge`, `le`)
- [x] Error responses use `HTTPException` with correct status codes
- [x] Dependency injection via factory functions in `config/routes.py`
- [x] Idempotency of PUT/DELETE — all verified safe
- [ ] **NavigationService discards state** — BE-24 (new, LOW)

### Dimension 2: WebSocket Streaming
- [x] Connection lifecycle — `accept()`/`close()` handled; resources cleaned in `finally` blocks
- [x] Binary frame format — PCM chunks consistent with frontend expectations
- [x] Backpressure — bounded `asyncio.Queue` for enhanced; `await send_bytes()` for normal
- [x] Multiple clients — per-task state via `contextvars` (fixes #2493)
- [x] Error during streaming — `_send_error()` with recovery position before return
- [x] `_chunk_tails_lock` serializes crossfade state (fixes #2326)
- [x] Semaphore properly released in `finally` blocks

### Dimension 3: Chunked Processing
- [x] Chunk boundaries — samples aligned; `ChunkBoundaryManager` handles math
- [x] Crossfade correctness — equal-power curves (sin^2/cos^2), no sample loss
- [x] First/last chunk — `fast_start=True` for chunk 0; last-chunk duration capped
- [x] Processing failure — chunk error triggers cache invalidation + recovery position
- [x] Concurrent streams — `MAX_CONCURRENT_STREAMS` semaphore (10) across all controllers

### Dimension 4: Processing Engine
- [x] Engine lifecycle — singleton `ProcessingEngine`; per-request jobs
- [x] Async/sync boundary — CPU-bound calls via `asyncio.to_thread()` with timeouts
- [ ] **ProcessorFactory cache key uses object identity** — BE-22 (new, MEDIUM)
- [ ] **ProcessingLockManager cross-loop lock** — BE-25 (new, LOW)

### Dimension 5: Schema Consistency
- [x] All endpoints use Pydantic models for input/output
- [x] `snake_case` throughout; frontend handles transformation
- [x] Optional fields marked correctly; sensible defaults
- [x] Enum values used for `WebSocketMessageType`, `ProcessingStatus`
- [x] Generic wrappers (`SuccessResponse[T]`, `PaginatedResponse[T]`) for consistency

### Dimension 6: Middleware & Configuration
- [x] CORS — explicit origin list; no wildcard with credentials (#2224)
- [x] Rate limiting — path-based `RateLimitMiddleware` with eviction (#2575, #2630)
- [x] Security headers — `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`
- [x] Router registration — all routers via `setup_routers()` in `config/routes.py`
- [x] Lifespan — proper startup/shutdown via `create_lifespan()` in `config/startup.py`

### Dimension 7: Error Handling & Resilience
- [x] Global exception handler — `RequestValidationError` and generic `Exception` caught
- [x] WebSocket error propagation — sanitized messages sent before close
- [x] File not found — handled with 404 `HTTPException`
- [x] Recovery — chunk failure sends recovery position to client (#2085)
- [x] Path traversal — `validate_file_path()` / `validate_scan_path()` in `security/path_security.py`

### Dimension 8: Performance & Resource Management
- [x] Event loop blocking — all sync I/O via `asyncio.to_thread()` with timeouts
- [x] Connection pooling — SQLAlchemy `pool_pre_ping=True` configured
- [x] Streaming efficiency — chunk-by-chunk loading, no full-file allocation (#2121)
- [x] Concurrent request handling — semaphore limits concurrent streams
- [ ] **FingerprintQueue.enqueue() misleading thread-safety claim** — BE-23 (new, MEDIUM)

### Dimension 9: Test Coverage
- [x] Router coverage — 14/15 routers have dedicated test files (settings.py lacks tests)
- [x] WebSocket testing — `test_websocket_protocol_b3.py`, `test_websocket_task_cleanup.py`
- [x] Chunked processing — boundary, crossfade, and edge cases tested
- [x] Schema validation — invalid payloads tested for rejection
- [x] Error scenarios — corrupt files, missing tracks, timeouts tested
- [x] Security — path traversal, artwork SSRF, file upload magic bytes tested
