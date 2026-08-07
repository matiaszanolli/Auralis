# Backend Audit — Auralis — 2026-08-07

**Scope**: FastAPI backend — routers, WebSocket streaming, chunked processing, processing engine, schemas, middleware, error handling, performance, test coverage.
**Method**: 9 dimension agents (backend-specialist), max 3 concurrent, deep depth, no finding limit. All 9 dimensions completed.
**Prior report**: `docs/audits/AUDIT_BACKEND_2026-07-29.md` (9 days earlier) — every dimension cross-checked prior findings for regression/still-open status rather than re-deriving from scratch.

---

## Executive Summary

**57 new findings** (0 CRITICAL, **2 HIGH**, **22 MEDIUM**, 33 LOW) plus 2 confirmed **regressions** of closed issues (#4780, and partially #4902/#4737/#4999 — see Relationships) and roughly a dozen existing OPEN issues re-verified still-present (not re-filed).

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 22 |
| LOW | 33 |
| **Total (new)** | **57** |

| Dimension | New | Notable result |
|---|---|---|
| 1 — Route Handlers | 2 | Clean apart from 2 LOW; 11 existing issues re-verified, 1 flagged stale-closable (#4814) |
| 2 — WebSocket Streaming | 6 (+3 existing re-confirmed) | **WS-1 (HIGH)**: closed #4999's timeout fix never reached `stream_seek.py` |
| 3 — Chunked Processing | 7 (+1 existing) | **CP-1 (MEDIUM)**: level-smoothing ramp lands entirely inside the discarded 5s head — makes two closed fixes (#3831, #4352) inert |
| 4 — Processing Engine | 7 | **PE-5 (HIGH)**: track-change prune leaks a full decoded temp WAV per AAC/M4A/WMA track change — second drop path closed #4737 missed |
| 5 — Schema Consistency | 7 (+1 existing) | **SC-1**: #3838's scope estimate (~28 endpoints/7 routers) is now wrong by 68% — live count is 47/15 |
| 6 — Middleware & Config | 7 | **MW-1 (MEDIUM)**: `logger.debug` is unconditionally unreachable, invalidating 3 hardening commits' stated diagnostic-retrieval rationale |
| 7 — Error Handling | 4 | **EH-1 (MEDIUM)**: deleted-on-disk track returns 400 not 404; the 404 handler written for it is dead code |
| 8 — Performance | 5 | **PF-3 (MEDIUM)**: 207 `asyncio.to_thread` sites share Python's default executor; 10 concurrent streams × 2 slots can exceed it on 2-4 core hardware |
| 9 — Test Coverage | 12 (+2 existing, +1 clean note) | **TC-4 (MEDIUM)**: a missing `Origin` header in the shared test fixture causes 131 of 194 live test failures (68%) — the entire mutating half of the API has no effective coverage, concealing several already-filed live bugs |

### Headline theme: two independent "closed fix didn't reach every sibling" findings

**WS-1** and **PE-2** both trace back to closed **#4999** — the chunk-timeout abort fix landed only in `stream_enhanced.py`, leaving `stream_seek.py` (WS-1) and `streamlined_worker.py`'s `_process_chunk` (PE-2) with the exact pre-fix hang behavior. **PE-5** is the same shape one level down: closed **#4737** added `close()` to one processor-eviction path in `streamlined_worker.py` but missed a second, and the second is hit on every track change, not just LRU pressure. This is the third consecutive backend audit to find this "partial-sibling-fix" pattern (see also CP-1/CP-4, which found a closed level-smoothing fix that never reaches the emitted audio at all).

### Headline theme: the backend CI gate is red right now, and the reason conceals real bugs

**TC-4** found that a one-line test-fixture gap (`tests/backend/conftest.py`'s `client` fixture never sets an `Origin` header) causes `OriginCheckMiddleware` to reject 131 of 194 live test failures (68%) with a constant 403 — meaning the player, enhancement, queue, similarity, files, metadata and artwork routers all currently have **zero passing write-path test coverage**. This single fixture bug is large enough that it is masking several already-filed live regressions (BE4-13, BE1-3, BE2-01) behind assertions that structurally cannot execute. **TC-2** and **TC-13** independently found the baseline gate itself is currently red (2 unlisted deterministic failures, 21 unlisted e2e failures), and **TC-3** found 69 baseline entries have gone stale (tests now pass but the ratchet still silently permits their old failure).

---

## Route Coverage Matrix

All 20 registered routers (derived from `auralis-web/backend/config/routes.py`), with dimension coverage and open-finding status:

| Router | RH | WS | CP | PE | SC | MW | EH | PF | TC | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| albums | ✓ | — | — | — | SC-1 | — | — | — | ✓ | No `response_model` on 4 routes |
| artists | ✓ | — | — | — | SC-1, SC-5 | — | — | PF-1 | ✓ | N+1 hydration (PF-1); `album_id=0` sentinel |
| artwork | ✓ | — | — | — | SC-1 | MW-5 | EH-2 | — | TC-1 | Untested (403 via TC-4); rate-limit gap |
| cache_streamlined | ✓ | — | — | — | SC-1 | — | — | — | — | |
| enhancement | ✓ | ✓ (WS-2, WS-9) | CP-2, CP-3 | — | SC-1 | — | — | — | TC-4, TC-8 | Chunk pre-warm silently no-ops for AAC/M4A/WMA |
| files | ✓ | — | — | — | SC-1 | — | — | — | TC-2, TC-4 | Deterministic 405-vs-404 CI failure |
| fingerprint_queue | ✓ | ✓ (WS-9) | — | — | SC-1 | — | — | — | — | |
| fingerprint_status | ✓ | — | — | — | — | — | — | — | — | |
| health | RH-1 | — | — | — | — | — | — | — | — | Schema-version drift regression |
| library | ✓ | — | — | — | — | MW-5 | — | — | TC-6 (existing #4715) | |
| library_scan | ✓ | — | — | — | — | — | — | — | — | |
| metadata | ✓ | — | — | — | — | — | EH-1, EH-2 | — | TC-4, TC-5 | 400-not-404 on deleted file |
| player | RH-2 | ✓ (WS-2, WS-3, WS-5) | — | — | SC-4, SC-6 | — | — | — | TC-4, TC-5, TC-7, TC-8 | Highest test-gap concentration |
| playlists | ✓ | — | — | — | SC-1, SC-2, SC-3, SC-7 | — | — | — | ✓ | All 10 routes unmodelled; 3 competing type declarations |
| processing_api | ✓ | — | — | PE-1, PE-3 | — | — | — | — | TC-4 | Config settings silently dropped |
| settings | ✓ | — | — | — | — | — | — | — | — | |
| similarity | ✓ | — | — | — | SC-8 | — | — | — | TC-4 | |
| similarity_graph | ✓ | — | — | — | — | — | — | — | — | |
| system (WS endpoint) | — | WS-1, WS-4, WS-5, WS-6, WS-8 | — | — | — | — | ✓ | — | TC-7, TC-8, TC-15 | WS-1 HIGH |
| tracks | ✓ | — | — | — | SC-1 | — | — | — | — | |

---

## Findings

### CRITICAL

None found.

---

### HIGH

#### WS-1: `stream_seek.py` never got #4999's chunk-timeout abort — a DSP timeout after a seek cascades into a 30s-per-chunk pileup
- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_seek.py:310-338` (compare `auralis-web/backend/core/stream_enhanced.py:275-303`)
- **Status**: NEW (incomplete fix of CLOSED #4999)
- **Description**: Commit `1a4372cb` ("fix: abort stream on chunk-processing timeout…", #4999) added a dedicated `except TimeoutError` branch to `stream_enhanced.py`'s chunk loop, because `stream_chunk_ops.process_chunk_only` raises `TimeoutError` while the orphaned OS thread is still inside `processor.process_chunk_safe()` holding the processor's `threading.RLock`. Continuing the loop on the same `processor` makes every subsequent chunk block on that lock and time out 30s later in turn. `git show --stat 1a4372cb` shows the commit touched **only** `stream_enhanced.py` and its new test; `stream_seek.py` — which runs the *identical* loop over the *same* long-lived `processor` local and calls the *same* `controller._process_chunk_only` — was not changed. Its `except Exception as chunk_error:` at `:310` still swallows `TimeoutError` (`TimeoutError` ⊂ `OSError` ⊂ `Exception`) into the pre-existing skip-and-continue path, exactly the behaviour #4999 removed.
- **Evidence**:
```python
# stream_enhanced.py:275  — the #4999 guard
            except TimeoutError:
                await controller._drain_cancelled_task(lookahead_task)
                stopped_early = True
                break

# stream_seek.py:310  — no TimeoutError branch; falls into skip-and-continue
            except Exception as chunk_error:
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                logger.error(f"Failed to process chunk {chunk_idx}: {chunk_error}", exc_info=True)
                failed_chunks.append(chunk_idx)
                continue
```
- **Impact**: A hung DSP call on any chunk of a **seek** stream (every scrub, and every `play_enhanced` with `start_position > 0`, i.e. every WS reconnect resume) stalls the stream for `CHUNK_PROCESS_TIMEOUT` (30s) per remaining chunk, emitting one `audio_stream_error` per chunk and delivering no audio. On a 4-minute track that is ~24 chunks × 30s ≈ 12 minutes of dead stream while the semaphore permit and executor threads stay pinned.
- **Siblings**: PE-2 (streamlined_worker.py's `_process_chunk` has the identical unfixed sibling shape).
- **Suggested Fix**: Lift the `except TimeoutError` branch from `stream_enhanced.py:275-303` into `stream_seek.py`'s loop verbatim (must precede `except Exception`). Better: factor the three near-identical chunk loops' error handling into `stream_chunk_ops.py` so this class of fix cannot land in only one sibling again.

#### PE-5: Track-change prune in `_build_tier2_cache` drops cached processors WITHOUT `close()` — leaks a full decoded temp WAV per M4A/AAC/WMA track change
- **Severity**: HIGH
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/streamlined_worker.py:359-377`; contrast the bounded path at `:126-140`; `auralis-web/backend/core/seekable_source.py:120-129`
- **Status**: NEW (second drop path missed by CLOSED #4737, which added `close()` only to the LRU-eviction path added by #4521)
- **Description**: `ChunkedAudioProcessor` owns a `SeekableSource` that, for formats libsndfile cannot open (`.m4a`, `.aac`, `.wma`), decodes the **whole track** into a `tempfile.mkdtemp()` WAV on first chunk load. #4737 made `_remember_processor`'s LRU eviction call `evicted.close()` for exactly this reason. `_build_tier2_cache` has a *second* removal path — the track-change prune — that rebuilds the OrderedDict via a comprehension and simply drops every entry belonging to the previous track, never calling `close()`:
```python
# core/streamlined_worker.py:366-368
self._processor_cache = OrderedDict(
    (k, v) for k, v in self._processor_cache.items() if k[0] == track_id
)
```
The dropped entries are the only remaining references to those processors, so their temp directories survive for the lifetime of the backend process.
- **Evidence**: The prune fires on **every track change** (worker tick, 1 Hz). Each track holds up to two entries (`preset=None` original + `preset=<name>` processed), each with its own `SeekableSource` temp dir. `_remember_processor`'s own docstring states the invariant this path violates: "dropping such an entry without closing it leaks that file for the process lifetime."
- **Impact**: For AAC/M4A/WMA libraries, ~2 full-length decoded WAVs (tens to hundreds of MB each) accumulate in the system temp dir per track change and are never reclaimed. On Linux `/tmp` is commonly tmpfs, so this is RAM, not just disk; a normal listening session of a few dozen tracks exhausts it. Files are outside `ChunkCacheManager`'s 512 MB reaper (different directory), so nothing cleans them up.
- **Suggested Fix**: Route the prune through the same close-and-drop helper as `_remember_processor` (pop each non-matching key, `close()` in a `try/except`, then rebuild), or extract one `_evict(cache_key)` used by both paths so a third removal path cannot reintroduce the omission.

---

### MEDIUM

#### WS-2: `handle_seek` decides enhanced-vs-normal from a stale per-connection `enabled` snapshot — seeking after toggling mastering off yields a stream that immediately self-terminates with zero audio
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:197-201, 363-391`; interacts with `stream_seek.py:222-229`, `routers/enhancement.py:228-229`
- **Status**: NEW (regression introduced by CLOSED #4742; distinct from OPEN #4677)
- **Description**: `handle_play_enhanced` snapshots `enabled` into `state.active_stream_settings[ws_id]`. `handle_seek` prefers that snapshot over the live `enhancement_settings` global when choosing enhanced-vs-normal routing, but the *enhanced* loop it selects checks the **live** global on every iteration (`stream_seek.py:222`). The two reads disagree whenever `POST /api/player/enhancement/toggle` flipped `enabled` to `False` since the last `play_enhanced`.
- **Impact**: Toggle mastering off during playback, then seek: backend starts an enhanced seek stream, sends `audio_stream_start`, then breaks on chunk 0 with `audio_stream_end reason: "stopped"`, `total_samples: 0`. User gets silence with no error frame.
- **Suggested Fix**: Resolve `enabled` from the live `enhancement_settings` dict (keep the snapshot for `preset`/`intensity`, which is what #4742 actually addressed).

#### CP-1: Level-smoothing gain ramp lands entirely inside the 5s head that `extract_chunk_segment` discards
- **Location**: `auralis-web/backend/core/chunked_processor.py:520-536,643-652`, `core/level_manager.py:110-129`
- **Status**: NEW (makes CLOSED #3831 and CLOSED #4352 inert on emitted audio)
- **Description**: `_smooth_level_transition()` runs on the 15s context-trimmed buffer before `extract_chunk_segment()` slices out `[5s:15s]`. The 50ms gain ramp sits at buffer offset 0 — i.e. entirely within the 5s the extraction discards. Verified empirically: the ramp region has 2205 distinct values, the emitted slice has exactly 1, and the boundary is a hard 1-sample step (0.1000 → 0.1189, 1.5dB).
- **Impact**: Every chunk boundary where the level smoother fires still produces the audible hard step that #3831 (MEDIUM) and #4352 (HIGH) were closed to eliminate. Both fixes are structurally unreachable by the listener.
- **Siblings**: CP-4 (same root cause — RMS history recorded pre-extraction on miss, post-extraction on hit).
- **Suggested Fix**: Move `_smooth_level_transition()` to run after `extract_chunk_segment()`, or pass the emitted-segment offset into `LevelManager.smooth_transition()` so the ramp lands at `overlap_samples` for chunks ≥1.

#### CP-2: Mid-playback chunk pre-warm silently no-ops for `.m4a`/`.aac`/`.wma` — it probes with bare `sf.info()`
- **Location**: `auralis-web/backend/routers/enhancement.py:148-207`
- **Status**: NEW (same class as CLOSED #4497, different file; adjacent to OPEN #4760)
- **Description**: `_preprocess_upcoming_chunks()` reads track duration with `sf.info(filepath)` instead of `auralis.io.unified_loader.get_audio_info()`. libsndfile cannot open `.m4a`/`.aac`/`.wma`, so `sf.info()` raises, the catch-all swallows it, and the entire pre-warm is skipped.
- **Impact**: Toggling enhancement mid-playback on an AAC/ALAC/WMA track warms zero chunks — the stream stalls waiting for on-demand DSP, precisely the failure this function exists to prevent.
- **Siblings**: CP-3 (latent leak this masks).
- **Suggested Fix**: Replace `sf.info()` with `get_audio_info(filepath)['duration_seconds']`, which routes FFmpeg-only formats through `ffprobe`.

#### PE-1: Reference/hybrid "missing reference" fallback permanently flips a POOLED processor's config to adaptive — later reference/hybrid jobs silently ignore their reference
- **Location**: `auralis-web/backend/core/processing_engine.py:502-523`, `processor_pool.py:110-120`, `auralis/core/hybrid_processor.py:55,284-291`
- **Status**: NEW (introduced by the fix for CLOSED #4735)
- **Description**: When a reference/hybrid job has no usable reference, `_execute_job` mutates the processor's own config in place (`processor.config.set_processing_mode("adaptive")`) and never restores it. `HybridProcessor.__init__` stores the config by reference, so on a cache hit the mutated object is the *previous* job's config — filed back under the correct reference/hybrid pool key while internally set to adaptive. The next job with a valid reference silently gets adaptive processing.
- **Impact**: Silently wrong audio output for reference/hybrid mastering jobs after any reference-less hybrid job in the same session. No error, job reports success. Downgraded from HIGH: the shipped frontend never calls `/api/processing/process` or `/upload-and-process` — reachable only via direct API/test callers today.
- **Suggested Fix**: Do not mutate the processor's config for the fallback; acquire a separate adaptive processor, or restore the mode in a `finally` before returning to the pool. Best: mark the processor poisoned (reuse #4727's pattern) so a mode-flipped instance is never cached.

#### PE-2: `StreamlinedCacheWorker._process_chunk` keeps a timed-out `ChunkedAudioProcessor` in its LRU cache and reuses it on the next tick — unfixed sibling of #4999/#4727
- **Location**: `auralis-web/backend/core/streamlined_worker.py:504-524,123-140`, `chunked_processor.py:677-698`
- **Status**: NEW — explicitly left open by CLOSED #4999's own completeness check
- **Description**: `_process_chunk` wraps `processor.process_chunk_safe(chunk_idx)` in `asyncio.wait_for` (20s/60s ceiling). `wait_for` cancels only the asyncio wrapper; the OS thread keeps running, holding `_processor_lock` and mutating shared state. On timeout the method returns `None` — the processor stays cached and the next tick reuses it.
- **Impact**: Each timeout parks one default-executor worker behind the orphaned call; the 1Hz worker loop adds one per cycle, so a truly hung DSP call exhausts the shared executor in minutes and stalls every other `asyncio.to_thread` in the backend. Orphaned thread's late completion also poisons `LevelManager` history for subsequent chunks.
- **Siblings**: WS-1 (same #4999-incompleteness shape, different file).
- **Suggested Fix**: On `TimeoutError`, evict the cache entry (`pop` + `close()`) so the next tick builds a fresh processor, mirroring #4727's poison/discard treatment.

#### PE-3: UI processing settings (`eq`, `dynamics`, `level_matching`, `genre_override`) are accepted with 200 and silently ignored — #3490's documented "wire-up follow-up" was never filed
- **Location**: `auralis-web/backend/core/processing_engine.py:351-417`, `routers/processing_api.py:59-114`
- **Status**: NEW (residue of CLOSED #3490; no follow-up issue exists)
- **Description**: `ProcessingSettings` validates and accepts `eq`/`dynamics`/`level_matching`/`genre_override`/`sample_rate`; `_create_processor_config` consumes **only** `mode`. Everything else is logged at INFO and discarded; `sample_rate` isn't even logged. The job still returns success as though the settings were applied.
- **Impact**: Any API client gets a success response for a mastering job whose EQ/dynamics/level/genre/sample-rate requests had no effect. Mitigated by the shipped frontend not calling this route.
- **Suggested Fix**: Reject unsupported keys at the router with 400/422, or surface them as `ignored_settings` in the response, and file the promised #3490 follow-up.

#### SC-1: 47 live routes still return raw `dict[str, Any]` with no `response_model` — count has grown since #3838 was filed (~28)
- **Location**: `auralis-web/backend/routers/` — 13 routers, `playlists.py` all 10 routes worst offender
- **Status**: Existing: #3838 (count drifted: filed as "~28 across 7 routers", now 47 across 15 — 68% understated)
- **Description**: 97 real route decorators; 50 declare `response_model=`, 47 do not. `playlists.py`'s entire contract (10/10 routes) is unmodelled.
- **Impact**: No response validation, no OpenAPI schema, no serialization filtering — the mechanism behind already-filed drift bugs #4833/#4679/#5009.
- **Suggested Fix**: Prioritize `playlists.py`/`tracks.py` when #3838 is picked up; update its title/body with the corrected count.

#### SC-2: Three competing `Playlist` type declarations, none of which the backend enforces
- **Location**: `auralis-web/backend/routers/playlists.py:89-155`, `serializers.py:71-79`, `auralis/library/models/core.py:432-465`; frontend `playlistService.ts:17-31`, `types/api.ts:196-204`, `types/domain.ts:107-118`
- **Status**: NEW (sibling of #4679/#4612 for a different entity)
- **Description**: With zero `response_model` on playlist routes, the wire shape is defined only by `Playlist.to_dict()`. Three frontend types disagree on `description` required/optional/nullable and on `updated_at` vs `modified_at`.
- **Impact**: Any consumer reading `playlist.description.trim()` off a description-less playlist throws at runtime, because TypeScript says the field is required.
- **Suggested Fix**: Add a `PlaylistResponse` Pydantic model, declare it as `response_model`, drop the `modified_at` alias once consumers move, collapse the three TS types.

#### MW-1: `logger.debug()` is unreachable in every supported configuration, invalidating the "still available for diagnostics" rationale of the #4366/#4376/#4778 path redactions
- **Location**: `auralis-web/backend/main.py:241-246`
- **Status**: NEW
- **Description**: `uvicorn.run()` hardcodes `log_level="info"`; no `log_config=`, no env override, `--dev` does not raise verbosity. Three separate hardening changes deliberately demoted diagnostics (install path, DB path) to DEBUG on the stated premise the info stays retrievable — that premise is false.
- **Impact**: Every `logger.debug` diagnostic (frontend-path resolution, DB location, router-registration confirmations) is dead code. A support session investigating "wrong database opened" has no supported way to obtain the path the code deliberately preserved for exactly that purpose.
- **Suggested Fix**: `log_level=os.environ.get("AURALIS_LOG_LEVEL", "debug" if _is_dev_mode() else "info")`.

#### MW-2: `file://` is in the WebSocket origin allowlist but not the REST origin allowlist — split-brain between two checks that claim a shared contract
- **Location**: `auralis-web/backend/config/globals.py:29-47`, `config/middleware.py:285-343`
- **Status**: NEW
- **Description**: `build_ws_origins()` unconditionally adds `"file://"`; `OriginCheckMiddleware` validates REST requests against `cors_allowed_origins()`, which never emits it. No supported launch path (`desktop/main.js:340-346`) produces a `file://` renderer — the entry is simultaneously unreachable for the legitimate client and a live widening of the WS attack surface: any locally-opened HTML file can open a WebSocket to the running player and drive playback/read state, while the same page is correctly 403'd on REST mutations.
- **Impact**: A local HTML file (downloaded attachment, saved page) can control playback and observe broadcasts over WS while blocked on REST.
- **Suggested Fix**: Delete `| {"file://"}` from `build_ws_origins()`.

#### EH-1: A deleted-on-disk track returns HTTP 400, not 404 — and the `FileNotFoundError`→404 handlers written for that case are unreachable
- **Location**: `auralis-web/backend/routers/metadata.py:154-173,199-216,252-313`, `security/path_security.py:239-243`
- **Status**: NEW (distinct from #4807, which covers the text leak in the same 400 body)
- **Description**: `validate_file_path()` signals both traversal-rejection and "file doesn't exist" with the same `PathValidationError`. Every metadata call site maps it unconditionally to 400. The `except FileNotFoundError: → 404` handlers each route also carries are dead code, because the existence check raises before any file I/O runs.
- **Impact**: The most common desktop failure mode — user moved/deleted/unplugged a file while the library row survives — is reported as "malformed request", indistinguishable from an actual traversal attempt. Frontend cannot branch "file missing → offer relocate" vs "bad request".
- **Suggested Fix**: Split the existence check into its own exception (`PathMissingError(PathValidationError)`), map that subclass to 404 at metadata call sites.

#### EH-3: Normal (unenhanced) streaming has no timeout on its per-chunk disk read — the enhanced and seek paths both do
- **Location**: `auralis-web/backend/core/stream_normal.py:249-323`
- **Status**: NEW
- **Description**: Every other chunk-producing path bounds its worker-thread call with `asyncio.wait_for(..., timeout=CHUNK_PROCESS_TIMEOUT)`. `stream_normal.py` bounds only the semaphore acquire; its two `asyncio.to_thread(_read_audio_chunk, ...)` calls are unbounded.
- **Impact**: A normal-mode stream over stalled storage (unplugged drive, stalled network mount) hangs indefinitely, holding a stream semaphore permit and an executor thread with no recovery until client disconnect. Repeat attempts exhaust the stream semaphore.
- **Suggested Fix**: Wrap both `to_thread` reads in `asyncio.wait_for(..., timeout=CHUNK_PROCESS_TIMEOUT)`, route the timeout into the existing `failed_chunks` recovery branch.

#### PF-1: `GET /api/artists` still hydrates every full `Track` row (incl. `lyrics` + `fingerprint_vector` blobs) per artist, only to build a genre set and two `len()`s
- **Location**: `auralis/library/repositories/artist_repository.py:116-123,163-170`; `auralis-web/backend/routers/artists.py:145-171`
- **Status**: Partial regression/residue of CLOSED #4553
- **Description**: #4553 removed two never-read eager-load chains; what remains still fully hydrates every `Track` ORM row belonging to every artist on the page, when the router only consumes `track.genres[*].name` and two `len()` counts. `Track` carries two unbounded Text columns whose cost dwarfs the ~200 bytes the counts actually need.
- **Impact**: Default page (limit=50) over a library averaging 200 tracks/artist hydrates 10,000 full `Track` objects on every artist-browse load and every search keystroke. Scales with tracks-per-artist, not page size.
- **Suggested Fix**: Replace with `func.count()` correlated subqueries for the counts and one grouped `select(Artist.id, Genre.name)` query for the genre set — the `album_repository.py:93-158` pattern (`#4777`) is the model to follow.

#### PF-2: The whole `backend/analysis/` caching layer (`TrackAnalysisCache` + `AnalysisExtractor`, 590 lines) has zero instantiations
- **Location**: `auralis-web/backend/analysis/track_analysis_cache.py`, `analysis_extractor.py`
- **Status**: NEW (sibling of the "tested-but-unwired subsystems" cluster; #4749 found the same shape for `get_mastering_target_service()`)
- **Description**: `TrackAnalysisCache` is a complete LRU+TTL cache with a singleton accessor; `AnalysisExtractor` is its only consumer. Repo-wide grep for either outside those two files returns nothing in `auralis/`/`auralis-web/`. Secondary defect if ever wired: `TrackAnalysisCache._cache` is a plain unlocked `dict`, unlike every other backend cache.
- **Impact**: 590 lines of maintained, tested, benchmark-scripted code that never executes; passing tests mask the absence.
- **Suggested Fix**: Decide — wire `AnalysisExtractor` into the enhancement/similarity path that needs content analysis (add the missing lock first), or delete both modules + the benchmark script per No-Variants.

#### PF-3: 207 `asyncio.to_thread` call sites all share Python's default executor, sized `min(32, cpu_count+4)` — `MAX_CONCURRENT_STREAMS=10` can exceed it on a 2-4 core desktop
- **Location**: process-wide; anchors `core/audio_stream_controller.py:117-122`, `services/library_auto_scanner.py:276-282`, `core/stream_normal.py:250-267`
- **Status**: NEW (the consequence was noted in passing inside #4727's writeup; never filed on its own)
- **Description**: 207 `asyncio.to_thread` sites, none targeting a dedicated executor (`loop.run_in_executor(None, ...)`). Each admitted stream holds up to two executor slots (chunk DSP + look-ahead read). A running auto-scan (`asyncio.shield`ed) pins one slot for its entire duration.
- **Impact**: Once submissions exceed pool size, work queues FIFO and undifferentiated — a latency-critical chunk DSP call queues behind a DB read and behind the scan thread. User-visible effect: audio stalls during a library scan on low-core machines; `CHUNK_PROCESS_TIMEOUT` fires on queueing delay rather than a real hang, converting a stall into a skipped chunk.
- **Suggested Fix**: Create dedicated DSP/streaming and I/O executors at lifespan startup, sized off `MAX_CONCURRENT_STREAMS`; route streaming paths through the dedicated pool.

#### TC-1: Every test of the artwork-download endpoint fails on a 403 from `OriginCheckMiddleware` — the router is effectively untested and the failures were absorbed into the CI baseline
- **Location**: `tests/backend/test_artwork_download.py`; `config/middleware.py:303`
- **Status**: NEW (root cause generalized by TC-4)
- **Description**: All 7 tests of `POST /api/albums/{id}/artwork/download` fail with 403 before the route runs, because the test client sends no `Origin` header. All 7 are baselined, so CI is green.
- **Impact**: Zero effective coverage for the artwork-download route including its 503 degradation and 500 handler.
- **Suggested Fix**: Fix the shared `client` fixture (see TC-4), regenerate baseline.

#### TC-2: Two deterministically-failing backend tests are absent from `pytest-baseline.json` — the backend CI gate is red right now
- **Location**: `tests/backend/test_files_api.py:138-141,250-252`; `pytest-baseline.json`
- **Status**: NEW (successor situation to CLOSED #4739, which committed the baseline)
- **Description**: Two tests assert 405 method-not-allowed and get 404; neither appears in the baseline.
- **Impact**: `backend-tests.yml` fails on every push touching `auralis/**`/`auralis-web/backend/**`/`tests/**` regardless of the actual change.
- **Suggested Fix**: Decide the correct contract (405 vs 404), fix it, regenerate baseline from a CI artifact.

#### TC-3: 69 of the baseline's backend entries are stale — those tests now pass, and the ratchet silently re-permits their exact failures
- **Location**: `pytest-baseline.json`
- **Status**: NEW
- **Description**: Only 27 of 220+ backend test files were re-run (lower bound); 69 baselined entries now pass, including the entire `TestWebSocketReconnect` class.
- **Impact**: Whole subsystems believed to be gated are not — they can regress to failing at any time and CI stays green.
- **Suggested Fix**: Regenerate baseline from fresh CI artifact; add a `--check-stale` mode to `scripts/check_pytest_baseline.py`.

#### TC-4: A missing `Origin` header in the shared `client` fixture neutralises 131 REST tests across 10 files — the mutating half of the API surface has no effective coverage
- **Location**: `tests/backend/conftest.py:128-172`; `config/middleware.py:303`
- **Status**: NEW (generalises TC-1)
- **Description**: The `client` fixture patches `websocket_connect` to inject a loopback Origin but leaves plain HTTP verbs alone. 131 of 194 live failures across the 27 baselined `tests/backend/` files (68%) are this single cause.
- **Impact**: Player (17 endpoints), enhancement, queue, similarity, files, metadata, artwork all have zero passing write-path coverage. Conceals already-filed live bugs BE4-13, BE1-3, BE2-01 behind assertions that structurally cannot execute.
- **Suggested Fix**: `test_client.headers.update({"origin": "http://localhost:8765"})` in the `client` fixture; add one deliberate no-Origin test to keep the rejection covered; regenerate baseline.

#### TC-7: The #3828 deadlock regression test never reaches the code it guards — omits `force`, gets rejected at the enhancement-disabled gate, and its failure message blames a bug that is actually fixed
- **Location**: `tests/backend/test_system_api.py:653-724`; `ws_handlers/playback_commands.py:174-188`
- **Status**: NEW
- **Description**: `test_play_enhanced_releases_lock_before_awaiting_old_task` sends `play_enhanced` without `"force": True`; enhancement is disabled by default in the test app, so the handler returns at the gate before the patched `stream_audio` is ever called. The test fails 100% of the time, is baselined, and its assertion message reads "(#3828 not fixed)" though #3828 is CLOSED.
- **Impact**: The lock-ordering invariant that separates "stream cleanup runs" from "silent deadlock on next track change" has zero real coverage, and the baseline actively misdirects future investigation.
- **Suggested Fix**: Add `"force": True` to both payloads, matching the sibling test one class above; confirm green; drop the baseline entry.

#### TC-10: `test_normal_streaming_no_overlap.py` (#2099 regression suite) is 240 lines of self-simulated arithmetic — 6 of its 7 tests import no production code and are tautological
- **Location**: `tests/backend/test_normal_streaming_no_overlap.py:1-240`
- **Status**: NEW
- **Description**: Six of seven tests declare local variables restating the intended chunk geometry, then assert those locals against each other — they cannot fail regardless of what `core/stream_normal.py` does. The hardcoded `15.0` also duplicates `chunk_boundaries.CHUNK_DURATION` in four places.
- **Impact**: The normal streaming path's defining invariant (non-overlapping emission) has no executing coverage; a regression reintroducing #2099's duplication would leave this suite green.
- **Suggested Fix**: Rewrite against `core/stream_normal.py`'s real chunk-emission loop, importing constants from `chunk_boundaries`.

#### TC-11: Regression of #4780 — six streaming-semaphore/TOCTOU tests still assert against `AudioStreamController.active_streams`, an attribute that does not exist
- **Location**: `tests/backend/test_stream_disconnect_toctou.py:138-260`; `core/audio_stream_controller.py:119-208`
- **Status**: Regression of #4780 (CLOSED — only one of two carrying files was fixed)
- **Description**: `test_stream_disconnect_toctou.py` still reads `controller.active_streams` in four tests (now `AttributeError`), plus two more failing for related reasons. The controller exposes `self._stream_semaphore`, no `active_streams` mapping.
- **Impact**: Invariant 7 (semaphore release on every early-exit path) is unverified. A leaked slot silently reduces `MAX_CONCURRENT_STREAMS` until playback stops starting — a user-visible hang with no error.
- **Suggested Fix**: Rewrite assertions against `_global_stream_semaphore._value` (or add an `active_stream_count` property), remove the six baseline entries.

#### TC-13: The entire `test_e2e_workflows.py` suite (21 tests) fails on a removed `LibraryDatabase.add_track()` and is absent from the baseline
- **Location**: `tests/integration/test_e2e_workflows.py`
- **Status**: NEW
- **Description**: 21 of `tests/integration/`'s failures are in this one file, none baselined. Every one calls `LibraryDatabase.add_track()`, removed by the `LibraryManager`→`LibraryDatabase`/repository refactor.
- **Impact**: The only named end-to-end REST→engine→response suite in the repo does not run — a second independent reason `backend-tests.yml` is red, and no passing integration-level coverage for add-track, search, pagination, or artwork flows.
- **Suggested Fix**: Repoint `add_track` calls at `RepositoryFactory().tracks.create(...)`, regenerate baseline.

---

### LOW

#### RH-1: `/api/version` degraded-mode fallback reports `db_schema_version=16` while the live schema is 17
- **Location**: `auralis-web/backend/routers/health.py:45-63`
- **Status**: Regression of #4053
- **Description**: `auralis/__version__.py:11` declares `__db_schema_version__ = 17` (#3480); the degraded-build fallback in `health.py` was brought current on version string but left at 16.
- **Suggested Fix**: Import `__db_schema_version__` directly, or add it to `sync_version.py`'s propagation targets.

#### RH-2: `/api/processing/parameters` is owned by the enhancement router and registered unconditionally, while the rest of `/api/processing/*` is gated behind `HAS_PROCESSING`
- **Location**: `auralis-web/backend/routers/enhancement.py:506-606`; `routers/processing_api.py:194`; `config/routes.py:78-90`
- **Status**: NEW
- **Description**: `processing_api.py`'s 8 routes are conditionally registered; `enhancement.py` separately declares a 9th route on the same `/api/processing` namespace, always registered. No path conflict, only ownership drift.
- **Suggested Fix**: Move the route onto `processing_api` router, or rename into the enhancement namespace.

#### WS-3: `handle_play_normal` never records `active_stream_settings`, and `_cancel_prior_task` never clears it — enhanced settings survive into a normal stream
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:240-293,34-46`
- **Status**: NEW (sibling of WS-2, of OPEN #4704)
- **Description**: Only `handle_play_enhanced` writes the snapshot; nothing clears it on a subsequent `play_normal`. Latent — the shipped frontend no longer sends `play_normal` (#4541), but the command remains valid on the wire.
- **Suggested Fix**: Have `handle_play_normal` write a disabled snapshot; clear it in `_cancel_prior_task`.

#### WS-4: A transient send failure permanently disables heartbeat monitoring for that connection, and `websocket.close()` in the eviction path is unguarded
- **Location**: `auralis-web/backend/ws_handlers/connection.py:48-62`
- **Status**: NEW (sibling of OPEN #3870)
- **Suggested Fix**: Pre-check connection liveness before the heartbeat send; wrap the eviction `close()` in `contextlib.suppress(Exception)`.

#### WS-5: `StreamState.active_stream_settings` is per-connection while the other four registries are process-global — contradicts its own docstring
- **Location**: `auralis-web/backend/ws_handlers/context.py:28-43`; `routers/system.py:331-337`
- **Status**: NEW
- **Suggested Fix**: Add a module-level dict alongside the other four globals and pass it explicitly.

#### WS-6: `ping` is exempt from rate limiting and each one costs a `pong` send — an unmetered request/response amplifier
- **Location**: `auralis-web/backend/routers/system.py:47-51,389-396`; `ws_handlers/messages.py:30-37`
- **Status**: NEW
- **Description**: Desktop-only, localhost-bound — LOW, not a security finding, since the actor must already be a local process.
- **Suggested Fix**: Meter `ping` under a separate generous bucket; exempt only `pong`/`heartbeat`.

#### CP-3: Throwaway pre-warm processor never calls `close()` — leaks the SeekableSource temp WAV once CP-2 is fixed
- **Location**: `auralis-web/backend/routers/enhancement.py:172-204`
- **Status**: NEW (latent; would be HIGH once CP-2 is fixed)
- **Suggested Fix**: Wrap the loop in `try/finally: processor.close()`.

#### CP-4: LevelManager RMS history mixes two different measurement windows (15s processed vs 10s cached)
- **Location**: `auralis-web/backend/core/chunked_processor.py:521-534,455-481`; `stream_chunk_ops.py:83-97`
- **Status**: NEW (fold into CP-1's fix)

#### CP-6: `chunked_processor.py` module docstring still advertises 10-second chunks and inter-chunk crossfade
- **Location**: `auralis-web/backend/core/chunked_processor.py:3-12`
- **Status**: NEW (same class as CLOSED #4988, different file)
- **Suggested Fix**: Rewrite header to describe the real 15s/5s-context/10s-emission model with no crossfade.

#### CP-7: Chunk-window geometry is implemented twice — the load path bypasses `ChunkBoundaryManager`
- **Location**: `auralis-web/backend/core/chunk_operations.py:74-93` vs `chunk_boundaries.py:157-219`
- **Status**: NEW
- **Description**: No divergence today (boundaries fall on 5s multiples), but a latent trap: a future asymmetric-context change silently desyncs the two derivations.
- **Suggested Fix**: Have `load_chunk_from_file()` call `get_chunk_boundaries()` rather than re-deriving.

#### CP-8: Dead per-processor state: `previous_chunk_tail` and `chunk_interval` are written but never read
- **Location**: `auralis-web/backend/core/chunked_processor.py:180,263`
- **Status**: NEW (sibling of CLOSED #3880)
- **Suggested Fix**: Delete both attributes; if `chunk_interval` must stay public, make it a `@property`.

#### PE-4: Engine's own `ProcessorPool` is never drained at shutdown, unlike the `ProcessorFactory` cache
- **Location**: `auralis-web/backend/config/startup.py:170-178`; `core/processor_pool.py:41`
- **Status**: NEW (related to OPEN #4744, why it's currently inert)
- **Suggested Fix**: Add `ProcessorPool.close_all()`, call from `_shutdown`.

#### PE-6: `StreamlinedCacheWorker.trigger_immediate_processing` reports success for a failed chunk build, and has no production caller
- **Location**: `auralis-web/backend/core/streamlined_worker.py:554-605`
- **Status**: NEW
- **Suggested Fix**: `return await self._process_chunk(...) is not None`.

#### PE-7: `_remember_processor` closes an evicted processor with no in-use check, and does the `rmtree` on the event loop
- **Location**: `auralis-web/backend/core/streamlined_worker.py:126-140`
- **Status**: NEW (practically unreachable today — worker loop is strictly serial)
- **Suggested Fix**: Track in-flight use per cache key; offload `close()` via `asyncio.to_thread`.

#### SC-3: `PlaylistCreateResponse` and `PlaylistAddTracksResponse` describe contracts the backend does not implement, and have no importer
- **Location**: `auralis-web/frontend/src/types/api.ts:211,222-225`; `routers/playlists.py:190-193,305-308`
- **Status**: NEW (same class as CLOSED #4753, different entity)
- **Suggested Fix**: Delete both orphan types, or fix them to match and import them so drift becomes a compile error.

#### SC-4: `QueueHistoryStateSnapshot` is enforced on the request but re-flattened to `dict[str, Any]` on the response
- **Location**: `auralis-web/backend/routers/player.py:123-135,225-234,242-245`
- **Status**: NEW (residual of CLOSED #4374)
- **Suggested Fix**: Reuse `QueueHistoryStateSnapshot` as the response type too; lift the `Literal` onto `QueueHistoryEntryResponse.operation`.

#### SC-5: `TrackInArtist.album_id: int` uses `0` as a "no album" sentinel instead of being `int | None`
- **Location**: `auralis-web/backend/routers/artists.py:45-56,245`
- **Status**: NEW
- **Suggested Fix**: Change to `album_id: int | None = None`, matching `Track.to_dict()`.

#### SC-6: `POST /api/player/volume` returns an unrounded float while its paired `volume_changed` broadcast rounds to an int
- **Location**: `auralis-web/backend/routers/player.py:467-487`; `services/playback_service.py:355-366`
- **Status**: NEW (adjacent to OPEN #4711, which covers a different scale split)
- **Description**: This route also never calls `PlayerStateManager.set_volume`, so `GET /api/player/status` stays stale regardless.
- **Suggested Fix**: Return `volume_100` from the route; type `VolumeResponse.volume` as `int`.

#### SC-7: `PaginatedResponse[T]` is a generic envelope no route uses — five endpoints hand-roll its five fields instead
- **Location**: `auralis-web/backend/routers/pagination.py:41-115`; hand-rolled at `playlists.py`, `albums.py`, `tracks.py`, `artists.py`
- **Status**: Regression of #4902 (only the `compute_has_more`/`PaginationParams` half landed)
- **Suggested Fix**: Adopt `PaginatedResponse[T]` as `response_model`, or delete it and standardise on the per-router pattern `artists.py` already uses.

#### SC-8: Response-model `ge`/`le` bounds convert engine anomalies into 500s at the serialization boundary
- **Location**: `auralis-web/backend/routers/similarity.py:45,59`
- **Status**: NEW
- **Description**: Downgraded to LOW — disprove attempt found upstream NaN guards (#4217-era) already prevent the reaching value; stands as a convention point.
- **Suggested Fix**: Clamp/`nan_to_num` in `calculate_similarity_score` (DSP-owned), or drop `ge`/`le` from response models.

#### MW-3: `OriginCheckMiddleware` re-evaluates `is_dev_mode()` per request, turning #4802's one-shot boot warning into per-request spam under `AURALIS_DEV_MODE`
- **Location**: `auralis-web/backend/config/middleware.py:293,314-343`; `config/app.py:36-49`
- **Status**: NEW
- **Suggested Fix**: Compute the allowlist once at module level, mirroring `ALLOWED_WS_ORIGINS`.

#### MW-4: The two sibling temp sweeps at `startup.py:357` and `:653-654` still `shutil.rmtree` on the event loop, in the same lifespan where #4754 offloaded the chunk sweep
- **Location**: `auralis-web/backend/config/startup.py:344-357,648-654`
- **Status**: NEW
- **Suggested Fix**: Wrap both helpers in `asyncio.to_thread`, same treatment as #4754's chunk sweep.

#### MW-5: Rate-limit table omits the outbound artwork-download route and the destructive library-reset route
- **Location**: `auralis-web/backend/config/middleware.py:147-152`
- **Status**: NEW
- **Description**: `POST /api/albums/{id}/artwork/download` is the only route generating outbound third-party HTTP traffic; unbounded call rate risks the user's IP getting throttled by MusicBrainz/Discogs. `POST /api/library/reset` has no throttle either.
- **Suggested Fix**: Add `"/api/library/reset": (1, 60)`; rate-limit artwork download at the `ArtworkDownloader` level.

#### MW-6: `FRONTEND_MISSING_HTML` links to `/api/docs`, which is `None` in the only branch that renders it
- **Location**: `auralis-web/backend/main.py:190-202,229-235`; `config/app.py:67-76`
- **Status**: NEW
- **Suggested Fix**: Drop the link, or point at `/api/health`.

#### MW-7: `NoCacheMiddleware` forces `no-store` on content-hashed Vite bundles, defeating the hashing it was built to work around
- **Location**: `auralis-web/backend/config/middleware.py:50-64`
- **Status**: NEW
- **Suggested Fix**: Restrict the no-store rule to `/` and `*.html`; let hashed `assets/*` be cached `immutable`.

#### EH-2: `handle_query_error` maps only `OperationalError`; every filesystem error under `with_error_handling` becomes a 500
- **Location**: `auralis-web/backend/routers/errors.py:79-106`; e.g. `routers/artwork.py:266-330`
- **Status**: NEW
- **Suggested Fix**: Extend the taxonomy with `FileNotFoundError → 404`, `PermissionError → 403`.

#### EH-4: `drain_cancelled_task` suppresses `CancelledError` targeting the *calling* task, silently dropping a seek/disconnect cancellation
- **Location**: `auralis-web/backend/core/stream_chunk_ops.py:212-235`
- **Status**: NEW
- **Description**: Timing-narrow (one loop iteration's drain window); a seek issued at that instant is dropped, old stream keeps sending, `handle_seek`'s await blocks until the old track finishes.
- **Suggested Fix**: Distinguish the inner task's own cancellation from a cancellation aimed at the caller via `asyncio.current_task().cancelling()`.

#### PF-4: If `streamlined_cache` fails to initialise, every stream silently gets its own 512MB-capped `SimpleChunkCache` — the #3855 sharing fix has no fallback guard
- **Location**: `auralis-web/backend/routers/system.py:98,180,236`; `core/audio_stream_controller.py:183`; `config/startup.py:679-700`
- **Status**: NEW
- **Description**: Degraded mode reintroduces exactly what #3855 fixed and multiplies the memory ceiling to ~2.6GB across 10 admitted streams, with no warning that sharing was lost.
- **Suggested Fix**: Hoist the fallback to a single module-level singleton; log a WARNING when the streamlined cache is absent.

#### PF-5: `get_full_processed_audio_path()` materialises the entire processed track twice in RAM — unreachable today, the only unbounded-memory hole in the pipeline
- **Location**: `auralis-web/backend/core/chunked_processor.py:728-806`
- **Status**: NEW
- **Suggested Fix**: Delete both dead methods, or rewrite as a streaming append loop if an export feature is planned.

#### TC-5: 16 negative-payload tests assert 422 but are short-circuited to 403 — invalid-payload rejection is unverified for player, enhancement and metadata
- **Location**: `tests/backend/test_enhancement_api.py`, `test_player_api_comprehensive.py`, `test_metadata_api.py`, `test_queue_endpoints.py`
- **Status**: NEW (consequence of TC-4)
- **Suggested Fix**: Fixed automatically by TC-4's fixture change; verify the 16 tests go green afterward.

#### TC-6: All 20 routers have test files and 98 of 99 routes are referenced; `POST /api/library/refresh-references` remains the sole unreferenced route
- **Location**: `auralis-web/backend/routers/library.py`
- **Status**: Existing: #4715

#### TC-8: Three WebSocket payload-validation tests pass vacuously
- **Location**: `tests/backend/test_system_api.py:463-530`
- **Status**: NEW
- **Description**: Two assert only `isinstance(data, dict)` on the connect handshake frame (not a real response); the third's "invalid preset" error is actually the enhancement-disabled error. The #4600 contract (bad intensity falls back rather than 422s, NaN/inf rejected) is asserted nowhere.
- **Suggested Fix**: Drain handshake frames first; assert the concrete contract.

#### TC-9: Chunk boundaries/crossfade/edge cases are the best-covered area of the backend — positive coverage note
- **Location**: `tests/backend/test_chunked_processor*.py` and 7 siblings
- **Status**: Clean — 381 tests green, constants sourced correctly in 20 files. No finding.

#### TC-12: Real concurrency coverage exists and passes, but `tests/concurrency/test_thread_safety.py` is permanently excluded from CI because it hangs
- **Location**: `tests/concurrency/test_thread_safety.py`; `.github/workflows/backend-tests.yml:96-99`
- **Status**: NEW
- **Suggested Fix**: Bisect the hang (likely a non-daemon worker in a module-scope fixture), fix, drop the `--ignore`.

#### TC-14: Corrupt-file/missing-resource/timeout coverage exists but the dedicated `test_error_handling.py` is one of 11 modules hard-skipped at import
- **Location**: `tests/backend/test_error_handling.py:22` and 10 siblings
- **Status**: Existing: #4691
- **Description**: `test_playlist_operations.py`'s skip reason is factually stale — `PlaylistRepository` exists and `routers/playlists.py` ships 9 endpoints against it.

#### TC-15: Connect/send/receive/disconnect are all covered and 45/48 `/ws` tests pass; residual gaps are TC-7/TC-8/TC-11 plus a live disconnect-during-broadcast failure
- **Location**: `tests/backend/test_connection_manager.py::TestBroadcastDisconnectSafety` (2 tests failing live, baselined)
- **Status**: NEW (mostly a clean note; the broadcast-disconnect failure is new)
- **Description**: The disconnected socket is still present in `active_connections` after a broadcast — the classic source of dead-socket accumulation across reloads.
- **Suggested Fix**: Determine whether `ConnectionManager.broadcast()` genuinely fails to remove the socket, fix, drop baseline entries.

---

## Relationships

- **WS-1, PE-2** both trace to the same incomplete fix: closed **#4999**'s chunk-timeout abort landed only in `stream_enhanced.py`. Fix once in `stream_chunk_ops.py` to close both.
- **CP-1, CP-4** share one root cause (level-smoothing operates on the pre-extraction buffer) and should be fixed together.
- **PE-5** is the same "partial-sibling-fix" shape as WS-1/PE-2, but for closed **#4737** (temp-WAV cleanup) instead of #4999 (timeout).
- **TC-1** is fully subsumed by **TC-4** — same root cause, TC-4 is the general finding.
- **TC-5** is a direct consequence of **TC-4** — will resolve automatically once the fixture is fixed.
- **CP-2 → CP-3**: CP-2's silent no-op currently *masks* CP-3's leak (the leak path never fires because pre-warm aborts first). Fixing CP-2 without CP-3 would introduce a new HIGH-severity leak.
- **SC-1, SC-2, SC-3, SC-7** all point at the same underlying gap: `playlists.py` has zero `response_model` coverage across all 10 routes, which is why 3 independent competing type declarations and 2 dead orphan types could accumulate undetected.
- **MW-2** and the WebSocket security posture: `OriginCheckMiddleware` (REST) and `ConnectionManager.connect` (WS) are documented as sharing one contract; MW-2 shows they've drifted.
- **PF-3** provides context for why **PE-2**'s timeout threshold (20s/60s) and **CHUNK_PROCESS_TIMEOUT** (30s) can fire from queueing delay, not just genuine hangs — the two findings compound under load.

---

## Prioritized Fix Order

1. **WS-1 / PE-2** (HIGH + MEDIUM, shared root cause) — lift the #4999 timeout guard into `stream_seek.py` and `streamlined_worker.py`; ideally factor into one shared helper so this can't happen a third time.
2. **PE-5** (HIGH) — route the track-change prune through the same close-and-drop helper as LRU eviction. Direct memory/disk leak on every track change for a whole audio-format class.
3. **TC-4** (MEDIUM, but unblocks ~14 other findings' worth of test signal) — one-line fixture fix restores effective coverage for the majority of the write-path API surface and is a prerequisite for trusting any future CI run on player/enhancement/queue/similarity/files/metadata/artwork.
4. **CP-1 + CP-4** (MEDIUM) — makes two already-closed, already-paid-for fixes (#3831, #4352) actually reach the listener.
5. **TC-2, TC-3, TC-13** (MEDIUM) — regenerate `pytest-baseline.json` from a fresh CI artifact once TC-4's fixture fix and the 405/404 and `add_track` issues are resolved; this recovers the gate itself.
6. **PF-3** (MEDIUM) — executor sizing is a structural risk that compounds every other timeout-based finding in this report.
7. **WS-2** (MEDIUM) — user-visible silent-failure bug (seek after disabling mastering → silence).
8. **EH-1** (MEDIUM) — status-code fix unblocks a "relocate missing file" UX the frontend cannot currently build.
9. Remaining MEDIUM findings (MW-1, MW-2, PE-1, PE-3, SC-1/SC-2, PF-1, PF-2, TC-1/TC-7/TC-10/TC-11) — independent, can be parallelized across owners.
10. LOW findings — batch by dimension owner; several (CP-6, RH-1, SC-3/SC-7) are trivial-effort doc/consistency fixes suitable for a quick-wins pass.

---

## Deferred / Out of Scope

- Broader launcher/readiness recovery concerns are tracked separately in `docs/audits/AUDIT_RECOVERY_2026-07-24.md` (REC-01, REC-05).
- DSP-owned decisions (SC-8's NaN clamp location, CP-1's exact ramp-placement fix) are flagged for `dsp-specialist` rather than decided here.
- Existing OPEN issues re-verified still-present but not re-filed (partial list; full detail in each dimension's checklist notes above): #4361, #4681, #4701, #4702, #4734, #4736, #4653, #4587, #4738, #4744, #4707, #4605, #4930, #4837, #4815, #4806, #4834, #4807, #4761, #4711, #4728, #4808, #4798, #4800, #4747, #4682, #4764. One existing issue flagged as likely stale/closable: **#4814** (`tracks.py` now calls `validate_file_path` before the mutagen read that #4814 was about).
