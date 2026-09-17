# Integration Audit — 2026-09-17

**Scope**: the 9 data flows between the React frontend, the FastAPI backend and the audio engine
**Depth**: deep | **Flows**: all 9 | **HEAD**: `61948c73`
**Method**: one agent per flow, at most 3 at a time. Each boundary was checked from both the sender's and the receiver's side. The orchestrator then re-checked every HIGH and MEDIUM claim against the source, and changed the severity or description where the evidence did not support it. Findings were deduplicated against the last 2,000 GitHub issues (111 open) and the 2026-09-13 integration report.

Context: since 2026-09-13 the frontend moved to Vite 8, and today's fixes landed: the prebuffer change listener (#5508), the preset narrowing to `'adaptive'`, and the backend restart notice (#5487). The flows that changed most (playback, seek) came back clean.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 1 |
| MEDIUM   | 9 |
| LOW      | 6 |
| **Total**| **16** |

**Severity changes and corrections made by the orchestrator**
- **INT-F5-01: stays HIGH, but the description was corrected.** The agent said a library-row pause never stops the local audio engine. It does: `useAudioStreamingCore` pauses the engine when Redux `isPlaying` turns false. Two defects remain. The row's WebSocket `pause` blocks the backend stream task, and **no frontend code ever sends `resume`**, so resuming from the transport bar plays out the buffered audio and then stops. Clicking the row again restarts the track from 0.
- **INT-F7-01: MEDIUM → LOW.** The 404-prone `artwork_url` is currently rendered by no UI (see INT-F7-02).
- **INT-F6-02: MEDIUM → LOW.** `FingerprintQueue.enqueue()` does only in-memory work under a lock, with no database or I/O. #4702, the same pattern, was LOW. It is also a different site from open #5390, which covers the worker's dequeue loop.
- **INT-F9-05: MEDIUM → LOW.** An undo feature nothing calls breaks nothing a user can see. Whether to ship it or delete it is a product decision.

**Key themes**
1. **Two control paths for one action.** Pause and resume are split between local-only and WebSocket-only paths (INT-F5-01). The same kind of split exists in library refresh: only `library_updated` triggers a refetch, while track removal broadcasts `library_tracks_removed`, which nothing refetches on (INT-F4-01).
2. **Sibling sites missed by earlier sweeps.** A bare `fetch()` that #5019's sweep missed (INT-F2-03). A settings endpoint that #5467 didn't cover (INT-F4-02). Synchronous `enqueue()` calls that #4702 didn't cover (INT-F6-02). A downloaded-artwork size cap that #4439 didn't cover (INT-F7-04). Search-request redirects that #5330 didn't cover (INT-F7-05).
3. **Frontend types that don't match the real payload.** The search hook's own inline type expects a singular `artist` that `Track.to_dict()` never sends (INT-F2-01). Settings types are non-nullable where the backend sends `null` (INT-F3-01). There are dead `crestFactor`/`centroid` fields (INT-F2-02).
4. **Features built but never connected to the UI.** Queue undo (INT-F9-05), `job_progress` (INT-F5-02), player-bar artwork via a `TrackInfo.tsx` nothing imports (INT-F7-02), and similarity graph builds (noted, not a defect).
5. **Areas that remain well hardened.** Playback (sample rate, chunk tiling, frame format, underrun handling, the restart notice) and seek (drift clamp, stale-chunk draining on both sides, last-seek-wins, seek while paused, level continuity) found nothing new. Enhancement preset mirrors, cache-key participation and stale-stream rejection were also clean.

---

## Flow Coverage Matrix

| # | Flow | Result | New findings | Existing (open) re-confirmed |
|---|------|--------|--------------|------------------------------|
| 1 | Track Playback | Clean | — | #5477 |
| 2 | Library Browsing | Findings | INT-F2-01 (M), INT-F2-03 (M), INT-F2-02 (L) | #5497, #5498, #5499, #5501, #5131, #5049 |
| 3 | Audio Enhancement | Finding | INT-F3-01 (M) | #5474, #5476, #5405, #5357, #5271, #4760 |
| 4 | Library Scanning | Findings | INT-F4-01 (M), INT-F4-02 (M) | #5475, #5500 |
| 5 | WebSocket Lifecycle | Findings | INT-F5-01 (H), INT-F5-02 (L) | #5469, #5476, #5468 |
| 6 | Fingerprint & Similarity | Findings | INT-F6-01 (M), INT-F6-02 (L) | #5390, #5381, #5273, #5509 |
| 7 | Artwork | Findings | INT-F7-02 (M), INT-F7-03 (M), INT-F7-04 (M), INT-F7-01 (L), INT-F7-05 (L) | #5473 |
| 8 | Seek & Rebuffer | Clean | — | #5409, #5446, #5258, #5477 |
| 9 | Queue & Playback State | Finding | INT-F9-05 (L) | #5460, #5358, #5189 |

**Closed issues re-verified as still fixed** (no regressions): #5461, #5462, #5464, #5487, #4784, #4557, #5254, #4815, #4563, #5385, #5459, #5402, #5455, #5456, #5458, #5465, #5466, #5467, #5470, #5471, #5057, #5505, #5267, #5506, #4679, #4447, #4901, #5255, #4526, #4527.

---

## Findings

### HIGH

#### INT-F5-01: Pause/resume has two disconnected control planes — the library-row pause button breaks playback instead of pausing it

- **Severity**: HIGH
- **Flow**: Flow 5 (WebSocket Lifecycle) — inbound command routing / dual control-plane split
- **Boundary**: Frontend (library view) → Backend WS handler → Frontend (Redux/local audio engine)
- **Location**: `auralis-web/frontend/src/components/library/usePlaybackState.ts:30-35` (sender) → `auralis-web/backend/ws_handlers/playback_control.py:25-38` (`handle_pause`) → `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:253-256` (receiver) vs. the canonical local pause at `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:511-534` and restart-from-0 at `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:72`
- **Status**: NEW
- **Description**: The app has two independent implementations of "pause", and they are not connected to each other or to the backend consistently:
  1. **Canonical transport bar / Space key** (`PlaybackSessionContext.handlePlayPause` → `usePlayEnhanced()` → `useAudioStreamingCore.pausePlayback()`/`resumePlayback()`) is **purely local**: it holds/resumes the Web Audio playback engine and never sends a WS `pause`/`resume`/`stop` command at all. The backend keeps rendering and streaming chunks regardless (self-limited only by `buffer_full`/`buffer_ready` flow control once the local PCM buffer fills).
  2. **Library grid/list row play-pause icon** (`components/library/Items/tracks/useTrackRowHandlers.ts:28-38` → `usePlaybackState.handlePause`, wired via `CozyLibraryView.tsx:256` `onPause={handlePause}`) does the opposite: it sends **only** the WS `pause` command (`wsContext.send({ type: 'pause' })`) and does **not** call the local engine's `pausePlayback()`. Backend's `handle_pause` clears the per-connection `pause_events` entry, which halts the *server-side chunk-streaming loop* (no more chunks are produced/sent), and broadcasts `playback_paused`, which `usePlayerStateSync.ts:253-256` uses only to set Redux `isPlaying = false` — nothing subscribes to `playback_paused`/`playback_resumed` to drive the local audio engine (confirmed by grep: no production caller of `pausePlayback()`/`resumePlayback()` outside `PlaybackSessionContext`).
  3. There is **no WS `resume` sender anywhere in production code** (confirmed by exhaustive grep for `type: 'resume'` / `type: 'stop'` across `src/` — the only hits are in test files). Clicking the library row again while `isPlaying === false` does not resume: `useTrackRowHandlers.handlePlayClick` calls `onPlay(trackId)` → `usePlaybackState.handlePlayTrack` → `usePlayTrack.playTrack` → `startTrack(track.id)` with **no** `start_position`, i.e. a full **restart from 0**, not a resume from the pause point.
