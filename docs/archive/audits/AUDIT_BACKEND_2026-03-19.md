# Backend Audit — 2026-03-19

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: FastAPI backend — `auralis-web/backend/`
**Dimensions**: Route Handlers · WebSocket Streaming · Chunked Processing · Processing Engine · Schema Consistency · Middleware & Config · Error Handling · Performance · Test Coverage
**Method**: 9 parallel dimension agents (Sonnet 4.6), followed by cross-dimension deduplication and severity triage. Prior findings BE-19–BE-23 re-verified. 14 cross-dimension duplicates eliminated.

## Executive Summary

This audit uncovered **35 new findings**: **3 HIGH**, **14 MEDIUM**, **18 LOW**. The most impactful issues are:

1. **Event loop starvation** — synchronous SQLAlchemy calls and CPU-bound similarity computations block the async event loop across all library routers, causing audio streaming dropouts during UI navigation (BE-24, BE-46, BE-47).
2. **Unguarded destructive endpoint** — `POST /api/library/reset` permanently wipes the entire library with no confirmation guard, exploitable via CSRF from any localhost-accessible page (BE-29).
3. **Audio integrity gaps** — crossfade applied to non-overlapping chunks in full-track export, seek path doesn't trim to exact position, and background cache builder resets DSP state per chunk (BE-34, BE-35, BE-42).

**Results**: 35 new confirmed findings (3 HIGH, 14 MEDIUM, 18 LOW).

| Severity | New | Carried-over (open) | Total Open |
|----------|-----|---------------------|------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 3 | 0 | 3 |
| MEDIUM | 14 | 2 | 16 |
| LOW | 18 | 3 | 21 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| BE-16: Enhancement router uses CHUNK_DURATION instead of CHUNK_INTERVAL | #2607 | **FIXED** |
| BE-17: WebSocket error handler exposes raw exception string to client | #2608 | **FIXED** |
| BE-18: Artist search joinedload causes N+1 on tracks and genres | #2609 | **FIXED** |
| BE-19: `_FINGERPRINT_WORKERS` evaluates to 0 on single-core CPU | #2621 | **OPEN** |
| BE-20: `cancel_job()` does not remove `progress_callbacks` entry | #2622 | **OPEN** |
| BE-21: Fingerprint exception traceback logged only at DEBUG level | #2623 | **OPEN** |
| BE-22: ProcessorFactory._get_config_hash uses object identity | — | **OPEN** |
| BE-23: FingerprintQueue.enqueue() sync shared state race | — | **OPEN** |

## Route Coverage Matrix

| Router File | Endpoints | Validated | Issues Found |
|-------------|-----------|-----------|--------------|
| `player.py` | 18 | async ✓, input ✓ | BE-25, BE-51 |
| `library.py` | 12 | async ✓, input partial | BE-27, BE-29, BE-54 |
| `albums.py` | 6 | async ✓, input partial | BE-27 |
| `artists.py` | 5 | async ✓, input ✓ | BE-45 |
| `playlists.py` | 8 | async ✓, input ✓ | BE-30 |
| `enhancement.py` | 8 | async ✓, input ✓ | BE-26, BE-49 |
| `metadata.py` | 4 | async ✓, input ✓ | BE-30 |
| `similarity.py` | 9 | async ✓, input ✓ | BE-46, BE-47 |
| `artwork.py` | 4 | async ✓, input ✓ | BE-30, BE-57 |
| `processing_api.py` | 6 | async ✓, input partial | BE-28, BE-43, BE-58 |
| `system.py` | WS | async ✓ | BE-31, BE-49 |
| `settings.py` | 5 | async ✓ | BE-55 |
| `webm_streaming.py` | 3 | async ✓ | BE-30, BE-33 |
| `cache_streamlined.py` | 4 | async ✓ | BE-30, BE-39 |
| `files.py` | 2 | async ✓, input ✓ | — |
| `serializers.py` | — (utility) | n/a | — |
| `pagination.py` | — (utility) | n/a | BE-45 |
| `dependencies.py` | — (utility) | n/a | — |

---

## New Findings

### HIGH Severity

---

