# Backend Audit — 2026-08-24

**Scope**: `auralis-web/backend/` — routers, WebSocket streaming, chunked
processing, processing engine, schemas, middleware, caching, seek/buffering.
**Depth**: deep (full call-graph tracing, live-code reproduction where
feasible). **Dimensions run**: all 11. **Prior report**:
`docs/audits/AUDIT_BACKEND_2026-08-13.md` (11 days old).

## Executive Summary

47 NEW findings survived independent verification: **0 CRITICAL, 5 HIGH, 24
MEDIUM, 18 LOW**. Two more findings are **regressions of CLOSED issues**
(#4765, #4568). A large number of additional candidate findings were
confirmed still present but are **not** re-reported here because they already
match an OPEN GitHub issue — see the dedup appendix.

**Three themes dominate this run:**

1. **The 2026-08-13 audit's findings were never filed as issues, and remain
   unfixed 11 days later.** B7-1 (recommendation timeout), B9-1/B9-2 (vacuous
   security tests), B10-1 through B10-5 (all five caching bugs), B11-1/B11-2/B11-3
   (seek leak, seek-to-end, duration mis-report), and B6-1 (a stale comment)
   all still reproduce verbatim against current code, and none of them have a
   matching entry in `gh issue list`. This audit restates all of them as NEW
   findings (they are, by GitHub's bookkeeping) and flags the process gap:
   audit reports without a following `/audit-publish` pass silently expire.
2. **Two closed issues have regressed.** #4765 (scan-folder allowlist
   registration) and #4568 (album-detail track rows showing blank
   artist/album) were both fixed once and are both broken again, reintroduced
   by refactors that landed after the fixes shipped (`#4670`'s router
   hoisting, and a missing `selectinload` addition alongside #5170's genre
   fix respectively). Neither refactor had a regression test pinning the
   original fix's behavior.
3. **Test coverage's real gap is not absence, it's silent decay.** Dimension
   9 found that router/endpoint happy-path coverage is broad and mature, but
   141 of 216 (~65%) of the CI ratchet's known-failure baseline is backend
   code, and the highest-value entries are tests that *name* a security or
   reliability guarantee (path traversal, WS message-size/depth limits,
   reconnect state push, streaming message order) and have quietly stopped
   verifying it — masked by the ratchet rather than caught by it.

Two pairs of findings from different dimensions turned out to be the same
underlying bug, found independently — noted and merged below rather than
double-counted: the missing-timeout bug on `recommendation_service.py`
(Dimensions 7 and 8), and the seek-past-duration silent-zero-audio bug
(Dimensions 3 and 11).

No path traversal, arbitrary-file-read, SQL injection, or CORS-wildcard
findings were found in this run — the security-sensitive route/middleware
surface remains sound at the code level (Dimension 9's findings are about
the *tests* for that surface having decayed, not the surface itself).

---

## Route Coverage Matrix

Derived from `auralis-web/backend/config/routes.py` (20 registered routers,
101 REST routes total). "Findings" lists this audit's new findings touching
that router; a router with no findings was swept and found clean.

