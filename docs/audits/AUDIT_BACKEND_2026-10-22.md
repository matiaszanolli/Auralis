# Backend Audit — 2026-10-22

- **Scope**: `auralis-web/backend/` (FastAPI app wiring, 20 registered routers, `/ws` + `ws_handlers/` + `websocket/`, chunked processor, streaming/seek paths, processing engine + job workers, schemas, middleware, caches, services), as defined in `.claude/commands/audit-backend.md`. Engine internals (`auralis/`) and the frontend were read only where a backend contract crosses into them.
- **Commit audited**: `44e4d433` (master).
- **Method**: fresh read of the current tree. 11 dimension agents ran (max 3 concurrent), at depth `deep` with no limit. Each agent deduplicated against all 5,613 GitHub issues (open and closed, up to #5859), against `docs/audits/` and against `.claude/issues/`. Behavioural claims were confirmed with scratch scripts against the real modules where practical, using an isolated `HOME`. No repo files were modified and no broad test runs were made.
- **Orchestrator verification**: before merging, the orchestrator re-checked all four HIGH findings and BE-D1-08 against the code. Two severities were adjusted (BE-D11-01 MEDIUM→HIGH, BE-D4-05 LOW→MEDIUM). Five worker findings were re-scoped as latent or partly latent after Dimension 10 independently confirmed BE-D8-01. Every changed entry says so inline.

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 36 |
| LOW | 46 |
| **Total** | **86** |

The status split is 82 NEW and 4 regressions of closed issues: BE-D4-01 of #4578, BE-D4-02 of #2332, BE-D1-08 of #3721 and BE-D11-01 of #4563. Two of the NEW findings are close siblings of closed fixes: BE-D7-01 is an incomplete fix of #5488, and BE-D1-05 is the #4600 NaN bug in the volume model, which that fix never covered. Open issues the agents found were cross-referenced and **not** re-reported (see the Appendix). Twenty-two findings overlap with the unpublished same-day `docs/audits/AUDIT_INTEGRATION_2026-10-22.md`, two of them via `AUDIT_ENGINE_2026-10-22.md`. Each one is marked **Cross-audit overlap** inline, so `/audit-publish` files it once.

**Key themes**

1. **Streaming liveness and seek correctness (HIGH).**
   - BE-D2-01: the flow-control gate can only be reopened by a `buffer_ready` that the client sends only when it ingests a frame, and the gate itself stops the frames. Since #5657 made the ring actually fill, enhanced playback of tracks longer than about 3 minutes should stall mid-track.
   - BE-D11-01: pre-seek frames still in flight pass the #4563 epoch filter, because the client adopts the new epoch only at `audio_stream_start`. Stale audio therefore lands at the head of the post-seek buffer.
   - Both are wire-protocol contracts that need a backend half and a frontend half.
2. **Library paths that import but cannot play (HIGH).** BE-D1-01: `POST /api/library/scan` trusts any user-chosen directory but never registers it with `path_security`. Every track scanned from outside `~/Music`/`~/Documents` is listed but fails streaming, metadata, lyrics and recommendations with "Audio file not found".
3. **Dead or mis-wired subsystems that look alive.**
   - BE-D4-01: the DB fingerprint tier can never succeed (a 7-field dataclass is built from 25 kwargs, and the `TypeError` is swallowed at DEBUG). This is the fourth time the symptom of #3557/#3836/#4578 has appeared.
   - BE-D8-01: the `StreamlinedCacheWorker` never initialises `track_status`, so it does no work. Its Tier-1/Tier-2 logic, and four findings that live inside it, are latent.
   - BE-D4-02: the 20-job queue bound is never enforced.
   - BE-D4-05: mastering recommendations fail for any track with a `.25d` hit.
   - BE-D1-08: a new `QueueService` is built per request, so the #3721/#4825/#5320 `set_queue` serialization never spans two requests.
4. **Chunk-cache integrity.**
   - BE-D10-01: a disk-cache hit runs the pruner before returning, and can hand back a path it just deleted.
   - BE-D3-01: a cache hit re-reads through `load_audio` and changes the channel shape for mono and >2-channel files.
   - BE-D3-02 / BE-D11-03: chunks rendered on a fresh `LevelManager` (by seek or prewarm) are persisted under the sequential cache key, which gives level steps of up to about 15 dB.
5. **Lifecycle and restart bugs.**
   - BE-D6-01: after `POST /api/library/reset`, the auto-scanner and fingerprint queue cannot restart.
   - BE-D6-02: `FingerprintExtractionQueue.stop()` blocks the loop for up to 30 s.
   - BE-D4-03 / BE-D7-05: `JobWorker.stop()` lets semaphore-parked jobs start after shutdown and persists in-flight jobs as CANCELLED rather than INTERRUPTED.
   - BE-D7-04: a degraded startup reports healthy.
6. **Validation gaps on mutating routes.**
   - BE-D1-04: scan-folder delete prunes tracks under an arbitrary path.
   - BE-D1-05: volume turns NaN into 100%.
   - BE-D5-01: an explicit `null` in `PUT /api/settings` bricks the settings routes.
   - BE-D1-03: playlist deletes report success on DB failure.
7. **Test gates that cannot catch the above.**
   - BE-D9-01: the "queue full" tests mock the very thing that is broken.
   - BE-D9-03: every `slow` test, including the only real REST→engine test, is excluded from CI and nothing else runs it.
   - BE-D9-02: the real-DSP sample-count test is one-sided.

**Verified clean** (from the agents' "checked and clean" notes):
- **Routes**: all 94 HTTP operations are `async def`. No hand-raised 503/400/404 is left in `routers/` (#5783 holds). Every router binds `RouterDeps` asynchronously (#5762 holds). There are no route-order conflicts, and every frontend `/api/` call has a backend route.
- **Chunk geometry**: emitted segments tile the source exactly for 8–192 kHz and edge lengths, in real end-to-end runs for WAV/MP3/OGG/M4A/WMA. There are no hardcoded chunk literals and no crossfade (#4642 holds).
- **Seek mapping**: brute-forced over about 320 durations × 215 positions with zero violations. Rapid seeks cancel and await. Look-ahead and the proactive buffer are drained on seek.
- **Middleware**: the order matches the documented CORS → SecurityHeaders → NoCache → OriginCheck → TrustedHost → RateLimit. There are no wildcard origins, and `null`/`file://` are rejected. The origin check runs before `accept()`.
- **Presets**: the preset single-source rule holds, and no removed preset name is accepted or emitted.
- **Paths**: `filepath` is never exposed (#3205).
- **Query and pool health**: there is no N+1 in list endpoints, and the pool is adequately sized.
- **Executors**: the executor split is correct at every `to_thread` site in `core/`.
- **Job store**: `job_store` writes are non-fatal.
- **Atomic writes**: chunk, thumbnail and `.25d` writes are all atomic.

## Route Coverage Matrix

The matrix comes from Dimension 1 (validation, typed errors, `response_model`) and Dimension 9 (tests that hit the real route over HTTP). There are 94 HTTP operations plus the `/ws` WebSocket. 92 of the 94 HTTP operations declare `response_model`; the 2 that don't are binary responses. None of the handlers is sync.

| Router | Prefix | Routes | Input validation | Typed errors | response_model | Real-route tests |
|---|---|---|---|---|---|---|
| albums | `/api/albums` | 4 | OK | OK | 4/4 | happy + error |
| artists | `/api/artists` | 3 | OK (search ignores `order_by`, BE-D1-11) | OK | 3/3 | happy + error |
| artwork | `/api/albums/{id}/artwork*` | 4 | OK | OK | 3/4 (binary GET) | happy + error |
| cache_streamlined | `/api/cache` | 5 | OK | OK | 5/5 | `DELETE /track/{id}` never called (BE-D9-06) |
| enhancement | `/api/player/enhancement/*`, `/api/player/mastering/*` | 5 | OK (recommendation not rate-limited, BE-D6-03) | 500 for timeout/bad file (BE-D7-08) | 5/5 | happy + error |
| files | `/api/files`, `/api/audio` | 2 | OK | OK | 2/2 | happy + error |
| fingerprint_queue | `/api/similarity/fingerprint-*` | 4 | OK | gaps (#5381) | 4/4 | one test each, repo mocked |
| fingerprint_status | `/api/library/fingerprints`, `/api/tracks/{id}/fingerprint` | 2 | OK | OK | 2/2 | weak / inert (BE-D9-04, BE-D9-05) |
| health | `/api/health`, `/api/version` | 2 | OK | degraded startup reports healthy (BE-D7-04) | 2/2 | happy + error |
| library | `/api/library/{stats,reset,refresh-references}` | 3 | OK | OK | 3/3 | happy + error |
| library_scan | `/api/library/scan*` | 2 | gaps (BE-D1-01, BE-D6-10) | OK | 2/2 | happy + error |
| metadata | `/api/metadata` | 4 | gaps (#5266; BE-D5-03, BE-D5-04) | inconsistent 400/500 (BE-D7-03) | 4/4 | happy + error |
| player | `/api/player/*` | 16 | gaps (BE-D1-05) | OK | 16/16 | `POST /queue/add-tracks` never called (BE-D9-06) |
| playlists | `/api/playlists` | 10 | OK | gaps (#5264, BE-D1-03) | 10/10 | mocked repo only; 2 routes never called (BE-D9-06) |
| processing_api | `/api/processing` | 10 | gaps (BE-D1-06) | OK | 9/10 (binary download) | happy + error; queue-full tests vacuous (BE-D9-01) |
| settings | `/api/settings` | 5 | gaps (BE-D1-04, BE-D5-01) | OK | 5/5 | happy + error |
| similarity | `/api/similarity/{tracks,fit}` | 4 | gaps (BE-D1-07) | gaps (#5381) | 4/4 | happy + error |
| similarity_graph | `/api/similarity/graph*` | 3 | no single-flight (BE-D1-09) | gaps (#5381) | 3/3 | happy + error (#5491 holds) |
| system | `/ws` (WebSocket only) | 1 | malformed `data` gives `internal_error` (BE-D2-04) | n/a | n/a | real `/ws` tested up to the `stream_audio` seam (BE-D9-07) |
| tracks | `/api/library/tracks*` | 6 | OK (lyrics fallback corrupts, BE-D1-02) | OK | 6/6 | happy + error; lyrics not-found test inert (BE-D9-04) |

## Findings

Findings are grouped by severity and ordered by dimension within each group. IDs are `BE-D<dimension>-<nn>`. Cross-dimension duplicates were removed before merging: each dimension received the running list of earlier findings and cross-referenced them instead of re-filing.

### CRITICAL (0)

_None._

### HIGH (4)

#### BE-D1-01: `POST /api/library/scan` accepts any user-chosen directory but never registers it, so imported tracks outside `~/Music`/`~/Documents` fail every `validate_file_path` consumer (streaming, metadata, lyrics, recommendation)
- **Severity**: HIGH
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/library_scan.py:112-150` (`scan_library`), `auralis-web/backend/schemas/library.py:20-33` (`LibraryScanRequest`), `auralis-web/backend/security/path_security.py:38-47,167-192`; consumers `core/stream_track_resolution.py:60-82`, `routers/metadata_deps.py:43-67`, `routers/tracks.py:185`
- **Status**: NEW (sibling of closed #4765 / #5259, which added allowlist registration to `PUT /api/settings` and `POST /api/settings/scan-folders` only)
- **Description**: `LibraryScanRequest.directories` is validated with `validate_user_chosen_directory`, which deliberately trusts any directory outside the OS-owned trees. The file-level check, `validate_file_path`, however only allows `~/Music`, `~/Documents`, `XDG_MUSIC_DIR` and directories registered at runtime through `register_allowed_directory()` -- called only by `settings.py` (add folder / PUT diff) and the startup seed from the persisted `scan_folders`. `scan_library` neither registers the scanned directories nor persists them to `scan_folders`, and the UI's "Scan folder" action (`useLibraryScan.handleScanFolder`, Electron `select-folder` picker) calls only this route. Tracks from such a scan are imported and listed, but every consumer that re-validates the stored path rejects them: `resolve_and_validate_track` (used by `play_normal`, `play_enhanced` and seek) answers `audio_stream_error: "Audio file not found"`, metadata read/write/batch 400/404, lyrics extraction is skipped, mastering recommendation 400s. After a restart nothing re-registers the folder either (startup seeds from settings only).
- **Evidence**: run against the live functions with `HOME` pointed at an empty dir and a temp directory outside it: `validate_directory_list([d])` -> accepted; `validate_file_path(d + '/a.wav')` -> `PathValidationError: Path is outside allowed directories`. `grep register_allowed_directory` shows callers only in `routers/settings.py` and `config/startup/components.py`.
- **Impact**: A user who scans a library living on another mount (`/mnt/...`, `/media/...`, a NAS) through the normal scan button sees tracks they cannot play, with a misleading "Audio file not found" error; the workaround (re-adding the folder under Settings -> scan folders) is not discoverable.
- **Siblings**: `LibraryAutoScanner` only scans settings folders (already registered), so it is unaffected.
- **Suggested Fix**: After a successful scan (or before it), `register_allowed_directory()` each validated directory -- and ideally add it to `scan_folders` via the settings repository so the registration survives restarts -- mirroring `add_scan_folder`.
- **Cross-audit overlap**: same defect as INT-F4-1 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D2-01: Backend flow-control gate can only be reopened by a frame the gate itself stops (and by a rate-limitable `buffer_ready`)
- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_gates.py:35-43`; `auralis-web/backend/ws_handlers/playback_control.py:56-68`; `auralis-web/backend/routers/system.py:41-58,128-142`; client side `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:139-150`, `audioChunkIngest.ts:95-102`
- **Status**: NEW (related, closed: #5657, whose lookahead cap made the ring actually fill; #5514)
- **Description**: `buffer_full` clears `flow_events[ws_id]`; the pumps then block forever in `wait_for_stream_gates()` (`flow_evt.wait()`, no timeout, no liveness check). The only thing that sets the event again is a client `buffer_ready` (or seek/play/stop/disconnect). The frontend decides to send `buffer_ready` only inside `handleChunk`, i.e. when an audio frame is ingested and `fill < 50%` while `flowPaused` is true. Once the server has stopped sending, no further frame arrives, so that branch can never run: the in-flight remainder of the current chunk lands while the ring is still above 75% (it takes roughly 70 s of playback to drain 25 points of a 100 MB ring), and after that the client plays out its buffer and stalls with `flowPausedRef=true` and the server parked at the gate. The ring only reaches 75% when `capacityForStream` hits the 100 MB cap, i.e. for tracks longer than roughly 3 minutes (capacity is 1.5x the stream size below the cap, so shorter tracks never pause). It was masked until #5657 (a5ee430b, 2026-10-17): before that the worklet feeder drained the ring at ~1.8x real time and kept it near the floor, so `buffer_full` never fired. Secondary path: `buffer_full`/`buffer_ready` go through the same 10 msg/s per-connection (30/s per-IP) limiter as user commands (only ping/pong/heartbeat are exempt, #4786), and the client sends each edge exactly once, so a `buffer_ready` dropped during a burst (seek-bar scrubbing) leaves the gate closed permanently with the client believing it resumed. The server answers a dropped message with a `rate_limit_exceeded` `error` frame that the client merely logs.
- **Evidence**:
  ```python
  # core/stream_gates.py
  flow_evt = stream_flow_events.get(key)
  if flow_evt is not None:
      await flow_evt.wait()          # no timeout; only buffer_ready/seek/play/stop/teardown set it
  ```
  ```ts
  // audioChunkIngest.ts - evaluated only per ingested frame
  if (fillPercentage > FLOW_PAUSE_FILL_PCT && !currentlyPaused) return 'pause';
  if (fillPercentage < FLOW_RESUME_FILL_PCT && currentlyPaused) return 'resume';
  ```
  `grep -rn buffer_ready auralis-web/frontend/src` has exactly one non-test send site (useStreamMessageHandlers.ts:149). `tests/backend/test_websocket_flow_control.py` only exercises `asyncio.Event` set/clear, not the round trip.
- **Impact**: For tracks longer than ~3 minutes, playback should stop mid-track once about 3.5 minutes of audio is buffered and the rest of the track is never delivered; the stream task also keeps its `_global_stream_semaphore` slot, processor and look-ahead task until the user seeks/skips. Found by static trace; not reproduced against a running Electron build, so confirm by playing a >4 min track in enhanced mode.
- **Siblings**: `stream_normal_chunks.py:110` and `stream_enhanced_chunks.py:136` (both call the same gate). Rate-limit drop of `buffer_ready` is the same failure with a different trigger.
- **Suggested Fix**: Make resume level-triggered on the client (evaluate the water mark from the BufferScheduler/feeder tick, not from frame ingest) or move to a credit/ack protocol; on the server exempt `buffer_full`/`buffer_ready` from the limiter and give the flow gate a bounded wait (re-open after N seconds, log it) so a lost edge cannot park a stream forever.
- **Cross-audit overlap**: same defect as INT-F5-1 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D4-01: Tier-1 (database) fingerprint load can never succeed -- it builds a 7-field `MasteringFingerprint` from 25 keyword arguments
- **Severity**: HIGH
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/fingerprint_loading.py:70-113`
- **Status**: Regression of #4578 (same symptom as #3557/#3836/#4578: Tier 1 always falls through; those fixes only repaired the repository wiring)
- **Description**: `load_from_database()` converts the `TrackFingerprint` row into a dict of the 25 fingerprint columns and then does `MasteringFingerprint(**fp_dict)`. `auralis.analysis.mastering_fingerprint.MasteringFingerprint` is a dataclass of 7 *different* fields (`loudness_dbfs`, `peak_dbfs`, `crest_db`, `spectral_centroid`, ...). The constructor raises `TypeError: unexpected keyword argument 'sub_bass_pct'`, which the function's blanket `except Exception` turns into a `logger.debug(...)` and `return None`. So the database tier of the documented three-tier hierarchy (`MasteringTargetService.load_fingerprint`) always misses, silently (DEBUG level, no test covers the real path -- `test_mastering_target_cache_signature_5489.py` monkey-patches `load_fingerprint_from_database`).
- **Evidence**:
  ```python
  # fingerprint_loading.py:103
  fingerprint = MasteringFingerprint(**fp_dict)      # fp_dict has sub_bass_pct, bass_pct, ... (25 keys)
  ...
  except Exception as e:
      logger.debug(f"Database fingerprint lookup failed for track {track_id}: {e}")
      return None
  ```
  Reproduced with a stub repository returning a record with the 25 attributes:
  `DEBUG:core.fingerprint_loading:Database fingerprint lookup failed for track 1: MasteringFingerprint.__init__() got an unexpected keyword argument 'sub_bass_pct'` -> `None`.
- **Impact**: `ChunkedAudioProcessor` never gets DB-derived fixed mastering targets (`init_fingerprint_and_processor` -> `load_fingerprint(extract_if_missing=False)`). Every library-fingerprinted track (the fingerprint queue writes the DB row, and the `<audio>.25d` that `SidecarManager` writes is a different file from the `~/.auralis/fingerprints/<hash>.25d` that Tier 2 reads) streams with `mastering_targets=None`, i.e. per-chunk fingerprint analysis, so the "8x faster, track-wide consistent" fixed-target design -- and the #5552/#5553/#5554 fixes to it -- is never reached for them. Nothing in the logs says so. (Tier 3 extraction is never requested either: the only call site passes `extract_if_missing=False` and the "extract on first chunk playback" comment in `chunk_processor_init.py` describes code that does not exist.)
- **Siblings**: `ChunkedAudioProcessor.fingerprint` is a `MasteringFingerprint` on the intended Tier-1 result but a 25D `dict` on the Tier-2/3 results (see BE-D4-05); a fix that makes Tier 1 return a dict like the other tiers also has to account for that. `generate_targets_from_fingerprint` already accepts either shape.
- **Suggested Fix**: Return the `fp_dict` itself (the shape Tier 2/3 return and `generate_targets_from_fingerprint` consumes) instead of constructing `MasteringFingerprint`; log load failures at WARNING; add a test that feeds a real `TrackFingerprint` row (not a patched method) through `load_fingerprint`.

#### BE-D11-01: Pre-seek frames still in flight are accepted after a seek -- the stream epoch is adopted only at `audio_stream_start`, not at `seek_started`
- **Severity**: HIGH (dimension agent: MEDIUM)
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:451-456` (seek_started carries no epoch), `auralis-web/backend/core/stream_messages.py:90-91` (epoch allocated in the new task's `send_stream_start`), `auralis-web/backend/core/stream_seek.py:130-219` (track lookup + processor construction sit between the cancel and that allocation); client side `auralis-web/frontend/src/hooks/enhancement/useStreamSubscriptions.ts:95-105`, `useEnhancedSeek.ts:67-79,99`, `audioChunkIngest.ts:61-66`
- **Status**: Regression of #4563 (the closed fix is in place but does not meet its own acceptance criterion "no PCM frame produced by the superseded stream reaches the audio buffer")
- **Description**: #4563 stamps a monotonically increasing `stream_epoch` on `audio_stream_start` and every `audio_chunk_meta`, and the client drops chunks whose epoch differs from the one it adopted. The client adopts a new epoch only when the new `audio_stream_start` arrives. Between the client resetting its PCM buffer (in `seekTo`, before it even sends the `seek` frame) and that start frame, the client's `streamEpochRef` is still the **old** stream's epoch. Every frame the old stream pushed before `_cancel_prior_task` ran (they all precede `seek_started` on the wire, because the old task is awaited to completion first) therefore classifies as current (`incomingEpoch === currentEpoch` -> `null` rejection) and is ingested into the freshly reset buffer. The follow-up `audio_stream_start` has `is_seek=true`, which takes the "resume into existing buffer" early return and keeps that buffer, so the stale audio sits at the head of the post-seek playback. The window is not tiny: after the cancel, the backend still has to look the track up, validate the path, build a `ChunkedAudioProcessor` in a thread (ffprobe, fingerprint load, pooled-processor lookup) before it allocates the new epoch, and the old stream is typically mid-burst because the server sends ahead until the client buffer reaches its flow-control threshold (a 300 KB frame is ~0.85 s of stereo audio and up to four are queued).
- **Evidence**:
  ```python
  # playback_commands.py:451-456 -- the only signal the client gets at the cancel point
  await _cancel_prior_task(ws_id, state)
  await safe_send_text(websocket, {"type": "seek_started",
                                   "data": {"track_id": track_id, "position": position}})
  # stream_messages.py:90-91 -- epoch only exists once the NEW task reaches send_stream_start
  epoch = _asc.next_stream_epoch()
  _asc._stream_epoch_var.set(epoch)
  ```
  ```ts
  // useEnhancedSeek.ts: reset happens first, epoch ref untouched; seek_started only clears isSeeking
  core.pcmBufferRef.current?.reset();  ...  wsContext.send({ type: 'seek', ... });
  useMessageSubscriptions(wsContext.subscribe, { seek_started: () => setIsSeeking(false) });
  // audioChunkIngest.ts: stale frame passes because currentEpoch is still the old epoch
  if (incomingEpoch != null && currentEpoch != null && incomingEpoch !== currentEpoch) return 'superseded-epoch';
  ```
  Wire order seen by the client: `[old-epoch frames sent before the cancel] -> seek_started -> audio_stream_start(new epoch, is_seek) -> new frames`. Everything before `audio_stream_start` and after the client's reset is ingested.
- **Impact**: A fraction of a second to a few seconds of pre-seek audio can play at the head of a seek when the seek lands while the server is sending (no error, no log; also `processedChunks` and the buffer-fill flow control count the stale frames). Timing dependent, so it reproduces intermittently, which is how #4563 originally looked.
- **Siblings**: `handle_play_enhanced`/`handle_play_normal` use the same cancel-then-start order, but their `audio_stream_start` has no `is_seek`, so the client rebuilds its buffer and the stale frames are discarded; the exposure is specific to the seek/resume path.
- **Suggested Fix**: Allocate the epoch in `handle_seek` *before* `seek_started`, include it in that frame (and hand it to `stream_from_position` so `send_stream_start` reuses it), and have the client adopt it on `seek_started`. Alternatively have the client reset the buffer on `seek_started` (every older frame precedes it on the wire) instead of on send.
- **Orchestrator note**: Raised from MEDIUM by the orchestrator: it is the exact failure HIGH #4563 was filed for (stale pre-seek audio at the head of post-seek playback), and the client code confirms the epoch is adopted only at `audio_stream_start` (`useStreamSubscriptions.ts`) while `seekTo` resets the buffer before sending `seek` (`useEnhancedSeek.ts`). The same-day integration audit independently rated it HIGH (INT-F1-1). Static trace; not reproduced end to end.
- **Cross-audit overlap**: same defect as INT-F1-1 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

### MEDIUM (36)

#### BE-D1-02: Lyrics file fallback returns Vorbis/FLAC lyrics as a Python list repr, mislabels them "lrc", and persists the corrupted text
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/tracks.py:174-188` (extraction), `:191-203` (persist + response)
- **Status**: NEW
- **Description**: The file-extraction fallback of `GET /api/library/tracks/{id}/lyrics` takes the first branch `elif hasattr(audio_file, 'tags') and audio_file.tags:` for every non-MP4 container and then does `str(audio_file.tags['LYRICS'])`. For FLAC/Ogg/Opus the tags object is a `VCommentDict` whose `__getitem__` returns a **list** of strings, so `str(...)` yields `"['line text']"`. Because `"[" in text and "]" in text` is then true, `format` is reported as `"lrc"`, and the mangled text is persisted to `tracks.lyrics` via `repos.tracks.update_metadata(..., lyrics=lyrics_text)`, so the corruption is permanent and the DB-hit path (line 148) serves it forever. The `UNSYNCEDLYRICS` fallback sits in the `elif hasattr(audio_file, 'get')` branch, which is unreachable for any file that has tags (the first `elif` already matched), so FLAC/Ogg files tagged `UNSYNCEDLYRICS` (the Vorbis-comment convention used by most taggers) never return lyrics. The ID3 branch only probes `'USLT::eng'` and the bare key `'USLT'`; mutagen keys USLT frames as `USLT:<desc>:<lang>`, so lyrics tagged with any other language code (`USLT::fra`, `USLT::und`, `USLT::XXX`) or a non-empty description are never found (the bare `'USLT'` key can never exist).
- **Evidence**:
  ```python
  elif hasattr(audio_file, 'tags') and audio_file.tags:
      if 'USLT::eng' in audio_file.tags: ...
      elif 'USLT' in audio_file.tags: ...
      elif 'LYRICS' in audio_file.tags:
          lyrics_text = str(audio_file.tags['LYRICS'])      # VCommentDict -> list
  elif hasattr(audio_file, 'get'):                          # unreachable when tags truthy
      lyrics_text = audio_file.get('LYRICS', [None])[0] or audio_file.get('UNSYNCEDLYRICS', [None])[0]
  ```
  Verified: `VCommentDict(); v['LYRICS']=['hello world']; str(v['LYRICS'])` -> `"['hello world']"`; `ID3().add(USLT(lang='fra',...))` -> keys `['USLT::fra']`, so neither `'USLT::eng'` nor `'USLT'` matches.
- **Impact**: Lyrics panel shows `['...']` with brackets/quotes for FLAC/Ogg files and tries to render them as timestamped LRC; non-English ID3 lyrics and all `UNSYNCEDLYRICS` tags report "no lyrics". The wrong value is written to the library DB.
- **Siblings**: `auralis/library/scanner` lyric extraction (not audited here) may share the same tag-key assumptions.
- **Suggested Fix**: Iterate `audio_file.tags.getall('USLT')` for ID3, join `VCommentDict` lists (`'\n'.join(tags['LYRICS'])`) and check `UNSYNCEDLYRICS` in the same branch; decide LRC by a timestamp regex (`\[\d+:\d+`) instead of bare bracket presence.

#### BE-D1-03: `DELETE /api/playlists/{id}` and `DELETE .../tracks/{track_id}` report success and broadcast even when the repository swallowed a DB error
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/playlists_crud.py:196-211` (`delete_playlist`), `:113-127` (`create_playlist`); `auralis-web/backend/routers/playlists_tracks.py:215-237` (`remove_track_from_playlist`); repositories `auralis/library/repositories/playlist_crud_mixin.py:120-165`, `playlist_ordering_mixin.py:37-90`
- **Status**: NEW (extends open #5264, which lists only `update`, `add_track`, `reorder_track` and `clear`; the two routes below ignore the result entirely, which is a different and worse failure)
- **Description**: Every `PlaylistRepository` mutator catches `Exception`, rolls back, logs, and returns a sentinel (`False`/`None`). `delete_playlist` calls `repos.playlists.delete(...)` and **discards the result**, then broadcasts `playlist_deleted` and returns `200 "Playlist deleted successfully"`; the inline comment justifies ignoring `False` for a concurrent-delete race, but `False` is equally what `database is locked`/IntegrityError returns. `remove_track_from_playlist` discards `repos.playlists.remove_track(...)`, whose *only* `False` path is the exception path (it returns `True` otherwise, even for rowcount 0), and likewise broadcasts `playlist_updated/track_removed` and returns 200. `create_playlist` maps a `None` result (DB failure) to `400 "Failed to create playlist"`, i.e. the client's fault.
- **Evidence**:
  ```python
  playlist = await asyncio.to_thread(repos.playlists.get_by_id, playlist_id)
  if playlist is None: raise NotFoundError("Playlist")
  await asyncio.to_thread(repos.playlists.delete, playlist_id)      # result dropped
  await broadcast_typed(connection_manager, "playlist_deleted", {"playlist_id": playlist_id})
  return {"message": "Playlist deleted successfully"}
  ```
  repository: `except Exception as e: session.rollback(); error(...); return False`
- **Impact**: Under transient SQLite contention (WAL writer busy, scan running) a delete or remove-track "succeeds" in the UI, and every connected client drops the playlist/track on the broadcast, while the row is still in the DB and reappears on the next fetch. #5264's 404/400 mislabelling is at least visible to the user; these two are silent.
- **Siblings**: #5264's four routes (`update_playlist`, `add_track_to_playlist`, `reorder_playlist_track`, `clear_playlist`); `add_track_to_playlist` also lacks the existence check the batch add route does.
- **Suggested Fix**: Fix at the root as #5264 proposes (repository re-raises or returns a tri-state), and in these two routes check the result before broadcasting.

#### BE-D1-04: `POST /api/settings/scan-folders/delete` prunes every track under an arbitrary, unvalidated, possibly-not-configured path
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/settings.py:55-66` (`_revoke_folder`), `:156-172` (`remove_scan_folder`); `auralis-web/backend/routers/settings_models.py:25-26` (`_ScanFolderRequest`); `auralis/library/repositories/track_repository_maintenance.py:198-250`; `auralis/library/repositories/settings_repository.py:183-203`
- **Status**: NEW (side effect introduced by #5467/#5523, which are closed)
- **Description**: `remove_scan_folder` takes `body.folder` as a bare `str` (no validation, no normalization -- `add_scan_folder` stores the *resolved* path from `validate_user_chosen_directory`). `SettingsRepository.remove_scan_folder()` silently does nothing when the string is not in the stored list, but the handler then unconditionally runs `_revoke_folder()`, which calls `prune_tracks_under_folder()` -> `TrackRepository.remove_tracks_under_folder(folder)`. That method resolves `folder` and deletes **every** Track row whose resolved path `is_relative_to` it (and, through `delete_tracks_by_ids`, their fingerprints/playlist memberships/favorites). So:
  - `{"folder": "/"}` (or `"."`, `"~"`-expanded, any parent of the library, or a sub-directory of a configured folder) wipes the matching tracks although nothing was removed from the scan-folder list;
  - an equivalent-but-not-identical spelling of a configured folder (trailing slash, symlinked path) fails the `folder in folders` membership test, so the setting stays configured and trusted by the auto-scanner while its tracks are deleted and its allowlist entry is dropped (`unregister_allowed_directory(Path(folder))` also resolves to the real entry);
  - removing a parent folder deletes the tracks of a still-configured nested scan folder.
  The batch `PUT /api/settings` diff path is safe because it only revokes folders that were really in the previous list; this dedicated endpoint has no such guard.
- **Evidence**:
  ```python
  settings = await asyncio.to_thread(repo.remove_scan_folder, body.folder)   # no-op if not in list
  await _revoke_folder(deps, body.folder)                                    # prunes regardless
  ```
- **Impact**: A mistyped or crafted request destroys library rows (play counts, favorites, playlist membership, fingerprints) that a rescan cannot restore; the response is a normal 200 with unchanged settings.
- **Siblings**: none (PUT path is diff-guarded).
- **Suggested Fix**: Resolve/normalize `body.folder` the same way as add, and only revoke+prune when the repository reports the folder was actually present (return the removed flag or compare before/after lists); skip pruning for folders still covered by another configured folder.

#### BE-D1-05: `POST /api/player/volume` turns `NaN`/`Infinity` into 100 % volume (the #4600 NaN-clamp bug, unfixed in the volume model)
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/player_models.py:91-104` (`SetVolumeRequest.clamp_volume`)
- **Status**: NEW (sibling of closed #4600, which fixed intensity only)
- **Description**: `clamp_volume` is `max(0.0, min(100.0, v))` on an unconstrained `float`. Pydantic's float accepts `NaN`/`Infinity` (JSON `NaN` literals parse with Python's `json`), and `min(100.0, nan)` returns `100.0`, so a NaN volume is silently converted to the maximum, never rejected. `SeekRequest` right above rejects non-finite values explicitly, and #4600's own comment names this exact failure (`max(0.0, min(1.0, nan))` is `1.0`). The clamp-not-reject policy documented in the class comment covers out-of-range finite values (150, -50); NaN has no meaningful clamp target.
- **Evidence**:
  ```
  >>> SetVolumeRequest.model_validate_json('{"volume": NaN}')   -> volume=100.0
  >>> SetVolumeRequest.model_validate(json.loads('{"volume": Infinity}')) -> volume=100.0
  ```
  (verified against the live model)
- **Impact**: A malformed/hand-crafted request sets full-scale output volume instead of a 422. The shipped frontend cannot send NaN (`JSON.stringify(NaN)` is `null`, which 422s), so exposure is limited to scripts/other local clients.
- **Siblings**: none found in `routers/` (`SetIntensityRequest`, `SettingsUpdateRequest.volume` use `ge/le`, which reject NaN).
- **Suggested Fix**: In the validator, `if not math.isfinite(v): raise ValueError(...)` before clamping.

#### BE-D1-06: `POST /api/processing/upload-and-process` keeps its own, drifted magic-byte sniff and rejects WMA/AU/ADTS-AAC uploads the loader supports
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/processing_upload.py:52-65` (`_is_valid_audio_magic`) vs `auralis-web/backend/routers/files_validation.py:14-40` (`_has_valid_audio_magic`)
- **Status**: NEW (sibling of closed #4498, whose fix landed only in `files_validation.py`)
- **Description**: Two hand-maintained copies of "does this buffer look like audio" exist. #4498 fixed the `/api/files/upload` copy and added `tests/backend/test_upload_magic_bytes.py::test_every_supported_format_is_recognised` to keep it in step with `SUPPORTED_FORMATS`; the processing-upload copy was never touched and is only unit-tested against its own short list (`tests/backend/test_processing_api.py:940`). The extension allowlist beside it (`AUDIO_EXTENSIONS`, derived from `auralis.io.formats`, line 29-33) still includes `.wma`, `.au`, `.aac`, so a well-formed file of those types passes the extension rule and is then rejected with `415 Unsupported or invalid audio file format`. The copy also accepts `b"FORM"` without checking the `AIFF/AIFC` form type and a bare `b"AIFF"` prefix that no real file starts with.
- **Evidence**: run against both functions: `wma` (ASF GUID header) -> processing `False` / files `True`; `.snd` AU header -> `False` / `True`; `0xFFF1` ADTS AAC -> `False` / `True`.
- **Impact**: Users cannot master WMA, AU or raw-ADTS AAC files through the upload path although the loader decodes them and the sibling upload route accepts them; the next added format will drift again because only one copy is guarded by a test.
- **Siblings**: `files_validation.py` is the canonical copy; `processing_upload.py:_ALLOWED_AUDIO_EXTENSIONS` re-export is the extension half of the same check.
- **Suggested Fix**: Delete the processing copy and import `_has_valid_audio_magic` (move it to a shared module, e.g. `auralis.io.formats` or `security/`), pointing the existing parametrised test at the shared function.

#### BE-D1-07: `POST /api/similarity/fit` ignores `fit()`'s result and does not forward `min_samples`, so it can report `fitted: true` for a system that is not fitted
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/similarity_explain.py:75-118`; `auralis/analysis/fingerprint/similarity.py:84-117`; `auralis/analysis/fingerprint/normalizer.py:100-104`
- **Status**: NEW (adjacent to open #5716, which covers the normalizer's unfiltered count and missing refit, not the route's handling)
- **Description**: The handler validates `min_samples` itself (`Query(10, ge=5)`, `if fingerprint_count < min_samples: 400`) and then calls `await asyncio.to_thread(similarity.fit)` **without arguments and without looking at the return value**. `FingerprintSimilarity.fit(min_samples=10)` returns `False` (it does not raise) when the library has fewer than its own default of 10 fingerprints, when the normalizer reads no usable rows, or when it is stopped. Two consequences: (1) the documented `min_samples` knob can only *raise* the bar -- `?min_samples=5` with 5-9 fingerprints passes the router check and then fails inside `fit()` on the engine's default of 10; (2) whatever `fit()` returns, the handler responds `200 {"fitted": true, "message": "Successfully fitted similarity system with N tracks"}`. `fingerprint_count` also comes from `repos.fingerprints.get_count()`, a bare `COUNT(*)` that includes in-progress claim placeholders and stale-version rows that `fit()` (via `get_all`) excludes (#4822), so the reported `total_fingerprints` can exceed what the model was fitted on.
- **Evidence**:
  ```python
  await asyncio.to_thread(similarity.fit)          # min_samples not passed, bool dropped
  return {"fitted": True, "total_fingerprints": fingerprint_count,
          "message": f"Successfully fitted similarity system with {fingerprint_count} tracks"}
  ```
- **Impact**: A client (or the settings UI) is told the system is fitted while `/similar`, `/compare`, `/explain` keep answering 503 "Similarity system not initialized" from `require_fitted`, with no hint why.
- **Siblings**: none; `similarity_autofit_worker` calls `fit` directly with its own handling.
- **Suggested Fix**: `ok = await asyncio.to_thread(similarity.fit, min_samples)`; if not `ok` raise `BadRequestError`/`ServiceUnavailableError`; report `similarity.fitted` rather than a literal `True`.
- **Cross-audit overlap**: same defect as INT-F6-2 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D1-08: `QueueService` is built per request, so its `set_queue` serialization/generation protocol (#3721/#4825/#5320) never spans two requests
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/player_deps.py:103-116` (`_get_queue_service`); state in `auralis-web/backend/services/queue_service_base.py:77-90`; consumers `queue_set_mixin.py:43-160`, `queue_edit_mixin.py`, `queue_order_mixin.py`
- **Status**: Regression of #3721 (fix present but defeated by the DI wiring; also voids the #4825 / #5320 follow-ups)
- **Description**: Every `/api/player/queue*` handler obtains its service through `Depends(_get_queue_service)`, which returns a **new** `QueueService(...)` on each request ("Lazy service initialization" docstring, no cache). All of the cross-request coordination lives on that instance: `self._set_queue_lock`, `self._set_queue_engine_lock`, `self._next_set_queue_generation`, `self._set_queue_generation`. Two overlapping requests therefore hold two different services with two different locks and two independent generation counters, so (a) a second `set_queue` can never supersede the first (`generation < self._set_queue_generation` compares against its own counter), (b) `_queue_mutation()`/`_invalidate_set_queue_generation()` in add/remove/clear/reorder/move/shuffle do not stop an in-flight `set_queue` from running `load_file()/play()` afterwards (#5320), and (c) the engine lock does not order engine calls. The sibling services already solved exactly this: `NavigationService` keeps its lock/seq in a module-level `_TrackChangeSequencer` whose docstring says "FastAPI `Depends()` builds a fresh instance per request -- so a lock or counter on `self` would never actually contend" (#4582), and `PlaybackService` delegates to the module-level `playback_event_sequencer`. `QueueService` was missed. Tests that construct one `QueueService` and `gather()` two calls pass, so the defect is invisible to them.
- **Evidence**:
  ```python
  def _get_queue_service(...) -> QueueService:
      """Lazy service initialization"""
      return QueueService(audio_player=..., library_database=..., ...)   # new instance per request
  # queue_service_base.py
  self._set_queue_lock = asyncio.Lock()          # per instance
  self._set_queue_generation = 0                 # per instance
  ```
  The only `QueueService(` construction site in non-test code is `player_deps.py:110`.
- **Impact**: The #3721 scenario (double-click "Play album", rapid playlist switch) is live again for the REST queue API: concurrent `POST /api/player/queue` calls interleave so the state manager can publish track B while the engine ends up on track A; a `clear`/`remove` racing a `set_queue` can still be followed by the stale request's load/play.
- **Siblings**: `QueueEnricher` is stateless (fine); `RecommendationService`/`PlaybackService` hold no per-instance coordination state.
- **Suggested Fix**: Move the locks/generation counters into a module-level (or `app.state`) singleton like `_TrackChangeSequencer`, or cache one `QueueService` per router `_PlayerDeps` instead of constructing it per request; add a test that issues two requests through the ASGI app, not two calls on one instance.

#### BE-D1-09: `POST /api/similarity/graph/build` has no single-flight; overlapping builds leave duplicate edges (no unique constraint)
- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/similarity_graph.py:62-85`; `auralis/analysis/fingerprint/knn_graph.py:81-170` (no lock); `auralis/library/models/fingerprint.py:232-258` (`SimilarityGraph`, no unique index on `(track_id, similar_track_id)` / `(track_id, rank)`); `auralis/library/repositories/similarity_graph_repository.py:61-83`
- **Status**: NEW (adjacent to open #5747, which covers the OFFSET paging/clear-first aspect, not concurrency)
- **Description**: The handler documents "this can take several minutes" and runs `graph_builder.build_graph(...)` in a worker thread, with nothing preventing a second request from starting while the first is running (the frontend hard-caps requests at 30 s, #4845, and a closed fetch does not cancel an already-running route, as `library_scan_lifecycle.py` itself documents). `FingerprintSimilarity.fit` got an explicit `_fit_lock` (#5243); `KNNGraphBuilder` has none. Two overlapping builds both run `clear_all()` (when `clear_existing=True`) and then each `add_edges()` its k neighbours for every track. `similarity_graph` has no unique constraint, so the table ends up with up to 2k rows per track (ranks 1..k twice). `get_similar_tracks` then serves `graph_builder.get_neighbors(track_id, limit)` straight from that table, i.e. the same similar track repeated, and `len(neighbors) >= limit` is satisfied by duplicates, so the correct real-time fallback is skipped as well. `DELETE /graph` racing a build has the same effect in reverse (a half-cleared, half-built graph).
- **Evidence**: handler body is `stats = await asyncio.to_thread(graph_builder.build_graph, k=k, clear_existing=clear_existing)`; `KNNGraphBuilder.build_graph` has no lock; `SimilarityGraph.__table_args__` lists only non-unique indexes; `add_edges` is a plain `session.add_all`.
- **Impact**: After a retried/double-submitted build the "similar tracks" list shows duplicates and returns fewer distinct tracks than `limit`; the corruption persists until the next successful single build.
- **Siblings**: `/api/similarity/fit` is protected by `_fit_lock`; `POST /api/library/scan` by the scan-slot registry.
- **Suggested Fix**: Add a non-blocking build lock in `KNNGraphBuilder` (or the router) that makes a second request fail fast with 409/503 "build in progress", and a unique index on `(track_id, similar_track_id)` so duplicates cannot persist.

#### BE-D1-10: `GET /api/albums/{id}/artwork` loads the whole album with every track, genre and artist just to read `artwork_path`
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/artwork.py:99-114` (`repos.albums.get_by_id`); `auralis/library/repositories/album_repository.py:48-53,74-87` (`_ALBUM_DETAIL_OPTIONS`)
- **Status**: NEW
- **Description**: Every album card in the library grid issues one `<img src="/api/albums/{id}/artwork[?size=N]">` request, and the handler resolves the album with `AlbumRepository.get_by_id`, whose `_ALBUM_DETAIL_OPTIONS` eagerly load `Album.artist` plus `selectinload(Album.tracks)` with `Track.genres`, `Track.artists` and `Track.album` -- four extra queries and a full hydration of every track row of that album -- and then `session.expunge_all()`. The handler reads exactly one column (`album.artwork_path`). `AlbumRepository` has no lightweight accessor (the list path got `with_expression` counters for this very reason, #4777). A page of 50 cards therefore costs ~250 queries and ~600 hydrated `Track` rows (more for large albums/box sets) on the shared `to_thread` pool before any image byte is served, and the same cost is paid again on every revalidation (`Cache-Control: public, no-cache` means each re-render re-requests and only the 304 skips the body, not the lookup).
- **Evidence**: `album = await asyncio.to_thread(repos.albums.get_by_id, album_id)` followed only by `album.artwork_path`; `_ALBUM_DETAIL_OPTIONS = (joinedload(Album.artist), selectinload(Album.tracks).selectinload(Track.genres), selectinload(Album.tracks).selectinload(Track.artists), selectinload(Album.tracks).joinedload(Track.album))`.
- **Impact**: Library/album views start slowly and contend with other repository calls and with WebSocket streaming for threads and SQLite connections, scaling with album track count and visible card count.
- **Siblings**: `extract_album_artwork`/`delete_album_artwork`/`download_album_artwork` also call `get_by_id` for one field (cold paths, so low impact).
- **Suggested Fix**: Add `AlbumRepository.get_artwork_path(album_id)` (single-column select) and use it in the GET handler and the three management handlers.
- **Cross-audit overlap**: same defect as INT-F7-3 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D2-02: Temp-WAV conversion hold leaks when the stream task is cancelled while the conversion is running
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_normal.py:132-134,267-277`; `auralis-web/backend/core/seekable_source.py:240-264`; `auralis-web/backend/core/stream_enhanced.py:224-239`; `auralis-web/backend/core/stream_seek.py:274-282`
- **Status**: NEW (sibling of closed #5253 / #5402; those fixed the normal-completion path, not cancellation mid-conversion)
- **Description**: `ConvertedWavRegistry.acquire()` increments `refs` before it decodes the whole file, and the holder must call `release(key)` exactly once. (a) `stream_normal_audio` assigns `conversion_key` only when `await asyncio.to_thread(converted_wavs.acquire, ...)` returns. If the task is cancelled during that await (stop, seek, next track, disconnect), the worker thread keeps running, finishes `acquire` (hold taken, WAV written) and returns the key to nobody; `conversion_key` is still `None` in the `finally`, so `release` is never called. (b) Enhanced/seek streams do `acquire` lazily inside the executor thread via `SeekableSource.resolve()` (`chunk_render.load_chunk`), setting `self._key` only after the decode. The cancelled stream's `finally` runs `await asyncio.to_thread(processor.close)` immediately; `close()` sees `_key is None` and returns, then the still-running thread sets `_key` on a processor nobody will close.
- **Evidence**:
  ```python
  # stream_normal.py
  conversion_key, streaming_filepath = await asyncio.to_thread(
      converted_wavs.acquire, validated_filepath, prefix=stream_temp_prefix()
  )
  ...
  finally:
      ...
      if conversion_key is not None:          # None if cancelled during the await above
          await asyncio.to_thread(converted_wavs.release, conversion_key)
  # seekable_source.py
  self._key, self._resolved = self._registry.acquire(self._filepath)   # set after decode finishes
  def close(self): if self._key is None: return
  ```
- **Impact**: `refs` for that file stays >= 1, so the conversion never goes idle and `_evict_locked` / `shutdown()` (idle-only) never remove it; the full-track float32 WAV (~100 MB for 5 min stereo) stays in the temp root until the next startup sweep. Trigger: skipping or stopping while a non-natively-seekable file (m4a/aac/wma/opus; in normal mode also mp3/ogg since `stream_normal` converts every FFMPEG_FORMATS entry) is still being decoded, which is exactly what rapid track skipping does. Each affected file leaks once (later holders reuse the same key).
- **Siblings**: the three entry points above.
- **Suggested Fix**: Run the acquire in a task whose result is released by a done-callback if the awaiting coroutine was cancelled (or shield it and release in `finally`), and make `SeekableSource.close()` coordinate with an in-flight `resolve()` (lock, or a closed flag that makes a late `acquire` result release itself).
- **Cross-audit overlap**: same defect as INT-F8-4 (seek path only; the normal-path half is new here) in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D2-03: A broadcast send timeout silently and permanently unsubscribes a still-connected client
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/config/globals.py:155-234` (`_send_to`, `broadcast`)
- **Status**: NEW
- **Description**: `broadcast()` treats `TimeoutError` (client did not accept a frame within `BROADCAST_SEND_TIMEOUT = 2.0`) the same as a send that raised: the socket is removed from `active_connections`. For an exception that is right (the socket is dead). For a timeout the socket is alive, its receive loop and heartbeat keep running (pongs arrive, so `is_stale` never fires), and nothing closes the socket or re-adds it; the only `append` is in `connect()`. Since #4784 the send really does suspend under backpressure, and the same socket is concurrently carrying ~300 KB binary PCM frames, so a client that is merely unresponsive for >2 s (renderer jank or a suspended window while a stream is in flight) hits this.
- **Evidence**:
  ```python
  if isinstance(result, TimeoutError):
      logger.warning(f"WebSocket send exceeded {BROADCAST_SEND_TIMEOUT}s — marking connection stale for removal")
  ...
  for stale in stale_connections:
      if stale in self.active_connections:
          self.active_connections.remove(stale)      # socket not closed
  ```
- **Impact**: After one slow window the client no longer receives any broadcast (`player_state`, `track_changed`, `queue_changed`, `library_updated`, `scan_*`, `mastering_recommendation`, `playback_started` from REST) while audio streaming and heartbeat look healthy, so the UI desynchronises until the user reloads. Likelihood is low (needs a >2 s stall) but there is no recovery.
- **Siblings**: none.
- **Suggested Fix**: On timeout, close the socket (e.g. 1013) so the client's reconnect path re-syncs through the initial `player_state` / `enhancement_settings_changed` pushes, or keep the entry and only skip this broadcast.
- **Cross-audit overlap**: same defect as INT-F5-5 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D3-01: Cache-hit path re-reads chunks through `load_audio`, so >2-channel (and mono) chunks change shape between cache miss and cache hit
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_streaming.py:84-95` (hit branch of `process_chunk`); loader behavior in `auralis/io/loaders/soundfile_loader.py:89-98` (`requires_layout_aware_downmix`) and `auralis/io/processing.py:34-36`
- **Status**: NEW
- **Description**: A cache miss returns the freshly rendered `extracted_chunk` with the source's native channel count (the chunk loader reads with `sf.SoundFile(...).read(always_2d=True)` and the engine preserves channels). A cache hit instead decodes the cached 16-bit WAV with the whole-file loader `load_audio()`, which is a different contract: it downmixes any channel count that is not 1/2 (and not a canonical native-downmix count) via FFmpeg, and downmixes 6/8 channels natively to stereo, and returns mono as 1-D. So the same chunk index yields N channels on first render and 2 channels on every later hit, inside a stream whose `audio_stream_start.channels` was set once from the probe (`processor.channels`). Because chunk WAVs are written natively N-channel, the hit path never round-trips what was stored.
- **Evidence**:
  ```python
  # chunk_streaming.py:84-90
  from auralis.io.unified_loader import load_audio
  audio, _ = load_audio(str(cached_path))
  _record_cache_hit_level(processor, chunk_index, audio=audio)
  return (str(cached_path), audio)
  ```
  Reproduced with the real processor (second `ChunkedAudioProcessor` for the same track, same cache dir; scratch `/tmp/audit/backend/d3/hit.py`):
  ```
  3ch  44.1k: miss (529200, 3)   hit (529200, 2)
  6ch  48k  : miss (720000, 6)   hit (720000, 2)  /  (336000, 6) -> (336000, 2)
  mono 44.1k: miss (529200, 1)   hit (529200,)      # 1-D, contradicts the #4132 "always 2-D" contract
  ```
- **Impact**: For a 3/4/5/6/7-channel FLAC/WAV/OGG track, replaying it (or any stream that mixes freshly-rendered chunks with chunks the proactive buffer / cache worker / an earlier play already wrote) interleaves N-channel and 2-channel float32 frames under a single advertised channel count; the client deinterleaves with the wrong stride, giving garbled audio and wrong duration for the hit chunks. Each hit also spawns an FFmpeg subprocess for non-native layouts. Mono is harmless today (every consumer flattens or reads `shape[0]`) but is the same contract break.
- **Siblings**: `chunk_batch.get_full_processed_audio_path` (`chunk_batch.py:90-95`, same `load_audio` re-read; unreachable, #5088); `ChunkedAudioProcessor.channels` advertisement (#5709).
- **Suggested Fix**: Read cached chunk WAVs with `sf.read(path, dtype='float32', always_2d=True)` (they are our own flat PCM files; no downmix, duration-cap or FFmpeg routing is wanted) so hit and miss return identical shape/dtype.

#### BE-D3-02: Cache worker renders chunks out of order through one LevelManager and persists the order-dependent bytes under the shared durable key
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/streamlined_tiers.py:112-135,139-150,204-224` (tier-1 "next chunk" vs tier-2 sequential build); `auralis-web/backend/core/streamlined_worker.py:180-190`; `auralis-web/backend/core/chunk_render.py:272-285` (smoothing against `processor._level_manager`); durable key `core/chunk_cache_manager.py:94-97` / `core/encoding/wav_encoder.py:129-131`
- **Status**: NEW
- **Description**: `LevelManager.smooth_transition` bakes a gain into the chunk relative to whatever chunk was rendered *previously by the same processor*, and `ChunkedAudioProcessor.process_chunk` persists the result to a path keyed only on track/signature/preset/intensity/targets/chunk index. `StreamlinedCacheWorker` keeps ONE processor (hence one LevelManager) per `(track, preset, intensity, signature)` and drives it with two independent schedulers every tick: tier 1 renders `current_chunk + 1` (a jump forward), then tier 2 renders `_building_chunk_idx` (sequential from 0). Consecutive calls on that processor are therefore frequently non-adjacent chunks (e.g. 1, 0, 2 on the first tick; every later tier-1 render lands between two tier-2 renders), so a chunk is smoothed against a non-neighbour's RMS (or, if it is the first render on that processor, left as an unsmoothed baseline) and that result is written to the same file the live stream later serves as a cache hit (hits are never re-smoothed, #4669). Contents of the cache therefore depend on which writer got there first and in what order. #5323/#5328 closed the prewarm and cancelled-look-ahead triggers of this class; the cache worker (a long-lived, always-on writer) was left as is.
- **Evidence**: Same processor class driven in the worker's order vs sequentially on a synthetic track alternating 15 s loud / 15 s quiet noise (scratch `/tmp/audit/backend/d3/ooo.py`, 6 chunks, 44.1 kHz stereo):
  ```
  sequential 0,1,2,3,4,5      gains(dB): [0, 16.91, 0, -1.45, 15.45, 0]
  worker-like 4,0,1,2,3,5     gains(dB): [0, 0, 16.91, 0, -1.45, 0]
  chunk 4 emitted RMS:  sequential -16.9 dB   vs   rendered-first -32.4 dB   (15.5 dB difference, same cache key)
  ```
  ```python
  # streamlined_tiers.py: tier 1 then tier 2 on the same worker processor
  await worker._ensure_tier1_chunk(track, track_id, next_chunk_idx, preset, intensity)   # current+1
  ...
  await worker._build_tier2_cache(track, track_id, current_chunk, preset, intensity)    # idx 0,1,2,...
  ```
- **Impact**: The loudness relationship at a chunk seam in an enhanced stream depends on scheduling accident: a step at the seam the smoother exists to prevent (up to the smoother's full correction, which #5558 shows can be tens of dB), persisted across plays until the WAV is pruned. Most visible in the first minute of a track (tier 1 and tier 2 interleave while playback advances) and after seeks.
- **Siblings**: `proactive_buffer._buffer_one_preset` renders chunks 0..2 in order on its own processor (OK) but races the worker for the same keys; `routers/enhancement_prewarm.py:125-150` renders current+1..+3 on a fresh processor so its first chunk is always an unsmoothed baseline; the live stream's seek path starts a fresh baseline at the seek chunk by design.
- **Suggested Fix**: Make the durable chunk independent of render order: apply level smoothing at serve time (stream pump) rather than before the durable write, or write the pre-smoothing segment to the cache and keep the LevelManager purely a per-stream playback concern. Failing that, only persist chunks whose predecessor chunk was the immediately preceding render on that processor.
- **Reachability**: Partly latent: the worker writer described here is gated by BE-D8-01, but Dimension 10 confirmed the same defect is LIVE through the seek path and the prewarm path, which render a chunk on a fresh `LevelManager` and persist it under the shared durable key (see also BE-D11-03). Fix serve-time smoothing / key the cache on render context regardless of what happens to the worker.
- **Cross-audit overlap**: same defect as INT-F8-5 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D4-02: `ProcessingEngine`'s bounded queue never bounds anything -- the 503 "queue is full" contract is dead (regression of #2332)
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/job_worker.py:61-101, 196-220`; `auralis-web/backend/core/processing_engine.py:154-168`
- **Status**: Regression of #2332 (acceptance criterion "HTTP 503 returned when queue is full")
- **Description**: `JobWorker.start()` pops each job from `job_queue` and immediately `spawn_background_task(self._run_job(job))`; `_run_job` then parks on `_concurrency_semaphore.acquire()`. The `asyncio.Queue(maxsize=20)` is therefore drained as fast as the loop turns, and the real backlog is an unbounded number of parked `_run_job` tasks. `submit_job`'s `put_nowait` essentially never raises `QueueFull`, `get_queue_status()["queue_full"]` is always `False`, and `max_queue_size` is decorative.
- **Evidence**: scratch run with `ProcessingEngine(max_concurrent_jobs=2)` and a 5 s `process_job`, 200 consecutive `create_job` + `submit_job`:
  `accepted 200 queuefull 0 qsize 0 tasks parked 200` and `{'queued': 200, 'processing': 2, 'max_queue_size': 20, 'queue_full': False}`.
- **Impact**: No backpressure on `POST /api/processing/process` or `/upload-and-process` (each upload spools up to `_MAX_UPLOAD_BYTES` of audio into the temp dir); a batch client can queue unbounded work and disk. The router's `except asyncio.QueueFull -> ServiceUnavailableError` branches, and the engine docstring's "QueueFull contract", are unreachable in production.
- **Siblings**: `routers/processing_upload.py:159` and `routers/processing_api.py:132` (dead 503 branches).
- **Suggested Fix**: Enforce the bound on pending (QUEUED) jobs -- e.g. count `QUEUED` jobs in `submit_job` against `max_queue_size`, or have the dispatcher acquire the semaphore *before* `job_queue.get()` so the queue holds the backlog.

#### BE-D4-03: `JobWorker.stop()` only cancels jobs that already hold a slot; semaphore-parked jobs start running during and after shutdown
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/job_worker.py:79-86, 124-136, 162-170`
- **Status**: NEW (sibling gap of the closed #4543 / #4706)
- **Description**: `_tasks[job_id]` is only populated *after* `semaphore.acquire()` returns. `stop()` cancels exactly the tasks in `_tasks`, waits for them to unwind (their `finally` releases the semaphore), then drains `job_queue` and cancels the dispatcher. Any `_run_job` task parked on the semaphore (backlog from BE-D4-02, or just a third job with `max_concurrent_jobs=2`) is neither in `_tasks` nor in `job_queue`, so it is never cancelled and its job is never marked CANCELLED: when the running jobs unwind and release their slots, the parked tasks acquire them and call `process_job` on a QUEUED job.
- **Evidence**: scratch run, 5 jobs, 2 slots, `await engine.stop_worker()`:
  `before stop started: [14ac, 56bb]` / `after stop started: [14ac, 56bb, d5c8 (stopped=True), 2bde (stopped=True)]` / statuses `[cancelled, cancelled, processing, processing, queued]`, and three `_run_job` tasks still alive after `stop_worker()` returned (the fifth never ran but is still parked).
- **Impact**: During lifespan shutdown (`config/startup/shutdown.py`: engine stop, then pool drain, library DB teardown, `shutdown_executors()`), fresh jobs begin loading audio, persisting to a DB that is being torn down, and submitting to executors being shut down (failures surface as swallowed `RuntimeError`/warnings); leftover tasks survive `stop()`. A job the user saw as "queued" is either half-started at exit or persisted as QUEUED and reported INTERRUPTED on next start.
- **Siblings**: none (single owner).
- **Suggested Fix**: Register every `_run_job` task (at spawn, not after acquire) and cancel/mark all of them in `stop()`; or have `_run_job` check `self._stopping` right after `acquire()` and mark the job CANCELLED instead of running it.

#### BE-D4-04: A Tier-2 `.25d` cache entry with `{}` targets is applied as fixed targets, silently replacing adaptive mastering with all-default parameters
- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/fingerprint_loading.py:149-158`; `auralis-web/backend/core/chunk_processor_init.py:139-166`; `auralis/analysis/fingerprint/fingerprint_storage.py:172-179`
- **Status**: NEW
- **Description**: `FingerprintService.get_or_create()` (called by the player's `_schedule_fingerprint_load` on every `load_file`) writes the `~/.auralis/fingerprints/<hash>.25d` cache with `targets={}` (`FingerprintStorage.save(audio_path, fingerprint, {})`), and `FingerprintStorage.load` returns `(fingerprint, targets or {})`. `load_from_file` re-derives targets only `if mastering_targets and isinstance(fingerprint, dict)`, so `{}` passes through with the comment "an empty dict means 'not derived yet' and is left for callers to fill" -- but no caller fills it (`MasteringTargetService.load_fingerprint` returns it as is; `init_fingerprint_and_processor` forwards it). `ProcessorFactory.get_or_create` then does `if mastering_targets is not None: set_fixed_mastering_targets(deepcopy({}))`, `HybridProcessor._process_adaptive_mode` passes `fixed_params={}` (`is not None`) and `ContinuousMode._resolve_parameters` takes the fast path, so `convert_targets_to_parameters({})` supplies pure defaults.
- **Evidence**: `FingerprintStorage.save(path, fp, {})` then `MasteringTargetService().load_fingerprint(1, path, extract_if_missing=False)` returns `(fp, {})` with `get_targets_hash({}) != "none"` (`99914b93...`). `HybridProcessor.set_fixed_mastering_targets({})` + `process()`: `last_parameters.target_lufs == -14.0`, all five `eq_curve` gains `0.0`, and `continuous_mode.last_fingerprint` stays unset (no analysis ran); with `None` the fingerprint analysis runs.
- **Impact**: Any track whose cache entry was created by the player path is mastered with generic flat EQ / -14 LUFS / fixed compression instead of its fingerprint-driven parameters, with no log line, and its chunk cache is keyed under a distinct targets hash. Compounds BE-D4-01 (with Tier 1 dead, this `.25d` is the only fixed-target source).
- **Siblings**: `StreamlinedCacheWorker` builds processors through the same `ChunkedAudioProcessor` init, so background-cached chunks inherit the same targets.
- **Suggested Fix**: In `load_from_file`, derive targets whenever they are empty (`if not mastering_targets`), and make `init_fingerprint_and_processor` treat falsy targets as `None`.

#### BE-D4-05: `ChunkedAudioProcessor.get_mastering_recommendation()` hands a 25D dict to an engine that needs a `MasteringFingerprint`
- **Severity**: MEDIUM (dimension agent: LOW)
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/chunk_mastering.py:58-70`
- **Status**: NEW
- **Description**: `compute_mastering_recommendation` only extracts a `MasteringFingerprint` when `processor.fingerprint is None`; otherwise it passes `processor.fingerprint` to `AdaptiveMasteringEngine.recommend_weighted`. `processor.fingerprint` is whatever the 3-tier loader returned, and Tier 2/3 return the 25D *dict*.
- **Evidence**: `AdaptiveMasteringEngine().recommend_weighted({k: 0.1 for k in DIMENSION_SCHEMA})` -> `AttributeError: 'dict' object has no attribute 'loudness_dbfs'` (caught by the function's `except Exception`, logged at ERROR, returns `None`).
- **Impact**: For a track with a Tier-2 `.25d` hit, `RecommendationService._get_or_analyze` (and `routers/enhancement_recommendation.py`) get `None` and the recommendation panel never populates, while a track with no cache works. Becomes the common case if BE-D4-01 is fixed by returning dicts.
- **Siblings**: BE-D1-14 (recommendation endpoint re-implementation) shares the recommendation surface.
- **Suggested Fix**: In `compute_mastering_recommendation`, use the loaded fingerprint only if `isinstance(..., MasteringFingerprint)`; otherwise extract via `MasteringFingerprint.from_audio_file`.
- **Orchestrator note**: Raised from LOW by the orchestrator: `processor.fingerprint` is whatever `init_fingerprint_and_processor()` loaded, and the Tier-2 `.25d` hit (the common case for any previously streamed or fingerprinted track) returns the 25D dict, so the recommendation route 500s (BE-D7-08) for most of the library rather than an edge case.

#### BE-D5-01: Explicit `null` in `PUT /api/settings` is written to the DB: a nulled `default_preset` makes `GET`/`PUT /api/settings` fail with 500 until a full reset, and null on any NOT NULL field is a 500 instead of a 422
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/settings_models.py:31-72,127`; `auralis-web/backend/routers/settings.py:110`; `auralis/library/repositories/settings_repository.py:124-135`
- **Status**: NEW
- **Description**: Every `SettingsUpdateRequest` field is declared `X | None = None`, and the handler turns the model into the update with `model_dump(exclude_unset=True)`. A client that sends `{"default_preset": null}` therefore produces `{'default_preset': None}`, which the repository `setattr`s onto the row unchanged. The model's Optional means "omitted" to a reader, but the pipeline treats an explicit null as "set to NULL". Two failure modes follow. (1) `default_preset` (and `theme`, `language`, `output_device`) are nullable columns, so the NULL is committed. `SettingsResponse.default_preset` is the non-Optional `EnhancementPresetLiteral = DEFAULT_PRESET`, so building the response from `to_dict()` raises a ValidationError. The PUT itself returns 500 after the commit, and every later `GET /api/settings` returns 500 too, because the stored row is permanently invalid. Only `POST /api/settings/reset` (which wipes all settings) recovers. The v22->v23 migration normalised old NULLs, but this path re-creates them. (2) Every other column is `Mapped[<non-Optional>]`, so `auto_scan`, `volume`, `bit_depth`, `enhancement_intensity`, `crossfade_*` and the rest raise `IntegrityError` at commit and return 500 where a 422 is the contract everywhere else.
- **Evidence**:
  ```python
  # settings_models.py:75 / 127
  default_preset: EnhancementPresetLiteral | None = None          # request
  default_preset: EnhancementPresetLiteral = DEFAULT_PRESET        # response (not Optional)
  # settings.py:110
  payload = updates.model_dump(exclude_unset=True)                 # {"default_preset": None} survives
  # settings_repository.py:135
  setattr(settings, key, value)                                    # NULL committed
  ```
  Reproduced on a scratch DB. After a first save, `update_settings_with_previous_folders({'default_preset': None})` stores `None`. Then `SettingsUpdateResponse(message='x', settings=s.to_dict())` and `SettingsResponse(**repo.get_settings().to_dict())` both raise `settings.default_preset: Input should be 'adaptive' [type=literal_error, input_value=None]`. Separately, `{'auto_scan': None}`, `{'volume': None}` and `{'bit_depth': None}` each raise `IntegrityError: NOT NULL constraint failed: user_settings.<col>`.
- **Impact**: No bundled frontend path sends null, so only a script or a future client triggers it. When triggered, the Settings dialog (`GET /api/settings` on open) is dead until the user resets all settings, and the endpoint reports 500 for what is client input.
- **Siblings**: None of the other request models have the same exposure. `UpdatePlaylistRequest` and `MetadataUpdateRequest` filter `None` explicitly; `SettingsUpdateRequest` alone passes it through.
- **Suggested Fix**: Drop explicit nulls for the non-nullable fields (`{k: v for k, v in payload.items() if v is not None or k in NULLABLE}`) or type those fields non-Optional with a `model_validator(mode='before')` that rejects null with a 422. Make `SettingsResponse.default_preset` degrade like its intensity sibling, or stop the null reaching the column.
- **Cross-audit overlap**: same defect as INT-F3-3 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D5-02: `PlayerState.shuffle_enabled`, `mastering_enabled`, `current_preset` and `analysis` are never written, and the frontend applies the frozen `shuffle_enabled` on every snapshot, flipping the shuffle toggle off
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/player_state.py:91,104,107,110`; `auralis-web/backend/core/state_manager.py:48-60,138-143,202`; `auralis-web/frontend/src/hooks/player/playerStateSnapshot.ts:118-119`
- **Status**: NEW (sibling of open #5460, which covers `PlayerState.queue` only)
- **Description**: `PlayerState` advertises four live-looking fields. A grep of every writer (`_mutate_state`/`update_state` callers: `set_track`, `set_playing`, `set_volume` -> volume/is_muted, `set_queue`, `follow_navigation`, `player_queue.set_repeat_mode` -> repeat_mode) shows none of them ever assigns `shuffle_enabled`, `mastering_enabled`, `current_preset` or `analysis`. They are permanently `False`/`True`/`"adaptive"`/`None`. The real shuffle state lives in the engine's `QueueManager` and is announced only by a separate `queue_shuffled` message. The real enhancement state lives in the `enhancement_settings` dict. `PlayerStatePayload` is built with `cast(PlayerStatePayload, state.model_dump())`, so the typed-payload machinery cannot notice. The frontend trusts the snapshot: `applyPlayerStateSnapshot` dispatches `setIsShuffled(state.shuffle_enabled)` whenever the key is present, and it is always present.
- **Evidence**:
  ```python
  # player_state.py
  shuffle_enabled: bool = False        # no writer anywhere
  mastering_enabled: bool = True       # no writer anywhere (grep: only player_state.py + outbound_messages.py)
  current_preset: EnhancementPresetLiteral = DEFAULT_PRESET   # no writer
  analysis: dict[str, Any] | None = None                      # no writer, no consumer
  ```
  ```ts
  // playerStateSnapshot.ts:118
  if ('shuffle_enabled' in state && state.shuffle_enabled !== undefined) {
    dispatch(setIsShuffled(state.shuffle_enabled));   // always false
  }
  ```
  `POST /api/player/queue/shuffle` -> `queue_order_mixin.py:162-171` broadcasts `queue_changed` + `queue_shuffled {is_shuffled: true}` and never touches the state manager.
- **Impact**: User enables shuffle (UI turns on). The next play, pause, volume change or navigation broadcasts `player_state` with `shuffle_enabled: false`, so the toggle visibly turns off while the engine queue stays shuffled. A reconnect snapshot does the same. `mastering_enabled` and `current_preset` report stale values, but the frontend currently ignores the former, and with a single preset the latter is harmless. `analysis` is dead.
- **Siblings**: #5460 (same snapshot overwrites the queue after edits). Same root cause: the snapshot is only partially maintained.
- **Suggested Fix**: Have the shuffle/unshuffle paths and the enhancement toggle/preset paths update `PlayerStateManager` (`update_state(shuffle_enabled=...)`), or delete the four fields from `PlayerState`/`PlayerStatePayload`/`RawPlayerStateData` and make the snapshot reader stop consuming `shuffle_enabled`.
- **Cross-audit overlap**: same defect as INT-F9-2 (shuffle part only) in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D5-03: Metadata round-trip truncates `year` (full date) and `bpm` (decimal) to integers on every save, even for a title-only edit
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/metadata_models.py:19,24`; `auralis/library/metadata_editor/readers.py:46-48,69-71`; `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:129-141`
- **Status**: NEW (sibling of closed #5506, which fixed only the track/disc `N/M` total)
- **Description**: `GET /api/metadata/tracks/{id}` returns every tag as the raw string (`year` = `str(TDRC)`/`DATE`, e.g. `"2020-05-01"`; `bpm` = `"128.5"`). The dialog stores that object and, on save, re-sends the whole form with `parseInt` applied to `year/track/disc/bpm`. `MetadataUpdateRequest` types `year` and `bpm` as `int`, so the PUT contract cannot carry a date or a fractional BPM. #5506 patched the writer for track/disc (`_with_existing_total`), but there is no equivalent for `year` or `bpm`. Every save therefore rewrites those two tags in the audio file.
- **Evidence**:
  ```ts
  // useMetadataForm.ts:133-136
  if (['year', 'track', 'disc', 'bpm'].includes(key)) {
    const num = parseInt(String(value), 10);        // "2020-05-01" -> 2020 ; "128.5" -> 128
  ```
  Reproduced against a real FLAC: `read_metadata` -> `{'title': 'x', 'year': '2020-05-01', 'bpm': '128.5'}`; `write_metadata(p, {'year': 2020, 'bpm': 128, 'title': 'x'})` -> read back `{'year': '2020', 'bpm': '128'}`. The same applies to MP3 `TDRC` and MP4 `©day`.
- **Impact**: Editing any field (even just the title) silently destroys the release date's month/day and the BPM's fraction in the user's file (the server-side backup is deleted after a successful write).
- **Siblings**: `track`/`disc` (fixed by #5506). `MetadataUpdateRequest.model_config` uses `extra="forbid"`, so a string `year` from a stricter client would 422 instead of round-tripping.
- **Suggested Fix**: Make `year` accept the string the reader emits (or have the writer preserve an existing longer date when the incoming value equals its year prefix, as `_with_existing_total` does), and make `bpm` a float. Alternatively let the dialog send only the fields the user changed.

#### BE-D6-01: `LibraryAutoScanner` and `FingerprintExtractionQueue` cannot be restarted after `stop()`, so `POST /api/library/reset` kills both for the rest of the session
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:69,86-99,115`; `auralis/services/fingerprint_queue.py:105,155-171,184,222`; restart driven by `auralis-web/backend/config/background_workers.py:80-92` and `auralis-web/backend/routers/library.py:138,163`
- **Status**: NEW
- **Description**: The reset endpoint stops every `BACKGROUND_WORKER_KEYS` worker, bulk-deletes, then calls `start_background_workers()` in a `finally`. That helper only works if `stop()` followed by `start()` leaves a running worker. Two of the four workers do not. `LibraryAutoScanner.stop()` sets `_stop_event`, and `start()` never clears it. The new `_run()` task therefore evaluates `while not self._stop_event.is_set()` as False and returns at once. `FingerprintExtractionQueue.stop()` sets `should_stop = True`, and `start()` never resets it. The new threads fail `while not self.should_stop` immediately, and `self.workers` accumulates dead thread objects. The other two workers handle it: `FingerprintQueue.start()` resets `_shutdown`, and `SimilarityAutoFitWorker.start()` calls `_stop_event.clear()`. `tests/backend/test_library_reset.py` uses `AsyncMock` workers, so it never exercises a real restart.
- **Evidence**:
```
# auto scanner (probe: _run_cycle replaced by a recorder that sleeps)
first start cycles 1 task done False
after stop+start cycles 1 task done True        # second start does nothing

# FingerprintExtractionQueue (real start/stop, probe loop honouring should_stop)
after start, alive: 2
after stop+start: should_stop= True  alive: 0  total thread objs: 4
```
- **Impact**: After any "Reset library", the auto-scanner (watchdog and periodic rescans of the user's scan folders) and the batch fingerprint extraction queue never run again until the app is restarted. The reset endpoint reports success, nothing is logged, and `/api/similarity/fingerprint-queue/status` just shows nothing progressing. Re-importing after a reset leaves tracks unfingerprinted, which degrades mastering targets and similarity.
- **Siblings**: `similarity_autofit` and the on-demand queue are fine. The same stop/start contract is used by the library-reset rollback path only.
- **Suggested Fix**: Make `start()` re-arm the stop state (`self._stop_event.clear()`; `self.should_stop = False`; clear `self.workers`) the way `FingerprintQueue.start()` does. Add a real-object stop-then-start test beside the `AsyncMock` ones.
- **Cross-audit overlap**: same defect as E6-04 in AUDIT_ENGINE_2026-10-22.md (fingerprint-queue half; the auto-scanner half is new here) (unpublished, same day). Publish once.

#### BE-D6-02: `FingerprintExtractionQueue.stop()` joins worker threads synchronously on the event loop for up to 30 s (library reset and shutdown)
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis/services/fingerprint_queue.py:173-203` (join at :196), awaited from `auralis-web/backend/config/background_workers.py:65` (`WORKER_STOP_KWARGS["fingerprint_queue"] = {"timeout": 30.0}`)
- **Status**: NEW
- **Description**: `stop` is declared `async def` but does `worker.join(timeout=remaining)` in a loop. `stop_background_workers` awaits the coroutine directly on the loop thread. Workers only check `should_stop` between tracks, and a track takes seconds to minutes (`track_timeout` defaults to 600 s). With any worker mid-extraction, the loop is blocked until the join times out. The 30 s budget is the whole `stop()` call, so the stall is up to 30 s. Compare #4775 (`Observer.join` blocked the loop for 5 s, fixed via `asyncio.to_thread`) and `LibraryAutoScanner.stop()`, which already offloads it.
- **Evidence**:
```python
async def stop(self, timeout: float = 30.0) -> bool:
    self.should_stop = True
    ...
    for worker in self.workers:
        remaining = timeout - (time.time() - start_time)
        ...
        worker.join(timeout=remaining)      # blocking, on the event loop
```
- **Impact**: `POST /api/library/reset` while fingerprinting is active (the common time to reset, right after an import) freezes every HTTP request and WebSocket frame for up to 30 s. The server heartbeat cannot be serviced (interval 30 s, timeout 10 s), so clients can be marked dead and drop. At shutdown the same stall delays teardown of every later step.
- **Siblings**: None in the lifespan. The other worker `stop()` methods await or offload.
- **Suggested Fix**: Run the join loop in `asyncio.to_thread` (or poll `is_alive()` with `await asyncio.sleep`).
- **Cross-audit overlap**: same defect as E6-05 in AUDIT_ENGINE_2026-10-22.md (unpublished, same day). Publish once.

#### BE-D6-03: The one multi-second GET (`/api/player/mastering/recommendation/{id}`) is outside the rate-limit table, and its cache key is a free float
- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware/rate_limit.py:50-55`; `auralis-web/backend/routers/enhancement_recommendation.py:24-120`; `auralis-web/backend/cache/recommendations_mixin.py:59,87`
- **Status**: NEW (relates to closed #3865, which only added caching)
- **Description**: `_RATE_LIMITS` covers four prefixes. The recommendation GET is not among them, though each uncached call builds a `ChunkedAudioProcessor` and runs a 1-5 s analysis (the handler's own comment). `OriginCheckMiddleware` does not gate GETs, so any page open in the user's browser can issue it blind (`new Image().src = ...`). The result cache is keyed `(track_id, confidence_threshold)`, and `confidence_threshold` is any float in `[0, 1]` (`Query(0.4, ge=0.0, le=1.0)`). Varying `?confidence_threshold=0.401, 0.402, ...` therefore misses the cache every time. Each call consumes a worker of the shared `IO_EXECUTOR`, which is also the loop's default executor used by every repository call (pool size 8). #5318 already established that cross-origin GETs are a supported-threat concern for this middleware.
- **Evidence**:
```python
cache_key = (track_id, confidence_threshold)          # recommendations_mixin.py:59
...
confidence_threshold: float = Query(0.4, ge=0.0, le=1.0, ...)   # no rounding / no snap
```
- **Impact**: A hostile page, or a buggy client loop, can pin all 8 I/O workers on repeated analyses (each bounded only by `CHUNK_PROCESS_TIMEOUT`). Every `to_thread` repository call then queues behind them, so the UI hangs. Browser Local Network Access prompts reduce, but do not remove, the exposure.
- **Siblings**: `GET /api/albums/{id}/fingerprint` and `GET /api/tracks/{id}/fingerprint` are DB-only and cheap, so they are not affected.
- **Suggested Fix**: Add `/api/player/mastering/recommendation` to `_RATE_LIMITS`. Quantise `confidence_threshold` (for example to 0.05 steps) before it is used as a cache key.

#### BE-D7-01: Normal-mode streaming still collapses libsndfile errors into the generic "Audio streaming failed" (incomplete fix of #5488)
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/job_error_mapping.py:28-91`; `auralis-web/backend/core/stream_normal.py:139-146,254-263`; `auralis-web/backend/core/stream_normal_chunks.py:86-95,230-244`
- **Status**: NEW (the enhanced/seek paths of closed #5488 are fine; the normal path never got an equivalent mapping)
- **Description**: #5488 made the three catch-alls call `_safe_error_message(e, default="Audio streaming failed")`, which maps `ModuleError` (what `unified_loader` raises) and a handful of stdlib types. The normal (unprocessed) path does NOT go through the unified loader for libsndfile formats: `stream_normal_audio` opens `.wav/.flac/.aiff/.aif/.au` with `sf.SoundFile(...)` directly (only `FFMPEG_FORMATS` are converted first). `soundfile.LibsndfileError` is `SoundFileRuntimeError -> RuntimeError`, which is neither a `ModuleError` nor in `_ERROR_CATEGORIES` (`OSError`/`ValueError`/`MemoryError`/...), so every corrupt, empty-header, truncated or vanished FLAC/WAV/AIFF falls to `default` and the user reads "Audio streaming failed". A missing file also raises `LibsndfileError` (not `FileNotFoundError`), so it too is generic here. Per-chunk read failures in `pump_normal_chunks` use fixed text ("Failed to stream audio chunk N") with the same `STREAMING_ERROR` code, so a permanent condition (file gone, unmounted drive) is indistinguishable from a transient one.
- **Evidence**:
  ```text
  # python-soundfile 0.14.0 in the project venv
  bad.wav  (random bytes)  LibsndfileError -> SoundFileRuntimeError -> SoundFileError -> RuntimeError
           _safe_error_message(e, default='Audio streaming failed') -> 'Audio streaming failed'
  trunc.flac               -> 'Audio streaming failed'
  missing.wav              -> 'Audio streaming failed'
  # same files through ChunkedAudioProcessor (enhanced path): 'Audio file could not be loaded',
  # 'Audio file is corrupted or unsupported', 'Audio file not found'
  ```
  ```python
  # stream_normal.py:140-146
  def _get_audio_info(filepath): with sf.SoundFile(filepath) as audio_file: ...
  sample_rate, channels, total_frames = await asyncio.to_thread(_get_audio_info, streaming_filepath)
  ```
- **Impact**: Playing the original (non-enhanced) version of a corrupt/truncated FLAC or WAV, or one deleted after validation, shows the same non-actionable text the closed issue was filed against, while the enhanced path for the same file says "corrupted or unsupported" / "not found". The wire `code` is the constant `STREAMING_ERROR` in every case, so the UI cannot branch on category (rescan vs retry) either.
- **Siblings**: `stream_normal_chunks.py:230-244` per-chunk text; all three `_send_error` catch-alls pass only the display string, never a category code.
- **Suggested Fix**: Map `soundfile.SoundFileError` (and `LibsndfileError`) in `_ERROR_CATEGORIES` ("Audio file could not be read or is corrupted"), or open the file in the normal path through the same loader/probe the enhanced path uses; consider returning the category as a stable `code` next to the text.

#### BE-D7-02: A skipped chunk is reported as an `audio_stream_error`, which the client treats as fatal, while the backend keeps streaming to a client that already tore down
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/stream_enhanced_chunks.py:246-271`; `auralis-web/backend/core/stream_normal_chunks.py:224-259`; client side `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:229-264`, `useAudioStreamingCore.ts:155-174`, `audioChunkIngest.ts:63-79`
- **Status**: NEW (cross-layer interaction of closed #3190 "skip failed chunk and continue" with closed #4655 "frontend auto-resumes from recovery_position")
- **Description**: On a per-chunk failure the pumps send `audio_stream_error` (with `recovery_position`), record the chunk in `failed_chunks`, and `continue` to render/stream the remaining chunks (#3190). The frontend handler for that same frame does `cleanupStreaming()` (disposes the PCM buffer and playback engine, nulls the stream metadata/epoch) and re-issues the stream once per distinct `(track_id, recovery_position)` (#4655). For a transient failure the re-issue works. For a deterministic failure (a chunk whose DSP/read always fails, e.g. a corrupt region or a NaN chunk) the re-issued stream fails on the same chunk, sends the same `recovery_position`, and the client's `alreadyAttempted` guard refuses to retry, so playback is dead at that point. The backend does not know: it keeps rendering and sending chunks `k+1..N`. Because the client has `initialized === false`, `classifyChunk` returns `'not-initialized'` and `handleChunk` pushes every one of them into `pendingChunksRef` (unbounded) until a new `audio_stream_start`. The terminal frame is then `reason="errored"`, which the client shows as "Playback ended with gaps", although there was no skipping: the first error already destroyed the playback engine.
- **Evidence**:
  ```python
  # stream_enhanced_chunks.py:246-271  (normal pump is the same shape)
  except Exception as chunk_error:
      ...
      await controller._send_error(websocket, track_id, f"Failed to process audio chunk {chunk_idx}",
                                   recovery_position=..., error_code=error_code)
      failed_chunks.append(chunk_idx)
      continue          # keeps rendering + sending chunk_idx+1 ...
  ```
  ```ts
  // useStreamMessageHandlers.ts:229-264
  handleStreamError: dispatch(setStreamingError(...)); cleanupStreaming();   // engine + buffer disposed
  if (... && !alreadyAttempted) { reissueActiveStreamAs(..., recoveryPosition) }   // once per (track, position)
  ```
- **Impact**: One permanently bad chunk (edge-case file) ends playback for the rest of the track with a misleading "ended with gaps" message, wastes the DSP/CPU for every remaining chunk, and grows the client's pending-chunk list by the rest of the track (hundreds of MB for a long track). The "skip and continue" design intent is never realised end to end.
- **Siblings**: both pumps; the TimeoutError branch already stops instead of continuing (`stream_enhanced_chunks.py:212-244`), so only the non-timeout branch has the mismatch.
- **Suggested Fix**: Make the two sides agree: either stop the stream after a chunk failure once the client has been told to resume from `recovery_position` (like the timeout branch), or add a non-fatal frame/flag (e.g. `fatal: false`) that the client records without disposing the engine. In the meantime cap consecutive failures the way the normal pump caps read timeouts.
- **Cross-audit overlap**: same defect as INT-F1-4 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D7-04: A degraded startup (library init rolled back) is invisible to the user: the app launches "healthy" and every data route 503s
- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/health.py:45-62`; `auralis-web/backend/config/startup/__init__.py:105-123`; `desktop/main.js:291-335`; `auralis-web/frontend/src/hooks/shared/useAPIHealthPoll.ts:34`
- **Status**: NEW (#4684 added the honest `auralis_available` field, but nothing reads it)
- **Description**: If `_init_library_database` (or any step of `_init_auralis_components`) raises (migration failure, locked or unwritable `~/.auralis`, corrupt DB), the lifespan logs the error, rolls every component back to `None` and carries on serving. `/api/health` deliberately stays `status: "healthy"` / HTTP 200 and reports the degradation only in `auralis_available: false`. The Electron supervisor waits for status 200 and ignores the body, the frontend poll calls `get('/api/health')` and ignores the payload, and a grep of the frontend and desktop code finds no consumer of `auralis_available`. The user therefore gets a window whose every library, player and settings request fails with 503 "Library not available", with no startup error dialog and no reason given anywhere outside the log file.
- **Evidence**:
  ```python
  # routers/health.py:59-62
  engine_ready = deps.has_auralis and (deps.get_library_database is not None and deps.get_library_database() is not None)
  return HealthResponse(status="healthy", auralis_available=engine_ready)
  ```
  ```js
  // desktop/main.js:300-318 - only statusCode === 200 is checked; the body is never parsed
  if (res.statusCode === 200) { resolve(); } else { reject(...); }
  ```
- **Impact**: The failure classes where a user most needs guidance (migration failed and was restored, DB locked by another Auralis instance, permissions) present as an empty, erroring UI. The only recovery is reading logs.
- **Siblings**: `config/startup/__init__.py` also catches processing-engine/streamlined-cache init failure and continues (`routers` then 503), same invisibility.
- **Suggested Fix**: Have the shell or the frontend health poll read `auralis_available` and show a blocking "Library failed to initialise" state (ideally with the init error category, kept path-free), or expose a `startup_error` field on the health payload for the poll to display.

#### BE-D8-01: The StreamlinedCacheWorker never does any work — `track_status` is never initialised, so every tick returns at "cache status is not initialized"
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/cache/playback_mixin.py:94-135`, `auralis-web/backend/routers/enhancement_controls.py:128-133,203-208`, `auralis-web/backend/core/streamlined_tiers.py:54-72`
- **Status**: NEW
- **Description**: `StreamlinedCacheManager.track_status[track_id]` is created in exactly one place: `update_position()`, and only when `track_changed and track_duration`. `update_position` has exactly two production callers (`set_enhancement_preset` and `set_enhancement_intensity`), and neither passes `track_duration`. So `track_status` stays empty for the life of the process. The worker's 1 Hz `process_priorities` therefore (a) returns immediately when `current_track_id` is `None` — which is true until the user first changes preset/intensity (the playing track is never reported to the cache manager; nothing else calls `update_position`, and `current_position` is only ever the value at the moment of that toggle), and (b) after the first toggle does one `tracks.get_by_id` DB round trip every second and then bails at `get_track_cache_status(track_id) is None`. `ensure_tier1_chunk`, `build_tier2_cache`, `_process_chunk`, `warm_tier1_immediately` and `trigger_immediate_processing` (which has no caller at all) are unreachable in production. The advertised "Tier 1 next-chunk / Tier 2 full-track pre-render / instant seek" behaviour does not exist, and `GET /api/cache/*` reports a permanently empty cache. Tests construct `TrackCacheStatus` / pass `track_duration` themselves, which is why this is not caught.
- **Evidence**:
  ```python
  # cache/playback_mixin.py:128
  if track_changed and track_duration:
      ...
      self.track_status[track_id] = TrackCacheStatus(...)
  # routers/enhancement_controls.py:128 and :203 — no track_duration
  await buffer_manager.update_position(track_id=state.current_track.id,
      position=state.current_time, preset=preset, intensity=intensity)
  # core/streamlined_tiers.py:69-72
  status = worker.cache_manager.get_track_cache_status(track_id)
  if status is None:
      logger.debug(f"Track {track_id} cache status is not initialized; skipping tick")
      return
  ```
- **Impact**: A whole performance subsystem (worker, tier-1/tier-2 dicts, per-consumer processor factory, eviction accounting, ~1000 lines incl. mixins) is inert; after any preset/intensity change the loop adds a pointless per-second DB query forever (until restart) and the track id is never cleared when playback stops or the track changes. Every behaviour documented in the module headers (and every fix like #4733/#5059/#5349/#5490 made to the dead path) is unverifiable in the running app. Seeks and track changes get no help from this layer.
- **Siblings**: `auto_mastering_enabled` is never set false either; `TrackCacheStatusResponse`/`cache_streamlined.py` stats are always empty. BE-D3-03 and BE-D4-07 describe defects inside the same unreachable path.
- **Suggested Fix**: Decide: either have the playback/stream start path report the real track (id, position, duration, preset, intensity) to `update_position(..., track_duration=...)` and keep it current, or delete the worker/tier path (CLAUDE.md "no variants / dead code" rule) and keep only the pieces the routers still use (recommendation cache).

---
- **Cross-audit overlap**: same defect as INT-F3-5 (related: look-ahead fed from REST player state) in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D8-02: Every player-state mutation and every `get_state()` deep-copies, serialises and broadcasts the entire queue (up to 50 000 tracks) on the event loop
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/core/state_manager.py:44-46,63,201-203`; `auralis-web/backend/player_state.py:60-100` (`queue: list[TrackInfo]`); `auralis-web/backend/schemas/request_bounds.py:33` (`MAX_TRACK_ID_LIST = 50_000`)
- **Status**: NEW
- **Description**: `PlayerState` carries the full `queue`. `_mutate_state` returns `self.state.model_copy(deep=True)` (under the asyncio lock) and `_broadcast_state` does `state.model_dump()` and then JSON-encodes it to every client; `get_state()` is the same deep copy. #2570 moved only the 1 Hz `position_changed` tick off this path; every play/pause/volume/mute/track-change/repeat/queue edit still pays O(queue). `get_state()` is also called by the enhancement toggles, `GET /api/player/status`, queue enrichment (`resolve_tracks` and `resolve_repeat_mode`, i.e. twice per `GET /api/player/queue`), seek and each WebSocket connect — all synchronously on the loop. The queue is allowed to be 50 000 entries (a "play whole library" action).
- **Evidence**: Measured with `PlayerState(queue=[TrackInfo(...)]*n)`:
  ```
  n=1000   deepcopy  2.3 ms  dump  0.5 ms  json  0.5 ms  171 KB
  n=5000   deepcopy 12.5 ms  dump  2.3 ms  json  2.8 ms  866 KB
  n=20000  deepcopy 51.1 ms  dump 10.2 ms  json 11.3 ms  3.5 MB
  ```
  (≈ 75 ms of loop-blocking and a 3.5 MB frame per client per mutation at 20 000 tracks; ≈ 200 ms / 8.7 MB at the 50 000 cap.)
- **Impact**: With a large queue, dragging the volume slider (one `update_state` per request), pausing, or skipping stalls the loop for tens to hundreds of ms per event — the same loop that paces WebSocket audio frames — and floods the socket with multi-MB `player_state` frames. Scales with library size, not with anything the user did.
- **Siblings**: `QueueInfoResponse` for `GET /api/player/queue` legitimately returns the queue (not in scope here); the `ws_handlers/connection.py:155` initial-state send has the same cost once per connect.
- **Suggested Fix**: Keep the queue out of `PlayerState` snapshots/broadcasts (broadcast `queue_size`/`queue_index` and a queue-changed event; queue contents are fetched via the queue endpoint), and make `get_state()` a shallow `model_copy()` (the queue list can be replaced, never mutated in place) so it is O(1).

---

#### BE-D8-03: `GET /api/artists/{id}` and `/tracks` share an over-wide eager-load set that still misses `Album.artist` — one WARNING per album per request
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis/library/repositories/artist_repository.py:73-77,102-111`; `auralis-web/backend/routers/artists.py:151-189,195-231`
- **Status**: NEW
- **Description**: Both artist detail routes call `ArtistRepository.get_by_id()`, which applies `_ARTIST_DETAIL_OPTIONS = (selectinload(Artist.tracks).selectinload(Track.genres), selectinload(Artist.tracks).selectinload(Track.album), selectinload(Artist.albums).selectinload(Album.tracks))`. (1) The set is the union of what neither route needs: `get_artist` reads only per-album `track_count`/`total_duration`, `year`, `title` and `len(artist.tracks)`; `get_artist_tracks` reads `track.album` only. Each hydrates every Track of the artist (and every track of every album, so a compilation drags in other artists' tracks) up to twice, including genres and the unbounded `lyrics`/`comments`/`fingerprint_vector` columns — the exact over-fetch #5084 removed for the list. (2) `Album.to_dict()` (via `serialize_album`) reads `album.artist`, which the options do not load; the album objects are expunged, so each access raises `DetachedInstanceError`, which `_safe_scalar` swallows and logs.
- **Evidence**: Scratch library (5 artists, 10 albums, 60 tracks), `artists.get_by_id` then serialising `artist.albums` and `artist.tracks`:
  ```
  artists.get_by_id   stmts=6 warnings=14
  "Album.artist could not be loaded (detached instance?); reporting None.
   The owning repository is missing a joinedload/selectinload(Album.artist)."
  ```
  (albums/tracks/genres/artists list reads in the same probe were 2-5 statements, 0 warnings.)
- **Impact**: Opening an artist page for an artist with N albums writes N WARNING lines each time, and loads 2x(tracks) rows plus genres for a response that needs counts. It is the "missing `selectinload()` on a list" shape from the special rules (the albums list inside the artist detail), and it will keep emitting noise that hides real detached-instance regressions.
- **Siblings**: `ArtistRepository.get_all_artists()` (`:236-255`) loads `Artist.tracks` twice (`selectinload(Artist.tracks).selectinload(Track.album)` plus a bare `selectinload(Artist.tracks)`).
- **Suggested Fix**: Give the album-list part of the artist detail the same treatment as `_ALBUM_LIST_OPTIONS` (`joinedload(Album.artist)` + `track_count_expr`/`total_duration_expr` via `with_expression`) and give `get_artist_tracks` its own minimal set (`Artist.tracks` -> `Track.album`, `Track.genres` only if serialised); drop the duplicate `selectinload(Artist.tracks)` in `get_all_artists`.

---
- **Cross-audit overlap**: same defect as INT-F2-6 (partial; the missing `Album.artist` eager-load is new here) in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D8-04: `POST /api/files/upload` decodes the entire upload into RAM (up to the 6 GiB guard) just to read duration/sample rate/channels, while holding the whole compressed file in memory too
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/backend/routers/files_upload.py:86-97,121-125`; sibling `auralis-web/backend/routers/processing_upload.py:114-130`
- **Status**: NEW
- **Description**: The handler reads the whole body into a `bytes` (`await file.read(_MAX_UPLOAD_BYTES + 1)`, up to 500 MB), writes it to a temp file, then calls `load_audio(temp_path)` and uses only `len(audio_data) / sample_rate`, `sample_rate` and `audio_data.shape[1]`. `load_audio` decodes the complete track to a float array; its guard (`MAX_DECODED_BYTES`, default 6 GiB, `auralis/io/loader.py:55-63`) allows multi-GiB allocations. A header probe already exists and is what the rest of the backend uses for this exact purpose: `get_audio_info()` (used in `routers/enhancement_prewarm.py:88` and `core/chunk_metadata.py:82`). `content` and `audio_data` both stay referenced until the loop iteration ends, so peak memory is compressed size + decoded size. `processing_upload.py` has the same read-all-into-`bytes` step (500 MB) before it writes the file.
- **Evidence**:
  ```python
  content = await file.read(_MAX_UPLOAD_BYTES + 1)            # files_upload.py:86
  ...
  audio_data, sample_rate = await asyncio.to_thread(load_audio, temp_path)   # :124
  duration = len(audio_data) / sample_rate
  ...
  "channels": 1 if audio_data.ndim == 1 else audio_data.shape[1]
  ```
- **Impact**: Dropping one long FLAC/DJ-mix into the library can transiently allocate several GiB (and minutes of decode) on the 8-worker I/O pool, risking OOM on a desktop machine and starving every repository call for the duration; the work is thrown away immediately. Per-file in a multi-file upload this repeats.
- **Siblings**: `processing_upload.py:114-130` (whole upload in RAM, then written); BE-D1-06/BE-D1-12 are other defects in the same handlers.
- **Suggested Fix**: Stream the upload to the temp file in chunks (`shutil.copyfileobj` in a thread, checking the magic bytes on the first 12 bytes and the size on the fly) and take duration/sample rate/channels from `get_audio_info()`.

---

#### BE-D8-05: A full library scan retains every added `Track` ORM object (and its relationship graph) until the scan returns — roughly 10 KB per track
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis/library/scanner/batch_processor.py:74-76`, `auralis/library/scanner/scan_stages.py:216-217`; consumers `auralis-web/backend/routers/library_scan_events.py:114-135`, `auralis-web/backend/services/auto_scan_events.py:90-98`
- **Status**: NEW
- **Description**: `process_file_batch` appends the detached `Track` returned by `tracks_repo.add()` to `ScanResult.added_tracks`, and `_process_batch` extends the scan-wide result with it. The only consumers are the two fingerprint-enqueue helpers, which read `t.id` and nothing else. Each retained `Track` is a fully populated instance (all ~40 columns including `lyrics`/`comments`, plus the eagerly loaded artists/album/genres it was returned with), and because every `add()` uses its own session, relationship objects are not shared between tracks.
- **Evidence**: Retaining the objects returned by `TrackRepository.add()` for 2 000 synthetic tracks (tracemalloc, warm process):
  ```
  no-retain  0.014 KB/track
  retain    10.28 KB/track
  ```
  i.e. ≈ 1 GB for a first import of 100 000 files, held for the whole scan and released only when the REST/auto-scan handler finishes the enqueue.
- **Impact**: First import (or a re-index after a library reset) of a large collection pushes the Electron backend's RSS up by ~10 KB per file for the entire scan, on top of the audio-analysis working set; weak machines can swap or be OOM-killed mid-scan. The same retention happens on each hourly auto-scan only for newly added files, so it is a first-import/bulk-add problem.
- **Siblings**: none in the scan path; `ScanResult.failures` is already capped (`MAX_RECORDED_FAILURES`).
- **Suggested Fix**: Record only the new track ids (`added_track_ids: list[int]`) and change the two enqueue helpers to iterate ids; or enqueue fingerprints per batch from the feeder.

---

#### BE-D9-01: The two "queue full" tests for #2332 never reach the real engine, so the dead 503 contract (BE-D4-02) and the `stop()` hole (BE-D4-03) stay green
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_processing_api.py:722-741` (and `:838`); `tests/backend/test_processing_job_persistence_5278.py:165-173`; `tests/backend/test_worker_task_lifecycle.py:219-380`
- **Status**: NEW (the contract-regression itself is BE-D4-02, a regression of #2332)
- **Description**: `TestQueueBackpressureAPI` is labelled "503 responses when the processing queue is full (issue #2332)". It sets `mock_engine.submit_job = AsyncMock(side_effect=asyncio.QueueFull())`, so it only proves the router maps an exception it injects itself. The one test that uses a real `ProcessingEngine` (`test_a_job_rejected_by_a_full_queue_is_not_persisted`, `max_queue_size=1`) never starts the worker. With no dispatcher draining `job_queue`, `put_nowait` fills, which is exactly why the bound appears to work there. In production `JobWorker.start()` drains the queue immediately into semaphore-parked `_run_job` tasks, so `QueueFull` never fires (BE-D4-02). Likewise every `TestStopDrainsInFlightJobs` test (#4543) runs exactly one job against free slots, so a job parked on the semaphore (BE-D4-03) is never constructed.
- **Evidence**:
  ```python
  # test_processing_api.py:728
  mock_engine.submit_job = AsyncMock(side_effect=asyncio.QueueFull())
  # test_processing_job_persistence_5278.py:166  (no start_worker anywhere in the file)
  engine = _engine(db_path, max_queue_size=1)
  await engine.submit_job(await engine.create_job(input_path="/a.wav", settings={}))
  with pytest.raises(asyncio.QueueFull):
  ```
  `grep -n "start_worker\|\.start()" tests/backend/test_processing_job_persistence_5278.py` returns nothing.
- **Impact**: The acceptance criterion of #2332 ("503 when full") is reported as pinned but is dead in production, with a green suite. Any fix to BE-D4-02/03 has no failing test to drive it.
- **Siblings**: `test_upload_and_process_returns_503_when_queue_full` (`test_processing_api.py:838`) has the same mock-injected shape.
- **Suggested Fix**: Add a real-engine test that starts the worker with `max_concurrent_jobs=1` and a blocking `process_job`, submits more than `max_queue_size` jobs, and asserts `QueueFull` / 503. Add a `stop()` test with more jobs than slots that asserts no parked job starts after `stop()`.

#### BE-D9-02: The only real-DSP "total sample count" test is stale and one-sided, and exact tiling is proven only against a hand-built buffer
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_chunked_processor_invariants.py:338-421` (also `:204-285`); `tests/backend/test_chunk_count_no_silence_padding.py:41-53`
- **Status**: NEW
- **Description**: `test_processed_chunks_concatenate_to_correct_duration` is headed "CRITICAL INVARIANT" and is the only test that runs `process_chunk` over every chunk of a real 90 s file and sums the output. It still models the retired overlapping-segments design: `rough_expected = total_duration + (n-1)*OVERLAP`, plus a 50 % tolerance. It asserts only `total_duration < rough_expected + tolerance` (an upper bound), with no lower bound and no equality. Output that is 40 s too long still passes, as does a track that is missing whole chunks, provided each file is non-empty. The sibling `test_processing_preserves_sample_count_per_chunk` checks chunk 0 only, with 1 % tolerance (about 6,600 samples). The exact, gapless, sample-preserving sweep tests (`test_sweep_total_samples_preserved_no_padding`) run `extract_chunk_segment` over `_trimmed_buffer()`, the test's own re-implementation of what the loader returns. They do not run the real loader plus DSP plus trim composition. `CLAUDE.md` makes "sample count preservation is critical for gapless playback" the first audio invariant, and the real pipeline never asserts it exactly.
- **Evidence**:
  ```python
  # test_chunked_processor_invariants.py:411-421
  expected_overlap_seconds = max(0, (processor.total_chunks - 1) * OVERLAP_DURATION)
  rough_expected = processor.total_duration + expected_overlap_seconds
  tolerance = processor.total_duration * 0.5
  assert total_duration < rough_expected + tolerance, (...)
  ```
  For the 90 s fixture the bound is `90 + 40 + 45 = 175 s`, against a true expected 90.0 s.
- **Impact**: A regression that duplicates or drops chunk audio in `ChunkedAudioProcessor.process_chunk` / `extract_chunk_segment` passes this "critical" test, and gapless playback breaks audibly.
- **Siblings**: `test_chunks_cover_entire_duration_no_gaps` / `test_chunk_boundaries_are_continuous` (same file) still use the "next_start <= curr_end (for overlap)" model and a 0.5 s tolerance. The `test_audio_just_over_chunk_duration` docstring (`test_chunked_processor_boundaries.py:152-179`) claims chunk spans but asserts only `len(chunk) > 0`.
- **Suggested Fix**: Replace the test with `sum(len(load_audio(chunk_path)) for all chunks) == total source samples` (exact), and add a per-chunk length check against `content_chunk_count` / chunk geometry from `chunk_boundaries.py`.

#### BE-D9-03: Every `slow`-marked test is excluded from CI and nothing ever runs them; that includes the only real-engine REST-to-engine test
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `.github/workflows/backend-tests.yml:134` (`-m "not slow"`); `pytest.ini:35`; `tests/integration/test_processing_engine_end_to_end.py:54`
- **Status**: NEW (same family as closed #4781 / #5095, which were CI exclusions of hanging files)
- **Description**: `pytest.ini` documents `slow` as "run nightly", but the repo has no nightly or scheduled test workflow (`grep schedule .github/workflows/*` finds only `rust-audit.yml`). CI is the only automated runner and it deselects `slow`. So these never run anywhere automated: `test_upload_and_process_end_to_end_with_real_engine` (the only test driving `POST /upload-and-process` through a real `ProcessingEngine`, real `HybridProcessor`, real save, status poll and download, written for #3819/#3489), 7 `tests/integration/test_api_workflows.py` / `test_e2e_workflows.py` workflows, 5 tests in `tests/backend/test_concurrent_operations.py`, `tests/concurrency/test_migration_lock_identity_4523.py`, and the `test_boundary_*` stress tests. The e2e test is not even slow: run alone it passed in 1.04 s, so its `slow` mark (documented as >1 s) is what drops it.
- **Evidence**:
  ```
  pytest.ini:35   slow: Tests that take a long time to run (> 1s) - run nightly
  backend-tests.yml:134   python -m pytest -q -m "not slow" -p no:randomly --junitxml=pytest-results.xml || true
  tests/integration/test_processing_engine_end_to_end.py:54   @pytest.mark.slow
  $ pytest -q tests/integration/test_processing_engine_end_to_end.py   ->  1 passed in 1.04s
  ```
- **Impact**: The sole guard against a "#3489-class" REST-to-engine regression, and the concurrency tests, give no CI signal. They can rot unnoticed; the baseline ratchet cannot flag a test that never runs.
- **Siblings**: `tests/integration/test_end_to_end_processing.py:594` and `tests/edge_cases/*` carry the same mark.
- **Suggested Fix**: Drop the `slow` mark from the 1 s e2e test, and either add a scheduled workflow that runs `-m slow` or stop documenting "nightly".

#### BE-D10-01: The disk-hit path runs the size pruner before returning the file it just validated, so a cache hit can hand back a path the pruner has just deleted
- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/core/chunk_path_cache.py:89-113` (`lookup_cached`), `auralis-web/backend/core/chunk_cache_manager.py:194-230` (`cache_chunk_path` -> `_maybe_prune`), `auralis-web/backend/core/chunk_disk_prune.py:46-84,118-130`, consumer `auralis-web/backend/core/chunk_streaming.py:81-94`
- **Status**: NEW
- **Description**: Every `ChunkedAudioProcessor` starts with an empty in-memory `chunk_cache` dict (the live stream, seek, prewarm, proactive buffer and recommendation paths all pass none or `{}`), so each chunk it reuses from an earlier play is a *disk* hit. `lookup_cached` validates the WAV (`exists()` + `is_wav_complete()`) and then calls `cache_chunk_path(cache_key, wav_chunk_path)` to record it. That method calls `_maybe_prune(path.parent)` unconditionally; the throttle counter is incremented by hits as well as writes, so on every 32nd hit/write the reaper runs synchronously, in the same call, *before* `lookup_cached` returns the path. The reaper deletes oldest-mtime-first until the directory is under 512 MB, with no `keep` exemption (unlike the thumbnail pruner's `keep=dst`). A hit does not refresh mtime, so the chunk you are replaying is exactly the kind of old file the reaper selects. The path is then returned to a caller (`process_chunk` immediately `load_audio`s it) that finds it gone. `prune_chunk_directory`'s docstring claims "the coldest tracks' WAVs are reclaimed first" and that a deleted file is safely a miss because `get_cached_chunk_path` re-checks existence, but that check happened *before* the prune and nothing re-checks afterwards.
- **Evidence**:
  ```python
  # chunk_path_cache.py:105-108
  if wav_chunk_path.exists():
      if is_wav_complete(wav_chunk_path):
          self._cache_manager.cache_chunk_path(cache_key, wav_chunk_path)   # -> _maybe_prune(dir) runs HERE
          return wav_chunk_path                                              # may no longer exist
  # chunk_cache_manager.py:224-230 (tail of cache_chunk_path)
  self._cache[cache_key] = str(path)
  self._maybe_prune(path.parent)          # no keep=path
  ```
  Reproduction (`scratchpad/d10/prune_hit.py`): six real chunk WAVs written through `WAVEncoder`, chunk 0 given the oldest mtime, a fresh `ChunkCacheManager({}, max_disk_bytes=4.5 files, prune_every=1)` and `ChunkPathCache.lookup_cached(0)`:
  ```
  lookup_cached(0) returned v4_track_7_abcd1234_adaptive_1.0_none_chunk_0.wav exists on return: False
  ```
  Downstream, `process_chunk` does `audio, _ = load_audio(str(cached_path))` with no fallback; `load_audio` on a missing path raises `ModuleError: File not found`, which reaches the pump's skip-failed-chunk branch (a ~10 s gap and, per BE-D7-02, an `audio_stream_error`). `get_wav_chunk_path` (prewarm) instead returns the dead path and logs "output file not found".
- **Impact**: Only when the directory is over the 512 MB cap, which in a session (the cache is wiped at launch) means roughly 45+ minutes of enhanced 44.1 kHz stereo audio, sooner for hi-res sources (a 96 kHz stereo chunk is ~3.8 MB). In that state, replaying material from near the start of the cache window (a seek back, "previous track" after a long run) can lose the chunk it is trying to serve exactly when the 32-call throttle fires; the user hears a skipped chunk or a stream error and a retry works (the file is gone, so it re-renders). Not data loss, but a deterministic race with the reaper rather than a rare timing window. The same TOCTOU applies to `POST /api/cache/clear` and `DELETE /api/cache/track/{id}` landing between a lookup and the read.
- **Siblings**: `ChunkCacheManager.cache_chunk_path` is also reached from `process_chunk`/`get_wav_chunk_path` after a write (safe there: the new file has the newest mtime). `proactive_buffer._buffer_chunk` (`chunk_path.exists()`) and `enhancement_prewarm` (`os.path.exists`) check existence only; harmless today because publication is atomic. `prune_thumbnail_cache` is also write-time-FIFO (hits never refresh mtime) but exempts the served file.
- **Suggested Fix**: Do not prune from the hit path (only `_maybe_prune` when the call actually added a new file), or pass the registered path as an exemption; refresh mtime (`os.utime`) on a hit so the reaper really is LRU as documented; and make `process_chunk`'s hit branch fall through to a re-render on `FileNotFoundError`/`ModuleError`.

#### BE-D11-02: A rate-limited (or otherwise rejected) `seek` is answered with a generic `error` frame after the client has already torn its playback down, and the server keeps the old stream running
- **Severity**: MEDIUM
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/routers/system.py:47,140-152` (limiter exempts only ping/pong/heartbeat), `auralis-web/backend/config/limits.py:201` (10 msg/s), `auralis-web/backend/ws_handlers/playback_commands.py:387-396`; client `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:64-92`, `components/player/useProgressBarInteraction.ts:176-191`, `components/player/progressBarMath.ts:8,44-56`, `hooks/websocket/useWebSocketErrors.ts`
- **Status**: NEW
- **Description**: `seek` is rate-limited together with every other command (per-connection 10 messages per second; `buffer_full`/`buffer_ready`/`pause`/`stop` share the bucket). The progress bar has `role="slider"` with `onKeyDown` and no `event.repeat` guard; every ArrowLeft/Right/Up/Down press is "a deliberate, discrete seek" of 1 s, so holding a key produces ~30 `seek` frames per second. In steady state about 10 per second are accepted and about 20 are answered with `{"type":"error","error":"rate_limit_exceeded"}`. The client performs `stopPlayback()`, `pcmBuffer.reset()`, `setIsSeeking(true)`, clears `pendingChunks`/`lastReceivedChunkIndex` *before* sending each seek, and the only consumer of the `error` frame is a toast (`useWebSocketErrors`). A rejected seek therefore leaves the client with an empty buffer, a stopped engine and `isSeeking === true` (cleared only by a later `seek_started`/`audio_stream_start`), while the server never saw the request: `_cancel_prior_task` did not run, the previous (accepted) stream keeps running under the **same** epoch, and its next frames are ingested into the reset buffer. Whether the final keypress was accepted is a coin toss weighted ~2:1 against, so the position the user ends on frequently does not match the audio/clock the client is playing. The same bucket also silently drops `stop`/`pause`/`resume` and `buffer_*` (the `buffer_ready` case is the sibling already noted in BE-D2-01).
- **Evidence**:
  ```python
  # routers/system.py:142-152
  if message.get("type") not in _RATE_LIMIT_EXEMPT_TYPES:      # {"ping","pong","heartbeat"}
      allowed, error_msg = _rate_limiter.check_rate_limit(websocket)
      if not allowed:
          await send_error_response(websocket, "rate_limit_exceeded", ...)
          continue                                            # seek never reaches handle_seek
  ```
  ```ts
  // useEnhancedSeek.ts -- state is destroyed on SEND, not on acknowledgement
  setIsSeeking(true); core.playbackEngineRef.current?.stopPlayback(); core.pcmBufferRef.current?.reset();
  wsContext.send({ type: 'seek', data: { track_id: trackId, position } });
  // useWebSocketErrors.ts -- the only handler of the rejection
  useWebSocketMessages(['error'], (m) => warning(m.message || 'An error occurred'));
  ```
- **Impact**: Held-key (accessibility) scrubbing on the progress bar can end in a desynchronised player: stopped or mid-stream audio, a position clock that does not match the stream, a stuck seeking flag, and one toast per dropped key. No data loss; recovered by the next accepted seek or a track restart.
- **Siblings**: `stop`, `pause`, `resume`, `buffer_full`, `buffer_ready` are in the same bucket (same silent-drop shape; a dropped `stop` leaves the stream running).
- **Suggested Fix**: Exempt the playback-control frames (or give them their own, generous bucket) from the per-message limiter, and/or coalesce seeks latest-wins in the receive loop; independently, answer a rejected `seek` with a typed `seek_rejected` that the client uses to restore its state, and ignore auto-repeat (`event.repeat`) in the progress-bar key handler.
- **Cross-audit overlap**: same defect as INT-F5-6 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

### LOW (46)

#### BE-D1-11: `GET /api/artists?search=...` silently ignores `order_by` (sibling of the fixed album case)
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/artists.py:93-107`; `auralis/library/repositories/artist_repository.py:185-225`
- **Status**: NEW (sibling of closed #2852, which fixed albums only)
- **Description**: `order_by` is validated as `Literal['name','album_count','track_count']`, but in the `search` branch the handler calls `repos.artists.search(search, limit=, offset=)` without it, and `ArtistRepository.search()` has no `order_by` parameter and hard-codes `.order_by(Artist.name)`. A client that sorts by `track_count` and then types in the search box gets the sort silently dropped; the schema accepted the value and nothing says it was ignored. Albums (`albums.py:84`) and tracks (`tracks.py:79`) forward `order_by` to `search()`.
- **Evidence**: `artists, total = await asyncio.to_thread(repos.artists.search, search, limit=limit, offset=offset)` vs `repos.albums.search, search, limit=limit, offset=offset, order_by=order_by`.
- **Impact**: Inconsistent ordering between search and non-search listings for artists.
- **Siblings**: none in routers; the repository method is the other half.
- **Suggested Fix**: Give `ArtistRepository.search()` the same `order_by` handling as `get_all()` (share the order-column builder) and pass it from the handler.
- **Cross-audit overlap**: same defect as INT-F2-12 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D1-12: Uploaded file is moved into `~/.auralis/uploads` before the DB insert and is never removed when the insert fails
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/files_upload.py:130-175`
- **Status**: NEW
- **Description**: `upload_files` writes the upload to a temp file, decodes it, then `shutil.move`s it to `~/.auralis/uploads/<uuid><suffix>` and only afterwards calls `repos.tracks.add(track_info)`. When `tracks.add` returns `None` (it rolls back and returns None on any error) the handler appends `"Failed to add track to library"`, and when it raises, the `except Exception` appends a per-file error. The `finally` block only unlinks `temp_path`, which `shutil.move` already consumed, so the permanent copy (up to 500 MB) is left behind with no DB row pointing at it. Nothing sweeps `~/.auralis/uploads` (the startup sweep from #4762 covers the tmp dirs only).
- **Evidence**: `await asyncio.to_thread(shutil.move, str(temp_path), str(permanent_path))` ... `track = await asyncio.to_thread(repos.tracks.add, track_info)` ... `else: results.append({... "Failed to add track to library"})` -- no `permanent_path.unlink()`.
- **Impact**: Each failed upload (e.g. database busy/locked, or `_validate_and_normalize_track_info` rejecting the payload) permanently leaks a full audio file into the user's home directory.
- **Siblings**: none in routers (`processing_upload.py` cleans its input on failure, line 169).
- **Suggested Fix**: Track `permanent_path` and unlink it in the failure branches (or insert first with the temp path and move after commit).

#### BE-D1-13: `GET /api/audio/formats` advertises `.mp3` output (always a 422) and a `sample_rates` list the offline pipeline ignores
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/files.py:100-114` (derivation), `auralis-web/backend/routers/processing_models.py:20-26,52-75` (`output_format` Literal + validator)
- **Status**: NEW
- **Description**: `output_formats` and `bit_depths` are read from the `Literal` annotations of `ProcessingSettings`, which still list `"mp3"`; the model's `_validate_format_bit_depth_combo` then rejects `output_format='mp3'` unconditionally ("no (mp3, bit_depth) combination can currently succeed"). The endpoint therefore returns `['.flac', '.mp3', '.wav']` for a format no request can use (verified against the live model). The inline comment says "these are the options, not a matrix", which covers invalid *pairs*, not a value that is never valid. `sample_rates` is a hard-coded list, though `create_processor_config` accepts `sample_rate` and ignores it (`job.ignored_settings`, #5060). The OpenAPI schema for `ProcessingSettings.output_format` has the same lie.
- **Evidence**: `sorted(get_args(ProcessingSettings.model_fields['output_format'].annotation))` -> `['flac','mp3','wav']`; `ProcessingSettings(output_format='mp3')` -> `ValidationError`.
- **Impact**: Any client building a format picker from this endpoint offers an option that always fails. (The shipped frontend does not call the endpoint today, so there is no user-visible effect yet.)
- **Siblings**: none.
- **Suggested Fix**: Drop `"mp3"` from the Literal (the validator already encodes why) and omit or flag `sample_rates` as not applied.

#### BE-D1-14: `GET /api/player/mastering/recommendation/{id}` re-implements `RecommendationService._get_or_analyze` instead of calling it
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/enhancement_recommendation.py:64-140` vs `auralis-web/backend/services/recommendation_service.py:50-100`
- **Status**: NEW
- **Description**: Both implement the same sequence -- `validate_file_path` re-check, `streamlined_cache_manager.get_mastering_recommendation`, build `ChunkedAudioProcessor(..., preset=DEFAULT_PRESET, intensity=1.0, chunk_cache={})` in a thread, `wait_for(..., CHUNK_PROCESS_TIMEOUT)`, `rec.to_response(track_id)`, `set_mastering_recommendation`. They already differ (the router maps `TimeoutError` to a 500 and turns `None` into a 500, the service returns `None`; the router passes the singleton cache, the service takes it by constructor), and every fix (#5248 timeout, #4817 path re-check) has to be applied twice. The route also reaches for the module-level `cache.streamlined_cache_manager` singleton although its router already injects the cache (`_get_streamlined_cache` in `enhancement_deps.py`), so it ignores `HAS_STREAMLINED_CACHE`/startup rollback. CLAUDE.md principle 1 (DRY) applies; the router should delegate to the service and keep only the HTTP mapping.
- **Evidence**: duplicated blocks quoted above; neither imports the other.
- **Impact**: Maintenance drift only today.
- **Siblings**: none.
- **Suggested Fix**: Inject `RecommendationService` into the route (it is already a `Depends` provider for the player router) and map its `None`/`TimeoutError` to the HTTP errors.

#### BE-D1-15: `GET /api/cache/health` hard-codes the tier size ceilings instead of using the cache manager's constants
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:174-182`; constants in `auralis-web/backend/cache/models.py:34-50`
- **Status**: NEW
- **Description**: `cache_health` decides `healthy` from `tier1["size_mb"] <= 15  # Should be ~12 MB`, `tier2["size_mb"] <= 250  # Max 240 MB`, `total <= 260`. `cache/models.py` defines the real limits (`TIER1_MAX_SIZE_MB = TIER1_MAX_CHUNKS * CHUNK_SIZE_MB * 2`, documented as ~10 MB, and `TIER2_MAX_SIZE_MB = 240`), and `CHUNK_SIZE_MB` is derived from the (16-bit PCM) chunk geometry. The route's numbers are hand-typed copies with a stale comment (~12 vs ~10 MB), so any change to chunk geometry or the tier limits silently makes the health verdict meaningless (always healthy, or never).
- **Evidence**: `tier1_healthy = tier1["size_mb"] <= 15`, `tier2_healthy = tier2["size_mb"] <= 250` vs `TIER1_MAX_SIZE_MB`, `TIER2_MAX_SIZE_MB` imported by `cache/manager.py`.
- **Impact**: Misleading health indicator in the cache monitor widget.
- **Siblings**: none.
- **Suggested Fix**: Import `TIER1_MAX_SIZE_MB`/`TIER2_MAX_SIZE_MB` and compare against those (plus a small tolerance constant).

#### BE-D1-16: Synchronous filesystem probing on the event loop in async handlers (`validate_file_path` incl. a 1000-track batch loop, artwork GET)
- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `auralis-web/backend/routers/metadata_batch.py:73-91` (loop of up to `MAX_BATCH_UPDATES = 1000` sync `validate_file_path` calls), `routers/metadata_deps.py:43-67` (called inline by 3 handlers; `update_track_metadata` calls it twice), `routers/enhancement_recommendation.py:68-77`, `routers/tracks.py:185-186`, `routers/processing_api.py:94-114`, `routers/artwork.py:136-157,197` (`resolve()`, `exists()`, `stat()` on the per-image hot path); implementation `security/path_security.py:167-192,254-291`
- **Status**: NEW (the earlier event-loop sweeps #3911/#4653/#5527 covered mkdir, file writes and `enqueue`, not these)
- **Description**: Every repository call in these handlers is offloaded with `asyncio.to_thread`, but `validate_file_path()` is called directly in the coroutine. Each call does `Path.resolve()` (one lstat per component), `get_allowed_directories()` (an `exists()` + `resolve()` for every allowed directory, including every registered scan folder), then `exists()`, `is_file()` and `os.access()`. `batch_update_metadata` repeats that for each of up to 1000 tracks in one uninterrupted loop on the loop thread, and `get_album_artwork` adds `resolve()/exists()/stat()` to the most frequently hit image route. On local NVMe this is cheap (about 45 microseconds per call measured on this machine, so about 45 ms for 1000), but a scan folder on a NAS/SMB mount or a spun-down external disk -- the common audiophile layout, and exactly what the `parent.exists()` guard in `cleanup_missing_files` (#2525) anticipates -- turns each syscall into a network/spin-up round trip, freezing the loop (and with it WebSocket audio delivery) for the whole batch.
- **Evidence**: `validated_filepath = str(validate_file_path(str(track.filepath), context=...))` inside `for update_req in request.updates:` in an `async def`, no `to_thread`.
- **Impact**: Conditional on slow storage; stalls streaming and other requests while a batch metadata edit validates, or while artwork requests stat a slow mount.
- **Siblings**: `core/stream_track_resolution.py:60-76` already wraps the same call in `asyncio.to_thread` -- the pattern to copy.
- **Suggested Fix**: Offload the whole validation loop (`await asyncio.to_thread(_validate_all, ...)`) and wrap the single-call sites the way `resolve_and_validate_track` does; same for the artwork path checks.

#### BE-D2-04: Omitted or `null` `data`, or a non-numeric `start_position`, turns a malformed command into `internal_error`
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:189,251,328,337,383`; `auralis-web/backend/routers/system.py:154-169`
- **Status**: NEW
- **Description**: `WebSocketMessageBase.data` is `dict | None` and `model_dump()` always emits the key, so `{"type": "play_normal"}` yields `{'data': None}`. `message.get("data", {})` returns `None` (the key exists), and `data.get("track_id")` raises `AttributeError`. Likewise `float(data.get("start_position", 0.0) or 0.0)` raises `ValueError` for a non-numeric string (a truthy non-numeric value skips the `or`). Both fall into the endpoint's generic handler, which logs at ERROR with a traceback and replies `internal_error` / "Command failed" instead of the typed `invalid_track_id` / validation error the neighbouring checks produce. The connection survives (#4771), so this is only a wrong error code and log noise; `force=bool("false")` is `True` for the same reason.
- **Evidence**:
  ```python
  data = message.get("data", {})              # None when the client omitted/nulled data
  track_id = data.get("track_id")             # AttributeError: 'NoneType' ...
  start_position = float(data.get("start_position", 0.0) or 0.0)   # ValueError on "abc"
  ```
  Verified: `WebSocketMessageBase.model_validate({'type':'play_normal'}).model_dump()` -> `{'type': <PLAY_NORMAL>, 'data': None}`.
- **Impact**: Misleading client error and ERROR-level traces for client-side bugs; no state corruption.
- **Siblings**: `handle_seek` (line 383) and `handle_play_enhanced` (line 189), `handle_play_normal` (line 328).
- **Suggested Fix**: `data = message.get("data") or {}` once in `dispatch_message`, and coerce `start_position` through a small shared helper that returns a typed `invalid_start_position` error.

#### BE-D2-05: The 64 KB inbound message cap is enforced only after the whole frame has been received
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/websocket/websocket_security.py:157-166`; `auralis-web/backend/config/limits.py:195`; `auralis-web/backend/main.py:124-130`
- **Status**: NEW
- **Description**: `WS_MAX_MESSAGE_SIZE` is documented as bounding per-message cost, but `validate_and_parse_message` runs on the already-delivered `frame["text"]` (and re-encodes it with `data.encode('utf-8')`). `uvicorn.run(...)` is called without `ws_max_size`, so uvicorn's default of 16 MiB applies at the protocol layer. Any local process with a loopback Origin-less connection (or an allowed origin) can make the server buffer and decode 16 MiB per message before the 64 KB check rejects it.
- **Evidence**: `uvicorn/config.py: ws_max_size: int = 16 * 1024 * 1024`; `main.py` passes only `host`, `port`, `log_level`.
- **Impact**: Limited to localhost memory/CPU churn (a few messages per second after the rate limit); the documented limit does not do what its comment says.
- **Siblings**: none.
- **Suggested Fix**: Pass `ws_max_size=WS_MAX_MESSAGE_SIZE` to `uvicorn.run` so oversized frames are refused at the protocol layer (1009); keep the in-handler check as defence in depth.
- **Cross-audit overlap**: same defect as INT-F5-11 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D2-06: `/ws` rate limiter re-types the per-connection limit instead of using `config/limits.py`
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/routers/system.py:41`
- **Status**: NEW (the heartbeat sibling of this exact pattern was closed in #5800)
- **Description**: `WS_MAX_MESSAGES_PER_SECOND = 10` lives in `config/limits.py` and is the constructor default, yet the only production instantiation passes the literal `10`. Retuning the constant silently does nothing for the live limiter (and the per-IP ceiling, defaulted to 3x the value, would not move either).
- **Evidence**: `_rate_limiter = WebSocketRateLimiter(max_messages_per_second=10)`.
- **Impact**: Config drift risk only today (values are equal).
- **Siblings**: none (the only other `HeartbeatManager()` call already takes the defaults).
- **Suggested Fix**: `WebSocketRateLimiter()` (or pass `WS_MAX_MESSAGES_PER_SECOND`).
- **Cross-audit overlap**: same defect as INT-F5-11 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D2-07: Streaming core still imports the chunk-cancel registry from `routers.system`
- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_enhanced.py:111`; `auralis-web/backend/core/stream_seek.py:107`
- **Status**: NEW (the same inversion #5761 removed for the pause/flow registries, which now live in `core/stream_gates.py`)
- **Description**: `stream_pause_events` / `stream_flow_events` were moved next to the pumps so the audio path no longer imports a router module; `_stream_chunk_cancel_events` (defined in `routers/system_streams.py`, re-exported by `routers/system.py`) was left behind, so both entry points still do a call-time `from routers.system import _stream_chunk_cancel_events`. This couples `core` to the router layer (and to its import order), and `StreamState.chunk_cancel_events` is the one registry that does not come from `core`.
- **Evidence**: `from routers.system import _stream_chunk_cancel_events` inside both functions.
- **Impact**: Layering/circular-import hazard; no runtime bug today.
- **Siblings**: the two call sites above.
- **Suggested Fix**: Define the dict in `core/stream_gates.py` beside the other two registries and import it from there in `system_streams.py` and the stream modules.

#### BE-D3-03: Cache worker renders and stores "original" (preset=None) chunks that no stream path ever reads
- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/streamlined_tiers.py:121-135,209-215`; `auralis-web/backend/core/chunk_disk_prune.py:24-25,76-107`
- **Status**: NEW
- **Description**: Tier 1 and tier 2 each render every chunk twice, once with `preset=None` ("original") and once with `'adaptive'`. The only readers of cache-manager chunk paths are the worker's own tier bookkeeping (`cache_manager.get_chunk` is called solely from `streamlined_tiers.py:122,139`); the enhanced stream always passes preset `'adaptive'` (`playback_commands.py:76-99,220-221,244-246`), and the normal/original stream (`stream_normal*.py`) reads the source file directly and never touches the chunk cache. So the "original" WAVs are written, counted, and never served. They still pass through the level smoother (so they carry baked gain on unprocessed audio), cost a decode + trim + PCM_16 write per chunk, and, because `is_fully_cached` requires them (`cache/models.py:160-162`), they also keep tier 2 "building" until every original chunk exists.
- **Evidence**:
  ```python
  # streamlined_tiers.py:209-215
  if chunk_idx not in status.cached_chunks_original:
      await worker._process_chunk(track, track_id, chunk_idx, preset=None, intensity=intensity, tier="tier2")
  ```
  ```python
  # chunk_disk_prune.py:24 — one shared budget for all chunk WAVs, reaped oldest-mtime first
  MAX_CHUNK_DISK_BYTES = 512 * 1024 * 1024
  ```
- **Impact**: Roughly half of the shared 512 MB on-disk chunk budget and half of the worker's render/decode work go to files nobody reads, and because the reaper deletes oldest-mtime first, freshly written "original" chunks push out older processed chunks of the playing track (which then re-render on demand).
- **Siblings**: `cache/models.py:160-162` (`is_fully_cached` couples completion to originals); `cache_streamlined.py:129` reports `cached_original` as a status counter only.
- **Suggested Fix**: Stop scheduling `preset=None` renders (and drop `cached_chunks_original` from the completion test), or serve them from the normal path if that tier is intended.
- **Reachability**: LATENT behind BE-D8-01: the worker never initialises `track_status`, so these renders never run in production today. Becomes live the moment BE-D8-01 is "fixed" by passing `track_duration`.

#### BE-D4-06: `AudioProcessingPipeline`'s fast-start and fixed-targets branches toggle a flag the live path never reads
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/audio_processing_pipeline.py:186-236`
- **Status**: NEW (adjacent to closed #3808/#4354, which fixed the race but not the premise)
- **Description**: Both the `targets is not None` branch and the `fast_start and chunk_index == 0` branch set `processor.content_analyzer.use_fingerprint_analysis = False` around `processor.process(audio)`. That attribute is read only by `ContentAnalyzer.analyze_content()`, which is called only from `AdaptiveMode` / `HybridMode`; the live `adaptive` path is `HybridProcessor._process_adaptive_mode` -> `ContinuousMode.process`, which calls `fingerprint_analyzer.analyze()` directly (or consumes `current_targets` set at construction). The toggle therefore changes nothing: `fast_start` ("skip fingerprint analysis for first chunk", passed for chunk 0 by `stream_chunk_ops.py:59`) does not skip anything, and the `targets` parameter is redundant with the targets already installed on the processor.
- **Evidence**: `grep use_fingerprint_analysis auralis/` -> only `content_analyzer.py` (set 44, read 145); `grep "analyze_content(" auralis/` -> only `adaptive_mode.py:77` and `hybrid_mode.py:58`.
- **Impact**: First-chunk latency for an untargeted track still pays a full fingerprint analysis, contrary to the code and docstrings; the toggle also takes `_process_lock` and mutates shared state for no effect.
- **Siblings**: `chunk_batch.py:104` passes `fast_start=(chunk_idx == 0)`.
- **Suggested Fix**: Delete the toggles and the `fast_start` parameter chain, or implement a real fast path in `ContinuousMode`.

#### BE-D4-07: Tier-2 builder's forward-only pointer never retries failed or evicted chunks and then logs "complete" every second
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/streamlined_tiers.py:208-228`
- **Status**: NEW
- **Description**: `build_tier2_cache` scans `range(worker._building_chunk_idx, total_chunks)` and advances `_building_chunk_idx = chunk_idx + 1` unconditionally after `_process_chunk`, even when that call returned `None` (timeout, missing file, error). The pointer is only reset on a track change. Chunks that failed, or that `_forget_tier2_chunk` later evicted (the 240 MB `TIER2_MAX_SIZE_MB` budget holds only ~11 minutes of original+processed chunks, so any longer track evicts as it builds), are never revisited; `cache_complete` stays `False`. Once the pointer reaches the end, every 1 Hz tick re-enters the function, the `range` is empty, and the fall-through `if not is_track_fully_cached(): logger.info("Tier 2 cache complete ...")` fires.
- **Evidence**: `streamlined_tiers.py:213-214, 222-223` (pointer advance after any outcome) and `:227-228` (unconditional INFO when not fully cached); `cache/eviction_mixin.py:_forget_tier2_chunk` sets `cache_complete = False`.
- **Impact**: An INFO line per second for the rest of playback of any long or partially failed track, plus a once-failed chunk is never rebuilt by the warm-cache worker (playback still works via `trigger_immediate_processing`). Wasted DSP: the worker renders an entire long track into a cache that evicts its own head.
- **Siblings**: BE-D3-03 (the same tiers render never-read original chunks, doubling the budget pressure).
- **Suggested Fix**: Only advance the pointer on success (or track failed indices with a retry cap), log completion once, and stop building when the track cannot fit the budget.
- **Reachability**: LATENT behind BE-D8-01 (the Tier-2 builder never runs today).

#### BE-D4-08: A cancelled or timed-out job's DSP keeps running on the 2-thread job pool while its slot is freed, so the next job's `wait_for` timer includes executor queueing
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/job_execution.py:162-205`; `auralis-web/backend/core/executors.py:96-99`
- **Status**: NEW
- **Description**: `HybridProcessor.process()` has no cancellation hook, so `cancel_job()` / `wait_for` timeout abandon the awaiting coroutine only; the thread keeps computing to completion on `JOB_EXECUTOR` (2 workers, sized to equal `max_concurrent_jobs`). `_run_job` releases the semaphore immediately, so up to two new jobs can start while two orphans still occupy both pool threads. Their `asyncio.wait_for(run_in_job_executor(...), timeout=300)` starts counting at submission, i.e. queueing behind the orphans is billed against the 300 s DSP budget (the exact failure mode #5086 documents for the chunk pool).
- **Evidence**: `job_execution.py:195-197` (`wait_for(run_in_job_executor(processor.process, audio), timeout)`), `executors.py:99` (`JOB_POOL_SIZE = 2`), `job_lifecycle.py:105-115` (cancel path only poisons the processor).
- **Impact**: After cancelling two long jobs, a third long job (e.g. a DJ-mix-length file) can fail with "Processing timed out after 300s" purely from queueing, and its processor is then poisoned/discarded; CPU is burned on results nobody will read.
- **Siblings**: none.
- **Suggested Fix**: Start the timeout clock when the executor begins running the call (wrap the function to set a started flag), or gate slot release on the orphan finishing, or give the job pool headroom (`2 x max_concurrent_jobs`).

#### BE-D4-09: Shutdown never closes the cache worker's cached `ChunkedAudioProcessor`s, so their converted temp WAVs outlive the process
- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/streamlined_lifecycle.py:33-49`; `auralis-web/backend/config/startup/shutdown.py:77-90, 152-157`
- **Status**: NEW
- **Description**: `StreamlinedCacheWorker.stop()` cancels the loop task but leaves `_processor_cache` populated. Each cached `ChunkedAudioProcessor` holds a `SeekableSource` reference on the converted temp WAV for `.m4a/.aac/.wma` tracks; `ProcessorFactory.clear_cache()` clears only the `HybridProcessor`s, and `converted_wavs.shutdown()` deletes only conversions with `refs == 0` ("a stream released after this deletes its own" -- but nothing ever releases these).
- **Evidence**: no `processor.close()` over `worker._processor_cache` anywhere in `stop()` or `_shutdown_components`; `ConvertedWavRegistry.shutdown()` -> `_evict_locked(0)` only evicts `_idle` entries.
- **Impact**: Up to the worker's cap (8 wrappers) of full-track FLOAT WAVs stay in the system temp dir after every exit that followed playback of a non-seekable format, until the next launch's `reclaim_stale_temp_entries` sweep.
- **Siblings**: BE-D2-02 (the stream-side hold leak).
- **Suggested Fix**: In `stop()`, drain `_processor_cache` through `close_dropped_processor` (off the loop) before clearing it.
- **Reachability**: LATENT behind BE-D8-01 (the worker processor cache is never filled today).

#### BE-D5-04: `GET /api/metadata/tracks/{id}` returns raw lower-cased tag keys for AIFF files, which `PUT` rejects (`extra="forbid"`), so a tagged AIFF can never be saved from the dialog
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis/library/metadata_editor/readers.py:145-162`; `auralis-web/backend/routers/metadata_models.py:30`; `auralis/io/formats.py:15-21`
- **Status**: NEW
- **Description**: `.aiff`/`.aif` are first-class library formats (`SOUNDFILE_FORMATS`) but have no `TAG_MAPPINGS` entry and no `EXTENSION_FORMAT_MAP` entry. `read_metadata` falls through to `read_generic_metadata`, which emits `str(key).lower()` for every ID3 frame (`tit2`, `tpe1`, `tdrc`, ...). The dialog keeps whatever object GET returned, so those keys are re-sent on save and `MetadataUpdateRequest` (`extra="forbid"`) answers 422 `Extra inputs are not permitted`. The form's real fields (`title`, `artist`) stay blank for such files, and `get_editable_fields` falls back to the FLAC field list via `get_format_key`'s default, so the contract is internally inconsistent for this format.
- **Evidence**: Reproduced with a tagged AIFF: `read_metadata` -> `{'tit2': 'Song', 'tpe1': 'Art', 'tdrc': '2020-05-01'}`; `MetadataUpdateRequest.model_validate({**md, 'title': 'New'})` -> `tit2: Extra inputs are not permitted`.
- **Impact**: Editing metadata of a tagged AIFF fails with a 422 whatever the user changes.
- **Siblings**: `.au` raises `Unsupported or invalid audio file` instead (400).
- **Suggested Fix**: Map AIFF to the ID3 reader/writer (like WAV) and key the output by `STANDARD_FIELDS`, or make the generic reader return only standard fields.

#### BE-D5-05: `alternative_profiles` wire shape disagrees with both typed contracts (`{id, name}` emitted; `{profile_id, profile_name, confidence_score}` declared)
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis/analysis/mastering_recommendation.py:46-48`; `auralis-web/backend/websocket/outbound_messages.py:174-189`; `auralis-web/frontend/src/types/ws/enhancement.ts:53-57`
- **Status**: NEW (the field was added to the frontend type by closed #3550; its item shape was never checked against the emitter)
- **Description**: `MasteringRecommendation.to_response()` (shared by the WS broadcast) emits `alternative_profiles` as `[{'id': p.profile_id, 'name': p.name}]`. `AlternativeProfilePayload` (backend TypedDict) and `MasteringRecommendationData` (TS) both declare `{profile_id, profile_name, confidence_score}`. Both typed sides are wrong about the wire. No emitter returns `confidence_score` for alternatives at all. `to_response` returns a plain dict and the broadcast site casts it, so mypy cannot catch it. The REST path strips the field (`MasteringRecommendationResponse` omits it), so only the WS frame carries it.
- **Evidence**:
  ```python
  # mastering_recommendation.py:46
  'alternative_profiles': [{'id': p.profile_id, 'name': p.name} for p in self.alternative_profiles],
  # outbound_messages.py:174
  class AlternativeProfilePayload(TypedDict):
      profile_id: str; profile_name: str; confidence_score: float
  ```
- **Impact**: None today (nothing consumes the field). A future consumer coded to the TS type reads `undefined` for every key.
- **Siblings**: REST and WS disagree on the presence of the field (REST strips it).
- **Suggested Fix**: Make the emitter produce the declared keys (including a real `confidence_score`) or correct both declarations to `{id, name}`, and build the WS payload through the TypedDict instead of casting.

#### BE-D5-06: Default intensity `1.0` is re-typed in ~13 places outside `core/`; `DEFAULT_INTENSITY` exists only privately in the WS command module
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:37`; `main.py:73`; `ws_handlers/connection.py:141`; `routers/enhancement_prewarm.py:203`; `routers/enhancement_recommendation.py:101`; `services/recommendation_service.py:85`; `routers/system_streams.py:58,201`; `cache/manager.py:122,141,205`; `cache/playback_mixin.py:99`; `cache/status_mixin.py:98`
- **Status**: NEW
- **Description**: `schemas/enhancement.py` fixed this class of problem for the preset (#4424/#5794: "a free string in 16 places") but not for the other half of the same settings triple. `INTENSITY_MIN/MAX` and `EnhancementIntensity` are shared, but the default is a bare `1.0` in the places listed. Only `ws_handlers/playback_commands.py` has a named `DEFAULT_INTENSITY`, and it is module-private. The on-connect `enhancement_settings_changed` push (`connection.py:136-143`) hand-builds the payload with its own `1.0` fallback instead of using `EnhancementSettingsChangedPayload` through `broadcast_typed`, and `UserSettings.enhancement_intensity` has its own `default=1.0` column default. Changing the default means the same grep the preset needed.
- **Evidence**: `grep -rnE 'intensity(: float)?\s*=\s*1\.0|"intensity": 1\.0|get\("intensity", 1\.0\)'` over `auralis-web/backend` outside `core/` returns the lines above.
- **Impact**: Maintainability only: a default change is easy to apply to some surfaces and miss others (the exact drift #5794 pinned for presets).
- **Siblings**: `core/` keeps its own local `1.0`s on purpose and is out of scope.
- **Suggested Fix**: Add `DEFAULT_INTENSITY` beside `DEFAULT_PRESET` in `schemas/enhancement.py`, re-export it, and import it in the sites above. Pin it with a test like `test_default_preset_single_source_5794.py`.

#### BE-D5-07: `QueueInfoResponse` is `extra="allow"`, so the engine's internal `repeat_enabled` (and any future engine key) is echoed beside the documented `repeat_mode`
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/player_models.py:146-168`; `auralis/player/components/queue_manager.py:243-252`; `auralis-web/backend/services/queue_service.py:64-82`
- **Status**: NEW
- **Description**: `get_queue_info()` returns the engine dict verbatim, enriched in place (`tracks`, `current_track`, `repeat_mode`). The response model's own comment says the engine's `repeat_enabled` bool was deliberately replaced by `repeat_mode` (#3896). But `model_config = ConfigDict(extra='allow')` lets the untouched engine keys through, so the wire carries both `repeat_enabled` (bool) and `repeat_mode` (three-valued). Because the model also guards the #3205 path stripping for `tracks`, any future engine key is shipped to the client unreviewed.
- **Evidence**: A real FastAPI round-trip with `{'tracks': [ti], 'current_index': 0, 'repeat_enabled': True, 'weird': 'x'}` returned `..."repeat_enabled":true,"weird":"x"`. The live engine dict always includes `repeat_enabled`.
- **Impact**: Two sources of truth for repeat state on the wire, and an open-ended pass-through on an endpoint whose contract is meant to be closed.
- **Siblings**: `SettingsResponse` is also `extra="allow"` (`settings_models.py:92`), but there it is documented and bounded by `to_dict()`.
- **Suggested Fix**: Set `extra='ignore'` (or drop the unused engine keys in `get_queue_info`) and enumerate any key a client really needs.

#### BE-D5-08: The scan-frame builders are duplicated between `routers/library_scan_events.py` and `services/auto_scan_events.py` and have already drifted
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/library_scan_events.py:48-100,139-166`; `auralis-web/backend/services/auto_scan_events.py:24-100,102-125`
- **Status**: NEW (the history of fixes #3502, #3209, #4427 and #5465 all repaired earlier symptoms of this duplication)
- **Description**: Both modules build the `library_scan_started` / `scan_progress` / `scan_complete` payloads and the fingerprint-enqueue step independently ("same pattern as the manual route"). Two differences already exist for the same logical frame. `scan_complete.files_processed` is `result.files_processed or result.files_found` in the manual path (`library_scan_events.py:155`) but `scan_result.files_processed` alone in the auto path (`auto_scan_events.py:115`). Since `files_processed` is only incremented on non-exception files while `files_found` counts every discovered file, a scan whose files all fail with exceptions reports N from the manual route and 0 from the auto-scanner. `scan_progress.current_file` falls back to `data.get('directory')` only in the auto path (`auto_scan_events.py:70`), so during the discovery phase the auto-scanner shows a directory where the manual route sends null. The frontend renders both through one `ScanStatusCard`.
- **Evidence**:
  ```python
  # library_scan_events.py:155
  "files_processed": result.files_processed or result.files_found,
  # auto_scan_events.py:115
  "files_processed": scan_result.files_processed if scan_result else 0,
  ```
- **Impact**: The same scan outcome reports different counts and progress text depending on whether it was started manually or by auto-scan.
- **Siblings**: `enqueue_added_for_fingerprinting` is duplicated in both modules.
- **Suggested Fix**: Move payload construction (`scan_complete_payload`, progress mapping) into one shared module that both emitters call, as `scan_progress_percentage` already is in `helpers.py`.
- **Cross-audit overlap**: same defect as INT-F4-9 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D5-09: Closed vocabularies and bounded scalars typed as bare `str`/`int`
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/backend/routers/settings_models.py:56-65`; `auralis-web/backend/routers/processing_models.py:29-35`; `auralis-web/backend/schemas/system.py:23,65`; `auralis-web/backend/routers/metadata_models.py:22-23,30`
- **Status**: NEW
- **Description**: Several fields with a fixed value set (or a documented range) are unconstrained. `SettingsUpdateRequest.bit_depth` is a free `int` (the column comment says 16/24/32, and `ProcessingSettings.bit_depth` is `Literal[16, 24, 32]`), `sample_rate` has `gt=0` but no ceiling or set, and `theme`/`language`/`output_device` are free strings. `HealthResponse.status` is documented "always 'healthy'" but is `str`, and `CacheTierStats.tier_name` is `str` for exactly `tier1|tier2` (the router assigns the two literals itself). `MetadataUpdateRequest` documents the aliases `track_number`/`disc_number` in OpenAPI but `model_dump()` emits `track`/`disc`, which are also what the GET and the `updated_fields` list use (accepted by `validate_by_name`, so not a bug, but two names for one field across one resource). `TrackCacheStatusResponse.estimated_cache_time_seconds` is `float | None` and no producer ever sets it (`cache_streamlined.py:126-133`).
- **Evidence**: See the locations above.
- **Impact**: An out-of-range `bit_depth` or sample rate is stored and echoed back as valid. Documentation, OpenAPI and client codegen describe looser contracts than the code intends.
- **Siblings**: `WebSocketErrorResponse.error` and `audio_stream_error.code` are free strings, but no consumer branches on them, so I did not raise it.
- **Suggested Fix**: Use `Literal[16, 24, 32]` for settings `bit_depth`, `Literal` for the two single-value strings, and delete or populate `estimated_cache_time_seconds`.

#### BE-D5-10: The frontend WS `TrackInfo` type disagrees with the backend `TrackPayload` (null vs undefined, plus eight fields the backend never sends)
- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/frontend/src/types/ws/base.ts:35-53`; `auralis-web/backend/websocket/outbound_messages.py:36-43`; `auralis-web/backend/player_state.py:28-52`
- **Status**: NEW
- **Description**: The backend sends `TrackInfo` as `{id, title, artist, album, duration, artwork_url, format}`, with `artwork_url` and `format` explicitly `str | None` (`null` is the common case, so tracks without artwork send `artwork_url: null`). The TS `TrackInfo` declares `artwork_url?: string` and `format?: string` (no `null`) and then eight further optional fields (`genre`, `year`, `bitrate`, `sample_rate`, `bit_depth`, `loudness`, `date_added`, `date_modified`) that no backend model produces, so they are always `undefined`. `mapTrackInfoToTrack` passes `track.artwork_url` straight through, and this works only because the target type happens to allow null.
- **Evidence**:
  ```ts
  // base.ts
  artwork_url?: string;  format?: string;  genre?: string; year?: number; bitrate?: number; ...
  ```
  ```python
  # player_state.py:44-52
  artwork_url: str | None = None
  format: str | None = None
  ```
- **Impact**: A `track.artwork_url === undefined` or `typeof ... === 'string'` check written against the declared type is wrong for the real null, and the dead fields invite consumers that can never get data.
- **Siblings**: `Track.loudness` (`types/domain.ts`) is likewise always undefined for real rows: `trackTransformer.ts:61` reads `apiTrack.loudness`, which only the Mock fallback emits, while `Track.to_dict()` emits `lufs_level`.
- **Suggested Fix**: Declare `artwork_url?: string | null; format?: string | null` and remove the eight unsent fields (and map `lufs_level` into `Track.loudness` or drop it).

---

Observation outside this dimension (not filed): `auralis/core/analysis/spectrum_mapper/preset_anchors.py` still defines `gentle`, `punchy` and `live` anchor entries alongside `adaptive`, which `SpectrumMapper` (built in `hybrid_setup.py:44`) interpolates over. Because this is engine code reached through `AdaptiveMode`, it falls to the engine audit if the "removed everywhere" directive is meant to cover internal anchors.

#### BE-D6-04: The `/api/library/scan` rate-limit prefix also throttles the read-only `GET /api/library/scan/status` to 2/min, and the UI calls it on every WebSocket reconnect
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware/rate_limit.py:50-55`, `config/limits.py:159-160`; consumer `auralis-web/frontend/src/hooks/library/useScanProgress.ts:194,257-259`
- **Status**: NEW
- **Description**: Buckets are `client:METHOD:prefix`, so `GET /api/library/scan/status` gets its own bucket, but with the scan POST's budget of 2 requests per 60 s. The frontend resyncs scan state through this GET on every transition to `connected` (#4821) and swallows any failure with an empty `.catch`. Observed with `TestClient`: `[503, 503, 429, 429]` for four consecutive calls (503 only because the library is not initialised, which shows the handler is reached for the first two).
- **Evidence**: `useEffect(() => { if (connectionStatus === 'connected') resyncScanStatus(); }, [connectionStatus]);` plus `.catch(() => { /* Best-effort resync ... */ })`.
- **Impact**: The third reconnect inside a minute (flaky WS, broadcast-timeout eviction, backend restart loop) gets a silent 429. The scan flag then stays stale, which is the exact "Scanning... forever" state #4821 set out to remove. Also, `/api/processing` GETs (jobs, presets, queue status) share one 10/min bucket, though the current UI does not poll them.
- **Siblings**: `/api/processing` and `/api/similarity` prefixes have the same prefix-wide GET budgets.
- **Suggested Fix**: Exempt the cheap read-only status GET (or apply limits only to state-changing methods and the genuinely heavy GETs).
- **Cross-audit overlap**: same defect as INT-F4-8 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D6-05: Unhandled 500s are returned without CORS, security headers or no-cache, contradicting the documented "every response" contract
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/app.py:117-123`; documented at `config/middleware/__init__.py:43-48` and `config/middleware/security_headers.py:62-70`
- **Status**: NEW
- **Description**: `@app.exception_handler(Exception)` is installed on Starlette's outermost `ServerErrorMiddleware`, outside the whole user-middleware stack. Because every middleware here is a `BaseHTTPMiddleware` that re-raises the downstream exception from `call_next`, the exception propagates past SecurityHeaders, NoCache and CORS before the handler builds the response. The setup comment ("a 403/429/400 bubbles back up through SecurityHeaders/NoCache") is true for responses, not for exceptions. `ServerErrorMiddleware` also re-raises after sending, so uvicorn logs the traceback a second time on top of the handler's `logger.error(..., exc_info=True)`.
- **Evidence**: A route raising `RuntimeError`, called with `Origin: http://localhost:3000` against the real app, returned `500 ['content-length', 'content-type']`. The same request to an unknown path returns `access-control-allow-origin`, CSP and `x-frame-options`. Traceback in the repro shows `ServerErrorMiddleware -> CORSMiddleware -> SecurityHeaders -> NoCache -> ... -> route`.
- **Impact**: Any cross-origin client (for example the packaged page on `127.0.0.1:8765` calling `localhost:8765`) sees a CORS network error instead of the 500 JSON body. All 500s carry no security headers. Every unhandled error is logged twice with a full traceback.
- **Siblings**: None.
- **Suggested Fix**: Catch `Exception` inside the stack (a small outermost-but-inside-CORS middleware, or have each dispatch return `_middleware_error_response` for downstream exceptions) so CORS and the security headers still apply, or fix the documentation to say 500s are outside them.

#### BE-D6-06: `--dev`'s `/api/docs` and `/api/redoc` render blank because the CSP blocks their jsdelivr assets
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware/security_headers.py:106-120`, `config/app.py:78-80`
- **Status**: NEW (adjacent to open #5070, which is about the disabled-docs link, not this)
- **Description**: In dev, FastAPI's default docs HTML loads `https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js` and `swagger-ui.css`. `SecurityHeadersMiddleware` stamps every response, including `/api/docs`, with `script-src 'self' 'unsafe-inline'` and `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`, which exclude that CDN.
- **Evidence**: Dev-mode `GET /api/docs` returns 200. The HTML references `['https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css', '.../swagger-ui-bundle.js']`, and the same response carries the CSP above.
- **Impact**: The documented dev feature ("View API Documentation" link in the dev stub page, `is_dev_mode()` warning text) is unusable. The only workaround is to disable the header.
- **Siblings**: `/api/redoc` loads from the same CDN.
- **Suggested Fix**: Skip the CSP (or extend it with the jsdelivr host) for `/api/docs`, `/api/redoc` when dev mode is on.

#### BE-D6-07: Startup creates an unused `~/Music/Auralis` directory, and a failure there rolls back the whole library init
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/startup/components.py:30-40`
- **Status**: NEW
- **Description**: `_init_library_database` does `Path.home()/"Music"/"Auralis"` with `mkdir(parents=True, exist_ok=True)`, labelled "Database directory ready". The database lives in `~/.auralis/library.db`, and nothing else in the backend or `auralis/` uses `~/Music/Auralis` (grep for it returns only this line). The step has no try/except by design (#3812), so any `OSError` (read-only or unmounted `~/Music`, `~/Music` being a file, permission, quota) propagates to `_rollback_partial_startup`.
- **Evidence**: `music_dir = Path.home() / "Music" / "Auralis"; music_dir.mkdir(parents=True, exist_ok=True)` followed by `globals_dict['library_database'] = LibraryDatabase()`, which never reads `music_dir`.
- **Impact**: An unrelated, unwritable home subdirectory makes every data route return 503 and health report `auralis_available: false`, though the DB itself could open. On healthy systems it silently creates an empty folder in the user's music library (a default scan root) on every launch.
- **Siblings**: None.
- **Suggested Fix**: Delete the mkdir (and the "Database directory ready" log). If a directory is wanted, create the DB's own parent via `LibraryDatabase`.

#### BE-D6-08: CORS `allow_headers` omits `X-Confirm-Reset`, so library reset fails preflight for cross-origin pages the CORS list explicitly supports
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware/__init__.py:113`; `auralis-web/frontend/src/services/settingsService.ts:188-191`; required by `auralis-web/backend/routers/library.py:83-97`
- **Status**: NEW
- **Description**: The frontend sends `X-Confirm-Reset: RESET` and the router rejects the call without it. The allow-list is `["Content-Type", "Authorization", "X-Requested-With", "Accept", "X-Session-Id"]`. In a production build `API_BASE_URL` is `http://localhost:8765`, so a page opened as `http://127.0.0.1:8765` (an origin CORS deliberately allows, #3539) is cross-origin and sends a preflight.
- **Evidence**: `OPTIONS /api/library/reset` with `Origin: http://localhost:8765`, `Access-Control-Request-Headers: content-type,x-confirm-reset` returns `400 Disallowed CORS headers`.
- **Impact**: "Reset library" cannot succeed from any cross-origin configuration the allowlist claims to support. Same-origin Electron use is unaffected.
- **Siblings**: No other custom request headers are sent by the frontend (checked `headers:` usages).
- **Suggested Fix**: Add `X-Confirm-Reset` to `allow_headers`.

#### BE-D6-09: User folder paths still reach INFO/ERROR logs despite the project's "absolute paths log at DEBUG" policy
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/services/missing_tracks.py:69,73`
- **Status**: NEW (same class as closed #4929 / #4778 / #5277; different sites)
- **Description**: The policy (#4366, #4376, #4778, `components.py:36-38` comment) is that absolute home/install paths go to DEBUG because INFO is persisted to electron-log and pasted into bug reports. The sanitizer only strips control characters (`auralis/utils/logging.py:27`), it does not redact paths. `remove_tracks_under_folder` logs the removed scan folder at INFO, and its failure at ERROR.
- **Evidence**: `logger.info(f"🗑️  Removed {removed} tracks under removed scan folder {folder}")`.
- **Impact**: Home directory name and library layout land in the persisted log at the default INFO level every time a scan folder is removed.
- **Siblings**: Full user file paths at ERROR/WARNING: `core/streamlined_worker.py:154`, `core/fingerprint_loading.py:241`, `analysis/fingerprint_generator.py:309`, `routers/artwork.py:143`, `routers/processing_jobs.py:88`. These are the same inconsistency #5277 closed for temp cleanup.
- **Suggested Fix**: Log `Path(x).name` (or demote to DEBUG), as the neighbouring sites already do.

#### BE-D6-10: `AURALIS_SCAN_TIMEOUT` is parsed per request with a bare `float()`, bypassing `get_int_env`'s "never crash" contract
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/routers/library_scan.py:146`; contrast `core/env_config.py:22-48`
- **Status**: NEW
- **Description**: Every other tunable goes through `get_int_env` at import time, which falls back with a warning on a malformed or sub-minimum value. The scan timeout alone is re-read inside the request handler and parsed with no validation. A non-numeric value raises `ValueError` after the scanner and progress callback are built. A zero or negative value makes `asyncio.wait_for` time out immediately, so a scan that was just started is stopped and reports 504. `inf` or `nan` disables or breaks the bound. `AURALIS_IO_POOL_WORKERS` has the related gap: it is accepted above the documented DB-pool ceiling of 10 (`core/executors.py:90-94`) without a clamp or warning.
- **Evidence**: `scan_timeout = float(os.environ.get("AURALIS_SCAN_TIMEOUT", "3600"))`.
- **Impact**: A typo in an env var turns every manual scan into a 500 (`ValueError during library scan` broadcast) or an instant 504 timeout, with no startup warning.
- **Siblings**: `AURALIS_IO_POOL_WORKERS` (`core/executors.py:94`).
- **Suggested Fix**: Resolve it once at import via `get_int_env("AURALIS_SCAN_TIMEOUT", 3600)` like the others, and clamp the pool size against the DB pool limit.

#### BE-D6-11: Backend shutdown has no overall deadline, and the Electron supervisor gives it about 1 s with a dead SIGKILL escalation
- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `desktop/main.js:481-506` (and 670-677); `auralis-web/backend/config/startup/shutdown.py:36-176`; `auralis-web/backend/main.py:122-127`
- **Status**: NEW
- **Description**: `_shutdown_components` is built from steps with their own timeouts (fingerprint workers 30 s, scanner watchdog join 5 s plus task wait 10 s, watchdog teardown wait 10 s, job drain, and so on) but nothing bounds the total, and `uvicorn.run` sets no `timeout_graceful_shutdown`. The supervisor sends SIGTERM (`main.js:485`), then schedules a SIGKILL 2 s later whose callback tests `this.pythonProcess`, which `cleanup()` sets to `null` at line 506 before the timer fires, so the escalation can never run. `before-quit` also calls `app.quit()` after 1 s (line 675). The WAL checkpoint and temp-WAV cleanup sit near the end of the sequence.
- **Evidence**: `setTimeout(() => { if (this.pythonProcess && !this.pythonProcess.killed) { ... kill('SIGKILL') ... } }, 2000);` followed by `this.pythonProcess = null;` at the end of `cleanup()`.
- **Impact**: A backend that is slow or stuck in shutdown is neither waited on nor force-killed. It lingers holding port 8765. The next launch finds it via the port check and `kill -9`s it, possibly mid-teardown (WAL checkpoint skipped; SQLite recovers, temp files wait for the age sweep). It is low impact on a healthy exit.
- **Siblings**: None.
- **Suggested Fix**: Keep a local reference to the child process in `cleanup()` so the SIGKILL timer works, and have the supervisor wait for exit. Optionally set `timeout_graceful_shutdown` and wrap `_shutdown_components` in an overall `asyncio.wait_for`.

#### BE-D7-03: Metadata routes: corrupt files give inconsistent 400/500 and the PUT 400 echoes the absolute file path
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/metadata_tracks.py:92-120,226-228`; `auralis/library/metadata_editor/metadata_editor.py:106,175`
- **Status**: NEW (the #3849/#5283 path-leak fixes covered `FileNotFoundError` and the batch result item, not this `ValueError`)
- **Description**: `MetadataEditor.read_metadata/write_metadata` raise `ValueError(f"Unsupported or invalid audio file: {filepath}")` when mutagen cannot identify the file. `PUT /api/metadata/tracks/{id}` catches every `ValueError` and answers `BadRequestError(f"Invalid metadata: {e}")`, i.e. a 400 that (a) puts the resolved absolute path in the response body (the project policy is that paths stay server-side, #4807/#3849) and (b) blames the request's metadata for a corrupt file. The other mutagen failure modes (`FLACNoHeaderError`, `HeaderNotFoundError`, `InvalidChunk`, `AACError`) are not `ValueError`, so they take the generic 500. `GET /api/metadata/tracks/{id}` catches only `FileNotFoundError`, so a corrupt file is always a 500 there. Same file, same defect, three different outcomes depending on extension and verb.
- **Evidence**:
  ```text
  # MetadataEditor.write_metadata(...) on 5 KB of random bytes
  m4a/ogg/opus/wma/au -> ValueError  'Unsupported or invalid audio file: /tmp/tmp.RavRMfHR9g/junk.m4a'
  flac -> FLACNoHeaderError, mp3 -> HeaderNotFoundError, wav/aiff -> InvalidChunk
  ```
  ```python
  # metadata_tracks.py:226-228
  except ValueError as e:
      raise BadRequestError(f"Invalid metadata: {e}")      # -> 400 with the file path
  ```
- **Impact**: A user editing tags of a corrupt m4a/ogg/opus/wma/au file receives a 400 containing `/home/<user>/Music/...`, labelled "Invalid metadata"; corrupt FLAC/MP3/WAV/AIFF give a bare 500 "Failed to update track metadata". Minor disclosure on a localhost-only app, but a stated policy violation and an unhelpful error.
- **Siblings**: `GET /api/metadata/tracks/{id}` (500 for every corrupt file); the batch route reports `str(e)` with the filepath replaced by the basename (`batch.py:138`), which is the correct pattern.
- **Suggested Fix**: Catch the editor's "unsupported/invalid file" condition (a dedicated exception or `mutagen.MutagenError` plus that `ValueError`) in both routes and answer a fixed 422/415 "Unreadable or unsupported audio file"; keep `Invalid metadata:` only for validation of the request's own values. Never interpolate the exception text.

#### BE-D7-05: Graceful shutdown persists in-flight jobs as CANCELLED, so INTERRUPTED is reachable only after a hard kill
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/job_worker.py:121-171`; `auralis-web/backend/core/job_lifecycle.py:204-212`; `auralis-web/backend/core/job_store.py:30-31,106-114`
- **Status**: NEW
- **Description**: #5278's contract is "a job still queued or processing at shutdown reloads as INTERRUPTED". Only the crash path honours it. On a graceful stop `JobWorker.stop()` sets every PROCESSING job's status to `CANCELLED` itself before cancelling its task, and `process_job`'s `finally` then persists that terminal state, so after a clean restart those jobs are listed as user-cancelled with no error message. Queued jobs drained by `stop()` are also set `CANCELLED` in memory but never persisted, so they alone reload as INTERRUPTED. The two outcomes for the same event differ, and the "Interrupted: the backend stopped before this job finished" message is never shown for an ordinary quit. No test covers the stop path (`tests/backend/test_processing_job_persistence_5278.py` exercises restore only).
- **Evidence**:
  ```python
  # job_worker.py:126-133 (stop)
  job = self._engine.jobs.get(job_id)
  if job and job.status == ProcessingStatus.PROCESSING:
      job.status = ProcessingStatus.CANCELLED      # persisted later by process_job's finally
  ...
  # job_worker.py:164-168  queued jobs: status = CANCELLED, never persisted (stay 'queued' in the DB)
  ```
- **Impact**: A user who quits the app mid-job sees the job as "cancelled" (and not "interrupted") next launch; a queued job shows "interrupted". Inconsistent and misleading, no data loss.
- **Siblings**: BE-D4-03 covers the related shutdown race for semaphore-parked jobs.
- **Suggested Fix**: In `stop()` mark in-flight and queued jobs `INTERRUPTED` with `INTERRUPTED_MESSAGE` (not `CANCELLED`) and persist them once, so graceful and crash shutdowns reload identically.

#### BE-D7-06: Enhanced/seek stream reports `reason="stopped"` after a server-side DSP timeout
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/core/stream_enhanced_chunks.py:212-244`; `auralis-web/backend/core/stream_messages.py:134-153,215-243`; `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:197-226`
- **Status**: NEW (sibling of the normal-path rule recorded in `stream_normal_chunks.py:248-257`)
- **Description**: #4790 reserves `audio_stream_end reason="stopped"` for a clean client-driven exit, and the normal pump explicitly avoids setting `stopped_early` when it aborts after consecutive read timeouts so the terminal frame says `"errored"`. The enhanced/seek pump's `TimeoutError` branch (a server-side abort after sending the error frame) sets `stopped_early = True`, so the epilogue emits `reason="stopped"`. The client treats `'stopped'` as "superseded by a new command" and does neither `markStreamEnded()` nor records the error state.
- **Evidence**:
  ```python
  # stream_enhanced_chunks.py:243-244
  stopped_early = True
  break
  # normal pump (stream_normal_chunks.py:250-257): "Deliberately NOT stopped_early ... lands on reason='errored'"
  ```
- **Impact**: Wrong terminal reason after a DSP timeout; the buffered tail is not played out and no "ended early" state is recorded (the preceding error frame partly masks it). Contract inconsistency only.
- **Siblings**: the `not delivered` branch at `:189` legitimately keeps `stopped` (the client is gone).
- **Suggested Fix**: Add the timed-out chunk to `failed_chunks` (or a separate `aborted` flag) instead of setting `stopped_early`, mirroring the normal pump.

#### BE-D7-07: `set_queue` ignores the engine's load/play result and still broadcasts `playing`
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/services/queue_set_mixin.py:146-165`
- **Status**: NEW (related to open #5725 but a different layer: the service discards the failure signal)
- **Description**: `AudioPlayer.load_file()` reports failure by returning `False` (missing file, undecodable file; it never raises). `_set_queue_impl` awaits it and `audio_player.play()` and ignores both return values, then calls `player_state_manager.set_playing(True)` and returns 200 "Queue set successfully". The route that does check the result (`POST /api/player/load`) answers 400. #5303 deliberately skips `validate_file_path` here, so a track deleted after the scan is not caught anywhere before the state is committed.
- **Evidence**:
  ```python
  await asyncio.to_thread(self.audio_player.load_file, current_track.filepath)   # bool ignored
  ...
  await asyncio.to_thread(self.audio_player.play)                                 # bool ignored
  playing_snapshot = await self.player_state_manager.set_playing(True, broadcast=False)
  ```
- **Impact**: "Play album" on a deleted/corrupt first track returns success and publishes `playing` state for a track that did not load; the failure surfaces only later as a streaming error. Small because audio is actually delivered over the WS stream.
- **Siblings**: `NavigationService.next_track` maps a failed engine move to "No next track available" (200), conflating end-of-queue with a load failure.
- **Suggested Fix**: Check the `load_file` result and skip `play()`/`set_playing(True)` (or raise a typed `OperationFailed`/`ResourceNotFound`) when it is `False`.

#### BE-D7-08: Mastering-recommendation endpoint reports timeouts and unanalysable files as generic 500s
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/enhancement_recommendation.py:115-135`; `auralis-web/backend/core/chunk_mastering.py:57-66`
- **Status**: NEW
- **Description**: `compute_mastering_recommendation` swallows a fingerprint-extraction failure (corrupt/unsupported/missing audio) into `None`; the route turns `None` into `HTTPException(500, "Failed to analyze audio file")`. `recommend_weighted` never returns `None` (it has a fallback), so `None` always means "this file could not be analysed", which is a property of the file, not a server fault. The route's own timeout is likewise a 500, while the scan route's timeout is a 504. The failure category computed upstream is lost, so the UI cannot tell "bad file" from "server broke".
- **Evidence**:
  ```python
  except TimeoutError:
      raise HTTPException(status_code=500, detail="Mastering recommendation analysis timed out — the file may be corrupt or on slow storage") from None
  if result is None:
      raise HTTPException(status_code=500, detail="Failed to analyze audio file")
  ```
- **Impact**: Server-error status (logged/handled as a backend fault) for a corrupt file; no retry/skip distinction. Low severity, the recommendation is optional.
- **Siblings**: none (the WS recommendation path degrades to `{}` on both conditions, which is appropriate there).
- **Suggested Fix**: 504 for the timeout and 422 (or 404 for a missing file) for `None`, using `_safe_error_message` on the swallowed exception to give a category.

#### BE-D8-06: Every track list/search/queue payload ships each track's full `lyrics` and `comments`, which the frontend never reads
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis/library/models/track.py:144-196` (`Track.to_dict`), `auralis-web/backend/schemas/library.py:125-126` (`TrackResponse.comments/lyrics`)
- **Status**: NEW
- **Description**: `Track.to_dict()` emits `comments` and `lyrics` for every track, and `TrackResponse`/`TrackListResponse` declare both, so `/api/library/tracks`, `/search`, `/favorites`, album/playlist track reads and metadata all carry them. The frontend has no reference to lyrics anywhere under `auralis-web/frontend/src` (a dedicated `/api/library/tracks/{id}/lyrics` endpoint already exists for the one place they would be needed). The repositories also hydrate these unbounded `Text` columns (plus `fingerprint_vector` and `fingerprint_error_message`) for every row of every read, since none is deferred.
- **Evidence**: `'comments': self.comments, 'lyrics': self.lyrics,` in `to_dict()`; `grep -rl lyrics auralis-web/frontend/src` returns nothing.
- **Impact**: Response size and JSON encode time scale with lyric length x page size (200 tracks x a few KB of LRC lyrics is several hundred KB per page, encoded on the event loop). Low severity because pages are capped at 200 and most libraries carry few lyrics.
- **Siblings**: `lyrics` persisted by `routers/tracks.py:get_track_lyrics` makes the column grow over time.
- **Suggested Fix**: Drop `lyrics`/`comments` from the list `TrackResponse` (keep them on the detail/metadata endpoint) and `defer()` the Text columns on list reads.
- **Cross-audit overlap**: same defect as INT-F2-14 in `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` (unpublished, same day). Publish once.

#### BE-D9-04: "Track not found" tests for lyrics and fingerprint patch the wrong router module, so the mock never runs and they pass only because the real DB is empty
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_library_api_comprehensive.py:221-229` and `:429-437`
- **Status**: NEW
- **Description**: Both tests use `@patch('routers.library.require_repository_factory')` and `mock_repos.tracks.get_by_id.return_value = None`. The routes they hit, `GET /api/library/tracks/{id}/lyrics` and `GET /api/tracks/{id}/fingerprint`, live in `routers/tracks.py` and `routers/fingerprint_status.py`, which resolve repos via `repo_deps.RepositoryFactoryDeps`. The patched name is in `routers.library`, which serves neither route. The patch is inert after the router split.
- **Evidence**: A probe that patched `routers.library.require_repository_factory` with a `Mock(side_effect=RuntimeError)` and called both URLs returned `404 {"detail":"Track 999 not found"}` with `patch_called=False` for both. The 404 comes from the real, empty, isolated library.
- **Impact**: The not-found branch is exercised only against the real DB, and the mock-based setup the tests describe (stubbing `get_by_id`, which would let them also vary the repo's behaviour) does nothing.
- **Siblings**: None found among the 149 resolved patch targets (the `routers.repo_deps.*`, `routers.albums_deps.*` and `routers.dependencies.*` patches all resolve through the module attribute the handlers actually call).
- **Suggested Fix**: Patch `routers.repo_deps.require_repository_factory` (as `test_get_artist_not_found` does), or inject via `patch.dict('main.globals_dict', {'repository_factory': mock})`.

#### BE-D9-05: Nine "response structure" tests only assert inside `if status_code == 200`, which never happens against the isolated empty library
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_library_api_comprehensive.py:231-239, 296-304, 361-369, 439-447`; `tests/backend/test_cache_streamlined_api.py:200-238`; `tests/backend/test_similarity_api.py:177-188, 233-243`
- **Status**: NEW (same family as closed #5810)
- **Description**: `_isolated_library_db` made the library empty, so these routes always answer 404 (or 200 `null`), and the schema assertions sit inside the unreachable `if response.status_code == 200:` branch. The test body never fails.
- **Evidence**: A probe against the real app with an empty library returned `/api/cache/track/1/status` 404, `/api/library/tracks/1/lyrics` 404, `/api/tracks/1/fingerprint` 404, `/api/artists/1` 404, `/api/albums/1` 404, `/api/similarity/tracks/1/explain/2` 404, `/api/similarity/graph/stats` 200 `null`. In the graph-stats test the inner `if data is not None:` also skips.
- **Impact**: The response contracts these tests are named for (`test_get_lyrics_structure`, `test_get_track_status_field_types`, `test_explain_similarity_structure`, ...) are unpinned, and the cache-status fields and explain `distance`/`similarity_score` can change shape undetected.
- **Siblings**: The nine tests are `test_get_lyrics_structure`, `test_get_artist_structure`, `test_get_album_structure`, `test_get_fingerprint_structure`, `test_get_track_status_structure`, `test_get_track_status_field_types`, `test_get_track_status_completion_range`, `test_explain_similarity_structure` and `test_get_graph_stats_structure`. `test_api_endpoint_integration.py` still has `pytest.skip("Playlist creation failed")` branches (`:416-424`).
- **Suggested Fix**: Seed rows through the repository (or inject a mock factory) and assert the 200 payload, or delete the tests. Turn `if 200:` into `assert status == 200`.

#### BE-D9-06: Four routes are never called over HTTP, and the playlists router has no real-DB round trip
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `routers/playlists_tracks.py:72-157` (`/tracks/add`, `/tracks/reorder`); `routers/player_queue.py:104-116` (`POST /api/player/queue/add-tracks`); `routers/cache_streamlined.py:136-145` (`DELETE /api/cache/track/{id}`)
- **Status**: NEW
- **Description**: Across the whole of `tests/`, no test calls these four routes. `/tracks/add` and `/tracks/reorder` were the #4658 fix, but `TestPlaylistDragDropRoutes` (`test_readiness_and_stream_end_contracts.py:197-260`) only asserts registration and the request models. The `add-tracks` route (#5651) is covered only at `QueueService` level (`tests/regression/test_queue_service_mutations.py:187`); its `ValueError` to status mapping is never run. `test_playlist_add_tracks_api` is named after `/tracks/add` but posts to `/tracks`. Playlist HTTP tests all stub the repository with `Mock`, and there is no `PUT /api/playlists/{id}` 404 or invalid-body 422 test over HTTP. The BE-D1-03 swallowed-DB-error path is likewise unreachable by these tests.
- **Evidence**: `grep -rn "tracks/reorder\|reorder_playlist_track" tests` returns only registration assertions; `grep -rn "add-tracks" tests` returns only the route-table entry in `test_router_split_5472.py:33`; the only `cache/track/` hit besides `/status` is a registration entry in `test_router_wiring_pinned_5832.py:76`.
- **Impact**: A change to the repository's `reorder_track(from, to)` / `add_track(position)` contract or to the 400 mapping breaks drag-and-drop with no failing test, and `add-tracks` ordering (#5651) is unpinned at the route.
- **Siblings**: Several "accepts GET only" tests accept `404` as well as `405` (e.g. `test_library_api_comprehensive.py:420-423`), so they would pass if the route were deleted.
- **Suggested Fix**: Add TestClient tests with a seeded temp DB for the playlist add/reorder routes, `add-tracks` (success plus a bad id), and `DELETE /api/cache/track/{id}`.

#### BE-D9-07: No test drives the real `/ws` streaming path end to end
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `tests/backend/test_system_api.py:393-540`; `tests/backend/test_audio_stream_lifecycle.py:48-125`
- **Status**: NEW
- **Description**: The `/ws` tests through the real endpoint all end at an error frame or at a recorded `stream_audio` call (`patch.object(system_module, "stream_audio", ...)`). The streaming-lifecycle tests run `AudioStreamController` against an `AsyncMock` websocket and a mock `ChunkedAudioProcessor` that returns silence (`proc.process_chunk_safe = AsyncMock(...)`, `:61-73`). No test connects with `TestClient.websocket_connect("/ws")`, plays a real library track with a real `ChunkedAudioProcessor`, and receives `audio_stream_start`, the `audio_chunk` meta/binary pairs and `audio_stream_end`. `test_play_enhanced_missing_track_id` also accepts "an error or may attempt processing" and passes on a `WebSocketDisconnect`.
- **Evidence**: `grep -rln audio_stream_start tests` lists only the controller-level files above. `receive_bytes` is never called in `tests/`.
- **Impact**: Wiring regressions between `/ws` command to `stream_audio` to controller to pump to wire (the product's main flow) are caught only by unit tests of each seam.
- **Siblings**: This also means the BE-D3-01 cache-hit shape change and the BE-D3-02 out-of-order render have no wire-level test.
- **Suggested Fix**: Add one `@pytest.mark.integration` test that streams a 12 s WAV through `/ws` (normal and enhanced) and asserts the concatenated binary payload length equals the source samples.

#### BE-D9-08: Live bugs found by other dimensions that no existing test would catch (summary)
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: see per item
- **Status**: NEW (summary of gaps; the underlying bugs are the cited IDs)
- **Description**: For each item I checked whether any test exercises the failing path.
  - **BE-D4-01** (`MasteringFingerprint(**25 kwargs)`): no test calls `core.fingerprint_loading.load_from_database`. `test_fingerprint_unification_4595.py` covers a different class, `FingerprintService._load_from_database`. `test_mastering_target_cache_signature_5489.py:35` monkey-patches `load_fingerprint_from_database` out.
  - **BE-D4-02/03**: see BE-D9-01.
  - **BE-D1-05** (volume `NaN`/`Inf` becomes 100 %): the NaN tests cover `SeekRequest` only (`test_request_body_constraints_4681.py:160-163`). The volume test pins only the finite clamp (`:151-154`).
  - **BE-D5-01** (explicit `null` in `PUT /api/settings`): `test_settings_router.py` sends no null.
  - **BE-D1-06** (processing upload sniff rejects WMA/AU/ADTS): `test_upload_magic_bytes.py` imports `routers.files._has_valid_audio_magic`, the other upload sniff. It never touches `routers/processing_upload.py`.
  - **BE-D1-12** (upload orphaned when the DB insert fails): no test makes the insert fail.
  - **BE-D2-04** (null or omitted `data` becomes `internal_error`): no `/ws` test sends `"data": null`.
  - **BE-D1-08 / D1-09** (per-request `QueueService`, concurrent graph build): no cross-request concurrency tests exist. The HTTP-level concurrency coverage is `test_sqlite_lock_contention_4773.py` and a 10-add loop in `test_player_api_comprehensive.py`.
  - **BE-D1-03** (playlist delete reports success on a swallowed DB error): see BE-D9-06.
- **Impact**: These bugs would reappear after a fix with no regression guard unless tests are written with each fix.
- **Siblings**: n/a
- **Suggested Fix**: Add the test with each fix, using the specific path each item names (real `MasteringFingerprint` construction, `{"volume": NaN}`, `{"default_preset": null}`, an upload with an injected insert failure).

#### BE-D10-02: The `/api/cache/*` surface describes only the inert streamlined tiers: the real chunk cache is invisible, "healthy" is constant, and the clear endpoints misreport and 503 without the manager
- **Severity**: LOW
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:85-103,138-158,173-202`; `auralis-web/backend/cache/status_mixin.py:45-92`; `auralis-web/frontend/src/components/settings/AdvancedSettingsPanel.tsx:130` (renders `CacheStatsDashboard`)
- **Status**: NEW (consequence-level cross-reference of BE-D8-01; the monitoring/clear-contract defects below are not in D8-01)
- **Description**: Because the worker never fills the tiers (D8-01), `GET /api/cache/stats` is permanently `{tier1: 0 chunks, tier2: 0 chunks, tracks: {}}`, `GET /api/cache/health` is permanently `healthy: true` (0 MB <= every hard-coded ceiling, ceilings are BE-D1-15), and `GET /api/cache/track/{id}/status` is a 404 for every track. The cache that actually holds all served chunks, the 512 MB `auralis_chunks` directory, is not reported anywhere: no size, count, hit rate or prune activity is exposed, so the Settings > Advanced dashboard shows a healthy, empty cache while the real one fills and prunes. Three clear-side defects sit on the same surface: (1) `DELETE /api/cache/track/{id}` returns `removed = len(tier1) + len(tier2)` entries for that track (always 0 in production), while the files it really deleted (`swept`) are only logged, and the response model documents "Number of cached chunks removed"; (2) both clear endpoints take the streamlined manager as a hard dependency (`_get_cache_manager` -> 503 "Cache manager is not yet initialised") even though `clear_all_caches` is explicitly written to run with `cache_manager=None` ("the filesystem and analysis tiers are still cleared"), and `config/startup/workers.py` nulls `streamlined_cache` whenever the worker fails to start or dies, so the only user-facing "clear caches" lever disappears together with the cache that does not matter; (3) the per-track clear does not touch the track's recommendation entries (`mastering_recommendations`, 60 s TTL, keyed `(track_id, threshold)` with no file signature) or its `MasteringTargetService` entry.
- **Evidence**:
  ```python
  # clearing_mixin.py:51-88 — returns tier entries, logs the swept count
  removed = len(t1_removed) + len(t2_removed)
  ...
  swept = await asyncio.to_thread(delete_chunk_files, self.chunk_dir, track_id)
  logger.info(f"... ({removed} entries, {swept} on-disk chunk file(s) swept)")
  return removed
  # cache_streamlined.py:148-158 — clear_cache requires the manager, then hands it to a helper that accepts None
  async def clear_cache(cache_manager: StreamlinedCacheManager = Depends(_get_cache_manager), ...):
      await clear_all_caches(cache_manager, deps.get_artwork_cache_dir())
  ```
- **Impact**: Operators and the user get a false "all clear" and no signal that the live cache is full, pruning, or behaving as a FIFO (BE-D10-01). A "clear and retry" reports `removed: 0` after deleting real files. Low severity because audio is unaffected.
- **Siblings**: BE-D1-15 (hard-coded ceilings), BE-D8-01.
- **Suggested Fix**: Either report the chunk directory (file count, MB, prune totals) from `/api/cache/stats` and return the swept count from the per-track clear, or delete the streamlined tier/worker/dashboard together (D8-01). Make `clear_cache` depend on the manager optionally and always run `clear_all_caches`.

#### BE-D10-03: `StreamlinedCacheManager.get_stats()` overstates the Tier-1 hit rate and iterates live dicts from a worker thread (latent behind BE-D8-01)
- **Severity**: LOW
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:136-185` (`get_chunk` counters), `auralis-web/backend/cache/status_mixin.py:45-92` (`get_stats`), `auralis-web/backend/routers/cache_streamlined.py:96,181` (`asyncio.to_thread(cache_manager.get_stats)`)
- **Status**: NEW (adjacent to closed #5252 and #3499; latent until the worker is revived)
- **Description**: Two defects in one function. (a) Counters: `get_chunk` records a Tier-1 miss only when *both* tiers miss (`tier1_misses += 1; tier2_misses += 1` after the loop). A request served by Tier 2 is a Tier-1 miss but is counted nowhere on the Tier-1 side, so `tier1.hit_rate = tier1_hits / (tier1_hits + tier1_misses)` ignores every Tier-2 hit. With 1 Tier-1 hit, 9 Tier-2 hits and 0 full misses the response says Tier-1 hit rate 100 % (true: 10 %). `cache_health` publishes the same `tier1_hit_rate`. #5252 fixed the double counting of full misses but left this asymmetry. (b) Thread safety: the router offloads `get_stats` to a thread (#3499), and `get_stats` iterates `tier1_cache`/`tier2_cache` (`_tier_size_mb`, `{c.track_id for c in tier2_cache.values()}`) and `track_status.items()` while `add_chunk`/eviction mutate them on the event loop under an `asyncio.Lock`, which does not exclude another thread.
- **Evidence**: Reproduction of (b) (`scratchpad/d10/race.py`, a thread calling `get_stats()` while the event loop inserts/pops `tier2_cache` entries): `RuntimeErrors from get_stats while loop mutates tier2_cache: 246 ['dictionary changed size during iteration']` in 3 s (the mutation rate is exaggerated; the mechanism is not). Code for (a):
  ```python
  # manager.py:180-185
  self.tier1_misses += 1
  self.tier2_misses += 1          # full miss only; a tier-2 hit increments neither miss counter
  ```
- **Impact**: None today (the tiers are empty, D8-01). If the worker is ever revived the stats endpoint intermittently 500s under load and overreports Tier-1 effectiveness.
- **Siblings**: `cache_streamlined.get_track_cache_status` runs `get_track_cache_status` in a thread over the same mutable state.
- **Suggested Fix**: Count a Tier-1 miss whenever Tier 1 does not serve the request; take a snapshot (`list(...)`/`dict(...)`) on the loop, or compute stats on the loop instead of `to_thread`. Better: delete the dead tier with D8-01.
- **Reachability**: LATENT behind BE-D8-01 (the streamlined tiers stay empty today).

#### BE-D10-04: The central `.25d` fingerprint store (`~/.auralis/fingerprints`) has no eviction, is untouched by Clear Cache and library reset, and is mostly unreachable orphans
- **Severity**: LOW
- **Dimension**: Caching & Invalidation
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:48-80,94-134,196-266` (key, `save`, `delete`/`clear_all` with no production caller); `auralis-web/backend/core/cache_cleanup.py:31-67`; `auralis-web/backend/core/fingerprint_loading.py:130-170`
- **Status**: NEW (related open: #5751 hard-coded dir, #5697 unversioned central `.25d`)
- **Description**: `FingerprintStorage` names each file `md5(abs_path : "{st_mtime}:{st_size}" : strategy)`, so any re-tag, `touch`, re-encode or move mints a new key and strands the old file, and a deleted track strands its file for good. Nothing ever removes entries: `FingerprintStorage.delete` and `clear_all` have no production caller, there is no size/age cap, `clear_all_caches` (the "one lifecycle boundary for every cache tier", #5257) does not include this tier, and `POST /api/library/reset` leaves it as well (its docstring says the analysis tier is only the in-memory `MasteringTargetService` cache). Files written under earlier key schemes (version `1.0`, before the #3679/#4127 changes) are rejected by `load` as `version != 2.0` and also never deleted. Freshness is mtime+size only (no content fallback, unlike `FileSignatureService` after #5256).
- **Evidence**: Measured on this machine's real store (read-only, `scratchpad/d10/orphans.py`): 3213 `.25d` files / 13 MB; only 383 are reachable by the current key for an existing source; 1757 reference sources that no longer exist (many from pytest temp dirs, since backend tests write to the real `HOME`) and 1072 reference sources that still exist under a *different* key. For the real library (`/mnt/Musica/Musica`) 1052 of 1458 entries are not the file's current key; 887 of 1259 still-existing library files have only legacy version-`1.0` entries (`scratchpad/d10/why.py`).
- **Impact**: Slow unbounded growth (about 4 KB per orphan; 13 MB here), no way for a user to reclaim or reset it, and stale derived data surviving a "reset everything". Low because the files are tiny and orphans are never read.
- **Siblings**: `~/.auralis/artwork` source files (reset-cleared but otherwise unbounded, orphaned albums #5596); pre-migration DB backups (#5750).
- **Suggested Fix**: Add the fingerprint store to `clear_all_caches`/reset, and sweep entries whose version is stale or whose recorded `source_file` no longer maps to the current key (on scan or at startup), with a count/age cap.

---

#### BE-D11-03: A cache-hit chunk that starts a stream (any seek into already-rendered audio) is recorded with trailing gain 0.0, discarding the remembered gain, so the next rendered chunk skips its gain release
- **Severity**: LOW
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/level_manager.py:311-321` (`record_cached_level`), fed by `core/chunk_stream_state.py:153-182` and `core/chunk_render.py:180-211`
- **Status**: NEW (sibling of the closed #4367/#4669/#4352 line of fixes, which only covered the mid-stream case)
- **Description**: A seek always builds a fresh `ChunkedAudioProcessor` and `LevelManager`. When the first chunk of that stream is a durable-cache hit, `_record_cache_hit_level` looks up the chunk's `(rms, trailing gain)` that was remembered when it was written, but `record_cached_level` treats "history is empty" as a baseline and stores `0.0` instead of the remembered `gain_db`. `smooth_transition` for the *next* (cache-miss) chunk then reads `gain_history[-1] == 0.0`, so the #4352 de-ramp (50 ms ramp from the held gain back to unity) is skipped even though the cached chunk really ends at that held gain. Baseline-0.0 is right for a freshly *rendered* chunk (it was not adjusted) and for chunk 0; it is wrong for a cache hit.
- **Evidence**: Synthetic 65 s track (15 s loud / 15 s quiet noise), real `ChunkedAudioProcessor` (scratch `/tmp/audit/backend/d11_hit_start.py`): play 0..4 straight through (chunk 4 is written with a held +15.45 dB), then seek into chunk 4 (hit) and render chunk 5:
  ```
  remembered (rms_db, trailing gain_db) for cached chunk 4: (-16.94, 15.45)
  LevelManager.gain_history after serving chunk 4 as the stream's first chunk: [0.0]
  A straight-through gains: [0.0, 16.91, 0.0, -1.45, 15.45, 0.0]    # chunk 5 ramps 15.45 dB -> 0 over 50 ms
  C seek-into-cached gains: [0.0, 0.0]                              # chunk 5 starts at unity: hard step
  chunk 5 first 50 ms vs straight-through: -11.6 dB
  ```
  ```python
  # level_manager.py:318-321
  is_baseline = chunk_index == 0 or len(self.rms_history) == 0
  self.rms_history.append(current_rms)
  self.gain_history.append(0.0 if is_baseline else _clamp_gain_db(gain_db))   # remembered gain dropped
  ```
- **Impact**: One hard gain step (the size of the held gain, normally a few dB; 15 dB in the synthetic worst case) at the boundary after the first chunk of a stream that began on cached audio, only where the following chunk is not cached (the frontier of what was played before). Narrow, hence LOW.
- **Siblings**: none besides the same call from `get_wav_chunk_path`'s path-only branch (its throw-away LevelManager is discarded, so harmless).
- **Suggested Fix**: In `record_cached_level` honour the supplied `gain_db` for cache hits (only force 0.0 when the call is a baseline *render*, i.e. `smooth_transition`), keeping chunk 0 at 0.0.

#### BE-D11-04: `send_pcm_chunk` leaves its producer task parked forever on a full queue when the stream is cancelled mid-chunk
- **Severity**: LOW
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/stream_protocol.py:211-256,282`
- **Status**: NEW
- **Description**: Every seek/stop/track change that lands while a chunk is being sent cancels `await asyncio.gather(_producer(), _consumer())`. `gather` completes its outer future as soon as the first child is cancelled, so the awaiting stream task proceeds with its own teardown while `_producer` is still alive: it was cancelled inside `await queue.put(item)`, runs `finally: await queue.put(None)` against the still-full queue (`_SEND_QUEUE_MAXSIZE=4`) and no consumer exists any more to free a slot. The producer task (and its queued frames, ~300 KB each, plus a view of the chunk array, 3.5-5.3 MB) is never awaited and never finishes; only the cyclic GC eventually reclaims it. The disconnect path does not have this problem (the consumer drains the queue before breaking).
- **Evidence**: Real `send_pcm_chunk` with a slow fake controller, cancelled 0.12 s into a 10 s stereo chunk (scratch `/tmp/audit/backend/d11_cancel_send2.py`):
  ```
  tasks still alive after cancel (excluding main): ['send_pcm_chunk.<locals>._producer']
  after gc, producer tasks alive: []        # only a gc.collect() removes it
  ```
  ```python
  # stream_protocol.py:254-255
  finally:
      await queue.put(None)  # sentinel   <- blocks forever once the consumer is gone and the queue is full
  ```
- **Impact**: Up to ~5 MB of pinned memory per seek-mid-send until the next GC pass plus an orphaned pending task; scrub storms (10 seeks/s are admitted) multiply it. No audio effect.
- **Siblings**: none; `pump_normal_chunks` reuses the same `send_pcm_chunk`.
- **Suggested Fix**: In the producer's `finally` use `put_nowait` guarded by `abort_event`/`queue.full()` (or skip the sentinel when cancelled), and make the consumer treat `abort_event` as the stop signal; alternatively await both children in a `try/finally` that cancels and gathers the producer.

---

## Relationships

- **Flow-control and seek wire protocol** (BE-D2-01, BE-D11-01, BE-D11-02, BE-D2-06, BE-D6-04, BE-D7-02, BE-D7-06).
  - Flow-control edges, seek and the stream epoch are all one-shot messages with no ack.
  - Flow-control edges and seeks share the 10 msg/s per-connection limiter (BE-D2-06 re-types that limit as a literal).
  - A dropped or rate-limited edge leaves either the server or the client stuck: the gate stays closed (BE-D2-01), the client stays "seeking" (BE-D11-02), or a skipped chunk is treated as fatal (BE-D7-02).
  - Fix them together as a protocol change: exempt control edges from the limiter, make resume level-triggered, put the epoch on `seek_started`, and correlate rejections. That is better than five separate patches.
  - A seek is currently the only recovery from a closed flow gate (verified in Dimension 11), so fixing BE-D11-02 without BE-D2-01 removes the workaround.
- **Fingerprint tiers** (BE-D4-01, BE-D4-04, BE-D4-05, BE-D7-08, BE-D6-03, BE-D1-14, BE-D10-04).
  - Tier 1 (DB) never works (BE-D4-01).
  - Tier 2 (`.25d`) can hand back `{}` targets that are applied as fixed (BE-D4-04), and its 25D dict breaks recommendations (BE-D4-05), which the route then reports as a 500 (BE-D7-08).
  - The recommendation route is also expensive and unthrottled (BE-D6-03), and it duplicates `RecommendationService` (BE-D1-14).
  - Fixing BE-D4-01 by returning dicts would make BE-D4-05 universal. Fix them in one change that normalises what the loader returns.
  - #5719 (open: a rescan keeps the old fingerprint row) becomes live once BE-D4-01 is fixed.
- **StreamlinedCacheWorker** (BE-D8-01 plus latent BE-D3-02 (worker half), BE-D3-03, BE-D4-07, BE-D4-09, BE-D10-02, BE-D10-03, BE-D1-15).
  - The worker is inert. "Fixing" BE-D8-01 by passing `track_duration` would activate four latent bugs at once and fill half the disk cache with unread "original" chunks.
  - The `/api/cache/*` surface (BE-D10-02, BE-D1-15) reports only these empty tiers.
  - Decide first whether to delete the worker and its tiers or to revive it.
- **Chunk cache under level smoothing** (BE-D3-02, BE-D11-03, BE-D10-01, BE-D3-01, #5258, #5558).
  - The durable chunk key does not encode render context (predecessor gain). Seek and prewarm renders therefore poison later sequential plays (BE-D3-02, INT-F8-5), and cache hits discard the remembered gain (BE-D11-03).
  - Cache-hit reads also lose channel layout (BE-D3-01) and can race the pruner (BE-D10-01).
- **Queue/player state coherence** (BE-D1-08, BE-D5-02, BE-D5-07, BE-D7-07, BE-D8-02, open #5460, #5725).
  - The REST queue service is rebuilt per request and the `PlayerState` snapshot carries never-written fields.
  - Each `player_state` broadcast serialises the whole queue (BE-D8-02) while overwriting client-owned state with frozen values (BE-D5-02).
- **Lifecycle symmetry** (BE-D6-01, BE-D6-02, BE-D4-03, BE-D7-05, BE-D4-09, BE-D6-11, BE-D2-02).
  - `start()`/`stop()` pairs that are not re-entrant (BE-D6-01).
  - A stop that blocks the loop (BE-D6-02).
  - Stops that miss parked work (BE-D4-03).
  - Shutdown with no deadline, where the Electron fallback is dead (BE-D6-11).
  - Temp WAV holds leaked on cancel (BE-D2-02, BE-D4-09).
- **Tests do not pin the fixes they claim** (BE-D9-01 → BE-D4-02/D4-03; BE-D9-02 → tiling; BE-D9-03 → all `slow` tests; BE-D9-08 lists the rest).

## Prioritized Fix Order

1. **BE-D2-01 + BE-D11-02 + BE-D2-06** (flow-control and seek liveness). This is likely user-visible on every enhanced track longer than about 3 minutes since #5657. Exempt `buffer_full`/`buffer_ready`/`seek` from the message limiter. Add a bounded wait on the flow gate. Make the client resume level-triggered.
2. **BE-D1-01** (scanned folders not registered). A one-line class of fix in `scan_library`: register each directory and persist it to `scan_folders`. Without it, whole libraries on other mounts cannot be played.
3. **BE-D11-01** (stale pre-seek audio). Carry the new epoch on `seek_started` (allocate it at cancel time) and have the client adopt it there. Close it together with item 1 because it touches the same handlers.
4. **BE-D4-01 + BE-D4-04 + BE-D4-05 + BE-D7-08** (fingerprint tiers). Fix them as one change, otherwise fixing Tier 1 makes BE-D4-05 universal. Add a real-DB test (BE-D9-08).
5. **BE-D10-01, BE-D3-01, BE-D3-02/BE-D11-03** (chunk-cache integrity: skipped chunks, channel-shape changes, level steps of about 15 dB).
6. **BE-D1-08, BE-D4-02 + BE-D9-01, BE-D4-03 + BE-D7-05** (regressed concurrency and backpressure contracts). Fix each with a test that uses the real engine/worker.
7. **BE-D1-04, BE-D1-05, BE-D5-01, BE-D1-03** (mutating-route validation and data loss: arbitrary-path prune, NaN volume, a null that bricks settings, false-success deletes).
8. **BE-D6-01, BE-D6-02, BE-D7-04** (library reset leaves workers dead and blocks the loop; degraded startup is invisible).
9. **BE-D8-01 decision** (delete or revive the streamlined worker, together with its latent findings and the `/api/cache/*` surface), then the remaining MEDIUMs.
10. **BE-D9-03** (run `slow` tests on a schedule). This is cheap, and it restores the only real REST→engine coverage.
11. The LOWs, opportunistically. Many are one-line fixes (BE-D2-06, BE-D6-08, BE-D6-10, BE-D1-15, BE-D5-06).

## Appendix — Existing issues cross-referenced (not re-reported)

Agents found these open issues for candidate findings and did not re-file them:
- **Dimension 2**: #5077, #5079, #5494.
- **Dimension 5**: #5049, #5497, #5500, #5460.
- **Dimension 6**: #5070, #5068, #5484.
- **Dimension 7**: #5264, #5265, #5725.

The closed fixes below were re-verified and are still in place: #5490 (tier warming off the loop), #5493 (`get_chunk` checks completeness), #5489 (target-service key includes the file signature), #5491 (similarity_graph success tests), #5323, #5328, #4642, #5783, #5762 and #3205. The per-dimension notes follow.

**Dimension 1**

- Existing: #5264 - playlist `update`/`add_track`/`reorder`/`clear` map swallowed DB errors to 404/400 (BE-D1-03 covers the two routes that ignore the result entirely).
- Existing: #5265 - `POST /api/metadata/batch` reports `success: true` when requested tracks were silently skipped (not-found / invalid path / no fields are dropped before `batch_update`).
- Existing: #5266 - `MetadataUpdateRequest` tag values entirely unbounded.
- Existing: #5381 - `_with_similarity_error_handling` turns `OperationalError` into 500 instead of 503 (similarity, graph, fingerprint-queue).
- Existing: #5501 - albums and artists routers register with no OpenAPI tag (7 operations show tag "none").
- Existing: #5716 - `FingerprintNormalizer.fit` gates on an unfiltered count and is never refitted (related to BE-D1-07).
- Existing: #5651 / #5189 - frontend bulk-queue / reorder issues (backend `add-tracks`/`move` routes themselves are fine).

**Dimension 3**

- `process_all_chunks_async` zero production callers — Existing: #5495 (OPEN). `get_full_processed_audio_path` unreachable (and its `_full.wav` key omits targets_hash / the quantised intensity) — Existing: #5088 (OPEN).
- LevelManager boosts chunks by up to +40 dB after the limiter with no peak check — Existing: #5558 (OPEN). In my render experiment below the smoother lifted a -32 dB passage by +16.9 dB in the *sequential* case too, which is that issue's territory.
- `audio_stream_start.channels` advertises the native channel count for >2ch FFmpeg-routed files — Existing: #5709 (OPEN). BE-D3-01 below is the cache-hit sibling of that disagreement and is not covered by it (#5709 states native >2ch WAV/FLAC is "self-consistent").
- #5323 (prewarm shares live HybridProcessor) and #5328 (cancelled look-ahead persists wrong-gain chunk) are CLOSED and their guards (`_track_is_live_streaming` in enhancement_prewarm.py, `_raise_if_cancelled` before the durable write) are still present. BE-D3-02 is a different writer (the cache worker) of the same root class, not a regression of those.

**Dimension 4**

- Existing: #5722 (OPEN) -- `ContinuousMode._reference_cloud` is cached for the processor's lifetime. Same root cause covers a *stale non-empty* cloud: nothing invalidates it after `refresh_cloud()` (scan end / fingerprint-queue drain / `POST /api/library/refresh-references`), so pooled `ProcessorPool` processors and cached `ProcessorFactory` processors keep the cloud they first loaded.
- Existing: #5695, #5701 (OPEN) -- fixed-target EQ tilt and whole-buffer peak clamp in the fixed-target path (`fixed_target_params.convert_targets_to_parameters`); not re-reported. Note for the fixer: that path also drops `target_crest_db` entirely (produced by `generate_targets_from_fingerprint`, never read by `convert_targets_to_parameters`).
- Cross-ref BE-D3-03 -- the Tier-1/Tier-2 builders in `streamlined_tiers.py` also render `preset=None` chunks no stream reads.

---

**Dimension 9**

- Existing: #5502 (OPEN), the `JobStore` to repository-factory production wiring is untested.
- #5491 (CLOSED) is still fixed: `test_similarity_graph_success_5491.py` is present.
- #5810 (CLOSED) fixed `_isolated_library_db`, but siblings of its "depends on ambient library contents" pattern remain (see BE-D9-05).

**Dimension 10**

- **Existing: #5258** (open, LOW): no single-flight for concurrent renders of the same chunk key. It is written for seek requests, but the same gap is hit **deterministically on every cold enhanced-stream start**: `stream_enhanced.py:186` spawns `buffer_presets_for_track`, which builds a second `ChunkedAudioProcessor` on the `PROACTIVE_BUFFER` factory and renders chunks 0-2 into the same durable keys while the stream renders chunk 0 and its look-ahead renders chunk 1. `_buffer_chunk` only checks `exists()` before starting, and the stream's own render is still in flight, so both run the DSP. Reproduction (`scratchpad/d10/dup_render.py`, synthetic 50 s track, two consumers, `asyncio.gather(stream.process_chunk_safe(0), buf.process_chunk_safe(0))`): `chunk 0 renders with both consumers racing: 2` (counted via `AudioProcessingPipeline.process_audio`). Worth a comment on #5258: the cost lands in the time-to-first-audio window, and the two renders use different pooled `HybridProcessor` states, so the surviving last-writer bytes are not guaranteed identical.
- **Existing: #5719** (open, MEDIUM): a rescan of a modified file keeps the old audio's fingerprint row. Relevant to this dimension: `fingerprint_loading.load_from_database` (Tier 1 of `MasteringTargetService`) has no freshness check, so once BE-D4-01 is fixed, Tier 1 will serve the previous audio's fingerprint ahead of the signature-keyed `.25d` for any edited file. Also note #3705 (the same defect) is CLOSED, but its closing commit `1f3070ea` fixed unrelated items (`similarity.find_similar` cap, etc.); the stale-DB-row behaviour was never changed.
- **Existing: #5088, #5495** (open, LOW): `get_full_processed_audio_path` / `process_all_chunks_async` have no production caller. If revived, note that `chunk_batch.py:86-89` builds its cache filename as `track_{id}_{sig}_{preset}_{raw intensity}_full.wav`, outside the lockstep key (no targets hash, no `CACHE_VERSION`, un-bucketed intensity), so it would reintroduce #4666/#5474 for the full-track file.
- **Existing: #5751** (open, LOW): artwork and fingerprint cache directories are hard-coded to `~/.auralis`, which also means `artwork_cache_dirs()` / `FingerprintStorage._get_cache_dir()` ignore `database_path` in tests.
- **Existing: #5503** (open, LOW): `CacheMonitor` hit-rate/size alerting has no production caller (related to BE-D10-02: no cache telemetry on the live tier).

Candidates checked and dropped: off-grid intensities share a 0.1 bucket by design (#5474; the UI slider is `step=0.1`); `fast_start` is not in the key but has no effect on the output (BE-D4-06); the recommendation cache's missing file signature is bounded by a 60 s TTL and its free-float key is BE-D6-03; artwork source writes are non-atomic (`ArtworkExtractor._save_artwork`, `ArtworkDownloader._save_artwork`) but the DB path is recorded only after the write and names are content-hashed, so no truncated file is ever referenced; thumbnail eviction is oldest-written-first rather than LRU, which is documented and only costs re-renders; the ETag `serve_path.stat()` in `routers/artwork.py:196` can in principle race a prune of the served thumbnail, but the pruner only reaches the newest entries when a single thumbnail exceeds the cap.

**Dimension 11**

- **BE-D2-01** (flow gate has no timeout, `buffer_ready` only per frame): seek interacts benignly -- `handle_seek` installs fresh set pause/flow events, so a seek is the recovery path for a wedged gate; the client's stale `flowPausedRef` costs one redundant `buffer_ready`.
- **BE-D2-02** (SeekableSource close/resolve race and the cancelled-acquire hold leak), **BE-D2-07** (`routers.system` import for the cancel registry), **BE-D7-06** (DSP timeout reported as `reason="stopped"`), **BE-D3-01** (cache hit re-read through `load_audio` changes channel shape for the first post-seek chunk), **BE-D3-02** (order-dependent bytes persisted under the shared durable key).
- **#5258 (OPEN)**: no single-flight dedup for concurrent seek requests to the same chunk key.
- **Seek-start chunk is rendered without smoothing and persisted under the sequential cache key** -- documented in the unpublished `docs/audits/AUDIT_INTEGRATION_2026-10-22.md` as INT-F8-5 (LOW); no GitHub issue title found. Independently reproduced with the real processor (scratch `/tmp/audit/backend/d11_seek_order.py`, same synthetic track): first contact via a seek to chunk 4 renders it at -32.4 dB vs -16.9 dB when reached straight through (gains `[0.0, -13.95]` vs `[.., 15.45, 0.0]`), and a later straight-through play serves those bytes as cache hits, giving a 3->4 seam step of -17.0 dB instead of -1.8 dB. Severity is arguably MEDIUM rather than LOW (it is the same mechanism as BE-D3-02 with a user-driven trigger); left to the owner of those two.
- **Frontend, out of this audit's scope**: `useEnhancedStreamStart.ts:94-107` returns early on `is_seek` with a live engine (every in-session seek), so `engine.setSeekOffset(seek_position)` is never applied after `stopPlayback()` zeroed the offset. Previously reported in `docs/audits/AUDIT_INTEGRATION_2026-08-13.md`; no matching issue title found in `issues.json`. The backend's `seek_position`/`seek_offset` are correct.

## Housekeeping (not findings — for `/audit-publish` triage or direct closure)

- **#5271** is still OPEN, but Dimension 5 found it already fixed in the current tree. Verify it and close it.
- **#3705** is CLOSED, but Dimension 10 notes its closing commit fixed unrelated items. Worth a glance.
- **#5258** (open, no single-flight on chunk renders) also fires on every cold enhanced-stream start: the proactive buffer and the stream both render chunk 0 (2 renders reproduced). This is worth a comment on that issue rather than a new one.
- **Doc rot**: `CLAUDE.md` still says `tests/backend/test_system_api.py` hangs as a whole file and must be `--ignore`d "exactly like CI does". `backend-tests.yml` no longer ignores it (Dimension 9). Re-check before editing, since the instruction may still hold locally.
- **Out of scope (frontend)**: in-session seeks never reapply `setSeekOffset`. This was reported in the 2026-08-13 integration audit (and as INT-F8-1 today), and no issue title matches it.