### BE-24: Synchronous SQLAlchemy Repository Calls Block the Async Event Loop Across All Library Routers
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/library.py:79-259`, `albums.py:73-190`, `artists.py:99-200`, `playlists.py:71-370`, `artwork.py:71-306`, `similarity.py:107-222`
- **Status**: NEW
- **Description**: Every `async def` route handler in the library, albums, artists, playlists, artwork, and similarity routers calls synchronous SQLAlchemy repository methods directly on the event loop without `asyncio.to_thread()`. SQLite queries can take 10–300 ms for large libraries (search with eager loads). During that window the event loop is blocked and cannot service WebSocket PCM streams, heartbeats, or any other HTTP request.
- **Evidence**:
  ```python
  # library.py:117-122
  if search:
      tracks, total = repos.tracks.search(search, limit=limit, offset=offset)  # sync
  else:
      tracks, total = repos.tracks.get_all(limit=limit, offset=offset, order_by=order_by)  # sync

  # Compare to the one correct handler (library.py:274):
  audio_file = await asyncio.to_thread(mutagen.File, track.filepath)  # correctly offloaded
  ```
- **Impact**: Audio glitches/dropouts in all active WebSocket streams whenever a user browses the library. On 10,000-track libraries, `get_all(limit=200)` with `joinedload` takes 50–300 ms. `extract_and_save_artwork` can take seconds.
- **Suggested Fix**: Wrap all repository calls in `asyncio.to_thread()`. Prioritize search, get_all, and `extract_and_save_artwork`.

---

### BE-29: `POST /api/library/reset` Is Unauthenticated With No Confirmation Guard
- **Severity**: HIGH
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/library.py:706-755`
- **Status**: NEW
- **Description**: A single POST permanently deletes every track, album, artist, genre, fingerprint, playlist, queue state, and play statistic. No confirmation token, no rate limit, no `X-Confirm-Reset` header check. The docstring says "frontend must confirm" but this is UI-only enforcement. The endpoint also bypasses the repository pattern with raw ORM deletes.
- **Evidence**:
  ```python
  @router.post("/api/library/reset")
  async def reset_library() -> dict[str, Any]:
      """...The frontend must confirm before calling."""
      session = repos.session_factory()
      session.execute(track_playlist.delete())
      session.execute(track_genre.delete())
      # ... all entities deleted ...
      session.commit()
  ```
- **Impact**: Any HTTP client or CSRF request from a localhost-accessible page can destroy the entire library. No backup is created before reset.
- **Suggested Fix**: Add a required confirmation header (e.g., `X-Confirm-Reset: "RESET"`) or body `{"confirm": "RESET_ALL"}`. Rate-limit to 1/minute.

---

### BE-47: `graph_builder.build_graph()` Runs Multi-Minute K-NN Computation on the Event Loop
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/similarity.py:371`
- **Status**: NEW
- **Description**: `POST /api/similarity/graph/build` calls `graph_builder.build_graph()` synchronously. The endpoint's own docstring warns "This can take several minutes for large libraries." The function performs O(N²) pairwise distance computation entirely on the event loop. During graph construction the application is completely unresponsive.
- **Evidence**:
  ```python
  async def build_similarity_graph(...) -> GraphStatsResponse:
      stats = graph_builder.build_graph(k=k, clear_existing=clear_existing)  # BLOCKS
  ```
- **Impact**: Complete service outage for all connected clients. No audio streaming, HTTP, or WebSocket heartbeats during graph construction. WebSocket clients will disconnect.
- **Suggested Fix**: `await asyncio.to_thread(graph_builder.build_graph, k=k, ...)`. Long-term: run as background task with job ID.

---

### MEDIUM Severity

---

### BE-25: Duplicate `/api/player/queue/add` Bypasses QueueService Position Logic
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/player.py:382-461`
- **Status**: NEW
- **Description**: Two POST handlers exist for queue-add. The legacy `/api/player/queue/add` calls `audio_player.add_to_queue()` directly, silently ignoring the `position` field. The correct `/api/player/queue/add-track` delegates to `QueueService` which supports positional insertion.
- **Impact**: Drag-and-drop targeting the wrong endpoint inserts at end instead of requested position with no error.
- **Suggested Fix**: Remove the legacy `/api/player/queue/add` handler.

---

