# Backend Audit — 2026-09-16

**Scope**: `auralis-web/backend/` — 20 registered routers, WebSocket handler layer, chunked processor + siblings, streaming/seek paths, processing engine + `job_*` siblings, schemas, middleware/config, caches, services, backend tests.
**Method**: fresh read of current source at HEAD (`10c76494`). 11 dimension agents (`audit-backend.md` default: all 11, depth `deep`, no limit), merged and deduplicated by the orchestrator. Every dimension cross-referenced `docs/audits/AUDIT_BACKEND_2026-09-13.md` (3 days prior) and re-verified, against live source rather than trusting commit messages, which of that report's findings are now fixed.
**Dedup baseline**: `gh issue list --limit 200` (102 open issues) at audit time.
**Context**: this audit landed three days after, and the same day as, a large wave of backend fixes — including several from this exact session (#5278 durable job persistence, #5317 FFmpeg bit depth, #5318 rate-limit method keying, #5349 processor cache file_signature). Every dimension was explicitly told which of the prior report's findings to treat as closed and re-verify rather than re-investigate from scratch.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 7 |
| LOW | 10 |
| **Total** | **17** |

Dimension yield (after merge): Route Handlers 0, WebSocket Streaming 1 LOW, Chunked Processing 1 LOW, Processing Engine 1 MEDIUM + 1 LOW, Schema Consistency 4 LOW, Middleware & Config 1 LOW, Error Handling 2 MEDIUM, Performance 1 MEDIUM, Test Coverage 1 MEDIUM + 1 LOW, Caching & Invalidation 2 MEDIUM + 1 LOW, Seek & Buffering 0.

**Overall**: this is the cleanest backend audit run to date — **zero CRITICAL and zero HIGH findings**, and every HIGH/CRITICAL finding from the 2026-09-13 report (the "Durable chunk cache has no writer coordination" and "Abandoned executor work" themes) is now fixed and was independently re-verified in place by at least one dimension agent, several by two. Route handling, WebSocket lifecycle, chunk tiling geometry, and seek/buffering are now essentially fully hardened — three dimensions (Route Handlers, Seek & Buffering) returned zero or near-zero findings after exhaustive re-tracing.

**Key themes**

1. **Three independently-built "prewarm the rest of the track in the background" mechanisms exist; at most one is reachable.** `chunk_batch.process_all_chunks_async` (BE-D3-01) has zero production callers. `core/chunk_cache.py::SimpleChunkCache`, a carefully-maintained in-memory numpy cache with its own multi-issue bug-fix history, is gated behind an `isinstance` check that is always `False` in the app's healthy configuration (BE-D10-01). Only `proactive_buffer.buffer_presets_for_track` is confirmed genuinely live (housekeeping note: issue #5281 calling it dead is now stale and should be closed). Recommend picking one prewarm/fast-cache strategy and deleting the other two rather than continuing to maintain three.
2. **Today's new durable-job-persistence feature (`e788ed76`, #5278) is solid but narrow, and highlighted what it does *not* cover.** `get_queue_status()` wasn't updated for the new `INTERRUPTED` status (BE-D4-01), the closure wiring it to the real repository factory has no integration test (BE-D9-02), and — the more consequential sibling gap — the live *playback session* (queue, current track, position) has no equivalent persistence layer at all: a backend restart silently hands a reconnecting client an empty "nothing playing" snapshot indistinguishable from a fresh launch (BE-D7-01).
3. **A second, uncoordinated cache-consistency gap remains in the streamlined (tier1/tier2) cache**, distinct from the durable-chunk-cache writer-coordination problems the last audit found and this session already fixed: `StreamlinedCacheManager.get_chunk()` never checks the file still exists before returning a hit, and an independent process-wide 512 MB reaper can silently delete a file it still tracks (BE-D10-02) — the same "monitoring says cached, bytes are gone" failure class as the fixed bugs, just at one layer up.
4. **A newly-introduced blocking call sits on the event loop.** `FileSignatureService.generate()` — real `open()`+`read()`+SHA-256 — runs unwrapped in `asyncio.to_thread` inside the streamlined cache worker's 1-second tick loop, at up to three call sites, one of which was added by this session's own #5349 fix (BE-D8-01). Mechanical, two-line fix.
5. **Error-message specificity is lost on the primary playback path.** All three streaming entry points (`stream_enhanced.py`/`stream_normal.py`/`stream_seek.py`) swallow their catch-all exception into a hardcoded "Audio streaming failed" instead of the specific FFmpeg/corrupt-file category `_safe_error_message()` already computes correctly for the job-processing path (BE-D7-02) — the backend already knows the real reason; it just doesn't tell the client.

**Most impactful**: BE-D7-01 (a restart silently erases what the user was playing, with no signal to the client that anything was lost) and BE-D10-01/BE-D10-02 (the fast in-memory chunk cache never runs, and the tier cache that does run can lie about what's actually on disk) are the three worth fixing first — none is a data-corruption risk, but all three are user-visible degradations of features the codebase has already invested real engineering in.

---

## Route Coverage Matrix

Derived from `config/routes.py` (20 registered routers). Dimension 1 found no validation, response-model, or DI gaps in any of them; the only router-level finding across the whole audit is cosmetic (Dimension 6, tags).

| Router | Prefix(es) | Async | Input validation | response_model | Notes |
|---|---|---|---|---|---|
| health | `/api/health`, `/api/version` | Yes | n/a | Full | |
| system | `/ws` | Yes | Message-level | n/a | WebSocket entry point |
| settings | `/api/settings*` | Yes | Pydantic + preset/intensity degrade-to-null | Full | Preset single-source-of-truth re-verified clean |
| files | `/api/files/upload`, `/api/audio/formats` | Yes | Magic bytes + size cap + extension allowlist | Full | |
| enhancement | `/api/player/enhancement/*` | Yes | `EnhancementPresetLiteral` | Full | Prewarm/live-stream race (prior BE-D3-01) fixed via `_track_is_live_streaming()` |
| artwork | `/api/albums/{id}/artwork*` | Yes | `Path(ge=1)` | 3/4 (raw image) | |
| albums | `/api/albums*` | Yes | `Path(ge=1)` | Full | **No `tags=` set (BE-D6-01, LOW)** |
| artists | `/api/artists*` | Yes | `Path(ge=1)` | Full | **No `tags=` set (BE-D6-01, LOW)** |
| playlists | `/api/playlists*` | Yes | `Path(ge=1)`, Pydantic bodies | Full | |
| library | `/api/library/stats`, reset, refresh | Yes | Query bounds | Full | |
| tracks | `/api/library/tracks*` | Yes | `Query(ge/le)`, `Path(ge=1)` | Full | |
| library_scan | `/api/library/scan*` | Yes | `LibraryScanRequest` validator | Full | |
| fingerprint_status | `/api/library/fingerprints/status`, `/api/tracks/{id}/fingerprint` | Yes | `Path(ge=1)` | Full | Test coverage confirmed present (spread across 3 files) |
| fingerprint_queue | `/api/similarity/fingerprint-queue/*` | Yes | Pydantic bodies | Full | |
| similarity | `/api/similarity/*` | Yes | `Path(ge=1)` | Full | DB-locked errors → 500 not 503 (Existing #5381) |
| similarity_graph | `/api/similarity/graph/*` | Yes | n/a (no body) | Full | **Success path untested (BE-D9-01, MEDIUM)** |
| player (+ 4 sub-files) | `/api/player/*` | Yes | `Path`/`Query` bounds, request-bounds models | Full | #5472 split verified correctness-preserving |
| processing_api (+ 4 sub-files) | `/api/processing/*` | Yes | Pydantic bodies | Full/FileResponse | `get_queue_status` misses `INTERRUPTED` bucket (BE-D4-01, LOW) |
| metadata | `/api/metadata/*` | Yes | Pydantic bodies | Full | |
| cache_streamlined | `/api/cache/*` | Yes | `Path(ge=1)` | Full | Status endpoint can report a stale "fully cached" (BE-D10-02, MEDIUM) |

Every handler across all 20 routers is `async def`; no route-shadowing conflicts found; dependency injection goes through `Depends()`/ContextVar providers, not module globals.

---

## Findings

### MEDIUM

### BE-D7-01: A backend restart silently drops the entire playback session (queue, current track, position) with no persistence and no client-visible signal
- **Severity**: MEDIUM
- **Dimension**: Error Handling / Recovery
- **Location**: `auralis-web/backend/player_state.py:55-86` (`PlayerState`), `auralis-web/backend/core/state_manager.py:22-45` (`PlayerStateManager.__init__`), `auralis-web/backend/config/startup/components.py`, `auralis-web/backend/ws_handlers/connection.py:148-162` (`setup_connection`)
- **Status**: NEW
- **Description**: `PlayerStateManager` holds the single in-memory `PlayerState` (queue, `queue_index`, `current_track`, `is_playing`, position) with no persistence layer of any kind. `auralis/library/repositories/queue_history_repository.py` exists but is wired only into the explicit undo/redo feature, not into snapshot-and-restore of "what's currently loaded." Neither the frontend (grepped for `localStorage` usage — only `ThemeContext.tsx` uses it) nor the backend remembers the session. Today's durable-job-persistence feature (`e788ed76`/#5278) gives `ProcessingJob` rows exactly this kind of restart survival; the live playback session has no analogue.
- **Evidence**:
  ```python
  # core/state_manager.py
  def __init__(self, websocket_manager: Any) -> None:
      self.state: PlayerState = PlayerState()   # always fresh defaults

  # ws_handlers/connection.py — runs on every (re)connect
  _state = _state_mgr.get_state()
  await websocket.send_text(json.dumps({"type": "player_state", "data": _state.model_dump()}))
  ```
- **Impact**: A user mid-playback when the backend restarts (crash, `--dev` relaunch, an Electron auto-update restart) loses their queue and position outright, with the reconnecting client receiving a clean "nothing loaded" snapshot wire-identical to a fresh launch — no error, no explanation, session must be rebuilt by hand.
- **Suggested Fix**: Either persist a minimal session snapshot (current track id, position, queue ids/order) on each meaningful transition and reload it the way `restore_jobs()` reloads jobs, or — if session loss on restart is accepted as by-design — make it visible: have `setup_connection` tell a reconnecting client explicitly that state was not preserved, instead of silently emitting an indistinguishable default.

### BE-D7-02: All three streaming entry points swallow their catch-all exception into a generic "Audio streaming failed", discarding the specific FFmpeg/corrupt-file categorization already computed elsewhere
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/stream_enhanced.py:271-275`, `auralis-web/backend/core/stream_normal.py:255-259`, `auralis-web/backend/core/stream_seek.py:274-279`; contrast `auralis-web/backend/core/job_error_mapping.py:68-85` (`_safe_error_message`)
- **Status**: NEW
- **Description**: Each of the three streaming entry points wraps its whole body in `except Exception as e: ... await controller._send_error(websocket, track_id, "Audio streaming failed")` with no re-raise, which absorbs the exception before it can reach the outer wrapper functions in `routers/system.py` that already call `_safe_error_message(e)` to translate a `ModuleError`/`FileNotFoundError`/etc. into a specific, user-safe category ("Audio file is corrupted or unsupported", "Audio decoder unavailable on server", ...).
- **Evidence**:
  ```python
  # core/stream_enhanced.py — swallows, does not re-raise
  except Exception as e:
      logger.error(f"Audio streaming failed: {e}", exc_info=True)
      if controller._is_websocket_connected(websocket):
          await controller._send_error(websocket, track_id, "Audio streaming failed")
  ```
  The frontend surfaces `data.error` verbatim (`useAudioStreamingCore.ts:398-402`), so the degraded message is user-visible, not just a log artifact.
- **Impact**: Playing a corrupt/unsupported file, or hitting any exception that isn't a plain chunk-DSP `TimeoutError`, shows the user only "Audio streaming failed" instead of an actionable reason — even though the backend's own log line (`exc_info=True`) already has the specific cause.
- **Siblings**: All three streaming entry points share the identical pattern (confirmed via `grep -n 'Audio streaming failed' core/stream_*.py`).
- **Suggested Fix**: Import `_safe_error_message` from `core.job_error_mapping` in the three `stream_*.py` modules and pass `_safe_error_message(e)` instead of the literal string to `controller._send_error(...)`.

### BE-D4-02: `MasteringTargetService`'s in-memory fingerprint/target cache has no content-signature invalidation and no per-track clear
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/mastering_target_service.py:84-88` (`_get_cache_key`), `:282-352` (`load_fingerprint`), `:486-500` (`clear_global_mastering_target_cache`)
- **Status**: NEW
- **Description**: This process-wide singleton — used by every `ChunkedAudioProcessor` to resolve fingerprint/mastering targets — keys its cache on `f"fingerprint_{track_id}_{md5(filepath)[:8]}"`: a hash of the *path*, not the content, unlike every sibling cache in the subsystem (`chunk_cache.py` keys on `file_signature`; `streamlined_processor_cache.py`'s key was given one today via #5349). `load_fingerprint()` checks this cache before touching the DB or `.25d` sidecar, so an in-place file replacement or fingerprint regeneration is invisible to it until process restart or a full `clear_cache()` — there is no per-track invalidation hook anywhere metadata/audio content changes.
- **Evidence**:
  ```python
  def _get_cache_key(self, track_id: int, filepath: str) -> str:
      file_hash = hashlib.md5(filepath.encode()).hexdigest()[:8]   # hash of the PATH, not content
      return f"fingerprint_{track_id}_{file_hash}"
  ```
- **Impact**: A track replaced in place (re-encode, restore, external edit) or re-fingerprinted by a rescan keeps being mastered against stale targets (wrong LUFS/crest/EQ) until the process restarts or the user hits the blanket "Clear Cache" (which drops every other track's warm cache too).
- **Suggested Fix**: Fold a content signature (reuse `core/file_signature.py`, matching every sibling cache) into `_get_cache_key`, and add a `forget(track_id)` method `routers/metadata.py` and the fingerprint-regeneration path can call.

### BE-D8-01: The streamlined cache worker's tier1/tier2 warming path runs blocking file I/O and SHA-256 hashing directly on the event loop, every ~1s tick during active playback
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/streamlined_tiers.py:118` (`ensure_tier1_chunk`), `auralis-web/backend/core/streamlined_worker.py:219,237` (`_process_chunk`), `auralis-web/backend/core/file_signature.py:64-80`
- **Status**: NEW (the call site at `streamlined_worker.py:237` was added by this session's own #5349 fix; the sibling at `streamlined_tiers.py:118` predates it)
- **Description**: `StreamlinedCacheWorker._worker_loop()` wakes every 1 second and calls `process_priorities()` directly on the event loop. `ensure_tier1_chunk()` calls `FileSignatureService.generate(track.filepath)` synchronously — real `open()` + `fstat()` + up to 128 KiB of `read()` + a SHA-256 pass, all on the loop thread. `_process_chunk()` does the same again independently. The very next line in the same function (`worker.library_database.tracks.get_by_id`) is correctly wrapped in `asyncio.to_thread(...)` with an explicit "sync DB call — offload to thread" comment — the pattern is known and applied one line away; only the signature computation was missed.
- **Evidence**:
  ```python
  # streamlined_tiers.py:52 — correctly offloaded
  track = await asyncio.to_thread(worker.library_database.tracks.get_by_id, track_id)
  # streamlined_tiers.py:118 — NOT offloaded
  file_signature = FileSignatureService.generate(track.filepath)   # blocking open+read+sha256
  ```
- **Impact**: This worker is active for the life of any playback session (that's its whole purpose), so the cost — up to 2-3 redundant hash passes per tick — is paid continuously. Sub-perceptible on local SSD; on a network share, external drive, or SMB/NFS-mounted library, each `open()`/`read()` can cost tens to hundreds of milliseconds, stalling WebSocket heartbeats and playback-control messages in the same window.
- **Suggested Fix**: Wrap the two `FileSignatureService.generate(track.filepath)` calls in `asyncio.to_thread(...)`, matching the pattern already used one line above for the repository lookup. Keep `_process_chunk`'s intentional re-computation (a deliberate #5349 correctness choice) — only how it runs needs to change.

### BE-D9-01: `similarity_graph` router's populated-graph success paths are never exercised — only the "no graph_builder" 503 branch is tested
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/similarity_graph.py:59-128`, `tests/backend/test_similarity_api.py:208-262`
- **Status**: NEW
- **Description**: All three handlers construct their response from real domain objects (`GraphStatsResponse(**stats.to_dict())`) only when `get_graph_builder()` returns a builder. Every test in the suite is written in a "mocked router" style that never provides a real/mocked `KNNGraphBuilder`, so every test only reaches the `graph_builder is None` branch. Nothing pins `GraphStats` (7 dataclass fields) against `GraphStatsResponse` (7 Pydantic fields) agreeing.
- **Impact**: If either shape drifts, `GraphStatsResponse(**stats.to_dict())` raises at request time, turning a successful graph build into an unhandled 500 for every caller — and no test in the suite would catch it before it ships.
- **Suggested Fix**: Add a test case supplying a fake `graph_builder` returning a real `GraphStats` instance and assert the router's JSON response matches end-to-end; consider a field-parity test like `test_response_model_coverage.py` already runs for other response models.

### BE-D10-01: The in-memory per-chunk audio cache (`SimpleChunkCache`) is dead code in production — every enhanced/seek chunk request skips it because the real `cache_manager` is never that class
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/core/stream_chunk_ops.py:74,174` (`process_chunk_only`), `auralis-web/backend/core/audio_stream_controller.py:145-161,216-241`, `auralis-web/backend/config/startup/workers.py:177-181`
- **Status**: NEW
- **Description**: `process_chunk_only()` — the shared per-chunk entry point for the enhanced and seek streaming paths — only consults `core/chunk_cache.py::SimpleChunkCache` when `isinstance(controller.cache_manager, SimpleChunkCache)`. In every real router wiring, `cache_manager` resolves to the `StreamlinedCacheManager` singleton, which shares no relationship with `SimpleChunkCache` (different base classes, different method names/signatures). `SimpleChunkCache` is only ever instantiated as the degraded fallback used when the streamlined cache fails to initialize.
- **Evidence**:
  ```python
  # core/stream_chunk_ops.py:74 — only reachable in degraded fallback mode
  if isinstance(controller.cache_manager, SimpleChunkCache):
      cached_result = controller.cache_manager.get(...)
  ```
- **Impact**: Every chunk of every enhanced or seek stream, in the app's default healthy configuration, always takes the cache-MISS branch — scrubbing back over the same seconds, toggling a preset, or a look-ahead re-request never gets the sub-millisecond in-memory hit the code exists for. Not a correctness bug (the on-disk `ChunkPathCache` is still checked one layer down), but several targeted historical fixes to this exact code path (file_signature keying, gain_db restoration, targets_hash keying, executor placement) all improved logic that never executes in production.
- **Suggested Fix**: Either adapt `process_chunk_only` to call `StreamlinedCacheManager`'s own tier1/tier2 API for the fast path, or delete `SimpleChunkCache` and this dead branch if the on-disk tier is considered sufficient.

### BE-D10-02: `StreamlinedCacheManager.get_chunk()` never checks the file still exists, so an independent on-disk reaper can silently desync tier1/tier2 bookkeeping from reality
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:134-180` (`get_chunk`), `auralis-web/backend/cache/models.py:85-92`, `auralis-web/backend/core/chunk_cache_manager.py:256-347`
- **Status**: NEW
- **Description**: Every physical chunk WAV lands in one shared directory with two independent, uncoordinated eviction policies: `ChunkCacheManager`'s process-wide 512 MB mtime reaper (which has no knowledge of `StreamlinedCacheManager`'s bookkeeping) and `StreamlinedCacheManager`'s own 240 MB tier2 LRU. `StreamlinedCacheManager.get_chunk()` returns `chunk.chunk_path` straight from its dicts with no `Path.exists()`/`is_wav_complete()` check — unlike every sibling in this dimension.
- **Evidence**:
  ```python
  # cache/manager.py — no existence check, unlike every sibling cache
  if cache_key in self.tier1_cache:
      chunk = self.tier1_cache[cache_key]
      ...
      return chunk.chunk_path, "tier1"          # path may already be gone
  ```
- **Impact**: The prewarm worker treats a stale hit as "already cached" and skips re-rendering it. More user-visibly, `GET /api/cache/track/{id}/status` and `/health` can report a track as `fully_cached: true` while the physical bytes have already been reclaimed by the unrelated reaper — a miss recorded as a hit, hiding a real regression.
- **Suggested Fix**: Have `get_chunk()` verify `chunk_path.exists()` (ideally `is_wav_complete()`) before returning a hit, evicting the stale entry on a miss — mirroring `ChunkCacheManager.get_cached_chunk_path`.

---

### LOW

### BE-D2-01: `HeartbeatManager.is_alive()` is dead code
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/websocket/websocket_protocol.py:69-75`
- **Status**: NEW
- **Description**: No production caller anywhere in the repository; the actual staleness/eviction decision uses `is_stale()`/`seconds_until_stale()` exclusively. Only exercised by its own unit test.
- **Impact**: None functionally — pure maintenance/clarity debt.
- **Suggested Fix**: Delete it, or document in its docstring that it is currently unused by production code.

### BE-D3-01: `ChunkedAudioProcessor.process_all_chunks_async` / `chunk_batch.process_all_chunks_async` has zero production callers
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunked_processor.py:285-287`, `auralis-web/backend/core/chunk_batch.py:36-77`
- **Status**: NEW
- **Description**: A whole-track background prewalker that no router, WebSocket handler, service, or background-task spawner ever calls, and no test exercises. The whole-track prewarm role it would serve is only partially covered by `proactive_buffer.buffer_presets_for_track` (which handles only the first few chunks and is itself already tracked, see Existing #5281 note below).
- **Siblings**: `get_full_processed_audio_path` (Existing #5088) and `buffer_presets_for_track`'s DI parameter (Existing #5281) are the same class of unreachable whole-track operation — see the "prewarm mechanisms" theme in the Executive Summary.
- **Suggested Fix**: Delete alongside the already-tracked cleanup, or pick one prewarm mechanism and delete the other two.

### BE-D4-01: `get_queue_status()` silently drops restored/interrupted jobs from every status bucket
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:312-330`, `auralis-web/backend/core/job_models.py:23-41`, `auralis-web/backend/routers/processing_models.py:124-133`
- **Status**: NEW (introduced by today's `e788ed76`, #5278)
- **Description**: `e788ed76` added a fifth terminal `ProcessingStatus.INTERRUPTED` for jobs a previous process left mid-flight, but `get_queue_status()` still buckets into only `queued`/`processing`/`completed`/`failed`/`cancelled`, so an interrupted job inflates `total` without appearing in any bucket. `QueueStatusResponse` has no `interrupted` field either.
- **Impact**: Latent today — no frontend code calls this endpoint — but any future dashboard or test asserting `total == sum(buckets)` will intermittently fail after a restart that caught a job mid-flight.
- **Suggested Fix**: Add an `interrupted` bucket to both `get_queue_status()` and `QueueStatusResponse`.

### BE-D5-03: `PlaylistResponse` marks fields `Optional` that are never actually `null`
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/schemas/library.py:184-197`
- **Status**: NEW
- **Description**: Six of twelve `PlaylistResponse` fields (`auto_master_enabled`, `mastering_profile`, `normalize_levels`, `track_count`, `total_duration`, `id`, `name`) are declared `X | None` even though the ORM/business logic guarantees non-null on every real row — unlike `TrackResponse`/`AlbumResponse`, whose block comment documents a genuine reason (a `to_dict()` except-branch that can omit keys) that `Playlist.to_dict()` does not share.
- **Impact**: None today — over-hedging is the safe direction; it does mean OpenAPI understates the real guarantee.
- **Suggested Fix**: Narrow the six fields to their real non-null types, keeping `description`/`smart_criteria`/`created_at`/`updated_at` as the only genuinely optional fields.

### BE-D5-04: `TrackResponse.recommended_reference` exposes a raw filesystem path with none of the `filepath` scrubbing #3205 requires
- **Severity**: LOW (currently inert)
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/schemas/library.py:112`, `auralis/library/models/track.py:76,171`, `auralis/player/integration_manager.py:291-299`
- **Status**: NEW
- **Description**: `recommended_reference` stores the same kind of value `filepath` was scrubbed for (#3205) — the only production consumer treats it as a filesystem path — but `TrackResponse` carries it through with no scrubbing. No repository/service/learning-engine code path currently writes it, so every row is `NULL` in practice and the leak is not live.
- **Impact**: If a future feature starts populating this column, it would leak an absolute server filesystem path through the public API with no field-level guard.
- **Suggested Fix**: Drop the field until something populates it, or route it through the same server-only exclusion `filepath` gets before it is wired up as a live value.

### BE-D5-05: Paginated list envelope duplicated verbatim across `TrackListResponse` and `AlbumListResponse` instead of a shared base
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/schemas/library.py:143-149,175-181`
- **Status**: NEW
- **Description**: Both list responses declare an identical four-field pagination envelope (`total`/`limit`/`offset`/`has_more`) inline rather than inheriting a shared base, so the two could silently drift.
- **Suggested Fix**: Factor a small `PaginationEnvelope(BaseModel)` and have both list responses inherit from it.

### BE-D5-06: REST `ScanResultResponse.failures` is an untyped `dict[str, str]` while the paired WebSocket broadcast uses a typed `TypedDict`
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/schemas/library.py:58-62`, `auralis-web/backend/websocket/outbound_messages.py:219-231`
- **Status**: NEW
- **Description**: `ScanResultResponse.failures` is typed `list[dict[str, str]]`, which OpenAPI can only describe as an open-ended map; the WS side's `ScanFailurePayload` TypedDict enforces exactly `{filename, reason}` under static checking.
- **Suggested Fix**: Add a small `ScanFailure(BaseModel)` matching the WS side's precision.

### BE-D6-01: `albums` and `artists` routers register with no OpenAPI tag, unlike every other router
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/routers/albums.py:396`, `auralis-web/backend/routers/artists.py:158`
- **Status**: NEW
- **Description**: Every other registered router constructs its `APIRouter` with `tags=[...]`; these two are the sole exceptions.
- **Impact**: Cosmetic — only visible in Swagger UI under `--dev` (production disables docs entirely).
- **Suggested Fix**: `APIRouter(tags=["albums"])` / `APIRouter(tags=["artists"])`.

### BE-D9-02: The production wiring connecting `ProcessingEngine`'s `JobStore` to the real repository factory is never exercised by any test
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/config/startup/workers.py:106-124`
- **Status**: NEW
- **Description**: `_job_repository()` is the only place in production code that connects `JobStore` to a live `RepositoryFactory`. The dedicated persistence test suite always constructs `JobStore` directly, bypassing this closure entirely.
- **Impact**: Ordering is correct today, but nothing pins it — a rename of `factory.processing_jobs` or a startup reordering would silently regress job persistence back to "everything lost on restart" while every dedicated persistence test keeps passing.
- **Suggested Fix**: Add one integration-style test that runs the real startup wiring against a tmp-file library DB and asserts a job round-trips through the real `RepositoryFactory`.

### BE-D10-03: `CacheMonitor`'s hit-rate/size alerting has zero production callers
- **Severity**: LOW
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/monitoring.py`
- **Status**: NEW (narrower re-scope of the 2026-09-13 report's BE-D10-03 — its other half, `TrackAnalysisCache`/`AnalysisExtractor`, is now fixed/removed via #5085)
- **Description**: No router, background task, or startup path ever constructs a `CacheMonitor`; `/health`'s alerting is recomputed inline instead.
- **Suggested Fix**: Wire it into a periodic task alongside `StreamlinedCacheWorker`, or delete it as unreachable.

---

## Relationships

- **The "three prewarm mechanisms" theme** spans Dimensions 3, 10, and 11: `process_all_chunks_async` (BE-D3-01, dead), `SimpleChunkCache` (BE-D10-01, dead in the healthy path), and `buffer_presets_for_track` (confirmed genuinely live — the #5281 issue describing it as dead is stale and should be closed). Fixing any one of BE-D3-01/BE-D10-01 is a good opportunity to also resolve which of the three the codebase actually wants to keep.
- **Today's durable-job-persistence feature (#5278) and its gaps** span Dimensions 4, 7, and 9: the feature itself is solid (confirmed by three independent agents), but BE-D4-01 (queue-status accounting), BE-D9-02 (untested wiring), and BE-D7-01 (the sibling subsystem — playback session — that has no equivalent at all) are three different angles on the same "brand-new feature, check what it does and doesn't cover" instruction.
- **BE-D8-01 and #5349 (this session's own fix)**: the newly-added call site in `_process_chunk` inherited the same missing-`to_thread` pattern already present at its sibling call site in `ensure_tier1_chunk`. Fixing BE-D8-01 should wrap both, not just the new one.
- **BE-D4-02 and BE-D10-02** are the same underlying pattern (a cache layer that can silently serve stale/wrong data with no reach-check) at two different layers of the caching stack — one in the fingerprint/mastering-target singleton (Processing Engine dimension), one in the streamlined chunk cache (Caching dimension).

## Housekeeping (not audit findings — for `/audit-publish` or direct closure)

- **#5281** ("`buffer_presets_for_track` is dead code, never called") is stale: fixed the day after filing (`3e551429`, #3884) and further hardened since (`a904da77`, #5378). Recommend closing directly rather than re-verifying in a future audit.

---

## Prioritized Fix Order

1. **BE-D7-01** (playback session lost on restart) — highest user-visible impact, no workaround once it happens.
2. **BE-D10-02** (stale cache hit reported as fresh) — a monitoring-truthfulness bug that masks its own regression.
3. **BE-D7-02** (generic streaming error message) — small, mechanical fix (one import + one substitution × 3 files) for a real UX loss.
4. **BE-D8-01** (blocking hash on the event loop) — mechanical two-line fix, compounds under any non-local-SSD library.
5. **BE-D4-02** (stale mastering targets) — real correctness bug, but requires the source file to be edited in place, a narrower trigger than the above.
6. **BE-D10-01** (dead in-memory chunk cache) and **BE-D3-01** (dead whole-track prewarm) — pick one prewarm/fast-cache strategy, delete the others; a design decision more than a bug fix.
7. **BE-D9-01** (untested similarity-graph success path) — cheap to add, closes a real blind spot.
8. Remaining LOW findings (BE-D2-01, BE-D4-01, BE-D5-03..06, BE-D6-01, BE-D9-02, BE-D10-03) — opportunistic cleanup, no user-visible impact today.
