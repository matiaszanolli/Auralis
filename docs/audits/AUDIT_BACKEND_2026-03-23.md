# Backend Audit — 2026-03-23

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: FastAPI backend — `auralis-web/backend/`
**Dimensions**: Route Handlers, WebSocket Streaming, Chunked Processing, Processing Engine, Schema Consistency, Middleware & Config, Error Handling, Performance, Test Coverage
**Method**: 3 parallel dimension agents (Sonnet), merged with dedup against 52 open issues and 20 recent fix commits.
**Context**: Post-fix audit — 20 backend commits since 2026-03-22 resolved ~30 previously reported issues.

## Executive Summary

This audit found **22 genuinely new findings** after aggressive deduplication. No CRITICAL or HIGH findings — the refactor addressed the most serious issues. The remaining findings are primarily correctness gaps in edge cases and performance issues in streaming paths.

**Key themes:**

1. **WS progress callback crash** (BE-DIM1-01) — A WebSocket disconnect during processing causes the progress callback to throw, marking a healthy job as FAILED.

2. **Event loop blocking in streaming** (BE-22) — `factory.tracks.get_by_id()` called directly on the event loop at 4 sites in AudioStreamController.

3. **Schema/protocol gaps** (DIM4-1, DIM4-3) — `subscribe_job_progress` reads wrong dict level (always None), and `WebSocketMessageType` enum is missing 3 outbound message types.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 3 |
| LOW | 19 |
| **Total** | **22** |

---

## MEDIUM

---

### BE-DIM1-01: subscribe_job_progress callback crash on WS disconnect aborts running job
- **Severity**: MEDIUM
- **Dimension**: Route Handlers / WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:741-751`
- **Status**: NEW
- **Description**: Progress callback captures live `websocket` reference with no try/except. On disconnect, `websocket.send_text` raises RuntimeError which propagates to `process_job()` and marks the healthy job as FAILED. User refreshing mid-job silently aborts processing.
- **Impact**: Any browser refresh during audio processing kills the job.
- **Suggested Fix**: Wrap callback in try/except; remove callback on disconnect; check connection state before send.

---

### DIM4-1: subscribe_job_progress reads job_id from wrong dict level — always None
- **Severity**: MEDIUM
- **Dimension**: Processing Engine / Schema Consistency
- **Location**: `auralis-web/backend/routers/system.py:738`
- **Status**: NEW
- **Description**: Uses `message.get("job_id")` instead of `message.get("data", {}).get("job_id")`. Under the WS protocol envelope, top-level `job_id` is always None. Progress callbacks never registered; all WS job-progress notifications silently dropped.
- **Impact**: Processing progress never reaches the frontend via WebSocket.
- **Suggested Fix**: Change to `data = message.get("data", {}); job_id = data.get("job_id")`.

---

### BE-22: factory.tracks.get_by_id() blocks event loop at 4 sites in AudioStreamController
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/audio_stream_controller.py` (stream_enhanced_audio, stream_normal_audio, stream_enhanced_audio_from_position, _prefetch_next_track)
- **Status**: NEW
- **Description**: Synchronous SQLAlchemy call on the async event loop. Under concurrent streams, blocks all other async handlers.
- **Impact**: Latency spikes and potential starvation during concurrent playback.
- **Suggested Fix**: Wrap in `await asyncio.to_thread(factory.tracks.get_by_id, track_id)`.

---

## LOW

---

### Route Handlers (5)
- **BE-DIM1-02**: Seek and play positions accept NaN/Infinity — reaches `int(nan / chunk_interval)` raising ValueError. Location: `system.py:297,448,613`
- **BE-DIM1-03**: `stop` cancels streaming task without awaiting — audio frames may continue briefly. Location: `system.py:583-586`
- **BE-DIM1-04**: `heartbeat_task.cancel()` not awaited in disconnect finally — leaked task reference. Location: `system.py:768`
- **BE-DIM1-05**: `/api/stream/{track_id}/chunk/{chunk_idx}` accepts negative indices — NumPy wrap-around. Location: `routers/webm_streaming.py:217`
- **BE-DIM1-06**: Seek-path chunk errors omit `recovery_position` — client can't resume after mid-seek failure. Location: `audio_stream_controller.py:1705-1717`

### Processing Engine / Schema (4)
- **DIM4-2**: `ProcessingJob.to_dict()` leaks server-side file paths in `GET /api/processing/jobs`. Location: `processing_engine.py:97-111`
- **DIM4-3**: `WebSocketMessageType` enum missing 3 outbound types: `enhancement_settings_changed`, `player_state`, `playback_resumed`. Location: `schemas.py`
- **DIM4-6**: `start_worker` task not retained as strong reference — brief cancel window. Location: `config/startup.py:277`
- **DIM4-7**: `DELETE /api/processing/jobs/cleanup?max_age_hours=0` silently purges all jobs including just-completed. Location: `routers/processing_api.py:481`

### Middleware / Config (2)
- **DIM4-4**: `cleanup_old_jobs` makes blocking `Path.exists()` while holding `_jobs_lock`. Location: `processing_engine.py:716,719`
- **DIM4-5**: `RateLimitMiddleware` eviction race under concurrent requests — minor accounting error. Location: `config/middleware.py`

### Error Handling (3)
- **BE-25**: `get_job()` and `register_progress_callback()` skip `_jobs_lock`. Location: `processing_engine.py`
- **BE-27**: Six `except Exception` handlers in `similarity.py` expose `str(e)` in HTTP 500 detail. Location: `routers/similarity.py`
- **BE-30**: `GET /api/processing/jobs` reflects caller-supplied `status` in error detail unsanitized. Location: `routers/processing_api.py`

### Performance (2)
- **BE-23**: `GET /api/albums/{id}/fingerprint` N+1 sequential DB query per track. Location: `routers/albums.py`
- **BE-24**: `POST /api/similarity/fingerprint-queue/enqueue-all` sync `queue.enqueue()` loop on event loop. Location: `routers/similarity.py`

### Test Coverage (3)
- **BE-28**: WebSocket `buffer_full`/`buffer_ready` flow-control messages have zero test coverage. Location: N/A
- **BE-29**: 6 endpoints in `processing_api.py` missing `response_model` declarations. Location: `routers/processing_api.py`
- **BE-26**: Negative `chunk_idx` not tested (duplicate with DIM1-05 above — counted once).

---

## Relationships & Shared Root Causes

1. **Progress callback chain**: BE-DIM1-01 (callback crash) and DIM4-1 (wrong dict level) both affect job progress. Even if DIM4-1 is fixed, BE-DIM1-01 means disconnect kills jobs.

2. **Event loop blocking**: BE-22 (AudioStreamController), DIM4-4 (cleanup_old_jobs), BE-24 (enqueue-all) — all sync calls on async event loop. A project-wide lint rule for `asyncio.to_thread` would prevent recurrence.

3. **Schema gaps**: DIM4-3 (missing enum values) and BE-29 (missing response_model) — backend schema layer doesn't fully document the actual API contract.

## Prioritized Fix Order

1. **BE-DIM1-01** — Progress callback crash. User refresh kills processing. Wrap in try/except.
2. **DIM4-1** — Job progress always None. Fix dict level. One-line fix.
3. **BE-22** — Event loop blocking. Wrap 4 sites in asyncio.to_thread.
4. **DIM4-2** — Path leakage in job list. Filter output_path/input_path.
5. **BE-27** — Exception string exposure in similarity router.

---

*Report generated by Claude Opus 4.6 — 2026-03-23*
*Suggest next: `/audit-publish docs/audits/AUDIT_BACKEND_2026-03-23.md`*