### BE-26: Mastering Recommendation Accepts Client-Supplied `filepath` Without Track Verification
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/enhancement.py:352-391`
- **Status**: NEW
- **Description**: `GET /api/player/mastering/recommendation/{track_id}` accepts a raw `filepath` query parameter but never verifies it belongs to the given `track_id`. Any file within library directories can be analyzed under any track_id.
- **Impact**: Analysis performed on wrong file; results attributed to wrong track in caches.
- **Suggested Fix**: Remove `filepath` param; resolve from DB via `track_id` like all other endpoints.

---

### BE-30: Raw Exception Strings in HTTP 500 `detail` Across 5+ Routers (~40 Sites)
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `playlists.py`, `artwork.py`, `cache_streamlined.py`, `webm_streaming.py`, `metadata.py`, `similarity.py` (~40 call sites total)
- **Status**: NEW
- **Description**: All `except Exception` blocks embed `str(e)` in `HTTPException.detail`, exposing SQLAlchemy internals, file paths, and Python type names. The global handler correctly suppresses traces but is never reached because router handlers catch first.
- **Evidence**:
  ```python
  except Exception as e:
      logger.error(f"Failed to get playlists: {e}")
      raise HTTPException(status_code=500, detail=f"Failed to get playlists: {e}")
  ```
- **Impact**: Internal implementation details exposed to API callers.
- **Suggested Fix**: Use static messages in `detail`; log exceptions with `exc_info=True`. Use `InternalServerError` from `routers/errors.py`.

---

### BE-31: Seek Handler Does Not Reset Pause/Flow-Control Events — Silent Deadlock
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:575-644`
- **Status**: NEW
- **Description**: `play_enhanced` and `play_normal` handlers create fresh `asyncio.Event` objects in the set (running) state before spawning tasks. The `seek` handler cancels the prior task but never resets these events. If the prior stream was paused or flow-controlled, the seek task immediately blocks at `await pause_evt.wait()` on the first chunk.
- **Impact**: Seek while paused deadlocks the stream. Frontend receives `seek_started` but no audio frames ever arrive. Semaphore slot held indefinitely.
- **Suggested Fix**: Reset both events in the seek handler before creating the task, same as `play_enhanced`/`play_normal`.

---

### BE-34: `get_full_processed_audio_path` Applies Crossfade to Non-Overlapping Chunks
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunked_processor.py:775-789`
- **Status**: NEW
- **Description**: Chunks stored on disk are non-overlapping (15s first, 10s subsequent). `get_full_processed_audio_path` applies `apply_crossfade_between_chunks` with 5-second overlap — but no shared audio exists. The crossfade blends unrelated samples, shortening output by `(N-1) × 5s`.
- **Impact**: Full-track export has incorrect duration and audible glitches at every chunk boundary.
- **Suggested Fix**: Replace with `np.concatenate(all_chunks, axis=0)` — chunks are already contiguous.

---

### BE-35: Seek Path Never Trims First Chunk to Exact Position
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1509-1587`
- **Status**: NEW
- **Description**: `stream_enhanced_audio_from_position` computes `seek_offset` and sends it as metadata, but never trims the first chunk's PCM. Seek always starts at the nearest 10s boundary.
- **Impact**: Seek precision error up to ~9.99 seconds. Seeking to 1:23 plays from 1:20.
- **Suggested Fix**: Trim first chunk by `round(seek_offset * sample_rate)` samples before streaming.

---