- **Evidence**:
  ```ts
  // usePlaybackState.ts:30-35 — the ONLY thing this "pause" does:
  const handlePause = useCallback(() => {
    wsContext.send({ type: 'pause' });
    // Redux state will sync via WebSocket player_state broadcast
  }, [wsContext]);
  ```
  ```python
  # playback_control.py:25-38 — halts server-side chunk production only
  async def handle_pause(websocket: WebSocket, state: StreamState) -> None:
      ws_id = _ws_id(websocket)
      async with playback_event_sequencer.transition_lock:
          pause_evt = state.pause_events.get(ws_id)
          if pause_evt is not None:
              pause_evt.clear()
          event_seq = playback_event_sequencer.next_transport_seq()
      await safe_send_text(websocket, {"type": "playback_paused", "data": {"state": "paused", "seq": event_seq}})
  ```
  ```ts
  // usePlayerStateSync.ts:253-256 — only flips a Redux flag, never touches audio
  const unsubscribePaused = subscribe('playback_paused', (message) => {
    if (!shouldApplyTransportEvent(message)) return;
    dispatch(setIsPlaying(false));
  });
  ```
  ```ts
  // useTrackRowHandlers.ts:28-38 — re-click always restarts, never resumes
  const handlePlayClick = useCallback((e) => {
    if (isCurrent && isPlaying && onPause) { onPause(); }
    else { onPlay(trackId); }   // -> playTrack -> startTrack(track.id), no resume position
  }, ...);
  ```
