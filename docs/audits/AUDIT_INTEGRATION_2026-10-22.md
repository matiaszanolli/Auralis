# Integration Audit — Backend ↔ Frontend ↔ Engine — 2026-10-22

**Scope**: the 9 critical data flows of `.claude/commands/audit-integration.md`, traced fresh against the live tree (HEAD `44e4d433` at audit start). Depth: deep. Limit: none.
**Method**: one flow agent per flow (max 3 concurrent), each reading both sides of every boundary and deduplicating against all 5,613 GitHub issues (open and closed, up to #5859). The orchestrator then merged the results, removed cross-flow duplicates and re-verified every HIGH finding against the source.
**Not used**: prior reports in `docs/audits/`, test runs.

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 7 |
| MEDIUM | 33 |
| LOW | 41 |
| **Total** | **81** (91 raw flow findings, minus 10 cross-flow duplicates merged) |

Five findings are regressions of closed issues: #2259 and #4563 (both HIGH, in the seek path), plus #4338, #5469 and #5474. 34 already-open issues still reproduce; they are listed below and not re-reported.

**Key themes**

1. **The `is_seek` resume contract is broken in three ways (HIGH ×3).** Seek, live enhancement re-issue and WS-reconnect resume all send a play/seek command and get back `audio_stream_start{is_seek:true}`. The client then takes the #3185 "resume into existing buffer" early return in `useEnhancedStreamStart.ts`, and three things go wrong:
   - The seek offset is never applied, so the clock restarts at 0 after every seek (INT-F8-1, regression of #2259). This also breaks auto-advance and reconnect resume.
   - Pre-seek frames that land between the click and the new `audio_stream_start` pass the epoch filter and play at the head of the seek (INT-F1-1, regression of #4563).
   - Re-issues send the *playhead* while keeping a buffer that runs ahead of it, so audio repeats (INT-F1-3).
   Three flow agents found the seek-offset bug independently.
2. **Backpressure can truncate playback (HIGH).** After `buffer_full` the client only re-evaluates flow control when another chunk arrives. The server stops sending chunks once it receives `buffer_full`, so `buffer_ready` is never sent, and the backend's `flow_evt.wait()` has no timeout (INT-F5-1). The WS rate limiter also counts `buffer_full`/`buffer_ready`, and it rejects commands without saying which one (INT-F5-6).
3. **Two UI surfaces write the same enhancement state through different transports.** The Settings dialog saves through `PUT /api/settings`, which never re-issues the stream. Turning auto-enhance off there stops playback silently (INT-F3-1, HIGH). Intensity changes made there never reach the playing stream or later seeks (INT-F3-2).
4. **The backend state manager is applied wholesale but rarely updated.** `player_state` frames overwrite client-owned volume, mute, playing, duration and shuffle with stale values (INT-F9-1, INT-F9-2; the queue half is open #5460). The reconnect watermark reset races the first snapshot (INT-F5-3). An evicted broadcast client stays connected but receives nothing (INT-F5-5).
5. **Library contract gaps at scale.** Search, sort and refresh work only on the loaded pages (INT-F2-1 HIGH, INT-F2-2, INT-F2-5). A manual folder scan imports tracks that streaming then refuses to play, because the folder is never registered in the path allowlist (INT-F4-1 HIGH). Scan errors and concurrent scans are invisible or confusing in the UI (INT-F4-2..4).

**Clean areas (verified, not just assumed)**
- **Chunk tiling.** Flow 1 checked emitted-segment tiling numerically over 210 rate/duration cases with the real `trim_context` + `extract_chunk_segment`, and it is exact. Seek index/offset math in `chunk_for_position` lands on the requested sample.
- **Binary format and sample rate.** The binary PCM frame format (float32 LE interleaved, 76,800-float frames, meta/binary pairing with `seq`) and the sample rate match end to end, from probe to `audio_stream_start` to `AudioContext`.
- **Preset vocabulary.** Only `'adaptive'` exists on every surface, and no retired preset name crosses an API boundary.
- **No `filepath` leak.** No queue or player payload carries `filepath` (#3205 holds). INT-F2-11 records a separate path-valued column (`recommended_reference`) that does leak.
- **Queue mutations.** Every queue mutation re-enriches from the engine queue before broadcasting, and `queue_changed` emits only snake_case `current_index`.
- **Backend teardown on disconnect.** Heartbeat, stream task, events, rate-limit bucket and membership are all released.

## Flow Coverage Matrix

| # | Flow | Schema match | Error handling | Timeouts | Data types | Null handling | Case conversion | Findings (H/M/L after merge) |
|---|---|---|---|---|---|---|---|---|
| 1 | Track Playback | ISSUE (F1-3, F1-8) | ISSUE (F1-4, F5-6) | OK (watchdog 45 s > backend worst 35 s) | OK (float32 LE, sr/channels consistent; #5709 open) | OK | OK (snake_case WS; `transformTrack`) | 2 / 1 / 2 |
| 2 | Library Browsing | ISSUE (F2-1, F2-2, F2-12, F2-13) | ISSUE (F2-4) | OK | OK | ISSUE (F2-13) | ISSUE (#5823 open: `has_more`/`hasMore`) | 1 / 6 / 7 |
| 3 | Audio Enhancement | ISSUE (F3-3) | ISSUE (F3-1) | OK | OK (0-1 float end to end; F3-6 bucket) | ISSUE (F3-3, F3-7) | N/A (snake_case both sides) | 1 / 3 / 3 |
| 4 | Library Scanning | ISSUE (F4-3, F4-9, F4-10) | ISSUE (F4-2, F4-4, F4-11) | ISSUE (F4-8) | OK | OK | OK | 1 / 5 / 5 |
| 5 | WebSocket Lifecycle | ISSUE (F5-9, F5-12) | ISSUE (F5-4, F5-6) | ISSUE (F5-1, F5-5) | OK | OK | N/A | 1 / 6 / 3 |
| 6 | Fingerprint & Similarity | ISSUE (F6-4, F6-7, F6-10) | ISSUE (F6-6, F6-9, F6-13) | OK | ISSUE (F6-12 score calibration) | ISSUE (F6-1) | OK | 0 / 6 / 7 |
| 7 | Artwork | ISSUE (F7-4) | ISSUE (F7-1) | OK | ISSUE (F7-6, F7-8 formats) | ISSUE (F7-4) | OK | 0 / 3 / 5 |
| 8 | Seek & Rebuffer | ISSUE (F8-6, F8-7) | ISSUE (F1-1, F5-6) | OK | ISSUE (F8-1: client clock drops `seek_position`) | OK | N/A | 1 / 1 / 3 |
| 9 | Queue & Playback State | ISSUE (F9-1, F9-2, F9-4) | OK (`runOptimistic` rollback) | OK | OK | ISSUE (F9-3, F9-4) | OK (only `current_index` emitted) | 0 / 2 / 6 |

Merged findings are counted under the flow of their primary ID.

## Findings

Finding IDs keep their originating flow (`INT-F<flow>-<n>`) for traceability. Merged duplicates are listed on the primary finding under **Merged duplicates**.

### CRITICAL (0)

None.

### HIGH (7)

#### INT-F1-1: Regression of #4563 - stale pre-seek frames pass the epoch filter and are kept by the `is_seek` buffer-preserve path
- **Severity**: HIGH
- **Flow**: 1 - Track Playback (seek)
- **Boundary**: Backend `stream_protocol`/`stream_messages` epoch stamp -> Frontend `classifyChunk` / resume guard
- **Location**: `auralis-web/backend/core/stream_protocol.py:232`, `core/stream_messages.py:90-91,110-118` -> `auralis-web/frontend/src/hooks/enhancement/audioChunkIngest.ts:71-73`, `hooks/enhancement/useEnhancedSeek.ts:68-86`, `hooks/enhancement/useEnhancedStreamStart.ts:94-107`
- **Status**: Regression of #4563 (fix is present but cannot take effect for the scenario it was written for)
- **Description**: #4563's scenario is: client resets its PCM buffer and sends `seek`; frames the old stream had already queued/sent arrive after the reset and are appended; the follow-up `audio_stream_start{is_seek:true}` preserves the buffer, so the stale audio plays at the head of the seek. The fix stamps a `stream_epoch` and has the client drop chunks whose epoch differs from the one recorded at `audio_stream_start`. But the client only adopts the new epoch when the NEW `audio_stream_start` arrives, and the backend cancels and awaits the old task BEFORE it sends the new start (`handle_seek` -> `_cancel_prior_task` -> `seek_started` -> new task). WebSocket order is preserved, so every superseded frame arrives while `streamEpochRef` still holds the OLD epoch, i.e. `incomingEpoch === currentEpoch`, and passes. After the new start no old-epoch frame can arrive at all, so the filter only guards a case that cannot occur. The only thing that later clears the stale audio is the unrelated out-of-sequence heuristic, and that fires only for backward seeks more than one chunk back.
- **Evidence**:
  - `useEnhancedSeek.ts:68-69`: `core.playbackEngineRef.current?.stopPlayback(); core.pcmBufferRef.current?.reset();` then `:86` `wsContext.send({type:'seek',...})`. `streamEpochRef` is not touched here.
  - `audioChunkIngest.ts:71-73`: `if (incomingEpoch != null && currentEpoch != null && incomingEpoch !== currentEpoch) return 'superseded-epoch'` - old frames carry the epoch == current, so they are accepted and appended to the freshly reset ring (`useStreamMessageHandlers.ts:255 ingestChunk`).
  - `useStreamSubscriptions.ts:104`: `streamEpochRef.current = incomingEpoch ?? null;` only on the new `audio_stream_start`.
  - `useEnhancedStreamStart.ts:94-107`: with `is_seek` and a live engine+buffer the handler only updates `totalChunks`, clears `pendingChunksRef` and returns - the ring is NOT reset.
  - `useStreamMessageHandlers.ts:123-131` (`isOutOfSequence` -> `buffer.reset()`) is the only incidental cleanup: `audioChunkIngest.ts:88-90` `incoming < last - 1`, and `lastReceivedChunkIndexRef` was set back to -1 by `useEnhancedSeek.ts:73`, then re-set to the stale frame's index by the first stale frame.
  - The shipped frontend test described in #4563's plan feeds a stale-epoch chunk AFTER the new start, which is the unreachable ordering.
  - `audio_stream_controller.py:82-96` comment itself states the pre-seek frames "land in the FRESH buffer", which is exactly before the epoch is known to the client.
- **Impact**: Whenever the backend is still streaming when the user seeks (any track that is still being rendered, flow-paused long tracks, hi-res material), 0.9-3.5 s (the code's own estimate: 4 queued frames plus socket buffers) of pre-seek audio plays at the head of the seek. `startPlaybackWhenBuffered` starts the engine as soon as 96 000 samples are in the ring, so the stale audio can start playing even before the new `audio_stream_start`. Backward seeks of more than one chunk accidentally self-heal via the out-of-sequence reset; forward seeks and small seeks do not.
- **Suggested Fix**: Make the client discard on the boundary it actually has. Cleanest: in `useEnhancedStreamStart` seek fast path, call `core.pcmBufferRef.current.reset()` (and stop/clear the engine) when `message.data.stream_epoch` differs from the epoch the buffer was filling under, i.e. treat a new epoch as "buffer content is from a superseded stream" regardless of `is_seek`. Alternative: have `seekTo` bump a client-side "expected next epoch" gate (drop everything until the next `audio_stream_start`), or have the backend send a discard marker the client uses to reset. Add a test that feeds stale-epoch frames BEFORE the new start.
- **Merged duplicates**: INT-F8-2. Found independently by Flows 1 and 8 (Flow 8 rated it MEDIUM on the grounds that the window is small on localhost; kept at HIGH because it is the exact failure HIGH #4563 was filed for and the window covers every seek while the backend is still rendering). Flow 8 adds: (a) `seek_started` is sent after the old task is fully cancelled (`playback_commands.py:453`), so it is a clean ordering boundary the client could reset on but only uses to clear `isSeeking`; (b) `audio_stream_end` / `audio_stream_error` carry no `stream_epoch` (`stream_messages.py:175-196`), so a late error from the superseded same-track stream also tears down the new one.

#### INT-F1-3: Live preset/intensity/enable change and WS-reconnect resume re-stream from the playback position but keep (or partly keep) the already-buffered audio, replaying seconds of audio
- **Severity**: HIGH
- **Flow**: 1 - Track Playback (stream re-issue / resume)
- **Boundary**: Frontend `reissueActiveStreamAs` / reconnect resume -> Backend `stream_from_position` (`is_seek:true`) -> Frontend resume guard + ring buffer
- **Location**: `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:94-100`, `websocketConnectionCore.ts:56-61`, `hooks/enhancement/usePlaybackTransport.ts:167-169` -> `auralis-web/backend/routers/system_streams.py:83-91` (`start_position>0` -> `stream_enhanced_audio_from_position`) -> `hooks/enhancement/useEnhancedStreamStart.ts:94-107`, `useStreamMessageHandlers.ts:123-131`
- **Status**: NEW
- **Description**: `is_seek:true` tells the client "append to the existing buffer" (`useEnhancedStreamStart.ts:92-107`). That assumption holds only when the new stream begins exactly where the buffered audio ends. Re-issues (`useEnhancementCommands.ts` toggle/preset/intensity) and reconnect resumes instead send `start_position = engine.getCurrentPlaybackTime()` - the position being played NOW. The ring and the worklet queue are ahead of that position (worklet look-ahead `workletLookaheadSeconds: 3.0`, ring up to the whole track once delivered). Nothing resets the buffer or the worklet on the re-issue path (only `seekTo` does).
  Two outcomes depending on how far ahead the old stream was:
  1. New first chunk index < `lastReceivedChunkIndex - 1` (typical once the backend is 2+ chunks ahead): `isOutOfSequence` fires, `buffer.reset()` + `setCurrentTime(0)`, but the worklet keeps its ~3 s queue (`WorkletOutput.disconnect()` is not called). The worklet plays P..P+3 (old settings) then the new stream, which starts at P again: 0-3 s of audio is replayed, plus a silent gap if DSP of the uncached chunk takes longer than the remaining queue.
  2. Otherwise the ring keeps `[P+3 .. buffered end]` and the new stream `[P ..]` is appended after it: everything between P and the buffered end (up to ~20 s, or the rest of the track if fully delivered but within 1 chunk) is played twice, and the new preset is heard only after the old-settings audio has finished.
  In both cases the tracker keeps counting `samplesPlayed` over the replayed audio, so the readout runs ahead of the real position by the replay length and auto-advance (INT-F1-2 clock) fires early at the end, cutting the tail.
  Secondary: the `BufferHealth.streamEnded` latch set by `markStreamEnded()` on the previous `audio_stream_end` is only cleared by `stopPlayback()` (`AudioPlaybackEngine.ts:204`), which a re-issue never calls, so for the rest of the track the 5 s/8 s hysteresis is disabled and a slower-than-realtime re-render degrades to hard underruns instead of clean low-water pauses.
- **Evidence**:
  - `useOutgoingChannel.ts:94`: `const resumePos = startPositionOverride ?? connState.resumeGetters[type]?.() ?? 0;` where the getter is `usePlaybackTransport.ts:167-168` `playbackEngineRef.current?.getCurrentPlaybackTime()`.
  - `system_streams.py:83-91`: `if start_position > 0: await controller.stream_enhanced_audio_from_position(... start_position=start_position)` -> `audio_stream_start{is_seek:true}` (`stream_messages.py:93-118`).
  - `useEnhancedStreamStart.ts:92-107`: resume guard comment "let new chunks append seamlessly (#3185)", no buffer/worklet reset, `lastReceivedChunkIndexRef` and `flowPausedRef` not reset either (those are only reset at `:201-203` on the recreate path).
  - `useStreamMessageHandlers.ts:123-131`: out-of-sequence branch resets only the ring and `setCurrentTime(0)`.
  - `useEnhancementCommands.ts:91-96,168,234`: `reissueRef.current('play_enhanced', {...})` with no preceding engine/buffer teardown.
- **Impact**: Every mid-playback preset/intensity change, enhancement toggle (these reissue at the current position by design, #3759/#3763) and every WS reconnect during playback produces repeated audio (0-3 s typical, up to ~20 s when the stream is only slightly ahead), a progress readout that runs ahead afterwards, and early auto-advance. This is the "repeated samples at a seam" class (HIGH), on a core feature.
- **Suggested Fix**: Make the resume contract explicit. Either (a) client: before sending a re-issue, do what `seekTo` does for the position being left (stop the engine and clear the worklet queue and the ring), then send `start_position = current position`, then re-apply the offset when the new stream starts (see INT-F1-2); or (b) protocol: add a distinct field (e.g. `resume:true` / `buffer_end_position`) so the client keeps its buffer only when the backend resumes from the buffered end, and report the buffered-end time (not the playback time) as the resume position in that mode. Also clear `streamEnded` when a new `audio_stream_start` is accepted.
- **Merged duplicates**: INT-F5-7. Found independently by Flows 1 and 5 (Flow 5 rated the reconnect-only half MEDIUM). Combined scope: every live enhancement toggle / preset / intensity re-issue and every WS reconnect during playback. Root cause shared with INT-F8-1: the client reports the *playhead* as `start_position` while keeping a buffer that runs ahead of it, and the `is_seek` resume guard neither trims nor resets.

#### INT-F2-1: Library search only filters already-loaded pages; the backend `search` param is never used by any mounted UI
- **Severity**: HIGH
- **Flow**: 2 - Library Browsing
- **Boundary**: Frontend (top-bar search) -> Backend list endpoints
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:81` -> `auralis-web/backend/routers/tracks.py:get_tracks (search param)`, `albums.py:get_albums`, `artists.py:get_artists`
- **Status**: NEW
- **Description**: The top-bar search box (`ComfortableApp.tsx:48/185`) is passed to `CozyLibraryView` as `searchQuery`, which does a client-side `.filter()` over the `tracks` array held by `useLibraryPagination` (first 50 rows plus whichever pages the user has scrolled). The backend implements `search=` (title/artist/album ILIKE with correct `total`) on `/api/library/tracks`, `/api/albums` and `/api/artists`, but the only code that calls it with `search=` is `useSearchLogic` -> `GlobalSearch`, which is mounted nowhere (`grep GlobalSearch` finds only its own directory). For the albums and artists views the query is not even forwarded: `CozyLibraryView` hands `LibraryViewRouter` no `searchQuery`, `useInfiniteAlbums({limit: 50})` and `useArtistsQuery({limit: 50})` pass no `search`.
- **Evidence**:
  - `CozyLibraryView.tsx:81-90`: `const filteredTracks = useMemo(() => { ... return tracks.filter(track => track.title.toLowerCase().includes(searchQuery.toLowerCase()) || track.artist... || (track.album ?? '')...` where `tracks` is the paginated page buffer from `useLibraryWithStats({ view, includeStats: false })` (`:69-77`).
  - `CozyLibraryView.tsx:174` `<LibraryViewRouter view=... />` (no `searchQuery`), `CozyAlbumGrid.tsx:66` `useInfiniteAlbums({ limit: 50 })`, `CozyArtistList.tsx` `useArtistsQuery({ limit: 50 })`.
  - Backend: `tracks.py:get_tracks` `repos.tracks.search, search, limit=limit, offset=offset` exists and is unused by this path.
- **Impact**: In a 100k-track library, typing an artist or title that is not in the first loaded pages shows the "no results" empty state (and `SearchResultsAnnouncement` announces zero results) even though the library contains matches. Albums and artists views ignore the search box entirely. Select-all (`useTrackSelection(filteredTracks)`) similarly acts on the loaded subset while `totalTracks` is shown.
- **Suggested Fix**: Frontend: when `searchQuery` is non-empty, drive `useLibraryPagination` (and `useInfiniteAlbums`/`useArtistsQuery`) with `search=` (debounced) so the backend filters and paginates; keep client filtering only as an instant-feedback overlay. Wire `searchQuery` through `LibraryViewRouter` for albums/artists.

#### INT-F3-1: Turning "Auto-enhance playback" off in Settings mid-playback stops the stream and nothing re-issues it
- **Severity**: HIGH
- **Flow**: 3, Audio Enhancement
- **Boundary**: Frontend (Settings dialog, `PUT /api/settings`) → Backend (runtime dict, stream loop) → Frontend (stream handlers)
- **Location**: `auralis-web/frontend/src/components/settings/EnhancementSettingsPanel.tsx:56` → `auralis-web/backend/routers/settings.py:151` / `routers/settings_sync.py:33-62` → `auralis-web/backend/core/stream_enhanced_chunks.py:126-133` → `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:205,225`
- **Status**: NEW
- **Description**: Two UI surfaces write the same runtime `enabled` flag. The Enhancement toggle (`useEnhancementCommands.toggleEnabled`) POSTs and then re-issues the active stream as `play_normal`. The Settings switch `auto_enhance` goes through `PUT /api/settings`, and `_sync_enhancement_settings` re-seeds `enabled=bool(auto_enhance)` and broadcasts. The only frontend consumer of that broadcast (`useEnhancementStatusSync.ts:57-65`) updates local state and never calls `reissueActiveStreamAs`. The running `play_enhanced` loop re-reads the live flag at the top of each chunk, sees `enabled=False`, and exits with `stopped_early`. The client treats `reason:'stopped'` as "superseded by a newer command" and neither marks the stream ended nor records anything.
- **Evidence**:
  - `settings_sync.py:47-48`: `live_settings = deps.get_enhancement_settings(); seed_enhancement_settings(live_settings, settings)`. `helpers.py:131`: `enhancement_settings['enabled'] = bool(getattr(user_settings,'auto_enhance',True))`.
  - `stream_enhanced_chunks.py:126-132`: `if controller._get_enhancement_enabled and not controller._get_enhancement_enabled(): ... stopped_early = True; break`.
  - `useStreamMessageHandlers.ts:225-226`: `// 'stopped': whatever stopped it supersedes it — a new play command, or the play_normal re-issue that disabling enhancement sends — so nothing to record.` For Settings-originated changes no such re-issue exists.
  - `useEnhancementStatusSync.ts:59-65` only calls `setState`. The only callers of `reissueActiveStreamAs` are `useEnhancementCommands.ts` and `useStreamMessageHandlers.ts:257` (error recovery).
- **Impact**: With enhanced playback running, the user opens Settings, switches off "Auto-enhance playback" and saves. The backend sends no further chunks after the one in flight. The client plays out whatever it has buffered, then goes silent. `markStreamEnded` is never called and the Redux stream state stays `streaming`, so the UI looks live. Play/pause only toggles pause/resume of the dead stream. Playback recovers only when the user seeks (`handle_seek` re-reads `enabled=False` and starts a normal stream) or picks another track.
- **Suggested Fix**: Make the frontend react to `enhancement_settings_changed` the same way the REST commands do. In `useEnhancementStatusSync`, or a session-level subscriber that owns `reissueActiveStreamAs`, re-issue `play_normal` or `play_enhanced` when the broadcast changes `enabled` while a stream is active. The alternative is to send the re-issue from the Settings save handler (`useSettingsDialog.handleSave`) when `auto_enhance` is in `pendingChanges`. Server-side, the loop could also send a typed end reason such as `enhancement_disabled` so the client does not wait on a stalled buffer.

#### INT-F4-1: Library "Scan Folder" imports tracks that the streaming path then refuses to play (allowed-directory registration missing on manual scan)
- **Severity**: HIGH
- **Flow**: 4 — Library Scanning (→ playback)
- **Boundary**: Frontend (`useLibraryScan`) → Backend scan route → Backend streaming (`validate_file_path`)
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryScan.ts:98` → `auralis-web/backend/routers/library_scan.py:100-231` (no registration) → `auralis-web/backend/core/stream_track_resolution.py:67-84`
- **Status**: NEW
- **Description**: `POST /api/library/scan` accepts any readable directory outside OS roots (`validate_user_chosen_directory`, `security/path_security.py:305-358`) but, unlike `POST /api/settings/scan-folders` (`routers/settings.py:175` `register_allowed_directory(validated)`) and startup (`config/startup/components.py:90-95`, seeded only from the persisted `scan_folders`), never calls `register_allowed_directory` and never persists the folder to `scan_folders`. The default allowlist is only `~/Music`, `~/Documents` (+`XDG_MUSIC_DIR`) (`path_security.py:40-44, 167-192`). Every track outside those roots is inserted into the library, listed, and clickable, but `resolve_and_validate_track` runs `validate_file_path` before any WebSocket stream and answers with `audio_stream_error: "Audio file not found"`. The same tracks 400 on metadata/lyrics/enhancement routes. After a backend restart nothing re-registers the folder either.
- **Evidence**:
  - frontend: `useLibraryScan.ts:98-102` `post<ScanSummary>('/api/library/scan', { directories: [folderPath] }, …)` with `folderPath` from Electron `selectFolder()` (arbitrary location) — the folder is never sent to `/api/settings/scan-folders`.
  - backend: `library_scan.py` contains no `register_allowed_directory` (only `routers/settings.py:29,138,175`, `config/startup/components.py:90` call it).
  - streaming: `stream_track_resolution.py:67-84` → `validate_file_path(str(track.filepath), …)` raises `PathValidationError("Path is outside allowed directories")` (`path_security.py:277-289`) → `_send_error(..., "Audio file not found")`; `stream_normal.py:108`, `stream_enhanced.py:139`, `stream_seek.py:131` all go through it.
  - The `validate_file_path` docstring (`path_security.py:224-235`) claims scanned-outside-allowlist tracks "must play" because the *player load path* skips validation, but the audio actually reaches the client through these WS stream handlers, which do validate.
- **Impact**: A user who picks e.g. `/mnt/data/music`, `~/Downloads/albums` or an external drive via the Library view's Scan Folder gets "Scan complete! Added N tracks", sees the tracks, and every play attempt fails with "Audio file not found". Works only for folders already under `~/Music`/`~/Documents` or previously added in Settings, so it passes casual testing. Same failure for symlink-escaped tracks that #4823 accepted.
- **Suggested Fix**: In `scan_library`, after validation (and before scanning) call `register_allowed_directory` for each resolved directory — or, better, have the Library "Scan Folder" flow add the folder to `scan_folders` through the settings endpoint (which registers, persists and wakes the auto-scanner) so startup re-seeds it. Keep one registration code path rather than copying the call.

#### INT-F5-1: Backend flow control is never resumed: `buffer_ready` is only evaluated when another chunk arrives, and `buffer_full` stops the chunks
- **Severity**: HIGH
- **Flow**: 5 - WebSocket Lifecycle (binary stream backpressure)
- **Boundary**: Frontend (flow-control sender) -> Backend (`stream_gates.wait_for_stream_gates`)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:144-150` / `audioChunkIngest.ts:95-101,171` -> `auralis-web/backend/ws_handlers/playback_control.py:209-222`, `core/stream_gates.py:35-43`
- **Status**: NEW (related closed: #3336, #2744, #5657, #5514)
- **Description**: The client decides pause/resume only inside `ingestChunk`, i.e. when a binary frame is received. After `buffer_full` the server blocks on `flow_evt.wait()` before the next chunk, so no further frame arrives to trigger `nextFlowControlSignal(fill, paused=true) -> 'resume'`. `buffer_ready` is sent from exactly one site, there is no timer, drain callback or `onUnderrun` consumer (`grep buffer_ready` over `src/` non-test = 1 hit), and the backend gate has no timeout. `handle_resume`/REST resume only set the *pause* event, never the flow event; only a new `play_*`/`seek` recreates the flow event.
- **Evidence**:
  - `useStreamMessageHandlers.ts:144-150`: `if (result.flowControl === 'pause') { flowPausedRef.current = true; wsContext.send({ type: 'buffer_full' ...` / `else if (result.flowControl === 'resume') { ... send({ type: 'buffer_ready' ...`; `result` comes only from `ingestChunk` (`audioChunkIngest.ts:171`).
  - `audioChunkIngest.ts:99-100`: `if (fill > 75 && !paused) return 'pause'; if (fill < 50 && paused) return 'resume';`
  - `core/stream_gates.py:41-43`: `flow_evt = stream_flow_events.get(key); if flow_evt is not None: await flow_evt.wait()` (no timeout), called once per chunk at `stream_enhanced_chunks.py:136` / `stream_normal_chunks.py:110`.
  - Capacity: `pcmRingOps.ts:capacityForStream` = `min(100 MB, 1.5 x stream bytes)`; the 75 % mark is reached only for streams whose unread backlog exceeds ~223 s at 44.1 kHz stereo float32 (tracks > ~4-7 min depending on server speed vs the 1.86x feeder, #5657).
- **Impact**: For long tracks (and any fast-delivery normal-path stream) the client sends `buffer_full` once, the server parks, and the remainder of the track is never delivered; playback runs out of buffered audio and stalls (only the local `playbackStalled` flag, #5461) until the user seeks or starts another track. Truncated playback with no error frame. Static analysis only (not run); the drain path to a resume signal does not exist in the source.
- **Suggested Fix**: Frontend: evaluate resume off the playback side (BufferScheduler feed tick / `onStallChange` / a 250 ms interval while `flowPausedRef.current`), sending `buffer_ready` when `getFillPercentage() < FLOW_RESUME_FILL_PCT`. Backend defence in depth: bound `flow_evt.wait()` (e.g. 30 s) and log + resume, so a lost `buffer_ready` cannot park a stream forever.

#### INT-F8-1: Seek-resume guard never applies `seek_position` to the playback clock - position restarts at 0 after every seek (regression of #2259)
- **Severity**: HIGH
- **Flow**: 8 - Seek & Rebuffer
- **Boundary**: Backend (`audio_stream_start.seek_position`) -> Frontend (playback engine position tracker)
- **Location**: `auralis-web/backend/core/stream_messages.py:110-118` (sends `is_seek`/`seek_position`) -> `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:94-106` (guard returns early) vs `:170-172` (only place `setSeekOffset` is called)
- **Status**: Regression of #2259 (fix only survives on the non-guard path; the guard added for #3185/#3187 bypasses it)
- **Description**: `seekTo()` calls `engine.stopPlayback()`, which runs `PlaybackPositionTracker.reset()` (zeroes `seekOffsetSeconds`, `samplesPlayed`, `pausedTime`) but keeps the engine and buffer alive. The backend then answers with `audio_stream_start {is_seek:true, seek_position:S}`. Because the engine and buffer still exist, `handleStreamStart` takes the "resume into existing buffer" early return and never reaches `engine.setSeekOffset(seekPosition)`. `startPlayback()` then zeroes `samplesPlayed`, so `getCurrentPlaybackTime()` = `0 + samplesPlayed/sr` = time elapsed since the seek, not the track position. The guard branch is hit for every within-track seek (engine/buffer are only absent after a full cleanup), so the correct-position path is effectively dead for seeks. While a seek is held paused the tracker state is `stopped`, which returns 0 as well.
- **Evidence**:
  - `useEnhancedStreamStart.ts:94`: `if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) { ... return; }` - no `setSeekOffset`.
  - `useEnhancedStreamStart.ts:170-172`: `if (isSeek && seekPosition > 0) { engine.setSeekOffset(seekPosition); }` is after the early return, in the engine-rebuild branch only.
  - `useEnhancedSeek.ts:68`: `core.playbackEngineRef.current?.stopPlayback();` -> `AudioPlaybackEngine.ts:206 this.positionTracker.reset()` -> `PlaybackPositionTracker.ts:73 this.seekOffsetSeconds = 0`.
  - `PlaybackPositionTracker.ts:89`: `return this.seekOffsetSeconds + this.samplesPlayed / sampleRate;`; `AudioPlaybackEngine.ts:148 this.positionTracker.setSamplesPlayed(0)`.
  - No test covers the guard + offset combination (`usePlayEnhanced.test.ts` seek tests only assert `startPlayback` calls).
- **Impact**: After any seek to S the time display and progress bar restart from ~0:00 and count up while the audio is at S+t. Knock-on effects, all driven by `engine.getCurrentPlaybackTime()`:
  1. Auto-advance never fires after a seek: `usePlaybackSessionHooks.ts:120` requires `currentTime >= trackDuration - 0.5`, but the clock only reaches `duration - S` at the real end, so the queue stops at the end of any track that was scrubbed (`PlaybackSessionContext.playbackEnded` is wrong the same way).
  2. Keyboard seek (`progressBarMath.ts:52`, `currentTime + KEYBOARD_STEP_SECONDS`) steps from the wrong base: after seeking to 2:00 and 3 s of playback, ArrowRight seeks to ~0:08.
  3. Live enhancement toggle/preset/intensity changes (`useOutgoingChannel.reissueActiveStreamAs`) and WS reconnect resume (`websocketConnectionCore.ts:56`) call the resume getter (`usePlaybackTransport.ts:168`), so they restart the stream at the elapsed-since-seek value instead of the real position.
- **Suggested Fix**: Make the position clock authoritative on seek, not on the engine rebuild. In the seek path (not the reconnect-resume path, where the engine keeps playing and `samplesPlayed` continues) call `engine.setSeekOffset(seek_position)` after `stopPlayback()` and before the next `startPlayback()` (e.g. record the pending offset in `seekTo` from the ack/`audio_stream_start`, or have `stopPlayback()` preserve a caller-supplied offset). Also make `getCurrentPlaybackTime()` return the held offset rather than 0 while a seek is pending/paused. Add a test: seek -> `audio_stream_start{is_seek,seek_position:60}` -> `getCurrentPlaybackTime()` starts at 60.
- **Merged duplicates**: INT-F1-2, INT-F5-2. Found independently by Flows 1, 5 and 8. Flow 5 adds the reconnect half: `resumeGetters[type]()` (`websocketConnectionCore.ts`) returns seconds-since-seek, so a WS reconnect after a seek resumes near the start of the track. Flow 1 adds that `useAutoAdvance`/`PlaybackSessionContext.playbackEnded` never fire after a seek, so the queue stops at the end of any scrubbed track. Orchestrator re-verified: `useEnhancedStreamStart.ts:94` early-returns before the only `setSeekOffset` call (`:170-172`), and `stopPlayback()` -> `PlaybackPositionTracker.reset()` zeroes the offset.

### MEDIUM (33)

#### INT-F1-4: Backend skips a failed chunk and keeps streaming, but the frontend treats every `audio_stream_error` as terminal and tears playback down
- **Severity**: MEDIUM
- **Flow**: 1 - Track Playback (error propagation)
- **Boundary**: Backend `pump_chunks` / `pump_normal_chunks` error recovery -> Frontend `handleStreamError` / `handleChunk`
- **Location**: `auralis-web/backend/core/stream_enhanced_chunks.py:246-271`, `core/stream_normal_chunks.py` (`failed_chunks.append(chunk_idx)` + `continue`) -> `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:229-262,108-116`
- **Status**: NEW
- **Description**: After a per-chunk processing exception the backend sends `audio_stream_error{recovery_position}` and deliberately continues with chunk N+1 (#3190), ending with `audio_stream_end{reason:'errored'}`. The frontend's `handleStreamError` immediately calls `cleanupStreaming()` (disposes buffer and engine, nulls metadata and epoch) and then auto-resumes at most once per `(track, recovery_position)` (#4655). The backend's subsequent chunks hit `handleChunk` with no buffer, are classified `not-initialized` and appended to `pendingChunksRef` with no cap. Because the auto-resume restarts at the failed chunk, a deterministically failing chunk (corrupt region, DSP error) fails again with the same `recovery_position`, `alreadyAttempted` blocks a second resume, and the remaining chunks keep accumulating.
- **Evidence**:
  - `stream_enhanced_chunks.py:267-271`: "Skip failed chunk and continue with remaining chunks (#3190) ... `failed_chunks.append(chunk_idx)` / `continue`".
  - `useStreamMessageHandlers.ts:238`: `cleanupStreaming();` unconditional on any `audio_stream_error`; `:246-250` `alreadyAttempted` guard.
  - `useStreamMessageHandlers.ts:108-116`: `if (rejection === 'not-initialized') { pendingChunksRef.current.push(message); return; }` - unbounded; the queue is only emptied by a later `audio_stream_start` drain (which drops old-epoch frames) or by the next play.
- **Impact**: One bad chunk ends audible playback at that point even though the backend is designed to skip it and continue; the rest of the track is rendered on the server (DSP + sends) and its PCM piles up in browser memory (up to the whole remainder of the track, tens to hundreds of MB) until the next play. The two sides disagree on whether a chunk error is terminal.
- **Suggested Fix**: Pick one contract. Preferred: the frontend treats `audio_stream_error` carrying `recovery_position` as non-terminal for the engine (keep buffer/engine, mark a gap, keep appending later chunks) and only tears down on errors without a recovery position or on `audio_stream_end{reason:'errored'}` with nothing buffered. Otherwise the backend should stop the stream after the first chunk error. In either case cap or discard `pendingChunksRef` when no stream is expected.

#### INT-F2-2: Album sort modes (Year / Era / A-Z) re-sort only the loaded subset; backend can only sort ascending and the frontend never sends `order_by`
- **Severity**: MEDIUM
- **Flow**: 2 - Library Browsing
- **Boundary**: Frontend album grid -> `GET /api/albums`
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:79-93` and `hooks/library/useInfiniteAlbums.ts:33-45` -> `auralis/library/repositories/album_repository.py:130`, `routers/albums.py:get_albums`
- **Status**: NEW
- **Description**: `LibraryViewRouter` lets the user pick `az | year | era` (`LibraryViewRouter.tsx:121,165`). The server always returns albums in `title ASC` pages of 50 because `fetchAlbums` sends only `offset`, `limit`, `search`. The grid then sorts/groups whatever pages are loaded in the browser. The backend contract offers no way to do the requested orders server-side: `order_by` accepts `title|year|created_at` but the repository always applies `.asc()` (no direction parameter), so "newest first" is impossible and `year ASC` puts NULL years first in SQLite.
- **Evidence**: `useInfiniteAlbums.ts:33-35` `new URLSearchParams({ offset: ..., limit: ... })` then only `search` appended; `CozyAlbumGrid.tsx:90` `sorted.sort((a, b) => (b.year || 0) - (a.year || 0));`; `album_repository.py:130` `.order_by(order_column.asc())`.
- **Impact**: With 5,000 albums, "Year (newest first)" shows the newest of the first 50 alphabetical albums; each further scroll page injects albums into the middle of the already-sorted grid (items jump, virtualised scroll offset shifts, era groups grow retroactively). The user never sees a true newest-first list unless every page is loaded.
- **Suggested Fix**: Add a direction (`order=asc|desc`, or `-year`) to the albums/tracks/artists list endpoints with an `id` tie-breaker, and make `useInfiniteAlbums` take `orderBy` and include it in the query key; drop client-side re-sorting of partial pages (keep era grouping client-side only over a server-ordered stream).

#### INT-F2-3: Server ordering for albums/artists/track titles is case-sensitive BINARY while the UI presents A-Z sections
- **Severity**: MEDIUM
- **Flow**: 2 - Library Browsing
- **Boundary**: Backend repositories -> Frontend grouping (`useGroupedArtists`, album grid)
- **Location**: `auralis/library/repositories/artist_repository.py:165` and `album_repository.py:130,210`, `track_repository_search.py:get_all/get_favorites` -> `frontend/src/hooks/shared/useGroupedArtists.ts:33-45`
- **Status**: NEW
- **Description**: `Artist.name`, `Album.title`, `Track.title` are plain `String` columns ordered with default SQLite BINARY collation (`Artist.name.asc()`, `Album.title` via `order_column.asc()`). The only NOCASE indexes (`idx_tracks_title`, `idx_albums_title`) are never used by these ORDER BYs. All uppercase-initial names therefore precede every lowercase-initial name (`deadmau5`, `k-os`, `alt-J`, `mewithoutYou`), and non-ASCII initials (`Ólafur Arnalds`, `Édith Piaf`) sort after `z`. `useGroupedArtists` buckets by `charAt(0).toUpperCase()` as pages stream in, so the "A" section is completed only when the late lowercase page arrives (potentially hundreds of rows later), and within a section the order is not alphabetical (`Abba ... Aztec, alt-J, apparat`).
- **Evidence**: `artist_repository.py:165` `order_column = Artist.name.asc()`; `artist_repository.py:215` `.order_by(Artist.name)`; `useGroupedArtists.ts:35` `const initial = artist.name.charAt(0).toUpperCase();`; no `collate(...)` on the ORDER BY expressions.
- **Impact**: Incorrect browse order and sections that mutate while scrolling; infinite scroll appears to "insert" artists into earlier letters. Library-size independent, grows worse with larger libraries.
- **Suggested Fix**: Backend: order by `collate(Artist.name, 'NOCASE')` (matching the existing NOCASE indexes so it is also index-backed) plus `id` tie-breaker; same for albums and track titles. Frontend: keep grouping but rely on server order.

#### INT-F2-4: A failed page-2+ fetch replaces the whole loaded albums/artists list with an error state (no retry)
- **Severity**: MEDIUM
- **Flow**: 2 - Library Browsing
- **Boundary**: Backend (503/500 on a later page) -> Frontend list state
- **Location**: `hooks/library/useLibraryQuery.ts:223` (fetchMore `setError`) -> `components/library/Items/artists/CozyArtistList.tsx:95`; `useInfiniteAlbums.ts:81` -> `components/library/Items/albums/CozyAlbumGrid.tsx:107`
- **Status**: NEW
- **Description**: For artists, `fetchMore` stores a page failure in the same `error` state used for the initial load, and the component renders the empty/error view whenever `error` is truthy even though `artists` holds hundreds of loaded rows. For albums, TanStack's `useInfiniteQuery` keeps `data` but sets `error` when `fetchNextPage` fails (after `shouldRetryQuery` retries), and `CozyAlbumGrid` returns `EmptyState "Error Loading Albums"` on `if (error)`. Neither error view has a retry action. `handle_query_error` deliberately maps transient SQLite locks to 503 (e.g. during a scan), so this is a realistic trigger. Related: `CozyArtistList.tsx:104` passes `isLoadingMore={isLoading && artists.length > 0}` but `fetchMore` toggles `isLoadingMore`, not `isLoading`, so the "loading more" indicator never shows.
- **Evidence**: `CozyArtistList.tsx:95` `if (error || artists.length === 0) { return emptyState; }`; `CozyAlbumGrid.tsx:107` `if (error) { return (<EmptyState title="Error Loading Albums" ...`; `useLibraryQuery.ts:221-224` `if (result.kind === 'error') { setError(result.error); return; }` in `fetchMore`.
- **Impact**: One transient failure while scrolling a large library throws away the user's position and loaded pages, and the only recovery is navigating away and back. By contrast the tracks list handles this correctly (`useLibraryPagination.loadMore` keeps tracks, sets `hasMore=false`).
- **Suggested Fix**: Render the error only when there is no data (`error && items.length === 0`); otherwise show an inline "Failed to load more - Retry" row that calls `fetchMore`/`fetchNextPage`. Use `isLoadingMore` from the hook for the indicator.

#### INT-F2-5: Albums grid (and a mounted artists list) is never refreshed on `library_updated` / metadata changes; TanStack cache is fresh for 5 minutes
- **Severity**: MEDIUM
- **Flow**: 2 - Library Browsing
- **Boundary**: Backend WS broadcast (`library_updated`) -> Frontend cache
- **Location**: `auralis-web/backend/routers/library_scan_events.py:176` -> `frontend/src/hooks/library/useLibraryWithStats.ts:76-84`, `App.tsx:18-24`, `hooks/library/useInfiniteAlbums.ts`
- **Status**: NEW
- **Description**: `library_updated` is subscribed in exactly one place, `useLibraryWithStats`, which only calls `refreshTracks()` and `refetchStats()`. `useInfiniteAlbums` uses key `['albums', {search, limit}]` under a global `staleTime` of 5 minutes (`QUERY_STALE_TIME_MS`), and nothing calls `invalidateQueries(['albums'])` (the only `invalidateQueries` in the app targets `['cache']`). Metadata edits (`useMetadataEditing(refreshTracks)`) and bulk actions likewise refresh only the track list. `useArtistsQuery` is hook-local state that is not refetched on `library_updated` while mounted.
- **Evidence**: `useLibraryWithStats.ts:84` `useWebSocketMessages(['library_updated'], handleLibraryUpdated);` with `handleLibraryUpdated` = `refreshTracks(); if (includeStats) refetchStats();`; `App.tsx:21` `staleTime: QUERY_STALE_TIME_MS` (`config/timing.ts:12` = 5 min); grep of `invalidateQueries|removeQueries|resetQueries` shows only `['cache']`.
- **Impact**: After a scan started from Settings (or the auto-scanner finishing, `library_auto_scanner.py:250`), switching to or staying on Albums shows the pre-scan album set for up to 5 minutes: new albums missing, removed albums still clickable (404 on `/api/albums/{id}/tracks`). Edited titles/years show the old values in the grid.
- **Suggested Fix**: In the `library_updated` / `metadata_updated` handlers also `queryClient.invalidateQueries({queryKey: ['albums']})` (and refetch the artists query); or subscribe in `useInfiniteAlbums` itself.

#### INT-F2-6: Artist detail and artist-tracks endpoints hydrate every Track row of the artist (with `lyrics`, `fingerprint_vector`) plus every album's tracks, just to count or list ids
- **Severity**: MEDIUM
- **Flow**: 2 - Library Browsing
- **Boundary**: Backend router -> Library repository (and unbounded response to frontend)
- **Location**: `routers/artists.py:159,188,203-215` -> `auralis/library/repositories/artist_repository.py:73-77,101-110`
- **Status**: NEW (sibling of closed #5084, which fixed only the list endpoint)
- **Description**: `ArtistRepository.get_by_id` uses `_ARTIST_DETAIL_OPTIONS` = `selectinload(Artist.tracks)` + `Track.genres` + `Track.album` + `selectinload(Artist.albums).selectinload(Album.tracks)`. `GET /api/artists/{id}` needs only album aggregates and one track count; `GET /api/artists/{id}/tracks` needs ids/titles/album title. Both pay for full ORM Track rows (all columns, including the unbounded `lyrics`/`comments` and `fingerprint_vector` Text columns) for every track by the artist, and the album chain loads each album's full tracks again. The tracks endpoint has no pagination and the artist "Play All"/"Add to queue" actions call it for the whole artist. "Various Artists"/compilation artists in a 100k-track library routinely own tens of thousands of tracks.
- **Evidence**: `artist_repository.py:73-77` `_ARTIST_DETAIL_OPTIONS = (selectinload(Artist.tracks).selectinload(Track.genres), selectinload(Artist.tracks).selectinload(Track.album), selectinload(Artist.albums).selectinload(Album.tracks),)`; `artists.py:188` `total_tracks=len(artist.tracks) if artist.tracks else 0`; the album loop at `artists.py:166-176` calls `serialize_album(album)` -> `Album.to_dict()` which walks `album.tracks` for count/duration.
- **Impact**: Opening an artist page or pressing Play All on a very large artist loads tens of thousands of ORM rows and their Text blobs into memory (hundreds of MB, seconds of latency on the shared worker thread pool) and returns an unbounded JSON array.
- **Suggested Fix**: Add dedicated repository reads: counts via correlated `with_expression` (as `_ARTIST_LIST_OPTIONS` does) and album aggregates via `track_count_expr`/`total_duration_expr`; for `/tracks` select only the needed columns (id/title/album title/track_no/disc/format) and paginate or stream ids.

#### INT-F2-7: Album grid fires one `/api/albums/{id}/fingerprint` per loaded album, each hydrating the full album detail
- **Severity**: MEDIUM
- **Flow**: 2 - Library Browsing
- **Boundary**: Frontend album grid -> Backend albums router -> repository
- **Location**: `frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:72-75` + `hooks/fingerprint/useAlbumFingerprint.ts:useAlbumFingerprints` -> `routers/albums_fingerprint.py:35`
- **Status**: NEW (not covered by closed #3644/#5611, which bounded concurrency and cache keying)
- **Description**: `useAlbumFingerprints(albumIds)` builds one `useQueries` entry per loaded album id (all loaded albums, not just visible ones). Each backend call does `repos.albums.get_by_id` with `_ALBUM_DETAIL_OPTIONS` (album + artist + all tracks + each track's genres/artists/album) only to collect `track.id`s, then a second query for fingerprints. There is no batch endpoint. Albums with no fingerprinted tracks answer 404 (expected during initial library fingerprinting), producing a failed request per tile.
- **Evidence**: `useAlbumFingerprint.ts` `queries: albumIds.map((albumId) => ({ queryKey: ['album-fingerprint', albumId], queryFn: ... withFingerprintSlot(() => fetchAlbumFingerprint(albumId, signal)) ... retry: false }))`; `albums_fingerprint.py:35` `album = await asyncio.to_thread(repos.albums.get_by_id, album_id)` then `track_ids = [track.id for track in tracks]`.
- **Impact**: Scrolling through a few thousand albums (a 100k-track library has ~8-10k) issues thousands of requests (10 at a time) that each hydrate a full album; backend CPU/IO competes with audio streaming; `useQueries` rebuilds a Map over every loaded id each render.
- **Suggested Fix**: Add `GET /api/albums/fingerprints?ids=` (or include a precomputed per-album summary in the list payload) that reads fingerprints by album via one SQL join; restrict the hook to visible rows; have `get_album_fingerprint` select track ids only.

#### INT-F3-2: The only intensity control (Settings dialog) never reaches the playing stream, and the next seek ignores it
- **Severity**: MEDIUM
- **Flow**: 3, Audio Enhancement
- **Boundary**: Frontend (Settings PUT) → Backend (`active_stream_settings` snapshot vs. global dict)
- **Location**: `auralis-web/frontend/src/components/settings/EnhancementSettingsPanel.tsx:72` → `auralis-web/backend/routers/settings_sync.py:47-48` → `auralis-web/backend/ws_handlers/playback_commands.py:283,419-424`
- **Status**: NEW (related closed: #3763 live changes, #5604 seek re-masters with play-time values)
- **Description**: #3763 and #5604 rest on one premise: the live-change reissue path in `useEnhancementControl` keeps the backend `active_stream_settings` snapshot current, so seek can safely omit preset and intensity (`useEnhancedSeek.ts:78-83` says so). That reissue path (`setIntensity`/`setPreset`) has no UI caller. The only intensity and default-preset controls live in the Settings dialog and go through `PUT /api/settings`, which updates the global dict and broadcasts but never touches `state.active_stream_settings`. `handle_seek` prefers the per-connection snapshot over the global dict.
- **Evidence**:
  - `playback_commands.py:283-287`: `state.active_stream_settings[ws_id] = {"preset": preset, "intensity": intensity, "enabled": ...}` is written only by `handle_play_enhanced`.
  - `playback_commands.py:419-424`: `stream_settings = state.active_stream_settings.get(ws_id) ... resolve_enhancement_params(data, stream_settings, global_settings)`. The snapshot wins and the global is only a fallback.
  - `useEnhancedSeek.ts:78-83`: "preset/intensity are deliberately OMITTED (#5604): the backend resolves them from this connection's active_stream_settings (#4742), which the live preset/intensity reissue path (useEnhancementControl) keeps current."
  - `grep -rn "setIntensity\|usePresetControl\|useIntensityControl" components/` has no hits outside the Settings panel, which uses `onSettingChange('enhancement_intensity', …)`.
- **Impact**: The user moves the intensity slider in Settings and saves while a track plays. The running stream, and any seek in that track, keep the old intensity (the snapshot). The new value applies only at the next `play_enhanced`, so the dialog and the UI state say 0.4 while the audio is mastered at 1.0. Chunks already in the disk cache are keyed by the old intensity and keep being served.
- **Suggested Fix**: After a successful `PUT /api/settings` that touches enhancement fields, have the frontend run the same reissue the REST commands use. Alternatively, have `_sync_enhancement_settings` update the `active_stream_settings` snapshots for all connections. A single "apply enhancement settings change" helper shared by both paths would remove the divergence.

#### INT-F3-3: `PUT /api/settings {"default_preset": null}` bypasses the preset Literal, persists NULL, and then bricks `GET /api/settings`
- **Severity**: MEDIUM
- **Flow**: 3, Audio Enhancement
- **Boundary**: Frontend / any local client → Backend settings router → DB → Backend response model
- **Location**: `auralis-web/backend/routers/settings_models.py:75` → `auralis/library/repositories/settings_repository.py:135` → `auralis-web/backend/routers/settings_models.py:127`
- **Status**: NEW (the null-tolerance part of #4424 and #5824 covered preset values, not an explicit null)
- **Description**: The request model types `default_preset: EnhancementPresetLiteral | None = None`. Because the handler uses `model_dump(exclude_unset=True)`, an explicit `null` stays in the payload. The repository does `setattr(settings, key, value)` for every whitelisted key, and the column is nullable (`default_preset: Mapped[str | None]`), so NULL is written. The response model is non-nullable since v23, with no null-degrade validator (unlike `enhancement_intensity`).
- **Evidence**:
  - `.venv/bin/python -I` check: `SettingsUpdateRequest.model_validate({'default_preset': None}).model_dump(exclude_unset=True)` gives `{'default_preset': None}`. `SettingsResponse.model_validate({'default_preset': None})` raises `Input should be 'adaptive' [type=literal_error, input_value=None]`.
  - `settings_repository.py:135`: `setattr(settings, key, value)`. `models/settings.py:50`: `default_preset: Mapped[str | None] = mapped_column(String, default='adaptive')`.
  - Routes: `response_model=SettingsUpdateResponse` (PUT) and `SettingsResponse` (GET) in `settings.py:262-266`. `to_dict()` returns the raw column (`models/settings.py:98`).
  - Same shape for `auto_enhance: null` and `enhancement_intensity: null`. Those columns are `Mapped[bool]` and `Mapped[float]`, so they fail with an IntegrityError and a 500 where a 422 is expected.
- **Impact**: One malformed request from any local client leaves NULL in `user_settings.default_preset`. The PUT already committed and then returns a 500 from response validation. Every later `GET /api/settings` also returns a 500, so the Settings dialog cannot load. Recovery needs `POST /api/settings/reset` or a manual DB edit. The runtime dict is unaffected, because the seed helper's `if stored_preset:` ignores NULL. The frontend never sends null, so this is an API-contract hole rather than a UI-reachable bug.
- **Suggested Fix**: Reject explicit nulls for non-nullable settings. In `SettingsUpdateRequest`, drop `| None` and rely on `exclude_unset`, or add a `field_validator(..., mode='before')` that rejects None for `default_preset`, `auto_enhance` and `enhancement_intensity`. Optionally add a `SettingsResponse` before-validator that maps a stored NULL `default_preset` to `DEFAULT_PRESET`, which is what the response default intended.

#### INT-F3-4: Enhancement toggle always re-issues a stream, and the "last stream command" is never cleared, so flipping the switch while idle or stopped starts playback
- **Severity**: MEDIUM
- **Flow**: 3, Audio Enhancement
- **Boundary**: Frontend (`useEnhancementCommands`) → WebSocket (`play_enhanced` / `play_normal`) → Backend streaming
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementCommands.ts:90-96` → `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:42-44,88-111`
- **Status**: NEW
- **Description**: `toggleEnabled` calls `reissueRef.current(...)` unconditionally after a successful POST. `reissueActiveStreamAs` only checks that `connState.lastStreamCommand` exists and has a `track_id`. That field is cleared only when a WS `stop` or `pause` is sent, or when the connection resets. The frontend never sends `stop` or `pause` over the WS: pause, stop and track-end are all client-side. `lastStreamCommand` therefore stays set for the rest of the session after the first play.
- **Evidence**:
  - `useEnhancementCommands.ts:90-96`: `if (newEnabled) { reissueRef.current('play_enhanced', {...}); } else { reissueRef.current('play_normal'); }`. There is no playing or streaming check, unlike `setPreset` and `setIntensity`, which at least check `enabledRef`.
  - `useOutgoingChannel.ts:88-92`: `const last = connState.lastStreamCommand; if (!last) return false; ... if (trackId == null) return false;`.
  - Only clear sites: `useOutgoingChannel.ts:44,53`, `websocketConnectionCore.ts:49`, and `websocketConnectionState.ts:131` (reset). A grep of `src` for `type: 'stop'` or `type: 'pause'` on a send finds none outside those handlers.
- **Impact**: After a track ends, after the user stops, or while paused (the stream is restarted but held by `pauseHoldRef`), flipping the Enhancement toggle sends a new `play_*` for the last track. The start position comes from the engine position getter: 0 after a stop, or near the end after completion. That starts audio the user did not ask for, or an out-of-range resume that ends or errors immediately.
- **Suggested Fix**: Gate the reissue on an active stream (streaming, buffering or playing; not idle, complete-and-ended or stopped). Also clear `lastStreamCommand` on client-side stop, on track end (`completed`) and on pause-with-no-stream, so a stale command cannot be replayed by either the toggle or the reconnect resume.
- **Merged duplicates**: INT-F5-10. Merged with Flow 5's INT-F5-10, same root cause: production code never sends WS `pause`/`resume`/`stop` (pause/stop are client-side only, `usePlaybackTransport.ts:76-96`), so the `lastStreamCommand` clearing branches (`useOutgoingChannel.ts:43-45,52-54`, #2385) never run and the three backend handlers in `ws_handlers/playback_control.py` are dead. Besides the toggle, a WS reconnect after a natural track end or stop re-issues the last `play_*` (`replayQueueAndResume`) and can restart a finished track; the backend also keeps streaming after a client-side stop until the next play/seek.

#### INT-F4-2: Directory-level and unexpected scan failures never reach the UI; an empty/failed scan is reported as a normal completion
- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning
- **Boundary**: Engine scanner → Backend emitters → Frontend (`useScanProgress`, `useLibraryScan`)
- **Location**: `auralis/library/scanner/file_discovery.py:54,82,84,137,139` and `scanner.py:240-243` → `routers/library_scan_events.py:broadcast_scan_complete` / `services/auto_scan_events.py:scan_complete_payload` → `useScanProgress.ts:129-141`
- **Status**: NEW (adjacent to open #5567 which covers *file*-level silent ingestion)
- **Description**: `files_failed`/`failures` only count per-file failures. Discovery swallows every directory-level problem with a log line: root missing/not a directory, `PermissionError` on the root or any subdirectory, `OSError` mid-walk (drive unplugged, NAS dropped). `scan_directories` additionally has a catch-all `except Exception: warning(...); return result` that returns a normal `ScanResult` (not `rejected`, no error flag). Both emitters then broadcast `scan_complete` with `files_failed:0` and the frontend renders it as a successful scan.
- **Evidence**:
  - `file_discovery.py:82-84` `except PermissionError: warning(...)` / `except Exception as e: error(...)` — nothing recorded on the result; `_walk_directory:137-139` same for subdirectories.
  - `scanner.py:240-243` `except Exception as e: warning(f"Library scan failed: {e}"); result.scan_time = …; return result`.
  - `scan_stages.py:111-112` `directories_counted += 1` after the walk even when it yielded nothing, so `directories_scanned` also lies.
  - auto-scan never re-validates its folders (`library_auto_scanner.py:_parse_scan_folders` → `_do_scan`): a configured folder on a disconnected drive produces `scan_complete{files_processed:0, files_added:0, files_failed:0}`; frontend shows "+0 added (0.1s)" (`ScanStatusCard.tsx:130-165`) and the manual toast says "Scan complete! Added 0 tracks" (`useLibraryScan.ts:112-121`).
  - Manual route validates the root only at request time (`validate_user_chosen_directory`), so unreadable *subfolders* and mid-scan disappearance still slip through.
- **Impact**: A partially-readable library (permission-denied album folders, flaky network share) imports a subset and tells the user the scan succeeded. A scanner-internal exception is indistinguishable from "nothing new". Users cannot tell why tracks are missing.
- **Suggested Fix**: Record directory-level errors on `ScanResult` (e.g. `result.record_failure(dirpath, reason)` or a separate `errors` list surfaced in `failures`), set a `failed`/`error` field when the catch-all fires, and have both emitters send `library_scan_error` (or include the error in `scan_complete`) when set. Revalidate auto-scan folders per cycle.

#### INT-F4-3: Concurrent scans (default `max_concurrent_scans=4`) share one un-keyed frame stream; UI state flip-flops and the setting is mislabeled
- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning
- **Boundary**: Backend (ScanCoordinator, two emitters) → Frontend (`useScanProgress`)
- **Location**: `auralis/library/models/settings.py:59` (default 4), `scan_coordinator.py:58-70`, `scan_stages.py:claim_scan` → `useScanProgress.ts:101-160`
- **Status**: NEW
- **Description**: The slot count defaults to 4, so a manual scan of folder A and the auto-scan of the configured folders (or a Library "Scan Folder" + Settings "Scan Now") run truly concurrently when their directory strings differ (reservation compares exact normalized strings only, `try_reserve_scan_paths`; a child dir of an actively scanned parent is not detected). Every frame (`library_scan_started`, `scan_progress`, `scan_complete`, `library_scan_error`) lacks a scan identifier, and the frontend keeps a single state object. The Settings control describes the value as "Number of parallel threads for library scanning", whereas it is the number of simultaneous scans (each single-threaded).
- **Evidence**:
  - `useScanProgress.ts:105-110` `library_scan_started` resets `...INITIAL_STATE` (wipes the other scan's progress); `:111-121` progress frames overwrite `current/total/percentage` from whichever scan sent last; `:122-141` the first `scan_complete` sets `isScanning:false` + `lastResult` while the other scan is still running — its next `scan_progress` flips `isScanning:true` again (`:113-115`).
  - `scan_complete` also arrives after `prune_missing_tracks` (`library_scan.py:175-177`), but the scan slot was already released in `scanner.py:248-250`, so a new scan can start and send `library_scan_started` before the previous request's `scan_complete`, which then clears `isScanning` for the new scan.
  - `AdvancedSettingsPanel.tsx:142` `description="Number of parallel threads for library scanning"`.
  - overlapping dirs: both scans call `tracks_repo.add` for the same files; `add()` returns the *existing* row on a race (`track_repository_lifecycle.py:~129-135`) and `batch_processor.py:157-159` counts it as `'added'`, so counts and fingerprint-enqueue are inflated.
- **Impact**: Progress bar jumps between two scans' counters, "Scanning…" disappears and reappears, "Scan Now" shows while a scan runs, last-result card shows whichever finished first. No data corruption (unique `filepath_key` holds).
- **Suggested Fix**: Add a `scan_id` to all lifecycle frames and key the frontend store by it (or aggregate), and/or default `max_concurrent_scans` to 1 and relabel the setting; make path reservation containment-aware (parent/child). Treat the existing-row return from `add()` as `skipped`.

#### INT-F4-4: `library_scan_error.error` is discarded by the frontend, so auto-scan failures are invisible
- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning
- **Boundary**: Backend (`broadcast_scan_error`, auto-scanner `_run`/`_do_scan`) → Frontend (`useScanProgress`)
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:131-142,206-214`, `routers/library_scan_events.py:broadcast_scan_error` → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:143-148`
- **Status**: NEW
- **Description**: The only consumer of `library_scan_error` resets the store to idle and keeps `lastResult`; the `error` string (`"<ExcName> during library scan"`, `"library scan timed out…"`, `"library scan cancelled"`) is never read, stored or shown. The REST caller of a manual scan sees a toast from the HTTP error, but an auto-scan cycle crash (which repeats every 30 s, `library_auto_scanner.py:141`) or a scan started elsewhere produces only a silent flip from "Scanning…" back to the previous result / "No scans yet".
- **Evidence**: `useScanProgress.ts:143-148` `else if (raw.type === 'library_scan_error') { setSharedState((prev) => ({ ...INITIAL_STATE, lastResult: prev.lastResult })); }`; `types/ws/library.ts:166-171` declares `data:{error:string}`; no other subscriber (`grep library_scan_error` in `src/` non-tests → only this file and type registry).
- **Impact**: User enabling auto-scan on a broken folder sees nothing happen; repeated failures every 30 s are never surfaced.
- **Suggested Fix**: Add `lastError: string | null` to `ScanStatus`, set it on `library_scan_error`, clear on `library_scan_started`, and render it in `ScanStatusCard` (and/or toast).

#### INT-F4-5: Moved/renamed files are re-imported as new rows while the old row is pruned, destroying playlist membership, favorites and play counts
- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning (rescan dedupe)
- **Boundary**: Engine scanner/repository → Library data → Frontend library view
- **Location**: `auralis/library/scanner/batch_processor.py:114-157` + `auralis-web/backend/services/missing_tracks.py:34-48` → `auralis/library/repositories/track_deletion.py:34-70`
- **Status**: NEW (the move-detection half was deliberately left out of closed #5458; `file_hash` is computed but unused — open #5755 covers the dead data, not this consequence)
- **Description**: Rescan identity is `filepath_key` only. After a user reorganises/renames files, the scan inserts the new paths as fresh tracks (new id, no history) and the post-scan `prune_missing_tracks` (now run after every manual and auto scan) deletes the old rows, removing their `track_playlist` rows, favorite flag, play counts and fingerprint. Before #5458 added pruning the user had duplicates; now they silently lose data.
- **Evidence**: `batch_processor.py:114` `existing_track = tracks_repo.get_by_path(file_path) if skip_existing else None`; `audio_analyzer.py` computes `file_hash` but `Track` never matches on it; `library_scan.py:175` / `library_auto_scanner.py` call `prune_missing_tracks` → `cleanup_missing_files` → `delete_tracks_by_ids` which deletes association rows (`track_deletion.py:56-57`). Frontend gets only `library_tracks_removed{count}` — no hint that user data went with it.
- **Impact**: Reorganising a library (very common) and rescanning wipes playlists/favorites for every moved file.
- **Suggested Fix**: Before pruning, match missing rows to newly-added rows by (file_hash + size/duration) and update `filepath` in place (carrying fingerprint, playlists, favorites); only prune the unmatched remainder.

#### INT-F4-6: Auto-scanner discards watchdog/settings wake-ups that arrive while a scan is running
- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning (auto-scan)
- **Boundary**: Backend settings router / watchdog → LibraryAutoScanner loop
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:107` (`reload_config` sets event), `:256-269` (`_interruptible_sleep` clears it) ; `services/scanner_watchdog.py:60-66`
- **Status**: NEW
- **Description**: `_run_cycle` runs `_do_scan` (minutes) and then `_interruptible_sleep`, whose first statement is `self._trigger_event.clear()`. Any `reload_config()` (folder added/removed, `auto_scan`/interval changed) and any debounced watchdog event that fired during the scan is therefore dropped, and the scanner sleeps the full `scan_interval` (default 3600 s). The frontend explicitly relies on the wake-up: `useSettingsDialog.ts:123` "Auto-scanner wakes up via reload_config() on the backend — no manual scan trigger needed".
- **Evidence**: `library_auto_scanner.py:264` `self._trigger_event.clear()` immediately before `await asyncio.wait_for(self._trigger_event.wait(), …)`; the event is also the only signal set by `reload_config` (`:107`) and the watchdog `_DebounceHandler` (`scanner_watchdog.py:64-66`).
- **Impact**: A folder added (or files copied in) while the startup/scheduled scan is running is not picked up until the next interval; the "real-time" watcher misses exactly the busy periods.
- **Suggested Fix**: Clear the event *before* `_do_scan` (at the top of the cycle) instead of in the sleep helper, or loop `while self._trigger_event.is_set()` after the scan.

#### INT-F5-3: `player_state` seq watermark is reset in a post-render effect, so the first snapshot after a backend restart can be dropped (incomplete fix of #4338)
- **Severity**: MEDIUM
- **Flow**: 5 - WebSocket Lifecycle (reconnect state resync)
- **Boundary**: Backend (initial `player_state` push on connect) -> Frontend (`usePlayerStateSync`)
- **Location**: `auralis-web/backend/ws_handlers/connection.py:151-159` -> `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:85-92,105-108`
- **Status**: Regression of #4338 (closed; fix is race-dependent)
- **Description**: The server pushes `enhancement_settings_changed` and `player_state` immediately after `accept()`. The watermarks (`lastSeenSeqRef`, transport, volume, track_changed) are zeroed in a `useEffect([connectionStatus])`, which runs only after React renders the `setConnectionStatus('connected')` made in `ws.onopen`. Both are scheduled as default-priority work (render + passive-effect flush are separate scheduler tasks), while the first server frames are separate WS `message` tasks queued behind `open`. The frame can be handled against the pre-restart watermark. Contrast `resetStreamFrameTracking()`, which #5619 correctly calls synchronously in the `open` path.
- **Evidence**:
  - `usePlayerStateSync.ts:85-87`: `useEffect(() => { if (connectionStatus === 'connected') { lastSeenSeqRef.current = 0; ...` (effect, not the open handler)
  - `usePlayerStateSync.ts:105-106`: `if (state.seq < lastSeenSeqRef.current) return;`
  - `core/state_manager.py:42,61-62` + `player_state.py:63`: a fresh process starts `_update_seq` at 0 and a new `server_instance_id`.
  - `useServerRestartNotice.ts:35-42` consumes the same frame without a watermark, so the user can get the "audio engine restarted" toast while Redux keeps the pre-restart queue/track/isPlaying.
- **Impact**: After a backend restart the reconnect snapshot (the only state resync; the idle backend sends no further `player_state`) may be discarded, leaving stale queue/current track/`isPlaying` in Redux until the next mutation. Ordering-dependent, so intermittent.
- **Suggested Fix**: Reset the watermarks when `player_state.server_instance_id` changes (data already on the frame), or reset them synchronously from the manager `open` handler next to `resetStreamFrameTracking`.

#### INT-F5-4: Origin rejection is sent pre-`accept()`, so the browser sees 1006/HTTP 403, never 1008; the #5469 permanent-failure path is dead
- **Severity**: MEDIUM
- **Flow**: 5 - WebSocket Lifecycle (connection init / handshake rejection)
- **Boundary**: Backend (`ConnectionManager.connect`) -> Frontend (`WebSocketManager.onclose`)
- **Location**: `auralis-web/backend/config/globals.py:121-135` -> `auralis-web/frontend/src/utils/errorHandling.ts:46,121-135`
- **Status**: Regression of #5469 (closed "WS reconnect loop ignores close code, retries a permanent 1008 rejection")
- **Description**: The backend calls `await websocket.close(code=1008)` and raises `WebSocketOriginRejected` *before* `await websocket.accept()` (#4703). Per ASGI, a close before accept is answered as an HTTP 403 handshake failure; a browser reports `onerror` + `onclose` with code **1006**, not the app-chosen 1008. The frontend only treats `1008` as permanent, so the rejected client retries up to `maxReconnectAttempts` (10 prod, 3 dev; backoff 1,2,4,8,16,30 s ...) against a refusal that can never succeed. Backend tests (Starlette `TestClient`) report the 1008 code and mask this.
- **Evidence**:
  - `globals.py:121-123`: `await websocket.close(code=1008)  # Policy Violation` then `raise WebSocketOriginRejected(...)` ; `accept()` is at :135 only on success.
  - `errorHandling.ts:46`: `const POLICY_CLOSE_CODES = new Set([1008]);` used at :125 against `event.code`.
- **Impact**: A mis-originated client (dev server on an unlisted port, `127.0.0.1` vs configured host, `VITE_WS_URL` pointing elsewhere) spins ~3 min of futile reconnects with `connectionStatus` flipping `disconnected`/`error` instead of failing fast with a clear policy error.
- **Suggested Fix**: Backend: `accept()` first and then `close(1008)` so the code reaches the client (cost: one accepted-then-closed socket), or add an HTTP-level origin check. Frontend: also treat "never opened" repeated failures (close 1006 with no prior `onopen`) as a capped, surfaced failure after N attempts.

#### INT-F5-5: A client evicted by `broadcast()` after one 2 s send timeout stays connected but never receives another broadcast
- **Severity**: MEDIUM
- **Flow**: 5 - WebSocket Lifecycle (backpressure, stale state)
- **Boundary**: Backend (`ConnectionManager.broadcast`) -> Frontend (all broadcast subscribers)
- **Location**: `auralis-web/backend/config/globals.py:176-234` (also `websocket_endpoint` `system.py:102-176`)
- **Status**: NEW (adjacent: #4581, #4784 closed; #5077 open covers only the heartbeat close path)
- **Description**: `_send_to` wraps `send_text` in `asyncio.wait_for(..., 2.0)`. Since uvicorn 0.52.1 is pinned (#4784) `send()` really blocks on `writable` while the transport is over its high-water mark, and that gate is shared with the PCM sender on the same socket, so the timeout is live. On timeout the socket is removed from `active_connections` ("marking connection stale for removal") but is neither closed nor told anything; the endpoint's receive loop, heartbeat (pong still answered) and stream task continue. Nothing re-adds it, so `position_changed`, `player_state`, `playback_*`, `scan_*`, `library_updated`, `artwork_updated` stop for that tab until it reconnects, and the connection looks healthy to the client (`isConnected` true, no resync).
- **Evidence**:
  - `globals.py:178-181`: `await asyncio.wait_for(connection.send_text(message_json), timeout=BROADCAST_SEND_TIMEOUT)`
  - `globals.py:225-229`: `for stale in stale_connections: if stale in self.active_connections: self.active_connections.remove(stale)` (no `close()`)
  - `grep active_connections` shows no other writer except `connect()`.
- **Impact**: One slow patch (renderer busy for >2 s while a 3.5 MB chunk is in flight, devtools pause, GC) permanently blinds the UI to transport/library events for the session: the progress tick freezes, library scans appear stuck, queue/player state drifts (the client only recovers at the next reconnect, which never happens).
- **Suggested Fix**: On eviction `close(code=1013 or 1011)` the socket so the frontend's reconnect + initial `player_state`/`enhancement_settings_changed` push (`setup_connection`) resynchronises; or keep the connection in the set and drop only the one frame.

#### INT-F5-6: Keyboard seeks are unthrottled and WS command rejections are not correlated, so a rate-limited `seek` leaves the client in a stuck "seeking" state
- **Severity**: MEDIUM
- **Flow**: 5 - WebSocket Lifecycle (inbound rate limit, error frames)
- **Boundary**: Frontend (`seek` frames) -> Backend (`WebSocketRateLimiter`) -> Frontend (`error` frame handling)
- **Location**: `auralis-web/frontend/src/components/player/useProgressBarInteraction.ts:179-191`, `hooks/enhancement/useEnhancedSeek.ts:56-80` -> `auralis-web/backend/routers/system.py:41,142-152`, `websocket/websocket_security.py:113-162`; `frontend/src/hooks/websocket/useWebSocketErrors.ts:221-230`
- **Status**: NEW (mouse-drag variant fixed in #5625; keyboard path not covered)
- **Description**: #5625 made a mouse/touch drag commit one seek, but `handleKeyDown` still calls `onSeek` per keydown. Holding an arrow key auto-repeats ~30 Hz; each call stops the engine, resets the buffer, sets `isSeeking=true` and sends a `seek` that makes the backend cancel and restart the stream. The limiter (10 msg/s per connection, 30/s per IP, `buffer_full`/`buffer_ready` not exempt) rejects the surplus with `{type:'error', error:'rate_limit_exceeded'}`. The only `error` consumer is `useWebSocketErrors`, which toasts; nothing rolls back the optimistic client state or retries the dropped frame (`isSeeking` is cleared only by `seek_started`/`audio_stream_start` that never come for a rejected seek). The same limiter can drop a `buffer_ready` (see INT-F5-1).
- **Evidence**:
  - `useProgressBarInteraction.ts:185-189`: `const newPosition = keyboardSeekTarget(event.key, currentTime, duration); ... onSeek(newPosition);`
  - `useEnhancedSeek.ts:65-85`: `setIsSeeking(true); engine.stopPlayback(); pcmBuffer.reset(); ... wsContext.send({ type: 'seek', ...})`
  - `system.py:142-152`: non-exempt types go through `_rate_limiter.check_rate_limit` and are answered `rate_limit_exceeded`.
  - `useWebSocketErrors.ts:224-229`: `useWebSocketMessages(['error'], ... warning(message.message ...))`
- **Impact**: Key-repeat seeking produces up to ~20 error toasts per second, ~10 stream restarts per second, and the last (target) seek can be the one rejected, leaving audio stopped / spinner on while the old stream keeps appending into the reset buffer.
- **Suggested Fix**: Frontend: debounce/coalesce keyboard seeks to one commit (like #5625) and treat a `rate_limit_exceeded`/`internal_error` frame while `isSeeking` as a failed command (clear `isSeeking`, re-send latest target). Backend: exempt `buffer_full`/`buffer_ready` (tiny, protocol-critical, like ping/pong #4786) and echo a `request_id`/command name in the error frame.
- **Merged duplicates**: INT-F1-5, INT-F8-3. Found independently by Flows 1, 5 and 8. Flow 1 adds that `buffer_full`/`buffer_ready` are not in `_RATE_LIMIT_EXEMPT_TYPES` (`system.py:47`) although the #4786 comment names them as the frames a seek-bar burst drops; a dropped `buffer_ready` parks the stream forever (see INT-F5-1). Flow 8 adds that `seekTo` performs its destructive local reset (engine stop, ring reset, `isSeeking=true`) before sending, so a rejected seek landing after the previous seek's `audio_stream_start` wipes a live stream and leaves the progress bar disabled (`Player.tsx:131`).

#### INT-F5-8: `WebSocketProvider` treats any localhost port >= 3000 as the Vite dev server and connects to hard-coded `ws://localhost:8765`, so `launch-auralis-web.py --port N` cannot connect
- **Severity**: MEDIUM
- **Flow**: 5 - WebSocket Lifecycle (connection init)
- **Boundary**: Launcher/Backend (`AURALIS_PORT`) -> Frontend (WS URL)
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:142-148`, `config/api.ts:21` <- `launch-auralis-web.py:68-71,169`, `backend/main.py:121`
- **Status**: NEW (incomplete fix of #4805; #5796 closed only covers the backend side)
- **Description**: #4805 made `--port` bind the backend and open the browser at `http://localhost:<port>`. The served production frontend then computes its WS URL: hostname `localhost` and `parseInt(port) >= 3000` (true for 9000) selects the "development" branch `${WS_BASE_URL}/ws` where `WS_BASE_URL = VITE_WS_URL ?? 'ws://localhost:8765'` is a build-time constant. REST has the same constant (`API_BASE_URL = 'http://localhost:8765'`). The backend allows the page origin (`BACKEND_PORT` is in the origin matrix) but the socket targets a different port.
- **Evidence**:
  - `WebSocketContext.tsx:142-145`: `if (window.location.hostname === 'localhost' && parseInt(window.location.port) >= 3000) { return \`${WS_BASE_URL}/ws\` }`
  - `launch-auralis-web.py:71`: `env["AURALIS_PORT"] = str(port)`; `:169` `frontend_url = f"http://localhost:{args.port}"`
- **Impact**: With a non-default port the app loads but REST and WS both fail (or talk to another process on 8765); the WS manager retries ~3 minutes then gives up.
- **Suggested Fix**: Frontend: when not served by Vite (`import.meta.env.DEV` false) always derive from `window.location` (`ws(s)://${location.host}/ws`); keep the explicit Vite branch gated on `import.meta.env.DEV`. Apply the same to `API_BASE_URL`.

#### INT-F5-9: Every `play_*` spawns a full mastering-recommendation analysis and broadcast whose only frontend consumer was deleted
- **Severity**: MEDIUM
- **Flow**: 5 - WebSocket Lifecycle (message inventory: sent but never handled)
- **Boundary**: Backend (`ws_handlers/playback_commands.py` -> `RecommendationService`) -> Frontend (no subscriber)
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:139-182,319-322,374-377`, `services/recommendation_service.py:104-150` -> `frontend/src/types/ws/enhancement.ts` (types only)
- **Status**: NEW (inverse of #4542, which added the trigger because the panel existed; the consumer hook was removed in #5767)
- **Description**: `_generate_mastering_recommendation` runs on every `play_enhanced`/`play_normal`: DB read, `RecommendationService` -> `ChunkedAudioProcessor` construction + analysis on the shared thread pool (#5248 notes it can exhaust the pool) and `broadcast_typed(..., "mastering_recommendation")` to all sockets. `grep mastering_recommendation|MasteringRecommendation` in `frontend/src` (non-test) matches only `types/ws/*`; `useMasteringRecommendation.ts` and the panel were deleted. `websocketTypeDiagnostics` only warns for *unregistered* types, so the registered-but-unsubscribed type is silent.
- **Evidence**: `playback_commands.py:319-322` `spawn_background_task(_generate_mastering_recommendation(track_id, deps), ...)`; `git log --diff-filter=D` shows `useMasteringRecommendation.ts` removed in `0a7e91d6 (#5767)`.
- **Impact**: Wasted CPU/IO plus a pool slot on every track start, contending with the first-chunk latency of the stream the user is waiting for; broadcast bytes with no reader.
- **Suggested Fix**: Delete the trigger (and `mastering_recommendation`/`MasteringRecommendationPayload`, the REST route if equally unused) or reinstate a consumer; at minimum remove it from the playback hot path.

#### INT-F6-1: Clicking a similar track silently does nothing unless that track is already loaded in the current view
- **Severity**: MEDIUM
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Backend `/similar` (library-wide ids) -> Frontend play handler (view-scoped track list)
- **Location**: `auralis-web/backend/routers/similarity_query.py:22` -> `auralis-web/frontend/src/components/library/useSimilarTracksModal.ts:44-50` and `components/library/Details/AlbumDetailView.tsx:226-231`
- **Status**: NEW
- **Description**: `/api/similarity/tracks/{id}/similar` returns ids from the whole library with only `title/artist/album` text. The modal's `onTrackPlay(trackId)` is resolved against whatever `tracks` array the host view holds. In `CozyLibraryView` that is the paginated (50 per page, infinite scroll) songs/favourites list; in `AlbumDetailView` it is only `album.tracks`. A similar track not in that array is dropped without feedback, and `SimilarTracksModal.handleTrackClick` closes the modal regardless.
- **Evidence**:
  - `useSimilarTracksModal.ts:44-50`: `const track = tracks.find(t => t.id === trackId); if (track) onPlayTrack(track);`
  - `AlbumDetailView.tsx:226-231`: `const track = album.tracks?.find((t: Track) => t.id === trackId); if (track) { playTrack(track); }`
  - `SimilarTracksModal.tsx:89-94`: `onTrackPlay(track.trackId); onClose();`
  - `useLibraryQuery.ts:99,210`: `limit = options.limit || 50` ... `nextOffset = offset + limit` (list is partial until the user scrolls).
  - Similarity is meant for cross-genre discovery (router docstring), so results are mostly outside the current album/page.
- **Impact**: The primary action of the Similar Tracks feature (click a result to play it) works only by coincidence. From an album page it almost never works (results come from other albums); from the library grid it works only for already-scrolled pages. The user sees the modal close and nothing play.
- **Suggested Fix**: Frontend: when the id is not in the local list, resolve it through the library API (single-track fetch) or the player's play-by-id/queue API, and keep the modal open with an error if that fails. Alternatively have `SimilarTrack` carry the full `TrackResponse` (the backend already batch-loads `repos.tracks.get_by_ids`).

#### INT-F6-2: `POST /api/similarity/fit` ignores the result of `fit()` and the caller's `min_samples`, and reports success when nothing was fitted
- **Severity**: MEDIUM
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Backend router -> Engine (`FingerprintSimilarity.fit`) -> API client
- **Location**: `auralis-web/backend/routers/similarity_explain.py:85-128` -> `auralis/analysis/fingerprint/similarity.py:82-125`, `normalizer.py:151-155`
- **Status**: NEW (related: #5716 covers the unfiltered `get_count` gate and the lack of refit, not the router's handling)
- **Description**: The router validates `min_samples` (query param, `ge=5`) against `repos.fingerprints.get_count()` and then calls `similarity.fit` with no arguments, so the engine applies its own default of 10. `fit()` returns `False` when it declines, but the router discards the return value and unconditionally returns `{"fitted": True, "message": "Successfully fitted ..."}`. `get_count()` is also unfiltered (counts stale-version rows and claim placeholders) while the normalizer reads `get_all()` (current rows only).
- **Evidence**:
  - `similarity_explain.py:111-125`: `if fingerprint_count < min_samples: raise BadRequestError(...)` / `await asyncio.to_thread(similarity.fit)` / `return {"fitted": True, "total_fingerprints": fingerprint_count, "message": f"Successfully fitted similarity system with {fingerprint_count} tracks"}`
  - `similarity.py:82`: `def fit(self, min_samples: int = 10, stop_event=...) -> bool:` ... `error("Failed to fit similarity system")`; `return success`
  - `normalizer.py:151-155`: `total = fingerprint_repository.get_count(); if total < min_samples: error(...); return False`
- **Impact**: `POST /fit?min_samples=5` on a library with 5-9 fingerprints returns 200 `fitted:true` while `is_fitted()` stays False, so the next `/similar` still returns 503 "not initialized". After an algorithm-version bump (mostly stale rows) the same happens with a large `get_count()` and few readable rows. `FitSimilarityResponse.fitted` ("True once the system is fitted") is false in these cases.
- **Suggested Fix**: Pass `min_samples` through (`similarity.fit, min_samples=min_samples`), check the boolean and raise 400/409 when it is False; report `total_fingerprints` from the fitted normalizer or a current-rows count, not `get_count()`.

#### INT-F6-3: Manual fit never publishes `graph_builder`, so `POST /graph/build` stays 503 after following its own error message
- **Severity**: MEDIUM
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Backend startup wiring -> graph router
- **Location**: `auralis-web/backend/routers/similarity_explain.py:85-128` and `routers/similarity_graph.py:76-82` -> `services/similarity_autofit_worker.py:84-92`
- **Status**: NEW
- **Description**: `globals['graph_builder']` is set to `None` at startup and assigned in exactly one place, `SimilarityAutoFitWorker._run`, and only when the startup auto-fit succeeds. On a fresh install (fewer than 10 fingerprints at startup) the auto-fit is skipped and the builder is never created. `POST /fit` fits the shared `FingerprintSimilarity` instance but has no handle on `globals_dict`, so it cannot create the builder. `POST /graph/build` then keeps answering "Similarity system not fitted. Please fit the system first using POST /api/similarity/fit", and `DELETE /graph` returns `{"edges_deleted": 0}` even when edges exist, until the backend restarts.
- **Evidence**:
  - `similarity_autofit_worker.py:84-92`: `if self._sim_system.fit(stop_event=...): self._globals_dict['graph_builder'] = self._builder_cls(...)` (the only assignment besides `config/startup/fingerprint.py:143,155` which set `None`).
  - `similarity_graph.py:76-78`: `if graph_builder is None: raise ServiceUnavailableError("Similarity system not fitted. Please fit the system first using POST /api/similarity/fit")`
  - A search of `auralis-web/backend` finds no other writer of `'graph_builder'`.
- **Impact**: The documented admin workflow (fit, then build graph) is unreachable on any library that was too small at launch, and the 503 text sends the caller in a circle.
- **Suggested Fix**: Create the builder lazily in `_graph_builder_getter` from the fitted `similarity_system` plus `library_database.SessionLocal` when `is_fitted()` is true, or have the fit route own that publication.

#### INT-F6-4: Fingerprint coverage payload contradicts itself (outdated rows count as "fingerprinted" but not as "progress"), and the similarity layer treats the same rows as missing
- **Severity**: MEDIUM
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Repository stats -> Backend status router -> Frontend coverage card
- **Location**: `auralis/library/repositories/fingerprint_stats_repository.py:81-129` -> `auralis-web/backend/routers/fingerprint_status.py:68-96`, `routers/fingerprint_queue.py:130-190,236-252` -> `frontend/src/hooks/library/useFingerprintCoverage.ts:119-144`, `components/settings/FingerprintCoverageCard.tsx:80-99`
- **Status**: NEW
- **Description**: `get_fingerprint_stats()` defines `fingerprinted = current + outdated` and `pending = total - fingerprinted`, but `progress_percent = int(current / total * 100)`. Consumers mix them: the status router derives "All tracks fingerprinted" from `fingerprinted == total`, the card shows `fingerprinted/total` next to a bar driven by `progress_percent`. `FINGERPRINT_ALGORITHM_VERSION` is 10, and rows below it are invisible to every similarity/display read (`_current_fingerprint_clause`, `exists`, `get_by_track_id`), which answer 404 "does not have a fingerprint" for them.
- **Evidence**:
  - `fingerprint_stats_repository.py:117-121`: `fingerprinted_count = current_count + outdated_count; pending_count = max(0, total_tracks - fingerprinted_count); progress_percent = int((current_count / max(1, total_tracks)) * 100)`
  - `fingerprint_status.py:77-80`: `elif fingerprinted_count == total_tracks: status = "All tracks fingerprinted"`
  - `FingerprintCoverageCard.tsx`: renders `{fingerprintedTracks} / {totalTracks}`, `<LinearProgress value={progressPercent}>`, `coverage.status`; the "Analyse remaining" button only `if pendingTracks > 0`.
  - `useFingerprintCoverage.ts:136-144`: polling only while `pendingTracks > 0`.
  - `fingerprint_queue.py:149-155`: `if pending == 0: return {... "message": "All tracks already have fingerprints!"}`; `get_missing_fingerprints` (`fingerprint_query_mixin.py:196-205`) is an unfiltered outer join, so outdated rows are never returned either.
- **Impact**: After any algorithm bump, N outdated tracks show "N / N", "All tracks fingerprinted" and a 0% bar. While the background scheduler re-fingerprints them the bar advances, but polling already stopped (pending == 0), so it freezes until the dialog is reopened. "Analyse remaining" never appears and `enqueue-all` is a no-op for outdated rows, while `/similar`, `/compare`, `/explain` and `/tracks/{id}/fingerprint` reject those same tracks as having no fingerprint.
- **Suggested Fix**: Backend: report `fingerprinted = current` and `pending = total - current` (or add `outdated` to the response and poll while it is non-zero); make the status line consistent with `progress_percent`; let `get_missing_fingerprints`/`enqueue-all` include outdated rows. Frontend: poll while `progressPercent < 100`.

#### INT-F6-5: Similarity returns short lists (sometimes 1-2 "similar" tracks) because the pre-filter box falls back only when it is completely empty
- **Severity**: MEDIUM
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Engine (`find_similar`) -> Backend response -> Frontend modal
- **Location**: `auralis/analysis/fingerprint/similarity.py:137-163,305-342` -> `routers/similarity_query.py:79-105`
- **Status**: NEW (adjacent to open #5715, which covers the missing `ORDER BY`; this is the under-fill side)
- **Description**: `find_similar` first restricts candidates to a hard box (lufs +-3, crest +-2 dB, bass_pct +-0.08, tempo +-15 BPM, all ANDed). The 5000-row fallback runs only `if not candidates:`. A box containing 1..n-1 rows returns exactly those rows, however far they are in 25-D and however many better matches lie outside the box. The router's #4864 logic (`len(neighbors) >= limit`, else recompute) assumes the recompute can widen; it runs the same pre-filter and returns the same short list.
- **Evidence**:
  - `similarity.py:155-163`: `candidates = self._get_prefiltered_candidates(...)`; `if not candidates: ... all_fps = self.fingerprint_repo.get_all(limit=5000)`
  - `similarity.py:322-327`: four-dimension box built from `target_fp.lufs/crest_db/bass_pct/tempo_bpm`
  - `similarity_query.py:60-73` comment: "When the library genuinely holds fewer than `limit` similar tracks the fallback returns the same short list".
  - UI requests `limit=20` (`CozyLibraryView.tsx:277`).
- **Impact**: On small or eclectic libraries a track with unusual loudness or tempo gets a handful of results while hundreds of tracks are rankable; a track whose box holds only itself shows "No similar tracks found". The persisted K-NN graph inherits the under-fill (fewer than `k` edges per track), hidden by `GraphStats.k_neighbors` being an average.
- **Suggested Fix**: Engine: when the box yields fewer than `n` candidates, top up from a bounded unfiltered ranked search (5000 rows ranked in NumPy) instead of falling back only on zero.

#### INT-F6-6: `useTrackFingerprint` treats every 404 as "queued" and polls forever, re-enqueueing a permanently failing track every 5 s
- **Severity**: MEDIUM
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Backend `/api/tracks/{id}/fingerprint` -> Frontend hook / AlbumCharacterPane
- **Location**: `routers/fingerprint_status.py:100-148` -> `frontend/src/hooks/fingerprint/useTrackFingerprint.ts:44-62,92-110`
- **Status**: NEW (the hook's 5xx handling is #4847, fixed; this is the 404 half)
- **Description**: The backend uses 404 for three different things: unknown track ("Track N not found"), fingerprint missing and queued ("...Queued for generation."), and fingerprint missing and not queued ("Not queued (already pending, or the background queue is full)"). `useSimilarTracks` keys on the detail text; `useTrackFingerprint` returns `null` for any 404 and `refetchInterval` returns 5000 ms whenever `data === null`, with no attempt cap. Each poll calls `queue.enqueue` again. `FingerprintQueue` dedupes only queued/processing ids and keeps no failed set, so a file that cannot be fingerprinted (unreadable, Rust DSP missing, 30 s timeout) is retried on every poll.
- **Evidence**:
  - `useTrackFingerprint.ts:52-54`: `if (err instanceof APIRequestError && err.statusCode === 404) { return null; }`
  - `useTrackFingerprint.ts:102-104`: `if (query.state.data === null) { return retryInterval; }`
  - `analysis/fingerprint_queue.py:92-110` (`enqueue` dedup only on `queued_set`/`processing`) and `:226-232` (`failed += 1` without recording the id).
  - `fingerprint_status.py:100-102`: `raise NotFoundError("Track", track_id)` for an unknown track.
- **Impact**: AlbumCharacterPane shows "analysing" indefinitely for a deleted track or an unprocessable file, and the backend burns one decode+analysis attempt (up to the 30 s `FingerprintGenerator.TIMEOUT`) per 5 s, plus log noise, for as long as the pane is open. A real failure is indistinguishable from a transient state.
- **Suggested Fix**: Frontend: classify the 404 detail (reuse the `classifySimilarityError` markers), stop polling for "not found", and cap polling attempts. Backend: keep a cooldown of recently failed ids in `FingerprintQueue` and report failure with a distinct status/code instead of 404.

#### INT-F7-1: `artwork_updated` cannot make art appear for an album that had none, and TrackRow's error flag is sticky
- **Severity**: MEDIUM
- **Flow**: 7 Artwork
- **Boundary**: Backend (WS `artwork_updated`) → Frontend state
- **Location**: `auralis-web/backend/routers/artwork_deps.py:32-47` → `auralis-web/frontend/src/hooks/library/useArtworkUpdates.ts:68-76`, `components/album/AlbumCard/AlbumCard.tsx:76`, `components/library/Items/tracks/useTrackImage.ts:12-24`, `services/artworkService.ts:57-70`
- **Status**: NEW (#5473 only fixed cache-busting of an already-present URL; #2867 only added the subscription)
- **Description**: The backend broadcasts `{action: extracted|downloaded|deleted, album_id, artwork_url?}`. The frontend discards everything except `album_id` and bumps a numeric revision. Every consumer that renders a thumbnail from list data gates on a field captured before the update, so the revision bump has nothing to act on in the case that matters, an album that had no artwork. (a) `AlbumCard` builds a URL only if `hasArtwork` is true; the grid passes `!!album.artworkUrl` from the list payload, which is null before the extract/download. (b) `withArtworkSize(undefined, …)` returns `undefined`, so `TrackRow`/`TrackCard` cannot start showing art. (c) For a row whose `<img>` previously failed (e.g. a 404 before the download), `useTrackImage` keeps one boolean `imageError` for the life of the mounted row and never resets it when the URL/revision changes, so even `?v=N` is never tried. `MediaCardArtwork` does reset on URL change, so only TrackRow has this. No list refetch is triggered by `artwork_updated`, and the message's `artwork_url` is unused.
- **Evidence**:
  - `AlbumCard.tsx:76-78`: `const artworkUrl = hasArtwork ? getArtworkUrl(albumId, { size: 256, revision: artworkRevision }) : undefined;`
  - `VirtualizedAlbumGrid.tsx:132`: `hasArtwork={!!album.artworkUrl}`
  - `artworkService.ts:57`: `if (!url) return url;`
  - `useTrackImage.ts:12-14`: `const [imageError, setImageError] = useState(false); … setImageError(true)` with no reset path
  - `useArtworkUpdates.ts:72-73`: only `msg.data.album_id` is read, `bumpRevision(msg.data.album_id)`
- **Impact**: After POST `/artwork/extract` or `/artwork/download` for an album without art (the only case where those endpoints do anything useful), grid cards and track rows keep showing placeholders until the user navigates away and the list is refetched. The mounted TrackRow stays on the MusicNote icon even after the art exists. Currently latent in the shipped UI because no component calls the extract/download endpoints (#5214), but the endpoints are public and the WS contract is advertised as the refresh mechanism.
- **Suggested Fix**: On `artwork_updated`, make the revision store also carry `hasArtwork = action !== 'deleted'` per album, and have AlbumCard/TrackRow/TrackCard build the URL from `albumId` whenever the store says the album has art. Alternatively invalidate the albums/tracks queries. Reset `imageError` in `useTrackImage` when the URL changes, as `MediaCardArtwork` already does.

#### INT-F7-2: Player bar requests full-resolution artwork and ignores `artwork_updated`
- **Severity**: MEDIUM
- **Flow**: 7 Artwork
- **Boundary**: Frontend (player bar) → Backend `GET /api/albums/{id}/artwork`
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:143` → `components/player/TrackDisplay.tsx:141-153` → `auralis-web/backend/routers/artwork.py:179-186`
- **Status**: NEW (#5521 added the image; #4447/#4901/#5473 sized and cache-busted every other consumer but not this one)
- **Description**: `Player` passes `currentTrack?.artworkUrl` (the bare `/api/albums/{id}/artwork` from `TrackInfo`) straight to `<img src>` of a 44×44 element. It does not go through `withArtworkSize` and does not subscribe to `useArtworkRevision`. The backend therefore serves the stored original (up to 2048px, up to 5 MiB, `MAX_ARTWORK_DIMENSION`), and the browser decodes a multi-megapixel bitmap for a 44px slot on every track change. When the artwork of the playing album is replaced or deleted, the `src` string never changes, so the image is not refetched.
- **Evidence**:
  - `Player.tsx:143`: `artworkUrl={currentTrack?.artworkUrl}`
  - `TrackDisplay.tsx:143-146`: `<img src={artworkUrl} … style={{ width: 44, height: 44, … }} />`
  - the sized callers: `TrackRow.tsx:112`: `withArtworkSize(track.artworkUrl ?? undefined, 80, artworkRevision)`
  - backend only thumbnails when `size is not None` (`artwork.py:183`)
- **Impact**: This is the always-on artwork surface and the one the #4447 fix targeted elsewhere: the largest transfer and decode of any artwork request, repeated at every track change. Stale or missing art in the player bar after an artwork update, until the track changes.
- **Suggested Fix**: In `Player.tsx` (or `TrackDisplay`) apply `withArtworkSize(url, 88, useArtworkRevision(currentTrack.albumId))`. `TrackInfo` carries no `album_id`, so either add it to `TrackPayload`/`TrackInfo` or parse it from the URL.

#### INT-F7-3: Every artwork GET (including 304 revalidations) loads the whole album graph
- **Severity**: MEDIUM
- **Flow**: 7 Artwork
- **Boundary**: Backend router → Engine repository
- **Location**: `auralis-web/backend/routers/artwork.py:121` → `auralis/library/repositories/album_repository.py:74-87` (`_ALBUM_DETAIL_OPTIONS`, :48-53)
- **Status**: NEW
- **Description**: The handler needs only `album.artwork_path`, but calls `repos.albums.get_by_id`, which eager-loads the artist, all tracks, and each track's genres, artists and album (four `selectinload`/`joinedload` options), then `expunge_all()`s the lot. The sibling `extract_and_save_artwork` deliberately uses a narrow `selectinload(Album.tracks)` query (#5028 comment at `album_artwork.py:30-33`), so the repository already acknowledges the cost. Because artwork responses are `Cache-Control: public, no-cache`, every thumbnail mount (scrolling a virtualized grid back and forth, remount of a tab) issues a conditional request that runs this full query before it can answer 304.
- **Evidence**:
  - `artwork.py:121`: `album = await asyncio.to_thread(repos.albums.get_by_id, album_id)`
  - `album_repository.py:48-53`: `_ALBUM_DETAIL_OPTIONS = (joinedload(Album.artist), selectinload(Album.tracks).selectinload(Track.genres), …artists, … .joinedload(Track.album))`
  - only `album.artwork_path` is read afterwards (`artwork.py:127,148`)
- **Impact**: A 200-card grid first paint is roughly 200 requests × about 5 queries each, with rows proportional to the album's track count and ORM hydration on the shared DB thread pool. Latency on thumbnail loading and contention with playback/scan DB access scales with library size, instead of one PK lookup per image.
- **Suggested Fix**: Add a narrow repository read such as `get_artwork_path(album_id) -> str | None` (a single `select(Album.artwork_path)`) and use it in `get_album_artwork` (and the `previous_path` reads in `artwork_manage.py:41,90`). Optionally embed the content hash in `artwork_url` (`?v=<hash>`) and serve `Cache-Control: public, max-age=31536000, immutable`, so revalidation disappears.

#### INT-F8-4: `SeekableSource.close()` races an executor thread still inside `resolve()` - temp WAV conversion leaked (m4a/aac/wma) when a seek lands during the first chunk
- **Severity**: MEDIUM
- **Flow**: 8 - Seek & Rebuffer
- **Boundary**: Backend stream task teardown -> backend executor thread -> `converted_wavs` registry
- **Location**: `auralis-web/backend/core/seekable_source.py:240-265` (`resolve`/`close`) <- `core/chunk_render.py:122` (`processor._source.resolve()` in the DSP thread) vs `core/stream_seek.py:286` (`await asyncio.to_thread(processor.close)` in the cancelled task's `finally`)
- **Status**: NEW (sibling of closed #5253/#5402, which only fixed the normal close path)
- **Description**: The conversion is acquired lazily, by the first `load_chunk` on a streaming-pool thread, and `SeekableSource._key` is only assigned after `acquire()` returns (which can block for the whole FFmpeg decode of the file). `handle_seek` cancels the prior stream task, but cancelling `await run_in_stream_executor(...)` does not stop the thread (the code base says so itself in `chunk_stream_state._raise_if_cancelled`, which polls only before DSP and before the write). The cancelled task's `finally` calls `processor.close()`; if the thread is still inside `acquire()`/`convert_to_temp_wav`, `_key is None` so `close()` is a no-op. The thread then finishes, sets `_key`/`_resolved` on an object nobody will close again, and the registry entry keeps `refs >= 1` forever, so it is never moved to the idle list or evicted. The same happens if `close()` runs between the cancel-event check and `resolve()` (the call re-acquires after close).
- **Evidence**:
  - `seekable_source.py:254`: `self._key, self._resolved = self._registry.acquire(self._filepath)` (assignment after the blocking decode); `:259`: `if self._key is None: return` (close is a no-op while acquire is in flight).
  - `chunk_render.py:122`: `seekable_path = processor._source.resolve()` runs in the executor thread inside `process_chunk`.
  - `stream_seek.py:285-286`: `if processor is not None: await asyncio.to_thread(processor.close)` runs as soon as the task is cancelled, independent of the worker thread.
  - `seekable_source.py` registry: `release()` is the only path to `_idle`/eviction and requires `refs` to reach 0.
- **Impact**: For m4a/aac/wma tracks, pressing play and scrubbing (or rapid scrubbing) while the first conversion (several seconds) is running leaks a full-track float32 WAV (about 210 MB for 10 min stereo 44.1 kHz) in the temp root for the process lifetime; each later holder of the same file also never drops it to idle. Repeatable disk/tmpfs growth on a normal user action.
- **Suggested Fix**: Make `SeekableSource` own its lifecycle atomically: guard `resolve()`/`close()` with a lock and a `_closed` flag so a `resolve()` that completes (or starts) after `close()` releases its hold immediately; or serialize teardown on the executor future so `close()` runs after the in-flight chunk thread exits.

#### INT-F9-1: Any `player_state` frame (repeat toggle, queue clear, WS reconnect push) overwrites live frontend-owned volume / mute / playing / duration / time with stale state-manager values
- **Severity**: MEDIUM
- **Flow**: 9 - Queue & Playback State
- **Boundary**: Backend (PlayerStateManager snapshot) -> Frontend (applyPlayerStateSnapshot -> Redux player slice)
- **Location**: `auralis-web/backend/core/state_manager.py:69-92,226-228` and `auralis-web/backend/routers/player_queue.py:159` and `auralis-web/backend/ws_handlers/connection.py:150-160` -> `auralis-web/frontend/src/hooks/player/playerStateSnapshot.ts:62-91`
- **Status**: NEW (adjacent to #5601, which gated only `current_track`/`queue_index`, and to #5460, which covers only `queue`)
- **Description**: `PlayerStateManager.state` is never told about anything the browser session does: volume is set only locally (`PlaybackSessionContext.tsx:handleVolumeChange` calls `setStreamingVolume` + `dispatch(setVolumeAction)`, no REST; `ENDPOINTS.PLAYER_VOLUME` has no caller), pause/resume/stop travel over the WS and only emit `playback_*` events, track skips are Redux-only. After `_set_queue_impl` calls `set_playing(True)` the manager keeps `is_playing=True`, `volume=80`, `is_muted=False`, `current_track=<first track>`, `duration=<first track duration>` and a wall-clock `current_time` forever. The next full `player_state` broadcast — triggered by the repeat button (`POST /api/player/queue/repeat` -> `update_state`), by Clear Queue (`set_playing(False)`/`set_track(None)`), by the next `set_queue`, and by the unconditional push on every WS (re)connect — is applied field by field with only the `current_track` id gate. `duration`, `current_time`, `volume`, `is_muted`, `is_playing` are dispatched unconditionally, including when the gate has just decided the snapshot's track is stale.
- **Evidence**:
  - `playerStateSnapshot.ts:79` `dispatch(setDurationAndSyncQueue(state.duration));` -> thunk `playerQueueSync.ts` dispatches `setDuration(duration)` (which also does `state.currentTrack.duration = action.payload`, `playerSlice.ts:126-128`) and `updateTrackById({id: currentTrackId, changes:{duration}})`. After a local Next to track B, a repeat toggle writes track A's duration onto B in the player slice AND the queue copy.
  - `playerStateSnapshot.ts:87` `dispatch(setVolume(state.volume));` and `:91` `dispatch(setMuted(state.is_muted));` against `player_state.py:82-83` (`volume: int = Field(default=80...)`, `is_muted: bool = False`, only changed by REST `set_volume` which the app never calls). `usePlaybackTransport.ts` re-applies `engineGainFromPlayerState` whenever Redux volume/mute change, so the audible gain jumps back to 80 % / unmuted.
  - `playerStateSnapshot.ts:64` `dispatch(setIsPlaying(state.is_playing));` with `state_manager.py:55` `self.state.is_playing = (self.state.state == PlaybackState.PLAYING)`; WS pause (`playback_control.py:34-39`) never reaches the manager, so a paused/finished session is flipped to `isPlaying=true`.
- **Impact**: Play track, skip with Next, drag the volume to 30 %, press the repeat button: volume snaps to 80 %, the progress bar total/remaining uses the previous track's duration (also persisted into the queue row), and a paused UI shows playing. Same on every WS reconnect. No audio samples are corrupted, but visible state and output gain are wrong after an unrelated action.
- **Suggested Fix**: Backend: make the repeat route (and clear) broadcast only `repeat_mode_changed` / `queue_changed` instead of a full `player_state`, and stop treating `PlayerStateManager` as the authority for client-owned fields; or have the WS handlers and a volume path keep it current. Frontend (cheaper and safer): in `applyPlayerStateSnapshot` skip `duration`, `current_time`, `is_playing`, `volume`, `is_muted` when the #5601 stale-track gate fires, and apply volume/mute only from `volume_changed` or on cold start (no local track).

#### INT-F9-2: `player_state.shuffle_enabled` is hard-wired to False, so the next `player_state` frame un-shuffles the UI
- **Severity**: MEDIUM
- **Flow**: 9 - Queue & Playback State
- **Boundary**: Backend (PlayerState.shuffle_enabled) -> Frontend (queue slice `isShuffled`)
- **Location**: `auralis-web/backend/player_state.py:91` (never assigned anywhere; grep of `auralis-web/backend` finds only the declaration, the TypedDict and the response model) -> `auralis-web/frontend/src/hooks/player/playerStateSnapshot.ts:118-120`
- **Status**: NEW (related: #5728 is about the engine flag surviving `set_queue`, not this)
- **Description**: `QueueOrderMixin.shuffle_queue` shuffles the engine queue and sets the engine flag (`QueueController.shuffle`), then emits `queue_shuffled {is_shuffled:true}`. Nothing writes `PlayerStateManager.state.shuffle_enabled`, so every `player_state` snapshot carries `shuffle_enabled: false`. The frontend applies it unconditionally.
- **Evidence**: `player_state.py:91` `shuffle_enabled: bool = False`; `playerStateSnapshot.ts:118` `if ('shuffle_enabled' in state && state.shuffle_enabled !== undefined) { dispatch(setIsShuffled(state.shuffle_enabled)); }`; triggers listed in INT-F9-1 (repeat toggle, clear, reconnect push, next set_queue).
- **Impact**: Enable shuffle (queue really is shuffled in the engine and Redux), then press repeat or reconnect the WS: the shuffle button shows off while the queue order stays shuffled, and the next toggle sends `enabled:true` again (a no-op re-shuffle guarded by #5315) instead of restoring the order. `GET /api/player/queue` (engine flag) then disagrees with the live UI.
- **Suggested Fix**: Backend: have `shuffle_queue`/`unshuffle_queue`/`set_queue`/`clear_queue` call `player_state_manager.update_state(shuffle_enabled=...)` (or populate it from the engine at broadcast time). Frontend: do not apply `shuffle_enabled` from `player_state` once `queue_shuffled` has been seen.

### LOW (41)

#### INT-F1-6: Playback never starts when less than 96 000 samples are delivered (seek into the last ~1 s, very short tracks)
- **Severity**: LOW
- **Flow**: 1 - Track Playback
- **Boundary**: Backend short stream / seek clamp -> Frontend engine start gate
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:105-109` (seek clamped to `duration - 0.5`) -> `auralis-web/frontend/src/services/audio/audioConstants.ts:20`, `AudioPlaybackEngine.ts:117-127`, `hooks/enhancement/usePlayEnhanced.ts:145`, `useStreamMessageHandlers.ts:204-225`
- **Status**: NEW
- **Description**: The engine refuses to start (`setState('error')`, underrun callback) with fewer than `minBufferSamples = 96000` samples buffered, and the auto-start rule uses exactly that threshold. A seek to the last second is clamped by the backend to `duration - 0.5 s`, delivering 0.5 s = 44 100 interleaved samples at 44.1 kHz stereo (22 050 mono). Likewise a track shorter than ~1.09 s stereo @ 44.1 kHz. `handleStreamEnd` only calls `markStreamEnded()`; nothing relaxes the start threshold when the stream is known to be complete, so the engine is never started.
- **Evidence**: `audioConstants.ts:20 minBufferSamples: 96000`; `AudioPlaybackEngine.ts:119-127 if (availableSamples < minBufferSamples) {... setState('error') ...}`; `chunk_boundaries.py:109 pos = min(pos, max(0.0, duration - min_remainder))` (0.5 s).
- **Impact**: Clicking the progress bar in the last ~1 s (or resuming at the end) leaves the UI buffering/complete with silence; `currentTime` stays below `duration - 0.5` so auto-advance does not fire.
- **Suggested Fix**: On `audio_stream_end`/last chunk, start playback with whatever is buffered (`startPlaybackWhenBuffered` should accept `buffered >= expected remaining samples`), or derive the threshold as `min(96000, remaining_samples)` from `total_duration - seek_position`.

#### INT-F1-8: WS schema docs omit `start_position` on `play_enhanced`
- **Severity**: LOW
- **Flow**: 1 - Track Playback
- **Boundary**: Frontend `reissueActiveStreamAs`/reconnect -> Backend `WebSocketMessageType` docs
- **Location**: `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:95-101` -> `auralis-web/backend/schemas/websocket.py:44-58`
- **Status**: NEW
- **Description**: The inbound-message documentation lists `play_enhanced` data as `{track_id, preset?, intensity?, force?}` and `start_position` only on `play_normal`. The frontend sends `start_position` on both (re-issue, reconnect resume, error recovery) and `handle_play_enhanced` honors it (`playback_commands.py:251`). Docs-only gap; the `is_seek`/`seek_position`/`seek_offset`/`stream_epoch` fields of `audio_stream_start` are likewise only described in comments.
- **Evidence**: `schemas/websocket.py:44-49` vs `playback_commands.py:251` and `useOutgoingChannel.ts:95-101`.
- **Impact**: Contract drift risk for the resume path that INT-F1-2/F1-3 show is under-specified.
- **Suggested Fix**: Document `start_position` on `play_enhanced` and the resume semantics (what position, buffer behavior) next to the field.

#### INT-F2-8: Every metadata save / bulk action re-fetches all loaded track pages sequentially
- **Severity**: LOW
- **Flow**: 2 - Library Browsing
- **Boundary**: Frontend `refreshTracks` -> `GET /api/library/tracks`
- **Location**: `hooks/library/useLibraryPagination.ts:169-181`
- **Status**: NEW
- **Description**: `refreshTracks` (used after metadata edits, bulk operations, `library_updated`, scan complete) loops `while (refreshed.length < loaded && more)` issuing one request per 50 rows, strictly sequentially, each with a `COUNT(*)` and an OFFSET scan.
- **Evidence**: `useLibraryPagination.ts:169` `while (refreshed.length < loaded && more) { ... await fetchTracksPage(view, newOffset, controller.signal); ... newOffset += PAGE_LIMIT; }`.
- **Impact**: After scrolling to 5,000 loaded tracks, one title edit triggers ~100 serial GETs (O(N^2) SQL cost from OFFSET); the list stays mounted so it is background churn rather than a freeze.
- **Suggested Fix**: Refresh only the affected row(s) via `GET /api/library/tracks/{id}` (patch in place), or fetch a single page with `limit=loaded` capped at the 200 max in few calls.

#### INT-F2-10: Playlist payload carries retired/unused mastering vocabulary (`mastering_profile: 'balanced'`, `auto_master_enabled`, `normalize_levels`)
- **Severity**: LOW
- **Flow**: 2 - Library Browsing
- **Boundary**: Library model -> Backend `PlaylistResponse` -> Frontend `Playlist`
- **Location**: `auralis/library/models/playlist.py:35,77` -> `schemas/library.py:PlaylistResponse` -> `frontend/src/services/playlistService.ts:30-32`
- **Status**: NEW
- **Description**: Every playlist row defaults `mastering_profile` to `'balanced'`, a preset name that no longer exists (only `'adaptive'` does, per the preset-narrowing directive), and the value is emitted on all playlist list/detail/create responses and typed `string` on the frontend. No frontend or backend consumer reads `mastering_profile`, `auto_master_enabled` or `normalize_levels`; `UpdatePlaylistRequest` cannot change them. (`Genre.preferred_profile` has the same `'balanced'` default and a stale `# warm, bright, punchy, balanced` comment at `models/genre.py:31`.)
- **Evidence**: `playlist.py:35` `mastering_profile: Mapped[str | None] = mapped_column(String, default='balanced')`; `playlistService.ts:31` `mastering_profile: string;`; mock data in `frontend/src/test/mocks/mockData.ts` uses `'adaptive'`, so the fixtures already disagree with the live backend.
- **Impact**: Stale preset vocabulary on the wire; any future consumer that validates against `EnhancementPreset` ('adaptive') will reject real playlists.
- **Suggested Fix**: Migrate the column default/values to `'adaptive'` (or drop the dead playlist-level mastering columns from `to_dict`/`PlaylistResponse`/TS type).

#### INT-F2-11: `Track.to_dict()` and `TrackResponse` expose `recommended_reference`, a server filesystem path column (latent #3205 leak)
- **Severity**: LOW
- **Flow**: 2 - Library Browsing
- **Boundary**: Library model -> Backend response -> Frontend
- **Location**: `auralis/library/models/track.py:80,177` -> `schemas/library.py:112`
- **Status**: NEW (latent)
- **Description**: `filepath` is correctly excluded from every library payload, but `recommended_reference` is documented in the model as "Best reference track path" and is serialized in every track row of every list/detail/playlist/album response and declared in `TrackResponse`. Currently nothing writes it (only `player/integration_library.py:95` reads it), so it is always null, but the first writer would leak an absolute server path to clients on each track, contradicting #3205 and the "never send server paths" comment in `serializers.py`.
- **Evidence**: `track.py:177` `'recommended_reference': self.recommended_reference,`; `track.py:80` `# Best reference track path`.
- **Impact**: Latent path disclosure (desktop/localhost app, so low severity today).
- **Suggested Fix**: Remove it (and `processing_profile`) from `to_dict`/`TrackResponse`, or rewrite to a track id before serialization.

#### INT-F2-12: `GET /api/artists?search=` silently ignores `order_by`
- **Severity**: LOW
- **Flow**: 2 - Library Browsing
- **Boundary**: Frontend/API client -> `routers/artists.py` -> `ArtistRepository.search`
- **Location**: `routers/artists.py:93-95` -> `artist_repository.py:185,215`
- **Status**: NEW
- **Description**: The router validates `order_by in {name, album_count, track_count}` for every request but the `search` branch calls `repos.artists.search(search, limit=limit, offset=offset)` without it, and the repository hard-codes `ORDER BY name`. The tracks and albums search branches do forward `order_by`.
- **Evidence**: `artists.py:95` `artists, total = await asyncio.to_thread(repos.artists.search, search, limit=limit, offset=offset)`.
- **Impact**: `?search=x&order_by=track_count` returns name order with 200 OK; a future sort control combined with search misbehaves.
- **Suggested Fix**: Give `ArtistRepository.search` an `order_by` parameter shared with `get_all`.

#### INT-F2-13: Different "no album / no artist" sentinels across library endpoints
- **Severity**: LOW
- **Flow**: 2 - Library Browsing
- **Boundary**: Backend serializers -> Frontend transformers
- **Location**: `routers/artists.py:214-215`, `models/album.py:to_dict`, `models/track.py:to_dict`, `trackTransformer.ts:24-27`
- **Status**: NEW
- **Description**: A track with no album is `album: null, album_id: null` in track lists, `album: "Unknown Album", album_id: 0` in `/api/artists/{id}/tracks` (id 0 is not a valid id; `TrackInArtist.album_id: number` in TS), and `''` after `transformTrack`. A track with no artist is `artists: []` -> `''`, whereas an album with no artist is `"Unknown Artist"` (#5457). Also `total_tracks` means the tag-declared count in `AlbumResponse` (`Album.total_tracks`) but the actual row count in `AlbumTracksResponse` and `ArtistDetailResponse`.
- **Evidence**: `artists.py:214-215` `album=track.album.title if track.album else "Unknown Album", album_id=track.album.id if track.album else 0`; `albums.py:210` `"total_tracks": len(tracks_data)` vs `album.py:98` `'total_tracks': self.total_tracks`.
- **Impact**: Currently harmless (the artist-tracks consumer reads only `id`), but any navigation built on `album_id` would route to album 0 (404).
- **Suggested Fix**: Emit `album_id: null` and a nullable `album` in `TrackInArtist`; rename the tag count to `declared_track_count`.

#### INT-F2-14: Every track row carries full `lyrics` and `comments` text that the library UI never reads
- **Severity**: LOW
- **Flow**: 2 - Library Browsing
- **Boundary**: Backend -> Frontend (payload size)
- **Location**: `models/track.py:183-184` -> `schemas/library.py:TrackResponse.lyrics/comments` -> `trackTransformer.ts` (drops both)
- **Status**: NEW
- **Description**: `Track.to_dict()` includes `lyrics` and `comments` for every row of every list page, album-tracks response and playlist detail (an LRC file is tens of KB). The only reader of lyrics is `GET /api/library/tracks/{id}/lyrics`; `transformTrack` discards both fields.
- **Evidence**: `track.py:183` `'comments': self.comments,` / `:184` `'lyrics': self.lyrics,`.
- **Impact**: 50-row pages and whole-album/playlist responses are inflated by the largest text columns; scales payload with lyric length, not library browsing needs.
- **Suggested Fix**: Omit `lyrics`/`comments` from the list serialization (keep them on the detail/lyrics endpoint).

#### INT-F2-15: Only `search()` got an `id` tie-breaker; `get_all`/`get_favorites`/albums/playlists page with a non-unique ORDER BY
- **Severity**: LOW
- **Flow**: 2 - Library Browsing
- **Boundary**: Repository -> offset pagination
- **Location**: `track_repository_search.py:get_all/get_favorites` (`ORDER BY title|created_at|...`), `album_repository.py:130,210` (`ORDER BY title`), `artist_repository.py:145-163` (count orders), `playlist_query_mixin.py:70` (`ORDER BY name`)
- **Status**: NEW (closed #4796 fixed only `TrackRepository.search()`)
- **Description**: The #4796 comment in `search()` states that LIMIT/OFFSET without a unique key can duplicate or skip rows across pages. The same non-unique ordering remains for the favorites view (`ORDER BY title`, ties like "Intro"), the albums list (`ORDER BY title`, many albums share a title), the artists count orders, and `order_by=play_count|year|last_played` on tracks. Default `created_at` ordering on tracks is practically unique.
- **Evidence**: `track_repository_search.py` favorites `.order_by(Track.title.asc()).limit(limit).offset(offset)`; albums `.order_by(order_column.asc())`.
- **Impact**: Possible duplicate album/track keys or skipped rows at page boundaries; SQLite is usually stable for a fixed plan so this is a defence-in-depth gap.
- **Suggested Fix**: Append `, Model.id.asc()` to every paged ORDER BY.

#### INT-F3-5: Server-side look-ahead (toggle/preset/intensity prewarm and the streamlined cache worker) is fed from REST player state that WS playback never updates
- **Severity**: LOW
- **Flow**: 3, Audio Enhancement
- **Boundary**: Frontend (toggle) → Backend (`enhancement_prewarm`, `StreamlinedCacheManager`)
- **Location**: `auralis-web/backend/routers/enhancement_prewarm.py:182-205` → `auralis-web/backend/routers/enhancement_controls.py:128,203` → `auralis-web/backend/cache/manager.py:123`
- **Status**: Existing: #4760 (open, prewarm throwaway processor) and #5495 (open, dead prewarm mechanisms) cover adjacent aspects. The state-source mismatch and the worker are not covered, so it is filed NEW.
- **Description**: `_maybe_prewarm_upcoming_chunks` only fires if `player_state_manager.get_state()` has a `current_track` and `state == "playing"`, and it uses `state.current_time` as the position. The frontend plays through WS `play_*` and never calls `/api/player/play` or `/api/player/load`. The only REST path that sets that state is the artist/playlist "play" context action, via `POST /api/player/queue`, and nothing advances `current_time` afterwards. WS streaming never touches the state manager (grep of `ws_handlers/*` and `core/stream*` finds no state-manager writes). Even when the state looks "playing", the prewarm is skipped whenever a WS task exists for that track (`_track_is_live_streaming`, `:186`), which is always true for the normal stream feeding the toggle. The streamlined cache worker's only position feed is `buffer_manager.update_position(...)` from the preset/intensity handlers, using the same stale state. `cache_manager.auto_mastering_enabled` is hard-coded `True` and never tied to the runtime `enabled` flag.
- **Evidence**: `enhancement_prewarm.py:186`: `if not (state.current_track and state.state.value == "playing"): return`. `enhancement_controls.py:128` and `:203` are the only callers of `update_position(` in the backend (`rg 'update_position\('`). `cache/manager.py:123`: `self.auto_mastering_enabled: bool = True`, with no writer.
- **Impact**: Enabling enhancement mid-playback usually gets no pre-rendered chunks. The first enhanced chunk is rendered on demand after the client re-issues the stream, so there is a re-buffer gap on every toggle-on, which is the #2296 and #4425 gap this machinery was built to remove. When the worker does run, it renders chunks near a stale position for a track that may not be playing, even with enhancement off. This conclusion comes from static tracing, not a live run.
- **Suggested Fix**: Feed both from the WS stream's own position and track: the stream controller already knows the track, chunk index and settings. Or make the frontend report position on toggle. Tie `auto_mastering_enabled` to the live `enabled` flag, or remove the worker feed if the worker is vestigial.

#### INT-F3-6: Chunk cache key buckets intensity to 0.1 but the DSP renders the raw value, so an off-grid intensity is served audio rendered for a different one
- **Severity**: LOW
- **Flow**: 3, Audio Enhancement
- **Boundary**: Frontend / WS / REST (any 0-1 float) → Backend cache key vs. engine blend
- **Location**: `auralis-web/backend/core/chunk_cache_manager.py:46-48,120` → `auralis-web/backend/core/chunk_render.py:239` → `auralis-web/backend/core/audio_processing_pipeline.py:286`
- **Status**: Regression of #5474 (partial fix. Its acceptance criterion 2 is "requests differing by less than the precision never collide in a way that serves stale-setting audio"; the fix unified the key precision but did not quantize at the API boundary or at render time.)
- **Description**: `intensity_cache_key()` rounds to one decimal for the on-disk filename and the in-memory key. `ChunkedAudioProcessor.intensity` stays the raw client value, and the blend `audio*(1-i)+processed*i` uses it. `streamlined_processor_cache` renders at the bucketed value (`cache_key[2]`), while the live stream renders at the raw value. Both write to the same bucketed filename.
- **Evidence**: `chunk_cache_manager.py:48`: `return round(float(intensity), INTENSITY_KEY_DECIMALS)`. `chunked_processor.py:84`: `self.intensity = intensity`. `chunk_render.py:239`: `intensity=processor.intensity` goes to the pipeline. The REST `EnhancementIntensity` and WS `is_valid_intensity` accept any float in [0,1].
- **Impact**: Latent today, because the Settings slider steps by 0.1. A non-UI client, or a future finer control, sending 0.34 and later 0.26 gets chunks rendered at 0.34 for the 0.26 request, from disk and across restarts. The difference is at most 0.05 in the blend.
- **Suggested Fix**: Quantize intensity once at ingestion (the `EnhancementIntensity` type and `is_valid_intensity`) so the render value equals the key value. Or key on the raw intensity at full precision.

#### INT-F3-7: Frontend enhancement state starts from defaults that differ from the backend, and the initial sync can fail or be overwritten silently
- **Severity**: LOW
- **Flow**: 3, Audio Enhancement
- **Boundary**: Backend (`GET /api/player/enhancement/status`, `enhancement_settings_changed`) → Frontend (`useEnhancementStatusSync`)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/enhancementState.ts:30-35` → `auralis-web/frontend/src/hooks/enhancement/useEnhancementStatusSync.ts:77-92` → `auralis-web/backend/main.py:70-74`
- **Status**: NEW
- **Description**: `INITIAL_STATE` is `enabled:false, intensity:1.0`. The backend runtime default and the DB default for `auto_enhance` are `True`. `PlaybackSessionContext` reads that local state to choose `play_normal` or `play_enhanced`. The initial status GET failure is swallowed (`console.warn`), leaving the default in place. A GET response that arrives after a newer WS `enhancement_settings_changed` overwrites the newer state, because both write unconditionally. The WS-connect push (`ws_handlers/connection.py:133-146`) re-syncs on every (re)connect, which mitigates the reconnect case.
- **Evidence**: `enhancementState.ts:33`: `enabled: false`. `main.py:71`: `"enabled": True`. `models/settings.py` comment: auto_enhance "Default True so a fresh install keeps enhanced playback on". `useEnhancementStatusSync.ts:87-89`: `catch (err) { console.warn(...) }`.
- **Impact**: On a slow or failed first fetch, the first play-start uses normal playback while the backend and Settings say enhancement is on. The disagreement lasts until the next broadcast. The window is small and the WS-connect push usually closes it.
- **Suggested Fix**: Treat the status as unknown until the first sync (do not decide `play_normal` vs `play_enhanced` before it), or seed `INITIAL_STATE.enabled` from the single backend default. Ignore a GET response if a newer WS message has already been applied (compare `lastUpdated`).

#### INT-F4-7: Counting-phase progress is sent but never displayed ("0 files" for the whole count pass); stale scanner comment
- **Severity**: LOW
- **Flow**: 4 — Library Scanning
- **Boundary**: Engine scanner → Backend bridge → Frontend (`ScanStatusCard`)
- **Location**: `auralis/library/scanner/scan_stages.py:97-109` → `routers/library_scan_events.py:75-100` / `services/auto_scan_events.py:48-72` → `components/settings/ScanStatusCard.tsx:77-82`
- **Status**: NEW
- **Description**: #4840 added a running tally during the counting pass (`stage:'counting', total_found:N, processed:0, progress:None`). The bridges map it to `current: processed (=0)`, `total: N`, `percentage: null`, `phase:'counting'`. The card shows `current` when `percentage` is null, so it displays "0 files" with an indeterminate bar; `phase` is read into the store (`useScanProgress.ts:119`) but no component uses it, and `total` (the tally) is hidden unless percentage is non-null. `scanner.py:185` still says "The counting pass emits no frames".
- **Evidence**: `ScanStatusCard.tsx:77` `{percentage != null && total > 0 ? `${current} / ${total}` : `${current} files`}`; `scan_stages.py:103-109` `'processed': 0 … 'progress': None`.
- **Impact**: On large/slow libraries the user sees "0 files" for minutes; the honest-tally feature is invisible.
- **Suggested Fix**: In the card, when `phase === 'counting'` show `Counting… {total} files found`; fix the stale comment.

#### INT-F4-8: `GET /api/library/scan/status` resync shares the scan rate-limit prefix (2 requests / 60 s per client), so reconnect storms fail silently
- **Severity**: LOW
- **Flow**: 4 — Library Scanning
- **Boundary**: Frontend (`resyncScanStatus`) → Backend `RateLimitMiddleware`
- **Location**: `useScanProgress.ts:194-218` → `auralis-web/backend/config/middleware/rate_limit.py:53,140-190`, `config/limits.py:159-160`
- **Status**: NEW
- **Description**: The limiter matches by `path.startswith("/api/library/scan")`, so the read-only resync GET gets its own bucket of `RATE_LIMIT_SCAN_MAX=2` per 60 s. `resyncScanStatus` runs on every WS (re)connect, and its `.catch(() => {})` swallows the 429 — this is the safety net for #4821 (missed terminal frame ⇒ stuck "Scanning…").
- **Evidence**: `rate_limit.py:53` `"/api/library/scan": (RATE_LIMIT_SCAN_MAX, RATE_LIMIT_SCAN_WINDOW)`; `useScanProgress.ts:215-218` `.catch(() => { /* Best-effort resync … */ })`.
- **Impact**: On the 3rd connect within a minute (backend restart flaps, dev HMR) the resync is rejected and a stuck `isScanning` is not healed until another reconnect.
- **Suggested Fix**: Exempt the `/status` GET (match exact path for the POST bucket) or give it a separate generous limit.

#### INT-F4-9: The two progress bridges are near-duplicates and have already drifted
- **Severity**: LOW
- **Flow**: 4 — Library Scanning
- **Boundary**: Backend manual emitter ↔ auto emitter
- **Location**: `routers/library_scan_events.py:30-125` vs `services/auto_scan_events.py:23-96`
- **Status**: NEW (history: closed #2484/#4427 fixed earlier drift)
- **Description**: Same payload shape, but: `current_file` falls back to `directory` only in the auto bridge (`auto_scan_events.py:70` vs `library_scan_events.py:99`), so during counting/discovering the auto-scan shows a folder name and the manual scan shows nothing; the manual bridge uses `run_coroutine_threadsafe` and drops any exception in the returned future (no `log_task_exception`, no `suppress_errors`), the auto bridge logs failures; total/percentage logic is copied. Violates the repo's DRY rule.
- **Evidence**: see lines above.
- **Impact**: Inconsistent UI between manual and auto scans; broadcast failures in the manual path are silent.
- **Suggested Fix**: One shared bridge (loop + connection_manager + fallback dirs) used by both; keep `directory` fallback in one place.

#### INT-F4-10: `scan_progress.current_file` is the first file of the already-processed batch, absolute, and the card splits on `/` only
- **Severity**: LOW
- **Flow**: 4 — Library Scanning
- **Boundary**: Engine → Backend → Frontend
- **Location**: `auralis/library/scanner/scan_stages.py:226` → `ScanStatusCard.tsx:107`; type `types/ws/library.ts:111`
- **Status**: NEW
- **Description**: (a) `'current_file': batch[0]` is emitted *after* the 50-file batch finished, so the label names the first file of the completed batch, not a current one. (b) Absolute server paths are used verbatim; the card takes the basename with `currentFile.split('/').pop()`, which leaves the full `C:\Users\…\song.mp3` on Windows builds (the desktop target list includes Windows). (c) `ScanProgressMessage.data.current_file?: string` but the backend always sends the key, as `null` when absent (`ScanProgressPayload.current_file: str | None`, `outbound_messages.py:215`) — handled only because of `?? null` (`useScanProgress.ts:118`).
- **Impact**: Cosmetic/inaccurate status text; type does not model `null`.
- **Suggested Fix**: Send the basename (or last processed file) and type it `string | null`; split on `/[\\/]/`.

#### INT-F4-11: Settings "Scan Now" collapses every failure (409/429/504/500) into "Failed to start scan"
- **Severity**: LOW
- **Flow**: 4 — Library Scanning
- **Boundary**: Backend scan route → Frontend `useSettingsDialog`
- **Location**: `routers/library_scan.py:152-229` → `useSettingsDialog.ts:158-168`
- **Status**: NEW
- **Description**: The route returns specific details (409 "Scan already in progress", 504 timeout, 429 rate limit, 500 `handle_query_error`), and the request now stays open for the whole scan (#5643), so an error after 30 minutes is also reported as "Failed to start scan". The Library-view flow (`useLibraryScan.ts:128-134`) shows `err.detail`; Settings throws it away. A scan rejected because the auto-scanner holds the slot (visible race right after startup/resync) is thus shown as a generic failure.
- **Evidence**: `useSettingsDialog.ts:164-167` `catch (err) { console.error('Failed to trigger scan:', err); setError('Failed to start scan'); }`.
- **Impact**: Misleading message; user can't tell "already scanning" from a real fault.
- **Suggested Fix**: Share the error-to-message logic with `useLibraryScan` (`APIRequestError.detail`; treat 409 as informational).

#### INT-F5-11: Inbound limits are applied after receipt/validation: invalid and binary frames are unmetered, limiter literal duplicates the config constant
- **Severity**: LOW
- **Flow**: 5 - WebSocket Lifecycle (origin / size / rate limits)
- **Boundary**: Client -> Backend (`routers/system.py`, `websocket/websocket_security.py`)
- **Location**: `auralis-web/backend/routers/system.py:41,113-152`, `websocket/websocket_security.py:195-260`
- **Status**: NEW (the `ping` exemption is the open #5079)
- **Description**: (a) The receive loop answers binary frames (`unsupported_frame_type`) and every failed `validate_and_parse_message` (`message_too_large`, `message_too_complex`, `invalid_json`, `validation_error`) with an outbound error frame *before* `check_rate_limit`, so a client can drive unlimited request/response traffic. (b) The 64 KB cap (`WS_MAX_MESSAGE_SIZE`) is checked on the fully buffered text (`len(data.encode())`); uvicorn's own `ws_max_size` (16 MB default, not set in `main.py:124`) is the real receive bound. (c) `_rate_limiter = WebSocketRateLimiter(max_messages_per_second=10)` repeats the literal instead of `WS_MAX_MESSAGES_PER_SECOND` (the #5800 "one definition" rule) and the 3x per-IP ceiling is derived, not configurable.
- **Evidence**: `system.py:41` `WebSocketRateLimiter(max_messages_per_second=10)`; `system.py:116-122` binary branch `continue`s before :142; `websocket_security.py:218-226` size check after receipt.
- **Impact**: Loopback-only deployment, so abuse is local; hardening/consistency gap.
- **Suggested Fix**: Count every received frame (including invalid/binary) against the limiter; pass `ws_max_size=WS_MAX_MESSAGE_SIZE` to `uvicorn.run`; use the shared constant.

#### INT-F5-12: Dead WS surface: Redux `connection.wsConnected` is never written, and broadcast types/literals with no consumer remain
- **Severity**: LOW
- **Flow**: 5 - WebSocket Lifecycle (state and message inventory)
- **Boundary**: Frontend (`WebSocketContext` -> Redux) / Backend (`outbound_messages.py`)
- **Location**: `auralis-web/frontend/src/store/slices/connectionSlice.ts:48`, `hooks/shared/useConnectionRedux.ts:31`, `store/selectors/player.ts:69-81`; `backend/websocket/outbound_messages.py:23,253,261-262`, `routers/metadata_tracks.py:198`, `routers/metadata_batch.py:125`
- **Status**: NEW
- **Description**: (a) `setWSConnected` has no production caller (grep: only the hook definition and middleware allow-lists); the provider's `isConnected` never reaches Redux, so `state.connection.wsConnected` is permanently `false` and `selectPlaybackState.canPlay` (no consumer today) would always be false. `ConnectionStatusIndicator` (the only user of `connect()` and the details panel) is not mounted anywhere. (b) `track_loaded`, `metadata_updated`, `metadata_batch_updated` are broadcast but have no frontend subscriber. (c) `QueueChangeAction` still lists `"undo"` (`outbound_messages.py:23`, `types/ws/queue.ts:46`) after queue undo was retired (#5526); no emitter exists.
- **Evidence**: `grep setWSConnected` over `src/` non-test; a per-type grep of non-test `src/` (0 subscriber hits for the three types).
- **Impact**: Misleading state for the next contributor; no runtime failure.
- **Suggested Fix**: Delete the unused slice field/selector/indicator or drive it from the provider's `open`/`close`; drop the unconsumed broadcasts and the `undo` literal.
- **Merged duplicates**: INT-F9-8. Part (c) was also found by Flow 9 (INT-F9-8): `"undo"` survives in `QueueChangeAction` on both sides (`outbound_messages.py:23`, `types/ws/queue.ts:46`) and in the frontend handler after #5526 retired queue history.

#### INT-F5-13: Reconnect gives up permanently after ~3 min (prod) / 7 s (dev) with no re-trigger
- **Severity**: LOW
- **Flow**: 5 - WebSocket Lifecycle (reconnect backoff)
- **Boundary**: Frontend (`WebSocketManager`) <-> Backend availability
- **Location**: `auralis-web/frontend/src/utils/errorHandling.ts:31-36,167-193`, `hooks/websocket/useWebSocketConnection.ts:189-210`
- **Status**: NEW
- **Description**: Backoff is 1, 2, 4, 8, 16, 30, 30, 30, 30, 30 s (10 attempts, ~181 s; dev cap 3 = 7 s). On exhaustion `onMaxAttemptsExceeded` retires the singleton and sets `connectionStatus='error'`; nothing retries afterwards: there is no `online`/`visibilitychange`/focus trigger, and the only manual `connect()` caller (`ConnectionStatusIndicator`) is not mounted (INT-F5-12). A backend restart longer than the budget (dev `--reload`, slow migration at start, laptop resume with the backend still booting) leaves the UI dead until a full page reload.
- **Evidence**: `errorHandling.ts:170-174` `if (this.reconnectAttempts >= this.config.maxReconnectAttempts) { ... onMaxAttemptsExceeded?.(); return; }`; `useWebSocketConnection.ts:189` `const maxAttempts = import.meta.env.DEV ? 3 : 10;`.
- **Impact**: Requires a page reload after a long outage; dev experience worst.
- **Suggested Fix**: Keep retrying at the 30 s cap indefinitely (show 'error' status but keep the timer), and/or retry on `online`/`visibilitychange`.

#### INT-F6-7: `FingerprintGenerator._record_to_dict` uses wrong attribute names, silently producing a 23-key "25D" dict
- **Severity**: LOW
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Repository model (`TrackFingerprint`) -> Backend generator cache-hit return value
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:343,361` -> `auralis/library/models/fingerprint.py:60,68`
- **Status**: NEW
- **Description**: The cache-hit branch builds its dict from `'tempo'` and `'loudness_variation'`, but the model columns (and schema names) are `tempo_bpm` and `loudness_variation_std`. The `hasattr` guards turn the mismatch into a silent omission, so a cached fingerprint comes back without those two dimensions while a freshly generated one has all 25 keys.
- **Evidence**: `fingerprint_generator.py`: `for field in ['tempo', 'rhythm_stability', ...]` and `for field in ['dynamic_range_variation', 'loudness_variation', 'peak_consistency']`; model: `tempo_bpm`, `loudness_variation_std`.
- **Impact**: Dormant today: the only caller (`FingerprintQueue._worker_loop`, `analysis/fingerprint_queue.py:220`) checks only `result is not None`. Any future consumer would see inconsistent keys between cache hit and miss.
- **Suggested Fix**: Build the dict from `schema.DIMENSION_NAMES` (`{n: getattr(fp, n) for n in DIMENSION_NAMES}`), as the #5786 single-name-list rule requires.

#### INT-F6-8: WebSocket `fingerprint_progress` reports `queued` even when nothing was queued
- **Severity**: LOW
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Backend stream controller -> Frontend `useFingerprintStatus`
- **Location**: `auralis-web/backend/core/stream_fingerprint.py:57-98` -> `frontend/src/hooks/enhancement/useFingerprintStatus.ts:88-95`
- **Status**: NEW (sibling of closed #5518/#5267, which fixed only the REST routes)
- **Description**: When the queue singleton is absent, `enqueue()` raises, or the queue is full, the code logs at debug and still sends `status="queued"`, `message="Audio analysis queued, using standard mastering"`.
- **Evidence**: `stream_fingerprint.py:57-76`: `if queue: added = await asyncio.to_thread(queue.enqueue, track_id) ... else: logger.debug("Fingerprint queue not available")`, followed unconditionally by `_send_fingerprint_progress(..., status="queued", ...)`.
- **Impact**: The UI shows a calm "queued" message for a track that will never be analysed (queue disabled or full).
- **Suggested Fix**: Send `failed`/`error` (both in the FE union) when the queue is missing or rejected the track; keep `queued` only when `added` is True or `queue.is_queued(track_id)`.

#### INT-F6-9: `enqueue-all` mislabels queue-full drops as "already queued", and the UI discards the response
- **Severity**: LOW
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Backend router -> Frontend coverage hook
- **Location**: `routers/fingerprint_queue.py:162-190` -> `frontend/src/hooks/library/useFingerprintCoverage.ts:104-113`
- **Status**: NEW
- **Description**: `FingerprintQueue.enqueue` returns False for already-queued, currently-processing and queue-full (`MAX_QUEUE_SIZE = 5000`). The router counts all as `skipped` ("Tracks already queued or processing") and computes `pending_after = pending - enqueued_count`. The FE does `await response.json()` and drops the body.
- **Evidence**: `fingerprint_queue.py:166-171`: `if queue.enqueue(track.id): enqueued += 1 else: skipped += 1`; `analysis/fingerprint_queue.py:104-110` (full-queue drop returns False); `useFingerprintCoverage.ts:110`: `await response.json();`.
- **Impact**: On libraries over 5000 pending tracks "Analyse remaining" silently enqueues only the first 5000 and the rest is reported as "already queued".
- **Suggested Fix**: Return a distinct `dropped_queue_full` count and surface `message` in the card, or drain in chunks.

#### INT-F6-10: The same fingerprint-coverage data is exposed under two sets of field names
- **Severity**: LOW
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Backend routers -> Frontend (one consumer)
- **Location**: `routers/fingerprint_status.py:37-45` vs `routers/fingerprint_queue_models.py:52-62`
- **Status**: NEW (#3217 was closed as "different concepts", but both routes serialise the same `get_fingerprint_stats()` dict)
- **Description**: `GET /api/library/fingerprints/status` returns `fingerprinted_tracks`, `pending_tracks`; `GET /api/similarity/fingerprint-stats` returns `fingerprinted`, `pending` (both carry `total_tracks`, `progress_percent`). Only the first has a frontend consumer.
- **Evidence**: `fingerprint_status.py:84-90` vs `fingerprint_queue.py:236-252`, both fed by `repos.fingerprints.get_fingerprint_stats`.
- **Impact**: A client written against one endpoint breaks on the other; doubles the surface for INT-F6-4.
- **Suggested Fix**: Remove the unused `fingerprint-stats` route or reuse `FingerprintingStatusResponse`.

#### INT-F6-11: The pre-computed K-NN graph path is dead in the product (never built automatically, and the UI's `limit=20` exceeds the default `k=10`)
- **Severity**: LOW
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Frontend request -> backend graph fast-path
- **Location**: `frontend/src/components/shared/SimilarTracksModal/SimilarTracksModal.tsx:60` + `hooks/fingerprint/useSimilarTracks.ts:131-133` -> `routers/similarity_query.py:55-105`
- **Status**: NEW
- **Description**: `build_graph` is called only from the manual `POST /graph/build` route; no startup, scan or frontend path builds the graph (INT-F6-3 makes it unreachable on small libraries anyway). The modal sends `use_graph=true&limit=20`; even a manually built graph with the default `k=10` gives `len(neighbors) (10) < limit (20)` and falls back to real-time. Each `/similar` request therefore pays one extra DB round trip and then recomputes.
- **Evidence**: A search of `build_graph`/`graph/build` over `auralis` and `auralis-web` (non-test) finds only the router and the engine definition; `SimilarTracksModal.tsx`: `limit = 20`; `similarity_query.py:79`: `if len(neighbors) >= limit:`.
- **Impact**: Wasted query per request; the graph feature and the `use_graph` flag / cache-key dimension give no benefit.
- **Suggested Fix**: Either build the graph after auto-fit/scan with `k >= 20`, or drop the graph path and the `use_graph` parameter.

#### INT-F6-12: Similarity "match %" is not calibrated: unrelated tracks score roughly 55-70%
- **Severity**: LOW
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Engine score -> Frontend percent display
- **Location**: `auralis/analysis/fingerprint/distance.py:225-236` -> `frontend/src/components/shared/SimilarTracksModal/SimilarTrackRow.tsx:117,124`
- **Status**: NEW
- **Description**: `similarity_score = 1 - distance` with `max_distance = 1.0`. Distance is a weighted RMS (weights sum to 1) over `[0,1]`-normalised dimensions, so 1.0 needs every dimension at opposite extremes. For independent uniform dimensions E[d^2] = 1/6, d about 0.41, so unrelated tracks display about "59% match" (estimate; real data is clamped to the 5th/95th percentile range). The returned range is 0-1 as documented and the FE multiplies by 100 once; the issue is the meaning of the displayed percent.
- **Evidence**: `distance.py`: `normalized_distance = MetricUtils.normalize_to_range(distance, max_distance, clip=True); similarity = 1.0 - normalized_distance` with default `max_distance: float = 1.0`; `SimilarTrackRow.tsx:117`: `{(track.similarityScore * 100).toFixed(0)}% match`.
- **Impact**: Percentages cluster in a narrow high band, so rank 1 and rank 20 look almost identical.
- **Suggested Fix**: Rescale by an empirically measured typical maximum (for example the 95th-percentile pairwise distance stored at fit time), or show rank only.

#### INT-F6-13: "Queued" / "initialising" similarity states say "try again" but the modal offers no retry and never re-fetches
- **Severity**: LOW
- **Flow**: 6 - Fingerprint & Similarity
- **Boundary**: Backend transient 404/503 -> Frontend modal
- **Location**: `routers/similarity_common.py:73-93,148-197` -> `frontend/src/components/shared/SimilarTracksModal/SimilarTracksModal.tsx:70-83,121-139`, `hooks/fingerprint/similarityErrorState.ts:62-109`
- **Status**: NEW
- **Description**: `classifySimilarityError` returns `retryable: true` for the queued, queue-rejected and initialising states, but the modal ignores `retryable`, has no retry control, and its effect depends only on `[open, trackId, limit, ...]`. The "initialising" hint ("This finishes shortly after startup") is also false when the auto-fit was skipped for a small library or fingerprints arrived after startup: the system is never refit (open #5716), so the 503 persists until restart.
- **Evidence**: `SimilarTracksModal.tsx:70-83` effect deps; `:121-139` renders only `title`/`hint`; `similarityErrorState.ts` hint text for `initialising`.
- **Impact**: The user must close and reopen the modal to retry; on fresh installs the hint misleads.
- **Suggested Fix**: Auto-retry with bounded backoff while `errorState.transient`, or add a "Try again" button wired to `findSimilar`; change the 503 copy once refit (#5716) exists.

#### INT-F7-4: `AlbumInArtist` carries no `artwork_url`, so the artist view probes `/artwork` for every album and 404s for the ones without art
- **Severity**: LOW
- **Flow**: 7 Artwork
- **Boundary**: Backend (artist detail schema) → Frontend (AlbumsTab)
- **Location**: `auralis-web/backend/routers/artists_models.py:60-66` → `auralis-web/frontend/src/components/library/Views/AlbumsTab.tsx:104-110`
- **Status**: NEW
- **Description**: The artist detail response's nested album model drops `artwork_url` (the frontend type `AlbumInArtistApiResponse` documents this at `api/transformers/types.ts:131`). The frontend works around it by passing `hasArtwork` unconditionally, so each album card requests a thumbnail and relies on `onError` to fall back. Albums without art therefore generate one backend request each, which hits the full-graph query of INT-F7-3 and returns a 404 JSON body, plus a console network error.
- **Evidence**: `artists_models.py:60-66`: fields are `id, title, year, track_count, total_duration` only. `AlbumsTab.tsx:104-110`: `// AlbumInArtist (backend) carries no artwork flag … hasArtwork`
- **Impact**: Noisy 404s and wasted queries on the artist page; no functional breakage.
- **Suggested Fix**: Add `artwork_url: str | None` to `AlbumInArtist` (derive it from `album.artwork_path`, the same `/api/albums/{id}/artwork` form), add it to the TS type/transformer, and drive `hasArtwork` from it.

#### INT-F7-5: MusicBrainz artist "image" relations are Wikimedia file *pages*, not image URLs, yet they are stored and rendered as `<img src>`
- **Severity**: LOW
- **Flow**: 7 Artwork
- **Boundary**: Engine (`ArtworkService`) → Backend/Frontend (`Artist.artwork_url` → `ArtistHeader <img>`)
- **Location**: `auralis/services/artwork_service.py:203-213` → `auralis/utils/artwork_security.py:9-19` → `auralis-web/frontend/src/components/library/Details/ArtistHeader.tsx:54`
- **Status**: NEW (#4526/#4936 covered CSP and host validation, not the URL's content type)
- **Description**: For each MusicBrainz url-rel of `type == 'image'`, the service accepts the first `resource` whose host passes `validate_artwork_url`. `commons.wikimedia.org` is on the allowlist, and MusicBrainz image relations commonly point at `https://commons.wikimedia.org/wiki/File:….jpg`, an HTML page. The host check passes, the URL is persisted, `Artist.to_dict()` emits it, and the browser receives `text/html` for an `<img>`. There is no check on the response type, nor a resolution to `upload.wikimedia.org` (Special:FilePath). `ArtistHeader` then drops to the placeholder via `onError` (#5520), so the failure is silent.
- **Evidence**: `artwork_service.py:203-209`: `if relation.get('type') == 'image': … image_url = url_data.get('resource') … _validated_artwork_result(image_url, "musicbrainz")`. `artwork_security.py:15-18` allowlist includes `"commons.wikimedia.org"`.
- **Impact**: Artist artwork sourced from MusicBrainz shows the placeholder for those artists. It is reachable only via the CLI `auralis/cli/fetch_artwork.py` (no backend path calls `fetch_artist_artwork`), so the blast radius is small.
- **Suggested Fix**: Resolve `commons.wikimedia.org/wiki/File:X` to `https://commons.wikimedia.org/wiki/Special:FilePath/X?width=600` (which redirects to `upload.wikimedia.org`, already trusted by the redirect-validating opener), or reject non-image URLs by extension/HEAD Content-Type before persisting.

#### INT-F7-6: Thumbnail re-encode drops JPEG EXIF orientation and ICC profile, so a thumbnail can differ from the full-size image
- **Severity**: LOW
- **Flow**: 7 Artwork
- **Boundary**: Backend thumbnail cache → Frontend `<img>`
- **Location**: `auralis-web/backend/routers/artwork_thumbnails.py:99-117` (`image.thumbnail(...)`, `out_image.save(handle, format=pil_fmt)`); same pattern in `auralis/utils/artwork_security.py:bound_artwork_dimensions`
- **Status**: NEW
- **Description**: `Image.save(handle, format="JPEG")` is called without `exif=`/`icc_profile=`. I verified with Pillow in the project venv that a JPEG with EXIF orientation 6 and an ICC profile comes out of `thumbnail()` + `save()` with neither. Browsers honour EXIF orientation on the original, so a folder-photo cover with orientation 6 shows rotated in the full-size surface (player bar, INT-F7-2) and unrotated in the thumbnail grids (or the reverse). Wide-gamut JPEGs also lose their profile and render with shifted colors in thumbnails only.
- **Evidence**: `artwork_thumbnails.py:117`: `out_image.save(handle, format=pil_fmt)`. Check output: `src exif orient 6 icc True` → `thumb exif orient None icc False`.
- **Impact**: Cosmetic inconsistency for a minority of covers (camera-originated folder images).
- **Suggested Fix**: Apply `ImageOps.exif_transpose(image)` before `thumbnail()`, and pass `icc_profile=image.info.get("icc_profile")` for JPEG/WEBP. Do the same in `bound_artwork_dimensions` so stored originals are normalized.

#### INT-F7-7: `getArtworkUrl` bakes an absolute `http://localhost:8765` origin in production while the other builders emit same-origin paths
- **Severity**: LOW
- **Flow**: 7 Artwork
- **Boundary**: Frontend URL builders → Backend CSP (`img-src 'self'`)
- **Location**: `auralis-web/frontend/src/services/artworkService.ts:38-43` vs `:52-75`; `auralis-web/frontend/src/config/api.ts:15`; `auralis-web/backend/config/middleware/security_headers.py:112`
- **Status**: NEW
- **Description**: In a production build `API_BASE_URL` is `http://localhost:8765`, so `getArtworkUrl` (AlbumArt, AlbumCard, palette) returns absolute `http://localhost:8765/api/...`. `withArtworkSize` (TrackRow/TrackCard) and the raw `artworkUrl` in `TrackDisplay` are root-relative. The backend explicitly supports the SPA being opened as `127.0.0.1` (`origins.py`/`hosts.py` emit both spellings, and the server binds 127.0.0.1). From a `http://127.0.0.1:8765` page, the absolute ones are cross-origin and are blocked by `img-src 'self' data: blob: …`, while the relative ones load. The Electron shell loads `http://localhost:8765` (`desktop/main.js:419`), so the shipped app is unaffected.
- **Evidence**: `artworkService.ts:42`: ``return `${API_BASE_URL}/api/albums/${albumId}/artwork${…}` `` vs `:68`: `if (!url.startsWith('/api/')) return url;` (returns relative).
- **Impact**: Only for browser use at the 127.0.0.1 origin: album grid/detail art is blocked while list thumbnails load.
- **Suggested Fix**: Emit root-relative `/api/albums/...` from `getArtworkUrl` (images do not need a base URL when the SPA is served by the backend; the Vite proxy covers dev), or apply the same prefix policy to all builders.

#### INT-F7-8: Extraction picks the first picture regardless of type and ignores webp/uppercase-extension folder art
- **Severity**: LOW
- **Flow**: 7 Artwork
- **Boundary**: Audio files/library → Engine extractor
- **Location**: `auralis/library/artwork_tags.py:30-33,61-64`; `auralis/library/artwork.py:127-143`
- **Status**: NEW
- **Description**: `_extract_from_id3` returns the first `APIC*` frame, and `_extract_from_flac` returns `pictures[0]`, without preferring picture type 3 (front cover) over back cover, artist photo, etc. Files that list a booklet/back picture first yield that as the album art. `_find_folder_artwork` only tries a fixed list of `.jpg/.jpeg/.png` names with limited case variants (`Cover.JPG`, `cover.webp`, `Folder.JPG` are missed on case-sensitive filesystems). ASF/WMA `WM/Picture` and WavPack/APE tags are not read.
- **Evidence**: `artwork_tags.py:31-33`: `if key.startswith('APIC'): apic = tags[key]; return apic.data, apic.mime`. `artwork_tags.py:63`: `picture = audio_file.pictures[0]  # Get first picture`.
- **Impact**: Wrong or missing covers for some libraries; no crash.
- **Suggested Fix**: Select the picture with `type == 3` (fall back to the first), and match folder art case-insensitively over `{folder,cover,front,albumart*}.{jpg,jpeg,png,webp}` via a directory listing.

#### INT-F8-5: A seek-start chunk is rendered without level smoothing and persisted under the sequential cache key
- **Severity**: LOW
- **Flow**: 8 - Seek & Rebuffer
- **Boundary**: Backend level continuity (`LevelManager`) -> on-disk chunk cache (`ChunkPathCache`)
- **Location**: `auralis-web/backend/core/level_manager.py:169-175` (baseline when history empty) + `core/chunk_streaming.py:133-145` (write under `track/signature/preset/intensity/targets/chunk` key) -> `core/chunk_path_cache.py:98-113` (disk hit)
- **Status**: NEW
- **Description**: Every seek builds a fresh `ChunkedAudioProcessor` (and `LevelManager`) so the first rendered chunk N has empty history and takes the "establish baseline" branch: no gain correction against chunk N-1, which the listener correctly never hears. That unsmoothed WAV is then stored under the same position-independent cache key a sequential play-through uses. On a later sequential playback, chunk N is a cache hit; `_record_cache_hit_level` only records its RMS and never re-smooths (#4669 comments say so explicitly), so the 1.5 dB boundary limiter that chunk N would have received after chunk N-1 is skipped and the N-1/N seam can step by the full natural level difference. Output of a chunk therefore depends on whether the user previously scrubbed to it.
- **Evidence**: `level_manager.py:169`: `# First chunk or no history: establish baseline` -> `return chunk, 0.0, False`; `chunk_streaming.py:133`: `chunk_path = processor._wav_encoder.encode_and_save_from_path(audio=extracted_chunk, ... chunk_index=chunk_index, ...)`; `chunk_render.py` remembers `(rms, gain_db=0.0)` for that key.
- **Impact**: Non-deterministic level step (bounded by the music's chunk-to-chunk RMS difference) at one chunk seam after a prior seek landed exactly there; no sample loss.
- **Suggested Fix**: Do not persist (or mark as "context-free") a chunk rendered with empty level history that is not chunk 0, or key it with its smoothing context; alternatively apply the cache-hit smoothing at read time when the previous chunk's recorded level is known.

#### INT-F8-6: `start_chunk` is documented as the client's progress-numerator offset but is never consumed - buffered range is wrong after a seek
- **Severity**: LOW
- **Flow**: 8 - Seek & Rebuffer
- **Boundary**: Backend (`audio_stream_start.start_chunk`, `total_chunks` = full track) -> Frontend (progress/buffer indicator)
- **Location**: `auralis-web/backend/core/stream_normal.py:197-211` and `core/stream_seek.py:177-193` (send `start_chunk` + full-track `total_chunks`, #3768) -> `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:96-99` / `components/player/Player.tsx:80`
- **Status**: NEW
- **Description**: The backend deliberately sends the full-track `total_chunks` and a `start_chunk` "so the client can offset the numerator". The frontend never reads `start_chunk` (only the type declaration mentions it), resets `processedChunks = 0` on the seek start, and the progress bar's buffered range is `processedChunks / totalChunks * 100`, drawn from the left edge. After seeking to 80% of a track the buffered bar shows 0% growing to 20% instead of the real 80-100% range, and `streamingProgress` reaches only (remaining/total) before `complete`.
- **Evidence**: `Player.tsx:80`: `const wsBufferedPercentage = totalChunks > 0 ? (processedChunks / totalChunks) * 100 : 0;`; `useEnhancedStreamStart.ts:98`: `core.streamingMetadataRef.current.processedChunks = 0;`; `grep start_chunk` in `frontend/src` (non-test) finds only `types/ws/streaming.ts:57`.
- **Impact**: Cosmetic/state mismatch (buffer indicator after any forward seek); no audio effect.
- **Suggested Fix**: Seed `processedChunks` with `start_chunk` on seek starts (and use it for the buffered-range start), or stop sending the field and the misleading comment.
- **Merged duplicates**: INT-F1-7. Found independently by Flows 1 and 8. Flow 1 adds that `total_chunks` is in 15 s units for normal streams and 10 s units for enhanced, so the denominator also changes when the enhancement toggle switches stream type.

#### INT-F8-7: Normal-path seek reports the raw requested position, not the clamped one actually delivered; seek to 0 is not flagged `is_seek`
- **Severity**: LOW
- **Flow**: 8 - Seek & Rebuffer
- **Boundary**: Backend normal stream -> Frontend
- **Location**: `auralis-web/backend/core/stream_normal.py:187-191` vs `core/chunk_boundaries.py:180-198 normal_stream_plan`
- **Status**: NEW
- **Description**: `normal_stream_plan` clamps the start to `duration - SEEK_MIN_CHUNK_REMAINDER` (#5409) and trims accordingly, but `stream_normal` builds `seek_kwargs = {"seek_position": start_position, ...}` from the unclamped argument. The enhanced path reports `effective_position` for exactly this reason (#4557/#5254). Separately, the whole seek block is under `if start_position > 0`, so a normal-path seek to 0 is sent as a plain stream start (enhanced always sets `is_seek`), which makes the client take the full engine/buffer rebuild branch instead of the resume branch.
- **Evidence**: `stream_normal.py:187-191`: `if start_position > 0: seek_kwargs = {"start_chunk": start_chunk, "seek_position": start_position, "seek_offset": seek_offset}`; `chunk_boundaries.py:180`: `pos = min(max(0.0, float(start_position)), max(0.0, duration - SEEK_MIN_CHUNK_REMAINDER))`.
- **Impact**: Once INT-F8-1 is fixed (client adopts `seek_position`), a normal-mode seek to the last 0.5 s or past the end would set the clock to the request (potentially beyond `duration`) while audio starts at `duration-0.5`. Today the discrepancy is masked by INT-F8-1.
- **Suggested Fix**: Return the clamped `pos` from `normal_stream_plan` (`NormalStreamPlan.effective_position`) and report it; set `is_seek` whenever the stream was started by a seek/resume command, including position 0.

#### INT-F9-3: `set_queue` applies `start_index` to the id-filtered list and has no upper bound, so a dropped id shifts the start track and an out-of-range index silently plays nothing
- **Severity**: LOW
- **Flow**: 9 - Queue & Playback State
- **Boundary**: Frontend (`useQueueMutations.setQueue` / `queueService.setQueue`: `start_index` relative to the sent id list) -> Backend (`queue_set_mixin._set_queue_impl`)
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:98-111` -> `auralis-web/backend/services/queue_set_mixin.py:70,129`
- **Status**: NEW
- **Description**: `start_index` is validated only `ge=0` (`QueueIndex`). The service drops ids missing from the library (`db_tracks = [by_id[tid] for tid in track_ids if tid in by_id]`) and then uses the same numeric `start_index` against `db_tracks`.
- **Evidence**: `queue_set_mixin.py:70` filter; `:129` `if start_index >= 0 and start_index < len(db_tracks):` guards `set_track`/`load_file`/`play`; `QueueController.set_queue` clamps the engine pointer (`queue_loading.py`: `min(start_index, track_count - 1)`); `state_manager.py:set_queue` stores `queue_index=start_index` unclamped and `current_track=None` when out of range. The route still answers `{"message": "Queue set successfully", "start_index": start_index}`.
- **Impact**: (a) Frontend sends `[10,20,30]`, `start_index=1`; id 10 was removed by a scan: engine/state manager start at 30, not 20. (b) `start_index >= len(db_tracks)`: nothing is loaded or played, the engine pointer points to the last track, the manager broadcasts `current_track=None` (the frontend then runs `setCurrentTrack(null)` over a playing track) and the REST call reports success. Needs a stale/deleted id or a bad index, hence LOW.
- **Suggested Fix**: Map `start_index` through the filter (index of `track_ids[start_index]` in `db_tracks`, else 0), reject `start_index >= len(track_ids)` with `InvalidRequest`, and return the effective index.

#### INT-F9-4: `GET /api/player/queue` drops unresolvable entries without re-basing `current_index` / `track_count`, unlike the `queue_changed` broadcast
- **Severity**: LOW
- **Flow**: 9 - Queue & Playback State
- **Boundary**: Backend (QueueService.get_queue_info) -> Frontend (`useQueueFetch`)
- **Location**: `auralis-web/backend/services/queue_service.py:74-81` vs `auralis-web/backend/services/queue_service_base.py:186-198` -> `auralis-web/frontend/src/hooks/player/useQueueFetch.ts:56-58`
- **Status**: NEW
- **Description**: The broadcast path keeps `resolved` position-for-position and re-bases `current_index` over dropped entries (#5455). The read path calls `enrich_tracks` (which silently filters `None`) and returns the engine's raw `current_index` and `track_count`.
- **Evidence**: `queue_service.py:75` `tracks = await self._enricher.enrich_tracks(info.get("tracks", []))` while `info["current_index"]`/`["track_count"]` stay engine values; frontend `useQueueFetch.ts:57` `dispatch(reduxSetCurrentIndex(response.current_index ?? 0))` with no `reconcileQueueIndex`.
- **Impact**: If a queued track vanished from the library (rescan), the initial/remounted fetch highlights the wrong row and `track_count` exceeds `tracks.length`. The same fetch also applies the raw engine index without the #5601 reconciliation, so any remount of a `usePlaybackQueue()` consumer (e.g. after an error-boundary reset) after local skips jumps the highlight back to the engine's stale slot.
- **Suggested Fix**: Share the re-basing logic (return `resolve_tracks` positions and derive index/count from them) between `get_queue_info` and `_broadcast_queue_changed`; run `useQueueFetch` through `reconcileQueueIndex` when a local track exists.

#### INT-F9-5: `queue_changed` has no sequence or generation, and the broadcast phase runs outside the engine lock, so two quick edits can land out of order and leave a stale queue
- **Severity**: LOW
- **Flow**: 9 - Queue & Playback State
- **Boundary**: Backend (concurrent `_broadcast_queue_changed` calls) -> Frontend (`useQueueSubscription` applies each frame wholesale)
- **Location**: `auralis-web/backend/services/queue_service_base.py:141-208` (read at 160, hydrate at 178, send at 208; lock released before, per #4825) -> `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:57-81`
- **Status**: NEW
- **Description**: Each mutator leaves `_queue_mutation()` and then does `to_thread(get_queue_info)` -> `resolve_tracks` (a library `get_by_paths` lookup for every appended track, because the state-manager filepath map is never refreshed after edits) -> `broadcast_typed`. A second mutation can run between request A's read (state S1) and A's send; if B's hydrate finishes first, B sends S2 and A then sends S1. `QueueChangedPayload` has no `seq` (unlike `player_state`, `track_changed`, `playback_*`), so the frontend cannot drop the older frame.
- **Evidence**: `queue_service_base.py:162` `info = await asyncio.to_thread(queue_obj.get_queue_info)`; `:178` `resolved = await self._enricher.resolve_tracks(...)`; `outbound_messages.py` `QueueChangedPayload` fields: `action, tracks, current_index, track_id, position, index, queue_size, from_index, to_index`, no `seq`. Frontend `useQueueSubscription.ts:57` does `reduxSetQueue(mappedTracks)` unconditionally.
- **Impact**: Rapid back-to-back remove/move/add (double-click delete, drag then delete) can end with Redux showing the pre-second-edit queue until the next broadcast; a subsequent index-based DELETE/move then targets the wrong row. Window is narrow, hence LOW.
- **Suggested Fix**: Stamp `queue_changed` with a monotonic `seq` taken inside `_queue_mutation()` (same pattern as `_TrackChangeSequencer`) and track a queue watermark in `useQueueSubscription`; or serialise the read+broadcast of `_broadcast_queue_changed` behind a dedicated broadcast lock.

#### INT-F9-6: Unshuffle after any intervening edit reports "No shuffle to undo" but leaves the engine `shuffle_enabled` flag True, which `GET /queue` then re-asserts
- **Severity**: LOW
- **Flow**: 9 - Queue & Playback State
- **Boundary**: Backend (QueueService.unshuffle_queue / QueueController) -> Frontend (`toggleShuffle` optimistic state, `useQueueFetch`)
- **Location**: `auralis-web/backend/services/queue_order_mixin.py:199-203`, `auralis/player/queue_controller.py:252-258`, `auralis/player/components/queue_shuffle.py` (`_invalidate_shuffle_snapshot_unlocked`) -> `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:213-234`, `useQueueFetch.ts:59`
- **Status**: NEW (neighbours: #5728, #5564)
- **Description**: Every queue-shape mutator (add, insert, remove, clear, reorder, move) drops the pre-shuffle snapshot. `QueueController.unshuffle` clears `shuffle_enabled` only `if restored`; `shuffle()` on a queue of <=1 tracks sets the flag without taking a snapshot at all. The REST route answers 200 with a message and no broadcast, while the frontend has already flipped `isShuffled` to false optimistically (the request did not fail, so there is no rollback).
- **Evidence**: `queue_order_mixin.py:199` `if not queue_manager.unshuffle(): return {"message": "No shuffle to undo", ...}`; `queue_controller.py:254-256` `restored = self.queue.unshuffle(); if restored: self.shuffle_enabled = False`; `QueueController.shuffle` (`:222-231`) sets `self.shuffle_enabled = True` unconditionally.
- **Impact**: Shuffle, drag one row (or add a track), switch shuffle off: UI off, engine flag stays True, and the next app load (or any `GET /api/player/queue`) shows shuffle on over an order that cannot be restored. The user also gets no feedback that the original order is gone.
- **Suggested Fix**: In `unshuffle_queue`, when nothing is restorable still clear the flag (and broadcast `queue_shuffled {is_shuffled:false}`); make `QueueController.unshuffle` set `shuffle_enabled=False` regardless of `restored`.

#### INT-F9-7: Engine queue pointer never follows frontend navigation, so shuffle pinning and remove-current handling anchor on a stale track
- **Severity**: LOW
- **Flow**: 9 - Queue & Playback State
- **Boundary**: Frontend (client-only Next/Previous/auto-advance) -> Engine (`QueueManager.current_index`)
- **Location**: `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:116-170` -> `auralis/player/components/queue_shuffle.py:58-72`, `auralis-web/backend/services/queue_edit_mixin.py:202-215`
- **Status**: NEW (the display half is mitigated by #5601; the engine half is untracked)
- **Description**: `handleNext`/`handlePrevious` only dispatch Redux + start a WS stream (`startTrackForSettings`); `/api/player/next|previous|jump` have no frontend callers and the WS `play_*` handlers never move the engine pointer. The engine therefore keeps pointing at the first track of the last `set_queue`. Backend queue operations decide "current" from that pointer.
- **Evidence**: `queue_shuffle.py:58` `current_track_id = current_track.get('id') ...` then swaps *that* track to index 0 (and, for `set_queue`-built filepath-only entries, `id` is None so nothing is pinned, #5564); `queue_edit_mixin.py:202` `success, was_current = queue_manager.remove_if_index_matches_current(index)` followed by `self.audio_player.load_file(file_path)` / `playback.stop` when `was_current`.
- **Impact**: With playlist `[A,B,C]` started on A and skipped to C: Shuffle pins A (not the playing C) at the front, so the playing track lands mid-queue and Previous leaves the expected neighbourhood; deleting row A makes the engine `load_file(B)` (or stop) although C is playing, while deleting the playing row C does nothing on the engine. Redux survives via `reconcileQueueIndex`, but the engine's loaded file and "current" semantics diverge from what plays.
- **Suggested Fix**: Report the frontend's playing queue index on `play_normal`/`play_enhanced` (or a small `PUT /api/player/queue/current`) and have the queue service move `QueueManager.current_index` (plus `follow_navigation`) there; alternatively make shuffle/remove use the frontend-supplied playing index.

#### INT-F9-9: Artist "Add to queue" still issues one request per track, each triggering a whole-queue enriched broadcast
- **Severity**: LOW
- **Flow**: 9 - Queue & Playback State
- **Boundary**: Frontend -> Backend
- **Location**: `auralis-web/frontend/src/components/library/Items/artists/useContextMenuActions.ts:77-83` -> `auralis-web/backend/services/queue_edit_mixin.py:67-75`
- **Status**: NEW (the bulk-selection path was moved to `/add-tracks` by #5651; this caller was not)
- **Description**: `for (const track of response.tracks) { await addTrackToQueue(track.id); }` sends N sequential `POST /queue/add-track`; each one re-hydrates and broadcasts the whole queue (`_broadcast_queue_changed`), so the traffic is O(N^2) in tracks.
- **Impact**: An artist with a few hundred tracks produces hundreds of full-queue frames and DB lookups; partial failure leaves a partial queue. Correctness of order is preserved (sequential).
- **Suggested Fix**: Call `addTracksToQueue(trackIds)` like `useBatchOperations.ts` does.
- **Merged duplicates**: INT-F2-9. Found independently by Flows 2 and 9 (artist "Add to queue" path left behind by #5651).

## Relationships

- **Seek/resume contract (INT-F8-1, INT-F1-1, INT-F1-3, INT-F8-6, INT-F8-7, INT-F1-6).** All six come from one under-specified `is_seek` contract in `useEnhancedStreamStart.ts`. One fix should give each case its own explicit handling:
  - *seek*: reset the buffer, adopt `seek_position` as the clock offset, and drop frames until the new epoch;
  - *re-issue/reconnect*: either resume from the buffered end and keep the buffer, or resume from the playhead and reset.
  INT-F8-7 (the normal path reports an unclamped `seek_position`) is masked until INT-F8-1 is fixed. INT-F1-8 (WS docs omit `start_position` on `play_enhanced`) is the documentation side.
- **Flow control and the rate limiter (INT-F5-1, INT-F5-6, INT-F1-4).** These share one gap: control frames are fire-and-forget, uncorrelated and can be rate-limited away. A level-based or periodic `buffer_ready`, a bounded `flow_evt.wait()`, and correlated error frames would fix all three.
- **`lastStreamCommand` never cleared (INT-F3-4, merged INT-F5-10) and INT-F3-1.** These are the two sides of one rule: the client owns pause/stop and never tells the backend. A stale re-issue after stop is the first; a missing re-issue after a Settings change is the second. A single "apply enhancement change" helper used by both the toggle and the Settings save would fix INT-F3-1 and INT-F3-2 together.
- **State manager authority (INT-F9-1, INT-F9-2, INT-F5-3, INT-F5-5; open #5460, #5726).** `PlayerStateManager` is broadcast as authoritative for fields only the browser owns. Decide which side owns each field before patching individual symptoms.
- **Build-time localhost origins (INT-F5-8, INT-F7-7).** Both derive `ws://`/`http://localhost:8765` from build constants instead of `window.location` in production. One fix in `config/api.ts` covers both.
- **Artwork staleness (INT-F7-1, INT-F7-2, INT-F7-4).** These share the missing `artwork_url` / version token on some payloads and the sticky error flag. INT-F7-3 (whole album graph loaded per artwork GET) is a performance sibling of INT-F2-6 and INT-F2-7 (over-hydration on artist/album endpoints).
- **Fingerprint coverage semantics (INT-F6-4, INT-F6-10, INT-F6-2, INT-F6-3; open #5716).** "Fingerprinted / outdated / fitted" means different things in the stats, similarity and fit layers.
- **Scan event bridges (INT-F4-3, INT-F4-4, INT-F4-9, INT-F4-7, INT-F4-10).** All five come from the two near-duplicate progress bridges (`library_scan_events.py` and `auto_scan_events.py`) plus an un-keyed frame stream. Consolidating the bridges first makes the rest small.

## Prioritized Fix Order

1. **INT-F8-1 + INT-F1-1 + INT-F1-3**: one `useEnhancedStreamStart` / `useEnhancedSeek` change. These are core playback correctness bugs: wrong clock after every seek, dead auto-advance, stale or repeated audio. Two of them are regressions of closed issues, so add the missing tests too: stale frames *before* the new start, and the guard path plus the offset.
2. **INT-F5-1**: resume flow control from the playback side and bound `flow_evt.wait()`. This truncates long tracks silently. Fix it together with INT-F5-6 (exempt flow-control frames, correlate errors, coalesce keyboard seeks).
3. **INT-F3-1, then INT-F3-2 and INT-F3-4**: route Settings enhancement changes through the same re-issue path as the toggle, and clear `lastStreamCommand` on stop and end.
4. **INT-F4-1**: register (and persist) manually scanned folders, so imported tracks can actually be played.
5. **INT-F2-1, then INT-F2-2 and INT-F2-5**: server-side search, sort and refresh for large libraries.
6. **INT-F9-1, INT-F9-2, INT-F5-3, INT-F5-5**: decide what `player_state` is allowed to overwrite.
7. **Remaining MEDIUM**, by blast radius: INT-F4-5 (moved files lose playlists and favorites; data loss for user curation), INT-F8-4 (leaked temp WAVs), INT-F3-3 (one bad PUT bricks Settings), INT-F5-4 / INT-F5-8 (connection failures), then the fingerprint and artwork MEDIUMs.
8. **LOW**: opportunistically, grouped by the relationships above.

## Existing Open Issues Confirmed (not re-reported)

| Issue | Flow | Still reproduces? |
|---|---|---|
| #5709 | 1 | Yes — `audio_stream_start.channels` = probed native count while FFmpeg-routed >2 ch files decode as stereo |
| #5649 | 1 | Yes — un-timed REST fetch / queue POST gate play start |
| #5558 | 1, 8 | Yes — `LevelManager` boosts after the limiter with no peak ceiling |
| #5701 | 8 | Yes — per-chunk gain seam behaviour |
| #5076 | 1 | Yes — `handle_play_normal` never records `active_stream_settings` |
| #5258 | 8 | Yes — no single-flight dedup of concurrent renders of the same chunk key (duplicated DSP after seek) |
| #5823 | 2, 9 | Yes — `has_more`/`hasMore` twins; `queue_changed` `currentIndex` fallback is dead |
| #5077 | 5 | Yes — heartbeat loop exits permanently on one failed ping send |
| #5079 | 5 | Yes — `ping` exempt from the rate limit, each costs a `pong` |
| #4760, #5495 | 3 | Yes — throwaway prewarm processor; dead prewarm mechanisms (INT-F3-5 adds the state-source mismatch) |
| #5567, #5594, #5500, #5719, #5748, #5755 | 4 | Yes — scanner ingestion/skip/typing/change-detection issues |
| #5716, #5715, #5381, #5747, #5368, #5718, #5390 | 6 | Yes — normalizer fit gate, prefilter order, 500 on DB lock, graph paging, factory bypass, blob migration, sync lookup on loop |
| #5751, #5069 | 7 | Yes — artwork dir defined twice; artwork download not rate-limited |
| #5460 | 9 | Yes — queue edits never update `PlayerStateManager.state`; reconnect restores the pre-edit queue |
| #5563, #5564, #5726, #5727, #5728, #5686, #5651 | 9 | Yes — engine `file_path` key mismatch, shuffle by id, stale current_track, add on empty queue, shuffle flag survives set_queue, duplicate count helpers, artist bulk-add path |

**Possibly stale open issues** (for triage, not findings):
- **#5271** (seeded intensity not range-guarded): `helpers.seed_enhancement_settings` now range-guards via `is_valid_intensity`.
- **#5189** (queue reorder unreachable or duplicates the track): does not reproduce on the queue path; playlist reorder was not examined.

## Next Step

```
/audit-publish docs/audits/AUDIT_INTEGRATION_2026-10-22.md
```