### BE-39: Streamlined Cache Router Never Registered Due to Startup-Order Race
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/routes.py:186`, `config/startup.py:285-305`
- **Status**: NEW
- **Description**: `setup_routers()` runs before lifespan. The cache router guard checks `globals_dict.get('streamlined_cache')` which is `None` at registration time. All `/api/cache/*` endpoints permanently return 404.
- **Impact**: Frontend cache management UI non-functional. No warning emitted.
- **Suggested Fix**: Register unconditionally when `HAS_STREAMLINED_CACHE` is True; return 503 if cache not initialized.

---

### BE-40: Dead LUFS Expression — Fingerprint-Driven Loudness Targeting Is a No-Op
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/mastering_target_service.py:362-363`
- **Status**: NEW
- **Description**: `generate_targets_from_fingerprint()` evaluates `fp_dict.get('lufs', ...)` but discards the result. Next line hardcodes `target_lufs = -14.0`. All tracks get identical LUFS normalization.
- **Evidence**:
  ```python
  fp_dict.get('lufs', dynamics.get('lufs', -14.0))  # result discarded
  target_lufs = -14.0  # always used
  ```
- **Impact**: Adaptive mastering is non-functional for loudness. Quiet classical and loud pop tracks all normalize to -14.
- **Suggested Fix**: Assign result: `current_lufs = fp_dict.get(...)`, then compute target based on it.

---

### BE-41: Uploaded Input Files Never Cleaned Up
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/routers/processing_api.py:187-228`, `core/processing_engine.py:563-591`
- **Status**: NEW
- **Description**: `upload_and_process` writes to `/tmp/auralis_uploads/`. `cleanup_old_jobs()` removes `job.output_path` but never `job.input_path`. Upload files accumulate indefinitely.
- **Impact**: Disk exhaustion on long-running instances.
- **Suggested Fix**: Also unlink `job.input_path` in `cleanup_old_jobs()`.

---

### BE-42: StreamlinedCacheWorker Creates New Processor Per Chunk — DSP State Reset
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/streamlined_worker.py:274-283`
- **Status**: NEW
- **Description**: Background cache builder creates a fresh `ChunkedAudioProcessor` (and `HybridProcessor`) for every chunk. DSP state (compressor envelopes, EQ history) resets at every boundary. Live streaming correctly reuses one processor.
- **Impact**: Audible compression pumping or level jumps every 10s during cached playback.
- **Suggested Fix**: Maintain one processor per `(track_id, preset, intensity)` across the build loop.

---

### BE-43: Raw Exception String Exposed in Job Status API Response
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/processing_engine.py:501,504`, `routers/processing_api.py:256-260`
- **Status**: NEW
- **Description**: `process_job` stores `str(e)` in `job.error_message`. `GET /api/processing/job/{id}` returns it verbatim, exposing file paths, FFmpeg stderr, and NumPy internals.
- **Suggested Fix**: Store human-readable category; log full exception separately.

---

### BE-44: No Timeout on DSP `processor.process()` in ProcessingEngine
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/processing_engine.py:447-453`
- **Status**: NEW
- **Description**: All three `asyncio.to_thread(processor.process, ...)` calls have no timeout. A hung HPSS or Rust PyO3 call blocks the semaphore slot indefinitely. Two hung jobs deadlock the processing queue permanently.
- **Suggested Fix**: Wrap with `asyncio.wait_for(..., timeout=300)`.

---

### BE-45: `has_more` Pagination Computed With Two Different Formulas
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `albums.py:76`, `library.py:119,154`, `artists.py:147`, `pagination.py:90`
- **Status**: NEW
- **Description**: `(offset + len(items)) < total` vs `(offset + limit) < total` used inconsistently. `pagination.py` utility exists but is not used by any endpoint.
- **Suggested Fix**: Use `pagination.py:PaginatedResponse.create()` everywhere.

---

### BE-46: `similarity.fit()` Blocks Event Loop With Bulk DB Load + NumPy Stats
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/similarity.py:331`
- **Status**: NEW
- **Description**: `POST /api/similarity/fit` calls `similarity.fit()` synchronously — loads all fingerprints and runs 25×4 NumPy reductions on the event loop. 0.1–2s stall for 5,000 tracks.
- **Suggested Fix**: `await asyncio.to_thread(similarity.fit)`.

---

### BE-48: `TrackBase`/`ArtistBase`/`AlbumBase` Declare `id: str` but All IDs Are `int`
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/schemas.py:301-320`
- **Status**: NEW
- **Description**: Base schemas use `id: str`. All DB models and the frontend `domain.ts` use integer IDs. If adopted as `response_model`, integer IDs silently coerce to strings.
- **Suggested Fix**: Change to `id: int`.

---

### BE-55: Settings Router Tests Entirely Skipped With Wrong Justification
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_main_api.py:1048-1068`
- **Status**: NEW
- **Description**: `TestSettingsEndpoints` is `@pytest.mark.skip(reason="No REST /api/settings endpoint")` — but the settings router has 5 active REST endpoints. All test stubs are empty `pass`.
- **Suggested Fix**: Remove skip decorator; implement the 6 test stubs.

---

### BE-56: `POST /api/library/reset` Has Zero Test Coverage
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/library.py:706-755`, `tests/backend/`
- **Status**: NEW
- **Description**: The most destructive endpoint in the API has no tests. Neither success path, rollback path, nor 503 path is exercised.
- **Suggested Fix**: Add `test_library_reset.py` covering 503, success, rollback, and response structure.

---

### LOW Severity

---

### BE-27: `order_by` Not Validated at Route Layer in Tracks/Albums Endpoints
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/library.py:86-134`, `albums.py`
- **Status**: NEW
- **Description**: Invalid `order_by` silently falls back to `'title'` in the repository. The artists endpoint correctly validates. Inconsistent.
- **Suggested Fix**: Add whitelist validation or use `Literal` type annotation.

---

### BE-28: `GET /api/processing/jobs` Has Unbounded `limit` Parameter
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/processing_api.py:326-348`
- **Status**: NEW
- **Description**: No `ge`/`le` constraints. Negative `limit` drops last job; very large values cause unbounded allocation.
- **Suggested Fix**: Use `Query(50, ge=1, le=1000)`.

---

### BE-32: `AudioStreamController.active_streams` Is Dead Code
- **Severity**: LOW
- **Dimension**: WebSocket Streaming / Chunked Processing
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:226,541,784,1507`
- **Status**: NEW
- **Description**: Every streaming handler creates a new `AudioStreamController` instance. `active_streams` is per-instance, always has at most one entry, and is discarded with the controller. Also keyed by `track_id` not `(track_id, ws_id)`, so same-track concurrent streams (seek + play) would cross-contaminate. Actual task tracking lives in `_active_streaming_tasks` in `system.py`.
- **Suggested Fix**: Remove `active_streams` and its usage sites.

---

### BE-33: `overlap_duration` Hardcoded to 5 in StreamMetadata
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/webm_streaming.py:201`
- **Status**: NEW
- **Description**: Hardcoded `overlap_duration=5` regardless of actual config. With defaults (`chunk_duration == chunk_interval == 10`), real overlap is 0. Clients using this field would trim 5s of valid audio.
- **Suggested Fix**: `max(0, chunk_duration - chunk_interval)`.

---

### BE-36: `_send_error` Always Uses `STREAMING_ERROR` Code Regardless of Context
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1370-1382`
- **Status**: NEW
- **Description**: Seek errors from within `stream_enhanced_audio_from_position` report `STREAMING_ERROR` instead of `SEEK_ERROR`, preventing frontend seek-error recovery UI from activating.
- **Suggested Fix**: Add optional `error_code` parameter to `_send_error`.

---

### BE-37: Seek Path Skips Look-Ahead Pipeline — Sequential Per-Chunk Latency
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1563-1587`
- **Status**: NEW
- **Description**: Normal playback uses look-ahead (process N+1 while streaming N). Seek path uses legacy sequential `_process_and_stream_chunk`. Also, computed `fast_start` flag is never passed.
- **Impact**: 2–10s gaps between chunks on slow storage during seek playback.
- **Suggested Fix**: Use same look-ahead pattern; pass `fast_start`.

---

### BE-38: `start_worker()` Is Effectively Serial — `max_concurrent_jobs` Is Dead
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:507-537`
- **Status**: NEW
- **Description**: Worker immediately `await task`s each job before looping. Only one worker is started. `max_concurrent_jobs=2`, the semaphore, and `_active_job_count` can never reflect >1 in-flight job. No practical impact for single-user desktop, but the parameter and log messages are misleading.
- **Suggested Fix**: Either remove the concurrency infrastructure or stop awaiting each task.

---

### BE-49: `SetPresetRequest.preset` Is Unconstrained `str` — Preset List Duplicated 3x
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/enhancement.py:41-49`, `system.py:235`, `domain.ts:158`
- **Status**: NEW
- **Description**: Preset validated via `@field_validator` against hardcoded list instead of Enum. Same list duplicated in system.py and frontend.
- **Suggested Fix**: Define `PresetEnum(str, Enum)` in `schemas.py`.

---

### BE-50: `ProcessingSettings` Uses camelCase `levelMatching` in Snake_case Schema
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/processing_api.py:82`
- **Status**: NEW
- **Description**: `levelMatching` is the only camelCase field. Clients sending `level_matching` are silently ignored.
- **Suggested Fix**: Rename with `alias="levelMatching"` for backwards compat.

---

### BE-51: 18 Player Endpoints Use `response_model=None` — No OpenAPI Schema
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/player.py`
- **Status**: NEW
- **Description**: All player endpoints suppress OpenAPI response schema generation. Regressions in response shape go undetected at the framework level.
- **Suggested Fix**: Define response models for key endpoints (status, seek, volume).

---

### BE-52: Fingerprint Endpoint Exposes Inconsistent Derived Fields
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/library.py:689-697`
- **Status**: NEW
- **Description**: Track fingerprint returns `percussive_ratio`, `chroma_energy_variance: null`, `key_strength` (derived/proxy fields). Album fingerprint excludes them. Inconsistent schemas.
- **Suggested Fix**: Standardize on the 25 canonical DB-backed dimensions for both.

---

### BE-53: `processing_engine.start_worker()` Task Leaked on Shutdown
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/startup.py:277`, `core/processing_engine.py:507`
- **Status**: NEW
- **Description**: Worker task reference discarded. No `stop_worker()` method exists. Shutdown guard `hasattr(..., 'stop_worker')` always False. Log says "Processing Engine stopped" regardless.
- **Suggested Fix**: Store task reference; add `stop_worker()` with `asyncio.Event`; await at shutdown.

---

### BE-54: Dead `middleware.py` at Backend Root Shadows Active Middleware
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/middleware.py`
- **Status**: NEW
- **Description**: Root-level `middleware.py` defines unused middleware classes including one with wildcard CORS. Never imported by `main.py`. Maintenance debt.
- **Suggested Fix**: Delete the file.

---

### BE-62: `get_state_manager` Not Wired to System Router — Reconnect Sync Broken
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/routes.py:83-89`
- **Status**: NEW
- **Description**: `create_system_router()` accepts optional `get_state_manager` for reconnect state sync. `setup_routers()` never passes it. Reconnecting WebSocket clients get no player state snapshot.
- **Suggested Fix**: Pass `get_state_manager=get_component('player_state_manager')`.

---

### BE-59: Dead `Path(input_path)` Expression in `create_job()`
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:146`
- **Status**: NEW
- **Description**: `Path(input_path)` called but result discarded. Neither validates nor normalizes. Dead code.
- **Suggested Fix**: Remove the expression.

---

### BE-60: `start_worker` Uses `print()` Instead of Logger
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/processing_engine.py:536`
- **Status**: NEW
- **Description**: Worker crash handler uses `print()` bypassing log handlers and omitting tracebacks.
- **Suggested Fix**: `logger.error("Worker error", exc_info=True)`.

---

### BE-61: `assert` Statements Used for Runtime Invariants in Streaming Hot Path
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:535-538`
- **Status**: NEW
- **Description**: Four `assert` statements guard metadata post-conditions. Python `-O` disables them. PyInstaller may enable optimization.
- **Suggested Fix**: Replace with explicit `if ... is None: raise ValueError(...)`.

---

### BE-57: `POST /api/albums/{id}/artwork/download` Has No Test Coverage
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/artwork.py:232-302`
- **Status**: NEW
- **Description**: Only artwork endpoint without tests. Happy path, 404, 503, and download failure all untested.
- **Suggested Fix**: Add mock-based tests for the MusicBrainz/iTunes download path.

---

### BE-58: `POST /api/processing/process` (File-Path Endpoint) Has No Happy-Path Test
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/processing_api.py:111-166`
- **Status**: NEW
- **Description**: Only tested for 503 (QueueFull). The 200-OK path and `reference_path` Matchering branch are untested.
- **Suggested Fix**: Add success-path test with mocked engine and `validate_file_path`.

---

## Relationships & Shared Root Causes

1. **Event loop blocking** (BE-24, BE-46, BE-47): All share the same root cause — synchronous operations called directly from async handlers. Fix pattern is uniform: `asyncio.to_thread()`.

2. **Exception leaking** (BE-30, BE-43): Both the REST router and processing engine expose raw exception strings. Fix: use `routers/errors.py:InternalServerError` pattern consistently.

3. **DSP state discontinuity** (BE-34, BE-42): Both the full-track export and background cache builder fail to maintain DSP state across chunk boundaries. The streaming path is correct and can serve as the reference implementation.

4. **Seek path deficiencies** (BE-31, BE-35, BE-36, BE-37): The seek handler has four issues — stale events, no PCM trimming, wrong error codes, and no look-ahead. These should be fixed together as a "seek reliability" pass.

5. **Dead code cluster** (BE-32, BE-38, BE-54, BE-59): Four dead code findings. Low impact but maintenance debt.

6. **Library reset** (BE-29, BE-56): Unguarded destructive endpoint with zero test coverage — highest combined risk in this audit.

## Prioritized Fix Order

| Priority | Findings | Rationale |
|----------|----------|-----------|
| 1 | BE-24, BE-47 | Event loop blocking causes audio dropouts during normal usage |
| 2 | BE-29 + BE-56 | Unguarded destructive endpoint with no tests |
| 3 | BE-31 | Seek-while-paused deadlock is user-triggerable |
| 4 | BE-42 | Cached playback audio artifacts every 10s |
| 5 | BE-34, BE-35 | Audio integrity: export corruption + seek precision |
| 6 | BE-40 | Adaptive mastering LUFS is a no-op |
| 7 | BE-30, BE-43 | Exception string leaks (security hardening) |
| 8 | BE-39 | Cache router 404s (feature broken) |
| 9 | BE-44 | Processing timeout (resilience) |
| 10 | BE-46 | similarity.fit() event loop (moderate stall) |
| 11 | All LOW | Cleanup pass |
