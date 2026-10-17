# Frontend Audit — 2026-10-16

**Scope**: `auralis-web/frontend/` (components, Redux, hooks, types, design system, API client, performance, accessibility, tests). Static audit by nine parallel dimension agents; `type-check:prod` was run by the Type Safety agent and passes. No vitest runs were made, and nothing was profiled at runtime, so runtime-behaviour claims (marked in the findings) come from code reading.
**Depth**: deep. **Limit**: none. **Dedup baseline**: 200 most recent GitHub issues (open + closed, #5339 and up), `.claude/issues/`, and `docs/audits/AUDIT_FRONTEND_*.md` (latest 2026-09-13). Older closed issues were checked against the local snapshots and prior reports rather than `gh`.

## Executive Summary

| Severity | Count |
|----------|------:|
| CRITICAL | 0 |
| HIGH | 10 |
| MEDIUM | 38 |
| LOW | 40 |
| **Total (unique)** | **88** |

93 raw findings from the nine dimensions collapse to 88 after merging cross-dimension duplicates (CMP-01 absorbs RDX-05; RDX-03 absorbs TS-02, TS-03 and API-11; RDX-06 absorbs TS-06). Five of the 88 are `Existing` open issues already tracked (CMP-09 in part, TS-07, TS-09, API-12, TST-04) and need no new issue; `/audit-publish` will dedupe them. All others are NEW.

| Dimension | Findings |
|-----------|---------:|
| 1 Component Quality (CMP) | 16 |
| 2 Redux State (RDX) | 9 (RDX-05 merged into CMP-01) |
| 3 Hook Correctness (HK) | 11 |
| 4 Type Safety (TS) | 7 |
| 5 Design System (DS) | 5 |
| 6 API Client (API) | 11 |
| 7 Performance (PERF) | 7 |
| 8 Accessibility (A11Y) | 11 |
| 9 Test Coverage (TST) | 11 |

No CRITICAL findings: no XSS path, no dropped audio frames, no state corruption that crashes the app.

### Key themes

1. **Actions that look successful but never reach the backend.** The library/artist context menus change only the Redux queue and still show success toasts (CMP-01); skips move only the frontend index and are then overwritten by stale backend snapshots (RDX-02); the playlist fetchers turn errors into "No playlists yet" (API-02); `useRestAPI` discards successful mutations as "stale" (HK-05) and swallows its own timeout as an unmount abort (HK-06). The common root is that the frontend keeps a second, optimistic copy of queue/playback state and has no reconciliation or error path.
2. **Wire-shape drift at the Redux boundary.** Raw snake_case payloads enter the camelCase store from `queue_changed`, the REST track fetch and `getPlaylist` (RDX-03, a sibling gap of the closed #5009 mapper), and the types claim otherwise (TS-04, TS-07).
3. **Playback-session lifecycle bugs.** After `audio_stream_end` the session state is `'complete'`, so Space/Play restarts the track instead of pausing (HK-02); auto-advance ignores repeat mode (HK-04); seek re-masters with stale preset settings (HK-03); persisted volume/mute never reach a new engine (RDX-04); the AudioWorklet feeder runs ~1.8x real time into an uncapped queue (PERF-01).
4. **Reconnect logic is broken and untested.** `WebSocketManager` schedules every failed reconnect twice (HK-01, spot-checked: both `onclose` and the connect `.catch` call `attemptReconnect`), and no spec exercises the real class (TST-01).
5. **Global keyboard shortcuts collide with focused widgets** (A11Y-01, A11Y-03, A11Y-02) — a seek-bar ArrowRight also skips the track; Space blocks button activation; "/" cannot be typed in a text field.
6. **Theming debt.** Dark-only tokens paired with theme-aware text are unreadable in light mode (DS-01, A11Y-10). `src/index.css` has not been loaded since 2025-11 yet still has parity tests reading it (DS-02).
7. **Test-suite honesty.** The baseline ratchet has no test-count floor and CI runs with `|| true` (TST-07); 9 `vi.mock` targets do not exist, one of which probably explains LibraryEmptyState's 19 baseline entries (TST-06); many error assertions are vacuous (TST-03).

### Most impactful issues

HK-01 (reconnect storm/give-up), HK-02 (Space restarts the track), RDX-01 (duplicate track loops Next), CMP-01 (context-menu queue actions lie), API-01 (Scan Now aborts the scan), PERF-01 (unbounded worklet queue), A11Y-01 (shortcuts hijack focused widgets).

## Relationships and Shared Root Causes

- **Queue-state duplication (RDX-01, RDX-02, CMP-01, HK-04, HK-08, API-06)**: the frontend owns an independent queue/index and mutates it optimistically. RDX-01 (index resolved by track id), RDX-02 (backend snapshots overwrite local index), CMP-01 (menu actions never call the backend) and API-06 (bulk adds race) all trace to this. Fixing it once — make the backend queue authoritative and have local actions go through `useQueueMutations`/`usePlayTrack` — closes most of the cluster.
- **Unmapped wire payloads (RDX-03 ⊇ TS-02/TS-03/API-11, TS-04, TS-07)**: one mapper at each ingress (WS `queue_changed`, REST track, playlist) removes the class; TS-04's generics then become checkable.
- **`useRestAPI` / transport (HK-05, HK-06, API-04, API-05, API-07, API-08)**: all in the same two files (`hooks/api/useRestAPI.ts`, `utils/apiRequest.ts`). Fix together; API-01 (30 s timeout aborting the scan) is the same timeout machinery.
- **Playback session (HK-02, HK-03, HK-04, RDX-04, PERF-01, PERF-05, CMP-06)**: PERF-05 (100 MB zero-fill on every seek) amplifies CMP-06 (seek on every mousemove). Fixing CMP-06 first removes most of PERF-05's user-visible cost.
- **WebSocket manager (HK-01, HK-09, TS-08, TST-01)**: TST-01 is why HK-01 survived; add the test with the fix.
- **Keyboard (A11Y-01, A11Y-02, A11Y-03)**: one listener (`services/keyboardShortcutsService.ts`) plus the row handlers.
- **Light theme (DS-01, A11Y-10, DS-04)**: token pairing; DS-04's dead palette is the likely source of the mismatched `palette.info`.
- **Dead code (CMP-09, CMP-10, RDX-07, RDX-08, DS-02, DS-04)**: orphaned components cost no bundle bytes (PERF agent checked `dist/`), but they generate false audit/test assurance — notably the `?raw` CSS parity tests (DS-02, TST cross-ref).
- **Test gaps (TST-01, TST-02)** pin nothing for HK-01, HK-02, HK-04, RDX-01, CMP-04: write regression tests alongside those fixes.

## Prioritized Fix Order

1. **HK-01** WebSocketManager double reconnect (+ TST-01 spec). Small fix, app-wide effect: today a transient outage can leave the app permanently disconnected.
2. **HK-02** Play/pause after stream completion (+ TST-02 spec). Core control, one-condition fix.
3. **RDX-01 / RDX-02 / CMP-01** queue authority cluster. Do together: key the sync by queue position, route menu actions through the backend mutations, drop local-only skip drift.
4. **API-01** Scan Now timeout, and **HK-05/HK-06** `useRestAPI` stale/timeout semantics (shared machinery), then **API-02** (errors → `[]`).
5. **A11Y-01** gate the global shortcut listener (`defaultPrevented`, widget roles, open modal), which also resolves A11Y-02/03 in part.
6. **PERF-01** cap the AudioWorklet feed (+ PERF-05); verify the two out-of-dimension worklet observations listed in the appendix (pause/resume position, last 5 s not fed) before closing.
7. **RDX-03** single ingress mapper; then TS-04/TS-05 typing.
8. **HK-03 / HK-04 / RDX-04** session correctness (preset on seek, repeat mode, volume restore).
9. **TST-07 / TST-06** harden the baseline ratchet and fix dead `vi.mock` targets (may shrink the baseline).
10. MEDIUM UX items (CMP-02..08, API-03..06, A11Y-04..06, DS-01, PERF-02..04), then LOW cleanups.

---

# Findings

## High Findings (10)

### CMP-01: Context-menu "Add to Queue" (track and artist) and artist "Play All" mutate only the Redux queue; the engine never hears about it
- **Severity**: HIGH
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/useTrackContextMenu.ts:85-109`, `auralis-web/frontend/src/components/library/Items/artists/useContextMenuActions.ts:44-112`, `auralis-web/frontend/src/hooks/shared/useQueueRedux.ts:48-51`
- **Status**: NEW (the 2026-07-12 audit only fixed the toast ordering in `handleAddToQueue`; it never noticed the missing backend call)
- **Description**: `useQueue()` from `useQueueRedux.ts` is a plain `dispatch(queueSlice.addTracks/setQueue/clearQueue)`. No REST call, no WS message. The Redux queue is only a mirror: `useQueueSubscription` overwrites it on every `queue_changed`, and the engine queue is authoritative (see the queue dataflow split). The correct paths already exist and are used elsewhere: `useBatchOperations.handleBulkAddToQueue` does `post(ENDPOINTS.QUEUE_ADD_TRACK)`, and `usePlaybackQueue().addTrack/setQueue` does optimistic Redux plus REST with rollback.
  - Track row / album-table row context menu "Add to Queue" calls `queue.addMany([queueTrack])`, then toasts `Added "<title>" to queue`.
  - Artist menu "Add to Queue" calls `queue.addMany(tracks)`, then toasts `Added <artist> to queue`.
  - Artist menu "Play All" does `queue.clear(); queue.setQueue(tracks); player.play()`. `player.play()` is only `setIsPlaying(true)`, a Redux flag. It starts no stream. It cannot start playback if nothing is streaming, and if something is streaming it just resumes the old track.
- **Evidence**:
  ```ts
  // useTrackContextMenu.ts:97
  queue.addMany([queueTrack]);
  success(`Added "${track.title}" to queue`);
  // useContextMenuActions.ts:58-62
  queue.clear();
  queue.setQueue(tracks);
  // Start playback
  player.play();
  ```
- **Impact**: The user gets a success toast but the engine queue is unchanged, so the track is never played. For "Play All", the queue panel shows the artist's tracks while the engine still holds the old queue. Index-based panel actions (remove, reorder) then target the wrong engine entry until the next `queue_changed` snaps Redux back. This is a silent no-op on a core action with a false success message.
- **Siblings**: `TrackTableRowItem.tsx` (album and artist-detail tables) reuses `useTrackContextMenu`. `ArtistListContent` / `ArtistListItem` reuse `useContextMenuActions`.
- **Suggested Fix**: Route these through `usePlaybackQueue().addTrack/setQueue` (or the `QUEUE_ADD_TRACK` POST that `useBatchOperations` uses). For "Play All", use `usePlayTrack` after the backend `setQueue` so a stream actually starts. Delete the Redux-only `useQueue().add/addMany/setQueue/clear` surface so it cannot be misused again.
- **Merged from RDX-05** (MEDIUM, Library context menus mutate the Redux queue and `isPlaying` locally and never tell the backend): ``auralis-web/frontend/src/components/library/Items/artists/useContextMenuActions.ts:56-66`, `:96`; `auralis-web/frontend/src/components/library/Items/tracks/useTrackContextMenu.ts:86-102`; `auralis-web/frontend/src/hooks/shared/usePlayerRedux.ts:41-65`, `auralis-web/frontend/src/hooks/shared/useQueu` — These production paths (`CozyArtistList` via `LibraryViewRouter`, `TrackRow`, `TrackTableRowItem`) call the Redux-only `useQueue().clear/setQueue/addMany` and `usePlayerActions().play`. Those wrappers dispatch bare slice actions. The real queue mutations POST to `/api/player/queue*` (`useQueueMutations`, `useAppDragDrop`). The artist "Play all" does `queue.clear(); queue.setQueue(tracks); player.play();`. `player.play()` is only `setIsPlaying(true)`: it starts no stream, and `startTrack` is never called.

### RDX-01: `setCurrentTrackAndSyncQueue` resolves the queue index by track id, so duplicate queue entries trap next/previous and auto-advance
- **Severity**: HIGH
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerQueueSync.ts:36-49`, callers `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:127-156`, `:224-231`
- **Status**: NEW
- **Description**: The thunk takes only a track object and recomputes `queue.currentIndex` with `findIndex((t) => t.id === track.id)`, which always returns the FIRST matching slot. `handleNext`/`handlePrevious` already know the exact target index (`currentQueueIndex ± 1`) and throw it away by passing `queueTracks[nextIndex]`. The queue legitimately holds the same track more than once: `useTrackContextMenu.handleAddToQueue` appends without a dedupe, and `/api/player/queue/add-track` has no dedupe either. `queueSlice.updateTrackById` documents duplicates as legitimate ("the same track can legitimately sit in the queue more than once").
- **Evidence**:
  ```ts
  // playerQueueSync.ts
  dispatch(setCurrentTrack(track));
  ...
  const idx = queue.tracks.findIndex((t) => t.id === track.id);
  if (idx >= 0) dispatch(setCurrentIndex(idx));
  // PlaybackSessionContext.tsx
  const nextIndex = currentQueueIndex + 1;
  const nextTrackData = queueTracks[nextIndex];
  dispatch(setCurrentTrackAndSyncQueue(nextTrackData));
  ```
  Queue `[A, B, A, C]`: at index 1 (B), Next plays the A at index 2, but the thunk writes `currentIndex = 0`. The next Next goes to index 1 (B), then back to A, and so on. C is unreachable.
- **Impact**: With a duplicate in the queue, manual Next is stuck in a loop. The auto-advance effect uses the same wrong index (`hasMoreTracks = currentQueueIndex < length - 1`), so natural track-end advance loops over the same tracks, or ends early when the first copy sits at the tail. Previous/Next navigation lands on the wrong position. `useEnhancedPlayCommand:106` has the same ambiguity, because it only knows an id (the user clicked a library row).
- **Siblings**: `usePlayerStateSync.ts:296-300` (`track_changed`) is correct because it uses the index from the payload. `usePlayerActions().setTrack` bypasses the thunk entirely (Existing: #5361).
- **Suggested Fix**: Give the thunk an optional explicit `index` argument (`setCurrentTrackAndSyncQueue(track, index?)`). `handleNext`/`handlePrevious` pass the index they computed. When no index is given, prefer the match nearest `queue.currentIndex` over the first match.

### HK-01: WebSocketManager schedules every failed reconnect twice, exhausting the retry budget early and leaking duplicate live sockets
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/utils/errorHandling.ts:67-129` (also `:134-144`, `:196-210`); budget set at `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:188-211`
- **Status**: NEW (adjacent to open #5469, which is about close codes, not this)
- **Description**: `connect()` rejects its promise from `ws.onerror`, and `ws.onclose` calls `attemptReconnect()`. For the first connection that is harmless, because the caller just logs. For every retry started from `attemptReconnect()`, the `.catch()` ALSO calls `attemptReconnect()`. A refused connection fires `error` then `close`, so each failed retry schedules two timers and bumps `reconnectAttempts` twice. Consequences:
  1. The attempt budget is consumed about twice as fast as configured. In dev (`maxAttempts = 3`) the manager gives up after roughly one real retry (~3 s). In prod (10) it gives up in tens of seconds instead of ~3 minutes.
  2. `this.reconnectTimeout` holds only the last timer, so `close()` cannot cancel the earlier ones. They fire later and open sockets on a manager the app already retired.
  3. Several retries run concurrently. Each `connect()` overwrites `this.ws`, orphaning the previous socket with its handlers still attached. If the backend comes back while two or more are pending, all of them open. Every orphan keeps feeding `onMessage` (duplicate dispatch of every broadcast) and fires `onOpen`, so `replayQueueAndResume` runs once per socket, re-sending the stream-resume command.
  4. `startHeartbeat()` is called on every open without clearing the previous interval, and `stopHeartbeat()` clears only the last one, so intervals leak.
  5. After `onMaxAttemptsExceeded` the singleton is retired (`closeCurrentManager`) but `wsManagerRef.current` still points at the dead manager. `send()` then queues forever, and nothing ever calls `connect()` again. The app is permanently offline until reload.
- **Evidence**:
  ```ts
  this.ws.onerror = (error) => { this.onError?.(error); reject(error); };   // :82
  this.ws.onclose = () => { this.stopHeartbeat(); this.onClose?.(); this.attemptReconnect(); }; // :92
  ...
  this.reconnectTimeout = setTimeout(() => {
    this.connect().catch(err => { this.attemptReconnect(); });               // :123-127  (2nd scheduler)
  }, delay);
  ```
  Simulation with a fake `WebSocket` that fires `error` then `close` on refusal. With `maxReconnectAttempts=3`: attempts 1, 2, 3 were consumed after one real retry cycle, and `onMaxAttemptsExceeded` fired 4 times. With `maxReconnectAttempts=10` and the server coming up after 300 ms: 10 attempts burned in 300 ms (6 sockets created), then 5 sockets were open at once and `onOpen` fired 5 times.
- **Impact**: After a backend restart (routine in `--dev`, and after any crash), the UI stops reconnecting within seconds (dev) or tens of seconds (prod) and stays dead: no player_state, no library_updated, no audio resume. When a reconnect does land during the overlap, the UI gets duplicate message dispatch and a duplicated stream re-issue, which restarts the stream twice.
- **Siblings**: none (single transport class).
- **Suggested Fix**: Make `attemptReconnect()` idempotent (return if `this.reconnectTimeout` is already pending, and null it when it fires), and drop the `.catch(... attemptReconnect())` in the timer, since `onclose` already drives retries. In `connect()` detach handlers from the previous `this.ws` before replacing it, clear any existing heartbeat in `startHeartbeat()`, and have `close()` set a `closed` flag that `attemptReconnect()` and the timer honour.

### HK-02: Play/pause (button and Space) restarts the track once the stream has finished delivering, instead of pausing
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:163-187` (decision), `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:214-215` (`isStreaming` definition), `auralis-web/frontend/src/components/player/Player.tsx:152` (consumer)
- **Status**: NEW
- **Description**: `isStreaming` is `streamingState.state === 'streaming' || 'buffering'`. When the backend sends `audio_stream_end` with `reason: 'completed'`, `handleStreamEnd` dispatches `completeStreaming`, which sets the state to `'complete'`. The backend does not pace delivery to real time. It sends chunks as fast as they render, and the client buffer holds ~5 minutes (100 MB), so for most tracks delivery completes long before playback does. For the rest of the track (the whole tail the user is listening to) `isStreaming` is `false` while audio is audibly playing. In that state:
  - `Player` passes `isPlaying={isStreaming && !isPaused}` = false, so the transport shows a Play icon during playback.
  - `handlePlayPause` takes the `else` branch (`!isStreaming`) and calls `startTrackForSettings(currentTrack.id)`, which stops and restarts the track from 0:00. It never reaches `pausePlayback()`.
  The `Player.tsx` stall comment ("the buffer draining after a completed stream") and the auto-advance logic both rely on `'complete'` persisting during playback, so the state is real, but the play/pause logic was never taught about it. `PlaybackSessionContext.transport.test.tsx` has no `handlePlayPause` case with `streamingState: 'complete'`.
- **Evidence**:
  ```ts
  // usePlayEnhanced.ts
  isStreaming: streamingState.state === 'streaming' || streamingState.state === 'buffering',
  // PlaybackSessionContext.tsx
  if (isStreaming) { isPaused ? resumePlayback() : pausePlayback(); }
  else { await startTrackForSettings(currentTrack.id); }   // reached while 'complete' but still playing
  // Player.tsx
  isPlaying={isStreaming && !isPaused}
  ```
- **Impact**: For any track whose rendering finishes before it stops playing (the common case), pausing after the delivery window restarts the song from the beginning and re-triggers rendering/fingerprint work. The play/pause icon is wrong for most of the track. The global Space shortcut has the same effect.
- **Siblings**: `useAudioVisualization.ts:131-137` derives activity from `streamingState === 'streaming'` too, so it also treats the `'complete'` tail as inactive, but it falls back to Redux `isPlaying` there.
- **Suggested Fix**: Derive "session active" from the engine, not the delivery state. For example expose `isPlaybackActive` (engine exists and has not ended, or `streamingState !== 'idle'`) and use it in `handlePlayPause` and `Player`. Treat `'complete'` as a still-playing state until the engine's playhead reaches the track end.

### API-01: Settings "Scan Now" inherits the 30 s default timeout; the abort now kills the scan server-side and reports "Failed to start scan"
- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/settingsService.ts:166-168`; caller `auralis-web/frontend/src/components/settings/useSettingsDialog.ts:149-158`; backend `auralis-web/backend/routers/library_scan.py:84-129` (`_await_scan` / `ScanClientGone`)
- **Status**: NEW (the symptom was reported as INT-08 in `docs/audits/AUDIT_INTEGRATION_2026-08-13.md`; I found no GitHub issue for it and the code is unchanged. Severity is higher than that report's MEDIUM because #4820 later made a client disconnect stop the scanner thread.)
- **Description**: `POST /api/library/scan` is a synchronous, long-lived request (backend timeout 3600 s). `useLibraryScan` knows this and passes `timeoutMs: SCAN_TIMEOUT_MS` (3,660,000). `settingsService.triggerLibraryScan` goes through the same `post()` with no `timeoutMs`, so `apiRequest` applies `DEFAULT_TIMEOUT_MS = 30000`. After 30 s `fetchWithTimeout` aborts the fetch; the browser closes the connection; the backend's disconnect watcher raises `ScanClientGone` and calls `stop_scanner`. The settings dialog then sets the generic `'Failed to start scan'`.
- **Evidence**:
  ```ts
  // settingsService.ts
  export async function triggerLibraryScan(directories: string[]): Promise<void> {
    await post(ENDPOINTS.LIBRARY_SCAN, { directories, recursive: true, skip_existing: true });  // no timeoutMs, no signal
  }
  // useSettingsDialog.ts
  } catch (err) { console.error('Failed to trigger scan:', err); setError('Failed to start scan'); }
  ```
  ```ts
  // useLibraryScan.ts (the correct sibling)
  post<ScanSummary>('/api/library/scan', {...}, { signal: controller.signal, timeoutMs: SCAN_TIMEOUT_MS })
  ```
- **Impact**: Any Settings "Scan Now" on a library that takes more than 30 s (essentially every first import) is cancelled mid-scan: the import stops partway and the user sees a "failed to start" error although the scan did start. Retrying while the scanner is still unwinding can also hit a 409 "scan in progress". The auto-scan path is unaffected.
- **Siblings**: No other call site pairs a long server operation with the default timeout, but nothing in the transport marks a call as long-running, so this is easy to repeat.
- **Suggested Fix**: Pass the scan timeout from one shared constant (move `SCAN_TIMEOUT_MS` out of `hooks/library/useLibraryScan.ts` into `config/api.ts` or `utils/apiRequest.ts` so the service layer can import it) and wire an unmount `AbortController` like `useLibraryScan`. Better: make the endpoint return immediately and let the existing WS/`scan/status` channel report completion.

### API-02: Playlist list fetchers turn every failure into an empty list, so the UI says "No playlists yet"
- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/playlist/usePlaylistData.ts:5-13, 34-47`; `auralis-web/frontend/src/components/library/Items/tracks/useTrackContextMenu.ts:48-58`; `auralis-web/frontend/src/components/library/Controls/AddToPlaylistMenu.tsx:37-47`
- **Status**: NEW
- **Description**: `fetchPlaylists()` catches every error from `playlistService.getPlaylists()` (network failure, timeout, 5xx, a guard failure on any page of the aggregated pages) and returns `[]`. `refresh()` then does `setPlaylists([])`, replacing a list that had loaded successfully. Nothing records an error, so `PlaylistListContent` takes its `playlists.length === 0` branch and shows "No playlists yet". `refresh` is wired to the WS `playlist_created`, `playlist_updated` and `playlists_refresh` events, so a single failed refetch wipes the sidebar. `useTrackContextMenu.fetchPlaylists` and `AddToPlaylistMenu` swallow the same way (`console.error` / `setPlaylists([])`), so the "Add to playlist" submenu looks empty rather than failed.
- **Evidence**:
  ```ts
  const fetchPlaylists = async () => {
    try { const response = await playlistService.getPlaylists(); return response.playlists; }
    catch (fetchError) { console.error('Failed to load playlists:', fetchError); return []; }
  };
  const refresh = useCallback(async () => {
    const loaded = await fetchPlaylists();
    if (!isMountedRef.current) return;
    setPlaylists(loaded);            // [] on failure -> existing list erased
  }, []);
  ```
- **Impact**: After a transient failure (a slow backend during a scan can hit the 30 s timeout) the user sees all their playlists disappear with no error, and may conclude they were deleted or create a duplicate. The state only heals on the next successful refresh.
- **Siblings**: the three sites above.
- **Suggested Fix**: Let `fetchPlaylists` rethrow; keep the previous `playlists` on refresh failure and expose an `error` (toast or inline) from `usePlaylistData`. The two menus should show "Couldn't load playlists" instead of the empty state.

### PERF-01: AudioWorklet feeder outruns real time ~1.8x into an unbounded worklet queue, so the water marks and backend flow control never see the real lookahead
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/services/audio/BufferScheduler.ts:201-223,231-256,124-135`; `auralis-web/frontend/public/audio-worklet-processor.js:28-35,51-56`; `auralis-web/frontend/src/services/audio/audioConstants.ts:18,26-30`; `auralis-web/frontend/src/hooks/enhancement/audioChunkIngest.ts:30-33,171`
- **Status**: NEW
- **Description**: Worklet mode is the live path in Electron (see the #4623 note in `BufferScheduler.ts`). `startFeeding()` runs every `feedIntervalMs = 50` and moves `bufferSize * channels` = 4096 frames per tick from the `PCMStreamBuffer` ring to the worklet via `postMessage`. That is 81,920 frames/s against 44,100 or 48,000 frames/s of playback, so about 1.7-1.86x real time. The worklet appends every block to `this._buffers` with no cap and no ack or credit protocol. The only gate on the feeder is `checkBufferHealth()`, and it looks at the ring alone (pause below 5 s, resume above 8 s). Everything the feeder moves out of the ring is invisible to both the water marks and the backend flow control, which also reads only ring fill (`buffer_full` at 75%, `audioChunkIngest.ts:171`). The ring therefore stays near the 5 s floor while the worklet accumulates the track.
  While the ring holds more than 5 s and the backend delivers at least 1.86x real time, the worklet queue grows by about 0.86 s of PCM per wall-clock second. It peaks at about 46% of the track length (T/1.86 of wall time at 0.86x growth). At 48 kHz stereo float32 that is about 40 MB for a 4-minute track and about 640 MB for a 1-hour mix or audiobook. The data sits in the AudioWorkletGlobalScope, so it does not show up in main-thread heap snapshots.
  `disconnectProcessor()` posts `{command:'clear'}` and drops the node. This runs on every pause, because `pausePlayback()` calls it, and on every seek and stop. Whatever lookahead the worklet held is discarded, while the ring has already advanced past it.
- **Evidence**:
  ```ts
  // BufferScheduler.ts:204-221  (bufferSize=4096, feedIntervalMs=50 -> 4096 frames / 50 ms)
  const feedChunkSize = this.bufferSize * channels;
  this.feedInterval = setInterval(() => {
    ...
    const bufferedSeconds = available / (sampleRate * bufferChannels);   // ring only
    if (!this.checkBufferHealth(bufferedSeconds, 'feed')) return;
    const samples = this.buffer.read(feedChunkSize);
    if (samples.length > 0) this.workletNode!.port.postMessage({ samples });
  }, PLAYBACK_ENGINE_CONFIG.feedIntervalMs);
  ```
  ```js
  // audio-worklet-processor.js:32-35  no bound on _buffers
  if (data.samples) {
    this._buffers.push(new Float32Array(data.samples));
    this._available += data.samples.length;
  }
  ```
  ```ts
  // BufferScheduler.ts:124-129  runs on pause, seek and stop
  disconnectProcessor(): void {
    this.stopFeeding();
    if (this.workletNode) { this.workletNode.port.postMessage({ command: 'clear' }); ...
  ```
- **Impact**:
  1. Memory in the audio path grows with track length (tens of MB typical, hundreds of MB for long-form audio) and is held until stop. The 100 MB ring and the "flow control at 75%" design give a false sense of a bounded buffer.
  2. The user-visible effect of 'clear' on pause. The ring has already advanced past the discarded audio, so resume continues from the ring and skips whatever the worklet held. Adjacent observations from reading `AudioPlaybackEngine`/`PlaybackPositionTracker` (see "Out-of-dimension observations") suggest this also resets the displayed position.
  3. The `onStallChange`/`playbackStalled` signal added in #5461 is driven by the ring level, not by what the worklet can actually play. It can report a stall while seconds of audio are queued.
  Confidence: high on the pacing arithmetic, which is plain from the constants. It has not been confirmed at runtime.
- **Siblings**: ScriptProcessor fallback (`handleAudioProcess`) pulls on demand and does not share the problem.
- **Suggested Fix**: Make the worklet the consumer in a pull or credit model. Have it report `available` in every `samplesPlayed` message, which it already includes but nobody reads, and feed only while `workletAvailable < targetLookahead` (about 2-3 s). Alternatively, give the worklet a bounded ring of its own and drop the main-thread feed interval. Also stop using 'clear' as the pause mechanism: suspend output (gain 0 or `AudioContext.suspend()`) or keep the node and flag it inactive.

### A11Y-01: The global shortcut listener fires on keys that focused widgets own, so arrow keys and Space double-act or hijack the focused control
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/services/keyboardShortcutsService.ts:167-188`; shortcut table at `auralis-web/frontend/src/ComfortableApp.tsx:85-215` (Space `:87`, ArrowRight/Left `:102-120`, ArrowUp/Down `:121-141`)
- **Status**: NEW
- **Description**: The service installs one `window` `keydown` listener. Its only guard is `isInputElement()`, which skips `input`/`textarea`/`select`/contenteditable. It does not check `event.defaultPrevented`, the focused element's role (`slider`, `button`, `option`, `tab`, `menuitem`, `listitem`), or whether a modal dialog is open. `useKeyboardShortcuts` never calls `disable()` either. It calls `preventDefault()` on every match. Shortcuts are unmodified single keys: Space = play/pause, ArrowRight/Left = next/previous track, ArrowUp/Down = volume +/-10, `m` = mute, `1`-`4` = view switch.
  - React handlers run first, but React's `preventDefault()` does not stop propagation. So a widget's own handling still reaches `window`, and the global handler fires as well.
  - Seek slider: `useProgressBarInteraction.handleKeyDown` handles ArrowLeft/Right (seek +/-1s), then the same keydown reaches the window listener and calls `nextTrack()` / `previousTrack()`. One ArrowRight press on the focused seek bar seeks and skips the track. ArrowUp/Down on it also changes volume by 10 and toasts.
  - Space on any focused `button`, MUI tab, menu item, or dialog button (Save, Cancel, Remove, Next, sidebar items): the global handler calls `preventDefault()` on the Space keydown, which cancels the browser's button activation, then toggles playback. Keyboard users cannot activate a focused button with Space anywhere in the app, and pressing it plays or pauses audio. `input` elements are exempt (so MUI Switch/Checkbox still work); real `<button>`s, `role=tab`, `role=menuitem` are not.
  - Arrow keys inside the library listbox (`TrackListViewContent.handleListboxKeyDown`), MUI Tabs in Settings, MUI Menus (context menu, batch menus) and the queue list move focus or selection and then ALSO change volume or skip a track.
  - Modal dialogs (Settings, Edit Metadata, Similar Tracks, Clear Queue, Reset Library confirmation) leave all shortcuts live, so Space/arrows/`m`/`1`-`4` act on the player and the view behind the modal.
- **Evidence**:
  ```ts
  // keyboardShortcutsService.ts:167-187
  private handleKeyDown = (event: KeyboardEvent): void => {
    if (!this.enabled) return;
    const isSearchKey = event.key === '/' && ...;
    if (!isSearchKey && this.isInputElement(event.target)) return;   // only input/textarea/select
    const shortcut = this.shortcuts.get(key);
    if (shortcut) { event.preventDefault(); shortcut.handler(); }    // no defaultPrevented / role / dialog check
  };
  // useProgressBarInteraction.ts: ArrowRight -> event.preventDefault(); onSeek(currentTime + 1)
  // ComfortableApp.tsx:102: { key: 'ArrowRight', handler: () => { nextTrack(); info('Next track'); } }
  ```
- **Impact**: The seek bar, the one control a keyboard user needs to scrub, cannot be used without skipping tracks. Space cannot activate focused buttons. Arrow-key navigation in lists, tabs and menus changes volume or skips tracks. The shortcuts also fail WCAG 2.1.4 (Character Key Shortcuts): Space, `m`, `1`-`4`, `/`, `?` are single-key and there is no way to turn them off or remap them. Screen-reader users in forms mode are especially exposed because they rely on Space/arrows to drive widgets.
- **Siblings**: `@hello-pangea/dnd` keyboard lifting (Space) in the playlist/queue drag-and-drop competes with the same global Space handler. The `Escape` shortcut (`ComfortableApp.tsx:178`) also fires while a dialog is open (it clears the search and closes Settings behind other dialogs).
- **Suggested Fix**: In `handleKeyDown`, return early if `event.defaultPrevented`, if the target (or an ancestor) is a widget that owns the key (`[role=slider|listbox|option|tab|tablist|menu|menuitem|dialog]`, `button` for Space, `[aria-modal=true]`), and while any modal is open (call `disable()`/`enable()` from the dialog open state). Add a Settings toggle to disable single-key shortcuts.

### TST-01: `WebSocketManager` (reconnect, heartbeat, close) is mocked out of every spec; its reconnect path has zero assertions
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/utils/errorHandling.ts:47-200` (class); specs `src/contexts/__tests__/WebSocketContext.{ping,mountedRef,reconnect,audioChunk,unregisteredType,cacheCleared}.test.tsx`, `src/hooks/websocket/__tests__/useWebSocketConnection.{singleton,reissueRecovery}.test.tsx`, `src/hooks/websocket/__tests__/websocketConnectionCore.*.test.ts`, `src/tests/integration/websocket-realtime/websocket-realtime.test.tsx:84-104`
- **Status**: NEW (related open: #5469 close-code retry; HK-01 in dim_3)
- **Description**: `utils/__tests__/` has only `errorHandling.isRetryableError` and `errorHandling.shouldRetryQuery` specs. Every other spec that touches the WebSocket stack replaces the class wholesale with `vi.mock('@/utils/errorHandling', () => ({ WebSocketManager: vi.fn() }))` and drives a hand-written fake that emits `open/close/error` by hand. The one spec that runs the real manager (`websocket-realtime.test.tsx`, which unmocks the context and stubs `global.WebSocket`) is titled "should reconnect on connection loss" but only asserts `isConnected === false` / `connectionStatus === 'disconnected'` after `simulateClose`, with the comment "Actual reconnection logic is implementation detail". Nothing therefore asserts: number of `attemptReconnect` schedules per failure, the `reconnectAttempts` budget, backoff delays, `onMaxAttemptsExceeded`, heartbeat start/stop, or that `close()` cancels the pending reconnect timer. This is exactly where HK-01 (every failed reconnect scheduled twice: `onclose` -> `attemptReconnect()` and `connect().catch` -> `attemptReconnect()`) lives, so it passed review with the whole suite green. `grep -rn "reconnectAttempts|attemptReconnect|maxReconnectAttempts"` over `*.test.*` hits only `connectionSlice.test.ts` (Redux counter), never the manager.
- **Evidence**:
  ```ts
  // websocket-realtime.test.tsx:96-103
  mockWS.simulateClose(1006, 'Connection lost');
  // Assert - should transition to disconnected state
  // Note: Actual reconnection logic is implementation detail
  await waitFor(() => {
    expect(result.current.isConnected).toBe(false);
    expect(result.current.connectionStatus).toBe('disconnected');
  });
  // hooks/websocket/__tests__/useWebSocketConnection.singleton.test.tsx:15
  vi.mock('@/utils/errorHandling', () => ({ WebSocketManager: vi.fn() }));
  ```
- **Impact**: The retry-budget exhaustion and duplicate-live-socket bug (HK-01) and any future regression in backoff/heartbeat/cleanup ship undetected; the app's only transport for playback state and audio chunks.
- **Siblings**: none beyond the listed specs.
- **Suggested Fix**: Add `utils/__tests__/errorHandling.WebSocketManager.test.ts` with fake timers and a controllable `WebSocket` stub: assert exactly one reconnect timer per close/failed-connect, delay sequence, stop at `maxReconnectAttempts` with `onMaxAttemptsExceeded`, heartbeat interval cleared on close, and `close()` clearing the timer. Rename the integration test or make it assert a reconnect `new WebSocket` call.

### TST-02: No test pins the HIGH defects found by the Hooks/Redux/Components audits (HK-02, RDX-01, HK-04, CMP-04)
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `src/contexts/__tests__/PlaybackSessionContext.transport.test.tsx` (whole file), `src/store/slices/__tests__/playerSlice.test.ts:364-420`, `src/components/settings/__tests__/SettingsDialog.test.tsx:100-112`
- **Status**: NEW (grouped regression-test gap; the underlying defects are HK-02 / RDX-01 / HK-04 / CMP-04 in dim_1-3)
- **Description**: Verified absence of tests for each:
  - HK-02 (play/pause restarts the track when `streamingState` is `'complete'`): `PlaybackSessionContext.transport.test.tsx` covers `handlePrevious`, `handleMuteToggle`, auto-advance only (`describe` blocks at lines 83, 170, 227). There is no `handlePlayPause` case at all, let alone one with a completed stream. `usePlayEnhanced.test.ts` covers `audio_stream_end -> completeStreaming` but not what the transport does next.
  - RDX-01 (duplicate track ids in queue trap next/previous): `setCurrentTrackAndSyncQueue` tests use queues of unique ids (`[10, 20, 30]`) and assert `setCurrentIndex(1)`. No duplicate-id case.
  - HK-04 (client auto-advance ignores repeat mode): `grep -i repeat` over `PlaybackSessionContext.*.test.tsx` returns nothing.
  - CMP-04 (Settings dialog keeps unsaved edits after Cancel): the only Cancel test has no assertion (see TST-03/TST-10).
  - HK-01 is covered in TST-01.
- **Evidence**:
  ```ts
  // playerSlice.test.ts:372-386 — unique ids only
  tracks: [{ id: 10, title: 'A' }, { id: 20, title: 'B' }, { id: 30, title: 'C' }],
  ```
- **Impact**: Four user-visible playback/queue regressions have no safety net; fixes for them will land without a failing-first test.
- **Siblings**: n/a
- **Suggested Fix**: Add the four regression cases (play/pause during `'complete'`, duplicate-id queue index resolution, repeat-one/repeat-all auto-advance, Cancel discards edits) when each underlying issue is fixed; gate the fix PRs on them.

## Medium Findings (38)

### CMP-02: Track context menu shows Favourite / Go to Album / Go to Artist / Track Info items that do nothing in the library list and tables
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/shared/ContextMenu/contextMenuActions.tsx:60-97`, `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:201-214`, `auralis-web/frontend/src/components/library/Items/tables/TrackTableRowItem.tsx:44-51`
- **Status**: NEW
- **Description**: `getTrackContextActions` renders `love`, `album`, `artist`, `similar` and `info` unconditionally. When a callback is missing it substitutes `() => {}`. `useTrackContextMenu` only passes `onToggleLove`, `onShowAlbum`, `onShowArtist` and `onShowInfo` when the caller supplied them. The two real call chains never do:
  - `TrackListViewContent` passes only `onPlay`, `onPause`, `onEditMetadata` and `onFindSimilar` to `SelectableTrackRow`, which forwards them to `TrackRow`.
  - `TrackTableRowItem` passes only `onPlay` and `onFindSimilar`.

  In the songs and favourites list the menu therefore lists "Add to Favourites", "Go to Album", "Go to Artist" and "Track Info". Clicking any of them closes the menu and does nothing. The same applies in album and artist detail tables, which also lack "Edit Metadata". Compare `edit-metadata` and `delete`, which the factory correctly omits when no callback is given. CozyLibraryView already hides the batch Remove button for the same reason (#4240).
- **Evidence**:
  ```tsx
  // contextMenuActions.tsx
  { id: 'love', label: ..., onClick: callbacks.onToggleLove || (() => {}), divider: true },
  { id: 'album', label: 'Go to Album', onClick: callbacks.onShowAlbum || (() => {}) },
  // TrackListViewContent.tsx:201 - no onToggleFavorite/onShowAlbum/onShowArtist/onShowInfo
  <SelectableTrackRow ... onEditMetadata={onEditMetadata} onFindSimilar={onFindSimilar} />
  ```
- **Impact**: Four visible controls are dead. A single track cannot be favourited from the context menu (only through batch selection), and there is no navigation to a track's album or artist from the main list.
- **Siblings**: Album and artist context factories have the same `|| (() => {})` shape (`getAlbumContextActions`, `getArtistContextActions`). Not verified individually.
- **Suggested Fix**: Build the action array conditionally, as `edit-metadata` and `delete` already are. Then wire `onToggleFavorite`, `onShowAlbum`, `onShowArtist` through the list chain, or hide the entries.

### CMP-03: Track context menu never loads playlists, so "Add to Playlist" offers only "Create New Playlist"
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:192-194`, `auralis-web/frontend/src/components/library/Items/tables/TrackTableRowItem.tsx:136`, `auralis-web/frontend/src/components/library/Items/tracks/useTrackContextMenu.ts:49-60,200`, `auralis-web/frontend/src/components/shared/ContextMenu/ContextMenu.tsx:67-72`
- **Status**: NEW
- **Description**: `ContextMenu` calls `onPlaylistsLoad()` when it opens. `useTrackContextMenu` exposes a working `fetchPlaylists` that fills the `playlists` state. Neither call site destructures or passes it. `TrackRow` passes `onPlaylistsLoad={() => { /* fetch playlists */ }}` and `TrackTableRowItem` passes `() => {}`. `playlists` therefore stays `[]` for the life of the row, and `PlaylistSection` renders "Add to Playlist" plus only "Create New Playlist" (`playlists.length > 0` is never true).
- **Evidence**:
  ```tsx
  // TrackRow.tsx:192
  onPlaylistsLoad={() => {
    /* fetch playlists */
  }}
  ```
  Repo-wide, `fetchPlaylists` from this hook has no consumer.
- **Impact**: A user cannot add a track to an existing playlist from the context menu in the main library views. Only batch add (select, then toolbar) and drag-drop remain.
- **Siblings**: Both rows listed above.
- **Suggested Fix**: Destructure `fetchPlaylists` and pass it as `onPlaylistsLoad`. It must be a stable reference: the menu's effect lists `onPlaylistsLoad` in its deps, so the current inline arrow would loop if it ever fetched and set state. Better, share `usePlaylistData`'s list instead of one fetch per row.

### CMP-04: Settings dialog keeps unsaved edits after Cancel/Esc and re-shows them as current values
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/settings/useSettingsDialog.ts:20-37,40-42,121-130`, `auralis-web/frontend/src/components/settings/SettingsDialog.tsx:40-47,92`, `auralis-web/frontend/src/ComfortableApp.tsx:341-370`
- **Status**: NEW
- **Description**: `ComfortableApp` mounts `SettingsDialog` once and toggles `open`, so the hook state is never torn down. `pendingChanges` is cleared only by a successful save or reset. Cancel, Esc and backdrop close call plain `onClose`. When the dialog reopens, `loadSettings()` refreshes `settings`, but `getValue` prefers `pendingChanges`. The edits the user cancelled are shown as if they were stored, and clicking Save commits them.
- **Evidence**:
  ```ts
  // useSettingsDialog.ts
  useEffect(() => { if (open) loadSettings(); }, [open]);   // never clears pendingChanges
  const getValue = ... if (key in pendingChanges) return pendingChanges[key] ...
  // SettingsDialog.tsx:92   onCancel={onClose}
  ```
- **Impact**: "Cancel" does not cancel. A user who changes, say, cache size, cancels, and later opens settings to change something else will unknowingly save the earlier edit.
- **Siblings**: None. The other dialogs are keyed per session (`EditMetadataDialog key={editSession}`).
- **Suggested Fix**: Reset `pendingChanges` (and `error`) when `open` becomes false or true. Alternatively, mount the dialog only while open and keep exit transitions with a keyed session, as `EditMetadataDialog` does.

### CMP-05: "Recently Played" (sidebar) and shortcut `4` "Playlists" render the entire library under misleading titles
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:186-192`, `auralis-web/frontend/src/hooks/library/useLibraryPagination.ts:91-94`, `auralis-web/frontend/src/components/layouts/Sidebar/SidebarContent.tsx:30-32`, `auralis-web/frontend/src/ComfortableApp.tsx:181-189`
- **Status**: NEW
- **Description**: The sidebar's "Recently Played" entry sets `currentView = 'recent'`, and the `4` shortcut sets `'playlists'`. `CozyLibraryView` handles `recent` and `playlists` only in the `viewConfig` title map. Data comes from `useLibraryPagination({ view })`, which special-cases only `favourites` and otherwise fetches `/api/library/tracks`. Both views therefore show the same unfiltered all-tracks list under "Recently Played / Tracks you played recently" and "Playlists / Your custom playlists". The backend already supports `order_by=last_played` (`routers/tracks.py`), and playlists live in the sidebar `PlaylistList`.
- **Evidence**:
  ```ts
  // useLibraryPagination.ts:91
  view === 'favourites' ? `/api/library/tracks/favorites?...` : `/api/library/tracks?...`
  // CozyLibraryView.tsx:190
  recent: { ..., title: 'Recently Played', subtitle: 'Tracks you played recently' },
  ```
- **Impact**: Two navigation targets show wrong content with confident headings. Pressing `4` shows all songs titled "Playlists".
- **Siblings**: None.
- **Suggested Fix**: Either request `order_by=last_played` with a play-count filter for `recent`, or remove the entry. Drop the `playlists` view and the `4` shortcut, or route them to the playlist UI.

### CMP-06: Dragging the progress bar fires a stream-restarting seek on every mousemove, and a second seek on mouseup (click)
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/useProgressBarInteraction.ts:94-153,167-182,226-241`, `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:48-93`
- **Status**: NEW (related: closed #4196 fixed a debounce in a since-deleted `usePlayerControls`; the current path has none)
- **Description**: `handleGlobalMouseMove` calls `onSeekRef.current(position)` for every `mousemove` while dragging. `onSeek` is `PlaybackSession.handleSeek`, which calls `seekTo`. Each call does `stopPlayback()`, `pcmBuffer.reset()`, clears pending chunks and sends a WS `seek` that makes the backend start a new stream. `handleMouseDown` seeks once, and the `click` that follows `mouseup` on the same element runs `handleClick`, so it seeks again at the release position. After the first seek, `Player` disables the bar (`isSeeking`), but the global drag handlers do not check `disabled` and keep seeking. The "live position during drag" design (throttled ARIA announcements) implies seeking was meant to happen on release.
- **Evidence**:
  ```ts
  const handleGlobalMouseMove = useCallback((event) => {
    ...
    const position = getPositionFromEvent(event);
    onSeekRef.current(position);          // every mousemove
  ```
- **Impact**: Scrubbing sends tens of seek commands per second. Each cancels and restarts a server-side stream render and wipes the local PCM buffer, so audio stays silent for the whole drag. It adds avoidable backend load and stream churn (and risks the seek-handoff races already tracked server-side).
- **Siblings**: `handleTouchMove` has the same per-event seek.
- **Suggested Fix**: During drag, update only the visual and ARIA position. Commit one seek on `mouseup`/`touchend`, and suppress the trailing click when a drag occurred.

### CMP-07: The library track list is torn down to a skeleton and loses scroll, focus and pagination on every refetch
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Views/TrackListView.tsx:86-96`, `auralis-web/frontend/src/hooks/library/useLibraryPagination.ts:66-90`, `auralis-web/frontend/src/components/library/useMetadataEditing.ts:24-27`, `auralis-web/frontend/src/components/library/useBatchOperations.ts:132,161`
- **Status**: NEW
- **Description**: `TrackListView` returns a different tree (`LibraryGridSkeleton` or `TrackRowSkeleton` list) whenever `loading` is true. `fetchTracks()` with its default `resetPagination = true` sets `loading=true` and `setTracks([])`. It is called after every metadata save, after bulk favourite toggles and bulk remove, and on every `library_updated` WebSocket event (including auto-scan with changes). The virtualized list, its roving-tabindex focus, scroll offset and the loaded pages (`loadMore` progress) are all discarded. Only the first 50 tracks come back.
- **Evidence**:
  ```tsx
  // TrackListView.tsx
  if (loading) { return viewMode === 'grid' ? <LibraryGridSkeleton count={12} /> : (<ListLoadingContainer>...TrackRowSkeleton...) }
  // useMetadataEditing.ts
  await onFetchTracks();   // -> fetchTracks(true)
  ```
- **Impact**: Favouriting five tracks from row 3,000, or an auto-scan finishing, snaps the view back to the top of a 50-item list and drops keyboard focus. Selection is reset too.
- **Siblings**: Grid mode uses the same early return.
- **Suggested Fix**: Show the skeleton only for the initial load (`loading && tracks.length === 0`). For post-mutation refreshes, refetch in place (`resetPagination=false` or patch the affected rows) and keep the list mounted.

### CMP-08: Error boundaries have no reset path, and the Player boundary covers transport controls and the queue panel together
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:298-328,336-402,404-426`, `auralis-web/frontend/src/components/core/ErrorBoundary.tsx:25-47`, `auralis-web/frontend/src/design-system/primitives/ErrorBoundary.tsx:19-55`
- **Status**: NEW (boundaries were added in #3583, #3115, #4880; this is about their recovery behaviour)
- **Description**: Boundaries are mounted around the library, settings, shortcuts help, Player, and the root. The mounted `components/core/ErrorBoundary` offers recovery only in its built-in UI. When a `fallback` node is supplied, as all four in `ComfortableApp` do, `handleRetry` is unreachable, so the fallbacks say "Refresh the page". A library render crash stays dead even after the user switches view (`currentView` does not reset the boundary). One boundary wraps the whole `Player`, so a render error in `QueuePanel` (virtualized, renders untrusted queue payloads) replaces the transport bar, seek bar and volume as well. The stream keeps playing in `PlaybackSessionContext`, with no controls. Sidebar, top bar and the album character pane have no local boundary and fall through to the root boundary, which replaces the whole window. `design-system/primitives/ErrorBoundary.tsx` has the better API (`fallback(error, retry)`, `onError`), but it has no importer.
- **Evidence**:
  ```tsx
  <ErrorBoundary fallback={<Box ...>Library failed to render. ... Refresh the page to retry.</Box>}>
  ...
  <ErrorBoundary fallback={<Box ...>Player encountered an error. Refresh the page to restart playback.</Box>}>
    <Player />   // QueuePanel is a child of Player
  ```
- **Impact**: A transient render error becomes unrecoverable without a reload, and a queue-panel bug removes playback controls while audio continues.
- **Siblings**: None.
- **Suggested Fix**: Consolidate on one `ErrorBoundary` that supports `fallback(error, retry)` and a `resetKeys` prop (for example `[currentView]`). Wrap `QueuePanel` in its own boundary inside `Player`. Delete the unused duplicate.

### RDX-02: Frontend-local skips move only Redux; backend queue/player snapshots then overwrite `queue.currentIndex` and `player.currentTrack` with the engine's stale pointer
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:50-55`, `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:130-181`, `:296-301`, `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:127-136`
- **Status**: NEW (backend side of the same drift: Existing #5460; INT-F9-03 in AUDIT_INTEGRATION_2026-09-13)
- **Description**: Next/Previous (`handleNext`/`handlePrevious`) never call the backend navigation endpoints (`/api/player/next|previous` exist in `config/api.ts` but have zero callers). They move `queue.currentIndex` and `player.currentTrack` locally and start the stream with a WS `play_normal`/`play_enhanced`. I grepped `ws_handlers/playback_commands.py` and `core/stream_*.py`; neither updates the engine queue pointer or `PlayerStateManager`. Three other writers then apply the BACKEND's index with no ordering or reconciliation against the local move:
  - `queue_changed.current_index` (`useQueueSubscription`), emitted after any backend queue edit;
  - `player_state.queue_index`/`current_track` (`usePlayerStateSync`);
  - `track_changed`.
  Only the `player_state` family has a `seq` watermark, and `queue_changed` has none. The watermarks are deliberately separate per message family (`lastSeenSeqRef`, `lastSeenTrackChangedSeqRef`, `lastSeenTransportEventSeqRef`), so nothing orders a `queue_changed` against a local skip.
- **Evidence**:
  ```ts
  // useQueueSubscription.ts
  if (data.tracks) dispatch(reduxSetQueue(data.tracks));
  if (data.current_index != null) dispatch(reduxSetCurrentIndex(data.current_index));
  // usePlayerStateSync.ts
  if ('queue_index' in state && typeof state.queue_index === 'number') dispatch(setCurrentIndex(state.queue_index));
  ```
- **Impact**: Play an album, skip to track 4, then drag a track into the queue (backend `queue_changed` carries `current_index` of the engine's pointer). Redux `queue.currentIndex` jumps back to the engine's pointer while `player.currentTrack` and the audio are still track 4. The next Next/auto-advance is computed from the wrong index and plays the wrong track.
- **Siblings**: RDX-01 (the same thunk), RDX-05 (Redux-only queue edits that the same broadcasts erase).
- **Suggested Fix**: Make one side authoritative. Either route Next/Previous through NavigationService so the engine pointer moves with the UI, or derive `queue.currentIndex` from `player.currentTrack.id` plus the queue (nearest-match, see RDX-01) when applying `queue_changed`/`player_state`, and stamp `queue_changed` with a `seq` that is compared against `lastSeenSeqRef`.

### RDX-03: Raw wire/REST payloads are dispatched into the camelCase `queue`/`player` slices without `mapTrackInfoToTrack`
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:52`, `:62`; `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:100-106`
- **Status**: NEW (sibling gap of #5009, which fixed only `useQueueFetch` and `usePlayerStateSync`)
- **Description**:
  - `queue_changed`/`queue_shuffled` dispatch `data.tracks` (`TrackInfo[]`, snake_case: `artwork_url`, `format`) straight into `queue.tracks`. The backend payload is `TrackPayload(artwork_url=..., format=...)` (`services/queue_enrichment.py:37-45`). `TrackInfo` happens to satisfy `QueueTrack` structurally, so the compiler is silent, but every entry lacks `artworkUrl`.
  - `useEnhancedPlayCommand` does `response.json()` on `GET /api/library/tracks/{id}` (`TrackResponse`: `duration: float | None`, `album: str | None`, ~40 snake_case analysis fields) and dispatches it as a `PlayerTrack` through `setCurrentTrackAndSyncQueue`. `transformTrack()` exists in `api/transformers` and is unused here.
  - The result is that `queue.tracks` and `player.currentTrack` change shape depending on which writer ran last. `player.currentTrack` is overwritten again by `mapTrackInfoToTrack` on the next snapshot.
- **Evidence**:
  ```ts
  // useEnhancedPlayCommand.ts:103-106
  const track = await response.json();
  dispatch(setCurrentTrackAndSyncQueue(track));
  // playerSlice.setCurrentTrack reducer
  state.duration = action.payload.duration;   // null for a TrackResponse with duration: null
  ```
- **Impact**: After any queue edit, queue entries have no `artworkUrl` (the artwork symptom #5009 already fixed for the fetch path). `track_changed` then copies such an entry into `player.currentTrack`. A null `duration` in the REST track poisons `player.duration`, and `setCurrentTime` clamps with `Math.min(x, null) === 0`. Extra analysis fields bloat the Redux state. Today's visible artwork impact is limited because the player bar renders none (#5521), but the shape is wrong for every consumer.
- **Siblings**: `useQueueFetch`/`usePlayerStateSync` use the mapper (correct).
- **Suggested Fix**: Map at the dispatch boundary: `data.tracks.map(mapTrackInfoToTrack)` in `useQueueSubscription`, and `transformTrack` (or a `PlayerTrack` picker with `duration ?? 0`) in `useEnhancedPlayCommand`. Better, make the reducers accept only the mapped type.
- **Merged from TS-02** (MEDIUM, `useQueueSubscription` dispatches raw `TrackInfo[]` (snake_case wire shape) into the Redux queue as `Track[]`, bypassing the #5009 mapper): ``auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:52,62`` — `queue_changed` and `queue_shuffled` carry `tracks?: TrackInfo[]` (`types/ws/queue.ts:37,69`: wire shape with `artwork_url`, `sample_rate`, ...). `reduxSetQueue` is typed `PayloadAction<Track[]>`, and `TrackInfo` is structurally assignable to `Track` (all `Track` extras are optional and the required core fields coincide), so the compiler accepts it. The other two `TrackInfo` -> Redux paths run `mapTrackInfoToTrack` (`hooks/player/trackInfoMapper.ts`), whose header exists precisely because "an unsafe cast" here produced objects with `.artwork_url` where consumers read `.artworkUrl` (#5009). This third site was missed. The mapper also normalises `album || ''` and `duration || 0`, which the raw dispatch skips.
- **Merged from TS-03** (MEDIUM, `useEnhancedPlayCommand` pushes an `any`-typed raw `/api/library/tracks/{id}` JSON body into `player.currentTrack`): ``auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:99-107`` — The hook uses a bare `fetch()` and `await response.json()` (`Promise<any>`), so `track` is `any` and `dispatch(setCurrentTrackAndSyncQueue(track))` type-checks. The body is a `TrackResponse` (`schemas/library.py:85`): snake_case, `artists: string[]` (no `artist` on a real row), `album: string | null`, `artwork_url`. `setCurrentTrackAndSyncQueue` takes a `PlayerTrack` (`artist: string`, `album: string`, `artworkUrl`). Everything else that builds a `Track` from this endpoint goes through `transformTrack` (which maps `artists[0]` -> `artist`, `album ?? ''`, `artwork_url` -> `artworkUrl`).
- **Merged from API-11** (LOW, `playlistService.getPlaylist().tracks` is typed as domain `Track[]` but is raw snake_case and is dispatched into Redux unmapped): ``auralis-web/frontend/src/services/playlistService.ts:35`; `auralis-web/frontend/src/components/playlist/usePlaylistContextActions.ts:39-47`; backend `auralis-web/backend/routers/playlists.py:229-253`` — `GET /api/playlists/{id}` returns `tracks: [track.to_dict() ...]`, i.e. snake_case with an `artists: string[]` array and no singular `artist`. `Playlist.tracks?: Track[]` claims the camelCase domain type, `isPlaylistShape` does not look at `tracks`, and `transformTracks` is not applied. The "Play playlist" action passes these objects to `setQueue(tracks, 0)`, which dispatches them straight into the Redux queue (and posts `tracks.map(t => t.id)`).

### RDX-04: `player.volume`/`isMuted` are never applied to a newly created `AudioPlaybackEngine`; WS-sourced volume never reaches the engine
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:138`, `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:65-80`, `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:536-538`, `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:187-197`, `:199-208`
- **Status**: NEW
- **Description**: Redux holds `volume` (default 80) and `isMuted`, and the UI slider reads them. The audio sink is set only imperatively, in `handleVolumeChange`, through `core.setVolume` on `playbackEngineRef.current?.` (a no-op when no engine exists). Every stream start builds a fresh `new AudioPlaybackEngine(...)` whose `gainNode.gain.value` is hard-coded to `1.0`, and nothing re-applies the Redux value. The `volume_changed` WS event and `player_state.volume` update Redux only (`usePlayerStateSync`). Mute is implemented as `handleVolumeChange(0)`.
- **Evidence**:
  ```ts
  // AudioPlaybackEngine.ts
  private volume: number = 1.0;
  this.gainNode.gain.value = this.volume;
  // useEnhancedStreamStart.ts:138
  const engine = new AudioPlaybackEngine(core.audioContextRef.current, buffer);   // no setVolume
  ```
- **Impact**: Redux says 80% (the default) but the first track plays at 100%. The slider is at 30% or muted, the user presses Next, and the new engine plays at full gain while the UI still shows 30% or "muted". The Redux value is not authoritative for the output.
- **Siblings**: `ComfortableApp` volume shortcuts go through the same `handleVolumeChange`.
- **Suggested Fix**: Apply `store.getState().player` volume/mute to the engine right after construction in `useEnhancedStreamStart`. Better, subscribe the engine to the Redux volume with an effect keyed on `[playerVolume, playerIsMuted, engine]`, so WS-sourced changes reach the output as well.

### HK-03: Seek re-masters with the preset/intensity captured at play time, undoing live intensity changes
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:116-120`, `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:59,76-83`
- **Status**: NEW
- **Description**: `currentTrackInfoRef` is written exactly once, in `playEnhanced`. When the user later drags the intensity slider or changes preset, `useEnhancementControl` calls `reissueActiveStreamAs(...)`, which restarts the stream with the new values and updates `connState.lastStreamCommand`, but it cannot reach `currentTrackInfoRef`. `seekTo` then sends `{type:'seek', data:{track_id, position, preset, intensity}}` from the stale ref. The backend's `resolve_enhancement_params` treats a valid client payload as authoritative (`ws_handlers/playback_commands.py:55-107, 397-423`), so the seek stream is mastered with the OLD intensity.
- **Evidence**:
  ```ts
  // set once at play start only
  currentTrackInfoRef.current = { trackId, preset, intensity };      // useEnhancedPlayCommand.ts:116
  // used on every seek
  const { trackId, preset, intensity } = currentTrackInfoRef.current; // useEnhancedSeek.ts:59
  ```
  A repo-wide grep shows no other writer of `currentTrackInfoRef`.
- **Impact**: Play at 1.0, drag intensity to 0.4 (audio changes), click the progress bar: audio jumps back to intensity 1.0 while the slider still says 0.4. A WS reconnect then flips it again, because the replay uses `lastStreamCommand` (0.4).
- **Siblings**: `useEnhancedStreamStart.ts:188` dispatches `startStreaming({intensity: currentTrackInfoRef.current?.intensity})` from the same stale ref (that Redux field is otherwise unread, see #5357).
- **Suggested Fix**: On seek, read preset/intensity from the live enhancement state (for example pass a getter into `useEnhancedSeek`, or sync `currentTrackInfoRef` from the `enhancement_settings_changed` stream). Alternatively omit them and let the backend use the connection's `active_stream_settings`, which `reissueActiveStreamAs` keeps current server-side.

### HK-04: Client-side auto-advance ignores repeat mode, so the repeat controls do nothing for playback
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:118-139, 216-232`
- **Status**: NEW
- **Description**: Playback is driven by the browser PCM session. End-of-track advance is the `useEffect` in `PlaybackSessionProvider`, which calls `handleNext` only when `currentQueueIndex < queueTracks.length - 1`, and `handleNext` indexes `queueTracks[currentQueueIndex + 1]` directly. Nothing reads `queue.repeatMode` or `isShuffled` here, and a repo-wide grep finds no playback-path consumer of `repeatMode`; it is only read by the queue UI buttons and sync hooks. With repeat-one the next track plays; with repeat-all the queue ends instead of wrapping to index 0. The backend repeat setting is stored and broadcast but is never consulted by the thing that actually advances playback.
- **Evidence**:
  ```ts
  const hasMoreTracks = currentQueueIndex < queueTracks.length - 1;           // :226
  if (isComplete && nearEnd && hasMoreTracks && !hasAutoAdvancedRef.current) { // :228
    hasAutoAdvancedRef.current = true;
    handleNext();
  }
  ```
- **Impact**: The "repeat one / repeat all" buttons in `QueueControlBar` have no effect on playback. Users who loop an album stop after the last track.
- **Siblings**: Manual `handleNext`/`handlePrevious` also clamp at the queue ends rather than wrapping under repeat-all.
- **Suggested Fix**: Select `repeatMode` in the provider. At end-of-track with `'one'`, restart the current id (reset `hasAutoAdvancedRef`). With `'all'` and no next track, wrap to index 0. Apply the same wrap rule in `handleNext`/`handlePrevious`.

### HK-05: `useRestAPI` stale-response guard discards successful POST/PUT/DELETE responses and reports them as failures
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:74, 133-134, 154-158`; callers in `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:213-271 (reorderTrack, toggleShuffle), 291-322 (setRepeatMode), 203-211 (removeTrack)`
- **Status**: NEW
- **Description**: The per-endpoint sequence guard (#2439) was written for GET races, but `request()` applies it to every verb. If a second request to the same endpoint string starts before the first resolves, the first response, even a 2xx whose server-side effect has already happened, is cancelled and rethrown as `StaleRequestError`. `useQueueMutations` catches that as a generic error: it sets `error` and rethrows (the optimistic rollback is correctly skipped by `isNewestMutation`, so the Redux state is right but the error banner/toast is wrong). Triggers are ordinary double clicks or fast drags on endpoints whose URL does not vary: `/api/player/queue/shuffle`, `/api/player/queue/repeat`, `/api/player/queue/move`, `/api/player/queue/add-track`, `/api/player/queue/clear`. `useEnhancementControl` only escapes this by luck, because its own request-id check swallows the same error.
- **Evidence**:
  ```ts
  const seq = (requestSequences.current.get(endpoint) ?? 0) + 1;      // keyed by endpoint only, any method
  ...
  if (seq !== requestSequences.current.get(endpoint)) {
    response.body?.cancel();
    throw Object.assign(new Error('Stale response'), { name: 'StaleRequestError' }); // after response.ok
  }
  ```
- **Impact**: Two quick repeat/shuffle clicks, or two fast queue drags, show "Stale response" as a command error although both mutations were applied server-side.
- **Siblings**: None beyond the callers above.
- **Suggested Fix**: Apply the sequence check only to `method === 'GET'` (and key it on method plus full URL including query string). Mutations should never be discarded after the server has accepted them.

### HK-06: `useRestAPI` timeouts surface as `AbortError`, which callers treat as a silent unmount-cancel
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:105-120, 172-176`; consumer `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:291-295, 367-370`
- **Status**: NEW
- **Description**: `fetchWithTimeout` aborts its own controller after 30 s. The abort rejection is `AbortError`, the same name used for unmount cancellation, and `request()` rethrows it untouched without `setError` ("don't surface as API error"). `useLibraryQuery` (tracks/albums/artists, search, infinite scroll) then hits `if (err.name === 'AbortError') return;` with no error state. `executeQuery`'s `finally` still clears `isLoading`. The result is a spinner that disappears and leaves an empty or stale list with no error and no retry affordance. The sibling transport `utils/apiRequest.ts` maps a timeout to `APIRequestError` with `statusCode: 0` precisely to avoid this, so the two layers disagree.
- **Evidence**:
  ```ts
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);  // :107
  ...
  if (err instanceof Error && (err.name === 'AbortError' || err.name === 'StaleRequestError')) { throw err; } // :174
  // useLibraryQuery catch:
  if (err instanceof Error && err.name === 'AbortError') { return; }       // "Request was cancelled"
  ```
- **Impact**: When the backend is slow (heavy scan or fingerprint load, which the code base itself says serializes the ASGI loop), library lists silently render empty after 30 s instead of showing the error state. `useQueueFetch` logs a warning only.
- **Siblings**: `useQueueFetch.ts` (swallows all errors), `useQueueHistory.ts`.
- **Suggested Fix**: Distinguish timeout from caller abort in `fetchWithTimeout` (track `timedOut`, throw an `APIRequestError`/`TimeoutError` with `statusCode: 0` for it) and keep `AbortError` only for unmount/supersession.

### HK-07: `useAlbumFingerprints` re-keys on the full album-id list, so every infinite-scroll page refetches everything and blanks all fingerprints meanwhile
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:123-160`; consumer `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:70-75`
- **Status**: NEW (the missing cancellation is adjacent to open #5519, which covers the bare `fetch` in `useInfiniteAlbums`)
- **Description**: `CozyAlbumGrid` feeds `useAlbumFingerprints` the ids of ALL albums loaded so far (`useInfiniteAlbums` pages of 50 flattened). The query key is the sorted joined id list, so every `fetchNextPage` produces a new key. Because there is no `placeholderData`/`keepPreviousData`, `queries.data` is `undefined` for the new key and the hook returns `new Map()`. All tiles lose their fingerprint (they fall back to the hash gradient) until the new queryFn finishes. That queryFn refetches fingerprints for every album, including the already-fetched ones, in sequential groups of 10. The queryFn also ignores React Query's `signal`, so superseded runs keep issuing requests. Over a scroll through N albums this is O(N²/50) requests, aimed at the backend that the code comments (#3644) say serves requests serially and starves audio streaming. The per-album cache that `useAlbumFingerprint` keeps (`['album-fingerprint', id]`) is never consulted or seeded.
- **Evidence**:
  ```ts
  queryKey: ['album-fingerprints-batch', [...albumIds].sort().join(',')],   // changes per page
  queryFn: async () => { for (i...; i += 10) await Promise.allSettled(chunk.map(fetchAlbumFingerprint)); ... },
  ...
  fingerprints: queries.data ?? new Map(),                                   // also a fresh Map every render
  ```
- **Impact**: Visible flicker of every album tile's colouring on each scroll page, plus growing redundant request load that can compete with playback.
- **Siblings**: `RecentlyTouchedSection.tsx:90` (small, fixed list, fine). No React Query queryFn in the project forwards `signal` (`useAlbumFingerprint`, `useTrackFingerprint`, `useInfiniteAlbums`, `useStandardizedAPI`).
- **Suggested Fix**: Back the batch with per-album `useQueries` (or `queryClient.fetchQuery`) on the existing `['album-fingerprint', id]` keys so only new ids are fetched, or at least add `placeholderData: keepPreviousData` and fetch only ids missing from the previous result. Forward `signal` into the fetch.

### TS-01: WS `subscribe` handlers receive an un-discriminated union, forcing ~20 hand-written casts (several to ad-hoc anonymous shapes instead of the declared message interfaces)
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:51,66-68` (`MessageHandler`, `subscribe`), `auralis-web/frontend/src/hooks/websocket/useWebSocketMessages.ts:30-52`
- **Status**: NEW
- **Description**: `subscribe(messageType: WebSocketMessageType, handler: MessageHandler)` types the handler as `(message: AnyWebSocketMessage | WebSocketMessage) => void`. The union contains the generic `WebSocketMessage<unknown>` (`type: WebSocketMessageType`, `data: unknown`), which absorbs every specific member, so TypeScript can never narrow a handler's `message` from the literal passed to `subscribe`. Every consumer therefore re-asserts the shape by hand, and nothing ties the asserted shape to the message type that was subscribed to. Worse, five handlers in `usePlayerStateSync.ts` and one in `useServerRestartNotice.ts` assert to **inline anonymous shapes** (`{ data?: { position?: number; seq?: number } }`) rather than the real `PositionChangedMessage`/`VolumeChangedMessage`/`TrackChangedMessage` interfaces in `types/ws/player.ts`, so a change to those interfaces cannot produce a compile error at the consumer. `useMasteringRecommendation.ts:70` goes further and casts a *function type* (`handleMasteringRecommendation as (msg: AnyWebSocketMessage | WebSocketMessage) => void`), which silences parameter contravariance entirely. The dispatch table is a `Map<string, Set<MessageHandler>>`, so there is also no compile-time exhaustiveness for which types have a subscriber (only `ALL_MESSAGE_TYPES` is checked).
- **Evidence**:
  ```ts
  // WebSocketContext.tsx
  export type MessageHandler = (message: AnyWebSocketMessage | WebSocketMessage) => void;
  subscribe: (messageType: WebSocketMessageType, handler: MessageHandler) => () => void;

  // usePlayerStateSync.ts:205, 238, 263, 279 -- anonymous re-declarations of messages that already have interfaces
  const data = (message as { data?: { position?: number; seq?: number } }).data;
  const data = (message as { data?: { seq?: number } }).data;
  const data = (message as { data?: { volume?: number; seq?: number } }).data;
  const data = (message as { data?: { action?: string; track_index?: number; seq?: number } }).data;
  ```
- **Impact**: No runtime bug today (every field I compared matches the backend). But the type system gives zero protection on the hottest message paths (`player_state`, `position_changed`, `track_changed`, audio stream messages): a backend rename that is mirrored in `types/ws/*.ts` still compiles at every consumer, which is the exact drift class behind #3593/#3976/#4440/#4441.
- **Siblings**: `hooks/enhancement/useAudioStreamingCore.ts:451,483,487,491`; `hooks/enhancement/useFingerprintStatus.ts:121`; `hooks/enhancement/useEnhancementControl.ts:180`; `hooks/enhancement/useMasteringRecommendation.ts:70`; `hooks/library/useScanProgress.ts:130,141`; `hooks/player/useQueueSubscription.ts:44`; `hooks/player/usePlayerStateSync.ts:120,205,238,263,279`; `hooks/player/useServerRestartNotice.ts:34`; `components/playlist/usePlaylistWebSocket.ts:50,69`; `hooks/websocket/useWebSocketMessages.ts:43,50`; `hooks/websocket/websocketConnectionCore.ts:244`.
- **Suggested Fix**: Make `subscribe` generic: `subscribe<K extends WebSocketMessageType>(type: K, handler: (m: Extract<AnyWebSocketMessage, { type: K }>) => void)` (and the same for `useWebSocketMessages` over a tuple of types), and drop the bare `WebSocketMessage` from the handler union. Then delete the casts and use the declared message interfaces.

### TS-04: Generic parameters on REST helpers do not describe the wire shape (`LibraryQueryResponse<T>`, `crudService.list(): Promise<T[]>`), producing `as unknown as` chains; guards are `boolean`, not type predicates
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:77-83,264,282,345,365`; `auralis-web/frontend/src/utils/serviceFactory.ts:67-77`; `auralis-web/frontend/src/services/playlistService.ts:100-106`; `auralis-web/frontend/src/utils/apiRequest.ts:92,206`
- **Status**: NEW
- **Description**: (1) `useLibraryQuery` calls `get<LibraryQueryResponse<T>>` where `LibraryQueryResponse<T> = { items: T[]; total; offset; limit; hasMore }`. The real body is `{ tracks | albums | artists: <Api shape>[], total, offset, limit, has_more }` (types/transformers `TracksApiResponse`/`AlbumsApiResponse`). `items` and `hasMore` never exist on the wire and `T` (`Track|Album|Artist`) is the post-transform domain type, not what is received; the code then reads the real fields through `response as unknown as Record<string, unknown>` (`deriveHasMore`) and `extractItemsFromResponse` re-asserts `as TrackApiResponse[]`. (2) `createCrudService().list()` is declared `Promise<T[]>` but returns `get(endpoint)` for endpoints that return envelopes (`/api/playlists` -> `{playlists, total}`, `/api/settings`, queue); callers must undo it with `as unknown as PlaylistsResponse` (`playlistService.ts:104`), `as UserSettings[] | UserSettings` (`settingsService.ts:119`), `as QueueResponse[] | QueueResponse` (`queueService.ts:59`). (3) `apiRequest`/`useRestAPI` do `return parsed as T`; `validate` is `(value: unknown) => boolean`, so a guard is never connected to `T` (any guard can be paired with any `T`; `QUERY_TYPE_GUARD[queryType]` is looked up dynamically against a `T` it knows nothing about).
- **Evidence**:
  ```ts
  const response = await get<LibraryQueryResponse<T>>(url, { validate: QUERY_TYPE_GUARD[queryType] });
  setHasMore(deriveHasMore(response as unknown as Record<string, unknown>, newOffset, items.length));
  // serviceFactory.ts
  async list(params?: P, options?: CrudRequestOptions): Promise<T[]> { ... return opts ? get(endpoint, opts) : get(endpoint); }
  // playlistService.ts:104
  ? response as unknown as PlaylistsResponse
  ```
- **Impact**: The interface fields that look usable (`response.items`, `response.hasMore`) are always `undefined` at runtime; a future author using them gets a silent empty list/`hasMore=false`. Casting hides which fields the code actually depends on. Unguarded typed calls (e.g. `useLibraryStats`, `useTrackFingerprint`, `useSimilarTracks`, `useQueueHistory`, `useAlbumDetails`, `useArtistDetailsData`, `useLibraryScan`, `/api/player/enhancement/status`) are compile-time-only contracts by design (see `api/responseGuards.ts` header), which is acknowledged scope, not re-argued here.
- **Siblings**: `hooks/enhancement/useEnhancementControl.ts:127` (`getter<EnhancementState>` where `EnhancementState` includes client-only `lastUpdated` that the response lacks); `hooks/player/useQueueFetch.ts:44,54-70` (`get<Record<string, unknown>>` then per-field `as number/boolean` before `??`, which defeats the `??` intent in types).
- **Suggested Fix**: Type the call with the wire type (`TracksApiResponse | AlbumsApiResponse | ArtistsApiResponse`, discriminated by `queryType`), make `validate` a type predicate (`(v: unknown) => v is T`) so `apiRequest` can return the narrowed type without `as T`, and give `createCrudService` separate `TList` and `TItem` type parameters (or a `list` result type per service).

### TS-05: `SettingsDialogContent`'s `getValue` is typed `=> any`, erasing the `| null` that `useSettingsDialog.getValue` really returns
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/components/settings/SettingsDialogContent.tsx:13`; real signature at `auralis-web/frontend/src/components/settings/useSettingsDialog.ts:160-166`
- **Status**: NEW (the user-visible symptom is Existing #5517; the root cause was not identified there)
- **Description**: `useSettingsDialog.getValue<K>(key): SettingsUpdate[K] | null` returns `null` whenever `settings` has not loaded or a stored value is null. The prop type that carries it into the panels is `<K extends keyof SettingsUpdate>(key: K) => any`, so all 20 panel props (`defaultPreset={getValue('default_preset')}`, `enhancementIntensity=...`, `autoScan=...`, `cacheSize=...`) accept `null`/`undefined` where the panels declare `string`/`number`/`boolean`. A compiler error that would have flagged exactly the null-handling gap of #5517 is suppressed.
- **Evidence**:
  ```ts
  // SettingsDialogContent.tsx:13
  getValue: <K extends keyof SettingsUpdate>(key: K) => any;
  // useSettingsDialog.ts:161
  <K extends keyof SettingsUpdate>(key: K): SettingsUpdate[K] | null => {
  ```
- **Impact**: Null/undefined settings reach controlled MUI `Select`/`Switch`/`Slider` (`<Select value={defaultPreset}>` in `EnhancementSettingsPanel.tsx:36`), producing uncontrolled->controlled warnings and broken controls (#5517) with no compile-time signal.
- **Siblings**: Other `any` sites are in TS-09.
- **Suggested Fix**: Type the prop as `ReturnType<typeof useSettingsDialog>['getValue']` (or `<K>(key: K) => SettingsUpdate[K] | null`) and handle `null` at each panel call site (`?? default`).

### DS-01: Dark-only glass / gradient / white-alpha tokens are paired with theme-aware text, so several user-visible surfaces are unreadable in light mode
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/library/Controls/BatchActionsMoreMenu.tsx:44-53`; `auralis-web/frontend/src/components/library/Controls/AddToPlaylistMenu.tsx:66-97`; `auralis-web/frontend/src/components/shared/SimilarTracksModal/SimilarTracksModal.tsx:107-113`; `auralis-web/frontend/src/components/track/TrackCardOverlay.tsx:82-101` (+ `TrackCardStyles.ts:66-75`); `auralis-web/frontend/src/components/shared/EnhancementToggle/SwitchVariant.tsx:43-53` (+ `EnhancementToggleStyles.ts:70-72`)
- **Status**: NEW (same family as closed #4534 / #4877, whose scope was `tokens.colors.text/bg`; the glass, gradient and white-alpha roles were never migrated. #4877's fix for text/bg is intact: only one commented reference to `tokens.colors.text/bg` remains.)
- **Description**: `ThemeContext.tsx` documents `themeVars` as the only theme-aware colour source, and the `tokens.colors.*` primitives as dark-only build blocks. `semanticTheme.ts` covers text, surface, border, accent and shadow roles, but has no role for "glass fill", "scrim", or "foreground on a dark chip". Components fill that gap by reaching for `tokens.glass.*`, `tokens.gradients.darkSubtle`, `tokens.colors.opacityScale.dark.*` and `.white.*`. These are all fixed dark-mode values, yet their child text uses `themeVars.*`, which flips to dark ink in light mode. The result is dark ink on a dark fill, or white on white.
- **Evidence**:
  ```tsx
  // BatchActionsMoreMenu.tsx:44-52 / AddToPlaylistMenu.tsx:68,96
  paper: { sx: { background: tokens.gradients.darkSubtle /* #1B232E -> #131A24 */, ... } }
  <MenuItem sx={{ color: themeVars.textStrong, gap: 1 }}>   // light mode: #1A1F3A

  // SimilarTracksModal.tsx:109 (children use themeVars.textPrimary/textSecondary)
  background: tokens.glass.strong.background,   // rgba(21,29,47,0.55)

  // TrackCardOverlay.tsx:82-97
  background: isHovered ? tokens.glass.starfield.sharp : tokens.glass.starfield.medium,
  color: isHovered ? themeVars.textPrimary : themeVars.textMuted,

  // SwitchVariant.tsx:43-52 (rendered by AlbumCharacterPane, variant="switch")
  '& .MuiSwitch-switchBase': { color: tokens.colors.opacityScale.white.veryStrong }   // white @50%
  '& .MuiSwitch-track':      { backgroundColor: tokens.colors.opacityScale.white.lighter } // white @15%
  ```
  Contrast computed from the light-mode values in `semanticTheme.ts` (`#1A1F3A` ink, `#5A6280` secondary, `#F8F9FD` canvas, `--app-backdrop` = navy @40%):
  - Batch "Edit Metadata" menu and "Add to playlist" menu: `#1A1F3A` on `#1B232E` is about 1.02:1.
  - SimilarTracksModal paper over MUI backdrop is about `#505664`. Primary text is about 2.2:1 and secondary/muted text about 1.2:1.
  - TrackCard duration badge over artwork: 1.0 to 2.0:1 on hover for typical artwork, and 1.3 to 2.6:1 at rest. It also sits at opacity 0.6 at rest.
  - EnhancementToggle switch: thumb and track are white on `#F8F9FD`, so the unchecked switch is effectively invisible.
- **Impact**: With the shipped `ThemeToggle` set to light, the library batch toolbar's "more" and "add to playlist" menus, the Similar Tracks modal body, track-grid duration badges and the Auto-Mastering switch in the album pane are unreadable or invisible. Dark mode, the default, is unaffected.
- **Siblings**:
  - Production, same mechanism (dark fill with theme-aware child text, or white-alpha foreground): `components/shared/MediaCard/MediaCard.tsx:141-172`, `components/core/MobileSidebarDrawer.tsx:53-56`, `components/shared/EnhancementToggle/EnhancementToggleStyles.ts:70-72`, `components/library/Views/AlbumsTab.tsx:55`, `components/library/Views/TrackListView.styles.ts:6`, `components/library/Styles/Button.styles.ts:45,97`, `components/library/Items/tracks/TrackRowAlbumArt.tsx:31`. These are lower-impact because most are borders, bevels or hover tints rather than text carriers, but each is white-alpha on a light canvas.
  - Brand accent used as text on a light tint: `components/shared/ui/feedback/EmptyState.styles.ts:32` (`accent.secondary` cyan).
  - Unmounted subtree, no production importer: `components/library/Styles/SearchStyles.styles.ts:96-110` (`TypeChip` artist/album chips are about 1.3:1 in light mode); `MediaCardOverlay.tsx:107-111` badge (dark.nearOpaque with `themeVars.textPrimary`, but no caller passes `badgeContent`).
- **Suggested Fix**: Add the missing roles to `SemanticTheme` (for example `glassFill`/`glassFillStrong`, `menuSurface` and `onGlass`, and a switch-thumb/track role) and use them from these components. Alternatively, use `themeVars.surfaceRaised` or `surfaceOverlay` for the two menus and the modal paper, and `onAccent` or a fixed white on the artwork duration badge. Then delete the dead `glassEffects` helper (see DS-04) so there is one route.

### API-03: A failed favorite toggle on the album page replaces the whole album view with "Error Loading Album"
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:121-153` (esp. `:128-131`, `:148-149`); `auralis-web/frontend/src/components/library/Details/AlbumDetailView.tsx:109-123`
- **Status**: NEW
- **Description**: `useAlbumDetails` has one `error` state, used both for the load failure and for mutation failures. `toggleFavorite` calls `setError(ApiErrorHandler.parse(err))` when the POST/DELETE fails, and also `setError({status: 400, message: 'Cannot favorite album: no tracks available'})` for an album with no loaded tracks. `AlbumDetailView` renders `if (error || !album) { ...EmptyState 'Error Loading Album'... }`, so the album that was displayed a moment ago is replaced by the error screen. Nothing resets `error` except an `albumId` change, and `setError` is returned from the hook but never called by the view.
- **Evidence**:
  ```ts
  // useAlbumDetails.ts toggleFavorite
  } catch (err) { console.error('Error toggling favorite:', err); setError(ApiErrorHandler.parse(err)); }
  // AlbumDetailView.tsx
  if (error || !album) { const notFound = !error || ApiErrorHandler.isNotFound(error); return (<EmptyState title={notFound ? 'Album not found' : 'Error Loading Album'} .../>) }
  ```
- **Impact**: One transient failure of the heart button (or clicking it on an empty album) blanks the page; the user must navigate away and back. A 404 from `/api/library/tracks/{id}/favorite` (track removed by a scan) shows "Album not found".
- **Siblings**: None found; `useArtistDetailsData` has no mutations.
- **Suggested Fix**: Keep a separate `favoriteError` (surface it through a toast), or use a distinct `loadError` that only the fetch effect sets, so a failed mutation never hides loaded content.

### API-04: Five `fetch()` call sites bypass the shared transport and have no timeout; one gates playback start
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:99-113`; `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:50-56`; `auralis-web/frontend/src/hooks/library/useFingerprintCoverage.ts:85, 104`; `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:46`; `auralis-web/frontend/src/hooks/api/useRestAPI.ts:111` (own 30 s timer)
- **Status**: NEW for all but `useInfiniteAlbums` (Existing: #5519, same pattern, not re-argued here)
- **Description**: #5019 moved most call sites onto `utils/apiRequest.ts` (default 30 s timeout, backend `detail` extraction, `statusCode` on the error). These sites were not converted. The one that matters most is `useEnhancedPlayCommand`: it awaits `GET /api/library/tracks/{id}` (to seed `currentTrack`) BEFORE it dispatches `startStreaming` and sends `play_enhanced`/`play_normal`. That fetch has an abort controller but no timeout. A slow or contended REST path (the code base itself says the local FastAPI serializes requests, and the DB reads run on a thread pool during scans) delays the play command indefinitely, with no buffering state and no error. Its non-OK branch is also silent: `if (response.ok) {...}` has no `else`, so a 404/500 leaves the previous track as `currentTrack` while the new one streams. `usePlayTrack` awaits an unbounded queue POST before `startTrack`. `useFingerprintCoverage` has no timeout or signal, and its 10 s poll can stack requests behind a hung one. Because these paths throw `HttpStatusError` (from `httpErrorFromResponse`) instead of `APIRequestError`, `isRetryableError()` cannot use their status and falls back to message-wording heuristics: a 503 "Service Unavailable" is never retried on the one React Query path that uses one (`useInfiniteAlbums`), and a 4xx whose `detail` contains "connection"/"timeout" is retried.
- **Evidence**:
  ```ts
  // useEnhancedPlayCommand.ts  (before dispatch(startStreaming) and wsContext.send)
  const response = await fetch(getApiUrl(`/api/library/tracks/${trackId}`), { signal: core.abortRef.current.signal });
  if (response.ok) { const track = await response.json(); dispatch(setCurrentTrackAndSyncQueue(track)); }   // no else, no timeout
  ```
  ```ts
  // errorHandling.ts isRetryableError: only `instanceof APIRequestError` uses a status
  ```
- **Impact**: Clicking play while the REST path is slow appears to do nothing; a failed metadata fetch leaves a stale track in the player bar. (The raw-JSON-into-Redux half of `useEnhancedPlayCommand` is RDX-03.)
- **Siblings**: the five sites above.
- **Suggested Fix**: Route them through `get`/`post` (with `signal`), and make the metadata fetch non-blocking: send the WS play command first and let the track metadata arrive via `player_state`/`track_changed`. Make `isRetryableError` also read `HttpStatusError.status` (or retire `httpErrorFromResponse` for callers that can use `apiRequest`).

### API-05: Cancellation gaps: `useRestAPI` cannot be cancelled by callers, and React Query `queryFn`s never forward `signal`
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:66-77, 103-122, 217-228` (no `signal` option); `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:44-60, 119-150`; `auralis-web/frontend/src/hooks/fingerprint/useTrackFingerprint.ts:41-52, 86-90`; `auralis-web/frontend/src/hooks/shared/useStandardizedAPI.ts:98-101, 126-129`; `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:245-312, 331-390` (supersession only by request id)
- **Status**: NEW (HK-07 covers the over-fetch trigger in `useAlbumFingerprints`; this finding is the missing cancellation)
- **Description**: `useRestAPI` accepts only `{ validate }` per call and aborts solely on unmount. `useLibraryQuery` (search typing, sort change, infinite scroll) therefore handles supersession by discarding the response (`isStale()`), and the superseded request still runs to completion. The React Query hooks build their request with `get(url)` and ignore the `{ signal }` that `useQuery` hands to the `queryFn`, so unmounting a tile or changing a query key never aborts the HTTP request. `useAlbumFingerprints` is the extreme case: its `queryFn` loops over all album-id chunks (10 concurrent) with no abort check, so after the key changes it keeps issuing every remaining chunk for the old list.
- **Evidence**:
  ```ts
  queryFn: () => fetchTrackFingerprint(trackId),            // no ({ signal }) => ..., get(url) has no signal
  for (let i = 0; i < albumIds.length; i += FINGERPRINT_BATCH_CONCURRENCY) { ... await Promise.allSettled(chunk.map(...)) }  // never checks cancellation
  ```
- **Impact**: Wasted requests against a backend that the code itself describes as serving requests serially ("firing 200 requests at once starves audio-streaming requests", `useAlbumFingerprint.ts`), so fast scrolling/typing in the library can delay stream chunks.
- **Siblings**: the hooks listed above; `useAPIHealthPoll`, `useFingerprintCoverage` and `useQueueFetch` have only a mounted-flag guard.
- **Suggested Fix**: Add an optional `signal` to `useRestAPI` calls (compose it with the per-request controller) and abort the previous request in `useLibraryQuery.executeQuery`; pass `signal` from the `queryFn` context into `get(...)`, and check `signal.aborted` between chunks in `useAlbumFingerprints`.

### API-06: Bulk "add to queue" fires N concurrent POSTs, so the queue order is not the selection order
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/library/useBatchOperations.ts:73-87`; backend `auralis-web/backend/services/queue_edit_mixin.py:30-75`
- **Status**: NEW
- **Description**: `handleBulkAddToQueue` maps every selected id to `post('/api/player/queue/add-track', { track_id })` and awaits them with `Promise.allSettled`. The requests are issued together over parallel connections. Server-side, each handler first awaits `asyncio.to_thread(tracks.get_by_id)` and only then takes `_set_queue_engine_lock` and appends, so the append order is the thread-pool completion order, not the request order. There is no batch endpoint, and each request also triggers its own full-queue `queue_changed` broadcast.
- **Evidence**:
  ```ts
  const results = await Promise.allSettled(
    trackIds.map(trackId => post(ENDPOINTS.QUEUE_ADD_TRACK, { track_id: trackId }))
  );
  ```
- **Impact**: Selecting tracks A, B, C and choosing "Add to queue" can append them as B, C, A (and the larger the selection, the more likely). N broadcasts of the whole queue go out per action.
- **Siblings**: `handleBulkToggleFavorite` / `handleBulkRemove` use the same fan-out, but order does not matter there.
- **Suggested Fix**: Add the tracks sequentially (`for ... await`), or add a backend `add-tracks` batch endpoint (as playlists have `POST /api/playlists/{id}/tracks`).

### API-12: Global search result subtitle reads a field the backend never fills (cross-reference), and search errors are invisible
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/library/Hooks/useSearchLogic.ts:73-80, 114-120, 138-141`
- **Status**: Existing: #5516 (subtitle `"undefined • Album"`: `Track.to_dict()` emits `artists: string[]`, and the response model's singular `artist` is only a fallback-path field, so the wire value is null/undefined). Not re-argued.
- **Description**: Noted only for the part #5516 does not mention: the search `catch` logs to the console and shows nothing, and the three searches use bare `get()` with no `validate` guard even though `isTracksListShape`/`isAlbumsListShape`/`isArtistsListShape` exist.
- **Evidence**: `console.error('Search error:', error);` (no state set)
- **Impact**: A failing search looks like an empty result list.
- **Siblings**: API-10.
- **Suggested Fix**: Fold into the #5516 fix: run results through `transformTracks`, pass the existing list guards, and set an error state.

### PERF-02: Every library track row mounts a full context-menu stack, including a whole-queue-slice Redux subscription
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/useTrackContextMenu.ts:47,104`; `auralis-web/frontend/src/hooks/shared/useQueueRedux.ts:28-60`; `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:95,182-203`; `auralis-web/frontend/src/components/library/Items/tables/TrackTableRowItem.tsx:47,127`
- **Status**: NEW
- **Description**: `useTrackContextMenu` runs once per mounted `TrackRow` and `TrackTableRowItem`, about 35 virtualized rows in the library list (viewport plus `overscan: 10`). It calls `useQueue()` only to reach `queue.addMany`. `useQueue()` subscribes to the whole `state.queue` slice (`shallowEqual`) and runs two O(queue) reductions: `remainingTime` (`slice` plus `reduce`, re-run on every `currentIndex` change) and `totalTime`. `lastUpdated` is `Date.now()` on every `setQueue`, so each queue snapshot or track change re-renders every row hook-owner, defeating the `memo` on `TrackRow`. The same #4176 problem was already fixed for the player (`usePlayerActions`) and never applied to the queue. In addition, each row renders its own `<ContextMenu>` (an MUI `Menu`, plus `CreatePlaylistDialog` and its form hooks, plus `usePlaylistActions`) even when closed, so every row mounted while scrolling pays for them.
- **Evidence**:
  ```ts
  // useTrackContextMenu.ts:47,97
  const queue = useQueue();            // whole queue slice + 2 O(n) reductions, per row
  ...
  queue.addMany([queueTrack]);         // the only use
  // useQueueRedux.ts:31-41
  const state = useSelector((state: RootState) => state.queue, shallowEqual);
  const remainingTime = useMemo(() => state.tracks.slice(state.currentIndex + 1).reduce(...), [state.tracks, state.currentIndex]);
  ```
- **Impact**: On every track change, queue edit, or `queue_changed` snapshot, about 35 rows each recompute the queue sums and re-render their full subtree. For a 5-10k-entry queue (user queued the library) that is hundreds of thousands of element visits per track change, plus the re-render. Extra mount cost per row appears during scroll.
- **Siblings**: `useContextMenuActions.ts` (artist list) uses `useQueue()` too, but it is one instance, so it is not hot.
- **Suggested Fix**: Add a `useQueueActions()` (dispatch-only, like `usePlayerActions`) and use it in `useTrackContextMenu`. Render `<ContextMenu>` only while `contextMenuPosition` is set, or hoist a single menu to the list level.

### PERF-03: Row callbacks close over the growing `tracks` array and the selection, so every page load, selection click, play/pause and search keystroke re-renders all visible rows
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/library/useTrackSelection.ts:99,121,127`; `auralis-web/frontend/src/components/library/useSimilarTracksModal.ts:21-26`; `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:94,133,209-225`; `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:56-66,191-205`; `auralis-web/frontend/src/components/core/useSearchInput.ts:20-26`; `auralis-web/frontend/src/ComfortableApp.tsx:47,286,324`
- **Status**: NEW
- **Description**: `SelectableTrackRow` and `TrackRow` are `memo`, and `SelectableTrackRow` documents that "the parent can pass a single stable callback for all rows". Two of the callbacks the list passes down are not stable. `toggleTrack` depends on `[tracks, lastSelectedId]`. `handleFindSimilar` depends on `[tracks]` (it does `tracks.find`). `TrackListViewContent` already fixes this for `handlePlay` with a `tracksRef` but not for these two. As a result:
  - every infinite-scroll page append (the `[...prev, ...items]` in `useLibraryQuery`),
  - every selection click (`lastSelectedId` changes),
  - every search keystroke (`filteredTracks` is a new array),
  gives all rows new `onToggleSelect`/`onFindSimilar` props, so every mounted row re-renders. A fourth trigger is that `isAnyPlaying={isPlaying}` is passed to every row to dim non-current rows, so every play/pause re-renders all rows too.
  The live top-bar search is also not debounced (`useSearchInput` calls `onSearch(query)` per keystroke into the root `ComfortableApp` state). Each keystroke re-renders the app shell, re-filters all loaded tracks with three `toLowerCase()` calls each, and re-renders every row. The orphaned `library/SearchBar.tsx` has a debounce (see CMP-09), but the one in use does not.
- **Evidence**:
  ```ts
  // useTrackSelection.ts:99
  [tracks, lastSelectedId]
  // useSimilarTracksModal.ts:21-26
  const handleFindSimilar = useCallback((trackId: number) => {
    const track = tracks.find(t => t.id === trackId);
    ...
  }, [tracks]);
  // TrackListViewContent.tsx:56-66 - the fix applied to handlePlay only
  const tracksRef = useRef(tracks); tracksRef.current = tracks;
  ```
- **Impact**: Scrolling a large library re-renders about 35 rows (each with its own context-menu stack, see PERF-02) on every 50-row page load, at the moment the user is scrolling. Typing in search and clicking selection checkboxes cost similar bursts. Combined with PERF-02, each row re-render is heavier than it looks.
- **Siblings**: Same `tracks`-capturing pattern in `selectRange`/`selectAll` (not passed to rows, so harmless).
- **Suggested Fix**: Read `tracks` and `lastSelectedId` through refs inside `toggleTrack` and `handleFindSimilar` so their identity is stable. Compute dimming via a CSS ancestor selector, or a `data-any-playing` attribute on the list container, instead of a per-row prop. Debounce, or `useDeferredValue`, the search query.

### PERF-04: The WebGL starfield renders a heavy full-viewport shader at display refresh rate forever, shown at 14% (light theme 3.5%) opacity
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/background/StarfieldBackground.tsx:131-175,191`; `auralis-web/frontend/src/components/background/starfield.shaders.ts:150-296`; `auralis-web/frontend/src/styles/globalStyles.ts:326-334`; `auralis-web/frontend/src/App.tsx:49`
- **Status**: NEW
- **Description**: `AudioReactiveStarfield` is mounted at the app root and its rAF loop never stops, apart from skipping the draw when `document.hidden`. It does not pause when playback is idle or paused, and it does not honor `prefers-reduced-motion` in JS (the CSS media query only shortens CSS animations). Per fragment, per frame, the shader evaluates five `fbm` calls (6+5+4+4+3 octaves), one 5-octave ridged fbm, an aurora layer with noise, and three star layers that each loop a 3x3 neighbourhood. That is roughly 30 noise evaluations (4 sin-hashes each) plus about 135 star hashes, all `highp`, with no frame cap. The canvas is then composited at `opacity: 0.14` plus `filter: saturate(0.75)`, an extra compositor pass on a layer that changes every frame. In the light theme it is `0.035`, effectively invisible but with the same GPU cost. The canvas is sized by CSS pixels (no DPR scaling), which helps, but full viewport pixels are still shaded.
  Second-order effect: about 50 style declarations use `backdrop-filter: blur()` (every `MediaCard`, `ArtistListItem`, `Player.styles`, `AlbumTrackTable`, and others, via `tokens.glass.*`). If the canvas shows through behind them, the compositor has to re-blur those regions each frame because the backdrop changes every frame. This second-order effect is unmeasured here; it needs a profile.
- **Evidence**:
  ```ts
  // StarfieldBackground.tsx:131-141,175 - unconditional loop
  const render = useCallback(() => {
    if (!gl || !program || !canvas || !isVisibleRef.current) { animationFrameRef.current = requestAnimationFrame(render); return; }
    ...
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    animationFrameRef.current = requestAnimationFrame(render);
  ```
  ```ts
  // globalStyles.ts:326-334
  .app-ambient-background { opacity: 0.14; filter: saturate(0.75); ... }
  html[data-theme='light'] .app-ambient-background { opacity: 0.035; }
  ```
- **Impact**: Constant GPU load (and battery/thermal cost on laptops) for the whole session, including while paused and while the app sits idle in the background. The visual payoff is a 14% overlay. On integrated GPUs it competes with the compositing of the library UI, with scroll jank as the symptom.
- **Siblings**: None.
- **Suggested Fix**: Cap the loop to about 30 fps (or lower, with the nebula at half-resolution), and render a single static frame when not playing and when `prefers-reduced-motion` is set. Skip WebGL entirely in the light theme, where it is 3.5% visible. Measure with and without the canvas to decide whether the card `backdrop-filter`s should be dropped from `MediaCard` base style.

### PERF-05: `PCMStreamBuffer` always allocates 100 MB and `reset()` zero-fills all of it, on every seek
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts:61,83,210-220`; `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:68`; `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:303`; `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:99-101`
- **Status**: NEW (amplifies CMP-06)
- **Description**: Every stream, from a 30 s clip to a 1-hour mix, gets a 100 MB `Float32Array` (26.2M elements), sized by constructor default, even though `sample_rate`, `channels` and `total_duration` are known at `audio_stream_start`. `reset()` then does `this.buffer.fill(0)` over the entire 100 MB on the main thread. The positions are already reset by the two assignments above it, so the fill is pure waste (nothing reads outside `[readPos, writePos)`). It also commits every page: a fresh `Float32Array` is lazily zero-mapped, and the fill forces the whole 100 MB resident after the first seek. `seekTo()` calls `reset()` on every seek, and per CMP-06 the progress bar can issue a seek on every mousemove while dragging.
- **Evidence**:
  ```ts
  // PCMStreamBuffer.ts:210-219
  reset(): void {
    this.writePos = 0; this.readPos = 0;
    this.totalAppended = 0; this.totalRead = 0;
    if (this.buffer) { this.buffer.fill(0); }      // 100 MB memset, main thread
  }
  ```
- **Impact**: Main-thread stall per seek (order of 10-50 ms for a 100 MB memset plus page faults on the first one), repeated up to 60x/s during a progress-bar drag, plus about 100 MB of extra resident memory per session after the first seek. The per-track 100 MB external allocation also adds GC pressure on every track change.
- **Siblings**: Same `reset()` is called by the out-of-sequence recovery in `useAudioStreamingCore.ts:303`.
- **Suggested Fix**: Drop the `fill(0)` (positions alone define the live range). Size the buffer from the stream-start metadata (e.g. `min(100 MB, duration * rate * channels * 4 + slack)`).

### A11Y-02: Track-row `onKeyDown` swallows Enter/Space from the nested Play and More buttons, so they cannot be activated by keyboard
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:117-135,171-178`; `auralis-web/frontend/src/components/library/Items/tables/TrackTableRowItem.tsx:49-103,136`
- **Status**: NEW
- **Description**: `RowContainer` (`role="option"`) and `StyledTableRow` register `onKeyDown` for Enter and Space. Both call `e.preventDefault()` and run the row action (play). The row's nested controls (`TrackRowPlayButton`, `MoreButton`, the table's `IconButton`) are DOM descendants, so their keydown bubbles to the row. The handler has no `e.target === e.currentTarget` check. The `stopPropagation()` calls in `handlePlayClick` and `handleMoreClick` only guard the `click` event.
  - Enter on "More options for X": the row's `preventDefault()` cancels the button's activation, so no menu opens. The row plays the track instead.
  - Enter or Space on the in-row Pause button of the current track: the row handler calls `onPlay(trackId)` again, so the button's pause branch (`handlePlayClick`: `isCurrent && isPlaying -> onPause`) is unreachable from the keyboard.
  - `role="option"` also makes its descendants presentational (an option cannot contain interactive children in the ARIA model), and `aria-label` replaces the option's content, so screen readers in browse mode do not expose the two buttons at all.
- **Evidence**:
  ```tsx
  // TrackRow.tsx:127
  onKeyDown={(e: KeyboardEvent) => {
    if (e.key === 'Enter') { e.preventDefault(); handleRowClick(); }
    else if (e.key === ' ') { e.preventDefault(); handleRowClick(); }
  }}
  ```
- **Impact**: Keyboard users cannot open the per-track "More options" menu (Add to queue, playlist, Edit Metadata, Find Similar) through its button, and cannot pause from the row's pause button. The context menu can still be reached with the Menu key or Shift+F10, which is undiscoverable. In `TrackRow` the menu also opens at `clientX/clientY` of the click, which is not tied to the button for keyboard-originated clicks.
- **Siblings**: Both row types listed above. Queue rows (`QueueTrackItem.tsx:73`) handle only Delete/Backspace and Alt+Arrows, so they are fine.
- **Suggested Fix**: Guard both handlers with `if (e.target !== e.currentTarget) return;`. Anchor the More menu to the button's `getBoundingClientRect()` rather than pointer coordinates. Do not put focusable buttons inside `role="option"`: use `role="row"`/`gridcell`, or move the buttons out of the option.

### A11Y-03: Typing "/" in any text field is blocked and steals focus to the search box ("AC/DC" cannot be typed)
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/services/keyboardShortcutsService.ts:170-172,181-184`; `auralis-web/frontend/src/ComfortableApp.tsx:191-200`; `auralis-web/frontend/src/components/core/AppTopBarSearchInput.tsx:41-42`
- **Status**: NEW
- **Description**: The comment "Allow '/' to work even in input fields" makes `/` the one key that bypasses the input guard, so the "Focus search" shortcut fires while typing in ANY `input`/`textarea`. The service calls `event.preventDefault()` before the handler, so the character is never inserted. The handler then runs `document.querySelector('input[placeholder*="Search"]').focus(); .select()`. The shortcut is found by matching the placeholder copy, and the top-bar search field has no `aria-label` and no `role="search"` landmark.
- **Evidence**:
  ```ts
  const isSearchKey = event.key === '/' && !event.ctrlKey && ...;
  if (!isSearchKey && this.isInputElement(event.target)) return;   // '/' passes in inputs
  ...
  if (shortcut) { event.preventDefault(); shortcut.handler(); }
  ```
- **Impact**: In Edit Metadata (title/artist/album), Create/Edit Playlist, Settings text fields, and the search box itself, a `/` can never be typed. In the search field it is worse: `/` re-selects the whole text, so the next character overwrites it ("AC/DC" becomes "DC"). A common artist or title cannot be entered or corrected. The brittle placeholder lookup also drops the shortcut silently if the copy changes.
- **Siblings**: None.
- **Suggested Fix**: Remove the `/` exemption (so `/` is ignored while typing). If it should still focus search from non-text controls, that already works. Give the search input an `aria-label="Search library"`, wrap it in `role="search"`, and focus it via a ref or `data-` hook instead of the placeholder.

### A11Y-04: Eight settings controls have no accessible name (six Selects and two number inputs)
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/settings/AudioSettingsPanel.tsx:37-47,53-64,73-85`; `InterfaceSettingsPanel.tsx:40-50`; `EnhancementSettingsPanel.tsx:31-42`; `AutoScanSettings.tsx:58-72`; `AdvancedSettingsPanel.tsx:62-67,89-94`
- **Status**: NEW
- **Description**: MUI's non-native `Select` takes its name from `aria-labelledby` = the `labelId` of its `InputLabel`. None of the `InputLabel`s has an `id` and none of the `Select`s has `labelId`. The `label="..."` prop only sizes the outline notch. The resulting combobox is named by its current value alone ("16-bit", "Dark"), and the field name is never announced. `AutoScanSettings`'s Select has neither an `InputLabel` nor an `aria-label`; the preceding `SectionLabel` is a plain styled element with no association. The "Cache Size (MB)" and "Max Concurrent Scans" `TextField type="number"` also have no `label`/`aria-label`, only a sibling `SectionLabel`. The sliders and switches in the same dialog are named correctly.
- **Evidence**:
  ```tsx
  <FormControl fullWidth>
    <InputLabel>Bit Depth</InputLabel>            {/* no id */}
    <Select value={bitDepth} label="Bit Depth" ...>   {/* no labelId */}
  ...
  <SectionLabel>Cache Size (MB)</SectionLabel>
  <TextField type="number" value={cacheSize} .../>   {/* no label / aria-label */}
  ```
- **Impact**: A screen-reader user opening Settings hears "combobox, 16-bit" or "spin button, 512" with no indication of which setting it controls (Output device, Bit depth, Sample rate, Theme, Default preset, Scan interval, Cache size, Max concurrent scans).
- **Siblings**: `ReplayGain`/crossfade/volume Sliders and the Switches are correctly labelled (`aria-label` / `FormControlLabel`).
- **Suggested Fix**: Add `id`/`labelId` pairs for the six Selects (or `aria-label` through `inputProps`/`SelectDisplayProps`). Give the two number fields a `label` or `slotProps.htmlInput['aria-label']`. Make `SectionLabel` a `<label htmlFor>` where it fronts a control.

### A11Y-05: The "Now playing" announcement lives in a component that unmounts while buffering, so new-track announcements are mounted with their text rather than updated
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/TrackDisplay.tsx:77-130`; `auralis-web/frontend/src/components/player/Player.tsx:132-137`
- **Status**: NEW (the live region itself is from #2362; this is about it being conditionally rendered)
- **Description**: `TrackDisplay` has two return paths. With `isLoading` it returns a skeleton tree that contains no live region. `Player` passes `isLoading={isBuffering}`, and every track change (Next, Previous, row play, auto-advance after a seek or stall) goes through `streamingState === 'buffering'`. When buffering ends, the full branch mounts and the `aria-live="polite"` div is inserted already containing "Now playing: X by Y". A live region that is created with its content, rather than modified after it exists, is announced inconsistently (commonly not at all) by NVDA/JAWS. `PlaybackControls` avoids exactly this problem (its region is "always rendered so assistive tech observes the region before its content changes"). Separately, the outer div carries `aria-label` without a role, which assistive tech ignores.
- **Evidence**:
  ```tsx
  if (isLoading) { return (<div ... aria-label={finalAriaLabel}> ...skeleton... </div>); }  // no live region
  return (<div ...>
    <div aria-live="polite" aria-atomic="true" style={{ position: 'absolute', ... }}>
      {`Now playing: ${title}...`}
  ```
- **Impact**: A screen-reader user pressing Next often hears nothing about which track started, which is the main feedback for the action. It is unverified on a real screen reader (static analysis only).
- **Siblings**: None.
- **Suggested Fix**: Hoist the live region out of the conditional (render it above both branches, or in `Player`), and keep it mounted. Fill it from `currentTrack` once buffering ends if the announcement should wait for audio.

### A11Y-06: Library search results, empty states and loading are never announced
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:70-84,222-240`; `auralis-web/frontend/src/components/library/Views/TrackListView.tsx:86-96`; `auralis-web/frontend/src/components/shared/ui/feedback/EmptyState.tsx`; `auralis-web/frontend/src/components/core/AppTopBarSearchInput.tsx`
- **Status**: NEW
- **Description**: The top-bar search filters the track list client-side as the user types. No live region reports the result count, `NoSearchResults`/`EmptyState` has no `role="status"`, and the loading skeletons (`LibraryGridSkeleton`, `TrackRowSkeleton`) carry no `aria-busy`/status text. The only live announcements in the library path are the view-change label (`AppViewAnnouncement`) and, for the Settings dialog, scan status. The one component that did announce result counts (`library/Search/GlobalSearch.tsx:64`) is unmounted (see CMP-09).
- **Evidence**: `rg "aria-live|role=\"status\"" components/library/Views components/library/CozyLibraryView.tsx components/shared/ui/feedback` returns no match. `CozyLibraryView.tsx:232`: `searchQuery ? <NoSearchResults query={searchQuery} /> : ...`.
- **Impact**: A screen-reader user typing a query hears nothing about how many tracks match, or that none do, and gets no cue that a list is reloading (it also resets, see CMP-07).
- **Siblings**: Album/artist grids and playlist detail views use the same empty-state components.
- **Suggested Fix**: Add one visually hidden `role="status"` region in the library container that announces "N tracks" / "No results for X" / "Loading", debounced against typing. Give `EmptyState` `role="status"`.

### TST-03: Vacuous error assertions: `expect(error).toBeDefined()` on `ApiError | null` state, plus `try/catch` that cannot fail
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `src/hooks/api/__tests__/useRestAPI.test.ts:199,216,305,374,411,446,484,746,843,860,935`; `src/hooks/player/__tests__/usePlaybackQueue.test.ts:308,683,760,1042,1084,1126,1174`
- **Status**: NEW
- **Description**: `useRestAPI` and `usePlaybackQueue` both declare `error` as `useState<ApiError | null>(null)`. `expect(null).toBeDefined()` passes, so at least 18 "should handle X errors" tests (POST/PUT/PATCH/DELETE errors, non-Error rejection, malformed JSON, queue rollback) assert nothing about the error state. Several of them are on the exact paths where dim_3 found bugs (HK-05 successful POST reported as failure, HK-06 timeout surfaced as `AbortError`). A second pattern compounds it: `try { await fn() } catch (e) { /* Expected */ }` or `catch (err) { expect(err).toBeDefined() }` — if the call stops rejecting, the test still passes. 23 such catch-and-ignore sites across 6 files; `expect.assertions` / `expect.hasAssertions` is used 0 times in the repo.
- **Evidence**:
  ```ts
  // useRestAPI.test.ts:292-306
  it('should handle POST errors', async () => {
    mockFetchError(400, 'Bad Request');
    ...
    try { await result.current.post('/api/test', {}); } catch (err) { // Expected }
    expect(result.current.error).toBeDefined();   // initial value is null -> passes
  });
  // usePlaybackQueue.test.ts:300-308
  try { await result.current.setQueue(mockTracks); } catch (err) { expect(err).toBeDefined(); }
  expect(result.current.error).toBeDefined();
  ```
- **Impact**: Error handling of the REST hook and queue hook is effectively untested; the suite stays green if errors are never recorded or never thrown.
- **Siblings**: `src/store/__tests__/testFixtures.test.ts:281` (`testScenarios.error` toBeDefined); the `catch` pattern appears in `useRestAPI.test.ts`, `usePlaybackQueue.test.ts`, `useLibraryQuery.test.ts`, `useQueueMutations.*`.
- **Suggested Fix**: Replace with `expect(result.current.error).not.toBeNull()` / `toMatchObject({ statusCode: 400 })`, and use `await expect(result.current.post(...)).rejects.toThrow(...)` instead of try/catch.

### TST-04: `useAppDragDrop` spec: 11 of 16 tests assert nothing real, and the reorder tests pin the buggy routing as expected
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `src/hooks/app/__tests__/useAppDragDrop.test.ts:60-300,405-475`; production `src/hooks/app/useAppDragDrop.ts:60-110`
- **Status**: Existing: #5189 (referenced by the spec itself; not present in the 200-issue `issues.json` snapshot, so open/closed state unverified — the bug is still in the code)
- **Description**: Two tests have no `expect` at all ("ignores drop with no destination", "ignores drop in same position" end on the comment "MSW will not handle the request, but that's OK"). Nine more end in `expect(result.current).toBeDefined()` after a comment that says "we just verify the success callback was called" — but never assert `mockSuccess` / `mockInfo` or which endpoint was hit. The `describe('reorder routing is broken (#5189)')` block then locks in the defect: a same-list drag in `queue` or `playlist-N` hits the ADD endpoint because `handleDragEnd` tests `destination.droppableId === 'queue'` / `startsWith('playlist-')` before `=== source.droppableId`. The assertions are `expect(hits).toEqual(['POST add-track']); // should be ['PUT move']`. Once #5189 is fixed these two tests must be inverted, and until then the file reads as passing coverage of drag-reorder.
- **Evidence**:
  ```ts
  expect(hits).toEqual(['POST add-track']);   // should be ['PUT move']
  expect(hits).toEqual(['POST playlist-add']); // should be ['PUT playlist-reorder']
  ```
- **Impact**: Drag-reorder in the queue duplicates the track instead of moving it (user-visible), and the test file gives false assurance for the other 9 cases.
- **Siblings**: none
- **Suggested Fix**: Fix #5189 and flip the two characterization tests; give the other nine real assertions (endpoint hit + `mockSuccess` message + error toast text).

### TST-05: Integration specs whose titles promise behaviour but assert only that a heading/element rendered
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `src/tests/integration/library-management/library-management.test.tsx:199-250` (search by title / artist / album); `src/tests/integration/library-management/playlist-management.test.tsx:118-142` (edit), `:144-166` (delete), `:305-345` (drag within playlist, drag from library), `:347-376` (drag from queue)
- **Status**: NEW
- **Description**: The #5186 clean-up kept these as the "reference pattern" integration specs, but at least 8 tests cannot fail on the behaviour in their name. The three search tests render `CozyLibraryView`, then assert `getByText(/All tracks in your library/i)` with the comment "Search input UI is not currently integrated... verifies the view renders correctly for future search integration" (identical assertion in all three). Edit/delete playlist tests right-click then assert `expect(playlist).toBeInTheDocument()` on the element they already held, with comments "Context menu may or may not appear in test environment". The drag tests assert the playlist label exists and say real drag simulation is out of scope. In the edit test, a `waitFor` callback contains a side effect and a floating promise (`user.click(editOption)` with no await), which also retries the click each poll; `waitFor` never fails because the callback never throws.
- **Evidence**:
  ```tsx
  // playlist-management.test.tsx:134-143
  await waitFor(() => {
    const editOption = screen.queryByText(/edit/i);
    if (editOption) { user.click(editOption); }          // floating, side-effecting
  }, { timeout: 1000 });
  // Note: Context menu may or may not appear in test environment
  expect(playlist).toBeInTheDocument();
  ```
- **Impact**: The README presents these specs as the template for future integration tests; the "Search & Filter", "Edit/Delete playlist" and "Drag & Drop" groups count toward the advertised totals while verifying nothing.
- **Siblings**: `src/components/library/AlbumCharacterPane/__tests__/AlbumCharacterPaneComponents.test.tsx:79,97,185` ("renders without crashing"), `src/components/settings/__tests__/SettingsDialog.test.tsx:100-112` (conditional `if (cancelButtons.length > 0)` and no assertion), `src/components/player/__tests__/QueueRecommendationsPanel.test.tsx:324-345` ("should call addTrack when add button clicked" — never clicks or asserts), `src/hooks/library/__tests__/useLibraryQuery.test.ts:1077` ("should abort request on unmount" — no assertion, mocks `AbortController`).
- **Suggested Fix**: Delete the placeholder tests or rewrite them (open the context menu via `userEvent`, `await` the click, assert the service call / dialog); drop the "future integration" tests rather than keep them green.

### TST-06: `vi.mock` targets that do not exist (mock is a no-op) — including the likely root cause of 19 baselined failures
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `src/components/__tests__/Integration.test.tsx:36,63,73,83,92,115` (≈100 lines of dead mocks); `src/components/__tests__/redux-flow.test.tsx:71`; `src/components/library/__tests__/LibraryEmptyState.test.tsx:16`; `src/components/library/Items/tracks/__tests__/TrackRowMemoization.test.tsx:21`
- **Status**: NEW (#5424 fixed only the duplicate WebSocketContext mock in `Integration.test.tsx`)
- **Description**: A resolver sweep over all `vi.mock/doMock` string targets in `src/**/*.test.*` finds 9 that resolve to nothing. `Integration.test.tsx` mocks `@/services/websocket/protocolClient`, `@/hooks/usePlayerCommands`, `usePlayerStateUpdates`, `useQueueCommands`, `useWebSocketProtocol`, `useStandardizedAPI` — all deleted modules (the real hook is `hooks/shared/useStandardizedAPI`). `redux-flow.test.tsx:71` automocks the same stale `@/hooks/useStandardizedAPI`. `LibraryEmptyState.test.tsx:16` mocks `../../shared/EmptyState` (the component actually imports `@/components/shared/ui/feedback`), so the test's `data-testid="empty-library"` stubs never apply and the real components render — the spec has 19 entries in `test-baseline.json`, which is very likely why. `TrackRowMemoization.test.tsx:21` mocks `../../shared/ContextMenu` (resolves to `components/library/Items/shared/`, not `components/shared/ContextMenu`), so the real ContextMenu renders in a test that says it "reduces noise". The "Integration" file also runs only Redux reducer dispatches plus one `ConnectionStatusIndicator` render.
- **Evidence**:
  ```ts
  // LibraryEmptyState.test.tsx:16   (component imports '@/components/shared/ui/feedback')
  vi.mock('../../shared/EmptyState', () => ({ EmptyLibrary: ..., NoSearchResults: ... }));
  ```
- **Impact**: Stale mocks hide that the tests no longer isolate what they claim; 19 baseline entries (and the 100-line mock preamble) cannot be cleared without fixing the path. Fixing LibraryEmptyState's path should let the baseline shrink.
- **Siblings**: the 4 files above.
- **Suggested Fix**: Delete the dead mocks in `Integration.test.tsx` / `redux-flow.test.tsx`, repoint the LibraryEmptyState and TrackRowMemoization mocks to the real module paths, rerun and shrink `test-baseline.json`. Add a lint-style guard (like `integration-tests-exercise-production-code.test.ts`) that resolves every `vi.mock` string.

### TST-07: Baseline ratchet has no test-count floor and ignores the runner's exit code
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/scripts/check-test-baseline.mjs:52-100,150-190`; `.github/workflows/frontend-test.yml` ("Run vitest: `pnpm run test:ci || true`")
- **Status**: NEW (complements closed #5344 and the `--strict-stale` work)
- **Description**: The script does fail on a missing/unparsable report and on `numTotalTests == 0`, and `--strict-stale` is wired in CI (verified; `pnpm run test:baseline -- --strict-stale` forwards the flag). Remaining gaps: (1) the only sanity check is "non-zero" — the baseline records `generatedFrom.totalTests: 3349` but nothing reads it, so a runner that OOMs (the suite needs the 2 GB heap) or an `exclude`/`include` change that silently drops hundreds of specs still reports "No new test failures". Specs that never ran are not failures, and baseline entries that are absent from the report are only informational ("notRun"). (2) The test step is `|| true`, so unhandled rejections / worker crashes / teardown timeouts that make vitest exit non-zero are invisible unless they also produce a `failed` assertion or suite. (3) `notRun` entries for deleted or renamed specs never trip anything, so a baseline can accumulate dead entries (currently none: all 18 spec files exist and entry names match).
- **Evidence**:
  ```js
  if (!parsed.numTotalTests) { ... process.exit(1); }   // only check on size
  ...
  const notRun = [...baseline].filter((id) => !present.has(id)).sort();   // informational only
  ```
- **Impact**: A partial/crashed vitest run can pass the gate green; test-suite shrinkage goes unnoticed.
- **Siblings**: `scripts/check_pytest_baseline.py` (backend equivalent, out of scope).
- **Suggested Fix**: Fail when `numTotalTests` is below e.g. 95% of `generatedFrom.totalTests` (or the count of collected suites drops), and have CI treat the vitest exit code as informational only when the JSON report exists and the run completed (`numTotalTestSuites` matches the spec count).

## Low Findings (40)

### CMP-09: 34 orphaned component files (~3,800 lines) are never mounted from the app
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: see Evidence (all under `auralis-web/frontend/src/components/`)
- **Status**: Existing: #5521 for `player/TrackInfo.tsx` only. The rest is NEW.
- **Description**: An import-graph walk from `index.tsx` (following dynamic imports and resolving barrel re-exports by imported name) leaves these component files unreachable from production code. They are reachable only from their own barrels or tests. Several have tests that keep them looking alive. Each was spot-checked with a word-level grep for its exported names outside tests and comments.
- **Evidence**:
  - Queue extras: `player/QueueRecommendationsPanel/*` (4 files), `player/QueueSearchPanel/*` (2), `player/QueueStatisticsPanel.tsx` + `.parts.tsx`, `player/ShuffleModeSelector.tsx`, `player/TrackInfo.tsx`
  - Search: `library/SearchBar.tsx` (240), `navigation/SearchBar.tsx` + `SearchInputAdornments.tsx` + `SearchKeyboardHint.tsx`, `CozyLibraryView/LibrarySearchControls.tsx`, `library/Search/*` (6), `library/Hooks/useSearchLogic.ts`
  - Connection: `shared/ConnectionStatusIndicator.tsx`, `shared/ConnectionDetailsPanel.tsx`
  - Misc: `shared/feedback/ProcessingToast.tsx` + `ProcessingStatsChips.tsx`, `shared/ui/badges/ParameterChip.tsx`, `shared/ui/loaders/LoadingSpinner.tsx`, `shared/ui/media/AlbumArtDisplay.tsx`, `track/TrackCardInfo.tsx`, `track/TrackCardOverlay.tsx`, `library/Controls/LibraryHeader.tsx`, `library/LibraryEmptyState.tsx`, `library/Items/albums/AlbumGridContent.tsx`, `library/Items/utilities/InfiniteScrollTrigger.tsx`
  - `CozyLibraryView.tsx`'s header comment still lists `LibrarySearchControls` and `LibraryEmptyState` as parts, but neither is imported.
- **Impact**: Dead UI that gets edited and audited (a11y fixes landed in `QueueSearchPanel`), a second `SearchBar` implementation, and a misleading architecture description. The app currently exposes no queue search, recommendations, statistics, shuffle-mode selector or connection details UI.
- **Siblings**: Extends the dead-subtree pattern from the 2026-07-25 and 07-29 audits.
- **Suggested Fix**: Decide per cluster: delete, or mount and track under a real issue. Fix the stale header comment.

### CMP-10: Dead queue-operation plumbing is passed through `TrackListView` into `TrackGridView`, which discards it
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Views/TrackListView.tsx:77-83,111-124`, `auralis-web/frontend/src/components/library/Views/TrackGridView.tsx:27-35,55-62`, `auralis-web/frontend/src/components/library/Views/useQueueOperations.ts`
- **Status**: NEW
- **Description**: `TrackListView` builds four queue handlers with `useQueueOperations({})` and passes them, together with `hasMore={false}` and `currentTrackId`, to `TrackGridView`. `TrackGridView` destructures them as `_onRemoveTrack`, `_onReorderQueue`, `_currentTrackId` and so on, and never uses them. `useQueueOperations` has no other importer. A `useToast` subscription and four callbacks are created per render for nothing.
- **Evidence**:
  ```tsx
  // TrackGridView.tsx
  currentTrackId: _currentTrackId, onRemoveTrack: _onRemoveTrack, onReorderQueue: _onReorderQueue, ...
  ```
- **Impact**: Misleading prop contract, dead hook, and queue-service functions that look reachable but are not.
- **Siblings**: Same family as closed #5396 (unused `AppMainContent` props).
- **Suggested Fix**: Remove the props from `TrackGridViewProps`, delete `useQueueOperations` and its call, and drop the `hasMore` / `currentTrackId` props.

### CMP-11: Library action callbacks are drilled through 3 intermediate components
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:243-260`, `auralis-web/frontend/src/components/library/Views/TrackListView.tsx`, `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:201-214`, `auralis-web/frontend/src/components/library/Items/tracks/SelectableTrackRow.tsx:27-80`
- **Status**: NEW
- **Description**: `onEditMetadata`, `onFindSimilar` and `onPause` travel `CozyLibraryView`, then `TrackListView`, then `TrackListViewContent`, then `SelectableTrackRow`, and only reach `TrackRow` / `useTrackContextMenu`, which uses them. `SelectableTrackRow` redeclares 10 callbacks, five of which no caller supplies (this is the root of CMP-02). `onPause` could come from `usePlaybackState` directly. The dialogs (`EditMetadataDialog`, `SimilarTracksModal`) are opened from deep rows but owned at the top, so the hop chain exists only to reach them. `currentTrackId` / `isPlaying` are also drilled and compared per row; that one is deliberate for `memo` and not a defect.
- **Evidence**: See the four files above; a prop-by-prop trace shows `TrackListView` only forwards.
- **Impact**: Every new row action requires editing four signatures. It is how CMP-02 happened.
- **Siblings**: `onOpenSettings` / `onNavigate` go `ComfortableApp`, then `AppSidebar`, then `Sidebar`, then `SidebarFooter` / `SidebarContent` (3 hops, simple callbacks, tolerable).
- **Suggested Fix**: Put dialog-open actions behind a small context or a Redux slice (`openEditMetadata(trackId)`) so rows dispatch directly. Remove the unused optional props from `SelectableTrackRow` / `TrackRow` until needed.

### CMP-12: `ComfortableApp.tsx` is 431 lines (project limit 300)
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:1-431`
- **Status**: NEW
- **Description**: The only non-test file in scope over 300 lines (`wc -l`, 205 component files plus `App*.tsx`). About 150 lines are the inline keyboard-shortcut table, and about 100 are four near-identical inline `ErrorBoundary` fallback `Box`es (the fallbacks differ only in text). Closest to the limit: `components/library/CozyLibraryView.tsx` (298), `components/library/AlbumCharacterPane/AlbumCharacterPane.tsx` (295), `components/player/QueuePanel/QueuePanelExpanded.tsx` (278).
- **Evidence**: `431 ComfortableApp.tsx`
- **Impact**: Maintainability only.
- **Siblings**: None over the limit.
- **Suggested Fix**: Extract `useAppShortcuts(...)` and a shared `<RegionErrorFallback message=...>`. This also helps CMP-08.

### CMP-13: Queue toggle button advertises a `Q` shortcut that does not exist
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:176`
- **Status**: NEW
- **Description**: The button has `title="Toggle queue (Q)"`. No handler for `q` / `Q` exists in `ComfortableApp`'s shortcut table or anywhere else in `src/` (word grep over non-test code).
- **Evidence**: `title="Toggle queue (Q)"`
- **Impact**: Misleading tooltip. The key does nothing.
- **Siblings**: None.
- **Suggested Fix**: Add the shortcut to `ComfortableApp` (with state lifted or a Redux flag), or drop it from the title.

### CMP-14: "Recently touched albums" is recorded from hover state, so keyboard and touch activation are never tracked
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Views/LibraryViewRouter.tsx:140-148`, `auralis-web/frontend/src/components/shared/MediaCard/MediaCard.tsx:111-124`
- **Status**: NEW
- **Description**: `AlbumsView.handleAlbumClick` calls `touchAlbum(...)` only when `hoveredAlbumTitle` is set. That state is set exclusively by `MediaCard`'s `onMouseEnter` (`onHoverEnter`). The card's "open" control is a native `<button>`, so Enter or Space activation by keyboard, and tap on touch, fire `onClick` with no prior hover. The album then opens but is never added to the recently-touched list.
- **Evidence**:
  ```tsx
  const handleAlbumClick = useCallback((albumId) => {
    if (hoveredAlbumTitle) { touchAlbum(albumId, hoveredAlbumTitle, ...); }
  ```
- **Impact**: Inconsistent feature for keyboard users. Also couples a side effect to hover timing.
- **Siblings**: None.
- **Suggested Fix**: Pass `(albumId, title, artist)` through the click callback (the `AlbumCard` already has them) instead of reading hover state.

### CMP-15: Deferred callbacks in two components are never cancelled
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/EditMetadataDialog/EditMetadataDialog.tsx:51-60`, `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:113-129`
- **Status**: NEW
- **Description**: (a) `handleSave` runs `setTimeout(() => onClose(), 1000)` with no handle or cleanup. Because the dialog now stays mounted and `CozyLibraryView` owns `open`, closing manually and opening another track's editor within that second lets the stale timer close the new dialog. (b) The roving-focus `tryFocus` re-queues `requestAnimationFrame` until the row exists, with no cancel or attempt cap, so it spins indefinitely if the list unmounts or the row never mounts.
- **Evidence**: `setTimeout(() => { onClose(); }, 1000);` and `else { requestAnimationFrame(tryFocus); }`
- **Impact**: A narrow race that closes the wrong dialog, and a possible leaked 60 Hz callback loop. Both are rare.
- **Siblings**: `useQueueKeyboardReorder.ts:110` retries once only, so it is fine.
- **Suggested Fix**: Store the timer id and clear it in an effect cleanup (or on dialog close). Cap and cancel the rAF retry on unmount.

### CMP-16: Numeric settings inputs write `NaN` into pending changes
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/settings/AdvancedSettingsPanel.tsx:66,93`
- **Status**: NEW
- **Description**: `onChange={(e) => onSettingChange('cache_size', parseInt(e.target.value))}`. Clearing the field gives `parseInt('') === NaN`, which is stored in `pendingChanges`. The controlled `<TextField value={NaN}>` triggers React's NaN warning, and Save serialises `null` (`JSON.stringify(NaN)`) into the PUT body. Min/max are advisory HTML attributes only.
- **Evidence**: `parseInt(e.target.value)` with no `Number.isNaN` guard.
- **Impact**: A save with a blank numeric field sends `null` and surfaces only a generic "Failed to save settings".
- **Siblings**: `max_concurrent_scans` (line 93).
- **Suggested Fix**: Ignore or clamp non-finite values, or keep the raw string in local state and commit on blur.

### RDX-06: Preset mirrors are hand-copied instead of derived from `EnhancementPreset` / `ENHANCEMENT_PRESETS`
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:25-26`, `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:56-59`, `:170-171`
- **Status**: NEW (sibling of closed #5404, which fixed only `useEnhancementControl.ts`)
- **Description**: The slice type is correct (`PresetName = 'adaptive'`, not a bare `string`). But it is an independent literal duplicating `EnhancementPreset` (`types/domain.ts:154`). The runtime guard is `const VALID_PRESETS: readonly string[] = ['adaptive']`, a bare `string[]` copy of `ENHANCEMENT_PRESETS`, followed by an `as PresetName` cast. If the preset list changes, the type, the guard and the domain list must all be edited by hand, and the cast hides a mismatch.
- **Evidence**:
  ```ts
  const VALID_PRESETS: readonly string[] = ['adaptive'];
  if (state.current_preset && VALID_PRESETS.includes(state.current_preset)) {
    dispatch(setPreset(state.current_preset as PresetName));
  ```
- **Impact**: Latent drift risk only; behaviour is correct today.
- **Siblings**: none beyond these two.
- **Suggested Fix**: `export type PresetName = EnhancementPreset;` and `ENHANCEMENT_PRESETS.includes(...)` (as `useEnhancementControl` now does) instead of the local list and cast.
- **Merged from TS-06** (LOW, Preset type is mirrored four times as separate literals and by bare `string` in five places; `usePlayerStateSync` narrows with a string-array membership check plus `as`): ``auralis-web/frontend/src/types/ws/player.ts:57` (`current_preset: string`); `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:58-59,170-171`; `auralis-web/frontend/src/store/slices/playerSlice.ts:25-26`; `auralis-web/frontend/src/types/ws/enhancement.ts:26-27`; `auralis-web/frontend/src/` — Verified state: **no removed preset name survives** in production code, `EnhancementPreset = 'adaptive'` (`types/domain.ts:154`), the backend `EnhancementPresetLiteral = Literal["adaptive"]` and every mirror agree today, and the single-option Select is intended. The weakness is structural: `types/ws/enhancement.ts` and `playerSlice.PresetName` each re-declare the literal `'adaptive'` instead of aliasing `EnhancementPreset`; `usePlayerStateSync` keeps a third copy as `VALID_PRESETS: readonly string[]` and narrows via `includes(...)` then `as PresetName`; and the wire `RawPlayerStateData.current_preset` is typed `string` although the backend `PlayerStatePayload.current_preset` is `EnhancementPreset`. `CurrentTrackInfo.preset: string` (the preset re-sent on seek) and `UserSettings/SettingsUpdate.default_preset: string` are likewise unconstrained (the backend settings model types `default_preset` as `EnhancementPresetLiteral | None`). A stale comment in `types/ws/streaming.ts:35-39` refers to an `isEnhancementPreset` function that no longer exists in `types/domain.ts`.

### RDX-07: The `connection` slice is write-dead in production: nothing sets `wsConnected`, and the API health poll lives only in an unmounted component
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/connectionSlice.ts:48-60`, `auralis-web/frontend/src/hooks/shared/useAPIHealthPoll.ts:20-80`, `auralis-web/frontend/src/components/shared/ConnectionStatusIndicator.tsx:70-80`, `auralis-web/frontend/src/store/selectors/player.ts:73-95`
- **Status**: NEW (adjacent to Existing #5354, #5129; not covered by either)
- **Description**: Grepping all non-test source finds no dispatcher of `setWSConnected`, `incrementReconnectAttempts` or `resetReconnectAttempts`. The WS connection state lives in `WebSocketContext`. `setAPIConnected`/`setLatency` are dispatched only by `useAPIHealthPoll`, and its sole caller is `ConnectionStatusIndicator`, which no production file imports. Even when mounted, `startPolling()` only arms `setInterval`, so the first check comes after 5 s and `apiConnected` starts `false`. The only live writer is the error middleware's `connection.setError` forward.
- **Evidence**:
  ```ts
  // selectors/player.ts: canPlay can never be true in production
  canPlay: wsConnected && apiConnected && currentTrack !== null,
  ```
- **Impact**: `selectPlaybackState.canPlay`, `selectConnectionStatus` and the transport-error forwarding in `errorTrackingMiddleware` (`player/setStreamingError` -> `connection.setError`) feed state nobody renders. Anyone who wires UI to these will see a permanently "disconnected" app.
- **Siblings**: #5354 (isLoading/error never dispatched), #5129 (dead selector cluster).
- **Suggested Fix**: Either bridge `WebSocketContext.connectionStatus` and the health poll into the slice from an always-mounted component (and poll once immediately), or delete the slice together with #5129/#5354.

### RDX-08: `player.streaming.normal` and the `'normal'` stream type are never written in production
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:38-41`, `:57-60`, `auralis-web/frontend/src/store/slices/playerStreamingReducers.ts:25-27`, `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:171-177`
- **Status**: NEW (adjacent to Existing #5357, where `StreamingInfo.intensity` is write-only)
- **Description**: `usePlayNormal` is gone. `playNormal` is a wire-command variant of the single `useAudioStreamingCore({ streamType: 'enhanced', acceptNormalStream: true })`. Every `startStreaming/updateStreamingProgress/completeStreaming/setStreamingError/resetStreaming/setPlaybackStalled` dispatch in non-test code passes `streamType: 'enhanced'`, so `state.player.streaming.normal` is permanently `initialStreamingInfo`. Every reducer still pays for the `streamType` indirection.
- **Evidence**: grep of `streamType: 'normal'` and `resetStreaming('normal')` in non-test code returns nothing.
- **Impact**: Maintenance trap only: a reader can think normal-mode progress is tracked separately. It is not, because normal and enhanced playback share the `enhanced` slot.
- **Siblings**: none.
- **Suggested Fix**: Collapse `streaming` to one `StreamingInfo`, or record the mode as a field of the single stream (`wireType: 'normal' | 'enhanced'`) instead of a parallel slot.

### RDX-09: `setCurrentTrack(null)` leaves `duration` and `currentTime` at the previous track's values
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:84-95`, caller `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:134-136`
- **Status**: NEW
- **Description**: The reducer updates `duration`/`currentTime` only inside `if (action.payload)`. A `player_state` with `current_track: null` (queue cleared) yields `currentTrack: null` but a stale `duration` and `currentTime`. `selectPlaybackProgress`, `selectFormattedTime` and `selectPlaybackState` then report progress for a track that no longer exists.
- **Evidence**:
  ```ts
  state.currentTrack = action.payload;
  if (action.payload) { state.duration = action.payload.duration; state.currentTime = 0; }
  ```
- **Impact**: Wrong derived values in the memoized selectors. The Player UI reads `currentTrack?.duration ?? 0`, so there is no visible effect today.
- **Siblings**: none.
- **Suggested Fix**: In the null branch, set `duration = 0` and `currentTime = 0`.

### RDX-10: `useQueueMutations` takes its rollback snapshot from a render-time ref and shares one `isLoading` across concurrent mutations
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:87-91`, `:142-170`, `:234-246`
- **Status**: NEW (the generation guard from #4836 is intact; this is the remaining gap)
- **Description**: `stateRef.current` is assigned during render, so two mutations started in the same tick (before React re-renders) both snapshot the pre-first-mutation queue. If the second fails and is the newest, `reduxSetQueue(previousTracks)` rolls back past the first, successful mutation. `reorderQueue` also computes the optimistic order from the same stale ref. `isLoading` is one boolean: the first mutation to finish clears it while others are still in flight.
- **Evidence**:
  ```ts
  stateRef.current = { tracks, currentIndex, isShuffled, repeatMode };   // render-time
  const previousTracks = stateRef.current.tracks;                         // runOptimistic
  ...
  finally { setIsLoading(false); }
  ```
- **Impact**: Needs programmatic back-to-back calls. Discrete UI events flush a render between clicks, and no current caller batches calls. Briefly wrong queue after a failed second request, and the spinner clears early.
- **Siblings**: `toggleShuffle`/`setRepeatMode` read `stateRef` the same way.
- **Suggested Fix**: Read the snapshot with `store.getState()` (via `useStore`) at call time, and use an in-flight counter instead of a boolean.

### HK-08: Overlapping `playTrack` clicks can leave the backend queue on one track while another plays
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:46-81` with `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:92-108`
- **Status**: NEW
- **Description**: `playTrack(B)` POSTs the queue (`[B]`) and then calls `startTrack(B)`. `startTrack` goes through `runTransportCommand`, which silently returns when a previous command is still pending. That window includes the `fetch('/api/library/tracks/{id}')` inside `playEnhanced`. A second click on a different row inside that window means the queue POST for B succeeds while `startTrack(B)` is dropped without any toast. Track A keeps playing, the backend queue is `[B]`, and Redux follows `queue_changed`.
- **Evidence**:
  ```ts
  if (commandPendingRef.current) return;     // PlaybackSessionContext.tsx:93 (returns a resolved promise, no signal to caller)
  ```
- **Impact**: Rare (tens of ms, longer when the backend is loaded); the visible result is "clicked B, A kept playing, queue shows B".
- **Siblings**: `handleNext`/`handlePrevious` coalesce the same way by design (#4835).
- **Suggested Fix**: Have `runTransportCommand` return a boolean/rejected promise when it drops a command, or make a later `startTrack` supersede the pending one (latest-wins) rather than being discarded.

### HK-09: `audio_chunk_meta` seq-desync tracking is not reset across disconnect, so a restarted backend can trigger a false DESYNC that tears down the resumed stream
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:146-175` (state at `:61-71`, `:113-125`)
- **Status**: NEW
- **Description**: `checkSeqForDesync` resets `expectedSeq` only when `stream_epoch` differs from `seqStreamEpoch`. Nothing resets either field on socket close or reconnect. The backend's epoch counter is per-process and starts at 1 (`audio_stream_controller.py:99`). `useAudioStreamingCore` already handles this exact hazard for its own `streamEpochRef` ("a backend restart restarts the count", cleared when `!isConnected`), but `connState` was missed. Scenario: first stream of a session (epoch 1, no seeks yet), backend restarts, the WS reconnects and `replayQueueAndResume` re-issues the stream, which is again epoch 1, so the epoch comparison sees "same stream", `seq 0 !== expectedSeq N`, and a synthetic `audio_stream_error` DESYNC is dispatched. `handleStreamError` then calls `cleanupStreaming()`, killing the resumed stream (no `recovery_position`, so no auto-resume).
- **Evidence**:
  ```ts
  if (stream_epoch !== connState.seqStreamEpoch) { connState.seqStreamEpoch = stream_epoch ?? null; connState.expectedSeq = null; }
  if (connState.expectedSeq !== null && seq !== connState.expectedSeq) { ... dispatch(desyncError) }
  ```
- **Impact**: Narrow (first stream of an app session, then backend restart; mostly dev reloads), but it defeats the reconnect-resume path (#3185) in exactly the restart case.
- **Siblings**: none.
- **Suggested Fix**: Reset `connState.expectedSeq` and `seqStreamEpoch` (and `pendingMeta`) in the manager `close` handler, or on every `audio_stream_start`.

### HK-10: `useAudioStreamingCore` subscribes on the whole `wsContext`, re-subscribing on every status flicker and disarming the stream-start watchdog
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:444-503` (also `:580-593`)
- **Status**: NEW (sibling of the #4668 fix applied to `useEnhancedSeek` and `useFingerprintStatus`)
- **Description**: The effect depends on `[wsContext, ...]`. `wsContext` is the memoized context value, whose identity changes with every `isConnected`/`connectionStatus` change. Other hooks were fixed (#4668) to depend on `wsContext.subscribe` only. Here, every connection-status change tears down and re-registers four subscriptions, and the cleanup calls `clearStreamStartWatchdog()`. A WS drop or reconnect between sending `play_*` and the first stream message therefore silently disarms the #4433 45 s watchdog, so a hung worker leaves the UI in `buffering` forever. The unsubscribe/resubscribe itself is synchronous inside one commit, so no messages are lost.
- **Evidence**:
  ```ts
  }, [wsContext, clearStreamStartWatchdog, streamType, acceptsStreamType, logPrefix]);   // :503
  return () => { clearStreamStartWatchdog(); unsubscribeStart(); ... };                  // :494
  ```
- **Impact**: Minor: lost watchdog in a connection-flap edge case, and needless subscription churn. The `setResumePositionGetter` effect (`:580-593`) has the same over-broad dependency.
- **Siblings**: `useAudioStreamingCore.ts:580-593`.
- **Suggested Fix**: Depend on `wsContext.subscribe` (and `wsContext.setResumePositionGetter`) only; do not clear the watchdog in this effect's cleanup (unmount is already covered by `useStreamStartWatchdog`).

### HK-11: `useScanProgress` state is per hook instance, so `ScanStatusCard` loses the last scan result and progress each time it remounts
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useScanProgress.ts:75-173`; consumers `auralis-web/frontend/src/components/settings/ScanStatusCard.tsx:~30`, `auralis-web/frontend/src/components/settings/SettingsDialog.tsx:46`
- **Status**: NEW
- **Description**: The hook keeps all scan state (`lastResult`, `current`, `total`, `percentage`, `currentFile`) in local `useState`, fed only by live WS frames. `SettingsDialog` holds one persistent instance (for the tab badge), while `ScanStatusCard` creates a second instance each time the dialog content mounts (MUI Dialog unmounts closed content, and the Library tab is not always active). A fresh instance starts at `INITIAL_STATE`, so the card shows no "last scan" result after close/reopen. If a scan is running it shows "Scanning…" with 0/0 and an indeterminate bar until the next progress frame. The #4821 resync only restores `isScanning`.
- **Evidence**:
  ```ts
  const [state, setState] = useState<ScanStatus>(INITIAL_STATE);   // per instance
  // resync on connect restores only isScanning:
  return prev.isScanning ? prev : { ...prev, isScanning: true };
  ```
- **Impact**: Cosmetic/informational: last-scan summary and failure list vanish when the dialog is closed and reopened; two parallel subscriptions do the same work.
- **Siblings**: none.
- **Suggested Fix**: Move scan status into a small Redux slice (or a module-level store like `useArtworkRevision` uses) fed by one subscription, and have both consumers read it.

### TS-07: Declared fields no transport populates: `Track.loudness` and the over-wide WS `TrackInfo`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/domain.ts:45`, `auralis-web/frontend/src/api/transformers/types.ts:104`, `auralis-web/frontend/src/api/transformers/trackTransformer.ts:57`, `auralis-web/frontend/src/types/ws/base.ts:40-69`
- **Status**: Existing: #5524 (crestFactor/centroid; the `Track` domain type and transformer have since dropped those two, but `loudness` remains and `TrackInfo` in `ws/base.ts` still carries `loudness`, `crest_factor`, `centroid`)
- **Description**: `Track.to_dict()` emits `lufs_level`, never `loudness` (the backend comment in `routers/serializers.py:62-65` says so explicitly); `loudness` exists only on the getattr-fallback path. No frontend code reads `track.loudness`. The WS `TrackInfo` additionally declares `genre`, `year`, `bitrate`, `sample_rate`, `bit_depth`, `date_added`, `date_modified`, `loudness`, `crest_factor`, `centroid`, which the backend WS `TrackPayload` (`id, title, artist, album, duration, artwork_url, format`) never sends.
- **Evidence**: `types/ws/base.ts:64-66`: `loudness?: number; crest_factor?: number; centroid?: number;`
- **Impact**: False contract only; a component that reads these gets `undefined` with no error.
- **Siblings**: `types/domain.ts:299` `SortOptions` (field list includes `'loudness'`) has zero importers (already covered by Existing #5371).
- **Suggested Fix**: Add `loudness` to the #5524 cleanup and narrow `TrackInfo` to the `TrackPayload` fields (or give REST and WS distinct types).

### TS-08: `WebSocketManager.on()` accepts any handler type for any event name, then force-casts
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/utils/errorHandling.ts:157-175`
- **Status**: NEW
- **Description**: The signature is `on(event: 'open'|'close'|'message'|'error', handler: (() => void) | ((event: MessageEvent | Event) => void))` and each switch arm does `handler as () => void`, `handler as (event: MessageEvent) => void`, etc. A `message` handler of type `() => void`, or an `open` handler expecting an event, compiles. The switch has no `default`/`never` check either.
- **Evidence**: `this.onMessage = handler as (event: MessageEvent) => void;`
- **Impact**: Compile-time only; all current callers (`useWebSocketConnection.ts`) pass the right shape. It is the sole transport-layer entry point for inbound frames, so it is worth being exact.
- **Siblings**: none.
- **Suggested Fix**: Use a mapped handler type: `on<E extends keyof Handlers>(event: E, handler: Handlers[E])` with `Handlers = { open: () => void; close: () => void; message: (e: MessageEvent) => void; error: (e: Event) => void }`.

### TS-09: Residual production `any` (16 occurrences, 7 files), most already filed
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/design-system/primitives/Text.tsx:102` (`ref={ref as any}`); `auralis-web/frontend/src/utils/apiRequest.ts:57,240,252,264` (`body?: Record<string, any>`); `auralis-web/frontend/src/utils/serviceFactory.ts:239-243`; `auralis-web/frontend/src/store/middleware/loggerMiddleware.ts:93,102-103,160`; `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:136,139`; `auralis-web/frontend/src/components/settings/SettingsDialogContent.tsx:13` (TS-05)
- **Status**: Existing: #5374 (serviceFactory), Existing: #5377 (loggerMiddleware, useMetadataForm); `Text.tsx` and `apiRequest.ts` are not in either
- **Description**: Group census, none individually impactful. `Text.tsx` casts the forwarded ref for a polymorphic `Component`; `apiRequest` request bodies are `Record<string, any>` while `useRestAPI`'s are already `Record<string, unknown>` (inconsistent siblings, and `Record<string, unknown>` is accepted by `JSON.stringify` identically). No `any` exists on the WS, store-reducer or response-parsing paths (those use `unknown`).
- **Evidence**: `<Component ref={ref as any} style={styles} className={className}>`
- **Impact**: Loss of checking on request-body construction and one ref.
- **Siblings**: see Location.
- **Suggested Fix**: `Record<string, unknown>` in `apiRequest.ts`; type the polymorphic ref with `React.ComponentPropsWithRef<T>['ref']`.

### TS-10: `tsc` over all sources reports 133 errors in 22 test files (up from 101 documented in `tsconfig.json`); production is clean
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/tsconfig.json:30-47` (documented figure "101"); `.github/workflows/frontend-typecheck.yml:8-11` (CI runs `type-check:prod` only); worst files `src/hooks/app/__tests__/useKeyboardShortcuts.test.ts` (29), `src/hooks/shared/__tests__/useDialogAccessibility.test.tsx` (17), `src/components/__tests__/redux-flow.test.tsx` (17), `src/components/__tests__/Integration.test.tsx` (16)
- **Status**: NEW (the workflow says test-file errors are "tracked separately"; no open issue found in the dedup baseline)
- **Description**: `pnpm run type-check:prod`: 0 errors. `pnpm run type-check`: 133 errors (88 TS2345, 29 TS2322, 7 TS2741, 2 TS7006, 2 TS6133, 2 TS2614, 1 TS6305, 1 TS2739, 1 TS2556). Several are tests built against stale production shapes, i.e. the tests no longer prove what they claim: `playerSlice.test.ts:41,51` omit required `StreamingInfo.stalled`; `store/__tests__/testFixtures.ts:143` omits `QueueState.isShuffled/repeatMode`; `store/slices/__tests__/*` import a `Track` export that `playerSlice` no longer has (TS2614); `transformPlayerState.test.ts:51` uses state `'idle'`, not in the `'playing'|'paused'|'stopped'|'loading'|'error'` union; `useReduxState.test.tsx` builds `PlayerTrack`/`QueueTrack` without `album`; `viteChunking.test.ts:19` hits TS6305 (`vite.manualChunks.d.ts` not built).
- **Evidence**: `src/types/__tests__/transformPlayerState.test.ts(51,7): error TS2322: Type '"idle"' is not assignable to type '"paused" | "error" | "playing" | "loading" | "stopped"'.`
- **Impact**: No production effect. The count grows silently (not gated); stale-shape tests hide real type drift (the same drift TS-01..TS-03 are about).
- **Siblings**: n/a.
- **Suggested Fix**: Fix the 22 files (mostly mock typing: `vi.fn()` -> typed `vi.fn<...>()`; add missing required fields), then add a `type-check` step (or a ratchet like the vitest baseline) to `frontend-typecheck.yml` and update the figure in `tsconfig.json`.

### DS-02: `src/index.css` (451 lines) is never loaded; the token-parity work and tests built on it guard nothing at runtime
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/index.css:1-451`; `auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css:23-138`; `auralis-web/frontend/src/theme/__tests__/cssCustomPropertyProducers.test.ts:25-60`; `auralis-web/frontend/src/design-system/__tests__/cssVariablesTokenParity.test.ts:14`
- **Status**: NEW (about 10 closed issues edited this file: #3927, #4171, #4172, #3636, #3057, #3159, #3127/#3087, #2967, #3985; none noticed it is not loaded)
- **Description**: `import './index.css'` was removed from `index.tsx` in commit `be0f3619` (2025-11-22, "Defer component imports"). Nothing else references it: not `index.html`, the Vite config, or any module. The built `dist/assets/` contains zero `.css` files. The only importers are two vitest files that read it with `?raw`. Its `:root` variables (`--space-*`, `--radius-*`, `--transition-*`, `--aurora-*`, `--midnight-blue`) therefore have no runtime producer. The sole consumer of those variables is `ShuffleModeSelector.module.css`, and `ShuffleModeSelector` itself has no production importer. The #4535 guard test counts `index.css` as a "producer", so it would pass for a module that consumed `--space-md` even though that variable resolves to nothing.
- **Evidence**:
  ```
  $ git show be0f3619 -- src/index.tsx | grep css   ->  -import './index.css';
  $ rg "index\.css" src index.html vite.config.mts  ->  only the two test files + comments
  $ ls dist/assets | grep -ci css                    ->  0
  $ rg "ShuffleModeSelector" src (non-test)          ->  its own .tsx and .module.css only
  ```
  `ShuffleModeSelector.module.css` header: "`--space-*, --radius-*, --transition-* -> the :root block in src/index.css`".
- **Impact**: No user-visible effect today, because the one consumer is unmounted. It is maintenance and false-assurance debt: the parity and producer tests pass against a file that is not shipped. If `ShuffleModeSelector`, or any new CSS module, relies on those variables, its gaps, padding, radii and transition silently collapse. The file also carries an off-palette `rgba(6,182,212,0.1)` at line 263.
- **Siblings**: `ShuffleModeSelector.tsx` and its `.module.css` (dead component).
- **Suggested Fix**: Either delete `index.css`, its two tests and the dead `ShuffleModeSelector` (preferred), or move the needed variables into `globalStyles.ts` generated from `tokens`. If the stylesheet stays, import it for real.

### DS-03: Four sites append `px` to a token that already ends in `px`, producing invalid CSS (`12pxpx`)
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/shared/MediaCard/MediaCardArtwork.tsx:101`; `auralis-web/frontend/src/components/shared/MediaCard/MediaCardOverlay.tsx:108`; `auralis-web/frontend/src/components/shared/ui/loaders/LoadingSpinner.tsx:82-83`
- **Status**: NEW (same defect class as closed #2357, "PlaylistList.tsx doubles px suffix"; that fix is intact, no `}px` remains there)
- **Description**: `tokens.spacing.*` and `tokens.borderRadius.*` are strings such as `'12px'`. Wrapping them as `` `${tokens.spacing.md}px` `` yields `12pxpx`, which the browser drops as an invalid declaration.
- **Evidence**:
  ```ts
  // MediaCardArtwork.tsx:101
  borderRadius: `${tokens.borderRadius.lg}px ${tokens.borderRadius.lg}px 0 0`,
  // MediaCardOverlay.tsx:108
  padding: `${tokens.spacing.xs}px ${tokens.spacing.sm}px`,
  // LoadingSpinner.tsx:82-83
  gap: `${tokens.spacing.md}px`,  padding: `${tokens.spacing.xxxl}px`,
  ```
- **Impact**: The `MediaCardArtwork` top-corner radius on album cards is dropped (partly masked if the parent clips). The badge padding and the `CenteredLoading` gap and padding are dead declarations, but `CenteredLoading` has no consumer outside the `ui` barrel, and no caller passes `badgeContent`. The cosmetic effect is small, but the pattern is a trap for the next author.
- **Siblings**: None beyond the four sites above (grep of `tokens.<scale>…}px` across `src/`).
- **Suggested Fix**: Drop the `px` suffix at each site. A `no-restricted-syntax` lint rule on `}px` after a `tokens.` expression would prevent a repeat.

### DS-04: `themeConfig.ts` still exports a parallel palette and a mode-aware glass helper that nothing uses and that disagree with the semantic layer
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:27-61` (`darkColors`), `:68-81` (`lightColors`), `:83-135` (`glassEffects`), `:142-143` and `:188-204` (palette consumption); `auralis-web/frontend/src/design-system/tokens/surfaces.ts:92-110` (`backgroundDark`/`backgroundLight`)
- **Status**: NEW (follow-up to closed #4584, which removed the `colors` alias but explicitly left these exports)
- **Description**: The only production import from `themeConfig` is `createAuralisTheme` (`ThemeContext.tsx:4`). Inside `createAuralisTheme`, only `darkColors.accent.*` and `lightColors.accent.*` are read, for the MUI palette's success, error, warning and info. The rest is dead: `darkColors`/`lightColors` `.text`, `.background`, `.neon` and `.glass`; the `gradients` export; and the whole `glassEffects` helper. `glassEffects` is the mode-aware glass implementation, yet no component calls it (only tests do). Components use the mode-fixed `tokens.glass.*` instead (see DS-01). The dead data also contradicts the live contract in two places. `darkColors.text.secondary` is lavender `accent.tertiary`, while `semanticTheme` dark `textSecondary` is white at 68%. MUI `palette.info.main` in dark mode is cyan (`darkColors.accent.info = accent.secondary` `#47D6FF`), while `themeVars.info` and the light palette are blue `#3B82F6`.
- **Evidence**:
  ```ts
  // themeConfig.ts:50-ish
  accent: { ..., info: tokens.colors.accent.secondary },   // dark -> #47D6FF
  // semanticTheme.ts: info: tokens.colors.semantic.info   // #3B82F6 in both modes
  ```
  `rg "glassEffects|lightColors|darkColors" src` outside tests matches only `themeConfig.ts`, a comment in `ThemeContext.tsx` and a comment in `surfaces.ts`.
- **Impact**: No runtime defect today (no component reads MUI `palette.info`). It is a second palette, plus an unused per-mode glass implementation that makes DS-01 look already solved. The `backgroundDark`/`backgroundLight` glass tokens exist only to feed that helper.
- **Siblings**: `tokens.colors.export` (`colors.ts`, about 40 lines) has no production consumer either (not verified against the backend export path).
- **Suggested Fix**: Build the MUI `success`/`error`/`warning`/`info` from `getSemanticTheme(mode)` and delete `darkColors`, `lightColors`, `gradients` and `glassEffects`. If a per-mode glass fill is needed, add it to `SemanticTheme` (DS-01). Update `themeConfig.tokens.test.ts` accordingly.

### DS-05: Residual literal spacing, radius, line-height and animation-duration values bypass the tokens
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: spacing/radius: about 35 `px`-literal sites in 19 files, for example `components/track/TrackCardStyles.ts:16,70-82` (`borderRadius: 12`, `paddingLeft: 8`, `padding: 16`, `borderRadius: 6`), `components/shared/CacheStatsDashboard.tsx:59,86,181`, `components/shared/CacheStatsDashboard/StatCards.tsx:81`, `components/shared/ConnectionDetailsPanel.tsx:44,214,243`, `components/settings/AdvancedSettingsPanel.tsx:140,174`, `components/library/Items/tracks/SelectableTrackRow.styles.ts:15`, `components/shared/ui/loaders/*Skeleton.tsx` (about 15 radius literals), `components/core/ErrorBoundary.tsx:66-79`, `components/shared/KeyboardShortcutsHelp.styles.ts:28,55`, `components/shared/ContextMenu/PlaylistSection.tsx:29,43` (`48px`); line-height: `components/library/Items/tracks/TrackRow.styles.ts:190,202`, `components/track/TrackCardInfo.tsx:38,55,72`, `components/platform/DesktopPlatformNotice.tsx:42`, `components/library/AlbumCharacterPane/RotatingDescription.tsx:53`, `components/library/Details/DetailViewHeader.tsx:92`; keyframe durations: about 20 `animation: '... Ns ...'` strings (`TrackDisplay.tsx:95,106`, `BatchActionsToolbarStyles.ts:30`, `DropZoneIcon.tsx:34,43`, `TrackListView.styles.ts:13`, `SettingsTabNav.tsx:42`, ...)
- **Status**: NEW (the specific sites listed in closed #5379 and #5384 are verified fixed; this is residual drift at other sites)
- **Description**: About 13 of the px radius literals are exact `tokens.borderRadius.sm/md/lg` values (`'8px'`, `'12px'`, `'16px'`). Most of the rest are 2/3/4/6px radii and paddings with no token (the radius scale starts at 8px, even though its comment says "minimum 8px"). `lineHeight` values 1.1/1.4/1.6 do not match `tokens.typography.lineHeight` (1.2/1.5/1.75). Keyframe durations and easings are inline strings, although `tokens.animations` and `tokens.transitions` exist. Typography is otherwise clean: a grep of `fontSize` finds only icon-size numerics, with no literal `fontSize`, `fontWeight` or `fontFamily` on text. `zIndex` literals are clean (0). Breakpoint usage is clean: all `@media` strings go through `tokens.breakpoints`, and the MUI `down('md')` hooks agree with them.
- **Impact**: Cosmetic. These values will not follow a future token change, and the 4/6px values hint that the radius or spacing scale lacks a small step.
- **Siblings**: n/a
- **Suggested Fix**: Replace the exact-match radii with tokens. Decide whether a small radius (4px) and the 1.4 line-height deserve tokens, or normalize to the existing steps.

### API-07: Error-message normalization is inconsistent: `${err}` in toasts, generic literals that discard the backend `detail`, and three error shapes
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/playlist/useCreatePlaylistForm.ts:46`, `useEditPlaylistForm.ts:52`, `usePlaylistOperations.ts:38`; `components/shared/ContextMenu/usePlaylistActions.ts:34, 52`; `components/library/Items/tracks/useTrackContextMenu.ts:67, 79`; `components/settings/useSettingsDialog.ts` (every catch); `components/library/Views/useQueueOperations.ts`
- **Status**: NEW
- **Description**: The transport carefully extracts the backend's `detail` (`utils/httpError.ts`, including the #5351 422 shape), but call sites then present it inconsistently. Seven toasts interpolate the raw error, so they read "Failed to delete playlist: APIRequestError: Playlist not found". `useSettingsDialog` and `useQueueOperations` replace the error with fixed strings ("Failed to add scan folder", "Failed to save settings"), dropping the useful reason (for example the 400 "One or more scan folders failed validation" or a 422 field list). `useRestAPI` additionally throws a plain `ApiError` object (not an `Error`), `apiRequest` throws `APIRequestError` (`statusCode`), and `httpErrorFromResponse` throws `HttpStatusError` (`status`); `ApiErrorHandler.parse` papers over the difference, but any code path that does `err instanceof Error ? err.message : ...` loses the message for the first kind.
- **Evidence**: `error(\`Failed to delete playlist: ${err}\`);` / `setError('Failed to add scan folder');`
- **Impact**: Cosmetic and diagnosability: users see class names, or a generic message when the backend said exactly what was wrong.
- **Siblings**: the sites above.
- **Suggested Fix**: One helper (for example `errorMessage(err, fallback)` built on `ApiErrorHandler.parse`) used by every toast/`setError`; have `useRestAPI` throw an `Error` subclass carrying `status`.

### API-08: The abort contract in `apiRequest` is documented wrongly and detected three different ways
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts:98-104, 207-215`; `auralis-web/frontend/src/services/playlistService.ts:141-146`; `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:292, 368`; `auralis-web/frontend/src/hooks/api/useRestAPI.ts:174`; `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:110`
- **Status**: NEW
- **Description**: `fetchWithTimeout`'s docblock says "a caller-triggered abort propagates as the underlying AbortError", and `getPlaylists` says "`apiRequest` re-throws [AbortError] without surfacing it". It does not: `apiRequest`'s catch wraps anything that is not an `APIRequestError` into `APIRequestError('Network error: ...', 0)`. Six callers already work around this with `controller.signal.aborted || isAbortError(err)` (and say so in comments), but a future caller that trusts the documented contract will show "Network error: signal is aborted" on every unmount or supersession. Detection is also split: `isAbortError` (errorGuards, intended single helper, #4462) versus ad-hoc `err instanceof Error && err.name === 'AbortError'` (`useLibraryQuery` x2, `useRestAPI`) and `err instanceof DOMException` (`useEnhancedPlayCommand`).
- **Impact**: Latent; a trap for new call sites.
- **Siblings**: see Location.
- **Suggested Fix**: Make `apiRequest` rethrow caller-initiated aborts unchanged (it already knows `didTimeout`), which makes the docs true and lets callers drop the double check; switch the ad-hoc checks to `isAbortError`.

### API-09: Base-URL and endpoint configuration is only partly centralized
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/config/api.ts:18-21, 35-38, 42-86`; `auralis-web/frontend/src/contexts/WebSocketContext.tsx:181-195`
- **Status**: NEW
- **Description**: REST base URL comes from `API_BASE_URL` everywhere (no hardcoded `localhost`/`:8765` outside `config/api.ts`, good). However: (1) the WebSocket default URL is chosen by a hostname/port heuristic (`hostname === 'localhost' && port >= 3000` -> `WS_BASE_URL`, else same-origin), so setting only `VITE_API_URL` (the #4468 escape hatch for a taken port 8765) moves REST but leaves WS on `ws://localhost:8765` unless `VITE_WS_URL` is also set; `getWsUrl()` is exported but has no caller. (2) `ENDPOINTS` says "Use these constants instead of hardcoding endpoint strings", but about 90 literal `'/api/...'` strings remain against 31 `ENDPOINTS.*` uses, and several catalog entries (the `PLAYER_*` group at least) have no consumer. `getBlob` and `patch` in `apiRequest.ts` are unused.
- **Impact**: Mostly maintainability; the port-override case only matters for someone running the backend on a non-default port.
- **Siblings**: n/a
- **Suggested Fix**: Derive `WS_BASE_URL` from `API_BASE_URL` when `VITE_WS_URL` is unset; either adopt `ENDPOINTS` consistently or trim it to what is used.

### API-10: Initial-state fetches swallow failures, and the shared enhancement-status promise is tied to the first consumer's abort
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:111-127, 196-216`; `auralis-web/frontend/src/hooks/player/useQueueFetch.ts:74-80`; `auralis-web/frontend/src/components/library/Hooks/useSearchLogic.ts:138-141`
- **Status**: NEW (sibling of HK-06 for `useQueueFetch`)
- **Description**: `useEnhancementControl` seeds `enabled/preset/intensity` from `GET /api/player/enhancement/status` and, on any failure, only `console.warn`s and keeps `INITIAL_STATE` (`enabled: false`) with no error and no retry (`useQueueFetch` does the same for the queue; the global search `catch` only `console.error`s, so a failed search shows stale or empty results). Additionally `_fetchEnhancementStatusOnce` shares one promise across all consumers but builds it with the FIRST consumer's `useRestAPI().get`: if that consumer unmounts while the request is in flight, `useRestAPI`'s unmount cleanup aborts it and every other consumer waiting on the same promise gets an `AbortError`, which they also swallow.
- **Evidence**: `// Silently fail - user can still interact with defaults` / `console.warn('Failed to fetch initial enhancement state:', err);`
- **Impact**: Rare on localhost, but when it happens the enhancement controls show "disabled" while the backend has it enabled (the next toggle then sends `enabled: true`, a no-op) until a WS `enhancement_settings_changed` arrives.
- **Siblings**: see Location.
- **Suggested Fix**: Build the shared promise from `apiRequest.get` (no per-hook controller) and expose/retry on error; at least show a non-blocking error state instead of defaults.

### PERF-06: Audio visualization values travel through React state at ~30 Hz although the only consumer reads them from a ref
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/audio/useAudioVisualization.ts:233-258,286-296`; `auralis-web/frontend/src/components/background/AudioReactiveStarfield.tsx:44-56`; `auralis-web/frontend/src/components/background/StarfieldBackground.tsx:156-158`
- **Status**: NEW (related: #5367 covers dead exports in the same file)
- **Description**: `useAudioVisualization` runs its own rAF loop at display refresh (`getByteFrequencyData` plus three band loops) while audio is active, and calls `setData` up to 30x/s. That re-renders `AudioReactiveStarfield` and `StarfieldBackground`, which is not `memo`. `StarfieldBackground` just copies the prop into `audioRef.current` during render and reads it from its own rAF loop. The React round trip is pure overhead. The decay branch also calls `setData` on every frame until `loudness < 0.01`.
- **Evidence**:
  ```ts
  // StarfieldBackground.tsx:156-158
  if (audioReactivity) { audioRef.current = audioReactivity; }   // consumed in rAF, not in render
  ```
- **Impact**: About 30 small re-renders per second during playback, plus a second rAF loop. Small per frame, but it is a render source that exists for no reason.
- **Siblings**: None.
- **Suggested Fix**: Have the hook write into a shared mutable ref (or a tiny external store read by the starfield's own rAF) and drop the state. If PERF-04 caps the starfield frame rate, sample the analyser from that same loop.

### PERF-07: Worklet transport copies each block twice and allocates on the audio thread; underrun is posted every render quantum
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/services/audio/BufferScheduler.ts:218-221`; `auralis-web/frontend/public/audio-worklet-processor.js:32-35,63-67`
- **Status**: NEW
- **Description**: The feed loop allocates a new `Float32Array` per tick in `PCMStreamBuffer.read()` and posts it without a transfer list, so the structured clone copies it. The worklet then does `new Float32Array(data.samples)`, a second copy plus an allocation on the real-time audio thread (GC pauses there can glitch output). When the queue runs short, `process()` posts `{type:'underrun'}` on every render quantum (128 frames, about 345 messages/s) with no rate limit. The main-thread handler is cheap (`bufferUnderrunCount++`, callbacks deduped), but it is steady message traffic for as long as the stall lasts.
- **Evidence**:
  ```js
  // audio-worklet-processor.js:63-67
  if (this._available < samplesNeeded) {
    for (...) output[ch].fill(0);
    this.port.postMessage({ type: 'underrun' });   // every quantum while starved
  ```
- **Impact**: About 160 KB/s of avoidable copy traffic and 20 allocs/s on the audio thread during playback; message spam during stalls.
- **Siblings**: None.
- **Suggested Fix**: `postMessage({samples}, [samples.buffer])`, and use `data.samples` directly in the worklet. Send `underrun` only on the not-underrun to underrun transition.

### A11Y-07: Toasts are all `role="alert"` (assertive), including the info echoes of every keyboard shortcut
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/design-system/primitives/Alert.tsx:78`; `auralis-web/frontend/src/components/shared/Toast/ToastItem.tsx:35-41`; `auralis-web/frontend/src/ComfortableApp.tsx:96,108,116,129,138,147`
- **Status**: NEW
- **Description**: `StyledAlert` wraps the design-system `Alert`, which hard-codes `role="alert"` for every variant. `ToastItem` renders info, success, warning and error identically. `ComfortableApp` shows an `info(...)` toast on each shortcut ("Playing", "Paused", "Next track", "Volume: 60%", "Muted", "Songs view"). Each one interrupts speech immediately, and "Playing/Paused" is announced twice, once assertively by the toast and once politely by the `PlaybackControls` status region (#4474). `AppViewAnnouncement` likewise duplicates the "Songs view" toast. A volume-key repeat queues up to three assertive announcements. Toasts also auto-dismiss at 4 s, and no focus path exists to the close button before they go.
- **Evidence**: `<div ref={ref} role="alert" ...>` in `Alert.tsx:78`, used for every toast type.
- **Impact**: Screen-reader users get assertive chatter for routine feedback, which can cut off the polite now-playing announcement, while real errors are no more prominent than echoes.
- **Siblings**: `Player.tsx:199` correctly uses `role="alert"` for the playback error banner.
- **Suggested Fix**: Make the role depend on the variant (`alert` for error/warning, `status` for info/success), and drop the info echoes for actions that already have a live region.

### A11Y-08: Heading levels skip, and `SimilarTracksModal` nests headings and paragraphs inside the dialog title
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Views/AlbumsTab.tsx:76`; `components/library/Items/albums/EraSection.tsx:131`; `components/library/Items/albums/RecentlyTouchedSection.tsx:106`; `components/library/AlbumCharacterPane/AlbumCharacterPane.tsx:217`; `components/player/QueuePanel/QueuePanelExpanded.tsx:176`; `components/shared/SimilarTracksModal/SimilarTracksModalHeader.tsx:21-45`
- **Status**: NEW (the single-`<h1>` invariant itself holds; see Checked, clean)
- **Description**: MUI `Typography variant="h6"` renders an `<h6>` element unless `component` is given. Under the view's `<h1>` (`ViewContainer`), the album view's section titles, era headers, "Recently touched" and the album character pane are `<h6>`, so the outline jumps h1 to h6. The Queue panel title is a raw `<h3>` with no `<h2>` above it. `SimilarTracksModalHeader` puts `Typography variant="h6"` and `variant="body2"` (rendered `<h6>` and `<p>`) inside MUI's `DialogTitle` (an `<h2>`), producing a heading nested in a heading and a block `<p>` inside a heading, and the dialog's accessible name becomes the title plus the whole subtitle. The other dialog headers (Settings, Edit Metadata, Shortcuts) correctly pass `component="span"`/`"div"`.
- **Evidence**: `<Typography variant="h6" sx={{...}}>Albums</Typography>` (AlbumsTab); `<Typography variant="h6">Similar Tracks</Typography>` inside `<DialogTitle>`.
- **Impact**: Heading navigation shows an irregular outline (h1, h6, h3) and the Similar Tracks dialog is announced with the track subtitle as part of its name.
- **Siblings**: `ErrorBoundary.tsx:67` (h1) is only shown when a boundary uses its default fallback, so it does not add a second `<h1>` in practice.
- **Suggested Fix**: Set `component="h2"`/`"h3"` on the section titles to match the real hierarchy, make the Queue title an `<h2>`, and give the Similar Tracks header `component="span"`/`"div"` like its siblings.

### A11Y-09: Virtualized lists expose no total size or position, so assistive tech reports the rendered window as the whole list
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:171-230`; `auralis-web/frontend/src/components/player/QueuePanel/QueuePanelExpanded.tsx:206-250`; `auralis-web/frontend/src/components/library/Items/artists/ArtistListContent.tsx`
- **Status**: NEW
- **Description**: The track listbox, the queue list and the artist list use `useVirtualizer`, so only the visible window (roughly 20-40 rows) is in the DOM. None of the rows sets `aria-setsize`/`aria-posinset` (`rg` finds neither string anywhere in `src/`), and the containers set no `aria-rowcount`/total. A screen reader announces "1 of 32" for a library of thousands, and the queue "list with 25 items" for a queue of 800.
- **Evidence**: `rg "aria-setsize|aria-posinset|aria-rowcount" src` returns nothing.
- **Impact**: Users cannot judge list size or position, and cannot tell whether more content exists below the rendered window.
- **Siblings**: The three lists above; `TrackRow` also lacks `index`-based `aria-posinset` even though it knows `index`.
- **Suggested Fix**: Pass `aria-setsize={total}` and `aria-posinset={index + 1}` on each option/listitem (the virtualizer and `tracks.length` already know both).

### A11Y-10: Light mode: aurora-filled primary buttons, semantic status text and accent text fall below WCAG AA
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `components/player/PlaybackControlsStyles.ts:37-43` (play/pause); `components/library/Details/AlbumActionButtons.tsx:50-51`; `components/library/Details/ArtistHeader.tsx:99-100`; `components/library/Details/AlbumDetailView.tsx:130-131`; status text in `components/settings/ScanStatusCard.tsx:125-141`, `components/settings/FingerprintCoverageCard.tsx:63`, `components/settings/AdvancedSettingsPanel.tsx:146-150`; `components/library/Items/tracks/TrackRow.styles.ts:117`, `components/library/Items/tables/TrackTableRowItem.tsx:84`
- **Status**: NEW (same family as closed #4534, whose fix is visible in `Button.styles.ts:19-22`, "onAccent, not textPrimary", but was not applied at these sites; separate mechanism from DS-01)
- **Description**: Contrast computed from the token values (WCAG relative luminance):
  - The play/pause button, "Play Album", "Play All" and the detail-view back button paint `tokens.gradients.aurora` (`#7366F0` to `#5A5CC4`, a fixed fill in both modes) with `color: themeVars.textPrimary`. In light mode that is ink `#1A1F3A` on violet: 3.76:1 at the light end and 2.89:1 at the dark end (needs 4.5:1 for the 14 px labels; 3:1 for the 24 px glyph, which fails at the dark end).
  - `lightMode.accent.success/warning/error` are the dark-mode hexes. Used as text on the white/near-white light surfaces: success `#10B981` 2.41:1 (2.54 on white), warning `#F59E0B` 2.04:1, error `#EF4444` 3.58:1. Hit by "Scan complete" / error lines, fingerprint error text and the Danger Zone heading.
  - Brand `#7366F0` as text on `#F8F9FD` is 4.08:1 (current-track title and number). Dark mode is fine for muted/secondary text (>= 6.5:1) and accent text is 4.41:1 on the base canvas, 3.64:1 on raised cards.
  - White on `#7366F0` (aurora buttons in dark mode, `onAccent`) is 4.30:1, just under 4.5:1 at the light end.
- **Evidence**: `color: themeVars.textPrimary` next to `background: tokens.gradients.aurora` at the four button sites.
- **Impact**: With the shipped theme toggle on light, the main Play control and several status messages are hard to read.
- **Siblings**: Other `themeVars.textPrimary`-on-aurora uses were checked and are fine (`GradientButton` uses `onAccent`).
- **Suggested Fix**: Use `themeVars.onAccent` on every aurora fill. Add darker light-mode `success`/`warning`/`error` text tokens (or use them only as icon/border colours). Deepen the light end of the aurora gradient or the accent text token by about 5% luminance.

### A11Y-11: Motion that ignores `prefers-reduced-motion`, and a "Show visualizations" setting that does nothing
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/background/StarfieldBackground.tsx:117-190`; `auralis-web/frontend/src/components/background/AudioReactiveStarfield.tsx`; `auralis-web/frontend/src/App.tsx:47-49`; `auralis-web/frontend/src/components/library/AlbumCharacterPane/RotatingDescription.tsx:24-40`; `auralis-web/frontend/src/components/library/AlbumCharacterPane/usePlaybackWithDecay.ts:60-77`; `auralis-web/frontend/src/styles/globalStyles.ts:336-344`
- **Status**: NEW
- **Description**: `globalStyles.ts` has a global `prefers-reduced-motion: reduce` rule, which neutralises CSS animations and transitions. It cannot reach the WebGL starfield, which runs an unconditional `requestAnimationFrame` loop (time-driven drift, audio-reactive and mouse-parallax movement) rendered from `App.tsx` on every screen, nor the JS-driven decay animation in the album pane. `RotatingDescription` also swaps the text every 10 s with no pause control (WCAG 2.2.2, auto-updating content lasting over 5 s). The Settings Interface tab offers "Show visualizations" (`show_visualizations`), but nothing outside the settings panel reads it, so the user's only opt-out of the animated background is inert.
- **Evidence**: `rg "matchMedia|useReducedMotion" src/components` returns nothing; `rg "show_visualizations|showVisualizations" src` hits only `settingsService.ts` and the settings panels.
- **Impact**: Users who request reduced motion (vestibular disorders) still get a continuously animating, mouse-following full-window background at 14% opacity. The background is low contrast and decorative, so this is not severe.
- **Siblings**: None.
- **Suggested Fix**: Read `matchMedia('(prefers-reduced-motion: reduce)')` and the `show_visualizations` setting in `App.tsx`; render a static frame or nothing. Pause `RotatingDescription` rotation under reduced motion.

### TST-08: `setup.ts` console.error filter is dead under `restoreMocks: true` / `mockReset: true`
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `src/test/setup.ts:151-165` (spy), `vitest.config.ts:46-47,172` (`restoreMocks: true`, `mockReset: true`)
- **Status**: NEW (confidence medium — derived from vitest 4.1.7 source `clearModuleMocks`: `if (restoreMocks) vi.restoreAllMocks(); if (mockReset) vi.resetAllMocks()`; not executed)
- **Description**: The filter that swallows the React Router and "Should not already be working" warnings is installed once, at setup-file load, via `vi.spyOn(console, 'error').mockImplementation(...)`. With `restoreMocks: true` that spy is restored before each test (including the first), so the suppression never applies and its comment ("Log all other errors normally") describes a filter that is not in effect. Effect today is only log noise, but the same trap applies to any other module-scope `vi.spyOn` in setup.
- **Evidence**:
  ```ts
  const originalError = console.error
  vi.spyOn(console, 'error').mockImplementation((...args) => { ... originalError(...args) })
  ```
- **Impact**: Noisy output and a misleading comment; could mask the real act() warnings the comment promises to keep visible.
- **Siblings**: n/a
- **Suggested Fix**: Move the spy into a `beforeEach` (or drop it, since the router is gone per #4943).

### TST-09: Test harness drifts from production: test store has no middleware and no serializable check; MSW defaults mirror old endpoints; unhandled requests only warn
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `src/test/test-utils.tsx:80-92` vs `src/store/index.ts:27-45`; `src/test/mocks/handlers.ts:382` vs `src/hooks/app/useAppDragDrop.ts:208`; `src/test/setup.ts:171-181`
- **Status**: NEW
- **Description**: `createTestStore` hand-copies the reducer map and sets `serializableCheck: false`; the production store (a singleton, no factory) uses default RTK checks plus error-tracking/logger middleware. A non-serializable or mutating dispatch (TS-02/RDX-03 raw payloads) warns in dev but never in tests, and a new slice added to `store/index.ts` is silently missing from every test store. `handlers.ts` still serves `PUT /api/playlists/:id/reorder` while the app calls `/api/playlists/:id/tracks/reorder`; the setup's `onUnhandledRequest` callback only `console.warn`s, so an unmatched REST call in a spec quietly becomes a network failure that most hooks swallow.
- **Evidence**:
  ```ts
  middleware: (getDefaultMiddleware) => getDefaultMiddleware({ serializableCheck: false })
  ```
- **Impact**: Tests can pass against a store configuration the app does not run.
- **Siblings**: n/a
- **Suggested Fix**: Export `createAppStore(preloaded)` from `store/index.ts` and use it in `test-utils`; make `onUnhandledRequest` throw for `/api/` HTTP requests; update the stale handler paths.

### TST-10: The weak-assertion gate only scans Python tests; the frontend has no equivalent
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `scripts/check_weak_assertions.py:25-80` (scans `tests/`, `assert x is not None` only); frontend `src/**/*.test.*`
- **Status**: NEW
- **Description**: The repo script is a Python `ast` ratchet over `tests/`. A heuristic scan of the frontend specs finds 126 `toBeDefined()` and 29 `toBeTruthy()` calls, 42 tests whose every assertion is `toBeDefined/toBeTruthy/not.toBeNull` (worst: `useAppDragDrop` 9, `useRestAPI` 7, `testFixtures.test.ts` 4, `AlbumCharacterPaneComponents` 3), 7 tests with no assertion, 12 `expect(result.current).toBeDefined()` smoke checks, and 0 uses of `expect.assertions`. Source-regex "tests" (e.g. `ErrorBoundary.test.tsx:131` regexes `ComfortableApp.tsx` for `<ErrorBoundary>…<Player />`) assert implementation text. There is no snapshot use (good) and no skipped tests.
- **Evidence**: n/a (counts from a scan script; see TST-03/04/05 for concrete cases).
- **Impact**: The pattern regrows unchecked (the backend history in the script docstring shows #4049/#4257 regrowing for the same reason).
- **Siblings**: n/a
- **Suggested Fix**: Add an ESLint rule (`vitest/expect-expect`, `vitest/no-conditional-expect`, `vitest/valid-expect`) or a small vitest-AST ratchet; baseline the current offenders.

### TST-11: Hooks with real logic and no direct spec
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `src/components/settings/useSettingsDialog.ts` (187 lines), `src/components/playlist/usePlaylistWebSocket.ts`, `usePlaylistData.ts`, `usePlaylistOperations.ts`, `src/components/CozyLibraryView/useLibraryKeyboardShortcuts.ts`, `src/hooks/enhancement/useEnhancedStreamStart.ts` (222), `useStreamStartWatchdog.ts` (67), `src/hooks/shared/use{Player,Queue,Connection,Cache,App}Redux.ts`
- **Status**: NEW
- **Description**: No spec names these modules. `useSettingsDialog` owns the pending-changes/Cancel/NaN logic behind CMP-04, CMP-16 and TS-05; `usePlaylistWebSocket` owns playlist WS subscriptions; the stream-start hooks are only reached through `useAudioStreamingCore.*` specs (which mock around parts of them). The five `*Redux` hooks are tested only through the `useReduxState` barrel (including the weak "should return all state slices" test, which only checks `toBeDefined`).
- **Evidence**: n/a
- **Impact**: Defects in these hooks (several already filed) have no direct test seam.
- **Siblings**: components/settings has 15 source files and 3 specs; components/playlist 14 and 3; components/navigation 6 and 0.
- **Suggested Fix**: Add direct hook specs when the related bugs are fixed (start with `useSettingsDialog`).

---

# Appendix: Per-Dimension Notes

#### Dim 1 (Component Quality) — Checked, clean
- XSS / unescaped metadata: no `dangerouslySetInnerHTML` anywhere in `src/`. The only `innerHTML` assignment is the bootstrap failure page in `index.tsx`, which escapes `&<>"` in the message and `<>` in the stack. No track-derived `href` or `window.open`.
- Rules of Hooks: scanned all component files for early returns before hooks. `LibraryViewRouter` (#3924) and `QueuePanel` (#5007) fixes are intact; the other hits were helper functions.
- List keys: no array-index keys on reorderable lists. Queue rows use stable occurrence-ordinal keys (`rowKeys`). Track, album, artist, playlist, toast and similar-track lists key on ids. Index keys appear only on static skeletons and fixed visual elements. `${id}-${index}` keys in the recommendation panels are in orphaned code (CMP-09).
- Unmounted-component updates: async-in-effect paths are guarded (`usePlaylistData` mounted ref, `useAlbumDetails`, `useArtistDetailsData`, `useSearchLogic`, `useMetadataForm` abort controllers, `usePlaybackWithDecay`). The remaining post-await setStates are in click handlers of components that stay mounted.
- Refs: the audio element is not touched by components. Virtualizer scroll refs, queue auto-scroll, progress-bar document listeners and `StarfieldBackground` rAF/listeners all clean up on unmount.
- `useToast` identity is memoized (`useToastMethods`), so no consumer re-render storm.
- Closed fixes verified in place: #5120 (layout-effect scroll element in 4 of 5 virtualized grids), #5397 (dialogs stay mounted for exit transitions), #5396 (`AppMainContent` props), #5389 (stable `getItemKey`), #3924, #5007.
- Components over 300 lines: only `ComfortableApp.tsx` (CMP-12).

Not reported, unverified: `TrackListViewContent.tsx:70-72` still resolves its scroll element in a passive `useEffect` and a plain ref (the other virtualized lists got the #5120 layout-effect fix). The virtualizer reads `getScrollElement()` in its layout effect before that ref is set, so its first render may produce no rows until a later re-render attaches it. I could not confirm this without running the app (no `node_modules` here), and parent re-renders probably mask it. Worth a quick runtime check.

#### Dim 2 (Redux State Management) — Checked, clean
- Selector memoization: all `useSelector` call sites in production code are field picks, or whole-slice with `shallowEqual` (`usePlayerRedux`, `useQueueRedux`, `useCacheRedux`, `useConnectionRedux`). There is no inline `.filter/.map` in a selector. Derived data uses `createSelector`, and the `make*` factories are documented as needing `useMemo`.
- Serializable state: `store/index.ts` uses `getDefaultMiddleware()` with no `serializableCheck`/`immutableCheck` suppression (only `test/test-utils.tsx` disables it). No Date/Map/Set/class/function/Error values are dispatched (`meta.timestamp` is a number, errors are strings).
- Thunks: there is no `createAsyncThunk`. The two sync-thunks (`playerQueueSync.ts`) have no async path to reject. The REST/WS errors are caught in hook code (`useQueueMutations`, `useQueueFetch`, `useAudioStreamingCore`) and dispatched or surfaced.
- Middleware: `errorTrackingMiddleware` never drops or reorders actions. It always calls `next` first, rethrows on error, defers its re-dispatch with a microtask, and guards stale forwards with `connectionGeneration` (#4430). The logger is DEV-only and stays out of production.
- Ordering guards that are present and correct: the `player_state` `seq` watermark, the `position_changed` stale-tick drop, the separate transport/volume/track_changed watermarks and the reset on reconnect. The trackId stale-guard (#4434) on streaming reducers is passed by every progress/complete/error caller except the watchdog and chunk-failure paths, which are bounded by the epoch check.
- Dispatch ordering inside the `player_state` handler is right: `setDuration` before `setCurrentTime` (#3936), and `setQueue` before `setCurrentIndex`.
- Reducer index arithmetic (`addTrack`, `removeTrack`, `reorderTrack`, `setQueue`, `setCurrentIndex`) was verified case by case for current-index shifts. No off-by-one was found.
- `PresetName` in `playerSlice.ts` is `'adaptive'`, not a bare `string` (see RDX-06 for the duplicate-literal note).
- Immer shared-reference concern (`setCurrentTrack(tracks[index])` sharing an object with `queue.tracks`): `setDuration`'s `currentTrack.duration = ...` is copy-on-write per slice, so no cross-slice mutation.
- Not re-filed because already tracked: #5354 (dead `isLoading`/`error`), #5129 (dead selector cluster), #5357 (`intensity` write-only), #5361 (`setTrack` bypasses the sync thunk), #5460 (backend queue edits not reflected in snapshots), #5521 (player bar has no artwork).

#### Dim 3 (Hook Correctness) — Checked, clean
- **Streaming session ownership**: `new AudioContext(` appears exactly once, in `hooks/enhancement/useEnhancedStreamStart.ts:127`. `usePlayEnhanced()` has a single production call site (`PlaybackSessionProvider`). `window.__auralisAudioContext` is written only by `AudioPlaybackEngine`, and `useAudioVisualization` only reads it (its dead wiring is already #5367). No second session found.
- **WebSocket subscription leaks**: every `subscribe()`/`useWebSocketMessages` call (`useAudioStreamingCore`, `useEnhancedSeek`, `useFingerprintStatus`, `useMasteringRecommendation`, `useArtworkUpdates`, `usePlayerStateSync`, `useScanProgress`, queue hooks) returns its unsubscribe from the effect cleanup. `useWebSocketMessages` uses an order-independent key and a callback ref, so it does not churn.
- **WebSocketContext value stability**: `dispatchMessage`, `subscribe`, `subscribeAll`, `send`, `setResumePositionGetter`, `reissueActiveStreamAs` are all `useCallback([])`; the context value is memoized. The StrictMode singleton/refCount handling, URL-change teardown, and `connectPromise` joining (#4522) read correctly. The `reissueActiveStreamAs` offline path (sets `lastStreamCommand` and queues) does not double-send, because `replayQueueAndResume` sees `queueHadStreamCommand`.
- **Binary frame parsing**: meta/PCM pairing, `pendingMeta` cleared synchronously for Blob/ArrayBuffer (#4331), stale-meta drop on `audio_stream_error` (#4782). `binaryType = 'arraybuffer'` is set, so the Blob branch is effectively dead (harmless).
- **Stale-stream filtering**: epoch adoption and `classifyChunk` correctly drop superseded-epoch chunks; queued pre-start chunks are drained after the new epoch is adopted.
- **eslint-disable sites** (3): `useEnhancedStreamStart.ts:218` (handleChunk deliberately listed, rest are refs/stable), `usePlayEnhanced.ts:203` (mount/unmount effect keyed on `dispatch` only), `useKeyboardShortcuts.ts:106` (trampoline via `shortcutsRef`; single call site in `ComfortableApp`). All justified; none causes a stale closure.
- **Timers/listeners**: `useStreamStartWatchdog`, `useFingerprintStatus`, `useMasteringRecommendation`, `useAutoHide`, `useAPIHealthPoll`, `useFingerprintCoverage`, `useRecentlyTouched`, `useAudioVisualization` (rAF and interval) all clear on unmount/dep change.
- **Request supersession**: `useLibraryQuery`, `useLibraryPagination`, `useLibraryStats`, `useLibraryScan`, `useSimilarTracks`, `useQueueFetch`, `useArtworkPalette`, `usePlayTrack` all use request ids/AbortControllers with correct stale guards. `useEnhancementControl` preset/intensity use request ids and the toggle uses an in-flight guard; initial status GET is deduped module-wide.
- **`useVirtualizer` getItemKey** (#5389): the only call site (`ArtistListContent.tsx`) uses a `useCallback`.
- **Custom hook return stability**: `usePlaybackQueue`, `useQueueMutations`, `usePlayerActions`, `usePlayer`, `useRestAPI`, `useCacheStats/Health`, `PlaybackControls/Progress` contexts are memoized. `useEnhancementControl` returns an unmemoized literal, but its only production consumers destructure primitives or stable callbacks.
- **`usePlayerStateSync`**: seq watermarks (player_state, transport events, volume, track_changed) are reset on reconnect (#4338) and applied per type; no stale-closure issue found.
- **Dead or non-mounted code not audited for production severity**: `QueueSearchPanel`, `QueueStatisticsPanel`, `QueueRecommendationsPanel`, `useQueueHistory`, `useOptimisticUpdate`, the Redux combinator hooks (#5354). `usePlaybackQueue`'s duplicate fetch/subscription per consumer is moot because only `QueuePanel` mounts it in production.
- **ThemeContext**: memoized value, effects keyed on `mode`; no issue.

#### Dim 4 (Type Safety) — Checked, clean
- WS message-name union vs backend: every name in `ALL_MESSAGE_TYPES` is emitted by the backend (`BroadcastMessageType` + `stream_messages.py`, `playback_commands.py` `seek_started`, `ws_handlers/playback_control.py` `playback_resumed`, `ws_handlers/messages.py` `job_progress`), and `ALL_MESSAGE_TYPES` has a compile-time `_AssertExhaustive` check. Payload fields for all messages listed in the header matched, including `seq`, `stream_epoch`, `reason`, `recovery_position`, `phase`.
- Binary vs text WS discrimination (`websocketConnectionCore.ts:handleSocketFrame`): `binaryType = 'arraybuffer'` set in `WebSocketManager`; ArrayBuffer and Blob branches both consume `pendingMeta` synchronously (#4331); text path handles `audio_chunk_meta`, `ping`, stale-meta clearing. `audio_chunk_meta` correctly kept out of the public union.
- Event handler types: all `MouseEvent`/`KeyboardEvent`/`DragEvent` handler annotations are React's (imported from `'react'`); only 4 `event.target as HTMLElement/Node` casts, all guarded by context.
- Union exhaustiveness: `never` checks exist where a closed union is switched (`libraryQueryRequest.ts`, `queue_shuffler.ts`, `registry.ts`); the remaining switches are over open string unions with `default` branches (toast severity, connection status, size/variant props). `useQueueSubscription`'s `switch (msg.type)` has no `default`, harmless (three cases, filtered by `useWebSocketMessages`).
- `tsconfig.json`: `strict` on, `noUnusedLocals/Parameters` on, `noFallthroughCasesInSwitch` on; `noUncheckedIndexedAccess` and `noImplicitReturns` deliberately off (documented, #4665); not re-reported.
- Track/Album/Artist REST types vs `Track.to_dict()`/`Album.to_dict()`/`Artist.to_dict()`: transformers map every consumed field; `album: string|null` is normalised (`?? ''`, #5359 fix intact); `artists[0]` -> `artist` intact; `created_at` for artists intact.
- Enhancement settings (REST + WS): `enabled/preset/intensity` match `EnhancementSettings`/`EnhancementSettingsChangedPayload`; removed presets (gentle/warm/bright/punchy/live) appear nowhere in production code or UI.
- `JSON.parse`: only one production use on external data (`websocketConnectionCore.ts:238`, inside try/catch) plus the guarded localStorage read in `useRecentlyTouched.ts` (shape is only checked as `Array.isArray`; benign, localStorage only).
- Generic hooks/utilities (`useOptimisticUpdate`, `useStandardizedAPI`, `createCrudService` constraints): constraints adequate apart from TS-04.
- Response-shape guards (`api/responseGuards.ts`) exist for tracks/albums/artists/queue/playlists/settings; adoption is intentionally incremental (documented design), so unguarded typed calls were not filed separately.

#### Dim 5 (Design System) — Checked, clean
- **Hardcoded colours**: Outside `design-system/`, `theme/` and the unloaded `index.css`, there are zero hex colours in non-test source (the many raw `#NNNN` grep hits are issue-number comments). The only `rgb`/`hsl` outside tokens are:
  - data-driven values in `AlbumCharacterPane/*` (fingerprint hue; legitimate);
  - `utils/colorExtraction.ts` and `utils/fingerprintToGradient.ts` (derived from artwork or fingerprint data; legitimate);
  - `ShuffleModeSelector.module.css:59,86` (dead component).
  - Canvas drawing: no `fillStyle`/`strokeStyle`/`addColorStop` outside tests. Named colours (`white`/`black`) in style props: none.
  - `AuroraWaveIcon.tsx` takes its stop colours from tokens.
- **Relative imports**: `../` is 0 in non-test source and 0 in tests. 627 sibling `./` imports exist in production code. I treated these as the usual same-directory convention rather than an `@/` violation, since prior audits (2026-09-13) did the same. If the orchestrator wants the strict reading, it is a single LOW with count 627 across the component, hook and types trees.
- **Theme plumbing**: `ThemeContext` validates the stored mode, memoizes the value, rebuilds the MUI theme per mode, writes `--app-*` variables, `data-theme` and `color-scheme`, and `getSemanticCssVariables` has identical keys for both modes (guarded by a test). 132 non-test files use `themeVars`. Direct `tokens.colors.text/bg` use in components is 0, so #4877's fix is intact. `tokens.colors.accent.primary`, `semantic.*` and `opacityScale.accent.*` are brand or semantic colours and are mode-neutral by design.
- **Token source of truth**: `design-system/tokens/*` is the single palette. `theme/semanticTheme.ts` and `themeConfig.ts` derive every value from tokens, with no second hex palette (aside from the dead duplicates in DS-04). Gradient and MUI shade hexes were moved into tokens (#3949, #3597).
- **Z-index**: no literal `zIndex` in non-test source.
- **Responsive**: no hardcoded media queries in live components (`Player.styles.ts`, `DetailViewHeader.tsx` and `TrackRow.styles.ts` use `tokens.breakpoints.md`). MUI default breakpoint values (600/900/1200/1536) coincide with `tokens.breakpoints`, though they are not derived from them. This is latent coupling only, not a defect. `useMediaQuery(theme.breakpoints.down('md'))` is used in `AppSidebar`, `AppTopBar` and `useAppLayout`.
- **Typography**: no literal `fontWeight`/`fontFamily` on text; `fontSize` literals are icon sizes only.
- **#4203** (`semantics.ts` token-composition convention) not re-filed, per the brief.

#### Dim 6 (API Client & Data Fetching) — Checked, clean
- **Endpoint existence / method / body match**: every path in `ENDPOINTS` and every literal `'/api/...'` call site (queue add-track/move/reorder/shuffle/repeat/clear/history/undo, playlists incl. `/tracks/add` and `/tracks/reorder`, settings incl. `scan-folders`/`delete`/`reset`, metadata, albums/artists/tracks, fingerprints, similarity, cache, health, scan and scan/status, enhancement toggle/preset/intensity/status) exists in the backend router tables with the same method; JSON bodies match the Pydantic models (`track_id/position`, `from_index/to_index`, `new_order`, `enabled`, `mode`, `track_ids`, scan request, metadata aliases). `/api/errors` is mentioned only in a comment and is not called.
- **Base URL**: no hardcoded host or port outside `config/api.ts` (only the WS default, see API-09).
- **Response guards**: all 9 exported guards have production callers (`isTracksListShape`: useLibraryPagination x2 and useLibraryQuery; `isAlbumsListShape`/`isArtistsListShape`: useLibraryQuery; `isQueueResponseShape`: queueService and useQueueFetch; `isArtistTracksResponseShape`: libraryService; `isPlaylistShape`/`isPlaylistsListShape`: playlistService; `isUserSettingsShape`: settingsService; `isCacheStatsShape`/`isCacheHealthShape`: useStandardizedAPI). Zero unused guards. Endpoints still consumed without a guard: `/api/albums` (useInfiniteAlbums), `/api/albums/{id}/tracks` and `/api/artists/{id}` (FE-04 in the 2026-09-13 audit), `/api/library/stats`, `/api/library/tracks/{id}`, enhancement status, fingerprint/similarity endpoints, search. Not filed: all degrade to `undefined` fields rather than corrupt state.
- **Retry**: only React Query retries, once, via `shouldRetryQuery` (transport/408/429/5xx except 501; 4xx not retried). No `useMutation`, so no POST is retried. Validation-failure errors (status 200) are not retried. The HTTP 422 `detail` / custom `errors` shapes are parsed correctly in `httpError.ts` (#5351 fix intact).
- **snake_case/camelCase**: tracks/albums/artists lists, album tracks, artist detail, and similar tracks are mapped through `api/transformers` (or an explicit mapper); the transformer field names match `schemas/library.py` (`artists`, `genres`, `filesize`, `created_at`...). Gaps are listed in API-11, API-12 and RDX-03.
- **Mutation failure handling**: queue mutations (`useQueueMutations`) roll back with generation counters and surface an error banner in `QueuePanelExpanded`; bulk operations report partial success correctly (`reportBatchResult`); `useAppDragDrop` toasts failures (note: its `track-` Draggable source and a `'queue'` Droppable do not exist anywhere in the tree, so only the playlist drop target is reachable in practice; the reorder branches are shadowed by the add branches).
- **Timeouts / unmount safety** on the `apiRequest` paths (library stats, pagination, scan, metadata form, album/artist details, similar tracks, health poll) are correct, including the signal-first abort check.
- **Cross-references (not re-filed)**: RDX-03, HK-05, HK-06, HK-07, #5009, #5516, #5519, #5466 (Scan Now discards result; distinct from API-01).

#### Dim 7 (Performance) — Out-of-dimension observations (for the orchestrator; not filed as PERF)

Static-read observations from the PERF-01 trace that belong to the Hooks/Playback or Correctness dimensions. Both are likely but not runtime-verified; worth a manual check (play, pause, resume; let a track play to its end).

- **Pause/resume in worklet mode likely resets the displayed position**. `AudioPlaybackEngine.resumePlayback()` creates a new `AudioWorkletNode` without reseeding. The new node's `samplesPlayed` message restarts at ~128 and goes through `positionTracker.setSamplesPlayed(count)` as an absolute value. `getCurrentPlaybackTime()` is `seekOffset + samplesPlayed / sampleRate` while playing, so it would snap back to the last seek offset (usually 0). `setPausedTime()` is only consulted while paused. The ScriptProcessor path accumulates deltas, so it is not affected. Files: `AudioPlaybackEngine.ts:161-189`, `BufferScheduler.ts:179-183`, `PlaybackPositionTracker.ts:81-92`. The lost lookahead from PERF-01 would also cause an audible skip.
- **The last <5 s of a track is probably never fed to the worklet**. `checkBufferHealth()` pauses the feed when the ring drops below 5 s and resumes only above 8 s. After the final chunk has arrived, the ring can never rise again, and nothing flushes the tail on `audio_stream_end` (`handleStreamEnd` only dispatches Redux state). The worklet then runs dry about 5 s before the end. Auto-advance in `PlaybackSessionContext` also needs `currentTime >= duration - 0.5`, so it may not fire. `BufferScheduler.test.ts` has no end-of-stream case.

## Checked, clean

- **Lists / virtualization**: library tracks (`TrackListViewContent`), track grid, albums (flat and per-era, `EraSection`), artists (`ArtistListContent`), queue (`QueuePanelExpanded`) and cache-stats track list are all `useVirtualizer`-windowed. `QueueTrackItem`, `AlbumCard`, `MediaCard`, `ArtistListItem`, `ArtistTrackRow` and `TrackTableRowItem` are memoized. Unvirtualized lists are bounded in practice: `AlbumTrackTable` (one album, typically under 100 rows; box sets rare), artist detail albums grid (`artist.tracks` is hard-coded `[]` in `useArtistDetailsData.ts`, so "All Tracks" never renders rows), playlists, similar-tracks modal (limit 20), and settings lists. Not worth a finding, though PERF-02 makes each `TrackTableRowItem` heavier than it needs to be.
- **Player 10 Hz tick**: `PlaybackSessionProvider` re-renders at 10 Hz, but `children` is stable and `controlsValue`/`progressValue` are split and memoized (#5006). `Player` passes only stable props to memoized children (#4632), and `QueuePanel` is memoized. `ProgressBar` uses inline `style` objects, not emotion `sx`, so there is no per-tick class generation.
- **Redux selectors**: no `useSelector(state => state)` anywhere in production code. The few whole-slice selectors (`usePlayerState`, `useQueueState`, `useQueue`) are consumed in production only by `useTrackContextMenu` and `useContextMenuActions` (PERF-02). `selectFormattedTime`/`selectPlaybackState` are documented internal-only and have no component subscribers. Store middleware: the logger is DEV-only, RTK immutable/serializable checks are dev-only.
- **WebSocket message rate**: audio PCM frames bypass Redux (binary `ArrayBuffer`, zero-copy decode) and progress dispatch is decile-throttled for the single streaming core. `position_changed` is 1 Hz. `player_state` carries no queue. `scan_progress` consumers are mounted only in settings. `artwork_updated` uses one refcounted global subscription plus `useSyncExternalStore` per album. Console logging is stripped in production builds (`dropConsole`).
- **Audio object lifecycle**: engine `dispose()` disconnects the gain node, the PCM ring is `dispose()`d on every replace and unmount (#4147), one shared `AudioContext` per sample rate with the analyser reused, `ScriptProcessor`/worklet node nulled after disconnect. No `createObjectURL`/`new Blob`/`FileReader` in production code, so there are no blob URLs to revoke. `pendingChunksRef` is cleared on cleanup and play, and bounded by the in-flight window. Memory growth that remains is PERF-01 (worklet queue).
- **Bundle**: per-icon MUI imports only (no `@mui/icons-material` barrel), no lodash/moment/charting libraries, `CozyLibraryView`, `SettingsDialog` and `KeyboardShortcutsHelp` are `lazy()`; `EditMetadataDialog`/`SimilarTracksModal` are lazy. The vendor/App split is a documented deliberate trade-off (#4697). Built `dist/` (2026-09-17): vendor 696 kB, App 332 kB, CozyLibraryView 145 kB, Settings 34 kB. **CMP-09's orphan clusters are tree-shaken out of the bundle**: strings unique to QueueRecommendationsPanel, QueueStatisticsPanel, QueueSearchPanel, ConnectionDetailsPanel and TrackInfo (`Expand recommendations`, `Expand statistics`, `Close search panel`, `Connection status details`, `No track playing`) do not occur in any `dist/*.js`. The orphans cost maintenance, not bytes. Minor note: `dist/mse-test.html` (14 kB dev page from `public/`) ships in the production build.
- **Images**: artwork uses size-hinted thumbnails (`getArtworkUrl({size})`, `withArtworkSize`) in `AlbumCard`, `TrackRow` (80 px), `TrackCard` and palette extraction (64 px), with `loading="lazy"` on the grid/row/player images. None set `decoding="async"` (cosmetic, skipped). Palette cache is LRU-bounded (#5020).
- **Polling / timers**: React Query defaults are sane (`staleTime` 5 min, no refetch-on-focus). The only intervals are the 100 ms position tick (gated on `isPlaying`), cache-stats/health polls (settings-only), fingerprint coverage poll (only while work is pending), WS heartbeat, and the BufferScheduler feed loop (PERF-01). Listener add/remove pairs are balanced.
- **Effect cascades**: `useAudioStreamingCore` already reads `isPaused` via a ref (#3624), `useWebSocketMessages` holds callbacks in refs, `useQueueFetch` uses an `isActive` guard. The one real cascade is HK-07 (already filed).


#### Dim 8 (Accessibility) — Checked, clean
- **Single `<h1>` per view (specced invariant)**: holds. Library views render the sole `<h1>` through `ViewContainer.tsx:64` (`component="h1"`); album/artist detail views (rendered without `ViewContainer`) use `DetailViewHeader.tsx:137` (#5391, intact). The top-bar title is a non-heading box (#5013). `LibraryHeader.tsx` (a second `<h1>`) is unmounted (CMP-09). `ErrorBoundary` `<h1>` only appears when no custom `fallback` is passed, and every mounted boundary passes one.
- **View-change announcement**: `AppViewAnnouncement.tsx` is mounted in `ComfortableApp.tsx` and is a correct `role="status" aria-live="polite" aria-atomic` region with a label for each known view.
- **Landmarks**: `banner` (`AppTopBar`), `nav` "Library navigation" (`SidebarContent`), `main` (`AppMainContent`), player `region`. `aria-current="page"` on active nav items.
- **Progress bar**: real `role="slider"` with `aria-valuemin/max/now/valuetext`, `aria-disabled`, arrow/Home/End keys, a throttled seek live region, and a visible focus ring. Volume uses a native `<input type="range">`, so keyboard support and value exposure come built in. Mute and previous/next/play-pause buttons have `aria-label`s. (A11Y-01 breaks the key handling from outside; the widgets themselves are fine.)
- **Play/pause announcement** (#4474), **queue reorder announcement** (#4536) and the playback error banner (`role="alert"`) are all present.
- **Icon-only buttons**: a multi-line scan of every `IconButton`/`button`/`Box component="button"` found no unlabelled icon-only control (the design-system `IconButton` falls back to MUI Tooltip `title` as `aria-label`, e.g. `FoldersList` remove; its label does not name the folder, a nit).
- **Clickable non-interactive elements**: a multi-line scan for `onClick` on `div`/`span`/`tr`/`li` found only the dialog overlays (`QueueSearchPanel`, `ClearQueueDialog`, `ConfirmationDialog`, which have keyboard Escape/trap alternatives), `DropZone` and `PlaylistListHeader` (both have role, tabIndex and onKeyDown), and `TableCell` `stopPropagation` wrappers. Artist, album and playlist items are real `ListItemButton`/`<button>`s.
- **Focus rings**: every `outline: 'none'` in components is paired with an explicit `:focus-visible` or state-based ring (PlaybackControls, VolumeControl, ProgressBar, Player queue button, ArtistHeader, AlbumActionButtons); `globalStyles.ts` has a global `:focus-visible` outline. #5342 (invisible row buttons on focus) is fixed.
- **Dialog semantics**: the three custom dialogs set `role="dialog"`, `aria-modal`, `aria-labelledby`, and trap focus through `useDialogAccessibility`/`focusManagement` (#5394 intact; no hand-rolled trap elsewhere). The other dialogs are MUI `Dialog`s, whose built-in trap and `DialogTitle` labelling apply.
- **Lists/labels**: queue list is `ul role="list"` with `aria-current` (#3649); settings sliders and switches have names; the track listbox uses roving tabindex with Arrow/Home/End.
- **Document**: `lang="en"` on `index.html`, no positive `tabindex` values found.
- **Not verified (needs a runtime or screen-reader check)**: where focus lands after the MUI dialogs (Edit Metadata, Similar Tracks, Create Playlist) close when launched from a context-menu item that unmounts with the menu; whether Chromium suppresses the click on a Space `keydown` `preventDefault()` for `<button>`s exactly as described in A11Y-01 (Enter is certain, Space is the documented Chromium behavior); whether NVDA/JAWS announce the freshly inserted live region in A11Y-05.

#### Dim 9 (Test Coverage) — Checked, clean
- Skipped tests: 0 `it.skip/describe.skip/it.todo/xit` in any spec (the one grep hit is a message string in the #5119 guard). The #5119 guard `integration-tests-exercise-production-code.test.ts` is sound.
- Snapshots: no `toMatchSnapshot` / `.snap` files anywhere.
- Global WebSocketContext mock: all 6 `WebSocketContext.*` specs and `websocket-realtime.test.tsx` correctly `vi.unmock` the context; `hooks/websocket/__tests__/useWebSocketMessages.test.ts` deliberately uses the mock via `vi.mock` and asserts against it appropriately; `useWebSocketConnection.*` / `websocketConnectionCore.*` do not import the context. No spec named like the real implementation asserts against the global mock.
- Baseline: all 101 entries (18 files) point to files that exist and test names that still appear; no stale entries; `--strict-stale` is wired in CI; the script fails on missing report, invalid JSON and 0 tests (limits in TST-07).
- Memory: no `while(true)`/`for(;;)`; the only `setInterval` in specs are a spy (`useAudioVisualization`) and a cleaned-up interval inside a mock (`PlayerTickMemoization`); all `useFakeTimers` uses (32) are balanced by `useRealTimers` and the global `afterEach`.
- Async: only one un-awaited `userEvent` call in the suite (TST-05); no `waitFor` callbacks with dispatches other than that one; `new Promise(r => setTimeout(r, n))` real sleeps appear 6 times, none with an `n` of 3+ digits.
- Selectors/slices tests use real reducers via `configureStore`, not mocked stores; `apiRequest.test.ts` really does not mock the module under test.
- `fireEvent` (110 uses, 21 files) vs `userEvent` (170 uses, 37 files): mixed but not a defect in itself.
- Large datasets: queue utilities and `useQueueSearch` / `useQueueRecommendations` have 1k-10k-item cases.

#### Dim 9 (Test Coverage) — Cross-references (not re-filed)
- dim_4 TS-10: 133 `tsc` errors in 22 test files.
- dim_5 DS-02: `src/theme/__tests__/cssCustomPropertyProducers.test.ts`, `src/design-system/__tests__/cssVariablesTokenParity.test.ts` (and `darkOnlyTokenLeak`) read the unloaded `src/index.css` via `?raw`, so they guard no runtime behaviour.

