# Backend Audit — 2026-09-13

**Scope**: `auralis-web/backend/` — 20 registered routers, WebSocket handler layer, chunked processor + siblings, streaming/seek paths, processing engine + `job_*` siblings, schemas, middleware/config, caches, services, backend tests.
**Method**: fresh read of current source (HEAD `ce119be1` + uncommitted frontend edits in `settingsService.ts` / `serviceFactory.ts`, which no finding depends on). 11 dimension agents (`audit-backend.md` default: all 11, depth `deep`, no limit), merged and deduplicated by the orchestrator. Each HIGH finding was spot-checked against source during the merge; severities were adjusted where noted.
**Dedup baseline**: 134 open issues plus the 1000 most recent issues in any state (`gh issue list`); prior reports under `docs/audits/` were not reused.
**Out of scope by directive**: narrowing enhancement presets to `'adaptive'` only (commits `c195ac80`, `ae9d28e3`) is intentional. The preset single source of truth was verified consistent across `schemas.py`, `settings.py`, `ws_handlers/playback_commands.py`, `websocket/outbound_messages.py` and the `core/proactive_buffer.py` mirror, with no drift.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 5 |
| MEDIUM | 8 |
| LOW | 6 |
| **Total** | **19** |

Dimension yield (after merge): Route Handlers 0, WebSocket 1, Chunked Processing 1, Processing Engine 1, Schema 2, Middleware & Config 2, Error Handling 2, Performance 2, Test Coverage 1 (3 more folded into the findings they cover), Caching 3, Seek & Buffering 4.

**Overall**: the backend is well hardened. All ~100 REST routes are `async def` and offload blocking work. `response_model` coverage is effectively complete, and there are no route-shadowing conflicts. Chunk tiling geometry was fuzz-verified with zero mismatches across ~2000 durations × 5 sample rates, and no chunk constant bypasses `chunk_boundaries.py`. WS lifecycle, backpressure and PCM framing agree with the frontend, and CORS is exact-list matching. Dozens of closed fixes were spot-checked and none have regressed.

**Key themes**
1. **Durable chunk cache has no writer coordination** (BE-D3-01, BE-D11-01, BE-D10-02). The on-disk WAV cache key is `(track, file_signature, preset, intensity, chunk)` and carries no stream identity. Independent `ChunkedAudioProcessor` instances write to it without coordination: an abandoned seek look-ahead, and the enhancement prewarm task that runs alongside the live stream. Each writer has its own `LevelManager`, so gain smoothed against the wrong history gets persisted and later served as a cache hit. The "Clear Cache" lever that should recover from this does not reach those files.
2. **Abandoned executor work** (BE-D7-01, BE-D2-01, BE-D11-01). `task.cancel()` / `wait_for` cannot stop DSP already running in a thread. Callers either leak the thread (jobs, on the 8-worker DB-sized I/O pool), hold a process-wide lock while waiting for it (stop), or let it finish and persist its result (look-ahead).
3. **Dev-mode propagation is launcher-specific and untested** (BE-D6-01, BE-D6-02).
4. **Contract nullability over-promised on the frontend** (BE-D5-01, BE-D5-02). The backend is correct, but the TS types claim non-null for fields the backend legitimately sends as `null`.

