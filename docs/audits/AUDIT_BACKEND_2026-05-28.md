# Backend Audit — 2026-05-28

**Scope**: FastAPI backend (`auralis-web/backend/`) — 18 routers, WebSocket streaming, chunked processing, processing engine, schemas, middleware/config, error handling, performance, test coverage.

**Dedup baseline**: 200 GitHub issues (185 closed, 15 open) at scan time; prior backend audits in `docs/audits/AUDIT_BACKEND_*.md`; local snapshots in `.claude/issues/`.

**Depth**: deep · **Limit**: unlimited

---

## Executive Summary

**131 findings** across 9 dimensions:

| Severity | Count |
|---|---|
| **CRITICAL** | 1 |
| **HIGH** | 16 |
| **MEDIUM** | 42 |
| **LOW** | 72 |
| **TOTAL** | **131** |

**Status breakdown** (parsed from each finding's `Status` line):

- **NEW**: 105
- **Existing (open issue)**: 9 — skipped per the dedup rules
- **Regression of closed**: 28

### Per-dimension counts

| # | Dimension | CRIT | HIGH | MED | LOW | Total |
|---|---|---|---|---|---|---|
| 1 | Route Handlers | 0 | 2 | 8 | 11 | 21 |
| 2 | WebSocket Streaming | 0 | 1 | 3 | 13 | 17 |
| 3 | Chunked Processing | 1 | 1 | 4 | 6 | 12 |
| 4 | Processing Engine | 0 | 1 | 2 | 7 | 10 |
| 5 | Schema Consistency | 0 | 1 | 5 | 6 | 12 |
| 6 | Middleware & Config | 0 | 3 | 4 | 11 | 18 |
| 7 | Error Handling | 0 | 2 | 7 | 7 | 16 |
| 8 | Performance | 0 | 3 | 5 | 6 | 14 |
| 9 | Test Coverage | 0 | 2 | 4 | 5 | 11 |

### Key themes

1. **One CRITICAL audio-integrity bug**: `extract_chunk_segment` slice offset duplicates 5 s of audio at every 30 s chunk boundary on enhanced streams (BE-CP-1). Regression of #2750 / commit c71c8842 — the prior fix shortened the duplicate window but never corrected the slice offset. Confirmed by direct numpy simulation.
2. **`str(e)` leak siblings**: prior fixes (#2169, #2608, #2667, #3331, #3543) plugged the leak inside controllers but missed wrapper sites in `routers/system.py`, `routers/files.py`, `services/library_auto_scanner.py`, `monitoring/metrics_collector.py`, and other locations — 5+ HIGH/MEDIUM findings spread across dims 1, 6, 7.
3. **Shared mutable state without lock**: BE-PE-1 (HybridProcessor flag race), BE-MW-1 (id(ws) reuse on rate limiter — regression of #3181), BE-CP-2 (trim_context cap on short tracks). Same root cause — shared object accessed by concurrent paths without synchronisation.
4. **Lifespan rollback drift**: BE-MW-3 (regression of #3540/BE-NEW-82) — rollback omits `fingerprint_queue`, `auto_scanner`, `ondemand_fingerprint_queue` and contains dead keys never set.
5. **Schema/contract drift between backend ↔ frontend**: 12 findings in dim 5 — `track_loaded` WS contract drift (BE-SCH-1, regression of #2479's incomplete fix), `PlayerState` snake-case/camelCase mixing, volume 0-1 vs 0-100, `JobStatusResponse.status: str` not an enum, ~25 path-int params lacking `ge=1`, raw `dict[str, Any]` returns on 7 routers.
6. **Frontend → backend route gap**: BE-RH-2 (HIGH) — `useQueueHistory` calls 3-4 endpoints (`/api/player/queue/history`, `/api/player/queue/undo`) that have no backend route; every page mount and undo silently 404s.
7. **Event-loop blocking sync calls survived the 2025-Q1 offload sweep**: BE-RH-1 (`webm_streaming.stream_chunk` direct sync DSP call), BE-PF-1 (`player.load_track` sync repo call on the #1-click path), BE-PF-2 (unbounded `FingerprintQueue`).
8. **Several closed issues re-opened by lack of code-fix**: dim 8 surfaced #3558 (artwork_downloader), #3560 (playlist batch-add), #3561 (metadata batch N+1), partial #3530 (factory pop semantics) — issues closed without diffs; code still matches the originally-flagged pattern.
9. **No regression of #3185, #3219, #2106, #2393, #2425, #2430, #2156, #2164, #2866, #3187, #3503, #3509, #3522, #3773, #3787, #3531, #3515, #3733, #2752, #2738** — verified intact by dim 2/4/8 spot-checks.

---

## Route Coverage Matrix (from Dim 9)

| Router (file) | Primary test file(s) | Rating |
|---|---|---|
| `albums.py` (275 LOC) | `test_albums_api.py` | Good |
| `artists.py` (242 LOC) | `test_artists_api.py` | Good |
| `artwork.py` (336 LOC) | `test_artwork_download.py`, `test_artwork_security.py`, `test_artwork_management.py`, `test_artwork_url_fix.py`, `test_artwork_path_validation.py`, `test_artwork_integration.py`, `test_track_artwork_field_naming.py` | Good |
| `cache_streamlined.py` (207 LOC) | `test_cache_streamlined_api.py`, `test_cache_endpoints.py`, `test_streamlined_cache.py`, `test_cache_integration_b2.py` | Good |
| `dependencies.py` (218 LOC) | `test_dependencies.py` | Good |
| `enhancement.py` (573 LOC) | `test_enhancement_api.py`, `test_processing_parameters.py` | Good |
| `errors.py` (103 LOC) | `test_error_responses.py`, `test_error_handling.py` | Good |
| `files.py` (263 LOC) | `test_files_api.py`, `test_no_duplicate_scan_route.py` | Good |
| `library.py` (899 LOC) | `test_library_api_comprehensive.py`, `test_library_reset.py`, `test_library_boundaries.py`, `test_library_pagination_invariants.py` | Good |
| `metadata.py` (382 LOC) | `test_metadata.py`, `test_metadata_api.py`, `test_metadata_batch_atomicity.py`, `test_metadata_operations.py` | Good |
| `pagination.py` (121 LOC) | `test_pagination.py` | Good |
| `player.py` (611 LOC) | `test_player_api_comprehensive.py`, `test_queue_endpoints.py`, `test_state_manager.py` | Good |
| `playlists.py` (374 LOC) | `test_playlist_integration.py`, `test_playlist_operations.py`, `test_main_api.py::TestPlaylistEndpoints`, `test_api_endpoint_integration.py` | Good |
| `processing_api.py` (528 LOC) | `test_processing_api.py` (mocks engine — never exercises real `process_job`) | **Partial** (Misleading: see BE-TC-2, BE-TC-3) |
| `serializers.py` (296 LOC) | `test_serializers.py` | Good |
| `settings.py` (144 LOC) | `test_main_api.py::TestSettingsEndpoints` | Good |
| `similarity.py` (624 LOC) | `test_similarity_api.py`, `test_similarity_api_new.py`, `test_similarity_error_redaction.py` | Good |
| `system.py` (890 LOC, WS handler) | `test_system_api.py`, `test_websocket_*.py` (8 of 14 WS msg types tested via real handler) | **Partial** (BE-TC-4) |
| `webm_streaming.py` (498 LOC) | `test_webm_streaming_api.py`, `test_streaming_timeouts.py`, `test_chunked_processor*.py`, `test_audio_stream_*.py` | Good |

---

## Cross-dimension overlap (files touched by ≥2 dimensions)

Files surfaced by multiple audit dimensions — often indicate shared root causes worth fixing together.

| File | # findings | Dimensions |
|---|---|---|
| `auralis-web/backend/routers/system.py` | 18 | D1, D2, D6, D7, D8, D9 |
| `auralis-web/backend/core/audio_stream_controller.py` | 13 | D2, D3, D5, D7, D8 |
| `auralis-web/backend/routers/files.py` | 5 | D1, D7, D9 |
| `auralis-web/backend/routers/library.py` | 4 | D1, D7 |
| `auralis-web/backend/routers/processing_api.py` | 4 | D1, D4, D5, D9 |
| `auralis-web/backend/config/globals.py` | 4 | D2, D6 |
| `auralis-web/backend/core/chunked_processor.py` | 4 | D3, D4 |
| `auralis-web/backend/core/processing_engine.py` | 4 | D4, D7, D8 |
| `auralis-web/backend/routers/player.py` | 3 | D1, D8 |
| `auralis-web/backend/routers/metadata.py` | 3 | D1, D7, D8 |
| `auralis-web/backend/websocket/websocket_security.py` | 3 | D2, D6 |
| `auralis-web/backend/config/startup.py` | 3 | D6, D8 |
| `auralis-web/backend/services/library_auto_scanner.py` | 3 | D7, D9 |
| `auralis-web/backend/routers/webm_streaming.py` | 2 | D1, D2 |
| `auralis-web/backend/routers/settings.py` | 2 | D1, D5 |
| `auralis-web/backend/routers/playlists.py` | 2 | D1, D8 |
| `auralis-web/backend/routers/enhancement.py` | 2 | D1, D4 |
| `auralis-web/backend/schemas.py` | 2 | D2, D9 |
| `auralis-web/backend/encoding/webm_encoder.py` | 2 | D2, D7 |
| `auralis-web/backend/core/level_manager.py` | 2 | D3, D4 |

---

## Findings

Grouped by severity (CRITICAL → LOW). Each finding's original location, status, evidence, impact, and suggested fix is preserved verbatim from its dimension report.


## CRITICAL (1)

> _Dim 3 — Chunked Processing_

### BE-CP-1: `extract_chunk_segment` middle/last slice offset is wrong — 5 s of audio duplicated at every chunk 0 → 1 boundary
- **Severity**: CRITICAL
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:207-214` (middle chunks), `194-205` (last chunk), in conjunction with `chunked_processor.py:567-577` and the post-`trim_context` invariant at `chunked_processor.py:505`.
- **Status**: NEW (regression of #2750 / commit `c71c8842` that was thought to fix the same symptom — the c71c8842 fix shortened the duplicate from 5 s to a still-5 s window because the slice offset was never corrected)
- **Description**: After `ChunkBoundaryManager.trim_context()` (`chunk_boundaries.py:192-272`) strips the 5 s of pre-context, the post-trim buffer represents source-time span `[chunk_idx * CHUNK_INTERVAL, chunk_idx * CHUNK_INTERVAL + CHUNK_DURATION]` — i.e. 15 s starting at `chunk_idx * 10 s`. For middle chunks `extract_chunk_segment` slices `processed_chunk[:CHUNK_INTERVAL * sr]` (lines 209-210), which extracts the **first 10 s of that buffer** = source `[chunk_idx * 10, chunk_idx * 10 + 10]`. For chunk 1 this is source [10 s, 20 s]. Chunk 0 (line 188) emits the full CHUNK_DURATION = 15 s = source [0, 15]. After concatenation the listener hears:
  - output [0 s, 15 s] = source [0, 15]
  - output [15 s, 25 s] = source [10, 20]
  → a **5-second backward jump** at output t=15 s, with source [10, 15] played twice.
  Chunks 2+ are correct relative to each other (chunk 2 emits source [20, 30], adjacent to chunk 1's source [10, 20] only because the bug is symmetric), but every track sees the chunk-0 → chunk-1 5 s duplication. The same offset bug applies to the `is_last` branch (line 201): the last chunk slices from offset 0 instead of `OVERLAP_DURATION * sr`, dropping the OVERLAP_DURATION of valid audio at the end.
- **Evidence**: Direct simulation with a 60 s ramp signal at 44.1 kHz:
  ```
  Chunk 0: source[0, 14],  dur=15.00 s  → emits [0,15]
  Chunk 1: source[10, 19], dur=10.00 s  ← starts at source 10 instead of 15
  Chunk 2: source[20, 29], dur=10.00 s
  ...
  Concatenated: 65.00 s (source is 60 s)
  Backward jumps detected: 1
    At output t=15.000 s: source jumped from 14 to 10
  ```
  The pre-refactor `_extract_chunk_segment` (commit `4825d4ff~`, in `chunked_processor.py:1086,1101,1108`) used `processed_chunk[overlap_samples : overlap_samples + expected_samples]` — but it operated on the NON-trimmed buffer (source [5, 30] for chunk 1), where that slice was `[5 s : 15 s]` = source [10, 20] (same bug, just expressed differently). When the refactor (4825d4ff) moved the slice into `chunk_operations.py` AND `chunked_processor.py:505` started calling `trim_context()` first, the slice was changed to `[:expected_samples]` to compensate for the already-removed leading 5 s, but the offset arithmetic was wrong: removing 5 s from the buffer head means the slice should now start at offset 5 s (= `OVERLAP_DURATION * sr` into the trimmed buffer, i.e. `[5 s : 15 s]` of the 15 s trimmed buffer = source [15, 25]) — not at offset 0.
  
  The test that should detect this (`tests/backend/test_chunked_processor_invariants.py:344-383 test_processed_chunks_concatenate_to_correct_duration`) has a 50 % tolerance on total duration and explicitly notes "With overlaps, sum of raw chunks will exceed original" — masking the bug. No cross-chunk audio-content continuity test exists.
- **Impact**: Every multi-chunk enhanced-stream playback (any track ≥ 15 s) repeats 5 s of audio at output t=15 s. On a typical track this is one of the most audible parts (post-intro). Combined with `_smooth_level_transition` per-chunk static gain (BE-CP-7), the boundary can produce both a level step and a content jump. The error is plainly audible to humans (5 s is not a click — it's "the song skips back 5 s once at the start"). Blast radius: 100 % of enhanced streams, every play. The frontend `_send_pcm_chunk` does not realign or trim, so the duplicate reaches the browser PCM buffer and is played.
- **Siblings**: The original `_extract_chunk_segment` had the same conceptual error pre-refactor; the chunk-content tests (`test_processing_preserves_sample_count_per_chunk`, `test_processed_chunks_concatenate_to_correct_duration`) test counts and durations but never sample CONTENT alignment — siblings of #2519's sample-count-only invariant gap.
- **Suggested Fix**: Either (a) in `extract_chunk_segment` middle branch use `processed_chunk[OVERLAP_DURATION*sr : OVERLAP_DURATION*sr + CHUNK_INTERVAL*sr]` and `is_last` branch `processed_chunk[OVERLAP_DURATION*sr : OVERLAP_DURATION*sr + remaining_samples]`, OR (b) make chunk 0 emit only `CHUNK_INTERVAL = 10 s` (= source [0, 10]) and middle chunks keep the `[:CHUNK_INTERVAL*sr]` slice. Option (a) is the historically-correct intent (see commit `c71c8842` message: "chunks 1+: 10s skipping 5s overlap"). Add a regression test that synthesises a ramp signal, processes via `ChunkedAudioProcessor`, concatenates the saved chunks, and asserts the output samples are strictly monotonically non-decreasing within ±1 sample (catches any backward jump).

---


## HIGH (16)

> _Dim 1 — Route Handlers_

### BE-RH-1: `webm_streaming.stream_chunk` calls sync DSP `get_wav_chunk_path` on the event loop
- **Severity**: HIGH
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/webm_streaming.py:354`
- **Status**: NEW
- **Description**: The handler instantiates `ChunkedAudioProcessor` correctly via `asyncio.to_thread` (lines 335-344) but then calls `processor.get_wav_chunk_path(chunk_idx)` **synchronously** on the event loop. `get_wav_chunk_path` (`core/chunked_processor.py:776`) runs the full DSP pipeline — `_sync_cache_lock` acquire, `_process_chunk_core` (HybridProcessor.process), `ChunkOperations.extract_chunk_segment`, then write-to-disk — typically 200 ms-2 s of CPU-bound work. The subsequent `Path(chunk_path).read_bytes` is correctly wrapped in `asyncio.to_thread`, hiding the violation.
- **Evidence**:
  ```python
  # webm_streaming.py:335-361
  processor = await asyncio.wait_for(
      asyncio.to_thread(chunked_audio_processor_class, ...),  # OK
      timeout=30.0
  )
  chunk_path = processor.get_wav_chunk_path(chunk_idx)        # ← runs DSP on the event loop
  wav_bytes = await asyncio.wait_for(
      asyncio.to_thread(Path(chunk_path).read_bytes),         # OK
      timeout=10.0
  )
  ```
  Compare with `routers/enhancement.py:155` which correctly wraps the same method: `wav_chunk_path = await asyncio.to_thread(processor.get_wav_chunk_path, chunk_idx)`.
- **Impact**: Every cache-miss chunk request blocks the FastAPI loop for the duration of one DSP pass — backend cannot serve any other REST/WS message during that window. With ~10 s chunk intervals and any concurrent listener whose buffer is filling, the loop stalls visibly. Hot path: enhanced playback over `/api/stream/{track_id}/chunk/{chunk_idx}` on cache miss.
- **Siblings**: Pattern matches BE-NEW-71 (`AudioProcessingPipeline.process_audio_async` async-in-name-only). The correctly-wrapped sibling at `enhancement.py:155` proves the fix shape is known.
- **Suggested Fix**: `chunk_path = await asyncio.to_thread(processor.get_wav_chunk_path, chunk_idx)`. Add a regression test (or test fixture sleep) that asserts the call goes through `asyncio.to_thread` (mock the executor).

---

> _Dim 1 — Route Handlers_

### BE-RH-2: `useQueueHistory` calls 3 backend endpoints that don't exist — 404 on every page load and every undo
- **Severity**: HIGH
- **Dimension**: Route Handlers (Missing endpoints)
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueHistory.ts:159, 192, 240, 277` — `auralis-web/backend/routers/player.py` (no matching routes)
- **Status**: NEW
- **Description**: The hook actively calls four endpoints that have no implementation in any backend router:
  - `GET /api/player/queue/history` (on mount, line 159)
  - `POST /api/player/queue/history` (record operation, line 192)
  - `POST /api/player/queue/undo` (undo, line 240)
  - `DELETE /api/player/queue/history` (clear, line 277)
  `grep -rn "/api/player/queue/history\|/api/player/queue/undo" auralis-web/backend/` returns no matches. The frontend `recordOperation` is called from `usePlaybackQueue` on every queue mutation. Every page that mounts `useQueueHistory` (any view using `usePlaybackQueue`) fires the initial GET, which now hits the FastAPI 404 handler.
- **Evidence**:
  ```ts
  // useQueueHistory.ts:153-171
  useEffect(() => {
    const fetchInitialHistory = async () => {
      try {
        const response = await get<{ history: HistoryEntry[]; count: number }>('/api/player/queue/history');
        ...
      } catch (err) {
        // Silently fail - history is optional
        console.warn('Failed to fetch queue history:', err);
      }
    };
    fetchInitialHistory();
  }, [get]);
  ```
  The `console.warn` masks the 404 in dev tools so the bug is silent in production.
- **Impact**:
  - Every queue undo invocation (`undo()` button) raises an error 100% of the time.
  - Every queue mutation (`recordOperation` from `usePlaybackQueue`) hits 404 and throws — caught by the hook's outer `try`, but the error propagates to the awaiter and may break mutation flows that await it.
  - Every page mount that includes the queue hook generates a noisy 404 in server logs.
  - Net effect: queue-history UI is non-functional but visually present, and clear-history/undo are dead buttons.
- **Siblings**: Same pattern as BE-NEW-33 (player/load no-op) — frontend code paper-trail that the feature exists, no backend implementation.
- **Suggested Fix**: Either (a) implement the four routes against a `QueueHistoryRepository` (the `QueueHistory` ORM model already exists at `auralis/library/models/core.py` per `library.py:856`), (b) gut the hook and replace with a no-op stub, or (c) feature-flag the hook so it doesn't fire when the feature is unavailable. Option (a) recommended — the model is half-built and visible in the reset transaction.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-1: Seek hands off to a new streaming task before the old one releases the websocket — concurrent senders interleave chunk frames
- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:680-779`
- **Status**: NEW
- **Description**: The `seek` handler cancels the old streaming task and then awaits its termination with a hard timeout of 100 ms via `asyncio.wait_for(asyncio.shield(old_task), timeout=0.1)`. If the old task is in the middle of DSP work inside `asyncio.to_thread(processor.process_chunk_safe, ...)` (which routinely runs 200 ms–2 s for an enhanced chunk), the cancellation cannot interrupt the blocking thread — the timeout fires, the exception is swallowed, and the seek handler immediately calls `_send_pcm_chunk` from the NEW task while the OLD task is still alive and resumes by sending its already-computed chunk over the same websocket. The two producers emit `audio_chunk_meta` + binary frames concurrently on a single connection, producing an interleaved stream the frontend cannot parse correctly (the `WebSocketContext` pairs each binary frame with the most-recent `audio_chunk_meta`, so old-task PCM is mis-tagged with new-task metadata — wrong `chunk_index`, wrong `seq`, wrong `stream_type`).
- **Evidence**:
  ```python
  if old_task and not old_task.done():
      old_task.cancel()
      try:
          await asyncio.wait_for(asyncio.shield(old_task), timeout=0.1)
      except (asyncio.CancelledError, TimeoutError):
          pass
  # ... seek_started send ...
  async with _active_streaming_tasks_lock:
      ...
      task = asyncio.create_task(stream_from_position())  # new sender starts
  ```
  The shield prevents the wait_for-induced cancellation from propagating, so on timeout the old task continues running. The play_enhanced/play_normal paths use `await old_task` (no timeout) precisely to avoid this race; seek is the outlier.
- **Impact**: Rapid seek presses (scrub UI, A/B bouncing, drag-seek) produce garbled audio because the old DSP chunk lands after the new stream has begun. The frontend's PCM stream buffer receives a packet labeled `chunk_index=N+5` (new) but containing samples from the old track-position; downstream crossfade/sequence assertions in `usePlayEnhanced` (the "out-of-sequence chunk" warning at line 443-447) fires but cannot recover the lost samples. Result: clicks, dropouts, or wrong-position audio for the first few seconds after every fast seek.
- **Siblings**: None — `play_enhanced` (lines 438-446) and `play_normal` (lines 535-543) use unbounded `await old_task`; only seek diverges.
- **Suggested Fix**: Drop the timeout/shield: `await old_task` unconditionally outside the lock (the lock is already released at line 680, so there is no deadlock risk in the seek path). If a hard upper bound is needed for UX, raise it to a value larger than the DSP envelope (~3 s) and ensure the new task is NOT registered until the old one actually exits — e.g. gate the new `create_task` on a `tasks_settled` event or a try/finally check of `old_task.done()`.

---

> _Dim 3 — Chunked Processing_

### BE-CP-2: `ChunkBoundaryManager.trim_context` `max_trim_fraction=0.25` cap leaves pre-context in the chunk for short tracks → last chunk emits the wrong audio range, final seconds of the track silently dropped
- **Severity**: HIGH
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:192-272` (`trim_context`); `chunk_operations.py:194-205` (`extract_chunk_segment` last-chunk branch)
- **Status**: NEW
- **Description**: `trim_context` requests to remove `CONTEXT_DURATION * sr = 5 * 44100 = 220500` samples from each side. The safety cap `actual_trim_start = min(trim_start_samples, max_trim_samples)` with `max_trim_samples = int(chunk_length * max_trim_fraction)` (default 0.25) silently REDUCES the trim when the loaded chunk is short. For any track ≤ ~20 s the loaded chunk for the last index is `< 20 s` (because `load_end` is capped at `total_duration`), so `max_trim_samples < context_samples` and the leading 5 s of CONTEXT remain in the buffer. `extract_chunk_segment` then slices `[:remaining_duration*sr]` from this offset-wrong buffer, returning source content from completely the wrong time range. The track's final seconds are LOST and earlier content is duplicated.
- **Evidence**: Direct simulation, 12 s track at 44.1 kHz:
  ```
  Chunk 1 is_last=True:
    loaded src[5, 12], length 7 s, max_trim 1.75 s
    trim_start_req = 5 s, capped to 1.75 s
    trimmed source range: [6.75, 12], 5.25 s
    extract takes first remaining_duration = 2 s
    → emits source [6.75, 8.75]
    intended: source [10, 12]
  ```
  Output for a 12 s track: chunk 0 emits source [0, 9] (its own 0.25 cap clipping), chunk 1 emits source [6.75, 8.75]. **Source [8.75, 12] is lost entirely** and source [6.75, 8.75] duplicates earlier audio. The warning log at `chunk_boundaries.py:236-238` does fire ("start trim capped by max_trim_fraction=0.25"), but downstream code does not adjust.
- **Impact**: Any track ≤ ~20 s — including most podcasts/voice memos, audio jingles, sound effects, and audio editing previews — has its final seconds dropped on enhanced playback. The user hears the track ending several seconds before the actual file end. Blast radius: 100 % of short tracks. Combined with BE-CP-1 (which already corrupts the chunk-0/1 boundary), a 12 s track produces output of length ~11 s with the wrong content distribution.
- **Siblings**: Same root cause family as BE-CP-1 (offset-arithmetic confusion between trimmed/non-trimmed buffer perspectives). No prior issue.
- **Suggested Fix**: Two parts. (1) When `trim_context` caps the trim, mark the buffer as "trim-aborted" and have `extract_chunk_segment` use a different slice offset based on actual trim performed. The simplest correct fix: have `trim_context` raise / signal when the cap would change the slice semantics, and short-circuit short tracks to "skip enhancement, stream original" (since DSP can't do anything meaningful with <15 s of audio anyway). (2) Add a single-chunk test (`total_duration < 15 s`) and a 2-chunk short-track test (`15 s < total_duration < 25 s`) to `test_chunked_processor_invariants.py` that asserts the concatenated output matches the input source by content (not just total sample count).

---

> _Dim 4 — Processing Engine_

### BE-PE-1: ChunkedAudioProcessor mutates `processor.content_analyzer.use_fingerprint_analysis` on a SHARED HybridProcessor instance outside any lock — concurrent streams of the same track race on the fingerprint-analysis flag
- **Severity**: HIGH
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/chunked_processor.py:430-462`; root cause `auralis-web/backend/core/processor_factory.py:214-225`
- **Status**: NEW (related to / regression-of #3530 + sibling of #3787)
- **Description**: `ProcessorFactory.get_or_create()` returns the cached `HybridProcessor` instance WITHOUT popping (`processor_factory.py:216-225`). Two concurrent `ChunkedAudioProcessor` instances with the same `(track_id, preset, intensity, config_hash, targets_hash)` therefore receive the SAME `HybridProcessor`. Inside `_process_chunk_with_hybrid_processor`, the chunked processor toggles `self.processor.content_analyzer.use_fingerprint_analysis = False`, calls `self.processor.process(audio_chunk)`, and restores the flag in a `finally:` block. The flag write happens OUTSIDE `_process_lock` (which `HybridProcessor.process()` acquires only for the DSP critical section). Two concurrent flows can interleave: Thread A writes False → Thread B writes True (its own setting) → Thread A enters `process()` lock → `process()` reads `use_fingerprint_analysis = True` (B's value, not A's). The fast-start path at lines 442-462 has the same shape. The same logical bug exists for `mastering_targets`-based path at lines 430-438. The #3787 fix added `_process_lock` to `process_realtime_chunk` but does NOT cover dynamic-attribute access to `content_analyzer` — that field lives on `HybridProcessor` but is mutated by external code with no lock at all.
- **Evidence**:
  ```python
  # chunked_processor.py:425-438 — race surface
  if self.mastering_targets is not None:
      # ↓↓↓ outside _process_lock; concurrent streams overwrite each other
      original_fingerprint_setting = self.processor.content_analyzer.use_fingerprint_analysis
      self.processor.content_analyzer.use_fingerprint_analysis = False
      try:
          processed_chunk = self.processor.process(audio_chunk)
      finally:
          self.processor.content_analyzer.use_fingerprint_analysis = original_fingerprint_setting

  # processor_factory.py:216-225 — shared-instance return (no pop)
  if cache_key in self._processor_cache:
      self._processor_cache.move_to_end(cache_key)
      cached = self._processor_cache[cache_key]
      return cached   # ← same instance returned to N concurrent callers
  ```
- **Impact**: Concurrent streams of the same track (A/B testing, two tabs of the same track, mid-stream seek-and-resume that creates a new ChunkedAudioProcessor before the old one is GCed) silently process with the WRONG `use_fingerprint_analysis` value for at least one chunk. Audible effects depend on what the fingerprint analysis would have done — typically slightly different EQ targets and dynamics curve. The bug is latent today because most user flows produce unique cache keys per stream (different intensities / preset switches), but it's a correctness footgun: any future "concurrent dual-stream" feature would hit it immediately. Also a regression of #3530 (the fix was closed but pop semantics were never added).
- **Siblings**: 
  - `_process_chunk_with_hybrid_processor` line 445 (fast-start path) does the same `use_fingerprint_analysis = False/True` toggle outside the lock.
  - Issue #3787 fixed `process_realtime_chunk` and 7 setters by extending `_process_lock` — but external attribute writes via `self.processor.content_analyzer.X = ...` are still unprotected.
- **Suggested Fix**: Two options, either alone is sufficient:
  1. Restore pop semantics in `ProcessorFactory.get_or_create()` and add `release_processor()` that callers must invoke in `finally:` — matches the pattern in `ProcessingEngine._get_or_create_processor` / `_return_processor` (#3201).
  2. OR: Wrap the `use_fingerprint_analysis` toggle in `with self.processor._process_lock:` at chunked_processor.py:425, 442, 445. Note `_process_lock` is an RLock so `process()`'s own acquire reentrants safely.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-1: `track_loaded` WS contract drift — backend emits `{track_id}` while spec + frontend type still declare `{track_path}`
- **Severity**: HIGH
- **Dimension**: Schema Consistency
- **Location**:
  - Backend emit: `auralis-web/backend/routers/player.py:326-329`
  - WS spec: `auralis-web/backend/WEBSOCKET_API.md:110-117`
  - Frontend type: `auralis-web/frontend/src/types/websocket.ts:184-189`
- **Status**: NEW (introduced by but not flagged in #2479 fix — that issue only addressed the path-leak)
- **Description**: The backend used to broadcast `{type: "track_loaded", data: {track_path: track.filepath}}`. PR #2479 (2026-02-20, INT-03 fix) correctly removed `track_path` to stop leaking the server filesystem path, replacing it with `data: {"track_id": track.id}` — but neither `WEBSOCKET_API.md` nor `TrackLoadedMessage` in `websocket.ts` was updated. The spec and frontend type both still declare `track_path: string`. Any future code path that reads `message.data.track_path` will get `undefined`; any future code path that reads `message.data.track_id` will fail the TS type guard because the field isn't declared.
- **Evidence**:
  ```python
  # backend/routers/player.py:326-329 — what is actually emitted today
  await connection_manager.broadcast({
      "type": "track_loaded",
      "data": {"track_id": track.id}
  })
  ```
  ```typescript
  // frontend/src/types/websocket.ts:184-189 — what the contract says
  export interface TrackLoadedMessage extends WebSocketMessage {
    type: 'track_loaded';
    data: {
      track_path: string;  // never sent — would be undefined
    };
  }
  ```
- **Impact**: No active consumer reads either field today, so impact is latent. The blast radius is the first new consumer that ships against the documented contract: a feature that wants to look up the loaded track's filepath from the WS payload (e.g., "now playing" sidebar that pre-fetches lyrics) will silently receive `undefined`. Equally, anyone who adds frontend code reading `message.data.track_id` will hit a TS error because the declared shape lacks that field. Also: `WEBSOCKET_API.md` is the API reference any new contributor or external integration consults — the doc is actively wrong.
- **Siblings**: Pattern is identical to BE-NEW-44 (`scan_time` vs `duration`) and BE-NEW-86 (`reason` vs `action`) — both filed and patched; this one was missed because the original fix (#2479) was filed under a different dimension (security/info-leak).
- **Suggested Fix**: Update `WEBSOCKET_API.md` line 114 to `"track_id": number`. Update `TrackLoadedMessage.data` in `websocket.ts:184-189` to `{ track_id: number }`. Add a comment referencing #2479 so the contract drift is explicit.

---

> _Dim 6 — Middleware & Config_

### BE-MW-1: `WebSocketRateLimiter` uses `id(websocket)` as dict key — exact reuse-unsafe pattern of #3181 not propagated
- **Severity**: HIGH
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/websocket/websocket_security.py:53, 68, 101`
- **Status**: Regression of #3181 (the original fix only patched `core/audio_stream_controller.ws_id`)
- **Description**: Issue #3181 explicitly flagged `id(websocket)` as a dict key because CPython reuses memory addresses after GC. The fix in `core/audio_stream_controller.py:192-202` introduced a UUID-based `ws_id()` helper that stores the id on the socket as `_auralis_id`. The same anti-pattern still lives in `websocket/websocket_security.py`: `self.message_log: dict[int, list[float]]` is keyed on `id(websocket)` in both `check_rate_limit()` (line 68) and `cleanup()` (line 101). When WS #1 is garbage-collected before its `cleanup()` runs (e.g. cleanup fails earlier in the finally chain), WS #2 may inherit #1's address and its existing rate-limit bucket — getting either a free pass or a pre-populated counter from the dead connection.
- **Evidence**:
  ```python
  # websocket_security.py:53
  self.message_log: dict[int, list[float]] = {}
  ...
  # check_rate_limit (line 68)
  ws_id = id(websocket)
  ...
  # cleanup (line 101)
  ws_id = id(websocket)
  if ws_id in self.message_log:
      del self.message_log[ws_id]
  ```
- **Impact**: Stale rate-limit state can be associated with a fresh WebSocket. In the worst case a new connection finds itself pre-rate-limited (false 429s) or — if cleanup wiped the entry between the two id reuses — escapes the limit entirely. Severity is HIGH because (a) #3181 was filed and "fixed" specifically for this anti-pattern, and (b) the parallel `id(websocket)` use in audio_stream_controller is what triggered #3181 originally.
- **Siblings**: `core/audio_stream_controller.ws_id` was already converted to UUID. The `_active_streaming_tasks` / `_active_streaming_track_ids` / `_stream_pause_events` / `_stream_flow_events` dicts in `routers/system.py` all key on the UUID-based `_ws_id()` correctly, so this is the only remaining instance.
- **Suggested Fix**: Replace `id(websocket)` with `ws_id(websocket)` from `core.audio_stream_controller` (importing it adds the cross-module dep, so the cleaner option is to move `ws_id` to `websocket/websocket_security.py` or a shared `websocket/_identity.py` and import from both sides). Change `dict[int, ...]` to `dict[str, ...]`.

---

> _Dim 6 — Middleware & Config_

### BE-MW-2: WebSocket per-connection rate limit is trivially bypassed by reconnecting
- **Severity**: HIGH
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/websocket/websocket_security.py:31-104` + `routers/system.py:42` (global `_rate_limiter` instance, fresh bucket per WS)
- **Status**: NEW
- **Description**: `_rate_limiter` is keyed per-WebSocket (whether by `id(ws)` per BE-MW-1 or by a future UUID). Each fresh connection gets an empty `message_log[ws_id]`. A misbehaving client that hits the 10 msg/sec cap need only close and immediately reopen the WebSocket — origin allowlist passes (same origin), `manager.connect` accepts, and the new connection starts with zero recorded messages. No per-IP fallback bucket exists, no minimum-time-between-connects backoff is enforced, and `ConnectionManager.active_connections` has no upper bound. On a localhost-only desktop a malicious local script can sustain effectively unlimited message throughput.
- **Evidence**:
  ```python
  # routers/system.py:42
  _rate_limiter = WebSocketRateLimiter(max_messages_per_second=10)
  ...
  # websocket_security.py:73-74 — bucket created from scratch on first message
  if ws_id not in self.message_log:
      self.message_log[ws_id] = []
  ```
- **Impact**: Defeats the intent of #2156 ("max 10 msg/sec per connection"). For a desktop app this is mostly a self-DoS risk, but combined with BE-MW-3 (no max-connection cap) a stuck/buggy frontend can also exhaust event-loop time by spinning up many sockets.
- **Siblings**: HTTP rate limiter is keyed on `client_ip:path` (`config/middleware.py:131-132`), which is robust because IP doesn't change across HTTP requests — but on localhost everything is `127.0.0.1` so the HTTP bucket is effectively process-wide. WS rate limit is the only per-connection limiter with bypass-on-reconnect semantics.
- **Suggested Fix**: Key `_rate_limiter` on `(client_ip, path)` for HTTP-style stability, or maintain a separate per-IP fallback bucket that survives reconnects. At minimum, add a `max_messages_per_second_per_ip` ceiling that aggregates across all current and recent connections from the same client.

---

> _Dim 6 — Middleware & Config_

### BE-MW-3: Lifespan rollback omits running background services (`fingerprint_queue`, `auto_scanner`, `ondemand_fingerprint_queue`) — partial fix of BE-NEW-82
- **Severity**: HIGH
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/startup.py:302-319` (rollback list at lines 313-318)
- **Status**: Regression of #3540 (BE-NEW-82)
- **Description**: #3540 fixed the "library_manager truthy but supporting services unset" case by nulling the dict at line 313-319. **But the rollback list only nulls eight stable-component slots and never AWAITS `.stop()` on the three background services that have already been started by the time the failure can occur.** The startup sequence is: (1) `fingerprint_queue.start()` at line 133 spawns N CPU workers; (2) `auto_scanner.start()` at line 206 spawns the scan loop task; (3) `EnhancedAudioPlayer(...)` at line 222 — this is where the most likely failures happen (audio device init, PortAudio, etc.); (4) `PlayerStateManager(manager)` at line 230. If any of (3)/(4) raise, the `except Exception` at line 302 runs the rollback for-loop — but `fingerprint_queue` and `auto_scanner` are NOT in that list. They remain non-None in `globals_dict`, still running, broadcasting messages, calling `library_manager.tracks.cleanup_missing_files` against a `library_manager` that was just rolled-back to None — instant `NoneType has no attribute 'tracks'` crash inside the auto-scanner task. Worse: the rollback list contains `'fingerprint_extractor'` and `'fingerprint_storage'`, **neither of which is ever set anywhere in `startup.py`** — dead nulls.
- **Evidence**:
  ```python
  # startup.py:313-318 — rollback list
  for _component in (
      'library_manager', 'repository_factory', 'settings_repository',
      'audio_player', 'player_state_manager',
      'fingerprint_extractor', 'fingerprint_storage',  # NEVER SET ANYWHERE
      'streamlined_cache', 'similarity_system', 'graph_builder',
  ):
      globals_dict[_component] = None
  # Missing: 'fingerprint_queue', 'auto_scanner', 'ondemand_fingerprint_queue'
  # — all of which can be running async tasks by this point.

  # startup.py:133 — fingerprint_queue.start() spawns workers
  await fingerprint_queue.start()
  # startup.py:206 — auto_scanner.start() spawns scan loop task
  await auto_scanner.start()
  # startup.py:222 — most-likely failure point
  globals_dict['audio_player'] = EnhancedAudioPlayer(...)
  ```
- **Impact**: A failure during `EnhancedAudioPlayer.__init__` or `PlayerStateManager.__init__` leaves: (a) the fingerprint workers running against `globals_dict['library_manager'] = None`, (b) the auto-scanner loop broadcasting `library_scan_started` / `scan_progress` against a frontend that's never going to receive a player state, (c) the on-demand fingerprint queue accepting work it cannot complete. The lifespan still yields (line 373) so the app comes "up" in a half-broken state; the shutdown path at lines 378-390 DOES stop these services because it checks `globals_dict['fingerprint_queue']` truthy, but only after the user closes the window — for the entire session those tasks burn CPU and corrupt state.
- **Siblings**: `ProcessingEngine.start_worker()` at lines 335-338 has the same shape — if the `spawn_background_task` returns and then later the engine fails to actually process anything, `globals_dict['processing_engine']` stays truthy and the router returns "submitted" responses for jobs that never run. `StreamlinedCacheWorker.start()` at line 362 similarly: the worker task can die after start and the cache will be silently empty.
- **Suggested Fix**: Add `fingerprint_queue`, `auto_scanner`, `ondemand_fingerprint_queue` to the rollback list AND `await .stop()` on each before nulling, wrapping each in its own try/except. Remove the dead `fingerprint_extractor` / `fingerprint_storage` entries. Consider a single explicit `_started_services: list[(name, stop_callable)]` registered as each service successfully starts, then iterated in reverse on rollback.

---

> _Dim 7 — Error Handling_

### BE-EH-1: WS `audio_stream_error` wrapper in `routers/system.py` leaks raw `str(e)` to client (3 sites)
- **Severity**: HIGH
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/system.py:419, 516, 746`
- **Status**: NEW (sibling of CLOSED #2608, #2667 — both fixed inside the controller; this is the WRAPPER above the controller)
- **Description**: When the `stream_audio`/`stream_normal`/`stream_from_position` inner coroutines raise an unhandled exception, the outer `except Exception as e:` in the WS dispatcher embeds `str(e)` directly into the `audio_stream_error.data.error` JSON field sent to the browser. `str(e)` for `OSError`/`FileNotFoundError`/`PermissionError` typically contains the full server-side absolute path of the audio file; for `sqlalchemy.exc.*` it contains SQL fragments; for `numpy.AxisError` it contains array shape internals.
- **Evidence**:
  ```python
  # routers/system.py:411-426 (also 506-523, 738-753)
  except Exception as e:
      logger.error(f"Error in streaming task: {e}", exc_info=True)
      try:
          await websocket.send_text(
              json.dumps({
                  "type": "audio_stream_error",
                  "data": {
                      "track_id": track_id,
                      "error": str(e),                # ← leak
                      "code": "STREAMING_ERROR",
                      "stream_type": "enhanced",
                  }
              })
          )
  ```
- **Impact**: Any browser JS / DevTools observer sees server file paths, DB internals, codec library detail. Same disclosure class as the fixed `_send_error` chunk-level case (#2667) — this wrapper site was never refactored to use the safe `_send_error` helper.
- **Siblings**: All three `stream_audio` / `stream_normal` / `stream_from_position` define-and-launch closures inside `routers/system.py` repeat this pattern.
- **Suggested Fix**: Replace `"error": str(e)` with a class-based summary (`f"{type(e).__name__} during streaming"`) and log full detail server-side with `exc_info=True` (already done at the line above). Alternative: route the failure through `controller._send_error(..., "Audio streaming failed")` which already does the right thing.

---

> _Dim 7 — Error Handling_

### BE-EH-2: `routers/files.py:223,240` upload response leaks raw `str(e)` per file
- **Severity**: HIGH
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/files.py:218-241`
- **Status**: NEW (sibling pattern to CLOSED #2169, #2667)
- **Description**: The bulk upload endpoint catches both inner (audio processing) and outer (any other) exceptions and emits the raw `str(e)` directly into the per-file `results[].message` JSON returned to the client.
- **Evidence**:
  ```python
  # routers/files.py:218-224
  except Exception as e:
      logger.error(f"Audio processing error for {file.filename}: {e}")
      results.append({
          "filename": file.filename or "",
          "status": "error",
          "message": f"Failed to process audio: {str(e)}"   # ← leak
      })
  # ... and routers/files.py:235-241
  except Exception as e:
      logger.error(f"Upload error for {file.filename}: {e}")
      results.append({
          "filename": file.filename or "",
          "status": "error",
          "message": str(e),                                # ← leak
      })
  ```
- **Impact**: Decode failures (libsndfile, mutagen, ffmpeg) and filesystem errors during upload echo their paths back to the browser. Worse: the outer block (235) catches `OSError`/`PermissionError` raised by `tempfile.NamedTemporaryFile` / `shutil.move` — those include the server temp-dir path and home-dir layout.
- **Siblings**: None elsewhere in the upload routers (`processing_api.py` already uses `_safe_error_message`).
- **Suggested Fix**: Emit `f"{type(e).__name__}: {category_message}"` where `category_message` reuses `core/processing_engine._safe_error_message(e)` (already available). Keep `logger.error` with `exc_info=True` for the server-side log.

---

> _Dim 8 — Performance_

### BE-PF-1: `POST /api/player/load` runs sync `library_manager.tracks.get_by_id` AND sync `audio_player.add_to_queue` (which may load audio) on the event loop
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/player.py:302, 318`
- **Status**: NEW
- **Description**: The `load_track` handler is an `async def` route on the user's #1 click path ("press play on a track"). Two sync calls run directly on the event loop before any `await asyncio.to_thread` happens:
  1. **Line 302**: `track = library_manager.tracks.get_by_id(request.track_id)` — sync SQLAlchemy session open + ORM load with `selectinload` (TrackRepository eagerly loads `artists`, `album`, `genres`).
  2. **Line 318**: `audio_player.add_to_queue(track_info)` — internally calls `load_track_from_library(track_id)` when the file manager is not yet loaded (see `auralis/player/enhanced_audio_player.py:457-484`), which performs blocking disk I/O and a SoundFile open.
- **Evidence**:
  ```python
  # routers/player.py:296-321
  audio_player = get_audio_player()
  ...
  # Security: Query track from database to validate file path
  library_manager = get_library_manager()
  track = library_manager.tracks.get_by_id(request.track_id)   # SYNC DB on event loop
  ...
  audio_player.add_to_queue(track_info)                         # may load_track_from_library → disk I/O
  success = await asyncio.to_thread(
      audio_player.load_track_from_library, request.track_id    # second load — wrapped
  )
  ```
- **Impact**: Every track click stalls the event loop for the duration of the DB query (10-100ms typical, longer under contention) and potentially for a SoundFile open (50-500ms). With concurrent listeners (multi-WS clients) or a slow disk, this serialises every other route response and every active stream chunk send. Compounds with BE-PF-7: the line-302 query is later thrown away when `load_track_from_library` re-fetches the track inside its own to_thread; the duplicate query exists only to validate the filepath, which `load_track_from_library` already does internally.
- **Siblings**: `core/streamlined_worker.py:112, 370` (sync `library_manager.tracks.get_by_id` in async `_process_priorities` / `trigger_immediate_processing`); `analysis/fingerprint_generator.py:166, 191` (sync `fingerprint_repo.get_by_track_id` / `add` in async `get_or_generate`).
- **Suggested Fix**: Wrap line 302 in `await asyncio.to_thread(library_manager.tracks.get_by_id, request.track_id)`. Drop the sync `audio_player.add_to_queue` and let `load_track_from_library` (already offloaded at 319) be the single source of truth; if queue insertion is needed before load, also offload it.

---

> _Dim 8 — Performance_

### BE-PF-2: `FingerprintQueue.enqueue()` is unbounded — `enqueue-all` on a 50,000-track library will pin all IDs in memory and `queued_set`
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/backend/analysis/fingerprint_queue.py:92-123, 87`
- **Status**: NEW
- **Description**: `FingerprintQueueState.queue` is a `deque` with no `maxlen`, and `enqueue()` always appends regardless of current size. The worker consumes one entry every full-track-decode-plus-fingerprint cycle (3-30s per track depending on length). The router endpoint `POST /api/similarity/fingerprint-queue/enqueue-all` (and any auto-trigger that fans out track IDs) can pump 50k+ IDs in milliseconds, while the single worker drains over hours. Both `self._state.queue` and `self._state.queued_set` hold the full backlog.
- **Evidence**:
  ```python
  # analysis/fingerprint_queue.py:108-123
  if track_id in self._state.queued_set:
      return False
  if track_id == self._state.processing:
      return False
  self._state.queue.append(track_id)        # no maxlen — unbounded
  self._state.queued_set.add(track_id)
  ```
  ```python
  # FingerprintQueueState (around line 42)
  # uses bare collections.deque() and a set() — no size caps anywhere
  ```
- **Impact**: At 50k track IDs × ~40 bytes (int + set bucket overhead) ≈ 2-4 MB — small in absolute terms, but the real issue is that the queue cannot apply backpressure. The auto-scan completion path (`services/library_auto_scanner.py:281-290`) and any future bulk-enqueue endpoint will silently accumulate IDs that the single sequential worker takes hours to drain. If the queue grows unboundedly through a session, the `set` size enables O(1) dedup but offers no eviction policy. There is no priority, no cancel, and no way to know "this enqueue is hopeless."
- **Siblings**: None in-tree (the other fingerprint queue, `auralis/services/fingerprint_queue.py`, is a worker pool that pulls directly from DB — no in-memory queue, so it's bounded by DB).
- **Suggested Fix**: Add a `max_size: int = 10000` constructor parameter and have `enqueue()` return `False` + log a warning when full (same shape as `processing_engine.submit_job` for `asyncio.QueueFull`). Document the bound in the docstring. Optionally surface queue depth via `/api/system/health` so operators see backpressure in the metrics dashboard.

---

> _Dim 8 — Performance_

### BE-PF-3: `StreamlinedCacheWorker._process_priorities` and `trigger_immediate_processing` call sync `library_manager.tracks.get_by_id` and construct sync `ChunkedAudioProcessor` directly on the event loop
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/streamlined_worker.py:112, 291, 370`
- **Status**: NEW
- **Description**: The worker loop runs every 1 s. Each iteration calls `self.library_manager.tracks.get_by_id(track_id)` synchronously on the event loop (line 112), then — if the chunk needs processing — `ChunkedAudioProcessor(track_id=..., filepath=..., preset=..., intensity=...)` (line 291) is constructed synchronously. The `ChunkedAudioProcessor.__init__` does sync `SoundFile` open for metadata (line 220-227), sync `MasteringTargetService.load_fingerprint` (DB query + possible 25d file read), and sync `HybridProcessor` construction via the processor factory (200-500ms CPU-bound).
- **Evidence**:
  ```python
  # core/streamlined_worker.py:104-115
  async def _process_priorities(self) -> None:
      ...
      track_id = self.cache_manager.current_track_id
      current_chunk = self.cache_manager._get_current_chunk(...)
      preset = self.cache_manager.current_preset
      intensity = self.cache_manager.intensity
      track = self.library_manager.tracks.get_by_id(track_id)   # sync DB on loop
      ...
  ```
  ```python
  # core/streamlined_worker.py:289-297
  cache_key = (track_id, preset, intensity)
  processor = self._processor_cache.get(cache_key)
  if processor is None:
      processor = ChunkedAudioProcessor(                          # sync, 200-500ms
          track_id=track_id,
          filepath=track.filepath,
          preset=preset,
          intensity=intensity,
      )
      self._processor_cache[cache_key] = processor
  ```
  ```python
  # core/streamlined_worker.py:370
  async def trigger_immediate_processing(...):
      track = self.library_manager.tracks.get_by_id(track_id)   # sync DB on loop
  ```
- **Impact**: Every 1s tick stalls the event loop for the duration of the DB query + (on cache miss) 200-500ms for processor construction. With one stream playing and `auto_mastering_enabled=True`, the loop fires every 1s and either does the lookup-only (~30ms stall) or the full miss (~500ms stall). Audio chunk sending happens through the same loop; a 500ms tick = 5 chunks worth of jitter. The two existing tests for streamlined_worker mock out the manager so this stall has never been measured.
- **Siblings**: BE-PF-4 (proactive_buffer), BE-PF-5 (FingerprintGenerator).
- **Suggested Fix**: Wrap line 112 in `await asyncio.to_thread(self.library_manager.tracks.get_by_id, track_id)`. Move the `ChunkedAudioProcessor(...)` constructor in `_process_chunk` (line 291-296) inside `await asyncio.to_thread(...)`. Same for line 370.

### MEDIUM (5)

---

> _Dim 9 — Test Coverage_

### BE-TC-1: `tests/backend/test_processing_engine.py::test_process_job_with_mocks` is a no-op — uses obsolete `Mock(result.audio)` pattern that production now rejects, all exceptions swallowed
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_processing_engine.py:220-257` (test); production it should cover: `auralis-web/backend/core/processing_engine.py:494-499` (`isinstance(result, np.ndarray)` guard)
- **Status**: NEW
- **Description**: The only "engine processes a real job" test creates a `Mock()` for `HybridProcessor.process()`'s return value and sets `mock_result.audio = np.zeros(...)`, `mock_result.lufs = -14.0`. Production code at line 494 now raises `TypeError("HybridProcessor.process() returned Mock, expected numpy.ndarray")` because the result is not a bare `np.ndarray`. The test wraps the call in `try/except Exception: pass`, so the `TypeError` is silently absorbed and the test passes without exercising a single line of the post-`process()` save / telemetry / completion flow. This is exactly the pattern that masked the original #3489 bug (the bug that took 3 releases to surface).
- **Evidence**: `mock_result = Mock(); mock_result.audio = np.zeros((1000, 2))` at line 236-237; `except Exception: pass` at lines 255-257. Production raises `TypeError` at `processing_engine.py:495-498` whenever `result` is not a real `np.ndarray`.
- **Impact**: Any future regression of the `result.audio` attribute-vs-bare-ndarray contract (or any other post-process branch — `save()` failure handling, `processor.last_content_profile` extraction, output-format/bit-depth/subtype mapping at lines 484-485, progress notification at line 510, output cleanup on failure) will not be caught. The bug-masking pattern that produced the original 100% offline-processing-broken regression (#3489) is still in the test suite verbatim.
- **Siblings**: Other tests with `try: ... except Exception: pass` swallowing real production exceptions (none of the same severity found in this scan, but the pattern is worth flagging once).
- **Suggested Fix**: Replace `mock_proc_instance.process.return_value = mock_result` with `mock_proc_instance.process.return_value = np.zeros((1000, 2), dtype=np.float32)` to match the post-#3489 contract. Drop the `try/except Exception: pass` — let the test assert `job.status == ProcessingStatus.COMPLETED` and that `mock_save` was called with the expected `subtype=PCM_16`. Add a second assertion verifying `processor.get_processing_info()` and `processor.last_content_profile` are pulled (catches regression of the telemetry side-channel extraction at lines 512-525).

---

> _Dim 9 — Test Coverage_

### BE-TC-2: `/api/processing/process` and `/upload-and-process` have no integration test that exercises a real `ProcessingEngine` + real `HybridProcessor` — all router tests mock the engine
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/processing_api.py:146-285` (`/process` and `/upload-and-process`); `tests/backend/test_processing_api.py` (only mocked); `tests/backend/test_processing_engine.py` (no-op per BE-TC-1)
- **Status**: NEW (parent finding BE-NEW-36 was closed without an integration test being added; this is a regression risk pattern)
- **Description**: Every test in `test_processing_api.py` injects `set_processing_engine(engine)` with a `Mock(spec=ProcessingEngine)`. The submit_job/get_job/cancel_job/get_queue_status methods are all `AsyncMock`/`Mock`. No test path drives a real `ProcessingEngine.process_job()` → `HybridProcessor.process()` → file save → status transition. Combined with BE-TC-1, the entire offline processing pipeline has zero end-to-end coverage. The /process route is the "primary offline mastering entry point" in production but is functionally untested at the integration level. The previously-shipped #3489 bug (everything-fails-silently) is the canonical example of what slips through.
- **Evidence**: `tests/backend/test_processing_api.py:26-67` — every test uses `mock_engine` fixture. No invocation of real `HybridProcessor.process` anywhere in the file. `grep -n "real\|integration\|HybridProcessor\|process_job" test_processing_api.py` returns only `Create a real temp file for download` (a tmp_path artefact, not real processing).
- **Impact**: A future regression of: subtype/bit-depth mapping, output-file save path, queue-full backpressure semantics, progress callbacks, content-profile telemetry extraction, output cleanup on failure, or the `isinstance(result, np.ndarray)` guard — none would be caught by CI. Functionally identical class of bug to #3489.
- **Siblings**: BE-TC-1 (the one test that purports to exercise this path is a no-op).
- **Suggested Fix**: Add `tests/integration/test_processing_engine_end_to_end.py` with one slow-marked test that: (1) generates a real short WAV via `numpy` + `soundfile`, (2) submits via `POST /api/processing/process` with a real `ProcessingEngine` (no mock — register it via `set_processing_engine`), (3) polls `/job/{id}` until status==COMPLETED, (4) downloads via `/job/{id}/download`, (5) asserts output is decodable WAV with sample count matching expected duration. One test catches the entire class of #3489 regressions.

---


## MEDIUM (42)

> _Dim 1 — Route Handlers_

### BE-RH-3: `system.py` leaks `str(e)` over WS `audio_stream_error` in 3 branches — info-disclosure parity with filed BE-27 for HTTP
- **Severity**: MEDIUM
- **Dimension**: Route Handlers (Error response hygiene)
- **Location**: `auralis-web/backend/routers/system.py:419, 516, 746`
- **Status**: NEW
- **Description**: The three streaming branches (`play_enhanced`, `play_normal`, `seek`) wrap their `stream_audio` coroutines in `except Exception as e: ... "error": str(e)` and forward the raw exception text over the WebSocket `audio_stream_error` payload. `str(e)` may contain filesystem paths, SQL fragments, dependency versions, traceback hints from FFmpeg/SoundFile, etc. — same disclosure class that BE-27 (similarity.py) and BE-NEW-42 (cache_streamlined.py) closed via the `_internal_error_response(user_message, exc)` correlation-id pattern. The HTTP surface follows that pattern now; the WS surface still does not.
- **Evidence**:
  ```python
  # system.py:411-426 (play_enhanced)
  except Exception as e:
      logger.error(f"Error in streaming task: {e}", exc_info=True)
      try:
          await websocket.send_text(json.dumps({
              "type": "audio_stream_error",
              "data": {
                  "track_id": track_id,
                  "error": str(e),              # ← raw exception text to client
                  "code": "STREAMING_ERROR",
                  "stream_type": "enhanced",
              }
          }))
      ...
  ```
  Same pattern at `system.py:516` (play_normal, code STREAMING_ERROR) and `system.py:746` (seek, code SEEK_ERROR).
- **Impact**: Any unhandled exception in the streaming pipeline (e.g. corrupt audio, missing fingerprint, repository failure, FFmpeg crash) leaks server internals to the browser. WS messages are accessible to any script running in the page; for the desktop bundle this is low blast-radius, but the pattern is also bad hygiene for the OpenAPI/log audit story.
- **Siblings**: BE-27 (similarity.py), BE-NEW-42 (cache_streamlined.py) — same anti-pattern at HTTP layer, both already closed.
- **Suggested Fix**: Extract the `similarity.py:_internal_error_response` helper to `routers/errors.py` (or a `ws_errors.py`), then call it from each WS branch to emit `{error: "<user_message>", ref: "<8-hex>"}` and log the full exception server-side. Keep `code` field for client classification.

---

> _Dim 1 — Route Handlers_

### BE-RH-4: `seek` task-handoff window — old task is popped from `_active_streaming_tasks` before being awaited; both old and new write to the same WS
- **Severity**: MEDIUM
- **Dimension**: Route Handlers (Concurrency / cancellation)
- **Location**: `auralis-web/backend/routers/system.py:677-687`
- **Status**: NEW
- **Description**: The seek branch pops the old task from `_active_streaming_tasks` *under* the lock (line 680), cancels it, and `await asyncio.wait_for(asyncio.shield(old_task), timeout=0.1)` *outside* the lock. The 100 ms budget is far too small for any DSP-in-flight chunk to actually exit — the `wait_for` times out, but `asyncio.shield` keeps the underlying task alive. Because the task was already popped, neither the new seek-task registration (line 768) nor a subsequent `stop`/disconnect cleanup will cancel it again. The old task's `finally:` self-cleanup at line 757 is guarded by `if _active_streaming_tasks.get(ws_id) is my_task` which is False (the slot now holds the new task), so the old task exits silently — but it can continue running for several seconds, sending chunks of the *prior* stream position to the WS that's already meant to be at the new position.
- **Evidence**:
  ```python
  # system.py:677-687
  async with _active_streaming_tasks_lock:
      ...
      old_task = _active_streaming_tasks.pop(ws_id, None)   # ← popped here
  if old_task and not old_task.done():
      logger.info("Cancelling existing streaming task for seek")
      old_task.cancel()
      try:
          await asyncio.wait_for(asyncio.shield(old_task), timeout=0.1)  # 100 ms only
      except (asyncio.CancelledError, TimeoutError):
          pass                                              # ← swallowed; old_task continues running
  ```
  Compare with `system.py:438-446` (`play_enhanced` task handoff) and `system.py:531-543` (`play_normal`), which both `await old_task` with no timeout — those wait for the old task to fully release before registering the new one.
- **Impact**: Following a user-initiated seek, the WS may receive interleaved chunks from old (pre-seek) and new (post-seek) streams for the duration the old task takes to hit its next `await`. With DSP chunks taking ~200-500 ms in the worst case, audible "stutter" / "double-back" is plausible. Also the old task's `_chunk_tails` / `_processor_lock` interactions are preserved (they release in the old task's own `finally`), but the new task's pause/flow events (lines 769-774) are fresh — so the old task may write through outdated events.
- **Siblings**: Resembles BE-NEW-67 (seek recovery_position discards offset). The play_* branches do it correctly — the seek branch is the asymmetric outlier.
- **Suggested Fix**: Use the same shape as `play_enhanced` — `await old_task` without `wait_for` / `shield`, and do not pop until after the await completes. If 100 ms hard cap is intentional (to keep seek latency bounded), then ALSO add a `cancel()` retry loop and/or refuse to register the new task until the old one is fully gone.

---

> _Dim 1 — Route Handlers_

### BE-RH-5: `player.load_track` calls `library_manager.tracks.get_by_id` synchronously on the event loop
- **Severity**: MEDIUM
- **Dimension**: Route Handlers (Blocking)
- **Location**: `auralis-web/backend/routers/player.py:302`
- **Status**: NEW
- **Description**: After the prior-cycle fix wired `load_track_from_library` through `asyncio.to_thread`, the same handler still does the initial DB lookup synchronously:
  ```python
  library_manager = get_library_manager()
  track = library_manager.tracks.get_by_id(request.track_id)    # ← sync on event loop
  ```
  `tracks.get_by_id` reaches the SQLAlchemy session and may block on a cold cache / lock contention. Every other handler in this router (`set_repeat_mode`, `seek`, `set_volume`, queue ops) goes through a service that uses `asyncio.to_thread` internally; `load_track` is the asymmetric outlier.
- **Impact**: Each `POST /api/player/load` call (track click in UI) briefly blocks the event loop. With pool_pre_ping enabled and a healthy session, this is usually <10 ms — but under DB lock contention or `library.db` mtime-cache miss, can spike to hundreds of ms.
- **Siblings**: Pattern matches BE-NEW-71 (sync DSP), BE-NEW-96 (QueueService sync DB calls). The fix shape is established at `library.py:113`, `metadata.py:110`, `albums.py:72`, etc.
- **Suggested Fix**: `track = await asyncio.to_thread(library_manager.tracks.get_by_id, request.track_id)`.

---

> _Dim 1 — Route Handlers_

### BE-RH-6: `PUT /api/settings` still accepts raw `dict[str, Any]` — no Pydantic validation, no OpenAPI schema, no `extra: forbid`
- **Severity**: MEDIUM
- **Dimension**: Route Handlers (Input validation)
- **Location**: `auralis-web/backend/routers/settings.py:77-95`
- **Status**: Regression of #3498 / BE-NEW-40 (filed 2026-05-25; **not fixed** — handler signature unchanged)
- **Description**: BE-NEW-40 called for a Pydantic `SettingsUpdateRequest` model with `extra: forbid`; the handler signature is still `async def update_settings(updates: dict[str, Any])`. The `_repo().update_settings(updates)` whitelisting in `SettingsRepository` is the only defense; type-coercion failures (e.g. `"volume": "loud"`) raise repository errors that the handler returns as generic 500 rather than 422. OpenAPI clients have no way to discover the settable field list.
- **Evidence**: `routers/settings.py:78`: `async def update_settings(updates: dict[str, Any]) -> dict[str, Any]:`. No `response_model=`. The whitelist lives in `auralis/library/repositories/settings_repository.py`.
- **Impact**: 422 vs 500 status divergence on bad type-coercion. OpenAPI consumers (frontend type-gen, swagger UI, third-party tooling) can't introspect the schema.
- **Siblings**: Same dead-end as `playlists.py` (no `response_model` on 8 endpoints), `library.py` (~10 endpoints), `albums.py` (4 endpoints), `artwork.py` (3 endpoints), `metadata.py` (4 endpoints).
- **Suggested Fix**: Mirror the existing `MetadataUpdateRequest(BaseModel)` pattern (`metadata.py:35-52`) — declare every settable field as `Optional[T]` with `extra: forbid`, return a typed `SettingsResponse`. Whitelist enforcement moves from the repository to the schema.

---

> _Dim 1 — Route Handlers_

### BE-RH-7: 4 `/api/library/*` endpoints are functional dead-ends — duplicate the dedicated router with a different response shape
- **Severity**: MEDIUM
- **Dimension**: Route Handlers (Dead code / response-shape drift)
- **Location**: `auralis-web/backend/routers/library.py:375 (`/api/library/artists`)`, `library.py:436 (`/api/library/artists/{artist_id}`)`, `library.py:464 (`/api/library/albums/{album_id}`)`, plus the documented-removed `/api/library/albums` (header comments line 14-17 still reference the dead routes)
- **Status**: NEW (filed #2379 + #2509 acknowledged the duplication but only removed the list endpoint for albums; per-id and artists list endpoints remain)
- **Description**: Frontend exclusively uses `/api/artists`, `/api/artists/{id}`, `/api/albums/{id}` (per `frontend/src/config/api.ts:60-62` and `frontend/src/hooks/library/useLibraryQuery.ts:120-125`). The library router keeps three parallel implementations that return different shapes — `library.py:425-430` returns a wrapper `{artists, total, offset, limit, has_more}` (raw dict), while `artists.py:153-159` returns a Pydantic-validated `ArtistsListResponse`. A third-party caller hitting `/api/library/artists` gets an undocumented shape, and the backend now has two divergent implementations of the same data product that can drift independently.
- **Evidence**: `useLibraryQuery.ts:120-125`:
  > `* - artists → /api/artists        (artists router — NOT /api/library/artists)`
  Same comment for albums. Test suite (`useLibraryQuery.test.ts:709-736`) explicitly asserts `expect(callUrl).not.toContain('/api/library/artists')`.
- **Impact**: Maintenance: a developer fixing an issue on `artists.py` may forget the `library.py` duplicate (or vice versa), leading to inconsistent behaviour for the rare third-party caller. CI / docs reference both shapes.
- **Siblings**: The header docstring of `library.py:14-17` lists these endpoints as supported — also stale.
- **Suggested Fix**: Delete `get_artists`, `get_artist`, `get_album` handlers from `library.py` and update the module docstring + `tests/backend/test_main_api.py:169,1141,1154` + `tests/backend/test_api_endpoint_integration.py:219` to use the supported endpoints.

---

> _Dim 1 — Route Handlers_

### BE-RH-8: `files.upload_files` leaks raw exception text via per-file `message: str(e)`
- **Severity**: MEDIUM
- **Dimension**: Route Handlers (Error response hygiene)
- **Location**: `auralis-web/backend/routers/files.py:223, 240`
- **Status**: NEW
- **Description**: The per-file result envelope embeds the raw exception text in two places:
  ```python
  # files.py:218-224
  except Exception as e:
      logger.error(f"Audio processing error for {file.filename}: {e}")
      results.append({
          "filename": file.filename or "",
          "status": "error",
          "message": f"Failed to process audio: {str(e)}"       # ← raw exception text
      })
  # files.py:235-241
  except Exception as e:
      logger.error(f"Upload error for {file.filename}: {e}")
      results.append({
          "filename": file.filename or "",
          "status": "error",
          "message": str(e)                                      # ← raw exception text
      })
  ```
  `load_audio` raises errors with the full file path; `shutil.move` raises with both source and destination paths; `repos.tracks.add` may include SQL fragments. Same disclosure class as BE-27 / BE-NEW-42 / BE-RH-3.
- **Impact**: Reveals server paths (`~/.auralis/uploads/<uuid>.flac`), library decoder versions, repo internals to the client.
- **Suggested Fix**: Mirror the `_internal_error_response` pattern — generate a `ref` per failure, log full exception with the ref, return `"message": "Failed to process audio (ref <hex8>)"`.

---

> _Dim 1 — Route Handlers_

### BE-RH-9: `system.subscribe_job_progress` callback never sees `track_id` validation — closure captures the WS but doesn't filter on subscription state
- **Severity**: MEDIUM
- **Dimension**: Route Handlers (Concurrency / lifecycle)
- **Location**: `auralis-web/backend/routers/system.py:781-809`
- **Status**: NEW (refinement of BE-NEW-62 / #3520 — the 64-char `job_id` length check was added, but the **callback** still doesn't check whether the WS is still open before sending)
- **Description**: The `progress_callback` closure captures `websocket` and is registered via `processing_engine.register_progress_callback(job_id, progress_callback)`. If the WS disconnects mid-job, the closure is still in `progress_callbacks[job_id]` — and the BE-NEW-63 finally-block fix only `unregister_progress_callback`s the IDs in `_subscribed_job_ids` (a local set). If the engine fires a progress event AFTER the WS disconnects but BEFORE `unregister_progress_callback` runs, the closure calls `await websocket.send_text(...)` on a closed socket and raises `RuntimeError("Cannot send on a closed connection")` or similar. The engine catches this (via its own try/except), but the engine-side log noise + the small window where the closure is invokable are real.
- **Evidence**: `system.py:798-809`:
  ```python
  async def progress_callback(job_id: str, progress: float, message: str) -> None:
      await websocket.send_text(json.dumps({
          "type": "job_progress",
          ...
      }))
  await processing_engine.register_progress_callback(job_id, progress_callback)
  _subscribed_job_ids.add(job_id)
  ```
  No guard on `websocket.client_state` or similar.
- **Impact**: Low blast-radius (engine's own exception handler absorbs the failure), but produces noisy logs and a brief window of misdirected sends. Worse, if `processing_engine.register_progress_callback` itself awaits before adding to the cb dict, the `await` window between line 808 and 809 could leave a callback registered for a job_id that's not in `_subscribed_job_ids`, defeating the disconnect cleanup.
- **Suggested Fix**: Inside `progress_callback`, gate the send on `websocket.client_state == WebSocketState.CONNECTED`. Or wrap the send in `try: ... except Exception: processing_engine.unregister_progress_callback(job_id)` to self-unregister on a dead WS. Verify the await-ordering at lines 808-809 is correct (`add` before `register` may be safer).

---

> _Dim 1 — Route Handlers_

### BE-RH-10: `player.load_track` declares `background_tasks: BackgroundTasks = None` — should be a `Depends()` default or no default
- **Severity**: MEDIUM
- **Dimension**: Route Handlers (FastAPI DI antipattern)
- **Location**: `auralis-web/backend/routers/player.py:280, 332`
- **Status**: NEW
- **Description**: The signature is:
  ```python
  async def load_track(request: LoadTrackRequest, background_tasks: BackgroundTasks = None) -> dict[str, Any]:
  ```
  FastAPI's `BackgroundTasks` is normally either an undefaulted parameter (FastAPI injects it automatically) or a `Depends(...)` parameter. Defaulting to `None` and then guarding with `if background_tasks` makes the recommendation generation conditional in a way that's never actually False under FastAPI runtime — FastAPI inspects parameters by type and injects `BackgroundTasks` regardless of the default. The `if background_tasks` check at line 332 is dead code. Worse, the type annotation `BackgroundTasks` plus default `None` makes type checkers complain (the default is the wrong type) and may break under stricter FastAPI version pinning.
- **Evidence**: All other BackgroundTasks-using handlers in the project (none in this dir) follow the standard `bg: BackgroundTasks` pattern (no default).
- **Impact**: Today: minimal — the runtime always injects, so the `if` is always True. Brittle: future FastAPI / mypy upgrade may flag or break.
- **Suggested Fix**: `async def load_track(request: LoadTrackRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:` and delete the `if background_tasks` guard.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-2: `play_enhanced` / `play_normal` await old streaming task while holding `_active_streaming_tasks_lock` — silently skips the old task's cleanup finally
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:435-449` (play_enhanced), `531-546` (play_normal)
- **Status**: NEW (regression of the cleanup intent in #3219)
- **Description**: After cancelling an in-flight stream, both handlers do `await old_task` from INSIDE `async with _active_streaming_tasks_lock`. The old streaming task's own finally block (`stream_audio`/`stream_normal`, lines 427-432 and 524-529) also enters `async with _active_streaming_tasks_lock` to perform an idempotent self-cleanup. With the lock held by the new request, the old task's finally `acquire()` is a second await inside a task that is being cancelled — Python re-raises `CancelledError` on the next await, aborting the finally without running `_active_streaming_track_ids.pop(...)`. Today this is harmless because the outer handler already removed both dict entries before awaiting (lines 437-438, 533-534), so the missed pop is a no-op; however, any future change that relies on the streaming task's finally to maintain other invariants (counters, metrics, queue cleanup) will be silently bypassed for every track switch.
- **Evidence**:
  ```python
  async with _active_streaming_tasks_lock:
      ...
      old_task = _active_streaming_tasks.pop(ws_id, None)
      if old_task and not old_task.done():
          old_task.cancel()
          try:
              await old_task           # <-- lock still held; old_task's finally
          except (asyncio.CancelledError, Exception):
              pass                     #     blocks on the same lock → CancelledError
      ...
  ```
  Compared to the seek path (line 681) and the disconnect path (line 847) which both `await task` *outside* the lock.
- **Impact**: Latent fragility. Today: silent skip of `_active_streaming_track_ids.pop` and any future cleanup added to the streaming-task finally. Defensive observation: the play handlers also do not pop `_active_streaming_track_ids` in their outer block (only `_active_streaming_tasks`), so any future bug-fix that adds work to the streaming task's finally will be undone.
- **Siblings**: Same pattern in both play_enhanced and play_normal — fix once, mirror.
- **Suggested Fix**: Mirror the seek pattern: pop the task under the lock, release the lock, then `await old_task` outside the lock. Hoist `_active_streaming_track_ids.pop(ws_id, None)`, `_stream_pause_events.pop(...)`, and `_stream_flow_events.pop(...)` into the outer pop step so the new task can be created with fresh state immediately after the await returns.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-3: Per-message stream coroutines capture `track_id` / `preset` / `force` / `start_position` by reference — outer loop reassignments can leak into in-flight cancellation paths
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:352-461` (stream_audio), `491-562` (stream_normal), `704-779` (stream_from_position)
- **Status**: NEW
- **Description**: The inner `async def stream_audio()` / `stream_normal()` / `stream_from_position()` close over the receive-loop locals `track_id`, `preset`, `intensity`, `start_position`, `force`, `ws_id`, `enhancement_enabled`. The receive loop reassigns those names on every message. Once the new task is scheduled, the receive loop yields at `await websocket.receive_text()` — but if a SECOND `play_enhanced`/`seek` message arrives before the new task has finished evaluating the call-site kwargs `track_id=track_id`, the outer-loop reassignment can mutate the cell the closure reads. The kwargs in `stream_enhanced_audio(track_id=track_id, ...)` are bound at the call site, so by the time the new request rebinds the cell the call has already passed its frozen value — typically safe. BUT the inner `except Exception` blocks (lines 411-426, 738-753) reference `track_id` from the closure when sending `audio_stream_error`. If the new request arrives while the first task is in its except path, the error message will contain the NEW (wrong) track_id, attributing a failure of stream A to track B.
- **Evidence**:
  ```python
  # Receive loop iteration N (track_id = A):
  track_id = data.get("track_id")     # = A
  ...
  async def stream_audio():
      try:
          ...
      except Exception as e:
          await websocket.send_text(json.dumps({
              "type": "audio_stream_error",
              "data": {"track_id": track_id, ...}   # closure reference — NOT A's
          }))
  # Receive loop iteration N+1 (track_id = B): reassigns the same cell.
  ```
- **Impact**: Misattributed error messages confuse client-side error UI (e.g. "Failed to load track 123" toast when the failed track was actually 47). Cancellation-path-of-old-task races are the trigger. Hard to reproduce manually, easy to hit under fast back-to-back play presses on slow disks.
- **Siblings**: All three inner coroutines (stream_audio, stream_normal, stream_from_position) share the closure-binding hazard.
- **Suggested Fix**: Bind kwargs explicitly via default-argument trick at coroutine creation: `async def stream_audio(track_id=track_id, preset=preset, intensity=intensity, force=force, start_position=start_position, ws_id=ws_id):` so each coroutine instance has its own immutable copies, identical to a fresh frame in C.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-4: `_load_audio_cached` LRU is shared process-wide and unbounded by audio size — one large file evicts everything; concurrent streams of the same file race to populate
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/webm_streaming.py:57-78`
- **Status**: NEW
- **Description**: `@lru_cache(maxsize=8)` on `_load_audio_cached(filepath, _mtime)` caches up to 8 fully-decoded files in RAM, with no per-file size accounting and no eviction-by-bytes policy. A user opening 8 lossless 24-bit 96 kHz albums (~150 MB each = ~1.2 GB) will silently pin all of them in heap forever (LRU never evicts because the bound is by entry count, not bytes). Worse: the cache key is `(filepath, _mtime)` — every chunk request for the same file re-checks `os.path.getmtime` (cheap) but if two concurrent streams hit the same file with a millisecond-rounded mtime, the underlying `load_audio` runs twice (LRU lookup is fast-path; no inner lock guards the load). The `audio.flags.writeable = False` guard does not protect against duplicate decodes — it only protects against in-place mutation after the read.
- **Evidence**:
  ```python
  @lru_cache(maxsize=8)
  def _load_audio_cached(filepath: str, _mtime: float = 0.0):
      from auralis.io.unified_loader import load_audio
      audio, sr = load_audio(filepath)
      audio.flags.writeable = False
      return audio, sr
  ```
  No `maxsize_bytes`, no lock around the decode. `audio_stream_controller.SimpleChunkCache` (lines 75-189) has a 512 MB `_max_memory_bytes` cap — the same discipline should apply to the WAV cache, but doesn't.
- **Impact**: Long sessions with large libraries can hit OOM. On Electron (4 GB renderer + 1 GB Python) this becomes a hard wall. Concurrent stream starts of the same fresh track double the decode cost (waste of ~100 ms–2 s).
- **Siblings**: `SimpleChunkCache` has the byte-aware eviction; this LRU does not.
- **Suggested Fix**: Replace `@lru_cache(maxsize=8)` with an OrderedDict + lock + byte counter (mirror `SimpleChunkCache` at ~/auralis-web/backend/core/audio_stream_controller.py:75). Cap at e.g. 512 MB total. Optional: gate the decode behind a per-path `threading.Lock()` so concurrent requests share the same in-flight decode.

---

> _Dim 3 — Chunked Processing_

### BE-CP-3: `_smooth_level_transition` applies a static per-chunk gain → discontinuity at every boundary AND silently promotes float32 → float64
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/level_manager.py:84-173` (`LevelManager.smooth_transition`); called from `chunked_processor.py:354-404, 516`
- **Status**: NEW
- **Description**: When the per-chunk RMS difference exceeds `MAX_LEVEL_CHANGE_DB = 1.5 dB`, the code computes `gain_adjustment = 10 ** (required_adjustment_db / 20)` (Python float = float64) and does `chunk_adjusted = chunk * gain_adjustment`. Two problems: (1) The gain is applied UNIFORMLY across the whole chunk — meaning the last sample of chunk N-1 has its true RMS-warmed value, but the FIRST sample of chunk N is multiplied by a static `gain_adjustment` derived from the WHOLE chunk's RMS. This produces a small but real discrete step at every boundary where the smoothing triggers — exactly the kind of "click" the smoothing is supposed to prevent. A linear ramp from `prev_gain → required_gain` over the chunk length would actually smooth, but the current code applies a hard scalar. (2) `chunk_adjusted = chunk * gain_adjustment` with a Python-float multiplicand promotes any float32 input to float64 (NEP-50: scalar operations on lower-precision arrays promote to the higher type when the scalar's type is not narrower) — silently doubling per-chunk memory in the streaming pipeline.
- **Evidence**:
  ```python
  # level_manager.py:143-146
  gain_adjustment = 10 ** (required_adjustment_db / 20)  # Python float64
  chunk_adjusted = chunk * gain_adjustment              # promotes float32 → float64
  ```
  In streaming, the per-chunk path is: load_audio (float32 by default in soundfile) → HybridProcessor.process → trim_context → smooth_transition (× scalar → float64) → extract_chunk_segment → WAV encoder (downcast back to float32 at the very end). Memory doubled for the entire `processed_chunk` lifetime.
  
  The boundary step is on the order of `MAX_LEVEL_CHANGE_DB = 1.5 dB`, which is ~19 % amplitude change — easily audible as a "thump" if it triggers.
- **Impact**: When a track has sudden dynamics shifts between chunks (e.g. loud verse → quiet chorus crossing a chunk boundary at 10 s, 20 s, ...), the listener hears a discrete amplitude step instead of a smooth fade. Memory: ~10 MB per chunk wasted for the float32 → float64 promotion lifetime. The float64 promotion sibling of #3658/#3659/#3744 (all CLOSED, all about `BrickWallLimiter` / `RealtimeProcessor` / `VectorizedEQProcessor` float promotion); same family at the LevelManager site.
- **Siblings**: `apply_gain` (`level_manager.py:175-190`) has the same `audio * gain_linear` pattern. `chunked_processor.py:512` (`np.zeros(..., dtype=np.float32)` for empty-chunk fallback) uses float32 but loses input dtype context (mismatched if input was float64).
- **Suggested Fix**: (1) Cast the scalar to `audio.dtype` before multiplying: `gain_adjustment = audio.dtype.type(10 ** (required_adjustment_db / 20))`. (2) Apply the gain as a per-sample LINEAR RAMP from the previous chunk's effective gain to the new gain across some short window (e.g. first 50 ms), then hold: `chunk[:ramp_len] *= linspace(prev_g, new_g, ramp_len, dtype=chunk.dtype)[:, None]; chunk[ramp_len:] *= new_g`. This eliminates the boundary step.

---

> _Dim 3 — Chunked Processing_

### BE-CP-4: Cached chunks in `SimpleChunkCache` skip `LevelManager.smooth_transition` — state-skew when cache hit/miss patterns alternate
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1117-1133` (`_process_chunk_only` cache path); `chunked_processor.py:469-518` (`_process_chunk_core`); `level_manager.py:84-173`
- **Status**: NEW
- **Description**: `_process_chunk_only` returns cached chunks **without** calling `processor.process_chunk_safe` → `_process_chunk_core` → `_smooth_level_transition`. The `LevelManager.rms_history` therefore SKIPS any cache-hit chunk. When the next chunk_idx misses the cache and triggers processing, `smooth_transition` compares its RMS against `rms_history[-1]` — which is the last PROCESSED chunk's RMS, not the chronologically-previous chunk. If chunks `[0, 2]` are cached and chunk 1 is not, the LevelManager smooths chunk 1 against chunk -1's RMS (whatever the prior track's last value was, or empty → treats as baseline). Because the ChunkedAudioProcessor is fresh-per-stream and prefetch is disabled, the most common path today never hits this; but `webm_streaming.py` and the recommendation_service `process_chunk` flow can cache-hit out-of-order via `_cache_manager.get_cached_chunk_path`.
- **Evidence**: `audio_stream_controller.py:1129-1131`:
  ```python
  if cached_result:
      pcm_samples, sr = cached_result
      logger.info(f"Cache HIT: chunk {chunk_index}, preset {processor.preset}")
  # NO call to processor.process_chunk_safe → no LevelManager update
  ```
  vs. cache-miss path at line 1141: `_chunk_path, pcm_samples = await processor.process_chunk_safe(chunk_index, fast_start=fast_start)` which DOES update the LevelManager.
- **Impact**: When `SimpleChunkCache` partially overlaps stream playback (rare today, but the cache lifecycle is being re-evaluated per the comments at audio_stream_controller.py:715-723), the per-chunk gain compensation can be applied based on stale or absent history — producing exactly the volume jumps it's meant to prevent. Currently latent because cache hits are rare in the new-stream-per-WS architecture; will surface if the singleton cache reform suggested in BE-NEW-55 lands.
- **Siblings**: Architectural issue, no direct sibling. Related to BE-CP-3 (the smoothing is itself fragile).
- **Suggested Fix**: Either (1) have `_process_chunk_only` update `processor._level_manager.rms_history` from cached chunks' calculated RMS before returning (so the smoothing state stays consistent regardless of cache state); OR (2) cache the LEVELMANAGER STATE alongside each chunk in `SimpleChunkCache`; OR (3) move `_smooth_level_transition` out of `_process_chunk_core` and into the streaming path (apply AFTER cache lookup), so it sees every chunk.

---

> _Dim 3 — Chunked Processing_

### BE-CP-5: Two `np.zeros(...)` fallbacks in `chunk_operations.load_chunk_from_file` lack `dtype=` and default to float64 → silent dtype promotion in fallback paths
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:128, 140`
- **Status**: NEW
- **Description**: When soundfile loading fails and the fallback `load_audio(full_audio)` path either runs past the file end or returns empty content, the code produces fallback silence via `np.zeros((1, channels))` (line 128) and `np.zeros((int(0.1 * sample_rate), channels))` (line 140) WITHOUT `dtype=`. NumPy defaults to `float64`. The downstream pipeline expects float32 (per CLAUDE.md invariant and `WAVEncoder` clip-and-encode path), so the entire chunk gets promoted to float64 until the final encode step. Same dtype-hazard family as the FIXED #3658, #3659, #3744 (all `MEDIUM`).
- **Evidence**:
  ```python
  # chunk_operations.py:127-128
  audio = np.zeros((1, full_audio.shape[1] if full_audio.ndim > 1 else 1))
  # line 140:
  audio = np.zeros((int(0.1 * sample_rate), num_channels))
  ```
  Compare with `chunk_operations.py:240` which DOES specify `dtype=np.float32`, and the explicit fix in `chunked_processor.py:512`. The inconsistency is the regression.
- **Impact**: Memory doubling for the affected chunk, plus any per-chunk dtype promotion that downstream operations (broadcast multiplication, EQ filter coefficients, RMS computation) propagate. Triggers on file-load fallback paths — rare in normal operation but reachable on transient file-system errors or libsndfile bugs.
- **Siblings**: Filed CLOSED MEDIUMs #3658 (BrickWallLimiter), #3659 (VectorizedEQProcessor), #3744 (RealtimeProcessor), #3748 (soundfile_loader default float64). Open siblings: none in current dimension set.
- **Suggested Fix**: Pass `dtype=full_audio.dtype if full_audio is not None else np.float32` (line 128) and `dtype=np.float32` (line 140, since `num_channels=2` is hardcoded as the default-stereo path). Add a unit test that asserts dtype preservation on the fallback path.

---

> _Dim 3 — Chunked Processing_

### BE-CP-6: `ChunkCacheManager` has no eviction policy — unbounded growth across long-lived processors
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_cache_manager.py:127-301` (entire class — no `max_entries`/`max_bytes`/LRU/TTL)
- **Status**: NEW
- **Description**: `ChunkCacheManager` stores `track_id_sig_preset_intensity_chunk_N → path` entries and provides `clear_track_cache` only — no automatic eviction, no size cap, no LRU. Each `ChunkedAudioProcessor` instance has its own dict (`self.chunk_cache = {}` at `chunked_processor.py:106`), so per-instance growth is bounded by `total_chunks`. But the **ChunkedAudioProcessor is held by every active enhanced stream**, the HybridProcessor inside is held by `ProcessorFactory` (LRU-bounded at 32 entries since #3515 / BE-NEW-57), AND the on-disk WAV chunks the cache POINTS TO never get cleaned up automatically (`WAVEncoder.cleanup_track_chunks` is only called from explicit cache-clearing endpoints). After ~hours of varied playback the `/tmp/auralis_chunks/` directory accumulates GB of WAVs even while the in-memory ChunkCacheManager dict stays "small" per-instance.
- **Evidence**: `chunk_cache_manager.py:127-135` — only a `__init__` taking an external dict, no cap. `chunked_processor.py:122-123` — `self.chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"; self.chunk_dir.mkdir(exist_ok=True)` — files persist across process restarts. `WAVEncoder` (`encoding/wav_encoder.py:151-189`) writes via `encode_and_save_from_path` but never tracks total size. `SimpleChunkCache` (`audio_stream_controller.py:82-189`) HAS a 512 MB / 50-chunk cap but is a **separate** in-memory cache and is also created per AudioStreamController instance.
- **Impact**: On a long-lived backend (~ days of uptime, expected in the Electron desktop app), the on-disk chunk cache can fill `/tmp` to capacity. `df /tmp` exhaustion will cause downstream WAV writes to fail (raising `IOError` per `wav_encoder.py:148-149`) and chunk-processing failures (#3190 recovery skips the chunk but does not surface the disk-full problem to the user).
- **Siblings**: BE-NEW-57 (CLOSED) bounded `ProcessorFactory`; BE-NEW-74 (`MasteringTargetService.cache` unbounded — still OPEN per /tmp/audit listing); BE-NEW-97 (`StreamlinedCacheManager.mastering_recommendations` unbounded — CLOSED).
- **Suggested Fix**: Add `max_entries` / `max_disk_bytes` parameters to `ChunkCacheManager.__init__`, periodic prune in `cache_chunk_path` (delete least-recently-used WAV from disk + remove from dict). Add a startup task that scans `/tmp/auralis_chunks/`, sorts by mtime, and deletes oldest until under a target size.

---

> _Dim 4 — Processing Engine_

### BE-PE-2: `processing_cache` dict referenced by `enhancement.py` is never written to — "intensity-change cache clear" and `POST /api/player/enhancement/cache/clear` operate on permanently-empty state
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/routers/enhancement.py:316-323, 547-571`; backing dict `auralis-web/backend/main.py:104`, `auralis-web/backend/config/globals.py:140`
- **Status**: NEW
- **Description**: `processing_cache` is declared in `main.py:104` and `globals.py:140` as `{}` and is plumbed into the enhancement router via `get_processing_cache`. Nothing in the codebase ever writes to it: `grep -rn "processing_cache\[" auralis-web/` returns zero hits. The intensity-change handler at `enhancement.py:317-323` builds `keys_to_remove = [k for k in cache.keys() if f"_{preset}_{old_intensity}_" in k]` — a list comprehension over an empty dict. The `POST /api/player/enhancement/cache/clear` endpoint at line 562 does `cache.clear()` and reports `items_cleared: 0` every time. The real processed-chunk caching now lives in `ChunkCacheManager` / `StreamlinedCacheManager` (in-memory) and `ProcessorFactory._processor_cache` (processor instances) — neither is reachable through this code path.
- **Evidence**:
  ```python
  # enhancement.py:316-323 — dead substring match against {}
  if get_processing_cache is not None and old_intensity != intensity:
      cache = get_processing_cache()
      keys_to_remove = [k for k in cache.keys() if f"_{preset}_{old_intensity}_" in k]
      for key in keys_to_remove:
          del cache[key]
      if keys_to_remove:
          logger.info(f"🧹 Cleared {len(keys_to_remove)} cache entries for old intensity {old_intensity}")

  # main.py:104 — declared but never written
  'processing_cache': {},
  ```
- **Impact**: The "cache cleared on intensity change" behaviour is dead — when a user moves the intensity slider, processed-chunk caches in `ProcessorFactory` / `ChunkCacheManager` continue to serve stale audio at the OLD intensity until the user explicitly hits the "clear cache" button (which also clears nothing). For users with auto-mastering enabled, intensity changes therefore don't take effect on in-flight chunks. The same wiring failure is also exposed as the `/api/player/enhancement/cache/clear` REST endpoint which returns "Processing cache cleared (N items removed)" with N always 0 — an actively misleading API surface.
- **Siblings**: The same dead `processing_cache` dict is passed to `routers/player.py:196` (`get_processing_cache`), which also never writes to it.
- **Suggested Fix**: Either (a) wire the intensity-change handler to actually invalidate `ProcessorFactory` entries (e.g., `processor_factory.cleanup_for_intensity(preset, old_intensity)` — needs a new helper) and `ChunkCacheManager` entries (`cache_manager.invalidate_intensity_change(...)` — also missing), or (b) delete the dead dict and the dead endpoint. Option (a) is the user-visible fix; option (b) at least stops the lying log line and lying API response.

---

> _Dim 4 — Processing Engine_

### BE-PE-3: `ChunkedAudioProcessor` constructs `MasteringTargetService()` with no `get_fingerprints_repository` — Tier-1 (DB) fingerprint lookup is silently dead on every track
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/chunked_processor.py:135`; consumer `auralis-web/backend/core/mastering_target_service.py:90-159, 456-472`
- **Status**: Regression of #3557 (BE-NEW-99) — issue closed COMPLETED but the wire-up was never done
- **Description**: `MasteringTargetService.__init__` accepts a `get_fingerprints_repository` callable for DB-tier (Tier 1, fastest) fingerprint lookup. `load_fingerprint_from_database()` early-returns `None` when `self._get_fingerprints_repository is None`. `ChunkedAudioProcessor.__init__` line 135 instantiates the service as `MasteringTargetService()` with NO arguments. The global singleton accessor `get_mastering_target_service()` (mastering_target_service.py:469) also passes no arguments. So every chunked processor's 3-tier loading degrades to (Tier 1 silently skipped) → Tier 2 (.25d file) → Tier 3 (extract from audio). The "✅ Loaded fingerprint from database" log line at line 148 is currently unreachable in production. The Phase 2 refactoring commit (6ca4ea14) added the DI parameter, but the call sites were never updated — and the audit-flagged issue (#3557 / BE-NEW-99) was closed-as-COMPLETED without a corresponding fix commit.
- **Evidence**:
  ```python
  # chunked_processor.py:135 — service constructed without DI
  self._mastering_target_service: Any = MasteringTargetService()
  
  # mastering_target_service.py:106-108 — Tier 1 short-circuits
  if self._get_fingerprints_repository is None:
      logger.debug("No fingerprints repository provided - skipping database lookup")
      return None
  
  # mastering_target_service.py:469-472 — global singleton also unwired
  if _global_mastering_target_service is None:
      _global_mastering_target_service = MasteringTargetService()
  ```
- **Impact**: Every ChunkedAudioProcessor pays the cost of Tier 2 (filesystem stat for `.25d` sidecar) per track even when the fingerprint is already cached in the DB. On a freshly-imported library where `.25d` files don't yet exist, every track also pays the full Tier 3 extraction cost (~3-10 s of audio analysis + Rust FFI) instead of the ~1 ms DB read. Wasted CPU per stream start. The fix is one-line at the construction site.
- **Siblings**: `get_mastering_target_service()` global singleton also bypasses DI.
- **Suggested Fix**: In `ChunkedAudioProcessor.__init__`, wire the repository factory through the constructor:
  ```python
  # Accept get_repository_factory in ChunkedAudioProcessor.__init__ (it's already wired via system.py controller)
  self._mastering_target_service: Any = MasteringTargetService(
      get_fingerprints_repository=lambda: get_repository_factory().fingerprints
  )
  ```
  Or use the global singleton with one-time initialisation at startup that binds the repo factory.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-2: `PUT /api/settings` still accepts `dict[str, Any]` — #3498 closed but never fixed
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/settings.py:77-91`
- **Status**: Regression of #3498 (issue CLOSED 2026-05-26; code at the cited line still matches the flagged pattern)
- **Description**: BE-NEW-40 (2026-05-25 audit) flagged `PUT /api/settings` as accepting `updates: dict[str, Any]` with no Pydantic model. Issue #3498 was created and closed-as-COMPLETED on 2026-05-26, but the route signature at `settings.py:78` still reads `async def update_settings(updates: dict[str, Any]) -> dict[str, Any]`. No `SettingsUpdateRequest` model was added, no `response_model=` was attached, and `extra='forbid'` was never wired up. The frontend `settingsService.ts` defines `SettingsUpdate` with ~22 typed optional fields — the contract exists on the consumer side but not on the producer side, so a typo in any field name silently no-ops via the SettingsRepository's internal whitelist (no 422 returned). OpenAPI docs still show "any object" for the request body.
- **Evidence**:
  ```python
  # backend/routers/settings.py:77-91 — unchanged since the 2026-05-25 audit
  @router.put("/api/settings")
  async def update_settings(updates: dict[str, Any]) -> dict[str, Any]:
      ...
      settings = await asyncio.to_thread(_repo().update_settings, updates)
      ...
      return {"message": "Settings updated", "settings": settings.to_dict()}
  ```
  ```typescript
  // frontend/src/services/settingsService.ts:50-82 — ~22 typed optional fields the backend would need to declare
  export interface SettingsUpdate {
    scan_folders?: string[];
    file_types?: string[];
    auto_scan?: boolean;
    scan_interval?: number;
    crossfade_enabled?: boolean;
    crossfade_duration?: number;
    gapless_enabled?: boolean;
    replay_gain_enabled?: boolean;
    volume?: number;
    output_device?: string | null;
    bit_depth?: number;
    sample_rate?: number;
    theme?: string;
    language?: string;
    show_visualizations?: boolean;
    mini_player_on_close?: boolean;
    default_preset?: string;
    auto_enhance?: boolean;
    enhancement_intensity?: number;
    cache_size?: number;
    max_concurrent_scans?: number;
    enable_analytics?: boolean;
    debug_mode?: boolean;
  }
  ```
- **Impact**: (a) OpenAPI clients cannot discover settable fields. (b) Type-coercion errors become 500s instead of 422s. (c) A field typo silently no-ops because the SettingsRepository whitelist drops unknown keys without complaint — the user thinks the change took effect. (d) #3498 was published to the changelog/GitHub timeline as "fixed", masking the gap.
- **Siblings**: Same `dict[str, Any]` pattern at `BatchMetadataUpdateRequest.metadata` (`metadata.py:55-58`), `cache_streamlined.CacheStatsResponse.tier1/tier2/overall` (`cache_streamlined.py:33-36`), `JobListResponse.jobs: list[dict[str, Any]]` (`processing_api.py:117-120`), `ProcessingSettings.eq/dynamics/level_matching` (`processing_api.py:75-82`).
- **Suggested Fix**: Define `SettingsUpdateRequest(BaseModel)` mirroring `SettingsUpdate` from the frontend (all fields `Optional`, sensible defaults `None`, `model_config = {"extra": "forbid"}`). Define `SettingsResponse(BaseModel)` reusing the field list. Add `response_model=SettingsResponse` to `PUT /api/settings`, `POST /scan-folders`, `POST /scan-folders/delete`, `POST /reset`. Reopen and re-close #3498 with the actual diff.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-3: ~28 endpoints across 7 routers still return raw `dict[str, Any]` with no `response_model` — #3507 closed but only player.py + artists.py + enhancement.py + processing_api.py were migrated
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location** (current counts of endpoints with/without `response_model=`, fresh grep at audit time):
  - `library.py` — 15 endpoints, 0 with `response_model`
  - `playlists.py` — 8 endpoints, 0 with `response_model`
  - `albums.py` — 4 endpoints, 0 with `response_model`
  - `artwork.py` — 4 endpoints, 0 with `response_model`
  - `metadata.py` — 4 endpoints, 0 with `response_model`
  - `settings.py` — 5 endpoints, 0 with `response_model`
  - `files.py` — 2 endpoints, 0 with `response_model`
  - `system.py` — 2 REST endpoints (health/version), 0 with `response_model`
  - `cache_streamlined.py` — 5 endpoints, 2 with `response_model`
  - `similarity.py` — 11 endpoints, 4 with `response_model`
- **Status**: Regression of #3507 (BE-NEW-49). Issue CLOSED 2026-05-26 but `library.py` / `playlists.py` / `albums.py` / `artwork.py` / `metadata.py` / `settings.py` / `files.py` still have zero `response_model=` decorations.
- **Description**: BE-NEW-49 (2026-05-25 audit) flagged ~44 endpoints across 7 routers as returning raw `dict[str, Any]` with no `response_model`. Issue #3507 was published and closed-as-COMPLETED on 2026-05-26. Re-counting today shows that `player.py` (18/18) and `artists.py` (3/3) were already complete before the issue was filed, and only `enhancement.py` (4 of 7), `processing_api.py` (8 of 9), and `cache_streamlined.py` (2 of 5), `similarity.py` (4 of 11) gained any new coverage. Seven of the eight routers the audit named are still at 0% coverage. The proposed `TrackResponse` / `AlbumResponse` / `PlaylistResponse` / `ScanResultResponse` / `LibraryStatsResponse` models from the audit's fix proposal don't exist anywhere in `schemas.py` or any router.
- **Evidence**:
  ```bash
  $ for f in auralis-web/backend/routers/*.py; do
      ep=$(grep -c "@router\.\(get\|post\|delete\|put\|patch\)" "$f")
      rm=$(grep -c "response_model=" "$f")
      [ "$ep" -gt 0 ] && echo "$(basename $f): $ep endpoints, $rm with response_model"
    done
  albums.py: 4 endpoints, 0 with response_model
  artists.py: 3 endpoints, 3 with response_model
  artwork.py: 4 endpoints, 0 with response_model
  cache_streamlined.py: 5 endpoints, 2 with response_model
  enhancement.py: 7 endpoints, 4 with response_model
  files.py: 2 endpoints, 0 with response_model
  library.py: 15 endpoints, 0 with response_model
  metadata.py: 4 endpoints, 0 with response_model
  player.py: 18 endpoints, 18 with response_model
  playlists.py: 8 endpoints, 0 with response_model
  processing_api.py: 9 endpoints, 8 with response_model
  settings.py: 5 endpoints, 0 with response_model
  similarity.py: 11 endpoints, 4 with response_model
  system.py: 2 endpoints, 0 with response_model
  webm_streaming.py: 2 endpoints, 1 with response_model
  ```
- **Impact**: (a) OpenAPI docs are unusable for these 28+ endpoints — schema field "Schema" tab shows nothing. (b) Direct contributor to BE-SCH-4 below (`scan_complete` REST returns `scan_time` while WS emits `duration` — would have been caught at write-time by an `ScanResultResponse` model with `response_model=`). (c) Frontend cannot generate a typed client. (d) The 2026-05-25 audit's BE-NEW-44 / BE-NEW-47 / BE-NEW-86 root-cause analysis explicitly named this gap; the gap remains.
- **Siblings**: This is the structural root cause of BE-SCH-4 (`scan_complete` field naming) and BE-SCH-5 (`/api/player/mastering/recommendation/{id}` missing `is_hybrid`).
- **Suggested Fix**: Stand up `TrackResponse`, `AlbumResponse`, `PlaylistResponse`, `PlaylistDetailResponse`, `ScanResultResponse`, `LibraryStatsResponse`, `TrackLyricsResponse`, `TrackFingerprintResponse`, `SettingsResponse`, `MetadataResponse`, `UploadResultResponse`, `MasteringRecommendationResponse` in `schemas.py` (reusing the `serializers.py` field-list dicts as the canonical source of truth). Then add `response_model=` at all 28+ sites. Reopen and reclose #3507 with the actual diff.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-4: `POST /api/library/scan` REST returns `scan_time` while the paired WS `scan_complete` broadcast emits `duration` — same handler, two field names for the same number
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**:
  - REST return: `auralis-web/backend/routers/library.py:651-659`
  - WS broadcast (same handler): `auralis-web/backend/routers/library.py:622-633`
  - Auto-scanner WS broadcast (already canonicalized): `auralis-web/backend/services/library_auto_scanner.py:307-325`
- **Status**: Partial-regression of #3502 / BE-NEW-44. The WS-emitter side was unified across manual + auto paths (both emit `duration`), but the manual REST `POST /api/library/scan` return body wasn't migrated — it still emits `scan_time` alongside the `duration` it just broadcast.
- **Description**: PR #3502 (2026-05-25) fixed the manual-vs-auto WS shape divergence (both now emit `{files_processed, files_added, files_updated, files_skipped, files_failed, duration, directories_scanned}`). But the `return` statement two lines below the broadcast in the same handler still constructs `{"scan_time": result.scan_time, ...}` — the REST response now uses `scan_time` while the WS broadcast (fired moments earlier) uses `duration` for the exact same `result.scan_time` value. The frontend's `useLibraryWithStats.scanForMusic` only reads `result.files_added` from the REST response, so the divergence is currently a latent contract violation rather than a user-visible bug — but it means anyone reading the API response programmatically (third-party tool, future feature) sees `scan_time` while anyone subscribed to the WS sees `duration`.
- **Evidence**:
  ```python
  # backend/routers/library.py:622-633 — WS uses `duration` (post-#3502)
  await connection_manager.broadcast({
      "type": "scan_complete",
      "data": {
          "files_processed": result.files_processed or result.files_found,
          "files_added": result.files_added,
          "files_updated": result.files_updated,
          "files_skipped": result.files_skipped,
          "files_failed": result.files_failed,
          "duration": result.scan_time,
          "directories_scanned": result.directories_scanned,
      }
  })
  
  # backend/routers/library.py:651-659 — REST still uses `scan_time`
  return {
      "files_found": result.files_found,
      "files_added": result.files_added,
      "files_updated": result.files_updated,
      "files_skipped": result.files_skipped,
      "files_failed": result.files_failed,
      "scan_time": result.scan_time,           # ← inconsistent with WS
      "directories_scanned": result.directories_scanned
  }
  ```
- **Impact**: A `ScanResultResponse` Pydantic model used as `response_model=` would have caught this divergence at write-time. Until then: scripted callers of `POST /api/library/scan` who also subscribe to `scan_complete` (the standard "kick the scan; wait for completion via WS" pattern) see two field names for the same value and must accept both.
- **Siblings**: Sibling of BE-SCH-3 (no `response_model`). Sibling of the `library_updated.action vs reason` historical case (#3544 / BE-NEW-86, already fixed). Sibling of `files_found` (REST) vs absence of that field in the WS broadcast — `files_processed` ≠ `files_found`.
- **Suggested Fix**: Pick one. Either rename the REST return field to `duration`, or rename the WS broadcast field to `scan_time`. The WS path already moved to `duration` in #3502 and the frontend type (`ScanCompleteMessage.data.duration`) ships that name, so the smaller-blast-radius fix is to rename the REST return. Then add `ScanResultResponse(BaseModel)` and `response_model=ScanResultResponse` so this can never regress.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-5: `GET /api/player/mastering/recommendation/{track_id}` returns `MasteringRecommendation.to_dict()` directly — emits `alternative_profiles`/`created`, omits `is_hybrid` (required by frontend type)
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**:
  - REST endpoint: `auralis-web/backend/routers/enhancement.py:430-443`
  - Backend dataclass: `auralis/analysis/adaptive_mastering_engine.py:54-77`
  - Service-layer broadcast (correctly adds `is_hybrid`): `auralis-web/backend/services/recommendation_service.py:88-97`
  - Frontend types (all three declare `is_hybrid: boolean` as REQUIRED): `auralis-web/frontend/src/types/{domain,api,websocket}.ts:{214,106,359}`
- **Status**: Partial-regression of #3550 (BE-NEW-92). Issue CLOSED 2026-05-26 but only fixed the WS path (`recommendation_service.py:96` adds `rec_dict['is_hybrid'] = bool(...)` to the broadcast), not the REST path.
- **Description**: `MasteringRecommendation.to_dict()` (`adaptive_mastering_engine.py:54-77`) returns `{primary_profile_id, primary_profile_name, confidence_score, predicted_loudness_change, predicted_crest_change, predicted_centroid_change, reasoning, created, alternative_profiles, weighted_profiles?}`. The WS broadcast path (`recommendation_service.py`) augments this with `is_hybrid = bool(weighted_profiles)` before broadcasting. The REST endpoint `GET /api/player/mastering/recommendation/{track_id}` at `enhancement.py:432` just calls `rec.to_dict()` and returns the result directly — no `is_hybrid`. The frontend `MasteringRecommendation` types in `domain.ts`, `api.ts`, and `websocket.ts` all declare `is_hybrid: boolean` (required, not optional). The endpoint also leaks `created` (ISO timestamp not in any frontend type) and `alternative_profiles` (declared optional in `websocket.ts` only, absent from `domain.ts` / `api.ts`). The fix to #3550 was applied only to the broadcast path; the REST endpoint was not updated.
- **Evidence**:
  ```python
  # backend/routers/enhancement.py:421-443 — REST returns to_dict() raw
  def _run_recommendation() -> dict | None:
      proc = ChunkedAudioProcessor(...)
      rec = proc.get_mastering_recommendation(confidence_threshold=_ct)
      return rec.to_dict() if rec is not None else None     # ← no is_hybrid added
  
  result = await asyncio.to_thread(_run_recommendation)
  if result is None:
      raise HTTPException(status_code=500, detail="Failed to analyze audio file")
  return result if isinstance(result, dict) else {}        # ← raw, missing is_hybrid
  
  # backend/services/recommendation_service.py:94-97 — WS adds is_hybrid
  rec_dict = cast(dict[str, Any], rec.to_dict())
  rec_dict['track_id'] = track_id
  rec_dict['is_hybrid'] = bool(rec_dict.get('weighted_profiles'))   # ← only here
  
  # backend/routers/enhancement.py:445 — no Pydantic model on REST endpoint
  @router.get("/api/player/mastering/recommendation/{track_id}")     # ← no response_model=
  ```
  ```typescript
  // frontend/src/types/api.ts:92-107 — is_hybrid REQUIRED
  export interface MasteringRecommendationResponse {
    track_id: number;
    primary_profile_id: string;
    ...
    is_hybrid: boolean;        // ← would be undefined on this endpoint's payload
  }
  ```
- **Impact**: Any frontend code that hits this REST endpoint (today only `usePlayer*` hooks listen on the WS path; the REST endpoint is reachable but uncalled by production frontend code) and trusts the declared type will read `is_hybrid` as `undefined`, which TypeScript will treat as `false` in boolean contexts — wrong if the recommendation IS hybrid. The endpoint also leaks `track_id` absent (the WS path adds it explicitly) — REST callers must derive it from the URL. Blast radius: dormant today (no frontend caller), but the OpenAPI doc + the WEBSOCKET_API.md cross-reference both promise a contract that isn't honored.
- **Siblings**: Sibling of BE-SCH-3 (no `response_model=`). Sibling of BE-NEW-92 / #3550 (partially fixed).
- **Suggested Fix**: Define `MasteringRecommendationResponse(BaseModel)` in `schemas.py` with fields aligned to the frontend Triple (`track_id, primary_profile_id, primary_profile_name, confidence_score, predicted_loudness_change, predicted_crest_change, predicted_centroid_change, weighted_profiles, alternative_profiles, reasoning, is_hybrid, created`). Add a `to_response(rec, track_id)` helper alongside `MasteringRecommendation.to_dict()` that fills `is_hybrid` and `track_id`. Use that helper in BOTH paths (`enhancement.py:432` + `recommendation_service.py:94`). Add `response_model=MasteringRecommendationResponse` to the REST endpoint.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-6: `audio_chunk_meta.seq` resets to 0 at every chunk boundary — the "monotonic across stream" promise (per #3189 + audit BE-NEW-48 docstring) was never actually delivered
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1410-1438` (`frame_seq` declared and incremented inside `_send_pcm_chunk`)
- **Status**: Partial-regression of BE-NEW-48 / #3506. The audit's BE-NEW-48 explicitly named two defects: (a) the frontend type missing `AudioChunkMetaMessage` — fixed; (b) "`frame_seq` is a LOCAL that resets to 0 every chunk — even if the frontend bound to it, it'd misfire at every chunk boundary." Defect (b) was never fixed. Issue #3774 (OPEN) tracks the consumer side ("frontend never validates the seq") but does not address the producer side (counter never made stream-monotonic).
- **Description**: `_send_pcm_chunk` declares `frame_seq = 0` as a local at line 1413, before its inner `_producer()` coroutine. The counter increments per frame within one chunk's call to `_send_pcm_chunk`, but every new chunk (every 10s in production) calls `_send_pcm_chunk` again with a fresh local — so `seq` jumps `0, 1, 2, ..., N-1, 0, 1, 2, ..., N-1` across chunk boundaries. The docstring at line 1410 ("Monotonic sequence counter for text+binary frame pairing. The client can use this to detect desync if frames are ever dropped or reordered (fixes #3189)") and the frontend type's JSDoc ("Monotonic sequence counter across the entire stream — clients can detect dropped or reordered frames by checking that seq increases by exactly 1 per frame") both promise stream-wide monotonicity. The code does not deliver it.
- **Evidence**:
  ```python
  # backend/core/audio_stream_controller.py:1410-1438 — local resets per chunk
  async def _send_pcm_chunk(self, websocket, pcm_samples, chunk_index, total_chunks, crossfade_samples):
      ...
      # Monotonic sequence counter for text+binary frame pairing.
      # The client can use this to detect desync if frames are ever
      # dropped or reordered (fixes #3189).
      frame_seq = 0                                   # ← reset on every chunk
      
      async def _producer():
          nonlocal frame_seq
          ...
          for frame_idx in range(num_frames):
              ...
              metadata = {
                  "type": "audio_chunk_meta",
                  "data": {
                      "seq": frame_seq,               # ← starts 0 at chunk boundary
                      ...
                  },
              }
              frame_seq += 1                          # ← bumps per frame within the chunk
  ```
  ```typescript
  // frontend/src/types/websocket.ts:484-498 — the JSDoc promise
  export interface AudioChunkMetaMessage extends WebSocketMessage {
    type: 'audio_chunk_meta';
    data: {
      /** Monotonic sequence counter across the entire stream — clients can
       *  detect dropped or reordered frames by checking that seq increases
       *  by exactly 1 per frame (fixes #3189). */
      seq: number;       // ← actually resets per chunk
      chunk_index: number;
      ...
    };
  }
  ```
- **Impact**: If the consumer side (#3774) ships as proposed — using `seq` to detect desync — it will trigger a false desync event at every 10-second chunk boundary in normal operation. The user-visible result would be a forced "restart from recovery_position" approximately every 10 seconds, defeating the purpose. The current state (no consumer) means the bug is dormant, but the contract docstring is wrong and will mislead the #3774 implementer.
- **Siblings**: #3780 (OPEN — `seq` vs `sequence` naming inconsistency between audio and analysis streams) sits adjacent — both should be coordinated. The audit BE-NEW-48 doc-cited "Two related fixes needed (define the type AND make the counter actually monotonic stream-wide)" — only the first happened.
- **Suggested Fix**: Hoist `frame_seq` to an instance attribute of `AudioStreamController` (`self._frame_seq = 0`) that's initialized in `__init__` and incremented inside `_send_pcm_chunk._producer()`. Reset it ONLY at `_send_stream_start` (i.e., at every new `audio_stream_start` boundary). That matches the JSDoc "across the entire stream" semantics and lets #3774's consumer-side detection actually work. If preferred, name the field clearly (`self._stream_frame_seq`) and document that it resets at stream start (not chunk start).

---

> _Dim 6 — Middleware & Config_

### BE-MW-4: `register_allowed_directory` has no inverse — removed scan folders remain in `_extra_allowed_dirs` until restart
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/security/path_security.py:29-36` + `routers/settings.py:118-129`
- **Status**: NEW
- **Description**: When a user adds a scan folder via `POST /api/settings/scan-folders`, the handler resolves and appends to module-level `_extra_allowed_dirs` (line 109). When the user removes the same folder via `POST /api/settings/scan-folders/delete`, the settings repo deletes the DB row, the auto-scanner is notified (line 123) — but **`_extra_allowed_dirs` is never modified**. There is no `unregister_allowed_directory()` function. The list grows monotonically per-process; any file under a previously-allowed directory continues to pass `validate_file_path()` until the next backend restart.
- **Evidence**:
  ```python
  # security/path_security.py:32-36 — only an "add" exists
  def register_allowed_directory(directory: Path) -> None:
      resolved = directory.resolve()
      if resolved not in _extra_allowed_dirs:
          _extra_allowed_dirs.append(resolved)
  # No corresponding `unregister_allowed_directory(directory)` exists.

  # routers/settings.py:118-129 — delete path doesn't touch _extra_allowed_dirs
  @router.post("/api/settings/scan-folders/delete")
  async def remove_scan_folder(body: _ScanFolderRequest) -> dict[str, Any]:
      settings = await asyncio.to_thread(_repo().remove_scan_folder, body.folder)
      await _notify_scanner()
      return {...}
  ```
- **Impact**: Removed folders remain implicitly trusted for `validate_file_path()` lookups during the session — `routers/metadata.py` validates `track.filepath` against this list five times per request (lines 117, 164, 219, 257, 315). On a desktop app the impact is low (single user, intentional choice), but it violates least-privilege: a user who removed `/mnt/external_drive` because they no longer want to scan it still finds the path implicitly allowed for direct serving.
- **Siblings**: Startup re-reads settings and registers fresh on every cold start (line 154-160), which means a restart auto-fixes the divergence. The dataset never accumulates indefinitely across restarts, only within a session.
- **Suggested Fix**: Add `unregister_allowed_directory(directory: Path) -> None` to `path_security.py` and call it from `routers/settings.py:remove_scan_folder` and `reset_settings`. Make `_extra_allowed_dirs` a `set[Path]` instead of a list so add/remove are O(1) and idempotent.

---

> _Dim 6 — Middleware & Config_

### BE-MW-5: `RateLimitMiddleware` 429 response bypasses `SecurityHeadersMiddleware` and `NoCacheMiddleware`
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware.py:151-158` + middleware registration at lines 178-208
- **Status**: NEW
- **Description**: Starlette applies middleware in reverse `add_middleware()` order, so the effective wrap is `CORSMiddleware( RateLimitMiddleware( SecurityHeadersMiddleware( NoCacheMiddleware( app ) ) ) )`. When rate limiting triggers, `RateLimitMiddleware.dispatch` short-circuits at line 154 with `return JSONResponse(...)` — it never calls `call_next(request)`. As a result the 429 response **never enters `SecurityHeadersMiddleware.dispatch`** which is where `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and `Content-Security-Policy` are added; nor does it pass through `NoCacheMiddleware` for the appropriate cache-control headers. The 429 is returned only with the explicit `Retry-After` header — CORS headers ARE added because CORS sits outermost.
- **Evidence**:
  ```python
  # config/middleware.py:154-158 — short-circuit
  return JSONResponse(
      status_code=429,
      content={"detail": "Too many requests"},
      headers={"Retry-After": str(retry_after)},
  )

  # Registration order (line 178-208):
  # add_middleware(NoCacheMiddleware)           ← innermost
  # add_middleware(SecurityHeadersMiddleware)
  # add_middleware(RateLimitMiddleware)         ← short-circuits BEFORE inner
  # add_middleware(CORSMiddleware)              ← outermost
  ```
- **Impact**: A throttled response is rendered without the documented browser security headers. Realistically the 429 body is small JSON and never user-controllable, so XSS / clickjacking risk is theoretical, but it violates the project's own header contract and any external CSP-compliance audit will flag it.
- **Siblings**: Same pattern would apply to any future middleware that short-circuits with a non-200 response above `SecurityHeadersMiddleware`. There are none today.
- **Suggested Fix**: Either (a) reorder so `SecurityHeadersMiddleware` and `NoCacheMiddleware` are registered AFTER `RateLimitMiddleware` (so they wrap it and run on the 429), or (b) add headers directly to the `JSONResponse(...)` literal. Option (a) is cleaner — just swap the order at lines 178-184.

---

> _Dim 6 — Middleware & Config_

### BE-MW-6: `path_security.validate_*` logs full resolved paths at INFO on every call — high-volume sensitive log
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/security/path_security.py:156, 226, 276`
- **Status**: NEW
- **Description**: All three validators (`validate_scan_path`, `validate_file_path`, `validate_user_chosen_directory`) log a successful-validation line at INFO with the full resolved path. `validate_file_path` is called 5x per `/api/metadata/tracks/{id}` request (one for each metadata field/picture/extract call in `routers/metadata.py:117, 164, 219, 257, 315`). On a typical session of playback + metadata editing this produces hundreds of INFO lines per minute, each containing the absolute filesystem path of the user's media library. The redactor pattern that exists in `sanitize_path_for_response()` (which converts `/home/user/Music/song.mp3` to `~/Music/song.mp3`) is NOT used in these log lines.
- **Evidence**:
  ```python
  # path_security.py:156
  logger.info(f"Path validation successful: {resolved_path}")
  # path_security.py:226
  logger.info(f"File path validation successful: {resolved_path}")
  # path_security.py:276
  logger.info(f"User-chosen directory validated: {resolved_path}")
  ```
- **Impact**: (1) Log noise dominates real INFO-level events; (2) The Electron `electron-log` captures stdout to disk under `~/.config/Auralis/logs/main.log`, so absolute paths to potentially-private music libraries land in a persisted file the user may not realize is collecting that data; (3) When users submit logs for bug reports, they unwittingly share their entire library layout. This is BE-NEW-83-adjacent (#3541 was about "don't leak server path in HTTPException details") — same class of issue but in logs instead of API responses.
- **Siblings**: `startup.py:91, 96` log the music dir and database path at INFO once at boot — acceptable. `routers/library.py:748` logs `"✓ Track found: {track.title} by {track.artists}"` at INFO per metadata fetch — also high-volume but no path. `routers/processing_api.py:188, 251` log `input_path` at INFO — same class.
- **Suggested Fix**: Drop the three `path_security.py` INFO lines to `logger.debug(...)`. If kept, use `sanitize_path_for_response(resolved_path)` so the home prefix is collapsed to `~/`. Same treatment for `processing_api.py:188, 251`.

---

> _Dim 6 — Middleware & Config_

### BE-MW-7: WebSocket origin allowlist accepts empty Origin header — non-browser local clients bypass check
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/globals.py:65-69`
- **Status**: NEW
- **Description**: The `connect()` method rejects connections whose Origin header is set but not in `ALLOWED_WS_ORIGINS`. **But empty origin is treated as a free pass** (line 66: `if origin and origin not in ALLOWED_WS_ORIGINS`). The inline comment says "Non-browser clients may not send Origin; we allow empty origins for compatibility" — the trade-off is intentional. On a localhost-only desktop this is largely fine, but any local process (Python script, `wscat`, browser extension talking to `ws://localhost:8765/ws` from outside a normal browser context) can connect and issue any WS command — including `play_enhanced`, `seek`, `subscribe_job_progress`. With no auth (#2206 was explicitly closed because the threat model is single-user desktop), the only defense is the origin check, which empty-origin clients skip.
- **Evidence**:
  ```python
  # config/globals.py:65-69
  origin = websocket.headers.get("origin", "").lower()
  if origin and origin not in ALLOWED_WS_ORIGINS:
      logger.warning(f"WebSocket connection rejected: untrusted origin {origin!r}")
      await websocket.close(code=1008)
      return
  ```
- **Impact**: Any local process can drive playback, scan the library, trigger fingerprinting, and observe player state via the WS. Severity is bounded by the localhost-only deployment, but if a future feature (LAN tunneling, mDNS sharing) ever exposes 8765 beyond loopback this becomes a CRITICAL hole.
- **Siblings**: Issue #3231 noted the rejection branch (code 4003 — actually 1008 in the current code) was never tested. The empty-origin acceptance branch is also untested.
- **Suggested Fix**: Either tighten the check to reject empty origins from non-loopback clients (`if not origin and websocket.client.host not in ("127.0.0.1", "::1"): close`), or add a `WS_REQUIRE_ORIGIN` env-var gate so packaging can flip it on for distributed builds. Add a regression test for both branches.

---

> _Dim 7 — Error Handling_

### BE-EH-3: `library_auto_scanner._run` outer crash-loop still broadcasts raw `str(exc)` (partial fix of #3543)
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:157-162`
- **Status**: NEW (sibling of CLOSED #3543 — the fix at line 263-275 sanitised only `_run_cycle`'s inner `scan_directories` exception path; the OUTER `_run` crash-loop broadcast was missed)
- **Description**: When `_run_cycle()` raises an unexpected exception (e.g., settings repo flake, `connection_manager_safe_broadcast` itself fails partway, watchdog OSError), the outer `except Exception as exc` broadcasts `{"error": str(exc)}` to every connected WebSocket. Inside `_run_cycle()` the analogous broadcast at line 268-274 was correctly refactored to `f"{type(exc).__name__} during library scan"`; the outer one (line 161) was left as-is.
- **Evidence**:
  ```python
  # services/library_auto_scanner.py:150-164
  async def _run(self) -> None:
      """Outer crash-safe loop."""
      while not self._stop_event.is_set():
          try:
              await self._run_cycle()
          except asyncio.CancelledError:
              raise
          except Exception as exc:
              logger.error(f"LibraryAutoScanner cycle failed: {exc}", exc_info=True)
              await connection_manager_safe_broadcast(
                  self._connection_manager,
                  {"type": "library_scan_error", "data": {"error": str(exc)}}   # ← still raw
              )
  ```
- **Impact**: Same blast radius as #3543: OS paths / mount points / permission detail leak to every connected client; tight crash-loop amplifies the noise.
- **Suggested Fix**: Mirror the line 268 form: `{"error": f"{type(exc).__name__} during library scan"}`.

---

> _Dim 7 — Error Handling_

### BE-EH-4: `audio_stream_controller._send_fingerprint_progress` leaks `str(e)` in `fingerprint_progress` WS message
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:402-414`
- **Status**: NEW
- **Description**: When fingerprint preparation (`fingerprint_generator.get_or_generate`) raises, the controller logs at warning level and then sends a `fingerprint_progress` WS event with `message=f"Fingerprint error: {str(e)}"`. The exception is typically `OSError`/`FFmpegError`/`np.linalg.LinAlgError` — `str(e)` includes the audio file's absolute path, ffmpeg stderr fragments, or numpy stack detail.
- **Evidence**:
  ```python
  # core/audio_stream_controller.py:402-414
  except Exception as e:
      logger.warning(f"Fingerprint preparation failed for track {track_id}: {e}, proceeding without optimization")
      if websocket:
          await self._send_fingerprint_progress(
              websocket,
              track_id=track_id,
              status="error",
              message=f"Fingerprint error: {str(e)}"   # ← leak
          )
  ```
- **Impact**: Same disclosure class as #2667 but on a different WS message type. Lower blast radius than `audio_stream_error` because fingerprint errors are rarer.
- **Suggested Fix**: `message=f"Fingerprint error: {type(e).__name__}"` and keep the full text in the server log.

---

> _Dim 7 — Error Handling_

### BE-EH-5: `ProcessingJob.to_dict()` re-leaks full `output_path` via `result_data` (regression-sibling of #3322)
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/processing_engine.py:98-116, 530-540`
- **Status**: NEW (regression-adjacent — #3322 sanitised `input_file`/`output_file` to `Path(...).name`, but `result_data["output_path"]` was missed)
- **Description**: `to_dict()` now correctly returns `Path(self.input_path).name` / `Path(self.output_path).name` for the top-level fields. But it also serialises `result_data` verbatim, and `result_data["output_path"] = job.output_path` (set at line 532) is the FULL server-side absolute path (e.g., `/tmp/auralis_processing/<job-uuid>_processed.wav`). GET `/api/processing/jobs` therefore still leaks the temp directory layout for any completed job.
- **Evidence**:
  ```python
  # core/processing_engine.py:530-540
  job.result_data = {
      "output_path": job.output_path,         # ← absolute path
      "sample_rate": int(sample_rate),
      ...
  }
  # core/processing_engine.py:98-116
  def to_dict(self) -> dict[str, Any]:
      """Exposes filenames only (no absolute paths) ... (#3322)."""
      return {
          ...
          "input_file": Path(self.input_path).name,
          "output_file": Path(self.output_path).name,
          ...
          "result_data": self.result_data,    # ← re-leaks output_path
          ...
      }
  ```
- **Impact**: Same blast radius as the original #3322 finding (server-side temp dir disclosure), only via a less-obvious carrier.
- **Suggested Fix**: When building `result_data`, store `"output_file": Path(job.output_path).name` instead of (or in addition to) `"output_path"`. Drop the absolute path entirely from the serialised dict; if internal code needs it, keep a separate non-serialised attribute.

---

> _Dim 7 — Error Handling_

### BE-EH-6: `routers/metadata.py:135, 180, 244` embed `FileNotFoundError` in 404 detail — leaks absolute filepath
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/metadata.py:134-135, 179-180, 243-244` (3 endpoints)
- **Status**: NEW
- **Description**: Each of the three metadata read endpoints catches `FileNotFoundError as e` and raises `HTTPException(status_code=404, detail=f"Audio file not found: {e}")`. `str(FileNotFoundError)` is `[Errno 2] No such file or directory: '/full/absolute/path/file.mp3'` — the 404 response body therefore contains the server filepath.
- **Evidence**:
  ```python
  # routers/metadata.py:132-138 (sibling at 179-183, 243-247)
  except HTTPException:
      raise
  except FileNotFoundError as e:
      raise HTTPException(status_code=404, detail=f"Audio file not found: {e}")   # ← leak
  except Exception as e:
      logger.error(f"Failed to get editable fields for track {track_id}: {e}")
      raise HTTPException(status_code=500, detail="Failed to get editable fields")
  ```
- **Impact**: Browser DevTools or any third-party client invoking these endpoints sees the full library path layout. Specifically same class as filesystem-path-leak issues #2107, #2270, #2479, all closed.
- **Siblings**: 3 sites in `routers/metadata.py` (lines 135, 180, 244); also `routers/webm_streaming.py:166, 287` already do the safe form (`f"Audio file not found for track {track_id}"`) so the canonical pattern exists.
- **Suggested Fix**: `raise HTTPException(status_code=404, detail=f"Audio file not found for track {track_id}")` — drop the `e`.

---

> _Dim 7 — Error Handling_

### BE-EH-7: `_safe_send` / `_safe_send_bytes` still detect WS-disconnect by `"close message" in str(e)` substring (partial fix of #3511)
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:304-309, 322-327`
- **Status**: NEW (sibling of CLOSED #3511 — the fix was applied only at lines 731/978/1751 outer handlers; the two helper methods still use the brittle substring)
- **Description**: `#3511` replaced the substring detection at the three outer `try/except`s with explicit `except WebSocketDisconnect:` but did NOT touch the two sender helper methods, which still classify a disconnect by matching the literal phrase "close message" in `str(e).lower()`. If Starlette ever rewords its `RuntimeError` (e.g., "websocket close message" → "cannot send after close"), these helpers will fall into the `else: logger.warning(...)` branch and spam the log on every normal disconnect.
- **Evidence**:
  ```python
  # core/audio_stream_controller.py:301-312
  try:
      await websocket.send_text(json.dumps(message))
      return True
  except RuntimeError as e:
      if "close message" in str(e).lower():   # ← brittle
          logger.debug(f"WebSocket closed during send: {e}")
      else:
          logger.warning(f"WebSocket send failed: {e}")
      return False
  # Same pattern at 322-327 in _safe_send_bytes
  ```
- **Impact**: Same class as the original #3511 (Starlette upgrade hazard); blast radius limited to log spam (these helpers don't raise either way, so behaviour stays correct).
- **Suggested Fix**: Replace the substring match with `if not self._is_websocket_connected(websocket): logger.debug(...); else: logger.warning(...)` — the helper already calls `_is_websocket_connected` at line 298, so the redundant guard is cheap.

---

> _Dim 7 — Error Handling_

### BE-EH-8: 6 long-lived background tasks still use bare `asyncio.create_task` (no `add_done_callback`) — silent task death (sibling of #3512)
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**:
  - `auralis-web/backend/core/state_manager.py:214` (`_position_update_task`)
  - `auralis-web/backend/core/streamlined_worker.py:61` (`_worker_task`)
  - `auralis-web/backend/services/self_tuner.py:113` (`tuning_task`)
  - `auralis-web/backend/services/library_auto_scanner.py:119` (`_task`)
  - `auralis-web/backend/analysis/fingerprint_queue.py:153` (`_worker_task`)
  - `auralis-web/backend/routers/system.py:149` (`heartbeat_task`)
- **Status**: NEW (sibling of CLOSED #3512 / BE-NEW-54 — the fix introduced `helpers.spawn_background_task` and migrated `_run_job`. The remaining long-lived background tasks were not migrated.)
- **Description**: `helpers.spawn_background_task(coro, name=...)` (lines 56-69 of `helpers.py`) is the canonical fire-and-forget helper since #3512. It attaches a `log_task_exception` done-callback so an unhandled exception raises a logged error rather than disappearing into asyncio's "never-retrieved" warning bucket. The six listed task creations remained on bare `asyncio.create_task`. Each loops on an outer `try/except`, so a bug INSIDE the loop body is caught — but if anything raises BEFORE the try (e.g., an import statement in `_position_update_loop` startup, or `asyncio.get_running_loop()` after loop shutdown) the task dies silently and the feature (position updates / cache worker / self-tune / scanner / fingerprint queue / heartbeat) stops working with no log entry.
- **Evidence**:
  ```python
  # core/state_manager.py:213-214
  if self._position_update_task is None or self._position_update_task.done():
      self._position_update_task = asyncio.create_task(self._position_update_loop())
  # services/self_tuner.py:113
  self.tuning_task = asyncio.create_task(self._tuning_loop())
  # ... 4 more identical sites
  ```
- **Impact**: Silent feature death on any unhandled exception that escapes the inner `while/try`. For the heartbeat task in particular, a silent death means stale WS connections never get evicted (issue #3521 prevention regresses).
- **Siblings**: All 6 listed sites.
- **Suggested Fix**: `from helpers import spawn_background_task` and replace `asyncio.create_task(coro)` with `spawn_background_task(coro, name="position_update")` (similar for each site). Take the `add_done_callback` out of `routers/enhancement.py:209-212` and switch to `spawn_background_task` as well, for consistency.

---

> _Dim 7 — Error Handling_

### BE-EH-9: `_process_chunk_only` per-chunk DSP has no `asyncio.wait_for` guard (sibling of #2747)
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1141`
- **Status**: NEW (sibling of CLOSED #2747 — that fix added a timeout to `ProcessingEngine.process_job`'s DSP path, but the streaming hot path was not similarly bounded)
- **Description**: Inside the streaming loop, every chunk goes through `await processor.process_chunk_safe(chunk_index, fast_start=...)` (line 1141) with no `wait_for` timeout. `process_chunk_safe` is offloaded to a thread, so a hung DSP call (e.g., due to a pathological audio buffer or a deadlock in the Rust DSP module) wedges the per-stream coroutine forever — pause/resume events stop working, the chunk-error recovery never fires, and the only way out is the client disconnecting (which is detected by the `_is_websocket_connected` check at the NEXT iteration).
- **Evidence**:
  ```python
  # core/audio_stream_controller.py:1141
  _chunk_path, pcm_samples = await processor.process_chunk_safe(chunk_index, fast_start=fast_start)
  ```
- **Impact**: A single corrupt chunk or DSP deadlock blocks the stream until WS disconnect. The semaphore slot is held while wedged, so 4 such wedges (the default `MAX_CONCURRENT_STREAMS=4`) starve all subsequent listeners. Logged at no severity — only `logger.debug` on cache miss.
- **Siblings**: Same pattern in `webm_streaming.py:354` (`processor.get_wav_chunk_path` is not wrapped in `asyncio.wait_for`).
- **Suggested Fix**: Wrap `process_chunk_safe` in `asyncio.wait_for(..., timeout=30.0)`; on `TimeoutError`, raise `chunk_error` to fall into the existing skip-failed-chunk recovery branch (which now correctly drains the look-ahead — #3493).

---

> _Dim 8 — Performance_

### BE-PF-4: `proactive_buffer.buffer_presets_for_track` constructs `ChunkedAudioProcessor` synchronously in an `async def` for each of 5 presets
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/proactive_buffer.py:55-64`
- **Status**: NEW
- **Description**: `buffer_presets_for_track` is `async def`. Inside, for each of `AVAILABLE_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]`, it constructs a `ChunkedAudioProcessor(track_id=..., filepath=..., preset=..., intensity=...)` directly without `asyncio.to_thread`. As noted in BE-PF-3, each construction does sync SoundFile open + MasteringTargetService.load_fingerprint + HybridProcessor init = 200-500 ms each. Across 5 presets = 1-2.5 s of event-loop stall before any await happens (the first await is `process_chunk_safe` at line 79).
- **Evidence**:
  ```python
  # core/proactive_buffer.py:55-79
  for preset in AVAILABLE_PRESETS:           # 5 presets
      processor = None
      try:
          processor = ChunkedAudioProcessor( # SYNC, 200-500ms each = up to 2.5s
              track_id=track_id,
              filepath=filepath,
              preset=preset,
              intensity=intensity
          )
          for chunk_idx in range(chunks_to_buffer):
              ...
              chunk_path, audio_array = await processor.process_chunk_safe(...)
  ```
- **Impact**: When `buffer_presets_for_track` is fired (after a track load, in background), it freezes the event loop for ~1-2.5s before the first `await`. Currently the call site (`main.py:130` `buffer_presets_fn=buffer_presets_for_track`) is injected but **no caller invokes it** (`grep buffer_presets_fn\\(` returns no in-tree matches). The function is dead code today, but the moment a follow-up wires it back in, every track click will stall. The dead-code state itself is also worth tracking as it indicates the proactive-buffering feature was disabled without removing the entry point.
- **Siblings**: BE-PF-3 (streamlined_worker), BE-PF-5 (FingerprintGenerator).
- **Suggested Fix**: Wrap the constructor in `await asyncio.to_thread(ChunkedAudioProcessor, track_id, filepath, preset, intensity)`. Same fix as `core/audio_stream_controller.py:592-601` already does for the streaming path. If the function is permanently dead, delete it instead.

---

> _Dim 8 — Performance_

### BE-PF-5: `FingerprintGenerator.get_or_generate` performs sync DB lookups and audio decode on the event loop
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:166, 191, 220`
- **Status**: NEW
- **Description**: `get_or_generate` is `async def`, called from `AudioStreamController._ensure_fingerprint_available` (line 370 of audio_stream_controller) and from `FingerprintQueue._worker_loop`. Three sync operations run directly on the event loop:
  1. Line 166: `fingerprint_repo.get_by_track_id(track_id)` — sync DB cache lookup.
  2. Line 191: `fingerprint_repo.add(track_id, fingerprint_data)` — sync DB write.
  3. Line 220: `audio, sample_rate = load_audio(filepath)` — sync full audio file decode (can be 200-500ms for a 3-min MP3 + ffmpeg launch).
- **Evidence**:
  ```python
  # analysis/fingerprint_generator.py:160-171
  try:
      repo_factory = self.get_repository_factory()
      fingerprint_repo = repo_factory.fingerprints
      fp_record = fingerprint_repo.get_by_track_id(track_id)    # SYNC DB
      ...
  ```
  ```python
  # analysis/fingerprint_generator.py:217-220
  try:
      logger.debug(f"Loading audio file: {filepath}")
      audio, sample_rate = load_audio(filepath)                  # SYNC full decode
  ```
- **Impact**: Two paths hit this:
  - **Stream startup**: `_ensure_fingerprint_available` runs before the first chunk is sent. The DB cache hit (line 166) stalls the loop for ~10-50ms; on miss, `load_audio` adds another ~200-500ms before the `to_thread` for Rust compute. That's added to the user-perceived first-chunk latency.
  - **Background `FingerprintQueue` worker**: each track in the queue starts with a sync DB+decode on the loop before its `to_thread`. With 50 enqueued tracks, that's 10-30 s of cumulative event-loop stalls during a background drain.
- **Siblings**: BE-PF-3, BE-PF-4.
- **Suggested Fix**: Wrap line 166 (`get_by_track_id`) and line 191 (`add`) in `asyncio.to_thread`. Move the entire "load_audio + transform + run_in_executor" block of `_generate_via_rust` inside one `to_thread` so the sync audio load + numpy work runs off the loop too.

---

> _Dim 8 — Performance_

### BE-PF-6: `AudioStreamController` instantiated fresh per `play_enhanced` request — per-stream `SimpleChunkCache` is never shared, cross-stream prefetch is impossible
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/system.py:358, 495, 711`; `core/audio_stream_controller.py:239` (cache_manager init)
- **Status**: NEW (architectural — sibling of BE-NEW-55)
- **Description**: Three of the four WebSocket handlers in `system.py` (`play_enhanced`, `play_normal`, and the seek path) construct a brand-new `AudioStreamController(...)` per request:
  ```python
  controller = AudioStreamController(
      chunked_processor_class=ChunkedAudioProcessor,
      get_repository_factory=get_repository_factory,
      get_enhancement_enabled=...,
  )
  ```
  The constructor (`AudioStreamController.__init__`, line 239) creates a fresh `SimpleChunkCache()` if no `cache_manager` is passed — and the callers don't pass one. As a result, the in-memory chunk cache is per-stream, not per-process. The same track replayed by the same client immediately after a stop produces 100% cache misses. The look-ahead prefetch (BE-NEW-55 was DISABLED in #3513 for exactly this reason — the prefetched chunk landed in a per-stream cache nobody else could see).
- **Evidence**:
  ```python
  # core/audio_stream_controller.py:238-241
  # Use provided cache manager or fallback to SimpleChunkCache
  self.cache_manager: StreamlinedCacheManager | SimpleChunkCache = (
      cache_manager or SimpleChunkCache()
  )
  ```
  ```python
  # routers/system.py:358-369 (also 495, 711) — three call sites, none pass cache_manager
  controller = AudioStreamController(
      chunked_processor_class=ChunkedAudioProcessor,
      get_repository_factory=get_repository_factory,
      get_enhancement_enabled=...
  )
  # → AudioStreamController.__init__ falls back to SimpleChunkCache()
  ```
- **Impact**:
  - **Cache miss on replay**: a user that scrubs back-and-forth or replays a track sees 100% cache misses on the second stream, even within seconds. With ~10 MB per cached chunk processed in ~500ms, repeated DSP work measurably impacts CPU and battery on the desktop.
  - **Look-ahead prefetch is permanently disabled** (per #3513 comment in audio_stream_controller.py line 715-723) until cache lifecycle is fixed. The annotation literally says: "Re-enable once the cache manager is hoisted to a process-wide singleton."
  - The constructor also rebuilds the `FingerprintGenerator` on every play_enhanced (line 244-261). The constructor itself is cheap (no I/O), but it does a sync `factory.session_factory` access + 1 attribute check; mostly OK, but wastes allocation.
- **Siblings**: BE-NEW-55 (filed and closed as "prefetch disabled until cache lifecycle fixed"); BE-NEW-57 (processor cache; fixed with `_PROCESSOR_CACHE_MAX = 32` LRU).
- **Suggested Fix**: Hoist `AudioStreamController` to a process-wide singleton (similar to `_global_processor_factory` in processor_factory.py). Each WebSocket call passes its own `websocket` to the controller method, not its own controller. The controller's `self.active_streams: dict[str, Any]` and `self._chunk_tails: dict[int, np.ndarray]` are already keyed by `ws_id(websocket)` / `track_id` and lock-protected, so a singleton is feasible. Alternatively, pass the lifespan-owned `StreamlinedCacheManager` (already a singleton in `globals_dict['cache_manager']`) explicitly to the constructor at every call site.

---

> _Dim 8 — Performance_

### BE-PF-7: `routers/playlists.py:add_tracks_to_playlist` does N×`await asyncio.to_thread(repos.playlists.add_track, ...)` — regression of #3560
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/playlists.py:273-275`
- **Status**: Regression of #3560 (closed 2026-05-25 with no diff)
- **Description**: `POST /api/playlists/{playlist_id}/tracks` accepts a list of track IDs and inserts them via:
  ```python
  for track_id in request.track_ids:
      if await asyncio.to_thread(repos.playlists.add_track, playlist_id, track_id):
          added_count += 1
  ```
  This is N round-trips to the thread pool + N independent INSERTs, one per track. The closed issue #3560 ("[2026-05-25] LOW - `POST /api/playlists/{id}/tracks` does N×`add_track` sequentially via `asyncio.to_thread`") was marked closed without any code change to playlists.py — `git log -- auralis-web/backend/routers/playlists.py` shows the most recent commit is `f3ae9593` (raw-exception cleanup, 2026-05-25) that does NOT touch this loop.
- **Evidence**:
  ```bash
  $ git log --oneline -- auralis-web/backend/routers/playlists.py | head -3
  f3ae9593 fix: remove raw exception strings from HTTP 500 response details (#2736)
  89eb4102 fix: offload all sync repository calls to thread pool in async routers
  350256f5 fix: align playlist WebSocket message types between backend and frontend
  ```
  None of these added a batch insert.
- **Impact**: For a typical 20-track album drag-and-drop: 20 × ~30ms = 600ms latency, plus 20× the to_thread overhead and 20× the SQLAlchemy session open/commit cycle. Bigger lists (full playlists, ~150 tracks) cross the 5s threshold the frontend uses for "timed out, retry."
- **Siblings**: BE-PF-8 (metadata batch update has the same pattern).
- **Suggested Fix**: Add `PlaylistRepository.add_tracks(playlist_id: int, track_ids: list[int]) -> int` that builds a single `INSERT INTO playlist_tracks ... VALUES (...)` for all IDs, then call once: `added_count = await asyncio.to_thread(repos.playlists.add_tracks, playlist_id, request.track_ids)`. Pattern matches the batched `repos.tracks.get_by_ids` introduced by #3228.

---

> _Dim 8 — Performance_

### BE-PF-8: `routers/metadata.py:batch_update_metadata` does N+1 sequential DB lookups in async loop — regression of #3561
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/metadata.py:305-309, 344-346`
- **Status**: Regression of #3561 (closed 2026-05-25 with no diff)
- **Description**: `POST /api/metadata/batch-update` iterates `request.updates` and for each one does:
  ```python
  for update_req in request.updates:
      track = await asyncio.to_thread(repos.tracks.get_by_id, update_req.track_id)   # 1 query per track
      ...
  # later, after batch_update returns:
  for result in results.get('results', []):
      ...
      updated_track = await asyncio.to_thread(
          lambda tid=track_id, u=updates: repos.tracks.update_metadata(tid, **u)     # 1 query per update
      )
  ```
  Issue #3561 was marked closed without a code change.
- **Evidence**:
  ```bash
  $ git log --oneline -- auralis-web/backend/routers/metadata.py | head -5
  6d8d6ac4 fix: HTTPException handling — don't let broad `except Exception` swallow nested 503
  d6017b35 ...
  ```
  No batched lookup commit. The N+1 pattern at lines 305-309 and 344-346 is unchanged.
- **Impact**: For a 50-track tag-editor save: 50 × ~15ms DB queries + 50 × ~20ms updates ≈ 1.75 s of cumulative thread-pool churn. UX-wise, the frontend's "Saving..." dialog stays up for that long.
- **Siblings**: BE-PF-7 (playlists batch add). Same root cause.
- **Suggested Fix**: Replace line 306 with a single `tracks_map = await asyncio.to_thread(repos.tracks.get_by_ids, [u.track_id for u in request.updates])` before the loop. Pre-derive `track = tracks_map.get(update_req.track_id)` inside the loop. For the second loop (line 344-346), add a `repos.tracks.update_metadata_batch(list_of_updates)` repository method.

### LOW (6)

---

> _Dim 9 — Test Coverage_

### BE-TC-3: `tests/backend/test_websocket_protocol_b3.py` (514 LOC) — 95% of file is skipped tests referencing never-merged classes, kept only for 8 `HeartbeatManager` tests at lines 258-330
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_websocket_protocol_b3.py:1-514`
- **Status**: Regression of #3517 (file was not gutted; collection error was patched by adding a skip)
- **Description**: Issue #3517 reported that this file imported `MessagePriority`, `MessageType`, `RateLimiter`, `WebSocketProtocol`, `WSMessage`, `ConnectionInfo` — none of which exist. The fix downgraded to a `pytestmark = pytest.mark.skip("Tests reference B.3 protocol classes ... never merged ...")` at the module/class level (still visible in the file: `class TestWSMessage`, `msg = WSMessage(type=MessageType.PING)` lines still present, just skipped). The 8 valid HeartbeatManager tests are still present but the remaining ~480 LOC is dead weight that pollutes the test inventory, breaks CI cache invalidation reasoning, and looks like real coverage in reports/IDEs. The intended fix per the audit ("Gut the file down to the 8 valid `TestHeartbeatManager` tests") was not done — the closure was cosmetic.
- **Evidence**: `wc -l tests/backend/test_websocket_protocol_b3.py` = 514. The `grep` shows references to `WSMessage(type=MessageType.PING)`, `ConnectionInfo`, `RateLimiter`, `WebSocketProtocol` are still present in the file (in `class TestWSMessage`, `class TestConnectionInfo`, `class TestRateLimiter`, `class TestWebSocketProtocol`). Only `from websocket.websocket_protocol import HeartbeatManager` actually imports something real.
- **Impact**: Coverage reports that count test files / LOC will overstate WS protocol coverage. Future grep-based audits will find this file and assume HeartbeatManager + WSMessage/RateLimiter/etc. are all tested. Mental-model drift for any developer reading the file.
- **Siblings**: None at this scale, but a periodic search for `pytest.mark.skip("...")` on top-level classes/modules might find similar dead files.
- **Suggested Fix**: Delete `class TestWSMessage`, `class TestConnectionInfo`, `class TestRateLimiter`, `class TestWebSocketProtocol`, `class TestMessagePriority` and their helper imports. Leave only `class TestHeartbeatManager` (lines ~258-330) and rename the file to `test_heartbeat_manager.py`. Net reduction: ~480 LOC.

---

> _Dim 9 — Test Coverage_

### BE-TC-4: 5-6 of 14 WebSocket message types in `system.py` still have no real `TestClient.websocket_connect("/ws")` round-trip — `play_normal`, `resume`, `heartbeat`, `buffer_full`, `buffer_ready`, `pong`
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/system.py:209-635` (handler dispatch); `tests/backend/test_system_api.py` (covers only 8 of 14 msg types via real WS)
- **Status**: Regression of #3516 (closed without the missing tests being added)
- **Description**: `system.py`'s `websocket_endpoint` dispatches on `message.get("type")` for 14 types: `pong`, `heartbeat`, `processing_settings_update`, `ab_track_loaded`, `play_enhanced`, `play_normal`, `pause`, `resume`, `buffer_full`, `buffer_ready`, `stop`, `seek`, `subscribe_job_progress`, (plus `ping` as a sentinel pre-check). `test_system_api.py` tests via real `client.websocket_connect("/ws")` only: `ping`, `processing_settings_update`, `ab_track_loaded`, `play_enhanced` (and its preset/intensity/missing-track_id variants), `pause`, `stop`, `seek`, `subscribe_job_progress`. The remaining branches — `play_normal` (entire unenhanced playback path: 100 LOC at `system.py:463-562`), `resume` (582-594), `heartbeat` (212-214), `buffer_full` (596-603), `buffer_ready` (605-611), and `pong` (209-210) — are exercised only by `test_websocket_flow_control.py` which manipulates `asyncio.Event` objects in isolation (not via the handler) and `test_websocket_task_orphan_race.py` which simulates the task-creation pattern without going through `websocket_endpoint`. The original audit (#3516) was closed without these tests being added.
- **Evidence**: `grep '"type":' tests/backend/test_system_api.py` returns only ping, processing_settings_update, ab_track_loaded, play_enhanced, pause, stop, seek, subscribe_job_progress. Handler dispatch at `system.py:209, 212, 216, 227, 238, 463, 564, 582, 596, 605, 613, 635, 781` covers 13 elif branches.
- **Impact**: The entire `play_normal` code path — buffer setup, chunk loading, send-queue management, flow-control event registration, disconnect cleanup — has no real-handler test. Regression of `play_normal` (e.g., a state-manager push missing a `state` field, a buffer-pause never being cleared, an unenhanced chunk being sent to the enhanced encoder) would not be caught. Same for the buffer_full/buffer_ready flow-control round-trip and the heartbeat liveness response.
- **Siblings**: None — `play_enhanced` is the only fully-tested high-bandwidth handler.
- **Suggested Fix**: Add 5 tests in `TestPlaybackControl` and `TestFlowControl` classes that send each message via real WS connect and assert: `play_normal` produces a `playback_started` or `audio_chunk_meta` frame; `resume` produces `playback_resumed`; `heartbeat` updates `_last_heartbeat[ws_id]` (mock-spy); `buffer_full` clears `_stream_flow_events[ws_id]`; `buffer_ready` sets it. Each test is ~20 LOC.

---

> _Dim 9 — Test Coverage_

### BE-TC-5: `NavigationService` (204 LOC) and `RecommendationService` (164 LOC) — both instantiated for every `player.py` request — have no dedicated unit tests
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/services/navigation_service.py:1-204`, `auralis-web/backend/services/recommendation_service.py:1-164`; instantiated at `auralis-web/backend/routers/player.py:240-253`
- **Status**: Regression of #3518 (closed; tests for `QueueService` and `PlaybackService` were added but the other two services were not)
- **Description**: Issue #3518 flagged 4 services as untested: `QueueService`, `PlaybackService`, `RecommendationService`, `NavigationService`. The first two received regression tests (`tests/regression/test_queue_service_set_queue.py`, `tests/regression/test_playback_service_concurrency.py`). The latter two received no tests at all (`grep -rl "NavigationService\|RecommendationService" tests/` returns zero matches). Both are wired into the player router and called on every queue/navigation operation — `play_next`/`play_previous`/`add_track`/`get_recommendations`. The issue was closed without them being addressed.
- **Evidence**: `grep -rlE "NavigationService|RecommendationService" /mnt/data/src/matchering/tests/` → no output. `routers/player.py:240-253` instantiates both via factory fns called on every request.
- **Impact**: Bugs in track-info hydration, "play next" target selection, recommendation ordering, or the broadcast wrapper would not be caught. The blast radius is the entire navigation path: every "skip", "previous", "add to queue", and recommendation request goes through these.
- **Siblings**: `LibraryAutoScanner` (426 LOC) at `services/library_auto_scanner.py` also has no dedicated tests (instantiated at `config/startup.py`); `SelfTuner` (347 LOC) but it appears to be unused.
- **Suggested Fix**: Add `tests/backend/test_navigation_service.py` and `tests/backend/test_recommendation_service.py`. Use the existing `mock_repository_factory_callable` fixture. ~6-8 tests per service covering: `__init__`, primary methods, edge cases (empty queue, missing track, connection-manager errors).

---

> _Dim 9 — Test Coverage_

### BE-TC-6: No real WS-reconnect-mid-stream test — the audit prompt's "concurrency: WS reconnects mid-stream" requirement has no coverage
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/system.py:319-562` (play_enhanced / play_normal disconnect-cleanup paths); `auralis-web/backend/core/audio_stream_controller.py` (controller per-WS state)
- **Status**: NEW
- **Description**: The prompt asks for "WS reconnects mid-stream" coverage. There are tests for *disconnect* mid-stream (`test_audio_stream_lifecycle.py::test_disconnect_mid_stream_stops_processing` at line 357, `test_disconnect_mid_stream_stops_reading` at 486, `test_audio_stream_crossfade.py:352`, `test_stream_disconnect_toctou.py`), but none simulate the *reconnect-after-disconnect* sequence. The handler at `system.py:319-562` has explicit `is_seek` handling for the reconnect case (per the comment "without the flag every WS reconnect produces an audible..." at `test_audio_stream_lifecycle.py:575`) but no test actually exercises that branch through `client.websocket_connect("/ws")` twice for the same `track_id`.
- **Evidence**: `grep -nE "reconnect|reconnection|connect_again|ws_reconnect"` across `tests/backend/` returns only a single line — a doc comment, not a test.
- **Impact**: Regression of the `is_seek` reconnect handling, of per-WS state cleanup on first disconnect (so the second connect gets fresh state), of the buffer-flush behaviour on reconnect, or of the global `_active_streaming_tasks` map's idempotent pop semantics under reconnect would not be caught.
- **Siblings**: None — disconnect-only coverage exists but reconnect-cycle does not.
- **Suggested Fix**: Add `test_audio_stream_reconnect.py` with one test that: (1) opens WS, sends `play_enhanced` for track X, reads N chunks, (2) closes WS, (3) opens new WS, sends `play_enhanced` for the same X (or X with `is_seek=True`), asserts second stream starts cleanly. ~30 LOC.

---


## LOW (72)

> _Dim 1 — Route Handlers_

### BE-RH-11: `processing_api.py` uses a module-level `_processing_engine` global with a setter — should be `Depends()`
- **Severity**: LOW
- **Dimension**: Route Handlers (DI antipattern)
- **Location**: `auralis-web/backend/routers/processing_api.py:58-64`
- **Status**: NEW
- **Description**: `_processing_engine: ProcessingEngine | None = None` plus `set_processing_engine(engine)` is the only router in the suite that uses a module-level mutable for DI. Every handler does `if not _processing_engine: raise HTTPException(503, ...)`. All other routers go through factory closures (`get_processing_engine: Callable[..., Any]`). Pattern mismatch + harder to test in isolation (test must monkeypatch the module global rather than override a dependency).
- **Suggested Fix**: Convert to `create_processing_router(get_processing_engine)` factory matching the rest of the suite.

---

> _Dim 1 — Route Handlers_

### BE-RH-12: `playlists.py` has zero `response_model=` on 8 endpoints — extends BE-NEW-49
- **Severity**: LOW
- **Dimension**: Route Handlers (Schema documentation)
- **Location**: `auralis-web/backend/routers/playlists.py:71, 95, 126, 171, 219, 255, 299, 337`
- **Status**: Existing: regression-class of BE-NEW-49 (filed 2026-05-25 — open, not yet addressed for this router)
- **Description**: `playlists.py` returns raw `dict[str, Any]` from all 8 handlers. No `response_model=`. The 8 broadcast `data` payloads are still ad-hoc dicts that the frontend reads defensively. Frontend `playlistService.ts` types the responses but with `as TypedResponse` casts — no runtime validation.
- **Impact**: As BE-NEW-49 — no OpenAPI documentation, no runtime schema validation, schema drift goes unnoticed at write-time.
- **Suggested Fix**: Define `PlaylistResponse`, `PlaylistsListResponse`, `PlaylistOperationResponse`. Add `response_model=` to each handler.

---

> _Dim 1 — Route Handlers_

### BE-RH-13: `library.py` returns raw `dict[str, Any]` on 13 of 15 handlers — extends BE-NEW-49
- **Severity**: LOW
- **Dimension**: Route Handlers (Schema documentation)
- **Location**: `auralis-web/backend/routers/library.py` (every `@router` decorator)
- **Status**: Existing: regression-class of BE-NEW-49 (open). Only `library.py` does NOT have `response_model=` declarations on any handler.
- **Description**: 15 handlers (refresh-references, stats, tracks list, favorites, single track, favorite POST/DELETE, lyrics, artists list, single artist, single album, scan, fingerprints/status, track fingerprint, reset) all return raw `dict[str, Any]`. The scan handler alone has 7 keys (`files_found`, `files_added`, ...) that the frontend type expects — drift between backend and frontend types is invisible to OpenAPI tooling.
- **Suggested Fix**: Reuse `LibraryStatsResponse`, `TrackResponse`, `ScanResultResponse` from `schemas.py` (or create them). Migrate one handler at a time.

---

> _Dim 1 — Route Handlers_

### BE-RH-14: `albums.py` returns `Any` from every handler — `response_model=` missing on all 4 endpoints
- **Severity**: LOW
- **Dimension**: Route Handlers (Schema documentation)
- **Location**: `auralis-web/backend/routers/albums.py:48, 92, 131, 173`
- **Status**: Existing: regression-class of BE-NEW-49 (open). `artists.py` was fully migrated to typed responses; `albums.py` was not.
- **Description**: Signatures are `-> Any` with bare `dict` returns. No `response_model=`. Compare with `artists.py:98-105` which uses `response_model=ArtistsListResponse` and typed return.
- **Suggested Fix**: Mirror `artists.py` — declare `AlbumResponse`, `AlbumsListResponse`, `AlbumTracksResponse`, `AlbumFingerprintResponse` Pydantic models and add `response_model=`.

---

> _Dim 1 — Route Handlers_

### BE-RH-15: `artwork.py` returns raw `dict[str, Any]` on 3 mutation endpoints
- **Severity**: LOW
- **Dimension**: Route Handlers (Schema documentation)
- **Location**: `auralis-web/backend/routers/artwork.py:167, 218, 260`
- **Status**: Existing: regression-class of BE-NEW-49 (open).
- **Description**: `POST /extract`, `DELETE`, `POST /download` all return `{message, artwork_url, album_id}` as a raw dict. No `response_model=`.
- **Suggested Fix**: Define `ArtworkOperationResponse` shared across the three endpoints.

---

> _Dim 1 — Route Handlers_

### BE-RH-16: `metadata.py` handlers declare `-> dict[str, Any]` despite request having Pydantic models — response side is naked
- **Severity**: LOW
- **Dimension**: Route Handlers (Schema documentation)
- **Location**: `auralis-web/backend/routers/metadata.py:94, 141, 186, 282`
- **Status**: Existing: regression-class of BE-NEW-49 (open).
- **Description**: Requests have `MetadataUpdateRequest`/`BatchMetadataRequest`, but all 4 responses are raw dicts.
- **Suggested Fix**: Define `EditableFieldsResponse`, `TrackMetadataResponse`, `MetadataUpdateResponse`, `BatchMetadataResponse`.

---

> _Dim 1 — Route Handlers_

### BE-RH-17: `files.py` `upload_files` and `get_supported_formats` lack `response_model=`
- **Severity**: LOW
- **Dimension**: Route Handlers (Schema documentation)
- **Location**: `auralis-web/backend/routers/files.py:89, 246`
- **Status**: Existing: regression-class of BE-NEW-49 (open).
- **Description**: Both return raw dicts. The upload result envelope (`{results: list[dict]}`) is consumed by `frontend/src/services/processingService.ts` but the per-item shape (`{filename, status, message, ...}`) is undocumented.
- **Suggested Fix**: Define `UploadResultItem` and `UploadResponse`; same for `AudioFormatsResponse`.

---

> _Dim 1 — Route Handlers_

### BE-RH-18: `system.health_check`, `system.get_version`, and seek/pause/resume WS broadcasts have no response or message schema
- **Severity**: LOW
- **Dimension**: Route Handlers (Schema documentation)
- **Location**: `auralis-web/backend/routers/system.py:70-76, 78-111`
- **Status**: NEW
- **Description**: `/api/health` and `/api/version` return raw dicts. The version fallback dict has 11 fields hardcoded — none typed. The `/ws` WS message constants (broadcasts at lines 577-583, 591-594, 630-633, 690-696) are inline JSON dicts with no schema reference. The `WebSocketMessageType` enum in `schemas.py` is inbound-only (BE-NEW-93 already filed).
- **Suggested Fix**: `HealthResponse`/`VersionResponse` Pydantic models. WS outbound messages handled as part of the BE-NEW-93 follow-up.

---

> _Dim 1 — Route Handlers_

### BE-RH-19: `library.scan_library` `_progress_callback` swallows `KeyError`/`TypeError` from malformed `progress_data` — falls back to "discovering"
- **Severity**: LOW
- **Dimension**: Route Handlers (Robustness)
- **Location**: `auralis-web/backend/routers/library.py:538-558`
- **Status**: NEW
- **Description**: The closure reads `progress_data.get('total_found', 0) or progress_data.get('processed', 0)`. If `progress_data` is something other than a dict (a bug in the scanner), `.get` raises `AttributeError` — but the closure runs in a separate thread, with no try/except. The exception will be silently swallowed by `asyncio.run_coroutine_threadsafe`'s future and not visible to operators unless they enable debug logging.
- **Impact**: A scanner bug emits malformed progress data → frontend stops getting updates with no error trail.
- **Suggested Fix**: Wrap the broadcast call in `try/except Exception: logger.warning("progress callback failed", exc_info=True)`.

---

> _Dim 1 — Route Handlers_

### BE-RH-20: `enhancement.get_mastering_recommendation` runs full `ChunkedAudioProcessor` instantiation + analysis with no auth, no rate limit, no track-already-analysed check
- **Severity**: LOW
- **Dimension**: Route Handlers (Resource consumption / endpoint hygiene)
- **Location**: `auralis-web/backend/routers/enhancement.py:375-443`
- **Status**: NEW
- **Description**: `GET /api/player/mastering/recommendation/{track_id}` triggers a fresh `ChunkedAudioProcessor` instantiation + `proc.get_mastering_recommendation()` (which runs a full audio decode + analysis). Each call costs ~1-5 seconds of CPU and ~100 MB of allocations. The handler has no rate limit, no caching against `MasteringTargetService.cache` (per BE-NEW-99 the Tier-1 lookup is dead anyway), and no `If-Modified-Since`-style check. A misbehaving client can pin one worker per second of activity.
- **Impact**: DoS-by-curiosity — a script that polls the recommendation endpoint for a long-running track triggers re-analysis every call.
- **Siblings**: BE-NEW-95 (`RecommendationService.generate_and_broadcast_recommendation` same issue via BackgroundTasks).
- **Suggested Fix**: Cache the recommendation by `(track_id, fingerprint_signature, confidence_threshold)` in `MasteringTargetService.cache` (fixing BE-NEW-99 in the same pass would unblock the Tier-1 path). Return cached results when present; only run analysis on miss.

---

> _Dim 1 — Route Handlers_

### BE-RH-21: `system.health_check` accepts no parameters but is missing GET-only enforcement — accepts any method per default APIRouter routing? (verify)
- **Severity**: LOW (verification — likely no-op)
- **Dimension**: Route Handlers (Verification)
- **Location**: `auralis-web/backend/routers/system.py:70`
- **Status**: NEW (low-confidence; flagged for verification)
- **Description**: `@router.get("/api/health")` is correctly restricted to GET by FastAPI. Re-read confirms — no issue. Including this entry as a no-op so the next auditor can verify the others.
- **Suggested Fix**: None — included for traceability.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-5: `HeartbeatManager.mark_pong` does not verify the pong corresponds to an outstanding ping — silent acceptance of stale pongs
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/websocket/websocket_protocol.py:40-53`; usage at `routers/system.py:210-214`
- **Status**: NEW
- **Description**: `HeartbeatManager.pending_pongs[connection_id]` holds a single timestamp — when the heartbeat task sends ping, it sets `pending_pongs[id] = now`. When the client pongs, `mark_pong` reads `pending_pongs[id]`, computes elapsed, deletes the entry. There is no token / nonce to bind the pong to the most-recent ping. The receive loop in `system.py` also calls `mark_pong` on type `"heartbeat"` messages (line 214), treating those as "proof of life" — but those clients send `heartbeat` on a 30 s independent timer (`RealTimeAnalysisStream.startKeepalive`) UNRELATED to the server's ping/pong. A client whose connection has actually died between two heartbeats but who recently sent a "heartbeat" frame will appear alive to `is_stale()` until the NEXT ping cycle, doubling the dead-connection eviction time.
- **Evidence**: `mark_pong` (line 40-53) blindly deletes `pending_pongs[id]` and reports the elapsed-since-ping; if no ping is outstanding (`if connection_id not in self.pending_pongs`), it returns False — but `pending_pongs` is also wiped by EVERY `mark_pong` call, so a stream of `heartbeat` keepalives can clear a freshly-armed `pending_pongs` slot before the actual pong arrives. Worse: nothing checks the return value of `mark_pong` (system.py lines 210, 214 discard it).
- **Impact**: Stale-connection detection window is up to 60 s instead of the documented 30 s. Doesn't drop audio, but delays cleanup of zombie sockets on flaky networks.
- **Siblings**: None.
- **Suggested Fix**: Either (a) include a monotonic ping_id in each ping frame and require pong to echo it, then store `pending_pongs[id] = ping_id`; or (b) at minimum, do not clear `pending_pongs` on receipt of `heartbeat` — only on `pong`. The system.py change is a one-liner: drop `heartbeat.mark_pong(connection_id)` from line 214 (let `heartbeat` keep its own timer untouched; the receive_text return value already proves liveness for the receive loop's perspective).

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-6: `ConnectionManager.broadcast` iterates connections serially — one slow client blocks broadcasts to every other connected client
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/config/globals.py:94-122`
- **Status**: NEW
- **Description**: `broadcast` snapshots `active_connections`, then awaits `connection.send_text(...)` sequentially in a for loop. A single client with a backed-up TCP send buffer (sleeping laptop, Wi-Fi handoff) blocks the entire broadcast — every subsequent client's state update is delayed until that client either drains or `send_text` raises. Per project memory, Auralis is desktop-only with typically one connected client, so this is theoretical for production. But the codebase repeatedly assumes multi-client mirroring (`set_volume`, `pause`, `playback_started/stopped` broadcasts — see `PlaybackService` comments at lines 304-318), so the policy is contradictory.
- **Evidence**:
  ```python
  message_json = json.dumps(message)
  for connection in connections_snapshot:
      try:
          await connection.send_text(message_json)
      except Exception as e:
          stale_connections.append(connection)
  ```
- **Impact**: With a frozen client, ALL other clients see N×latency state updates. Audio streaming is per-connection so audio is fine. Desktop deployment cap of 1-2 connections means this rarely manifests.
- **Siblings**: None.
- **Suggested Fix**: Use `asyncio.gather(*[connection.send_text(message_json) for connection in connections_snapshot], return_exceptions=True)`; mark connections whose result is an exception as stale. Adds parallelism with a one-line change.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-7: `_send_pcm_chunk.frame_seq` resets to 0 every chunk; comment claims "monotonic" but only monotonic WITHIN one chunk
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1410-1438`
- **Status**: Existing: #3780 (OPEN), Existing: #3774 (OPEN — frontend never validates)
- **Description**: The producer sets `frame_seq = 0` per call to `_send_pcm_chunk`, then increments through the frames of THAT chunk. So `seq` is monotonic per-chunk, not per-stream. The comment at line 1410-1412 ("Monotonic sequence counter for text+binary frame pairing. The client can use this to detect desync if frames are ever dropped or reordered") implies stream-wide monotonicity. Frontend code (`RealTimeAnalysisStream.ts:262-267`) checks `data.sequence` (different field name AND different stream) and `usePlayEnhanced.ts` does not consume the seq at all. Outdated comment + emitted-but-unread field = dead instrumentation.
- **Evidence**: `frame_seq = 0` reset (line 1413); `"seq": frame_seq` emit (line 1428); frontend never reads `audio_chunk_meta.seq` (#3774).
- **Impact**: Wire bandwidth waste (4 bytes per audio_chunk_meta frame × ~10 frames per chunk × duration), false sense of safety from desync.
- **Siblings**: #3780 (field-naming consistency), #3774 (frontend validation gap).
- **Suggested Fix**: Tracked in existing OPEN issues — fix in concert: rename to `sequence`, move counter to per-stream (closure-level), and add frontend consumer.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-8: `subscribe_job_progress` callback closure captures the websocket, never validated against multiple subscriptions for the same job
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:781-809`; `core/processing_engine.py:227-235`
- **Description**: Each call to `subscribe_job_progress` defines a new `progress_callback` and `register_progress_callback(job_id, callback)` stores it in a single-value dict (`processing_engine.progress_callbacks[job_id] = callback`). Two clients (or one client subscribing twice) for the same job_id overwrite each other's callback — only the most recent subscriber receives `job_progress` events. Per-job N:1 subscription model is undocumented and inconsistent with the rest of the WS API (broadcast-style for `processing_settings_applied`, `playback_*`).
- **Status**: NEW
- **Impact**: Desktop-only deployment with one client → no real-world manifestation. Multi-window Electron or testing scenarios would lose progress events for all but the latest subscriber.
- **Suggested Fix**: Make `progress_callbacks` a `dict[str, list[Callable]]` and notify all registered callbacks; unregister specific instances rather than wholesale.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-9: Receive loop's `mark_pong` treats client `heartbeat` frames as pong proof, polluting pending-pong state
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:212-214`
- **Status**: NEW (consolidates with BE-WS-5)
- **Description**: `elif message.get("type") == "heartbeat": heartbeat.mark_pong(connection_id)`. The receive loop conflates "keepalive sent by RealTimeAnalysisStream" with "pong to the heartbeat manager's ping". `mark_pong` always deletes `pending_pongs[id]`, so a client's 30-second keepalive can clear an outstanding ping timer set 200 ms earlier — defeating the staleness detection.
- **Impact**: Same as BE-WS-5: delayed detection of half-open WS connections.
- **Siblings**: BE-WS-5 (same root cause from the heartbeat side).
- **Suggested Fix**: Drop the `mark_pong` call from the `heartbeat` branch — let the protocol's `pong` reply (line 210) be the sole source of liveness proof.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-10: Heartbeat task `await websocket.send_text(json.dumps({"type": "ping"}))` is not protected by `_is_websocket_connected` — race with disconnect causes noisy stack traces
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:144-147`
- **Status**: NEW
- **Description**: `_heartbeat_loop` sends ping with bare `await websocket.send_text(...)`. If the WS just disconnected, Starlette raises `RuntimeError("Cannot call 'send' once a close message has been sent.")`. The except clause matches any Exception and returns without logging, so this is functionally safe — but RuntimeError is not the same as a clean close, and silent swallowing of all `Exception` hides other genuine bugs (encoder errors, oversized payloads). The streaming-controller `_safe_send` does this correctly: it calls `_is_websocket_connected` first AND distinguishes "close message" RuntimeError from other failures.
- **Impact**: Cleaner logs, lower bug visibility risk.
- **Suggested Fix**: Use `AudioStreamController._safe_send` (refactor it onto the module surface) or inline the same `_is_websocket_connected` pre-check.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-11: `validate_and_parse_message` uses `id(websocket)` for rate-limit log keys despite #3181 / `ws_id` UUID fix
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/websocket/websocket_security.py:67-90, 100-104`
- **Status**: NEW
- **Description**: The rate limiter still keys `self.message_log` by `id(websocket)` (lines 68, 101), the exact CPython memory-reuse hazard that motivated #3181's UUID `ws_id` fix elsewhere. If a websocket object is GC'd before `cleanup()` runs and a new websocket is allocated at the same address, the new connection inherits the old rate-limit log. `cleanup` always runs in the WS finally (system.py line 866), so risk is bounded — but the inconsistency is a latent foot-gun and contradicts the established convention.
- **Impact**: Theoretical false rate-limit rejection at the start of a fresh connection that reuses a recently-GC'd object's id. Hard to hit, easy to fix.
- **Siblings**: Same `id(websocket)` pattern is the bug that #3181 banned everywhere else.
- **Suggested Fix**: Replace `ws_id = id(websocket)` with `from core.audio_stream_controller import ws_id as _ws_id; key = _ws_id(websocket)`; change `message_log: dict[str, list[float]]`.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-12: WAV encoder always emits PCM_16 — `chunk_playable_duration`/`overlap_duration` are advertised in metadata but the WAV header has no overlap awareness
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/encoding/wav_encoder.py:60-63`; `routers/webm_streaming.py:81-97`
- **Status**: NEW
- **Description**: `StreamMetadata` exposes `chunk_duration`, `chunk_interval`, `chunk_playable_duration`, `overlap_duration` — the frontend is expected to subtract overlap when stitching chunks. But the WAV bytes returned per chunk encode the FULL `chunk_duration` (15 s) of audio at PCM_16, without any in-band marker for where the overlap region begins. The frontend must trust the metadata fields and trim by sample count. If a chunk arrives in an order other than its declared `chunk_idx` (e.g. cache MISS retry), the overlap-trim math at the frontend is wrong — and the WAV header offers no way to detect.
- **Evidence**: `encode_to_wav(audio, sample_rate)` writes the entire `audio` array verbatim as PCM_16 (no metadata, no markers, no fade-out). The router metadata (`chunk_playable_duration=chunk_interval`) is a separate contract.
- **Impact**: Brittle stitching on chunk reordering or cache-tier mismatch. Not currently observed.
- **Suggested Fix**: Embed `chunk_idx`, `start_sample_offset`, `playable_samples` into the WAV `INFO` chunk via soundfile `set_string` API, or — preferably — return JSON sidecar alongside the WAV bytes (X-Chunk-Idx + X-Playable-Samples already partly do this; add X-Overlap-Samples).

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-13: `WebSocketMessageType` enum is missing `force`/`pause`/`resume`/`stop`/`buffer_full`/`buffer_ready` documentation but accepts them; `extra='allow'` means any field passes
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/schemas.py:202-257`
- **Status**: NEW
- **Description**: The enum DOES list `BUFFER_FULL`/`BUFFER_READY`/`PAUSE`/`RESUME`/`STOP` (lines 222-234), but `WebSocketMessageBase` is declared with `extra='allow'` and `data: dict[str, Any] | None` — so any envelope passes once `type` is in the enum. The receive-loop branches do per-field validation (`isinstance(track_id, int)`, etc.) inline. This means:
  - The pydantic schema gives no protection on payload contents (track_id, position, preset, intensity).
  - A typo in client code (`"play_inhanced"` instead of `"play_enhanced"`) is rejected with `validation_error`, BUT a typo in payload field name (`"trackid"` instead of `"track_id"`) reaches the handler as `data.get("track_id") == None` and triggers the inline validator — different error path, no schema fingerprint.
- **Impact**: Inconsistent error UX; harder to maintain typed client SDKs; OpenAPI doc generation is unhelpful because the message types are opaque.
- **Suggested Fix**: Define per-type request models (`PlayEnhancedRequest`, `SeekRequest`, etc.) and validate `data` against the appropriate model in `validate_and_parse_message` based on `type`. Tracks better with frontend TS types.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-14: Look-ahead task in normal-path read does not pre-check WS connection — wastes CPU on a disconnected stream
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1019-1025`
- **Status**: NEW
- **Description**: `stream_normal_audio` launches the next chunk's read via `asyncio.create_task(asyncio.to_thread(_read_audio_chunk, ...))` BEFORE checking `_is_websocket_connected`. The enhanced-path equivalent (`_process_chunk_only`, lines 1136-1140) raises `ConnectionError` early if the WS is gone — but the normal-path lookahead has no such guard. If a disconnect happens between two chunk iterations, the lookahead task wastes a disk read (cheap, but unbounded under fast reconnects).
- **Impact**: Tiny: one unnecessary disk read per disconnect. Mostly hygiene.
- **Suggested Fix**: Inside the lookahead callable, check `_is_websocket_connected(websocket)` first and short-circuit. Mirror the `ConnectionError` pattern used in the enhanced path.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-15: `_send_pcm_chunk` re-checks `pcm_samples.dtype` post-cast but the cast path makes a full copy even when already float32 — unnecessary mempool churn under load
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1380-1393`
- **Status**: NEW (sibling of #3556 / BE-NEW-98 which fixed the per-frame byteorder branch)
- **Description**:
  ```python
  if pcm_samples.dtype != np.float32:
      pcm_samples = pcm_samples.astype(np.float32)
  ```
  Then `pcm_flat = pcm_samples.reshape(-1)`. The dtype check is correct, but the upstream `_process_chunk_only` always returns float32 (chunked_processor outputs float32). Same for the normal-path SoundFile read (`dtype='float32'` at line 982). So the dtype check is dead — but still computes the comparison. More importantly, the `astype` call when triggered does a full allocation; `astype(copy=False)` would skip allocation in the no-op case if the check failed for byteorder. Minor.
- **Impact**: ~zero — the path is never taken under current code. Pre-emptive hygiene.
- **Suggested Fix**: Either remove the dead branch (assert dtype, document that callers must pass float32) or use `astype(np.float32, copy=False)` so a hypothetical big-endian source doesn't allocate.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-16: WebM encoder kept in tree but no router calls it — dead code path with maintenance cost
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/encoding/webm_encoder.py` (entire file, 317 LOC); routers grep shows zero callers
- **Status**: NEW
- **Description**: The router is named `routers/webm_streaming.py` and its module docstring (lines 1-26) says "WAV Audio Unified Streaming Router" / "replacing WebM for browser compatibility" / "always returns WAV chunks". The router imports `wav_encoder.encode_to_wav` and never references `webm_encoder.encode_to_webm_opus`. Grep across `auralis-web/backend/` confirms zero callers of `encode_to_webm_opus`. The 317-LOC encoder remains under maintenance (recently patched in #3510 / BE-NEW-52 for CancelledError + ffmpeg subprocess orphans) yet serves no production traffic.
- **Impact**: 317 LOC of maintained but unreachable code; misleading filename `webm_streaming.py` for a router that exclusively serves WAV.
- **Suggested Fix**: Delete `webm_encoder.py` and the `check_ffmpeg_available` / `get_recommended_bitrate` helpers; rename the router file to `wav_streaming.py` (or `chunked_streaming.py`); update the router prefix from `"webm-streaming"` to a name that matches the wire format.

---

> _Dim 2 — WebSocket Streaming_

### BE-WS-17: `stream_normal_audio`'s temp-WAV cleanup `shutil.rmtree(..., ignore_errors=True)` silently swallows errors; no logging on failure
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1081-1087`
- **Status**: NEW
- **Description**: The compressed-format conversion (lines 866-883) writes a temp WAV to `tempfile.mkdtemp(prefix='auralis_stream_')`. On stream teardown, `shutil.rmtree(Path(temp_wav_path).parent, ignore_errors=True)` cleans it up — but `ignore_errors=True` + bare `except Exception: pass` means an `EBUSY`/`EACCES` failure (Windows, OneDrive sync) leaves the temp dir behind silently. Over weeks of usage these accumulate in `/tmp` (or `%TEMP%`).
- **Impact**: Disk leak on Windows under specific antivirus/cloud-sync conditions. Negligible on Linux.
- **Suggested Fix**: Replace with `shutil.rmtree(..., onerror=lambda *args: logger.warning(...))`; report leftover count on next startup.

---

> _Dim 3 — Chunked Processing_

### BE-CP-7: `apply_crossfade` docstring claims "equal-power" but implementation is equal-gain (sin²/cos²)
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:300-304`; same pattern at `chunked_processor.py:886-889`
- **Status**: NEW
- **Description**: Comment says "Create equal-power fade curves (sin²/cos²) to avoid ~3 dB energy dip at crossfade midpoint". This is contradictory: sin² + cos² = 1 is **equal-gain** (amplitude-preserving). Equal-POWER requires `sin² + cos² = 1` as **power** sum, which means amplitudes `sin` and `cos` (without the square) — that's the curve where uncorrelated signals' RMS is preserved. For correlated signals (which adjacent chunks of the same track ARE), equal-gain is the right choice — so the IMPLEMENTATION is fine. The COMMENT is wrong. Also note: both call sites are dead code in production (the only `_apply_boundary_crossfade` in streaming is the no-op shim per #3514).
- **Evidence**: `chunk_operations.py:300-304` — comment "equal-power", code `cos(t)**2`/`sin(t)**2`. The fix-issue note references `#2080` which was about energy-dip avoidance.
- **Impact**: Docstring confusion — a future engineer reading "equal-power" while looking at sin²/cos² will either "correct" the implementation (introducing a real 3 dB dip) or be confused about which crossfade type is in use. The CODE is correct for the use case; the COMMENT is the bug.
- **Siblings**: `chunked_processor.py:858-907` `apply_crossfade_between_chunks` has the identical mislabelled comment. Test `tests/backend/test_equal_power_crossfade.py` exists but tests the implementation under its (wrong) name.
- **Suggested Fix**: Correct the comment to "equal-gain (sin² + cos² = 1) — appropriate for crossfading correlated signals (same source) without amplitude drop. NOT equal-power; for uncorrelated material use sin/cos to preserve RMS."

---

> _Dim 3 — Chunked Processing_

### BE-CP-8: `_prefetch_next_track`, `_process_chunk_with_hybrid_processor`, `next_track_prefetched`, `apply_crossfade_between_chunks` module-level — all dead code
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1233-1320` (`_prefetch_next_track`, ~88 LOC); `audio_stream_controller.py:655` (`next_track_prefetched: bool = False` — set, never read); `chunked_processor.py:409-467` (`_process_chunk_with_hybrid_processor`, ~58 LOC); `chunked_processor.py:858-907` (`apply_crossfade_between_chunks`, ~50 LOC)
- **Status**: NEW
- **Description**: Confirmed by `grep -rn` across `/mnt/data/src/matchering/auralis-web/backend/`:
  - `_prefetch_next_track`: defined only; 0 call sites (comment at line 715-723 explains it was disabled in #3513 / BE-NEW-55 and not yet re-enabled)
  - `_process_chunk_with_hybrid_processor`: defined only; 0 call sites (replaced by `AudioProcessingPipeline.process_audio` in `_process_chunk_core`)
  - `next_track_prefetched`: assigned `False` at line 655, never referenced anywhere else in the file
  - `apply_crossfade_between_chunks` (module-level in `chunked_processor.py`) and `ChunkOperations.apply_crossfade`: only callers are test files
  Total: ~196 LOC of dead code in audio-critical paths, plus the misleading invitation in the `_prefetch_next_track` docstring ("Re-enable once the cache manager is hoisted to a process-wide singleton") that has not been actioned.
- **Evidence**:
  ```
  $ grep -rn "_prefetch_next_track\|next_track_prefetched" auralis-web/backend/
  audio_stream_controller.py:1233: async def _prefetch_next_track(  # definition only
  audio_stream_controller.py:655:  next_track_prefetched: bool = False
  audio_stream_controller.py:716:  # _prefetch_next_track wrote chunk 0 of the next track...  (comment)
  
  $ grep -n "_process_chunk_with_hybrid_processor" auralis-web/backend/core/chunked_processor.py
  409: def _process_chunk_with_hybrid_processor  # definition only
  ```
- **Impact**: Maintenance cost: every refactor must keep dead branches consistent. `_prefetch_next_track` carries ~88 LOC of risky logic (queue parsing, async repo calls, processor instantiation, cache writes) that drifts silently. Sibling #3776 (CLOSED) deleted a similar 475-LOC `usePlayerStreaming` dead-code path. Same hygiene.
- **Siblings**: #3776 (`usePlayerStreaming` 475-LOC dead path), #3775 (chunk_duration constant duplication — already cleaned up).
- **Suggested Fix**: Delete `_prefetch_next_track` and `next_track_prefetched` (re-introduce when cache lifecycle is fixed; the current implementation provably doesn't help). Delete `_process_chunk_with_hybrid_processor` (replaced by pipeline). Convert `apply_crossfade_between_chunks` module-level to a single `from .chunk_operations import ChunkOperations` re-export OR delete entirely; remove the equivalent dead pipeline copy.

---

> _Dim 3 — Chunked Processing_

### BE-CP-9: `_chunk_tails` storage still allocates per-chunk tail copies that nothing reads
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1191-1210` (writes), `1322-1353` (no-op reader)
- **Status**: NEW
- **Description**: `_stream_processed_chunk` allocates a `pcm_samples[-tail_samples:].copy()` per chunk (~200 ms × float32 = ~70 KB per chunk for stereo @ 44.1 kHz) and stores it in `self._chunk_tails[track_id]`. The only reader is `_apply_boundary_crossfade`, which the docstring explicitly says is "a no-op (rather than removing the call) so the prev_tail storage in _chunk_tails_lock remains available if a future variant needs it again." So per-chunk we make a 70 KB allocation, take a lock, write to a dict, and then never read it. The cleanup at end-of-stream is correct (`_drop_chunk_tail`) but the storage itself is purely speculative future-use.
- **Evidence**: `audio_stream_controller.py:1204-1207`:
  ```python
  if chunk_index < processor.total_chunks - 1:
      tail_samples = min(crossfade_samples, len(pcm_samples))
      self._chunk_tails[processor.track_id] = pcm_samples[-tail_samples:].copy()
  ```
  Consumer (`_apply_boundary_crossfade:1322-1353`) returns `current_chunk` unchanged.
- **Impact**: 70 KB × num_chunks per stream of unused allocations, plus lock contention on `_chunk_tails_lock` for no functional reason. Negligible memory pressure but wasteful CPU (the `.copy()` is real work). #2326 / #3527 race-fix history made this lock necessary for the ORIGINAL crossfade — now it serialises writes that no consumer reads.
- **Siblings**: Same "kept-for-future" pattern flagged in #3776 (dead hook 475 LOC).
- **Suggested Fix**: Either (a) actually implement the boundary crossfade using the tail (proper overlap-add with the head of the next chunk), or (b) remove the tail-storage allocation and the `_chunk_tails`/`_chunk_tails_lock` infrastructure entirely. The current state is the worst of both worlds.

---

> _Dim 3 — Chunked Processing_

### BE-CP-10: `_load_metadata` fallback path computes `self.channels` via untyped chained ternaries — wrong for mono int16 WAVs
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunked_processor.py:233`
- **Status**: NEW
- **Description**: The soundfile-fallback metadata path at line 233 computes:
  ```python
  self.channels = audio.ndim if audio.ndim == 1 else audio.shape[0] if audio.shape[0] <= 2 else audio.shape[1]
  ```
  This is operator-precedence-ambiguous (resolves as `audio.ndim if audio.ndim == 1 else (audio.shape[0] if audio.shape[0] <= 2 else audio.shape[1])`) and produces wrong values for:
  - mono `(N,)` array → returns `1` (correct, but for the wrong reason — `audio.ndim == 1` is true, returns `1`, but ndim ≠ channels)
  - stereo `(N, 2)` array, where N > 2 → checks `audio.shape[0] <= 2` (= False if N > 2) → returns `audio.shape[1] = 2` (correct)
  - stereo `(2, N)` channels-first → `audio.shape[0] <= 2` (True) → returns `audio.shape[0] = 2` (correct)
  - the ambiguity bites on borderline cases (tiny stereo files like a 2-sample chunk-1 fallback) where `(2, 2)` returns 2 by shape[0] (correct) but `(1, 2)` returns 1 by shape[0] (WRONG: should be 2).
  In practice the fallback is rare (only hit when soundfile fails to read metadata), but the assignment is incorrect on edge cases.
- **Evidence**: Code as quoted; the much cleaner upstream path at line 221-227 uses `f.channels` directly.
- **Impact**: Rare. When the fallback fires AND the audio has an unusual shape, `self.channels` may be wrong, which propagates to chunk-extraction silence-padding and may cause shape-broadcast errors downstream.
- **Siblings**: 04d6eca6 (commit) added a similar `audio.shape[1] if audio.ndim > 1 else 1` guard at `chunk_operations.py:128`. Hardening the same site here is overdue.
- **Suggested Fix**: Replace with explicit logic:
  ```python
  if audio.ndim == 1:
      self.channels = 1
  elif audio.ndim == 2:
      self.channels = audio.shape[1] if audio.shape[0] > audio.shape[1] else audio.shape[0]
  else:
      raise ValueError(f"Unsupported audio shape: {audio.shape}")
  ```

---

> _Dim 3 — Chunked Processing_

### BE-CP-11: `_process_chunk_core` empty-chunk fallback hardcodes channel count and dtype, ignores input
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunked_processor.py:507-512`
- **Status**: NEW
- **Description**: When `processed_chunk` length is 0 after `trim_context`, the fallback creates 100 ms of silence with `np.zeros((sample_rate // 10, num_channels), dtype=np.float32)`. The `num_channels` is taken from `audio_chunk.shape[1] if audio_chunk.ndim > 1 else 2` — but the fallback dtype is hardcoded float32 regardless of `audio_chunk.dtype`. If the input was float64, the silence chunk is float32, then `_smooth_level_transition` multiplies it by a Python float (line 146 of level_manager.py), promoting it back to float64. The dtype "ping-pong" wastes memory.
- **Evidence**:
  ```python
  # chunked_processor.py:507-512
  if len(processed_chunk) == 0:
      logger.error(f"Chunk {chunk_index} is empty after context trimming. Returning silence.")
      num_channels = audio_chunk.shape[1] if audio_chunk.ndim > 1 else 2
      assert self.sample_rate is not None
      processed_chunk = np.zeros((self.sample_rate // 10, num_channels), dtype=np.float32)
  ```
- **Impact**: Rare (only when trim_context produces empty output, which means short-track BE-CP-2 scenario). Negligible runtime impact when it does fire.
- **Siblings**: Same family as BE-CP-5 (dtype-forgetting in chunk_operations fallback paths).
- **Suggested Fix**: `dtype=audio_chunk.dtype if isinstance(audio_chunk, np.ndarray) else np.float32`.

---

> _Dim 3 — Chunked Processing_

### BE-CP-12: `ChunkBoundaryManager.__init__` uses `__import__('numpy')` instead of a top-level numpy import
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:49`
- **Status**: NEW
- **Description**: `self._total_chunks = int(__import__('numpy').ceil(total_duration / CHUNK_INTERVAL))` — uses `__import__` at the call site instead of a normal `import numpy as np` at module top. The module already does `import numpy` inside `trim_context` (line 222). This was likely a workaround for some import-order issue at the time of file creation but is now a code smell: every `ChunkBoundaryManager()` instantiation does an import lookup. CPython caches modules so it's fast, but the pattern hides the numpy dependency from static analyzers and creates inconsistency with the rest of the module.
- **Evidence**: Direct code quote above. The same calculation could simply use `import math; math.ceil(...)` — no numpy needed.
- **Impact**: Negligible runtime. Code-hygiene only.
- **Siblings**: None.
- **Suggested Fix**: `import math` at top of module, then `self._total_chunks = math.ceil(total_duration / CHUNK_INTERVAL)`. Remove the in-function `import numpy as np` at line 222 — promote to module top alongside `import logging`.

---

> _Dim 4 — Processing Engine_

### BE-PE-4: `proactive_buffer.buffer_presets_for_track` is dead — injected as `buffer_presets_fn` to player router but never invoked anywhere
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/proactive_buffer.py:22-105` (function), `auralis-web/backend/routers/player.py:200, 215` (injected, unused), `auralis-web/backend/main.py:130`, `auralis-web/backend/config/routes.py:64, 183` (wiring)
- **Status**: NEW
- **Description**: `proactive_buffer.buffer_presets_for_track` is exported, imported in `main.py:63`, packed into `globals_dict['buffer_presets_fn']`, threaded through `config/routes.py` into `create_player_router(buffer_presets_fn=...)`. Inside the player router (`routers/player.py`), the parameter is declared at line 200 and documented at line 215 — and that's the only mention. `grep -n buffer_presets_fn auralis-web/backend/routers/player.py` shows two hits, both definitional. The function buffers the first 3 chunks × 5 presets (~225 s of DSP work) for instant preset switching, but no endpoint ever calls it. The `proactive_buffer` module additionally lost its `get_buffer_status()` helper to #3526 (dead glob pattern); the remaining code is purely vestigial.
- **Evidence**:
  ```bash
  $ grep -rn buffer_presets auralis-web/backend/ | grep -v __pycache__
  core/proactive_buffer.py:22:async def buffer_presets_for_track(...
  routers/player.py:200:    buffer_presets_fn: Callable[..., Any],
  routers/player.py:215:        buffer_presets_fn: Function for proactive preset buffering
  main.py:63:from core.proactive_buffer import buffer_presets_for_track
  main.py:130:    'buffer_presets_fn': buffer_presets_for_track,
  config/routes.py:64:    buffer_presets_fn: Any = deps.get('buffer_presets_fn')
  config/routes.py:183:        buffer_presets_fn=buffer_presets_fn,
  ```
- **Impact**: ~120 lines of code that look like a working feature but never execute. Preset switches in the first 90 s of a track must wait the full processing window because the proactive buffer never fires. Confusing for maintainers — the comment "🎉 Proactive buffering complete" appears nowhere in production logs because the function is never reached.
- **Suggested Fix**: Either (a) hook `asyncio.create_task(buffer_presets_fn(track_id, filepath, intensity, total_chunks))` into the play handler in `routers/player.py` or `routers/system.py` (e.g., right after `stream_enhanced_audio` is launched), or (b) delete `proactive_buffer.py` and the wiring chain. Option (b) is cheaper if proactive buffering isn't on the roadmap.

---

> _Dim 4 — Processing Engine_

### BE-PE-5: `LevelManager.rms_history` and `gain_history` lists grow unbounded for the life of the ChunkedAudioProcessor
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/level_manager.py:41-42, 108-173`
- **Status**: NEW
- **Description**: `LevelManager` stores `self.rms_history: list[float] = []` and `self.gain_history: list[float] = []` with `.append()` calls in every `smooth_transition()` invocation (one per chunk). There is no cap. With 30 s chunks and a typical track, a 5-minute track produces 10 entries — negligible. But for long-form content (1 h+ podcasts, classical concerts, audiobooks), or for ChunkedAudioProcessor instances kept alive in `StreamlinedCacheWorker._processor_cache` (line 55) over multiple track repeats, the lists can reach several thousand entries. Each float is 24 bytes in a CPython list — small but unbounded growth on a process-wide singleton service.
- **Evidence**:
  ```python
  # level_manager.py:41-42, 110-111
  self.rms_history: list[float] = []
  self.gain_history: list[float] = []
  # ...
  if chunk_index == 0 or len(self.rms_history) == 0:
      current_rms = self.calculate_rms(chunk)
      self.rms_history.append(current_rms)
      self.gain_history.append(0.0)
  ```
  And in `smooth_transition`, every branch ends with `self.rms_history.append(...)` / `self.gain_history.append(...)` — never `.pop()` or `del`.
- **Impact**: Memory growth proportional to chunk count over the LevelManager's lifetime. Per-track instance is bounded by track length (~10 KB per hour), but `StreamlinedCacheWorker._processor_cache` retains ChunkedAudioProcessor instances across tracks (the cache evicts on track change but not on track repeat) — so a user looping a 1-hour podcast accumulates ~10 KB per loop forever.
- **Siblings**: `chunked_processor.py:194-195` declares the same `chunk_rms_history` / `chunk_gain_history` lists for legacy compat and copies them from LevelManager every chunk — same unbounded growth.
- **Suggested Fix**: Cap both lists with `collections.deque(maxlen=128)` — only the LAST chunk's RMS matters for the transition smoothing logic; the older history is only used for `get_statistics()` and could keep last-N entries.

---

> _Dim 4 — Processing Engine_

### BE-PE-6: `QueueStatusResponse` Pydantic schema declares `cancelled` and `total` fields the engine never populates — response has `total=0, cancelled=0` next to `total_jobs=N, queue_full=...`
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/routers/processing_api.py:123-132`; producer `auralis-web/backend/core/processing_engine.py:766-779`
- **Status**: NEW
- **Description**: `QueueStatusResponse` declares fields `queued, processing, completed, failed, cancelled, total` with `extra="allow"`. `ProcessingEngine.get_queue_status()` returns a dict with `total_jobs` (not `total`) and never produces a `cancelled` count even though cancelled jobs exist in `self.jobs`. Because `model_config = {"extra": "allow"}`, the actual JSON response includes both: `{"total": 0, "total_jobs": 5, "cancelled": 0, ...}`. The schema fields are defaults; the engine fields are extras. Frontend gets contradictory data and either has to know to prefer `total_jobs` over `total`, or treats `cancelled=0` as truth even when many cancelled jobs are present.
- **Evidence**:
  ```python
  # processing_api.py:123-132 — schema declares total/cancelled
  class QueueStatusResponse(BaseModel):
      queued: int = 0
      processing: int = 0
      completed: int = 0
      failed: int = 0
      cancelled: int = 0
      total: int = 0
      model_config = {"extra": "allow"}

  # processing_engine.py:766-779 — producer returns total_jobs, no cancelled
  return {
      "total_jobs": len(jobs),
      "queued": ...,
      "processing": ...,
      "completed": ...,
      "failed": ...,
      # cancelled missing
      "max_concurrent": ...,
      "max_queue_size": ...,
      "queue_full": ...,
  }
  ```
- **Impact**: API contract drift. A frontend reading `queueStatus.total` gets always-0; one reading `queueStatus.cancelled` gets always-0. Truth lives in `total_jobs` and `[len(j) for j in jobs if j.status == CANCELLED]` — neither documented.
- **Suggested Fix**: Either align the producer (add `"total": len(jobs), "cancelled": len([j for j in jobs if j.status == CANCELLED])`) or rename the schema fields to `total_jobs`. The producer fix is one line and preserves the schema's documented field names.

---

> _Dim 4 — Processing Engine_

### BE-PE-7: `MasteringTargetService` cache-hit path does not `move_to_end` — `OrderedDict` LRU degenerates to FIFO eviction
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/mastering_target_service.py:77-82, 303-308`
- **Status**: NEW
- **Description**: `_store_in_cache` (line 77) correctly uses `OrderedDict.move_to_end` on every WRITE, and evicts via `popitem(last=False)`. But the cache-HIT branch at line 304-308 reads `self.cache[cache_key]` without calling `move_to_end`. So a hot key that's repeatedly read but never re-stored will eventually be evicted as the OLDEST when the cache fills, even though it's the MOST RECENTLY USED. This silently turns the cache from LRU into FIFO-after-first-write.
- **Evidence**:
  ```python
  # mastering_target_service.py:303-308 — read without move_to_end
  with self._lock:
      if cache_key in self.cache:
          cached = self.cache[cache_key]
          if isinstance(cached, tuple) and len(cached) == 2:
              logger.debug(f"Using cached fingerprint for track {track_id}")
              return cached   # ← no move_to_end
  ```
- **Impact**: For typical listening sessions (≤ 256 unique tracks per session), the cache cap of 256 is never reached and the bug is dormant. For users with a large library and shuffle mode crossing the 256-entry threshold, hot tracks revisited after 256 different tracks would get evicted even though they're frequently played.
- **Suggested Fix**: Add `self.cache.move_to_end(cache_key)` right after the `if cache_key in self.cache:` check at line 305.

---

> _Dim 4 — Processing Engine_

### BE-PE-8: `streamlined_worker._process_chunk` calls synchronous `library_manager.tracks.get_by_id(track_id)` from async context (2 sites)
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/streamlined_worker.py:112, 370`
- **Status**: NEW (sibling of #3333 which fixed AudioStreamController)
- **Description**: `_process_priorities` (line 112) and `trigger_immediate_processing` (line 370) call `self.library_manager.tracks.get_by_id(track_id)` directly from `async def` methods. `get_by_id` issues a synchronous SQLite query through SQLAlchemy. Issue #3333 fixed this pattern at 4 sites in `AudioStreamController` by wrapping in `asyncio.to_thread`. The streamlined_worker copies were missed.
- **Evidence**:
  ```python
  # streamlined_worker.py:111-112 — sync DB call in async context
  async def _process_priorities(self) -> None:
      ...
      track = self.library_manager.tracks.get_by_id(track_id)   # ← blocks event loop

  # streamlined_worker.py:369-370 — same pattern
  async def trigger_immediate_processing(...):
      track = self.library_manager.tracks.get_by_id(track_id)   # ← blocks event loop
  ```
- **Impact**: Each blocking call is short (~1-5 ms for an indexed PK lookup), but `_process_priorities` runs every 1 second in a tight loop (line 83 `await asyncio.sleep(1.0)`), and `trigger_immediate_processing` runs on every cache miss. Cumulative event-loop blocking. On a slow disk (HDD with cold cache) the lookup can exceed 50 ms — measurable jank.
- **Siblings**: `mastering_target_service.py:115` `fingerprints_repo.get_by_track_id(track_id)` runs inside `load_fingerprint_from_database`, which is called from synchronous `load_fingerprint()` — that one is OK because it's already inside `asyncio.to_thread` via the chunked-processor pipeline. The streamlined_worker hits don't have that wrapping.
- **Suggested Fix**: Wrap both calls in `await asyncio.to_thread(self.library_manager.tracks.get_by_id, track_id)`. Match the #3333 fix pattern.

---

> _Dim 4 — Processing Engine_

### BE-PE-9: `cancel_job` is sync but mutates `self.progress_callbacks` outside `_jobs_lock` — race window with concurrent `register_progress_callback`/`_notify_progress` exists when handler does `await`
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:686-709`
- **Status**: NEW
- **Description**: `cancel_job(self, job_id)` is a synchronous method (line 686). It reads `self.jobs.get(job_id)`, mutates `job.status`, `job.completed_at`, reads `self._tasks.get(job_id)`, calls `task.cancel()`, and pops `self.progress_callbacks[job_id]` — all without acquiring `_jobs_lock` (which is an `asyncio.Lock`, only acquirable from `async` context). Because cancel_job is sync and does no `await`, it runs atomically within one event-loop tick — so cross-coroutine races inside this function don't happen on the single event-loop thread. BUT: it's called from `routers/processing_api.py:355` as a plain (non-awaited) call inside `async def cancel_job`. Between line 355 and the next `raise HTTPException`, the event loop yields nowhere — so far still safe. The latent risk: if `cancel_job` is ever refactored to add an `await` (e.g., `await self._notify_progress(...)`), the dict mutations would suddenly need the lock. Also confusingly, `unregister_progress_callback` (line 232) DOES acquire `_jobs_lock` for the same `progress_callbacks.pop` — inconsistent.
- **Evidence**:
  ```python
  # processing_engine.py:706 — pop without _jobs_lock
  def cancel_job(self, job_id: str) -> bool:
      ...
      self.progress_callbacks.pop(job_id, None)   # ← no lock
  
  # processing_engine.py:232-235 — same op, locked
  async def unregister_progress_callback(self, job_id: str) -> None:
      async with self._jobs_lock:
          self.progress_callbacks.pop(job_id, None)
  ```
- **Impact**: Today: latent, no observable bug because `cancel_job` is fully synchronous. Tomorrow: any refactor adding an `await` to `cancel_job` would silently introduce a race. Inconsistency with `unregister_progress_callback` makes the code harder to reason about.
- **Suggested Fix**: Either (a) keep `cancel_job` sync and DELETE the asyncio.Lock on `unregister_progress_callback` (since GIL serialises sync mutations and `asyncio.Lock` doesn't help) — make consistency explicit, or (b) make `cancel_job` async and acquire `_jobs_lock` around the dict access. Option (a) is the simpler refactor; option (b) is the safer one for future evolution.

---

> _Dim 4 — Processing Engine_

### BE-PE-10: `_notify_progress` reads `self.jobs.get(job_id)` and writes `job.progress` outside `_jobs_lock`
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:237-256`
- **Status**: NEW
- **Description**: `_notify_progress` is `async def`. It reads `self.jobs.get(job_id)` without holding `_jobs_lock`, writes `job.progress = progress` (also no lock), and only then enters `async with self._jobs_lock:` to read `progress_callbacks`. Because `cleanup_old_jobs` (line 711) deletes from `self.jobs` UNDER `_jobs_lock`, there's a window where `_notify_progress` could read a job that's about to be deleted by a concurrent cleanup. The write to `job.progress` after the delete is harmless (the dict entry is gone) but the read-before-lock is inconsistent with the lock policy.
- **Evidence**:
  ```python
  # processing_engine.py:243-246 — unlocked read + write
  async def _notify_progress(self, job_id: str, progress: float, message: str = "") -> None:
      job = self.jobs.get(job_id)   # ← outside lock
      if job:
          job.progress = progress    # ← outside lock
          async with self._jobs_lock:
              callback = self.progress_callbacks.get(job_id)
  ```
- **Impact**: Latent. In CPython with the GIL, `dict.get` and attribute assignment are atomic — no torn reads. But if a concurrent `cleanup_old_jobs` is mid-deletion (between `del self.jobs[job_id]` and `del self.progress_callbacks[job_id]`), `_notify_progress` could fetch the job, write progress to it, and then look up a callback that has already been deleted — minor wasted work, no crash.
- **Suggested Fix**: Move the `self.jobs.get(job_id)` and `job.progress = progress` INSIDE the `async with self._jobs_lock:` block, or — since the only consumer of `progress` is the same dict access — re-read inside the lock.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-7: Duplicate `CacheStatsResponse` / `TrackCacheStatus` in `schemas.py` (typed) and `cache_streamlined.py` (`dict[str, Any]`) — #3548 closed but the duplicate is acknowledged as a TODO in code
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - Canonical typed version: `auralis-web/backend/schemas.py:423-471` (`CacheTierStats`, `OverallCacheStats`, `CacheStatsResponse`, `TrackCacheStatusResponse`)
  - Duplicate router-local version: `auralis-web/backend/routers/cache_streamlined.py:23-47` (router's own `CacheStatsResponse` with `tier1: dict[str, Any]`, `tier2: dict[str, Any]`, `overall: dict[str, Any]`)
- **Status**: Regression of #3548 / BE-NEW-90. Issue CLOSED 2026-05-26 but the router-local copy still exists and explicitly acknowledges itself as a not-yet-migrated duplicate in an inline docstring.
- **Description**: BE-NEW-90 (2026-05-25 audit) flagged that `schemas.py` declares fully-typed `CacheTierStats` + `OverallCacheStats` + `CacheStatsResponse` while `routers/cache_streamlined.py` declares its own `CacheStatsResponse` with `tier1: dict[str, Any]` (and a separate `TrackCacheStatus` instead of `TrackCacheStatusResponse`). Issue #3548 was closed 2026-05-26 but a fresh read of `cache_streamlined.py:23-32` shows the local copy is still there with an explicit "NOTE: schemas.CacheStatsResponse exposes properly-typed nested fields (#3548 / BE-NEW-90). This local copy uses dict[str, Any] to absorb the StreamlinedCacheManager.get_stats() return shape verbatim. Migrating to the schemas.py version is a follow-up that needs to verify the get_stats() dict matches the typed model field-for-field." So #3548's resolution was "document the gap" rather than "fix the gap" — but the issue was closed without that distinction being recorded.
- **Evidence**:
  ```python
  # backend/routers/cache_streamlined.py:23-37 — current local copy
  class CacheStatsResponse(BaseModel):
      """Response model for cache statistics.
  
      NOTE: schemas.CacheStatsResponse / CacheTierStats / OverallCacheStats
      expose properly-typed nested fields (#3548 / BE-NEW-90). This local
      copy uses dict[str, Any] to absorb the StreamlinedCacheManager.get_stats()
      return shape verbatim. Migrating to the schemas.py version is a
      follow-up that needs to verify the get_stats() dict matches the
      typed model field-for-field.
      """
      tier1: dict[str, Any]
      tier2: dict[str, Any]
      overall: dict[str, Any]
      tracks: dict[int, dict[str, Any]]
  ```
- **Impact**: OpenAPI docs for `GET /api/cache/stats` show `{tier1: object, tier2: object, overall: object}` with no inner field shape, even though `schemas.py` has them fully typed. Anyone integrating against the docs sees opaque objects. The router-local `TrackCacheStatus` is a strict subset of `schemas.TrackCacheStatusResponse` (missing `estimated_cache_time_seconds`) — also unnecessary duplication.
- **Siblings**: Same pattern as the duplicate `PaginatedResponse` in `schemas.py` vs `routers/pagination.py` (BE-SCH-8). `schemas.PaginatedResponse` is dead code (no caller); `pagination.PaginatedResponse.create` is also dead (no caller — see BE-SCH-8).
- **Suggested Fix**: Import the canonical models from `schemas` in `cache_streamlined.py` and delete the local copy. Verify the `StreamlinedCacheManager.get_stats()` return matches `CacheStatsResponse(**stats)` (it almost certainly does — the existing fields are 1:1 named the same). If the dict-formed return omits one canonical field, add a `field-for-field shape test` (one-off pytest) that constructs the typed model from a real `get_stats()` call. Re-open and re-close #3548 if the migration lands.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-8: Three coexisting pagination response shapes — `schemas.PaginatedResponse` is dead code, ad-hoc shapes circulate in library/albums/playlists
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - Dead `schemas.PaginatedResponse` (data + nested pagination): `auralis-web/backend/schemas.py:86-106`
  - Dead `routers/pagination.PaginatedResponse.create` (flat shape): `auralis-web/backend/routers/pagination.py:20-92`
  - Ad-hoc shapes in use today: `routers/library.py:167-173` (`{tracks, total, offset, limit, has_more}`), `routers/library.py:424-430` (`{artists, total, offset, limit, has_more}`), `routers/albums.py:79-85` (`{albums, total, offset, limit, has_more}`), `routers/library.py:199-205` (`{tracks, total, limit, offset, has_more}`)
  - Frontend type: `auralis-web/frontend/src/types/domain.ts:352-355` (`{data: T[], pagination: PaginationState}`)
- **Status**: Regression of #3508 / BE-NEW-50. Issue CLOSED 2026-05-26 but neither `schemas.PaginatedResponse` nor `pagination.PaginatedResponse.create()` is called by any production code, and the ad-hoc shapes still circulate.
- **Description**: BE-NEW-50 (2026-05-25 audit) flagged two duplicate `PaginatedResponse` models with 14 endpoints using a third ad-hoc form. The proposed fix was "pick the flat shape, delete the dead duplicate, migrate routers." Issue #3508 closed 2026-05-26. Fresh search at audit time: `grep -rn "PaginatedResponse" auralis-web/backend/` shows `schemas.PaginatedResponse` declared but zero call sites (dead code), `pagination.PaginatedResponse.create()` declared but only called from its own docstring example (zero production callers), and the original ~14 ad-hoc usages all still in place using `{tracks/artists/albums/playlists}` as the items key rather than the proposed standard `items` key. The frontend `domain.ts:352-355` declares `PaginatedResponse<T>` with `{data: T[], pagination: {limit, offset, total, hasMore}}` — neither backend shape matches it.
- **Evidence**:
  ```python
  # backend/schemas.py:86-106 — declared but never used
  class PaginatedResponse(BaseModel, Generic[T]):
      status: str = Field(default="success")
      data: list[T] = Field(description="Page of items")
      pagination: PaginationMeta = Field(description="Pagination metadata")
      ...
  # zero callers anywhere
  
  # backend/routers/pagination.py:60-92 — declared, has a nice .create() factory, never called
  @classmethod
  def create(cls, items, total, limit, offset) -> PaginatedResponse[T]:
      return cls(items=items, total=total, offset=offset, limit=limit,
                 has_more=(offset + len(items)) < total)
  # zero callers anywhere except its own docstring example
  
  # backend/routers/library.py:167-173 — what's actually shipped today
  return {
      "tracks": serialize_tracks(tracks),
      "total": total,
      "offset": offset,
      "limit": limit,
      "has_more": has_more
  }
  ```
  ```typescript
  // frontend/src/types/domain.ts:345-355 — what the frontend type contract says
  export interface PaginationState {
    limit: number;
    offset: number;
    total: number;
    hasMore: boolean;
  }
  export interface PaginatedResponse<T> {
    data: T[];
    pagination: PaginationState;
  }
  ```
- **Impact**: Frontend `PaginatedResponse<T>` cannot be used to type any actual API response (no endpoint returns that shape). Any new endpoint following the canonical `pagination.PaginatedResponse` pattern would silently break existing consumers that read `tracks`/`artists`/`albums`. The `schemas.PaginatedResponse` model exists only to confuse — it's pure dead code referenced nowhere.
- **Siblings**: BE-SCH-7 (duplicate `CacheStatsResponse`). BE-SCH-3 (response_model coverage).
- **Suggested Fix**: Pick one shape and commit. Recommendation: keep the flat ad-hoc shape but rename the item key to `items` across all routers and add `response_model=PaginatedResponse[XxxResponse]` using `routers/pagination.PaginatedResponse`. Delete `schemas.PaginatedResponse` (dead code). Update frontend `PaginatedResponse<T>` to `{items: T[], total, offset, limit, has_more}` to match. This is one PR per resource (tracks, artists, albums, playlists, favorites) — ~5 PRs total.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-9: ~25 path-int params have no `Path(..., ge=1)` validation — `-1`, `0`, and very large values reach the DB layer
- **Severity**: LOW
- **Dimension**: Schema Consistency / Input Validation
- **Location**: All match `async def \w+(\w+_id: int)` with no `Path(...)` constraint. Concrete sites (grep output):
  - `routers/albums.py:92, 131, 173` (`album_id: int`)
  - `routers/artists.py:163, 204` (`artist_id: int`)
  - `routers/artwork.py:55, 168, 219, 261` (`album_id: int`)
  - `routers/cache_streamlined.py:101, 136` (`track_id: int`)
  - `routers/enhancement.py:376` (`track_id: int`)
  - `routers/library.py:212, 237, 261, 285, 437, 465, 718` (track_id / artist_id / album_id)
  - `routers/metadata.py:94, 141, 186` (`track_id: int`)
  - `routers/playlists.py:96, 172, 220, 256, 300, 338` (playlist_id / track_id)
  - `routers/similarity.py:477` (`track_id: int`)
  - `routers/webm_streaming.py:133` (`track_id: int`)
  - `routers/player.py:482` (`index: int` for `/api/player/queue/{index}`)
- **Status**: NEW (partial sibling of #2727 / #3559 which fixed query-param `order_by` validation but never addressed path-int validation generally)
- **Description**: FastAPI accepts any string-parseable integer for `xxx_id: int` path params with no constraint — `-1`, `0`, `2147483647`, etc. Most of these endpoints subsequently call `repos.tracks.get_by_id(-1)` which returns `None` and 404s; not actively dangerous but allows nonsense input to traverse the entire request pipeline before failing. The `/api/player/queue/{index}` endpoint specifically accepts negative indices and forwards them to `service.remove_track_from_queue(-1)` which then has to ValueError-bounce. Best-practice FastAPI uses `Path(..., ge=1)` or `Path(..., ge=0)` for integer IDs.
- **Evidence**:
  ```python
  # backend/routers/library.py:212 — no constraint
  async def get_track(track_id: int) -> dict[str, Any]:
      ...
      track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)   # accepts -1
  
  # backend/routers/player.py:481-482 — accepts negative index
  @router.delete("/api/player/queue/{index}", response_model=RemoveFromQueueResponse)
  async def remove_from_queue(index: int) -> dict[str, Any]:
      ...
      return await service.remove_track_from_queue(index)   # accepts -5
  ```
  Compare to `webm_streaming.py:227` which DOES use the pattern:
  ```python
  chunk_idx: int = PathParam(..., ge=0, description="Chunk index (must be non-negative)")
  ```
- **Impact**: Defense-in-depth gap. Currently any `xxx_id ≤ 0` reaches `repos.*.get_by_id` and 404s naturally; any large value reaches it and 404s naturally; any value that happens to coincide with a real DB id 200s and serves the resource. The risk window is bugs in the repo layer (e.g., a future "soft-delete" feature that exposes negative IDs) or bugs in the URL routing that conflate signed/unsigned. Per-route `ge=1` would make the contract explicit and let the 422 fire at the boundary.
- **Siblings**: `/api/processing/job/{job_id}` and similar string IDs are appropriately validated upstream by the engine (`_subscribed_job_ids` check + length cap), so this is specific to int path params.
- **Suggested Fix**: Sweep — for every `async def \w+(\w+_id: int)` (or `index: int`), change to `from fastapi import Path` then `xxx_id: int = Path(..., ge=1)`. `chunk_idx` already does this; copy the pattern. ~25 sites, mechanical change.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-10: `domain.ts` `PlayerState` mixes snake_case `gapless_enabled`/`crossfade_enabled`/`crossfade_duration` into otherwise camelCase shape — and `api.ts` `PlayerVolumeRequest.volume` says 0.0-1.0 while backend uses 0-100
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - `auralis-web/frontend/src/types/domain.ts:132-147` (`PlayerState` interface mixes snake_case in)
  - `auralis-web/frontend/src/types/api.ts:62-64` (`PlayerVolumeRequest.volume: 0.0 - 1.0`)
  - `auralis-web/frontend/src/types/api.ts:79-90` (a SECOND `PlayerState` interface, with the same snake_case mix)
  - `auralis-web/frontend/src/types/api.ts:196` (`EnhancementSettingsResponse.last_updated` — backend never emits this)
  - Backend canonical: `auralis-web/backend/routers/player.py:95-102` (`SetVolumeRequest.volume` clamped to 0-100)
  - Backend `PlayerState.volume`: `auralis-web/backend/player_state.py:62` (`volume: int = 80` — 0-100 scale)
- **Status**: NEW (BE-NEW-43 / BE-NEW-47 fixed `repeat_mode` and `TrackInfo.filepath/artwork_url`, but the broader naming inconsistency in `domain.ts` and `api.ts` was not in scope)
- **Description**: `domain.ts` `PlayerState` interface (line 132-147) declares `currentTrack`, `isPlaying`, `volume`, `position`, `duration`, `queueIndex` in camelCase but `gapless_enabled`, `crossfade_enabled`, `crossfade_duration` in snake_case in the same interface. The transformer at `websocket.ts:transformPlayerState` only sets the snake_case fields on the camelCase OUTPUT interface (`PlayerStateData`) — so two interfaces exist with overlapping field names but different conventions: `domain.PlayerState` (snake-mixed) and `websocket.PlayerStateData` (camel-only). `api.ts` ships a THIRD `PlayerState` interface (line 79-90) with the same snake-mixed shape — three Redux/component callers consume different interface names. Additionally, `api.ts:62-64` declares `PlayerVolumeRequest.volume: number  // 0.0 - 1.0` and `domain.ts:135` declares `PlayerState.volume: number  // 0.0 - 1.0`, but the backend `SetVolumeRequest.clamp_volume` enforces `0.0-100.0` (`player.py:101-102`) and `PlayerState.volume: int = 80` defaults to 80 (0-100 scale). The frontend's actual production call site at `usePlaybackControl.ts:345` correctly sends `Math.round(validVolume)` 0-100 — so the runtime is right but the type contract is wrong. The `usePlayerAPI.ts:231` legacy hook still sends `?volume=N` as a query param which the backend does NOT accept (backend takes JSON body) — separate but related issue.
- **Evidence**:
  ```typescript
  // frontend/src/types/domain.ts:132-147 — snake_case fields in a camelCase shape
  export interface PlayerState {
    currentTrack: Track | null;
    isPlaying: boolean;
    volume: number; // 0.0 - 1.0                       ← wrong; backend uses 0-100
    position: number;
    duration: number;
    queue: Track[];
    queueIndex: number;
    isLoading: boolean;
    error: string | null;
    gapless_enabled: boolean;                          ← snake-case in a camelCase shape
    crossfade_enabled: boolean;
    crossfade_duration: number;
  }
  
  // frontend/src/types/api.ts:62-64
  export interface PlayerVolumeRequest {
    volume: number; // 0.0 - 1.0                       ← wrong; backend clamps 0-100
  }
  
  // frontend/src/types/api.ts:79-90 — duplicate PlayerState with the same defects
  export interface PlayerState {
    currentTrack: TrackInfo | null;
    isPlaying: boolean;
    volume: number;                                    ← unit not documented
    position: number;
    duration: number;
    queue: TrackInfo[];
    queueIndex: number;
    gapless_enabled: boolean;                          ← snake-case
    crossfade_enabled: boolean;
    crossfade_duration: number;
  }
  ```
  ```python
  # backend/routers/player.py:95-102
  class SetVolumeRequest(BaseModel):
      volume: float
      @field_validator('volume')
      def clamp_volume(cls, v: float) -> float:
          return max(0.0, min(100.0, v))                ← 0-100 is canonical
  
  # backend/player_state.py:62
  volume: int = 80                                       ← 0-100 default
  ```
- **Impact**: (a) Multiple `PlayerState` interfaces (3 total: `domain`, `api`, `websocket.PlayerStateData`) with the same field names but different shapes — IDE will autocomplete the wrong one and component code that assumes "volume 0-1" will visually display 0.8 as 80%. (b) The `last_updated` field on `api.EnhancementSettingsResponse` is never sent — frontend code that reads it gets `undefined`. (c) `usePlayerAPI.ts` is a deprecated hook that still ships the wrong call signature (query param vs body) — if any code path reaches it, the volume change silently fails. (d) Per CLAUDE.md "Frontend: components < 300 lines, all colors via tokens, camelCase" — the snake_case mix violates the convention.
- **Siblings**: BE-NEW-43 (`repeat_mode`) — already fixed. BE-NEW-47 (`TrackInfo.filepath/artwork_url`) — already fixed. This is the "long tail" of the same camel/snake naming drift across three frontend type files.
- **Suggested Fix**: (a) Rename `domain.PlayerState.gapless_enabled`/`crossfade_enabled`/`crossfade_duration` to camelCase (matches `websocket.PlayerStateData` which already does). Drop the `last_updated` field from `api.EnhancementSettingsResponse`. (b) Annotate `volume: number  // 0-100 integer scale` on all three interfaces. (c) Delete `api.PlayerState` (duplicate of `websocket.PlayerStateData`) and re-export the websocket version. (d) Fix or delete `usePlayerAPI.setVolume` to use JSON body.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-11: `presets` payload at `GET /api/processing/presets` mixes camelCase (`targetLufs`, `lowMid`, `highMid`) into otherwise snake_case backend response
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/processing_api.py:403-515` (preset dict literals)
- **Status**: NEW
- **Description**: The backend everywhere else uses snake_case for JSON keys. The `/api/processing/presets` endpoint returns a deeply-nested `{presets: {...}}` dict where the inner EQ band names are camelCase (`lowMid`, `highMid`) and the level-matching target is camelCase (`targetLufs`). All other audio terms in the same dict use snake_case (`level_matching`, `attack`, `release`, `threshold`, `ratio`). The frontend type is `PresetsResponse: { presets: dict[str, Any] }` so the inconsistency is hidden — but anyone wiring a typed reader to these keys must dual-case.
- **Evidence**:
  ```python
  # backend/routers/processing_api.py:414-415 — camelCase mixed in
  "level_matching": {"enabled": True, "targetLufs": -16}       # ← camelCase nested in snake_case
  ...
  # backend/routers/processing_api.py:423-429
  "eq": {
      "enabled": True,
      "low": 1,
      "lowMid": 0.5,                                            # ← camelCase
      "mid": 0,
      "highMid": 1,                                             # ← camelCase
      "high": 2
  },
  ```
- **Impact**: Aesthetic for now (the frontend just consumes opaque presets). If a future PR adds typed EQ band manipulation, the case mismatch will be a footgun.
- **Siblings**: #2748 (CLOSED — `ProcessingSettings.level_matching` camelCase alias) was the same flavor, just on the request side.
- **Suggested Fix**: Pick one. Rename `targetLufs` → `target_lufs`, `lowMid` → `low_mid`, `highMid` → `high_mid` consistently across the 5 presets. Add a regression test that all keys in the presets payload are snake_case.

---

> _Dim 5 — Schema Consistency_

### BE-SCH-12: `JobStatusResponse.status: str` should be `Literal["queued", "processing", "completed", "failed", "cancelled"]` (or the `ProcessingStatus` enum); `QueueInfoResponse.repeat_enabled: bool` diverges from `PlayerState.repeat_mode: str`
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - `routers/processing_api.py:102-108` (`JobStatusResponse.status: str`)
  - `routers/processing_api.py:117-120` (`JobListResponse.jobs: list[dict[str, Any]]`)
  - `routers/processing_api.py:367-368` (`status: str | None = None` query parameter)
  - `routers/player.py:142-153` (`QueueInfoResponse.repeat_enabled: bool | None` instead of `repeat_mode: Literal`)
- **Status**: NEW
- **Description**: `JobStatusResponse.status` is typed `str` although the backend `ProcessingStatus` enum already exists at `core/processing_engine.py:` and is used in line 376 (`valid_statuses = [s.value for s in ProcessingStatus]`). Same for the `status` query parameter at line 367 (typed `str | None`, with manual runtime validation). FastAPI/Pydantic would automatically generate the OpenAPI enum spec if these were typed as `ProcessingStatus` directly. Separately, `QueueInfoResponse` declares `repeat_enabled: bool | None` while the canonical `PlayerState.repeat_mode: str` is `Literal["off", "all", "one"]` per the post-#3501 fix — the queue response is a bool that's silently lossy (loses the distinction between "all" and "one"). Frontend `Queue` type at `domain.ts:121-126` correctly declares `repeatMode: 'off' | 'all' | 'one'`.
- **Evidence**:
  ```python
  # backend/routers/processing_api.py:102-108
  class JobStatusResponse(BaseModel):
      job_id: str
      status: str                                       # ← should be Literal or ProcessingStatus
      progress: float
      error_message: str | None = None
      result_data: dict[str, Any] | None = None         # ← also unstructured
  
  # backend/routers/processing_api.py:367
  async def list_jobs(status: str | None = None, ...):  # ← should be ProcessingStatus | None
      ...
      valid_statuses = [s.value for s in ProcessingStatus]
      if status not in valid_statuses:
          raise HTTPException(400, ...)                  # ← manual when Literal would 422 at the boundary
  
  # backend/routers/player.py:148-152
  class QueueInfoResponse(BaseModel):
      ...
      shuffle_enabled: bool | None = None
      repeat_enabled: bool | None = None                  # ← should be repeat_mode: Literal["off","all","one"]
  ```
- **Impact**: (a) OpenAPI docs show `string` instead of an enum for job status. (b) Frontend's `Queue.repeatMode` cannot be populated from `GET /api/player/queue` because the endpoint only returns `repeat_enabled: bool` — frontend has to call `GET /api/player/status` instead, defeating the queue endpoint. (c) `status: str` allows arbitrary strings through; the 400 check is manual.
- **Siblings**: BE-NEW-43 / #3501 fixed the `repeat_mode` semantic on `PlayerState` but the related `QueueInfoResponse` field wasn't updated. SetVolumeRequest similarly clamps in a validator instead of declaring `Field(ge=0.0, le=100.0)`.
- **Suggested Fix**: (a) `from core.processing_engine import ProcessingStatus` then `status: ProcessingStatus` on `JobStatusResponse` and the `list_jobs` query param. Drop the manual `valid_statuses` check. (b) Rename `QueueInfoResponse.repeat_enabled` → `repeat_mode: Literal["off","all","one"]` for parity with `PlayerState`. Update the frontend `Queue` consumer if it currently reads from `repeat_enabled`. (c) Replace `SetVolumeRequest.clamp_volume` validator with `volume: float = Field(ge=0.0, le=100.0)` so OpenAPI shows the bounds.

---

> _Dim 6 — Middleware & Config_

### BE-MW-8: `ALLOWED_WS_ORIGINS` does not include `https://` — HTTPS dev frontend would be rejected
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/globals.py:29-38`
- **Status**: NEW
- **Description**: The allowlist is constructed from `schemes = ("http", "ws")`. If a developer ever runs the Vite frontend behind a TLS dev cert (e.g. for testing PWA / service worker features that require secure context) the page origin becomes `https://localhost:3000`, the WS upgrade carries `Origin: https://localhost:3000`, and `ConnectionManager.connect` rejects it with code 1008. The CORS allowlist in `config/middleware.py:196-199` has the same scheme limitation. Auralis is desktop-only today, but the README's "Run (components) — frontend on :3000 via Vite" workflow is the documented dev path; any future HTTPS-on-Vite setup is silently broken.
- **Evidence**:
  ```python
  # config/globals.py:30-38
  ALLOWED_WS_ORIGINS = frozenset(
      {f"{scheme}://{host}:{port}"
       for scheme in ("http", "ws")
       for host in ("localhost", "127.0.0.1")
       for port in _DEV_PORTS}
      | {"file://"}
  )
  ```
- **Impact**: Niche dev workflow breaks silently with a "WebSocket connection rejected" warning. Zero production impact today.
- **Siblings**: `config/middleware.py:195-199` (CORS) shares the same gap.
- **Suggested Fix**: Extend `schemes` to `("http", "https", "ws", "wss")` in both `globals.py` and `middleware.py`. Adds 64 more entries to the set — still trivial.

---

> _Dim 6 — Middleware & Config_

### BE-MW-9: `ProcessingEngine` and `StreamlinedCacheWorker` failures leave dict entries truthy — routers return false-positive 2xx
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/startup.py:329-341, 352-366`
- **Status**: NEW
- **Description**: Both block follow the pattern: `globals_dict['X'] = SomeService(...)` BEFORE attempting to `await X.start()` or check that the worker spawned. If startup raises mid-block, the dict still holds the partially-initialized object (the except handler logs and continues without nulling). `processing_api` routes check `if processing_engine is None` and return 503; with a stale truthy entry they return 200 / 202 for submissions that will never be processed (the worker task is dead). Same for the streamlined cache — chunk endpoints will try to hit a cache backed by a worker that's not draining.
- **Evidence**:
  ```python
  # startup.py:329-341
  try:
      ...
      globals_dict['processing_engine'] = ProcessingEngine(max_concurrent_jobs=2)
      set_processing_engine(globals_dict['processing_engine'])
      globals_dict['_processing_worker_task'] = spawn_background_task(...)
      logger.info("✅ Processing Engine initialized")
  except Exception as e:
      logger.error(f"❌ Failed to initialize Processing Engine: {e}")
      # NOTE: globals_dict['processing_engine'] is NOT reset to None here
  ```
- **Impact**: User submits a processing job → 202 with `job_id` → polls `/api/processing/job/{job_id}` → 404 forever because the worker isn't there to register it. No surface error, just stuck "queued". For the cache, every chunk request takes the slow path through `ChunkedAudioProcessor` because the cache is empty and stays empty — silent performance regression.
- **Siblings**: BE-MW-3 covers the same class for the LibraryManager / fingerprint_queue path. This is the "single-service" version of that bug.
- **Suggested Fix**: After both `start_worker()` / `start()` calls succeed, only then assign to `globals_dict`. Or, on except, explicitly `globals_dict.pop('processing_engine', None)` / `globals_dict.pop('streamlined_cache', None)`.

---

> _Dim 6 — Middleware & Config_

### BE-MW-10: `is_dev_mode` resolution duplicated across `main.py` and `config/app.py`
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/main.py:168` + `auralis-web/backend/config/app.py:35`
- **Status**: NEW
- **Description**: Identical "is this dev mode?" computation appears in two places: `main.py:168` (`"--dev" in sys.argv or os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")`) and `config/app.py:35` (same expression with operand order reversed). A future change to dev-mode signaling (e.g. adding `AURALIS_DEV=1`) must be applied to both; the two are guaranteed to drift.
- **Evidence**:
  ```python
  # main.py:168
  is_dev_mode = "--dev" in sys.argv or os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")

  # config/app.py:35
  is_dev = os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes") or "--dev" in sys.argv
  ```
- **Impact**: Maintenance hazard; no runtime defect today.
- **Siblings**: None.
- **Suggested Fix**: Move to `config/app.py` (or a new `config/env.py`) as `is_dev_mode() -> bool` and import from both sites.

---

> _Dim 6 — Middleware & Config_

### BE-MW-11: `CSP` header allows `'unsafe-inline'` for scripts and styles
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware.py:63-71`
- **Status**: NEW
- **Description**: `Content-Security-Policy` includes `script-src 'self' 'unsafe-inline'` and `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`. `'unsafe-inline'` defeats CSP's XSS protection for inline `<script>` tags and `style=` attributes. On a single-user desktop app served via Electron this is far less critical than on a public web app, but the `Content-Security-Policy` header is present specifically as a defense-in-depth measure — leaving the easiest-to-exploit holes wide open partially negates the point. Vite produces inline preload scripts and React inline styles by default, which is presumably why this was added.
- **Evidence**:
  ```python
  # config/middleware.py:63-71
  response.headers["Content-Security-Policy"] = (
      "default-src 'self'; "
      "script-src 'self' 'unsafe-inline'; "
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
      ...
  )
  ```
- **Impact**: Defense-in-depth weaker than the header implies. Real risk is bounded by Electron's process isolation and absence of remote content.
- **Siblings**: None.
- **Suggested Fix**: Investigate replacing `'unsafe-inline'` with hash-based / nonce-based allowances generated at build time by Vite. If unfixable in the foreseeable future, drop the CSP header rather than ship a paper one — or at least document why `'unsafe-inline'` is intentional.

---

> _Dim 6 — Middleware & Config_

### BE-MW-12: HTTP rate-limit per-path windows are documented but the values are magic numbers with no env-var override
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware.py:85-90`
- **Status**: NEW
- **Description**: `_RATE_LIMITS` hard-codes `(5, 60)` for `/api/files/upload`, `(10, 60)` for `/api/processing`, `(2, 60)` for `/api/library/scan`, `(20, 60)` for `/api/similarity`. None of these can be overridden via env-var, settings UI, or config file. The limits assume a "typical" user; power users running large library imports or batch processing can hit them legitimately. The 2/minute scan limit in particular is awkward — a user re-triggering a scan after seeing an error is one click away from a 429.
- **Evidence**:
  ```python
  # config/middleware.py:85-90
  _RATE_LIMITS: dict[str, tuple[int, int]] = {
      "/api/files/upload": (5, 60),
      "/api/processing": (10, 60),
      "/api/library/scan": (2, 60),
      "/api/similarity": (20, 60),
  }
  ```
- **Impact**: Power-user friction; no security defect.
- **Siblings**: None.
- **Suggested Fix**: Read overrides from env vars (`AURALIS_RATE_LIMIT_SCAN=10/60`) at class init. Document in `README.md`.

---

> _Dim 6 — Middleware & Config_

### BE-MW-13: `EVICTION_INTERVAL = 256` and other middleware magic numbers are undocumented
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware.py:93`, `websocket/websocket_security.py:26-28`
- **Status**: NEW
- **Description**: `_EVICTION_INTERVAL = 256` is referenced as "evict stale keys every 256 rate-limited requests to bound memory (#2630)" — but 256 is arbitrary, there's no benchmark or doc justifying the choice, and the eviction sweep walks the entire `_windows` dict (`O(n * m)` where n=keys and m=avg timestamps-per-key) inside the global asyncio lock. On a desktop app this is a non-issue (n is tiny), but it's worth a comment for the next maintainer who tries to tune it.
- **Evidence**:
  ```python
  # config/middleware.py:93
  _EVICTION_INTERVAL = 256

  # websocket_security.py:26-28
  MAX_MESSAGE_SIZE = 64 * 1024
  MAX_MESSAGES_PER_SECOND = 10
  MESSAGE_WINDOW_SECONDS = 1.0
  ```
- **Impact**: Maintainability only.
- **Siblings**: None.
- **Suggested Fix**: Move to a `config/limits.py` constants module with docstrings explaining the trade-off (memory vs eviction cost).

---

> _Dim 6 — Middleware & Config_

### BE-MW-14: WebSocket `manager.connect` logs `client.host:client.port` at INFO even when origin is rejected one line earlier
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/globals.py:67-69, 74-76`
- **Status**: NEW
- **Description**: When the Origin header is rejected at line 66-69, the method returns. Good. But when the origin is accepted (or empty), the very next operation (lines 74-76) logs `f"WebSocket connected from {client.host}:{client.port}. Total connections: ..."` at INFO. With BE-MW-7 (empty-origin clients pass), every `wscat` / Python script connection logs the connecting process at INFO. Combined with BE-MW-6 (path validation INFOs), the dev console scrolls past important events during normal use.
- **Evidence**:
  ```python
  # config/globals.py:74-76
  client = websocket.client
  client_id = f"{client.host}:{client.port}" if client else "unknown"
  logger.info(f"WebSocket connected from {client_id}. ...")
  ```
- **Impact**: Log noise.
- **Siblings**: `disconnect` (line 90) logs at INFO per disconnect; `broadcast` (line 122) logs at INFO whenever it removes stale connections.
- **Suggested Fix**: Drop to DEBUG; keep INFO only for the rejection path (which already logs at WARNING — line 67 — that's fine).

---

> _Dim 6 — Middleware & Config_

### BE-MW-15: `RateLimitMiddleware` returns generic `"Too many requests"` — no body identifies which rule fired
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware.py:154-158`
- **Status**: NEW
- **Description**: The 429 body is `{"detail": "Too many requests"}` with `Retry-After` header. The frontend gets no programmatic signal of which limit (upload vs scan vs similarity) was hit — it can only guess from the request URL. For a UX that says "you're scanning too often, wait 23s" the client has to remember the path and parse `Retry-After`. The middleware already knows both `path` and `limit_rule`; including them in the JSON would cost nothing.
- **Evidence**:
  ```python
  # config/middleware.py:154-158
  return JSONResponse(
      status_code=429,
      content={"detail": "Too many requests"},
      headers={"Retry-After": str(retry_after)},
  )
  ```
- **Impact**: Frontend UX; no defect.
- **Siblings**: None.
- **Suggested Fix**: `content={"detail": "Too many requests", "rule": prefix, "retry_after_seconds": retry_after}`.

---

> _Dim 6 — Middleware & Config_

### BE-MW-16: `validate_user_chosen_directory` trusts user choice — comment says "single-user desktop app", but no enforcement that the caller is the user
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/security/path_security.py:230-277`
- **Status**: NEW
- **Description**: Used only by `routers/settings.py:103` for adding scan folders. The function skips the allow-list check that `validate_scan_path` / `validate_file_path` enforce. Its docstring justifies this with: "Auralis is a single-user desktop app. When the user explicitly selects a folder to scan, we trust their choice". But there is no verification that the REST call came from the local user vs an attacker. Today the WS Origin check (config/globals.py) is the only auth — there's no equivalent on REST endpoints for `settings/scan-folders`. So any local process that can talk to `127.0.0.1:8765` can call this endpoint with arbitrary paths (e.g. `/etc`, `/root`) and add them to the allowlist, which then propagates to `validate_file_path` permitting reads of any file in that tree via the metadata endpoints.
- **Evidence**:
  ```python
  # security/path_security.py:236-245 — docstring
  """
  Auralis is a single-user desktop app. When the user explicitly selects a
  folder to scan, we trust their choice and only enforce basic safety checks
  (no traversal, must exist, must be readable) without restricting to
  predefined allowed directories.
  """
  # No auth check before line 103 of routers/settings.py.
  ```
- **Impact**: A local process can register `/etc` (or any readable dir), then read individual files via `/api/metadata/tracks/{id}` if a track row pointing into that dir can be inserted. Combined with the lack of `unregister_allowed_directory` (BE-MW-4), the registration persists for the session.
- **Siblings**: `routers/library.py:821 reset_library` requires the `X-Confirm-Reset: RESET` header as a safety guard — same pattern could apply here.
- **Suggested Fix**: At minimum, require an `X-Confirm-Scan-Folder: ADD` header on the add endpoint, mirroring the reset_library pattern. Long term, recognize that "single-user desktop" doesn't mean "anything local is trusted" — any local code execution that touches port 8765 is currently equivalent to library read access.

---

> _Dim 6 — Middleware & Config_

### BE-MW-17: `cleanup` and `disconnect` errors in `system.py` WebSocket finally-block are caught silently but state remains
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/routers/system.py:824-888`
- **Status**: NEW
- **Description**: The finally-block was hardened by #3521 (BE-NEW-63) to wrap each step in its own try/except so one failure doesn't skip later steps. Each step logs `logger.warning("X cleanup failed", exc_info=True)` and proceeds. Good. **But the residual state isn't cleared.** If `_rate_limiter.cleanup(websocket)` raises at line 866, the rate-limit bucket for this ws_id stays in the dict (combined with BE-MW-1, the next reuse picks up this bucket). If `manager.disconnect(websocket)` raises at line 886, the ws stays in `manager.active_connections` and the next `broadcast()` will try to send to a dead socket (broadcast does handle this via stale-connection eviction at lines 117-122, so that's OK for the broadcast itself, but `len(active_connections)` is overstated until the next broadcast).
- **Evidence**:
  ```python
  # system.py:864-868
  try:
      _rate_limiter.cleanup(websocket)
  except Exception:
      logger.warning("Rate-limiter cleanup failed", exc_info=True)
  # If this raised, the entry remains in _rate_limiter.message_log forever.
  ```
- **Impact**: Slow leak under abnormal conditions; rare in practice because `cleanup` just does `del`.
- **Siblings**: None.
- **Suggested Fix**: After each catch block, do a "best-effort second pass" — e.g. directly mutate `_rate_limiter.message_log.pop(id(ws), None)` ignoring exceptions. Or accept the leak and document it.

---

> _Dim 6 — Middleware & Config_

### BE-MW-18: `routes.py` hard-codes router imports — disabled features still pulled at module import
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/routes.py:16-31`
- **Status**: NEW
- **Description**: All 14 routers are imported at module load (lines 16-31) regardless of `HAS_AURALIS` / `HAS_PROCESSING` / `HAS_SIMILARITY` flags. Their factory functions are only INVOKED if the relevant `HAS_*` is True, but the imports happen unconditionally. If any router's import-time code fails (e.g. `routers/similarity.py` importing `auralis.analysis.fingerprint`), `setup_routers` blows up before any conditional router protection kicks in. The intent of #2324 ("syntax errors or missing transitive deps should degrade gracefully") is only honored for `processing_api`, `cache_streamlined`, `similarity`, `webm_streaming` because those wrap their `app.include_router(...)` in try/except — but the imports at lines 16-31 are not protected and will hard-crash setup if any router module is broken.
- **Evidence**:
  ```python
  # config/routes.py:16-31 — unprotected imports
  from routers.albums import create_albums_router
  from routers.artists import create_artists_router
  ...
  from routers.similarity import create_similarity_router
  from routers.webm_streaming import create_webm_streaming_router
  from routers.system import create_system_router
  ```
- **Impact**: A bug in any router module crashes the entire backend at startup. Defense-in-depth that already exists at the `include_router` call site is bypassed for the import.
- **Siblings**: `main.py:77-93` does protect optional `auralis.*` imports with try/except — same pattern should apply here.
- **Suggested Fix**: Either wrap each `from routers.X import create_X_router` in its own try/except (matching `main.py:77-93`), or move the imports to inside `setup_routers` so they only run if the corresponding `HAS_*` flag is true.

---

> _Dim 7 — Error Handling_

### BE-EH-10: WebMEncoderError generic constructor passes `str(e)` (informational leak surface)
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/encoding/webm_encoder.py:242-244`
- **Status**: NEW (encoding currently has no live caller, but the class is exported)
- **Description**: The generic catch-all at the bottom of `encode_to_webm_opus` re-raises with the raw exception text:
  ```python
  except Exception as e:
      logger.error(f"WebM encoding failed: {e}")
      raise WebMEncoderError(f"Encoding failed: {str(e)}") from e
  ```
  The class is `WebMEncoderError`; if any future router catches this and embeds the string in a 500 detail, the leak surface returns. There is no current caller (`encode_to_webm_opus` is exported from `encoding/__init__.py` but not imported by any router today — the backend uses `wav_encoder` instead), so the impact is latent.
- **Impact**: Latent — would leak codec/path/internal detail if encoder is ever re-wired. No current user-visible impact.
- **Suggested Fix**: `raise WebMEncoderError(f"Encoding failed: {type(e).__name__}") from e`. The `from e` preserves the chain server-side; the string passed to clients is class-only.

---

> _Dim 7 — Error Handling_

### BE-EH-11: Seek-path outer error handler does not pass `error_code="SEEK_ERROR"`
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1891-1894`
- **Status**: NEW
- **Description**: The seek-path outer `except Exception:` calls `self._send_error(websocket, track_id, "Audio streaming failed")` without `error_code="SEEK_ERROR"`. The default falls back to `"STREAMING_ERROR"`. But the seek-path's intra-loop TimeoutError at line 1725 correctly uses `error_code="SEEK_ERROR"`. The intra-loop chunk-error at 1855-1875 doesn't pass either, also defaulting. The result is that frontend recovery code keyed on `code === "SEEK_ERROR"` only fires for the 30s processor-init timeout, not for the much more common in-flight failure.
- **Evidence**:
  ```python
  # core/audio_stream_controller.py:1891-1894
  except Exception as e:
      logger.error(f"Seek streaming failed: {e}", exc_info=True)
      if self._is_websocket_connected(websocket):
          await self._send_error(websocket, track_id, "Audio streaming failed")   # ← code defaults to STREAMING_ERROR
  ```
- **Impact**: Frontend code-routed recovery (e.g., seek-resume-via-buffered-position) doesn't fire for in-flight seek failures.
- **Suggested Fix**: Pass `error_code="SEEK_ERROR"` here (and at line 1870-1875 inside the chunk-error branch, for consistency).

---

> _Dim 7 — Error Handling_

### BE-EH-12: `routers/system.py:815` `Unknown message type: {message_type}` reflects caller-supplied string unsanitised
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/system.py:813-815`
- **Status**: NEW (sibling of CLOSED #3332 — caller-controlled status reflection)
- **Description**: Unknown WS message types are echoed back to the client by interpolating the raw value into the error payload. The validator at `websocket/validator.py:validate_and_parse_message` already caps message size to 64 KB so the field is bounded, but it's still a caller-controlled echo — typically lower-priority than a server-side info leak but can be used for log-injection if `message_type` contains escape characters that the frontend log component renders unsafely.
- **Evidence**:
  ```python
  # routers/system.py:813-815
  message_type = message.get("type", "unknown")
  logger.warning(f"Unknown WebSocket message type: {message_type!r}")
  await send_error_response(websocket, "unknown_message_type", f"Unknown message type: {message_type}")
  ```
- **Impact**: Minor — the WS protocol is browser-only (frontend); unlikely to be a real exploit vector, but the pattern is the same as the closed #3332.
- **Suggested Fix**: Either strip to alnum-only before interpolation, or send a generic `"Unrecognised message type"` and rely on the server-side log for forensics.

---

> _Dim 7 — Error Handling_

### BE-EH-13: `routers/files.py:179` `Path.home() / ".auralis" / "uploads"` mkdir runs on event loop
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/files.py:179-180`
- **Status**: NEW
- **Description**: `upload_dir.mkdir(parents=True, exist_ok=True)` is sync filesystem I/O on the event loop, immediately after the file was loaded in a thread. Slow disk → loop stall. The rest of the upload pipeline correctly offloads via `asyncio.to_thread`. Inconsistency rather than a real DoS, but it's a missed line during the #3494 sweep.
- **Impact**: Brief event-loop stall (≤ 50 ms on a healthy disk; seconds on a network mount).
- **Suggested Fix**: Wrap in `await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)` — or hoist to module-level startup.

---

> _Dim 7 — Error Handling_

### BE-EH-14: `WebMEncoderError` and `WAVEncoderError` not mapped in global handler — surface as 500 with generic detail
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/encoding/{wav_encoder.py:30, webm_encoder.py:34}`, no handler in `config/app.py`
- **Status**: NEW
- **Description**: Both encoder modules define their own `*Error(Exception)` subclasses but `config/app.py` only has handlers for `HTTPException`, `RequestValidationError`, and `Exception`. Callers in `webm_streaming.py:490-496` catch `WAVEncoderError` explicitly and translate to 500; if a future caller forgets, the catch-all returns "Internal server error" with no class context in the response. Acceptable but inconsistent with the other audio-domain errors which raise `HTTPException` with category messages.
- **Impact**: Low — current callers all handle these explicitly; future callers may not.
- **Suggested Fix**: Either add `@app.exception_handler(WAVEncoderError | WebMEncoderError)` returning 500 with a category message, or document that encoder errors must always be translated by the caller.

---

> _Dim 7 — Error Handling_

### BE-EH-15: `services/library_auto_scanner.py:119` `start()` does not capture done-callback on its own task
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:117-123`
- **Status**: NEW (subsumed by BE-EH-8 but worth flagging separately because the closed #3543 description explicitly mentioned "no done-callback" as part of the LOW finding and reportedly fixed it — the create_task call was untouched)
- **Description**: #3543's closure comment claimed the broadcast-leak AND the done-callback gap were addressed; only the broadcast was. `start()` still creates the task without `add_done_callback`.
- **Impact**: Same as BE-EH-8.
- **Suggested Fix**: Same as BE-EH-8.

---

> _Dim 7 — Error Handling_

### BE-EH-16: `routers/library.py:332` `except Exception: pass` swallows lyrics-tag parse errors silently
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/library.py:330-333`
- **Status**: NEW (sibling of CLOSED #2172 — bare except in lyrics extraction; that fix replaced bare `except:` with `except Exception:` but did not add a log line)
- **Description**: The MP4 `\xa9lyr` atom lookup is wrapped in `except Exception: pass`. A malformed MP4 atom that raises (e.g., `KeyError` on a non-list value) is silently dropped — the user sees "no lyrics" with no explanation. There's no `logger.debug` to aid diagnosis.
- **Evidence**:
  ```python
  # routers/library.py:328-333
  if isinstance(audio_file, MP4):
      try:
          lyrics_text = audio_file.get('\xa9lyr', [None])[0]
      except Exception:
          pass
  ```
- **Impact**: Diagnostic — bug reports of "no lyrics on M4A" lack any server-side trace.
- **Suggested Fix**: `except Exception: logger.debug("MP4 lyrics atom parse failed for %s", track.filepath, exc_info=True); pass`.

---

> _Dim 8 — Performance_

### BE-PF-9: `services/artwork_downloader.py` opens `aiohttp.ClientSession` per request and writes artwork to disk synchronously — regression of #3558
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/services/artwork_downloader.py:153, 222, 291-292`
- **Status**: Regression of #3558 (closed 2026-05-25 with no diff)
- **Description**: `_try_musicbrainz` (line 153) and `_try_itunes` (line 222) both do `async with aiohttp.ClientSession() as session:` — a fresh session per request. The `_save_artwork` helper at line 291-292 does:
  ```python
  with open(filepath, "wb") as f:
      f.write(data)
  ```
  on an asyncio call path. The closed issue #3558 ("[2026-05-25] LOW - `services/artwork_downloader.py` opens `aiohttp.ClientSession` per request and writes artwork to disk synchronously from async context") never received a diff.
- **Evidence**:
  ```python
  # services/artwork_downloader.py:153, 222
  async with aiohttp.ClientSession() as session:   # new session per call — no connection pool reuse
      ...
  # services/artwork_downloader.py:291-292 (called from async path)
  with open(filepath, "wb") as f:
      f.write(data)
  ```
- **Impact**: Artwork downloads are typically out-of-band, but during bulk library scan + artwork backfill, each call opens a new TCP connection (no keep-alive across calls) and blocks the loop on `f.write()`. With many concurrent backfills, the event-loop blocking is measurable.
- **Siblings**: None.
- **Suggested Fix**: Lift `aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=4, ttl_dns_cache=300))` to a singleton initialised in `__init__` and reuse across calls; close it in a `close()` method called from lifespan shutdown. Wrap the file write in `asyncio.to_thread(filepath.write_bytes, data)` (or use `aiofiles`).

---

> _Dim 8 — Performance_

### BE-PF-10: `services/queue_service.py:remove_track_from_queue` and `clear_queue` call sync `audio_player.load_file()` / `audio_player.stop()` on the event loop
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/services/queue_service.py:428, 678`
- **Status**: NEW (sibling of #3716 which fixed the same pattern in `playback_service.py`)
- **Description**: After fix #3716 wrapped `PlaybackService.{play,pause,stop,seek,set_volume}` in `to_thread`, two analogous sync calls remain in `queue_service`:
  - Line 428: `self.audio_player.load_file(file_path)` — sync disk I/O + SoundFile open on the event loop after removing the currently-playing track.
  - Line 678: `self.audio_player.stop()` — sync engine stop on the event loop in `clear_queue`.
- **Evidence**:
  ```python
  # services/queue_service.py:425-429
  if new_current and hasattr(self.audio_player, 'load_file'):
      file_path = new_current.get('filepath') or new_current.get('file_path')
      if file_path:
          self.audio_player.load_file(file_path)         # SYNC, disk I/O
          logger.info(f"Removed current track; loaded next: {new_current.get('id')}")
  ```
  ```python
  # services/queue_service.py:676-678
  if hasattr(self.audio_player, 'stop'):
      self.audio_player.stop()                            # SYNC
  ```
- **Impact**: Removing the currently-playing track stalls the loop for one SoundFile open (~50-200ms). `clear_queue` stalls for the duration of `audio_player.stop()` (usually fast, but can block on `_audio_lock`).
- **Siblings**: BE-PF-1.
- **Suggested Fix**: `await asyncio.to_thread(self.audio_player.load_file, file_path)` and `await asyncio.to_thread(self.audio_player.stop)`. Matches the existing pattern used at queue_service.py:307-308.

---

> _Dim 8 — Performance_

### BE-PF-11: `_get_processor_cache_key` in `processing_engine.py` hashes config via `getattr(adaptive, 'eq_gains', None)` — relies on dynamically-attached attributes that no engine code reads
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/processing_engine.py:285-297`
- **Status**: Existing: #3528 (closed — fix shipped 2026-05-25; verified key includes the explicit fields). LOW residual concern only: the key still depends on dynamically-attached attributes that `_create_processor_config` decided to STOP setting after BE-NEW-32 (line 380-407 now logs unsupported settings instead of writing them).
- **Description**: After the BE-NEW-32 fix landed, `_create_processor_config` no longer writes `eq_gains` / `compressor` / `target_lufs` / `gain` / `genre_override` to `config.adaptive`. The cache key, however, still calls `getattr(adaptive, "eq_gains", None)` etc., which all return `None` for every job. Effectively the cache key collapses to `(mode, sample_rate, adaptive_mode, mastering_profile)` — five constants for every adaptive/reference/hybrid job + 5 presets = ~15 unique keys total in practice. The 5-entry FIFO eviction (line 347-350) caps it, but the 5 extra `getattr`s are dead computation on every job.
- **Evidence**:
  ```python
  # core/processing_engine.py:285-297
  adaptive = getattr(config, "adaptive", None)
  key_parts: list[str] = [
      mode,
      str(config.internal_sample_rate),
      getattr(adaptive, "mode", "unknown") if adaptive else "unknown",
      getattr(config, "mastering_profile", ""),
      repr(getattr(adaptive, "eq_gains", None)) if adaptive else "",   # always None
      repr(getattr(adaptive, "compressor", None)) if adaptive else "", # always None
      repr(getattr(adaptive, "target_lufs", None)) if adaptive else "",# always None
      repr(getattr(adaptive, "gain", None)) if adaptive else "",       # always None
      repr(getattr(adaptive, "genre_override", None)) if adaptive else "", # always None
  ]
  ```
- **Impact**: Five wasted `getattr` calls per job (microseconds). The real issue is documentation/staleness — the key looks like it differentiates EQ-customised jobs, but it can't (the writer no longer writes them). Future contributors will assume the key is meaningful.
- **Siblings**: None.
- **Suggested Fix**: Either delete the 5 dead key parts and update the comment, or wire the actual reader (#3490 follow-up) and reactivate the writers. Currently the code lies about caching granularity.

---

> _Dim 8 — Performance_

### BE-PF-12: `MAX_CONCURRENT_STREAMS = 10` is a module constant — undocumented and not exposed for per-deployment tuning
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:67-72`
- **Status**: NEW (documentation/configurability LOW)
- **Description**: The hard cap of 10 concurrent streams is appropriate for a desktop-only deployment (single user, A/B compare = 2 streams max) but exists as a magic number with no env-var override, no config-file knob, and no per-connection scoping. The comment cites issue #2185 for the rationale, but operators can't tune this without a code edit + rebuild. The audit project note (`project_desktop_only.md`) confirms desktop-only is the intended scope, so a low limit is fine — the LOW is purely about traceability.
- **Evidence**:
  ```python
  # core/audio_stream_controller.py:64-72
  # Maximum number of concurrent audio streams (enhanced, normal, seek).
  # Each stream holds a ChunkedProcessor in memory; unbounded concurrency
  # causes OOM under load (issue #2185).
  MAX_CONCURRENT_STREAMS: int = 10
  # Module-level shared semaphore so the cap is enforced across ALL
  # AudioStreamController instances (fixes #2469: per-instance semaphore
  # was created fresh per request, making the cap non-functional).
  _global_stream_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)
  ```
- **Impact**: None today (desktop-only, 10 is plenty). If the deployment model ever changes (LAN-shared backend, multi-user), the constant needs to grow — and there's no obvious place to put the override.
- **Siblings**: `_SEND_QUEUE_MAXSIZE = 4`, `_PROCESSOR_CACHE_MAX = 32`, `_FINGERPRINT_WORKERS`, `cache_sizes` in memory_monitor — same pattern across the codebase.
- **Suggested Fix**: Read from `os.environ.get("AURALIS_MAX_CONCURRENT_STREAMS", "10")` with int parse. Document in `auralis-web/backend/CONFIG.md` (or wherever the magic numbers are tracked). Same treatment for `_SEND_QUEUE_MAXSIZE`.

---

> _Dim 8 — Performance_

### BE-PF-13: `auralis_chunks/` on-disk cache is cleared only at startup — no eviction during long sessions
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/config/startup.py:65-73`; `core/chunked_processor.py:122-123`; `core/encoding/wav_encoder.py:209` (`cleanup_track_chunks` exists but no caller)
- **Status**: NEW
- **Description**: `ChunkedAudioProcessor.__init__` creates `/tmp/auralis_chunks/` and stores up to ~3 MB per chunk × (chunks per track) × (presets × intensities played) WAVs on disk. The startup lifespan (`config/startup.py:65-73`) wipes the directory on backend start, but during a long-running session nothing evicts these files. `WAVEncoder.cleanup_track_chunks` (line 209 of wav_encoder.py) exists but `grep cleanup_track_chunks` returns no in-tree caller.
- **Evidence**:
  ```python
  # core/chunked_processor.py:122-123
  self.chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
  self.chunk_dir.mkdir(exist_ok=True)
  ```
  ```python
  # config/startup.py:65-73 — only run at startup, not periodically
  chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
  if chunk_dir.exists():
      try:
          shutil.rmtree(chunk_dir)
          chunk_dir.mkdir(exist_ok=True)
          logger.info(f"🧹 Cleared chunk directory: {chunk_dir}")
      except Exception as e:
          logger.warning(f"Failed to clear chunk directory: {e}")
  ```
  ```bash
  $ grep -r cleanup_track_chunks auralis-web/ tests/
  # only the definition; zero callers
  ```
- **Impact**: A user that plays continuously for hours accumulates 100s of MB of WAV chunks on `/tmp` until the process restarts. On a tmpfs `/tmp` (typical Linux), this consumes real RAM. Desktop-only context means this is bounded by user behaviour, not adversarial input, but a long listening session + multiple preset comparisons can balloon the directory.
- **Siblings**: None.
- **Suggested Fix**: Wire `WAVEncoder.cleanup_track_chunks(track_id=...)` into `AudioStreamController.stream_enhanced_audio`'s `finally:` for the cleanup-on-track-end case. Add a periodic disk-eviction task (e.g., LRU by mtime, cap 1 GB) in lifespan; reuse the `LibraryAutoScanner`'s asyncio-loop pattern.

---

> _Dim 8 — Performance_

### BE-PF-14: `audio_processing_pipeline.process_audio_async`'s `processor_lock` parameter is always `None` in production callers — no benefit from the async wrapper
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/audio_processing_pipeline.py:318-363`
- **Status**: NEW (residual concern after BE-NEW-71 fix)
- **Description**: After BE-NEW-71 was fixed (the `async def` is now genuinely async via `await asyncio.to_thread(_run)`), the method still accepts a `processor_lock: asyncio.Lock | None = None` parameter that no production caller passes. The path that uses the lock (line 360-362) is dead in production; the only callers (`ChunkedAudioProcessor._process_chunk_core` and tests) pass nothing.
- **Evidence**:
  ```python
  # core/audio_processing_pipeline.py:359-363
  if processor_lock is not None:
      async with processor_lock:
          return await _asyncio.to_thread(_run)
  return await _asyncio.to_thread(_run)
  ```
  ```bash
  $ grep -rn "process_audio_async" auralis-web/ tests/ | head -5
  core/audio_processing_pipeline.py:319:    async def process_audio_async(
  # → no other callers
  ```
- **Impact**: Dead code path adds branch noise. Also, the actual production caller (`ChunkedAudioProcessor._process_chunk_core` → `AudioProcessingPipeline.process_audio` at line 492) is synchronous, called from `_process_chunk_locked` under a `threading.Lock`. The async wrapper is unused.
- **Siblings**: None.
- **Suggested Fix**: Either delete `process_audio_async` (and the `import asyncio` at line 349) if no consumer adopts it, or document the intended caller. Verify no out-of-tree script depends on it before deletion.

---

> _Dim 9 — Test Coverage_

### BE-TC-7: No real-decode integration test for FFmpeg-routed formats (MP3, AAC, OGG, OPUS, M4A) through the backend ingestion path
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/files.py:88-244` (upload + format detection); `auralis-web/backend/routers/processing_api.py:203-285` (upload-and-process); `auralis/io/unified_loader.py`
- **Status**: Existing: #3696
- **Description**: Already filed as an open issue. Backend upload/format-detection branches are exercised only with WAV or magic-byte stubs; no real MP3/AAC/OGG/OPUS/M4A bytes flow through the FFmpeg-routed branches of `_is_valid_audio_magic` (`processing_api.py:37-50`) or the format-detection path in `files.py`.
- **Evidence**: See #3696.
- **Impact**: Format-specific FFmpeg failures (codec missing, container malformed, sample-rate mismatch) wouldn't be caught.
- **Suggested Fix**: See #3696. SKIP — already tracked.

---

> _Dim 9 — Test Coverage_

### BE-TC-8: Schema `LibraryScanRequest.validate_directory_paths` path-traversal-rejection logic has no direct unit test
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/schemas.py:260-287` (validator); `tests/backend/test_schemas_and_middleware.py` (covers other schemas but not this one); `tests/security/test_scan_path_validation.py` (covers `security/path_security.py` directly, not via the schema)
- **Status**: NEW
- **Description**: `LibraryScanRequest` is a Pydantic model whose `validate_directory_paths` field validator wraps `validate_user_chosen_directory(path)` from `security/path_security`. There is no direct test that constructs `LibraryScanRequest(directories=["../../etc"])` and asserts a `ValidationError` is raised. `tests/security/test_scan_path_validation.py` tests the underlying security function but does not exercise the Pydantic-validator wrapper, which means a regression that loses the `field_validator` decorator (or accidentally returns the unvalidated input) would not be caught at the API layer.
- **Evidence**: `grep -l "LibraryScanRequest"` returns 3 files, none of which construct the model with invalid input and assert validation behaviour.
- **Impact**: A future refactor that drops the `@field_validator` decorator, or returns the wrong list (e.g., `v` instead of `validated`), would silently disable schema-level path-traversal blocking. Defense-in-depth degradation.
- **Siblings**: `WebSocketMessageBase` (line 239) and `WebSocketErrorResponse` (line 290) similarly have no direct construction tests in `test_schemas_and_middleware.py`.
- **Suggested Fix**: Add 3-4 tests in `test_schemas_and_middleware.py::TestLibraryScanRequest`: valid path, traversal `..`, absolute-root `/`, empty list. Each test ~5 LOC.

---

> _Dim 9 — Test Coverage_

### BE-TC-9: WebSocket "pong" handler branch has no test (the client→server pong is supposed to update HeartbeatManager but no test verifies)
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/system.py:209-210` (`elif message.get("type") == "pong"`); `auralis-web/backend/websocket/websocket_protocol.py::HeartbeatManager`
- **Status**: NEW
- **Description**: The handler dispatches on `pong` (which the client sends in response to a server `ping`). The handler body just falls through with no broadcast. No test sends `{"type": "pong"}` and asserts the HeartbeatManager registers the receipt (or that the connection's `last_heartbeat` timestamp advances). HeartbeatManager itself is tested in `test_websocket_protocol_b3.py` (`test_heartbeat_mark_pong_success`) but only via the manager API directly — not through the WS handler dispatch.
- **Evidence**: `grep -n "pong"` in `system.py` finds the dispatch line; `grep -nE "\"type\":\s*\"pong\"" tests/` finds zero round-trip tests.
- **Impact**: If the `pong` dispatch is removed (e.g., during a future refactor that thinks "pong is a no-op"), no test fails — but liveness tracking silently degrades.
- **Siblings**: `heartbeat` message type (line 212) — also untested via real WS (see BE-TC-4).
- **Suggested Fix**: Add one test in `test_system_api.py::TestWebSocketEndpoint`: send `{"type": "pong"}`, then send `{"type": "ping"}`, assert server replies with pong (i.e., connection is alive). ~10 LOC.

---

> _Dim 9 — Test Coverage_

### BE-TC-10: No concurrency test for parallel similarity calls — `/api/similarity/tracks/{id}/similar` and `/fit` under simultaneous client load
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/similarity.py:96, 201, 260, 297, 353` (similarity endpoints); `tests/backend/test_similarity_api*.py` (single-call only)
- **Status**: NEW
- **Description**: The prompt asks for "concurrency: parallel similarity calls". `test_similarity_api.py` / `test_similarity_api_new.py` test each endpoint sequentially with mocks. No test fires N concurrent `/api/similarity/tracks/X/similar` requests against the same graph state, or interleaves `/fit` (which holds a write-lock on the model) with `/tracks/X/similar` (read). `tests/concurrency/test_thread_safety.py` does not include similarity endpoints. The #2752 fix moved `similarity.fit` to `asyncio.to_thread` to avoid blocking the event loop — but no test verifies that a `/tracks/X/similar` request placed during an in-flight `/fit` actually completes (rather than blocking on the same thread-pool slot).
- **Evidence**: `grep -nE "parallel|concurrent" tests/backend/test_similarity*.py` returns no matches. `grep -rE "concurrent.*similar|similar.*concurrent" tests/concurrency/` returns nothing.
- **Impact**: A regression that re-introduces sync blocking (or a thread-pool starvation under high `/fit` load) would not be caught. Closure of #2752 was load-bearing but tested only via single-call mocks.
- **Siblings**: None — similarity is the only major endpoint with this concurrency pattern.
- **Suggested Fix**: Add `tests/concurrency/test_similarity_endpoint_concurrency.py` with one async test that uses `asyncio.gather` to fire 10 concurrent `/tracks/X/similar` requests against a mocked similarity system (with artificial latency), asserting all return within reasonable time and none deadlock.

---

> _Dim 9 — Test Coverage_

### BE-TC-11: `LibraryAutoScanner` (426 LOC) has no dedicated tests — only sibling regressions (`test_personal_preferences_atomic.py`, `test_no_duplicate_scan_route.py`) touch adjacent code
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:1-426`; instantiated at `auralis-web/backend/config/startup.py`
- **Status**: NEW (in scope of BE-NEW-60's untested-services concern, but not addressed by #3518's closure)
- **Description**: 426 LOC service handling watchdog + polling fallback for new audio files. Holds long-running asyncio task. `grep -rE "LibraryAutoScanner" tests/` returns no matches. Auto-scan triggers `library_manager.scan_folder` which is the same code path as user-initiated scans (covered) — but the watchdog/polling lifecycle (start, stop, reload_config, polling-interval handling, error recovery) is uncovered.
- **Evidence**: `grep -rlE "LibraryAutoScanner|library_auto_scanner" /mnt/data/src/matchering/tests/` → no output.
- **Impact**: Watchdog/polling lifecycle bugs, reload_config races (called from settings router on every scan-folder change), and asyncio-task cancellation behaviour would not be caught.
- **Siblings**: `SelfTuner` (347 LOC) appears unused in production wiring; `RecommendationService` / `NavigationService` (covered in BE-TC-5).
- **Suggested Fix**: Add `tests/backend/test_library_auto_scanner.py` with ~5 tests: `start()` creates task, `stop()` cancels task, `reload_config()` is idempotent and threadsafe, watchdog event triggers scan, polling fallback runs at expected interval.

---


## Prioritized Fix Order

### Tier 0 — Ship before the next release

- **BE-CP-1** — `auralis-web/backend/core/chunk_operations.py` (NEW (regression of #2750 / commit `c71c8842` that was thought to fix the same symptom — the c71c8842 fix shortened the duplicate from 5 s to a still-5 s window because the slice offset was never corrected))

This is confirmed by direct numpy simulation; every user listening to enhanced-mode content past the first 30 s hears a 5-second backward jump at every chunk boundary.

### Tier 1 — HIGH-severity, NEW or regression

- **BE-RH-1** (Route Handlers) — `auralis-web/backend/routers/webm_streaming.py` _(NEW)_
- **BE-RH-2** (Route Handlers) — `auralis-web/frontend/src/hooks/player/useQueueHistory.ts` _(NEW)_
- **BE-WS-1** (WebSocket Streaming) — `auralis-web/backend/routers/system.py` _(NEW)_
- **BE-CP-2** (Chunked Processing) — `auralis-web/backend/core/chunk_boundaries.py` _(NEW)_
- **BE-PE-1** (Processing Engine) — `auralis-web/backend/core/chunked_processor.py` _(NEW)_
- **BE-SCH-1** (Schema Consistency) — `` _(NEW)_
- **BE-MW-1** (Middleware & Config) — `auralis-web/backend/websocket/websocket_security.py` _(Regression of #3181)_
- **BE-MW-2** (Middleware & Config) — `auralis-web/backend/websocket/websocket_security.py` _(NEW)_
- **BE-MW-3** (Middleware & Config) — `auralis-web/backend/config/startup.py` _(Regression of #3540)_
- **BE-EH-1** (Error Handling) — `auralis-web/backend/routers/system.py` _(NEW)_
- **BE-EH-2** (Error Handling) — `auralis-web/backend/routers/files.py` _(NEW)_
- **BE-PF-1** (Performance) — `auralis-web/backend/routers/player.py` _(NEW)_
- **BE-PF-2** (Performance) — `auralis-web/backend/analysis/fingerprint_queue.py` _(NEW)_
- **BE-PF-3** (Performance) — `auralis-web/backend/core/streamlined_worker.py` _(NEW)_
- **BE-TC-1** (Test Coverage) — `tests/backend/test_processing_engine.py` _(NEW)_
- **BE-TC-2** (Test Coverage) — `auralis-web/backend/routers/processing_api.py` _(NEW)_

### Tier 2 — MEDIUM-severity, batch by file/root-cause

Group the MEDIUM findings into per-PR batches by file or root-cause:
- `routers/system.py` overlaps (D1, D2, D6, D7) — single PR for WS handler hygiene + str(e) leak fixes.
- `core/audio_stream_controller.py` overlaps (D2, D3, D5, D7) — single PR for streaming controller cleanup.
- Schema/contract drift (D5: BE-SCH-1..12) — single PR aligning backend response shapes with frontend TS types.
- `str(e)` leak siblings (D6: BE-MW-6, D7: BE-EH-1..4) — single PR; small, mechanical.

### Tier 3 — LOW-severity / tech-debt

The 72 LOW findings are predominantly documentation, dead-code removal, log-level tweaks, missing type hints, and undocumented behaviors. Batch into a single cleanup PR per file or per area; none are release-blocking.

---

## Next steps

1. Run **`/audit-publish docs/audits/AUDIT_BACKEND_2026-05-28.md`** to publish the new findings as GitHub issues (already-OPEN existing-N items are skipped automatically).
2. **BE-CP-1** should be filed as a CRITICAL issue and fixed before the next release.
3. The 28 regressions of previously-closed issues (#2750, #3181, #3540, #3530, #3543, #3558, #3560, #3561, etc.) indicate prior fixes were incomplete; the surfaces named in those regressions deserve re-verification, not just the new fix.
