# Backend Audit — 2026-07-25

**Scope**: `auralis-web/backend/` — 20 registered routers (94 HTTP endpoints + 1 WebSocket), WebSocket streaming stack, chunked processor, processing engine, schemas, middleware, services. ~27,200 lines across 108 Python modules.
**Method**: 9 dimension agents, fresh read of current `master` (168 commits since the 2026-07-12 audit, including the `#4270` split of `similarity.py` into `similarity` / `similarity_graph` / `fingerprint_queue`). No prior audit report was used as a finding source.
**Dedup baseline**: 2,000 GitHub issues (159 open) fetched at audit start; `docs/audits/` and `.claude/issues/` scanned. Findings matching an OPEN issue were omitted; CLOSED issues were re-verified for regressions.
**Out of scope**: React frontend internals, `auralis/` engine internals, Rust DSP — except where the backend's contract with them is the defect.

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 11 |
| MEDIUM | 21 |
| LOW | 21 |
| **Total** | **53** |

No CRITICAL findings. The backend's async hygiene is genuinely strong — 184 `asyncio.to_thread` / `run_in_executor` call sites, zero `subprocess`, zero `time.sleep`, zero synchronous HTTP clients, every route handler `async def`, bounded send queues and a working heartbeat on the WebSocket path, and a middleware stack whose LIFO ordering, CORS allowlist and rate-limit critical section all check out. The 53 findings cluster into five themes:

**1. Seek is broken on both streaming paths (BE2-01, BE2-02, BE2-03 — all HIGH).** This is the most user-visible cluster and the highest-value fix in the report. The chunk-geometry contract — chunk *N* is cored at `[N*10, N*10+15]` but `extract_chunk_segment` skips the leading `OVERLAP_DURATION`, so chunk *N ≥ 1* actually emits `[N*10+5, N*10+15)` — is not mirrored in the seek math. The enhanced path therefore lands **5 s past** the requested position and leaves the position readout permanently 5 s ahead of the audio; the normal path lands up to **15 s before** it (it advertises a `seek_offset` that no client consumes) and re-plays that audio on every WebSocket reconnect-resume. On top of both, in-flight frames from the superseded stream survive the seek because `is_seek: true` tells the client to preserve its buffer and the wire protocol has no stream-epoch to discriminate them. Dimension 3 independently reached the same conclusion about the position→chunk mapping from the chunk-geometry side, which is strong corroboration.

**2. Two shipped fixes are silently non-functional.** `BE8-01` (HIGH) is a **regression of the CLOSED #3836**: the Tier-1 database fingerprint lookup it restored resolves the repository from `config.globals.globals_dict`, but the live component registry is a *different* dict built inline in `main.py` — the one it reads has no `repository_factory` key at all, so the accessor returns `None` on every call and every `ChunkedAudioProcessor` construction still falls through to the slow tiers. `BE7-01` and `BE3-02`/`BE3-03` are the same shape one layer down: cache correctness assumptions that hold only because the code path they protect is never reached.

**3. Contract drift between backend and frontend (BE5-01 HIGH, BE1-05, BE5-02…BE5-05, BE5-09 MEDIUM).** The album-detail track table reads camelCase from a snake_case endpoint and silently renders blank artist/track-number columns; `Track.to_dict()` omits six fields the frontend `Track` type declares as required; the same Album entity ships in two casings from sibling endpoints; the WebSocket message registry has drifted in both directions; and a drag-drop hook calls two playlist routes that return 405 because they were never registered.

**4. Resource and lifecycle gaps (BE4-01, BE6-01 HIGH; BE4-02, BE6-02, BE8-03 MEDIUM).** A generic-exception path in `process_job` never returns its exclusively-owned processor to the pool; the lifespan shutdown's first three steps are unguarded so one failing worker skips the SQLite WAL checkpoint entirely; and three separate lock-across-slow-work sites (`ProcessorFactory` RLock, `ProcessorPool` asyncio.Lock, `PlaybackService._playback_lock` across an untimed WebSocket broadcast) serialize or, in the broadcast case, can hang the transport controls outright.

**5. Validation and error-shape gaps (BE1-01 HIGH; BE1-02…BE1-04, BE7-02, BE7-03 MEDIUM).** `POST /api/metadata/batch` accepts an unvalidated `dict[str, Any]` that reaches a `setattr` loop over arbitrary `Track` ORM columns including the primary key; a module-level recommendation cache is keyed by an unbounded client-supplied float with no eviction; several getters dereference `None` into a 500 where a 503 is meant; and the shared `aiohttp` session has no `ClientTimeout`.

**Most impactful single issues**: BE2-01/BE2-02 (seek is wrong in both modes, on every seek), BE8-01 (a closed performance fix that never took effect), BE1-01 (localhost-reachable library-DB corruption vector).

## Route Coverage Matrix

All 20 registered routers, derived from `auralis-web/backend/config/routes.py`. "Tested" = endpoint path pattern appears somewhere under `tests/`; it does **not** imply the behaviour is asserted (see BE9-01 — eleven backend test modules are hard-skipped at import, so some of this coverage is illusory).

| Router | Endpoints | `response_model` | Pydantic models | `Query()` bounds | error decorator | Path-tested |
|--------|-----------|------------------|-----------------|------------------|-----------------|-------------|
| albums | 4 | 0 | 0 | 2 | yes | 4/4 |
| artists | 3 | 3 | 6 | 4 | yes | 3/3 |
| artwork | 4 | 0 | 0 | 1 | yes | 4/4 |
| cache_streamlined | 5 | 2 | 2 | 0 | no | 5/5 |
| enhancement | 6 | 5 | 5 | 0 | no | 6/6 |
| files | 2 | 0 | 0 | 0 | no | 2/2 |
| fingerprint_queue | 4 | 0 | 0 | 1 | no | 4/4 |
| fingerprint_status | 2 | 0 | 0 | 0 | no | 2/2 |
| health | 2 | 2 | 0 | 0 | no | 2/2 |
| library | 3 | 0 | 0 | 0 | yes | 2/3 |
| library_scan | 1 | 1 | 0 | 0 | no | 1/1 |
| metadata | 4 | 0 | 3 | 0 | yes | 4/4 |
| player | 19 | 19 | 24 | 1 | no | 19/19 |
| playlists | 8 | 0 | 3 | 0 | yes | 8/8 |
| processing_api | 9 | 8 | 9 | 2 | no | 9/9 |
| settings | 5 | 5 | 4 | 0 | yes | 5/5 |
| similarity | 4 | 3 | 4 | 5 | no | 4/4 |
| similarity_graph | 3 | 1 | 1 | 2 | no | 3/3 |
| system | 1 (WebSocket `/ws`) | — | — | — | no | n/a |
| tracks | 6 | 0 | 0 | 4 | no | 6/6 |
| **Total** | **94 HTTP + 1 WS** | **49** | **61** | **22** | **8/20** | **93/94** |

Notes:
- `response_model=` coverage is 49/94 (52%). The general gap is already tracked by **#3838** and is deliberately not re-reported; only specific correctness consequences appear as findings (BE5-08, BE5-06).
- The `#4270` similarity split was verified route-for-route against `74f6dfc1^`: all 11 original paths present, no duplicates across the three routers sharing the `/api/similarity` prefix, no lost `Query()` bounds. The one gap is that nothing tests the *composed* app (BE9-04).
- `POST /api/library/refresh-references` is the single endpoint with no test reference anywhere (BE9-02).
- 8 of 20 routers use the shared `with_error_handling` decorator; the rest hand-roll (BE7-04 covers the two that emit a non-standard error shape).

## Findings

## CRITICAL (0)

_None._


## HIGH (11)

### BE1-01: `POST /api/metadata/batch` mass-assigns arbitrary ORM columns (unvalidated `dict[str, Any]`)
- **Severity**: HIGH
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/metadata.py:56-64, 275-344` → `auralis/library/repositories/track_repository.py:785-828`
- **Status**: NEW
- **Description**: The single-track route `PUT /api/metadata/tracks/{track_id}` validates its body with `MetadataUpdateRequest` (`extra="forbid"`, explicit tag fields). The batch route does not: `BatchMetadataUpdateRequest.metadata` is a free-form `dict[str, Any]`. That dict is passed verbatim into `MetadataUpdate(updates=...)`, echoed back unchanged by `MetadataEditor.batch_update` (`'updates': update.updates`, `metadata_editor.py:302`), and then handed to `repos.tracks.update_metadata_batch`, which does `setattr(track, key, value)` for **any** attribute that exists on the `Track` ORM object — including `id`, `filepath`, `album_id`, `duration`, `play_count`, `favorite`.
- **Evidence**:
```python
# routers/metadata.py
class BatchMetadataUpdateRequest(BaseModel):
    track_id: int
    metadata: dict[str, Any] = Field(..., description="Metadata fields to update")   # no whitelist
...
    successful_track_ids = await asyncio.to_thread(repos.tracks.update_metadata_batch, db_updates)

# auralis/library/repositories/track_repository.py:815
                for key, value in fields.items():
                    if hasattr(track, key) and value is not None:
                        setattr(track, key, value)      # any Track column, incl. primary key
```
- **Impact**: A single POST to a localhost route can rewrite a track's primary key (breaking FK references from queue/fingerprint/playlist rows), repoint `filepath`, or falsify library statistics — i.e. DB-level corruption of the library with no error surfaced to the user. Escalation to arbitrary file read is blocked: `core/stream_enhanced.py:103`, `core/stream_normal.py:107` and `core/stream_seek.py:105` re-run `validate_file_path(track.filepath)` before decoding (#4345), which is why this is rated HIGH rather than CRITICAL.
- **Siblings**: None — this is the only router accepting an unconstrained `dict[str, Any]` that reaches a `setattr` loop. `routers/settings.py` (`extra="forbid"`) and `routers/metadata.py` PUT are the correctly-validated counterparts.
- **Suggested Fix**: Reuse `MetadataUpdateRequest` for `BatchMetadataUpdateRequest.metadata` (or validate against an explicit tag-field allowlist before building `MetadataUpdate`), and add a column allowlist inside `update_metadata_batch` / `update_metadata` so `id` and `filepath` can never be set via a metadata path.

### BE2-01: Enhanced-path seek lands 5 s past the requested position (OVERLAP_DURATION ignored in the seek math)
- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_seek.py:143-231`
- **Status**: NEW
- **Description**:
  `stream_enhanced_audio_from_position` picks the start chunk and the intra-chunk trim as if chunk
  `N`'s emitted audio began at source time `N * CHUNK_INTERVAL`. It does not. Under the canonical
  chunk model (`core/chunk_boundaries.py`), chunk `N`'s *core* is `[N*10, N*10+15]`, and
  `ChunkOperations.extract_chunk_segment` (`core/chunk_operations.py:226-234`) then **skips
  `OVERLAP_DURATION` (5 s)** because the previous chunk already emitted it. So the samples the
  streaming layer actually receives for chunk `N ≥ 1` cover source time
  `[N*10 + 5, N*10 + 15)` — chunk 1 = `[15,25)`, chunk 2 = `[25,35)`, …
  The seek code computes `chunk_start_time = start_chunk_idx * chunk_interval` and trims
  `seek_offset = start_position - chunk_start_time` seconds off the *front of the already
  overlap-skipped buffer*, so the first sample actually delivered is at
  `N*10 + 5 + (P - N*10) = P + 5`. Every enhanced seek to a position ≥ 10 s overshoots by exactly
  `OVERLAP_DURATION`, and the 5 s of audio between the requested point and the delivered point is
  never sent. Meanwhile `audio_stream_start.seek_position = P` makes the client set its position
  counter to `P` (`useEnhancedStreamStart.ts:137-139`), so the displayed time stays 5 s behind the
  audio for the rest of the track.
  Correct derivation for the containing chunk is `N = floor((P - OVERLAP_DURATION) / CHUNK_INTERVAL)`
  (clamped at 0) with `offset = P - (N*CHUNK_INTERVAL + OVERLAP_DURATION)` for `N ≥ 1`, and
  `offset = P` for `N = 0`.
- **Evidence**:
```python
# core/stream_seek.py:145-151
chunk_interval = processor.chunk_interval            # 10.0
start_chunk_idx = int(start_position / chunk_interval)
chunk_start_time = start_chunk_idx * chunk_interval  # ← assumes chunk N starts at N*10
seek_offset = start_position - chunk_start_time
...
# core/stream_seek.py:225-227
if chunk_idx == start_chunk_idx and seek_offset > 0:
    trim_samples = round(seek_offset * processor.sample_rate)
    pcm_samples = pcm_samples[trim_samples:]          # ← buffer already starts at N*10+5
```
```python
# core/chunk_operations.py:227-230 (regular chunk)
# "skip overlap already emitted by the previous chunk"
extracted = processed_chunk[overlap_samples:overlap_samples + expected_samples]
```
- **Impact**: Every enhanced-mode seek beyond the first 10 s silently drops 5 s of audio and starts
  playback 5 s late; the transport bar/position readout is permanently 5 s ahead of what is audible
  for the remainder of the stream. Worst case (offset ≈ 9.9 s) the first delivered chunk is trimmed
  down to ~0.1 s, producing an immediate buffer-underrun stutter on top of the skip.
- **Siblings**: Only site — `stream_enhanced.py` and `stream_normal.py` do not trim. The
  complementary error on the normal path is BE2-02 (same root contract, opposite direction).
- **Suggested Fix**: Derive the containing chunk and the trim from the *emitted* timeline, not the
  core timeline: `start_chunk_idx = max(0, ceil((P - CHUNK_DURATION) / CHUNK_INTERVAL))` (or the
  equivalent `floor((P - OVERLAP)/INTERVAL)` form), and compute `seek_offset` relative to
  `chunk_start_time + (OVERLAP_DURATION if start_chunk_idx > 0 else 0)`. Import the constants from
  `core/chunk_boundaries.py` and add a unit test asserting the delivered first-sample time equals the
  requested position for `P ∈ {0, 5, 12, 27, 33}`.

### BE2-02: Normal-path seek/resume replays up to 15 s of already-heard audio — `seek_offset` is emitted but has no consumer
- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_normal.py:166-207, 235-284`
- **Status**: NEW
- **Description**:
  The normal (unprocessed) path locates the containing chunk correctly
  (`start_chunk = start_sample // interval_samples`, 15 s chunks, no overlap) but then streams that
  chunk **from its start** (`start_sample = chunk_idx * interval_samples`) — it never trims to the
  requested position. It compensates on paper by publishing
  `seek_offset = start_position - start_chunk*chunk_duration` in `audio_stream_start`, delegating the
  trim to the client. No client consumes it: a repo-wide grep of
  `auralis-web/frontend/src` finds `seek_offset` only in the type declaration
  (`types/ws/streaming.ts:44`); `usePlayNormal.handleStreamStart` reads only `is_seek`, and the
  position tracker is seeded from `seek_position`, not `seek_offset`. The result is that audio
  restarts at the chunk boundary — up to `CHUNK_DURATION` (15 s) *before* the requested position —
  while the UI position jumps to the requested position.
  This is also the WS-reconnect resume path (`replayQueueAndResume` re-issues `play_normal` with the
  current position, #3185/#3755), so every reconnect during normal playback re-sends and re-plays up
  to 15 s of audio the user already heard.
- **Evidence**:
```python
# core/stream_normal.py:186-192 — offset is advertised…
seek_kwargs = {
    "start_chunk": start_chunk,
    "seek_position": start_position,
    "seek_offset": start_position - (start_chunk * chunk_duration),
}
# core/stream_normal.py:263-266 — …but the read starts at the chunk boundary, untrimmed
start_sample = chunk_idx * interval_samples
chunk_audio = await asyncio.to_thread(
    _read_audio_chunk, streaming_filepath, start_sample, chunk_samples
)
```
- **Impact**: Duplicated audio on every normal-mode seek and on every WS reconnect-resume (up to 15 s
  re-played), plus a position readout that disagrees with the audio. Combined with BE2-01, neither
  streaming path honours the requested seek position.
- **Siblings**: BE2-01 (enhanced path, opposite-direction error from the same chunk-geometry
  contract). No other `seek_offset` producer/consumer exists in the backend.
- **Suggested Fix**: Trim server-side like the enhanced path does — drop
  `round(seek_offset * sample_rate)` frames from the first emitted chunk (or simply seek the
  `SoundFile` to `int(start_position * sample_rate)` for the first chunk) — and keep emitting
  `seek_offset` as metadata only. Either way, make one side authoritative and add a test that asserts
  the first delivered sample corresponds to `start_position`.

### BE2-03: In-flight frames from a superseded stream are appended to the client buffer after a seek (no discard boundary in the protocol)
- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:232-257`, `auralis-web/backend/core/stream_protocol.py:174-257`, `auralis-web/backend/core/stream_messages.py:60-95`
- **Status**: NEW (adjacent to open #3774, which notes only that `seq` is unvalidated client-side)
- **Description**:
  On `seek`, the client synchronously stops the engine and calls `pcmBufferRef.current?.reset()`
  *before* sending the message (`useEnhancedSeek.ts:66-88`). The backend only cancels the prior
  streaming task when the receive loop gets around to the `seek` frame. Everything the old task has
  already pushed — up to `_SEND_QUEUE_MAXSIZE` (4) encoded frames plus whatever is sitting in the
  socket/TCP buffers, i.e. roughly 0.9–3.5 s of pre-seek audio — arrives *after* the reset and is
  appended to the now-empty buffer by `handleChunk`. The subsequent `audio_stream_start` carries
  `is_seek: true`, which by design tells the client to **preserve** its buffer
  (`useEnhancedStreamStart.ts:81-95`), so the stale audio is never discarded; it plays out ahead of
  the seek target.
  The wire protocol offers nothing to discriminate these frames: `audio_chunk_meta.track_id` is the
  same track, `chunk_index` is ≥ the last seen (so the `detectOutOfSequence` guard, which only fires
  on `incoming < last - 1`, does not trip), and `seq` — the one field that could carry a stream epoch
  — is reset to `[0]` at each `audio_stream_start` and is not validated by the client.
- **Evidence**:
```python
# ws_handlers/playback_commands.py:238-257 — old task cancelled only when the seek frame is dispatched
if old_task and not old_task.done():
    old_task.cancel()
    try:
        await old_task
    except (asyncio.CancelledError, Exception):
        pass
await websocket.send_text(json.dumps({"type": "seek_started", ...}))
```
```ts
// useEnhancedStreamStart.ts:81-95 — is_seek keeps the (already-polluted) buffer
if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) {
  core.pendingChunksRef.current = [];   // pending queue cleared, live buffer is not
  ...
  return;
}
```
- **Impact**: A fraction of a second to a few seconds of pre-seek audio is played back at the head of
  every seek, before the requested position — audible as a stutter/rewind. Same mechanism applies to
  any resume that sets `is_seek` (WS reconnect).
- **Siblings**: `handle_stop` and `_cancel_prior_task` have the same "cancel is asynchronous w.r.t.
  frames already emitted" shape, but their follow-up `audio_stream_start` has `is_seek` unset, so the
  client rebuilds the buffer and the stale frames are discarded — only the `is_seek` paths are
  exposed.
- **Suggested Fix**: Give each stream a monotonically increasing epoch id, stamp it on
  `audio_stream_start` and on every `audio_chunk_meta` (the `seq`/`track_id` stamping in
  `stream_messages.send_stream_start` / `stream_protocol.send_pcm_chunk` is the natural place), and
  have the client drop any chunk whose epoch is not the current one. A cheaper interim fix: emit an
  explicit `audio_stream_discard` control frame from `handle_seek` immediately after cancelling the
  old task, and have the seek resume-guard reset the PCM buffer on it.

### BE2-04: Synchronous SQLAlchemy query executed on the event loop inside the streaming path
- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_fingerprint.py:146-161`
- **Status**: NEW
- **Description**:
  `check_or_queue_fingerprint` is `async def` and is awaited from `stream_enhanced_audio`
  (`stream_enhanced.py:144-148`) before the first chunk, but it calls
  `fingerprint_repo.exists(track_id)` directly — a fully synchronous
  `session_scope() + session.execute(select(count()))` round-trip against SQLite
  (`auralis/library/repositories/fingerprint_repository.py:437-453`). It is not wrapped in
  `asyncio.to_thread`, unlike every other repository call on the same code paths
  (`stream_enhanced.py:93`, `stream_normal.py:97`, `stream_seek.py:95` all use `to_thread`). This
  blocks the whole event loop — every other WebSocket connection, all in-flight chunk sends, the
  heartbeat, and the receive loop — for the duration of the query, which is unbounded when the
  library DB is locked by a concurrent scan/fingerprint write (`pool_pre_ping`, migration lock, or a
  long write transaction).