| Router | Async | Validated | DI pattern | New findings |
|---|---|---|---|---|
| albums | ✅ | ✅ | per-request | BE-2 (album tracks blank artist/album) |
| artists | ✅ | ✅ | per-request | — |
| artwork | ✅ | ✅ | module `_deps` (BE-4) | BE-4 |
| cache_streamlined | ✅ | ✅ | per-request | BE-16 (clear never deletes disk), BE-19 (no unified clear) |
| enhancement | ✅ | ✅ | per-request | BE-14/BE-21 (recommendation timeout, shared w/ services) |
| files | ✅ | ✅ | module `_deps` (BE-4) | BE-4 |
| fingerprint_queue | ✅ | ✅ | per-request | BE-3 (thread-unsafe enqueue) |
| fingerprint_status | ✅ | ✅ | per-request | — |
| health | ✅ | n/a | per-request | — |
| library | ✅ | ✅ | module-level `APIRouter` (Existing #5177/#4361) | BE-19 (reset doesn't clear caches) |
| library_scan | ✅ | ✅ | per-request | BE-3 (thread-unsafe enqueue) |
| metadata | ✅ | ✅ | module `_deps` (BE-4) | BE-8 (batch success:true), BE-9 (unbounded fields), BE-11 (filepath leak) |
| player | ✅ | ✅ | per-request | BE-10 (volume 400 vs 503), BE-22 (dead proactive-buffer plumbing) |
| playlists | ✅ | ✅ | module `_deps` (BE-4) | BE-4, BE-5 (add-tracks 400), BE-7 (falsy=404 ambiguity) |
| processing_api | ✅ | ✅ | ContextVar (correct pattern) | BE-12 (jobs total field), BE-13 (upload comment), BE-15 (list vs status shape) |
| settings | ✅ | ✅ | per-request | BE-1 (scan-folder allowlist dead code — regression) |
| similarity | ✅ | ✅ | ContextVar (correct pattern) | BE-3 (thread-unsafe enqueue) |
| similarity_graph | ✅ | ✅ | per-request | — |
| system | ✅ | ✅ | module-level `APIRouter` (Existing #5177/#4361) | — |
| tracks | ✅ | ✅ | per-request | — |

All 101 routes are `async def`; no unconstrained `int` path parameters
remain anywhere in the tree (#3893 complete); no route registered without a
`response_model` except two deliberate binary-response exceptions (file
download, artwork image).

---

## Findings

### HIGH

#### BE-14: Per-play mastering-recommendation analysis has no timeout — a single bad file can exhaust the shared thread pool
- **Severity**: HIGH
- **Dimension**: Error Handling / Performance (found independently by both; merged)
- **Location**: `auralis-web/backend/services/recommendation_service.py:76-109,135-158`; REST twin `auralis-web/backend/routers/enhancement.py:590-636`
- **Status**: NEW (restates prior audit's B7-1, never filed as a GitHub issue — no match in `issues.json`)
- **Description**: `generate_and_broadcast_recommendation()` and `get_recommendation_for_track()` construct a `ChunkedAudioProcessor` and call `get_mastering_recommendation()` inside a bare `await asyncio.to_thread(_analyze)` — no `asyncio.wait_for(...)` timeout. This fires on **every track play** (both `handle_play_enhanced` and `handle_play_normal`, plus `POST /api/player/load`), not an edge case. Every sibling construction of the same `ChunkedAudioProcessor` on the streaming paths (`stream_enhanced.py`, `stream_seek.py`, `stream_chunk_ops.py`) wraps the identical constructor in `asyncio.wait_for(..., timeout=CHUNK_PROCESS_TIMEOUT)` specifically to guard "file may be corrupt or on slow storage" (#2125/#3852) — this one caller was never brought in line. The underlying hang is real: `ChunkedAudioProcessor.__init__` → `_load_metadata()` bounds FFmpeg-probed formats to 30s but calls `sf.info()` with **no timeout at all** for natively-decodable formats.
- **Evidence**:
  ```python
  # recommendation_service.py:96,155 — both call sites, no wait_for
  rec_dict = await asyncio.to_thread(_analyze)
  # vs. every streaming entry point:
  processor = await asyncio.wait_for(
      asyncio.to_thread(controller.chunked_processor_class, ...),
      timeout=_asc.CHUNK_PROCESS_TIMEOUT,
  )
  ```
- **Impact**: A corrupt-header file, or a track on removable/network storage that disappears mid-read, permanently pins an `IO_EXECUTOR` worker the first time it's played — the surrounding `except Exception` never runs because the hang is inside the blocking call itself. Since this fires unconditionally on every play, repeated plays of one or more bad files exhaust the shared 8-worker pool, queuing every other `to_thread` call (repository reads, thumbnailing, settings I/O, chunk reads) behind the wedged threads — a single bad file degrades unrelated concurrent requests process-wide.
- **Suggested Fix**: Wrap both call sites in `asyncio.wait_for(..., timeout=CHUNK_PROCESS_TIMEOUT)`, catching `TimeoutError` and falling back to the existing "recommendations are optional, return `{}`" behavior. Apply the same wrap to `routers/enhancement.py`'s `_run_recommendation`.

#### BE-16: `POST /api/cache/clear` and `DELETE /api/cache/track/{id}` never delete on-disk WAV chunks
- **Severity**: HIGH
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:131-159`, `cache/manager.py:676-710`, `core/chunk_path_cache.py:77-101`
- **Status**: NEW (restates prior audit's B10-2, never filed)
- **Description**: Both endpoints call only `StreamlinedCacheManager.clear_all()`/`.clear_track()`, which empty the `tier1_cache`/`tier2_cache` **dicts** — bookkeeping, not the bytes. Neither ever `unlink()`s a file. `ChunkPathCache.lookup_cached()` checks `wav_chunk_path.exists()` on disk independent of any in-memory dict, so clearing the dicts has no effect on it. A second cleanup path that would actually help — `ChunkCacheManager.clear_track_cache()` — is called from nowhere in production, and even it only pops dict entries rather than unlinking files.
- **Evidence**: `grep -rn "clear_track_cache" auralis-web/backend` shows zero callers outside its own docstring; no `force_reprocess`/`bypass_cache` flag exists anywhere in the codebase.
- **Impact**: Cache-clear — the user's primary troubleshooting lever for "the cached audio sounds wrong, clear and retry" — is a no-op for anything already on disk. The exact same bytes are served on the very next request while the user believes they forced a clean reprocess. Combined with BE-17 below, there is no working escape hatch at all.
- **Suggested Fix**: Have `clear_all()`/`clear_track()` also delete the corresponding on-disk WAV files (paths are known before the dicts are cleared), or wire the router through `ChunkCacheManager.clear_track_cache()` extended to `unlink()` matched paths.

#### BE-17: `StreamlinedCacheManager`'s in-memory chunk-cache key omits the file signature
- **Severity**: HIGH
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:96-99,339,394`
- **Status**: NEW (restates prior audit's B10-1, never filed)
- **Description**: `StreamlinedCacheManager` is the production-wired chunk cache (`config/startup.py` injects it as the singleton `StreamlinedCacheWorker` consults). Its key is still `f"{track_id}_{preset_key}_{intensity:.1f}_{chunk_idx}"` — no file signature. `SimpleChunkCache` (the fallback layer) and the on-disk `ChunkPathCache`/`ChunkCacheManager` tier both already carry the #4358 fix (`file_signature` is part of both key and filename); `StreamlinedCacheManager` was never given the same fix, and it is consulted *before* the signature-aware disk lookup.
- **Evidence**: `SimpleChunkCache`'s docstring: *"v4: key now includes file_signature (#4358)"*; `StreamlinedCacheManager.get_chunk()`/`add_chunk()` build the signature-less key above with no such parameter on the API at all.
- **Impact**: A user who edits/replaces a track's audio file in place (same `track_id`, e.g. a re-master landing at the identical path) keeps hearing the pre-edit cached audio for the remainder of the backend's uptime — until LRU eviction happens to reclaim the entry — even though the on-disk tier and `SimpleChunkCache` would both correctly detect the change.
- **Suggested Fix**: Add `file_signature` to `CachedChunk`, `CachedChunk.key()`, and the `get_chunk()`/`add_chunk()` signatures, mirroring `SimpleChunkCache` and the on-disk key shape.

#### BE-18: Every seek or play of a non-natively-seekable format (m4a/aac/wma) leaks a full-track temp WAV
- **Severity**: HIGH
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/stream_seek.py:428-437`, `stream_enhanced.py:402-412`, `config/startup.py:479`, `config/limits.py:28`
- **Status**: NEW (restates prior audit's B11-1, never filed)
- **Description**: `SeekableSource.resolve()` converts a non-seekable input to a temp WAV exactly once (correct — #4737), but neither `stream_seek.py`'s nor `stream_enhanced.py`'s `finally` block ever calls `processor.close()`, which is what would clean up that temp file. The startup sweep in `config/startup.py` globs only the `STREAM_TEMP_PREFIX` ("`auralis_stream_`") pattern — never the `auralis_seekable_*` prefix `SeekableSource` actually uses.
- **Evidence**: Confirmed at current line numbers in both `finally` blocks — no `.close()` call present in either.
- **Impact**: Every seek or play of an m4a/aac/wma track leaks one full-track-duration temp WAV file that no startup sweep will ever reclaim (wrong glob pattern). This compounds with usage — a session with many seeks on non-seekable-format tracks accumulates disk usage with no bound and no cleanup path.
- **Suggested Fix**: Call `processor.close()` (which should in turn call `seekable_source.cleanup()`) in both `finally` blocks; separately, widen `config/startup.py`'s startup-sweep glob to also match `auralis_seekable_*` as a backstop for any leak that occurs before the primary fix lands.

#### BE-21: Out-of-range seek positions produce a silent, zero-audio "completed" stream
- **Severity**: HIGH
- **Dimension**: Seek & Buffering / Chunked Processing (found independently by both; merged — Dimension 11's broader framing used)
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:395-398` (only rejects `position < 0`), `auralis-web/backend/core/chunk_boundaries.py:99-121` (`chunk_for_position`, no upper clamp), `auralis-web/backend/core/stream_seek.py:259-266`, `core/chunk_operations.py:248-264`
- **Status**: NEW (restates and broadens prior audit's B11-2, never filed)
- **Description**: `handle_seek` validates only `position < 0`/non-finite — there is no upper clamp against track duration anywhere between the WS handler and `chunk_for_position`. For any `position >= total_duration` (not only the exact boundary), `chunk_for_position` clamps the chunk `index` to the last chunk but leaves `offset` computed from the raw, unclamped position — the sliver-avoidance guard is structurally gated on `index < total_chunks - 1`, a no-op for the last chunk. `trim_samples` then exceeds the buffer length; numpy's safe slicing silently yields a 0-length array. `send_pcm_chunk` sends no frame for a 0-frame buffer and still returns success.
- **Evidence**:
  ```python
  # chunk_boundaries.py:108-121 — index clamped, offset is not
  index = max(0, min(index, total_chunks - 1))
  offset = max(0.0, pos - emitted_chunk_start(index))
  if (index < total_chunks - 1 and emitted_chunk_length(index) - offset < min_remainder):
      ...  # unreachable when index is already the last chunk
  ```
- **Impact**: A client bug, stale slider state, or a scrub-to-end gesture sends a seek position at or past `total_duration`; the client sees `audio_stream_start` immediately followed by `audio_stream_end (reason="completed")` with zero audio frames delivered — a jump to 100% with silence and no diagnostic, indistinguishable from a normal end-of-track but actually a silently discarded seek.
- **Suggested Fix**: Give `chunk_for_position` an optional `total_duration` parameter and clamp `pos`/`offset` so a seek at or past the end lands on the last audible instant instead of an empty buffer, or reject `position > processor.duration` explicitly in `handle_seek`/`stream_seek.py` once duration is known.

---

### MEDIUM

#### BE-1: `PUT /api/settings` never registers or unregisters scan-folder allowlist entries (regression of #4765)
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/settings.py:276-302`; `auralis/library/repositories/settings_repository.py:70-75`
- **Status**: Regression of #4765 (CLOSED)
- **Description**: `update_settings()` passes its `payload` dict **by reference** into `SettingsRepository.update_settings()`, which does `del updates['scan_folders']` as part of its special-casing — mutating the caller's own dict. The router's post-write `if 'scan_folders' in payload:` block (which calls `register_allowed_directory()`/`unregister_allowed_directory()`) is therefore always `False` and never runs. Reproduced live: `payload` before the call contains `scan_folders`; after, it doesn't.
- **Evidence**: `settings.py:295-302` checks `payload` after the repository call already deleted the key from it.
- **Impact**: A scan folder added via this route persists to the DB but is never added to `_extra_allowed_dirs`, so `validate_file_path()` rejects every file under it with 400 until restart. A folder removed this way stays trusted until restart — exactly the gap #4765 closed, reopened. Kept MEDIUM (not HIGH) because the shipped UI doesn't exercise this path — it uses the dedicated `POST /api/settings/scan-folders[/delete]` routes, which are unaffected.
- **Suggested Fix**: Snapshot the touched keys/values before the repository call, or pass `dict(payload)` into it. Long-term: stop `SettingsRepository.update_settings` from mutating its argument.

#### BE-2: `GET /api/albums/{id}/tracks` returns blank `artists`/`album` for every track (regression of #4568)
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/albums.py:236-270`; eager-load: `auralis/library/repositories/album_repository.py:62-65`; degrade site: `auralis/library/models/track.py:118-195`
- **Status**: Regression of #4568 (CLOSED, originally HIGH)
- **Description**: `_ALBUM_DETAIL_OPTIONS` eager-loads `Album.artist` and `Album.tracks → Track.genres` but not `Track.artists` or `Track.album`. After `expunge_all()`, `Track.to_dict()`'s bare `except Exception:` blocks (not the project's `_safe_collection()`/`_safe_scalar()` pattern) silently degrade the un-eager-loaded access to `[]`/`None` with **no warning logged**.
- **Evidence**: Reproduced against a real SQLite DB: `TRACK DICT artists=[] album=None artwork_url=None genres=['Rock']` — genres loaded (added for #5170), artists/album not.
- **Impact**: Every track row in the album-detail view renders blank artist and blank per-track album/artwork_url — the exact symptom #4568 was closed for. The frontend has no fallback for this shape (`trackTransformer.ts:22`). Invisible to any test that checks shape but not values.
- **Suggested Fix**: Add `selectinload(Album.tracks).selectinload(Track.artists)` (and load `Track.album`) to `_ALBUM_DETAIL_OPTIONS`, mirroring #5170's genre fix. Separately, `Track.to_dict()`'s bare excepts should use `_safe_collection()`/`_safe_scalar()` so a missing eager-load logs a WARNING instead of silently emitting empty values.

#### BE-3: `FingerprintQueue.enqueue()` is called from worker threads, violating its own documented single-thread contract
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/fingerprint_queue.py:180,236-246`; `library_scan.py:190-193`; `similarity_common.py:105-129`
- **Status**: NEW
- **Description**: `FingerprintQueue.enqueue()`'s own docstring says "Do NOT call from a thread without adding external synchronization" — four call sites across three router files call it via `asyncio.to_thread` anyway. The dequeue side is guarded by an `asyncio.Lock`, which provides zero protection against an OS thread from the `to_thread` pool.
- **Evidence**: Worker does `async with self._lock: track_id = queue.popleft(); ...; processing = track_id` — a threaded `enqueue(X)` can land between `popleft()` and the `processing = X` assignment, so both guards read `False` and `X` gets double-enqueued.
- **Impact**: Concrete interleaving causes duplicate fingerprinting work (double CPU cost, double-written fingerprint row) or a dropped enqueue, most plausible right after a large library import when several endpoints race.
- **Suggested Fix**: Drop the `to_thread` hops (enqueue is O(1) in-memory work) to restore the documented single-threaded model, or give the queue's state a real `threading.Lock` shared by `enqueue()` and the worker.

#### BE-4: Module-level `_deps` singleton in playlists/artwork/metadata/files.py cross-contaminates routers built in the same process
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/playlists.py:149-169`, `artwork.py:293-307`, `metadata.py:234-252`, `files.py:150-161,384-385`
- **Status**: NEW (narrows and corrects OPEN #5177's stated scope — see note below)
- **Description**: The `#4670` router-hoisting refactor moved these routers' dependencies into a module-level `_XxxDeps` object that each `create_*_router()` overwrites on every call. The APIRouter-singleton half of #5177 is fixed for these four files, but the dependency-capture half was relocated, not removed — each file's own comment asserting "only ever called once in the same process" is empirically false: multiple test files call each factory independently. `similarity.py`/`processing_api.py` solve this correctly with a per-router `_Deps` object published through a `ContextVar`.
- **Impact**: No production impact (each factory is called once at real startup), but a test building a throwaway router can silently repoint `main.app`'s live router at its mocks — including a bare `object()` stand-in — for the remainder of the same pytest process, producing order-dependent false passes/failures.
- **Suggested Fix**: Port the `ContextVar` pattern from `similarity.py`/`processing_api.py` to all four files. Note for issue housekeeping: #5177 (and duplicate-looking #4361) should be re-scoped or split — `library.py`/`system.py` still have the original APIRouter-singleton half (unfixed, LOW, tracked as-is), while this `_deps` hazard is a distinct, newer bug the same refactor introduced.

#### BE-5: `POST /api/playlists/{id}/tracks` returns 400 when tracks are already present or the playlist doesn't exist
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/playlists.py:395-400`; `auralis/library/repositories/playlist_membership_mixin.py:196-228`
- **Status**: NEW (#4734 CLOSED covered only the two DELETE routes; this is the untouched POST sibling)
- **Description**: `PlaylistRepository.add_tracks()` is idempotent by design (`INSERT OR IGNORE`) and returns the count of newly-inserted rows — 0 both when all tracks are already members **and** when the playlist doesn't exist. The route converts any `added_count == 0` into a flat 400.
- **Impact**: User-visible: `useBatchOperations.ts` calls this and shows "Failed to add tracks" for an operation that changed nothing it needed to. A nonexistent `playlist_id` also gets 400 instead of 404, inconsistent with every other route in the file.
- **Suggested Fix**: Fetch the playlist first and raise `NotFoundError` if absent; always return 200 with the real `added_count` (including 0), mirroring the #4734/#3563 precedent.

#### BE-6: Zero-duration track crashes chunk-0 processing with an uncaught `ValueError`
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:236-246`, `chunk_streaming.py:137-148,242-253`, `core/encoding/wav_encoder.py:143-146`
- **Status**: NEW (previously B3-1 in the 2026-08-13 audit, never filed)
- **Description**: `content_chunk_count(0.0)` clamps to 1, so a structurally-valid-but-empty audio file (0 duration) is still processed. Chunk 0 is also the last chunk, so `max_duration` collapses to 0 and `extract_chunk_segment` returns a 0-length array, which passes pad/trim validation unchanged. `WAVEncoder.encode_and_save[_from_path]` then raises a bare `ValueError` at its `audio.size == 0` guard — a check that runs **before**, and is not covered by, the `try/except WAVEncoderError` wrapping the actual save.
- **Impact**: A 0-duration file crashes chunk-0 processing with an unhandled `ValueError` instead of a clear "unplayable file" error; nothing upstream rejects `total_duration <= 0` before this point.
- **Suggested Fix**: Reject `total_duration <= 0` explicitly in `ChunkedAudioProcessor._load_metadata()` before any chunk is requested, or have `extract_chunk_segment` raise a descriptive error for a 0-length "chunk 0" result rather than deferring to the encoder's generic guard.

#### BE-7: Retrying a chunk after a post-DSP failure re-runs the shared stateful processor over already-processed audio
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_render.py:155-205`, `chunk_streaming.py:118-148`
- **Status**: NEW
- **Description**: `process_chunk_core` runs `AudioProcessingPipeline.process_audio()` against a deliberately shared, stateful `HybridProcessor` (envelope/gain-reduction state persists by design across chunks). If a step *after* that DSP call fails — `extract_chunk_segment`'s validation or the encoder's empty/finite checks (see BE-6) or a disk-full/permission error — the exception propagates uncached, but the processor's internal envelope state has already advanced past this chunk's audio. A retry of the same chunk index (the documented recovery flow's `recovery_position` maps back to the same index) re-runs the stateful DSP a second time over identical source audio on top of already-advanced state.
- **Impact**: Narrow trigger (needs a failure specifically between the DSP call and durable write), likely small audible effect in most cases (envelope followers converge quickly, 5s context padding helps), but a genuine violation of the "process each chunk exactly once" invariant the shared-processor design depends on — for content with fast transients right at a chunk's start, the double pass could plausibly produce an audible discrepancy.
- **Suggested Fix**: Route a chunk retry to a fresh `HybridProcessor` rather than the perturbed shared instance, or restructure so the stateful DSP call is the last fallible step before the result is final, or at minimum log loudly on retry-after-partial-DSP so the failure mode is visible.

#### BE-8: `GET /api/processing/jobs` exposes 5 more raw fields per job than `GET /api/processing/job/{id}` for the same entity
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/processing_api.py:137-143,552-578`; `core/job_models.py:64-82`
- **Status**: NEW
- **Description**: `JobListResponse.jobs` is typed `list[dict[str, Any]]` — an untyped passthrough that bypasses `response_model` filtering entirely — and returns `job.to_dict()` verbatim (10 fields). `get_job_status()` deliberately hand-builds a `JobStatusResponse` with only 5 of those same fields for the same entity.
- **Impact**: A client fetching a job via the list endpoint sees 6 more fields than the same job fetched via the status endpoint — the two disagree about what a "job" looks like. No live frontend consumer exists today, but this is a real, reproducible, mounted contract inconsistency.
- **Suggested Fix**: Reuse `JobStatusResponse` for `JobListResponse.jobs: list[JobStatusResponse]` (dropping the extra fields), or extend `JobStatusResponse` to a superset both handlers share.

#### BE-9: Processing jobs live only in an in-memory dict — a backend crash/restart silently loses all queued/in-flight export jobs
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/processing_engine.py:92`; `core/job_models.py:32-52`
- **Status**: NEW
- **Description**: The whole export-job subsystem is backed by one process-lifetime dict with no database table or repository. On a backend restart/crash mid-job, every queued and in-flight job is gone with no trace; `get_job_status()` returns a clean 404 rather than crashing, but the client cannot distinguish "never existed" from "silently lost on restart" from "completed but the engine forgot."
- **Impact**: Limited to the batch mastering-export flow (interactive streaming is stateless and unaffected). A user who submits a long export and hits a backend restart loses all visibility into that job with no error surfaced.
- **Suggested Fix**: Persist job identity + terminal status (queued/running/completed/failed + output_path) to a lightweight table via the repository pattern, and add a startup sweep (mirroring the existing orphaned-temp-file sweep) to reconcile jobs whose output file exists but whose in-memory record is gone.

#### BE-10: `StreamlinedCacheManager`'s dedicated mastering-recommendation cache has zero production callers
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/cache/manager.py:177-183,637-674`; would-be callers `services/recommendation_service.py:76-158`, `routers/enhancement.py:555-630`
- **Status**: NEW
- **Description**: A fully-built, tested, LRU-bounded (256 entries) recommendation cache exists and is exercised only by an integration test. `recommendation_service.py` and the REST recommendation endpoint each construct a fresh `ChunkedAudioProcessor` and recompute from scratch every single time, never consulting or populating this cache.
- **Impact**: Every play of every track and every REST poll pays for a fresh processor construction, metadata probe, and `AdaptiveMasteringEngine.recommend_weighted()` call — even for the identical track played twice in a row within the cache's window.
- **Suggested Fix**: Have `RecommendationService` consult `get_mastering_recommendation(track_id)` before constructing a processor, and populate it after a successful compute, mirroring the #4358 chunk-cache fix pattern.

#### BE-15: Two "SECURITY:"-labeled WebSocket message-validation tests fail
- **Severity**: MEDIUM
- **Dimension**: Test Coverage / Security
- **Location**: `tests/security/test_websocket_security.py:94-113,143-165`
- **Status**: NEW
- **Description**: `test_boundary_message_size` sends a raw string where `WebSocketMessageBase` requires a dict, so it fails on an unrelated schema-type error rather than testing the size boundary. `test_reject_deeply_nested_json` (docstring: "Attack vector: CPU exhaustion via deep recursion") shows a 1000-level-deep payload is accepted outright — there is no depth-based protection, only a byte-size cap this payload doesn't hit.
- **Impact**: The size-boundary test provides no working coverage of the actual accept/reject boundary; the nesting test demonstrates and then is silenced on a real CPU/memory-exhaustion vector.
- **Suggested Fix**: Fix the size-boundary fixture to send a valid dict payload near the limit. For nesting, add a recursion-depth guard to message parsing and assert rejection, or explicitly document that only byte-size is bounded by design.

#### BE-20: `clear_track()` Tier1 eviction uses substring matching, over-evicting unrelated tracks
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:681-693`
- **Status**: NEW (restates prior audit's B10-3, never filed)
- **Description**: `t1_keys = [k for k in self.tier1_cache if str(track_id) in str(k)]` — substring matching. Track IDs are sequential integers, so `clear_track(1)` also matches track 12's key. Tier2's filter three lines below already does this correctly with exact equality.
- **Impact**: `DELETE /api/cache/track/{id}` silently evicts hot Tier1 entries for unrelated currently-playing tracks, causing an unnecessary re-buffer hiccup.
- **Suggested Fix**: Filter Tier1 on `CachedChunk.track_id == track_id`, matching the sibling Tier2 loop.

#### BE-23: Tier2 cache hit/miss counters are structurally wrong, and the bad numbers are served live via `/api/cache/stats`
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:196,357-360,559-564`; `cache/monitoring.py:110-123`
- **Status**: NEW (restates prior audit's B10-4, never filed)
- **Description**: `tier2_misses` is initialized to 0 and never incremented anywhere; `tier2["hit_rate"]` divides by the combined four-counter total rather than `tier2_hits + tier2_misses`.
- **Impact**: `GET /api/cache/stats` (a real, externally-callable endpoint) returns an artificially low, wrongly-scaled Tier2 hit rate that never reflects a Tier2 regression — hiding exactly the class of regression the metric exists to catch.
- **Suggested Fix**: Split the miss branch into tier1-only-miss vs. both-missed, incrementing both counters appropriately; compute `tier2["hit_rate"]` as `tier2_hits / max(1, tier2_hits + tier2_misses)`.

#### BE-24: Thumbnail cache has no backstop eviction; `POST /api/library/reset` orphans the entire artwork tree
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/core/thumbnail_cache.py` (whole file); `routers/library.py:132-184`
- **Status**: NEW (restates prior audit's B10-5, never filed)
- **Description**: `thumbnail_cache.py` has no size cap, TTL, or "sweep orphaned thumbnails" mechanism, unlike the chunk cache's hard 512MB ceiling. `reset_library()` deletes every Track/Album row but never touches the thumbnail directory.
- **Impact**: Each "nuke and rescan" orphans every thumbnail/artwork file for every pre-reset album with no reclamation path. Low urgency (small per-image files) but genuinely unbounded, unlike every other cache tier.
- **Suggested Fix**: Have `reset_library()` clear `~/.auralis/artwork/`, or add a size-capped sweep analogous to `ChunkCacheManager.prune_chunk_directory()`.

#### BE-25: `file_signature.py`'s mtime+size key has no content fallback
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/core/file_signature.py:40-99`
- **Status**: NEW
- **Description**: The signature is derived purely from `mtime`/`size`/`filepath`. Two blind spots have no fallback: a same-size in-place edit (e.g. a loudness-correction tool that rewrites samples but preserves frame count and byte count), and coarse mtime granularity on FAT32/exFAT (2-second resolution) — plausible for a music library on removable/external storage.
- **Impact**: Every consumer of this signature (`ChunkPathCache`, `ChunkCacheManager`, `SimpleChunkCache`) trusts it as proof of validity. In the blind-spot cases, a genuinely edited file serves its pre-edit cached audio indefinitely — the same failure mode as BE-17, but unfixable by fixing BE-17 alone since even the "correct" signature-aware tiers trust this input.
- **Suggested Fix**: Hash a small fixed-size sample of file content (e.g. first + last 64KB) alongside mtime/size for a cheap but much stronger signature.

#### BE-26: No cache-clearing path reaches all three caches
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:139-159`, `routers/library.py:132-184`
- **Status**: NEW (sibling of BE-16/BE-24, viewed from the invalidation-reach angle)
- **Description**: `/api/cache/clear` only touches the chunk cache; it has no awareness of the thumbnail cache or the (currently dead, per #5085) track-analysis cache. `reset_library()` — the most destructive user-facing action in the app — touches neither the chunk-cache directory nor the thumbnail directory.
- **Impact**: A user who resets their library gets a consistent DB but stale chunk WAVs (self-correcting via LRU) and unbounded orphaned thumbnails (BE-24, not self-correcting) both survive. A user who reads "clear cache" as a global reset gets only one of three layers touched, and per BE-16, not even fully that one.
- **Suggested Fix**: Introduce one shared `clear_all_caches()` entry point that both `reset_library()` and `/api/cache/clear` delegate to.

#### BE-27: Completed-stream branch mis-reports full-track duration instead of what was actually delivered after a seek
- **Severity**: MEDIUM
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/stream_seek.py:411-419`, `stream_normal.py:472-479`
- **Status**: NEW (restates prior audit's B11-3, never filed)
- **Description**: The `else:` (completed) branch reports `processor.duration`/`processor.sample_rate` — the full track — regardless of `delivered_samples`, which is what a client resuming from a mid-track seek actually received.
- **Impact**: A client that ends a seek-then-play sequence at completion is told the stream delivered the full track duration even when it started partway through, which can throw off any client-side accounting keyed on delivered-sample count.
- **Suggested Fix**: Report duration derived from `delivered_samples`/`sample_rate` in the completed branch, matching what `stopped_early` branches already do correctly.

Test-coverage findings D9-1, D9-3 through D9-9 (vacuous security-injection
assertions, a broken path-traversal regression suite, a non-functional
system-path rejection test, broken WebSocket security tests, stale reconnect
regression tests, a broken streaming happy-path fixture, a live-server-only
player E2E suite, and an unreliable metadata test file) are folded into the
consolidated list below rather than repeated in full — see **Test Coverage
Cluster** in Relationships.

---

### LOW

| ID | Title | Location |
|---|---|---|
| BE-31 | Repository "False/0 means either not-found or internal failure" turns transient DB errors into permanent-looking 404/400 across playlists.py | `routers/playlists.py:314-317,447-448,489-493,569-572` |
| BE-32 | `POST /api/metadata/batch` reports `success: true` when every requested track was silently skipped | `routers/metadata.py:488-517,567-574` |
| BE-33 | `MetadataUpdateRequest` tag values are entirely unbounded (#4681 covered only batch count/track_id) | `routers/metadata.py:38-55` |
| BE-34 | `enqueue_for_fingerprinting()` reports success even when the queue rejected the track | `routers/similarity_common.py:105-129` |
| BE-35 | `POST /api/player/volume` returns 400 (not 503) when the audio player is unavailable | `routers/player.py:525-550`, `services/playback_service.py:309-311` |
| BE-36 | `GET /api/processing/jobs`'s `total` field is the post-truncation count, not the real total | `routers/processing_api.py:551-579` |
| BE-37 | Upload size-cap comment in `processing_api.py` overstates what it prevents (body is already fully spooled by Starlette before the handler runs) | `routers/processing_api.py:395-401` |
| BE-38 | Seeded `enhancement_intensity` is not range-guarded the way `default_preset` is | `helpers.py:119-129` |
| BE-39 | `library.py`/`system.py` still pair a module-level `APIRouter()` with a `create_*_router()` factory | `routers/library.py:39,86-186`, `system.py:62` — Existing: #5177/#4361, narrowed scope per BE-4 |
| BE-40 | `send_error`/`send_fingerprint_progress` log a benign client disconnect at ERROR instead of classifying it like every sibling send helper | `core/stream_messages.py:157-224` |
| BE-41 | Stale comment claims chunk concatenation applies crossfading; contradicts the accurate comment two lines below it | `core/chunk_batch.py:108-121` |
| BE-42 | `BatchMetadataResultItem.filepath` leaks the server's absolute filesystem path — the one response model breaking the codebase-wide #3205 rule | `routers/metadata.py:138-160` |
| BE-43 | `OriginCheckMiddleware` registration comment claims a causal order the LIFO middleware stack does not produce (actual order: OriginCheck runs *before* TrustedHost) | `config/middleware.py:470-474` |
| BE-44 | Two temp-cleanup failure logs in `config/startup.py` log the full absolute path at WARNING, inconsistent with their own success-path siblings | `config/startup.py:500,581` |
| BE-45 | Vacuous `assert True` regression test for legacy import paths | `tests/regression/test_version_compatibility.py:404-420` |
| BE-46 | No single-flight dedup for concurrent seek requests to the same chunk key — wasted duplicate DSP work (not corruption; atomic writes prevent torn files) | `core/stream_seek.py:130-142`, `core/chunk_path_cache.py:77-101` |
| BE-47 | `buffer_presets_for_track` (proactive-buffering "instant preset switching") is fully wired for DI but never actually called — dead since before #4071 | `core/proactive_buffer.py:22-113`, `routers/player.py:816,835-837` |

Additionally: **D9-2/D9-10/D9-11** (test-coverage LOW cluster — one more
vacuous-assertion test, a context finding that 65% of the CI baseline is
backend-scoped, and 4 baseline entries in `test_library_reset.py` that pass
in isolation but may be flaking full-suite) are context/aggregate findings
rather than standalone bugs — see the Test Coverage Cluster below rather than
a numbered entry each.

---

## Relationships

- **Test Coverage Cluster (Dimension 9, 9 findings, MEDIUM/LOW)**: `D9-1`
  (vacuous `assert True` in two named injection tests), `D9-3` (path-traversal
  regression suite 100% broken via `ImportError` on renamed symbols), `D9-4`
  (system-path rejection test fails because the validator has no such
  blocklist), `D9-5` (both WS "SECURITY:" tests broken — folded into BE-15
  above), `D9-6` (reconnect-state-push regression tests stale), `D9-7`
  (streaming happy-path tests fail on a missing fixture file), `D9-8` (the
  21-test player E2E suite requires a live server on :8765 and can never pass
  in a sandboxed run), `D9-9` (metadata test file has an environment-dependent
  fixture plus a real `setup_routers` lambda-arity crash on fresh import),
  `D9-2`/`D9-10`/`D9-11` (a second vacuous test, the 65%-backend-share context
  finding, and 4 possibly-stale baseline entries). None of these are new
  production bugs — they are a coherent picture of the CI ratchet's largest
  debt concentration sitting exactly in the areas (path security, WS message
  limits, reconnect UX, streaming message ordering) this audit's other
  dimensions independently confirmed are otherwise correct in production
  code. Fix cluster together; several share the same root cause class
  (renamed symbols after a refactor, or a mocked call path a later refactor
  bypassed).
- **BE-14 = merged DIM7-1 (Error Handling) + D8-1 (Performance)**: same bug
  (missing timeout on `recommendation_service.py`'s `ChunkedAudioProcessor`
  construction), found independently by both dimensions. Also the direct
  successor of the 2026-08-13 audit's B7-1.
- **BE-21 = merged D11-1 (Seek & Buffering) + D3-2 (Chunked Processing)**:
  same bug (seek past/at track duration silently drops the final chunk),
  found independently by both dimensions; Dimension 11's broader framing
  (reachable for *any* out-of-range position, not just the exact boundary)
  is used as the primary write-up.
- **BE-16 (cache-clear doesn't touch disk) + BE-17 (in-memory key omits file
  signature) + BE-25 (file_signature has no content fallback)**: three
  independent layers of the same failure class — a user has no reliable way
  to force a stale-cache re-read at any of the three levels (in-memory key,
  on-disk clear action, or the signature both trust). Fixing only one leaves
  the other two as an escape hatch for staleness to persist. Recommend fixing
  BE-17 and BE-16 together (same file family, `cache/manager.py` +
  `routers/cache_streamlined.py`), then BE-25 as a follow-up since it's a
  smaller, more foundational change that benefits every tier at once.
- **BE-26 is the "invalidation reach" view of BE-16/BE-24**: same root
  finding (no owner of "clear everything") from a different checklist angle;
  fixing BE-26's proposed `clear_all_caches()` entry point is a natural
  vehicle for BE-16's disk-deletion fix and BE-24's reset-time thumbnail
  sweep.
- **BE-1 and BE-2 are both regressions of CLOSED issues**, both caused by a
  refactor landing after the original fix with no regression test pinning
  the fixed behavior (`#4670` router hoisting for BE-1; a missing
  `selectinload` alongside the unrelated #5170 genre fix for BE-2). Consider
  adding a regression test for each as part of the fix, specifically
  exercising the *value*, not just the response shape.
- **BE-4 corrects OPEN #5177's stated scope**: the module-level-`APIRouter`
  half of #5177 is fixed for playlists/artwork/metadata/files (by the same
  `#4670` refactor that introduced BE-4's `_deps` singleton hazard as a
  side effect); `library.py`/`system.py` still have the *original* bug
  (tracked as BE-39/LOW). Re-scoping #5177 into two issues would prevent it
  from reading as "fixed" once the library.py/system.py half lands while
  the newer `_deps` hazard silently persists.

---

## Prioritized Fix Order

1. **BE-1, BE-2** (MEDIUM, regressions of CLOSED issues) — user-visible
   correctness regressions with the smallest fixes on this list (a
   dict-reference bug and a missing `selectinload`). Add a regression test
   for each while fixing, since the lack of one is exactly how both
   regressed silently.
2. **BE-17, BE-16** (HIGH) — restore the user's only cache-troubleshooting
   lever and close the in-memory staleness gap it's meant to fix. Do these
   together; both live in `cache/manager.py`/`routers/cache_streamlined.py`.
3. **BE-18** (HIGH) — two `processor.close()` calls plus a glob-pattern
   widening; trivially small relative to a permanent, unbounded per-seek
   disk leak.
4. **BE-21** (HIGH) — a `total_duration` clamp in one shared function
   (`chunk_boundaries.chunk_for_position`) fixes both the seek-to-end and
   seek-past-end cases in one change.
5. **BE-14** (HIGH) — one `asyncio.wait_for` wrapper at two call sites,
   copying a pattern already used three files away.
6. **BE-25** (MEDIUM) — a bounded-content-hash fallback in
   `file_signature.py` strengthens every cache tier that trusts it at once,
   including partially mitigating BE-17 even before that fix lands.
7. **BE-20, BE-23** (MEDIUM) — both one-line-scale fixes in `cache/manager.py`,
   worth doing alongside BE-16/BE-17 while that file is already open.
8. **BE-26, BE-24** (MEDIUM) — a shared `clear_all_caches()` entry point,
   with the thumbnail-sweep and reset-library wiring built on top of it.
9. **Test Coverage Cluster** (D9-1, D9-3 through D9-9 — see Relationships) —
   not urgent individually, but collectively the largest coherent risk in
   this audit: several guard named security/reliability guarantees this
   session confirmed are still correct in production code today, but a
   *future* regression in any of them would currently ship silently. D9-8
   (21-test player E2E suite) and D9-3/D9-4/D9-5/D9-6 (security- and
   reconnect-relevant) first.
10. **BE-3** (MEDIUM) — drop two `to_thread` hops around O(1) work; smallest
    fix on the list relative to its data-integrity implication (duplicate
    fingerprint work).
11. **BE-4** (MEDIUM) — port an existing, already-correct pattern
    (`ContextVar`) from two files in the same directory to four more.
12. **BE-5, BE-27** (MEDIUM) — both small, isolated idempotency/reporting
    fixes with existing precedent elsewhere in the same file family.
13. **BE-6, BE-7** (MEDIUM) — chunked-processing edge cases; narrow triggers,
    address opportunistically alongside other `chunk_render.py`/
    `chunk_streaming.py` work.
14. **BE-8, BE-9, BE-10** (MEDIUM) — processing-jobs subsystem: schema
    consolidation, persistence, and cache wiring are three independent,
    non-blocking improvements to the same low-traffic export-job surface.
15. **BE-15** (MEDIUM) — fix the two WebSocket security test fixtures; small,
    and closes a real gap in nesting-depth protection once addressed.
16. **All LOW findings (BE-31 through BE-47)** — opportunistic. BE-43 and
    BE-41 are one-line comment fixes; BE-38 pairs naturally with BE-1's fix
    site (`helpers.py`); BE-42 pairs with BE-9 (both `metadata.py`/job
    schema cleanup).

---

## Deduplicated / Confirmed Still Open (not re-reported)

The following were independently rediscovered or re-verified this session
and confirmed still present, but match an OPEN GitHub issue and are **not**
re-reported as findings: #3838 (deferred, response_model — count has shrunk
to 2 intentional exceptions), #4361/#5177 (see BE-4/BE-39), #4630, #4647,
#4666, #4669, #4676, #4703, #4708, #4711, #4712, #4726, #4727, #4730, #4737,
#4750, #4755, #4761, #4766, #4768, #4770, #4771, #4786, #4790, #4798, #4806,
#4809, #4815, #4817, #4834, #4838, #4842, #4843, #4857, #4861, #4930, #4942,
#4953, #5009, #5010, #5018, #5032, #5035, #5046, #5047, #5048, #5049, #5050,
#5051, #5056, #5058, #5059, #5060, #5061, #5066, #5067, #5068, #5069, #5077,
#5078, #5079, #5080, #5081, #5083, #5085, #5086, #5087, #5098, #5115, #5117,
#5131, #5166, #5174, #5175, #5192, #5196, #5200, #5208, #5224, #5225, #5236,
#5238.

**Never filed despite prior identification** (restated as NEW in this report
per GitHub's bookkeeping — see Executive Summary theme 1): the 2026-08-13
audit's B6-1, B7-1 (→ BE-14), B9-1/B9-2 (→ D9-1/D9-2), B10-1 through B10-5
(→ BE-17/BE-16/BE-20/BE-23/BE-24), and B11-1/B11-2/B11-3 (→ BE-18/BE-21/BE-27).

---

## Dimensions With No New Findings

- **Dimension 4 (Processing Engine)** — both candidate defects found
  (pooled-processor config-mutation-on-fallback, and a timed-out processor
  staying in the streamlined-worker LRU cache) already match OPEN issues
  (#5058 HIGH, #5059 MEDIUM) and are not re-reported. The `AudioProcessingPipeline`/
  `MasteringTargetService`/`LevelManager` consolidations were independently
  verified as genuine — no surviving duplicate logic in `chunked_processor.py`.

## Notable Verifications (no regression, no new finding)

- **WebSocket connection lifecycle, handshake rejection, binary frame format,
  backpressure, multi-client isolation, heartbeat/keepalive, reconnection** —
  all independently re-traced against current code and confirmed correct;
  the one genuinely new WS finding (error-log level classification) is LOW.
- **Middleware ordering, CORS, static-file path restriction, rate-limit
  bookkeeping, lifespan symmetry, `--dev` flag scope, env-var import-time
  tuning** — all re-derived from actual code (including the installed
  Starlette source) and confirmed correct, aside from the two LOW
  documentation-accuracy findings (BE-43, BE-44).
- **N+1 queries, `selectinload()` survival through the #4511/#4604 repository
  mixin splits, executor singleton wiring, bounded queues, SQLAlchemy pool
  config** — all re-verified against current code; no regressions found.
- **Rapid-seek serialization, prefetch-cancellation discard semantics,
  post-seek level-continuity baseline handling, seekable-source
  memoization (#4737)** — all independently re-traced and confirmed intact.
- **No bare `except:` and no `except Exception: pass` returning a false
  success anywhere in `auralis-web/backend/`** — reconfirmed by fresh grep.
- **No path traversal, arbitrary-file-read, or CORS-wildcard issue found**
  anywhere in the routers/middleware surface this session.

---

*Generated by `/audit-backend` on 2026-08-24. All 11 dimensions run at depth
`deep`, no `--limit`. Findings were produced by fresh, independent reads of
current source in each dimension (not a diff against the prior report),
cross-checked against `gh issue list` (200 entries) for dedup.*