- **Impact**: Clicking the pause icon on any library track row (grid or list view, `CozyLibraryView`/`TrackListView`, which is the live library UI mounted from `AppMainContent.tsx`) does not stop the sound: the already-buffered PCM keeps playing through the local Web Audio graph while the backend stops sending new chunks and the UI shows "paused". Once the local buffer drains, audio stops abruptly (not a clean pause). Clicking play again does not resume — it restarts the same track from position 0, potentially overlapping with whatever tail of the original buffer was still playing. This is a directly reachable, everyday user action that visibly misbehaves, and it is the same class of bug #4541 fixed for play/next/previous (multiple control planes for one session) but that sweep evidently missed pause.
- **Suggested Fix**: Route the library row's pause/play-toggle through `usePlaybackControls().handlePlayPause` (the same entry point the transport bar uses) instead of a bespoke `wsContext.send({type:'pause'})`, so there is exactly one pause/resume implementation. If a direct WS `pause`/`resume` round-trip is still wanted (e.g. to also halt server-side chunk production immediately rather than waiting for `buffer_full`), have `usePlayerStateSync`'s `playback_paused`/`playback_resumed` subscriptions actually drive the shared session's local engine, and implement a real WS `resume` sender that carries the current playback position instead of relying on a full restart.
- **Orchestrator note**: The description is partly wrong, and the finding stays HIGH for a different reason. `useAudioStreamingCore.ts:565-577` watches Redux `isPlaying` and calls `playbackEngineRef.current.pausePlayback()` when it becomes false (#2252). So once the `playback_paused` broadcast arrives, a library-row pause **does** pause the local audio. These defects were verified against the code:
  1. The backend's `handle_pause` clears the stream task's pause event. Nothing in the frontend ever sends `resume` (flow control sends `buffer_ready`, which is a separate event). If the user then resumes from the transport bar or Space, `handlePlayPause` → `resumePlayback()` restarts only the local engine. The server-side stream stays blocked, so playback stops when the buffered audio runs out, partway through the track.
  2. Clicking the library row again restarts the track from 0 instead of resuming.

### MEDIUM

#### INT-F2-01: Global search track results read a field the backend never sends — subtitle renders "undefined • Album"
- **Severity**: MEDIUM
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend `GET /api/library/tracks?search=` → Frontend `useSearchLogic.ts`
- **Location**: `auralis-web/backend/routers/serializers.py:46-82` (`DEFAULT_TRACK_FIELDS`, `serialize_tracks`) + `auralis/library/models/track.py:156-189` (`Track.to_dict()`) → `auralis-web/frontend/src/components/library/Hooks/useSearchLogic.ts:79-90,120`
- **Status**: NEW
- **Description**: `GlobalSearch`'s search hook declares its own ad-hoc response type instead of using the canonical `trackTransformer`/`TrackApiResponse`:
  ```ts
  interface SearchTrackResponse {
    id: number;
    title: string;
    artist: string;   // <-- never emitted by the real endpoint
    album: string;
    album_id?: number;
  }
  ...
  subtitle: `${track.artist} • ${track.album}`,
  ```
  For a real (non-Mock) track, `serialize_tracks()` prefers `Track.to_dict()`, which emits `artists` (a list) but never a singular `artist` key — that key exists only in `DEFAULT_TRACK_FIELDS`, the Mock/fallback path `serialize_object()` uses only when `to_dict()` is unavailable or raises. This is the exact class of bug `trackTransformer.ts` fixed for the rest of the app under #2263 (`apiTrack.artists?.[0] ?? apiTrack.artist`), but `useSearchLogic.ts` bypasses that transformer entirely with its own inline interface and never received the fix.
- **Evidence**: `Track.to_dict()` return dict (track.py:156-189) contains `id, title, duration, sample_rate, bit_depth, bitrate, channels, format, filesize, peak_level, rms_level, dr_rating, lufs_level, mastering_quality, recommended_reference, processing_profile, album_id, track_number, disc_number, year, comments, lyrics, play_count, last_played, skip_count, favorite, album, artwork_url, artists, genres, created_at, updated_at` — no `artist` singular key anywhere. `TrackRepository.search()` (`track_repository_search.py:23`) returns real `Track` ORM rows, not Mocks, so the fallback path is never taken in production.
- **Impact**: Every track result in the global search dropdown shows `"undefined • <album>"` as its subtitle in production (album and artist search results are unaffected — `Album.to_dict()` does emit `artist`, and `ArtistResponse` emits `album_count`/`track_count`, both of which `useSearchLogic.ts` reads correctly). No test in `GlobalSearch.test.tsx` mocks a realistic response shape, so this is untested and has shipped unnoticed.
- **Suggested Fix**: Route the tracks branch of `performSearch()` through the existing `transformTrack`/`TrackApiResponse` (read `artists?.[0]` with an `artist` fallback), matching how every other track-consuming call site already handles this field, instead of maintaining a second, incorrect ad-hoc interface.

#### INT-F2-03: `useInfiniteAlbums.ts` still calls bare `fetch()` with no timeout — sibling of #5019, missed by that sweep
- **Severity**: MEDIUM
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Frontend `useInfiniteAlbums.ts` → Backend `GET /api/albums`
- **Location**: `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:44-51`
- **Status**: NEW
- **Description**: `fetchAlbums()`, the `queryFn` backing `useInfiniteAlbums()` (used live by `CozyAlbumGrid.tsx`, the album grid's data source), calls the browser `fetch()` directly instead of the shared `apiRequest` transport:
  ```ts
  const response = await fetch(getApiUrl(`/api/albums?${params}`));
  if (!response.ok) {
    throw await httpErrorFromResponse(response);
  }
  ```
  `#5019` (`73243c8d`) swept exactly this pattern — "bare `fetch()` call sites have no upper bound, so a stalled backend leaves their loading states pending forever" — across 8 call sites and migrated them to `get()`/`post()`/`put()`, which compose `DEFAULT_TIMEOUT_MS` (30s) with the caller's `AbortSignal`. `useInfiniteAlbums.ts` was not one of the 8 migrated files and still has no timeout of any kind: TanStack Query's `useInfiniteQuery` does not impose one either — it only retries on a *rejected* promise, and a `fetch()` that never resolves (stalled backend, per #4815's class of bug) never rejects.
- **Impact**: If the backend stalls or hangs while serving `GET /api/albums` (matches the exact scenario #4815/#5019 target), the album grid's `isFetchingNextPage`/`isLoading` states hang indefinitely with no timeout, no error, and no way for the user to recover short of reloading the page.
- **Suggested Fix**: Route `fetchAlbums()` through `get()` from `@/utils/apiRequest` (as every other list-fetching hook in this flow now does), passing `pageParam`/`search` as query params the same way and keeping the raw-JSON return shape `transformAlbumsResponse` expects.

#### INT-F3-01: Settings dialog renders a legacy-degraded `default_preset`/`enhancement_intensity` as a broken control instead of falling back to a sane default
- **Severity**: MEDIUM
- **Flow**: Flow 3 (Audio Enhancement)
- **Boundary**: Backend `GET /api/settings` response → Frontend Settings dialog
- **Location**: `auralis-web/backend/routers/settings.py:172-197` (`SettingsResponse._degrade_unknown_preset` / `_degrade_invalid_intensity`) → `auralis-web/frontend/src/services/settingsService.ts:14-49` (`UserSettings` interface) → `auralis-web/frontend/src/components/settings/SettingsDialogContent.tsx:78-80` → `auralis-web/frontend/src/components/settings/EnhancementSettingsPanel.tsx:29-73`
- **Status**: NEW
- **Description**: `SettingsResponse` deliberately types `default_preset: EnhancementPresetLiteral | None` and `enhancement_intensity: EnhancementIntensity | None`, and its `mode="before"` validators actively rewrite an out-of-range/legacy stored value (e.g. a pre-#4861 `'warm'`/`'bright'`/`'punchy'`/`'gentle'` row, or a pre-#4600 out-of-range intensity) to `None` at response time so the API doesn't 500 — this is the correct backend-side half of the "degrade, don't echo the bad value" contract the audit brief asks for. Nothing ever migrates the stored DB row (`default_preset` is a plain `String` column per the code's own comments, and no migration in `auralis/library/migrations/` touches it), so any user whose account predates the 2026-09-13 preset narrowing keeps `default_preset='warm'` (or similar) in the DB indefinitely, and every `GET /api/settings` for that account now returns `default_preset: null`.

  The frontend never learned about this: `UserSettings.default_preset` is typed as a bare non-nullable `string` (`settingsService.ts:38`, similarly `enhancement_intensity: number` at line 40), and `isUserSettingsShape()` in `responseGuards.ts` does not validate either field. `useSettingsDialog.ts`'s `getValue()` is re-declared with an `any` return type in `SettingsDialogContent.tsx`'s local prop interface (`getValue: <K extends keyof SettingsUpdate>(key: K) => any`), which erases the `| null` that the real implementation returns. So `defaultPreset={getValue('default_preset')}` passes `null` straight into `EnhancementSettingsPanel`'s `<Select value={defaultPreset}>` with no `?? 'adaptive'` fallback — unlike the sibling `scanFolders={getValue('scan_folders') ?? []}` a few lines above, which does guard. The `<Select>` only has one `<MenuItem value="adaptive">`, so a `null` value matches nothing MUI recognizes as a valid selection. The same unguarded pass-through happens for `enhancementIntensity={getValue('enhancement_intensity')}` feeding a `<Slider value={enhancementIntensity} min={0} max={1}>` with no numeric fallback either.
- **Evidence**:
  ```python
  # routers/settings.py
  @field_validator("default_preset", mode="before")
  @classmethod
  def _degrade_unknown_preset(cls, value: object) -> object:
      if value is None or value in VALID_PRESETS:
          return value
      logger.warning(...)
      return None   # <-- legacy 'warm' etc. becomes null on the wire
  ```
  ```typescript
  // services/settingsService.ts
  export interface UserSettings {
    ...
    default_preset: string;        // lies: backend can send null
    enhancement_intensity: number; // lies: backend can send null
    ...
  }
  ```
  ```typescript
  // components/settings/SettingsDialogContent.tsx
  getValue: <K extends keyof SettingsUpdate>(key: K) => any;   // erases the real `| null`
  ...
  scanFolders={getValue('scan_folders') ?? []}       // guarded
  ...
  defaultPreset={getValue('default_preset')}          // NOT guarded
  enhancementIntensity={getValue('enhancement_intensity')}  // NOT guarded
  ```
- **Impact**: For any account carrying a pre-2026-09-13 `default_preset` (or a pre-#4600 out-of-range `enhancement_intensity`), opening Settings → Enhancement shows the preset `<Select>` with no visible selection (MUI logs an out-of-range-value dev warning) and/or the intensity `<Slider>` with an invalid/`NaN` thumb position, instead of the intended "just show Adaptive/a sane default" behavior the backend validators were written to enable. It's UI-only — the actual runtime `enhancement_settings` dict (seeded separately via `helpers.seed_enhancement_settings`, which keeps the *previous* in-memory value rather than adopting the invalid one) is unaffected, so playback itself is not mis-mastered by this bug. The user can still manually pick "Adaptive" from the dropdown to clear it.
- **Suggested Fix**: Either type `UserSettings.default_preset`/`enhancement_intensity` as `string | null`/`number | null` in `settingsService.ts` and have `EnhancementSettingsPanel` fall back explicitly (`defaultPreset ?? 'adaptive'`, `enhancementIntensity ?? 1.0`), or fix `SettingsDialogContent.tsx`'s local `getValue` prop type to match the real `SettingsUpdate[K] | null` return type so TypeScript itself catches the missing fallback (as it should have here).

#### INT-F4-01: Removing a scan folder, or rescanning to clean up deleted files, deletes the tracks but never tells the library view to refresh
- **Severity**: MEDIUM
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Backend (`services/missing_tracks.py`, `routers/library_scan.py`, `routers/settings.py`) → Frontend (`useLibraryWithStats.ts`)
- **Location**: `auralis-web/backend/services/missing_tracks.py:44-77` (`prune_tracks_under_folder`) → `auralis-web/backend/routers/settings.py:383-399` (`remove_scan_folder`); `auralis-web/backend/routers/library_scan.py:362-402` (`scan_library`, prune-return discarded + `library_updated` condition) → `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:72-78`
- **Status**: NEW (sibling of the CLOSED #5458/#5467, which added the two prune calls but not their `library_updated` follow-through)
- **Description**: `useLibraryWithStats.ts:78` is the *only* place in the frontend that refetches the track/stats view — and it does so *only* on the `library_updated` WS message (line 78: `useWebSocketMessages(['library_updated'], handleLibraryUpdated)`). `library_tracks_removed` is consumed nowhere except `useScanProgress.ts`, purely to update the *last-scan-result counter* (`filesRemoved`), never to trigger a refetch. Two prune paths never fire `library_updated`:
  1. **`remove_scan_folder`** (`routers/settings.py:383-399`) calls `prune_tracks_under_folder()`, which (per `missing_tracks.py:66-77`) only ever broadcasts `library_tracks_removed` — there is no `library_updated` call anywhere in that function or its caller. The confirmation dialog the user just clicked through says *"Tracks from this folder will be removed from the library"* (`SettingsDialog.tsx:108`), but nothing tells the already-rendered library view to refresh.
  2. **`scan_library`** (`routers/library_scan.py:367`) calls `await prune_missing_tracks(library_database, connection_manager)` and **discards its return value**. The `library_updated` broadcast three lines later (`library_scan.py:392`) is gated on `if result.files_added or result.files_updated:` — it has no way to know a prune happened. Contrast with the auto-scanner's equivalent path (`library_auto_scanner.py:354,385`), which captures `removed = await prune_missing_tracks(...)` and correctly guards on `if files_added or removed:`.
- **Evidence**:
  ```python
  # routers/library_scan.py:362-368 — manual scan: prune runs, but its count is thrown away
  await prune_missing_tracks(library_database, connection_manager)
  ...
  if connection_manager:
      scan_complete_payload: ScanCompletePayload = {...}
      await broadcast_typed(connection_manager, "scan_complete", scan_complete_payload)
      if result.files_added or result.files_updated:   # <-- no `removed` term
          await broadcast_typed(connection_manager, "library_updated", {...})

  # library_auto_scanner.py:354,385 — auto-scan: same prune, correctly wired
  removed = await prune_missing_tracks(self._library_database, self._connection_manager)
  ...
  if files_added or removed:                            # <-- correct
      await broadcast_typed(self._connection_manager, "library_updated", {...})

  # services/missing_tracks.py:66-77 — remove-folder path never broadcasts library_updated at all
  if removed:
      logger.info(f"🗑️  Removed {removed} tracks under removed scan folder {folder}")
      if connection_manager is not None:
          await broadcast_typed(connection_manager, "library_tracks_removed", {"count": removed}, suppress_errors=True)
      # no library_updated broadcast anywhere in this function or its one caller (settings.py:397)

  # useLibraryWithStats.ts:72-78 — the only refetch trigger in the app
  const handleLibraryUpdated = useCallback(() => {
    fetchTracks();
    if (includeStats) refetchStats();
  }, [fetchTracks, includeStats, refetchStats]);
  useWebSocketMessages(['library_updated'], handleLibraryUpdated);
  ```
- **Impact**: Two concrete user-visible cases: (1) remove a scan folder in Settings — the confirmation dialog promises the tracks disappear from the library, and the DB row is in fact deleted (verified: `remove_tracks_under_folder` uses `Path.is_relative_to()`, correctly boundary-safe), but the already-open library grid/list keeps showing them until the user manually navigates away and back or reloads the page; (2) manually rescan a folder after deleting some files on disk with none added/updated — `cleanup_missing_files` removes the dead rows, `scan_complete` fires with `files_added: 0, files_updated: 0`, and the view stays stale for the same reason. Neither case corrupts data (the DB is correct), but it visibly contradicts the UI's own promise and the auto-scanner's behavior for the identical operation.
- **Suggested Fix**: Capture `prune_missing_tracks`'s/`prune_tracks_under_folder`'s return count in both callers and fold it into the `library_updated` trigger condition, exactly as `library_auto_scanner.py` already does — e.g. `removed = await prune_missing_tracks(...)` in `library_scan.py`, then `if result.files_added or result.files_updated or removed:`; and add an unconditional `library_updated` broadcast (with `action: "scan"`, `track_count: 0`) inside `prune_tracks_under_folder`'s `if removed:` branch (or its one caller in `settings.py`) so folder removal refreshes the view every time it actually deletes rows.

#### INT-F4-02: `PUT /api/settings`'s generic `scan_folders` removal path revokes path trust but skips the track-prune step the dedicated remove-folder endpoint added in #5467
- **Severity**: MEDIUM
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Frontend (`settingsService.updateSettings`) → Backend (`routers/settings.py`)
- **Location**: `auralis-web/backend/routers/settings.py:303-360` (`update_settings`, diff/unregister block at 344-350) vs. `auralis-web/backend/routers/settings.py:381-399` (`remove_scan_folder`)
- **Status**: NEW (same class as CLOSED #5467, but on the sibling endpoint #5467's fix never touched)
- **Description**: There are two backend routes that can remove an entry from `scan_folders`: the dedicated `POST /api/settings/scan-folders/delete` (`remove_scan_folder`) and the generic `PUT /api/settings` (`update_settings`), which accepts a full replacement `scan_folders` array and diffs it against the previous value to register/unregister path-trust allowlist entries (`update_settings`'s own docstring at line 315-318 explicitly says it exists "so a folder added via this generic route skips both [validation and allowlist registration]" — i.e., it is deliberately meant to behave identically to the dedicated endpoints for this column). #5467 added `prune_tracks_under_folder()` to `remove_scan_folder` only; `update_settings`'s diff loop (lines 344-350) calls `unregister_allowed_directory(Path(removed))` for every folder dropped from the array but never prunes the Track rows under it.
- **Evidence**:
  ```python
  # routers/settings.py:344-350 — update_settings: unregisters trust, never prunes tracks
  if 'scan_folders' in payload:
      previous_folders = set(previous_list)
      new_folders = set(payload['scan_folders'] or [])
      for added in new_folders - previous_folders:
          register_allowed_directory(Path(added))
      for removed in previous_folders - new_folders:
          unregister_allowed_directory(Path(removed))   # <-- no prune_tracks_under_folder call

  # routers/settings.py:383-397 — remove_scan_folder: has both steps
  unregister_allowed_directory(Path(body.folder))
  library_database = get_library_database() if get_library_database else None
  if library_database is not None:
      await prune_tracks_under_folder(library_database, body.folder, connection_manager)
  ```
  The shipped frontend never actually drives this path today — `settingsService.ts`'s `updateSettings()` is called only from `useSettingsDialog.handleSave` with `pendingChanges`, and nothing in the Settings UI ever puts `scan_folders` into `pendingChanges` (`handleAddScanFolder`/`handleConfirmRemove` both call the dedicated `addScanFolder`/`removeScanFolder` endpoints directly, bypassing `pendingChanges` entirely).
- **Impact**: If any current or future client (a second frontend surface, a script, or a future refactor that folds folder editing into the generic settings form) removes a folder via `PUT /api/settings` instead of the dedicated endpoint, it reproduces exactly the bug #5467 fixed: Track rows under the removed folder stay visible/browsable/queueable in the library while every path-validated endpoint (metadata, tracks, enhancement) starts rejecting them with an unexplained 400, since the folder's path trust was just revoked out from under them. Currently latent rather than user-visible, since the shipped UI never exercises this branch.
- **Suggested Fix**: Factor the "for removed in previous_folders - new_folders" loop in `update_settings` to also call `prune_tracks_under_folder(library_database, removed, connection_manager)` for each dropped folder, mirroring `remove_scan_folder`. `library_database`/`connection_manager` are already available via the router factory's closure (same objects `remove_scan_folder` uses).

#### INT-F6-01: `/similar`, `/compare`, `/explain` always claim a missing fingerprint was "queued", even when the queue rejected it
- **Severity**: MEDIUM
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Backend (`routers/similarity_common.py`) → Frontend (`hooks/fingerprint/similarityErrorState.ts`)
- **Location**: `auralis-web/backend/routers/similarity_common.py:157-170` (`require_fingerprinted_tracks`) → `auralis-web/frontend/src/hooks/fingerprint/similarityErrorState.ts:72-90` (`classifySimilarityError`)
- **Status**: NEW (related to, but distinct from, the closed #5267)
- **Description**: `require_fingerprinted_tracks()` — shared by `GET /similar`, `/compare` and `/explain` — calls `await enqueue_for_fingerprinting(track_id)` but discards its boolean result, then unconditionally raises a 404 whose `detail` says the track "does not have a fingerprint. Queued for background processing." regardless of whether the enqueue actually succeeded. `enqueue_for_fingerprinting()` itself was fixed by #5267 to correctly return `queue.enqueue()`'s real result (`False` when the in-memory queue is full at `MAX_QUEUE_SIZE = 5000`, or in the rare race where the track is claimed as `processing` between the `exists()` check and the enqueue call) — but this caller never looks at it. The frontend's `classifySimilarityError()` trusts the word "queued" in the message unconditionally: it renders `kind: 'queued'`, `retryable: true`, "Check back in a few seconds" — a calm, transient state — even for a track that was never actually queued and will not self-heal until something else (e.g. a full `enqueue-all` sweep) enqueues it.
- **Evidence**:
  ```python
  # auralis-web/backend/routers/similarity_common.py:157-170
  for track_id in track_ids:
      if not await asyncio.to_thread(repos.fingerprints.exists, track_id):
          await enqueue_for_fingerprinting(track_id)   # return value discarded
          raise NotFoundError(
              "Track",
              detail=(
                  f"Track {track_id} does not have a fingerprint. "
                  "Queued for background processing."
              ),
          )
  ```
  Contrast with the sibling route that gets this right:
  ```python
  # auralis-web/backend/routers/fingerprint_status.py:138-150
  queued = await asyncio.to_thread(queue.enqueue, track_id)
  detail = (
      f"Fingerprint not available for track {track_id}. Queued for generation."
      if queued else
      f"Fingerprint not available for track {track_id}. "
      "Not queued (already pending, or the background queue is full) — try again shortly."
  )
  ```
  ```typescript
  // auralis-web/frontend/src/hooks/fingerprint/similarityErrorState.ts:72-90
  if (status === 404) {
    if (message.toLowerCase().includes(QUEUED_MARKER)) {
      return { kind: 'queued', title: 'Analysing this track',
        hint: 'It has been queued for fingerprinting. Check back in a few seconds.',
        retryable: true, transient: true };
    }
    ...
  ```
- **Impact**: `useSimilarTracks` is the one similarity endpoint with a live frontend consumer (`SimilarTracksModal`). When the on-demand queue is saturated (5000 entries — realistic during a large initial library import, since the same queue backs auto-scan and manual-scan enqueue too) or a track is mid-processing, a user opening "Similar Tracks" for an unfingerprinted track sees a calm "Analysing this track… check back in a few seconds" message that never resolves, instead of an accurate "still catching up" or actionable state.
- **Suggested Fix**: Capture `enqueue_for_fingerprinting()`'s return value in `require_fingerprinted_tracks()` and vary the 404 detail the way `fingerprint_status.py` already does (e.g. "Queued for background processing." vs "Not queued — the background queue is busy, try again shortly."). Optionally give `classifySimilarityError` a distinct `kind` for the "not actually queued" case so the UI can say something other than a fixed few-seconds ETA.

---

#### INT-F7-02: Live player bar renders no album artwork — `TrackInfo.tsx` is dead code, `Player.tsx`/`TrackDisplay.tsx` never show it
- **Severity**: MEDIUM
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Backend WS `player_state`/queue `artwork_url` → Frontend player-bar rendering
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:18,137` (imports/renders only `TrackDisplay`) and `auralis-web/frontend/src/components/player/TrackDisplay.tsx` (no artwork prop at all) vs. the orphaned `auralis-web/frontend/src/components/player/TrackInfo.tsx`
- **Status**: NEW
- **Description**: The backend correctly emits `artwork_url` for the currently-playing track (via `player_state`/queue TrackInfo — see INT-F7-01 for its own gap) and per-track artwork in the queue, but no component in `components/player/` actually renders it. `Player.tsx` composes `TimeDisplay`, `BufferingIndicator`, `ProgressBar`, `PlaybackControls`, `VolumeControl`, `TrackDisplay`, and `QueuePanel` — `TrackDisplay.tsx`'s props are only `title`/`artist`/`album`/`isLoading`, with no artwork field or `<img>` anywhere in the component. `QueuePanel/QueueTrackItem.tsx` likewise has no `<img>`/artwork rendering. The one component that does render artwork correctly — `TrackInfo.tsx` (uses `track.artworkUrl`, has an empty-state fallback, and has been maintained: closed #3650/#3634/#3505 all fixed bugs in it) — has zero production importers; `grep -rn "import.*TrackInfo" src` shows only its own test file (`components/player/__tests__/TrackInfo.test.tsx`) importing it. Git history shows an earlier "PlayerBarV2" that did show artwork (closed #3993 fixed a `loading=` attribute on "PlayerBarV2 artwork img"); that component no longer exists in the tree.
- **Evidence**:
  ```tsx
  // Player.tsx:11-21 — no artwork component imported
  import TimeDisplay from './TimeDisplay';
  import BufferingIndicator from './BufferingIndicator';
  import ProgressBar from './ProgressBar';
  import PlaybackControls from './PlaybackControls';
  import VolumeControl from './VolumeControl';
  import TrackDisplay from './TrackDisplay';
  import QueuePanel from './QueuePanel';
  ```
  ```tsx
  // TrackDisplay.tsx:19-50 — props carry no artwork field
  export interface TrackDisplayProps {
    title: string;
    artist?: string;
    album?: string;
    isLoading?: boolean;
    className?: string;
    ariaLabel?: string;
  }
  ```
  `grep -rn "import.*TrackInfo\b" src` (excluding WS type imports) returns only `components/player/__tests__/TrackInfo.test.tsx:12`.
- **Impact**: The most prominent, always-visible surface of the player (the bottom player bar) never shows album art, even though the data pipeline supports it end-to-end and a working component for it already exists in the tree. This is a functional/UX gap, not a crash, but it is a genuine boundary mismatch: the backend->WS contract promises artwork the frontend's primary consumer never uses.
- **Suggested Fix**: Wire `TrackInfo.tsx` (or a `MediaCardArtwork`-style thumbnail) into `Player.tsx` alongside `TrackDisplay`, sourcing the URL from the same `selectCurrentTrack` state `TrackInfo.tsx` already reads — fixing INT-F7-01 first so the URL it receives is null-safe. If the artwork-less bar is intentional, delete the orphaned `TrackInfo.tsx` component (and its test) instead so the codebase doesn't carry two contradictory implementations (violates the "no variants" project principle otherwise).

#### INT-F7-03: `ArtistHeader.tsx`'s artwork `onError` hides the image without falling back to the placeholder avatar
- **Severity**: MEDIUM
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Backend `Artist.artwork_url` (external CDN URL) → Frontend `ArtistHeader.tsx`
- **Location**: `auralis-web/frontend/src/components/library/Details/ArtistHeader.tsx:40-65`
- **Status**: NEW
- **Description**: `ArtistHeader` renders the artist's external artwork image when `artist.artworkUrl` is truthy, and otherwise renders an `ArtistAvatarCircle` initial-letter placeholder. On a load failure, its `onError` handler only sets `e.currentTarget.style.display = 'none'` — it never switches to the `ArtistAvatarCircle` branch (that branch is chosen once, at initial render, based on `artist.artworkUrl` truthiness, not on load success). The result is a blank circular void (no image, no letter, no icon) rather than the documented fallback. This is exactly the failure mode `config/middleware/security_headers.py`'s own comments describe as a **known, expected, frequent case**: `Artist.artwork_url` (per the deliberate #4526 exception) is an arbitrary external URL, and any MusicBrainz `image` relation host not on the small CSP `img-src` allowlist (`_ARTIST_ARTWORK_IMG_HOSTS`) is blocked by the browser and always fires `onError`. Every other artwork surface in the app that added an `onError` handler (`MediaCardArtwork.tsx`, closed #4437) falls back to a real placeholder; this one does not.
- **Evidence**:
  ```tsx
  // ArtistHeader.tsx:40-65
  artwork={
    artist.artworkUrl ? (
      <Box component="img" src={artist.artworkUrl} alt={artist.name}
        sx={{ width: 200, height: 200, borderRadius: '50%', ... }}
        onError={(e) => {
          // Fallback to placeholder on image load error
          e.currentTarget.style.display = 'none';
        }}
      />
    ) : (
      <ArtistAvatarCircle>{getArtistInitial(artist.name)}</ArtistAvatarCircle>
    )
  }
  ```
  The comment claims "Fallback to placeholder on image load error", but `display: none` produces an empty box, not the `ArtistAvatarCircle` sibling branch.
- **Impact**: For any artist whose MusicBrainz-sourced image points outside the CSP allowlist (documented as the common case, not an edge case, in `security_headers.py`), the artist detail page shows a blank circle instead of the initial-letter avatar the rest of the app uses consistently.
- **Suggested Fix**: Track failure in component state (`useState`) and render `ArtistAvatarCircle` when either `artworkUrl` is falsy or the load failed, mirroring `MediaCardArtwork.tsx`'s `imageFailed` pattern.

#### INT-F7-04: Downloaded artwork has no pixel-dimension bound — sibling gap of #4439
- **Severity**: MEDIUM
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Backend `services/artwork_downloader.py` (write) → `routers/artwork.py` GET (serve, full resolution)
- **Location**: `auralis-web/backend/services/artwork_downloader.py:346-372` (`ArtworkDownloader._save_artwork`) vs `auralis/library/artwork.py:245-285,303` (`ArtworkExtractor._bound_dimensions`, called from its own `_save_artwork`)
- **Status**: NEW
- **Description**: Closed #4439 ("No dimension bound on served artwork — arbitrarily large images streamed to client") added `_bound_dimensions()` — a PIL downscale to `_MAX_ARTWORK_DIMENSION = 2048` px — to the embedded/folder artwork extractor (`auralis/library/artwork.py`). The online-download path (`auralis-web/backend/services/artwork_downloader.py`), a separate module with its own unrelated `_save_artwork` method, was never given the same treatment: it only enforces `MAX_ARTWORK_PAYLOAD_BYTES` (5 MiB) on the downloaded bytes and sniffs the format extension via `_detect_image_extension`, with no PIL step and no dimension check. A highly-compressible image (e.g. a large flat-color PNG) can be well under 5 MiB while having an enormous pixel size, and `_save_artwork` writes it to disk unmodified. `GET /api/albums/{id}/artwork` (no `size` query param) then serves that file as-is via `FileResponse` — the thumbnail-bucket downscale path in `routers/artwork.py` only runs when the caller supplies `?size=`.
- **Evidence**:
  ```python
  # auralis-web/backend/services/artwork_downloader.py:346-372 — no dimension check
  async def _save_artwork(self, data: bytes, album_id: int, ext: str = "jpg") -> str:
      ext = _detect_image_extension(data, default=ext)
      data_hash = hashlib.md5(data).hexdigest()[:8]
      filename = f"album_{album_id}_{data_hash}.{ext}"
      filepath = self.cache_dir / filename
      await asyncio.to_thread(filepath.write_bytes, data)
      return str(filepath)
  ```
  ```python
  # auralis/library/artwork.py:303 — the ONLY writer that bounds dimensions
  artwork_data = self._bound_dimensions(artwork_data)
  ```
- **Impact**: A full-resolution `GET /api/albums/{id}/artwork` request (no `size` param — used by, e.g., a hero/detail view, or any caller omitting the hint) for artwork obtained via the online-download endpoint can stream an oversized bitmap to the browser/Electron renderer, reintroducing the decode-cost and memory problem #4439 fixed for the extraction path. Currently reachable only via a direct API call, since #5214 removed the frontend's UI for triggering a download — but the endpoint itself is live and unauthenticated (localhost-only).
- **Suggested Fix**: Share `_bound_dimensions`-equivalent logic (or move it to `artwork_security.py` alongside `detect_image_extension`, which the comment in `artwork_downloader.py:36-41` already notes was relocated for exactly this kind of cross-module sharing) and call it from `ArtworkDownloader._save_artwork` too.

### LOW

### LOW

#### INT-F2-02: `crestFactor`/`centroid` are dead Track fields — no backend track endpoint ever populates them
- **Severity**: LOW
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend `schemas/library.py::TrackResponse` / `routers/serializers.py::DEFAULT_TRACK_FIELDS` / `Track.to_dict()` → Frontend `api/transformers/types.ts::TrackApiResponse`, `api/transformers/trackTransformer.ts`
- **Location**: `auralis-web/frontend/src/api/transformers/types.ts:105-107` → `auralis-web/frontend/src/api/transformers/trackTransformer.ts:57-59` (backend side: `auralis-web/backend/schemas/library.py` `TrackResponse`, `auralis-web/backend/routers/serializers.py:46-82`, `auralis/library/models/track.py:156-189`, none of which declare `crest_factor` or `centroid`)
- **Status**: NEW
- **Description**: `TrackApiResponse` declares `crest_factor?` and `centroid?`, and `transformTrack()` maps them to `Track.crestFactor`/`Track.centroid`. No track-returning endpoint (`/api/library/tracks`, `/api/library/tracks/{id}`, album/artist track lists, playlist tracks) ever emits either key — they exist in neither `Track.to_dict()` nor `DEFAULT_TRACK_FIELDS` nor `TrackResponse`. A grep across `auralis-web/backend` and `auralis/library` for `crest_factor` as an output key returns nothing.
- **Evidence**: `grep -rn "'crest_factor'" auralis-web/backend auralis/library` → no matches. `trackTransformer.ts:57-59`: `crestFactor: apiTrack.crest_factor ?? undefined, centroid: apiTrack.centroid ?? undefined` — always `undefined` for every real response.
- **Impact**: No functional breakage (no component currently reads `Track.crestFactor`/`.centroid` for display), but the fields are a false contract: they imply data the backend does not provide, and a component added later that displays them would silently show nothing with no error.
- **Suggested Fix**: Either drop `crest_factor`/`centroid` from `TrackApiResponse`/`Track` domain type, or add them to `Track.to_dict()` (they exist as fingerprint dimensions — `crest_db`, `spectral_centroid` — under different names/scales) if the intent was to surface analysis data on the track list.

#### INT-F5-02: `subscribe_job_progress` / `job_progress` is fully implemented on both sides but never invoked by the shipped frontend

- **Severity**: LOW
- **Flow**: Flow 5 (WebSocket Lifecycle) — inbound/outbound message type reachability
- **Boundary**: Frontend → Backend (command never sent) / Backend → Frontend (payload never subscribed)
- **Location**: `auralis-web/backend/ws_handlers/messages.py:49-104` (`handle_subscribe_job_progress`, dispatched from `ws_handlers/connection.py:204-205`) ↔ `auralis-web/frontend/src/types/ws/system.ts` (types only, no sender/subscriber in production `src/`)
- **Status**: NEW
- **Description**: The backend implements a complete, carefully-guarded `subscribe_job_progress` handler (job_id validation, per-connection closure replacement, disconnect cleanup that unregisters only this connection's own subscription) and emits typed `job_progress` broadcasts. `job_progress` is correctly present in the frontend's `ALL_MESSAGE_TYPES` registry (`types/ws/registry.ts`) and has a defined message shape (`types/ws/system.ts`). However, an exhaustive grep of `auralis-web/frontend/src` (excluding tests) finds **zero** production call sites that send `{type: 'subscribe_job_progress', ...}` and **zero** production call sites that `subscribe('job_progress', ...)` or otherwise consume it. The whole path is reachable only from tests.
- **Evidence**:
  ```
  $ grep -rn "subscribe_job_progress" auralis-web/frontend/src | grep -v __tests__
  types/ws/system.ts:43: * Emitted by `ws_handlers/messages.py::handle_subscribe_job_progress` ...
  types/ws/system.ts:44: * connections that sent a `subscribe_job_progress` frame for that `job_id`;
  $ grep -rln "'job_progress'" auralis-web/frontend/src | grep -v __tests__
  types/ws/system.ts
  types/ws/registry.ts
  ```
- **Impact**: No functional breakage today (nothing depends on it), but it is dead protocol surface: whatever backend job-progress feature this was meant to expose (processing jobs tracked by `job_id` via `ProcessingEngine.register_progress_callback`) has no live UI. Low risk of drift since both ends still agree on shape; worth flagging so it isn't mistaken for a wired feature during future audits.
- **Suggested Fix**: Either wire a consumer (e.g. a job/progress toast or a mastering-job progress indicator) that sends `subscribe_job_progress` for jobs the UI cares about and subscribes to `job_progress`, or remove the handler/type if the feature was superseded by something else (e.g. polling `processing_job` REST endpoints) and document that decision.

#### INT-F6-02: Two more `FingerprintQueue.enqueue()` call sites still block the event loop synchronously — #4702 fixed only the `routers/` sites
- **Severity**: LOW
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Backend streaming/scan services → `analysis/fingerprint_queue.FingerprintQueue` (in-process, but crosses the async-event-loop / thread-lock boundary the queue itself documents as load-bearing)
- **Location**: `auralis-web/backend/core/stream_fingerprint.py:178` (`check_or_queue_fingerprint`) and `auralis-web/backend/services/library_auto_scanner.py:346` (`_do_scan`)
- **Status**: NEW (incomplete fix / missed sibling of closed #4702)
- **Description**: #4702 established the rule that every `async def` calling `FingerprintQueue.enqueue()` must offload it via `asyncio.to_thread`, and fixed the two call sites it scoped to under `auralis-web/backend/routers/` (`fingerprint_status.py`, and the batch loop in `library_scan.py`, which itself references "#4702" in a comment while wrapping its whole enqueue loop in `asyncio.to_thread`). Two more call sites outside that scoped directory were never converted and still call `queue.enqueue(...)` directly on the event loop from inside `async def` functions:
  1. `stream_fingerprint.check_or_queue_fingerprint()` — invoked from `stream_enhanced.py:200` at the start of every enhanced-audio WebSocket stream when the track's fingerprint is missing. Single-item, same shape as the original #4702 finding.
  2. `library_auto_scanner._do_scan()` — the exact "larger-N" sibling #4702's own Completeness Checks called "the more valuable of the two" to fix (a comprehension enqueueing every newly-added track after a scan, on the loop). Its neighbor in `library_scan.py` (manual "Scan Now") was correctly wrapped; the periodic auto-scanner's copy of the same logic was not, even though a code comment there explicitly says "same pattern as library.py:520-529" (now `library_scan.py`'s fixed code).
- **Evidence**:
  ```python
  # auralis-web/backend/core/stream_fingerprint.py:178 (inside async def check_or_queue_fingerprint)
  added = queue.enqueue(track_id)          # sync, on the loop
  ```
  ```python
  # auralis-web/backend/services/library_auto_scanner.py:346 (inside async def _do_scan)
  enqueued = sum(1 for t in scan_result.added_tracks if fp_queue.enqueue(t.id))   # sync, O(N), on the loop
  ```
  Compare with the fixed sibling in the same file family:
  ```python
  # auralis-web/backend/routers/library_scan.py:353-355 — the #4702 fix, offloading the identical loop shape
  def _enqueue_added() -> int:
      return sum(1 for t in result.added_tracks if fp_queue.enqueue(t.id))
  enqueued = await asyncio.to_thread(_enqueue_added)
  ```
  `FingerprintQueue.enqueue()` itself documents the invariant these two sites violate:
  ```python
  # auralis-web/backend/analysis/fingerprint_queue.py:83-86
  # enqueue() is intentionally called through asyncio.to_thread by
  # several routes so large batches do not monopolize the event loop.
  # A real thread lock must therefore guard its check-then-mutate state
  # together with the async worker's dequeue transition (#5261).
  ```
- **Impact**: `stream_fingerprint.py`'s site is low-impact per call (same in-memory-lock cost #4702 called sub-millisecond), but it sits directly in the enhanced-streaming hot path — every unfingerprinted track played with enhancement on hits it. `library_auto_scanner.py`'s site is the O(N) case #4702 flagged as the valuable one to fix: on an initial library import via the folder watcher (not the manual "Scan Now" path, which got the fix), a scan adding hundreds or thousands of tracks holds the event loop — stalling every concurrent WebSocket audio stream, heartbeat and chunk send — for the sum of N lock-acquiring `enqueue()` calls, right before the `scan_complete` broadcast.
- **Suggested Fix**: Wrap both remaining call sites in `asyncio.to_thread`, mirroring `library_scan.py`'s pattern exactly (single `to_thread` around the whole `sum(...)` comprehension for the auto-scanner; `await asyncio.to_thread(queue.enqueue, track_id)` for the streaming site). Consider a lint/grep check (as #4702 suggested) so a third sibling can't reappear silently.
- **Orchestrator note**: Rated LOW: `FingerprintQueue.enqueue()` is in-memory work under a `threading.Lock` (no DB or I/O; see `analysis/fingerprint_queue.py:90-120`), and #4702, the same pattern, was LOW. The auto-scanner loop is the only site where N can be large.

#### INT-F7-01: `player_state.create_track_info()` builds `artwork_url` without checking whether the album actually has artwork
- **Severity**: LOW
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Engine/Backend (`player_state.py`) → WebSocket `player_state`/queue TrackInfo
- **Location**: `auralis-web/backend/player_state.py:157-172` (`create_track_info`) → consumed by `auralis-web/backend/core/state_manager.py:112` and `auralis-web/backend/services/queue_enrichment.py:110-116` (`resolve_tracks`'s library-lookup fallback, `create_track_info_fn`)
- **Status**: NEW
- **Description**: `create_track_info()` computes `album_art_url` purely from whether an `album_id` can be found (`if album_id: album_art_url = f"/api/albums/{album_id}/artwork"`), with no check of `album.artwork_path`. This is the code path that feeds the canonical WebSocket `player_state` broadcast (current-track "now playing" state, via `state_manager.py:112`) and the queue-resolution fallback in `QueueEnricher.resolve_tracks()`. Meanwhile `Track.to_dict()` (`auralis/library/models/track.py:148-149`, used by the REST `/api/tracks` list/detail endpoints) and `Album.to_dict()` (`auralis/library/models/album.py:75-77`) both correctly gate the URL on `album.artwork_path` being set, returning `None` otherwise. Two backend code paths compute the same wire field (`artwork_url`) for the same entity with different null-safety.
- **Evidence**:
  ```python
  # auralis-web/backend/player_state.py:157-163 (create_track_info)
  album_art_url: str | None = None
  album_id = getattr(track, 'album_id', None)
  if not album_id and hasattr(track, 'album') and track.album and not isinstance(track.album, str) and hasattr(track.album, 'id'):
      album_id = track.album.id
  if album_id:
      album_art_url = f"/api/albums/{album_id}/artwork"
  ```
  ```python
  # auralis/library/models/track.py:147-149 (Track.to_dict, the REST path)
  album_artwork = None
  if album and album.artwork_path:
      album_artwork = f"/api/albums/{album.id}/artwork"
  ```
  `GET /api/albums/{id}/artwork` 404s whenever `album.artwork_path` is falsy (`routers/artwork.py:385-386`), so any track whose album has no artwork file gets a `player_state`/queue `artwork_url` that is guaranteed to 404 on fetch.
- **Impact**: Currently dormant in the UI — no live frontend surface renders the WS-sourced `artwork_url` today (see INT-F7-02), so the bad URLs are not fetched. It becomes a real, silent landmine the moment the player bar or `QueuePanel` are wired to show artwork (a natural next step given `TrackInfo.tsx` and `AlbumArt`-style components already exist for exactly this): every album without artwork would produce a failed-request/broken-image or an unnecessary 404 round-trip on every queue re-render, instead of the clean `null`→placeholder path REST consumers already get.
- **Suggested Fix**: Mirror `Track.to_dict()`'s guard in `create_track_info()` — only build the URL when `album.artwork_path` (not just `album_id`) is present; `getattr(track.album, 'artwork_path', None)` is already reachable at that call site.
- **Orchestrator note**: Rated LOW: no production frontend surface renders the WS/queue `artwork_url` today (see INT-F7-02), so the 404 URL is dormant.

#### INT-F7-05: Artwork metadata-search requests still auto-follow redirects — sibling gap of #5330
- **Severity**: LOW
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Backend `services/artwork_downloader.py` → external MusicBrainz/iTunes search APIs
- **Location**: `auralis-web/backend/services/artwork_downloader.py:233` (`_try_musicbrainz`, MusicBrainz release search) and `:302` (`_try_itunes`, iTunes search) vs. `:74-92` (`_get_trusted_artwork`, used only for the subsequent image-fetch requests)
- **Status**: NEW
- **Description**: #5330 (closed) fixed artwork *image* downloads to validate each redirect hop before requesting it, because `aiohttp`'s default `allow_redirects=True` would otherwise send a real request to an untrusted/internal host mid-chain. That fix (`_get_trusted_artwork`) is applied to the Cover Art Archive and iTunes *image* URLs (`:249-251`, `:323`), but the two metadata *search* calls that precede them — `session.get(search_url, params=params, headers=headers)` for MusicBrainz (`:233`) and `session.get(self.itunes_api, params=params)` for iTunes (`:302`) — still use the session's default redirect behavior with no hop validation, since they don't go through `_get_trusted_artwork` at all.
- **Evidence**:
  ```python
  # :233 — MusicBrainz search, no redirect validation
  async with session.get(search_url, params=params, headers=headers) as resp:
      ...
      data = await resp.json()
      release_id = releases[0]["id"]
  # :246-251 — only the FOLLOW-UP image fetch is hardened
  coverart_url = f"{self.coverart_api}/release/{release_id}/front"
  async with _get_trusted_artwork(session, coverart_url, "MusicBrainz", headers) as resp:
      ...
  ```
  ```python
  # :302 — iTunes search, same gap
  async with session.get(self.itunes_api, params=params) as resp:
      ...
  ```
- **Impact**: Narrow — a redirect would have to originate from `musicbrainz.org` or `itunes.apple.com` themselves (compromise or MITM), and the response is only JSON-parsed to extract an id used in a further request to an already-trusted, fixed host. But the blast radius matches the pattern #5330 was written to close: a single unvalidated backend-initiated GET to an attacker-directed URL (blind SSRF).
- **Suggested Fix**: Route the two search calls through `_get_trusted_artwork` (or a lighter variant that doesn't require a 200-body read) the same way the image fetches are, for consistency and to fully close the class of bug #5330 targeted.

#### INT-F9-05: The entire queue-history/undo feature is wired end-to-end on the backend but has zero frontend callers
- **Severity**: LOW
- **Flow**: Flow 9 (Queue & Playback State)
- **Boundary**: Frontend hook → REST endpoints (never invoked)
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueHistory.ts:1-341` → `auralis-web/backend/routers/player_queue_history.py:1-145` / `auralis/library/repositories/queue_history_repository.py`
- **Status**: NEW
- **Description**: `useQueueHistory()` is the sole frontend caller of all four queue-history endpoints (`GET/POST/DELETE /api/player/queue/history`, `POST /api/player/queue/undo`). It is exported from `hooks/player/index.ts`, but grepping the entire `src/components/` and `src/hooks/` trees (excluding the hook's own file, its test, and the barrel re-export) turns up **no component that calls `useQueueHistory()`**. In particular:
  - `recordOperation()` — the function that must be called *before* a mutation to snapshot pre-edit state — has no caller anywhere. None of `useQueueMutations.ts`'s `setQueue`/`addTrack`/`removeTrack`/`reorderTrack`/`reorderQueue`/`toggleShuffle`/`clearQueue` call it.
  - No component renders an "Undo" control. `QueueControlBar.tsx` (the live queue panel's control row) exposes Shuffle, Repeat (off/all/one), and Clear only — no Undo button.
  - Consequently `POST /api/player/queue/history` is never called in production, so `queue_history_repository`'s history table is never populated by real usage, `GET .../history` always returns an empty list, and `POST /api/player/queue/undo` can never do anything (`repo.undo()` returns `None` → 404) because nothing was ever recorded.
- **Evidence**:
  ```
  # Only file referencing the 3 wire paths in the whole frontend tree:
  $ grep -rn "queue/history\|queue/undo" auralis-web/frontend/src --include="*.ts" --include="*.tsx" | grep -v __tests__
  auralis-web/frontend/src/hooks/player/useQueueHistory.ts:192:  ...('/api/player/queue/history')
  auralis-web/frontend/src/hooks/player/useQueueHistory.ts:229:  '/api/player/queue/history'
  auralis-web/frontend/src/hooks/player/useQueueHistory.ts:277:  await post('/api/player/queue/undo', {})
  auralis-web/frontend/src/hooks/player/useQueueHistory.ts:305:  await apiDelete('/api/player/queue/history')

  # No component ever calls the hook:
  $ grep -rln "useQueueHistory" auralis-web/frontend/src --include="*.tsx" | grep -v __tests__
  (no results)

  # No Undo control in the live queue panel:
  $ grep -n "ndo" auralis-web/frontend/src/components/player/QueuePanel/*.tsx
  (no match for "Undo")
  ```
  Backend side is fully implemented and functional in isolation (`player_queue_history.py:46-144`, `queue_history_repository.py`'s singleton `QueueState` row + history table), confirming this is a wiring gap, not a missing/broken endpoint (that was #3805, closed).
- **Impact**: The queue-undo feature — a user-visible capability the backend was explicitly built for (#3805 "Phase 7A - Queue History & Undo/Redo") — does not exist from the user's perspective. No queue edit can ever be undone through the UI, regardless of how correct the backend implementation is. This has silently been the case since the backend endpoints were implemented (`f820ea9c`, closing #3805) — #3805 fixed the 404s but nothing was ever added to call `recordOperation` from a real mutation site or to render an Undo affordance. The persisted `QueueState`/history rows this subsystem maintains are consequently pure overhead with no observable effect.
- **Suggested Fix**: Either (a) wire `recordOperation` into each of `useQueueMutations.ts`'s mutation callbacks (capturing the pre-mutation snapshot before `runOptimistic`'s `apply()`) and add an Undo button to `QueueControlBar.tsx` bound to `useQueueHistory().undo`, or (b) if queue undo is no longer a wanted product feature, remove `useQueueHistory.ts`, the four backend endpoints, and `queue_history_repository.py`'s history table together, consistent with the project's "no dead code" / retire-in-place principle — a partial removal already happened once (`7dd14d11`, dropping the `redo()` stub) without finishing the job.
- **Orchestrator note**: Rated LOW: nothing visible breaks, because the UI never offered undo. This is a ship-or-delete product decision (wire an Undo control, or delete the hook, route and repository), like #4861.

---

## Relationships

- **INT-F5-01 and #5460.** Both involve the backend's playback state and the frontend's local session state drifting apart. Fixing INT-F5-01 by routing the library row through `usePlaybackControls().handlePlayPause` removes one of the two pause paths. The WebSocket `pause` handler then either needs a matching `resume` sender or should be retired.
- **INT-F4-01 and INT-F4-02.** Both belong to the #5467 folder-removal path. The dedicated endpoint prunes tracks but doesn't trigger a library refetch; the generic `PUT /api/settings` path doesn't prune at all. Fix them together: one helper that prunes and broadcasts `library_updated`, called from both endpoints and from the manual scan's prune-only case.
- **INT-F7-01 and INT-F7-02.** If player-bar artwork is added back (INT-F7-02), INT-F7-01's unchecked URL immediately becomes a visible broken image. Fix INT-F7-01 first, or together.
- **INT-F6-01 and #5381/#5390.** These share the similarity helper path. INT-F6-01 changes the error text the frontend classifies, so check `classifySimilarityError()` in the same change.
- **INT-F2-01 and #2263.** The same bug class #2263 fixed with `trackTransformer.ts`. The search hook should reuse that transformer rather than its own inline type.

## Prioritized Fix Order

1. **INT-F5-01**: an everyday UI action that interrupts playback partway through a track. Route the library row's pause through the shared session.
2. **INT-F4-01**: removed tracks stay visible in the library until a manual reload.
3. **INT-F2-01**: every global-search track result shows "undefined • Album".
4. **INT-F3-01**: a broken settings control for installs that still hold a pre-2026-09-13 preset (no data migration normalized those rows).
5. **INT-F6-01, INT-F2-03, INT-F7-03**: misleading or stuck UI states in less common situations.
6. **INT-F7-02** (a product decision: restore player-bar artwork or delete `TrackInfo.tsx`), **INT-F7-04**, **INT-F4-02**.
7. The LOW findings: dead-contract and dead-code cleanup (INT-F2-02, INT-F5-02, INT-F9-05) and consistency with earlier fixes (INT-F6-02, INT-F7-01, INT-F7-05).