- **Evidence**:
```python
# core/stream_fingerprint.py:148-151
factory = controller._get_repository_factory()
fingerprint_repo = factory.fingerprints
if fingerprint_repo.exists(track_id):     # ← sync DB round-trip, no to_thread
```
- **Impact**: Head-of-line blocking of the entire backend event loop at the start of every enhanced
  stream. Under DB contention this stalls audio delivery for all connections simultaneously and can
  trip the frontend's stream-start watchdog.
- **Siblings**: `core/stream_prefetch.py:54` — `queue_state = factory.queue.get_queue_state()` has
  the identical shape (sync repo call in an `async def`); it is currently unreachable in production
  (prefetch disabled per #3513, tracked dead by #3884) but is still exercised by tests and must be
  fixed together. Every other repo call in `core/stream_*.py` is correctly `to_thread`-wrapped.
- **Suggested Fix**: `if await asyncio.to_thread(fingerprint_repo.exists, track_id):` and the same
  wrapping for `factory.queue.get_queue_state` in `stream_prefetch.py`.

### BE4-01: `process_job` generic-exception path never returns (or closes) the exclusively-owned processor
- **Severity**: HIGH
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:503-563` (specifically the `except Exception` branch, 546-559)
- **Status**: NEW
- **Description**: `ProcessorPool.get_or_create()` **pops** the instance out of the cache so that no concurrent job shares it
  (documented at `core/processor_pool.py:80-97`: "The instance is POPPED from the cache ... The caller must return it via
  `return_to_cache()` after use"). `process_job` honours that contract on three of its four exit paths — success (line 519),
  `TimeoutError` (529-530) and `asyncio.CancelledError` (542-543) all call `await self._return_processor(...)`. The catch-all
  `except Exception` branch does **not**. The popped `HybridProcessor` reference is simply dropped, and `.close()` is never
  called on it either.
- **Evidence**:
  ```python
  except Exception as e:
      job.status = ProcessingStatus.FAILED
      logger.error("Processing job %s failed: %s", job.job_id, e, exc_info=True)
      job.error_message = _safe_error_message(e)
      job.completed_at = datetime.now()
      await self._notify_progress(job.job_id, 100.0, f"Processing failed: {job.error_message}")
  finally:
      self._cancel_events.pop(job.job_id, None)
  ```
  (no `_return_processor`, no `processor.close()` — contrast lines 529-530 and 542-543, which both guard with
  `if processor is not None and config is not None`.)
  `HybridProcessor.close()` (`auralis/core/hybrid_processor.py:167-180`) exists precisely because
  `fingerprint_analyzer` "owns a 5-thread executor that is never reclaimed otherwise, leaking up to 50 idle threads across a
  10-entry cache" (that was #3746). `ProcessorFactory` calls `.close()` on every eviction/cleanup path
  (`core/processor_factory.py:261, 350, 418`); this path calls it nowhere.
- **Impact**: Every job that fails after processor acquisition — i.e. every corrupt/unsupported input file, every
  `save()` failure, every `ValueError` out of the DSP chain, every `TypeError` from the `isinstance(result, np.ndarray)`
  guard — permanently drops a warm processor **and leaks its 5-thread fingerprint executor**. The threads are not reclaimed
  by GC (an executor with live worker threads is reachable from the threading module), so a session that hits N failing jobs
  accumulates 5N idle threads plus the associated per-processor buffers. Also silently defeats the pool: the next job with
  identical config pays the full 200-500 ms `HybridProcessor.__init__` again.
- **Siblings**: The same "pop then drop" asymmetry exists in `ProcessorPool.return_to_cache`'s FIFO eviction
  (`core/processor_pool.py:107-111`: `self.processors.pop(cache_keys[0], None)` with no `.close()`), which is already
  filed as **#4370 (OPEN, LOW)** — reported there, not duplicated here. `ProcessorFactory` (`core/processor_factory.py`) is
  the *correct* reference implementation for both. No other `core/` or `services/` site pops a processor without returning it.
- **Suggested Fix**: Mirror the `TimeoutError` branch — add
  `if processor is not None and config is not None: await self._return_processor(job.mode, config, processor)` to the
  `except Exception` branch, or (cleaner) hoist the return into the existing `finally:` and drop it from the three
  individual branches so no future exit path can miss it. If the processor is suspected to be in a bad state after a
  failure, call `processor.close()` instead of returning it — but it must be one or the other, never neither.

### BE5-01: Album-detail track rows read camelCase fields from a snake_case endpoint — artist and track number render blank
- **Severity**: HIGH
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/albums.py:115-150`, `auralis-web/backend/routers/serializers.py:163-173`, `auralis/library/models/core.py:91-155`, `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:62-77`
- **Status**: NEW
- **Description**:
  `GET /api/albums/{album_id}/tracks` returns `serialize_tracks(album.tracks)`. `serialize_object()`
  prefers the ORM object's `to_dict()` and returns it verbatim, so each track is `Track.to_dict()` —
  strictly snake_case, with `artists` as an **array** and no singular `artist` key. The only production
  consumer, `useAlbumDetails.ts`, maps every nested track through **camelCase** property reads. Every one
  of those reads is `undefined`, and each is silently defaulted, so the album detail page renders tracks
  with an empty artist column and no track numbers instead of failing loudly.

  The backend even documents the opposite belief: `routers/albums.py:110-112` says "The sibling
  `{id}/tracks` endpoint intentionally stays snake_case **for its existing consumer
  (useAlbumDetails.ts)**". The consumer does not in fact read snake_case for the nested track objects —
  only for the three top-level album keys (`album_id`, `album_title`, `total_tracks`).
- **Evidence**:
  Backend emits (`auralis/library/models/core.py:122-155`): `'artists': artist_names`, `'artwork_url'`,
  `'track_number'`, `'disc_number'`, `'album_id'` — and **no** `'artist'`, **no** `'filepath'`.

  Frontend reads (`useAlbumDetails.ts:62-77`):
  ```ts
  tracks: (data.tracks || []).map((t: DetailTrack) => ({
    id: t.id,
    title: t.title ?? '',
    artist: t.artist ?? '',          // backend key is `artists: string[]` -> ''
    album: t.album ?? '',
    duration: t.duration ?? 0,
    filepath: t.filepath ?? '',      // backend never emits filepath  -> ''
    artworkUrl: t.artworkUrl ?? null,   // backend key is artwork_url  -> null
    genre: t.genre ?? null,             // backend key is genres[]     -> null
    year: t.year ?? null,
    trackNumber: t.trackNumber ?? null, // backend key is track_number -> null
    discNumber: t.discNumber ?? null,   // backend key is disc_number  -> null
    albumId: t.albumId ?? null,         // backend key is album_id     -> null
    favorite: t.favorite ?? undefined,
  })),
  ```
  Renderer (`components/library/Items/tables/TrackTableRowItem.tsx:70,90`):
  ```tsx
  trackNumber={track.trackNumber ?? undefined}
  ...
  {track.artist}
  ```
  Note `title`, `album`, `duration`, `year`, `favorite` happen to line up because those key names are
  identical in both casings — which is exactly why the bug is invisible in a smoke test: the row is
  populated, just missing artist and track number.
- **Impact**:
  Album detail view (a primary navigation surface) shows a track list with a blank artist column and no
  track numbers, and `albumId` is null so any downstream album navigation from a row is broken. No error
  is logged because every read is `??`-defaulted. `filepath: ''` also feeds `queue_recommender`/
  `queue_statistics` format extraction, which then reports `'unknown'` for every track.
- **Siblings**:
  Same class of defect (camelCase reader vs snake_case emitter) exists nowhere else I could find in a
  production path: `useLibraryQuery.ts` and `useInfiniteAlbums.ts` correctly route through
  `transformAlbums`/`transformArtists`. `api/transformers/trackTransformer.ts` has the mirror-image
  problem (`filepath: apiTrack.filepath`, `dateAdded: apiTrack.date_added` — both always undefined) but
  has **zero production callers** (only `playlistTransformer.ts`, itself orphaned per #4492), so it is
  latent rather than live — see BE5-02.
- **Suggested Fix**:
  Route `data.tracks` through the existing `transformTrack()` (after fixing it per BE5-02), or map the
  actual backend keys in `useAlbumDetails.ts` (`t.artists?.[0] ?? ''`, `t.artwork_url`, `t.track_number`,
  `t.disc_number`, `t.album_id`). Prefer the transformer so this endpoint gains a single, tested mapping
  point. Add a contract test that asserts the rendered row's artist is non-empty for a fixture album.

### BE6-01: Unguarded worker stops abort the rest of lifespan shutdown, skipping the SQLite WAL checkpoint
- **Severity**: HIGH
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/startup.py:545-610`
- **Status**: NEW
- **Description**: The shutdown block is one big `try/except Exception`. The later steps (audio player stop, processor-factory cache clear, artwork session close, `library_manager.shutdown()`) each have their *own* inner `try/except`, but the three earliest steps do not: the `BACKGROUND_WORKER_KEYS` stop loop (`await worker.stop(...)`), `streamlined_worker.stop()`, and `processing_engine.stop_worker()`. If any of those raises (e.g. a fingerprint worker that times out, or `stop()` on a partially-initialised worker), control jumps to the outer handler at line 609 and **every** remaining shutdown step is skipped.
- **Evidence**:
```python
try:
    from config.background_workers import BACKGROUND_WORKER_KEYS
    for _worker_key in BACKGROUND_WORKER_KEYS:
        worker = globals_dict.get(_worker_key)
        if worker:
            await worker.stop(**_worker_stop_kwargs.get(_worker_key, {}))   # unguarded
    ...
    if 'streamlined_worker' in globals_dict and globals_dict['streamlined_worker']:
        await globals_dict['streamlined_worker'].stop()                     # unguarded
    if 'processing_engine' in globals_dict and globals_dict['processing_engine']:
        await globals_dict['processing_engine'].stop_worker()               # unguarded
    ...
    if 'library_manager' in globals_dict and globals_dict['library_manager']:
        try:
            globals_dict['library_manager'].shutdown()   # WAL checkpoint + engine dispose
        ...
except Exception as e:
    logger.error(f"Error during shutdown: {e}")
```
  Note the sibling helper `config/background_workers.py:50-55` already wraps each `worker.stop()` in its own try/except — the lifespan path re-implements the loop inline *without* that protection, so the two paths that #4111 was meant to keep in sync have diverged in error handling.
- **Impact**: On a bad shutdown the audio device is never released, the HybridProcessor thread pools (#3746) leak, the aiohttp artwork session is never closed, and — most importantly — `LibraryManager.shutdown()` never runs, so the SQLite WAL is not checkpointed and the engine is not disposed. On an Electron quit this is a silent partial shutdown; repeated occurrences grow `library.db-wal` and leave the DB needing recovery on next open.
- **Siblings**: `config/background_workers.py:35-56` implements the same loop *with* per-worker guards — the divergence is the root cause.
- **Suggested Fix**: Replace the inline loop with a call to `stop_background_workers(lambda k: globals_dict.get(k))`, and wrap the `streamlined_worker.stop()` / `processing_engine.stop_worker()` calls in their own try/except so every shutdown step is best-effort and independent.

### BE7-01: Chunk/full-audio cache WAVs are written non-atomically to their canonical cache path — a crash mid-write leaves a truncated file that is served forever as a cache hit
- **Severity**: HIGH
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/chunked_processor.py:728-760` and `:652-681`; `auralis-web/backend/core/encoding/wav_encoder.py:142-149`
- **Status**: NEW (nearest dedup match is OPEN #4508, which is the *engine-side* `FingerprintStorage.save` `.25d` file — a different file, different subsystem, and only LOW there because a bad fingerprint is recomputable; this is the audio cache path)
- **Description**: Every producer of a cached chunk WAV writes directly to the final, content-addressed cache filename. There is no `tmp` + `os.replace` (or `.part` suffix) staging step, and the cache-hit path validates only `Path.exists()` — never size, WAV header length, or decodability. If the process dies between file creation and the last byte (Electron quit, `kill -9`, OOM, power loss — all routine on a desktop app), a truncated WAV sits at the exact key the cache looks up.
- **Evidence**:
  - `core/chunked_processor.py` (`get_wav_chunk_path`) writes the final file in one shot:
    ```python
    wav_bytes = encode_to_wav(extracted_chunk, self.sample_rate)
    # Write WAV file
    wav_chunk_path.write_bytes(wav_bytes)
    ```
    and the hit path immediately above it is a pure existence check:
    ```python
    # Check if already exists on disk
    if wav_chunk_path.exists():
        logger.info(f"WAV chunk {chunk_index} already exists on disk")
        self._cache_manager.cache_chunk_path(cache_key, wav_chunk_path)
        return str(wav_chunk_path)
    ```
  - `get_full_processed_audio_path` has the same shape: `if full_path.exists(): return str(full_path)` guarding a later `save_audio(str(full_path), full_audio, self.sample_rate, subtype='PCM_16')`.
  - `core/encoding/wav_encoder.py::encode_and_save` calls `save_audio(str(chunk_path), ...)` directly on the destination path; its validation (`ndarray`, non-empty, `np.isfinite`) all runs *before* the write, so it cannot detect a partial write.
  - `core/chunk_cache_manager.py:191,210` — `get_cached_chunk_path` / `cache_chunk_path` likewise gate on `if not path.exists()`.
  - Cache keys embed `CACHE_VERSION`, track id, file signature, preset and intensity, so the poisoned entry is stable across restarts: the only recovery is a manual cache clear.
- **Impact**: Persistent audio corruption surviving restart. After an unclean shutdown, the affected chunk decodes short or fails to decode; the user hears a gap/glitch at a fixed point in a specific track on every subsequent play, with no error surfaced anywhere (the WAV *is* there, so nothing on the error path fires). It is the one place in this dimension where an error path produces durable wrong audio rather than a transient failure.
- **Siblings**: All three write sites above (per-chunk WAV, full concatenated WAV, `WAVEncoder.encode_and_save`) share the defect, plus the two existence-only cache gates in `chunk_cache_manager.py`. `services/artwork_downloader.py:352` (`await asyncio.to_thread(filepath.write_bytes, data)`) has the same non-atomic shape but is benign: the filename embeds an MD5 of the payload and a bad image is merely re-fetched.
- **Suggested Fix**: Write to `chunk_path.with_suffix('.wav.part')` (or a `NamedTemporaryFile` in the same directory) and `os.replace()` onto the final name — `os.replace` is atomic within a filesystem, so a reader either sees the complete file or no file. Optionally add a cheap sanity gate on cache hit (declared RIFF size vs. `st_size`) to evict any pre-existing poisoned entries written before the fix.

### BE8-01: Tier-1 (DB) fingerprint lookup is still dead — the #3836 fix reads a globals dict that startup never populates
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/chunked_processor.py:71-87`, `auralis-web/backend/config/globals.py:155-191`, `auralis-web/backend/main.py:97-115`, `auralis-web/backend/core/mastering_target_service.py:460-482`
- **Status**: Regression of #3836 (CLOSED — the shipped fix is non-functional)
- **Description**: #3836 fixed "Tier-1 (DB) fingerprint lookup is silently dead on every track" by adding `_default_get_fingerprints_repository()`, which resolves the repository from `config.globals.globals_dict`. But the runtime component registry is **not** that dict. `main.py:97` constructs its own local `globals_dict` literal, passes it as `deps['globals']`, and `config/startup.py:217` writes `globals_dict['repository_factory']` into *that* object. The module-level `globals_dict = create_globals_dict()` at `config/globals.py:191` is a completely separate dict that no startup code ever touches — and `create_globals_dict()` does not even declare a `'repository_factory'` key (grep: zero matches in `config/globals.py`). So the accessor's `globals_dict.get("repository_factory")` returns `None` on every call, unconditionally, in production.
- **Evidence**:
```python
# core/chunked_processor.py:80-84  — reads the dead dict
from config.globals import globals_dict
factory = globals_dict.get("repository_factory")
if factory is None:
    return None                       # ← always taken
```
```python
# main.py:97-115 — the LIVE registry is a different object
globals_dict = { 'library_manager': None, 'repository_factory': None, ... }
deps = { ..., 'globals': globals_dict, ... }
# config/startup.py:217 — populates main.py's dict, not config.globals'
globals_dict['repository_factory'] = RepositoryFactory(...)
```
```python
# config/globals.py:155-191 — dead sibling, no 'repository_factory' key at all
def create_globals_dict() -> dict[str, Any]:
    return {'library_manager': None, 'settings_repository': None, ...}
globals_dict = create_globals_dict()
```
  `MasteringTargetService.load_fingerprint()` (`core/mastering_target_service.py:314-336`) therefore always falls through Tier 1 (database, fastest) to Tier 2 (`.25d` sidecar) and, absent a sidecar, Tier 3 (`extract_fingerprint_from_audio`, documented "slow").
- **Impact**: Every `ChunkedAudioProcessor` construction — one per stream, one per preset switch, one per cache-warm job — re-derives the mastering fingerprint from disk or from a full audio extraction instead of a single indexed DB row, despite the fingerprint already being in the library DB. This is the exact cost #3836 was closed to eliminate: added latency before first audio on every play and every preset change, and redundant CPU that competes with live chunk mastering. It is invisible in logs because the accessor's `except Exception: return None` and the Tier-1 miss both log at DEBUG.
- **Siblings**: `core/chunked_processor.py:82` is the only reader of `config.globals.globals_dict`; the dead `create_globals_dict()`/`globals_dict` pair at `config/globals.py:155-191` is otherwise unreferenced (see BE8-05).
- **Suggested Fix**: Make `config.globals` the single registry — have `main.py` import and mutate `config.globals.globals_dict` instead of building a private literal (and add the missing `'repository_factory'` key), or thread the factory into `ChunkedAudioProcessor` explicitly. Add a test asserting `_default_get_fingerprints_repository()` is non-None after `create_lifespan(deps)` startup.

### BE8-02: PlaybackService holds `_playback_lock` across `ConnectionManager.broadcast()` — one stalled WS client freezes all transport controls
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/backend/services/playback_service.py:145-153,181-188,215-223,262`, `auralis-web/backend/config/globals.py:123-152`
- **Status**: NEW (Related: #3867, which covers only the serial-iteration slowness *inside* broadcast, not the lock held across it)
- **Description**: `play()`, `pause()`, `stop()` and `seek()` each hold `self._playback_lock` for the whole body, which includes `await self.connection_manager.broadcast({...})`. `broadcast()` iterates the connection snapshot and `await connection.send_text(...)` per client with **no timeout and no `wait_for`**. Starlette's WebSocket send applies backpressure: if a client stops reading (backgrounded/suspended Electron renderer, a half-open TCP connection not yet detected as stale), `send_text` blocks until the OS socket buffer drains. Because the lock wraps it, every other transport command queues behind that one stalled send.
- **Evidence**:
```python
async with self._playback_lock:  # #3734
    await asyncio.to_thread(self.audio_player.play)
    await self.player_state_manager.set_playing(True)
    await self.connection_manager.broadcast({          # ← unbounded await under the lock
        "type": "playback_started", "data": {"state": "playing"}
    })
```
```python
# config/globals.py:139-146 — no timeout on the per-client send
for connection in connections_snapshot:
    try:
        await connection.send_text(message_json)       # ← can block indefinitely
    except Exception as e:
        stale_connections.append(connection)
```
  Note `broadcast()` correctly releases `ConnectionManager._lock` before sending (only the snapshot is taken under it) — the problem is the *caller's* lock, not that one.
- **Impact**: Play/pause/stop/seek all hang with no timeout and no error path; the user's transport buttons stop responding entirely and the only recovery is the socket eventually timing out at the OS level or a backend restart. The special-rule "lock held across an await" applies; downgraded from an outright CRITICAL because it is loopback-only and self-heals once the socket errors, but not downgraded further because there is no bound at all on the stall.
- **Siblings**: `services/queue_service.py:180-192` (`_broadcast_queue_changed`) awaits the same unbounded `broadcast()`, and `cache/manager.py:213,218,311,498` hold `self._lock` across `await`s — those are internal awaits with bounded work, so only the playback path has the unbounded-external-await shape.
- **Suggested Fix**: Move the `broadcast()` call outside the `async with self._playback_lock` block (state is already committed by then), and independently wrap each per-client `send_text` in `asyncio.wait_for(..., timeout=~2s)` inside `ConnectionManager.broadcast`, treating a timeout as a stale connection.


## MEDIUM (21)

### BE1-02: `upload_and_process` writes up to 500 MB to disk synchronously on the event loop
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/processing_api.py:214-296` (write at 259-261)
- **Status**: NEW
- **Description**: The upload handler is `async def` but performs the temp-file write with a plain blocking `open()/write()`. `_MAX_UPLOAD_BYTES` is 500 MB (`config/limits.py`), so the whole payload is held in memory and then written on the event-loop thread. The sibling upload handler in `routers/files.py` was explicitly fixed for exactly this (#3494) and wraps every sync step in `asyncio.to_thread`; `processing_api.py` was never brought in line.
- **Evidence**:
```python
# routers/processing_api.py:259-261  (async def upload_and_process)
input_path = temp_dir / f"{uuid.uuid4()}{original_ext}"
with open(input_path, "xb") as f:
    f.write(content)            # blocking, up to 500 MB, no run_in_executor
# also blocking: temp_dir.mkdir(exist_ok=True)  (line 235)

# routers/files.py:194-199 — the correct sibling pattern
def _write_temp(content_bytes: bytes, suffix_str: str) -> str: ...
temp_path = await asyncio.to_thread(_write_temp, content, suffix)
```
- **Impact**: While the write runs, the event loop is stalled: WebSocket audio chunk delivery, heartbeats and every other REST request are blocked → audible playback dropout and possible heartbeat-timeout disconnects. Rated MEDIUM rather than HIGH because the only client of this endpoint is `frontend/src/services/processingService.ts:227`, which issue #4470 records as having zero production consumers — but the route is registered and reachable on `127.0.0.1:8765`.
- **Siblings**: None else — `routers/files.py`, `routers/metadata.py`, `routers/artwork.py` and all repository calls already use `asyncio.to_thread`.
- **Suggested Fix**: Move the `mkdir` + `open()/write()` into an `asyncio.to_thread` helper mirroring `files.py::_write_temp`, ideally streaming `file.read(chunk)` into the target instead of buffering the full body.

### BE1-03: Similarity routes 500 instead of 503 when the similarity system is uninitialised
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/similarity.py:171-181, 238-241, 275-278` (contrast 305-308)
- **Status**: NEW
- **Description**: `globals_dict['similarity_system']` is legitimately `None` when component init fails or before the lifespan populates it (`config/startup.py:456-459` sets it to `None` on any exception), and the router family is registered on the import-time `HAS_SIMILARITY` flag independent of that. `POST /fit` guards with an explicit `if similarity is None: raise HTTPException(503, ...)`, but `get_similar_tracks`, `compare_tracks` and `explain_similarity` dereference the getter result directly, so `None.is_fitted` raises `AttributeError`, is swallowed by `_with_similarity_error_handling`, and becomes an opaque `500 "Error … (ref 1a2b3c4d)"`.
- **Evidence**:
```python
# similarity.py:275-278 (explain_similarity)
similarity = get_similarity_system()
if not await asyncio.to_thread(similarity.is_fitted):   # AttributeError when None → 500 via decorator
    raise HTTPException(status_code=503, detail="Similarity system not initialized")

# similarity.py:305-308 (fit) — the correct guard
if similarity is None:
    raise HTTPException(status_code=503, detail="Similarity system not available")
```
- **Impact**: The frontend cannot distinguish "feature not ready yet, retry later" from a genuine server fault: a 503 with a clear message becomes a 500 with only a correlation id. `similarityService.ts` surfaces it as a hard error instead of a "still initialising" state.
- **Siblings**: Same class of unguarded getter in `routers/library_scan.py:49-50` (`library_manager = get_library_manager()` then `LibraryScanner(library_manager)` with no `None` check → 500 from `handle_query_error` instead of 503) and `routers/player.py:356-357` (`library_manager.tracks.get_by_id(...)` executed **outside** the `try:` at line 361, so a `None` manager produces an unhandled `AttributeError`). `routers/similarity_graph.py` and `routers/cache_streamlined.py::_require_cache` do it correctly.
- **Suggested Fix**: Add the same `if X is None: raise ServiceUnavailableError(...)` guard used by `_require_cache`/`require_repository_factory` to every getter dereference — ideally by routing all three through a shared `require_similarity_system()` helper in `similarity_common.py`.

### BE1-04: `_recommendation_cache` in the enhancement router never evicts and is keyed by an unbounded client-supplied float
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/enhancement.py:43-44, 376-456`
- **Status**: NEW
- **Description**: `GET /api/player/mastering/recommendation/{track_id}` caches results in a module-level dict keyed by `(track_id, confidence_threshold)`. Expired entries are detected on read but never deleted, and no size cap exists. `confidence_threshold: float = 0.4` is a bare query parameter with **no** `Query(..., ge=0.0, le=1.0)` bounds despite the docstring documenting the 0.0–1.0 range, so the key space is effectively unbounded (every distinct float is a new permanent entry), and out-of-range values (negative, `1e30`, `nan` via `?confidence_threshold=nan`) are passed straight into `proc.get_mastering_recommendation()`.
- **Evidence**:
```python
_recommendation_cache: dict[tuple[int, float], tuple[float, dict[str, Any]]] = {}
_RECOMMENDATION_TTL_S: float = 60.0
...
async def get_mastering_recommendation(track_id: int, confidence_threshold: float = 0.4):
    _cache_key = (track_id, confidence_threshold)     # unbounded key space, no eviction
    ...
    _recommendation_cache[_cache_key] = (_now + _RECOMMENDATION_TTL_S, result_dict)
```
- **Impact**: Process-lifetime memory growth proportional to (tracks × distinct thresholds requested) with no ceiling — a long desktop session that browses a large library retains every recommendation payload forever. Out-of-range/`nan` thresholds reach the DSP analysis layer unvalidated.
- **Siblings**: None — every other numeric query parameter in the audited routers is bounded (`Query(..., ge=…, le=…)`) except the case in BE1-07.
- **Suggested Fix**: Declare `confidence_threshold: float = Query(0.4, ge=0.0, le=1.0)` and replace the plain dict with a bounded `OrderedDict`/LRU (or purge expired keys on insert).

### BE1-05: `useAppDragDrop` calls two playlist endpoints the backend never registers (405)
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: backend `auralis-web/backend/routers/playlists.py:230-302`; frontend `auralis-web/frontend/src/hooks/app/useAppDragDrop.ts:165, 215`
- **Status**: NEW
- **Description**: The drag-and-drop hook posts to `POST /api/playlists/{id}/tracks/add` and `PUT /api/playlists/{id}/tracks/reorder`. Neither path exists: the router registers `POST /api/playlists/{playlist_id}/tracks` (body `{track_ids: [...]}`, not `{track_id, position}`) and has **no** reorder route at all, even though `PlaylistRepository.reorder_track()` (`auralis/library/repositories/playlist_repository.py:506`) implements the operation. Both request paths pattern-match the `DELETE /api/playlists/{playlist_id}/tracks/{track_id}` route, so Starlette returns **405 Method Not Allowed**, not 404.
- **Evidence**:
```ts
// useAppDragDrop.ts:165
const response = await fetch(`/api/playlists/${playlistId}/tracks/add`, {
  method: 'POST', body: JSON.stringify({ track_id: trackId, position }) });
// useAppDragDrop.ts:215
await fetch(`/api/playlists/${playlistId}/tracks/reorder`, { method: 'PUT', ... });
```
- **Impact**: Any consumer of this hook gets "Failed to add track to playlist" / "Failed to reorder playlist" toasts for every drag-drop onto a playlist. Currently latent — `grep -rn useAppDragDrop` across `frontend/src` finds only `PHASE1/PHASE2_COMPLETION_REPORT.md`, i.e. the hook has no live importer — so this is drift that will bite whoever re-wires drag-and-drop rather than a live outage.
- **Siblings**: Same class of dead client→server drift: `services/api/standardizedAPIClient.ts:406-407` still calls `/api/chunks/{trackId}/{chunkIndex}`, retired with the WAV/MSE router in #4435 (`config/routes.py:274-278`); `config/api.ts:55,77-79` still exports `PLAYER_PLAY`/`PLAYER_PAUSE`/`PLAYER_STOP`/`ENHANCEMENT_SETTINGS` constants for routes that do not exist (`ComfortableApp.tsx:63` documents their removal); `store/middleware/errorTrackingMiddleware.ts:348` beacons to a non-existent `/api/errors`.
- **Suggested Fix**: Either add `PUT /api/playlists/{playlist_id}/tracks/reorder` (wired to `reorder_track`) and point the hook's add call at the existing `POST …/tracks` contract, or delete the orphaned hook and the stale constants.

### BE2-05: A truncated stream emits a success-shaped `audio_stream_end` reporting the FULL track length
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_enhanced.py:179-286`, `auralis-web/backend/core/stream_seek.py:187-285`
- **Status**: NEW
- **Description**:
  The per-chunk loop `break`s when enhancement is toggled off mid-stream, and control then falls
  straight through to `_send_stream_end(total_samples=int(processor.duration * processor.sample_rate),
  duration=processor.duration)` — i.e. a normal end-of-track message describing the *whole* track,
  even though only the chunks streamed so far were delivered. There is no field distinguishing
  "completed" from "stopped early", so a client cannot tell a truncated stream from a finished one.
  The frontend already carries a workaround comment acknowledging exactly this
  (`useEnhancementControl.ts:265-276`: "the backend's `stream_enhanced_audio` loop sees enabled=false,
  breaks, and emits a success-shaped `audio_stream_end` — the frontend completes streaming and the
  user is silenced"), which it patches by re-issuing the stream — a client-side band-aid over a
  backend protocol defect.
  The other `break`s in the same loops are disconnect-driven, where `_send_stream_end` fails the
  connectivity check and is harmless; the enhancement-toggle break is the reachable case.
- **Evidence**:
```python
# core/stream_enhanced.py:181-187 → falls through to the unconditional stream_end below
if controller._get_enhancement_enabled and not controller._get_enhancement_enabled():
    logger.info("Enhancement disabled mid-stream, stopping enhanced stream ...")
    await controller._drain_cancelled_task(lookahead_task)
    lookahead_task = None
    break
...
# core/stream_enhanced.py:281-286
await controller._send_stream_end(websocket, track_id=track_id,
    total_samples=int(processor.duration * processor.sample_rate),
    duration=processor.duration)
```
- **Impact**: `completeStreaming` marks the stream 100 % complete with a duration that does not match
  the delivered audio; any consumer that treats `audio_stream_end` as "track finished" (progress
  gauges today, auto-advance logic tomorrow) is wrong. Forces the frontend to keep a compensating
  re-issue hack.
- **Siblings**: `stream_seek.py:189-195 / 280-285` is the same code shape.
  `stream_normal.py:308-315` has no early-break-with-partial-content case (its only breaks are
  disconnects), so it is unaffected.
- **Suggested Fix**: Track whether the loop completed (`completed = chunk_idx == total_chunks - 1`,
  or a flag set on each break) and either send `audio_stream_end` with a
  `reason: "completed" | "stopped"` field plus the actually-delivered sample count, or send a
  distinct `audio_stream_stopped` message on the early-break path.

### BE3-02: On-disk WAV chunk cache is not keyed on mastering targets — a track cached before its fingerprint exists keeps serving un-targeted chunks
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunked_processor.py:198-231, 687-745`; key generation at `auralis-web/backend/core/chunk_cache_manager.py:50-109`
- **Status**: NEW
- **Description**: Both chunk cache keys (`get_chunk_cache_key` / `get_wav_cache_key`) and the on-disk WAV filename (`WAVEncoder.get_chunk_path` via `chunked_processor._get_chunk_path`) are composed of `track_id + file_signature + preset + intensity + chunk_index`. They do **not** include `mastering_targets`. But `mastering_targets` materially changes the DSP: `ProcessorFactory.get_or_create` deliberately hashes them into its own processor cache key (`core/processor_factory.py:206-215`, "#3720: include the targets content in the cache key"), and `AudioProcessingPipeline.apply_enhancement` takes a completely different branch when `targets is not None` (`core/audio_processing_pipeline.py:177-204`, fingerprint analysis disabled + fixed targets). `ChunkedAudioProcessor.__init__` loads targets with `extract_if_missing=False` (`chunked_processor.py:213-218`), so on first play a track normally has **no** fingerprint and therefore no targets; the background fingerprint queue fills it in afterwards.
- **Evidence**:
  ```python
  # core/chunk_cache_manager.py:77
  return f"{track_id}_{file_signature}_{preset}_{intensity}_chunk_{chunk_index}"
  # core/chunk_cache_manager.py:109
  return f"{track_id}_{file_signature}_{preset}_{intensity}_wav_{chunk_index}"
  ```
  `get_wav_chunk_path` short-circuits on the *file existing on disk*, not just on the in-process dict:
  ```python
  # core/chunked_processor.py:724-729
  wav_chunk_path = self._get_wav_chunk_path(chunk_index)
  if wav_chunk_path.exists():
      logger.info(f"WAV chunk {chunk_index} already exists on disk")
      self._cache_manager.cache_chunk_path(cache_key, wav_chunk_path)
      return str(wav_chunk_path)
  ```
  So a WAV written by an earlier, target-less `ChunkedAudioProcessor` (via `process_chunk`'s `encode_and_save_from_path`, same path) is returned verbatim to a later, target-aware processor.
  Mitigating factor (verified): `config/startup.py:176-179` `shutil.rmtree`s `/tmp/auralis_chunks` at startup, so this does not persist across restarts. It is an intra-session issue only.
- **Impact**: Within a session, chunks processed before the fingerprint landed are mixed with chunks processed after it → an audible tonal/level shift mid-track at the boundary where the cache stops covering. `_preprocess_upcoming_chunks` (`routers/enhancement.py:163`) is the concrete reachable path since it calls `get_wav_chunk_path` directly.
- **Siblings**: `core/chunk_cache.py:46-60` — `SimpleChunkCache._make_key` has the same gap (`v{VERSION}:{track_id}:{chunk_idx}:{preset}:{intensity}:{file_signature}`), though its impact is smaller because a fresh `SimpleChunkCache` is created per `play_enhanced` (#3855).
- **Suggested Fix**: Fold a short hash of `mastering_targets` (reuse `ProcessorFactory._get_targets_hash`) into `ChunkCacheManager.get_chunk_cache_key` / `get_wav_cache_key` and into the `WAVEncoder` filename, so a targets change misses instead of serving mismatched audio. Cheap alternative: have the fingerprint-queue completion callback call `ChunkCacheManager.clear_track_cache(track_id, file_signature)` and unlink the track's on-disk WAVs.

### BE3-03: Disk-cache hit in `process_chunk` / `get_wav_chunk_path` skips LevelManager recording — the #3832 fix covers only the in-memory tier
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunked_processor.py:515-524` and `:713-729`
- **Status**: NEW (sibling of CLOSED #3832 / #4367 — those fixes are present and correct in `core/stream_chunk_ops.py:83-97`, but only there)
- **Description**: `LevelManager` keeps a chronological `rms_history` / `gain_history` used by `smooth_transition` to limit inter-chunk level changes to `MAX_LEVEL_CHANGE_DB` (1.5 dB). #3832 established that a cache hit must still be *recorded* (`note_cached_chunk_level`) so a later cache-MISS chunk smooths against the right previous RMS. That recording is wired only into the `SimpleChunkCache` branch of `stream_chunk_ops.process_chunk_only`. The two `ChunkedAudioProcessor` cache-hit branches return early without touching the `LevelManager`.
- **Evidence**:
  ```python
  # core/chunked_processor.py:515-524  (dict/disk cache hit inside process_chunk)
  if cached_path is not None:
      logger.info(f"Serving cached chunk {chunk_index}/{self.total_chunks}")
      from auralis.io.unified_loader import load_audio
      audio, _ = load_audio(str(cached_path))
      return (str(cached_path), audio)      # <- no note_cached_chunk_level()
  ```
  ```python
  # core/chunked_processor.py:718-729  (get_wav_chunk_path, both dict and on-disk hits)
  if cached_path is not None:
      logger.info(f"Serving cached WAV chunk {chunk_index}")
      return str(cached_path)               # <- no note_cached_chunk_level()
  ```
  Reachable when `SimpleChunkCache` (50 chunks / 512 MB, `core/chunk_cache.py:32`) has evicted an entry but `ChunkCacheManager`'s per-processor dict still holds the path — i.e. long tracks and back-seeks. Also reachable on every `_preprocess_upcoming_chunks` call.
- **Impact**: `rms_history[-1]` is a stale, non-adjacent chunk's RMS when the next cache-MISS chunk is smoothed. `smooth_transition` then either applies a gain correction that is not needed or fails to apply one that is — a level step at the boundary, i.e. the exact artefact #3831/#3832/#4352 exist to prevent. Because the gain is baked into the WAV that is then cached, the wrong level is persisted.
- **Siblings**: Both sites above. The correct pattern already exists at `core/chunked_processor.py:405-431` (`note_cached_chunk_level`) — it is simply not called from these branches.
- **Suggested Fix**: In `process_chunk`'s cache-hit branch call `self.note_cached_chunk_level(audio, chunk_index, gain_db)`. `get_wav_chunk_path` returns only a path, so it must either decode the cached WAV to record the level or (cheaper) persist the trailing `gain_db` in a sidecar/attr keyed by chunk so the recording does not require a decode.

### BE3-04: No NaN/Inf validation on DSP *output* — `np.clip` passes NaN straight through to the PCM_16 encoder
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/audio_processing_pipeline.py:230-255`; `auralis-web/backend/encoding/wav_encoder.py:52-63`
- **Status**: NEW
- **Description**: `AudioProcessingPipeline.validate_audio` checks `np.all(np.isfinite(audio))` on the **input** (`audio_processing_pipeline.py:92-98`) and raises. There is no equivalent check on the **output** of `processor.process()`. `apply_enhancement` validates only `processed is None` and (for `intensity < 1.0`) the sample count. The chunk then flows to `trim_context` → `smooth_transition` → `extract_chunk_segment` → `encode_to_wav`, where the only sanitisation is `np.clip(audio, -1.0, 1.0)` — and `np.clip` leaves NaN as NaN.
- **Evidence**:
  ```python
  # encoding/wav_encoder.py:58-62
  # Ensure audio is in valid range for PCM_16 encoding [-1.0, 1.0]
  # Clip to prevent distortion
  audio = np.clip(audio, -1.0, 1.0)          # np.clip(np.nan, -1, 1) -> nan
  sf.write(wav_buffer, audio, sample_rate, format='WAV', subtype='PCM_16')
  ```
  A single NaN also poisons `LevelManager.calculate_rms` (`core/level_manager.py:83-84`: `np.sqrt(np.mean(audio**2))` → `nan`), so `level_diff_db` becomes `nan`, `abs(nan) > 1.5` is `False`, and the chunk silently takes the no-adjustment branch — and `nan` is appended to `rms_history`, so **every subsequent chunk** in the track also compares against `nan` and never smooths again.
- **Impact**: A NaN produced by any DSP stage becomes an undefined PCM sample (libsndfile behaviour is unspecified; typically full-scale or zero) — an audible click — and permanently disables level smoothing for the rest of the track. Precedent that this is reachable in this codebase: CLOSED #4104 ("Silent audio -> fully-NaN output via amplify(audio, +inf) crashes the stream") and CLOSED #4099/#4237 (inter-stage NaN guards added in the engine). The chunk pipeline has no such guard at its own boundary.
- **Siblings**: `core/level_manager.py:83-86` (`calculate_rms` has no finite guard); `core/chunk_crossfade.py:64` and `core/chunk_operations.py:331` propagate NaN through the mix.
- **Suggested Fix**: In `AudioProcessingPipeline.apply_enhancement`, after `processed = processor.process(audio)`, add `np.nan_to_num(processed, nan=0.0, posinf=1.0, neginf=-1.0, copy=False)` on the pipeline-owned array (or `np.isfinite` + log + fall back to `audio`). Additionally make `encode_to_wav` use `np.nan_to_num` before `np.clip` as a last line of defence.

### BE4-02: `ProcessorFactory.get_or_create` holds a `threading.RLock` across 200-500 ms `HybridProcessor` construction
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processor_factory.py:218-275`
- **Status**: NEW (sibling-of-pattern; the *asyncio* variant in `core/processor_pool.py` is already reported by another dimension — this is the separate `threading.RLock` instance in a different file)
- **Description**: The factory serialises its whole cache under one process-wide `threading.RLock` (`self._lock`,
  line 106) and constructs the processor **inside** the critical section (`processor = HybridProcessor(config)`, line 243),
  along with the LRU eviction loop that calls `_evicted_proc.close()` (line 261) — executor shutdown, also blocking.
- **Evidence**: `with self._lock:` at line 218 spans the cache-hit read, `HybridProcessor(config)` at 243,
  `set_fixed_mastering_targets` at 247, and the `while len(...) > _PROCESSOR_CACHE_MAX` eviction/`close()` loop at 252-264.
  The engine's own async pool documents the counter-pattern explicitly and offloads construction
  (`core/processing_engine.py:165-170`: "Construction is CPU-bound (200-500 ms) — offloaded to a thread so the event loop
  stays responsive while the pool lock is held").
- **Impact**: This is a *sync* lock, so it does not itself block the event loop — but every consumer
  (`core/chunked_processor.py:218`, `core/audio_processing_pipeline.py:132` via `select_processor`) is on a chunk-production
  hot path. A cold-cache construction for one stream stalls **all** other streams' processor lookups for the full
  construction time, including cache *hits* that would otherwise be instant. With rapid preset A/B switching (each distinct
  `(track_id, preset, intensity, config_hash, targets_hash)` is a fresh construction) this serialises the whole streaming
  fleet behind one cold start. Confirmed callers are all invoked from worker threads, so it is contention, not event-loop
  starvation — hence MEDIUM rather than HIGH.
- **Siblings**: Same shape as the already-reported `ProcessorPool.get_or_create` asyncio-lock finding in
  `core/processor_pool.py:88-97`. Grep of `core/` + `services/` found no third instance.
- **Suggested Fix**: Two-phase it: under the lock, insert a placeholder/`Future` for the key and release; construct
  outside the lock; re-acquire only to publish. At minimum move the eviction `close()` calls out of the critical section
  (collect evicted instances into a local list, close them after `with` exits) — that alone removes the executor-shutdown
  stall from the hot path.

### BE4-03: `handle_seek` lets the stored preset/intensity override the client's, inverting `play_enhanced` precedence
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:221-231` (compare 69-89)
- **Status**: NEW
- **Description**: The two handlers resolve `preset`/`intensity` with **opposite** precedence against the shared runtime
  `enhancement_settings` dict. `handle_play_enhanced` treats the client message as authoritative and the stored dict as a
  *fallback*; `handle_seek` treats the stored dict as authoritative and the client message as the fallback. `handle_seek`
  additionally skips the `VALID_PRESETS` validation that `play_enhanced` performs (`schemas.VALID_PRESETS`, "single source
  of truth (#4424)").
- **Evidence**:
  ```python
  # handle_play_enhanced (client wins, stored is fallback):
  preset = raw_preset.lower() if (... raw_preset.lower() in VALID_PRESETS) else None
  ...
  if preset is None:
      preset = settings.get("preset", "adaptive")
      
  # handle_seek (stored wins, client is fallback — and no VALID_PRESETS check):
  preset = data.get("preset", "adaptive")
  intensity = data.get("intensity", 1.0)
  if deps.get_enhancement_settings is not None:
      preset = settings.get("preset", preset)
      intensity = settings.get("intensity", intensity)
  ```
  The stored dict is *always* populated with a `"preset"` key (`main.py:110-114`, `config/globals.py:179-183`,
  and `helpers.seed_enhancement_settings` at `helpers.py:629-647`), so `settings.get("preset", preset)` unconditionally
  discards whatever the client sent.
- **Impact**: Whenever the frontend's live preset/intensity differs from the server-side dict — which is the normal state
  per the project's own note that the live source is `useEnhancementControl()` local state while the server dict only
  updates when the enhancement REST endpoints are hit — a seek silently re-masters the track with a *different* preset than
  the one the user is currently listening to. The user hears an audible enhancement change purely as a side effect of
  scrubbing, with no UI indication. Not audio corruption (both presets are valid), so MEDIUM.
- **Siblings**: `handle_play_normal` (154-200) takes no preset at all (correct — normal path is unprocessed).
  `routers/system.py:84-85, 231-232` read only `.get("enabled", ...)` and are unaffected. This is the only precedence
  inversion in the WS command surface.
- **Suggested Fix**: Extract the `play_enhanced` resolution block (validate against `VALID_PRESETS`, client value wins,
  stored dict as fallback) into one shared helper and call it from both handlers, so seek continues the *current* stream's
  enhancement rather than resetting it to the persisted default.

### BE5-02: `Track.to_dict()` omits six fields the frontend Track contract declares, including required `filepath`
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis/library/models/core.py:122-155`, `auralis-web/frontend/src/types/domain.ts:12-45`, `auralis-web/frontend/src/api/transformers/types.ts:57-83`, `auralis-web/frontend/src/types/ws/base.ts:40-66`
- **Status**: NEW
- **Description**:
  Every REST track payload (`/api/library/tracks`, `/api/library/tracks/{id}`, `/api/library/tracks/favorites`,
  `/api/albums/{id}/tracks`, `/api/playlists/{id}`) is produced by `Track.to_dict()`. That dict never
  contains `filepath`, `artist` (singular), `genre` (singular), `date_added`, `date_modified`, `loudness`,
  `crest_factor`, or `centroid`. The frontend contract declares several of these as **required**:
  - `types/domain.ts:18` — `filepath: string;` (required)
  - `api/transformers/types.ts:64` — `TrackApiResponse.filepath: string;` (required, and the file's header
    comment claims "These types represent the EXACT shape of data returned from the backend API")
  - `api/transformers/types.ts:80-83` — `date_added` / `date_modified`; backend emits `created_at` / `updated_at`
  - `api/transformers/types.ts:76-78` — `loudness` / `crest_factor` / `centroid`; backend emits
    `lufs_level` / `dr_rating` / (nothing)

  `types/ws/base.ts:46-52` additionally documents, as a code comment describing the contract: *"REST
  endpoints (album/track details) **do** return it [filepath]"*. That statement is false for every REST
  endpoint in the tree — I grepped all of `routers/` and no track-listing response includes `filepath`.
- **Evidence**:
  `serializers.py:18-42` `DEFAULT_TRACK_FIELDS` lists `'filepath': ''` under the comment *"Core identity
  (always required by TrackApiResponse)"*, but `serialize_object()` (`serializers.py:97-106`) returns
  `obj.to_dict()` and never reaches the fallback branch for a real ORM `Track`. So the declared default is
  unreachable and the field is simply absent from the wire.

  `trackTransformer.ts:31,50-51` consumes them without a fallback:
  ```ts
  filepath: apiTrack.filepath,          // -> undefined, typed as string
  dateAdded: apiTrack.date_added ?? undefined,   // always undefined
  dateModified: apiTrack.date_modified ?? undefined,
  ```
- **Impact**:
  Any consumer that trusts `Track.filepath: string` gets `undefined` at runtime with no type-checker
  warning (TS believes it is a `string`). Today the two live readers
  (`utils/queue/queue_statistics.ts:212`, `utils/queue/queue_recommender.ts:426`) guard with
  `if (!filepath) return 'unknown'`, so the format/statistics panels silently report "unknown" for 100% of
  tracks rather than crashing. `dateAdded`/`dateModified`/`loudness`/`crestFactor`/`centroid` are
  permanently undefined, so any sort or display keyed on them is dead. This is a latent
  `undefined`-deref waiting for the first consumer that does `track.filepath.endsWith(...)`.
- **Siblings**:
  `Album.to_dict()` (`core.py:208-224`) and `Artist.to_dict()` (`core.py:248-261`) have the analogous gap
  for `date_added` (they emit `created_at`); `api/transformers/types.ts:42` declares
  `ArtistApiResponse.date_added` and `artistTransformer` maps it, so `Artist.dateAdded` is likewise always
  undefined.
- **Suggested Fix**:
  Decide the intent explicitly. If `filepath` is deliberately withheld from REST (consistent with
  `player_state.TrackInfo.filepath = Field(exclude=True)`, #3205), then mark it optional in `domain.ts`
  and `api/transformers/types.ts`, delete it from `DEFAULT_TRACK_FIELDS`, and correct the false comment at
  `types/ws/base.ts:46-52`. If it is meant to ship, add it to `Track.to_dict()`. Either way, add
  `date_added`/`date_modified` aliases to `Track.to_dict()` (the `Playlist.to_dict()` `modified_at` alias
  at `core.py:336-337` is the established precedent) or drop them from the TS contract.

### BE5-03: The same Album entity is emitted in two different casings by sibling endpoints
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/serializers.py:220-241`, `auralis-web/backend/routers/albums.py:42-113`, `auralis-web/frontend/src/api/transformers/types.ts:15-31`
- **Status**: NEW
- **Description**:
  `GET /api/albums` returns `serialize_albums()` → snake_case (`track_count`, `artwork_url`,
  `total_duration`, `artist_id`). `GET /api/albums/{id}` returns `serialize_album_detail()` → camelCase
  (`trackCount`, `artworkUrl`, `totalDuration`, `artistId`). Two endpoints on the same router, same
  entity, two incompatible shapes. The frontend has exactly one Album contract type
  (`AlbumApiResponse`, snake_case) and one transformer (`transformAlbum`), which would silently produce
  `trackCount: undefined` if pointed at the detail endpoint.
- **Evidence**:
  `serialize_album_detail` (`serializers.py:230-241`) returns `{'trackCount': ..., 'artworkUrl': ...,
  'totalDuration': ..., 'artistId': ..., 'dateAdded': ...}` while `serialize_album` returns the
  snake_case keys. The docstring frames this as intentional (#4423), but it makes the API's casing
  convention endpoint-dependent rather than global, and `types/api.ts` / `api/transformers/types.ts`
  encode only the snake_case variant.
- **Impact**:
  A developer wiring an album-detail view will reach for `transformAlbum` (the documented "single source
  of truth for album data transformation") and get an all-undefined Album. Mitigating factor that keeps
  this at MEDIUM rather than HIGH: I found **no production consumer** of `GET /api/albums/{id}` — only
  MSW mocks (`test/mocks/handlers.ts:210`). So the divergence is currently unexercised.
- **Siblings**:
  None — every other serializer in `serializers.py` (`serialize_track`, `serialize_artist`,
  `serialize_playlist`) is uniformly snake_case. `serialize_album_detail` is the lone camelCase producer
  in the backend.
- **Suggested Fix**:
  Pick one convention for the wire (snake_case, matching the other 25 routers) and let the frontend
  transformer own the casing translation, as it already does for albums/artists/playlists. If the
  camelCase detail shape must stay, add a matching `AlbumDetailCamelApiResponse` type + transformer to
  `api/transformers/` so the contract is at least declared on both sides.

### BE5-04: WebSocket message-type registry has drifted in both directions (`cache_cleared`, `job_progress` backend-only; `queue_updated` frontend-only)
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:162`, `auralis-web/backend/ws_handlers/messages.py:69`, `auralis-web/frontend/src/types/ws/registry.ts:66-165`, `auralis-web/frontend/src/types/ws/queue.ts:12,23`
- **Status**: NEW
- **Description**:
  I enumerated every outbound `{"type": "..."}` literal in the backend and diffed it against the
  frontend's `WebSocketMessageType` union / `ALL_MESSAGE_TYPES`. Three types are unmatched:

  | Type | Backend emits | Frontend declares | Consequence |
  |---|---|---|---|
  | `cache_cleared` | yes (`cache_streamlined.py:162`) | **no** | broadcast falls on the floor; not in the union, so no component can even subscribe type-safely |
  | `job_progress` | yes (`ws_handlers/messages.py:69`) | **no** (only a raw string compare in `services/processingService.ts:158`) | consumer bypasses the typed registry entirely |
  | `queue_updated` | **no** (removed by #3492; see `services/queue_service.py:456` and `routers/player.py:583`) | yes — in the union, in `ALL_MESSAGE_TYPES`, in `QUEUE_TYPES`, with a `isQueueUpdatedMessage` guard | dead subscription key that can never fire |

  The frontend has a compile-time exhaustiveness assertion (`registry.ts:161-165`) that guarantees
  `ALL_MESSAGE_TYPES` covers the union — but nothing guarantees the union covers what the backend
  actually sends, so drift is one-directional-silent.
- **Evidence**:
  Backend outbound set (grep of `"type": "<literal>"` across `auralis-web/backend/`, excluding inbound
  `ping`/`pong`/`seek`): `artwork_updated, audio_chunk_meta, audio_stream_end, audio_stream_error,
  audio_stream_start, cache_cleared, enhancement_settings_changed, error, fingerprint_progress,
  job_progress, library_scan_error, library_scan_started, library_tracks_removed, library_updated,
  mastering_recommendation, metadata_batch_updated, metadata_updated, playback_paused, playback_resumed,
  playback_started, playback_stopped, player_state, playlist_created, playlist_deleted, playlist_updated,
  position_changed, queue_changed, queue_shuffled, repeat_mode_changed, scan_complete, scan_progress,
  seek_started, track_changed, track_loaded, volume_changed`.

  `routers/player.py:583` explicitly records the removal: *"`queue_updated` had no FE subscriber"* — yet
  the FE type/guard/registry entries were never removed.
- **Impact**:
  `cache_cleared` is emitted after a cache purge and no UI can react to it (cache panels stay stale until
  the next poll). `queue_updated` is a permanently-dead subscription key that a future author will
  reasonably subscribe to and then debug for an hour. `job_progress` works only because
  `processingService.ts` compares raw strings — and that file has zero production consumers (#4470), so
  the typed path for job progress does not exist at all.
- **Siblings**:
  Related but distinct and already open: #3780 (`seq` vs `sequence` field-name inconsistency across
  streams), #3873 (`WebSocketMessageType` enum in `schemas.py` documents only the inbound subset).
- **Suggested Fix**:
  Add `cache_cleared` and `job_progress` to `StreamingMessageType`/a new maintenance domain in
  `types/ws/`, with data shapes; delete `queue_updated` from `queue.ts`, `registry.ts` (union,
  `ALL_MESSAGE_TYPES`, `QUEUE_TYPES`) and `guards.ts`. Longer term, generate the frontend union from the
  backend literal set (or add a backend test that asserts every emitted literal appears in
  `ALL_MESSAGE_TYPES`) so the drift is caught mechanically.

### BE5-05: Player/queue request bodies carry no numeric range or length constraints — out-of-range indices reach the engine
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/player.py:52-127`
- **Status**: NEW
- **Description**:
  Body models in the player router validate almost nothing. Unlike the query-parameter surface (which
  consistently uses `Query(50, ge=1, le=200)`) and unlike `schemas.PaginationParams`
  (`ge=1, le=500`), the request bodies accept any `int`:
  - `SetQueueRequest.tracks: list[int]` — no `min_length`/`max_length`; `start_index: int = 0` — no `ge=0`,
    so `-1` is accepted
  - `ReorderQueueRequest.new_order: list[int]` — no bound, no permutation check
  - `MoveQueueTrackRequest.from_index` / `to_index` — no `ge=0`
  - `AddTrackToQueueRequest.track_id` / `position` — no `ge` bound; `track_id=-1` is accepted
  - `LoadTrackRequest.track_id: int` — no `ge=1`
  - `SeekRequest.position` — correctly rejects NaN/inf/negative (`player.py:84-91`) but has no upper bound,
    so a seek past `duration` is a valid request
  - `QueueHistoryStateSnapshot.current_index: int = 0` — no `ge=0`

  Two other models silently **clamp** rather than reject, which is a different strictness problem:
  `SetVolumeRequest.clamp_volume` (`player.py:98-101`) turns `volume: 999` into `100`, and
  `SetIntensityRequest.clamp_intensity` (`enhancement.py:70-73`) turns `intensity: 5.0` into `1.0`. A
  client bug that sends a 0–100 intensity gets a silent full-strength enhancement instead of a 422.
- **Evidence**:
  ```python
  class SetQueueRequest(BaseModel):
      tracks: list[int]      # Track IDs
      start_index: int = 0   # no ge=0

  class MoveQueueTrackRequest(BaseModel):
      from_index: int        # no ge=0
      to_index: int          # no ge=0
  ```
  Contrast `schemas.py:365-368`, which does constrain the same class of value:
  `limit: int = Field(default=50, ge=1, le=500)`.
- **Impact**:
  Negative and absurd indices reach `QueueService`/`PlaybackService` and the engine queue, where the
  failure mode is a 500 or a silently wrong queue position rather than a 422 that tells the client what
  was wrong. The clamping variants are worse than either: they convert a client contract violation into a
  successful response describing a value the client did not ask for.
- **Siblings**:
  `routers/playlists.py:35-49` (`CreatePlaylistRequest.name` has no `min_length`, `track_ids` no bound),
  `routers/metadata.py:36-63` (batch update request has no item-count bound). Path-parameter validation is
  the separate, already-open **#3893**; this finding is about **body** models, which #3893 does not cover.
- **Suggested Fix**:
  Add `Field(ge=...)` / `Field(min_length=..., max_length=...)` to the models above, mirroring the
  constraints already used in `schemas.PaginationParams`. Replace the two clamping `field_validator`s with
  `Field(ge=0, le=100)` / `Field(ge=0.0, le=1.0)` so an out-of-range value 422s at the boundary; if
  clamping must be preserved for backward compatibility, log a warning so it is at least observable.

### BE6-02: Similarity auto-fit runs on an untracked daemon thread that shutdown never joins
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/startup.py:431-455`
- **Status**: NEW
- **Description**: `_auto_fit_similarity` is launched on a bare `threading.Thread(daemon=True)`. The thread is never stored in `globals_dict`, never joined, and has no stop signal. It streams every fingerprint row through `sim_system.fit()` using the LibraryManager's `SessionLocal`, and on success assigns `gd['graph_builder']` from off the event loop. The lifespan shutdown block stops every other worker but has no knowledge of this thread.
- **Evidence**:
```python
threading.Thread(
    target=_auto_fit_similarity,
    name="similarity-autofit",
    daemon=True,
).start()
```
  No corresponding entry exists in `BACKGROUND_WORKER_KEYS` (`config/background_workers.py:26-30`) nor in `_ROLLBACK_SERVICES_TO_STOP` (`config/startup.py:38-42`).
- **Impact**: A quit during auto-fit (common on a large first-run library, which is exactly when auto-fit takes longest) tears the process down mid-SQLAlchemy-session. `library_manager.shutdown()` disposes the engine while the daemon thread may still hold a session, producing "Cannot operate on a closed database"/WAL-checkpoint contention on exit. It also races the destructive `POST /api/library/reset` path, which stops only the `BACKGROUND_WORKER_KEYS` workers — auto-fit keeps reading fingerprints from a database being reset.
- **Siblings**: None — every other long-running task in the backend goes through `spawn_background_task` or the `BACKGROUND_WORKER_KEYS` registry; this is the one exception.
- **Suggested Fix**: Run the fit via `spawn_background_task(asyncio.to_thread(_auto_fit_similarity))` and retain the task handle in `globals_dict` so shutdown (and library reset) can cancel/await it, or wrap it in a minimal `start()`/`stop()` service registered in `BACKGROUND_WORKER_KEYS`.

### BE6-03: `HAS_AURALIS` is a hardcoded `True` — the "demo mode" fallback it gates is unreachable
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/main.py:69`, `auralis-web/backend/config/startup.py:188,467-468`, `auralis-web/backend/routers/health.py:33`
- **Status**: NEW
- **Description**: #3534 replaced the three other feature flags with real import probes (`HAS_PROCESSING`, `HAS_STREAMLINED_CACHE`, `HAS_SIMILARITY` each have a `try: import ... except ImportError:` that flips them false). `HAS_AURALIS` was left as a bare literal `True` with no probe, so it can never be false.
- **Evidence**:
```python
HAS_AURALIS = True          # main.py:69 — no probe, unlike the three flags below it
...
try:
    from core.chunked_processor import ChunkedAudioProcessor
except ImportError:
    HAS_PROCESSING = False
```
  Consequences: `startup.py:467-468`'s `else: logger.warning("Auralis not available - running in demo mode")` is dead code, and `GET /api/health` reports `auralis_available: true` unconditionally (`routers/health.py:33`) even when the entire Auralis init block failed and `_rollback_partial_startup` nulled every component.
- **Impact**: The health endpoint lies about backend readiness — a failed Auralis startup (rolled back to all-None, every data route returning 503) still reports `{"status": "healthy", "auralis_available": true}`. Any client or packaging smoke test gating on `/api/health` sees a green light on a non-functional backend.
- **Siblings**: The other three flags are correctly probed — this is the single un-probed one.
- **Suggested Fix**: Give `HAS_AURALIS` an import probe matching the sibling pattern (`try: import auralis; except ImportError: HAS_AURALIS = False`), and have `/api/health` report readiness from the live `globals_dict['library_manager']` rather than the static import-time flag.

### BE7-02: `ArtworkDownloader`'s shared `aiohttp.ClientSession` has no `ClientTimeout` — a stalled artwork host holds a request for aiohttp's 5-minute default, x3 sources
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/services/artwork_downloader.py:136-142` (session construction), used at `:220`, `:235`, `:286`, `:310`
- **Status**: NEW (dedup: CLOSED #4442 is the *frontend* `apiRequest` timeout; no backend artwork-timeout issue open or closed)
- **Description**: The shared session is built with only a connector — `aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=4, ttl_dns_cache=300))`. No `timeout=aiohttp.ClientTimeout(...)` is passed, so every request falls back to aiohttp's default `total=5*60`. The downloader tries MusicBrainz search -> Cover Art Archive -> iTunes search -> iTunes download **sequentially**, so one album can occupy a worker for up to ~20 minutes against a black-holing host before the broad `except Exception: return None` at the end of each source finally fires.
- **Evidence**: session factory has no timeout kwarg; each source is a plain `async with session.get(...)` with no per-request `timeout=`; the fallback chain is sequential inside `download_artwork`. `TCPConnector(limit=4)` means four such stalls exhaust the pool and serialize everything behind them.
- **Impact**: Bulk artwork backfill can appear hung for minutes with no user-visible error. Not a correctness bug — the `except Exception` handlers do eventually return `None` cleanly and the session is properly closed at shutdown via `close_artwork_downloader()` — so this is a responsiveness/latency defect, not a leak. Downgraded from HIGH because the desktop-only app means the stalled path is a background enrichment, not a request-serving path.
- **Siblings**: None — this is the only `aiohttp` client in the backend (`grep` for `aiohttp` matches only this module).
- **Suggested Fix**: `aiohttp.ClientSession(connector=..., timeout=aiohttp.ClientTimeout(total=15, connect=5))`, and consider an overall `asyncio.wait_for` around the whole three-source fallback chain so the worst case is bounded regardless of how many sources are added later.

### BE7-03: `_validate_artwork_url` swallows all exceptions into `return False`, and the same broad-swallow shape recurs in six best-effort helpers
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/services/artwork_downloader.py:82-92`; siblings listed below
- **Status**: NEW
- **Description**: A full-tree AST sweep for handlers whose entire body is `pass` / `return None` / `return <const>` / `continue` found exactly 15 sites. Most are defensible (best-effort `websocket.send_text` guards). The ones worth reporting are the helpers where the swallow converts a *programming* error (AttributeError, TypeError, a refactor-broken attribute) into an indistinguishable "normal negative answer", so the wrong behaviour is silent:
  - `_validate_artwork_url` catching `Exception -> return False`: a bug inside the validator is indistinguishable from "untrusted domain", so artwork silently never downloads and the SSRF allowlist appears to reject everything, with no log line at all (the branch has no `logger` call).
  - `services/audio_content_predictor.py:173` — `except Exception: pass` inside prediction, silently degrading the ML result.
  - `core/processing_engine.py:479` — `except Exception: pass` on a processing path.
  - `routers/system.py:132,148,197,269` — these four are the WS `send_text` guards and are **fine as-is** (commented `# WebSocket may be closed`); listed only to account for the sweep.
- **Evidence**: the validator's terminal handler is literally
  ```python
    except Exception:
        return False
  ```
  with no logging, wrapping `urlparse` + hostname suffix matching. Compare with every *other* rejection path in the same module, which logs (`logger.warning(f"Rejecting untrusted artwork URL: {artwork_url!r}")`).
- **Impact**: Silent wrong behaviour rather than a crash — the class this dimension classifies as MEDIUM. A latent bug in any of these helpers manifests only as a feature quietly not working (no artwork, degraded prediction), with nothing in the logs to point at the cause.
- **Siblings**: Full swallow inventory from the AST sweep, for completeness: `services/artwork_downloader.py:92`, `services/audio_content_predictor.py:173`, `services/queue_service.py:255`, `ws_handlers/connection.py:59`, `core/processing_engine.py:479`, `core/mastering_target_service.py:255`, `core/chunked_processor.py:87` (already OPEN as the excluded `_default_get_fingerprints_repository`), `core/stream_protocol.py:59`, `routers/system.py:132/148/197/269`, `config/middleware.py:60/91/184` (excluded — covered by another dimension). Already OPEN and not re-reported: #3914 (`routers/library.py` lyrics `except Exception: pass`).
- **Suggested Fix**: Narrow to the exceptions actually expected (`ValueError` for `urlparse`), and add `logger.debug/warning` to every swallow so a silent failure is at least traceable. Where the handler exists purely to guard a best-effort WS send, keep the swallow but keep the explanatory comment.

### BE8-03: `ProcessorPool.get_or_create` holds its asyncio lock across the 200-500 ms processor construction
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/processor_pool.py:79-97`
- **Status**: NEW
- **Description**: The pool's `asyncio.Lock` is held for the whole `get_or_create` body, including `await self._create_processor(config)` — a factory that offloads a documented 200-500 ms CPU-bound `HybridProcessor.__init__` to a thread. The docstring justifies this as "the event loop stays responsive while the lock is held", which is true for the loop but not for other acquirers: any concurrent job needing a *different* config serialises behind the construction, even though there is no shared state to protect during the construction itself (the key was already checked and missed).
- **Evidence**:
```python
async with self._lock:
    key = self.cache_key(mode, config)
    if key in self.processors:
        return self.processors.pop(key)
    processor = await self._create_processor(config)   # ← 200-500 ms under the lock
    return processor
```
- **Impact**: With `ProcessingEngine(max_concurrent_jobs=2)` the observable cost is bounded (~0.5 s of added latency for the second job), but the shape also means a construction that hangs — e.g. a `HybridProcessor` blocking on a stalled file read from a network/cloud-synced music folder — permanently deadlocks every future processor acquisition, with no timeout.
- **Siblings**: `core/streamlined_worker.py:324` has the same shape (`await asyncio.to_thread(...)` under a held lock).
- **Suggested Fix**: Release the lock around construction — re-check the key after the `await` and, if another coroutine created one meanwhile, keep one and discard/close the duplicate; or hold a per-key placeholder future instead of the pool-wide lock.

### BE8-04: Second N+1 in `queue_service._resolve_entries` — one `get_by_path` per unresolved queue entry
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/services/queue_service.py:263-276`
- **Status**: NEW (distinct from #4359, which covers `_broadcast_queue_changed`'s `get_by_id` loop on the event loop)
- **Description**: When the player-state snapshot doesn't cover every engine queue entry, `_resolve_entries` issues one `tracks.get_by_path(fp)` per missing filepath inside `_lookup()`. Unlike #4359 this correctly runs under `asyncio.to_thread`, so the event loop is not blocked — but it is still N sequential indexed queries where a single batched lookup would do, and the sibling `TrackRepository` already exposes a batched accessor (`get_by_ids`, used at `queue_service.py:352-359` precisely to avoid this).
- **Evidence**:
```python
def _lookup() -> dict[str, TrackInfo]:
    found: dict[str, TrackInfo] = {}
    for fp in missing:
        track = self.library_manager.tracks.get_by_path(fp)   # N queries
        ...
by_fp.update(await asyncio.to_thread(_lookup))
```
  compare `queue_service.py:352-359`, which deliberately uses the batched `get_by_ids` "for large queues".
- **Impact**: Scales with queue size. On a "play all" of a large album/playlist where the state manager snapshot is stale (the exact scenario #4374 documented — engine queue and state manager diverge after add/remove/move), every queue read issues hundreds of round-trips before the WebSocket queue payload is emitted, visibly delaying the queue UI.
- **Siblings**: `services/queue_service.py:362-368` has a `_fetch_individually` fallback with the same shape, but it is guarded by `hasattr(tracks_repo, 'get_by_ids')` and is dead against the real repository.
- **Suggested Fix**: Add/use a batched `get_by_paths(list[str]) -> dict[str, Track]` on `TrackRepository` mirroring `get_by_ids`, and call it once from `_lookup()`.

### BE9-01: Twelve backend test modules are hard-skipped at module level, giving illusory subsystem coverage
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_playlist_operations.py:24`, `tests/backend/test_error_handling.py:22`, `tests/backend/test_similarity_api.py:44`, `tests/backend/test_file_format_support.py:24`, `tests/backend/test_performance_benchmarks.py:22`, `tests/backend/test_playlist_integration.py:34`, `tests/backend/test_database_migrations.py:24`, `tests/backend/test_library_boundaries.py:25`, `tests/backend/test_string_input_boundaries.py:23`, `tests/backend/test_simplified_ui.py:25`, `tests/backend/test_streamlined_cache.py:17`
- **Status**: NEW (issue #4381 covers only the two playlist modules; the other nine are untracked)
- **Description**: Eleven modules set a module-level `pytestmark = pytest.mark.skip(...)` and are therefore never collected. The stated reasons are stale API-drift excuses ("Tests use old TrackRepository API", "APIs incompatible with current implementation", "LibraryManager.close() which doesn't exist"). Several of them are the *only* dedicated coverage for their subsystem — most notably `test_streamlined_cache.py` (the entire streamlined cache manager, which `config/startup.py` treats as a critical worker) and `test_error_handling.py` (backend error paths), plus `test_database_migrations.py` (the v15→v16 migration path known to break the suite).
- **Evidence**:
```python
# tests/backend/test_streamlined_cache.py:17
pytestmark = pytest.mark.skip(reason="Tests use APIs incompatible with current implementation. Requires refactoring.")
# tests/backend/test_error_handling.py:22
pytestmark = pytest.mark.skip(reason="Tests use old TrackRepository API - requires session_factory parameter")
# tests/backend/test_database_migrations.py:24
pytestmark = pytest.mark.skip(reason="Tests use LibraryManager.close() which doesn't exist. Requires refactoring to match current API.")
```
- **Impact**: `pytest tests/backend -q` reports these as skips, not failures, so CI and the release checklist stay green while the streamlined cache, backend error handling, DB migrations, file-format support and library boundary behaviour have *zero* executing assertions. A regression in any of those subsystems ships undetected. This is also the mechanism behind the known "tests/backend never goes fully green" baseline — the skipped modules mask which failures are real.
- **Siblings**: `tests/backend/test_migration_manager_fd_leak.py:34` uses `skipif` (conditional, legitimate — not part of this finding).
- **Suggested Fix**: Triage the eleven modules into "port to the current API" vs "delete as superseded"; for each one kept, replace the module-level skip with a tracking issue reference and a `xfail(strict=True)` so drift surfaces instead of hiding. Start with `test_streamlined_cache.py` and `test_error_handling.py` — those cover live, critical paths.


## LOW (21)

### BE1-06: ValueError→HTTP status mapping by substring sniffing returns 400 for service-unavailable conditions
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/player.py:490-500, 616-627, 653-664`
- **Status**: NEW
- **Description**: `set_queue` decides its status code by testing for the substring `"valid"` in the exception message. `QueueService.set_queue` raises `ValueError("Audio player not available")`, `ValueError("Player state manager not available")` and `ValueError("Library manager not available")` (`services/queue_service.py:334-338`) — none contain `"valid"` — so all three service-outage conditions are reported as **400 Bad Request** with the flattened detail `"Player not available"`, while every sibling endpoint in the same router maps the identical conditions to 503.
- **Evidence**:
```python
# player.py:496-497
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e) if "valid" in str(e) else "Player not available")
```
- **Impact**: The frontend's retry logic (which keys off status codes) treats a transient startup/outage state as a permanent client error and will not retry; the operator-facing detail is also lost.
- **Siblings**: Same substring-sniffing pattern at `player.py:623` (`400 if "Invalid" in str(e) else 503` — `"Failed to remove track"` falls through to 503) and `player.py:660` (`404 if "not found" in str(e).lower() else 503`). These two happen to land on the right codes today but are equally fragile to message rewording.
- **Suggested Fix**: Raise typed service exceptions (e.g. `ServiceUnavailableError` / `BadRequestError` from `routers/errors.py`) inside the service layer instead of bare `ValueError`, and drop the string inspection from the handlers.

### BE1-07: `enqueue-all` declares `limit: int` but defaults to `None`
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/fingerprint_queue.py:133-137`
- **Status**: NEW
- **Description**: The parameter is annotated `int` with a `Query(None, ge=1, le=10000, …)` default. Pydantic does not validate defaults, so the handler receives `None` when the parameter is omitted and forwards it to `repos.fingerprints.get_missing_fingerprints(limit=None)` (which is the intended "all" semantics) — but the annotation is a lie, mypy cannot catch a genuine `None` deref added later, and the generated OpenAPI schema advertises a non-nullable integer whose documented default is `null`.
- **Evidence**:
```python
async def enqueue_all_missing_fingerprints(
    limit: int = Query(None, ge=1, le=10000, description="Maximum tracks to enqueue (default: all)")
) -> dict[str, Any]:
```
- **Impact**: Type-checking and API-doc inaccuracy only; runtime behaviour is currently correct. Carried over verbatim from the pre-#4270 `similarity.py:545`, so this is pre-existing, not a split regression.
- **Siblings**: None — every other optional query parameter in the audited routers is annotated `X | None`.
- **Suggested Fix**: Change the annotation to `limit: int | None = Query(None, ge=1, le=10000, …)`.

### BE1-08: Fingerprint-queue enqueue called synchronously from an async handler in one of three call sites
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/fingerprint_status.py:104`
- **Status**: NEW
- **Description**: `GET /api/tracks/{track_id}/fingerprint` calls `queue.enqueue(track_id)` directly on the event loop, while the two other routers that perform the identical call offload it (`routers/similarity.py:141` and `routers/fingerprint_queue.py:126` both use `await asyncio.to_thread(queue.enqueue, track_id)`; the batch path in `fingerprint_queue.py:182-192` offloads the whole loop per #3335).
- **Evidence**:
```python
# fingerprint_status.py:104
queued = queue.enqueue(track_id)                       # sync, on the loop
# similarity.py:141 / fingerprint_queue.py:126
added = await asyncio.to_thread(queue.enqueue, track_id)
```
- **Impact**: `FingerprintQueue.enqueue` is a bounded in-memory push under a lock, so the stall is sub-millisecond in practice — the finding is consistency/robustness (a future implementation that touches the DB or filesystem inside `enqueue` would silently start blocking audio streaming from this one path).
- **Siblings**: `routers/library_scan.py:131` calls `fp_queue.enqueue(t.id)` in a comprehension over every newly-added track, on the loop, after the scan completes — same pattern, larger N.
- **Suggested Fix**: Wrap both call sites in `asyncio.to_thread` to match the other three.

### BE2-06: `manager.connect()` rejection is not propagated — the endpoint runs a full connection lifecycle on a never-accepted socket
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/ws_handlers/connection.py:33-62`, `auralis-web/backend/config/globals.py:72-106`
- **Status**: NEW
- **Description**:
  `ConnectionManager.connect()` performs the sole Origin/loopback check and, on rejection, calls
  `websocket.close(code=1008)` and **returns `None`** without ever calling `accept()`.
  `setup_connection` ignores the return value: it assigns a connection id, spawns the heartbeat
  background task, attempts two initial `send_text` pushes, and returns normally; `websocket_endpoint`
  then enters the receive loop and finally runs the whole `teardown_connection` sequence for a
  connection that was never established.
  This is **not** an auth bypass — the handshake is denied before `accept()`, so no client message
  can ever be exchanged, and the receive loop dies immediately with `RuntimeError` — but a rejected
  connection still costs a live `ws_heartbeat_*` task (up to one 30 s sleep before its first send
  fails), two swallowed exceptions, and a full teardown pass. It also means the security decision is
  invisible to the caller, so any future code added between `setup_connection` and the receive loop
  would run for rejected origins.
- **Evidence**:
```python
# config/globals.py:86-89 — rejection returns, does not raise
if origin not in ALLOWED_WS_ORIGINS:
    logger.warning(f"WebSocket connection rejected: untrusted origin {origin!r}")
    await websocket.close(code=1008)
    return
```
```python
# ws_handlers/connection.py:44-62 — result unchecked; heartbeat spawned regardless
await manager.connect(websocket)
connection_id = _ws_id(websocket)
heartbeat = HeartbeatManager(interval_seconds=30, timeout_seconds=10)
...
heartbeat_task = spawn_background_task(_heartbeat_loop(), name=f"ws_heartbeat_{connection_id}")
```
- **Impact**: Wasted task/teardown work per rejected connection and a latent hazard: the single
  authoritative origin check has no way to stop the handler. Desktop/localhost binding keeps the
  security impact at zero today (downgraded accordingly).
- **Siblings**: `setup_connection` is the only caller of `manager.connect`; no other handler consults
  its result.
- **Suggested Fix**: Make `ConnectionManager.connect` return `bool` (or raise `WebSocketException`),
  have `setup_connection` return early / re-raise on rejection, and have `websocket_endpoint` skip the
  receive loop and teardown when setup reports failure.

### BE2-07: `handle_seek` re-implements `_cancel_prior_task` and diverges from it in what per-connection state it clears
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:30-51, 232-257`
- **Status**: NEW
- **Description**:
  `_cancel_prior_task` (used by `handle_play_enhanced` and `handle_play_normal`) pops, under the lock,
  `active_tasks`, `active_track_ids`, `pause_events` **and** `flow_events` before cancelling.
  `handle_seek` open-codes the same sequence but pops only `active_tasks` — `active_track_ids`,
  `pause_events` and `flow_events` keep pointing at the superseded stream's objects for the whole
  cancel-and-await window, and are only replaced later at line 266-272. `handle_stop`
  (`playback_control.py:66-73`) is a third copy of the same idiom, with yet another (correct) subset.
  There is no functional bug today — the old task is cancelled, and the seek re-registers everything a
  few lines later — but three divergent copies of a lock-ordered state-teardown sequence is exactly
  the shape that produced #3828/#3522/#4364, and the divergence is invisible without diffing the three
  sites.
- **Evidence**:
```python
# _cancel_prior_task (playback_commands.py:36-42)
old_task = state.active_tasks.pop(ws_id, None)
state.active_track_ids.pop(ws_id, None)
state.pause_events.pop(ws_id, None)
state.flow_events.pop(ws_id, None)

# handle_seek (playback_commands.py:234-237) — only the task is popped
async with state.active_tasks_lock:
    for k in [k for k, v in state.active_tasks.items() if v.done()]:
        state.active_tasks.pop(k, None)
    old_task = state.active_tasks.pop(ws_id, None)
```
- **Impact**: Maintenance hazard only; a future change to the teardown contract will be applied to one
  or two of the three copies.
- **Siblings**: `ws_handlers/playback_control.py:66-73` (`handle_stop`) is the third copy;
  `ws_handlers/connection.py:168-187` (`teardown_connection`) is a fourth, lock-split variant.
- **Suggested Fix**: Have `handle_seek` and `handle_stop` call `_cancel_prior_task` (promoted to a
  shared helper in `ws_handlers/`), keeping the "pop under lock, cancel+await outside the lock"
  ordering that #3828 established.

### BE3-05: `cache/manager.py` re-derives `content_chunk_count()`'s formula instead of importing it
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/cache/manager.py:161-172`
- **Status**: NEW (adjacent to CLOSED #4025, which removed the redeclared *constants* but left the redeclared *formula*)
- **Description**: `chunk_boundaries.content_chunk_count()` is documented as the single source of truth for chunk counting. `StreamlinedCacheManager._calculate_total_chunks` imports `CHUNK_DURATION`/`CHUNK_INTERVAL` correctly but then reimplements the count by hand, including a local re-derivation of the overlap.
- **Evidence**:
  ```python
  # cache/manager.py:169-172
  import math
  overlap = CHUNK_DURATION - CHUNK_INTERVAL      # re-derives OVERLAP_DURATION
  return max(1, math.ceil((duration - overlap) / CHUNK_INTERVAL))
  ```
  vs. `core/chunk_boundaries.py:37`: `return max(1, int(np.ceil((total_duration - OVERLAP_DURATION) / CHUNK_INTERVAL)))`. Currently numerically identical (15 − 10 = 5 = `OVERLAP_DURATION`), so **no present-day impact**.
- **Impact**: None today. Drift hazard: if `CHUNK_DURATION` and `OVERLAP_DURATION` are ever decoupled (they are independent constants), the cache's completion target silently diverges from `ChunkedAudioProcessor.total_chunks` and tracks are reported as never fully cached.
- **Siblings**: `core/chunk_operations.py:346-368` (`calculate_total_chunks`) already does this correctly — it delegates to `content_chunk_count` — and is the pattern to copy.
- **Suggested Fix**: `from core.chunk_boundaries import content_chunk_count` and `return content_chunk_count(duration)`.

### BE3-06: `ChunkOperations.load_chunk_from_file` hardcodes the context window and ignores its own `overlap_duration` parameter
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:39-104` (specifically `:87`)
- **Status**: NEW (narrower and more specific than OPEN #4289, which is about `ChunkOperations` *defaults*; this is about a literal in the body plus a dead parameter)
- **Description**: The context window is a bare literal rather than `CONTEXT_DURATION`, and the `overlap_duration` parameter — which every caller dutifully passes as `OVERLAP_DURATION` (`chunked_processor.py:335-337`) — is never read in the function body.
- **Evidence**:
  ```python
  # core/chunk_operations.py:87
  context_duration = 5.0 if with_context else 0.0    # should be CONTEXT_DURATION
  ```
  `grep -n "overlap_duration" core/chunk_operations.py` shows it in the signature and docstring of `load_chunk_from_file` only — never in an expression. Verified currently harmless: `5.0 == CONTEXT_DURATION`, and the geometry it produces matches `ChunkBoundaryManager.get_chunk_boundaries` (`chunk_boundaries.py:91-102`) exactly, including the `max(0, …)` / `min(total_duration, …)` clamps.
- **Impact**: None today. If `CONTEXT_DURATION` is ever retuned, the *load* window and the *trim* window (`calculate_context_trim_samples`, which is derived from the boundary manager) desynchronise — and that desync is precisely the #3807 failure mode (wrong audio range emitted for edge chunks).
- **Siblings**: `ChunkOperations.extract_chunk_segment`, `calculate_total_chunks`, `get_chunk_time_range` all carry the same `chunk_duration=15 / chunk_interval=10 / overlap_duration=5` literal defaults (this is the OPEN #4289 surface); the `5.0` at `:87` is the one that is not merely a default but an unconditional literal in the execution path.
- **Suggested Fix**: `from core.chunk_boundaries import CONTEXT_DURATION` and use it at `:87`; either wire `overlap_duration` into the geometry or drop the parameter.

### BE4-04: `JobWorker.stop()` cancels in-flight job tasks but never awaits them
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/job_worker.py:97-132`
- **Status**: NEW
- **Description**: `stop()` iterates `self._tasks`, calls `task.cancel()` and immediately moves on to draining the queue
  and cancelling the loop task. Only `self._worker_task` is awaited (lines 125-130). The per-job `_run_job` tasks are never
  gathered, so `stop()` returns while their `finally:` blocks (task deregistration, semaphore release, and the
  `await self._engine.cleanup_old_jobs(...)` at line 95) may still be pending.
- **Evidence**: lines 106-113 cancel without collecting the tasks; the only `await` on a task is `await self._worker_task`
  at 128. Note `_run_job`'s `finally` itself contains an `await` (line 95), which will raise `CancelledError` again during
  cancellation unwinding and skip the cleanup entirely.
- **Impact**: On shutdown (and on `POST /api/library/reset`, which drives the same worker set via
  `config/background_workers.py`), the engine reports "worker stopped" while job tasks are still unwinding. Combined with
  BE4-01 this means an interrupted job's processor is dropped without `close()`. Bounded and shutdown-only, hence LOW.
- **Siblings**: `config/background_workers.py:35-56` (`stop_background_workers`) correctly `await`s each worker's `stop()`,
  so the fleet-level teardown is fine; the gap is only inside `JobWorker`.
- **Suggested Fix**: Collect the cancelled tasks and `await asyncio.gather(*tasks, return_exceptions=True)` before the
  "worker stopped" log, and wrap `_run_job`'s `finally` cleanup in a shielded/`try-except CancelledError` block so it
  completes during cancellation.

### BE4-05: `intensity` participates in the processor cache key but is not a processor parameter
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processor_factory.py:110-141, 175-275`; `core/audio_processing_pipeline.py:132-140, 236-253`
- **Status**: NEW
- **Description**: `ProcessorCacheKey` includes `intensity`, and `select_processor` forwards it into `get_or_create`, but
  the constructed `HybridProcessor` is never told about it — only `config.mastering_profile = preset.lower()` is applied
  (line 240). Intensity is realised purely as a post-hoc dry/wet blend in `apply_enhancement`
  (`processed = audio * (1.0 - intensity) + processed * intensity`, line 253), which operates on the processor's *output*.
- **Evidence**: `get_or_create` uses `intensity` only inside `_get_cache_key`; there is no other reference to it in the
  method body. Two calls differing only in `intensity` therefore build two byte-identical processors occupying two of the
  32 LRU slots.
- **Impact**: Cache dilution — an intensity slider sweep can evict genuinely distinct `(track, preset)` processors and
  force redundant 200-500 ms constructions (each of which also spins up a fresh 5-thread fingerprint executor). Purely a
  performance/footprint issue; audio output is unaffected because the blend is applied downstream regardless.
- **Siblings**: None — `ProcessorPool.cache_key` (`core/processor_pool.py:47-77`) correctly keys only on fields the
  processor actually consumes.
- **Suggested Fix**: Drop `intensity` from `ProcessorCacheKey` (keep `preset`, `config_hash`, `targets_hash`, `track_id`),
  or, if a future wire-up makes intensity a real DSP parameter, apply it to the processor at construction so the key is
  honest. The former is the safe change today.

### BE5-06: `DEFAULT_TRACK_FIELDS` documents itself as the response contract but is unreachable for real ORM objects
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/serializers.py:18-42, 93-126`
- **Status**: NEW
- **Description**:
  `serialize_object()` returns `obj.to_dict()` whenever the object has one and is not a Mock, and only
  falls through to `fallback_fields` otherwise. Every real `Track`/`Album`/`Artist`/`Playlist` has
  `to_dict()`, so `DEFAULT_TRACK_FIELDS` and friends only ever apply to Mock objects in tests. Yet the
  dict is annotated as the authoritative contract — *"Core identity (always required by
  TrackApiResponse)"*, *"fixes #2267 — frontend requires artist/album"*, *"#2851 — required for album
  track ordering and favorite status"* — and lists keys (`filepath`, `artist`, `genre`, `date_added`,
  `date_modified`, `loudness`) that `Track.to_dict()` never produces.
- **Evidence**:
  ```python
  if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict', None)):
      obj_type_name = type(obj).__name__
      if 'Mock' not in obj_type_name and 'MagicMock' not in obj_type_name:
          result = obj.to_dict()
          if isinstance(result, dict):
              return result      # <- always taken for real ORM rows
  ```
- **Impact**:
  Documentation debt that actively misleads: it is the most natural place to look for "what does the
  track endpoint return", and it is wrong. It is also why BE5-01/BE5-02 went unnoticed — the fallback dict
  looks like a guarantee. Tests that construct Mocks exercise a shape production never emits, so they
  cannot catch the divergence.
- **Siblings**:
  `DEFAULT_ALBUM_FIELDS`, `DEFAULT_ARTIST_FIELDS`, `DEFAULT_PLAYLIST_FIELDS` are equally unreachable.
- **Suggested Fix**:
  Either make the fallback authoritative (project `to_dict()` output through the field map so the response
  shape is identical on both paths), or relabel the dicts as test-only Mock defaults and move the real
  contract into a Pydantic response model — which is also what #3838 would give these endpoints.

### BE5-07: `serialize_album_detail` maps a `genre` key that `Album.to_dict()` never produces
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/serializers.py:237`, `auralis/library/models/core.py:208-224`
- **Status**: NEW
- **Description**:
  `serialize_album_detail` builds its camelCase output with `'genre': snake.get('genre')`. `Album.to_dict()`
  emits no `genre` key (genre lives on `Track` via the `track_genre` association, and `Album` has no genre
  column), so `GET /api/albums/{id}` always returns `genre: null`. The frontend `Album` domain type
  (`types/domain.ts:67`) declares `genre?: string`, so a consumer would reasonably expect it to be
  populated sometimes.
- **Evidence**:
  `Album.to_dict()` keys: `id, title, artist_id, year, total_tracks, total_discs, artwork_url,
  avg_dr_rating, avg_lufs, mastering_consistency, artist, track_count, total_duration, created_at,
  updated_at`. No `genre`.
- **Impact**:
  A permanently-null field in the response — harmless at runtime (the TS type is optional) but it
  advertises a capability the data model does not have, and it will read as "genre lookup is broken"
  rather than "albums have no genre" to whoever debugs it next.
- **Siblings**:
  `DEFAULT_ALBUM_FIELDS` (`serializers.py:44-52`) does not list `genre` either, confirming the key was
  never sourced from anywhere.
- **Suggested Fix**:
  Drop the `genre` key from `serialize_album_detail`, or derive it (e.g. the modal genre across
  `album.tracks`) if album genre is actually wanted. Same for `dateAdded`, which resolves via the
  `snake.get('date_added') or snake.get('created_at')` fallback — that one works, but only by accident of
  the `or`.

### BE5-08: Enhancement response models type `preset` as free-form `str` while the shared literal and the frontend union are strict
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/enhancement.py:76-86`, `auralis-web/backend/schemas.py:27-28`, `auralis-web/backend/player_state.py:86`, `auralis-web/frontend/src/types/ws/enhancement.ts:22-29`
- **Status**: NEW
- **Description**:
  `EnhancementPresetLiteral` was introduced (#4424) as the single source of truth and is correctly used on
  the **request** side (`SetPresetRequest.preset`, `SettingsUpdateRequest.default_preset`). The
  **response** side was not migrated: `EnhancementSettings.preset: str` (the `response_model` for
  `GET /api/player/enhancement/status` and, nested, for all three mutation endpoints) and
  `PlayerState.current_preset: str` are both untyped strings. The frontend
  `EnhancementSettingsChangedMessage.data.preset` is the strict union
  `'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy'`, and `AudioStreamStartMessage.data.preset` is
  typed `EnhancementPreset`.
- **Evidence**:
  ```python
  class EnhancementSettings(BaseModel):
      enabled: bool
      preset: str        # <- not EnhancementPresetLiteral
      intensity: float   # <- no ge=0.0, le=1.0 either
  ```
  vs `schemas.py:28`: `EnhancementPresetLiteral = Literal["adaptive", "gentle", "warm", "bright", "punchy"]`.
- **Impact**:
  The one-way constraint means the runtime `enhancement_settings` dict is the only thing keeping the
  response in the union — if any code path ever writes a non-canonical preset (e.g. a capitalised value,
  or a profile name from the mastering engine), it will be serialized straight through to a frontend that
  narrows on the literal union, and the enhancement UI will fall out of its switch. The response model is
  also what drives OpenAPI, so the docs advertise a free-form string for a closed enum.
- **Siblings**:
  `EnhancementSettings.intensity: float` has no `ge=0.0/le=1.0` despite the request-side validator
  clamping to that range; `player_state.PlayerState.repeat_mode: str` is likewise a bare `str` with the
  allowed values only in a comment, while `RepeatModeRequest.mode` (`player.py:111`) correctly uses
  `Literal["off", "all", "one"]`. (`JobStatusResponse.status: str` is the same pattern and is already
  open as **#3896** — not re-reported.)
- **Suggested Fix**:
  Change `EnhancementSettings.preset` to `EnhancementPresetLiteral`, add
  `intensity: float = Field(ge=0.0, le=1.0)`, and change `PlayerState.current_preset` /
  `repeat_mode` to the corresponding `Literal`s. All are non-breaking for well-behaved data and turn a
  silent frontend break into a backend 500 at the serialization boundary.

### BE5-09: Two different `volume` scales share the field name across the settings and player contracts
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/settings.py:69,109`, `auralis-web/backend/routers/player.py:94-101`, `auralis-web/backend/player_state.py:68`
- **Status**: NEW
- **Description**:
  `SettingsUpdateRequest.volume` is constrained to `ge=0.0, le=1.0` (a 0–1 float scale).
  `SetVolumeRequest.volume` clamps to `0.0–100.0`, and `PlayerState.volume: int = 80` is the 0–100 integer
  scale. Same field name, same API surface, two incompatible scales, and neither model's docstring or
  `description=` states which one applies — the only marker is the `le=1.0` bound on one side and a
  parenthetical in a class docstring on the other.
- **Evidence**:
  ```python
  # settings.py:69
  volume: float | None = Field(default=None, ge=0.0, le=1.0)
  # player.py:94-101
  class SetVolumeRequest(BaseModel):
      """Request model for volume control (0–100)."""
      volume: float
      @field_validator('volume')
      def clamp_volume(cls, v: float) -> float:
          return max(0.0, min(100.0, v))
  ```
  The player side of this is well-handled at runtime: `usePlaybackControl.ts:305-310` scales 0–1 → 0–100
  before POSTing, and `usePlayerStateSync.ts:218-222` treats the broadcast as 0–100. So the **player**
  path is internally consistent; the hazard is that the settings path uses the other scale under the same
  name, and `SettingsResponse.volume` (`settings.py:109`) is an unconstrained `float | None` that carries
  it back out.
- **Impact**:
  Latent rather than active: a persisted `settings.volume` of `0.8` and a live player volume of `80`
  are the same loudness expressed two ways, and any code that restores settings volume into the player
  (or vice versa) without a ×100 will be wrong by two orders of magnitude. The `le=1.0` bound means the
  0–100 value would 422 in one direction, which is at least loud; the reverse direction (0.8 → 0.8% volume)
  is silent.
- **Siblings**:
  Partially adjacent to open **#3894** ("`api.ts` `PlayerVolumeRequest.volume` says 0.0-1.0 while backend
  uses 0-100") — that issue is about the TS request type's comment. This finding is about the two
  **backend** models disagreeing with each other, which #3894 does not cover.
- **Suggested Fix**:
  Normalise on one scale (0–100 integer, matching `PlayerState` and the WS broadcast) and add explicit
  `description="0-100"` / `description="0.0-1.0"` to both `Field`s so the OpenAPI schema documents the
  scale rather than leaving it to a bound. If the persisted scale must stay 0–1, rename it
  `volume_normalized` so the two are not confusable.

### BE6-04: CSP `connect-src` allows only `localhost`, while CORS and the WS allowlist deliberately allow `127.0.0.1` too
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware.py:80-88`
- **Status**: NEW
- **Description**: #3539 established the contract that both host spellings must be accepted because browsers treat them as distinct origins — `cors_allowed_origins()` (`middleware.py:202-206`) and `build_ws_origins()` (`config/globals.py:38-48`) both iterate `("localhost", "127.0.0.1")`. The hardcoded CSP string does not: `connect-src 'self' ws://localhost:* http://localhost:*` has no `127.0.0.1` form.
- **Evidence**:
```python
"connect-src 'self' ws://localhost:* http://localhost:*; "
```
  vs. the two allowlist builders that were explicitly fixed to cover both spellings.
- **Impact**: A page served by the backend and opened via `http://127.0.0.1:8765` relies on CSP3's `'self'` matching same-host `ws://` — behaviour that is not uniform across engines and breaks entirely for a cross-port dev connection reached via the IP form. Effect is a hard WebSocket failure (no audio) for a user who navigates by IP, with only a console CSP violation to explain it.
- **Siblings**: None — the other two allowlists are correct; only the CSP literal drifted.
- **Suggested Fix**: Build the CSP `connect-src` list from the same host × port matrix used by `cors_allowed_origins()` instead of hardcoding, or at minimum add `ws://127.0.0.1:* http://127.0.0.1:*`.

### BE6-05: Frontend-not-found fallback page echoes the absolute install path into the HTTP response
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/main.py:190-206`
- **Status**: NEW
- **Description**: #4366 demoted the absolute frontend path from INFO to DEBUG logging precisely because it embeds the OS username and install layout and lands in the user-shareable electron-log. The same string is still interpolated into the fallback HTML body served at `/`. It is HTML-escaped (no XSS), but the disclosure that motivated #4366 is unchanged for anyone who screenshots or pastes that page into a bug report.
- **Evidence**:
```python
logger.debug(f"Frontend not found at: {frontend_path}")   # demoted by #4366
@app.get("/")
async def root() -> HTMLResponse:
    return HTMLResponse(f"""... <p>Frontend not found at: {html_module.escape(str(frontend_path))}</p> ...""")
```
- **Impact**: Path/username disclosure in a page users are likely to screenshot when reporting a broken install. Localhost-only, so no remote exposure.
- **Siblings**: None — the DEBUG-level logs at `main.py:163,192` and `config/startup.py:207,212` already follow the #4366 convention.
- **Suggested Fix**: Drop the interpolated path from the HTML body and point users at the log instead ("see the backend log for the search path"), keeping the DEBUG log line as the diagnostic channel.

### BE6-06: Startup temp sweep unconditionally deletes every `auralis_stream_*` dir in the system temp root
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/startup.py:124-143,176-186`
- **Status**: NEW
- **Description**: `reclaim_leftover_stream_temps` globs `auralis_stream_*` across the whole system temp directory and `rmtree`s each match with no age check and no PID/ownership check. Same for the `auralis_chunks` directory wipe immediately above it. Both assume exactly one backend process ever exists.
- **Evidence**:
```python
for leftover in temp_root.glob("auralis_stream_*"):
    shutil.rmtree(leftover)
```
- **Impact**: A second backend starting up (developer running `main.py --dev` on an alternate port while the packaged Electron app is open, or a test run against the real temp root) deletes the *live* temp WAVs and cached chunks of the running instance, producing mid-playback file-not-found errors in the other process. Bounded in practice because the default port binding usually prevents a second instance.
- **Siblings**: The `auralis_chunks` wipe at `config/startup.py:176-183` has the identical single-instance assumption.
- **Suggested Fix**: Only reclaim directories older than a threshold (e.g. mtime > 1h) or tag temp dir names with the owning PID and skip live PIDs.

### BE7-04: `routers/library_scan.py` and `routers/fingerprint_queue.py` emit ad-hoc `{"error": ...}` payload shapes instead of the shared `routers/errors.py` classes
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/library_scan.py:181,195`; `auralis-web/backend/routers/fingerprint_queue.py:86`
- **Status**: NEW
- **Description**: 15 of the 20 registered routers import from `routers/errors.py` and raise the shared `NotFoundError` / `BadRequestError` / `ServiceUnavailableError` / `InternalServerError` classes, producing a uniform `{"detail": "..."}` body. A handful of sites instead return a 200 response carrying an embedded `{"error": ...}` key: the scan-timeout and scan-exception branches in `library_scan.py` (`"data": {"error": f"library scan timed out after {int(scan_timeout)}s"}` and `"data": {"error": f"{type(e).__name__} during library scan"}`) and `fingerprint_queue.py:86` (`"error": "internal_error"`).
- **Evidence**: the two shapes coexist; `grep` for `'"error":'` across `routers/` returns exactly these three plus the four WS-frame builders in `system.py` (which are WebSocket `audio_stream_error` frames, a deliberately different contract and correct there).
- **Impact**: Cosmetic/contractual only. The frontend must special-case "HTTP 200 that actually means failure" for these two endpoints; a caller checking only `response.ok` treats a timed-out scan as success. No resource leak, no wrong audio. Note the scan branches are *deliberate* (they broadcast progress-style payloads over the same shape as success), so this is a design inconsistency rather than an oversight — flagging for contract uniformity, not urgency.
- **Siblings**: The three sites above; no others.
- **Suggested Fix**: Either raise `ServiceUnavailableError`/`InternalServerError` from these branches, or — if the 200-with-embedded-error shape is intentional for the scan progress contract — add an explicit `status: "error"` discriminant to the Pydantic response model so the frontend has a typed field to branch on rather than sniffing for an `error` key.

### BE8-05: `config/globals.py` instantiates a second, unused `ConnectionManager` at import time
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/backend/config/globals.py:155-191`
- **Status**: NEW
- **Description**: `create_globals_dict()` has no callers other than the module-level `globals_dict = create_globals_dict()` on the last line, which runs at import and constructs a `ConnectionManager()` (with its own `asyncio.Lock` and empty connection list) that no code ever registers a socket against. The live manager is the one built at `main.py:96`.
- **Evidence**:
```python
def create_globals_dict() -> dict[str, Any]:
    return { ..., 'manager': ConnectionManager() }
globals_dict = create_globals_dict()     # only caller; result only read by the dead path in BE8-01
```
  `grep -rn "create_globals_dict" auralis-web/backend tests` → the definition and this one call site.
- **Impact**: Negligible runtime cost, but it is the object that makes BE8-01's bug invisible: the dead dict *looks* like a populated registry to a reader, and `.get()` on it silently returns `None` rather than raising. Removing it converts BE8-01's failure mode from silent to loud.
- **Siblings**: None.
- **Suggested Fix**: Delete `create_globals_dict()` and the module-level `globals_dict` once BE8-01 is fixed by consolidating on a single registry object.

### BE9-02: `POST /api/library/refresh-references` is the only route with no test reference at all
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/routers/library.py:63-66`
- **Status**: NEW
- **Description**: A pattern sweep of all 98 registered endpoint paths against the whole `tests/` tree found exactly one path that never appears: `/api/library/refresh-references`. The handler rebuilds the entire mastering reference cloud (clears every `is_reference` flag, rescores every fingerprint), and its shared closure `_refresh_reference_cloud` is also wired as the scanner end-of-run hook and the fingerprint-queue drain hook (`config/startup.py:302-322`).
- **Evidence**:
```python
@router.post("/api/library/refresh-references")
@with_error_handling("refresh reference cloud")
async def refresh_reference_cloud() -> dict[str, Any]:
```
  `grep -rn "refresh-references" tests/` → no matches. It also has no frontend caller (`grep -rn "refresh-references" auralis-web/frontend/src` → no matches), so it is reachable only by direct API call.
- **Impact**: A destructive-ish, library-wide reclassification endpoint with three call paths (REST, scanner hook, queue drain hook) has no regression test. A change to `refresh_cloud()`'s signature or semantics would break all three silently — and the two hook call sites swallow exceptions (`logger.warning` only), so failure is invisible.
- **Siblings**: None — every other endpoint has at least one path reference in tests.
- **Suggested Fix**: Add a repo-backed test that seeds fingerprints, calls the endpoint, and asserts the cleared/selected counts, plus one asserting the scanner/queue hooks invoke the same closure.

### BE9-03: `test_similarity_api.py` is a skipped predecessor of `test_similarity_api_new.py` — a "_new" variant pair
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_similarity_api.py:44`, `tests/backend/test_similarity_api_new.py`
- **Status**: NEW
- **Description**: The live similarity coverage lives in `test_similarity_api_new.py` (39 tests across all three routers of the #4270 split). The original `test_similarity_api.py` remains in the tree, hard-skipped. This is the exact "No variants" anti-pattern the project principles forbid (`CLAUDE.md`: *No "Enhanced"/"V2"/"Advanced" copies. Refactor in-place*), applied to tests.
- **Evidence**: two sibling files covering the same router family, one permanently skipped, distinguished only by a `_new` suffix.
- **Impact**: A contributor grepping for similarity tests finds the dead file first (alphabetically and by the more obvious name), reads stale expectations, and may extend the skipped module. Maintenance cost only — no runtime impact.
- **Siblings**: `tests/backend/test_playlist_operations.py` / `test_playlist_integration.py` are a similar dead pair (both skipped, both covering playlists) — tracked by #4381.
- **Suggested Fix**: Delete `tests/backend/test_similarity_api.py` and rename `test_similarity_api_new.py` to `test_similarity_api.py`, porting any unique cases from the dead file first.

### BE9-04: No test asserts the three split similarity routers do not collide on the shared `/api/similarity` prefix
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/backend/config/routes.py:239-258`, `auralis-web/backend/routers/similarity.py`, `similarity_graph.py`, `fingerprint_queue.py`
- **Status**: NEW
- **Description**: #4270 split one router into three that are all mounted under the same `/api/similarity` prefix in a single `try/except`. `test_similarity_api_new.py` mounts each router *individually* into its own test app, so it verifies each router's routes in isolation but never verifies the composed application: no test asserts that the three route tables are disjoint, nor that a failure importing one of the three doesn't silently drop the other two (they share one `try/except` — a single ImportError skips all three registrations and only emits `logger.warning`).
- **Evidence**:
```python
if HAS_SIMILARITY:
    try:
        from routers.similarity import create_similarity_router
        from routers.similarity_graph import create_similarity_graph_router
        from routers.fingerprint_queue import create_fingerprint_queue_router
        app.include_router(create_similarity_router(...))
        app.include_router(create_similarity_graph_router(...))
        app.include_router(create_fingerprint_queue_router(...))
    except Exception as e:
        logger.warning(f"⚠️  Failed to register similarity router family: {e}", exc_info=True)
```
  Test side: `router = create_similarity_graph_router(...)` then a fresh `FastAPI()` per class — never the real composed app.
- **Impact**: A future path added to one of the three that shadows another (e.g. a `/graph/{name}` catching `/graph/stats`) would pass all existing tests and only fail at runtime. Likewise a broken transitive import in any one module silently removes 11 endpoints with a warning nobody reads.
- **Siblings**: The same all-or-nothing `try/except` shape guards `processing_api` (`config/routes.py:77-89`) and `cache_streamlined` (`config/routes.py:222-233`), but those register a single router each so the blast radius is smaller.
- **Suggested Fix**: Add one test that builds the real app via `setup_routers()` and asserts the expected set of `/api/similarity/*` paths is present and unique; assert on `app.routes` rather than per-router mounts.

## Relationships

**R1 — The chunk-geometry contract is the single root cause of the seek cluster.**
`BE2-01`, `BE2-02` and `BE2-03` all trace to one undocumented invariant: `ChunkOperations.extract_chunk_segment` (`auralis-web/backend/core/chunk_operations.py:226-234`) drops `OVERLAP_DURATION` from the head of every chunk `N ≥ 1`, so the *emitted* timeline is not `N * CHUNK_INTERVAL`. Dimension 3 rediscovered the same defect independently from the chunk side (reported there as BE3-01, removed here as a same-file:line duplicate of BE2-01) — two agents converging on the same lines from opposite directions. `BE3-06` (`load_chunk_from_file` hardcoding the context window) is the same class of "geometry constant restated locally instead of imported". Fixing the seek math without also fixing `BE2-03`'s missing stream epoch leaves audible pre-seek audio at the head of every seek, so they should ship together.

**R2 — Two independent globals registries.**
`main.py:97` builds a `globals_dict` literal and `config/startup.py` populates it; `config/globals.py:191` builds a *second* one at import time that nothing populates. `BE8-01` (HIGH — Tier-1 fingerprint lookup permanently dead, regression of #3836) is caused by reading the wrong one; `BE8-05` (LOW — a stray unused `ConnectionManager`) is the same object seen from the other side. Deleting `create_globals_dict()` and consolidating on one registry fixes both and makes any future misresolution loud instead of silent.

**R3 — "Lock held across slow work" appears at three independent sites.**
`BE4-02` (`ProcessorFactory.get_or_create`, `threading.RLock` across a 200-500 ms `HybridProcessor.__init__`), `BE8-03` (`ProcessorPool.get_or_create`, `asyncio.Lock` across the same construction), and `BE8-02` (`PlaybackService._playback_lock` across an untimed `ConnectionManager.broadcast`). The first two are throughput serialization; the third can hang play/pause/stop/seek indefinitely because the per-client `send_text` has no timeout. `core/streamlined_worker.py:324` is a fourth instance of the same shape. One shared remedy — release the lock around the slow call and re-check on re-entry — applies to all four.

**R4 — Cache correctness assumptions that only hold because a path is unreachable.**
`BE3-02` (chunk cache not keyed on mastering targets), `BE3-03` (disk-cache hit skips `LevelManager` recording), `BE8-01` (Tier-1 lookup dead) and `BE7-01` (non-atomic cache WAV writes) interact: because `BE8-01` keeps mastering targets from ever being loaded from the DB, `BE3-02`'s missing cache-key component is currently masked. Fixing `BE8-01` alone will *expose* `BE3-02` as a live stale-cache bug. They must be fixed in that order, or together.

**R5 — Backend↔frontend contract drift has one mechanical cause: no generated types.**
`BE5-01` (camelCase read from a snake_case endpoint), `BE5-02` (six fields the TS `Track` type requires that `to_dict()` never emits), `BE5-03` (same entity, two casings from sibling endpoints), `BE5-04` (WS registry drift both ways), `BE1-05` (two playlist routes the frontend calls that don't exist) and `BE5-09` (two incompatible `volume` scales under one field name) are all instances of hand-maintained parallel type definitions. #3838's `response_model=` gap is the enabling condition — without declared response models there is nothing to generate from.

**R6 — Startup/shutdown symmetry has two independent holes.**
`BE6-01` (unguarded worker stops abort the rest of shutdown, skipping the WAL checkpoint), `BE6-02` (similarity auto-fit on an untracked daemon thread nobody joins), `BE4-04` (`JobWorker.stop()` cancels but never awaits) and `BE4-01` (processor never returned on the generic-exception path). All four are "a resource with a start but a conditional stop"; `config/background_workers.py` already has the correct per-worker-guarded pattern that `config/startup.py` re-implements without the guards.

## Prioritized Fix Order

**Tier 1 — fix first (user-visible, every session)**

1. **BE2-01 + BE2-02 + BE2-03** — seek correctness on both streaming paths, plus the stream-epoch discard boundary. Every seek in the app is currently wrong in one direction or the other, and every WebSocket reconnect re-plays up to 15 s. Fix as one change against `core/chunk_boundaries.py` constants, with unit tests asserting the delivered first-sample time equals the requested position for `P ∈ {0, 5, 12, 27, 33}`.
2. **BE8-01** — regression of the CLOSED #3836. A one-line-class bug (wrong globals dict) that silently reverted a shipped performance fix; costs a full fingerprint re-derivation on every play and every preset switch. Cheap to fix, and it is a *closed issue that is not actually fixed* — the highest-signal finding for process reasons alone.
3. **BE1-01** — `POST /api/metadata/batch` mass-assignment into arbitrary `Track` ORM columns including the primary key. Localhost-only, but the blast radius is library-DB corruption with no user-visible error.

**Tier 2 — fix before next release**

4. **BE8-02** — `_playback_lock` held across an untimed WebSocket broadcast. Add a `wait_for` timeout to the per-client `send_text` and move the broadcast outside the lock; a stalled renderer currently freezes all transport controls with no recovery.
5. **BE4-01** — processor leaked on `process_job`'s generic-exception path. Compounds across failed jobs at ~200 MB each.
6. **BE6-01** — guard each lifespan shutdown step independently (reuse `stop_background_workers`) so a failing worker can't skip the SQLite WAL checkpoint.
7. **BE7-01** — write cache WAVs to a temp path and `os.replace` into place, so a crash mid-write can't leave a truncated file at the canonical cache path.
8. **BE5-01** — album-detail track rows: pick one casing and fix the side that's wrong. Currently a visibly blank artist column.
9. **BE2-04** — wrap the two synchronous repository calls in the streaming path (`stream_fingerprint.py:148`, `stream_prefetch.py:54`) in `asyncio.to_thread`; they block the entire event loop at every enhanced-stream start.

**Tier 3 — same sprint, grouped by shared remedy**

10. **BE3-02 + BE3-03** — chunk cache keying and `LevelManager` bookkeeping on the cache-hit path. Must land with or after BE8-01 (see R4).
11. **BE4-02 + BE8-03 + BE8-05** — the lock-across-construction pattern and the duplicate globals registry (see R2, R3).
12. **BE1-03 + BE1-02 + BE1-04** — router hardening: `None`-getter → 503 not 500, `to_thread` the 500 MB upload write, bound and evict `_recommendation_cache`.
13. **BE7-02 + BE7-03** — `aiohttp` `ClientTimeout` and the over-broad `except → return False` in the artwork downloader.
14. **BE3-04** — NaN/Inf validation on DSP *output* (`np.clip` passes NaN through). Cheap, and the only remaining audio-integrity gap in the chunk path.
15. **BE5-02 … BE5-05, BE4-03, BE6-02, BE6-03, BE9-01** — contract drift, seek preset inversion, lifecycle and test-liveness items.

**Tier 4 — opportunistic**

16. All 21 LOW findings. The highest-leverage of these are **BE9-01**'s companions (**BE9-03**, **BE9-04**) and **BE2-07** (three divergent copies of the WS teardown sequence) — both are the shape that produced past regressions rather than active bugs.

## Audit Provenance

- Dimension outputs: 9/9 completed (Route Handlers, WebSocket Streaming, Chunked Processing, Processing Engine, Schema Consistency, Middleware & Config, Error Handling, Performance, Test Coverage).
- Cross-dimension deduplication removed 1 finding: `BE3-01` (position→chunk-index mapping) is the same `core/stream_seek.py:145-155` defect as `BE2-01`, found independently by Dimension 3.
- Findings matching an OPEN issue were omitted rather than re-reported. Notable confirmations of still-open issues (not counted above): #3838 (`response_model=` coverage), #3900 (CSP `unsafe-inline`), #3901 (rate-limit magic numbers), #3867 (serial broadcast), #3870 (unguarded heartbeat send), #3884 (`proactive_buffer` dead), #3914, #4359, #4370, #4381, #4431, #3774/#3780, #3873, #3909, #4289.
- One CLOSED issue was found regressed: **#3836** (see BE8-01).

Next step:

```
/audit-publish docs/audits/AUDIT_BACKEND_2026-07-25.md
```


## Appendix A — Verified Clean / Disproved / Dedup Notes

Consolidated from the nine dimension reports. These are checks that were performed and came back clean, candidate findings that were investigated and disproved, and already-tracked issues that were confirmed still present. They are recorded so a future audit does not re-litigate them.

### From dim_1.md

#### Deduplicated (verified present, reported elsewhere — NOT counted above)

- **Missing `response_model=`** on `routers/tracks.py` (6 routes), `routers/playlists.py` (8), `routers/metadata.py` (4), `routers/library.py` (3), `routers/files.py` (2), `routers/cache_streamlined.py` (3), `routers/fingerprint_status.py` (2), `routers/fingerprint_queue.py` (4), `routers/similarity_graph.py` (2 of 3), `routers/enhancement.py` (1) — **Existing: #3838**.
- **Module-level shared `APIRouter`** in `player.py:49`, `enhancement.py:37`, `artwork.py:31`, `library.py:38`, `files.py:82`, `playlists.py:32`, `system.py:47` (factories mutate a module-global router) — **Existing: #4361**.
- **Path `int` params without `Path(..., ge=1)`** across albums/artists/playlists/tracks/metadata/artwork (`-1`/`0` reach the repository layer) — **Existing: #3893**.
- **Three coexisting pagination response shapes**, `schemas.PaginatedResponse` dead — **Existing: #3892**.
- **Duplicate `CacheStatsResponse`/`TrackCacheStatus`** typed in `schemas.py` vs `dict[str, Any]` in `cache_streamlined.py` — **Existing: #3891**.
- **`presets` payload mixes camelCase into a snake_case response** (`processing_api.py:432,443-447`) — **Existing: #3895**.
- **`QueueStatusResponse` declares `cancelled`/`total` the engine never populates** — **Existing: #3886**.
- **`JobStatusResponse.status: str` should be a `Literal`/enum** — **Existing: #3896**.
- **`/tracks/{id}/fingerprint` emits `loudness_variation_std` while the FE type expects `loudness_variation`** (`fingerprint_status.py:157`) — **Existing: #4429**.
- **`routers/library.py:332` `except Exception: pass` for lyrics-tag parsing** — the code moved to `routers/tracks.py:182-183` and now logs the exception; **#3914 is stale, not a live finding**.

#### Disproved (investigated, not reported)

- **#4270 similarity split regression** — diffed the three new routers against `git show 74f6dfc1^:…/similarity.py`: all 11 paths, all `Query` bounds, all `response_model`s and the `#3331` redaction helper are byte-equivalent in behaviour; the three routers share the `/api/similarity` prefix but have zero overlapping path patterns (`/tracks/*`, `/fit` vs `/graph*` vs `/fingerprint-queue*`, `/fingerprint-stats`), and `functools.wraps` preserves `__wrapped__` so FastAPI still introspects the real signatures through the decorator.
- **Route-ordering conflicts** — `/api/player/queue/history` (GET/POST/DELETE) is registered before `/api/player/queue/{index}` (DELETE) with an explanatory comment; `/api/library/tracks/favorites` precedes `/api/library/tracks/{track_id}`; `/api/processing/jobs/cleanup` (DELETE) does not collide with `/api/processing/jobs` (GET). No misordered literal-vs-parameterized pair found.
- **DELETE idempotency** — `DELETE /api/albums/{id}/artwork` is explicitly idempotent (#3563); `PlaylistRepository.clear()` and `remove_track()` return `True` for already-empty/already-removed states (`playlist_repository.py:426-503`), so the playlist DELETE routes are idempotent in practice. Only `DELETE /api/playlists/{id}` 404s on repeat, which is conventional.
- **`cache_streamlined` awaiting sync methods** — confirmed `StreamlinedCacheManager.clear_track`/`clear_all` are `async def` (`cache/manager.py:548,574`) and `get_stats`/`get_track_cache_status` are sync and correctly wrapped in `asyncio.to_thread`.
- **Artwork path traversal** — `routers/artwork.py:164-190` resolves and `is_relative_to`-checks against `~/.auralis/artwork` **before** the existence check; thumbnail sizes are bounded (`ge=16, le=2048`) and snapped to 5 buckets, so the on-disk thumbnail cache cannot be inflated by arbitrary sizes.

### From dim_2.md

#### Dedup notes
Checked against `/tmp/audit/backend/issues.json` (159 OPEN issues) plus `.claude/issues/*/ISSUE.md`.
Deliberately **omitted** as already-open matches:
- **#4431** — `audio_stream_start.total_duration` divergence between enhanced and normal seek paths
  (still present at `stream_normal.py:206` vs `stream_seek.py:173`).
- **#3774 / #3780** — `audio_chunk_meta.seq` emitted but never validated / `seq` vs `sequence` naming.
  BE2-03 is reported separately because its consequence (stale audio after seek) is not described
  there, but the two share a fix.
- **#3873** — `WebSocketMessageType` enum contract. Note for the record: the enum still admits 8
  outbound-only types (`seek_started`, `job_progress`, `audio_stream_error`, `playback_paused`,
  `playback_resumed`, `playback_stopped`, `player_state`, `enhancement_settings_changed`) that
  `dispatch_message` answers with `unknown_message_type`.
- **#3884** — `proactive_buffer.buffer_presets_for_track` is dead (confirmed still dead).
- **#3867** — serial `ConnectionManager.broadcast`.
- **#3870** — heartbeat `send_text` not guarded by a connection check.
- **#3909** — seek-path outer handler omits `error_code="SEEK_ERROR"` (confirmed still true at
  `stream_seek.py:293`).
- **#3885**, **#3878**, **#3880**, **#4289** — chunk/level bookkeeping items outside this dimension's
  new findings.

---

#### Scan completeness

All assigned files were read in full: `core/audio_stream_controller.py`; `ws_handlers/{connection,
context,messages,playback_commands,playback_control}.py`; `websocket/{websocket_protocol,
websocket_security}.py`; `core/{stream_enhanced,stream_normal,stream_seek,stream_prefetch,
stream_protocol,stream_messages,stream_chunk_ops,stream_fingerprint,proactive_buffer}.py`;
`encoding/wav_encoder.py` and `core/encoding/wav_encoder.py` (both, in full);
`routers/system.py`. Supporting reads for verification: `core/chunk_boundaries.py`,
`core/chunk_operations.py`, `core/chunked_processor.py` (chunk emission geometry),
`config/globals.py` (`ConnectionManager`), `helpers.py` (`spawn_background_task`), `schemas.py`
(`WebSocketMessageType`, `WebSocketMessageBase`), and
`auralis/library/repositories/fingerprint_repository.py`. Frontend counterparts:
`contexts/WebSocketContext.tsx`, `hooks/websocket/websocketConnectionCore.ts`,
`hooks/enhancement/{useAudioStreamingCore,useEnhancedStreamStart,useEnhancedSeek,
useEnhancementControl}.ts`, `utils/audio/pcmDecoding.ts`, `types/ws/streaming.ts`,
`store/slices/playerSlice.ts`.

Two further checks completed after the initial pass, both **clean**:
- **No lock held across an `await`** anywhere in the WS scope. `_chunk_tails_lock`
  (`stream_chunk_ops.stream_processed_chunk:217-234`) wraps only synchronous NumPy work, with the
  chunk send outside it; `active_tasks_lock` never wraps the `await old_task` in
  `_cancel_prior_task` / `handle_seek` / `handle_stop` / `teardown_connection`;
  `ConnectionManager._lock` snapshots the connection list and sends outside; the rate limiter's
  `threading.Lock` contains no awaits.
- **The two `wav_encoder.py` modules are confirmed non-duplicates** after reading both in full:
  `core/encoding/wav_encoder.py` is the versioned chunk-file writer (`CACHE_VERSION`, `PCM_16`
  default, NaN/Inf validation, `cleanup_track_chunks`), `encoding/wav_encoder.py` is the in-memory
  `encode_to_wav` / `read_wav_frame_info` / `get_wav_chunk` function module. Shared filename only —
  no stale copy, no finding.

### From dim_3.md

#### Verified-clean / no finding

- **Chunk geometry is exact.** `extract_chunk_segment` chunk-0 `[0:15s]`, middle `[5s:15s]`, last `[5s : 5s+remaining]` reconstructs the source timeline contiguously with zero gap and zero duplication; the last-chunk `remaining_duration = total - (10*(N-1) + 5)` exactly consumes the trimmed buffer. No off-by-one on the final chunk. (`core/chunk_operations.py:193-234`)
- **No fractional-sample drift.** All time→sample conversions use `round()`, and per-chunk extraction lengths are computed independently from absolute times rather than accumulated — `chunk_boundaries.py:126-135` documents the #2327 fix and it is intact.
- **Crossfade sample-count and copy hygiene.** `chunk_crossfade.apply_crossfade_between_chunks` and `ChunkOperations.apply_crossfade` both build a new array via `np.concatenate` and never mutate an input in place; total length is exactly `len(chunk1) + len(chunk2) - overlap`. (The equal-power-vs-equal-gain docstring discrepancy is OPEN #3878; the dead-code status of `apply_crossfade_between_chunks` is OPEN #3879 — both omitted per dedup.)
- **No fade on chunk 0.** `stream_chunk_ops.apply_boundary_crossfade` is an intentional no-op (`core/stream_chunk_ops.py:155-186`); no attack-clipping fade-in is applied to any chunk, including chunk 0.
- **`LevelManager` history is bounded** — `deque(maxlen=256)` at `core/level_manager.py:45-46`. OPEN #3885 ("grow unbounded") appears to be a stale-open; the fix is present.
- **Cache eviction is bounded and byte-accurate.** `SimpleChunkCache.put` correctly debits the overwritten entry before evicting (#3192 fix intact, `core/chunk_cache.py:117-133`) and `invalidate_chunk` debits too. The on-disk reaper (`ChunkCacheManager.prune_chunk_directory`, 512 MB, mtime-ordered, throttled behind a class-level lock) is correct, and unlinking a file another stream is reading is safe because `get_cached_chunk_path` re-checks `path.exists()`.
- **Concurrent/stale-track safety.** Cache keys include `file_signature` on both tiers (#4358 intact), `get_wav_chunk_path` holds `_sync_cache_lock` across the whole check→process→write cycle, `process_chunk_safe` runs DSP off the event loop via `asyncio.to_thread`, the shared-processor fingerprint toggle is under `processor._process_lock` (#4354 intact), and per-chunk DSP is bounded by `asyncio.wait_for(CHUNK_PROCESS_TIMEOUT)` (#3852 intact). Out-of-range `chunk_index` is rejected at both `get_wav_chunk_path` (raises `ValueError`) and `load_chunk_from_file` (#4342 intact).
- **Single-chunk-failure containment.** A failed chunk raises out of `process_chunk_only`, is drained by `drain_cancelled_task` (#3493 intact), and does not corrupt later chunks: each chunk is loaded and processed from absolute source offsets with no carried buffer state other than the (bounded, recoverable) `LevelManager` history.
- **PCM_16 accounting** in `cache/manager.py` was confirmed correct — excluded per the cross-dimension dedup note.

### From dim_4.md

#### Verified-clean (checked, no finding)

- **Engine API integration**: `load_audio(job.input_path, cancel_event=...)`, `resample_audio(audio, orig, target)`,
  `save(file_path=, audio_data=, sample_rate=, subtype=)` all match the current `auralis/io/` definitions exactly;
  `processor.reset_realtime_eq()` / `reset_dynamics()` / `reset_psychoacoustic_eq()` / `get_processing_info()` all exist on
  `HybridProcessor`. No signature drift.
- **Async/sync boundary in `ProcessingEngine`**: every CPU/disk-bound call (`load_audio`, `resample_audio`,
  `processor.process`, `save`, `HybridProcessor.__init__`) is wrapped in `asyncio.to_thread`, and the DSP call is
  additionally `asyncio.wait_for`-guarded at 300 s. No `asyncio.run()`/`run_until_complete()` anywhere in the engine path,
  no `await` on a non-awaitable.
- **Semaphore accounting in `JobWorker._run_job`**: the `acquired` flag correctly prevents an over-release on
  cancel-during-acquire; `active_job_count` is only touched under the acquired branch.
- **`enhancement_settings` identity**: single dict object from `main.py:110` through `deps['enhancement_settings']`,
  `create_lifespan`'s `deps['globals']`, and `seed_enhancement_settings` (which mutates in place per key, never rebinds).
  No copy, no `dict(...)`, no reassignment on any path. (The dead second dict in `config/globals.py:179` is unrelated to
  this chain and is covered by another dimension's `config.globals.globals_dict` finding.)
- **Shared-processor toggle race**: `apply_enhancement`'s `use_fingerprint_analysis` set/restore is correctly wrapped in
  `processor._process_lock` on both branches (the #4354 fix is present and intact).
- **Sample-count invariant**: `apply_enhancement` raises rather than truncate-blending on a length mismatch (#4371 fix
  present); `validate_audio` returns `audio.copy()` on the silence path rather than aliasing.

#### Dedup notes
Matched-and-omitted OPEN issues encountered while reading in-scope code: **#4370** (ProcessorPool FIFO eviction skips
`.close()`), **#3898** / **#3888** / **#3886** (streamlined worker + queue-status schema), **#3913**
(`library_auto_scanner.start()` done-callback), **#4359** (queue broadcast N+1), **#3762** (ProcessPoolExecutor recreation).
No regressions of CLOSED issues were observed in the code actually read — #3489, #3531, #2459, #2747, #3746, #4354 and
#4371 all still have their fixes in place.

### From dim_5.md

#### Dedup notes

Verified against `/tmp/audit/backend/issues.json` (159 issues). The following schema-dimension defects
were found in current code but are already tracked by an **OPEN** issue and are therefore **omitted**
from the findings above:

- **#3838** — ~28 endpoints returning raw `dict[str, Any]` with no `response_model`. Still accurate:
  `albums.py`, `tracks.py`, `library.py`, `playlists.py`, `metadata.py`, `artwork.py`, `files.py`,
  `system.py` remain unmigrated (49 `response_model=` usages, all in player/artists/enhancement/
  processing_api/settings/similarity/cache/health/library_scan).
- **#4429** — `loudness_variation_std` vs frontend `loudness_variation`. Confirmed still present, and the
  **sibling** at `GET /api/albums/{id}/fingerprint` (`routers/albums.py:229`) has the identical mismatch —
  that endpoint's `db_to_api` map renames 4 other columns to match the frontend but leaves this one.
  Belongs on #4429.
- **#3891** — duplicate `CacheStatsResponse` / `TrackCacheStatus` in `schemas.py` (typed) vs
  `cache_streamlined.py` (`dict[str, Any]`). Confirmed still duplicated
  (`schemas.py:498-503` vs `cache_streamlined.py:23-45`).
- **#3892** — three coexisting pagination shapes; `schemas.PaginatedResponse` still dead, ad-hoc
  `{total, offset, limit, has_more}` shapes still inlined in `tracks.py`, `albums.py`, `artists.py`, and a
  fourth `PaginatedResponse` still lives in `routers/pagination.py:20`.
- **#3893** — path-int params lacking `Path(..., ge=1)`. Confirmed; BE5-05 covers the disjoint
  **body-model** case only.
- **#3886** — `QueueStatusResponse` declares `cancelled`/`total` the engine never populates.
- **#3894 / #3895 / #3896** — `domain.ts` PlayerState casing, `/api/processing/presets` camelCase leak,
  `JobStatusResponse.status: str`. All still present.
- **#3780** — `seq` vs `sequence` naming across streams; **#3873** — `WebSocketMessageType` enum scope;
  **#3774** — `audio_chunk_meta.seq` emitted but unvalidated; **#4431** — `audio_stream_start.total_duration`
  divergence between enhanced and normal seek paths. All confirmed still present in
  `core/stream_messages.py` / `core/stream_protocol.py`.
- **#4398 / #4460** — unused/drifted types in `types/api.ts`. Confirmed.

No **CLOSED** issue in the dedup set matched a defect found here, so there are no regressions to report.

### From dim_7.md

#### Areas checked and found sound (no finding)

- **Streaming semaphore accounting**: `core/stream_enhanced.py:70-305` acquires under `asyncio.wait_for(..., timeout=5.0)`, sends `_send_error(websocket, track_id, "Server busy - too many active streams")` on `asyncio.TimeoutError` and returns *before* entering the guarded region; the single `try/finally` spanning track lookup through the streaming loop releases exactly once at `:305`, with an explicit comment about `BaseException` escaping before release. `stream_normal.py:65` and `stream_seek.py:74` follow the identical pattern.
- **WebSocket error propagation**: processing failures reach the client as a typed `audio_stream_error` frame with a `code` (`PROCESSOR_UNAVAILABLE`, `STREAMING_ERROR`) before the socket closes; `WebSocketDisconnect` is caught by type rather than by the old `"close message" in str(e)` substring test (the #3850 fix is still in place — no regression).
- **Timeouts**: present on every long operation — semaphore acquire (5s), processor instantiation (30s, with a corrupt-file-specific message), per-chunk processing (`CHUNK_PROCESS_TIMEOUT`), DSP processing (`ProcessingEngine.processing_timeout`, `:387-418` with `except TimeoutError` at `:521`), streamlined worker (`:343-350`), fingerprint generation (`analysis/fingerprint_generator.py:281-303`), and auto-scanner task shutdown/join. No unbounded job wait found.
- **Upload path** (`routers/processing_api.py:235-296`): size cap enforced before full-body read, magic-byte format validation, UUID filename, `open(..., "xb")` against symlink TOCTOU, temp-file cleanup in `except Exception: input_path.unlink(missing_ok=True); raise`, `asyncio.QueueFull -> 503`, and an `except HTTPException: raise` guard so 413/415/503 are not re-wrapped into 500.
- **HTTPException-to-500 re-wrap anti-pattern**: an AST pass over all 26 router modules found zero real instances.
- **Auto-scanner crash loop** (`services/library_auto_scanner.py`): shutdown is bounded (`wait_for(self._task, timeout=10.0)`, `shield(scan_future)` with 5s, `observer.join(timeout=5)`) and the idle wait is an event-driven `wait_for(self._trigger_event.wait(), timeout=seconds)` rather than a hot poll — no spin-on-permanent-failure loop found anywhere in the backend.