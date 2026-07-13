# Backend Audit — Auralis FastAPI Backend

**Date**: 2026-07-12
**Scope**: `auralis-web/backend/` — 19 routers, WebSocket streaming, chunked processor, processing engine, schemas, middleware/config, error handling, performance, test coverage
**Method**: 9-dimension deep audit (route handlers, WebSocket, chunked processing, processing engine, schema consistency, middleware/config, error handling, performance, test coverage). Every finding re-read against the live tree and cross-checked against 142 open/closed GitHub issues for deduplication.
**Baseline**: Auralis is a desktop-only Electron app binding to `127.0.0.1:8765`; network-exposure-only severities are downgraded per `_audit-severity.md`.

---

## Executive Summary

The backend is **well-hardened**. Middleware/config, error handling, and test coverage are in strong shape — most of the classic 500-leak / orphaned-subprocess / CORS-wildcard / N+1-on-list-endpoint hazards were already fixed by prior audit trails (#2xxx/#3xxx/#4xxx) and were re-confirmed present. No CRITICAL findings.

The real defects cluster in the **audio-continuity and shared-state mechanics** of the streaming path:

- Two **HIGH** issues, both concerning boundary/shared-state correctness during concurrent or transitioning chunk processing.
- Three **NEW MEDIUM** issues: a stale chunk-count formula fed to the frontend, an in-memory chunk cache that ignores file identity, and a synchronous N+1 running on the event loop during queue changes.
- The rest are LOW: dead code, doc/model drift (notably: the documented "5s equal-power crossfade" **does not run at stream time**), typing looseness, and localhost-scoped hardening gaps.

**Actionable findings (NEW + Regression): 2 HIGH, 3 MEDIUM, 18 LOW.** An additional ~13 findings map to already-open issues (confirmed present, not re-filed).

### Findings by severity (actionable only)

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 0 | — |
| HIGH | 2 | B3-01 (NEW), B4-01 (Regression of #3808) |
| MEDIUM | 3 | B1-01, B3-02, B8-01 (all NEW) |
| LOW | 18 | B1-02, B2-01, B2-02, B2-03/B7-01, B3-03, B3-04, B4-03, B4-04, B4-05, B5-01, B5-05, B5-06, B6-01, B6-05, B7-02, B7-04, B8-02, B9-01 |

### Key themes

1. **Boundary continuity is not what the docs claim.** The "5s equal-power crossfade" model is fiction at stream time (B3-04): the only wired boundary handler is an explicit no-op. Continuity rests entirely on 5s processing context + `LevelManager` gain smoothing — and that smoothing has a gap that re-introduces an audible amplitude step (B3-01).
2. **Shared-processor state is toggled without the lock the fix intended.** The #3808 fix lives only in dead code; the live path races the fingerprint-analysis flag on a factory-shared `HybridProcessor` (B4-01).
3. **Event-loop discipline is nearly universal but has one live hole.** Almost every sync repo call is wrapped in `to_thread`; the queue-changed broadcast is the exception — a synchronous N+1 on the loop during playback (B8-01).
4. **Cache-key divergence.** The in-memory `SimpleChunkCache` omits `file_signature` that the on-disk cache includes, so the two layers disagree after an in-session file change (B3-02).

---

## Route Coverage Matrix

All 19 routers verified: handlers are `async def`, errors translated via `handle_query_error`/local helpers, literal-before-parameterized ordering correct, path-traversal guards present on artwork/upload/download/metadata. Test column from Dimension 9.

| Router | Endpoints | `async` | Validation | Error paths | `response_model` | Tested |
|--------|-----------|---------|------------|-------------|------------------|--------|
| albums | 4 | ✅ | Path ge=1 (#3893) | ✅ | ✗ (#3838) | ✅ |
| artists | 3 | ✅ | ✅ | ✅ | partial | ✅ |
| artwork | 4 | ✅ | ✅ traversal-guarded | ✅ 403/404 | ✗ (#3838) | ✅ |
| cache_streamlined | 5 | ✅ | ✅ | ✅ | 3/5 | ✅ |
| enhancement | 6 | ✅ | ✅ Literal preset | ✅ | 1/6 | ✅ |
| files | 2 | ✅ | ✅ magic-byte+size | ✅ | ✗ (#3838) | ✅ |
| fingerprint_status | 2 | ✅ | ✅ | ✅ | ✗ (#3838) | ✅ |
| health | 2 | ✅ | n/a | n/a | ✅ | ✅ |
| library | 3 | ✅ | ✅ | ✅ | ✗ (#3838) | ✅ |
| library_scan | 1 | ✅ | ✅ | ✅ sanitised | n/a | ✅ |
| metadata | 4 | ✅ | ✅ validate_file_path | ✅ | ✗ (#3838) | ✅ |
| player | 19 | ✅ | ✅ | ✅ | loose `Any` (B5-06) | ✅ |
| playlists | 8 | ✅ | ✅ | ✅ | ✗ (#3838) | ⚠️ mocked only (B9-01) |
| processing_api | 9 | ✅ | ✅ | ✅ | 1/9 | ✅ |
| settings | 5 | ✅ | ✅ range/unknown-field | ✅ | partial | ✅ |
| similarity | 11 | ✅ | ✅ | ✅ redaction/429 | 4/11 | ✅ |
| system (`/ws`) | 1 WS | ✅ | ✅ | ✅ | n/a | ✅ |
| tracks | 6 | ✅ | ✅ | ✅ | ✗ (#3838) | ✅ |
| wav_streaming | 2 | ✅ | ✅ | ✅ | 1/2 | ✅ |

**Structural note (B1-02, LOW):** 8 of 19 routers (player, playlists, enhancement, artwork, files, wav_streaming, library, system) create their `APIRouter` at **module scope** and decorate onto it inside the factory, rather than the isolated per-factory pattern the other 11 use (`metadata.py:87` documents "fresh router … avoids route pollution"). No production effect (each factory runs once) but a test-isolation / latent duplicate-registration hazard.

---

## Findings

### HIGH

#### B3-01: `LevelManager` no-adjustment branch snaps gain to unity, re-introducing the boundary step #3831 fixed
- **Severity**: HIGH
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/level_manager.py:206-214` (else branch) vs `:162-204` (adjustment branch)
- **Status**: NEW
- **Description**: Because the stream-time crossfade is a no-op (B3-04), `LevelManager.smooth_transition` is the *only* thing smoothing chunk boundaries. Its #3831 fix ramps `prev_gain → new_gain` over the first 50 ms **only when an adjustment fires**. An adjusted chunk holds a non-zero corrective gain flat across its body (`env[ramp_len:] = new_gain`). When the next chunk is within tolerance, the else branch returns it **unchanged at unity gain with no ramp** and records `gain 0.0`. So the previous chunk ends at e.g. `-3.5 dB` and the next begins at `0 dB` on contiguous source audio — a multiplicative amplitude step at the exact boundary.
- **Evidence**:
  ```python
  else:   # level change acceptable
      self.rms_history.append(current_rms)
      self.gain_history.append(0.0)
      return chunk, 0.0, False   # unity gain, NO ramp out of prev chunk's held gain
  ```
- **Impact**: Audible click / level "pop" at any adjusted→unadjusted boundary — common on material with a transient-loud section returning to normal. Server sends `crossfade_samples=0` (#2188) so the client does not mask it. `required_adjustment_db` is uncapped, so the step can be several dB. Meets the "audible artifact ⇒ at least HIGH" rule.
- **Siblings**: adjustment→adjustment IS continuous (ramps from `gain_history[-1]`); B3-03 is the cache-hit variant of the same gain-state bookkeeping gap.
- **Suggested Fix**: Always build an envelope ramping `prev_gain → target` (target = 1.0 in the no-adjustment case) whenever `gain_history[-1] != 0`, so every chunk's leading 50 ms ramps out of the previous held gain instead of snapping.

#### B4-01: Shared-processor fingerprint-analysis toggle race in the LIVE chunk path (the #3808 fix is dead code)
- **Severity**: HIGH
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/audio_processing_pipeline.py:180-238` (live) vs dead fix in `auralis-web/backend/core/chunked_processor.py:406-468`
- **Status**: Regression of #3808
- **Description**: The production path `ChunkedAudioProcessor.process_chunk → _process_chunk_core → AudioProcessingPipeline.apply_enhancement` mutates the shared processor's `processor.content_analyzer.use_fingerprint_analysis = False` and restores it in a `finally` **without holding any lock**. `HybridProcessor.process()` only takes `_process_lock` *inside* `_process_impl`, so the flag set/restore is outside that lock. The #3808 fix that wraps set+process+restore in `_process_lock` lives ONLY in `_process_chunk_with_hybrid_processor`, which has **zero callers** (dead code).
- **Evidence**:
  ```python
  # audio_processing_pipeline.py — live path, NO lock around the toggle
  if original_setting is not None:
      processor.content_analyzer.use_fingerprint_analysis = False
  try:
      processed = processor.process(audio)   # _process_lock only held INSIDE process()
  finally:
      if original_setting is not None:
          processor.content_analyzer.use_fingerprint_analysis = original_setting
  ```
- **Impact**: The global `ProcessorFactory` singleton hands the **same** `HybridProcessor` to concurrent `ChunkedAudioProcessor` instances (realistically `StreamlinedCacheWorker` building Tier-2 cache in one `to_thread` while `stream_enhanced` processes chunks in another). Interleaved set/restore corrupts the shared flag: thread B captures A's already-`False` as its "original", A restores to `True`, B processes with fingerprint analysis it meant to disable, and the flag can be left permanently `False` for all future callers → wrong per-chunk DSP mode + persistent corrupted shared state. Thread-safety violation on shared mutable state affecting DSP correctness (not sample-count, so not CRITICAL).
- **Related**: #3919 (`process_audio_async` `processor_lock` always None — async wrapper provides no serialization either).
- **Suggested Fix**: Have `apply_enhancement` acquire `processor._process_lock` around set/process/restore (mirror chunked_processor.py:436), or add a `process_no_fingerprint()` method on `HybridProcessor` that toggles inside its own `_process_lock`; then delete the dead `_process_chunk_with_hybrid_processor`.

### MEDIUM

#### B1-01: Stream metadata `total_chunks` uses the naive formula `content_chunk_count()` exists to replace
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/wav_streaming.py:300` (`get_stream_metadata`)
- **Status**: NEW
- **Description**: The metadata endpoint computes `total_chunks = math.ceil(duration / chunk_interval)` — exactly the naive `ceil(duration / CHUNK_INTERVAL)` that `core/chunk_boundaries.content_chunk_count()` (#4124) was written to correct. With shipped defaults (duration=15, interval=10, overlap=5), for any duration in `(n*INTERVAL, n*INTERVAL + OVERLAP)` the naive formula over-allocates one trailing chunk carrying 0 new content. The router imports `CHUNK_DURATION`/`CHUNK_INTERVAL` from `chunk_boundaries` but not the canonical counter.
- **Evidence**: `total_chunks = math.ceil(duration / chunk_interval)` vs `content_chunk_count = max(1, ceil((duration - OVERLAP_DURATION) / CHUNK_INTERVAL))`.
- **Impact**: The frontend consumes this directly (`playerSlice.ts` `totalChunks`). For affected durations the player requests one extra end-of-track chunk → silence-padded penultimate chunk and/or spurious short/empty final fetch; for `enhanced=False` a tail-near start offset can trip the empty-chunk 400 path. Bounded end-of-track glitch that manifests whenever overlap > 0 (the default).
- **Siblings**: None — only route computing chunk totals; `enhancement.py` already uses `content_chunk_count` (confirming intended SoT).
- **Suggested Fix**: `from core.chunk_boundaries import content_chunk_count; total_chunks = content_chunk_count(duration)`.

#### B3-02: `SimpleChunkCache` key omits `file_signature` — in-memory cache serves stale audio/sample-rate after an in-session file change
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_cache.py:46-50` (`_make_key`)
- **Status**: NEW
- **Description**: The active streaming cache (`SimpleChunkCache`, wired at `audio_stream_controller.py:144`) keys on `(CACHE_VERSION, track_id, chunk_idx, preset, intensity)` with **no `file_signature`**. The on-disk `ChunkCacheManager` and the WAV encoder paths DO include it. If a track's file is modified/replaced while its DB `track_id` is unchanged (re-scan / re-tag mid-session), the on-disk layer correctly misses and reprocesses, but the in-memory cache keeps returning the previously-processed samples and their stored `sample_rate` for the process lifetime.
- **Evidence**:
  ```python
  key_str = f"v{self.CACHE_VERSION}:{track_id}:{chunk_idx}:{preset}:{intensity:.2f}"  # no file_signature
  ```
- **Impact**: Stale processed audio served; if the replacement file has a different sample rate, the cached `(audio, sr)` tuple yields wrong-speed/pitch playback until restart. The two cache layers also disagree (one hits, one misses) for the same logical chunk.
- **Siblings**: On-disk `ChunkCacheManager` keys already include `file_signature` — the fix is to align them.
- **Suggested Fix**: Thread `file_signature` into `SimpleChunkCache._make_key` via `get`/`put`, or invalidate a `track_id`'s in-memory entries when its file signature changes on re-scan.

#### B8-01: `queue_service._broadcast_queue_changed` runs an N+1 of synchronous `get_by_id` on the event loop
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/services/queue_service.py:157-168`
- **Status**: NEW
- **Description**: `_broadcast_queue_changed` is `async def` but hydrates the queue by looping over every entry and calling the **synchronous** `self.library_manager.tracks.get_by_id(tid)` directly (not wrapped in `to_thread`). This is both blocking sync DB I/O on the event loop **and** an N+1 (one query per entry). It fires from all seven queue-mutation paths (set/add/remove/reorder/next/previous/clear — lines 368, 438, 495, 546, 589, 634, 685).
- **Evidence**:
  ```python
  for entry in raw_tracks:
      tid = entry.get('id') or entry.get('track_id')
      if tid is not None and self.library_manager is not None:
          db_track = self.library_manager.tracks.get_by_id(tid)   # sync DB, on loop, per entry
  ```
- **Impact**: A large queue (whole album/library → hundreds–thousands of entries) triggers that many sequential sync queries on the loop on **every** queue change, including `next_track`/`previous_track` during active playback → event-loop stall mid-stream, risking WebSocket send starvation and audible stutter. The sibling `_set_queue_impl` (lines 253-279) was already fixed for this exact pattern (#3554) with batched `get_by_ids` inside `to_thread`; the broadcast path (added for #3492) reintroduced it.
- **Siblings**: Same class as OPEN #3888 (`streamlined_worker` sync `get_by_id` — different location). `TrackRepository.get_by_ids` (`auralis/library/repositories/track_repository.py:245`) already returns `dict[int, Track]`.
- **Suggested Fix**: Collect ids, then a single `await asyncio.to_thread(tracks_repo.get_by_ids, ids)` and hydrate from the map (mirror `_set_queue_impl`).

### LOW

#### B1-02: 8 routers register routes on a module-level shared `APIRouter`
- **Severity**: LOW · **Dimension**: Route Handlers · **Status**: NEW
- **Location**: module-level `router = APIRouter(...)` in `player.py:47`, `playlists.py:30`, `enhancement.py:35`, `artwork.py:29`, `files.py:60`, `wav_streaming.py:48`, `library.py:38`, `system.py:47`
- **Description**: These decorate handlers onto a module-scope router inside their factory; the other 11 routers create a fresh router per factory call (`metadata.py:87` documents why: avoids route pollution). No production effect (each factory runs once), but test-isolation and latent duplicate-registration hazard — a second factory call binds closures/deps that never take effect (FastAPI serves the first-registered handler).
- **Suggested Fix**: Move each `router = APIRouter(...)` inside its `create_*_router()` factory.

#### B2-01: `AudioStreamController.active_streams` is a write-only dead registry
- **Severity**: LOW · **Dimension**: WebSocket Streaming · **Status**: NEW
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:168-169`; writes in `stream_enhanced.py:129-130,295-296`, `stream_normal.py:159-160,316-317`, `stream_seek.py:131-132,289-290`
- **Description**: `active_streams` (and `_active_streams_lock`) is written on stream start / popped in `finally` in all three entry points but **never read** anywhere. Because the wrappers build a fresh `AudioStreamController` per request, it never holds >1 entry. The real cancellation registry is `routers/system.py::_active_streaming_tasks`. Dead code implying a per-controller cancellation mechanism that doesn't exist, plus a needless async lock acquire per stream.
- **Suggested Fix**: Remove `active_streams` + `_active_streams_lock` and the six write sites.

#### B2-02: `handle_stop` leaves stale `pause_events`/`flow_events`/`active_track_ids` entries
- **Severity**: LOW · **Dimension**: WebSocket Streaming · **Status**: NEW
- **Location**: `auralis-web/backend/ws_handlers/playback_control.py:63-75`
- **Description**: `handle_stop` pops only `state.active_tasks[ws_id]`; unlike `_cancel_prior_task` and `teardown_connection` it does not pop `active_track_ids`/`pause_events`/`flow_events`. Entries dangle until the next play/seek recreates them or disconnect cleans them. Harmless (post-stop pause/resume is a no-op; play-dedup still requires a live task) and bounded to one entry per `ws_id`.
- **Suggested Fix**: In `handle_stop`, inside the same lock block, also pop the three event/track dicts to match the other teardown paths.

#### B2-03 / B7-01: Temp directory leaked when FFmpeg decode fails during normal streaming
- **Severity**: LOW · **Dimension**: WebSocket Streaming / Error Handling · **Status**: NEW
- **Location**: `auralis-web/backend/core/stream_normal.py:105-119, 319-334`
- **Description**: (Found independently by Dimensions 2 and 7 — merged.) On the compressed-format path, `tempfile.mkdtemp(prefix='auralis_stream_')` (line 108) creates the dir, but `temp_wav_path` is only assigned after `load_audio` + `sf.write` succeed (line 113). If `load_audio` (corrupt/unsupported file, FFmpeg error) or the WAV write raises, `temp_wav_path` stays `None`, so the `finally` (`if temp_wav_path:`) skips `shutil.rmtree` and the freshly-created dir is orphaned.
- **Impact**: One empty orphan temp dir per failed compressed normal-stream. Self-healing: `config/startup.py::reclaim_leftover_stream_temps` sweeps `auralis_stream_*` at next boot (#3877), so bounded to a session.
- **Siblings**: PCM path never mkdtemp's; enhanced path creates no temp dir; `ffmpeg_loader.load_with_ffmpeg` uses `mkstemp`+`finally` unlink correctly.
- **Suggested Fix**: Assign `temp_dir` to an outer-scope variable at creation and `rmtree` it in `finally` regardless of WAV-write success (or try/except that removes it before re-raising).

#### B3-03: Cache-hit level recording appends `gain 0.0`, desyncing the boundary ramp
- **Severity**: LOW · **Dimension**: Chunked Processing · **Status**: NEW
- **Location**: `auralis-web/backend/core/level_manager.py:152-160` via `chunked_processor.py:381-403` (`note_cached_chunk_level`) and `stream_chunk_ops.py:87-92`
- **Description**: When a chunk is served from `SimpleChunkCache`, `note_cached_chunk_level` calls `smooth_transition(apply_adjustment=False)` (#3832) which appends `gain_history.append(0.0)` regardless of the gain actually baked into the cached samples. A subsequent cache-MISS chunk reads `gain_history[-1] == 0.0` as its `prev_gain` and ramps from unity even though the emitted cached chunk ended at a non-zero gain. Cache→miss variant of B3-01, bounded to a single boundary.
- **Suggested Fix**: Persist the applied `gain_db` alongside cached chunks so `note_cached_chunk_level` restores the true trailing gain into `gain_history`.

#### B3-04: Documented "5s equal-power crossfade" does not run at stream time; the crossfade helpers are dead and equal-gain, not equal-power
- **Severity**: LOW · **Dimension**: Chunked Processing · **Status**: Existing #3878 + #3879 (extends with new facts)
- **Location**: `stream_chunk_ops.py:143-174` (`apply_boundary_crossfade` no-op); `chunk_operations.py:273-333` and `chunked_processor.py:849-898` (`apply_crossfade*`, no callers)
- **Description**: The model/docstrings describe a "5s overlap equal-power (sqrt) crossfade", but (a) the only wired boundary handler `apply_boundary_crossfade` is an explicit no-op — chunks are emitted non-overlapping and NOT crossfaded; (b) both remaining crossfade helpers have no callers; (c) both use `fade_out=cos²(t)`/`fade_in=sin²(t)` (equal-GAIN → −3 dB power dip for uncorrelated content) despite "equal-power" comments — no `sqrt` curve exists in `core/`. #3878 covers `ChunkOperations.apply_crossfade`'s mislabel, #3879 the module-level dead copy. **New facts:** `ChunkOperations.apply_crossfade` is ALSO dead, and the top-level model/doc asserts a stream-time crossfade that never runs. No runtime defect on its own (continuity is context + LevelManager, per B3-01) but doc drift + a trap for a future caller.
- **Suggested Fix**: Fold `ChunkOperations.apply_crossfade` into the #3879 dead-code removal; correct WEBSOCKET/model docs to "context-continuous + level-smoothed, not crossfaded". If crossfade is ever reinstated, use a true equal-power curve (`cos(t)`/`sin(t)`).

#### B4-03: `streamlined_worker._processor_cache` accessed without a lock across tasks
- **Severity**: LOW · **Dimension**: Processing Engine · **Status**: NEW
- **Location**: `auralis-web/backend/core/streamlined_worker.py:289-305`, eviction at `:220-227`
- **Description**: `_process_chunk` does `get(cache_key)` → `await to_thread(ChunkedAudioProcessor, ...)` → `cache[cache_key] = processor`. `trigger_immediate_processing` (router task) and `_worker_loop` can reach this concurrently; the `await` between check and set means both may miss and each build a `ChunkedAudioProcessor` (redundant SoundFile metadata open + fingerprint/DB lookup), one silently overwritten. No corruption (single-threaded loop; heavy `HybridProcessor` is factory-owned/`.close()`-managed) — wasted CPU/IO only.
- **Suggested Fix**: Guard the check-and-set with an `asyncio.Lock`, or accept and document the redundant construct.

#### B4-04: `ProcessingEngine._return_processor` uses plain-dict FIFO eviction, not LRU, and skips `.close()`
- **Severity**: LOW · **Dimension**: Processing Engine · **Status**: NEW
- **Location**: `auralis-web/backend/core/processing_engine.py:345-355`
- **Description**: The processor cache is a plain `dict`; eviction pops `list(self.processors)[0]` (insertion-order FIFO, evicting oldest-inserted regardless of recency), and drops instances without `.close()`. The sibling `ProcessorFactory` uses `OrderedDict` + `move_to_end` LRU (#3515) and `.close()` on evict (#3746). If this cache ever exceeds 5 distinct configs, a hot processor can be evicted while a cold one survives, and evicted processors leak fingerprint executor threads. Low likelihood on desktop.
- **Related**: #4250 (split-out-of-processing_engine backlog).
- **Suggested Fix**: Switch `self.processors` to `OrderedDict`, `move_to_end` on hit, `.close()` on evict — reuse the factory pattern.

#### B4-05: `apply_enhancement` intensity blend truncates to `min_len` instead of asserting sample count
- **Severity**: LOW · **Dimension**: Processing Engine · **Status**: NEW
- **Location**: `auralis-web/backend/core/audio_processing_pipeline.py:229-237`
- **Description**: For `intensity < 1.0` the blend does `min_len = min(len(audio), len(processed))` and slices both. If the processor ever returned a different-length array, this silently DROPS trailing samples rather than surfacing the invariant violation — a latent gapless-glitch mask. The invariant is currently upheld upstream by `HybridProcessor`, so defensive-only today.
- **Suggested Fix**: Assert `len(processed) == len(audio)` before blending (log+raise) instead of silently truncating.

#### B5-01: Orphan `api.ts` REST request/response types diverge from real backend contracts
- **Severity**: LOW · **Dimension**: Schema Consistency · **Status**: NEW (extends dead-REST-surface effort, PR #7 / commit 7ecd34c9)
- **Location**: `auralis-web/frontend/src/types/api.ts` (SimilarTrack:315, SimilarTracks{Response:320,Request:309}, LibraryScan{Request:141,Response:145}, Metadata*{157,166,171,177}, EnhancementSettingsResponse:193) vs backend `routers/similarity.py:70`, `schemas.py:290`, `routers/metadata.py:35-63,360-367`, `routers/enhancement.py:86-89`
- **Description**: Several `api.ts` types describe contracts that no longer match the backend and are consumed by no fetch site (real consumers inline the shape or use a service-local type): `SimilarTrack` nested vs backend flat; `LibraryScanRequest {directory?}` vs backend `{directories: list[str]}`; `LibraryScanResponse {scan_id,status,progress}` vs backend `ScanResultResponse {files_*,duration,...}`; `MetadataBatchUpdate*` structurally incompatible; `EnhancementSettingsResponse` flat vs backend `{message, settings:{...}}`. No runtime impact today (all unused) but a latent trap — importing them yields a 422 or `undefined`, and it misleads contract audits.
- **Suggested Fix**: Delete the unused types or realign to actual backend shapes and re-point consumers (follow-up to the dead-REST-surface retirement).

#### B5-05: `GraphStatsResponse.build_time_seconds` nullable on backend, non-nullable on frontend
- **Severity**: LOW · **Dimension**: Schema Consistency · **Status**: NEW
- **Location**: `auralis-web/backend/routers/similarity.py:100` (`build_time_seconds: float | None = None`) vs `auralis-web/frontend/src/services/similarityService.ts` (`GraphStats.build_time_seconds: number`)
- **Description**: Backend can return `null` (graph built without timing) but the frontend type declares required non-null `number`; the endpoint's `response_model=GraphStatsResponse | None` also allows a fully-null body the frontend doesn't model. `stats.build_time_seconds.toFixed()` could hit null. Low likelihood.
- **Suggested Fix**: `build_time_seconds?: number | null` in the frontend type and handle the null-body case.

#### B5-06: Player queue response models use loose `Any` typing, defeating the schema contract
- **Severity**: LOW · **Dimension**: Schema Consistency · **Status**: NEW
- **Location**: `auralis-web/backend/routers/player.py:154-161` (`QueueInfoResponse.tracks: list[Any]`, `current_track: Any | None`)
- **Description**: Despite a `response_model`, `tracks: list[Any]` / `current_track: Any` means no schema on the track payload — FastAPI serializes whatever the engine returns, and OpenAPI/validation is nominal only. The canonical `TrackInfo` (`player_state.py`) / `TrackBase` (`schemas.py:327`) should be reused.
- **Suggested Fix**: Type `tracks: list[TrackInfo]` and `current_track: TrackInfo | None`.

#### B6-01: OpenAPI schema JSON still served at `/openapi.json` in production despite Swagger/ReDoc being disabled
- **Severity**: LOW · **Dimension**: Middleware & Config · **Status**: NEW
- **Location**: `auralis-web/backend/config/app.py:38-48`
- **Description**: `create_app()` sets `docs_url`/`redoc_url` to `None` in production "to not leak the full API schema (fixes #2418)", but leaves `openapi_url` at its default `/openapi.json`, which FastAPI still serves. Swagger UI is gone yet `GET /openapi.json` returns the complete schema in production. The code does not achieve its own stated hardening goal. Localhost-only binding keeps real exposure minimal.
- **Suggested Fix**: Pass `openapi_url="/api/openapi.json" if is_dev else None` to `FastAPI(...)`.

#### B6-05: Startup logs absolute home/database paths at INFO level
- **Severity**: LOW · **Dimension**: Middleware & Config · **Status**: NEW
- **Location**: `auralis-web/backend/config/startup.py:204,209`
- **Description**: #3844 demoted path-validation logging to DEBUG because absolute paths are sensitive and persist to the on-disk electron-log. Startup path logs (`Database directory ready: {music_dir}`, `Database location: {database_path}`) share that exposure but still log at INFO (once per launch). Not covered by the #3844 fix.
- **Suggested Fix**: Demote the two path lines to `logger.debug`, or log only the basename.

#### B7-02: `FingerprintGenerator` process-isolation docstring diverges from ThreadPool reality; hung DSP thread not reclaimable on timeout
- **Severity**: LOW · **Dimension**: Error Handling · **Status**: NEW
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:124,158,243-281`
- **Description**: Docstrings claim fingerprinting runs "in a subprocess, completely isolated" via `ProcessPoolExecutor`, but the code uses `ThreadPoolExecutor` + `run_in_executor`. On `asyncio.wait_for(timeout)` firing, the future is cancelled but the worker thread keeps running the Rust DSP to completion (threads can't be force-killed). A pathological file that hangs the DSP permanently consumes one executor thread; repeats can exhaust the pool. The crash-isolation the docstring implies is not present. Same limitation in `processing_engine.py:479-494` and per-chunk timeouts.
- **Suggested Fix**: Correct the docstrings to the ThreadPoolExecutor + GIL-releasing-Rust design, or restore true `ProcessPoolExecutor` isolation if crash containment is actually wanted.

#### B7-04: Exceptions raised inside `BaseHTTPMiddleware` bypass the JSON 500 formatter
- **Severity**: LOW · **Dimension**: Error Handling · **Status**: NEW
- **Location**: `auralis-web/backend/config/middleware.py:26-163`; `config/app.py:75-81`
- **Description**: `@app.exception_handler(Exception)` only wraps route handling; exceptions raised inside a `BaseHTTPMiddleware.dispatch` (NoCache / SecurityHeaders / RateLimit) are handled by Starlette's `ServerErrorMiddleware` and return a plaintext `Internal Server Error` WITHOUT the JSON `{"detail": ...}` shape the frontend expects (and without security headers). Very low in practice — the middleware bodies are trivial and already None-guarded — but a future raising path there produces an off-contract 500.
- **Suggested Fix**: Wrap each `dispatch` body in try/except returning `JSONResponse(500, {"detail": "Internal server error"})`.

#### B8-02: `AudioContentPredictor._load_chunk_fast`/`_extract_features` perform blocking file I/O and full-file decode on the event loop
- **Severity**: LOW · **Dimension**: Performance · **Status**: NEW
- **Location**: `auralis-web/backend/services/audio_content_predictor.py:133-183` (load), `256+` (`_extract_features`)
- **Description**: Both are `async def` but call `soundfile.SoundFile(...).seek()/read()` (primary) and `unified_loader.load_audio(filepath)` (fallback — decodes the entire file) plus NumPy feature math directly in the coroutine, no `to_thread`. **Currently latent** — no live streaming/router path invokes `analyze_chunk_fast` (only `self_tuner.py:218` / `learning_system.py:325` fetch the predictor for affinity rules). Downgraded to LOW; becomes MEDIUM if ever wired into streaming preset-prediction.
- **Suggested Fix**: Wrap the soundfile read and `load_audio` fallback in `to_thread`; prefer the seek+partial-read path (avoid full-file decode for one chunk).

#### B9-01: Playlists router has zero repo-backed test coverage — both dedicated test files are hard-skipped on a false premise
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW
- **Location**: `tests/backend/test_playlist_operations.py:1-30`, `tests/backend/test_playlist_integration.py`; router `auralis-web/backend/routers/playlists.py` (8 endpoints)
- **Description**: Both files apply a module-level `pytest.mark.skip(reason="… PlaylistRepository not yet implemented")` and skip 100% of tests. The premise is false: `auralis/library/repositories/playlist_repository.py` exists and all 8 endpoints are wired. The only executed playlist coverage is `test_main_api.py` with `Mock()` repos — so the real repository→router serialization path (ordering, cascade delete, track-add dedup) is never exercised end-to-end.
- **Related**: #4234 (rewrite library integration tests) — but playlist-specific and distinct.
- **Suggested Fix**: Remove the stale `pytestmark` and run against a temp-DB `PlaylistRepository`, or delete and add a repo-backed workflow test.

---

## Existing issues confirmed present (not re-filed)

These were matched to open issues during dedup and verified still present; listed for completeness.

| Area | Issue | Note |
|------|-------|------|
| Route Handlers | #3893 | Path int params lacking `Path(..., ge=1)` |
| Route Handlers / Schema | #3838 | ~50 endpoints (issue says ~28) return raw `dict`, no `response_model` — count understated |
| Route Handlers | #3886 | `QueueStatusResponse.total`/`cancelled` never populated |
| Route Handlers | #4304 | 35 raw `HTTPException(404)` bypass `NotFoundError` helper |
| Route Handlers | #3896 | `JobStatusResponse.status: str` should be `Literal`/enum |
| Route Handlers | #3895 | `/api/processing/presets` mixes camelCase into snake_case body |
| Route Handlers | #3910 | `system.py:815` reflects caller message type unsanitised |
| WebSocket | #3870 | Heartbeat ping not guarded by `_is_websocket_connected` |
| WebSocket | #3869 | Receive loop treats client `heartbeat` frames as pong proof |
| WebSocket | #3868 | `subscribe_job_progress` closure captures unvalidated websocket |
| WebSocket | #3780 / #3774 | `seq` vs `sequence` naming; `audio_chunk_meta.seq` not validated by frontend |
| WebSocket | #3873 | `WebSocketMessageType` `extra='allow'` misses pause/resume/stop/buffer_* |
| WebSocket | #3906 | `system.py` WS `finally` swallows cleanup/disconnect errors silently |
| WebSocket | #3884 | `proactive_buffer.buffer_presets_for_track` dead |
| Chunked | #3878 / #3879 / #3880 | crossfade mislabel / dead code / `_chunk_tails` (see B3-04) |
| Chunked | #4289 / #4284 / #4280 / #3883 / #3882 / #4245 | geometry defaults, dup constant, numpy hygiene, hardcoded channels=2, god-class split |
| Processing Engine | #3490 | Offline jobs drop UI eq/dynamics/level/genre settings (B4-02) |
| Processing Engine | #3919 | `process_audio_async` `processor_lock` always None |
| Schema | #3892 / #3891 / #4306 / #4315 | dup `PaginatedResponse` / dup `CacheStatsResponse` / dead playlist serializers / dead artist compat fields |
| Middleware | #3900 / #3899 / #4012 | CSP `unsafe-inline` / `is_dev_mode` duplicated / unused startup imports |
| Error Handling | #3912 | Encoder errors surface as generic 500 |
| Performance | #3888 | `streamlined_worker` sync `get_by_id` from async (sibling of B8-01) |
| Test Coverage | #3696 / #4282 | No real-decode FFmpeg format tests / 4 dead streaming-integration classes (wrong import) |

### Verified fixed (regression checks passed — do NOT re-file)
- **#3885** `LevelManager.rms_history`/`gain_history` unbounded → now `deque(maxlen=256)`.
- **#3887** `MasteringTargetService` cache → `move_to_end` LRU present.
- **#3888** `streamlined_worker.get_by_id` → wrapped in `to_thread` (note B8-01 is a *different* location).
- **#3746** `ProcessorFactory` closes evicted processors.
- **#3877** leftover `auralis_stream_*` / `auralis_chunks` temp sweeps on boot.
- CORS explicit allowlist (no wildcard+credentials), middleware ordering, StaticFiles traversal-safety, lifespan rollback/teardown — all present and correct.

---

## Relationships & Shared Root Causes

- **B3-01, B3-03, B3-04 share one root cause:** the stream-time crossfade is a no-op (B3-04), so `LevelManager` gain smoothing is the *sole* boundary treatment — and its gain-state bookkeeping has two gaps (B3-01 the live no-adjustment snap, B3-03 the cache-hit `gain 0.0`). Fixing B3-01's "always ramp from `gain_history[-1]`" logic and persisting baked-in gain (B3-03) together close the audible-step surface. Documentation should be corrected to match reality (B3-04).
- **B4-01 and B4-03/B4-04 are shared-processor lifecycle issues:** B4-01 is the correctness-critical one (unlocked toggle on a factory-shared processor); B4-03/B4-04 are the same "cache/lifecycle discipline diverges from the well-built `ProcessorFactory`" theme at lower stakes. `ProcessorFactory` is the reference pattern to converge on.
- **B8-01 and #3888** are the same anti-pattern (sync `get_by_id` from async context) in two services; both should adopt `get_by_ids` in `to_thread`.
- **B1-01 and #4124** — the naive chunk-count formula that `content_chunk_count()` was created to replace persists in one router; a grep for `ceil(.*/.*interval)` should confirm no third site.
- **B2-03/B7-01, B6-01, B6-05, B7-02, B7-04** are a cluster of localhost-scoped hardening/hygiene gaps and doc drift — individually LOW, worth a single sweep.

---

## Prioritized Fix Order

1. **B4-01 (HIGH, Regression #3808)** — shared-processor toggle race. Wrap the toggle in `_process_lock` (or add `process_no_fingerprint()`) and delete the dead fix. Correctness-critical under the realistic worker+stream concurrency; the intended fix already exists, just unwired.
2. **B3-01 (HIGH)** — boundary gain snap. Make the no-adjustment branch ramp from `gain_history[-1]` to unity. Directly audible; small, localized change.
3. **B8-01 (MEDIUM)** — queue-broadcast N+1 on the loop. Batch via `get_by_ids` in `to_thread`; the sibling `_set_queue_impl` is a copy-paste template. Affects live playback responsiveness.
4. **B3-02 (MEDIUM)** — `SimpleChunkCache` file_signature. Thread it into the key to stop stale-audio/wrong-sample-rate after in-session file changes.
5. **B1-01 (MEDIUM)** — swap `math.ceil(...)` for `content_chunk_count(duration)` in stream metadata (one line).
6. **B3-03 + B3-04 (LOW, same subsystem as #2)** — do alongside B3-01: persist baked-in gain and fix the crossfade docs/dead code.
7. **LOW hardening sweep** — B6-01 (`openapi_url`), B6-05 (log demotion), B7-04 (middleware try/except), B2-03/B7-01 (temp-dir cleanup), B7-02 (docstring), B2-01/B2-02 (WS dead code / stale entries), B4-03/B4-04/B4-05 (processor-cache discipline), B5-01/B5-05/B5-06 (schema typing), B9-01 (un-skip playlist tests), B1-02 (router isolation).

---

*Report generated by `/audit-backend`. To create GitHub issues for the NEW and Regression findings:*
```
/audit-publish docs/audits/AUDIT_BACKEND_2026-07-12.md
```
