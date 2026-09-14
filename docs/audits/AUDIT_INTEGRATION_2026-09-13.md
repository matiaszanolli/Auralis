# Integration Audit — 2026-09-13

**Scope**: 9 critical data flows across the audio engine (`auralis/`), FastAPI backend (`auralis-web/backend/`) and React frontend (`auralis-web/frontend/src/`).
**Depth**: deep | **Limit**: none | **Method**: one flow agent per flow (max 3 concurrent, fresh read of current source). The orchestrator then re-read the code behind every finding before merging and recalibrated severities against `.claude/commands/_audit-severity.md`. Candidates that did not survive re-verification are listed at the end.
**Dedup baseline**: `gh issue list` — 134 open + 600 most recent closed issues.
**Context**: enhancement presets were deliberately narrowed to `'adaptive'` only on 2026-09-13 (`c195ac80`, `ae9d28e3`). The removal of gentle/warm/bright/punchy/live is not reported. Consistency of the narrowing was checked end to end (see Flow 3 row and INT-F5-02).

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 5 |
| MEDIUM | 13 |
| LOW | 5 |
| **Total** | **23** (all NEW; 0 regressions) |

**Key themes**

1. **Fixes that landed in one of two parallel implementations.** This is the dominant root cause, behind 10 of the 23 findings. A closed issue fixed one copy of the logic, and its sibling still carries the bug: #5254 seek clamp (enhanced path only → INT-F8-01), #4602 rejected-scan broadcast (start frame only → INT-F4-04), #4841 scan failures (Library view only → INT-F4-01), #4414 sub-frame counting (main ingest only → INT-F1-01), `QueueEnricher` vs bespoke hydration (→ INT-F9-01), and three album-creation sites (→ INT-F2-01).
2. **Split-brain queue / now-playing state (Flow 9).** The engine queue, `PlayerStateManager.state` and Redux are updated by different paths that never reconcile. Queue edits broadcast raw filepath rows (INT-F9-01), are reverted by the next `player_state` (INT-F9-02), and the backend advances "now playing" on its own wall-clock estimate (INT-F9-03).
3. **Unit/scale contracts that exist only in comments.** Spectral centroid is served as 0–1 but documented and consumed as Hz (INT-F6-01), `bass_pct` is filtered with a 0–100 tolerance (INT-F6-02), cache keys round intensity three ways (INT-F3-01), and the scanner phase union has drifted (INT-F4-06).
4. **Backend state the UI never shows.** Stream-end `reason` (INT-F1-02), local buffer stalls (INT-F1-03), scan failures (INT-F4-01) and terminal WS failure (INT-F5-03) are all computed and then dropped at the last hop.