**Most impactful**: BE-D11-01 and BE-D3-01 (audible level steps durably cached under ordinary scrubbing or toggling). BE-D7-01 (repeated job timeouts can exhaust the I/O pool that serves every repository call). BE-D10-02 (cache clear is a no-op for what live playback wrote, which also leaves #4666 without a workaround).

---

## Route Coverage Matrix

Endpoint counts cover both `@router.<method>` decorators and `add_api_route()` calls. The test column is from dimension 9.

| Router (factory) | Prefix / paths | #Endpoints | Async | Input validation | response_model | Tests (happy / errors) | Notes |
|---|---|---|---|---|---|---|---|
| health | `/api/health`, `/api/version` | 2 | Yes | n/a | Full | Yes / Partial | Always-200 liveness contract |
| system | `/ws` | 1 (WS) | Yes | Message-level | n/a | Yes / Yes | `test_system_api.py` runs in CI (no `--ignore` in `backend-tests.yml`) |
| settings | `/api/settings*` | 5 | Yes | Pydantic + preset/intensity degrade-to-null | Full | Yes / Yes | Preset narrowing verified |
| files | `/api/files/upload`, `/api/audio/formats` | 2 | Yes | Magic bytes + size cap at read + extension allowlist | Full | Yes / Yes | UUID storage blocks filename traversal |
| enhancement | `/api/player/enhancement/*` | 5 | Yes | `EnhancementPresetLiteral` | Full | Yes / Yes | Prewarm race (BE-D3-01) untested |
| artwork | `/api/albums/{id}/artwork*` | 4 | Yes | `Path(ge=1)` | 3/4 (raw image) | Yes / Yes | Strong traversal/redirect tests |
| playlists | `/api/playlists*` | 10 | Yes | `Path(ge=1)`, Pydantic bodies | Full | Yes / Yes | Mostly handler-seam tests |
| library | `/api/library/stats`, reset, refresh | 3 | Yes | Query bounds | Full | Yes / Yes | |
| tracks | `/api/library/tracks*` | 6 | Yes | `Query(ge/le)`, `Path(ge=1)` | Full | Yes / Yes | |
| library_scan | `/api/library/scan*` | 2 | Yes | `LibraryScanRequest` validator | Full | Yes / Yes | |
| fingerprint_status | `/api/library/fingerprints/status`, `/api/tracks/{id}/fingerprint` | 2 | Yes | `Path(ge=1)` | Full | Yes / Partial | No dedicated test file |
| metadata | `/api/tracks/{id}/metadata*` | 4 | Yes | `validate_file_path` on every FS touch | Full | Yes / Yes | |
| albums | `/api/albums*` | 4 | Yes | `Path(ge=1)` | Full | Yes / Yes | |
| artists | `/api/artists*` | 3 | Yes | `Path(ge=1)`, Query bounds | Full | Yes / Yes | N+1 fixed (#5084) |
| player | `/api/player/*` | 19 | Yes | Clamped volume, validated position, `Literal` repeat | Full | Yes / Yes | #5268, #5303 open |
| cache_streamlined | `/api/cache/*` | 5 | Yes | Path param | Full | Yes / Yes | Clear reach gap (BE-D10-02) |
| similarity | `/api/similarity/*` | 4 | Yes | Query bounds | Full | Yes / Yes | 500-vs-503 (BE-D7-02) |
| similarity_graph | `/api/similarity/graph*` | 3 | Yes | Mostly admin ops | Full | Yes / Partial | Thinnest test coverage |
| fingerprint_queue | `/api/similarity/fingerprint-queue*` | 4 | Yes | `Path(ge=1)`, Query bounds | Full | Yes / Yes | |
| processing_api | `/process`, `/job/*`, `/presets` … | 10 | Yes | Pydantic settings incl. format/bit-depth cross-validator | 9/10 (download) | Yes / Yes | `/presets` catalog is #4861 (closed, product decision) |

Totals: ~100 REST `(method, path)` pairs plus 1 WS route. No duplicate pairs, and no static-vs-dynamic segment shadowing.

---

## Findings

### HIGH

### BE-D2-01: `handle_stop` holds the process-wide transport lock across an unbounded task-cancellation await
- **Severity**: HIGH (special rule: lock held across `await`)
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/ws_handlers/playback_control.py:88-115`, `auralis-web/backend/services/playback_event_sequencer.py:23-35`, `auralis-web/backend/core/chunk_streaming.py:123-132`
- **Status**: NEW
- **Description**: `playback_event_sequencer.transition_lock` is one `asyncio.Lock` for the whole process. It is shared by every WS connection and also by the REST `PlaybackService` (`playback_service.py:133` returns it as `_playback_lock`). `handle_pause`/`handle_resume` do no awaiting while holding it. `handle_stop`, however, calls `await await_cancelled_task(task, logger)` inside `async with transition_lock`. `task.cancel()` cannot interrupt chunk DSP that has already started in `STREAM_EXECUTOR` (documented in #4815 / `ws_handlers/context.py`), and `process_chunk` checks its cancel event only before DSP starts. The await can therefore last as long as an in-flight chunk takes, which the code documents as up to ~2 s.
- **Evidence** (verified during merge):
  ```python
  async with playback_event_sequencer.transition_lock:
      async with state.active_tasks_lock:
          task = state.active_tasks.pop(ws_id, None)
          ...
          cancel_event = state.chunk_cancel_events.pop(ws_id, None)
      if cancel_event is not None:
          cancel_event.set()
      if task and not task.done():
          task.cancel()
          await await_cancelled_task(task, logger)   # lock still held
          logger.info("Cancelled active streaming task")
      event_seq = playback_event_sequencer.next_transport_seq()
  ```
- **Impact**: While one connection's stop waits on its in-flight chunk, pause/resume/stop on every other WS connection stalls for up to ~2 s. So do REST `/api/player/play|pause` requests that go through `PlaybackService`. Realistic triggers are a reconnect racing the old socket's teardown, two windows, or the REST and WS transports being used together.
- **Siblings**: `_cancel_prior_task` (`playback_commands.py:110-136`) awaits cancellation outside `transition_lock`, so it does not have this problem.
- **Test gap (folded BE-D9-02)**: `transition_lock` contention is tested only at the service layer (`tests/regression/test_playback_service_concurrency.py`). `test_playback_event_ordering_5294.py` drives the WS handlers sequentially on one connection, never concurrently across two `StreamState`s.
- **Suggested Fix**: Take the sequence number and release `transition_lock` before awaiting the cancelled task, or move `await_cancelled_task` after the lock block, as `_cancel_prior_task` already does. Add a two-connection WS-handler contention test.

### BE-D3-01: Enhancement prewarm renders upcoming chunks on the shared `HybridProcessor` alongside the live stream and persists them to the durable cache
- **Severity**: HIGH (audible artifact, durably cached)
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/routers/enhancement.py:175-320` (`_preprocess_upcoming_chunks`, `_maybe_prewarm_upcoming_chunks`), `auralis-web/backend/core/chunk_processor_init.py:93-137`, `auralis-web/backend/core/processor_factory.py:192` (`get_or_create`), `auralis/core/hybrid_processor.py:236-262`
- **Status**: NEW (same architectural area as CLOSED #4354, but a different failure mode)
- **Description**: `_maybe_prewarm_upcoming_chunks` runs only while the track is already playing (`state.state.value == "playing"`), on preset/intensity/toggle changes (#4425). It spawns a background task that builds its own `ChunkedAudioProcessor` (with its own fresh `LevelManager` and `chunk_cache={}`) and calls `get_wav_chunk_path()` for chunks `current+1..current+3`. Through `ProcessorFactory.get_or_create(track_id, preset, config_hash, targets_hash)`, both the prewarm and the live stream's processor resolve to the same stateful `HybridProcessor` singleton. `HybridProcessor._process_lock` provides mutual exclusion but not ordering, so the prewarm and the live look-ahead can alternate calls on that one instance. Each prewarm chunk is written to the deterministic on-disk WAV path. That path is shared with the live stream, which later serves it as a cache hit. The gain in those files was smoothed by a `LevelManager` with no history. *Merge note*: a seek also feeds the shared processor out of order, but only once. Here two sequences keep alternating on it, and the result is persisted.
- **Evidence**:
  ```python
  # routers/enhancement.py — fires only while already streaming
  if not (state.current_track and state.state.value == "playing"):
      return
  spawn_background_task(_preprocess_upcoming_chunks(...))
  # independent processor, same shared HybridProcessor underneath
  processor = await asyncio.to_thread(ChunkedAudioProcessor, track_id=track_id,
      filepath=filepath, preset=preset, intensity=intensity, chunk_cache={})
  for chunk_idx in chunks_to_process:          # current_idx+1 .. +3
      wav_chunk_path = await asyncio.to_thread(processor.get_wav_chunk_path, chunk_idx)
  ```
- **Impact**: Toggling enhancement or changing intensity mid-track can bake a wrong compressor/envelope state and an unsmoothed level into up to 3 cached chunks. The live stream then plays them as cache hits, and they persist for future plays of that track.
- **Siblings**: The per-chunk DSP in this prewarm loop also runs on plain `asyncio.to_thread` (the 8-worker I/O pool) rather than `run_in_stream_executor`, the same executor placement issue as BE-D8-02 but with heavier work. BE-D11-01 is the same class of problem: an uncoordinated writer to the cache, which has no stream identity.
- **Test gap (folded BE-D9-03)**: `test_preprocess_upcoming_chunks_5052.py` monkeypatches `spawn_background_task` to await the prewarm synchronously, which removes the concurrency. No test runs the prewarm alongside a live stream on one processor.
- **Suggested Fix**: Skip prewarm when a live stream for the same `track_id` is active (that stream's look-ahead already covers the gap), or reuse the live stream's `ChunkedAudioProcessor`/`LevelManager` through a per-track registry. Add a concurrency test that does not use the synchronous-await shim.

### BE-D11-01: An in-flight look-ahead render that survives seek cancellation writes its chunk to the durable cache with the abandoned stream's level state
- **Severity**: HIGH (look-ahead result cached with wrong state)
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/chunk_streaming.py:76-186` (single cancel check at :128-132, disk write at :168-178), `auralis-web/backend/core/stream_seek_chunks.py:126-130`, `auralis-web/backend/core/stream_enhanced_chunks.py` (identical look-ahead pattern), `auralis-web/backend/ws_handlers/playback_commands.py:110-136`
- **Status**: NEW (the cache-write consequence of the orphaned-thread mechanism in CLOSED #4815; that issue's close addressed only concurrent corruption of DSP internals)
- **Description**: `_cancel_prior_task` sets the chunk cancel event, then cancels and awaits the old task. `process_chunk` reads the event once, before DSP. Nothing inside `_process_chunk_core` / `AudioProcessingPipeline` / `HybridProcessor.process()` checks it again. If a seek arrives while a look-ahead's DSP is already running, the executor thread finishes and `process_chunk` still takes its success path. That path is `encode_and_save_from_path(...)` followed by `_path_cache.store(...)`, and its key has no stream identity. The gain baked into that chunk came from the abandoned processor's `LevelManager` history.
- **Evidence**:
  ```python
  cancel_event = getattr(processor, "_cancel_event", None)
  if cancel_event is not None and cancel_event.is_set():      # only check
      raise ChunkCancelledError(...)
  # ... DSP + smoothing, no further check ...
  chunk_path = processor._wav_encoder.encode_and_save_from_path(
      audio=extracted_chunk, ..., chunk_index=chunk_index, subtype='PCM_16')
  processor._path_cache.store(chunk_index, chunk_path)
  ```
- **Impact**: During ordinary scrubbing, a look-ahead task exists and is mid-DSP for most of the pump loop's lifetime. A seek can therefore persist a chunk whose loudness was smoothed against a sequence no later listener hears. Because of #4669, a later cache hit applies it without re-smoothing, giving an audible level step at that boundary. Typical size is up to ~1.5 dB (`MAX_LEVEL_CHANGE_DB`).
- **Siblings**: `stream_enhanced_chunks.py` `pump_enhanced_chunks` (a seek during ordinary enhanced playback). BE-D3-01 (same class, triggered by prewarm).
- **Suggested Fix**: Check `cancel_event` again immediately before `encode_and_save_from_path` / `_path_cache.store`, and discard the result when it is set, or skip the durable write when the task is no longer `active_tasks[ws_id]`.

### BE-D7-01: Job-processing timeouts permanently leak threads from the DB-sized I/O pool; the chunk-timeout path never invalidates the pooled `HybridProcessor`
- **Severity**: HIGH (resource leak that compounds)
- **Dimension**: Error Handling (overlaps Processing Engine)
- **Location**: `auralis-web/backend/core/job_execution.py:158-189`, `auralis-web/backend/core/executors.py:87-162`, `auralis-web/backend/core/stream_chunk_ops.py:109-121`, `auralis-web/backend/core/processor_factory.py:370-407` (`invalidate`)
- **Status**: NEW. The dedicated-executor follow-up was deferred in the closing comments of #4727 / #4815 / #4999 but never filed.
- **Description**: `job_execution.py` wraps `load_audio` / `processor.process` / `save` in `asyncio.wait_for(asyncio.to_thread(...))`. On timeout only the asyncio wrapper is cancelled, and the OS thread keeps running. Since #5086, the loop's default executor is `IO_EXECUTOR` (8 workers, sized to the SQLAlchemy pool), and every repository-backed REST call uses it. #4727 fixed the correctness half: the timed-out processor is discarded from `ProcessorPool`. The systemic half, a dedicated bounded DSP executor, was never done. Second gap (*corrected during merge*): `ProcessorFactory` does have an `invalidate()` API (#5274) and a `cleanup_track()`, and `chunk_streaming.py` calls `invalidate()` after post-DSP failures. The `TimeoutError` branch in `stream_chunk_ops.process_chunk_only` calls neither. The singleton `HybridProcessor`, which the orphaned thread may still be advancing, therefore remains cached for the next stream of that track.
- **Evidence**:
  ```python
  # core/job_execution.py
  result = await asyncio.wait_for(asyncio.to_thread(processor.process, audio), timeout=timeout)
  # core/executors.py
  IO_POOL_SIZE: int = get_int_env("AURALIS_IO_POOL_WORKERS", 8)
  # core/stream_chunk_ops.py — no invalidate()/cleanup_track() on timeout
  except TimeoutError as e:
      ...
      raise TimeoutError(...) from e
  ```
- **Impact**: Each full-track job timeout (300 s default) removes one of the 8 I/O workers for as long as the hung call runs. Enough of them make every `asyncio.to_thread` in the process queue, so the app stops responding while WS heartbeats keep answering. Replaying or seeking a track after a chunk timeout can hand the new stream a processor whose state is still being advanced by the abandoned thread.
- **Siblings**: `core/streamlined_worker.py` `_process_chunk` keeps a timed-out processor cached (Existing: #5059).
- **Suggested Fix**: Run job DSP on a dedicated bounded executor, following the `STREAM_EXECUTOR` pattern. In the chunk `TimeoutError` branch, call `processor._processor_factory.invalidate(...)` the same way `_invalidate_after_post_dsp_failure` does. Longer term, pass the cancel token into `HybridProcessor.process`.

### BE-D10-02: Cache-clear endpoints and library reset delete only the chunk files the streamlined manager recorded, not the on-disk cache live playback writes
- **Severity**: HIGH (layers left inconsistent; the only workaround for #4666 fails)
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:762-820` (`clear_track`, `clear_all`, `_unlink_chunk_files`), `auralis-web/backend/core/cache_cleanup.py:29-53` (`clear_all_caches`), `auralis-web/backend/routers/cache_streamlined.py:138-167`, `auralis-web/backend/routers/library.py:184-192`
- **Status**: NEW (the #5249 fix covers only paths recorded in tier1/tier2)
- **Description**: `StreamlinedCacheManager.clear_track()` / `clear_all()` unlink only the paths in `tier1_cache` / `tier2_cache`, which are populated only by the background `StreamlinedCacheWorker`. Live playback (`stream_enhanced.py` / `stream_normal.py` building a fresh `ChunkedAudioProcessor` per session) writes deterministic `v{CACHE_VERSION}_track_{id}_{sig}_{preset}_{intensity}_chunk_{n}.wav` files through `ChunkPathCache` into the same chunk directory. `ChunkPathCache.lookup_cached()` finds them again purely by `Path.exists()` + `is_wav_complete()`. `clear_all_caches` (the #5257 lifecycle boundary) calls `cache_manager.clear_all()`, the thumbnail clear and the analysis-cache clear. Nothing sweeps the chunk directory (verified during merge).
- **Evidence**:
  ```python
  # core/cache_cleanup.py
  if cache_manager is not None:
      await cache_manager.clear_all()          # only recorded tier1/tier2 paths
  files_removed, bytes_reclaimed = await asyncio.to_thread(clear_artwork_cache, cleanup_root)
  return CacheClearResult(..., analysis_cache_cleared=clear_global_track_analysis_cache())
  ```
- **Impact**: "Clear Cache" (`POST /api/cache/clear`) and `DELETE /api/cache/track/{id}` leave the files the next play will serve. That covers the stuck/bad-master case the lever exists for, and the stale-targets case of Existing #4666 (the on-disk cache is not keyed on mastering targets). After a library reset, `track_{id}` files from the previous library stay until the opportunistic 512 MB reaper runs.
- **Siblings**: `clear_track_cache` shares the same `clear_track()` call.
- **Suggested Fix**: Add a chunk-directory sweep to `clear_all_caches`: glob and unlink under the encoder's chunk dir, scoped to `track_{id}_` for per-track clears, in the same way as `ChunkCacheManager.prune_chunk_directory`.

### MEDIUM

### BE-D10-01: The `StreamlinedCacheWorker` processor cache key omits `file_signature`, so an in-place edit leaves stale renders and a false "fully cached" status
- **Severity**: MEDIUM (downgraded from HIGH at merge: live playback always builds a fresh processor, so no wrong audio is heard, and growth is bounded by the 8-slot LRU and the 240 MB tier-2 budget)
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/core/streamlined_processor_cache.py:27-53`, `auralis-web/backend/core/streamlined_worker.py:220-259`, `auralis-web/backend/core/streamlined_tiers.py:112-160`
- **Status**: NEW (distinct from Existing #5059)
- **Description**: `ProcessorCacheKey = (track_id, preset, bucketed_intensity)`. Every sibling cache includes `file_signature` (#4358, #5251). After an in-place edit, such as a tag rewrite via `routers/metadata.py`, the tier helpers compute a fresh signature for the lookup. `_process_chunk` still reuses the warm processor, whose signature (and, for m4a/aac/wma, whose decoded temp WAV) was frozen at construction. It then calls `add_chunk(..., file_signature=processor.file_signature)` with the old signature, and tier-2 `TrackCacheStatus` marks each chunk done anyway.
- **Evidence**:
  ```python
  ProcessorCacheKey = tuple[int, str | None, float]   # no file_signature
  processor = await get_or_build_processor(self, (track_id, preset, _intensity_key(intensity)), track.filepath)
  success = await self.cache_manager.add_chunk(..., file_signature=processor.file_signature)
  ```
- **Impact**: `GET /api/cache/track/{id}/status` reports fully cached while no lookup with the correct signature can ever hit those entries. The background worker stops rebuilding tier 2 for that track, keeps re-running tier-1 DSP each tick without ever getting a hit, and orphaned entries occupy the budget until eviction.
- **Suggested Fix**: Add `file_signature` to `ProcessorCacheKey` and pass the freshly computed signature from `ensure_tier1_chunk` / `build_tier2_cache` into `_process_chunk`.

### BE-D5-01: Frontend `Track.album` is typed non-null, but the backend sends `null` for albumless tracks; `CozyLibraryView` search throws
- **Severity**: MEDIUM (contract mismatch; downgraded from HIGH at merge because the backend is correct and the crash is frontend-side, so it should be cross-checked with the concurrent frontend audit)
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:77-82`, `auralis-web/frontend/src/api/transformers/trackTransformer.ts:29`, `auralis-web/frontend/src/api/transformers/types.ts:72`, `auralis-web/frontend/src/types/domain.ts:16`; backend `auralis-web/backend/schemas.py` (`TrackResponse.album: str | None`), `auralis/library/models/track.py` (`to_dict`)
- **Status**: NEW
- **Description**: `Track.to_dict()` emits `'album': None` when no album row exists, which is common for singles and loose files. `TrackResponse.album` is correctly `str | None`. `TrackApiResponse.album: string` and the domain `Track.album: string` claim non-null, and `transformTrack` passes the field through without the `?? ''` fallback it gives neighbouring fields. `CozyLibraryView` (live, mounted from `AppMainContent.tsx`) then calls `track.album.toLowerCase()` with no guard.
- **Evidence**:
  ```ts
  return tracks.filter(track =>
    track.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    track.artist.toLowerCase().includes(searchQuery.toLowerCase()) ||
    track.album.toLowerCase().includes(searchQuery.toLowerCase())   // TypeError on null
  );
  ```
- **Impact**: Typing any search query while an albumless track is in the list throws inside `useMemo`, which breaks the library view's filtering and render.
- **Siblings**: `useSearchLogic.ts:120` renders the literal text "null". `queue_recommender.ts:110`, `useQueueSearch.ts:221-222` and `useTrackContextMenu.ts:92` already guard correctly.
- **Suggested Fix**: Add `album: apiTrack.album ?? ''` (and the same for `title`/`artist`) in `transformTrack`, and mark `TrackApiResponse.album` as `string | null`.

### BE-D6-02: The documented alternate dev launch paths never enable backend dev mode, so the `:3000` renderer is rejected by CORS and the WS origin check
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `desktop/main.js:138-216` (`startPythonBackend`), `desktop/backend-env.js:26-33`, `docs/CONTRIBUTING.md:48`, `auralis-web/backend/config/origins.py`
- **Status**: NEW
- **Description**: `is_dev_mode()` recognizes only a `--dev` argv token or `AURALIS_DEV_MODE`. The Electron dev branch passes `[main.py]` with no `--dev`, and `buildBackendEnv(env, true)` passes the parent env through unchanged; `backend-env.test.js` asserts that it does not add the variable. Yet the same branch loads `http://localhost:3000`. CONTRIBUTING's `python -m uvicorn main:app --reload` also sets neither.
- **Evidence**:
  ```js
  if (this.isDevelopment) {
    pythonArgs = [path.join(__dirname, '..', 'auralis-web', 'backend', 'main.py')];   // no --dev
  }
  env: { ...buildBackendEnv(process.env, this.isDevelopment), ... }
  ```
- **Impact**: A contributor following either documented command gets a backend whose origin allowlist admits only `:8765`. Every `/api/*` fetch from `:3000` fails CORS and the WS closes with 1008, so the app appears broken and nothing obvious points at the cause.
- **Suggested Fix**: Pass `--dev` (or set `AURALIS_DEV_MODE=1`) in the Electron development branch, and fix the CONTRIBUTING example to `python main.py --dev`.

### BE-D7-02: Similarity/graph/fingerprint-queue routers map a transient "database is locked" to 500 instead of the app-standard 503
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/similarity_common.py:82-98`; consumers `routers/similarity.py`, `routers/similarity_graph.py`, `routers/fingerprint_queue.py`
- **Status**: NEW
- **Description**: `_with_similarity_error_handling` sends every non-`HTTPException` through `_internal_error_response()`, which always returns 500. It bypasses `routers/errors.py::handle_query_error`, whose `OperationalError` → `ServiceUnavailableError` (503) branch every other router gets.
- **Evidence**:
  ```python
  except HTTPException:
      raise
  except Exception as e:
      raise _internal_error_response(operation, e) from e   # always 500
  ```
- **Impact**: Lock contention during a scan plus graph rebuild looks permanent (500) on `/api/similarity/*`, while the same condition elsewhere is a retryable 503.
- **Suggested Fix**: Delegate the non-HTTP branch to `handle_query_error`, keeping the correlation-id redaction on top.

### BE-D8-01: The fingerprint-queue worker runs a synchronous repository lookup on the event loop
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/analysis/fingerprint_queue.py:220` (`_worker_loop`); helper `auralis-web/backend/config/startup.py:894-905` (`get_track_filepath`)
- **Status**: NEW
- **Description**: `_worker_loop` is `async def` and calls `self._get_filepath(track_id)` directly. That is `get_track_filepath()`, which runs `factory.tracks.get_by_id(track_id)`, a synchronous SQLAlchemy query. Its sibling DB calls in `FingerprintGenerator.get_or_generate` were moved to `asyncio.to_thread` under #3854; this one was missed.
- **Evidence**: `filepath = self._get_filepath(track_id)   # sync DB call inside async loop`
- **Impact**: After a large scan (10k–100k tracks queued), each dequeue blocks the loop for one SQLite round-trip. On a busy DB (scan writes, WAL checkpoint) these add up to jitter on WS control traffic during playback.
- **Suggested Fix**: `filepath = await asyncio.to_thread(self._get_filepath, track_id)`.

### BE-D9-01: `tests/integration` builds its own `TestClient` without an Origin header, repeating #5089's defect and masking 422 coverage
- **Severity**: MEDIUM (a test giving false assurance on schema validation)
- **Dimension**: Test Coverage
- **Location**: `tests/integration/test_api_integration.py:39-42`, `tests/integration/test_api_workflows.py:41-67`
- **Status**: NEW (same root cause as CLOSED #5089, whose scope note called out this follow-up)
- **Description**: #5089 added a trusted `Origin` header only to `tests/backend/conftest.py`. `tests/integration/` has no conftest, and both files construct their own client without one. `OriginCheckMiddleware` rejects state-changing `/api/*` requests with 403 before any route or Pydantic validation.
- **Evidence**: `pytest-baseline.json` lists 8 `test_api_integration.py` tests as known failures, including `test_api_malformed_json_422` (the suite's only malformed-body 422 integration check) and the volume set/validation tests.
- **Impact**: These write-path assertions produce no signal. A regression that let `/api/player/volume` accept a body without `volume` would pass CI.
- **Siblings**: `test_api_workflows.py` also self-skips through a wrong `auralis_web.backend` import path.
- **Suggested Fix**: Add `tests/integration/conftest.py` (or edit both fixtures) to set `origin: http://localhost:8765`. Then re-run the two files and regenerate the baseline from a CI artifact.

### BE-D11-02: `SeekableSource` re-converts the whole file on every play/seek for m4a/aac/wma, not once per track
- **Severity**: MEDIUM
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/seekable_source.py:82-137`, `auralis-web/backend/core/chunked_processor.py:126-130`, `auralis-web/backend/core/stream_seek.py:138-149`
- **Status**: NEW (#4737 fixed repeated decodes per chunk; this is the same problem per seek. #5253 fixed the temp-file leak, not the decode.)
- **Description**: `resolve()` memoizes per instance. A new `SeekableSource` is built in every `ChunkedAudioProcessor.__init__`, and a new processor is built for every `play_enhanced` / `play_normal` / `seek` command. For formats libsndfile cannot open, each seek into an uncached region pays a full-file FFmpeg decode plus a full-size temp WAV write.
- **Evidence**: `self._source = SeekableSource(filepath)` in the processor constructor. The #5253 comment in `stream_seek.py` states that conversion happens "once per ChunkedAudioProcessor instance, and … a new instance is constructed per seek".
- **Impact**: Seek latency grows with the whole track's length on a common class of files. Concurrent connections each decode independently.
- **Siblings**: `stream_normal.py:118-141` has its own per-stream `convert_to_temp_wav` call.
- **Suggested Fix**: Keep a shared, refcounted registry of converted temp WAVs keyed by `(filepath, file_signature)`, owned alongside `ProcessorFactory`.

### BE-D11-03: Normal-path seek/resume at or past the end is not clamped to duration and errors the stream
- **Severity**: MEDIUM
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:152-192` (`normal_stream_plan`), `auralis-web/backend/core/stream_normal_chunks.py:99-116,168-203`, `auralis-web/backend/routers/system.py:226-271`, `auralis-web/backend/ws_handlers/playback_commands.py:395-398`
- **Status**: NEW (the #5254 fix covered only `chunk_for_position`, not this function)
- **Description**: `handle_seek` validates only `position >= 0` and that it is finite. With enhancement disabled, `stream_from_position` goes to `stream_normal_audio`. `normal_stream_plan` takes no `total_duration`, and it clamps `start_chunk` but not the trim/offset derived from the raw position. This is the "index clamped, offset not" defect #5254 fixed in the enhanced path.
- **Evidence**: For a 125.3 s track at 44.1 kHz, `position=130.3` gives `start_chunk=8`, `first_chunk_trim_samples=454230`, and a start sample (5,746,230) beyond `total_frames` (≈5,525,730). `sf.SoundFile.seek()` past EOF raises `LibsndfileError` (verified experimentally by dimension 11).
- **Impact**: A seek or saved-position resume at `>= duration` with enhancement off ends in an error frame and `reason="errored"` instead of landing on the last audible instant. It does not hang.
- **Suggested Fix**: Clamp `start_position` to duration inside `normal_stream_plan`, as `chunk_for_position` does, or reject it in `stream_normal_audio` once the duration is known.

### LOW

### BE-D4-01: `JobWorker.cancel_task()` is dead code duplicating `job_lifecycle.cancel_job()`
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/job_worker.py:221-238`, `auralis-web/backend/core/job_lifecycle.py:239-241`
- **Status**: NEW
- **Description**: `cancel_task()` has no production callers; the only test reads its docstring. `cancel_job()` re-implements the same lookup-and-cancel inline against `engine._tasks`.
- **Evidence**: `grep -rn "\.cancel_task(" auralis-web/backend/` matches only the definition.
- **Impact**: The two copies can drift apart, which is a DRY violation.
- **Suggested Fix**: Have `cancel_job()` call `engine._worker.cancel_task(job_id)`, or delete the method and its docstring test.

### BE-D5-02: Frontend `Playlist` type declares backend-nullable fields as required
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/frontend/src/services/playlistService.ts:17-30`; backend `auralis-web/backend/schemas.py:325-341`, `auralis/library/models/playlist.py`
- **Status**: NEW
- **Description**: `PlaylistResponse` declares `description`, `mastering_profile`, `auto_master_enabled`, `normalize_levels`, `created_at` and `updated_at` as `X | None`, matching the nullable ORM columns. The TS `Playlist` interface declares all six as non-null.
- **Impact**: Latent only today, since `description` is guarded and the other fields are unread. Future code written against this type would compile and then crash, the same failure shape as BE-D5-01.
- **Suggested Fix**: Mark the fields `| null`, or route playlists through a transformer that supplies defaults.

### BE-D6-01: `launch-auralis-web.py` never clears an inherited `AURALIS_DEV_MODE` for non-dev launches; dev-mode handling is untested
- **Severity**: LOW (loopback-only, needs a pre-existing env var; matches closed siblings #4898/#4802/#4350)
- **Dimension**: Middleware & Config (+ Test Coverage)
- **Location**: `launch-auralis-web.py:52-86` (`start_backend`), `auralis-web/backend/main.py:53`
- **Status**: NEW (the #4898/#4802 fix covered only `desktop/backend-env.js`)
- **Description**: `env = os.environ.copy()` and `AURALIS_DEV_MODE=1` is only ever added, never cleared, when `dev_mode=False`. An exported value from an earlier session therefore widens CORS/WS origins and re-enables `/api/docs` on a supposedly production-shaped run. *Folded BE-D9-04 (downgraded from HIGH, as a test gap on a LOW bug)*: `tests/test_launch_auralis_web_4805.py` never pre-seeds the parent env or asserts on `AURALIS_DEV_MODE`. Separately, `main.py:53` keeps its own copy of the dev-mode predicate (for log level), and no test checks it agrees with `config.app.is_dev_mode()`.
- **Evidence**:
  ```python
  env = os.environ.copy()
  if dev_mode:
      env["AURALIS_DEV_MODE"] = "1"   # never cleared otherwise
  ```
- **Suggested Fix**: Set `env["AURALIS_DEV_MODE"] = "0"` when not in dev mode, mirroring `buildBackendEnv`. Add a leak test and a parametrized agreement test between the `main.py` predicate and `is_dev_mode()`.

### BE-D8-02: Cache-hit level recording runs on the shared I/O pool instead of the stream executor
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/stream_chunk_ops.py:93-98`
- **Status**: NEW
- **Description**: On every in-memory cache hit, `process_chunk_only` calls `await asyncio.to_thread(note_level, ...)`, which runs on the 8-worker `IO_EXECUTOR` rather than `run_in_stream_executor`. That is contrary to the #5086 split for per-chunk hot-path work.
- **Impact**: Adds queueing latency to warm-cache chunk delivery when scans or repository work saturate the I/O pool. The work itself is tiny and not under `wait_for`, so it cannot trip `CHUNK_PROCESS_TIMEOUT`.
- **Siblings**: The prewarm per-chunk DSP in `routers/enhancement.py` (see BE-D3-01) is on `asyncio.to_thread` too, and that work is heavier.
- **Suggested Fix**: Use `run_in_stream_executor`.

### BE-D10-03: `TrackAnalysisCache`/`AnalysisExtractor` and `CacheMonitor` have no production callers, but the analysis cache is still reported as a cleared tier
- **Severity**: LOW
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/analysis/track_analysis_cache.py`, `auralis-web/backend/analysis/analysis_extractor.py`, `auralis-web/backend/cache/monitoring.py`, `auralis-web/backend/core/cache_cleanup.py:10,52`
- **Status**: NEW
- **Description**: `AnalysisExtractor` (the only user of `TrackAnalysisCache`, keyed on `track_id` only) and `CacheMonitor` are never used outside their own modules and tests. `clear_all_caches` still calls `clear_global_track_analysis_cache()` and reports `analysis_cache_cleared`.
- **Impact**: Misleading lifecycle reporting. If the cache is ever wired in without adding `file_signature` to its key, it will serve stale analysis after file edits.
- **Suggested Fix**: Remove these components and the clear step, or wire them in with a signature-complete key.

### BE-D11-04: `normal_stream_plan` truncates the seek trim with `int()` instead of `round()`
- **Severity**: LOW
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:176-181`
- **Status**: NEW
- **Description**: `first_chunk_trim_samples = int(start_position * sample_rate) - ...`. Every other sample-boundary calculation in the module (the #2327 rationale) and the enhanced seek trim in `stream_seek_chunks.py:119` use `round()`.
- **Impact**: Up to one sample of inconsistency, which is inaudible.
- **Suggested Fix**: Use `round()`. Fix together with BE-D11-03.

---

## Skipped as Existing (confirmed still present, not re-reported)

| Issue | Summary | Seen by |
|---|---|---|
| #5303 | `POST /api/player/load` uses DB filepath without `validate_file_path()` | D1 |
| #5268 | `POST /api/player/volume` returns 400, not 503, when the player is unavailable | D1 |
| #5051 | Level-smoothing gain ramp lands in the discarded 5 s overlap head | D3 |
| #4669 | Disk-cache hit skips `LevelManager` recording | D3, D8, D11 |
| #4666 | On-disk chunk cache not keyed on mastering targets | D3 (chains with BE-D10-02) |
| #5056 | `previous_chunk_tail` / `chunk_interval` dead state | D3 |
| #5058 | Reference/hybrid missing-reference fallback mutates the pooled processor config | D4 |
| #5059 | `StreamlinedCacheWorker` keeps a timed-out processor cached | D7, D10 |
| #5088 | `get_full_processed_audio_path()` blocks the loop (unreachable) | D8 |
| #5067, #5275, #5066, #5071, #5070, #5069, #5068, #5206, #4855 | Middleware/config: per-request dev-mode warning, OriginCheck/TrustedHost comment, `file://` split-brain, NoCache on hashed bundles, docs link, rate-limit table gaps, blocking temp sweeps, unused executor getters, predictable temp dirs | D6 |
| #5258 | No single-flight for concurrent seeks to the same chunk key | D11 |
| #5281 | `buffer_presets_for_track` is dead code | D5, D11 |
| #5192, #5195, #5224, #5225, #5226, #5149, #5150, #5176 | Test-suite hygiene items | D9 |
| #4861 (closed, product decision) | `/api/processing/presets` projects the engine profile catalog incl. `live` | D1, D5 |

Closed fixes spot-checked with no regression: #4700, #4605, #4581, #4784, #4815 (start-of-DSP check), #4406, #4895, #4792, #4576, #4575, #4689, #5061, #4735, #4710, #4677, #4586, #4902, #4798–#4801, #4569, #4898, #4802, #4350, #4947, #5084, #4737 (per-chunk memoization), #5254 (enhanced path).

---

## Relationships

- **Uncoordinated writers to a durable cache keyed without stream identity**: BE-D3-01 (prewarm) and BE-D11-01 (orphaned look-ahead) both persist chunks whose gain came from the wrong `LevelManager` history. #4669 means a later cache hit never re-smooths them, which turns a transient mistake into a persistent audible step. BE-D10-02 then removes the user's recovery path ("Clear Cache" does not touch those files), and it also blocks the workaround for #4666. **These four should be fixed as one design change**: gate durable writes on stream liveness, avoid a second processor while a stream is live, and have cache-clear sweep the chunk directory.
- **Abandoned executor work**: BE-D7-01 (job threads leak on the I/O pool; chunk timeout doesn't invalidate), BE-D2-01 (stop waits under a global lock for work it cannot interrupt), BE-D11-01 (abandoned work persists its result) and #5059 all come from `cancel()` / `wait_for` not reaching DSP running in a thread. The long-term fix is the same for all of them: pass the existing `threading.Event` into `HybridProcessor.process` / `AudioProcessingPipeline`, and check it both before persisting and at stage boundaries.
- **Executor placement (#5086)**: BE-D7-01 (job DSP on the I/O pool), BE-D8-02 (cache-hit bookkeeping) and the BE-D3-01 sibling (prewarm DSP) put per-chunk or DSP work on the 8-worker pool that also serves every repository call. BE-D8-01 is the reverse problem: DB work on the loop thread.
- **Normal-path seek drift**: BE-D11-03 and BE-D11-04 live in the same function (`normal_stream_plan`), which missed the #5254 and #2327 conventions. Fix them together.
- **Dev mode**: BE-D6-01 (fails to disable) and BE-D6-02 (fails to enable) share a root cause: each launcher decides dev mode separately, and nothing tests it (folded BE-D9-04).
- **Frontend nullability**: BE-D5-01 and BE-D5-02 are the same pattern. The transformer layer is the right single place to fix it.

---

## Prioritized Fix Order

1. **BE-D11-01 + BE-D3-01** (together): check the cancel event before `encode_and_save_from_path` / `_path_cache.store`, and skip prewarm while a live stream for the track exists. These stop wrong-level audio from entering the persistent cache under normal use. Add concurrency tests for both (the folded D9-03 test gap).
2. **BE-D10-02**: sweep the chunk directory in `clear_all_caches`. Cheap, and it restores the recovery lever for item 1 and for #4666.
3. **BE-D2-01**: move `await_cancelled_task` out of `transition_lock`. A few lines, and it removes cross-connection and REST transport stalls.
4. **BE-D7-01**: call `ProcessorFactory.invalidate()` on chunk timeout (small), then move job DSP to a dedicated bounded executor (larger; protects the DB-sized I/O pool).
5. **BE-D11-03 + BE-D11-04**: clamp and round in `normal_stream_plan`.
6. **BE-D5-01**: null fallback in `transformTrack` (one line, user-visible crash). Coordinate with the frontend audit.
7. **BE-D9-01**: integration conftest Origin header, then regenerate the baseline, so 422 coverage is real again.
8. **BE-D10-01, BE-D11-02**: add `file_signature` to the streamlined processor key; shared converted-source registry.
9. **BE-D6-02, BE-D6-01**: dev-mode propagation plus tests.
10. **BE-D7-02, BE-D8-01**: similarity 503 mapping; `to_thread` for the fingerprint-queue lookup.
11. **LOW cleanup**: BE-D8-02, BE-D4-01, BE-D10-03, BE-D5-02.

---

## Audit Notes

- **Doc drift found in passing (not filed as a finding)**: CLAUDE.md says the whole-backend-suite command excludes `tests/backend/test_system_api.py` and `tests/concurrency/test_thread_safety.py` "exactly like CI does". The current `.github/workflows/backend-tests.yml` has no `--ignore` flags; the workflow header records the hangs as fixed by #4781 and #5095. The local "don't run them as whole files" advice may still apply, but the claim that CI excludes them is stale. Worth a docs follow-up.
- Severity adjustments made at merge: BE-D10-01 HIGH→MEDIUM, BE-D5-01 HIGH→MEDIUM, BE-D9-04 HIGH→LOW (folded into BE-D6-01). BE-D9-02 and BE-D9-03 were folded into BE-D2-01 and BE-D3-01. The second half of BE-D7-01 was corrected: `ProcessorFactory.invalidate()` exists (#5274) but is not called on chunk timeout.
- No tests were executed except dimension-local static checks and small geometry/`soundfile` probes. No source was modified.

Suggested next step: `/audit-publish docs/audits/AUDIT_BACKEND_2026-09-13.md`
