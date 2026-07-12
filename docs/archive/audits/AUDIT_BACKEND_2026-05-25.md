# Backend Audit — Auralis FastAPI (2026-05-25)

**Auditor**: Claude Opus 4.7 (orchestrator) + 9 dimension subagents
**Scope**: `auralis-web/backend/` — `main.py`, 18 routers, `core/`, `services/`, `config/`, `schemas.py`, `encoding/`, `websocket/`, plus backend-related tests under `tests/`
**Prior cycle**: `docs/audits/AUDIT_BACKEND_2026-03-23.md` (BE-NEW-1 … BE-NEW-30 plus prior BE-22, BE-25, BE-27, BE-DIM1-01, DIM4-*)
**Dedup**: cross-checked against the prior cycle, open GitHub issues, and recent commit history (PR #3192 cache-bytes invalidation, PR #3325 progress-callback-under-lock, #574c3e2e queue WS dual-naming — all verified still in place).

---

## Executive Summary

| Severity | Count |
|----------|------:|
| CRITICAL | 0     |
| HIGH     | 5     |
| MEDIUM   | 26    |
| LOW      | 36    |
| **All**  | **67**|

(After cross-dimension consolidation; raw total across 9 dimensions was 86.)

### Key themes

1. **Cancellation safety in the streaming hot path is broken in two ways that compound** (HIGH). The `#3190` "skip failed chunk and continue" recovery is non-functional because the cancelled look-ahead task raises `CancelledError`, which `except Exception` cannot catch (Python 3.8+ derives it from `BaseException`); the same look-ahead task is also leaked on outer-exception / outer-finally exits, holding `HybridProcessor` references and worker-pool slots. The cumulative effect: every transient chunk-processing error tears down the entire stream instead of skipping the bad chunk, and every cancelled stream (every `seek`, `stop`, track-change) leaks DSP work.
2. **The offline-processing API is silently 100% broken** (HIGH). `ProcessingEngine.process_job` dereferences `result.audio` / `len(result.audio)` on a value that is actually a bare `numpy.ndarray`. Every successful job becomes `status=failed`, `error_message="An unexpected error occurred during processing"`. The bug is masked by `# type: ignore[union-attr]` and by `tests/backend/test_processing_api.py` mocking the whole `ProcessingEngine`.
3. **The offline-processing UI EQ/dynamics/level/genre controls are dead inputs** (HIGH). `ProcessingEngine._create_processor_config` writes UI settings to `config.adaptive.eq_gains` / `compressor` / `target_lufs` / `gain` / `genre_override` — none of which any code in `auralis/` ever reads. Only the implicit fingerprint-derived continuous parameters take effect. The WebSocket broadcast confirms the new settings, so the UI looks "responsive" while changing nothing audible.
4. **`POST /api/player/load` silently no-ops** (HIGH). Calls `audio_player.load_current_track()` via a `hasattr` check that always returns `False` in production (the real player exposes `load_track_from_library(track_id)`). Returns "Track loaded successfully" while only adding to the queue; never actually loads the audio file.
5. **Schema-vs-frontend contract drift is the single most prolific category** (1 HIGH + 4 MEDIUM + 5 LOW from Dim 5, plus ~44 endpoints returning raw `dict[str, Any]` with no `response_model`). The headline mismatches:
   - Backend emits `queue_updated`, frontend only subscribes to `queue_changed`/`queue_shuffled` → Redux queue **never updates** after add/remove/reorder/clear/shuffle.
   - `repeat_mode_changed` broadcasts `repeat_mode: "none"`, frontend Literal expects `'off' | 'all' | 'one'` → UI toggle gets stuck.
   - `scan_complete` has two backend shapes (`scan_time` vs `duration`) → manual scan toast shows "Scan complete — undefined seconds".
   - `playback_paused/resumed/stopped` payload depends on REST-vs-WS source (`{state}` vs `{success: true}`).
6. **Backend-vs-Electron-bundle drift is a real risk** (LOW, may be HIGH if the desktop copy is shipped as-is). `desktop/resources/backend/core/processing_engine.py` is missing the PR #3325 jobs-lock protection AND has `unregister_progress_callback` as sync — but the caller awaits it. If the desktop bundle ships this copy, every WS-disconnect-during-job hits `TypeError: object NoneType can't be used in 'await' expression`.
7. **A multi-axis "fire-and-forget asyncio.create_task" pattern** appears across `start_worker`, `_run_job`, `next_track`, `_prefetch_next_track`, `subscribe_job_progress`, `library_auto_scanner`. Only one site in the entire backend has `add_done_callback` — every other task silently swallows uncaught exceptions, including the job-queue main loop and the position-update next-track advance.
8. **Audio quality regression — every 10 s boundary has a 200 ms volume dip** (MEDIUM). The post-#3186 fade-in-only crossfade has no overlap-add; adjacent (non-overlapping) chunks have the head of each non-first chunk attenuated by `sin²(0→π/2)` while the prev tail is unmixed.
9. **Three independent unbounded caches** (one HIGH-ish from leaked processors, two LOW): `ProcessorFactory._processor_cache` (`HybridProcessor` instances, ~200 MB each), `MasteringTargetService.cache`, `StreamlinedCacheManager.mastering_recommendations` (singleton).

### Top 5 most impactful fixes (by user-visible impact)

| # | Finding | Why first |
|---|---------|-----------|
| 1 | **BE-NEW-36 (Engine)** — `result.audio` on `np.ndarray` | Every offline-mastering job currently fails. User-facing. |
| 2 | **BE-NEW-37 (Engine)** — UI EQ/dynamics/level/genre are dead inputs | User believes the UI controls work; they don't. |
| 3 | **BE-NEW-50 (WS / Chunking)** — `CancelledError` bypasses `except Exception` in skip-failed-chunk recovery + look-ahead orphan | Every transient chunk error tears down the stream, defeating the purpose of #3190. |
| 4 | **BE-NEW-38 (Routes)** — `POST /api/player/load` silently no-ops | Anyone calling the documented endpoint gets a lying 200 OK. |
| 5 | **BE-NEW-31 (Schemas)** — `queue_updated` vs `queue_changed` mismatch | Redux queue never updates after mutations — entire queue UX is stale. |

---

## Route Coverage Matrix (18 routers)

| Router | Dedicated tests | Verdict |
|---|---|---|
| `albums.py` | `test_albums_api.py` | covered |
| `artists.py` | `test_artists_api.py` | covered |
| `artwork.py` | multiple `test_artwork_*` | covered |
| `cache_streamlined.py` | `test_cache_streamlined_api.py` | covered |
| `enhancement.py` | `test_enhancement_api.py` | covered |
| `files.py` | `test_files_api.py` | covered |
| `library.py` | `test_library_api_comprehensive.py` | covered |
| `metadata.py` | `test_metadata_api.py` | covered |
| `player.py` | `test_player_api_comprehensive.py` | covered |
| `playlists.py` | `test_main_api.py` smoke only | **weak** |
| `processing_api.py` | `test_processing_api.py` (mocks engine — see BE-NEW-36) | misleading |
| `settings.py` | `test_main_api.py` smoke only | **weak** |
| `similarity.py` | `test_similarity_api_new.py`, `test_similarity_error_redaction.py` | covered |
| `system.py` (WS) | `test_system_api.py` | covered (WS message-type gaps — see BE-NEW-58) |
| `webm_streaming.py` | `test_webm_streaming_api.py` | covered |
| `dependencies.py` / `errors.py` / `pagination.py` / `serializers.py` (helpers) | own test files | covered |

All 18 router files have at least nominal coverage; the gaps are at the **handler-level** inside `system.py` (5 of 14 WS message types untested), the **services** layer the routers depend on (4 services totaling 1250 LOC have no unit tests), and the **core** chunked-processing modules (2 modules totaling 850 LOC untested). Plus `test_websocket_protocol_b3.py` fails collection entirely (495 LOC dead, HeartbeatManager unreachable).

---

## Findings

Numbered sequentially after consolidation. Cross-dimension duplicates are consolidated under a single ID and noted under "Originally surfaced by".

### HIGH (5)

#### BE-NEW-31: `ProcessingEngine.process_job` calls `result.audio` on a `numpy.ndarray` — every successful offline job marked FAILED
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:546, 557, 560, 561, 562`
- **Description**: `processor.process(audio)` (`auralis/core/hybrid_processor.py:175-182`) returns `np.ndarray | None`; the three implementations all `return processed` where `processed` is `np.ndarray`. `process_job` then accesses `result.audio` and `len(result.audio)` unconditionally. `np.ndarray` has no `.audio` attribute → `AttributeError` → caught by `except Exception` → rewritten as "An unexpected error occurred during processing" via `_safe_error_message(e)`.
- **Impact**: Four primary endpoints (`/api/processing/process`, `/upload-and-process`, `/job/{id}/download`, `/job/{id}`) are functionally broken. CI is green because `test_processing_api.py` mocks `ProcessingEngine`. Currently shipping in 1.2.0-beta.3.
- **Suggested fix**: `audio_data = result if isinstance(result, np.ndarray) else result.audio` and pull `processing_time`/`genre`/`lufs` from `processor.last_content_profile` or `processor.get_processing_info()`. Add an integration test that exercises `engine.process_job()` against a real `HybridProcessor`.

#### BE-NEW-32: `_create_processor_config` writes UI EQ/dynamics/level/genre to attributes no `auralis/` code reads — UI inputs are dead
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:404, 408, 418, 428-434, 438, 442, 450, 457-463`
- **Description**: `_create_processor_config` writes job settings to `config.adaptive.eq_gains` / `compressor` / `target_lufs` / `gain` / `genre_override`. None of these are declared fields on `AdaptiveConfig` (`auralis/core/config/settings.py:35-73`) — they're dynamically attached via `setattr` (hence the `# type: ignore[attr-defined]`). `grep -rn 'config\.adaptive\.eq_gains' auralis/` returns zero readers. Only the implicit fingerprint-derived continuous parameters affect output.
- **Impact**: For any future offline-mastering job (once BE-NEW-31 is fixed): manual EQ, manual compressor, level-matching target, and genre override have no audible effect. UI broadcasts the settings, so the user thinks they work.
- **Suggested fix**: Either declare the fields on `AdaptiveConfig` and wire `PsychoacousticEQ` / dynamics modules to read them, OR delete the dead `_apply_*_to_config` helpers and document that offline mastering supports only fingerprint-driven adaptive mode (and hide the dead controls in the UI).

#### BE-NEW-33: `POST /api/player/load` silently no-ops — `hasattr` always False, returns lying 200 OK
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/player.py:312`
- **Description**: `audio_player.load_current_track() if hasattr(audio_player, 'load_current_track') else True`. The method doesn't exist on `EnhancedAudioPlayer` (real method is `load_track_from_library(track_id)` at `auralis/player/enhanced_audio_player.py:290`). `hasattr` always False → conditional collapses to `True` → handler returns "Track loaded successfully" while only `add_to_queue` ran; the file is never loaded. A `test_main_api.py` mock sets `mock_player.load_current_track.return_value = True`, masking the bug in unit tests. Frontend has the constant `PLAYER_LOAD: '/api/player/load'` but doesn't call it, which has hidden the issue in practice.
- **Impact**: Anyone calling the documented endpoint (third-party tooling, future frontend code) gets a 200 with `{"message": "Track loaded successfully"}` while the player never loads audio. The `track_loaded` WS broadcast also fires, lying to subscribers.
- **Suggested fix**: `success = await asyncio.to_thread(audio_player.load_track_from_library, request.track_id)`. Drop the `add_to_queue` + `hasattr` dance. Add a regression test that hits the live player (not a mock).

#### BE-NEW-34: `queue_updated` (backend) vs `queue_changed` (frontend subscriber) — Redux queue never updates after any mutation
- **Dimension**: Schema Consistency
- **Location**:
  - `auralis-web/backend/services/queue_service.py:257, 330, 390, 444, 489, 531, 579`
  - `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:205-235`
  - `auralis-web/frontend/src/types/websocket.ts:217-251` declares `QueueChangedMessage` / `QueueShuffledMessage` — both unused on the wire
- **Description**: Backend NEVER emits `queue_changed` or `queue_shuffled`; every queue mutation goes out as `queue_updated` with `{action, queue_size}` (counts only, no tracks). The frontend only subscribes to `queue_changed` / `queue_shuffled` / `repeat_mode_changed`. The `queue_updated` payload also doesn't carry the tracks — even if the frontend subscribed, it'd need an extra round-trip.
- **Impact**: Every REST queue mutation (`POST /api/player/queue/add-track`, `DELETE /queue/{index}`, `PUT /queue/reorder`, `POST /queue/clear`, `POST /queue/shuffle`) leaves Redux `tracks`/`currentIndex`/`isShuffled` stale until the user navigates away.
- **Suggested fix**: Pick one shape. Emit `queue_changed` with `{tracks, current_index, action}` from `QueueService` and delete the dead `queue_updated`.

#### BE-NEW-35: Skip-failed-chunk recovery (#3190) crashes the stream on the next chunk + look-ahead orphan
- **Dimension**: Chunked Processing / WebSocket Streaming (consolidates Dim 2 BE-NEW-31, Dim 3 BE-NEW-31, Dim 7 BE-NEW-33)
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:644-717, 918-965, 1677-1739`
- **Description**: Two related bugs in all three streaming methods (`stream_enhanced_audio`, `stream_normal_audio`, `stream_enhanced_audio_from_position`):
  1. After `lookahead_task.cancel()` in the per-iteration `except`, the local is NOT reset to `None`. The next iteration `await lookahead_task` on the cancelled task → `CancelledError`. `CancelledError` derives from `BaseException` (not `Exception`) in Python 3.8+; neither the per-iteration `except` nor the outer `except Exception` catches it. The "Skip failed chunk and continue (#3190)" recovery is non-functional whenever a look-ahead has been started (every iteration except chunk 0).
  2. The outer `except Exception` (line 729) and outer `finally:` (line 738) do NOT cancel the look-ahead. On outer-block exception or `_send_stream_end()` failure, the look-ahead keeps running unobserved, holding a `ChunkedAudioProcessor` reference and competing for thread-pool workers / `_processor_lock`.
- **Impact**: (a) First chunk failure tears down the entire stream instead of skipping the bad chunk (user must reconnect). (b) Orphaned look-aheads accumulate under rapid stream-switching, leaking DSP work.
- **Suggested fix**: After every `lookahead_task.cancel()`: `try: await lookahead_task except (asyncio.CancelledError, Exception): pass; lookahead_task = None`. Also add `if lookahead_task and not lookahead_task.done(): lookahead_task.cancel()` (with an await) to the outer `finally:` block of all three methods.

---

### MEDIUM (26)

#### BE-NEW-36: `POST /api/files/upload` reads up to 500 MB into RAM and runs sync DSP/DB on event loop
- **Location**: `auralis-web/backend/routers/files.py:114-220`
- **Description**: `_MAX_UPLOAD_BYTES = 500 MB` cap is checked AFTER `await file.read()` (no size cap on the read). A 2 GB body is fully buffered before rejection. Then `tempfile.NamedTemporaryFile`, `tmp.write(content)`, `load_audio(temp_path)`, `shutil.move`, `repos.tracks.add(track_info)` all run sync on the event loop. Contrast `processing_api.py:226` which correctly does `await file.read(_MAX_UPLOAD_BYTES + 1)`.
- **Impact**: Memory DoS + every successful upload blocks the event loop for seconds. Whole-backend blast radius.
- **Suggested fix**: `await file.read(_MAX_UPLOAD_BYTES + 1)`, stream-write in 8 KB chunks, wrap `load_audio`/`shutil.move`/`repos.tracks.add` in `asyncio.to_thread`.

#### BE-NEW-37: `webm_streaming.py` sync DB / file-load on event loop (4 sites)
- **Location**: `auralis-web/backend/routers/webm_streaming.py:154, 168, 181, 266`
- **Description**: `GET /api/stream/{track_id}/metadata` and `/chunk/{chunk_idx}` call `repos.tracks.get_by_id` sync; metadata path additionally has `load_audio(track.filepath)` and `get_audio_info(track.filepath)` directly on the loop. Same anti-pattern as BE-22 (filed 2026-03-23, fixed in controller); regressed at the REST router.
- **Suggested fix**: Wrap each in `asyncio.to_thread`. Drop the `load_audio` fallback in favour of `get_audio_info` (header-only).

#### BE-NEW-38: `routers/metadata.py:batch_update_metadata` outer `except Exception` swallows nested `HTTPException(503)` → 500
- **Location**: `auralis-web/backend/routers/metadata.py:298-376`
- **Description**: `require_repository_factory(get_repository_factory)` raises `HTTPException(503)` when factory unavailable. The only `except` is `except Exception as e: raise HTTPException(500, "Batch update failed")`. `HTTPException ⊂ Exception` → 503 becomes 500. Other routers use `except HTTPException: raise; except Exception: …`.
- **Suggested fix**: Add `except HTTPException: raise` before the bare `except Exception`.

#### BE-NEW-39: `routers/settings.py` mutation handlers also swallow HTTPException(503) → 500 (4 endpoints)
- **Location**: `auralis-web/backend/routers/settings.py:77-91, 102-110, 112-121, 123-132`
- **Description**: Same pattern as BE-NEW-38, applied to `PUT /api/settings`, `POST /scan-folders`, `POST /scan-folders/delete`, `POST /reset`.
- **Suggested fix**: Same as BE-NEW-38; or replace `_repo()` with a `Depends`-injected dependency.

#### BE-NEW-40: `PUT /api/settings` accepts `dict[str, Any]` — no Pydantic model, no validation, no OpenAPI documentation
- **Location**: `auralis-web/backend/routers/settings.py:77-91`
- **Description**: Repo internally whitelists field names; route accepts any JSON object. OpenAPI clients can't discover settable fields; type-coercion errors become 500s instead of 422s.
- **Suggested fix**: Define `SettingsUpdateRequest(BaseModel)` with explicit `Optional` fields + `model_config = {"extra": "forbid"}`; add `response_model=SettingsResponse`.

#### BE-NEW-41: `cache_streamlined.py` sync `cache_manager.get_stats()` / `get_track_cache_status()` on event loop (3 sites)
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:83, 102, 168`
- **Description**: `get_stats`/`get_track_cache_status` are sync (`cache/manager.py:380, 389`). Frontend polls `/api/cache/health` and `/api/cache/stats` periodically — each poll blocks the loop briefly.
- **Suggested fix**: Wrap in `asyncio.to_thread`.

#### BE-NEW-42: `cache_streamlined.py` exposes raw `str(e)` in 5 HTTP 500 details (consolidates Dim 1 BE-NEW-38 + Dim 7 BE-NEW-35)
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:87, 122, 133, 156, 192`
- **Description**: `raise HTTPException(500, detail=str(e))` at every site leaks DB/file/symbol details. Same disclosure class as filed BE-27 (similarity.py).
- **Suggested fix**: Use the `_internal_error_response(user_message, exc)` pattern from `similarity.py:31-41` — log full exception with correlation id, return generic message + id.

#### BE-NEW-43: `repeat_mode_changed` and `player_state` broadcast `repeat_mode: "none"` — frontend Literal is `'off' | 'all' | 'one'`
- **Location**: `auralis-web/backend/player_state.py:64, routers/player.py:557-565, core/state_manager.py:142`
- **Description**: REST accepts `'off'|'all'|'one'` then maps `'off' → 'none'` server-side; broadcast carries `"none"`. Frontend writes `'none'` into Redux where the union expects `'off'`. UI toggle button gets stuck.
- **Suggested fix**: Drop the wire-level rename. Either broadcast `"off"` or change `PlayerState.repeat_mode` to `Literal["off","all","one"]`.

#### BE-NEW-44: `scan_complete` has two backend payload shapes (`scan_time` vs `duration`) — manual scan toast shows "undefined seconds"
- **Location**:
  - `auralis-web/backend/routers/library.py:555-567` (manual: `scan_time`)
  - `auralis-web/backend/services/library_auto_scanner.py:268-279` (auto: `duration`)
  - `auralis-web/backend/WEBSOCKET_API.md:444-459` documents a third shape with `tracks_added`
- **Description**: Frontend `useScanProgress.ts:85-89` reads `msg.data.duration` and `files_added`. Manual scan emits `scan_time`/`files_added`; auto-scan emits `duration`/`files_added`. After a manual scan, the duration is `undefined`.
- **Suggested fix**: One helper `_emit_scan_complete(connection_manager, result)` used by both call sites with canonical superset shape.

#### BE-NEW-45: `playback_paused/resumed/stopped` carry inconsistent payloads — `{state: ...}` (REST) vs `{success: true}` (WS)
- **Location**:
  - `auralis-web/backend/services/playback_service.py:136-139, 170-173, 202-206`
  - `auralis-web/backend/routers/system.py:561-567, 577-583, 618-624`
- **Description**: Same message type, two payloads depending on whether triggered by REST or in-band WS command. Frontend type expects `{state}`.
- **Suggested fix**: Pick `{state: 'playing'|'paused'|'stopped'}` everywhere.

#### BE-NEW-46: `track_changed.action="jumped"` (with extra `track_index`) but frontend Literal is `'next' | 'previous'`
- **Location**: `auralis-web/backend/services/navigation_service.py:188-194`
- **Description**: `jump_to_track()` emits `action: "jumped"` which the frontend type doesn't declare; the `track_index` field is the only carrier of "which track is now current" and isn't declared either.
- **Suggested fix**: Extend frontend Literal + add `track_index?: number`, OR fold `jumped` into the full `player_state` broadcast.

#### BE-NEW-47: `TrackInfo` uses `album_art`+`file_path` (player_state) vs `artwork_url`+`filepath` (REST serializers / WS contract)
- **Location**:
  - `auralis-web/backend/player_state.py:34, 35`
  - `auralis-web/backend/routers/serializers.py:18-42`
  - Frontend `transformBackendTrack()` defensively reads BOTH forms (evidence of the inconsistency)
- **Description**: Same logical field name diverges across the two serialization paths. Components reading `player_state.current_track.artwork_url` directly (not via `transformBackendTrack`) see `undefined` and show no artwork. The `is_enhanced` field on `player_state.TrackInfo` is never set true and isn't on the frontend type — dead field.
- **Suggested fix**: Rename `TrackInfo.album_art` → `artwork_url`, `file_path` → `filepath`, drop `is_enhanced`.

#### BE-NEW-48: `audio_chunk_meta.seq` field missing from frontend type; legacy `audio_chunk` type unused (consolidates Dim 2 BE-NEW-38 + Dim 5 BE-NEW-40)
- **Location**:
  - Backend emit: `auralis-web/backend/core/audio_stream_controller.py:1324-1356`
  - Frontend types: `auralis-web/frontend/src/types/websocket.ts:420-435, 686`
- **Description**: Backend sends `frame_seq` for client-side desync detection (per `#3189`), but the frontend type has no `AudioChunkMetaMessage` interface. Worse, `frame_seq` is a LOCAL that resets to 0 every chunk — even if the frontend bound to it, it'd misfire at every chunk boundary. Two related fixes needed (define the type AND make the counter actually monotonic stream-wide).
- **Suggested fix**: Define `AudioChunkMetaMessage` on the frontend; promote `frame_seq` to an attribute of the controller and thread it across chunks.

#### BE-NEW-49: ~44 endpoints across 7 routers return raw `dict[str, Any]` with no `response_model` — no validation, no OpenAPI documentation
- **Location**: `library.py` (14/0), `playlists.py` (8/0), `metadata.py` (4/0), `albums.py` (4/0), `artwork.py` (4/0), `settings.py` (5/0), `files.py` (2/0), `system.py` (3/0). Contrast `player.py` (18/18), `artists.py` (3/3).
- **Description**: Direct contributor to BE-NEW-44 (`scan_time` vs `duration`) and BE-NEW-47 (`file_path` vs `filepath`) — both would have been caught at write-time if the response model were enforced.
- **Suggested fix**: Write `TrackResponse`, `AlbumResponse`, `PlaylistResponse`, `ScanResultResponse`, `LibraryStatsResponse` (reusing `serializers.py` field lists) and add `response_model=` to every endpoint.

#### BE-NEW-50: Two duplicate `PaginatedResponse` models with incompatible shapes — 14 endpoints use yet a third
- **Location**: `schemas.py:86-106` vs `routers/pagination.py:20-92` vs ad-hoc in `library.py`/`artists.py`/etc.
- **Suggested fix**: Pick the flat shape (`{items, total, offset, limit, has_more}`), delete `schemas.PaginatedResponse` (dead code), migrate `ArtistsListResponse` and library/playlist/album routers to `routers.pagination.PaginatedResponse.create()`.

#### BE-NEW-51: `play_normal` doesn't update `_active_streaming_track_ids` — corrupts subsequent `play_enhanced` dedup
- **Location**: `auralis-web/backend/routers/system.py:455-549` (vs `play_enhanced` at 444-452 which does set it)
- **Description**: Dedup check at lines 335-345 reads `_active_streaming_track_ids[ws_id]`. The asymmetric maintenance causes a stale id to dedup a legitimate play_enhanced request after an A/B switch — the click is silently dropped.
- **Suggested fix**: Add `_active_streaming_track_ids[ws_id] = track_id` after `_active_streaming_tasks[ws_id] = task` in `play_normal` (symmetric to play_enhanced).

#### BE-NEW-52: WebM encoder orphans ffmpeg subprocess on `CancelledError`
- **Location**: `auralis-web/backend/encoding/webm_encoder.py:180-199`
- **Description**: Only `asyncio.TimeoutError` is handled. On `CancelledError`, `proc` is never killed; ffmpeg keeps running, holds temp files, outer `finally` may fail to unlink them.
- **Suggested fix**: `except (asyncio.TimeoutError, asyncio.CancelledError): with contextlib.suppress(...): proc.kill(); await proc.wait(); raise`.

#### BE-NEW-53: `AudioStreamController` detects WS disconnect by substring match `"close message" in str(e).lower()`
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:731, 978, 1751`
- **Description**: Depends on Starlette's internal exception wording (not a public contract). A Starlette upgrade changing wording → every disconnect misclassified as ERROR with a bogus `_send_error()` attempt.
- **Suggested fix**: `except WebSocketDisconnect: logger.info(...)` explicitly; let other exceptions take the error branch.

#### BE-NEW-54: Fire-and-forget `asyncio.create_task` without `add_done_callback` (5 sites)
- **Location**:
  - `auralis-web/backend/config/startup.py:291` (`processing_engine.start_worker`)
  - `auralis-web/backend/core/processing_engine.py:684` (`_run_job`)
  - `auralis-web/backend/core/state_manager.py:242` (`next_track`)
  - `auralis-web/backend/core/audio_stream_controller.py:677-681` (`_prefetch_next_track`)
  - `auralis-web/backend/services/library_auto_scanner.py:218` (progress)
- **Description**: Only one site in the whole backend (`enhancement.py:203`) uses `add_done_callback`. If `start_worker`'s outer loop ever exits via unexpected exception, the entire job queue silently stops; same for `next_track` (playback stops advancing). Python 3.14 stricter asyncio error-handling makes this more likely to bite.
- **Suggested fix**: Add a shared helper in `helpers.py`:
  ```python
  def _log_task_exception(t: asyncio.Task[Any]) -> None:
      if not t.cancelled() and t.exception() is not None:
          logger.error("Background task %s failed", t.get_name(), exc_info=t.exception())
  ```
  Apply at all 5 sites; consider a project-wide lint rule.

#### BE-NEW-55: `_prefetch_next_track` background work survives disconnect AND lands in a cache nobody else sees
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:677-681, 1141-1228`
- **Description**: Launched fire-and-forget at 80 % progress (also covered by BE-NEW-54). Even worse: `self.cache_manager` is a `SimpleChunkCache` created fresh per `AudioStreamController` (`system.py:354-362`); the prefetched chunk lands in a cache that no other stream will ever see. Functionally discarded work.
- **Suggested fix**: Either disable the prefetch until cache lifecycle is fixed, OR register the task in `self.active_streams` for cancellation on disconnect, OR hoist `cache_manager` to a process-wide singleton.

#### BE-NEW-56: Server-side fade-in at every non-first chunk creates a 200 ms volume dip at each 10 s boundary
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1230-1267, 1094-1119`
- **Description**: Commit `48a038ee` (#3186) removed the prev-tail mix but kept the `sin²(0→π/2)` fade-in. `_stream_processed_chunk` sends chunks with `crossfade_samples=0`, so the frontend does not overlap. Adjacent (non-overlapping) chunks have the head of each non-first chunk attenuated.
- **Impact**: Audible periodic dip / amplitude modulation every 10 s of playback.
- **Suggested fix**: Either re-introduce overlap-add (extract `chunk_interval + crossfade_samples` and tell the client), OR remove `_apply_boundary_crossfade` and rely on the DSP-with-context to produce seamless boundaries.

#### BE-NEW-57: `ProcessorFactory._processor_cache` unbounded — `cleanup_track()` is never called
- **Location**: `auralis-web/backend/core/processor_factory.py:230-253`
- **Description**: Each `ChunkedAudioProcessor.__init__` inserts a `HybridProcessor` keyed on `(track_id, preset, intensity, config_hash)`. No size limit, no LRU, no production caller of `cleanup_track()`. `HybridProcessor` holds compressor followers, EQ filter banks, fingerprint analysers, mastering targets — several MB each.
- **Impact**: For a 5000-track library at multiple presets/intensities: tens of MB/hour of moderate use, gigabytes/week of continuous use.
- **Suggested fix**: Add LRU cap (e.g., 32 entries) with eviction on `get_or_create`, OR call `processor_factory.cleanup_track(track_id)` in `AudioStreamController.stream_enhanced_audio`'s `finally:`.

#### BE-NEW-58: 5 of 14 WebSocket message types in `system.py` have no router-level test
- **Location**: `auralis-web/backend/routers/system.py:216, 455, 569, 585, 594`
- **Description**: `heartbeat`, `play_normal` (entire unenhanced playback path), `resume`, `buffer_full`, `buffer_ready` — none sent through `client.websocket_connect("/ws")` in tests. `test_websocket_flow_control.py` only exercises `asyncio.Event` in isolation; it never goes through the handler (see BE-NEW-71).
- **Suggested fix**: Add 5 router-level tests that send each message and assert the expected outgoing message type.

#### BE-NEW-59: `test_websocket_protocol_b3.py` (495 LOC) fails collection — HeartbeatManager has zero working tests
- **Location**: `tests/backend/test_websocket_protocol_b3.py:30-38`
- **Description**: Imports `ConnectionInfo`, `MessagePriority`, `MessageType`, `RateLimiter`, `WebSocketProtocol`, `WSMessage` from `websocket.websocket_protocol`. The module only exports `HeartbeatManager`. Pytest reports collection error; all ~40 tests (including the 8 valid `TestHeartbeatManager` tests at lines 258-330) never run.
- **Impact**: HeartbeatManager (governs WS-connection liveness) has zero working tests. Misleading test inventory.
- **Suggested fix**: Gut the file down to the 8 valid `TestHeartbeatManager` tests; immediately recovers coverage.

#### BE-NEW-60: 4 services classes used by `player.py` have no dedicated unit tests (~1250 LOC)
- **Location**: `auralis-web/backend/services/{playback,queue,navigation,recommendation}_service.py`
- **Description**: All instantiated in `routers/player.py:223-247`. Only docstring mention of `QueueService` in `tests/backend/test_api_endpoint_integration.py`. `QueueService` alone is 591 LOC including shuffle-fairness, history pruning, repeat-mode transitions, queue template hydration.
- **Suggested fix**: Add `test_queue_service.py`, `test_playback_service.py`, `test_navigation_service.py`, `test_recommendation_service.py` — `mock_repository_factory_callable` fixture already exists.

#### BE-NEW-61: `client` test fixture shares production `LibraryManager` and `~/.auralis/library.db`
- **Location**: `tests/backend/conftest.py:98-119`
- **Description**: Imports `main.app` (production singleton); runs real lifespan which constructs a real `LibraryManager()` against `~/.auralis/library.db`. No test-mode flag, no temp DB, no monkeypatch. Tests that mutate library state corrupt the developer's real DB. No parallel test execution possible.
- **Suggested fix**: Override `globals_dict['library_manager']`/`repository_factory`/`settings_repository` in the fixture, OR point `LibraryManager` at per-test `tmp_path`.

---

### LOW (36)

#### BE-NEW-62 → BE-NEW-97
(Grouped by theme; per-finding format same as above but condensed.)

| ID | Title | Location |
|----|-------|----------|
| BE-NEW-62 | `subscribe_job_progress` accepts unvalidated `job_id`; callbacks accumulate until disconnect | `routers/system.py:768-785` |
| BE-NEW-63 | WS disconnect cleanup unprotected — one failing callback unregister aborts later cleanup steps | `routers/system.py:800-831` |
| BE-NEW-64 | Seek branch updates `_stream_pause_events`/`_stream_flow_events` outside `_active_streaming_tasks_lock` | `routers/system.py:752-765` |
| BE-NEW-65 | `MAX_CONCURRENT_STREAMS` is global only — no per-connection quota | `core/audio_stream_controller.py:62-70` |
| BE-NEW-66 | Origin checks at `system.py` and `ConnectionManager` are inconsistent — `file://` accepted by one, rejected by the other | `routers/system.py:123-133` + `config/globals.py:22-70` |
| BE-NEW-67 | Seek error-recovery `recovery_position` discards the user's sub-chunk seek offset | `core/audio_stream_controller.py:1719-1737` |
| BE-NEW-68 | `proactive_buffer.get_buffer_status()` glob pattern stale — always returns empty set (dead code) | `core/proactive_buffer.py:108-135` |
| BE-NEW-69 | `_chunk_tails.pop()` runs without `_chunk_tails_lock` in failure-recovery, end-of-stream `finally`, prefetch paths | `core/audio_stream_controller.py:709, 740, 1213, 1758` |
| BE-NEW-70 | `_get_processor_cache_key` hashes `vars(config)` whose `repr()` excludes dynamically-attached `eq_gains`/`compressor`/etc. → key collision | `core/processing_engine.py:258-291` |
| BE-NEW-71 | `AudioProcessingPipeline.process_audio_async` is async in name only — sync `process_audio()` on event loop | `core/audio_processing_pipeline.py:318-363` |
| BE-NEW-72 | `ProcessorFactory.get_or_create()` returns cached processor without popping — concurrent streams of same track share one instance | `core/processor_factory.py:142-146` + `core/chunked_processor.py:142` |
| BE-NEW-73 | `ProcessingEngine._run_job` over-releases semaphore on cancel-during-acquire (latent) | `core/processing_engine.py:612-630` |
| BE-NEW-74 | `MasteringTargetService.cache` unbounded — `clear_cache()` never called from production | `core/mastering_target_service.py:66, 430-435` |
| BE-NEW-75 | `desktop/resources/backend/core/processing_engine.py` drifted — sync `unregister_progress_callback`, missing `_jobs_lock` (PR #3325 not in bundle) | `desktop/resources/backend/core/processing_engine.py:232-256` |
| BE-NEW-76 | `HAS_AURALIS`/`HAS_STREAMLINED_CACHE`/`HAS_SIMILARITY` are hardcoded `True` — feature gates do nothing | `main.py:62-86` |
| BE-NEW-77 | `enhancement_settings` (enabled/preset/intensity) in-memory only — reverts to defaults on every restart | `main.py:104-108`, `routers/enhancement.py:186, 246, 306` |
| BE-NEW-78 | `create_system_router` declares & documents `get_player_manager` — never receives it (dead param) | `routers/system.py:52, 64` |
| BE-NEW-79 | `logging.basicConfig` + `uvicorn.run(log_level="info")` produces duplicate log lines for every backend module | `main.py:25, 207` |
| BE-NEW-80 | All optional-router include failures share the same log severity — webm streaming (primary audio path) can fail silently | `config/routes.py:71-81, 195-204, 207-217, 220-229` |
| BE-NEW-81 | CORS covers `localhost:3000-3006` but only `127.0.0.1:3000` — Vite alt ports on the IP are blocked | `config/middleware.py:191-201` |
| BE-NEW-82 | Lifespan startup partial-failure leaves `library_manager` populated but supporting services unset | `config/startup.py:75-278` |
| BE-NEW-83 | `webm_streaming` exposes server-side filepaths in 404 responses | `routers/webm_streaming.py:160, 272` |
| BE-NEW-84 | `helpers.batch_operation` leaks raw `str(e)` into `BatchItemResult.error` (4 sites) | `helpers.py:177, 185, 247, 254` |
| BE-NEW-85 | `library_auto_scanner` broadcasts raw `str(exc)` as `library_scan_error` (info leak + no done-callback) | `services/library_auto_scanner.py:218, 234` |
| BE-NEW-86 | `library_updated` payload — backend `{reason}`, frontend type `{action, …counts}` (contract drift) | `routers/library.py:571-574`, `services/library_auto_scanner.py:283-286` |
| BE-NEW-87 | `cache_cleared` WS message bypasses `{type, data}` envelope and isn't on `WebSocketMessageType` | `routers/cache_streamlined.py:147-151` |
| BE-NEW-88 | `PlayerState.state` enum has `"error"` but frontend Literal omits it (hypothetical impact today) | `player_state.py:18-24` |
| BE-NEW-89 | `seek_started.track_id` + `audio_stream_error.recovery_position` not declared on frontend types | `routers/system.py:681-687`, `core/audio_stream_controller.py:1468-1475` |
| BE-NEW-90 | `CacheStatsResponse` / `TrackCacheStatus` duplicated in `schemas.py` and `routers/cache_streamlined.py` (router version `dict[str, Any]`) | `schemas.py:414-462`, `routers/cache_streamlined.py:22-37` |
| BE-NEW-91 | `SetPresetRequest.preset` typed as `str` with runtime validator (should be `Literal`) — value list duplicated in WS path | `routers/enhancement.py:40-49`, `routers/system.py:260` |
| BE-NEW-92 | `MasteringRecommendation.to_dict()` emits `alternative_profiles`/`created` not in frontend type; `is_hybrid` added by service layer | `auralis/analysis/adaptive_mastering_engine.py:54-77`, `services/recommendation_service.py:88-97` |
| BE-NEW-93 | `WebSocketMessageType` enum in `schemas.py` is inbound-only despite the name; missing ~25 outbound types | `schemas.py:202-227` |
| BE-NEW-94 | `helpers.create_cache_aware_response` returns `timestamp: time.time()` (Unix float); `SuccessResponse.timestamp` is ISO-8601 | `helpers.py:550-558` vs `schemas.py:32` |
| BE-NEW-95 | `RecommendationService.generate_and_broadcast_recommendation` runs full audio analysis on event loop via FastAPI BackgroundTasks | `services/recommendation_service.py:47-108, 110-159` |
| BE-NEW-96 | `QueueService.set_queue`/`add_track_to_queue` block event loop with sync DB lookups + audio-player calls | `services/queue_service.py:145-213, 215-276` |
| BE-NEW-97 | `StreamlinedCacheManager.mastering_recommendations` unbounded singleton — also unprotected by `self._lock` | `cache/manager.py:115, 480-494, 550` |
| BE-NEW-98 | `_send_pcm_chunk` allocates fresh array per frame via `astype('<f4')` even when already float32 — wasteful copies in audio hot path | `core/audio_stream_controller.py:1294-1296, 1353` |
| BE-NEW-99 | `MasteringTargetService` Tier-1 (DB) lookup is dead — every `ChunkedAudioProcessor` instantiates the service without injecting the fingerprints repo | `core/chunked_processor.py:135`, `core/mastering_target_service.py:53-69, 443-457` |
| BE-NEW-100 | `services/artwork_downloader.py` opens `aiohttp.ClientSession` per request and writes artwork to disk synchronously from async context | `services/artwork_downloader.py:153, 222, 273-292` |
| BE-NEW-101 | `GET /api/artists` `order_by` parameter not validated at route layer (sibling of filed `#2727` for `/api/library/tracks`) | `routers/artists.py:104` |
| BE-NEW-102 | `POST /api/playlists/{id}/tracks` does N×`add_track` sequentially via `asyncio.to_thread` | `routers/playlists.py:255-297` |
| BE-NEW-103 | `routers/metadata.py:batch_update_metadata` does N+1 sequential DB lookups in async loop | `routers/metadata.py:305-309, 344-346` |
| BE-NEW-104 | `routers/enhancement.py:get_processing_parameters` silently returns defaults on any exception | `routers/enhancement.py:439-536` |
| BE-NEW-105 | `DELETE /api/albums/{id}/artwork` returns 404 on repeat call — DELETE not idempotent | `routers/artwork.py:218-251` |
| BE-NEW-106 | Module-level `APIRouter` singletons in 9 routers (factory re-invocation duplicates routes) | `library.py:44`, `files.py:58`, `artwork.py:29`, `playlists.py:32`, `enhancement.py:30`, `player.py:49`, `system.py:44`, `webm_streaming.py:46`, `processing_api.py:30` |
| BE-NEW-107 | 2 chunked-processor sub-modules untested: `audio_processing_pipeline.py` (388 LOC), `mastering_target_service.py` (459 LOC) | tests missing |
| BE-NEW-108 | `analysis/track_analysis_cache.py` (263 LOC) + `analysis_extractor.py` (327 LOC) untested AND no production callers | tests missing / dead-code overlap |
| BE-NEW-109 | `LibraryAutoScanner` (370 LOC, startup-active scanner) has no dedicated test | tests missing |
| BE-NEW-110 | `WAVEncoder` (244 LOC) has no test file | tests missing |
| BE-NEW-111 | `tests/contracts/` directory referenced in audit scope does not exist (no contract test suite) | infra |
| BE-NEW-112 | `test_websocket_flow_control.py` exercises `asyncio.Event` semantics, not the WS handler — BE-28 not actually fixed | `tests/backend/test_websocket_flow_control.py:1-93` |
| BE-NEW-113 | No regression test for WS-disconnect-during-`subscribe_job_progress` callback (baseline BE-DIM1-01) | tests missing |
| BE-NEW-114 | No test for chunked-processor cache invalidation under preset/intensity change mid-stream | tests missing |

---

## Relationships

### Shared root causes

- **CancelledError handling gap.** BE-NEW-35 (recovery), BE-NEW-52 (ffmpeg), BE-NEW-53 (disconnect detection), BE-NEW-63 (cleanup) all share the same anti-pattern: `except Exception` clauses that do not catch `BaseException`-derived `CancelledError`, leaking subprocesses / tasks / cleanup steps on cancellation. A project-wide convention ("explicitly handle `CancelledError`; do not rely on `except Exception` for cancellation safety") would prevent the next instance.
- **`asyncio.create_task` without `add_done_callback`.** BE-NEW-54 enumerates 5 sites; BE-NEW-55 adds the prefetch task. One shared helper (`_log_task_exception`) and a project lint rule would close the entire class.
- **Schema-as-`dict[str, Any]`.** BE-NEW-49 (~44 endpoints) is the structural root cause of BE-NEW-44 (`scan_time` vs `duration`), BE-NEW-47 (`file_path` vs `filepath`), BE-NEW-86 (`reason` vs `action`), and indirectly BE-NEW-50 (pagination ad-hoc). Phase-B-1 schema work stalled before reaching library/playlist/album routers — completing it would prevent the next round of contract drift.
- **`HTTPException` swallowed by `except Exception`.** BE-NEW-38 (metadata), BE-NEW-39 (settings) share the pattern. Linting / convention: "Always `except HTTPException: raise` before `except Exception`."
- **Three unbounded caches** (BE-NEW-57, BE-NEW-74, BE-NEW-97) all expose `clear_*()` methods that nobody calls. A single "stale-cache" lifecycle audit (or a project convention "all caches MUST have an eviction policy at construction") would close the category.
- **Backend-vs-Electron-bundle drift** (BE-NEW-75) is a category risk: any backend fix that doesn't make it into `desktop/resources/backend/` silently doesn't ship. Either delete the checked-in copy and regenerate at build time, or add a pre-commit hook asserting equality.

### Compounds / chains

- **BE-NEW-31 + BE-NEW-32**: BE-NEW-31 hides BE-NEW-32 — until offline jobs actually run, you can't tell that EQ/dynamics/level/genre have no effect. Fixing #31 immediately reveals #32 in the field, so they should be fixed together (or #32 acknowledged in the #31 fix's release notes).
- **BE-NEW-55 + BE-NEW-57**: The look-ahead prefetch (BE-NEW-55) lands in a per-instance cache that's discarded, AND the underlying `_processor_cache` (BE-NEW-57) is unbounded. Fixing the cache lifecycle (single global cache + LRU) addresses both at once.
- **BE-NEW-44 + BE-NEW-49**: The scan-complete shape mismatch (#44) is a direct consequence of the `dict[str, Any]` return convention (#49). A `ScanCompleteResponse` Pydantic model with a `response_model=` would have caught the divergence at write-time.

---

## Prioritized Fix Order

### Now (this sprint)
1. **BE-NEW-31** — Fix `result.audio` → `result` cast in `process_job`. Tiny diff, unblocks the entire offline-processing API. Add an integration test that runs against a real `HybridProcessor`.
2. **BE-NEW-35** — Fix the `CancelledError` gap in `#3190` recovery + the look-ahead orphan in all three streaming methods. Single coherent patch (3 sites, same shape).
3. **BE-NEW-33** — Wire `POST /api/player/load` to the real `load_track_from_library`. 5-line fix; add a real-player regression test.
4. **BE-NEW-34** + **BE-NEW-43** — Pick canonical WS message shapes for queue and repeat-mode. Smallest change is to align the backend emit with the frontend types (drop the `'none'`-mapping; rename `queue_updated` → `queue_changed` with full payload).
5. **BE-NEW-42** — `cache_streamlined.py` `str(e)` → `_internal_error_response`. 5-site sweep, matches the BE-27 fix pattern.

### Soon (next sprint)
6. **BE-NEW-32** — Decide: declare `eq_gains`/`compressor`/etc. on `AdaptiveConfig` and wire engine readers (real fix), OR remove the dead helpers and hide the UI controls. Either way, document.
7. **BE-NEW-54 + BE-NEW-55** — Add `_log_task_exception` helper, apply at all 5 fire-and-forget sites. Hoist `cache_manager` to a process-wide singleton (closes BE-NEW-55 properly).
8. **BE-NEW-36 + BE-NEW-37 + BE-NEW-41** — `asyncio.to_thread` sweep across the obvious hot paths (`files.py` upload, `webm_streaming.py`, `cache_streamlined.py` polling endpoints).
9. **BE-NEW-44 + BE-NEW-45 + BE-NEW-47 + BE-NEW-49** — Schema/`response_model` consolidation epic. Start with `TrackResponse` / `AlbumResponse` / `PlaylistResponse` / `ScanResultResponse`; fan out to the 44 currently-untyped endpoints.
10. **BE-NEW-56** — Audio quality: re-introduce overlap-add OR remove `_apply_boundary_crossfade`. User-perceptible.
11. **BE-NEW-58 + BE-NEW-59 + BE-NEW-61 + BE-NEW-112** — Test infrastructure: trim `test_websocket_protocol_b3.py` to the 8 valid HeartbeatManager tests, fix `client` fixture (per-test DB), add the 5 missing WS message-type tests, replace `test_websocket_flow_control.py` with real handler round-trips.

### Quarter / epic
12. **BE-NEW-57 + BE-NEW-74 + BE-NEW-97** — Stale-cache lifecycle audit; add LRU caps to all three caches.
13. **BE-NEW-75** — Resolve the desktop-bundle drift policy (build-time copy vs hand-maintained + pre-commit check).
14. **BE-NEW-50 + BE-NEW-90** — Schema deduplication. Pick the flat `PaginatedResponse`, delete the dead duplicate, migrate routers.
15. **BE-NEW-60 + BE-NEW-107 + BE-NEW-109 + BE-NEW-110** — Backend services + analysis modules unit-test backfill (~3000 LOC currently untested).
16. **BE-NEW-111** — Stand up `tests/contracts/` to auto-detect WS / REST contract drift.

### Defer / track only
- **BE-NEW-65** (per-connection stream quota) — Desktop-only deployment makes this near-irrelevant; revisit if multi-user support is ever planned.
- **BE-NEW-88** (`PlayerState.state` `error`) — Hypothetical impact until something actually sets the state.
- **BE-NEW-108** (untested `track_analysis_cache` / `analysis_extractor`) — Determine dead-vs-latent first, delete if dead.

---

**Report status**: Ready for publish.
**Next step**: `/audit-publish docs/audits/AUDIT_BACKEND_2026-05-25.md`
**Labels for publishing**: `backend`, `bug`, severity label, plus domain labels (`websocket` / `streaming` for Dim 2/3 findings; `concurrency` for the CancelledError class; `performance` for BE-NEW-36/37/41/95/96/98; `tech-debt`/`maintenance` for the schema-consolidation epic).