**Most impactful boundary mismatches**
- **INT-F8-01**: with enhancement off, seeking to the end (End key sends `position = duration`) produces a silent zero-audio stream. This is #5254's symptom on the path its fix missed.
- **INT-F9-01**: every queue edit on a normally-built queue broadcasts `{'filepath': ...}` rows into Redux, losing ids and titles and leaking server paths (#3205 invariant).
- **INT-F2-01**: a retag followed by a rescan creates artist-less albums that vanish from artist pages and serialize `artist: null` against a non-nullable frontend type.

**Preset narrowing**: consistent in code across every mirror (`schemas.py` `VALID_PRESETS`, `domain.ts`, `outbound_messages.py`, `usePlayerStateSync.ts`, `useEnhancementControl.ts`), and a legacy stored `default_preset` degrades safely on both sides. The only surviving removed-preset reference is documentation: `auralis-web/backend/WEBSOCKET_API.md:637` (INT-F5-02). `usePlayerStateSync.ts:58` keeps a local `['adaptive']` mirror instead of importing `ENHANCEMENT_PRESETS`. The values agree, so this is a DRY nit, not a finding.

## Flow Coverage Matrix

Legend: OK = boundary verified, no defect · finding ID = defect · EX = existing open issue confirmed · N/A = not applicable.

| # | Flow | Schema match | Error handling | Timeouts | Data types / units | Null handling | Case conversion | Flow-specific checks | Findings |
|---|------|--------------|----------------|----------|--------------------|---------------|-----------------|----------------------|----------|
| 1 | Track Playback | OK queue POST, `play_enhanced`/`play_normal` | F1-02 stream-end `reason` ignored | OK 30 s DSP timeout vs start watchdog; EX #5190/#5019 | OK SR engine→AudioContext; float32 LE binary framing; seams tile | OK | OK snake_case WS | F1-03 underrun invisible; F1-01 progress over-count; F1-04 ring-buffer slot | F1-01, F1-02, F1-03, F1-04 |
| 2 | Library Browsing | OK tracks/albums/artists/playlists | OK 404/503 distinct | N/A | OK `limit/offset/has_more`, max 200 | F2-01 `album.artist` null | OK transformers | OK large libraries paginated; eager-loads match `to_dict` | F2-01 |
| 3 | Audio Enhancement | OK REST bodies | OK | N/A | F3-01 cache-key intensity precision | OK legacy preset degrades | N/A | OK live preset/intensity reach transport; REST/WS bounds shared; preset narrowing consistent in code; EX #5271 | F3-01 |
| 4 | Library Scanning | OK REST + WS scan payloads | F4-01 failures hidden | OK 3600 s server-side, no client timeout | F4-06 `phase: 'counting'` | OK | OK | F4-02 manual scan no prune/move detection; F4-04 rejected auto-scan broadcasts complete; F4-05 folder removal; EX #4820 cancel | F4-01, F4-02, F4-04, F4-05, F4-06 |
| 5 | WebSocket Lifecycle | OK all routed inbound/outbound types handled | OK error-frame shape | OK heartbeat 30 s / 10 s; broadcast send 2 s | OK binary vs text consistent | OK | OK | F5-01 reconnect ignores close code; F5-03 status UI collapse; F5-02 protocol doc rot | F5-01, F5-02, F5-03 |
| 6 | Fingerprint & Similarity | OK 25-D names/order agree | OK 404 + enqueue; 503 unfitted | N/A | F6-01 centroid/rolloff Hz vs 0–1; F6-02 `bass_pct` scale | OK | OK | OK score range 0–1; graph fallback | F6-01, F6-02 |
| 7 | Artwork | OK `size`/`v`; `artwork_updated` payload | OK 404 → placeholder | N/A | OK Content-Type sniffed; size buckets match requests | OK no URL without artwork | OK | F7-01 track views not cache-busted; OK cache headers (`NoCacheMiddleware` skips `/api`); EX #5069 | F7-01 |
| 8 | Seek & Rebuffer | OK seconds end to end | OK NaN/negative rejected | N/A | F8-01 normal path has no end clamp | OK | OK | OK stale-chunk drain both sides, last seek wins, first-chunk level, post-seek tiling; F8-02 seek while paused resumes | F8-01, F8-02 |
| 9 | Queue & Playback State | OK request/response models | OK 400/404/503 mapping, index bounds | OK in-process | OK | F9-01 unresolvable entries fall back to raw dict | OK | F9-01 filepath leak; F9-02 state manager never updated by edits; F9-03 duplicate auto-advance; F9-04 no restart persistence; EX #5189 reorder unreachable | F9-01, F9-02, F9-03, F9-04 |

## Findings

### HIGH

### INT-F8-01: Normal (unenhanced) stream seek has no end-of-track clamp — unfixed sibling of closed #5254
- **Severity**: HIGH (same symptom and rating as #5254 on the enhanced path)
- **Flow**: 8 (Seek & Rebuffer)
- **Boundary**: Frontend seek (position = `duration`) → Backend normal-stream chunk plan → Frontend stream end
- **Location**: `auralis-web/frontend/src/components/player/useProgressBarInteraction.ts:162-164` → `auralis-web/backend/ws_handlers/playback_commands.py` (`handle_seek`, dispatches on live `enhancement_settings.enabled`) → `auralis-web/backend/core/chunk_boundaries.py:150-190` (`normal_stream_plan`) → `auralis-web/backend/core/stream_normal_chunks.py:175-192`; reported position at `auralis-web/backend/core/stream_normal.py:196`
- **Status**: NEW (sibling of CLOSED #5254, whose fix is only in `chunk_for_position()`)
- **Description**: `chunk_for_position()` clamps to `duration - SEEK_MIN_CHUNK_REMAINDER` when `total_duration` is given. `normal_stream_plan()` has no duration clamp. It clamps only `start_chunk` to `total_chunks - 1`, while `first_chunk_trim_samples` is still derived from the raw `start_position`. For `start_position >= duration` the first read, `_read_audio_chunk(path, chunk_idx*interval + trim, chunk_samples - trim)`, starts at or past EOF. It returns zero samples, or a negative frame count raises and is recorded as a failed chunk. No later chunk exists, so the stream ends having delivered no audio. The frontend does not clamp either: the End key sends exactly `duration`, and `useEnhancedSeek.ts` has no min/max. `stream_normal.py:196` also reports the raw requested `seek_position`, not an effective one.
- **Evidence**:
  ```python
  # chunk_boundaries.py (normal_stream_plan) — no duration clamp
  if start_position > 0:
      start_sample = int(start_position * sample_rate)
      start_chunk = min(start_sample // interval_samples, total_chunks - 1)
  first_chunk_trim_samples = int(start_position * sample_rate) - (start_chunk * interval_samples) if start_position > 0 else 0
  ```
  ```ts
  // useProgressBarInteraction.ts:162-164
  case 'End': event.preventDefault(); newPosition = duration; break;
  ```
- **Impact**: With enhancement disabled, an End-key seek (or a stored duration slightly short of the decoded length) yields a silent stream. It ends either "errored", which triggers the error/auto-resume path, or with an empty final chunk.
- **Suggested Fix**: Pass `total_duration` into `normal_stream_plan()` and apply the same `min_remainder` clamp before deriving `start_sample`, `start_chunk` and trim, ideally via one clamp helper shared with `chunk_for_position()`. Report the effective position as `seek_position`, as `stream_seek.py` does.

### INT-F9-01: `queue_changed` falls back to raw engine entries — leaks filepaths and pushes id/title-less rows into Redux after any queue edit
- **Severity**: HIGH (agent proposed CRITICAL; recalibrated because the #3205 leak itself was rated LOW for a localhost single-user app, but the broken queue UI after every edit on the normal play path is a realistic, user-visible failure)
- **Flow**: 9 (Queue & Playback State)
- **Boundary**: Engine queue → Backend `QueueService` broadcast → Frontend Redux queue
- **Location**: `auralis-web/backend/services/queue_service.py:128-177` (`_broadcast_queue_changed` hydration + fallback) ← `auralis-web/backend/services/queue_service.py:326-331` (`set_queue` passes `[t.filepath for t in db_tracks]`) and `auralis/player/queue_controller.py:355-365` (wraps each as `{'filepath': track}`, no `id`) → `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:47-56` (`dispatch(reduxSetQueue(data.tracks))`, unvalidated)
- **Status**: NEW (violates the #3205 "never send filepath" invariant; the REST read path is safe)
- **Description**: `_broadcast_queue_changed()` runs on add/remove/reorder/move/shuffle/unshuffle and hydrates entries by `entry['id']`/`entry['track_id']`. A queue started through `POST /api/player/queue`, the standard "play album/playlist" path, holds entries with no id. `by_id` is empty and every entry takes the fallback `track_dict = dict(entry)`, i.e. `{'filepath': '/home/…/track.flac'}`. A library track deleted while queued triggers the same fallback. `QueueChangedPayload.tracks` is `list[dict[str, Any]]`, so nothing catches it. The REST read path (`auralis-web/backend/services/queue_enrichment.py:98-105`) drops unresolvable entries instead.
- **Evidence**:
  ```python
  # queue_service.py:165-170
  if track_dict is None:
      if isinstance(entry, dict):
          track_dict = dict(entry)          # {'filepath': ...}
      else:
          track_dict = {'filepath': entry}
  ```
  ```ts
  // useQueueSubscription.ts
  if (data.tracks) dispatch(reduxSetQueue(data.tracks));
  ```
- **Impact**: After the first edit to a normally-built queue, the Redux queue holds rows without `id`, `title`, `artist` or `duration`, so the queue UI goes blank or corrupt until a full `player_state` or REST refetch replaces it. The absolute local path of every queued file is also broadcast to all WS clients and visible in devtools.
- **Suggested Fix**: Replace the bespoke hydration in `_broadcast_queue_changed` with `QueueEnricher.enrich_tracks()`, which is already correct and drops unresolvable rows. Better still, have `set_queue` store `{'id', 'filepath'}` dicts in the engine so enrichment can always key by id. Type `QueueChangedPayload.tracks` as the serialized `TrackInfo` shape.

### INT-F9-03: Backend `PlayerStateManager` advances "now playing" on its own wall-clock estimate, independent of the real track advance
- **Severity**: HIGH
- **Flow**: 9 (Queue & Playback State)
- **Boundary**: Backend state manager ↔ Frontend auto-advance / NavigationService ↔ Engine queue
- **Location**: `auralis-web/backend/core/state_manager.py:171-198` (`next_track`, in-memory only) and `:305-340` (`_position_update_loop`), started by `set_playing(True)` from `auralis-web/backend/services/queue_service.py:362`, `auralis-web/backend/services/playback_service.py:189,233,275` and `auralis-web/backend/services/navigation_service.py:277` ↔ `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:217-232` (auto-advance → `handleNext`) → `auralis-web/backend/services/navigation_service.py:113-168` (engine navigation + `track_changed`); engine's own advance at `auralis/player/player_streaming_mixin.py:92-159`
- **Status**: NEW
- **Description**: Once playback starts via the normal queue path, the 1 Hz loop ticks `current_time` on wall-clock time. When `new_time >= duration` it awaits `self.next_track()`, which only increments `state.queue_index` and `state.current_track` by indexing `self.state.queue`. It never touches the engine, the stream or `NavigationService`, then broadcasts `player_state`. Meanwhile the frontend advances on its own when the WS stream reports `complete` near the end: `handleNext` computes `currentQueueIndex + 1` from Redux and goes through `NavigationService`. No backend code consumes the engine's `track_completed` callbacks. The backend estimate ignores stream buffering latency and reads a queue that is stale after any edit (INT-F9-02).
- **Evidence**:
  ```python
  # state_manager.py next_track — no engine / navigation call
  if self.state.queue_index < len(self.state.queue) - 1:
      new_index = self.state.queue_index + 1
      next_track = self.state.queue[new_index]
  ...
  await self.update_state(queue_index=new_index, current_track=next_track, current_time=0.0)
  ```
  ```ts
  // PlaybackSessionContext.tsx:224-231
  if (isComplete && nearEnd && hasMoreTracks && !hasAutoAdvancedRef.current) { hasAutoAdvancedRef.current = true; handleNext(); }
  ```
- **Impact**: Near every natural track end, the backend's "now playing" and queue index can disagree with the frontend-driven advance and the engine queue. After a queue edit the backend picks the next track from a stale list. If its snapshot reaches Redux before the frontend's own completion check, `handleNext` may compute from an already-advanced index. That could skip a track; it depends on timing and was not reproduced.
- **Suggested Fix**: Make `PlayerStateManager` reactive. Remove its self-advance branch, keep the loop as a position ticker only, and update now-playing solely from the navigation path's `track_changed` (which the frontend auto-advance already uses), so one path owns "what plays next".

### INT-F2-01: Rescan-driven album creation orphans the album from its artist; the resulting `artist: null` violates the frontend's non-nullable contract
- **Severity**: HIGH
- **Flow**: 2 (Library Browsing), reached from Flow 4 (Library Scanning)
- **Boundary**: Engine (repository/model) → Backend (serializer) → Frontend (transformer/types)
- **Location**: `auralis/library/repositories/track_repository_mutation.py:78-84` (`update_by_filepath`) and `:136-144` (`update`) → `auralis/library/models/album.py:98` (`Album.to_dict`) → `auralis-web/frontend/src/api/transformers/types.ts:18`, `auralis-web/frontend/src/api/transformers/albumTransformer.ts:30`, `auralis-web/frontend/src/types/domain.ts:68`
- **Status**: NEW
- **Description**: Both update paths create `Album(title=..., year=...)` with no `artist_id`, even when the same call has just updated the track's artists. `update_by_filepath()` is the production path for every rescan of a known file (`auralis/library/scanner/batch_processor.py:150-152`), so an external retag into an unseen album title creates a permanently artist-less album. The first-scan path (`auralis/library/repositories/track_repository_lifecycle.py` `_get_or_create_album`) does set `artist_id`, so the album-creation sites disagree. `Album.to_dict()` emits `"artist": null`, while `GET /api/albums/{id}/tracks` (`auralis-web/backend/routers/albums.py:264`) returns `'Unknown Artist'` for the same album. The frontend types `artist: string` and `transformAlbum` passes it through unguarded, unlike every neighbouring optional field.
- **Evidence**:
  ```python
  # track_repository_mutation.py:80-84
  album = session.execute(select(Album).where(Album.title == track_info['album'])).scalars().first()
  if not album:
      album = Album(title=track_info['album'], year=track_info.get('year'))   # no artist_id
  # album.py:98
  'artist': artist.name if artist else None,
  ```
  ```ts
  // types.ts:18            artist: string;
  // albumTransformer.ts:30 artist: apiAlbum.artist,   // no null guard
  ```
- **Impact**: After an ordinary retag and rescan, the album disappears from its artist's page (NULL FK) and renders with a blank artist in album grids, cards and search. This is a persistent library inconsistency with no error anywhere.
- **Suggested Fix**: Engine: route both update paths through the lifecycle mixin's get-or-create logic with the resolved artist id, and add a one-off repair for existing `artist_id IS NULL` albums (backfill from their tracks' artists). Frontend, as defense in depth: type `artist: string | null` and coalesce in `transformAlbum`, or apply the `'Unknown Artist'` fallback in `Album.to_dict()`.

### INT-F4-02: Manual scan never prunes deleted files, and moved files become duplicates
- **Severity**: HIGH
- **Flow**: 4 (Library Scanning)
- **Boundary**: Backend REST scan endpoint ↔ Engine scanner/repository
- **Location**: `auralis-web/backend/routers/library_scan.py` (no `cleanup_missing_files` call) vs `auralis-web/backend/services/library_auto_scanner.py:344-357`; `auralis/library/scanner/batch_processor.py:115-161`, `auralis/library/repositories/track_repository_lookup.py:57-65`
- **Status**: NEW
- **Description**: `cleanup_missing_files()` and the `library_tracks_removed` broadcast run only in the auto-scanner's `_do_scan`; a grep of `auralis-web/backend` finds no other caller. `POST /api/library/scan`, which backs both the Library "Scan Folder" and Settings "Scan Now" buttons, only adds and updates. Rescan matching is keyed purely on the case-folded filepath. A SHA-256 `file_hash` is computed per file in `AudioAnalyzer.extract_audio_info` but never persisted (`Track` has no hash column), so a moved file inserts a new row and the old row stays.
- **Evidence**: `grep -rn cleanup_missing_files auralis-web/backend` → only `auralis-web/backend/services/library_auto_scanner.py:346` (plus a docstring in `auralis-web/backend/config/startup.py`). `batch_processor.py:116`: `existing_track = tracks_repo.get_by_path(file_path) if skip_existing else None`.
- **Impact**: Users with `auto_scan` off (a supported setting), or who rescan manually right after reorganising, accumulate entries for deleted files (which fail when played) and duplicates for moved files.
- **Suggested Fix**: After a successful `scan_directories()` in the manual router, call `tracks.cleanup_missing_files()` via `asyncio.to_thread` and broadcast `library_tracks_removed` with the auto-scanner's payload. Moved-file detection (persist `file_hash` and match on it when the path lookup misses) is a separate follow-up.

### MEDIUM

### INT-F8-02: Seeking while paused audibly resumes playback — the post-seek auto-start ignores the pre-seek pause state
- **Severity**: MEDIUM (user-intent violation: a paused player starts making sound after a scrub; no corruption or data loss)
- **Flow**: 8 (Seek & Rebuffer)
- **Boundary**: Frontend transport intent (paused) → Frontend streaming core / playback engine, across the seek round trip (`seek` → `audio_stream_start is_seek` → `audio_chunk`)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:48-89` (`seekTo`) → `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:178-203` (`resumePlayback` / `stopPlayback`) → auto-start sites `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:210-213` and `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:314-322`
- **Status**: NEW
- **Description**: Pause is purely client-side. `PlaybackSessionContext.handlePlayPause` calls the core's `pausePlayback()`, which calls `engine.pausePlayback()` and `setIsPaused(true)`; no WS `pause` is sent (a grep for `type: 'pause'` in `auralis-web/frontend/src/` finds nothing). `seekTo` then calls `engine.stopPlayback()`, which moves the tracker to `'stopped'` and discards the paused state, and never records `isPaused`. When the seek stream arrives, both auto-start sites call `engine.startPlayback()` and then `setIsPaused(false)`, gated only by a buffer threshold and `!engine.isPlaying()`. `resumePlayback()` returns early unless the state is `'paused'`, so `'stopped'` cannot be resumed. Nothing in code or issue history marks this as intended. The closest issue, closed #2744, reset the *backend* pause/flow events on seek to fix a deadlock, a separate mechanism the frontend pause does not use.
- **Evidence**:
  ```ts
  // useEnhancedSeek.ts:66-68 — pause state neither captured nor preserved
  core.playbackEngineRef.current?.stopPlayback();
  core.pcmBufferRef.current?.reset();
  // useAudioStreamingCore.ts:315-322 — auto-start ignores isPaused
  if (engine && !engine.isPlaying() && result.bufferedSamples >= getStartThreshold(metadata, engine)) {
    engine.startPlayback(); setIsPaused(false);
  }
  // AudioPlaybackEngine.ts:178-181 — cannot resume after stop
  resumePlayback(): void { if (this.positionTracker.getState() !== 'paused') { return; } ... }
  ```
- **Impact**: A user who pauses, scrubs (click, drag, arrow keys, Home/End) and expects to press play later hears audio as soon as the seek stream buffers, and the play/pause control flips to "playing" without being pressed.
- **Suggested Fix**: In `seekTo`, capture `wasPaused = core.isPaused` and carry it into the seek stream start, e.g. a `startPaused` ref read by both auto-start sites. When set, fill the buffer but leave the engine in a resumable paused state instead of calling `startPlayback()`. Put both auto-start sites behind one shared helper so they cannot diverge.

### INT-F9-02: Queue edits never update `PlayerStateManager.state`, so the next `player_state` broadcast reverts Redux to a stale queue / current track
- **Severity**: MEDIUM (agent proposed HIGH; matches the scale's "stale Redux state after a backend event")
- **Flow**: 9 (Queue & Playback State)
- **Boundary**: Backend `QueueService` / `PlayerStateManager` → WS `player_state` → Frontend Redux
- **Location**: `auralis-web/backend/services/queue_service.py:378-749` (`add_track_to_queue`, `remove_track_from_queue`, `reorder_queue`, `move_track_in_queue`, `shuffle_queue`, `unshuffle_queue`, `clear_queue`) vs `auralis-web/backend/core/state_manager.py:152-169` (`set_queue`) → `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:182-193`, `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:47-56`
- **Status**: NEW
- **Description**: A grep of `queue_service.py` for `player_state_manager.` finds calls only in `_set_queue_impl` and `clear_queue`. `clear_queue` calls `set_playing(False)` and `set_track(None, None)` but never `set_queue([])`. `remove_track_from_queue` reloads the engine when the current track is removed but never calls `set_track`. The other edits never touch state at all. `seq` advances on every `_mutate_state()` (volume, pause and so on), and `usePlayerStateSync` applies `state.queue` whenever the top-level `seq` passes. `queue_changed` carries no `seq`, so nothing protects the newer queue.
- **Evidence**:
  ```ts
  // usePlayerStateSync.ts:182-193 — gated only by top-level seq
  if (state.queue && Array.isArray(state.queue)) { const tracks = state.queue.map(...); dispatch(setQueue(tracks)); }
  ```
- **Impact**: After any edit, the next unrelated `player_state` (volume, pause, navigation) restores the pre-edit queue in the UI. After clearing, stale queue length and contents can reappear. After removing the playing track, now-playing keeps showing the removed track.
- **Suggested Fix**: Have every `QueueService` mutation call `player_state_manager.set_queue(enriched, current_index, broadcast=False)` with the same enrichment used for `queue_changed`, and call `set_track()` in the was-current branch of `remove_track_from_queue`. Alternatively, give `queue_changed` a queue generation and have `usePlayerStateSync` ignore older `player_state.queue` payloads.

### INT-F1-03: Local playback-buffer stall is invisible to the UI — silence with no "buffering" indication
- **Severity**: MEDIUM (agent proposed HIGH; no audio is dropped and position does not drift, because the position tracker counts only frames actually played)
- **Flow**: 1 (Track Playback)
- **Boundary**: Frontend playback engine (`BufferScheduler`) → Frontend Redux/UI
- **Location**: `auralis-web/frontend/src/services/audio/BufferScheduler.ts:214-237` (`checkBufferHealth`), `:316-340` (`handleAudioProcess`) → `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:160-162`
- **Status**: NEW
- **Description**: When decoded PCM falls below `lowWaterMarkSeconds` (5 s) because delivery is slower than real time, `checkBufferHealth` pauses output and fills silence, emitting only `console.warn` and no callback. A hard underrun does call `onUnderrun`, but its only subscriber is a `DEBUG`-gated console log, and `isBufferPaused`/`getUnderrunCount` have no UI consumer. Redux `streamingState` is driven by chunk *arrival*, so it stays at `'streaming'` during the silence.
- **Evidence**:
  ```ts
  // useEnhancedStreamStart.ts:160-162
  engine.onUnderrun(() => { DEBUG && console.warn('[usePlayEnhanced] Buffer underrun detected'); });
  ```
- **Impact**: On a slow DSP or chunk, the case the flow-control and look-ahead machinery exists for, playback goes silent for seconds while the transport still shows "playing". It looks like a hang.
- **Suggested Fix**: Report the soft pause/resume transitions and hard underruns through one callback that dispatches a local-buffering flag, separate from the network-driven `streamingState.state`, and render it as a buffering indicator.

### INT-F1-02: `audio_stream_end.reason` (completed/stopped/errored) is emitted but never read
- **Severity**: MEDIUM
- **Flow**: 1 (Track Playback)
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/core/stream_messages.py:118-154,194-269` → `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:338-351`
- **Status**: NEW (closed #4659/#4790 added the backend half; the consumer was never built)
- **Description**: `handleStreamEnd` dispatches `completeStreaming` unconditionally, and the reducer sets `state='complete'` and `progress=100` whatever the reason. A grep for `.reason` in `auralis-web/frontend/src/` finds only unrelated fingerprint and recommendation hits. The one `reason="stopped"` path without an accompanying `audio_stream_error` (enhancement disabled mid-stream, `auralis-web/backend/core/stream_enhanced_chunks.py:76-85`) is currently masked by the client-side reissue in `toggleEnabled()`.
- **Evidence**: `const handleStreamEnd = useCallback((message) => { if (!acceptsStreamType(...)) return; dispatch(completeStreaming({ streamType, trackId: message.data.track_id })); }, ...)`
- **Impact**: Any early stop not compensated elsewhere is shown as a completed track (100%, no error). With INT-F9-03's auto-advance keyed on `'complete'`, it can also trigger a spurious advance.
- **Suggested Fix**: Branch on `message.data.reason`: only `'completed'` should dispatch `completeStreaming`, and `'stopped'`/`'errored'` should surface a soft error or at least not report 100%.

### INT-F1-01: Pre-`audio_stream_start` queued-chunk drain counts `processedChunks` per sub-frame, not per content chunk
- **Severity**: MEDIUM
- **Flow**: 1 (Track Playback)
- **Boundary**: Backend multi-frame `audio_chunk` → Frontend chunk ingest
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:188-206` (vs the correct rule in `auralis-web/frontend/src/hooks/enhancement/audioChunkIngest.ts:173-175`)
- **Status**: NEW (sibling path missed by the #4414 fix)
- **Description**: `ingestChunk` increments `processedChunks` only on a chunk's final sub-frame (`frameIndex >= frameCount - 1`). The drain loop for chunks that raced ahead of `audio_stream_start` hand-rolls `buffer.append` and `processedChunks++` once per queued message, discarding frame metadata.
- **Evidence**: `for (const queuedMessage of queuedChunks) { ...; buffer.append(samples); core.streamingMetadataRef.current!.processedChunks++; }`
- **Impact**: The progress percentage jumps ahead of delivered audio when more than one sub-frame arrives before the start message. Audio is unaffected.
- **Suggested Fix**: Drain the queue through `ingestChunk` so both paths share one counting rule.

### INT-F4-04: Auto-scanner broadcasts an all-zero `scan_complete` when its cycle is rejected by the scan-slot guard, resetting a live manual scan's UI
- **Severity**: MEDIUM (agent proposed HIGH; transient wrong UI state, and the real scan completes and emits its own `scan_complete`)
- **Flow**: 4 (Library Scanning)
- **Boundary**: Backend auto-scan service → Frontend WS handler
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:302-384` (no `rejected` check) vs `auralis-web/backend/routers/library_scan.py:196-197` and `auralis/library/scanner/scanner.py:424` → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:130-142`
- **Status**: NEW (same bug class #4602 fixed for the *start* frame; the complete frame on the auto-scanner side was missed)
- **Description**: `scan_directories()` returns `rejected=True` immediately when another scan holds the slot. The manual router turns that into a 409 with no broadcast, and the scanner skips its own completion callback. `_do_scan` has no such check; the only `rejected` in the file is the #4602 comment at line 214. It runs `cleanup_missing_files` and broadcasts `scan_complete` with zero counts. `useScanProgress` resets to `INITIAL_STATE` (`isScanning: false`) on every `scan_complete`.
- **Evidence**: `scan_result = await asyncio.shield(scan_future)` is followed directly by building `scan_complete_payload` and `broadcast_typed(..., "scan_complete", ...)`, with no `if scan_result.rejected: return`.
- **Impact**: A manual scan overlapping a scheduled or watchdog-triggered auto-scan loses its progress bar and shows "+0 added (0.0s)" while still running.
- **Suggested Fix**: Add `if scan_result.rejected: logger.debug(...); return` immediately after the shielded await, mirroring `scanner.py:424`.

### INT-F4-01: Settings "Scan Now" and all auto-scans hide failed/skipped files from the user
- **Severity**: MEDIUM (agent proposed HIGH; a diagnostics gap with a workaround, since the Library view's "Scan Folder" path does show failures)
- **Flow**: 4 (Library Scanning)
- **Boundary**: Backend WS `scan_complete` / REST scan response → Frontend Settings surface
- **Location**: `auralis-web/frontend/src/services/settingsService.ts:166-168` (`triggerLibraryScan` discards the response) → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:31-39,130-142` → `auralis-web/frontend/src/components/settings/ScanStatusCard.tsx:113-141`
- **Status**: NEW (the #4841 fix covered only `useLibraryScan.ts`)
- **Description**: `useScanProgress` stores `filesFailed`/`filesSkipped` from `scan_complete` but never reads `data.failures`. `ScanStatusCard` renders only `filesAdded`, `filesRemoved` and `duration`; a grep finds no `filesFailed` in the card. `triggerLibraryScan` returns `void`, dropping the REST body.
- **Evidence**: `ScanStatusCard.tsx:125-133` renders `+{lastResult.filesAdded} added`, `−{lastResult.filesRemoved} removed`, `({lastResult.duration.toFixed(1)}s)` and nothing else.
- **Impact**: Corrupt or unsupported files silently fail to import on the primary (auto-scan) path, with no count or filename shown.
- **Suggested Fix**: Render failed/skipped counts in `ScanStatusCard`, carry `failures` into `ScanResult`, and extract `useLibraryScan.ts` `describeFailures()` into a shared helper both surfaces use.

### INT-F4-05: Removing a scan folder revokes path trust for its tracks but never prunes them
- **Severity**: MEDIUM
- **Flow**: 4 (Library Scanning)
- **Boundary**: Backend settings endpoint → Engine library / other backend endpoints
- **Location**: `auralis-web/backend/routers/settings.py:376-386` → `auralis/library/repositories/settings_repository.py:163-183`; `auralis-web/backend/security/path_security.py:84-92` consumed by `validate_file_path()` in `auralis-web/backend/routers/metadata.py`, `auralis-web/backend/routers/tracks.py:183`, `auralis-web/backend/routers/enhancement.py:193,597`
- **Status**: NEW
- **Description**: `POST /api/settings/scan-folders/delete` edits the JSON folder list and calls `unregister_allowed_directory()` in the same request. No code removes or flags `Track` rows under that folder, so they stay listed while every endpoint that validates their stored path rejects them.
- **Evidence**: `SettingsRepository.remove_scan_folder` touches only `settings.scan_folders`; `settings.py:384` calls `unregister_allowed_directory(Path(body.folder))`.
- **Impact**: After a folder is removed, its tracks remain visible, but metadata, track and enhancement operations on them fail with `400 Invalid track filepath` or silently do nothing.
- **Suggested Fix**: Either prune (or offer to prune) tracks under the removed folder and broadcast `library_tracks_removed`, or keep path trust for files still backing a `Track` row until that row is pruned.

### INT-F5-03: Connection-status UI collapses `error`/`disconnected` into `connecting`, so a dead WebSocket shows "connecting" forever
- **Severity**: MEDIUM
- **Flow**: 5 (WebSocket Lifecycle)
- **Boundary**: Frontend connection hook/context → Frontend top bar
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:197-210` → `auralis-web/frontend/src/ComfortableApp.tsx:54,289`
- **Status**: NEW
- **Description**: The hook exposes a 4-state `connectionStatus` and sets `'error'` once reconnect attempts are exhausted and the singleton is retired. `ComfortableApp` destructures only `isConnected` and passes `isConnected ? 'connected' : 'connecting'` to `AppTopBar`, which already supports a `'disconnected'` style.
- **Evidence**: `ComfortableApp.tsx:54` `const { isConnected } = wsContext;`, and `:289` `connectionStatus={isConnected ? 'connected' : 'connecting'}`.
- **Impact**: After a permanent give-up (nothing reconnects until a reload), the indicator still says "connecting" while playback and live updates are dead, with no recovery affordance.
- **Suggested Fix**: Pass the context's `connectionStatus` through, map `'error'` to the disconnected style, and ideally offer a manual reconnect action.

### INT-F5-01: Reconnect loop ignores the close code and retries a permanent 1008 origin rejection
- **Severity**: MEDIUM
- **Flow**: 5 (WebSocket Lifecycle)
- **Boundary**: Backend WS security → Frontend reconnect logic
- **Location**: `auralis-web/backend/config/globals.py:114-129` → `auralis-web/frontend/src/utils/errorHandling.ts:173-178,188-210`
- **Status**: NEW
- **Description**: The backend closes with 1008 (Policy Violation) for untrusted origins, which can never succeed on retry. `WebSocketManager`'s `onclose = () => { ...; this.attemptReconnect(); }` takes no `CloseEvent` and backs off through up to 10 attempts (production) before giving up. A grep for `event.code`/`.code ===` in `utils`, `hooks/websocket` and `contexts` finds nothing.
- **Evidence**: `errorHandling.ts:173-177`.
- **Impact**: Roughly 1–2 minutes of futile retries with no diagnostic, then (via INT-F5-03) a permanent "connecting" label. Rare in the localhost desktop topology.
- **Suggested Fix**: Accept the `CloseEvent` in `onclose`, skip `attemptReconnect()` for policy-class codes such as 1008, and signal permanent failure immediately.

### INT-F6-01: `spectral_centroid`/`spectral_rolloff` are served as normalized 0–1 values, but the API labels them Hz and the frontend applies Hz thresholds
- **Severity**: MEDIUM (agent proposed HIGH; deterministic but display-only, affecting the Album Character gradient and tone tags, with no audio or data impact)
- **Flow**: 6 (Fingerprint & Similarity)
- **Boundary**: Engine DB (normalized) → Backend REST → Frontend display utilities
- **Location**: `auralis-web/backend/routers/fingerprint_status.py:181-182`, `auralis-web/backend/routers/albums.py:339-340`, `auralis-web/backend/schemas.py:372-373` → `auralis-web/frontend/src/utils/fingerprintToGradient.ts:133-140,211-212`, `auralis-web/frontend/src/utils/albumCharacterDescriptors.ts:90-92`
- **Status**: NEW (distinct from closed #4538/#4863, which fixed engine-internal denormalization)
- **Description**: `auralis/analysis/fingerprint/schema.py` declares `spectral_centroid` as `Unit.NORMALIZED` 0–1 (1.0 = `CENTROID_NORMALIZATION_HZ` = 8 kHz), and `auralis/analysis/fingerprint/rust_fingerprint.py:93` writes `raw / CENTROID_NORMALIZATION_HZ`. `centroid_to_hz()`/`rolloff_to_hz()` are called only from `auralis/core/recording_type_detector.py`, so neither REST route converts. `FingerprintVectorResponse` documents both fields as "(Hz)". The frontend clamps the centroid to `[500, 8000]`, tags `> 3500` "Crisp" and `< 1500` "Dark", and defaults missing values to `2000`/`8000`.
- **Evidence**:
  ```python
  # fingerprint_status.py:181   "spectral_centroid": fp.spectral_centroid,     # 0-1, unconverted
  # schemas.py:372              Field(default=None, description="Spectral centroid (Hz)")
  ```
  ```ts
  // fingerprintToGradient.ts:135     const normalizedCentroid = Math.max(500, Math.min(8000, centroid));
  // albumCharacterDescriptors.ts:90  if (fp.spectral_centroid > 3500) { 'Crisp' } else if (< 1500) { 'Dark' }
  ```
- **Impact**: For every real track the centroid clamps to the 500 floor. The brightness→lightness mapping is constant across album cards, media-card artwork, the era view and the Album Character pane, and every album is tagged "Dark", never "Crisp". Test fixtures mix Hz-scale and fraction-scale values, so the suite cannot catch it.
- **Suggested Fix**: Convert at the backend boundary with `centroid_to_hz()`/`rolloff_to_hz()` in both routes, matching the documented "(Hz)" contract. The alternative is to keep 0–1 on the wire, fix the field descriptions and rescale the frontend thresholds. Align the test fixtures either way.

### INT-F6-02: Similarity pre-filter uses a ±8.0 tolerance on `bass_pct`, a 0–1 fraction
- **Severity**: MEDIUM
- **Flow**: 6 (Fingerprint & Similarity)
- **Boundary**: Engine similarity search → Library repository range query (serves `/api/similarity/tracks/{id}/similar`)
- **Location**: `auralis/analysis/fingerprint/similarity.py:328` → `auralis/library/repositories/fingerprint_similarity_mixin.py:189-235`
- **Status**: NEW
- **Description**: `_get_prefiltered_candidates` builds `(bass_pct - 8.0, bass_pct + 8.0)` with a `# ±8%` comment, but `schema.py:55` declares `bass_pct` as `Unit.FRACTION` in `(0.05, 0.50)`. The range always matches everything, so the dimension contributes nothing to the pre-filter.
- **Evidence**: `'bass_pct': (target_fp.bass_pct - 8.0, target_fp.bass_pct + 8.0),  # ±8%` vs `'bass_pct': (Unit.FRACTION, 0.05, 0.50)`.
- **Impact**: When the lufs/crest/tempo match set exceeds `n * prefilter_factor`, the unordered SQL `LIMIT` truncates arbitrarily, so tracks with very different bass profiles displace closer matches and result quality degrades silently in larger libraries.
- **Suggested Fix**: Use `± 0.08` and fix the comment. Separately, `auralis/library/fingerprint_quantizer.py` bounds assume 0–100 for `*_pct`. It has no production write path today but must be fixed before it is wired up.

### INT-F7-01: Track grid and list views never cache-bust artwork on `artwork_updated`, unlike album views
- **Severity**: MEDIUM
- **Flow**: 7 (Artwork)
- **Boundary**: Backend WS `artwork_updated` broadcast → Frontend track components
- **Location**: `auralis-web/backend/routers/artwork.py:526,575,642` → `auralis-web/frontend/src/components/track/TrackCard.tsx:61`, `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:101`
- **Status**: NEW
- **Description**: `AlbumArt.tsx`, `AlbumCard.tsx` and `useArtworkPalette.ts` are the only production users of `useArtworkRevision(albumId)`, which appends a revision parameter so the `<img src>` changes and the browser re-fetches. `TrackCard` and `TrackRow` pass `track.artworkUrl` only through `withArtworkSize()`, so the URL never changes after artwork is extracted, downloaded or deleted.
- **Evidence**: `TrackCard.tsx:61` `artworkUrl={withArtworkSize(albumArt, artworkSize)}` and `TrackRow.tsx:101` `withArtworkSize(track.artworkUrl ?? undefined, 80)`, vs `AlbumArt.tsx:97-101` `getArtworkUrl(albumId, { size, revision: artworkRevision })`.
- **Impact**: After an album's artwork changes, mounted track grids, lists, playlists and queue rows keep the old image (or a broken one after deletion) until refetched, while album views update live.
- **Suggested Fix**: Derive the revision from `track.albumId` via `useArtworkRevision` in `TrackCard`/`TrackRow`, or better, give `withArtworkSize` a revision option so one helper owns cache-busting.

### LOW

### INT-F3-01: Chunk-cache keys round `intensity` to three different precisions
- **Severity**: LOW (agent proposed MEDIUM; latent, since no shipped surface emits an off-grid intensity: the slider steps by 0.1 and every default is 1.0)
- **Flow**: 3 (Audio Enhancement)
- **Boundary**: Backend enhancement settings → Backend chunk-cache tiers
- **Location**: `auralis-web/backend/cache/manager.py:123` (`.1f`), `auralis-web/backend/core/chunk_cache.py:59` (`.2f`), `auralis-web/backend/core/chunk_cache_manager.py:86` (unrounded)
- **Status**: NEW
- **Description**: `intensity` is a continuous float accepted anywhere in `[0,1]` over REST (`EnhancementIntensity`) and WS (`is_valid_intensity`). The streamlined in-memory tier keys on one decimal, while the on-disk tier that renders and names the file keys on the raw value. Two requests in the same 0.1 bucket (e.g. 0.06 and 0.14) share a streamlined-tier key, so the second can be served the file rendered for the first.
- **Evidence**: `f"{track_id}_{preset_key}_{intensity:.1f}_{chunk_idx}_{file_signature}"` vs `f"{track_id}_{file_signature}_{preset}_{intensity}_chunk_{chunk_index}"`.
- **Impact**: A non-UI client, or any future finer-grained control, sending off-grid intensities gets audio mastered at stale settings.
- **Suggested Fix**: Share one canonical intensity-key formatter (a rounding constant beside `INTENSITY_MIN/MAX`) across all three tiers, or quantise intensity at the API boundary.

### INT-F4-06: Scanner emits `phase: 'counting'`, which the frontend phase union does not declare
- **Severity**: LOW
- **Flow**: 4 (Library Scanning)
- **Boundary**: Engine scanner → Backend WS bridge → Frontend types
- **Location**: `auralis/library/scanner/scanner.py:266-273` → `auralis-web/backend/routers/library_scan.py:158`, `auralis-web/backend/services/library_auto_scanner.py:267` → `auralis-web/frontend/src/types/ws/library.ts:116`, `auralis-web/frontend/src/hooks/library/useScanProgress.ts:28`
- **Status**: NEW
- **Description**: Both bridges forward `stage` verbatim as `phase`, and the #4840 pre-count pass emits `'counting'`. The frontend types declare only `'discovering' | 'processing'`.
- **Evidence**: `phase?: 'discovering' | 'processing';` vs `'stage': 'counting'`.
- **Impact**: Benign today, since no UI branches on `phase`. A future exhaustive switch would mishandle it silently.
- **Suggested Fix**: Add `'counting'` to both unions, or define the phase literal once in `outbound_messages.py` and mirror it.

### INT-F5-02: `WEBSOCKET_API.md` documents a fictitious `player_state` payload, omits most client→server commands, and still lists removed presets
- **Severity**: LOW
- **Flow**: 5 (WebSocket Lifecycle), plus Flow 3's preset-narrowing consistency check
- **Boundary**: Documentation ↔ backend protocol contract
- **Location**: `auralis-web/backend/WEBSOCKET_API.md:33-165,622-673` (preset line `:637`) vs `auralis-web/backend/websocket/outbound_messages.py:46-63`, `auralis-web/backend/ws_handlers/connection.py:180-207`, `auralis-web/backend/schemas.py` (`VALID_PRESETS`)
- **Status**: NEW (distinct from closed #4988/#4991)
- **Description**:
  1. The documented `player_state` is camelCase (`currentTrack`, `isPlaying`, 0–1 `volume`). The real payload is snake_case with `seq`, `state`, `current_time`, 0–100 `volume` and more.
  2. "Client → Server Commands" documents only `play_enhanced`/`play_normal`, not `pause`, `resume`, `stop`, `seek`, `buffer_full`, `buffer_ready`, `ping`, `pong` or `heartbeat`.
  3. Line 637 still says `preset` is "One of: adaptive, gentle, warm, bright, punchy"; neither preset-narrowing commit touched this file.
- **Evidence**: `WEBSOCKET_API.md:637`: `"preset"?: string, // Optional. One of: adaptive, gentle, warm, bright, punchy.`
- **Impact**: Documentation only, but this is the protocol reference named in `CLAUDE.md`.
- **Suggested Fix**: Regenerate the `player_state` example from `PlayerStatePayload`, document every routed inbound type, and state `adaptive` only (or reference `VALID_PRESETS`).

### INT-F1-04: `PCMStreamBuffer` reserves a full/empty disambiguation slot but its overflow check does not honour it
- **Severity**: LOW
- **Flow**: 1 (Track Playback)
- **Boundary**: Frontend WS chunk ingest → circular PCM buffer
- **Location**: `auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts:80-91,240-280`
- **Status**: NEW
- **Description**: `initialize()` allocates `capacityInSamples + 1`, but `writeToBuffer` computes `freeSpace = buffer.length - used` without subtracting the reserved slot. Filling the buffer exactly makes `writePos === readPos`, which reads as empty.
- **Evidence**: `const bufferCapacity = this.buffer.length; const freeSpace = bufferCapacity - currentlyUsed;`
- **Impact**: Not reachable under current flow control, which pauses the backend at 75% fill of a ~25M-sample buffer. A latent defense-in-depth gap.
- **Suggested Fix**: `freeSpace = bufferCapacity - currentlyUsed - 1`.

### INT-F9-04: `QueueRepository` is unwired — the playback queue is not persisted across restart
- **Severity**: LOW (agent proposed MEDIUM; a missing feature or dead code rather than a mismatch between two live layers)
- **Flow**: 9 (Queue & Playback State)
- **Boundary**: Backend/Engine → Library persistence (absent)
- **Location**: `auralis/library/repositories/queue_repository.py` (`get_queue_state`, `set_queue_state`, `update_queue_state`, `clear_queue`); exposed via `auralis/library/repositories/factory.py:156-159` and `auralis/library/database.py:282-283`
- **Status**: NEW (related to OPEN #5246, an off-by-one inside the same unreachable method)
- **Description**: A grep of `auralis/` and `auralis-web/backend/` outside tests for `get_queue_state|set_queue_state|update_queue_state` finds only the repository itself. No startup hook restores a queue and no `QueueService` mutation persists one. Only `queue_history_repository.py` (the undo stack) is live.
- **Evidence**: grep above.
- **Impact**: Closing and reopening the desktop app loses the queue. The repository's presence among the "13 repos" in the architecture docs suggests the feature exists when it does not.
- **Suggested Fix**: Decide product intent. Either wire `set_queue_state()` into `QueueService` mutations and replay `get_queue_state()` at startup, or delete `QueueRepository` along with #5246's target code.

## Relationships

**R1 — A fix landed in one of two parallel implementations** (10 findings). Each of these closed issues fixed one copy of duplicated logic, and a sibling kept the bug:

| Finding | Fixed copy | Unfixed sibling |
|---------|------------|-----------------|
| INT-F8-01 | `chunk_for_position` (#5254) | `normal_stream_plan` |
| INT-F4-04 | manual router / scanner rejection guard (#4602) | auto-scanner completion |
| INT-F4-01 | `useLibraryScan` failure toast (#4841) | Settings/auto-scan card |
| INT-F1-01 | `ingestChunk` sub-frame counting (#4414) | pre-start drain loop |
| INT-F9-01 | `QueueEnricher` | bespoke `_broadcast_queue_changed` hydration |
| INT-F2-01 | lifecycle album creation | two update-path creations |
| INT-F4-02 | auto-scanner prune | manual scan |
| INT-F8-02 | — | two auto-start sites, neither honouring pause |
| INT-F7-01 | album views' revision hook | track views |
| INT-F3-01 | — | three cache-key builders |

This is the project's DRY / No-variants principle failing at the boundary. The durable fix in each case is to collapse the pair into one shared helper, not to patch the second copy. Any future fix to one member of these pairs should grep for the sibling.

**R2 — Split-brain queue / now-playing** (INT-F9-01, INT-F9-02, INT-F9-03, with existing #5189). Three stores (engine queue, `PlayerStateManager.state`, Redux) are written by different paths with no generation protocol. Fix these three together. INT-F9-01's enrichment output is exactly what INT-F9-02 should store, and INT-F9-03's advance should be driven from the same authoritative path. INT-F1-02 interacts: a stopped stream reported as `'complete'` feeds the frontend auto-advance.

**R3 — Units and literals defined only in comments** (INT-F6-01, INT-F6-02, INT-F3-01, INT-F4-06, INT-F5-02). Scale or literal contracts live in docstrings, so the wire, the docs and the consumers drift. Typed payload literals (`outbound_messages.py` → `auralis-web/frontend/src/types/ws/`) and one conversion site per unit would prevent the class.

**R4 — State computed but dropped at the last hop** (INT-F1-02, INT-F1-03, INT-F4-01, INT-F5-03, and INT-F5-01 feeding INT-F5-03). In each case the backend or engine already produces the signal and only the UI surfacing is missing. These are cheap, frontend-only fixes.

**R5 — Library consistency across scan entry points** (INT-F2-01, INT-F4-02, INT-F4-04, INT-F4-05). Manual scan, auto-scan, rescan-update and folder removal each apply a different subset of the library's invariants (artist linkage, pruning, rejection handling, trust revocation).

## Prioritized Fix Order

1. **INT-F8-01**: small and contained (one clamp plus the effective position), silent-audio symptom, mirrors an already-accepted fix (#5254).
2. **INT-F9-01 → INT-F9-02 → INT-F9-03** as one change set. Reuse `QueueEnricher` in the broadcast, store the same enriched list in `PlayerStateManager`, then remove the state manager's self-advance. INT-F9-01 alone breaks the queue UI after every edit.
3. **INT-F2-01**: engine fix plus a repair pass for already-orphaned albums. This is the one finding that leaves bad data behind, so the longer it waits the more rows need repair.
4. **INT-F4-02 and INT-F4-04**: small backend additions that reuse existing repository methods and payloads.
5. **INT-F8-02**: user-visible transport misbehaviour. Fold both auto-start sites into one helper.
6. **INT-F6-01 and INT-F6-02**: one-line unit conversions with visible payoff (album tone tags and gradient; similarity quality). Align the test fixtures.
7. **R4 surfacing bundle**: INT-F1-02, INT-F1-03, INT-F5-03, INT-F5-01, INT-F4-01. All frontend, low risk.
8. **INT-F7-01, INT-F4-05, INT-F1-01**.
9. **LOW**: INT-F3-01 (before any finer-grained intensity control ships), INT-F4-06, INT-F5-02 (cheap doc fix, and the last removed-preset reference), INT-F1-04, INT-F9-04 (product decision first).

## Skipped as Existing (verified still open / still valid)

- **#4820** (OPEN, HIGH): frontend scan cancellation never reaches the backend (`useLibraryScan.ts:100-102` ↔ `library_scan.py:175-193` `asyncio.shield`). Re-confirmed.
- **#4816** (OPEN): library reset does not pause an in-flight manual scan.
- **#5196** (OPEN, LOW): 5.0 s scan-cancel grace timeout duplicated in the manual router and auto-scanner.
- **#4823** (OPEN, LOW): scanner follows symlinks without containment. **#4973** (OPEN, LOW): dead `LibraryScanner` compat shims.
- **#5271** (OPEN): seeded `enhancement_intensity` not range-guarded like `default_preset`. Re-confirmed.
- **#5190 / #5019** (OPEN): raw `fetch()` calls with no timeout in the playback flow (queue POST, track GET).
- **#5189** (OPEN): queue/playlist reorder unreachable on the frontend. **#5246** (OPEN): `QueueRepository.update_queue_state` off-by-one (see INT-F9-04).
- **#5258** (OPEN, LOW): no single-flight dedup for concurrent seek requests to one chunk key.
- **#5069** (OPEN): rate-limit table omits outbound artwork-download fetches.
- **#5281** (OPEN, LOW), "`buffer_presets_for_track` never called": **appears stale**. `auralis-web/backend/core/stream_enhanced.py:174-179` now calls it via `spawn_background_task`, wired on 2026-08-25 ("fix: wire up proactive preset buffering into the real play_enhanced path"). Recommend verifying and closing.

Closed issues spot-checked and confirmed still fixed (no regressions): #3205 (Pydantic `TrackInfo.filepath` exclude; the INT-F9-01 leak bypasses it via a raw dict), #4414, #4557, #4560, #4563, #4580, #4602, #4616, #4626, #4629, #4630, #4643, #4654, #4656, #4659/#4790, #4677, #4742, #4776, #4813, #4833, #4841, #4842, #4849, #4864, #4870, #4881, #4901, #5075, #5254 (enhanced path only; see INT-F8-01).

## Candidates Not Reported (disproved or reclassified during verification)

- **INT-F7-02** (flow agent, MEDIUM, "now-playing artwork has no `onError` and no size hint"): **dropped**. `auralis-web/frontend/src/components/player/TrackInfo.tsx` has no production importer. The only `<TrackInfo>` in use is a styled `Box` from `TrackRow.styles.ts`, so the component is dead code, not the live player bar. This is tech-debt territory (delete it) and not an integration defect.
- **INT-F4-03**: the same defect as OPEN #4820; listed above, not counted.
- Seek-while-paused (INT-F8-02) was briefly considered intentional and then **kept**. Neither code comments nor issue history (including #2744, which concerns backend pause-event deadlock) document "seek resumes playback" as a design decision.
- Flow-agent candidates disproved on re-read: stale `desktop/resources/auralis/` preset tables are gitignored build output rsynced from `auralis/` in CI; the dev/prod `WS_BASE_URL` branch resolves identically in every supported topology; `FingerprintQuantizer`'s 0–100 bounds have no production write path; track `Track.duration` is decode-accurate (soundfile/ffprobe), so the auto-advance `nearEnd` tolerance holds; chunk seam tiling, binary frame pairing, flow-control round trip, first-post-seek level reset and post-seek tiling were all re-derived as correct; the `usePlaybackWithDecay` `setIntensity` is animation state, not an enhancement surface.

---
Next step: `/audit-publish docs/audits/AUDIT_INTEGRATION_2026-09-13.md`
