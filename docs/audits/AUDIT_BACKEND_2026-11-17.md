# Backend Audit Report - 2026-11-17

**Scope**: `auralis-web/backend/` (routers, WebSocket, chunked processing, processing engine, schemas, middleware/config, error handling, performance, tests, caching, seek/buffering). Eleven dimensions, fresh read of the current source; no prior report was consulted. Dedup baseline: all 6090 GitHub issues (highest #6346).

## Executive Summary

| Severity | NEW | Regression | Existing (open) | Total |
|---|---|---|---|---|
| CRITICAL | 0 | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 | 0 |
| MEDIUM | 12 | 0 | 2 | 14 |
| LOW | 41 | 2 | 2 | 45 |
| **Total** | **53** | **2** | **4** | **59** |

Counts are after cross-dimension de-duplication (10 duplicate reports merged into 6 findings). 55 findings are actionable (NEW + regression); 4 are already tracked by open issues (#5959, #5960, #6171, #5076) and are listed for completeness only. Do not re-publish those.

**Key themes**

- **No CRITICAL or HIGH findings.** The backend is in good shape: path security, origin checks, WebSocket lifecycle, chunk tiling and rate limiting all held up under a skeptical read.
- **Processor lease leak (D4-01)**: the #6091 exclusive-lease model is not paired on every acquire. Recommendation analysis leaks a warm `HybridProcessor` on every uncached call (reproduced), plus two cancel/timeout race windows.
- **Wrong-audio / degraded-audio risks in the caches**: a DSP fallback is persisted as a mastered chunk (D10-01), a stale Tier-1 fingerprint is cached under the new file signature (D10-02), and a failed durable-cache write fails a chunk whose audio is already rendered (D7-01).
- **Lossy-container geometry (D3-01, D11-01)**: follow-ups to #6345 / #6314. The last chunk can be empty and fail the stream, and header-less VBR MP3 geometry still follows ffprobe's wrong duration (reproduced with real files).
- **A hard 500 on a core endpoint (D5-01)**: `GET /api/player/status` fails whenever a track is loaded or the queue is non-empty (reproduced with the real router).
- **Fix-follow-through gaps**: many LOW findings are siblings a closed issue did not reach (#6092, #6188, #6210, #5891, #6162, #5499, #6048, #5810).
- **Startup robustness (D6-02)**: a non-UTF-8 chunk-cache owner marker in the system temp dir aborts startup on every launch (reproduced).

**Most impactful**: D5-01, D4-01, D10-01, D10-02, D3-01, D11-01, D6-02, D7-01, D7-02, D1-01, D9-01.

Reproduction side effect to know about: the D6 agent forced one real app startup against the system temp dir, which cleared `/tmp/auralis_chunks` (chunk cache only) and rewrote `/tmp/auralis_chunks.owner`. HOME was a scratch dir; the real library was untouched.

## Route Coverage Matrix

All 20 registered routers (from `auralis-web/backend/config/routes.py`) have both happy-path and error-path tests. Router-level findings are cross-referenced in the last column.

| # | Router (family) | Routes | Happy | Error | Test files (primary) | Notable gaps |
|---|---|---|---|---|---|---|
| 1 | processing_api (`/api/processing`) | process, upload-and-process, job/{id}, job/{id}/download, job/{id}/cancel, jobs, queue/status, presets, parameters, jobs/cleanup | Yes | Yes | test_processing_api.py, test_processing_parameters.py, test_processing_router_handler_seam_4670.py, test_processing_engine.py, test_processing_job_persistence_5278.py, test_queue_backpressure_real_engine_5964.py, integration/test_processing_engine_end_to_end.py, test_rate_limit_key_prefix_4728.py | `DELETE /jobs/cleanup` has a single happy test, no error case; `TestProcessingParametersDocumentation` baselined-failing |
| 2 | health (`/api/health`, `/api/version`) | 2 | Yes | Yes (503 readiness) | test_health_readiness_4684.py, test_system_api.py, test_main_api.py | none |
| 3 | system (`/ws`) | websocket | Yes | Yes | test_system_api.py, test_system_router_handler_seam_5832.py, test_audio_stream_*.py, test_ws_*_*.py, test_stream_*.py, test_websocket_*.py, security/test_websocket_security.py | none material (see Verified OK) |
| 4 | settings | GET/PUT /api/settings, scan-folders (add/delete), reset | Yes | Yes | test_settings_router.py, test_settings_router_handler_seam_5832.py, test_enhancement_settings_persistence_4587.py, test_update_settings_prunes_removed_folders_5523.py, test_scan_folder_delete_guard_5941.py, test_remove_scan_folder_prunes_tracks_5467.py, test_path_leak_regression.py, concurrency/test_settings_lock_all_writers_5334.py | `POST /scan-folders/delete` and `/settings/reset` have no explicit error-status assertion (guard 5941 asserts 200 forms) |
| 5 | files | POST /api/files/upload, GET /api/audio/formats | Yes | Yes | test_files_api.py, test_files_router_handler_seam_4670.py, test_upload_magic_bytes.py, test_upload_file_count_cap.py, test_upload_budgets_6167.py, test_upload_reads_header_not_audio_5962.py, test_file_format_support.py | `/api/audio/formats` happy only (no failure mode exists) |
| 6 | enhancement | toggle, preset, intensity, status, mastering/recommendation/{id} | Yes | Yes | test_enhancement_api.py, test_enhancement_router_handler_seam_4670.py, test_enhancement_preset_literal_4710.py, test_intensity_validation_contract.py, test_recommendation_abuse_bounds_5956.py, test_mastering_recommendation_response.py, test_enhancement_settings_*.py | none |
| 7 | artwork | GET artwork, POST extract, DELETE artwork, POST download | Yes | Partial | test_artwork_security.py, test_artwork_download.py, test_artwork_router_handler_seam_4670.py, test_artwork_updated_payload_4676.py, test_artwork_thumbnails.py, test_main_api.py | extract/delete error branches untested: D9-04 |
| 8 | playlists | list, get, create, update, delete, tracks add (x2), reorder, remove track, clear | Yes | Yes | test_main_api.py, test_playlist_db_error_not_a_404_5264.py, test_playlist_write_failures_5940.py, test_drag_drop_and_bulk_routes_6000.py, test_playlists_router_handler_seam_4670.py, test_playlists_pagination.py, test_playlist_integration.py | update empty-body 400 + broadcast payloads: D9-05 |
| 9 | library (stats, reset, refresh-references) | 3 | Yes | Yes | test_library_reset.py, test_library_reset_rate_limited_5069.py, test_refresh_references_endpoint_4715.py, test_cors_confirm_reset_preflight_5989.py, test_library_api_comprehensive.py | none |
| 10 | tracks | list, favorites, get, favorite POST/DELETE, lyrics | Yes | Yes | test_library_api_comprehensive.py, test_main_api.py, test_lyrics_persist_regression.py, test_lyrics_extraction_5939.py, test_track_list_payload_5906.py, test_sqlite_lock_contention_4773.py | none |
| 11 | library_scan | POST /api/library/scan, GET /scan/status | Yes | Yes | test_files_api.py, test_scan_start_and_cancel_frames.py, test_library_scan_status_endpoint_4821.py, test_scan_status_rate_limit_5911.py, test_library_scan_handler_seam_5166.py, test_library_scan_error_broadcast.py, test_manual_scan_prunes_missing_5458.py, test_scan_failures_reach_ui_5877.py, test_rate_limit_method_scoped_5318.py | none |
| 12 | fingerprint_status | GET /api/library/fingerprints/status, GET /api/tracks/{id}/fingerprint | Yes | Yes (404) | test_library_api_comprehensive.py, test_fingerprint_coverage_consistency_5891.py, test_fingerprint_spectral_unit_conversion_5470.py, test_fingerprint_key_contract_4429.py, test_origin_check_cross_site_get_6158.py | status endpoint HTTP test asserts only `isinstance(data, dict)` (shape pinned in 5891 instead) |
| 13 | metadata | GET fields, GET track, PUT track, POST batch | Yes | Yes (strong) | test_metadata_api.py, test_metadata.py, test_metadata_batch_atomicity.py, test_metadata_missing_file_404_5080.py, test_metadata_unreadable_file_422_5993.py, test_metadata_update_bounds_5266.py, test_path_leak_regression.py, security/test_metadata_mass_assignment.py | none |
| 14 | albums | list, fingerprints, get, tracks, fingerprint | Yes | Yes | test_albums_api.py, test_album_fingerprints_batch_5873.py, test_albums_router_handler_seam_4670.py, test_album_tracks_key_contract.py, test_library_api_comprehensive.py | `/albums/fingerprints` has only 2 calls (happy-leaning) |
| 15 | artists | list, get, tracks | Yes | Yes | test_artists_api.py, test_artist_*_contract_*.py, test_artist_list_query_cost_5084.py, test_artist_search_order_5904.py, test_library_api_comprehensive.py | none |
| 16 | player | status, load, seek, volume, queue (GET/POST/DELETE/reorder/move/clear/add-track/add-tracks/shuffle/repeat), next, previous | Yes | Yes | test_player_api_comprehensive.py, test_queue_endpoints.py, test_api_workflows_current.py, test_player_router_handler_seam_4670.py, test_router_split_5472.py, regression/test_queue_error_status_mapping.py, test_drag_drop_and_bulk_routes_6000.py, integration/test_phase4_player_workflow.py | vacuous reorder-bounds / seek-negative tests: D9-06 |
| 17 | cache_streamlined (`/api/cache`) | stats, track status, track DELETE, clear, health | Yes | Yes | test_cache_streamlined_api.py, test_cache_clear_without_manager_6002.py, test_cache_clear_sweeps_live_chunks_5340.py, test_cache_health_limits_5971.py, test_cache_stats_*_*.py, test_cache_cleanup_5257.py | `DELETE /track/{id}` has no error-case HTTP test |
| 18 | similarity (`/api/similarity`) | similar, compare, explain, fit | Yes | Yes | test_similarity_api.py, test_similarity_router_handler_seam_4670.py, test_similarity_explain_preconditions_4630.py, test_similarity_error_redaction.py, test_similarity_explain_contract.py, test_similar_graph_width_4864.py, test_similarity_db_locked_503_5381.py, concurrency/test_similarity_endpoint_concurrency.py | `/similar` success path covered only via handler-level mocks (HTTP tests assert 404/422) |
| 19 | similarity_graph | graph/build, graph/stats, DELETE graph | Yes | Yes | test_similarity_api.py, test_similarity_graph_success_5491.py, test_similarity_graph_single_flight_5945.py, test_graph_build_not_ready_message_5890.py | none |
| 20 | fingerprint_queue | status, enqueue/{id}, enqueue-all | Yes | Yes | test_similarity_api.py, test_enqueue_all_reports_queue_full_5920.py, test_fingerprint_queue_limit_annotation.py, test_fingerprint_queue_lookup_off_loop_5390.py, test_enqueue_offloaded_4702.py, test_enqueue_updated_tracks_5719.py | none |

Registration and wiring are themselves pinned by `test_router_wiring_pinned_5832.py`, `test_routes_optional_router_import_failure.py`, `test_router_factory_isolation_4361.py`, `test_router_dependency_isolation_5262.py` and `test_response_model_coverage.py`.

Router-level route-handler findings (Dimension 1): D1-01 settings, D1-02 fingerprint_queue, D1-03 files, D1-04 playlists, D1-05 processing/cache/enhancement/metadata, D1-06 fingerprint_status. Player: D5-01. Playlists: D7-02, D9-05.

## Findings

### MEDIUM (NEW)

### D5-01: GET /api/player/status returns 500 whenever a track is loaded or the queue is non-empty
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/player_state.py:44`, `auralis-web/backend/services/playback_service_base.py:68`, `auralis-web/backend/routers/player.py:97`
- **Status**: NEW
- **Description**: `TrackInfo.filepath` is declared `Field(exclude=True)` (server-only, #3205) but is still a REQUIRED field with no default. `PlaybackService.get_status()` returns `state.model_dump()`, which drops `filepath` from `current_track` and from every `queue` entry. The route is registered with `response_model=PlayerState`, so FastAPI re-validates that dict against `PlayerState`/`TrackInfo`, finds `filepath` missing, and raises `ResponseValidationError`, which surfaces as a 500. With no current track and an empty queue the dict has no `TrackInfo` in it and the call succeeds, which is why a "no track" smoke test passes. (`GET /api/player/queue` is not affected: its service returns `TrackInfo` instances, not a dump.)
- **Evidence**:
  ```python
  # player_state.py:44
  filepath: str = Field(exclude=True)
  # services/playback_service_base.py:67-68
  state = self.player_state_manager.get_state()
  return cast(dict[str, Any], state.model_dump())
  # routers/player.py:97
  router.add_api_route("/api/player/status", get_player_status, methods=["GET"], response_model=PlayerState)
  ```
  Reproduced with the real router and a real `PlayerStateManager` (`/tmp/audit/auralis/backend/_d5_repro.py`):
  `with track 500 Internal Server Error` / `no track 200`. Returning the `PlayerState` instance instead of its `model_dump()` gives 200 in a minimal FastAPI app. The OpenAPI schema for the same route also advertises `filepath` as required, which is never sent.
- **Impact**: The documented REST status endpoint (`ENDPOINTS.PLAYER_STATUS`, listed in the frontend config and in `useRestAPI` docs) fails for any client that calls it while something is loaded; the WS `player_state` path is unaffected (it dumps on purpose). No in-app consumer calls it today, which is why nothing noticed; any new caller or external integration gets a 500 plus a logged traceback.
- **Suggested Fix**: Have `get_status()` return the `PlayerState` instance (FastAPI then serializes it with `filepath` excluded), or split the wire DTO from the internal one (`filepath: str | None = Field(default=None, exclude=True)`). Add a test that loads a track into a real `PlayerStateManager` and asserts a 200 from `/api/player/status`.

### D1-01: `POST /api/settings/reset` wipes the scan-folder list and path trust but never prunes the tracks under those folders
- **Severity**: MEDIUM
- **Dimension**: Route Handler Correctness (sibling consistency across the routes that write `scan_folders`)
- **Location**: `auralis-web/backend/routers/settings.py:198-214` (vs. `settings.py:141-144` and `:180-195`)
- **Status**: NEW (sibling of closed #5467 / #5523; those fixed the other two `scan_folders` writers)
- **Description**: Three routes change the `scan_folders` column. Remove-folder and the `PUT /api/settings` diff both call `_revoke_folder()` (unregister the allowed directory AND `prune_tracks_under_folder`), because revoking trust alone leaves Track rows that are visible in the library but rejected with a 400 by every path-validated endpoint (#5467, #5523). `reset_settings` is the third writer: `repo.reset_to_defaults()` replaces the settings row (empty `scan_folders`) and the handler calls `clear_extra_allowed_directories()`, which drops trust for every runtime-registered folder, but it never prunes. The allowlist's built-in roots are only `~/Music` and `~/Documents` (`security/path_allowlist.py:DEFAULT_ALLOWED_DIRS`) plus `XDG_MUSIC_DIR`, so every library track outside those becomes untrusted. Nothing later repairs it: `scan_folders` is now empty, so no startup re-registration or auto-scan covers the old folders. The UI reaches this route (`components/settings/useSettingsDialog.ts:95` -> `settingsService.resetSettings()`).
- **Evidence**:
  ```python
  # settings.py:204-208
  settings = await asyncio.to_thread(repo.reset_to_defaults)
  # reset_to_defaults wipes the configured scan_folders list, so no
  # previously-registered extra directory should remain trusted (#3842).
  clear_extra_allowed_directories()
  await _notify_scanner(deps)
  ```
  versus the PUT route:
  ```python
  # settings.py:141-144
  for removed in previous_folders - new_folders:
      # Same revoke+prune as the dedicated delete endpoint (#5523): trust
      # revoked alone left the tracks behind, rejected with a 400.
      await _revoke_folder(deps, removed, sorted(new_folders))
  ```
  `reset_to_defaults()` (`settings_repository.py:143-160`) returns only the new settings, so the handler never learns the previous folder list. No test covers pruning on reset.
- **Impact**: After "Reset settings" in the dialog, every track outside `~/Music` / `~/Documents` stays in the library, browsable and queueable, but playback, metadata, recommendation and lyrics routes return 400 "Invalid track filepath" or "not in an allowed location". A user whose library lives on a separate mount (e.g. `/mnt/...`) loses playback of the whole library with no explanation, until they manually re-add the folder or reset the library.
- **Suggested Fix**: Read the stored `scan_folders` before the reset (or add a `reset_to_defaults_with_previous_folders` mirroring `update_settings_with_previous_folders`), then run `_revoke_folder(deps, folder, remaining=())` for each, so all three writers share the one revoke+prune step.

### D3-01: Last chunk can come up with 0 samples when the source holds less than its probed duration by more than the last chunk's remainder; the render fails and the stream ends "errored"
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_segment_extraction.py:87-99,141-146`; `auralis-web/backend/core/encoding/wav_encoder.py:164-165`; `auralis-web/backend/core/chunk_render_miss.py:68-87`
- **Status**: NEW (the closed #6345 fixed "pad the last chunk up to the probe"; its sibling "the last chunk is empty" is not handled)
- **Description**: `content_chunk_count()` allocates a trailing chunk for any probed duration `T` with `T mod 10 > 5` (e.g. `T=25.03` gives 3 chunks; the last carries `T-(10*2+5)=0.03s`). #6345 correctly stopped padding that last chunk when the decoder holds fewer samples than the probe (AAC priming 2112 samples, MP3 delay ~1105, or the 1%/0.5 s `LENGTH_AGREEMENT_TOLERANCE` that `can_seek_natively` accepts for libsndfile-read MP3/OGG). But when the shortfall is >= the remaining content of the last chunk (the last chunk's real content is <= the decoder's missing tail), the last chunk's trimmed buffer is shorter than `overlap_samples`, so `processed_chunk[overlap_samples:...]` is an EMPTY `(0, ch)` array. `extract_chunk_segment` only logs at debug for `is_last` and returns it. `WAVEncoder.encode_and_save` then raises `ValueError("Cannot encode empty audio array")` (not a `WAVEncoderError`), `render_chunk` runs `_invalidate_after_post_dsp_failure` (discards the leased HybridProcessor) and re-raises. The pump treats it as a failed chunk (`failed_chunks.append`, `audio_stream_error stream_continues=True`) and the stream finishes with `reason="errored"`. The penultimate chunk is additionally padded with silence (it is not `is_last`, so the `padded with silence` branch applies) for the part of its core that the decoder never produced. Window of affected tracks: `T mod 10` in `(5, 5 + shortfall/10)` per priming-delta, i.e. roughly 0.25-0.5% of M4A/MP3 files, more for MP3s whose length libsndfile under-reports within tolerance.
- **Evidence**: Reproduced against the real `ChunkedAudioProcessor.process_chunk` with a 25.0 s WAV and the probe patched to 25.03 s (what a container with 1323 priming samples reports):
  ```
  total_chunks 3
  chunk 0 ok (661500, 2)
  chunk 1 ok (441000, 2)
  chunk 2 FAILED ValueError Cannot encode empty audio array
  ```
  Code:
  ```python
  # chunk_segment_extraction.py:99 (last-chunk branch)
  extracted = processed_chunk[overlap_samples:overlap_samples + expected_samples]
  # :141
  if current_samples < expected_for_validation and is_last:
      logger.debug(f"Chunk {chunk_index} (last): source ended ...")   # returns the empty array as-is
  # wav_encoder.py:164
  if audio.size == 0:
      raise ValueError("Cannot encode empty audio array")
  ```
  Synthetic run of `trim_context` + `extract_chunk_segment` for `T=25.03`, actual samples `T*sr-2112`: chunk 1 is `789 samples short ... padded with silence`, chunk 2 `len 0`, total emitted 1102500 vs source 1101711.
- **Impact**: For the affected tracks the final chunk of the enhanced/seek stream always fails: ERROR log + `audio_stream_error`, `audio_stream_end reason="errored"`, the frontend sets "Playback ended with gaps" and does not dispatch `completeStreaming`, and the session auto-advance only fires on `streamingState === 'complete'` (`usePlaybackSessionHooks.ts:116`), so the queue does not advance at the end of the track. Up to ~48 ms of silence is also padded onto the end of the penultimate chunk. The cached state is not poisoned (nothing is written), so every replay fails the same way.
- **Suggested Fix**: Treat a zero-length last segment as "no content": `extract_chunk_segment`/`render_chunk` should return an empty segment without encoding, and `pump_chunks` should skip sending it and not record a failure (or clamp `total_chunks` once the decoder's real length is known). Also stop padding a non-last chunk when it is the one carrying the decoder-short tail (`chunk_index == total_chunks - 2`).

### D4-01: Recommendation analysis (and two race windows) take a ProcessorFactory lease that is never released
- **Severity**: MEDIUM
- **Dimension**: Processing Engine (lease pairing / resource cleanup)
- **Location**: `auralis-web/backend/services/recommendation_analysis.py:47-60`; `auralis-web/backend/core/stream_enhanced_lifecycle.py:110-131,151-152`; `auralis-web/backend/core/chunk_processor_lease.py:29-45`; `auralis-web/backend/core/chunk_render.py:139,151`
- **Status**: NEW
- **Description**: Since #6091 every `ChunkedAudioProcessor` with a non-None preset takes an exclusive `HybridProcessor` lease in `__init__` (`processor_factory.acquire`, `chunk_processor_init.py:179`), and `close()` is the only thing that hands it back (`release_lease`). The lease also records a strong reference in `ProcessorFactory._active_processors[track_id]` (`processor_lease.py:111`), which nothing but `release_lease`/`discard_lease`/`clear_cache` removes. Three call paths create a leased processor that no one closes:
  1. **Every mastering recommendation analysis (deterministic).** `_analyze()` builds `ChunkedAudioProcessor(..., preset=DEFAULT_PRESET, ...)` on the live-stream factory (it does not pass `processor_factory=`, so it also pops a warm released instance of the live stream's key), calls `get_mastering_recommendation()`, and returns without `processor.close()`. This runs on every `POST /api/player/load` (`player_playback.py` schedules `generate_and_broadcast_recommendation` for each load) and on `GET /api/player/mastering/recommendation/{id}` whenever the result is not cached.
  2. **Stream init that is cancelled or times out.** `run_enhanced_stream` constructs the processor in `asyncio.to_thread` under `wait_for`. On `TimeoutError` (or a `CancelledError` from seek/stop/skip/disconnect) the thread is abandoned; `stream.processor` stays `None`, so the `finally` (`:151`) skips `close()`. The cancel event only makes a tier-3 analysis wait give up; `ChunkedAudioProcessor.__init__` has no cancel check after `init_fingerprint_and_processor`, so the orphaned thread still finishes construction and leases a processor nobody owns.
  3. **Render thread outliving its stream's `close()`.** `process_chunk_core` runs `processor.load_chunk(...)` (disk decode) and only then `processor.hybrid_processor()`. `hybrid_processor()` re-leases whenever `self.processor is None`, and `close()` leaves no closed marker. A seek/stop that lands during the load phase (the cancel poll happens before it, `chunk_stream_state._raise_if_cancelled`) lets the orphaned executor thread lease a new processor on an already-closed `ChunkedAudioProcessor`; the pre-write cancel check then raises, and the lease is never returned.
- **Evidence**:
  ```python
  # services/recommendation_analysis.py:47-60
  def _analyze() -> dict[str, Any] | None:
      from core.chunked_processor import ChunkedAudioProcessor
      processor = ChunkedAudioProcessor(
          track_id=track_id, filepath=filepath, preset=DEFAULT_PRESET,  # analysis only
          intensity=DEFAULT_INTENSITY, chunk_cache={}, cancel_event=abandoned,
      )
      rec = processor.get_mastering_recommendation(confidence_threshold=confidence_threshold)
      return cast(dict[str, Any], rec.to_response(track_id)) if rec is not None else None   # no close()
  ```
  ```python
  # core/chunk_processor_lease.py:37 - re-leases after close()
  if self.processor is None:
      self.processor = self._processor_factory.acquire(...)
  ```
  Reproduced against the live code (scratch HOME, synthetic 20 s WAV): three `ChunkedAudioProcessor(track_id=101/102/103, preset='adaptive')` + `get_mastering_recommendation()` with no `close()` leave `get_processor_factory().active_processors == {101, 102, 103}` and an empty cache; a processor that is `close()`d is returned to the cache (`cache 1`).
- **Impact**: One `HybridProcessor` (plus its config deep copy and fixed targets) stays strongly referenced per distinct track loaded, for the life of the backend; the warm instance the live stream had released for the same key is consumed instead of returned, defeating the #6091 warm-reuse. Measured size of an idle instance is small (~75 KB), so this is slow growth rather than an outage, but it breaks the stated invariant that every acquire is paired with `release_lease`/`discard_lease` and grows with library browsing. Any future `SeekableSource` temp-WAV ownership on this path would leak a file too (the #5253 class), because `close()` also releases that.
- **Suggested Fix**: Close the processor in `_analyze()` (`try/finally: processor.close()`), or pass `preset=None`-style analysis that takes no lease. In `run_enhanced_stream` hand the constructed object back to the caller even when abandoned (e.g. wrap construction so the thread closes its result if `cancel_event` is set after `__init__`), and give `ChunkedAudioProcessor` a `_closed` flag so `hybrid_processor()` refuses to lease after `close()`.
- **Merged**: Also reported by: D3-03, D7-04, D8-04, D11-02 (same root cause, merged; the sub-variants are the recommendation-analysis path, the stream-init timeout/cancel path, the proactive-buffer cancel path, and the orphaned render thread re-leasing after `close()`).

### D6-02: Startup aborts (non-self-healing) when the chunk-cache owner marker holds non-UTF-8 bytes — `claim_chunk_cache` only catches `OSError` and the call is unguarded in the lifespan
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config (startup/shutdown)
- **Location**: `auralis-web/backend/config/startup/tempfiles.py:159-172`, called from `:231`; lifespan call `auralis-web/backend/config/startup/__init__.py:168`
- **Status**: NEW (same root-cause class as closed #6155 / #4855: fixed-name `auralis_*` entries directly in the shared system temp root; #6155 hardened the three directories, not the owner-marker *file*)
- **Description**: `claim_chunk_cache()` does `owner_marker.read_text().strip()` inside `try/except OSError`. `read_text()` raises `UnicodeDecodeError` (a `ValueError`, not `OSError`) for non-UTF-8 content, so it escapes `claim_chunk_cache`, `_cleanup_temp_directories()` and — because `lifespan()` awaits `_cleanup_temp_directories()` bare, unlike every other startup step (`sweep_fingerprint_store`, `_init_*` all catch) — aborts the whole lifespan ("Application startup failed"). The marker is only rewritten *after* the read, so the failure never heals; if the file is owned by another local account in a sticky `/tmp` it cannot even be deleted by the user. The marker lives at a predictable name (`/tmp/auralis_chunks.owner`) in the shared temp root, so a co-resident account can plant it (a disk-full/corrupted write would also do it).
- **Evidence**:
  ```python
  # tempfiles.py:159-172
  try:
      if owner_marker.exists():
          recorded = owner_marker.read_text().strip()
          ...
  except OSError as e:
      logger.debug(f"Could not read chunk-cache owner marker: {e}")
  ```
  Reproduced: marker containing bytes `\xff\xfe\x80` -> `claim_chunk_cache(...)` and `asyncio.run(_cleanup_temp_directories())` (with `tempfile.tempdir` pointed at the scratch dir) both raise `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff`. `startup/__init__.py:168`: `await _cleanup_temp_directories()` has no try/except.
- **Impact**: Backend (and therefore the whole Electron app) refuses to start on every launch until the file is removed; for housekeeping that is documented elsewhere as "must not block the app starting" (`fingerprint_store.py`).
- **Suggested Fix**: Catch `(OSError, ValueError)` (or read bytes and `decode(errors="ignore")`) in `claim_chunk_cache`, and wrap the `_cleanup_temp_directories()` call in the lifespan like the neighbouring sweep so housekeeping can only degrade, never abort startup. Optionally open the marker with `O_NOFOLLOW` and verify ownership (`lstat().st_uid`) as `create_secure_temp_dir` does.

### D7-01: A failed durable chunk-cache write fails the whole chunk even though the rendered audio is already in memory
- **Severity**: MEDIUM
- **Dimension**: Error Handling & Resilience
- **Location**: `auralis-web/backend/core/chunk_render_miss.py:62-89` (the write), `auralis-web/backend/core/chunk_streaming.py:109-121` (single-flight followers), `auralis-web/backend/core/stream_chunk_ops.py:74` (the path is discarded by the only streaming caller)
- **Status**: NEW
- **Description**: `render_chunk` runs the DSP, then persists the segment with `encode_and_save_from_path(...)` and `_path_cache.store(...)` inside the same `try` as the DSP. Any write failure (ENOSPC on a full or tmpfs temp root, a permissions or quota error, a `WAVEncoderError` from the atomic-save wrapper) lands in `except Exception:`. That branch calls `_invalidate_after_post_dsp_failure()` (which discards the stream's leased `HybridProcessor`, because `_dsp_state_advanced` is already True) and re-raises. The pump then reports `Failed to process audio chunk N` and skips the chunk. The processed PCM array (`extracted_chunk`) exists at that point and is exactly what the stream would have sent. The pump never uses the path: `process_chunk_only` does `_chunk_path, pcm_samples = ...` and drops it. The disk file is only a cache for later hits and for single-flight followers.
- **Evidence**:
  ```python
  # chunk_render_miss.py
  68:        chunk_path = processor._wav_encoder.encode_and_save_from_path(
  ...
  79:        processor._path_cache.store(chunk_index, chunk_path)
  80:    except ChunkCancelledError:
  ...
  86:    except Exception:
  87:        _invalidate_after_post_dsp_failure(processor, chunk_index)
  88:        raise
  # chunk_render.py:159   processor._dsp_state_advanced = processor.preset is not None
  # stream_chunk_ops.py:74  _chunk_path, pcm_samples = await asyncio.wait_for(...)   # path unused
  ```
- **Impact**: When the temp root is full (the codebase already notes it can be a RAM tmpfs, and FFmpeg decode WAVs, the 512 MB chunk cache and uploads all compete for it), every enhanced chunk fails. The user hears silence plus one error frame per chunk, although the audio was computed. Each failure also throws away the leased processor, so the limiter and EQ state continuity is lost for the next chunk. Single-flight followers cannot read a file that was never written, so each re-renders and fails the same way.
- **Suggested Fix**: Treat the cache write as best-effort: catch `OSError` / `WAVEncoderError` around the encode and store only, log a WARNING, skip `_path_cache.store`, and still return `(None or the intended path, smoothed array)`. Do not invalidate the processor for a failure that happened after the DSP result was already secured. Keep raising for the DSP itself.

### D7-02: `POST /api/playlists/{id}/tracks` reports a failed database write as `200 "Added 0 track(s)"`
- **Severity**: MEDIUM
- **Dimension**: Error Handling & Resilience
- **Location**: `auralis/library/repositories/playlist_membership_mixin.py:239-277` (guarded repository method), `auralis-web/backend/routers/playlists_tracks.py:20-68` (route), `auralis-web/frontend/src/components/library/Items/tracks/useTrackContextMenu.ts:68-70` (consumer that ignores the count)
- **Status**: NEW (same class as closed #5940 and #5264; neither covered `add_tracks`, and the later fix left `add_tracks` on the guarded swallow)
- **Description**: `PlaylistRepository.add_tracks` is the one playlist mutator still wrapped in `self._guarded(...)`. `_GuardedScope.__exit__` swallows every `Exception`, logs it, and falls through to `return 0`. The router documents `0` as "missing playlist or all-duplicate" and returns 200 with `added_count: 0`. It checks playlist existence first, so a database failure (locked beyond the 60 s busy timeout, an IntegrityError at commit, a vanished FK) is indistinguishable from the idempotent no-op. No error is raised and no broadcast is sent. `add_track`, `update`, `reorder_track` and `clear` were changed in #5264 to propagate DB errors, and `delete` / `remove_track` / `create` got result checks in #5940. `add_tracks` was left out.
- **Evidence**:
  ```python
  # playlist_membership_mixin.py
  239:        with self._guarded(f"Failed to batch-add tracks to playlist {playlist_id}") as session:
  ...
  277:        return 0            # reached after the guard swallowed any Exception
  # routers/playlists_tracks.py
  49:    added_count = await asyncio.to_thread(repos.playlists.add_tracks, playlist_id, request.track_ids)
  66:        "message": f"Added {added_count} track(s) to playlist",
  # useTrackContextMenu.ts:68-70
  await playlistService.addTracksToPlaylist(playlistId, [track.id]);
  success(`Added to "${playlistName}"`);        // return value (0) ignored
  ```
- **Impact**: Under SQLite contention during a scan, or after any IntegrityError, adding a track to a playlist from the context menu shows a success toast while nothing was written. The bulk path reads `addedCount === 0` as "Failed", but it cannot tell failure from "already present". Nothing is retried or surfaced.
- **Suggested Fix**: Make `add_tracks` follow #5264 (use `_session_scope` so a DB error propagates, return 0 only for missing playlist or all-duplicate). The route's `with_error_handling` then maps it to 503/500. Make the single-track context-menu handler check the returned count.

### D8-01: Thumbnail cache walks the whole cache directory twice on every cache miss (quadratic first-load cost)
- **Severity**: MEDIUM
- **Dimension**: Performance & Resource Management
- **Location**: `auralis-web/backend/routers/artwork_thumbnails.py:205-219`, `auralis-web/backend/core/thumbnail_cache.py:126-170` (`prune_thumbnail_cache`), `:242-275` (`reap_orphan_temp_files`)
- **Status**: NEW (siblings #4532, #5255, #4527 are CLOSED and only added the eviction/locking; none addresses its per-miss cost)
- **Description**: `_get_or_create_thumbnail()` runs two O(N) filesystem sweeps after/before *every* thumbnail render, where N is the number of files in the thumbnail directory: `reap_orphan_temp_files()` (a `glob` over the directory) and `prune_thumbnail_cache()` (`iterdir()` + `is_file()` + `stat()` for every entry, then a sort of all entries). The cap is 128 MiB, so at steady state the directory holds roughly 5k-20k thumbnails. Rendering a grid of covers for the first time (every album is a miss) therefore costs O(albums x cached files). The sibling on-disk chunk cache deliberately amortises exactly this with `PRUNE_EVERY_N_WRITES = 32` (`core/chunk_disk_prune.py`); the thumbnail cache has no throttle at all. All of it runs on a default-executor (I/O pool, 8 shared workers) thread while holding the per-key render lock.
- **Evidence**:
  ```python
  # routers/artwork_thumbnails.py:205-219
  if not dst.exists():
      thumb_dir.mkdir(parents=True, exist_ok=True)
      with _thumb_render_lock(key):
          if not dst.exists():
              reap_orphan_temp_files(thumb_dir)          # glob(".tmp-*") over the whole dir
              _render_thumbnail(src, dst, bucket, pil_fmt, ext, thumb_dir)
              prune_thumbnail_cache(thumb_dir, keep=dst) # iterdir + stat every file + sort
  # core/thumbnail_cache.py:147-155
  for entry in thumb_dir.iterdir():
      if entry.name.startswith(THUMB_TMP_PREFIX) or not entry.is_file():
          continue
      stat = entry.stat()
  ```
  Measured: rendering a 256 px thumbnail from a 1000 px JPEG = 11 ms; the two maintenance sweeps = 38 ms at 5,000 cached files and 93 ms at 10,000 files (warm page cache). Maintenance is 3-8x the actual work and grows linearly with cache size.
- **Impact**: Scrolling a large library's album/track grid for the first time makes each cover several times slower than necessary (and the delay grows as the cache fills), and ties up the shared 8-worker I/O pool that the REST repository calls also use. No failure, but visible artwork lag and DB-call queueing during grid scroll.
- **Suggested Fix**: Throttle the prune/reap the way `ChunkDiskPruneMixin` does (every N renders, non-blocking scan lock) or track the running total in memory and prune only when it crosses the cap; reap temp files at startup / on a timer rather than per miss.
- **Merged**: Also reported by: D10-05 (the same miss-path directory rescan, plus FIFO eviction and a delete-while-serving window; merged).

### D9-01: tests/integration/test_api_integration.py boots the full lifespan against the developer's real ~/.auralis/library.db (#5810 isolation only covers tests/backend)
- **Severity**: MEDIUM
- **Dimension**: Test Coverage (test hermeticity)
- **Location**: `tests/integration/test_api_integration.py:39-51` (fixture), isolation fixture at `tests/backend/conftest.py:210-231`
- **Status**: NEW (incomplete follow-through of closed #5810; same class as closed #3519)
- **Description**: #5810 made `tests/backend/conftest.py::client` depend on a session-scoped `_isolated_library_db` that monkeypatches
  `auralis.library.constants.DEFAULT_DB_PATH` / `database_engine.DEFAULT_DB_PATH`, and an autouse `_isolated_fingerprint_store`.
  Both fixtures live in `tests/backend/conftest.py`, so they apply only to `tests/backend/`. `tests/integration/` has no conftest of its
  own and `tests/conftest.py` has no equivalent, yet `tests/integration/test_api_integration.py` defines its own `client` that
  enters `with TestClient(app, ...) as client:` (runs the real lifespan -> `config/startup/components.py:36`
  `globals_dict['library_database'] = LibraryDatabase()` -> `DEFAULT_DB_PATH`). It then performs state-changing calls.
- **Evidence**:
  ```
  tests/integration/test_api_integration.py:50:    with TestClient(app, headers={"origin": "http://localhost:8765"}) as client:
  tests/integration/test_api_integration.py:325:    response = client.post("/api/player/enhancement/preset", json={"preset": "adaptive"})   # persists via repos.settings.update_settings (routers/enhancement_controls.py:35,120)
  tests/integration/test_api_integration.py:418:    response = client.post("/api/cache/clear")                                              # sweeps chunk dir + .25d store (cache_cleanup.py:97)
  tests/integration/test_api_integration.py:160:    response = client.post("/api/player/volume", json={"volume": 70})
  auralis-web/backend/config/startup/components.py:36:    globals_dict['library_database'] = LibraryDatabase()
  tests/backend/conftest.py:38-47   (_isolated_fingerprint_store is autouse in tests/backend only)
  ```
- **Impact**: Running `tests/integration/test_api_integration.py` (it is in the default `pytest` collection and not `slow`) migrates the
  developer's real library DB and writes a backup beside it, starts the real background workers/auto-scanner against whatever scan
  folders that DB holds, overwrites persisted enhancement settings, and Clear Cache sweeps the real fingerprint store. Assertions such
  as `status_code in [200, 404]` (lines 247, 308) also depend on whatever the ambient library contains - the exact non-hermeticity
  #5810 removed for tests/backend.
- **Suggested Fix**: Hoist `_isolated_library_db` and `_isolated_fingerprint_store` (autouse) into `tests/conftest.py` (or add a
  `tests/integration/conftest.py` that reuses them) so every test that boots `main.app` gets a throwaway DB.

### D10-01: Degraded DSP fallbacks are persisted into the durable chunk cache as if they were a mastered render
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation (poisoned / torn cache entries)
- **Location**: `auralis-web/backend/core/audio_processing_pipeline.py:124-132`, `auralis-web/backend/core/chunk_render.py:164-170`, `auralis-web/backend/core/chunk_render_miss.py:57-79`
- **Status**: NEW
- **Description**: `apply_enhancement` returns the *unprocessed input* when the processor returns `None` or non-finite output (`finite_or_fallback`), and `process_chunk_core` substitutes 100 ms of silence when trimming leaves nothing. None of these return a marker. `render_chunk` then writes the result with `encode_and_save_from_path` and records it with `_path_cache.store()` under the exact key a successful render uses. The `finite_or_fallback` docstring promises "one audible discontinuity instead of a silent, permanent poisoning", but the cache makes it permanent for the session: every replay, seek-back and later stream of that track/preset/intensity/targets hits `lookup_cached` and is served the unmastered (or 100 ms) chunk. The project already treats "failed after DSP state advanced" as non-persistable (`_invalidate_after_post_dsp_failure`, #5274), but a fallback that *returns normally* skips that guard. The pipeline's DSP output is state-dependent (a leased, warm HybridProcessor), so the same chunk would likely render fine on a fresh processor if it were retried.
- **Evidence**:
```python
# audio_processing_pipeline.py:124-132
if processed is None:
    logger.error("Processor returned None, using original audio")
    return audio
processed = finite_or_fallback(processed, audio, chunk_index)
if processed is audio:
    return audio
# chunk_render.py:165-170
if len(processed_chunk) == 0:
    logger.error(f"Chunk {chunk_index} is empty after context trimming. Returning silence.")
    processed_chunk = np.zeros((processor.sample_rate // 10, num_channels), dtype=audio_chunk.dtype)
# chunk_render_miss.py:68-79  (unconditional persist)
chunk_path = processor._wav_encoder.encode_and_save_from_path(audio=extracted_chunk, ...)
processor._path_cache.store(chunk_index, chunk_path)
```
- **Impact**: One transient NaN/None from the DSP leaves a chunk of unmastered audio (a level and tonal jump, partly softened by serve-time smoothing) or a 100 ms hole (sample-count violation) replayed on every visit until restart or manual Clear Cache. Rare trigger, but wrong audio served repeatedly and hard to attribute.
- **Suggested Fix**: Have the pipeline/`process_chunk_core` report that a fallback was used (flag or dedicated exception) and have `render_chunk` serve the fallback audio without `encode_and_save`/`store`, discarding the leased processor as for a post-DSP failure so the next request re-renders.

### D10-02: MasteringTargetService caches a stale Tier-1 DB fingerprint under the NEW file-signature key, and nothing invalidates it when the rescan deletes the row
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation (stale-after-edit, invalidation reach)
- **Location**: `auralis-web/backend/core/mastering_target_service.py:134-154`, `auralis-web/backend/core/fingerprint_loading.py:43-70`; engine side `auralis/library/repositories/track_repository_mutation.py:115-121`
- **Status**: NEW (sibling gap of closed #5489 / #3705, whose fixes are present)
- **Description**: The cache key is `fingerprint_{track_id}_{file_signature}`, but Tier 1 (`load_from_database(track_id)`) looks the row up by `track_id` only and is never checked against the file. If a file is replaced in place (re-rip, remaster at the same path) and played before the library rescan runs, the new signature misses the cache, Tier 1 returns the OLD recording's fingerprint, and that is stored under the NEW-signature key. The later rescan correctly deletes the stale row (#5719) and the queue writes a fresh one, but the backend is never told: nothing calls `clear_global_mastering_target_entry` on a rescan/audio-change/fingerprint-complete event (only the cache endpoints, library reset and shutdown do). The stale `(fingerprint, targets)` tuple then wins the `if cache_key in self.cache` check for the rest of the process (256-entry LRU), and `targets_hash` derives from it, so the chunk cache is also filled with chunks rendered against the old file's targets.
- **Evidence**:
```python
# mastering_target_service.py:134-154
cache_key = self._get_cache_key(track_id, filepath, file_signature)   # new signature
with self._lock:
    if cache_key in self.cache: ... return cached
fingerprint = self.load_fingerprint_from_database(track_id)           # by track_id only
if fingerprint is not None:
    targets = self.generate_targets_from_fingerprint(fingerprint)
    ...
        self._store_in_cache(cache_key, result)                       # old fingerprint, new key
```
`grep -rn clear_global_mastering_target_entry` -> only `core/cache_cleanup.py` (clear endpoints).
- **Impact**: A track whose audio was swapped is mastered against the previous recording's tonal/level targets for the whole session (until restart or Clear Cache). Window is "file replaced, played before rescan finishes", so uncommon, but undetectable by the user.
- **Suggested Fix**: Do not cache a Tier-1 result unless the DB row is provably for this signature (e.g. skip the cache store for Tier 1, or compare the row's file mtime/size), and call `clear_global_mastering_target_entry(track_id)` from the audit-change/rescan path (or on fingerprint completion).

### D11-01: Header-less VBR / joined MP3s are converted correctly but chunk geometry still uses ffprobe's (wrong) duration
- **Severity**: MEDIUM
- **Dimension**: Seek & Buffering (seek-target geometry / seekable source)
- **Location**: `auralis-web/backend/core/chunk_metadata.py:93-98` (duration/total_chunks from the probe), `auralis-web/backend/core/seekable_source.py:353-376` (`resolve()` converts lazily, never feeds the real length back), `auralis-web/backend/core/stream_seek.py:92-96`
- **Status**: NEW (residual of closed #6314: the reader was fixed, the duration that drives the geometry was not; no open issue covers it)
- **Description**: #6314's fix routes a file whose libsndfile length disagrees with ffprobe's through the one-time FFmpeg temp-WAV conversion, so the samples that are read are right. But `load_audio_metadata()` still takes `total_duration` (and therefore `total_chunks`, the `audio_stream_start.total_duration`, and the seek clamp in `chunk_for_position(..., total_duration=meta.duration)`) from ffprobe's container estimate. Those are exactly the files for which that estimate is untrustworthy (the #6314 evidence table shows -6% / +8%). After conversion nothing reconciles the two: `ChunkedAudioProcessor.total_duration` stays the probe value while the converted WAV holds the true length. The stream-start message is sent before the first chunk is read (and `resolve()` is lazy), so the correction cannot happen later either.
  - Probe OVER-estimates: tail chunks lie beyond the real EOF and are emitted as silence (non-last chunks are padded), and a seek into the last stretch lands on a chunk that holds no audio: `chunk_for_position` clamps to `probe_duration - 0.5`, the trim removes everything, and the stream "completes" with 0 samples (the #5254 failure mode, reached through a different door).
  - Probe UNDER-estimates: the real tail is never streamed (stream ends early with `reason="completed"`).
  I reproduced both on the current tree with `ffmpeg ... -c:a libmp3lame -q:a N -write_xing 0` files and `ChunkedAudioProcessor(preset=None)` (original-audio path, so no DSP involved; same geometry as enhanced).
- **Evidence**:
  ```
  chunk_metadata.py:95   total_duration = float(meta['duration_seconds'])      # ffprobe
  chunk_metadata.py:98   total_chunks = _bounded_chunk_count(total_duration, filepath)

  # over-estimate: 40.05 s of real audio, ffprobe says 73.94 s (can_seek_natively -> False, so it IS converted)
  dur 73.944788 chunks 7
  chunk 0 audible_s=14.96 | 1 9.98 | 2 9.98 | 3 5.02 (len 10.00) | 4 0.00 (len 10.00) | 5 0.00 (len 10.00) | 6 len 0
  total emitted 65.0 s for a 40.05 s file
  chunk_for_position(72.0, 7, total_duration=73.94) -> (6, 7.0, 72.0)   # chunk 6 emits 0 samples -> empty "completed" stream

  # under-estimate: 20.04 s real, ffprobe says 18.95 s
  probe dur 18.954594 chunks 2 emitted s 18.954603 converted wav s 20.035918   # last 1.08 s never streamed
  ```
- **Impact**: For header-less VBR (older encoders, cut files) and similar files, enhanced playback shows and plays a wrong length: seconds of trailing silence (or a dropped tail), the progress bar and seek range disagree with the audio, and a seek into the final region delivers nothing yet reports completion. `stream_normal` of the same file is correct (it takes `total_frames` from the converted WAV), so the two modes disagree again, which is the symptom #6314 set out to remove. Rare in practice (the library audit found none), silent when it occurs.
- **Suggested Fix**: When `can_seek_natively()` is False, resolve the conversion at processor construction (it is needed for the first chunk anyway, and the constructor already runs off the loop) and set `total_duration` / `total_chunks` from the converted WAV's `sf.info` frames / sample rate before the stream-start message. Add a regression test with a `-write_xing 0` VBR MP3 asserting `sum(len(chunk))` equals the decoded length.

### MEDIUM (Existing open issues, not to be re-filed)

### D8-06: Existing — whole queue is serialised and broadcast on the loop for every player-state mutation
- **Severity**: MEDIUM
- **Dimension**: Performance & Resource Management
- **Location**: `auralis-web/backend/core/state_manager.py:203-206` (`_broadcast_state`), `auralis-web/backend/player_state.py:86` (`queue: list[TrackInfo]`)
- **Status**: Existing: #5960 (OPEN)
- **Description**: Still present after the shallow-copy partial fix: `_broadcast_state` does `state.model_dump()` (whole queue) and `ConnectionManager.broadcast()` then `json.dumps()` of it, synchronously, for play/pause/volume/set_track/etc. Measured at 20,000 tracks: ~11 ms model_dump + ~13 ms json.dumps and a 3.4 MB frame per broadcast on the event loop (volume-slider drags multiply this). Not re-filed.

### D11-04: StreamlinedCacheWorker (the only server-side look-ahead / buffering worker) never runs: `update_position` has no production caller
- **Severity**: MEDIUM
- **Dimension**: Seek & Buffering (buffering)
- **Location**: `auralis-web/backend/cache/playback_mixin.py:94`, `auralis-web/backend/core/streamlined_tiers.py:46-48`
- **Status**: Existing: #5959 (still present: `grep -rn update_position` finds only the definition; `current_track_id` is only ever set in `cache/manager.py:103` as `None`, so `get_playback_snapshot()` returns None and every tick returns "No track playing")
- **Description / Impact**: Listed for completeness; Tier-1 next-chunk and Tier-2 full-track pre-render never execute, so seek/play latency relies solely on the per-stream look-ahead and the 3-chunk proactive buffer. Not re-reported in detail.
- **Suggested Fix**: See #5959.
- **Merged**: Also reported by: D8-07, D10-07 (same open issue #5959; merged).

### LOW (NEW and regressions)

### D1-02: `enqueue-all` still ignores outdated-version fingerprints, so "Analyse remaining" is a no-op for them
- **Severity**: LOW
- **Dimension**: Route Handler Correctness (response/behavior consistency)
- **Location**: `auralis-web/backend/routers/fingerprint_queue.py:142-163`
- **Status**: Regression of #5891 (closed; the fix commit 5f5c20b2c changed the status and stats routes but states "the enqueue-all route still reads them", and the issue's evidence named this exact block)
- **Description**: #5891 redefined "pending" for the status route as `total - current`, so outdated (older-algorithm) rows are pending. `GET /api/library/fingerprints/status` reports them pending, and the frontend's "Analyse remaining" button (`useFingerprintCoverage.ts:107-135`, shown while `pendingTracks > 0`) posts to `enqueue-all`. That handler still uses the repository's `pending = total - (current + outdated)` and `get_missing_fingerprints()`, an outer join that returns only tracks with no row at all. With only outdated rows pending it answers "All tracks already have fingerprints!" with `enqueued: 0`; with a mix it enqueues only the never-fingerprinted ones. The per-track route `enqueue_fingerprint` uses `fingerprints.exists()` (current-version only), so the two enqueue routes disagree about what "has a fingerprint" means.
- **Evidence**:
  ```python
  # fingerprint_queue.py:144-155
  total_tracks = stats['total']
  already_fingerprinted = stats['fingerprinted']   # current + outdated
  pending = stats['pending']                        # total - (current + outdated)
  if pending == 0:
      return {"enqueued": 0, ..., "message": "All tracks already have fingerprints!"}
  ...
  missing_tracks = await asyncio.to_thread(repos.fingerprints.get_missing_fingerprints, limit=limit)
  ```
  `fingerprint_status.py:68-69` uses `stats.get('current', ...)` and `max(0, total - fingerprinted)` for the same data.
- **Impact**: After a `FINGERPRINT_ALGORITHM_VERSION` bump the UI shows N pending and a button that does nothing and says everything is fingerprinted. Mitigation: the background worker loop eventually re-fingerprints outdated rows on its own (`auralis/services/fingerprint_queue.py:259-266`), so this is a misleading manual lever rather than lost work.
- **Suggested Fix**: Compute `pending` here as `total - current` (as the status route does) and have the batch enqueue select tracks lacking a *current* fingerprint (e.g. the same `_current_fingerprint_clause()` that `exists()` uses), then drop the repository's two diverging counters or document one meaning.

### D1-03: The upload disk quota added by #6167 has no way to be released, and its error text points at an action that frees nothing
- **Severity**: LOW
- **Dimension**: Route Handler Correctness
- **Location**: `auralis-web/backend/routers/files_upload.py:161-163, 203-209`; `auralis-web/backend/routers/files_upload_budget.py:67-71`; `auralis-web/backend/config/limits.py:29-34`
- **Status**: NEW (incomplete follow-through of closed #6167, fixed today in a65783dd8; not a regression of its acceptance criteria)
- **Description**: `UploadBudget.admit_storage()` sums every regular file in `~/.auralis/uploads` and refuses a file once the total passes `MAX_UPLOAD_DIR_BYTES` (20 GiB), replying "Upload storage is full (20 GiB); remove tracks to free space". Nothing in the backend or library ever deletes a file in that directory: a grep for `uploads` finds only this route and a docstring in `data_dir.py`; `track_deletion.py`, `track_missing_files.py`, `remove_tracks_under_folder` and `reset_library` delete rows only, and there is no delete-track route. So the advice cannot be followed through the app, and a library reset (which removes the rows) leaves the files and the quota consumed.
- **Evidence**:
  ```python
  # files_upload.py:208
  "message": f"Upload storage is full ({MAX_UPLOAD_DIR_BYTES // 2**30} GiB); remove tracks to free space",
  # files_upload_budget.py:70-71
  self._stored_bytes = await asyncio.to_thread(_directory_bytes, self._directory)
  return self._stored_bytes + size <= self._directory_limit
  ```
  `grep -rn "uploads" auralis auralis-web/backend --include='*.py'` -> only `files_upload.py` (writer), `config/limits.py` (comment), `data_dir.py` (docstring).
- **Impact**: Once cumulative uploads reach 20 GiB, `POST /api/files/upload` rejects every file permanently, and orphaned upload files from reset/pruned libraries stay on disk. Practical reach is small (the route has no frontend consumer, per #6167's own notes), hence LOW.
- **Suggested Fix**: Unlink a track's file when its row is removed and its path is under the uploads directory (reset, prune, delete), or make the message honest ("delete files in the uploads folder").

### D1-04: `GET /api/playlists/{id}` is the one unbounded read, and serializes the whole track list on the event loop
- **Severity**: LOW
- **Dimension**: Route Handler Correctness (validation / bounds, event-loop work)
- **Location**: `auralis-web/backend/routers/playlists_crud.py:55-80`
- **Status**: NEW (sibling of closed #4554, which paginated only the list route, and of #6084)
- **Description**: Every other collection route is `limit`-bounded (`limit_query()` max 200). `get_playlist` returns every track of the playlist. The handler runs `[track.to_dict() for track in playlist.tracks]` on the event loop, then FastAPI validates the list against `PlaylistDetailResponse` (`list[TrackResponse]`) and JSON-encodes it, also on the loop. Playlists may hold up to `MAX_TRACK_ID_LIST` = 50,000 tracks (`schemas/request_bounds.py`; create and add-tracks accept that many).
- **Evidence**:
  ```python
  # playlists_crud.py:72-80
  playlist = await asyncio.to_thread(repos.playlists.get_by_id, playlist_id)
  ...
  playlist_dict = serialize_playlist(playlist)
  playlist_dict['tracks'] = [track.to_dict() for track in playlist.tracks]
  return playlist_dict
  ```
  Measured with synthetic `Track` rows (this repo's `Track.to_dict`, `TrackResponse`, `jsonable_encoder`): 20,000 tracks = 0.28 s `to_dict` + 0.08 s model validation + 0.47 s encode, about 0.85 s and 9 MB, all single-threaded on the loop; scales linearly (about 2 s at 50k).
- **Impact**: Opening a very large playlist stalls the event loop for 1 s or more (WebSocket audio chunk sends, heartbeats, other requests) and ships a multi-MB body. Normal playlists are unaffected.
- **Suggested Fix**: Add `limit`/`offset` (via `limit_query`/`offset_query`/`paginated`) to the tracks part of the detail response, or at minimum serialize in `asyncio.to_thread`.

### D1-05: Residual hand-rolled / no-op `try/except HTTPException: raise` boilerplate and undecorated handlers (siblings of #6210)
- **Severity**: LOW
- **Dimension**: Route Handler Correctness (error handling convention, DRY)
- **Location**: `routers/processing_parameters.py:107-194` (hand-rolled, undecorated); `routers/cache_streamlined.py:121-136`; `routers/enhancement_recommendation.py:86-109`; `routers/metadata_tracks.py:66,118,227`; `routers/processing_jobs.py:168-180` (undecorated)
- **Status**: NEW (the closed #6210 / #4605 converted only `tracks.py` and `fingerprint_status.py`)
- **Description**: `_audit` convention: error plumbing belongs to `@with_error_handling(...)`, and a fresh hand-rolled copy is a DRY regression. Remaining copies:
  - `get_processing_parameters` has no decorator and re-implements the pattern: `except HTTPException: raise` then `except Exception: logger.exception(...); raise HTTPException(500, ...)`. It bypasses `handle_query_error`'s mapping (OperationalError -> 503, missing file -> 404/403).
  - `get_track_cache_status` (decorated) wraps its body in `try: ... except HTTPException: raise`, a pure no-op.
  - `get_mastering_recommendation` (decorated) has the same no-op `try/.../except HTTPException: raise` around the analysis block.
  - `metadata_tracks.py` handlers (decorated) each carry an extra `except HTTPException: raise` that is redundant, since the neighbouring arms (`FileNotFoundError`, `UnreadableAudioFileError`, `ValueError`) cannot catch an `HTTPException`.
  - `cleanup_old_jobs` (`DELETE /api/processing/jobs/cleanup`) is the one `/api/processing` job handler with no `@with_error_handling`, so an engine failure escapes to the generic 500 middleware with no operation context.
- **Evidence**:
  ```python
  # processing_parameters.py:182-194
  except HTTPException:
      raise
  except Exception:
      logger.exception("Failed to get processing parameters")
      raise HTTPException(status_code=500, detail="Failed to get processing parameters")
  # cache_streamlined.py:121-136 (inside @with_error_handling("get track cache status"))
  try:
      status = cache_manager.get_track_cache_status(track_id)
      ...
  except HTTPException:
      raise
  ```
- **Impact**: No functional break today; inconsistent status mapping on one route and dead code that invites further drift.
- **Suggested Fix**: Decorate `get_processing_parameters` and `cleanup_old_jobs` with `@with_error_handling(...)` and delete the inner try blocks whose only handler re-raises.

### D1-06: `get_track_fingerprint` re-implements `enqueue_for_fingerprinting()` inline
- **Severity**: LOW
- **Dimension**: Route Handler Correctness (DRY: "improve existing code rather than duplicate logic")
- **Location**: `auralis-web/backend/routers/fingerprint_status.py:115-144` (vs. `routers/similarity_common.py:124-152`)
- **Status**: NEW
- **Description**: `similarity_common.enqueue_for_fingerprinting(track_id)` is the shared, best-effort "queue this track so a missing-fingerprint 404 self-heals" helper (offloaded to a thread, swallows failures, returns whether the queue accepted it; #4630/#5267/#5518). `get_track_fingerprint` carries its own copy of the same logic (import `get_fingerprint_queue`, `asyncio.to_thread(queue.enqueue, ...)`, swallow `Exception`, compute a "Queued" / "Not queued" detail) with differently worded messages, so the two 404 texts the frontend classifies can drift. The same handler also logs five INFO lines per request including the track title and artists (`:101-114`), which is noise for a route polled by the album character pane.
- **Evidence**:
  ```python
  # fingerprint_status.py:116-137
  queued = False
  try:
      from analysis.fingerprint_queue import get_fingerprint_queue
      queue = get_fingerprint_queue()
      if queue:
          queued = await asyncio.to_thread(queue.enqueue, track_id)
          ...
  except Exception as q_err:
      logger.debug(f"Could not enqueue track {track_id}: {q_err}")
  ```
- **Impact**: Maintenance risk and message drift only.
- **Suggested Fix**: Call `enqueue_for_fingerprinting(track_id)` from `similarity_common` (or hoist it to a neutral module) and build the 404 detail from its return value.

### D2-01: Fingerprint readiness check runs after whole-track extraction, so the client is told "queued / standard mastering" for a stream that is already fingerprint-mastered
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_enhanced.py:85-88`, `auralis-web/backend/core/stream_fingerprint.py:94-110`, `auralis-web/backend/core/chunk_processor_init.py:158-159`, `auralis-web/backend/core/fingerprint_loading.py:245`
- **Status**: NEW (adjacent closed work: #5919 fixed "queued when nothing queued"; #6336/#6338 introduced extract-at-construction)
- **Description**: Since the whole-track change, `ChunkedAudioProcessor.__init__` runs `load_fingerprint(extract_if_missing=True, save_extracted=True)` (Tier 3) before the first chunk, and `run_enhanced_stream` builds the processor before the body runs. Tier 3 persists only a `.25d` sidecar (`FingerprintStorage.save`), never a DB row. `stream_enhanced`'s body then calls `_check_or_queue_fingerprint`, which tests only `fingerprint_repo.exists(track_id)` (DB). For any track with a sidecar but no DB row (just extracted, or sidecar-only) it returns False, enqueues a redundant background job, and sends `fingerprint_progress` `status="queued"` with the message "Audio analysis queued, using standard mastering" — while the stream is in fact mastering against the whole-track fingerprint plan. The log line "Streaming with standard adaptive mastering (fingerprint queued...)" is wrong in the same way. The seek path does not call the check at all, so the same track reports differently on play vs seek.
- **Evidence**:
  ```python
  # stream_enhanced_lifecycle.py:111  processor (and Tier-3 extraction) already done
  stream.processor = await asyncio.wait_for(asyncio.to_thread(controller.chunked_processor_class, ...), timeout=...)
  # stream_enhanced.py:85-88  runs afterwards, DB-only check
  if await controller._check_or_queue_fingerprint(track_id=track_id, websocket=websocket):
      ...
  else:
      logger.info("📊 Streaming with standard adaptive mastering (fingerprint queued for background generation)")
  # chunk_processor_init.py:158  extraction up front, sidecar only
  extract_if_missing=True, save_extracted=True,
  # fingerprint_loading.py:245
  FingerprintStorage.save(Path(filepath), fingerprint_data, mastering_targets)
  ```
- **Impact**: The UI (`useFingerprintStatus`) shows "queued, using standard mastering" for audio that is fully fingerprint-mastered; operators reading logs are misled; one redundant enqueue per play (cheap, the extractor reuses the sidecar).
- **Suggested Fix**: Ask the processor what it actually used (it holds `fingerprint` / `mastering_targets`) and report that, or drop the DB-only check and enqueue only to persist the DB row without claiming "standard mastering".
- **Merged**: Also reported by: D4-04 (same stale readiness message after construction-time extraction; merged).

### D2-02: `teardown_connection` still swallows the caller's own cancellation (site missed by #6092)
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/ws_handlers/connection.py:233-237` and `:252-255`
- **Status**: NEW (sibling of CLOSED #6092 / #5083; `core/task_cancellation.await_cancelled_task` exists but this teardown never adopted it)
- **Description**: Both awaits of a task the teardown just cancelled use the bare `except CancelledError: pass` shape that #6092 removed from the position ticker, JobWorker, cache worker and auto-scanner. The stream await is even broader, `except (asyncio.CancelledError, Exception): pass`. A cancellation aimed at the endpoint task itself (second shutdown cancel while it is parked here) is indistinguishable and is dropped. `playback_commands._cancel_prior_task` and `handle_stop` in the same package already use `await_cancelled_task`, so the connection path is the lone outlier.
- **Evidence**:
  ```python
  heartbeat_task.cancel()
  try:
      await heartbeat_task
  except asyncio.CancelledError:
      pass
  ...
  live = signal_cancel(task, cancel_event)
  if live is not None:
      try:
          await live
      except (asyncio.CancelledError, Exception):
          pass
  ```
- **Impact**: A cancelled WS handler continues running the rest of teardown instead of unwinding, and returns normally to the server; mostly cosmetic during shutdown but it is the exact class #6092 closed, and the unbounded `await live` is not interruptible by the second cancel.
- **Suggested Fix**: Replace both blocks with `await await_cancelled_task(task, logger)` (re-raises when `caller_is_being_cancelled()`), keeping the later cleanup steps in a `finally`.

### D2-03: Write-only stream state: `active_track_ids` and `WSDeps.broadcast_manager`, with comments describing behavior that no longer exists
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `ws_handlers/context.py:41,76-78`; `ws_handlers/playback_commands.py:183,224`; `ws_handlers/seek_command.py:143`; `ws_handlers/stream_cancel.py:38`; `routers/system.py:87,99-101`; `routers/system_streams.py:23-25,126-128,151-153,208-210` (all under `auralis-web/backend/`)
- **Status**: NEW
- **Description**: `StreamState.active_track_ids` (and the module-level `_active_streaming_track_ids`) is assigned in three handlers and popped in `detach_stream` and the three stream `finally` blocks, but nothing reads it: the "dedup by track_id" it was kept for was removed by #4726 ("every command is authoritative"). `WSDeps.broadcast_manager` is populated in `routers/system.py` with the comment "the play handlers broadcast mastering_recommendation", but no handler reads it (`grep broadcast_manager` finds only the field and the assignment); the recommendation broadcast now lives in `RecommendationService`. Every new teardown site (#6292) has to keep maintaining the dead registry.
- **Evidence**:
  ```python
  # context.py:41 / :78
  active_track_ids: dict[str, int]
  broadcast_manager: Any = None
  # system.py:99-101
  # #4542: the play handlers broadcast mastering_recommendation, which
  # goes to every client rather than just this socket.
  broadcast_manager=deps.manager,
  # playback_commands.py:183 (comment: "so subsequent play_enhanced dedup checks see the truth")
  state.active_track_ids[ws_id] = track_id
  ```
- **Impact**: Maintenance debt and misleading comments (a reader assumes dedup or a broadcast happens); no runtime defect.
- **Suggested Fix**: Delete `active_track_ids` from `StreamState`, the module dict, the three writes and the pops; delete `WSDeps.broadcast_manager` and its comment; update the tests that construct `StreamState(active_track_ids=...)`.

### D2-04: A rejected `play_enhanced` (enhancement disabled, no `force`) still overwrites the shared enhancement settings
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:105-110` vs `:128-141`
- **Status**: NEW
- **Description**: `handle_play_enhanced` writes the accepted preset/intensity into the process-wide `enhancement_settings` dict (`settings["preset"] = ...; settings["intensity"] = ...`, #4601) before it evaluates the `if not enhancement_enabled and not force` gate that rejects the command with `ENHANCEMENT_DISABLED`. A command the server refuses therefore still mutates state that REST `GET /api/processing/parameters` / enhancement-settings reads and that later `play_enhanced`/`seek` frames use as fallback, with no persistence or `enhancement_settings_changed` broadcast. Other connections' fallbacks change silently.
- **Evidence**:
  ```python
  settings["preset"] = preset          # :109  mutated in place, shared by reference
  settings["intensity"] = intensity    # :110
  ...
  if not enhancement_enabled and not force:   # :128  command rejected afterwards
      ... "code": "ENHANCEMENT_DISABLED" ...
      return
  ```
- **Impact**: Rejected command has a side effect (an A/B toggle with enhancement off can still move the stored intensity); minor because the frontend sends its own current slider value on each play.
- **Suggested Fix**: Move the write-back below the enabled/force gate (right before `_cancel_prior_task`), so only accepted commands mutate shared state.

### D3-02: `get_wav_chunk_path` is a second render+persist pipeline with no production caller, and it is the only writer of the content profile `/api/processing/parameters` reads
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_streaming.py:148-233`; `auralis-web/backend/core/chunk_content_profile.py`; `auralis-web/backend/routers/processing_parameters.py:116-136`; `auralis-web/backend/core/chunked_processor.py:170,233-235,276-278`
- **Status**: NEW (adjacent closed issues: #4895 two encode+persist pipelines, #6086 lock fix on this function, #4341/#4601 content-profile; none notes that the function is unreachable)
- **Description**: `get_wav_chunk_path()` is documented as "the PRIMARY output method for the unified architecture", but every production path (stream pump, proactive buffer, streamlined worker, recommendation analysis) goes through `process_chunk` / `process_chunk_safe` -> `render_chunk`. `grep` finds callers of `get_wav_chunk_path` only under `tests/` (7 test files). It is a divergent copy of the miss path (no single-flight claim, its own `_sync_cache_lock`, `encode_and_save` to a pre-computed path, own cancel/invalidate handling) that the project's own "deleted as unreachable" policy (#5088, #5492, #5495) would remove. Side effect: the ONLY call to `store_content_profile(...)` lives inside it (lines 227-231; `render_chunk` never stores), so the global that `GET /api/processing/parameters` reads ("populated by ChunkedAudioProcessor during streaming playback") is never filled by live playback.
- **Evidence**:
  ```python
  # chunk_streaming.py:152
  This is the PRIMARY output method for the unified architecture.
  # chunk_streaming.py:227-230  (the only store_content_profile call in the backend)
  if processor.processor is not None:
      processor_profile = getattr(processor.processor, 'last_content_profile', None)
      if processor_profile and processor.preset is not None:
          store_content_profile(processor.preset, processor_profile)
  # routers/processing_parameters.py:116,136
  Reads from the global content profile cache populated by ChunkedAudioProcessor
  profile = get_last_content_profile(preset)   # -> None in production -> returns _DEFAULT_PARAMETERS
  ```
- **Impact**: In a real session `/api/processing/parameters` always returns its `is_default: True` payload, regardless of what the engine is doing (no frontend caller today, so API-only). The dead pipeline is a divergence risk (a fix applied to `render_chunk`, e.g. #5258 single-flight, never reaches it) and keeps `_sync_cache_lock`, `_get_wav_chunk_path`, `get_wav_chunk_path` as untested-in-prod surface.
- **Suggested Fix**: Delete `get_wav_chunk_path` (and `_sync_cache_lock` / `_get_wav_chunk_path`), and move the `store_content_profile` call into `render_chunk` (after a successful render) so the visualizer endpoint is fed by the live path; or drop the endpoint's "real data" claim.
- **Merged**: Also reported by: D10-03 (same function, same file:line; merged).

### D3-04: Stale "crossfade" / "15 s chunk" wording survives in the chunk path after #4642
- **Severity**: LOW
- **Dimension**: Chunked Processing (comment accuracy)
- **Location**: `core/chunk_boundaries.py:22`; `core/chunk_file_loading.py:48`; `core/chunked_processor.py:203`; `core/stream_enhanced.py:9`; `core/audio_stream_controller.py:155`; `core/proactive_buffer.py:4,25`
- **Status**: NEW (#5053/#6245 fixed only the `chunked_processor.py` module docstring and the architecture docs)
- **Description**: The emitted path has no boundary crossfade and each non-first chunk emits 10 s, but several comments still describe the retired model, which is exactly what the CLAUDE.md/audit "no crossfade at seams" rule warns future editors about.
- **Evidence**:
  ```python
  # chunk_boundaries.py:22   OVERLAP_DURATION = 5.0  # seconds - overlap for natural crossfades
  # chunk_file_loading.py:48 Chunks after the first include OVERLAP_DURATION at the start for crossfading.
  # chunked_processor.py:203 """Get chunk duration in seconds for crossfade calculations"""
  # stream_enhanced.py:9     chunk-boundary crossfading, and per-chunk error recovery.
  # audio_stream_controller.py:155  crossfading at boundaries, caching for performance, and error recovery.
  # proactive_buffer.py:25   PRELOAD_CHUNKS = 3  # Buffer first 45 seconds (3 x 15s chunks)   (emitted: 15+10+10 = 35 s)
  ```
- **Impact**: Misleads maintainers into re-adding a crossfade or mis-sizing the pre-buffer (3 chunks buffer 35 s, not 45 s). No runtime effect.
- **Suggested Fix**: Reword to "overlap used as render context / chunk-count geometry; emitted segments tile exactly", and fix the 45 s figure.

### D4-02: Cancelling a queued job does not free its slot in the bounded job queue
- **Severity**: LOW
- **Dimension**: Processing Engine (state management / backpressure)
- **Location**: `auralis-web/backend/core/job_lifecycle.py:215-250`; `auralis-web/backend/core/processing_engine.py:155-169,282-298`; `auralis-web/backend/core/job_worker.py:237-261`
- **Status**: NEW
- **Description**: `cancel_job` on a QUEUED job only sets `status = CANCELLED` and calls `cancel_task()`, which finds nothing because queued jobs have no task yet. The job object stays inside the `asyncio.Queue` (`maxsize=max_queue_size=20`). Since #5949 the dispatcher takes a concurrency slot before it dequeues, so a cancelled entry is only removed once one of the two running jobs finishes (up to `DEFAULT_PROCESSING_TIMEOUT`=300 s each). Until then `put_nowait` keeps raising `QueueFull`.
- **Evidence**:
  ```python
  # job_lifecycle.py:230-246
  job.status = ProcessingStatus.CANCELLED
  job.completed_at = datetime.now()
  ...
  engine._worker.cancel_task(job_id)     # no task for a queued job: no-op
  ```
  ```python
  # processing_engine.py:163 / 297
  self.job_queue.put_nowait(job)         # QueueFull while cancelled entries still occupy the queue
  "queue_full": self.job_queue.full(),   # while "queued" (counted by status) already reads 0
  ```
- **Impact**: A client that fills the queue, cancels everything and resubmits receives 503 "Processing queue is full" while `/queue/status` reports `queued: 0`. Bounded and self-healing once a running job ends, hence LOW.
- **Suggested Fix**: Skip cancelled entries when judging capacity (count non-cancelled jobs, or drain cancelled heads in `submit_job` before `put_nowait`), or track queued-job count separately from the raw `Queue`.

### D4-03: Expired-job temp files are swept only as a side effect of another job finishing
- **Severity**: LOW
- **Dimension**: Processing Engine (resource cleanup)
- **Location**: `auralis-web/backend/core/job_worker.py:122-127,219-222`; `auralis-web/backend/core/processing_engine.py:265-276`; `auralis-web/backend/config/startup/workers.py:126-134`
- **Status**: NEW
- **Description**: `completed_job_ttl_hours` is 1 h, but `cleanup_old_jobs` is called only from `_run_job`'s `finally` (after some job ends), once in `stop()`, and from the explicit `DELETE /api/processing/jobs/cleanup`. There is no periodic task. The sweep that runs when job N finishes can only expire jobs older than 1 h, so the output file (and, for `upload-and-process`, the uploaded input of up to `MAX_UPLOAD_BYTES`) of the last completed job in a session persists until the next job runs more than an hour later or the app restarts (startup `reclaim_stale_temp_entries`).
- **Evidence**: `grep` of non-test callers of `cleanup_old_jobs` returns only `job_worker.py:124`, `job_worker.py:220`, and the DELETE route.
- **Impact**: Temp disk (full-track WAV/FLAC output plus the uploaded source) is held much longer than the documented 1 h TTL on an idle backend. Desktop single-user, so LOW.
- **Suggested Fix**: Run the sweep from a lightweight periodic task owned by the worker (or schedule one at `completed_at + ttl` when a job reaches a terminal status).

### D5-02: WS play/seek `track_id` guard has no int64 upper bound and accepts booleans, unlike the shared `TrackId` type
- **Severity**: LOW
- **Dimension**: Schema Consistency (schema reuse / type accuracy)
- **Location**: `auralis-web/backend/ws_handlers/enhancement_params.py:114`, `auralis-web/backend/ws_handlers/seek_command.py:37`, vs `auralis-web/backend/schemas/request_bounds.py:40`
- **Status**: Regression of #6162 (closed; its WS half was explicitly left unchanged by commit 607d8075f, "The WS play_* track_id guard is unchanged")
- **Description**: #6162 bounded REST ids with `TrackId = Annotated[int, Field(ge=1, le=MAX_SQLITE_INT)]` and the module's stated purpose is that every body type inherits the bound. The WebSocket inbound handlers hand-roll `isinstance(track_id, int) and track_id > 0` instead, so values above 2^63-1 pass validation and reach SQLite. `isinstance(True, int)` is also true, so `track_id: true` is accepted as track 1 (the sibling `is_valid_intensity` rejects bool explicitly).
- **Evidence**:
  ```python
  # enhancement_params.py:114
  if not isinstance(track_id, int) or track_id <= 0:
  # seek_command.py:37
  if not isinstance(track_id, int) or track_id <= 0:
  ```
  `LibraryDatabase.tracks.get_by_id(10**30)` raises `OverflowError: Python int too large to convert to SQLite INTEGER` (reproduced). In `core/stream_track_resolution.py` the blanket `except Exception` logs it with `exc_info=True` and sends the generic "Failed to load track" frame instead of `invalid_track_id`.
- **Impact**: A client frame with a huge id produces an ERROR traceback per frame and a misleading error code; the REST surface answers the same input with 422/404 and a WARNING.
- **Suggested Fix**: Validate WS ids through one shared helper built on `TrackId` (e.g. `TypeAdapter(TrackId)` or an `is_valid_track_id()` beside `is_valid_intensity`) that also rejects `bool`; use it in `parse_play_request` and `handle_seek`.

### D5-03: Seek and preset rejections omit `command`, so the client cannot clear its optimistic "seeking" state
- **Severity**: LOW
- **Dimension**: Schema Consistency (error envelope)
- **Location**: `auralis-web/backend/ws_handlers/seek_command.py:39,44`, `auralis-web/backend/ws_handlers/playback_commands.py:117`
- **Status**: NEW (related to closed #5885 / #5973, which added `command` to the other rejections but not these)
- **Description**: `WebSocketErrorResponse.command` exists so a client can roll back the optimistic state it set before sending (#5885). The play-command rejections pass `command=...`, as do the rate-limit and internal-error replies. The seek handler's own `invalid_track_id` and `invalid_seek_position` replies, and play_enhanced's `invalid_preset`, do not. The frontend only reacts to errors whose `command === 'seek'`.
- **Evidence**:
  ```python
  # seek_command.py:39, 44
  await send_error_response(websocket, "invalid_track_id", "track_id must be a positive integer")
  await send_error_response(websocket, "invalid_seek_position", "position must be a non-negative number")
  # playback_commands.py:117
  await send_error_response(websocket, "invalid_preset", f"Invalid preset. Must be one of: ...")
  ```
  ```ts
  // useEnhancedSeek.ts:141
  if (message.command !== 'seek' || rejected === null) return;
  ```
- **Impact**: A rejected seek (e.g. non-finite or negative computed position) leaves `pendingSeekRef` set and `isSeeking` true until some other event resets it: the same stuck progress bar #5885 fixed for the rate-limited case. Trigger is rare (needs a bad client value), hence LOW.
- **Suggested Fix**: Pass `command="seek"` / `command="play_enhanced"` at these three sites (a `command=` default derived from the dispatched type would remove the whole class).

### D5-04: `/explain` emits DB-column dimension names and normalized centroid/rolloff, while the fingerprint endpoints emit API names and Hz
- **Severity**: LOW
- **Dimension**: Schema Consistency (naming, units)
- **Location**: `auralis/analysis/fingerprint/similarity_explanation.py:70-84` (payload), `auralis-web/backend/routers/similarity_models.py:36-46` (`DimensionContribution`), vs `auralis-web/backend/routers/fingerprint_status.py:150-176` and `routers/albums_fingerprint.py:22-52`
- **Status**: NEW
- **Description**: `FingerprintVectorResponse` is the documented API vocabulary for the 25 dimensions (`sub_bass`, `pitch_confidence`, `chroma_energy_mean`, `stereo_correlation`; centroid/rolloff in Hz, #2477/#5470). `GET /api/similarity/tracks/{a}/explain/{b}` builds `dimension` from `schema.DIMENSION_NAMES` (DB-column names) and `value1/value2/difference` from `fp.to_vector()` (raw DB values).
- **Evidence**:
  ```
  DIMENSION_NAMES = ('sub_bass_pct', 'bass_pct', ..., 'pitch_stability', 'chroma_energy', ..., 'phase_correlation')
  raw1 = fp1.to_vector()            # spectral_centroid stored normalized 0-1 (schema.py:76, Unit.NORMALIZED)
  'value1': float(raw1[idx]) ...    # no centroid_to_hz / rolloff_to_hz
  # fingerprint_status.py:173
  "spectral_centroid": centroid_to_hz(fp.spectral_centroid),
  ```
- **Impact**: One concept, two vocabularies and two units on sibling endpoints; a client that joins explain contributions to a track's fingerprint by key (`pitch_confidence` vs `pitch_stability`) or compares `spectral_centroid` values gets mismatches (0.4 vs 3200 Hz for the same quantity). No in-app consumer today (the discovery UI was deleted), so LOW.
- **Suggested Fix**: Map names with the existing `_DB_TO_API` table and convert centroid/rolloff with the same helpers in one shared projection used by all three endpoints, or document the explain payload as engine-side vocabulary in `DimensionContribution`.

### D5-05: The same track is described with three different artist/album representations
- **Severity**: LOW
- **Dimension**: Schema Consistency (nested schemas / reuse)
- **Location**: `auralis-web/backend/player_state.py:38-51,127-135` (`TrackInfo`), `auralis/library/models/track.py:143-169` (`TrackResponse`), `auralis-web/backend/routers/fingerprint_status.py:55-58,150-151`
- **Status**: NEW (#5905 closed the library-endpoint sentinels only; #5985 closed a TS/TypedDict null mismatch only)
- **Description**: Library responses (`TrackResponse`) carry `artists: list[str]` and `album: str | None` (null when absent, per #5905). Queue/player/WS (`TrackInfo`/`TrackPayload`) carry `artist: str` = only the first artist (`track.artists[0].name`) and `album: str` with the sentinels `"Unknown Artist"` / `"Unknown Album"`. The per-track fingerprint response carries `artist: str` = all artists joined with `", "` and the same sentinels. `TrackInfo.album` also cannot represent "no album" the way every other track-shaped model does.
- **Evidence**:
  ```python
  # player_state.py:127-129,134
  artist_name = "Unknown Artist"
  if hasattr(track, 'artists') and track.artists: artist_name = track.artists[0].name
  album_name = "Unknown Album"
  # fingerprint_status.py:150
  "artist": ", ".join(a.name for a in track.artists) if track.artists else "Unknown Artist",
  ```
- **Impact**: A multi-artist track shows "A, B" in one view and "A" in the queue/player bar; a track with no tags is `[]`/`null` in the library and a literal "Unknown Artist" string in the queue, so UI code cannot treat "absent" uniformly (e.g. hide the row, localise the label).
- **Suggested Fix**: Emit one shape: keep `artists: list[str]` + nullable `album` in `TrackInfo`/`TrackPayload` (or derive one display string in a single helper used by all three), and leave the "Unknown ..." labelling to the frontend transformer layer as #5905 already decided.

### D5-06: `FingerprintVectorResponse` makes all 25 fields optional (and defaults to an all-null vector) though they are never null
- **Severity**: LOW
- **Dimension**: Schema Consistency (optional fields)
- **Location**: `auralis-web/backend/schemas/library.py:198-240`, `auralis-web/backend/routers/albums_models.py:49,59`
- **Status**: NEW
- **Description**: The track/album models are Optional-everywhere for a documented reason (`Track.to_dict()` degrades for detached rows). The fingerprint model has no such reason: every `TrackFingerprint` column is `nullable=False`, and both handlers always populate all 25 keys (`median_fingerprint()` returns floats via `np.median`; the track endpoint reads the columns directly). Yet every field is `float | None = None`, and `AlbumFingerprintResponse` / `AlbumFingerprintEntry` use `default_factory=FingerprintVectorResponse`, so a code path that forgot to fill `fingerprint` would serialize a valid-looking all-null fingerprint instead of failing.
- **Evidence**:
  ```python
  sub_bass: float | None = Field(default=None, description="Sub-bass energy share")
  ...
  fingerprint: FingerprintVectorResponse = Field(default_factory=FingerprintVectorResponse, ...)
  ```
  (`models/fingerprint.py`: all 25 columns `nullable=False`.)
- **Impact**: OpenAPI/codegen types every dimension as nullable, forcing null guards on clients, and the response model cannot catch a producer that drops a key.
- **Suggested Fix**: Make the 25 fields required `float` and drop the `default_factory` on the two album models.

### D5-07: `PlaylistListResponse` re-declares the page envelope instead of extending `PaginatedResponse`
- **Severity**: LOW
- **Dimension**: Schema Consistency (schema reuse)
- **Location**: `auralis-web/backend/routers/playlists_models.py:55-61`
- **Status**: NEW (sibling of closed #5499, whose fix introduced `PaginatedResponse` and adopted it for tracks, albums and artists but not playlists)
- **Description**: `TrackListResponse`, `AlbumListResponse` and `ArtistsListResponse` all subclass `schemas.library.PaginatedResponse`; `PlaylistListResponse` still copies `total/limit/offset/has_more` verbatim. The handler already uses the shared `paginated()` envelope, so only the model drifts.
- **Evidence**:
  ```python
  class PlaylistListResponse(BaseModel):
      playlists: list[PlaylistResponse] = ...
      total: int = Field(...); limit: int = Field(...); offset: int = Field(...); has_more: bool = Field(...)
  ```
- **Impact**: A change to the envelope (rename, added field) updates three list models and silently skips the fourth.
- **Suggested Fix**: `class PlaylistListResponse(PaginatedResponse)` with just the `playlists` list.

### D5-08: Closed string sets are re-declared as inline Literals instead of imported (repeat mode x4, playback state x2)
- **Severity**: LOW
- **Dimension**: Schema Consistency (enum values)
- **Location**: `auralis-web/backend/player_state.py:101`, `auralis-web/backend/routers/player_models.py:119,170`, `auralis-web/backend/websocket/outbound/player.py:17,33`
- **Status**: NEW (closed #6048 fixed only the frontend copies, commit d1fca07d0)
- **Description**: The repeat-mode set `off|all|one` is spelled four times (`PlayerState.repeat_mode`, `RepeatModeRequest.mode`, `QueueInfoResponse.repeat_mode`, and `RepeatMode` in `outbound/player.py`), plus a fifth tuple in `queue_enrichment.py:158`. `PlayerStatePayload.state` re-types `Literal["playing","paused","stopped","loading","error"]` although `PlaybackState` (a `str` Enum, already imported by `player_state.py` "so there is one enum for engine and wire") defines it. The preset set was unified by #4424/#5794 precisely to avoid this.
- **Evidence**:
  ```python
  player_state.py:101   repeat_mode: Literal["off", "one", "all"] = "off"
  player_models.py:119  mode: Literal["off", "all", "one"]
  player_models.py:170  repeat_mode: Literal["off", "all", "one"] | None = None
  outbound/player.py:17 RepeatMode = Literal["off", "all", "one"]
  outbound/player.py:33 state: Literal["playing", "paused", "stopped", "loading", "error"]
  ```
- **Impact**: No defect today; adding a mode or state means editing 5+ sites, and each copy stays self-consistent so mypy will not flag a miss (the request model would 422 a value the WS payload emits).
- **Suggested Fix**: Define `RepeatMode` once (e.g. in `player_state.py` or `schemas/`) and import it in the three places; type the payload `state` from `PlaybackState` values.

### D5-09: Stale docstrings contradict the current schemas
- **Severity**: LOW
- **Dimension**: Schema Consistency (documentation of contract)
- **Location**: `auralis-web/backend/routers/albums_models.py:15-19`, `auralis-web/backend/routers/enhancement_controls.py:151,159`, `auralis-web/backend/routers/pagination.py:22-30`
- **Status**: NEW
- **Description**: Three comments describe contracts that no longer exist. (1) `AlbumTracksResponse` says it is "deliberately snake_case while the sibling `GET /api/albums/{id}` is camelCase"; #4679 removed the camelCase shape and `GET /api/albums/{id}` now returns the snake_case `AlbumResponse` (see `albums.py:141-153`). (2) `set_enhancement_intensity` documents the intensity as "clamped" / "already clamped by SetIntensityRequest"; since #4600 the model rejects out-of-range and non-finite values with a 422 (`EnhancementIntensity = Field(ge=0, le=1)`), it never clamps. (3) `compute_has_more`'s docstring says a shared generic response model was "deleted here (#5054)" and that the other four endpoints "should eventually adopt" the per-router pattern; `PaginatedResponse` (#5499) now exists and three of them subclass it.
- **Evidence**:
  ```python
  # albums_models.py:15-16
  Deliberately snake_case while the sibling `GET /api/albums/{id}` is camelCase
  # enhancement_controls.py:159
  intensity = body.intensity  # already clamped by SetIntensityRequest
  ```
- **Impact**: Readers (and the audit tooling) take these as the live contract; the clamp comment in particular invites reintroducing the NaN-to-maximum hazard #4600 removed.
- **Suggested Fix**: Rewrite the three comments to the current behavior.

### D5-10: Same field name, different meaning across request/response bodies (`tracks` of ids, `processing` as id vs count)
- **Severity**: LOW
- **Dimension**: Schema Consistency (field naming)
- **Location**: `auralis-web/backend/routers/player_models.py:22` vs `:56` and `routers/playlists_models.py:24,35`; `routers/fingerprint_queue_models.py:22` vs `routers/processing_models.py:126`
- **Status**: NEW
- **Description**: Every other id-list body field is `track_ids` (`AddTracksToQueueRequest`, `CreatePlaylistRequest`, `AddTracksRequest`), but `SetQueueRequest.tracks` is also a list of ids (`TrackIdList`) and shares its name with response fields that hold full track objects (`QueueInfoResponse.tracks`, `TrackListResponse.tracks`). Separately, `processing` is a job COUNT in `QueueStatusResponse` and a single TRACK ID (or null) in `FingerprintQueueStatusResponse`, next to `queued` which is a count in both.
- **Evidence**:
  ```python
  player_models.py:22        tracks: TrackIdList          # ids
  player_models.py:56        track_ids: TrackIdList
  processing_models.py       processing: int = 0          # count
  fingerprint_queue_models.py:22  processing: int | None = Field(default=None, description="Track ID being processed, if any")
  ```
- **Impact**: Naming only; the frontend already sends `tracks: ids`, so a rename is a breaking contract change. Worth fixing only with a versioned alias or when the endpoint is next touched.
- **Suggested Fix**: Accept `track_ids` on `POST /api/player/queue` (keep `tracks` as an alias for one release) and rename the fingerprint-queue field to `processing_track_id`.

### D6-01: WebSocket origin/limit rejections log an unthrottled WARNING per attempt — page-triggerable log flood (#6188 fix missed this site)
- **Severity**: LOW
- **Dimension**: Middleware & Config (logging)
- **Location**: `auralis-web/backend/config/globals.py:136-150`, `:160`
- **Status**: NEW (sibling gap left by closed #6188 / #6186; they throttled OriginCheck, Host, CORS preflight and invalid WS frames via `config/log_throttle.warn_throttled` but not `ConnectionManager.connect`)
- **Description**: `ConnectionManager.connect()` logs `logger.warning(...)` on every rejected handshake (untrusted `Origin`, empty Origin from a non-loopback peer, and the 17th-connection refusal) with no throttle. A hostile web page can run `new WebSocket("ws://localhost:8765/ws")` in a loop: the `Host` header is `localhost:8765`, so `LoggingTrustedHostMiddleware` passes it, the page's `Origin` is not in `ALLOWED_WS_ORIGINS`, and the handler logs one WARNING per attempt (accept, close 1008, raise). #6188's own note assumed "the WS part needs an origin-allowed client", which is wrong for exactly this rejection branch: the rejection happens *because* the origin is not allowed.
- **Evidence**:
  ```python
  # config/globals.py:136-139
  if origin not in ALLOWED_WS_ORIGINS:
      logger.warning(f"WebSocket connection rejected: untrusted origin {origin!r}")
      await self._reject_origin(websocket, f"untrusted origin {origin!r}")
  ```
  Reproduced with `TestClient(main.app).websocket_connect('/ws', headers={'Origin': 'http://evil.example', 'Host': 'localhost:8765'})` x50: 50 WARNING records ("WebSocket connection rejected: untrusted origin ...") for 50 attempts (0 suppressed). Against a real `python main.py` (AURALIS_PORT=18766) each raw-socket upgrade with `Origin: http://evil.example` produced three log lines: the `config.globals` WARNING, then uvicorn's `- "WebSocket /ws" [accepted]` and `connection open` (see D6-03). Compare `config/middleware/origin_check.py:103-129`, which uses `warn_throttled`.
- **Impact**: Same anti-forensic effect #6188 documented: electron-log keeps 1 MiB + one archive, so a visited page floods the log and evicts earlier security entries within minutes; also one accept+close per attempt on the loop.
- **Suggested Fix**: Route the three `logger.warning` calls in `connect()` through `warn_throttled(logger, "ws.untrusted_origin" | "ws.non_loopback_no_origin" | "ws.connection_limit", ...)` (fixed keys, as the module docstring requires).

### D6-03: uvicorn's per-request access log stays enabled — every request (with its query string) is persisted, and per-connection WS lines undo the #6188 throttling
- **Severity**: LOW
- **Dimension**: Middleware & Config (logging configuration)
- **Location**: `auralis-web/backend/main.py:394-403`
- **Status**: NEW (adjacent to closed #6184 / #6188, which bounded the app-level rejection logs and sanitized uvicorn's formatter but left `access_log` at its default)
- **Description**: `uvicorn.run(app, ..., log_config=None, log_level=_log_level, ...)` is called without `access_log=False`. With `log_config=None` uvicorn's loggers propagate to the root handler configured by `configure_logging()` (INFO in a packaged build), so `uvicorn.access` emits one INFO line per HTTP request and `uvicorn.error` emits `"WebSocket /ws" [accepted]` + `connection open` per socket. Python's default `basicConfig` stream is stderr, and `desktop/main.js:216-220` logs all backend stderr via `log.error('[Backend Error]', ...)` into the electron-log file (1 MiB + one archive per the #6188 analysis). Normal traffic (library browsing, artwork, polling) therefore consumes the same persisted budget #6188 throttling was meant to protect, the lines are labelled as errors, and URLs with user query strings (library search terms) are persisted at INFO.
- **Evidence**:
  ```python
  # main.py:394-403
  uvicorn.run(
      app, host="127.0.0.1", port=_port,
      ws_max_size=WS_MAX_MESSAGE_SIZE,
      log_level=_log_level,
      log_config=None,
      timeout_graceful_shutdown=int(SHUTDOWN_STEP_TIMEOUT_S),
      proxy_headers=False,
  )   # no access_log=False
  ```
  Observed on a real server (`python main.py`, AURALIS_PORT=18765, HOME=scratch): `uvicorn.access - INFO - 127.0.0.1:56828 - "GET /api/library/tracks?limit=1 HTTP/1.1" 200` for each of 4 curl requests; and for each hostile-origin WS upgrade `uvicorn.error - INFO - ... "WebSocket /ws" [accepted]` and `connection open`, independent of any app-level throttle.
- **Impact**: Routine use (and a hostile page opening sockets/GETs in a loop) rolls the 1 MiB persisted log quickly, evicting startup/security entries; mislabelled as `[Backend Error]`; search terms land in the persisted log despite the INFO "safe to paste" policy.
- **Suggested Fix**: Pass `access_log=False` to `uvicorn.run` (the app already logs its own security-relevant rejections), and either demote/filter the `uvicorn.error` per-WebSocket lines or leave them to DEBUG; keep `log_config=None`.

### D6-04: Similarity auto-fit logs two ERROR lines at startup and every 5 minutes for the normal "library has < 10 fingerprints" state
- **Severity**: LOW
- **Dimension**: Middleware & Config (logging levels / background-worker wiring)
- **Location**: `auralis/analysis/fingerprint/normalizer.py:101-104`, `auralis/analysis/fingerprint/similarity.py:149-150`; driven from `auralis-web/backend/services/similarity_autofit_worker.py:42,91-100` (started by `config/startup/fingerprint.py:154-161`)
- **Status**: NEW
- **Description**: `SimilarityAutoFitWorker._run()` calls `fit()` once at startup and then every `_CHECK_INTERVAL_SECONDS = 300` while running. `FingerprintNormalizer.fit()` logs `error("Insufficient fingerprints for normalization: N < 10")` and `FingerprintSimilarity.fit()` logs `error("Failed to fit similarity system")` whenever the count is below `min_samples`, although the backend treats this as an expected, quiet state (the worker itself logs INFO "skipped (not enough fingerprints yet)" and `config/startup/fingerprint.py` documents it as "a no-op (returns False) below min_samples"). Result: a fresh install or any small library emits two ERROR lines on every launch and again every 5 minutes for as long as the app stays open.
- **Evidence**:
  ```python
  # normalizer.py:101-104
  total = fingerprint_repository.get_count(current_only=True)
  if total < min_samples:
      error(f"Insufficient fingerprints for normalization: {total} < {min_samples}")
      return False
  # similarity.py:149-150
  else:
      error("Failed to fit similarity system")
  ```
  Startup of a real backend on an empty library (HOME=scratch) printed `auralis - ERROR - Insufficient fingerprints for normalization: 0 < 10` / `auralis - ERROR - Failed to fit similarity system` immediately before the worker's own INFO "skipped" line.
- **Impact**: ERROR noise in the persisted log (and `[Backend Error]` mislabelling through the Electron wrapper) that trains users/support to ignore ERROR lines and eats the log budget; ~24 spurious ERROR lines/hour for an idle empty library.
- **Suggested Fix**: Log the below-threshold case at INFO/DEBUG (it is a return value, not a failure) and let only a real exception inside `fit()` use `error()`; optionally log it once per transition rather than every re-check.

### D6-05: `CONFIG.md` (the env-var reference) omits ~15 tunables read at import time and points two variables at modules that no longer read them
- **Severity**: LOW
- **Dimension**: Middleware & Config (env-var tuning docs)
- **Location**: `auralis-web/backend/CONFIG.md:15-23`; code in `config/limits.py:185-223`, `config/origins.py:39`, `core/executors.py:100-117`, `config/bootstrap.py:44-81`, `config/app.py:304`
- **Status**: NEW
- **Description**: CONFIG.md presents itself as the table of per-deployment overrides ("Tuning constants that can be overridden per-deployment via environment variables"), but a sweep of every `AURALIS_*` name read by the backend/engine/desktop against the doc shows that these are read in code and absent from it: `AURALIS_PORT`, `AURALIS_DEV_MODE` (changes Swagger/ReDoc exposure and widens the CORS/WS origin allowlists, #4802), `AURALIS_LOG_LEVEL`, all 18 `AURALIS_RATE_LIMIT_*_{MAX,WINDOW}` variables (#3901 added them precisely so a power user can raise the 2/min scan limit), `AURALIS_IO_POOL_WORKERS`, `AURALIS_JOB_POOL_WORKERS`, `AURALIS_TRANSPORT_POOL_WORKERS`, `AURALIS_FINGERPRINT_TRACK_TIMEOUT`, `AURALIS_MAX_DECODED_BYTES`, `AURALIS_MAX_DURATION_SECONDS`, `AURALIS_DATA_DIR`. Two documented rows are stale after the #6271/#5991 splits: `AURALIS_FINGERPRINT_WORKERS` is listed under `analysis/fingerprint_generator.py` but is read in `analysis/fingerprint_executor.py:29-31`; `AURALIS_SCAN_TIMEOUT` is listed under `routers/library_scan.py` but is read in `config/limits.py:185`.
- **Evidence**: `comm` of the doc's `AURALIS_*` set against `grep -rhoE "AURALIS_[A-Z_]+"` over `auralis-web/backend`, `auralis`, `desktop/main.js`, `launch-auralis-web.py` yields the list above as "in code, not in doc" and nothing in "doc, not in code". `config/limits.py:204-223` `get_int_env("AURALIS_RATE_LIMIT_..._MAX", ...)`.
- **Impact**: An operator cannot discover the rate-limit/pool/port/dev-mode switches from the one document meant to list them; the stale "Where" column sends a reader to the wrong module.
- **Suggested Fix**: Add the missing rows (grouping the rate-limit pairs) and correct the two "Where" entries; consider generating the table from `get_int_env` call sites so it cannot drift again (`scripts/check_doc_counts.py` pattern).

### D7-03: Connection-pool exhaustion (`sqlalchemy.exc.TimeoutError`) is returned as HTTP 500, not a retryable 503
- **Severity**: LOW
- **Dimension**: Error Handling & Resilience
- **Location**: `auralis-web/backend/routers/errors.py:145-148` (`handle_query_error`), `auralis/library/database_engine.py:60-64` (pool config)
- **Status**: NEW
- **Description**: `handle_query_error`, the funnel behind `with_error_handling`, maps only `sqlalchemy.exc.OperationalError` to 503. SQLAlchemy raises QueuePool exhaustion as `sqlalchemy.exc.TimeoutError`, which is a direct `SQLAlchemyError` subclass, not an `OperationalError` (checked with `issubclass` in the project venv). The engine is `pool_size=5, max_overflow=5` with SQLAlchemy's default 30 s `pool_timeout`. Routers run sync repository calls on an 8-thread I/O pool, while the scanner thread and the multi-worker fingerprint extraction queue also hold sessions. #4810 sized the I/O pool to the pool ceiling to avoid exactly this, and its note records that the failure "surfaces as a 500 rather than back-pressure". The sizing narrows the window but the mapping was never added. `_with_similarity_error_handling` has the same gap.
- **Evidence**:
  ```python
  # routers/errors.py
  146:    from sqlalchemy.exc import OperationalError
  147:    if isinstance(error, OperationalError):
  148:        raise ServiceUnavailableError(f"Database temporarily unavailable during {operation}")
  ...
  157:    raise InternalServerError(operation, error)     # TimeoutError falls here -> 500 + ERROR traceback
  ```
- **Impact**: During a large scan plus fingerprint backlog, a request that waits the full 30 s for a connection returns "Failed to <operation>" (500) with an ERROR traceback instead of a 503 the client can retry. The frontend cannot tell it from a server bug.
- **Suggested Fix**: Add `sqlalchemy.exc.TimeoutError` to the 503 branch in `handle_query_error` and in `_with_similarity_error_handling`.

### D7-05: A single-flight follower thread polls forever when its stream ends by chunk timeout, because only cancellation sets its stop flag
- **Severity**: LOW
- **Dimension**: Error Handling & Resilience
- **Location**: `auralis-web/backend/core/chunk_single_flight.py:37-40`, `auralis-web/backend/core/chunk_streaming.py:106-114`, `auralis-web/backend/core/stream_enhanced_chunks.py:221-262`, `auralis-web/backend/core/stream_enhanced_lifecycle.py:143-157`
- **Status**: NEW
- **Description**: A stream that misses a chunk another stream is already rendering becomes a follower. Its executor thread blocks in `wait_for_leader`, which loops `while not self._done.wait(0.1): check_cancelled()`. `check_cancelled` is `_raise_if_cancelled`, which reads only the stream's `chunk_cancel_event`. That event is set by `signal_cancel` (stop, seek, play-reissue, disconnect) and by the processor-init timeout. When a chunk wait hits `CHUNK_PROCESS_TIMEOUT` (30 s), `process_chunk_only` raises `TimeoutError`. The pump sends the error, `break`s, and the stream ends normally. `run_enhanced_stream`'s `finally` never sets `chunk_cancel_event`. The `wait_for` has abandoned the coroutine, but the follower thread keeps polling until the leader finishes. The same is true of the leader's own thread. A leader that never finishes (a stalled network mount, which this library lives on, or a hung native call) therefore parks one stream-pool thread per timed-out follower stream, indefinitely.
- **Evidence**:
  ```python
  # chunk_single_flight.py:39-40
  while not self._done.wait(FOLLOWER_POLL_S):
      check_cancelled()                       # only the stream's cancel event can raise here
  # stream_enhanced_lifecycle.py:143-157 (finally): no chunk_cancel_event.set() on this exit path
  ```
- **Impact**: Needs a leader that does not finish plus repeated play attempts of the same chunk. The pool is `max(4, 2 * MAX_CONCURRENT_STREAMS)` = 20 threads shared with look-ahead reads and every other stream, so about 20 retries starve all streaming until the mount recovers or the process restarts. This is the pile-up #4999 and #5074 were written to avoid, reintroduced by single-flight (e0e91f792).
- **Suggested Fix**: Set `stream.chunk_cancel_event` in the `finally` of `run_enhanced_stream` and in the pump's timeout branch, so an abandoned follower (and an abandoned leader's post-DSP persist) exits. Optionally bound `wait_for_leader` with a deadline.

### D7-06: Tier-3 fingerprint extraction swallows every failure, so a track-specific failure silently falls back to per-chunk mastering
- **Severity**: LOW
- **Dimension**: Error Handling & Resilience
- **Location**: `auralis-web/backend/core/fingerprint_loading.py:250-253`, `auralis/analysis/fingerprint/windowed_compute.py:147-149`, `auralis-web/backend/core/chunk_processor_init.py:150-165`
- **Status**: NEW
- **Description**: `extract_from_audio` (and `compute_windowed_fingerprint` beneath it) catch `Exception`, including `FingerprintUnavailable`, and return `None`. `init_fingerprint_and_processor` documents that on `None` "the renderer falls back to per-chunk analysis, as before". The #6107 policy holds when the engine is missing or broken for every call, because the per-chunk `analyze` then raises on chunk 0 and the stream fails. It does not hold when whole-track analysis fails for this track (non-finite result, partial result, decode error) while the 15 s chunk windows analyse fine. In that case no mastering targets are set (`targets_hash` = "none"). Each chunk is mastered from its own fingerprint, which is what the "one whole-track plan" design in the scope text exists to prevent. The failure is visible only in an ERROR log line. The client is told nothing, and the chunks are cached on disk under the `none` targets hash for the session.
- **Evidence**:
  ```python
  # fingerprint_loading.py:250-253
  except Exception as e:
      logger.error(f"Fingerprint extraction failed for {Path(filepath).name}: {e}")
      return None
  # chunk_processor_init.py:156-157
  # extraction itself fails the result is None and the renderer falls back to per-chunk analysis, as before.
  ```
- **Impact**: A rare track-specific analysis failure plays with chunk-to-chunk inconsistent mastering instead of failing or retrying. No bypass of the master occurs, so this is not the #6107 failure mode.
- **Suggested Fix**: Let `FingerprintUnavailable` from tier 3 propagate through `extract_from_audio` so it ends the stream through the existing `job_error_mapping` / `_safe_error_message` path, or at least send the client a `fingerprint_progress` "failed" status. Keep returning `None` for the deliberate cases (cancelled wait, empty or too-short audio).

### D8-02: `SimilarityAutoFitWorker` permanently parks one of the 8 default-executor (DB-sized) threads
- **Severity**: LOW
- **Dimension**: Performance & Resource Management
- **Location**: `auralis-web/backend/services/similarity_autofit_worker.py:69`, `:96-99`; pool sizing in `auralis-web/backend/core/executors.py:98-106`, `:243`
- **Status**: NEW (introduced as a side effect of the #4682 fix, which is CLOSED)
- **Description**: `start()` submits the whole worker loop with `asyncio.ensure_future(asyncio.to_thread(self._run))`. `to_thread` uses the loop's default executor, which `install_executors()` sets to the I/O pool of only `IO_POOL_SIZE = 8` workers (deliberately sized to stay under the SQLAlchemy pool of 10, #4810/#5086). `_run()` never returns until shutdown: after the initial fit it loops on `self._stop_event.wait(300)` forever, so a worker thread is occupied for the whole process lifetime while idle. Effective I/O pool capacity is 7, and every other long to_thread job (library scan, K-NN graph build, job input decode/resample/save, stream setup with whole-track fingerprint analysis) subtracts further from the 8 that all repository calls share.
- **Evidence**:
  ```python
  # similarity_autofit_worker.py:69
  self._task = asyncio.ensure_future(asyncio.to_thread(self._run))
  # :96-99
  self._fit_once(first=True)
  while not self._stop_event.wait(self._check_interval):   # 300 s, parked in a pool thread
      self._fit_once(first=False)
  # executors.py:243
  asyncio.get_running_loop().set_default_executor(_io_executor)   # 8 workers
  ```
- **Impact**: Roughly 12% of the pool the REST layer depends on is permanently unavailable; during a library scan + auto-fit + a job decode the margin shrinks to a handful of workers, so UI browse calls can queue behind them. Moderate, not a failure.
- **Suggested Fix**: Run the wait loop as an asyncio task and `to_thread` only each `fit()` pass (the thread is then busy only while fitting), or give the worker its own dedicated `threading.Thread`/small executor as the other long-lived workers have.

### D8-03: `POST /api/similarity/fingerprint-queue/enqueue-all` hydrates every missing track as a full ORM row to read `.id`, then the queue accepts only 5,000
- **Severity**: LOW
- **Dimension**: Performance & Resource Management
- **Location**: `auralis-web/backend/routers/fingerprint_queue.py:163-167`; `auralis/library/repositories/fingerprint_query_mixin.py:240-272` (`get_missing_fingerprints`); queue cap `auralis-web/backend/analysis/fingerprint_queue.py:65`
- **Status**: NEW (related but distinct from CLOSED #5906/#5872, which deferred `lyrics`/`comments` only on list reads; this query was left out; stale-version rows missed by this query are tracked in #5891, not repeated here)
- **Description**: With no `limit` (the default and the UI case) the handler loads every `Track` row lacking a fingerprint — all columns including the large `lyrics` and `comments` text — expunges them, and then uses only `track.id`. `FingerprintQueue.MAX_QUEUE_SIZE = 5000`, so for a big library everything beyond the first 5,000 ids is hydrated for nothing and reported as `dropped_queue_full`.
- **Evidence**:
  ```python
  # routers/fingerprint_queue.py:163-167
  missing_tracks = await asyncio.to_thread(repos.fingerprints.get_missing_fingerprints, limit=limit)
  enqueued_count, skipped_count, dropped_count = await asyncio.to_thread(
      queue.enqueue_many, [track.id for track in missing_tracks]
  )
  # fingerprint_query_mixin.py:253-262
  stmt = select(Track).outerjoin(TrackFingerprint, ...).where(TrackFingerprint.id == None).order_by(Track.id)
  if limit is not None: stmt = stmt.limit(limit)
  tracks = session.execute(stmt).scalars().all()
  ```
  Measured on a scratch library: 20,000 tracks with ~3 KB lyrics each = 0.5 s and ~125 MB peak Python heap (transient, on an I/O-pool thread) for a result of which at most 5,000 ids are used.
- **Impact**: Transient memory and I/O spike proportional to library size on a button press; `Track` rows with lyrics make it worse. Not a failure.
- **Suggested Fix**: Add an id-only repository query (`select(Track.id)...limit(MAX_QUEUE_SIZE - queued)`) and use it from this route; have `get_missing_fingerprints` `defer()` the text columns like `_track_eager_options(list_read=True)`.

### D8-05: Synchronous filesystem calls on the event loop in several `async def` handlers (sweep missed siblings)
- **Severity**: LOW
- **Dimension**: Performance & Resource Management
- **Location**: `routers/artwork.py:110,115,123,131,171`; `routers/processing_jobs.py:81,84,91`; `core/job_execution.py:152`; `routers/files_upload.py:160`; `services/recommendation_service.py:61` (`validate_file_path`); `routers/processing_upload.py:151`
- **Status**: NEW (the same class as #4653/#3911, whose "consistency sweeps" are CLOSED but did not reach these)
- **Description**: `get_album_artwork` is hit once per album tile. Its `mkdir` and DB read are offloaded (the comment says "#4653's CONSISTENCY sweep"), but the rest of the handler still does `Path.resolve()` x2, `is_relative_to`, `exists()`, `mimetypes` and `serve_path.stat()` directly on the loop. `download_result` does `resolve()` x2 + `exists()`; `execute_job` does `Path(reference_path).exists()`; `upload_files` does `Path(temp_path).stat()`; `RecommendationService._get_or_analyze` calls `validate_file_path()` (resolve + stat) on the loop. Each is a few syscalls on a local disk, but a library or artwork folder on a network share/slow disk turns each into a loop-wide stall (WebSocket audio frames, pongs, transport commands all share the loop).
- **Evidence**:
  ```python
  # routers/artwork.py:110-131,171  (inside async def get_album_artwork)
  allowed_dir = artwork_dir.resolve()
  requested_path = Path(artwork_path).resolve(strict=False)
  if not requested_path.exists(): ...
  stat = serve_path.stat()
  ```
- **Impact**: Negligible on a local SSD; latency spikes for every concurrent stream/WebSocket client if the stat target is slow. Pure consistency/hardening.
- **Suggested Fix**: Wrap the path validation/stat block of each handler in one `asyncio.to_thread` helper (as `get_album_artwork` already does for `_get_or_create_thumbnail`).

### D9-02: Two strict-xfail tests in tests/backend/test_error_handling.py still describe the already-fixed #5191 bug and now "xfail" for the wrong reason
- **Severity**: LOW
- **Dimension**: Test Coverage (stale tests)
- **Location**: `tests/backend/test_error_handling.py:173-186` and `:213-224`
- **Status**: NEW (sibling of closed #5156 - xfail markers citing CLOSED issues)
- **Description**: `test_error_process_nan_audio_short_buffer` / `test_error_process_inf_audio_short_buffer` are `xfail(strict=True)` with
  reason "#5191: the MIN_SAMPLES short-circuit returns before validate_audio_finite". #5191 is CLOSED and fixed in `73cc8b982`
  ("a short non-finite buffer fails fast like a long one"): `process()` now raises `ModuleError` for NaN/Inf at any length, and the
  new `tests/auralis/core/test_short_buffer_nonfinite_5191.py` pins that. The two old tests call `processor.process(...)` and then
  assert the output is finite; because `process()` now raises, an un-narrowed `xfail` swallows the exception and reports XFAIL, so the
  strict marker can never flip to XPASS. The tests are permanently green no-ops that document a bug that no longer exists.
- **Evidence**:
  ```
  tests/backend/test_error_handling.py:173:@pytest.mark.xfail(
  tests/backend/test_error_handling.py:174:    strict=True,
  tests/backend/test_error_handling.py:175:    reason="#5191: the MIN_SAMPLES short-circuit returns before "
  tests/backend/test_error_handling.py:183:    processed = processor.process(audio_with_nan)      # now raises ModuleError (73cc8b982)
  tests/backend/test_error_handling.py:184:    assert not np.isnan(processed).any()
  ```
- **Impact**: Misleading coverage signal (two "known bug" tests for a fixed bug); an xfail without `raises=` hides any future,
  different exception in that path.
- **Suggested Fix**: Delete the two tests (the behaviour is covered by `test_short_buffer_nonfinite_5191.py`), or convert them to
  `pytest.raises(ModuleError, match="NaN|Inf")`.

### D9-03: tests/boundaries/test_chunked_processing_boundaries.py hardcodes stale chunk geometry (CHUNK_DURATION=10, OVERLAP=3) instead of importing chunk_boundaries
- **Severity**: LOW
- **Dimension**: Test Coverage (chunk boundaries)
- **Location**: `tests/boundaries/test_chunked_processing_boundaries.py:24-28` (constants), `:97-370`, `:520`, `:543`
- **Status**: NEW
- **Description**: CLAUDE.md invariant: chunk constants come only from `core/chunk_boundaries.py`. This file (30 tests, 23 not `slow`,
  so they run in CI) defines `CHUNK_DURATION = 10.0  # (Phase 2 reduced from 30s)` and `OVERLAP_DURATION = 3.0`; the live values are
  15 / 10 (INTERVAL) / 5. Every "exact boundary" test is therefore built at a duration that is not a real boundary (e.g. "exactly one
  chunk duration" is a 10 s file, which is simply a short single-chunk track; several tests carry a comment admitting
  "Real engine CHUNK_DURATION is 15s, so this ~10s file is a single ..."). Docstrings still say 30.0s / 60.0s / 90.0s. Lines 520/543
  assert `processor.total_chunks >= int(duration / CHUNK_DURATION) + 1 - 1`, i.e. exactly the `duration / CHUNK_DURATION` counting
  that the project says `content_chunk_count()` replaced; they pass only because the stale 10.0 happens to equal today's
  `CHUNK_INTERVAL`. The real boundary cases are covered in `tests/backend/test_chunked_processor_boundaries.py` (which imports
  `CHUNK_DURATION, OVERLAP_DURATION` from `core.chunk_boundaries`), so this file is a misleading duplicate rather than a gap.
- **Evidence**:
  ```
  tests/boundaries/test_chunked_processing_boundaries.py:27:CHUNK_DURATION = 10.0  # 10 seconds per chunk (Phase 2 reduced from 30s)
  tests/boundaries/test_chunked_processing_boundaries.py:28:OVERLAP_DURATION = 3.0  # 3 seconds overlap
  tests/boundaries/test_chunked_processing_boundaries.py:520:    expected_chunks = int(duration / CHUNK_DURATION) + 1
  tests/backend/test_chunked_processor_boundaries.py:29:from core.chunk_boundaries import CHUNK_DURATION, OVERLAP_DURATION
  ```
  Siblings with local mock constants that disagree with the real ones (mock-only, lower impact):
  `tests/backend/test_chunk_failure_recovery.py:36` (`CHUNK_DURATION = 30.0`), `tests/backend/test_chunk_timeout_seek_stream_abort_5074.py:33` (`30.0`).
- **Impact**: A change to chunk geometry will not move these tests; they report green while asserting nothing about real boundaries.
- **Suggested Fix**: Import `CHUNK_DURATION`/`CHUNK_INTERVAL`/`OVERLAP_DURATION` and use `content_chunk_count()` for expected counts, or delete the
  file in favour of `tests/backend/test_chunked_processor_boundaries.py`.

### D9-04: Artwork extract/delete error branches have no test at any level (extract "no artwork found" 404, delete unknown album 404, delete-already-absent)
- **Severity**: LOW
- **Dimension**: Test Coverage (router error cases)
- **Location**: `auralis-web/backend/routers/artwork_manage.py:46-48` (extract 404), `:91-93` (delete 404), `:107-111` (no broadcast when `success` False)
- **Status**: NEW
- **Description**: `POST /api/albums/{id}/artwork/extract` and `DELETE /api/albums/{id}/artwork` are exercised only by success cases:
  `tests/backend/test_main_api.py:1609-1657` (HTTP, mocked repos) and `tests/backend/test_artwork_router_handler_seam_4670.py:59-105`
  (direct handler call). The seam file asserts 404 only for GET and download. The 404s, the idempotent "already deleted -> success but
  no broadcast" contract (#3563 comment in the handler) and a repository exception mapping through `with_error_handling` are not asserted.
- **Evidence**:
  ```
  artwork_manage.py:46:    if not artwork_path:
  artwork_manage.py:47:        raise NotFoundError("Artwork", detail="No artwork found in album tracks")
  artwork_manage.py:91:    if album is None:
  artwork_manage.py:92:        raise NotFoundError("Album", album_id)
  artwork_manage.py:109:    if success:
  artwork_manage.py:110:        await _broadcast_artwork_updated(connection_manager, "deleted", album_id)
  ```
  grep across tests for `artwork/extract` finds only `test_main_api.py`; no test has `extract_and_save_artwork` returning falsy or `get_by_id` returning None for delete.
- **Impact**: A regression that turned the idempotent DELETE back into a 404 (#3563 was exactly that) or that broadcast on a no-op delete would pass CI.
- **Suggested Fix**: Add three seam tests (extract falsy -> 404; delete missing album -> 404; delete with `delete_artwork -> False` -> 200 and `broadcast.assert_not_awaited()`).

### D9-05: Playlist update route's empty-body 400 and the playlist_updated / playlist_deleted broadcast payloads are never asserted
- **Severity**: LOW
- **Dimension**: Test Coverage (router error cases / WS broadcasts)
- **Location**: `auralis-web/backend/routers/playlists_crud.py:146-148` (400), `:166-173`, `:217-220`; `playlists_tracks.py:58-61,106-109,149-154,202-205,236-241`
- **Status**: NEW
- **Description**: `PUT /api/playlists/{id}` with a body that sets neither `name` nor `description` raises `BadRequestError("No update data provided")`;
  `grep -rn "No update data" tests` returns nothing. The `playlist_updated` broadcasts (`renamed`, `track_added` x2, `reordered`, `track_removed`, `cleared`)
  and `playlist_deleted` are consumed by the frontend, but the only value-level broadcast assertions in tests are `playlist_created` and `cleared`
  (`test_playlists_router_handler_seam_4670.py:67,120`); `reordered` is checked only by substring-grepping handler source
  (`test_ws_typed_broadcast_contract_5293.py:129`: `assert '"action": "reordered"' in source`). Playlist update/delete success are tested only
  against mocks in `test_main_api.py:1380-1403` with no broadcast assertion.
- **Evidence**:
  ```
  playlists_crud.py:146:    if not update_data:
  playlists_crud.py:147:        raise BadRequestError("No update data provided")
  test_ws_typed_broadcast_contract_5293.py:129:    assert '"action": "reordered"' in source
  ```
- **Impact**: Frontend playlist-list refresh depends on these frames; a renamed key/action would not fail any test.
- **Suggested Fix**: Add seam tests for the 400 and one parametrised broadcast test (action + `playlist_id`) per mutating playlist handler.

### D9-06: Vacuous negative tests in test_player_api_comprehensive.py: the "malicious indices" reorder test sends the wrong schema, and several bounds tests accept status sets that include the success code
- **Severity**: LOW
- **Dimension**: Test Coverage (assertion quality)
- **Location**: `tests/backend/test_player_api_comprehensive.py:648-657`, `:262-268`, `:365-368`, `:316-320`
- **Status**: NEW
- **Description**: `test_reorder_invalid_indices` PUTs `{"from_index": -999, "to_index": 999999}` to `/api/player/queue/reorder`, but
  `ReorderQueueRequest` (`routers/player_models.py:26-34`) takes `new_order`, while `from_index/to_index` belong to `/queue/move`. The request
  always fails body validation (422), so the test never reaches the queue-index bounds it claims to test, and `in [200, 400, 422]` hides that.
  `test_seek_negative_position` asserts `in [200, 400, 422]` although `SeekRequest.validate_position` (`player_models.py:76-83`) unconditionally
  rejects negatives, so the only correct status is 422. `test_get_queue_accepts_get_only` / `test_remove_from_queue_accepts_delete_only`
  accept `200/404/405` and assert nothing about the method contract (an existing route returns 200 for the "wrong" verb in the first one).
- **Evidence**:
  ```
  test_player_api_comprehensive.py:650:        response = client.put("/api/player/queue/reorder", json={"from_index": -999, "to_index": 999999})
  test_player_api_comprehensive.py:656:        assert response.status_code in [200, 400, 422]
  player_models.py:34:    new_order: QueueIndexList
  player_models.py:80:        if v < 0:
  ```
- **Impact**: Out-of-range reorder/negative-seek hardening could regress with these tests staying green (the real bounds are only pinned elsewhere:
  `test_request_body_constraints_4681.py`, `test_queue_error_status_mapping.py`).
- **Suggested Fix**: Send `{"new_order": [-999, 999999]}` and assert 422 (or 400 from the service); tighten seek-negative to `== 422`. Same lenient-set pattern (29 sites) is listed
  in the weak-status-code sweep: `test_similarity_api.py:278,293,294,444,458,470`, `test_library_api_comprehensive.py:138,503,513,538`, `test_api_endpoint_integration.py:94,291,297,325`, `test_artists_api.py:146,153`.

### D9-07: Dead fixtures in tests/backend/conftest.py (several returning fabricated constants)
- **Severity**: LOW
- **Dimension**: Test Coverage (test hygiene)
- **Location**: `tests/backend/conftest.py:325-343` (`sample_track_ids`, `fingerprint_count`), `:523-560` (`mock_track_repository`, `mock_album_repository`, `mock_artist_repository`), `:494` (`mock_repository_factory_callable`), `sample_audio_long`
- **Status**: NEW
- **Description**: Word-grep of every fixture name across `tests/` shows zero consumers for `sample_track_ids`, `sample_audio_long`,
  `mock_track_repository`, `mock_album_repository`, `mock_artist_repository`, `mock_repository_factory_callable`. `fingerprint_count` is
  shadowed by a class-local fixture in `tests/auralis/analysis/fingerprint/test_similarity_system.py:102`, so the conftest version is unused too.
  `sample_track_ids` / `fingerprint_count` return fixed numbers ("In a real implementation, this would query the test database") and
  `mock_library_database` still documents "a mock LibraryManager" (retired in #4915).
- **Evidence**:
  ```
  tests/backend/conftest.py:325: def sample_track_ids(client, mock_track):   # returns [1, 2, 3]
  tests/backend/conftest.py:338: def fingerprint_count():                  # returns 100
  ```
- **Impact**: Dead scaffolding that looks like real fixtures; an author reaching for `sample_track_ids` gets IDs that do not exist in the isolated DB.
- **Suggested Fix**: Delete the unused fixtures and fix the LibraryManager docstring.

### D9-08: Startup wiring of the .25d store sweep (config/startup/fingerprint_store.py) and test_main_api's "marked as skipped" header are untested/stale
- **Severity**: LOW
- **Dimension**: Test Coverage (startup / docs-in-tests)
- **Location**: `auralis-web/backend/config/startup/fingerprint_store.py:20-28`, wired at `config/startup/__init__.py:169`; stale header `tests/backend/test_main_api.py:1-9`
- **Status**: NEW
- **Description**: `sweep_fingerprint_store()` (off-loop `to_thread`, "failure is logged, never fatal to startup") has no test: grep for the
  function name in `tests/` returns nothing; the engine-side `sweep_orphans` is tested (`tests/auralis/analysis/test_fingerprint_store_sweep_6004.py`) and
  the clear-cache path is tested, but not the startup step or its swallow-on-failure contract (sibling startup steps - stale sweep #5068, temp sweep,
  decode temps #5734, chunk dir offload - each have one). Separately `test_main_api.py` opens with "NOTE: ... This file is marked as skipped" although
  it has no skip marker and runs (`tests/backend/test_no_unaccountable_skips_4691.py` exists to prevent exactly that kind of mismatch).
- **Evidence**:
  ```
  fingerprint_store.py:25-28:    try: return await asyncio.to_thread(FingerprintStorage.sweep_orphans)
                                 except Exception as e: logger.warning(...); return 0
  test_main_api.py:6-8: "NOTE: Multiple API endpoints return 404/503 ... This file is marked as skipped."
  ```
- **Impact**: A raised exception in the sweep would abort startup with no test failing; the stale header misleads readers about what runs in CI.
- **Suggested Fix**: Add a two-line test (sweep raises -> returns 0, logged; runs via `to_thread`); remove the stale header paragraph.

### D9-09 (informational): CI deselects `slow`; the nightly slow suite is report-only, so ~170 slow tests (incl. concurrent library read/write, 1-2 hour chunk counts, many-chunks-no-gaps) can never fail a build
- **Severity**: LOW
- **Dimension**: Test Coverage (concurrency / chunk coverage gating)
- **Location**: `.github/workflows/backend-tests.yml:134` (`-m "not slow"`), `.github/workflows/slow-tests.yml:3-9,42-45` (`|| true`, report-only)
- **Status**: NEW (the workflow itself was added for #5966, closed; the missing gate is acknowledged in its header but not tracked by an open issue)
- **Description**: Concurrency tests `tests/backend/test_concurrent_operations.py` (5 of 7 tests `slow`), `tests/concurrency/test_thread_safety.py` (slow-marked cases),
  `tests/integration/test_e2e_workflows.py`, `tests/integration/test_end_to_end_processing.py` and the long-audio / no-gap chunk tests are `slow`. The nightly run always exits 0
  ("the slow suite has never had a CI baseline"). Fast-lane coverage remains good (processor-pool, rate-limit, similarity-endpoint, stream-race and WS-task tests are not `slow`).
- **Impact**: Regressions confined to slow-marked concurrency/E2E tests surface only as an unread artifact.
- **Suggested Fix**: Check in a slow-suite baseline and gate nightly on it exactly as `check_pytest_baseline.py` does for the fast lane.

### D10-04: Clear Cache / per-track clear / library reset never reach the ProcessorFactory tier (warm HybridProcessors)
- **Severity**: LOW
- **Dimension**: Caching & Invalidation (invalidation reach)
- **Location**: `auralis-web/backend/core/cache_cleanup.py:39-105`, `auralis-web/backend/core/processor_lease.py:119-142`, `auralis-web/backend/config/startup/shutdown.py:117`
- **Status**: NEW
- **Description**: Released stream processors are parked in `ProcessorFactory._processor_cache` (32-entry LRU, key = `(track_id, preset, config_hash, targets_hash)`, no file signature) and re-leased by the next stream with their DSP state intact. `clear_track_caches` / `clear_all_caches` clear chunk files, thumbnails, the target cache and the streamlined tiers but not this tier; `processor_factory.clear_cache()` is called only at shutdown. So the user's "clear and retry" lever re-renders chunk 0 on a processor warmed by the previous stream (not a clean render), and after a library reset (track ids restart) a new track with the same id and the same targets hash ("none") inherits another track's envelope/limiter state.
- **Evidence**:
```python
# cache_cleanup.py: only streamlined manager, delete_chunk_files, mastering-target cache, artwork, .25d
grep -rn "\.clear_cache()" --include=*.py -> mastering_target_service.py:240, config/startup/shutdown.py:117
```
- **Impact**: Minor audible non-determinism on re-render after a clear; stale warm state surviving a library reset. Not data corruption.
- **Suggested Fix**: Have `clear_track_caches` drop that track's entries and `clear_all_caches` call `processor_factory.clear_cache()` (leased/in-use instances are not in the cache, so this is safe).

### D10-06: No single-flight for Tier-3 fingerprint extraction: concurrent processors for one track each decode and analyse it
- **Severity**: LOW
- **Dimension**: Caching & Invalidation (concurrent computers of the same key)
- **Location**: `auralis-web/backend/core/mastering_target_service.py:106-178`, `auralis-web/backend/core/chunk_processor_init.py:148-162`, `auralis-web/backend/core/stream_enhanced_lifecycle.py:108-126`
- **Status**: NEW
- **Description**: Every play/seek builds a new `ChunkedAudioProcessor` in a thread, which runs `load_fingerprint(extract_if_missing=True)`. The service lock covers only the dict, not the compute, and the analysis gate admits jobs by memory budget (40 minutes), not by identity. A seek (or the 90 s init-timeout retry) while the first init thread is already past the gate, or the library fingerprint queue working the same unscanned track, starts a second whole-track decode and analysis of the same file. `should_stop` only aborts a job still waiting on the gate. Results are identical and the `.25d` write is atomic, so nothing corrupts; the cost is duplicate CPU/RAM (~85 MB per minute of audio per job) on the interactive path, lengthening first-chunk latency and risking `PROCESSOR_INIT_TIMEOUT`.
- **Evidence**:
```python
# mastering_target_service.py:157-175 -- no per-(track,signature) in-flight registry
file_result = self.load_fingerprint_from_file(filepath)
...
if extract_if_missing:
    extract_result = self.extract_fingerprint_from_audio(filepath, save_to_file=save_extracted, should_stop=should_stop)
```
- **Impact**: Performance only; most visible on first play of a freshly scanned library while the background queue is still running.
- **Suggested Fix**: Add a per-(track_id, signature) single-flight (like `chunk_single_flight.py`) so followers wait for and reuse the leader's result, re-checking the cache/Tier 2 after the wait.

### D11-03: A WS `seek` / `play_*` position written as a huge integer raises OverflowError and is reported as `internal_error`
- **Severity**: LOW
- **Dimension**: Seek & Buffering (seek past end / invalid position)
- **Location**: `auralis-web/backend/ws_handlers/seek_command.py:42`, `auralis-web/backend/ws_handlers/enhancement_params.py:119-124`
- **Status**: NEW (closed #6130/#6312 are `AudioPlayer.seek` in the engine; #5973 and #3317 cover non-numeric and NaN/inf, not an int too large for float)
- **Description**: `handle_seek` validates with `isinstance(position, (int, float)) and math.isfinite(position)`. JSON integers are unbounded Python ints and `math.isfinite(10**400)` raises `OverflowError` rather than returning False, so the intended `invalid_seek_position` reply is never reached. `parse_play_request` has the same hole: `float(10**400)` raises `OverflowError`, which its `except (TypeError, ValueError)` does not catch. The dispatch loop catches it generically.
- **Evidence**:
  ```python
  # seek_command.py:42
  if not isinstance(position, (int, float)) or not math.isfinite(position) or position < 0:
  # enhancement_params.py:119
  start_position = float(data.get("start_position", 0.0) or 0.0)
  ```
  Run with `{"position": 1<400 zeros>}`: `handle_seek` raised `OverflowError int too large to convert to float`; `parse_play_request` with `start_position` the same.
- **Impact**: The client gets `internal_error: Command failed` instead of a typed validation error, and the server logs an ERROR with a full traceback for a client-supplied value (one frame per attempt, bounded only by the rate limiter). Connection survives (#4771), so this is cosmetic/log-noise, but it is the "seek past end / out-of-range" branch the validation was written to cover.
- **Suggested Fix**: Convert once inside a try (`float(position)` catching `OverflowError`), or reject ints above a sane bound (e.g. `abs(position) > 1e9`) before `isfinite`; reuse the same helper in `parse_play_request`.

### LOW (Existing open issues, not to be re-filed)

### D2-05: Paused streams hold a global stream slot and processor indefinitely (pause gate unbounded)
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_gates.py:62-65`, `core/stream_enhanced_lifecycle.py` (semaphore held until `finally`), `core/stream_normal.py:71-81`
- **Status**: Existing: #6171 (OPEN; the `ws_max_size`, connection-cap and per-IP-sweep parts of that issue are fixed in code, the "paused streams hold global slots" part is not)
- **Description**: `wait_for_stream_gates` awaits `pause_evt.wait()` with no bound while the stream still owns a `_global_stream_semaphore` permit, a leased `HybridProcessor`, its look-ahead result and a proactive-buffer task. `MAX_CONCURRENT_STREAMS` is 10 and `WS_MAX_CONNECTIONS` 16, so enough paused streams make every new play fail with "Server busy" after 5 s.
- **Evidence**:
  ```python
  pause_evt = stream_pause_events.get(key)
  if pause_evt is not None:
      await pause_evt.wait()
  ```
- **Impact**: Capacity starvation by idle paused streams; single-user desktop makes it unlikely.
- **Suggested Fix**: As tracked in #6171 (release the permit/processor while paused, or time-box the pause).
- **Merged**: Also reported by: D8-08 (same open issue #6171; merged).

### D11-05: Seek inherits stale `active_stream_settings` after a `play_normal`
- **Severity**: LOW
- **Dimension**: Seek & Buffering (seek parameter resolution)
- **Location**: `auralis-web/backend/ws_handlers/seek_command.py:68`, `auralis-web/backend/ws_handlers/playback_commands.py:187-225` (`handle_play_normal` never writes the snapshot)
- **Status**: Existing: #5076 (still present: `handle_play_normal` does not record `active_stream_settings`, and `_cancel_prior_task` is called with `clear_settings=False`)
- **Description / Impact**: Seek reads the connection's snapshot from an earlier `play_enhanced` after a later `play_normal` replaced it. Not re-reported in detail.

## Relationships

- **Lease pairing (D4-01)**: one root cause behind five per-dimension reports. `ChunkedAudioProcessor.__init__` takes the lease (`chunk_processor_init.py`), and only streams that reach their `finally` return it. D10-04 (cache clear never reaches the warm-processor tier) is the other half of the same lifecycle: leaked processors are also unreachable by Clear Cache.
- **Fingerprint-extraction at construction (#6336/#6338)** spawned D2-01 (stale "queued / standard mastering" message), D7-06 (extraction failure silently falls back to per-chunk mastering) and D10-06 (no single-flight for concurrent extraction of one track). D10-02 (stale Tier-1 fingerprint cached under the new signature) feeds the same plan.
- **Chunk cache integrity**: D10-01 (fallback audio persisted), D7-01 (write failure fails the chunk) and D3-02 (unreachable second render pipeline that bypasses single-flight) all concern the `chunk_render_miss.py` / `chunk_streaming.py` seam. Fix D10-01 and D7-01 together so degraded output is neither cached nor allowed to fail a good render.
- **Lossy-container geometry**: D3-01 (empty last chunk) and D11-01 (VBR MP3 probe duration) share the cause that chunk geometry comes from the container probe while the decoder holds a different number of samples. A single "measured length" feed-back into `chunk_metadata.py` would address both.
- **Thumbnail cache**: D8-01 (per-miss directory walks) is the same code as the FIFO/delete-while-serving defect; one rework of `prune_thumbnail_cache` covers both.
- **Throttled-logging and fix follow-through**: D6-01 and D6-03 are the remaining holes in #6188; D2-02 is the site #6092 missed; D1-05 is the rest of #6210; D1-02 and D5-02 are regressions of #5891 and #6162 where a fix left a named sibling unchanged.
- **WebSocket validation**: D5-02, D5-03 and D11-03 are all in `seek_command.py` / `enhancement_params.py` input validation and can be fixed in one pass (shared `TrackId` bounds, `command` on rejections, finite and bounded position).
- **Test isolation**: D9-01 is the one place a test can mutate the developer's real `~/.auralis/library.db`; D1-01 and D9-06 are examples of paths whose behaviour is not asserted.

## Prioritized Fix Order

1. **D5-01**: a core REST endpoint returns 500 for the normal playing state; one-line-class fix with a reproduction.
2. **D4-01**: leak of warm processors on every uncached recommendation; cheap to fix with try/finally and closes five reports.
3. **D10-01 and D7-01**: audio-integrity: stop caching degraded fallbacks and stop failing a good render on a cache-write error.
4. **D10-02**: stale fingerprint can drive the wrong mastering plan after a retag or rescan.
5. **D3-01 and D11-01**: last-chunk failure and VBR MP3 geometry; both user-audible on real files.
6. **D6-02**: startup aborts on every launch from a corrupted marker file.
7. **D7-02**: database failure reported as success to the user.
8. **D1-01**: scan-folder reset leaves orphaned tracks (sibling of already-fixed #5467/#5523).
9. **D9-01**: test can write to the developer's real library.
10. **D8-01**: quadratic first-load thumbnail cost.
11. **Regressions D1-02, D5-02**: small, already-triaged scope.
12. **Remaining LOW findings**: batch by theme: WebSocket validation, logging throttling, schema consolidation, test hygiene, documentation drift.
