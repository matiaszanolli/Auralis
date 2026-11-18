# Integration Audit - 2026-11-17

Scope: all 9 critical flows (backend / frontend / engine boundaries), depth deep, no limit. Fresh trace of the current source (HEAD `7029fa50a`); no prior report was consulted. Dedup baseline: all 6,090 issues (highest #6346) fetched with `--state all`.

## Executive Summary

**37 findings after cross-flow dedup: 0 CRITICAL, 1 HIGH, 14 MEDIUM, 22 LOW.** (39 raw findings; F5-01 merged into F1-04 and F5-02 into F8-03, the same boundary issue seen from two flows.) Three are regressions of closed issues (#5925, #5866, #5931), plus a residual-fix gap against #6162; the rest are NEW. No audio-integrity defect (dropped or duplicated samples, sample-rate mismatch, chunk-seam gap) was found: the chunk tiling, frame pairing, epoch supersession and every regression guard listed in the flow definitions were re-verified in place.

Key themes:
1. **Flow-control and stream-session state machine on the client** (F1-01 HIGH, F1-02, F1-03, F8-01, F8-04): the one HIGH is a side effect of the bounded flow gate that fixed #5863 - after the server-side bound expires it resumes sending to a paused client whose PCM ring then overflows and drops frames silently. The 45 s start watchdog is shorter than the backend's 90 s processor-init window, and a trailing `errored` end after an auto-recovered stream error ends the recovered session.
2. **Client teardown never tells the server** (F1-04, F9-01): client-side stop / clear-queue / terminal error do not send WS `stop`, so the server keeps rendering and streaming, and after Clear Queue nothing in the UI can stop the audio.
3. **Engine queue vs `PlayerState` divergence** (F9-02 .. F9-06): the second queue-shape split (after #4374) leaves shuffle, repeat, current index and state stale after set/clear/remove.
4. **Stale frontend state after a backend-side change** (F2-01, F2-04, F5-04, F7-01, F7-02, F6-02): artwork URL dropped in the artist view, caches not revalidated after reconnect, retag orphaning artwork, library reset leaving the similarity fit.
5. **Search/filter parity between server and client** (F2-02, F2-03).
6. **Validation errors without `command`** (F8-03): `seek` rejections cannot be matched by the client's rollback.

Most impactful boundary mismatches: F1-01 (Backend flow gate -> Frontend PCM ring), F2-01 (backend `artwork_url` dropped by the artist-detail mapper), F8-01 (seek resume path leaves progress throttling armed), F9-01 (clear queue vs live stream).

## Flow Coverage Matrix

| Flow | Boundaries checked | Findings (after dedup) | Regression guards |
|------|-------------------|------------------------|-------------------|
| 1 Track Playback | Both sides of every boundary in the flow table, plus the per-flow checklist | 4 (0C / 1H / 2M / 1L); F1-01, F1-02, F1-03, F1-04 | all held |
| 2 Library Browsing | Both sides of every boundary in the flow table, plus the per-flow checklist | 6 (0C / 0H / 4M / 2L); F2-01, F2-02, F2-03, F2-04, F2-05, F2-06 | #5925 and #5866 regressed (F2-01, F2-02); others held |
| 3 Audio Enhancement | Both sides of every boundary in the flow table, plus the per-flow checklist | 3 (0C / 0H / 1M / 2L); F3-01, F3-02, F3-03 | all held |
| 4 Library Scanning | Both sides of every boundary in the flow table, plus the per-flow checklist | 3 (0C / 0H / 1M / 2L); F4-01, F4-02, F4-03 | all held |
| 5 WebSocket Lifecycle | Both sides of every boundary in the flow table, plus the per-flow checklist | 2 (0C / 0H / 0M / 2L); F5-03, F5-04 | all held |
| 6 Fingerprint & Similarity | Both sides of every boundary in the flow table, plus the per-flow checklist | 4 (0C / 0H / 1M / 3L); F6-01, F6-02, F6-03, F6-04 | #6162 incompletely covered (F6-01); others held |
| 7 Artwork | Both sides of every boundary in the flow table, plus the per-flow checklist | 4 (0C / 0H / 1M / 3L); F7-01, F7-02, F7-03, F7-04 | all held |
| 8 Seek & Rebuffer | Both sides of every boundary in the flow table, plus the per-flow checklist | 4 (0C / 0H / 1M / 3L); F8-01, F8-02, F8-03, F8-04 | #5931 regressed (F8-01); others held |
| 9 Queue & Playback State | Both sides of every boundary in the flow table, plus the per-flow checklist | 7 (0C / 0H / 3M / 4L); F9-01, F9-02, F9-03, F9-04, F9-05, F9-06, F9-07 | all held |

Per-flow verified-OK items are in Appendix A.

## Findings

### CRITICAL (0)

None.

### HIGH (1)

#### F1-01: Bounded flow gate lets a paused client's PCM ring overflow; overflow drops frames silently
- **Severity**: HIGH
- **Flow**: 1 (Track Playback) — flow control
- **Boundary**: Backend (`wait_for_stream_gates`) → Frontend (`PCMStreamBuffer.append`)
- **Location**: `auralis-web/backend/core/stream_gates.py:52-75` (and call sites `stream_enhanced_chunks.py:144`, `stream_normal_chunks.py:103`) → `auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts:238-272`, `auralis-web/frontend/src/hooks/enhancement/audioChunkIngest.ts:121-128`, `auralis-web/frontend/src/hooks/enhancement/flowDrainWatch.ts:36-47`, `auralis-web/frontend/src/hooks/enhancement/usePlaybackTransport.ts:90-94`
- **Status**: NEW (side effect of the #5863 fix; related closed: #5863, #5514)
- **Description**: The #5863 fix bounds the server's flow gate at `FLOW_GATE_TIMEOUT_S = 30` and, on timeout, resumes delivery without the client's `buffer_ready` (the gate event is never set, so every later chunk waits another 30 s and then sends anyway: one chunk per 30 s). The fix assumed the client's drain watch "re-syncs" the buffer state. That holds only while the client is consuming. A user pause is client-side only (`pausePlayback` calls `engine.pausePlayback()` and never sends a WS `pause`; #5514 removed that on purpose), and a paused engine stops feeding the worklet, so the ring never drains below the 50% resume mark and `flowDrainWatch` never sends `buffer_ready`. The client also does not re-send `buffer_full` (it is already latched: `fill > 75 && !paused` is false), so nothing tells the server to keep waiting. The server therefore keeps trickling one 10 s chunk per 30 s into a ring that is already at 75+%. When free space is exhausted, `PCMStreamBuffer.writeToBuffer` drops the new frames (`console.warn` only), while `ingestChunk` still increments `processedChunks`/progress. The drop can fall mid-chunk (the leading frames of a chunk fit, the tail is dropped, and a later smaller frame can still fit and be appended out of order). When the user resumes and the ring drains, `buffer_ready` is sent and the server delivers the chunks after the dropped ones, so the listener hears an unannounced forward skip of 10 s per dropped chunk. No error frame, no `audio_stream_error`, no stall flag.
- **Evidence**:
  - Server, `stream_gates.py:65-75`: `if flow_evt.is_set(): return` / `await asyncio.wait_for(flow_evt.wait(), timeout=FLOW_GATE_TIMEOUT_S)` / `except TimeoutError: logger.warning(...resuming delivery (#5863))` — returns with the event still clear; called once per chunk, so each chunk costs one 30 s wait.
  - Client latch, `audioChunkIngest.ts:125-126`: `if (fillPercentage > FLOW_PAUSE_FILL_PCT && !currentlyPaused) return 'pause'; if (fillPercentage < FLOW_RESUME_FILL_PCT && currentlyPaused) return 'resume';` — no re-assertion of pause while already latched.
  - Drain watch, `flowDrainWatch.ts:39-44`: only emits when `buffer.getFillPercentage() < FLOW_RESUME_FILL_PCT`; a paused engine does not read the ring.
  - Pause is local, `usePlaybackTransport.ts:90-94`: `pauseHoldRef.current = true; playbackEngineRef.current?.pausePlayback(); setIsPaused(true);` (no `wsContext.send`).
  - Overflow, `PCMStreamBuffer.ts:251-264`: `const freeSpace = bufferCapacity - currentlyUsed - 1; if (sampleCount > freeSpace) { console.warn(...Dropping...); return; }`.
  - Headroom above the pause mark is 25% of capacity (`capacityForStream`, `pcmRingOps.ts`: `min(100 MB, 1.5 x stream bytes)`). A track long enough to reach the 75% mark (backlog over about 223 s at 44.1 kHz stereo; any stream whose 1.5x size exceeds the 100 MB cap) has 74 s of headroom at 44.1 kHz stereo (about 3.7 min of pause), 34 s at 96 kHz stereo (about 2 min of pause) and about 11 s at 96 kHz 6-channel (under 1 min).
- **Impact**: Pause a long (or hi-res) track for longer than the headroom allows, resume, and part of the track is silently skipped. This is the "WebSocket chunk drops/gaps" class (HIGH in `_audit-severity.md`). Everything needed is realistic: flow pause is reached for long tracks in the first minute because delivery runs several times faster than real time, and pausing for a few minutes is ordinary use.
- **Suggested Fix**: Make the client authoritative for "do not send more": while `flowPausedRef` is true, either (a) re-send `buffer_full` on every chunk that arrives into a ring above the pause mark (so the server's gate is re-armed) and have the server treat a re-asserted `buffer_full` as resetting the 30 s bound, or (b) make the server's bound conditional (give up waiting only if the connection has been silent, and send at most one chunk per timeout while the client has not said `buffer_ready`) and make the client refuse (not silently drop) a frame that will not fit, by emitting `audio_stream_error`/re-requesting from the last accepted sample. Minimum viable: have `PCMStreamBuffer.append` return a rejected flag that `ingestChunk` turns into a stream error instead of counting it as ingested.

### MEDIUM (14)

#### F1-02: Frontend stream-start watchdog (45 s) is shorter than the backend's 90 s processor-init window
- **Severity**: MEDIUM
- **Flow**: 1 (Track Playback) — timeouts
- **Boundary**: Backend (`run_enhanced_stream`, processor init before `audio_stream_start`) → Frontend (`useStreamStartWatchdog`)
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:126` and `auralis-web/backend/core/stream_enhanced_lifecycle.py:110-129` → `auralis-web/frontend/src/services/audio/audioConstants.ts:57-71`, `auralis-web/frontend/src/hooks/enhancement/useStreamStartWatchdog.ts:60-68`
- **Status**: NEW (related closed: #6336, #4433, #6232; the guard for #6232 holds but its mirror is now incomplete)
- **Description**: `audio_stream_start` is sent only after `ChunkedAudioProcessor` is constructed, and construction now runs the whole-track fingerprint analysis for an unfingerprinted track (`init_fingerprint_and_processor(..., extract_if_missing=True)`, `chunk_processor_init.py:148-161`). #6336 gave that step its own `PROCESSOR_INIT_TIMEOUT = 90.0` (analysis can wait behind a busy analysis gate). The frontend mirror `BACKEND_STREAM_TIMING` was not updated: the watchdog is `(30 chunk + 5 semaphore + 10 interval) s = 45 s` and is cleared only by `audio_stream_start` / `audio_chunk` / `audio_stream_end` / `audio_stream_error`. The backend sends nothing before `audio_stream_start` (it is the first control frame; the first `fingerprint_progress` also comes after init), so any init between 45 s and 90 s hits the watchdog first. The watchdog's own comment ("the backend's `audio_stream_error` surfaces first") no longer holds.
- **Evidence**:
  - Backend: `stream.processor = await asyncio.wait_for(asyncio.to_thread(controller.chunked_processor_class, ...), timeout=_asc.PROCESSOR_INIT_TIMEOUT)` (`stream_enhanced_lifecycle.py:111-121`), `PROCESSOR_INIT_TIMEOUT: float = 90.0  # init also runs a missing whole-track analysis (#6336)`.
  - Frontend: `chunkProcessTimeoutSeconds: 30, streamSemaphoreWaitSeconds: 5, chunkIntervalSeconds: 10` -> `STREAM_START_WATCHDOG_DERIVED_MS = 45000`; the timer body is `endActiveStream(); onTimeoutRef.current();` (`useStreamStartWatchdog.ts:62-66`), and `onTimeout` dispatches `setStreamingError('Timed out waiting for the audio stream to start. Please try again.')` and runs `cleanupStreaming()` (`streamingCoreLifecycle.ts:56-67`).
- **Impact**: For a long, unfingerprinted track while the fingerprint queue is busy (the exact #6336 scenario), the user sees a "timed out, please try again" error at 45 s and the session is marked ended (`streamActive = false`, so reconnect/toggle will not re-issue it). The backend is still working and later sends `audio_stream_start`, which the (cleaned-up) client accepts and plays, so the error is spurious. If the user does "try again", the new `play_enhanced` cancels the in-flight init (the cancel event is set), the analysis starts over, and it can time out the same way each attempt.
- **Suggested Fix**: Add `processorInitTimeoutSeconds: 90` to `BACKEND_STREAM_TIMING` and derive the watchdog as `processorInit + semaphoreWait + chunkProcess + interval` (or: have the backend send an early keep-alive control frame such as `audio_stream_pending` that the client treats as proof of life and that re-arms the watchdog). Keep the mirror and `audio_stream_controller.py` in the same commit, as `audioConstants.ts` already instructs.

#### F1-03: A trailing `audio_stream_end{reason:"errored"}` after an auto-recovered stream error ends the recovered stream's session
- **Severity**: MEDIUM
- **Flow**: 1 (Track Playback) — failure paths
- **Boundary**: Backend (`pump_chunks` / `pump_normal_chunks` error + end frames) → Frontend (`handleStreamError` / `handleStreamEnd` / `connState.streamActive`)
- **Location**: `auralis-web/backend/core/stream_enhanced_chunks.py:221-257` (and `stream_normal_chunks.py:180-218`) → `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:111-137,142-191`, `auralis-web/frontend/src/hooks/enhancement/useStreamSubscriptions.ts:127-136`, `auralis-web/frontend/src/hooks/enhancement/streamingCoreLifecycle.ts:81`, `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:87-121`
- **Status**: NEW (related closed: #4655, #5867, #5876, #6017, #5995)
- **Description**: On a per-chunk DSP timeout (and on the normal path's two consecutive read timeouts) the backend sends a terminal `audio_stream_error` carrying `recovery_position` and no `continues`, records the chunk in `failed_chunks`, and then `send_stream_completion` sends `audio_stream_end{reason:"errored"}` for the same stream. The client's error handler runs `cleanupStreaming()` (which nulls `bufferEpochRef`/`streamEpochRef`) and auto-resumes through `wsContext.reissueActiveStreamAs(...)`. The trailing end frame then arrives before the reissued `audio_stream_start` (same socket, and the old task finishes before the new one starts). It passes both guards: the epoch guard `isSupersededEpoch` is bypassed because `bufferEpochRef.current` is now `null`, and the track guard `isSupersededTrack` passes because it is the same track and `setStreamingError` kept `trackId`. `handleStreamEnd` then treats it as the live stream finishing with gaps: it calls `endActiveStream(trackId)` (setting `connState.streamActive = false`) and dispatches "Playback ended with gaps". `reissueActiveStreamAs` writes straight to `wsManagerRef.current.send` and does not set `streamActive`, and nothing sets it again when the recovered `audio_stream_start` arrives (only `send()` of a `play_*`/`seek` and the reconnect replay do).
- **Evidence**:
  - Backend: `except TimeoutError: ... send_error(..., recovery_position=...)` then `failed_chunks.append(chunk_idx); break` (`stream_enhanced_chunks.py:221-257`); `send_stream_completion` -> `stopped_early or failed_chunks` -> `reason = "errored"` (`stream_lifecycle.py:207-230`).
  - Client cleanup before reissue: `bufferEpochRef.current = null` (`streamingCoreLifecycle.ts:81`) then `wsContext.reissueActiveStreamAs(reissueType, {}, recoveryPosition)` (`useStreamMessageHandlers.ts:181`).
  - Epoch guard that does not fire: `const current = bufferEpochRef.current; return frameEpoch != null && current != null && frameEpoch !== current;` (`useStreamSubscriptions.ts:69-72`).
  - The end handler: `if (reason === 'completed' || reason === 'errored') { ...; endActiveStream(trackId); }` (`useStreamMessageHandlers.ts:111-120`), `endActiveStream` sets `connState.streamActive = false` when `lastStreamCommand.data.track_id === trackId` (`websocketConnectionState.ts:158-162`).
  - Reissue path never re-arms it: `connState.lastStreamCommand = next; wsManagerRef.current.send(JSON.stringify(next));` (`useOutgoingChannel.ts:112-113`).
  - No test pins the error -> end(errored) -> reissue sequence (`useAudioStreamingCore.sessionEnd.5876.test.tsx` and `usePlayEnhanced.test.ts` cover each message alone).
- **Impact**: After a recovered DSP/read timeout the audio resumes, but the session is invisible to the two consumers of `streamActive`: a WebSocket reconnect no longer re-issues the stream (playback dies when the buffered tail runs out), and an enhancement enabled/preset/intensity change mid-playback returns `false` from `reissueActiveStreamAs` so the live setting change is not applied. The UI also flashes a stale "Playback ended with gaps" error until the recovered `audio_stream_start` resets it.
- **Suggested Fix**: Frontend: when the error handler starts a recovery, remember the failed stream's epoch (`recoveringEpochRef`) and drop any `audio_stream_end`/`audio_stream_error` carrying that epoch (or keep `bufferEpochRef` across the recovery cleanup so the superseded-epoch guard sees the new start), and have `reissueActiveStreamAs` set `connState.streamActive = true` when it sends. Alternatively backend: do not follow a terminal `audio_stream_error` that offers a `recovery_position` with an `audio_stream_end`.

#### F2-01: Artist detail drops `AlbumInArtist.artwork_url`, so every artist-page album card renders the placeholder (#5925 fix never reaches the UI)
- **Severity**: MEDIUM
- **Flow**: 2 (Library Browsing) — artist detail
- **Boundary**: Backend `GET /api/artists/{id}` → frontend `useArtistDetailsData` → `AlbumsTab`
- **Location**: `auralis-web/backend/routers/artists.py:154-161` / `artists_models.py` (`AlbumInArtist.artwork_url`) → `auralis-web/frontend/src/components/library/Details/useArtistDetailsData.ts:79-85` → `auralis-web/frontend/src/components/library/Views/AlbumsTab.tsx:105`
- **Status**: Regression of #5925 (closed; fix is incomplete end to end)
- **Description**: #5925 made the backend send `artwork_url` on each nested album and changed `AlbumsTab` to pass `hasArtwork={Boolean(album.artwork_url)}`. `useArtistDetailsData` rebuilds each album as an explicit literal (`id,title,year,track_count,total_duration`) and discards `artwork_url`. `ArtistDetailTabs` passes that array to `AlbumsTab`, so `album.artwork_url` is always `undefined` and `hasArtwork` is always `false`.
- **Evidence**:
  - Backend: `AlbumInArtist(... artwork_url=album_data.get('artwork_url'))` (artists.py:154-161) — emitted, `/api/albums/{id}/artwork` or null.
  - Frontend hook: `albums: (data.albums || []).map((a) => ({ id: a.id, title: a.title, year: a.year ?? undefined, track_count: a.track_count, total_duration: a.total_duration ?? 0 }))` — no `artwork_url`; local `Album` interface in the same file has no such field either.
  - `AlbumsTab.tsx:105`: `hasArtwork={Boolean(album.artwork_url)}`; `AlbumCard.tsx:74` only builds a thumbnail URL when `hasArtwork || artworkRevision > 0`.
  - `AlbumsTab.artwork.5925.test.tsx` feeds `artwork_url` directly to `AlbumsTab`, bypassing the hook, so it stays green.
  - Before #5925 the cards always requested artwork (404 noise); now they never do, which is worse for albums that do have art.
- **Impact**: Artist page album grid shows no cover art for any album (only placeholder/fingerprint gradient) unless an `artwork_updated` WS event bumps the revision.
- **Suggested Fix**: Add `artwork_url?: string | null` to the hook's `Album` type and map `artwork_url: a.artwork_url ?? undefined` (or spread the wire album). Add a hook-level test (`useArtistDetailsData` → `AlbumsTab`) asserting an album with art gets `hasArtwork`.

#### F2-02: `GET /api/library/tracks/favorites` ignores `search`, so favourites-view search is client-side over loaded pages only (partial regression of #5866)
- **Severity**: MEDIUM
- **Flow**: 2 (Library Browsing) — favourites view search
- **Boundary**: Frontend `tracksEndpoint()` → Backend `get_favorite_tracks`
- **Location**: `auralis-web/frontend/src/hooks/library/libraryPageFetch.ts:36-45` → `auralis-web/backend/routers/tracks.py:85-93` (and `TrackRepositorySearchMixin.get_favorites`, track_repository_search.py:136)
- **Status**: Regression of #5866 (closed HIGH; the favourites half was never wired)
- **Description**: For `view === 'favourites'` the frontend sends `?limit&offset&search=…` to `/api/library/tracks/favorites`. That handler declares only `limit` and `offset`; FastAPI silently drops the unknown `search`, and `get_favorites()` has no search capability (always `ORDER BY title`). The server therefore returns the unfiltered favourites. The only filtering left is the `filteredTracks` overlay in `CozyLibraryView.tsx:108-117`, which sees only already-loaded pages — exactly the false-"no results" behaviour #5866 fixed for the main track list.
- **Evidence**:
  - `libraryPageFetch.ts:40-45`: `if (search.trim()) params.set('search', …)`; path switches to `ENDPOINTS.LIBRARY_TRACKS_FAVORITES`. The test `libraryPageFetch.search.test.ts:29-31` asserts the URL carries `search` to the favorites route, but nothing checks the server honours it.
  - `tracks.py:85-93`: `get_favorite_tracks(limit, offset, repos)` — no `search`.
  - `CozyLibraryView.tsx:265`: when `filteredTracks.length === 0 && !loading` it renders `LibraryEmptyContent` instead of `TrackListView`, so the infinite-scroll/virtualizer trigger is unmounted and the user cannot page in the remaining favourites.
- **Impact**: With more than one page (50) of favourites, searching for a favourite not in the loaded pages shows "no results"; `SearchResultsAnnouncement` announces zero results to screen readers. `total` shown is the unfiltered favourites count.
- **Suggested Fix**: Add `search` (and ideally `order_by`/`order`) to `get_favorite_tracks` and a `favorites_only` filter to `TrackRepository.search()` (reuse the same `contains_text` filter + `favorite == True`), or have the frontend not send `search` and document the limitation. Add a backend test pinning that `?search=` narrows the favourites total.

#### F2-03: Client-side search overlay hides rows the server legitimately matched (any non-first artist, casefold vs toLowerCase)
- **Severity**: MEDIUM
- **Flow**: 2 (Library Browsing) — tracks search
- **Boundary**: Backend `TrackRepository.search` (title / any artist / album, `casefold`) → frontend `CozyLibraryView.filteredTracks`
- **Location**: `auralis/library/repositories/track_repository_search.py:42-52` + `text_search.py:contains_text` → `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:107-117` (artist reduced to `artists[0]` in `api/transformers/trackTransformer.ts:22`)
- **Status**: NEW
- **Description**: The page returned by `/api/library/tracks?search=` is matched against `Track.title`, **every** `Artist.name` joined to the track, and `Album.title`, using Python `str.casefold()`. The view then filters those same rows again client-side with `track.title/artist/album.toLowerCase().includes(searchQuery.toLowerCase())`, where `track.artist` is only the first entry of `artists[]`. A track matched by a secondary artist (e.g. `["Alice","Bob"]`, search "bob"), or by a casefold-only equivalence (`ß`/`SS`, search "strasse" for "Straße"), is returned by the server but dropped by the overlay. The un-debounced `searchQuery` also filters the previous debounced result set during the 250 ms debounce window.
- **Evidence**:
  - Server: `search_filter = or_(contains_text(Track.title,q), contains_text(Artist.name,q), contains_text(Album.title,q))` over `join(Track.artists, isouter=True)` (any artist).
  - Client: `track.artist.toLowerCase().includes(...)`; `trackTransformer.ts:22` `const artist = apiTrack.artists?.[0] ?? ''`.
  - #5866's commit message states the client filter "stays as the instant-feedback overlay", but its semantics are narrower than the server's.
- **Impact**: Visible result count is smaller than `totalTracks` (and than the server's count); collaborations/feature tracks do not appear when searched by the featured artist, and an all-filtered page shows the empty state (which also unmounts the infinite-scroll trigger).
- **Suggested Fix**: Drop the overlay once the debounced server query equals `searchQuery` (apply it only while `searchQuery !== debouncedSearch`), or have the overlay match against all `artists`. Prefer trusting the server result.

#### F2-04: `useLibraryQuery.refresh()` supersedes an in-flight `executeQuery` without clearing its flags — `isLoading`/`isFetchingRef` stick, `fetchMore` and same-key `refetch` are dead
- **Severity**: MEDIUM
- **Flow**: 2 (Library Browsing) — artist list refresh on library change
- **Boundary**: WebSocket `library_updated`/`metadata_*` frame → `CozyArtistList.refresh()` → `useLibraryQueryFetchers` (shared request guard)
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQueryFetchers.ts:190-203` (refresh), `:77-130` (executeQuery finally), `:136` (fetchMore guard); caller `components/library/Items/artists/CozyArtistList.tsx:68-70`
- **Status**: NEW (introduced with the #5871 in-place refresh; the guard test `useLibraryQuery.test.ts:698+` does not cover an in-flight query)
- **Description**: `executeQuery` sets `isFetchingRef = true` and `setIsLoading(true)` and only resets them in `finally` when `!isStale()`. `refresh()` calls `beginRequest()` (bumping the shared request id) and `claimRequest()` (aborting executeQuery's HTTP call) but never touches `isFetchingRef` or `setIsLoading`. If `refresh()` runs while an `executeQuery` is in flight, that query ends as `aborted`/`stale`, its `finally` skips the reset, and refresh itself never clears it. `refresh()` only takes the `executeQuery` path when `data` is empty; on a search change the old rows stay in `data` (the effect calls `executeQuery(0,false)` without clearing), so `dataLengthRef.current > 0` and the in-place path is taken.
- **Evidence**: Sequence: user edits the artist search → effect fires `executeQuery(0,false)` (`isFetchingRef=true`, `isLoading=true`, old rows kept) → a `library_updated` / `metadata_updated` frame arrives → `refreshArtists()` → `refresh()` → `beginRequest()` + `claimRequest()` abort the query; `fetchLoadedPages` succeeds with the new `endpointOptions` and sets data/offset/total/hasMore but not `isLoading` → `executeQuery`'s `finally` already skipped (`isStale()` true). Result: `isFetchingRef` stays true, `isLoading` stays true. Then `fetchMore` returns at line 136 (`isFetchingRef.current`), and `refetch()`/Retry for the same URL returns at line 81 (`queryKeyRef === queryKey && isFetchingRef`). If the new search has zero results, `isLoading && artists.length === 0` keeps `ArtistListLoading` up forever (CozyArtistList.tsx:97). The sibling track hook avoids this by emptying `tracks` on reset and delegating (`useLibraryPagination.refreshTracks` → `fetchTracks(true)` when `loaded === 0`).
- **Impact**: Artist list stuck on a skeleton, or infinite scroll permanently stalled with `hasMore` true, until the search text changes. Window is the artists-search request duration coinciding with a scan-complete/metadata-edit frame.
- **Suggested Fix**: In `refresh()` (and any path that calls `beginRequest()` without owning the flags), clear `isFetchingRef.current` and `setIsLoading(false)` after a `refreshed` result, or make `executeQuery`'s `finally` reset the flags when it was superseded by a non-`executeQuery` request. Alternatively have `refresh()` delegate to `executeQuery` whenever one is in flight. Add a hook test: start `executeQuery`, call `refresh()` before it resolves, assert `isLoading` false and `fetchMore` works.

#### F3-01: A seek after the stream finished delivering renders with the pre-change preset/intensity; Settings saves are only applied to a still-live stream
- **Severity**: MEDIUM
- **Flow**: 3 (Audio Enhancement) / 8 (Seek)
- **Boundary**: Backend (`PUT /api/settings` -> runtime dict -> `enhancement_settings_changed`) -> Frontend (re-issue gate) -> Backend (`handle_seek` snapshot precedence)
- **Location**: `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:97-101` (`reissueActiveStreamAs` returns false when `!connState.streamActive`) and `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:129-137` (`endActiveStream` on `completed`) -> `auralis-web/backend/ws_handlers/seek_command.py:68-73` (`resolve_enhancement_params(data, stream_settings, global_settings)`)
- **Status**: NEW (related to open #5076, which is about `play_normal` not recording or clearing the snapshot; this is a different trigger on the same snapshot). It is a residual hole in the #5874 fix, which is closed.
- **Description**: #5874 made a Settings-dialog intensity/preset save reach later seeks by re-issuing the playing stream as `play_enhanced`, which refreshes the per-connection `state.active_stream_settings` snapshot. The seek frame deliberately omits preset/intensity (#5604), so the backend resolves them from that snapshot first and from the live global dict only if the snapshot lacks a valid value. The re-issue is skipped once the stream is no longer "active" on the client. `audio_stream_end{reason:'completed'}` calls `endActiveStream`, and that arrives early in a normal session because the server renders ahead of the playhead and the PCM buffer is sized for the whole track. After that, a Settings save updates the global dict and the client state, but nothing updates the connection snapshot, which a finished stream never clears. A later seek (the client always sends a WS `seek`, resetting its buffer) therefore re-renders from the seek point with the old preset/intensity, while `enabled` is correctly read live (#5075).
- **Evidence**:
  - Sender: `useOutgoingChannel.ts:100-101`:
    ```ts
    const last = connState.lastStreamCommand;
    if (!last || !connState.streamActive) return false;
    ```
    `useEnhancementControl.ts:144-154` (`handleExternalChange`) calls `reissueRef.current('play_enhanced', { preset, intensity })` and ignores the `false` return.
  - Receiver: `seek_command.py:68-73`:
    ```py
    stream_settings = state.active_stream_settings.get(ws_id)
    global_settings = deps.get_enhancement_settings() ...
    preset, intensity = resolve_enhancement_params(data, stream_settings, global_settings)
    ```
    `resolve_enhancement_params` (`enhancement_params.py:83-97`) stops consulting fallbacks once preset and intensity are both resolved, and the snapshot always carries both keys, so the new global values are never read.
  - Snapshot lifetime: `active_stream_settings` is written only at `playback_commands.py:151` and cleared only by `detach_stream(clear_settings=True)` (stop/disconnect). A stream finishing does not clear it.
  - The Settings dialog is the only intensity/preset control in the UI, since nothing calls `setIntensity`/`setPreset`. The affected path is therefore the main one.
- **Impact**: The user lowers the intensity in Settings after the track has finished streaming, then scrubs. The seeked audio is still mastered at the old intensity until the next `play_enhanced`, which is the exact symptom #5874 fixed for a live stream. The behaviour is inconsistent: `enabled` takes effect on seek, preset/intensity do not. The buffered tail also keeps the old mode, which the code documents as accepted. Workaround: restart the track.
- **Suggested Fix**: Backend: have `_sync_enhancement_settings` (and the toggle/preset/intensity routes) write the new preset/intensity into every connection's `active_stream_settings` entry, or have `handle_seek` prefer the live global dict for connections that are not mid-stream. Alternatively, frontend: send the live `preset`/`intensity` from `useEnhancementControl` state on `seek`. That state is kept current by the broadcast, unlike the play-time snapshot #5604 removed.

#### F4-01: Auto-scanner's `library_updated` condition omits `files_updated`; manual path includes it
- **Severity**: MEDIUM
- **Flow**: 4 (Library Scanning) - Progress/UI update
- **Boundary**: Backend (auto-scanner) -> Frontend (library views via `library_updated`)
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:244` -> `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts` (`useWebSocketMessages(['library_updated'], handleLibraryUpdated)`)
- **Status**: NEW (related closed: #5912 unified the progress bridge / `scan_complete_payload` but not the terminal `library_updated` decision; #5515 added the `removed` term to both paths)
- **Description**: The two scan emitters each carry their own copy of "scan_complete, then library_updated if anything changed". The manual route's copy (`broadcast_scan_complete`) refreshes the UI when `files_added or files_updated or removed`. The auto-scanner's inline copy only tests `files_added or removed`. A background rescan that only UPDATES rows (a retagged/replaced file detected via `check_modifications=True`, or a moved/renamed file relocated by `relocate_missing_track`, #5880, which the batch processor reports as `'updated'`) therefore emits `scan_complete` but never `library_updated`, so open Library/Albums/Artists views keep showing the pre-scan metadata until the user reloads. The auto-scanner is exactly the path that notices out-of-app file edits (watchdog and hourly poll), so the case is realistic.
- **Evidence**:
  - Manual: `auralis-web/backend/routers/library_scan_events.py:59`: `if result.files_added or result.files_updated or removed:` then broadcast `library_updated {"action": "scan", "track_count": result.files_added}`.
  - Auto: `auralis-web/backend/services/library_auto_scanner.py:222,244`: `files_added = scan_result.files_added ...` / `if files_added or removed:`; `files_updated` is never read in `_do_scan`.
  - Frontend refresh trigger: `useLibraryWithStats.ts` refreshes tracks and stats only on `library_updated` (the scan card consumes `scan_complete` but does not refresh lists).
  - Pinned test `tests/backend/test_prune_refreshes_library_5515.py` only covers the manual router for the updated/removed combinations.
- **Impact**: Stale library metadata after a background (auto/watchdog) scan that changed rows without adding any. Workaround: reload or trigger a manual scan.
- **Suggested Fix**: Delete the auto-scanner's inline `scan_complete` + `library_updated` block and call one shared helper. Move `broadcast_scan_complete` from `routers/library_scan_events.py` into `services/scan_events.py` (it already owns `scan_complete_payload`) and use it from both emitters, passing `suppress_errors` as the auto path needs. That removes the drift class instead of patching one condition. Add an auto-scanner test mirroring the 5515 cases for an update-only scan.

#### F6-02: Library reset leaves the in-process similarity system fitted on the deleted library's statistics
- **Severity**: MEDIUM
- **Flow**: 6 (Fingerprint & Similarity)
- **Boundary**: Backend library-reset route -> engine `FingerprintSimilarity` / `FingerprintNormalizer` -> Backend similarity routes -> Frontend modal
- **Location**: `auralis-web/backend/routers/library.py:100-168` (reset: stops/starts workers, `repos.reset_library`, `clear_all_caches`; nothing touches `similarity_system`) -> `auralis/analysis/fingerprint/similarity.py:93-152` (`needs_refit`, `fit`) and `auralis-web/backend/services/similarity_autofit_worker.py:101-119`
- **Status**: NEW
- **Description**: `FingerprintSimilarity.fitted`, the normalizer's percentile ranges (`normalizer.stats`) and `reference_distance` live in memory. Library reset deletes every track and fingerprint but never resets that object. On the restart of `similarity_autofit` the first `fit()` returns immediately: `self.fitted and not self.needs_refit()`, and `needs_refit()` is `current_count >= fitted_from * 1.5` with `current_count == 0` right after a reset. Later it only refits once the new library is 1.5x larger than the OLD fitted sample. The startup comment (`config/startup/fingerprint.py:139-143`) says a reset leaves the system unfitted behind a 503; the code does not do that.
- **Evidence**: `similarity.py:134` (`if self.fitted and not self.needs_refit(): return True`), `similarity.py:104-107`; `library.py:144-165` contains no similarity/normalizer reset; `grep "fitted = False"` in `auralis/analysis/fingerprint/` only hits `__init__` of the two classes.
- **Impact**: After reset + rescan of a different or smaller library (old 10 000 tracks, new 300), similarity ranks and the "match %" use min/max ranges and a calibration distance of the previous library until the new one exceeds 1.5x the old sample or the backend restarts. A very different library (e.g. loud rock -> quiet classical) clamps most dimensions to 0/1, flattening rankings and scores. `/similar` also does not return the "initialising" 503 while the new library has fewer than `min_samples` fingerprints. Workaround: restart the backend.
- **Suggested Fix**: On reset (after `clear_all_caches`), mark the similarity system unfitted (e.g. a `reset()` that clears `fitted`, `normalizer.stats`, `reference_distance`) and drop `graph_builder`, so the auto-fit worker restarts from a clean fit; or make `needs_refit()` also trigger when the current count falls far below the fitted sample.

#### F7-01: A retag moves the track to a new, artwork-less album and the old album's artwork file is deleted, so the album silently loses its cover
- **Severity**: MEDIUM
- **Flow**: 7 (Artwork) - crosses into Flow 4 (Library Scanning)
- **Boundary**: Engine (scanner / TrackRepository update path) -> Engine (artwork store) -> Backend GET `/api/albums/{id}/artwork` -> Frontend (hasArtwork false, gradient placeholder)
- **Location**: `auralis/library/repositories/track_repository_mutation.py:85-145` (`update_by_filepath` -> `_assign_album`, `_prune_after_relation_change`) -> `auralis/library/repositories/orphan_pruning.py:51-85` (unlinks the pruned album's artwork file) vs. `auralis/library/repositories/track_repository_lifecycle.py:231-243` (the ONLY scan-time artwork extraction, in `add()`)
- **Status**: NEW (adjacent to closed #6331 / #5457 / #5880; none covers artwork on the update path)
- **Description**: Artwork is extracted from the file/folder only in `TrackRepository.add()`, and only when the album row has no `artwork_path`. `update_by_filepath()` (called by the scanner with `replace_tags=True` for any modified file, and for moved files via `relocate_missing_track`) re-resolves the album through `_get_or_create_album`. If the album tag changed, that creates a brand-new album row with `artwork_path = NULL` and never calls the extractor. Since #6331 the same transaction then runs `prune_orphans`, which deletes the old, now childless album row AND unlinks its artwork file (after commit). Net effect for an album retag: the cover that was extracted from the (still present) embedded tag / folder.jpg is thrown away and nothing regenerates it. Later rescans skip the file (mtime/size unchanged) so nothing heals it, and the frontend has no UI for `POST /artwork/extract` (artworkService.ts: "no extract/download/delete wrappers", #5214).
- **Evidence** (reproduced against the live code with a temp DB; one WAV + `folder.jpg`):
  ```
  after add: album 1 Old Album  .../artwork/album_1_9c4e8288.jpg
  db.tracks.update_by_filepath(path, dict(info, album="New Album"), replace_tags=True)
  album 2 New Album None
  old file exists: False
  ```
  Sender side: `track_repository_mutation.py:73` `track.album = self._get_or_create_album(...)` (no artwork step); `orphan_pruning.py:67-69,79-81` returns `Album.artwork_path` of deleted rows and queues them for unlink. Receiver side: `Album.to_dict()` (`models/album.py:93`) yields `artwork_url=None` -> `AlbumCard hasArtwork=false` -> placeholder; `GET /artwork` -> 404 "Artwork".
- **Impact**: Any user who fixes an album title/artist tag in a file (or the whole album) and rescans loses that album's cover art permanently until they hit the extract endpoint by hand. Before #6331 the old album lingered with its art, so this is a behaviour change introduced alongside the orphan sweep. The same missing self-heal applies to an album whose `artwork_path` points at a file that has since vanished (never re-extracted because `not album.artwork_path` is false). Minor side effect: the pruned album's derived thumbnails in `artwork/thumbnails/` are not purged (`prune_orphans` is engine-side and cannot reach `core.thumbnail_cache`); they are only reclaimed by the 128 MiB FIFO cap.
- **Suggested Fix**: Factor the extraction block in `add()` into one helper (e.g. `_ensure_album_artwork(session, album, filepath)`) and call it from `update_by_filepath()` / `update()` after `_assign_album`, whenever the resolved album has no `artwork_path` or its file is missing. Optionally also treat "artwork file missing on disk" as "no artwork" in that helper.

#### F8-01: Redux streaming progress is throttled out after a seek - "Buffering..." spinner, 0% buffered bar and a dead stall indicator for the whole seek stream
- **Severity**: MEDIUM
- **Flow**: 8 (Seek & Rebuffer)
- **Boundary**: Backend (`audio_stream_start` is_seek) -> Frontend (streaming core ref state vs Redux `player.streaming.enhanced`)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:104-148` (resume fast path, returns at :147 without resetting `lastDispatchedProgressRef`; the only reset is :243 on the rebuild path) -> `auralis-web/frontend/src/hooks/enhancement/useStreamChunkHandler.ts:111-128` + `auralis-web/frontend/src/hooks/enhancement/audioChunkIngest.ts:137-148` (`shouldDispatchProgress`)
- **Status**: Regression of #5931 (the fix there only seeded `metadata.processedChunks`; the buffered range after a seek is still wrong because the Redux write is suppressed). Related: #2535 (introduced the throttle).
- **Description**: A seek always takes the "resume into existing buffer" branch of `handleStreamStart` (`isSeek` true, engine and buffer exist). That branch dispatches `startStreaming(...)`, whose reducer sets `state='buffering'`, `processedChunks=0`, `progress=0`, `bufferedSamples=0`. The only thing that moves the state to `'streaming'` and updates `processedChunks`/`progress` is `updateStreamingProgress`, dispatched from `useStreamChunkHandler` and gated by `shouldDispatchProgress(clamped, lastDispatchedProgressRef.current, throttle=true)`. That gate passes only for the first chunk of a stream (`last < 0`), at 100%, or when the 10% decile rises above the *previous stream's* last dispatched value. `lastDispatchedProgressRef` is reset to -1 only in the stream-rebuild path (line 243); neither `sendSeek` (useEnhancedSeek.ts:78-112) nor the seek fast path resets it. So the ref still holds the value from before the seek.
- **Evidence**:
  - Sender/state: `useEnhancedStreamStart.ts:137-147` sets `streamingMetadataRef.processedChunks = startChunkOffset(start_chunk)`, dispatches `startStreaming(...)`, then `return`s. Line 243 (`core.lastDispatchedProgressRef.current = -1; // Reset progress throttle (fixes #2535)`) is after that return.
  - `playerStreamingReducers.ts:84-87`: `s.state = 'buffering'; ... s.processedChunks = 0; s.progress = 0`; `:152`: `if (s.state === 'buffering' && bufferedSamples > 0) s.state = 'streaming'` (only reachable through `updateStreamingProgress`).
  - `audioChunkIngest.ts:137-148`: `if (lastDispatchedProgress < 0) return true; if (clampedProgress >= 100) return true; return floor(clamped/10) > floor(max(0,last)/10);` and `useStreamChunkHandler.ts:118` stores `lastDispatchedProgressRef.current = clampedProgress` only when it dispatches.
  - Consumers: `Player.tsx:81` `isBuffering = streamingState === 'buffering'` (shows "Buffering..." + spinner in `BufferingIndicator`), `Player.tsx:88` `isStalled = streamingState === 'streaming' && playbackStalled`, `Player.tsx:~146` buffered bar = `processedChunks / totalChunks` from Redux.
  - Example: a 20-chunk track has played/buffered to chunk 14 (last dispatched 70-75). User seeks to chunk 6 (30%). The seek stream's chunks give progress 35, 40, ... 70; none exceed the old decile 7 until the stream passes the old high-water mark, so no `updateStreamingProgress` is dispatched. If the previous stream had delivered everything (short tracks, or after flow control caught up) `last = 100` and nothing is dispatched until the final chunk. `usePlayEnhanced` passes `throttleProgress: true` (usePlayEnhanced.ts:157).
  - Existing test `hooks/enhancement/__tests__/startChunkOffset.test.ts` covers `ingestChunk` arithmetic only, not the ref reset on the resume path.
- **Impact**: After most seeks (any seek whose chunk progress is below the pre-seek high-water decile, i.e. every backward seek and every seek after a fully delivered short track): the player shows a permanent "Buffering..." spinner, the buffered bar sits at 0% instead of its true edge (the very symptom #5931 set out to fix), and the local-stall indicator (#5461) can never show because `isStalled` requires `'streaming'`. State heals only when the stream reaches the old decile or its last chunk. Audio is unaffected.
- **Suggested Fix**: Frontend only. Reset `core.lastDispatchedProgressRef.current = -1` (and `flowPausedRef` for symmetry) in the resume branch of `handleStreamStart` before the `startStreaming` dispatch (or in `sendSeek`), so the first chunk of every stream, seek stream included, always dispatches. Add a hook-level test: stream to 80%, `audio_stream_start{is_seek}`, first chunk -> expect `streaming` state and non-zero `processedChunks`.

#### F9-01: Clear Queue leaves the browser stream playing with no UI control that can stop it
- **Severity**: MEDIUM
- **Flow**: 9 (Queue & Playback State)
- **Boundary**: Backend (`QueueService.clear_queue`, `queue_changed`/`player_state`) → Frontend (queue panel, playback session)
- **Location**: `auralis-web/backend/services/queue_edit_mixin.py:262-280` → `auralis-web/frontend/src/hooks/player/useQueueEditMutations.ts:117-120`, `auralis-web/frontend/src/components/player/QueuePanel/QueuePanelExpanded.tsx:139-146`, `auralis-web/frontend/src/hooks/player/playerStateSnapshot.ts:53-60`, `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:115-120`, `auralis-web/frontend/src/contexts/usePlaybackNavigation.ts:45-52`
- **Status**: NEW (related but distinct from closed #6016, which fixed only remove-one-row via `useFollowRemovedTrack`; the clear path has no equivalent)
- **Description**: Clear stops only the engine's shadow player (`audio_player.stop`) and resets `PlayerState` (`set_playing(False)`, `set_track(None)`). The audio the user hears comes from the WebSocket PCM stream into the browser's AudioWorklet, which the backend does not cancel and the frontend never stops on clear. `confirmClearQueue` calls only `clearQueue()` (Redux `clearQueue` + `POST /queue/clear`); unlike `removeTrackFollowingPlayback` it never calls `stopPlayback`. The resulting `player_state` snapshot carries `current_track: null`, which `applyPlayerStateSnapshot` applies (`dispatch(setCurrentTrack(null))`), while `is_playing: false` is ignored because `sessionOwnsPlayback` was computed from the pre-dispatch track (playerStateSnapshot.ts:70). `queue_changed{cleared, current_index:-1}` changes nothing else (`useQueueSubscription` only sets queue/index).
- **Evidence**:
  - Backend `clear_queue`: `queue_manager.clear_queue(); await asyncio.to_thread(self.audio_player.stop)`, then `set_playing(False)`, `set_track(None)`, `_broadcast_queue_changed(action="cleared")`. Nothing touches `audio_stream_controller` or sends `playback_stopped`.
  - Frontend `handlePlayPause`: `if (!currentTrack?.id) { ... return; }` — a no-op once `currentTrack` is null even though `isPlaybackActive` (`isStreaming`) is true. `usePlaybackNavigation.step`: with an empty queue `index >= queueTracks.length` and repeat != 'all' → `return` (no `stopPlayback`). `useAutoAdvance` computes `trackDuration = currentTrack?.duration ?? 0`, so it also never fires.
  - Grep of `stopPlayback(` callers: only `usePlaybackNavigation`, `useFollowRemovedTrack`, seek/stream re-issue. No reaction to `currentTrack → null` or `queue_changed.action === 'cleared'`.
- **Impact**: After "Clear" while a track plays, the UI shows an empty queue and "No track" but audio keeps playing to the end. Play/Pause (button and Space), Next and Previous are all no-ops; only volume/mute, seek, or starting another track affects it. The user cannot stop playback from the transport.
- **Suggested Fix**: Frontend: make the clear path follow playback like #6016 — in `QueuePanel`, wrap `clearQueue` with a session call that runs `stopPlayback()` (through the transport gate) when the queue is cleared; or have `PlaybackSessionProvider` stop the stream when `queue_changed.action === 'cleared'` / `player.currentTrack` becomes null while `isStreaming`. Also relax `handlePlayPause` so an active session can be paused without a `currentTrack`.

#### F9-02: `useQueueFetch` applies the engine's stale queue pointer unreconciled, and re-runs on every sidebar expand
- **Severity**: MEDIUM
- **Flow**: 9
- **Boundary**: Backend (`GET /api/player/queue`, engine pointer) → Frontend (Redux queue slice)
- **Location**: `auralis-web/backend/services/queue_service.py:46-91` → `auralis-web/frontend/src/hooks/player/useQueueFetch.ts:58-68`; re-mount trigger `auralis-web/frontend/src/components/playlist/usePlaylistContextActions.ts:28` via `auralis-web/frontend/src/components/layouts/Sidebar/Sidebar.tsx:53-58`
- **Status**: NEW (uncovered sibling of closed #5601: its `reconcileQueueIndex` guard is intact on `queue_changed`, `player_state` and `track_changed`, but this fourth applier was never covered; stale pointer itself is Existing #5937)
- **Description**: `GET /api/player/queue` returns `current_index`/`current_track` straight from the engine queue, whose pointer does not follow client-side navigation (#5937). `useQueueFetch` dispatches `reduxSetQueue(...)` then `reduxSetCurrentIndex(response.current_index ?? 0)` raw, with no `reconcileQueueIndex` against the playing track. It runs in a mount effect of `usePlaybackQueue`, and `usePlaybackQueue` is not mounted once: `usePlaylistContextActions` calls it only to obtain `setQueue`, and `PlaylistList` (hence that hook) lives in `SidebarContent`, which `Sidebar` unmounts/remounts on every collapse/expand (`if (collapsed) return <CollapsedSidebar/>`). Every remount therefore refires the REST fetch and overwrites the live queue index (and `isShuffled`, `repeatMode`) with the engine's. Each extra `usePlaybackQueue` instance also adds a duplicate `queue_changed` WS subscriber.
- **Evidence**:
  - `useQueueFetch.ts:58-61`: `dispatch(reduxSetQueue(...)); dispatch(reduxSetCurrentIndex(response.current_index ?? 0)); dispatch(reduxSetIsShuffled(response.shuffle_enabled ?? false));` — contrast `useQueueSubscription.ts:56-64` and `playerStateSnapshot.ts:121-128`, which call `reconcileQueueIndex(tracks, engineIdx, playingTrackId)`.
  - `usePlaylistContextActions.ts:28`: `const { setQueue } = usePlaybackQueue();` (the sibling artist hook correctly imports `setQueue` from `services/queueService` instead).
  - `queueIndexReconciliation.ts` header documents this exact hazard ("Any backend snapshot that then carries the engine's stale pointer ... would jump the UI back to a track the audio left long ago").
- **Impact**: Play A, press Next to B (engine pointer stays on A), collapse and re-expand the sidebar: the queue highlight jumps back to A while B keeps playing; Next/auto-advance then step from A's slot and replay/skip tracks. Shuffle and repeat toggles also snap to engine values mid-session.
- **Suggested Fix**: Frontend. Run the fetch result through `reconcileQueueIndex` with `store.getState().player.currentTrack?.id` (same as the other appliers); and change `usePlaylistContextActions` to use `services/queueService.setQueue` (as the artist hook does) so only `QueuePanel` owns `usePlaybackQueue`'s fetch/subscription side effects.

#### F9-03: A queue built while nothing is playing is unreachable from the transport, and row 0 is labelled "playing"
- **Severity**: MEDIUM
- **Flow**: 9
- **Boundary**: Engine/Backend (`current_index = -1`, no current track) → Frontend (queue slice default index 0, transport)
- **Location**: `auralis/player/components/queue_manager.py:25,32-36` (append leaves `current_index` at -1) and `auralis-web/backend/services/queue_service_base.py:186-198` (`queue_changed.current_index = -1`) → `auralis-web/frontend/src/store/slices/queueSlice.ts:24,144`, `auralis-web/frontend/src/hooks/player/queueIndexReconciliation.ts:27-30`, `auralis-web/frontend/src/components/player/QueuePanel/QueuePanelExpanded.tsx:239`, `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:115-120`, `auralis-web/frontend/src/contexts/usePlaybackNavigation.ts:43-52`
- **Status**: NEW
- **Description**: The engine represents "nothing selected" as `current_index == -1` (empty queue; `add_track`/`add_tracks` never select). The frontend has no such state: `queue.currentIndex` is initialised to 0 and `clearQueue`/`setQueue` clamp to `>= 0`, and `reconcileQueueIndex` treats an engine index of -1 as "keep local". So after "Add to queue" (single or bulk, #5612/#5651) on an empty or cleared queue with no track playing, Redux holds `tracks=[T1,...]`, `currentIndex=0`, `player.currentTrack=null`. Queue rows have no click-to-play handler. Play/Pause does nothing without `currentTrack`; Next computes `currentIndex + 1`, so it starts T2 and T1 is skipped (with a one-track queue Next is "already at last"). Meanwhile row 0 renders the "▶ playing" marker because `isCurrentTrack = index === currentIndex`.
- **Evidence**: `handlePlayPause`: `if (!currentTrack?.id) { DEBUG && console.warn('No track loaded, cannot play'); return; }`. `usePlaybackNavigation.step`: `let index = currentQueueIndex + delta`. `QueueTrackItem.tsx` has `onMouseEnter/KeyDown/Drag*` handlers only (no `onClick` play). Engine: `get_queue_info()['current_index'] == -1` after add-to-empty, broadcast as `current_index: -1`.
- **Impact**: Tracks queued from the library into an idle player cannot be started from the queue or transport; Next silently skips the first queued track; the queue panel claims a track is playing when none is. Workaround: play any track from the library (which resets the queue via `set_queue`).
- **Suggested Fix**: Frontend: when `player.currentTrack` is null, make Play/Next start `queue.tracks[currentIndex]` (index 0) instead of no-op / index+1, and render the playing marker only when `player.currentTrack?.id === track.id`; optionally add click/double-click-to-play on queue rows.

### LOW (22)

#### F1-04: Client-side stop never reaches the backend; the removed/stopped track keeps rendering and streaming
- **Severity**: LOW
- **Flow**: 1 (Track Playback) — lifecycle
- **Boundary**: Frontend (`usePlaybackTransport.stopPlayback`, `useFollowRemovedTrack`) → Backend (stream task, stream-slot semaphore)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlaybackTransport.ts:78-88`, `auralis-web/frontend/src/contexts/useFollowRemovedTrack.ts:46-58` → `auralis-web/backend/ws_handlers/playback_control.py:75-100` (`handle_stop`, never sent)
- **Status**: NEW
- **Description**: `stopPlayback()` is documented as "client-side only (no WS stop)": it ends the tracked stream, disposes the ring and engine, and returns. No client path sends `{type: 'stop'}` (the only `stop` sends in `src/` are the bookkeeping branches in `useOutgoingChannel`/`replayQueueAndResume`). When `stopPlayback()` is not immediately followed by a new `play_*` (which cancels the old task), the backend stream task keeps running: `useFollowRemovedTrack` stops and, if the removed track was the last one or the session was not running (`wasRunning` false, i.e. paused), starts nothing. With the ring gone the client sends no `buffer_full`, so the server does not throttle: it renders every remaining chunk at full DSP speed (each looks like a cache miss on first play) and pushes it into a socket whose frames the client drops after 64 queued (`MAX_PENDING_CHUNK_FRAMES`), holding one of the 10 stream permits and a leased `HybridProcessor` until the track ends, the next play, or disconnect.
- **Evidence**: `usePlaybackTransport.ts:78-88`: `endActiveStream(); playbackEngineRef.current?.stopPlayback(); dispatch(resetStreaming(streamType)); cleanupStreaming(); ...` with no `wsContext.send`. `useFollowRemovedTrack.ts:50-54`: `stopPlayback(); const successor = queue.tracks[index]; if (!successor) { dispatch(setCurrentTrack(null)); return; }`. Backend `handle_stop` (detach, signal cancel event, cancel task) is reachable only by a `stop` frame no client sends.
- **Impact**: Wasted CPU/IO and a held stream slot for up to the remaining length of the stopped track (minutes of DSP for a long track), and the orphan's frames can pile into the next session's `pendingChunksRef` until `play` clears it. Bounded by the next play/disconnect, so low severity.
- **Suggested Fix**: Send `stop` from `stopPlayback()` only when it is not immediately followed by a play (e.g. add a `{notifyBackend}` option used by `useFollowRemovedTrack` and by a user stop), or have `cleanupStreaming` send `stop` when it disposes a live buffer for a stream that has not ended. Keep `pause` client-only (#5514).
- **Merged from**: F5-01 (Flow 5 found the same missing `stop` on the WebSocket-lifecycle side: client stop and terminal-error teardown never reach the backend).

#### F2-05: `AlbumTracksResponse` docstring still says the sibling `GET /api/albums/{id}` is camelCase
- **Severity**: LOW
- **Flow**: 2 (Library Browsing)
- **Boundary**: Backend schema documentation (OpenAPI description) ↔ actual wire contract
- **Location**: `auralis-web/backend/routers/albums_models.py:12-18` vs `auralis-web/backend/routers/albums.py:141-152`
- **Status**: NEW
- **Description**: The model docstring (which becomes the OpenAPI schema description) says the track-list response is "Deliberately snake_case while the sibling `GET /api/albums/{id}` is camelCase". #4679 made `/api/albums/{id}` snake_case and removed the camelCase serializer (albums.py comment says so).
- **Evidence**: `albums.py:153: return serialize_album(album)` with `response_model=AlbumResponse` (snake_case fields in `schemas/library.py:149`).
- **Impact**: Misleads anyone writing a client from the OpenAPI doc; no runtime effect.
- **Suggested Fix**: Reword the docstring to drop the camelCase claim.

#### F2-06: `PlaylistListResponse` re-declares the paging envelope instead of extending `PaginatedResponse`; frontend `Playlist.created_at/updated_at` typed non-null
- **Severity**: LOW
- **Flow**: 2 (Library Browsing) — playlists
- **Boundary**: Backend `PlaylistListResponse` / `PlaylistResponse` → frontend `PlaylistsResponse` / `Playlist`
- **Location**: `auralis-web/backend/routers/playlists_models.py:55-62` (vs `schemas/library.py:136` `PaginatedResponse`); `auralis-web/backend/schemas/library.py:194-195` → `auralis-web/frontend/src/services/playlistService.ts:34-35`
- **Status**: NEW
- **Description**: (a) The playlists list route is on the envelope by value (`paginated("playlists", …)`), but its response model copies the four fields instead of subclassing `PaginatedResponse` like tracks/albums/artists, so `test_paginated_envelope_shared_5499.py` does not cover it and a future envelope change can skip it. (b) `PlaylistResponse.created_at/updated_at` are `str | None` (columns are `Mapped[datetime | None]`), but the TS `Playlist` declares `created_at: string; updated_at: string` — the same "nullable backend field typed non-null" class as #6049.
- **Evidence**: `class PlaylistListResponse(BaseModel): playlists…; total…; limit…; offset…; has_more…`; TS `created_at: string;`.
- **Impact**: Maintenance drift risk and a latent `undefined/null` read if a null timestamp row ever appears; nothing breaks today (defaults populate timestamps).
- **Suggested Fix**: `class PlaylistListResponse(PaginatedResponse)` with just `playlists`, add it to the #5499 parametrized test; type the TS timestamps `string | null`.

#### F3-02: Enhancement toggle failure is an unhandled promise rejection and is never surfaced
- **Severity**: LOW
- **Flow**: 3 (Audio Enhancement)
- **Boundary**: Backend (`POST /api/player/enhancement/toggle` 4xx/5xx/timeout) -> Frontend (`AlbumCharacterPane` -> `EnhancementToggle`)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementCommands.ts:94-100,160-163` -> `auralis-web/frontend/src/components/library/AlbumCharacterPane/AlbumCharacterPane.tsx:73,158-161` -> `auralis-web/frontend/src/components/shared/EnhancementToggle/SwitchVariant.tsx:40`
- **Status**: NEW
- **Description**: `runCommand` sets the hook's `error` state and then rethrows the `ApiError`. The only UI consumer of the live toggle destructures just `{ enabled, setEnabled }`, passes `setEnabled` (typed `Promise<void>`) as `onToggle: (enabled: boolean) => void`, and never reads `error`. `SwitchVariant` calls `onToggle(e.target.checked)` without `.catch`, and no `unhandledrejection` handler exists in the frontend. A 429/500/503/timeout on the toggle POST therefore leaves the switch snapping back with no message and an unhandled rejection in the console.
- **Evidence**:
  - Sender: `useEnhancementCommands.ts:94-99`:
    ```ts
    } catch (err) {
      ...
      setError(apiError);
      throw apiError;
    ```
  - Receiver: `AlbumCharacterPane.tsx:73`: `const { enabled: isEnhancementEnabled, setEnabled } = useEnhancementControl();` and `:161`: `onToggle={setEnabled}`. `isProcessing` is not passed either.
  - `SwitchVariant.tsx:40`: `onChange={(e) => onToggle(e.target.checked)}`.
- **Impact**: A failed toggle gives no feedback, so the user cannot tell whether auto-mastering is on. The persisted/runtime state is unchanged, so audio stays consistent. This is a UX and error-handling gap, not a data-integrity one.
- **Suggested Fix**: Frontend: in `AlbumCharacterPane` wrap the call (`onToggle={(v) => { void setEnabled(v).catch(() => {}); }}`) and render the hook's `error` or a toast. Pass `isProcessing={isLoading}` so the switch reflects the in-flight request.

#### F3-03: The local-command suppression window is armed after the POST resolves, but the confirmation broadcast is sent before the response, so one toggle can re-issue the stream twice
- **Severity**: LOW
- **Flow**: 3 (Audio Enhancement)
- **Boundary**: Backend (`toggle_enhancement`: broadcast, then HTTP response) -> Frontend (`useEnhancementStatusSync` external-change classification)
- **Location**: `auralis-web/backend/routers/enhancement_controls.py:278-293` -> `auralis-web/frontend/src/hooks/enhancement/useEnhancementCommands.ts:90-92,125,149` and `enhancementBroadcastReissue.ts:250-257` / `useEnhancementStatusSync.ts:293-296`
- **Status**: NEW
- **Description**: A local command is supposed to suppress its own echo (`markLocalEnhancementCommand` + a 2 s window) so only one re-issue happens. `markLocalEnhancementCommand()` runs inside `apply`, i.e. after `await spec.request()`. The server awaits `broadcast_typed(...)` before it returns the HTTP response, so the WS frame is written first. The WS handler runs synchronously on arrival. If it arrives before the POST promise resolves, `isExternalChange()` is still true and the broadcast is treated as a Settings-originated change. The handler's refs still hold the old state, because the optimistic `applyState` has not run. It therefore re-issues the stream (`play_normal` or `play_enhanced`), then `apply` runs and re-issues a second time. The second `play_*` cancels the first stream, so there are two stream restarts, two buffer flushes and two DSP starts for one toggle. Whether the WS frame wins the race is not guaranteed (different sockets), so the effect is probabilistic. The existing test (`useEnhancementControl.test.ts`, "does not re-issue on top of a local command") only covers broadcast-after-command ordering.
- **Evidence**:
  - Server: `enhancement_controls.py:278-293` broadcasts, then `return {...}`.
  - Client: `useEnhancementCommands.ts:90-92` `await spec.request(); ... spec.apply();`, with `markLocalEnhancementCommand()` only at `:125` and `:149`, both inside `apply`. `useEnhancementStatusSync.ts:293` `if (onExternalChange && isExternalChange())`.
- **Impact**: Duplicate stream restarts on enhancement toggle: wasted DSP, a longer audible gap from the double flush, and a second cancelled stream. Playback recovers. This path is currently reachable only through the `AlbumCharacterPane` switch, since `setIntensity`/`setPreset` have no UI caller.
- **Suggested Fix**: Frontend: call `markLocalEnhancementCommand()` before `post(...)` (at command start) instead of in `apply`, so the broadcast that precedes the response is already suppressed. Alternatively, have the server omit the echo to the originating client.

#### F4-02: Frontend scan timeout is hard-coded to the backend's default, not its configured value
- **Severity**: LOW
- **Flow**: 4 (Library Scanning) - Scan request / large folders
- **Boundary**: Frontend -> Backend (`POST /api/library/scan`)
- **Location**: `auralis-web/frontend/src/config/api.ts:58` (`SCAN_TIMEOUT_MS = 3_660_000`) -> `auralis-web/backend/config/limits.py:185` (`SCAN_TIMEOUT_S = get_int_env("AURALIS_SCAN_TIMEOUT", 3600)`)
- **Status**: NEW (adjacent closed: #5643 fixed the 30 s default; #5991 only hardened env parsing)
- **Description**: The frontend's per-request timeout is a literal (backend default 3600 s + 60 s). The backend value is environment-overridable, and the frontend has no way to learn it. Since #4820 an aborted fetch is a "stop the scan" signal (`_watch_for_disconnect` -> `ScanClientGone` -> `stop_scanner`). If the operator raises `AURALIS_SCAN_TIMEOUT` above ~1 h for a very large initial import, the frontend aborts at 61 min, the backend treats it as a client disconnect, stops the scan, broadcasts `library_scan_error: "library scan cancelled"`, and the UI reports a failure. The configured limit is never reached.
- **Evidence**: `config/api.ts:52-58` comment documents the coupling ("the meaningful bound is the backend's own AURALIS_SCAN_TIMEOUT (1h) ... this sits just past it") but encodes only the default. Used by `useLibraryScan.ts:127` and `settingsService.ts:213-217`.
- **Impact**: Only when the env override exceeds the default. Large first-time imports are cut at about 1 h regardless of configuration, with a misleading "cancelled" frame.
- **Suggested Fix**: Either expose `SCAN_TIMEOUT_S` (for example in the settings or health payload) and derive the frontend bound from it, or drop the client-side upper bound for this endpoint (the backend 504 is already the bound, and the abort signal still serves unmount). Failing that, document the env var as "frontend must be rebuilt".

#### F4-03: Rescan existence check is one full ORM load per file; the batched lookup is unused by the scanner
- **Severity**: LOW
- **Flow**: 4 (Library Scanning) - Filesystem scan -> Database
- **Boundary**: Engine scanner -> Repository
- **Location**: `auralis/library/scanner/batch_processor.py:162` (`tracks_repo.get_by_path(file_path)` inside the per-file loop) -> `auralis/library/repositories/track_repository_lookup.py:56` (`get_by_path`; the batched `get_by_paths` at `:67` has one production caller, queue enrichment)
- **Status**: NEW
- **Description**: `process_file_batch` receives 50 paths at a time (`DEFAULT_BATCH_SIZE`) but resolves each with its own `get_by_path`, which opens a session and loads the Track plus its eager `selectinload` collections (artists/album/genres), only to compare `file_mtime`/`filesize` for the common "skipped" outcome. The auto-scanner rescans every configured folder on each cycle (default hourly, plus on every debounced watchdog event), so this per-file cost is paid for the whole library each time.
- **Evidence**: Measured locally on a scratch SQLite DB with 2000 tracks: `get_by_path` is about 0.96 ms per file (about 96 s per 100k files), `get_by_paths` in batches of 50 is about 0.05 ms per file (about 19x less). The scan runs in a worker thread, so this is latency and DB contention, not event-loop blocking.
- **Impact**: Minutes of avoidable DB work per cycle on very large libraries; no correctness effect.
- **Suggested Fix**: In `process_file_batch`, prefetch `existing = tracks_repo.get_by_paths(file_paths)` once per batch and pass it to `process_single_file` (keeping `get_by_path` as a fallback for single-file callers).

#### F5-03: `mastering_recommendation` broadcast has no frontend subscriber and its only emitter is a REST route no client calls
- **Severity**: LOW
- **Flow**: 5 (WebSocket Lifecycle) — message types documented and handled on both sides
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/services/recommendation_service.py:107` (emit, reached only from `auralis-web/backend/routers/player_playback.py:131-137`, `POST /api/player/load`) → `auralis-web/frontend/src/types/ws/registry.ts:146` (type declared, zero subscribers; `ENDPOINTS.PLAYER_LOAD` at `config/api.ts:109` has no caller)
- **Status**: NEW (same dead-surface class as closed #5916 and #5887, which removed the WS play trigger and the panel but left this emitter and type; `track_loaded`, the other consumer-less type, is already documented as informational)
- **Description**: #5887 removed the per-play analysis. The remaining trigger, `load_track()` scheduling `generate_and_broadcast_recommendation` as a background task, belongs to `POST /api/player/load`, which the frontend never calls (the `PLAYER_LOAD` constant is unused; playback starts over WS `play_*`). The `GET /api/player/mastering/recommendation/{id}` route also has no frontend caller. `mastering_recommendation` therefore has a typed payload, an `ALL_MESSAGE_TYPES` entry and a WEBSOCKET_API.md section ("Trigger: When track loads") describing a flow that cannot happen from the app. Unlike `track_loaded`, it is not recorded as intentionally informational.
- **Evidence**:
  ```python
  # player_playback.py:131-137
  background_tasks.add_task(recommendation_service.generate_and_broadcast_recommendation, track_id=track.id, track_path=track.filepath)
  ```
  ```ts
  // grep -rn "mastering_recommendation" frontend/src (non-test): types/ws/registry.ts, types/ws/enhancement.ts only
  ```
- **Impact**: Documentation/contract drift only; a full analysis plus broadcast runs if anything ever calls the REST route, with no consumer. No user-visible failure.
- **Suggested Fix**: Either delete the emitter, the route's background task and the WS type end-to-end (consistent with #5887/#5916), or add it to the documented-informational list next to `track_loaded` and correct the "Trigger" line in `WEBSOCKET_API.md`.

#### F5-04: Library, album and artwork caches are not revalidated after a WebSocket reconnect; `library_updated` / `metadata_*` / `library_tracks_removed` / `artwork_updated` are fire-and-forget
- **Severity**: LOW
- **Flow**: 5 (WebSocket Lifecycle) — reconnection re-establishes state
- **Boundary**: Backend → Frontend (state sync after disconnect)
- **Location**: `auralis-web/backend/ws_handlers/connection.py:142-176` (reconnect pushes only `enhancement_settings_changed` and `player_state`) → `auralis-web/frontend/src/hooks/library/useLibraryChangeSync.ts:33-52`, `auralis-web/frontend/src/hooks/library/useArtworkUpdates.ts:79-103`
- **Status**: NEW (reconnect resync already exists for the scan status, #4821 `useScanProgress.ts:268`, and playlists, #6042 `usePlaylistWebSocket.ts:43`; library/albums/artwork were not covered by any closed issue)
- **Description**: On connect the server replays two snapshots and the client resyncs scan status and playlists. Everything else the client learns from broadcast frames is not replayed: a `library_updated` (auto-scanner or scan finishing), `library_tracks_removed`, `metadata_updated`/`metadata_batch_updated` or `artwork_updated` frame emitted while the socket was down (backend restart during `--dev` reload, the ~3 min backoff window, the give-up state until `useReconnectOnNetwork`) is lost. `useLibraryChangeSync` only invalidates on those frames; the QueryClient has `refetchOnWindowFocus: false` and a 5 min `staleTime` (`App.tsx:24`), and nothing keys off `connectionStatus === 'connected'` for these caches.
- **Evidence**:
  ```ts
  // useLibraryChangeSync.ts:33-52 — invalidation only inside the frame handler
  useWebSocketMessages(LIBRARY_CHANGE_MESSAGES, handleChange);
  // grep connectionStatus/isConnected consumers: only useScanProgress.ts:268 and usePlaylistWebSocket.ts:43
  ```
- **Impact**: After an outage that spans a library change, album/track grids and artwork stay on the pre-outage data (removed albums still clickable then 404, new tracks absent) until the 5 min staleTime lapses and a view remounts, or the user reloads. Limited by the single-client desktop setting and by needing the change to land during the outage.
- **Suggested Fix**: Frontend: in `useLibraryChangeSync`, invalidate `['albums']` / `['album-fingerprint']` (and bump artwork revisions or invalidate the track list) on a `connectionStatus` transition to `'connected'` that is not the first connect, mirroring the playlist/scan resync pattern.

#### F6-01: Similarity/fingerprint-queue routes answer 500 + traceback for a track id above 2^63-1 (incomplete fix of #6162)
- **Severity**: LOW
- **Flow**: 6 (Fingerprint & Similarity)
- **Boundary**: Frontend/HTTP client -> Backend similarity routers -> SQLite binding
- **Location**: `auralis-web/backend/routers/similarity_common.py:97-121` (`_with_similarity_error_handling`) <- `similarity_query.py:217-252,319-344`, `similarity_explain.py:21-59`, `fingerprint_queue.py:292-309`; compare `routers/errors.py:137-141` (`handle_query_error`)
- **Status**: Regression of #6162 (closed; the fix covered only routes wrapped by `with_error_handling`)
- **Description**: #6162 made an id above SQLite's INTEGER range a 404 by adding an `OverflowError` branch to `handle_query_error` (and `TrackId` with `le=MAX_SQLITE_INT` for body models). The similarity router family does not use `with_error_handling`; it has its own decorator, `_with_similarity_error_handling`, which handles `HTTPException` and `OperationalError` only and sends every other exception to `_internal_error_response` (HTTP 500 + `logger.exception`). Its path ids are `Annotated[int, Path(ge=1)]` with no upper bound, so `repos.tracks.get_by_id(10**20)` raises `OverflowError` inside the decorator.
- **Evidence**: reproduced at HEAD with a real `LibraryDatabase` behind `create_similarity_router`:
  ```
  GET /api/similarity/tracks/99999999999999999999/similar          -> 500 {"detail":"Error finding similar tracks (ref e939c2d7)"}  + OverflowError traceback in the log
  GET /api/similarity/tracks/99999999999999999999/similar?limit=5  -> 500
  ```
  The sibling routes (`fingerprint_status.get_track_fingerprint`, `albums_fingerprint`) use `with_error_handling` and map the same input to 404.
- **Impact**: Error noise (ERROR traceback per request) and a 500 instead of 404 on four routes (`/similar`, `/compare`, `/explain`, `POST /fingerprint-queue/enqueue/{id}`). Not reachable from the UI (ids come from the library); only a hand-built request or a corrupted id.
- **Suggested Fix**: Add `except OverflowError` -> `NotFoundError("Resource")` to `_with_similarity_error_handling` (or delegate to `handle_query_error`'s mapping), or bound the path ids with `le=MAX_SQLITE_INT` (use `TrackId`).

#### F6-03: "Analyse remaining" is a silent no-op when the pending tracks are outdated (residual of #5891)
- **Severity**: LOW
- **Flow**: 6 (Fingerprint & Similarity)
- **Boundary**: Frontend `FingerprintCoverageCard` / `useFingerprintCoverage` -> Backend `fingerprint_status` + `fingerprint_queue` routers -> `FingerprintStatsRepository`
- **Location**: `auralis-web/backend/routers/fingerprint_status.py:62-88` (pending = total - current) vs `auralis-web/backend/routers/fingerprint_queue.py:350-362,371` (pending = `stats['pending']`, tracks = `get_missing_fingerprints`); `auralis/library/repositories/fingerprint_stats_repository.py:60-72`, `fingerprint_query_mixin.py:240-258`
- **Status**: NEW (the closed #5891 explicitly left the enqueue-all route on the old keys: commit 5f5c20b2c "the enqueue-all route still reads them")
- **Description**: After #5891 the status route reports `fingerprinted_tracks = current` and `pending_tracks = total - current`, so tracks with an older-algorithm fingerprint count as pending and the card shows the "Analyse remaining" button (`useFingerprintCoverage.ts`, `FingerprintCoverageCard.tsx:129-143`). That button calls `POST /api/similarity/fingerprint-queue/enqueue-all`, which still reads `stats['pending']` (= total - current - outdated) and `get_missing_fingerprints` (an outer join on "no fingerprint row"). Outdated rows are therefore never enqueued, and with only outdated rows left the route returns `{"enqueued": 0, "message": "All tracks already have fingerprints!"}`; the hook only surfaces `message` when `dropped_queue_full` is set, so the click shows nothing.
- **Evidence**: `fingerprint_queue.py:352-362` (`pending = stats['pending']`; `if pending == 0: return {... "All tracks already have fingerprints!"}`); `fingerprint_stats_repository.py:61-62` (`pending_count = total - (current+outdated)`); `useFingerprintCoverage.ts` `analyseRemaining` (notice only for `dropped_queue_full`).
- **Impact**: After a `FINGERPRINT_ALGORITHM_VERSION` bump the card shows "fingerprinting in progress (N/M)" with an "Analyse remaining" button that does nothing. The background `FingerprintExtractionQueue` Phase 2 re-fingerprints outdated rows on its own wave (after startup or scan), so no data is lost; only the manual trigger is dead and the message is wrong. Tracks with a stuck claim placeholder are in the same state.
- **Suggested Fix**: Make enqueue-all use the same definition as the status route (current-version rows count as fingerprinted; select tracks whose fingerprint is missing, placeholder, or outdated), or hide the button when `missing == 0` and tell the user the outdated ones are re-analysed automatically.

#### F6-04: `/explain` names and scales the same dimensions differently from the other fingerprint endpoints
- **Severity**: LOW
- **Flow**: 6 (Fingerprint & Similarity)
- **Boundary**: Engine `get_similarity_explanation` -> Backend `SimilarityExplanation` -> (no frontend consumer today)
- **Location**: `auralis/analysis/fingerprint/similarity_explanation.py:63-96` (`dimension` = DB names from `DIMENSION_NAMES`; `value1/value2` = raw stored columns) vs `auralis-web/backend/routers/fingerprint_status.py:153-187` and `albums_fingerprint.py:24-73` (API names, centroid/rolloff in Hz)
- **Status**: NEW
- **Description**: The track and album fingerprint endpoints use the API vocabulary of `FingerprintVectorResponse` (`bass`, `pitch_confidence`, `chroma_energy_mean`, `stereo_correlation`; `spectral_centroid`/`rolloff` converted to Hz, #2477/#5470). `/api/similarity/tracks/{a}/explain/{b}` returns `dimension` as DB column names (`bass_pct`, `pitch_stability`, `chroma_energy`, `phase_correlation`) and `value1/value2/difference` for `spectral_centroid`/`spectral_rolloff` as the stored 0-1 normalized values, not Hz.
- **Evidence**: `similarity_explanation.py:72-84` builds `_entry` from `raw1 = fp1.to_vector()` with no `centroid_to_hz`/`rolloff_to_hz` and no `_DB_TO_API` rename; `similarity_models.py:162-172` documents them only as "raw (denormalized) per-track values".
- **Impact**: A client that joins an explain row with a `/tracks/{id}/fingerprint` value by dimension name finds no match for 12 of 25 dimensions and a 8000x/10000x unit difference for two. No frontend consumer exists (the discovery tree was deleted in #4912), so there is no visible breakage today; the first consumer to be added repeats #4846/#5470.
- **Suggested Fix**: Map explain dimensions through the shared DB->API table (move `_DB_TO_API` next to `FingerprintVectorResponse`) and convert centroid/rolloff with `centroid_to_hz`/`rolloff_to_hz`, or document the DB-name/normalized contract in `DimensionContribution`.

#### F7-02: Track grid cards and the player bar can never show artwork that appears after load (sibling gap of #5894)
- **Severity**: LOW
- **Flow**: 7 (Artwork)
- **Boundary**: Backend WS `artwork_updated` -> Frontend `useArtworkRevision` consumers
- **Location**: `auralis-web/backend/routers/artwork_deps.py:25-44` (broadcast) -> `auralis-web/frontend/src/components/track/TrackCard.tsx:51-64`, `auralis-web/frontend/src/components/player/Player.tsx:50-56`
- **Status**: NEW (sibling of closed #5894, which fixed only `AlbumCard` and `TrackRow`; those two guards verified still in place)
- **Description**: `AlbumCard.tsx:74` and `TrackRow.tsx:119-123` build the URL from the album id once the revision is > 0, so art that did not exist at load time can appear. `TrackCard` still does `withArtworkSize(albumArt, size, revision)`, and `withArtworkSize` returns `undefined` for an undefined `albumArt`, so the revision bump is a no-op for a track whose album had no art at load. `Player.tsx` derives the album id by regex from `currentTrack.artworkUrl`; when that is null the id is 0, `useArtworkRevision(0)` never bumps, and `playerBarArtwork` stays `undefined`. TrackCard's own comment ("a mounted card keeps the old (or broken) image after the album's artwork is extracted") describes exactly the case it does not handle for the extract path.
- **Evidence**: `TrackCard.tsx:64 artworkUrl={withArtworkSize(albumArt, artworkSize, artworkRevision)}`; `artworkService.ts:57 if (!url) return url;`; `Player.tsx:53 Number(/\/albums\/(\d+)\/artwork/.exec(currentTrack?.artworkUrl ?? '')?.[1] ?? 0)`.
- **Impact**: After extract/download (only reachable through the API, no UI), the track grid and the player bar keep the placeholder until the list/track is reloaded. Low because the trigger has no UI.
- **Suggested Fix**: In `TrackCard`, fall back to `getArtworkUrl(albumId, {size, revision})` when `albumArt` is empty and `revision > 0` (as TrackRow does). In `Player`, carry `albumId` on `PlayerTrack` (or the backend `TrackInfo`) instead of regexing the URL, and apply the same fallback.

#### F7-03: Palette-mode (indexed PNG / GIF) covers are downscaled with nearest-neighbour, producing aliased thumbnails
- **Severity**: LOW
- **Flow**: 7 (Artwork)
- **Boundary**: Backend thumbnail renderer -> Frontend grid / player bar
- **Location**: `auralis-web/backend/routers/artwork_thumbnails.py:103-116` (`_render_thumbnail`)
- **Status**: NEW
- **Description**: `image.thumbnail((bucket, bucket))` is called on the image in its native mode. Pillow forces `Resampling.NEAREST` for modes `"1"` and `"P"` (documented on `Image.resize`), and the render path only converts to RGB for the JPEG target (`pil_fmt == "JPEG" and mode not in ("RGB","L")`). PNG/GIF sources are rendered as PNG and left in `P`, so every indexed-colour or GIF cover is shrunk 4-16x with no filtering (and keeps a quantised palette).
- **Evidence**: Running the real `_render_thumbnail` on a 512x512 1-px checkerboard to 64 px: RGB source -> mean 128.0 (correctly averaged); same image as mode P -> mean 0.0 (nearest sampling picked one phase). Same pattern in `artwork_security.bound_artwork_dimensions` for >2048 px sources.
- **Impact**: Jagged/shimmering thumbnails for albums whose cover is an 8-bit PNG or GIF (the format `_thumb_target` explicitly maps to PNG). Cosmetic, no data loss.
- **Suggested Fix**: Before `thumbnail()`, convert `P` (and `1`) images to `RGBA` if `"transparency" in image.info` else `RGB`; the PNG output stays lossless. Do the same in `bound_artwork_dimensions`.

#### F7-04: Thumbnail cache evicts oldest-created (not least-recently-used) and rescans the whole directory on every miss once over the cap
- **Severity**: LOW
- **Flow**: 7 (Artwork)
- **Boundary**: Backend thumbnail cache <-> Frontend grid scroll
- **Location**: `auralis-web/backend/core/thumbnail_cache.py:122-172` (`prune_thumbnail_cache`), called per miss at `auralis-web/backend/routers/artwork_thumbnails.py:202-206`
- **Status**: NEW (the #5255 cap itself is present and works; this is about its policy)
- **Description**: Eviction sorts by `st_mtime`, which is the render time; a cache hit never touches it, so the policy is FIFO, not LRU. Every miss while `total > THUMBNAIL_CACHE_MAX_BYTES` (128 MiB) also does a full `iterdir()` plus a `stat()` per entry before deleting a single file. A library whose grid working set exceeds the cap (roughly 6-7k albums at ~20 KB per 256-px JPEG; the cap comment itself says "thousands") evicts exactly the covers the user scrolled past first, so scrolling back re-renders them (PIL decode of a stored cover up to 2048 px) and each of those misses rescans the directory under the IO executor.
- **Evidence**: `entries.append((stat.st_mtime, ...))` / `entries.sort(key=lambda item: item[0])`; no `os.utime` anywhere on the hit path in `_get_or_create_thumbnail`.
- **Impact**: Large libraries (the brief's 100k+ track case) thrash the thumbnail cache and spend IO-pool time on repeated renders and directory scans; small libraries are unaffected.
- **Suggested Fix**: Touch `dst` on hit (cheap `os.utime`) or sort by `st_atime`-equivalent, and/or keep a running size counter / prune in batches to a low-water mark (e.g. evict down to 90% of the cap) so the scan is not repeated on every miss.

#### F8-02: Playback clock reads 0:00 between the seek click and `audio_stream_start`; the seek offset is armed only on the ack
- **Severity**: LOW
- **Flow**: 8
- **Boundary**: Frontend (seek command) -> Backend (`seek_started` / `audio_stream_start`) -> Frontend (playback clock)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:78-112` (`sendSeek`) -> `auralis-web/frontend/src/services/audio/PlaybackPositionTracker.ts:84-87` / `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:133-135`
- **Status**: NEW (related to #5860 which fixed the clock only from the ack onward)
- **Description**: `sendSeek` calls `playbackEngineRef.current.stopPlayback()`, whose `positionTracker.reset()` zeroes `seekOffsetSeconds` and `samplesPlayed` and sets state `'stopped'`. In `'stopped'` the tracker reports `seekOffsetSeconds + samplesPlayed/sr` = 0. Nothing arms the offset with the requested target at send time; `setSeekOffset(seekPosition)` runs only when `audio_stream_start` arrives (useEnhancedStreamStart.ts:133-135). The backend sends `seek_started` first (seek_command.py:102-105), which clears `isSeeking` (useEnhancedSeek.ts:135-138), then constructs a `ChunkedAudioProcessor` on a worker thread (stream_enhanced_lifecycle.py:108-118, 200 ms to seconds, up to `PROCESSOR_INIT_TIMEOUT` for a cold track) before `audio_stream_start` is emitted. For that whole window the 10 Hz poll (`usePlaybackTransport.ts:129-137`) feeds `getCurrentPlaybackTime() == 0` into `currentTime`.
- **Evidence**: `PlaybackPositionTracker.reset()` (`seekOffsetSeconds = 0`), `AudioPlaybackEngine.stopPlayback()` (:201-211); the only `setSeekOffset` call sites are `useEnhancedStreamStart.ts:134` and `:212`. `sendSeek` never calls it. Consumers of the clock in the window: `ProgressBar` (`wsCurrentTime`), `useKeyboardSeek.ts:58` (`targetRef.current ?? currentTime` base for the next arrow key), and the reconnect resume getter `usePlaybackTransport.ts:172-173`.
- **Impact**: After every click/drag seek the progress bar and time readout snap to 0:00 (no "Seeking..." overlay any more, since `seek_started` already cleared it) and then jump to the target when the stream start arrives. An arrow-key press in that window steps from 0 (seeks to ~1 s) instead of from the pending target; a WS drop in the window reissues `play_enhanced` from position 0 instead of the target. UI-level only; audio ends up correct.
- **Suggested Fix**: Frontend. In `sendSeek`, right after `stopPlayback()`, call `core.playbackEngineRef.current?.setSeekOffset(seek.position)` (the tracker already honours a held offset in `'stopped'`, #5860); `audio_stream_start` then re-arms it with the backend's effective position.

#### F8-03: handle_seek's validation rejections omit `command`, so the client cannot roll back `isSeeking` (gap left by #5885)
- **Severity**: LOW
- **Flow**: 8
- **Boundary**: Backend (WS error frame) -> Frontend (`useEnhancedSeek` error subscription)
- **Location**: `auralis-web/backend/ws_handlers/seek_command.py:39` and `:44` -> `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:139-141`
- **Status**: NEW (sibling of closed #5885; the same repo's play validation passes `command=`, see `enhancement_params.py:116,122`, `playback_commands.py:72`)
- **Description**: #5885 added `WebSocketErrorResponse.command` so a client can match a rejection to its optimistic state; the rate-limit path (system.py:140-142) and the dispatcher's `internal_error` path (system.py:~232) pass it. The two validation rejections inside `handle_seek` do not: `send_error_response(websocket, "invalid_track_id", ...)` and `send_error_response(websocket, "invalid_seek_position", ...)` carry `command=None`. The frontend handler returns early unless `message.command === 'seek'`, so `pendingSeekRef` is left set, `isSeeking` is never cleared (no `seek_started` or `audio_stream_start` follows a rejected seek), and the bar (`disabled={... isSeeking ...}`, Player.tsx:148) stays locked with the engine already stopped and the buffer reset by `sendSeek`.
- **Evidence**: backend `seek_command.py:37-45` (two `send_error_response` calls with no `command`); frontend `useEnhancedSeek.ts:139-141`: `if (message.command !== 'seek' || rejected === null) return;`. A non-finite position serialises as JSON `null` (`data.get("position", 0)` returns `None` -> `invalid_seek_position`); the UI guards make this unlikely (`positionFromPointer` fallback is `currentTime`, `keyboardSeekTarget` clamps), but `currentTime` is read straight from the engine clock, so any NaN there reaches the wire.
- **Impact**: Latent stuck "Seeking..." state and dead playback until the next play/stop, for any seek frame the backend rejects at validation. Low reachability from the current UI, but it is the same failure class #5885 set out to close.
- **Suggested Fix**: Backend: pass `command="seek"` at both calls in `seek_command.py` (and, while there, `command="play_enhanced"` for `invalid_preset` at `playback_commands.py:117`). Add a test mirroring `test_ws_malformed_play_commands_5973.py` asserting `command` on the seek rejections.
- **Merged from**: F5-02 (Flow 5 found the same omission of `command` in `handle_seek` validation errors).

#### F8-04: Seek/resume fast path sets the clock offset onto a still-running engine when the buffer epoch collides after a backend restart
- **Severity**: LOW
- **Flow**: 8 (reconnect-resume shares the seek path; overlaps Flow 5)
- **Boundary**: Backend (`audio_stream_start.stream_epoch`, per-process counter) -> Frontend (`bufferEpochRef`)
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:99-105` (`next_stream_epoch`, `itertools.count` per process) -> `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:112-135`, `auralis-web/frontend/src/hooks/enhancement/useStreamSubscriptions.ts:141-143`
- **Status**: NEW (gap in the #5861 / #5860 combination)
- **Description**: On a resume `audio_stream_start` (`is_seek`) the handler discards the buffer and stops the engine only when `shouldDiscardSupersededBuffer(incoming_epoch, bufferEpochRef)` is true (epochs differ). Afterwards it unconditionally calls `setSeekOffset(seekPosition)` (#5860). For a user seek this is right (the engine was stopped by `sendSeek`). For a reconnect resume the engine is deliberately kept alive and playing (usePlaybackTransport.ts:186-194), and its tracker holds `samplesPlayed` accumulated since the engine started. If the epochs are equal the stop/reset branch is skipped, so the clock becomes `seekPosition + samplesPlayed/sr`, roughly double the real position. Equality is possible because the epoch counter restarts at 1 in a new backend process while `bufferEpochRef` is not cleared on disconnect (only `streamEpochRef` is, useStreamSubscriptions.ts:141-143): play one track (epoch 1), restart the backend (dev reload, crash), reconnect-resume yields epoch 1 again.
- **Evidence**: `useEnhancedStreamStart.ts:112` (discard gated on epoch inequality), `:133-135` (unconditional `setSeekOffset(seekPosition)` for `seekPosition > 0`), `PlaybackPositionTracker.getCurrentPlaybackTime` `'playing'` branch `seekOffsetSeconds + samplesPlayed / sampleRate`; `bufferEpochRef` writers: only `useStreamSubscriptions.ts:122` and `cleanupStreaming` (`streamingCoreLifecycle.ts:81`).
- **Impact**: After a backend restart followed by an automatic reconnect-resume, the playback clock/progress bar jumps ahead by the elapsed play time, and the retained pre-reconnect buffer is appended to rather than replaced (replayed audio); auto-advance logic keyed on the clock can fire early. Requires an epoch collision, so rare.
- **Suggested Fix**: Frontend. Clear `bufferEpochRef` (and treat "no known buffer epoch" as discard-needed for `is_seek` starts) in the `!isConnected` effect alongside `streamEpochRef`, and/or only call `setSeekOffset` when the engine is not playing (`!engine.isPlaying()`), otherwise `stopPlayback()` first so the offset and tracker reset stay paired.

#### F9-04: `PlayerState.shuffle_enabled` (and the UI) survive `set_queue` / `clear_queue` after the engine drops its shuffle flag
- **Severity**: LOW
- **Flow**: 9
- **Boundary**: Engine (`QueueManager.clear`) → Backend state manager (`PlayerState.shuffle_enabled`) → Frontend (`queue.isShuffled`)
- **Location**: `auralis/player/components/queue_manager.py:74` → `auralis-web/backend/core/state_manager.py:148-165`, `auralis-web/backend/services/queue_set_mixin.py:179-185`, `auralis-web/backend/services/queue_edit_mixin.py:262-280` → `auralis-web/frontend/src/hooks/player/playerStateSnapshot.ts:131-133`
- **Status**: NEW (the engine half was fixed by closed #5728; #5899/#5936 mirror shuffle into PlayerState only in the shuffle/unshuffle endpoints)
- **Description**: `set_queue` (the play-a-track path) and `clear_queue` call `QueueManager.clear()`, which resets the engine's `shuffle_enabled` to False (#5728). Only `shuffle_queue`/`unshuffle_queue` write `PlayerState.shuffle_enabled`; `PlayerStateManager.set_queue` and `clear_queue` leave it, and no `queue_shuffled{is_shuffled:false}` is sent. The frontend never resets `isShuffled` on its own queue replacement either. Result: three disagreeing sources — engine False, PlayerState True, Redux True.
- **Evidence**: `grep shuffle_enabled auralis-web/backend` shows writers only at `queue_order_mixin.py:150` (`update_state(shuffle_enabled=enabled)`). Snapshots then carry the stale True (`playerStateSnapshot.ts` applies `shuffle_enabled` unconditionally), while `GET /queue` (`useQueueFetch`) carries the engine's False.
- **Impact**: Shuffle shows ON over a queue that is not shuffled (tracks added later append in order). The first toggle sends `enabled:false` → engine "No shuffle to undo" (visible no-op), and only the second toggle shuffles. The displayed state also flips between reconnect snapshots (True) and refetches (False).
- **Suggested Fix**: Backend: have `set_queue` and `clear_queue` record `shuffle_enabled=False` (reuse `_record_shuffle_state`) and emit `queue_shuffled{is_shuffled:false}`; or decide that shuffle is a sticky mode and re-apply it to the new queue.

#### F9-05: `POST /queue/repeat` never reaches the engine, so engine-derived `has_next`/`has_previous` and REST next/previous ignore repeat
- **Severity**: LOW
- **Flow**: 9
- **Boundary**: Backend router → Engine queue
- **Location**: `auralis-web/backend/routers/player_queue.py:147-170` → `auralis/player/components/queue_manager.py:230-231`, `auralis/player/components/queue_navigation.py:54-136`
- **Status**: NEW (closed #6311 made `get_queue_info()` honour `repeat_enabled`; that flag is never set in the live app, so the fix is inert)
- **Description**: `set_repeat_mode` only calls `player_state_manager.update_state(repeat_mode=...)` and broadcasts. Nothing calls `AudioPlayer.set_repeat`/`QueueController.set_repeat` (grep of `set_repeat|repeat_enabled` under `auralis-web/backend` finds only a docstring and the enrichment `pop`). The engine's `repeat_enabled` is therefore always False; `resolve_repeat_mode` papers over this for the `repeat_mode` field by preferring PlayerState.
- **Evidence**: `get_queue_info()` computes `has_next = idx < len-1 or (repeat_enabled and tracks)` from the always-False flag, so `GET /api/player/queue` reports `has_next:false` at the last track under repeat "all" while reporting `repeat_mode:"all"` in the same body. `NavigationService.next_track` → `AudioPlayer.next_track` also wraps only under `repeat_enabled`.
- **Impact**: No effect on the shipped UI (the frontend ignores `has_next`/`has_previous` and never calls REST next/previous; repeat is applied client-side, #5605), so API surfaces contradict each other for any other client and for the dead-but-routed `/next` `/previous`.
- **Suggested Fix**: Backend: in `set_repeat_mode`, also set the engine flag (`await asyncio.to_thread(audio_player.queue.set_repeat, request.mode != 'off')`) or drop `has_next`/`has_previous` from `QueueInfoResponse`.

#### F9-06: Removing the playing/last queue item does not update `PlayerState.state` or position
- **Severity**: LOW
- **Flow**: 9
- **Boundary**: Backend queue service → PlayerStateManager → (cold/reconnecting) frontend
- **Location**: `auralis-web/backend/services/queue_edit_mixin.py:171-186,205-232` and `auralis-web/backend/services/queue_service_base.py:229-243` → `auralis-web/backend/core/state_manager.py:148-170`
- **Status**: NEW
- **Description**: Remove-current follows up only on the engine (`load_file(successor)` — which stops playback via `load_and_stop` — or `playback.stop()` when the queue emptied). The #5460 mirror then calls `PlayerStateManager.set_queue(...)`, which swaps `queue`/`queue_index`/`current_track` but leaves `state`, `is_playing` and `current_time` untouched. `clear_queue`, by contrast, calls `set_playing(False)` and `set_track(None)`.
- **Evidence**: After removing the only playing track: engine stopped, `PlayerState.current_track=None`, but `state=PLAYING`, `is_playing=True`, position ticker task still running (idles because `current_track` is None). After removing a playing track with a successor: `current_track` becomes the successor with the old track's `current_time` and a `PLAYING` state, though the engine is stopped on the successor at 0.
- **Impact**: A client that does not own playback (cold start/reconnect — `applyPlayerStateSnapshot` adopts `is_playing`/`current_time` then) shows "playing" with no track or the successor at the previous track's position. Connected sessions are unaffected (they own those fields, #5898).
- **Suggested Fix**: Backend: when `was_current` is true, `set_track(successor-or-None)` (resets time, state LOADING/STOPPED) and `set_playing(False)` outside the engine lock, mirroring `clear_queue`.

#### F9-07: `unshuffle_queue` "No shuffle to undo" path broadcasts a `player_state` while holding the engine lock
- **Severity**: LOW
- **Flow**: 9
- **Boundary**: Backend queue service → WebSocket broadcast
- **Location**: `auralis-web/backend/services/queue_order_mixin.py:212-222` (`_record_shuffle_state` → `PlayerStateManager.update_state` → `broadcast_state`)
- **Status**: NEW (sibling of closed #4825; introduced with the #5936 fix; the invariant is stated in `_queue_mutation`'s docstring: "The engine lock never covers a broadcast")
- **Description**: In the `not queue_manager.unshuffle()` branch, `await self._record_shuffle_state(False)` and the `return` execute inside `async with self._queue_mutation()`. `update_state` broadcasts a full `player_state` (whole queue) to all WS clients while `_set_queue_engine_lock` is held, so a slow WS client stalls every `set_queue` and queue edit behind that lock.
- **Evidence**: `queue_order_mixin.py:215-222` vs. the normal branch (lines 224-235), which records state after leaving the block; `clear_queue` carries an explicit comment placing its state updates outside the lock for this reason.
- **Impact**: Narrow (only after an edit dropped the shuffle snapshot), but it re-opens the #4825 stall: queue/play commands block on a slow or backgrounded client.
- **Suggested Fix**: Backend: set a local flag inside the block, leave it, then call `_record_shuffle_state(False)` and return the "No shuffle to undo" response.

## Relationships

- **Client stop never reaches the server**: F1-04 (merged F5-01) and F9-01 share one root cause: no WS `stop` is sent on client-side teardown (stop, removed track, clear queue, terminal error). Fixing it in the shared teardown path (`usePlaybackSessionHooks` / streaming core) fixes both; F9-01 additionally needs a transport control that can stop the stream.
- **Seek reject / rollback**: F8-03 (merged F5-02) leaves the client stuck on `isSeeking`; with F8-01 (progress throttled after seek) and F8-02 (clock 0:00 before ack) the seek resume path has three client-side defects that should be fixed together.
- **Stream session state across restart and error**: F1-03 and F8-04 are both gaps in how the epoch / `streamEnded` latch re-arms across a new or recovered stream; F1-02 and F1-01 are timing mismatches between the backend gate/init window and the frontend watchdog/ring.
- **Preset/intensity staleness**: F3-01 (seek after the stream finished delivering uses the old preset) is the seek-side counterpart of open #5076 and of the #5874 re-issue fix; F3-03 (double re-issue) is in the same re-issue path.
- **Engine queue vs `PlayerState`**: F9-02, F9-03, F9-04, F9-05, F9-06 and F9-07 all come from the engine queue and the state manager holding separate copies of shuffle/repeat/index/state; a single post-mutation mirror step in `_queue_mutation` (queue_service_base.py) would cover most of them.
- **Cache freshness**: F5-04 (no revalidation after reconnect), F7-02 (artwork cards never refresh), F2-01 (artwork URL dropped), F7-01 (retag drops the cover) and F6-02 (similarity fit survives a library reset) are the same class - a backend change that the frontend (or an in-process cache) does not learn about.
- **Search**: F2-02 and F2-03 together mean favourites and the client-side overlay can disagree with the server's search.
- **Dead surface**: F5-03 (mastering_recommendation has no subscriber) is of the same class as #5916 / #5887.

## Prioritized Fix Order

1. **F1-01 (HIGH)** - silent PCM drop on a paused client; audio integrity.
2. **F1-03, F1-02** - playback ends or fails to start on recovery / slow processor init.
3. **F9-01 + F1-04** - a stream that cannot be stopped from the UI; wasted server CPU.
4. **F8-01, F8-03, F8-04, F8-02** - seek resume path.
5. **F2-01, F2-04, F2-02, F2-03** - library UI regressions of #5925 / #5866 (cheap fixes).
6. **F9-02, F9-03, F9-04 .. F9-07** - queue/state consistency.
7. **F3-01, F4-01, F6-02, F7-01** - stale data after backend-side changes.
8. Remaining LOW items (docs, perf, typing, dead surface).


## Existing open issues observed (not re-reported)

**Flow 3**

- Existing: #5655 (OPEN) - initial enhancement-status fetch failures are swallowed. Until the WS connect push or GET corrects `INITIAL_STATE.enabled=true`, a play can send `play_enhanced` that the server rejects with `ENHANCEMENT_DISABLED`. The frontend has no handler for that code and treats it as a generic terminal stream error.
- Existing: #5076 (OPEN) - `handle_play_normal` never records `active_stream_settings`, and `_cancel_prior_task` never clears it.
- Existing: #6039 (OPEN) - `player.preset`/`currentTime` etc. are write-only Redux state. The live source of truth is confirmed to be `useEnhancementControl()` local state.

**Flow 4**


- **Existing: #5878** (OPEN, MEDIUM): concurrent scans share one un-keyed frame stream (`max_concurrent_scans` defaults to 4, `models/settings.py:59`), so `library_scan_started` / `scan_progress` / `scan_complete` from two scans flip-flop the single `useScanProgress` store. Still accurate against current code (`scan_events.make_progress_callback` carries no scan id; `handleScanMessage` has one global state).

**Flow 6**


- Existing: #5922 (OPEN, LOW) — the pre-computed K-NN graph is never built automatically and the UI asks `limit=20` while the default `k=10`, so every `/similar` call falls back to the real-time path. Related staleness that belongs under the same issue: persisted edges keep the scores/ranks of the fit and algorithm version they were built under (`knn_graph.py:158-166` stores `result.similarity_score` at build time; `similarity_autofit_worker.py:104-108` notes "an already persisted K-NN graph keeps its old edges until rebuilt"); `use_graph=true` can therefore return neighbours scored on an old normalization.
- Existing: #6346 (OPEN) — mastering-side fingerprint window decision; no similarity-side effect observed.
- Existing: #5708 (OPEN) — `load_file()` fingerprints tracks nothing consumes (engine side of the same queue; not re-traced).

**Flow 9**

- #5937 (OPEN): engine queue pointer never follows frontend navigation. Confirmed still true: no backend path moves `current_index` after client Next/Previous. Root of F9-02's stale value and of shuffle pinning / remove-current anchoring on the wrong track.
- #5960 (OPEN): every `player_state` carries the whole queue. `get_state()` is now a shallow copy (the deep-copy cost is gone) but `_broadcast_state` still `model_dump()`s the full queue each time.
- #6047 (OPEN): `useAppDragDrop` — within-list reorder branch is now tested first, but no `Draggable` feeds it.
- #6082 (OPEN): four unrelated locks serialise track-changing engine ops (`_set_queue_engine_lock`, `_TrackChangeSequencer`, gapless `update_lock`, queue `_lock`).

## Appendix A - Per-flow coverage and verified-OK items

### Flow 1 Track Playback


Boundaries traced on both sides (sender and receiver code read, with line numbers):

1. **Play command (FE -> BE)**: `usePlayTrack.ts` (REST queue POST then `startTrack`) -> `useEnhancedPlayCommand.ts` (`play_enhanced` / `play_normal`, fields `track_id`, `preset`, `intensity`; `start_position` only on reissue/reconnect) -> `ws_handlers/connection.py::dispatch_message` -> `playback_commands.py` (`parse_play_request`, `resolve_enhancement_params`, `_cancel_prior_task`, fresh pause/flow events) -> `routers/system_streams.py`. Rate limiter exempts `buffer_full`/`buffer_ready`/`pong`. Field names and units match (snake_case on the wire).
2. **Stream skeleton**: `stream_enhanced_lifecycle.run_enhanced_stream` (semaphore, cancel event, track resolution, processor init timeout, teardown) shared by `stream_enhanced.py` / `stream_seek.py`; `stream_normal.py` for `play_normal`. Teardown and cancel ordering (#3828/#4815/#6292) intact.
3. **Chunk geometry / tiling**: `chunk_boundaries.py` (15 s / 10 s / 5 s; `content_chunk_count`), `chunk_boundary_manager.trim_context`, `chunk_segment_extraction.extract_chunk_segment`, `chunk_file_loading`, `chunk_render`/`chunk_render_miss`/`chunk_streaming`. Verified analytically that chunk 0 emits [0,15), chunk k emits [10k+5, 10k+15), the last chunk emits [10(n-1)+5, T), and `content_chunk_count` guarantees the penultimate chunk is full and the last non-empty; no gap, overlap or repeated samples at seams. Seek geometry (`chunk_for_position`, `emitted_chunk_start`, first-chunk trim in frames) is consistent with it. Mono (N,1) and 6-channel inputs through `HybridProcessor.process` were run: shape and dtype are preserved (float32, same length).
4. **Sample-rate / channel consistency**: probe (`chunk_metadata`, `get_audio_info`) -> `audio_stream_start.sample_rate/channels` -> `AudioContext({sampleRate})` -> `PCMStreamBuffer` -> worklet. FFmpeg decode keeps native rate (`-ar source_sample_rate`) and downmixes >2 ch to stereo, advertised via `decoded_channel_count` (#5709). Frame counting is in frames (not interleaved samples) in worklet, `PlaybackPositionTracker` and `stream_end.total_samples`.
5. **Wire format**: `send_pcm_chunk` (JSON `audio_chunk_meta` + raw little-endian float32 binary, <= ~300 KB per frame, monotonic `seq`, `stream_epoch`, `track_id`) <-> `socketFrameParser.handleSocketFrame` (`binaryType = 'arraybuffer'` set in `errorHandling.ts:103`, so the Blob branch is not reached; pendingMeta captured/cleared synchronously) <-> `decodeAudioChunkMessage`. `stream_start/end/error` payloads match `types/ws/streaming.ts` field for field (`stream_epoch`, `is_seek`, `start_chunk`, `seek_position`, `reason`, `continues`, `recovery_position`).
6. **Epoch / supersession handling**: per-stream epoch stamped on start, chunk meta, end and error; `classifyChunk`, `shouldDiscardSupersededBuffer`, `isSupersededEpoch`, `isSupersededTrack`; stale frames from a replaced stream are dropped (verified for the rapid-skip path: they queue in `pendingChunksRef` and are dropped on the new start by epoch).
7. **Flow control**: `buffer_full` at >75%, `buffer_ready` at <50% via ingest and via `flowDrainWatch` (250 ms poll, registered in `useAudioStreamingCore`), bounded server gate in `stream_gates.py` (finding F1-01 is about its interaction with a paused client).
8. **Playback engine**: `AudioPlaybackEngine`, `BufferScheduler`/`WorkletOutput` (seconds-based start gate via `minBufferSeconds`, 5 s/8 s water marks over ring + worklet queue, 3 s lookahead feeder), `public/audio-worklet-processor.js` (underrun reporting, frame-exact progress), `PlaybackPositionTracker`, end-of-stream tail handling (`markStreamEnded`, `startPlaybackWhenBuffered` short-stream start).

Regression guards verified still in place (no regression found):
- #5863 / `3a1ab313`: `flowDrainWatch.ts` present and registered in `useAudioStreamingCore.ts:150-156`; `stream_gates.py` bound present; `tests/backend/test_flow_gate_bound_5863.py` and `flowDrainWatch.test.ts` exist.
- #6232 / `a3488cff`: start gate in seconds (`minBufferSeconds: 1.0` via `BufferScheduler.getMinBufferSamples`), watchdog derived from `BACKEND_STREAM_TIMING` (the derivation holds; the mirror is incomplete: F1-02).
- #5867 / `0121aaca`: `message.data.continues === true` keeps engine and buffer (`useStreamMessageHandlers.ts:153-156`); backend sends `continues: True` on the skip path (`stream_notifications.py:58-59`, `stream_enhanced_chunks.py:271-280`); `chunkError.5867` test exists.
- #5900 / `4b261747`: `shortStream = engine.hasStreamEnded() && available > 0` in `startPlaybackWhenBuffered`; `AudioPlaybackEngine.start` honours `streamIsComplete`; `shortStreamStart.5900` test exists.
- #6017 / `cde03344`: `isSupersededTrack` guard in `handleStreamEnd`/`handleStreamError`; reducers also drop mismatched `trackId`; `supersededTrack.6017` test exists.
- #5876 / `b65f5759`: `streamActive` / `endActiveStream` gate reissue and reconnect replay; `sessionEnd.5876` test exists (F1-03 is a gap in how the new stream re-arms it, not a removal of the guard).
- #4642 (no crossfade): no crossfade code at the seams in `stream_chunk_ops.py` or `PCMStreamBuffer.ts`.

Verified-OK items (examined, no defect found):
- Frame pairing: Blob path capture-and-clear is synchronous; `audio_stream_error` clears a stale `pendingMeta`; `resetStreamFrameTracking` on reconnect.
- `seq` desync detection resets per `stream_epoch`; backend seeds a fresh cell per stream and mutates it across the gathered producer's copied context.
- Cancel/seek ordering: `handle_play_enhanced`/`handle_seek` await the prior task before registering fresh pause/flow events, so no stale event is reused; a stale `flowPausedRef` after a seek self-heals (spurious `buffer_ready`).
- Look-ahead is processed strictly in stream order, so serve-time `LevelManager` smoothing sees chunks in order; the sample-count invariant is enforced in `AudioProcessingPipeline.apply_enhancement`.
- Short last chunk / decoder-short source (#6345): last chunk no longer padded; `trim_context` keeps the core measured from its start.
- Auto-advance keys off `streamingState === 'complete' && currentTime >= trackDuration - 0.5`; library duration is now probed the same way as playback (#6134), so a duration mismatch does not strand the advance.
- Idle edge cases noted but not filed (not provable as defects): channel counts that do not divide the 76,800-sample frame (7 channels) would split a PCM frame across WS frames; the ring would transiently hold a non-multiple of `channels`. A startup low-water pause (feeder holds at 1-8 s buffered) briefly reports a stall at every track start; intentional hysteresis.

### Flow 2 Library Browsing


Boundaries traced (both sides, current source):
- Frontend hooks → API client: `useLibraryQuery` + `useLibraryQueryFetchers` + `libraryQueryRequest` (artists), `useLibraryPagination` + `libraryPageFetch` (tracks/favourites), `useInfiniteAlbums` (albums), `useAlbumDetails`, `useArtistDetailsData` + `libraryService`, `playlistService` + `usePlaylistDetails`, `useLibraryStats`, `useLibraryChangeSync`.
- REST routers → repositories: `tracks.py`, `albums.py`, `artists.py`, `playlists_crud.py`, `library.py` → `TrackRepository` (search/get_all/get_favorites), `AlbumRepository`, `ArtistRepository` + `artist_page.py`, `PlaylistQueryMixin`/`PlaylistCrudMixin`, `StatsRepository`.
- ORM `to_dict()` → `serializers*` → Pydantic response models (`schemas/library.py`, `artists_models.py`, `albums_models.py`, `playlists_models.py`, `library_models.py`) → frontend wire types (`api/transformers/types.ts`) → transformers → domain types; runtime guards in `api/responseGuards.ts`.

Verified OK (regression guards from the flow text):
- Shared `PaginatedResponse` envelope on tracks/albums/artists lists; `paginated()` and `compute_has_more()` are the single builders; frontend reads only snake_case `has_more` (`deriveHasMore`, `libraryPageFetch`, `transformAlbumsResponse`) (#5499, #5823).
- Sort is server-side with `order_by` + `order`, NULLs last, NOCASE, id tie-breaker (`base.sort_terms`); `CozyAlbumGrid` maps every sort mode to a server order and does not re-sort loaded pages (#5868/#5869). The only client reordering is `useGroupedArtists` letter grouping, which is consistent with the server's order.
- Absent album/artist is `null` on the wire (`Album.to_dict` → `artist: None`, `TrackInArtist.album: str | None`); wire types admit `| null` for album year/artist/artwork, similar-track and TrackInfo fields; frontend normalises at the transformer (`UNKNOWN_ARTIST_LABEL`, `?? ''`, `duration ?? 0`) (#5905, #6049).
- Detached-ORM safety: every list/detail path uses named eager-load tuples or SQL aggregates (`_track_eager_options(list_read=True)`, `_ALBUM_LIST_OPTIONS`, `_ARTIST_LIST_OPTIONS` + `_attach_genre_names`, `_PLAYLIST_DETAIL_OPTIONS`), `to_dict()` uses `_safe_collection/_safe_scalar`; response models list every key `to_dict()` emits (no silent field stripping).
- Pagination bounds agree: backend `limit` 1..200 / `offset` ≤ MAX_SQLITE_INT; frontend `LIBRARY_PAGE_LIMIT=50`, `LIBRARY_MAX_PAGE_LIMIT=200`; refresh paths read pages in whole-page multiples and report `offset` as the start of the last page consistently with `fetchMore`.
- Response shape guards (`isTracksListShape`, `isAlbumsListShape`, `isArtistsListShape`, `isArtistDetailShape`, `isAlbumTracksShape`, `isArtistTracksResponseShape`, `isPlaylistsListShape`, `isCreatePlaylistResponseShape`, `isLibraryStatsShape`) are applied on every list and detail call in this flow; no raw-cast JSON found.
- Stale/out-of-order protection (`useLatestRequestGuard`, `useSupersedingAbort`, abort-on-unmount) present on all list fetchers; error states keep loaded rows on a failed later page (#5870); album grid stays in TanStack cache and is invalidated by `useLibraryChangeSync` (#5871).
- Large libraries (100k+): all tracks/albums/artists lists are server-paginated with COUNT queries and virtualized rendering (`TrackListViewContent`, `VirtualizedAlbumGrid`, `ArtistListContent`); artist list/page avoid hydrating Track rows (#5084, #5872). `library_updated` is only broadcast on scan/removal completion, so the "re-read all loaded pages" refresh is not storm-prone.
- `LibraryStatsResponse` keys match the TS `LibraryStats`.
- Artist artwork external URLs vs CSP `img-src` allowlist still wired (#4526); album artwork is an `/api/albums/{id}/artwork` URL.
- Timeouts: shared `apiRequest` (DEFAULT_TIMEOUT_MS, status-0 for connection/timeout failures) is used by every hook in the flow; 4xx/5xx map to `ApiErrorHandler` / friendly errors.

Not reported (judged by design or already tracked): tracks list defaulting to `created_at` ascending (backend default, no frontend `order_by`); genre not searchable although `TrackRepository.search` docstring mentions it; `GET /api/albums/{id}` has no frontend caller.

### Flow 3 Audio Enhancement

Boundaries checked:
1. UI -> `useEnhancementControl` state: toggle/preset/intensity commands, in-flight guards, stale-request guard, optimistic apply. Single live source of truth confirmed.
2. REST: `POST /api/player/enhancement/{toggle,preset,intensity}` and `GET /status` (request models, `response_model`, DB persistence, in-place dict mutation, broadcast payload); `PUT /api/settings` and `POST /api/settings/reset` -> `seed_enhancement_settings` -> broadcast. Field names are snake_case on both sides with no case conversion needed. Null/optional handling is consistent.
3. WS: `enhancement_settings_changed` payload and the connect-time push (backend `connection.py` vs `types/ws/enhancement.ts`); `play_enhanced`/`play_normal`/`seek` command shapes (`types/ws/commands.ts` vs `playback_commands.py` / `seek_command.py` / `enhancement_params.py`); `audio_stream_start` preset/intensity echo; mid-stream `enabled` re-check (`stream_enhanced_chunks.py`).
4. Re-issue / resume: `reissueActiveStreamAs`, `replayQueueAndResume`, resume getters registered for both stream types, `endActiveStream` and the `stopped` vs `completed` semantics.
5. Engine boundary: preset and intensity through `ChunkedAudioProcessor` -> `AudioProcessingPipeline` (dry/wet blend, sample-count invariant) -> `ProcessorFactory` (intensity is not in the processor key by design, #4707). The chunk cache is wiped on every start (`config/startup/tempfiles.py`), so the DSP changes of 2026-11-17 do not leak stale chunks. The web path does not use `auralis/player/realtime`, so there is no real-time/offline split to reconcile.

Verified OK: preset contract parity; intensity range/NaN validation on all three surfaces; Settings-slider step (0.1) matches the 0.1 cache bucket, so the displayed value equals the rendered value; persisted/runtime/UI sync for toggle/preset/intensity; pause is client-side only, so a re-issue while paused works; reconnect resume uses the refreshed `lastStreamCommand`; WS-vs-REST stale-read protection on the status GET; no off-list preset write path exists (repository whitelist plus Literal validation).

Minor observation, not filed: `ENDPOINTS.ENHANCEMENT_{TOGGLE,PRESET,INTENSITY}` in `config/api.ts:99-101` have no consumers, because `useEnhancementCommands.ts` and `useEnhancementStatusSync.ts` hard-code the URL strings.

### Flow 4 Library Scanning


Boundaries checked, sender and receiver, with line-level reads:

1. **Frontend trigger -> REST.**
   - `useLibraryScan.ts` posts `{directories:[folder]}` to `/api/library/scan` with `SCAN_TIMEOUT_MS` and an AbortController. Settings "Scan Now" (`triggerLibraryScan`) posts `{directories, recursive, skip_existing}` with the same timeout and no abort signal.
   - Both match `schemas/library.py:LibraryScanRequest`. Field names and defaults agree, and the schema validator resolves and validates the paths.
   - 409, 429, 499, 500 and 504 all map to `describeScanError`. FastAPI and custom 422 shapes are rendered by `utils/httpError.ts`.
2. **Streaming allowlist (#5865, guard).** `useLibraryScan.ts:110` registers the folder via `POST /api/settings/scan-folders` alongside the scan (failure non-fatal). The backend `add_scan_folder` calls `register_allowed_directory` and `_notify_scanner`. Verified in place.
3. **REST -> scanner threading.**
   - `scan_library` runs `scan_directories` via `to_thread`; `_await_scan` races the scan, the timeout and `http.disconnect` (awaiting `receive()`, not polling).
   - `stop_scanner` signals the shared `threading.Event`; the scanner's `finally` releases the slot and path reservation. Timeout, cancel and client-gone each emit a terminal `library_scan_error`; a 409 does not emit one (so it cannot wipe the running scan's UI, #4602).
4. **Scan failures reach the UI (#5877, guard).**
   - Unreadable roots or subfolders (`FileDiscovery._root_failed` / `_directory_error`, depth limit) go to `ScanResult.directory_errors`. Unexpected exceptions go to `ScanResult.error` (class name only).
   - The REST route answers 500 on `error` and returns `directory_errors` in `ScanResultResponse`. The WS path sends `library_scan_error` on error and `scan_complete.directory_errors` otherwise. The frontend surfaces `lastError`, `unreadableFolders`, and an error toast.
   - `walk_complete` (no directory errors and no error) gates `prune_missing_tracks` on both paths. A stopped scan never reaches prune.
5. **Both paths report the scanner's own `files_processed` (#5912, guard).** `scan_complete_payload` is the single builder used by both emitters. Verified. Pinned by `test_scan_complete_payload_5912.py`.
6. **Progress frames.**
   - Frames: `started` (turned into `library_scan_started` with normalized dirs), `counting` (running tally, `percentage: null`), `discovering` and `processing` (real fraction via `scan_progress_percentage`).
   - Payload `{current,total,percentage,current_file,phase}` equals `ScanProgressPayload` and `ScanProgressMessage`. The `phase` union includes `counting`. `current_file` falls back to the directory and the card uses `pathBasename`.
   - The thread-to-loop bridge (`call_soon_threadsafe` plus a done-callback) keeps frame order before the terminal frame. I traced the task ordering and found no path for a late `scan_progress` to re-arm `isScanning` after `scan_complete`.
7. **WS lifecycle on the client.**
   - The `useScanProgress` single refcounted subscription handles `library_scan_started`, `scan_progress`, `scan_complete`, `library_tracks_removed` and `library_scan_error`. `lastError` is cleared on the next start or complete.
   - The reconnect resync (`GET /api/library/scan/status`) is epoch-guarded against late frames (#6101). It has its own rate-limit bucket (30/min) via longest-prefix matching (#5911). `is_scanning()` is a live read of the slot counter.
8. **Duplicate detection / rescan.**
   - `get_by_path` and `add()` both key on `filepath_key`, so the case-insensitive platform key is consistent.
   - The skip rule compares mtime (tolerance) and size against `file_mtime`/`filesize` (#5574, #5748). `skip_existing=False` updates rather than re-adds (#6146).
   - Moved files are relocated only on an unambiguous size+duration match with a provably-missing old file (#5880).
   - Concurrent scans of the same or nested directories are rejected by the real-path ancestry reservation (#6097), and the slot is released on the rejection path (#4330).
9. **Prune safety.** `cleanup_missing_files` uses ENOENT/ENOTDIR-only `os.stat` semantics, double-checks before delete, and skips tracks whose parent directory is gone (unmounted volume). The one residual (a track directly inside an empty mount-point root) is documented in `track_missing_files.py` and is not a new finding.
10. **Metadata -> DB insert.**
    - `audio_info_to_track_info` keys match `TrackRepository.add()` (`filepath`, `title`, `duration`, `sample_rate`, `channels`, `format`, `filesize`, `file_mtime`, `artists`, `album`, `album_artist`, `genres`, `track_number`, `disc_number`, `year`).
    - Tag caps, track-number cap, UTF-8 filename failure, undecodable-file refusal and oversize-probe refusal all surface as named per-file failures. Failure payloads are reduced to `filename` plus a redacted reason (`ScanFailure.to_dict`, #5341, #5749).
11. **Auto-scanner.**
    - It uses the same bridge, enqueue helper and `scan_complete_payload` as the manual path. A rejected cycle sends no frames (#5465), and the trigger event is consumed before the settings read (#5881).
    - Watchdog events are debounced 500 ms and filtered. Shutdown stops the scanner thread via `stop_scanner`. Crash-loop frames are redacted to the exception class.
12. **Timeouts / large folders.** Streaming batches of 50, with the path cache capped at 100k and a fallback to a second walk. Counting frames every 250 files. Backend bound 3600 s with 504 plus a terminal frame; frontend bound just above it (see F4-02 for the override caveat).
13. **Case/units.** WS and REST payloads are all snake_case on the wire (`files_added`, `directory_errors`, `directories_scanned`); the frontend types and consumers use the same keys. `duration` is seconds in both REST and WS (#3839 guard holds). `percentage` is 0-100 or null.

Verified-OK regression guards from the brief: #5877 (directory errors / aborted scans reach the UI; incomplete walk never prunes), #5912 (shared payload), #5865 (allowlist registration), duplicate detection on rescan, and large-folder chunking.

Noted but not reported, because each is benign or deliberate:
- The manual route never sets `scanner.set_scan_complete_callback`, so the reference-cloud refresh only runs after auto-scans. The fingerprint-queue drain hook also refreshes the cloud, which is the useful trigger.
- `EmptyLibrary` ignores the dropped path (`onFolderDrop={() => onScanFolder()}`) and opens the picker. This is a UX choice, since a browser drop yields a virtual path.
- Client cancel and unmount emit `library_scan_error: "library scan cancelled"`, shown as "Last scan failed". This is by design (#4820).

### Flow 5 WebSocket Lifecycle


Boundaries traced (sender and receiver, with current line numbers):

1. **Handshake / accept / limits**: `routers/system.py:56-193` (endpoint, `add_api_websocket_route`, per-connection finally) ↔ `config/globals.py:91-167` (`ConnectionManager.connect`: origin allowlist, empty-Origin loopback rule, `WS_MAX_CONNECTIONS` checked under the lock after accept, 1013) ↔ `ws_handlers/connection.py:109-181` (`setup_connection`, heartbeat task spawn, initial `enhancement_settings_changed` + `player_state` pushes) ↔ frontend `WebSocketManager` (`utils/errorHandling.ts`), `useWebSocketConnection.ts`, `websocketConnectionLifecycle.ts`.
2. **Inbound pipeline**: `receive_text_frame` (binary answered with `unsupported_frame_type`), `validate_and_parse_message` (size, JSON depth, schema, type whitelist), per-type limiter order (ping own budget, exempt types `pong`/`heartbeat`/`buffer_full`/`buffer_ready`, enum-vs-frozenset membership checked live), `dispatch_message`, per-handler exception isolation (#4771).
3. **Command contract**: frontend `OutgoingCommand` union (`types/ws/commands.ts`) ↔ backend `WebSocketMessageType` + handler reads (`playback_commands.py`, `seek_command.py`, `enhancement_params.py`, `playback_control.py`); field names, types, `start_position` clamping (`chunk_boundaries.py:183`), `force` boolean, preset/intensity precedence all match.
4. **Outbound contract**: all 26 `BroadcastMessageType` literals (`outbound_messages.py:70-97`) are present in `ALL_MESSAGE_TYPES`; per-socket frames (`playback_paused/resumed/stopped`, `seek_started`, `audio_*`, `fingerprint_progress`, `error`) match `types/ws/*` shapes including `seq`, `stream_epoch`, `reason`, `continues`, `command`; WEBSOCKET_API.md lists every type.
5. **Binary framing**: `send_pcm_chunk` (meta text frame then bytes, per-stream `seq` cell, `stream_epoch`, bounded producer/consumer queue, 300 KB frames) ↔ `socketFrameParser.ts` (pendingMeta pairing, seq desync check reset per epoch and on reconnect, stale-meta clear on `audio_stream_error`, `binaryType='arraybuffer'`).
6. **Timing policy**: `WS_HEARTBEAT_INTERVAL_SECONDS=30` / `TIMEOUT=10` with decoupled ping/stale deadlines (`run_heartbeat_loop`), client pong reply (`socketFrameParser.ts`), client `heartbeat` every 30 s (`mark_alive`), `ws_max_size` transport bound (`main.py:124`), reconnect budget constants shared (`config/timing.ts`, `connectionSlice`, manager default).
7. **Reconnection**: manager backoff and 1008 permanent-close handling, singleton reuse/joining, `replayQueueAndResume` (queue flush, `resetStreamFrameTracking`, `streamActive` gate, `positionRefreshedOnReplay` re-read), epoch-forget on disconnect, engine kept alive across a drop with buffer discard on the new epoch, `useReconnectOnNetwork`, `server_instance_id` watermark reset (`playerSyncWatermarks.ts`), `wsBaseFromApiBase`.

Regression guards verified present and consistent (no regression): rejected Origin accepted-then-closed 1008 (#5883, `globals.py:104-116`); invalid/binary frames metered via `may_reply` and transport size bound (#5915); malformed play/seek typed errors and `data: null` handling (#5973); `ping` own budget (#5079/#4786); `track_loaded` informational and documented (#5708 stays open, not re-reported); `metadata_*` consumed by `useLibraryChangeSync` and no `undo` action (#5916); `OutgoingCommand` union (#6050); `useMessageSubscriptions` as the shared subscribe lifecycle with `usePlayerStateSync`/`usePlaylistWebSocket` on it (#5789/#6041; the only hand-rolled subscribers are the deliberately refcounted `useScanProgress` and `useArtworkUpdates`, neither keyed on connection status); `server_instance_id` resets watermarks in the snapshot handler (#5882); queued stream re-issue refreshes `start_position` (#6044); `useReconnectOnNetwork` retries after give-up (#5917); `VITE_API_URL`-derived WS base (#5654); stream teardown through one `detach_stream` helper at play/seek, stop and disconnect (#6292); `stream_epoch` stamped on `audio_stream_start`/`audio_chunk_meta`/end/error and filtered client-side (#5861); `chunk_cancel_events` removed by identity so a successor's token is not popped (#4815).

Verified-OK / disproved candidates (not findings):
- Initial snapshot ordering: subscriber effects (children) run before `WebSocketProvider`'s connect effect, so the on-connect `player_state` is not missed.
- `str`-enum `type` membership in the exempt frozenset works on this interpreter (tested), so the pong/buffer_* exemptions are live.
- A flow-parked stream whose `buffer_ready` is lost resumes after 30 s at one chunk per gate wait (the event stays clear), so it cannot flood the client's ring buffer.
- Pending chunks received with no initialised stream are bounded (`MAX_PENDING_CHUNK_FRAMES`).
- `useWebSocketConnection.connect()` increments `connState.refCount` on every call, including via `useReconnectOnNetwork` retries, so after a retry an unmount would not close the singleton; the provider is the app root and never unmounts in production, so this was not raised.
- Accept-then-close with 1013 (connection cap, broadcast eviction) fires `onopen`, which resets the manager's retry counter; with a 16-socket cap and one client this loop is not reachable in practice, so not raised.

### Flow 6 Fingerprint & Similarity


Boundaries checked (sender and receiver, with line numbers):
- Frontend `useSimilarTracks` / `similarityCache` / `similarityErrorState` / `SimilarTracksModal` / `useSimilarTracksModal` <-> `GET /api/similarity/tracks/{id}/similar` (`similarity_query.py`, `similarity_models.SimilarTrack`, `similarity_common.require_fingerprinted_tracks`).
- Frontend `useTrackFingerprint`, `useAlbumFingerprint(s)`, `FingerprintCoverageCard` / `useFingerprintCoverage`, `useFingerprintStatus` <-> `fingerprint_status.py`, `albums_fingerprint.py` (+ `albums.py:210-216` route order), `fingerprint_queue.py`, WS `fingerprint_progress` (`stream_fingerprint.py`, `stream_notifications.py`, `types/ws/enhancement.ts`).
- Backend -> engine: `FingerprintSimilarity` (fit / needs_refit / calibrate / find_similar / calculate_similarity), `FingerprintNormalizer`, `FingerprintDistance` (weights order == `TrackFingerprint.to_vector()` == `schema.DIMENSION_NAMES`), `KNNGraphBuilder`, `SimilarityGraphRepository`, `FingerprintQueryMixin` / `FingerprintSimilarityMixin` (`_current_fingerprint_clause` applied on every read), `FingerprintCrudMixin.add/update` (version stamping), on-demand `FingerprintGenerator` + `FingerprintQueue`, batch `FingerprintExtractionQueue` phases, `FingerprintService`.
- Startup wiring and lifecycle: `config/routes.py:250-268`, `config/startup/fingerprint.py`, `SimilarityAutoFitWorker`, `config/background_workers.py`, reset route (`routers/library.py`).
- Rate limit prefix `/api/similarity` (20/60 s) against the modal's request pattern.

Verified OK:
- Regression guards present and intact: #5889 (`fit` forwards `min_samples`, a False result is a 503, `similarity_explain.py:127-129`); #5945 (class-level non-blocking `_busy` lock, 409 `GraphBuildInProgress` on build and clear); #5381 (`OperationalError` -> 503 in the similarity-family decorator); #5873 (album grid reads one batched request, route registered before `/api/albums/{album_id}`, frontend batcher chunks 100 ids against the 200 cap and sends repeated `ids=`); #5518/#5267/#5919 (queued vs not-queued wording, `enqueue` boolean honoured, `fingerprint_progress` reports `failed` when nothing queued); #4822/#5891 (current-version clause on every read, status counts only usable rows); #5715/#5471 (prefilter ordered by distance to box centre, `bass_pct` tolerance 0.08); #5892 (fallback to full search when the box holds fewer than n); #4864 (graph answer shorter than `limit` falls back to real-time); #5923 (calibrated reference distance used on `/similar`, `/compare`, `/explain` and stored edges); #5057 (NaN distance -> score 0.0, response bounds hold); #4656 (`None` similarity system -> 503); #5890 (graph builder is published by the autofit re-check within `_CHECK_INTERVAL_SECONDS`; the 503 text says so).
- Fingerprint format: 25 dimensions in one order across schema, model `to_vector`, normalizer, weights and distance; response key renames (`pitch_confidence`, `chroma_energy_mean`, `stereo_correlation`, bands without `_pct`) are identical on the track and album endpoints and match the frontend `AudioFingerprint` interface; centroid/rolloff are served in Hz and the frontend gradient/descriptor code expects Hz; band fractions are 0-1 on both sides.
- Similarity scores: always in [0,1] (calibrated clip), `distance` finite float, `rank` 1-based in both graph and real-time paths; frontend renders `score * 100` and treats `rank`/`title`/`artist`/`album` as nullable.
- Missing fingerprint: 404 with distinguishable detail ("Queued..." / "Not queued...") enqueued through `asyncio.to_thread`; frontend classifies queued / queue-rejected / initialising / not-found and polls `useTrackFingerprint` with an error-first stop rule and a 36-poll cap.
- Detached-ORM rule: `get_similar_tracks` reads `t.artists[0]` / `t.album.title` from `tracks.get_by_ids`, which applies `_track_eager_options()`.
- On-demand vs batch write path: both stamp `FINGERPRINT_ALGORITHM_VERSION` (`add`/`update`/`upsert`), both go through `compute_windowed_fingerprint` (finite check, 25-key completeness).
- Case conversion: `use_graph`, `include_details` query params serialize as `true`/`false`; response bodies are snake_case and converted explicitly in the hooks.
- Known design bounds not reported: real-time fallback ranks only the 5000 most recent fingerprints (#3705); on-demand `FingerprintGenerator.TIMEOUT` cannot reclaim a worker thread (documented, #4377).

### Flow 7 Artwork


Boundaries traced (sender and receiver, current source):
- Frontend URL builders (`services/artworkService.ts`, `AlbumCard`, `AlbumArt`, `TrackRow`, `TrackCard`, `Player`, `useArtworkPalette`, `MediaCardArtwork`, `useTrackImage`, `ProgressiveImage`/`useProgressiveImageLoader`) -> `GET /api/albums/{id}/artwork[?size&v]` (`routers/artwork.py`).
- Router -> repository (`AlbumArtworkLookupMixin.get_artwork_path`, single-column, #5896) -> path validation (resolve + `is_relative_to(artwork_dir)` before exists) -> MIME detection (extension then magic bytes) -> `_get_or_create_thumbnail` -> ETag/304 -> `FileResponse`.
- Thumbnail cache (`artwork_thumbnails.py`, `core/thumbnail_cache.py`): key = path-hash + bucket + source mtime_ns + size + ext; purge and render share `thumb_path_hash`; purge resolves sources the same way the render path does; per-key render lock with waiter-counted retirement; per-writer `mkstemp` temp + atomic `replace`; orphan temp reaping; 128 MiB backstop prune; `clear_all_caches` clears thumbnails only (source art kept) and library reset clears both.
- Write paths: `ArtworkExtractor` (embedded ID3/MP4/FLAC/ASF/APE/Vorbis, folder art with symlink/special-file refusal, front-cover preference), `ArtworkDownloader` (MusicBrainz CAA / iTunes, redirect-hop validation, bounded read, shared dimension cap, sniffed extension), `extract`/`download`/`delete` routes (previous path read before overwrite, both-path purge, idempotent DELETE, `artwork_updated` broadcast via the shared `_broadcast_artwork_updated`).
- WS `artwork_updated`: backend `ArtworkUpdatedPayload` (action, album_id, optional artwork_url) matches frontend `ArtworkUpdatedMessage` (types/ws/enhancement.ts:72-79); single refcounted subscription store (`useArtworkRevision`).
- Serializers: `Album.to_dict` / `Track.to_dict` / `create_track_info` emit `/api/albums/{id}/artwork` only when the album has art (#5528 holds); `AlbumInArtist.artwork_url` populated (#5925 holds) and `AlbumsTab` uses it for `hasArtwork`; artist `artwork_url` is the documented external-CDN exception with CSP `img-src` allowlist.
- Cross-cutting: NoCacheMiddleware leaves `/api` untouched so the route's `Cache-Control: public, no-cache` + ETag stands; RateLimitMiddleware has no artwork rule; the IO default executor carries the `to_thread` calls.

Regression guards verified present and effective: #6153 (decompression-bomb rejection at write via `bound_artwork_dimensions`/`_save_artwork` and at serve via `open_bounded_image` -> 404 in `_get_or_create_thumbnail`), #5927 (`upright_with_profile` bakes EXIF orientation, keeps ICC, drops CMYK profile), #5925 (artist album artwork_url), #5894 (AlbumCard/TrackRow revision fallback), #5895 (player bar 88 px variant + revision), #5896 (single-column lookup), #4532/#4527/#5255 (purge, per-writer temp, cap), #5337/#5330 (https-only + per-hop redirect validation), #4850 (superseded file unlink), #3563 (idempotent DELETE).

Verified OK / notes (not findings):
- Every frontend `size` (64, 80, 88, 216, 256, 280, 40) snaps to a bucket (64/128/256/512); no request bypasses the cache, and all are inside the `ge=16, le=2048` validator. Sizes above 1024 would still return a 1024 px image, but the frontend never requests them.
- Cache headers agree with cache invalidation: ETag comes from the served file's stat, the thumbnail key embeds source mtime/size, so an edited source yields a new key and a new ETag; the only redundant revalidation is a new ETag after FIFO eviction and re-render (same bytes).
- Observation, not reported: `AlbumCard` asks for 256 px for slots that `minmax(216px, 1fr)` can stretch to roughly 216-300+ CSS px (more on HiDPI), while `TrackRow` and the player bar explicitly request 2x; it is a policy choice, not a miss.
- Observation, not reported: `AlbumArt` (album header, search avatars) requests the URL unconditionally and 404s for albums without art, the remaining probe pattern of #5925; the fallback gradient handles it.
- Observation, not reported: the artist-artwork CSP allowlist is narrower than `TRUSTED_ARTWORK_DOMAINS` (archive.org, coverartarchive.org, mzstatic.com and subdomains of the listed hosts are accepted by the validator but not by `img-src`); the source comment documents this as a KNOWN LIMITATION and forbids loosening it, and artist artwork is only fetched by the CLI.
- Observation, not reported: the artwork GET still does `resolve()/exists()/stat()` inline on the event loop (cheap local syscalls; #5972 targeted `validate_file_path`).

### Flow 8 Seek & Rebuffer


Boundaries traced (both sides, with line numbers):
1. Scrubber / keyboard -> `seekTo`: `useProgressBarDrag.ts`, `useKeyboardSeek.ts`, `progressBarMath.ts`, `PlaybackSessionContext.handleSeek` -> `useEnhancedSeek.sendSeek` (WS `seek`, `{track_id, position}` in seconds; preset/intensity omitted, #5604).
2. WS `seek` -> backend: `routers/system.py` receive loop (size/schema validation, 10 msg/s limiter, `rate_limit_exceeded` + `command`), `ws_handlers/seek_command.py::handle_seek`, `_cancel_prior_task` (pop under lock, cancel + await outside it), pause/flow event reset and task registration under `active_tasks_lock`, live `enabled` re-read (#5075), `stream_from_position` routing enhanced vs normal.
3. Seek stream: `stream_seek.py` -> `chunk_for_position` (overlap-aware, `emitted_chunk_start`, clamp to `duration - 0.5`, sliver advance, effective position), `send_stream_start` (always `is_seek`, `seek_position` = effective, `seek_offset`, `start_chunk`, `stream_epoch`, per-stream `seq` reset), `pump_chunks` (look-ahead, first-chunk trim `round(seek_offset*sr)`, recovery_position, DSP-timeout abort, drain of look-ahead in `finally`), `send_pcm_chunk` framing with epoch and seq stamps, `send_stream_completion`.
4. Chunk geometry: `chunk_boundaries.py`, `chunk_segment_extraction.py`, `chunk_file_loading.py` (emitted segments tile; chunk 0 = 15 s, later = 10 s, last chunk short; seek offset never exceeds the emitted length of its chunk for non-last chunks).
5. Level continuity: `LevelManager`/`level_transition.py` (first chunk of a fresh processor establishes a baseline; serve-time smoothing per stream; cache holds raw segments, #5948).
6. Normal-mode seek: `stream_normal.py` + `normal_stream_plan` (clamp #5409, round() trim #5446, effective position #5932) and `seekable_source.py` conversion sharing.
7. Frontend resume: `useStreamSubscriptions` (epoch adoption, late-start guard, terminal-frame epoch filter), `useStreamChunkHandler`/`audioChunkIngest.classifyChunk` (superseded-epoch drop, bounded pending queue), `useEnhancedStreamStart` (resume branch), `socketFrameParser.checkSeqForDesync` (rebaseline on epoch change; a half-sent meta/binary pair cannot fuse with the next stream because every binary frame follows its own meta), `flowDrainWatch` + `buffer_full`/`buffer_ready` (stale `flowPausedRef` after a seek self-heals within 250 ms; exempt from the rate limiter), `AudioPlaybackEngine`/`PlaybackPositionTracker`/`BufferScheduler` stop/start.

Regression guards verified still in place:
- #5860 seek_position applied to the clock on the resume path (useEnhancedStreamStart.ts:133-135, 211-213; tracker 'stopped' branch holds the offset). Gap before the ack is F8-02.
- #5861 discard of superseded buffer content on a changed epoch (useEnhancedStreamStart.ts:112-122) and terminal-frame epoch filter (useStreamSubscriptions.ts:69-72). Residual edge in F8-04.
- #5862 worklet queue teardown + `resetStreamEnded` on epoch replacement (useEnhancedStreamStart.ts:119, 126).
- #5885 keyboard burst coalescing (useKeyboardSeek.ts) and rate-limit rejection handling with a single retry (useEnhancedSeek.ts:139-152; backend sends `command`). Validation-error gap is F8-03.
- #5931 `start_chunk` offset (startChunkOffset) is present but its Redux effect is suppressed (F8-01).
- #5604 seek omits preset/intensity; backend resolves from `active_stream_settings` (seek_command.py:67-77).
- #6130 / #5254 / #5409 huge or past-end positions: `handle_seek` rejects non-finite/negative, `chunk_for_position` and `normal_stream_plan` clamp to `duration - SEEK_MIN_CHUNK_REMAINDER` and report the effective position.
- #4557 enhanced seek maps through `emitted_chunk_start` (no 5 s overshoot); #4560 normal path trims server-side; #3806/#5083 old task awaited before the new stream registers and `drain_cancelled_task` propagates caller cancellation.

Verified OK (no finding): position units are seconds on both sides; rapid consecutive seeks serialise through the receive loop and the last one wins (each cancels and awaits its predecessor; a seek cancelled before its first step never registers anything); stale pre-seek frames are removed by the per-chunk epoch filter plus the buffer reset on the new epoch; the first post-seek chunk is rendered with 5 s of pre-roll context and level-baselined (no history), so no gain ramp against an unrelated chunk; `seek_offset` trim cannot exceed the emitted segment (sliver rule); `audio_stream_error` for a failed first chunk reports the exact seek target as `recovery_position`; the seek stream does not start the proactive buffer task; pause is client-side only (no WS pause is sent), so the seek's fresh pause event cannot desync pause state.

Minor observation, not reported: a normal-mode seek to exactly 0 is still sent without `is_seek` (`stream_normal.py` builds `seek_kwargs` only when `start_position > 0`; second half of #5932 was never done). It works because the client then rebuilds the engine and buffer, so there is no functional defect, only a heavier path than the enhanced seek-to-0.

### Flow 9 Queue & Playback State


Boundaries traced (sender and receiver, with lines):
1. Frontend mutation hooks (`useQueueEditMutations`, `useQueueModeMutations`, `queueMutationRunner/Guards`) → `routers/player_queue.py` (request bodies, indices, `QueueIndex`/`TrackIdList` bounds, route ordering `DELETE /queue/{index}` vs `PUT /queue/reorder|move`) — schema match OK for set/add/add-tracks/remove/move/reorder/clear/shuffle/repeat; error mapping via `raise_for_service_error`.
2. `QueueService` mixins ↔ `QueueController`/`QueueManager` (engine): `_queue_mutation` generation protocol + engine lock, set_queue sequencer (process-wide, #5944), `start_index` re-basing (#5933), failed `load_file` (#5996), atomic remove-current (#5360), identity-based shuffle/move/reorder (#4776/#5564), shuffle snapshot invalidation (#4525/#5315).
3. QueueService → `PlayerStateManager` (mirror in `_broadcast_queue_changed_locked`) → `player_state` snapshot → `applyPlayerStateSnapshot` (seq watermarks, #5601/#5898 gates).
4. `queue_changed` / `queue_shuffled` / `repeat_mode_changed` payloads (`websocket/outbound/queue.py`) → `types/ws/queue.ts` → `useQueueSubscription` → Redux.
5. `GET /api/player/queue` (`get_queue_info`, `QueueEnricher`) → `useQueueFetch`.
6. Client-side navigation/removal/auto-advance (`usePlaybackNavigation`, `useFollowRemovedTrack`, `useAutoAdvance`) vs the engine queue.

Verified-OK regression guards (still in place):
- #4374 enrichment on every read and broadcast path (`resolve_tracks`; unresolvable entries dropped, `current_index` and `track_count` re-based in both `get_queue_info` (#5934) and the broadcast).
- #5983: `repeat_enabled` popped in `resolve_repeat_mode`; `QueueInfoResponse.model_config extra='ignore'`.
- #5460: every edit mirrors the resolved queue into `PlayerStateManager` (`broadcast=False`) before `queue_changed`; `current_track` follows the engine pointer.
- #3205/#5455: `filepath` never reaches clients (`TrackInfo.filepath = Field(exclude=True)`; `to_track_payload` built field by field; `format` shipped instead).
- #5823: all emitters send snake_case `current_index`; the frontend reads only `current_index`.
- #5935: `queue_changed` read-hydrate-send runs under `queue_set_sequencer.broadcast_lock`.
- #5189: queue and playlist drag reorder go to `PUT /queue/move` and `/playlists/{id}/tracks/reorder` (no add-endpoint duplication); `{from_index,to_index}` match `MoveQueueTrackRequest`/`ReorderTrackRequest`.
- #5920: `enqueue-all` returns `dropped_queue_full` and the frontend surfaces it (`useFingerprintCoverage`).
- #5526: no queue history/undo remains (frontend type comment at `types/ws/queue.ts:28` still mentions a "history-undo emitter" — stale comment only).
- #6016/#5600/#5601/#4836/#5624: `useFollowRemovedTrack`, nearest-slot duplicate resolution, `reconcileQueueIndex`, per-field rollback generations and call-time snapshots all present.
- #5487: backend restart is detected via `server_instance_id` (`useServerRestartNotice` toast; watermarks reset in `observeServerInstance`); the live queue is not persisted and the empty post-restart snapshot replaces the Redux queue (`setQueue([])`, `current_track: null`).
- #5651: bulk add is one atomic append plus one broadcast; #5320/#5944: mutators supersede an in-flight `set_queue`.
- #6084 (c) deliberately left (sub-millisecond sync mutators on the event loop; confirmed from the issue's closing comment), not reported.

Checklist items: Schema match (OK, see 1/4); Error handling (4xx/5xx → `ApiErrorHandler.parseWithCode`, rollback only by newest mutation; OK); Timeouts (queue POSTs bounded by the shared 30 s transport, backend work is sub-second; OK); Data types (indices int, `duration` float seconds, `volume` 0-100 int; OK); Null handling (`queue_changed.tracks` omitted on hydration failure and ignored by client; `current_index` -1 ignored by reducer, but see F9-03); Case conversion (`artwork_url` → `artworkUrl` via `mapTrackInfoToTrack`; `format` is dropped by the mapper but unused by queue UI; OK).
